/* GBT小土豆V8 桌面壳 · 真壳取证器（**每扇窗在真壳里长什么样** → PNG）
 *
 * ## 它补的是哪一块（这是复演器自己写明的空白）
 *
 * `rehearse.cjs` 的 docstring 里写着：
 *   「验：窗口能不能建 · 页面能不能载入 · preload 能不能挂上 · 页面有没有报 JS 错
 *     不验：**窗口长什么样**（要真显示）」
 * ⇒ 「这扇窗到底长什么样」从来没有机检过。而这一格很要紧：
 *   **用裸 Chromium 渲（`render_page.py`）会得到一个假读数** ——
 *   `window.js:19` 读 `window.gbtW3`（preload 注入的），裸浏览器里当然读不到 ⇒
 *   上帝视角四个大格全写「取不到：没有接上宿主进程」。我第 31 轮就先栽在这上面，
 *   差点把"渲染方式不对"判成"主窗是空的"。**看窗必须用真壳看。**
 *
 * ## 怎么做
 *
 * 按 `windows.json` 逐扇建 BrowserWindow，用与 `main.cjs` **同一套 webPreferences**
 * （同 `preload.cjs`），等页面跑完，再 `capturePage()` 落 PNG。
 *
 * 🔴 **为什么是 `show: true` + 屏幕外**，而不是复演器那种 `show: false`：
 *   隐藏窗口在 Windows 上**不绘制**，`capturePage()` 会拿到**空白帧** ——
 *   而空白帧看起来和"这扇窗本来就是空的"一模一样，正是最容易误判的那种假读数。
 *   所以这里把窗口放到屏幕外（x = -20000）并 `skipTaskbar`：**真绘制、但不打扰主人。**
 *
 * 🔴 **空白帧自检（负对照）**：截完抽样看像素，若整幅只有一种颜色，标 `BLANK`。
 *   ——量具必须能测出"我这次没量到东西"，否则它报的绿是假的。
 *
 * 用法：electron holo_pet_w3/shell/shots.cjs [--out 目录]
 * 退出码：0 全过 · 1 有窗截不到/有 JS 错 · 2 有未决（needs_url 那扇）
 */
"use strict";
const path = require("node:path");
const fs = require("node:fs");
const os = require("node:os");

const HERE = __dirname;
const SHELL = path.join(HERE, "..");
const chrome = require(path.join(HERE, "chrome.cjs"));
const TIMEOUT_MS = 9000;
const argv = process.argv.slice(2);
const _oi = argv.indexOf("--out");
const OUTDIR = _oi >= 0 && argv[_oi + 1] ? path.resolve(argv[_oi + 1])
                                         : path.join(os.tmpdir(), "gbt-shell-shots");
const REPORT = path.join(OUTDIR, "report.json");
const OFFSCREEN = -20000;

const rows = [];
const blockedNet = [];

/* 🔴 **复用真壳的接线**（2026-09-23 第 31 轮补，首跑踩到）：
 * 第一版我在这里只挂了 `preload.cjs`，没接主进程那一半 —— 结果页面对宿主喊
 * `w3:eigenflux` / `w3:h1`，主机回「No handler registered」，**截出来是"半个宿主"的样子**，
 * 不是用户真看到的。若照着那份图去做设计判断，就是在拿假读数下结论。
 * ⇒ 现在：`GBT_W3_WIRE_ONLY=1` 让 `main.cjs` **只接线、不开窗**，然后本器再建自己的窗。
 *   **一处接线，两个消费者** —— 不重写第二份（重写必然漂）。 */
process.env.GBT_W3_WIRE_ONLY = "1";
try {
  require("./main.cjs");
} catch (err) {
  console.log("⚠️ 真壳接线没挂上（截出来的会是「半个宿主」的样子）：" + String(err && err.message || err).slice(0, 120));
}

