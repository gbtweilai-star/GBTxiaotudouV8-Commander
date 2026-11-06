/* 改动影响面板（2026-11-06 并入开发仓）：id 一律 im-* / impact-mon，
 * 与 omni-monitor 的 om-* 各管一块，避免两个面板抢同一个表头。 */
/* 改动影响 · 多域监控（2026-11-04 重做）
 *
 * 主人令更正（这条是这张面板存在的唯一理由）：
 *   它**不是**在监控别的页面、别的能力位活着没活着 —— 那归心跳与服务巡检。
 *   它只回答一个问题：**「我这一刀改下去，哪些部位会跟着坏」**。
 *   避免的正是「修一处、坏一处」。
 *
 * 数据全部来自仓库关系图（5601 部位 / 65814 条关联）：
 *   · 写侧：万能插每真执行一次，omni_plug._sync_impact() **同步**追加一行留痕
 *   · 读侧：/api/omni?op=impact 才去图里算波及面 —— 执行永远不等这张图
 *
 * 人话约定（给不看代码的人）：
 *   1 跳 = 直接依赖它 / 被它依赖 —— 改名字改签名，这些最先断
 *   2 跳 = 外圈间接依赖 —— 回归时扫一遍
 *   波及 0 处 = 不在仓库关系图里（新文件/临时文件），**不等于安全**
 */
