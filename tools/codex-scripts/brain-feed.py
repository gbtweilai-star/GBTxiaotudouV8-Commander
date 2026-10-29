# -*- coding: utf-8 -*-
"""神经可视化 · 数据面（窗 E 的唯一数据出口，2026-09-23 起）。

## 它是什么

把**本仓真实的四样东西**算成一张脑图数据，落成 `brain-data.js` 给窗 E 读：

| 层 | 真出处 | 现读 |
|---|---|---|
| 皮层核心 | DSH 主导核（对话面就是它） | 1 个 |
| **束长环** | `caps_registry` 的 **domain** 字段 | **29 个真实能力域**（**不是**参考稿里编的 22） |
| **触手层** | `caps_registry` 的**每一个能力位** + `state/skill_atlas.json` 的技能 | **161 能力位** + 341 技能 |
| 突触连线 | 域→能力位的**从属关系**（真字段）+ `code_structure.deps` 的内部边 | 真实，不画假线 |
| **执行脉冲** | `store/audit.jsonl` 里 **真的发生过**的 `call` 事件 | 按时间倒序取最近 N 条 |
| 执行路线 | `store/sync_steps.json` 的**未收步** | 真欠的活 |
| 门禁环 | `security/policy.py` 的作用域表 | 14 个作用域 |

## 三条纪律

1. **不许编数据**。参考稿里有 `setInterval` 伪造 AI 回复、`Math.random()` 伪造活跃数 ——
   那些在本仓是 P0（编造指标）。没有实时流就**如实写"静默"**，不拿随机数装作在跑。
2. **每个点都要能追到出处**：能力位带 `kind`，脉冲带 `ts`/`event`/`kind`。
3. **缺源就说缺**（`null` + `why`），**不许显示成 0**。

## 用法

    py -3.14 tools/codex-scripts/brain-feed.py
    py -3.14 tools/codex-scripts/brain-feed.py --out holo_pet_w3/brain/brain-data.js
"""
import argparse
import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
STORE = ROOT / "gbt_allinone" / "store"
AUDIT = STORE / "audit.jsonl"
STEPS = STORE / "sync_steps.json"
ATLAS = ROOT / "state" / "skill_atlas.json"

PULSE_N = 90          # 取最近多少条真事件当脉冲
PULSE_MAX_AGE_S = 6 * 3600   # 超过这个岁数的**不算"活"**，只算"史"

# 域 → 中文标签（**只为显示**；域 id 一律用 registry 里的真值，绝不改写）
DOMAIN_CN = {
    "system": "系统", "llm": "模型", "pipeline": "流水线", "tentacle": "手眼网耳",
    "engine": "引擎", "mind": "心智", "creation": "创作", "recon": "侦察",
    "tools": "工具", "data": "数据", "security": "安全", "finance": "金融",
    "longrun": "长跑", "devour": "吞噬", "video": "视频", "project": "项目",
    "voice": "声音", "device": "设备", "brain": "大脑", "comms": "通信",
    "vision": "视觉", "automation": "自动化", "life": "生活", "image_video": "图像视频",
    "integration": "集成", "framework": "框架", "infra": "基础设施",
    "social": "社交", "collab": "协作",
}


def _hue(i: int, n: int) -> float:
    """按域序号给一个色相。**不写 hex**：色相是数，颜色由前端算 ⇒ 换配色不用改数据。

    锚在品牌三色的色相族上（青 ~187 / 紫 ~262 / 金 ~35），在它们之间铺开，
    于是整张图天然是"家族色"而不是彩虹盘（彩虹盘是 AI 味特征之一）。
    """
    family = [187.0, 262.0, 35.0]
    t = (i / max(n, 1)) * len(family)
    a, b = family[int(t) % 3], family[(int(t) + 1) % 3]
    return round((a + (b - a) * (t - int(t))) % 360, 1)


def _caps() -> tuple:
    """能力位：真出处 `caps_registry`。返回 `(benign, unimpl)`。"""
    try:
        from gbt_allinone.caps_registry import BENIGN_CAPS, UNIMPLEMENTED_CAPS
    except Exception as e:                                          # noqa: BLE001
        return None, None, "%s: %s" % (type(e).__name__, str(e)[:120])
    return dict(BENIGN_CAPS), tuple(UNIMPLEMENTED_CAPS), ""


