/* GBT小土豆V8 桌面壳 · 窗口复演（**真建窗口、但不显示**）
 *
 * ## 它补的是哪一块
 *
 * `preflight.cjs` 验的是"壳的模块与注册表对不对"，它**刻意不建窗口**；
 * 于是"**每扇窗的页面在真 Electron 窗口里到底加不加载得起来**"从来没验过 ——
 * 页面文件存在 ≠ 它能被 BrowserWindow 载入（CSP 拦、preload 报错、路径解析错都会在这儿现形）。
 *
 * ⇒ 本件按 `windows.json` **逐个建 BrowserWindow**，用与 `main.cjs` **同一套 webPreferences**，
 *   然后 `loadFile`，等 `did-finish-load` / `did-fail-load` / `console-message`，逐窗给读数。
 *   🔴 `show: false` —— **屏幕上不会出现任何东西**，不打扰主人。
 *
 * ## 它验什么 / 不验什么
 *
 * 验：窗口能不能建 · 页面能不能载入 · preload 能不能挂上 · 页面有没有报 JS 错 · 有没有出网请求
 * 不验：窗口长什么样（要真显示）· DSH 对话面（要主人运行时给带 token 的 URL）
 *
 * 用法：electron holo_pet_w3/shell/rehearse.cjs
 * 退出码：0 全过 · 1 有窗载入失败 · 2 有未决（needs_url 那扇）
 */
"use strict";
const path = require("node:path");
const fs = require("node:fs");

const HERE = __dirname;
const SHELL = path.join(HERE, "..");
const TIMEOUT_MS = 8000;          // 单窗上限：首版 15s × 7 窗 ≈ 105s，被外层 120s 掐掉了
const OUT = path.join(require("node:os").tmpdir(), "gbt-rehearse.json");

/* 🔴 **逐窗即时打印**（首版把所有结果攒到最后才打 ⇒ 外层 120s 一掐就"零输出"，
   什么都看不到）。现在：每完成一扇就打一行 + 立刻落一份 JSON ——
   **即使被掐断，也留着证据**。这是"进程会被杀"这一事实的应对，不是打印风格问题。 */
const rows = [];
function say(row) {
  rows.push(row);
  const icon = row.state === "PASS" ? "✅" : row.state === "FAIL" ? "🔴" : "⏳";
  console.log(icon + " " + String(row.id).padEnd(12) + String(row.state).padEnd(9) + row.detail);
  try {
    fs.writeFileSync(OUT, JSON.stringify({ at: new Date().toISOString(), rows: rows,
                                            blockedNet: blockedNet }, null, 1), "utf8");
  } catch (_) { /* 落不下产物不该让复演崩 */ }
  }
let blockedNet = [];


