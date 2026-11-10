// 助手模型选择：顶栏按钮 + 弹窗。不指定时跟随 DeepSeek Harness 默认模型。
import React from 'react'
import { fetchModels, saveAssistant, setDesk, useDesk } from './desk.js'
import { t } from './i18n.js'
import { Dialog, Icon } from './ui.jsx'

export function ModelButton() {
  const model = useDesk(s => s.model)
  const override = useDesk(s => s.settings?.assistant?.model)
  return (
    <button type="button" className="md-open-dock" title={t('助手模型')} onClick={() => setDesk({ modelPickOpen: true })}>
      <Icon name="spark" size={13} />{override || model || t('助手模型')}
    </button>
  )
}

export function ModelPicker() {
  const open = useDesk(s => s.modelPickOpen)
  const override = useDesk(s => s.settings?.assistant)
  const [data, setData] = React.useState(null)
  const [busy, setBusy] = React.useState(false)
  React.useEffect(() => {
    if (!open) return
    setData(null)
    fetchModels().then(setData).catch(() => setData({ providers: [], default: null }))
  }, [open])
  if (!open) return null
  const close = () => setDesk({ modelPickOpen: false })
  const pick = async (provider, model) => {
    setBusy(true)
    if (await saveAssistant({ provider, model })) close()
    setBusy(false)
  }
  const isCurrent = (provider, model) => override?.provider === provider && override?.model === model
  return (
    <Dialog title={t('助手模型')} onClose={close} width={480}>
      <div className="md-form">
        <div className="md-field">
          <div className="md-presets">
            <button type="button" disabled={busy} className={!override?.model ? 'is-on' : ''} onClick={() => pick('', '')}>
              {t('跟随默认')}{data?.default?.model ? `（${data.default.model}）` : ''}
            </button>
          </div>
          <small>{t('不指定时，助手跟随 DeepSeek Harness 的默认模型。')}</small>
        </div>
        {!data ? <p className="md-muted"><span className="md-shimmer">{t('正在读取可用模型…')}</span></p> : null}
        {(data?.providers ?? []).map(p => (
          <div className="md-field" key={p.provider}>
            <span>{p.name}</span>
            <div className="md-presets">
              {p.models.map(m => (
                <button type="button" key={m.id} disabled={busy} className={isCurrent(p.provider, m.id) ? 'is-on' : ''} onClick={() => pick(p.provider, m.id)}>{m.name}</button>
              ))}
            </div>
          </div>
        ))}
        {data && !data.providers.length ? <p className="md-muted">{t('还没有已接入的模型提供方。')}</p> : null}
      </div>
    </Dialog>
  )
}
