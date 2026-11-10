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
    if (n >= 1024) return (n / 1024).toFixed(1) + " GB";
    if (n >= 1) return n.toFixed(1) + " MB";
    return Math.max(1, Math.round(n * 1024)) + " KB";
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
    if (!rows.length) {
      var empt = el("div", "ms-empty", kind ? "当前分类暂无产物。" : "还没有媒体产物。");
      empt.appendChild(el("em", null, kind
        ? "切回「全部」看看其它类型；仍为空说明 outputs/ 里还没落这一类文件。"
        : "产物来自产品目录 outputs/（语音互通 / 创作 / 视频）。跑一次对应任务后会自动出现在这里，也可以点右上「刷新」。"));
      grid.appendChild(empt);
    }
    rows.forEach(function (it) {
      var card = el("div", "ms-card");
      var icon = it.kind === "video" ? "▶" : (it.kind === "audio" ? "♪" : "▣");
      card.appendChild(el("div", "ms-icon " + it.kind, icon));
      card.appendChild(el("div", "ms-name", it.title || it.path));
      card.appendChild(el("div", "ms-meta", it.kind + " · " + humanSize(it.size_mb) + " · " + (it.at || "").slice(5, 16)));
      card.onclick = function () { openPreview(it); };
      grid.appendChild(card);
    });
    if (countEl) {
      var cn = (j && j.counts) || {};
      var label = { video: "视频", image: "图片", audio: "音频" };
      var parts = Object.keys(cn).map(function (k) { return (label[k] || k) + " " + cn[k]; });
      countEl.textContent = (j && j.count != null ? j.count : rows.length) + " 件" +
        (parts.length ? " · " + parts.join(" · ") : "");
    }
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
