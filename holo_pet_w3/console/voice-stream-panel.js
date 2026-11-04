/* ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
 * 流式语音：浏览器 PCM16 16k 分片 → /api/voice/stream；局部/最终 Whisper；真 KWS 未做。 */
(function () {
  "use strict";
  var stateEl = document.getElementById("vs-state"), textEl = document.getElementById("vs-text");
  var timeEl = document.getElementById("vs-time"), startBtn = document.getElementById("vs-start");
  var stopBtn = document.getElementById("vs-stop");
  if (!startBtn) return;
  var ctx = null, stream = null, source = null, node = null, timer = null;
  var session = null, startedAt = 0, lastChunk = 0, lastPartial = 0;
  function pad16(f32) {
    var ratio = ctx.sampleRate / 16000, outLen = Math.floor(f32.length / ratio);
    var out = new Int16Array(outLen);
    for (var i = 0; i < outLen; i++) {
      var start = Math.floor(i * ratio), sum = 0, n = 0;
      for (var j = start; j < Math.min(f32.length, start + Math.ceil(ratio)); j++) { sum += f32[j]; n++; }
      var v = n ? sum / n : 0;
      out[i] = Math.max(-1, Math.min(1, v)) * 32767;
    }
    return out;
  }
  function b64(i16) {
    var bytes = new Uint8Array(i16.buffer), s = "";
    for (var i = 0; i < bytes.length; i += 4096) {
      s += String.fromCharCode.apply(null, bytes.subarray(i, i + 4096));
    }
    return btoa(s);
  }
  function send(op, payload) {
    return fetch("/api/voice/stream", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({ op: op, session: session }, payload || {})) })
      .then(function (r) { return r.json(); });
  }
  function stopStream() {
    if (timer) { clearInterval(timer); timer = null; }
    try { if (node) node.disconnect(); } catch (e) {}
    try { if (source) source.disconnect(); } catch (e) {}
    try { if (stream) stream.getTracks().forEach(function (t) { t.stop(); }); } catch (e) {}
    try { if (ctx) ctx.close(); } catch (e) {}
    stream = source = node = ctx = null;
    if (startBtn) startBtn.disabled = false;
    if (stateEl) stateEl.textContent = "已停止";
  }
  function begin() {
    if (ctx) return;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      if (textEl) textEl.textContent = "这个环境没有 getUserMedia"; return;
    }
    fetch("/api/voice/stream", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ op: "start" }) }).then(function (r) { return r.json(); }).then(function (j) {
      if (!j || !j.ok) { if (textEl) textEl.textContent = "start 失败：" + ((j && j.error) || "未知"); return; }
      session = j.session; startedAt = Date.now(); lastChunk = 0; lastPartial = 0;
      return navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
    }).then(function (s) {
      if (!s) return;
      stream = s;
      ctx = new (window.AudioContext || window.webkitAudioContext)();
      source = ctx.createMediaStreamSource(s);
      node = ctx.createScriptProcessor(4096, 1, 1);
      node.onaudioprocess = function (ev) {
        var now = Date.now();
        if (now - lastChunk < 700) return;
        lastChunk = now;
        var pcm = pad16(ev.inputBuffer.getChannelData(0));
        var partial = now - lastPartial > 3000;
        if (partial) lastPartial = now;
        send("chunk", { pcm_base64: b64(pcm), partial: partial }).then(function (r) {
          if (r && r.ok) {
            var dur = Number(r.duration || 0);
            if (timeEl) timeEl.textContent = dur.toFixed(1) + "s";
            if (r.partial && textEl) textEl.textContent = ((r.acoustic_wake && r.acoustic_wake.wake) || (r.wake && r.wake.wake) ? "声学唤醒 · " : "局部：") + r.partial;
          }
        }).catch(function () {});
      };
      source.connect(node); node.connect(ctx.destination);
      if (stateEl) stateEl.textContent = "采集中";
      if (startBtn) startBtn.disabled = true;
      timer = setInterval(function () {
        if (timeEl) timeEl.textContent = ((Date.now() - startedAt) / 1000).toFixed(1) + "s";
      }, 200);
    }).catch(function (e) {
      if (textEl) textEl.textContent = "麦克风/启动失败：" + (e && e.message ? e.message : e);
      stopStream();
    });
  }
  function finish() {
    if (!session) { stopStream(); return; }
    send("end").then(function (r) {
      if (textEl) textEl.textContent = (r && r.ok) ? ((((r.acoustic_wake && r.acoustic_wake.wake) || (r.wake && r.wake.wake)) ? "声学唤醒 · " : "") + "最终：" + (r.text || "（静音/未识别）")) : ("结束失败：" + ((r && r.error) || "未知"));
      stopStream();
    }).catch(function () { stopStream(); });
  }
  startBtn.addEventListener("click", begin);
  if (stopBtn) stopBtn.addEventListener("click", finish);
  window.__voiceStreamStop = finish;
})();
