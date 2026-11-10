import assert from 'node:assert/strict'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { extractJson, fallbackArticle, fallbackPlan } from '../src/ai.js'
import { assertPublicUrl, harvest, harvestText } from '../src/harvest.js'
import { activeStyle, normalizeStyle, stylePrompts, styleToVoice } from '../src/style.js'
import { articlePrompts, planPrompts } from '../src/ai.js'
import { migrateState } from '../src/seed.js'
import { requestRejection } from '../src/host.js'
import { localIntent, parseWhen } from '../src/intents.js'
import { computeInsights, exportSkill, proposeRules } from '../src/learn.js'
import { applyOps } from '../src/ops.js'
import { buildSeed } from '../src/seed.js'
import { Store } from '../src/store.js'
import { generateImage } from '../src/images.js'
import { applyRevision, normalizePlan, Producer } from '../src/produce.js'
import { saveProduction, resolveExportDir } from '../src/export.js'
import { chatPrompts } from '../src/ai.js'
import { mkdir, readdir, writeFile } from 'node:fs/promises'
import { publicSettings, Settings } from '../src/settings.js'
import { stat } from 'node:fs/promises'

const NOW = new Date('2026-10-31T15:00:00+08:00') // 周六

function seed() {
  return buildSeed(NOW)
}

test('parseWhen 解析常见中文时间', () => {
  const at = (text) => {
    const d = parseWhen(text, NOW)
    return d && [d.getMonth() + 1, d.getDate(), d.getHours(), d.getMinutes()]
  }
  assert.deepEqual(at('明晚8点'), [11, 1, 20, 0])
  assert.deepEqual(at('后天上午九点半'), [11, 2, 9, 30])
  assert.deepEqual(at('11月3日 20:00'), [11, 3, 20, 0])
  assert.deepEqual(at('下周三'), [11, 4, 20, 0])
  assert.equal(parseWhen('没有时间的一句话', NOW), null)
})

test('localIntent 记灵感', () => {
  const plan = localIntent(seed(), '记一下：地铁上看到的广告牌文案很好', { now: NOW })
  assert.equal(plan.ops[0].op, 'add_item')
  assert.match(plan.ops[0].body, /^地铁/)
  assert.match(plan.ops[0].title, /^地铁/)
  for (const said of ['记下：同一句话', '记：同一句话', '灵感：同一句话', '加个灵感：同一句话']) {
    assert.equal(localIntent(seed(), said, { now: NOW }).ops[0].body, '同一句话', said)
  }
})

test('localIntent 用书名号定位并排期', () => {
  const state = seed()
  const plan = localIntent(state, '把《慢写》排到明晚8点 小红书', { now: NOW })
  const op = plan.ops[0]
  assert.equal(op.op, 'schedule_item')
  assert.equal(op.platform, '小红书')
  assert.equal(state.items.find(i => i.id === op.id).title.startsWith('慢写'), true)
})

test('localIntent 找不到对象时不乱改', () => {
  const plan = localIntent(seed(), '把《完全不存在的内容abc》排到明晚8点', { now: NOW })
  assert.equal(plan.ops.length, 0)
})

test('localIntent 成文、脚本、分镜都走一键成稿，这篇指向当前选中', () => {
  const state = seed()
  for (const said of ['把这篇写成脚本', '把这篇成稿', '给这篇画分镜']) {
    assert.deepEqual(localIntent(state, said, { now: NOW, focusId: 'seed_2' }).actions, [{ type: 'produce', id: 'seed_2' }], said)
  }
})

test('applyOps 拒绝未知操作和原型链上的名字', () => {
  const state = seed()
  const { errors } = applyOps(state, [{ op: 'constructor' }, { op: 'rm_rf' }])
  assert.equal(errors.length, 2)
})

test('applyOps 过滤非法字段和危险媒体地址', () => {
  const state = seed()
  const { receipts } = applyOps(state, [{ op: 'add_item', title: 'x', media: { src: 'javascript:alert(1)' }, url: 'javascript:alert(1)', status: 'nope', evil: 1 }])
  const item = state.items.find(i => i.id === receipts[0].target)
  assert.equal(item.media, undefined)
  assert.equal(item.url, undefined)
  assert.equal(item.status, 'idea')
  assert.equal(item.evil, undefined)
})

test('applyOps 部分失败不影响其余操作', () => {
  const state = seed()
  const { receipts, errors } = applyOps(state, [{ op: 'set_status', id: 'nope', status: 'draft' }, { op: 'set_status', id: 'seed_2', status: 'draft' }])
  assert.equal(errors.length, 1)
  assert.equal(receipts.length, 1)
  assert.equal(state.items.find(i => i.id === 'seed_2').status, 'draft')
})

test('删除父卡片时子卡片接到上一级', () => {
  const state = seed()
  applyOps(state, [{ op: 'update_item', id: 'seed_2', parentId: 'seed_1' }, { op: 'update_item', id: 'seed_3', parentId: 'seed_2' }, { op: 'delete_item', id: 'seed_2' }])
  assert.equal(state.items.find(i => i.id === 'seed_3').parentId, 'seed_1')
})

test('clear_samples 清空示例但保留用户内容', () => {
  const state = seed()
  applyOps(state, [{ op: 'add_item', title: '我自己的' }, { op: 'clear_samples' }])
  assert.deepEqual(state.items.map(i => i.title), ['我自己的'])
  assert.equal(state.metrics.length, 0)
})

