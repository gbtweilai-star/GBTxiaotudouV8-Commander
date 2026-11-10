// 界面语言：中文写在代码里，英文按中文原文查表。跟随 DeepSeek Harness 的语言，设置里也能固定成中文或 English。
import React from 'react'
import { EN } from './en/index.js'

let preference = 'auto'
let hostLang = readHostLang()
const listeners = new Set()

function readHostLang() {
  if (typeof document === 'undefined') return 'zh'
  const tag = (document.documentElement.lang || navigator.language || 'zh').toLowerCase()
  return tag.startsWith('zh') ? 'zh' : 'en'
}

function notify() {
  listeners.forEach(fn => fn())
}

if (typeof document !== 'undefined' && typeof MutationObserver !== 'undefined') {
  new MutationObserver(() => {
    const next = readHostLang()
    if (next !== hostLang) {
      hostLang = next
      if (preference === 'auto') notify()
    }
  }).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] })
}

/** 当前生效的语言：'zh' 或 'en'。 */
export function lang() {
  return preference === 'auto' ? hostLang : preference
}

/** 设置里的语言偏好：'auto'、'zh' 或 'en'。 */
export function setLanguagePreference(value) {
  const next = value === 'zh' || value === 'en' ? value : 'auto'
  if (next === preference) return
  const before = lang()
  preference = next
  if (lang() !== before) notify()
}

export function subscribeLang(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export function useLang() {
  return React.useSyncExternalStore(subscribeLang, lang)
}

/**
 * 翻译一段界面文字。key 就是中文原文，{name} 是占位符。
 * @param {string} zh - 中文原文。
 * @param {Record<string, unknown>} [vars] - 占位符的值。
 * @returns {string} 当前语言的文字。
 */
export function t(zh, vars) {
  const text = lang() === 'en' ? (EN[zh] ?? zh) : zh
  return vars ? text.replace(/\{(\w+)\}/g, (match, key) => (vars[key] === undefined ? match : String(vars[key]))) : text
}

/** 英文要加空格和复数的地方用这个：n 为 1 时取 one，否则取 other。 */
export function plural(n, one, other) {
  return n === 1 ? one : other
}
