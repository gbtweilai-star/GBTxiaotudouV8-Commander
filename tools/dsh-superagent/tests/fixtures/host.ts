/**
 * In-memory DSH host fixture (as in tests/runtime.spec.ts) running a configured Runtime with GitHub and Feishu sources,
 * allowed member Alice (`ou_alice`), listened chat `oc_team`, and `auto` eval mode. Stop it with `stop()`.
 */
import { Context } from '@deepseek-ai/cordis'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { vi, type Mock } from 'vitest'
import type { UserMessage } from '@deepseek-ai/dsh-llm'
import { Runtime } from '../../src/app/runtime.ts'
import { Store } from '../../src/app/store.ts'
import { SettingsSchema } from '../../src/policy.ts'
import { feishuKind, feishuTrigger } from '../../src/sources/feishu.ts'
import { githubKind } from '../../src/sources/github.ts'
import { Commands } from '../../src/infra/commands.ts'
import { credentialHelper, workerGitConfig } from '../../src/infra/environment.ts'
import type { Trigger } from '../../src/core/index.ts'
import { testMachine } from './deployment.ts'

export const MEMBER = 'ou_alice'
export const CHAT = 'oc_team'

/** Build a Feishu mention trigger from Alice in `oc_team`, using the digits in `id` as the timestamp offset in seconds. */
export function feishu(id: string, text: string, overrides: Record<string, unknown> = {}): Trigger {
  const at = String(Date.parse('2026-09-09T00:00:00Z') + Number(id.replace(/\D/g, '') || 0) * 1000)
  return feishuTrigger({ message_id: `om_${id}`, chat_id: CHAT, chat_type: 'group', sender_id: MEMBER, sender_type: 'user', content: text, create_time: at,
    mentions: [{ id: 'ou_bot' }], ...overrides }, 'ou_bot', 'cli_bot')!
}

type RegisteredTool = { name: string; execute: (args: unknown, execution: { signal: AbortSignal }) => Promise<unknown> }
type FakeAgent = {
  id: string; status: string; inbox: { nextTurn: UserMessage[]; nextStep: UserMessage[] }
  cancel: Mock; inject: Mock<(message: UserMessage) => void>; steer: Mock<(message: UserMessage) => void>; followup: Mock<(message: UserMessage) => void>
}
/** A text message, as DSH's job tools and subagents send their notices. */
const notice = (id: string, text: string) => ({ id, role: 'user', content: [{ type: 'text', text }], source: { kind: 'tool-jobs', form: 'notice' } }) as unknown as UserMessage
type HttpHandler = (req: unknown, res: unknown) => Promise<void>
type Delivery = { sessionId: string; mode: 'queue' | 'steer'; id: string; text: string }

/**
 * DSH's job registry as the Executor uses it, with DSH's job tools: the jobs a Session can see, their events, a wait and a
 * kill. `run` starts a job a Session owns, `output` has one print, and `end` ends one, as its process does; an end no wait
 * collected reaches its owner, which it wakes when idle, as the job tools deliver it. `released` counts the waits ends
 * released.
 * @param owner - the agent of a Session, which an end reaches.
 */
