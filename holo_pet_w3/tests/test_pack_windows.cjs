/* GBT小土豆V8 桌面壳 · 打包覆盖回归（**带正负对照**，照《扫描器自证律》）
 *
 * 为什么要有这组：`preflight.cjs` 的 `K:globs` **方向是反的** ——
 * 它验「每条 files 规则匹配得到实物」，验不出「**有扇窗没被任何规则覆盖**」。
 * 实测（2026-09-23 第 31 轮）就真漏了一次：加了第 8 扇窗 `eye`，
 * 却忘了把它的目录加进 `package.json` 的 `files` ⇒ 包里会少一整扇窗，
 * 而预检**全绿**。断言松一点的测试抓不到这种（"规则都能匹配到东西" = 绿）。
 *
 * ⇒ 本组必须带**正负对照**：
 *   对照 A：真实 package.json 的 files        → 未覆盖必须为空
 *   对照 B：同一份 files **拿掉 eye 规则**      → 必须命中 eye（证明判据不瞎）
 *   两片段结果必须**不同**；相同 = SCANNER_BLIND，不许报 PASS。
 *
 * 判据本体在 `../shell/pack-coverage.cjs` —— **预检与测试共用同一份**，不复制。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const W3 = path.join(__dirname, "..");
const PKG = JSON.parse(fs.readFileSync(path.join(W3, "package.json"), "utf8"));
const REG = JSON.parse(fs.readFileSync(path.join(W3, "shell", "windows.json"), "utf8"));
const pc = require(path.join(W3, "shell", "pack-coverage.cjs"));

const FILES = (PKG.build && PKG.build.files) || [];
const ids = (list) => list.map((w) => w.id).sort();

test("build.files 存在且非空（没有它就没得判）", () => {
  assert.ok(FILES.length > 0, "package.json build.files 为空 —— 打出来的包会静默少东西");
});

test("对照 A：注册表里每扇本地窗都被 files 规则覆盖", () => {
  const bad = pc.uncoveredWindows(FILES, REG);
  assert.deepStrictEqual(bad, [],
    "有窗没被打包白名单覆盖：" + bad.map((w) => w.id + "(" + w.f + ")").join(", "));
});

test("对照 B（负对照）：拿掉 eye 规则必须报得出 eye —— 否则判据是瞎的", () => {
  const withoutEye = FILES.filter((p) => p !== "eye/**/*" && p !== "eye/*");
  const bad = ids(pc.uncoveredWindows(withoutEye, REG));
  assert.ok(bad.includes("eye"),
    "拿掉 eye 规则后仍报「全覆盖」⇒ SCANNER_BLIND：本判据分辨不出缺覆盖。实测未覆盖=" + JSON.stringify(bad));
});

test("正负对照结果必须不同（相同即判据不可判别）", () => {
  const a = ids(pc.uncoveredWindows(FILES, REG));
  const b = ids(pc.uncoveredWindows(FILES.filter((p) => p !== "eye/**/*"), REG));
  assert.notDeepStrictEqual(a, b, "SCANNER_BLIND: 正负两臂结果相同，判据不可判别");
});

test("每扇本地窗的页面文件都真在盘上（白名单覆盖 ≠ 文件存在）", () => {
  const miss = pc.windowFiles(REG)
    .filter((w) => !fs.existsSync(path.resolve(W3, w.f)));
  assert.deepStrictEqual(miss, [], "注册表点了名但盘上没有：" + JSON.stringify(miss));
});

test("负规则不许把某扇窗排除掉（被排除 = 没覆盖）", () => {
  const negOnly = FILES.filter((p) => !String(p).startsWith("!"))
    .concat(["!**/*.html"]);
  const bad = ids(pc.uncoveredWindows(negOnly, REG));
  assert.ok(bad.length > 0, "负规则把所有 html 排除了，判据却说全覆盖 —— 负规则没被算进去");
});

/* ── 包里会装进什么（按序裁决 + 内容审计）────────────────────────────
   2026-09-23 第 35 轮实测的缺口：`eye/**` 把 `eye/frames/` 里
   **触手拍的整屏截图**（12 张 / 1.9 MB）一起匹配进了包。
   `.gitignore` 早排除了它们，**打包白名单从来没跟它同步过**。
   而 `K:globs`（规则都匹配到实物）与 `K:winfiles`（每扇窗都被覆盖）**都会给它放绿** ——
   所以必须单独立一格，判据是「**这是什么**」，不是「规则匹配没匹配到」。 */

function realTree() {
  const out = [];
  (function walk(dir, rel) {
    let ents = [];
    try { ents = fs.readdirSync(dir, { withFileTypes: true }); } catch (_) { return; }
    for (const e of ents) {
      const p = path.join(dir, e.name);
      const r = rel ? rel + "/" + e.name : e.name;
      if (e.isDirectory()) walk(p, r); else out.push(r);
    }
  })(W3, "");
  return out;
}

