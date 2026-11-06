/* GBT小土豆V8 · 认知界面服务自启（Electron 原生壳内调用）
 *
 * 主人 2026-11-01 令：「服务重启后要跑 python tools/console-server.py --port 8766，
 * 这个直接做到原生 APP 里面自动执行就好了。」
 *
 * 职责：壳启动时（建窗之前）确保 127.0.0.1:8766 的认知界面服务在跑。
 *   · 已在跑且**就是本仓**   -> { ok:true, already:true, root_match:true }
 *   · 没在跑                 -> 用仓库自带 pyembed 解释器 detached 起一个，再等端口接管
 *   · 被别的仓/别的程序占着  -> { ok:false, status:"root_mismatch" / "port_foreign" }，不接管
 *   · 起不来                 -> { ok:false, status, reason }，调用方只打日志、不牵连壳启动
 * 幂等：重复调用不会起第二个进程（先探端口）。
 *
 * 2026-11-05 修的两个既有缺陷（都实测触发过）：
 *   ① ping 单发只等 900ms。/api/state 要读 state 文件，忙时必超时 -> 壳误判「没在跑」
 *      -> 再 spawn 一个 -> 端口被占 -> 报「起不来」，其实服务好好的。
 *      现在：单发 2000ms x 重试 2 次，且**只有超时才重试**（ECONNREFUSED 立刻有答案，重试没意义）。
 *   ② ping 只看端口答不答，不辨来源根 -> 壳会静默沿用别的仓（例如 D: 成品目录）里的旧服务。
 *      现在：/api/state 回 root + pid，与本仓比对；不一致**明说**，不静默劫持。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";

const fs = require("fs");
const path = require("path");
const http = require("http");
const net = require("net");
const { spawn } = require("child_process");

const PORT = Number(process.env.GBT_CONSOLE_PORT || 8766);
const HOST = "127.0.0.1";
const PING_TIMEOUT_MS = 2000;
const PING_RETRIES = 2;
const RETRY_GAP_MS = 200;
const TCP_PROBE_MS = 800;

function defaultSleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function findRoot() {
  let dir = __dirname;
  for (let i = 0; i < 8; i += 1) {
    if (fs.existsSync(path.join(dir, "gbt_allinone"))) return dir;
    const up = path.dirname(dir);
    if (up === dir) break;
    dir = up;
  }
  return null;
}

/* 路径归一：解析符号链接、去尾分隔符、Windows 上大小写不敏感。
 * 目的只有一个 —— 「D:\A\payload」与「d:/a/payload/」必须判成同一个根。 */
function normalizeRoot(p) {
  if (!p || typeof p !== "string") return null;
  let s = p;
  try { s = fs.realpathSync(s); } catch (err) { /* 目录不在盘上也照样比字面量 */ }
  s = path.resolve(s).replace(/[\\/]+$/, "");
  return process.platform === "win32" ? s.toLowerCase() : s;
}

/* 三态：true=同根 / false=不同根 / null=有一边没报（判不了） */
function sameRoot(a, b) {
  const na = normalizeRoot(a);
  const nb = normalizeRoot(b);
  if (na === null || nb === null) return null;
  return na === nb;
}

/* /api/state 的识别口径：ok===true 且 caps 是数字。
 * 只做 JSON.parse 是不够的 —— 随便哪个服务回个 JSON 都会被当成认知界面。 */
function looksLikeConsole(d) {
  return !!d && d.ok === true && typeof d.caps === "number";
}

/* 单发探测。不重试 —— 重试策略在 pingWithRetry 里，这样调用方看得见「试了几次」。 */
function ping(timeoutMs, target) {
  const port = Number((target && target.port) || PORT);
  const host = (target && target.host) || HOST;
  const ms = Number(timeoutMs) > 0 ? Number(timeoutMs) : PING_TIMEOUT_MS;
  return new Promise((resolve) => {
    let done = false;
    const finish = (v) => {
      if (done) return;
      done = true;
      resolve(Object.assign({ port }, v));
    };
    const req = http.get({ host, port, path: "/api/state", timeout: ms }, (res) => {
      let body = "";
      res.setEncoding("utf8");
      res.on("data", (c) => { body += c; });
      res.on("end", () => {
        let d = null;
        try { d = JSON.parse(body); } catch (err) { d = null; }
        if (!looksLikeConsole(d)) {
          return finish({ ok: false, reason: "端口有响应但不是认知界面服务",
                          http_status: res.statusCode });
        }
        finish({
          ok: true,
          caps: d.caps,
          skills: d.skills,
          root: typeof d.root === "string" ? d.root : null,
          pid: Number.isInteger(d.pid) ? d.pid : null,
        });
      });
      res.on("error", (err) => finish({ ok: false, reason: String((err && err.code) || err) }));
    });
    req.on("timeout", () => { req.destroy(); finish({ ok: false, reason: "timeout" }); });
    req.on("error", (err) => finish({ ok: false, reason: String((err && err.code) || err) }));
  });
}

