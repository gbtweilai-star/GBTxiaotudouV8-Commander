/* GBT小土豆V8 · 万能插（Three.js）
 * 参考主人视频：数字覆盖的结状管道（数据在交错触手里流动）。
 * 映射（不是装饰）：
 *   · 三叶结管道 = 万能插触手本体（任何能力都能插进任何域）；
 *   · 管道表面流动的数字 = 实时 token/事件（数字纹理沿管道流动）；
 *   · 8 个插口 = 能力域（system/llm/security/tentacle/…），带同心环座；
 *   · 每个插口有一根自动插合的触手，尖端脉冲往复（插进/拔出）；
 *   · 中心核 = 调度器（本机指挥官）。
 * 交互：拖动旋转 / 滚轮缩放；标记 data-plug3d。
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

document.documentElement.dataset.plug3d = "imported";

const SOCKETS = [
  { name: "system", k: 0 }, { name: "llm", k: 1 }, { name: "security", k: 2 },
  { name: "tentacle", k: 3 }, { name: "mind", k: 4 }, { name: "recon", k: 5 },
  { name: "pipeline", k: 6 }, { name: "video", k: 7 },
];

let renderer, scene, camera, controls, composer, bloom;
let inited = false, running = false, raf = 0;
let knotTex, tips = [];

function digitsTexture() {
  const c = document.createElement("canvas");
  c.width = 512; c.height = 512;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#05070b"; ctx.fillRect(0, 0, 512, 512);
  ctx.font = "500 20px 'JetBrains Mono', monospace";
  ctx.textBaseline = "middle";
  for (let row = 0; row < 22; row++) {
    for (let col = 0; col < 20; col++) {
      const d = String((row * 7 + col * 3 + (row * col) % 10) % 10);
      ctx.fillStyle = (row + col) % 4 === 0 ? "#eaf3ff" : "#9fb8d8";
      ctx.fillText(d, col * 26 + 3, row * 23 + 10);
    }
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = THREE.RepeatWrapping;
  t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(18, 3);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function labelSprite(text, color) {
  const c = document.createElement("canvas");
  c.width = 512; c.height = 96;
  const ctx = c.getContext("2d");
  ctx.font = "600 38px 'JetBrains Mono', monospace";
  ctx.fillStyle = color; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(text, 256, 48);
  const tex = new THREE.CanvasTexture(c);
  tex.minFilter = THREE.LinearFilter;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
  sp.scale.set(2.6, 0.5, 1);
  return sp;
}

function glowSprite(color, size, opacity) {
  const c = document.createElement("canvas");
  c.width = 128; c.height = 128;
  const ctx = c.getContext("2d");
  const g = ctx.createRadialGradient(64, 64, 2, 64, 64, 62);
  g.addColorStop(0, "rgba(255,255,255,.9)");
  g.addColorStop(0.35, "rgba(255,255,255,.22)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g; ctx.fillRect(0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(c);
  const m = new THREE.SpriteMaterial({ map: tex, color: color, transparent: true,
    blending: THREE.AdditiveBlending, depthWrite: false, opacity: opacity || 0.85 });
  const sp = new THREE.Sprite(m);
  sp.scale.set(size, size, 1);
  return sp;
}

function trefoil(t) {
  const s = Math.sin(t), c = Math.cos(t);
  return new THREE.Vector3(
    s + 2 * Math.sin(2 * t),
    c - 2 * Math.cos(2 * t),
    -Math.sin(3 * t)
  ).multiplyScalar(1.15);
}

function init() {
  if (inited) return true;
  const canvas = document.getElementById("plug3d-canvas");
  try {
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true,
      preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x02050a, 0.012);
    camera = new THREE.PerspectiveCamera(46, 1, 0.1, 400);
    camera.position.set(0, 2.5, 20);

    // ── 数字结：三叶结管道 + 流动数字纹理 ──
    const pts = [];
    for (let i = 0; i < 220; i++) pts.push(trefoil((i / 220) * Math.PI * 2));
    const curve = new THREE.CatmullRomCurve3(pts, true, "catmullrom", 0.5);
    knotTex = digitsTexture();
    const knotMat = new THREE.MeshStandardMaterial({
      map: knotTex, color: 0xdbe6f5, metalness: 0.45, roughness: 0.5,
      emissive: 0x9fb8d8, emissiveIntensity: 0.9, emissiveMap: knotTex,
    });
    const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 240, 0.62, 20, true), knotMat);
    scene.add(tube);
    scene.add(glowSprite(0x4f8cff, 6.2, 0.16));

    // ── 8 个万能插口：同心环座 + 触手尖端（插进/拔出） ──
    const socketMat = new THREE.MeshStandardMaterial({
      color: 0xb9c8dd, metalness: 0.9, roughness: 0.25,
      emissive: 0x1a2b46, emissiveIntensity: 0.6 });
    const tipMat = new THREE.MeshStandardMaterial({
      color: 0xff9a3c, emissive: 0xff6a00, emissiveIntensity: 1.4,
      metalness: 0.25, roughness: 0.35 });

    SOCKETS.forEach(function (s, i) {
      const a = (i / SOCKETS.length) * Math.PI * 2;
      const R = 6.2;
      const pos = new THREE.Vector3(Math.cos(a) * R, Math.sin(a) * R * 0.82, 1.6);
      const socket = new THREE.Group();
      socket.position.copy(pos);
      socket.rotation.z = a;
      // 座：三层同心环
      for (let r = 0; r < 3; r++) {
        const ring = new THREE.Mesh(new THREE.TorusGeometry(0.46 + r * 0.2, 0.035, 10, 48), socketMat);
        ring.rotation.x = Math.PI / 2;
        socket.add(ring);
      }
      // 插口内发光面
      const disc = new THREE.Mesh(new THREE.CircleGeometry(0.42, 32),
        new THREE.MeshBasicMaterial({ color: 0x1d3352, transparent: true, opacity: 0.9 }));
      disc.rotation.x = -Math.PI / 2;
      socket.add(disc);
      const gl = glowSprite(0x5f9bff, 1.4, 0.5);
      gl.position.z = 0.1;
      socket.add(gl);
      socket.add((function () { const l = labelSprite(s.name, "#cfe0f5"); l.position.set(0, 0, 0.95); return l; })());
      scene.add(socket);

      // 触手：从中心走到插口（曲线），尖端在插口附近脉冲
      const p0 = new THREE.Vector3(0, 0, 0);
      const p1 = pos.clone().normalize().multiplyScalar(R * 0.5).add(new THREE.Vector3(0.4, -0.6, 0.2));
      const p2 = pos.clone().multiplyScalar(0.92);
      const path = new THREE.CatmullRomCurve3([p0, p1, p2], false, "catmullrom", 0.6);
      const tMat = new THREE.MeshStandardMaterial({
        color: 0x8fa6c4, metalness: 0.8, roughness: 0.3,
        emissive: 0x14213a, emissiveIntensity: 0.5 });
      scene.add(new THREE.Mesh(new THREE.TubeGeometry(path, 60, 0.055, 8, false), tMat));
      const tip = new THREE.Mesh(new THREE.SphereGeometry(0.18, 20, 20), tipMat);
      scene.add(tip);
      tips.push({ tip: tip, path: path, phase: i * 0.6 });
    });

    // ── 中心调度核 ──
    const core = new THREE.Mesh(new THREE.SphereGeometry(0.7, 32, 32),
      new THREE.MeshBasicMaterial({ color: 0xff9f1c }));
    scene.add(core);
    scene.add(glowSprite(0xff9f1c, 4.5, 0.55));

    // ── 外圈星尘 ──
    const DUST = 1200;
    const arr = new Float32Array(DUST * 3);
    for (let i = 0; i < DUST; i++) {
      const r = 11 + Math.random() * 26;
      const th = Math.random() * Math.PI * 2, ph = Math.acos(2 * Math.random() - 1);
      arr[i * 3] = r * Math.sin(ph) * Math.cos(th);
      arr[i * 3 + 1] = r * Math.cos(ph) * 0.8;
      arr[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th);
    }
    const dg = new THREE.BufferGeometry();
    dg.setAttribute("position", new THREE.BufferAttribute(arr, 3));
    scene.add(new THREE.Points(dg, new THREE.PointsMaterial({
      color: 0x6f86a8, size: 0.09, transparent: true, opacity: 0.35, depthWrite: false })));

    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const l1 = new THREE.PointLight(0x4f8cff, 2.4, 60); l1.position.set(4, 4, 6); scene.add(l1);
    const l2 = new THREE.PointLight(0xff9a3c, 1.4, 60); l2.position.set(-5, -3, 4); scene.add(l2);

    const wrap = document.querySelector(".view-plug") || canvas;
    controls = new OrbitControls(camera, wrap);
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.45;
    controls.enablePan = false;
    controls.minDistance = 7;
    controls.maxDistance = 45;
    controls.rotateSpeed = 0.75;

    composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.55, 0.5, 0.62);
    composer.addPass(bloom);

    resize();
    inited = true;
    document.documentElement.dataset.plug3d = "ok:" + SOCKETS.length + "插口+数字结";
    draw();
    return true;
  } catch (e) {
    document.documentElement.dataset.plug3d = "error:" + String((e && e.message) || e).slice(0, 120);
    return false;
  }
}

function resize() {
  const c = document.getElementById("plug3d-canvas");
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
  const t = performance.now() / 1000;
  // 数字沿结流动
  if (knotTex) { knotTex.offset.x = (t * 0.06) % 1; knotTex.offset.y = (t * 0.02) % 1; }
  // 触手尖端：沿路径往复插合
  tips.forEach(function (o) {
    const k = 0.72 + 0.26 * (0.5 + 0.5 * Math.sin(t * 1.6 + o.phase));
    o.tip.position.copy(o.path.getPointAt(Math.min(0.999, k)));
    o.tip.material.emissiveIntensity = 0.9 + 0.7 * (0.5 + 0.5 * Math.sin(t * 3 + o.phase));
  });
  controls.update();
  draw();
}

export function start() { if (!init()) return; if (running) return; running = true; loop(); }
export function stop() { running = false; if (raf) { cancelAnimationFrame(raf); raf = 0; } }

window.__plug3d = { start, stop, get ok() { return inited; } };
window.addEventListener("gbt:view", function (e) { if (e.detail === "plug") start(); else stop(); });
window.addEventListener("resize", function () { resize(); if (!running && renderer) draw(); });
if ((location.hash || "").replace("#", "") === "plug") setTimeout(start, 60);
