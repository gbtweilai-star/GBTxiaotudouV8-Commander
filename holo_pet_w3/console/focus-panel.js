/* ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
 * 焦点栈 + 记忆审计面板：只读列表/审计；弹出焦点走 POST（不执行工具）。 */
(function () {
  "use strict";
  var list = document.getElementById("focus-list");
  var auditEl = document.getElementById("focus-audit");
  var countEl = document.getElementById("focus-count");
  if (!list) return;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function render(j) {
    var focus = (j && j.focus) || {};
    var items = focus.items || [];
    list.innerHTML = "";
    if (!items.length) list.appendChild(el("div", "focus-empty", "暂无焦点（主循环把此刻最重要的事压进来）"));
    items.forEach(function (it) {
      var row = el("div", "focus-item");
      var main = el("div", "focus-main");
      main.appendChild(el("b", "focus-score", String(it.score)));
      main.appendChild(el("span", "focus-title", it.title || it.id));
      main.appendChild(el("span", "focus-kind", it.kind || "task"));
      row.appendChild(main);
      var x = el("button", "focus-pop", "×");
      x.type = "button"; x.title = "弹出这个焦点";
      x.onclick = function () {
        fetch("/api/focus", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ op: "pop", id: it.id }) }).then(refresh).catch(function () {});
      };
      row.appendChild(x);
      list.appendChild(row);
    });
    if (countEl) countEl.textContent = (focus.count || 0) + "/" + (focus.max || 12);
    var a = (j && j.audit) || {};
    var t = a.totals || {};
    if (auditEl) {
      auditEl.textContent = "记忆审计：" + (a.verdict === "clean" ? "干净" :
        (a.verdict ? "需复核（" + (t.issues || 0) + " 问题）" : "—")) +
        " · 记录 " + (a.count || 0) + " · 源 " + ((j && j.audit_source) || "state/memory_bank.jsonl");
    }
  }
  function refresh() {
    fetch("/api/focus", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(render)
      .catch(function () {});
  }
  window.__focusRefresh = refresh;
  var b = document.getElementById("focus-refresh");
  if (b) b.addEventListener("click", refresh);
  setInterval(refresh, 10000);
  refresh();
})();
