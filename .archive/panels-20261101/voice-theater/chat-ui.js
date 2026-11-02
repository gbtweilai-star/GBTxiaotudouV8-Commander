/* GBT小土豆V8 · 语音剧场 · **对话主区**（照主人现在用的这个对话框做）
 *
 * 主人 2026-10-18 逐字：「按照我们现在这个对话框设计然后加装我们的能力以及语音交互」。
 * ⇒ 左列 = 消息流（谁说的 / 说了什么 / 工具回执卡），下边 = 输入条，右侧 = 她（3D）+ 链路体检。
 *
 * ## 三条纪律（跟本仓一致）
 * 1. **不编回话**：桥不通就贴"没接上壳桥"，桥回错就把它的 error/status 原话抄进气泡。
 * 2. **能力走壳桥的真口**：`window.gbtW3.health / tasks / tools / selfcheck`（preload 暴露的那些），
 *    不另造一套"假能力"。取不到就红字写清缺哪个口。
 * 3. **输入条与语音共用一台状态机**：打字发送 = think→speak；按住光球 = listen（页面原逻辑不动）。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
(function () {
  "use strict";

  var list = document.getElementById("chatList");
  var sub = document.getElementById("chatSub");
  var say = document.getElementById("say");
  var send = document.getElementById("send");
  var mcap = document.getElementById("mcap");
  if (!list) return;

  function hhmm() {
    var d = new Date();
    return ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2);
  }

  function push(kind, who, text) {
    var row = document.createElement("div");
    row.className = "msg " + (kind === "me" ? "msg--me" : (kind === "err" ? "msg--her msg--err" : (kind === "tool" ? "msg--her msg--tool" : "msg--her")));
    var w = document.createElement("div");
    w.className = "msg__who";
    w.textContent = who + " · " + hhmm();
    var b = document.createElement("div");
    b.className = "msg__body";
    b.textContent = String(text == null ? "" : text);
    row.appendChild(w);
    row.appendChild(b);
    list.appendChild(row);
    list.scrollTop = list.scrollHeight;
    return row;
  }
  window.GBT_CHAT = { push: push };

  push("her", "GBT小土豆V8", "我在。左边这条是我们的对话，右边是我。按住那颗圆球就能说，也可以直接打字。");

  function bridge() {
    return (window.gbtW3 && typeof window.gbtW3.message === "function") ? window.gbtW3 : null;
  }

  function setSub(t) { if (sub) sub.textContent = t; }

  /* 回话出声：走壳桥 → 能力位 `cap voice op=speak`（同一门；edge-tts zh-TW）。
     拿不到就**如实说**，绝不用 SAPI 冒充她（本页已无任何 zh-CN 合成）。
     🔴 2026-10-19（主人令）：这一次合成要**落成一个文件**（play:false 不让系统声卡出声），
     再由页面用 WebAudio 播放**同一个文件** ⇒ 波形吃的是这一句真音频，声音也只有一路（不双响）。 */
  function speakReply(text) {
    var t = String(text || "").trim();
    if (!t) return;
    if (!window.gbtW3 || typeof window.gbtW3.say !== "function") {
      setSub("没接上壳桥的嘴（gbtW3.say 不在）⇒ 这段不回话出声");
      return;
    }
    var OUT = "holo_pet_w3/voice-theater/assets/.utt/last.mp3";
    window.gbtW3.say({ text: t, out: OUT, play: false }).then(function (r) {
      if (!(r && r.ok === true)) {
        setSub("出声失败：" + String((r && (r.error || r.reason)) || "未读到原因"));
        push("err", "系统", "这句没能出声：" + String((r && (r.error || r.reason)) || "未读到原因") + "\n（原因照抄能力位回执，不编）");
        return;
      }
      /* 真产物 → 波形换源。URL 相对页面目录：assets/.utt/last.mp3 */
      var file = String(r.file || OUT).replace(/^holo_pet_w3\/voice-theater\//, "");
      var url = file + "?v=" + Date.now();
      if (window.GBT_AUDIO && typeof window.GBT_AUDIO.speakFile === "function") {
        setSub("她的神经嗓已就绪（" + (r.voice || "edge-tts") + "）· 播放这一句的真音频");
        window.GBT_AUDIO.speakFile(url).then(function (ok) {
          if (!ok) {
            var info = (window.GBT_AUDIO.info && window.GBT_AUDIO.info()) || {};
            setSub("这句落到盘上了，但波形没换源成功：" + String(info.err || "未读到原因"));
            push("err", "系统", "波形换源失败：" + String(info.err || "未读到原因") + "\n（文件仍是 " + file + "）");
          }
        });
      } else {
        setSub("已合成（" + (r.voice || "edge-tts") + "），但页面没有音频引擎 ⇒ 这句没放出来");
      }
    }).catch(function (e) {
      setSub("出声异常：" + String((e && e.message) || e));
    });
  }

  function sendText() {
    var t = String(say.value || "").trim();
    if (!t) return;
    push("me", "你", t);
    say.value = "";
    var b = bridge();
    if (!b) {
      setSub("没接上壳桥 · 这句没有送出去");
      push("err", "系统", "没接上壳桥（window.gbtW3.message 不在）⇒ 这句没有送出去。\n裸浏览器打开时就是这样，不是坏了。");
      return;
    }
    var row = push("her", "GBT小土豆V8", "…（已送出，等回话）");
    var body = row.querySelector(".msg__body");
    b.message({ text: t }).then(function (r) {
      if (r && r.ok) {
        body.textContent = String(r.reply || "（桥回空：HTTP " + (r.status || "?") + "，没有正文）");
        setSub("已连壳桥 · 上一句已回话");
        speakReply(String(r.reply || ""));
      } else {
        row.className = "msg msg--her msg--err";
        body.textContent = "没回话：" + String((r && (r.error || ("HTTP " + r.status))) || "未读到原因") + "\n（桥原话照抄，不编）";
        setSub("桥回错 · 原因见气泡");
      }
      list.scrollTop = list.scrollHeight;
    }).catch(function (e) {
      row.className = "msg msg--her msg--err";
      body.textContent = "调用异常：" + String((e && e.message) || e);
    });
  }

  if (send) send.addEventListener("click", sendText);
  if (say) {
    say.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendText(); }
    });
  }

  /* 能力条：**她自己动手**（2026-10-18 下一步「她 → 触手」）。
     走壳桥 gbtW3.cap → 壳里写死的**只读白名单** → 唯一门 cap <kind>；
     表外的 kind 一定被拒（回执里带允许名单），页面不自己判断能不能。 */
  var CAPS = {
    health:    { label: '健康',   kind: 'health' },
    selfscan:  { label: '自检',   kind: 'selfscan' },
    alerts:    { label: '异常',   kind: 'alerts' },
    inventory: { label: '清点',   kind: 'inventory' }
  };

  function flatten(r) {
    if (r == null) return '（空回执）';
    if (typeof r === 'string') return r;
    if (r.error) return 'error: ' + r.error;
    if (r.text) return String(r.text);
    try { return JSON.stringify(r, null, 1).slice(0, 6000); } catch (e) { return String(r); }
  }

  if (mcap) {
    mcap.addEventListener('click', function (ev) {
      var btn = ev.target && ev.target.closest ? ev.target.closest('.mcap__btn') : null;
      if (!btn) return;
      var key = btn.getAttribute('data-cap');
      var spec = CAPS[key];
      if (!spec) return;
      var b = bridge();
      if (!b || typeof b.cap !== 'function') {
        push('err', '能力 · ' + spec.label, '壳桥没有 w3:cap 这个口（旧壳或裸浏览器）—— 这一下没发出去。');
        return;
      }
      /* 她的动作跟着走：出手先歪头「在想」，成了点头，被拒/失败摇头 */
      if (window.GBT_MOTION) window.GBT_MOTION.play('tilt', 0.8);
      push('tool', '她动手 · ' + spec.label, '调用中…（kind=' + spec.kind + '）');
      var row = list.lastChild;
      var body = row.querySelector('.msg__body');
      Promise.resolve(b.cap({ kind: spec.kind, payload: {} })).then(function (r) {
        if (r && r.ok) {
          body.textContent = flatten(r.result || r).slice(0, 6000);
          if (window.GBT_MOTION) window.GBT_MOTION.play('nod', 1);
          setSub('她刚跑完 ' + spec.kind + '（真回执见气泡）');
        } else {
          row.className = 'msg msg--her msg--err';
          var why = (r && (r.error || r.reason || r.status)) || '未读到原因';
          body.textContent = '没做成：' + String(why) +
            (r && r.refused ? ('\n允许的：' + (r.allowlist || []).join(', ')) : '') +
            '\n（回执照抄，不编）';
          if (window.GBT_MOTION) window.GBT_MOTION.play('shake', 1);
          setSub('她这一下被拒/失败 · 原因见气泡');
        }
        list.scrollTop = list.scrollHeight;
      }).catch(function (e) {
        row.className = 'msg msg--her msg--err';
        body.textContent = '调用异常：' + String((e && e.message) || e);
        if (window.GBT_MOTION) window.GBT_MOTION.play('shake', 1);
      });
    });
  }
})();
