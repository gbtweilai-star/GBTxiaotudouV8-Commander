/* ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
 * 轮次追踪：只读归并；session+间隔切轮；不伪造输入/证据。 */
(function () {
  "use strict";
  var list = document.getElementById("tt-list");
  var detail = document.getElementById("tt-detail");
  var countEl = document.getElementById("tt-count");
  if (!list) return;
  var traces = [];
  function el(tag, cls, text) {
    var n = document.createElement(tag); if (cls) n.className = cls;
    if (text != null) n.textContent = text; return n;
  }
  function renderDetail(t) {
    if (!detail) return;
    detail.innerHTML = "";
    var head = el("div", "tt-detail-head");
    head.appendChild(el("b", null, t.id + " · " + t.session));
    head.appendChild(el("span", "tt-badge " + t.status, t.status));
    detail.appendChild(head);
    detail.appendChild(el("div", "tt-meta", t.start + " → " + t.end + " · " + t.duration_s + "s · 步骤 " + t.count + " · 证据 " + t.evidence_count));
    if (t.input != null) {
      detail.appendChild(el("div", "tt-input", "输入：" + t.input));
    } else {
      detail.appendChild(el("div", "tt-input tt-none", "账里没有记录输入（不伪造）"));
    }
    var steps = el("div", "tt-steps");
    (t.steps || []).forEach(function (s, i) {
      var row = el("div", "tt-step" + (s.ok ? "" : " is-fail"));
      row.appendChild(el("span", "tt-n", String(i + 1)));
      row.appendChild(el("span", "tt-at", (s.at || "").slice(5, 19)));
      row.appendChild(el("span", "tt-act", (s.action || s.actor || "?")));
      row.appendChild(el("span", "tt-target", s.target || ""));
      var body = el("div", "tt-body");
      body.appendChild(el("div", "tt-detail-text", s.detail || ""));
      if (s.evidence) body.appendChild(el("div", "tt-evidence", "证据：" + s.evidence));
      row.appendChild(body);
      row.appendChild(el("span", "tt-result", s.result || "ok"));
      steps.appendChild(row);
    });
    detail.appendChild(steps);
  }
  function render(j) {
    traces = (j && j.traces) || [];
    list.innerHTML = "";
    if (!traces.length) list.appendChild(el("div", "tt-empty", "暂无轮次（账为空）"));
    traces.forEach(function (t) {
      var row = el("div", "tt-item" + (t.status === "review" ? " is-review" : ""));
      row.appendChild(el("span", "tt-dot"));
      var main = el("div", "tt-main");
      main.appendChild(el("span", "tt-time", (t.start || "").slice(5, 16)));
      main.appendChild(el("span", "tt-session", t.session || "?"));
      main.appendChild(el("span", "tt-steps-n", t.count + " 步 · " + t.status));
      row.appendChild(main);
      row.onclick = function () {
        list.querySelectorAll(".tt-item").forEach(function (x) { x.classList.remove("is-active"); });
        row.classList.add("is-active");
        renderDetail(t);
      };
      list.appendChild(row);
    });
    if (countEl) countEl.textContent = (j && j.count != null ? j.count : traces.length) + " 轮 · 总 " + ((j && j.total) || 0);
    if (traces.length) { list.firstChild.classList.add("is-active"); renderDetail(traces[0]); }
  }
  function refresh() {
    fetch("/api/turns?limit=60", { cache: "no-store" }).then(function (r) { return r.json(); })
      .then(render).catch(function () {});
  }
  window.__turnsRefresh = refresh;
  var b = document.getElementById("tt-refresh");
  if (b) b.addEventListener("click", refresh);
  refresh();
})();
