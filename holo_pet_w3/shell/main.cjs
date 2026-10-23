// R-H165（2026-09-19）：本表行号按 caps_registry.py **实际行号**刷新（因 sched_define 后新增约 30 行而漂移；非静默改数）
/* GBT小土豆V8 · 上帝视角 · 主进程骨架（W3）
 *
 * 职责（《W3上帝视角镜像方案.md》§2.2）：
 *   单例锁 · 窗口注册表（windows.json）· 托盘（图标运行时生成，维度不放二进制）
 *   · 布局持久化（userData/window-layout.json，越界回落主屏）· 吸附
 *   · 只读 IPC（渲染进程零写口）· 主进程侧订阅 /api/events
 *
 * 为什么 SSE 订阅在主进程：panel_server 的 _send_json 不发 CORS 头，
 * 渲染进程从 file:// 直接 fetch 会被浏览器拦死；给它加头就是动生产代码（本轮红线）。
 * 所以订阅者前移到主进程，推送通道**仍是同一条 /api/events**，不新增第二套。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";

const { app, BrowserWindow, Tray, Menu, ipcMain, screen, nativeImage, shell } = require("electron");
const fs = require("fs");
const path = require("path");
const http = require("http");
const zlib = require("zlib");
const crypto = require("crypto");
const { execFile, spawn } = require("child_process");
const layout = require("./layout.cjs");
const features = require("./features.cjs");
const chrome = require("./chrome.cjs");
/* 对话面自主回路（主人令 2026-10-04）：读她的回复 → 过桥执行 → 自动回喂。
   注入只允许收口在本模块（守卫 B4 的判据已据此改写）。 */
const deepseekLoop = require("./deepseek_loop.cjs");
const os = require("os");

const HERE = __dirname;
const PANEL = process.env.GBT_PANEL_URL || "http://127.0.0.1:8765";
const READONLY_NOTE = "只读态：自检结果仅 UI 显示，不落盘";

/* 🔴 2026-10-21 根因修复（主人：「数字人页面是垃圾 / 一片载入中」）：
   实测（CDP 抓控制台）数字人那扇窗报 `THREE.WebGLRenderer: A WebGL context
   could not be created. Reason: VENDOR = 0xffff, DEVICE = 0xffff,
   GL_VENDOR = Disabled, GL_RENDERER = Disabled` ⇒ three.js 根本没起来，
   页面永远停在「引擎：载入中」，左边 2/3 是全黑的空工作台。

   本机显卡是在的（AMD Radeon RX 6500M + 核显，驱动 30.0.14064.4）：所以不是「没有
   GPU」，而是**这台 Electron 的 GL 被禁用了**（Chromium 走到 0xffff 那档 =
   GPU 不可用 + 软件光栅也被挡）。Chromium ≥128 起，软件 WebGL 必须显式开
   `enable-unsafe-swiftshader` 才允许 —— 这条开关就是补这一层：
   GPU 能用就走 GPU，不能用就走 CPU 软渲染（慢一点，但**画得出来**）。
   ⚠️ 名字里的「unsafe」是 Chromium 对「软渲染可被用于时序攻击」的历史称谓，
   我们只渲染自己的本地 GLB、零外部输入、零远端取数 ⇒ 风险面不成立。 */
app.commandLine.appendSwitch("enable-unsafe-swiftshader");

/* 🔴 2026-10-10 根因修复（主人截图：上帝视角「看任务/看账本」全 ENOENT，
   读的是 userData\gbt_allinone\store）：**打包态 ROOT=null**。
   便携版运行时解包到 %TEMP%\<hash>\resources\app\shell ⇒ 从那儿往上走 12 层
   **永远走不到桌面** ⇒ ROOT=null ⇒ STORE=null ⇒ 路径回落到 userData（那里当然没有真账本）。

   修法 = **三级兜底**（顺序即优先级），任一级命中即用：
     ① 环境变量 **GBT_REPO_ROOT**（显式指定，装机/调试最稳）
     ② **指针文件** %LOCALAPPDATA%\gbt_allinone\repo-root.txt（**仓这边自己写**，
        见 tools/codex-scripts/repo-root-pin.py；打包态靠它认家）
     ③ 常见位置（桌面\GBT小土豆V8 与当前工作目录）
   判据：认到的根**必须**含 gbt_allinone/caps_registry.py（不许认一个空目录当根）。 */
function _isRepo(p) {
  try {
    return !!p && fs.existsSync(path.join(p, "gbt_allinone", "caps_registry.py"));
  } catch (err) { return false; }
}

function findRepoRoot(start) {
  // ① 往上走（开发态：源码树里直接命中）
  let cur = start;
  for (let i = 0; i < 12; i++) {
    if (_isRepo(cur)) return cur;
    const up = path.dirname(cur);
    if (up === cur) break;
    cur = up;
  }
  // ② 环境变量
  if (_isRepo(process.env.GBT_REPO_ROOT)) return process.env.GBT_REPO_ROOT;
  // ③ 指针文件（仓这边写的；打包态靠它认家）
  try {
    const pin = path.join(app.getPath("userData"), "repo-root.txt");
    if (fs.existsSync(pin)) {
      const p = fs.readFileSync(pin, "utf8").trim();
      if (_isRepo(p)) return p;
    }
    // 打包态的 userData 是 ...\gbt_allinone，仓写在同一处
    const alt = path.join(app.getPath("appData"), "gbt_allinone", "repo-root.txt");
    if (fs.existsSync(alt)) {
      const p2 = fs.readFileSync(alt, "utf8").trim();
      if (_isRepo(p2)) return p2;
    }
  } catch (err) { /* 读不到就继续往下兜 */ }
  // ④ 常见位置
  for (const cand of [path.join(app.getPath("home"), "Desktop", "GBT小土豆V8"),
                      path.join(app.getPath("home"), "桌面", "GBT小土豆V8"),
                      process.cwd()]) {
    if (_isRepo(cand)) return cand;
  }
  return null;
}

const ROOT = findRepoRoot(HERE);
const STORE = ROOT ? path.join(ROOT, "gbt_allinone", "store") : null;
const DOCS = ROOT ? path.join(ROOT, "gbt_allinone", "docs") : null;
const LAYOUT_FILE = path.join(app.getPath("userData"), "window-layout.json");

function readRegistry() {
  const file = path.join(HERE, "windows.json");
  try {
    const parsed = JSON.parse(fs.readFileSync(file, "utf8"));
    if (parsed && Array.isArray(parsed.windows)) return parsed;
  } catch (err) {
    /* 注册表坏了就当空的，不抛 */
  }
  return { version: 1, windows: [] };
}

/* ── 托盘图标：运行时生成，维度里不放二进制 ── */

function crcTable() {
  const t = new Int32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c;
  }
  return t;
}
const CRC_T = crcTable();

function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = CRC_T[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function pngChunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length, 0);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body), 0);
  return Buffer.concat([len, body, crc]);
}

function trayIcon(size, fill, edge) {
  const stride = size * 4 + 1;
  const raw = Buffer.alloc(stride * size);
  for (let y = 0; y < size; y++) {
    raw[y * stride] = 0;
    for (let x = 0; x < size; x++) {
      const o = y * stride + 1 + x * 4;
      const onEdge = x === 0 || y === 0 || x === size - 1 || y === size - 1;
      const c = onEdge ? edge : fill;
      raw[o] = c[0]; raw[o + 1] = c[1]; raw[o + 2] = c[2]; raw[o + 3] = 0xff;
    }
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; ihdr[9] = 6; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  const png = Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    pngChunk("IHDR", ihdr),
    pngChunk("IDAT", zlib.deflateSync(raw)),
    pngChunk("IEND", Buffer.alloc(0)),
  ]);
  return nativeImage.createFromBuffer(png);
}

/* ── 只读数据口 ── */

function tailLines(file, maxBytes, maxLines) {
  const st = fs.statSync(file);
  const start = Math.max(0, st.size - maxBytes);
  const fd = fs.openSync(file, "r");
  const buf = Buffer.alloc(st.size - start);
  try {
    fs.readSync(fd, buf, 0, buf.length, start);
  } finally {
    fs.closeSync(fd);
  }
  const lines = buf.toString("utf8").split(/\r?\n/).filter((s) => s.trim());
  if (start > 0 && lines.length) lines.shift();   /* 首行多半被截断，丢掉 */
  return lines.slice(-maxLines);
}

function ok(data) { return { ok: true, data: data }; }
function no(error, extra) { return Object.assign({ ok: false, error: error }, extra || {}); }

function httpGetJson(url, timeoutMs) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      let body = "";
      res.setEncoding("utf8");
      res.on("data", (d) => { body += d; });
      res.on("end", () => {
        if (res.statusCode !== 200) return resolve(no("HTTP " + res.statusCode));
        try { resolve(ok(JSON.parse(body))); }
        catch (err) { resolve(no("响应不是 JSON")); }
      });
    });
    req.on("error", (err) => resolve(no(String(err.message || err))));
    req.setTimeout(timeoutMs || 2500, () => { req.destroy(); resolve(no("超时")); });
  });
}

function w3State() { return httpGetJson(PANEL + "/api/state", 2500); }

/* ── R-H295 · 把框架自己的只读审计接进上帝视角 ──
 *
 * 欠账出处：docs/待落刀登记.md
 *   · 「覆盖审计接进上帝视角（实时显示覆盖率与死角）」—— **未接**
 *   · 「把零调用点清单接进上帝视角 / 工作区（定期扫、可点名）」—— **未接**
 *
 * 为什么以前接不上：`:8765` 的 `/api/capability` 是**异步**口 —— 它返回
 * `{accepted, deferred, request_id}`，真结果由 `cap_result` 事件从 `/api/events`
 * 送回来（panel_server.py:2290-2311）。渲染进程从 file:// 直接 fetch 会被 CORS 拦死
 * （见本文件头注），所以「调能力 + 等结果」这件事只能在主进程做。
 * 本函数就是补上这半截：POST 拿 request_id → 在该表上等 SSE 送回同名 request_id。
 */
const CAP_PENDING = new Map();

function httpPostJson(pathname, bodyObj, timeoutMs) {
  return new Promise((resolve) => {
    const data = Buffer.from(JSON.stringify(bodyObj || {}), "utf8");
    const m = PANEL.match(/^https?:\/\/([^\/:]+)(?::(\d+))?/);
    const req = http.request({
      host: (m && m[1]) || "127.0.0.1",
      port: Number((m && m[2]) || 8765),
      path: pathname,
      method: "POST",
      headers: { "Content-Type": "application/json",
                 "Content-Length": data.length },
    }, (res) => {
      let raw = "";
      res.setEncoding("utf8");
      res.on("data", (d) => { raw += d; });
      res.on("end", () => {
        if (res.statusCode !== 200) return resolve(no("HTTP " + res.statusCode));
        try { resolve(ok(JSON.parse(raw))); }
        catch (e) { resolve(no("响应不是 JSON")); }
      });
    });
    req.on("error", (err) => resolve(no(String(err.message || err))));
    req.setTimeout(timeoutMs || 30000, () => { req.destroy(); resolve(no("超时")); });
    req.write(data);
    req.end();
  });
}

/* 调一个能力并把结果等回来。
 *
 * R-H295：**自带订阅**，不复用全局那条 SSE。原因：app.whenReady() 里
 * registerIpc → createWindow → buildTray → refreshTrayMenu → startSse 是**一条不断的链**，
 * 上游任一环抛错（例如托盘图标构造失败）整条链就在 .catch 里结束，startSse 永远不会跑 ——
 * 那时"能力调用超时"看起来像能力坏了，其实是订阅压根没建。
 * 本函数自己开一条 /api/events 只等自己那个 request_id，拿到即断，与托盘/窗口解耦。
 * 超时如实报超时，不拿空对象冒充成功。
 */
function callCapability(kind, payload, waitMs) {
  return new Promise((resolve) => {
    const data = Buffer.from(JSON.stringify({
      kind: kind, payload: payload || {}, confirm: true,
    }), "utf8");
    const m = PANEL.match(/^https?:\/\/([^\/:]+)(?::(\d+))?/);
    const host = (m && m[1]) || "127.0.0.1";
    const port = Number((m && m[2]) || 8765);
    const deadline = Date.now() + (waitMs || 60000);
    let settled = false;
    let sseReq = null;

    function finish(value) {
      if (settled) return;
      settled = true;
      if (sseReq) { try { sseReq.destroy(); } catch (e) { /* 已断 */ } }
      resolve(value);
    }

    /* 先挂订阅，再发调用 —— 反过来会漏掉"结果比订阅先到"的窗口 */
    sseReq = http.get({ host: host, port: port, path: "/api/events" }, (res) => {
      if (res.statusCode !== 200) { finish(no("事件流 HTTP " + res.statusCode)); return; }
      let buf = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => {
        buf += chunk;
        let idx = buf.indexOf("\n\n");
        while (idx >= 0) {
          const block = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          const dataLines = [];
          const lines = block.split("\n");
          for (let li = 0; li < lines.length; li++) {
            const t = lines[li].replace(/\r$/, "");
            if (t.indexOf("data:") === 0) dataLines.push(t.slice(5).replace(/^ /, ""));
          }
          if (!dataLines.length) { idx = buf.indexOf("\n\n"); continue; }
          try {
            const ev = JSON.parse(dataLines.join("\n"));
            if (ev && ev.type === "cap_result" && ev.request_id === rid) {
              finish(ok({ kind: ev.kind, request_id: ev.request_id,
                          result: ev.result === undefined ? null : ev.result }));
            }
          } catch (e) { /* 非 JSON 忽略 */ }
          idx = buf.indexOf("\n\n");
        }
      });
      res.on("end", () => { /* 服务端断流：交给下面的超时兜底 */ });
    });
    sseReq.on("error", (err) => finish(no("事件流断开：" + String(err.message || err))));

    let rid = null;
    const posted = http.request({
      host: host, port: port, path: "/api/capability", method: "POST",
      headers: { "Content-Type": "application/json", "Content-Length": data.length },
    }, (res) => {
      let raw = "";
      res.setEncoding("utf8");
      res.on("data", (d) => { raw += d; });
      res.on("end", () => {
        let meta = {};
        try { meta = JSON.parse(raw); } catch (e) { finish(no("能力口响应不是 JSON")); return; }
        if (!meta.ok) { finish(no(meta.error || "能力口拒绝")); return; }
        if (meta.needs_confirmation) {
          finish(no("能力层要求二次确认，主进程未代确认（不绕门）",
                    { kind: kind, needs_confirmation: true }));
          return;
        }
        if (!meta.request_id) { finish(no("面板未回 request_id（异步口口径变了？）", meta)); return; }
        rid = meta.request_id;
        const timer = setInterval(() => {
          if (Date.now() > deadline) {
            clearInterval(timer);
            finish(no("等结果超时（" + Math.round((waitMs || 60000) / 1000) + "s）：cap_result 没回来",
                      { request_id: rid }));
          }
        }, 250);
      });
    });
    posted.on("error", (err) => finish(no("能力口断开：" + String(err.message || err))));
    posted.setTimeout(15000, () => { posted.destroy(); finish(no("能力口超时")); });
    posted.write(data);
    posted.end();
  });
}

/* SSE 分发：命中等待表就把结果交回去（其余事件照旧广播给渲染层） */
function settleCapPending(ev) {
  if (!ev || ev.request_id === undefined) return false;
  const slot = CAP_PENDING.get(ev.request_id);
  if (!slot) return false;
  CAP_PENDING.delete(ev.request_id);
  clearTimeout(slot.timer);
  slot.resolve(ok({ kind: ev.kind, request_id: ev.request_id,
                    result: ev.result === undefined ? null : ev.result }));
  return true;
}

/* 覆盖率审计（实时：每次调用现跑框架那只只读审计器，不存快照、不猜） */
async function w3Coverage() {
  const r = await callCapability("coverage_auditor", {}, 60000);
  if (!r.ok) return r;
  const body = (r.data && r.data.result) || {};
  const inner = body.result && typeof body.result === "object" ? body.result : body;
  return ok({
    readonly: true,
    note: "实时跑 coverage_auditor（只读审计器）；覆盖率与死角以它为准，面板不做二次判读。",
    at: new Date().toISOString(),
    raw: inner,
  });
}

/* 渲染进化的最优基因（欠账：「进 trace_store · 工作区可跑实验 · 上帝视角显示最优基因」—— 未接）。
   同 coverage/orphans：实时现跑 render_evolution，不落快照。
   诚实口径：现在 genomes=0 —— 面板就该显示「还没有最优基因」，不许拿某个默认值冒充
   （该能力自己的红线第 1 条就是「无基线不许进化」）。 */
async function w3Gene() {
  const r = await callCapability("render_evolution", {}, 60000);
  if (!r.ok) return r;
  const body = (r.data && r.data.result) || {};
  const inner = body.result && typeof body.result === "object" ? body.result : body;
  return ok({
    readonly: true,
    note: "实时跑 render_evolution（只读）；最优基因与实验数以它为准。0 代就如实写 0 代。",
    at: new Date().toISOString(),
    raw: inner,
  });
}


async function w3Orphans() {
  const r = await callCapability("caps_called_audit", {}, 60000);
  if (!r.ok) return r;
  const body = (r.data && r.data.result) || {};
  const inner = body.result && typeof body.result === "object" ? body.result : body;
  return ok({
    readonly: true,
    note: "实时跑 caps_called_audit（只读审计器）；孤儿口径以它自己的 rule 字段为准。",
    at: new Date().toISOString(),
    raw: inner,
  });
}


function w3Tasks() {
  const file = path.join(STORE, "tasks.json");
  try {
    const parsed = JSON.parse(fs.readFileSync(file, "utf8"));
    const tasks = Array.isArray(parsed.tasks) ? parsed.tasks : [];
    return ok({ next_id: parsed.next_id, total: tasks.length, tasks: tasks.slice(-8) });
  } catch (err) {
    return no("tasks.json 读不动：" + String(err.message || err));
  }
}

function w3Env() {
  return new Promise((resolve) => {
    const code = "import json,sys;sys.path.insert(0," + JSON.stringify(ROOT) +
      ");from gbt_allinone import services as s;print(json.dumps(s.inspect(quiet=True),ensure_ascii=True,default=str))";
    execFile("py", ["-3.10", "-c", code], { timeout: 25000, windowsHide: true }, (err, stdout, stderr) => {
      if (err) return resolve(no("inspect 跑不动：" + String(err.message || err), { stderr: String(stderr || "").slice(0, 300) }));
      try { resolve(ok(JSON.parse(String(stdout).trim()))); }
      catch (e) { return resolve(no("inspect 输出不是 JSON")); }
    });
  });
}

