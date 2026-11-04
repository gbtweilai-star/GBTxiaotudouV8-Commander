/* 做好之后长这样 · 成品预览（2026-11-02）
 *
 * 用真画面讲人话：每个展板 = 本机真实跑出来的界面截图（console 各视图 / 蓝图页 / 记忆 API 卡片），
 * 页面往下滚 = 镜头穿过一页页成品；右侧「提整改」随时改，不用懂代码。
 * 落地进度读 /api/blueprint；批准后她自动做到完（除危险/转账不打扰）。
 * 立体感：CSS 3D 景深 + GSAP 缓动（本仓已 vendor gsap），滚动位置就是镜头位置。
 */
var $ = function (id) { return document.getElementById(id); };
var API = "/api/blueprint";

var DELIVERABLES = [
  { key: "chat", name: "聊天窗口", desc: "你和它说话的地方：问什么答什么，上下文不会断。", url: "/console/index.html#chat", status: "done" },
  { key: "caps", name: "它会做的事（385 项）", desc: "它所有能力列成一张表，点开就能用，不用记命令。", url: "/console/index.html#caps", status: "done" },
  { key: "space", name: "能力星图", desc: "一眼看到它会什么、分几大类，是一张活的星图。", url: "/console/index.html#space", status: "done" },
  { key: "team", name: "分工网络", desc: "多个角色怎么协作、消息怎么流转，像一张会呼吸的网。", url: "/console/index.html#team", status: "done" },
  { key: "mind", name: "任务指引", desc: "接到任务后拆成一步步：做什么、怎么判定成功、卡住怎么办。", url: "/console/index.html#mind", status: "done" },
  { key: "dash", name: "仪表盘", desc: "现在跑得怎么样、哪块报警，一页看完。", url: "/console/index.html#dash", status: "done" },
  { key: "prof", name: "职业分工", desc: "哪类活归哪个职业、会调哪些能力，派单前先看清。", url: "/console/index.html#prof", status: "done" },
  { key: "bp", name: "这一页（成品预览）", desc: "你现在看的这页：完工前先看到成品，随时能提整改。", url: "/blueprint3d/", status: "doing" },
  { key: "memory", name: "它会记住的事", desc: "聊过、做过的东西都会记住，随时能查回来，还能验有没有被改。", url: "/api/memory?op=stats", status: "done" }
];
var state = { idx: 0, cursor: 0, data: null, omni: null, revKey: "" };

var cards = [], dots = [];

