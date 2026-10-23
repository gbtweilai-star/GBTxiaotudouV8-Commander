/* GBT小土豆V8 · 桌面壳 · 托盘品牌图 · 契约测试
 *
 * 跑法（自动被 tests/run_tests.py 发现）：
 *     node --test holo_pet_w3/tests/test_tray_logo.cjs
 *
 * 为什么这件必须存在：主人令（2026-10-07）指着截图里的**托盘/任务栏那一格**说「这里的 Logo」——
 * 原来那里是 `trayIcon(16, 金, 青)` **代码现画的方块**，品牌在托盘上断了。
 * 修法是读品牌真资产，而"真"这件事不能靠我说：这里把**逐字节相同**钉死。
 * 钉住的是三件事：① 图在；② 是合法 PNG；③ 与品牌源`assets/brand/logo-potato-32.png` **逐字节相同**
 * （⇒ 谁哪天"顺手"换了一张自己画的图，这条当场红）。
 *
 * 品牌资产的唯一出处是 `assets/brand/`（见 memory/2026-09-22-品牌与Logo不丢.md §二）；
 * 壳内的 `build/tray-logo-32.png` 是**随包分发的复制品**，不是第二份真源 —— 所以它必须与源同字节。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");

const ROOT = path.join(__dirname, "..", "..");            // 仓根
const SRC = path.join(ROOT, "assets", "brand", "logo-potato-32.png");
const SHIPPED = path.join(ROOT, "holo_pet_w3", "build", "tray-logo-32.png");
const sha = (p) => crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex");

test("托盘品牌图在壳内（随包分发的那一份）", () => {
  assert.ok(fs.existsSync(SHIPPED), "缺 " + SHIPPED + " —— 托盘会退回方块图");
});

test("它是合法 PNG（头 8 字节就是 PNG 签名）", () => {
  const head = fs.readFileSync(SHIPPED).subarray(0, 8);
  assert.deepStrictEqual([...head], [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
});

test("与品牌源逐字节相同（品牌只有一份真资产，壳内不许是「另画的一张」）", () => {
  assert.ok(fs.existsSync(SRC), "品牌源不见了：" + SRC);
  assert.strictEqual(sha(SHIPPED), sha(SRC),
    "壳内托盘图与 assets/brand/logo-potato-32.png 不同 —— 品牌要么被换过、要么被重画过");
});

test("负对照：随便一张别的 PNG 不该等于品牌源（说明上一条不是恒真）", () => {
  const other = path.join(ROOT, "assets", "brand", "icon-potato-512.png");
  assert.ok(fs.existsSync(other), "需要一个不同的参照文件");
  assert.notStrictEqual(sha(other), sha(SRC), "两个不同资产竟然同哈希 —— 取样错了");
});
