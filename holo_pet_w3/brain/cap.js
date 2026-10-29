/* GBT小土豆V8 · 单项能力独立页 · 渲染器
 *
 * 一页一条能力。`<body class="cap-page" data-kind="<kind>">` 由生成器写死；
 * 本脚本从 `brain-data.js`（真数据）里把这一条**连同它的真实连接**渲染出来。
 *
 * 纪律与主窗一致：颜色从 CSS token 读、不写色号；缺数据就如实说缺；
 * 不用 `Math.random`、不编调用史。经典脚本（`file://` 下 ESM 走不通）。
 */
(function () {
  "use strict";
  const D = globalThis.GBT_BRAIN;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  if (!D) {
    document.body.innerHTML = '<div class="cap-body"><p class="empty"><b>数据脚本没加载</b> —— ' +
      '先跑 py -3.14 tools/codex-scripts/brain-feed.py --out holo_pet_w3/brain/brain-data.js</p></div>';
    return;
  }

  const kind = document.body.dataset.kind || "";
  /* 生成出来的独立页在 `caps/` 下，模板页在 `brain/` 下 —— 链接前缀必须**按实际路径算**，
     写死一个就会有一半页面点不开（这类"看着对、点开 404"最容易漏）。 */
  const IN_CAPS = /\/caps\//.test(location.pathname);
  const CAP = (k) => (IN_CAPS ? "./" : "caps/") + encodeURIComponent(k) + ".html";
  const HOME = IN_CAPS ? "../../index.html" : "index.html";
  const nodes = D.nodes || [];
  const me = nodes.find((n) => n.id === kind) || null;
  const bundles = D.bundles || [];
  const bundle = me && me.bundle ? bundles.find((b) => b.id === me.bundle) : null;

  /* ── 真实连接：出边 / 入边 / 同束 ── */
  const edges = D.edges || [];
  const out = edges.filter((e) => e.a === kind);
  const inn = edges.filter((e) => e.b === kind);
  const sibs = me && me.bundle ? nodes.filter((n) => n.impl && n.bundle === me.bundle && n.id !== kind) : [];
  const hist = (D.pulses || []).filter((p) => p.kind === kind);

  /* ── 头部 ── */
  $("cap-id").textContent = kind || "（缺 id）";
  $("cap-desc").textContent = (me && me.desc) || "（这条能力位在本机注册表里没有说明字段）";
  $("crumb-here").textContent = kind;
  /* 🔴 页面固定（主人令 2026-10-27）：`（束）`这一格以前是
       setAttribute("href", HOME)   // caps 页里 HOME = "../../index.html"
     那是 **APP 根首页** —— 点下去等于把整个 APP 装进 panel 的 webview 内容区
     （主人令 2026-10-04「不许跳转，全部内镶嵌」）。现在改成"让面板切页"：
     `panelGoto` 只认注册表里的窗 id，`godview` 就是那扇窗；壳不在就由 cap.js 的
     委托回退到 showWindow，再不行如实说没桥 —— 三层都不静默。
     ⚠️ 只在 `caps/` 下这么改：模板页（`brain/` 下，IN_CAPS 为假）的 HOME 是
     `index.html`（brain 自己的总目录），那是同目录浏览，语义不同，保持原样。 */
  const cb = $("crumb-bundle");
  cb.textContent = bundle ? bundle.label : "（无束）";
  if (IN_CAPS) {
    cb.setAttribute("href", "#");
    cb.setAttribute("data-panel-goto", "godview");
  } else {
    cb.setAttribute("href", HOME);
  }

  const state = !me ? "未登记" : !me.impl ? "仅登记未实现" : me.safe ? "免卡直跑" : "需授权";
  const badge = $("cap-state");
  badge.textContent = state;
  badge.className = "mc-badge " + (!me ? "" : !me.impl ? "critical" : me.safe ? "nominal" : "warning");

  /* ── 遥测条（真数）── */
  $("t-implemented").textContent = me ? (me.impl ? "是" : "否") : "—";
  $("t-safe").textContent = me ? (me.safe ? "是" : "否") : "—";
  $("t-bundle").textContent = bundle ? (bundle.label + "（" + bundle.n + " 位）") : "—";
  $("t-calls").textContent = hist.length;
  $("t-out").textContent = out.length;
  $("t-in").textContent = inn.length;

  /* ── 出处：这一条能力位真实落在哪些文件上 ── */
  const files = (me && me.files) || [];
  $("src-files").innerHTML = files.length
    ? files.map((f) => '<div class="kv"><span class="k">实现文件</span><span class="v">' + esc(f) + "</span></div>").join("")
    : '<p class="empty"><b>没有落到文件上</b> —— 分派支路里没抓到 import，' +
      '不等于它没有实现（判据边界见 brain-feed.py 的 _dispatch_files）</p>';
  $("src-registry").textContent = D.source.caps;
  $("src-dispatch").textContent = D.source.edges;

  /* ── 连接：出边（我用谁）/ 入边（谁用我）── */
  function rows(list, dir) {
    if (!list.length) return "";
    return list.map((e) => {
      const other = dir === "out" ? e.b : e.a;
      const via = dir === "out" ? (e.fa + " → " + e.fb) : (e.fb + " → " + e.fa);
      const href = CAP(other);
      return '<div class="link-row"><span class="dir">' + (dir === "out" ? "→" : "←") + "</span>" +
             '<a class="id" href="' + href + '">' + esc(other) + "</a>" +
             '<span class="w">权重 ' + esc(e.w) + "</span>" +
             '<span class="via">' + esc(via) + "</span></div>";
    }).join("");
  }
  $("out-list").innerHTML = out.length ? rows(out, "out")
    : '<p class="empty"><b>没有出边</b> —— 它不依赖别的能力位（或依赖的是包入口这类<em>噪音边</em>，已过滤）</p>';
  $("in-list").innerHTML = inn.length ? rows(inn, "in")
    : '<p class="empty"><b>没有入边</b> —— 账本与依赖图里没有别的能力位指向它</p>';
  $("out-n").textContent = out.length + " 条";
  $("in-n").textContent = inn.length + " 条";

  /* ── 调用史（**真发生过的**审计事件）── */
  $("hist-n").textContent = hist.length + " 次";
  $("hist-list").innerHTML = hist.length
    ? hist.slice(0, 40).map((p) =>
        '<div class="hist"><span class="t">' + esc(String(p.iso || "").slice(11, 19)) + "</span>" +
        "<span>" + esc(p.bundle || "未分类") + "</span>" +
        '<span class="' + (p.ok === false ? "bad" : "ok") + '">' + (p.ok === false ? "失败" : "成功") + "</span></div>").join("")
    : '<p class="empty">审计账本里<b>没有这条能力位的调用记录</b> —— 如实报"没有"，不是"读不到"</p>';

  /* ── 同束的其他能力位（横向导航，一页一条）── */
  $("sib-n").textContent = sibs.length + " 位";
  $("sib-list").innerHTML = sibs.length
    ? sibs.map((n) => '<a href="' + CAP(n.id) + '">' + esc(n.id) + "</a>").join("")
    : '<p class="empty">这一束里只有它一位</p>';

  /* ── 全量导航**故意不铺开**（风哥：「别设计的挤在一起小气的样子」）──
     铺开发 = 又一屏 161 个小格子 = 换个地方挤。只报条数，入口指向总目录（那里按束分组）。 */
  $("all-n").textContent = nodes.length + " 页";

  $("cap-at").textContent = D.at;
})();

