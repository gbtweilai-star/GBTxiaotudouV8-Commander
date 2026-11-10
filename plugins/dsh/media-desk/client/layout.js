// 散落布局。始终基于全部根卡片计算，筛选和新增内容都不会让整面墙重新洗牌。
import { displayItem, hash, seeded } from './util.js'

export const HERO = { w: 540, h: 372 }

export function cardSize(raw) {
  const item = displayItem(raw)
  const h = hash(item.id)
  if (item.media && ['image', 'video', 'web'].includes(item.kind)) {
    const width = 176 + (h % 5) * 20
    const ratio = item.media.h && item.media.w ? item.media.h / item.media.w : 0.75
    return { w: width, h: width * ratio + 66 }
  }
  if (item.kind === 'quote') return { w: 220 + (h % 3) * 20, h: 186 }
  return { w: 232, h: 186 }
}

/** 螺旋撒点，再迭代推开重叠的卡片。中间留给首屏那句话，手动摆放过的卡片不动。 */
export function scatterLayout(items) {
  const ordered = [...items].sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt) || a.id.localeCompare(b.id))
  const rand = seeded(7919)
  const nodes = ordered.map((item, index) => {
    const angle = index * 2.39996 + rand() * 0.5
    const radius = 210 + 112 * Math.sqrt(index + 1)
    const size = cardSize(item)
    const jitter = (rand() - 0.5) * 7
    return { id: item.id, x: item.pos?.x ?? Math.cos(angle) * radius * 1.34, y: item.pos?.y ?? Math.sin(angle) * radius * 0.86, w: size.w, h: size.h, fixed: Boolean(item.pos), r: item.pos?.r ?? jitter }
  })
  const gap = 20
  for (let step = 0; step < 240; step += 1) {
    let moved = false
    for (let i = 0; i < nodes.length; i += 1) {
      const a = nodes[i]
      const hx = (a.w + HERO.w) / 2 + gap - Math.abs(a.x)
      const hy = (a.h + HERO.h) / 2 + gap - Math.abs(a.y)
      if (hx > 0 && hy > 0 && !a.fixed) {
        if (hx < hy) a.x += Math.sign(a.x || 1) * hx
        else a.y += Math.sign(a.y || 1) * hy
        moved = true
      }
      for (let j = i + 1; j < nodes.length; j += 1) {
        const b = nodes[j]
        if (a.fixed && b.fixed) continue
        const ox = (a.w + b.w) / 2 + gap - Math.abs(a.x - b.x)
        const oy = (a.h + b.h) / 2 + gap - Math.abs(a.y - b.y)
        if (ox <= 0 || oy <= 0) continue
        moved = true
        const horizontal = ox < oy
        const push = (horizontal ? ox : oy) / 2
        const dir = horizontal ? Math.sign(a.x - b.x || 1) : Math.sign(a.y - b.y || 1)
        const shareA = b.fixed ? 2 : a.fixed ? 0 : 1
        const shareB = a.fixed ? 2 : b.fixed ? 0 : 1
        if (horizontal) {
          a.x += dir * push * shareA
          b.x -= dir * push * shareB
        } else {
          a.y += dir * push * shareA
          b.y -= dir * push * shareB
        }
      }
    }
    if (!moved) break
  }
  return Object.fromEntries(nodes.map(n => [n.id, { x: Math.round(n.x), y: Math.round(n.y), r: n.r, d: n.fixed ? 0 : (hash(n.id) % 13 - 6) / 100 }]))
}
