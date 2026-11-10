// 通用小组件：图标、按钮、对话框、提示。
import React from 'react'
import { setDesk, undo, useDesk } from './desk.js'
import { t } from './i18n.js'

const PATHS = {
  plus: 'M12 5v14M5 12h14',
  close: 'M6 6l12 12M18 6L6 18',
  send: 'M12 19V5M6 11l6-6 6 6',
  check: 'M5 12.5l4.5 4.5L19 7',
  chevL: 'M14.5 5.5L8 12l6.5 6.5',
  chevR: 'M9.5 5.5L16 12l-6.5 6.5',
  chevD: 'M6 9.5l6 6 6-6',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4',
  chat: 'M5 6.5A2.5 2.5 0 0 1 7.5 4h9A2.5 2.5 0 0 1 19 6.5v7a2.5 2.5 0 0 1-2.5 2.5H11l-4 4v-4h0A2.5 2.5 0 0 1 5 13.5z',
  scatter: 'M4 5h6v7H4zM13 4h7v5h-7zM6 15h5v5H6zM14 12h6v8h-6z',
  wall: 'M4 4h7v10H4zM13 4h7v6h-7zM4 16h7v4H4zM13 12h7v8h-7z',
  list: 'M4 6h16M4 12h16M4 18h16',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM5 20c.8-3.4 3.6-5.5 7-5.5s6.2 2.1 7 5.5',
  spark: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z',
  pen: 'M4 20l1-4L16 5l3 3L8 19zM14 7l3 3',
  film: 'M4 5h16v14H4zM8 5v14M16 5v14M4 9.5h4M4 14.5h4M16 9.5h4M16 14.5h4',
  branch: 'M6 4v8a4 4 0 0 0 4 4h6M6 4a2 2 0 1 0 0 .01M18 16a2 2 0 1 0 0 .01M6 12a4 4 0 0 1 4-4h6M18 8a2 2 0 1 0 0 .01',
  trash: 'M5 7h14M10 7V5h4v2M7 7l1 13h8l1-13',
  pin: 'M9 4h6l-1 6 3 3v2H7v-2l3-3zM12 15v5',
  link: 'M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1',
  copy: 'M9 9h10v11H9zM5 15V4h10',
  upload: 'M12 16V5M7 10l5-5 5 5M5 19h14',
  calendar: 'M5 6h14v14H5zM5 10h14M9 3.5v4M15 3.5v4',
  zoomIn: 'M12 6v12M6 12h12',
  zoomOut: 'M6 12h12',
  target: 'M12 4v3M12 17v3M4 12h3M17 12h3M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z',
  play: 'M8 5.5v13l11-6.5z',
  undo: 'M8 6L4 10l4 4M4 10h10a5 5 0 0 1 0 10h-3',
  bolt: 'M13 3L5 14h6l-1 7 8-11h-6z',
  refresh: 'M19 8a8 8 0 0 0-14-1L4 9M5 16a8 8 0 0 0 14 1l1-2M4 4v5h5M20 20v-5h-5',
  edit: 'M4 20l1-4L16 5l3 3L8 19z',
  eye: 'M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12zM12 9.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z',
  upRight: 'M7 17L17 7M8 7h9v9',
  image: 'M4 5h16v14H4zM4 16l5-4.5 4 3.5 3-2.5 4 3.5M15.5 9.5a1 1 0 1 0 0 .01',
  clock: 'M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16zM12 8v4l3 2',
  expand: 'M14 5h5v5M10 19H5v-5M19 5l-6 6M5 19l6-6',
  save: 'M12 4v11M7 11l5 5 5-5M5 20h14',
  folder: 'M4 7h6l2 2h10v10H4z',
  more: 'M5 12h.01M12 12h.01M19 12h.01',
  // 带齿的齿轮。原来的圆加八条短线看起来像太阳，会被当成切换深浅色的按钮
  gear: 'M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
}

export function Icon({ name, size = 16, fill = false, stroke = 1.6 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={fill ? 'currentColor' : 'none'} stroke={fill ? 'none' : 'currentColor'} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  )
}

export function IconButton({ icon, label, onClick, active, tone, size = 16, className = '', ...rest }) {
  return (
    <button type="button" className={`md-icon-btn ${active ? 'is-active' : ''} ${tone ? `is-${tone}` : ''} ${className}`} aria-label={label} title={label} onClick={onClick} {...rest}>
      <Icon name={icon} size={size} />
    </button>
  )
}

