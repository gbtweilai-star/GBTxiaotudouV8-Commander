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
let arms = [];            // {role, curve, tip, glow, until}
let liveMsgs = [];        // 真实事件驱动的消息点 {dot, curve, t, speed}
let es = null;
let liveActive = 0;
let waves = [];          // 冲击波环 {sprite, t, speed, maxScale}
let coreMesh = null;     // 共享任务核（收到消息时闪一下）
let coreFlash = 0;

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

function ringSprite(color, size, opacity) {
  const c = document.createElement("canvas");
  c.width = 256; c.height = 256;
  const ctx = c.getContext("2d");
  const g = ctx.createRadialGradient(128, 128, 40, 128, 128, 126);
  g.addColorStop(0.0, "rgba(255,255,255,0)");
  g.addColorStop(0.55, "rgba(255,255,255,0)");
  g.addColorStop(0.78, "rgba(255,255,255,.85)");
  g.addColorStop(0.9, "rgba(255,255,255,.25)");
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
    coreMesh = core;
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
      arms.push({ role: r.name, curve: curve, tip: tip, glow: gl, until: 0 });
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
    connectLive();
    if (new URLSearchParams(location.search).get("selftest") === "1") {
      setTimeout(function () { lightRole("inventory"); lightRole("selfscan"); }, 300);
    }
    if (new URLSearchParams(location.search).get("pulse") === "1") {
      const seq = ["inventory", "selfscan", "signature_guard", "recon", "report"];
      let pi = 0;
      setInterval(function () { lightRole(seq[pi % seq.length]); pi++; }, 700);
    }
    draw();
    return true;
  } catch (e) {
    document.documentElement.dataset.team3d = "error:" + String((e && e.message) || e).slice(0, 120);
    return false;
  }
}

/* 事件名 → 协作角色（真实映射：守卫/账本类落「审计」，执行类落「执行」，报告类落「报告」） */
const EVENT_ROLE = {
  selfscan: "审计", inventory: "审计", signature_guard: "审计", legacy_guard: "审计",
  cap_self: "审计", truth_scan: "审计", inventory_report: "审计",
  auth_denied: "协同", denied: "协同",
  call: "执行", run: "执行", ok: "执行",
  report: "报告", deliver: "报告",
  plan: "规划", kernel: "规划", chain_kernel: "规划",
  verify: "验证", test: "验证",
  docs: "固化", ledger: "固化", orchestration: "固化",
  recon: "感知", scan: "感知",
};

function roleFor(cap) {
  const k = String(cap || "").toLowerCase();
  if (EVENT_ROLE[k]) return EVENT_ROLE[k];
  for (const key in EVENT_ROLE) {
    if (k.indexOf(key) >= 0) return EVENT_ROLE[key];
  }
  // 兜底：按名字哈希到一个角色，保持稳定（同一能力永远同一角色）
  let h = 0;
  for (let i = 0; i < k.length; i++) h = (h * 31 + k.charCodeAt(i)) % 997;
  return ROLES[h % ROLES.length].name;
}

function roleArm(name) {
  for (let i = 0; i < arms.length; i++) if (arms[i].role === name) return arms[i];
  return null;
}

/* 真实事件点亮：对应角色触手亮 6 秒，并从「角色尖端 → 共享任务核」飞一颗消息点 */
function lightRole(cap) {
  const name = roleFor(cap);
  const a = roleArm(name);
  if (!a) return name;
  a.until = performance.now() + 6000;
  // ⑧ 脉冲特效：角色尖端炸一圈冲击波
  const tipPos = a.tip.position.clone();
  const wave = ringSprite(0xffd166, 1.2, 0.95);
  wave.position.copy(tipPos);
  scene.add(wave);
  waves.push({ sprite: wave, t: 0, speed: 1.6, maxScale: 9.0, baseY: tipPos.y });
  if (waves.length > 16) {
    const old = waves.shift();
    scene.remove(old.sprite);
    old.sprite.material.dispose();
  }
  // 消息点 + 拖尾辉光（角色 → 中心）
  const dot = new THREE.Mesh(new THREE.SphereGeometry(0.1, 10, 10),
    new THREE.MeshBasicMaterial({ color: 0xffd166 }));
  scene.add(dot);
  const trail = glowSprite(0xffd166, 0.9, 0.85);
  scene.add(trail);
  liveMsgs.push({ dot: dot, trail: trail, curve: a.curve, t: 0, speed: 1.4, role: name });
  coreFlash = 1.0;
  if (liveMsgs.length > 24) {
    const old = liveMsgs.shift();
    scene.remove(old.dot);
    old.dot.geometry.dispose();
    old.dot.material.dispose();
  }
  updateLiveMarker();
  return name;
}

