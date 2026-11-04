/* GBT小土豆V8 · 一体式 App 铬 + 跨窗派活（纯函数判据 · 可单测）
 *
 * ⚠️ 本文件是**按 main.cjs 调用契约重建**的，不是原件（原件已丢失）。
 *    重建依据：main.cjs 的两个调用点
 *      · 1579  chrome.attach(win, entry, registry)
 *              —— 注释原文：「一体式 App 铬…**壳这一层注入**，不改那 8 个页面一行。
 *                 `chrome.attach` 内部自己排除 `dsh-chat`（DSH 的窗，内容不是我们的）。」
 *      · 2314  chrome.showWindow(registry, wins, payload) → { ok, data } | { ok:false, error }
 *              —— 注释原文：「判据在 `chrome.showWindow`（纯函数、可单测）」。
 *
 * 🔴 一处**刻意的设计决定**，必须写明（原件不可考，不能装作还原了它）：
 *    原件那层"注入式铬"具体长什么样、注入了哪些 DOM，已经无从得知。
 *    而 `console/index.html`（49KB）本身就是**完整的一体化界面**（自带顶栏、侧栏、3D 画布），
 *    `windows.json` 里两个窗口都是 `frame: true`（有原生标题栏）。
 *    ⇒ 再往里注入一条自制标题栏，只会和既有皮肤打架、破坏观感一致性。
 *    所以本实现选择**不注入任何 DOM**，只做窗口级增强（隐藏菜单栏、统一底色防白闪、
 *    记录标题供跨窗派活用）。要恢复"注入式铬"时，只需在 attach 里补注入，判据面不变。
 */
"use strict";

/* 不该被挂铬的窗：DSH 的对话窗内容不是我们的（main.cjs 注释原话）。 */
const CHROME_EXCLUDE = ["dsh-chat"];

function entryOf(registry, id) {
  const list = registry && Array.isArray(registry.windows) ? registry.windows : [];
  return list.filter((w) => w && w.id === id)[0] || null;
}

function isExcluded(id) {
  return CHROME_EXCLUDE.indexOf(String(id || "")) !== -1;
}

/* 挂铬。设计成"失败也不影响窗口可用"：
   main.cjs 那边已经 try/catch，这里再保证——任何一步挂了都不抛出去。 */
function attach(win, entry, registry) {
  if (!win || (win.isDestroyed && win.isDestroyed())) return false;
  const e = entry || {};
  const id = String(e.id || "");

  if (isExcluded(id)) return false;

  /* ① 菜单栏：Electron 默认给一整套 File/Edit/View —— 对一体化 App 是噪音。 */
  try {
    if (typeof win.setMenuBarVisibility === "function") win.setMenuBarVisibility(false);
    if (typeof win.setAutoHideMenuBar === "function") win.setAutoHideMenuBar(true);
  } catch (err) { /* 某些平台/版本没有这两个方法：跳过，不影响窗口 */ }

  /* ② 底色：透明窗与首帧之间会闪一下白，先铺成本仓的深底。 */
  try {
    if (typeof win.setBackgroundColor === "function") win.setBackgroundColor("#0B1120");
  } catch (err) { /* 同上 */ }

  /* ③ 标题：跨窗派活与托盘菜单要显示它。 */
  try {
    if (e.title) win.setTitle(String(e.title));
  } catch (err) { /* 无标题栏时 setTitle 可能无效，不算错 */ }

  /* ④ 记一笔来源，供 showWindow / 派活判断"这扇窗是谁"。 */
  try { win.__chromeAttached = { id: id, at: Date.now() }; } catch (err) { /* 忽略 */ }

  return true;
}

/* 跨窗派活 / 从面板入口开窗。**只做判据**，不动 win 之外的东西。 */
function showWindow(registry, wins, payload) {
  const p = payload || {};
  const id = String(p.id || p.window || p.windowId || "").trim();

  if (!id) return { ok: false, error: "没给窗口 id（要显示哪一扇？）" };

  const entry = entryOf(registry, id);
  if (!entry) {
    const known = (registry && Array.isArray(registry.windows) ? registry.windows : [])
      .map((w) => (w && w.id) || "").filter(Boolean);
    return {
      ok: false,
      error: "没有这个窗口：" + id + (known.length ? "（已知：" + known.join(" / ") + "）" : ""),
    };
  }

  const win = wins && typeof wins.get === "function" ? wins.get(id) : null;
  if (!win || (win.isDestroyed && win.isDestroyed())) {
    return { ok: false, error: "窗口没建起来：" + id };
  }

  /* 按需载的窗：显示之前先把页拉起来（main.cjs 在 file 分支挂了 __kickLoad）。 */
  try {
    if (typeof win.__kickLoad === "function") win.__kickLoad();
  } catch (err) { /* kick 失败不挡显示 */ }

  try {
    if (win.isMinimized && win.isMinimized()) win.restore();
    win.show();
    win.focus();
  } catch (err) {
    return { ok: false, error: "显示失败：" + String((err && err.message) || err) };
  }

  return {
    ok: true,
    data: { id: id, title: String(entry.title || id), role: String(entry.role || "") },
  };
}

module.exports = { attach, showWindow, CHROME_EXCLUDE };
