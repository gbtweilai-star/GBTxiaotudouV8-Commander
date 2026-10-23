/* GBT小土豆V8 桌面壳 · 一体式 App 铬（chrome）—— **一处定义，所有窗共用**
 *
 * ## 为什么要有这一件（2026-09-23 第 32 轮，拿真壳取证图换的）
 *
 * 上一轮做出 `shell/shots.cjs`（真壳取证器）之后，把 8 扇窗的真图摆在一起看，结论很难看：
 *
 *   | 窗 | 顶栏 | 品牌串 |
 *   |---|---|---|
 *   | 上帝视角 / AI 朋友圈 / 赏金台 | 有 | `GBT小土豆V8 · xxx` |
 *   | 触手视觉回传 | 有 | **`触手视觉回传`（少了 `GBT小土豆V8 ·` 前缀）** |
 *   | 执行面 / 代码台 / 神经工作台 | **没有**（被大球 hero 顶掉） | 只有 `<title>` |
 *
 * ⇒ 主人要的是「**一体式**电脑桌面APP」，而现在是**八个各自为政的网页**：
 *   品牌串不一致、有的有顶栏有的没有、没有任何跨窗跳转。**这跟"一体式"是矛盾的。**
 *
 * ## 怎么解（以及为什么不改那 8 个页面）
 *
 * 改 8 个页面 = 同一个决定写 8 遍 ⇒ 必然漂（本仓为"两份判据不一致"付过代价）。
 * ⇒ 改成**壳这一层注入**：`webContents.insertCSS()` + `executeJavaScript()`。
 *   一处定义、零页面改动、且能**逐窗排除**。
 *
 * 🔴 **DSH 那扇窗（`dsh-chat`）一行都不碰** —— 硬约束：不改 DeepSeek Harness 的页面对话面。
 *   它是这个 App 的窗，但**它的内容不是我们的**。所以它不在注入名单里；
 *   别窗能看到它、能跳过去，但没人往它里面塞东西。
 *
 * 🔴 **本文件里的色值只许用准用集里那 15 色**（机检 `audit_skin.py` 会扫 `.cjs`）。
 *   全部走 `var(--gbt-*, <准用集兜底>)`，一个准用集外的色号都没有。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";

/* 铬高：30px。够放一行 12px 字 + 芯片，又不抢页面自己的顶栏。 */
const CHROME_H = 30;
const BAR_ID = "gbt-chrome";
/* 新鲜度那个 span 的 id —— **一处定义**。
   2026-09-23 第 34 轮踩到的：取证器的断言里手写了 `gbt-fresh`，
   而元素实际是 `gbtc-fresh`（跟其他铬元素一样走 gbtc- 前缀）⇒ 7 扇窗全被判「未声明」，
   **断言自己写错了 id，却报成"页面没声明"**。抽成常量之后两边引用同一个。 */
const FRESH_ID = "gbtc-fresh";

/* 哪些窗不注入：DSH 的窗（内容不是我们的）、以及一切没有本地 file 的窗。 */
const NEVER = new Set(["dsh-chat"]);

/* 🔴 品牌标 = **真 Logo**（主人令 2026-10-07 指着截图里的品牌位说「这里的 Logo」）。
   原来这里是个 9px 的小金点（`background: var(--gbt-gold)` 的圆点）——
   品牌位放一个色点，等于没有品牌。现在读品牌真资产：
   `build/tray-logo-32.png` 是 `assets/brand/logo-potato-32.png` 的**逐字节复制**
   （同字节由 `tests/test_tray_logo.cjs` 钉住，含「随便换一张就报红」的负对照）。
   ⚠️ 这里必须给**绝对 file:// URL**：铬是注入到**各层级的页面**里的，
   相对路径会随页面深度变化；`__dirname` 在开发态与打包态都指向壳自己的目录，所以用它算。 */
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const LOGO_URL = pathToFileURL(path.join(__dirname, "..", "build", "tray-logo-32.png")).href;