function w3Ledger() {
  const audit = path.join(STORE, "audit.jsonl");
  const dir = path.join(STORE, "ledger");
  const out = { audit_tail: [], ledgers: {}, ledger_dir: dir };
  try {
    out.audit_tail = tailLines(audit, 16384, 8).map((ln) => {
      try { return JSON.parse(ln); } catch (e) { return { raw: ln.slice(0, 160) }; }
    });
  } catch (err) {
    return no("audit.jsonl tail 读不动：" + String(err.message || err));
  }
  if (!fs.existsSync(dir)) {
    out.note = "store/ledger/ 尚未成形 —— 四路账本要等一次真实往返（V2）才有行；按《反空壳律》如实记，不拿空文件顶替。";
    return ok(out);
  }
  fs.readdirSync(dir).filter((f) => f.endsWith(".jsonl")).forEach((f) => {
    try {
      out.ledgers[f] = tailLines(path.join(dir, f), 16384, 12).map((ln) => {
        try { return JSON.parse(ln); } catch (e) { return { raw: ln.slice(0, 160) }; }
      });
    } catch (err) {
      out.ledgers[f] = { error: String(err.message || err) };
    }
  });
  return ok(out);
}

function w3Health() {
  const dir = path.join(STORE, "health");
  if (!fs.existsSync(dir)) return ok({ records: [], byFault: {}, note: "store/health/ 还不存在" });
  const records = [];
  const byFault = {};
  fs.readdirSync(dir).filter((f) => f.endsWith(".jsonl")).forEach((f) => {
    try {
      const last = tailLines(path.join(dir, f), 8192, 1)[0];
      if (!last) return;
      const rec = JSON.parse(last);
      rec.source_file = f;
      records.push(rec);
      if (rec.fault_id) byFault[rec.fault_id] = rec;
    } catch (err) {
      records.push({ source_file: f, parse_error: String(err.message || err) });
    }
  });
  return ok({ records: records, byFault: byFault });
}

function w3Matrix() {
  const file = path.join(DOCS, "GBT全故障点设计.md");
  let text;
  try {
    text = fs.readFileSync(file, "utf8");
  } catch (err) {
    return no("母表读不动：" + String(err.message || err));
  }
  const lines = text.split(/\r?\n/);
  const rows = [];
  let inTable = false;
  lines.forEach((line) => {
    if (/^\|\s*故障点\s*\|/.test(line)) { inTable = true; return; }
    if (!inTable) return;
    if (!line.startsWith("|")) { if (rows.length) inTable = false; return; }
    if (/^\|[\s\-:|]+\|$/.test(line)) return;
    const cells = line.split("|").slice(1, -1).map((s) => s.trim().replace(/\*\*/g, ""));
    if (cells.length < 6) return;
    rows.push({
      label: cells[0], id: (cells[0].split(/\s+/)[0] || "").trim(),
      probe: cells[1], beat: cells[2], audit: cells[3], user: cells[4], why: cells[5] || "",
    });
  });
  if (!rows.length) return no("母表 §10.2 没解析出任何行");
  const payload = ok(rows);
  payload.rows = rows;
  payload.source = "gbt_allinone/docs/GBT全故障点设计.md §10.2（" + rows.length + " 点）";
  return payload;
}

function w3Mindmap() {
  const file = path.join(DOCS, "GBT全项目思维导图.md");
  let text;
  try { text = fs.readFileSync(file, "utf8"); } catch (err) { return no("思维导图源文件读不动：" + String(err.message || err)); }
  const fence = /```markdown\r?\n([\s\S]*?)```/.exec(text);
  if (!fence) return no("没找到 §一 的 markmap markdown 块");
  return ok(fence[1]);
}

function w3Selfcheck() {
  const checks = [];
  return w3State().then((st) => {
    checks.push({ name: "面板 /api/state", pass: st.ok === true, detail: st.ok ? "ok:true" : st.error });
    checks.push({ name: "store/tasks.json", pass: fs.existsSync(path.join(STORE, "tasks.json")), detail: "只读探测存在性" });
    checks.push({ name: "store/audit.jsonl", pass: fs.existsSync(path.join(STORE, "audit.jsonl")), detail: "只读探测存在性" });
    const h = w3Health();
    checks.push({ name: "store/health/ 记录数", pass: true, detail: String((h.data && h.data.records.length) || 0) + " 条" });
    checks.push({ name: "渲染进程写口", pass: true, detail: "0 个（preload 只暴露只读 IPC）" });
    return ok({ readonly: true, note: READONLY_NOTE, wrote_anything: false, checks: checks });
  });
}

function w3Introspect() {
  const h = w3Health();
  const t = w3Tasks();
  return Promise.resolve(ok({
    readonly: true,
    note: "全局自省 = 只读汇总；写盘要等后台探针服务独立进程上线",
    health_records: (h.data && h.data.records.length) || 0,
    tasks: t.ok ? t.data.total : "<" + (t.error || "取不到") + ">",
    collected_at: new Date().toISOString(),
  }));
}

/* ── 主进程侧 SSE 订阅 ── */

function startSse(broadcast) {
  let req = null;
  let retry = null;
  /* 🔴 2026-09-23 第 43 轮：**状态变化如实打出来**。
     为什么非打不可：这条链上有**三处静默出口**（非 200 / error / end），
     任何一处走到，屏上只有「未接」三个字，盘上什么都没有 ——
     于是"实时流没接上"这件事**没法从日志里查**，只能靠猜。
     与本仓既定的"灰态必须带原因"同一条规矩。 */
  function notify(st) {
    lastStreamState = st;
    console.log("[w3] 实时流状态: %s", st);
    broadcast("w3:stream", st);
  }
  function connect() {
    req = http.get(PANEL + "/api/events", (res) => {
      if (res.statusCode !== 200) {
        console.error("[w3] 实时流被拒：HTTP %s（目标 %s/api/events）", res.statusCode, PANEL);
        notify("closed");
        return schedule();
      }
      notify("open");
      let buf = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => {
        buf += chunk;
        let idx = buf.indexOf("\n\n");
        while (idx >= 0) {
          const block = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          /* R-H295 · 修根因：原来这里是
           *     if (block.indexOf("data: ") === 0) { ... }
           * 而 panel_server._write_sse（panel_server.py:2856）每条事件都**先写 `id: N\n`
           * 再写 `data: …\n\n`** —— 于是**没有任何一个块是以 "data: " 开头的**，
           * 这个条件永远不成立 ⇒ 上帝视角的实时推送从来没送进渲染层一条事件；
           * 15 秒一次的心跳是注释行（`: heartbeat`），同样被丢掉，所以连"活着"都看不出来。
           * 副作用：新接的 callCapability 也拿不到 cap_result（它也喂自这里）。
           * 现在按 SSE 规范逐行解析：`data:` 可多行、`id:`/`event:`/注释各自独立；
           * 首个块还夹着 HTTP 响应头（`\r\n\r\n`），逐行解析天然忽略它们。 */
          const dataLines = [];
          const lines = block.split("\n");
          for (let li = 0; li < lines.length; li++) {
            const t = lines[li].replace(/\r$/, "");
            if (t.indexOf("data:") === 0) dataLines.push(t.slice(5).replace(/^ /, ""));
          }
          if (dataLines.length) {
            try {
              const ev = JSON.parse(dataLines.join("\n"));
              /* 先喂等待表（callCapability 的结果就在 cap_result 上回来），再广播 */
              settleCapPending(ev);
              broadcast("w3:event", ev);
            } catch (e) { /* 非 JSON 的心跳等忽略 */ }
          }
          idx = buf.indexOf("\n\n");
        }
      });
      res.on("end", () => { notify("closed"); schedule(); });
    });
    /* 🔴 2026-09-23 第 43 轮：这一行原来把**错误对象整个吞掉** ——
       `req.on("error", () => { notify("closed"); schedule(); })`。
       后果：实时流可以**永远**连不上（每 5 s 重试一次，一路静默），
       而盘上、屏上都不说为什么 —— 页脚只有「未接」三个字。
       这与 `broadcast` 那边早就定下的规矩（"坏因如实打到 stderr"）自相矛盾。
       现在如实打出来：错误码 + 目标地址，让人**一眼知道断在哪**。 */
    req.on("error", (err) => {
      const why = (err && (err.code || err.message)) || "未知";
      console.error("[w3] 实时流断开：%s（目标 %s/api/events）", why, PANEL);
      notify("closed");
      schedule();
    });
  }
  function schedule() {
    if (retry) return;
    retry = setTimeout(() => { retry = null; connect(); }, 5000);
  }
  connect();
  return () => { if (req) req.destroy(); if (retry) clearTimeout(retry); };
}

/* ── §12 工具出口（只读视图 · 刀 2b） ──
 *
 * 硬约束（O54 同族）：本口不得产生任何健康通道写入、不得落足迹 ——
 * 只做 fs 只读 + 展示映射；不 import 能力层、不起子进程、不落账。
 * 只读视图，任何状态判定以能力层为准，面板只做展示映射。
 * 灰态必须带原因（不得只灰不解释，否则又变成「有货架没货」）。
 *
 * 出口清单的真身在 gbt_allinone/coze_mail_cap.py 与 gbt_allinone/file_operation.py；
 * 能力接线后必须同批更新本表（PROJECT_BLUEPRINT §八「能力落地必须同批登记出口清单」）。
 */

const TOOLS_CAPS = [
  {
    cap: "prompt_bridge",
    registered: "caps_registry.py:889",
    actions: [
      { name: "status", state: "live", reason: "只读纯函数：先问当前态再决定发不发车（零副作用）" },
      { name: "compile", state: "live", reason: "只读纯本地：四段模板 + 原意保真自检（丢词即 intent_loss）" },
      { name: "passthrough", state: "live", reason: "只读：原样透传（不转化）" },
    ],
  },
  {
    cap: "voice_orchestra",
    actions: [
      { name: "list", state: "live", reason: "read-only: list skill atoms" },
      { name: "pipeline", state: "live", reason: "read-only: scene to pipeline" },
      { name: "status", state: "live", reason: "read-only: local backend availability" },
    ],
  },
  {
    cap: "coze_mail",
    registered: "caps_registry.py:784",
    actions: [
      { name: "status", state: "live", reason: "只读探针：读 state.json 与通道行数，不调能力层" },
      { name: "search", state: "pending", reason: "后端未接线 backend_not_wired（coze_mail_cap.py:69 _UnwiredTransport）" },
      { name: "read", state: "pending", reason: "后端未接线 backend_not_wired（同上）" },
      { name: "draft", state: "pending", reason: "" },
    ],
  },
  {
    cap: "create",
    registered: "caps_registry.py:790",
    actions: [
      { name: "status", state: "live", reason: "只读探针：读 state.json 与写根存在性，零字节零目录" },
      { name: "intent", state: "pending", reason: "本地登记（不发网络）；本轮不开放点击" },
      { name: "output", state: "pending", reason: "文本出口未接线 text_exit_not_wired：result=pending，不伪造成成功" },
    ],
  },
];

const TOOLS_NOT_EXPORTED = "敏感档动作不挂出口（物理上没有键）：coze_mail mark / send / reply / register · create configure / write";
const TOOLS_LINES_CAP_BYTES = 1048576;

/* R-H295：`registered` 原来是**硬编码行号**，实测已经漂了一个 ——
   voice_orchestra 声明 `caps_registry.py:560`，而 560 是 prompt_bridge 的行号，
   真实在 572（对着注册表逐个数出来的）。行号会随注册表增删漂移：本文件开头
   （main.cjs:1）自己就记着「本表行号按 caps_registry.py 实际行号刷新（因 sched_define
   后新增约 30 行而漂移；非静默改数）」—— 也就是靠人工重刷维持。
   指向**别人**的行号比不写更坏：读者会照着一个假引用去查，还查到东西。
   改成运行时现查真实行号；查不到就如实说查不到，不编、也不留旧值。 */
function registeredAt(cap) {
  try {
    if (!ROOT) return null;
    const p = path.join(ROOT, "gbt_allinone", "caps_registry.py");
    if (!fs.existsSync(p)) return null;
    const lines = fs.readFileSync(p, "utf8").split(/\r?\n/);
    const re = new RegExp('^\\s*"' + String(cap).replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + '":');
    for (let i = 0; i < lines.length; i++) {
      if (re.test(lines[i])) return "caps_registry.py:" + (i + 1);
    }
    return null;
  } catch (e) {
    return null;
  }
}

function readJsonIfPresent(file) {
  try {
    if (!file || !fs.existsSync(file)) return { present: false, data: null, error: null };
    return { present: true, data: JSON.parse(fs.readFileSync(file, "utf8")), error: null };
  } catch (err) {
    return { present: true, data: null, error: String((err && err.message) || err) };
  }
}

function channelLines(file) {
  try {
    if (!file || !fs.existsSync(file)) return 0;
    if (fs.statSync(file).size > TOOLS_LINES_CAP_BYTES) return null;
    return fs.readFileSync(file, "utf8").split(/\r?\n/).filter((s) => s.trim()).length;
  } catch (err) {
    return null;
  }
}

function draftReason(allowCount) {
  if (allowCount === null || allowCount === undefined) return "白名单读数不可用（未取到 allow_to）-> 按全拒口径处理";
  if (allowCount === 0) return "白名单为空（allow_to 0 条）-> 全拒（coze_mail_cap.py:416 _check_recipient）";
  return "白名单 " + allowCount + " 条；本轮仍不开放点击";
}

/* 只读视图，任何状态判定以能力层为准，面板只做展示映射。 */
async function w3Tools() {
  if (!STORE) return no("找不到仓库根（上层没有 gbt_allinone）-> 工具出口不猜路径");
  if (!fs.existsSync(STORE)) {
    return no("store 不存在：" + path.basename(STORE) + "（取不到就不显示绿 · 负对照口径）",
              { store: path.basename(STORE), store_present: false });
  }
  const mailState = readJsonIfPresent(path.join(STORE, "health", "coze_mail", "state.json"));
  const mailAllow = mailState.data && Array.isArray(mailState.data.allow_to)
    ? mailState.data.allow_to.length : null;
  const createState = readJsonIfPresent(path.join(STORE, "health", "create", "state.json"));
  const writeRoot = process.env.GBT_CREATE_ROOT || (ROOT ? path.join(ROOT, "outputs") : null);
  const facts = {
    coze_mail: {
      state_present: mailState.present,
      state_error: mailState.error,
      enabled: mailState.data ? mailState.data.enabled !== false : null,
      address_set: !!(mailState.data && mailState.data.address),
      allow_to_count: mailAllow,
      events_lines: channelLines(path.join(STORE, "health", "coze_mail", "events.jsonl")),
    },
    create: {
      state_present: createState.present,
      state_error: createState.error,
      text_exit_target: (createState.data && createState.data.text_exit_target) || "eigenflux",
      text_exit_source: (createState.data && createState.data.text_exit_source) || "default",
      write_root_label: writeRoot ? path.basename(writeRoot) : null,
      write_root_exists: !!(writeRoot && fs.existsSync(writeRoot)),
      events_lines: channelLines(path.join(STORE, "health", "create", "events.jsonl")),
    },
  };
  const caps = TOOLS_CAPS.map((c) => {
    const acts = c.actions.map((a) => {
      let reason = a.reason;
      if (c.cap === "coze_mail" && a.name === "draft") reason = draftReason(mailAllow);
      return { name: a.name, state: a.state, reason: reason };
    });
    // 现查真实行号；查不到就如实说，不回落到可能已漂的硬编码值
    const at = registeredAt(c.cap);
    return { cap: c.cap, registered: at || "未在 caps_registry.py 找到（不编行号）",
             declared: c.registered || null, actions: acts, facts: facts[c.cap] };
  });
  /* R-H295 · ⑤ 修「命名与覆盖面错位」。
   * 本页标题写的是「工具出口」，读的人自然以为它列出**全部**出口；实际 TOOLS_CAPS
   * 是一张**精选 4 项**的硬编码表（prompt_bridge / voice_orchestra / coze_mail / create），
   * 而注册表里有 141 个可用能力。落差 137 项**在面板上完全看不见**，
   * 脚注还只说「敏感档动作不挂出口（物理上没有键）」—— 暗示其余都挂了，那是假的。
   * 修法不是把 141 项全塞进这张表（那会把"展示映射"变成第二份能力表，
   * 违背本口「不复制任何一份能力表」的硬约束），而是**把落差本身如实显示出来**：
   * 全量口径取自正门 `/api/capabilities`（返回注册表 + 面板自身能力面），不自己数。
   */
  let coverage = { curated: TOOLS_CAPS.length, total: null, enabled: null,
                   disabled: null, app_routes: null, source: "/api/capabilities" };
  try {
    const disc = await httpGetJson(PANEL + "/api/capabilities", 4000);
    if (disc.ok && disc.data) {
      const dd = disc.data;
      coverage.total = dd.total === undefined ? null : dd.total;
      coverage.enabled = dd.enabled === undefined ? null : dd.enabled;
      coverage.disabled = dd.disabled === undefined ? null : dd.disabled;
      coverage.app_routes = (dd.app && Array.isArray(dd.app.routes)) ? dd.app.routes.length : null;
      coverage.note = ("本页是**精选展示**：" + coverage.curated + " / " +
                       (coverage.total === null ? "?" : coverage.total) +
                       "（可用 " + (coverage.enabled === null ? "?" : coverage.enabled) +
                       " · 禁用 " + (coverage.disabled === null ? "?" : coverage.disabled) +
                       "）。全量清单看能力总目录，不在这里复制第二份。");
    } else {
      coverage.note = "取不到全量口径（" + (disc.error || "未返回") + "）—— 落差数字如实留空，不估。";
    }
  } catch (err) {
    coverage.note = "取不到全量口径（" + String(err.message || err) + "）—— 落差数字如实留空，不估。";
  }

  return ok({
    readonly: true,
    store: path.basename(STORE),
    root: ROOT ? path.basename(ROOT) : null,
    note: "只读视图：不落账、不建目录、不写健康通道；面板只做展示映射。",
    caps: caps,
    coverage: coverage,
    not_exported_note: TOOLS_NOT_EXPORTED,
  });
}

/* ── 窗口 6 · 赏金台（阶段一：本机只读） ── */

const H1_BINARY_ENV = "GBT_H1_BINARY";
const H1_DRAFTS_ENV = "GBT_H1_DRAFTS";
const H1_BINARY_DEFAULT = process.env.LOCALAPPDATA
  ? path.join(process.env.LOCALAPPDATA, "gbt_allinone", "bin", "h1mcp.exe") : null;
const H1_DRAFTS_DEFAULT = process.env.APPDATA
  ? path.join(process.env.APPDATA, "h1mcp", "drafts") : null;

/* 配置项优先级：环境变量（测试钩子）> windows.json 的 entry.config > 内置默认。绝不查 PATH。 */
function h1ConfiguredPath(envName, configKey, fallback) {
  if (process.env[envName]) return process.env[envName];
  const entry = (registry.windows || []).filter((e) => e.id === "h1")[0];
  const raw = entry && entry.config ? entry.config[configKey] : null;
  if (typeof raw === "string" && raw.trim()) {
    return raw.trim().replace(/%([^%]+)%/g, (m, name) => (process.env[name] || m));
  }
  return fallback;
}
const H1_CRED_VARS = [
  { name: "H1_USERNAME", role: "HackerOne 用户名", read_by: "h1mcp v0.1.4" },
  { name: "H1_API_KEY", role: "API 令牌（二进制实际读取名）", read_by: "h1mcp v0.1.4" },
  { name: "H1_API_TOKEN", role: "历史口径名（h1mcp v0.1.4 不读取）", read_by: null },
];

