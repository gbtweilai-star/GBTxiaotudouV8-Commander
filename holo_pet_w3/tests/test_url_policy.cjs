/* GBT小土豆V8 · 桌面壳 · URL / 窗口来源策略 · 契约测试
 *
 * 跑法（自动被 tests/run_tests.py 发现）：
 *     py -3.14 holo_pet_w3/tests/run_tests.py
 *   或 node --test holo_pet_w3/tests/test_url_policy.cjs
 *
 * 为什么这组测试必须存在：`shell/url-policy.cjs` 决定"这个常驻托盘壳能加载什么"。
 * 它原来是 `main.cjs` 里的一段内联代码，而 `main.cjs` 第一行就 require("electron")
 * ⇒ 在普通 node 下**根本没法测**，只能靠"我看着对"。抽成纯模块后，这里把每条规则钉死。
 *
 * 纪律：**负对照必须占多数** —— 只测"合法地址能过"等于没测防护。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");

const P = require(path.join(__dirname, "..", "shell", "url-policy.cjs"));

/* ── 必须放行：本机回环 http/https ── */
test("放行：127.0.0.1 带端口", () => {
  const r = P.loopbackUrlOnly("http://127.0.0.1:3080/?token=abc");
  assert.strictEqual(r.ok, true, r.why);
  assert.match(r.url, /^http:\/\/127\.0\.0\.1:3080\//);
});

test("放行：localhost 与 ::1 与 [::1]", () => {
  for (const u of ["http://localhost:8765/x", "http://[::1]:3080/", "https://127.0.0.1/y"]) {
    const r = P.loopbackUrlOnly(u);
    assert.strictEqual(r.ok, true, u + " 应放行，实得 " + JSON.stringify(r));
  }
});

/* ── 必须拒绝：这是安全件的本体，逐个钉 ── */
test("拒绝：外部主机（http 与 https 都要拒）", () => {
  for (const u of ["http://example.com/", "https://evil.test/x", "http://192.168.1.10:3080/"]) {
    const r = P.loopbackUrlOnly(u);
    assert.strictEqual(r.ok, false, u + " 竟然放行了");
    assert.match(r.why, /回环|主机/, "拒绝理由必须说清是主机不合格");
  }
});

test("拒绝：危险协议 file/javascript/data", () => {
  for (const u of ["file:///C:/Windows/System32/calc.exe",
                   "javascript:alert(1)",
                   "data:text/html,<script>1</script>"]) {
    const r = P.loopbackUrlOnly(u);
    assert.strictEqual(r.ok, false, u + " 竟然放行了");
  }
});

test("拒绝：空 / 非 URL / 只有主机名", () => {
  for (const u of ["", "   ", "not a url", "127.0.0.1:3080"]) {
    const r = P.loopbackUrlOnly(u);
    assert.strictEqual(r.ok, false, JSON.stringify(u) + " 竟然放行了");
  }
});

test("拒绝理由不许是空串（静默拒绝比报错更难查）", () => {
  for (const u of ["", "http://example.com/", "file:///x", "javascript:1"]) {
    const r = P.loopbackUrlOnly(u);
    assert.strictEqual(r.ok, false);
    assert.ok(String(r.why || "").trim().length > 0, JSON.stringify(u) + " 的 why 是空的");
  }
});

/* ── 窗口来源决策：单一决策点 ── */
test("windowSource：带合法 url → kind=url", () => {
  const s = P.windowSource({ id: "a", url: "http://127.0.0.1:3080/" });
  assert.strictEqual(s.kind, "url");
});

test("windowSource：带非法 url → kind=blocked 且带 why（不许静默变 file）", () => {
  const s = P.windowSource({ id: "a", url: "http://example.com/" });
  assert.strictEqual(s.kind, "blocked");
  assert.ok(s.why, "blocked 必须带 why");
});

test("windowSource：needs_url → kind=connect 且带 port", () => {
  const s = P.windowSource({ id: "dsh-chat", needs_url: true, port: 3080 });
  assert.strictEqual(s.kind, "connect");
  assert.strictEqual(s.port, 3080);
});

test("windowSource：只有 file → kind=file", () => {
  const s = P.windowSource({ id: "g", file: "../index.html" });
  assert.strictEqual(s.kind, "file");
  assert.strictEqual(s.file, "../index.html");
});

test("windowSource：三样都没有 → blocked（不许猜一个默认页）", () => {
  const s = P.windowSource({ id: "empty" });
  assert.strictEqual(s.kind, "blocked");
});

test("优先级：url 存在时即使也写了 file，也必须按 url 判（不许回退到本地文件绕过白名单）", () => {
  const s = P.windowSource({ id: "x", url: "http://example.com/", file: "../index.html" });
  assert.strictEqual(s.kind, "blocked",
    "url 非法却回退去 loadFile ⇒ 白名单可被绕过");
});

/* ── 2026-10-04 外部点名白名单（主人令：对话窗直载原生 DeepSeek 网页）── */
test("放行：白名单内外部主机且必须 https（chat.deepseek.com）", () => {
  const r = P.windowLoadPolicy("https://chat.deepseek.com/");
  assert.strictEqual(r.ok, true, r.why);
});

test("拒绝：白名单主机走 http（外部只收 https）", () => {
  const r = P.windowLoadPolicy("http://chat.deepseek.com/");
  assert.strictEqual(r.ok, false, "http 竟然放行了");
  assert.ok(r.why, "拒绝必须带理由");
});

test("拒绝：白名单外主机（哪怕 https、哪怕同根域）", () => {
  for (const u of ["https://example.com/", "https://deepseek.com/", "https://evil.chat.deepseek.com.evil.test/"]) {
    const r = P.windowLoadPolicy(u);
    assert.strictEqual(r.ok, false, u + " 竟然放行了");
  }
});

test("回环在总策略下照旧放行（老规则不回退）", () => {
  const r = P.windowLoadPolicy("http://127.0.0.1:3080/?token=abc");
  assert.strictEqual(r.ok, true, r.why);
});

test("loopbackUrlOnly 仍是窄规则（DSH token 口子的白名单不许被放宽）", () => {
  const r = P.loopbackUrlOnly("https://chat.deepseek.com/");
  assert.strictEqual(r.ok, false, "外部主机竟能过窄规则 —— DSH 口子被放宽了");
});

/* ── 页面固定：窗内导航策略（主人令 2026-10-04「全部给我固定住」）── */
test("导航：同文档（仅 hash/query 变）放行", () => {
  const cur = "file:///C:/w3/home/index.html";
  for (const u of ["file:///C:/w3/home/index.html#sec2", "file:///C:/w3/home/index.html?a=1"]) {
    assert.strictEqual(P.shouldBlockNavigate(cur, u).block, false, u + " 被误拦");
  }
});

test("导航：跨文档一律拦（页面固定住，点链接不带走窗）", () => {
  const cur = "file:///C:/w3/home/index.html";
  for (const u of ["file:///C:/w3/gallery/index.html", "http://127.0.0.1:8765/assets/home/index.html",
                   "https://chat.deepseek.com/", "file:///C:/Windows/System32/calc.exe"]) {
    const r = P.shouldBlockNavigate(cur, u);
    assert.strictEqual(r.block, true, u + " 竟然放行");
    assert.ok(String(r.why || "").length > 0, "拦截必须带理由");
  }
});

test("导航：about:blank 放行（初始空白页），非 URL 拦", () => {
  assert.strictEqual(P.shouldBlockNavigate("file:///x.html", "about:blank").block, false);
  assert.strictEqual(P.shouldBlockNavigate("file:///x.html", "不是 URL").block, true);
});

test("导航：两扇窗的原页互跳也算跨文档（跳转由壳改判为开窗）", () => {
  const cur = "file:///C:/w3/exec-deck/index.html";
  const nxt = "file:///C:/w3/code-deck/index.html";
  assert.strictEqual(P.shouldBlockNavigate(cur, nxt).block, true,
    "窗 A 点链接跳窗 B 必须拦下（由主进程改为开窗 B）");
});

/* ── 与真实注册表对照：现读的 windows.json 必须全过 ── */
test("现读 windows.json：每个窗都能被判成一个合法来源", () => {
  const fs = require("node:fs");
  const reg = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "shell", "windows.json"), "utf8"));
  assert.ok(Array.isArray(reg.windows) && reg.windows.length > 0);
  for (const w of reg.windows) {
    const s = P.windowSource(w);
    assert.ok(["url", "connect", "file"].includes(s.kind),
      `窗 ${w.id} 判成了 ${s.kind}（${s.why || ""}）—— 注册表里有个加载不了的窗`);
  }
});

