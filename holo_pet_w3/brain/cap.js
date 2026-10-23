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
  $("crumb-bundle").textContent = bundle ? bundle.label : "（无束）";
  $("crumb-bundle").setAttribute("href", HOME);

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
