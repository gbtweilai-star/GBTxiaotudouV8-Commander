/* GBT小土豆V8 · 对话面自主回路（可单测的判据 + 最小 IO）
 *
 * ⚠️ 本文件是**按 main.cjs 调用契约重建**的，不是原件（原件已丢失）。
 *    重建依据：main.cjs 的三个调用点
 *      · 1588  deepseekLoop.register(win, { userData })
 *              —— 只在 `entry.id === "dsh-chat" && entry.url` 时被调用
 *                 （即**直载外部对话页**的那扇窗；载本地 connect.html 时不挂）。
 *      · 1945  deepseekLoop.status() → { enabled, configured, ... }
 *      · 1949  deepseekLoop.setEnabled(!status().enabled)
 *              —— 托盘菜单项，切换自主回路开关。
 *
 * 🔴 边界（照仓里既有说法）：
 *     ① 渲染进程**零写口**：所有落盘都在主进程这里，页面只被读；
 *     ② 不往页面里注入脚本 —— 页面自己的 CSP 说了算，壳不绕它；
 *     ③ 页面读不到就**如实说读不到**（status().note），不假装在跑。
 *
 * 当前 windows.json 里 `dsh-chat` 载的是本地 `shell/connect.html`（无 url），
 * 所以 register 实际不会触发 —— 本模块保持"挂着也不出错、没挂也不影响壳"。
 */
"use strict";

const fs = require("fs");
const path = require("path");

const STATE_FILE = "deepseek-loop.json";

const state = {
  enabled: true,        /* 托盘项默认勾上：主人装上就该能用 */
  configured: false,    /* 只有真挂到一扇外部对话页才算"已配置" */
  attachedId: null,
  attachedAt: null,
  note: "未挂载：没有直载外部对话页的窗（当前 dsh-chat 载本地 connect.html）",
  userData: null,
};

function statePath(userData) {
  if (!userData) return null;
  return path.join(String(userData), STATE_FILE);
}

function loadState(userData) {
  const p = statePath(userData);
  if (!p) return;
  try {
    const doc = JSON.parse(fs.readFileSync(p, "utf8"));
    if (doc && typeof doc === "object") {
      if (typeof doc.enabled === "boolean") state.enabled = doc.enabled;
    }
  } catch (err) { /* 没有就是默认值，不算错 */ }
}

function saveState() {
  const p = statePath(state.userData);
  if (!p) return false;
  try {
    fs.mkdirSync(path.dirname(p), { recursive: true });
    fs.writeFileSync(p, JSON.stringify({
      enabled: state.enabled,
      saved_at: new Date().toISOString(),
    }, null, 2), "utf8");
    return true;
  } catch (err) {
    console.error("[w3] 自主回路状态写不进（不影响运行）:", err && err.message);
    return false;
  }
}

/* 挂到一扇真正的外部对话窗。
   只做三件事：记状态、挂 did-finish-load 做一次**可读性探测**、开关注册。
   不做：注入脚本、拦截请求、改页面 DOM。 */
function register(win, opt) {
  const o = opt || {};
  if (o.userData) {
    state.userData = String(o.userData);
    loadState(state.userData);
  }

  if (!win || (win.isDestroyed && win.isDestroyed())) {
    state.note = "窗已销毁，没挂上";
    return { ok: false, reason: state.note };
  }

  try {
    state.attachedId = String((win.__chromeAttached && win.__chromeAttached.id) || "dsh-chat");
  } catch (err) { state.attachedId = "dsh-chat"; }
  state.attachedAt = Date.now();
  state.configured = true;
  state.note = "已挂载：" + state.attachedId + (state.enabled ? "（回路开）" : "（回路关）");

  /* 可读性探测：只读一句，不注入任何东西。
     读不到就如实记"页面不可读"，这正是原件注释里那句话的语义。 */
  try {
    if (win.webContents && typeof win.webContents.on === "function") {
      win.webContents.on("did-finish-load", () => {
        if (!state.enabled) return;
        let url = "";
        try { url = String(win.webContents.getURL() || ""); } catch (err) { url = ""; }
        const readable = /^https?:/i.test(url);
        state.note = readable
          ? "已挂载：" + state.attachedId + "（页面可读）"
          : "已挂载：" + state.attachedId + "（页面不可读：不是 http/https 页）";
        console.log("[w3] 自主回路 " + state.attachedId + "：" + state.note);
      });
    }
  } catch (err) {
    console.error("[w3] 自主回路挂载监听失败:", err && err.message);
  }

  return { ok: true, note: state.note };
}

function status() {
  return {
    enabled: state.enabled === true,
    configured: state.configured === true,
    attached_id: state.attachedId,
    attached_at: state.attachedAt,
    note: state.note,
  };
}

function setEnabled(on) {
  state.enabled = on !== false;
  saveState();
  state.note = (state.configured
    ? "已挂载：" + state.attachedId
    : "未挂载：没有直载外部对话页的窗") + (state.enabled ? "（回路开）" : "（回路关）");
  return status();
}

module.exports = { register, status, setEnabled };
