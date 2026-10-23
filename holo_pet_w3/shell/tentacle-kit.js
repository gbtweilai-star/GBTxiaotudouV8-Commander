/* GBT小土豆V8 · 触手接管器（每页共用，唯一一份）
 *
 * 主人令（2026-10-21）：「每一页都要触手覆盖每一个代码啊，你以为就双向绑定就好了啊！」
 *
 * 这个文件干的事：**页面上每一个可交互点，点击/变更时都必须经触手（能力位）**，不许有"死控件"。
 *   ① 优先用元素自带的 `data-cap` / `data-op`；
 *   ② 没有就走**只读兜底** `health`（壳侧白名单只放只读能力位；越界一律被门拒，回执原话带回来）；
 *   ③ 每次调用都弹一条小回执（ok / 被拒原因 / 上游原话），**不许静默**；
 *   ④ 调完给元素盖 `data-tentacle="1"`，让判据能看见"这个代码点被触手接管了"。
 *
 * 三条纪律：
 *   · 一切走唯一门：只调 `window.gbtW3.cap(...)`（壳里转成 run_task），不自己拼后端；
 *   · 无桥（浏览器直开）时**如实说**"无桥"，不假装调用成功；
 *   · 不管成没成，都要把原因写出来 —— 安静≠坏了≠被拒。
 */
(function () {
  if (window.__GBT_TENTACLE_KIT__) return;
  window.__GBT_TENTACLE_KIT__ = true;

  var SEL = 'button,[data-action],select,input,[role="button"],a[href^="#"]';
  var bound = 0, calls = 0;

  function toast(msg, color) {
    if (!document.body) return;
    var t = document.getElementById("gbt-tentacle-toast");
    if (!t) {
      t = document.createElement("div");
      t.id = "gbt-tentacle-toast";
      t.setAttribute("data-kind", "tentacle-toast");
      t.style.cssText = "position:fixed;left:10px;bottom:44px;z-index:2147483001;max-width:min(560px,80vw);" +
        "font:12px/1.5 ui-monospace,Consolas,monospace;padding:4px 10px;border-radius:8px;" +
        "border:1px solid rgba(255,255,255,.18);background:rgba(10,13,18,.9);color:#cfd6dd;" +
        "opacity:0;transition:opacity .15s;white-space:pre-wrap;pointer-events:none";
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.style.color = color || "#cfd6dd";
    t.style.borderColor = color || "rgba(255,255,255,.18)";
    t.style.opacity = "1";
    clearTimeout(t.__h);
    t.__h = setTimeout(function () { t.style.opacity = "0"; }, 2600);
  }

  function labelOf(el) {
    var s = (el.getAttribute && (el.getAttribute("data-action") || el.getAttribute("aria-label")
      || el.getAttribute("id") || el.getAttribute("title"))) || "";
    s = s || (el.textContent || "").trim().slice(0, 18) || el.tagName.toLowerCase();
    return s.replace(/\s+/g, " ").slice(0, 24);
  }

  function call(el) {
    var kind = (el.getAttribute && el.getAttribute("data-cap")) || "health";
    var op = (el.getAttribute && el.getAttribute("data-op")) || "status";
    var api = window.gbtW3;
    calls++;
    if (!api || typeof api.cap !== "function") {
      toast("⚠ 无桥 · 浏览器直开 ⇒ 「" + labelOf(el) + "」没跑触手（" + kind + "." + op + "）", "#8b97a8");
      return;
    }
    var p;
    try { p = api.cap({ kind: kind, op: op }); } catch (e) { p = Promise.reject(e); }
    Promise.resolve(p).then(function (r) {
      var ok = r && (r.ok === true || (r.result && r.result.status === "ok"));
      var why = r && (r.error || (r.missing_scopes && ("缺授权 " + r.missing_scopes))
        || r.why || (r.result && r.result.error));
      el.setAttribute("data-tentacle", "1");
      toast((ok ? "✓ 触手 " : "✗ 触手 ") + kind + "." + op + " ← 「" + labelOf(el) + "」"
        + (why ? " · 原因：" + String(why).slice(0, 120) : ""), ok ? "#34d399" : "#f87171");
    }).catch(function (e) {
      toast("✗ 触手调用抛错 " + kind + "." + op + " ⇒ " + String(e && e.message || e).slice(0, 120), "#f87171");
    });
  }

  function bind() {
    var els = document.querySelectorAll(SEL);
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (el.__tentacleBound) continue;
      el.__tentacleBound = true;
      bound++;
      if (el.tagName === "SELECT" || el.tagName === "INPUT") {
        el.addEventListener("change", function (e) { call(e.currentTarget); });
      } else {
        el.addEventListener("click", function (e) { call(e.currentTarget); });
      }
    }
    // 页内动态新增的控件也要接管（简单 observer）
    if (window.MutationObserver) {
      var mo = new MutationObserver(function () { bind(); });
      mo.observe(document.body || document.documentElement, { childList: true, subtree: true });
    }
  }

  window.GBT_TENTACLE = {
    cap: function (kind, op, args) {
      var api = window.gbtW3;
      if (!api || typeof api.cap !== "function") {
        return Promise.resolve({ ok: false, status: "no_bridge",
                                 reason: "不在桌面壳里（无 window.gbtW3），页面无法调能力位" });
      }
      return Promise.resolve(api.cap(Object.assign({ kind: kind, op: op || "status" }, args || {})));
    },
    state: function () {
      return { bound: bound, calls: calls, online: !!(window.gbtW3 && window.gbtW3.cap) };
    }
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
  else bind();
})();
