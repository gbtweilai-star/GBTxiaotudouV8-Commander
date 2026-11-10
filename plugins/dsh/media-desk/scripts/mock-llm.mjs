// 本地模拟模型（OpenAI 兼容流式接口），只用于开发时验证模型链路，不消耗真实额度。
// 也模拟图片接口：返回 assets 里的示例图，并故意延迟几秒，用来看生成过程。
// 用法：node scripts/mock-llm.mjs [端口]。每次请求的摘要写到 stdout。
import { readFileSync, readdirSync } from 'node:fs'
import { createServer } from 'node:http'

const PORT = Number(process.argv[2] ?? 4399)
const ASSETS = new URL('../assets/', import.meta.url)
const PHOTOS = readdirSync(ASSETS).filter(name => /^(hills|dunes|sea|still|night|ink)\.jpg$/.test(name))
const SKETCHES = readdirSync(ASSETS).filter(name => /^(topo|stairs|facade)\.jpg$/.test(name))
let served = 0

function answer(system, user) {
  if (system.includes('文风分析师')) {
    return JSON.stringify({ name: '慢半拍', summary: '不急着下结论，先把场景讲清楚。', tone: '平静、好奇。', sentences: '长短交替，常用逗号断开。', opening: '从一个具体的早晨开始。', structure: '场景、疑问、一个小发现。', words: ['那天', '后来'], avoid: ['感叹号'], samples: ['那天早上我差点迟到，却停在了一块广告牌前。'] })
  }
  if (system.includes('策划案')) {
    return JSON.stringify({ title: '慢一点，也算到达', coverText: '慢，也算到达', facts: ['差点迟到 3 分钟'], outline: ['第一部分', '结尾'], cover: 'A lone commuter on an empty subway platform at dawn, soft golden light', characters: 'a young man in a grey jacket with a canvas backpack', images: [{ anchor: '第一部分', caption: '站台上的早晨', prompt: 'Morning light on a subway platform, one figure waiting' }, { anchor: '结尾', caption: '抬头那一刻', prompt: 'A person looks up at a billboard with quiet wonder' }], shots: [['特写', '广告牌上的一行字', '慢一点也算到达。', 'Close-up of a blank billboard corner'], ['中景', '他停下脚步抬头', '那天我差点迟到。', 'Medium shot from behind, man stops and looks up'], ['全景', '人潮从他身边涌过', '所有人都在赶路。', 'Wide shot, crowd rushing past a still man'], ['近景', '他笑了一下', '我忽然不急了。', 'Close shot of the man smiling faintly'], ['俯拍', '站台上的人流', '慢下来才看见路。', 'Top-down view of commuters on a platform'], ['中景', '他走上楼梯进入阳光', '你今天慢下来了吗？', 'Medium shot, man climbing stairs into sunlight']].map(([shot, visual, voice, prompt]) => ({ shot, visual, voice, seconds: 5, prompt })) })
  }
  if (system.includes('只输出一个 JSON 对象')) {
    const said = user.slice(user.lastIndexOf('用户说：') + 4)
    const focus = /focusId: (\S+)/.exec(user)?.[1]
    if (user.includes('<production>')) {
      return JSON.stringify({ reply: '标题改短了，第一个要点也换了说法，第 3 镜重画成俯拍。', ops: [], revise: { title: '慢一点，也算到', edits: [{ find: '要点一', replace: '第一点：先停下来' }], shots: [{ no: 3, shot: '俯拍', voice: '所有人都在赶路，只有他停住了。', prompt: 'Top-down view of a crowd flowing around one still man' }] } })
    }
    if (said.includes('排查错误')) return '这不是 JSON'
    if (said.includes('写成脚本') && focus !== 'null') return JSON.stringify({ reply: '开始写脚本。', ops: [], actions: [{ type: 'draft', id: focus, format: 'script' }] })
    return JSON.stringify({
      reply: '已经帮你补全成一个选题，并放进灵感墙。',
      ops: [
        { op: 'add_item', kind: 'note', title: `补全后的选题：${said.slice(0, 16)}`, body: '模型补全的说明。', tags: ['模拟'], status: 'idea' },
        { op: 'add_skill', name: '模拟规则', rule: '标题不超过 20 字', source: '对话', status: 'proposed', confidence: 0.6 },
        { op: 'delete_item', id: 'not-a-real-id' },
      ],
    })
  }
  return '# 模型写的标题\n\n那天早上我差点迟到，3 分钟后的地铁，我却停在了一块广告牌前。\n\n## 第一部分\n\n广告牌上只有一句话。这是流式写出的正文，用来验证打字效果，正式内容由真实模型生成。\n\n- 要点一\n- 要点二\n\n<script>window.__xss = 1</script>\n\n## 结尾\n\n只留一个行动：今天慢下来一次。\n'
}

createServer((req, res) => {
  const chunks = []
  req.on('data', c => chunks.push(c))
  req.on('end', async () => {
    if (req.url.endsWith('/models')) {
      res.setHeader('content-type', 'application/json')
      res.end(JSON.stringify({ data: [{ id: 'mock-model' }] }))
      return
    }
    const body = JSON.parse(Buffer.concat(chunks).toString() || '{}')
    if (req.url.endsWith('/images/generations')) {
      served += 1
      const pool = body.prompt.includes('storyboard') ? SKETCHES : PHOTOS
      await new Promise(r => setTimeout(r, 2500 + (served % 5) * 1500))
      res.setHeader('content-type', 'application/json')
      res.end(JSON.stringify({ data: [{ b64_json: readFileSync(new URL(pool[served % pool.length], ASSETS)).toString('base64') }] }))
      return
    }
    const messages = body.messages ?? []
    const flat = m => (typeof m.content === 'string' ? m.content : (m.content ?? []).map(p => p.text ?? '').join(''))
    const system = messages.filter(m => m.role === 'system' || m.role === 'developer').map(flat).join('\n')
    const user = messages.filter(m => m.role === 'user').map(flat).join('\n')
    const text = answer(system, user)
    console.log(JSON.stringify({ url: req.url, model: body.model, stream: body.stream, systemHead: system.slice(0, 30), hasRules: system.includes('开头先给数字'), hasVoice: system.includes('<voice>') }))
    res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' })
    const base = { id: 'mock', object: 'chat.completion.chunk', created: Math.floor(Date.now() / 1000), model: body.model }
    const send = choice => res.write(`data: ${JSON.stringify({ ...base, choices: [choice] })}\n\n`)
    send({ index: 0, delta: { role: 'assistant', content: '' }, finish_reason: null })
    for (let i = 0; i < text.length; i += 12) {
      send({ index: 0, delta: { content: text.slice(i, i + 12) }, finish_reason: null })
      await new Promise(r => setTimeout(r, 70))
    }
    send({ index: 0, delta: {}, finish_reason: 'stop' })
    res.write(`data: ${JSON.stringify({ ...base, choices: [], usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 } })}\n\n`)
    res.write('data: [DONE]\n\n')
    res.end()
  })
}).listen(PORT, '127.0.0.1', () => console.log(`mock llm on ${PORT}`))
