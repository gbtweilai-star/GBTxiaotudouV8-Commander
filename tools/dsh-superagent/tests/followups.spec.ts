/** Follow-up routing: human messages on subscribed threads go directly to the ticket worker and notify the main session without starting an Eval. */
import { afterEach, expect, it, vi } from 'vitest'
import { CHAT, feishu, startRuntime, type Host } from './fixtures/host.ts'
import { repliedTo } from '../src/app/links.ts'
import { inputMessage } from '../src/executor/dsh.ts'

let h: Host | undefined
afterEach(async () => { await h?.stop(); h = undefined })
const THREAD = `feishu:${CHAT}:om_1`
const followup = (id: string, text: string, overrides: Record<string, unknown> = {}) => feishu(id, text, { mentions: [], root_id: 'om_1',
  ...overrides })
const notices = (host: Host) => host.relays(host.runtime.masterId).filter(item => item.kind === 'follow_up')

it('delivers a follow-up to the worker and tells the main Session with a card, without an Eval', async () => {
  h = await startRuntime()
  const { ticket, sessionId } = await h.acceptedTicket(feishu('1', '@bot 修一下回归'))
  h.deliveries.mockClear()
  const message = followup('2', '顺便把标题也改了', { parent_id: 'om_1' })
  h.runtime.receive(message)
  await h.runtime.idle()
  expect(h.relays(sessionId)).toEqual([expect.objectContaining({ trigger_id: message.id, text: '顺便把标题也改了' })])
  expect(notices(h)).toEqual([{ kind: 'follow_up', trigger_id: message.id, from: 'ou_alice', thread: THREAD, at: message.at,
    text: '顺便把标题也改了',
    replies_to: { trigger_id: ticket.origin.triggerId, preview: '@bot 修一下回归' },
    delivered_to: [{ ticket_id: ticket.id, title: ticket.title, state: 'working' }],
      note: expect.stringContaining('worker has it and decides') }])
  // No candidate, no Eval, no Decision: nothing waits on the main Session, and the Thread's queue stays free.
  expect(h.candidates()).toEqual([])
  expect(h.runtime.store.threads.get(THREAD)).toMatchObject({ pending: [] })
  expect(h.runtime.store.threads.get(THREAD)).not.toHaveProperty('evaluating')
  expect(h.runtime.store.decisions.byThread(THREAD)).toHaveLength(1)
  expect(h.runtime.store.triggers.disposition(message.id)).toEqual({ fanout: [ticket.id], at: expect.any(String) })
})

it('sends a person\'s message that reaches no ticket, such as only one a person stopped, to Eval as before', async () => {
  h = await startRuntime()
  const { ticket } = await h.acceptedTicket(feishu('1', '@bot 修一下回归'))
  h.runtime.engine.stopTicket(ticket.id)
  h.deliveries.mockClear()
  const message = followup('2', '@bot 换个方式修', { mentions: [{ id: 'ou_bot' }] })
  h.runtime.receive(message)
  await h.runtime.idle()
  expect(notices(h)).toEqual([])
  expect(h.candidates()).toEqual([message.id])
})

