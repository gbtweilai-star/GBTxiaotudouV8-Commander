/* GBT小土豆V8 · W3 · 品牌 token 引用契约 + 盲区紫标记契约
 *
 * 为什么要有这组：R63 首屏实测出「`--gbt-violet` 声明了，但全仓 `var(--gbt-violet)` 0 命中」——
 * 品牌三色白皮书定了三色，屏上只渲染出金 + 青两色。这不是渲染故障，是**声明了没人用**。
 * 这类缺陷断言松一点的测试抓不到（token 存在 = 绿），所以本组必须带**正负对照**（《扫描器自证律》）：
 *   对照片段 A：声明 + 被引用  -> unused 必须为空
 *   对照片段 B：声明 + 没引用  -> unused 必须命中它（证明扫描器不瞎，能报得出）
 * 两片段结果必须不同；相同 = SCANNER_BLIND，不许报 PASS。
 *
 * 另守两条《holo_petUI规格》§2.1 冻结约束：
 *   1) 裸色值只允许出现在 §1 token 定义块（:root）里；
 *   2) 盲区标记走**身份色**（深空紫描边 + 标签），不顶替 §10.3 的绿 / 黄 / 红 / 灰状态色。
 * 行为级证据（真窗口里 `tr[data-blind="true"]` 命中 + 紫色像素 > 0）由 R64 真窗口抓取单独给，不在本文件假装。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const W3 = path.join(__dirname, "..");
const CSS = fs.readFileSync(path.join(W3, "window.css"), "utf8");
const JS = fs.readFileSync(path.join(W3, "window.js"), "utf8");

const BRAND = ["--gbt-gold", "--gbt-cyan", "--gbt-violet"];

/* 扫描器：把 CSS 拆成「:root 里声明的 --gbt-*」与「:root 之外被 var() 引用的 --gbt-*」。
 * 解析不出来一律返回 blind（不许把读不到当读到了 —— 《空不等于不存在律》）。 */
function scanTokens(css) {
  const rootAt = css.indexOf(":root");
  if (rootAt < 0) return { blind: "NO_ROOT_BLOCK" };
  const open = css.indexOf("{", rootAt);
  const close = css.indexOf("}", open);
  if (open < 0 || close < 0) return { blind: "ROOT_BLOCK_UNPARSED" };
  const rootBlock = css.slice(open + 1, close);
  const outside = css.slice(0, open) + css.slice(close + 1);
  const declared = [];
  const re = /(--gbt-[a-z0-9-]+)\s*:/g;
  let m;
  while ((m = re.exec(rootBlock)) !== null) declared.push(m[1]);
  const used = declared.filter((t) => outside.indexOf("var(" + t + ")") >= 0);
  return { blind: null, declared: declared, used: used,
           unused: declared.filter((t) => used.indexOf(t) < 0) };
}

test("1. 正对照：真实 window.css 里三色 token 全部被引用（声明了就必须用）", () => {
  const s = scanTokens(CSS);
  assert.strictEqual(s.blind, null, "扫描器读不到 :root 块 —— 先修扫描器，别报 0 命中");
  for (const t of BRAND) {
    assert.ok(s.declared.indexOf(t) >= 0, t + " 没在 :root 里声明");
    assert.ok(s.used.indexOf(t) >= 0, t + " 声明了但全文件 var() 0 引用 —— 就是 R63 那个缺口");
  }
  assert.deepStrictEqual(s.unused, [], "还有声明未引用的 token：" + s.unused.join(","));
});

test("2. 负对照：对照片段 A（声明+引用）与 B（声明+没引用）结果必须不同", () => {
  /* 自伤 #3（如实留档）：初版 A 组声明了 gold + violet 却只引用 violet，
   * 于是 A 组自己就带着一个未引用项 —— 对照片段不满足它要断言的不变量，用例先红。
   * 修法：A / B 只放一个 token，差别只在「引没引用它」。 */
  const A = ":root {\n  --gbt-violet: #7C4DFF;\n}\n.x { color: var(--gbt-violet); }";
  const B = ":root {\n  --gbt-violet: #7C4DFF;\n}\n.x { color: #000000; }";
  const a = scanTokens(A);
  const b = scanTokens(B);
  assert.strictEqual(a.blind, null);
  assert.strictEqual(b.blind, null);
  assert.deepStrictEqual(a.unused, [], "A 组不该有未引用项");
  assert.deepStrictEqual(b.unused, ["--gbt-violet"], "B 组必须报出未引用项，否则扫描器瞎");
  assert.notDeepStrictEqual(a.unused, b.unused);
});

test("3. 盲区紫标记契约：实现 ↔ 样式 ↔ 标记名三处对齐", () => {
  assert.ok(/tr\[data-blind="true"\]/.test(CSS), "window.css 里没有 tr[data-blind=\"true\"] 规则");
  assert.ok(CSS.indexOf("var(--gbt-violet)") >= 0, "盲区规则没有引用深空紫 token");
  assert.ok(/\.gbt-blind-tag\s*\{/.test(CSS), "window.css 里没有 .gbt-blind-tag 规则");
  assert.ok(JS.indexOf('tr2.dataset.blind = "true"') >= 0, "window.js 没给盲区行打 data-blind");
  assert.ok(JS.indexOf('"gbt-blind-tag"') >= 0, "window.js 没挂 gbt-blind-tag 标签");
  assert.ok(JS.indexOf("var isBlind = false;") >= 0, "window.js 没有盲区判定的局部标记");
});

/* 剥注释：对「代码」断言，不对「文本」断言（《扫描器自证律》）。
 * 不剥的后果实测过：window.css:185-188 那句注释正文里的字面量 #6B7280 被算成违规，
 * 与 330/345 两条真违规混在同一条红里 ⇒ 红得没有判别性，长期红下去就没人看了。
 * 修法抄 test_w9_features.cjs:311-313 已经验证过的两层拆法。 */
const BARE_COLOR = /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/g;
const stripComments = (src) => String(src)
  .replace(/\/\*[\s\S]*?\*\//g, " ")
  .replace(/(^|[^:])\/\/[^\n]*/g, "$1 ");

test("4. 裸色值纪律：:root 之外不许出现裸色值（§2.1 冻结约束）", () => {
  const open = CSS.indexOf("{", CSS.indexOf(":root"));
  const close = CSS.indexOf("}", open);
  const outside = CSS.slice(0, open) + CSS.slice(close + 1);

  /* 剥注释层自己的正负对照：注释里的色值必须被剥掉，真代码里的必须留着。
     没有这一组，剥过头（把真代码也剥了）会直接把本条测试变成永远绿的摆设。 */
  const NOTE_ONLY = "/* 中性就用中性 token，不要写 #6B7280 这种裸色值 */\n.x { color: red; }";
  const REAL_CODE = "/* 注释里写着 rgba(1, 2, 3, .5) */\n.x { background: rgba(245, 176, 65, 0.06); }";
  assert.deepStrictEqual(stripComments(NOTE_ONLY).match(BARE_COLOR) || [], [],
                         "剥注释层没牙：注释里的色值仍被当真代码");
  assert.deepStrictEqual(stripComments(REAL_CODE).match(BARE_COLOR) || [], ["rgba("],
                         "剥注释层剥过头：真代码里的裸色值也被剥掉了");

  const bare = stripComments(outside).match(BARE_COLOR) || [];
  assert.deepStrictEqual(bare, [], "token 定义块之外出现裸色值：" + bare.join(", "));
});
