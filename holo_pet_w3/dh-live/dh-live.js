/* 数字人 · 整页舞台（2026-11-02 重做）
 * 目标：一整页只有数字人；无按钮；语音指挥全身动作；动作走骨骼过渡，自然不硬切。
 * 资产：/voice-theater/assets/dh-v2-rigged.glb（Mixamo 65 骨骼 · idle/walk 两段）。
 * 说明：该资产没有口型骨/morph，说话用头颈节律 + 手臂手势表达，不假装有口型。
 */
(function () {
  "use strict";
  var stage = document.getElementById("stage");
  var stateEl = document.getElementById("state");
  var capEl = document.getElementById("caption");
  var hintEl = document.getElementById("hint");


  var renderer, scene, camera, mixer, modelRoot, clock;
  var B = {};              // 骨骼名 -> Bone
  var RESTQ = {};          // 初始四元数
  var CLEAN = {};          // 每帧 mixer 输出快照（不含叠加），下一帧先回到这里
  var ANIM = {};           // 动画驱动到的骨名集合
  var G = null;            // 本地兜底手势
  var SRV = { active: false, action: "", dur: 2.0, phase: 0, targets: [],
    applied: [], lastSent: 0, pending: false, ok: false,
    startedAt: 0, lastResp: 0 };
  var idleT = 0;
  var talking = false;
  var speakingSince = 0;
  var lastCaption = "";
  var BASE = new THREE.Vector3(0, 0, 0);

  function boneKey(n) { return String(n || "").replace(/[^\w\-]/g, ""); }
  function getBone(n) { return B[n] || B[boneKey(n)]; }
  function addRot(n, axis, angle) {
    var b = getBone(n);
    if (!b || !angle) return;
    var q = new THREE.Quaternion();
    var ax = axis === "x" ? new THREE.Vector3(1, 0, 0)
      : axis === "y" ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(0, 0, 1);
    q.setFromAxisAngle(ax, angle);
    b.quaternion.multiply(q);
  }
  function env(u) { var s = Math.sin(Math.PI * Math.min(1, Math.max(0, u))); return s * s; }
  function showCaption(t) {
    lastCaption = t;
    capEl.textContent = t;
    capEl.classList.add("show");
    clearTimeout(showCaption._t);
    showCaption._t = setTimeout(function () { capEl.classList.remove("show"); }, 4200);
  }
  function setState(s) {
    stateEl.textContent = s;
  }

  /* ---------------- 手势库：每帧在 idle 之上叠骨 ----------------- */
  var GESTURES = {
    wave: { dur: 2.4, fn: function (u) {
      var e = env(u), s = Math.sin(u * Math.PI * 6) * 0.35 * env(u);
      addRot("mixamorig:RightArm", "z", -1.25 * e);
      addRot("mixamorig:RightArm", "x", -0.35 * e);
      addRot("mixamorig:RightForeArm", "y", s);
      addRot("mixamorig:RightHand", "y", s * 0.8);
      addRot("mixamorig:Head", "z", 0.08 * e);
    } },
    nod: { dur: 1.5, fn: function (u) {
      var s = Math.sin(u * Math.PI * 4) * Math.sin(Math.PI * u);
      addRot("mixamorig:Head", "x", 0.26 * s);
      addRot("mixamorig:Neck", "x", 0.12 * s);
    } },
    shake: { dur: 1.6, fn: function (u) {
      var s = Math.sin(u * Math.PI * 6) * Math.sin(Math.PI * u);
      addRot("mixamorig:Head", "y", 0.30 * s);
      addRot("mixamorig:Neck", "y", 0.12 * s);
    } },
    bow: { dur: 2.2, fn: function (u) {
      var e = env(u);
      addRot("mixamorig:Spine1", "x", 0.30 * e);
      addRot("mixamorig:Spine2", "x", 0.28 * e);
      addRot("mixamorig:Neck", "x", 0.18 * e);
      addRot("mixamorig:Head", "x", 0.12 * e);
      addRot("mixamorig:LeftArm", "z", 0.10 * e);
      addRot("mixamorig:RightArm", "z", -0.10 * e);
    } },
    hug: { dur: 2.2, fn: function (u) {
      var e = env(u);
      addRot("mixamorig:LeftArm", "z", 0.9 * e);
      addRot("mixamorig:RightArm", "z", -0.9 * e);
      addRot("mixamorig:LeftForeArm", "y", -1.1 * e);
      addRot("mixamorig:RightForeArm", "y", 1.1 * e);
      addRot("mixamorig:Spine2", "x", 0.10 * e);
      addRot("mixamorig:Head", "x", 0.08 * e);
    } },
    heart: { dur: 2.4, fn: function (u) {
      var e = env(u);
      addRot("mixamorig:LeftArm", "z", 0.55 * e);
      addRot("mixamorig:RightArm", "z", -0.55 * e);
      addRot("mixamorig:LeftForeArm", "y", -1.5 * e);
      addRot("mixamorig:RightForeArm", "y", 1.5 * e);
      addRot("mixamorig:LeftHand", "z", 0.3 * e);
      addRot("mixamorig:RightHand", "z", -0.3 * e);
    } },
    clap: { dur: 2.0, fn: function (u) {
      var e = env(u), s = Math.sin(u * Math.PI * 10) * env(u);
      addRot("mixamorig:LeftArm", "z", 0.7 * e);
      addRot("mixamorig:RightArm", "z", -0.7 * e);
      addRot("mixamorig:LeftForeArm", "y", -0.9 * e + s * 0.25);
      addRot("mixamorig:RightForeArm", "y", 0.9 * e - s * 0.25);
      addRot("mixamorig:Head", "x", 0.06 * e);
    } },
    think: { dur: 3.0, fn: function (u) {
      var e = env(u);
      addRot("mixamorig:RightArm", "z", -0.55 * e);
      addRot("mixamorig:RightForeArm", "y", 1.9 * e);
      addRot("mixamorig:RightHand", "x", 0.5 * e);
      addRot("mixamorig:Head", "z", 0.12 * e);
      addRot("mixamorig:Head", "x", -0.05 * e);
    } },
    shy: { dur: 2.6, fn: function (u) {
      var e = env(u);
      addRot("mixamorig:Head", "x", 0.18 * e);
      addRot("mixamorig:Head", "z", -0.10 * e);
      addRot("mixamorig:LeftArm", "z", 0.35 * e);
      addRot("mixamorig:RightArm", "z", -0.35 * e);
      addRot("mixamorig:LeftForeArm", "y", -1.2 * e);
      addRot("mixamorig:RightForeArm", "y", 1.2 * e);
    } },
    angry: { dur: 2.6, fn: function (u) {
      var e = env(u), s = Math.sin(u * Math.PI * 5) * env(u);
      addRot("mixamorig:LeftArm", "z", 0.75 * e);
      addRot("mixamorig:RightArm", "z", -0.75 * e);
      addRot("mixamorig:LeftForeArm", "y", -1.4 * e);
      addRot("mixamorig:RightForeArm", "y", 1.4 * e);
      addRot("mixamorig:Head", "y", 0.20 * s);
      addRot("mixamorig:Spine2", "x", 0.06 * e);
    } },
    surprise: { dur: 2.0, fn: function (u) {
      var e = env(u);
      addRot("mixamorig:LeftArm", "z", 0.8 * e);
      addRot("mixamorig:RightArm", "z", -0.8 * e);
      addRot("mixamorig:LeftForeArm", "y", -0.5 * e);
      addRot("mixamorig:RightForeArm", "y", 0.5 * e);
      addRot("mixamorig:Spine1", "x", -0.10 * e);
      addRot("mixamorig:Head", "x", -0.14 * e);
    } },
    laugh: { dur: 2.6, fn: function (u) {
      var e = env(u), s = Math.sin(u * Math.PI * 8) * env(u);
      addRot("mixamorig:Spine2", "x", 0.10 * e + s * 0.03);
      addRot("mixamorig:Head", "x", 0.16 * e + s * 0.05);
      addRot("mixamorig:LeftArm", "z", 0.25 * e);
      addRot("mixamorig:RightArm", "z", -0.25 * e);
      addRot("mixamorig:LeftForeArm", "y", -0.7 * e);
      addRot("mixamorig:RightForeArm", "y", 0.7 * e);
    } },
    stretch: { dur: 3.2, fn: function (u) {
      var e = env(u);
      addRot("mixamorig:LeftArm", "z", 2.2 * e);
      addRot("mixamorig:RightArm", "z", -2.2 * e);
      addRot("mixamorig:Spine1", "x", -0.10 * e);
      addRot("mixamorig:Head", "x", -0.08 * e);
    } },
    point: { dur: 2.0, fn: function (u) {
      var e = env(u);
      addRot("mixamorig:RightArm", "x", 1.15 * e);
      addRot("mixamorig:RightArm", "z", -0.35 * e);
      addRot("mixamorig:RightForeArm", "y", 0.15 * e);
      addRot("mixamorig:Head", "y", -0.10 * e);
    } },
    salute: { dur: 2.2, fn: function (u) {
      var e = env(u);
      addRot("mixamorig:RightArm", "z", -0.75 * e);
      addRot("mixamorig:RightForeArm", "y", 1.9 * e);
      addRot("mixamorig:RightHand", "x", 0.4 * e);
      addRot("mixamorig:Spine2", "x", -0.04 * e);
    } },
    shrug: { dur: 1.8, fn: function (u) {
      var e = env(u);
      addRot("mixamorig:LeftArm", "z", 0.35 * e);
      addRot("mixamorig:RightArm", "z", -0.35 * e);
      addRot("mixamorig:LeftForeArm", "y", -0.4 * e);
      addRot("mixamorig:RightForeArm", "y", 0.4 * e);
      addRot("mixamorig:Head", "z", 0.10 * e);
    } },
    turn: { dur: 3.0, fn: function (u) {
      var e = env(u), side = Math.sin(u * Math.PI * 2);
      if (modelRoot) modelRoot.rotation.y = 1.35 * side * env(u);
    } },
    squat: { dur: 2.6, fn: function (u) {
      var e = env(u);
      addRot("mixamorig:Hips", "x", 0.18 * e);
      addRot("mixamorig:LeftUpLeg", "x", -0.65 * e);
      addRot("mixamorig:RightUpLeg", "x", -0.65 * e);
      addRot("mixamorig:LeftLeg", "x", 1.25 * e);
      addRot("mixamorig:RightLeg", "x", 1.25 * e);
      addRot("mixamorig:LeftFoot", "x", -0.55 * e);
      addRot("mixamorig:RightFoot", "x", -0.55 * e);
      addRot("mixamorig:Spine1", "x", 0.18 * e);
      if (modelRoot) modelRoot.position.y = -0.42 * e * 1.72;
    } },
    dance: { dur: 5.2, fn: function (u) {
      var e = env(u), s = Math.sin(u * Math.PI * 8), c = Math.sin(u * Math.PI * 4);
      addRot("mixamorig:Hips", "y", 0.22 * s * env(u));
      addRot("mixamorig:Spine2", "z", 0.10 * s * env(u));
      addRot("mixamorig:LeftArm", "z", 0.9 * env(u) + 0.35 * s * env(u));
      addRot("mixamorig:RightArm", "z", -0.9 * env(u) - 0.35 * s * env(u));
      addRot("mixamorig:LeftForeArm", "y", -1.0 * c * env(u));
      addRot("mixamorig:RightForeArm", "y", 1.0 * c * env(u));
      addRot("mixamorig:Head", "z", 0.10 * c * env(u));
    } },
    talk: { dur: 4.0, fn: function (u) {
      var e = env(u), s = Math.sin(u * Math.PI * 10) * env(u);
      addRot("mixamorig:Head", "x", 0.06 * s);
      addRot("mixamorig:Neck", "x", 0.03 * s);
      addRot("mixamorig:RightArm", "z", -0.35 * e);
      addRot("mixamorig:RightForeArm", "y", 1.2 * e + 0.10 * s);
      addRot("mixamorig:LeftArm", "z", 0.12 * e);
    } },
    ready: { dur: 1.6, fn: function (u) {
      var e = env(u);
      addRot("mixamorig:Head", "x", 0.08 * e);
      addRot("mixamorig:Spine2", "x", 0.05 * e);
    } }
  };

  var INTENTS = [
    { re: /(挥|招)手|打招呼|你好|嗨|hello/i, g: "wave", say: "你好呀。" },
    { re: /点头|同意|好的|可以/, g: "nod", say: "嗯。" },
    { re: /摇头|不同意|不行|不要/, g: "shake", say: "不行哦。" },
    { re: /鞠躬|行礼|谢谢|感谢/, g: "bow", say: "不客气。" },
    { re: /拥抱|抱抱|抱一下/, g: "hug", say: "来，抱一个。" },
    { re: /比心|爱心|爱你/, g: "heart", say: "给你比心。" },
    { re: /鼓掌|拍手|棒/, g: "clap", say: "厉害。" },
    { re: /思考|想想|考虑/, g: "think", say: "我想想。" },
    { re: /害羞|不好意思|脸红/, g: "shy", say: "别这样说啦。" },
    { re: /生气|愤怒|气死/, g: "angry", say: "哼。" },
    { re: /惊讶|吃惊|真的假的|不会吧/, g: "surprise", say: "真的？" },
    { re: /笑|开心|高兴|哈哈/, g: "laugh", say: "哈哈。" },
    { re: /伸懒腰|伸展|伸个懒腰/, g: "stretch", say: "嗯——舒服。" },
    { re: /指|那边|看那里/, g: "point", say: "那边。" },
    { re: /敬礼|收到|遵命/, g: "salute", say: "收到。" },
    { re: /耸肩|不知道|随便/, g: "shrug", say: "我也不知道。" },
    { re: /转身|转一圈|转个身/, g: "turn", say: "好。" },
    { re: /蹲|蹲下|蹲一下/, g: "squat", say: "好。" },
    { re: /跳舞|跳一个|来一段/, g: "dance", say: "来一段。" },
    { re: /走两步|走路|走一下/, g: "walk", say: "好。" },
    { re: /站好|站起来|回来/, g: "reset", say: "嗯。" }
  ];

  function playGesture(name) {
    if (name === "reset" && modelRoot) {
      modelRoot.rotation.y = 0; modelRoot.position.y = 0;
    }
    if (name === "walk" && mixer) {
      var clip = null;
      (window.__DH_CLIPS || []).forEach(function (c) { if (/walk/i.test(c.name)) clip = c; });
      if (clip) {
        var a = mixer.clipAction(clip);
        a.reset(); a.setLoop(THREE.LoopOnce, 1); a.clampWhenFinished = true;
        a.fadeIn(0.35).play();
        setTimeout(function () { if (a.isRunning()) a.fadeOut(0.4); }, 2200);
      }
    }
    // 首选：动作由服务端触手层下发（万能插执行器 + 眼手脑闭环）
    fetch("/api/dh/action", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gesture: name }) }).then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.ok) {
          SRV.active = true; SRV.ok = true; SRV.action = name;
          SRV.dur = Number(d.dur || 2.0); SRV.phase = 0;
          SRV.targets = []; SRV.applied = []; SRV.pending = false;
          SRV.startedAt = performance.now(); SRV.lastResp = performance.now();
          G = null;
        } else {
          fallbackGesture(name);
        }
      }).catch(function () { fallbackGesture(name); });
  }

  function fallbackGesture(name) {
    if (!GESTURES[name] && name !== "walk" && name !== "reset") return;
    SRV.active = false; SRV.ok = false;
    G = { name: name, t0: performance.now() / 1000,
      dur: GESTURES[name] ? GESTURES[name].dur : 2.0 };
  }

  function postFrame(eye) {
    if (SRV.pending) return;
    SRV.pending = true;
    fetch("/api/dh/frame", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ eye: eye }) }).then(function (r) { return r.json(); })
      .then(function (d) {
        SRV.pending = false;
        if (!d || !d.ok) return;
        SRV.targets = d.targets || [];
        SRV.phase = Number(d.phase || 0);
        SRV.lastResp = performance.now();
        if (SRV.phase > SRV.dur + 0.35) SRV.active = false;
      }).catch(function () { SRV.pending = false; });
  }

  function applyServerTargets() {
    for (var i = 0; i < SRV.targets.length; i++) {
      var t = SRV.targets[i];
      addRot("mixamorig:" + t.bone, t.axis, Number(t.sign || 1) * Number(t.angle || 0));
    }
    SRV.applied = SRV.targets;
  }

  function applyGesture(now) {
    if (!G) return;
    var u = (now - G.t0) / G.dur;
    if (u >= 1) {
      G = null;
      if (modelRoot) { modelRoot.rotation.y *= 0.9; }
      return;
    }
    var def = GESTURES[G.name];
    if (def) def.fn(Math.min(1, Math.max(0, u)));
  }

  function idleLayer(now) {
    idleT = now;
    addRot("mixamorig:Spine1", "x", Math.sin(now * 0.9) * 0.012);
    addRot("mixamorig:Spine2", "x", Math.sin(now * 0.7 + 0.6) * 0.012);
    addRot("mixamorig:Head", "y", Math.sin(now * 0.45) * 0.05);
    addRot("mixamorig:Head", "x", Math.sin(now * 0.9 + 0.4) * 0.02);
    // 平视修正：让她看镜头而不是仰头看人（Head.nod 实测轴 z / sign -1）
    applyHeadFix();
    addRot("mixamorig:LeftArm", "z", Math.sin(now * 0.8) * 0.02);
    addRot("mixamorig:RightArm", "z", -Math.sin(now * 0.8 + 0.8) * 0.02);
    if (modelRoot) modelRoot.position.y = Math.sin(now * 1.0) * 0.004;
  }

  function animate() {
    requestAnimationFrame(animate);
    var dt = Math.min(0.05, clock.getDelta());
    var now = clock.elapsedTime;
    if (mixer) mixer.update(dt);
    // 只回正「当前 idle clip 不驱动旋转」的骨（Hips 是 position-only，必须回正，
    // 否则它会被动作叠加旋转一直带着转；手臂等 idle 驱动的骨保持动画姿势）
    for (var rk in RESTQ) {
      if (!ANIM[rk] && B[rk]) B[rk].quaternion.copy(RESTQ[rk]);
    }
    // Hips / Head / Neck 无条件回正：根骨防叠加漂移；头颈防资产 idle 的仰头/偏头
    ["mixamorig:Hips", "mixamorig:Head", "mixamorig:Neck"].forEach(function (bn) {
      var b = getBone(bn);
      if (b && RESTQ[b.name]) b.quaternion.copy(RESTQ[b.name]);
    });
    if (modelRoot) {
      idleLayer(now);
      if (SRV.active && SRV.ok) {
        // 超时保护：动作结束 / 服务端掉帧 ⇒ 立刻回正，不留半截姿势
        if (performance.now() - SRV.lastResp > 700 ||
            performance.now() - SRV.startedAt > (SRV.dur + 0.8) * 1000) {
          SRV.active = false; SRV.targets = []; SRV.applied = [];
        }
        var eye = {};
        for (var i = 0; i < SRV.applied.length; i++) {
          eye[SRV.applied[i].bone + "." + SRV.applied[i].axis] = SRV.applied[i].angle;
        }
        if (performance.now() - SRV.lastSent > 40) {
          SRV.lastSent = performance.now();
          postFrame(eye);
        }
        applyServerTargets();
      } else {
        applyGesture(now);
      }
    }
    renderer.render(scene, camera);
  }

  function init() {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.26;
    renderer.shadowMap.enabled = true;
    stage.appendChild(renderer.domElement);

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x07080a);
    scene.fog = new THREE.FogExp2(0x07080a, 0.03);
    camera = new THREE.PerspectiveCamera(34, window.innerWidth / window.innerHeight, 0.1, 100);

    var hemi = new THREE.HemisphereLight(0xdbe9ff, 0x2a211a, 1.45);
    scene.add(hemi);
    var key = new THREE.DirectionalLight(0xfff4ea, 2.9);
    key.position.set(2.2, 3.4, 3.0);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.camera.near = 0.5; key.shadow.camera.far = 12;
    key.shadow.camera.left = -2; key.shadow.camera.right = 2;
    key.shadow.camera.top = 3; key.shadow.camera.bottom = -1;
    scene.add(key);
    var rim = new THREE.DirectionalLight(0x9fc4e0, 1.6);
    rim.position.set(-2.4, 2.2, -2.2);
    scene.add(rim);
    var fill = new THREE.DirectionalLight(0xffe9d8, 1.0);
    fill.position.set(-1.0, 1.4, 2.6);
    scene.add(fill);
    var faceFill = new THREE.DirectionalLight(0xffe7d8, 0.55);
    faceFill.position.set(0, 1.6, 3.2);
    scene.add(faceFill);

    var floorGeo = new THREE.CircleGeometry(3.2, 64);
    var floorMat = new THREE.MeshStandardMaterial({ color: 0x0c0e12, roughness: 0.95, metalness: 0.0 });
    var floor = new THREE.Mesh(floorGeo, floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    scene.add(floor);
    var glow = new THREE.Mesh(new THREE.CircleGeometry(1.4, 48),
      new THREE.MeshBasicMaterial({ color: 0x0f1820, transparent: true, opacity: 0.7 }));
    glow.rotation.x = -Math.PI / 2; glow.position.y = 0.002;
    scene.add(glow);

    clock = new THREE.Clock();
    var loader = new THREE.GLTFLoader();
    loader.load("../voice-theater/assets/dh-tentacle-rerig.glb", function (gltf) {
      modelRoot = gltf.scene || (gltf.scenes && gltf.scenes[0]);
      if (!modelRoot) { setState("模型缺失"); return; }
      var box = new THREE.Box3().setFromObject(modelRoot);
      var size = new THREE.Vector3(); box.getSize(size);
      if (isFinite(size.y) && size.y > 0) {
        var k = 1.72 / size.y;
        modelRoot.scale.multiplyScalar(k);
        box.setFromObject(modelRoot);
        var c = new THREE.Vector3(); box.getCenter(c);
        modelRoot.position.x -= c.x;
        modelRoot.position.z -= c.z;
        modelRoot.position.y -= box.min.y;
      }
      modelRoot.traverse(function (o) {
        if (o.isMesh || o.isSkinnedMesh) {
          o.frustumCulled = false; o.castShadow = true;
          var mats = Array.isArray(o.material) ? o.material : [o.material];
          mats.forEach(function (mm) {
            if (!mm) return;
            if (mm.map) {
              mm.map.anisotropy = 8;
              mm.map.colorSpace = THREE.SRGBColorSpace;
            }
            if ("envMapIntensity" in mm) mm.envMapIntensity = 1.0;
            if ("roughness" in mm) mm.roughness = Math.max(0.35, mm.roughness);
            mm.needsUpdate = true;
          });
        }
        if (o.isBone) {
          B[o.name] = o; B[boneKey(o.name)] = o;
          RESTQ[o.name] = o.quaternion.clone();
        }
      });
      scene.add(modelRoot);
      window.__DH_CLIPS = gltf.animations || [];
      mixer = new THREE.AnimationMixer(modelRoot);
      var idleClip = null;
      (gltf.animations || []).forEach(function (c) {
        if (/idle/i.test(c.name)) idleClip = c;
      });
      if (!idleClip && gltf.animations && gltf.animations.length) idleClip = gltf.animations[0];
      // ANIM = idle clip 真正驱动四元数的骨；其它骨（尤其 Hips）每帧回正
      if (idleClip) {
        (idleClip.tracks || []).forEach(function (tr) {
          var full = String(tr.name || "");
          if (!/\.quaternion$/.test(full)) return;
          var nm = full.split(".")[0];
          if (nm) { ANIM[nm] = true; ANIM[boneKey(nm)] = true; }
        });
      }
      if (idleClip) mixer.clipAction(idleClip).play();
      // 相机取全身
      camera.position.set(0, 1.45, 3.55);
      camera.lookAt(0, 1.32, 0);
      setState("待机");
      window.__DH_READY = true;
      playGesture("ready");
    }, undefined, function () {
      setState("模型加载失败");
      hintEl.textContent = "模型没有加载到（voice-theater/assets/dh-v2-rigged.glb）";
    });

    window.addEventListener("resize", function () {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    });
    animate();
  }

  /* ---------------- 语音 → 动作 / 对话（本机离线 ASR） ---------------- */
  var listening = false;

  function setMic(on) {
    listening = on;
    setState(on ? "在听" : "待机");
    if (hintEl) hintEl.style.opacity = on ? "1" : "0";
  }
  function speak(text) {
    if (!window.speechSynthesis) { showCaption(text); return; }
    try { window.speechSynthesis.cancel(); } catch (e) {}
    var u = new SpeechSynthesisUtterance(text);
    u.lang = "zh-CN"; u.rate = 1.02; u.pitch = 1.02;
    u.onstart = function () { talking = true; setState("在说"); playGesture("talk"); };
    u.onend = function () { talking = false; setState(listening ? "在听" : "待机"); };
    window.speechSynthesis.speak(u);
    showCaption(text);
  }
  function handleText(text) {
    text = String(text || "").trim();
    if (!text) return;
    showCaption("“" + text + "”");
    for (var i = 0; i < INTENTS.length; i++) {
      if (INTENTS[i].re.test(text)) {
        playGesture(INTENTS[i].g === "walk" ? "walk" : INTENTS[i].g);
        if (INTENTS[i].say) speak(INTENTS[i].say);
        return;
      }
    }
    setState("在想");
    fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text }) }).then(function (r) { return r.json(); })
      .then(function (d) {
        speak((d && d.ok && d.text) ? d.text : "我这边没连上模型，先在设置里配一下模型吧。");
      }).catch(function () { speak("我这会儿没连上模型。"); });
  }

  /* 按住空格：浏览器录音 → 16k WAV → 本机离线识别 */
  var PTT = { stream: null, ctx: null, src: null, proc: null, sink: null,
    chunks: [], on: false, rate: 48000 };

  function encodeWav(chunks, inRate, outRate) {
    var total = 0;
    for (var i = 0; i < chunks.length; i++) total += chunks[i].length;
    var ratio = inRate / outRate;
    var outN = Math.max(1, Math.floor(total / ratio));
    var pcm = new Int16Array(outN);
    var pos = 0;
    for (var c = 0; c < chunks.length; c++) {
      var ch = chunks[c];
      for (var j = 0; j < ch.length; j++) {
        var idx = Math.floor((pos + j) / ratio);
        if (idx >= outN) break;
        var s = Math.max(-1, Math.min(1, ch[j]));
        pcm[idx] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      pos += ch.length;
    }
    var buf = new ArrayBuffer(44 + pcm.length * 2);
    var v = new DataView(buf);
    function ws(off, str) { for (var k = 0; k < str.length; k++) v.setUint8(off + k, str.charCodeAt(k)); }
    ws(0, "RIFF"); v.setUint32(4, 36 + pcm.length * 2, true); ws(8, "WAVE");
    ws(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true);
    v.setUint16(22, 1, true); v.setUint32(24, outRate, true);
    v.setUint32(28, outRate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    ws(36, "data"); v.setUint32(40, pcm.length * 2, true);
    new Int16Array(buf, 44).set(pcm);
    return buf;
  }
  function bufToB64(buf) {
    var bytes = new Uint8Array(buf), bin = "";
    for (var i = 0; i < bytes.length; i += 0x8000) {
      bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    }
    return btoa(bin);
  }

  function startPTT() {
    if (PTT.on) return;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      hintEl.textContent = "这个窗口不支持录音（getUserMedia 不可用）";
      hintEl.style.opacity = "1";
      return;
    }
    navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1,
      echoCancellation: true, noiseSuppression: true, autoGainControl: true } })
      .then(function (stream) {
        PTT.stream = stream;
        var AC = window.AudioContext || window.webkitAudioContext;
        PTT.ctx = new AC({ sampleRate: 16000 });
        PTT.rate = PTT.ctx.sampleRate || 16000;
        PTT.src = PTT.ctx.createMediaStreamSource(stream);
        PTT.proc = PTT.ctx.createScriptProcessor(2048, 1, 1);
        PTT.chunks = [];
        PTT.proc.onaudioprocess = function (ev) {
          PTT.chunks.push(new Float32Array(ev.inputBuffer.getChannelData(0)));
        };
        PTT.sink = PTT.ctx.createGain();
        PTT.sink.gain.value = 0;
        PTT.src.connect(PTT.proc);
        PTT.proc.connect(PTT.sink);
        PTT.sink.connect(PTT.ctx.destination);
        PTT.on = true;
        setMic(true);
        hintEl.textContent = "在听…松开空格发送";
        hintEl.style.opacity = "1";
      }).catch(function (err) {
        hintEl.textContent = "麦克风没开成：" + String((err && err.name) || err).slice(0, 60);
        hintEl.style.opacity = "1";
      });
  }

  function stopPTT() {
    if (!PTT.on) return;
    PTT.on = false;
    try { PTT.proc.disconnect(); } catch (e) {}
    try { PTT.src.disconnect(); } catch (e) {}
    try { PTT.sink.disconnect(); } catch (e) {}
    try { PTT.stream.getTracks().forEach(function (t) { t.stop(); }); } catch (e) {}
    var rate = PTT.rate;
    var chunks = PTT.chunks.slice();
    try { PTT.ctx.close(); } catch (e) {}
    setMic(false);
    hintEl.textContent = "识别中…";
    hintEl.style.opacity = "1";
    if (!chunks.length) {
      hintEl.textContent = "没录到声音，再按住空格试一次";
      return;
    }
    var wav = encodeWav(chunks, rate, 16000);
    var b64 = bufToB64(wav);
    fetch("/api/asr", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ wav_b64: b64, culture: "zh-CN" }) })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.ok && d.heard && d.text) { handleText(d.text); return; }
        SRV.active = false; SRV.targets = []; SRV.applied = []; SRV.ok = false; G = null;
        hintEl.textContent = (d && d.ok) ? "没听清，按住空格再说一次" :
          "识别器不可用：" + String((d && (d.reason || d.error)) || "未知").slice(0, 60);
        hintEl.style.opacity = "1";
      }).catch(function () {
        hintEl.textContent = "语音服务没响应（/api/asr）";
        hintEl.style.opacity = "1";
      });
  }

  window.addEventListener("keydown", function (e) {
    if (e.code !== "Space" || e.repeat) return;
    var t = e.target;
    if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
    e.preventDefault();
    startPTT();
  });
  window.addEventListener("keyup", function (e) {
    if (e.code !== "Space") return;
    e.preventDefault();
    stopPTT();
  });
  window.addEventListener("blur", function () { if (PTT.on) stopPTT(); });

  var HEAD_FIX = { hx: 0, hy: 0, hz: 0, nx: 0, ny: 0, nz: 0 };
  function applyHeadFix() {
    if (HEAD_FIX.hx) addRot("mixamorig:Head", "x", HEAD_FIX.hx);
    if (HEAD_FIX.hy) addRot("mixamorig:Head", "y", HEAD_FIX.hy);
    if (HEAD_FIX.hz) addRot("mixamorig:Head", "z", HEAD_FIX.hz);
    if (HEAD_FIX.nx) addRot("mixamorig:Neck", "x", HEAD_FIX.nx);
    if (HEAD_FIX.ny) addRot("mixamorig:Neck", "y", HEAD_FIX.ny);
    if (HEAD_FIX.nz) addRot("mixamorig:Neck", "z", HEAD_FIX.nz);
  }

  function focusHand(side) {
    var b = getBone("mixamorig:" + (side || "Right") + "Hand");
    if (!b || !camera) return false;
    var p = new THREE.Vector3();
    b.getWorldPosition(p);
    camera.position.set(p.x + 0.35, p.y + 0.12, p.z + 0.55);
    camera.lookAt(p.x, p.y, p.z);
    return true;
  }
  window.__DH = {
    focusHand: focusHand,
    headFix: function (hx, hy, hz, nx, ny, nz) {
      HEAD_FIX.hx = +hx || 0; HEAD_FIX.hy = +hy || 0; HEAD_FIX.hz = +hz || 0;
      HEAD_FIX.nx = +nx || 0; HEAD_FIX.ny = +ny || 0; HEAD_FIX.nz = +nz || 0;
      return HEAD_FIX;
    },
    gesture: playGesture,
    debug: function () {
      var hips = getBone("mixamorig:Hips");
      return { srv: { active: SRV.active, action: SRV.action, phase: SRV.phase,
        dur: SRV.dur, targets: SRV.targets.length, ok: SRV.ok, pending: SRV.pending },
        root: modelRoot ? { rot: modelRoot.rotation.toArray(), pos: modelRoot.position.toArray() } : null,
        cam: camera ? { pos: camera.position.toArray(), up: camera.up.toArray(), rot: camera.rotation.toArray() } : null,
        hips: hips ? { q: hips.quaternion.toArray(), animated: !!ANIM[hips.name] } : null,
        mix: mixer ? { time: mixer.time, actions: (mixer._actions || []).length,
          running: (mixer._actions || []).map(function (a) { return {
            n: (a._clip && a._clip.name) || "", run: a.isRunning(), w: a.getEffectiveWeight(),
            t: a.time, dur: a._clip ? a._clip.duration : 0 }; }) } : null };
    },
    text: handleText,
    speak: speak,
    ready: function () { return !!window.__DH_READY; }
  };

  if (!window.THREE) { document.body.innerHTML = "<div style='color:#fff;padding:40px'>three 未载入</div>"; return; }
  init();
})();
