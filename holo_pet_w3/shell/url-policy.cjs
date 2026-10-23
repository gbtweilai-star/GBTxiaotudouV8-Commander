/* GBT小土豆V8 · 桌面壳 · URL 与窗口来源策略（**纯函数模块**）
 *
 * 为什么单独抽出来：这段是**安全件**（决定"壳能加载什么"）。
 * 它原来内联在 `main.cjs` 里，而 `main.cjs` 第一行就 `require("electron")` ——
 * 于是**根本没法在普通 node 下单元测试**，只能靠"我看着对"。
 * 抽成不依赖 electron 的纯模块后，`tests/test_url_policy.cjs` 能直接 require 它，
 * 用 `node --test` 把每条接受/拒绝规则钉死。
 *
 * 规则（2026-10-04 起两条）：**本机回环 http/https + 点名外部白名单（仅 https）**。
 *   放行：http(s)://127.0.0.1:* / localhost / ::1 / [::1]
 *         https://chat.deepseek.com/*（主人令：对话窗直载原生 DeepSeek 网页）
 *   拒绝：白名单外的一切外部主机、file:、javascript:、data:、非 URL、空
 * 为什么必须这么严：这是个**常驻托盘 + preload 的壳**。`loadURL` 一旦不限域，
 *   它就变成一个通用浏览器 —— 完全不同的安全面。外部白名单是**点名制**：
 *   多一个主机必须改这份名单（Python 守卫 B6 持同名名单互绑，两边不许漂移）。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";

const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "::1", "[::1]"]);
const OK_PROTOCOLS = new Set(["http:", "https:"]);
/** 外部点名白名单 —— 只收 https。与 tools/codex-scripts/desktop-shell-guard.py 的
 *  ALLOWED_EXTERNAL_HOSTS 同名单互绑；改任何一边必须同步另一边。 */
const EXTERNAL_ALLOWED_HOSTS = new Set(["chat.deepseek.com"]);

/** 只放行本机回环 http/https（DSH token 口子仍在用这条窄规则）。 */
function loopbackUrlOnly(raw) {
  const s = String(raw == null ? "" : raw).trim();
  if (!s) return { ok: false, why: "空 URL" };
  let u;
  try {
    u = new URL(s);
  } catch (err) {
    return { ok: false, why: "不是合法 URL：" + s.slice(0, 80) };
  }
  if (!OK_PROTOCOLS.has(u.protocol)) {
    return { ok: false, why: "只放行 http/https，收到 " + u.protocol };
  }
  if (!LOOPBACK_HOSTS.has(u.hostname)) {
    return { ok: false, why: "只放行本机回环，收到主机 " + u.hostname };
  }
  return { ok: true, url: u.toString() };
}

/** 主机名是不是回环（给别的调用方复用，别各写一份）。 */
function isLoopbackHost(host) {
  return LOOPBACK_HOSTS.has(String(host == null ? "" : host));
}

/**
 * 窗加载 URL 的总策略 —— 回环 http/https 或白名单外部 https。
 * 返回 `{ ok, url }` 或 `{ ok:false, why }`。
 */
function windowLoadPolicy(raw) {
  const s = String(raw == null ? "" : raw).trim();
  if (!s) return { ok: false, why: "空 URL" };
  let u;
  try {
    u = new URL(s);
  } catch (err) {
    return { ok: false, why: "不是合法 URL：" + s.slice(0, 80) };
  }
  if (!OK_PROTOCOLS.has(u.protocol)) {
    return { ok: false, why: "只放行 http/https，收到 " + u.protocol };
  }
  if (LOOPBACK_HOSTS.has(u.hostname)) {
    return { ok: true, url: u.toString() };
  }
  if (u.protocol === "https:" && EXTERNAL_ALLOWED_HOSTS.has(u.hostname)) {
    return { ok: true, url: u.toString() };
  }
  return {
    ok: false,
    why: "外部主机不在白名单：" + u.hostname + "（点名制，见 EXTERNAL_ALLOWED_HOSTS）",
  };
}

/**
 * 一个窗注册项该加载什么 —— **单一决策点**。
 *
 * 返回 `{kind, ...}`：
 *   `url`     带着 `url`（已过总策略）→ 主进程 `loadURL`
 *   `blocked` 声明了 url 但不合法 → 落到拒绝页，`why` 写清原因（**不静默**）
 *   `connect` 声明了 `needs_url`（要主人运行时给 URL，例如 DSH 对话面）→ 落到本地引导页
 *   `file`    本地文件 → `loadFile`
 */
function windowSource(entry) {
  const e = entry || {};
  if (e.url) {
    const chk = windowLoadPolicy(e.url);
    return chk.ok
      ? { kind: "url", url: chk.url }
      : { kind: "blocked", why: chk.why, id: e.id };
  }
  if (e.needs_url) {
    return { kind: "connect", id: e.id, port: Number(e.port) || 0 };
  }
  if (e.file) {
    return { kind: "file", file: e.file };
  }
  return { kind: "blocked", why: "既没有 url、也没有 needs_url、也没有 file", id: e.id };
}

/**
 * 窗内导航策略 —— **页面固定**（主人令 2026-10-04：「全部给我固定住」）。
 *
 * 壳的每一扇窗都锁在自己的原页上：点页面里的链接**不许把当前窗带走**。
 * 允许的只有「同文档」（同协议/主机/路径，仅 query/hash 变）—— 那是页内锚点/查询，
 * 由页面自己处理；其余一律拦。要跳就去**开对应的窗**（菜单/托盘/App 铬），
 * 或走显式的「在浏览器打开」（另一个动作口，不经本窗导航）。
 *
 * 返回 `{ block: bool, why }`。
 */
function shouldBlockNavigate(current, next) {
  const n = String(next == null ? "" : next).trim();
  if (!n || n === "about:blank") return { block: false, why: "空白初始页" };
  let a, b;
  try {
    a = new URL(String(current || ""));
    b = new URL(n);
  } catch (err) {
    return { block: true, why: "目标不是合法 URL" };
  }
  if (a.protocol === b.protocol && a.host === b.host && a.pathname === b.pathname) {
    return { block: false, why: "同文档（query/hash 变）" };
  }
  return { block: true, why: "跨文档跳转（页面已固定：要跳请开对应窗或走「在浏览器打开」）" };
}

module.exports = {
  LOOPBACK_HOSTS,
  OK_PROTOCOLS,
  EXTERNAL_ALLOWED_HOSTS,
  loopbackUrlOnly,
  windowLoadPolicy,
  isLoopbackHost,
  windowSource,
  shouldBlockNavigate,
};
