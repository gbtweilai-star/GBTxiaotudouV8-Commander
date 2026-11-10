// 数据复盘。
import React from 'react'
import { dispatchOps, fetchInsights, learnSkills, openItem, setDesk, toast, useDesk } from './desk.js'
import { ConnectDialog } from './connect.jsx'
import { EN } from './en/index.js'
import { lang, plural, t, useLang } from './i18n.js'
import { Icon, Segmented } from './ui.jsx'
const clip = (text, n) => (text.length > n ? `${text.slice(0, n).trimEnd()}…` : text)
import { PLATFORMS, compact, platformChoices, displayItem, fmtDate, posterOf, dayKey } from './util.js'

/** 带数量的文字：英文在 1 时用单数那条 key；{s} 给共用词典里写成 piece{s} 的那种。 */
function count(n, one, other, vars = {}) {
  return t(plural(n, one, other), { n: Number(n).toLocaleString(), s: n === 1 ? '' : 's', ...vars })
}

function niceMax(value) {
  if (value <= 0) return 1
  const pow = 10 ** Math.floor(Math.log10(value))
  const step = [1, 2, 2.5, 5, 10].find(n => n * pow >= value) ?? 10
  return step * pow
}

/** 单序列折线：十字准线 + 提示框，配一份可切换的表格。 */
function TrendChart({ daily: rows, field }) {
  const daily = rows.map(row => ({ ...row, value: row[field] }))
  const [hover, setHover] = React.useState(null)
  const box = React.useRef(null)
  const [size, setSize] = React.useState({ width: 640, height: 220 })
  React.useLayoutEffect(() => {
    const el = box.current
    if (!el) return undefined
    const observer = new ResizeObserver(([entry]) => setSize({ width: entry.contentRect.width, height: Math.max(entry.contentRect.height, 140) }))
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  const { width, height } = size
  const pad = { l: 44, r: 12, t: 12, b: 26 }
  const max = niceMax(Math.max(...daily.map(d => d.value)))
  const x = i => pad.l + (i / Math.max(daily.length - 1, 1)) * (width - pad.l - pad.r)
  const y = v => pad.t + (1 - v / max) * (height - pad.t - pad.b)
  const line = daily.map((d, i) => `${i ? 'L' : 'M'} ${x(i).toFixed(1)} ${y(d.value).toFixed(1)}`).join(' ')
  const area = `${line} L ${x(daily.length - 1).toFixed(1)} ${y(0)} L ${x(0).toFixed(1)} ${y(0)} Z`
  const ticks = [0, 0.5, 1].map(t => t * max)
  const labelEvery = Math.ceil(daily.length / Math.max(Math.floor(width / 72), 2))
  const onMove = (event) => {
    const rect = event.currentTarget.getBoundingClientRect()
    const ratio = (event.clientX - rect.left - pad.l) / (width - pad.l - pad.r)
    setHover(Math.max(0, Math.min(daily.length - 1, Math.round(ratio * (daily.length - 1)))))
  }
  const point = hover === null ? null : daily[hover]
  return (
    <div className="md-chart" ref={box}>
      <svg width={width} height={height} role="img" aria-label={t(field === 'views' ? '每日播放趋势，共 {n} 天，峰值 {peak}' : '每日互动趋势，共 {n} 天，峰值 {peak}', { n: daily.length, peak: compact(Math.max(...daily.map(d => d.value))) })} onPointerMove={onMove} onPointerLeave={() => setHover(null)}>
        {ticks.map(tick => (
          <g key={tick}>
            <line x1={pad.l} x2={width - pad.r} y1={y(tick)} y2={y(tick)} className="md-chart-grid" />
            <text x={pad.l - 8} y={y(tick) + 4} textAnchor="end" className="md-chart-axis">{compact(tick)}</text>
          </g>
        ))}
        {daily.map((d, i) => (i % labelEvery === 0 ? <text key={d.date} x={x(i)} y={height - 6} textAnchor="middle" className="md-chart-axis">{Number(d.date.slice(5, 7))}/{Number(d.date.slice(8, 10))}</text> : null))}
        <path d={area} className="md-chart-area" />
        <path d={line} className="md-chart-line" pathLength="1" />
        {point ? (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={pad.t} y2={height - pad.b} className="md-chart-cross" />
            <circle cx={x(hover)} cy={y(point.value)} r="4.5" className="md-chart-dot" />
          </g>
        ) : null}
      </svg>
      {point ? (
        <div className="md-chart-tip" style={{ left: Math.min(x(hover) + 12, width - 150), top: Math.max(y(point.value) - 56, 0) }}>
          <small>{fmtDate(`${point.date}T12:00:00`)}</small>
          <b>{field === 'views' ? count(point.value, '1 播放', '{n} 播放') : count(point.value, '1 互动', '{n} 互动')}</b>
          {field === 'views' ? <small>{count(point.engaged, '1 互动', '{n} 互动')}</small> : null}
        </div>
      ) : null}
    </div>
  )
}

function addMetric(items) {
  setDesk({
    dialog: {
      title: t('录入一条数据'),
      initial: { platform: '公众号', date: dayKey(new Date()) },
      fields: [
        { name: 'itemId', label: t('对应内容'), type: 'select', options: [{ value: '', label: t('不关联内容') }, ...items.filter(i => !i.parentId).map(i => ({ value: i.id, label: displayItem(i).title.slice(0, 26) }))] },
        { name: 'platform', label: t('平台'), type: 'select', options: platformChoices().map(v => ({ value: v, label: t(v) })) },
        { name: 'date', label: t('日期'), type: 'date', required: true },
        { name: 'views', label: t('播放 / 阅读'), type: 'number', required: true },
        { name: 'likes', label: t('点赞'), type: 'number' },
        { name: 'comments', label: t('评论'), type: 'number' },
        { name: 'saves', label: t('收藏'), type: 'number' },
      ],
      onSubmit: (v) => {
        const n = key => Number(v[key]) || 0
        dispatchOps([{ op: 'add_metric', itemId: v.itemId || null, platform: v.platform, date: new Date(`${v.date}T12:00:00`).toISOString(), views: n('views'), likes: n('likes'), comments: n('comments'), saves: n('saves') }], { label: t('录入数据') })
      },
    },
  })
}

/** 平台名：中文原文，或者它的英文名（不分大小写）。 */
function platformOf(name) {
  const value = String(name ?? '').toLowerCase()
  return PLATFORMS.find(p => p.toLowerCase() === value || String(EN[p] ?? '').toLowerCase() === value)
}

/** CSV：日期,平台,阅读,点赞,评论,转发,收藏 */
export function parseCsv(text) {
  const ops = []
  const errors = []
  text.trim().split(/\r?\n/).forEach((line, index) => {
    const cols = line.split(/[,，\t]/).map(c => c.trim())
    if (index === 0 && !/\d/.test(cols[0])) return
    const date = new Date(cols[0])
    const platform = platformOf(cols[1])
    if (Number.isNaN(date.getTime()) || !platform) {
      errors.push(index + 1)
      return
    }
    const [views, likes, comments, shares, saves] = cols.slice(2).map(v => Number(v) || 0)
    ops.push({ op: 'add_metric', platform, date: date.toISOString(), views: views ?? 0, likes: likes ?? 0, comments: comments ?? 0, shares: shares ?? 0, saves: saves ?? 0 })
  })
  return { ops, errors }
}

function importCsv() {
  setDesk({
    dialog: {
      title: t('粘贴 CSV 数据'),
      submitLabel: t('导入'),
      fields: [{ name: 'csv', label: t('每行一条：日期,平台,阅读,点赞,评论,转发,收藏'), type: 'textarea', rows: 7, required: true, placeholder: t('2026-10-30,公众号,3200,120,18,40,66') }],
      onSubmit: (values) => {
        const { ops, errors } = parseCsv(values.csv ?? '')
        const done = count(ops.length, '导入 1 条数据', '导入 {n} 条数据')
        if (ops.length) dispatchOps(ops, { label: done, silent: true })
        toast(errors.length ? t('导入 {n} 条，第 {rows} 行格式不对', { n: ops.length, rows: errors.slice(0, 5).join(t('、')) }) : done, { error: errors.length > 0, undo: !errors.length && ops.length > 0 })
      },
    },
  })
}

function Metric({ label, value, unit, wide }) {
  return <div className={`md-metric ${wide ? 'is-wide' : ''}`}><dt>{label}</dt><dd>{value}{unit ? <small>{unit}</small> : null}</dd></div>
}

export function InsightsView() {
  useLang()
  const items = useDesk(s => s.state.items)
  const metrics = useDesk(s => s.state.metrics)
  const skills = useDesk(s => s.state.skills)
  const [data, setData] = React.useState(null)
  const [show, setShow] = React.useState('chart')
  const [connecting, setConnecting] = React.useState(false)
  const accounts = useDesk(s => s.state.accounts)
  React.useEffect(() => {
    let alive = true
    fetchInsights().then((next) => { if (alive) setData(next) }).catch(err => toast(err.message, { error: true }))
    return () => { alive = false }
  }, [metrics, items])
  if (!data) return <div className="md-board-page"><div className="md-tile md-i-hero" /></div>
  // 有真实数据后，不再把示例规则当建议
  const proposed = skills.filter(s => s.status === 'proposed' && (data.hasSample || !s.sample))
  // 有的平台公开接口读不到播放量，这时统一按互动来比
  const hasViews = data.views > 0
  const barKey = data.platforms.every(p => p.views > 0) ? 'views' : 'engaged'
  const maxBar = Math.max(1, ...data.platforms.map(p => p[barKey]))
  const realAccounts = accounts.some(row => row.externalId)
  const dialog = connecting ? <ConnectDialog onClose={() => setConnecting(false)} /> : null
  const best = data.top[0]
  const bestItem = best && items.find(i => i.id === best.id)
  const heroPic = bestItem && posterOf(displayItem(bestItem))
  const actions = (
    <div className="md-hero-actions">
      <button type="button" className="md-pill is-primary" onClick={() => setConnecting(true)}><Icon name="user" size={14} />{t('导入账号数据')}</button>
      <button type="button" className="md-pill" onClick={() => addMetric(items)}><Icon name="plus" size={14} />{t('录入数据')}</button>
      <button type="button" className="md-pill" onClick={importCsv}><Icon name="upload" size={14} />{t('粘贴 CSV')}</button>
    </div>
  )
  if (!metrics.length) {
    return (
      <div className="md-board-page">
        <section className="md-tile md-i-hero is-empty">
          <div className="md-hero-copy">
            <h1 className="md-i-line">{t('发布之后，把数据录进来，')}<br />{t('这里就开始替你复盘。')}</h1>
            {actions}
          </div>
        </section>
        {dialog}
      </div>
    )
  }
  return (
    <div className="md-board-page">
      <div className="md-insights">
        <section className="md-tile md-i-hero">
          <div className="md-hero-copy">
            <h1 className="md-i-line">
              <b>{count(data.published, '1 条内容', '{n} 条内容')}</b> {t('带来了')} <b>{hasViews ? t(plural(data.views, '1 次播放', '{n} 次播放'), { n: compact(data.views) }) : t(plural(data.engaged, '1 次互动', '{n} 次互动'), { n: compact(data.engaged) })}</b>{best ? t('，') : t('。')}
              {best ? <><br />{t('表现最好的是')} {heroPic ? <img className="md-inline-pic" src={heroPic} alt="" draggable={false} /> : null} <b>{clip(best.title, lang() === 'en' ? 30 : 14)}</b>{t('。')}</> : null}
            </h1>
            {actions}
          </div>
          <dl className="md-metrics">
            {hasViews ? <Metric label={t('互动率')} value={(data.engagementRate * 100).toFixed(1)} unit="%" /> : null}
            <Metric label={t('总互动')} value={compact(data.engaged)} />
            {realAccounts && data.followers ? <Metric label={t('粉丝')} value={compact(data.followers)} /> : <Metric label={lang() === 'en' ? t('平台（数量）') : '平台'} value={data.platforms.length} unit={t('个')} />}
          </dl>
          {data.hasSample ? <span className="md-i-sample">{t('示例数据')}</span> : null}
        </section>

        <section className="md-tile md-i-trend">
          <header className="md-tile-head">
            <h2>{hasViews ? t('每日播放') : t('每日互动')}</h2>
            <span className="md-grow" />
            <Segmented label={t('显示方式')} value={show} onChange={setShow} options={[{ value: 'chart', label: t('图') }, { value: 'table', label: t('表') }]} />
          </header>
          {show === 'chart' ? <div className="md-i-chart"><TrendChart daily={data.daily} field={hasViews ? 'views' : 'engaged'} /></div> : (
            <div className="md-i-table">
              <table className="md-table is-plain">
                <thead><tr><th>{t('日期')}</th>{hasViews ? <th className="is-num">{t('播放')}</th> : null}<th className="is-num">{t('互动')}</th></tr></thead>
                <tbody>{[...data.daily].reverse().map(d => <tr key={d.date}><td>{lang() === 'en' ? fmtDate(`${d.date}T12:00:00`) : d.date}</td>{hasViews ? <td className="is-num">{d.views.toLocaleString()}</td> : null}<td className="is-num">{d.engaged.toLocaleString()}</td></tr>)}</tbody>
              </table>
            </div>
          )}
        </section>

        <section className="md-tile md-i-platforms">
          <header className="md-tile-head"><h2>{t('平台分布')}</h2><span className="md-tile-meta">{barKey === 'views' ? t('播放') : t('互动')}</span></header>
          <ul className="md-bars" aria-label={barKey === 'views' ? t('各平台播放') : t('各平台互动')}>
            {data.platforms.map(platform => (
              <li key={platform.platform} title={t(platform.views ? '{platform}：{views} 播放，{likes} 赞，{saves} 收藏' : '{platform}：{likes} 赞，{saves} 收藏', { platform: t(platform.platform), views: platform.views.toLocaleString(), likes: platform.likes.toLocaleString(), saves: platform.saves.toLocaleString() })}>
                <span>{t(platform.platform)}</span>
                <b>{compact(platform[barKey])}</b>
                <span className="md-bar-track"><i style={{ width: `${(platform[barKey] / maxBar) * 100}%` }} /></span>
              </li>
            ))}
          </ul>
        </section>

        <section className="md-tile md-i-top">
          <header className="md-tile-head"><h2>{t('表现最好的内容')}</h2></header>
          <ol className="md-top">
            {data.top.slice(0, 5).map((row, index) => {
              const item = items.find(i => i.id === row.id)
              const poster = item && posterOf(displayItem(item))
              return (
                <li key={row.id}>
                  <button type="button" onClick={() => openItem(row.id)}>
                    <span className="md-top-rank">{index + 1}</span>
                    <span className="md-thumb">{poster ? <img src={poster} alt="" loading="lazy" /> : null}</span>
                    <span className="md-top-title"><strong>{row.title}</strong><small>{t(row.platform)} · {t('{likes} 赞 · {saves} 收藏', { likes: compact(row.likes), saves: compact(row.saves) })}</small></span>
                    <b>{row.views ? compact(row.views) : t(plural(row.engaged, '1 互动', '{n} 互动'), { n: compact(row.engaged) })}</b>
                  </button>
                </li>
              )
            })}
          </ol>
        </section>

        <section className="md-tile md-i-advice">
          <header className="md-tile-head">
            <h2>{t('给你的建议')}</h2>
            <span className="md-grow" />
            <button type="button" className="md-pill is-small" onClick={learnSkills}><Icon name="spark" size={13} />{t('重新分析')}</button>
          </header>
          <div className="md-i-advice-list">
            {proposed.length ? proposed.slice(0, 4).map(skill => (
              <div key={skill.id} className="md-i-tip">
                <strong>{skill.name}</strong>
                <p>{skill.evidence ?? skill.rule}</p>
                <button type="button" className="md-pill is-small" onClick={() => dispatchOps([{ op: 'update_skill', id: skill.id, status: 'active' }], { label: t('启用规则「{name}」', { name: skill.name }) })}>{t('写进规则')}</button>
              </div>
            )) : <p className="md-muted">{t('点「重新分析」，从现有数据里找出值得坚持的做法。')}</p>}
          </div>
        </section>
      </div>
      {dialog}
    </div>
  )
}