function say(row) {
  rows.push(row);
  const icon = row.state === "PASS" ? "✅" : row.state === "FAIL" ? "🔴"
             : row.state === "PENDING" ? "⏳" : "⚠️";
  console.log(icon + " " + String(row.id).padEnd(12) + String(row.state).padEnd(9) + row.detail);
  try {
    fs.mkdirSync(OUTDIR, { recursive: true });
    fs.writeFileSync(REPORT, JSON.stringify(
      { at: new Date().toISOString(), outdir: OUTDIR, rows: rows, blockedNet: blockedNet }, null, 1), "utf8");
  } catch (_) { /* 落不下产物不该让取证崩 */ }
}

/* 抽样判"整幅是不是一个颜色" —— 用 Electron 的 nativeImage 取位图。
   为什么要它：空白帧与"本来就空的窗"在文件层面长得一样，只有像素能分开。 */
function looksBlank(img) {
  try {
    const sz = img.getSize();
    if (!sz || !sz.width || !sz.height) return "尺寸为 0";
    const bmp = img.getBitmap();            // BGRA
    const stride = sz.width * 4;
    const seen = new Set();
    const stepY = Math.max(1, Math.floor(sz.height / 40));
    const stepX = Math.max(1, Math.floor(sz.width / 40));
    for (let y = 0; y < sz.height; y += stepY) {
      for (let x = 0; x < sz.width; x += stepX) {
        const o = y * stride + x * 4;
        seen.add((bmp[o] << 16) | (bmp[o + 1] << 8) | bmp[o + 2]);
        if (seen.size > 3) return "";       // 有三种以上颜色 ⇒ 有内容
      }
    }
    return "整幅只有 " + seen.size + " 种颜色（疑似空白帧）";
  } catch (e) {
    return "空白自检跑不动：" + String(e && e.message || e).slice(0, 60);
  }
}

