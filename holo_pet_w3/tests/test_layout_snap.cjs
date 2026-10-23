/* GBT小土豆V8 · W3 · 布局吸附契约测试（字段形状）
 *
 * 被测对象：`holo_pet_w3/shell/layout.cjs`（JS 纯函数）——所以用 `node --test` 跑，
 * 不用 Python 重写一遍逻辑（重写等于验复刻品，不算验真代码）。
 *
 * 本组用例守的是 R28 修掉的那个缺陷：调用方把 Electron 的 `getBounds()`
 * （形状 `{x,y,width,height}`）直接喂给只认 `{x,y,w,h}` 的 `snapBounds`。
 *
 * 按《扫描器自证律》，用例 2 与用例 6 是**对照**：
 *   用例 2 = 反向证明「不转换就会错」（假绿防线）
 *   用例 6 = 负对照「不该吸的时候不许吸」（防止测试只会说"吸了"）
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const path = require("path");
const fs = require("node:fs");

const layout = require(path.join(__dirname, "..", "shell", "layout.cjs"));

const DISPLAYS = [{ x: 0, y: 0, width: 1920, height: 1080 }];
const PX = layout.SNAP_PX;                        /* 12 */

const electronShape = (x, y, w, h) => ({ x: x, y: y, width: w, height: h });
const internalShape = (x, y, w, h, id) =>
  layout.fromBrowserBounds(electronShape(x, y, w, h), id || "win");

/* 陪练窗口：x=100 宽 800 → 右边缘 900 */
const PEER = internalShape(100, 100, 800, 600, "peer");

test("1. 内部形状 {x,y,w,h}：吸其他窗口右边缘 → 吸到 900", () => {
  const w = internalShape(894, 300, 800, 600, "godview");   /* 距 900 仅 6px */
  const snapped = layout.snapBounds(w, DISPLAYS, [PEER], PX);
  assert.strictEqual(snapped.x, 900);
});

test("2. 修复前现场（自身与 others 都是 Electron 形状）→ 停在 894 不吸；且「只修一半」不够", () => {
  const selfRaw = electronShape(894, 300, 800, 600);        /* 相当于 win.getBounds() */
  const peerRaw = electronShape(100, 100, 800, 600);        /* 相当于 o.getBounds() */

  /* 两边都没转 —— 修复前的真实行为 */
  const bothRaw = layout.snapBounds(selfRaw, DISPLAYS, [peerRaw], PX);
  assert.strictEqual(bothRaw.x, 894, "两边都未转换：吸不到 peer 右边缘");
  assert.notStrictEqual(bothRaw.x, 900);

  /* 只修自身、漏了 others —— peer 的右边缘目标退化成它的左边缘 100，仍然吸不到 */
  const halfFixed = layout.snapBounds(
    internalShape(894, 300, 800, 600, "godview"), DISPLAYS, [peerRaw], PX);
  assert.strictEqual(halfFixed.x, 894, "只转自身不转 others：仍然吸不到 900 —— 两处都得改");

  /* 两处都转换才吸上 */
  const fixed = layout.snapBounds(
    internalShape(894, 300, 800, 600, "godview"), DISPLAYS, [PEER], PX);
  assert.strictEqual(fixed.x, 900);
});

test("3. 走修复后的调用序列（转换 → snapBounds → toBrowserBounds）→ 吸到 900 且尺寸不变", () => {
  const raw = electronShape(894, 300, 800, 600);            /* 相当于 win.getBounds() */
  const snapped = layout.snapBounds(
    layout.fromBrowserBounds(raw, "godview"), DISPLAYS, [PEER], PX);
  const next = layout.toBrowserBounds(snapped);
  assert.strictEqual(next.x, 900);
  assert.strictEqual(next.width, 800);
  assert.strictEqual(next.height, 600);
});

