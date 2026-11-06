/* GBT小土豆V8 · 桌面壳 · 认知界面服务自启 · 契约测试
 *
 * 跑法（自动被 npm test 发现）：
 *     node --test holo_pet_w3/tests/test_console_service.cjs
 *   或 holo_pet_w3 下 npm test
 *
 * 为什么必须有：这个模块决定壳「连不连、连的是谁那份代码」。
 *   2026-11-05 实测踩过两次：
 *     ① ping 只等 900ms，/api/state 一忙就超时 -> 壳以为没在跑 -> 再起一个 -> 端口被占 -> 报「起不来」。
 *     ② ping 只看端口答不答 -> 壳静默连上 D: 成品目录里的旧服务，跑的不是本仓代码。
 *   所以判据里既要「超时要重试」，也要「不是本仓要明说」。
 *
 * 纪律：负对照占多数 —— 只测「正常那行能过」等于没测。
 * 全部用假 ping / 假 spawn，不碰真 8766/8777，也不起真 python。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");
const http = require("node:http");
const net = require("node:net");
const { EventEmitter } = require("node:events");

const C = require(path.join(__dirname, "..", "shell", "console-service.cjs"));

const ROOT = path.resolve(__dirname, "..", "..");
const OTHER_ROOT = path.resolve(__dirname, "..", "..", "..");

/* ── 小工具 ─────────────────────────────────────────────────────────── */

function scripted(values) {
  const calls = [];
  const fn = async (ms) => {
    calls.push(ms);
    const v = values.length > 1 ? values.shift() : values[0];
    return v;
  };
  fn.calls = calls;
  return fn;
}

function fakeChild(pid) {
  const child = new EventEmitter();
  child.pid = pid;
  child.unref = () => {};
  return child;
}

function spawnRecorder(child) {
  const seen = [];
  const fn = (exe, argv, opts) => {
    seen.push({ exe: exe, argv: argv, opts: opts });
    return child;
  };
  fn.seen = seen;
  return fn;
}

function okProbe(root, pid) {
  return { ok: true, caps: 427, skills: 3, root: root, pid: pid, port: 8766 };
}

function startServer(handler) {
  return new Promise((resolve) => {
    const srv = http.createServer(handler);
    srv.listen(0, "127.0.0.1", () => resolve(srv));
  });
}

function closeServer(srv) {
  return new Promise((resolve) => srv.close(resolve));
}

async function closedPort() {
  const srv = net.createServer();
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  const p = srv.address().port;
  await new Promise((r) => srv.close(r));
  return p;
}

/* ── 根路径 ─────────────────────────────────────────────────────────── */

test("findRoot：从 shell/ 往上能找到本仓（有 gbt_allinone）", () => {
  const root = C.findRoot();
  assert.ok(root, "找不到仓根 = 壳永远起不了服务");
  assert.strictEqual(root, ROOT);
});

test("sameRoot：同根（尾分隔符 / Windows 大小写）判 true", () => {
  assert.strictEqual(C.sameRoot(ROOT, ROOT + path.sep), true);
  if (process.platform === "win32") {
    assert.strictEqual(C.sameRoot(ROOT.toUpperCase(), ROOT.toLowerCase()), true,
      "Windows 上大小写不同仍是同一个目录");
  }
});

test("sameRoot：不同目录判 false（负对照——不能永远 true）", () => {
  assert.strictEqual(C.sameRoot(ROOT, OTHER_ROOT), false);
});

test("sameRoot：有一边没报 -> null（判不了，不许当成同根）", () => {
  assert.strictEqual(C.sameRoot(null, ROOT), null);
  assert.strictEqual(C.sameRoot(ROOT, undefined), null);
  assert.strictEqual(C.sameRoot("", ROOT), null);
  assert.strictEqual(C.normalizeRoot(null), null);
});

/* ── 单发探测 ───────────────────────────────────────────────────────── */

test("ping：真接到认知界面 -> 收下 caps / root / pid", async () => {
  const srv = await startServer((req, res) => {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ ok: true, caps: 427, skills: 9,
                             root: "C:/some/root", pid: 4242, engine: {}, guards: {} }));
  });
  try {
    const p = await C.ping(3000, { port: srv.address().port });
    assert.strictEqual(p.ok, true);
    assert.strictEqual(p.caps, 427);
    assert.strictEqual(p.skills, 9);
    assert.strictEqual(p.root, "C:/some/root");
    assert.strictEqual(p.pid, 4242);
  } finally { await closeServer(srv); }
});

test("ping：旧版只回 caps/skills -> 仍算认知界面，但 root/pid 是 null", async () => {
  const srv = await startServer((req, res) => {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ ok: true, caps: 427, skills: 9 }));
  });
  try {
    const p = await C.ping(3000, { port: srv.address().port });
    assert.strictEqual(p.ok, true, "旧版服务不许被判成「不是认知界面」");
    assert.strictEqual(p.root, null);
    assert.strictEqual(p.pid, null);
  } finally { await closeServer(srv); }
});

