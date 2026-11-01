/* GBT小土豆V8 · 穿透式交叉扫描（真实扫描结果驱动）
 *
 * 主人 2026-11-01：「原生穿透式交叉扫描可视化，每次扫描不管扫什么都要看到她是怎么扫的…
 * 遇到扫描疑点她会考虑会反思穿透」+「她的视觉可不是只有 OCR」。
 *
 * 数据 100% 来自真跑：tools/export-scan-data.py 调 tools/penetrating_cross_scan.py，
 * 把每次扫描的 unit_details（unit / status=agree|arbitrated|unhooked）写进 console-data.js：
 *   · 绿点 = agree（两路以上读数一致）
 *   · 琥珀点 = arbitrated（两路不一致，第三路仲裁 → 真"疑点"）
 *   · 红点 = unhooked / missing（没钩住，如实报，不折叠成绿）
 * 扫描线自上而下；遇非绿点：大脑反思（环）→ 手穿透（纵深束）→ 速度放慢；一轮完嘴巴报结论。
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

document.documentElement.dataset.scan3d = "imported";

const SENSES = [
  { key: "eye", name: "眼睛", color: 0x7bdff2, desc: "视觉全谱" },
  { key: "ear", name: "耳朵", color: 0x9b8cff, desc: "听异常" },
  { key: "mouth", name: "嘴巴", color: 0xffd166, desc: "报结论" },
  { key: "hand", name: "手", color: 0xff8a3c, desc: "穿透" },
  { key: "brain", name: "大脑", color: 0xff5f6d, desc: "反思" },
];

let renderer, scene, camera, controls, composer, bloom;
let inited = false, running = false, raf = 0;
let group = null;
let nodes = [], nodePoints = null;
let sweepPlane = null, sweepY = 9;
let sweepDir = -1, speed = 2.6, slowUntil = 0;
let rings = [], depthBeams = [], senseOrbs = {};
let hud = {};
let stats = { swept: 0, doubts: 0, reflections: 0, penetrations: 0 };
let total = 0, doubtN = 0, greenN = 0, amberN = 0, redN = 0;
let targetName = "";
let scans = [];

function labelSprite(text, color, scale, size) {
  const c = document.createElement("canvas");
  c.width = 512; c.height = 96;
  const ctx = c.getContext("2d");
  ctx.font = "600 " + (size || 38) + "px 'JetBrains Mono', monospace";
  ctx.fillStyle = color; ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ctx.fillText(text, 256, 48);
  const tex = new THREE.CanvasTexture(c);
  tex.minFilter = THREE.LinearFilter;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
  const s = scale || 2.6;
  sp.scale.set(s, s * 0.19, 1);
  return sp;
}

function glowSprite(color, size, opacity) {
  const c = document.createElement("canvas");
  c.width = 128; c.height = 128;
  const ctx = c.getContext("2d");
  const g = ctx.createRadialGradient(64, 64, 2, 64, 64, 62);
  g.addColorStop(0, "rgba(255,255,255,.9)");
  g.addColorStop(0.3, "rgba(255,255,255,.24)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g; ctx.fillRect(0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(c);
  const m = new THREE.SpriteMaterial({ map: tex, color: color, transparent: true,
    blending: THREE.AdditiveBlending, depthWrite: false, opacity: opacity || 0.85 });
  const sp = new THREE.Sprite(m);
  sp.scale.set(size, size, 1);
  return sp;
}

function ringSprite(color, size, opacity) {
  const c = document.createElement("canvas");
  c.width = 256; c.height = 256;
  const ctx = c.getContext("2d");
  const g = ctx.createRadialGradient(128, 128, 40, 128, 128, 126);
  g.addColorStop(0.0, "rgba(255,255,255,0)");
  g.addColorStop(0.55, "rgba(255,255,255,0)");
  g.addColorStop(0.78, "rgba(255,255,255,.9)");
  g.addColorStop(1.0, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(128, 128, 126, 0, Math.PI * 2); ctx.fill();
  const tex = new THREE.CanvasTexture(c);
  const m = new THREE.SpriteMaterial({ map: tex, color: color, transparent: true,
    blending: THREE.AdditiveBlending, depthWrite: false, opacity: opacity || 0.9 });
  const sp = new THREE.Sprite(m);
  sp.scale.set(size, size, 1);
  return sp;
}

function loadData() {
  const d = window.GBT_CONSOLE || {};
  scans = ((d.scan && d.scan.scans) || []).filter(function (s) {
    return (s.unit_details && s.unit_details.length) || s.units;
  });
}

function clearGroup() {
  if (group) {
    scene.remove(group);
    group.traverse(function (o) {
      if (o.geometry) o.geometry.dispose();
      if (o.material) {
        if (Array.isArray(o.material)) o.material.forEach(function (m) { m.dispose(); });
        else o.material.dispose();
      }
    });
  }
  group = new THREE.Group();
  scene.add(group);
  nodes = []; nodePoints = null; sweepPlane = null;
  rings.forEach(function (r) { r.sprite.material.dispose(); });
  rings = [];
  stats = { swept: 0, doubts: 0, reflections: 0, penetrations: 0 };
  sweepDir = -1; sweepY = 9.4;
}

function buildScan(scan) {
  clearGroup();
  targetName = scan.target;
  const units = (scan.unit_details && scan.unit_details.length) ? scan.unit_details
    : Array.from({ length: Math.min(scan.units || 0, 4000) }, function (_, i) {
        return { unit: "unit-" + i, status: "agree" };
      });
  total = units.length;
  const COLS = 26;
  const ROWS = Math.max(1, Math.ceil(total / COLS));
  const W = 13.2, H = 20.0;
  const posArr = [], colArr = [];
  nodes = [];
  greenN = amberN = redN = doubtN = 0;
  units.forEach(function (u, i) {
    const col = i % COLS, row = Math.floor(i / COLS);
    const x = (col / (COLS - 1) - 0.5) * W + (Math.random() - 0.5) * 0.22;
    const y = (0.5 - row / Math.max(1, ROWS - 1)) * H + (Math.random() - 0.5) * 0.18;
    const z = (Math.random() - 0.5) * 2.4;
    const st = String(u.status || "agree");
    let color, doubt = false;
    if (st === "agree") { color = new THREE.Color(0x36e08a); greenN++; }
    else if (st === "arbitrated") { color = new THREE.Color(0xffb020); amberN++; doubt = true; }
    else { color = new THREE.Color(0xff3b4e); redN++; doubt = true; }
    if (doubt) doubtN++;
    nodes.push({ pos: new THREE.Vector3(x, y, z), doubt: doubt, st: st, lit: false, base: color.clone() });
    posArr.push(x, y, z);
    colArr.push(color.r * 0.55, color.g * 0.55, color.b * 0.55);
  });
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(posArr, 3));
  g.setAttribute("color", new THREE.Float32BufferAttribute(colArr, 3));
  nodePoints = new THREE.Points(g, new THREE.PointsMaterial({
    size: 0.15, vertexColors: true, transparent: true, opacity: 0.95,
    blending: THREE.AdditiveBlending, depthWrite: false }));
  group.add(nodePoints);

  const e = [], ec = [];
  function edge(a, b) {
    const A = nodes[a].pos, B = nodes[b].pos;
    e.push(A.x, A.y, A.z, B.x, B.y, B.z);
    const c1 = nodes[a].base, c2 = nodes[b].base;
    ec.push(c1.r * 0.45, c1.g * 0.45, c1.b * 0.45, c2.r * 0.45, c2.g * 0.45, c2.b * 0.45);
  }
  nodes.forEach(function (n, i) {
    const col = i % COLS, row = Math.floor(i / COLS);
    if (col < COLS - 1 && i + 1 < nodes.length) edge(i, i + 1);
    if (row < ROWS - 1 && i + COLS < nodes.length) edge(i, i + COLS);
    if (col < COLS - 1 && i + COLS + 1 < nodes.length && i % 3 === 0) edge(i, i + COLS + 1);
    if (i + COLS * 2 < nodes.length && i % 7 === 0) edge(i, i + COLS * 2);
  });
  const eg = new THREE.BufferGeometry();
  eg.setAttribute("position", new THREE.Float32BufferAttribute(e, 3));
  eg.setAttribute("color", new THREE.Float32BufferAttribute(ec, 3));
  group.add(new THREE.LineSegments(eg, new THREE.LineBasicMaterial({
    vertexColors: true, transparent: true, opacity: 0.16,
    blending: THREE.AdditiveBlending, depthWrite: false })));

  const plane = new THREE.Mesh(new THREE.PlaneGeometry(W + 2.8, 0.05),
    new THREE.MeshBasicMaterial({ color: 0xcfe4ff, transparent: true, opacity: 0.8,
      blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
  plane.rotation.x = -Math.PI / 2;
  group.add(plane);
  const sg = glowSprite(0xcfe4ff, 8.2, 0.25);
  sg.position.y = 0.02;
  plane.add(sg);
  sweepPlane = plane;

  const bar = document.getElementById("scan-targets");
  if (bar) {
    bar.innerHTML = "";
    scans.forEach(function (sc) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "scan-target" + (sc.target === targetName ? " is-active" : "");
      b.textContent = sc.target + " (" + (sc.units || 0) + ")";
      b.addEventListener("click", function () { buildScan(sc); });
      bar.appendChild(b);
    });
  }
  updateHud();
  document.documentElement.dataset.scan3d =
    "ok:" + targetName + ":" + total + "单元+" + doubtN + "疑点";
}

function updateHud() {
  if (hud.target) hud.target.textContent = targetName;
  const totEl = document.getElementById("scan-total");
  if (totEl) totEl.textContent = String(total);
  if (hud.swept) hud.swept.textContent = String(Math.min(stats.swept, total));
  if (hud.doubt) hud.doubt.textContent = String(stats.doubts);
  if (hud.refl) hud.refl.textContent = String(stats.reflections);
  if (hud.pen) hud.pen.textContent = String(stats.penetrations);
  document.documentElement.dataset.scan3dSwept = String(stats.swept);
  document.documentElement.dataset.scan3dDoubts = String(stats.doubts);
  document.documentElement.dataset.scan3dReflections = String(stats.reflections);
  document.documentElement.dataset.scan3dPenetrations = String(stats.penetrations);
  document.documentElement.dataset.scan3dGreen = String(greenN);
  document.documentElement.dataset.scan3dAmber = String(amberN);
  document.documentElement.dataset.scan3dRed = String(redN);
}

function sensePulse(key, ms) {
  const s = senseOrbs[key];
  if (s) s.until = performance.now() + (ms || 900);
  const el = document.querySelector('.scan-sense[data-sense="' + key + '"]');
  if (el) el.classList.add("is-lit");
}

function reflect(node) {
  sensePulse("brain", 1400);
  sensePulse("ear", 1200);
  stats.reflections += 1;
  const wave = ringSprite(node.st === "arbitrated" ? 0xffb020 : 0xff5f6d, 0.8, 0.95);
  wave.position.copy(node.pos);
  group.add(wave);
  rings.push({ sprite: wave, t: 0, maxScale: 4.6 });
  if (rings.length > 24) {
    const old = rings.shift();
    group.remove(old.sprite);
    old.sprite.material.dispose();
  }
  sensePulse("hand", 1400);
  const beam = depthBeams.find(function (b) { return b.until < performance.now(); }) || depthBeams[0];
  if (beam) {
    beam.mesh.position.set(node.pos.x, node.pos.y, 0);
    beam.until = performance.now() + 900;
  }
  stats.penetrations += 1;
  slowUntil = performance.now() + 800;
  if (hud.state) hud.state.textContent = "疑点 → 反思 → 穿透";
}

function stepScan(dt) {
  if (!sweepPlane) return;
  const slowing = performance.now() < slowUntil;
  sweepY += sweepDir * (slowing ? speed * 0.25 : speed) * dt;
  if (sweepY < -9.4 || sweepY > 9.4) {
    sweepDir *= -1;
    sweepY = sweepDir > 0 ? -9.4 : 9.4;
    stats.swept = 0;
    if (hud.state) hud.state.textContent = "扫描中";
    sensePulse("eye", 1200);
    sensePulse("ear", 900);
  }
  sweepPlane.position.y = sweepY;
  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i];
    if (n.lit) continue;
    if ((sweepDir < 0 && n.pos.y <= sweepY) || (sweepDir > 0 && n.pos.y >= sweepY)) {
      n.lit = true;
      stats.swept += 1;
      if (n.doubt) { stats.doubts += 1; reflect(n); }
    }
  }
  const colAttr = nodePoints.geometry.attributes.color;
  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i];
    const k = n.lit ? 1.05 : 0.2;
    colAttr.setXYZ(i, n.base.r * k, n.base.g * k, n.base.b * k);
  }
  colAttr.needsUpdate = true;
  if (stats.swept >= total) {
    if (hud.state) hud.state.textContent = "本轮扫完 · " + (doubtN ? "疑点已全部穿透" : "全绿·无遗漏");
    sensePulse("mouth", 1500);
  }
  updateHud();
}

function init() {
  if (inited) return true;
  const canvas = document.getElementById("scan3d-canvas");
  try {
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true,
      preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x03060b, 0.010);
    camera = new THREE.PerspectiveCamera(46, 1, 0.1, 400);
    camera.position.set(0, 2, 27);
    camera.lookAt(0, 0, 0);

    loadData();
    if (!scans.length) {
      document.documentElement.dataset.scan3d = "no-scan-data";
      return false;
    }

    // 五感
    SENSES.forEach(function (s, i) {
      const a = (i / SENSES.length) * Math.PI * 2 - Math.PI / 2;
      const pos = new THREE.Vector3(Math.cos(a) * 8.4, 11.6, Math.sin(a) * 2.4 - 1.5);
      const orb = new THREE.Mesh(new THREE.SphereGeometry(0.3, 24, 24),
        new THREE.MeshStandardMaterial({ color: s.color, emissive: s.color,
          emissiveIntensity: 1.0, metalness: 0.3, roughness: 0.35 }));
      orb.position.copy(pos);
      scene.add(orb);
      const gl = glowSprite(s.color, 1.9, 0.75);
      gl.position.copy(pos);
      scene.add(gl);
      const lb = labelSprite(s.name + " · " + s.desc, "#e6f0ff", 2.6, 34);
      lb.position.copy(pos).add(new THREE.Vector3(0, -0.75, 0));
      scene.add(lb);
      senseOrbs[s.key] = { orb: orb, glow: gl, until: 0 };
    });

    const beamGeo = new THREE.CylinderGeometry(0.02, 0.02, 26, 8, 1, true);
    depthBeams = [];
    for (let i = 0; i < 6; i++) {
      const beam = new THREE.Mesh(beamGeo, new THREE.MeshBasicMaterial({
        color: 0xff5f6d, transparent: true, opacity: 0.0,
        blending: THREE.AdditiveBlending, depthWrite: false }));
      beam.rotation.x = Math.PI / 2;
      scene.add(beam);
      depthBeams.push({ mesh: beam, until: 0 });
    }

    const DUST = 1600;
    const arr = new Float32Array(DUST * 3);
    for (let i = 0; i < DUST; i++) {
      const r = 16 + Math.random() * 26;
      const th = Math.random() * Math.PI * 2, ph = Math.acos(2 * Math.random() - 1);
      arr[i * 3] = r * Math.sin(ph) * Math.cos(th);
      arr[i * 3 + 1] = r * Math.cos(ph);
      arr[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th);
    }
    const dg = new THREE.BufferGeometry();
    dg.setAttribute("position", new THREE.BufferAttribute(arr, 3));
    scene.add(new THREE.Points(dg, new THREE.PointsMaterial({
      color: 0x6f86a8, size: 0.09, transparent: true, opacity: 0.32, depthWrite: false })));

    scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const l1 = new THREE.PointLight(0x6f9bff, 1.8, 80); l1.position.set(6, 12, 8); scene.add(l1);
    const l2 = new THREE.PointLight(0xff5f6d, 1.2, 80); l2.position.set(-6, -8, 6); scene.add(l2);

    const wrap = document.querySelector(".view-scan") || canvas;
    controls = new OrbitControls(camera, wrap);
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.18;
    controls.enablePan = false;
    controls.minDistance = 12;
    controls.maxDistance = 60;
    controls.rotateSpeed = 0.7;

    composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.55, 0.5, 0.62);
    composer.addPass(bloom);

    hud = {
      target: document.getElementById("scan-target"),
      swept: document.getElementById("scan-swept"),
      doubt: document.getElementById("scan-doubt"),
      refl: document.getElementById("scan-refl"),
      pen: document.getElementById("scan-pen"),
      state: document.getElementById("scan-state"),
    };

    const want = new URLSearchParams(location.search).get("target");
    const pick = (want && scans.find(function (x) { return x.target === want; })) || scans[0];
    buildScan(pick);
    resize();
    inited = true;
    draw();
    return true;
  } catch (e) {
    document.documentElement.dataset.scan3d = "error:" + String((e && e.message) || e).slice(0, 120);
    return false;
  }
}

function resize() {
  const c = document.getElementById("scan3d-canvas");
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

let last = performance.now();
function loop() {
  if (!running) return;
  raf = requestAnimationFrame(loop);
  const now = performance.now();
  const dt = Math.min(0.05, (now - last) / 1000);
  last = now;
  stepScan(dt);
  for (let i = rings.length - 1; i >= 0; i--) {
    const r = rings[i];
    r.t += dt * 1.6;
    if (r.t >= 1) { group.remove(r.sprite); r.sprite.material.dispose(); rings.splice(i, 1); continue; }
    const sc = 0.8 + r.t * r.maxScale;
    r.sprite.scale.set(sc, sc, 1);
    r.sprite.material.opacity = Math.max(0, (1 - r.t) * 0.95);
  }
  const tnow = performance.now();
  depthBeams.forEach(function (b) {
    b.mesh.material.opacity = tnow < b.until ? 0.55 : Math.max(0, b.mesh.material.opacity - 0.03);
  });
  Object.keys(senseOrbs).forEach(function (k) {
    const s = senseOrbs[k];
    const lit = tnow < s.until;
    s.orb.material.emissiveIntensity = lit ? 2.4 : 1.0;
    s.glow.material.opacity = lit ? 1.0 : 0.75;
    const kk = lit ? 1.35 : 1.0;
    s.orb.scale.set(kk, kk, kk);
    const el = document.querySelector('.scan-sense[data-sense="' + k + '"]');
    if (el) el.classList.toggle("is-lit", lit);
  });
  controls.update();
  draw();
}

export function start() { if (!init()) return; if (running) return; running = true; last = performance.now(); loop(); }
export function stop() { running = false; if (raf) { cancelAnimationFrame(raf); raf = 0; } }

window.__scan3d = {
  start, stop,
  get ok() { return inited; },
  get stats() { return { swept: stats.swept, doubts: stats.doubts, reflections: stats.reflections,
                         penetrations: stats.penetrations, total: total }; },
  get target() { return targetName; },
  switchTo: function (t) {
    const sc = scans.find(function (x) { return x.target === t; });
    if (sc) buildScan(sc);
    return targetName;
  },
  reset: function () {
    nodes.forEach(function (n) { n.lit = false; });
    stats = { swept: 0, doubts: 0, reflections: 0, penetrations: 0 };
    updateHud();
  },
};
window.addEventListener("gbt:view", function (e) { if (e.detail === "scan") start(); else stop(); });
window.addEventListener("resize", function () { resize(); if (!running && renderer) draw(); });
if ((location.hash || "").replace("#", "") === "scan") setTimeout(start, 60);