function main() {
  let electron;
  try {
    electron = require("electron");
  } catch (err) {
    console.log("不在 electron 运行时 —— 请用 `electron holo_pet_w3/shell/shots.cjs`");
    return 1;
  }
  const { app, BrowserWindow } = electron;
  if (!app) { console.log("拿不到 app —— 不是主进程上下文"); return 1; }

  const reg = JSON.parse(fs.readFileSync(path.join(HERE, "windows.json"), "utf8"));
  const pol = require(path.join(HERE, "url-policy.cjs"));
  fs.mkdirSync(OUTDIR, { recursive: true });

  /* 同复演器：不许自动退出（"一个窗都不剩"会把进程送走，只跑了第一扇却报 exit 0）。 */
  app.on("window-all-closed", () => { /* 等全部截完自己 app.exit */ });

  function one(w) {
    return new Promise((resolve) => {
      const src = pol.windowSource(w);
      if (src.kind === "connect" || src.kind === "url") {
        say({ id: w.id, state: "PENDING",
              detail: "要主人运行时给带 token 的 URL（" + src.kind + "）—— 取证也关不掉这一格" });
        return resolve();
      }
      if (src.kind !== "file") {
        say({ id: w.id, state: "FAIL", detail: "来源被判 " + src.kind + "：" + (src.why || "?") });
        return resolve();
      }
      const file = path.resolve(path.join(HERE, w.file));
      if (!fs.existsSync(file)) {
        say({ id: w.id, state: "FAIL", detail: "页面不存在：" + w.file });
        return resolve();
      }
      const d = w.default || {};
      const W = Math.min(1600, Math.max(720, d.w || 1240));
      const H = Math.min(1000, Math.max(520, d.h || 780));
      let settled = false;
      const errs = [];
      let txtErr = "";                    // 文字落盘失败的原因（与截图失败分开记）
      const win = new BrowserWindow({
        show: true,                       // 🔴 必须真绘制，见文件头
        x: OFFSCREEN, y: OFFSCREEN,       // 屏幕外：真绘制但不打扰主人
        width: W, height: H,
        skipTaskbar: true,
        frame: false,
        webPreferences: {
          preload: path.join(HERE, "preload.cjs"),   // 与 main.cjs 同一套
          contextIsolation: true,
          nodeIntegration: false,
          backgroundThrottling: false,                // 屏幕外也要照常绘制
        },
      });
      win.webContents.on("console-message", (_e, level, message) => {
        if (level >= 3) errs.push(String(message).slice(0, 90));
      });
      /* 🔴 **取证器也要挂铬**（2026-09-23 第 32 轮）：不挂的话，拍的就不是
         "用户真看到的样子"，而是"没有 App 铬的样子" —— 又一种假读数。
         与 `main.cjs` 共用 `./chrome.cjs` 同一份定义。 */
      try { chrome.attach(win, w, reg); } catch (err) { errs.push("铬挂载失败:" + String(err && err.message || err).slice(0, 60)); }
      win.webContents.session.webRequest.onBeforeRequest({ urls: ["*://*/*"] }, (dd, cb) => {
        blockedNet.push(w.id + " -> " + dd.url.slice(0, 90));
        cb({ cancel: true });
      });
      win.webContents.on("did-fail-load", (_e, code, desc) => {
        if (settled) return;
        settled = true;
        say({ id: w.id, state: "FAIL", detail: "载入失败 " + code + " " + desc });
        win.destroy(); resolve();
      });
      win.webContents.on("did-finish-load", () => {
        if (settled) return;
        settled = true;
        // 留一拍让页面脚本把桥上的数据画完（上帝视角 5s 一刷，这里取首屏）
        setTimeout(async () => {
          const png = path.join(OUTDIR, w.id + ".png");
          try {
            /* 🔴 **铬在场断言**（2026-09-23 第 32 轮）：`chrome.attach` 挂上去没有，
               以前**没有任何机检** —— 注入脚本抛一行错、或 `NEVER` 名单写错，
               表面上"窗照样拍得出、照样 PASS"，实际那扇窗就是没有 App 铬的孤儿。
               取证器是唯一既知道"该挂"又看得到 DOM 的地方 ⇒ 断言放这里。 */
            let chromeState = "n/a";
            if (!chrome.NEVER.has(w.id) && !w.needs_url) {
              try {
                chromeState = String(await win.webContents.executeJavaScript(
                  "!!document.getElementById('gbt-chrome')", true));
              } catch (e) { chromeState = "ERR " + String(e && e.message || e).slice(0, 40); }
              if (chromeState !== "true") {
                errs.push("App 铬没挂上（#gbt-chrome 不在）");
              }
            }
            /* 🔴 **先把"屏上真出现的文字"落盘，再截图**（2026-10-29 修顺序）：
               原来文字落盘写在 `capturePage()` **之后** ⇒ 这台机器 `capturePage` 必挂
               （`UnknownVizError`，GPU 进程崩），直接跳进 catch ⇒ **一个 .txt 都不写**。
               于是 `exposure-scan.py` 永远退 2「没扫」，而「截图失败」和「文字没取到」
               被压成了同一个失败 —— 两件不同的事压成一个，正是本仓最忌的那种糊。
               现在：**文字独立成一步**（自己 try），截图挂了不影响取证面。
               （文字仍是 `innerText`：扫源码会假阳/假阴，只有渲染后的文字是真取样面。） */
            try {
              const txt = await win.webContents.executeJavaScript(
                "document.body ? document.body.innerText : ''", true);
              fs.writeFileSync(path.join(OUTDIR, w.id + ".txt"), String(txt || ""), "utf8");
            } catch (e) { txtErr = "文字取不到：" + String(e && e.message || e).slice(0, 60); }
            const img = await win.webContents.capturePage();
            const blank = looksBlank(img);
            fs.writeFileSync(png, img.toPNG());
            /* 🔴 **数据新鲜度必须声明**（2026-09-23 第 34 轮）：
               八扇窗有五种取数方式，"用户看不出哪一扇的数字是几小时前的"就是假绿。
               契约是 `window.GBT_DATA`（有脚本的页）或 `<html data-data-*>`（静态页）。
               **没声明 ⇒ 铬显示「数据 未声明」⇒ 这一扇判红** —— 沉默不许装成没问题。 */
            let freshState2 = "n/a";
            if (!chrome.NEVER.has(w.id) && !w.needs_url) {
              try {
                freshState2 = String(await win.webContents.executeJavaScript(
                  "var e=document.getElementById('" + chrome.FRESH_ID + "'); e ? e.textContent : '(无铬)'", true));
              } catch (e) { freshState2 = "ERR"; }
              if (freshState2.indexOf("未声明") >= 0 || freshState2 === "(无铬)" || freshState2 === "ERR") {
                errs.push("数据新鲜度未声明（铬上写着：" + freshState2 + "）");
              }
            }
            const kb = (fs.statSync(png).size / 1024).toFixed(0);
            const sz = img.getSize();
            say({
              id: w.id,
              state: (errs.length || blank) ? "FAIL" : "PASS",
              detail: (errs.length ? ("页面报错 " + errs.length + " 条：" + errs[0] + " ｜ ") : "")
                    + (blank ? ("⚠️ " + blank + " ｜ ") : "")
                    + "铬=" + chromeState + " · 数据=" + freshState2 + " · "
                    + W + "×" + H + " → " + sz.width + "×" + sz.height + " · " + kb + " KB · "
                    + path.relative(SHELL, png).replace(/\\/g, "/"),
              png: png,
              chrome: chromeState,
            });
          } catch (e) {
            say({ id: w.id, state: "FAIL",
                  detail: "capturePage 失败：" + String(e && e.message || e).slice(0, 80)
                        + (txtErr ? " ｜ " + txtErr : " ｜ 文字已落盘（可跑 exposure-scan）") });
          }
          win.destroy(); resolve();
        }, 1600);
      });

      win.loadFile(file);
      setTimeout(() => {
        if (settled) return;
        settled = true;
        say({ id: w.id, state: "FAIL", detail: TIMEOUT_MS + "ms 内没载完（超时）" });
        win.destroy(); resolve();
      }, TIMEOUT_MS);
    });
  }

  (async () => {
    console.log("=".repeat(78));
    console.log("桌面壳 · 真壳取证（每扇窗用真 preload 绘制 → PNG）");
    console.log("=".repeat(78));
    console.log("  壳目录 " + SHELL);
    console.log("  产物目录 " + OUTDIR);
    console.log("  注册表 " + reg.windows.length + " 扇窗");
    console.log("-".repeat(78));
    for (const w of reg.windows) await one(w);
    console.log("-".repeat(78));
    if (blockedNet.length) {
      console.log("  🔴 有 " + blockedNet.length + " 条出网请求：");
      blockedNet.slice(0, 6).forEach((x) => console.log("      · " + x));
    } else {
      console.log("  ✅ 零出网请求 —— 断网照常绘制");
    }
    const fail = rows.filter((r) => r.state === "FAIL").length;
    const pend = rows.filter((r) => r.state === "PENDING").length;
    const pass = rows.filter((r) => r.state === "PASS").length;
    console.log("-".repeat(78));
    console.log("  取到真图 " + pass + " 扇 · FAIL " + fail + " · PENDING " + pend);
    console.log("  ⚠️ PENDING 不算 PASS（needs_url 那扇只有主人运行时能关）");
    console.log("  产物 " + REPORT);
    console.log("=".repeat(78));
    app.exit(fail ? 1 : (pend ? 2 : 0));
  })();
}

try {
  const e = require("electron");
  if (e && e.app) {
    e.app.whenReady().then(() => {
      const r = main();
      if (typeof r === "number") e.app.exit(r);
    }).catch((err) => {
      console.log("取证自身抛错：" + String(err && err.stack || err).slice(0, 400));
      e.app.exit(3);
    });
  } else {
    const r = main();
    if (typeof r === "number") process.exit(r);
  }
} catch (err) {
  console.log("取证自身抛错：" + String(err && err.stack || err).slice(0, 400));
  try { require("electron").app.exit(3); } catch (_) { process.exit(3); }
}
