/* GBT小土豆V8 桌面壳 · 一体式 App 铬的契约回归（**带正负对照**）
 *
 * 为什么要有这组：
 *   ① **硬约束「不许碰 DSH 那扇窗」以前没有机检**。`chrome.NEVER` 名单写错一个字符、
 *      或哪天有人手滑把 `dsh-chat` 从名单里删掉，注入就会往**主人的对话面**里塞 DOM ——
 *      而表面上"窗照样开、图照样拍得出"。这条必须在**单测**里钉死。
 *   ② 铬在场与否，以前只有真壳取证器看得到（那是 Electron 进程）；而判断逻辑
 *      （谁注入、谁不注入、芯片叫什么）**完全不依赖 Electron** ⇒ 可以在纯 node 里测。
 *
 * 判据本体 `shell/chrome.cjs` **零 electron 依赖**（只导出纯函数 + attach），
 * 所以这里能直接 require —— 不需要起壳。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const W3 = path.join(__dirname, "..");
const chrome = require(path.join(W3, "shell", "chrome.cjs"));
const REG = JSON.parse(fs.readFileSync(path.join(W3, "shell", "windows.json"), "utf8"));
const entryOf = (id) => REG.windows.filter((w) => w.id === id)[0];

/** 假窗口：只记"有没有被挂上 did-finish-load 监听"，不碰 Electron。 */
function fakeWin() {
  const listeners = [];
  return {
    listeners: listeners,
    webContents: {
      on: (ev) => listeners.push(ev),
      insertCSS: () => Promise.resolve("k"),
      executeJavaScript: () => Promise.resolve("ok"),
    },
  };
}

/* ── 硬约束：DSH 那扇窗一行都不碰 ───────────────────────────────────── */

test("NEVER 名单里有 dsh-chat（DSH 的窗：内容不是我们的）", () => {
  assert.ok(chrome.NEVER.has("dsh-chat"),
    "chrome.NEVER 里没有 dsh-chat —— 注入会往主人的对话面里塞 DOM，违反硬约束");
});

test("attach('dsh-chat') 必须返回 false，且**不许注册任何监听**", () => {
  const w = fakeWin();
  const r = chrome.attach(w, entryOf("dsh-chat"), REG);
  assert.strictEqual(r, false, "dsh-chat 竟然被判为可注入");
  assert.deepStrictEqual(w.listeners, [],
    "dsh-chat 虽被判 false，却已经注册了监听 —— '不注入'必须是**真的没接线**");
});

test("负对照：普通窗必须被判为可注入（否则上一条是空过）", () => {
  const w = fakeWin();
  const r = chrome.attach(w, entryOf("godview"), REG);
  assert.strictEqual(r, true, "普通窗竟然不可注入 —— 那 NEVER 判据是空过的，测不出东西");
  assert.ok(w.listeners.includes("did-finish-load"),
    "判 true 却没注册 did-finish-load：铬永远不会真的挂上去");
});

test("needs_url 的窗（要主人给 URL）不注入 —— 它的页面不是我们的", () => {
  const w = fakeWin();
  const r = chrome.attach(w, entryOf("dsh-chat"), REG);
  assert.strictEqual(r, false);
});

test("attach 对残缺入参不抛（宁可少挂，不许把窗弄崩）", () => {
  assert.strictEqual(chrome.attach(null, entryOf("godview"), REG), false);
  assert.strictEqual(chrome.attach(fakeWin(), null, REG), false);
  assert.strictEqual(chrome.attach(fakeWin(), {}, REG), false);
});

/* ── 铬的形状：品牌、芯片、当前窗 ───────────────────────────────────── */

test("barScript 覆盖注册表里**每一扇**窗（少一扇就是一个跳不过去的孤岛）", () => {
  const js = chrome.barScript(entryOf("godview"), REG);
  const miss = REG.windows.map((w) => w.id).filter((id) => js.indexOf(JSON.stringify(id)) < 0);
  assert.deepStrictEqual(miss, [], "有窗没出现在芯片里：" + JSON.stringify(miss));
});

test("barScript 标出当前窗（aria-current 只能有一个）", () => {
  const js = chrome.barScript(entryOf("brain"), REG);
  assert.ok(js.indexOf('"self":"brain"') >= 0 || js.indexOf('"self": "brain"') >= 0,
    "注入脚本里没带当前窗 id");
  assert.ok(js.indexOf("aria-current") >= 0, "没有 aria-current：当前窗无从标记");
});

test("品牌串一致：GBT + 小土豆 + V8（eye 那份曾经少了前缀）", () => {
  const js = chrome.barScript(entryOf("eye"), REG);
  assert.ok(js.indexOf("小土豆") >= 0 && js.indexOf("V8") >= 0,
    "注入的铬里没有完整品牌串");
});

