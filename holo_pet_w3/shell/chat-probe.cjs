/* GBT小土豆V8 · 对话窗会话形态对照实验（一次性诊断，2026-10-04）
 *
 * 主人线索：「换无痕启动就不会了」—— 怀疑 CloudFront 拦的是**长期档的身份态**，
 * 不是 IP。本件同一时刻、同一台机，跑两组对照：
 *   ① 无痕会话（非持久 partition，内存档，等价 incognito）
 *   ② 现用持久档（default session，主人的登录态在里面）
 * 各加载一次 https://chat.deepseek.com/，打印：HTTP 状态码（若有）/ 标题 / 正文片段。
 *
 * 结论怎么读：无痕 200 且持久 403 ⇒ 拦的是档的态（换档即可）；
 *             两者都 403 ⇒ 拦的是 IP/指纹，换会话无用。
 *
 * 用法：npx electron shell/chat-probe.cjs
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";

const { app, BrowserWindow, session } = require("electron");
const URL_ = "https://chat.deepseek.com/";

/* 诊断期调试：每步落标记（electron 主进程异常不许无声无息） */
const fs = require("fs");
const path = require("path");
const MARK = path.join(require("os").tmpdir(), "gbt-chat-probe.trace");
function trace(line) { try { fs.appendFileSync(MARK, new Date().toISOString() + " " + line + "\n"); } catch (_) {} }
trace("module loaded");
process.on("uncaughtException", (e) => trace("uncaught: " + (e && e.stack || e)));
process.on("unhandledRejection", (e) => trace("unhandled: " + (e && e.stack || e)));

app.commandLine.appendSwitch("--disable-http-cache");

/* 🔴 Electron 默认「全部窗关了就退应用」——探针第一组销毁窗后进程直接退，
   第二组还没跑（实测踩过：两次对照只跑出一次）。本件要顺序跑两组 ⇒ 拦掉默认退出。 */
app.on("window-all-closed", () => { /* 探针自己决定何时退 */ });

function probe(partition, label) {
  trace("probe start: " + label);
  return new Promise((resolve) => {
    const ses = partition ? session.fromPartition(partition) : session.defaultSession;
    const win = new BrowserWindow({
      show: false,
      width: 1200, height: 800,
      webPreferences: { partition: partition || undefined, contextIsolation: true, nodeIntegration: false },
    });
    let status = "none";
    const out = { label, status };
    ses.webRequest.onCompleted({ urls: [URL_ + "*"] }, (d) => { status = d.statusCode; out.status = d.statusCode; });
    const done = () => {
      /* 等 6 秒让页面 JS（可能的挑战页）落定，再读文本 + 截图留证。 */
      setTimeout(() => {
        win.webContents.executeJavaScript(
          "({title: document.title, body: (document.body ? document.body.innerText : '').slice(0,180)})",
          true).then((r) => {
            out.title = r && r.title; out.body = r && r.body;
          }).catch(() => {}).then(() => {
            win.webContents.capturePage().then((img) => {
              try {
                require("fs").writeFileSync(
                  require("path").join(require("os").tmpdir(),
                    "chat-probe-" + (label.indexOf("无痕") === 0 ? "anon" : "persist") + ".png"),
                  img.toPNG());
                out.shot = true;
              } catch (_) { out.shot = false; }
            }).catch(() => {}).then(() => {
              try { win.destroy(); } catch (_) {}
              resolve(out);
            });
          });
      }, 6000);
    };
    win.webContents.on("did-finish-load", done);
    win.webContents.on("did-fail-load", (e, code, desc) => { out.fail = code + " " + desc; done(); });
    win.loadURL(URL_);
    setTimeout(() => { if (!out.title && !out.fail) { out.fail = "timeout"; try { win.destroy(); } catch (_) {} resolve(out); } }, 25000);
  });
}

app.whenReady().then(async () => {
  trace("whenReady fired");
  const rows = [];
  rows.push(await probe("gbt-probe-anon-" + Date.now(), "无痕（内存档）"));
  rows.push(await probe(null, "现用持久档（default session）"));
  for (const r of rows) {
    trace("RESULT [" + r.label + "] HTTP=" + (r.status || "无")
          + " | fail=" + (r.fail || "-")
          + " | title=" + JSON.stringify(r.title || "")
          + " | body=" + String(r.body || "").replace(/\s+/g, " ").slice(0, 120));
  }
  const out = path.join(require("os").tmpdir(), "gbt-chat-probe-result.json");
  try {
    fs.writeFileSync(out, JSON.stringify({ at: new Date().toISOString(), rows }, null, 1), "utf8");
    trace("wrote " + out);
  } catch (e) { trace("write failed: " + e.message); }
  app.quit();
});
