/** Concurrent runtime behavior across overlapping triggers, deliveries, and worker launches. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { latestAssignment, waitsForPerson, type Ticket, type Trigger } from '../src/core/index.ts'
import { Later } from '../src/app/effects.ts'
import { reportRelay } from '../src/app/notices.ts'
import { WorkerSlots, inputMessage, mandateInstructions, ticketExecution, transient, triggerMessage } from '../src/executor/dsh.ts'
import { SettingsSchema } from '../src/policy.ts'
import { Commands } from '../src/infra/commands.ts'
import { deferred, waitUntil } from './fixtures/async.ts'
import { CHAT, MEMBER, feishu, startRuntime, type Host } from './fixtures/host.ts'

let h: Host
beforeEach(async () => { h = await startRuntime() })
afterEach(async () => { await h.stop() })
const lark = { users: [{ member_id: MEMBER, name: 'Alice' }], has_more: false }
const linkLookedUp = (messageId: string) =>
  vi.mocked(Commands.prototype.lark).mock.calls.some(([args]) => args.includes('+messages-mget') && args.includes(messageId))
/** Hold the first resolution of a Session until `gate` resolves; `held()` says whether it began. */
function holdSession(sessionId: string, gate: Promise<void>) {
  let held = false
  h.controller.resolveAgent.mockImplementation(async (id: string) => { if (id === sessionId && !held) { held = true; await gate } return h.resolveDefault(id) })
  return () => held
}
/** The turn of a Session's agent ends, and DSH says so. */
const idle = (sessionId: string) => {
  const agent = h.agents.get(sessionId)!
  agent.status = 'idle'
  h.ctx.emit('agent/status', { agent, status: 'idle' } as never)
}

it('evaluates a message that arrives on a thread while an earlier candidate\'s card waits for its link, in the thread\'s next Eval', async () => {
  const gate = deferred()
  // The first candidate's source link lookup is slow; Feishu allows it up to linkTimeoutMs.
  vi.mocked(Commands.prototype.lark).mockImplementation(async args => { if (args.includes('+messages-mget') && args.includes('om_1')) await gate.promise; return lark })
  await h.runtime.settings.pause(true, 'panel')
  const a1 = feishu('1', '@bot 修 A'), b1 = feishu('2', '@bot 修 B'), b2 = feishu('3', '@bot B 还有这个', { root_id: 'om_2' })
  h.runtime.receive(a1); h.runtime.receive(b1)
  await h.runtime.settings.pause(false, 'panel')
  await waitUntil(() => linkLookedUp('om_1'))
  h.runtime.receive(b2)
  gate.resolve(); await h.runtime.idle()
  const threadB = `feishu:${CHAT}:om_2`
  expect(h.runtime.store.threads.get(threadB)).toMatchObject({ evaluating: { triggerIds: [b1.id] }, pending: [b2.id] })
  await h.route({ kind: 'ignore', trigger_id: b1.id, reason: 'duplicate' })
  await h.runtime.idle()
  expect(h.runtime.store.threads.get(threadB)).toMatchObject({ evaluating: { triggerIds: [b2.id] }, pending: [] })
  // A slow link lookup holds only its own candidate's card.
  expect(h.candidates()).toEqual([b1.id, a1.id, b2.id])
})

it('delivers nothing to a ticket a person stopped while an earlier ticket\'s delivery waited', async () => {
  const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
  const two = await h.acceptedTicket(feishu('5', '@bot 修二'))
  await h.runtime.settings.pause(true, 'panel')
  h.runtime.receive(feishu('2', '一的补充', { mentions: [], root_id: 'om_1', sender_id: 'ou_guest' }))
  h.runtime.receive(feishu('6', '二的补充', { mentions: [], root_id: 'om_5', sender_id: 'ou_guest' }))
  // Tickets are processed newest-first, so holding ticket two pauses the pass before ticket one is delivered.
  const gate = deferred()
  const held = holdSession(two.sessionId, gate.promise)
  const resumed = h.runtime.settings.pause(false, 'panel')
  await waitUntil(held)
  await h.runtime.engine.stopTicket(one.ticket.id)
  const before = h.deliveries.mock.calls.length
  gate.resolve(); await resumed; await h.runtime.idle()
  expect(h.deliveries.mock.calls.slice(before).map(([call]) => call.sessionId)).not.toContain(one.sessionId)
  expect(h.runtime.store.tickets.get(one.ticket.id)).toMatchObject({ ended: { by: 'human' }, undelivered: [] })
})

it('drops a delivery whose ticket a person stopped while it waited for the worker Session', async () => {
  const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
  await h.runtime.settings.pause(true, 'panel')
  h.runtime.receive(feishu('2', '一的补充', { mentions: [], root_id: 'om_1', sender_id: 'ou_guest' }))
  const gate = deferred()
  const held = holdSession(one.sessionId, gate.promise)
  const resumed = h.runtime.settings.pause(false, 'panel')
  await waitUntil(held)
  await h.runtime.engine.stopTicket(one.ticket.id)
  const before = h.deliveries.mock.calls.length
  gate.resolve(); await resumed; await h.runtime.idle()
  expect(h.deliveries.mock.calls.slice(before).map(([call]) => call.sessionId)).not.toContain(one.sessionId)
  expect(h.runtime.store.tickets.get(one.ticket.id)).not.toHaveProperty('delivery')
})

it('runs prepare commands in the background, side by side, while accepts, intake and passes go on', async () => {
  const settings = h.runtime.store.settings()
  h.runtime.store.saveSettings({ ...settings, executor: { ...settings.executor, prepare: 'git -C /srv/widgets worktree add "$DSH_SUPERAGENT_DIR"' } })
  const prepare = deferred()
  h.hooks.prepare = prepare.promise
  const prepares = () => h.subprocess.spawn.mock.calls.filter(([spec]) => spec.argv[0] === 'sh').length
  const first = [feishu('1', '@bot 修一'), feishu('2', '@bot 修二')]
  for (const trigger of first) h.runtime.receive(trigger)
  await h.runtime.idle()
  for (const [index, trigger] of first.entries()) {
    const accepted = await h.route({ kind: 'accept', trigger_id: trigger.id, title: 'fix', worktree_name: `fix-${index}`, acknowledgement: '收到。' })
    expect(accepted).toMatchObject({ decision: 'accept', ticket: { state: 'working/queued' } })
  }
  await waitUntil(() => prepares() === 2)
  // A Source loop's next message is stored at once, and a pass relays it while both prepare commands still run.
  const later = feishu('3', '@bot 修三')
  expect(h.runtime.receive(later)).toBe('stored')
  await h.runtime.pump()
  expect(h.candidates()).toEqual([...first, later].map(trigger => trigger.id))
  prepare.resolve()
  await h.runtime.idle()
  expect(h.runtime.store.tickets.list().map(ticket => ticket.assignments.at(-1)!.state)).toEqual(['running', 'running'])
})

it('keeps a launch that a pause cut short queued, and finishes it once processing resumes', async () => {
  const settings = h.runtime.store.settings()
  h.runtime.store.saveSettings({ ...settings, executor: { ...settings.executor, prepare: 'make worktree' } })
  const prepare = deferred()
  h.hooks.prepare = prepare.promise
  const trigger = feishu('1', '@bot 修一')
  h.runtime.receive(trigger); await h.runtime.idle()
  await h.route({ kind: 'accept', trigger_id: trigger.id, title: 'fix', worktree_name: 'fix-one', acknowledgement: '收到。' })
  await waitUntil(() => h.subprocess.spawn.mock.calls.some(([spec]) => spec.argv[0] === 'sh'))
  await h.runtime.settings.pause(true, 'panel')
  prepare.resolve(); await h.runtime.idle()
  const [ticket] = h.runtime.store.tickets.list()
  expect(ticket!.assignments).toEqual([expect.objectContaining({ state: 'pending' })])
  expect(h.runtime.effects.pending('launch')).toBe(true)
  vi.useFakeTimers({ toFake: ['Date'], now: Date.now() + 6000 })
  try { await h.runtime.settings.pause(false, 'panel'); await h.runtime.idle() } finally { vi.useRealTimers() }
  expect(h.runtime.store.tickets.get(ticket!.id)!.assignments).toEqual([expect.objectContaining({ state: 'running' })])
})

