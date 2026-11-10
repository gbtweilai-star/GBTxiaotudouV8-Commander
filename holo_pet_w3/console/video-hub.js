/* ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
 * 视频舱：只读编目 + 六段只读探针联跑；不生成视频。 */
(function () {
  "use strict";
  var box = document.getElementById("vh-stages");
  var countEl = document.getElementById("vh-count");
  if (!box) return;
  function el(tag, cls, text) {
    var n = document.createElement(tag); if (cls) n.className = cls;
    if (text != null) n.textContent = text; return n;
  }
  function render(j) {
    box.innerHTML = "";
    var stages = (j && j.stages) || [];
    if (!stages.length) {
      var empt = el("div", "vh-empty", "没有读到视频编目。");
      empt.appendChild(el("em", null, "点「刷新」重试；仍为空说明 /api/video 没返回任何能力位，先查后端再联跑。"));
      box.appendChild(empt);
    }
    stages.forEach(function (st) {
      var col = el("div", "vh-stage");
      var head = el("div", "vh-stage-head");
      head.appendChild(el("b", null, st.stage));
      head.appendChild(el("span", null, st.count));
      col.appendChild(head);
      col.appendChild(el("div", "vh-sub", st.sub));
      var list = el("div", "vh-list");
      (st.items || []).forEach(function (it) {
        var row = el("div", "vh-item");
        row.appendChild(el("span", "vh-cap", it.cap));
        row.appendChild(el("span", "vh-domain", it.domain || ""));
        row.appendChild(el("span", "vh-desc", it.desc || ""));
        list.appendChild(row);
      });
      col.appendChild(list);
      box.appendChild(col);
    });
    if (countEl) countEl.textContent = (j && j.count != null ? j.count : 0) + " 件" +
      (stages.length ? " · " + stages.length + " 组阶段（六段可联跑）" : "");
  }
  function refresh() {
    fetch("/api/video", { cache: "no-store" }).then(function (r) { return r.json(); })
      .then(render).catch(function () {});
  }
  function runStages() {
    var out = document.getElementById("vh-run-result");
    if (out) out.textContent = "六段只读探针运行中…";
    fetch("/api/video", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ op: "run" }) }).then(function (r) { return r.json(); }).then(function (j) {
      if (!out) return;
      var rows = j.stages || [];
      out.innerHTML = "";
      rows.forEach(function (s) {
        var row = document.createElement("span");
        row.className = "vh-run-item " + (s.ok ? "ok" : "bad");
        row.textContent = s.stage + (s.ok ? " ✓" : " ✗ " + (s.error || (s.result || {}).reason || ""));
        out.appendChild(row);
      });
      var sum = document.createElement("span");
      var okN = rows.filter(function (s) { return s.ok; }).length;
      sum.className = "vh-run-sum";
      sum.textContent = okN + "/" + rows.length + " 段通" + (j.ok ? "" : "（有段未通）") + " · 未生成视频";
      out.appendChild(sum);
    }).catch(function () { if (out) out.textContent = "联跑失败"; });
  }
  window.__videoRefresh = refresh;
  window.__videoRunStages = runStages;
  var b = document.getElementById("vh-refresh");
  if (b) b.addEventListener("click", refresh);
  var rb = document.getElementById("vh-run");
  if (rb) rb.addEventListener("click", runStages);
  refresh();
})();
