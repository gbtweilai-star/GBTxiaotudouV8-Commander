/* GBT小土豆V8 · 纯函数决策层（无 fs 副作用 · 可被 node --test 钉住）
 *
 * ⚠️ 本文件是**按 main.cjs 调用契约重建**的，不是原件（原件已丢失）。
 *    重建依据：main.cjs 的 15 个调用点 ——
 *      · LIMITS.friends / LIMITS.feed_items       1024/1187/1204
 *      · scanPetResources(fs, dir) → models[]      1025
 *      · buildCarriers({...}) → { carriers, primary }  1033
 *      · summonPlan({...}) → { ok, exe, argv, cwd, reason }  1067
 *      · resolveHome(env, homedir) → home          1154
 *      · eigenfluxPaths(home, server) → paths      1155
 *      · homeLabel(home) → 短标签                   1160
 *      · redact(text) → 脱敏文本                    1128（注释写明"邮箱只出布尔，绝对路径不回显"）
 *      · pickLatest(files) → file|null             1194
 *      · normalizeProfile / normalizeFriend / normalizeFeedItem  1179/1187/1204
 *      · mergeMessages(lists, LIMITS) → rows       1226
 *      · toIso(ms) → ISO 字符串                     1207
 *
 * 三条红线（照仓里既有说法，不新立判据）：
 *   ① **绝对路径不回显**：所有对外文本先过 redact()，只留 basename；
 *   ② **邮箱只出布尔**：不把地址原样交给渲染层；
 *   ③ 这里**不做 IO**：fs 由调用方传进来，本模块只管归一化与判据，这样才能单测。
 */
"use strict";

const path = require("path");

/* 面板桥端口：与 main.cjs 的 PANEL 默认值、panel_server.py 的 --port 默认值三处一致。 */
const PANEL_PORT = 8765;
const PANEL_HOST = "127.0.0.1";

/* 各处的截断上限。数值是**展示口径**，不是数据完整性口径：
   取少一点让首屏能扫读，取多一点只会变成一屏流不完的列表。 */
const LIMITS = {
  friends: 60,
  feed_items: 40,
  messages: 80,
  message_text: 280,
  feed_text: 400,
};

/* ── 小工具 ────────────────────────────────────────────── */

function str(v) {
  return v == null ? "" : String(v);
}

function safeBasename(p) {
  try { return path.basename(str(p)) || str(p); } catch (err) { return str(p); }
}

/* 路径片段 → 只留文件名。
   🔴 这里有个**必须处理**的现实：本机的用户名带空格（"Lenovo E14 Gen 5"），
      用 `[^\s]*` 去卡路径会在第一个空格处断掉，把 `C:\Users\Lenovo` 当成整条路径，
      结果留下一个 `Lenovo` —— 既没抹干净，又丢了真正的文件名。
   ⇒ 允许空格，但用"中文标点 + CJK + 引号括号"当终止符；
      再对取出的 basename 做一次尾部清洗（万一后面紧跟的是中文说明）。 */
function shortenPath(segment) {
  const raw = str(segment).trim();
  if (!raw) return raw;
  const base = safeBasename(raw);
  /* basename 里混进了后续中文说明时，截到第一个 CJK 之前。 */
  const cut = base.search(/[\u4e00-\u9fa5]/);
  return cut > 0 ? base.slice(0, cut).trim() : base;
}

/* 脱敏：绝对路径 → basename；邮箱 → 占位符。
   注意顺序：先处理路径（路径里可能含 @），再处理邮箱。 */
