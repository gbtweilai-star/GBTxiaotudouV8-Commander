import assert from 'node:assert/strict'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { callModel, planPrompts } from '../src/ai.js'
import { currentLang, ENGLISH_DIRECTIVE, tr, withLang } from '../src/i18n.js'
import { localIntent, parseWhen } from '../src/intents.js'
import { applyOps } from '../src/ops.js'
import { applyRevision, normalizePlan } from '../src/produce.js'
import { buildSeed, localizeSamples, migrateState, samplesNeedLocale } from '../src/seed.js'
import { Store } from '../src/store.js'
import plugin from '../src/host.js'

const NOW = new Date('2026-10-31T15:00:00+08:00')
const CJK = /[一-鿿]/
const clone = value => JSON.parse(JSON.stringify(value))

test('tr：中文原样返回，英文查表并填占位符，查不到时退回原文', () => {
  assert.equal(currentLang(), 'zh')
  assert.equal(tr('把《{title}》排到 {when}', { title: '慢写', when: '11月3日 20:00' }), '把《慢写》排到 11月3日 20:00')
  withLang('en', () => {
    assert.equal(currentLang(), 'en')
    assert.equal(tr('把《{title}》排到 {when}', { title: 'Slow writing', when: 'Nov 3 20:00' }), 'Scheduled "Slow writing" for Nov 3 20:00')
    assert.equal(tr('改好了。'), 'Done.')
    assert.equal(tr('词典里没有的一句'), '词典里没有的一句')
    assert.equal(tr('导入{platform}账号', {}), 'Import {platform} account')
  })
  assert.equal(withLang('en-US', currentLang), 'en')
  assert.equal(withLang('zh-CN', currentLang), 'zh')
  assert.equal(withLang(undefined, currentLang), 'zh')
})

