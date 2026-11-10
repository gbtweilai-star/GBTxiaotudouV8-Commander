// 浏览器侧的状态：Host 状态的本地镜像，加上只属于界面的选中、视图等。
import React from 'react'
import { coverDataUrl } from './cover.js'
import { lang, plural, setLanguagePreference, t } from './i18n.js'

const BASE = 'media-desk/'

let snapshot = {
  state: null, model: null, modelOk: null, modelError: null, canUndo: false, error: null,
  view: 'home', mode: 'scatter', focusId: null, sheetOrigin: null, dockOpen: true, studioDock: false, chatQuote: null, query: '', kindFilter: 'all', related: null,
  live: {}, settings: null, settingsOpen: false, modelPickOpen: false, thinking: false, toast: null, capture: null, dialog: null,
}
const listeners = new Set()

export function getDesk() {
  return snapshot
}

export function setDesk(patch) {
  snapshot = { ...snapshot, ...(typeof patch === 'function' ? patch(snapshot) : patch) }
  listeners.forEach(fn => fn())
}

function subscribe(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export function useDesk(selector) {
  return React.useSyncExternalStore(subscribe, () => selector(snapshot))
}

async function request(path, body) {
  const res = await fetch(BASE + path, body === undefined ? { headers: { 'x-media-desk-lang': lang() } } : {
    method: 'POST', headers: { 'content-type': 'application/json', 'x-media-desk-lang': lang() }, body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || t('请求失败（{status}）', { status: res.status }))
  return data
}

let toastTimer = null
export function toast(text, { undo = false, error = false } = {}) {
  clearTimeout(toastTimer)
  setDesk({ toast: { text, undo, error, key: Date.now() } })
  toastTimer = setTimeout(() => setDesk({ toast: null }), undo || text.length > 24 ? 6000 : 3200)
}

export function report(err) {
  toast(err.message || String(err), { error: true })
}

export async function loadDesk() {
  try {
    // 先读设置拿到语言偏好，示例数据按这个语言返回
    const settings = await request('settings')
    setLanguagePreference(settings.language)
    const data = await request('state')
    setDesk({ settings, state: data.state, model: data.model, modelOk: data.modelOk, modelError: data.modelError, canUndo: data.canUndo, error: null })
  } catch (err) {
    setDesk({ error: err.message })
  }
}

export async function dispatchOps(ops, { label = t('操作'), undoable = true, silent = false } = {}) {
  try {
    const data = await request('ops', { ops, label, undoable })
    setDesk({ state: data.state, canUndo: undoable || snapshot.canUndo })
    if (data.errors?.length) toast(data.errors[0], { error: true })
    else if (!silent && data.receipts?.[0]) toast(data.receipts[0].text, { undo: undoable })
    return data
  } catch (err) {
    report(err)
    return null
  }
}

export async function undo() {
  try {
    const data = await request('undo', {})
    setDesk({ state: data.state, canUndo: data.canUndo, toast: null })
    if (data.label) toast(t('已撤销：{label}', { label: data.label }))
  } catch (err) {
    report(err)
  }
}

export function openItem(id, origin = null) {
  setDesk({ focusId: id, sheetOrigin: origin })
}

export function closeItem() {
  setDesk({ focusId: null, sheetOrigin: null, studioDock: false, chatQuote: null })
}

/** 一键成稿。任务在 Host 里跑，这里只负责启动和看进度。 */
export async function runProduce(id) {
  try {
    const data = await request('produce', { id })
    setDesk({ state: data.state })
  } catch (err) {
    report(err)
  }
}

export async function cancelProduce(id) {
  try {
    await request('produce/cancel', { id })
  } catch (err) {
    report(err)
  }
}

export async function regenAsset(id, target) {
  try {
    const data = await request('produce/regen', { id, target })
    setDesk({ state: data.state })
  } catch (err) {
    report(err)
  }
}

function mergeProduction(id, production, status) {
  setDesk(s => ({ state: { ...s.state, items: s.state.items.map(item => (item.id === id ? { ...item, production, ...(status ? { status } : {}) } : item)) } }))
}

/** 轮询进度，返回停止函数。 */
export function watchProduction(id) {
  let stopped = false
  const tick = async () => {
    while (!stopped) {
      try {
        const data = await request(`production?id=${encodeURIComponent(id)}`)
        if (stopped) return
        setDesk(s => ({ live: { ...s.live, [id]: data.live } }))
        if (data.production) mergeProduction(id, data.production, data.status)
      } catch {
        // 连接抖动时下一轮再试
      }
      await new Promise(r => setTimeout(r, 700))
    }
  }
  tick()
  return () => { stopped = true }
}

export async function saveSettings(payload) {
  try {
    const settings = await request('settings', payload)
    setLanguagePreference(settings.language)
    setDesk({ settings })
    toast(t('设置已保存'))
    return true
  } catch (err) {
    report(err)
    return false
  }
}

export async function fetchModels() {
  return request('models')
}

/** 切换助手模型；两个字段都空表示跟随默认。 */
export async function saveAssistant(assistant) {
  try {
    const settings = await request('settings', { assistant })
    setDesk({ settings, model: settings.assistantEffective ?? snapshot.model })
    toast(t('助手模型已切换'))
    return true
  } catch (err) {
    report(err)
    return false
  }
}

export async function testImage(payload) {
  try {
    const settings = await request('settings', payload)
    setLanguagePreference(settings.language)
    setDesk({ settings })
    const { src } = await request('settings/test', {})
    return src
  } catch (err) {
    report(err)
    return null
  }
}

function runActions(actions) {
  for (const action of actions) {
    if (action.type === 'produce' && action.id) {
      openItem(action.id)
      runProduce(action.id)
    }
    if (action.type === 'open' && action.id) openItem(action.id)
    if (action.type === 'nav' && action.view) setDesk({ view: action.view })
  }
}

export async function sendChat(text) {
  const { chatQuote: quote, focusId } = snapshot
  // 选中的段落或某一镜，随消息一起交给模型
  const message = quote ? (quote.text ? t('关于{label}「{quote}」：{text}', { label: quote.label, quote: quote.text, text }) : t('关于{label}：{text}', { label: quote.label, text })) : text
  setDesk(s => ({
    thinking: true,
    chatQuote: null,
    state: { ...s.state, chat: [...s.state.chat, { id: `tmp_${Date.now()}`, role: 'user', text: message, itemId: focusId ?? undefined }] },
  }))
  try {
    const data = await request('chat', { message, focusId: focusId ?? undefined })
    setDesk({ state: data.state, canUndo: true, modelOk: data.modelOk, modelError: data.modelError })
    runActions(data.actions || [])
  } catch (err) {
    report(err)
    await loadDesk()
  } finally {
    setDesk({ thinking: false })
  }
}

export async function saveProduced(id) {
  try {
    const production = snapshot.state.items.find(row => row.id === id)?.production
    // 视频封面在浏览器里合成，一起存进文件夹
    const videoCover = await coverDataUrl({ src: production.cover?.src, text: production.coverText || production.title }).catch(() => undefined)
    const data = await request('produce/save', { id, videoCover })
    setDesk({ state: data.state })
    toast(t('已保存到 {path}', { path: data.path }))
  } catch (err) {
    report(err)
  }
}

export async function revealSaved(id) {
  try {
    await request('produce/reveal', { id })
  } catch (err) {
    report(err)
  }
}

export async function clearChat() {
  try {
    const data = await request('chat/clear', {})
    setDesk({ state: data.state })
  } catch (err) {
    report(err)
  }
}

export async function captureUrl(url, extra = {}) {
  try {
    const data = await request('capture-url', { url, ...extra })
    setDesk({ state: data.state, canUndo: true })
    toast(t('已收藏到灵感墙'), { undo: true })
    return data.id
  } catch (err) {
    report(err)
    return null
  }
}

export async function uploadFile(file) {
  const res = await fetch(`${BASE}upload`, { method: 'POST', headers: { 'content-type': file.type, 'x-media-desk-lang': lang() }, body: file })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || t('上传失败'))
  return data
}

export async function captureFiles(files) {
  for (const file of files) {
    try {
      const { src, kind } = await uploadFile(file)
      const title = file.name.replace(/\.[^.]+$/, '')
      await dispatchOps([{ op: 'add_item', kind, title, media: { src } }], { label: t('收藏 {title}', { title }), silent: true })
      toast(t('已放到灵感墙'), { undo: true })
    } catch (err) {
      report(err)
    }
  }
}

export async function refreshAccount(payload) {
  try {
    const data = await request('account/refresh', payload)
    setDesk({ state: data.state, canUndo: true })
    if (data.fetchError) toast(t('读取主页失败：{error}', { error: data.fetchError }), { error: true })
    else toast(t('已更新账号档案'))
    return data
  } catch (err) {
    report(err)
    return null
  }
}

export async function extractStyle(payload) {
  try {
    const data = await request('style/extract', payload)
    setDesk({ state: data.state, canUndo: true })
    const missed = data.failures?.length ?? 0
    toast(missed ? t(plural(missed, '风格提炼好了，有 1 个链接没抓到', '风格提炼好了，有 {n} 个链接没抓到'), { n: missed }) : t('风格提炼好了，之后就按它写'), { undo: true })
    return true
  } catch (err) {
    report(err)
    return false
  }
}

export async function monidStatus() {
  try {
    return await request('monid/status')
  } catch (err) {
    return { state: 'error', message: err.message }
  }
}

export async function importAccount(payload) {
  try {
    const data = await request('monid/import', payload)
    setDesk({ state: data.state, canUndo: true })
    const spent = data.cost ? t('，花费 ${cost}', { cost: data.cost.toFixed(3) }) : ''
    const what = t(plural(data.count, '读到 {name} 的 1 条内容，新增 {added} 条', '读到 {name} 的 {count} 条内容，新增 {added} 条'), { name: data.nickname, count: data.count, added: data.added })
    toast(data.styleError ? t('{what}{spent}。风格没提炼成：{error}', { what, spent, error: data.styleError }) : t('{what}，已提炼成风格{spent}', { what, spent }), { error: Boolean(data.styleError), undo: !data.styleError })
    return true
  } catch (err) {
    report(err)
    return false
  }
}

export async function learnSkills() {
  try {
    const data = await request('skills/learn', {})
    setDesk({ state: data.state, canUndo: true })
    toast(data.added ? t(plural(data.added, '从数据里提炼出 1 条新规则，等你确认', '从数据里提炼出 {n} 条新规则，等你确认'), { n: data.added }) : t('目前的数据还提炼不出新规则'))
  } catch (err) {
    report(err)
  }
}

export async function exportSkills() {
  try {
    const data = await request('skills/export', {})
    setDesk({ state: data.state })
    toast(t(plural(data.rules, '已导出 Skill：{name}（1 条规则）', '已导出 Skill：{name}（{n} 条规则）'), { name: data.name, n: data.rules }))
  } catch (err) {
    report(err)
  }
}

export function fetchInsights() {
  return request('insights')
}

