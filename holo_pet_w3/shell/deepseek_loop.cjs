/* GBT小土豆V8 · 对话面自主回路（主人令 2026-10-04：「她能直接操控触手能力来实现自主运行」）
 *
 * 它是什么：把 chat.deepseek.com 这一扇窗变成**自主运行的决策-执行回路** ——
 *   ① 读：每 TICK 从页面里取她**最新一条回复**（跳过「已思考」推理块，只认正文）；
 *   ② 判：回复里有 ```gbt 指令块、且这条还没处理过（内容哈希去重）才动手；
 *   ③ 执行：把回复原文交给 `deepseek_bridge.py exec --execute`（**run_task 唯一门**，
 *      授权/作用域/审计全在门里，本模块不旁路一条）；
 *   ④ 回喂：把桥产出的 ```gbt-result 反馈块**自动粘贴回输入框并发送** ⇒ 她读到结果继续干。
 * 人一步都不用点 —— 这就是「借你装的眼睛看、借你装的手脚动」的闭环本体。
 *
 * 护栏（一条都不许少）：
 *   · 急停：仓内 `state/deepseek_bridge/PAUSE` 文件存在 ⇒ 本 tick 只读不送（托盘可见）；
 *   · 轮次上限 MAX_ROUNDS：跑到上限**自动停**并记日志（防两个模型互相刷屏烧时间）；
 *   · 只读她的**正文**：`think|reason` 祖先链上的节点一律跳过（推理草稿里的示例块不许当指令执行）；
 *   · 不碰凭据：本模块只做「读页面文本 / 写输入框」，不读 cookie、不碰存储、不发外部请求；
 *   · 全程留痕：每轮一行进 `loop.log`（谁执行了什么、读到多少字、成没成）。
 *
 * 配置（app userData 下 `gbt-deepseek-loop.json`，由 deepseek_bridge.py 自动写入）：
 *   { "bridge": "<deepseek_bridge.py 绝对路径>", "python": "py", "pythonArgs": ["-3.14"] }
 * 没有配置 = 回路待配置（**不猜路径、不假装在跑**，日志里如实写）。
 *
 * 为什么注入收口在本文件：B4 守卫的旧义是「不碰对话窗」，主人令改为自主运行后，
 * 注入只允许出现在**本模块**、只作用于**这一扇窗** —— 别的文件出现注入一律判 FAIL。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { execFile } = require("child_process");

const CFG_NAME = "gbt-deepseek-loop.json";
const TICK_MS = Number(process.env.GBT_DS_LOOP_TICK_MS || 3000);
const MAX_ROUNDS = Number(process.env.GBT_DS_LOOP_MAX || 40);
const EXEC_TIMEOUT_MS = Number(process.env.GBT_DS_LOOP_EXEC_TIMEOUT_MS || 120000);

/* ── 纯函数（可单测，不依赖 electron）────────────────────────────────── */

/** 从文本里抽 ```gbt 指令块（与 Python 桥同一套行级规则；```gbt-result 不算）。 */
function extractBlocks(text) {
  const lines = String(text == null ? "" : text).split(/\r?\n/);
  const out = [];
  const fenceAt = (line) => {
    let idx = line.indexOf("```gbt");
    while (idx !== -1) {
      const after = line.charAt(idx + 6);
      if (!after || !/[A-Za-z0-9_-]/.test(after)) return idx;
      idx = line.indexOf("```gbt", idx + 1);
    }
    return -1;
  };
  let i = 0;
  while (i < lines.length) {
    const idx = fenceAt(lines[i]);
    if (idx < 0) { i += 1; continue; }
    let rest = lines[i].slice(idx + 6).trim();
    if (rest && !rest.startsWith("{")) {
      const parts = rest.split(/\s+/);
      rest = parts.length > 1 ? rest.replace(/^\S+\s*/, "").trim() : "";
    }
    if (rest.startsWith("{")) {
      const a = rest.indexOf("{");
      const b = rest.lastIndexOf("}");
      if (a >= 0 && b > a) out.push(rest.slice(a, b + 1));
      i += 1;
      continue;
    }
    i += 1;
    const buf = [];
    while (i < lines.length) {
      if (lines[i].trim() === "```") break;
      buf.push(lines[i]);
      i += 1;
    }
    out.push(buf.join("\n"));
    i += 1;
  }
  return out;
}

