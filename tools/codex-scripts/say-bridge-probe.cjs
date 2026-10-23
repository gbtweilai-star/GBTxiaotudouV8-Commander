/* GBT小土豆V8 · `w3:say` 桥的**端到端真探**（真 Electron · 只读之外只发一次"念一句"）
 *
 * ## 它验什么（P14：被前置条件挡住的代码 = 从没验过的代码）
 * 2026-10-18 新加的「壳替页面念一句」通道：preload `gbtW3.say` → IPC `w3:say`
 * → `five-dim.py cap voice op=speak` → 能力位回执。这条链**不可能靠读代码证明**，
 * 必须真跑一次：IPC 有没有挂上、python 起不起得来、回执有没有 `spoken:true`、被拒时原因带不带回来。
 *
 * ## 做法
 * ① `GBT_W3_WIRE_ONLY=1` 让 main.cjs **只接线不开窗**（与 shots.cjs 同一套）；
 * ② 自建一扇隐藏窗、挂**真 preload**，载 `about:blank`（我们要验的是桥，不是页面）；
 * ③ 在页面里 `await window.gbtW3.say({text})`，把回执**原样**打印；
 * ④ 再发一次空文本，验「缺参如实拒」那条路（不许静默）。
 *
 * 用法（在 holo_pet_w3 目录下）：
 *   node_modules\electron\dist\electron.exe ..\tools\codex-scripts\say-bridge-probe.cjs [--json]
 * 退出码：0 桥通且真出声 · 1 没通（原因在回执里）
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";
const path = require("node:path");
const fs = require("node:fs");
const { app, BrowserWindow } = require("electron");

const argv = process.argv.slice(2);
const ASJSON = argv.indexOf("--json") >= 0;
const HERE = __dirname;
const SHELL = path.join(HERE, "..", "..", "holo_pet_w3");
const TEXT = "主人，这条是壳桥念的：台湾腔，真出声。";

process.env.GBT_W3_WIRE_ONLY = "1";
let wired = true;
try { require(path.join(SHELL, "shell", "main.cjs")); }
catch (e) { wired = false; console.log("⚠️ 真壳接线没挂上：" + String(e && e.message || e).slice(0, 160)); }

function done(code, payload) {
  console.log(ASJSON ? JSON.stringify(payload, null, 1) : payload.report);
  app.exit(code);
}

app.whenReady().then(async () => {
  const win = new BrowserWindow({
    show: false, width: 640, height: 480,
    webPreferences: {
      preload: path.join(SHELL, "shell", "preload.cjs"),
      contextIsolation: true, nodeIntegration: false,
    },
  });
  await win.loadURL("about:blank");

  const hasApi = await win.webContents.executeJavaScript(
    "!!(window.gbtW3 && typeof window.gbtW3.say === 'function')", true);

  let receipt = null, err = "";
  if (hasApi) {
    try {
      receipt = await win.webContents.executeJavaScript(
        `window.gbtW3.say(${JSON.stringify({ text: TEXT })})`, true);
    } catch (e) { err = String(e && e.message || e); }
  }

  let emptyReceipt = null;
  if (hasApi) {
    try { emptyReceipt = await win.webContents.executeJavaScript("window.gbtW3.say({text:''})", true); }
    catch (e) { emptyReceipt = { error: String(e && e.message || e) }; }
  }

  /* 🔴 2026-10-19 加（主人令「波形要跟着她这一次真说的话走」）：
     验证"一次合成、只落盘不出声"这条路：out 允许范围内 → 必须回 file 且 spoken:false；
     out 越界（写别处 / 非 mp3 / 带 ../）→ 必须被壳拒，绝不放行乱写。 */
  let outReceipt = null, outDeny = null, outFile = null;
  if (hasApi) {
    try {
      outReceipt = await win.webContents.executeJavaScript(
        `window.gbtW3.say(${JSON.stringify({ text: TEXT, out: "holo_pet_w3/voice-theater/assets/.utt/last.mp3", play: false })})`,
        true);
      const f = outReceipt && outReceipt.file;
      if (f) {
        const p = path.join(SHELL, "..", String(f).replace(/^holo_pet_w3\//, "holo_pet_w3/"));
        outFile = { path: String(f), exists: fs.existsSync(p), bytes: fs.existsSync(p) ? fs.statSync(p).size : 0 };
      }
    } catch (e) { outReceipt = { error: String(e && e.message || e) }; }
    try {
      outDeny = await win.webContents.executeJavaScript(
        `window.gbtW3.say(${JSON.stringify({ text: TEXT, out: "../../evil.mp3", play: false })})`, true);
    } catch (e) { outDeny = { error: String(e && e.message || e) }; }
  }

  /* 她**自己动手**这条路：白名单内一位 + 表外一位（后者必须被拒，否则白名单没牙） */
  let capOk = null, capDeny = null, hasCap = false;
  if (hasApi) {
    try {
      hasCap = await win.webContents.executeJavaScript("typeof window.gbtW3.cap === 'function'", true);
    } catch (e) { hasCap = false; }
  }
  if (hasCap) {
    try {
      capOk = await win.webContents.executeJavaScript("window.gbtW3.cap({kind:'health',payload:{}})", true);
    } catch (e) { capOk = { error: String(e && e.message || e) }; }
    try {
      capDeny = await win.webContents.executeJavaScript("window.gbtW3.cap({kind:'code_patch',payload:{op:'apply'}})", true);
    } catch (e) { capDeny = { error: String(e && e.message || e) }; }
  }

  const ok = !!(wired && hasApi && receipt && receipt.ok === true && receipt.spoken === true
                && capOk && capOk.ok === true && capDeny && capDeny.refused === true
                /* 2026-10-19：落盘路径必须真写出文件、且 spoken:false（只落盘不出声）；
                   out 越界必须被壳拒（ok:false） */
                && outReceipt && outReceipt.ok === true && outReceipt.spoken === false
                && outFile && outFile.exists === true && outFile.bytes > 0
                && outDeny && outDeny.ok === false);
  const report = [
    "══════════════════════════════════════════════════════════════",
    "  壳桥「念一句」端到端真探（真 Electron · 隐藏窗 · 走能力位）",
    "══════════════════════════════════════════════════════════════",
    "  接线     " + (wired ? "main.cjs 已接线" : "🔴 没挂上"),
    "  页面口   " + (hasApi ? "window.gbtW3.say 在 ✅" : "🔴 不在"),
    "  真出声   " + (receipt ? JSON.stringify(receipt) : "🔴 " + err),
    "  缺参拒   " + (emptyReceipt ? JSON.stringify(emptyReceipt) : "-"),
    "  落盘+不出声 " + (outReceipt ? JSON.stringify(outReceipt).slice(0, 240) : "🔴 没测到"),
    "  落盘文件 " + (outFile ? JSON.stringify(outFile) : "（回执里没有 file）"),
    "  out 越界拒 " + (outDeny ? JSON.stringify(outDeny).slice(0, 200) : "🔴 没测到（壳没挡住？）"),
    "  她动手   " + (hasCap ? JSON.stringify(capOk) : "🔴 没有 w3:cap 口"),
    "  表外拒   " + (capDeny ? JSON.stringify(capDeny).slice(0, 220) : "🔴 没测到（白名单可能没牙）"),
    "──────────────────────────────────────────────────────────────",
    "  判读：`ok:true` + `spoken:true` + voice=zh-TW-* ⇒ 嘴通；",
    "        `capOk.ok:true` + `capDeny.refused:true` ⇒ 她那只手通、且白名单有牙。",
    "  若回 `missing_scopes`/`no_taiwan_lane`，就是**门或引擎**的事，不是桥坏了。",
  ].join("\n");

  done(ok ? 0 : 1, {
    wired: wired, hasApi: hasApi, receipt: receipt, emptyReceipt: emptyReceipt,
    hasCap: hasCap, capOk: capOk, capDeny: capDeny, report: report });
});
