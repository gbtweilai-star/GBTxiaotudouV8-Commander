/* 触手引导器（2026-10-30 · 按需激活）
 *
 * 为什么要有它：原来每页都**同步阻塞**引 tentacle-bridge.js + tentacle-kit.js（约 37KB），
 * 首页渲染被这两个下载挡住；而且绝大多数页压根不会调能力位 —— 这就是"没做到按需激活"。
 *
 * 现在：立即放一个**代理 gbtW3**（调用先排队，语义与真件一致），
 * 真件在空闲/首次真实调用时才加载。页面代码一行都不用改。
 */
(function () {
  if (window.__GBT_BOOT__) return;
  window.__GBT_BOOT__ = { loaded: false, queued: 0, at: Date.now() };

  var BASE = (function () {
    // 从本文件的 src 推出 shell/ 目录（页面在各层子目录里，相对路径不可靠）
    var s = document.currentScript && document.currentScript.src;
    if (!s) {
      var all = document.getElementsByTagName("script");
      for (var i = all.length - 1; i >= 0; i--) {
        if (/tentacle-boot\.js/.test(all[i].src || "")) { s = all[i].src; break; }
      }
    }
    return s ? s.replace(/tentacle-boot\.js.*$/, "") : "/holo_pet_w3/shell/";
  })();

  var pending = [];
  var real = null;

  function load(cb) {
    if (real) return cb && cb();
    var n = 0, done = function () { if (++n === 2) { real = window.gbtW3 || null; cb && cb(); } };
    ["tentacle-bridge.js", "tentacle-kit.js"].forEach(function (f) {
      var e = document.createElement("script");
      e.src = BASE + f + "?v=20261030b";
      e.onload = done;
      e.onerror = done;
      document.head.appendChild(e);
    });
  }

  // 代理：调用先排队，真件就绪后按序补发
  function flush() {
    var q = pending.splice(0, pending.length);
    for (var i = 0; i < q.length; i++) {
      try { q[i](); } catch (e) {}
    }
    window.__GBT_BOOT__.loaded = !!window.gbtW3;
  }

  var proxy = {
    _queued: true,
    status: function () { return { pending: pending.length, loaded: !!window.gbtW3, base: BASE }; },
    cap: function () {
      var a = arguments;
      if (window.gbtW3 && window.gbtW3.cap) return window.gbtW3.cap.apply(window.gbtW3, a);
      return new Promise(function (res, rej) {
        pending.push(function () {
          try { window.gbtW3.cap.apply(window.gbtW3, a).then(res, rej); } catch (e) { rej(e); }
        });
        schedule();
      });
    },
    toast: function () {
      var a = arguments;
      if (window.gbtW3 && window.gbtW3.toast) return window.gbtW3.toast.apply(window.gbtW3, a);
      pending.push(function () { try { window.gbtW3.toast.apply(window.gbtW3, a); } catch (e) {} });
      schedule();
    }
  };

  if (!window.gbtW3) window.gbtW3 = proxy;

  var scheduled = false;
  function schedule() {
    if (scheduled || real) return;
    scheduled = true;
    var run = function () { load(flush); };
    if (window.requestIdleCallback) requestIdleCallback(run, { timeout: 2500 });
    else setTimeout(run, 1200);
  }

  // 空闲时预加载（不阻塞首屏）；也可以等第一次真实调用
  if (document.readyState === "complete") schedule();
  else window.addEventListener("load", schedule);
})();
