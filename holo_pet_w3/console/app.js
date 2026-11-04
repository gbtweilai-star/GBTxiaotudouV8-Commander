/* GBT小土豆V8 · 认知界面逻辑
 * 数据：优先 /api/data（console-server 现读）；直开 file:// 时退回 window.GBT_CONSOLE。
 * 对话：/api/chat → energy_core.think(context="console-web")（无限上下文 + temperature=0 稳定输出）。
 */
(function () {
  "use strict";

  var MODE = { online: false, data: null };
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
        if (j && j.ok && j.data) { MODE.online = true; MODE.data = j.data; render(j.data); }
        else throw new Error((j && j.error) || "无数据");
      })
      .catch(function (e) {
        if (silent && MODE.online) return;      // 静默刷新失败：保留当前实时数据，不污染界面
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

  function chatSubmit(text) {
    var _att = ATTACH;
    addUserMsg(text, _att);
    if (_att) clearAttachPreview();
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
      body: JSON.stringify({
        text: text, context: "console-web",
        image: (_att && _att.kind === "image") ? _att.dataUrl : "",
        image_name: (_att && _att.kind === "image") ? (_att.name || "") : "",
        file: (_att && _att.kind === "file") ? _att.dataUrl : "",
        file_name: (_att && _att.kind === "file") ? (_att.name || "") : "",
        file_type: (_att && _att.kind === "file") ? (_att.type || "") : ""
      })
    }).then(function (r) { return r.json(); }).then(function (j) {
      pending.remove();
      if (j && j.ok) {
        var meta;
        if (j.via === "capability_router") {
          // 2026-11-02：四类能力（看屏幕/开网页/读写文件/看图）走万能插真执行，回执如实标出来
          meta = "万能插 · " + (j.label || j.intent || "能力") +
            (j.ms != null ? " · " + j.ms + "ms" : "") + " · 已落审计";
        } else if (j.via && (j.via.indexOf("file:") === 0 || j.via === "vision:local")) {
          // 2026-11-02：对话附图 / 文件发送 —— 本地解析，不借云端
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
    wireProfDispatch();
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
    var chk = $("bw-native-check"); if (chk) chk.addEventListener("click", function () {
      bwNativeState("检测中…");
      bwNative("status").then(function (j) {
        var r = (j && j.result) || {};
        bwNativeState(r.ok ? "已连接（" + (r.base || "127.0.0.1:9222") + "）"
          : (r.status === "needs_browser_debug" ? "未启动（Chrome 调试口未开）" : (r.status || j.error || "不可用")) +
            (r.browser_executable ? " · " + r.browser_executable : ""));
      }).catch(function (e) { bwNativeState("接口不可用：" + e.message); });
    });
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
    var ok = ["chat", "caps", "skills", "space", "media", "video", "world", "browser", "brain", "plug", "team", "mind", "stream", "turns", "scan", "prof", "bounty", "dash", "moments", "teardown"];
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
    switchView(h || "chat");
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