test('Store 持久化、撤销，并能感知另一进程的写入', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'media-desk-'))
  try {
    const a = new Store(dir)
    const before = (await a.read()).items.length
    await a.mutate('add', s => applyOps(s, [{ op: 'add_item', title: '新灵感' }]))
    assert.equal((await a.read()).items.length, before + 1)
    assert.equal(await a.undoLast(), 'add')
    assert.equal((await a.read()).items.length, before)

    const b = new Store(dir)
    await b.mutate('b', s => applyOps(s, [{ op: 'add_item', title: '来自桌面端' }]))
    assert.equal((await a.read()).items[0].title, '来自桌面端')
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test('extractJson 容忍代码块和前后说明', () => {
  assert.deepEqual(extractJson('好的：\n```json\n{"a":1}\n```\n完成'), { a: 1 })
  assert.deepEqual(extractJson('结果是 [1,2] 。'), [1, 2])
  assert.throws(() => extractJson('没有结构'))
})

test('降级生成的内容明确标注未连接模型', () => {
  const state = seed()
  assert.match(fallbackArticle(state, state.items[0]), /没有连上文字模型/)
  const plan = fallbackPlan(state.items[0], '## 甲\n## 乙', { imageCount: 2, shotCount: 6 })
  assert.equal(plan.images.length, 2)
  assert.equal(plan.shots.length, 6)
})

test('proposeRules 基于数据提案，已有规则不重复', () => {
  const state = seed()
  const first = proposeRules(state)
  assert.ok(first.length > 0)
  assert.ok(first.every(p => p.evidence))
  applyOps(state, first.map(p => ({ op: 'add_skill', ...p })))
  assert.equal(proposeRules(state).length, 0)
})

test('proposeRules 没有数据时不提案', () => {
  const state = seed()
  state.metrics = []
  assert.equal(proposeRules(state).length, 0)
})

test('computeInsights 汇总与逐日数据一致', () => {
  const state = seed()
  const data = computeInsights(state)
  assert.equal(data.daily.reduce((a, b) => a + b.views, 0), data.views)
  assert.equal(data.platforms.reduce((a, b) => a + b.views, 0), data.views)
})

test('requestRejection 没有鉴权服务时拒绝，有服务时听它的', () => {
  const req = { headers: { cookie: 'x' } }
  assert.equal(requestRejection({ get: () => undefined }, req), 403)
  assert.equal(requestRejection({ get: () => ({ requestRejection: () => 401 }) }, req), 401)
  let seen = null
  const allowed = requestRejection({ get: () => ({ requestRejection: (r) => { seen = r; return undefined } }) }, req)
  assert.equal(allowed, undefined)
  assert.equal(seen.headers, req.headers)
})

test('exportSkill 不导出示例规则和示例人物', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'media-desk-skill-'))
  try {
    const state = seed()
    await assert.rejects(exportSkill(state, dir), /示例规则和模板不会被导出/)
    applyOps(state, [{ op: 'add_skill', name: '我的规则', rule: '标题不超过 20 字', status: 'active' }])
    const result = await exportSkill(state, dir)
    assert.equal(result.rules, 1)
    const body = await readFile(result.path, 'utf8')
    assert.match(body, /^---\nname: media-desk-voice\n/)
    assert.match(body, /我的规则/)
    assert.doesNotMatch(body, /开头先给数字/)
    assert.doesNotMatch(body, /想入门的小林/)
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test('assertPublicUrl 拒绝本机和内网地址', async () => {
  for (const url of ['http://localhost:3000', 'http://127.0.0.1', 'http://10.0.0.1', 'http://192.168.1.1', 'http://169.254.169.254/latest', 'http://[::1]/', 'http://[::ffff:127.0.0.1]/', 'file:///etc/passwd']) {
    await assert.rejects(assertPublicUrl(url), url)
  }
})

test('harvest 解析元信息，并拦截跳转到内网', async () => {
  const page = '<html><head><title>备用标题</title><meta property="og:title" content="主页 &amp; 档案"><meta name="description" content="粉丝 1.2万"><meta property="og:image" content="/a.jpg"></head></html>'
  const ok = async () => new Response(page, { headers: { 'content-type': 'text/html' } })
  const info = await harvest('https://93.184.216.34/u', ok)
  assert.equal(info.title, '主页 & 档案')
  assert.equal(info.image, 'https://93.184.216.34/a.jpg')
  assert.equal(info.followers, 12000)

  const redirect = async () => new Response(null, { status: 302, headers: { location: 'http://127.0.0.1/admin' } })
  await assert.rejects(harvest('https://93.184.216.34/u', redirect), /本机|内网/)
})

const PNG = Buffer.from('89504e470d0a1a0a0000000d49484452', 'hex')
const IMAGE = { baseUrl: 'https://img.example/v1', model: 'm', apiKey: 'secret-key-1234', size: '1536x1024', quality: '', extra: '{"output_format":"jpeg"}' }

test('generateImage 发送标准请求，支持 b64 和 images[0].url 两种返回', async () => {
  const calls = []
  const b64 = async (url, init) => {
    calls.push([String(url), init])
    return new Response(JSON.stringify({ data: [{ b64_json: PNG.toString('base64') }] }), { status: 200 })
  }
  const one = await generateImage(IMAGE, 'p', { fetchImpl: b64 })
  assert.equal(one.ext, '.png')
  assert.equal(calls[0][0], 'https://img.example/v1/images/generations')
  assert.equal(calls[0][1].headers.authorization, 'Bearer secret-key-1234')
  assert.deepEqual(JSON.parse(calls[0][1].body), { model: 'm', prompt: 'p', n: 1, size: '1536x1024', output_format: 'jpeg' })

  const viaUrl = async (url) => (String(url).endsWith('/generations')
    ? new Response(JSON.stringify({ images: [{ url: 'https://93.184.216.34/a.png' }] }))
    : new Response(PNG))
  assert.equal((await generateImage(IMAGE, 'p', { fetchImpl: viaUrl })).ext, '.png')
})

test('generateImage 拒绝内网下载地址、非图片内容，报错里不带密钥', async () => {
  const internal = async () => new Response(JSON.stringify({ data: [{ url: 'http://127.0.0.1/x.png' }] }))
  await assert.rejects(generateImage(IMAGE, 'p', { fetchImpl: internal }), /本机|内网/)
  const html = async () => new Response(JSON.stringify({ data: [{ b64_json: Buffer.from('<html>').toString('base64') }] }))
  await assert.rejects(generateImage(IMAGE, 'p', { fetchImpl: html }), /不是图片/)
  const leak = async () => new Response(JSON.stringify({ error: { message: 'bad key secret-key-1234' } }), { status: 400 })
  await assert.rejects(generateImage(IMAGE, 'p', { fetchImpl: leak }), err => !err.message.includes('secret-key') && err.message.includes('***'))
  const denied = async () => new Response('{}', { status: 401 })
  await assert.rejects(generateImage(IMAGE, 'p', { fetchImpl: denied }), /密钥无效/)
})

test('generateImage 遇到 5xx 重试一次', async () => {
  let n = 0
  const flaky = async () => {
    n += 1
    return n === 1 ? new Response('<html>', { status: 502 }) : new Response(JSON.stringify({ data: [{ b64_json: PNG.toString('base64') }] }))
  }
  assert.equal((await generateImage(IMAGE, 'p', { fetchImpl: flaky })).ext, '.png')
  assert.equal(n, 2)
})

test('Settings 权限 600，密钥不外泄，空密钥不覆盖', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'media-desk-set-'))
  try {
    const settings = new Settings(dir)
    await settings.update({ image: { baseUrl: 'https://x.example/v1/images/generations/', model: 'm', apiKey: 'sk-abcdefgh1234' }, imageCount: 99 })
    assert.equal((await stat(join(dir, 'settings.json'))).mode & 0o777, 0o600)
    const open = publicSettings(await settings.read())
    assert.equal(open.image.baseUrl, 'https://x.example/v1')
    assert.equal(open.image.keyHint, '1234')
    assert.equal(open.imageCount, 4)
    assert.equal(open.imageReady, true)
    assert.ok(!JSON.stringify(open).includes('abcdefgh'))
    await settings.update({ image: { apiKey: '  ', model: 'n' } })
    assert.equal((await settings.read()).image.apiKey, 'sk-abcdefgh1234')
    await assert.rejects(settings.update({ image: { baseUrl: 'javascript:alert(1)' } }), /http/)
    await assert.rejects(settings.update({ image: { extra: '[1]' } }), /JSON/)
    await settings.update({ image: { clearKey: true } })
    assert.equal(publicSettings(await settings.read()).imageReady, false)
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test('normalizePlan 丢弃多余字段并按设置截断', () => {
  const plan = normalizePlan({ title: 'T', cover: 'c', images: [{ prompt: 'a', evil: 1 }, { prompt: 'b' }, { prompt: 'c' }], shots: [{ prompt: 'x', seconds: 999 }, 'bad', null] }, { imageCount: 2, shotCount: 6 }, 'fallback')
  assert.equal(plan.images.length, 2)
  assert.equal(plan.images[0].evil, undefined)
  assert.equal(plan.shots.length, 1)
  assert.equal(plan.shots[0].seconds, 60)
  assert.equal(normalizePlan(null, { imageCount: 1, shotCount: 1 }, 'F').title, 'F')
})

async function producerFixture({ callText, generate, ready = true }) {
  const dir = await mkdtemp(join(tmpdir(), 'media-desk-prod-'))
  const store = new Store(dir)
  await store.read()
  const settings = new Settings(dir)
  await settings.update({ imageCount: 1, shotCount: 2, voice: '短句，爱用比喻', ...(ready ? { image: { baseUrl: 'https://i.example/v1', model: 'm', apiKey: 'k' } } : {}) })
  return { dir, store, producer: new Producer({ store, settings, callText, generate }) }
}

async function waitDone(producer, id) {
  for (let i = 0; i < 200 && producer.isRunning(id); i += 1) await new Promise(r => setTimeout(r, 5))
}

const isPlan = system => system.includes('策划案')
const PLAN = JSON.stringify({ title: '最终标题', cover: 'cover', characters: 'a man', images: [{ anchor: '第一节', caption: '图注', prompt: 'fig' }], shots: [{ shot: '特写', visual: '手', voice: '说', seconds: 4, prompt: 's1' }, { shot: '全景', visual: '街', voice: '说', seconds: 6, prompt: 's2' }] })

test('Producer 跑完整条线：文章、规划、全部图片，语气进入提示词', async () => {
  const prompts = []
  const systems = []
  const callText = async ({ system, onText }) => {
    systems.push(system)
    if (isPlan(system)) return { text: PLAN, model: 'deepseek' }
    onText('# 模型标题\n\n正文')
    return { text: '# 模型标题\n\n## 第一节\n正文', model: 'deepseek' }
  }
  const generate = async (_, prompt) => {
    prompts.push(prompt)
    return { buffer: PNG, ext: '.png' }
  }
  const { dir, store, producer } = await producerFixture({ callText, generate })
  try {
    assert.equal(await producer.start('seed_2'), true)
    assert.equal(await producer.start('seed_2'), false)
    await waitDone(producer, 'seed_2')
    const item = (await store.read()).items.find(i => i.id === 'seed_2')
    const p = item.production
    assert.equal(p.status, 'done')
    assert.equal(p.title, '最终标题')
    assert.match(p.article, /## 第一节/)
    assert.doesNotMatch(p.article, /模型标题/)
    assert.equal(p.cover.status, 'done')
    assert.match(p.cover.src, /^media-desk\/files\/g_.+\.png$/)
    assert.equal(p.shots.length, 2)
    assert.ok(p.shots.every(s => s.status === 'done'))
    assert.equal(item.status, 'draft')
    assert.equal(prompts.length, 4)
    assert.ok(prompts.some(x => x.includes('black and white') && x.includes('a man')))
    assert.ok(systems.every(x => x.includes('短句，爱用比喻')))
    assert.ok(isPlan(systems[0]))
    assert.equal((await stat(join(dir, 'files', p.cover.src.split('/').pop()))).size, PNG.length)
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test('Producer 模型漏掉分镜时用模板补齐', async () => {
  const callText = async ({ system }) => (isPlan(system) ? { text: '{"title":"T","cover":"c","images":[],"shots":[{"shot":"特写","visual":"手","prompt":"x"}]}', model: 'd' } : { text: '# T\n## 甲\n正文', model: 'd' })
  const { dir, store, producer } = await producerFixture({ callText, generate: async () => ({ buffer: PNG, ext: '.png' }) })
  try {
    await producer.start('seed_2')
    await waitDone(producer, 'seed_2')
    const p = (await store.read()).items.find(i => i.id === 'seed_2').production
    assert.equal(p.images.length, 1)
    assert.equal(p.shots.length, 2)
    assert.deepEqual(p.shots.map(s => s.no), [1, 2])
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test('Producer 文章和图片同时开工，策划案流式露出标题和分镜', async () => {
  const order = []
  let release
  const gate = new Promise((r) => { release = r })
  const callText = async ({ system, onText }) => {
    if (isPlan(system)) {
      onText('{"title":"流式标题","shots":[{"visual":"第一镜"},{"visual":"第二镜"}]')
      return { text: PLAN, model: 'd' }
    }
    order.push('article-start')
    await gate
    order.push('article-end')
    return { text: '正文', model: 'd' }
  }
  const generate = async () => {
    order.push('image')
    return { buffer: PNG, ext: '.png' }
  }
  const { dir, store, producer } = await producerFixture({ callText, generate })
  try {
    await producer.start('seed_2')
    for (let i = 0; i < 100 && !order.includes('image'); i += 1) await new Promise(r => setTimeout(r, 5))
    // 文章还没写完，图片已经开始了
    assert.ok(order.includes('image'))
    assert.ok(!order.includes('article-end'))
    const live = producer.status('seed_2')
    assert.equal(live.title, '流式标题')
    assert.deepEqual(live.visuals, ['第一镜', '第二镜'])
    release()
    await waitDone(producer, 'seed_2')
    const p = (await store.read()).items.find(i => i.id === 'seed_2').production
    assert.equal(p.status, 'done')
    assert.equal(p.article, '正文')
    assert.equal(p.title, '最终标题')
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test('Producer 一张图失败不影响其他，可以单独重画', async () => {
  let fail = true
  const generate = async (_, prompt) => {
    if (prompt.includes('s1') && fail) throw new Error('额度不足')
    return { buffer: PNG, ext: '.png' }
  }
  const callText = async ({ system }) => (isPlan(system) ? { text: PLAN, model: 'd' } : { text: '# T\n正文', model: 'd' })
  const { dir, store, producer } = await producerFixture({ callText, generate })
  try {
    await producer.start('seed_2')
    await waitDone(producer, 'seed_2')
    let p = (await store.read()).items.find(i => i.id === 'seed_2').production
    assert.equal(p.status, 'done')
    assert.equal(p.shots[0].status, 'failed')
    assert.equal(p.shots[0].error, '额度不足')
    assert.equal(p.shots[1].status, 'done')
    fail = false
    await producer.regenerate('seed_2', 'shot:0')
    await new Promise(r => setTimeout(r, 40))
    p = (await store.read()).items.find(i => i.id === 'seed_2').production
    assert.equal(p.shots[0].status, 'done')
    await assert.rejects(producer.regenerate('seed_2', '../x'), /目标无效/)
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test('Producer 没接生图时只出文字和分镜文案，没有模型时给结构草稿', async () => {
  const callText = async () => { throw new Error('no model') }
  const generate = async () => { throw new Error('不该被调用') }
  const { dir, store, producer } = await producerFixture({ callText, generate, ready: false })
  try {
    await producer.start('seed_2')
    await waitDone(producer, 'seed_2')
    const p = (await store.read()).items.find(i => i.id === 'seed_2').production
    assert.equal(p.status, 'done')
    assert.equal(p.engine, 'local')
    assert.match(p.article, /结构草稿/)
    assert.equal(p.needsProvider, true)
    assert.equal(p.cover.status, 'skipped')
    assert.equal(p.shots.length, 2)
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test('Producer 可以取消，重启后卡住的任务会被标记为中断', async () => {
  const callText = ({ signal }) => new Promise((_, reject) => signal.addEventListener('abort', () => reject(new Error('aborted'))))
  const { dir, store, producer } = await producerFixture({ callText, generate: async () => ({ buffer: PNG, ext: '.png' }) })
  try {
    await producer.start('seed_2')
    await producer.cancel('seed_2')
    await waitDone(producer, 'seed_2')
    assert.equal((await store.read()).items.find(i => i.id === 'seed_2').production.status, 'cancelled')

    await store.mutate('x', (s) => { s.items.find(i => i.id === 'seed_3').production = { status: 'running', cover: { status: 'running' }, images: [], shots: [] }; return s }, { undoable: false })
    await producer.settle('seed_3')
    const p = (await store.read()).items.find(i => i.id === 'seed_3').production
    assert.equal(p.status, 'failed')
    assert.equal(p.cover.status, 'idle')
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

function revisable() {
  return {
    status: 'done', title: '旧标题', article: '开头一段。\n\n## 第一节\n\n这里要改。',
    cover: { prompt: 'c', status: 'done' }, images: [{ caption: '图', prompt: 'i', status: 'done', anchor: '第一节' }],
    shots: [{ no: 1, shot: '中景', visual: 'v', voice: 'x', seconds: 5, prompt: 'p', status: 'done' }],
  }
}

test('applyRevision 改标题、局部替换、只重画改了画面的图', () => {
  const p = revisable()
  const { receipts, errors, targets } = applyRevision(p, {
    title: '新标题', edits: [{ find: '这里要改', replace: '$& 改好了' }, { find: '不存在的句子', replace: 'x' }],
    cover: { prompt: 'night' }, images: [{ no: 1, caption: '新图注' }], shots: [{ no: 1, voice: '新口播', prompt: 'top' }, { no: 9, prompt: '越界' }],
  })
  assert.equal(p.title, '新标题')
  // replace 里的 $& 不能被当成替换语法
  assert.match(p.article, /\$& 改好了/)
  assert.equal(p.images[0].caption, '新图注')
  assert.equal(p.images[0].prompt, 'i')
  assert.equal(p.shots[0].voice, '新口播')
  assert.deepEqual(targets, ['cover', 'shot:0'])
  assert.equal(errors.length, 1)
  assert.ok(receipts.length >= 4)
})

test('applyRevision 忽略垃圾输入，整篇重写时去掉一级标题', () => {
  const p = revisable()
  const before = JSON.stringify(p)
  assert.deepEqual(applyRevision(p, null), { receipts: [], errors: [], targets: [] })
  applyRevision(p, { images: 'x', shots: [null, 3], edits: [1, { find: 2 }], title: 5 })
  assert.equal(JSON.stringify(p), before)
  applyRevision(p, { article: '# 标题\n\n新的正文' })
  assert.equal(p.article, '新的正文')
})

test('chatPrompts 只有成稿完成时才把成稿交给模型', () => {
  const state = seed()
  const item = state.items[0]
  assert.doesNotMatch(chatPrompts(state, 'x', { focusId: item.id }).user, /<production>/)
  item.production = { ...revisable(), article: '独特正文' }
  const prompts = chatPrompts(state, 'x', { focusId: item.id })
  assert.match(prompts.user, /<production>.*独特正文/)
  assert.match(prompts.system, /revise/)
  item.production.status = 'running'
  assert.doesNotMatch(chatPrompts(state, 'x', { focusId: item.id }).user, /<production>/)
})

test('saveProduction 写出文章、脚本和素材，标题里的路径字符被清掉', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'media-desk-save-'))
  try {
    const filesDir = join(dir, 'files')
    await mkdir(filesDir)
    await writeFile(join(filesDir, 'a.jpg'), PNG)
    await writeFile(join(filesDir, 'b.jpg'), PNG)
    const p = revisable()
    p.title = '../危险/标题: 测试'
    p.cover.src = 'media-desk/files/a.jpg'
    p.images[0].src = 'media-desk/files/b.jpg'
    p.shots[0].src = 'media-desk/assets/../../secret.jpg'
    p.shots[0].voice = '带|竖线'
    const saved = await saveProduction(p, { filesDir, exportDir: join(dir, 'out'), videoCover: Buffer.from([0xff, 0xd8, 0xff]) })
    assert.equal(saved.path, join(dir, 'out', '危险 标题 测试'))
    const names = await readdir(saved.path)
    assert.deepEqual(names.sort(), ['分镜脚本.md', '封面原图.jpg', '视频封面.jpg', '脚本.md', '配图1.jpg'].sort())
    const article = await readFile(join(saved.path, '脚本.md'), 'utf8')
    assert.match(article, /^# \.\.\/危险/)
        assert.match(article, /这里要改。\n\n!\[图\]\(配图1\.jpg\)/)
    assert.match(await readFile(join(saved.path, '分镜脚本.md'), 'utf8'), /带｜竖线/)
    // 再存一次写回同一个文件夹
    p.savedPath = saved.path
    assert.equal((await saveProduction({ ...p, title: '改名了' }, { filesDir, exportDir: join(dir, 'out') })).path, saved.path)
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test('resolveExportDir 展开 ~，空值用默认位置', () => {
  assert.match(resolveExportDir(''), /Documents\/自媒体工作台$/)
  assert.ok(!resolveExportDir('~/x').startsWith('~'))
  assert.equal(resolveExportDir('/tmp/x'), '/tmp/x')
})

test('风格：只留白名单字段，能变成写作要求，并进入提示词', () => {
  const style = normalizeStyle({ name: '慢半拍', summary: 's', tone: 't', words: ['那天', 3, ''], samples: ['样句'], evil: 1 })
  assert.equal(style.evil, undefined)
  assert.deepEqual(style.words, ['那天'])
  assert.match(styleToVoice(style), /常用词：那天/)
  assert.equal(normalizeStyle(null, '备用').name, '备用')
  assert.equal(styleToVoice(null), '')
  assert.match(stylePrompts('素材', '').system, /文风分析师/)

  const state = seed()
  const item = state.items[0]
  const { receipts } = applyOps(state, [{ op: 'add_style', name: '我的', tone: '很独特的语气' }])
  assert.equal(activeStyle(state), null)
  // 没选风格时用设置里的语气
  assert.match(articlePrompts(state, item, '旧语气').system, /旧语气/)
  applyOps(state, [{ op: 'set_style', id: receipts[0].target }])
  const prompts = articlePrompts(state, item, '旧语气')
  assert.match(prompts.system, /很独特的语气/)
  assert.doesNotMatch(prompts.system, /旧语气/)
  assert.match(planPrompts(state, item, { imageCount: 1, shotCount: 1 }).system, /很独特的语气/)
  applyOps(state, [{ op: 'delete_style', id: receipts[0].target }])
  assert.equal(state.activeStyleId, null)
})

test('脚本提示词带上策划好的事实和口播，保证数字一致', () => {
  const state = seed()
  const plan = { title: 'T', outline: ['甲'], facts: ['存了 214 条提示词'], shots: [{ visual: 'v', voice: '三个月存了 214 条' }] }
  const { system, user } = articlePrompts(state, state.items[0], '', plan)
  assert.match(system, /口播脚本/)
  assert.match(system, /存了 214 条提示词/)
  assert.match(user, /三个月存了 214 条/)
  const normalized = normalizePlan({ title: 'T', coverText: '封面字', facts: ['a', 1] }, { imageCount: 0, shotCount: 0 }, 'x')
  assert.equal(normalized.coverText, '封面字')
  assert.deepEqual(normalized.facts, ['a'])
  assert.equal(normalizePlan({}, { imageCount: 0, shotCount: 0 }, '很长很长很长很长很长的标题').coverText.length, 12)
})

test('风格预设：旧模板换成新预设，清空示例也不会删预设', async () => {
  const { STYLE_CATEGORIES, STYLE_PRESETS } = await import('../src/style-presets.js')
  for (const row of STYLE_PRESETS) {
    assert.ok(STYLE_CATEGORIES.includes(row.category), row.name)
    for (const key of ['icon', 'name', 'summary', 'tone', 'sentences', 'opening', 'structure']) assert.ok(row[key], `${row.name} 缺 ${key}`)
    assert.ok(row.words.length && row.avoid.length && row.samples.length, row.name)
    assert.ok(!/[\u4e00-\u9fff]/.test(row.icon), `${row.name} 的图标不能是汉字`)
  }
  assert.equal(new Set(STYLE_PRESETS.map(row => row.icon)).size, STYLE_PRESETS.length)
  for (const category of STYLE_CATEGORIES) assert.ok(STYLE_PRESETS.some(row => row.category === category), category)

  const old = { items: [], activeStyleId: 'seed_style_story', styles: [{ id: 'seed_style_story', name: '松弛讲故事', sample: true }, { id: 'st_1', name: '我的' }] }
  migrateState(old)
  assert.equal(old.activeStyleId, 'preset_story')
  assert.equal(old.styles.some(row => row.id.startsWith('seed_style_')), false)
  assert.equal(old.styles[0].name, '我的')
  assert.equal(old.styles.filter(row => row.preset).length, STYLE_PRESETS.length)

  // 预设删过之后不再补回来
  const deleted = migrateState({ items: [], sampleCleared: true })
  assert.equal(deleted.styles.length, STYLE_PRESETS.length)
  applyOps(deleted, [{ op: 'delete_style', id: 'preset_news' }])
  assert.equal(migrateState(deleted).styles.some(row => row.id === 'preset_news'), false)

  const state = seed()
  assert.equal(state.styles.length, STYLE_PRESETS.length)
  assert.ok(state.items.some(row => row.sample))
  applyOps(state, [{ op: 'add_style', name: '我的' }, { op: 'set_style', id: 'preset_travel' }, { op: 'clear_samples' }])
  assert.equal(state.items.some(row => row.sample), false)
  assert.equal(state.metrics.some(row => row.sample), false)
  assert.equal(state.skills.some(row => row.sample), false)
  assert.equal(state.accounts.some(row => row.sample), false)
  assert.equal(state.styles.length, STYLE_PRESETS.length + 1)
  assert.equal(state.activeStyleId, 'preset_travel')
})

test('harvestText 抽出正文，去掉脚本和导航', async () => {
  const page = '<html><head><title>标题</title><style>x{}</style></head><body><nav>导航内容不要这段内容</nav><script>var a=1</script><p>这是第一段正文内容，足够长。</p><div>这是第二段&amp;正文内容，足够长。</div></body></html>'
  const { text, title } = await harvestText('https://93.184.216.34/a', async () => new Response(page, { headers: { 'content-type': 'text/html' } }))
  assert.equal(title, '标题')
  assert.match(text, /第一段正文/)
  assert.match(text, /第二段&正文/)
  assert.doesNotMatch(text, /导航|var a/)
  await assert.rejects(harvestText('http://127.0.0.1/x'), /本机|内网/)
})

test('applyRevision 能改封面大字', () => {
  const p = revisable()
  const { receipts } = applyRevision(p, { coverText: '新大字' })
  assert.equal(p.coverText, '新大字')
  assert.match(receipts[0], /新大字/)
})

test('提炼风格时，用户起的名字优先于模型起的名字', async () => {
  const { normalizeStyle } = await import('../src/style.js')
  assert.equal(normalizeStyle({ name: '慢半拍' }, '我自己').name, '我自己')
  assert.equal(normalizeStyle({ name: '慢半拍' }, '').name, '慢半拍')
  assert.equal(normalizeStyle({}, '').name, '未命名风格')
})

test('Monid：主页链接只认三个平台和固定格式的 ID', async () => {
  const { findUrl, parseAccountUrl } = await import('../src/monid.js')
  assert.equal(parseAccountUrl('https://www.xiaohongshu.com/user/profile/aaaabbbbccccdddd00001111?xsec=1').platform, '小红书')
  assert.equal(parseAccountUrl('https://www.douyin.com/user/MS4wLjABAAAAabcdefghijklmnopqrstuvwxyz?from=1').id, 'MS4wLjABAAAAabcdefghijklmnopqrstuvwxyz')
  assert.equal(parseAccountUrl('https://space.bilibili.com/12345678/video').id, '12345678')
  for (const bad of ['https://evil.example/user/profile/aaaabbbbccccdddd00001111', 'https://xiaohongshu.com.evil.example/user/profile/aaaabbbbccccdddd00001111', 'https://www.xiaohongshu.com/user/profile/--query', 'https://www.douyin.com/user/self', 'javascript:alert(1)']) {
    assert.equal(parseAccountUrl(bad), null, bad)
  }
  assert.equal(findUrl('长按复制 https://v.douyin.com/abc/ 打开抖音'), 'https://v.douyin.com/abc/')
})

test('Monid：短链只跟平台自己的域名，打开后不是主页就报错', async () => {
  const { resolveAccount } = await import('../src/monid.js')
  await assert.rejects(resolveAccount('https://evil.example/x', async () => assert.fail('不该请求')), /认不出/)
  await assert.rejects(resolveAccount('没有链接'), /没找到链接/)
  const hops = []
  const fake = async (url) => { hops.push(url); return { headers: new Headers({ location: 'https://space.bilibili.com/42' }) } }
  const account = await resolveAccount('看这个 https://b23.tv/abc', fake)
  assert.equal(account.id, '42')
  assert.equal(hops.length, 1)
})

test('Monid：从 .cmd shim 找到真正的 CLI 入口（含转发壳）', async () => {
  const { resolveMonidEntry } = await import('../src/monid.js')
  const dir = await mkdtemp(join(tmpdir(), 'monid-shim-'))
  try {
    const entry = join(dir, 'node_modules', '@monid-ai', 'cli', 'dist', 'index.js')
    await mkdir(join(dir, 'node_modules', '@monid-ai', 'cli', 'dist'), { recursive: true })
    await writeFile(entry, '')
    const shim = join(dir, 'monid.cmd')
    await writeFile(shim, '@ECHO off\r\n"%dp0%\\node_modules\\@monid-ai\\cli\\dist\\index.js" %*')
    assert.equal(await resolveMonidEntry(shim), entry)
    const forwarder = join(dir, 'forwarder.cmd')
    await writeFile(forwarder, '@echo off\r\ncall "' + shim + '" %*')
    assert.equal(await resolveMonidEntry(forwarder), entry)
    assert.equal(await resolveMonidEntry(join(dir, 'no-such-dir', 'missing.cmd')), null)
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test('Monid：有 JS 入口时用 node 执行，参数原样传、不经过 shell', async () => {
  const { createMonidRunner } = await import('../src/monid.js')
  const calls = []
  const exec = (file, argv, options, callback) => { calls.push({ file, argv, options }); callback(null, '{"balance":{"value":0,"currency":"USD"}}', '') }
  const run = createMonidRunner(exec, async () => ({ bin: 'C:\\npm\\monid.cmd', entry: 'C:\\npm\\node_modules\\@monid-ai\\cli\\dist\\index.js', path: 'C:\\npm' }))
  assert.deepEqual(await run(['--query', '{"limit":1}', '-j']), { balance: { value: 0, currency: 'USD' } })
  assert.equal(calls.length, 1)
  assert.equal(calls[0].file, process.execPath)
  assert.deepEqual(calls[0].argv, ['C:\\npm\\node_modules\\@monid-ai\\cli\\dist\\index.js', '--query', '{"limit":1}', '-j'])
  assert.equal(calls[0].options.env.NO_COLOR, '1')
  assert.equal(calls[0].options.env.PATH, 'C:\\npm')
})

test('Monid：没有 JS 入口时照旧直接调用命令本身', async () => {
  const { createMonidRunner } = await import('../src/monid.js')
  const calls = []
  const exec = (file, argv, options, callback) => { calls.push({ file, argv }); callback(null, '{"ok":true}', '') }
  const run = createMonidRunner(exec, async () => ({ bin: '/usr/local/bin/monid', entry: null, path: '/usr/local/bin' }))
  assert.deepEqual(await run(['balance', '-j']), { ok: true })
  assert.equal(calls[0].file, '/usr/local/bin/monid')
  assert.deepEqual(calls[0].argv, ['balance', '-j'])
})

const xhsOutput = { code: 0, success: true, data: { notes: [
  { id: 'a'.repeat(24), title: '第一条', desc: '正文', create_time: 1790000000, likes: 10, comments_count: 2, collected_count: 3, share_count: 1, view_count: 0, images_list: [{ url: 'http://ci.example/1.jpg' }] },
  { id: 'not-valid', title: '坏数据' },
] } }

test('Monid：只取用得到的字段，坏数据和平台报错都不进来', async () => {
  const { normalizePosts, normalizeProfile } = await import('../src/monid.js')
  const [note, ...rest] = normalizePosts('小红书', xhsOutput)
  assert.equal(rest.length, 0)
  assert.deepEqual([note.title, note.likes, note.views, note.cover], ['第一条', 10, 0, 'https://ci.example/1.jpg'])
  assert.equal(note.url, `https://www.xiaohongshu.com/explore/${'a'.repeat(24)}`)
  const [video] = normalizePosts('抖音', { status_code: 0, aweme_list: [{ aweme_id: '123', desc: '第一行\n第二行', create_time: 1790000000, statistics: { digg_count: 5, play_count: 0 }, video: { cover: { url_list: ['https://p.example/c.jpg'] } } }] })
  assert.deepEqual([video.title, video.likes, video.url], ['第一行', 5, 'https://www.douyin.com/video/123'])
  const [bili] = normalizePosts('B站', { code: 0, data: { list: { vlist: [{ bvid: 'BV1xx', title: '视频', created: 1790000000, play: 99, comment: 1, pic: '//i0.example/a.jpg' }] } } })
  assert.deepEqual([bili.views, bili.cover], [99, 'https://i0.example/a.jpg'])
  assert.throws(() => normalizePosts('抖音', { status_code: 8, status_msg: '账号不存在' }), /账号不存在/)
  assert.throws(() => normalizePosts('B站', { code: -404, message: '啥都木有' }), /啥都木有/)
  assert.equal(normalizeProfile('B站', { profile: { data: { name: '某人' } }, relation: { follower: 7 } }).followers, 7)
  assert.equal(normalizeProfile('小红书', { profile: { data: { nickname: '某人', interactions: [{ type: 'fans', count: 8 }] } } }).followers, 8)
})

test('Monid：花费累加，资料失败不影响内容，预算拦截和没装都说清楚', async () => {
  const { fetchAccount, monidStatus } = await import('../src/monid.js')
  const account = { platform: '小红书', id: 'a'.repeat(24), url: 'u' }
  const calls = []
  const run = async (args) => {
    calls.push(args)
    if (args.includes('/api/v1/xiaohongshu/app_v2/get_user_info')) throw new Error('超时')
    return { status: 'COMPLETED', cost: { value: 0.01 }, output: xhsOutput }
  }
  const result = await fetchAccount(account, run)
  assert.equal(result.posts.length, 1)
  assert.equal(result.cost, 0.01)
  assert.equal(calls.length, 2)
  assert.deepEqual(JSON.parse(calls[0][calls[0].indexOf('--query') + 1]), { user_id: 'a'.repeat(24) })
  await assert.rejects(fetchAccount(account, async () => ({ status: 'BLOCKED' })), /预算限制/)
  await assert.rejects(fetchAccount(account, async () => null), /还没装好/)
  await assert.rejects(fetchAccount(account, async () => ({ status: 'COMPLETED', output: { code: 0, data: { notes: [] } } })), /没抓到内容/)
  assert.deepEqual(await monidStatus(async () => null), { state: 'missing' })
  assert.deepEqual(await monidStatus(async () => ({ error: { code: 'AUTH_FAILED' } })), { state: 'nokey' })
  assert.deepEqual(await monidStatus(async () => ({ balance: { value: 1.5, currency: 'USD' } })), { state: 'ready', balance: { value: 1.5, currency: 'USD' } })
})

test('Monid：重复导入只更新数字，示例数据退出统计，没有播放量时按互动排序', async () => {
  const { importPosts, normalizePosts, postsToMaterial } = await import('../src/monid.js')
  const { computeInsights } = await import('../src/learn.js')
  const posts = normalizePosts('小红书', xhsOutput)
  const draft = { items: [{ id: 's', title: '示例', status: 'published', sample: true }], metrics: [{ id: 'sm', itemId: 's', platform: '抖音', date: '2026-01-01T00:00:00Z', views: 9999, likes: 1, sample: true }], accounts: [{ id: 'sa', followers: 500, sample: true }] }
  const account = { platform: '小红书', id: 'x', url: 'https://www.xiaohongshu.com/user/profile/x' }
  const first = importPosts(draft, { account, profile: { nickname: '我', followers: 100 }, posts })
  assert.deepEqual(first, { added: 1, updated: 0 })
  const item = draft.items.find(row => row.imported)
  item.title = '我改过的标题'
  const second = importPosts(draft, { account, profile: { nickname: '我', followers: 120 }, posts: [{ ...posts[0], likes: 50 }] })
  assert.deepEqual(second, { added: 0, updated: 1 })
  assert.equal(draft.items.filter(row => row.imported).length, 1)
  assert.equal(item.title, '我改过的标题')
  assert.equal(draft.metrics.filter(row => row.externalId).length, 1)
  assert.equal(draft.accounts.filter(row => row.externalId).length, 1)
  const insights = computeInsights(draft)
  assert.equal(insights.hasSample, false)
  assert.equal(insights.views, 0)
  assert.equal(insights.engaged, 56)
  assert.equal(insights.published, 1)
  assert.equal(insights.followers, 120)
  assert.equal(insights.top[0].engaged, 56)
  assert.match(postsToMaterial(posts), /第一条\n正文/)
})

test('Monid：不经过 shell，混着提示也能解析，出错时读得到错误', async () => {
  const { createMonidRunner } = await import('../src/monid.js')
  const located = async () => ({ bin: '/x/monid', path: '/x' })
  let seen
  const noisy = createMonidRunner((bin, args, options, callback) => {
    seen = { bin, args, options }
    callback(null, '有新版本可用\n{"balance":{"value":1}}\n', '')
  }, located)
  const injected = '$(touch /tmp/pwned); --query'
  assert.deepEqual(await noisy(['run', injected]), { balance: { value: 1 } })
  assert.equal(seen.bin, '/x/monid')
  assert.deepEqual(seen.args, ['run', injected])
  assert.equal(seen.options.shell, undefined)
  assert.equal(seen.options.env.NO_COLOR, '1')
  const failing = createMonidRunner((bin, args, options, callback) => callback(new Error('exit 1'), '{"error":{"code":"AUTH_FAILED"}}', ''), located)
  assert.equal((await failing(['balance', '-j'])).error.code, 'AUTH_FAILED')
  const broken = createMonidRunner((bin, args, options, callback) => callback(new Error('exit 1'), '', '坏了'), located)
  await assert.rejects(broken(['balance', '-j']), /坏了/)
  assert.equal(await createMonidRunner(() => assert.fail('不该运行'), async () => null)(['balance', '-j']), null)
})

test('Monid：封面存到本地，内网地址、非图片和已有封面都跳过', async () => {
  const { mkdtemp, readdir, rm } = await import('node:fs/promises')
  const { tmpdir } = await import('node:os')
  const { join } = await import('node:path')
  const { saveCovers } = await import('../src/monid.js')
  const dir = await mkdtemp(join(tmpdir(), 'md-covers-'))
  const png = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0, 0, 0, 0])
  const requested = []
  const fake = async (url) => {
    requested.push(String(url))
    if (String(url).includes('html')) return new Response('<html>', { status: 200 })
    return new Response(png, { status: 200 })
  }
  const posts = [
    { id: 'ok', cover: 'https://93.184.216.34/a.png' },
    { id: 'html', cover: 'https://93.184.216.34/html' },
    { id: 'private', cover: 'https://127.0.0.1/secret.png' },
    { id: 'none', cover: null },
    { id: 'known', cover: 'https://93.184.216.34/known.png' },
  ]
  const state = { items: [{ externalId: '抖音:known', media: { src: 'media-desk/files/x.png' } }] }
  const saved = await saveCovers(posts, '抖音', state, dir, fake)
  assert.deepEqual([...saved.keys()], ['ok'])
  assert.match(saved.get('ok'), /^media-desk\/files\/c_[\w]+\.png$/)
  assert.equal(requested.some(url => url.includes('127.0.0.1') || url.includes('known')), false)
  assert.equal((await readdir(dir)).length, 1)
  await rm(dir, { recursive: true })
})

test('排期：排上日历就是待发布，取消排期退回草稿，已发布不动', () => {
  const state = seed()
  const [ideaR, doneR] = applyOps(state, [{ op: 'add_item', title: '只有灵感' }, { op: 'add_item', title: '已成稿' }]).receipts
  const done = state.items.find(row => row.id === doneR.target)
  done.production = { status: 'done', title: '已成稿' }
  applyOps(state, [{ op: 'schedule_item', id: ideaR.target, scheduledAt: '2026-12-01T12:00:00Z' }, { op: 'schedule_item', id: doneR.target, scheduledAt: '2026-12-01T12:00:00Z' }])
  assert.equal(state.items.find(row => row.id === ideaR.target).status, 'outline')
  assert.equal(done.status, 'ready')
  applyOps(state, [{ op: 'schedule_item', id: doneR.target, scheduledAt: null }])
  assert.equal(done.status, 'draft')
  applyOps(state, [{ op: 'update_item', id: doneR.target, status: 'published' }, { op: 'schedule_item', id: doneR.target, scheduledAt: null }])
  assert.equal(done.status, 'published')
  const [media] = applyOps(state, [{ op: 'add_item', kind: 'image', media: { src: 'media-desk/files/x.png' } }]).receipts
  assert.match(state.items.find(row => row.id === media.target).title, /的图片$/)
})

test('生图被限流（429）时会等一会儿再试，最多三次', async () => {
  const calls = { s1: 0, other: 0 }
  const generate = async (_, prompt) => {
    if (prompt.includes('s1')) {
      calls.s1 += 1
      if (calls.s1 < 3) throw new Error('请求太频繁或额度不足（429）')
    } else calls.other += 1
    return { buffer: PNG, ext: '.png' }
  }
  const callText = async ({ system }) => (isPlan(system) ? { text: PLAN, model: 'd' } : { text: '# T\n正文', model: 'd' })
  const { dir, store, producer } = await producerFixture({ callText, generate })
  producer.retryScale = 0.001
  try {
    await producer.start('seed_2')
    await waitDone(producer, 'seed_2')
    const p = (await store.read()).items.find(i => i.id === 'seed_2').production
    assert.equal(calls.s1, 3)
    assert.equal(p.shots[0].status, 'done')
    assert.ok(p.shots.every(row => row.status === 'done'))
  } finally {
    await rm(dir, { recursive: true })
  }
})

test('撤销只撤回那一步：之后生成的成稿和画好的图不受影响', async () => {
  const { Store, revertChange } = await import('../src/store.js')
  const dir = await mkdtemp(join(tmpdir(), 'md-undo-'))
  try {
    const store = new Store(dir)
    const state = await store.read()
    const id = state.items[0].id
    // 1. 切换风格（可撤销）
    await store.mutate('切换风格', (draft) => { draft.activeStyleId = 'preset_travel' })
    // 2. 之后生成了成稿（不可撤销的后台写入）
    await store.mutate('成稿', (draft) => { draft.items[0].production = { status: 'done', title: '原标题', shots: [{ no: 1, prompt: 'a', status: 'done', src: 'old.png' }] } }, { undoable: false })
    // 3. 对话改了标题和第 1 镜的画面（可撤销）
    await store.mutate('对话', (draft) => { const p = draft.items[0].production; p.title = '新标题'; p.shots[0].prompt = 'b'; p.shots[0].status = 'running' })
    // 4. 第 1 镜重画完成（不可撤销）
    await store.mutate('成稿', (draft) => { const shot = draft.items[0].production.shots[0]; shot.status = 'done'; shot.src = 'new.png' }, { undoable: false })

    assert.equal(await store.undoLast(), '对话')
    let p = (await store.read()).items.find(row => row.id === id).production
    assert.equal(p.title, '原标题')
    assert.equal(p.shots[0].prompt, 'a')
    assert.equal(p.shots[0].src, 'new.png')
    assert.equal(p.shots[0].status, 'done')

    assert.equal(await store.undoLast(), '切换风格')
    const after = await store.read()
    assert.equal(after.activeStyleId, null)
    p = after.items.find(row => row.id === id).production
    assert.equal(p.status, 'done', '撤销切换风格不能抹掉成稿')

    // 什么都没改的操作不进撤销栈
    await store.mutate('空操作', () => {})
    assert.equal(store.undo.length, 0)

    // 新增和删除也能撤回，删掉的行回到原位
    const removed = after.items[1]
    await store.mutate('删除', (draft) => { draft.items.splice(1, 1) })
    await store.mutate('新增', (draft) => { draft.items.unshift({ id: 'new_1', title: '新灵感' }) })
    await store.undoLast()
    await store.undoLast()
    const back = await store.read()
    assert.equal(back.items.some(row => row.id === 'new_1'), false)
    assert.equal(back.items[1].id, removed.id)

    assert.deepEqual(revertChange({ a: 1 }, { a: 2 }, { a: 3 }), { a: 3 }, '之后又被改过就保留现在的值')
  } finally {
    await rm(dir, { recursive: true })
  }
})

test('状态规则：发布时间、排期与取消排期、清空示例不留悬空数据', () => {
  const state = seed()
  const [r] = applyOps(state, [{ op: 'add_item', title: '只有灵感' }]).receipts
  const item = state.items.find(row => row.id === r.target)
  applyOps(state, [{ op: 'schedule_item', id: item.id, scheduledAt: '2026-12-01T12:00:00Z' }])
  assert.equal(item.status, 'outline')
  applyOps(state, [{ op: 'schedule_item', id: item.id, scheduledAt: null }])
  assert.equal(item.status, 'idea', '没成稿的灵感取消排期回到灵感')
  applyOps(state, [{ op: 'update_item', id: item.id, status: 'published' }])
  assert.ok(item.publishedAt, '用 update_item 发布也要记发布时间')
  applyOps(state, [{ op: 'set_status', id: item.id, status: 'draft' }])
  assert.equal(item.publishedAt, undefined, '离开已发布要清掉发布时间')
  const sample = state.items.find(row => row.sample)
  const [child] = applyOps(state, [{ op: 'add_item', title: '挂在示例下面', parentId: sample.id }, { op: 'add_metric', itemId: sample.id, platform: '抖音', date: '2026-11-01T12:00:00Z', views: 10 }]).receipts
  applyOps(state, [{ op: 'clear_samples' }])
  assert.equal(state.items.find(row => row.id === child.target).parentId, null)
  assert.equal(state.metrics.length, 0)
})
