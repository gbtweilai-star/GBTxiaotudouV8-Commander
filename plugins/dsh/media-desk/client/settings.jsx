// 设置：开放接入的生图模型和保存位置。
import React from 'react'
import { saveSettings, setDesk, testImage, useDesk } from './desk.js'
import { t, useLang } from './i18n.js'
import { Dialog, Icon } from './ui.jsx'

// 常见服务的 OpenAI 兼容地址，模型名以各家文档为准。label 是中文原文，显示时再翻译
const PRESETS = [
  { id: 'openai', label: 'OpenAI', baseUrl: 'https://api.openai.com/v1', model: 'gpt-image-1', size: '1536x1024', quality: 'medium', extra: '' },
  { id: 'xai', label: 'xAI', baseUrl: 'https://api.x.ai/v1', model: 'grok-2-image', size: '', quality: '', extra: '' },
  { id: 'ark', label: '火山方舟', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3', model: '', size: '1024x1024', quality: '', extra: '' },
  { id: 'zhipu', label: '智谱', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', model: 'cogview-4', size: '1024x1024', quality: '', extra: '' },
  { id: 'silicon', label: '硅基流动', baseUrl: 'https://api.siliconflow.cn/v1', model: '', size: '', quality: '', extra: '{"image_size":"1024x1024"}' },
  { id: 'custom', label: '其他自定义', baseUrl: '', model: '', size: '1024x1024', quality: '', extra: '' },
]

// 中文和 English 各用自己的语言写，切错了也认得出来
const LANGUAGES = [
  { value: 'auto', label: () => t('跟随 DeepSeek Harness') },
  { value: 'zh', label: () => '中文' },
  { value: 'en', label: () => 'English' },
]

export function SettingsDialog() {
  useLang()
  const open = useDesk(s => s.settingsOpen)
  const settings = useDesk(s => s.settings)
  const [form, setForm] = React.useState(null)
  const [testing, setTesting] = React.useState(false)
  const [sample, setSample] = React.useState(null)
  const [advanced, setAdvanced] = React.useState(false)
  React.useEffect(() => {
    if (!open || !settings) return
    const { image } = settings
    setForm({ source: image.source ?? 'http', language: settings.language ?? 'auto', baseUrl: image.baseUrl, model: image.model, apiKey: '', size: image.size, quality: image.quality, toolSize: image.toolSize ?? '1536x1024', toolQuality: image.toolQuality ?? '', extra: image.extra, exportDir: settings.exportDir ?? '', imageCount: settings.imageCount, shotCount: settings.shotCount })
    setSample(null)
  }, [open, settings])
  if (!open || !form) return null
  const close = () => setDesk({ settingsOpen: false })
  const set = (key, value) => setForm(f => ({ ...f, [key]: value }))
  const payload = () => ({
    language: form.language,
    image: { source: form.source, baseUrl: form.baseUrl, model: form.model, apiKey: form.apiKey, size: form.size, quality: form.quality, toolSize: form.toolSize, toolQuality: form.toolQuality, extra: form.extra },
    exportDir: form.exportDir, imageCount: Number(form.imageCount), shotCount: Number(form.shotCount),
  })
  const activePreset = PRESETS.find(p => p.baseUrl && p.baseUrl === form.baseUrl)?.id ?? (form.baseUrl ? 'custom' : null)
  return (
    <Dialog title={t('设置')} onClose={close} width={520}>
      <form className="md-form" onSubmit={async (event) => {
        event.preventDefault()
        if (await saveSettings(payload())) close()
      }}>
        <div className="md-field">
          <span>{t('语言')}</span>
          <div className="md-presets" role="radiogroup" aria-label={t('语言')}>
            {LANGUAGES.map(option => (
              <button type="button" key={option.value} role="radio" aria-checked={form.language === option.value} className={form.language === option.value ? 'is-on' : ''} onClick={() => set('language', option.value)}>{option.label()}</button>
            ))}
          </div>
        </div>
        <label className="md-field">
          <span>{t('成稿保存到')}</span>
          <input value={form.exportDir} onChange={e => set('exportDir', e.target.value)} placeholder={settings.defaultExportDir} />
        </label>

        <div className="md-field">
          <span>{t('生图来源')}</span>
          <div className="md-presets" role="radiogroup" aria-label={t('生图来源')}>
            {[['http', '图片 API'], ['tool', 'DSH 生成工具']].map(([value, label]) => <button type="button" key={value} role="radio" aria-checked={form.source === value} className={form.source === value ? 'is-on' : ''} onClick={() => set('source', value)}>{t(label)}</button>)}
          </div>
          {form.source === 'tool' ? <>
            <small>{t(settings.imageToolAvailable ? '已检测到生图工具；账号登录和额度以试画结果为准。' : '未找到订阅生图工具，或默认执行器不支持直接调用；请检查插件和执行器后刷新工作台。')}</small>
            <small>{t('复用插件接入 DSH 的订阅生图能力。例如，插件已让你通过 ChatGPT（GPT）订阅在 DSH 中生成图片，工作台就可复用，无需另填图片 API Key。其他国内外服务的订阅也需由插件接入生图功能，并在工作台适配范围内；仅登录订阅或接入聊天模型并不代表支持生图。')}</small>
            <small>{t('当前适配 dsh-plugin-subscriptions。使用的服务、账号及回退规则由该插件决定，工作台不会自动切换到图片 API。')}</small>
            <small>{t('试画和生成图片会消耗订阅账号的生图额度。')}</small>
          </> : null}
        </div>
        {form.source === 'http' ? <>
        <div className="md-field">
          <span>{t('生图模型')}</span>
          <div className="md-presets">
            {PRESETS.map(preset => (
              <button type="button" key={preset.id} className={activePreset === preset.id ? 'is-on' : ''} onClick={() => setForm(f => ({ ...f, baseUrl: preset.baseUrl, model: preset.model, size: preset.size, quality: preset.quality, extra: preset.extra }))}>{t(preset.label)}</button>
            ))}
          </div>
          <small>{t('支持任何兼容 OpenAI 图片接口（/images/generations）的服务。')}</small>
        </div>
        <label className="md-field">
          <span>{t('接口地址')}</span>
          <input type="url" value={form.baseUrl} onChange={e => set('baseUrl', e.target.value)} placeholder="https://…/v1" />
        </label>
        <label className="md-field">
          <span>{t('模型')}</span>
          <input value={form.model} onChange={e => set('model', e.target.value)} placeholder={t('模型名称')} />
        </label>
        <label className="md-field">
          <span>{t('密钥')}{settings.image.hasKey ? t('（已保存，末四位 {hint}）', { hint: settings.image.keyHint }) : ''}</span>
          <input type="password" autoComplete="off" value={form.apiKey} onChange={e => set('apiKey', e.target.value)} placeholder={settings.image.hasKey ? t('留空表示不修改') : 'sk-…'} />
          <small>{t('只保存在这台电脑上，不会写进内容数据，也不会被打包或发给模型。')}</small>
        </label>
        </> : null}
        <div className="md-field-row">
          <label className="md-field"><span>{t('配图数量')}</span><input type="number" min="0" max="4" value={form.imageCount} onChange={e => set('imageCount', e.target.value)} /></label>
          <label className="md-field"><span>{t('分镜格数')}</span><input type="number" min="0" max="12" value={form.shotCount} onChange={e => set('shotCount', e.target.value)} /></label>
        </div>
        <button type="button" className="md-advanced" aria-expanded={advanced} onClick={() => setAdvanced(!advanced)}><Icon name={advanced ? 'chevD' : 'chevR'} size={12} />{t('高级')}</button>
        {advanced ? (
          <>
            {form.source === 'http' ? <div className="md-field-row">
              <label className="md-field"><span>{t('尺寸')}</span><input value={form.size} onChange={e => set('size', e.target.value)} placeholder="1536x1024" /></label>
              <label className="md-field"><span>{t('质量')}</span><input value={form.quality} onChange={e => set('quality', e.target.value)} placeholder="low / medium / high" /></label>
            </div> : <div className="md-field-row">
              <label className="md-field"><span>{t('尺寸')}</span><select value={form.toolSize} onChange={e => set('toolSize', e.target.value)}><option value="">{t('工具默认')}</option>{['1024x1024', '1024x1536', '1536x1024', 'auto'].map(value => <option key={value} value={value}>{value}</option>)}</select></label>
              <label className="md-field"><span>{t('质量')}</span><select value={form.toolQuality} onChange={e => set('toolQuality', e.target.value)}><option value="">{t('工具默认')}</option>{['low', 'medium', 'high', 'auto'].map(value => <option key={value} value={value}>{value}</option>)}</select></label>
            </div>}
            {form.source === 'http' ? <label className="md-field">
              <span>{t('附加参数（JSON）')}</span>
              <input value={form.extra} onChange={e => set('extra', e.target.value)} placeholder='{"output_format":"jpeg"}' />
            </label> : null}
          </>
        ) : null}
        {sample ? <img className="md-test-sample" src={sample} alt={t('测试图')} /> : null}
        <div className="md-form-foot">
          <button type="button" className="md-btn" disabled={testing} onClick={async () => {
            setTesting(true)
            setSample(null)
            setSample(await testImage(payload()))
            setTesting(false)
          }}>{testing ? <span className="md-shimmer">{t('正在试画…')}</span> : t('试画一张')}</button>
          <span style={{ flex: 1 }} />
          <button type="button" className="md-btn" onClick={close}>{t('取消')}</button>
          <button type="submit" className="md-btn is-primary">{t('保存')}</button>
        </div>
      </form>
    </Dialog>
  )
}
