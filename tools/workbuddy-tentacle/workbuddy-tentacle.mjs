// workbuddy-tentacle.mjs —— 从 DSH 侧插进 WorkBuddy 免费通道的一根触手
// dev: 自由的风 · 本署名不可删除、勿篡改归属
//
// 它不是「注册进 DSH 的 provider」，而是一个**进程外的本地桥**：
//   本机 WorkBuddy AI 桌面 App 的登录态 → 插件自带的凭据仓库（含 5.6+ 的 at-rest 解密）
//   → 插件自带的 loopback shim（OpenAI 兼容：/v1/models · /v1/chat/completions · /healthz）
//   → 本进程把它钉在一个稳定端口上，于是任何本地消费者（DSH 自定义 provider / 框架 llm 车道 /
//     我自己的命令行）都能「反向调用」WorkBuddy 的免费模型。
//
// 复用而不重造：凭据、目录、上游协议、SSE 形状全部来自 dsh-workbuddy-connect@0.6.5 的公开导出
// （WorkBuddyCredentialStore / WorkBuddyUpstreamClient / WorkBuddyCatalog / createWorkBuddyShim）。
// 这不复制它的鉴权逻辑，也不碰桌面 App 的私钥；只把「已经能用的那套」接到一个固定端口。
//
// 用法：
//   node --preserve-symlinks --preserve-symlinks-main workbuddy-tentacle.mjs probe
//   node --preserve-symlinks --preserve-symlinks-main workbuddy-tentacle.mjs chat --model deepseek-v4.1-flash --prompt "你好"
//   node --preserve-symlinks --preserve-symlinks-main workbuddy-tentacle.mjs serve --port 31720
//
// 只读口径：probe/chat 不写任何配置文件；serve 只开本地 socket。

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

// ── 0. 环境：插件用 Electron 二进制当 at-rest 密钥助手；没配就按安装路径兜底 ──
const DEFAULT_ELECTRON = path.join(
  process.env.LOCALAPPDATA ?? '',
  'Programs',
  'WorkBuddyAI',
  'WorkBuddyAI.exe',
)
if (!process.env.WORKBUDDY_AI_ELECTRON_BIN && fs.existsSync(DEFAULT_ELECTRON)) {
  process.env.WORKBUDDY_AI_ELECTRON_BIN = DEFAULT_ELECTRON
}

const argv = process.argv.slice(2)
const mode = argv[0] ?? 'probe'
function flag(name, fallback) {
  const i = argv.indexOf(`--${name}`)
  return i >= 0 && argv[i + 1] !== undefined ? argv[i + 1] : fallback
}

const log = (...a) => console.error('[tentacle]', ...a)

// 插件的 installedAppVersion() 只在 darwin 上实现；Windows 下它会退到编译期常量
// （FALLBACK_APP_VERSION），而上游按 User-Agent 里的客户端版本做风控 ⇒ 退化的 UA 会被
// 直接拒成 HTTP 400「请求被拦截，请重新发送」。这里把**本机真实安装版本**（5.8.4 一类的
// 安装清单值）显式喂进聊天身份，绕开 darwin-only 的探测。只影响 UA，不碰鉴权/密钥。
function installedAppVersionHint() {
  const fromEnv = process.env.WORKBUDDY_AI_APP_VERSION?.trim()
  if (fromEnv) return fromEnv
  const manifest = path.join(
    process.env.LOCALAPPDATA ?? '',
    'Programs',
    'WorkBuddyAI',
    'resources',
    'install-manifest.json',
  )
  try {
    const parsed = JSON.parse(fs.readFileSync(manifest, 'utf8'))
    if (typeof parsed.appVersion === 'string' && parsed.appVersion.trim() !== '') return parsed.appVersion.trim()
  } catch {}
  return undefined
}

const APP_VERSION = installedAppVersionHint()

