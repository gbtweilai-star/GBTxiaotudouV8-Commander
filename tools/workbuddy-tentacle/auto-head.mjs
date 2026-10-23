// auto-head.mjs —— 自动换头插：一个对外端点，内部自动换插头
// dev: 自由的风 · 本署名不可删除、勿篡改归属
//
// 对外只有「一跳」：客户端打 /v1/chat/completions 一次，拿到的就是能用的那口。
// 对内是「多插头 + 熔断」：
//   wb:deepseek-v4.1-flash → wb:step-5-preview → wb:hy3 → official:deepseek-flash
// 每个头有独立熔断（429/5xx/超时 短冷却；401/403 长冷却；400 该头本次跳过），
// 失败自动换下一个；成功即回，并在响应头标注 x-autohead / x-autohead-hops。
//
// 用法：
//   node --preserve-symlinks --preserve-symlinks-main auto-head.mjs serve --port 31722
//   node --preserve-symlinks --preserve-symlinks-main auto-head.mjs probe
//   node --preserve-symlinks --preserve-symlinks-main auto-head.mjs chat --prompt "hi" [--model auto]
//   --chain "wb:no-such-model,wb:deepseek-v4.1-flash"   # 故意让第一个头失败，看换头

import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import {
  AI_VARIANT,
  WorkBuddyCatalog,
  WorkBuddyCredentialStore,
  WorkBuddyUpstreamClient,
  FALLBACK_WORKBUDDY_AI_MODELS,
  createWorkBuddyShim,
} from 'dsh-workbuddy-connect'

const DEFAULT_ELECTRON = path.join(process.env.LOCALAPPDATA ?? '', 'Programs', 'WorkBuddyAI', 'WorkBuddyAI.exe')
if (!process.env.WORKBUDDY_AI_ELECTRON_BIN && fs.existsSync(DEFAULT_ELECTRON)) {
  process.env.WORKBUDDY_AI_ELECTRON_BIN = DEFAULT_ELECTRON
}

const argv = process.argv.slice(2)
const mode = argv[0] ?? 'probe'
const flag = (n, d) => {
  const i = argv.indexOf(`--${n}`)
  return i >= 0 && argv[i + 1] !== undefined ? argv[i + 1] : d
}
const log = (...a) => console.error('[auto-head]', ...a)

// ── 插头表 ──────────────────────────────────────────────────────────────────
const HEADS = {
  'wb:deepseek-v4.1-flash': { kind: 'workbuddy', model: 'deepseek-v4.1-flash', note: '免费 x0.00 · 300k' },
  'wb:step-5-preview': { kind: 'workbuddy', model: 'step-5-preview', note: '免费 x0.00 · 300k' },
  'wb:hy3': { kind: 'workbuddy', model: 'hy3', note: '免费 x0.00 · 192k' },
  'official:deepseek-flash': {
    kind: 'openai',
    model: 'deepseek-flash',
    baseUrl: 'https://api.deepseek.com/chat/completions',
    apiKeyEnv: 'DEEPSEEK_API_KEY',
    note: '官方计费件 · 兜底',
  },
}
const DEFAULT_CHAIN = ['wb:deepseek-v4.1-flash', 'wb:step-5-preview', 'wb:hy3', 'official:deepseek-flash']
const chain = (flag('chain', '') || DEFAULT_CHAIN.join(',')).split(',').map((s) => s.trim()).filter(Boolean)