def _audit_pulses(limit: int) -> tuple:
    """执行脉冲：**真发生过的** `call` 事件。取不到就说取不到。"""
    if not AUDIT.is_file():
        return None, "没有审计账本 %s" % AUDIT.name
    rows = []
    try:
        with AUDIT.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"call"' not in line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:                                   # noqa: BLE001
                    continue
                if e.get("event") != "call":
                    continue
                m = e.get("meta") or {}
                rows.append({"ts": float(e.get("ts") or 0), "iso": e.get("iso"),
                             "kind": str(m.get("kind") or m.get("cap") or "?"),
                             "ok": bool(m.get("ok", True)),
                             "synced": bool(m.get("synced")),
                             "entry": m.get("synced_entry")})
    except OSError as e:
        return None, "账本读不动：%s" % str(e)[:100]
    rows.sort(key=lambda r: -r["ts"])
    return rows[:limit], ""


def _steps() -> tuple:
    """执行路线：`sync_steps.json` 的未收步（**真欠的活**）。"""
    if not STEPS.is_file():
        return [], ""
    try:
        d = json.loads(STEPS.read_text(encoding="utf-8-sig")) or {}
    except Exception as e:                                          # noqa: BLE001
        return None, "步账读不动：%s" % str(e)[:80]
    now = time.time()
    out = []
    for sid, st in d.items():
        t0 = float((st or {}).get("t0") or 0)
        out.append({"id": sid, "goal": str((st or {}).get("goal") or "")[:80],
                    "age_h": round((now - t0) / 3600, 2) if t0 else None})
    out.sort(key=lambda x: -(x["age_h"] or 0))
    return out, ""


def _skills() -> tuple:
    """技能：`state/skill_atlas.json` 的条目（只取名字与根，用于雾状点云）。"""
    if not ATLAS.is_file():
        return None, "没有图鉴 %s" % ATLAS.name
    try:
        d = json.loads(ATLAS.read_text(encoding="utf-8-sig"))
    except Exception as e:                                          # noqa: BLE001
        return None, "图鉴读不动：%s" % str(e)[:80]
    items = d.get("skills") if isinstance(d, dict) else d
    return [{"name": s.get("name"), "root": s.get("root")} for s in (items or [])], ""


def _scopes() -> list:
    """门禁：`policy` 的作用域表（真值，非抄写）。"""
    try:
        from gbt_allinone.security import policy
        return sorted((policy.describe().get("scope_descriptions") or {}).keys())
    except Exception:                                               # noqa: BLE001
        return []


# ── 真实连接：能力位 → 能力位 ────────────────────────────────────────────────
# 风哥令：「**所有连接都要可视化**」「大脑执行层跟什么连接……哪些连接也会根据对应连接亮起来」。
#
# 真出处链（一环都不猜）：
#   ① `caps_registry` 每个能力位都有 **`handler`** 字段（实测 150/150 都有）—— 那是真实函数名；
#   ② AST 扫 `gbt_allinone/**/*.py`，找出**哪个文件定义了这个 handler**；
#   ③ AST 扫每个文件的 `import`，得到**真实的内部依赖边**；
#   ④ 两条拼起来：文件 A 依赖文件 B ⇒ 「A 的能力位」连着「B 的能力位」。
# ⇒ 图上的每一根线，都能顺着 handler 名字回查到源码。
# 扫盘必须**剪枝**（2026-09-23 实测踩到）：
#   `gbt_allinone/` 底下挂着 `store/native_browser/profile/`（浏览器 profile，上万个文件）
#   和 `.pylibs/`（vendored 的 win32comext 示例）—— 不剪掉的话 AST 全盘扫会**跑到超时**，
#   数据面直接卡死。这不是性能优化，是**能不能产出**的问题。
_SKIP_PARTS = {"__pycache__", "store", ".pylibs", "archived_logs", "node_modules", ".git"}


def _py_files(base: Path):
    """只走**我们自己写的** Python：剪掉 store / .pylibs 等非本体的目录。"""
    for f in base.rglob("*.py"):
        if _SKIP_PARTS & set(f.parts):
            continue
        yield f


