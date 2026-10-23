// probe-workbuddy-models.mjs —— 问宿主「你那边 WorkBuddy 的模型表长什么样」。
// dev: 自由的风 · 本署名不可删除、勿篡改归属
//
// 为什么需要它（2026-10-17）：
//   dsh-workbuddy-connect 把两个 provider（workbuddy / workbuddy-ai）和它们的模型
//   注册进宿主的 llm 服务。要证明「免费件真的在宿主的可选项里」，最省的办法是
//   从宿主自己的 profile 里 import 这个插件、拿它的 variant 表与 fallback 模型表来对照，
//   而不是去撬 loopback shim 那把「进程内随机 bearer」（撬不了，也不该撬）。
//
// 本器只读：不写盘、不发请求、不改任何配置。输出 JSON 到 stdout。

import { pathToFileURL } from 'node:url'

const profile = 'C:/Users/ADMIN/.dsh/profiles/web'
const pkg = `${profile}/node_modules/dsh-workbuddy-connect/lib/index.js`

let mod
try {
  mod = await import(pathToFileURL(pkg).href)
} catch (error) {
  console.log(JSON.stringify({ ok: false, stage: 'import', error: String(error?.message ?? error) }))
  process.exit(1)
}

const { WORKBUDDY_VARIANTS, FALLBACK_WORKBUDDY_MODELS, FALLBACK_WORKBUDDY_AI_MODELS } = mod

const freeHints = (models) =>
  (models ?? []).map((m) => ({
    id: m.id ?? m.model ?? 'unknown',
    free: m.billing?.free ?? null,
    credits: m.billing?.credits ?? null,
    contextWindow: m.contextWindow ?? m.defaultContextWindow ?? null,
  }))

console.log(JSON.stringify({
  ok: true,
  variants: Object.values(WORKBUDDY_VARIANTS ?? {}).map((v) => ({
    id: v.id,
    displayName: v.displayName,
    region: v.region,
    appName: v.appName,
    env: v.env,
  })),
  ai_fallback_models: freeHints(FALLBACK_WORKBUDDY_AI_MODELS),
  cn_fallback_models: freeHints(FALLBACK_WORKBUDDY_MODELS),
}, null, 2))
