/**
 * 语音剧场 · 状态机行为验证（不靠浏览器）
 * 开发者：自由的风 · 本署名不可删除、不可篡改归属
 *
 * 为什么要有它（2026-10-18）：
 *   `voice-theater-check.py` 只能证明「画面不是空壳」；**截图证明不了交互**，
 *   而实测**无头浏览器不跑页面异步任务**（录音端点停在"正在枚举…"）⇒ 交互仍未被验。
 *   本器把页面里的内联脚本**原样**取出来，在 Node 的 `vm` 里跑，
 *   用**假 DOM** 驱动真实事件，按页面自己写的状态机断言转移。
 *
 * 它验什么（每一条都能指回页面的哪根线）：
 *   S1 初始态 = idle（状态轨只有 idle 亮）
 *   S2 按住光球（pointerdown）→ listen
 *   S3 松手（window pointerup）→ think → 约 780ms 后 → speak（音频真播时）
 *   S4 Esc 立即打断 → idle（任何状态都能被打断）
 *   S5 音频源：默认 = 样本；`?audio=x` = 产物（体检文案随来源变）
 *   S6 解码成功 → 徽标「已就绪」；解码失败 → 「解码失败」+ 原因（不假装能放）
 *
 * 它不验什么：真实出声/收音（那要 audio_output / privacy_read 票与硬件）。
 *
 * 用法：node tools/codex-scripts/voice-theater-states.mjs
 * 退出码：0 全过 · 1 有红
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..", "..");
const PAGE = resolve(ROOT, "holo_pet_w3/voice-theater/index.html");

const html = readFileSync(PAGE, "utf8");
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) {
  console.error("🔴 页面里找不到内联 <script>");
  process.exit(1);
}
const SRC = m[1];

/* ── 假 DOM ───────────────────────────────────────────────────────────── */
function makeEl(id, extra = {}) {
  const el = {
    id,
    textContent: "",
    attrs: {},
    listeners: {},
    style: { setProperty() {} },
    classList: { add() {}, remove() {} },
    children: [],
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return this.attrs[k] ?? null; },
    addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
    appendChild(c) { this.children.push(c); return c; },
    insertBefore(c) { this.children.push(c); return c; },
    remove() {},
    getContext() {
      return {
        setTransform() {}, clearRect() {}, fillRect() {}, fillStyle: "",
      };
    },
    get clientWidth() { return 800; },
    get clientHeight() { return 46; },
    width: 0,
    height: 0,
    ...extra,
  };
  return el;
}

function makeWorld(search = "") {
  const railStates = ["idle", "listen", "think", "speak"];
  const rail = railStates.map((s) => {
    const e = makeEl("rail-" + s);
    e.setAttribute("data-state", s);
    e.setAttribute("data-on", s === "idle" ? "1" : "0");
    return e;
  });

  const byId = {
    halo: makeEl("halo"),
    glow: makeEl("glow"),
    orb: makeEl("orb"),
    caption: makeEl("caption"),
    who: makeEl("who"),
    wave: makeEl("wave"),
    say: makeEl("say"),
    send: makeEl("send"),
    stop: makeEl("stop"),
    hint: makeEl("hint"),
    pMic: makeEl("pMic"),
    pMicNote: makeEl("pMicNote"),
    pSrc: makeEl("pSrc"),
    pSrcNote: makeEl("pSrcNote"),
    pReady: makeEl("pReady"),
  };
  byId.orb.setAttribute("data-pressed", "0");
  byId.orb.setAttribute("data-live", "0");

  const winListeners = {};

  const document = {
    getElementById: (id) => byId[id] ?? null,
    querySelectorAll: (sel) => (sel === ".rail__item" ? rail : []),
    createElement: () => makeEl("dyn"),
    createTextNode: (t) => ({ nodeValue: t }),
  };

  const fetched = [];

  const sandbox = {
    document,
    location: { search },
    console,
    setTimeout, clearTimeout, setInterval, clearInterval,
    Promise, Date, Math, JSON, String, Number, Object, Array, Error, Uint8Array,
    URLSearchParams, // 🔴 第一版漏给这个 ⇒ `?audio=` 读不到，三条红全是量具自己的 bug
    requestAnimationFrame: () => 0, // 不跑渲染循环（这里只验状态机）
    fetch: (url) => {
      fetched.push(String(url));
      if (String(url).includes("missing")) {
        return Promise.resolve({ ok: false, status: 404, arrayBuffer: async () => new ArrayBuffer(0) });
      }
      return Promise.resolve({ ok: true, status: 200, arrayBuffer: async () => new ArrayBuffer(16) });
    },
    navigator: { mediaDevices: undefined }, // 无麦路径：按住 → 如实退键盘
    window: {
      addEventListener(t, f) { (winListeners[t] = winListeners[t] || []).push(f); },
      devicePixelRatio: 1,
      AudioContext: FakeAudio,
    },
    AudioContext: FakeAudio,
  };
  sandbox.window.window = sandbox.window;

  return { sandbox, byId, rail, winListeners, fetched };
}