test("ping：回 JSON 但不是认知界面 -> 拒绝（负对照）", async () => {
  const srv = await startServer((req, res) => {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ hello: "world" }));
  });
  try {
    const p = await C.ping(3000, { port: srv.address().port });
    assert.strictEqual(p.ok, false);
    assert.strictEqual(p.reason, "端口有响应但不是认知界面服务");
  } finally { await closeServer(srv); }
});

test("ping：回 HTML -> 拒绝（不许把任意网页当服务）", async () => {
  const srv = await startServer((req, res) => {
    res.writeHead(200, { "content-type": "text/html" });
    res.end("<html>hi</html>");
  });
  try {
    const p = await C.ping(3000, { port: srv.address().port });
    assert.strictEqual(p.ok, false);
  } finally { await closeServer(srv); }
});

test("ping：没人听 -> ECONNREFUSED（不是 timeout）", async () => {
  const port = await closedPort();
  const p = await C.ping(2000, { port: port });
  assert.strictEqual(p.ok, false);
  assert.notStrictEqual(p.reason, "timeout", "没人听必须是立刻拒连，不是等满超时");
});

/* ── 重试策略 ───────────────────────────────────────────────────────── */

test("重试：超时 2 次后成功 -> 仍判在跑，共试 3 次", async () => {
  const probe = scripted([{ ok: false, reason: "timeout" },
                          { ok: false, reason: "timeout" },
                          okProbe("C:/x", 1)]);
  const r = await C.pingWithRetry(probe, 2000, 2, async () => {});
  assert.strictEqual(r.ok, true);
  assert.strictEqual(r.attempts, 3, "一次超时不等于不在，必须重试");
  assert.strictEqual(probe.calls.length, 3);
});

test("重试：端口明确拒连 -> 只试 1 次（重试没意义，负对照）", async () => {
  const probe = scripted([{ ok: false, reason: "ECONNREFUSED" }]);
  const r = await C.pingWithRetry(probe, 2000, 2, async () => {});
  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.attempts, 1);
  assert.strictEqual(probe.calls.length, 1, "拒连是确定答案，再试只是白等启动时间");
});

test("重试：pingRetries=0 -> 超时也只试 1 次（证明重试确实由参数控制）", async () => {
  const probe = scripted([{ ok: false, reason: "timeout" }]);
  const r = await C.pingWithRetry(probe, 2000, 0, async () => {});
  assert.strictEqual(r.attempts, 1);
  assert.strictEqual(probe.calls.length, 1);
});

/* ── 已在跑：辨来源根 ───────────────────────────────────────────────── */

test("已在跑且同根 -> ok / already / root_match=true，且不起新进程", async () => {
  const spawn = spawnRecorder(fakeChild(111));
  const r = await C.ensureConsoleServer({
    root: ROOT, pingImpl: scripted([okProbe(ROOT, 999)]),
    spawnImpl: spawn, sleep: async () => {},
  });
  assert.strictEqual(r.ok, true);
  assert.strictEqual(r.already, true);
  assert.strictEqual(r.root_match, true);
  assert.strictEqual(r.server_pid, 999);
  assert.strictEqual(spawn.seen.length, 0, "已经同根在跑，绝不许再起一个");
});

test("已在跑但属于另一个仓 -> root_mismatch，且不起新进程、不静默接管", async () => {
  const spawn = spawnRecorder(fakeChild(111));
  const r = await C.ensureConsoleServer({
    root: ROOT, pingImpl: scripted([okProbe(OTHER_ROOT, 888)]),
    spawnImpl: spawn, sleep: async () => {},
  });
  assert.strictEqual(r.ok, false, "连错仓还报 ok=true = 让主人以为跑的是新代码");
  assert.strictEqual(r.status, "root_mismatch");
  assert.strictEqual(r.root_match, false);
  assert.strictEqual(spawn.seen.length, 0, "不许靠再起一个进程去「抢」端口");
  assert.ok(r.reason.includes(OTHER_ROOT), "要说出对面是谁：" + r.reason);
  assert.ok(r.reason.includes(ROOT), "要说出本仓是哪个：" + r.reason);
});

test("已在跑但旧版不报 root -> root_unknown（判不了就不许当成同根）", async () => {
  const spawn = spawnRecorder(fakeChild(111));
  const r = await C.ensureConsoleServer({
    root: ROOT, pingImpl: scripted([{ ok: true, caps: 427, skills: 3, root: null, pid: null }]),
    spawnImpl: spawn, sleep: async () => {},
  });
  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.status, "root_unknown");
  assert.strictEqual(spawn.seen.length, 0);
});

/* ── 端口被别人占着 ─────────────────────────────────────────────────── */

