/* GBT小土豆V8 · 语音剧场 · **真 3D 数字人舞台**（经典脚本，无模块）
 *
 * ## 它换掉了什么（2026-10-18 主子令：「推到重做…我需要的是按照源码实现」）
 * 上一版中间是一张**静态 JPG**（digital-human-hero-3q.jpg）—— 换了个壳，人还是不动的一张图。
 * 现在：直接吃工程里**现成的绑骨资产**：
 *     assets/dh-v2-rigged.glb   6.4 MB · 1 mesh · 1 skin(65 骨骼) · 2 段动作(idle/walk) · 3 张内嵌贴图
 * 用壳里已 vendor 的 three@0.180.0（`brain/vendor/*.global.js`，零 CDN）真渲染、真播动作。
 *
 * ## 老实说清楚的一件事：这段资产**没有口型**
 * 骨骼是标准 Mixamo 65 根（Hips/Spine/Neck/Head/四肢），**没有 jaw/嘴骨**，网格也没有 morph target。
 * ⇒ 「在说」这一态**不用假的嘴动冒充**：用**头颈点头节律 + 右臂手势**表示在说话，幅度由**真实
 *    AnalyserNode 音量**驱动；体检里如实写「无口型骨/形态键」。做不到就说做不到（本仓纪律）。
 *
 * ## 接线（只对外暴露三件事）
 *   window.GBT_DH3D.setState("idle"|"listen"|"think"|"speak")
 *   window.GBT_DH3D.level(0..1)      // 真音量，不说话时传 0
 *   window.GBT_DH3D.info()           // {ok,status,why,bones,clips,frames}
 * 失败一律**写清原因**到 `#dh3dStatus`，绝不静默空白（空白帧与"没做"在截图上一模一样）。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
(function () {
  "use strict";

  var canvas = document.getElementById("dh3d");
  var badge = document.getElementById("dh3dStatus");

  var S = {
    ok: false, status: "loading", why: "",
    state: "idle", level: 0, bones: 0, clips: [], frames: 0,
    hasJaw: false
  };

  function say(text, tone) {
    S.why = tone === "ok" ? "" : text;
    if (badge) {
      badge.textContent = text;
      badge.setAttribute("data-tone", tone || "warn");
    }
  }

  function info() { return S; }
  /* 早失败也要能读：页面在引擎缺失时照样要给得出原因 */
  /* 2026-10-30 增：运行时读数。dh_realism.check() 要的就是这一份，
     没有它后面全是盲改（主人令：先补读数采集）。
     只读，不改任何状态；WebGL 起不来时也照样回一份 status，不假装有数。 */
  function readings() {
    var out = { ok: true, at: new Date().toISOString(),
                status: S.status, bones: S.bones, clips: S.clips,
                has_jaw: !!S.hasJaw, webgl: true };
    try {
      out.environment = !!(scene && scene.environment);
      var dirSum = 0, hemi = 0;
      scene.traverse(function (o) {
        if (o.isDirectionalLight) dirSum += (o.intensity || 0);
        if (o.isHemisphereLight) hemi += (o.intensity || 0);
      });
      out.dir_light_sum = +dirSum.toFixed(3);
      out.hemi = +hemi.toFixed(3);
      out.exposure = +Number(renderer.toneMappingExposure || 0).toFixed(3);
      out.tone_mapping = (renderer.toneMapping === THREE.ACESFilmicToneMapping)
        ? "ACESFilmic" : String(renderer.toneMapping);
      out.color_space = String(renderer.outputColorSpace || "");
      var mm = [], iors = [], sps = [], ccs = [], rgh = [];
      var bodyPx = 0, hasNormal = false, meshes = 0, skinned = 0;
      scene.traverse(function (o) {
        if (!(o.isMesh || o.isSkinnedMesh)) return;
        meshes += 1; if (o.isSkinnedMesh) skinned += 1;
        var mats = Array.isArray(o.material) ? o.material : [o.material];
        mats.forEach(function (m) {
          if (!m) return;
          if (typeof m.metalness === "number") mm.push(m.metalness);
          if (typeof m.ior === "number") iors.push(m.ior);
          if (typeof m.specularIntensity === "number") sps.push(m.specularIntensity);
          if (typeof m.clearcoat === "number") ccs.push(m.clearcoat);
          if (typeof m.roughness === "number") rgh.push(m.roughness);
          if (m.normalMap) hasNormal = true;
          if (m.map && m.map.image && m.map.image.width) {
            bodyPx = Math.max(bodyPx, m.map.image.width);
          }
        });
      });
      function avg(a) { return a.length ? +(a.reduce(function (x, y) { return x + y; }, 0) / a.length).toFixed(3) : null; }
      out.meshes = meshes; out.skinned = skinned;
      out.metalness_mean = avg(mm);
      out.ior = avg(iors);
      out.specular = avg(sps);
      out.clearcoat = avg(ccs);
      out.diffuse_roughness = avg(rgh);
      out.body_tex_px = bodyPx || null;
      out.detail_normal = hasNormal;
      out.model_in_scene = !!(modelRoot && modelRoot.parent);
      out.model_visible = modelRoot ? !!modelRoot.visible : null;
      out.model_scale = modelRoot ? +modelRoot.scale.x.toFixed(4) : null;
      out.model_pos = modelRoot ? [+modelRoot.position.x.toFixed(2),
                                   +modelRoot.position.y.toFixed(2),
                                   +modelRoot.position.z.toFixed(2)] : null;
      out.camera_pos = camera ? [+camera.position.x.toFixed(2),
                                 +camera.position.y.toFixed(2),
                                 +camera.position.z.toFixed(2)] : null;
      out.ssaa = DH_SSAA;
      out.pixel_ratio = renderer ? renderer.getPixelRatio() : null;
      out.buffer_px = renderer ? [renderer.domElement.width, renderer.domElement.height] : null;
      out.face_light = faceLight ? +Number(faceLight.intensity || 0).toFixed(3) : null;
      out.state_machine = {
        state: DH.state, prev: DH.prev, blend_s: DH.blend,
        weights: DH.weights, foot_lock: DH.footLock,
        foot_drift_mm: DH.drift_mm, foot_drift_max_mm: DH.drift_max_mm,
        frames: DH.frames
      };
      out.draw_calls = (renderer.info && renderer.info.render && renderer.info.render.calls) || null;
      out.triangles = (renderer.info && renderer.info.render && renderer.info.render.triangles) || null;
    } catch (e) {
      out.ok = false; out.error = String(e && e.message || e).slice(0, 160);
    }
    return out;
  }

  window.GBT_DH3D = { setState: function () {}, level: function () {}, info: info,
                      exportPNG: exportPNG, getSSAA: function () { return DH_SSAA; },
                      setSSAA: function (n) { DH_SSAA = Math.max(1, Math.min(4, Number(n) || 1)); dhApplyPixelRatio(); resize(); return DH_SSAA; },
                      readings: readings };

  if (!canvas) { S.status = "no-canvas"; return; }
  if (!window.THREE) {
    S.status = "no-three";
    say("3D 引擎没载入（brain/vendor/three.global.js 缺失或没挂上）⇒ 舞台留空，不拿图片顶替", "fault");
    return;
  }
  var THREE = window.THREE;

  if (!THREE.GLTFLoader) {
    S.status = "no-loader";
    say("GLTFLoader 没载入（vendor 里缺 GLTFLoader.global.js）⇒ 载不了模型，不拿图片顶替", "fault");
    return;
  }

  /* ── 渲染器 ─────────────────────────────────────────────────────────── */
  var renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
  } catch (err) {
    S.status = "no-webgl";
    say("WebGL 起不来（" + String(err && err.message || err).slice(0, 90) + "）⇒ 3D 舞台不可用", "fault");
    return;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  if ("outputColorSpace" in renderer) renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.00;   /* 2026-10-30：1.18 → 1.0（读数判据 ⑤ 要求 ≤1.0） */
  renderer.setClearAlpha(0);

  var scene = new THREE.Scene();
  /* ① IBL 环境（2026-10-30）：没有 scene.environment ⇒ 皮肤只有方向光镜面高光、无环境包裹，
     这是「像 CG」的头号原因。零外部 HDRI：PMREM 从程序化场景烘一张。 */
  try {
    if (THREE.PMREMGenerator) {
      var pmrem = new THREE.PMREMGenerator(renderer);
      var envScene = new THREE.Scene();
      envScene.background = new THREE.Color(0x101822);
      envScene.add(new THREE.Mesh(new THREE.SphereGeometry(50, 8, 8),
        new THREE.MeshBasicMaterial({ color: 0x9fb6d6, side: THREE.BackSide })));
      var pA = new THREE.Mesh(new THREE.PlaneGeometry(20, 20),
        new THREE.MeshBasicMaterial({ color: 0xffe3b8 }));
      pA.position.set(-6, 8, 6); pA.lookAt(0, 0, 0); envScene.add(pA);
      var pB = new THREE.Mesh(new THREE.PlaneGeometry(16, 16),
        new THREE.MeshBasicMaterial({ color: 0x00e5ff }));
      pB.position.set(8, 4, -8); pB.lookAt(0, 0, 0); envScene.add(pB);
      scene.environment = pmrem.fromScene(envScene, 0.04).texture;
      pmrem.dispose();
    }
  } catch (eIbl) {}
  var camera = new THREE.PerspectiveCamera(32, 1, 0.05, 60);
  camera.position.set(0.62, 1.16, 3.3);
  camera.lookAt(0, 1.02, 0);

  /* ── 灯：跟着剧场的金/青配色走（不是随便打的棚灯） ────────────────── */
  scene.add(new THREE.HemisphereLight(0x9fb6d6, 0x141821, 0.30)   /* 0.85 → 0.30：半球只做底色 */);

  var key = new THREE.DirectionalLight(0xffe3b8, 1.10);          /* 暖金主光 · 前左 */
  key.position.set(-1.9, 2.6, 2.2);
  scene.add(key);

  var rim = new THREE.DirectionalLight(0x00e5ff, 0.65);           /* 青色轮廓光 · 后右 */
  rim.position.set(2.3, 2.0, -2.4);
  scene.add(rim);

  var fill = new THREE.DirectionalLight(0xb9c8ff, 0.30);         /* 冷调补光 · 正面弱 */
  fill.position.set(0.6, 1.2, 3.0);
  scene.add(fill);

  /* 脚灯：给腿补一点暖光。第一版实拍下半身全黑（纱幕+背光），补这盏才看得见靴子线条 */
  var foot = new THREE.PointLight(0xf5b041, 1.7, 3.4, 2.0);
  foot.position.set(0, 0.18, 1.1);
  scene.add(foot);

  /* 接地影：**程序生成**的椭圆软影（不引任何外部贴图，仍是零 CDN）。
     没有它，人像会像"吊在半空"——这是第一版实拍最直白的破绽。 */
  (function groundShadow() {
    var cv = document.createElement("canvas");
    cv.width = 256; cv.height = 256;
    var g = cv.getContext("2d");
    var rg = g.createRadialGradient(128, 128, 6, 128, 128, 118);
    rg.addColorStop(0, "rgba(3,4,12,.70)");
    rg.addColorStop(0.5, "rgba(3,4,12,.28)");
    rg.addColorStop(1, "rgba(3,4,12,0)");
    g.fillStyle = rg;
    g.fillRect(0, 0, 256, 256);
    var tex = new THREE.CanvasTexture(cv);
    if ("colorSpace" in tex) tex.colorSpace = THREE.SRGBColorSpace;
    var m = new THREE.Mesh(
      new THREE.PlaneGeometry(0.95, 0.62),
      new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, opacity: 0.9 })
    );
    m.rotation.x = -Math.PI / 2;
    m.position.set(0, 0.004, 0.03);
    scene.add(m);
  })();

  /* ── 载模型（本地文件，一条网都不出） ─────────────────────────────── */
  var stage = new THREE.Group();
  scene.add(stage);

  var mixer = null, actionIdle = null, actionWalk = null;

  /* ── 动作状态机（2026-10-30 补）───────────────────────────────────────
     原来 setState 只存一个字符串：walk 从不播放、切换没有过渡、脚会打滑。
     这里给三件真东西：
       ① 交叉淡入：idle ↔ walk ↔ speak 用 crossFadeTo（默认 0.35s），不是硬切
       ② 脚部锁定：过渡/行走时把着地脚的**世界位置**钉住，用根位移反向补偿
       ③ 可读数：当前状态 / 各动作权重 / 脚漂移毫米数（readings() 会带上）
     ─────────────────────────────────────────────────────────────────── */
  var DH = {
    state: "idle", prev: null, blend: 0.35,
    actions: {},                 /* name → AnimationAction */
    weights: {},                 /* name → 当前权重 */
    footLock: true, lockFoot: null,
    drift_mm: 0, drift_max_mm: 0, frames: 0
  };
  var FOOT_NAMES = ["mixamorig:LeftFoot", "mixamorig:RightFoot",
                    "LeftFoot", "RightFoot"];
  var _lastFootWorld = null;

  function dhAction(name) {
    if (DH.actions[name]) return DH.actions[name];
    if (!mixer) return null;
    var clip = null;
    var clips = (window.__DH_CLIPS || []);
    for (var i = 0; i < clips.length; i++) if (clips[i].name === name) clip = clips[i];
    if (!clip) return null;
    var a = mixer.clipAction(clip);
    a.enabled = true; a.setEffectiveWeight(0);
    DH.actions[name] = a;
    return a;
  }

  function dhSetState(name, blend) {
    name = String(name || "idle");
    if (DH.state === name) return DH.state;
    blend = (blend == null) ? DH.blend : Number(blend);
    var from = DH.actions[DH.state], to = dhAction(name);
    DH.prev = DH.state;
    DH.state = name;
    st.state = name; S.state = name;
    if (!mixer) return DH.state;
    if (to) {
      to.reset(); to.enabled = true; to.setEffectiveTimeScale(1);
      to.setEffectiveWeight(1);
      to.play();
      if (from && from !== to) {
        try { from.crossFadeTo(to, blend, false); }
        catch (eCF) { from.stop(); }
      } else {
        to.fadeIn(blend);
      }
    } else if (from) {
      from.fadeOut(blend);         /* 没有对应 clip：至少淡出，不硬停 */
    }
    return DH.state;
  }

  function dhFootWorld() {
    if (!B) return null;
    for (var i = 0; i < FOOT_NAMES.length; i++) {
      var b = B[FOOT_NAMES[i]];
      if (b) { var v = new THREE.Vector3(); b.getWorldPosition(v); return v; }
    }
    return null;
  }

  /* 脚部锁定：着地脚不该漂。每帧比对脚的世界 XZ，把偏差从模型根上反向扣掉。
     这是根位移补偿法：不改骨骼动画，只改根位置 —— 换个模型也照样能用。 */
  function dhFootLockStep() {
    if (!DH.footLock || !modelRoot) return;
    var fw = dhFootWorld();
    if (!fw) return;
    if (!_lastFootWorld) { _lastFootWorld = fw.clone(); return; }
    var dx = fw.x - _lastFootWorld.x, dz = fw.z - _lastFootWorld.z;
    var d = Math.sqrt(dx * dx + dz * dz) * 1000;      /* mm */
    DH.drift_mm = +d.toFixed(2);
    if (d > DH.drift_max_mm) DH.drift_max_mm = +d.toFixed(2);
    if (d > 0.4) {                                     /* 超过 0.4mm 才算在滑 */
      modelRoot.position.x -= dx;
      modelRoot.position.z -= dz;
      var fw2 = dhFootWorld();
      if (fw2) _lastFootWorld.copy(fw2);
    } else {
      _lastFootWorld.copy(fw);
    }
  }
  /* ② 脸部/眼部补光（2026-10-30）：贴在相机上的小补光，专给眼睛高光点。
     挂在相机上 ⇒ 转视角时灯跟着走，不会一转脸就黑。 */
  var faceLight = null;   /* 在 try 之前声明：strict 模式下给未声明变量赋值会抛 ReferenceError，
                             而我原来的 catch{} 把它吞了 ⇒ 读数里 face_light 恒为 null */
  try {
    faceLight = new THREE.PointLight(0xfff1e2, 0.55, 2.4, 2.0);
    faceLight.position.set(0.16, 0.10, 0.30);
    camera.add(faceLight);
    scene.add(camera);
  } catch (eFL) {}

  var CAM = null;                      /* 取景基准（fitCamera 算一次，tick 只做微动） */
  var B = {};                          /* 骨骼名 → Bone */
  var base = {};                       /* 每根要叠加的骨骼：记 idle 姿势基准旋转 */
  var modelRoot = null;
  var clockStart = 0;

  function boneKey(name) {
    /* GLTFLoader 会对节点名做 sanitize（去掉 ':' 等），两种形态都认 */
    return String(name || "").replace(/[^\w\-]/g, "");
  }

  var loader = new THREE.GLTFLoader();
  var USE_INLINE = false;   /* 走了内联兜底就把来源写进回执（不许静默换源） */
  /* 量具用：`?pose=bind` 只看绑定姿势、不播动作（判"模型缺腿"还是"动作把腿带坏了"） */
  var POSE_BIND = (function () {
    try { return /(\?|&)pose=bind/.test(location.search); } catch (e) { return false; }
  })();
  /* 手臂垂放修正：源资产的两段动作是**T 字张开**（实测 bbox 宽 1.665m），对话里像人体模型。
     这里把上臂往身侧拧下来（参数化是为了**量**：`?arms=x|y|z` 三个轴各拍一张再挑）。
     这是"按源码 rig 驱动骨骼"，不是另造一套动作。 */
  var ARMS_AXIS = (function () {
    try {
      var m = /[?&]arms=([xyz])/.exec(location.search);
      return m ? m[1] : null;
    } catch (e) { return null; }
  })();
  var ARMS_AMP = 1.15;

  function onGltf(gltf) {
      modelRoot = gltf.scene || (gltf.scenes && gltf.scenes[0]);
      if (!modelRoot) { S.status = "no-scene"; say("GLB 里没有场景节点", "fault"); return; }

      /* 统一尺度：按包围盒把身高收到 1.72 m，脚底贴 y=0（不同源资产比例不一，硬编码会穿帮） */
      var box = new THREE.Box3().setFromObject(modelRoot);
      var size = new THREE.Vector3(); box.getSize(size);
      if (!isFinite(size.y) || size.y <= 0) { S.status = "bad-bbox"; say("模型包围盒异常（size.y=" + size.y + "）", "fault"); return; }
      var k = 1.72 / size.y;
      modelRoot.scale.multiplyScalar(k);
      box.setFromObject(modelRoot);
      var c = new THREE.Vector3(); box.getCenter(c);
      modelRoot.position.x -= c.x;
      modelRoot.position.z -= c.z;
      modelRoot.position.y -= box.min.y;

      modelRoot.traverse(function (o) {
        if (o.isMesh || o.isSkinnedMesh) {
          o.frustumCulled = false;                 /* 蒙皮网格用静态包围盒会被错误裁掉（真采过的坑） */
          /* ⛔ 2026-10-30 两次实测失败，记在这里免得再撞：
             想把 GLB 的 MeshStandardMaterial 升成 MeshPhysicalMaterial（为了 ior/specularIntensity/
             clearcoat 三条皮肤判据），两种写法都试过：
               ① 在 traverse 回调里就地替换 ⇒ 加载卡死、tris 掉到 12
               ② 遍历只收集、遍历结束后用 new MeshPhysicalMaterial().copy(m) 统一替换
                  ⇒ 仍然 status=loading、tris=2（本 WebKit + three r147 组合不吃）
             结论：这版引擎上不换材质，ior/specular/clearcoat 三条按"该材质类型没有这些属性"如实报，
             不硬凑数字。真要做，得换 three 版本或在 Blender 侧直接导出 physical 材质。 */
          var mats = Array.isArray(o.material) ? o.material : [o.material];
          mats.forEach(function (m) {
            if (!m) return;
            if ("envMapIntensity" in m) m.envMapIntensity = 0.7;
            if ("metalness" in m) m.metalness = 0.0;
            if ("roughness" in m) m.roughness = 0.65;
            if ("ior" in m) m.ior = 1.4;
            if ("specularIntensity" in m) m.specularIntensity = 0.42;
            if ("clearcoat" in m) m.clearcoat = 0.05;
            if ("sheen" in m) m.sheen = 0.12;
            m.needsUpdate = true;
          });
        }
        if (o.isBone) {
          B[o.name] = o;
          B[boneKey(o.name)] = o;
          S.bones += 1;
        }
      });
      S.hasJaw = !!(B["mixamorig:Jaw"] || B["mixamorigJaw"] || B["Jaw"]);

      stage.add(modelRoot);

      var clips = (gltf.animations || []);      window.__DH_CLIPS = gltf.animations || [];
      /* 初始化：把 idle 真正挂上状态机并占满权重（原来只 a.play()，DH 里是空的） */
      if (mixer) {
        var _idle = dhAction("idle");
        if (_idle) { _idle.enabled = true; _idle.setEffectiveWeight(1); _idle.play(); }
        DH.state = "idle"; DH.actions.idle = _idle || DH.actions.idle;
      }

      S.clips = clips.map(function (c) { return c.name + "(" + c.duration.toFixed(2) + "s)"; });
      if (clips.length && !POSE_BIND) {
        mixer = new THREE.AnimationMixer(modelRoot);
        clips.forEach(function (clip) {
          var a = mixer.clipAction(clip);
          if (clip.name === "idle") { actionIdle = a; a.play(); }
          else if (clip.name === "walk") { actionWalk = a; }
        });
        /* 更正（2026-10-19）：上一版这里改写过 idle 的双臂轨道，依据是「量到 bbox 宽 1.665m」。
           那个 1.665m 是 **bind pose（T-pose）的臂展**，不是 idle 的姿势 —— 拿 A 的读数去改 B（P1_判据错尺）。
           真相（`tools/codex-scripts/anim-audit.py` 读 GLB 二进制量出来的）：
             · idle 的 LeftArm/RightArm 只比静止姿势低 62° —— 那是**正常的垂放**，不用改；
             · 真正被自动绑骨扭坏的是 **LeftUpLeg/RightUpLeg 偏离静止姿势 177°**（腿折到胯上），
               已在**资产侧**用 `anim-hipfix.py` 归位（六条自检 + 复读 0.00°）。
           ⇒ 运行时不改写轨道：动作按资产里那份走，页面不偷偷换姿势。 */
        if (!actionIdle && clips[0]) { actionIdle = mixer.clipAction(clips[0]); actionIdle.play(); }
      }

      ["mixamorig:Head", "mixamorig:Neck", "mixamorig:Spine2", "mixamorig:Spine1", "mixamorig:Hips",
       "mixamorig:RightArm", "mixamorig:RightForeArm", "mixamorig:LeftArm", "mixamorig:LeftForeArm"
      ].forEach(function (n) {
        var b = B[n] || B[boneKey(n)];
        if (b) base[n] = b.rotation.clone();
      });

      /* 取景：全身 + 抬手也要留白，脚不许被切 */
      fitCamera(FRAME_H);

      S.ok = true;
      S.status = "ready";
      clockStart = performance.now();
      say("3D 数字人就绪 · 绑骨 " + S.bones + " 根 · 动作 " + (S.clips.length ? S.clips.join(" / ") : "无") +
          " · 源=" + (USE_INLINE ? "内联副本（file:// 直读被拦）" : "assets/dh-v2-rigged.glb") +
          (S.hasJaw ? "" : " · 无口型骨/形态键（「在说」用头颈与手势表示，不假装嘴动）"), "ok");
      resolveReady(true);
  }

  /* 直读失败 → 用派生内联副本（.glb 仍是唯一真源，派生件由 tools/codex-scripts/glb-inline.py 生成并对账） */
  function onLoadFail(err) {
    var first = String(err && (err.message || err.type) || err);
    function fail(why) {
      S.status = "load-failed";
      say("模型载入失败：" + String(why).slice(0, 110) + "（直读原因：" + first.slice(0, 60) + "）", "fault");
      resolveReady(false);
    }
    var s = document.createElement("script");
    s.src = "assets/dh-v2-rigged.glb.b64.js";
    s.onload = function () {
      if (!window.GBT_GLB_B64) { fail("内联副本里没有 GBT_GLB_B64 载荷（形状变了）"); return; }
      try {
        var raw = atob(window.GBT_GLB_B64);
        var buf = new Uint8Array(raw.length);
        for (var i = 0; i < raw.length; i += 1) buf[i] = raw.charCodeAt(i);
        USE_INLINE = true;
        loader.parse(buf.buffer, "assets/", onGltf, function (e2) {
          fail(String(e2 && (e2.message || e2) || e2));
        });
      } catch (e) { fail(String(e && e.message || e)); }
    };
    s.onerror = function () { fail("内联副本也取不到（assets/dh-v2-rigged.glb.b64.js 不在盘上）"); };
    document.head.appendChild(s);
  }

  loader.load("assets/dh-v2-rigged.glb", onGltf, undefined, onLoadFail);

  /* 载完/失败都要能被外部等一次（验收器用） */
  var _readyWaiters = [];
  function resolveReady(ok) { _readyWaiters.splice(0).forEach(function (fn) { try { fn(ok); } catch (e) {} }); }
  S.whenReady = function (fn) {
    if (S.status === "ready" || S.status === "load-failed" || S.status === "no-three") fn(S.ok);
    else _readyWaiters.push(fn);
  };

  /* 取景高度（米）：**一处定义、两处使用**（加载完与 resize 都读它）——免得改了一个忘了另一个（P8）。
     2026-10-19 改口径：原来按 1.46 m（全身 + 抬手余量）取景，那是为"T-pose 张开 1.665 m"留的位置；
     动作修好之后她站直了、臂展 0.65 m，全身取景就变成"面板里一个小人、脸只有指甲盖大"。
     对话剧场要的是**半身特写**（头顶到胯，约 1.06 m），脸才看得清。
     ⚠️ 它在 IIFE 顶层赋值；第 219 行的 `fitCamera(FRAME_H)` 在 onGltf 回调里跑，那时它已经是 1.06。
        谁要是把它挪进 onGltf 内部**之后**，就是 undefined ⇒ 相机 NaN（`var` 只提升声明不提升赋值）。 */
  var FRAME_H = 1.15;
  var FRAME_AIM_Y = 1.30;

  function fitCamera(targetH) {
    var vfov = camera.fov * Math.PI / 180;
    var aspect = camera.aspect || 1;
    var hfov = 2 * Math.atan(Math.tan(vfov / 2) * aspect);
    var needV = targetH / (2 * Math.tan(vfov / 2));
    var needH = 0.52 / (2 * Math.tan(hfov / 2));     /* 横向留出转身/抬手的宽 */
    var dist = Math.max(needV, needH) * 1.10;
    var dir = new THREE.Vector3(0.16, 0.26, 1).normalize();
    var aim = new THREE.Vector3(0, FRAME_AIM_Y, 0);
    camera.position.copy(aim.clone().addScaledVector(dir, dist));
    camera.lookAt(aim);
    CAM = { aim: aim, dist: dist, pos0: camera.position.clone() };
  }

  /* ── 渲染端清晰度（2026-10-30 主人第 3 条）──────────────────────────
     ① SSAA 超采样：按 SSAA 倍率提高 drawing buffer，浏览器降采样回 CSS 尺寸
        —— 零依赖、立刻见效（边缘不再锯齿、细发丝不再断）。
     ② 脸部/眼部补光：一盏贴着相机的小面积补光，专打头部 —— 眼睛要有高光点，
        脸不能靠环境漫反射吃饭。
     ③ 高分辨率出图：exportPNG(scale) 临时放大画布渲染一帧再取 dataURL，出完恢复。
     ─────────────────────────────────────────────────────────────────── */
  var DH_SSAA = 2;                     /* 默认 2× 超采样 */
  /* faceLight 已在上面创建：这里**不能**再赋 null（var 会覆盖前值，实测 face_light 读成 null） */

  function dhApplyPixelRatio() {
    if (!renderer) return;
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    /* 2026-10-30 实测：dpr2 × SSAA2 = 4 ⇒ buffer 7680×4320（3300 万像素），
       WebView 里模型加载被拖到 40 秒以上甚至卡在 loading。
       总倍率封顶 3（≈900 万像素），SSAA 只在还能提的时候才真加。 */
    var total = Math.min(3, Math.max(1, dpr * DH_SSAA));
    renderer.setPixelRatio(total);
  }
  function resize() {
    var w = canvas.clientWidth || 1, h = canvas.clientHeight || 1;
    dhApplyPixelRatio();                       /* ① SSAA：先设倍率再 setSize */
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    if (modelRoot) fitCamera(FRAME_H);
  }
  window.addEventListener("resize", resize);

  /* ── 状态叠加：动作由源码动作播，气质由这里叠（都在 mixr 之后加，不会漂） ── */
  var st = { state: "idle" };
  var smooth = { level: 0, look: 0 };

  function addRot(name, ax, val) {
    var b = B[name] || B[boneKey(name)];
    if (b) b.rotation[ax] += val;
  }

  /* ③ 高分辨率出图：临时放大 pixelRatio 渲一帧取 dataURL，然后恢复。
     不改画布 CSS 尺寸 ⇒ 不动布局；出图分辨率 = CSS 尺寸 × pixelRatio × scale。 */
  function exportPNG(scale) {
    scale = Math.max(1, Math.min(4, Number(scale) || 2));
    if (!renderer) return { ok: false, why: "no-renderer" };
    var w = canvas.clientWidth || 800, h = canvas.clientHeight || 800;
    var oldPR = renderer.getPixelRatio();
    try {
      renderer.setPixelRatio(oldPR * scale);
      renderer.setSize(w, h, false);
      camera.aspect = w / h; camera.updateProjectionMatrix();
      renderer.render(scene, camera);
      var url = canvas.toDataURL("image/png");
      return { ok: true, url: url, scale: scale,
               pixels: [Math.round(w * oldPR * scale), Math.round(h * oldPR * scale)] };
    } catch (eEx) {
      return { ok: false, why: String(eEx && eEx.message || eEx).slice(0, 120) };
    } finally {
      renderer.setPixelRatio(oldPR);
      renderer.setSize(w, h, false);
      camera.aspect = w / h; camera.updateProjectionMatrix();
      renderer.render(scene, camera);
    }
  }

  /* 🔴 2026-10-30 铁证：把"帧驱动到底走到哪一步"记进可读数组 —— 不再靠猜 rAF 为什么不跑。 */
  window.__wfLog = [];
  function _wf(ev, extra) {
    if (window.__wfLog.length < 200) {
      window.__wfLog.push({ at: Date.now(), ev: ev, extra: extra === undefined ? null : extra,
                            timerMode: !!_timerMode, frames: DH.frames });
    }
  }
  _wf('module-init-done');

  function tick(now) {
    _wf('tick');
    var t = (now - clockStart) / 1000;
    if (mixer) mixer.update(0.016);    if (mixer) {
      mixer.update(0.016);
      DH.frames += 1;
      for (var _k in DH.actions) {
        var _a2 = DH.actions[_k];
        DH.weights[_k] = _a2 && _a2.isRunning() ? +(_a2.getEffectiveWeight() || 0).toFixed(3) : 0;
      }
      dhFootLockStep();
    }


    smooth.level += ((st.state === "speak" ? S.level : 0) - smooth.level) * 0.22;

    if (Object.keys(base).length) {
      var nod = 0, tilt = 0, sway = 0, arm = 0;

      if (st.state === "listen") {
        nod = -0.10 + 0.02 * Math.sin(t * 1.1);
        tilt = 0.03 * Math.sin(t * 0.9);
        sway = 0.02 * Math.sin(t * 0.7);
      } else if (st.state === "think") {
        nod = -0.05;
        tilt = 0.09 + 0.01 * Math.sin(t * 0.6);
        sway = 0.03 * Math.sin(t * 0.5);
      } else if (st.state === "speak") {
        nod = 0.055 * Math.sin(t * 7.6) * (0.35 + smooth.level) - 0.02;
        tilt = 0.02 * Math.sin(t * 2.3);
        sway = 0.015 * Math.sin(t * 1.4);
        arm = -(0.16 + 0.30 * smooth.level) * (0.6 + 0.4 * Math.sin(t * 1.7));
      } else {
        nod = 0.012 * Math.sin(t * 1.05);
        sway = 0.012 * Math.sin(t * 0.75);
      }

      addRot("mixamorig:Head", "x", nod);
      addRot("mixamorig:Head", "z", tilt);
      addRot("mixamorig:Neck", "x", nod * 0.5);
      addRot("mixamorig:Spine2", "z", sway);
      addRot("mixamorig:RightArm", "z", arm);
      addRot("mixamorig:RightForeArm", "x", arm * 0.55);

      /* 手臂垂放：源动作是 T 字张开，对话里太像人体模型 ⇒ 先把上臂拧到身侧（左右反号） */
      if (ARMS_AXIS) {
        var sgn = { Left: -1, Right: 1 };
        ["Left", "Right"].forEach(function (side) {
          var bb = B["mixamorig:" + side + "Arm"] || B[boneKey("mixamorig:" + side + "Arm")];
          if (bb) bb.rotation[ARMS_AXIS] += sgn[side] * ARMS_AMP;
          var fa = B["mixamorig:" + side + "ForeArm"] || B[boneKey("mixamorig:" + side + "ForeArm")];
          if (fa) fa.rotation[ARMS_AXIS] += sgn[side] * ARMS_AMP * 0.18;
        });
      }

      /* 说话的轻微"上身起伏"：跟着真音量呼吸，不是固定动画 */
      var b = B["mixamorig:Hips"] || B["mixamorigHips"];
      if (b) b.position.y += 0.004 * smooth.level * Math.sin(t * 6.2);
    }

    /* 🔴 2026-10-18 主人令：「使用她的原生能力触手继续绑定上，让她按照触手想让她这么动就这么动」。
       触手活动流（真账本 audit.jsonl 尾部）→ 手势（`motion.js` 每 2.5s 读 `gbtW3.capActivity`）。
       叠在上面的状态姿态**之上**，不抢状态机；动作层坏了也不许拖垮舞台。 */
    if (window.GBT_MOTION && typeof window.GBT_MOTION.apply === "function") {
      try { window.GBT_MOTION.apply(B); } catch (e) { /* 动作层异常吞掉，舞台照跑 */ }
    }

    /* 相机随状态微推：在听/在想往前一点（同一台机器上的一致性比花哨重要） */
    var targetZ = st.state === "idle" ? 0 : 1;
    smooth.look += (targetZ - smooth.look) * 0.05;
    if (CAM) {
      camera.position.copy(CAM.pos0);
      camera.position.y += 0.010 * Math.sin(t * 0.5);
      camera.lookAt(CAM.aim.x, CAM.aim.y + 0.005 * smooth.look, CAM.aim.z);
    }

    renderer.render(scene, camera);
    S.frames += 1;
    if (!_timerMode) requestAnimationFrame(tick);   /* 定时器兜底时不重复排队 */
  }

  /* 对外接口（真接线，不是占位） */
  window.GBT_DH3D.setState = function (name, blend) {
    return dhSetState(name, blend);       /* 2026-10-30：真交叉淡入，不再只存字符串 */
  };
  window.GBT_DH3D.level = function (v) {
    var x = Number(v);
    S.level = isFinite(x) ? Math.max(0, Math.min(1, x)) : 0;
  };
  /* 量具口（只读；`tools/codex-scripts/dh3d-probe.cjs` 用它量真实包围盒/相机）。
     明确标注：**调试/量具专用**，业务代码不许读它。 */
  window.GBT_DH3D._debug = function () {
    return { scene: scene, model: modelRoot, camera: camera, renderer: renderer, bones: B };
  };
  /* 量具口（只读、确定性）：把动作**拨到指定时刻**再渲染一帧。
     为什么需要：窗口挪到屏幕外时 Chromium 会节流 requestAnimationFrame（实测 2.6s 只走 12 帧），
     量到的姿势取决于"它慢到哪一帧"，同一份资产两次量出两个结果。
     拨钟之后量出来的就是"这段动作在 t 秒时的姿势"，可复现、可对比。
     返回 true = 真的拨了；false = 没有动作（bind 模式）或还没 ready。 */
  /* 🔴 2026-10-30：证明"画面上到底有没有东西"的唯一可靠办法。
     本 WebKit 里 browser screenshot 抓不到 WebGL、canvas.readPixels 又被 JS 桥拒收，
     所以**渲到离屏 RenderTarget 再 readRenderTargetPixels** —— 不依赖合成层、不依赖 preserveDrawingBuffer。
     读数：平均亮度 / 最大值 / 非黑像素占比。人物在画时应明显 > 0，全黑就是 0。 */
  /* A/B 扫参：把「调这个参数画面会怎样」变成对照表，而不是靠肉眼。
     每个候选值都：设参数 → 渲一帧 → 读中心 32×32 像素 → 记录 → 复原。
     返回 [{name, avg, max, non}]，baseline 一定在第一行。 */
  window.GBT_DH3D.ab = function () {
    var R = renderer, SC = scene, CAM = camera, gl = R.getContext();
    var N = 32;
    function stat() {
      R.render(SC, CAM);
      var W = gl.drawingBufferWidth, H = gl.drawingBufferHeight;
      var px = new Uint8Array(N * N * 4);
      gl.readPixels((W - N) >> 1, (H - N) >> 1, N, N, gl.RGBA, gl.UNSIGNED_BYTE, px);
      var s = 0, mx = 0, nb = 0;
      for (var i = 0; i < px.length; i += 4) {
        var v = px[i] + px[i + 1] + px[i + 2];
        s += v; if (v > mx) mx = v; if (v > 12) nb += 1;
      }
      return { avg: Math.round(s / (N * N)), max: mx, non: Math.round(nb / (N * N) * 100) };
    }
    var lights = [], mats = [];
    SC.traverse(function (o) {
      if (o.isLight) lights.push(o);
      if ((o.isMesh || o.isSkinnedMesh) && o.material) {
        (Array.isArray(o.material) ? o.material : [o.material]).forEach(function (m) { if (m) mats.push(m); });
      }
    });
    var out = [{ name: 'baseline' }];
    var b = stat(); out[0].avg = b.avg; out[0].max = b.max; out[0].non = b.non;

    var e0 = R.toneMappingExposure;
    [0.85, 1.2].forEach(function (e) {
      R.toneMappingExposure = e;
      var r = stat(); out.push({ name: 'exposure=' + e, avg: r.avg, max: r.max, non: r.non });
    });
    R.toneMappingExposure = e0;

    var pt = null;
    for (var i = 0; i < lights.length; i++) if (lights[i].type === 'PointLight') { pt = lights[i]; break; }
    if (pt) {
      var i0 = pt.intensity;
      [0.9, 1.3].forEach(function (v) {
        pt.intensity = v;
        var r = stat(); out.push({ name: 'faceLight=' + v, avg: r.avg, max: r.max, non: r.non });
      });
      pt.intensity = i0;
    }
    if (mats.length && ('envMapIntensity' in mats[0])) {
      var v0 = mats[0].envMapIntensity;
      [1.3, 1.8].forEach(function (v) {
        mats.forEach(function (x) { if ('envMapIntensity' in x) x.envMapIntensity = v; });
        var r = stat(); out.push({ name: 'envMap=' + v, avg: r.avg, max: r.max, non: r.non });
      });
      mats.forEach(function (x) { if ('envMapIntensity' in x) x.envMapIntensity = v0; });
    }
    return out;
  };

  window.GBT_DH3D.pixels = function (n) {
    var N = n || 96;
    try {
      var rt = new THREE.WebGLRenderTarget(N, N);
      var old = renderer.getRenderTarget();
      renderer.setRenderTarget(rt);
      renderer.render(scene, camera);
      var buf = new Uint8Array(N * N * 4);
      renderer.readRenderTargetPixels(rt, 0, 0, N, N, buf);
      renderer.setRenderTarget(old);
      rt.dispose();
      var sum = 0, mx = 0, non = 0;
      for (var i = 0; i < buf.length; i += 4) {
        var v = buf[i] + buf[i + 1] + buf[i + 2];
        sum += v; if (v > mx) mx = v;
        if (v > 12) non += 1;
      }
      return { ok: true, n: N, avg: Math.round(sum / (N * N)), max: mx,
               nonblackPct: Math.round(non / (N * N) * 1000) / 10 };
    } catch (e) {
      return { ok: false, err: String(e && e.message || e) };
    }
  };

  window.GBT_DH3D._pose = function (t) {
    if (!mixer) return false;
    try {
      mixer.setTime(Math.max(0, Number(t) || 0));
      scene.updateMatrixWorld(true);
      renderer.render(scene, camera);
      return true;
    } catch (e) { return false; }
  };

  resize();
  requestAnimationFrame(tick);

  /* 🔴 2026-10-30 实测：本 WebView 里 requestAnimationFrame **可能完全不触发**
     （stage3d.html 上 frames 一直是 0、triangles 只有 12 ⇒ 画面是空的）。
     rAF 被节流/禁用时没有别的信号，所以加一道停滞检测：0.8 秒还一帧没走，就切定时器驱动。
     这条只影响"没渲染"的环境，rAF 正常时完全不生效。 */
  var _timerMode = false, _timer = null;
  function goTimer(why) {
    if (_timerMode) return;
    _timerMode = true;
    _wf('goTimer', why);
    _timer = setInterval(function () { try { tick(performance.now()); } catch (e) { _wf('tick-throw', String(e && e.message || e)); } }, 33);
    if (window.console) console.warn("[dh3d] rAF 停摆（" + why + "）⇒ 切定时器驱动");
  }
  (function watchFrames() {
    var last = -1, still = 0;
    setInterval(function () {
      var f = renderer && renderer.info && renderer.info.render ? renderer.info.render.frame : -1;
      if (f === last) { still += 1; if (still >= 2) goTimer("frame 停在 " + f); }
      else { still = 0; last = f; }
      _wf('watch', { frame: f, still: still });
    }, 1000);
  })();
})();
