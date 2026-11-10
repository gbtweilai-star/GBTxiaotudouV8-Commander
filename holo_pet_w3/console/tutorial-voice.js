(function () {
  "use strict";
  var LS = "gbt_tutorial_done_v1";
  var STEPS = [
    "你好，我是她。这一页是三栏认知主控：左边是能力与面板，中间是舞台，右边是账与流。",
    "想跟我说什么，点下方语音面板的开始按钮，麦克风就交给我了；说「小土豆」我会应。",
    "想在任何页面呼唤我，按 Ctrl 加 K，说：小土豆，自检、看屏、或者念一句话。",
    "想把我的头像摆到顺手的位置，直接拖；双击我，我休着但不会消失。",
    "危险操作我永远不会替你按同意，转账和资金必须你在终端亲自点头。",
    "随时说：小土豆，教程，我把这几句再念一遍。"
  ];
  var queue = [], speaking = false;
  function runNext() {
    if (speaking || !queue.length) return;
    speaking = true;
    var t = queue.shift();
    function done() { speaking = false; setTimeout(runNext, 500); }
    var say = window.__gbtAvatarSay;
    if (say) { Promise.resolve(say(t)).then(done, done); } else { done(); }
  }
  function play(steps) {
    queue = (steps || STEPS).slice(0, 12);
    runNext();
  }
  window.__gbtTutorial = play;

  function boot() {
    var done = false;
    try { done = localStorage.getItem(LS) === "1"; } catch (e) { }
    if (!done) {
      try { localStorage.setItem(LS, "1"); } catch (e2) { }
      setTimeout(function () { play([STEPS[0], STEPS[1], STEPS[5]]); }, 1200);
    }
    window.addEventListener("gbt-voice-final", function (ev) {
      var q = String((ev && ev.detail && ev.detail.query) || "");
      if (/教程|教我|怎么用/.test(q)) play();
    });
  }
  function safeBoot() { try { boot(); } catch (e) { } }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", safeBoot);
  else safeBoot();
})();