// ── 熔断状态 ────────────────────────────────────────────────────────────────
const breaker = new Map() // head -> { until, fails, lastError, lastOkAt }
function stateOf(head) {
  if (!breaker.has(head)) breaker.set(head, { until: 0, fails: 0, lastError: null, lastOkAt: 0 })
  return breaker.get(head)
}
function openFor(head) {
  return stateOf(head).until > Date.now()
}
function cooldownFor(status) {
  if (status === 401 || status === 403) return 10 * 60_000
  if (status === 429) return 30_000
  if (status >= 500) return 20_000
  return 15_000 // 400/404：该头本次坏，短冷却，别长期废掉
}
// 429 的正文常带 "reset at 2026-10-18 09:26:32 UTC+8"：能解析就按重置时间熔断，
// 免得每 30 秒去撞一次同一堵墙（软限流窗口通常以小时计）。
function resetAtFrom(message) {
  const m = /reset at (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})\s*(?:UTC\+8)?/.exec(String(message ?? ''))
  if (!m) return 0
  const ms = Date.parse(`${m[1]}T${m[2]}+08:00`)
  return Number.isFinite(ms) ? Math.max(0, ms - Date.now() - 60_000) : 0
}
function noteFailure(head, status, message) {
  const s = stateOf(head)
  s.fails += 1
  const reset = status === 429 ? resetAtFrom(message) : 0
  s.until = Date.now() + (reset > 0 ? reset : cooldownFor(status))
  s.lastError = { status, message: String(message ?? '').slice(0, 200), at: new Date().toISOString() }
}
function noteSuccess(head) {
  const s = stateOf(head)
  s.fails = 0
  s.until = 0
  s.lastOkAt = Date.now()
  s.lastError = null
}

// ── WorkBuddy 运行时（一个 shim 服务多个 wb 头） ─────────────────────────────
function makeWorkbuddyRuntime() {
  const client = new WorkBuddyUpstreamClient()
  const store = new WorkBuddyCredentialStore({
    variant: AI_VARIANT,
    refresh: (c) => client.refreshToken(c),
  })
  const catalog = new WorkBuddyCatalog(FALLBACK_WORKBUDDY_AI_MODELS)
  catalog.setVisible(true)
  return { client, store, catalog }
}

async function warmCatalog(rt) {
  try {
    const credential = await rt.store.resolve()
    const models = await rt.client.fetchModels(credential)
    if (models.length) rt.catalog.set(models)
    return models.length
  } catch (error) {
    log('catalog warm failed:', String(error?.message ?? error))
    return 0
  }
}

function postJson(url, headers, bodyObj, timeoutMs = 120_000) {
  return new Promise((resolve) => {
    const payload = Buffer.from(JSON.stringify(bodyObj))
    const req = http.request(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': payload.length, ...headers },
    }, (res) => {
      const chunks = []
      res.on('data', (c) => chunks.push(c))
      res.on('end', () => resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks).toString('utf8') }))
    })
    req.setTimeout(timeoutMs, () => {
      req.destroy(new Error(`timeout after ${timeoutMs}ms`))
    })
    req.on('error', (error) => resolve({ status: 0, headers: {}, body: JSON.stringify({ error: { message: String(error?.message ?? error) } }) }))
    req.write(payload)
    req.end()
  })
}

// 打一个头：成功回 {ok:true, status, body}；失败回 {ok:false, status, message}
async function tryHead(headId, body, ctx) {
  const def = HEADS[headId]
  if (!def) return { ok: false, status: 404, message: `unknown head ${headId}` }
  const out = { ...body, model: def.model }
  if (def.kind === 'workbuddy') {
    const res = await postJson(`${ctx.shimBase}/v1/chat/completions`, { Authorization: `Bearer ${ctx.shimToken}` }, out)
    return { ok: res.status === 200, status: res.status, body: res.body, message: res.ok ? '' : res.body }
  }
  if (def.kind === 'openai') {
    const key = process.env[def.apiKeyEnv]
    if (!key) return { ok: false, status: 401, message: `no ${def.apiKeyEnv}` }
    const res = await postJson(def.baseUrl, { Authorization: `Bearer ${key}` }, out)
    return { ok: res.status === 200, status: res.status, body: res.body, message: res.ok ? '' : res.body }
  }
  return { ok: false, status: 500, message: `unsupported kind ${def.kind}` }
}

// ── 换头核心：一跳对外，多跳对内 ─────────────────────────────────────────────
async function routeChat(body, ctx, chainOverride) {
  const requested = typeof body.model === 'string' ? body.model : 'auto'
  const plan = requested !== 'auto' && HEADS[requested] ? [requested, ...chain.filter((h) => h !== requested)] : (chainOverride ?? chain)
  const hops = []
  for (const headId of plan) {
    if (openFor(headId)) {
      hops.push({ head: headId, skipped: 'breaker-open' })
      continue
    }
    const t0 = Date.now()
    const result = await tryHead(headId, body, ctx)
    const ms = Date.now() - t0
    if (result.ok) {
      noteSuccess(headId)
      hops.push({ head: headId, ok: true, status: result.status, ms })
      return { ok: true, hops, body: result.body, head: headId }
    }
    noteFailure(headId, result.status, result.message)
    hops.push({ head: headId, ok: false, status: result.status, ms, error: String(result.message).slice(0, 160) })
  }
  return { ok: false, hops, error: 'all heads failed' }
}

