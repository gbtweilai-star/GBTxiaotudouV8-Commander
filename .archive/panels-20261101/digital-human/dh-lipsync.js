/* ══════════════════════════════════════════════════════════════════════════════
   dh-lipsync.js —— 音素（viseme）判定 · 吸收件
   ─────────────────────────────────────────────────────────────────────────────
   来源：wawa-lipsync（MIT）· https://github.com/wass08/wawa-lipsync
         packages/wawa-lipsync/src/lipsync.ts（423 行）+ visemes.ts
         原文件已按原样放在 digital-human/vendor/wawa-lipsync/ 下（含 LICENSE，不得删除）。
   许可：MIT —— 保留版权与许可声明（见 vendor/wawa-lipsync/LICENSE）。
   本节是**忠实移植**（不是重写）：频带划分 / 谱质心 / 音量 / 带能量差 / 15 个 viseme 的
   打分规则 / "当前 viseme 的持续时长加成与惩罚" 全部照原实现搬过来；
   只改了两处接口，因为我们的页面已经有一条既有的 WebAudio 分析链：
     ① 不自建 AudioContext，改成 attachAnalyser(analyser, sampleRate) 复用现成的那条；
     ② 输出 sRGB 无关的纯数据（viseme 字符串 + 特征），由调用方决定怎么驱动骨头。
   为什么值得吸收：原来我们的口型是"RMS → 下颌角度"，任何音都张一样大 —— 这是"假对齐"；
   这套分类能分出元音/爆破音/摩擦音，嘴型才跟着字走。
   ══════════════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";
  var VISEMES = {
    sil: "viseme_sil", PP: "viseme_PP", FF: "viseme_FF", TH: "viseme_TH",
    DD: "viseme_DD", kk: "viseme_kk", CH: "viseme_CH", SS: "viseme_SS",
    nn: "viseme_nn", RR: "viseme_RR", aa: "viseme_aa", E: "viseme_E",
    I: "viseme_I", O: "viseme_O", U: "viseme_U"
  };
  var ST = {
    silence: "silence", vowel: "vowel", plosive: "plosive", fricative: "fricative"
  };
  var VISEMES_STATES = {};
  VISEMES_STATES[VISEMES.sil] = ST.silence;
  VISEMES_STATES[VISEMES.PP] = ST.plosive;
  VISEMES_STATES[VISEMES.FF] = ST.fricative;
  VISEMES_STATES[VISEMES.TH] = ST.fricative;
  VISEMES_STATES[VISEMES.DD] = ST.plosive;
  VISEMES_STATES[VISEMES.kk] = ST.plosive;
  VISEMES_STATES[VISEMES.CH] = ST.fricative;
  VISEMES_STATES[VISEMES.SS] = ST.fricative;
  VISEMES_STATES[VISEMES.nn] = ST.plosive;
  VISEMES_STATES[VISEMES.RR] = ST.fricative;
  VISEMES_STATES[VISEMES.aa] = ST.vowel;
  VISEMES_STATES[VISEMES.E] = ST.vowel;
  VISEMES_STATES[VISEMES.I] = ST.vowel;
  VISEMES_STATES[VISEMES.O] = ST.vowel;
  VISEMES_STATES[VISEMES.U] = ST.vowel;

  function average(a) {
    if (!a.length) return 0;
    var s = 0;
    for (var i = 0; i < a.length; i++) s += a[i];
    return s / a.length;
  }

  function create(opts) {
    opts = opts || {};
    var historySize = opts.historySize || 10;
    var maxVisemeDuration = 100;
    var analyser = null, dataArray = null, sampleRate = 44100, binWidth = 1;
    var history = [], state = ST.silence, viseme = VISEMES.sil;
    var visemeStartTime = 0, features = null;
    /* 与原实现一致的 7 个频带（Hz） */
    var bands = [
      { start: 50, end: 200 }, { start: 200, end: 400 }, { start: 400, end: 800 },
      { start: 800, end: 1500 }, { start: 1500, end: 2500 },
      { start: 2500, end: 4000 }, { start: 4000, end: 8000 }
    ];

    function attachAnalyser(a, sr) {
      analyser = a;
      dataArray = new Uint8Array(a.frequencyBinCount);
      sampleRate = sr || 44100;
      binWidth = sampleRate / (a.fftSize || 2048);
      history = []; features = null; state = ST.silence;
      visemeStartTime = performance.now();
      return true;
    }

    function extractFeatures() {
      analyser.getByteFrequencyData(dataArray);
      var bandEnergies = bands.map(function (b) {
        var s0 = Math.round(b.start / binWidth);
        var e0 = Math.min(Math.round(b.end / binWidth), dataArray.length - 1);
        return average(Array.prototype.slice.call(dataArray, s0, e0)) / 255;
      });
      var sumAmp = 0, weighted = 0;
      for (var i = 0; i < dataArray.length; i++) {
        var freq = i * binWidth, amp = dataArray[i] / 255;
        sumAmp += amp; weighted += freq * amp;
      }
      var centroid = sumAmp > 0 ? weighted / sumAmp : 0;
      var volume = average(bandEnergies);
      var deltaBands = bandEnergies.map(function (e, idx) {
        if (history.length < 2) return 0;
        return e - history[history.length - 2].bands[idx];
      });
      var f = { bands: bandEnergies, deltaBands: deltaBands, volume: volume, centroid: centroid };
      if (sumAmp > 0) {
        history.push(f);
        if (history.length > historySize) history.shift();
      }
      return f;
    }

    function getAveragedFeatures() {
      var len = history.length || 1, sv = 0, sc = 0, sb = [0, 0, 0, 0, 0, 0, 0];
      for (var i = 0; i < history.length; i++) {
        var f = history[i];
        sv += f.volume; sc += f.centroid;
        for (var j = 0; j < f.bands.length; j++) sb[j] += f.bands[j];
      }
      var b = sb.map(function (x) { return x / len; });
      return { volume: sv / len, centroid: sc / len, bands: b, deltaBands: b };
    }

    function computeScores(cur, avg, dVolume, dCentroid) {
      var s = {};
      Object.keys(VISEMES).forEach(function (k) { s[VISEMES[k]] = 0; });
      var b7 = cur.bands[6];
      if (avg.volume < 0.2 && cur.volume < 0.2) s[VISEMES.sil] = 1.0;
      Object.keys(VISEMES_STATES).forEach(function (v) {
        if (VISEMES_STATES[v] === ST.plosive) {
          if (dVolume < 0.01) s[v] -= 0.5;
          if (avg.volume < 0.2) s[v] += 0.2;
          if (dCentroid > 1000) s[v] += 0.2;
        }
      });
      if (cur.centroid > 1000 && cur.centroid < 8000) {
        if (cur.centroid > 7000) s[VISEMES.DD] += 0.6;
        else if (cur.centroid > 5000) s[VISEMES.kk] += 0.6;
        else if (cur.centroid > 4000) {
          s[VISEMES.PP] += 1;
          if (b7 > 0.25 && cur.centroid < 6000) s[VISEMES.DD] += 1.4;
        } else s[VISEMES.nn] += 0.6;
      }
      if (dCentroid > 1000 && cur.centroid > 6000 && avg.centroid > 5000) {
        if (cur.bands[6] > 0.4 && avg.bands[6] > 0.3) s[VISEMES.FF] = 0.7;
      }
      if (avg.volume > 0.1 && avg.centroid < 6000 && cur.centroid < 6000) {
        var b1 = avg.bands[0], b2 = avg.bands[1], b3 = avg.bands[2],
            b4 = avg.bands[3], b5 = avg.bands[4];
        var gapB1B2 = Math.abs(b1 - b2);
        var maxGap = Math.max(Math.abs(b2 - b3), Math.abs(b2 - b4), Math.abs(b3 - b4));
        if (b3 > 0.1 || b4 > 0.1) {
          if (b4 > b3) { s[VISEMES.aa] = 0.8; if (b3 > b2) s[VISEMES.aa] += 0.2; }
          if (b3 > b2 && b3 > b4) s[VISEMES.I] = 0.7;
          if (gapB1B2 < 0.25) s[VISEMES.U] = 0.7;
          if (maxGap < 0.25) s[VISEMES.O] = 0.9;
          if (b2 > b3 && b3 > b4) s[VISEMES.E] = 1;
          if (b3 < 0.2 && b4 > 0.3) s[VISEMES.I] = 0.7;
          if (b3 > 0.25 && b5 > 0.25) s[VISEMES.O] = 0.7;
          if (b3 < 0.15 && b5 < 0.15) s[VISEMES.U] = 0.7;
        }
      }
      return s;
    }

    function adjust(scores) {
      var adj = {};
      for (var k in scores) adj[k] = scores[k];
      var dur = performance.now() - visemeStartTime;
      for (var v in adj) {
        if (v !== viseme) continue;
        var boost;
        if (dur <= 100) boost = 1.3;
        else if (dur <= maxVisemeDuration) {
          var decay = (dur - 100) / (maxVisemeDuration - 100);
          boost = 1.3 - 0.3 * decay;
        } else boost = Math.max(0.5, 1.0 - (dur - maxVisemeDuration) / 1000);
        adj[v] *= boost;
      }
      return adj;
    }

    function detectState() {
      var cur = history[history.length - 1];
      if (!cur) { state = ST.silence; viseme = VISEMES.sil; return; }
      var avg = getAveragedFeatures();
      var scores = computeScores(cur, avg, cur.volume - avg.volume, cur.centroid - avg.centroid);
      var adj = adjust(scores);
      var best = -Infinity, top = VISEMES.sil;
      for (var v in adj) if (adj[v] > best) { best = adj[v]; top = v; }
      if (top !== viseme) visemeStartTime = performance.now();
      state = VISEMES_STATES[top];
      viseme = top;
    }

    function process() {
      if (!analyser) return null;
      features = extractFeatures();
      detectState();
      return features;
    }

    return {
      attachAnalyser: attachAnalyser,
      process: process,
      VISEMES: VISEMES,
      info: function () {
        return {
          viseme: viseme, state: state,
          history: history.length,
          volume: features ? +features.volume.toFixed(3) : null,
          centroid: features ? Math.round(features.centroid) : null,
          bands: features ? features.bands.map(function (x) { return +x.toFixed(3); }) : null
        };
      }
    };
  }

  window.GBT_LIPSYNC = { create: create, VISEMES: VISEMES };
})();
