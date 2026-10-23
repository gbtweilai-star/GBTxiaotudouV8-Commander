/* GBT小土豆V8 · 语音剧场 · **触手驱动的动作层**（2026-10-18 主人令）
 *
 * 主人原话：「使用她的原生能力触手继续绑定上，让她按照触手想让她这么动就这么动」。
 *
 * ## 它把什么接起来
 * 壳桥 `gbtW3.capActivity()` 读的是**真账本** `gbt_allinone/store/audit.jsonl` 的尾部
 * （谁在动、动了几次、成没成 —— 只读）。本文件把这份**真实活动流**翻译成她的动作：
 *
 *   触手活动                        她的动作（真骨骼，不是贴图动画）
 *   ────────────────────────────────────────────────────────────────
 *   vision/tentacle/see（在看）      → look（头转向，颈随动）
 *   denied / ok:false（被拒/失败）    → shake（摇头）+ 肩微沉
 *   click/type/exec（动手）          → nod（点头）×2
 *   obsidian/memory（记东西）         → tilt（歪头想）
 *   其它成功调用                      → sway（轻微换重心）
 *
 * ## 三条纪律
 * 1. **动的是她自己的骨骼**：上臂/前臂/头/颈/胸椎 —— 与 `dh3d.js` 共用同一副 rig。
 * 2. **不抢状态机**：待机/在听/在想/在说 的姿态偏移仍由 `dh3d.js` 负责；这里的动作是**叠加**。
 * 3. **取不到就明说**：`capActivity` 不可用/为空时，状态条写「触手活动：未读到」，不假装在跟着动。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
(function () {
  "use strict";

  var S = { ok: false, why: "未开始", last: null, played: 0, source: "gbtW3.capActivity" };
  var queue = [];            /* [{gesture, t, dur, amp}] */
  var lastSeenTotal = null;

  /* ── 手势库：只写"相对偏移"，每帧由 dh3d 的 tick 调用 apply() 叠加 ────────── */
  var GESTURES = {
    nod:       [{ bone: "mixamorig:Head", ax: "x", amp: 0.10, freq: 2.1, cycles: 1.2 }],
    look:      [{ bone: "mixamorig:Head", ax: "y", amp: 0.26, freq: 0.9, cycles: 1 },
                { bone: "mixamorig:Neck", ax: "y", amp: 0.12, freq: 0.9, cycles: 1 }],
    tilt:      [{ bone: "mixamorig:Head", ax: "z", amp: 0.13, freq: 0.7, cycles: 1 }],
    shake:     [{ bone: "mixamorig:Head", ax: "y", amp: 0.10, freq: 4.2, cycles: 2 },
                { bone: "mixamorig:Spine1", ax: "x", amp: 0.03, freq: 4.2, cycles: 2 }],
    sway:      [{ bone: "mixamorig:Spine2", ax: "z", amp: 0.045, freq: 0.8, cycles: 1 },
                { bone: "mixamorig:Hips", ax: "y", amp: 0.02, freq: 0.8, cycles: 1 }],
    raise_right: [{ bone: "mixamorig:RightArm", ax: "z", amp: 0.42, freq: 1.1, cycles: 1 },
                  { bone: "mixamorig:RightForeArm", ax: "x", amp: 0.28, freq: 1.1, cycles: 1 }],
    both_hands: [{ bone: "mixamorig:RightArm", ax: "z", amp: 0.30, freq: 1.0, cycles: 1 },
                 { bone: "mixamorig:LeftArm", ax: "z", amp: -0.30, freq: 1.0, cycles: 1 }],
    bow:       [{ bone: "mixamorig:Spine", ax: "x", amp: 0.16, freq: 0.9, cycles: 1 },
                { bone: "mixamorig:Neck", ax: "x", amp: 0.08, freq: 0.9, cycles: 1 }]
  };

  /* ── 活动 → 手势 ───────────────────────────────────────────────────────── */
  function pickGesture(row) {
    var m = (row && row.meta) || {};
    var kind = String(m.kind || row.kind || "").toLowerCase();
    var act = String(m.action || m.op || row.action || "").toLowerCase();
    var okFlag = m.ok !== undefined ? !!m.ok : (row.ok !== undefined ? !!row.ok : null);
    var ev = String(row.event || m.event || "").toLowerCase();

    if (okFlag === false || ev === "deny" || ev === "denied" || m.denied === true) return { g: "shake", amp: 1.0 };
    if (/vision|tentacle|see|seen|capture|screenshot|gods_eye/.test(kind + " " + act)) return { g: "look", amp: 1.0 };
    if (/obsidian|memory|vault|brain/.test(kind)) return { g: "tilt", amp: 0.9 };
    if (/click|type|key|exec|console|mouse|window/.test(kind + " " + act)) return { g: "nod", amp: 1.0 };
    if (/voice|speak|tts/.test(kind)) return { g: "both_hands", amp: 0.7 };
    return { g: "sway", amp: 0.6 };
  }

  function push(g, amp) {
    var spec = GESTURES[g];
    if (!spec) return;
    /* 同类动作不排队堆叠：只保留最后一个，避免"抽风" */
    queue = queue.filter(function (q) { return q.g !== g; });
    queue.push({ g: g, spec: spec, t0: performance.now(), dur: 1400, amp: amp || 1 });
    S.last = g;
    S.played += 1;
  }

  /* ── 每帧叠加（由 dh3d.js 的 tick 调用；它负责拿到骨骼表）──────────────── */
  function apply(B) {
    if (!queue.length || !B) return;
    var now = performance.now();
    var keep = [];
    queue.forEach(function (q) {
      var p = (now - q.t0) / q.dur;
      if (p >= 1) return;                       /* 播完就丢 */
      keep.push(q);
      var env = Math.sin(Math.PI * p) * q.amp;  /* 起-落包络：不许突然弹 */
      q.spec.forEach(function (c) {
        var b = B[c.bone] || B[c.bone.replace(/[^\w\-]/g, "")];
        if (!b) return;
        var phase = Math.sin(2 * Math.PI * c.freq * (now - q.t0) / 1000);
        b.rotation[c.ax] += c.amp * env * phase * (c.cycles >= 1 ? 1 : 1);
      });
    });
    queue = keep;
  }

  function info() { return { ok: S.ok, why: S.why, last: S.last, played: S.played, queued: queue.length, source: S.source }; }

  function report(t) {
    var el = document.getElementById("dh3dStatus");
    if (el && el.getAttribute("data-tone") === "ok") el.textContent = String(el.textContent).replace(/\s*·\s*触手活动：.*$/, "") + " · " + t;
  }

  /* ── 拉真活动流 ───────────────────────────────────────────────────────── */
  function poll() {
    if (!window.gbtW3 || typeof window.gbtW3.capActivity !== "function") {
      S.ok = false; S.why = "壳桥没有 capActivity（裸浏览器/旧壳）";
      report("触手活动：未读到（没接上壳桥）");
      return;
    }
    Promise.resolve(window.gbtW3.capActivity()).then(function (r) {
      if (!r || r.ok !== true) {
        S.ok = false; S.why = "capActivity 回错：" + String((r && r.error) || "未读到原因");
        report("触手活动：未读到（" + String((r && r.error) || "桥回错").slice(0, 30) + "）");
        return;
      }
      var total = Number(r.total || 0);
      var tail = Array.isArray(r.tail) ? r.tail : [];
      S.ok = true; S.why = "";
      if (lastSeenTotal === null) {
        lastSeenTotal = total;                  /* 首轮只对齐基线，不把历史当新动作 */
        report("触手活动：已接上（账本 " + total + " 条）");
        return;
      }
      if (total > lastSeenTotal) {
        var fresh = tail.slice(-Math.min(3, total - lastSeenTotal));
        fresh.forEach(function (row) {
          var pick = pickGesture(row);
          push(pick.g, pick.amp);
        });
        lastSeenTotal = total;
      }
    }).catch(function (e) {
      S.ok = false; S.why = "capActivity 异常：" + String((e && e.message) || e);
      report("触手活动：未读到（异常）");
    });
  }

  /* 对外 */
  window.GBT_MOTION = {
    apply: apply,
    play: function (g, amp) { push(String(g || "sway"), amp); },
    info: info,
    gestures: Object.keys(GESTURES)
  };

  S.ok = true;
  /* 第一轮定基线 + 贴状态；3D 舞台要后载（6.4MB 模型），所以头两秒补几拍，
     免得状态条停在"载入中…"时被拍到（2026-10-18 实拍踩到过这个读数假象）。 */
  poll();
  [800, 1800, 3200].forEach(function (ms) { setTimeout(poll, ms); });
  setInterval(poll, 2500);
})();