const botMessage = () => feishu('2', 'CI 失败', { mentions: [], root_id: 'om_1', sender_id: 'cli_ci', sender_type: 'bot' })
it('wakes an idle worker for a bot\'s Input only when a worker slot is free, and creates a worker Session someone deleted again', async () => {
  const settings = h.runtime.store.settings()
  h.runtime.store.saveSettings({ ...settings, executor: { ...settings.executor, maxWorkers: 1 } })
  const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
  h.agents.get(one.sessionId)!.status = 'idle'
  const two = await h.acceptedTicket(feishu('5', '@bot 修二'))
  expect(h.agents.get(two.sessionId)!.status).toBe('running')
  h.runtime.receive(botMessage()); await h.runtime.idle()
  // Ticket two's worker takes the only slot, so ticket one's Input waits.
  expect(h.runtime.store.tickets.get(one.ticket.id)!.undelivered).toHaveLength(1)
  h.agents.get(two.sessionId)!.status = 'idle'
  h.agents.delete(one.sessionId)
  vi.useFakeTimers({ toFake: ['Date'], now: Date.now() + 6000 })
  try { await h.runtime.pump(); await h.runtime.idle() } finally { vi.useRealTimers() }
  expect(h.runtime.store.tickets.get(one.ticket.id)!.undelivered).toEqual([])
  expect(h.agents.get(one.sessionId)!.status).toBe('running')
})

it('wakes an idle worker for a person\'s message at once, in the slot kept beyond the limit', async () => {
  const settings = h.runtime.store.settings()
  h.runtime.store.saveSettings({ ...settings, executor: { ...settings.executor, maxWorkers: 1 } })
  const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
  h.agents.get(one.sessionId)!.status = 'idle'
  const two = await h.acceptedTicket(feishu('5', '@bot 修二'))
  expect(h.agents.get(two.sessionId)!.status).toBe('running')
  h.runtime.receive(feishu('2', '一的补充', { mentions: [], root_id: 'om_1', sender_id: 'ou_guest' })); await h.runtime.idle()
  expect(h.runtime.store.tickets.get(one.ticket.id)!.undelivered).toEqual([])
  expect(h.agents.get(one.sessionId)!.status).toBe('running')
})

it('counts a launch under way against maxWorkers, so a bot\'s Input for an idle worker waits for the slot', async () => {
  const settings = h.runtime.store.settings()
  h.runtime.store.saveSettings({ ...settings, executor: { ...settings.executor, maxWorkers: 1, prepare: 'make worktree' } })
  const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
  h.agents.get(one.sessionId)!.status = 'idle'
  // Ticket two's launch holds the only slot while its prepare command runs, before its worker's Session does.
  const prepare = deferred()
  h.hooks.prepare = prepare.promise
  h.runtime.receive(feishu('5', '@bot 修二')); await h.runtime.idle()
  await h.route({ kind: 'accept', trigger_id: feishu('5', '').id, title: 'two', worktree_name: 'fix-two', acknowledgement: '收到。' })
  await waitUntil(() => h.subprocess.spawn.mock.calls.filter(([spec]) => spec.argv[0] === 'sh').length === 2)
  h.runtime.receive(botMessage()); await h.runtime.pump()
  expect(h.runtime.store.tickets.get(one.ticket.id)!.undelivered).toHaveLength(1)
  expect(h.agents.get(one.sessionId)!.status).toBe('idle')
  prepare.resolve(); await h.runtime.idle()
  const two = h.runtime.store.tickets.list().find(ticket => ticket.id !== one.ticket.id)!
  expect(h.agents.get(`worker-${two.id}`)!.status).toBe('running')
  // The slot is ticket two's now, so ticket one's Input still waits.
  expect(h.runtime.store.tickets.get(one.ticket.id)!.undelivered).toHaveLength(1)
})

it('records on the ticket that its worker Session could not be created again', async () => {
  const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
  h.agents.get(one.sessionId)!.status = 'idle'
  h.agents.delete(one.sessionId)
  h.controller.resolveAgent.mockImplementation(async (id: string) => {
    if (id === one.sessionId) throw new Error('The Session store is offline')
    return h.resolveDefault(id)
  })
  h.runtime.receive(feishu('2', '一的补充', { mentions: [], root_id: 'om_1', sender_id: 'ou_guest' })); await h.runtime.idle()
  expect(h.runtime.store.tickets.get(one.ticket.id)).toMatchObject({ delivery: { error: expect.stringContaining('The Session store is offline') } })
})