function updateLiveMarker() {
  const el = document.documentElement.dataset;
  if (!el.team3d || el.team3d.indexOf("ok:") !== 0) return;
  const parts = el.team3d.split("+");
  while (parts.length > 3) parts.pop();
  parts[2] = "脉冲" + waves.length;
  el.team3d = parts.join("+");
  el.team3dPulses = String(waves.length);
}

function connectLive() {
  if (es || typeof EventSource === "undefined") return;
  if (new URLSearchParams(location.search).get("nosse") === "1") {
    document.documentElement.dataset.team3dLive = "off-for-test";
    return;
  }
  if (!/^https?:/.test(location.protocol)) {
    document.documentElement.dataset.team3dLive = "unsupported";
    return;
  }
  try {
    es = new EventSource("/api/events");
    es.onmessage = function (e) {
      try {
        const d = JSON.parse(e.data);
        if (d && d.cap) {
          const role = lightRole(d.cap);
          document.documentElement.dataset.team3dLast = d.cap + "→" + role;
          document.documentElement.dataset.team3dLive = "on";
        }
      } catch (err) { /* ignore */ }
    };
    es.onerror = function () { document.documentElement.dataset.team3dLive = "reconnecting"; };
  } catch (e) {
    document.documentElement.dataset.team3dLive = "unsupported";
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
  // 真实事件消息点：角色尖端 → 中心（反向走）
  for (let i = liveMsgs.length - 1; i >= 0; i--) {
    const m = liveMsgs[i];
    m.t += m.speed * 0.016;
    if (m.t >= 1) {
      scene.remove(m.dot);
      m.dot.geometry.dispose();
      m.dot.material.dispose();
      if (m.trail) {
        scene.remove(m.trail);
        m.trail.material.dispose();
      }
      liveMsgs.splice(i, 1);
      updateLiveMarker();
      continue;
    }
    m.dot.position.copy(m.curve.getPointAt(Math.min(0.999, 1 - m.t)));
  }
  // 冲击波：扩散 + 淡出（真正的脉冲特效）
  for (let i = waves.length - 1; i >= 0; i--) {
    const w = waves[i];
    w.t += w.speed * 0.016;
    if (w.t >= 1) {
      scene.remove(w.sprite);
      w.sprite.material.dispose();
      waves.splice(i, 1);
      updateLiveMarker();
      continue;
    }
    const sc = 1.2 + w.t * w.maxScale;
    w.sprite.scale.set(sc, sc, 1);
    w.sprite.material.opacity = Math.max(0, (1 - w.t) * 0.95);
  }
  // 消息点拖尾跟随
  liveMsgs.forEach(function (m) {
    if (m.trail) m.trail.position.copy(m.dot.position);
  });
  // 核心被消息点亮时闪一下
  if (coreMesh) {
    coreFlash = Math.max(0, coreFlash - 0.02);
    const k = 1 + coreFlash * 0.6;
    coreMesh.scale.set(k, k, k);
    coreMesh.material.color.setHex(coreFlash > 0.1 ? 0xffd166 : 0xff9f1c);
  }
  // 角色亮灯衰减
  const nowMs = performance.now();
  arms.forEach(function (a) {
    const lit = nowMs < a.until;
    a.tip.material.emissiveIntensity = lit ? 2.2 : 1.0;
    a.glow.material.opacity = lit ? 1.0 : 0.8;
  });
  controls.update();
  draw();
}

export function start() { if (!init()) return; if (running) return; running = true; loop(); }
export function stop() { running = false; if (raf) { cancelAnimationFrame(raf); raf = 0; } }

window.__team3d = { start, stop, lightRole: function (cap) { return lightRole(cap); },
  get ok() { return inited; }, get live() { return liveMsgs.length; },
  get pulses() { return waves.length; },
  roleFor: roleFor };
window.addEventListener("gbt:view", function (e) { if (e.detail === "team") start(); else stop(); });
window.addEventListener("resize", function () { resize(); if (!running && renderer) draw(); });
if ((location.hash || "").replace("#", "") === "team") setTimeout(start, 60);
