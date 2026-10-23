/* 形状探针：把上帝视角四格背后的**真实数据形状**打出来（只在 Electron 里有意义）。
 *
 * 为什么要单独一件：`main.cjs:1341` 那句注释写着「让探针能脱离 Electron 直接验它们」——
 * **实测不成立**：`require("electron")` 在纯 node 下解析不到（全局装的 electron 不在
 * `holo_pet_w3/node_modules` 里）⇒ `main.cjs:17` 当场 MODULE_NOT_FOUND。
 * 所以形状只能在 Electron 运行时里取。本件就是那一步，**不许靠猜字段名**。
 *
 * 用法：electron holo_pet_w3/shell/probe-shapes.cjs
 */
"use strict";
process.env.GBT_W3_WIRE_ONLY = "1";     // 只接线、不开窗

const electron = require("electron");
const { app } = electron;

function show(name, v) {
  const s = JSON.stringify(v);
  console.log("=== " + name + "  （" + (s ? s.length : 0) + " 字符）===");
  if (s === undefined) { console.log("  undefined"); return; }
  console.log("  顶层键: " + (v && typeof v === "object" ? Object.keys(v).join(", ") : typeof v));
  console.log("  " + s.slice(0, 900));
  console.log();
}

app.whenReady().then(() => {
  let m;
  try {
    m = require("./main.cjs");
  } catch (err) {
    console.log("require main.cjs 失败：" + String(err && err.message || err));
    return app.exit(3);
  }
  for (const n of ["w3State", "w3Tasks", "w3Env", "w3Ledger", "w3Health", "w3Eigenflux", "w3H1"]) {
    if (typeof m[n] !== "function") { console.log("=== " + n + " 不存在 ===\n"); continue; }
    try { show(n, m[n]()); } catch (err) { console.log("=== " + n + " 抛错：" + String(err && err.message || err) + "\n"); }
  }
  app.exit(0);
}).catch((err) => { console.log("探针抛错：" + String(err && err.stack || err).slice(0, 300)); app.exit(3); });
