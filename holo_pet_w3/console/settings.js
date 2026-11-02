/* 设置面板（2026-11-02）：模型 / 外观 / 行为 / 数据 / 高级
 * 读写 /api/settings，落 state/app-settings.json；模型配置直接决定 /api/chat 走谁。
 */
(function () {
  if (window.__gbtSettings) return;
  window.__gbtSettings = true;
  var $ = function (id) { return document.getElementById(id); };
  var S = null, curTab = "model";

  function open() {
    var m = $("set-modal");
    if (!m) return;
    m.hidden = false;
    m.setAttribute("aria-hidden", "false");
    load();
  }
  function close() {
    var m = $("set-modal");
    if (m) { m.hidden = true; m.setAttribute("aria-hidden", "true"); }
  }

  function load() {
    fetch("/api/settings").then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) return;
      S = d.settings;
      fill(S);
    }).catch(function () {});
  }

  function fill(s) {
    $("set-provider").value = s.model.provider || "openai-compatible";
    $("set-base-url").value = s.model.base_url || "";
    $("set-api-key").value = s.model.api_key || "";
    $("set-model-name").value = s.model.name || "";
    $("set-temp").value = s.model.temperature != null ? s.model.temperature : 0;
    $("set-max").value = s.model.max_tokens || 1024;
    $("set-timeout").value = s.model.timeout || 300;
    $("set-sys").value = s.model.system_prompt || "";
    $("set-theme").value = s.appearance.theme || "dark";
    $("set-font").value = String(s.appearance.font_scale || 1);
    $("set-density").value = s.appearance.density || "comfortable";
    $("set-motion").checked = !!s.appearance.reduced_motion;
    $("set-lang").value = s.behavior.language || "zh-CN";
    $("set-enter").checked = !!s.behavior.send_with_enter;
    $("set-notify").checked = !!s.behavior.notifications;
    $("set-sound").checked = !!s.behavior.sound;
    $("set-autostart").checked = !!s.behavior.auto_start;
    $("set-datadir").value = s.data.data_dir || "state";
    $("set-memory").checked = !!s.data.memory_chain;
    $("set-backup").checked = !!s.data.auto_backup;
    $("set-backupdir").value = s.data.backup_dir || "";
    $("set-proxy").value = s.advanced.proxy || "";
    $("set-retries").value = s.advanced.retries != null ? s.advanced.retries : 2;
    $("set-ctx").value = s.advanced.context_mode || "ring";
    $("set-window").value = s.advanced.window_chars || 8000;
  }

  function collect() {
    return {
      model: {
        provider: $("set-provider").value,
        base_url: $("set-base-url").value.trim(),
        api_key: $("set-api-key").value,
        name: $("set-model-name").value.trim(),
        temperature: Number($("set-temp").value || 0),
        max_tokens: Number($("set-max").value || 1024),
        timeout: Number($("set-timeout").value || 300),
        system_prompt: $("set-sys").value
      },
      appearance: {
        theme: $("set-theme").value,
        font_scale: Number($("set-font").value || 1),
        density: $("set-density").value,
        reduced_motion: $("set-motion").checked
      },
      behavior: {
        language: $("set-lang").value,
        send_with_enter: $("set-enter").checked,
        notifications: $("set-notify").checked,
        sound: $("set-sound").checked,
        auto_start: $("set-autostart").checked
      },
      data: {
        data_dir: $("set-datadir").value || "state",
        memory_chain: $("set-memory").checked,
        auto_backup: $("set-backup").checked,
        backup_dir: $("set-backupdir").value.trim()
      },
      advanced: {
        proxy: $("set-proxy").value.trim(),
        retries: Number($("set-retries").value || 0),
        context_mode: $("set-ctx").value,
        window_chars: Number($("set-window").value || 8000)
      }
    };
  }

  function apply(s) {
    document.body.classList.toggle("reduce-motion", !!s.appearance.reduced_motion);
    document.body.classList.toggle("density-compact", s.appearance.density === "compact");
    try { document.body.style.zoom = String(s.appearance.font_scale || 1); } catch (e) {}
    if (window.__gbtApplySettings) window.__gbtApplySettings(s);
  }

  function save() {
    var s = collect();
    fetch("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(s) }).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) throw new Error(d.error || "保存失败");
      S = d.settings;
      apply(S);
      $("sm-saved").textContent = "已保存 · " + new Date().toLocaleTimeString();
      setTimeout(function () { $("sm-saved").textContent = ""; }, 4000);
    }).catch(function (e) {
      $("sm-saved").textContent = "保存失败：" + String(e).slice(0, 80);
    });
  }

  function test() {
    var s = collect();
    $("set-test-state").className = "sm-state";
    $("set-test-state").textContent = "测试中…";
    fetch("/api/model-test", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(s.model) }).then(function (r) { return r.json(); }).then(function (d) {
      if (d.ok) {
        $("set-test-state").className = "sm-state ok";
        $("set-test-state").textContent = "连上了 · " + (d.ms || "?") + "ms · " +
          String(d.text || "").slice(0, 40);
      } else {
        $("set-test-state").className = "sm-state err";
        $("set-test-state").textContent = String(d.error || "连接失败").slice(0, 140);
      }
    }).catch(function (e) {
      $("set-test-state").className = "sm-state err";
      $("set-test-state").textContent = "请求失败：" + String(e).slice(0, 120);
    });
  }

  function exportJson(obj, name) {
    var blob = new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  }

  function wire() {
    var tabs = $("sm-tabs");
    if (!tabs) return;
    tabs.addEventListener("click", function (e) {
      var b = e.target.closest("button");
      if (!b) return;
      curTab = b.getAttribute("data-tab");
      tabs.querySelectorAll("button").forEach(function (x) {
        x.classList.toggle("on", x === b);
      });
      document.querySelectorAll("#sm-panes > section").forEach(function (p) {
        p.hidden = p.getAttribute("data-pane") !== curTab;
      });
    });
    $("sm-close").addEventListener("click", close);
    $("set-modal").addEventListener("click", function (e) {
      if (e.target === $("set-modal")) close();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !$("set-modal").hidden) close();
    });
    $("sm-save").addEventListener("click", save);
    $("set-test").addEventListener("click", test);
    $("set-export").addEventListener("click", function () {
      if (S) exportJson(S, "gbt-settings.json");
    });
    $("set-import").addEventListener("click", function () { $("set-import-file").click(); });
    $("set-import-file").addEventListener("change", function () {
      var f = this.files && this.files[0];
      if (!f) return;
      var fr = new FileReader();
      fr.onload = function () {
        try {
          var data = JSON.parse(fr.result);
          fetch("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data) }).then(function (r) { return r.json(); }).then(function (d) {
            if (d.ok) { S = d.settings; fill(S); apply(S); $("sm-saved").textContent = "已导入"; }
          });
        } catch (e) { $("sm-saved").textContent = "导入失败：JSON 无效"; }
      };
      fr.readAsText(f);
      this.value = "";
    });
    $("set-export-mem").addEventListener("click", function () {
      fetch("/api/memory?op=stats").then(function (r) { return r.json(); }).then(function (d) {
        exportJson(d, "gbt-memory-index.json");
      }).catch(function () {});
    });
    // Enter 发送开关：关掉时 Enter 换行
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Enter" || e.shiftKey || e.isComposing) return;
      if (!S || !S.behavior || S.behavior.send_with_enter !== false) return;
      if (!e.target || e.target.id !== "chat-input") return;
      e.preventDefault();
      var t = e.target, p = t.selectionStart || t.value.length;
      t.value = t.value.slice(0, p) + "\n" + t.value.slice(t.selectionEnd || p);
      t.selectionStart = t.selectionEnd = p + 1;
    }, true);
  }

  document.addEventListener("DOMContentLoaded", function () {
    wire();
    fetch("/api/settings").then(function (r) { return r.json(); }).then(function (d) {
      if (d.ok) { S = d.settings; apply(S); }
    }).catch(function () {});
  });
  window.__openSettings = open;
  window.__gbtSettingsRef = function () { return S; };
})();
