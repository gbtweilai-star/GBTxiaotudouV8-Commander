/* GBT小土豆V8 桌面壳 · **真启动预演**（`npm run startup`）
 *
 * ## 它补的是哪一格（预检自己写明的空白）
 *
 * `preflight.cjs` 里有一行：
 *     ⏳ S:lock   单例锁/托盘不做判定（那要真启动，本件刻意不启动）
 * ⇒ 「**真启动**」这条路（单例锁 → registerIpc → startSse → 建窗 → 托盘 → 布局落盘）
 *   从来没有机检过。而 `main.cjs` 上面记着一条实测教训：
 *   **托盘图标构造失败会让 startSse 永远不跑，而且没有任何提示**（页脚只安静地显示「实时流：未接」）。
 *   那种缺陷只有**走真链**才抓得到。
 *
 * ## 做法：不另写一条链，而是**让真链自己跑一遍**
 *
 * `GBT_W3_STARTUP_PROBE=1` 只改 `createWindow` 里两个字段（屏幕外 + 不显示），
 * 引导链**一个环节都不跳**。本件 require `./main.cjs` ⇒ 它的 `app.whenReady()` 回调
 * 比本件的**先注册**，所以真的引导先跑，本件再等一拍去**观察效果**。
 *
 * ## 看到什么算什么（都是公开 API 上的效果，不读内部变量）
 *
 *   ① 单例锁拿到了吗（拿不到 main.cjs 会自己 quit ⇒ 一个窗都不会有）
 *   ② 建了几扇窗（`BrowserWindow.getAllWindows()`）
 *   ③ 每扇窗载到东西了吗（`getURL()` 是 file:// 且不在 loading）
 *   ④ **托盘图标真能构造出来吗**（调导出的 `trayIcon()`，看尺寸与 PNG 字节）
 *   ⑤ 布局落盘了吗（`window-layout.json` 存在且刚被写过）
 *   ⑥ 全程有没有 `[w3] ... 失败` 的日志（main.cjs 每个可能抛的环节都有留痕）
 *
 * 用法：electron holo_pet_w3/shell/startup.cjs
 * 退出码：0 全过 · 1 有硬失败
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";

process.env.GBT_W3_STARTUP_PROBE = "1";   // 屏幕外 + 不显示；引导链不跳环节

const path = require("node:path");
const fs = require("node:fs");

/* 🔴 **先挂 console.error 再 require main.cjs** —— 顺序反了就抓不到引导期的留痕。 */
const w3Errors = [];
const origError = console.error.bind(console);
console.error = function () {
  const s = Array.prototype.map.call(arguments, String).join(" ");
  if (s.indexOf("[w3]") >= 0) w3Errors.push(s.replace(/\s+/g, " ").slice(0, 180));
  origError.apply(null, arguments);
};

const electron = require("electron");
const { app, BrowserWindow } = electron;

/* 🔴 **2026-09-23 第 38 轮补：探针不许写主人的真布局文件。**
   实测事故：`startup.cjs` 里"挪一下窗"那一步会触发 `saveWindowState()`，
   而它写的是 `app.getPath("userData")/window-layout.json` —— **真的那一份**。
   结果：八扇窗全被记成 `x=-20000`（屏幕外），**主人下次启动 App 会以为它没起来**。
   （`interact.cjs` 点芯片触发 `show()` 也会把 `visible:true` 写进去，同罪。）
   ⇒ 在 require main.cjs **之前**把 userData 指到临时目录 —— `main.cjs` 的
     `LAYOUT_FILE` 是在**载入时**算的，所以顺序必须在它前面。
   并记下真文件的事前指纹，跑完再核一次（见文件末尾的 `realLayoutUntouched`）。 */
const REAL_LAYOUT = path.join(app.getPath("userData"), "window-layout.json");
const REAL_BEFORE = (() => {
  try { return fs.existsSync(REAL_LAYOUT) ? fs.statSync(REAL_LAYOUT).mtimeMs + ":" + fs.statSync(REAL_LAYOUT).size : "absent"; }
  catch (_) { return "unreadable"; }
})();
const PROBE_HOME = path.join(require("node:os").tmpdir(), "gbt-w3-probe-userdata");
try { fs.mkdirSync(PROBE_HOME, { recursive: true }); } catch (_) {}
app.setPath("userData", PROBE_HOME);

const SHELL = path.join(__dirname, "..");
const REG = JSON.parse(fs.readFileSync(path.join(__dirname, "windows.json"), "utf8"));
const LAYOUT_FILE = path.join(app.getPath("userData"), "window-layout.json");
const SETTLE_MS = 3500;