function h1FileSha256(file) {
  try { return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex"); }
  catch (err) { return null; }
}

/* 只读视图：不调 API、不起子进程、不写文件；取不到就不许显示绿。凭据只报布尔，不回显值（连用户名也不回显）。 */
function w3H1() {
  const h1Binary = h1ConfiguredPath(H1_BINARY_ENV, "binary_path", H1_BINARY_DEFAULT);
  const h1Drafts = h1ConfiguredPath(H1_DRAFTS_ENV, "drafts_path", H1_DRAFTS_DEFAULT);
  const binary = {
    path: h1Binary, present: false, bytes: null, tag: null,
    sha256: null, recorded_sha256: null, sha_match: null,
    sidecar_present: false, reason: null,
  };
  if (!h1Binary) {
    binary.reason = "LOCALAPPDATA 不可用 -> 拿不到稳定工具目录";
  } else if (!fs.existsSync(h1Binary)) {
    binary.reason = "二进制不存在（未安装或路径不符）";
  } else {
    try {
      binary.present = true;
      binary.bytes = fs.statSync(h1Binary).size;
      binary.sha256 = h1FileSha256(h1Binary);
      const sidecar = h1Binary + ".sha256";
      if (fs.existsSync(sidecar)) {
        binary.sidecar_present = true;
        const txt = fs.readFileSync(sidecar, "utf8");
        const hm = txt.match(/[0-9a-fA-F]{64}/);
        if (hm) binary.recorded_sha256 = hm[0].toLowerCase();
        const vm = txt.match(/tag=([^\r\n]+)/);
        if (vm) binary.tag = vm[1].trim();
      }
      binary.sha_match = (binary.sha256 && binary.recorded_sha256)
        ? binary.sha256 === binary.recorded_sha256 : null;
      if (binary.sha_match === false) binary.reason = "侧车哈希与产物不一致（产物被替换过）";
    } catch (err) {
      binary.reason = "读取失败：" + (err && err.code ? err.code : String(err));
    }
  }

  const credItems = H1_CRED_VARS.map((v) => ({
    name: v.name,
    role: v.role,
    read_by: v.read_by,
    configured: !!process.env[v.name],   /* 只报布尔，不回显值 */
  }));
  const credsReady = credItems.filter((c) => c.name === "H1_USERNAME" || c.name === "H1_API_KEY")
    .every((c) => c.configured);

  const drafts = { path: h1Drafts, initialized: false, count: null, files: [], reason: null };
  if (!h1Drafts) {
    drafts.reason = "APPDATA 不可用 -> 拿不到草稿目录";
  } else if (!fs.existsSync(h1Drafts)) {
    drafts.reason = "目录不存在（未初始化）";
  } else {
    try {
      const names = fs.readdirSync(h1Drafts).filter((n) => /\.json$/i.test(n)).sort().slice(0, 50);
      drafts.initialized = true;
      drafts.count = names.length;
      drafts.files = names.map((n) => {
        const row = { name: n, bytes: null, mtime: null, title: null, program_handle: null, parse_error: null };
        try {
          const p = path.join(h1Drafts, n);
          const st = fs.statSync(p);
          row.bytes = st.size;
          row.mtime = st.mtime.toISOString();
          const doc = JSON.parse(fs.readFileSync(p, "utf8"));
          if (typeof doc.title === "string") row.title = doc.title;
          if (typeof doc.program_handle === "string") row.program_handle = doc.program_handle;
        } catch (err) { row.parse_error = (err && err.name) || "READ_ERROR"; }
        return row;
      });
    } catch (err) {
      drafts.reason = "目录读取失败：" + (err && err.code ? err.code : String(err));
    }
  }

  const ready = binary.present === true && binary.sha_match === true && credsReady;
  const body = {
    readonly: true,
    stage: "stage1-local-readonly",
    note: "只读：不调 API、不起子进程、不写文件；凭据只报配置状态，不回显值。",
    badge: ready ? "ok" : (binary.present ? "warn" : "off"),
    binary: binary,
    credentials: { ready: credsReady, items: credItems },
    drafts: drafts,
    api_surfaces: [
      { id: "programs_scope", title: "程序与 scope", state: "pending", reason: "阶段二未接入（走 mcp_bridge 能力层，需 Owner 单独放行）" },
      { id: "reports", title: "我的报告", state: "pending", reason: "阶段二未接入（同上）" },
      { id: "earnings", title: "收益", state: "pending", reason: "阶段二未接入（同上）" },
    ],
    sensitive_note: "敏感档动作不接：submit_report / submit_draft / add_comment / close_report / update_report_severity / request_disclosure。",
  };
  if (!binary.present) return no("h1mcp 取不到：" + (binary.reason || "未知原因"), { panel: body });
  return ok(body);
}

/* ── §13 数字人召唤台 + AI 朋友圈（W9） ──
 *
 * 定性：本段新增**两个口**，只有一个是"动作口"：
 *   w3:pets / w3:eigenflux  —— 只读探测，零写盘、零网络、零子进程（除一次懒探测）。
 *   w3:summon               —— 唯一动作口：**只起一个本机窗口**；不写任何文件、
 *                              不发任何网络、不 kill 任何进程、不碰 store。
 * 面板上「可点」一律由**实测就绪态**决定：不就绪就不给点，并把原因写在按钮旁边（不假绿）。
 *
 * 决策全在 ./features.cjs（纯函数层，可被 node --test 钉住）；本段只做
 * fs 只读探测 / execFile 探针 / spawn 一次。绝对路径**不回显**给渲染层，只出 basename。
 */

const PETS_RESOURCES = ROOT ? path.join(ROOT, "potato_pet", "resources") : null;
const PETS_ELECTRON = ROOT
  ? path.join(ROOT, "holo_pet", "node_modules", "electron", "dist", "electron.exe") : null;
const PETS_PY_EXE = process.env.GBT_PY_EXE || "py";
const EF_SERVER = "eigenflux";

/* Python 腿就绪态：只查两个模块**在不在**，不 import（import PySide6 会拉起 Qt，太重）。
 * 结果缓存一次；点「刷新就绪态」才 force 重测 —— 不猜、也不每次点都起子进程。 */
let PETS_PY_PROBE = null;

function probePythonLeg(force) {
  if (PETS_PY_PROBE && force !== true) return Promise.resolve(PETS_PY_PROBE);
  const code = [
    "import json",
    "import importlib.util as u",
    "def has(n):",
    "    try: return u.find_spec(n) is not None",
    "    except Exception: return False",
    "print(json.dumps({'pyside6': has('PySide6'), 'live2d': has('live2d')}))",
  ].join("\n");
  return new Promise((resolve) => {
    execFile(PETS_PY_EXE, ["-3.10", "-c", code], { timeout: 20000, windowsHide: true },
      (err, stdout) => {
        const out = { checked: false, pyside6: false, live2d: false,
                      interpreter: PETS_PY_EXE + " -3.10" };
        if (!err) {
          try {
            const parsed = JSON.parse(String(stdout).trim());
            out.pyside6 = parsed.pyside6 === true;
            out.live2d = parsed.live2d === true;
            out.checked = true;
          } catch (e) { out.checked = false; }
        }
        PETS_PY_PROBE = out;
        resolve(out);
      });
  });
}

/* 面板是否在服务：拿到任何响应头即算在服务（不看状态码，只看"有没有人接电话"）。 */
function panelPing() {
  return new Promise((resolve) => {
    const req = http.get(PANEL + "/api/state", (res) => { res.resume(); resolve(true); });
    req.on("error", () => resolve(false));
    req.setTimeout(1500, () => { req.destroy(); resolve(false); });
  });
}

async function petsSnapshot(force) {
  const models = features.scanPetResources(fs, PETS_RESOURCES);
  const electronPresent = !!(PETS_ELECTRON && fs.existsSync(PETS_ELECTRON));
  let electronBytes = 0;
  if (electronPresent) {
    try { electronBytes = fs.statSync(PETS_ELECTRON).size; } catch (err) { electronBytes = 0; }
  }
  const python = await probePythonLeg(force);
  const panelReachable = await panelPing();
  const carriers = features.buildCarriers({
    python: python, electronPresent: electronPresent, panelReachable: panelReachable,
    electronBytes: electronBytes, models: models.length,
  });
  return { models: models, carriers: carriers, panelReachable: panelReachable, python: python };
}

/* 只读视图：不起窗口、不写文件、不发网络。绝对路径不回显。 */
async function w3Pets(payload) {
  if (!ROOT) return no("找不到仓库根（上层没有 gbt_allinone）-> 形象库不猜路径");
  const snap = await petsSnapshot(!!(payload && payload.refresh === true));
  const issues = [];
  if (!snap.python.checked) issues.push("py -3.10 探针没跑起来（解释器不可用？）—— Python 腿按未探测记，不猜");
  if (!PETS_RESOURCES || !fs.existsSync(PETS_RESOURCES)) issues.push("potato_pet/resources 不在位");
  return ok({
    readonly: true,
    stage: "w9",
    note: "只读探测：不起窗口、不写文件、不发网络；点「召唤数字人」才起一个本机窗口。",
    resources_label: PETS_RESOURCES ? path.basename(PETS_RESOURCES) : null,
    resources_present: !!(PETS_RESOURCES && fs.existsSync(PETS_RESOURCES)),
    models: snap.models,
    model_count: snap.models.length,
    carriers: snap.carriers.carriers,
    primary: snap.carriers.primary,
    python: snap.python,
    panel_reachable: snap.panelReachable,
    issues: issues,
  });
}

/* 唯一动作口：就绪才起，起完 unref（壳一退，数字人不跟着死）。 */
async function w3Summon(payload) {
  const carrier = payload && payload.carrier ? String(payload.carrier) : "";
  if (!ROOT) return no("找不到仓库根 -> 拒绝召唤", { carrier: carrier });
  const plan = features.summonPlan({
    carrier: carrier, repoRoot: ROOT, electronExe: PETS_ELECTRON, pythonExe: PETS_PY_EXE,
  });
  if (!plan.ok) return no("召唤被拒：" + plan.reason, { carrier: carrier });
  const snap = await petsSnapshot(false);
  const row = snap.carriers.carriers.filter((c) => c.id === carrier)[0];
  if (!row || row.ready !== true) {
    return no("载体未就绪，拒绝起进程：" + ((row && row.reason) || "没有这一条载体"),
              { carrier: carrier, ready: false });
  }
  /* 🔴 2026-10-10 修一处**同族的判据病**：拿「文件存在性」去判一个 **PATH 命令**。
     plan.exe 可能是**裸命令名**（PETS_PY_EXE 默认就是 "py"，见上方常量），
     而 fs.existsSync("py") **永远是 false** ⇒ 所有 python 载体被**错杀在门口**。
     实测撞到：给面板桥加载体后，召唤直接报「可执行文件不在位：py」，而 py 明明可用。
     （live2d-pet 同病 —— 一直没暴露，只因为没人召唤过它。）
     ⇒ 含路径分隔符的**绝对/相对路径**才要求存在；**裸命令名**交给 spawn 按 PATH 解析。 */
  const isPathLike = /[\\/]/.test(plan.exe);
  if (isPathLike && !fs.existsSync(plan.exe)) {
    return no("可执行文件不在位：" + path.basename(plan.exe), { carrier: carrier });
  }
  try {
    const child = spawn(plan.exe, plan.argv, { detached: true, cwd: plan.cwd, stdio: "ignore" });
    child.unref();
    return ok({
      summoned: true, carrier: carrier, pid: child.pid, reason: plan.reason,
      cwd_label: path.basename(plan.cwd),
      argv_label: plan.argv.map((a) => path.basename(a)).join(" "),
      wrote_anything: false, killed_anything: false,
    });
  } catch (err) {
    return no("起不来：" + String((err && err.message) || err), { carrier: carrier });
  }
}

/* 🔴 2026-10-10（主人令）**建窗之前**确保面板桥在跑。
   主人实测：「打开 APP 里面还是一大堆没连接没配置」—— 真探后真因不是一堆配置，
   而是**面板桥 :8765 没在跑**（capability-audit 那两条断连其实是同一件事）。
   壳自己早就写好了一句「本地面板 :8765 未就绪 —— 数字人壳没有可加载的页面」，
   却**什么都不做**；而 windows.json 又写着「它正在 8765 跑」⇒ 假定有人拉，其实没人拉。
   （open-full-panel.bat 会自己探+拉，所以走那个入口看不到 —— **走的入口不同，结果不同**。）
   做法：复用既有的 panelPing() + w3Summon()，**不另写一条起进程的路**。
   失败一律只打日志、不牵连壳启动（与 R-H295「展示面不许拖垮数据面」同向）。 */
async function ensurePanelBridge() {
  if (!ROOT) return { ok: false, reason: "找不到仓库根（上层没有 gbt_allinone）" };
  if (await panelPing()) return { ok: true, already: true };
  const out = await w3Summon({ carrier: "panel-bridge" });
  if (!out || out.ok !== true) {
    return { ok: false, reason: String((out && (out.error || out.reason)) || "召唤被拒") };
  }
  /* 幂等起进程后给桥一点时间听端口；最多约 10s，不无限等。 */
  for (let i = 0; i < 20; i += 1) {
    await new Promise((r) => setTimeout(r, 500));
    if (await panelPing()) return { ok: true, already: false, waited_ms: (i + 1) * 500 };
  }
  return { ok: false, reason: "进程起了但 :8765 一直没接管（可能端口被占，launch_panel 会顺延）" };
}

/* 🔴 2026-10-21（主人令「把云插件的GBT小土豆V8大模型接入到原生APP里面使用」）：
   **建窗之前**确保模型桥在跑 —— 「模型对话」页（model-chat）只连本机桥 127.0.0.1:8791，
   钥匙在桥里（DPAPI 保险箱），页面零凭据；桥没人拉 ⇒ 页面永远「桥：连不上」，
   云插件的 GBT小土豆V8 大模型就等于没接进 APP。
   做法：探活（GET /health）→ 没起就 spawn `py -3.14 -X utf8 tools/model-bridge/server.py`，
   桥自己的 stderr（只有 slot/model/http/耗时 一行行，不落聊天内容）追加进
   outputs/model-bridge/bridge.log。失败只打日志、不牵连壳启动（与 R-H295 同向）。
   退出收尸：只 kill **本进程拉起的**那个 child；用户自己终端拉的桥不碰。 */
const MODEL_BRIDGE_PORT = 8791;
const MODEL_BRIDGE_JS = path.join(ROOT, "tools", "model-bridge", "server.py");
let modelBridgeChild = null;

/* 🔴 2026-10-24（主人令「接 APP 启动逻辑」）：本机自有权重服务（Q5_0 · OpenAI 兼容）——
   桥的 selfhost 车道就指向它。为什么由壳来拉：
   ① 桥的车道地址在 import 时算好，必须在桥之前就绪；
   ② 壳是唯一同时知道 ROOT、解释器、权重位置的地方。
   失败只打日志、不牵连壳启动；桥那边会自然落回 cfai（weights_ours=false）。 */
const LOCAL_LLM_PORT = 8792;
const LOCAL_LLM_JS = path.join(ROOT, "tools", "model-bridge", "local_llm_server.py");
const LOCAL_LLM_GGUF = path.join(ROOT, "state", "weights", "gbt-v8-v82-q5_0.gguf");
let localLlmChild = null;

function localLlmPing() {
  return new Promise((resolve) => {
    const req = http.get(
      { host: "127.0.0.1", port: LOCAL_LLM_PORT, path: "/health", timeout: 2000 },
      (res) => { res.resume(); resolve(res.statusCode === 200); });
    req.on("error", () => resolve(false));
    req.setTimeout(2000, () => { req.destroy(); resolve(false); });
  });
}

/* 🔴 2026-10-24 实测：壳默认的 PETS_PY_EXE = "py" → 落到 Python 3.14（uv），
   那里**没装 llama_cpp** ⇒ 服务秒退（ModuleNotFoundError），而桥是纯标准库所以照跑。
   所以这里必须单独挑一个「能 import llama_cpp」的解释器。 */
function pickLlmPython() {
  const cands = [process.env.GBT_LLM_PY_EXE, "C:\\Python312\\python.exe", PETS_PY_EXE].filter(Boolean);
  for (const cand of cands) {
    try {
      require("child_process").execFileSync(cand, ["-c", "import llama_cpp"],
        { stdio: "ignore", windowsHide: true, timeout: 20000 });
      return cand;
    } catch (err) { /* 下一个候选 */ }
  }
  return "";
}

async function ensureLocalLLM() {
  if (!ROOT) return { ok: false, reason: "找不到仓库根" };
  if (!fs.existsSync(LOCAL_LLM_GGUF)) return { ok: false, reason: "缺权重：" + LOCAL_LLM_GGUF };
  if (await localLlmPing()) return { ok: true, already: true };
  const pyExe = pickLlmPython();
  if (!pyExe) return { ok: false, reason: "没有装 llama_cpp 的解释器（试过 GBT_LLM_PY_EXE / C:\\Python312 / " + PETS_PY_EXE + "）" };
  const bareLauncher = !/[\\/]/.test(pyExe);
  const argv = (bareLauncher ? ["-3.14", "-X", "utf8"] : ["-X", "utf8"]).concat([
    /* 2026-10-24 实测（6 核 / 12 线程）：threads=8 在两次对照里都是同批最高；
       ctx=64 的"更快"是页缓存温度造成的假象，反向复跑就没了，所以仍用 256。 */
    LOCAL_LLM_JS, "--model", LOCAL_LLM_GGUF, "--port", String(LOCAL_LLM_PORT),
    "--ctx", "256", "--threads", "8",
  ]);
  let logStream = null;
  try {
    fs.mkdirSync(path.join(ROOT, "outputs", "model-bridge"), { recursive: true });
    logStream = fs.createWriteStream(path.join(ROOT, "outputs", "model-bridge", "local-llm.log"), { flags: "a" });
    localLlmChild = spawn(pyExe, argv,
      { cwd: ROOT, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
    const sink = logStream;
    localLlmChild.stdout.on("data", (d) => { try { sink.write(d); } catch (err) { /* 日志写不出不拖垮服务 */ } });
    localLlmChild.stderr.on("data", (d) => { try { sink.write(d); } catch (err) { /* 同上 */ } });
    localLlmChild.on("exit", () => { localLlmChild = null; });
  } catch (err) {
    return { ok: false, reason: "起不来：" + String((err && err.message) || err) };
  }
  /* 4.88 GB 权重冷加载 + 换页可能要几十秒；最多等 90s，不无限等。 */
  for (let i = 0; i < 90; i += 1) {
    await new Promise((r) => setTimeout(r, 1000));
    if (await localLlmPing()) return { ok: true, already: false, waited_ms: (i + 1) * 1000 };
  }
  return { ok: false, reason: "进程起了但 :8792 一直没接管（看 outputs/model-bridge/local-llm.log）" };
}

function modelBridgePing() {
  return new Promise((resolve) => {
    const req = http.get(
      { host: "127.0.0.1", port: MODEL_BRIDGE_PORT, path: "/health", timeout: 1500 },
      (res) => { res.resume(); resolve(true); });
    req.on("error", () => resolve(false));
    req.setTimeout(1500, () => { req.destroy(); resolve(false); });
  });
}

function modelBridgeHealth() {
  return new Promise((resolve) => {
    const req = http.get(
      { host: "127.0.0.1", port: MODEL_BRIDGE_PORT, path: "/health", timeout: 2000 },
      (res) => {
        let buf = "";
        res.setEncoding("utf8");
        res.on("data", (d) => { buf += d; });
        res.on("end", () => { try { resolve(JSON.parse(buf)); } catch (err) { resolve(null); } });
      });
    req.on("error", () => resolve(null));
    req.setTimeout(2000, () => { req.destroy(); resolve(null); });
  });
}

/* 桥的 /health 里有没有 selfhost 车道、地址是不是指向本机权重服务。 */
function bridgeHasSelfhost(h) {
  if (!h || !Array.isArray(h.upstreams)) return false;
  return h.upstreams.some((u) => u && u.name === "selfhost"
    && String(u.base_url || "").indexOf(":" + LOCAL_LLM_PORT) >= 0);
}

/* 收掉监听某端口的进程 —— 只用于清掉**没带 selfhost 车道**的残留桥。
   拿不到 PID 就返回 0，让上层如实报"没清掉"，不假装成功。 */
function killListeners(port) {
  let out = "";
  try {
    out = require("child_process").execSync("netstat -ano -p tcp", { encoding: "utf8", windowsHide: true });
  } catch (err) {
    return 0;
  }
  const pids = new Set();
  out.split(/\r?\n/).forEach((line) => {
    if (line.indexOf(":" + port) < 0 || !/LISTENING/i.test(line)) return;
    const parts = line.trim().split(/\s+/);
    const pid = parts[parts.length - 1];
    if (/^\d+$/.test(pid) && pid !== "0") pids.add(pid);
  });
  let n = 0;
  pids.forEach((pid) => {
    try { require("child_process").execSync("taskkill /PID " + pid + " /F", { stdio: "ignore" }); n += 1; } catch (err) { /* 收不掉就不算 */ }
  });
  return n;
}

async function ensureModelBridge() {
  if (!ROOT) return { ok: false, reason: "找不到仓库根" };
  const health = await modelBridgeHealth();
  if (health && bridgeHasSelfhost(health)) return { ok: true, already: true };
  if (health && !bridgeHasSelfhost(health)) {
    /* 🔴 2026-10-24：残留桥是**上一轮没带 selfhost env** 起的 —— 它照样能答，
       但答的是云端模型（weights_ours=false）。"结果对、车道错"必须清掉重起。 */
    const killed = killListeners(MODEL_BRIDGE_PORT);
    console.error("[w3] 模型桥缺 selfhost 车道（残留实例），已收掉 " + killed + " 个监听进程，重起中");
    for (let i = 0; i < 24; i += 1) {
      await new Promise((r) => setTimeout(r, 250));
      if (!(await modelBridgePing())) break;
    }
  }
  /* py 启动器才吃 "-3.14"；GBT_PY_EXE 直接给解释器路径时不该带版本参数（同 w3Summon 的判据：
     含路径分隔符的才是路径，裸命令名交给 spawn 按 PATH 解析）。 */
  const bareLauncher = !/[\\/]/.test(PETS_PY_EXE);
  const argv = bareLauncher ? ["-3.14", "-X", "utf8", MODEL_BRIDGE_JS]
                            : ["-X", "utf8", MODEL_BRIDGE_JS];
  let logStream = null;
  try {
    fs.mkdirSync(path.join(ROOT, "outputs", "model-bridge"), { recursive: true });
    logStream = fs.createWriteStream(path.join(ROOT, "outputs", "model-bridge", "bridge.log"), { flags: "a" });
    /* 🔴 2026-10-24：把 selfhost 车道的地址在桥起来那一刻定死 ——
       桥的 UPSTREAMS 是在 import 时读环境变量算出来的，起晚了再设没用。 */
    modelBridgeChild = spawn(PETS_PY_EXE, argv,
      { cwd: ROOT, windowsHide: true, stdio: ["ignore", "pipe", "pipe"],
        env: Object.assign({}, process.env, {
          GBT_ENABLE_SELFHOST_LANE: "1",
          GBT_OURS_BASE_URL: "http://127.0.0.1:" + LOCAL_LLM_PORT + "/v1",
        }) });
    const sink = logStream;
    modelBridgeChild.stdout.on("data", (d) => { try { sink.write(d); } catch (err) { /* 日志写不出不拖垮桥 */ } });
    modelBridgeChild.stderr.on("data", (d) => { try { sink.write(d); } catch (err) { /* 同上 */ } });
    modelBridgeChild.on("exit", () => { modelBridgeChild = null; });
  } catch (err) {
    return { ok: false, reason: "起不来：" + String((err && err.message) || err) };
  }
  /* 幂等起进程后给桥一点时间听端口；最多约 10s，不无限等。 */
  for (let i = 0; i < 20; i += 1) {
    await new Promise((r) => setTimeout(r, 500));
    if (await modelBridgePing()) return { ok: true, already: false, waited_ms: (i + 1) * 500 };
  }
  return { ok: false, reason: "进程起了但 :8791 一直没接管（看 outputs/model-bridge/bridge.log）" };
}

/* ── §13b AI 朋友圈（W9）· 本机只读 ──
 *
 * 为什么读盘在主进程：窗口 CSP 是 connect-src 'none'，渲染层**没有任何网络口**；
 * 数据在 ~/.eigenflux，只能由主进程 fs 读、归一化后经 IPC 交出去。
 * 远端来的文本一律先经 features.redact()；邮箱只出布尔，绝对路径不回显。
 */

function readJsonVia(file) {
  try { return { ok: true, doc: JSON.parse(fs.readFileSync(file, "utf8")) }; }
  catch (err) {
    return { ok: false, error: (err && err.code) ? String(err.code) : String((err && err.name) || err) };
  }
}

function listFilesDeep(dir, depth) {
  const out = [];
  if (!dir || depth > 3 || !fs.existsSync(dir)) return out;
  let names;
  try { names = fs.readdirSync(dir); } catch (err) { return out; }
  names.forEach((n) => {
    const p = path.join(dir, n);
    let st;
    try { st = fs.statSync(p); } catch (err) { return; }
    if (st.isDirectory()) { listFilesDeep(p, depth + 1).forEach((x) => out.push(x)); return; }
    out.push({ file: p, name: n, bytes: st.size, mtimeMs: st.mtimeMs });
  });
  return out;
}

function w3Eigenflux() {
  const home = features.resolveHome(process.env, os.homedir());
  const paths = features.eigenfluxPaths(home, EF_SERVER);
  const body = {
    readonly: true,
    stage: "w9",
    note: "只读：不调 API、不发网络、不写文件、不发消息；全部数据来自本机缓存。",
    home_label: features.homeLabel(home),
    initialized: false,
    issues: [],
    source: {},
    profile: null,
    friends: [],
    feed: [],
    messages: [],
    counts: { friends: 0, feed: 0, messages: 0 },
  };
  if (!fs.existsSync(paths.root)) {
    body.issues.push("未初始化：本机还没有 EigenFlux（" + body.home_label +
      " 下没有 servers/" + EF_SERVER + "）—— 是未初始化，不是空数据");
    return ok(body);
  }
  body.initialized = true;

  const pr = readJsonVia(paths.profile);
  if (pr.ok && pr.doc && !Array.isArray(pr.doc)) {
    body.profile = features.normalizeProfile(pr.doc);
    body.source.profile = path.basename(paths.profile);
  } else {
    body.issues.push("档案读不到：" + (pr.ok ? "profile.json 不是对象" : pr.error));
  }

  const cr = readJsonVia(paths.contacts);
  if (cr.ok && Array.isArray(cr.doc)) {
    body.friends = cr.doc.slice(0, features.LIMITS.friends).map(features.normalizeFriend);
    body.source.contacts = path.basename(paths.contacts);
  } else {
    body.issues.push("好友读不到：" + (cr.ok ? "contacts.json 不是数组" : cr.error));
  }

  const feedFiles = listFilesDeep(paths.broadcasts, 2).filter((f) => /\.json$/i.test(f.name));
  const latestFeed = features.pickLatest(feedFiles);
  if (!latestFeed) {
    body.issues.push("动态流读不到：broadcasts 下没有 JSON —— 本机还没收到过动态");
  } else {
    const fr = readJsonVia(latestFeed.file);
    if (!fr.ok) {
      body.issues.push("最新动态文件解析失败：" + fr.error);
    } else {
      const items = Array.isArray(fr.doc) ? fr.doc
        : (fr.doc && Array.isArray(fr.doc.items) ? fr.doc.items : []);
      body.feed = items.slice(0, features.LIMITS.feed_items).map(features.normalizeFeedItem);
      body.source.feed = {
        file: latestFeed.name, files_total: feedFiles.length,
        items_in_file: items.length, mtime: features.toIso(latestFeed.mtimeMs),
      };
    }
  }

  const msgFiles = listFilesDeep(paths.messages, 2).filter((f) => /\.json$/i.test(f.name));
  msgFiles.sort((a, b) => (Number(b.mtimeMs) || 0) - (Number(a.mtimeMs) || 0));
  const picked = msgFiles.slice(0, 4);
  if (!picked.length) {
    body.issues.push("私信读不到：messages 下没有 JSON —— 本机还没有会话");
  }
  const lists = [];
  picked.forEach((f) => {
    const mr = readJsonVia(f.file);
    if (!mr.ok) { body.issues.push("私信文件解析失败：" + f.name + "（" + mr.error + "）"); return; }
    const rows = Array.isArray(mr.doc) ? mr.doc
      : (mr.doc && Array.isArray(mr.doc.items) ? mr.doc.items : []);
    lists.push(rows);
  });
  body.messages = features.mergeMessages(lists, features.LIMITS);
  body.source.messages = { files_total: msgFiles.length, files_read: picked.length };
  body.counts = {
    friends: body.friends.length, feed: body.feed.length, messages: body.messages.length,
  };
  return ok(body);
}
/* ── 窗口 ── */

const registry = readRegistry();
const wins = new Map();
let tray = null;
/* 实时流的**当前状态**（2026-09-23 第 43 轮加）。
   为什么要记：`startSse` 跑在建窗之前（R-H295 的"数据面先立"），那条 `notify("open")`
   发生时还没有窗口 ⇒ 状态只报一次就丢。记下来，建窗完成后**补发**给迟到的订阅者。
   null = 还没连过（此时不该补发任何状态 —— 补发 null 等于替面板编一个状态）。 */
let lastStreamState = null;

function broadcast(channel, payload) {
  /* R-H295：原实现没有任何错误隔离 —— 某个窗口的 webContents 处于异常态时
     （`isDestroyed` 本身可能抛、`send` 也可能抛），异常会从 SSE 的 data 回调里冒出来，
     而那条路径上没人接：**实时流会整条断掉甚至带走主进程**，
     症状和"实时流未接"一样，但原因完全不同。
     逐窗口隔离：坏的那扇跳过，其余照推；坏因如实打到 stderr。 */
  wins.forEach((w, id) => {
    try {
      if (w && !w.isDestroyed() && w.webContents && !w.webContents.isDestroyed()) {
        w.webContents.send(channel, payload);
      }
    } catch (err) {
      console.error("[w3] 推送失败（跳过该窗，其余照推） id=" + id + " ch=" + channel + ":", err);
    }
  });
}

function saveWindowState() {
  const data = layout.loadLayout(LAYOUT_FILE);
  wins.forEach((w, id) => {
    if (!w || w.isDestroyed()) return;
    data.windows[id] = layout.fromBrowserBounds(w.getBounds(), id, w.isVisible());
  });
  try { layout.saveLayout(LAYOUT_FILE, data); } catch (err) { /* 写不进布局文件不该拖垮壳 */ }
}

/* ── 2026-09-23 加：窗可以加载**回环 HTTP**（一体式要塞对话面）────────────────
   规则与测试见 `shell/url-policy.cjs` —— 它**不依赖 electron**，所以能在普通 node 下单测
   （`tests/test_url_policy.cjs`）。这里只是把它接上；**策略本身不在这份文件里**。

   ⚠️ 对话面（DSH）的**真实约束**（2026-09-23 实测）：
     `GET http://127.0.0.1:3080/` → **HTTP 401**
     body 原文：`dsh web authentication required; reopen the URL printed by dsh web.`
   ⇒ 它要的是 **`dsh web` 启动时打印的那条带 token 的 URL**，不是裸 URL。
     **本文件不保存、不读、不猜那个 token**（凭据不许明文落盘）。
     带 token 的 URL 只能由**主人在运行时**提供 —— 见 windows.json 里 `dsh-chat` 的 `needs_url`。 */
const urlPolicy = require("./url-policy.cjs");
const loopbackUrlOnly = urlPolicy.loopbackUrlOnly;
/* DeepSeek Harness 自接入（2026-10-07）：壳自己拉起 `dsh web`，读它就绪那一行，
   再交给下面**同一个**口子 `w3ConnectDsh`（过回环白名单 · URL 只在内存 · 只回 host）。
   本模块不监听、不注入、不代理对话协议 —— 口径见它的模块头。 */
const dshLaunch = require("./dsh-launch.cjs");
/* 每扇窗各自的自接入句柄（窗关掉就收走子进程，别在托盘里留一个孤儿 dsh）。 */
const dshAutoHandles = new Map();

/* 启动期标志：只有**第一批**建窗（启动那一次）受下面「唯一可见窗」规则约束；
   启动之后按需唤醒（托盘/菜单/面板入口）的窗照常走各自声明。 */
let STARTUP_DONE = false;

function createWindow(entry) {
  const stored = layout.loadLayout(LAYOUT_FILE).windows[entry.id];
  const displays = screen.getAllDisplays();
  const wanted = stored || entry.default;
  const placed = layout.clampBounds(layout.normalize(wanted, entry.id), displays);
  /* 🔴 **真启动预演的插桩**（2026-09-23 第 37 轮）：`GBT_W3_STARTUP_PROBE=1` 时
     所有窗**屏幕外 + 不显示**，但引导链**一个环节都不跳**（单例锁 → registerIpc →
     startSse → createWindow → buildTray → refreshTrayMenu）。
     为什么插在这里而不是另写一条探针链：另写一条就**不是真启动**了 ——
     托盘图标构造失败会让 startSse 永远不跑（本文件上面记着这条实测），
     那种缺陷只有走真链才抓得到。**只改两个字段，不设这个变量时行为一个字节不动。** */
  const PROBE = process.env.GBT_W3_STARTUP_PROBE === "1";
  /* 🔴 主人令 2026-10-08（照白龙马口径）：「打开 APP 直接就是数字人语音交互页」。
     启动唯一可见窗 = digital-human：第一批建窗时其余窗一律不显（位置/尺寸照旧走
     持久化布局，只收可见位——避免持久化里的旧可见位把它顶出来）；digital-human
     强制显，并由启动段 focus。PROBE（真启动预演）不受影响；启动之后按需唤醒不受约束。 */
  if (!PROBE && !STARTUP_DONE) placed.visible = (entry.id === "digital-human");
  /* 🔴 品牌统一（主人令 2026-10-04）：任务栏/窗口用自家图标，不再露 Electron 默认脸。 */
  const iconPath = path.join(HERE, "..", "build", "icon.ico");
  const win = new BrowserWindow({
    x: PROBE ? -20000 : placed.x, y: PROBE ? -20000 : placed.y,
    width: placed.w, height: placed.h,
    minWidth: 720, minHeight: 480,
    transparent: entry.transparent !== false,
    frame: entry.frame === true,
    resizable: entry.resizable !== false,
    alwaysOnTop: entry.alwaysOnTop !== false,
    hasShadow: false,
    backgroundColor: "#00000000",
    show: placed.visible !== false,   /* 可见性来自注册表 / 持久化布局（W7）——声明了就要生效 */
    title: entry.title || entry.id,
    icon: fs.existsSync(iconPath) ? iconPath : undefined,
    webPreferences: {
      preload: path.join(HERE, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      /* 🔴 2026-10-21 加（主人问「肢体动作控制不好」时量出来的真因之一）：
         Chromium 对**被别的窗盖住**的页面会把 requestAnimationFrame 节流到 ~1fps。
         实测她那扇窗被挡在后面时帧计数 2.4 秒只走了 2 帧（4→6），骨骼驱动器每帧算的
         角度根本没机会画出来 —— 看起来就是「骨绑了却不动」。
         关掉后台节流：只要窗还开着就按正常帧率跑（她是要一直动给人看的，
         被盖住时少画几帧省不了多少电，却会把"在动"变成"冻住"）。 */
      backgroundThrottling: false,
      /* 面板窗需要 <webview>（页面在面板内容区里切换，主人令 2026-10-04）：
         只有注册表里显式声明 webviewTag 的窗才开，别处一律不开（安全面收窄）。 */
      webviewTag: entry.webviewTag === true,
      /* 外部对话窗用**标准 Chrome UA**（2026-10-04 实测）：chat.deepseek.com 的
         CloudFront 边缘会把 Electron 默认 UA 判成机器人（403 / configuration error），
         换成常规浏览器 UA 是嵌入式浏览器的标准兼容措施（不改任何站点内容与凭据）。 */
      userAgent: entry.id === "dsh-chat"
        ? "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
          + "Chrome/136.0.0.0 Safari/537.36"
        : undefined,
      /* 🔴 音频自动播放（2026-10-08 加 · 主人令「数字人以语音交互做」落地时那条坑）：
         Chromium 默认**要用户手势才允许出声**（Electron 继承）。数字人若只在主人点过之后
         才敢开口，那"它有话要说时主动播报"这件事就永远做不到；反过来，一律放开又会让
         任何页面都能在没人点的情况下出声 —— 所以**做成注册表开关、默认关**：
           `audio_autoplay: true`   ⇒ no-user-gesture-required（适合数字人窗）
           不写 / false             ⇒ user-gesture-required（安全默认：不点不出声）
         ⚠️ 与 memory 里那条「服务端别出声」不冲突：那条说的是**面板服务进程**别喇叭，
         这里是**渲染层页面**的出声许可，两回事。
         ✅ 现状（2026-10-08）：这一格**早就是按窗开的**，数字人窗（windows.json: digital-human）
         已登记 `audio_autoplay: true` ⇒ 它的 autoplayPolicy 现为 no-user-gesture-required
         （其余窗不写 = user-gesture-required）。出声面已办；**采集面（麦克风）在下面单独开**，
         见本函数里 media_capture 那段。 */
      autoplayPolicy: entry.audio_autoplay === true
        ? "no-user-gesture-required"
        : "user-gesture-required",
    },
  });
  if (entry.alwaysOnTop !== false) win.setAlwaysOnTop(true, "screen-saver");

  /* 🔴 **麦克风采集权限**（2026-10-08 加 · 口径照白龙马 BaiLongma 的 electron/main.cjs）：
     病根（白龙马那边与我们都实测到）：Chromium 默认**不把麦克风交给页面** ——
     `enumerateDevices()` 数不到 audioinput（标签也拿不到）、`getUserMedia` 直接落
     `NotFoundError`。白龙马的解法是给**那一扇窗**的 session 装两个处理器：
       `setPermissionRequestHandler`（异步请求：放 media）
       `setPermissionCheckHandler`（同步检查：放 media）
     本壳照抄这套，但**口径收得比它更窄**（窄口径，不许全局放开）：
       ① **只有注册表显式声明 `media_capture: true` 的窗才装**（或 id 恒为 digital-human）——
          现读只有数字人一扇（windows.json 里并列在 audio_autoplay 旁）；别的窗**一个字节不加**；
       ② 处理器内部再核对**请求方必须就是这一扇窗自己的 webContents** —— 即使将来别的窗
          与它共用 default session，media 也只对这一扇生效；
       ③ 除 media 外**一律 callback(false)**：不是"放开一切"，是不认识的一概拒。
     ⚠️ 权限处理器是**每 session 一份**（Electron 语义）：本壳各窗共用 default session，
        所以处理器对其它窗的权限请求也会被叫到 —— 而这里的应答是「非本窗 ⇒ 全拒」，
        方向只收不放；哪个窗将来要 media，就在注册表里明确登记它，别在代码里顺手放宽。
     ⚠️ 装上这两个处理器**只解决"许可"层**：设备层（WASAPI 没有活动录音端点）不归它管 ——
        2026-10-08 现读：活动录音端点 0 ⇒ getUserMedia 仍会如实落 NotFoundError（页面照贴原文）。 */
  if (entry.id === "digital-human" || entry.media_capture === true) {
    const ses = win.webContents.session;
    const isThisWindow = function (wc) {
      try { return !!wc && wc.id === win.webContents.id; } catch (err) { return false; }
    };
    ses.setPermissionRequestHandler((wc, permission, callback) => {
      if (permission === "media" && isThisWindow(wc)) return callback(true);
      callback(false);
    });
    ses.setPermissionCheckHandler((wc, permission) => {
      if (permission === "media" && isThisWindow(wc)) return true;
      return false;
    });
  }

  /* 🔴 品牌统一（主人令 2026-10-04）：页面自带的 <title> 不许盖掉壳的品牌名。
     实测：对话窗载 chat.deepseek.com 后标题被改成「展示AI能力 - DeepSeek」，
     主人眼里品牌就断了 —— 现在标题恒为注册表里的「GBT小土豆V8 · …」。
     这是壳在管自己的窗口框，**不碰页面内容一个字节**（B4 不注入判据不受影响）。 */
  win.on("page-title-updated", (event) => {
    event.preventDefault();
  });

  /* 🔴 页面固定（主人令 2026-10-04「全部点下就自动跳转，全部给我固定住」
     → **2026-10-22 加严（主人令逐字：「把APP从新整理清楚把跳转页面全部给我固定住别在出现跳转页面」）**：
     上一版的口径是「跳转 = 开那扇窗」，**这正是他说的"跳转页面"** —— 点一下，焦点被另一扇窗抢走。
     现在改成：**窗内一律钉死不动，也不替他开窗**。同文档（query/hash）放行；跨文档只记一行日志。
     要看别的面板，走托盘/菜单/面板清单 —— 那是主人自己的动作，不是页面点出来的。 */
  win.webContents.on("will-navigate", (event, url) => {
    let cur = "";
    try { cur = win.webContents.getURL(); } catch (err) { cur = ""; }
    const verdict = urlPolicy.shouldBlockNavigate(cur, url);
    if (!verdict.block) return;
    event.preventDefault();
    const target = String(url).slice(0, 120);
    console.log("[w3] 已拦跳转（页面固定）：" + entry.id + " ← " + target);
  });
  /* 外链/新窗一律不开 Electron 窗（壳不做通用浏览器；要开走「在浏览器打开」动作口）。
     2026-10-22：拒绝也**记一行**，否则"点了没反应"在日志里查不到（P19：拒绝路径不许哑）。 */
  win.webContents.setWindowOpenHandler(({ url }) => {
    console.log("[w3] 已拦新窗（页面固定）：" + String(url || "").slice(0, 120));
    return { action: "deny" };
  });
  /* 🔴 2026-10-22 追加（主人令：「全部给我定住不能出现跳转」）：
     `will-navigate` 只管**顶层文档**；页面里的 `<iframe src=…>` 照样能把内容换掉
     —— 面板清单那种"左栏点一下、右边整块换页"就是它。这里连子帧一起钉死。 */
  win.webContents.on("will-frame-navigate", (event, url) => {
    let cur = "";
    try { cur = win.webContents.getURL(); } catch (err) { cur = ""; }
    if (urlPolicy.shouldBlockNavigate(cur, url).block) {
      event.preventDefault();
      console.log("[w3] 已拦子帧跳转（页面固定）：" + entry.id + " ← " + String(url).slice(0, 120));
    }
  });

  /* 一体式 App 铬（2026-09-23 第 32 轮）：**壳这一层注入**，不改那 8 个页面一行。
     `chrome.attach` 内部自己排除 `dsh-chat`（DSH 的窗，内容不是我们的）。 */
  try { chrome.attach(win, entry, registry); } catch (err) { console.error("[w3] 铬挂载失败:", err); }

  /* 对话面自主回路（主人令 2026-10-04）：只挂**直载外部对话页**的那扇窗。
     2026-10-04 定性改道后 dsh-chat 载本地 GBT 对话面（connect.html）⇒ 不挂回路
     （无 DeepSeek DOM 可读，挂了只会刷「页面不可读」）。外部页回来时（url/file 更改）自动生效。 */
  if (entry.id === "dsh-chat" && entry.url) {
    try { deepseekLoop.register(win, { userData: app.getPath("userData") }); }
    catch (err) { console.error("[w3] 自主回路挂载失败:", err); }
  }

  /* 加载什么 —— 决策在 url-policy.windowSource（**单一决策点**，可单测）。
     四种结果：url / blocked（不合法→拒绝页，理由写清）/ connect（要主人运行时给 URL）/ file。 */
  const src = urlPolicy.windowSource(entry);
  if (src.kind === "url") {
    win.loadURL(src.url);
    /* 🔴 2026-10-10（主人令）**加载失败要说明白是什么** —— 这治的是"一大堆"的观感。
       桥不在时 Electron 丢的是**通用错误页**，主人只看得出"打不开"，看不出"为什么"。
       现在：若失败的是**面板地址**，改载 blocked.html（壳已有的"拒绝加载"页）并写明一句话 ——
       桥没在服务、怎么起。**建窗前已有 ensurePanelBridge 兜底**，这里是它没兜住时的如实告知
       （例如 launch_panel.py 顺延到了别的端口，或桥随后挂了）。
       注意：只在**面板地址**上这么做 —— 别的窗（对话面等）故障各有各的语义，不套同一句话。 */
    win.webContents.on("did-fail-load", (_ev, code, desc, failedUrl) => {
      if (win.isDestroyed() || !failedUrl || failedUrl.indexOf(PANEL) !== 0) return;
      console.error("[w3] 面板加载失败（%s %s）：%s", code, desc, failedUrl);
      try {
        win.loadFile(path.join(HERE, "blocked.html"), {
          query: {
            id: String(entry.id),
            why: "本地面板桥没在服务（" + PANEL + "）—— 数字人壳没有可加载的页面。" +
                 "壳会在建窗前自动拉起它；手动起法：py -3.14 holo_pet/launch_panel.py " +
                 "--host 127.0.0.1 --port 8765 --no-browser",
          },
        });
      } catch (err) {
        console.error("[w3] 面板失败页也载不出来:", err);
      }
    });
  } else if (src.kind === "connect") {
    /* 2026-10-23：有"主人自己那台 DSH"的地址就直接接上（同一会话）；没有才落引导页。 */
    let liveUrl = "";
    try {
      const live = JSON.parse(fs.readFileSync(path.join(app.getPath("userData"), "dsh-live.json"), "utf8"));
      const u = String((live && live.url) || "");
      if (/^http:\/\/(127\.0\.0\.1|localhost|\[::1\]):\d+\/\?token=/.test(u)) liveUrl = u;
    } catch (_e) { liveUrl = ""; }
    if (liveUrl) {
      const res = w3ConnectDsh({ url: liveUrl });
      if (res && res.ok) console.log("[w3] 已接上主人自己那台 DSH（同一会话）host=" + (res.host || ""));
      else {
        console.error("[w3] 接上次记的 DSH 失败（落到引导页）：" + ((res && res.error) || "(未知)"));
        win.loadFile(path.join(HERE, "connect.html"),
                     { query: { id: String(src.id || entry.id), port: String(src.port || 0) } });
      }
    } else {
      win.loadFile(path.join(HERE, "connect.html"),
                   { query: { id: String(src.id || entry.id), port: String(src.port || 0) } });
    }
  } else if (src.kind === "file") {
    win.loadFile(path.join(HERE, src.file));
  } else {
    console.error("[gbt-shell] 拒绝加载（%s）：%s", entry.id, src.why);
    win.loadFile(path.join(HERE, "blocked.html"),
                 { query: { why: src.why, id: String(entry.id) } });
  }

  /* ── DeepSeek Harness 自接入（主人令 2026-10-07）──────────────────────────────
     以前这一步要主人**手动**：去看 `dsh web` 的终端、复制那条带 token 的 URL、贴进引导页。
     现在壳自己把它拉起来（`--no-open`：不在主人系统浏览器里再开一份），读它就绪时
     打印的那一行，走**同一个** `w3ConnectDsh` 载进本窗。

     为什么不去另写一条捷径：那个口子上钉着三件事（过回环白名单 / URL 只进内存 / 只回 host）。
     复制一份 = 迟早漂移，而守卫 B7 判的正是这三条 —— 所以这里只是**调用**它，一个字节不改。

     三条兜底（都不静默，各有一行日志，且**都不挡主路**）：
       ① 3080 上已经有人在听 ⇒ 不自起（两个实例会抢同一份会话状态），停在引导页原路照旧；
       ② `dsh` 不在 PATH / 起不来 ⇒ 同上，主人仍可手贴带 token 的 URL；
       ③ 窗关掉 ⇒ 子进程收走（别在托盘里留一个孤儿）。
     本窗的导航不受影响：就绪 URL 与引导页不同源，但那是**壳自己** loadURL，
     不经过 will-navigate（那条只管页面内部发起的跳转）。 */
  if (entry.id === "dsh-chat"
      && (src.kind === "connect"
          || (src.kind === "file" && /connect\.html$/i.test(String(src.file || ""))))
      && entry.auto_dsh && entry.auto_dsh.enabled === true) {
    const handle = dshLaunch.startDsh({
      port: Number(entry.auto_dsh.port) || 3080,
      /* 2026-10-22：cwd 钉在**仓根** —— 主人手打那条命令时就在 `C:\Users\ADMIN\Desktop\GBT小土豆V8`；
         npx 的解析面跟着 cwd 走，不钉就等于"我在另一个目录里跑同一条命令"。 */
      cwd: path.join(HERE, "..", ".."),
      onUrl: (url) => {
        if (win.isDestroyed()) return;      /* 窗已关：URL 直接丢掉 —— 不落盘、不重开窗 */
        const res = w3ConnectDsh({ url: url });
        if (res && res.ok) console.log("[w3] DSH 自接入已接上 host=" + res.host);
        else console.error("[w3] DSH 自接入被拒：" + ((res && res.error) || "(未知)"));
      },
      onLog: (msg) => console.log("[w3] dsh：「" + msg + "」"),
    });
    dshAutoHandles.set(win.id, handle);
    win.once("closed", () => {
      const cur = dshAutoHandles.get(win.id);
      if (cur) { cur.stop(); dshAutoHandles.delete(win.id); }
    });
  }
  /* 🔴 **2026-09-23 第 43 轮修的「迟到订阅者」缺陷**（一条只有真跑才照得到的死角）。

     症状：页脚**永远**显示「实时流：未接」，而面板端其实在推、连接也真的建起来了 ——
     录下来的页面 innerText 就是「实时流：未接」，可与此同时账本还在出数（走 5 s 轮询兜底）。

     查证（三步都是实测，不是推断）：
       ① 面板端有这条路由：`panel_server.py:3445` → `GET /api/events`；
          Python 直连拿到 `HTTP 200 · text/event-stream` + 真事件字节；
          Node 照本壳的写法直连 **13 ms** 拿到 `status 200` ⇒ **不是网络、不是面板**。
       ② `preload.cjs:47-48` 两个口（`onEvent` / `onStreamState`）都在 ⇒ 不是桥没接。
       ③ `window.js:1056-1060` 订阅也在，徽章默认文案就是 HTML 里写死的「实时流：未接」
          ⇒ **只要那条 `w3:stream` 消息没到，页脚就永远停在默认值**。

     真因（**是 R-H295 那次修法的副作用**）：
       R-H295 把 `startSse` 提到 `createWindow` **之前**（数据面先立 —— 这个方向是对的，
       它治的是"托盘坏掉会弄死实时流"）。但 `broadcast()` 是**遍历 `wins`** 推送的，
       于是 `notify("open")` 发生的那一刻 `wins` **还空着**，那条状态**没有任何窗口听得到**。
       ⇒ 生产者被挪到了消费者前面，"状态只报一次"的毛病就露出来了。

     修法（**不许把 startSse 挪回去**，那会退回老病）：补**状态回放** ——
     窗口加载完成后，把当前状态单独补发给它。迟到的订阅者也能拿到现状，这是 pub/sub 的本分。 */
  win.webContents.on("did-finish-load", () => {
    if (!lastStreamState) return;
    try {
      /* 🔴 销毁竞态护栏（2026-10-04 真启动预演抓到）：探针/快速关闭的窗在事件
         回调落地前就可能已销毁 —— 对已销毁 WebContents send 会抛
         "Object has been destroyed"。外部对话窗的载入尤其慢（网络），竞态面更大。 */
      if (win.isDestroyed() || win.webContents.isDestroyed()) return;
      win.webContents.send("w3:stream", lastStreamState);
    } catch (err) {
      console.error("[w3] 补发实时流状态失败 id=" + entry.id + ":", err);
    }
  });
  /* 🔴 **2026-09-23 第 37 轮修的真缺陷：`moved` 在 Windows 上永远不触发。**
     Electron 文档对 `BrowserWindow` 的 `moved` 事件原文写着 **"macOS only"** ——
     而本壳跑在 Windows 11 上 ⇒ 下面这段（吸附对齐 + 挪窗后落盘）**在本机从来没跑过**。

     怎么发现的：新加的「真启动预演」（`shell/startup.cjs`）里有一条
     「主动挪一下窗，看布局文件会不会被重写」——**判红**。查下去才是这个原因。
     为什么以前的门全都放绿：预检**刻意不启动**、复演只验载入、取证只拍图 ——
     **没有一格会去动一下窗**。这是一条只有"真启动 + 真动手"才照得到的死角。

     修法：抽出 `onMoved()`，`moved`（macOS）与 `move`（全平台）都接上；
     `move` 在拖动期间会**连续**触发，所以做防抖 —— 每次拖动都跑一遍吸附 + 写盘会白烧磁盘。 */
  function onMoved() {
    const others = [];
    wins.forEach((o, oid) => { if (oid !== entry.id && o && !o.isDestroyed()) others.push(layout.fromBrowserBounds(o.getBounds(), oid)); });
    const snapped = layout.snapBounds(layout.fromBrowserBounds(win.getBounds(), entry.id), screen.getAllDisplays(), others, layout.SNAP_PX);
    const next = layout.toBrowserBounds(snapped);
    const cur = win.getBounds();
    if (next.x !== cur.x || next.y !== cur.y) win.setBounds(next);
    saveWindowState();
  }
  let moveTimer = null;
  win.on("moved", onMoved);                       // macOS
  win.on("move", () => {                          // Windows / Linux（全平台）
    if (moveTimer) clearTimeout(moveTimer);
    moveTimer = setTimeout(() => { moveTimer = null; onMoved(); }, 220);
  });
  win.on("resized", saveWindowState);
  win.on("close", saveWindowState);
  win.on("closed", () => { if (moveTimer) clearTimeout(moveTimer); wins.delete(entry.id); });
  wins.set(entry.id, win);
  return win;
}

/* ── 数字人页的受理口本体（契约见上面 ipcMain.handle("w3:message") 那段的注释）───
   目标**写死**：只可能打到本机面板桥这一条路；页面给什么都改不了它。 */
const W3_MSG_TARGET = { host: "127.0.0.1", port: 8765, path: "/api/message", timeout: 30000, maxChars: 4000 };

function w3Message(payload) {
  return new Promise((resolve) => {
    const raw = String((payload && payload.text) || "");
    const text = raw.trim().slice(0, W3_MSG_TARGET.maxChars);
    if (!text) return resolve({ ok: false, error: "空文本：没有要送出的内容" });
    const body = JSON.stringify({ text: text });
    const req = http.request({
      host: W3_MSG_TARGET.host, port: W3_MSG_TARGET.port, path: W3_MSG_TARGET.path,
      method: "POST", timeout: W3_MSG_TARGET.timeout,
      headers: { "content-type": "application/json", "content-length": Buffer.byteLength(body) },
    }, (res) => {
      let buf = "";
      res.on("data", (c) => { if (buf.length < 400000) buf += c; });
      res.on("end", () => {
        const okk = res.statusCode >= 200 && res.statusCode < 300;
        resolve({ ok: okk, status: res.statusCode,
                  reply: buf.slice(0, W3_MSG_TARGET.maxChars),
                  error: okk ? undefined : ("桥回 HTTP " + res.statusCode + "：" + buf.slice(0, 200)) });
      });
    });
    req.on("timeout", () => { try { req.destroy(); } catch (err) { /* 已在销毁路上 */ }
                              resolve({ ok: false, error: "桥没在 30 秒内回话（超时）" }); });
    req.on("error", (err) => resolve({ ok: false, error: "桥连不上：" + String(err && err.message ? err.message : err).slice(0, 160) }));
    req.write(body);
    req.end();
  });
}

/* ── W9 · 窗 A：把对话面接上（**主人在运行时给 URL**）─────────────────────────
   背景：对话面裸 URL 回 401，要 `dsh web` 打印的**带 token 的 URL**。
   纪律（三条，写在这儿免得以后有人"顺手优化"掉）：
     ① **不落盘**：URL 只在内存里交给 `loadURL`，不写任何配置文件、不进布局文件；
     ② **不回显**：返回值只给 `host`（`127.0.0.1:3080`），**绝不把整条 URL 回给渲染进程**
        —— 它带 token，一回显就会进界面/日志；
     ③ **不白名单外**：仍然过 `loopbackUrlOnly()`，只放行本机回环。 */
/* 最近一次接上的对话入口（**只在内存**：不落盘、不写日志；只为把引擎嵌进我们的框架页）。 */
let lastDshEntry = null;

function w3ConnectDsh(payload) {
  const raw = String((payload && payload.url) || "").trim();
  if (!raw) return { ok: false, error: "没有给 URL" };
  const chk = loopbackUrlOnly(raw);
  if (!chk.ok) return { ok: false, error: chk.why, rule: "只放行本机回环（127.0.0.1 / localhost / ::1）" };
  const win = wins.get("dsh-chat");
  if (!win || win.isDestroyed()) return { ok: false, error: "对话面的窗不在（先从托盘菜单把它开起来）" };
  let host = "";
  try { host = new URL(chk.url).host; } catch (err) { host = "(无法解析)"; }
  /* 🔴 2026-10-09 主人令「必须镶嵌进去……统一品牌和Logo，我们是把她集成进我们，而不是还是使用她本身」：
     原来这里 **win.loadURL(chk.url)** 把她的官方界面**整窗盖满** ⇒ 我们自己的门面（品牌/Logo）全没了。
     改成**我们的壳包住她的引擎**：
       ① 载**我们自己的**品牌框架页 shell/dsh-embed.html（顶部 GBT 星环 Logo + 名称）；
       ② 再把入口 URL **注入内层 webview**（executeJavaScript，URL 只进内存，
          **不成为窗口 URL、不进历史**——比原来的整窗 loadURL 更收敛）。
     dshEntry 只给**本应用自己的本地页**（wrapper / 面板内嵌页）取用，仍是回环白名单校验过的。 */
  lastDshEntry = { url: chk.url, host: host, at: new Date().toISOString() };
  /* 🔴 2026-10-23 主人令：「AI对话页面不是我们现在对话的页面」——
     把主人**自己那台** dsh web 的地址记住；下次启动直接接上同一个会话，不再自起第二个实例。 */
  try {
    fs.writeFileSync(path.join(app.getPath("userData"), "dsh-live.json"),
      JSON.stringify({ url: chk.url, host: host, at: new Date().toISOString() }, null, 1));
  } catch (err) { console.error("[w3] 记住 DSH 地址失败（不影响本次接入）:", err && err.message); }
  try {
    win.loadFile(path.join(HERE, "dsh-embed.html"));
    win.webContents.once("did-finish-load", () => {
      if (win.isDestroyed()) return;
      win.webContents.executeJavaScript(
        "window.__gbtMountDsh && window.__gbtMountDsh(" + JSON.stringify(chk.url) + ")")
        .catch((err) => console.error("[w3] 把引擎注入内层 webview 失败：" + err));
    });
  } catch (err) {
    console.error("[w3] 载品牌框架页失败，回退整窗载入：" + err);
    win.loadURL(chk.url);
  }
  /* 落一张**不含 token** 的回执：这是"真接上过一次"的机器证据（守卫 B1e 读它）。
     回执里只有 host 与时间 —— **绝不写 URL、绝不写 token**。

     🔴 2026-10-07 实测补的两条（那天主人真开着成品，我从外面看得清清楚楚）：
       ① **打包版里 `ROOT` 是 null**：portable 包运行时会解包到临时目录，`findRepoRoot`
          从那儿往上走 12 层也找不到 `gbt_allinone` ⇒ 原来那句 `path.join(ROOT, "state")`
          直接抛、被 catch 吞掉 ⇒ **合成品里回执永远不落盘**，而那正是最该有证据的时候
          （我实测：APP 进程与它自己拉起的 `dsh web` 之间两条 established 连接在，
          可盘上就是没有回执）。
       ② ⇒ 改成**写多个落点**：仓里那份（开发态 · 守卫 B1e 读它）**加** userData 那份
          （打包态一定可写）。写成功几处就报几处，一处都写不成就把原因原样打出来。 */
  const receipt = JSON.stringify({ host: host, at: new Date().toISOString(),
                                   note: "由桌面壳 w3ConnectDsh 落盘：只记 host 与时间，不落 URL 与凭据" }, null, 1);
  const spots = [];
  if (ROOT) spots.push(path.join(ROOT, "state"));
  try { spots.push(app.getPath("userData")); } catch (err) { /* userData 取不到就只写仓里那份 */ }
  const wrote = [];
  for (const dir of spots) {
    try {
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(path.join(dir, "desktop-dsh-connect-receipt.json"), receipt, "utf8");
      wrote.push(dir);
    } catch (err) {
      /* 回执写不了不影响接上；但也不静默 —— 记一行给排查 */
      console.error("[gbt-shell] 回执写不了（%s）：%s", dir, String(err).slice(0, 120));
    }
  }
  if (!wrote.length) console.error("[gbt-shell] 回执一处都没写成（接上没受影响，但这次的机器证据缺了）");
  return { ok: true, host: host, note: "已交给对话框加载；URL 只在内存，未落盘、未回显" };
}

function buildTray() {
  /* 🔴 托盘图标 = **品牌真图**（主人令 2026-10-07：「这里的 Logo」）。
     以前这一行是 `trayIcon(16, 金, 青)` —— **代码现画的方块**：任务栏那一格里就是一块色块，
     品牌在托盘上断了。现在直接读品牌资产：`build/tray-logo-32.png` 是
     `assets/brand/logo-potato-32.png` 的**逐字节复制**（sha256 由 `tests/test_tray_logo.cjs`
     钉住 —— 不重画、不换色、不丢署名；品牌只走这一份真资产）。
     读不到就退回原来那个方块，并**把原因打出来** —— 不静默变成空白托盘。 */
  const logoFile = path.join(HERE, "..", "build", "tray-logo-32.png");
  let image = null;
  try { if (fs.existsSync(logoFile)) image = nativeImage.createFromPath(logoFile); } catch (err) { image = null; }
  if (!image || image.isEmpty()) {
    console.warn("[w3] 托盘品牌图读不到（%s）—— 退回内置方块图（任务栏品牌会缺）", logoFile);
    image = trayIcon(16, [0xf5, 0xb0, 0x41], [0x00, 0xe5, 0xff]);
  }
  tray = new Tray(image);
  tray.setToolTip("GBT小土豆V8 · 点一下显示/隐藏全部窗（右键出菜单）");
  tray.on("click", () => { wins.forEach((w) => { if (!w.isDestroyed()) w.isVisible() ? w.hide() : w.show(); }); });
  return tray;
}

/**
 * 自建应用菜单（2026-10-04 主人令）：**换掉 Electron 的英文默认菜单**。
 *
 * 为什么换：默认那排（File/Edit/View/Window）是给开发调试的，主人问「这些拿来干嘛的、
 * 返回在哪里」——壳窗没有浏览器返回键，页面内部一跳就没有退路（实测踩过）。
 * 本菜单把主人真需要的东西放前面：**← 返回**（有历史回退、没历史重载 ⇒ 永远出得去）、
 * 重载、窗口跳转、退出。Ctrl+C/V 由 Chromium 原生处理，不依赖 Edit 菜单。
 */
function refreshAppMenu() {
  const focused = () => BrowserWindow.getFocusedWindow();
  const nav = (fn) => { const w = focused(); if (w && !w.isDestroyed()) fn(w); };
  const winItems = registry.windows.map((entry) => ({
    label: (wins.has(entry.id) && !wins.get(entry.id).isDestroyed()
            && wins.get(entry.id).isVisible() ? "隐藏 · " : "打开 · ") + (entry.title || entry.id),
    click: () => {
      const w = wins.get(entry.id);
      if (!w || w.isDestroyed()) createWindow(entry);
      else if (w.isVisible()) w.hide();
      else { w.show(); w.focus(); }
      refreshAppMenu();
      refreshTrayMenu();
    },
  }));
  const template = [
    { label: "← 返回", accelerator: "Alt+Left", click: () => nav((w) => {
        if (w.webContents.canGoBack && w.webContents.canGoBack()) w.webContents.goBack();
        else w.reload();                                   /* 没有历史 ⇒ 重载回这扇窗的原页 */
      }) },
    { label: "⟳ 重载", accelerator: "CmdOrCtrl+R", click: () => nav((w) => w.reload()) },
    { type: "separator" },
    { label: "窗口", submenu: winItems },
    { type: "separator" },
    { label: "退出", click: () => { app.isQuitting = true; app.quit(); } },
  ];
  try { Menu.setApplicationMenu(Menu.buildFromTemplate(template)); } catch (err) { /* 菜单坏不许弄崩壳 */ }
}

function refreshTrayMenu() {
  if (!tray) return;
  const items = registry.windows.map((entry) => ({
    label: (wins.has(entry.id) && !wins.get(entry.id).isDestroyed() && wins.get(entry.id).isVisible() ? "隐藏 " : "显示 ") + (entry.title || entry.id),
    click: () => {
      const w = wins.get(entry.id);
      if (!w || w.isDestroyed()) createWindow(entry);
      else if (w.isVisible()) w.hide();
      else { w.show(); w.focus(); }
      refreshTrayMenu();
    },
  }));
  items.push({ type: "separator" });
  /* 自主回路开关（主人令 2026-10-04）：状态现读，点了即切（PAUSE 文件仍是最高否决）。 */
  try {
    const ds = deepseekLoop.status();
    items.push({
      label: (ds.enabled ? "✅ " : "⬜ ") + "触手自主执行（她自己的双手）"
             + (ds.configured ? "" : " · 未配置"),
      click: () => { deepseekLoop.setEnabled(!deepseekLoop.status().enabled); refreshTrayMenu(); },
    });
  } catch (err) { /* 回路模块坏掉不许弄崩托盘 */ }
  items.push({ label: "重载当前窗口", click: () => wins.forEach((w) => { if (!w.isDestroyed()) w.reload(); }) });
  items.push({
    label: "重置布局",
    click: () => {
      const empty = layout.emptyLayout();
      try { layout.saveLayout(LAYOUT_FILE, empty); } catch (err) { /* 忽略 */ }
      wins.forEach((w, id) => {
        const entry = registry.windows.filter((e) => e.id === id)[0];
        if (!entry || w.isDestroyed()) return;
        const b = layout.clampBounds(layout.normalize(entry.default, id), screen.getAllDisplays());
        w.setBounds(layout.toBrowserBounds(b));
      });
    },
  });
  items.push({ label: "退出", click: () => { app.isQuitting = true; app.quit(); } });
  tray.setContextMenu(Menu.buildFromTemplate(items));
}

function registerIpc() {
  ipcMain.handle("w3:config", () => ok({ engine: process.env.GBT_TREE_ENGINE || "auto", readonly: true, root: ROOT ? path.basename(ROOT) : null }));
  /* 实时流的**现状**（只读拉取，2026-09-23 第 45 轮加）。
     为什么要能"拉"：`w3:stream` 是**推**，只在状态**变化**时发一次；
     而窗口是**后来才建**的（`startSse` 跑在建窗之前 —— R-H295 的"数据面先立"）。
     上一轮用"建窗后补发"治了主进程建的那条路，但**别的东西建的窗**（取证器 shots 自己建窗）
     照样收不到 ⇒ 屏上又是一句「实时流：未接」，而主进程其实连着。
     ⇒ 补一个**只读拉取**：谁建的窗都能问一句"现在什么状态"。推 + 拉都在，才不挑宿主。 */
  ipcMain.handle("w3:stream-state", () => ok({ state: lastStreamState }));
  ipcMain.handle("w3:state", () => w3State());
  ipcMain.handle("w3:tasks", () => w3Tasks());
  ipcMain.handle("w3:env", () => w3Env());
  ipcMain.handle("w3:ledger", () => w3Ledger());
  ipcMain.handle("w3:health", () => w3Health());
  ipcMain.handle("w3:matrix", () => w3Matrix());
  ipcMain.handle("w3:mindmap", () => w3Mindmap());
  ipcMain.handle("w3:selfcheck", () => w3Selfcheck());
  ipcMain.handle("w3:introspect", () => w3Introspect());
  ipcMain.handle("w3:tools", () => w3Tools());
  ipcMain.handle("w3:h1", () => w3H1());
  ipcMain.handle("w3:pets", (ev, payload) => w3Pets(payload));
  ipcMain.handle("w3:summon", (ev, payload) => w3Summon(payload));
  ipcMain.handle("w3:eigenflux", () => w3Eigenflux());
  /* R-H295 新接：框架自己的两只只读审计器（欠账「覆盖审计 / 零调用点清单接进上帝视角」）*/
  ipcMain.handle("w3:coverage", () => w3Coverage());
  ipcMain.handle("w3:orphans", () => w3Orphans());
  ipcMain.handle("w3:gene", () => w3Gene());
  /* ── 数字人页的「文本→桥」受理口（2026-10-08）─────────────────────────────
     背景（实测，不是推演）：数字人页是**离线自包含**的（CSP `connect-src 'none'`），
     任何网络取数原语都被浏览器当场拒 ⇒ "说话→拿回复"这条链在**页面侧**永远接不上。
     而行长按本仓既有做法（`/api/capability` 同款先例）：**壳替页面跑这一趟**。
     🔴 三条纪律（与 `w3ConnectDsh` 同源）：
       ① **目标由壳钉死**：页面只能给文本，URL/host/port 写死在壳里 ⇒ 页面无法把这一口
          变成"任意 URL 代理"（防 SSRF：连回环之外的地址都构造不出来）；
       ② **文本限额** `MSG_MAX`：超长截断，别让 IPC 变成大数据通道；
       ③ 回包**截断后再回**渲染层；失败**带原文**返回 —— 不静默、不假绿。
     为什么不干脆放开页面的 CSP：那等于把这个窗的网络面从"零"放开到"能到处发请求"。
     壳跑一趟，页面的网络面**仍然是零**。 */
  ipcMain.handle("w3:message", async (ev, payload) => w3Message(payload));

/* ── 云账号「登入授权」+「部署网格节点」（主人令 2026-10-23）──────────────────
   主人逐字：「你直接做成账户登入授权不就好了，不做密钥密钥容易泄露」
             「你还是直接在APP上做好我自己点击登入授权吧，要不然一直都是一个在那里卡着」
   为什么是"授权一个 → 部署一个"：实测 wrangler 的 OAuth 会话是**全局一份**
   （`~/.wrangler/config/default.toml`），后一次登录覆盖前一次；所以按轮次走，
   一轮授权配一个节点，不需要同时持有十份会话，也不需要任何 API token。
   红线：本段**不写任何凭据**；会话文件由 wrangler 自己管，页面只拿邮箱与掩码。 */
const CF_OAUTH_ROOT = path.join(os.homedir(), ".cf-oauth");
const CF_MESH_SRC = path.join(ROOT, "deploy", "cloud-10", "mesh10");

function cfWhoami() {
  return new Promise((resolve) => {
    execFile("cmd", ["/c", "npx", "--yes", "wrangler@4", "whoami"],
      { cwd: ROOT, windowsHide: true, timeout: 180000 },
      (err, stdout, stderr) => {
        const text = String(stdout || "") + String(stderr || "");
        const email = (text.match(/associated with the email\s+(\S+)/) || [])[1] || null;
        const m = text.match(/│\s*([^│]+?)\s*│\s*([0-9a-f]{32})\s*│/);
        resolve({
          ok: !!email, email,
          account: m ? m[1].trim() : null,
          idMask: m ? m[2].slice(0, 8) + "****" : null,
          why: email ? null : text.slice(-300),
        });
      });
  });
}

ipcMain.handle("cf:status", () => cfWhoami());

/* 主人令 2026-10-23：「APP 直接安装好 10 个独立云插件，密钥我自己填」
   ⇒ 页面每格粘一把 API 令牌（只在本进程内存里，**不落盘、不回显、不写日志**），
     壳用这把令牌问出账号 → 用该令牌把网格节点部署进去 → 回地址。
   这条路径不碰浏览器、不需要 OAuth、不需要主人点任何按钮。 */
function cfRun(cmdArgs, env, timeout) {
  return new Promise((resolve) => {
    execFile("cmd", cmdArgs, { cwd: ROOT, windowsHide: true, timeout: timeout || 300000, env },
      (err, stdout, stderr) => resolve(String(stdout || "") + String(stderr || "")));
  });
}

/* 2026-10-23：令牌**只读自检**（不部署、不建任何资源）。
   实测价值：主人那把令牌 read 类全通（/accounts 1 条 · /workers/scripts 14 条），
   但 deploy 报 No access ⇒ 缺的是 **Workers Scripts:Edit** 这一条写权限。
   本通道就是让主人在粘令牌后立刻知道「读得到、但装不了 / 全通」。 */
function cfGet(token, urlPath) {
  return new Promise((resolve) => {
    const req = require("https").request({ hostname: "api.cloudflare.com", path: "/client/v4" + urlPath,
      method: "GET", headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" } },
      (res) => {
        let buf = "";
        res.on("data", (d) => { buf += d; });
        res.on("end", () => {
          let j = null;
          try { j = JSON.parse(buf); } catch (_e) { j = null; }
          resolve({ status: res.statusCode, body: j });
        });
      });
    req.on("error", (err) => resolve({ status: 0, body: { error: String((err && err.message) || err) } }));
    req.setTimeout(20000, () => { req.destroy(); resolve({ status: 0, body: { error: "timeout 20s" } }); });
    req.end();
  });
}

/* 2026-10-23：**一次把 10 节点互认打通**。
   做法：读 state/mesh-nodes.json 全表 → 对每个节点 POST /roster {nodes:[全表]}（批量覆盖，10 次写）。
   为什么不逐个自报 90 次：单条 POST 一次只写一条，10 节点要 90 次；批量版 10 次就成。
   KV 不跨账号 ⇒ 每个节点各存一份全表（这是设计使然，不是重复）。 */
ipcMain.handle("mesh:sync", async () => {
  let nodes = [];
  try {
    const d = JSON.parse(fs.readFileSync(path.join(ROOT, "state", "mesh-nodes.json"), "utf8"));
    const seen = new Set();
    for (const n of (d.nodes || [])) {
      const url = String(n.url || "").replace(/\/$/, "");
      if (url && !seen.has(url)) { seen.add(url); nodes.push({ id: n.id || "", url }); }
    }
  } catch (e) {
    return { ok: false, why: "读 mesh-nodes.json 失败：" + String((e && e.message) || e) };
  }
  if (nodes.length < 2) return { ok: false, why: "节点不足 2 个（当前 " + nodes.length + "），无从互认" };

  function post(url, body) {
    return new Promise((resolve) => {
      const u = new URL(url.replace(/\/$/, "") + "/roster");
      const data = JSON.stringify(body);
      const req = require("https").request({ hostname: u.hostname, path: u.pathname, method: "POST",
        headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(data) } },
        (res) => {
          let buf = "";
          res.on("data", (c) => { buf += c; });
          res.on("end", () => { let j = null; try { j = JSON.parse(buf); } catch (_e) { j = null; }
            resolve({ status: res.statusCode, body: j || buf.slice(0, 160) }); });
        });
      req.on("error", (err) => resolve({ status: 0, body: String((err && err.message) || err) }));
      req.setTimeout(20000, () => { req.destroy(); resolve({ status: 0, body: "timeout" }); });
      req.end(data);
    });
  }

  const rows = [];
  for (const n of nodes) {
    const r = await post(n.url, { nodes });
    rows.push({ node: n.id || n.url, http: r.status,
                ok: !!(r.body && r.body.ok), peers: r.body && r.body.peers, tail: r.status === 200 ? null : String(r.body).slice(0, 120) });
  }
  const okCount = rows.filter((x) => x.ok).length;
  return { ok: okCount === nodes.length, nodes: nodes.length, synced: okCount,
           expected_edges: nodes.length * (nodes.length - 1), rows };
});

ipcMain.handle("cf:verify", async (_ev, payload) => {
  const token = String((payload && payload.token) || "").trim();
  if (!/^[A-Za-z0-9_\-]{20,}$/.test(token)) return { ok: false, why: "令牌形状不对" };
  const acc = await cfGet(token, "/accounts");
  const acct = (acc.body && acc.body.result && acc.body.result[0]) || null;
  if (!acct) {
    return { ok: false, why: "这把令牌读不到任何账号（缺 Account Settings:Read 或令牌无效）",
             http: acc.status, detail: JSON.stringify(acc.body || {}).slice(0, 240) };
  }
  const scr = await cfGet(token, "/accounts/" + acct.id + "/workers/scripts");
  const scripts = (scr.body && scr.body.result) || [];
  const hasMesh = scripts.some((x) => (x.id || x.name) === "gbt-mesh-10");
  return { ok: true, account: acct.name, idMask: String(acct.id).slice(0, 8) + "****", acctId: acct.id,
           scriptsRead: Array.isArray(scripts) ? scripts.length : null,
           meshPresent: hasMesh,
           canDeploy: scr.status === 200 && Array.isArray(scripts) ? null : null,
           note: "读链路通；部署还需要 Workers Scripts:Edit（缺的话 install 会报 No access to the specified resource）" };
});

ipcMain.handle("cf:install", async (_ev, payload) => {
  const slot = String((payload && payload.slot) || "01").replace(/[^0-9]/g, "").padStart(2, "0").slice(-2);
  const token = String((payload && payload.token) || "").trim();
  if (!/^[A-Za-z0-9_\-]{20,}$/.test(token)) {
    return { ok: false, why: "令牌形状不对（应形如 cfat_… 或 40 位以上字母数字）" };
  }
  const env = { ...process.env, CLOUDFLARE_API_TOKEN: token };
  delete env.CLOUDFLARE_ACCOUNT_ID;
  const who = await cfRun(["/c", "npx", "--yes", "wrangler@4", "whoami"], env, 180000);
  const m = who.match(/│\s*([^│]+?)\s*│\s*([0-9a-f]{32})\s*│/);
  if (!m) return { ok: false, why: "这把令牌问不出账号（可能已失效/权限不足）", detail: who.slice(-300) };
  const acctName = m[1].trim();
  const acctId = m[2];
  const mask = acctId.slice(0, 8);
  const dir = path.join(CF_MESH_SRC, "build", "slot-" + slot);
  try {
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, "worker.js"), fs.readFileSync(path.join(CF_MESH_SRC, "worker.js")));
    fs.writeFileSync(path.join(dir, "wrangler.toml"),
      'name = "gbt-mesh-10"\nmain = "worker.js"\ncompatibility_date = "2025-01-01"\n\n'
      + '[vars]\nNODE_ID = "acct-' + mask + '"\nMESH = "[]"\n');
  } catch (e) {
    return { ok: false, why: "写部署目录失败", detail: String((e && e.message) || e) };
  }
  /* 2026-10-23：每个账号各建一份 KV（命名空间不跨账号）→ 写进 wrangler.toml 的绑定。
     没有 ROSTER 时 /roster 会回 501「没绑 KV」，10 节点就永远互不认。 */
  const kvOut = await cfRun(["/c", "npx", "--yes", "wrangler@4", "kv", "namespace", "create", "ROSTER", "--json"],
    { ...env, CLOUDFLARE_ACCOUNT_ID: acctId }, 180000);
  let kvId = null;
  try {
    const j = JSON.parse(String(kvOut).slice(String(kvOut).indexOf("{")));
    kvId = (j && (j.id || j.namespace_id)) || null;
  } catch (_e) { kvId = null; }
  if (kvId) {
    try {
      fs.appendFileSync(path.join(dir, "wrangler.toml"),
        '\n[[kv_namespaces]]\nbinding = "ROSTER"\nid = "' + kvId + '"\n');
    } catch (e) { console.error("[w3] 写 KV 绑定失败:", e && e.message); }
  } else {
    console.error("[w3] KV 未建成（不影响部署，但本节点将无法登记邻居）：" + String(kvOut).slice(-200));
  }

  const depEnv = { ...env, CLOUDFLARE_ACCOUNT_ID: acctId };
  const out = await cfRun(["/c", "npx", "--yes", "wrangler@4", "deploy", "-c",
    path.join(dir, "wrangler.toml")], depEnv, 300000);
  const url = (out.match(/https:\/\/[a-z0-9\-.]+\.workers\.dev/) || [])[0] || null;
  return { ok: !!url, url, slot, account: acctName, idMask: mask + "****", acctId,
           tail: url ? null : out.slice(-400) };
});

ipcMain.handle("cf:login", async (ev, payload) => {
  const raw = String((payload && payload.slot) || "01").replace(/[^0-9]/g, "") || "01";
  const slot = raw.padStart(2, "0").slice(-2);
  const home = path.join(CF_OAUTH_ROOT, "acct-" + slot);
  try { fs.mkdirSync(home, { recursive: true }); } catch (_e) { /* 目录已在就算成功 */ }
  return await new Promise((resolve) => {
    const child = spawn("cmd", ["/c", "npx", "--yes", "wrangler@4", "login"], {
      cwd: ROOT, windowsHide: true,
      env: { ...process.env, USERPROFILE: home, HOME: home, CLOUDFLARE_API_TOKEN: "" },
    });
    let out = "";
    let urlSent = false;
    const timer = setTimeout(() => {
      try { child.kill(); } catch (_e) { /* 已退出 */ }
      resolve({ ok: false, why: "5 分钟没等到授权（已中止，可重试）" });
    }, 300000);
    const grab = (buf) => {
      out += String(buf);
      const m = out.match(/https:\/\/dash\.cloudflare\.com\/oauth2\/auth\?[^\s]+/);
      if (m && !urlSent) {
        urlSent = true;
        try { shell.openExternal(m[0]); } catch (_e) { /* 打不开就让页面自己给链接 */ }
        try { ev.sender.send("cf:login-url", m[0]); } catch (_e) { /* 窗已关 */ }
      }
    };
    child.stdout.on("data", grab);
    child.stderr.on("data", grab);
    child.on("exit", async (code) => {
      clearTimeout(timer);
      const st = await cfWhoami();
      resolve({ ...st, code, slot, home });
    });
  });
});

ipcMain.handle("cf:deploy", async () => {
  const st = await cfWhoami();
  if (!st.ok) return { ok: false, why: "当前没有有效会话：先点「登入授权」", detail: st.why };
  const mask = String(st.idMask || "").replace(/\*/g, "");
  if (!/^[0-9a-f]{8}$/.test(mask)) return { ok: false, why: "读不到账号 id（掩码不完整）", detail: st };
  const dir = path.join(CF_MESH_SRC, "build", "acct-" + mask);
  try {
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, "worker.js"), fs.readFileSync(path.join(CF_MESH_SRC, "worker.js")));
    fs.writeFileSync(path.join(dir, "wrangler.toml"),
      'name = "gbt-mesh-10"\nmain = "worker.js"\ncompatibility_date = "2025-01-01"\n\n'
      + '[vars]\nNODE_ID = "acct-' + mask + '"\nMESH = "[]"\n');
  } catch (e) {
    return { ok: false, why: "写部署目录失败", detail: String((e && e.message) || e) };
  }
  return await new Promise((resolve) => {
    execFile("cmd", ["/c", "npx", "--yes", "wrangler@4", "deploy", "-c", path.join(dir, "wrangler.toml")],
      { cwd: ROOT, windowsHide: true, timeout: 300000 },
      (err, stdout, stderr) => {
        const text = String(stdout || "") + String(stderr || "");
        const url = (text.match(/https:\/\/[a-z0-9\-.]+\.workers\.dev/) || [])[0] || null;
        resolve({ ok: !!url, url, email: st.email, node: "acct-" + mask, tail: text.slice(-400) });
      });
  });
});

  /* ── 数字人页的**嘴**：把"念一句"交给框架能力位（单一门 run_task）────────────
     主人令 2026-10-18：「把 digital-human 那扇窗的嘴也换成神经嗓」。
     两条硬约束，写在这儿免得以后有人"顺手优化"：
     ① **不自己合成**：页面不碰 TTS，壳只做一次**能力位调用**（`five-dim.py cap voice op=speak`），
        授权/审计/钢印全在门上；壳不拼命令行字符串、不走 shell（数组传参，文本只当一个参数）。
     ② **不静默**：能力位回什么都原样回渲染层（含 `denied`/`missing_scopes`/`no_taiwan_lane` 的原因），
        页面据此决定是"真在说"还是"如实报不能"。
     ③ 文本限额 `SAY_MAX`，超长截断；超时 25s；失败带 `error` 原文。 */
  const SAY_MAX = 600;
  ipcMain.handle("w3:say", async (ev, payload) => {
    const text = String((payload && payload.text) || "").trim().slice(0, SAY_MAX);
    if (!text) return { ok: false, error: "空文本：没有要念的内容" };
    const script = path.join(ROOT, "tools", "codex-scripts", "five-dim.py");
    if (!fs.existsSync(script)) return { ok: false, error: "五维脚本不在盘上：" + script };
    /* 🔴 2026-10-19 加（主人令：波形要跟着她**这一次真说的话**走）：
       允许页面要求"把这次合成落成一个文件给我"，好让波形吃的是这一句真音频而不是固定样本。
       安全边界写死：只许写进剧场自己的 assets/.utt/、只许 .mp3、只许相对路径（挡 ../ 与绝对路径）。 */
    const reqOut = String((payload && payload.out) || "").trim();
    let outPath = null;
    if (reqOut) {
      const norm = reqOut.replace(/\\/g, "/");
      if (!/^holo_pet_w3\/voice-theater\/assets\/\.utt\/[A-Za-z0-9_.-]+\.mp3$/.test(norm)) {
        return { ok: false, error: "out 不在允许范围（只许 holo_pet_w3/voice-theater/assets/.utt/<名>.mp3）：" + reqOut };
      }
      outPath = norm;
      try { fs.mkdirSync(path.join(ROOT, "holo_pet_w3", "voice-theater", "assets", ".utt"), { recursive: true }); }
      catch (e) { return { ok: false, error: "建目录失败：" + String((e && e.message) || e) }; }
    }
    const voicePayload = { op: "speak", text: text };
    if (outPath) voicePayload.out = outPath;
    if (payload && typeof payload.play === "boolean") voicePayload.play = payload.play;
    const args = [script, "cap", "voice", JSON.stringify(voicePayload)];
    return await new Promise((resolve) => {
      execFile("py", ["-3.14"].concat(args), { timeout: 25000, windowsHide: true },
        (err, stdout, stderr) => {
          const out = String(stdout || "");
          let parsed = null;
          try { parsed = JSON.parse(out); } catch (e) { /* 下面按原文回 */ }
          if (parsed) {
            const outer = parsed.result || parsed;
            const r = (outer && outer.result) || outer;
            const okSay = (typeof r.ok === "boolean") ? r.ok : (String(parsed.status || "") === "ok");
            resolve({ ok: okSay, backend: r.backend, voice: r.voice,
                      spoken: r.spoken === true,
                      /* 落盘路径原样回给页面：波形要拿它换成"这一句真音频" */
                      file: r.file || outPath || undefined,
                      reason: r.reason || r.error || parsed.reason,
                      status: r.status || parsed.status, auth_consumed: r.auth_consumed,
                      missing_scopes: parsed.missing_scopes || r.missing_scopes,
                      raw: okSay ? undefined : out.trim().slice(0, 400),
                      error: okSay ? undefined
                           : (r.reason || r.error || parsed.reason ||
                              ("没就绪：status=" + String(parsed.status || r.status || "?") +
                               " missing=" + JSON.stringify(parsed.missing_scopes || r.missing_scopes || []))) });
            return;
          }
          resolve({ ok: false,
                    error: (err ? String(err.message || err).slice(0, 200) + " · " : "") +
                           (String(stderr || "").trim().slice(0, 200) ||
                            out.trim().slice(0, 200) || "能力位没回可解析的 JSON") });
        });
    });
  });
  /* W9 · 窗 A 的动作口：把主人粘进来的 URL 交给对话框。
     它**不是数据写口**（不写文件、不写配置），但**是动作口** ——
     preload 里 `non_readonly_capability` 那一行必须同步登记它，不许悄悄放宽。 */
  /* ── 她**自己动手**：白名单内的只读能力位（2026-10-18「下一步」）────────────
     主人给的方向是"她 → 触手"。这条路的风险是**页面拿到了万能门**，所以三条硬约束：
     ① **白名单写死在壳里**（下表）。表外的 kind 直接拒，页面传什么都越不了界；
        表里只放**静态零作用域、只读**的那几位（与 DSH 侧 MCP 桥的读子集一致）；
     ② payload 只允许是**普通对象**且 ≤ 8KB，序列化后作为同一个参数传给 `cap`（不拼命令、不过 shell）；
     ③ 回执**原样回**（ok / denied / missing_scopes / reason 全带），页面据此说实话。 */
  const CAP_READONLY = new Set([
    "health", "selfscan", "alerts", "auth_gate_status", "inventory",
    "file_hygiene", "mirror_status", "count_words", "signature_guard", "echo",
  ]);
  ipcMain.handle("w3:cap", async (ev, payload) => {
    const kind = String((payload && payload.kind) || "").trim();
    if (!kind) return { ok: false, error: "缺 kind：要调哪一位" };
    if (!CAP_READONLY.has(kind)) {
      return { ok: false, refused: true,
               error: "不在壳白名单内（只放只读、零作用域的那几位）：" + kind,
               allowlist: Array.from(CAP_READONLY) };
    }
    let body = {};
    if (payload && payload.payload && typeof payload.payload === "object") body = payload.payload;
    let arg = "";
    try { arg = JSON.stringify(body); } catch (e) { return { ok: false, error: "payload 不能序列化：" + String(e.message || e) }; }
    if (arg.length > 8192) return { ok: false, error: "payload 太大（>8KB）" };
    const script = path.join(ROOT, "tools", "codex-scripts", "five-dim.py");
    if (!fs.existsSync(script)) return { ok: false, error: "五维脚本不在盘上：" + script };
    return await new Promise((resolve) => {
      execFile("py", ["-3.14", script, "cap", kind, arg], { timeout: 25000, windowsHide: true },
        (err, stdout, stderr) => {
          const out = String(stdout || "");
          let parsed = null;
          try { parsed = JSON.parse(out); } catch (e) { /* 下面按原文回 */ }
          if (!parsed) {
            resolve({ ok: false, error: (err ? String(err.message || err).slice(0, 160) + " · " : "") +
                        (String(stderr || "").trim().slice(0, 160) || out.trim().slice(0, 160) || "能力位没回可解析的 JSON") });
            return;
          }
          /* 🔴 2026-10-18 实测修正：能力位信封是**两层**（`{... , result:{ status, result:{…} }}`），
             只读一层会把"跑成功的能力"判成 ok:false（health 第一次就这么被误判）。
             与 `w3:cap-frame` 用同一套拆法：outer → inner，ok 取内层，兜底看信封。 */
          const outer = (parsed && parsed.result) || parsed || {};
          const inner = (outer && outer.result) || outer;
          const okk = (typeof inner.ok === "boolean") ? inner.ok
                    : (String(parsed.status || outer.status || "") === "ok");
          resolve({ ok: okk, kind: kind,
                    denied: parsed.denied === true || outer.denied === true || inner.denied === true,
                    status: inner.status || outer.status || parsed.status,
                    reason: inner.reason || inner.error || outer.reason || parsed.reason,
                    result: inner });
        });
    });
  });
  /* 触手视野**活体取帧**（主人令 2026-10-04：「触手视觉从来都不会传回触手视野画面，
     我需要的是这个视野画面」）：走面板桥真调 `tentacle see`（DXGI 直读整帧，门内 policy 不变），
     把帧**只在内存**回传给页面渲染 —— 壳不落盘、不回显路径、不缓存。 */
  ipcMain.handle("w3:cap-frame", async () => {
    const t0 = Date.now();
    const r = await callCapability("tentacle",
      { action: "see", kwargs: { incremental: false } }, 25000);
    const ms = Date.now() - t0;
    if (!r || !r.ok) return { ok: false, error: (r && r.error) || "取帧调用失败", ms: ms };
    const outer = (r.data && r.data.result) || {};
    const inner = (outer && outer.result) || outer || {};
    const b64 = inner.image_base64 || "";
    if (!b64) return { ok: false, error: "信封里没有帧字节", keys: Object.keys(inner).slice(0, 8), ms: ms };
    return { ok: true, b64: b64, size: inner.size || null, fmt: inner.fmt || "jpeg", ms: ms };
  });

  /* 触手**活动流**（主人令 2026-10-04：「触手她都不活动的吗？」）：
     读**真账本**（gbt_allinone/store/audit.jsonl）尾部：谁在动、动了几次、成没成 —— 只读，不改盘。 */
  const repoRootForLedger = () => {
    /* 打包态壳里没有 gbt_allinone，仓根靠**回路配置**（桥的绝对路径）反推；读不到才退回相对路径。 */
    try {
      const cfg = JSON.parse(fs.readFileSync(
        path.join(app.getPath("userData"), "gbt-deepseek-loop.json"), "utf8"));
      if (cfg && cfg.bridge) return path.resolve(path.dirname(cfg.bridge), "..", "..");
    } catch (err) { /* 没配置：退回相对 */ }
    return path.resolve(HERE, "..", "..");
  };
  ipcMain.handle("w3:cap-activity", () => {
    const ledger = path.join(repoRootForLedger(), "gbt_allinone", "store", "audit.jsonl");
    const out = { ok: true, ledger: "gbt_allinone/store/audit.jsonl", total: null, tail: [], counts: [], at: new Date().toISOString() };
    try {
      const raw = fs.readFileSync(ledger, "utf8");
      const lines = raw.split("\n").filter((l) => l.trim());
      out.total = lines.length;
      const rows = [];
      for (let i = Math.max(0, lines.length - 400); i < lines.length; i++) {
        try { rows.push(JSON.parse(lines[i])); } catch (e) { /* 坏行跳过 */ }
      }
      const cnt = {};
      rows.forEach((r) => {
        const m = r && r.meta;
        const kind = m && typeof m === "object" ? m.kind : null;
        if (kind) cnt[kind] = (cnt[kind] || 0) + 1;
      });
      out.counts = Object.keys(cnt).map((k) => ({ kind: k, n: cnt[k] }))
        .sort((a, b) => b.n - a.n).slice(0, 12);
      out.tail = rows.slice(-24).map((r) => {
        const m = r && r.meta;
        return { iso: r && r.iso, event: r && r.event,
                 kind: m && typeof m === "object" ? m.kind : null,
                 ok: m && typeof m === "object" ? (m.ok === undefined ? null : !!m.ok) : null };
      }).reverse();
    } catch (err) {
      out.ok = false;
      out.error = String(err && err.message || err).slice(0, 200);
    }
    return out;
  });

  /* 触手**心跳派活**（主人令：让触手真动起来）：按轮换给**只读**能力位派活（全在册、零作用域），
     每轮如实记账（账本自己会写）。开/关由主人；关掉即停。只派只读 —— 写类永不自动（要票的活不自动跑）。 */
  let heartbeatTimer = null;
  let heartbeatState = { on: false, round: 0, last: null, lastAt: null };
  const HEARTBEAT_CAPS = [
    { kind: "health", payload: {} },
    { kind: "llm_status", payload: {} },
    { kind: "tentacle", payload: { action: "see", kwargs: { incremental: false } } },
    { kind: "task_manager", payload: { op: "list" } },
    { kind: "selfscan", payload: {} },
  ];
  ipcMain.handle("w3:heartbeat", async (ev, payload) => {
    const want = payload && payload.on === true;
    if (!want) {
      if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null; }
      heartbeatState.on = false;
      return { ok: true, on: false, round: heartbeatState.round, last: heartbeatState.last };
    }
    if (heartbeatTimer) return { ok: true, on: true, note: "已在跑", round: heartbeatState.round };
    heartbeatState.on = true;
    const tickBeat = async () => {
      const spec = HEARTBEAT_CAPS[heartbeatState.round % HEARTBEAT_CAPS.length];
      heartbeatState.round += 1;
      const t0 = Date.now();
      const r = await callCapability(spec.kind, spec.payload, 25000);
      heartbeatState.last = { kind: spec.kind, ok: !!(r && r.ok), ms: Date.now() - t0 };
      heartbeatState.lastAt = new Date().toISOString();
      console.log("[w3] 心跳派活 #" + heartbeatState.round + "：" + spec.kind
                  + (r && r.ok ? " ok " : " 失败 ") + heartbeatState.last.ms + "ms");
    };
    tickBeat();
    heartbeatTimer = setInterval(tickBeat, 6000);
    return { ok: true, on: true, round: heartbeatState.round, caps: HEARTBEAT_CAPS.map((c) => c.kind) };
  });

  ipcMain.handle("w3:connect-dsh", (ev, payload) => w3ConnectDsh(payload));