function makeRuntime() {
  const client = new WorkBuddyUpstreamClient(
    APP_VERSION === undefined
      ? {}
      : { resolveChatIdentity: async () => ({ clientVersion: APP_VERSION }) },
  )
  const store = new WorkBuddyCredentialStore({
    variant: AI_VARIANT,
    refresh: (credential) => client.refreshToken(credential),
  })
  const catalog = new WorkBuddyCatalog(FALLBACK_WORKBUDDY_AI_MODELS)
  catalog.setVisible(true)
  return { client, store, catalog }
}

function pickModels(models) {
  return models.map((m) => ({
    id: m.id,
    name: m.name,
    free: m.billing?.free ?? null,
    credits: m.billing?.credits ?? null,
    contextWindow: m.contextWindow ?? m.defaultContextWindow ?? null,
    maxTokens: m.maxTokens ?? null,
  }))
}

async function loadCatalog(runtime) {
  const credential = await runtime.store.resolve()
  const models = await runtime.client.fetchModels(credential)
  if (models.length > 0) runtime.catalog.set(models)
  return { credential, models: runtime.catalog.current() }
}

// ── 1. probe：凭据 + 目录现读 ────────────────────────────────────────────────
async function probe() {
  const runtime = makeRuntime()
  const status = await runtime.store.status()
  const { credential, models } = await loadCatalog(runtime)
  const picked = pickModels(models)
  console.log(JSON.stringify({
    ok: true,
    variant: AI_VARIANT.id,
    region: AI_VARIANT.region,
    signIn: status?.state ?? null,
    domain: credential?.domain ?? status?.domain ?? null,
    accessTokenExpiresAtMs: credential?.expiresAtMs ?? null,
    modelCount: picked.length,
    free: picked.filter((m) => m.free === true).map((m) => m.id),
    paid: picked.filter((m) => m.free === false).map((m) => ({ id: m.id, credits: m.credits })),
    models: picked,
  }, null, 2))
}