/* ── 互通层（2026-10-24）：任意能力页都能「调任意能力位」，Ctrl+K 跳任意页 ──
   两件事都走本地桥 http://127.0.0.1:8791；桥不在就如实说桥不在，不装死。 */
(function () {
  "use strict";
  var BRIDGE = "http://127.0.0.1:8791";
  var kind = document.body.dataset.kind || "";
  var CACHE = "gbt.caps.v1";

  function el(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    return e;
  }
  function getCaps() {
    var raw = sessionStorage.getItem(CACHE);
    if (raw) { try { return Promise.resolve(JSON.parse(raw)); } catch (e) { /* 坏了就重取 */ } }
    return fetch(BRIDGE + "/v1/caps").then(function (r) { return r.json(); })
      .then(function (j) {
        if (j && j.caps) { sessionStorage.setItem(CACHE, JSON.stringify(j.caps)); }
        return (j && j.caps) || [];
      })
      .catch(function () { return []; });
  }

  /* ── ① 调用面板：本页就能跑任何能力位 ── */
  var panel = el("div", "gbt-call");
  panel.style.cssText = "position:fixed;right:14px;bottom:14px;z-index:2147483000;width:340px;"
    + "font:13px/1.5 system-ui,'Microsoft YaHei',sans-serif;background:rgba(7,10,26,.92);"
    + "color:#E8ECF8;border:1px solid rgba(120,170,255,.35);border-radius:12px;padding:10px 12px;"
    + "box-shadow:0 10px 30px rgba(3,4,12,.45)";
  var head = el("div", null, "⛓ 调用能力位 ");
  head.style.cssText = "font-weight:600;margin-bottom:6px;cursor:pointer";
  var body = el("div");
  body.style.display = "none";
  var sel = el("select");
  sel.style.cssText = "width:100%;margin:4px 0;background:#111827;color:#E8ECF8;border:1px solid var(--taste-border,#1E3A5F);border-radius:8px;padding:4px";
  var ta = el("textarea");
  ta.value = "{}";
  ta.rows = 3;
  ta.style.cssText = "width:100%;box-sizing:border-box;background:#111827;color:#E8ECF8;border:1px solid var(--taste-border,#1E3A5F);border-radius:8px;padding:6px;font-family:ui-monospace,Consolas,monospace";
  var run = el("button", null, "运行");
  run.style.cssText = "margin-top:6px;background:#2b6cff;color:var(--taste-text,#E8ECF8);border:0;border-radius:8px;padding:6px 14px;cursor:pointer";
  var out = el("pre", null, "");
  out.style.cssText = "max-height:180px;overflow:auto;background:var(--taste-ground,#0B1120);border:1px solid var(--taste-border,#1E3A5F);border-radius:8px;padding:8px;margin:8px 0 0;white-space:pre-wrap;word-break:break-all;font:12px/1.45 ui-monospace,Consolas,monospace";
  head.appendChild(el("span", null, "· Ctrl+K 跳页"));
  body.appendChild(sel); body.appendChild(ta); body.appendChild(run); body.appendChild(out);
  panel.appendChild(head); panel.appendChild(body);
  document.body.appendChild(panel);
  head.addEventListener("click", function () {
    body.style.display = body.style.display === "none" ? "block" : "none";
    if (body.style.display === "block") { loadSelect(); }
  });
  var selectLoaded = false;
  function loadSelect() {
    if (selectLoaded) { return; }
    selectLoaded = true;
    sel.appendChild(el("option", null, "（读能力名册…）"));
    getCaps().then(function (caps) {
      sel.innerHTML = "";
      if (!caps.length) { sel.appendChild(el("option", null, "桥没起（:8791 不通）")); return; }
      caps.forEach(function (c) {
        var o = el("option", null, c.name + " · " + (c.domain || ""));
        o.value = c.name;
        sel.appendChild(o);
      });
      if (kind) { sel.value = kind; }
    });
  }
  run.addEventListener("click", function () {
    var cap = sel.value || kind;
    var args;
    try { args = JSON.parse(ta.value || "{}"); } catch (e) {
      out.textContent = "payload 不是合法 JSON：" + e.message; return;
    }
    out.textContent = "调用 " + cap + " …";
    var t0 = performance.now();
    fetch(BRIDGE + "/v1/dispatch", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({capability: cap, args: args})
    }).then(function (r) { return r.json(); })
      .then(function (j) {
        var ms = Math.round(performance.now() - t0);
        out.textContent = "// " + ms + " ms\n" + JSON.stringify(j, null, 1).slice(0, 4000);
      })
      .catch(function (e) { out.textContent = "桥连不上（" + BRIDGE + "）：" + e.message; });
  });

  /* ── ② 命令面板：Ctrl+K 搜 341 个能力位，回车跳页 ── */
  var pal = el("div", "gbt-pal");
  pal.style.cssText = "position:fixed;inset:0;z-index:2147483001;display:none;"
    + "background:rgba(3,4,12,.72);backdrop-filter:blur(3px)";
  var box = el("div");
  box.style.cssText = "position:absolute;left:50%;top:14%;transform:translateX(-50%);width:min(640px,92vw);"
    + "background:#111827;border:1px solid var(--taste-border,#1E3A5F);border-radius:14px;overflow:hidden;"
    + "box-shadow:0 24px 60px rgba(3,4,12,.6)";
  var inp = el("input");
  inp.placeholder = "搜能力位 / 页面名…（Esc 关，Enter 打开）";
  inp.style.cssText = "width:100%;box-sizing:border-box;padding:14px 16px;border:0;outline:0;"
    + "background:#111827;color:#E8ECF8;font:15px system-ui,'Microsoft YaHei',sans-serif";
  var list = el("div");
  list.style.cssText = "max-height:52vh;overflow:auto";
  box.appendChild(inp); box.appendChild(list);
  pal.appendChild(box);
  document.body.appendChild(pal);

  var all = [];
  var sel2 = 0;
  function paint() {
    var q = inp.value.trim().toLowerCase();
    var hits = all.filter(function (c) {
      return !q || (c.name + " " + (c.domain || "") + " " + (c.desc || "")).toLowerCase().indexOf(q) >= 0;
    }).slice(0, 60);
    list.innerHTML = "";
    if (!hits.length) {
      var e2 = el("div", null, all.length ? "没有匹配" : "桥没起（:8791 不通），拿不到名册");
      e2.style.cssText = "padding:16px;color:#9AA4C4";
      list.appendChild(e2); return;
    }
    if (sel2 >= hits.length) { sel2 = 0; }
    hits.forEach(function (c, i) {
      var row = el("div");
      row.style.cssText = "padding:9px 16px;cursor:pointer;border-top:1px solid var(--taste-border,#1E3A5F);"
        + (i === sel2 ? "background:var(--taste-raised,#1A2535);" : "");
      row.innerHTML = "<b>" + c.name + "</b> <span style='color:#9AA4C4'>· " + (c.domain || "")
        + "</span><br><span style='color:#9AA4C4;font-size:12px'>" + (c.desc || "") + "</span>";
      row.addEventListener("click", function () { location.href = c.page; });
      list.appendChild(row);
    });
  }
  function openPal() {
    sel2 = 0; inp.value = ""; pal.style.display = "block"; inp.focus();
    if (all.length) { paint(); return; }
    list.innerHTML = "<div style='padding:16px;color:#9AA4C4'>读名册…</div>";
    getCaps().then(function (caps) { all = caps; paint(); });
  }
  function closePal() { pal.style.display = "none"; }
  inp.addEventListener("input", function () { sel2 = 0; paint(); });
  inp.addEventListener("keydown", function (e) {
    if (e.key === "ArrowDown") { sel2 = Math.min(sel2 + 1, 59); paint(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { sel2 = Math.max(sel2 - 1, 0); paint(); e.preventDefault(); }
    else if (e.key === "Enter") {
      var q = inp.value.trim().toLowerCase();
      var hits = all.filter(function (c) {
        return !q || (c.name + " " + (c.domain || "") + " " + (c.desc || "")).toLowerCase().indexOf(q) >= 0;
      });
      if (hits[sel2]) { location.href = hits[sel2].page; }
    } else if (e.key === "Escape") { closePal(); }
  });
  pal.addEventListener("click", function (e) { if (e.target === pal) { closePal(); } });
  document.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) { e.preventDefault(); openPal(); }
  });
})();

