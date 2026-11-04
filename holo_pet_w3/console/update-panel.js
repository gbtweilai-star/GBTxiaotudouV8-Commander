/* ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
 * 更新校验：只读验签；绝不下载/安装。 */
(function () {
  "use strict";
  var result = document.getElementById("up-result");
  if (!result) return;
  function check() {
    var raw = (document.getElementById("up-manifest") || {}).value || "";
    var key = (document.getElementById("up-key") || {}).value || "";
    var manifest;
    try { manifest = JSON.parse(raw || "{}"); } catch (e) { result.textContent = "JSON 解析失败"; return; }
    fetch("/api/update", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ op: "verify", manifest: manifest, public_key: key, current_version: "8.0.0" }) })
      .then(function (r) { return r.json(); }).then(function (j) {
        if (!j || j.ok === false) { result.textContent = "失败：" + ((j && j.error) || "未知"); return; }
        var st = document.getElementById("up-state");
        if (st) st.textContent = j.verified ? "已验签" : "未通过";
        result.textContent = "signed=" + j.signed + " · signature_ok=" + j.signature_ok +
          " · newer=" + j.newer + " · install_supported=" + j.install_supported +
          (j.reason ? " · " + j.reason : "");
      }).catch(function () { result.textContent = "校验请求失败"; });
  }
  var b = document.getElementById("up-check");
  if (b) b.addEventListener("click", check);

  /* ── 本地更新测试链（只 state/updates-test；不碰正式 APP）── */
  var chain = { stage_id: "", token: "" };
  function chainOut(text) {
    var el = document.getElementById("up-chain-result");
    if (el) el.textContent = text;
  }
  function chainPost(op, extra) {
    return fetch("/api/update-chain", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({ op: op }, extra || {})) }).then(function (r) { return r.json(); });
  }
  function chainRefresh() {
    fetch("/api/update-chain", { cache: "no-store" }).then(function (r) { return r.json(); })
      .then(function (j) {
        var el = document.getElementById("up-chain-result");
        if (!el) return;
        el.textContent = j.init ? ("target=" + (j.target_version || "?") + " · stages=" + j.stages + " · backups=" + j.backups) : "未初始化";
      }).catch(function () {});
  }
  function chainInit() {
    chainPost("init").then(function (j) { chainOut(j.ok ? "init ok · 无密钥 hash-only" : ("init 失败：" + (j.error || "未知"))); chainRefresh(); });
  }
  function chainStage() {
    chainPost("stage").then(function (j) {
      if (j.ok) {
        chain.stage_id = j.stage_id; chain.token = j.confirm_token;
        chainOut("staged " + j.version + " · " + j.files + " files · token 只显示一次");
        var b = document.getElementById("up-chain-confirm"); if (b) b.disabled = false;
      } else chainOut("stage 失败：" + (j.error || "未知"));
    });
  }
  function chainConfirm() {
    chainPost("confirm", { stage_id: chain.stage_id, token: chain.token }).then(function (j) {
      chainOut(j.ok ? ("applied · " + (j.version || "") + " · backup=" + (j.backup || "")) : ("confirm 失败：" + (j.error || "未知")));
      chainRefresh();
    });
  }
  function chainRollback() {
    chainPost("rollback").then(function (j) {
      chainOut(j.ok ? ("rolled back · version=" + (j.version || "")) : ("rollback 失败：" + (j.error || "未知")));
      chainRefresh();
    });
  }
  var ci = document.getElementById("up-chain-init"), cs = document.getElementById("up-chain-stage"),
      cc = document.getElementById("up-chain-confirm"), cr = document.getElementById("up-chain-rollback");
  if (ci) ci.addEventListener("click", chainInit);
  if (cs) cs.addEventListener("click", chainStage);
  if (cc) cc.addEventListener("click", chainConfirm);
  if (cr) cr.addEventListener("click", chainRollback);
  chainRefresh();

})();