test("chipLabel：去掉括号副题，但不许把名字砍成空", () => {
  assert.strictEqual(chrome.chipLabel("GBT小土豆V8 · 对话（DeepSeek Harness）", "dsh-chat"), "对话");
  assert.strictEqual(chrome.chipLabel("GBT小土豆V8 · 上帝视角", "godview"), "上帝视角");
  assert.strictEqual(chrome.chipLabel("", "eye"), "eye");
  assert.strictEqual(chrome.chipLabel("（只有括号）", "x"), "x");
});

test("shortTitle：只去掉品牌前缀，完整名保留给 title 提示", () => {
  assert.strictEqual(chrome.shortTitle("GBT小土豆V8 · 对话（DeepSeek Harness）", "dsh-chat"),
                     "对话（DeepSeek Harness）");
});

/* ── 跨窗跳转：判据本体在纯函数里，所以能真测 ───────────────────────── */

/** 假窗口：记下 show/focus/restore 有没有被调到。 */
function fakeTarget(opts) {
  const o = opts || {};
  const calls = [];
  return {
    calls: calls,
    isDestroyed: () => !!o.destroyed,
    isMinimized: () => !!o.minimized,
    restore: () => calls.push("restore"),
    show: () => { calls.push("show"); if (o.throwOnShow) throw new Error("show 炸了"); },
    focus: () => calls.push("focus"),
  };
}

test("跨窗跳转：认得出的窗 + 活着的窗 ⇒ 唤起，并真的 show+focus", () => {
  const wins = new Map([["brain", fakeTarget()]]);
  const r = chrome.showWindow(REG, wins, { id: "brain" });
  assert.strictEqual(r.ok, true, "已知且活着的窗竟然没唤起：" + JSON.stringify(r));
  assert.deepStrictEqual(wins.get("brain").calls, ["show", "focus"]);
  assert.deepStrictEqual(r.data, { shown: "brain" });
});

test("跨窗跳转：最小化的窗先 restore 再 show+focus", () => {
  const wins = new Map([["h1", fakeTarget({ minimized: true })]]);
  chrome.showWindow(REG, wins, { id: "h1" });
  assert.deepStrictEqual(wins.get("h1").calls, ["restore", "show", "focus"]);
});

test("跨窗跳转：**白名单**——不认的 id 一律拒（不许被塞任意字符串）", () => {
  const wins = new Map([["brain", fakeTarget()]]);
  for (const bad of ["", "nope", "../../etc", "godview2", null, undefined, {}, { id: 1 }]) {
    const r = chrome.showWindow(REG, wins, bad);
    assert.strictEqual(r.ok, false, "不该放行的 id 竟然放行了：" + JSON.stringify(bad));
  }
  assert.deepStrictEqual(wins.get("brain").calls, [], "被拒的请求却动了窗口");
});

test("跨窗跳转：注册表里有、但窗口还没建 ⇒ 如实报「还没建起来」，不假装成功", () => {
  const r = chrome.showWindow(REG, new Map(), { id: "godview" });
  assert.strictEqual(r.ok, false);
  assert.ok(/还没建起来/.test(r.error), "报错没说明真因：" + r.error);
});

test("跨窗跳转：已销毁的窗 ⇒ 拒（唤起一个死窗口会抛）", () => {
  const wins = new Map([["eye", fakeTarget({ destroyed: true })]]);
  const r = chrome.showWindow(REG, wins, { id: "eye" });
  assert.strictEqual(r.ok, false);
  assert.deepStrictEqual(wins.get("eye").calls, []);
});

test("跨窗跳转：窗口自己抛异常 ⇒ 不冒泡，转成结构化拒绝（不许把主进程带崩）", () => {
  const wins = new Map([["code-deck", fakeTarget({ throwOnShow: true })]]);
  let r;
  assert.doesNotThrow(() => { r = chrome.showWindow(REG, wins, { id: "code-deck" }); });
  assert.strictEqual(r.ok, false);
  assert.ok(/唤起失败/.test(r.error), "异常没被转成结构化拒绝：" + r.error);
});

test("跨窗跳转：注册表里**每一扇**窗都跳得动（少一扇就是孤岛）", () => {
  const wins = new Map(REG.windows.map((w) => [w.id, fakeTarget()]));
  const dead = REG.windows.filter((w) => !chrome.showWindow(REG, wins, { id: w.id }).ok)
                          .map((w) => w.id);
  assert.deepStrictEqual(dead, [], "这些窗跳不过去：" + JSON.stringify(dead));
});

/* ── 数据新鲜度契约（八扇窗共用的一条血路）────────────────────────── */

const T0 = Date.parse("2026-09-23T10:00:00");
const at = (secAgo) => T0 - secAgo * 1000;

