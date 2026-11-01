/* GBT小土豆V8 · 触手协作可视化（Three.js）
 *
 * 主人 2026-11-01：「还有触手协作可视化面板，同样的风格做出来」。
 *
 * 映射（不是装饰）：
 *   · 中心橙色核 = 共享任务（当前要交付的那件事）；
 *   · 8 根触手 = 8 个协作角色（感知/规划/执行/验证/审计/固化/报告/协同），
 *     每根是不同的能力域代表，颜色区分；
 *   · 触手之间的弧线 = 协作链（交接/回喂/复核）；
 *   · 弧线上流动的光点 = 协作消息（有来回，不是单向箭头）；
 *   · 底座同心环 = 共享账本（所有协作都要落 orchestration-ledger/audit）。
 * 交互：拖动旋转 / 滚轮缩放；标记 data-team3d。
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

document.documentElement.dataset.team3d = "imported";

const ROLES = [
  { name: "感知", hue: 0.58, desc: "读架构/契约" },
  { name: "规划", hue: 0.50, desc: "七步拆解" },
  { name: "执行", hue: 0.08, desc: "run_task 派单" },
  { name: "验证", hue: 0.33, desc: "真跑读数字" },
  { name: "审计", hue: 0.72, desc: "留痕对账" },
  { name: "固化", hue: 0.13, desc: "五处落位" },
  { name: "报告", hue: 0.60, desc: "给数字" },
  { name: "协同", hue: 0.95, desc: "交接回喂" },
];

let renderer, scene, camera, controls, composer, bloom;
let inited = false, running = false, raf = 0;
let pulses = [];
let linkCount = 0;

function labelSprite(text, color, scale) {
  const c = document.createElement("canvas");
  c.width = 512; c.height = 96;
  const ctx = c.getContext("2d");
  ctx.font = "600 40px 'JetBrains Mono', monospace";
  ctx.fillStyle = color; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(text, 256, 48);
  const tex = new THREE.CanvasTexture(c);
  tex.minFilter = THREE.LinearFilter;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
  const s = scale || 2.4;
  sp.scale.set(s, s * 0.19, 1);
  return sp;
}

function glowSprite(color, size, opacity) {
  const c = document.createElement("canvas");
  c.width = 128; c.height = 128;
  const ctx = c.getContext("2d");
  const g = ctx.createRadialGradient(64, 64, 2, 64, 64, 62);
  g.addColorStop(0, "rgba(255,255,255,.92)");
  g.addColorStop(0.32, "rgba(255,255,255,.24)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g; ctx.fillRect(0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(c);
  const m = new THREE.SpriteMaterial({ map: tex, color: color, transparent: true,
    blending: THREE.AdditiveBlending, depthWrite: false, opacity: opacity || 0.85 });
  const sp = new THREE.Sprite(m);
  sp.scale.set(size, size, 1);
  return sp;
}

function init() {
  if (inited) return true;
  const canvas = document.getElementById("team3d-canvas");
  try {
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true,
      preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x03070d, 0.012);
    camera = new THREE.PerspectiveCamera(46, 1, 0.1, 400);
    camera.position.set(0, 5, 22);

    // ── 共享任务核 ──
    const core = new THREE.Mesh(new THREE.SphereGeometry(0.85, 32, 32),
      new THREE.MeshBasicMaterial({ color: 0xff9f1c }));
    scene.add(core);
    scene.add(glowSprite(0xff9f1c, 6.0, 0.5));
    const coreLbl = labelSprite("共享任务", "#ffe0a8", 2.2);
    coreLbl.position.set(0, 1.35, 0);
    scene.add(coreLbl);

    // 共享账本底座：同心环
    const ledgerMat = new THREE.MeshStandardMaterial({
      color: 0x6f86a8, metalness: 0.8, roughness: 0.3, emissive: 0x0e1c33, emissiveIntensity: 0.5 });
    for (let r = 0; r < 3; r++) {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(2.3 + r * 0.55, 0.02, 8, 96), ledgerMat);
      ring.rotation.x = Math.PI / 2;
      ring.position.y = -1.9;
      scene.add(ring);
    }
    const ledgerLbl = labelSprite("共享账本", "#9fb8d8", 1.6);
    ledgerLbl.position.set(0, -2.25, 2.9);
    scene.add(ledgerLbl);

    const tipPos = [];
    const armMat = new THREE.MeshStandardMaterial({
      color: 0x9fb3d1, metalness: 0.75, roughness: 0.35,
      emissive: 0x14213a, emissiveIntensity: 0.6 });
    const N = ROLES.length;

    ROLES.forEach(function (r, i) {
      const a = (i / N) * Math.PI * 2;
      const R = 7.2;
      const dir = new THREE.Vector3(Math.cos(a) * R, Math.sin(a) * R * 0.55 + 0.4, Math.sin(a) * R * 0.45);
      // 触手：中心 → 外端（曲线）
      const mid = dir.clone().multiplyScalar(0.55).add(new THREE.Vector3(0, 1.1, 0));
      const curve = new THREE.CatmullRomCurve3([
        new THREE.Vector3(0, 0, 0), mid, dir,
      ], false, "catmullrom", 0.6);
      scene.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 64, 0.075, 10, false), armMat));

      const tipColor = new THREE.Color().setHSL(r.hue, 0.85, 0.6);
      const tip = new THREE.Mesh(new THREE.SphereGeometry(0.34, 24, 24),
        new THREE.MeshStandardMaterial({ color: tipColor, emissive: tipColor,
          emissiveIntensity: 1.0, metalness: 0.3, roughness: 0.35 }));
      tip.position.copy(dir);
      scene.add(tip);
      const gl = glowSprite(tipColor.getHex(), 1.9, 0.8);
      gl.position.copy(dir);
      scene.add(gl);
      const lbl = labelSprite(r.name + " · " + r.desc, "#dce8f8", 2.6);
      lbl.position.copy(dir).add(new THREE.Vector3(0, 0.9, 0));
      scene.add(lbl);
      tipPos.push(dir.clone());
    });

    // ── 协作链：任意两角色之间的弧线 + 流动消息 ──
    const linkMat = new THREE.LineBasicMaterial({ color: 0x5f9bff, transparent: true,
      opacity: 0.22, blending: THREE.AdditiveBlending, depthWrite: false });
    const pulseGeo = new THREE.SphereGeometry(0.07, 10, 10);
    const pulseMat = new THREE.MeshBasicMaterial({ color: 0xffe0a8 });
    const pairs = [];
    for (let i = 0; i < tipPos.length; i++) {
      for (let j = i + 1; j < tipPos.length; j++) {
        // 只连相邻 2 个 + 对角 1 个，避免太密
        const d = Math.min(Math.abs(i - j), tipPos.length - Math.abs(i - j));
        if (d !== 1 && d !== 2) continue;
        pairs.push([i, j]);
      }
    }
    pairs.forEach(function (pair) {
      const a = tipPos[pair[0]], b = tipPos[pair[1]];
      const mid = a.clone().add(b).multiplyScalar(0.5);
      mid.y += 1.6 + a.distanceTo(b) * 0.08;
      const c = new THREE.CatmullRomCurve3([a, mid, b], false, "catmullrom", 0.5);
      scene.add(new THREE.Mesh(new THREE.TubeGeometry(c, 48, 0.018, 8, false), linkMat));
      linkCount++;
      for (let k = 0; k < 2; k++) {
        const dot = new THREE.Mesh(pulseGeo, pulseMat);
        scene.add(dot);
        pulses.push({ dot: dot, curve: c, t: Math.random(), speed: 0.12 + Math.random() * 0.1 });
      }
    });

    // 星尘
    const DUST = 1200;
    const arr = new Float32Array(DUST * 3);
    for (let i = 0; i < DUST; i++) {
      const r = 12 + Math.random() * 28;
      const th = Math.random() * Math.PI * 2, ph = Math.acos(2 * Math.random() - 1);
      arr[i * 3] = r * Math.sin(ph) * Math.cos(th);
      arr[i * 3 + 1] = r * Math.cos(ph) * 0.7;
      arr[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th);
    }
    const dg = new THREE.BufferGeometry();
    dg.setAttribute("position", new THREE.BufferAttribute(arr, 3));
    scene.add(new THREE.Points(dg, new THREE.PointsMaterial({
      color: 0x8fa6c4, size: 0.09, transparent: true, opacity: 0.35, depthWrite: false })));

    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const l1 = new THREE.PointLight(0x4f8cff, 2.2, 80); l1.position.set(6, 6, 8); scene.add(l1);
    const l2 = new THREE.PointLight(0xff9a3c, 1.4, 80); l2.position.set(-6, -4, 6); scene.add(l2);

    const wrap = document.querySelector(".view-team") || canvas;
    controls = new OrbitControls(camera, wrap);
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.4;
    controls.enablePan = false;
    controls.minDistance = 8;
    controls.maxDistance = 50;
    controls.rotateSpeed = 0.75;

    composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.55, 0.5, 0.62);
    composer.addPass(bloom);

    resize();
    inited = true;
    document.documentElement.dataset.team3d = "ok:" + ROLES.length + "臂+" + linkCount + "协作链";
    draw();
    return true;
  } catch (e) {
    document.documentElement.dataset.team3d = "error:" + String((e && e.message) || e).slice(0, 120);
    return false;
  }
}

function resize() {
  const c = document.getElementById("team3d-canvas");
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
  pulses.forEach(function (p) {
    p.t += p.speed * 0.016;
    if (p.t > 1) p.t -= 1;
    p.dot.position.copy(p.curve.getPointAt(Math.min(0.999, p.t)));
    p.dot.material.opacity = 1;
  });
  controls.update();
  draw();
}

export function start() { if (!init()) return; if (running) return; running = true; loop(); }
export function stop() { running = false; if (raf) { cancelAnimationFrame(raf); raf = 0; } }

window.__team3d = { start, stop, get ok() { return inited; } };
window.addEventListener("gbt:view", function (e) { if (e.detail === "team") start(); else stop(); });
window.addEventListener("resize", function () { resize(); if (!running && renderer) draw(); });
if ((location.hash || "").replace("#", "") === "team") setTimeout(start, 60);