function main() {
  let electron;
  try {
    electron = require("electron");
  } catch (err) {
    console.log("不在 electron 运行时 —— 请用 `electron holo_pet_w3/shell/rehearse.cjs`");
    return 1;
  }
  const { app, BrowserWindow } = electron;
  if (!app) {
    console.log("拿不到 app —— 不是主进程上下文");
    return 1;
  }

  const reg = JSON.parse(fs.readFileSync(path.join(HERE, "windows.json"), "utf8"));
  const pol = require(path.join(HERE, "url-policy.cjs"));
  /* 🔴 **不要在这里再声明一份 `rows`**（首跑踩到，而且它报的是"假绿"）：
     模块级已有一份 `rows`，`say()` 往那一份推；这里再 `const rows = []` 会**遮蔽**它，
     于是最终统计读到的是**空的局部数组** ⇒ 打印 `PASS 0 · FAIL 0 · PENDING 0` + 退出码 0。
     **"一条没数到"和"一条问题都没有"长得一模一样** —— 这正是本仓反复强调的那类假绿。
     ⇒ 全脚本只有**一份** `rows`。 */
  const blockedNet = [];

  /* 🔴 **不许自动退出**（首跑只跑了一扇窗就退了，退出码还是 0 —— 最容易被读成"全过"）：
     我每验完一扇就 `destroy()`，于是"一个窗都不剩" ⇒ Electron 默认行为 `window-all-closed`
     直接把进程送走。**只跑了一扇而报 exit 0，比报错更危险** —— 它会让人以为七扇都验过了。 */
  app.on("window-all-closed", () => { /* 复演期间刻意不退，等全部验完自己 app.exit */ });

  /* 每个窗一条：建 → 载 → 记 → 关。串行做，避免互相抢资源把读数搅浑。 */
  function one(w) {
    return new Promise((resolve) => {
      const src = pol.windowSource(w);
      if (src.kind === "connect" || src.kind === "url") {
        say({ id: w.id, state: "PENDING",
                    detail: "要主人运行时给带 token 的 URL（" + src.kind + "）—— 复演关不掉这一格" });
        return resolve();
      }      if (src.kind !== "file") {
        say({ id: w.id, state: "FAIL", detail: "来源被判 " + src.kind + "：" + (src.why || "?") });
        return resolve();
      }
      const file = path.resolve(path.join(HERE, w.file));
      if (!fs.existsSync(file)) {
        say({ id: w.id, state: "FAIL", detail: "页面不存在：" + w.file });
        return resolve();
      }
      let settled = false;
      const win = new BrowserWindow({
        show: false,                       // 🔴 关键：屏幕上什么都不出现
        width: 900, height: 600,
        webPreferences: {
          preload: path.join(HERE, "preload.cjs"),
          contextIsolation: true,
          nodeIntegration: false,
        },
      });
      const errs = [];
      win.webContents.on("console-message", (_e, level, message) => {
        if (level >= 3) errs.push(String(message).slice(0, 90));
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
        // 再等一拍，让页面里的脚本跑完（有错的这时才冒出来）
        setTimeout(() => {
          say({
            id: w.id,
            state: errs.length ? "FAIL" : "PASS",
            detail: errs.length ? ("页面报错 " + errs.length + " 条：" + errs[0])
                                : "载入成功 · 页面无 JS 错",
          });
          win.destroy(); resolve();
        }, 900);
      });

      /* 出网探测：壳该是离线自包含的，任何非 file/data 请求都记下来 */
      win.webContents.session.webRequest.onBeforeRequest({ urls: ["*://*/*"] }, (d, cb) => {
        blockedNet.push(w.id + " -> " + d.url.slice(0, 90));
        cb({ cancel: true });
      });

      win.loadFile(file);
      setTimeout(() => {
        if (settled) return;
        settled = true;
        say({ id: w.id, state: "FAIL", detail: "15s 内没载完（超时）" });
        win.destroy(); resolve();
      }, TIMEOUT_MS);
    });
  }

  (async () => {
    for (const w of reg.windows) {
      await one(w);
    }

    const pad = (s, n) => String(s).padEnd(n);
    console.log("=".repeat(78));
    console.log("桌面壳 · 窗口复演（**真建窗口、不显示** · 屏幕上不会出现任何东西）");
    console.log("=".repeat(78));
    console.log("  壳目录 " + SHELL);
    console.log("  注册表 " + reg.windows.length + " 扇窗 · 逐个建 BrowserWindow 并 loadFile");
    console.log("-".repeat(78));
    /* 逐窗结果**上面已经即时打过**（`say()` 每完成一扇就打一行 + 落产物）。
       这里**不再重复** —— 首版忘了删这段，结果七行打了两遍（毛刺，已修）。 */
    console.log("-".repeat(78));
    if (blockedNet.length) {
      console.log("  🔴 有 " + blockedNet.length + " 条**出网请求**（壳该是离线自包含的）：");
      blockedNet.slice(0, 6).forEach((x) => console.log("      · " + x));
    } else {
      console.log("  ✅ 零出网请求 —— 断网照常开窗");
    }
    const fail = rows.filter((r) => r.state === "FAIL").length;
    const pend = rows.filter((r) => r.state === "PENDING").length;
    const pass = rows.filter((r) => r.state === "PASS").length;
    console.log("-".repeat(78));
    console.log("  PASS " + pass + " · FAIL " + fail + " · PENDING " + pend);
    console.log("  ⚠️ PENDING 不算 PASS（needs_url 那扇只有主人运行时能关）");
    console.log("  退出码：0=全过 · 1=有窗载入失败 · 2=有未决");
    console.log("=".repeat(78));
    app.exit(fail ? 1 : (pend ? 2 : 0));
  })();
}

/* 🔴 **必须等 `app.whenReady()`**（首跑踩到）：
   首版在模块加载时直接调 `main()`，Electron 报
   `Cannot create BrowserWindow before app is ready` —— 而且是以
   **UnhandledPromiseRejection** 的形式出现的：不打这一行的话，
   外面只会看到"进程挂着、零输出"，查半天。
   ⇒ 入口一律 `whenReady().then(...)`，并且 `.catch` 兜住。 */
try {
  const e = require("electron");
  if (e && e.app) {
    e.app.whenReady().then(() => {
      const r = main();
      if (typeof r === "number") e.app.exit(r);
    }).catch((err) => {
      console.log("复演自身抛错：" + String(err && err.stack || err).slice(0, 400));
      e.app.exit(3);
    });
  } else {
    const r = main();
    if (typeof r === "number") process.exit(r);
  }
} catch (err) {
  console.log("复演自身抛错：" + String(err && err.stack || err).slice(0, 400));
  try { require("electron").app.exit(3); } catch (_) { process.exit(3); }
}