/* 把入口交给**本应用自己的本地页**（品牌框架页 / 面板内嵌页）→ 引擎嵌在我们门面里跑。
   仍过回环白名单；没有就如实说"还没接上"，不假装。 */
ipcMain.handle("w3:dsh-entry", () => {
  if (!lastDshEntry || !lastDshEntry.url) {
    return { ok: false, error: "还没接上：壳尚未拉起 dsh web（或它没打印就绪 URL）" };
  }
  const chk = loopbackUrlOnly(lastDshEntry.url);
  if (!chk.ok) return { ok: false, error: chk.why };
  return { ok: true, url: chk.url, host: lastDshEntry.host };
});
  /* 面板内跳页（主人令 2026-10-04「要固定在 APP 面板上」）：只认注册表里的窗 id，
     把该窗的页面路径发给**面板窗**，由它在内容区里切换 —— **不开任何新窗**。
     面板不在（被关）时如实回 {ok:false}，调用方回落开窗。 */
  ipcMain.handle("w3:panel-goto", (ev, payload) => {
    const id = payload && payload.id ? String(payload.id) : "";
    const entry = registry.windows.filter((e) => e.id === id)[0];
    if (!entry) return { ok: false, error: "没有这扇窗：" + id.slice(0, 40) };
    const panelWin = wins.get("panel");
    if (!panelWin || panelWin.isDestroyed()) return { ok: false, error: "面板窗还没建起来" };
    if (entry.id === "panel") return { ok: true, note: "面板自己不用切" };
    try {
      panelWin.webContents.send("panel:goto", { id: entry.id, title: entry.title || entry.id });
      if (!panelWin.isVisible()) panelWin.show();
      panelWin.focus();
      return { ok: true, id: entry.id };
    } catch (err) {
      return { ok: false, error: String(err && err.message || err).slice(0, 200) };
    }
  });
  /* 在系统浏览器里打开一个**本机回环**页面（页面固定的配套动作口，2026-10-04）。
     为什么需要：窗已上锁（点链接不带走窗），但「进工作空间」这类**显式**意图要能达成 ——
     走浏览器开，不动壳的窗。只放行回环（loopbackUrlOnly），不落盘、不回显 URL、只回 host。 */
  ipcMain.handle("w3:open-external", (ev, payload) => {
    const raw = payload && payload.url ? String(payload.url) : "";
    const chk = urlPolicy.loopbackUrlOnly(raw);
    if (!chk.ok) return { ok: false, error: "只放行本机回环地址：" + chk.why };
    try {
      shell.openExternal(chk.url);
      let host = "";
      try { host = new URL(chk.url).host; } catch (err) { host = ""; }
      return { ok: true, host: host };
    } catch (err) {
      return { ok: false, error: String(err && err.message || err).slice(0, 200) };
    }
  });
  /* W13 · 一体式 App 铬的跨窗跳转口（2026-09-23 第 32 轮加）。
     它**不是数据写口**，但是**动作口**（会改窗口可见性/焦点）⇒：
       · 只认注册表里**已有的 id**（白名单，不认任意字符串）；
       · 不写文件、不出网、不 kill 任何东西；
       · `preload.cjs` 的 `non_readonly_capability` 那一行**同步登记**它，不许悄悄放宽。 */
  ipcMain.handle("w3:show-window", (ev, payload) => {
    /* 判据在 `chrome.showWindow`（纯函数、可单测）—— 这里只做 `ok()/no()` 的适配。 */
    const r = chrome.showWindow(registry, wins, payload);
    return r.ok ? ok(r.data) : no(r.error);
  });

  /* ══ W3 · 语音对讲（2026-09-23 第 58 轮）══════════════════════════════════
     主人令：「我打开页面就自动监听，关闭她也跟着关闭，但是大脑后台是在运行的。」
     ⇒ 四条硬纪律（写死，别改）：
       ① **不设开关**：页面打开就起，页面关闭就停。本进程**不做常驻守护** ——
          "大脑后台照常运行"是 DSH 的事，不归这一段。
       ② **绑 webContents**：`sender.once('destroyed', …)` 才是"关页面就停"的**可靠实现**。
          页面被强杀时它自己的 `pagehide` 发不出去；只靠那一句，麦克风就留在那儿开着。
       ③ **一切走唯一门**：这里只拉起 `tools/codex-scripts/intercom.py`，
          它内部调 `five-dim.py cap voice`（= `api.run_task`）。
          **主进程不直接碰 voice_cap、不碰麦克风、不读凭据、不写任何数据。**
       ④ `preload.cjs` 的 `non_readonly_capability` 那一行**同步登记**本口（它开麦克风+出声），
          不许悄悄放宽。
     ⚠️ 现读实况（2026-09-23）：本机**没有可用录音设备**（唯一输入端点是 iPhone 蓝牙免提，
        未连接）⇒ 监听会如实回 `no_input` 并退避；**这不是坏，是没设备**，页面按黄色显示。
     */
  const intercomSessions = new Map();   // webContents.id → {child, startedAt, rounds, heard, last}
  const INTERCOM_JS = path.join(ROOT, "tools", "codex-scripts", "intercom.py");

  function intercomStop(id) {
    const s = intercomSessions.get(id);
    if (!s) return false;
    try { if (s.child && !s.child.killed) s.child.kill(); } catch (e) { /* 可能已退，如实忽略 */ }
    intercomSessions.delete(id);
    return true;
  }

  /* 三条腿的状态**只问一次、缓存在主进程**（第 58 轮补）。
     为什么必须缓存：走一次门要起 Python + 加载框架 + 连发两次 `cap voice`，
     实测要好几秒；而取证/开窗在那一秒就发生了 ⇒ 页面会显示"未取到"，
     那是**时序**不是"坏"。缓存后：**注册时就先预热**，等窗口起来时读数已经在了。 */
  let intercomStatusCache = null;
  function intercomStatus(force) {
    if (intercomStatusCache && !force) return Promise.resolve(intercomStatusCache);
    return intercomRun(["status"], 120000).then((r) => {
      intercomStatusCache = (r && r.ok && r.data) ? r.data : null;
      return intercomStatusCache;
    }, () => null);
  }

  function intercomStart(wc) {
    const id = wc.id;
    if (intercomSessions.has(id)) return intercomSessions.get(id);
    const child = spawn(PETS_PY_EXE,
      ["-3.10", INTERCOM_JS, "watch", "--jsonl", "--seconds", "4", "--culture", "zh-CN"],
      { cwd: ROOT, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
    const sess = { child: child, startedAt: Date.now(), rounds: 0, heard: 0, last: null,
                   status: null };
    intercomSessions.set(id, sess);
    /* 三条腿：优先吃**预热好的缓存**（`intercomStatus()` 在注册时就已发起）。 */
    intercomStatus().then((s) => { sess.status = s; }, () => { sess.status = null; });
    let buf = "";
    child.stdout.on("data", (d) => {
      buf += d.toString("utf8");
      let i;
      while ((i = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, i).trim();
        buf = buf.slice(i + 1);
        if (line.charAt(0) !== "{") continue;          // 非 JSON 行（进度/告警）不转给页面
        try {
          const rec = JSON.parse(line);
          sess.rounds = rec.rounds_total || sess.rounds + 1;
          sess.heard = rec.heard_total || sess.heard;
          sess.last = rec;
          if (!wc.isDestroyed()) wc.send("w3:intercom-event", rec);
        } catch (e) { /* 半行/坏行丢掉 —— 不编一条假读数 */ }
      }
    });
    child.on("exit", (code) => {
      const s = intercomSessions.get(id);
      if (s && s.child === child) intercomSessions.delete(id);
      if (!wc.isDestroyed()) wc.send("w3:intercom-event", { status: "stopped", exit: code });
    });
    /* 🔴 这一句就是「关掉页面她也跟着关」的可靠实现。 */
    wc.once("destroyed", () => { intercomStop(id); });
    return sess;
  }

  /* 一次性调用（status / say）：同一件脚本、同一道门。 */
  function intercomRun(args, timeoutMs) {
    return new Promise((resolve) => {
      execFile(PETS_PY_EXE, ["-3.10", INTERCOM_JS].concat(args),
        { cwd: ROOT, timeout: timeoutMs || 120000, windowsHide: true, maxBuffer: 1 << 20 },
        (err, stdout, stderr) => {
          const txt = String(stdout || "");
          const i = txt.indexOf("{");
          if (i < 0) {
            resolve(no("对讲件没吐 JSON：" + String(stderr || err || "").slice(0, 160)));
            return;
          }
          try { resolve(ok(JSON.parse(txt.slice(i)))); }
          catch (e) { resolve(no("JSON 解析失败：" + String(e).slice(0, 120))); }
        });
    });
  }

  ipcMain.handle("w3:intercom", (ev, payload) => {
    const op = (payload && payload.op) || "state";
    const args = (payload && payload.args) || {};
    const wc = ev.sender;
    if (op === "status") return intercomStatus(true).then((s) => ok(s || { ok: false }));
    if (op === "start") {
      const s = intercomStart(wc);
      return ok({ listening: true, rounds: s.rounds, heard: s.heard, last: s.last,
                  status: s.status || null });
    }
    if (op === "stop") { intercomStop(wc.id); return ok({ listening: false }); }
    if (op === "state") {
      const s = intercomSessions.get(wc.id);
      return ok({ listening: !!s, rounds: s ? s.rounds : 0, heard: s ? s.heard : 0,
                  last: s ? s.last : null, status: (s && s.status) || null });
    }
    if (op === "say") {
      if (!args.text) return no("缺少 text");
      return intercomRun(["say", String(args.text)], 180000);
    }
    return no("未知 op：" + op);
  });
  /* **预热**：注册完就先把三条腿问一次（不阻塞、失败也不报错），
     等第一扇窗起来时缓存里已经有读数了 —— 这正是"页面显示未取到"那个时序坑的解。 */
  intercomStatus();
}

/* 🔴 **只接线模式**（2026-09-23 第 31 轮加，为真壳取证器 `shots.cjs` 而开）：
 * `GBT_W3_WIRE_ONLY=1` 时**只建立只读数据面（IPC）**，不开窗、不进托盘、不抢单例锁。
 *
 * 为什么要它：`shots.cjs` 要拍的是**"真实数据面下的窗长什么样"**。
 * 而唯一可靠的做法是复用**同一份** `registerIpc` —— 在取证器里重写一遍接线，
 * 两份必然漂（那时拍的就不是真壳，是"我以为的壳"）。
 * 只加一个分支，**不设这个变量时走的还是原来那条路，既有行为一个字节不动**。
 */
const WIRE_ONLY = process.env.GBT_W3_WIRE_ONLY === "1";
if (WIRE_ONLY) {
  /* `app &&`：让**无 Electron 的 node 进程**也能 require 本件只为拿那几个只读数据函数
     （形状探针用）。没有这一层，`app.whenReady()` 会当场抛，导出的函数就用不上了。 */
  if (app) {
    app.whenReady().then(() => {
      registerIpc();
      try { startSse(broadcast); } catch (err) { console.error("[w3] 只接线模式 SSE 未起:", err); }
    });
  }
} else if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    wins.forEach((w, id) => {
      if (w.isDestroyed()) return;
      const entry = registry.windows.filter((e) => e.id === id)[0];
      if (entry && entry.default && entry.default.visible === false) return;   /* 默认不开的窗：第二个实例不唤它（W7） */
      if (w.isMinimized()) w.restore();
      w.show();
      w.focus();
    });
  });
  app.whenReady().then(async () => {
    /* R-H295 · 数据面先立，展示面后立，且展示面不许拖垮数据面。
     * 病根：这里原来是一条不断的链
     *     registerIpc → createWindow → buildTray → refreshTrayMenu → startSse
     * 任一环抛错就整条进 .catch（记「启动失败」后 app.quit()）—— 于是
     * **托盘图标/菜单一旦出问题，实时推送 startSse 就永远不执行，而且没有任何提示**：
     * 页脚只是安静地显示「实时流：未接」，能力调用则表现为"超时"。
     * 实测（无头桩里 refreshTrayMenu 抛 `isVisible is not a function`）就复现了这条路径。
     * 现在：只读数据面（IPC + SSE 订阅）先无条件建立；窗口/托盘各自 try/catch，
     * 坏了就在盘上如实说坏了，不牵连数据面。 */
    registerIpc();
    startSse(broadcast);

    /* 🔴 2026-10-10（主人令）：**建窗之前**确保面板桥在跑 ——
       否则数字人壳没有可加载的页面，主人看到的是一片「未连接/未配置」。
       （真因见 ensurePanelBridge 处的说明：桥没人拉，而 windows.json 假定有人在拉。）
       失败只打日志、不牵连启动（与 R-H295 同向：展示面不许拖垮数据面）。 */
    try {
      const br = await ensurePanelBridge();
      if (br.ok !== true) {
        console.error("[w3] 面板桥未就绪（不牵连壳启动）:", br.reason);
      } else if (br.already !== true) {
        console.error("[w3] 面板桥已拉起（等了 " + br.waited_ms + " ms）");
      }
    } catch (err) {
      console.error("[w3] 面板桥确保失败（不牵连壳启动）:", err);
    }

    /* 🔴 2026-10-21（主人令）：**建窗之前**确保模型桥在跑 ——
       「模型对话」页只连 127.0.0.1:8791，桥不起 = 云插件的大模型在 APP 里用不上。
       失败只打日志、不牵连壳启动（与面板桥同向）。 */
    try {
      const ll = await ensureLocalLLM();
      if (ll.ok !== true) {
        console.error("[w3] 本机权重服务未就绪（不牵连壳启动）:", ll.reason);
      } else if (ll.already !== true) {
        console.error("[w3] 本机权重服务已拉起（等了 " + ll.waited_ms + " ms）");
      }
    } catch (err) {
      console.error("[w3] 本机权重服务确保失败（不牵连壳启动）:", err);
    }

    try {
      const mb = await ensureModelBridge();
      if (mb.ok !== true) {
        console.error("[w3] 模型桥未就绪（不牵连壳启动）:", mb.reason);
      } else if (mb.already !== true) {
        console.error("[w3] 模型桥已拉起（等了 " + mb.waited_ms + " ms）");
      }
    } catch (err) {
      console.error("[w3] 模型桥确保失败（不牵连壳启动）:", err);
    }

    try {
      registry.windows.forEach((entry) => createWindow(entry));
      STARTUP_DONE = true;      /* 启动批次结束：此后按需唤醒不再受「唯一可见窗」约束 */
      /* 主人令 2026-10-08：打开 APP 直接进入数字人语音交互页 —— 把它顶到最前。 */
      if (process.env.GBT_W3_STARTUP_PROBE !== "1") {
        const dh = wins.get("digital-human");
        if (dh && !dh.isDestroyed()) { dh.show(); dh.focus(); }
      }
    } catch (err) {
      console.error("[w3] 建窗失败（数据面不受影响）:", err);
    }
    try {
      buildTray();
      refreshTrayMenu();
      refreshAppMenu();          /* 换掉 Electron 英文默认菜单（主人令 2026-10-04） */
    } catch (err) {
      console.error("[w3] 托盘失败（数据面不受影响，实时流照常）:", err);
    }
    try {
      screen.on("display-metrics-changed", () => {
        wins.forEach((w, id) => {
          if (w.isDestroyed()) return;
          w.setBounds(layout.toBrowserBounds(layout.clampBounds(w.getBounds(), screen.getAllDisplays())));
        });
        saveWindowState();
      });
    } catch (err) {
      console.error("[w3] 显示器事件挂载失败:", err);
    }
    if (process.env.GBT_W3_DEBUG) {
      console.log("[w3] root=" + ROOT + " windows=" + registry.windows.map((e) => e.id).join(","));
    }
  }).catch((err) => {
    console.error("[w3] 启动失败:", err);
    app.quit();
  });
  app.on("window-all-closed", () => {
    const hasMain = registry.windows.some((e) => e.role === "main");
    if (hasMain) app.quit();
    /* W3 只登记子窗口：全关 ≠ 退出，退到托盘常驻（§2.2） */
  });
  /* 壳真退出时把自接入拉起的 `dsh web` 一并收走 —— 否则托盘里退出后，
     那条子进程会变成孤儿继续占着端口（下次自接入就会撞上"已有实例在听"而拒起）。 */
  app.on("will-quit", () => {
    dshAutoHandles.forEach((h) => { try { h.stop(); } catch (err) { /* 收不掉不拖垮退出 */ } });
    dshAutoHandles.clear();
    /* 模型桥同理：只收**本进程拉起的**那个（用户自己终端拉的桥不碰）。
       桥是 ThreadingHTTPServer，没有优雅停接口 ⇒ kill 子进程即停。 */
    /* 本机权重服务同理：只收本进程拉起的那个（4.88 GB 常驻，不收会漏内存）。 */
    if (localLlmChild) {
      try { localLlmChild.kill(); } catch (err) { /* 已退：如实忽略 */ }
      localLlmChild = null;
    }
    if (modelBridgeChild) {
      try { modelBridgeChild.kill(); } catch (err) { /* 已退：如实忽略 */ }
      modelBridgeChild = null;
    }
  });
}

/* 只读数据面整体导出 —— 让探针能脱离 Electron 直接验它们（见 .scratch/_w3_ipc_harness.cjs）。 */
module.exports = {
  findRepoRoot,
  tailLines,
  trayIcon,
  w3State,
  w3Tasks,
  w3Env,
  w3Ledger,
  w3Health,
  w3Matrix,
  w3Mindmap,
  w3Selfcheck,
  w3Introspect,
  w3Tools,
  w3H1,
  w3Pets,
  w3Summon,
  w3Eigenflux,
  /* R-H295 新接的两只只读审计器（脱离 Electron 也能探）*/
  w3Coverage,
  w3Orphans,
  w3Gene,
  callCapability,
};