/* ── 页面固定（2026-10-27）：跨"扇"入口只许切页/开窗，不许导航 ──
 *
 * 这些页面活在 panel 的 `<webview>` 里（panel/index.html 显式给 webview 挂了壳的 preload，
 * 所以 `window.gbtW3` 是有的）。三种环境、三层回退，**每层都不静默**：
 *   ① 在面板里  ⇒ `panelGoto({id})`：让**面板**在内容区切页（主人令 2026-10-04
 *      「不许跳转，全部内镶嵌」）—— 当前 webview 的 URL 一个字节不动；
 *   ② 在壳里但不在面板 ⇒ `showWindow({id})`：开那扇窗（只认注册表里已有的 id）；
 *   ③ 都没有（浏览器直开）⇒ 什么都不做，只把 title 改成实话，不假装点过了。
 * 🔴 为什么写在这里而不是页页内联：cap.js 是这 349 页共用的渲染器
 *    （"版式与渲染只有一份"，见 cap-pages.py 的纪律）。
 */
(function () {
  "use strict";
  var api = window.gbtW3 || null;
  var els = document.querySelectorAll("[data-panel-goto]");
  for (var i = 0; i < els.length; i++) {
    (function (el) {
      el.addEventListener("click", function (e) {
        if (e && e.preventDefault) e.preventDefault();
        var id = el.getAttribute("data-panel-goto");
        if (api && typeof api.panelGoto === "function") {
          Promise.resolve(api.panelGoto({ id: id })).then(null, function () {
            if (api && typeof api.showWindow === "function") return api.showWindow({ id: id });
          });
          return;
        }
        if (api && typeof api.showWindow === "function") {
          Promise.resolve(api.showWindow({ id: id })).then(null, function () {});
          return;
        }
        el.setAttribute("title", "浏览器直开时切不到「" + id + "」—— 请在 GBT小土豆V8 壳里打开");
      });
    })(els[i]);
  }
})();

