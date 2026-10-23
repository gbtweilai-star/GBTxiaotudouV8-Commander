/* GBT小土豆V8 · W9 · 功能纯函数层（数字人召唤台 + AI 朋友圈本机只读）
 *
 * 为什么单独成文件：`shell/main.cjs` 顶部就 `require("electron")`，`node --test` 里根本
 * require 不动 —— 所以凡是要被用例钉住的行为，一律挪到这里：纯函数、零 electron、零副作用。
 *
 * 纪律：
 *   1) 本文件**不写盘、不起子进程、不发网络**；fs / path 由调用方传入或只读使用。
 *   2) 远端来的文本一律先过 `redact()` 再上屏；绝对路径**不回显**，只报 basename。
 *   3) 缺什么就报什么 —— 不拿默认值顶替，不把"灰"渲染成"绿"（《假绿铁律》）。
 *
 * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
 */
"use strict";

const path = require("path");

const LIMITS = {
  feed_items: 20,
  messages: 20,
  friends: 50,
  content_chars: 420,
  bio_chars: 240,
  models: 12,
};

/* ── 一 · 脱敏层：任何要上屏的远端文本先过这里 ── */

const REDACT_RULES = [
  { name: "private_key_block",
    re: /-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----/g },
  { name: "windows_path", re: /[A-Za-z]:\\[^\s"'<>|]*/g },
  { name: "credential_kv",
    re: /(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|passwd|credential|bearer)\s*[:=]?\s*[A-Za-z0-9._~+/=-]{8,}/gi },
  { name: "prefixed_secret", re: /\b(?:sk|ak|zk|pk)-[A-Za-z0-9._-]{8,}\b/g },
  { name: "email", re: /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g },
];

const REDACT_PLACEHOLDER = "[已脱敏]";

/* 返回 {text, redactions, rules} —— 命中数必须报出来，否则"脱没脱"无从判定 */
function redact(value) {
  let out = value === null || value === undefined ? "" : String(value);
  let redactions = 0;
  const rules = [];
  for (const rule of REDACT_RULES) {
    const before = out;
    out = out.replace(rule.re, () => { redactions += 1; return REDACT_PLACEHOLDER; });
    if (out !== before) rules.push(rule.name);
  }
  return { text: out, redactions: redactions, rules: rules };
}

function clip(value, max) {
  const s = value === null || value === undefined ? "" : String(value);
  const n = Number(max) > 0 ? Number(max) : LIMITS.content_chars;
  return s.length > n ? s.slice(0, n) + "…" : s;
}

/* 时间戳单位未定时两种都吃：>1e12 当毫秒，否则当秒 */
function toIso(ts) {
  const n = Number(ts);
  if (!Number.isFinite(n) || n <= 0) return null;
  const d = new Date(n > 1e12 ? n : n * 1000);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

/* ── 二 · EigenFlux 本机路径（只算路径，不回显绝对路径给渲染层） ── */

function resolveHome(env, userHome) {
  const raw = env && env.EIGENFLUX_HOME ? String(env.EIGENFLUX_HOME).trim() : "";
  return raw || path.join(String(userHome || ""), ".eigenflux");
}

function homeLabel(home) {
  const base = path.basename(String(home || ""));
  return base || "(未解析)";
}

function eigenfluxPaths(home, server) {
  const root = path.join(String(home || ""), "servers", String(server || "eigenflux"));
  return {
    root: root,
    profile: path.join(root, "profile.json"),
    contacts: path.join(root, "contacts.json"),
    credentials: path.join(root, "credentials.json"),
    broadcasts: path.join(root, "data", "broadcasts"),
    messages: path.join(root, "data", "messages"),
  };
}

/* entries: [{file, name, bytes, mtimeMs}] -> 最新的那一条（空则 null） */
function pickLatest(entries) {
  const rows = Array.isArray(entries) ? entries.slice() : [];
  rows.sort((a, b) => (Number(b.mtimeMs) || 0) - (Number(a.mtimeMs) || 0));
  return rows[0] || null;
}

/* ── 三 · 归一化：只保留展示需要的字段，且全部过脱敏 ── */

function normalizeProfile(raw) {
  const r = raw && typeof raw === "object" ? raw : {};
  const bio = redact(clip(r.bio, LIMITS.bio_chars));
  return {
    agent_name: clip(r.agent_name, 80),
    agent_id: clip(r.agent_id, 64),
    bio: bio.text,
    /* 只报"邮箱是否绑定"这一个布尔 —— 值本身永不回显 */
    email_bound: !!String(r.email || "").trim(),
    redactions: bio.redactions,
  };
}

function normalizeFriend(row) {
  const r = row && typeof row === "object" ? row : {};
  const remark = redact(clip(r.remark, 80));
  return {
    agent_id: clip(r.agent_id, 64),
    agent_name: redact(clip(r.agent_name, 80)).text,
    remark: remark.text,
    friend_since: toIso(r.friend_since),
    redactions: remark.redactions,
  };
}

function normalizeFeedItem(row) {
  const r = row && typeof row === "object" ? row : {};
  const content = redact(clip(r.raw_content, LIMITS.content_chars));
  return {
    item_id: clip(r.item_id, 64),
    author: redact(clip(r.display_name, 80)).text,
    author_id: clip(r.author_agent_id, 64),
    relation: clip(r.author_relation, 32),
    type: clip(r.broadcast_type, 32),
    created_at: toIso(r.created_at),
    domains: Array.isArray(r.domains) ? r.domains.map((x) => clip(x, 24)).slice(0, 6) : [],
    keywords: Array.isArray(r.keywords) ? r.keywords.map((x) => clip(x, 24)).slice(0, 6) : [],
    expected_response: clip(r.expected_response, 48),
    truncated_at_source: r.raw_content_truncated === true,
    content: content.text,
    redactions: content.redactions,
  };
}

function normalizeMessage(row) {
  const r = row && typeof row === "object" ? row : {};
  const content = redact(clip(r.content, LIMITS.content_chars));
  return {
    msg_id: clip(r.msg_id, 64),
    conv_id: clip(r.conv_id, 64),
    sender_id: clip(r.sender_id, 64),
    sender_name: redact(clip(r.sender_name, 80)).text,
    is_official: r.sender_is_official === true,
    created_at: toIso(r.created_at),
    content: content.text,
    redactions: content.redactions,
  };
}

/* lists: [[row,...], ...] -> 去重(按 msg_id) + 按时间倒序 + 截断 */
function mergeMessages(lists, limits) {
  const lim = limits || LIMITS;
  const seen = Object.create(null);
  const out = [];
  (Array.isArray(lists) ? lists : []).forEach((rows) => {
    (Array.isArray(rows) ? rows : []).forEach((row) => {
      if (!row || typeof row !== "object") return;
      const key = String(row.msg_id || "") ||
        JSON.stringify([row.sender_id, row.created_at, row.content]);
      if (seen[key]) return;
      seen[key] = true;
      out.push(normalizeMessage(row));
    });
  });
  out.sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
  return out.slice(0, lim.messages);
}

/* ── 四 · 数字人形象库（真扫盘，缺件如实列） ── */

function scanPetResources(fsApi, resourcesDir) {
  const out = [];
  if (!resourcesDir || !fsApi || typeof fsApi.existsSync !== "function") return out;
  if (!fsApi.existsSync(resourcesDir)) return out;
  let names;
  try { names = fsApi.readdirSync(resourcesDir); } catch (err) { return out; }
  names.sort().forEach((name) => {
    const dir = path.join(resourcesDir, name);
    let st;
    try { st = fsApi.statSync(dir); } catch (err) { return; }
    if (!st.isDirectory()) return;
    const entry = {
      name: name, model3: null, moc3: null, bytes: 0,
      motions: 0, expressions: 0, textures: 0, issues: [],
    };
    let files = [];
    try { files = fsApi.readdirSync(dir); } catch (err) { files = []; }
    files.sort().forEach((f) => {
      const p = path.join(dir, f);
      let s;
      try { s = fsApi.statSync(p); } catch (err) { return; }
      if (s.isDirectory()) {
        let inner = [];
        try { inner = fsApi.readdirSync(p); } catch (err) { inner = []; }
        if (f === "motions") entry.motions = inner.filter((x) => x.endsWith(".json")).length;
        else if (f === "expressions") entry.expressions = inner.filter((x) => x.endsWith(".json")).length;
        else if (/\.(2048|4096)$/.test(f) || /^textures?/i.test(f)) {
          entry.textures += inner.filter((x) => x.toLowerCase().endsWith(".png")).length;
        }
        return;
      }
      if (f.endsWith(".model3.json")) { entry.model3 = f; entry.bytes += Number(s.size) || 0; }
      else if (f.endsWith(".moc3")) { entry.moc3 = f; entry.bytes += Number(s.size) || 0; }
    });
    if (!entry.model3) entry.issues.push("缺 model3.json · 起不来");
    if (!entry.moc3) entry.issues.push("缺 moc3 · 起不来");
    if (!entry.textures) entry.issues.push("无贴图目录 · 会是空壳");
    entry.ready = entry.issues.length === 0;
    out.push(entry);
  });
  return out.slice(0, LIMITS.models);
}

/* ── 五 · 载体就绪表（取不到一律不显绿） ── */

function buildCarriers(input) {
  const i = input || {};
  const py = i.python || {};
  const pyChecked = py.checked === true;
  const pyReady = pyChecked && py.pyside6 === true && py.live2d === true;
  const pyMissing = pyChecked
    ? [py.pyside6 === true ? null : "PySide6", py.live2d === true ? null : "live2d-py"]
        .filter(Boolean)
    : [];
  const pyReason = !pyChecked
    ? "未探测（点「刷新就绪态」现测，不猜）"
    : pyReady
      ? String(py.interpreter || "py -3.10") + " · PySide6 + live2d 就位"
      : "缺依赖：" + pyMissing.join(" + ") +
        " —— 补法：py -3.10 -m pip install PySide6 live2d-py";

  const electronPresent = i.electronPresent === true;
  const panelReachable = i.panelReachable === true;
  const shellReady = electronPresent && panelReachable;
  const shellReason = !electronPresent
    ? "Electron 运行时不在位（holo_pet/node_modules/electron/dist/electron.exe）"
    : !panelReachable
      ? "本地面板 :8765 未就绪 —— 数字人壳没有可加载的页面"
      : "Electron 运行时在位 · 面板 :8765 已就绪";

  return {
    primary: shellReady ? "desktop-shell" : (pyReady ? "live2d-pet" : null),
    carriers: [
      {
        id: "desktop-shell",
        title: "桌面数字人壳（Electron · 推荐）",
        ready: shellReady,
        reason: shellReason,
        note: i.electronBytes
          ? ("运行时 " + Math.round(Number(i.electronBytes) / 1048576) + " MB")
          : null,
      },
      {
        id: "live2d-pet",
        title: "Live2D 桌宠（potato_pet）",
        ready: pyReady,
        reason: pyReason,
        note: Number(i.models) > 0 ? (Number(i.models) + " 个形象在库") : null,
      },
      /* 🔴 2026-10-10（主人令）**补一格：面板桥自己没人拉**。
         主人实测：「打开 APP 里面还是一大堆没连接没配置」—— 真探后真因不是一堆配置，
         而是**面板桥 :8765 没在跑**（capability-audit 那两条断连 bridge.panel-8765 /
         svc.panel-bridge-raw 其实是同一件事）。
         而本件上面早就写好了一句「本地面板 :8765 未就绪」—— **它知道，但什么都不做**。
         （open-full-panel.bat 会自己探+拉，所以走那个入口看不到；走的入口不同，结果不同。）
         ⇒ 把「拉桥」补成一条载体，由引导链在建窗前召唤。**只出命令，真 spawn 仍在 main.cjs。** */
      {
        id: "panel-bridge",
        title: "本地面板桥 :8765（launch_panel.py）",
        ready: true,      /* 只用仓内 launch_panel.py + stdlib；幂等（先探再起） */
        reason: "幂等：已在跑则直接返回 0；起法 = py -3.14 holo_pet/launch_panel.py --host 127.0.0.1 --port 8765 --no-browser",
        note: panelReachable ? "当前已在听 :8765" : "当前未在听 :8765 —— 建窗前应由壳拉起",
      },
    ],
  };
}

/* ── 六 · 召唤计划：只出命令，真 spawn 留在 main.cjs ── */

function summonPlan(input) {
  const i = input || {};
  const carrier = String(i.carrier || "desktop-shell");
  const root = String(i.repoRoot || "");
  if (!root) return { ok: false, carrier: carrier, reason: "找不到仓库根（上层没有 gbt_allinone）" };

  if (carrier === "desktop-shell") {
    const exe = String(i.electronExe || "");
    if (!exe) return { ok: false, carrier: carrier, reason: "没有可用的 Electron 运行时路径" };
    return {
      ok: true, carrier: carrier, exe: exe,
      argv: [path.join(root, "holo_pet", "desktop", "main.cjs")],
      cwd: path.join(root, "holo_pet"),
      detached: true,
      reason: "起独立桌面窗口（无边框 · 置顶 · 可拖动）",
    };
  }
  if (carrier === "panel-bridge") {
    /* 🔴 2026-10-10（主人令）：面板桥（127.0.0.1:8765）**没人负责拉起** ——
       壳的 windows.json 写着「它正在 8765 跑」，但壳自己不拉 ⇒ 直接开壳时面板一片「未连接」。
       --no-browser：壳拉起时不弹浏览器；launch_panel.py 本身幂等（先探，已在跑就返回 0）。 */
    return {
      ok: true, carrier: carrier, exe: String(i.pythonExe || "py"),
      argv: ["-3.14", path.join(root, "holo_pet", "launch_panel.py"),
             "--host", "127.0.0.1", "--port", "8765", "--no-browser"],
      cwd: path.join(root, "holo_pet"),
      detached: true,
      reason: "起本地面板桥 :8765（幂等：先探再起；只为数字人壳有页可加载）",
    };
  }
  if (carrier === "live2d-pet") {
    return {
      ok: true, carrier: carrier, exe: String(i.pythonExe || "py"),
      argv: ["-3.10", path.join(root, "potato_pet", "main.py")],
      cwd: path.join(root, "potato_pet"),
      detached: true,
      reason: "起 PySide6 Live2D 桌宠窗口",
    };
  }
  return { ok: false, carrier: carrier, reason: "未知载体：" + carrier };
}

/* pid 存活探测：ESRCH / EINVAL 一律当"不在"（失败方向安全） */
function isAlive(pid, kill) {
  const n = Number(pid);
  if (!Number.isFinite(n) || n <= 0) return false;
  const send = typeof kill === "function" ? kill : process.kill.bind(process);
  try { send(n, 0); return true; } catch (err) { return false; }
}

module.exports = {
  LIMITS: LIMITS,
  REDACT_PLACEHOLDER: REDACT_PLACEHOLDER,
  redact: redact,
  clip: clip,
  toIso: toIso,
  resolveHome: resolveHome,
  homeLabel: homeLabel,
  eigenfluxPaths: eigenfluxPaths,
  pickLatest: pickLatest,
  normalizeProfile: normalizeProfile,
  normalizeFriend: normalizeFriend,
  normalizeFeedItem: normalizeFeedItem,
  normalizeMessage: normalizeMessage,
  mergeMessages: mergeMessages,
  scanPetResources: scanPetResources,
  buildCarriers: buildCarriers,
  summonPlan: summonPlan,
  isAlive: isAlive,
};