it('leaves a delivered follow-up to its ticket\'s worker: the main Session may stop the ticket on it, and route it only once handed back',
  async () => {
  h = await startRuntime()
  const { ticket, sessionId } = await h.acceptedTicket(feishu('1', '@bot 修一下回归'))
  const other = await h.acceptedTicket(feishu('3', '@bot 另一件事'))
  const settle = async (id: string, text: string, sender?: string) => {
    const message = followup(id, text, sender ? { sender_id: sender } : {})
    h!.runtime.receive(message); await h!.runtime.idle()
    return message.id
  }
  const master = (name: string, args: Record<string, unknown>) => h!.runTool(h!.runtime.masterId, name, args)
  const decides = /its worker decides whether it belongs there/
  // A guest's follow-up stays inferred, so its stop does not stop the work; the main Session cannot route or requeue it.
  const guest = await settle('4', '别做了', 'ou_guest')
  expect(await h!.route({ kind: 'stop', ticket_id: ticket.id, trigger_id: guest })).toMatchObject({ decision: 'ignore' })
  await expect(h!.route({ kind: 'accept', trigger_id: guest, title: 'More', worktree_name: 'more', acknowledgement: 'ok' }))
    .rejects.toThrow(decides)
  await expect(master('orchestrator_trigger_requeue', { trigger_id: guest })).rejects.toThrow(decides)
  // A person may still send it to Eval from the panel.
  expect(await h.api('POST', `triggers/${encodeURIComponent(guest)}/requeue`)).toMatchObject({ status: 200, body: { queued: true } })
  await h.runtime.pump(); await h.runtime.idle()
  expect(h.candidates()).toContain(guest)
  // Alice's follow-ups carry her authority once the worker hands them back: one goes to the other ticket, one becomes new work.
  const attach = await settle('5', '这个其实是另一件事的')
  await expect(h!.route({ kind: 'attach', ticket_id: other.ticket.id, trigger_id: attach })).rejects.toThrow(decides)
  await h.runTool(sessionId, 'orchestrator_trigger_handback', { trigger_id: attach, reason: 'It is about the other request.' })
  expect(await h!.route({ kind: 'attach', ticket_id: other.ticket.id, trigger_id: attach }))
    .toMatchObject({ ticket: expect.objectContaining({ ticket_id: other.ticket.id }) })
  const work = await settle('6', '另外把导出按钮也加上')
  const request = { trigger_id: work, title: '导出按钮', worktree_name: 'export', acknowledgement: '收到，加导出按钮。' }
  await expect(h!.route({ kind: 'accept', ...request })).rejects.toThrow(decides)
  // The attach subscribed the other ticket to this thread, so its worker decides the message too; it is new work once both
  // hand it back.
  await h.runTool(sessionId, 'orchestrator_trigger_handback', { trigger_id: work, reason: 'It asks for an export button.' })
  await expect(h!.route({ kind: 'accept', ...request })).rejects.toThrow(decides)
  await h.runTool(other.sessionId, 'orchestrator_trigger_handback', { trigger_id: work, reason: 'Not this ticket either.' })
  const accepted = await h!.route({ kind: 'accept', ...request })
  expect(h.runtime.store.tickets.get((accepted.ticket as { ticket_id: string }).ticket_id)!.mandate).toMatchObject({ strength: 'explicit' })
  // A stop on a person's request needs no hand-back.
  const stop = await settle('7', '先停一下')
  expect(await h!.route({ kind: 'stop', ticket_id: ticket.id, trigger_id: stop })).toMatchObject({ decision: 'stop' })
  expect(h.runtime.store.tickets.get(ticket.id)!.ended).toMatchObject({ by: 'human', outcome: 'stopped' })
})

/**
 * Count main-session model turns triggered by steers: each steer while idle starts a new turn,
 * whereas all steers arriving while running batch into the next step.
 */
function modelCalls(host: Host) {
  const master = host.agents.get(host.runtime.masterId)!
  const seen: string[] = []
  const steer = master.steer.getMockImplementation() as (message: unknown) => void
  master.steer.mockImplementation((message: unknown) => { seen.push(master.status); steer(message) })
  return () => seen.filter(status => status === 'idle').length + (seen.includes('running') ? 1 : 0)
}

it('costs the main Session one model call for a burst of follow-ups while it works, and two while it idles', async () => {
  for (const busy of [true, false]) {
    h = await startRuntime()
    await h.acceptedTicket(feishu('1', '@bot 修一下回归'))
    const master = h.agents.get(h.runtime.masterId)!
    master.status = busy ? 'running' : 'idle'
    h.deliveries.mockClear()
    const calls = modelCalls(h)
    for (const id of ['2', '3', '4', '5', '6']) h.runtime.receive(followup(id, `第 ${id} 条补充`, { sender_id: 'ou_guest' }))
    await h.runtime.idle()
    expect([notices(h).length, h.candidates().length, calls()]).toEqual([5, 0, busy ? 1 : 2])
    await h.stop(); h = undefined
  }
})

it('keeps a follow-up\'s notice in the effect queue until the main Session takes it, and sends it once', async () => {
  h = await startRuntime()
  await h.acceptedTicket(feishu('1', '@bot 修一下回归'))
  h.deliveries.mockClear()
  h.agents.get(h.runtime.masterId)!.steer.mockImplementationOnce(() => { throw new Error('session gone') })
  const message = followup('2', '补充一点')
  h.runtime.receive(message)
  await h.runtime.idle()
  // The notice is stored with the intake's transaction, keyed by its Trigger, and a duplicate message adds nothing.
  expect(h.runtime.store.db.prepare("SELECT key FROM effect WHERE kind = 'relay'").all()).toEqual([{ key: `followup:${message.id}` }])
  expect(h.runtime.receive(followup('2', '补充一点'))).toBe('duplicate')
  vi.useFakeTimers({ toFake: ['Date'], now: Date.now() + 2000 })
  try { await h.runtime.pump(); await h.runtime.idle() } finally { vi.useRealTimers() }
  expect(notices(h).map(item => item.trigger_id)).toEqual([message.id])
  expect(h.runtime.effects.pending('relay')).toBe(false)
})

