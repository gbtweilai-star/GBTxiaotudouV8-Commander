/* ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
 * 思考流/行动流：只读列表；轮询 /api/stream，不执行任何东西。 */
(function () {
  "use strict";
  var list = document.getElementById("ts-list");
  var countEl = document.getElementById("ts-count");
  if (!list) return;
  var LABEL = { thought: "想", action: "做", result: "果", guard: "闸", system: "系" };
  var FULL = { thought: "思考", action: "行动", result: "结果", guard: "闸门", system: "系统" };
  function el(tag, cls, text) {
    var n = document.createElement(tag); if (cls) n.className = cls;
    if (text != null) n.textContent = text; return n;
  }
  function render(j) {
    var entries = (j && j.entries) || [];
    list.innerHTML = "";
    if (!entries.length) {
      var empt = el("div", "ts-empty", "还没有事件。");
      empt.appendChild(el("em", null, "对话或执行一次任务后，这里会出现 想 / 做 / 果 / 闸 / 系 五类记录；本页每 5 秒自动刷新，也可点右上「刷新」。"));
      list.appendChild(empt);
    }
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
    if (countEl) {
      var cs = (j && j.counts) || {};
      var parts = Object.keys(cs).filter(function (k) { return cs[k]; })
        .map(function (k) { return (FULL[k] || k) + " " + cs[k]; });
      countEl.textContent = (j && j.count != null ? j.count : 0) + " 条" +
        (parts.length ? " · " + parts.join(" · ") : "");
    }
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