function redact(text) {
  let s = str(text);
  if (!s) return s;

  /* Windows 盘符路径：允许空格，遇引号/尖括号/竖线/中文标点/换行停 */
  s = s.replace(/[A-Za-z]:\\[^\r\n"'<>|，。；、！？（）《》【】]*/g, shortenPath);
  /* POSIX 家目录路径：同上 */
  s = s.replace(/\/(?:Users|home)\/[^\r\n"'<>|，。；、！？（）《》【】]*/g, shortenPath);
  /* 邮箱：不保留原值，只留占位符与布尔语义 */
  s = s.replace(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, "<email>");
  return s;
}

function toIso(ms) {
  const n = Number(ms);
  if (!Number.isFinite(n) || n <= 0) return null;
  try { return new Date(n).toISOString(); } catch (err) { return null; }
}

/* 从一堆文件里挑 mtime 最新的那个。main.cjs 只给 mtimeMs。 */
function pickLatest(files) {
  const list = Array.isArray(files) ? files.filter(Boolean) : [];
  if (!list.length) return null;
  let best = list[0];
  for (const f of list) {
    if ((Number(f.mtimeMs) || 0) > (Number(best.mtimeMs) || 0)) best = f;
  }
  return best;
}

/* ── EigenFlux 本机路径推导 ─────────────────────────────── */

/* 数据根默认 ~/.eigenflux；允许环境变量改道（取证/多实例时用）。 */
function resolveHome(env, homedir) {
  const e = env || {};
  const override = str(e.GBT_EIGENFLUX_HOME || e.EIGENFLUX_HOME).trim();
  if (override) return override;
  return str(homedir);
}

/* 不回显完整绝对路径 —— 只给一个能认出来的短标签。 */
function homeLabel(home) {
  const h = str(home).trim();
  if (!h) return "未知主目录";
  /* 能认成家目录就给 ~，否则给最后一段。 */
  if (/[\\/](Users|home)[\\/][^\\/]+[\\/]?$/i.test(h)) return "~";
  return safeBasename(h);
}

function eigenfluxPaths(home, server) {
  const root = path.join(str(home), ".eigenflux", "servers", str(server || "eigenflux"));
  return {
    root: root,
    profile: path.join(root, "profile.json"),
    contacts: path.join(root, "contacts.json"),
    broadcasts: path.join(root, "broadcasts"),
    messages: path.join(root, "messages"),
  };
}

/* ── 数字人载体 ─────────────────────────────────────────── */

/* 真扫形象库目录。model 目录通常是 potato_pet/resources，里面一个形象一个子目录。
   只回名字与大小 —— 绝对路径不出这个函数。 */
function scanPetResources(fsMod, dir) {
  const out = [];
  if (!dir) return out;
  let names = [];
  try { names = fsMod.readdirSync(dir); } catch (err) { return out; }

  for (const n of names) {
    if (!n || n.charAt(0) === ".") continue;
    const abs = path.join(dir, n);
    let st = null;
    try { st = fsMod.statSync(abs); } catch (err) { continue; }

    if (st.isDirectory()) {
      out.push({ name: n, kind: "dir", bytes: 0, label: n });
      continue;
    }
    /* 只把"像模型/形象"的文件算进去，别把 README 也算成形象 */
    if (!/\.(json|model3\.json|glb|gltf|png|webp|moc3)$/i.test(n)) continue;
    out.push({
      name: n,
      kind: /\.(glb|gltf)$/i.test(n) ? "gltf" : (/\.moc3$/i.test(n) ? "live2d" : "data"),
      bytes: Number(st.size) || 0,
      label: n.replace(/\.[^.]+$/, ""),
    });
  }
  return out;
}

/* 载体就绪表。**每一条都带原因** —— 不就绪必须说清为什么，不写"灰了不说"。
   id 是 summonPlan 的入参，不能随手改名（ensurePanelBridge 硬用 "panel-bridge"）。 */
function buildCarriers(opt) {
  const o = opt || {};
  const py = o.python || {};
  const electronPresent = o.electronPresent === true;
  const panelReachable = o.panelReachable === true;
  const models = Number(o.models) || 0;

  const carriers = [];

  carriers.push({
    id: "panel-bridge",
    label: "面板桥 :" + PANEL_PORT,
    kind: "service",
    ready: panelReachable,
    reason: panelReachable
      ? "已在服务"
      : "没在服务：点「召唤」会拉起 holo_pet/panel_server.py（只读 HTTP，不写盘）",
  });

  carriers.push({
    id: "live2d",
    label: "Python 腿 · live2d",
    kind: "python",
    ready: py.checked === true && py.live2d === true,
    reason: py.checked !== true
      ? "解释器没探通（" + str(py.interpreter || "没记录") + "）—— 按未探测记，不猜"
      : (py.live2d === true ? "live2d 包已装" : "解释器通了，但没装 live2d 包"),
  });

  carriers.push({
    id: "pyside6",
    label: "Python 腿 · PySide6",
    kind: "python",
    ready: py.checked === true && py.pyside6 === true,
    reason: py.checked !== true
      ? "解释器没探通（" + str(py.interpreter || "没记录") + "）"
      : (py.pyside6 === true ? "PySide6 已装" : "解释器通了，但没装 PySide6"),
  });

  carriers.push({
    id: "electron",
    label: "Electron 载体",
    kind: "electron",
    ready: electronPresent,
    reason: electronPresent
      ? "electron.exe 在位"
      : "holo_pet 下的 electron 不在位（形象库 " + models + " 项，但没运行时）",
  });

  const primary = carriers.filter((c) => c.ready)[0] || carriers[0];
  return { carriers: carriers, primary: primary };
}

/* 召唤计划：**纯函数**，只说"该跑什么"，不 spawn、不写盘。
   main.cjs 拿到后自己 spawn，并对"裸命令名 vs 路径"分开判（见 1083 行注释）。 */
function summonPlan(opt) {
  const o = opt || {};
  const carrier = str(o.carrier).trim();
  const root = str(o.repoRoot).trim();
  const pythonExe = str(o.pythonExe || "py").trim() || "py";
  const electronExe = str(o.electronExe).trim();

  if (!root) return { ok: false, reason: "没有仓库根，不知道该从哪起进程" };
  if (!carrier) return { ok: false, reason: "没指定载体" };

  if (carrier === "panel-bridge") {
    /* 注意：仓里 blocked.html 的提示写的是 launch_panel.py，但**盘上是 panel_server.py**。
       这里以后者为准（前者不存在）。参数与 panel_server.py 的 argparse 一致。 */
    return {
      ok: true,
      carrier: carrier,
      exe: pythonExe,
      argv: [
        "-3.14",
        path.join(root, "holo_pet", "panel_server.py"),
        "--host", PANEL_HOST,
        "--port", String(PANEL_PORT),
      ],
      cwd: root,
      reason: "起本地面板桥（只读 HTTP，不写盘）",
    };
  }

  if (carrier === "live2d" || carrier === "pyside6") {
    /* 形象库目录若不在位，这里仍给出计划；就绪判定由 buildCarriers 负责，
       main.cjs 会拿 ready 再拦一次（不靠这里猜）。 */
    return {
      ok: true,
      carrier: carrier,
      exe: pythonExe,
      argv: [
        "-3.10",
        path.join(root, "potato_pet", "run_pet.py"),
        "--carrier", carrier,
      ],
      cwd: root,
      reason: "起 Python 数字人窗（" + carrier + "）",
    };
  }

  if (carrier === "electron") {
    if (!electronExe) return { ok: false, reason: "没有 electron 可执行文件的路径" };
    return {
      ok: true,
      carrier: carrier,
      exe: electronExe,
      argv: [path.join(root, "potato_pet")],
      cwd: root,
      reason: "用 Electron 起形象库窗",
    };
  }

  return { ok: false, reason: "没有这个载体：" + (carrier || "(空)") };
}

/* ── EigenFlux 归一化 ───────────────────────────────────── */

function normalizeProfile(doc) {
  const d = doc && typeof doc === "object" ? doc : {};
  const counts = d.counts && typeof d.counts === "object" ? d.counts : {};
  return {
    name: redact(str(d.name || d.display_name || "")),
    handle: redact(str(d.handle || d.username || "")),
    bio: redact(str(d.bio || d.description || "")),
    avatar: str(d.avatar || d.avatar_url || ""),
    created_at: str(d.created_at || d.createdAt || ""),
    counts: {
      friends: Number(counts.friends) || 0,
      posts: Number(counts.posts || counts.feed) || 0,
    },
  };
}

function normalizeFriend(item) {
  const d = item && typeof item === "object" ? item : {};
  return {
    id: str(d.id || d.user_id || d.uid || ""),
    name: redact(str(d.name || d.display_name || d.nickname || "")),
    handle: redact(str(d.handle || d.username || "")),
    note: redact(str(d.note || d.remark || d.bio || "")),
    since: str(d.since || d.created_at || d.added_at || ""),
  };
}

function normalizeFeedItem(item) {
  const d = item && typeof item === "object" ? item : {};
  const text = redact(str(d.text || d.content || d.body || ""));
  const author = d.author && typeof d.author === "object" ? d.author : {};
  return {
    id: str(d.id || d.post_id || ""),
    at: str(d.at || d.created_at || d.timestamp || ""),
    author: redact(str(author.name || d.author_name || d.authorName || "")),
    author_handle: redact(str(author.handle || d.author_handle || "")),
    text: text.length > LIMITS.feed_text ? text.slice(0, LIMITS.feed_text) + "…" : text,
    likes: Number(d.likes || d.like_count) || 0,
    comments: Number(d.comments || d.comment_count) || 0,
  };
}

/* 合并多个私信文件的行。
   去重键优先 id，没有 id 就用「对方+时间+正文」的指纹。
   时间倒序（新的在上），再按 LIMITS 截断。 */
function mergeMessages(lists, limits) {
  const lim = limits || LIMITS;
  const cap = Number(lim.messages) || LIMITS.messages;
  const textCap = Number(lim.message_text) || LIMITS.message_text;

  const seen = new Set();
  const out = [];

  (Array.isArray(lists) ? lists : []).forEach((rows) => {
    if (!Array.isArray(rows)) return;
    rows.forEach((row) => {
      const d = row && typeof row === "object" ? row : {};
      const text = redact(str(d.text || d.content || d.body || ""));
      const at = str(d.at || d.created_at || d.timestamp || "");
      const from = redact(str(d.from || d.sender || d.from_name || ""));
      const id = str(d.id || d.message_id || "");

      const key = id || (from + "|" + at + "|" + text.slice(0, 40));
      if (seen.has(key)) return;
      seen.add(key);

      out.push({
        id: id,
        at: at,
        from: from,
        to: redact(str(d.to || d.recipient || "")),
        text: text.length > textCap ? text.slice(0, textCap) + "…" : text,
      });
    });
  });

  out.sort((a, b) => {
    const ta = Date.parse(a.at) || 0;
    const tb = Date.parse(b.at) || 0;
    return tb - ta;
  });

  return out.slice(0, cap);
}

module.exports = {
  LIMITS,
  redact,
  toIso,
  pickLatest,
  resolveHome,
  homeLabel,
  eigenfluxPaths,
  scanPetResources,
  buildCarriers,
  summonPlan,
  normalizeProfile,
  normalizeFriend,
  normalizeFeedItem,
  mergeMessages,
  PANEL_PORT,
  PANEL_HOST,
};
