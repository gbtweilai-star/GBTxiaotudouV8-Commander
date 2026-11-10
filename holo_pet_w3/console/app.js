/* GBT小土豆V8 · 认知界面逻辑
 * 数据：优先 /api/data（console-server 现读）；直开 file:// 时退回 window.GBT_CONSOLE。
 * 对话：/api/chat → energy_core.think(context="console-web")（有界窗口 n_ctx + 全量检索，temperature=0 稳定输出）。
 */
(function () {
  "use strict";

  var MODE = { online: false, data: null };
  var LAST_GOOD = null;   // 上一次真数据（刷新失败时继续用，不把整页打回“离线”）
  var ATTACH = null;   // 对话 + 号附图（dataURL/name/bytes）
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

  function loadData(silent) {
    // 先渲染内联快照（有 <script src=state/console-data.js> 就有数据）——
    // 这样即使 /api/data 慢/挂，页面也不会空白。
    MODE.data = fallback();
    render(MODE.data);
    if (location.protocol === "file:") return;
    fetch("/api/data", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (j && j.ok && j.data) {
          LAST_GOOD = j.data;
          window.GBT_CONSOLE = j.data;   // 3D 模块（星图/扫描/世界…）读的是这个全局
          MODE.online = true; MODE.data = j.data; render(j.data);
        } else throw new Error((j && j.error) || "无数据");
      })
      .catch(function (e) {
        if (silent && MODE.online) return;      // 静默刷新失败：保留当前实时数据，不污染界面
        if (LAST_GOOD) {                        // 有过真数据：继续显示，只标“这轮没刷上”
          window.GBT_CONSOLE = LAST_GOOD;
          MODE.data = LAST_GOOD;
          MODE.online = true;
          render(LAST_GOOD);
          var st = $("conn-state");
          if (st) st.textContent = "本机 · 刷新失败，显示上次数据";
          return;
        }
        MODE.data = fallback();
        render(MODE.data);
        addBot("⚠ 读不到实时数据（" + e.message + "），显示的是内联快照。起服务：python tools/console-server.py");
      });
  }

  /* 默认视图：万能插。多域监控仍按需手动展开，不自动轮询 */
  var DEFAULT_VIEW = "chat";

  /* 上下文窗口：只读引擎实报，不写死数值 */
  function ctxOf(d) {
    var n = d && d.engine && d.engine.n_ctx;
    return n ? (n + " ctx") : "ctx —";
  }

  /* ───────── 左栏 ───────── */
  function renderLeft(d) {
    $("pill-l1").textContent = MODE.online ? "实时" : "快照";
    var alive0 = !!(d.engine && d.engine.alive);
    var ia = $("ai-activity");
    if (ia) ia.setAttribute("data-state", alive0 ? "busy" : "idle");
    $("ai-activity-label").textContent = alive0 ? "在线 · 本机指挥官" : "离线";
    $("ai-activity-detail").textContent =
      (d.engine && d.engine.weights ? d.engine.weights : "—") + " · " + ctxOf(d);

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
      var cls = (v === "clean" || v === "quiet") ? "ok" : (v ? "bad" : "warn");
      var row = el("div", "ev " + cls);
      row.appendChild(el("span", "dot"));
      var body = el("div", null, "");
      var b = el("b", null, k);
      body.appendChild(b);
      body.appendChild(document.createTextNode(" · " + (guards[k] || "未读")));
      var det = (d.guard_details || {})[k];
      var extra = "";
      if (det && k === "signature") {
        extra = " · " + (det.pages_checked || "?") + " 页 / 缺 " + (det.missing_count || 0);
      } else if (det && k === "inventory") {
        extra = " · 异物 " + ((det.foreign || []).length) +
                " / 运行态 " + ((det.runtime || []).length);
      } else if (det && k === "legacy") {
        var bf = (((det.categories || {})["backup-files"] || {}).files) || 0;
        var dc = (((det.notes || {})["doc-number-collisions"] || {}).groups) || 0;
        extra = " · 散落备份 " + bf + " / 编号撞车 " + dc;
      } else if (det && k === "alerts") {
        extra = " · runtime " + (det.runtime_faults == null ? "?" : det.runtime_faults) +
                " / 异常 " + (det.anomalies == null ? "?" : det.anomalies);
      } else if (det && k === "selfscan") {
        var rt = det.routing || {}, md = det.modules || {};
        extra = " · 路由 " + (rt.routed || 0) + "/" + (rt.registered || 0) +
                " / 模块查 " + (md.checked || 0) + " 坏 " + ((md.failed || []).length);
      }
      if (extra) body.appendChild(document.createTextNode(extra));
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
      var v = String(gs[k] || "").toLowerCase();
      return v.indexOf("clean") >= 0 || v === "quiet";
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
      " · " + (alive ? ("有界窗口 " + ctxOf(d) + " · 全量检索 · temperature=0") : "离线")));
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

  /* ───────── AI 打印（Codex 对话面板同款逐字吐字） ─────────
   * Codex 的回答不是「整段闪现」：边生成边吐字、末尾一根光标、
   * 只有视图贴着底部时才自动跟随。本机 /api/chat 是整包返回
   * （energy_core.think 非流式），所以吐字在前端按字推进，节奏随长度自适应。
   * 判据：gbt_allinone/tests/test_console_chat_print.py
   */
  var PRINT_CPS = 90;
  var PRINT_CARET = "\u258d";

  function _reduced() {
    try {
      return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    } catch (e) { return false; }
  }

  /* 只在用户本来就贴着底部时才跟滚 —— 往上翻历史时别把他拽回来 */
  function _stickBottom(force) {
    var con = $("chat-history");
    if (!con) return;
    var gap = con.scrollHeight - con.scrollTop - con.clientHeight;
    if (force || gap < 48) con.scrollTop = con.scrollHeight;
  }

  /* 收掉所有还在吐的：新消息进来时旧回答立即落定，不留半句 */
  function finishPrinting() {
    Array.prototype.forEach.call(document.querySelectorAll(".msg.printing"), function (n) {
      if (n.__finishPrint) n.__finishPrint();
      else if (n.__abort) n.__abort();
    });
  }

  function printingNow() {
    return !!document.querySelector(".msg.printing");
  }

  /* ── AI 步骤行（Codex 同款）：先给一条可折叠的过程行，再吐正式回答 ── */
  function _msLabel(ms) {
    if (ms == null || ms === "") return "";
    var n = Number(ms);
    if (!isFinite(n)) return "";
    if (n >= 1000) return (Math.round(n / 100) / 10) + "s";
    // 0ms 不等于「没耗时」：回执里的毫秒是 int 截断的，<1ms 如实写 <1ms
    if (n < 1) return "<1ms";
    return (Math.round(n * 10) / 10) + "ms";
  }

  /* 把 /api/chat 的回执折成「已使用 …」一个人能看懂的过程行；
     详情折在下面，不默认展开 —— 与 Codex 的步骤行同一形状。 */
  /* 把 /api/chat 回执折成「过程行」：她扫了什么、调了哪个工具、回执怎么说、
     最后怎么组织回答。每一行都来自回执本身，不猜、不编。 */
  function _short(v, n) {
    var s = (v == null) ? "" : String(v);
    return s.length > n ? s.slice(0, n) + "…" : s;
  }

  function buildSteps(j) {
    j = j || {};
    /* 2026-11-07：服务端 SSE 会把这一轮真实走过的步骤随最终回执带回。
       有它就原样用 —— 收尾时别再拿粗粒度折行把她真走过的过程覆盖掉。 */
    if (Array.isArray(j.steps) && j.steps.length) {
      return j.steps.map(function (s) {
        return { title: s.title, ms: (s.ms != null ? s.ms : s.at_ms), rows: s.rows || [] };
      });
    }
    var cap = (j.capability && typeof j.capability === "object") ? j.capability : null;
    var call = (j.call && typeof j.call === "object") ? j.call : null;
    var rt = (j.route && typeof j.route === "object") ? j.route : null;
    var steps = [];

    if (rt) {
      var rows = [];
      if (rt.input) rows.push(["原话", _short(rt.input, 140)]);
      if (rt.intent || rt.action) rows.push(["意图", String(rt.intent || "?") + " / " + String(rt.action || "?")]);
      var tgt = rt.target_abs || rt.target;
      if (tgt) rows.push(["对象", _short(tgt, 140)]);
      if (rt.matched && rt.matched.length) rows.push(["命中词", rt.matched.join(" / ")]);
      if (rt.missing && rt.missing.length) rows.push(["缺参数", rt.missing.join(" / ")]);
      if (rt.confidence != null) rows.push(["置信度", String(rt.confidence)]);
      if (rt.reason) rows.push(["说明", _short(rt.reason, 240)]);
      if (rt.error) rows.push(["错误", _short(rt.error, 200)]);
      var toolMs = (cap && cap.ms != null) ? Number(cap.ms) : 0;
      var routeMs = (j.ms_route != null) ? Math.max(0, Math.round(Number(j.ms_route) - toolMs)) : null;
      steps.push({
        title: "扫描指令 · 命中 " + ((rt.matched || []).length) + " 个词",
        ms: routeMs, rows: rows
      });
    }

    if (call || (cap && (cap.cap || cap.method))) {
      var kind = (call && call.kind) || (cap && cap.cap) || "tentacle";
      var payload = (call && call.payload && typeof call.payload === "object") ? call.payload : null;
      var opv = (payload && payload.op) || (cap && cap.op) || "";
      var r2 = [["工具", String(kind) + (opv ? " · " + opv : "")]];
      if (cap && cap.method) r2.push(["方法", String(cap.method)]);
      if (payload) {
        Object.keys(payload).forEach(function (k) {
          var v = payload[k];
          if (k === "op" || v === "" || v == null) return;   // op 已在标题里，不重复一行
          r2.push([k, _short(typeof v === "string" ? v : JSON.stringify(v), 200)]);
        });
      }
      if (cap && cap.params && Object.keys(cap.params).length) {
        r2.push(["params", _short(JSON.stringify(cap.params), 220)]);
      }
      if (cap && cap.socket && !(payload && payload.socket)) r2.push(["表面", String(cap.socket)]);
      if (cap && cap.target && !(payload && payload.target)) r2.push(["目标", _short(cap.target, 140)]);
      if (cap && cap.energy) r2.push(["代价", _short(cap.energy, 220)]);
      steps.push({ title: "调用工具 · " + kind + (opv ? "(" + opv + ")" : ""),
                   ms: (cap ? cap.ms : null), rows: r2 });
    }

    // 回执的形状按能力位不同：屏幕/看图是 {ok,size,...}（键是中文动作词「看」），
    // 读文件直接把正文挂在 cap.read 上（字符串）。所以按「非元数据键」认回执，
    // 两种形状都如实摊开 —— 不为了对齐格式而丢掉她真读到的东西。
    var rc = null, rcKey = "";
    if (cap) {
      var META = { op: 1, ok: 1, socket: 1, target: 1, action: 1, energy: 1, plug: 1, ms: 1,
                   auth_consumed: 1, cap: 1, method: 1, params: 1, judge: 1, missing: 1,
                   missing_scopes: 1, gate: 1, margin: 1, whitelist: 1, candidate: 1, why: 1,
                   rule: 1, size: 1, fmt: 1, image_kb: 1, engine: 1, capture_ms: 1 };
      var _ck = Object.keys(cap);
      for (var _i = 0; _i < _ck.length; _i++) {
        if (META[_ck[_i]]) continue;
        var _v = cap[_ck[_i]];
        if (_v == null || _v === "") continue;
        rcKey = _ck[_i];
        rc = (typeof _v === "object" && !Array.isArray(_v)) ? _v : { ok: cap.ok, note: _short(_v, 240) };
        break;
      }
      if (!rc && (cap.rule || cap.why || cap.ok != null)) { rc = cap; rcKey = "capability"; }
      if (!rc && cap.size) { rc = cap; rcKey = "capability"; }
    }
    if (rc) {
      var r3 = [["结果", (rc.ok === true ? "ok" : (rc.ok === false ? "failed" : (rc.status || "—")))]];
      if (rc.status) r3.push(["状态", String(rc.status)]);
      if (rcKey && rcKey !== "capability") r3.push(["动作", rcKey]);
      if (rc.note) r3.push(["内容", rc.note]);
      if (rc.image_kb != null) r3.push(["载荷", rc.image_kb + "KB" + (rc.fmt ? " · " + rc.fmt : "")]);
      if (rc.rule) r3.push(["判定", String(rc.rule)]);
      if (rc.why) r3.push(["原因", _short(rc.why, 320)]);
      if (rc.missing && rc.missing.length) r3.push(["缺", rc.missing.join(" / ")]);
      if (rc.engine) r3.push(["采集", String(rc.engine) + (rc.capture_ms != null ? " · " + rc.capture_ms + "ms" : "")]);
      if (rc.size && rc.size.length === 2) r3.push(["帧", rc.size.join("×") + (rc.delta ? " · 增量" : " · 整帧")]);
      if (rc.mss_recovered) r3.push(["自愈", "mss 句柄失效 → 已重建"]);
      // 标题如实反映回执的**实际状态**：ok=true 是成功；already_running / denied 这类
      // 既不是成功也不是失败，直接写状态本身，别一律压成「失败」。
      var rcTitle = (rc.ok === true) ? "成功"
        : (rc.status ? String(rc.status) : (rc.rule ? String(rc.rule) : (rc.note ? _short(rc.note, 40) : "失败")));
      steps.push({ title: "执行回执 · " + rcTitle, ms: null, rows: r3 });
    }

    var r4 = [];
    if (j.via) r4.push(["通道", String(j.via)]);
    if (j.label) r4.push(["命中", _short(j.label, 120)]);
    if (j.usage && j.usage.completion_tokens != null) r4.push(["tokens", String(j.usage.completion_tokens) + " · temperature=0"]);
    if (j.ring && j.ring.seq != null) r4.push(["记忆环", "seq " + j.ring.seq + " / 历史 " + (j.ring.db_turns != null ? j.ring.db_turns : "?") + " 轮"]);
    if (j.elapsed_ms != null) r4.push(["总耗时", _msLabel(j.elapsed_ms)]);
    if (j.error) r4.push(["错误", _short(j.error, 240)]);
    if (r4.length) steps.push({ title: "组织回答 · " + (j.via || "本机"),
                                ms: (j.elapsed_ms != null ? j.elapsed_ms : null), rows: r4 });

    return steps;
  }

  /* 单个步骤行（Codex 同款：标题 + 耗时，详情默认折叠）。
     `state:"running"` 的行显示「执行中」并带一个活计时，回执到了就换成实测耗时。 */
  function _stepEl(s) {
    s = s || {};
    var head = el("button", "step-head");
    head.type = "button";
    head.setAttribute("aria-expanded", "false");
    head.appendChild(el("span", "step-chev", "›"));
    head.appendChild(el("span", "step-title", s.title || ""));
    var running = s.state === "running";
    var msTxt = running ? "执行中" : _msLabel(s.ms);
    var msEl = el("span", "step-ms" + (running ? " live" : ""), msTxt);
    if (msTxt) head.appendChild(msEl);
    var body = el("div", "step-body");
    body.hidden = true;
    (s.rows || []).forEach(function (r) {
      var row = el("div", "step-row");
      row.appendChild(el("b", "", r[0]));
      row.appendChild(el("span", "", r[1]));
      body.appendChild(row);
    });
    head.addEventListener("click", function () {
      var open = body.hidden;
      body.hidden = !open;
      head.setAttribute("aria-expanded", open ? "true" : "false");
      head.classList.toggle("is-open", open);
    });
    return { head: head, body: body, msEl: msEl };
  }

  function renderSteps(wrap, steps) {
    if (!wrap) return;
    wrap.innerHTML = "";
    if (!steps || !steps.length) return;
    steps.forEach(function (s) {
      var n = _stepEl(s);
      wrap.appendChild(n.head);
      wrap.appendChild(n.body);
    });
  }

  function printBot(text, meta, steps, turn) {
    var box = $("chat-messages");
    if (!box) return null;
    var m, body, caret, wrap;
    if (turn && turn.node && turn.node.parentNode) {
      turn.live = false;
      turn.stop();
      m = turn.node;
      body = turn.bodyEl;
      caret = turn.caret;
      wrap = turn.wrap;
      /* 流式步骤已经有内容时，最终回执若没折出步骤就别清空她真实走过的过程。 */
      if (steps && steps.length) renderSteps(wrap, steps);
    } else {
      m = el("div", "msg bot printing");
      wrap = el("div", "msg-steps");
      m.appendChild(wrap);
      renderSteps(wrap, steps);
      if (!wrap.children.length) m.removeChild(wrap);
      body = el("span", "msg-text");
      caret = el("span", "tw-caret", PRINT_CARET);
      m.appendChild(body);
      m.appendChild(caret);
      box.appendChild(m);
    }
    var con = document.getElementById("chat-area");
    if (con) con.classList.add("has-msgs");
    _stickBottom(true);


    var s = String(text == null ? "" : text);
    var i = 0;
    var done = false;

    function finish() {
      if (done) return;
      done = true;
      body.textContent = s;
      m.classList.remove("printing");
      if (caret.parentNode) caret.parentNode.removeChild(caret);
      if (meta) m.appendChild(el("div", "meta", meta));
      _stickBottom(false);
      if (typeof m.__onDone === "function") m.__onDone(m);
    }
    m.__finishPrint = finish;

    if (!s.length || _reduced()) { finish(); return m; }

    var step = Math.max(1, Math.round(s.length / 240));
    var delay = Math.max(8, Math.round(1000 / PRINT_CPS));

    (function tick() {
      if (done) return;
      i = Math.min(s.length, i + step);
      body.textContent = s.slice(0, i);
      _stickBottom(false);
      if (i >= s.length) { finish(); return; }
      window.setTimeout(tick, delay);
    })();

    return m;
  }

  /* 一轮对话的「进行中」骨架（Codex 同款：过程行先到，正文随后逐字）。
     2026-11-07 主人令：「她开始执行任务每一步都要能看到她在干嘛执行到哪里」。
     服务端用 SSE 把每个阶段 push 过来，这里**到达一条就追加一行**：
     进行中的自动展开、前一条收起；最终回执到达后再换成完整步骤 + 逐字正文。 */
  function beginTurn() {
    var box = $("chat-messages");
    if (!box) return null;
    var m = el("div", "msg bot printing");
    var wrap = el("div", "msg-steps");
    m.appendChild(wrap);
    var body = el("span", "msg-text");
    var caret = el("span", "tw-caret", PRINT_CARET);
    m.appendChild(body);
    m.appendChild(caret);
    box.appendChild(m);
    var con = document.getElementById("chat-area");
    if (con) con.classList.add("has-msgs");
    _stickBottom(true);

    var t0 = Date.now();
    var timer = 0;
    var lastSeq = 0;
    var placeholder = null;
    var runningMsEl = null, runningBase = 0, runningAt = 0;

    /* 未收到任何流式步骤前的占位行：真实计时，不许假装在跑。 */
    placeholder = _stepEl({ title: "接收指令 · 正在处理", rows: [], state: "running" });
    wrap.appendChild(placeholder.head);
    wrap.appendChild(placeholder.body);

    timer = window.setInterval(function () {
      if (runningMsEl) {
        runningMsEl.textContent = _msLabel(Date.now() - runningAt + runningBase);
        return;
      }
      if (placeholder) placeholder.msEl.textContent = _msLabel(Date.now() - t0);
    }, 100);

    var turn = {
      node: m, wrap: wrap, bodyEl: body, caret: caret, t0: t0, live: true,
      stop: function () { if (timer) { window.clearInterval(timer); timer = 0; } },
      step: function (rec) {
        if (!rec || !turn.live) return;
        if (rec.seq != null && rec.seq <= lastSeq) return;
        if (rec.seq != null) lastSeq = rec.seq;
        /* 第一条真步骤到达：撤掉占位行，之后只追加，不再清空 —— 过程是长出来的。 */
        if (placeholder) { wrap.innerHTML = ""; placeholder = null; }
        var running = rec.state === "running";
        var n = _stepEl({ title: rec.title, rows: rec.rows, ms: rec.ms,
                          state: running ? "running" : "done" });
        /* 只展开「当前这一步」，历史步骤自动收起 —— 与 Codex 的执行面同一读法。 */
        Array.prototype.forEach.call(wrap.querySelectorAll(".step-body"), function (b) { b.hidden = true; });
        Array.prototype.forEach.call(wrap.querySelectorAll(".step-head"), function (h) {
          h.classList.remove("is-open"); h.setAttribute("aria-expanded", "false");
        });
        wrap.appendChild(n.head);
        wrap.appendChild(n.body);
        if (running && n.body.children.length) {
          n.body.hidden = false;
          n.head.classList.add("is-open");
          n.head.setAttribute("aria-expanded", "true");
        }
        if (running) {
          runningMsEl = n.msEl;
          runningBase = Number(rec.at_ms) || 0;
          runningAt = Date.now();
        } else {
          runningMsEl = null;
          if (rec.ms == null && rec.at_ms != null) n.msEl.textContent = _msLabel(rec.at_ms);
        }
        _stickBottom(false);
      },
      phase: function (txt) {
        if (placeholder) placeholder.head.querySelector(".step-title").textContent = txt;
        _stickBottom(false);
      },
      drop: function () { turn.stop(); if (m.parentNode) m.parentNode.removeChild(m); }
    };
    m.__abort = function () {
      if (!turn.live) return;
      turn.live = false;
      turn.stop();
      if (placeholder) {
        placeholder.msEl.textContent = _msLabel(Date.now() - t0);
        placeholder.msEl.classList.remove("live");
        placeholder.head.querySelector(".step-title").textContent = "已中途中止";
      } else {
        var stop = _stepEl({ title: "已中途中止", ms: Date.now() - t0,
                             rows: [["说明", "用户中止，后续步骤未执行"]] });
        wrap.appendChild(stop.head);
        wrap.appendChild(stop.body);
      }
      m.classList.remove("printing");
      if (caret.parentNode) caret.parentNode.removeChild(caret);
      _stickBottom(false);
    };
    return turn;
  }

  function fmtSize(n) {
    n = Number(n) || 0;
    if (n < 1024) return n + "B";
    if (n < 1048576) return (n / 1024).toFixed(1) + "KB";
    return (n / 1048576).toFixed(1) + "MB";
  }

  /* ───────── 对话 + 号附图：选图/粘贴/预览/移除/发送 ───────── */
  function clearAttachPreview() {
    ATTACH = null;
    var box = $("chat-attach-preview");
    if (box) { box.hidden = true; box.innerHTML = ""; }
  }

  function showAttachPreview(a) {
    var box = $("chat-attach-preview");
    if (!box) return;
    box.innerHTML = "";
    var im;
    if (a.kind === "image") {
      im = document.createElement("img");
      im.className = "attach-thumb"; im.src = a.dataUrl; im.alt = a.name || "附图";
    } else {
      im = el("span", "attach-thumb attach-file-icon", "文");
    }
    var name = el("span", "attach-name",
      (a.name || "附件") + " · " + fmtSize(a.bytes));
    var x = el("button", "attach-x", "×");
    x.type = "button"; x.title = "移除附图";
    x.onclick = function () { clearAttachPreview(); };
    box.appendChild(im); box.appendChild(name); box.appendChild(x);
    box.hidden = false;
  }

  function setAttach(file, mode) {
    if (!file) return;
    var isImg = /^image\//.test(file.type || "");
    if (mode === "image" && !isImg) {
      addBot("⚠ 图片入口只接图片（png/jpg/webp/gif…）；其它文件请用「文件」入口", "附图");
      return;
    }
    var maxBytes = isImg ? 8 * 1024 * 1024 : 20 * 1024 * 1024;
    if (file.size > maxBytes) { addBot("⚠ 文件太大（> " + (maxBytes / 1048576) + "MB）", "附图"); return; }
    var fr = new FileReader();
    fr.onload = function () {
      ATTACH = { kind: isImg ? "image" : "file", name: file.name,
                 type: file.type || "", dataUrl: String(fr.result || ""), bytes: file.size };
      showAttachPreview(ATTACH);
    };
    fr.onerror = function () { addBot("⚠ 文件读取失败", "附件"); };
    fr.readAsDataURL(file);
  }

  function addUserMsg(text, att) {
    var m = addMsg("user", text || (att ? (att.kind === "image" ? "（附图）" : "（附件）") : ""));
    if (att && att.kind === "image") {
      var im = document.createElement("img");
      im.className = "msg-attach"; im.src = att.dataUrl; im.alt = "附图";
      m.appendChild(im);
    } else if (att) {
      var sp = document.createElement("span");
      sp.className = "msg-file";
      sp.textContent = "附件：" + (att.name || "文件") + " · " + fmtSize(att.bytes);
      m.appendChild(sp);
    }
    return m;
  }

  /* 回执 → 底部元信息（保持原有口径：通道 / tokens / 记忆环都来自回执本体）。 */
  function _chatMeta(j) {
    var meta;
    if (j.via === "capability_router") {
      meta = "万能插 · " + (j.label || j.intent || "能力") +
        (j.ms != null ? " · " + j.ms + "ms" : "") + " · 已落审计";
    } else if (j.via && (j.via.indexOf("file:") === 0 || j.via === "vision:local")) {
      var vLabel = j.via === "vision:local" ? "附图视觉读数"
        : (j.via === "file:text" ? "文本附件" : (j.via === "file:binary" ? "二进制附件" : "本地附件"));
      meta = "本地附件 · " + vLabel + (j.ms != null ? " · " + j.ms + "ms" : "") + " · 不借云端";
    } else {
      meta = (j.usage ? j.usage.completion_tokens + " tok · " : "") +
        (j.ms != null ? j.ms + "ms · " : "") + "temperature=0";
      var ring = j.ring || {};
      meta += " · 上下文 seq " + (ring.seq != null ? ring.seq : "?") +
        " / 历史 " + (ring.db_turns != null ? ring.db_turns : "?") + " 轮";
    }
    return meta;
  }

  /* 读 POST /api/chat 的 SSE 流：
     `step` 立刻交给 turn.step 追加，`final` 作为最终回执返回。
     流断在半路没有 final ⇒ 如实报「没有收到最终回执」，不拿半截冒充成功。 */
  function _readChatStream(resp, turn) {
    var reader = resp.body.getReader();
    var dec = new TextDecoder("utf-8");
    var buf = "";
    var final = null;

    function pump() {
      return reader.read().then(function (r) {
        if (r.done) return final || { ok: false, error: "流已断开，没有收到最终回执" };
        buf += dec.decode(r.value, { stream: true });
        var idx;
        while ((idx = buf.indexOf("\n\n")) >= 0) {
          var block = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          var data = [];
          block.split("\n").forEach(function (ln) {
            if (ln.indexOf("data:") === 0) data.push(ln.slice(5).replace(/^ /, ""));
          });
          if (!data.length) continue;
          var ev = null;
          try { ev = JSON.parse(data.join("\n")); } catch (e) { ev = null; }
          if (!ev) continue;
          if (ev.type === "step") { if (turn && turn.step) turn.step(ev); }
          else if (ev.type === "final") { final = ev.result || {}; }
        }
        if (final) return final;
        return pump();
      });
    }
    return pump().then(function (j) {
      try { reader.cancel(); } catch (e) { /* 已断开 */ }
      return j;
    });
  }

  function _finishChat(j, turn, btn) {
    if (j && j.ok) {
      printBot(String(j.text || "").trim() || "(空回答)", _chatMeta(j), buildSteps(j), turn);
    } else {
      printBot("⚠ " + ((j && j.error) || "调用失败"), "如实报错", buildSteps(j), turn);
    }
    if (btn) btn.disabled = false;
  }

  function chatSubmit(text) {
    finishPrinting();          // 上一轮还在吐字：先让它落定，再把新消息接上
    var _att = ATTACH;
    addUserMsg(text, _att);
    if (_att) clearAttachPreview();
    var btn = document.querySelector(".send-btn");
    btn.disabled = true;
    var turn = beginTurn();
    if (!MODE.online) {
      if (turn) turn.drop();
      addBot("（演示模式：直开 file:// 不能调本机引擎。\n起服务后即可真对话：python tools/console-server.py，然后打开 http://127.0.0.1:8766/）\n\n本机模型：有界窗口 + 全量检索（数值按引擎实报，不写死）· 稳定输出（temperature=0）。",
        "file:// · 未连接");
      btn.disabled = false;
      return;
    }
    if (turn) turn.phase("执行中 · 等待本机回执");
    fetch("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: text, context: "console-web",
        stream: true,
        image: (_att && _att.kind === "image") ? _att.dataUrl : "",
        image_name: (_att && _att.kind === "image") ? (_att.name || "") : "",
        file: (_att && _att.kind === "file") ? _att.dataUrl : "",
        file_name: (_att && _att.kind === "file") ? (_att.name || "") : "",
        file_type: (_att && _att.kind === "file") ? (_att.type || "") : ""
      })
    }).then(function (r) {
      var ct = (r.headers.get("content-type") || "").toLowerCase();
      if (ct.indexOf("text/event-stream") >= 0 && r.body && r.body.getReader) {
        return _readChatStream(r, turn);
      }
      /* 老服务 / 代理剥了流：退回整包 JSON，但步骤仍照常折出来。 */
      return r.json();
    }).then(function (j) {
      _finishChat(j, turn, btn);
    }).catch(function (e) {
      printBot("⚠ 请求失败：" + e.message, "网络错误", null, turn);
      btn.disabled = false;
    });
  }

  function wire() {
    /* P1：万能插四类快捷条（点一下就等于发一句对应人话；执行仍走 /api/chat → capability_router） */
    var CAP_TEMPLATES = {
      screen: "帮我看看屏幕",
      web: "打开 https://example.com",
      file: "读文件 README.md",
      image: "看图 icons/avatar.png"
    };
    /* 2026-11-02：对话 + 号附图（文件选择 / 粘贴图片 / 预览 / 移除） */
    var attachBtn = $("chat-attach");
    var fileInput = $("chat-file");
    if (attachBtn && fileInput) {
      attachBtn.addEventListener("click", function () { fileInput.click(); });
      fileInput.addEventListener("change", function () {
        var f = fileInput.files && fileInput.files[0];
        if (f) setAttach(f, "image");
        fileInput.value = "";
      });
    }
    var fileBtn = $("chat-attach-file");
    var uploadInput = $("chat-upload");
    if (fileBtn && uploadInput) {
      fileBtn.addEventListener("click", function () { uploadInput.click(); });
      uploadInput.addEventListener("change", function () {
        var f = uploadInput.files && uploadInput.files[0];
        if (f) setAttach(f, "file");
        uploadInput.value = "";
      });
    }
    var chatInputEl = $("chat-input");
    if (chatInputEl) {
      chatInputEl.addEventListener("paste", function (e) {
        var items = (e.clipboardData && e.clipboardData.items) || [];
        for (var i = 0; i < items.length; i++) {
          if (items[i].type && items[i].type.indexOf("image/") === 0) {
            var f = items[i].getAsFile();
            if (f) { setAttach(f); e.preventDefault(); }
            break;
          }
        }
      });
    }
    Array.prototype.forEach.call(document.querySelectorAll("#cap-quick .cap-chip"), function (b) {
      b.addEventListener("click", function () {
        var t = CAP_TEMPLATES[b.getAttribute("data-cap")];
        if (!t) return;
        var inp = $("chat-input");
        if (inp) inp.value = t;
        chatSubmit(t);
      });
    });
    $("chat-composer").addEventListener("submit", function (e) {
      e.preventDefault();
      var t = $("chat-input").value.trim();
      if (!t && !ATTACH) return;
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
      var t = document.querySelector('.view-tab[data-view="teardown"]');
      if (t) t.click();
    });
    $("settings-btn").addEventListener("click", function () {
      if (window.__openSettings) { window.__openSettings(); return; }
      addBot("设置：模型/语音/社交在壳的 connect 页；本页只读状态。", "占位");
    });
    var tb = $("titlebar-time");
    if (tb) tb.textContent = nowStr();
  }

  function render(d) {
    var mc = $("model-chip");
    if (mc) {
      var eng = d.engine || {};
      mc.textContent = "本机指挥官 · " + (eng.weights || "无权重") + " · " + ctxOf(d);
    }
    renderLeft(d);
    renderRight(d);
    var f = $("footer-at");
    if (f) f.textContent = d.generated_at || "—";
    var sub = $("console-sub");
    if (sub) {
      sub.textContent = "本机指挥官 · " +
        ((d.engine && d.engine.base) || "127.0.0.1:8792") +
        " · 有界窗口 " + ctxOf(d) + " · 稳定输出(temperature=0)" +
        (MODE.online ? " · 实时" : " · 快照");
    }
    renderCaps(d);
    renderSkills(d);
    renderProfessions(d);
    wireProfRoute();
    wireProfDispatch();
    renderDash(d);
    var cs = $("caps-sub"), ss = $("skills-sub");
    if (cs) cs.textContent = (d.caps && d.caps.total) + " 位 · " + ((d.domains && d.domains.length) || 0) + " 域";
    if (ss) {
      var sk = d.skills || {};
      var errs = sk.errors || [];
      var verdict = sk.validate || "?";
      var label = verdict === "ok" ? "全部合规"
        : (errs.length ? (errs.length + " 项待修")
          : (sk.warnings ? (sk.warnings + " 条提示") : verdict));
      ss.textContent = (sk.count || 0) + " 个 · " + label;
      ss.title = errs.map(function (e) {
        var msgs = e.errors;
        var txt = (Object.prototype.toString.call(msgs) === "[object Array]")
          ? msgs.join("；") : (msgs || "").toString();
        return (e.skill || e.path || "?") + "：" + (txt || "待修");
      }).join("\n") || "";
      document.documentElement.dataset.skills = verdict + ":" + errs.length;
    }
    var cn = $("tab-caps-n"), sn = $("tab-skills-n");
    if (cn) cn.textContent = (d.caps && d.caps.total) || "";
    if (sn) sn.textContent = (d.skills && d.skills.count) || "";

    // 开场欢迎（只一次）
    if (!$("chat-messages").childElementCount) {
      addBot("我是 GBT小土豆V8 的认知界面。左边是她的能力与流水，中间是对话，右边是心跳/行动/守卫。\n" +
        "本机指挥官：有界窗口 " + ctxOf(d) + "（模型只看一屏、其余靠全量检索）· 稳定输出（temperature=0）。",
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
        var dot = document.createElement("span"); dot.className = "legend-dot";
        dot.style.background = x[0];
        row.appendChild(dot); row.appendChild(document.createTextNode(x[1]));
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
    if (!items.length) {
      document.documentElement.dataset.prof = "empty:no-data";
      var emptyEl = document.createElement("div");
      emptyEl.className = "prof-empty";
      emptyEl.textContent = "职业表没加载：data/professions.json 缺失或读不出。"
        + "跑 tools/gen-professions.py 生成后再刷新（不会凭空编职业）。";
      wrap.appendChild(emptyEl);
      return;
    }
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

  /* ───────── 职业派单（只跑 safe 候选；真执行写账本） ───────── */
  function wireProfDispatch() {
    var btn = $("dispatch-btn"), inp = $("route-input");
    if (!btn || !inp) return;
    btn.addEventListener("click", function () {
      var task = (inp.value || "").trim();
      var out = $("dispatch-result");
      if (!task) { if (out) out.textContent = "先输入任务"; return; }
      if (!window.confirm("真派单会执行 safe 能力位并写账本，确定？")) { return; }
      if (out) out.textContent = "派单中…";
      btn.disabled = true;
      fetch("/api/dispatch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task: task, confirm: true, max_caps: 3 }),
      }).then(function (r) { return r.json(); }).then(function (d) {
        if (!out) return;
        out.innerHTML = "";
        var b = document.createElement("b");
        b.textContent = (d.profession || "?") + " ";
        out.appendChild(b);
        if (!d.executed) {
          out.appendChild(document.createTextNode("· 计划：" + (d.caps_planned || []).join(" · ")
            + "（未执行：" + (d.reason || "") + "）"));
          document.documentElement.dataset.dispatch = "plan:" + d.profession_id;
          return;
        }
        var lines = (d.results || []).map(function (x) {
          return x.cap + (x.ok ? " ✓" : " ✗") + " (" + x.ms + "ms)";
        });
        out.appendChild(document.createTextNode(
          "· 执行 " + (d.ok_count || 0) + "/" + (d.results || []).length
          + " · " + lines.join(" · ") + " · " + (d.ledger || "")));
        document.documentElement.dataset.dispatch =
          "ok:" + d.profession_id + ":" + (d.ok_count || 0) + "/" + (d.results || []).length;
      }).catch(function (e) {
        if (out) out.textContent = "派单失败：" + ((e && e.message) || e);
        document.documentElement.dataset.dispatch = "error";
      }).then(function () { btn.disabled = false; });
    });
  }

  /* ───────── 赏金工作台（授权 → 发现 → 报告 → 赔付账本） ───────── */
  var BOUNTY = null;
  function bountyApi(op, extra) {
    var body = Object.assign({ op: op }, extra || {});
    return fetch("/api/bounty", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(function (r) { return r.json(); });
  }
  function renderBounty(d) {
    var strip = $("bounty-summary");
    if (!strip) return;
    var emptyEl = $("bounty-empty");
    if (emptyEl) emptyEl.hidden = !!((d && d.programs) || 0);
    strip.innerHTML = "";
    function kpi(label, val) {
      var el = document.createElement("div");
      el.className = "bounty-kpi";
      var b = document.createElement("b");
      b.textContent = String(val);
      el.appendChild(b);
      el.appendChild(document.createTextNode(" " + label));
      strip.appendChild(el);
    }
    kpi("授权项目", d.programs || 0);
    kpi("已记录发现", d.findings || 0);
    var by = d.by_severity || {};
    kpi("critical", by.critical || 0);
    kpi("high", by.high || 0);
    kpi("medium", by.medium || 0);
    var pay = d.payout_total || {};
    var keys = Object.keys(pay);
    if (!keys.length) kpi("赔付账本", "0");
    keys.forEach(function (c) { kpi("赔付 " + c, pay[c]); });

    var sel = $("bounty-program");
    if (sel) {
      sel.innerHTML = "";
      (d.programs_list || []).forEach(function (p) {
        var o = document.createElement("option");
        o.value = p.id;
        o.textContent = p.name + " (" + (p.platform || "自有") + ")";
        sel.appendChild(o);
      });
      if (!(d.programs_list || []).length) {
        var o2 = document.createElement("option");
        o2.value = "";
        o2.textContent = "还没有授权项目（点右侧按钮建自有靶场）";
        sel.appendChild(o2);
      }
    }

    var box = $("bounty-findings");
    if (box) {
      box.innerHTML = "";
      (d.findings_list || []).forEach(function (f) {
        var card = document.createElement("div");
        card.className = "bounty-finding";
        var ti = document.createElement("div");
        ti.className = "bf-title";
        ti.textContent = f.title;
        card.appendChild(ti);
        var sev = document.createElement("span");
        sev.className = "sev sev-" + (f.severity || "info");
        sev.textContent = "[" + (f.severity || "info").toUpperCase() + "] ";
        card.appendChild(sev);
        card.appendChild(document.createTextNode(
          f.target + " · " + (f.cwe || "-") + " · " + (f.cvss || "-")
          + " · 证据 " + ((f.evidence || []).length) + " 个"));
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "scan-target";
        btn.textContent = "生成报告";
        btn.style.marginLeft = "8px";
        btn.addEventListener("click", function () {
          bountyApi("report", { finding: f.id }).then(function (r) {
            var el = $("bounty-gate-result");
            if (el) {
              el.className = r.ok ? "ok" : "blocked";
              el.textContent = r.ok ? ("报告已生成：" + r.report + " · sha256 " + (r.sha256 || "").slice(0, 12))
                : ("生成失败：" + (r.reason || "")); 
            }
          });
        });
        card.appendChild(btn);
        box.appendChild(card);
      });
    }
    document.documentElement.dataset.bounty =
      "ok:" + (d.programs || 0) + "项目:" + (d.findings || 0) + "发现";
  }
  function ensureBounty() {
    if (BOUNTY) { renderBounty(BOUNTY); }
    return bountyApi("summary").then(function (d) {
      BOUNTY = d;
      renderBounty(d);
      return d;
    }).catch(function (e) {
      document.documentElement.dataset.bounty = "error:" + String((e && e.message) || e).slice(0, 80);
      return null;
    });
  }
  function wireBounty() {
    var checkBtn = $("bounty-check");
    var demoBtn = $("bounty-add-demo");

    var createBtn = $("bounty-create");
    if (createBtn) {
      createBtn.addEventListener("click", function () {
        var name = (($("bounty-name") || {}).value || "").trim();
        var scopeRaw = (($("bounty-scope") || {}).value || "").trim();
        var authref = (($("bounty-authref") || {}).value || "").trim() || "本机自建靶场";
        var out = $("bounty-new-result");
        if (!name || !scopeRaw) { if (out) out.textContent = "名称和授权范围都要填"; return; }
        var scope = scopeRaw.split(/[,，\s]+/).filter(Boolean);
        if (out) out.textContent = "创建中…";
        createBtn.disabled = true;
        bountyApi("add_program", { name: name, scope: scope, authorization_ref: authref })
          .then(function (r) {
            if (!out) return;
            if (r && r.ok) {
              out.textContent = "已建：" + ((r.program && r.program.id) || name) + " · 现在可以做范围检查了";
              document.documentElement.dataset.bountyCreate = "ok";
              ensureBounty();
            } else {
              out.textContent = "拒绝：" + ((r && (r.reason || r.error)) || "未知");
              document.documentElement.dataset.bountyCreate = "fail";
            }
          })
          .catch(function (e) {
            if (out) out.textContent = "创建失败：" + ((e && e.message) || e);
            document.documentElement.dataset.bountyCreate = "error";
          })
          .then(function () { createBtn.disabled = false; });
      });
    }

    if (!checkBtn) return;
    checkBtn.addEventListener("click", function () {
      var prog = ($("bounty-program") || {}).value || "";
      var target = (($("bounty-target") || {}).value || "").trim();
      var out = $("bounty-gate-result");
      if (!target) { if (out) out.textContent = "先填目标"; return; }
      bountyApi("check", { program: prog, target: target }).then(function (d) {
        if (!out) return;
        if (d.ok) {
          out.className = "ok";
          out.textContent = "允许：" + target + " 在授权范围（" + (d.authorization_ref || "") + "）";
          document.documentElement.dataset.scopeCheck = "allowed";
        } else {
          out.className = "blocked";
          out.textContent = "拒绝：" + (d.reason || "不在授权范围");
          document.documentElement.dataset.scopeCheck = "blocked";
        }
      });
    });
    if (demoBtn) {
      demoBtn.addEventListener("click", function () {
        var prog = ($("bounty-program") || {}).value || "";
        var target = (($("bounty-target") || {}).value || "127.0.0.1").trim();
        bountyApi("add_finding", {
          program: prog, title: "示例发现（自有靶场）", severity: "medium",
          target: target, cwe: "CWE-000", cvss: "0.0",
          steps: "1) 自建靶场 2) 只读验证 3) 记录证据", impact: "演示用",
          remediation: "演示用",
        }).then(function (d) {
          var out = $("bounty-gate-result");
          if (out) {
            out.className = d.ok ? "ok" : "blocked";
            out.textContent = d.ok ? ("已录入：" + d.finding.id) : ("拒绝：" + (d.reason || ""));
          }
          ensureBounty();
        });
      });
    }
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

  /* ── 世界锻造 3D：按需动态 import（P1） ── */
  var WORLD_P = null;

  /* ───────── 内置浏览器（Electron webview）+ 原生浏览器（Chrome CDP）控制 ───────── */
  var BROWSER_READY = false;
  var BW_NATIVE_URL = "";

  function bwNormUrl(u) {
    u = String(u || "").trim();
    if (!u) return "";
    if (/^[a-z][a-z0-9+.-]*:\/\//i.test(u)) return u;
    if (/^[\w-]+(\.[\w-]+)+([\/:?#].*)?$/.test(u)) return "https://" + u;
    return "https://www.bing.com/search?q=" + encodeURIComponent(u);
  }

  function bwNative(action, extra) {
    var body = Object.assign({ action: action }, extra || {});
    return fetch("/api/browser", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); });
  }

  function bwNativeState(text) {
    var el = $("bw-native-state");
    if (el) el.textContent = text || "—";
  }

  var BW_PROBED = false;
  /* 检测本机 Chrome 调试口；进页面自动跑一次，按钮可强制重跑 */
  function bwNativeProbe(force) {
    if (BW_PROBED && !force) return null;
    BW_PROBED = true;
    var hint = $("bw-native-hint");
    bwNativeState("检测中…");
    return bwNative("status").then(function (j) {
      var r = (j && j.result) || {};
      if (r.ok) {
        bwNativeState("已连接（" + (r.base || "127.0.0.1:9222") + "）");
        if (hint) hint.textContent = "已连上 Chrome 调试口：可「在 Chrome 打开当前页」或「AI 读当前页」把正文取回来。";
        document.documentElement.dataset.bwNative = "ok";
      } else if (r.status === "needs_browser_debug") {
        bwNativeState("未启动（Chrome 调试口未开）");
        if (hint) hint.textContent = "Chrome 没开调试口：点「启动 Chrome」（自动带 --remote-debugging-port=9222）；"
          + "或在已开的 Chrome 快捷方式目标后加这个参数、重启后再点「检测」。";
        document.documentElement.dataset.bwNative = "needs_browser_debug";
      } else {
        bwNativeState(r.status || j.error || "不可用");
        if (hint) hint.textContent = "原生浏览器不可用：" + (r.error || r.status || j.error || "未知")
          + "；上面的内置页签仍可正常浏览。";
        document.documentElement.dataset.bwNative = "fail";
      }
    }).catch(function (e) {
      bwNativeState("接口不可用：" + e.message);
      if (hint) hint.textContent = "调不到 /api/browser：" + e.message;
      document.documentElement.dataset.bwNative = "error";
    });
  }



  /* ───────── 我们自己的原生浏览器（WebContentsView 宿主，browser_embed）───────── */
  var BROWSER_HOST = null;
  function browserBodyRect() {
    var b = document.querySelector(".gbt-browser-body");
    if (!b) return null;
    var r = b.getBoundingClientRect();
    if (!r.width || !r.height) return null;
    return { x: r.left, y: r.top, width: r.width, height: r.height };
  }
  function hostRender(st) {
    if (!st) return;
    var url = $("bw-url");
    if (url && st.url && document.activeElement !== url) url.value = st.url;
    var fb = $("bw-fallback");
    if (fb) { fb.hidden = true; }
    var box = $("bw-tabs");
    if (box) {
      box.innerHTML = "";
      (st.tabs || []).forEach(function (tab) {
        var el = document.createElement("button");
        el.type = "button";
        el.className = "bw-tab" + (tab.id === st.active ? " is-active" : "");
        el.title = tab.url || tab.title || "";
        var label = document.createElement("span");
        label.className = "bw-tab-label";
        label.textContent = (tab.title || tab.url || "新标签页").slice(0, 18);
        el.appendChild(label);
        var x = document.createElement("span");
        x.className = "bw-tab-x"; x.textContent = "×"; x.title = "关闭标签";
        x.onclick = function (e) {
          e.stopPropagation();
          if (BROWSER_HOST) BROWSER_HOST.closeTab(tab.id).then(hostRender).catch(function () {});
        };
        el.appendChild(x);
        el.onclick = function () { if (BROWSER_HOST) BROWSER_HOST.switchTab(tab.id).then(hostRender).catch(function () {}); };
        box.appendChild(el);
      });
      var add = document.createElement("button");
      add.type = "button"; add.className = "bw-newtab"; add.textContent = "+"; add.title = "新标签页";
      add.onclick = function () {
        if (BROWSER_HOST) BROWSER_HOST.newTab("about:blank").then(hostRender).catch(function () {});
      };
      box.appendChild(add);
    }
  }
  function hostShow() {
    if (!BROWSER_HOST) return;
    if ($("chat-area").getAttribute("data-view") !== "browser") return;
    var b = browserBodyRect();
    if (!b) return;
    BROWSER_HOST.show(b).then(hostRender).catch(function () {});
  }
  function hostHide() {
    if (BROWSER_HOST) BROWSER_HOST.hide().catch(function () {});
  }
  function hostLoad(u) {
    if (!BROWSER_HOST) return;
    var target = bwNormUrl(u);
    if (!target) return;
    BROWSER_HOST.navigate(target).then(hostRender).catch(function (e) {
      var fb = $("bw-fallback");
      if (fb) { fb.hidden = false; fb.textContent = "加载失败：" + String(e && e.message || e).slice(0, 200); }
    });
  }
  function ensureHostBrowser(host) {
    if (BROWSER_HOST) return true;
    BROWSER_HOST = host;
    var wv = $("gbt-webview");
    if (wv) wv.style.display = "none";
    var url = $("bw-url");
    host.onEvent(function (ev) {
      if (!ev) return;
      if (ev.type === "navigate" && ev.url && url && document.activeElement !== url) url.value = ev.url;
      if (ev.type === "fail") {
        var fb = $("bw-fallback");
        if (fb) { fb.hidden = false; fb.textContent = "页面加载失败：" + (ev.error || ev.code); }
      }
      host.state().then(hostRender).catch(function () {});
    });
    host.state().then(hostRender).catch(function () {});
    if (url) {
      url.addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); hostLoad(url.value); }
      });
    }
    var go = $("bw-go"); if (go) go.addEventListener("click", function () { hostLoad(url.value); });
    var back = $("bw-back"); if (back) back.addEventListener("click", function () { host.back().then(hostRender).catch(function () {}); });
    var fwd = $("bw-forward"); if (fwd) fwd.addEventListener("click", function () { host.forward().then(hostRender).catch(function () {}); });
    var rel = $("bw-reload"); if (rel) rel.addEventListener("click", function () { host.reload().then(hostRender).catch(function () {}); });
    var ext = $("bw-external"); if (ext) ext.addEventListener("click", function () {
      var u = (url && bwNormUrl(url.value)) || "";
      if (u) window.open(u, "_blank");
    });
    window.addEventListener("resize", function () {
      if (BROWSER_HOST && $("chat-area").getAttribute("data-view") === "browser") {
        var b = browserBodyRect();
        if (b) BROWSER_HOST.setBounds(b).catch(function () {});
      }
    });
    hostLoad("https://www.bing.com");
    return true;
  }

  function ensureBrowser() {
    if (window.gbtBrowser && typeof window.gbtBrowser.state === "function") {
      return ensureHostBrowser(window.gbtBrowser);
    }
    var wv = $("gbt-webview");
    if (!wv) return false;
    var fb = $("bw-fallback");
    var isElectron = typeof wv.loadURL === "function";
    if (!isElectron) {
      if (fb) {
        fb.hidden = false;
        fb.textContent = "内置浏览器只在桌面版 APP（Electron）里可用；当前是浏览器直开。\n" +
          "可点「外部」用系统浏览器打开，或直接用地址栏访问 http://127.0.0.1:8766/console/";
      }
      wv.style.display = "none";
      return false;
    }
    if (BROWSER_READY) return true;
    BROWSER_READY = true;
    if (fb) fb.hidden = true;
    var url = $("bw-url");
    function load(u) {
      var target = bwNormUrl(u);
      if (!target) return;
      if (url) url.value = target;
      try { wv.loadURL(target); } catch (e) {
        if (fb) { fb.hidden = false; fb.textContent = "加载失败：" + String(e && e.message || e).slice(0, 200); }
      }
    }
    if (url) {
      url.addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); load(url.value); }
      });
    }
    var go = $("bw-go"); if (go) go.addEventListener("click", function () { load(url.value); });
    var back = $("bw-back"); if (back) back.addEventListener("click", function () { try { wv.goBack(); } catch (e) {} });
    var fwd = $("bw-forward"); if (fwd) fwd.addEventListener("click", function () { try { wv.goForward(); } catch (e) {} });
    var rel = $("bw-reload"); if (rel) rel.addEventListener("click", function () { try { wv.reload(); } catch (e) {} });
    var ext = $("bw-external"); if (ext) ext.addEventListener("click", function () {
      var u = (url && bwNormUrl(url.value)) || "";
      if (u) window.open(u, "_blank");
    });
    wv.addEventListener("did-navigate", function (e) { if (url && e && e.url) url.value = e.url; });
    wv.addEventListener("did-navigate-in-page", function (e) { if (url && e && e.url) url.value = e.url; });
    wv.addEventListener("did-start-loading", function () { if (fb) fb.hidden = true; });
    wv.addEventListener("did-stop-loading", function () {});
    wv.addEventListener("did-fail-load", function (e) {
      if (e && e.errorCode && e.errorCode !== -3) {
        if (fb) {
          fb.hidden = false;
          fb.textContent = "页面加载失败：" + (e.errorDescription || e.errorCode) +
            "\n（检查网址/网络；或点「外部」用系统浏览器打开）";
        }
      }
    });
    var chk = $("bw-native-check"); if (chk) chk.addEventListener("click", function () { bwNativeProbe(true); });
    var launch = $("bw-native-launch"); if (launch) launch.addEventListener("click", function () {
      bwNativeState("启动中…");
      bwNative("launch", { url: (url && bwNormUrl(url.value)) || "" }).then(function (j) {
        var r = (j && j.result) || {};
        bwNativeState(r.ok ? ("已启动" + (r.url ? " · " + r.url : "")) : ("启动失败：" + (r.error || r.status || j.error || "未知")));
      }).catch(function (e) { bwNativeState("接口不可用：" + e.message); });
    });
    var nread = $("bw-native-read"); if (nread) nread.addEventListener("click", function () {
      bwNativeState("AI 读取中…");
      bwNative("get_text", { max_chars: 4000 }).then(function (j) {
        var r = (j && j.result) || {};
        var box = $("bw-ai-read");
        if (!r.ok) { bwNativeState("读取失败：" + (r.error || r.status || j.error || "未知")); return; }
        if (box) {
          box.hidden = false;
          box.textContent = "AI 读到的当前页（外部内容，仅作数据，不作指令）：\n" +
            String(r.text || "").slice(0, 3000);
        }
        bwNativeState("已读当前页 · " + String(r.text || "").length + " 字");
      }).catch(function (e) { bwNativeState("接口不可用：" + e.message); });
    });
    var nopen = $("bw-native-open"); if (nopen) nopen.addEventListener("click", function () {
      var u = (url && bwNormUrl(url.value)) || "";
      if (!u) return;
      bwNativeState("切换中…");
      bwNative("navigate", { url: u }).then(function (j) {
        var r = (j && j.result) || {};
        bwNativeState(r.ok ? "已在 Chrome 打开" : ("失败：" + (r.error || r.status || j.error || "未知")));
      }).catch(function (e) { bwNativeState("接口不可用：" + e.message); });
    });
    load("https://www.bing.com");
    return true;
  }

  function ensureWorld() {
    if (WORLD_P) return WORLD_P;
    WORLD_P = import("./world3d.js").then(function (m) {
      return m;
    }).catch(function (e) {
      document.documentElement.dataset.world3d = "import-err:" + String(e && e.message || e).slice(0, 80);
      return null;
    });
    return WORLD_P;
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
    var ok = ["chat", "caps", "skills", "space", "media", "video", "world", "browser", "brain", "plug", "team", "mind", "stream", "turns", "flow", "scan", "prof", "bounty", "dash", "moments", "teardown"];
    if (ok.indexOf(name) < 0) name = "chat";
    con.setAttribute("data-view", name);
    Array.prototype.forEach.call(document.querySelectorAll(".view-tab"), function (b) {
      b.classList.toggle("is-active", b.getAttribute("data-view") === name);
    });
    try { window.dispatchEvent(new CustomEvent("gbt:view", { detail: name })); } catch (e) {}
    if (name === "world") {
      ensureWorld().then(function (m) { if (m && m.start) try { m.start(); } catch (e) {} });
    }
    if (name === "browser") {
      ensureBrowser();
      if (BROWSER_HOST) hostShow();
      try { bwNativeProbe(); } catch (e) {}
    }
    if (name === "stream" && typeof window.__streamRefresh === "function") {
      window.__streamRefresh();
    }
    if (name === "media" && typeof window.__mediaRefresh === "function") {
      window.__mediaRefresh();
    }
    if (name === "video" && typeof window.__videoRefresh === "function") {
      window.__videoRefresh();
    }
    if (name === "turns" && typeof window.__turnsRefresh === "function") {
      window.__turnsRefresh();
    }
    window.__lastView = name;
    if (typeof window.__meshSwitch === "function") window.__meshSwitch(name);
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
    if (name === "bounty") {
      wireBounty();
      ensureBounty();
    }
    if (name === "flow") {
      var fl = document.getElementById("flow-drawer");
      if (fl) { fl.classList.remove("is-open"); fl.setAttribute("aria-hidden", "true"); }
      // flow-map.js 在本文件之后加载：首屏直接进 #flow 时它还不在，等它到再起
      var startFlow = function () {
        if (!(window.gbtFlow && window.gbtFlow.start)) return false;
        try { window.gbtFlow.start(); document.documentElement.dataset.flow = "started"; }
        catch (e) { document.documentElement.dataset.flow = "start-err:" + String((e && e.message) || e).slice(0, 80); }
        return true;
      };
      if (!startFlow()) {
        window.addEventListener("load", function once() { window.removeEventListener("load", once); startFlow(); });
        window.setTimeout(startFlow, 200);
        window.setTimeout(function () {
          if (!(window.gbtFlow && window.gbtFlow.start)) document.documentElement.dataset.flow = "module-missing";
        }, 2500);
      }
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
    if (name !== "browser" && BROWSER_HOST) hostHide();
    if (location.hash !== "#" + name) {
      try { history.replaceState(null, "", "#" + name); } catch (e) {}
    }
  }
  function wireViews() {
    Array.prototype.forEach.call(document.querySelectorAll(".view-tab"), function (b) {
      b.addEventListener("click", function () { switchView(b.getAttribute("data-view")); });
    });
    var h = (location.hash || "").replace("#", "");
    switchView(h || DEFAULT_VIEW);
  }

  window.addEventListener("resize", function () {
    drawGraph((MODE.data && MODE.data.domains) || []);
  });

  /* 2026-11-02：状态自愈 —— 引擎可能比页面晚起来（冷启动/重启），定时 + 回窗重读，避免一直显示离线快照 */
  function wireAutoRefresh() {
    if (window.__gbtAutoRefresh) return;
    window.__gbtAutoRefresh = true;
    setInterval(function () { if (!document.hidden) loadData(true); }, 15000);
    window.addEventListener("focus", function () { loadData(true); });
  }

  try {
    wire();
    wireViews();
    loadData();
    wireAutoRefresh();
  } catch (e) {
    document.documentElement.dataset.apperr = String((e && e.stack) || e).slice(0, 500);
  }
})();