def _handler_files() -> tuple:
    import ast
    try:
        from gbt_allinone.caps_registry import BENIGN_CAPS
    except Exception as e:                                          # noqa: BLE001
        return {}, {}, "%s: %s" % (type(e).__name__, str(e)[:100])
    want = {}
    for kind, meta in BENIGN_CAPS.items():
        h = str((meta or {}).get("handler") or "").strip()
        if h:
            want.setdefault(h, []).append(kind)
    base = ROOT / "gbt_allinone"
    found = {}
    for f in _py_files(base):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, OSError, ValueError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in want:
                found.setdefault(node.name, str(f.relative_to(ROOT)).replace("\\", "/"))
    kind2file, mapped = {}, 0
    for h, kinds in want.items():
        if h not in found:
            continue
        for k in kinds:
            kind2file[k] = found[h]
            mapped += 1
    return kind2file, found, "" if mapped else "一个 handler 都没落到文件上"


def _dispatch_files() -> tuple:
    """**按真实分派支路**取每个能力位依赖了哪些文件（替代"按 handler 找函数"）。

    为什么换：实测 `handler` 名只有 11/150 能在 `gbt_allinone/**` 里找到同名函数 ——
    多数能力位是 `_run_benign` 里的一条 **if 支路**（实测 **143 处** `kind ==` 比较），
    不是独立函数。用户令「所有连接都要可视化」，那就必须按**真实分派结构**取，不能按名字猜。

    每条支路里：`import` 了什么模块 + 调了 api.py 里哪个顶层函数 ⇒ 就是它的真实依赖面。
    """
    import ast
    p = ROOT / "gbt_allinone" / "api.py"
    if not p.is_file():
        return {}, "没有 gbt_allinone/api.py"
    try:
        tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, OSError) as e:
        return {}, "api.py 解析不了：%s" % str(e)[:80]
    fn = None
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "_run_benign":
            fn = n
            break
    if fn is None:
        return {}, "api.py 里没有 _run_benign（分派结构变了，本器要重看）"

    api_rel = "gbt_allinone/api.py"
    # api.py 自己定义的顶层函数名 —— 支路里调它们就是"依赖 api.py 本体"
    local_fns = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

    def resolve(mod: str, level: int, pkg: str) -> list:
        cands = []
        if level:
            up = pkg.rsplit("/", level - 1)[0] if level > 1 else pkg
            m = (up + "/" + (mod or "").replace(".", "/")).strip("/")
        else:
            m = (mod or "").replace(".", "/")
        for c in (m + ".py", m + "/__init__.py"):
            if (ROOT / c).is_file():
                cands.append(c)
        return cands

    pkg = "gbt_allinone"

    def branch_files(body: list) -> set:
        files, imported = set(), {}
        for node in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(node, ast.ImportFrom):
                for c in resolve(node.module or "", node.level, pkg):
                    files.add(c)
                # 子模块也要解析：`from .tools import code_graph` 若只 resolve(node.module)，
                # 得到的是 tools/__init__.py，漏掉真正的 gbt_allinone/tools/code_graph.py
                # ⇒ 新加的能力位在 brain 页上不出现（2026-10-29 实测 code_graph 缺席）。
                _base_mod = (node.module or "").replace(".", "/")
                for al in node.names:
                    _sub = (_base_mod + "/" + al.name).strip("/")
                    for c in resolve(_sub, node.level, pkg):
                        files.add(c)
                    if al.asname:
                        imported[al.asname] = _sub
            elif isinstance(node, ast.Import):
                for al in node.names:
                    for c in resolve(al.name, 0, pkg):
                        files.add(c)
                    imported[al.asname or al.name.split(".")[0]] = al.name
            elif isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Name) and f.id in local_fns:
                    files.add(api_rel)
                elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in imported:
                    for c in resolve(imported[f.value.id], 0, pkg):
                        files.add(c)
        return files or {api_rel}

    out = {}
    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue
        t = node.test
        vals = t.comparators if isinstance(t, ast.Compare) else []
        keys = [v.value for v in vals if isinstance(v, ast.Constant) and isinstance(v.value, str)]
        if not keys:
            continue
        fs = branch_files(node.body)
        for k in keys:
            out.setdefault(k, set()).update(fs)
    return {k: sorted(v) for k, v in out.items()}, ""


