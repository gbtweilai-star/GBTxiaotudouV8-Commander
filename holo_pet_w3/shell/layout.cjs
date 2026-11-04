/* GBT小土豆V8 · 窗口布局持久化 + 几何（纯函数 · 可单测）
 *
 * ⚠️ 本文件是**按 main.cjs 调用契约重建**的，不是原件（原件已丢失）。
 *    重建依据：main.cjs 的 11 个调用点
 *      · 1262/1294  loadLayout(LAYOUT_FILE) → { windows: { [id]: record } }
 *      · 1267/1957  saveLayout(LAYOUT_FILE, data)
 *      · 1956       emptyLayout()
 *      · 1297/1961  normalize(wanted, id) → record
 *      · 1297/1961  clampBounds(record, displays) → record
 *      · 1754/1962  toBrowserBounds(record) → { x, y, width, height }
 *      · 1265/1752  fromBrowserBounds(bounds, id, visible) → record
 *      · 1753       snapBounds(record, displays, others, SNAP_PX) → record
 *      · 1753       SNAP_PX 常量
 *    职责（main.cjs 头部注释原话）：**布局持久化（userData/window-layout.json，越界回落主屏）· 吸附**。
 *
 * record 形状（本仓内部统一，不对外）：{ x, y, w, h, visible }
 *   —— 和 windows.json 里 `default` 的字段名一致（x/y/w/h/visible），
 *      所以 stored 与 default 可以直接同构替换，不需要两套读法。
 * BrowserWindow 用的是 { x, y, width, height }，靠 toBrowserBounds / fromBrowserBounds 换。
 */
"use strict";

const fs = require("fs");
const path = require("path");

/* 吸附阈值：两道边相距 <= 12px 就当"贴上"。太小会吸附不住，太大会误吸。 */
const SNAP_PX = 12;

/* 窗口最小可用尺寸：再小就点不到标题栏按钮。 */
const MIN_W = 320;
const MIN_H = 240;

/* 没有布局记录时的兜底尺寸（和 windows.json 里主窗的量级对齐）。 */
const DEFAULT_W = 1280;
const DEFAULT_H = 860;

const LAYOUT_VERSION = 1;

function toNum(v, dflt) {
  const n = Number(v);
  return Number.isFinite(n) ? n : dflt;
}

function toInt(v, dflt) {
  return Math.round(toNum(v, dflt));
}

/* 空布局。**不含任何窗口条目** —— 条目由保存时写入。 */
function emptyLayout() {
  return { version: LAYOUT_VERSION, saved_at: null, windows: {} };
}

/* 读布局文件。任何失败（不存在 / 坏 JSON / 形状不对）一律回空布局，不抛。
   为什么吞异常：布局文件坏掉不该让壳起不来，最差就是"窗口回到默认位置"。 */