it('relays a message a worker handed back as a candidate with the worker\'s reason', async () => {
  h = await startRuntime()
  const { ticket, sessionId } = await h.acceptedTicket(feishu('1', '@bot 修一下回归'))
  const message = followup('2', '另外把导出按钮也加上')
  h.runtime.receive(message)
  await h.runtime.idle()
  expect(await h.runTool(sessionId, 'orchestrator_trigger_handback', { trigger_id: message.id, reason: 'It asks for an export button.' }))
    .toEqual({ trigger_id: message.id, queued: true })
  await h.runtime.pump(); await h.runtime.idle()
  // The candidate tells the main Session; no requeue notice comes before it.
  const injected = h.agents.get(h.runtime.masterId)!.inject.mock.calls.map(([notice]) => JSON.stringify(notice))
  expect(injected.filter(notice => notice.includes('trigger_requeued'))).toEqual([])
  expect(h.relays(h.runtime.masterId).find(item => item.kind === 'candidate'
    && item.trigger_id === message.id)).toMatchObject({ strength: 'explicit',
    handed_back: [{ trigger_id: message.id, ticket_id: ticket.id, reason: 'It asks for an export button.' }] })
  await expect(h.runTool(sessionId, 'orchestrator_trigger_handback', { trigger_id: message.id,
    reason: 'Again' })).rejects.toThrow(/handed that trigger back/)
  // Attaching it back to the ticket that returned it is refused.
  await expect(h.route({ kind: 'attach', ticket_id: ticket.id, trigger_id: message.id }))
    .rejects.toThrow(/handed that trigger back as beyond it/)
})

it('lets a worker follow a related thread for context, which the main Session hears of without waking, and notes a ticket', async () => {
  h = await startRuntime()
  const { ticket, sessionId } = await h.acceptedTicket(feishu('1', '@bot 修一下回归'))
  const master = h.agents.get(h.runtime.masterId)!
  master.inject.mockClear(); h.deliveries.mockClear()
  expect(await h.runTool(sessionId, 'orchestrator_thread_follow', { thread: 'github:7',
    reason: 'The issue it fixes.' })).toEqual({ followed: true, thread: 'github:7' })
  await h.runtime.idle()
  expect(h.runtime.store.threads.get('github:7')).toMatchObject({ subscriptions: [ticket.id], context: [ticket.id] })
  const text = (message: unknown) => (message as { content: { text: string }[] }).content[0]!.text
  const injected = master.inject.mock.calls.map(([message]) => JSON.parse(text(message)) as Record<string, unknown>)
  expect(injected).toEqual([expect.objectContaining({ thread_followed: { ticket_id: ticket.id, thread: 'github:7',
    reason: 'The issue it fixes.' } })])
  expect(h.relays(h.runtime.masterId)).toEqual([])
  await expect(h.runTool(sessionId, 'orchestrator_thread_follow', { thread: 'github', reason: 'x' })).rejects.toThrow(/<source>:<id>/)
  expect(await h.runTool(h.runtime.masterId, 'orchestrator_ticket_note', { ticket_id: ticket.id, text: 'Ticket B renamed the setting.' }))
    .toMatchObject({ reason: 'Noted for the worker' })
  await h.runtime.idle()
  expect(h.deliveries.mock.calls.map(([call]) => call).filter(call => call.sessionId === sessionId).map(call => call.text))
    .toEqual([expect.stringContaining('Note from the orchestrator, for context only: Ticket B renamed the setting.')])
})

