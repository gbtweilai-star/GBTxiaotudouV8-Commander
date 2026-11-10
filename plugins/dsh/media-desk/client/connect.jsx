// 抓账号：先引导用户接好 Monid，再贴主页链接。
import React from 'react'
import { importAccount, monidStatus, toast, useDesk } from './desk.js'
import { t, useLang } from './i18n.js'
import { Dialog, Icon } from './ui.jsx'

const SETUP_LINE = 'set up https://monid.ai/SKILL.md'
// 命令里的占位词要跟着语言走，用的时候再翻译
const KEY_COMMAND = 'monid keys add -k 你的密钥 -l main'
const KEYS_URL = 'https://app.monid.ai/access/api-keys'

/** 花费是按 Monid 目录价估的，实际花费以导入结果为准。 */
function detect(text) {
  const value = String(text ?? '')
  if (/xiaohongshu\.com|xhslink\.com/i.test(value)) return { platform: '小红书', estimate: '$0.02' }
  if (/douyin\.com/i.test(value)) return { platform: '抖音', estimate: '$0.002' }
  if (/bilibili\.com|b23\.tv/i.test(value)) return { platform: 'B站', estimate: '$0.003' }
  if (/tiktok\.com/i.test(value)) return { platform: 'TikTok', estimate: '$0.002' }
  if (/instagram\.com/i.test(value)) return { platform: 'Instagram', estimate: '$0.002' }
  if (/(?:^|[/.])(?:x|twitter)\.com/i.test(value)) return { platform: 'X', estimate: '$0.001' }
  return null
}

function CopyLine({ value, label }) {
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      toast(t('已复制'))
    } catch (err) {
      toast(t('复制失败：{error}', { error: err.message }), { error: true })
    }
  }
  return (
    <div className="md-copy-line">
      <code>{value}</code>
      <button type="button" className="md-pill is-small" aria-label={label} onClick={copy}><Icon name="copy" size={13} />{t('复制')}</button>
    </div>
  )
}

function SetupGuide({ status, checking, onCheck }) {
  return (
    <div className="md-setup">
      <p className="md-setup-lead">{t('小红书、抖音、B 站、TikTok、Instagram 和 X 的数据要通过 Monid 读取。它是第三方数据服务，按次收费，一个账号大约几分钱。')}</p>
      <ol>
        <li>
          <strong>{t('把这句话发给 DeepSeek Harness 的新会话')}</strong>
          <span>{t('它会帮你装好 Monid。')}</span>
          <CopyLine value={SETUP_LINE} label={t('复制安装指令')} />
        </li>
        <li>
          <strong>{t('注册 Monid，创建一个密钥')}</strong>
          <span>{t('余额不够的话要先充值。')}</span>
          <a href={KEYS_URL} target="_blank" rel="noreferrer">app.monid.ai/access/api-keys</a>
        </li>
        <li>
          <strong>{t('在终端里保存密钥')}</strong>
          <span>{t('密钥不要发在聊天里。')}</span>
          <CopyLine value={t(KEY_COMMAND)} label={t('复制保存密钥的命令')} />
        </li>
      </ol>
      {status?.state === 'nokey' ? <p className="md-setup-note">{t('Monid 已经装好，还差第 3 步的密钥。')}</p> : null}
      {status?.state === 'error' ? <p className="md-setup-note is-error">{status.message}</p> : null}
      <button type="button" className="md-btn is-primary md-setup-check" onClick={onCheck} disabled={checking}>{checking ? <span className="md-shimmer">{t('正在检查…')}</span> : t('我装好了，检查一下')}</button>
    </div>
  )
}

function AccountForm({ status, onClose }) {
  const accounts = useDesk(s => s.state.accounts)
  const [text, setText] = React.useState('')
  const [busy, setBusy] = React.useState(false)
  const found = detect(text)
  const saved = accounts.filter(row => row.externalId && row.url)
  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    const ok = await importAccount({ text })
    setBusy(false)
    if (ok) onClose()
  }
  return (
    <form className="md-form" onSubmit={submit}>
      <label className="md-field">
        <span>{t('你的账号主页链接')}</span>
        <textarea rows={3} required value={text} onChange={e => setText(e.target.value)} placeholder={t('小红书、抖音、B 站、TikTok、Instagram 或 X 的主页链接，App 分享出来的文字也可以')} />
        <small>{t('请只抓自己的账号。会读取最近 20 条公开内容和互动数据，放进内容和复盘，并提炼成你的风格。')}</small>
      </label>
      {saved.length ? (
        <div className="md-saved-accounts">
          {saved.map(row => <button type="button" key={row.id} className="md-pill is-small" onClick={() => setText(row.url)}><Icon name="refresh" size={12} />{t(row.platform)} · {row.handle}</button>)}
        </div>
      ) : null}
      <p className="md-setup-foot">
        {t('链接会发给 Monid 和它的数据服务商。只能读到公开内容，后台才有的数据（如小红书和抖音的播放量）读不到。')}
      </p>
      <div className="md-form-foot">
        <span className="md-monid-balance">{status.balance ? t('Monid 余额 ${value}', { value: status.balance.value.toFixed(2) }) : t('Monid 已连接')}</span>
        <span style={{ flex: 1 }} />
        <button type="button" className="md-btn" onClick={onClose}>{t('取消')}</button>
        <button type="submit" className="md-btn is-primary" disabled={busy}>
          {busy ? <span className="md-shimmer">{t('正在导入和提炼…')}</span> : found ? t('导入{platform}（约 {estimate}）', { platform: t(found.platform), estimate: found.estimate }) : t('导入')}
        </button>
      </div>
    </form>
  )
}

export function ConnectDialog({ onClose }) {
  useLang()
  const [status, setStatus] = React.useState(null)
  const [checking, setChecking] = React.useState(true)
  const check = React.useCallback(async () => {
    setChecking(true)
    const next = await monidStatus()
    setStatus(next)
    setChecking(false)
    if (next.state === 'missing') toast(t('还没找到 Monid，先完成第 1 步'), { error: false })
  }, [])
  React.useEffect(() => {
    let alive = true
    monidStatus().then((next) => {
      if (!alive) return
      setStatus(next)
      setChecking(false)
    })
    return () => { alive = false }
  }, [])
  const ready = status?.state === 'ready'
  return (
    <Dialog title={ready ? t('导入我的账号') : t('连接 Monid')} onClose={onClose} width={500}>
      {!status ? <p className="md-setup-lead md-shimmer">{t('正在检查 Monid…')}</p> : null}
      {status && !ready ? <SetupGuide status={status} checking={checking} onCheck={check} /> : null}
      {ready ? <AccountForm status={status} onClose={onClose} /> : null}
    </Dialog>
  )
}