test("4. 屏幕右边缘（依赖 b.w）：Electron 形状不吸 1516 / 转换后吸 1520", () => {
  const raw = electronShape(1516, 300, 400, 300);
  const viaElectron = layout.snapBounds(raw, DISPLAYS, [], PX);
  assert.strictEqual(viaElectron.x, 1516, "b.w 回落 1120 → 目标算成 800 → 不吸");
  const viaInternal = layout.snapBounds(layout.fromBrowserBounds(raw, "w"), DISPLAYS, [], PX);
  assert.strictEqual(viaInternal.x, 1920 - 400, "真实宽度 400 → 目标 1520 → 吸");
});

test("5. 尺寸不被默认值改写：转换后 400；直接喂 Electron 形状得 1120", () => {
  const raw = electronShape(894, 300, 400, 300);
  const good = layout.toBrowserBounds(
    layout.snapBounds(layout.fromBrowserBounds(raw, "w"), DISPLAYS, [PEER], PX));
  assert.strictEqual(good.width, 400);
  assert.strictEqual(good.height, 300);
  const bad = layout.toBrowserBounds(
    layout.snapBounds(raw, DISPLAYS, [PEER], PX));
  assert.strictEqual(bad.width, 1120, "缺 w/h 时 normalize 回落默认值——这就是症状 B");
});

test("6. 负对照：距离 > SNAP_PX 时不许吸", () => {
  const w = internalShape(887, 300, 800, 600, "godview");   /* 距 900 = 13px > 12 */
  const snapped = layout.snapBounds(w, DISPLAYS, [PEER], PX);
  assert.strictEqual(snapped.x, 887);
  assert.notStrictEqual(snapped.x, 900);
});

test("7. 幂等：normalize(fromBrowserBounds(b)) 的 x/y/w/h 与 fromBrowserBounds(b) 一致", () => {
  const raw = electronShape(10, 20, 800, 600);
  const converted = layout.fromBrowserBounds(raw, "w");
  const normalized = layout.normalize(converted, "w");
  assert.strictEqual(normalized.x, 10);
  assert.strictEqual(normalized.y, 20);
  assert.strictEqual(normalized.w, 800);
  assert.strictEqual(normalized.h, 600);
  assert.strictEqual(normalized.w, converted.w);
  assert.strictEqual(normalized.h, converted.h);
});

/* ── W7 · 窗口可见性契约（《指纹算法必须同名》同类：声明了就必须生效）──
 * 背景：注册表里的 `default.visible:false` 曾「声明了没人用」—— main.cjs 建窗从不读它，
 * 窗口照样弹出来（与 R63 `--gbt-violet` 声明了、`var()` 0 引用同类）。
 * 本组两层判据：① 纯函数层 `layout.normalize` 的 visible 语义；② 源码层 main.cjs 有没有真的用它。
 * 源码层断言与 R64 品牌 token 契约同法（`node --test` 下不起 Electron，只能断源码）。 */
const W3 = path.join(__dirname, "..");
const MAIN = fs.readFileSync(path.join(W3, "shell", "main.cjs"), "utf8");

test("8. 窗口可见性契约：default.visible:false 的窗，起壳后不弹出来", () => {
  /* ① 纯函数层：未声明 → 默认可见；声明 false → 不可见 */
  assert.strictEqual(layout.normalize({}, "w").visible, true, "未声明 visible 的窗必须默认可见");
  assert.strictEqual(layout.normalize({ visible: false }, "w").visible, false);
  assert.strictEqual(layout.normalize({ visible: true }, "w").visible, true);
  /* 负对照：两组结果必须不同，否则判据没有判别性 */
  assert.notStrictEqual(layout.normalize({}, "w").visible, layout.normalize({ visible: false }, "w").visible);

  /* ② 源码层：建窗必须把这个值传进 BrowserWindow 的 show: */
  assert.ok(/show:\s*placed\.visible/.test(MAIN),
    "shell/main.cjs 建窗没有把 placed.visible 传给 show: —— default.visible 又变成『声明了没人用』");
  /* ③ 第二个实例不许把「默认不开」的窗唤醒 */
  assert.ok(/entry\.default\.visible === false\) return;/.test(MAIN),
    "shell/main.cjs 的 second-instance 没有跳过 default.visible:false 的窗");
});