test("进包清单：eye 的页面进、**触手拍的截图不进**", () => {
  const inc = pc.resolvePack(FILES, ["eye/index.html", "eye/eye.js", "eye/frames/f-000.jpg", "eye/frames.js"]);
  assert.ok(inc.includes("eye/index.html"), "eye 的页面竟然没进包（那扇窗会是空的）");
  assert.ok(inc.includes("eye/eye.js"));
  assert.ok(!inc.includes("eye/frames/f-000.jpg"),
    "**整屏截图会进包** —— 打出来的 App 会带着主人的桌面截图分发");
  assert.ok(!inc.includes("eye/frames.js"), "描述主人屏幕的帧清单会进包");
});

test("负对照：拿掉负规则，截图必须**真被判成会进包**（否则这一格是空的）", () => {
  const noNeg = FILES.filter((p) => p !== "!eye/frames/**" && p !== "!eye/frames.js");
  const inc = pc.resolvePack(noNeg, ["eye/frames/f-000.jpg"]);
  assert.ok(inc.includes("eye/frames/f-000.jpg"),
    "拿掉负规则后仍说截图不进包 ⇒ 判据不可判别（它根本测不出这件事）");
  const shame = pc.auditPack(inc);
  assert.strictEqual(shame.length, 1, "审计没把截图报出来");
  assert.ok(/截图/.test(shame[0].why), "报的理由不对：" + shame[0].why);
});

test("按序裁决：后面的规则覆盖前面的（electron-builder 语义）", () => {
  assert.strictEqual(pc.includedIn(["a/**", "!a/b/**"], "a/b/c.txt"), false);
  assert.strictEqual(pc.includedIn(["!a/b/**", "a/**"], "a/b/c.txt"), true,
    "反序时后写的 a/** 应该把前面的排除盖回来");
  assert.strictEqual(pc.includedIn(["a/**"], "z/c.txt"), false, "白名单制：没命中就不进包");
});

/* ── 通配翻译器本身（它是所有打包判据的共同地基）──────────────────── */

test("通配翻译：`**` 要能跨目录，`*` 不许跨目录", () => {
  assert.ok(pc.rx("a/**").test("a/b/c.txt"), "`a/**` 匹配不到 a/b/c.txt —— 翻译器坏了");
  assert.ok(pc.rx("a/**").test("a/b.txt"));
  assert.ok(pc.rx("a/**/*").test("a/index.html"), "`a/**/*` 要能匹配它自己这一层");
  assert.ok(pc.rx("a/**/*").test("a/x/y.html"), "`a/**/*` 要能跨层");
  assert.ok(pc.rx("*.html").test("index.html"));
  assert.ok(!pc.rx("*.html").test("eye/index.html"), "`*.html` 不该跨目录（electron-builder 是相对路径匹配）");
  assert.ok(pc.rx("**/__pycache__/**").test("x/y/__pycache__/a.pyc"));
});

test("通配翻译：链式替换的坑不许再回来（`a/**` 曾经编成 `/^a\\/.[^/]*$/`）", () => {
  /* 这条是**回归钉子**：第三步 replace 曾经把第二步生成的 `.*` 里的星号再吃一遍。
     判据：`a/**` 编出来的正则必须能匹配"任意深度"。 */
  const r = pc.rx("a/**");
  for (const p of ["a/b.txt", "a/b/c.txt", "a/b/c/d/e.txt"]) {
    assert.ok(r.test(p), "`a/**` 匹配不到 " + p + "（正则=" + r.source + "）");
  }
});

test("内容审计：依赖目录 / 编译缓存 / 版本库元数据都抓得到", () => {
  const bad = pc.auditPack(["x/node_modules/y.js", "gbt_allinone/__pycache__/a.pyc",
                            ".git/config", "desktop.ini"]);
  const paths = bad.map((b) => b.path);
  for (const p of ["x/node_modules/y.js", "gbt_allinone/__pycache__/a.pyc", ".git/config", "desktop.ini"]) {
    assert.ok(paths.includes(p), "没抓到：" + p);
  }
});

test("真实配置 × 真实树：进包清单里一个「不该进」的都没有", () => {
  const inc = pc.resolvePack(FILES, realTree());
  const shame = pc.auditPack(inc);
  assert.deepStrictEqual(shame, [],
    "真实配置下仍有文件会被打进包但不该进：" + JSON.stringify(shame.slice(0, 5)));
});

test("真实配置 × 真实树：八扇窗的页面**都在**进包清单里（不是只有配置说覆盖）", () => {
  const inc = new Set(pc.resolvePack(FILES, realTree()));
  const miss = pc.windowFiles(REG).filter((w) => !inc.has(w.f)).map((w) => w.id + "(" + w.f + ")");
  assert.deepStrictEqual(miss, [], "这些窗的页面不在进包清单里：" + JSON.stringify(miss));
});
