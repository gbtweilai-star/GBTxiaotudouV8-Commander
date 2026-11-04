/* ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
 * 媒体舞台：只读索引既有产物；点开用 /api/media/file 播放/查看。 */
(function () {
  "use strict";
  var grid = document.getElementById("ms-grid");
  var countEl = document.getElementById("ms-count");
  var histEl = document.getElementById("ms-history");
  var modal = document.getElementById("ms-modal");
  if (!grid) return;
  var kind = "";
  function el(tag, cls, text) {
    var n = document.createElement(tag); if (cls) n.className = cls;
    if (text != null) n.textContent = text; return n;
  }
  function humanSize(mb) {
    var n = Number(mb) || 0;
    return n >= 1024 ? (n / 1024).toFixed(1) + " GB" : n.toFixed(1) + " MB";
  }
  function srcFor(path) { return "/api/media/file?path=" + encodeURIComponent(path); }
  function openPreview(it) {
    if (!modal) return;
    var body = document.getElementById("ms-modal-body");
    var title = document.getElementById("ms-modal-title");
    if (title) title.textContent = it.title + " · " + it.kind;
    body.innerHTML = "";
    var node;
    if (it.kind === "image") {
      node = document.createElement("img"); node.src = srcFor(it.path); node.alt = it.title;
    } else if (it.kind === "video") {
      node = document.createElement("video"); node.src = srcFor(it.path); node.controls = true; node.autoplay = true;
    } else {
      node = document.createElement("audio"); node.src = srcFor(it.path); node.controls = true;
    }
    node.className = "ms-media";
    body.appendChild(node);
    body.appendChild(el("div", "ms-path", it.path));
    modal.hidden = false;
  }
  function render(j) {
    var rows = (j && j.items) || [];
    grid.innerHTML = "";
    if (!rows.length) grid.appendChild(el("div", "ms-empty", "这个分类暂无产物"));
    rows.forEach(function (it) {
      var card = el("div", "ms-card");
      var icon = it.kind === "video" ? "▶" : (it.kind === "audio" ? "♪" : "▣");
      card.appendChild(el("div", "ms-icon " + it.kind, icon));
      card.appendChild(el("div", "ms-name", it.title || it.path));
      card.appendChild(el("div", "ms-meta", it.kind + " · " + humanSize(it.size_mb) + " · " + (it.at || "").slice(5, 16)));
      card.onclick = function () { openPreview(it); };
      grid.appendChild(card);
    });
    if (countEl) countEl.textContent = (j && j.count != null ? j.count : rows.length) + " 件 · " +
      JSON.stringify((j && j.counts) || {});
    if (histEl) {
      var h = (j && j.history) || [];
      histEl.innerHTML = "";
      histEl.appendChild(el("b", null, "最近产物"));
      h.forEach(function (x) { histEl.appendChild(el("span", "ms-hist", (x.at || "").slice(5, 16) + " · " + x.title)); });
      if (!h.length) histEl.appendChild(el("span", "ms-hist", "—"));
    }
  }
  function refresh() {
    fetch("/api/media?limit=120&kind=" + encodeURIComponent(kind), { cache: "no-store" })
      .then(function (r) { return r.json(); }).then(render).catch(function () {});
  }
  window.__mediaRefresh = refresh;
  document.querySelectorAll(".ms-filter").forEach(function (b) {
    b.addEventListener("click", function () {
      document.querySelectorAll(".ms-filter").forEach(function (x) { x.classList.remove("is-active"); });
      b.classList.add("is-active");
      kind = b.getAttribute("data-kind") || "";
      refresh();
    });
  });
  var rb = document.getElementById("ms-refresh");
  if (rb) rb.addEventListener("click", refresh);
  var mc = document.getElementById("ms-modal-close");
  if (mc) mc.addEventListener("click", function () { modal.hidden = true; });
  if (modal) modal.addEventListener("click", function (e) { if (e.target === modal) modal.hidden = true; });
  refresh();
})();