/* 注入的样式。**只用 var(--gbt-*, <准用集内兜底>)** —— 不引入新色号。 */
const CSS = `
#${BAR_ID} {
  position: fixed; top: 0; left: 0; right: 0; height: ${CHROME_H}px;
  display: flex; align-items: center; gap: 8px; padding: 0 10px;
  box-sizing: border-box; z-index: 2147483000;
  font: 12px/1 "Microsoft YaHei UI", "Segoe UI", system-ui, sans-serif;
  background: var(--gbt-bg, #0B1120);
  color: var(--gbt-text, #E8ECF8);
  border-bottom: 1px solid var(--gbt-line, #1E3A5F);
  -webkit-app-region: drag; user-select: none;
  /* 🔴 **绝不许换行**（首拍就翻车）：8 个中文芯片一换行，30px 的栏被撑成两行，
     标签从中间断开（「上帝视 / 角」「神经工 / 作台」）—— 看着就是没做完的样子。
     宽度不够就让导航**横向滚**，栏高永远是 ${CHROME_H}px。 */
  flex-wrap: nowrap; overflow: hidden;
}
#${BAR_ID} .gbtc-mark {
  width: 18px; height: 18px; border-radius: 5px; flex: 0 0 auto;
  background: url("${LOGO_URL}") center/contain no-repeat;
}
#${BAR_ID} .gbtc-brand { font-weight: 600; letter-spacing: .02em; white-space: nowrap; flex: 0 0 auto; }
#${BAR_ID} .gbtc-brand b { color: var(--gbt-gold, #F5B041); font-weight: 600; }
#${BAR_ID} .gbtc-sep { width: 1px; height: 14px; background: var(--gbt-line, #1E3A5F); flex: 0 0 auto; }
#${BAR_ID} .gbtc-title { color: var(--gbt-cyan, #00E5FF); white-space: nowrap; flex: 0 0 auto; }
#${BAR_ID} .gbtc-grow { flex: 1 1 auto; min-width: 4px; }
#${BAR_ID} .gbtc-nav {
  display: flex; gap: 3px; flex-wrap: nowrap; min-width: 0;
  overflow-x: auto; overflow-y: hidden;
  -webkit-app-region: no-drag;
  scrollbar-width: none;                 /* Firefox */
}
#${BAR_ID} .gbtc-nav::-webkit-scrollbar { display: none; height: 0; }
#${BAR_ID} .gbtc-chip {
  font: inherit; font-size: 11px; line-height: 1;
  padding: 4px 7px; cursor: pointer; white-space: nowrap; flex: 0 0 auto;
  color: var(--gbt-dim, #9AA4C4);
  background: transparent;
  border: 1px solid var(--gbt-line, #1E3A5F);
  border-radius: 999px;
}
#${BAR_ID} .gbtc-chip:hover { color: var(--gbt-text, #E8ECF8); border-color: var(--gbt-cyan, #00E5FF); }
#${BAR_ID} .gbtc-chip[aria-current="true"] {
  color: var(--gbt-bg, #0B1120);
  background: var(--gbt-cyan, #00E5FF);
  border-color: var(--gbt-cyan, #00E5FF);
  cursor: default;
}
#${BAR_ID} .gbtc-host {
  display: inline-flex; align-items: center; gap: 5px; white-space: nowrap;
  color: var(--gbt-dim, #9AA4C4); font-size: 11px;
}
#${BAR_ID} .gbtc-host i {
  width: 7px; height: 7px; border-radius: 50%; background: var(--gbt-off, #6B7280); display: block;
}
#${BAR_ID} .gbtc-host[data-state="ok"] i { background: var(--gbt-ok, #22C55E); }
#${BAR_ID} .gbtc-host[data-state="off"] i { background: var(--gbt-off, #6B7280); }
#${BAR_ID} .gbtc-clock {
  font-family: Consolas, "Cascadia Mono", monospace; color: var(--gbt-dim, #9AA4C4);
  white-space: nowrap; min-width: 62px; text-align: right;
}
/* ── 数据新鲜度（2026-09-23 第 34 轮）：**八扇窗共用一条血路契约** ──
   为什么必须统一：八个窗有五种取数方式（IPC 实时 / 静态快照 / 生成数据文件 / 文件轮询），
   而**用户从屏上看不出哪一扇的数字是几小时前的**。那正是本仓"假绿"那一族。
   契约：页面声明两件事 ——「形态」= 实时 | 快照，「时刻」= 这一份数据是什么时候的。
   铬读它、算年龄、按年龄上色。**没声明就明写「数据 未声明」** —— 沉默不许装成没问题。
   （⚠️ 本段在模板字面量里，**不许出现反引号** —— 会当场把字符串截断。） */
#${BAR_ID} .gbtc-fresh {
  display: inline-flex; align-items: center; gap: 5px; white-space: nowrap;
  font-family: Consolas, "Cascadia Mono", monospace; font-size: 11px;
  padding: 3px 7px; border-radius: 999px;
  color: var(--gbt-off, #6B7280); border: 1px solid var(--gbt-line, #1E3A5F);
}
#${BAR_ID} .gbtc-fresh[data-state="ok"]    { color: var(--gbt-ok, #22C55E);    border-color: var(--gbt-ok, #22C55E); }
#${BAR_ID} .gbtc-fresh[data-state="warn"]  { color: var(--gbt-warn, #F5B041);  border-color: var(--gbt-warn, #F5B041); }
#${BAR_ID} .gbtc-fresh[data-state="fault"] { color: var(--gbt-fault, #EF4444); border-color: var(--gbt-fault, #EF4444); }
#${BAR_ID} .gbtc-fresh[data-state="gray"]  { color: var(--gbt-off, #6B7280); }
/* 页面内容整体下移一条铬的高度。box-sizing 一起给，免得 100% 高的布局被顶出滚动条。 */
html.gbtc-on body { padding-top: ${CHROME_H}px !important; box-sizing: border-box; }
`;

