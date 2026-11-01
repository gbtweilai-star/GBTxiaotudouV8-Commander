/* GBT小土豆V8 · 认知界面逻辑
 * 数据：优先 /api/data（console-server 现读）；直开 file:// 时退回 window.GBT_CONSOLE。
 * 对话：/api/chat → energy_core.think(context="console-web")（无限上下文 + temperature=0 稳定输出）。
 */
(function () {
  "use strict";

  var MODE = { online: false, data: null };
  var $ = function (id) { return document.getElementById(id); };
  var el = function (tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };

  function nowStr() {
    var d = new Date();
    return d.toTimeString().slice(0, 8);
  }

  /* ───────── 数据 ───────── */
  function fallback() {
    return (window.GBT_CONSOLE && window.GBT_CONSOLE) || {
      generated_at: "—", caps: { total: 0, safe: 0, unsafe: 0, check: {}, docs: "?" },
      skills: { count: 0, validate: "?", names: [] },
      engine: { alive: false }, meter: {}, guards: {},
      domains: [], flow: [], ledger: [], note: "无数据"
    };
  }

  function loadData() {
    // 先渲染内联快照（有 <script src=state/console-data.js> 就有数据）——
    // 这样即使 /api/data 慢/挂，页面也不会空白。
    MODE.data = fallback();
    render(MODE.data);
    if (location.protocol === "file:") return;
    fetch("/api/data", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (j && j.ok && j.data) { MODE.online = true; MODE.data = j.data; render(j.data); }
        else throw new Error((j && j.error) || "无数据");
      })
      .catch(function (e) {
        MODE.data = fallback();
        render(MODE.data);
        addBot("⚠ 读不到实时数据（" + e.message + "），显示的是内联快照。起服务：python tools/console-server.py");
      });
  }

  /* ───────── 左栏 ───────── */
  function renderLeft(d) {
    $("pill-l1").textContent = MODE.online ? "实时" : "快照";
    var alive0 = !!(d.engine && d.engine.alive);
    var ia = $("ai-activity");
    if (ia) ia.setAttribute("data-state", alive0 ? "busy" : "idle");
    $("ai-activity-label").textContent = alive0 ? "在线 · 本机指挥官" : "离线";
    $("ai-activity-detail").textContent =
      (d.engine && d.engine.weights ? d.engine.weights : "—") + " · ctx 无限";

    // 图例：域
    var lg = $("legend");
    lg.innerHTML = "";
    (d.domains || []).slice(0, 10).forEach(function (x) {
      lg.appendChild(el("span", "chip", x.domain + " " + x.count));
    });

    // 流：守卫 + 引擎 + 技能
    var si = $("si-l1");
    si.innerHTML = "";
    var guards = d.guards || {};
    Object.keys(guards).forEach(function (k) {
      var v = String(guards[k] || "?").toLowerCase();
      var cls = v === "clean" ? "ok" : (v ? "bad" : "warn");
      var row = el("div", "ev " + cls);
      row.appendChild(el("span", "dot"));
      var body = el("div", null, "");
      var b = el("b", null, k);
      body.appendChild(b);
      body.appendChild(document.createTextNode(" · " + (guards[k] || "未读")));
      row.appendChild(body);
      si.appendChild(row);
    });
    (d.skills && d.skills.names ? d.skills.names : []).slice(0, 8).forEach(function (n) {
      var row = el("div", "ev");
      row.appendChild(el("span", "dot"));
      var body = el("div");
      body.appendChild(el("b", null, "skill"));
      body.appendChild(document.createTextNode(" · " + n));
      row.appendChild(body);
      si.appendChild(row);
    });

    // 图谱
    drawGraph(d.domains || []);
  }

  /* ───────── 图谱：域节点绕中心排布 ───────── */
  function drawGraph(domains) {
    var svg = $("graph");
    if (!domains.length) return;
    var W = window.innerWidth, H = window.innerHeight;
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.innerHTML = "";
    var NS = "http://www.w3.org/2000/svg";
    var cx = W * 0.52, cy = H * 0.48, R = Math.min(W, H) * 0.26;
    var max = domains[0].count || 1;
    var center = document.createElementNS(NS, "circle");
    center.setAttribute("cx", cx); center.setAttribute("cy", cy);
    center.setAttribute("r", 26); center.setAttribute("fill", "rgba(232,176,106,.10)");
    center.setAttribute("stroke", "rgba(232,176,106,.35)");
    svg.appendChild(center);
    domains.forEach(function (d, i) {
      var a = (i / domains.length) * Math.PI * 2 - Math.PI / 2;
      var x = cx + Math.cos(a) * R, y = cy + Math.sin(a) * R;
      var r = 5 + (d.count / max) * 16;
      var line = document.createElementNS(NS, "line");
      line.setAttribute("x1", cx); line.setAttribute("y1", cy);
      line.setAttribute("x2", x); line.setAttribute("y2", y);
      line.setAttribute("stroke", "rgba(255,255,255,.08)");
      svg.appendChild(line);
      var c = document.createElementNS(NS, "circle");
      c.setAttribute("cx", x); c.setAttribute("cy", y); c.setAttribute("r", r);
      c.setAttribute("fill", i % 3 === 0 ? "rgba(232,176,106,.55)" : "rgba(110,168,254,.45)");
      c.setAttribute("stroke", "rgba(255,255,255,.15)");
      svg.appendChild(c);
      var t = document.createElementNS(NS, "text");
      t.setAttribute("x", x); t.setAttribute("y", y + r + 12);
      t.setAttribute("fill", "rgba(236,233,228,.55)");
      t.setAttribute("font-size", "10");
      t.setAttribute("font-family", "monospace");
      t.setAttribute("text-anchor", "middle");
      t.textContent = d.domain + " " + d.count;
      svg.appendChild(t);
    });
  }

  /* ───────── 右栏 ───────── */
  function renderRight(d) {
    var caps = d.caps || {};
    var gs = d.guards || {};
    var cleanN = Object.keys(gs).filter(function (k) {
      return String(gs[k] || "").toLowerCase().indexOf("clean") >= 0;
    }).length;
    $("stat-caps").textContent = caps.total || "—";
    $("stat-skills").textContent = (d.skills && d.skills.count) || "—";
    $("stat-guards").textContent = cleanN + "/" + Object.keys(gs).length;
    $("stat-toks").textContent = (d.meter && d.meter.power_tok_s) || "—";
    $("stat-ledger").textContent = (d.flow && d.flow.length) || 0;

    var st = $("hb-state");
    var alive = d.engine && d.engine.alive;
    st.setAttribute("data-state", alive ? "live" : "waiting");
    var hbNow = new Date();
    $("hb-last").textContent = (MODE.online ? "实时 · " : "快照 · ") + hbNow.toTimeString().slice(0, 8);
    $("hb-state-label").textContent = alive ? "本机引擎在线" : "离线";
    $("hb-count").textContent = (d.meter && d.meter.calls) || 0;
    $("hb-last").textContent = "读数 " + (d.generated_at || "—");

    // 波形：用能力数做振幅（数据驱动，不是装饰随机）
    var w = $("hb-wave");
    var amp = Math.max(8, Math.min(26, (caps.total || 20) / 20));
    var pts = [];
    for (var x = 0; x <= 320; x += 4) {
      var y = 36 - Math.sin((x / 320) * Math.PI * 6) * amp * (0.5 + 0.5 * Math.sin(x / 47));
      pts.push((x === 0 ? "M" : "L") + x + " " + y.toFixed(1));
    }
    w.setAttribute("d", pts.join(" "));
    var mon = document.querySelector(".heartbeat-monitor");
    if (mon) {
      mon.removeAttribute("data-beat");
      void mon.offsetWidth;           // 重启动画
      mon.setAttribute("data-beat", "minor");
    }

    // 行动日志
    var al = $("action-log");
    al.innerHTML = "";
    var flow = d.flow || [];
    if (!flow.length) al.appendChild(el("div", "empty", "最近编排会显示在这里"));
    flow.slice(-8).reverse().forEach(function (r) {
      var row = el("div", "action-row");
      row.appendChild(el("span", "t", (r.at || "").slice(11, 19)));
      var body = el("span");
      body.appendChild(el("span", "k", (r.action || "?")));
      body.appendChild(document.createTextNode(" " + (r.target || "")));
      body.appendChild(el("span", "g", " · " + String(r.result || "").slice(0, 42)));
      row.appendChild(body);
      al.appendChild(row);
    });

    // 思考与工具：守卫 + 引擎 + 上下文
    var si2 = $("si-l2");
    si2.innerHTML = "";
    Object.keys(gs).forEach(function (k) {
      var row = el("div", "ev " + (String(gs[k]).toLowerCase() === "clean" ? "ok" : "bad"));
      row.appendChild(el("span", "dot"));
      var body = el("div");
      body.appendChild(el("b", null, k));
      body.appendChild(document.createTextNode(" · " + gs[k]));
      row.appendChild(body);
      si2.appendChild(row);
    });
    var eng = el("div", "ev " + (alive ? "ok" : "bad"));
    eng.appendChild(el("span", "dot"));
    var b2 = el("div");
    b2.appendChild(el("b", null, "engine"));
    b2.appendChild(document.createTextNode(" · " + ((d.engine && d.engine.weights) || "无") +
      " · " + (alive ? "无限制上下文 · temperature=0 稳定输出" : "离线")));
    eng.appendChild(b2);
    si2.appendChild(eng);
    var cs = $("cog-state");
    cs.setAttribute("data-state", alive ? "live" : "idle");
    cs.textContent = alive ? "在线" : "待命";
  }

  /* ───────── 对话 ───────── */
  function addMsg(role, text, meta) {
    var box = $("chat-messages");
    var m = el("div", "msg " + role);
    m.textContent = text;
    if (meta) m.appendChild(el("div", "meta", meta));
    box.appendChild(m);
    var con = document.getElementById("chat-area");
    if (con) con.classList.add("has-msgs");
    $("chat-history").scrollTop = $("chat-history").scrollHeight;
    return m;
  }

  function addBot(text, meta) { return addMsg("bot", text, meta); }

  function chatSubmit(text) {
    addMsg("user", text);
    var btn = document.querySelector(".send-btn");
    btn.disabled = true;
    var pending = addBot("…");
    if (!MODE.online) {
      pending.remove();
      addBot("（演示模式：直开 file:// 不能调本机引擎。\n起服务后即可真对话：python tools/console-server.py，然后打开 http://127.0.0.1:8766/）\n\n本机模型：无限制上下文（有界窗口 + 全量可检索）· 稳定输出（temperature=0）。",
        "file:// · 未连接");
      btn.disabled = false;
      return;
    }
    fetch("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text, context: "console-web" })
    }).then(function (r) { return r.json(); }).then(function (j) {
      pending.remove();
      if (j && j.ok) {
        var meta = (j.usage ? j.usage.completion_tokens + " tok · " : "") +
          (j.ms != null ? j.ms + "ms · " : "") + "temperature=0";
        var ring = j.ring || {};
        meta += " · 上下文 seq " + (ring.seq != null ? ring.seq : "?") +
          " / 历史 " + (ring.db_turns != null ? ring.db_turns : "?") + " 轮";
        addBot(String(j.text || "").trim() || "(空回答)", meta);
      } else {
        addBot("⚠ " + ((j && j.error) || "调用失败"), "如实报错");
      }
    }).catch(function (e) {
      pending.remove();
      addBot("⚠ 请求失败：" + e.message, "网络错误");
    }).then(function () { btn.disabled = false; });
  }

  function wire() {
    $("chat-composer").addEventListener("submit", function (e) {
      e.preventDefault();
      var t = $("chat-input").value.trim();
      if (!t) return;
      $("chat-input").value = "";
      chatSubmit(t);
    });
    $("chat-input").addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        $("chat-composer").dispatchEvent(new Event("submit", { cancelable: true }));
      }
    });
    $("refresh-btn").addEventListener("click", function () { loadData(); });
    $("reset-view-btn").addEventListener("click", function () {
      document.body.classList.toggle("graph-on");
      drawGraph((MODE.data && MODE.data.domains) || []);
    });
    $("voice-btn").addEventListener("click", function () {
      addBot("语音入口在壳的 connect 页（ASR/TTS 未在这页接）。", "占位");
    });
    $("settings-btn").addEventListener("click", function () {
      addBot("设置：模型/语音/社交在壳的 connect 页；本页只读状态。", "占位");
    });
    var tb = $("titlebar-time");
    if (tb) tb.textContent = nowStr();
  }

  function render(d) {
    var mc = $("model-chip");
    if (mc) {
      var eng = d.engine || {};
      mc.textContent = "本机指挥官 · " + (eng.weights || "无权重") + " · 无限上下文";
    }
    renderLeft(d);
    renderRight(d);
    var f = $("footer-at");
    if (f) f.textContent = d.generated_at || "—";
    var sub = $("console-sub");
    if (sub) {
      sub.textContent = "本机指挥官 · " +
        ((d.engine && d.engine.base) || "127.0.0.1:8792") +
        " · 无限制上下文 · 稳定输出(temperature=0)" +
        (MODE.online ? " · 实时" : " · 快照");
    }
    renderCaps(d);
    renderSkills(d);
    renderProfessions(d);
    wireProfRoute();
    renderDash(d);
    var cs = $("caps-sub"), ss = $("skills-sub");
    if (cs) cs.textContent = (d.caps && d.caps.total) + " 位 · " + ((d.domains && d.domains.length) || 0) + " 域";
    if (ss) ss.textContent = (d.skills && d.skills.count) + " 个 · " + ((d.skills && d.skills.validate) || "?");
    var cn = $("tab-caps-n"), sn = $("tab-skills-n");
    if (cn) cn.textContent = (d.caps && d.caps.total) || "";
    if (sn) sn.textContent = (d.skills && d.skills.count) || "";

    // 开场欢迎（只一次）
    if (!$("chat-messages").childElementCount) {
      addBot("我是 GBT小土豆V8 的认知界面。左边是她的能力与流水，中间是对话，右边是心跳/行动/守卫。\n" +
        "本机指挥官：无限制上下文（模型只看一屏、全量可检索）· 稳定输出（temperature=0）。",
        MODE.online ? "online" : "snapshot");
    }
  }


  /* ───────── 功能表（385 位，可搜可筛） ───────── */
  function renderCaps(d) {
    var items = (d.caps && d.caps.items) || [];
    var sel = $("cap-domain");
    if (sel && !sel.dataset.filled) {
      var doms = {};
      items.forEach(function (x) { doms[x.domain] = (doms[x.domain] || 0) + 1; });
      Object.keys(doms).sort().forEach(function (k) {
        var o = document.createElement("option");
        o.value = k; o.textContent = k + " (" + doms[k] + ")";
        sel.appendChild(o);
      });
      sel.dataset.filled = "1";
    }
    function draw() {
      var q = ($("cap-search") && $("cap-search").value || "").trim().toLowerCase();
      var dm = ($("cap-domain") && $("cap-domain").value) || "";
      var rows = $("cap-rows"); if (!rows) return;
      rows.innerHTML = "";
      var n = 0;
      items.forEach(function (x) {
        if (dm && x.domain !== dm) return;
        if (q && (x.name + " " + x.desc + " " + x.domain).toLowerCase().indexOf(q) < 0) return;
        n++;
        if (n > 400) return;
        var tr = document.createElement("tr");
        var td1 = document.createElement("td"); td1.className = "cap-name"; td1.textContent = x.name;
        var td2 = document.createElement("td"); td2.className = "cap-domain"; td2.textContent = x.domain;
        var td3 = document.createElement("td");
        var g = document.createElement("span");
        g.className = "cap-gate " + (x.safe ? "safe" : "gated");
        g.textContent = x.safe ? "只读" : "需授权";
        td3.appendChild(g);
        var td4 = document.createElement("td"); td4.className = "cap-desc"; td4.textContent = x.desc;
        tr.appendChild(td1); tr.appendChild(td2); tr.appendChild(td3); tr.appendChild(td4);
        rows.appendChild(tr);
      });
      var em = $("cap-empty"); if (em) em.hidden = n > 0;
    }
    draw();
    if (!$("cap-search").dataset.bound) {
      $("cap-search").addEventListener("input", draw);
      $("cap-domain").addEventListener("change", draw);
      $("cap-search").dataset.bound = "1";
    }
  }

  /* ───────── 技能栏（23 个卡） ───────── */
  function renderSkills(d) {
    var items = (d.skills && d.skills.items) || [];
    var grid = $("skill-grid"); if (!grid) return;
    function draw() {
      var q = ($("skill-search") && $("skill-search").value || "").trim().toLowerCase();
      grid.innerHTML = "";
      var n = 0;
      items.forEach(function (x) {
        if (q && (x.name + " " + (x.desc || "") + " " + (x.source || "")).toLowerCase().indexOf(q) < 0) return;
        n++;
        var card = document.createElement("div"); card.className = "skill-card";
        var h3 = document.createElement("h3"); h3.textContent = x.name;
        var p = document.createElement("p"); p.textContent = x.desc || "";
        var meta = document.createElement("div"); meta.className = "skill-meta";
        var ok = document.createElement("span"); ok.className = "skill-pill ok"; ok.textContent = "合规";
        meta.appendChild(ok);
        var src = document.createElement("span"); src.className = "skill-pill";
        src.textContent = x.source ? "来源: superpowers-zh" : "原生";
        meta.appendChild(src);
        if (x.refs && x.refs.length) {
          var rf = document.createElement("span"); rf.className = "skill-pill";
          rf.textContent = "refs " + x.refs.length;
          meta.appendChild(rf);
        }
        card.appendChild(h3); card.appendChild(p); card.appendChild(meta);
        grid.appendChild(card);
      });
      var em = $("skill-empty"); if (em) em.hidden = n > 0;
    }
    draw();
    if ($("skill-search") && !$("skill-search").dataset.bound) {
      $("skill-search").addEventListener("input", draw);
      $("skill-search").dataset.bound = "1";
    }
  }

  /* ───────── 仪表盘（域分布 / 门占比 / 守卫 / 流水） ───────── */
  function renderDash(d) {
    var doms = (d.domains || []).slice(0, 14);
    var max = doms.length ? doms[0].count : 1;
    var bars = $("dash-bars");
    if (bars) {
      bars.innerHTML = "";
      doms.forEach(function (x) {
        var row = document.createElement("div"); row.className = "bar-row";
        var nm = document.createElement("span"); nm.className = "bar-name"; nm.textContent = x.domain;
        var tr = document.createElement("span"); tr.className = "bar-track";
        var fi = document.createElement("span"); fi.className = "bar-fill";
        fi.style.width = Math.max(3, Math.round(x.count / max * 100)) + "%";
        tr.appendChild(fi);
        var nn = document.createElement("span"); nn.className = "bar-n"; nn.textContent = x.count;
        row.appendChild(nm); row.appendChild(tr); row.appendChild(nn);
        bars.appendChild(row);
      });
    }
    var caps = d.caps || {};
    var total = caps.total || 1, safe = caps.safe || 0;
    var pct = Math.round(safe / total * 100);
    var donut = $("dash-donut");
    if (donut) donut.style.background = "conic-gradient(var(--ok) 0 " + pct + "%, var(--warn) " + pct + "% 100%)";
    var gsub = $("dash-gate-sub"); if (gsub) gsub.textContent = safe + " 只读 / " + (total - safe) + " 需授权";
    var lg = $("dash-gate-legend");
    if (lg) {
      lg.innerHTML = "";
      [["var(--ok)", "只读 " + safe + "（" + pct + "%）"],
       ["var(--warn)", "需授权 " + (total - safe) + "（" + (100 - pct) + "%）"]].forEach(function (x) {
        var row = document.createElement("div");
        var i = document.createElement("i"); i.style.background = x[0];
        row.appendChild(i); row.appendChild(document.createTextNode(x[1]));
        lg.appendChild(row);
      });
    }
    var kv = $("dash-kv");
    if (kv) {
      var g = d.guards || {};
      var gh = Object.keys(g).map(function (k) { return k + ":<b>" + g[k] + "</b>"; }).join("　");
      kv.innerHTML = "<div>能力位：<b>" + total + "</b></div>" +
        "<div>技能：<b>" + ((d.skills && d.skills.count) || 0) + "</b></div>" +
        "<div>引擎：<b>" + ((d.engine && d.engine.alive) ? "在线" : "离线") + "</b></div>" +
        "<div>权重：<b>" + ((d.engine && d.engine.weights) || "—") + "</b></div>" +
        "<div style='grid-column:1/-1'>守卫：" + gh + "</div>";
    }
    var flow = d.flow || [];
    var fsub = $("dash-flow-sub"); if (fsub) fsub.textContent = flow.length + " 条";
    var fbox = $("dash-flow");
    if (fbox) {
      fbox.innerHTML = "";
      flow.slice(-10).reverse().forEach(function (r) {
        var row = document.createElement("div"); row.className = "row";
        var t = document.createElement("span"); t.textContent = (r.at || "").slice(11, 19);
        var b = document.createElement("span");
        var k = document.createElement("b"); k.textContent = (r.action || "?");
        b.appendChild(k);
        b.appendChild(document.createTextNode(" " + (r.target || "") + " · " + String(r.result || "").slice(0, 40)));
        row.appendChild(t); row.appendChild(b);
        fbox.appendChild(row);
      });
    }
  }

  /* ───────── 职业视图：12 种触手职业（编程为首席） ───────── */
  function renderProfessions(d) {
    var wrap = $("prof-grid");
    var box = d && d.professions;
    var items = (box && box.professions) || [];
    document.documentElement.dataset.prof =
      "ok:" + items.length + "职业" + (items.some(function (p) { return p.chief; }) ? "+编程首席" : "");
    var titleEl = $("prof-title");
    var cov = box && box.coverage;
    if (titleEl) {
      titleEl.textContent = "触手职业 · " + items.length + " 种职业（编程工程师为首席）"
        + (cov ? " · 覆盖 " + cov.caps_covered + "/" + cov.caps_total + " 能力位" : "");
    }
    var subEl = $("prof-sub");
    if (subEl && cov) {
      subEl.textContent = "域覆盖 " + cov.domains_covered + "/" + cov.domains_total
        + " · 孤儿能力位 " + (cov.orphans || []).length
        + (cov.flex_caps ? (" · 机动补位 " + cov.flex_caps) : " · 无补位（全部显式归属）")
        + " · 一个能力位可属多职业";
    }
    if (!wrap) return;
    wrap.innerHTML = "";
    items.forEach(function (p) {
      var card = document.createElement("section");
      card.className = "prof-card" + (p.chief ? " is-chief" : "");
      var url = "https://github.com/gbtweilai-star/GBTxiaotudouV8-Commander";
      card.innerHTML = "";
      var top = document.createElement("div");
      top.className = "prof-top";
      var ti = document.createElement("span");
      ti.className = "prof-title";
      ti.textContent = p.title + (p.chief ? "（首席）" : "");
      top.appendChild(ti);
      if (p.chief) {
        var pill = document.createElement("span");
        pill.className = "prof-chief-pill";
        pill.textContent = "CHIEF";
        top.appendChild(pill);
      }
      var cnt = document.createElement("span");
      cnt.className = "prof-count";
      cnt.textContent = (p.cap_count || 0) + " 能力位";
      top.appendChild(cnt);
      card.appendChild(top);

      var head = document.createElement("div");
      head.className = "prof-line";
      head.textContent = p.headline || "";
      card.appendChild(head);

      var kv = document.createElement("div");
      kv.className = "prof-kv";
      function row(k, v) {
        var b = document.createElement("b"); b.textContent = k; kv.appendChild(b);
        var s2 = document.createElement("span"); s2.textContent = v; kv.appendChild(s2);
      }
      row("域", (p.domains || []).join(" · "));
      row("工具", (p.tools || []).join(" · "));
      row("KPI", p.kpi || "");
      card.appendChild(kv);

      var caps = document.createElement("div");
      caps.className = "prof-caps";
      (p.caps || []).slice(0, 10).forEach(function (name) {
        var chip = document.createElement("span");
        chip.className = "prof-cap";
        chip.textContent = name;
        caps.appendChild(chip);
      });
      card.appendChild(caps);
      wrap.appendChild(card);
    });
  }

  /* ───────── 职业路由（只读规划：任务 → 职业 → 候选能力位） ───────── */
  function wireProfRoute() {
    var btn = $("route-btn"), inp = $("route-input");
    if (!btn || !inp) return;
    function run() {
      var task = (inp.value || "").trim();
      if (!task) return;
      var res = $("route-result");
      if (res) res.textContent = "路由中…";
      fetch("/api/route", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task: task }),
      }).then(function (r) { return r.json(); }).then(function (d) {
        if (!d || d.ok !== true) {
          if (res) res.textContent = "没命中职业（走协同/指挥人工定）：" + ((d && d.error) || "");
          document.documentElement.dataset.route = "miss";
          return;
        }
        var safe = (d.safe_candidates || []).slice(0, 6).join(" · ");
        var gated = (d.gated_candidates || []).length;
        if (res) {
          res.innerHTML = "";
          var b = document.createElement("b");
          b.textContent = d.profession + " ";
          res.appendChild(b);
          res.appendChild(document.createTextNode(
            "（命中：" + (d.matched || []).join("、") + "）→ 候选能力位：" + safe
            + (gated ? "（另有 " + gated + " 个需授权位，要票）" : "")
            + " · 工具：" + (d.tools || []).join("/")
            + " · KPI：" + d.kpi));
        }
        document.documentElement.dataset.route = "ok:" + d.id + ":" + (d.safe_candidates || []).length;
        document.documentElement.dataset.routeProf = d.profession || "";
      }).catch(function (e) {
        if (res) res.textContent = "路由失败：" + ((e && e.message) || e);
        document.documentElement.dataset.route = "error";
      });
    }
    btn.addEventListener("click", run);
    inp.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); run(); }
    });
  }

  /* ───────── 3D 视图按需加载（动态 import，file:// 下会失败→走兜底提示） ───────── */
  var SPACE_P = null;
  function ensure3d() {
    if (SPACE_P) return SPACE_P;
    var fb = $("space3d-fallback");
    SPACE_P = import("./space3d.js").then(function (m) {
      return m;
    }).catch(function (e) {
      document.documentElement.dataset.space3d = "import-err:" + String(e && e.message || e).slice(0, 80);
      if (fb) {
        fb.hidden = false;
        fb.textContent = "3D 模块没加载：3D 需要 http 打开（python tools/console-server.py → http://127.0.0.1:8766/#space）。\n" + String(e && e.message || e);
      }
      return null;
    });
    return SPACE_P;
  }

  /* ───────── 大脑执行层：按需动态 import ───────── */
  var BRAIN_P = null;
  function ensureBrain() {
    if (BRAIN_P) return BRAIN_P;
    BRAIN_P = import("./brain3d.js").then(function (m) {
      return m;
    }).catch(function (e) {
      document.documentElement.dataset.brain3d = "import-err:" + String((e && e.message) || e).slice(0, 80);
      return null;
    });
    return BRAIN_P;
  }

  /* ───────── 万能插：按需动态 import ───────── */
  var PLUG_P = null;
  function ensurePlug() {
    if (PLUG_P) return PLUG_P;
    PLUG_P = import("./plug3d.js").then(function (m) {
      return m;
    }).catch(function (e) {
      document.documentElement.dataset.plug3d = "import-err:" + String((e && e.message) || e).slice(0, 80);
      return null;
    });
    return PLUG_P;
  }

  /* ───────── 触手协作 / 思维导图：按需动态 import ───────── */
  var TEAM_P = null, MIND_P = null;
  function ensureTeam() {
    if (TEAM_P) return TEAM_P;
    TEAM_P = import("./team3d.js").then(function (m) { return m; })
      .catch(function (e) {
        document.documentElement.dataset.team3d = "import-err:" + String((e && e.message) || e).slice(0, 80);
        return null;
      });
    return TEAM_P;
  }
  function ensureMind() {
    if (MIND_P) return MIND_P;
    MIND_P = import("./mindmap3d.js").then(function (m) { return m; })
      .catch(function (e) {
        document.documentElement.dataset.mindmap = "import-err:" + String((e && e.message) || e).slice(0, 80);
        return null;
      });
    return MIND_P;
  }

  /* ───────── 穿透扫描：按需动态 import ───────── */
  var SCAN_P = null;
  function ensureScan() {
    if (SCAN_P) return SCAN_P;
    SCAN_P = import("./scan3d.js").then(function (m) { return m; })
      .catch(function (e) {
        document.documentElement.dataset.scan3d = "import-err:" + String((e && e.message) || e).slice(0, 80);
        return null;
      });
    return SCAN_P;
  }

  /* ───────── 视图切换（支持 #hash，便于截图/直达） ───────── */
  function switchView(name) {
    var con = $("chat-area"); if (!con) return;
    var ok = ["chat", "caps", "skills", "space", "brain", "plug", "team", "mind", "scan", "prof", "dash"];
    if (ok.indexOf(name) < 0) name = "chat";
    con.setAttribute("data-view", name);
    Array.prototype.forEach.call(document.querySelectorAll(".view-tab"), function (b) {
      b.classList.toggle("is-active", b.getAttribute("data-view") === name);
    });
    try { window.dispatchEvent(new CustomEvent("gbt:view", { detail: name })); } catch (e) {}
    if (name === "brain") {
      ensureBrain().then(function (m) { if (m && m.start) try { m.start(); } catch (e) {} });
    }
    if (name === "plug") {
      ensurePlug().then(function (m) { if (m && m.start) try { m.start(); } catch (e) {} });
    }
    if (name === "team") {
      ensureTeam().then(function (m) { if (m && m.start) try { m.start(); } catch (e) {} });
    }
    if (name === "mind") {
      ensureMind().then(function (m) { if (m && m.start) try { m.start(); } catch (e) {} });
    }
    if (name === "scan") {
      ensureScan().then(function (m) { if (m && m.start) try { m.start(); } catch (e) {} });
    }
    if (name === "space") {
      ensure3d().then(function (m) { if (m && m.start) try { m.start(); } catch (e) {} });
    } else if (SPACE_P) {
      ensure3d().then(function (m) { if (m && m.stop) try { m.stop(); } catch (e) {} });
    }
    var fb = $("space3d-fallback");
    if (fb) {
      if (name !== "space") { fb.hidden = true; }
      else if (location.protocol === "file:") {
        fb.hidden = false;
        fb.textContent = "3D 星图用的是 ES Module + WebGL：file:// 直开会被浏览器拦。\n请用 python tools/console-server.py 起服务，打开 http://127.0.0.1:8766/#space";
      } else {
        fb.hidden = true;
        setTimeout(function () {
          var st = document.documentElement.dataset.space3d || "";
          if (document.getElementById("chat-area").getAttribute("data-view") === "space" && !st) {
            fb.hidden = false;
            fb.textContent = "3D 未就绪：可能 WebGL 不可用（检查 chrome://gpu），或 three.js 模块没加载（看控制台报错）。";
          }
        }, 1800);
      }
    }
    if (location.hash !== "#" + name) {
      try { history.replaceState(null, "", "#" + name); } catch (e) {}
    }
  }
  function wireViews() {
    Array.prototype.forEach.call(document.querySelectorAll(".view-tab"), function (b) {
      b.addEventListener("click", function () { switchView(b.getAttribute("data-view")); });
    });
    var h = (location.hash || "").replace("#", "");
    switchView(h || "chat");
  }

  window.addEventListener("resize", function () {
    drawGraph((MODE.data && MODE.data.domains) || []);
  });

  try {
    wire();
    wireViews();
    loadData();
  } catch (e) {
    document.documentElement.dataset.apperr = String((e && e.stack) || e).slice(0, 500);
  }
})();