/* 一次超时不等于不在：忙时 /api/state 会慢。但「端口明确拒连」和「答的不是认知界面」
 * 都是**确定的答案**，重试只是白等 —— 所以只对 timeout 重试。 */
async function pingWithRetry(pingImpl, timeoutMs, retries, sleep) {
  const wait = sleep || defaultSleep;
  const n = Number.isInteger(retries) && retries > 0 ? retries : 0;
  let last = null;
  let attempts = 0;
  for (let i = 0; i <= n; i += 1) {
    attempts = i + 1;
    last = await pingImpl(timeoutMs);
    if (last && last.ok) break;
    if (!last || last.reason !== "timeout") break;
    if (i < n) await wait(RETRY_GAP_MS);
  }
  return Object.assign({}, last || { ok: false, reason: "timeout" }, { attempts: attempts });
}

/* TCP 层探活：区分「没人听」与「有人在听但不回 HTTP」。
 * 后者绝不能 spawn —— 起了也只会 EADDRINUSE 立刻退，然后报一句含糊的「起不来」。 */
function tcpProbe(port, host, timeoutMs) {
  const ms = Number(timeoutMs) > 0 ? Number(timeoutMs) : TCP_PROBE_MS;
  return new Promise((resolve) => {
    let done = false;
    const sock = net.connect({ host: host || HOST, port: Number(port) });
    const finish = (v) => {
      if (done) return;
      done = true;
      try { sock.destroy(); } catch (err) { /* 已经关了 */ }
      resolve(v);
    };
    sock.setTimeout(ms);
    sock.once("connect", () => finish(true));
    sock.once("timeout", () => finish(false));
    sock.once("error", () => finish(false));
  });
}

function pythonPlan(root, port) {
  const embedded = path.join(root, "pyembed", "python.exe");
  const script = path.join(root, "tools", "console-server.py");
  const tail = ["-X", "utf8", script, "--port", String(port)];
  if (fs.existsSync(embedded)) {
    return { exe: embedded, argv: tail, via: "pyembed" };
  }
  return { exe: "py", argv: ["-3.14"].concat(tail), via: "py -3.14（仓内没有 pyembed）" };
}

function describeExit(info) {
  if (!info) return "未捕获退出原因";
  if (info.error) return info.error;
  const bits = [];
  if (info.code !== null && info.code !== undefined) bits.push("code=" + info.code);
  if (info.signal) bits.push("signal=" + info.signal);
  return bits.length ? bits.join(" ") : "未捕获退出原因";
}

/* 端口上已经有人答话：是不是本仓？ */
function judgeRunning(p, root, port) {
  const match = sameRoot(p.root, root);
  const base = {
    port: port, already: true, caps: p.caps, skills: p.skills,
    root: p.root, expected_root: root, server_pid: p.pid,
    root_match: match, attempts: p.attempts,
  };
  if (match === true) {
    return Object.assign({ ok: true, status: "running", pid: p.pid }, base);
  }
  if (match === false) {
    return Object.assign({
      ok: false, status: "root_mismatch",
      reason: ":" + port + " 上跑的是**另一个仓**的认知界面服务：" + p.root
        + "；本壳要的是 " + root
        + "。不自动接管（要合就关掉那边，或用 GBT_CONSOLE_PORT 换端口）",
    }, base);
  }
  return Object.assign({
    ok: false, status: "root_unknown",
    reason: ":" + port + " 上有认知界面服务在跑，但它不报 root（旧版 console-server），"
      + "无法确认它读的是不是本仓：" + root
      + "。不自动接管（同上：关掉那边或用 GBT_CONSOLE_PORT 换端口）",
  }, base);
}

/* 刚起的子进程答话了：用 pid 认领，pid 缺失才退回按 root 判。 */
function judgeStarted(p, child, root, port, waitedMs) {
  const minePid = child && Number.isInteger(child.pid) ? child.pid : null;
  const byPid = (minePid !== null && p.pid !== null) ? (p.pid === minePid) : null;
  const byRoot = sameRoot(p.root, root);
  const base = {
    port: port, pid: minePid, server_pid: p.pid, waited_ms: waitedMs,
    caps: p.caps, skills: p.skills, root: p.root, expected_root: root,
    root_match: byRoot, pid_match: byPid,
  };
  if (byPid === true) {
    return Object.assign({ ok: true, already: false, status: "started" }, base);
  }
  if (byPid === false) {
    return Object.assign({
      ok: false, status: "port_foreign",
      reason: "我起的子进程是 pid=" + minePid + "，但 :" + port + " 应答的是 pid=" + p.pid
        + "（别人先占了），不是它",
    }, base);
  }
  if (byRoot === true) {
    return Object.assign({ ok: true, already: false, status: "started" }, base);
  }
  if (byRoot === false) {
    return Object.assign({
      ok: false, status: "root_mismatch",
      reason: "我起的子进程是 " + root + "，但 :" + port + " 应答的是 " + p.root,
    }, base);
  }
  return Object.assign({
    ok: false, status: "port_ambiguous_owner",
    reason: ":" + port + " 应答了，但既不报 pid 也不报 root —— 无法确认它是不是我刚起的那个",
  }, base);
}