/** 短名：`GBT小土豆V8 · 对话（DeepSeek Harness）` → `对话`（芯片上再砍掉括号副题）。
 *  注册表里的 title 是唯一来源 —— 这里只做**显示用的收窄**，不改登记。 */
function shortTitle(t, id) {
  const s = String(t || id || "");
  const i = s.lastIndexOf("·");
  return (i >= 0 ? s.slice(i + 1) : s).trim() || id;
}

/** 芯片标签：在短名基础上再去掉结尾的括号副题（`对话（DeepSeek Harness）` → `对话`）。
 *  为什么：8 个芯片要挤进最窄只有 880px 的窗，最长的那个会把整条导航挤到截断。
 *  完整名字仍留在 `title` 提示里，**信息一个都没丢**。 */
function chipLabel(t, id) {
  return shortTitle(t, id).replace(/[（(][^）)]*[）)]\s*$/, "").trim() || id;
}

/** 年龄格式化（注入到页里跑的就是它本身，见 barScript 的 `toString()` 注入）。 */
function fmtAge(s) {
  if (s < 60) return Math.floor(s) + "s";
  if (s < 3600) return Math.floor(s / 60) + "m";
  if (s < 86400) return Math.floor(s / 3600) + "h" + Math.floor((s % 3600) / 60) + "m";
  return Math.floor(s / 86400) + "d" + Math.floor((s % 86400) / 3600) + "h";
}

/**
 * 数据新鲜度判据 —— **一处定义，两处消费**：
 *   ① 注入到页面里跑（`barScript` 用 `toString()` 把**函数本身**塞进去）；
 *   ② 单测里直接调（`tests/test_chrome.cjs`）。
 * 不用 `toString()` 注入而各写一份的话，两份阈值必然漂 —— 而"漂了没人知道"正是本仓
 * 反复付代价的那类问题（这条判据的分档尤其容易被改一处忘一处）。
 *
 * 阈值按**形态**分档，因为"实时"与"快照"的"老"不是一回事：
 *   实时：>15s 降级 · >120s 故障（页面本来就该一直在刷）
 *   快照：>6h 降级 · >48h 故障
 * 没声明（kind 不是那两个字、或时刻解析不出来）⇒ `数据 未声明`（灰）。
 * **沉默不许装成没问题。**
 */
function freshState(kind, atMs, nowMs) {
  if (kind !== "实时" && kind !== "快照") return { state: "gray", text: "数据 未声明", age: null };
  if (!isFinite(atMs)) return { state: "gray", text: "数据 未声明", age: null };
  var age = (nowMs - atMs) / 1000;
  if (age < 0) age = 0;
  var state;
  if (kind === "实时") state = age <= 15 ? "ok" : (age <= 120 ? "warn" : "fault");
  else state = age <= 21600 ? "gray" : (age <= 172800 ? "warn" : "fault");
  return { state: state, text: kind + " · " + fmtAge(age) + "前", age: age };
}