// ── 2. chat：一次真调用（走 shim，SSE 收完拼文本） ──────────────────────────
function callShim(baseUrl, token, body) {
  return new Promise((resolve, reject) => {
    const payload = Buffer.from(JSON.stringify(body))
    const req = http.request(`${baseUrl}/v1/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': payload.length,
        Authorization: `Bearer ${token}`,
        Accept: 'text/event-stream',
      },
    }, (res) => {
      const chunks = []
      res.on('data', (c) => chunks.push(c))
      res.on('end', () => resolve({ status: res.statusCode, text: Buffer.concat(chunks).toString('utf8') }))
    })
    req.on('error', reject)
    req.write(payload)
    req.end()
  })
}

function parseSse(text) {
  let content = ''
  let reasoning = ''
  let usage = null
  let finish = null
  for (const line of text.split('\n')) {
    const trimmed = line.trim()
    if (!trimmed.startsWith('data:')) continue
    const data = trimmed.slice(5).trim()
    if (data === '[DONE]') continue
    let obj
    try { obj = JSON.parse(data) } catch { continue }
    const choice = obj.choices?.[0]
    const delta = choice?.delta ?? {}
    if (typeof delta.content === 'string') content += delta.content
    if (typeof delta.reasoning_content === 'string') reasoning += delta.reasoning_content
    if (typeof delta.reasoning === 'string') reasoning += delta.reasoning
    if (choice?.finish_reason) finish = choice.finish_reason
    if (obj.usage) usage = obj.usage
  }
  return { content, reasoning, usage, finish }
}

async function chat() {
  const runtime = makeRuntime()
  const model = flag('model', 'deepseek-v4.1-flash')
  const prompt = flag('prompt', '用一句中文回答：你是什么模型？')
  const system = flag('system', undefined)
  const effort = flag('effort', undefined)
  const shim = createWorkBuddyShim({
    store: runtime.store,
    client: runtime.client,
    catalog: runtime.catalog,
  })
  try {
    await shim.ready
    await loadCatalog(runtime)
    const messages = []
    if (system) messages.push({ role: 'system', content: system })
    messages.push({ role: 'user', content: prompt })
    const body = { model, messages, stream: true }
    if (effort) body.reasoning_effort = effort
    const started = Date.now()
    const { status, text } = await callShim(shim.baseUrl(), shim.token(), body)
    const parsed = parseSse(text)
    if (status !== 200) {
      console.log(JSON.stringify({ ok: false, status, body: text.slice(0, 800) }, null, 2))
      process.exitCode = 2
      return
    }
    console.log(JSON.stringify({
      ok: true,
      model,
      ms: Date.now() - started,
      content: parsed.content,
      reasoningChars: parsed.reasoning.length,
      finish: parsed.finish,
      usage: parsed.usage,
    }, null, 2))
  } finally {
    await shim.close()
  }
}

// ── 3. serve：把 shim 钉到固定端口，供任何本地消费者反向调用 ─────────────────
async function serve() {
  const port = Number(flag('port', '31720'))
  const host = flag('host', '127.0.0.1')
  const runtime = makeRuntime()
  const shim = createWorkBuddyShim({
    store: runtime.store,
    client: runtime.client,
    catalog: runtime.catalog,
  })
  await shim.ready
  const upstream = shim.baseUrl()
  const token = shim.token()

  const state = { models: 0, free: [], lastRefresh: null, lastError: null }
  const refresh = async () => {
    try {
      const { models } = await loadCatalog(runtime)
      state.models = models.length
      state.free = models.filter((m) => m.billing?.free === true).map((m) => m.id)
      state.lastRefresh = new Date().toISOString()
      state.lastError = null
    } catch (error) {
      state.lastError = String(error?.message ?? error)
    }
  }
  await refresh()
  const timer = setInterval(refresh, 10 * 60 * 1000)
  timer.unref?.()

  const server = http.createServer((req, res) => {
    // 本桥只做两件事：健康页（带模型数）与把请求原样转给 shim（补上进程内 bearer）。
    if (req.method === 'GET' && (req.url === '/' || req.url === '/healthz')) {
      const payload = JSON.stringify({
        ok: true,
        tentacle: 'workbuddy-ai',
        upstream,
        models: state.models,
        free: state.free,
        lastRefresh: state.lastRefresh,
        lastError: state.lastError,
      })
      res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' })
      res.end(payload)
      return
    }
    const forward = http.request(`${upstream}${req.url}`, {
      method: req.method,
      headers: { ...req.headers, host: new URL(upstream).host, authorization: `Bearer ${token}` },
    }, (up) => {
      res.writeHead(up.statusCode ?? 502, up.headers)
      up.pipe(res)
    })
    forward.on('error', (error) => {
      if (!res.headersSent) res.writeHead(502, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({ error: { message: String(error?.message ?? error), type: 'tentacle_upstream' } }))
    })
    req.pipe(forward)
  })

  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(port, host, resolve)
  })
  log(`listening http://${host}:${port} -> ${upstream} (models=${state.models})`)
  console.log(JSON.stringify({
    ok: true,
    listen: `http://${host}:${port}`,
    openaiBase: `http://${host}:${port}/v1`,
    models: state.models,
    free: state.free,
    pid: process.pid,
  }))
  const shutdown = async () => {
    clearInterval(timer)
    server.close()
    await shim.close().catch(() => {})
    process.exit(0)
  }
  process.on('SIGINT', shutdown)
  process.on('SIGTERM', shutdown)
}

try {
  if (mode === 'probe') await probe()
  else if (mode === 'chat') await chat()
  else if (mode === 'serve') await serve()
  else {
    console.error(`unknown mode "${mode}" (probe | chat | serve)`)
    process.exitCode = 1
  }
} catch (error) {
  console.error(JSON.stringify({ ok: false, mode, error: String(error?.message ?? error) }))
  process.exitCode = 1
}