def _file_edges() -> dict:
    """真实的**内部 import 边**：`{文件: {被依赖文件: 次数}}`（AST 现读，不用采样）。"""
    import ast
    base = ROOT / "gbt_allinone"
    out = {}
    for f in _py_files(base):
        rel = str(f.relative_to(ROOT)).replace("\\", "/")
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, OSError, ValueError):
            continue
        pkg = f.parent.relative_to(ROOT).as_posix()
        deps = {}
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.ImportFrom):
                if node.level:                       # 相对 import：`from .tools import x`
                    up = pkg.rsplit("/", node.level - 1)[0] if node.level > 1 else pkg
                    mods.append((up + "/" + (node.module or "").replace(".", "/")).strip("/"))
                elif node.module and node.module.startswith("gbt_allinone"):
                    mods.append(node.module.replace(".", "/"))
            elif isinstance(node, ast.Import):
                for al in node.names:
                    if al.name.startswith("gbt_allinone"):
                        mods.append(al.name.replace(".", "/"))
            for m in mods:
                for cand in (m + ".py", m + "/__init__.py"):
                    t = ROOT / cand
                    if t.is_file() and cand != rel:
                        deps[cand] = deps.get(cand, 0) + 1
        if deps:
            out[rel] = deps
    return out


def _build_edges_multi(kind_files: dict, fedges: dict) -> tuple:
    """文件级依赖 → **能力位级连接**（一个能力位可以落在多个文件上）。

    判据：能力位 A 碰过的任一文件，依赖了能力位 B 碰过的任一文件 ⇒ A↔B 之间有一条**真边**。
    每条边都能回查：`A --(文件甲→文件乙)--> B`。返回 `(edges, 有依赖的文件数, why)`。
    """
    if not kind_files:
        return [], 0, "没有任何能力位落到文件上，建不了连接"
    byfile = {}
    for kind, fs in kind_files.items():
        for f in fs:
            byfile.setdefault(f, []).append(kind)
    edges, seen = [], {}
    for f, deps in fedges.items():
        for src in byfile.get(f, ()):          # 只从**真实实现文件**出发，不从公共库出发
            for dep, w in deps.items():
 # 丢掉"依赖包初始化文件"这类**噪音边**（2026-09-23 实测）：
                #    第一版跑出来 1500 条边**全是** `api.py → __init__.py`，
                #    于是每个能力位都连到每个能力位 —— 满屏线，但零信息。
                #    包 `__init__` 是命名空间入口，不是一条真实的"谁用谁"。
                if dep.endswith("/__init__.py") or dep.endswith("api.py"):
                    continue
                for dst in byfile.get(dep, ()):
                    if src == dst:
                        continue
                    key = (src, dst)
                    if key in seen:
                        seen[key]["w"] += w
                        continue
                    seen[key] = {"a": src, "b": dst, "w": w, "fa": f, "fb": dep}
    edges = sorted(seen.values(), key=lambda e: -e["w"])
    # 上限**为了可读**（MC：功能性高于一切）：线糊成一团就等于没有信息
    return edges[:1500], len(fedges), ""