function hashText(s) {
  return crypto.createHash("sha256").update(String(s), "utf8").digest("hex").slice(0, 16);
}

/** 读页面的 JS：取最新一条**正文**回复（跳过 think/reason 祖先链）。 */
const READ_JS = `(function(){
  try {
    var nodes = Array.prototype.slice.call(document.querySelectorAll('[class*="ds-markdown"]'));
    var msgs = nodes.filter(function(n){
      for (var p = n; p; p = p.parentElement) {
        var c = "" + (p.className || "");
        if (/think|reason/i.test(c)) return false;
      }
      return true;
    });
    if (!msgs.length) return { ok: false, why: "no-message-node" };
    var last = msgs[msgs.length - 1];
    return { ok: true, count: msgs.length, text: (last.innerText || "").slice(0, 20000) };
  } catch (e) { return { ok: false, why: String(e).slice(0, 120) }; }
})()`;

/** 数会话条数（用来判「新对话还没装触手」）。 */
const COUNT_JS = `(function(){
  try {
    var n = document.querySelectorAll('[class*="ds-markdown"]').length;
    var user = document.querySelectorAll('[class*="fbb737a4"], [class*="chat-message"]').length;
    return { ok: true, assistant: n, user: user };
  } catch (e) { return { ok: false, why: String(e).slice(0, 100) }; }
})()`;

/** 写输入框并发送的 JS（React 受控组件：原生 setter + input 事件 + Enter）。 */
function sendJs(text) {
  return `(function(){
  try {
    var ta = document.querySelector('textarea#chat-input') || document.querySelector('textarea');
    if (!ta) return { ok: false, why: "no-textarea" };
    var setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
    setter.call(ta, ${JSON.stringify(text)});
    ta.dispatchEvent(new Event("input", { bubbles: true }));
    ta.focus();
    ta.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true }));
    return { ok: true, len: ta.value.length };
  } catch (e) { return { ok: false, why: String(e).slice(0, 120) }; }
})()`;
}

/* ── 回路本体 ─────────────────────────────────────────────────────────── */

const state = {
  win: null,
  userData: "",
  enabled: false,
  timer: null,
  busy: false,
  rounds: 0,
  lastHash: "",
  equippedHash: "",
  /** 连续「读不到页面」次数：页面挂了（CloudFront 错误页/断网）时累计，到阈值自动重载自愈。 */
  noTextTicks: 0,
  reloads: 0,
  lastNote: "未启动",
  logFile: "",
};

function log(line) {
  const row = "[" + new Date().toISOString().slice(0, 19) + "] " + line;
  state.lastNote = line;
  try {
    if (state.logFile) fs.appendFileSync(state.logFile, row + "\n", "utf8");
  } catch (err) { /* 记不上账不许弄崩回路 */ }
}

function readCfg() {
  try {
    return JSON.parse(fs.readFileSync(path.join(state.userData, CFG_NAME), "utf8"));
  } catch (err) {
    return null;
  }
}

/** 从桥路径反推仓根（桥在 <repo>/tools/codex-scripts/deepseek_bridge.py）。 */
function repoOf(cfg) {
  if (!cfg || !cfg.bridge) return "";
  return path.resolve(path.dirname(cfg.bridge), "..", "..");
}

function pauseFile(cfg) {
  const repo = repoOf(cfg);
  return repo ? path.join(repo, "state", "deepseek_bridge", "PAUSE") : "";
}

function feedbackFile(cfg) {
  const repo = repoOf(cfg);
  return repo ? path.join(repo, "state", "deepseek_bridge", "last_feedback.md") : "";
}