function esc(s) {
  return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function buildCards() {
  var world = $("world");
  var dotsEl = $("dots");
  world.innerHTML = ""; dotsEl.innerHTML = "";
  cards = []; dots = [];
  DELIVERABLES.forEach(function (d, i) {
    var el = document.createElement("div");
    el.className = "card" + (d.status === "doing" ? " is-doing" : "");
    if (d.key === "memory") {
      var mem = document.createElement("div");
      mem.className = "memcard";
      mem.innerHTML = "<h3>它会记住的事</h3>" +
        "<div class='memrow'><b id='m-index'>—</b><span>条记忆</span></div>" +
        "<div class='memrow'><b id='m-tri'>—</b><span>中文子串可搜</span></div>" +
        "<div class='memrow'><b id='m-ver'>—</b><span>条防改链</span></div>" +
        "<p>聊过 / 做过的都会记住，随时能查回来；改一个字都能验出来。</p>";
      el.appendChild(mem);
    } else {
      var img = document.createElement("img");
      img.src = "./previews/" + d.key + ".png";
      img.alt = d.name;
      el.appendChild(img);
    }
    var tint = document.createElement("div"); tint.className = "tint"; el.appendChild(tint);
    var badge = document.createElement("div"); badge.className = "badge";
    badge.innerHTML = "<i></i>" + esc(d.name) + " · " +
      (d.status === "doing" ? "在建" : "已做好");
    el.appendChild(badge);
    var tryb = document.createElement("button");
    tryb.type = "button"; tryb.className = "trybtn"; tryb.textContent = "试用";
    tryb.addEventListener("click", function (ev) {
      ev.stopPropagation(); openTry(d.key);
    });
    el.appendChild(tryb);
    world.appendChild(el);
    cards.push(el);

    var dot = document.createElement("i");
    dot.addEventListener("click", function () { goto(i); });
    dotsEl.appendChild(dot);
    dots.push(dot);
    el.addEventListener("click", function () {
      if (Math.abs(i - state.cursor) < 0.25) window.open(d.url, "_blank");
      else goto(i);
    });
  });
}

function sceneHeight() {
  return (DELIVERABLES.length + 1) * window.innerHeight;
}

function goto(i) {
  i = Math.max(0, Math.min(DELIVERABLES.length - 1, i));
  var top = (i / Math.max(1, DELIVERABLES.length - 1)) * (sceneHeight() - window.innerHeight);
  window.scrollTo({ top: top, behavior: "smooth" });
}

function updateCaption(i) {
  var d = DELIVERABLES[i];
  if (!d) return;
  var nameEl = $("cap-name"), descEl = $("cap-desc");
  if (window.gsap) {
    window.gsap.to([nameEl, descEl], { opacity: 0, y: 6, duration: 0.12, onComplete: function () {
      nameEl.textContent = d.name;
      descEl.textContent = d.desc;
      window.gsap.to([nameEl, descEl], { opacity: 1, y: 0, duration: 0.22, ease: "power2.out" });
    } });
  } else {
    nameEl.textContent = d.name;
    descEl.textContent = d.desc;
  }
  var chip = $("cap-status");
  chip.textContent = d.status === "doing" ? "在建" : "已做好";
  chip.className = "chip " + d.status;
  $("cap-open").href = d.url;
  state.idx = i;
  dots.forEach(function (x, k) { x.className = k === i ? "on" : ""; });
}

function layout() {
  var vw = window.innerWidth, vh = window.innerHeight;
  var n = DELIVERABLES.length;
  cards.forEach(function (el, i) {
    var d = i - state.cursor;
    var baseX = vw / 2 - el.offsetWidth / 2;
    var baseY = vh * 0.46 - el.offsetHeight / 2;
    var x = baseX + d * (vw * 0.5);
    var y = baseY + d * (-vh * 0.03);
    var z = -Math.abs(d) * 900;
    var ry = -d * 16;
    var sc = 1 - Math.min(0.26, Math.abs(d) * 0.05);
    el.style.transform = "translate3d(" + x + "px," + y + "px," + z + "px) rotateY(" + ry +
      "deg) scale(" + sc + ")";
    el.style.opacity = String(Math.max(0.06, 1 - Math.abs(d) * 0.45));
    el.style.zIndex = String(100 - Math.round(Math.abs(d) * 10));
    el.classList.toggle("is-gray", state.data && state.data.landing &&
      state.data.landing.state === "running" && d !== 0 ? false : false);
  });
}

function scrollTarget() {
  var max = Math.max(1, sceneHeight() - window.innerHeight);
  var p = Math.min(1, Math.max(0, window.scrollY / max));
  return p * (DELIVERABLES.length - 1);
}

var lastIdx = -1;
function tick() {
  var target = scrollTarget();
  state.cursor += (target - state.cursor) * 0.12;
  if (Math.abs(target - state.cursor) < 0.0006) state.cursor = target;
  layout();
  var idx = Math.round(state.cursor);
  if (idx !== lastIdx) { lastIdx = idx; updateCaption(idx); }
  requestAnimationFrame(tick);
}

function plainState(d) {
  if (!d || !d.id) return "还没开工";
  if (d.landed) return "做完了";
  if (d.landing && d.landing.state === "running") return "她自己做到完";
  if (d.revise && d.revise.some(function (x) { return !x.resolved; })) return "等你确认整改";
  if (d.approved) return "已批准，待开工";
  return "等你批准";
}

function renderStats(d) {
  state.data = d;
  var done = DELIVERABLES.filter(function (x) { return x.status === "done"; }).length;
  $("k-pct").textContent = Math.round(done / DELIVERABLES.length * 100) + "%";
  $("k-count").textContent = done + " / " + DELIVERABLES.length;
  $("k-state").textContent = plainState(d);
  $("k-exec").textContent = state.omni && state.omni.ok ? "她自己来" : "—";
  var bpLine = $("cap-bp");
  if (bpLine) {
    bpLine.textContent = d.id
      ? ("落地清单 " + (d.done || 0) + " / " + (d.total || 0) + " 项" +
         (d.current ? " · 下一步：" + d.current : " · 全部完成"))
      : "";
  }
  $("b-approve").disabled = !d.id || !!d.approved;
  $("b-land").disabled = !d.id || !d.approved ||
    (d.landing && d.landing.state === "running");
  renderRevise(d);
}

function renderRevise(d) {
  var items = (d && d.revise) || [];
  $("r-count").textContent = items.length;
  $("r-list").innerHTML = items.map(function (x) {
    return "<div class='rev" + (x.resolved ? " is-resolved" : "") + "'><span>" +
      esc(x.at) + "</span> · " + esc(x.task || "整体") + "<br>" + esc(x.note) + "</div>";
  }).join("") || "<div class='rev'><span>还没有整改记录</span></div>";
}

function apiJson(url, opts) {
  return fetch(url, opts).then(function (r) {
    return r.json().then(function (j) { return { status: r.status, body: j }; });
  });
}
function post(body) {
  return apiJson(API, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body) });
}
function refresh() {
  return apiJson(API).then(function (r) {
    renderStats(r.body || {});
  }).catch(function () {});
}