def build() -> dict:
    benign, unimpl, why_caps = _caps()
    pulses, why_pulses = _audit_pulses(PULSE_N)
    steps, why_steps = _steps()
    skills, why_skills = _skills()

    # ── 束长：域 → 它的能力位。域 id 直接取 registry 的真值，一个都不改 ──
    bundles, nodes = [], []
    if benign:
        by_dom = {}
        for kind, meta in benign.items():
            d = str((meta or {}).get("domain") or "未分类")
            by_dom.setdefault(d, []).append(kind)
        for name in sorted(by_dom, key=lambda k: -len(by_dom[k])):
            bundles.append({"id": name, "label": DOMAIN_CN.get(name, name),
                            "n": len(by_dom[name])})
        for i, b in enumerate(bundles):
            b["hue"] = _hue(i, len(bundles))
            for kind in sorted(by_dom[b["id"]]):
                meta = benign[kind] or {}
                nodes.append({"id": kind, "bundle": b["id"],
                              "safe": bool(meta.get("safe")),
                              "impl": True,
                              "desc": str(meta.get("desc") or "")[:70]})
        # 仅登记未实现的那 11 个：**单独一层**，如实标 impl=false（不许混进已实现里充数）
        for k in (unimpl or ()):
            nodes.append({"id": k, "bundle": None, "safe": False, "impl": False,
                          "desc": "只登记，未实现（调用得到 unknown capability）"})

    # ── 脉冲：把审计事件按 kind 挂到它所属的域/能力位上 ──
    kind2bundle = {n["id"]: n["bundle"] for n in nodes}
    now = time.time()
    live = 0
    for p in (pulses or []):
        p["bundle"] = kind2bundle.get(p["kind"])
        p["age_s"] = round(now - p["ts"], 1) if p["ts"] else None
        if p["age_s"] is not None and p["age_s"] <= PULSE_MAX_AGE_S:
            live += 1

    # ── 真实连接（能力位之间）──
    disp, why_disp = _dispatch_files()          # 首选：真实分派支路
    kind2file_h, _h2f, why_map = _handler_files()   # 兜底：按 handler 找同名函数
    fedges = _file_edges()
    # 每个能力位 → 它**真实碰到的文件集合**（分派支路优先，其次 handler 定义处）
    kind_files = {}
    for n in nodes:
        if not n["impl"]:
            continue
        fs = list(disp.get(n["id"]) or [])
        if not fs and kind2file_h.get(n["id"]):
            fs = [kind2file_h[n["id"]]]
        kind_files[n["id"]] = fs
        n["files"] = fs
        n["file"] = fs[0] if fs else None
    edges, n_dep, why_edges = _build_edges_multi(kind_files, fedges)

    return {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": {
            "caps": "gbt_allinone/caps_registry.py（含 handler 字段）",
            "edges": "AST 现读：handler→文件→该文件的真实 import",
            "pulses": "gbt_allinone/store/audit.jsonl（event=call）",
            "steps": "gbt_allinone/store/sync_steps.json",
            "skills": "state/skill_atlas.json",
            "scopes": "gbt_allinone/security/policy.py",
        },
        "honest": {
            "caps_why": why_caps, "pulses_why": why_pulses,
            "steps_why": why_steps, "skills_why": why_skills,
            "edges_why": (why_disp or why_map or why_edges),
            "note": ("脉冲 = **真发生过的** call 事件；连接 = **真 import 边**抬上来的能力位关系。"
                     "没有就是没有，本页不用随机数冒充在跑（参考稿里的 setInterval 假回复属 P0，不采纳）"),
        },
        "totals": {
            "bundles": len(bundles),
            "caps_total": (len(benign) if benign else None),
            "caps_impl": (len(benign) if benign else None),
            "caps_unimpl": (len(unimpl) if unimpl else None),
            "skills": (len(skills) if skills is not None else None),
            "scopes": len(_scopes()),
            "pulses": (len(pulses) if pulses is not None else None),
            "pulses_live_6h": live,
            "open_steps": (len(steps) if steps is not None else None),
            "edges": len(edges),
            "cap_files": len({f for fs in kind_files.values() for f in fs}),
            "dep_files": n_dep,
        },
        "bundles": bundles,
        "nodes": nodes,
        # 门禁作用域的**名字**（不只是个数）：右栏要把它渲染成药丸，
        # 只给个数就只能显示"14 个"，说不清是哪 14 个 —— 那不算"该有的全都有"。
        "scope_names": _scopes(),
        "edges": edges,
        "pulses": pulses or [],
        "steps": steps or [],
        "skills": (skills or [])[:400],
        # 生成后端轮询池（`genrouter.py` 每一次调用都会刷新 `state/genpool.json`）。
        # 这里**只读那份件、不起进程** —— 面板要显示"几条腿、今天出了几张"，
        # 不该为它去 spawn 一个 Python（读文件既便宜又不会挂）。
        # 读不到就如实为 None（面板显示"口径件还没生成"），不编一个假的池子。
        "genpool": _genpool(),
        # 语音收件箱尾部（`intercom.py watch --inbox` 只追加写它）。
        # **主脑读它**才叫"听进去了"；面板显示它才叫"看得见"。取不到就是 None，不编。
        "voice_inbox": _voice_inbox(),
    }


