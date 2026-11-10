import { EN } from './en/index.js'
import { lang, t } from './i18n.js'

// 这些表只放中文原文，显示时再用 t() 翻译
export const STATUSES = ['idea', 'outline', 'draft', 'ready', 'published']
export const STATUS_LABEL = { idea: '灵感', outline: '大纲', draft: '草稿', ready: '待发布', published: '已发布' }
export const KIND_LABEL = { image: '图片', video: '视频', web: '网页', quote: '金句', note: '笔记' }
export const PLATFORMS = ['公众号', '小红书', '抖音', 'B站', '视频号', 'TikTok', 'Instagram', 'YouTube', 'X']
const OVERSEAS = new Set(['TikTok', 'Instagram', 'YouTube', 'X'])
/** 下拉框里的平台顺序：英文界面把海外平台放前面。 */
export function platformChoices() {
  return lang() === 'en' ? [...PLATFORMS.filter(p => OVERSEAS.has(p)), ...PLATFORMS.filter(p => !OVERSEAS.has(p))] : PLATFORMS
}
export const STYLE_CATEGORIES = ['科技数码', '旅行探店', 'Vlog 生活', '观点认知', '干货教程', '种草测评', '情感故事', '热点资讯']

export function styleIcon(style) {
  return style?.icon || '✍️'
}
export const PLATFORM_URL = {
  公众号: 'https://mp.weixin.qq.com/', 小红书: 'https://creator.xiaohongshu.com/publish/publish', 抖音: 'https://creator.douyin.com/creator-micro/content/upload',
  B站: 'https://member.bilibili.com/platform/upload/video/frame', 视频号: 'https://channels.weixin.qq.com/platform/post/create', TikTok: 'https://www.tiktok.com/tiktokstudio/upload', Instagram: 'https://www.instagram.com/', YouTube: 'https://studio.youtube.com/', X: 'https://x.com/compose/post',
}

