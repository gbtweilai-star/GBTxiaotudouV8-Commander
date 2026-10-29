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
  assert.strictEqual(cmdLine, "npx --yes @deepseek-ai/dsh@0.2.1-rc.2 --profile gbt-official --no-open --port 0",
    "端口被占时必须改用 0 端口另起，否则主人强关过一次后就永远接不上");
  /* 🔴 换上 gbt-official 之后**不许再出现 `web` 子命令**（2026-10-26 实测）：
     `dsh --profile gbt-official web` 直接报 `too many arguments … got 1: web`，起来就退。
     `web` 只是 `--profile web` 的语法糖，换了 profile 就不能再写它。 */
  assert.ok(!/(^|\s)web(\s|$)/.test(cmdLine),
    "命令里不许再带 `web` 子命令（它等价于 --profile web，会顶掉 gbt-official）：" + cmdLine);
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
  assert.strictEqual(cmdLine, "npx --yes @deepseek-ai/dsh@0.2.1-rc.2 --profile gbt-official --no-open",
    "命令必须是这条（npx 形式 + 主人选定的 gbt-official 权限档），且带 --no-open");
  /* 权限档是主人 2026-10-26 定的：`danger-full-access` 只存在于 gbt-official，
     少了 --profile 就等于悄悄把主人的权限降成默认档。这条钉住它。 */
  assert.ok(cmdLine.includes("--profile gbt-official"),
    "必须显式 --profile gbt-official，否则主人原来的 danger-full-access 就丢了：" + cmdLine);
  /* 🔴 `--yes` 是**硬要求**，不是风格问题（2026-10-26 实测教训）：
     npx 首次见到未缓存的包会交互式问 "Ok to proceed? (y)"；
     壳的 stdin 是 ignore ⇒ 等不到 y ⇒ 进程挂住、就绪行永远不来、
     对话面永远停在「等壳把引擎拉起来」，而日志里一个字都不报。
     这条断言就是防止将来有人嫌 `--yes` 多余把它删掉。 */
  assert.ok(/^npx --yes /.test(cmdLine),
    "npx 必须带 --yes：否则首次会卡在交互确认上，谁都看不出为什么起不来");
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

/* ── 心跳：把「在装依赖」与「真卡死」分开报（2026-10-26 实测逼出来的判据）──
 *
 * 为什么必须有：`npx … --version` 实测能 60 秒**零字节**而不死 —— 它在下 tarball。
 * 壳这边若一个字不说，主人的观感就是"死了"，而实际处置完全不同：
 *   零输出   ⇒ 继续等（npx 在装依赖）
 *   有输出没就绪行 ⇒ dsh 在启动，若长期停住才该怀疑
 * 所以这两条必须**分别**报出来，且下面用 30ms 心跳把真实节奏压进单测。
 */
function makeFake() {
  const { EventEmitter } = require("node:events");
  const fake = new EventEmitter();
  fake.stdout = new EventEmitter();
  fake.stderr = new EventEmitter();
  fake.killed = false;
  fake.kill = () => {};
  return fake;
}

test("心跳：零输出时明说「一行输出都没有（在装依赖）」，不是含糊的「等待中」", async () => {
  const logs = [];
  const fake = makeFake();
  const h = D.startDsh({
    onUrl: () => {}, onLog: (m) => logs.push(m), probeImpl: async () => false,
    spawnImpl: () => fake, heartbeatMs: 30,
  });
  await new Promise((res) => setTimeout(res, 20));
  /* 元检查：心跳还没到点之前，不许先有「仍在等」——证明后面那条是心跳打出来的 */
  assert.ok(!logs.join("|").includes("仍在等就绪"),
    "20ms 时就出现心跳说明节奏没被 heartbeatMs 控制：" + logs.join("|"));
  await new Promise((res) => setTimeout(res, 100));
  const all = logs.join("|");
  assert.ok(all.includes("仍在等就绪"), "心跳一条都没打：" + all);
  assert.ok(all.includes("一行输出都没有"), "零输出时必须点明是在装依赖，实得：" + all);
  assert.ok(all.includes("装依赖"), "要给出可执行的理解（在装依赖，继续等）：" + all);
  h.stop();
});

test("心跳：有输出但没就绪行 ⇒ 报字节数，不许再说「零输出」（负对照）", async () => {
  const logs = [];
  const fake = makeFake();
  const h = D.startDsh({
    onUrl: () => {}, onLog: (m) => logs.push(m), probeImpl: async () => false,
    spawnImpl: () => fake, heartbeatMs: 30,
  });
  await new Promise((res) => setTimeout(res, 20));
  fake.stdout.emit("data", "booting the web app, please wait\n");   /* 有输出，但不是就绪行 */
  await new Promise((res) => setTimeout(res, 100));
  /* 🔴 2026-10-27 修：判据原来要求**整段日志**都不许出现「一行输出都没有」。
     那是个**竞态**：心跳 30ms 打第一条、测试 20ms 才 emit 数据 —— 定时器一漂就先说了
     「零输出」，之后才说「已收到 33 字节」。整段日志里两句话都合法，判据却判红。
     正解：只看**最后一条心跳**（"当前状态"必须跟实际一致，而不是"历史上从未说过"）。
     这条和本仓那条教训同源：**判快照还是判终态，必须说清**。 */
  const beat = logs.filter((m) => String(m).includes("仍在等就绪")).pop() || "";
  assert.ok(beat.includes("已收到"), "有输出时最后一条心跳就该报字节数：实得 " + beat);
  assert.ok(!beat.includes("一行输出都没有"),
    "已经有输出了还说「零输出」= 判据没跟着实际走：实得 " + beat);
  h.stop();
});

test("心跳：命中就绪行之后必须住口（不许继续念「仍在等」）", async () => {
  const logs = [];
  const urls = [];
  const fake = makeFake();
  const h = D.startDsh({
    onUrl: (u) => urls.push(u), onLog: (m) => logs.push(m), probeImpl: async () => false,
    spawnImpl: () => fake, heartbeatMs: 30,
  });
  await new Promise((res) => setTimeout(res, 20));
  fake.stdout.emit("data", "dsh web: http://127.0.0.1:3080/?token=OK1\n");
  assert.deepStrictEqual(urls, ["http://127.0.0.1:3080/?token=OK1"]);
  const before = logs.filter((l) => l.includes("仍在等就绪")).length;
  await new Promise((res) => setTimeout(res, 120));
  const after = logs.filter((l) => l.includes("仍在等就绪")).length;
  assert.strictEqual(after, before, "接上之后还在念「仍在等」，主人会以为没接上：" + logs.join("|"));
  h.stop();
});

test("心跳：heartbeatMs=0 则一条都不打（负对照 + 元检查：证明前面几条确由心跳产生）", async () => {
  const logs = [];
  const fake = makeFake();
  const h = D.startDsh({
    onUrl: () => {}, onLog: (m) => logs.push(m), probeImpl: async () => false,
    spawnImpl: () => fake, heartbeatMs: 0,
  });
  await new Promise((res) => setTimeout(res, 120));
  assert.strictEqual(logs.filter((l) => l.includes("仍在等就绪")).length, 0,
    "关掉心跳还在打 = 「仍在等」不是心跳产生的，前面几条判据就形同虚设：" + logs.join("|"));
  h.stop();
});
