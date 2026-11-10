// GitHub issue 回归：#3 生图网关返回相对路径，#4 会话外调用缺少会话标识。
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { callModel, PLUGIN_SESSION_ID } from '../src/ai.js'
import { generateImage, imageUrlCandidates } from '../src/images.js'

const PNG = Buffer.from('89504e470d0a1a0a0000000d49484452', 'hex')
const GATEWAY = { baseUrl: 'http://gw.test:11435/qwenimage/v1', model: 'Qwen-Image-2.1', apiKey: 'secret-key-1234', size: '', quality: '', extra: '{"output_format":"png"}' }

test('#3 图片地址候选：保留挂载前缀，已带前缀和完整链接原样用，危险协议不要', () => {
  assert.deepEqual(imageUrlCandidates('/v1/images/x/content', GATEWAY.baseUrl), [
    'http://gw.test:11435/qwenimage/v1/images/x/content',
    'http://gw.test:11435/qwenimage/v1/v1/images/x/content',
    'http://gw.test:11435/v1/images/x/content',
  ])
  assert.deepEqual(imageUrlCandidates('/qwenimage/v1/images/x/content', GATEWAY.baseUrl), ['http://gw.test:11435/qwenimage/v1/images/x/content'])
  assert.deepEqual(imageUrlCandidates('/v1/images/x', 'https://api.example/v1'), ['https://api.example/v1/images/x'])
  assert.deepEqual(imageUrlCandidates('https://cdn.example/a.png', GATEWAY.baseUrl), ['https://cdn.example/a.png'])
  assert.deepEqual(imageUrlCandidates('javascript:alert(1)', GATEWAY.baseUrl), [])
  assert.deepEqual(imageUrlCandidates('', GATEWAY.baseUrl), [])
})

test('#3 网关返回 b64_json: null 和相对 url：跳过 404 的拼法，下到图，不重画', async () => {
  const seen = []
  const gateway = async (url, init) => {
    const href = String(url)
    seen.push([init?.method ?? 'GET', href, init?.headers?.authorization])
    if (href.endsWith('/images/generations')) return new Response(JSON.stringify({ data: [{ b64_json: null, url: '/v1/images/abc/content', file_path: '/srv/abc.png' }] }))
    if (href === 'http://gw.test:11435/qwenimage/v1/images/abc/content') return new Response(PNG)
    return new Response('not found', { status: 404 })
  }
  const result = await generateImage(GATEWAY, 'a paper boat', { fetchImpl: gateway })
  assert.equal(result.ext, '.png')
  assert.equal(seen.filter(([method]) => method === 'POST').length, 1)
  // 同源下载带上用户填的密钥
  assert.deepEqual(seen[1], ['GET', 'http://gw.test:11435/qwenimage/v1/images/abc/content', 'Bearer secret-key-1234'])
})

test('#3 地址确定拿不到时不重画，也不说成「连不上生图服务」', async () => {
  let posts = 0
  const missing = async (url) => {
    if (String(url).endsWith('/images/generations')) {
      posts += 1
      return new Response(JSON.stringify({ data: [{ b64_json: null, url: '/v1/images/abc/content' }] }))
    }
    return new Response('', { status: 404 })
  }
  await assert.rejects(generateImage(GATEWAY, 'p', { fetchImpl: missing }), err => /下载图片失败（404）/.test(err.message) && !/连不上/.test(err.message))
  assert.equal(posts, 1)

  posts = 0
  const garbage = async () => {
    posts += 1
    return new Response(JSON.stringify({ data: [{ url: 'http://' }] }))
  }
  await assert.rejects(generateImage(GATEWAY, 'p', { fetchImpl: garbage }), err => !/连不上/.test(err.message))
  assert.equal(posts, 1)

  const onlyPath = async () => new Response(JSON.stringify({ data: [{ b64_json: null, url: null, file_path: '/srv/abc.png' }] }))
  await assert.rejects(generateImage(GATEWAY, 'p', { fetchImpl: onlyPath }), /本机的文件路径/)
})

test('#3 别的域名的下载地址照样拦内网', async () => {
  const internal = async (url) => (String(url).endsWith('/images/generations')
    ? new Response(JSON.stringify({ data: [{ url: 'http://127.0.0.1/x.png' }] }))
    : new Response(PNG))
  await assert.rejects(generateImage(GATEWAY, 'p', { fetchImpl: internal }), /本机|内网/)
})

test('#4 模型调用带上会话标识，供 opencode-go 这类按会话路由的网关使用', async () => {
  const requests = []
  const ctx = {
    get(name) {
      if (name === 'agentDefaultModel') return { currentSelection: () => ({ provider: 'opencode-go', model: 'deepseek-v4.1-flash' }) }
      if (name === 'llm') {
        return {
          prepareCall: async () => ({
            config: {},
            async* stream(request) {
              requests.push(request)
              yield { type: 'text-delta', text: 'ok' }
            },
          }),
        }
      }
      return undefined
    },
  }
  await callModel(ctx, { system: 's', user: 'u' })
  await callModel(ctx, { system: 's', user: 'u' })
  await callModel(ctx, { system: 's', user: 'u', sessionId: 'custom' })
  assert.match(PLUGIN_SESSION_ID, /^dsh-media-desk-[\da-f-]{36}$/)
  assert.deepEqual(requests.map(row => row.sessionId), [PLUGIN_SESSION_ID, PLUGIN_SESSION_ID, 'custom'])
})

test('PR #5 助手模型自选：指定后优先用，清空后跟随默认；提供方和模型要一起填', async () => {
  const { modelInfo, setAssistantModel } = await import('../src/ai.js')
  const { Settings } = await import('../src/settings.js')
  const { mkdtemp, rm } = await import('node:fs/promises')
  const { tmpdir } = await import('node:os')
  const { join } = await import('node:path')
  const ctx = { get: name => (name === 'llm' ? {} : name === 'agentDefaultModel' ? { currentSelection: () => ({ provider: 'deepseek', model: 'deepseek-chat' }) } : undefined) }
  try {
    assert.equal(modelInfo(ctx).model, 'deepseek-chat')
    setAssistantModel({ provider: 'opencode-go', model: 'deepseek-v4.1-flash' })
    assert.deepEqual(modelInfo(ctx), { provider: 'opencode-go', model: 'deepseek-v4.1-flash', label: 'deepseek-v4.1-flash' })
    setAssistantModel({ provider: '', model: '' })
    assert.equal(modelInfo(ctx).model, 'deepseek-chat')
  } finally {
    setAssistantModel(null)
  }

  const dir = await mkdtemp(join(tmpdir(), 'media-desk-'))
  try {
    const settings = new Settings(dir)
    assert.deepEqual((await settings.read()).assistant, { provider: '', model: '' })
    await settings.update({ assistant: { provider: ' opencode-go ', model: 'm' } })
    assert.deepEqual((await settings.read()).assistant, { provider: 'opencode-go', model: 'm' })
    await assert.rejects(settings.update({ assistant: { provider: 'opencode-go', model: '' } }), /一起填/)
    await settings.update({ voice: 'x' })
    assert.deepEqual((await settings.read()).assistant, { provider: 'opencode-go', model: 'm' })
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})