/** 生成注入用的脚本。**不写任何内联样式**（页面 CSP 是 `style-src 'self'`），只设类名与属性。 */
function barScript(entry, registry) {
  const items = (registry.windows || []).map((w) => ({
    id: w.id,
    label: chipLabel(w.title, w.id),
    full: shortTitle(w.title, w.id),
    local: !w.needs_url,
  }));
  const payload = JSON.stringify({ self: entry.id, items: items, h: CHROME_H });
  const label = shortTitle(entry.title, entry.id);
  return `(function(){
  var C = ${payload};
  if (document.getElementById(${JSON.stringify(BAR_ID)})) return "already";
  var d = document.createElement("div");
  d.id = ${JSON.stringify(BAR_ID)};
  d.setAttribute("data-win", C.self);
  function mk(tag, cls, text){ var e = document.createElement(tag); if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = String(text); return e; }
  d.appendChild(mk("span", "gbtc-mark"));
  var brand = mk("span", "gbtc-brand"); brand.appendChild(document.createTextNode("GBT"));
  brand.appendChild(mk("b", null, "小土豆")); brand.appendChild(document.createTextNode("V8"));
  d.appendChild(brand);
  /* 🔴 **页面自己有顶栏时不重复写窗口名**（首拍看到的丑处）：上帝视角那几扇窗自己
     就有一条写着「GBT小土豆V8 · 上帝视角」的栏，App 铬再写一遍 ⇒ 60px 内两次品牌。
     探测方式是**运行期问页面**（有没有 .gbt-topbar），不是按页写死一张名单
     —— 名单会漂，探测不会。 */
  if (!document.querySelector(".gbt-topbar")) {
    d.appendChild(mk("span", "gbtc-sep"));
    d.appendChild(mk("span", "gbtc-title", ${JSON.stringify(label)}));
  }
  d.appendChild(mk("span", "gbtc-grow"));
  var nav = mk("nav", "gbtc-nav");
  C.items.forEach(function(it){
    var b = mk("button", "gbtc-chip", it.label + (it.local ? "" : " ⋯"));
    b.type = "button";
    b.setAttribute("data-goto", it.id);
    if (it.id === C.self) b.setAttribute("aria-current", "true");
    b.title = it.local ? ("切到：" + it.full) : (it.full + "（要主人运行时给 URL）");
    b.addEventListener("click", function(){
      var br = window.gbtW3;
      if (!br) return;                                           /* 没宿主：不假装能跳 */
      b.disabled = true;
      /* 🔴 面板内跳页（主人令 2026-10-04：「要固定在 APP 面板上」，不再开一推窗）：
         优先请**面板窗**在内容区里切到该页；面板不在/失败才回落到开窗（老路，托盘仍可用）。 */
      var done = function(){ setTimeout(function(){ b.disabled = false; }, 400); };
      if (typeof br.panelGoto === "function") {
        Promise.resolve(br.panelGoto({ id: it.id }))
          .then(function(r){ if (!r || !r.ok) { if (typeof br.showWindow === "function") return br.showWindow({ id: it.id }); } })
          .catch(function(){}).then(done);
        return;
      }
      if (typeof br.showWindow === "function") {
        Promise.resolve(br.showWindow({ id: it.id })).catch(function(){}).then(done);
        return;
      }
      done();
    });
    nav.appendChild(b);
  });
  d.appendChild(nav);
  var host = mk("span", "gbtc-host"); host.id = "gbtc-host";
  host.appendChild(mk("i"));
  host.appendChild(mk("span", null, window.gbtW3 ? "宿主已接" : "无宿主"));
  host.setAttribute("data-state", window.gbtW3 ? "ok" : "off");
  d.appendChild(host);
  /* ── 数据新鲜度：**两条声明路都读**（CSP 逼出来的，不是设计冗余）──
       ① 有脚本的页：随时写 window.GBT_DATA = {kind, at}（或调 window.gbtFresh）。
          —— 与注入顺序无关：铬每秒读一次，晚到也读得到。
       ② **静态快照页**：把 data-data-kind / data-data-at 写在 html 标签上。
          —— 为什么不能也用脚本：本壳 CSP 是 script-src 'self'，
             **内联 script 会被挡掉**，静态页没有外部脚本可挂。
       阈值按形态分档（实时与快照的"老"不是一回事）：
         实时：>15s 降级 · >120s 故障      快照：>6h 降级 · >48h 故障
       没声明 ⇒ 「数据 未声明」（灰）。**沉默不许装成没问题。**
       （⚠️ 本段在模板字面量里，**不许出现反引号** —— 会当场把字符串截断。） */
  var fresh = mk("span", "${FRESH_ID}", "数据 未声明"); fresh.id = "${FRESH_ID}";
  fresh.setAttribute("data-state", "gray");
  fresh.title = "有脚本的页：window.GBT_DATA={kind:'实时|快照',at:'ISO'}；静态页：<html data-data-kind data-data-at>";
  d.appendChild(fresh);
  /* 判据**本体**注入（不是抄一份）：注入代码与单测跑的是字面上同一个函数。 */
  var fmtAge = ${fmtAge.toString()};
  var freshState = ${freshState.toString()};
  function freshTick(){
    var src = window.GBT_DATA || {};
    var el = document.documentElement;
    var kind = src.kind || el.getAttribute("data-data-kind") || "";
    var at = src.at || el.getAttribute("data-data-at") || "";
    var atMs = at ? Date.parse(String(at).replace(" ", "T")) : NaN;
    var r = freshState(kind, atMs, Date.now());
    fresh.textContent = r.text;
    fresh.setAttribute("data-state", r.state);
  }
  freshTick(); setInterval(freshTick, 1000);
  var clock = mk("span", "gbtc-clock", "--:--:--"); clock.id = "gbtc-clock";
  d.appendChild(clock);
  function tick(){
    var n = new Date();
    var p = function(x){ return (x < 10 ? "0" : "") + x; };
    clock.textContent = p(n.getHours()) + ":" + p(n.getMinutes()) + ":" + p(n.getSeconds());
  }
  tick(); setInterval(tick, 1000);
  var body = document.body || document.documentElement;
  body.insertBefore(d, body.firstChild);
  document.documentElement.classList.add("gbtc-on");
  /* 声明口：**一个调用**就够，页不用记中文串、不用自己拼 dataset。
       实时页：每刷成功一次就 window.gbtFresh(window.GBT_LIVE)
       快照页：生成时写一次 window.gbtFresh(window.GBT_SNAP, "<ISO>")
     没调过 ⇒ 铬显示「数据 未声明」。 */
  window.GBT_LIVE = "实时";
  window.GBT_SNAP = "快照";
  window.gbtFresh = function (kind, at) {
    var el = document.documentElement;
    el.setAttribute("data-data-kind", kind === "实时" ? "实时" : "快照");
    el.setAttribute("data-data-at", at || new Date().toISOString());
    return true;
  };
  return "ok";
})();`;
}