test("端口答话但不是认知界面 -> port_foreign，不起新进程", async () => {
  const spawn = spawnRecorder(fakeChild(111));
  const r = await C.ensureConsoleServer({
    root: ROOT, pingImpl: scripted([{ ok: false, reason: "端口有响应但不是认知界面服务" }]),
    spawnImpl: spawn, sleep: async () => {},
  });
  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.status, "port_foreign");
  assert.strictEqual(spawn.seen.length, 0);
});

test("端口在听但不回 /api/state -> port_unresponsive，不硬起第二个", async () => {
  const spawn = spawnRecorder(fakeChild(111));
  const r = await C.ensureConsoleServer({
    root: ROOT, pingImpl: scripted([{ ok: false, reason: "timeout" }]),
    tcpProbeImpl: async () => true,
    spawnImpl: spawn, sleep: async () => {}, pingRetries: 1,
  });
  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.status, "port_unresponsive");
  assert.strictEqual(spawn.seen.length, 0,
    "起了也只会 EADDRINUSE 立刻退，然后报一句含糊的「起不来」");
});

/* ── 自己起：认领子进程 ─────────────────────────────────────────────── */

test("没人听 -> 起一个，端口由我的子进程接管（pid 对上）才算成功", async () => {
  const child = fakeChild(4321);
  const spawn = spawnRecorder(child);
  const r = await C.ensureConsoleServer({
    root: ROOT,
    pingImpl: scripted([{ ok: false, reason: "ECONNREFUSED" }, okProbe(ROOT, 4321)]),
    tcpProbeImpl: async () => false,
    spawnImpl: spawn, sleep: async () => {},
  });
  assert.strictEqual(r.ok, true);
  assert.strictEqual(r.already, false);
  assert.strictEqual(r.status, "started");
  assert.strictEqual(r.pid, 4321);
  assert.strictEqual(r.pid_match, true);
  assert.strictEqual(spawn.seen.length, 1);
  const argv = spawn.seen[0].argv.join(" ");
  assert.ok(argv.includes("console-server.py"), "要起的是 console-server.py：" + argv);
  assert.ok(argv.includes("--port"), "必须带 --port：" + argv);
  assert.strictEqual(spawn.seen[0].opts.detached, true, "壳退出后服务要活着");
  assert.strictEqual(spawn.seen[0].opts.stdio, "ignore");
});

test("起了子进程但端口被别人的 pid 应答 -> port_foreign（负对照）", async () => {
  const child = fakeChild(4321);
  const r = await C.ensureConsoleServer({
    root: ROOT,
    pingImpl: scripted([{ ok: false, reason: "ECONNREFUSED" }, okProbe(ROOT, 7777)]),
    tcpProbeImpl: async () => false,
    spawnImpl: spawnRecorder(child), sleep: async () => {},
  });
  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.status, "port_foreign");
  assert.strictEqual(r.pid_match, false);
  assert.ok(r.reason.includes("4321") && r.reason.includes("7777"), r.reason);
});

test("子进程一起来就退 -> child_exited，且立刻收手（不傻等满 12 秒）", async () => {
  const child = fakeChild(4321);
  let slept = 0;
  const r = await C.ensureConsoleServer({
    root: ROOT,
    pingImpl: scripted([{ ok: false, reason: "ECONNREFUSED" }]),
    tcpProbeImpl: async () => false,
    spawnImpl: spawnRecorder(child),
    sleep: async () => { slept += 1; if (slept === 1) child.emit("exit", 1, null); },
    waitSteps: 24, waitStepMs: 500,
  });
  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.status, "child_exited");
  assert.deepStrictEqual(r.exit, { code: 1, signal: null });
  assert.ok(slept <= 2, "已知子进程退了就该停，实际等了 " + slept + " 轮");
  assert.ok(r.reason.includes("code=1"), "要带上退出码：" + r.reason);
});

test("子进程活着但就是不接管 -> timeout（与 port_foreign 分开报）", async () => {
  const child = fakeChild(4321);
  const r = await C.ensureConsoleServer({
    root: ROOT,
    pingImpl: scripted([{ ok: false, reason: "ECONNREFUSED" }]),
    tcpProbeImpl: async () => false,
    spawnImpl: spawnRecorder(child), sleep: async () => {},
    waitSteps: 3, waitStepMs: 10,
  });
  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.status, "timeout");
  assert.ok(r.reason.includes("30 ms"), "3 轮 x 10ms = 30ms，要说出等了多久：" + r.reason);
});

test("找不到仓根 -> no_root，且不 spawn（负对照）", async () => {
  const spawn = spawnRecorder(fakeChild(1));
  const r = await C.ensureConsoleServer({
    root: null, pingImpl: scripted([okProbe(ROOT, 1)]),
    spawnImpl: spawn, sleep: async () => {},
  });
  assert.strictEqual(r.ok, false);
  assert.strictEqual(r.status, "no_root");
  assert.strictEqual(spawn.seen.length, 0);
});
