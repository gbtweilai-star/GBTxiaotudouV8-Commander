/* GBT小土豆V8 · 网页壳填充（补上 Safari 里缺的 window.gbtW3）
 *
 * 主人令（2026-10-21 / 2026-10-29）：
 *   「所有的代码页面都要使用触手双向绑定，每一页都要使用触手覆盖每一个代码」
 *
 * ## 为什么需要这个文件
 *   tentacle-kit.js 的设计是对的：**每个可交互点都必须经触手（能力位），不许有死控件**。
 *   但它只认 `window.gbtW3.cap(...)` —— 那个对象**只有 Electron 壳里才有**。
 *   在 Safari / 浏览器直开时它是 undefined ⇒ kit 只能报「无桥」⇒ 页面等于没接触手。
 *   实测：28 个活页面里 20 个连 kit 都没引；引了的那些在 Safari 里也全是「无桥」。
 *
 * ## 这个文件干两件事
 *   ① 提供 `window.gbtW3`：cap() / toast() / status()
 *      cap 走桥的 `POST /_cap` ⇒ 桥里转成 run_task ⇒ **门照跑、权限照判**，页面零凭据。
 *   ② **报到**：页面一加载就 POST /_tentacle/hello，证明"这一页真活着、真接了触手"。
 *      有报到 ⇒ 覆盖清单里能看见；看不见 ⇒ 就是打不通，不再靠猜。
 *
 * ## 三条纪律（与 kit 一致）
 *   · 只经桥，不自己拼后端；
 *   · 无桥时**如实说无桥**，不假装调用成功；
 *   · 不管成没成，原因都要写出来 —— 安静≠坏了≠被拒。
 */
(function () {
  if (window.__GBT_WEB_SHELL__) return;
  window.__GBT_WEB_SHELL__ = true;

  var ORIGIN = (location.origin && location.origin !== "null")
    ? location.origin : "http://127.0.0.1:8080";
  // 桥默认 8791；页面用 ?bridge=8792 之类可改
  var m = /[?&]bridge=(\d+)/.exec(location.search);
  var BR = "http://127.0.0.1:" + (m ? m[1] : "8791");

  var stats = { calls: 0, ok: 0, fail: 0, last: null };

  function pageName() {
    var p = location.pathname.replace(/^\/+/, "");
    return p || "index.html";
  }

  function toast(msg, color) {
    var t = document.getElementById("gbt-tentacle-toast");
    if (!t) {
      if (!document.body) return;
      t = document.createElement("div");
      t.id = "gbt-tentacle-toast";
      t.style.cssText = "position:fixed;left:10px;bottom:44px;z-index:2147483001;" +
        "max-width:min(560px,80vw);font:12px/1.5 ui-monospace,Consolas,monospace;" +
        "padding:4px 10px;border-radius:8px;border:1px solid rgba(255,255,255,.18);" +
        "background:rgba(10,13,18,.92);color:#cfd6dd;opacity:0;transition:opacity .15s;" +
        "white-space:pre-wrap;pointer-events:none";
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.style.color = color || "#cfd6dd";
    t.style.borderColor = color || "rgba(255,255,255,.18)";
    t.style.opacity = "1";
    clearTimeout(t.__h);
    t.__h = setTimeout(function () { t.style.opacity = "0"; }, 2800);
  }

  function cap(name, payload) {
    stats.calls++;
    var body = JSON.stringify({ cap: name, payload: payload || {} });
    return fetch(BR + "/_cap", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: body
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d && d.ok) { stats.ok++; } else { stats.fail++; }
      stats.last = d;
      return d;
    }).catch(function (e) {
      stats.fail++;
      stats.last = { ok: false, error: { message: "无桥：" + String(e).slice(0, 60) } };
      return stats.last;
    });
  }

  window.gbtW3 = {
    cap: cap,
    toast: toast,
    status: function () {
      return { bridge: BR, page: pageName(), stats: stats,
               kit: !!window.__GBT_TENTACLE_KIT__ };
    },
    bridge: BR
  };

  // 报到：让覆盖清单看得见这一页
  window.addEventListener("load", function () {
    setTimeout(function () {
      var n = 0;
      try {
        n = document.querySelectorAll(
          'button,[data-action],select,input,[role="button"]').length;
      } catch (e) { n = -1; }
      fetch(BR + "/_tentacle/hello", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ page: pageName(), kit: !!window.__GBT_TENTACLE_KIT__,
                               controls: n })
      }).catch(function () { /* 无桥就安静：页面自己会显示"无桥" */ });
    }, 600);
  });
})();
  /* ── 统一自证（2026-10-30）──────────────────────────────────────────
     为什么放在壳里：401 个页面各自实现一遍既重复又会走偏。
     只要页面带 ?_probe=1 打开，就由壳替它做两件事：
       ① 真调一次能力位（走 /_cap → run_task），证明"本页真能穿透到执行层"
       ② 把证据 POST 给桥 /_probe，落 state/page_probes.jsonl
     不带 ?_probe=1 时**完全零开销**（连这个函数都不会执行）。 */
  (function autoProbe() {
    if (!/[?&]_probe=1/.test(location.search)) return;
    function bridgeBase() {
      // ⚠️ 本段在 IIFE 之外，`BR` 不可见（踩过：ReferenceError 被 catch 吞掉，自报永远不发生）
      return (window.gbtW3 && window.gbtW3.bridge) || "http://127.0.0.1:8791";
    }
    function report() {
      var t0 = performance.now();
      var BR2 = bridgeBase();
      window.gbtW3.cap("health", {}).then(function (r) {
        var payload = {
          page: (location.pathname || "").replace(/^\//, ""),
          ok: !!(r && r.ok),
          readings: {
            cap_ok: !!(r && r.ok),
            cap_ms: Math.round(performance.now() - t0),
            cap_python: (r && r.result && r.result.python) || null
          }
        };
        return fetch(BR2 + "/_probe", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
      }).catch(function (e) {
        try {
          fetch(bridgeBase() + "/_probe", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ page: (location.pathname || "").replace(/^\//, ""),
              ok: false, readings: { cap_ok: false, cap_err: String(e && e.message || e).slice(0, 80) } })
          });
        } catch (e2) { /* 桥也不在，就什么都不做（页面照常可用） */ }
      });
    }
    if (document.readyState === "complete") setTimeout(report, 1200);
    else window.addEventListener("load", function () { setTimeout(report, 1200); });
  })();