test("新鲜度·实时：≤15s 绿 · ≤120s 黄 · 更久红", () => {
  assert.strictEqual(chrome.freshState("实时", at(5), T0).state, "ok");
  assert.strictEqual(chrome.freshState("实时", at(15), T0).state, "ok");
  assert.strictEqual(chrome.freshState("实时", at(16), T0).state, "warn");
  assert.strictEqual(chrome.freshState("实时", at(120), T0).state, "warn");
  assert.strictEqual(chrome.freshState("实时", at(121), T0).state, "fault");
});

test("新鲜度·快照：≤6h 灰（还没到要提醒）· ≤48h 黄 · 更久红", () => {
  assert.strictEqual(chrome.freshState("快照", at(3600), T0).state, "gray");
  assert.strictEqual(chrome.freshState("快照", at(21600), T0).state, "gray");
  assert.strictEqual(chrome.freshState("快照", at(21601), T0).state, "warn");
  assert.strictEqual(chrome.freshState("快照", at(172800), T0).state, "warn");
  assert.strictEqual(chrome.freshState("快照", at(172801), T0).state, "fault");
});

test("新鲜度·未声明：**沉默不许装成没问题**，一律灰 + 明写「未声明」", () => {
  for (const [k, t] of [["", T0], ["实时", NaN], ["啥也不是", T0], ["快照", NaN]]) {
    const r = chrome.freshState(k, t, T0);
    assert.strictEqual(r.state, "gray", "未声明竟被判成 " + r.state);
    assert.strictEqual(r.text, "数据 未声明");
  }
});

test("新鲜度·文案带年龄（用户看得到「多久以前」，不是只有一个色点）", () => {
  assert.strictEqual(chrome.freshState("实时", at(5), T0).text, "实时 · 5s前");
  assert.strictEqual(chrome.freshState("快照", at(3600 * 3 + 60 * 12), T0).text, "快照 · 3h12m前");
  assert.strictEqual(chrome.freshState("快照", at(86400 * 2 + 3600 * 3), T0).text, "快照 · 2d3h前");
});

test("新鲜度·判据只有一份：注入的脚本里嵌的就是本文件这个函数", () => {
  const js = chrome.barScript(entryOf("godview"), REG);
  assert.ok(js.indexOf(chrome.freshState.toString()) >= 0,
    "注入脚本里的新鲜度判据不是本文件这个函数 —— 说明抄了一份，两份会漂");
  assert.ok(js.indexOf("GBT_DATA") >= 0,
    "注入脚本没有读页面声明的 window.GBT_DATA");
  assert.ok(js.indexOf("data-data-kind") >= 0,
    "注入脚本没有读静态页写在 <html> 上的声明（静态页 CSP 挡内联脚本，只能走属性）");
});

test("新鲜度·声明口给到了页里（有脚本的页一行就能声明）", () => {
  const js = chrome.barScript(entryOf("h1"), REG);
  assert.ok(js.indexOf("window.gbtFresh") >= 0, "没有给页留声明口");
  assert.ok(js.indexOf("window.GBT_LIVE") >= 0 && js.indexOf("window.GBT_SNAP") >= 0,
    "没给形态常量 —— 页会自己拼中文串，迟早拼错一个");
});

/* ── 样式与布局的三条硬约束 ─────────────────────────────────────────── */

test("栏高是常量且注入的样式把它写死（换行会把栏撑成两行）", () => {
  assert.ok(chrome.CHROME_H > 0 && chrome.CHROME_H <= 40, "栏高不合理：" + chrome.CHROME_H);
  assert.ok(chrome.CSS.indexOf("flex-wrap: nowrap") >= 0,
    "CSS 里没有 flex-wrap: nowrap —— 8 个中文芯片会换行，把栏撑成两行（首拍就翻过车）");
  assert.ok(chrome.CSS.indexOf("height: " + chrome.CHROME_H + "px") >= 0,
    "CSS 里的栏高与 CHROME_H 对不上");
});

test("CSS 一个准用集外的色号都不许有（只用 var(--gbt-*, 兜底)）", () => {
  /* 准用集现读：window.css + skin-mission-control.css 的 :root。 */
  const files = [path.join(W3, "window.css"), path.join(W3, "skin-mission-control.css")];
  const allow = new Set();
  for (const f of files) {
    const t = fs.readFileSync(f, "utf8");
    for (const m of t.matchAll(/#([0-9A-Fa-f]{6})\b/g)) allow.add(m[1].toUpperCase());
  }
  const used = new Set();
  for (const m of chrome.CSS.matchAll(/#([0-9A-Fa-f]{6})\b/g)) used.add(m[1].toUpperCase());
  const bad = [...used].filter((c) => !allow.has(c));
  assert.deepStrictEqual(bad, [],
    "铬的 CSS 里出现了准用集外的色号：" + JSON.stringify(bad) +
    "（机检 audit_skin.py 会报混入）");
});
