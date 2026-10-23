/* GBT小土豆V8 · 上帝视角 · 布局纯逻辑（W3）
 *
 * 这一层**刻意不 require("electron")**：布局的越界回落与吸附是可以离线复算的纯函数，
 * 所以布局探针（`.scratch/w3_layout_probe.py`）能脱离 Electron 直接验它。
 * 主进程 `main.cjs` 只是调用方。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";

const fs = require("fs");
const path = require("path");

const MIN_VISIBLE = 40;      /* 至少要有 40×40 落在某块屏里，才算"看得见" */
const SNAP_PX = 12;          /* §2.2：距屏幕或其他 GBT 窗口边缘 ≤ 12px 即吸附 */
const LAYOUT_VERSION = 1;

function defaultEntry(id) {
  return { id: id, x: 120, y: 80, w: 1120, h: 720, visible: true };
}

function normalize(entry, id) {
  const d = defaultEntry(id);
  const src = entry && typeof entry === "object" ? entry : {};
  const num = (v, fallback) => (Number.isFinite(Number(v)) ? Math.round(Number(v)) : fallback);
  return {
    id: id,
    x: num(src.x, d.x),
    y: num(src.y, d.y),
    w: Math.max(320, num(src.w, d.w)),
    h: Math.max(240, num(src.h, d.h)),
    visible: src.visible === undefined ? true : Boolean(src.visible),
  };
}

function emptyLayout() {
  return { version: LAYOUT_VERSION, windows: {} };
}

function loadLayout(file) {
  try {
    const parsed = JSON.parse(fs.readFileSync(file, "utf8"));
    if (parsed && typeof parsed === "object" && parsed.windows) return parsed;
  } catch (err) {
    /* 首次运行 / 文件坏了 → 回落到空布局，不抛 */
  }
  return emptyLayout();
}

function saveLayout(file, layout) {
  const dir = path.dirname(file);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(file, JSON.stringify(layout, null, 2), "utf8");
  return file;
}

function rectsOf(displays) {
  const list = Array.isArray(displays) ? displays : [];
  const out = [];
  list.forEach((d) => {
    if (!d) return;
    const a = d.workArea || d.bounds || d;
    if (!a) return;
    const x = Number(a.x) || 0;
    const y = Number(a.y) || 0;
    const width = Number(a.width) || 0;
    const height = Number(a.height) || 0;
    if (width > 0 && height > 0) out.push({ x, y, width, height });
  });
  return out;
}

function intersects(b, d) {
  const ix = Math.min(b.x + b.w, d.x + d.width) - Math.max(b.x, d.x);
  const iy = Math.min(b.y + b.h, d.y + d.height) - Math.max(b.y, d.y);
  return ix >= MIN_VISIBLE && iy >= MIN_VISIBLE;
}

/** 越界回落：只要有一块屏看得见就原样返回；全看不见 → 回主屏，**尺寸不变**。 */
function clampBounds(bounds, displays) {
  const b = normalize(bounds, (bounds && bounds.id) || "win");
  const rects = rectsOf(displays);
  if (!rects.length) return b;
  if (rects.some((d) => intersects(b, d))) return b;
  const p = rects[0];
  return { id: b.id, x: p.x + 24, y: p.y + 24, w: b.w, h: b.h, visible: b.visible };
}

function snapValue(v, targets, snapPx) {
  for (let i = 0; i < targets.length; i++) {
    if (Math.abs(v - targets[i]) <= snapPx) return targets[i];
  }
  return v;
}

/** 吸附：先吸屏幕边缘，再吸其他 GBT 窗口边缘。只在 moved 事件里算。 */
function snapBounds(bounds, displays, others, snapPx) {
  const b = normalize(bounds, (bounds && bounds.id) || "win");
  const px = Number.isFinite(snapPx) ? snapPx : SNAP_PX;
  const rects = rectsOf(displays);
  const xs = [];
  const ys = [];
  rects.forEach((d) => { xs.push(d.x, d.x + d.width - b.w); ys.push(d.y, d.y + d.height - b.h); });
  (Array.isArray(others) ? others : []).forEach((o) => {
    if (!o) return;
    if (Number.isFinite(o.x)) xs.push(o.x, o.x + (Number(o.w) || 0));
    if (Number.isFinite(o.y)) ys.push(o.y, o.y + (Number(o.h) || 0));
  });
  return Object.assign({}, b, {
    x: snapValue(b.x, xs, px),
    y: snapValue(b.y, ys, px),
  });
}

function toBrowserBounds(b) {
  return { x: b.x, y: b.y, width: b.w, height: b.h };
}

function fromBrowserBounds(b, id, visible) {
  return { id: id, x: b.x, y: b.y, w: b.width, h: b.height, visible: visible === undefined ? true : visible };
}

module.exports = {
  MIN_VISIBLE, SNAP_PX, LAYOUT_VERSION,
  defaultEntry, emptyLayout, loadLayout, saveLayout,
  clampBounds, snapBounds, toBrowserBounds, fromBrowserBounds, normalize,
};
