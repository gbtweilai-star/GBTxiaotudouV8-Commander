/* ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
 * 思考流/行动流：只读列表；轮询 /api/stream，不执行任何东西。 */
(function () {
  "use strict";
  var list = document.getElementById("ts-list");
  var countEl = document.getElementById("ts-count");
  if (!list) return;
  var LABEL = { thought: "想", action: "做", result: "果", guard: "闸", system: "系" };
  function el(tag, cls, text) {
    var n = document.createElement(tag); if (cls) n.className = cls;
    if (text != null) n.textContent = text; return n;
  }
  function render(j) {
    var entries = (j && j.entries) || [];
    list.innerHTML = "";
    if (!entries.length) list.appendChild(el("div", "ts-empty", "暂无事件"));
    entries.forEach(function (e) {
      var row = el("div", "ts-item");
      row.setAttribute("data-kind", e.kind || "system");
      row.appendChild(el("span", "ts-kind", LABEL[e.kind] || e.kind || "?"));
      row.appendChild(el("span", "ts-time", (e.at || "").replace("T", " ").slice(5, 19)));
      row.appendChild(el("span", "ts-actor", e.actor || "?"));
      var main = el("div", "ts-main");
      main.appendChild(el("span", "ts-title", e.title || e.detail || ""));
      if (e.detail && e.title && e.detail !== e.title) main.appendChild(el("span", "ts-detail", e.detail.slice(0, 180)));
      row.appendChild(main);
      if (e.result) row.appendChild(el("span", "ts-result", e.result));
      list.appendChild(row);
    });
    if (countEl) countEl.textContent = (j && j.count != null ? j.count : 0) + " 条 · " +
      JSON.stringify((j && j.counts) || {});
  }
  function refresh() {
    fetch("/api/stream?limit=100", { cache: "no-store" })
      .then(function (r) { return r.json(); }).then(render).catch(function () {});
  }
  window.__streamRefresh = refresh;
  var b = document.getElementById("ts-refresh");
  if (b) b.addEventListener("click", refresh);
  setInterval(function () {
    if (window.__lastView === "stream") refresh();
  }, 5000);
})();
