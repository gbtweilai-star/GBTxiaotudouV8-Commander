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
  /* ── 主动性运行时（2026-10-30 · 照 dsh-pet 的调度模型）───────────────
     她要"不等指令"：心跳在线 → 定时取话 → 气泡说出来；空闲久了自己也找话说。
     一条规矩照抄 dsh-pet：**一次只让一只宠物说**，气泡 15 秒。 */
  (function proactive() {
    var B = null, bubble = null, bubbleTimer = null, idleTimer = null;
    var lastUser = Date.now(), said = 0;

    function base() { return (window.gbtW3 && window.gbtW3.bridge) || "http://127.0.0.1:8791"; }

    function show(text, secs) {
      if (!text) return;
      if (!bubble) {
        bubble = document.createElement("div");
        bubble.id = "__gbt_bubble";
        bubble.style.cssText = "position:fixed;left:50%;bottom:96px;transform:translateX(-50%);" +
          "max-width:74vw;padding:10px 14px;border-radius:14px;background:rgba(10,16,28,.94);" +
          "color:#cfe9ff;font:13px/1.6 system-ui,-apple-system,sans-serif;z-index:2147483000;" +
          "border:1px solid rgba(0,229,255,.35);box-shadow:0 8px 28px rgba(0,0,0,.45);" +
          "opacity:0;transition:opacity .25s";
        document.body.appendChild(bubble);
      }
      bubble.textContent = text;
      bubble.style.opacity = "1";
      clearTimeout(bubbleTimer);
      bubbleTimer = setTimeout(function () { bubble.style.opacity = "0"; }, (secs || 15) * 1000);
    }

    function post(path, body) {
      return fetch(base() + path, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {})
      }).then(function (r) { return r.json(); }).catch(function () { return null; });
    }

    function beat() {
      post("/_proactive/heartbeat", { surface: "web" }).then(function (d) {
        if (d && d.sleep) return;                        // 睡着时安静
        post("/_proactive/tick", {}).then(function () {
          /* pull 也走 POST：桥的路由表里 /_proactive 只收 POST（GET 会被判 no route） */
          return post("/_proactive/pull", { limit: 1 });
        }).then(function (d) {
          var it = d && d.items && d.items[0];
          if (it) { show(it.text, it.bubble_s || 15); said += 1; window.__gbt_said = said; }
        }).catch(function () {});
      });
    }

    // 每 30 秒一次心跳（tick 内部自己按密度决定说不说，页面不判断）
    setInterval(beat, 30000);
    setTimeout(beat, 1500);

    // 空闲自言自语：3 分钟没动 → 冒一句；之后每 5 分钟一句（不刷屏）
    function markActive() { lastUser = Date.now(); }
    ["pointerdown", "keydown", "wheel", "touchstart"].forEach(function (e) {
      window.addEventListener(e, markActive, { passive: true });
    });
    idleTimer = setInterval(function () {
      if (Date.now() - lastUser < 180000) return;
      if (window.__gbt_idleSaid && Date.now() - window.__gbt_idleSaid < 300000) return;
      window.__gbt_idleSaid = Date.now();
      var pool = ["……我在这儿", "要不要我巡一圈？", "今天的账我还没对完", "主人，喝口水"];
      show(pool[Math.floor(Math.random() * pool.length)], 12);
    }, 60000);

    window.__gbt_proactive = {
      said: function () { return said; },
      poke: beat,
      sleep: function (on) { return post("/_proactive/sleep", { on: !!on }); }
    };
  })();