it('takes the message a follow-up answers from its Source kind, whichever kind it is', async () => {
  h = await startRuntime()
  const parent = feishu('1', 'the earlier message')
  h.runtime.store.triggers.save(parent)
  const reply = { ...feishu('2', 'a reply'), source: 'other' }
  expect(repliedTo({ store: h.runtime.store, sources: { repliesTo: trigger => trigger.id === reply.id ? parent.id : undefined } },
    reply)).toEqual(parent)
  expect(repliedTo({ store: h.runtime.store, sources: { repliesTo: () => undefined } }, reply)).toBeUndefined()
  expect(repliedTo(h.runtime, followup('3', 'yes', { parent_id: 'om_1' }))).toEqual(parent)
})

it('tells the main Session of a follow-up to an ended ticket once the ticket resumes, and not when it cannot', async () => {
  h = await startRuntime()
  const { ticket, sessionId } = await h.acceptedTicket(feishu('1', '@bot 修一下回归'))
  await h.runTool(sessionId, 'orchestrator_report', { state: 'ready', summary: 'Done' })
  expect(h.runtime.store.tickets.get(ticket.id)!.ended).toBeDefined()
  // While processing is paused the message waits for the ticket, which has not resumed: the main Session hears nothing yet.
  await h.runtime.settings.pause(true, 'panel')
  h.deliveries.mockClear()
  const message = followup('2', '再改一下标题')
  h.runtime.receive(message); await h.runtime.idle()
  expect(notices(h)).toEqual([])
  await h.runtime.settings.pause(false, 'panel')
  await h.runtime.pump(); await h.runtime.idle()
  expect(h.runtime.store.tickets.get(ticket.id)!.ended).toBeUndefined()
  expect(notices(h)).toEqual([expect.objectContaining({ trigger_id: message.id, delivered_to: [expect.objectContaining({ ticket_id: ticket.id })] })])
})

it('tells the main Session nothing of a message it attached to an ended ticket, which resumes for it', async () => {
  h = await startRuntime()
  const { ticket, sessionId } = await h.acceptedTicket(feishu('1', '@bot 修一下回归'))
  await h.runTool(sessionId, 'orchestrator_report', { state: 'dropped', summary: 'nothing to do' })
  const request = feishu('40', '@bot 上次那个改动还要改一下', { root_id: undefined })
  h.runtime.receive(request); await h.runtime.idle()
  await h.route({ kind: 'attach', ticket_id: ticket.id, trigger_id: request.id })
  await h.runtime.idle()
  expect(h.runtime.store.tickets.get(ticket.id)!.ended).toBeUndefined()
  expect(notices(h)).toEqual([])
})

it('tells the main Session of a follow-up an earlier version queued for Eval, when the queue lets it go', async () => {
  h = await startRuntime()
  const { ticket } = await h.acceptedTicket(feishu('1', '@bot 修一下回归'))
  const message = followup('2', '顺便看看日志')
  h.deliveries.mockClear()
  // An earlier version delivered the follow-up to the ticket, queued it for Eval as well, and told the main Session nothing.
  h.runtime.store.atomic(() => {
    h!.runtime.store.triggers.save(message)
    h!.runtime.store.triggers.saveDisposition(message.id, { fanout: [ticket.id], at: message.at })
    h!.runtime.store.threads.save({ ...h!.runtime.store.threads.get(THREAD)!, pending: [message.id] })
  })
  await h.runtime.pump(); await h.runtime.idle()
  expect(h.runtime.store.threads.get(THREAD)).toMatchObject({ pending: [] })
  expect(notices(h)).toEqual([expect.objectContaining({ trigger_id: message.id, delivered_to: [expect.objectContaining({ ticket_id: ticket.id })] })])
})

it('sends a request on a thread a worker follows only for context to Eval, and marks the worker\'s copy as context', async () => {
  h = await startRuntime()
  const { ticket, sessionId } = await h.acceptedTicket(feishu('1', '@bot 修一下回归'))
  await h.runTool(sessionId, 'orchestrator_thread_follow', { thread: `feishu:${CHAT}:om_9`, reason: 'The same page.' })
  h.deliveries.mockClear()
  const request = feishu('10', '@bot 把这里的按钮也改了', { root_id: 'om_9' })
  h.runtime.receive(request)
  await h.runtime.idle()
  // It is nobody's follow-up: the main Session assesses it, and the worker reads it as context.
  expect(h.candidates()).toEqual([request.id])
  expect(notices(h)).toEqual([])
  expect(h.runtime.store.triggers.disposition(request.id)).toMatchObject({ fanout: [ticket.id], context: [ticket.id] })
  expect(h.relays(sessionId)).toEqual([expect.objectContaining({ trigger_id: request.id, context: true })])
})