def _voice_inbox(n=6):
    """读 `state/voice_inbox.jsonl` 的**尾部 n 条**（只读，不写、不清、不轮转）。"""
    try:
        p = ROOT / "state" / "voice_inbox.jsonl"
        if not p.is_file():
            return {"exists": False, "n": 0, "last": []}
        lines = [x for x in p.read_text(encoding="utf-8", errors="replace").splitlines()
                 if x.strip().startswith("{")]
        last = []
        for ln in lines[-n:]:
            try:
                last.append(json.loads(ln))
            except Exception:                                        # noqa: BLE001
                pass
        return {"exists": True, "n": len(lines), "bytes": p.stat().st_size, "last": last}
    except Exception as e:                                           # noqa: BLE001
        return {"exists": None, "n": 0, "last": [], "error": str(e)[:120]}


def _genpool():
    """读 `state/genpool.json`（由 `tools/codex-scripts/genrouter.py` 写）。取不到返回 None。"""
    try:
        p = ROOT / "state" / "genpool.json"
        if not p.is_file():
            return None
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        return None


def write_js(path: Path, data: dict) -> str:
    """落成 `.js`：**为什么不是 .json** —— 壳的窗口走 `file://` + `connect-src 'none'`，
    `fetch()` 读本地 json 会被挡；而 `<script src>` 是 `script-src 'self'` 放行的。
    ⇒ 数据以**经典脚本**的形式内嵌（这是本仓已有做法，不是新发明）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "/* 自动生成，别手改。重建：\n"
        "   py -3.14 tools/codex-scripts/brain-feed.py --out holo_pet_w3/brain/brain-data.js\n"
        "   数据全部来自本仓真实源码；每一项的出处见 SOURCE。 */\n"
        "globalThis.GBT_BRAIN = " + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        + ";\n", encoding="utf-8")
    return str(path)


def main() -> int:
    ap = argparse.ArgumentParser(description="神经可视化数据面（窗 E 的唯一出口）")
    ap.add_argument("--out", default="", help="落成 brain-data.js")
    ap.add_argument("--json", default="", help="另存一份纯 JSON（便于复核）")
    a = ap.parse_args()

    t0 = time.time()
    d = build()
    T = d["totals"]
    print("=" * 78)
    print("神经可视化 · 数据面（**以源码为准**，不用参考稿里的编造数字）")
    print("=" * 78)
    print("  束长（真实能力域）%s ｜ 能力位 %s（已实现 %s + 仅登记 %s）"
          % (T["bundles"], T["caps_total"], T["caps_impl"], T["caps_unimpl"]))
    print("  技能雾 %s ｜ 门禁作用域 %s ｜ 审计脉冲 %s（近 6h 内 %s）｜ 未收步 %s"
          % (T["skills"], T["scopes"], T["pulses"], T["pulses_live_6h"], T["open_steps"]))
    print("-" * 78)
    for b in d["bundles"]:
        print("    %-16s %-12s %3d 个能力位   hue %s" % (b["id"], b["label"], b["n"], b["hue"]))
    for k in ("caps_why", "pulses_why", "steps_why", "skills_why"):
        if d["honest"].get(k):
            print("  🔴 %s：%s" % (k, d["honest"][k]))
    if d["pulses"]:
        print("-" * 78)
        print("  最近 5 条真脉冲：")
        for p in d["pulses"][:5]:
            print("    %-9s %-22s bundle=%-12s ok=%s  %ss 前"
                  % (str(p.get("iso"))[11:19], p["kind"], p["bundle"], p["ok"], p["age_s"]))
    else:
        print("  ⚠️ 没有脉冲：审计账本里没有 `call` 事件 —— **如实报静默**，不拿随机数冒充")
    print("-" * 78)
    print("  用时 %.2fs" % (time.time() - t0))

    if a.json:
        Path(a.json).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print("  JSON: %s" % a.json)
    if a.out:
        print("  数据脚本: %s" % write_js(Path(a.out), d))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(3)
