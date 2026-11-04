/* ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
 * 提醒：创建/取消；写面由后端过 filesystem_write 门，不做网络通知。 */
(function () {
  "use strict";
  var list = document.getElementById("rem-list");
  var countEl = document.getElementById("rem-count");
  var input = document.getElementById("rem-input");
  var timeEl = document.getElementById("rem-time");
  var note = document.getElementById("rem-note");
  if (!list) return;
  function pad(n) { return String(n).padStart(2, "0"); }
  function defaultDue() {
    var d = new Date(Date.now() + 10 * 60000);
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
      "T" + pad(d.getHours()) + ":" + pad(d.getMinutes());
  }
  function el(tag, cls, text) {
    var n = document.createElement(tag); if (cls) n.className = cls;
    if (text != null) n.textContent = text; return n;
  }
  function render(j) {
    var rows = (j && j.reminders) || [];
    list.innerHTML = "";
    if (!rows.length) list.appendChild(el("div", "reminder-empty", "暂无提醒"));
    rows.slice(0, 8).forEach(function (r) {
      var row = el("div", "reminder-item");
      row.appendChild(el("span", "reminder-dot", r.status === "pending" ? "●" : "○"));
      var main = el("div", "reminder-main");
      main.appendChild(el("span", "reminder-title", r.title || r.id));
      main.appendChild(el("span", "reminder-due", (r.due_at || "").replace("T", " ").slice(5, 16)));
      row.appendChild(main);
      if (r.status === "pending") {
        var x = el("button", "reminder-cancel", "×");
        x.type = "button"; x.title = "取消提醒";
        x.onclick = function () {
          fetch("/api/reminders", { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ op: "cancel", id: r.id }) }).then(refresh).catch(function () {});
        };
        row.appendChild(x);
      } else row.appendChild(el("span", "reminder-status", r.status));
      list.appendChild(row);
    });
    if (countEl) countEl.textContent = (j && j.count != null ? j.count : rows.length) +
      ((j && j.due_count) ? " · 到点 " + j.due_count : "");
  }
  var notified = {};
  var cardMap = {};
  function notifyDue(j) {
    var due = (j && j.due) || [];
    due.forEach(function (r) {
      if (!r || !r.id || notified[r.id]) return;
      notified[r.id] = true;
      fetch("/api/ui/cards", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ op: "create", card: {
          kind: "wake", title: "提醒 · " + (r.title || "到点"),
          body: "到点：" + (r.title || "") + "（" + (r.due_at || "") + "）",
          source: "reminder", ttl: 900,
          actions: [{ id: "ok", type: "confirm", label: "知道了" },
                    { id: "later", type: "dismiss", label: "稍后" }]
        } }) }).then(function (res) { return res.json(); }).then(function (res) {
          if (res && res.ok && res.card && res.card.id) cardMap[res.card.id] = r.id;
        }).catch(function () {});
    });
  }
  function refresh() {
    fetch("/api/reminders", { cache: "no-store" }).then(function (r) { return r.json(); })
      .then(function (j) { render(j); notifyDue(j); }).catch(function () {});
  }
  function create() {
    var title = input ? input.value.trim() : "";
    var due = timeEl && timeEl.value ? timeEl.value : defaultDue();
    if (!title) { if (input) input.focus(); return; }
    fetch("/api/reminders", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ op: "create", reminder: { title: title, due_at: due } }) })
      .then(function (r) { return r.json(); }).then(function (j) {
        if (j && j.ok) { if (input) input.value = ""; refresh(); }
        else if (note) note.textContent = "创建失败：" + ((j && j.error) || "未知");
      }).catch(function () {});
  }
  window.__reminderRefresh = refresh;
  if (timeEl && !timeEl.value) timeEl.value = defaultDue();
  var b = document.getElementById("rem-add");
  if (b) b.addEventListener("click", create);
  if (input) input.addEventListener("keydown", function (e) { if (e.key === "Enter") create(); });
  setInterval(refresh, 15000);
  refresh();

  window.addEventListener("gbt:ui-card-action", function (e) {
    var ev = (e && e.detail) || {};
    var rid = cardMap[ev.card_id];
    if (!rid) return;
    var act = ev.action || {};
    if (act.type === "confirm" || act.id === "ok") {
      fetch("/api/reminders", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ op: "complete", id: rid }) })
        .then(function (r) { return r.json(); })
        .then(function (j) { if (j && j.ok) refresh(); })
        .catch(function () {});
    }
  });

})();