/**
 * 给一扇窗挂上铬。**返回是否挂了**（不挂 = 明确不注入的窗，不是失败）。
 *
 * 幂等：页面 reload 会再触发一次 `did-finish-load`，注入脚本里自带
 * `getElementById` 早退，所以不会叠出第二条铬。
 */
function attach(win, entry, registry) {
  if (!win || !entry || !entry.id) return false;
  if (NEVER.has(entry.id)) return false;                 // DSH 的窗：一行都不碰
  if (entry.needs_url) return false;                     // 非本地页：不注入
  const wc = win.webContents;
  const go = () => {
    try { wc.insertCSS(CSS).catch(() => {}); } catch (_) { /* 样式失败不该弄崩窗 */ }
    try { wc.executeJavaScript(barScript(entry, registry), true).catch(() => {}); } catch (_) { /* 同上 */ }
  };
  wc.on("did-finish-load", go);
  return true;
}

/**
 * 跨窗跳转的**判据本体**（从 `main.cjs` 的 IPC 内联体里抽出来，为了能单测）。
 *
 * 为什么不留在 `registerIpc()` 里：那是个闭包，`wins` / `registry` 都拿不到 ⇒
 * "跳得动吗"这件事**永远只能靠真启动壳去点一下**才知道，等于没验。
 * 抽成纯函数之后：不认的 id、还没建的窗、已销毁的窗、抛出异常的窗，
 * 四路都能在纯 node 里测（本仓既有同类做法：`url-policy.cjs` 的"单一决策点，可单测"）。
 *
 * 返回 `{ok:true, data}` 或 `{ok:false, error}` —— 与 `main.cjs` 的 `ok()/no()` 同形。
 */
function showWindow(registry, wins, payload) {
  const id = payload && payload.id ? String(payload.id) : "";
  const entry = ((registry && registry.windows) || []).filter((e) => e.id === id)[0];
  if (!entry) return { ok: false, error: "没有这扇窗：" + id.slice(0, 40) };
  const w = wins && typeof wins.get === "function" ? wins.get(id) : null;
  if (!w || (typeof w.isDestroyed === "function" && w.isDestroyed())) {
    return { ok: false, error: "这扇窗还没建起来：" + id };
  }
  try {
    if (typeof w.isMinimized === "function" && w.isMinimized()) w.restore();
    w.show();
    w.focus();
    return { ok: true, data: { shown: id } };
  } catch (err) {
    return { ok: false, error: "唤起失败：" + String((err && err.message) || err).slice(0, 80) };
  }
}

module.exports = { CHROME_H, BAR_ID, FRESH_ID, NEVER, CSS, shortTitle, chipLabel, barScript,
                   attach, showWindow, freshState, fmtAge };
