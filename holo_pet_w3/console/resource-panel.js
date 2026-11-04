/* ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
 * 本机资源快照：只读；CPU/内存/磁盘条 + host/uptime；不写盘/不起进程。 */
(function () {
  "use strict";
  var host = document.getElementById("res-host");
  if (!host) return;
  function el(id) { return document.getElementById(id); }
  function pct(id, v) { var b = el(id); if (b) b.style.width = Math.max(0, Math.min(100, Number(v) || 0)) + "%"; }
  function render(j) {
    if (host) host.textContent = (j && j.host) || "—";
    pct("res-cpu-bar", j && j.cpu_percent);
    pct("res-mem-bar", j && j.mem_percent);
    pct("res-disk-bar", j && j.disk_percent);
    var cpu = el("res-cpu"), mem = el("res-mem"), disk = el("res-disk"), note = el("res-note");
    if (cpu) cpu.textContent = (j && j.cpu_percent != null ? j.cpu_percent + "%" : "—");
    if (mem) mem.textContent = (j && j.mem_percent != null ? j.mem_percent + "% · " +
      Math.round(j.mem_used_mb) + "/" + Math.round(j.mem_total_mb) + "MB" : "—");
    if (disk) disk.textContent = (j && j.disk_percent != null ? j.disk_percent + "% · " +
      j.disk_used_gb + "/" + j.disk_total_gb + "GB" : "—");
    if (note) {
      var up = j && j.uptime_s ? (j.uptime_s / 3600).toFixed(1) + "h" : "—";
      var pc = (j && j.process_count != null) ? j.process_count : "—";
      note.textContent = "uptime " + up + " · 进程 " + pc + " · " + ((j && j.platform) || "");
    }
  }
  function refresh() {
    fetch("/api/resources", { cache: "no-store" }).then(function (r) { return r.json(); })
      .then(render).catch(function () {});
  }
  window.__resourcesRefresh = refresh;
  setInterval(refresh, 10000);
  refresh();
})();