test("现读注册表：dsh-chat 载本地 GBT 对话面（2026-10-04 改道），白名单仍在壳里备用", () => {
  const fs = require("node:fs");
  const reg = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "shell", "windows.json"), "utf8"));
  const w = reg.windows.filter((x) => x.id === "dsh-chat")[0];
  assert.ok(w, "注册表里没有 dsh-chat");
  /* 改道原因（实测取证）：DeepSeek 风控判 Electron 客户端「使用环境异常」（无痕/持久档同弹，
     见 shell/chat-probe.cjs）⇒ 对话面移到主人 Chrome；本窗载本地页。 */
  const hasUrl = !!w.url;
  const hasFile = !!w.file;
  assert.ok(hasFile || hasUrl, "dsh-chat 必须有可载来源（file 或 url）");
  if (hasUrl) {
    assert.strictEqual(new URL(w.url).hostname, "chat.deepseek.com",
      "若回到外部直载，主机必须仍是白名单里那一个");
    assert.ok(P.EXTERNAL_ALLOWED_HOSTS.has(new URL(w.url).hostname));
  } else {
    assert.match(w.file, /connect\.html$/, "改道时窗 A 应载本地 GBT 对话面 connect.html");
    assert.ok(P.EXTERNAL_ALLOWED_HOSTS.size >= 1, "外部白名单不许被清空（官方许可入口备用）");
  }
});
