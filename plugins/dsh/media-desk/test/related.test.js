import assert from 'node:assert/strict'
import test from 'node:test'
import { relatedIdeas, relatedLayout, terms } from '../client/related.js'

const items = [
  { id: 'a', title: 'Agents vs. chatbots, explained', tags: ['AI'], createdAt: '2026-11-01' },
  { id: 'b', title: 'A pricing map', body: 'Forty pages, and one agent that read them all.', createdAt: '2026-11-02' },
  { id: 'c', title: 'Old facades', body: 'Again and again the windows change.', createdAt: '2026-11-03' },
  { id: 'd', title: '30 秒看懂 Agent 和聊天机器人的区别', createdAt: '2026-10-30' },
  { id: 'e', title: '一人公司第 300 天', body: '收入曲线和那个差点放弃的下午。', createdAt: '2026-10-29' },
  { id: 'f', title: '这周只做一件事', body: '把灵感到成稿缩短到 24 小时', production: { title: '一人公司怎么定价' }, createdAt: '2026-10-28' },
]

test('relatedIdeas：标题命中排在正文命中前面，英文按整词匹配', () => {
  assert.deepEqual(relatedIdeas(items, 'agent'), ['a', 'd', 'b'])
  assert.deepEqual(relatedIdeas(items, 'agents'), ['a'])
  assert.deepEqual(relatedIdeas(items, 'ai'), ['a'])
  assert.deepEqual(relatedIdeas(items, 'the'), [])
})

test('relatedIdeas：中文按整段和两字片段，成稿标题也算，常用虚词不算', () => {
  assert.deepEqual(relatedIdeas(items, '一人公司'), ['e', 'f'])
  assert.deepEqual(relatedIdeas(items, '怎么办'), [])
  assert.ok(terms('AI 产品怎么定价').some(row => row.term === 'ai'))
  assert.ok(!terms('AI 产品怎么定价').some(row => row.term === '怎么'))
})

test('relatedLayout：左右交替排成列，同一侧不重叠，太高就往外开一列', () => {
  const cards = Array.from({ length: 6 }, (_, i) => ({ id: `c${i}`, w: 220, h: 300 }))
  const spots = relatedLayout(cards)
  assert.ok(spots.c0.x < 0 && spots.c1.x > 0)
  const left = ['c0', 'c2', 'c4'].map(id => spots[id])
  for (const a of left) for (const b of left) if (a !== b && a.x === b.x) assert.ok(Math.abs(a.y - b.y) >= 300)
  assert.ok(new Set(left.map(p => p.x)).size === 2)
})
