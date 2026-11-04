/* 皮肤：Claude 风 · 暖纸感（2026-11-02）
 * 不画任何背景特效；只负责"亮起来"的进入动效与切视图轻过渡。
 * 保持对话框零覆盖：不注入任何覆盖层。
 */
(function () {
  if (window.__claudeSkin) return;
  window.__claudeSkin = true;
  function zap() {
    document.body.classList.remove("skin-powering");
    void document.body.offsetWidth;
    document.body.classList.add("skin-powering");
    window.clearTimeout(zap._t);
    zap._t = window.setTimeout(function () {
      document.body.classList.remove("skin-powering");
    }, 700);
  }
  window.addEventListener("load", function () { window.setTimeout(zap, 60); });
  document.addEventListener("click", function (e) {
    var t = e.target.closest && e.target.closest(".view-tab, .panel-actions .reset-view");
    if (t) zap();
  }, true);
  var chat = document.getElementById("chat-area");
  if (chat && window.MutationObserver) {
    new MutationObserver(function (muts) {
      for (var i = 0; i < muts.length; i++) {
        if (muts[i].attributeName === "data-view") { zap(); return; }
      }
    }).observe(chat, { attributes: true, attributeFilter: ["data-view"] });
  }
  window.__skinCube = { zap: zap };
})();
