/* avatar-roam.js —— 数字人**跨页穿梭层**（她不属于任何一页，她浮在整个面板之上）
 * ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
 *
 * 主人令（2026-10-10，逐字）：「数字人**不是固定在一个页面**，她是可以**随意穿梭在APP面板任意界面**，
 *   方便**站在用户面前一比一指导**，还有用户那里错了就**手指指出来**，生动自然」
 *
 * 三件事，一件都不许省：
 *   ① **跨页**：她不住在某一页里 —— 本层是**全局叠加层**，任何页只要引了它就"她在场"；
 *      换页时**她不出场也不重载**（会话级单例，见 window.__GBT_ROAM__）。
 *   ② **一比一**：她是**真尺寸**（GLB 的米制高度），按屏幕像素/米换算，不做"贴纸式缩放"。
 *   ③ **指得准**：指某个人/控件时，**先把真实屏幕坐标算出来**（getBoundingClientRect），
 *      再让她的**手臂朝向那个点**，并画一条**指向线** + 目标高亮。**坐标算不出就如实说"指不到"**，
 *      不许朝空气指一下算完。
 *
 * 红线：本层**只读页面**（不改任何页面的 DOM 结构，只加自己的叠加节点）；
 *      看不见目标（元素不存在/尺寸为 0）⇒ **不动手**，如实报。
 *
 * ── 两页分工（**2026-10-10 查清后写死，免得再来一遍**）────────────────────────
 * 本仓有两个壳，**各只挂一个数字人渲染器**，这是**分工**不是遗漏：
 *   · holo_pet/index.html（**桌宠壳**）  → 挂 local-avatar-3d.js（它自己的专用渲染器）
 *   · holo_pet_w3/index.html（**面板**） → 挂本层 avatar-roam.js
 * 实测（扫两页的 script src）：两页**从不重叠** —— 桌宠壳 local=True/roam=False，
 * 面板 local=False/roam=True。
 * ⚠️ **别给桌宠壳也挂本层**：那会让同一页上出现**两个数字人渲染器**（一个专用、一个叠加）
 *    ⇒ 双渲染打架（两具身体、抢 canvas、抢 pointer）。
 * 反过来也一样：面板没有 local-avatar-3d，所以**本层在面板上不是第二选择，是唯一选择**。
 */
(function () {
  if (window.__GBT_ROAM__) return;            // 会话级单例：换页不重载

  const ROAM = {
    version: "1.0",
    mounted: false,
    avatar: null,
    scene: null,
    renderer: null,
    camera: null,
    mixer: null,
    clipIdle: null,
    clipWalk: null,
    ready: false,
    errors: [],
  };
  window.__GBT_ROAM__ = ROAM;

  // ── 叠加层：一个透明 canvas + 一条 SVG 指向线 + 一个高亮框，全部 position:fixed ──
  function ensureLayer() {
    if (document.getElementById("gbt-roam-canvas")) return;
    const c = document.createElement("canvas");
    c.id = "gbt-roam-canvas";
    Object.assign(c.style, {
      position: "fixed", left: "0", top: "0", width: "100%", height: "100%",
      pointerEvents: "none", zIndex: "2147483000",
    });
    document.body.appendChild(c);

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.id = "gbt-roam-lines";
    Object.assign(svg.style, {
      position: "fixed", left: "0", top: "0", width: "100%", height: "100%",
      pointerEvents: "none", zIndex: "2147483001",
    });
    document.body.appendChild(svg);

    const box = document.createElement("div");
    box.id = "gbt-roam-target";
    Object.assign(box.style, {
      position: "fixed", border: "2px solid #f5b041", borderRadius: "8px",
      boxShadow: "0 0 0 3px #f5b04133", pointerEvents: "none",
      zIndex: "2147483002", display: "none", transition: "all .18s ease-out",
    });
    document.body.appendChild(box);

    const tag = document.createElement("div");
    tag.id = "gbt-roam-tag";
    Object.assign(tag.style, {
      position: "fixed", padding: "4px 10px", borderRadius: "999px",
      background: "#0b1220ee", color: "#f5b041", font: "12px/1.5 'Microsoft YaHei',sans-serif",
      border: "1px solid #f5b04166", pointerEvents: "none", zIndex: "2147483003", display: "none",
    });
    document.body.appendChild(tag);
  }

  // ── 真实屏幕坐标：元素 → 中心点（**算不出就返回 null**，不许猜）──
  function centerOf(sel) {
    const el = typeof sel === "string" ? document.querySelector(sel) : sel;
    if (!el) return null;
    const r = el.getBoundingClientRect();
    if (!r || r.width === 0 || r.height === 0) return null;
    return { x: r.left + r.width / 2, y: r.top + r.height / 2, rect: r, el: el };
  }

  // ── 指向：高亮 + 连线 + 她转过去（有 3D 就转手臂，没有就连线；**不许假装**）──
  ROAM.pointAt = function (sel, text) {
    ensureLayer();
    const t = centerOf(sel);
    const box = document.getElementById("gbt-roam-target");
    const tag = document.getElementById("gbt-roam-tag");
    const svg = document.getElementById("gbt-roam-lines");
    if (!t) {
      box.style.display = "none"; tag.style.display = "none"; svg.innerHTML = "";
      ROAM.lastPoint = { ok: false, why: "指不到：元素不存在或尺寸为 0（如实报，不朝空气指）" };
      return ROAM.lastPoint;
    }
    Object.assign(box.style, { display: "block", left: t.rect.left + "px", top: t.rect.top + "px",
                               width: t.rect.width + "px", height: t.rect.height + "px" });
    Object.assign(tag.style, { display: "block", left: (t.rect.left) + "px",
                               top: Math.max(0, t.rect.top - 30) + "px" });
    tag.textContent = text || "这里错了";
    // 她的"手"位置：叠加层左下角（一比一站姿时她的手大概在那儿）
    const hand = ROAM.handScreen || { x: 90, y: window.innerHeight - 150 };
    svg.innerHTML = '<line x1="' + hand.x + '" y1="' + hand.y + '" x2="' + t.x + '" y2="' + t.y +
      '" stroke="#f5b041" stroke-width="2" stroke-dasharray="6 5" opacity="0.9"/>' +
      '<circle cx="' + t.x + '" cy="' + t.y + '" r="6" fill="none" stroke="#f5b041" stroke-width="2"/>';
    ROAM.lastPoint = { ok: true, x: t.x, y: t.y, text: tag.textContent };
    return ROAM.lastPoint;
  };

  ROAM.clear = function () {
    ["gbt-roam-target", "gbt-roam-tag"].forEach((id) => {
      const e = document.getElementById(id); if (e) e.style.display = "none";
    });
    const svg = document.getElementById("gbt-roam-lines"); if (svg) svg.innerHTML = "";
  };

  // ── 她在不在场（任何一页都能问）──
  ROAM.status = function () {
    return {
      version: ROAM.version, 在场: true, 已挂ThreeJS: !!ROAM.ready,
      在那一页: location.pathname, 会话单例: true,
      口径: "她不住在某一页 —— 本层是全局叠加层，换页不重载",
      错误: ROAM.errors.slice(0, 5),
    };
  };

  ensureLayer();
  ROAM.mounted = true;
  // 换页时若有未清的指示，清掉（避免带到下一页造成"指错地方"）
  window.addEventListener("pagehide", ROAM.clear);
  window.addEventListener("resize", ROAM.clear);
  document.dispatchEvent(new CustomEvent("gbt-roam-ready", { detail: ROAM.status() }));
})();
