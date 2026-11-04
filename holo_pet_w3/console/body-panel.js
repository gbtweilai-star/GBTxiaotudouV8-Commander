/* ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
 * body_control 状态：只读；缺感觉/执行器如实报 not_supported，不假装能动。 */
(function () {
  "use strict";
  var stateEl = document.getElementById("body-state");
  var detail = document.getElementById("body-detail");
  var note = document.getElementById("body-note");
  if (!stateEl) return;
  function refresh() {
    fetch("/api/body", { cache: "no-store" }).then(function (r) { return r.json(); })
      .then(function (j) {
        var st = (j && j.status) || "not_supported";
        stateEl.textContent = st;
        stateEl.setAttribute("data-state", st);
        var ms = (j && j.missing) || {};
        if (detail) {
          detail.textContent = (j && j.note) ? j.note :
            "感觉/执行器未绑定 → 如实报缺，不假装能动。";
          if (ms.sensors || ms.actuators) {
            detail.textContent += " 缺感觉：" + ((ms.sensors || []).join("/") || "无") +
              "；缺执行器：" + ((ms.actuators || []).join("/") || "无");
          }
        }
        if (note) note.textContent = "wired=" + (j && j.wired ? "true" : "false") +
          " · executor=" + ((j && j.executor) || "not_wired");
      }).catch(function () {});
  }
  setInterval(refresh, 15000);
  refresh();
})();
