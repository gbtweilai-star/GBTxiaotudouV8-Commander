/* GBT小土豆V8 · 心跳预算（纯函数 · 可单测）
 *
 * ⚠️ 本文件是**按 main.cjs 调用契约重建**的，不是原件（原件已丢失）。
 *    重建依据：main.cjs 的四个调用点
 *      · 2458  beatBudgetMod.LAG_KEEP           环形缓冲保留的迟到样本数
 *      · 2787  beatBudgetMod.STALE_CAP_MS       预算上限
 *      · 2786  beatBudget({beatMs, floorMs, lagMax, capMs}) → **数字（毫秒）**
 *              （2793 行拿它和上次的值做 `!==` 比较，2795 行直接拼 "ms" ⇒ 必须是 number）
 *
 * 为什么预算要**自适应**（照 main.cjs 2453 行附近的既有说法）：
 *   固定阈值只对"一直很闲"的窗成立；一处重帧就会把正常窗判成卡死并强崩。
 *   所以只留最近 LAG_KEEP 次迟到，看门狗按**这扇窗自己的实测迟到**抬预算。
 *
 * 红线：
 *   · 预算**不许低于** floorMs —— 低于它等于把正常窗判死；
 *   · 预算**不许高于** capMs  —— 高于它等于看门狗永不触发，卡死也没人管；
 *   · 返回整数毫秒；NaN / 负数一律按下限处理，不返回 undefined。
 */
"use strict";

/* 环形缓冲保留多少拍。取 12：按 BEAT_MS=2000 约 24 秒的窗口，
   够跨过一次 GC 抖动，又不至于把很久以前的尖峰永远钉在预算里。 */
const LAG_KEEP = 12;

/* 预算硬上限。STALE_MS 默认 10000；给到 30000 = 容忍连续 15 拍迟到。
   再高就不是"卡死检测"了，是"没有检测"。 */
const STALE_CAP_MS = 30000;

function num(v, dflt) {
  const n = Number(v);
  return Number.isFinite(n) ? n : dflt;
}

/* beatBudget({beatMs, floorMs, lagMax, capMs}) → 毫秒整数
 *   beatMs  基本拍间隔（main.cjs 现为 2000）
 *   floorMs 下限（main.cjs 现为 max(beatMs*3, 10000) = 10000）
 *   lagMax  该窗最近的实测迟到上限（ring 里取 max；没量到就是 0）
 *   capMs   上限（STALE_CAP_MS）
 *
 * 语义：预算 = 基本拍 + 实测迟到上限，再夹进 [floor, cap]。
 *   lagMax = 0     → max(2000, 10000) = 10000（贴着下限，与"没量到"一致）
 *   lagMax = 3000  → max(5000, 10000) = 10000（还没越过下限）
 *   lagMax = 20000 → 22000（真的量大，就真的抬）
 *   lagMax = 90000 → 封顶 30000（不无限让）
 */
function beatBudget(opt) {
  const o = opt || {};
  const beatMs = Math.max(0, num(o.beatMs, 2000));
  const capMs = Math.max(1, num(o.capMs, STALE_CAP_MS));

  /* 下限本身不许超过上限：传进来的 floorMs 若比 capMs 还大（配置写错），
     以上限为准 —— 否则 clamp 逻辑会退化成"永远等于 floor"，等于没上限。 */
  const floorRaw = Math.max(0, num(o.floorMs, beatMs * 3));
  const floorMs = Math.min(floorRaw, capMs);

  const lagMax = Math.max(0, num(o.lagMax, 0));

  let budget = beatMs + lagMax;
  if (budget < floorMs) budget = floorMs;
  if (budget > capMs) budget = capMs;

  return Math.round(budget);
}

module.exports = { beatBudget, STALE_CAP_MS, LAG_KEEP };
