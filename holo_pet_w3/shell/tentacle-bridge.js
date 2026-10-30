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

    /* 2026-10-30：不再只测 health —— 那只能证明"桥在"，证明不了"这一页能打通它自己那一域"。
       做法：按页面归属的域，挑该域一个**免票免参数**的位去调（映射表由 caps_registry 现算生成）。
       三种结果要分开，判决才准：
         · 门没通（连 JSON 都没拿到）        → 页面调不到能力位
         · 门通了但该位自身报错              → 域内该位不可用（不是接线问题）
         · 都 OK                             → 穿透 ok（附域与耗时） */
    function bridgeBase() {
      return (window.gbtW3 && window.gbtW3.bridge) || "http://127.0.0.1:8791";
    }
    function domainOf() {
      var d = (document.documentElement.dataset || {}).gbtDomain || (document.body && document.body.dataset || {}).gbtDomain;
      if (d) return d;
      var p = location.pathname;
      if (/model-chat|wgpu\//.test(p)) return "llm";
      if (/voice-theater|digital-human/.test(p)) return "voice";
      if (/panel/.test(p)) return "system";
      if (/kernel/.test(p)) return "mind";
      return "system";
    }
    function report() {
      var dom = domainOf();
      var t0 = performance.now();
      /* 必须用**绝对路径**：相对路径会跟着页面所在目录走
         （/holo_pet_w3/model-chat/shell/... 直接 404 ⇒ 映射表拿不到，永远退回 health）。 */
      fetch("/holo_pet_w3/shell/page-domain-caps.json", { cache: "no-store" })
        .then(function (r) { return r.ok ? r.json() : {}; })
        .catch(function () { return {}; })
        .then(function (map) {
          var cap = (map && map[dom]) || "health";
          /* 功能探针：页面可以自己声明 window.GBT_FUNC_PROBE = async () => ({name, ok, evidence})
             用来证明"这一页的活真的发生过"（拿到了真数据 / 真出了声 / 真答了话），
             而不只是"接线通"。没声明就跳过，不当成失败。 */
          var funcP = (typeof window.GBT_FUNC_PROBE === "function")
            ? Promise.resolve().then(window.GBT_FUNC_PROBE).catch(function (e) {
                return { name: "func", ok: false, evidence: String(e && e.message || e).slice(0, 60) };
              })
            : Promise.resolve(null);
          return Promise.all([funcP, window.gbtW3.cap(cap, {})]).then(function (pair) {
            var fr = pair[0], res = pair[1];
            var reached = !!(res && res.cap);
            var rd = {
              cap_domain: dom, cap_name: cap, cap_reached: reached,
              cap_ok: !!(res && res.ok),
              cap_ms: Math.round(performance.now() - t0),
              cap_python: (res && res.result && res.result.python) || null,
              cap_err: (res && res.error && res.error.message) || null
            };
            if (fr) {
              rd.func_name = fr.name || "func";
              rd.func_ok = !!fr.ok;
              rd.func_evidence = String(fr.evidence || "").slice(0, 120);
            }
            return {
              page: (location.pathname || "").replace(/^\//, ""),
              ok: !!(res && res.ok) && (!fr || !!fr.ok),
              readings: rd
            };
          });
        })
        .then(function (payload) {
          return fetch(bridgeBase() + "/_probe", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
          });
        })
        .catch(function (e) {
          try {
            fetch(bridgeBase() + "/_probe", {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ page: (location.pathname || "").replace(/^\//, ""),
                ok: false, readings: { cap_reached: false,
                  cap_err: String(e && e.message || e).slice(0, 80) } })
            });
          } catch (e2) { /* 桥也不在：页面照常可用，只是没账 */ }
        });
    }
    if (document.readyState === "complete") setTimeout(report, 1200);
    else window.addEventListener("load", function () { setTimeout(report, 1200); });
  })();