it('lets a worker go on after a passing provider failure, three times, before its ticket fails', async () => {
  const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
  const ticket = () => h.runtime.store.tickets.get(one.ticket.id)!
  const fail = (error: unknown) => { h.ctx.emit('agent/error', { agent: h.agents.get(one.sessionId), turn: 1, step: 1, error } as never) }
  const busy = Object.assign(new Error('Service Unavailable'), { status: 503 })
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  try {
    fail(busy)
    await vi.advanceTimersByTimeAsync(15_000)
    expect(h.deliveries.mock.calls.map(([call]) => call).filter(call => call.sessionId === one.sessionId).at(-1)!.text)
      .toContain('Your last turn failed for a passing reason')
    expect(latestAssignment(ticket())?.report).toBeUndefined()
  } finally { vi.useRealTimers() }
  fail(busy); fail(busy)
  expect(latestAssignment(ticket())?.report).toBeUndefined()
  // The fourth passing failure fails the ticket, as any other failure does at once.
  fail(busy)
  await vi.waitFor(() => expect(latestAssignment(ticket())?.report).toMatchObject({ state: 'failed', summary: expect.stringContaining('Service Unavailable') }))
})
describe('a worker that goes on after a passing failure', () => {
  const busy = () => Object.assign(new Error('Service Unavailable'), { status: 503 })
  const told = (sessionId: string) => h.deliveries.mock.calls.map(([call]) => call)
    .filter(call => call.sessionId === sessionId && call.text.includes('Your last turn failed for a passing reason'))
  it('starts the count of passing failures again once its turn ends as turns do', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    const agent = h.agents.get(one.sessionId)!
    const ticket = () => h.runtime.store.tickets.get(one.ticket.id)!
    const fail = () => { h.ctx.emit('agent/error', { agent, turn: 1, step: 1, error: busy() } as never) }
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try { fail(); fail(); fail(); await vi.advanceTimersByTimeAsync(60_000) } finally { vi.useRealTimers() }
    expect(told(one.sessionId)).toHaveLength(3)
    // Once the resumed turn ends normally, a later passing failure starts a new retry count rather than counting as the fourth in a row.
    agent.status = 'idle'
    h.ctx.emit('agent/status', { agent, status: 'idle' } as never)
    await vi.waitFor(() => expect(latestAssignment(ticket())?.report?.state).toBe('waiting'))
    fail()
    await h.runtime.idle()
    expect(latestAssignment(ticket())?.report?.state).toBe('waiting')
  })
  it('waits while processing is paused, and goes on once it resumes', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    const agent = h.agents.get(one.sessionId)!
    agent.status = 'idle'
    await h.runtime.settings.pause(true, 'panel')
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      h.ctx.emit('agent/error', { agent, turn: 1, step: 1, error: busy() } as never)
      await vi.advanceTimersByTimeAsync(20_000)
      expect(told(one.sessionId)).toEqual([])
      await h.runtime.settings.pause(false, 'panel')
      await vi.advanceTimersByTimeAsync(5000)
    } finally { vi.useRealTimers() }
    expect(told(one.sessionId)).toHaveLength(1)
  })
  it('drops its timer when the host stops within the backoff', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      h.ctx.emit('agent/error', { agent: h.agents.get(one.sessionId), turn: 1, step: 1, error: busy() } as never)
      await h.runtime.stop()
      // Its timer is cleared with the Executor, so nothing reads the closed database.
      await vi.advanceTimersByTimeAsync(60_000)
    } finally { vi.useRealTimers() }
    expect(told(one.sessionId)).toEqual([])
  })
})
describe('a worker whose work runs in the background', () => {
  /** The worker's last words, as its Session holds them. */
  const said = (sessionId: string, text: string) => {
    (h.agents.get(sessionId) as unknown as { session: { snapshotEvents: () => unknown[] } }).session.snapshotEvents =
      () => [{ type: 'assistant/message', data: { message: { content: [{ type: 'text', text }] } } }]
  }
  const minutes = (n: number) => vi.advanceTimersByTimeAsync(n * 60_000)
  it('stays busy while its shell job runs, holding its slot, and reports waiting once the job ended and its turn ends', async () => {
    const settings = h.runtime.store.settings()
    h.runtime.store.saveSettings({ ...settings, executor: { ...settings.executor, maxWorkers: 1 } })
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    const ticket = () => h.runtime.store.tickets.get(one.ticket.id)!
    const job = h.jobs.run(one.sessionId)
    idle(one.sessionId); await h.runtime.idle()
    // No waiting report and nothing relayed while the job runs; the next ticket waits for the slot the job holds.
    expect(latestAssignment(ticket())?.report).toBeUndefined()
    const two = await h.acceptedTicket(feishu('5', '@bot 修二'))
    expect(latestAssignment(h.runtime.store.tickets.get(two.ticket.id)!)).toMatchObject({ state: 'pending' })
    // The job ends, which wakes the worker with its result; its turn ends, and it reports waiting.
    h.jobs.end(job)
    expect(h.agents.get(one.sessionId)!.status).toBe('running')
    idle(one.sessionId)
    await vi.waitFor(() => expect(latestAssignment(ticket())?.report?.state).toBe('waiting'))
  })
  it('stays busy while a subagent of it works, and reports waiting once the turn its end woke it for ends', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    const ticket = () => h.runtime.store.tickets.get(one.ticket.id)!
    const child = h.subagents.spawn(one.sessionId)
    idle(one.sessionId); await h.runtime.idle()
    expect(latestAssignment(ticket())?.report).toBeUndefined()
    h.subagents.settle(child)
    expect(h.agents.get(one.sessionId)!.status).toBe('running')
    idle(one.sessionId)
    await vi.waitFor(() => expect(latestAssignment(ticket())?.report?.state).toBe('waiting'))
  })
  it('kills its shell jobs and releases its subagents when its ticket stops, whose ends wake no one, and lets it start new ones', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    const agent = h.agents.get(one.sessionId)!
    const job = h.jobs.run(one.sessionId), child = h.subagents.spawn(one.sessionId)
    h.runtime.engine.stopTicket(one.ticket.id)
    await vi.waitFor(() => expect(h.jobs.service.kill).toHaveBeenCalledWith(job, one.sessionId, expect.any(String)))
    await vi.waitFor(() => expect(h.subagents.service.drainChildren).toHaveBeenCalledWith(agent, [child]))
    // The kill's end released the stop's own wait, which is how DSH tells the worker's job tools it was collected; the
    // released subagent's end, which DSH delivers before the release returns, is dropped with the turn it woke.
    expect(h.jobs.released).toBe(1)
    await vi.waitFor(() => expect(agent.cancel.mock.invocationCallOrder.at(-1)).toBeGreaterThan(h.subagents.service.drainChildren.mock.invocationCallOrder[0]!))
    expect(agent.cancel).toHaveBeenLastCalledWith({ kind: 'user' }, { keepInbox: false })
    // Its Session still admits subagents, as when the ticket resumes.
    expect(() => h.subagents.spawn(one.sessionId)).not.toThrow()
  })
  it('reports waiting for the Assignment that replaced one whose idle still waited for its subagents', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    const ticket = () => h.runtime.store.tickets.get(one.ticket.id)!
    // The first Assignment's turn ends while a subagent of it works.
    const child = h.subagents.spawn(one.sessionId)
    idle(one.sessionId); await h.runtime.idle()
    // Delivering a person's message fails, and a person retries: the subagent is released, and a second Assignment starts.
    h.runtime.engine.deliveryFailed(one.ticket.id, latestAssignment(ticket())!.id, 'Session busy')
    h.runtime.engine.retryTicket(one.ticket.id); await h.runtime.idle()
    await vi.waitFor(() => expect(latestAssignment(ticket())).toMatchObject({ state: 'running' }))
    expect(h.subagents.live(child)).toBe(false)
    // The second Assignment's turn ends: it is reported waiting.
    idle(one.sessionId)
    await vi.waitFor(() => expect(latestAssignment(ticket())?.report?.state).toBe('waiting'))
    expect(ticket().assignments).toHaveLength(2)
  })
  /**
   * A worker that hands off to a person, with `report`, frees its slot and stops its subagents; its job, a server for the
   * person, runs on, and its end wakes no one.
   */
  async function handsOff(report: Record<string, unknown>, before?: (ticketId: string) => void) {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    before?.(one.ticket.id)
    const job = h.jobs.run(one.sessionId, 'pnpm dev'), child = h.subagents.spawn(one.sessionId)
    await h.runTool(one.sessionId, 'orchestrator_report', report); await h.runtime.idle()
    const relayed = h.relays(h.runtime.masterId).length
    idle(one.sessionId); await h.runtime.idle()
    // The subagent stops, and the turn its end woke is cancelled; the job's end is collected.
    await vi.waitFor(() => expect(h.subagents.live(child)).toBe(false))
    await vi.waitFor(() => expect(h.agents.get(one.sessionId)!.status).toBe('idle'))
    expect(h.jobs.service.wait).toHaveBeenCalledWith(job, expect.any(Number), one.sessionId, expect.anything())
    expect(h.runtime.executor.activeCount()).toBe(0)
    expect(h.jobs.service.kill).not.toHaveBeenCalled()
    h.jobs.end(job)
    expect(h.agents.get(one.sessionId)!.status).toBe('idle')
    expect(h.jobs.released).toBe(1)
    // The worker reads of the end at its next turn.
    await vi.waitFor(() => expect(h.agents.get(one.sessionId)!.inject).toHaveBeenCalledWith(expect.objectContaining({
      content: [expect.objectContaining({ text: `Your background job ${job} (pnpm dev) ended: completed.` })] })))
    await h.runtime.idle()
    expect(h.runtime.executor.activeCount()).toBe(0)
    expect(h.relays(h.runtime.masterId)).toHaveLength(relayed)
    expect(latestAssignment(h.runtime.store.tickets.get(one.ticket.id)!)?.report).toMatchObject({ state: report.state })
    return one
  }
  it('frees the slot of a worker that reports blocked, stopping its subagents and leaving its jobs, whose end wakes no one', async () => {
    await handsOff({ state: 'blocked', summary: 'Which color?' })
  })
  it('keeps a failed worker from being woken by a job it left, and from failing again', async () => {
    await handsOff({ state: 'failed', summary: 'The build broke.' })
  })
  it('frees the slot of a worker that reports ready on a ticket that follows its pull request', async () => {
    await handsOff({ state: 'ready', summary: 'PR ready' }, ticketId => { h.runtime.engine.bindThread(ticketId, { source: 'github', id: '7' }, true) })
  })
  it('frees the slot of a worker that asks a person a question with a progress report', async () => {
    await handsOff({ state: 'progress', summary: 'The server runs.', human_action: 'Does the button look right?' })
  })
  it('leaves the background work of a turn a person started in the worker\'s Session after a hand-off to that turn', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    const agent = h.agents.get(one.sessionId)!
    await h.runTool(one.sessionId, 'orchestrator_report', { state: 'blocked', summary: 'Which color?' }); await h.runtime.idle()
    // A person answers in the worker's Session, which the ticket does not record; the turn starts a subagent and a job.
    await new Promise(resolve => setTimeout(resolve, 5))
    h.ctx.emit('agent/inbox/claimed', { agent, message: { id: 'typed', role: 'user', content: [], source: { kind: 'user' } }, turn: 2 } as never)
    const child = h.subagents.spawn(one.sessionId), job = h.jobs.run(one.sessionId)
    idle(one.sessionId); await h.runtime.idle()
    await new Promise(resolve => setTimeout(resolve, 10))
    // They keep the worker busy, as any turn's background work does.
    expect(h.subagents.live(child)).toBe(true)
    expect(h.jobs.service.wait).not.toHaveBeenCalled()
    expect(h.runtime.executor.activeCount()).toBe(1)
    h.subagents.settle(child); h.jobs.end(job)
    expect(agent.status).toBe('running')
  })
  it('leaves the jobs a worker left to a person out of a later turn\'s background work, and does not kill them at the limit', async () => {
    const one = await handsOff({ state: 'ready', summary: 'PR ready' }, ticketId => { h.runtime.engine.bindThread(ticketId, { source: 'github', id: '7' }, true) })
    const ticket = () => h.runtime.store.tickets.get(one.ticket.id)!
    // A second server, left too; then a note from the orchestrator wakes the worker, whose turn ends without a report.
    const server = h.jobs.run(one.sessionId, 'pnpm preview')
    await h.runTool(one.sessionId, 'orchestrator_report', { state: 'ready', summary: 'Preview up' }); await h.runtime.idle()
    idle(one.sessionId); await h.runtime.idle()
    await vi.waitFor(() => expect(h.jobs.service.wait).toHaveBeenCalledWith(server, expect.any(Number), one.sessionId, expect.anything()))
    await new Promise(resolve => setTimeout(resolve, 5))
    h.runtime.engine.note(one.ticket.id, 'CI passed on the pull request.'); await h.runtime.idle()
    await vi.waitFor(() => expect(h.agents.get(one.sessionId)!.status).toBe('running'))
    idle(one.sessionId)
    await vi.waitFor(() => expect(latestAssignment(ticket())?.report?.state).toBe('waiting'))
    expect(h.jobs.service.kill).not.toHaveBeenCalled()
    expect(h.runtime.executor.activeCount()).toBe(0)
  })
  it('records each end of a worker\'s turn on its Assignment, also after its ready report', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    h.runtime.engine.bindThread(one.ticket.id, { source: 'github', id: '7' }, true)
    await h.runTool(one.sessionId, 'orchestrator_report', { state: 'ready', summary: 'PR ready' }); await h.runtime.idle()
    const report = latestAssignment(h.runtime.store.tickets.get(one.ticket.id)!)!.report!
    await new Promise(resolve => setTimeout(resolve, 5))
    idle(one.sessionId); await h.runtime.idle()
    await vi.waitFor(() => expect(latestAssignment(h.runtime.store.tickets.get(one.ticket.id)!)!.idleAt! > report.at).toBe(true))
  })
  it('shows no turn end on a running Assignment whose worker works again, whatever turn ends were recorded', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    idle(one.sessionId)
    await vi.waitFor(() => expect(latestAssignment(h.runtime.store.tickets.get(one.ticket.id)!)?.report?.state).toBe('waiting'))
    await h.runTool(one.sessionId, 'orchestrator_report', { state: 'progress', summary: 'On it again' })
    const page = await h.api('GET', `tickets/${one.ticket.id}`)
    expect((page.body as { assignments: Record<string, unknown>[] }).assignments[0]).not.toHaveProperty('turnEndedAt')
  })
  it('keeps a ticket open at a merge while its worker does in the background a message it acknowledged', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    const ticket = () => h.runtime.store.tickets.get(one.ticket.id)!
    h.runtime.engine.bindThread(one.ticket.id, { source: 'github', id: '7' }, true)
    await h.runTool(one.sessionId, 'orchestrator_report', { state: 'ready', summary: 'PR ready' }); await h.runtime.idle()
    idle(one.sessionId); await h.runtime.idle()
    // A person asks for more; the worker acknowledges it, starts the work in the background and its turn ends.
    await new Promise(resolve => setTimeout(resolve, 5))
    const more = feishu('2', '再加个测试', { mentions: [], root_id: 'om_1' })
    h.runtime.receive(more); await h.runtime.idle()
    await vi.waitFor(() => expect(ticket().undelivered).toEqual([]))
    await h.runTool(one.sessionId, 'orchestrator_ack', { trigger_id: more.id, text: '收到' })
    h.jobs.run(one.sessionId)
    idle(one.sessionId); await h.runtime.idle()
    h.runtime.engine.threadClosed({ source: 'github', id: '7' }, 'merged', new Date().toISOString())
    expect(ticket().ended).toBeUndefined()
    expect(h.jobs.service.kill).not.toHaveBeenCalled()
  })
  it('keeps a worker busy with what it started after a message reached its ready ticket', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    const ticket = () => h.runtime.store.tickets.get(one.ticket.id)!
    // The ticket follows its pull request, so a ready report leaves it open.
    h.runtime.engine.bindThread(one.ticket.id, { source: 'github', id: '7' }, true)
    await h.runTool(one.sessionId, 'orchestrator_report', { state: 'ready', summary: 'PR ready' })
    idle(one.sessionId); await h.runtime.idle()
    expect(h.runtime.executor.activeCount()).toBe(0)
    // A person asks for more; the worker starts the tests in the background and ends its turn.
    await new Promise(resolve => setTimeout(resolve, 5))
    h.runtime.receive(feishu('2', '再加个测试', { mentions: [], root_id: 'om_1' })); await h.runtime.idle()
    await vi.waitFor(() => expect(latestAssignment(ticket())?.deliveredAt! >= latestAssignment(ticket())!.report!.at).toBe(true))
    const job = h.jobs.run(one.sessionId)
    idle(one.sessionId); await h.runtime.idle()
    await new Promise(resolve => setTimeout(resolve, 10))
    expect(h.jobs.service.kill).not.toHaveBeenCalled()
    expect(h.runtime.executor.activeCount()).toBe(1)
    h.jobs.end(job); idle(one.sessionId)
    await vi.waitFor(() => expect(latestAssignment(ticket())?.report?.state).toBe('waiting'))
  })
  it('gives each idle of a worker its own 30 minutes, not counting the turns that ends of its background work wake it for', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    const ticket = () => h.runtime.store.tickets.get(one.ticket.id)!
    const first = h.jobs.run(one.sessionId)
    let second = ''
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      idle(one.sessionId)
      await minutes(20)
      // The job ends and wakes the worker, which starts another and ends its turn 5 minutes later.
      h.jobs.end(first)
      second = h.jobs.run(one.sessionId)
      await minutes(5)
      idle(one.sessionId)
      // 35 minutes after the first idle, 10 after the second.
      await minutes(10)
      expect(h.jobs.service.kill).not.toHaveBeenCalled()
      expect(latestAssignment(ticket())?.report).toBeUndefined()
      await minutes(20)
    } finally { vi.useRealTimers() }
    await vi.waitFor(() => expect(h.jobs.service.kill).toHaveBeenCalledWith(second, one.sessionId, expect.any(String)))
    expect(latestAssignment(ticket())?.report?.state).toBe('waiting')
  })
  it('kills the jobs that run 30 minutes after the turn ended, leaving its subagents, and reports waiting after the worker\'s words', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    const ticket = () => h.runtime.store.tickets.get(one.ticket.id)!
    said(one.sessionId, 'The tests run in the background.')
    const job = h.jobs.run(one.sessionId, 'pnpm test\n  --watch=false'), child = h.subagents.spawn(one.sessionId)
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      idle(one.sessionId)
      await minutes(29)
      expect(latestAssignment(ticket())?.report).toBeUndefined()
      await minutes(1)
    } finally { vi.useRealTimers() }
    await vi.waitFor(() => expect(latestAssignment(ticket())?.report).toMatchObject({ state: 'waiting', summary: 'The tests run in the background.\n\n'
      + `Background jobs ran 30 minutes after the worker's turn ended and were killed: ${job} (pnpm test).` }))
    expect(h.jobs.service.kill).toHaveBeenCalledWith(job, one.sessionId, expect.any(String))
    // The kill was collected, so the worker reads of it at its next turn.
    expect(h.agents.get(one.sessionId)!.inject).toHaveBeenCalledWith(expect.objectContaining({ content: [expect.objectContaining({
      text: `Your background jobs ran 30 minutes after your turn ended and were killed: ${job} (pnpm test).` })] }))
    // Stopping its subagent would wake it with the end, in the Assignment it was just reported waiting in.
    expect(h.subagents.live(child)).toBe(true)
    expect(h.relays(h.runtime.masterId).at(-1)).toMatchObject({ kind: 'worker_report', state: 'waiting' })
  })
  it('says a worker\'s subagents still run when only they ran 30 minutes after the turn ended', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    h.subagents.spawn(one.sessionId)
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try { idle(one.sessionId); await minutes(30) } finally { vi.useRealTimers() }
    await vi.waitFor(() => expect(latestAssignment(h.runtime.store.tickets.get(one.ticket.id)!)?.report).toMatchObject({ state: 'waiting',
      summary: 'Subagents still ran 30 minutes after the worker\'s turn ended.' }))
  })
  it('holds a delivery that reached a worker while a hand-off stopped its subagents until the stop ended', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    const agent = h.agents.get(one.sessionId)!
    h.runtime.engine.bindThread(one.ticket.id, { source: 'github', id: '7' }, true)
    h.subagents.spawn(one.sessionId)
    await h.runTool(one.sessionId, 'orchestrator_report', { state: 'ready', summary: 'PR ready' }); await h.runtime.idle()
    // A person's message is on its way into the worker's Session, held there, as the worker hands off; the release is slow.
    const session = deferred(), drain = deferred(), release = h.subagents.service.drainChildren.getMockImplementation()!
    h.subagents.service.drainChildren.mockImplementationOnce(async (parent, ids) => { await drain.promise; await release(parent, ids) })
    await new Promise(resolve => setTimeout(resolve, 5))
    const held = holdSession(one.sessionId, session.promise)
    h.runtime.receive(feishu('2', '按钮再大一点', { mentions: [], root_id: 'om_1' }))
    await vi.waitFor(() => expect(held()).toBe(true))
    idle(one.sessionId)
    await vi.waitFor(() => expect(h.subagents.service.drainChildren).toHaveBeenCalled())
    session.resolve()
    await new Promise(resolve => setTimeout(resolve, 20))
    drain.resolve()
    // The message reaches the worker after the stop's cancel, which would have dropped it.
    const message = expect.objectContaining({ sessionId: one.sessionId, text: expect.stringContaining('按钮再大一点') })
    await vi.waitFor(() => expect(h.deliveries).toHaveBeenCalledWith(message), { timeout: 5000 })
    const delivered = h.deliveries.mock.calls.findIndex(([call]) => call.sessionId === one.sessionId && call.text.includes('按钮再大一点'))
    expect(h.deliveries.mock.invocationCallOrder[delivered]).toBeGreaterThan(agent.cancel.mock.invocationCallOrder.at(-1)!)
  })
  it('keeps an Input a restart found handed over to a settled worker, and delivers a waiting one once its subagents stopped', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    const agent = h.agents.get(one.sessionId)!, ticket = () => h.runtime.store.tickets.get(one.ticket.id)!
    idle(one.sessionId)
    await vi.waitFor(() => expect(latestAssignment(ticket())?.report?.state).toBe('waiting'))
    // A subagent still runs, whose release is slow; one Input waits in the Session's inbox, another in the ticket.
    h.subagents.spawn(one.sessionId)
    const gate = deferred(), drain = h.subagents.service.drainChildren.getMockImplementation()!
    h.subagents.service.drainChildren.mockImplementationOnce(async (parent, ids) => { await gate.promise; await drain(parent, ids) })
    agent.inbox.nextStep.push({ id: 'taken-later', role: 'user', content: [{ type: 'text', text: 'Handed over' }], source: { kind: 'user' } } as never)
    const stored = ticket()
    stored.inputs.push({ id: 'input-late', kind: 'text', text: 'One more thing', at: new Date().toISOString() })
    stored.undelivered.push('input-late')
    h.runtime.store.tickets.save(stored)
    // The delivery waits for the release, so the effects are not idle until it ends.
    h.runtime.executor.resume()
    await new Promise(resolve => setTimeout(resolve, 20))
    const late = expect.objectContaining({ sessionId: one.sessionId, text: expect.stringContaining('One more thing') })
    expect(h.deliveries).not.toHaveBeenCalledWith(late)
    const reports = () => h.relays(h.runtime.masterId).filter(item => item.kind === 'worker_report').length
    const reported = reports()
    gate.resolve()
    await vi.waitFor(() => expect(h.deliveries).toHaveBeenCalledWith(late))
    expect(agent.cancel).not.toHaveBeenCalledWith({ kind: 'user' }, { keepInbox: false })
    expect(agent.inbox.nextStep.map(message => message.id)).toContain('taken-later')
    // The turn the subagent's end woke and the release cancelled reports nothing.
    await h.runtime.idle()
    expect(reports()).toBe(reported)
  })
  it('collects the end of a job left to a person until dsh-superagent stopped its workers', async () => {
    const one = await handsOff({ state: 'blocked', summary: 'Which color?' })
    const agent = h.agents.get(one.sessionId)!
    const server = h.jobs.run(one.sessionId, 'pnpm dev')
    await h.runTool(one.sessionId, 'orchestrator_report', { state: 'blocked', summary: 'Which size?' }); await h.runtime.idle()
    idle(one.sessionId)
    await vi.waitFor(() => expect(h.jobs.service.wait).toHaveBeenCalledWith(server, expect.any(Number), one.sessionId, expect.anything()))
    // The server ends while the host stops, after it cancelled the workers.
    const cancel = agent.cancel.getMockImplementation()!
    agent.cancel.mockImplementationOnce((...args: unknown[]) => { h.jobs.end(server); return cancel(...args as [unknown, { keepInbox?: boolean }]) })
    const woken = agent.followup.mock.calls.length
    await h.stop()
    expect(agent.followup.mock.calls.length).toBe(woken)
    expect(agent.status).toBe('idle')
  })
  it('stops every worker\'s jobs and subagents when dsh-superagent stops, before it releases their tool limits', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    const job = h.jobs.run(one.sessionId), child = h.subagents.spawn(one.sessionId)
    await h.stop()
    expect(h.jobs.service.kill).toHaveBeenCalledWith(job, one.sessionId, expect.any(String))
    expect(h.subagents.live(child)).toBe(false)
  })
  it('cancels no worker for a subagent that ended before, and cancels the turn a release woke also when the release fails', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    const agent = h.agents.get(one.sessionId)!
    h.subagents.settle(h.subagents.spawn(one.sessionId))
    // Its ready report ends the ticket, and it ends its own turn.
    await h.runTool(one.sessionId, 'orchestrator_report', { state: 'ready', summary: 'Done' })
    await h.runtime.idle(); await new Promise(resolve => setTimeout(resolve, 10))
    expect(agent.cancel).not.toHaveBeenCalled()
    // A release that fails after the ends woke the worker still cancels that turn.
    const two = await h.acceptedTicket(feishu('5', '@bot 修二'))
    const other = h.agents.get(two.sessionId)!
    const child = h.subagents.spawn(two.sessionId)
    h.subagents.service.drainChildren.mockImplementationOnce(async () => { h.subagents.settle(child); throw new Error('ACTIVATION_TEARDOWN_FAILED') })
    h.runtime.engine.stopTicket(two.ticket.id)
    await vi.waitFor(() => expect(h.subagents.service.drainChildren).toHaveBeenCalled())
    await vi.waitFor(() => expect(other.cancel.mock.invocationCallOrder.at(-1)).toBeGreaterThan(h.subagents.service.drainChildren.mock.invocationCallOrder.at(-1)!))
  })
  it('stops the jobs and the turn of a worker a restart in this process left running, before its Assignment starts again', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    const job = h.jobs.run(one.sessionId)
    h.runtime.executor.resume()
    expect(h.agents.get(one.sessionId)!.cancel).toHaveBeenCalledWith({ kind: 'user' }, { keepInbox: true })
    await vi.waitFor(() => expect(h.jobs.service.kill).toHaveBeenCalledWith(job, one.sessionId, expect.any(String)))
    expect(h.runtime.store.tickets.get(one.ticket.id)!.inputs).toEqual([expect.objectContaining({ kind: 'text', text: expect.stringContaining('host restarted') })])
  })
  it('stops a ticket whose worker Session was never created without a health error, and goes on past a failing kill', async () => {
    const settings = h.runtime.store.settings()
    h.runtime.store.saveSettings({ ...settings, executor: { ...settings.executor, maxWorkers: 1 } })
    await h.acceptedTicket(feishu('1', '@bot 修一'))
    const queued = await h.acceptedTicket(feishu('5', '@bot 修二'))
    expect(h.agents.has(queued.sessionId)).toBe(false)
    // DSH cannot list the children of a Session that does not exist.
    const list = h.subagents.service.listChildren.getMockImplementation()!
    h.subagents.service.listChildren.mockImplementation(async (id: string) => {
      if (id === queued.sessionId) throw new Error('SESSION_QUERY_SESSION_NOT_FOUND')
      return list(id)
    })
    h.runtime.engine.stopTicket(queued.ticket.id); await h.runtime.idle()
    await new Promise(resolve => setTimeout(resolve, 10))
    expect(h.runtime.health.worker?.state).not.toBe('error')
    // A kill that throws leaves the other jobs to be killed.
    const one = h.runtime.store.tickets.list().find(ticket => ticket.id !== queued.ticket.id)!
    const sessionId = `worker-${one.id}`
    const [first, second] = [h.jobs.run(sessionId), h.jobs.run(sessionId)]
    h.jobs.service.kill.mockImplementationOnce(() => { throw new Error('No such process') })
    h.runtime.engine.stopTicket(one.id)
    await vi.waitFor(() => expect(h.jobs.service.kill).toHaveBeenCalledWith(second, sessionId, expect.any(String)))
    expect(h.jobs.service.kill).toHaveBeenCalledWith(first, sessionId, expect.any(String))
  })
})
describe('what a worker read', () => {
  const later = () => new Promise(resolve => setTimeout(resolve, 5))
  /** A ticket its worker completed, and a person's thanks on its thread, which resumes it once received. */
  async function completed() {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    await h.runTool(one.sessionId, 'orchestrator_report', { state: 'ready', summary: 'Done' }); await h.runtime.idle()
    idle(one.sessionId)
    await later()
    return { one, thanks: feishu('2', '@bot 谢谢', { root_id: 'om_1' }), ticket: () => h.runtime.store.tickets.get(one.ticket.id)! }
  }
  /** Deliveries to a Session of a message with `text` fail until the returned function lets them through. */
  function failing(sessionId: string, text: string) {
    const agent = h.agents.get(sessionId)!, steer = agent.steer.getMockImplementation()!
    let fail = true
    agent.steer.mockImplementation(message => {
      if (fail && message.content.some(block => block.type === 'text' && block.text.includes(text))) throw new Error('Session busy')
      steer(message)
    })
    return () => { fail = false }
  }
  /** Runs `then` after the delivery retry, two seconds on; the clock moves on only by `vi.setSystemTime`. */
  async function retried(then: () => Promise<void>) {
    vi.useFakeTimers({ toFake: ['Date'], now: Date.now() + 2000 })
    try { await h.runtime.pump(); await h.runtime.idle(); await then(); await h.runtime.pump(); await h.runtime.idle() }
    finally { vi.useRealTimers() }
  }
  it('sends to Eval a message that woke a ticket and that a retry delivered after a progress report, at a dropped report', async () => {
    const { one, thanks, ticket } = await completed()
    const pass = failing(one.sessionId, '谢谢')
    h.runtime.receive(thanks); await h.runtime.idle()
    expect(ticket().delivery).toBeDefined()
    await h.runTool(one.sessionId, 'orchestrator_report', { state: 'progress', summary: 'Looking' })
    pass()
    // The retry steers the message in while the worker writes that nothing is left, and no step takes it before.
    await retried(async () => {
      expect(ticket().undelivered).toEqual([])
      await h.runTool(one.sessionId, 'orchestrator_report', { state: 'dropped', summary: 'Nothing to do' })
    })
    expect(h.candidates()).toContain(thanks.id)
  })
  it('counts a delivered message as read only once its step took it into the Session, not when a cut-off step claimed it', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    const more = feishu('2', '再改一下', { mentions: [], root_id: 'om_1' })
    h.runtime.receive(more); await h.runtime.idle()
    const input = () => h.runtime.store.tickets.get(one.ticket.id)!.inputs.find(item => item.kind === 'trigger' && item.triggerId === more.id) as
      { readAt?: string | null }
    await vi.waitFor(() => expect(input().readAt).toBe(null))
    // A step claims it and is cut off before the Session took it, as a cancel in its pre-step does, which drops the message.
    h.claim(one.sessionId); await h.runtime.idle(); await later()
    expect(input().readAt).toBe(null)
  })
  it('keeps a note waiting in a worker\'s Session across an in-process restart, for the next Assignment\'s first step', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    h.runtime.engine.note(one.ticket.id, 'Ticket B changes the same page.'); await h.runtime.idle()
    const copies = () => h.deliveries.mock.calls.filter(([call]) => call.sessionId === one.sessionId && call.text.includes('Ticket B changes the same page.'))
    await vi.waitFor(() => expect(copies()).toHaveLength(1))
    const claimed: string[] = []
    h.ctx.on('agent/inbox/claimed', ({ message }) => { claimed.push(message.id) })
    // The restart cancels the worker's turn and keeps its inbox, where the note waits.
    h.runtime.executor.resume()
    await vi.waitFor(() => expect(claimed).toContain(copies()[0]![0].id))
    expect(copies()).toHaveLength(1)
  })
  it('delivers once a message a crash left waiting in a worker\'s Session, which the restart puts back for the next Assignment', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    h.runtime.receive(feishu('2', '再改一下', { mentions: [], root_id: 'om_1' })); await h.runtime.idle()
    const copies = () => h.deliveries.mock.calls.filter(([call]) => call.sessionId === one.sessionId && call.text.includes('再改一下'))
    await vi.waitFor(() => expect(copies()).toHaveLength(1))
    // The process dies: the worker's agent is not loaded when the restart runs, and its inbox, which holds the message,
    // persists for the launch that loads it.
    const agent = h.agents.get(one.sessionId)!
    h.agents.delete(one.sessionId); agent.status = 'idle'
    h.controller.resolveAgent.mockImplementation(async (id: string) => { if (id === one.sessionId) h.agents.set(id, agent); return h.resolveDefault(id) })
    const waiting: string[][] = [], launch = agent.followup.getMockImplementation()!
    agent.followup.mockImplementation(message => { waiting.push([...agent.inbox.nextTurn, ...agent.inbox.nextStep].map(item => item.id)); launch(message) })
    h.runtime.executor.resume()
    await vi.waitFor(() => expect(copies()).toHaveLength(2))
    // The launch's message found no copy of it waiting, which its step would take beside the copy delivered after.
    expect(waiting[0]).not.toContain(copies()[0]![0].id)
  })
  it('gives the Assignment an in-process restart starts a message a cut-off step had claimed, once', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    h.runtime.receive(feishu('2', '再改一下', { mentions: [], root_id: 'om_1' })); await h.runtime.idle()
    const sent = () => h.deliveries.mock.calls.filter(([call]) => call.sessionId === one.sessionId && call.text.includes('再改一下')).length
    await vi.waitFor(() => expect(sent()).toBe(1))
    // A step claims it and the restart cuts the step off before the Session took it, which drops it.
    h.claim(one.sessionId)
    h.runtime.executor.resume()
    await vi.waitFor(() => expect(sent()).toBe(2))
    await h.runtime.idle(); await later()
    expect(sent()).toBe(2)
  })
  it('counts a message that woke a ticket as read by a later dropped report once a step of its worker took it', async () => {
    const { one, thanks } = await completed()
    // The resumed Assignment's message wakes the worker; its next step takes the note that it resumed and the message.
    h.runtime.receive(thanks); await h.runtime.idle()
    h.step(one.sessionId)
    await later()
    await h.runTool(one.sessionId, 'orchestrator_report', { state: 'dropped', summary: 'Nothing to do' })
    await h.runtime.pump(); await h.runtime.idle()
    expect(h.candidates()).not.toContain(thanks.id)
  })
  it('counts a message a retry delivered to its idle worker as read by the report of the turn it woke', async () => {
    const { one, thanks, ticket } = await completed()
    const pass = failing(one.sessionId, '谢谢')
    h.runtime.receive(thanks); await h.runtime.idle()
    idle(one.sessionId)
    await vi.waitFor(() => expect(latestAssignment(ticket())?.report?.state).toBe('waiting'))
    pass()
    // The retry wakes the worker, whose first step takes the message.
    await retried(async () => {
      expect(h.agents.get(one.sessionId)!.status).toBe('running')
      vi.setSystemTime(Date.now() + 1000)
      await h.runTool(one.sessionId, 'orchestrator_report', { state: 'dropped', summary: 'Nothing to do' })
    })
    expect(h.candidates()).not.toContain(thanks.id)
  })
  it('sends to Eval at a merge a message that reached the worker after its last step, which no step took before its turn ended', async () => {
    const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
    const ticket = () => h.runtime.store.tickets.get(one.ticket.id)!
    h.runtime.engine.bindThread(one.ticket.id, { source: 'github', id: '7' }, true)
    await h.runTool(one.sessionId, 'orchestrator_report', { state: 'ready', summary: 'PR ready' }); await h.runtime.idle()
    // A person's thanks reaches the worker after the step of its report, and its turn ends with no step taking it.
    await later()
    const thanks = feishu('2', '@bot 谢谢', { root_id: 'om_1' })
    h.runtime.receive(thanks); await h.runtime.idle()
    idle(one.sessionId)
    await vi.waitFor(() => expect(latestAssignment(ticket())?.report?.state).toBe('waiting'))
    await later()
    h.runtime.engine.threadClosed({ source: 'github', id: '7' }, 'merged', new Date().toISOString())
    await h.runtime.pump(); await h.runtime.idle()
    expect(ticket().ended).toMatchObject({ outcome: 'merged' })
    expect(h.candidates()).toContain(thanks.id)
  })
})
it('reports nothing for a worker whose turn ends while it waits out the backoff of a passing failure', async () => {
  const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
  const agent = h.agents.get(one.sessionId)!
  const relayed = h.relays(h.runtime.masterId).length
  h.ctx.emit('agent/error', { agent, turn: 1, step: 1, error: Object.assign(new Error('Service Unavailable'), { status: 503 }) } as never)
  agent.status = 'idle'
  h.ctx.emit('agent/status', { agent, status: 'idle' } as never)
  await h.runtime.idle()
  await new Promise(resolve => setTimeout(resolve, 20))
  expect(latestAssignment(h.runtime.store.tickets.get(one.ticket.id)!)?.report).toBeUndefined()
  expect(h.relays(h.runtime.masterId)).toHaveLength(relayed)
})
it('wakes an idle worker for a status request in the slot kept for a person, while every other slot is taken', async () => {
  const settings = h.runtime.store.settings()
  h.runtime.store.saveSettings({ ...settings, executor: { ...settings.executor, maxWorkers: 1 } })
  const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
  // Its worker ended its turn without a report, so it waits.
  h.agents.get(one.sessionId)!.status = 'idle'
  h.ctx.emit('agent/status', { agent: h.agents.get(one.sessionId), status: 'idle' } as never)
  await vi.waitFor(() => expect(latestAssignment(h.runtime.store.tickets.get(one.ticket.id)!)?.report?.state).toBe('waiting'))
  const two = await h.acceptedTicket(feishu('5', '@bot 修二'))
  expect(h.agents.get(two.sessionId)!.status).toBe('running')
  expect(h.runtime.engine.requestStatus(one.ticket.id)).toBe(true); await h.runtime.idle()
  expect(h.runtime.store.tickets.get(one.ticket.id)!.undelivered).toEqual([])
  expect(h.agents.get(one.sessionId)!.status).toBe('running')
})
it('tells a passing failure of the provider or the network from one that a later try would meet again', () => {
  for (const error of [Object.assign(new Error('x'), { status: 429 }), Object.assign(new Error('x'), { status: 503 }),
    Object.assign(new Error('connect'), { code: 'ECONNRESET' }), new TypeError('fetch failed'), new Error('getaddrinfo EAI_AGAIN api.example.com')]) {
    expect(transient(error)).toBe(true)
  }
  for (const error of [Object.assign(new Error('x'), { status: 400 }), Object.assign(new Error('x'), { status: 401 }), new Error('context too long'), 'LlmError: offline']) {
    expect(transient(error)).toBe(false)
  }
})
it('reports a worker waiting when its turn ends after a person answered its blocked report', async () => {
  const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
  await h.runTool(one.sessionId, 'orchestrator_report', { state: 'blocked', summary: 'Which color?' })
  // The person answers later than the report.
  await new Promise(resolve => setTimeout(resolve, 5))
  h.runtime.receive(feishu('2', '蓝色', { mentions: [], root_id: 'om_1' })); await h.runtime.idle()
  const ticket = () => h.runtime.store.tickets.get(one.ticket.id)!
  expect(waitsForPerson(ticket())).toBe(false)
  h.agents.get(one.sessionId)!.status = 'idle'
  h.ctx.emit('agent/status', { agent: h.agents.get(one.sessionId), status: 'idle' } as never)
  await vi.waitFor(() => expect(latestAssignment(ticket())?.report?.state).toBe('waiting'))
})

