/* 全链路视图 v2（2026-11-06 主人令 + agent-graph 设计模型）
 *
 * 照 jihe520/agent-graph 的设计标准做「宿主适配」（DESIGN.md「适配」一节）：
 *   项目   → 触手分组（界面 / 能力位 / 工具 / 文档 / 数据 / 其它）
 *   泳道   → 每组的竖列，列头写组名 + 条数 + 用量 + 状态计数
 *   agent  → 触手（tentacle），状态：运行中 / 最近用过 / 待用
 *   子 agent → 能力位（同一个触手挂的能力位）
 *   提交   → 运行链步骤（/api/turns 的 steps），「现在」段单独置顶
 *   会话侧栏 → 右侧推拉抽屉（460–560px，点卡片开、再点关）
 * 原则照抄三条：① graph 是主视图、会话从属；② 每个状态都对应真实数据；
 *              ③ 不能做就说原因（抽屉里如实写「无接口」而不是留空）。
 */
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var GROUPS = [
    { id: "ui", title: "界面 · holo_pet_w3", hint: "页面 / 面板 / 3D", test: function (p) { return p.indexOf("holo_pet_w3/") === 0; } },
    { id: "core", title: "能力位 · gbt_allinone", hint: "能力位本体与记忆链", test: function (p) { return p.indexOf("gbt_allinone/") === 0 && p.indexOf("gbt_allinone/docs/") !== 0; } },
    { id: "tools", title: "工具 · tools", hint: "CLI / codex-scripts", test: function (p) { return p.indexOf("tools/") === 0; } },
    { id: "docs", title: "文档 · docs", hint: "规范 / 契约", test: function (p) { return p.indexOf("gbt_allinone/docs/") === 0 || p.indexOf("docs/") === 0; } },
    { id: "state", title: "数据 · state", hint: "台账 / 绑定 / 记忆", test: function (p) { return p.indexOf("state/") === 0; } },
    { id: "other", title: "其它", hint: "外部 / 资产", test: function () { return true; } }
  ];
  var CATS = [
    { id: "talk", name: "对话与认知", desc: "跟她说的话 + 她怎么想", views: ["chat", "mind", "stream", "turns", "brain"] },
    { id: "cap", name: "能力与执行", desc: "427 位怎么用、怎么插", views: ["caps", "skills", "plug", "prof", "bounty"] },
    { id: "team", name: "触手与协作", desc: "谁跟谁连、扫到哪", views: ["team", "scan"] },
    { id: "media", name: "媒体与内容", desc: "图 / 视频 / 动态", views: ["media", "video", "moments"] },
    { id: "space", name: "空间与 3D", desc: "星图 / 世界 / 数字人", views: ["space", "world", "teardown"] },
    { id: "watch", name: "监视与诊断", desc: "心跳 / 链路 / 读数", views: ["dash", "flow", "browser"] }
  ];
  var RUN_WINDOW_MS = 300000;
  var MODEL = null, PICKED = null, timer = 0, EDGE_SVG = null;

  function el(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt != null) n.textContent = txt;
    return n;
  }
  function num(n) {
    n = Number(n) || 0;
    if (n >= 10000) return (Math.round(n / 100) / 100) + "w";
    if (n >= 1000) return (Math.round(n / 10) / 10) + "k";
    return String(n);
  }
  function groupOf(path) {
    for (var i = 0; i < GROUPS.length; i++) {
      if (GROUPS[i].id !== "other" && GROUPS[i].test(path)) return GROUPS[i].id;
    }
    return "other";
  }
  function statusOf(name, running, used) {
    if (running[name]) return "running";
    if (used[name]) return "ok";
    return "idle";
  }
  function statusText(s) {
    return s === "running" ? "运行中" : (s === "ok" ? "最近用过" : (s === "done" ? "完成" : "待用"));
  }

  function load() {
    return Promise.all([
      fetch("/api/tentacle?op=list", { cache: "no-store" }).then(function (r) { return r.json(); }).catch(function () { return {}; }),
      fetch("/api/turns?limit=40", { cache: "no-store" }).then(function (r) { return r.json(); }).catch(function () { return {}; }),
      fetch("/api/data", { cache: "no-store" }).then(function (r) { return r.json(); }).catch(function () { return {}; })
    ]).then(function (rs) {
      MODEL = build(rs[0] || {}, rs[1] || {}, (rs[2] || {}).data || {});
      render();
    });
  }

  function build(tent, turns, data) {
    var now = Date.now();
    var running = {}, used = {}, tasks = [];
    var traces = (turns && turns.traces) || [];
    traces.forEach(function (tr) {
      var steps = tr.steps || [];
      steps.forEach(function (st) {
        var cap = st.cap || st.kind || st.action || "";
        if (cap) used[cap] = true;
        var at = Date.parse(st.at || tr.start || "");
        if (isFinite(at) && (now - at) < RUN_WINDOW_MS) running[cap] = true;
      });
      var last = steps[steps.length - 1] || {};
      var at = Date.parse(last.at || tr.start || "");
      if (isFinite(at) && (now - at) < RUN_WINDOW_MS) {
        tasks.push({
          id: "task:" + (tr.id || tasks.length),
          name: last.cap || last.kind || "任务",
          session: tr.session || "",
          steps: steps.length,
          age: Math.max(0, Math.round((now - at) / 1000)),
          list: steps.map(function (s) { return (s.at || "") + "  " + (s.cap || s.action || s.kind || "step"); })
        });
      }
    });

    var tents = (tent.tentacles || []).slice().sort(function (a, b) { return b.count - a.count; });
    var assets = tent.assets || [];

    var cols = GROUPS.map(function (G) {
      var members = tents.filter(function (t) {
        var as = t.assets || [];
        if (!as.length) return G.id === "other";
        for (var i = 0; i < as.length; i++) if (groupOf(as[i]) === G.id) return true;
        return false;
      });
      var total = members.reduce(function (s, t) { return s + (Number(t.count) || 0); }, 0);
      var top = members.slice(0, 9).map(function (t) {
        return {
          id: t.name, name: t.name, kind: t.kind || "触手",
          count: Number(t.count) || 0, assets: t.assets || [],
          status: statusOf(t.name, running, used)
        };
      });
      var counts = { running: 0, ok: 0, idle: 0 };
      members.forEach(function (t) { counts[statusOf(t.name, running, used)]++; });
      return { id: G.id, title: G.title, hint: G.hint, total: total, members: members.length, counts: counts, cards: top, more: members.length - top.length };
    });

    var nodeSet = {};
    cols.forEach(function (c) { c.cards.forEach(function (x) { nodeSet[x.id] = x.assets; }); });
    var ids = Object.keys(nodeSet), edges = [];
    for (var i = 0; i < ids.length; i++) {
      for (var j = i + 1; j < ids.length; j++) {
        var a = nodeSet[ids[i]], b = nodeSet[ids[j]];
        if (!a.length || !b.length) continue;
        var small = a.length < b.length ? a : b, big = a.length < b.length ? b : a, shared = 0;
        for (var k = 0; k < small.length; k++) if (big.indexOf(small[k]) >= 0) shared++;
        if (shared >= 2) edges.push({ a: ids[i], b: ids[j], w: shared });
      }
    }
    edges.sort(function (x, y) { return y.w - x.w; });

    return {
      cols: cols, tasks: tasks, edges: edges.slice(0, 80),
      stats: {
        caps: (data.caps && data.caps.total) || 0,
        tentacles: tents.length,
        assets: assets.length,
        pairs: (tent.stats && tent.stats.pairs) || 0,
        bound: (tent.stats && tent.stats.caps_bound) || 0,
        running: tasks.length,
        traces: traces.length,
        runningTentacles: Object.keys(running).length
      }
    };
  }

  function render() {
    renderStats();
    renderNow();
    renderCols();
    renderCategories();
    drawEdges();
    if (PICKED) renderDrawer(PICKED);
  }

  function renderStats() {
    var box = $("flow-stats");
    if (!box) return;
    var s = MODEL.stats;
    box.innerHTML = "";
    [["能力位", s.caps, "已绑 " + s.bound], ["触手", s.tentacles, "资产 " + s.assets],
     ["绑定对", s.pairs, "链 " + s.traces], ["运行中", s.running, "触手 " + s.runningTentacles]
    ].forEach(function (it) {
      var c = el("div", "flow-stat");
      c.appendChild(el("div", "flow-stat-n", num(it[1])));
      c.appendChild(el("div", "flow-stat-k", it[0] + " · " + it[2]));
      box.appendChild(c);
    });
    var sub = $("flow-sub");
    if (sub) sub.textContent = s.tentacles + " 条触手 · " + s.assets + " 个资产 · 每 6s 刷新";
    var leg = $("flow-legend");
    if (leg) {
      leg.innerHTML = "";
      [["running", "运行中"], ["ok", "最近用过"], ["idle", "待用"]].forEach(function (it) {
        var sp = el("span", "flow-pill st-" + it[0]);
        sp.appendChild(el("i", "flow-leg-dot"));
        sp.appendChild(el("b", "", it[1]));
        leg.appendChild(sp);
      });
    }
  }

  function renderNow() {
    var box = $("flow-now-list");
    var band = $("flow-now");
    if (!box || !band) return;
    box.innerHTML = "";
    var tasks = MODEL.tasks;
    band.classList.toggle("is-empty", !tasks.length);
    if (!tasks.length) {
      box.appendChild(el("div", "flow-now-empty", "最近 5 分钟没有正在执行的任务（链会随对话自动出现）"));
      return;
    }
    tasks.slice(0, 8).forEach(function (t) {
      var c = el("button", "flow-task");
      c.type = "button";
      c.appendChild(el("span", "flow-task-dot"));
      var main = el("div", "flow-task-main");
      main.appendChild(el("div", "flow-task-name", t.name));
      main.appendChild(el("div", "flow-task-sub", t.session + " · " + t.steps + " 步"));
      c.appendChild(main);
      c.appendChild(el("span", "flow-task-age", t.age < 1 ? "刚刚" : t.age + "s 前"));
      c.addEventListener("click", function () {
        openDrawer({ id: t.id, name: t.name, kind: "运行链", count: t.steps, assets: t.list, status: "running" });
      });
      box.appendChild(c);
    });
  }

  function renderCols() {
    var wrap = $("flow-cols");
    if (!wrap) return;
    wrap.innerHTML = "";
    MODEL.cols.forEach(function (c) {
      var col = el("section", "flow-col");
      var head = el("div", "flow-col-head");
      head.appendChild(el("div", "flow-col-title", c.title));
      head.appendChild(el("div", "flow-col-sub", c.members + " 条 · " + num(c.total) + " 次 · " + c.hint));
      var pills = el("div", "flow-col-pills");
      if (c.counts.running) pills.appendChild(el("span", "flow-pill st-running", "运行 " + c.counts.running));
      if (c.counts.ok) pills.appendChild(el("span", "flow-pill st-ok", "用过 " + c.counts.ok));
      pills.appendChild(el("span", "flow-pill st-idle", "待用 " + c.counts.idle));
      head.appendChild(pills);
      col.appendChild(head);

      c.cards.forEach(function (card) {
        var row = el("button", "flow-card st-" + card.status);
        row.type = "button";
        row.setAttribute("data-node", card.id);
        row.appendChild(el("span", "flow-bead"));
        var main = el("div", "flow-card-main");
        var t = el("div", "flow-card-title");
        t.appendChild(el("span", "flow-card-name", card.name));
        t.appendChild(el("span", "flow-pill st-" + card.status, statusText(card.status)));
        main.appendChild(t);
        main.appendChild(el("div", "flow-card-sub", num(card.count) + " 次 · " + card.assets.length + " 资产"));
        row.appendChild(main);
        row.appendChild(el("span", "flow-card-n", num(card.count)));
        row.addEventListener("click", function () { pick(card); });
        col.appendChild(row);
      });
      if (c.more > 0) {
        var more = el("button", "flow-card flow-more");
        more.type = "button";
        more.appendChild(el("span", "flow-bead"));
        more.appendChild(el("span", "flow-card-name", "+" + c.more + " 条触手"));
        more.addEventListener("click", function () {
          openDrawer({ id: c.id + ":more", name: c.title + " · 其余", kind: "分组", count: c.total, assets: [], status: "idle", hint: c.members + " 条全部见「触手协作」页" });
        });
        col.appendChild(more);
      }
      wrap.appendChild(col);
    });
  }

  function pick(card) {
    PICKED = card;
    Array.prototype.forEach.call(document.querySelectorAll(".flow-card"), function (n) {
      n.classList.toggle("is-on", n.getAttribute("data-node") === card.id);
    });
    openDrawer(card);
    drawEdges(card.id);
  }

  function openDrawer(node) {
    var d = $("flow-drawer");
    if (!d) return;
    d.classList.add("is-open");
    d.setAttribute("aria-hidden", "false");
    renderDrawer(node);
  }
  function closeDrawer() {
    PICKED = null;
    var d = $("flow-drawer");
    if (!d) return;
    d.classList.remove("is-open");
    d.setAttribute("aria-hidden", "true");
    Array.prototype.forEach.call(document.querySelectorAll(".flow-card"), function (n) { n.classList.remove("is-on"); });
    drawEdges();
  }

  function renderDrawer(node) {
    var t = $("flow-drawer-title"), b = $("flow-drawer-body");
    if (!t || !b) return;
    t.textContent = node.name;
    b.innerHTML = "";
    var kv = el("div", "flow-kv");
    [["状态", statusText(node.status)], ["用量", num(node.count) + " 次"], ["类型", node.kind || "—"],
     ["绑定资产", String((node.assets || []).length) + " 个"]].forEach(function (it) {
      var row = el("div", "flow-kv-row");
      row.appendChild(el("b", "", it[0]));
      row.appendChild(el("span", "", it[1]));
      kv.appendChild(row);
    });
    b.appendChild(kv);
    if (node.hint) b.appendChild(el("div", "flow-note", node.hint));
    if ((node.assets || []).length) {
      b.appendChild(el("div", "flow-h", "资产 · 前 40 个"));
      var list = el("div", "flow-assets");
      node.assets.slice(0, 40).forEach(function (a) { list.appendChild(el("div", "flow-asset", a)); });
      b.appendChild(list);
    } else if (node.kind !== "运行链") {
      b.appendChild(el("div", "flow-note", "这个节点没有直接绑定的资产（聚合节点）。"));
    }
    var acts = el("div", "flow-acts");
    var goCaps = el("button", "flow-act", "在功能表里查这个触手");
    goCaps.type = "button";
    goCaps.addEventListener("click", function () {
      var tab = document.querySelector('.view-tab[data-view="caps"]');
      if (tab) tab.click();
      var s = $("cap-search");
      if (s) { s.value = node.name; s.dispatchEvent(new Event("input", { bubbles: true })); }
    });
    acts.appendChild(goCaps);
    var goTeam = el("button", "flow-act", "看它的绑定（触手协作）");
    goTeam.type = "button";
    goTeam.addEventListener("click", function () {
      var tab = document.querySelector('.view-tab[data-view="team"]');
      if (tab) tab.click();
    });
    acts.appendChild(goTeam);
    b.appendChild(acts);
  }

  function drawEdges(focusId) {
    var host = $("flow-cols");
    if (!host) return;
    var old = $("flow-edge-svg");
    if (old && old.parentNode) old.parentNode.removeChild(old);
    if (!MODEL || !MODEL.edges.length) return;
    var rect = host.getBoundingClientRect();
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("id", "flow-edge-svg");
    svg.setAttribute("class", "flow-edge-svg");
    svg.setAttribute("width", host.scrollWidth);
    svg.setAttribute("height", rect.height);
    var cards = {};
    Array.prototype.forEach.call(host.querySelectorAll(".flow-card[data-node]"), function (n) {
      var r = n.getBoundingClientRect();
      cards[n.getAttribute("data-node")] = {
        x: r.left - rect.left + host.scrollLeft, y: r.top - rect.top + r.height / 2
      };
    });
    MODEL.edges.forEach(function (e) {
      var A = cards[e.a], B = cards[e.b];
      if (!A || !B) return;
      var on = focusId && (e.a === focusId || e.b === focusId);
      var mx = (A.x + B.x) / 2;
      var p = document.createElementNS("http://www.w3.org/2000/svg", "path");
      p.setAttribute("d", "M" + A.x + "," + A.y + " Q" + mx + "," + ((A.y + B.y) / 2) + " " + B.x + "," + B.y);
      p.setAttribute("class", "flow-edge" + (on ? " is-on" : ""));
      p.setAttribute("stroke-width", (0.8 + Math.min(3.2, e.w * 0.5)).toFixed(2));
      svg.appendChild(p);
    });
    host.appendChild(svg);
  }

  function renderCategories() {
    var grid = $("flow-page-grid"), bar = $("flow-pages-bar"), sub = $("flow-pages-sub");
    if (!grid || !bar) return;
    var tabs = Array.prototype.slice.call(document.querySelectorAll(".view-tab[data-view]"))
      .map(function (b) { return { id: b.getAttribute("data-view"), label: (b.textContent || "").trim() }; });
    var byId = {};
    tabs.forEach(function (t) { byId[t.id] = t; });
    var seen = {};
    var cats = CATS.map(function (c) {
      var pages = c.views.map(function (v) { return byId[v]; }).filter(Boolean);
      pages.forEach(function (p) { seen[p.id] = true; });
      return { id: c.id, name: c.name, desc: c.desc, pages: pages };
    });
    var rest = tabs.filter(function (t) { return !seen[t.id]; });
    if (rest.length) cats.push({ id: "rest", name: "其它页面", desc: "暂未归类", pages: rest });
    var total = tabs.length || 1;
    sub.textContent = tabs.length + " 个页面 · " + cats.length + " 类";
    bar.innerHTML = CATS.length ? "" : "";
    cats.forEach(function (c) {
      var seg = el("span", "flow-bar-seg");
      seg.style.flex = String(Math.max(1, c.pages.length));
      seg.setAttribute("title", c.name + " · " + c.pages.length + " 页");
      bar.appendChild(seg);
    });
    grid.innerHTML = "";
    cats.forEach(function (c) {
      var pct = Math.round((c.pages.length / total) * 1000) / 10;
      var card = el("section", "flow-page-card");
      var head = el("div", "flow-page-head");
      head.appendChild(el("span", "flow-page-name", c.name));
      head.appendChild(el("span", "flow-page-pct", pct + "%"));
      card.appendChild(head);
      card.appendChild(el("div", "flow-page-desc", c.desc));
      var meter = el("div", "flow-page-meter");
      var fill = el("span", "flow-page-fill");
      fill.style.width = Math.max(3, pct) + "%";
      meter.appendChild(fill);
      card.appendChild(meter);
      var list = el("div", "flow-page-list");
      c.pages.forEach(function (p) {
        var chip = el("button", "flow-chip");
        chip.type = "button";
        chip.textContent = p.label.replace(/\s*\d+$/, "").trim();
        chip.addEventListener("click", function () {
          var tab = document.querySelector('.view-tab[data-view="' + p.id + '"]');
          if (tab) tab.click();
        });
        list.appendChild(chip);
      });
      card.appendChild(list);
      grid.appendChild(card);
    });
  }

  function start() {
    var r = $("flow-refresh");
    if (r && !r.__bound) { r.__bound = true; r.addEventListener("click", function () { load(); }); }
    var c = $("flow-drawer-close");
    if (c && !c.__bound) { c.__bound = true; c.addEventListener("click", closeDrawer); }
    load();
    if (timer) window.clearInterval(timer);
    timer = window.setInterval(function () {
      var con = document.getElementById("chat-area");
      if (con && con.getAttribute("data-view") === "flow") load();
    }, 6000);
    window.addEventListener("resize", function () { if (MODEL) drawEdges(PICKED && PICKED.id); });
  }
  function stop() {
    if (timer) { window.clearInterval(timer); timer = 0; }
  }

  window.gbtFlow = { start: start, stop: stop, _build: build, _cats: CATS, _groups: GROUPS };
})();