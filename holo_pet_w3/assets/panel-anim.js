/* 面板入场动效（GSAP）—— GBT小土豆V8
 *
 * 口径（2026-11-01 主人：「APP 面板真闹心，动效做起来」）：
 *  · 只动 transform/opacity（合成层，60fps）；
 *  · 尊重 prefers-reduced-motion：用户要静止就不动，并如实记 data-anim="skipped"；
 *  · 不猜结构：优先 [data-anim] 元素；没有就取 main/.wrap/.grid 的直接子元素；再兜底 body 直接子元素；
 *  · 结果可验证：完成后 document.documentElement.dataset.anim = "done"（配合 headless 截图/DOM 断言）；
 *  · gsap 没加载就如实标 failed，不做假动画。
 */
(function () {
  var root = document.documentElement;
  var api = { done: false, count: 0, mode: null, reason: "" };
  window.__panelAnim = api;

  var reduce = false;
  try {
    reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch (e) {}

  if (reduce) {
    root.dataset.anim = "skipped";
    api.mode = "skipped";
    api.reason = "prefers-reduced-motion";
    return;
  }
  if (!window.gsap) {
    root.dataset.anim = "failed";
    api.mode = "failed";
    api.reason = "gsap 未加载";
    return;
  }

  function pick() {
    var explicit = Array.prototype.slice.call(document.querySelectorAll("[data-anim]"));
    if (explicit.length) return explicit;
    var hosts = document.querySelectorAll("main, .wrap, .grid, .cards, .panel-body, #app, #content");
    var out = [];
    Array.prototype.forEach.call(hosts, function (h) {
      var kids = Array.prototype.slice.call(h.children);
      if (kids.length) out = out.concat(kids);
    });
    if (out.length) return out;
    return Array.prototype.slice.call(document.body.children).filter(function (el) {
      var t = el.tagName;
      return t !== "SCRIPT" && t !== "STYLE" && t !== "LINK" && t !== "NOSCRIPT";
    });
  }

  var targets = pick().slice(0, 24);
  if (!targets.length) {
    root.dataset.anim = "empty";
    api.mode = "empty";
    return;
  }
  api.count = targets.length;
  api.mode = "gsap";
  // 同步标记"已接线"（rAF 在下拉 DOM/无渲染时可能不跳，所以完成态另标；这两个标记让巡检能区分"没接线"和"没跑完"）
  root.dataset.anim = "started";
  root.dataset.animCount = String(targets.length);

  var tl = window.gsap.timeline({
    defaults: { duration: 0.4, ease: "power2.out" },
    onComplete: function () {
      api.done = true;
      root.dataset.anim = "done";
    }
  });
  tl.from(targets, { y: 14, opacity: 0, stagger: 0.03, clearProps: "transform,opacity" });

  // 超时兜底：2.5s 还没完成就如实标 timeout，不假装 done
  window.setTimeout(function () {
    if (!api.done && root.dataset.anim !== "done") {
      root.dataset.anim = "timeout";
      api.reason = "timeline 未在 2.5s 内完成";
    }
  }, 2500);
})();
