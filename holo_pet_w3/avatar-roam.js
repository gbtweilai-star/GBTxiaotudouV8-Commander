(function () {
  "use strict";
  if (window.__GBT_AVATAR_ROAM__) return;
  window.__GBT_AVATAR_ROAM__ = true;

  var me = document.currentScript;
  var ROOT = me ? me.src.replace(/[^\/\\]+$/, "") : "./";
  var LS = "gbt_avatar_roam_v1";

  var state = { visible: true, minimized: false, scale: 1, x: null, y: null };
  try {
    var saved = JSON.parse(localStorage.getItem(LS) || "null");
    if (saved && typeof saved === "object") state = Object.assign(state, saved);
  } catch (e) { }

  var orb = null, badge = null, threeFail = "", glb = null;

  function saveState() {
    try { localStorage.setItem(LS, JSON.stringify(state)); } catch (e) { }
  }
  function ensureDom() {
    if (orb || !document.body) return false;
    orb = document.createElement("div");
    orb.id = "gbt-avatar-roam";
    orb.style.cssText =
      "position:fixed;z-index:2147483000;width:96px;height:120px;cursor:grab;" +
      "user-select:none;touch-action:none;left:32px;bottom:32px";
    badge = document.createElement("div");
    badge.textContent = "她";
    badge.style.cssText =
      "position:absolute;left:50%;top:6px;transform:translateX(-50%);" +
      "font:10px/1.6 ui-monospace,Consolas,monospace;color:#9fb7d4;" +
      "background:rgba(10,13,18,.6);border-radius:8px;padding:0 8px";
    var fx = document.createElement("div");
    fx.id = "gbt-avatar-roam-fx";
    fx.style.cssText = "position:absolute;inset:0;";
    orb.appendChild(fx);
    orb.appendChild(badge);
    document.body.appendChild(orb);
    positioning(); applyVisibility(); drag(orb);
    orb.addEventListener("dblclick", function () {
      state.minimized = !state.minimized; saveState(); applyVisibility();
    });
    return true;
  }
  function positioning() {
    if (state.x != null) { orb.style.left = state.x + "px"; orb.style.top = state.y + "px"; orb.style.bottom = "auto"; }
    else { orb.style.left = "32px"; orb.style.top = "auto"; orb.style.bottom = "32px"; }
    orb.style.transform = state.minimized ? "scale(.6)" : "scale(" + state.scale + ")";
  }
  function applyVisibility() {
    if (!orb) return;
    orb.style.display = state.visible ? "block" : "none";
    badge.textContent = state.minimized ? "休" : "她";
    positioning();
  }
  function drag(el) {
    var sx = 0, sy = 0, ox = 0, oy = 0, on = false;
    el.addEventListener("pointerdown", function (e) {
      on = true; try { el.setPointerCapture(e.pointerId); } catch (e2) { }
      sx = e.clientX; sy = e.clientY;
      var r = el.getBoundingClientRect(); ox = r.left; oy = r.top;
      el.style.cursor = "grabbing";
    });
    el.addEventListener("pointermove", function (e) {
      if (!on) return;
      state.x = Math.max(0, Math.min(window.innerWidth - 96, ox + (e.clientX - sx)));
      state.y = Math.max(0, Math.min(window.innerHeight - 120, oy + (e.clientY - sy)));
      positioning(); saveState();
    });
    el.addEventListener("pointerup", function () { on = false; el.style.cursor = "grab"; });
  }
  function loadScript(src) {
    return new Promise(function (res, rej) {
      var s = document.createElement("script");
      s.src = src; s.onload = res;
      s.onerror = function () { rej(new Error("加载失败 " + src)); };
      document.head.appendChild(s);
    });
  }
  function mount3D() {
    var host = document.getElementById("gbt-avatar-roam-fx");
    if (!host) return Promise.resolve(false);
    return loadScript(ROOT + "assets/vendor/three.global.js")
      .then(function () { return loadScript(ROOT + "assets/vendor/GLTFLoader.global.js"); })
      .then(function () {
        var T = window.THREE;
        if (!T || !T.GLTFLoader) throw new Error("vendor three 不在");
        var w = 96, h = 120;
        var renderer = new T.WebGLRenderer({ alpha: true, antialias: true });
        renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
        renderer.setSize(w, h);
        renderer.domElement.style.cssText = "width:100%;height:100%";
        host.appendChild(renderer.domElement);
        var scene = new T.Scene();
        var cam = new T.PerspectiveCamera(35, w / h, .01, 20);
        cam.position.set(0, .35, 3.2);
        scene.add(new T.AmbientLight(0xffffff, .9));
        var key = new T.DirectionalLight(0x9ecbff, 1.4);
        key.position.set(2, 3, 4); scene.add(key);
        var url = ROOT + "assets/dh/dh-v7-detail.glb";
        return new Promise(function (res, rej) {
          new T.GLTFLoader().load(url, res, undefined,
            function (e) { rej(new Error("GLB 加载失败：" + ((e && e.message) || e))); });
        }).then(function (g) {
          glb = g; scene.add(g.scene);
          var box = new T.Box3().setFromObject(g.scene);
          var c = box.getCenter(new T.Vector3());
          var sz = box.getSize(new T.Vector3());
          var k = 2.0 / Math.max(.001, sz.y);
          g.scene.scale.setScalar(k);
          g.scene.position.set(-c.x * k, -box.min.y * k - .85, -c.z * k);
          var t0 = performance.now();
          (function tick() {
            requestAnimationFrame(tick);
            var t = (performance.now() - t0) / 1000;
            g.scene.rotation.y = Math.sin(t * .6) * .35;
            g.scene.position.y = -0.85 + Math.sin(t * 1.1) * .03;
            renderer.render(scene, cam);
          })();
          badge.title = "她 · DH-V7 常驻（双击休/醒，拖动调位置）";
          return true;
        });
      })
      .catch(function (e) {
        threeFail = String(e && e.message || e); mountFallback(); return false;
      });
  }
  function mountFallback() {
    var host = document.getElementById("gbt-avatar-roam-fx");
    if (!host) return;
    var s = document.createElement("div");
    s.style.cssText =
      "position:absolute;inset:0;border-radius:50% 50% 46% 46%;" +
      "background:radial-gradient(circle at 35% 30%,#8fd0ff,#0b1120 75%);" +
      "box-shadow:0 0 24px rgba(120,190,255,.55);opacity:.9";
    host.appendChild(s);
    badge.title = "3D 没起：" + threeFail + " · 兜底为平面拟球，如实告知";
  }
  function say(text) {
    var t = String(text || "").trim();
    if (!t) return Promise.resolve({ ok: false, reason: "empty" });
    if (window.gbtW3 && window.gbtW3.cap) {
      return window.gbtW3.cap("voice", { op: "tts", text: t });
    }
    badge.textContent = "哑";
    badge.title = "无桥：本页没接能力位桥，不出声。接上 tentacle-bridge.js 再来";
    return Promise.resolve({ ok: false, reason: "no_bridge" });
  }
  window.__gbtAvatarSay = say;
  window.__gbtAvatarState = function () {
    return Object.assign({}, state, { three: threeFail || "ok", glb: !!glb });
  };
  window.__gbtAvatarToggle = function () {
    state.visible = !state.visible; saveState(); applyVisibility();
  };

  function boot() {
    if (!ensureDom()) { document.addEventListener("DOMContentLoaded", boot); return; }
    mount3D();
    if (window.__gbtTutorialReady) window.__gbtTutorialReady();
  }
  boot();
})();