export function jobRegistry(owner: (sessionId: string) => FakeAgent | undefined = () => undefined) {
  type Job = { id: string; owner: string; status: string; label?: string }
  const jobs = new Map<string, Job>()
  const listeners = new Set<{ owner: string; listener: (event: { type: string }) => void }>()
  const waits = new Map<string, ((job: Job) => void)[]>()
  let released = 0
  const emit = (job: Job, type: string) => { for (const listener of [...listeners]) if (listener.owner === job.owner) listener.listener({ type }) }
  const end = (id: string, status = 'completed') => {
    const job = jobs.get(id)!
    job.status = status
    const waiting = waits.get(id) ?? []
    waits.delete(id); released += waiting.length
    for (const wake of waiting) wake({ ...job })
    emit(job, 'settled')
    const agent = waiting.length ? undefined : owner(job.owner)
    const ended = notice(`notice-${id}`, `Job ${id} ended: ${status}`)
    if (agent?.status === 'idle') agent.followup(ended)
    else agent?.inject(ended)
  }
  const service = {
    list: vi.fn((caller: string) => [...jobs.values()].filter(job => job.owner === caller)),
    // A wait ends with the job, or fails once its signal aborts, which leaves the job's end uncollected.
    wait: vi.fn((id: string, _timeoutMs: number, _caller: string, signal?: AbortSignal) => new Promise<Job>((resolve, reject) => {
      const wake = (job: Job) => { signal?.removeEventListener('abort', abort); resolve(job) }
      const abort = () => { waits.set(id, (waits.get(id) ?? []).filter(item => item !== wake)); reject(new Error('wait aborted')) }
      waits.set(id, [...waits.get(id) ?? [], wake])
      signal?.addEventListener('abort', abort, { once: true })
    })),
    // A killed job ends a moment later, as its process does, also under a test's fake timers.
    kill: vi.fn((id: string) => { queueMicrotask(() => { end(id, 'killed') }); return 'requested' }) as Mock<(id: string) => string>,
    events: { subscribe: (filter: { owner: string }, listener: (event: { type: string }) => void) => {
      const entry = { owner: filter.owner, listener }
      listeners.add(entry)
      return () => { listeners.delete(entry) }
    } },
  }
  return { service, end, output: (id: string) => { emit(jobs.get(id)!, 'output') }, get released() { return released },
    run: (owner: string, label?: string) => { const id = `bash-${jobs.size + 1}`; jobs.set(id, { id, owner, status: 'running', label }); return id } }
}

/**
 * DSH's subagents as the Executor uses them. `spawn` starts a child of a Session, an agent while it lives, which a drain of
 * the Session's descendants refuses from then on; `settle` ends one, whose end wakes its idle parent or steers a running one
 * before a wait for the parent's children returns. Releasing or interrupting a child settles it; a drain of descendants
 * injects their ends. The catalog lists every child a Session had.
 */
export function subagentRuntime(agents: Map<string, FakeAgent>) {
  const children = new Map<string, { parent: string; live: boolean; settled: PromiseWithResolvers<void> }>()
  const closed = new Set<string>()
  const settle = (id: string, wake = true) => {
    const child = children.get(id)
    if (!child?.live) return
    child.live = false
    agents.delete(id)
    const parent = agents.get(child.parent), ended = notice(`settled-${id}`, `Subagent ${id} settled`)
    if (!wake) parent?.inject(ended)
    else if (parent?.status === 'idle') parent.followup(ended)
    else parent?.steer(ended)
    child.settled.resolve()
  }
  const service = {
    waitForChildren: vi.fn(async (parent: { id: string }) => {
      const live = [...children.values()].filter(child => child.parent === parent.id && child.live)
      await Promise.all(live.map(child => child.settled.promise))
      return live.length > 0
    }),
    listChildren: vi.fn(async (id: string) => [...children].filter(([, child]) => child.parent === id).map(([childId]) => ({ id: childId }))),
    drainChildren: vi.fn(async (_parent: { id: string }, ids: readonly string[]) => { for (const id of ids) settle(id) }),
    drainDescendants: vi.fn(async (parents: readonly { id: string }[]) => {
      for (const parent of parents) {
        closed.add(parent.id)
        for (const [id, child] of children) if (child.parent === parent.id) settle(id, false)
      }
    }),
    interrupt: vi.fn((id: string) => { settle(id) }),
  }
  const spawn = (parent: string) => {
    if (closed.has(parent)) throw new Error('DRAINING: the Session admits no new subagents')
    const id = `child-${children.size + 1}`
    children.set(id, { parent, live: true, settled: Promise.withResolvers<void>() })
    agents.set(id, { id, status: 'running', session: { header: { parentSession: parent } } } as never)
    return id
  }
  return { service, settle, spawn, live: (id: string) => !!children.get(id)?.live }
}