function openDrawer(d) {
  state.revKey = d.key;
  $("d-title").textContent = "给「" + d.name + "」提整改";
  $("d-meta").textContent = "说人话就行：哪里不对、想改成什么样。会写进整改记录，落地前会照它改。";
  $("d-note").value = "";
  $("drawer").hidden = false;
  if (window.gsap) window.gsap.fromTo("#drawer", { x: 18, opacity: 0 },
    { x: 0, opacity: 1, duration: 0.25, ease: "power2.out" });
}

/* ---------- 试用台：用的都是真功能 ---------- */
function tryTab(name) {
  document.querySelectorAll(".try-tabs button").forEach(function (b) {
    b.classList.toggle("on", b.getAttribute("data-tab") === name);
  });
  document.querySelectorAll(".try-pane").forEach(function (p) {
    p.classList.toggle("on", p.getAttribute("data-pane") === name);
  });
  if (name === "page") {
    var fr = $("t-page-frame");
    if (fr && fr.getAttribute("src") === "about:blank") {
      var sel = $("t-page-sel");
      if (sel && sel.value) { fr.src = sel.value; $("t-page-open").href = sel.value; }
    }
  }
}

function openTry(key) {
  var d = DELIVERABLES.filter(function (x) { return x.key === key; })[0] || DELIVERABLES[0];
  $("try").hidden = false;
  if (window.gsap) {
    window.gsap.fromTo(".try-box", { y: 10, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.22, ease: "power2.out" });
  }
  if (key === "memory") { tryTab("memory"); return; }
  tryTab("page");
  var sel = $("t-page-sel");
  if (sel) {
    sel.value = d.url;
    $("t-page-open").href = d.url;
    $("t-page-frame").src = d.url;
  }
}

function closeTry() { $("try").hidden = true; $("t-page-frame").src = "about:blank"; }

function memSave() {
  var t = $("t-mem-in").value.trim();
  var out = $("t-mem-out");
  if (!t) { out.textContent = "先写一句要记住的话。"; return; }
  out.textContent = "写入中…";
  apiJson("/api/memory", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ op: "write", src: "trial", name: "preview-trial", text: t }) })
    .then(function (r) {
      var b = r.body || {};
      var res = (b.results || [])[0] || {};
      if (b.ok && res.ok) {
        out.textContent = "已存进真实记忆链 ✅\n" +
          "版本 version = " + res.version + "（链上第几条）\n" +
          "哈希 h = " + String(res.h || "").slice(0, 16) + "…\n" +
          "来源=" + res.src + " · " + (res.at || "") + "\n\n" +
          "下一步：在下面输入关键词，点「查回来」看它真能召回。";
      } else {
        out.textContent = "写入失败：" + JSON.stringify(b).slice(0, 400);
      }
    }).catch(function (e) { out.textContent = "写入失败：" + String(e); });
}

function memFind() {
  var q = $("t-mem-q").value.trim();
  var out = $("t-mem-out");
  if (!q) { out.textContent = "先写一个要查的关键词。"; return; }
  out.textContent = "查询中…";
  fetch("/api/memory?op=recall&k=3&q=" + encodeURIComponent(q))
    .then(function (r) { return r.json(); }).then(function (b) {
      if (!b.ok) { out.textContent = "查询失败：" + JSON.stringify(b).slice(0, 300); return; }
      var cov = b.coverage || {};
      var lines = [
        "查到了 " + (b.total || 0) + " 条（覆盖率 " + (cov.matched || 0) + "/" + (cov.terms || 0) + " = " +
          Math.round((cov.rate || 0) * 100) + "%）"
      ];
      (b.hits || []).slice(0, 3).forEach(function (h, i) {
        lines.push("", (i + 1) + ". " + (h.text || "").slice(0, 90) +
          "\n   来源=" + h.src + " · " + (h.at || ""));
      });
      if (!b.total) lines.push("", "没查到：可能这个关键词还没存过。");
      out.textContent = lines.join("\n");
    }).catch(function (e) { out.textContent = "查询失败：" + String(e); });
}