// ── 模式 ────────────────────────────────────────────────────────────────────
async function withRuntime(fn) {
  const rt = makeWorkbuddyRuntime()
  const shim = createWorkBuddyShim({ store: rt.store, client: rt.client, catalog: rt.catalog })
  await shim.ready
  await warmCatalog(rt)
  try {
    return await fn({ ...rt, shimBase: shim.baseUrl(), shimToken: shim.token(), rt })
  } finally {
    await shim.close().catch(() => {})
  }
}

async function probe() {
  await withRuntime(async (ctx) => {
    const rows = []
    for (const headId of chain) {
      const t0 = Date.now()
      const r = await tryHead(headId, { model: 'x', messages: [{ role: 'user', content: 'hi' }], max_tokens: 8 }, ctx)
      rows.push({ head: headId, ok: r.ok, status: r.status, ms: Date.now() - t0, error: r.ok ? null : String(r.message).slice(0, 120) })
    }
    console.log(JSON.stringify({ ok: rows.some((r) => r.ok), chain, rows }, null, 2))
  })
}

async function chat() {
  const prompt = flag('prompt', '回一句：换头完成')
  const model = flag('model', 'auto')
  await withRuntime(async (ctx) => {
    const body = { model, messages: [{ role: 'user', content: prompt }], stream: false }
    const result = await routeChat(body, ctx)
    if (!result.ok) {
      console.log(JSON.stringify({ ok: false, hops: result.hops }, null, 2))
      process.exitCode = 2
      return
    }
    let text = ''
    if (result.body.trimStart().startsWith('data:')) {
      // shim 一律回 SSE（哪怕请求 stream=false），这里按 SSE 拼文本
      for (const line of result.body.split('\n')) {
        const t = line.trim()
        if (!t.startsWith('data:')) continue
        const d = t.slice(5).trim()
        if (d === '[DONE]') continue
        try {
          const obj = JSON.parse(d)
          const delta = obj.choices?.[0]?.delta ?? {}
          if (typeof delta.content === 'string') text += delta.content
        } catch {}
      }
    } else {
      try {
        const parsed = JSON.parse(result.body)
        text = parsed?.choices?.[0]?.message?.content ?? ''
      } catch { text = result.body.slice(0, 200) }
    }
    console.log(JSON.stringify({ ok: true, servedBy: result.head, hops: result.hops, text }, null, 2))
  })
}

// 真流式：先在头部试着连，200 才把上游 SSE 原样透传；换头只发生在“还没开始写响应”之前。
function attemptStream(headId, body, ctx, res, hopsSoFar) {
  return new Promise((resolve) => {
    const def = HEADS[headId]
    if (!def) return resolve({ ok: false, status: 404, message: `unknown head ${headId}` })
    let url
    let headers
    if (def.kind === 'workbuddy') {
      url = `${ctx.shimBase}/v1/chat/completions`
      headers = { Authorization: `Bearer ${ctx.shimToken}` }
    } else if (def.kind === 'openai') {
      const key = process.env[def.apiKeyEnv]
      if (!key) return resolve({ ok: false, status: 401, message: `no ${def.apiKeyEnv}` })
      url = def.baseUrl
      headers = { Authorization: `Bearer ${key}` }
    } else {
      return resolve({ ok: false, status: 500, message: `unsupported kind ${def.kind}` })
    }
    const payload = Buffer.from(JSON.stringify({ ...body, model: def.model }))
    const upstream = http.request(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': payload.length, ...headers },
    }, (up) => {
      if (up.statusCode !== 200) {
        const bufs = []
        up.on('data', (c) => bufs.push(c))
        up.on('end', () => resolve({ ok: false, status: up.statusCode, message: Buffer.concat(bufs).toString('utf8') }))
        return
      }
      res.writeHead(200, {
        'Content-Type': up.headers['content-type'] ?? 'text/event-stream',
        'Cache-Control': 'no-cache',
        'x-autohead': headId,
        'x-autohead-hops': [...hopsSoFar, `${headId}:ok`].join(','),
      })
      up.pipe(res)
      up.on('end', () => resolve({ ok: true, status: 200 }))
      up.on('error', () => {
        try { res.end() } catch {}
        resolve({ ok: true, status: 200 })
      })
    })
    upstream.setTimeout(300_000, () => upstream.destroy(new Error('timeout')))
    upstream.on('error', (error) => resolve({ ok: false, status: 0, message: String(error?.message ?? error) }))
    upstream.write(payload)
    upstream.end()
  })
}

