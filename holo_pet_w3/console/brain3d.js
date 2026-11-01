/* GBT小土豆V8 · 大脑执行层（Three.js）
 * 参考主人给的视频：中心蓝色脑核 + 对称曲面管道绕成闭环 + 末端橙色发光节点 + 同心线圈。
 * 数据映射（不是装饰）：
 *   · 中心 = 大脑（本机指挥官）；
 *   · 7 条对称臂 = chain_kernel 七步执行路径（-1 邻域感知 → 5 报告），每臂带步名标签；
 *   · 末端橙色节点 = 该步的证据落点（读到的读数/账本）；
 *   · 同心线圈 = 审计闭环（每步都要留痕，绕回中心）；
 *   · 每步上 3 个橙色小节点 = 该步当前的能力位/事件数（按 chain_kernel 实际步骤静态映射）。
 * 交互：OrbitControls 拖拽旋转/滚轮缩放；Bloom 辉光；诚实标记 data-brain3d。
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

document.documentElement.dataset.brain3d = "imported";

const STEPS = [
  { step: -1, name: "邻域感知" },
  { step: 0, name: "理解" },
  { step: 1, name: "计划" },
  { step: 2, name: "执行" },
  { step: 3, name: "验证" },
  { step: 4, name: "固化" },
  { step: 5, name: "报告" },
];

let renderer, scene, camera, controls, composer, bloom;
let inited = false, running = false, raf = 0, group;

function has3d() {
  const c = document.getElementById("brain3d-canvas");
  if (!c) return null;
  try { return c.getContext("webgl2") || c.getContext("webgl"); } catch (e) { return null; }
}

function glowSprite(color, size, opacity) {
  const c = document.createElement("canvas");
  c.width = 128; c.height = 128;
  const ctx = c.getContext("2d");
  const g = ctx.createRadialGradient(64, 64, 2, 64, 64, 62);
  g.addColorStop(0, "rgba(255,255,255,.95)");
  g.addColorStop(0.3, "rgba(255,255,255,.25)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g; ctx.fillRect(0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(c);
  const m = new THREE.SpriteMaterial({ map: tex, color: color, transparent: true,
    blending: THREE.AdditiveBlending, depthWrite: false, opacity: opacity || 0.9 });
  const s = new THREE.Sprite(m);
  s.scale.set(size, size, 1);
  return s;
}

function label(text, color) {
  const c = document.createElement("canvas");
  c.width = 512; c.height = 96;
  const ctx = c.getContext("2d");
  ctx.font = "600 40px 'JetBrains Mono', monospace";
  ctx.fillStyle = color; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(text, 256, 48);
  const tex = new THREE.CanvasTexture(c);
  tex.minFilter = THREE.LinearFilter;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
  sp.scale.set(3.0, 0.56, 1);
  return sp;
}

function init() {
  if (inited) return true;
  const canvas = document.getElementById("brain3d-canvas");
  try {
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true,
      preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x03070d, 0.012);
    camera = new THREE.PerspectiveCamera(46, 1, 0.1, 400);
    camera.position.set(0, 4.5, 22);
    group = new THREE.Group();
    scene.add(group);

    // ── 中心脑核：蓝色发光（她的头像贴上去）──
    const core = new THREE.Mesh(new THREE.SphereGeometry(1.35, 40, 40),
      new THREE.MeshBasicMaterial({ color: 0x2f7fff }));
    group.add(core);
    const coreGlow = glowSprite(0x4f8cff, 7.5, 0.55);
    group.add(coreGlow);
    const avatarTex = new THREE.TextureLoader().load("../../icons/avatar.png");
    const face = new THREE.Mesh(new THREE.SphereGeometry(1.36, 40, 40),
      new THREE.MeshBasicMaterial({ map: avatarTex, color: 0xffffff, transparent: true, opacity: 0.92 }));
    face.renderOrder = 50;
    group.add(face);

    const tubeMat = new THREE.MeshStandardMaterial({
      color: 0x9fb3d1, metalness: 0.85, roughness: 0.28,
      emissive: 0x1b2c4a, emissiveIntensity: 0.6 });
    const nodeMat = new THREE.MeshStandardMaterial({
      color: 0xff8a2a, emissive: 0xff6a00, emissiveIntensity: 1.2,
      metalness: 0.3, roughness: 0.35 });
    const ringMat = new THREE.MeshStandardMaterial({
      color: 0x8fa6c4, metalness: 0.8, roughness: 0.3,
      emissive: 0x14213a, emissiveIntensity: 0.5 });

    const N = STEPS.length;
    STEPS.forEach(function (st, i) {
      const a = (i / N) * Math.PI * 2;
      const arm = new THREE.Group();
      arm.rotation.z = a;
      group.add(arm);

      // 主臂曲线：外绕一圈再回到中心上方（参考图那种闭环曲面）
      const pts = [
        new THREE.Vector3(0.0, 0.0, 0.0),
        new THREE.Vector3(1.6, 1.3, 0.0),
        new THREE.Vector3(4.4, 2.6, 0.0),
        new THREE.Vector3(6.4, 1.2, 0.0),
        new THREE.Vector3(5.4, -1.4, 0.0),
        new THREE.Vector3(2.4, -2.0, 0.0),
        new THREE.Vector3(0.0, -0.25, 0.0),
      ];
      const curve = new THREE.CatmullRomCurve3(pts, false, "catmullrom", 0.5);
      const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 140, 0.055, 10, false), tubeMat);
      arm.add(tube);

      // 第二根细管（并行神经束）
      const pts2 = pts.map(function (p, k) {
        return p.clone().add(new THREE.Vector3(0, 0.28 * Math.sin(k * 1.7), 0.35));
      });
      const curve2 = new THREE.CatmullRomCurve3(pts2, false, "catmullrom", 0.5);
      arm.add(new THREE.Mesh(new THREE.TubeGeometry(curve2, 140, 0.028, 8, false), tubeMat));

      // 末端橙色节点
      const end = pts[3];
      const node = new THREE.Mesh(new THREE.SphereGeometry(0.32, 24, 24), nodeMat);
      node.position.copy(end);
      arm.add(node);
      arm.add((function () { const g = glowSprite(0xff8a2a, 1.5, 0.85); g.position.copy(end); return g; })());

      // 末端同心线圈（参考图里那种盘绕环）
      for (let r = 0; r < 3; r++) {
        const ring = new THREE.Mesh(new THREE.TorusGeometry(0.55 + r * 0.22, 0.012, 8, 64),
          ringMat);
        ring.position.copy(end);
        ring.rotation.x = Math.PI / 2;
        ring.rotation.y = r * 0.35;
        arm.add(ring);
      }

      // 臂上 3 个橙色小节点（该步的证据落点）
      [1, 2, 4].forEach(function (k) {
        const p = curve.getPointAt(k / 6);
        const n = new THREE.Mesh(new THREE.SphereGeometry(0.13, 16, 16), nodeMat);
        n.position.copy(p);
        arm.add(n);
      });

      // 步名标签（外端）
      const lb = label(st.step + " · " + st.name, "#ffd8a8");
      lb.position.copy(end).add(new THREE.Vector3(0, 0.85, 0));
      arm.add(lb);
    });

    // 外圈星尘
    const DUST = 1400;
    const arr = new Float32Array(DUST * 3);
    for (let i = 0; i < DUST; i++) {
      const r = 12 + Math.random() * 30;
      const th = Math.random() * Math.PI * 2, ph = Math.acos(2 * Math.random() - 1);
      arr[i * 3] = r * Math.sin(ph) * Math.cos(th);
      arr[i * 3 + 1] = r * Math.cos(ph) * 0.7;
      arr[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th);
    }
    const dg = new THREE.BufferGeometry();
    dg.setAttribute("position", new THREE.BufferAttribute(arr, 3));
    scene.add(new THREE.Points(dg, new THREE.PointsMaterial({
      color: 0x8fa6c4, size: 0.09, transparent: true, opacity: 0.4, depthWrite: false })));

    scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const l1 = new THREE.PointLight(0x4f8cff, 3.0, 60); group.add(l1);
    const l2 = new THREE.PointLight(0xff8a2a, 1.6, 60); l2.position.set(6, 3, 4); group.add(l2);

    const wrap = document.querySelector(".view-brain") || canvas;
    controls = new OrbitControls(camera, wrap);
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.35;
    controls.enablePan = false;
    controls.minDistance = 8;
    controls.maxDistance = 50;
    controls.rotateSpeed = 0.75;

    composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.62, 0.55, 0.6);
    composer.addPass(bloom);

    resize();
    inited = true;
    document.documentElement.dataset.brain3d = "ok:" + N + "臂+审计环";
    draw();
    return true;
  } catch (e) {
    document.documentElement.dataset.brain3d = "error:" + String((e && e.message) || e).slice(0, 120);
    return false;
  }
}

function resize() {
  const c = document.getElementById("brain3d-canvas");
  if (!c || !renderer) return;
  const w = c.clientWidth || 600, h = c.clientHeight || 400;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  if (composer) composer.setSize(w, h);
  if (bloom) bloom.resolution.set(w, h);
}

function draw() {
  if (composer) composer.render(); else renderer.render(scene, camera);
}

function loop() {
  if (!running) return;
  raf = requestAnimationFrame(loop);
  if (group) group.rotation.y += 0.0016;
  controls.update();
  draw();
}

export function start() { if (!init()) return; if (running) return; running = true; loop(); }
export function stop() { running = false; if (raf) { cancelAnimationFrame(raf); raf = 0; } }

window.__brain3d = { start, stop, get ok() { return inited; } };
window.addEventListener("gbt:view", function (e) { if (e.detail === "brain") start(); else stop(); });
window.addEventListener("resize", function () { resize(); if (!running && renderer) draw(); });
if ((location.hash || "").replace("#", "") === "brain") setTimeout(start, 60);