function chatAsk() {
  var t = $("t-chat-in").value.trim();
  var out = $("t-chat-out");
  if (!t) { out.textContent = "先问一句。"; return; }
  out.textContent = "她在想…（本机模型可能要几十秒，超时会如实报）";
  var ctrl = new AbortController();
  var timer = setTimeout(function () { ctrl.abort(); }, 150000);
  fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: t, context: "preview-trial" }), signal: ctrl.signal })
    .then(function (r) { return r.json(); }).then(function (b) {
      clearTimeout(timer);
      out.textContent = b.ok
        ? (String(b.text || "") + "\n\n—— 用掉 " + (b.ms || b.elapsed_ms || "?") + " ms")
        : ("没电/出错（不编答案）：" + String(b.error || "").slice(0, 300));
    }).catch(function (e) {
      clearTimeout(timer);
      out.textContent = "没等到她（" + String(e) + "）。可以再试一次，或先看页面。";
    });
}

function wire() {
  $("cap-revise").addEventListener("click", function () {
    openDrawer(DELIVERABLES[state.idx]);
  });
  document.querySelectorAll(".try-tabs button").forEach(function (b) {
    b.addEventListener("click", function () { tryTab(b.getAttribute("data-tab")); });
  });
  $("try-close").addEventListener("click", closeTry);
  $("t-mem-save").addEventListener("click", memSave);
  $("t-mem-find").addEventListener("click", memFind);
  $("t-chat-go").addEventListener("click", chatAsk);
  $("t-chat-in").addEventListener("keydown", function (e) { if (e.key === "Enter") chatAsk(); });
  $("t-mem-in").addEventListener("keydown", function (e) { if (e.key === "Enter") memSave(); });
  $("t-page-sel").innerHTML = DELIVERABLES.map(function (d) {
    return "<option value='" + esc(d.url) + "'>" + esc(d.name) + "</option>";
  }).join("");
  $("t-page-sel").addEventListener("change", function () {
    $("t-page-frame").src = this.value;
    $("t-page-open").href = this.value;
  });
  $("d-close").addEventListener("click", function () { $("drawer").hidden = true; });
  $("b-refresh").addEventListener("click", function () { refresh(); loadOmni(); });
  $("b-approve").addEventListener("click", function () {
    if (!state.data || !state.data.id) { alert("还没有蓝图：先用页面里的入口生成一份。"); return; }
    if (!confirm("批准开工？之后她自动做到完，除危险/转账不再打扰你。")) return;
    post({ op: "approve", id: state.data.id }).then(function (r) {
      alert(r.body && r.body.ok ? "已批准：她开始自己做了。" : JSON.stringify(r.body || {}));
      refresh();
    });
  });
  $("b-land").addEventListener("click", function () {
    if (!state.data || !state.data.id) return;
    post({ op: "land", id: state.data.id, max_rounds: 6 }).then(function (r) {
      if (!(r.body && r.body.ok)) alert(JSON.stringify(r.body || {}));
      refresh();
    });
  });
  $("d-submit").addEventListener("click", function () {
    var note = $("d-note").value.trim();
    if (!state.data || !state.data.id) { alert("还没有蓝图。"); return; }
    if (!note) { alert("写一句你想怎么改"); return; }
    post({ op: "revise", id: state.data.id, task: state.revKey, note: note })
      .then(function (r) {
        if (r.body && r.body.ok) { $("d-note").value = ""; refresh(); }
        else alert(JSON.stringify(r.body || {}));
      });
  });
  $("d-ack").addEventListener("click", function () {
    if (!state.data || !state.data.id) return;
    post({ op: "revise_ack", id: state.data.id, task: state.revKey })
      .then(function () { refresh(); });
  });
  window.addEventListener("scroll", function () {}, { passive: true });
  window.addEventListener("resize", function () { layout(); });
}

function loadOmni() {
  return apiJson("/api/omni").then(function (r) {
    state.omni = r.body || {};
    if (state.data) renderStats(state.data);
  }).catch(function () {});
}

function loadMemory() {
  return fetch("/api/memory?op=stats").then(function (r) { return r.json(); }).then(function (b) {
    var sync = (b && b.sync) || {}, idx = (b && b.index) || {};
    var fts = idx.fts || {};
    var set = function (id, v) {
      var el = $(id);
      if (el) el.textContent = (v == null ? "—" : v);
    };
    set("m-index", idx.total);
    set("m-tri", fts.trigram);
    set("m-ver", sync.version);
  }).catch(function () {});
}

buildCards();
loadMemory();
wire();
layout();
lastIdx = 0; updateCaption(0);
tick();
loadOmni();
refresh();
setInterval(function () {
  if (state.data && state.data.landing && state.data.landing.state === "running") refresh();
}, 4000);
window.__bp3d = { goto: goto, openTry: openTry, tryTab: tryTab,
  memSave: memSave, memFind: memFind, chatAsk: chatAsk,
  get data() { return state.data; }, get idx() { return state.idx; } };