test('英文请求下生成英文示例，结构和中文版完全一致', async () => {
  const zh = buildSeed(NOW, 'zh')
  const en = withLang('en', () => buildSeed(NOW))
  assert.equal(zh.sampleLang, 'zh')
  assert.equal(en.sampleLang, 'en')
  assert.deepEqual(en.items.map(row => [row.id, row.kind, row.status, row.platform, row.scheduledAt, row.media?.src ?? null]), zh.items.map(row => [row.id, row.kind, row.status, row.platform, row.scheduledAt, ({ seed_7: 'media-desk/assets/poster-en.jpg', seed_20: 'media-desk/assets/emboss-en.jpg' })[row.id] ?? row.media?.src ?? null]))
  // 图上印着中文的那张，英文版换成英文图；切回中文换回来
  const back = localizeSamples(structuredClone(en), 'zh')
  assert.equal(back.items.find(row => row.id === 'seed_7').media.src, 'media-desk/assets/poster.jpg')
  assert.deepEqual(en.metrics, zh.metrics)
  assert.deepEqual(en.styles.map(row => [row.id, row.category, row.icon]), zh.styles.map(row => [row.id, row.category, row.icon]))
  for (const row of en.items) for (const field of ['title', 'body', 'source', ...row.tags]) assert.ok(!CJK.test(field in row ? row[field] : field), `${row.id} ${field}`)
  for (const key of ['people', 'angles', 'skills', 'accounts']) assert.ok(!CJK.test(JSON.stringify(en[key].map(({ platform, ...rest }) => rest))), key)
  for (const row of en.styles) assert.ok(!CJK.test(JSON.stringify({ ...row, category: '' })), row.id)

  // Store 在请求里第一次建库时也按请求语言写示例
  const dir = await mkdtemp(join(tmpdir(), 'media-desk-'))
  try {
    const state = await withLang('en', () => new Store(dir).read())
    assert.equal(state.sampleLang, 'en')
    assert.equal(state.items[0].title, en.items[0].title)
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test('localizeSamples：中英来回切换只换示例文字，用户内容和改过的地方不动', () => {
  const state = buildSeed(NOW, 'zh')
  const original = clone(state)
  const [mine] = applyOps(state, [{ op: 'add_item', title: '我自己的灵感', body: '只属于我' }]).receipts
  applyOps(state, [
    { op: 'set_status', id: 'seed_2', status: 'published' },
    { op: 'update_item', id: 'seed_3', title: '我改过的标题' },
    { op: 'update_style', id: 'preset_news', tone: '我自己的语气' },
    { op: 'add_style', name: '我的风格', tone: '原样' },
  ])
  const seed2 = state.items.find(row => row.id === 'seed_2')
  seed2.production = { status: 'done', title: '成稿标题', article: '正文' }
  const metrics = clone(state.metrics)
  const before = clone(state)

  assert.equal(samplesNeedLocale(state, 'en'), true)
  assert.equal(samplesNeedLocale(state, 'zh'), false)
  localizeSamples(state, 'en')
  assert.equal(state.sampleLang, 'en')
  assert.equal(samplesNeedLocale(state, 'en'), false)
  const item = id => state.items.find(row => row.id === id)
  assert.equal(item(mine.target).title, '我自己的灵感')
  assert.equal(item(mine.target).body, '只属于我')
  assert.ok(!CJK.test(item('seed_1').title))
  assert.equal(item('seed_2').status, 'published')
  assert.ok(item('seed_2').publishedAt)
  // 中文成稿和改过的标题先收起来，英文下显示英文示例
  assert.equal(item('seed_2').production, undefined)
  assert.ok(!CJK.test(item('seed_2').title))
  assert.ok(!CJK.test(item('seed_3').title))
  assert.ok(!CJK.test(item('seed_3').body))
  assert.deepEqual(state.metrics, metrics)
  const news = state.styles.find(row => row.id === 'preset_news')
  assert.equal(news.tone, '我自己的语气')
  assert.ok(!CJK.test(news.name))
  assert.equal(news.category, '热点资讯')
  assert.equal(state.styles.find(row => row.name === '我的风格').tone, '原样')
  assert.equal(state.people.find(row => row.id === 'newbie').role, 'Target reader')
  assert.equal(state.accounts[0].platform, '公众号')

  // 重复调用不再改动
  const once = JSON.stringify(state)
  localizeSamples(state, 'en')
  assert.equal(JSON.stringify(state), once)

  // 切回中文，回到切换前的样子
  localizeSamples(state, 'zh')
  const withoutStash = clone(state)
  for (const row of withoutStash.items) delete row.otherLang
  assert.deepEqual(withoutStash, { ...before, sampleLang: 'zh' })
  // 英文那份也留着：在英文下改过的内容切回英文还在
  localizeSamples(state, 'en')
  item('seed_4').title = 'My English edit'
  localizeSamples(state, 'zh')
  assert.equal(item('seed_4').title, original.items[3].title)
  localizeSamples(state, 'en')
  assert.equal(item('seed_4').title, 'My English edit')
  localizeSamples(state, 'zh')
  assert.equal(item('seed_1').title, original.items[0].title)
})

test('localizeSamples：清空示例后只换内置预设；旧数据没有 sampleLang 时当作中文', () => {
  const state = buildSeed(NOW, 'zh')
  applyOps(state, [{ op: 'add_item', title: '我的' }, { op: 'clear_samples' }])
  localizeSamples(state, 'en')
  assert.deepEqual(state.items.map(row => row.title), ['我的'])
  assert.ok(state.styles.every(row => !CJK.test(row.name)))
  localizeSamples(state, 'zh')
  assert.ok(state.styles.every(row => CJK.test(row.name)))

  const old = buildSeed(NOW, 'zh')
  delete old.sampleLang
  assert.equal(samplesNeedLocale(old, 'zh'), false)
  assert.equal(migrateState(old).sampleLang, 'zh')
  const legacy = migrateState({ items: [], people: [], angles: [], skills: [], accounts: [], metrics: [] })
  assert.equal(legacy.sampleLang, 'zh')
  localizeSamples(legacy, 'en')
  assert.ok(legacy.styles.length > 0 && legacy.styles.every(row => !CJK.test(row.name)))
})

test('英文界面下，系统提示词末尾追加英文要求，原来的中文提示词保留', async () => {
  const seen = []
  const ctx = {
    get(name) {
      if (name === 'agentDefaultModel') return { currentSelection: () => ({ provider: 'p', model: 'm' }) }
      if (name === 'llm') {
        return {
          prepareCall: async () => ({
            config: {},
            async* stream(request) {
              seen.push(request.system)
              yield { type: 'text-delta', text: 'ok' }
            },
          }),
        }
      }
      return undefined
    },
  }
  await callModel(ctx, { system: '你是文风分析师。', user: 'x' })
  await withLang('en', () => callModel(ctx, { system: '你是文风分析师。', user: 'x' }))
  assert.equal(seen[0], '你是文风分析师。')
  assert.ok(seen[1].startsWith('你是文风分析师。'))
  assert.ok(seen[1].endsWith(ENGLISH_DIRECTIVE))

  // 模拟模型靠中文关键词识别提示词，英文界面下这些词还在
  const state = buildSeed(NOW, 'zh')
  const settings = { imageCount: 2, shotCount: 6, voice: '' }
  const en = withLang('en', () => planPrompts(state, state.items[0], settings).system)
  assert.match(en, /策划案/)
  assert.doesNotMatch(en, /中文图注/)
  assert.match(planPrompts(state, state.items[0], settings).system, /中文图注/)
})

test('英文本地规则：常见说法和中文一样能用，回复是英文', () => {
  withLang('en', () => {
    const state = buildSeed(NOW)
    assert.deepEqual(localIntent(state, 'write it as a script', { now: NOW, focusId: 'seed_2' }).actions, [{ type: 'produce', id: 'seed_2' }])
    const noted = localIntent(state, 'note: billboard copy on the subway', { now: NOW })
    assert.equal(noted.ops[0].op, 'add_item')
    assert.equal(noted.reply, 'Saved. It\'s on the idea wall.')
    const scheduled = localIntent(state, 'schedule "Slow writing" for tomorrow 8pm on xiaohongshu', { now: NOW })
    assert.equal(scheduled.ops[0].id, 'seed_7')
    assert.equal(scheduled.ops[0].platform, '小红书')
    const when = new Date(scheduled.ops[0].scheduledAt)
    assert.deepEqual([when.getMonth() + 1, when.getDate(), when.getHours()], [11, 1, 20])
    assert.deepEqual(localIntent(state, 'move it to ready', { now: NOW, focusId: 'seed_2' }).ops, [{ op: 'set_status', id: 'seed_2', status: 'ready' }])
    assert.equal(localIntent(state, 'rename it to "A better title"', { now: NOW, focusId: 'seed_2' }).ops[0].id, 'seed_2')
    assert.match(localIntent(state, "what's on my schedule", { now: NOW }).reply, /^Coming up:/)
    const [receipt] = applyOps(state, [{ op: 'schedule_item', id: 'seed_2', scheduledAt: '2026-11-03T12:00:00Z', platform: '小红书' }]).receipts
    assert.match(receipt.text, /^Scheduled ".+" for Nov 3 \d\d:00 · RedNote$/)
  })
  const at = text => { const d = parseWhen(text, NOW); return d && [d.getMonth() + 1, d.getDate(), d.getHours(), d.getMinutes()] }
  assert.deepEqual(at('Nov 3 20:00'), [11, 3, 20, 0])
  assert.deepEqual(at('next wed'), [11, 4, 20, 0])
  assert.deepEqual(at('tonight at 9'), [10, 31, 21, 0])
  assert.equal(parseWhen('no date here', NOW), null)
})

test('英文成稿：回执、默认景别和封面大字兜底都是英文，长度上限不变', () => {
  withLang('en', () => {
    const plan = normalizePlan({ shots: [{ prompt: 'x' }] }, { imageCount: 0, shotCount: 1 }, 'Why your first AI side project never makes a dollar')
    assert.equal(plan.shots[0].shot, 'Medium shot')
    assert.equal(plan.coverText, 'Why your first AI side')
    assert.ok(plan.coverText.length <= 24)
    const production = { title: 't', coverText: 'c', article: 'abc', cover: { prompt: 'p' }, images: [], shots: [{ shot: 'Wide', prompt: 'p' }] }
    assert.deepEqual(applyRevision(production, { title: 'New', cover: { prompt: 'q' } }).receipts, ['Changed the title to "New"', 'Redrew the cover'])
    assert.match(applyRevision(production, { shots: [{ no: 1, prompt: 'r' }] }, { canDraw: false }).receipts[0], /^Updated the image description for shot 1/)
  })
  const production = { title: 't', cover: { prompt: 'p' }, images: [], shots: [] }
  assert.deepEqual(applyRevision(production, { cover: { prompt: 'q' } }, { canDraw: false }).receipts, ['更新了画面描述：封面（接入生图模型后才会重画）'])
})

test('GET state 按请求头的语言换示例文字', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'media-desk-'))
  const previous = process.env.DSH_HOME
  process.env.DSH_HOME = dir
  try {
    let handler = null
    const ctx = {
      get: name => (name === 'connection' ? { requestRejection: () => undefined } : undefined),
      effect: fn => fn(),
      webServer: { register: (options) => { handler = options.handler } },
    }
    plugin.apply(ctx)
    const get = lang => new Promise((resolve) => {
      const res = { statusCode: 0, headersSent: false, setHeader() {}, end: body => resolve({ status: res.statusCode, body: JSON.parse(body) }) }
      handler({ url: '/media-desk/state', method: 'GET', headers: { 'x-media-desk-lang': lang } }, res)
    })
    const zh = await get('zh')
    assert.equal(zh.status, 200)
    assert.equal(zh.body.state.sampleLang, 'zh')
    const en = await get('en')
    assert.equal(en.body.state.sampleLang, 'en')
    assert.ok(!CJK.test(en.body.state.items[0].title))
    assert.equal(en.body.canUndo, false, '换语言不占撤销位')
    const back = await get('zh')
    assert.equal(back.body.state.items[0].title, zh.body.state.items[0].title)
  } finally {
    if (previous === undefined) delete process.env.DSH_HOME
    else process.env.DSH_HOME = previous
    await rm(dir, { recursive: true, force: true })
  }
})

test('旧的英文数据：示例上残留的中文成稿收进中文那份，切回中文还在', () => {
  const state = buildSeed(NOW, 'en')
  const row = state.items.find(item => item.id === 'seed_1')
  delete row.otherLang
  row.production = { status: 'done', title: '中文成稿' }
  const mine = { id: 'it_mine', title: '我的中文灵感', drafts: {} }
  state.items.push(mine)
  migrateState(state)
  assert.equal(row.production, undefined)
  assert.ok(!CJK.test(row.title))
  assert.equal(mine.title, '我的中文灵感')
  localizeSamples(state, 'zh')
  assert.equal(row.production.title, '中文成稿')
})

