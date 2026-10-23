/* 生成后端 · 轮询池读数（第 58 轮）
 *
 * 数据从哪来：`state/genpool.json` → 由 `brain-feed.py` 带进 `brain-data.js` 的 `genpool` 块。
 * **本页一个请求都不发**（CSP 是 `connect-src 'none'`，fetch 必被拒），只读那份已经内嵌的数据 ——
 * 这与本窗既有的做法一致（`brain-data.js` 靠同源 `<script>` 重注入拿新快照）。
 *
 * 为什么要有这一块：这条链原来只活在命令行里（`genrouter.py --list`），
 * 主人在面板上看不见"几条腿可用、今天出了几张、谁在等凭据"。**看不见的能力等于没有。**
 *
 * 口径（写死，别改成好看的样子）：
 *   · 可用 / 等凭据 / 未验 **分开列**，不合并成"共 10 条腿"糊过去；
 *   · 缺什么就写什么（`缺 CLOUDFLARE_API_TOKEN`）—— 那是主人下一步要补的东西；
 *   · 云后端**不占本地磁盘**这件事写在脚注里（主人问过一次"10 个是不是 50GB"）。
 */
(function () {
  "use strict";

  var POLL_MS = 5000;

  function $(id) { return document.getElementById(id); }

  function row(k, v, state) {
    var d = document.createElement("div");
    d.className = "iv-row" + (state ? " iv-" + state : "");
    var a = document.createElement("span");
    a.className = "iv-k";
    a.textContent = k;
    var b = document.createElement("span");
    b.className = "iv-v";
    b.textContent = v;
    d.appendChild(a);
    d.appendChild(b);
    return d;
  }

  function render() {
    var el = $("rail-genpool");
    if (!el) return;
    var D = globalThis.GBT_BRAIN || {};
    var g = D.genpool;
    if (!g) {
      /* 取不到就**如实说取不到**（口径件还没生成），不编一个假的池子 */
      el.replaceChildren(row("轮询池", "口径件还没生成（跑一次 genrouter.py 就会写 state/genpool.json）", "wait"));
      return;
    }
    var kids = [];
    kids.push(row("池子", g.pool_size + " 条腿 · 可用 " + g.usable + " · 等凭据 " + g.waiting));
    kids.push(row("今日调用", String(g.calls_today_total == null ? "—" : g.calls_today_total)));

    (g.pool || []).forEach(function (p) {
      var st = p.status === "可用" ? "ok" : (p.status === "冷却中" ? "wait" : "wait");
      var tail = p.missing && p.missing.length ? ("缺 " + p.missing.join("、"))
                                              : (p.is_local ? "本机 · 真无限" : (p.free || ""));
      kids.push(row(p.is_local ? "本机" : p.id.replace(/_/g, " ").slice(0, 14), tail, st));
    });

    if (g.calls_today && Object.keys(g.calls_today).length) {
      var s = Object.keys(g.calls_today).map(function (k) {
        return k + " × " + g.calls_today[k];
      }).join(" · ");
      kids.push(row("今日明细", s));
    }
    kids.push(row("口径", "云后端不占本地磁盘 · 同一家多账号不算多条腿 · 未验的不参与路由"));
    kids.push(row("快照", String(g.at || "—")));
    el.replaceChildren.apply(el, kids);
  }

  function boot() {
    render();
    setInterval(render, POLL_MS);      /* brain.js 每 15s 重注入快照，这里跟着刷新 */
    /* 只读自述：验收要能**量**这一块起没起来，不靠看图说"有" */
    window.__brainGenpool = { poll_ms: POLL_MS, has_data: function () {
      return !!(globalThis.GBT_BRAIN && globalThis.GBT_BRAIN.genpool);
    } };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