function loadLayout(file) {
  const out = emptyLayout();
  if (!file) return out;
  let doc;
  try {
    doc = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (err) {
    return out;
  }
  if (!doc || typeof doc !== "object") return out;
  if (doc.version) out.version = doc.version;
  if (doc.saved_at) out.saved_at = doc.saved_at;
  if (doc.windows && typeof doc.windows === "object" && !Array.isArray(doc.windows)) {
    out.windows = doc.windows;
  }
  return out;
}

/* 写布局文件：先写 .tmp 再 rename，避免写一半断电留下半个 JSON。 */
function saveLayout(file, data) {
  if (!file) return false;
  const doc = Object.assign(emptyLayout(), data || {});
  doc.version = doc.version || LAYOUT_VERSION;
  doc.saved_at = new Date().toISOString();
  if (!doc.windows || typeof doc.windows !== "object") doc.windows = {};

  try {
    fs.mkdirSync(path.dirname(file), { recursive: true });
  } catch (err) { /* 目录已在或不可建：交给下面的写入去暴露 */ }

  const tmp = file + ".tmp";
  fs.writeFileSync(tmp, JSON.stringify(doc, null, 2), "utf8");
  fs.renameSync(tmp, file);
  return true;
}

/* 把任意来路的"想要的窗口位置"标准化成 record。
   wanted 可能是 windows.json 的 default（w/h）、旧布局里的记录（w/h）、
   或别处传来的 BrowserWindow bounds（width/height）—— 三种都吃。 */
function normalize(wanted, id) {
  const w = wanted || {};
  const rawW = w.w !== undefined ? w.w : w.width;
  const rawH = w.h !== undefined ? w.h : w.height;

  return {
    id: id || w.id || null,
    x: toInt(w.x, 0),
    y: toInt(w.y, 0),
    w: Math.max(MIN_W, toInt(rawW, DEFAULT_W)),
    h: Math.max(MIN_H, toInt(rawH, DEFAULT_H)),
    visible: w.visible !== false,
  };
}

function workAreaOf(display) {
  const d = display || {};
  return d.workArea || d.bounds || null;
}

/* 两个矩形的重叠面积。用于判"这扇窗现在落在哪块屏上"。 */
function overlapArea(rect, area) {
  if (!rect || !area) return 0;
  const ax1 = rect.x, ay1 = rect.y;
  const ax2 = rect.x + rect.w, ay2 = rect.y + rect.h;
  const bx1 = area.x, by1 = area.y;
  const bx2 = area.x + area.width, by2 = area.y + area.height;

  const ow = Math.min(ax2, bx2) - Math.max(ax1, bx1);
  const oh = Math.min(ay2, by2) - Math.max(ay1, by1);
  if (ow <= 0 || oh <= 0) return 0;
  return ow * oh;
}

/* 挑这扇窗该归哪块屏：重叠面积最大的那块；完全越界就回主屏。
   displays 传进来的通常是 screen.getAllDisplays()，首项即主屏。 */
function pickDisplay(record, displays) {
  const list = Array.isArray(displays) ? displays.filter(Boolean) : [];
  if (!list.length) return null;

  let best = null;
  let bestArea = 0;
  for (const d of list) {
    const area = workAreaOf(d);
    if (!area) continue;
    const a = overlapArea(record, area);
    if (a > bestArea) { bestArea = a; best = d; }
  }
  if (best) return best;

  /* 完全越界（拔了副屏 / 改了分辨率）：回落主屏。 */
  return list[0];
}

/* 把 record 夹回某块屏的工作区内。
   两件事：
     ① 完全越界 → 回主屏并居中，别让窗口飘到看不见的地方；
     ② 部分越界 → 平移进来，保证标题栏够得着（至少露出 SNAP_PX*4 的边）。
   尺寸超过工作区时收缩到工作区。 */
function clampBounds(record, displays) {
  const r = normalize(record, record && record.id);
  const list = Array.isArray(displays) ? displays : [];

  if (!list.length) return r;

  const wa = workAreaOf(pickDisplay(r, list));
  if (!wa) return r;

  /* 尺寸先收进工作区 */
  if (r.w > wa.width) r.w = Math.max(MIN_W, wa.width);
  if (r.h > wa.height) r.h = Math.max(MIN_H, wa.height);

  const minVisible = Math.min(SNAP_PX * 4, Math.floor(r.w / 2), Math.floor(r.h / 2));
  const wasOffScreen = overlapArea(r, wa) <= 0;

  if (wasOffScreen) {
    /* 越界回落：居中放主屏。 */
    r.x = Math.round(wa.x + Math.max(0, (wa.width - r.w) / 2));
    r.y = Math.round(wa.y + Math.max(0, (wa.height - r.h) / 2));
    return r;
  }

  /* 平移进边界，保证至少 minVisible 露出。 */
  const maxX = wa.x + wa.width - minVisible;
  const minX = wa.x - r.w + minVisible;
  const maxY = wa.y + wa.height - minVisible;
  const minY = wa.y - r.h + minVisible;

  if (r.x > maxX) r.x = maxX;
  if (r.x < minX) r.x = minX;
  if (r.y > maxY) r.y = maxY;
  if (r.y < minY) r.y = minY;

  return r;
}

/* record → BrowserWindow.setBounds 要的形状 */
function toBrowserBounds(record) {
  const r = normalize(record, record && record.id);
  return { x: r.x, y: r.y, width: r.w, height: r.h };
}

/* BrowserWindow.getBounds → record（保存时用） */
function fromBrowserBounds(bounds, id, visible) {
  const b = bounds || {};
  const r = normalize({ x: b.x, y: b.y, w: b.width, h: b.height }, id);
  if (visible !== undefined) r.visible = visible === true;
  return r;
}

/* 吸附：把 record 的边往"屏幕边缘 + 其他窗口的边"上贴。
   snapping 只改位置不改尺寸，且一次只认**最近的一条**候选，避免连跳。
   返回新的 record（不原地改入参）。 */
function snapBounds(record, displays, others, snapPx) {
  const r = normalize(record, record && record.id);
  const px = Math.max(0, toNum(snapPx, SNAP_PX));
  if (px === 0) return r;

  const edgesX = [];
  const edgesY = [];

  /* 屏幕工作区的四条边 */
  const list = Array.isArray(displays) ? displays : [];
  const wa = workAreaOf(pickDisplay(r, list));
  if (wa) {
    edgesX.push(wa.x, wa.x + wa.width);
    edgesY.push(wa.y, wa.y + wa.height);
  }

  /* 其他窗口的四条边（只取左边和上边做候选，右侧由上边组合覆盖） */
  (Array.isArray(others) ? others : []).forEach((o) => {
    if (!o) return;
    const n = normalize(o, o.id);
    edgesX.push(n.x, n.x + n.w);
    edgesY.push(n.y, n.y + n.h);
  });

  if (!edgesX.length && !edgesY.length) return r;

  /* 横向：我的左边贴某条边，或我的右边贴某条边，取绝对偏移最小且 <= px 的 */
  let bestDx = null;
  for (const e of edgesX) {
    const dxLeft = e - r.x;
    if (Math.abs(dxLeft) <= px && (bestDx === null || Math.abs(dxLeft) < Math.abs(bestDx))) {
      bestDx = dxLeft;
    }
    const dxRight = e - (r.x + r.w);
    if (Math.abs(dxRight) <= px && (bestDx === null || Math.abs(dxRight) < Math.abs(bestDx))) {
      bestDx = dxRight;
    }
  }
  if (bestDx !== null) r.x = Math.round(r.x + bestDx);

  /* 纵向同理 */
  let bestDy = null;
  for (const e of edgesY) {
    const dyTop = e - r.y;
    if (Math.abs(dyTop) <= px && (bestDy === null || Math.abs(dyTop) < Math.abs(bestDy))) {
      bestDy = dyTop;
    }
    const dyBottom = e - (r.y + r.h);
    if (Math.abs(dyBottom) <= px && (bestDy === null || Math.abs(dyBottom) < Math.abs(bestDy))) {
      bestDy = dyBottom;
    }
  }
  if (bestDy !== null) r.y = Math.round(r.y + bestDy);

  return r;
}

module.exports = {
  SNAP_PX,
  loadLayout,
  saveLayout,
  emptyLayout,
  normalize,
  clampBounds,
  toBrowserBounds,
  fromBrowserBounds,
  snapBounds,
};