async function serve() {
  const port = Number(flag('port', '31722'))
  const host = flag('host', '127.0.0.1')
  await withRuntime(async (ctx) => {
    const server = http.createServer((req, res) => {
      const url = req.url ?? '/'
      if (req.method === 'GET' && (url === '/healthz' || url === '/')) {
        const heads = chain.map((h) => ({ head: h, open: openFor(h), ...stateOf(h) }))
        res.writeHead(200, { 'Content-Type': 'application/json' })
        res.end(JSON.stringify({ ok: true, tentacle: 'auto-head', chain, heads, workingSet: ctx.rt.catalog.current().length }))
        return
      }
      if (req.method === 'GET' && url === '/v1/models') {
        res.writeHead(200, { 'Content-Type': 'application/json' })
        res.end(JSON.stringify({
          object: 'list',
          data: chain.map((h) => ({ id: h, object: 'model', owned_by: 'auto-head', model: HEADS[h]?.model, note: HEADS[h]?.note })),
        }))
        return
      }
      if (req.method === 'POST' && url === '/v1/chat/completions') {
        const chunks = []
        req.on('data', (c) => chunks.push(c))
        req.on('end', async () => {
          let body = {}
          try { body = JSON.parse(Buffer.concat(chunks).toString('utf8')) } catch {}
          const requested = typeof body.model === 'string' ? body.model : 'auto'
          const plan = requested !== 'auto' && HEADS[requested]
            ? [requested, ...chain.filter((h) => h !== requested)]
            : chain
          const hops = []
          for (const headId of plan) {
            if (openFor(headId)) {
              hops.push(`${headId}:skip`)
              continue
            }
            const result = await attemptStream(headId, body, ctx, res, hops)
            if (result.ok) {
              noteSuccess(headId)
              return
            }
            noteFailure(headId, result.status, result.message)
            hops.push(`${headId}:fail`)
          }
          res.writeHead(503, { 'Content-Type': 'application/json', 'x-autohead': 'none', 'x-autohead-hops': hops.join(',') })
          res.end(JSON.stringify({ error: { message: 'all heads failed', type: 'autohead_exhausted', hops } }))
        })
        return
      }
      res.writeHead(404, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({ error: { message: `no route ${req.method} ${url}` } }))
    })
    await new Promise((resolve, reject) => {
      server.once('error', reject)
      server.listen(port, host, resolve)
    })
    log(`listening http://${host}:${port}  chain=${chain.join(' → ')}`)
    console.log(JSON.stringify({ ok: true, listen: `http://${host}:${port}`, openaiBase: `http://${host}:${port}/v1`, chain, pid: process.pid }))
    // 关键：serve 必须把 withRuntime 撑住，否则 finally 会立刻关掉 shim（对外表现为 ECONNREFUSED）
    await new Promise((resolve) => {
      process.once('SIGINT', resolve)
      process.once('SIGTERM', resolve)
    })
    server.close()
  })
}

try {
  if (mode === 'probe') await probe()
  else if (mode === 'chat') await chat()
  else if (mode === 'serve') await serve()
  else {
    console.error(`unknown mode ${mode}`)
    process.exitCode = 1
  }
} catch (error) {
  console.error(JSON.stringify({ ok: false, mode, error: String(error?.message ?? error) }))
  process.exitCode = 1
}