/** @param seed - writes to the database before the Runtime opens it, such as records an earlier version stored. */
export async function startRuntime(seed?: (store: Store) => void) {
  const directory = mkdtempSync(join(tmpdir(), 'orchestrator-host-'))
  const AGENT = join(directory, 'agent-gh'), BOT = join(directory, 'lark-bot')
  const repository = { default_branch: 'master', permissions: { push: true } }
  vi.spyOn(Commands.prototype, 'gh').mockImplementation(async args => args[1] === 'user' ? { login: 'agent-bot' } : repository)
  vi.spyOn(Commands.prototype, 'lark').mockResolvedValue({ users: [{ member_id: MEMBER, name: 'Alice' }], has_more: false })
  vi.spyOn(Commands.prototype, 'git').mockResolvedValue('')
  vi.spyOn(Commands.prototype, 'run').mockResolvedValue('{"ok":true,"data":{}}')
  const scoped = 'git config -z --show-scope --get-regexp ^(credential\\..*|http\\..*extraheader)$'
  const answers: Record<string, string> = {
    [`${AGENT} api user`]: '{"login":"agent-bot","id":7}',
    [`${AGENT} api repos/acme/widgets --jq {name: .full_name, push: .permissions.push}`]: '{"name":"acme/widgets","push":true}\n',
    [`${BOT} auth status`]: JSON.stringify({ appId: 'cli_bot', brand: 'feishu', identities: { bot: { status: 'ready' } } }),
    [`${BOT} config strict-mode`]: 'strict-mode: bot (source: profile)',
    [`${BOT} api GET /open-apis/bot/v3/info --as bot --format ndjson`]: '{"bot":{"open_id":"ou_bot"},"code":0,"msg":"ok"}',
    ['git config -z --show-origin --get-all credential.https://github.com.helper']: `file:${workerGitConfig(directory)}\0${credentialHelper(AGENT)}\0`,
    [scoped]: `global\0credential.helper\n\0global\0credential.https://github.com.helper\n${credentialHelper(AGENT)}\0`,
  }
  /** A prepare command (`sh -c`) waits for this while it is set. */
  const hooks: { prepare?: Promise<void> } = {}
  const subprocess = { spawn: vi.fn((spec: { argv: readonly string[] }) => {
    const argv = [...spec.argv]
    while (argv[0] === 'env' || /^[A-Z_]+=/.test(argv[0] ?? '')) argv.shift()
    const reader = (text: string) => ({ readFrom: () => ({ text, nextOffset: text.length, lossy: false }) })
    const exited = { exitCode: 0, signal: null }
    const done = argv[0] === 'sh' && hooks.prepare ? hooks.prepare.then(() => exited) : Promise.resolve(exited)
    return { done, collected: { stdout: reader(answers[argv.join(' ')] ?? ''), stderr: reader('') } }
  }) }
  const agents = new Map<string, FakeAgent>()
  /** Each Session's next step, which takes the messages that wait for one. */
  const steps = new Map<string, () => void>(), claims = new Map<string, () => void>()
  const tools = new Map<string, Map<string, RegisteredTool>>()
  const deliveries = vi.fn<(request: Delivery) => void>()
  let http!: HttpHandler
  const resolveDefault = async (id: string) => agents.has(id) ? { agent: agents.get(id) } : { error: { code: 'session/not-found' } }
  const controller = {
    create: vi.fn(async ({ sessionId }: { sessionId: string }) => {
      if (agents.has(sessionId)) return
      const agentCtx = new Context()
      const sessionTools = new Map<string, RegisteredTool>()
      tools.set(sessionId, sessionTools)
      const register = (tool: RegisteredTool) => { sessionTools.set(tool.name, tool); return () => sessionTools.delete(tool.name) }
      agentCtx.reflect.provide('tools', { register, get: () => undefined, restrict: vi.fn(() => () => {}), guard: vi.fn(() => () => {}) })
      agentCtx.reflect.provide('skills', { register: () => () => {} })
      agentCtx.reflect.provide('systemPrompt', { section: () => () => {} })
      const inbox = { nextTurn: [] as UserMessage[], nextStep: [] as UserMessage[],
        // A pending message taken out, as DSH's inbox does by its id.
        remove: (id: string) => [inbox.nextTurn, inbox.nextStep].some(list => {
          const at = list.findIndex(message => message.id === id)
          if (at >= 0) list.splice(at, 1)
          return at >= 0
        }) }
      // A step claims each message once, all that wait for a step and, as a turn starts, the next queued one, and takes them into
      // the Session's history, unless it is `cut` off before, as a cancel in its pre-step does; DSH says each.
      const taken = new Set<string>()
      let turn = 0
      const take = (starts: boolean, cut = false) => {
        const agent = agents.get(sessionId)!
        const queued = starts ? inbox.nextTurn.filter(message => !taken.has(message.id)).slice(0, 1) : []
        for (const message of [...inbox.nextStep.filter(item => !taken.has(item.id)), ...queued]) {
          taken.add(message.id)
          ctx.emit('agent/inbox/claimed', { agent, message, turn } as never)
          if (!cut) ctx.emit('session/event', session as never, { type: 'user/message', data: message } as never)
        }
      }
      steps.set(sessionId, () => { take(false) })
      claims.set(sessionId, () => { take(false, true) })
      const deliver = (mode: 'queue' | 'steer') => vi.fn((message: UserMessage) => {
        inbox[mode === 'queue' ? 'nextTurn' : 'nextStep'].push(message)
        deliveries({ sessionId, mode, id: message.id, text: message.content.map(block => block.type === 'text' ? block.text : '').join('') })
        // A message wakes an idle agent: its turn starts at once, and DSH says so, and its first step takes what waits.
        const agent = agents.get(sessionId)!
        if (agent.status !== 'idle') return
        agent.status = 'running'
        ctx.emit('agent/status', { agent, status: 'running' } as never)
        turn++
        take(true)
      })
      const session = { id: sessionId, snapshotEvents: () => [], requestHeader: () => undefined, append: vi.fn() }
      let status = 'idle'
      const idle: (() => void)[] = []
      // A cancel drops the inbox unless kept, and the turn it stops ends a moment later, which DSH says.
      const cancel = vi.fn((_cause: unknown, options?: { keepInbox?: boolean }) => {
        if (!options?.keepInbox) { inbox.nextTurn.length = 0; inbox.nextStep.length = 0 }
        if (status === 'idle') return
        queueMicrotask(() => {
          const agent = agents.get(sessionId)!
          if (agent.status === 'idle') return
          agent.status = 'idle'
          ctx.emit('agent/status', { agent, status: 'idle' } as never)
        })
      })
      agents.set(sessionId, { id: sessionId, ctx: agentCtx, inbox, followup: deliver('queue'), steer: deliver('steer'), inject: vi.fn(), session, cancel,
        get status() { return status }, set status(next: string) { status = next; if (next === 'idle') for (const wake of idle.splice(0)) wake() },
        // Once its turn ended, as DSH's does.
        whenIdle: () => status === 'idle' ? Promise.resolve() : new Promise<void>(resolve => { idle.push(resolve) }) } as never)
    }),
    selectModel: vi.fn(async () => {}), resolveAgent: vi.fn(resolveDefault), rename: vi.fn(async () => {}),
    prompt: vi.fn(() => { throw new Error('Plugin delivery must not use user RPC') }),
    inspect: vi.fn(async () => ({ events: [] })),
  }
  const reader = { read: async () => ({ events: [] }), [Symbol.asyncDispose]: async () => {} }
  const persistence = { flush: vi.fn(async () => {}), open: vi.fn(async () => reader) }
  const webServer = { host: '127.0.0.1', port: 3082, register: (route: { handler: HttpHandler }) => { http = route.handler; return () => {} } }
  const jobs = jobRegistry(id => agents.get(id))
  const subagents = subagentRuntime(agents)
  const services = { agents, llm: { resolveCallConfig: vi.fn(async (value: unknown) => value) }, sessionController: controller,
    sessionPersistence: persistence, workspaceRegistry: { create: async (cwd: string) => ({ id: cwd }) }, permissionPresets: { set: () => {} }, subprocess, webServer,
    jobs: jobs.service, subagents: subagents.service }
  const ctx = new Context()
  for (const [name, service] of Object.entries(services)) ctx.reflect.provide(name, service)
  for (const cli of [AGENT, BOT]) writeFileSync(cli, '#!/bin/sh\n', { mode: 0o755 })
  const seeded = new Store(join(directory, 'orchestrator.sqlite'))
  const sources = { github: { enabled: true, config: { repository: 'acme/widgets', cli: AGENT } }, feishu: { enabled: true, config: { cli: BOT } } }
  seeded.saveSettings(SettingsSchema.parse({ ...seeded.settings(), sources }))
  seed?.(seeded)
  seeded.close()
  const runtime = new Runtime(ctx, testMachine({ stateDir: directory }), vi.fn())
  await runtime.ready
  runtime.sources.register(feishuKind); runtime.sources.register(githubKind)
  const settings = runtime.store.settings()
  runtime.store.saveSettings({ ...settings, eval: { ...settings.eval, mode: 'auto' },
    policy: { ...settings.policy, sources: { feishu: { allowed: [{ id: MEMBER, name: 'Alice' }], syncChat: CHAT }, github: { allowed: [{ id: 'alice' }] } } },
    sources: { ...sources, feishu: { enabled: true, config: { cli: BOT, chats: [{ chatId: CHAT, listen: 'all' }], directMessages: true } } } })
  deliveries.mockClear()

  /** Parsed JSON payloads delivered to `sessionId`. */
  const relays = (sessionId: string) => deliveries.mock.calls.map(([call]) => call).filter(call => call.sessionId === sessionId)
    .map(call => JSON.parse(call.text) as Record<string, unknown>)
  const candidates = () => relays(runtime.masterId).filter(item => item.kind === 'candidate').map(item => item.trigger_id)
  const runTool = async (sessionId: string, name: string, args: unknown) => {
    const tool = tools.get(sessionId)?.get(name)
    if (!tool) throw new Error(`Tool ${name} is not registered for ${sessionId}`)
    return await tool.execute(args, { signal: new AbortController().signal }) as Record<string, unknown>
  }
  /** Route one decision with the main Session's orchestrator_route, answering its result; a refused one throws its reason. */
  async function route(item: Record<string, unknown>): Promise<Record<string, unknown>> {
    const { results } = await runTool(runtime.masterId, 'orchestrator_route', { decisions: [item] }) as { results: Record<string, unknown>[] }
    if (results[0]!.refused) throw new Error(String(results[0]!.refused))
    return results[0]!
  }
  async function acceptedTicket(trigger: Trigger) {
    runtime.receive(trigger)
    await runtime.idle()
    const result = await route({ kind: 'accept', trigger_id: trigger.id, title: `Fix ${trigger.id}`, worktree_name: 'fix-regression', acknowledgement: '收到，修复回归。' })
    await runtime.idle()
    const ticket = runtime.store.tickets.get((result.ticket as { ticket_id: string }).ticket_id)!
    return { trigger, ticket, sessionId: `worker-${ticket.id}` }
  }
  async function api(method: string, path: string, json?: unknown) {
    let status = 0, text = ''
    const chunks = json === undefined ? [] : [Buffer.from(JSON.stringify(json))]
    const req = { method, url: `/orchestrator/api/${path}`, headers: { host: '127.0.0.1:3082', 'x-orchestrator-request': '1' }, async *[Symbol.asyncIterator]() { yield* chunks } }
    await http(req, { writeHead: (code: number) => { status = code }, end: (data: string) => { text = data } })
    return { status, body: JSON.parse(text) as Record<string, unknown> }
  }
  async function stop() { await runtime.stop(); vi.restoreAllMocks(); rmSync(directory, { recursive: true, force: true }) }
  /** The Session's model takes its next step, which takes the messages steered in since its last. */
  const step = (sessionId: string) => { steps.get(sessionId)!() }
  /** A step of the worker claims what waits for it, and is cut off before the Session took it. */
  const claim = (sessionId: string) => { claims.get(sessionId)!() }
  return { runtime, ctx, directory, agents, tools, deliveries, relays, candidates, runTool, route, acceptedTicket, api, controller, subprocess, hooks, resolveDefault, stop,
    jobs, subagents, step, claim }
}
export type Host = Awaited<ReturnType<typeof startRuntime>>
