/* ═══════════════════════════════════════════════════════════════════════════
   companion.js · 她一个人（holo_pet 桌面 App 版）

   主人令（2026-10-20）：「数字人一个人出现在 APP 面板，可以随意走动在任何一页上面，美观拉满」
                       ＋「她自己会走，我也能拖着放哪都行」。

   与 DSH 浮层的区别：那边是**浏览器**，装不了 12 MB 模型也没有 three.js ⇒ 用立绘；
   这边是 **Electron**，本仓已经有 three.js + `avatar-hd.glb`（65 关节 · idle/walk 两段动画）
   ⇒ 用真模型，走路由 `walk` 驱动，是真肢体而不是贴纸位移。

   为什么单独一件（不放 app.js 里）：app.js 是 154 KB 主控，前面任一 electron 桥报错都会让后面整段不执行；
   她是门面，必须自己活自己的。

   挂法：index.html 末尾
     <script type="module" src="./companion.js"></script>
   依赖 index.html 里的 importmap（"three" / "three/addons/"）。
   ═══════════════════════════════════════════════════════════════════════════ */
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

// 🔴 2026-10-20 修：模型路径原来是**相对页面**的（./assets/...），挂到 assets/*/index.html 这类子页会 404。
//    改成相对**脚本自身**（import.meta.url）：不管她在哪一页，找的都是 holo_pet/assets/... 那一份。
const HERE = new URL(".", import.meta.url);
const MODEL = new URL("assets/digital-human/raw/rig/avatar-hd.glb", HERE).href;
const HEIGHT = 1.65;          // 目标身高（米），与 local-avatar-3d.js 同一口径
const SPEED = 0.055;          // 每秒走多少视口宽（约 6%/s，走一趟 8 秒左右）
const IDLE_MS = 5200;         // 站多久再走
const BAND = [3, 12];         // 落脚高度带（vh，离底）

