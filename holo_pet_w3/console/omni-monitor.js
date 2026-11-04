/* 万能插 · 多域监控（2026-11-02）
 * 每 2.5s 拉 /api/omni?op=monitor：7 插座 + 系统 + 记忆 + 触手 + 蓝图 + 文件 + 数字人；
 * 逐字段 diff（含 +0.1% CPU / 文件 mtime / 记忆版本 +1），变化高亮并进“最近变化”时间线。
 */
(function () {
  if (window.__omniMon) return;
  window.__omniMon = true;
  var $ = function (id) { return document.getElementById(id); };
  var last = null;

  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function fmtT(sec) {
    if (!sec) return "--";
    var d = new Date(sec * 1000);
    function p(n) { return n < 10 ? "0" + n : "" + n; }
    return p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
  }
  function dot(state) {
    var c = state === "ready" ? "#5ad19a" : (state === "needs_key" ? "#ffb02e" : "#e0715c");
    return "<i class='om-dot' style='background:" + c + "'></i>";
  }
  function card(title, state, rows, changedPaths) {
    var changed = {};
    (changedPaths || []).forEach(function (p) { changed[p] = true; });
    var body = rows.map(function (r) {
      var on = changed[r[0]];
      return "<div class='om-row" + (on ? " chg" : "") + "'><span>" + esc(r[0]) +
        "</span><b>" + esc(r[1]) + (r[2] ? "<i>" + esc(r[2]) + "</i>" : "") + "</b></div>";
    }).join("");
    return "<section class='om-card'><h3>" + dot(state) + esc(title) + "</h3>" + body + "</section>";
  }

  function render(d) {
    var s = d.domains || {};
    var sum = d.summary || {};
    var changes = d.changes || [];
    var changedPaths = changes.map(function (c) { return c.path; });
    $("om-sub").textContent = "采样 " + fmtT(d.sampled_at) + " · 变化 " + changes.length +
      " · 历史 " + (d.history || 0) + " 次";
    var cards = [];
    var sys = s.system || {};
    cards.push(card("系统", "ready", [
      ["CPU", (sys.cpu == null ? "—" : sys.cpu + "%"), sys.cpu == null ? "" : "实时"],
      ["内存", (sys.ram == null ? "—" : sys.ram + "%"), sys.ram_used_mb ? Math.round(sys.ram_used_mb / 1024) + "G" : ""],
      ["磁盘可用", sys.disk_free_gb + "G", ""],
      ["进程", sys.procs, ""],
    ], changedPaths));
    var om = s.omni || {};
    cards.push(card("万能插", "ready", [
      ["插座类型", om.kinds || 0, "process/file/api/web/app/ai/dh"],
      ["已插", om.sockets || 0, ""],
      ["钥匙槽", om.keys || 0, "env 只报已配数"],
      ["CA/全开", (om.ca ? "CA✓" : "CA×") + " · " + (om.full_open ? "全开" : "按门"), om.trusted ? "主人会话" : ""],
    ], changedPaths));
    var mem = s.memory || {};
    cards.push(card("记忆链", mem.error ? "needs_key" : "ready", [
      ["版本", mem.version == null ? "—" : mem.version, ""],
      ["条数", mem.count == null ? "—" : mem.count, ""],
      ["头哈希", mem.head ? String(mem.head).slice(0, 10) : "—", ""],
    ], changedPaths));
    var te = s.tentacle || {};
    cards.push(card("触手绑定", "ready", [
      ["资产", te.assets, ""],
      ["绑定对", te.pairs, ""],
      ["能力覆盖", (te.caps_bound == null ? "—" : te.caps_bound + "/" + te.caps_total),
       te.caps_missing ? "缺 " + te.caps_missing : "全连"],
    ], changedPaths));
    var bp = s.blueprint || {};
    cards.push(card("蓝图", bp.approved ? "ready" : "needs_key", [
      ["蓝图", bp.id || "—", ""],
      ["任务", (bp.done || 0) + "/" + (bp.tasks || 0), ""],
      ["批准", bp.approved ? "已批" : "待批", ""],
    ], changedPaths));
    var fl = s.files || {};
    var fsrow = Object.keys(fl).slice(0, 4).map(function (k) {
      return [k, fl[k].exists ? "✓" : "×", fl[k].exists ? fmtT(fl[k].mtime) : ""];
    });
    cards.push(card("关键状态文件", "ready", fsrow, changedPaths));
    var dh = s.dh || {};
    cards.push(card("数字人", dh.error ? "needs_key" : "ready", [
      ["动作", dh.action || "待机", ""],
      ["误差", dh.err == null ? "—" : dh.err, ""],
      ["执行器", dh.omni ? "已插" : "未插", ""],
      ["手势", dh.hand || "—", ""],
    ], changedPaths));
    var pa = s.proactive || {};
    cards.push(card("主动智能体", pa.error ? "needs_key" : (pa.running ? "ready" : "needs_key"), [
      ["运行", pa.running ? "执行中" : "未启动", ""],
      ["队列", (pa.counts && pa.counts.queued) || 0, "工单 " + (pa.tickets || 0)],
      ["完成", (pa.counts && pa.counts.done) || 0, "失败 " + ((pa.counts && pa.counts.failed) || 0)],
    ], changedPaths));
    var ln = s.lines || {};
    cards.push(card("关联线路", ln.error ? "needs_key" : "ready", [
      ["监控文件", ln.watched == null ? "—" : ln.watched, ""],
      ["关联边", ln.edges == null ? "—" : ln.edges, ""],
      ["本轮变化", ln.changed == null ? 0 : ln.changed, ""],
      ["最近涟漪", ln.last_path ? String(ln.last_path).split("/").pop() + " · " + ln.last_related + " 条" : "—", ""],
    ], changedPaths));
    $("om-grid").innerHTML = cards.join("");

    var recent = (d.recent || []).slice().reverse();
    var html = "";
    recent.forEach(function (ev) {
      var items = (ev.changes || []).slice(0, 6).map(function (c) {
        var from = esc(c.from), to = esc(c.to);
        var text = c.kind === "added" ? "新增 " + to : (c.kind === "removed" ?
          "移除 " + from : from + " → " + to);
        return "<div class='om-chg'><u>" + esc(c.path) + "</u><span>" + text + "</span></div>";
      }).join("");
      html += "<div class='om-ev'><div class='om-ev-t'>" + fmtT(ev.at) +
        " · " + (ev.changes || []).length + " 项</div>" + items + "</div>";
    });
    $("om-recent").innerHTML = html || "<div class='om-empty'>还没有变化（采样后对比会出现在这里）</div>";
    last = d;
  }

  function poll() {
    fetch("/api/omni?op=monitor").then(function (r) { return r.json(); })
      .then(function (d) { if (d && d.domains) render(d); })
      .catch(function () {});
  }

  var open = false, timer = null;
  function setOpen(v) {
    open = !!v;
    var panel = $("omni-mon"), toggle = $("om-toggle");
    if (panel) panel.classList.toggle("collapsed", !open);
    if (toggle) toggle.style.display = open ? "none" : "";
    try { localStorage.setItem("gbt.omniMonOpen", open ? "1" : "0"); } catch (e) {}
    if (open) {
      poll();
      if (!timer) timer = setInterval(poll, 2500);
    } else if (timer) {
      clearInterval(timer); timer = null;
    }
  }

  function wire() {
    try { open = localStorage.getItem("gbt.omniMonOpen") === "1"; } catch (e) { open = false; }
    setOpen(open);
    var toggle = $("om-toggle"), collapse = $("om-collapse");
    if (toggle) toggle.addEventListener("click", function () { setOpen(true); });
    if (collapse) collapse.addEventListener("click", function () { setOpen(false); });
    var btn = $("om-selftest");
    if (btn) btn.addEventListener("click", function () {
      btn.disabled = true; btn.textContent = "自检中…";
      fetch("/api/omni?op=fullopen").then(function (r) { return r.json(); })
        .then(function (d) {
          btn.disabled = false;
          btn.textContent = "全开自检 " + (d.passed || 0) + "/" + (d.total || 0);
          poll();
        }).catch(function () {
          btn.disabled = false; btn.textContent = "自检失败";
        });
    });
    if (open) { poll(); if (!timer) timer = setInterval(poll, 2500); }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
  else wire();
})();