export function Segmented({ value, options, onChange, label }) {
  return (
    <div className="md-seg" role="radiogroup" aria-label={label}>
      {options.map(option => (
        <button key={option.value} type="button" role="radio" aria-checked={value === option.value} className={value === option.value ? 'is-on' : ''} onClick={() => onChange(option.value)} title={option.title ?? option.label}>
          {option.icon ? <Icon name={option.icon} size={15} /> : null}
          {option.label ? <span>{option.label}</span> : null}
        </button>
      ))}
    </div>
  )
}

export function Dialog({ title, onClose, children, width = 440 }) {
  const ref = React.useRef(null)
  // onClose 每次渲染都可能是新函数；放进 ref，免得每打一个字焦点就被抢走
  const close = React.useRef(onClose)
  close.current = onClose
  React.useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        close.current()
      }
    }
    window.addEventListener('keydown', onKey, true)
    const body = ref.current
    ;(body?.querySelector('.md-dialog-head ~ * input, .md-dialog-head ~ * textarea, .md-dialog-head ~ * select') ?? body?.querySelector('.md-dialog-head ~ * button'))?.focus()
    return () => window.removeEventListener('keydown', onKey, true)
  }, [])
  return (
    <div className="md-dialog-mask" onPointerDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <div className="md-dialog" role="dialog" aria-modal="true" aria-label={title} style={{ width }} ref={ref}>
        <div className="md-dialog-head">
          <h2>{title}</h2>
          <IconButton icon="close" label={t('关闭')} onClick={onClose} />
        </div>
        {children}
      </div>
    </div>
  )
}

/** 字段驱动的通用编辑框，风格、规则和数据都用它。 */
export function FormDialog() {
  const dialog = useDesk(s => s.dialog)
  const [values, setValues] = React.useState({})
  React.useEffect(() => {
    if (dialog) setValues(dialog.initial ?? {})
  }, [dialog])
  if (!dialog) return null
  const close = () => setDesk({ dialog: null })
  const submit = (event) => {
    event.preventDefault()
    dialog.onSubmit(values)
    close()
  }
  return (
    <Dialog title={dialog.title} onClose={close}>
      <form onSubmit={submit} className="md-form">
        {dialog.fields.map(field => (
          field.type === 'hidden' ? <p key={field.name} className="md-muted">{field.label}</p> : <label key={field.name} className="md-field">
            <span>{field.label}</span>
            {field.type === 'textarea' ? (
              <textarea rows={field.rows ?? 3} value={values[field.name] ?? ''} placeholder={field.placeholder} required={field.required} onChange={e => setValues(v => ({ ...v, [field.name]: e.target.value }))} />
            ) : field.type === 'select' ? (
              <select value={values[field.name] ?? ''} required={field.required} onChange={e => setValues(v => ({ ...v, [field.name]: e.target.value }))}>
                {field.options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            ) : (
              <input type={field.type ?? 'text'} value={values[field.name] ?? ''} placeholder={field.placeholder} required={field.required} onChange={e => setValues(v => ({ ...v, [field.name]: e.target.value }))} />
            )}
            {field.hint ? <small>{field.hint}</small> : null}
          </label>
        ))}
        <div className="md-form-foot">
          {dialog.onDelete ? <button type="button" className="md-btn is-danger" onClick={() => { dialog.onDelete(); close() }}>{t('删除')}</button> : null}
          <span style={{ flex: 1 }} />
          <button type="button" className="md-btn" onClick={close}>{t('取消')}</button>
          <button type="submit" className="md-btn is-primary">{dialog.submitLabel ?? t('保存')}</button>
        </div>
      </form>
    </Dialog>
  )
}

export function Toast() {
  const toast = useDesk(s => s.toast)
  if (!toast) return null
  return (
    <div key={toast.key} className={`md-toast ${toast.error ? 'is-error' : ''}`} role={toast.error ? 'alert' : 'status'}>
      {toast.undo ? <Icon name="check" size={14} /> : null}
      <span>{toast.text}</span>
      {toast.undo ? <button type="button" onClick={undo}>{t('撤销')}</button> : null}
    </div>
  )
}

export function Empty({ title, hint, action }) {
  return (
    <div className="md-empty">
      <p className="md-empty-title">{title}</p>
      {hint ? <p>{hint}</p> : null}
      {action}
    </div>
  )
}