function register(win, opts) {
  state.win = win;
  state.userData = (opts && opts.userData) || "";
  state.logFile = state.userData ? path.join(state.userData, "deepseek-loop.log") : "";
  const cfg = readCfg();
  log(cfg ? "回路注册：配置就位（bridge=" + cfg.bridge + "）"
          : "回路注册：**未配置** —— 待运行 deepseek_bridge.py feed/status 写入 " + CFG_NAME);
  /* 🔴 默认**关闭待命**（2026-10-04 实测改）：DeepSeek 风控对 Electron 内核弹
     「使用环境异常…建议使用我们的官方产品」（无痕与持久档**同弹**，见 chat-probe 对照），
     在官方点名异常的环境里自动跑是给主人账号添风险 ⇒ 需要主人托盘点头才开。
     正路：对话面放主人的 Chrome（Nanobrowser 扩展驱动），执行侧仍走 watch/门。 */
  state.enabled = false;
  log("回路待命（默认关）：要开请托盘点「触手自主执行」——建议对话面用你的 Chrome（官方环境）");
  startTimer();
}

function startTimer() {
  if (state.timer) clearInterval(state.timer);
  state.timer = setInterval(tick, TICK_MS);
  if (state.timer.unref) state.timer.unref();
}

function stop() {
  if (state.timer) clearInterval(state.timer);
  state.timer = null;
  state.enabled = false;
  log("回路已停");
}

function setEnabled(on) {
  state.enabled = !!on;
  state.rounds = 0;                    /* 重开时清轮次，给足预算 */
  log(state.enabled ? "回路开启（自主运行）" : "回路关闭（手动）");
  return state.enabled;
}

function status() {
  const cfg = readCfg();
  return {
    enabled: state.enabled,
    configured: !!cfg,
    rounds: state.rounds,
    maxRounds: MAX_ROUNDS,
    lastNote: state.lastNote,
    logFile: state.logFile,
  };
}

function tick() {
  if (!state.enabled || state.busy || !state.win || state.win.isDestroyed()) return;
  const cfg = readCfg();
  if (!cfg || !cfg.bridge) { return; }                     /* 未配置：不在日志里刷屏 */
  const pf = pauseFile(cfg);
  if (pf && fs.existsSync(pf)) { state.lastNote = "急停闸生效（PAUSE）"; return; }
  if (state.rounds >= MAX_ROUNDS) {
    state.enabled = false;
    log("已达轮次上限 " + MAX_ROUNDS + " —— 回路自动停（要续跑：托盘重开或重启）");
    return;
  }
  state.busy = true;
  /* 先看这轮对话是不是空的（新对话）——空 ⇒ **自动给她装上触手**（把能力清单作为
     她的第一条上下文送进去），主人再不用手动粘清单。装过一次（哈希记档）就不再装。 */
  state.win.webContents.executeJavaScript(COUNT_JS, true).then((c) => {
    if (c && c.ok && c.assistant === 0 && c.user === 0 && equipOnce(cfg)) return;
    return runRead(cfg);
  }).catch((e) => { log("计数异常：" + String(e).slice(0, 140)); state.busy = false; });
}

/** 自动装触手：把身份+全部能力清单当第一条消息发出去（每次新对话一次）。 */
function equipOnce(cfg) {
  const repo = repoOf(cfg);
  const mf = repo ? path.join(repo, "state", "deepseek_bridge", "tool_manifest.md") : "";
  let text = "";
  try { text = fs.readFileSync(mf, "utf8"); } catch (e) { text = ""; }
  if (!text) { log("自动装触手：读不到清单 " + mf + "（先跑 deepseek_bridge.py manifest）"); return false; }
  const h = hashText(text);
  if (h === state.equippedHash) return false;               /* 已装过同一份，不重复发 */
  state.win.webContents.executeJavaScript(sendJs(text), true).then((s) => {
    if (s && s.ok) {
      state.equippedHash = h;                               /* 🔴 只在**真送出**后记哈希：
                                                               页面未载完（no-textarea）时失败
                                                               必须留机会下轮重试 ——
                                                               实测踩过：先记哈希 ⇒ 永不重试。 */
      state.noTextTicks = 0;
      log("自动装触手：能力清单已作为首条消息送出（" + text.length + " 字）");
    } else {
      noteNoText(s && s.why);
    }
    state.busy = false;
  }).catch((e) => { noteNoText(String(e).slice(0, 120)); state.busy = false; });
  return true;
}