function boot() {
  if (document.querySelector("[data-gbt-companion]")) return;

  const root = document.createElement("div");
  root.className = "gbt-cmp";
  root.setAttribute("data-gbt-companion", "3d");
  root.innerHTML =
    '<div class="gbt-cmp__fig" data-role="fig">' +
    '<canvas class="gbt-cmp__canvas" data-role="canvas"></canvas>' +
    '<div class="gbt-cmp__shadow"></div>' +
    '<div class="gbt-cmp__bubble" data-role="bubble"></div>' +
    '<div class="gbt-cmp__hint">DRAG ME</div>' +
    "</div>";
  document.body.appendChild(root);

  const fig = root.querySelector('[data-role="fig"]');
  const canvas = root.querySelector('[data-role="canvas"]');
  const bubble = root.querySelector('[data-role="bubble"]');

  // 语音：悬停出现的小麦克风。点了才去问本机耳朵桥（tools/digihuman/ear-server.py，只监听回环）。
  const earBtn = document.createElement("button");
  earBtn.type = "button";
  earBtn.className = "gbt-cmp__mic";
  earBtn.title = "说一句（走过来 / 停下 / 挥挥手 / 转一圈 / 跳一下 / 点头 / 摇头）";
  earBtn.textContent = "🎤";

  // 瑜伽教学入口：点一下换下一式（悬停才出现，不挡画面）
  const yogaBtn = document.createElement("button");
  yogaBtn.type = "button";
  yogaBtn.className = "gbt-cmp__mic gbt-cmp__yoga";
  yogaBtn.title = "瑜伽教学：点一下换下一式（树式 / 战士二式 / 举手伸展）";
  yogaBtn.textContent = "🧘";
  fig.appendChild(yogaBtn);
  fig.appendChild(earBtn);
  const EAR = "http://127.0.0.1:8770/listen?seconds=6";

  // ── 三渲二：透明底 + 与主舞台同一套 IBL（不额外造第二套打光口径）──────────
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.18;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(24, 1, 0.01, 100);
  // 2026-10-20 收紧取景：原来 5.2 的位置把人拍成了中间一小块（截图实测）
  camera.position.set(0, 1.02, 3.15);
  camera.lookAt(0, 0.86, 0);

  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 1.0;
  scene.add(new THREE.HemisphereLight(0xd9f8ff, 0x07101f, 0.30));
  const key = new THREE.DirectionalLight(0xffffff, 1.15);
  key.position.set(2, 4, 4);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x4fe7ff, 0.65);
  rim.position.set(-3, 2, -3);
  scene.add(rim);
  // 补一盏正面柔光：主题是深色底，只有 key+rim 时她整个人糊在黑里（截图实测）
  const fill = new THREE.DirectionalLight(0xffffff, 0.85);
  fill.position.set(-1.4, 1.3, 3.4);
  scene.add(fill);

  let model = null;
  let mixer = null;
  let baseY = 0;
  let idleAction = null;
  let walkAction = null;

  new GLTFLoader().load(MODEL, (gltf) => {
    model = gltf.scene;
    const box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    model.position.sub(center);
    model.position.y = -size.y * 0.34;
    model.rotation.y = -Math.PI / 2;       // -90° = 正面朝镜头（实测，见 FRONT_YAW 注记）
    // 用**绑定姿势**（mixer.play 之前）量高度，别在动画姿势下量 —— 同一具模量出来能差 1.6 倍
    model.scale.setScalar(HEIGHT / Math.max(size.y, 0.01));
    scene.add(model);

    mixer = new THREE.AnimationMixer(model);
    // 🔴🔴 2026-10-20 亲眼看定的根因（隔离台 state/lab-none.png vs lab-idle.png / lab-walk.png）：
    //    **这具 GLB 静止姿势是干净的**（黑金紧身衣 + 长靴 + T-pose，四肢齐全、比例正常），
    //    可它自带的 `idle` / `walk` 两段 clip **一播就把骨架甩烂**：
    //      · idle → 腿翻到头顶、手臂横飞，成了"四肢乱插的怪物"；
    //      · walk → 同上，而且把 Hips 整体位移，人直接飘出画面。
    //    上一版只验证了"clips 存在、骨头能被写"，没看画面 ⇒ 一条典型的**判据错尺假绿**（P1/P7）。
    //    结论：**不播这两段 clip**，待机与走路全部程序化（见 procedural()）。
    const idleClip = THREE.AnimationClip.findByName(gltf.animations, "idle") || null;
    const walkClip = THREE.AnimationClip.findByName(gltf.animations, "walk") || null;
    fig.dataset.brokenClips = [idleClip && "idle", walkClip && "walk"].filter(Boolean).join(",");
    idleAction = null;                       // 刻意不建 Action：建了就会有人 play 它
    walkAction = null;
    baseY = model.position.y;
    fig.classList.add("is-ready");
    // 🔴 2026-10-20 实测（CDP 真等 15 秒后问的，不是猜）：只加 .is-ready 类时
    //    getComputedStyle(fig).opacity 依然是 "0" —— 她一直隐形。
    //    内联样式优先级最高，这里直接写死，不再依赖"类 + 过渡"这条链。
    fig.style.opacity = "1";
    headBone = findHead(model);
    model.traverse((o) => { if (o.isBone && o.name) bones[bkey(o.name)] = o; });
    console.log("[companion] 骨骼收集", Object.keys(bones).length, "节（含手指）",
      "示例=", Object.keys(bones).filter((k) => /index1$/.test(k)).join(","));
    fig.dataset.clips = gltf.animations.map((a) => a.name).join(",");
    applyPose("rest");                       // 立起程序化待机（手臂放下），不依赖任何 clip
    window.__gbtCompanion = api;                     // 自检/自动化口子
    console.log("[companion] 模型就绪 clips=", fig.dataset.clips, "（不播，见 CLIPS 注记）");
  }, undefined, (err) => {
    fig.dataset.failed = "1";
    console.error("[companion] 模型加载失败", err);
  });

  // ── 巡游状态：位置用**视口百分比**（跨窗口尺寸都不用重算）──────────────────
  const st = {
    x: 0.16, y: 7,          // 当前（x=视口宽比例，y=vh）
    tx: 0.16, ty: 7,
    walking: false,
    held: false,
    face: -1,
  };
  const SPOTS = [0.10, 0.20, 0.30, 0.42, 0.54, 0.66, 0.78, 0.88];
  let yawHold = null;                          // 非 null 时钉住朝向（只给量具/自动化用）
  // 🔴 实测（state/only-y-090.png）：这具模的"正面朝镜头"是 yaw = -90°，不是 0。
  //    0 时是侧面（双肩沿 z 排开），π 是背面。
  const FRONT_YAW = -Math.PI / 2;

  // 🔴 2026-10-20 加：**她在说什么**必须能被机器读到。
  //    原来气泡只写进 DOM，自动化只能靠"看起来有字"判断，一步念错也看不出来（P1 一类假绿）。
  let lastSaid = "";
  function setBubble(text) {
    bubble.textContent = text;
    bubble.classList.toggle("is-on", !!text);
  }
  function pickNext() {
    const t = SPOTS[Math.floor(Math.random() * SPOTS.length)];
    st.tx = Math.abs(t - st.x) < 0.06 ? SPOTS[Math.floor(Math.random() * SPOTS.length)] : t;
    st.ty = BAND[0] + Math.random() * (BAND[1] - BAND[0]);
    st.face = st.tx >= st.x ? 1 : -1;
    st.walking = true;
  }

  // 走：每秒推进，落点用「够近即停」，不靠定时器猜
  let last = performance.now();
  let idleTimer = 0;

  function tick(now) {
    const dt = Math.min(0.06, (now - last) / 1000);
    last = now;
    if (mixer) mixer.update(dt);

    if (!st.held) {
      const dx = st.tx - st.x;
      if (st.walking && Math.abs(dx) > 0.004) {
        st.x += Math.sign(dx) * Math.min(Math.abs(dx), SPEED * dt);
        st.y += (st.ty - st.y) * Math.min(1, dt * 2.2);
      } else if (st.walking) {
        st.walking = false;
        idleTimer = now + IDLE_MS;
      } else if (now > idleTimer && idleTimer !== 0) {
        pickNext();
      }
    }

    // 动画权重：走 = walk 1 / idle 0，站 = 反之（交叉一点，不硬切）
    if (walkAction && idleAction) {
      const want = st.walking ? 1 : 0;
      walkAction.weight += (want - walkAction.weight) * Math.min(1, dt * 6);
      idleAction.weight = 1 - walkAction.weight;
    }
    if (model) {
      // 🔴 2026-10-20 实测纠正（CDP 量关节世界坐标，不是看感觉）：
      //    原来"朝左/朝右"是给整身 +180°（`π + (face>0?0:π)`）⇒ 她在**一半时间里把后背给用户**。
      //    而且 π 这一侧量出来 shoulderLx<0 ⇒ 那正是**背对镜头**的那一半（作者注释写的"面朝镜头"是反的）。
      //    改成：站住时 yaw=0（正面朝用户）；走起来只侧身 ±0.56 rad（32°），像人走路侧身，不像转身离开。
      //    插值必须**走最短弧**（atan2 归一化），否则 2π 与 0 之间会绕一整圈。
      const faceY = yawHold !== null ? yawHold : (FRONT_YAW + (st.walking ? st.face * 0.5 : 0));
      let dYaw = faceY - model.rotation.y;
      dYaw = Math.atan2(Math.sin(dYaw), Math.cos(dYaw));
      model.rotation.y += dYaw * Math.min(1, dt * 5);
      const hop = st.walking ? Math.abs(Math.sin(now / 120)) * 0.012
                : (body.mode === "dance" ? Math.abs(Math.sin(now / 220)) * 0.030 : 0);
      model.position.y = baseY - (body.mode === "sit" ? SIT_DROP : 0) + hop;
    }

    fig.style.left = (st.x * 100).toFixed(2) + "%";
    fig.style.bottom = st.y.toFixed(2) + "vh";
    stepPose();
    procedural(now);
    applyGesture(now);
    fig.classList.toggle("is-walk", st.walking);
    renderer.render(scene, camera);
    requestAnimationFrame(tick);
  }

  // ── 拖拽：抓住就停在手上，松手站住等 IDLE_MS 再自己走 ────────────────────
  fig.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    const rect = fig.getBoundingClientRect();
    const offX = e.clientX - (rect.left + rect.width / 2);
    st.held = true;
    st.walking = false;
    try { fig.setPointerCapture(e.pointerId); } catch (_) { /* 忽略 */ }
    const move = (ev) => {
      st.x = Math.min(0.95, Math.max(0.03, (ev.clientX - offX) / window.innerWidth));
      st.y = Math.min(45, Math.max(1, ((window.innerHeight - ev.clientY) / window.innerHeight) * 100));
      if (model) model.rotation.y = -Math.PI / 2;   // 被拎起来时正面朝镜头
    };
    const up = () => {
      st.held = false;
      idleTimer = performance.now() + IDLE_MS;
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  });

  fig.addEventListener("click", () => {
    const words = ["嗯？", "我在呢～", "要我陪你吗？", "我在听。", "你叫我？"];
    setBubble(words[Math.floor(Math.random() * words.length)]);
    fig.classList.add("is-waving");
    setTimeout(() => fig.classList.remove("is-waving"), 2200);
    setTimeout(() => setBubble(""), 4200);
  });

  // ── 手指级手势库 ─────────────────────────────────────────────────────────
  // 骨架实测（从 GLB 的 nodes 里读出来的，不是猜）：mixamorig:LeftHandThumb1..4 /
  //   Index1..4 / Middle1..4 / Ring1..4 / Pinky1..4 —— 每只手 20 节，双手 40 节。
  // 曲指角度按「每节递减」给（近节最大、末节最小），这样看着像手指自己弯，不是整根折断。
  const bones = {};
  // 🔴 2026-10-20 实测假绿：GLB 里名字是 `mixamorig:RightHandIndex1`，但 three.js 的 GLTFLoader
  //    会 sanitize 节点名（`:` 等被去掉）⇒ 按原名查 `bones['mixamorig:...']` 永远 undefined，
  //    于是"手势返回 true 但一个骨头都没动"。这里统一用**归一化键**（去非字母数字 + 小写）查。
  const bkey = (n) => String(n || "").replace(/[^A-Za-z0-9]/g, "").toLowerCase();
  const FINGERS = ["Thumb", "Index", "Middle", "Ring", "Pinky"];
  // 曲指幅度（弧度）：第 1/2/3 节。拇指方向不同，单独一套
  const CURL4 = [0.55, 0.45, 0.35];
  const CURLT = [0.30, 0.26, 0.22];
  const GEST = {
    open: { thumb: 0, others: 0 },                       // 张开
    fist: { thumb: 1, others: 1 },                       // 握拳
    point: { thumb: 1, keep: ["Index"] },                // 只伸食指
    peace: { thumb: 1, keep: ["Index", "Middle"] },      // 剪刀手
    thumbsup: { thumb: 0, others: 1, thumbOut: true },   // 点赞
    cup: { thumb: 0.3, others: 0.25, axis: "x" },        // 掌心微窝（接东西）
  };
  const gestureState = { name: "" };

  function boneList(side) {
    const out = [];
    for (const f of FINGERS) {
      for (let i = 1; i <= 3; i++) {
        const b = bones[bkey("mixamorig:" + side + "Hand" + f + i)];
        if (b) out.push({ finger: f, idx: i, bone: b });
      }
    }
    return out;
  }

  function applyHand(name) {
    const g = GEST[name];
    if (!g) return false;
    const axis = g.axis || "z";
    let applied = 0;
    for (const side of ["Left", "Right"]) {
      for (const f of boneList(side)) {
        const keep = g.keep || [];
        let amt = 0;
        if (f.finger === "Thumb") {
          amt = g.thumbOut ? (f.idx === 1 ? -0.5 : 0.15) : (g.thumb || 0);
          amt *= CURLT[f.idx - 1];
        } else if (keep.indexOf(f.finger) >= 0) {
          amt = 0;
        } else {
          amt = (g.others === undefined ? 0 : g.others) * CURL4[f.idx - 1];
        }
        f.bone.rotation[axis] = amt;
        applied += 1;
      }
    }
    gestureState.name = applied ? name : "";
    gestureState.applied = applied;
    if (!applied) console.error("[companion] 手势 " + name + " 一个骨头都没设上（查名失败）");
    return applied > 0;
  }

  // ── 体位库（瑜伽/伸展）：骨骼目标角 → tick 里平滑趋近 ────────────────────
  // 🔴 口径先说清：这是**动作级**示范（肢体大致到位），不是医疗/解剖级对齐；
  //    这具模型的手是低模，别指望近景手指细节（见全程记录 §26）。
  //    轴与符号是**试出来的**：mixamo 骨架在 three.js 里，抬臂≈Arm 的 Z 轴（左右反号），
  //    屈腿≈UpLeg 的 Z + Leg 的 X。摆完必须读骨角度 + 截图确认，不许"看着差不多"。
  const POSES = {
    rest: {},
    // 树式：双臂上举、右腿屈起（脚掌贴左小腿）
    tree: {
      LeftArm: [-1.40, 0, 0.30], RightArm: [-1.40, 0, -0.30],
      LeftForeArm: [0, 0, 0.25], RightForeArm: [0, 0, -0.25],
      RightUpLeg: [0, 0, -0.35], RightLeg: [-1.15, 0, 0],
      Spine1: [0.02, 0, 0], Head: [-0.05, 0, 0],
    },
    // 战士二式：双臂平举、双腿分开
    warrior2: {
      LeftArm: [-1.30, 0, 0.55], RightArm: [-1.30, 0, -0.55],
      LeftForeArm: [0, 0, 0.05], RightForeArm: [0, 0, -0.05],
      LeftUpLeg: [0, 0, 0.30], RightUpLeg: [0, 0, -0.30],
      LeftLeg: [0.18, 0, 0], RightLeg: [0.18, 0, 0],
      Head: [0, 0.35, 0],
    },
    // 举手伸展：双臂上举 + 脊柱轻微后仰
    reachUp: {
      LeftArm: [-1.55, 0, 0.20], RightArm: [-1.55, 0, -0.20],
      LeftForeArm: [0, 0, 0.10], RightForeArm: [0, 0, -0.10],
      Spine1: [-0.10, 0, 0], Spine2: [-0.08, 0, 0], Head: [-0.12, 0, 0],
    },
  };
  // 坐下（2026-10-20 解出来的角度）：判据 = 腿弯上去把脚抬高了 0.16 m，
  // 所以根节点同时降 0.16 m，脚仍踩在原来的地面上、髋真的低下去。
  // 角度是量出来的（判据 = 大腿水平、小腿竖直、脚回到原地）：
  //   UpLeg −1.4 ⇒ 膝 (y0.627, z0.488) 与髋同高；Leg −1.6 ⇒ 脚 (y0.240, z0.543) 在膝正下方 0.387。
  //   脚被抬高了 0.46 m ⇒ 根节点降 0.46 m，脚回到 −0.22 的地面，髋落到 0.17（坐在矮凳上的高度）。
  POSES.sit = {
    LeftUpLeg: [-1.4, 0, 0], RightUpLeg: [-1.4, 0, 0],
    LeftLeg: [-1.6, 0, 0], RightLeg: [-1.6, 0, 0],
    Spine1: [0.06, 0, 0],
  };

  // ── 瑜伽课表：3 个体位 × 分解步骤（顺序即教学顺序，可循环、可切换）────────────
  const YOGA = [
    { pose: "tree", name: "树式", steps: [
      "站直，双脚踩实，肩膀放松。",
      "重心移到左脚，右脚掌贴到左小腿内侧。",
      "双手合十举过头顶，眼睛看前方一点。",
      "稳住呼吸，保持 5 个呼吸再慢慢放下。" ] },
    { pose: "warrior2", name: "战士二式", steps: [
      "双脚分开约一条腿长，右脚外转 90 度。",
      "弯曲右膝，让膝盖对着脚尖方向。",
      "双臂向两侧平举，与地面平行。",
      "头转向右手方向，保持平稳呼吸。" ] },
    { pose: "reachUp", name: "举手伸展", steps: [
      "双脚并拢站直，脊柱向上延伸。",
      "吸气，双臂从两侧慢慢举过头顶。",
      "胸口微开、肩膀下沉，不要耸肩。",
      "呼气放松还原，重复三次。" ] },
  ];
  const yogaState = { idx: -1, step: -1 };
  // 自动往下讲：一个 🧘 按钮只能走"一步"，那不叫教 —— 教学必须自己一步一步念下去，人只负责跟。
  // 定时器句柄统一管在这里：换式/停止时一次清干净，免得上一式的计时器把这一式的步骤念乱。
  const yogaPlay = { timers: [], on: false };
  function yogaClearPlay() {
    for (const t of yogaPlay.timers) clearTimeout(t);
    yogaPlay.timers.length = 0;
    yogaPlay.on = false;
  }

  const poseTarget = {};                      // boneName(归一化) -> [x,y,z]
  const poseState = { name: "rest", applied: 0 };

  function boneWorld(name) {
    const b = bones[bkey(name)];
    if (!b) return null;
    const p = new THREE.Vector3(); b.getWorldPosition(p);
    return { x: +p.x.toFixed(4), y: +p.y.toFixed(4), z: +p.z.toFixed(4) };
  }
  // 世界坐标「瞄准」：把一根骨指向某个世界点（骨自身轴沿子骨方向），再把解出的欧拉角交给 tick 保持。
  // 为什么不是手写欧拉角：**这具模型的绑定姿势本来就是双手过顶**（实测手 y=1.56 > 头 y=1.13），
  // 照 T-pose 假设写的角度反而把手臂压成横举 —— 树式念着"双手合十举过头顶"、手上却没有，就是这么来的。
  function aimBone(boneName, tx, ty, tz) {
    const k = bkey(boneName);
    const b = bones[k];
    if (!b || !b.children || !b.children.length) return false;
    const p = new THREE.Vector3(); b.getWorldPosition(p);
    const c = new THREE.Vector3(); b.children[0].getWorldPosition(c);
    const cur = c.clone().sub(p);
    const want = new THREE.Vector3(tx, ty, tz).sub(p);
    if (cur.lengthSq() < 1e-10 || want.lengthSq() < 1e-10) return false;
    cur.normalize(); want.normalize();
    const pq = new THREE.Quaternion(); b.parent.getWorldQuaternion(pq);
    const qw = new THREE.Quaternion().setFromUnitVectors(cur, want);
    const local = pq.clone().invert().multiply(qw).multiply(pq);
    b.quaternion.premultiply(local);
    b.updateMatrixWorld(true);
    const e = new THREE.Euler().setFromQuaternion(b.quaternion, "XYZ");
    poseTarget[k] = [e.x, e.y, e.z];
    return true;
  }
  // 回到**绑定姿势**：GLB 静止姿势是干净的（黑金装 + 长靴 + T-pose），
  // 这是一切程序化姿势的起点（自带动画不能用，见上面 CLIPS 注记）。
  const bindRot = {};                    // 绑定姿势下每根骨的角度（衰减要落到这里，不是落到 0）
  function resetToBind() {
    let n = 0;
    if (model) {
      model.traverse((o) => { if (o.isSkinnedMesh && o.skeleton) { o.skeleton.pose(); n += 1 } });
      model.updateMatrixWorld(true);
    }
    // 🔴 2026-10-20 实测根因：`stepPose()` 对"没被体位指定的骨"是**衰减到 0**，
    //    可锁骨（Shoulder）在绑定姿势里根本不是 0 —— 衰减把肩关节挪了位，
    //    于是同一组手臂角度在"刚设完"和"跑一秒后"量出两个完全不同的手位置（左手从髋侧甩到体侧 19cm）。
    for (const k of Object.keys(bones)) {
      const b = bones[k];
      bindRot[k] = [b.rotation.x, b.rotation.y, b.rotation.z];
    }
    return n;
  }
  // 待机手臂：把手从 T-pose 放到髋侧。
  // 这四个角度是**三轴坐标下降解出来的**（判据 = 手掌世界坐标到髋侧目标点的距离，不是"看着像"）：
  //   左手 (0.102, 0.692, 0.048) 距目标 3.0mm · 右手 (-0.104, 0.688, 0.054) 距 6.5mm。
  // 为什么不用瞄准法：同一套 aim 在左臂上会把手甩到体侧 19cm 外（实测 0.188 vs 目标 0.06），
  // 右臂却是对的 —— 这具骨架左右不对称，瞄准法只保证方向、不保证落点。
  const IDLE_ARMS = {
    LeftArm: [-2.325, -0.425, -0.6], LeftForeArm: [1.225, 0.45, 0.713],
    RightArm: [-1.95, 1.137, 0.45], RightForeArm: [-0.787, 0.375, -0.675],
  };
  function applyIdleArms() {
    let n = 0;
    for (const name of Object.keys(IDLE_ARMS)) {
      const key = bkey("mixamorig:" + name);
      const b = bones[key];
      const a = IDLE_ARMS[name];
      if (!b || !a) continue;
      poseTarget[key] = a;
      b.rotation.set(a[0], a[1], a[2]);
      n += 1;
    }
    return n;
  }
  // 「手要举过头顶」的体位改成瞄准式：目标点相对头/肩给，模型换了也不会跑偏。  // 四个数（ex/ey/dx/up）是**扫出来的**，不是估的：判据 = 手掌世界坐标到目标点的距离。
  // 只瞄前臂时手会甩过头（双手间距 18cm，看着没合十）；把肘往内收 4cm、压低到 +0.16 后
  // 双手落到 ±2.8cm（间距约 5.6cm），且仍高过 Head 骨 0.33 —— 见 state/cdp-elbow-sweep2.mjs 读数。
  const AIM_POSES = {
    tree: { dx: 0.02, up: 0.36, fwd: 0.06, ex: -0.04, ey: 0.16 },
    reachUp: { dx: 0.03, up: 0.38, fwd: 0.03, ex: -0.03, ey: 0.18 },
  };
  function aimArms(A) {
    const head = boneWorld("mixamorig:Head");
    const sl = boneWorld("mixamorig:LeftArm");
    const sr = boneWorld("mixamorig:RightArm");
    if (!head || !sl || !sr) return 0;
    const sgnL = sl.x >= 0 ? 1 : -1;          // 左臂在世界 x 的符号（量出来的，不假设）
    let n = 0;
    if (aimBone("mixamorig:LeftArm", sl.x + sgnL * A.ex, sl.y + A.ey, sl.z + A.fwd * 0.3)) n += 1;
    if (aimBone("mixamorig:LeftForeArm", sgnL * A.dx, head.y + A.up, A.fwd)) n += 1;
    if (aimBone("mixamorig:RightArm", sr.x - sgnL * A.ex, sr.y + A.ey, sr.z + A.fwd * 0.3)) n += 1;
    if (aimBone("mixamorig:RightForeArm", -sgnL * A.dx, head.y + A.up, A.fwd)) n += 1;
    return n;
  }

  function snapAll() {                        // 立即到位（机检/教学开局用，不等平滑）
    for (const k of Object.keys(poseTarget)) {
      const b = bones[k];
      const t = poseTarget[k];
      if (b) b.rotation.set(t[0], t[1], t[2]);
    }
  }

  function applyPose(name) {
    const P = POSES[name];
    if (!P) return false;
    if (body.mode !== "rest" && name !== "sit" && name !== "rest") body.mode = "rest";   // 换姿势就别再坐着（rest/sit 自己管模式）

    for (const k of Object.keys(poseTarget)) delete poseTarget[k];
    // 🔴 2026-10-20 实测第二层真因：`mixer.timeScale = 0` 只是"时间不走"，**它每帧仍把这帧姿势写回骨骼**，
    //    于是我把 LeftArm 设成 1.40，下一帧又被动画写回 0.18。摆体位前必须 `stopAllAction()`，
    //    回 rest 时再把 idle 挂回去。
    if (mixer) mixer.stopAllAction();
    if (name === "rest") {
      // 没有可用 clip 可回退（见 CLIPS 注记）：rest = 干净绑定姿势 + 两条手臂放下
      resetToBind();
      const na = applyIdleArms();
      poseState.name = "rest"; poseState.applied = na;
      snapshotIdleBase();
      return na > 0;
    }
    let n = 0;
    for (const bone of Object.keys(P)) {
      const b = bones[bkey("mixamorig:" + bone)];
      if (!b) continue;
      poseTarget[bkey("mixamorig:" + bone)] = P[bone];
      n += 1;
    }
    // 瞄准式体位必须**从确定姿势起算**：先把列出的角度直接落到位（跟 poseNow 一样），再瞄手。
    // 否则解出来的角度取决于上一帧停在哪（同一个体位两次读数不一样 —— P5 一类）。
    if (AIM_POSES[name]) {
      for (const k of Object.keys(poseTarget)) {
        const b = bones[k];
        const t = poseTarget[k];
        if (b) b.rotation.set(t[0], t[1], t[2]);
      }
      if (model) model.updateMatrixWorld(true);
    }
    poseState.name = n ? name : "rest";
    poseState.applied = n;
    if (!n) console.error("[companion] 体位 " + name + " 一根骨头都没对上");
    const AP = AIM_POSES[name];
    if (AP) {
      const a = aimArms(AP);
      if (!a) console.error("[companion] 体位 " + name + " 的举手瞄准一条都没对上");
      poseState.applied = n + a;
    }
    return n > 0;
  }

  // ── 手臂手势（比心 / 鼓掌 / 抱抱）：手要**到胸前**，靠"先算胸点、再瞄手"而不是写死欧拉角 ──
  //    胸点 = 双肩中点 + 前方向 0.14 - 上方向 0.06；前/右/上 三个方向每帧从关节现算，
  //    所以她转身、走路侧身时手也不会甩到背后去（写死角度就会）。
  const ag = { type: "", t0: 0, dur: 0 };
  function frameAxes() {
    const hip = boneWorld("mixamorig:Hips") || boneWorld("mixamorig:Hip");
    const head = boneWorld("mixamorig:Head");
    const sl = boneWorld("mixamorig:LeftArm");
    const sr = boneWorld("mixamorig:RightArm");
    if (!hip || !head || !sl || !sr) return null;
    const nrm = (v) => { const L = Math.hypot(v.x, v.y, v.z) || 1; return { x: v.x / L, y: v.y / L, z: v.z / L }; };
    const up = nrm({ x: head.x - hip.x, y: head.y - hip.y, z: head.z - hip.z });
    const right = nrm({ x: sl.x - sr.x, y: sl.y - sr.y, z: sl.z - sr.z });
    const cross = (a, b) => ({ x: a.y * b.z - a.z * b.y, y: a.z * b.x - a.x * b.z, z: a.x * b.y - a.y * b.x });
    let fwd = nrm(cross(right, up));
    const mid = { x: (sl.x + sr.x) / 2, y: (sl.y + sr.y) / 2, z: (sl.z + sr.z) / 2 };
    // 两个候选方向互为反向：取"朝镜头"的那个（她绝大多数时间是面向用户的）
    const toCam = { x: camera.position.x - mid.x, y: camera.position.y - mid.y, z: camera.position.z - mid.z };
    if (fwd.x * toCam.x + fwd.y * toCam.y + fwd.z * toCam.z < 0) fwd = { x: -fwd.x, y: -fwd.y, z: -fwd.z };
    const chest = { x: mid.x + fwd.x * 0.14, y: mid.y - 0.06, z: mid.z + fwd.z * 0.14 };
    return { chest, fwd, right, up };
  }
  function handsToChest(spread) {
    const A = frameAxes();
    if (!A) return false;
    const L = { x: A.chest.x + A.right.x * spread, y: A.chest.y, z: A.chest.z + A.right.z * spread };
    const R = { x: A.chest.x - A.right.x * spread, y: A.chest.y, z: A.chest.z - A.right.z * spread };
    const sl = boneWorld("mixamorig:LeftArm");
    const sr = boneWorld("mixamorig:RightArm");
    if (!sl || !sr) return false;
    const sgnL = sl.x >= 0 ? 1 : -1;
    aimBone("mixamorig:LeftArm", sl.x + sgnL * 0.09, sl.y - 0.14, sl.z + A.fwd.z * 0.05);
    aimBone("mixamorig:RightArm", sr.x - sgnL * 0.09, sr.y - 0.14, sr.z + A.fwd.z * 0.05);
    // 只瞄一次是"方向对、落点不对"：手掌在骨**末端**，直接瞄目标会甩过头（实测比心双手还差 15 cm）。
    // 这里做 3 次"量误差→把目标反向挪同样距离"的修正，落点才真的到胸口。
    const aimHand = (fore, hand, t) => {
      let tg = { ...t };
      for (let i = 0; i < 3; i += 1) {
        aimBone(fore, tg.x, tg.y, tg.z);
        const h = boneWorld(hand);
        if (!h) return;
        tg = { x: tg.x - (h.x - t.x), y: tg.y - (h.y - t.y), z: tg.z - (h.z - t.z) };
      }
    };
    aimHand("mixamorig:LeftForeArm", "mixamorig:LeftHand", L);
    aimHand("mixamorig:RightForeArm", "mixamorig:RightHand", R);
    return true;
  }
  function armGesture(now) {
    if (!ag.type) return;
    const p = Math.min(1, (now - ag.t0) / ag.dur);
    if (ag.type === "clap")      handsToChest(0.02 + Math.abs(Math.sin(now / 90)) * 0.10);
    else if (ag.type === "heart") handsToChest(0.03);
    else if (ag.type === "hug")  handsToChest(0.05 + (1 - Math.min(1, p * 1.6)) * 0.42);  // 张开 → 合上
    if (p >= 1) { ag.type = ""; applyPose("rest"); }
  }

  // 身体模式：rest（站着待机）/ sit（坐着）/ dance（跳一段）
  // 为什么要状态：待机那套是"每帧按时间写腿"，坐着时腿的角度必须由体位库保持，
  // 两种写入者同时改同一批骨头 = 谁最后写谁赢，画面会抖（这正是"看着不对劲"最常见的来源）。
  const body = { mode: "rest", until: 0 };
  const SIT_DROP = 0.46;   // 与 POSES.sit 那一组角度配套（脚抬高多少就降多少）

  // ── 程序化待机/步态：GLB 自带的 idle / walk 一播就把骨架甩烂（见 CLIPS 注记），
  //    所以呼吸、走路摆腿全部按时间自己算，叠在"手臂放下"的待机姿势上。
  let idleBase = null;
  function snapshotIdleBase() {
    const get = (n) => { const b = bones[bkey(n)]; return b ? [b.rotation.x, b.rotation.y, b.rotation.z] : null; };
    idleBase = {
      spine1: get("mixamorig:Spine1"),
      spine2: get("mixamorig:Spine2") || get("mixamorig:Spine1"),
      head: get("mixamorig:Head"),
      lUpLeg: get("mixamorig:LeftUpLeg"), rUpLeg: get("mixamorig:RightUpLeg"),
      lLeg: get("mixamorig:LeftLeg"), rLeg: get("mixamorig:RightLeg"),
      hips: get("mixamorig:Hips") || get("mixamorig:Hip"),
    };
  }
  function procedural(now) {
    if (!idleBase) return;
    if (ag.type) { armGesture(now); return; }         // 手臂手势进行中：这几根骨由它接管
    const br = Math.sin(now / 1700) * 0.020;            // 呼吸（约 3.4 秒一循环）
    const sd = Math.sin(now / 2900) * 0.012;            // 重心左右晃
    const put = (name, base, dx, dy, dz) => {
      if (!base) return;
      const k = bkey(name);
      if (!bones[k]) return;
      poseTarget[k] = [base[0] + dx, base[1] + dy, base[2] + dz];
    };
    put("mixamorig:Spine2", idleBase.spine2, br, sd * 0.4, sd * 0.6);
    put("mixamorig:Head", idleBase.head, -br * 0.7, sd * 1.4, -sd * 0.3);

    if (body.mode === "sit") return;                 // 坐着：腿交给体位库，别再按时间写

    if (body.mode === "dance" && now > body.until) {      // 跳到点自己收（不用外面的计时器）
      body.mode = "rest";
      applyPose("rest");
      api.say("跳完啦～");
    }
    if (body.mode === "dance") {
      const ph = now / 260;
      const sw = Math.sin(ph);
      put("mixamorig:Hips", idleBase.hips, 0, 0, sw * 0.12);
      put("mixamorig:Spine2", idleBase.spine2, br, 0, -sw * 0.10);
      put("mixamorig:Head", idleBase.head, Math.sin(ph * 2) * 0.05, -sw * 0.18, 0);
      const la = IDLE_ARMS.LeftArm, ra = IDLE_ARMS.RightArm;
      poseTarget[bkey("mixamorig:LeftArm")] = [la[0] + sw * 0.40, la[1], la[2]];
      poseTarget[bkey("mixamorig:RightArm")] = [ra[0] - sw * 0.40, ra[1], ra[2]];
      put("mixamorig:LeftUpLeg", idleBase.lUpLeg, Math.max(0, sw) * 0.10, 0, 0);
      put("mixamorig:RightUpLeg", idleBase.rUpLeg, Math.max(0, -sw) * 0.10, 0, 0);
      return;
    }
    if (st.walking) {
      const ph = now / 240;
      const amp = 0.18;                                  // 0.34 太大：腿会往两边劈（截图实测）
      put("mixamorig:LeftUpLeg", idleBase.lUpLeg, Math.sin(ph) * amp, 0, 0);
      put("mixamorig:RightUpLeg", idleBase.rUpLeg, -Math.sin(ph) * amp, 0, 0);
      put("mixamorig:LeftLeg", idleBase.lLeg, Math.max(0, -Math.sin(ph)) * 0.30, 0, 0);
      put("mixamorig:RightLeg", idleBase.rLeg, Math.max(0, Math.sin(ph)) * 0.30, 0, 0);
      // 走路不能只有腿在动：手臂**反相**摆（同侧腿在前时同侧臂在后），上身再前倾一点点。
      // 之前只有腿动、手臂钉在髋侧 —— 远看像"平移"，这就是"不自然"最直观的一条。
      const la = IDLE_ARMS.LeftArm, ra = IDLE_ARMS.RightArm;
      poseTarget[bkey("mixamorig:LeftArm")] = [la[0] - Math.sin(ph) * 0.22, la[1], la[2]];
      poseTarget[bkey("mixamorig:RightArm")] = [ra[0] + Math.sin(ph) * 0.22, ra[1], ra[2]];
      put("mixamorig:Spine1", idleBase.spine1, 0.05, 0, 0);
    } else if (idleBase.lUpLeg) {
      put("mixamorig:LeftUpLeg", idleBase.lUpLeg, 0, 0, 0);   // 站住：腿回待机
      put("mixamorig:RightUpLeg", idleBase.rUpLeg, 0, 0, 0);
      put("mixamorig:LeftLeg", idleBase.lLeg, 0, 0, 0);
      put("mixamorig:RightLeg", idleBase.rLeg, 0, 0, 0);
    }
  }

  function stepPose() {
    // 每帧向目标角平滑趋近（0.14 系数）；没被指定的骨回 0
    const A = 0.14;
    for (const k of Object.keys(bones)) {
      const b = bones[k];
      const t = poseTarget[k];
      if (t) {
        b.rotation.x += (t[0] - b.rotation.x) * A;
        b.rotation.y += (t[1] - b.rotation.y) * A;
        b.rotation.z += (t[2] - b.rotation.z) * A;
      } else {
        const b0 = bindRot[k];
        if (!b0) continue;
        b.rotation.x += (b0[0] - b.rotation.x) * A;
        b.rotation.y += (b0[1] - b.rotation.y) * A;
        b.rotation.z += (b0[2] - b.rotation.z) * A;
      }
    }
  }

  // ── 程序化手势：全部作用在**骨骼/根节点**上，不是 CSS 贴纸 ──────────────
  // 🔴 现有 GLB 只有 idle/walk 两段动画；其余动作要么程序化（本段），要么等接入更多 clip。
  //    这里实现的是真旋转/真位移，能被 CDP 读到数值，不靠"看起来像"。
  const g = { type: "", t0: 0, dur: 0 };
  let headBone = null;
  function findHead(scene3) {
    let found = null;
    scene3.traverse((o) => {
      if (!found && o.isBone && /head/i.test(o.name || "")) found = o;
    });
    return found;
  }
  function gesture(type) {
    const D = { spin: 1300, jump: 900, nod: 1100, shake: 1200 }[type];
    if (!D) return false;
    g.type = type; g.t0 = performance.now(); g.dur = D;
    return true;
  }
  function applyGesture(now) {
    if (!g.type || !model) return;
    const p = Math.min(1, (now - g.t0) / g.dur);
    const fade = Math.sin(Math.PI * p);
    if (g.type === "spin") {
      model.rotation.y = -Math.PI / 2 + Math.PI * 2 * p;   // 从正面起转一整圈再回正面
    } else if (g.type === "jump") {
      model.position.y = baseY + 0.16 * fade;
    } else if (g.type === "nod" && headBone) {
      headBone.rotation.x = 0.30 * Math.sin(Math.PI * 2 * p);
    } else if (g.type === "shake" && headBone) {
      headBone.rotation.y = 0.34 * Math.sin(Math.PI * 2 * p);
    }
    if (p >= 1) { g.type = ""; if (headBone) { headBone.rotation.x = 0; headBone.rotation.y = 0; } }
  }

  const api = {
    where: () => ({ x: st.x, y: st.y, walking: st.walking }),
    go: (x) => { st.tx = Math.max(0.03, Math.min(0.95, x)); st.face = st.tx >= st.x ? 1 : -1; st.walking = true; idleTimer = 0; },
    stop: () => { st.walking = false; st.tx = st.x; idleTimer = performance.now() + IDLE_MS; },
    wave: () => fig.click(),
    say: (t) => { lastSaid = String(t || ""); setBubble(lastSaid); return lastSaid; },
    lastSaid: () => lastSaid,
    clips: () => (fig.dataset.clips || ""),
    // 一个动作名进来，她真的动（能被自动化测到状态变化）
    do: (action) => {
      const A = String(action || "");
      if (A === "come") { api.go(0.5); api.say("来了～"); return true; }
      if (A === "stop") { api.stop(); api.say("好，我停住。"); return true; }
      if (A === "wave") { api.wave(); return true; }
      const H = { fist: "fist", open: "open", point: "point", peace: "peace",
                  thumbsup: "thumbsup", cup: "cup" };
      if (H[A] && applyHand(H[A])) { api.say({ fist: "握好了。", thumbsup: "给你点赞！",
        peace: "✌️", point: "看这边。", cup: "给我吧。", open: "手张开。" }[A] || ""); return true; }
      if (gesture(A)) { api.say({ spin: "转一圈～", jump: "跳！", nod: "嗯嗯。", shake: "不是哦。" }[A] || ""); return true; }
      if (A === "sit") {
        body.mode = "sit"; applyPose("sit"); snapAll();
        api.view("sit");          // 坐着时人是矮的：full 机位会把她挤到画框下沿、腿还被切掉
        api.say("坐下了。"); return true;
      }
      if (A === "stand") {
        body.mode = "rest"; applyPose("rest");
        api.view("full");
        api.say("站起来了。"); return true;
      }
      if (A === "dance") {
        body.mode = "dance"; body.until = performance.now() + 6000;
        applyPose("rest"); api.say("来一段～"); return true;
      }
      if (A === "heart" || A === "clap" || A === "hug") {
        const D = { heart: 4000, clap: 2600, hug: 2200 }[A];
        ag.type = A; ag.t0 = performance.now(); ag.dur = D;
        applyHand(A === "heart" ? "cup" : "open");     // 比心手微窝、鼓掌/抱抱张掌
        api.say({ heart: "给你比个心。", clap: "鼓掌～", hug: "抱抱。" }[A]);
        return true;
      }
      api.say("没听清～");
      return false;
    },
    // 🔴 2026-10-20 实测：同一句「走过来」的 conf 五次采样 = 0.456/0.491/0.591/0.597/0.630，
    //    正好绕在 0.55 门槛上（约六成能过）。**不在判据上作弊**（降门槛会让负例更好混进来），
    //    改在交互层：被拒就**自动再听一次**，两次都不过才告诉她"没听清"。
    //    粗算：单次通过率 ~0.6 ⇒ 两次至少一次过 ≈ 1-0.4² ≈ 84%。
    // 第二个参数 wav：给机检用（桥的 /listen?wav=<绝对路径> 可以直接吃文件，不必有麦）。
    // 这条口子让"识别→动作"能端到端真跑，而不是只测识别器本身。
    hear: async (seconds, wav) => {
      const one = async () => {
        const url = "http://127.0.0.1:8770/listen?seconds=" + (seconds || 6)
          + (wav ? "&wav=" + encodeURIComponent(wav) : "");
        const r = await fetch(url, { cache: "no-store" });
        return await r.json();
      };
      try {
        let j = await one();
        if (!j || !j.ok) { api.say("没听清～再说一遍？"); return { ok: false, why: (j && j.why) || "没听清" }; }
        if (!j.accepted) {
          api.say("再听一次…");
          j = await one();
          if (!j || !j.accepted) {
            api.say("没听清（" + ((j && j.why) || "置信度不够") + "）");
            return j || { ok: false, why: "没听清" };
          }
        }
        api.do(j.action);
        return j;
      } catch (err) {
        api.say("耳朵没开：先跑 tools/digihuman/ear-server.py");
        return { ok: false, why: String((err && err.message) || err) };
      }
    },
    gesture: (t) => gesture(t),
    // 手指级：open/fist/point/peace/thumbsup/cup
    hand: (n) => applyHand(n),
    handState: () => gestureState.name,
    handApplied: () => gestureState.applied || 0,
    boneCount: () => Object.keys(bones).length,
    boneRot: (name, axis) => {
      const b = bones[bkey(name)];
      return b ? Number(b.rotation[axis || "z"].toFixed(4)) : null;
    },
    // 一根骨的完整欧拉角（XYZ，弧度）：解出来的姿势要**抄回体位库**时必须读全三轴
    boneEuler: (name) => {
      const b = bones[bkey(name)];
      return b ? { x: +b.rotation.x.toFixed(3), y: +b.rotation.y.toFixed(3), z: +b.rotation.z.toFixed(3) } : null;
    },
    // 探针口（只给自动化用）：写**一根骨**的目标角，并同步进 poseTarget，
    // 这样 tick 的平滑不会把它拉回去（否则读数与截图会被下一帧改掉）。
    // 判姿态只信 worldPos 的坐标，不信"看着像"（P1：判据用错尺就是假绿）。
    setBone: (name, x, y, z) => {
      const k = bkey(name);
      const b = bones[k];
      if (!b) return false;
      b.rotation.set(x || 0, y || 0, z || 0);
      poseTarget[k] = [x || 0, y || 0, z || 0];
      return true;
    },
    worldPos: (name) => boneWorld(name),
    // 回到**绑定姿势**（skeleton.pose()）：用来区分"她本来就歪"还是"动画把她带歪了"
    bindPose: () => {
      if (mixer) mixer.stopAllAction();
      const n = resetToBind();
      for (const k of Object.keys(poseTarget)) delete poseTarget[k];
      poseState.name = "rest"; poseState.applied = 0;
      return n;
    },
    stopMixer: () => { if (mixer) mixer.stopAllAction(); return true; },
    // 朝向（自动化口）：0 = 正面朝用户；±1 = 走起来朝那边侧身
    face: (dir) => { st.face = dir >= 0 ? 1 : -1; st.walking = false; idleTimer = 0; return st.face; },
    // 量朝向用：把 yaw 钉住（null 放开），tick 不再自动改她
    yaw: (v) => { yawHold = v === null || v === undefined ? null : Number(v); return yawHold; },
    hipRot: () => {
      const b = bones[bkey("mixamorig:Hips")] || bones[bkey("mixamorig:Hip")];
      return b ? { x: +b.rotation.x.toFixed(3), y: +b.rotation.y.toFixed(3), z: +b.rotation.z.toFixed(3) } : null;
    },
    rootRot: () => (model ? { x: +model.rotation.x.toFixed(3), y: +model.rotation.y.toFixed(3), z: +model.rotation.z.toFixed(3) } : null),
    // 世界坐标「瞄准」：把一根骨**指向**某个世界点（骨自身 Y 轴沿子骨方向）。
    // 为什么不是解欧拉角：三轴自由解出来的手能到位，但**肘部朝向是乱的**（截图实测：手贴在脑后、肘外翻）。
    // 瞄准式只回答"这根骨该指哪"，天然落在同一个平面里，动作才像人。
    // 世界坐标「瞄准」（同一份实现在 aimBone，体位库用它解"举手过顶"）
    aim: (boneName, tx, ty, tz) => aimBone(boneName, tx, ty, tz),
    // 机位：'full' 整身 / 'hand' 看手
    // 🔴 2026-10-20 修：上一版手部机位是**我估的数字**（0.55,1.30,1.05），截图里根本没框住手。
    //    改成**按手骨的真实世界坐标**定位：先取 RightHand 的 getWorldPosition，再在它前面 0.42、
    //    略高 0.05 处放相机；这样模型缩放/姿势一变也不会跑偏。
    view: (mode) => {
      if (mode === "hand") {
        const hb = bones[bkey("mixamorig:RightHand")] || bones[bkey("mixamorig:LeftHand")];
        if (hb) {
          const p = new THREE.Vector3();
          hb.getWorldPosition(p);
          camera.position.set(p.x + 0.10, p.y + 0.06, p.z + 0.40);
          camera.lookAt(p.x, p.y, p.z);
          fig.dataset.handAt = [p.x.toFixed(3), p.y.toFixed(3), p.z.toFixed(3)].join(",");
        } else {
          camera.position.set(0, 1.2, 0.9);
          camera.lookAt(0, 1.0, 0);
        }
      } else if (mode === "sit") {
        // 坐着时人是"矮一头"的：机位必须跟着降低、拉近，否则她会被挤到画框最下面、腿还被切掉
        camera.position.set(0, 0.52, 3.0);
        camera.lookAt(0, 0.40, 0.15);
      } else if (mode === "whole") {
        // 看全身：原来的 full 机位（z=3.15 / 视线 0.86）会把头和脚切掉，
        // 验"站得直不直、有没有多出来的肢体"必须拉远看整身。
        camera.position.set(0, 0.95, 4.9);
        camera.lookAt(0, 0.88, 0);
      } else {
        camera.position.set(0, 1.02, 3.15);
        camera.lookAt(0, 0.86, 0);
      }
      camera.updateProjectionMatrix();
      fig.dataset.view = mode || "full";
      return fig.dataset.view;
    },
    handCenter: () => fig.dataset.handAt || null,
    // 冻结动画：拍手指细节必须先把 walk/idle 停住，否则手一直在动、机位跟着乱跑
    // （2026-10-20 实测：两次读数手的世界坐标从 (-0.011,1.160,-0.382) 跳到 (0.038,0.218,0.109)）
    pose: (n) => applyPose(n),
    // ── 瑜伽教学：换个体位 → 说步骤 → 可循环/可切换 ──────────────────────
    yoga: (i) => {
      yogaClearPlay();                                     // 换式即停旧播放，防上一式的计时器继续念
      const k = ((i % YOGA.length) + YOGA.length) % YOGA.length;
      const it = YOGA[k];
      applyPose(it.pose);
      for (const key of Object.keys(poseTarget)) {          // 立即到位，便于读数验证
        const b = bones[key]; const t = poseTarget[key];
        if (b) { b.rotation.x = t[0]; b.rotation.y = t[1]; b.rotation.z = t[2]; }
      }
      yogaState.idx = k; yogaState.step = 0;
      api.say("第 " + (k + 1) + " 式 · " + it.name + "：" + it.steps[0]);
      return { idx: k, name: it.name, steps: it.steps.length, pose: api.poseState() };
    },
    yogaNext: () => api.yoga((yogaState.idx < 0 ? 0 : yogaState.idx + 1)),
    yogaStep: () => {
      if (yogaState.idx < 0) return null;
      const it = YOGA[yogaState.idx];
      yogaState.step = (yogaState.step + 1) % it.steps.length;
      api.say(it.steps[yogaState.step]);
      return { idx: yogaState.idx, step: yogaState.step, say: it.steps[yogaState.step] };
    },
    yogaStop: () => {
      yogaClearPlay();
      yogaState.idx = -1; yogaState.step = -1;
      applyPose("rest"); api.say("好，我们到这里，慢慢放松。");
      return { stopped: true, pose: api.poseState() };
    },
    // 🎬 自动教学：进这一式、立刻到位、然后**自己**一步一步念下去（默认 2600ms/步）。
    //    为什么不是让外面轮询 yogaStep：一轮一步的节奏由外面决定，页面一卡就断；
    //    而且真实用户点的是按钮，不是控制台。播放态要能被读到（yogaPlaying / yogaState.on）。
    yogaPlay: (i) => {
      yogaClearPlay();
      const k = ((i % YOGA.length) + YOGA.length) % YOGA.length;
      api.yoga(k);                                  // 体位 + 第一步立刻说（yoga 内部会再清一次，幂等）
      const it = YOGA[k];
      const MS = 2600;
      for (let s = 1; s < it.steps.length; s += 1) {
        yogaPlay.timers.push(setTimeout(() => {
          if (yogaState.idx !== k) return;           // 中途换了式/停了 ⇒ 旧计时器不再念
          yogaState.step = s;
          api.say(it.steps[s]);
        }, MS * s));
      }
      yogaPlay.timers.push(setTimeout(() => { yogaPlay.on = false; }, MS * it.steps.length));
      yogaPlay.on = true;
      return { playing: true, idx: k, name: it.name, steps: it.steps.length, stepMs: MS,
               totalMs: MS * it.steps.length, pose: api.poseState() };
    },
    yogaPlaying: () => yogaPlay.on,
    yogaStopAll: () => { yogaClearPlay(); return api.yogaStop(); },
    // 🎓 完整一节课（目标口径原文：「先完整示范一个体位，再分解讲步骤、可循环、可切换下一个动作」）：
    //    0s     先给**完整式样**看两秒半（真人教学也是先做一个完整的给人看）
    //    2.6s   开始分解：第 1..N 步，每步 2.6s
    //    然后   说"跟着我，再来一遍" + 第二遍步骤（可循环）
    //    结束   说"做完啦"，播放态归 false；再点 🧘 = 下一式（可切换）
    //    中途换式/停止：`yogaState.idx !== k` 让整段旧计划作废，不会串台。
    yogaTeach: (i) => {
      yogaClearPlay();
      const k = ((i % YOGA.length) + YOGA.length) % YOGA.length;
      const it = YOGA[k];
      const MS = 2600;
      yogaState.idx = k; yogaState.step = -1;
      applyPose(it.pose);
      snapAll();
      api.say("先看一遍完整的「" + it.name + "」。");
      const at = (ms, fn) => yogaPlay.timers.push(setTimeout(() => {
        if (yogaState.idx !== k) return;
        fn();
      }, ms));
      let t = MS;
      for (let round = 0; round < 2; round += 1) {
        if (round === 1) { at(t, () => api.say("跟着我，再来一遍。")); t += MS; }
        for (let s = 0; s < it.steps.length; s += 1) {
          at(t, () => { yogaState.step = s; api.say(it.steps[s]); });
          t += MS;
        }
      }
      at(t, () => { yogaPlay.on = false; api.say("做完啦。想换下一式，就再点一下。"); });
      yogaPlay.on = true;
      return { teaching: true, idx: k, name: it.name, steps: it.steps.length, rounds: 2,
               totalMs: t, pose: api.poseState() };
    },
    yogaState: () => ({ ...yogaState, on: yogaPlay.on, pose: poseState.name, list: YOGA.map((y) => y.name) }),
    // 立即到位（不平滑）：无头环境里 rAF 被节流，平滑 900ms 才走 2 帧 ⇒ 机检必须用这个口
    poseNow: (n) => {
      if (!applyPose(n)) return false;
      for (const k of Object.keys(poseTarget)) {
        const b = bones[k]; const t = poseTarget[k];
        if (b) { b.rotation.x = t[0]; b.rotation.y = t[1]; b.rotation.z = t[2]; }
      }
      return true;
    },
    poseTargets: () => Object.keys(poseTarget).length,
    poseState: () => ({ name: poseState.name, applied: poseState.applied }),
    // 教学：先完整示范一次 → 再分解步骤（每步一句话）→ 循环两遍
    teach: (name, steps) => {
      if (!POSES[name]) return false;
      api.say("先看一遍完整的「" + name + "」。");
      applyPose(name);
      const script = (steps && steps.length ? steps : [
        { p: "rest", s: "第一步：站直，脚掌踩实，肩膀放松。" },
        { p: "reachUp", s: "第二步：双臂慢慢举过头顶，掌心相对。" },
        { p: name, s: "第三步：进入体位，保持呼吸，不要憋气。" },
      ]);
      let t = 2600;
      for (const it of script) {
        setTimeout(() => { applyPose(it.p); api.say(it.s); }, t);
        t += 2400;
      }
      setTimeout(() => { applyPose("rest"); api.say("做完啦，跟着我再走一遍。"); }, t);
      return true;
    },
    freeze: (on) => {
      const z = on === false ? 1 : 0;
      if (mixer) mixer.timeScale = z;
      if (z === 0) { st.walking = false; idleTimer = 0; }
      fig.dataset.frozen = z === 0 ? "1" : "0";
      return fig.dataset.frozen;
    },
    rect: () => {
      const r = fig.getBoundingClientRect();
      return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
    },
  };

  yogaBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    // 点一下 = **开始教**（自动一步步念完），不是"给我看下一步"。
    // 正在播就停（同一个按钮做开关，页面上不堆第二个键）。
    if (api.yogaPlaying()) { api.yogaStopAll(); return; }
    const cur = api.yogaState().idx;
    api.yogaTeach(cur < 0 ? 0 : cur + 1);        // 点一下 = 完整教一节（示范→分解→循环）
  });

  earBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    setBubble("我在听…");
    api.hear(6);
  });

  function resize() {
    const r = fig.getBoundingClientRect();
    const w = Math.max(1, Math.round(r.width));
    const h = Math.max(1, Math.round(r.height));
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(fig);
  resize();
  requestAnimationFrame(tick);
  idleTimer = performance.now() + IDLE_MS;
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot, { once: true });
} else {
  boot();
}
