/* GBT小土豆V8 桌面壳 · **交互预演**（`npm run interact`）
 *
 * ## 它补的是哪一格
 *
 * 第 37 轮的真启动预演抓到一个真缺陷（`moved` 是 macOS only ⇒ 挪窗落盘是死代码），
 * 由此看清一类**共同死角**：现有的四支器验的是
 *   「**载不载得起来**」（rehearse）·「**画得对不对**」（shots）·「**启不启得动**」（startup），
 * 而**没有一件去"动它一下"**。跨窗跳转、铬上的时钟/新鲜度自走、芯片集合一致 ——
 * 全是"动手才看得见"的行为。
 *
 * ⇒ 本件在**真启动**之后，用 `executeJavaScript` 去**真点真读**：
 *
 *   I1 跨窗跳转**端到端**：点「上帝视角」那条铬上的「神经工作台」芯片
 *      → 主进程 `w3:show-window` → 那一扇窗真的 `isVisible()`
 *      （这条链以前只有**判据函数**的单测，**从没端到端跑过**）
 *   I2 白名单：从页面里直接喊一个不存在的窗 id ⇒ 必须 `ok:false`，且**不崩**
 *   I3 新鲜度徽章**会自己走**：隔一拍再读，文案必须变（它每秒 tick）
 *   I4 八扇窗的芯片集合**一致**（一体式的底线：导航到哪都一样）
 *   I5 当前窗高亮**只有一个**（`aria-current="true"` 恰好一条）
 *
 * 🔴 窗全部在屏幕外（`GBT_W3_STARTUP_PROBE=1`）⇒ 连 `show()` 都不会打扰主人。
 *
 * 用法：electron holo_pet_w3/shell/interact.cjs
 * 退出码：0 全过 · 1 有硬失败
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";

process.env.GBT_W3_STARTUP_PROBE = "1";   // 走真引导链，但窗全在屏幕外

const path = require("node:path");
const fs = require("node:fs");

const electron = require("electron");
const { app, BrowserWindow } = electron;

/* 🔴 **探针不许写主人的真布局文件**（第 38 轮 · 拿一次自伤换的教训）：
   本件点芯片会触发 `show()` ⇒ `saveWindowState()` ⇒ 把 `visible:true` 写进
   `app.getPath("userData")/window-layout.json` —— **真的那一份**。
   实测事故：`startup.cjs` + 本件连跑几次之后，那份文件里八扇窗全被记成 `x=-20000`，
   **主人下次启动 App 会以为它根本没起来**。
   ⇒ require main.cjs **之前**把 userData 指到临时目录（`main.cjs` 的 `LAYOUT_FILE` 是载入时算的）。 */
const REAL_LAYOUT = path.join(app.getPath("userData"), "window-layout.json");
const REAL_BEFORE = (() => {
  try { return fs.existsSync(REAL_LAYOUT) ? fs.statSync(REAL_LAYOUT).mtimeMs + ":" + fs.statSync(REAL_LAYOUT).size : "absent"; }
  catch (_) { return "unreadable"; }
})();
const PROBE_HOME = path.join(require("node:os").tmpdir(), "gbt-w3-probe-interact");
try { fs.mkdirSync(PROBE_HOME, { recursive: true }); } catch (_) {}
app.setPath("userData", PROBE_HOME);

/* ⏱ 固定等待是错的（第 38 轮实测）：`SETTLE_MS = 3500` 在批跑时会踩空 ——
   有一跑只认出 **6** 扇窗，`godview` 不在里面，因为铬是挂在 `did-finish-load` 上的，
   而那扇页多调了 4 个 IPC。⇒ 改成**轮询到齐**（有上限），不再赌一个秒数。 */
const SETTLE_MS = 2500;
const READY_MAX_MS = 12000;

const SHELL = path.join(__dirname, "..");
const REG = JSON.parse(fs.readFileSync(path.join(__dirname, "windows.json"), "utf8"));
const delay = (ms) => new Promise((r) => setTimeout(r, ms));

const rows = [];
function say(id, state, detail) {
  rows.push({ id, state, detail });
  const icon = state === "PASS" ? "✅" : state === "FAIL" ? "🔴" : "⏳";
  console.log(icon + " " + String(id).padEnd(10) + String(state).padEnd(9) + detail);
}

/* ⚠️ 模块作用域 —— 第 37 轮踩过：写在函数里，回调里就 `M is not defined`，
   而那条错会被报成"托盘坏了"（**指向完全错的方向**）。 */
let M = { __error__: "未 require" };
try {
  M = require("./main.cjs");
} catch (err) {
  M = { __error__: String((err && err.message) || err).slice(0, 200) };
}