/** 页面读不到时的自愈：连续多轮读不到 ⇒ 重载一次（有界 3 次）。 */
function noteNoText(why) {
  state.noTextTicks += 1;
  if (state.noTextTicks < 6) {
    log("页面暂不可读（" + (why || "unknown") + "）第 " + state.noTextTicks + " 轮 —— 就绪后自动重试");
    return;
  }
  if (state.reloads >= 3) {
    log("页面持续不可读且重载已用满 3 次（上游多半在拦，实测 CloudFront 403）—— "
        + "**回路自停等人**：请主人看一眼（换网络/稍后重试/托盘重开）");
    state.enabled = false;                                  /* 真的停下：不空转、不刷屏、不刷站 */
    return;
  }
  state.reloads += 1;
  state.noTextTicks = 0;
  log("页面连续不可读 ⇒ 自动重载第 " + state.reloads + " 次（自愈）");
  try { state.win.reload(); } catch (e) { log("重载失败：" + String(e).slice(0, 120)); }
}

function runRead(cfg) {
  state.win.webContents.executeJavaScript(READ_JS, true).then((r) => {
    if (!r || !r.ok || !r.text) { noteNoText((r && r.why) || "empty"); state.busy = false; return; }
    state.noTextTicks = 0;
    const blocks = extractBlocks(r.text);
    if (!blocks.length) { state.busy = false; return; }
    const h = hashText(r.text);
    if (h === state.lastHash) { state.busy = false; return; }
    state.lastHash = h;
    state.rounds += 1;
    log("第 " + state.rounds + " 轮：读到回复 " + r.text.length + " 字 · 指令块 " + blocks.length + " 个 → 过桥执行");
    const tmp = path.join(state.userData, "round-" + state.rounds + ".md");
    try { fs.writeFileSync(tmp, r.text, "utf8"); } catch (err) { log("写临时件失败：" + err.message); state.busy = false; return; }
    const args = (cfg.pythonArgs || ["-3.14"]).concat([cfg.bridge, "exec", "--file", tmp, "--execute"]);
    execFile(cfg.python || "py", args, { timeout: EXEC_TIMEOUT_MS, windowsHide: true }, (err, stdout) => {
      if (err) {
        log("桥执行失败（如实记录，回路继续）：" + String(err.message || err).slice(0, 200));
        state.busy = false;
        return;
      }
      const summary = String(stdout || "").trim().split(/\r?\n/).slice(-3).join(" | ").slice(0, 300);
      log("桥回执：" + (summary || "(空)"));
      let fb = "";
      try { fb = fs.readFileSync(feedbackFile(cfg), "utf8"); } catch (e) { fb = ""; }
      if (!fb) { log("反馈块读不到（last_feedback.md 缺失）—— 本轮不自动回喂"); state.busy = false; return; }
      state.win.webContents.executeJavaScript(sendJs(fb), true).then((s) => {
        log(s && s.ok ? "反馈已自动回喂（输入 " + s.len + " 字并回车）"
                      : "回喂失败：" + ((s && s.why) || "unknown"));
        state.busy = false;
      }).catch((e2) => { log("回喂注入异常：" + String(e2).slice(0, 160)); state.busy = false; });
    });
  }).catch((e) => {
    log("读页面异常：" + String(e).slice(0, 160));
    state.busy = false;
  });
}

module.exports = {
  CFG_NAME,
  register,
  stop,
  setEnabled,
  status,
  extractBlocks,        /* 纯函数：单测用 */
  hashText,
  _readJs: READ_JS,
  _sendJs: sendJs,
};