it('resumes an ended ticket a person wrote to during a pause once it lifts, under the Policy then', async () => {
  const pass = async () => {
    vi.useFakeTimers({ toFake: ['Date'], now: Date.now() + 6000 })
    try { await h.runtime.pump(); await h.runtime.idle() } finally { vi.useRealTimers() }
  }
  const ended = async (id: string) => {
    const { ticket, sessionId } = await h.acceptedTicket(feishu(id, `@bot 修${id}`, { root_id: `om_${id}` }))
    await h.runTool(sessionId, 'orchestrator_report', { state: 'ready', summary: 'Done.' })
    return ticket.id
  }
  const first = await ended('1'), second = await ended('3')
  const followUp = async (id: string, root: string) => {
    await h.runtime.settings.pause(true, 'panel')
    h.runtime.receive(feishu(id, '再改一下', { mentions: [], root_id: root })); await h.runtime.idle()
  }
  // While processing is paused, the message waits on the ended ticket; the first pass after the pause resumes it.
  await followUp('2', 'om_1')
  expect(h.runtime.store.tickets.get(first)).toMatchObject({ ended: expect.anything(), undelivered: [expect.any(String)] })
  await h.runtime.settings.pause(false, 'panel'); await pass()
  expect(h.runtime.store.tickets.get(first)).toMatchObject({ assignments: [expect.anything(), expect.objectContaining({ state: 'running' })] })
  expect(h.runtime.store.tickets.get(first)).not.toHaveProperty('ended')
  // A Mandate the Policy no longer holds when the pause lifts does not resume: its sender left the list meanwhile.
  await followUp('4', 'om_3')
  const settings = h.runtime.store.settings()
  h.runtime.store.saveSettings({ ...settings, policy: { ...settings.policy, sources: { ...settings.policy.sources, feishu: { ...settings.policy.sources.feishu!, allowed: [] } } } })
  await h.runtime.settings.pause(false, 'panel'); await pass()
  expect(h.runtime.store.tickets.get(second)).toMatchObject({ ended: expect.anything(), undelivered: [] })
})