/** 一扇窗的铬自述它是谁（铬自己写在 `data-win` 上）。窗没了就回空串，不抛。 */
async function whoIs(win) {
  try {
    if (!win || win.isDestroyed()) return "";
    return String(await win.webContents.executeJavaScript(
      "(function(){var b=document.getElementById('gbt-chrome');" +
      "return b?b.getAttribute('data-win'):'';})()", true) || "");
  } catch (_) { return ""; }
}

/** 轮询到"认得的窗"不再增加（或到上限）。返回 id → win。 */
async function census() {
  const t0 = Date.now();
  let byId = {}, last = -1, stable = 0;
  while (Date.now() - t0 < READY_MAX_MS) {
    byId = {};
    for (const w of BrowserWindow.getAllWindows()) {
      const id = await whoIs(w);
      if (id) byId[id] = w;
    }
    const n = Object.keys(byId).length;
    if (n === last) { stable++; if (stable >= 2) break; } else { stable = 0; }
    last = n;
    await delay(500);
  }
  return byId;
}

/** 到用的时候**重新解析**一次句柄 —— 开场那一刻的句柄可能已经失效。 */
function alive(byId, id) {
  const w = byId[id];
  try { return w && !w.isDestroyed() ? w : null; } catch (_) { return null; }
}

app.whenReady().then(() => {
  setTimeout(async () => {
    if (M.__error__) {
      say("M:require", "FAIL", "require main.cjs 就抛了：" + M.__error__);
      return app.exit(1);
    }
    const wins = BrowserWindow.getAllWindows();
    if (!wins.length) {
      say("I0", "FAIL", "一个窗都没有 —— 真引导没跑起来，下面的交互无从谈起");
      return app.exit(1);
    }

    /* 建 窗 → id 的映射：**轮询到齐**，不再赌一个固定秒数。
       （第 38 轮实测：固定 3.5s 在批跑时会踩空 ⇒ 只认出 6 扇，godview 缺。） */
    const byId = await census();
    say("I0", Object.keys(byId).length >= 6 ? "PASS" : "FAIL",
        "轮询到 " + Object.keys(byId).length + " 扇窗认了身份（铬上的 data-win）：" + Object.keys(byId).join(","));

    /* 存活普查：还活着的才算数（开场句柄可能已失效） */
    const dead = Object.keys(byId).filter((id) => !alive(byId, id));
    if (dead.length) say("I0b", "FAIL", "这些窗的句柄已失效：" + dead.join(","));

    /* ── I1 跨窗跳转端到端 ───────────────────────────────────────────── */
    try {
      const from = alive(byId, "godview"), to = alive(byId, "brain");
      if (!from || !to) {
        say("I1", "FAIL", "缺 godview 或 brain 窗，跳转验不了（认出来的：" + Object.keys(byId).join(",") + "）");
      } else {
        const before = to.isVisible();
        const clicked = await from.webContents.executeJavaScript(
          "(function(){var b=document.querySelector('#gbt-chrome [data-goto=\"brain\"]');" +
          "if(!b) return 'no-chip'; b.click(); return 'clicked';})()", true);
        await delay(900);
        const after = to.isVisible();
        if (clicked !== "clicked") {
          say("I1", "FAIL", "在上帝视角的铬上找不到「神经工作台」芯片（返回 " + clicked + "）");
        } else if (before === after && !after) {
          say("I1", "FAIL", "点了芯片，但目标窗**没被唤起**（isVisible 仍是 false）—— 跳转链断了");
        } else {
          say("I1", "PASS", "点「神经工作台」芯片 ⇒ 那一扇窗真的被唤起（isVisible " + before + " → " + after + "）");
        }
      }
    } catch (err) {
      say("I1", "FAIL", "跳转验证抛了：" + String((err && err.message) || err).slice(0, 120));
    }

    /* ── I2 白名单：不存在的 id 必须 ok:false，且不崩 ─────────────────── */
    try {
      const src = alive(byId, "godview") || alive(byId, "brain") || BrowserWindow.getAllWindows().find(function(w){return !w.isDestroyed();});
      const r = await src.webContents.executeJavaScript(
        "window.gbtW3.showWindow({id:'../../etc'}).then(function(x){return JSON.stringify(x);})" +
        ".catch(function(e){return 'THREW:'+e.message;})", true);
      const txt = String(r || "");
      if (txt.indexOf("THREW") === 0) say("I2", "FAIL", "不认的 id 让它抛了（应当转成结构化拒绝）：" + txt.slice(0, 90));
      else if (txt.indexOf('"ok":false') >= 0 || txt.indexOf('"ok": false') >= 0) {
        say("I2", "PASS", "不认的窗 id 被如实拒绝：" + txt.slice(0, 90));
      } else say("I2", "FAIL", "不认的 id 竟然没被拒：" + txt.slice(0, 90));
    } catch (err) {
      say("I2", "FAIL", "白名单验证抛了：" + String((err && err.message) || err).slice(0, 120));
    }

    /* ── I3 新鲜度徽章会自己走 ──────────────────────────────────────── */
    try {
      const src = alive(byId, "godview") || alive(byId, "brain") || BrowserWindow.getAllWindows().find(function(w){return !w.isDestroyed();});
      const read = () => src.webContents.executeJavaScript(
        "(function(){var e=document.getElementById('gbtc-fresh');return e?e.textContent:'';})()", true);
      const seen = [];
      for (let i = 0; i < 4; i++) { seen.push(String(await read() || "")); await delay(900); }
      const uniq = Array.from(new Set(seen));
      if (!seen[0] || seen[0].indexOf("未声明") >= 0) {
        say("I3", "FAIL", "徽章没拿到读数（读到 '" + seen[0] + "'）");
      } else if (uniq.length < 2) {
        say("I3", "FAIL", "四次读数一模一样（" + uniq.join(" / ") + "）—— 它没在走");
      } else {
        say("I3", "PASS", "徽章自己在走：" + uniq.slice(0, 3).join(" → "));
      }
    } catch (err) {
      say("I3", "FAIL", "徽章验证抛了：" + String((err && err.message) || err).slice(0, 120));
    }

    /* ── I4/I5 八扇窗的芯片集合一致 · 当前窗高亮恰好一个 ─────────────── */
    try {
      let ref = null, mismatch = [], noCur = [], counts = {};
      for (const id of Object.keys(byId)) { const w = alive(byId, id); if (!w) continue;
        const r = await w.webContents.executeJavaScript(
          "(function(){var nav=document.querySelector('#gbt-chrome .gbtc-nav');if(!nav)return null;" +
          "var chips=[].map.call(nav.querySelectorAll('[data-goto]'),function(b){return b.getAttribute('data-goto');});" +
          "var cur=nav.querySelectorAll('[aria-current=\"true\"]').length;" +
          "return JSON.stringify({chips:chips.sort(),cur:cur});})()", true);
        if (!r) continue;
        const o = JSON.parse(String(r));
        counts[id] = o.chips.length;
        if (ref === null) ref = o.chips;
        else if (JSON.stringify(ref) !== JSON.stringify(o.chips)) mismatch.push(id);
        if (o.cur !== 1) noCur.push(id + "(cur=" + o.cur + ")");
      }
      const n = Object.keys(counts).length;
      say("I4", mismatch.length ? "FAIL" : "PASS",
          mismatch.length ? ("这些窗的导航芯片跟别人不一样：" + mismatch.join(","))
                          : (n + " 扇窗导航芯片集合**完全一致**（各 " + (ref || []).length + " 个）"));
      say("I5", noCur.length ? "FAIL" : "PASS",
          noCur.length ? ("当前窗高亮不唯一：" + noCur.join(" · "))
                       : (n + " 扇窗的当前窗高亮都恰好 1 个"));
    } catch (err) {
      say("I4", "FAIL", "芯片集合验证抛了：" + String((err && err.message) || err).slice(0, 120));
      say("I5", "PENDING", "同上，没验到");
    }

    /* ── I6 🔴 不许污染主人的真布局文件（第 38 轮加 · 这条是拿一次自伤换的）── */
    let realNow = "unreadable";
    try {
      realNow = fs.existsSync(REAL_LAYOUT)
        ? fs.statSync(REAL_LAYOUT).mtimeMs + ":" + fs.statSync(REAL_LAYOUT).size : "absent";
    } catch (_) {}
    say("I6", realNow === REAL_BEFORE ? "PASS" : "FAIL",
        realNow === REAL_BEFORE
          ? ("真布局文件没被本件碰过（探针 userData 已改到 " + PROBE_HOME + "）")
          : ("**真布局文件被改了**：" + REAL_BEFORE + " → " + realNow + " · " + REAL_LAYOUT));

    const fail = rows.filter((r) => r.state === "FAIL").length;
    const pass = rows.filter((r) => r.state === "PASS").length;
    console.log("=".repeat(78));
    console.log("桌面壳 · 交互预演（真启动 + 真点真读 · 窗全在屏幕外 · 不打扰主人）");
    console.log("=".repeat(78));
    console.log("  PASS " + pass + " · FAIL " + fail);
    console.log("  退出码：0=交互这条线全过 · 1=有硬失败");
    console.log("=".repeat(78));
    app.exit(fail ? 1 : 0);
  }, SETTLE_MS);
}).catch((err) => {
  console.log("交互预演自身抛错：" + String((err && err.stack) || err).slice(0, 400));
  app.exit(3);
});