it('shows a candidate\'s message as its workers would read it, with the message it answers', async () => {
  h = await startRuntime()
  const { ticket, sessionId } = await h.acceptedTicket(feishu('1', '@bot 修一下回归'))
  const long = `另外，${'导出按钮的文案也需要改。'.repeat(60)}`
  const reply = followup('2', long, { parent_id: 'om_1' })
  h.runtime.receive(reply); await h.runtime.idle()
  await h.runTool(sessionId, 'orchestrator_trigger_handback', { trigger_id: reply.id, reason: 'Another change.' })
  await h.runtime.pump(); await h.runtime.idle()
  const card = h.relays(h.runtime.masterId).find(item => item.kind === 'candidate' && item.trigger_id === reply.id)!
  expect(card).toMatchObject({ from: 'ou_alice', text: long.slice(0, 600) + '…', chars: long.length, read: `trigger/${reply.id}`,
    replies_to: { trigger_id: ticket.origin.triggerId, preview: '@bot 修一下回归' } })
  expect(card).not.toHaveProperty('triggers')
})

it('keeps a listed member\'s request on a ticket\'s thread to that ticket, so it is not done twice', async () => {
  h = await startRuntime()
  const { ticket, sessionId } = await h.acceptedTicket(feishu('1', '@bot 修一下设置页保存按钮的文案'))
  h.deliveries.mockClear()
  // The benchmark's case: an addressed request from a listed member on the ticket's own thread.
  const request = followup('2', '@bot [W1-a] 概览页的保存按钮也按同样方式改一下', { mentions: [{ id: 'ou_bot' }] })
  h.runtime.receive(request); await h.runtime.idle()
  // The worker has it and decides; the main Session hears of it and cannot open a second ticket for it.
  expect(h.relays(sessionId)).toEqual([expect.objectContaining({ trigger_id: request.id })])
  expect(notices(h)).toEqual([expect.objectContaining({ trigger_id: request.id,
    note: expect.stringContaining('orchestrator_route kind stop') })])
  await expect(h.route({ kind: 'accept', trigger_id: request.id, title: '概览页按钮',
    worktree_name: 'overview-button', acknowledgement: '收到。' })).rejects.toThrow(/its worker decides whether it belongs there/)
  // The worker takes it as within its ticket and says so.
  expect(await h.runTool(sessionId, 'orchestrator_ack', { trigger_id: request.id, text: '收到：概览页的保存按钮也一起改。' }))
    .toMatchObject({ trigger_id: request.id })
  expect(h.runtime.store.tickets.list().map(item => item.id)).toEqual([ticket.id])
  expect(h.candidates()).toEqual([])
})

it('leaves a follow-up to its ticket\'s worker after the main Session drops the subscriptions of its thread', async () => {
  h = await startRuntime()
  const { ticket } = await h.acceptedTicket(feishu('1', '@bot 修一下回归'))
  const request = followup('2', '@bot 另外把导出按钮也加上', { mentions: [{ id: 'ou_bot' }] })
  h.runtime.receive(request); await h.runtime.idle()
  const master = (name: string, args: Record<string, unknown>) => h!.runTool(h!.runtime.masterId, name, args)
  expect(await master('orchestrator_thread_unsubscribe', { thread: THREAD })).toEqual({ removed: true, thread: THREAD })
  // The worker has the message and still decides it, so the main Session cannot open a second ticket for it.
  await expect(h!.route({ kind: 'accept', trigger_id: request.id, title: '导出按钮', worktree_name: 'export',
    acknowledgement: '收到，加导出按钮。' })).rejects.toThrow(/its worker decides whether it belongs there/)
  expect(h.runtime.store.tickets.list().map(item => item.id)).toEqual([ticket.id])
})

it('tells a worker it may hand back a message beyond its ticket or for another one, also when the message resumed it', async () => {
  expect(inputMessage({ id: 'r', kind: 'resumed', triggerId: 't', at: '' })).toContain('hand it back with orchestrator_trigger_handback')
  h = await startRuntime()
  const { sessionId } = await h.acceptedTicket(feishu('1', '@bot 修一下回归'))
  expect((h.tools.get(sessionId)!.get('orchestrator_trigger_handback') as unknown as { description: string }).description)
    .toContain('beyond this ticket or for another one')
})