it('ends a worker\'s turn only when the stop that ended its Assignment commits', async () => {
  const one = await h.acceptedTicket(feishu('1', '@bot 修一'))
  const worker = h.agents.get(one.sessionId)! as unknown as { cancel: ReturnType<typeof vi.fn> }
  expect(() => h.runtime.store.atomic(() => { h.runtime.engine.stopTicket(one.ticket.id); throw new Error('rolled back') })).toThrow('rolled back')
  expect(worker.cancel).not.toHaveBeenCalled()
  expect(h.runtime.store.tickets.get(one.ticket.id)!.ended).toBeUndefined()
  h.runtime.engine.stopTicket(one.ticket.id)
  expect(worker.cancel).toHaveBeenCalledOnce()
})

describe('the Executor\'s parts', () => {
  it('holds one worker slot per ticket that runs or starts, and lets launches take the slots no worker or wake holds', () => {
    const running = ['t1']
    const slots = new WorkerSlots(() => running, () => 3)
    slots.reserve('t2', 'launch')
    slots.reserve('t3', 'wake')
    expect(slots.used()).toBe(3)
    // launches() excludes 'launch' reservations because the launch queue tracks active launches separately.
    expect(slots.launches()).toBe(1)
    expect(() => slots.reserve('t4', 'wake')).toThrow(Later)
    expect(() => slots.reserve('t3', 'wake')).not.toThrow()
    slots.free('t3')
    expect(slots.used()).toBe(2)
    slots.reserve('t4', 'launch')
    expect(slots.used()).toBe(3)
  })
  it('wakes a worker for a person\'s message in the one slot beyond the limit, and ahead of launches once a slot frees up', () => {
    const running = ['t1', 't2', 't3']
    const slots = new WorkerSlots(() => running, () => 3)
    expect(() => slots.reserve('t4', 'launch')).toThrow(Later)
    expect(() => slots.reserve('t4', 'wake')).toThrow(Later)
    slots.reserve('t5', 'person')
    expect(slots.used()).toBe(4)
    expect(slots.launches()).toBeLessThanOrEqual(0)
    // No second person's wake fits beyond the limit; once a worker ends, it does, while a launch still waits.
    expect(() => slots.reserve('t6', 'person')).toThrow(Later)
    running.splice(0, 1)
    expect(() => slots.reserve('t7', 'launch')).toThrow(Later)
    slots.reserve('t6', 'person')
    expect(slots.used()).toBe(4)
  })
  it('words an assignment, and the limits an inferred mandate sets, from the ticket alone', () => {
    const settings = SettingsSchema.parse({ policy: { rules: [{ id: 'copy', name: 'Copy fixes', enabled: true,
      instruction: 'Fix typos only.' }] } })
    const ticket = { id: 'ticket-0123456789abcdef', origin: { triggerId: 'tr1', triggerIds: [] },
      mandate: { strength: 'inferred', policyVersion: 'v1', basis: { rules: ['copy'] }, actor: { source: 'github', id: 'alice' },
        scope: '' } } as unknown as Ticket
    const execution = ticketExecution(ticket, { kind: 'accept', title: 'Fix', scope: 'the typo', reason: 'r', name: 'fix-typo' } as never,
      settings, '/state')
    expect(execution).toEqual(expect.objectContaining({ name: 'fix-typo-ticket-01234' }))
    expect(execution).not.toHaveProperty('session')
    // The source Trigger goes with the assignment, so the text does not point at it.
    expect(execution.assignment).toContain('Scope: the typo.')
    expect(execution.assignment).not.toContain('trigger/tr1')
    expect(ticketExecution({ ...ticket, mandate: { ...ticket.mandate, strength: 'explicit' } } as Ticket,
      { kind: 'accept', title: 'Fix', scope: 'Fix', reason: 'r', name: 'fix-login', note: 'the login page' } as never, settings, '/state').assignment)
      .toBe('Routing note (not the source request): the login page')
    // The worker's system prompt holds the limits an inferred Mandate sets, so the assignment does not repeat them.
    expect(execution.assignment).not.toContain(mandateInstructions(ticket.mandate))
    expect(execution.assignment).toContain('- Copy fixes (copy): Fix typos only.')
    expect(mandateInstructions({ strength: 'explicit' })).toBe('')
  })
  it('renders each kind of Input as its worker reads it, inline, and no reopen Input', () => {
    const asked = { id: 'tr1', source: 'feishu', threads: [{ source: 'feishu', id: 'oc:om_1' }], actor: { source: 'feishu', id: 'ou_a' }, human: true,
      at: '2026-09-01T00:00:00Z', text: 'Which page?', meta: {} } as Trigger
    const reply = { ...asked, id: 'tr2', text: 'The login page. '.repeat(50) }
    const card = triggerMessage(reply, { source_url: 'https://x' }, 'see the log', asked)
    expect(card).toEqual({ trigger_id: 'tr2', from: 'ou_a', thread: 'feishu:oc:om_1', at: '2026-09-01T00:00:00Z', text: expect.stringMatching(/^The login page\./),
      chars: reply.text.length, read: 'trigger/tr2', source_url: 'https://x', routing_note: 'see the log', replies_to: { trigger_id: 'tr1', preview: 'Which page?' } })
    expect(card.text).toHaveLength(601)
    expect(triggerMessage(asked, {})).toEqual({ trigger_id: 'tr1', from: 'ou_a', thread: 'feishu:oc:om_1', at: asked.at, text: 'Which page?' })
    expect(JSON.parse(inputMessage({ id: 'i1', kind: 'trigger', triggerId: 'tr2', at: '' }, card)!)).toEqual(card)
    expect(JSON.parse(inputMessage({ id: 'i1', kind: 'trigger', triggerId: 'gone', at: '' })!)).toEqual({ trigger_id: 'gone', read: 'trigger/gone' })
    expect(inputMessage({ id: 'i2', kind: 'text', at: '', text: 'Please also update the docs' })).toBe('Please also update the docs')
    // A Policy change says what it means for the ticket, without version hashes.
    const changed = inputMessage({ id: 'i3', kind: 'policy-changed', at: '', from: 'v1', to: 'v2', effect: { requesterAllowed: false,
      requester: { source: 'github', id: 'ci-bot' },
      rules: [{ id: 'copy', name: 'Copy fixes', change: 'changed', instruction: 'Fix typos only.' }, { id: 'visual', name: 'Visual', change: 'disabled' }] } })!
    expect(changed).toContain('Rule Copy fixes (copy), which this ticket was accepted under, changed. Keep the remaining work within it as it reads now: Fix typos only.')
    expect(changed).toContain('Rule Visual (visual), which this ticket was accepted under, no longer applies')
    // The sender is named, a bot as a person.
    expect(changed).toContain('The sender this ticket is for, ci-bot on github, may no longer start work here')
    expect(changed).not.toContain('person')
    expect(changed).not.toContain('v2')
    const mode = inputMessage({ id: 'i6', kind: 'policy-changed', at: '', from: 'v1', to: 'v2', effect: { proactive: false } })!
    expect(mode).toContain('Work inferred from a rule is no longer accepted, as the accept mode is no longer auto')
    expect(mode).not.toContain('sender')
    expect(inputMessage({ id: 'i5', kind: 'resumed', at: '', triggerId: 'tr2' })).not.toContain('tr2')
    expect(inputMessage({ id: 'i4', kind: 'reopen', at: '' } as never)).toBeUndefined()
  })
  it('relays a worker\'s question, result or answer to the main Session, and keeps its progress internal', () => {
    const ticket = { id: 't1', title: 'Fix', updatedAt: '2026-09-01T00:00:00Z', attention: { id: 'a1', question: 'Which color?' }, assignments: [],
      mandate: { strength: 'explicit' }, origin: { triggerId: 'tr1' } } as unknown as Ticket
    expect(reportRelay(ticket, { state: 'progress', summary: 'halfway' })).toBeUndefined()
    expect(reportRelay(ticket, { state: 'blocked', summary: 'need input', question: 'Which color?' }))
      .toMatchObject({ id: 'attention:t1:a1', text: expect.stringContaining('"kind":"worker_attention"') })
    const ready = reportRelay({ ...ticket, attention: undefined } as unknown as Ticket, { state: 'ready', summary: 'Done',
      answers: 'tr9' })!
    expect(ready.id).toMatch(/^report:/)
    expect(JSON.parse(ready.text)).toMatchObject({ kind: 'worker_report', ticket: { ticket_id: 't1' }, trigger_id: 'tr1', state: 'ready', answer_to: 'tr9', summary: 'Done' })
  })
})
