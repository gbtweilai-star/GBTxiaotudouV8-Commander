/* GBT小土豆V8 · 世界锻造 3D 视图（P1）
 * 数据面：POST /api/world {op:"view3d", spec:{seed}} → world_forge.view3d（纯函数）
 * 画面：柱高=海拔，颜色=生物群系，金球=城市，蓝面=海平面；可拖动/缩放/换世界。
 * 标记：document.documentElement.dataset.world3d = "ok:<柱数>:<城数>" / "no-webgl" / "error:…"
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const HOST = "world3d-canvas";
let inited = false, running = false, raf = 0;
let renderer, scene, camera, controls, group, canvas, statusEl;
let seed = 7, W = 0, H = 0, D = 8;

document.documentElement.dataset.world3d = "imported";

function webglOk() {
  try { return canvas && (canvas.getContext("webgl2") || canvas.getContext("webgl")); }
  catch (e) { return null; }
}

function disposeGroup() {
  if (!group) return;
  scene.remove(group);
  group.traverse(function (o) {
    if (o.geometry) o.geometry.dispose();
    if (o.material) {
      if (Array.isArray(o.material)) o.material.forEach(function (m) { m.dispose(); });
      else o.material.dispose();
    }
  });
  group = null;
}

function resize() {
  if (!renderer || !canvas) return;
  const w = canvas.clientWidth || (canvas.parentElement && canvas.parentElement.clientWidth) || 640;
  const h = canvas.clientHeight || (canvas.parentElement && canvas.parentElement.clientHeight) || 420;
  renderer.setSize(w, h, false);
  if (camera) { camera.aspect = w / Math.max(1, h); camera.updateProjectionMatrix(); }
}

function build(d) {
  disposeGroup();
  group = new THREE.Group();
  scene.add(group);
  W = d.world.width; H = d.world.height; D = d.world.depth;
  const box = new THREE.BoxGeometry(1, 1, 1);
  const mat = new THREE.MeshStandardMaterial({ roughness: 0.86, metalness: 0.04 });
  const inst = new THREE.InstancedMesh(box, mat, d.columns.length);
  const m = new THREE.Matrix4(), c = new THREE.Color();
  d.columns.forEach(function (col, i) {
    const h = Math.max(0.2, Number(col.h) || 0.2);
    m.makeScale(1, h, 1);
    m.setPosition(col.x - W / 2, h / 2, col.y - H / 2);
    inst.setMatrixAt(i, m);
    inst.setColorAt(i, c.set(d.palette[col.biome] || "#7d7f86"));
  });
  inst.instanceMatrix.needsUpdate = true;
  if (inst.instanceColor) inst.instanceColor.needsUpdate = true;
  group.add(inst);

  const water = new THREE.Mesh(
    new THREE.PlaneGeometry(W, H),
    new THREE.MeshStandardMaterial({ color: 0x2f6f9f, transparent: true, opacity: 0.32,
      roughness: 0.2, metalness: 0.15 }));
  water.rotation.x = -Math.PI / 2;
  water.position.y = Math.max(0.25, D * 0.32);
  group.add(water);

  const cg = new THREE.SphereGeometry(0.55, 12, 12);
  const cm = new THREE.MeshStandardMaterial({ color: 0xffc65c, emissive: 0x8a5a00,
    emissiveIntensity: 0.65 });
  (d.cities || []).forEach(function (ci) {
    const s = new THREE.Mesh(cg, cm);
    s.position.set(ci.x - W / 2, Math.max(0.8, D * 0.32 + 1.3), ci.y - H / 2);
    group.add(s);
  });

  if (statusEl) {
    statusEl.textContent = "seed=" + d.seed + " · 文明 " + d.stats.civs +
      " · 城市 " + d.stats.cities + " · 体素 " + D + " 层";
  }
  document.documentElement.dataset.world3d =
    "ok:" + d.columns.length + ":" + (d.cities || []).length;
  camera.position.set(Math.max(W, H) * 0.95, Math.max(W, H) * 0.8, Math.max(W, H) * 1.15);
  camera.lookAt(0, 0, 0);
  controls.target.set(0, 2, 0);
  controls.update();
}

async function load(newSeed) {
  if (newSeed != null) seed = newSeed;
  const r = await fetch("/api/world", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ op: "view3d", spec: { seed: seed } })
  });
  const j = await r.json();
  if (!j || !j.ok) throw new Error((j && j.error) || "view3d 失败");
  build(j);
  return j;
}

function frame() {
  if (!running) return;
  raf = requestAnimationFrame(frame);
  if (controls) controls.update();
  if (renderer && scene && camera) renderer.render(scene, camera);
}

function init() {
  canvas = document.getElementById(HOST);
  if (!canvas) return;
  statusEl = document.getElementById("world3d-status");
  if (!webglOk()) {
    document.documentElement.dataset.world3d = "no-webgl";
    const fb = document.getElementById("world3d-fallback");
    if (fb) { fb.hidden = false; fb.textContent = "本机 WebGL 不可用：世界 3D 视图无法渲染（数据面仍可通过 /api/world 取）。"; }
    return;
  }
  renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0d1116);
  camera = new THREE.PerspectiveCamera(48, 1, 0.1, 2000);
  controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.rotateSpeed = 0.6;
  controls.minDistance = 6;
  controls.maxDistance = 220;
  scene.add(new THREE.AmbientLight(0xffffff, 0.75));
  const d1 = new THREE.DirectionalLight(0xfff2df, 1.15);
  d1.position.set(30, 60, -20);
  scene.add(d1);
  const d2 = new THREE.DirectionalLight(0x88b7ff, 0.35);
  d2.position.set(-20, 15, 40);
  scene.add(d2);
  window.addEventListener("resize", resize);
  const regen = document.getElementById("world3d-regen");
  if (regen) {
    regen.addEventListener("click", function () {
      load(Math.floor(Math.random() * 1000000)).catch(function (e) {
        document.documentElement.dataset.world3d = "error:" + String(e && e.message || e).slice(0, 80);
      });
    });
  }
  inited = true;
  load(seed).catch(function (e) {
    document.documentElement.dataset.world3d = "error:" + String(e && e.message || e).slice(0, 80);
    if (statusEl) statusEl.textContent = "世界载入失败：" + String(e && e.message || e);
  });
}

export function start() {
  if (!inited) init();
  if (!renderer) return;
  running = true;
  resize();
  setTimeout(resize, 60);
  cancelAnimationFrame(raf);
  frame();
}

export function stop() {
  running = false;
  cancelAnimationFrame(raf);
}
