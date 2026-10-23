/* GBT小土豆V8 · 桌面壳 · DeepSeek Harness 自接入 · 契约测试
 *
 * 跑法（自动被 tests/run_tests.py 发现）：
 *     py -3.14 holo_pet_w3/tests/run_tests.py
 *   或 node --test holo_pet_w3/tests/test_dsh_launch.cjs
 *
 * 为什么必须有：这个模块决定"壳拿哪条 URL 去载对话面"。
 * 判错一条 = 要么接不上（缺 token 的裸 URL 必回 401），要么把 token 打进日志。
 * 纪律同 test_url_policy.cjs：**负对照占多数** —— 只测"正常那行能过"等于没测。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");
const net = require("node:net");

const D = require(path.join(__dirname, "..", "shell", "dsh-launch.cjs"));

/* ── 必须接住的：就绪行 ── */
test("接住：dsh web 就绪行（含 token）", () => {
  const url = D.parseDshUrlLine("dsh web: http://127.0.0.1:3080/?token=abc123");
  assert.ok(url, "就绪行应当解析出 URL");
  assert.match(url, /^http:\/\/127\.0\.0\.1:3080\/\?token=abc123$/);
});

test("接住：就绪行后面还跟着 (LAN: …) 的形态", () => {
  const line = "dsh web: http://127.0.0.1:3080/?token=t9 (LAN: http://192.168.1.5:3080/?token=t9)";
  const url = D.parseDshUrlLine(line);
  assert.ok(url, "一行里有多条 URL 时也要接住");
  assert.match(url, /^http:\/\/127\.0\.0\.1:3080\//, "必须取**回环**那条，不是 LAN 那条");
});

test("接住：前面有别的前缀输出（启动日志混在一行里）", () => {
  const url = D.parseDshUrlLine("[w3] ready · dsh web: http://localhost:3080/?token=x");
  assert.ok(url);
  assert.match(url, /localhost:3080/);
});

/* ── 必须拒绝的：这一组才是本件的本体 ── */
test("拒绝：没有 token 的裸 URL（载进来必回 401，不如不接）", () => {
  assert.strictEqual(D.parseDshUrlLine("dsh web: http://127.0.0.1:3080/"), null);
  assert.strictEqual(D.parseDshUrlLine("dsh web: http://127.0.0.1:3080/?token="), null);
});

test("拒绝：不是就绪行", () => {
  for (const line of ["", "  ", "dsh web: opening the default browser; pass --no-open to disable",
                      "http://127.0.0.1:3080/?token=abc", "listening on 3080"]) {
    assert.strictEqual(D.parseDshUrlLine(line), null, JSON.stringify(line) + " 不该被当成就绪行");
  }
});

test("拒绝：非法输入不抛异常（null / undefined / 数字 / 对象）", () => {
  for (const v of [null, undefined, 0, {}, [], true]) {
    assert.strictEqual(D.parseDshUrlLine(v), null);
  }
});

test("拒绝：非 http(s) 协议（file: / javascript:）", () => {
  assert.strictEqual(D.parseDshUrlLine("dsh web: file:///C:/x?token=a"), null);
  assert.strictEqual(D.parseDshUrlLine("dsh web: javascript:alert(1)?token=a"), null);
});

/* ── 凭据卫生：脱敏 ── */
test("脱敏：maskUrl 永不带 token，且保留 host", () => {
  const m = D.maskUrl("http://127.0.0.1:3080/?token=SUPERSECRET");
  assert.ok(!m.includes("SUPERSECRET"), "maskUrl 漏了 token：" + m);
  assert.match(m, /127\.0\.0\.1:3080/);
  assert.match(m, /token=\*\*\*/);
});

test("脱敏：scrub 抹掉任意文本里的 token（日志路径都过它）", () => {
  const out = D.scrub("GET /?token=SUPERSECRET&x=1 failed");
  assert.ok(!out.includes("SUPERSECRET"), "scrub 漏了：" + out);
  assert.match(out, /token=\*\*\*/);
  assert.match(out, /x=1/, "非 token 的内容不许被误伤");
});

test("脱敏：maskUrl 对非法 URL 不抛异常", () => {
  assert.strictEqual(D.maskUrl("nonsense"), "(非法 URL)");
  assert.strictEqual(D.maskUrl(null), "(非法 URL)");
});

/* ── 端口探测：正负两路都要有（只测 false = 会把"永远 false"也放绿）── */
test("探测：没人听 → false（用 OS 刚放掉的高位端口）", async () => {
  const r = await D.isPortListening(45999, "127.0.0.1", 300);
  assert.strictEqual(typeof r, "boolean");
  assert.strictEqual(r, false, "45999 上不该有人在听（真有 ⇒ 环境特殊，请换端口复跑）");
});

test("探测：自己在听 → true", async () => {
  const srv = net.createServer();
  await new Promise((res) => srv.listen(0, "127.0.0.1", res));
  const port = srv.address().port;
  try {
    assert.strictEqual(await D.isPortListening(port, "127.0.0.1", 500), true);
  } finally {
    await new Promise((res) => srv.close(res));
  }
});

/* ── startDsh：不自起第二实例 + 就绪行 → onUrl（走假实现，不真起 dsh）── */
test("startDsh：端口已在听 ⇒ 不去动它，改用 OS 分配的端口（--port 0）另起一个", async () => {
  const { EventEmitter } = require("node:events");
  const logs = [];
  const urls = [];
  let cmdLine = null;
  const fake = new EventEmitter();
  fake.stdout = new EventEmitter();
  fake.stderr = new EventEmitter();
  fake.killed = false;
  fake.kill = () => {};
  const h = D.startDsh({
    port: 3080, onUrl: (u) => urls.push(u), onLog: (m) => logs.push(m),
    probeImpl: async () => true,
    spawnImpl: (c) => { cmdLine = c; return fake; },
  });
  await new Promise((res) => setTimeout(res, 20));
  /* 🔴 2026-10-22 口径翻了（留痕）：主人贴出他自己那条命令后，壳里起的命令改成
     `npx --yes @deepseek-ai/dsh web --no-open`（与他逐字一致，cwd 钉仓根）。
     **原期望：`dsh web --no-open --port 0`；翻成：走 npx 的那条 + `--port 0`。**
     理由：裸 `dsh` 是 npm 垫片，`shell:true` 下解析依赖 Electron 进程的 PATH —— 那正是
     "上次为什么对话窗停在别处"这类事故的温床；npx 不依赖垫片。 */
  /* 🔴 2026-10-23 口径再翻（主人令 A，留痕）：版本**钉死** `@0.1.5-rc.3`。
     上一版是裸 `npx --yes @deepseek-ai/dsh`（与主人手打命令逐字一致），但 npx 会取最新版；
     2026-10-23 取到 0.2.1 后 preset 机制换代（目录式 → 注册表式），主人自建的 gbt-spine
     当场变成 `Unknown agent preset`，会话恢复不了。故命令里带上版本，断言直接用 D.DSH_PKG，
     避免模块与测试两处各写一份版本号而漂开。 */
  assert.strictEqual(cmdLine, `npx --yes ${D.DSH_PKG} web --no-open --port 0`,
    "端口被占时必须改用 0 端口另起，否则主人强关过一次后就永远接不上");
  assert.ok(logs.join("\n").includes("已经有服务在听"), "要说清撞上了什么：" + logs.join("|"));
  /* 换端口起的那一个同样要能接上 —— 就绪行的端口是任意的，解析不许写死 3080 */
  fake.stdout.emit("data", "dsh web: http://127.0.0.1:54321/?token=SECRET9\n");
  assert.deepStrictEqual(urls, ["http://127.0.0.1:54321/?token=SECRET9"]);
  assert.ok(!logs.join("|").includes("SECRET9"), "日志里漏了 token");
  h.stop();
});

test("startDsh：没人在听 ⇒ 起 dsh web --no-open，就绪行交给 onUrl，日志里没有 token", async () => {
  const { EventEmitter } = require("node:events");
  const logs = [];
  const urls = [];
  const fake = new EventEmitter();
  fake.stdout = new EventEmitter();
  fake.stderr = new EventEmitter();
  fake.killed = false;
  fake.kill = () => { fake.killed = true; };
  let cmdLine = null;
  const h = D.startDsh({
    port: 3080, onUrl: (u) => urls.push(u), onLog: (m) => logs.push(m),
    probeImpl: async () => false,
    spawnImpl: (c) => { cmdLine = c; return fake; },
  });
  await new Promise((res) => setTimeout(res, 20));
  /* 同上的口径翻转（2026-10-22）+ 钉版本（2026-10-23 主人令 A）。
     为什么"一律"带 --port 0：实测无 --port 0 时撞 3080 会 EADDRINUSE 直接崩（不是自动换端口）。 */
  assert.strictEqual(cmdLine, `npx --yes ${D.DSH_PKG} web --no-open --port 0`, "一律带 --port 0（撞 3080 会崩，实测）");
  fake.stdout.emit("data", "dsh web: http://127.0.0.1:3080/?token=SECRET7\r\n");
  assert.deepStrictEqual(urls, ["http://127.0.0.1:3080/?token=SECRET7"]);
  assert.ok(!logs.join("\n").includes("SECRET7"), "日志里漏了 token：" + logs.join("|"));
  h.stop();
  assert.strictEqual(fake.killed, true, "stop() 要真的把子进程杀掉");
});

test("startDsh：无换行的输出不许无限吃内存（缓冲有上限）", async () => {
  const { EventEmitter } = require("node:events");
  const fake = new EventEmitter();
  fake.stdout = new EventEmitter();
  fake.stderr = new EventEmitter();
  fake.killed = false;
  fake.kill = () => {};
  const h = D.startDsh({
    onUrl: () => {}, onLog: () => {}, probeImpl: async () => false,
    spawnImpl: () => fake,
  });
  await new Promise((res) => setTimeout(res, 20));
  fake.stdout.emit("data", "x".repeat(300000));   /* 无换行的一大坨 */
  fake.stdout.emit("data", "\ndsh web: http://127.0.0.1:3080/?token=after\n");
  h.stop();
  assert.ok(true, "不崩就算过：缓冲封顶后仍能继续解析下一行");
});

/* ── stop()：必须收**整棵进程树**（这条是端到端实测逼出来的真缺陷）── */
test("stop()：Windows 上必须 taskkill /T —— 只 kill 外壳会给主人留下孤儿 dsh（占端口、token 拿不回）", async () => {
  const { EventEmitter } = require("node:events");
  const calls = [];
  const fake = new EventEmitter();
  fake.stdout = new EventEmitter();
  fake.stderr = new EventEmitter();
  fake.pid = 4242;
  fake.killed = false;
  fake.kill = () => { calls.push(["child.kill"]); fake.killed = true; };
  const h = D.startDsh({
    onUrl: () => {}, onLog: () => {}, probeImpl: async () => false,
    spawnImpl: (cmd, args) => { calls.push([cmd, args]); return fake; },
  });
  await new Promise((res) => setTimeout(res, 20));
  h.stop();
  if (process.platform === "win32") {
    const tk = calls.find((c) => c[0] === "taskkill");
    assert.ok(tk, "Windows 上必须用 taskkill 收树，实得调用：" + JSON.stringify(calls));
    assert.deepStrictEqual(tk[1], ["/PID", "4242", "/T", "/F"], "/T 才是连子孙一起收");
    assert.ok(!calls.some((c) => c[0] === "child.kill"), "只 kill 外壳 = 留下 dsh 孤儿");
  } else {
    assert.ok(calls.some((c) => c[0] === "child.kill"), "非 Windows 上直接 kill");
  }
});
