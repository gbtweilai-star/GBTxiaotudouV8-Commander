/* ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
 * 动态 API 槽：只读列表；执行器未接，call 永远 not_supported。 */
(function () {
  "use strict";
  var list = document.getElementById("api-list");
  var countEl = document.getElementById("api-count");
  var note = document.getElementById("api-note");
  if (!list) return;
  function el(tag, cls, text) {
    var n = document.createElement(tag); if (cls) n.className = cls;
    if (text != null) n.textContent = text; return n;
  }
  function render(j) {
    var slots = (j && j.slots) || [];
    list.innerHTML = "";
    if (!slots.length) list.appendChild(el("div", "api-empty", "没有登记的槽；调用 call 会返回 not_supported"));
    slots.forEach(function (s) {
      var row = el("div", "api-item");
      row.appendChild(el("span", "api-method", s.method || "GET"));
      row.appendChild(el("span", "api-name", s.name || ""));
      row.appendChild(el("span", "api-host", (function () {
        try { return new URL(s.url).host; } catch (e) { return "?"; }
      })()));
      list.appendChild(row);
    });
    if (countEl) countEl.textContent = (j && j.count != null ? j.count : slots.length) + "/20";
    if (note) note.textContent = "https-only · 拒私网 · 密钥只存 env 引用名 · 执行器 " +
      ((j && j.executor) || "not_wired");
  }
  function refresh() {
    fetch("/api/slots", { cache: "no-store" }).then(function (r) { return r.json(); })
      .then(render).catch(function () {});
  }
  window.__apiSlotsRefresh = refresh;
  setInterval(refresh, 20000);
  refresh();
})();