(function () {
  if (window.__impactBoard) return;
  window.__impactBoard = true;

  var $ = function (id) { return document.getElementById(id); };
  var LV = { red: "#F2565E", amber: "#E8A33A", green: "#5ad19a", grey: "#6f7270" };
  var lastData = null;

  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function clock(ts) {
    var m = /T(\d\d:\d\d)/.exec(String(ts || ""));
    if (m) return m[1];
    var s = String(ts || "").slice(11, 16);
    return s || "--";
  }
  function num(n) {
    var v = Number(n || 0);
    return isFinite(v) ? v.toLocaleString("zh-CN") : String(n);
  }

  /* ① 一句话结论：普通人只看这一行就够 */
  function renderVerdict(v) {
    var el = $("im-verdict");
    if (!el) return;
    if (!v) {
      el.style.borderLeftColor = LV.grey;
      el.innerHTML = "<div class='im-v-head' style='color:#9a9c99'>还没有可判断的改动</div>" +
        "<div class='im-v-body'>在下面输入一个文件路径，先看看它会连到哪。</div>";
      return;
    }
    var c = LV[v.level] || LV.grey;
    el.style.borderLeftColor = c;
    el.innerHTML =
      "<div class='im-v-head' style='color:" + c + "'>" + esc(v.head) + "</div>" +
      "<div class='im-v-body'>" + esc(v.body || "") + "</div>";
  }

  /* ② 四个数字：不讲节点、不讲边 */
  function renderNums(g) {
    var el = $("im-nums");
    if (!el) return;
    if (!g) { el.innerHTML = ""; return; }
    var items = [
      [num(g.parts), "个部位", "登记过的文件与能力位"],
      [num(g.links), "条关联", "谁引用谁，改动顺着这些线传"],
      [(g.core_share || 0) + "%", "连成一整片", "越高越是一动牵全身"],
      [num(g.islands), "处孤立", "跟大部队断开的部分"]
    ];
    el.innerHTML = items.map(function (x) {
      return "<div class='im-num'><b>" + x[0] + "</b><span>" + x[1] + "</span>" +
        "<i>" + x[2] + "</i></div>";
    }).join("");
  }

  /* ③ 单点查询结果：改这一处会碰到谁 */
  function renderProbe(p) {
    var el = $("im-probe");
    if (!el) return;
    if (!p) { el.style.display = "none"; el.innerHTML = ""; return; }
    el.style.display = "";
    var c = !p.in_graph ? LV.grey
      : (p.reach2 >= 1500 ? LV.red : (p.reach2 >= 200 ? LV.amber : LV.green));
    var head = p.in_graph
      ? "改 <b>" + esc(p.label) + "</b> 会碰到：1 跳 " + num(p.reach1) +
        " 处 · 外圈 " + num(p.reach2) + " 处"
      : "<b>" + esc(p.label) + "</b> 不在关系图里，撞不到别处";
    var sample = "";
    if ((p.sample || []).length) {
      var tags = p.sample.slice(0, 12).map(function (s) {
        var name = String(s).split("/").pop();
        return "<u title='" + esc(s) + "'>" + esc(name) + "</u>";
      }).join("");
      if (p.sample.length > 12) tags += "<u title='还有更多'>…</u>";
      sample = "<div class='im-sample'>最先断的：" + tags + "</div>";
    }
    el.innerHTML = "<div class='im-p-head' style='color:" + c + "'>" + head + "</div>" + sample;
  }

  /* ④ 条形图：最不能随便动的 */
  function renderBars(rows) {
    var el = $("im-bars");
    if (!el) return;
    if (!rows || !rows.length) {
      el.innerHTML = "<div class='im-empty'>关系图里还没有可排的文件。</div>";
      return;
    }
    var max = 1;
    rows.forEach(function (r) { if ((r.reach || 0) > max) max = r.reach; });
    el.innerHTML = rows.map(function (r, i) {
      var w = Math.max(2, Math.round((r.reach || 0) / max * 100));
      var c = i === 0 ? LV.red : (r.reach >= max * 0.5 ? LV.amber : "#7EA2F6");
      var dir = String(r.path || "");
      var slash = dir.lastIndexOf("/");
      var where = slash > 0 ? dir.slice(0, slash) : "仓库根";
      return "<div class='im-bar'>" +
        "<div class='im-bar-top'><span title='" + esc(r.path) + "'>" + esc(r.label) + "</span>" +
        "<b style='color:" + c + "'>" + num(r.reach) + "</b></div>" +
        "<div class='im-bar-track'><div class='im-bar-fill' style='width:" + w +
        "%;background:" + c + "'></div></div>" +
        "<div class='im-bar-sub'>" + esc(where) +
        " · 关联文件 " + num(r.files) + " · 能力位 " + num(r.caps) + "</div>" +
        "</div>";
    }).join("");
  }

  /* ⑤ 时间线：刚才动了什么 → 会连带碰到多少处 */
  function renderFeed(rows) {
    var el = $("im-feed");
    if (!el) return;
    if (!rows || !rows.length) {
      el.innerHTML = "<div class='im-empty'>还没有万能插动作。它每真执行一次，这里就多一条。</div>";
      return;
    }
    el.innerHTML = rows.map(function (r) {
      var c = !r.in_graph ? LV.grey
        : (r.reach2 >= 1500 ? LV.red : (r.reach2 >= 200 ? LV.amber : "#7EA2F6"));
      var badge = r.in_graph ? ("波及 " + num(r.reach2) + " 处") : "不在仓库里";
      var raw = String(r.target || "");
      var name = raw.split(/[\\\/]/).pop() || raw;
      return "<div class='im-ev'>" +
        "<span class='im-ev-t'>" + esc(clock(r.ts)) + "</span>" +
        "<span class='im-ev-a" + (r.ok ? "" : " bad") + "'>" + esc(r.action || "执行") + "</span>" +
        "<span class='im-ev-n' title='" + esc(raw) + "'>" + esc(name) + "</span>" +
        "<b class='im-ev-r' style='color:" + c + "'>" + esc(badge) + "</b>" +
        "</div>";
    }).join("");
  }

  function render(d) {
    if (!d || !d.ok) {
      var el = $("im-verdict");
      if (el) {
        el.style.borderLeftColor = LV.red;
        el.innerHTML = "<div class='im-v-head' style='color:" + LV.red + "'>读不到关系图</div>" +
          "<div class='im-v-body'>" + esc((d && d.error) || "接口没有返回") +
          (d && d.how ? "<br>" + esc(d.how) : "") + "</div>";
      }
      return;
    }
    lastData = d;
    var g = d.graph || {};
    var sub = $("im-sub");
    if (sub) {
      sub.textContent = "改一处之前先看一圈 · 图建于 " +
        (String(g.built_at || "").replace("T", " ") || "未知");
    }
    renderVerdict(d.verdict);
    renderNums(g);
    renderProbe(d.probe);
    renderBars(d.ranking);
    renderFeed(d.recent);
    var lg = $("im-legend");
    if (lg) lg.textContent = d.note || "";
  }

  function load(target) {
    var url = "/api/omni?op=impact";
    if (target) url += "&target=" + encodeURIComponent(target);
    var sub = $("im-sub");
    if (sub) sub.textContent = "正在读关系图…";
    fetch(url, { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(render)
      .catch(function (e) {
        var el = $("im-verdict");
        if (!el) return;
        el.style.borderLeftColor = LV.red;
        el.innerHTML = "<div class='im-v-head' style='color:" + LV.red + "'>连不上后端</div>" +
          "<div class='im-v-body'>" + esc(e && e.message ? e.message : "网络错误") + "</div>";
      });
  }

  var open = false;
  function setOpen(v) {
    open = !!v;
    var panel = $("impact-mon"), toggle = $("im-toggle");
    if (panel) panel.classList.toggle("collapsed", !open);
    if (toggle) toggle.style.display = open ? "none" : "";
    try { localStorage.setItem("gbt.impactBoardOpen", open ? "1" : "0"); } catch (e) {}
    if (open) load((($("im-path") || {}).value || "").trim());
  }

  function wire() {
    try { open = localStorage.getItem("gbt.impactBoardOpen") === "1"; } catch (e) { open = false; }
    setOpen(open);
    var toggle = $("im-toggle"), collapse = $("im-collapse"),
        refresh = $("im-refresh"), ask = $("im-ask");
    if (toggle) toggle.addEventListener("click", function () { setOpen(true); });
    if (collapse) collapse.addEventListener("click", function () { setOpen(false); });
    if (refresh) refresh.addEventListener("click", function () {
      load((($("im-path") || {}).value || "").trim());
    });
    if (ask) ask.addEventListener("submit", function (ev) {
      ev.preventDefault();
      load((($("im-path") || {}).value || "").trim());
    });
    if (open) load("");
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
  else wire();
})();
