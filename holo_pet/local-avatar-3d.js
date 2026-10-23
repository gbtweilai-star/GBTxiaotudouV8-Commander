import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const canvas = document.querySelector("#avatar-canvas");
if (canvas) {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(24, 1, 0.01, 100);
  camera.position.set(0, 1.35, 6.4);
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.08;
  // ── IBL 环境（修 AI 味禁令 ❌「无环境光的纯方向光打光」）────────────────
  // 🔴 2026-09-25 修：原来这里**只有半球光 + 两盏方向光**（key 3.4 / rim 2.2 / hemi 2.4），
  //    没有任何环境贴图 ⇒ 皮肤只有方向光的镜面高光、**没有环境的漫反射包裹**，
  //    阴影死黑、整体像 CG。three.js 官方对 MeshPhysicalMaterial 的原话是
  //    "For best results, always specify an environment map"。
  //    RoomEnvironment 是**程序化**影棚环境（不依赖外部 HDRI 文件），离线可跑。
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 1.0;
  // 🔴 光照配比必须跟着压：环境已经承担绝大部分漫反射，方向光留原来的强度会叠爆
  //    （在离线取景器里实测过：黑衣冲成灰褐、皮肤惨白）。影棚口径 —— 主光负责形，
  //    辅光只提暗部，勾边给轮廓，半球光几乎只做底色。
  scene.add(new THREE.HemisphereLight(0xd9f8ff, 0x07101f, 0.30));
  const key = new THREE.DirectionalLight(0xffffff, 1.15);
  key.position.set(2, 4, 4);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x4fe7ff, 0.65);
  rim.position.set(-3, 2, -3);
  scene.add(rim);
  let model;
  let mixer;
  const loader = new GLTFLoader();
  // 🔴 2026-10-10 换代（主人令「我从新绑骨了你替换一下精细点哈」+「记得把旧的清理了」）：
  //    这一版的 `avatar-hd.glb` 是**主人在 Tripo 重新绑骨的成品**转出来的，读数**全部现读**：
  //      · **12.64 MB** · **65 关节**（mixamorig 标准命名，含手指）· 2 段动画 idle/walk
  //      · 机检（tools/codex-scripts/verify-3d-asset.py）：**20,543 面 = 主角量级**（20k–80k 内）·
  //        NORMAL/TEXCOORD_0 齐 · **蒙皮零权重顶点 0 · 每顶点权重和最大偏差 0.000000（归一 True）**
  //      · S8 门：idle 2.00s 闭合差 0.000000 · walk 1.10s 闭合差 0.000000 **步幅比 0.550**（需 0.5–0.8）
  //    ✅ 顺手解掉了上一版**写在下面那条"已知代价"**：54.35 MB → 12.64 MB（**轻 4.3 倍**），
  //       而且**没有减面**（减面那条老路会毁 UV），面板首屏不再被 51 MB 拖住。
  //    ⚠️ 与上一版的差别（如实写，不藏着）：上一版是**自研绑骨 26 关节 + 头发弹簧链**，
  //       这一版是 **Tripo 重绑 65 关节**（头发弹簧链不在了）；上一版 idle 4.0s，这一版 2.0s。
  //    ✅ 旧的 4 份同一 mesh 的重复件（合计 70.6 MB）**已送回收站**，不再各存一份。
  loader.load("./assets/digital-human/raw/rig/avatar-hd.glb", (gltf) => {
    model = gltf.scene;
    const box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    model.position.sub(center);
    model.position.y = -size.y * 0.34;
    model.rotation.y = Math.PI;
    // 🔴 2026-10-10 同一个病的**第三副副本**（前两副在 Blender 那边：清动画≠绑定姿势 · 求值前后差 0.979 vs 0.621）：
    //    这里按 size.y 把人缩到 1.65 —— 而 size 量的是**当前姿势**下的包围盒。
    //    实测同一具模型：**绑定姿势 0.979** vs **动画姿势 0.621** ⇒ 缩放系数差 **1.6 倍**
    //    （1.65/0.979=1.685 vs 1.65/0.621=2.657）⇒ 她在大屏上的大小**会随"什么时候量"而变**。
    //    ⇒ 用**绑定姿势**的高度做基准：GLB 的骨架在解析时就是 bind pose，
    //      所以在**加进场景、还没跑 mixer 之前**量（本行就在 play 之前，顺序是对的），
    //      并写明"这个数必须是 bind pose 的" —— 免得后人在 play 之后再量一次。
    const scale = 1.65 / Math.max(size.y, 0.01);   // ⚠️ size 必须是**绑定姿势**下量的（见上）
    model.scale.setScalar(scale);
    scene.add(model);
    if (gltf.animations.length) {
      // 🔴 2026-10-10 修（与 Blender 那边**同一个病**的第三副副本：对象没搞清就下手）：
      //    原写法按**下标**取 gltf.animations[0] —— 顺序是 GLB 里的事，不该按下标赌。
      //    现在顺序恰好是 ['idle','walk'] 所以看着对；**顺序一变成 [walk, idle]，她就会原地走**。
      //    ⇒ 按**名字**取 idle，取不到再退回第一条（退路要留，但不能把退路当主路）。
      mixer = new THREE.AnimationMixer(model);
      const idle = THREE.AnimationClip.findByName(gltf.animations, "idle")
        || gltf.animations[0];
      mixer.clipAction(idle).play();
      console.log("[local-avatar-3d] 动画取自:", idle.name || "(无名·按下标退回第一条)");
    }
    document.body.dataset.localAvatar3d = "ready";
    console.log("[local-avatar-3d] loaded", JSON.stringify({ animations: gltf.animations.length, height: size.y, scale }));
  }, undefined, (error) => {
    document.body.dataset.localAvatar3d = "failed";
    const reason = document.querySelector("#fallback-reason");
    if (reason) reason.textContent = "本地三维模型加载失败";
    console.error("[local-avatar-3d] GLB load failed", error);
  });
  const clock = new THREE.Clock();
  function resize() {
    const rect = canvas.parentElement.getBoundingClientRect();
    const width = Math.max(1, rect.width);
    const height = Math.max(1, rect.height - 80);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(canvas.parentElement);
  resize();
  function frame() {
    const elapsed = clock.getElapsedTime();
    if (mixer) mixer.update(Math.min(clock.getDelta(), 0.05));
    if (model) {
      model.rotation.y = Math.sin(elapsed * 0.42) * 0.045;
      model.position.x = Math.sin(elapsed * 0.8) * 0.015;
    }
    renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }
  frame();
}