const rows = [];
const delay = (ms) => new Promise((r) => setTimeout(r, ms));
function say(id, state, detail) {
  rows.push({ id: id, state: state, detail: detail });
  const icon = state === "PASS" ? "✅" : state === "FAIL" ? "🔴" : "⏳";
  console.log(icon + " " + String(id).padEnd(12) + String(state).padEnd(9) + detail);
}

function mainModule() {
  try {
    return require("./main.cjs");
  } catch (err) {
    return { __error__: String((err && err.message) || err).slice(0, 200) };
  }
}

/* ⚠️ 必须**模块作用域**：第一版写在 `main()` 里，后面 whenReady 回调里就 `M is not defined`
   —— 探针自己抛了，却报成「托盘图标构造抛了」，**指向完全错的方向**。 */
const M = mainModule();

function main() {
  if (M.__error__) {
    say("M:require", "FAIL", "require main.cjs 就抛了：" + M.__error__);
    return 1;
  }
  say("M:require", "PASS", "main.cjs 载入成功（真引导链已注册）");
  return 0;
}

const rc = main();

app.whenReady().then(() => {
  /* 本件的 whenReady 比 main.cjs 的**后注册** ⇒ 真的引导先跑。再等一拍让它建完窗、载完页。 */
  setTimeout(async () => {
    const want = (REG.windows || []).length;
    const wins = BrowserWindow.getAllWindows();

    /* ① 单例锁 + ② 建窗 */
    say("S:lock", wins.length > 0 ? "PASS" : "FAIL",
        wins.length > 0 ? "单例锁拿到（否则 main.cjs 会自己 quit，一个窗都不会有）"
                        : "一个窗都没有 —— 单例锁没拿到，或建窗整段抛了");
    say("S:windows", wins.length === want ? "PASS" : "FAIL",
        "建了 " + wins.length + " / 注册表 " + want + " 扇窗");

    /* ③ 每扇窗载到东西了吗
       2026-10-04 起两类判据（主人令：窗 A 直载原生 DeepSeek 网页后，probe 抓到
       「外部窗仍在载入」的假红）：
         · 本地窗（file://）照旧钉死：必须载完且停止载入；
         · 外部白名单对话窗（url-policy.EXTERNAL_ALLOWED_HOSTS）：外部载入受
           网络/登录态影响、没有完成时限 ⇒ 只要求「已真的发起 https 导航」。 */
    const urlPolicy = require("./url-policy.cjs");
    const bad = [];
    let externalCount = 0;
    /* 本地窗的「载完」判据配 **15s 有界等待**（2026-10-04 补）：brain 窗带 three.js
       大快照，单拍检查会因机器负载偶发「仍在载入」假红 —— 判据不变（仍必须载完），
       等待有时限，判决不随负载漂（P3：同型拒绝同形状）。 */
    const waitStart = Date.now();
    while (Date.now() - waitStart < 15000) {
      const stillLoading = wins.filter((w) => {
        try { return w.webContents.isLoading(); } catch (_) { return false; }
      }).length;
      if (stillLoading === 0) break;
      await new Promise((r) => setTimeout(r, 250));
    }
    wins.forEach((w, i) => {
      let u = "", loading = true;
      try { u = w.webContents.getURL(); loading = w.webContents.isLoading(); } catch (_) {}
      let host = "";
      try { host = new URL(u).hostname; } catch (_) {}
      if (urlPolicy.EXTERNAL_ALLOWED_HOSTS.has(host)) {
        externalCount += 1;
        if (!/^https:\/\//.test(u)) {
          bad.push("#" + i + " 外部对话窗没发起导航 url=" + (u || "(空)"));
        }
        return;
      }
      if (!/^file:\/\//.test(u) || loading) bad.push("#" + i + " url=" + (u || "(空)") + (loading ? " 仍在载入" : ""));
    });
    say("S:loaded", bad.length ? "FAIL" : "PASS",
        bad.length ? ("有窗没载成 file:// 或仍在载入：" + bad.slice(0, 3).join(" · "))
                   : (wins.length + " 扇窗全过（本地窗载到 file:// 且停止载入；外部对话窗 "
                      + externalCount + " 扇已发起导航，完成与否不设时限）"));

    /* ④ 托盘图标**真构造一次**（这条是重点：它失败会让 startSse 永远不跑且无声）
       ⚠️ 参数必须与 `buildTray()` **一致**：真实调用是
          `trayIcon(16, [0xf5,0xb0,0x41], [0x00,0xe5,0xff])`。
          第一版我只传了 `size` ⇒ `fill` 是 undefined ⇒ 里面 `fill[0]` 抛
          `Cannot read properties of undefined (reading '0')`，
          而探针把它报成「托盘图标构造抛了」—— **又是指向错方向的假红**。 */
    let tray = "未验";
    try {
      const img = typeof M.trayIcon === "function"
        ? M.trayIcon(16, [0xf5, 0xb0, 0x41], [0x00, 0xe5, 0xff]) : null;
      const sz = img && typeof img.getSize === "function" ? img.getSize() : null;
      const png = img && typeof img.toPNG === "function" ? img.toPNG() : null;
      if (sz && sz.width > 0 && sz.height > 0 && png && png.length > 100) {
        tray = "PASS";
        say("S:tray", "PASS", "托盘图标构造成功 " + sz.width + "×" + sz.height + " · PNG " + png.length + " 字节");
      } else {
        tray = "FAIL";
        say("S:tray", "FAIL", "托盘图标构造出来是空的：size=" + JSON.stringify(sz) + " png=" + (png ? png.length : null));
      }
    } catch (err) {
      tray = "FAIL";
      say("S:tray", "FAIL", "托盘图标构造抛了：" + String((err && err.message) || err).slice(0, 120));
    }

    /* ④c 自建应用菜单（主人令 2026-10-04「这些是拿来干嘛的？返回在哪里？」）：
       应用菜单必须是我们自己的中文菜单（含 ← 返回 / ⟳ 重载），不许再是 Electron 默认英文排。 */
    try {
      const menu = require("electron").Menu.getApplicationMenu();
      const labels = menu ? menu.items.map((i) => i.label || "") : [];
      const hasBack = labels.some((l) => /返回/.test(l));
      const hasReload = labels.some((l) => /重载/.test(l));
      say("S:menu", hasBack && hasReload ? "PASS" : "FAIL",
          "应用菜单：" + JSON.stringify(labels.filter((l) => l).slice(0, 6))
          + (hasBack && hasReload ? "（自建中文菜单就位）" : "（**不是**自建菜单：返回/重载缺）"));
    } catch (err) {
      say("S:menu", "FAIL", "读应用菜单失败：" + String((err && err.message) || err).slice(0, 120));
    }



    /* ④b 🔴 实时流到底接上没有（2026-09-23 第 43 轮加）。

       为什么非有不可：页脚那句「实时流：未接」**只有真启动才照得到** ——
         · 预检**刻意不启动**；
         · 复演只验"载到东西了"；
         · 取证（shots）虽然真渲染，但它是 **WIRE_ONLY 另建窗**，
           压根走不到 `createWindow` 里那条**状态回放**路径。
       ⇒ 三支器全绿，可屏上一直挂着「未接」—— 这正是"门看不见"的典型。

       判据取**页面自己渲染出来的字样**，不取主进程里的变量：
       屏上说什么才算什么（`window.js` 那句 `if (bridge && …)` 是会**静默跳过**的）。 */
    try {
      /* 🔴 选窗判据必须**精确到主窗**（2026-09-23 第 43 轮自己踩的坑）：
         第一版我写的是 `/index\.html$/` —— 而**八扇窗里七扇的 URL 都以 index.html 结尾**
         （godview / eigenflux / h1 / exec-deck / code-deck / brain / eye 全是 `…/index.html`）
         ⇒ `find` 命中的是第一扇，**不是主窗** ⇒ 读到的 body 只有 677 字、
         徽章元素根本不在那页上 ⇒ 我的探针把**自己找错窗**报成了「产品实时流没接上」。
         这就是本仓反复栽的那个型：判据"看着对、其实匹配的是别的东西"。
         ⇒ 判据收窄到**壳根下那一张** `holo_pet_w3/index.html`（路径含中文，URL 会百分号编码，
            所以先 decodeURIComponent 再比）。 */
      const isMain = (u) => {
        try { return /holo_pet_w3[\\/]index\.html$/i.test(decodeURIComponent(u)); }
        catch (_) { return false; }
      };
      const target = wins.find((x) => { try { return isMain(x.webContents.getURL()); } catch (_) { return false; } });
      if (!target) {
        say("S:stream", "FAIL",
            "**没找到主窗**（壳根下的 holo_pet_w3/index.html）⇒ 本格**没验到**，"
            + "别读成通过（八扇窗里七扇都以 index.html 结尾，选窗判据必须精确到壳根那一张）");
      } else {
      const got = await target.webContents.executeJavaScript(
        "(function(){var el=document.getElementById('stream-badge');" +
        " return { bridge: !!(window.gbtW3 && window.gbtW3.onStreamState)," +
        " exists: !!el," +
        " badge: el ? (el.textContent || '') : '(元素不在)'," +
        " outer: el ? String(el.outerHTML).slice(0, 90) : ''," +
        " inHtml: document.body.innerHTML.indexOf('stream-badge') >= 0," +
        " textLen: (document.body.innerText || '').length }; })()", true);
      const badge = String((got && got.badge) || "");
      const ok = badge.indexOf("已接") >= 0;
      say("S:stream", ok ? "PASS" : "FAIL",
          "页面徽章=" + JSON.stringify(badge) + " · 元素在=" + (got && got.exists)
          + " · 桥=" + (got && got.bridge) + " · body 里有 id=" + (got && got.inHtml)
          + " · 正文长=" + (got && got.textLen)
          + (ok ? "" : " ⇒ 状态没送到页面上：页脚会**一直**显示「未接」，而主进程可能已经连上了"));
      }
    } catch (err) {
      say("S:stream", "FAIL", "取页面徽章抛了：" + String((err && err.message) || err).slice(0, 120));
    }

    /* ⑤ 布局持久化 —— **主动去动一下窗再验落盘**。
       第一版我写的是"看文件是不是刚被写过"，判红（5.9 天前）—— 而那是**我断言错了**：
       布局**本来就不在启动时写**，是窗被**移动/缩放/关闭**时才写（`win.on("moved"|"resized"|"close")`）。
       静态看时间戳验不到这条线；要验就得**真触发一次**。 */
    let layoutOk = false, layoutNote = "";
    try {
      const before = fs.existsSync(LAYOUT_FILE) ? fs.statSync(LAYOUT_FILE).mtimeMs : 0;
      const target = wins.find((w) => { try { return !w.isDestroyed(); } catch (_) { return false; } });
      if (!target) {
        layoutNote = "没有可动的窗，持久化这条线没验到";
      } else {
        const b = target.getBounds();
        target.setBounds({ x: b.x, y: b.y + 7, width: b.width, height: b.height });   // 挪 7px
        /* 🔴 **必须等一下**：`moved` 是**异步**事件（`win.on("moved", …)` 里才写盘）。
           第一版我在 `setBounds` 之后**同步**就去比 mtime ⇒ 必然判红，
           而报出来的是「持久化这条线断了」—— **把探针的时序问题报成了产品缺陷**。 */
        await delay(700);
        const after = fs.existsSync(LAYOUT_FILE) ? fs.statSync(LAYOUT_FILE).mtimeMs : 0;
        layoutOk = after > before;
        layoutNote = layoutOk
          ? ("动一次窗 ⇒ window-layout.json 真的被重写（" + path.basename(LAYOUT_FILE) + "）")
          : "动了一次窗，布局文件**没被重写** ⇒ 持久化这条线断了";
      }
    } catch (err) {
      layoutNote = "布局持久化验证抛了：" + String((err && err.message) || err).slice(0, 90);
    }
    say("S:layout", layoutOk ? "PASS" : "FAIL", layoutNote);

    /* ⑥ 引导期有没有 [w3] 失败留痕 */
    say("S:noreport", w3Errors.length ? "FAIL" : "PASS",
        w3Errors.length ? ("引导期有 " + w3Errors.length + " 条失败留痕：" + w3Errors[0])
                        : "引导期零条 [w3] 失败留痕（建窗/托盘/SSE 都没报错）");

    /* ⑦ 🔴 **不许污染主人的真布局文件**（第 38 轮加 · 这条是拿一次自伤换的）。
       本件会真挪窗（触发 saveWindowState）⇒ 如果写的是真那份，
       八扇窗就会被记成屏幕外，**主人下次启动以为 App 没起来**。
       判据：跑完再核一次真文件的事前指纹。 */
    let realNow = "unreadable";
    try {
      realNow = fs.existsSync(REAL_LAYOUT)
        ? fs.statSync(REAL_LAYOUT).mtimeMs + ":" + fs.statSync(REAL_LAYOUT).size : "absent";
    } catch (_) {}
    say("S:nopollute", realNow === REAL_BEFORE ? "PASS" : "FAIL",
        realNow === REAL_BEFORE
          ? ("真布局文件没被本件碰过（探针 userData 已改到 " + PROBE_HOME + "）")
          : ("**真布局文件被改了**：" + REAL_BEFORE + " → " + realNow + " · " + REAL_LAYOUT));

    const fail = rows.filter((r) => r.state === "FAIL").length;
    const pass = rows.filter((r) => r.state === "PASS").length;
    console.log("=".repeat(78));
    console.log("桌面壳 · 真启动预演（`GBT_W3_STARTUP_PROBE=1` · 窗全部屏幕外 · 不打扰主人）");
    console.log("=".repeat(78));
    console.log("  壳目录 " + SHELL);
    console.log("  引导链：单例锁 → registerIpc → startSse → 建窗 → 托盘 → 布局落盘（**一个环节都不跳**）");
    console.log("-".repeat(78));
    console.log("  PASS " + pass + " · FAIL " + fail);
    console.log("  退出码：0=真启动这条路全过 · 1=有硬失败");
    console.log("=".repeat(78));
    app.exit(fail ? 1 : 0);
  }, SETTLE_MS);
}).catch((err) => {
  console.log("预演自身抛错：" + String((err && err.stack) || err).slice(0, 400));
  app.exit(3);
});

if (rc) app.exit(rc);
