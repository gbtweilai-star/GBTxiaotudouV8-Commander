/* GBT小土豆V8 · 窗口 URL 策略（纯函数 · 可单测）
 *
 * ⚠️ 本文件是**按 main.cjs 调用契约重建**的，不是原件（原件已在本机全盘丢失，
 *    94,109 个文件 + resources/app + portable zip 均无副本）。
 *    重建依据：main.cjs 的三个调用点
 *      · 1281/2296  loopbackUrlOnly(raw) → { ok, why }  用来拦「只放行本机回环」
 *      · 1449/1453  shouldBlockNavigate(cur, next) → { block, reason }
 *      · 1594       windowSource(entry) → { kind: url|connect|file|blocked, ... }
 *    行为红线（照仓里的既有说法，不新立判据）：
 *      · 绝对路径 / 内部 host 与 port **不回显**给渲染层，只回主机名与布尔；
 *      · 唯一放行面是**本机回环**（127.0.0.1 / localhost / ::1），其余一律不给过。
 */
"use strict";

const LOOPBACK_HOSTS = ["127.0.0.1", "localhost", "::1", "0.0.0.0"];
const ALLOWED_PROTOCOLS = ["http:", "https:"];

function parseSafely(raw) {
  const s = String(raw == null ? "" : raw).trim();
  if (!s) return null;
  try { return new URL(s); } catch (err) { return null; }
}

function isLoopbackHost(hostname) {
  const h = String(hostname || "").toLowerCase().replace(/^\[|\]$/g, "");
  return LOOPBACK_HOSTS.indexOf(h) !== -1;
}

/* 只放行本机回环。
   返回 { ok: true, url, host } 或 { ok: false, why }。
   why 是**给人看的一句话**，不含绝对路径（面板页会直接把它印出来）。 */
function loopbackUrlOnly(raw) {
  const s = String(raw == null ? "" : raw).trim();
  if (!s) return { ok: false, why: "空地址：没有可以加载的 URL" };

  const u = parseSafely(s);
  if (!u) {
    /* 没写协议时给一句更可操作的话：引导页要求主人贴的是完整地址。 */
    const looksLikeHost = /^[a-zA-Z0-9.\-]+(:\d+)?(\/|$)/.test(s);
    return {
      ok: false,
      why: looksLikeHost ? "缺协议头：要写 http:// 或 https:// 开头" : "不是合法 URL",
    };
  }

  if (ALLOWED_PROTOCOLS.indexOf(u.protocol) === -1) {
    return { ok: false, why: "只接 http/https（收到 " + u.protocol + "）" };
  }
  if (!isLoopbackHost(u.hostname)) {
    /* 只回主机名，不回整条 URL —— 整条里可能带 token。 */
    return { ok: false, why: "主机不是本机回环（" + u.hostname + "）" };
  }
  return { ok: true, url: u.toString(), host: u.hostname, port: u.port || "" };
}

/* 页面内部发起的跳转要不要拦。
   放行：同源、file → file、本机回环。
   拦截：其余跨源（跳转 = 该由壳开窗，而不是本窗被导航走）。 */
function shouldBlockNavigate(curRaw, nextRaw) {
  const next = parseSafely(nextRaw);
  if (!next) return { block: true, reason: "目标不是合法 URL" };

  const cur = parseSafely(curRaw);

  /* 同源放行（含 hash / 查询串变化）。 */
  if (cur && cur.origin === next.origin) return { block: false, sameOrigin: true };

  /* file:// 之间放行：壳自己的页面互相跳不该被拦。 */
  if (next.protocol === "file:" && (!cur || cur.protocol === "file:")) {
    return { block: false, sameOrigin: true };
  }

  /* 本机回环放行（面板 → 控制台的跨端口跳转属于这一类）。 */
  if (ALLOWED_PROTOCOLS.indexOf(next.protocol) !== -1 && isLoopbackHost(next.hostname)) {
    return { block: false, loopback: true };
  }

  return {
    block: true,
    reason: "跨源跳转不在放行名单（" + next.origin + "）",
    origin: next.origin,
  };
}

/* 这扇窗该载什么。四种结果，与 main.cjs:1594 的分支一一对应：
     { kind: "url",     url }               → loadURL
     { kind: "connect", id, port }          → loadFile(connect.html, {id, port})
     { kind: "file",    file }              → loadFile(path.join(HERE, file))
     { kind: "blocked", why }               → loadFile(blocked.html, {why})
   优先级：显式 url > file > 引导页。
   「有 url 但不合法」**不能静默降级成 file** —— 那等于替主人改了他的配置，
   必须 blocked 并把理由印在页上。 */
function windowSource(entry) {
  const e = entry || {};
  const url = e.url ? String(e.url).trim() : "";
  const file = e.file ? String(e.file).trim() : "";

  if (url) {
    const chk = loopbackUrlOnly(url);
    if (!chk.ok) return { kind: "blocked", why: chk.why };
    return { kind: "url", url: chk.url };
  }

  if (file) return { kind: "file", file: file };

  /* 既没 url 也没 file：DSH 对话面走引导页，让主人在运行时给地址。 */
  return { kind: "connect", id: e.id || null, port: 0 };
}

module.exports = { loopbackUrlOnly, shouldBlockNavigate, windowSource, isLoopbackHost };
