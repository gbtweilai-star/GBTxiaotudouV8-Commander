/* GBT小土豆V8 · 页面取图器（一次性验收工具，2026-10-04）
 *
 * 干什么：把任意**本地页面**（file://）离屏渲染成 PNG —— 给页面的视觉验收取证用，
 * 不依赖开窗/菜单/坐标的真实交互（那些是另一条判据：真启动预演 S:windows/S:loaded）。
 *
 * 用法：npx electron shell/page-shot.cjs "<页面绝对路径>" [宽] [高]
 *   产物：%TEMP%\gbt-page-shot.png（+ 同目录 gbt-page-shot.json 记路径与尺寸）
 *
 * 纪律：只读本地 file:// 页面（不联网、不注入外部站点）；截图落临时目录，不进仓。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";

const { app, BrowserWindow } = require("electron");
const fs = require("fs");
const os = require("os");
const path = require("path");

app.on("window-all-closed", () => { /* 本件自己决定何时退（Electron 默认全关即退会把取证截断） */ });

const page = process.argv[2];
const W = Number(process.argv[3] || 1500);
const H = Number(process.argv[4] || 1100);

app.whenReady().then(async () => {
  const out = path.join(os.tmpdir(), "gbt-page-shot.png");
  const meta = path.join(os.tmpdir(), "gbt-page-shot.json");
  const win = new BrowserWindow({ show: false, width: W, height: H,
    /* 🔴 离屏渲染（2026-10-04 实测补）：不开它时窗口高被**屏幕工作区**卡死（要 2400 只给 942），
       长页只能拍到首屏 ⇒ 验收漏掉下半页。offscreen 允许任意尺寸，拍全页。 */
    webPreferences: { contextIsolation: true, nodeIntegration: false, offscreen: true } });
  try {
    await win.loadFile(page);
    await new Promise((r) => setTimeout(r, 1200));           /* 让页面把首帧画完（无网络依赖） */
    /* 🔴 长页**分段取证**（2026-10-04 实测）：窗口高被屏幕工作区卡住（要 2600 只给 ~1000），
       一屏一张会漏下半页 ⇒ 按 scrollHeight 滚动逐屏拍，全部落盘，一张不落。 */
    const total = await win.webContents.executeJavaScript(
      "Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)", true);
    const vh = await win.webContents.executeJavaScript("window.innerHeight", true);
    const shots = [];
    const nShots = Math.max(1, Math.ceil(Number(total) / Math.max(1, Number(vh))));
    for (let i = 0; i < nShots; i++) {
      await win.webContents.executeJavaScript(
        "window.scrollTo(0, " + (i * Number(vh)) + ")", true);
      await new Promise((r) => setTimeout(r, 350));
      const img = await win.webContents.capturePage();
      const f = out.replace(/\.png$/, "-" + (i + 1) + ".png");
      fs.writeFileSync(f, img.toPNG());
      shots.push({ file: f, size: img.getSize() });
    }
    fs.writeFileSync(meta, JSON.stringify({ page, out, total_height: total, viewport: vh,
      shots, at: new Date().toISOString() }, null, 1), "utf8");
    console.log("SHOT " + shots.length + " 屏：" + shots.map((s) => s.file).join(" | "));
  } catch (err) {
    fs.writeFileSync(meta, JSON.stringify({ page, error: String(err && err.message || err) }, null, 1), "utf8");
    console.log("SHOT-FAIL " + String(err && err.message || err));
  }
  app.quit();
});