async function ensureConsoleServer(options) {
  const opt = options || {};
  const port = Number(opt.port || PORT);
  const target = { port: port, host: HOST };
  const singlePing = opt.pingImpl || ((ms) => ping(ms, target));
  const sleep = opt.sleep || defaultSleep;
  const spawnImpl = opt.spawnImpl || spawn;
  const tcpProbeImpl = opt.tcpProbeImpl || tcpProbe;
  const pingTimeoutMs = Number(opt.pingTimeoutMs) > 0 ? Number(opt.pingTimeoutMs) : PING_TIMEOUT_MS;
  const pingRetries = opt.pingRetries === undefined ? PING_RETRIES : Number(opt.pingRetries);
  const waitStepMs = Number(opt.waitStepMs) > 0 ? Number(opt.waitStepMs) : 500;
  const waitSteps = opt.waitSteps === undefined ? 24 : Number(opt.waitSteps);

  const root = opt.root === undefined ? findRoot() : opt.root;
  if (!root) {
    return { ok: false, status: "no_root", port: port,
             reason: "找不到仓库根（上层没有 gbt_allinone）" };
  }

  const first = await pingWithRetry(singlePing, pingTimeoutMs, pingRetries, sleep);
  if (first.ok) return judgeRunning(first, root, port);

  if (first.reason === "端口有响应但不是认知界面服务") {
    return {
      ok: false, status: "port_foreign", port: port, probe: first,
      reason: ":" + port + " 已被别的程序占着（它应答了，但不是认知界面服务）",
    };
  }

  if (first.reason === "timeout") {
    const taken = await tcpProbeImpl(port, HOST, TCP_PROBE_MS);
    if (taken) {
      return {
        ok: false, status: "port_unresponsive", port: port, probe: first,
        reason: ":" + port + " 有人在听，但不回 /api/state（连试 " + first.attempts + " 次超时）。"
          + "不另起第二个 —— 起了也只会因端口被占立刻退出",
      };
    }
  }

  const plan = pythonPlan(root, port);
  const state = { exit: null };
  let child = null;
  try {
    child = spawnImpl(plan.exe, plan.argv, {
      detached: true, cwd: root, stdio: "ignore", windowsHide: true,
    });
  } catch (err) {
    return {
      ok: false, status: "spawn_failed", port: port, exe: plan.exe, via: plan.via,
      reason: "起不来：" + String((err && err.message) || err),
    };
  }
  try {
    if (child && typeof child.unref === "function") child.unref();
  } catch (err) { /* 已经退了 */ }
  if (child && typeof child.once === "function") {
    child.once("exit", (code, signal) => { state.exit = { code: code, signal: signal }; });
    child.once("error", (err) => {
      state.exit = state.exit || { error: "spawn error: " + String((err && err.message) || err) };
    });
  }

  for (let i = 0; i < waitSteps; i += 1) {
    await sleep(waitStepMs);
    const p = await singlePing(pingTimeoutMs);
    if (p && p.ok) return judgeStarted(p, child, root, port, (i + 1) * waitStepMs);
    if (state.exit) break;
  }

  if (state.exit) {
    return {
      ok: false, status: "child_exited", port: port, exe: plan.exe, via: plan.via,
      pid: child && child.pid, exit: state.exit,
      reason: "子进程起来就退了（" + describeExit(state.exit) + "）：多半是 :" + port
        + " 已被别的进程占着，或者 " + plan.via + " 起不了 console-server.py",
    };
  }
  return {
    ok: false, status: "timeout", port: port, exe: plan.exe, via: plan.via,
    pid: child && child.pid,
    reason: "进程起了但 :" + port + " 一直没接管（等了 " + (waitSteps * waitStepMs) + " ms）",
  };
}

module.exports = {
  ensureConsoleServer, ping, pingWithRetry, tcpProbe, findRoot,
  normalizeRoot, sameRoot, pythonPlan,
  PORT, HOST, PING_TIMEOUT_MS, PING_RETRIES,
};
