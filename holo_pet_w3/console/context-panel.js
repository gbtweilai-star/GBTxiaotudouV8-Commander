/* ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
 * 上下文注入预览：按最后一条用户消息选择焦点/记忆/工具结果；只读，不注入模型。 */
(function () {
  "use strict";
  var list = document.getElementById("inject-items");
  var meta = document.getElementById("inject-meta");
  var budgetEl = document.getElementById("inject-budget");
  if (!list) return;
  function el(tag, cls, text) {
    var n = document.createElement(tag); if (cls) n.className = cls;
    if (text != null) n.textContent = text; return n;
  }
  function lastQuery() {
    var ms = document.querySelectorAll("#chat-messages .msg.user");
    var m = ms[ms.length - 1];
    return m ? String(m.textContent || "").slice(0, 200) : "";
  }
  function render(j) {
    var sel = (j && j.selection) || {};
    var items = sel.items || [];
    list.innerHTML = "";
    if (!items.length) list.appendChild(el("div", "inject-empty", "没有可注入项（候选为空或都过期）"));
    items.forEach(function (it) {
      var row = el("div", "inject-item");
      row.appendChild(el("span", "inject-src", it.source || "?"));
      row.appendChild(el("span", "inject-text", (it.text || "").slice(0, 120)));
      row.appendChild(el("span", "inject-score", String(it.score)));
      list.appendChild(row);
    });
    if (budgetEl) budgetEl.textContent = (sel.used || 0) + "/" + (sel.budget || 3000);
    if (meta) {
      var d = sel.dropped || {};
      meta.textContent = "候选 " + ((j && j.candidates) || 0) + " · 选中 " + (sel.count || 0) +
        " · 丢：过期" + (d.expired || 0) + "/重复" + (d.duplicate || 0) +
        "/预算" + (d.budget || 0);
    }
  }
  function refresh() {
    var q = encodeURIComponent(lastQuery());
    fetch("/api/context?budget=3000&query=" + q, { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(render).catch(function () {});
  }
  window.__contextRefresh = refresh;
  var b = document.getElementById("inject-preview");
  if (b) b.addEventListener("click", refresh);
  setInterval(refresh, 15000);
  refresh();
})();