class FakeAudio {
  constructor() {
    this.state = "running";
    this.destination = {};
  }
  createAnalyser() {
    return {
      fftSize: 0, smoothingTimeConstant: 0, frequencyBinCount: 512,
      connect() {},
      getByteFrequencyData(a) { for (let i = 0; i < a.length; i += 1) a[i] = 120; },
    };
  }
  createBufferSource() {
    return { buffer: null, connect() {}, start() {}, stop() {}, onended: null };
  }
  decodeAudioData() { return Promise.resolve({ duration: 3 }); }
  resume() { return Promise.resolve(); }
}

/* ── 断言小工具 ───────────────────────────────────────────────────────── */
const results = [];
function check(name, ok, detail) {
  results.push({ name, ok: !!ok, detail: detail || "" });
}

function activeState(rail) {
  const on = rail.find((r) => r.getAttribute("data-on") === "1");
  return on ? on.getAttribute("data-state") : "(none)";
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function runCase(title, search) {
  const world = makeWorld(search);
  await vm.runInNewContext(SRC, world.sandbox, { filename: `voice-theater${search || ""}` });
  await sleep(30); // 让启动时的微任务跑完
  return world;
}

async function main() {
  /* — 默认（样本） — */
  let w = await runCase("default", "");
  check("S1 初始态=idle", activeState(w.rail) === "idle", `实际 ${activeState(w.rail)}`);
  check("S5a 默认源=样本", w.byId.pSrc.textContent.includes("样本"), `实际「${w.byId.pSrc.textContent}」`);
  check("S6a 解码成功→已就绪", w.byId.pReady.textContent === "已就绪", `实际「${w.byId.pReady.textContent}」`);

  // S2 按住
  (w.byId.orb.listeners.pointerdown || []).forEach((f) => f({ preventDefault() {} }));
  await sleep(20);
  check("S2 按住→listen", activeState(w.rail) === "listen", `实际 ${activeState(w.rail)}`);
  check("S2b 光球标记 data-live=1", w.byId.orb.getAttribute("data-live") === "1");

  // S3 松手 → think → speak
  (w.winListeners.pointerup || []).forEach((f) => f());
  await sleep(20);
  check("S3a 松手→think", activeState(w.rail) === "think", `实际 ${activeState(w.rail)}`);
  await sleep(900);
  check("S3b 780ms 后→speak", activeState(w.rail) === "speak", `实际 ${activeState(w.rail)}`);

  // S4 打断
  (w.winListeners.keydown || []).forEach((f) => f({ key: "Escape" }));
  await sleep(20);
  check("S4 Esc→idle", activeState(w.rail) === "idle", `实际 ${activeState(w.rail)}`);

  /* — ?audio=（产物） — */
  w = await runCase("audio", "?audio=/holo_pet_w3/digital-human/welcome-gbt-v8-zh.wav");
  check("S5b ?audio=→产物", w.byId.pSrc.textContent.includes("TTS 产物"), `实际「${w.byId.pSrc.textContent}」`);
  check("S6b 产物解码成功→已就绪", w.byId.pReady.textContent === "已就绪", `实际「${w.byId.pReady.textContent}」`);

  /* — 取不到音频（负控：不许装作能用） — */
  w = await runCase("missing", "?audio=missing.wav");
  await sleep(60);
  check("S6c 取不到→解码失败", w.byId.pReady.textContent === "解码失败", `实际「${w.byId.pReady.textContent}」`);
  check("S6d 失败时给原因", /404|取不到/.test(w.byId.hint.textContent), `hint=「${w.byId.hint.textContent}」`);

  /* — 输出 — */
  const red = results.filter((r) => !r.ok);
  console.log("═".repeat(74));
  console.log("  语音剧场 · 状态机行为验证（Node 沙箱 + 假 DOM，不靠浏览器）");
  console.log("═".repeat(74));
  for (const r of results) {
    console.log(`  ${r.ok ? "✅" : "🔴"} ${r.name.padEnd(22, " ")} ${r.detail}`);
  }
  console.log("-".repeat(74));
  console.log(`结论：${red.length ? `有红 ${red.length} 条` : "全过"}（共 ${results.length} 条）`);
  console.log("边界：只验**状态转移与文案**；真实出声/收音要票与硬件，本器不宣称验过。");
  process.exit(red.length ? 1 : 0);
}

main().catch((e) => {
  console.error("🔴 验证器自身失败：", e && e.stack ? e.stack : e);
  process.exit(1);
});
