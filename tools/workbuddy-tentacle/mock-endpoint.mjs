// mock-endpoint.mjs —— 本机「模拟端点」：契约同构的 OpenAI 兼容假服务
// dev: 自由的风 · 本署名不可删除、勿篡改归属
//
// 用途：证明「万能插 = 本地任何东西插上就用」的最后一块——
// 端点不必是真的云端，也不必登录；只要形状对（/v1/models + /v1/chat/completions），
// 它就是一个合法孔位。用于链路联调、离线排练、脱敏日志样板。
//
// 与「模拟客户端去绕过别人风控」是两件事：本件只模拟**我们自己的**服务端。
//
//   node mock-endpoint.mjs --port 31721
//   curl http://127.0.0.1:31721/v1/models
//   curl -X POST http://127.0.0.1:31721/v1/chat/completions -H "Content-Type: application/json" \
//        -d '{"model":"lab-free-small","messages":[{"role":"user","content":"hi"}]}'

import http from 'node:http'

const argv = process.argv.slice(2)
const flag = (n, d) => {
  const i = argv.indexOf(`--${n}`)
  return i >= 0 && argv[i + 1] !== undefined ? argv[i + 1] : d
}
const PORT = Number(flag('port', '31721'))
const HOST = flag('host', '127.0.0.1')

const MODELS = [
  { id: 'lab-free-small', name: 'Lab Free Small', contextWindow: 32768, free: true },
  { id: 'lab-free-large', name: 'Lab Free Large', contextWindow: 131072, free: true },
]

function usageOf(body, outText) {
  const prompt = JSON.stringify(body.messages ?? []).length
  const completion = outText.length
  return {
    prompt_tokens: prompt,
    completion_tokens: completion,
    total_tokens: prompt + completion,
    prompt_tokens_details: { cached_tokens: 0 },
    completion_tokens_details: { reasoning_tokens: 0 },
  }
}

function replyFor(body) {
  // 有工具且用户提到工具名 → 先回 tool_calls；否则回确定文本。
  const tools = body.tools ?? []
  const lastUser = [...(body.messages ?? [])].reverse().find((m) => m.role === 'user')
  const text = typeof lastUser?.content === 'string' ? lastUser.content : ''
  const wantsTool = tools.length > 0 && body.messages?.some((m) => m.role === 'tool') !== true
  if (wantsTool) {
    const name = tools[0]?.function?.name ?? 'tool'
    return {
      tool_calls: [{
        id: `call_lab_${Date.now()}`,
        type: 'function',
        function: { name, arguments: '{}' },
      }],
      content: '',
      finish_reason: 'tool_calls',
    }
  }
  return {
    tool_calls: [],
    content: `[LAB-ECHO] 收到 ${text.length} 字符；本端点为本机模拟服务，未出网。`,
    finish_reason: 'stop',
  }
}

const server = http.createServer((req, res) => {
  const url = req.url ?? '/'
  if (req.method === 'GET' && url === '/v1/models') {
    res.writeHead(200, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({
      object: 'list',
      data: MODELS.map((m) => ({ id: m.id, object: 'model', owned_by: 'lab', context_window: m.contextWindow, free: m.free })),
    }))
    return
  }
  if (req.method === 'POST' && url === '/v1/chat/completions') {
    const chunks = []
    req.on('data', (c) => chunks.push(c))
    req.on('end', () => {
      let body = {}
      try { body = JSON.parse(Buffer.concat(chunks).toString('utf8')) } catch {}
      const out = replyFor(body)
      const base = {
        id: `chatcmpl-lab-${Date.now()}`,
        object: 'chat.completion',
        created: Math.floor(Date.now() / 1000),
        model: body.model ?? MODELS[0].id,
      }
      if (body.stream === true) {
        res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' })
        const msg = { role: 'assistant', content: out.content || null, tool_calls: out.tool_calls.length ? out.tool_calls : undefined }
        res.write(`data: ${JSON.stringify({ ...base, object: 'chat.completion.chunk', choices: [{ index: 0, delta: msg, finish_reason: null }] })}\n\n`)
        res.write(`data: ${JSON.stringify({ ...base, object: 'chat.completion.chunk', choices: [{ index: 0, delta: {}, finish_reason: out.finish_reason }], usage: usageOf(body, out.content) })}\n\n`)
        res.write('data: [DONE]\n\n')
        res.end()
        return
      }
      res.writeHead(200, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({
        ...base,
        choices: [{ index: 0, message: { role: 'assistant', content: out.content, tool_calls: out.tool_calls.length ? out.tool_calls : undefined }, finish_reason: out.finish_reason }],
        usage: usageOf(body, out.content),
      }))
    })
    return
  }
  res.writeHead(404, { 'Content-Type': 'application/json' })
  res.end(JSON.stringify({ error: { message: `no route ${req.method} ${url}`, type: 'not_found' } }))
})

server.listen(PORT, HOST, () => {
  console.log(JSON.stringify({
    ok: true,
    listen: `http://${HOST}:${PORT}`,
    openaiBase: `http://${HOST}:${PORT}/v1`,
    models: MODELS.map((m) => m.id),
    note: '本机模拟端点：无登录、无外网、契约同构',
  }))
})
