/* GBT小土豆V8 · 认知界面服务自启（Electron 原生壳内调用）
 *
 * 主人 2026-11-01 令：「服务重启后要跑 python tools/console-server.py --port 8766，
 * 这个直接做到原生 APP 里面自动执行就好了。」
 *
 * 职责：壳启动时（建窗之前）确保 127.0.0.1:8766 的认知界面服务在跑。
 *   · 已在跑          → 直接返回 { ok:true, already:true }
 *   · 没在跑          → 用仓库自带 pyembed 解释器 detached 起一个，再等端口接管
 *   · 起不来          → 返回 { ok:false, reason }，调用方只打日志、不牵连壳启动
 * 幂等：重复调用不会起第二个进程（先探端口）。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";

const fs = require("fs");
const path = require("path");
const http = require("http");
const { spawn } = require("child_process");

const PORT = Number(process.env.GBT_CONSOLE_PORT || 8766);
const HOST = "127.0.0.1";

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

function ping(timeoutMs) {
  return new Promise((resolve) => {
    const req = http.get({
      host: HOST, port: PORT, path: "/api/state", timeout: timeoutMs || 900,
    }, (res) => {
      let body = "";
      res.on("data", (c) => { body += c; });
      res.on("end", () => {
        try {
          const d = JSON.parse(body);
          resolve({ ok: true, caps: d.caps, skills: d.skills });
        } catch (err) {
          resolve({ ok: false, reason: "端口有响应但不是认知界面服务" });
        }
      });
    });
    req.on("timeout", () => { req.destroy(); resolve({ ok: false, reason: "timeout" }); });
    req.on("error", (err) => { resolve({ ok: false, reason: String((err && err.code) || err) }); });
  });
}

function pythonPlan(root) {
  const embedded = path.join(root, "pyembed", "python.exe");
  if (fs.existsSync(embedded)) {
    return { exe: embedded, argv: ["-X", "utf8", path.join(root, "tools", "console-server.py"),
                                  "--port", String(PORT)] };
  }
  return { exe: "py", argv: ["-3.14", "-X", "utf8", path.join(root, "tools", "console-server.py"),
                             "--port", String(PORT)] };
}

async function ensureConsoleServer(options) {
  const root = (options && options.root) || findRoot();
  if (!root) return { ok: false, reason: "找不到仓库根（上层没有 gbt_allinone）" };
  const first = await ping(900);
  if (first.ok) return { ok: true, already: true, caps: first.caps, port: PORT };

  const plan = pythonPlan(root);
  try {
    const child = spawn(plan.exe, plan.argv, {
      detached: true, cwd: root, stdio: "ignore", windowsHide: true,
    });
    child.unref();
    for (let i = 0; i < 24; i += 1) {
      await new Promise((r) => setTimeout(r, 500));
      const p = await ping(700);
      if (p.ok) return { ok: true, already: false, pid: child.pid, waited_ms: (i + 1) * 500,
                        caps: p.caps, port: PORT };
    }
    return { ok: false, reason: "进程起了但 :" + PORT + " 一直没接管（端口被占？）" };
  } catch (err) {
    return { ok: false, reason: "起不来：" + String((err && err.message) || err) };
  }
}

module.exports = { ensureConsoleServer, ping, findRoot, PORT };