export function hash(text) {
  let h = 2166136261
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

export function seeded(seed) {
  let s = seed || 1
  return () => {
    s = Math.imul(s ^ (s >>> 15), 2246822507)
    s = Math.imul(s ^ (s >>> 13), 3266489909)
    s ^= s >>> 16
    return (s >>> 0) / 4294967296
  }
}

export const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** 把弹簧响应采样成 CSS linear() 缓动，WAAPI 和 CSS 都能用。 */
export function springEasing(stiffness = 170, damping = 20, mass = 1) {
  const w0 = Math.sqrt(stiffness / mass)
  const zeta = damping / (2 * Math.sqrt(stiffness * mass))
  const wd = w0 * Math.sqrt(Math.max(1 - zeta * zeta, 1e-4))
  const at = t => 1 - Math.exp(-zeta * w0 * t) * (Math.cos(wd * t) + ((zeta * w0) / wd) * Math.sin(wd * t))
  let duration = 0.1
  while (duration < 4 && (Math.abs(at(duration) - 1) > 0.002 || Math.abs(at(duration + 0.05) - 1) > 0.002)) duration += 0.05
  const points = []
  const N = 36
  for (let i = 0; i <= N; i += 1) points.push(Number(at((i / N) * duration).toFixed(4)))
  points[N] = 1
  return { easing: `linear(${points.join(',')})`, duration: Math.round(duration * 1000) }
}

export const SPRING_SOFT = springEasing(120, 16)
export const SPRING_SNAP = springEasing(260, 24)

export function dayKey(date) {
  const d = new Date(date)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function pad(n) {
  return String(n).padStart(2, '0')
}

export function fmtTime(iso) {
  const d = new Date(iso)
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const MONTHS_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function fmtDate(iso) {
  const d = new Date(iso)
  if (lang() === 'en') return `${MONTHS_SHORT[d.getMonth()]} ${d.getDate()}`
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

export function fmtWhen(iso) {
  if (!iso) return t('未排期')
  return `${fmtDate(iso)} ${fmtTime(iso)}`
}

export function relativeDay(iso) {
  const diff = Math.round((new Date(dayKey(iso)) - new Date(dayKey(new Date()))) / 86400000)
  if (diff === 0) return t('今天')
  if (diff === 1) return t('明天')
  if (diff === 2) return t('后天')
  if (diff === -1) return t('昨天')
  if (diff < 0 && diff > -8) return t('{n}天前', { n: -diff })
  return fmtDate(iso)
}

export function toLocalInput(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function compact(n) {
  if (n === null || n === undefined) return '—'
  if (lang() === 'en') {
    // 英文用 K / M，去掉多余的 .0
    const short = (value, suffix) => `${value.toFixed(value >= 100 ? 0 : 1).replace(/\.0$/, '')}${suffix}`
    if (n >= 999500) return short(n / 1000000, 'M')
    if (n >= 10000) return short(n / 1000, 'K')
    return n.toLocaleString('en-US')
  }
  if (n >= 10000) return `${(n / 10000).toFixed(n >= 100000 ? 0 : 1)}万`
  return n.toLocaleString()
}

/** 数量后面的单位。英文在 n 为 1 时用单数，词典里 key 写成「单位|1」。 */
export function unit(n, zh) {
  if (lang() === 'en' && n === 1 && EN[`${zh}|1`] !== undefined) return EN[`${zh}|1`]
  return t(zh)
}

/** 连续记录天数：今天还没记时，从昨天往回算，不会让今天一早就断掉。 */
/** 灵感墙和邮票只放自己记下的灵感，从账号导入的已发内容不算。 */
export function isIdea(item) {
  return !item.parentId && !item.imported
}

export function computeStreak(items, now = new Date()) {
  const days = new Set(items.filter(isIdea).map(i => dayKey(i.createdAt)))
  const cursor = new Date(now)
  if (!days.has(dayKey(cursor))) cursor.setDate(cursor.getDate() - 1)
  let streak = 0
  while (days.has(dayKey(cursor))) {
    streak += 1
    cursor.setDate(cursor.getDate() - 1)
  }
  return streak
}

/** 成稿之后，卡片显示封面和最终标题。 */
export function displayItem(item) {
  const production = item.production
  if (!production?.title || production.status === 'running') return item
  const src = production.cover?.src
  return { ...item, title: production.title, ...(src ? { kind: 'image', media: { src, w: 3, h: 2 } } : {}) }
}

export function posterOf(item) {
  if (!item.media) return null
  return item.media.poster || (item.kind === 'video' ? null : item.media.src)
}

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]))
}

function inline(text) {
  return escapeHtml(text)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
}

/** 草稿预览用的极简 Markdown：先转义，再处理结构，模型输出里的 HTML 不会被执行。 */
export function renderMarkdown(source) {
  const lines = source.split('\n')
  const out = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (/^\s*$/.test(line)) { i += 1; continue }
    const heading = /^(#{1,4})\s+(.*)$/.exec(line)
    if (heading) { out.push(`<h${heading[1].length}>${inline(heading[2])}</h${heading[1].length}>`); i += 1; continue }
    if (/^>\s?/.test(line)) {
      const quote = []
      while (i < lines.length && /^>\s?/.test(lines[i])) { quote.push(inline(lines[i].replace(/^>\s?/, ''))); i += 1 }
      out.push(`<blockquote>${quote.join('<br>')}</blockquote>`)
      continue
    }
    if (/^\|.*\|\s*$/.test(line) && /^\|[\s:|-]+\|\s*$/.test(lines[i + 1] || '')) {
      const cells = row => row.trim().replace(/^\||\|$/g, '').split('|').map(c => inline(c.trim()))
      const head = cells(line)
      i += 2
      const body = []
      while (i < lines.length && /^\|.*\|\s*$/.test(lines[i])) { body.push(cells(lines[i])); i += 1 }
      out.push(`<table><thead><tr>${head.map(c => `<th>${c}</th>`).join('')}</tr></thead><tbody>${body.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table>`)
      continue
    }
    if (/^\s*([-*·]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line)
      const rows = []
      while (i < lines.length && /^\s*([-*·]|\d+\.)\s+/.test(lines[i])) { rows.push(`<li>${inline(lines[i].replace(/^\s*([-*·]|\d+\.)\s+/, ''))}</li>`); i += 1 }
      out.push(ordered ? `<ol>${rows.join('')}</ol>` : `<ul>${rows.join('')}</ul>`)
      continue
    }
    const para = []
    while (i < lines.length && !/^\s*$/.test(lines[i]) && !/^(#{1,4}\s|>|\|)/.test(lines[i]) && !/^\s*([-*·]|\d+\.)\s+/.test(lines[i])) { para.push(inline(lines[i])); i += 1 }
    if (para.length) out.push(`<p>${para.join('<br>')}</p>`)
    else { out.push(`<p>${inline(line)}</p>`); i += 1 }
  }
  return out.join('')
}

/** 正文长度：中文按字数（不算空白），英文按词数，中文字在英文里各算一个。 */
export function textLength(text) {
  if (lang() !== 'en') return text.replace(/\s/g, '').length
  return (text.match(/[\u4e00-\u9fff]|[A-Za-z0-9][A-Za-z0-9'’-]*/g) || []).length
}

