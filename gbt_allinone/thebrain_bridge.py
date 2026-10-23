# gbt-capability: thebrain_bridge
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""TheBrain 15 思维导图接入桥（thebrain_bridge）· 🥔GBT小土豆V8

主人令 2026-09-28：
    「"C:\\Users\\ADMIN\\Desktop\\TheBrain 15.lnk"
      把这个思维导图集成进去把AI连接上，**使用我们的变压器连接上**」

这一句拆成**三件可判定的事**，本模块逐件落地：

  ① **集成进去** —— 把 TheBrain 的思维导图读进框架，变成框架的图结构。
     · 读面**双路径**：**离线直读 `Brain.db`（优先，最可靠）** + 在线走 Orion 本地 REST
       （`GetThoughtGraphAsync`）。离线读不需要 TheBrain 运行 —— 实测它没跑时也读得到。
     · 图上的**每个节点、每条边都能指出出处**（数据库行 / API 路径）——
       照 `tools/brain_graph.py` 的铁律：**指不出的，不画**。

  ② **把 AI 连接上** —— TheBrain 自带的 AI 面在**未订阅**下不可用
     （`MetaSettings.preferences.message = "No active subscription found."`），
     而它后端本来就带 `OpenAI.dll` / `Anthropic.dll`（OpenAI 兼容）。
     框架**已经有一条活的 OpenAI 兼容端点**：`llm/genoffice_bridge.py`
     （`127.0.0.1:31716/v1`，统一密钥 `gbtv8-…`，真流式 SSE）。
     ⇒ 不缺 AI，**缺的是把两边接起来**。

    ③ **使用我们的变压器连接上** —— 这一环是**本模块的灵魂**。
     桥直连 31716 是**不过变压器**的；本模块补上这一环，两种形态：
     · `ask` / `summarize`：框架侧读图 → **`transformer.compress`（省 token）**
       → `cache_get`（省调用）→ `llm/unified.ask`（真模型）→ `cache_put`。
       **必须给前后两个数**（变压器硬判据）。
     · `serve`：起一条**变压器前置的 OpenAI 兼容端点**（**CLI-only**，不挂能力位 ——
       常驻阻塞不许挂住调用方，照 `genoffice_bridge` 的纪律）——
       TheBrain 的 AI 指向它，**每一次请求都先过变压器**再转发上游。
       形态：`TheBrain → 本端点(127.0.0.1:<port>/v1，过变压器) → 31716 桥(我们的大模型) → 网关 → 模型`。

     主人 2026-09-28 追加令：「**可以啊就把我们的大模型接入 genoffice_bridge**」
     ⇒ 上游钉死 `llm/genoffice_bridge`（`127.0.0.1:31716`）这一条**我们的大模型通道**；
     它背后是 `key_gateway` 的多路换道池（`/health` 回报 `gateway_alive`）。

## 诚实边界（页面上必须原样写出，不许假装）

- **不代持账号、不代登录、不搬运凭据**。`MetaSettings.orion.localapikeys` 是 TheBrain
  自己的本地 API key；本模块**只读**它的存在性用于诊断，**明文不回显**（只给指纹）。
- **离线读是只读的**（`mode=ro`），**绝不改 Brain.db**。写面一律走 Orion（TheBrain 运行态），
  未运行 ⇒ `fail_closed` 如实报「需先开 TheBrain」，**不直接改数据库文件**。
- **不写 TheBrain 的配置**。`endpoint` op 只**报告**「该填什么」，改不改由主人自己定
  （改别人的配置是把控制权交出去，主人没点这个头）。
- 真调 AI = **把内容送出本机** ⇒ 挂 `external_llm`；写回 = **触外部进程/服务** ⇒ 挂
  `process_execute`。`security/policy.py` 是 owner-only 且**无 `thebrain_bridge` 分支**
  ⇒ 门在本模块内**自闸**（`auth_gate` 唯一校验入口），缺授权如实报缺，**不绕门**。

op = status / graph / search / notes / ask / summarize / endpoint / serve / think / link /
      verify / where
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent            # gbt_allinone/
_REPO = _ROOT.parent                               # 仓库根
_STATE = _REPO / "state"
_LEDGER = _STATE / "thebrain_bridge.jsonl"

# 只读 op（不挂作用域）｜写面 op（真出网 / 真触外部，必须过门）
_READ_OPS = ("status", "graph", "search", "notes", "endpoint", "verify", "where")
_GATE_EXTERNAL = ("external_llm",)                 # ask/summarize：内容出本机
_GATE_WRITE = ("process_execute",)                 # think/link/serve：触外部进程/服务

_HOME = Path(os.path.expanduser("~"))
# 数据面候选（**存在才算**，不猜）
_METADB = _HOME / "AppData" / "Local" / "TheBrain" / "MetaDB" / "TheBrainMeta.db"
_AICONV = _HOME / "AppData" / "Local" / "TheBrain" / "AiConversations" / "AiConversations.db"
_BRAINS_GLOB = ("Brains/*/*/Brain.db", "Brains/*/Brain.db")
_TB_EXE_CANDIDATES = (
    _HOME / "AppData" / "Local" / "Programs" / "TheBrain 15" / "TheBrain 15.exe",
    _HOME / "AppData" / "Local" / "TheBrain" / "TheBrain 15.exe",
)
# 框架既有 OpenAI 兼容端点（llm/genoffice_bridge.py）
_OUR_ENDPOINT = "http://127.0.0.1:31716/v1"
_OUR_HEALTH = "http://127.0.0.1:31716/health"

# TheBrain Link.Relation —— 值取自 Orion `LinkDto`（**未逐值实探**，标注为待核实）
_RELATION = {1: "child", 2: "parent", 3: "jump", 4: "sibling", 5: "friend", 6: "unknown"}


# ── 探针（只读，绝不猜）────────────────────────────────────────────────────

def _first_existing(*paths: Path) -> str:
    for p in paths:
        try:
            if p.exists():
                return str(p)
        except OSError:
            continue
    return ""


def _find_brains() -> list:
    out = []
    for pat in _BRAINS_GLOB:
        for p in sorted(_HOME.glob(pat)):
            try:
                out.append({"db": str(p), "bytes": p.stat().st_size})
            except OSError:
                continue
    return out


def _probe_our_endpoint(timeout: float = 2.0) -> dict:
    """探框架自己的 OpenAI 兼容端点（genoffice_bridge）—— 活没活、几路可用。"""
    import urllib.request
    try:
        with urllib.request.urlopen(_OUR_HEALTH, timeout=timeout) as r:
            body = json.loads(r.read().decode("utf-8", "replace"))
        return {"alive": True, "url": _OUR_ENDPOINT, "health": body,
                "auth": str(body.get("auth") or ""),
                "gateway": f"{body.get('gateway_alive')}/{body.get('gateway_total')}"}
    except Exception as exc:                                      # noqa: BLE001
        return {"alive": False, "url": _OUR_ENDPOINT,
                "error": f"{type(exc).__name__}: {exc}",
                "how_to_start": "py -3.14 -m gbt_allinone.llm.genoffice_bridge serve"
                                "  （或 llm/genoffice_bridge.py 的 serve()）"}


def _probe_orion() -> dict:
    """Orion 本地 REST = TheBrain 运行态自有 Kestrel（**动态端口**）⇒ 离线不可知，如实报。"""
    running = _tb_running()
    if not running:
        return {"known": False, "running": False,
                "why": "TheBrain 未运行 ⇒ Orion(Kestrel) 未起，端口运行态才可知（动态端口）",
                "fallback": "读面请用 **离线直读 Brain.db**（本模块 graph/search 已支持）"}
    return {"known": False, "running": True,
            "why": "TheBrain 在跑，但 Orion 端口是 Kestrel **动态端口**；"
                   "本模块不扫描端口**避免猜**（要精确端口请从 TheBrain 进程的监听表取）",
            "auth": "ApiKey（MetaSettings.orion.localapikeys）"}


def _tb_running() -> bool:
    """TheBrain 进程在不在（读本地进程表，不用 psutil 硬依赖）。"""
    try:
        import subprocess
        cp = subprocess.run(["tasklist", "/FI", "IMAGENAME eq TheBrain 15.exe"],
                            capture_output=True, timeout=8,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return b"TheBrain 15.exe" in (cp.stdout or b"")
    except Exception:                                             # noqa: BLE001
        return False


def _apikey_fingerprint() -> dict:
    """只报 Orion 本地 API key 的**存在性与指纹**，**明文绝不回显**。"""
    if not _METADB.is_file():
        return {"present": False, "why": "TheBrainMeta.db 不存在"}
    try:
        con = sqlite3.connect(f"file:{_METADB.as_posix()}?mode=ro", uri=True, timeout=5)
        row = con.execute(
            "SELECT Value FROM MetaSettings WHERE Name='orion.localapikeys'").fetchone()
        con.close()
        if not row:
            return {"present": False, "why": "MetaSettings 里没有 orion.localapikeys"}
        data = json.loads(row[0])
        keys = []
        for uid, k in (data or {}).items():
            ks = str(k)
            keys.append({"user": uid[:8] + "…", "fingerprint": f"{len(ks)}/{ks[:4]}…{ks[-4:]}"
                         if len(ks) > 8 else "过短"})
        return {"present": True, "count": len(keys), "keys": keys,
                "_口径": "**只报指纹，不回显明文**（明文属 TheBrain 自己的凭据）"}
    except Exception as exc:                                      # noqa: BLE001
        return {"present": False, "error": f"{type(exc).__name__}: {exc}"}


def _subscription_state() -> dict:
    if not _METADB.is_file():
        return {"known": False}
    try:
        con = sqlite3.connect(f"file:{_METADB.as_posix()}?mode=ro", uri=True, timeout=5)
        row = con.execute(
            "SELECT Value FROM MetaSettings WHERE Name='preferences.message'").fetchone()
        con.close()
        msg = json.loads(row[0]) if row else ""
        return {"known": True, "message": msg,
                "ai_usable_by_itself": not ("No active subscription" in str(msg))}
    except Exception as exc:                                      # noqa: BLE001
        return {"known": False, "error": f"{type(exc).__name__}: {exc}"}


def status() -> dict:
    """**探针底表**（只读）：TheBrain 装/跑 · 数据面 · Orion · 我们的 AI 端点 · 变压器。"""
    exe = _first_existing(*_TB_EXE_CANDIDATES)
    brains = _find_brains()
    tc = _transformer_mod()
    try:
        tstats = tc.stats()
    except Exception as exc:                                      # noqa: BLE001
        tstats = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": True, "op": "status", "dimension": "integration",
        "thebrain": {
            "installed": bool(exe), "exe": exe, "running": _tb_running(),
            "install_hint": "TheBrain 15（TheBrain Technologies 官方安装包）",
        },
        "data": {
            "brains": brains, "brain_count": len(brains),
            "metadb": {"path": str(_METADB), "exists": _METADB.is_file()},
            "aiconversations": {"path": str(_AICONV), "exists": _AICONV.is_file()},
            "orion_apikey": _apikey_fingerprint(),
            "subscription": _subscription_state(),
        },
        "orion": _probe_orion(),
        "our_ai_endpoint": _probe_our_endpoint(),
        "transformer": {"op": "stats", "stats": tstats},
        "口径": ("装没装=查已知安装位 · 跑没跑=tasklist · 图=离线直读 Brain.db（mode=ro）· "
                "Orion=运行态动态端口（离线如实报不可知）· 我们的端点=探 31716/health · "
                "变压器=transformer.stats()"),
        "红线": ("**不改 Brain.db**（mode=ro）· **不写 TheBrain 配置** · "
                "**不回显凭据明文**（只给指纹）"),
    }


# ── 读面：思维导图（离线直读 Brain.db 优先）─────────────────────────────────

def _read_brain_db(db: str, limit: int = 5000) -> dict:
    """**只读**打开 Brain.db，取 Thoughts / Links。`mode=ro` ⇒ 绝不改文件。"""
    con = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True, timeout=8)
    con.row_factory = sqlite3.Row
    try:
        th = [dict(r) for r in con.execute(
            "SELECT Id, BrainId, Name, CreationDateTime, ModificationDateTime, "
            "ForgottenDateTime, TypeId, Kind FROM Thoughts LIMIT ?", (int(limit),))]
        lk = [dict(r) for r in con.execute(
            "SELECT Id, BrainId, ThoughtIdA, ThoughtIdB, Relation, Meaning, Direction, "
            "Name FROM Links LIMIT ?", (int(limit),))]
    finally:
        con.close()
    return {"thoughts": th, "links": lk}


def _ticks_to_iso(v) -> str:
    """TheBrain 时间戳 = .NET ticks（0001-01-01 起 100ns）。取不到就回原值。"""
    try:
        import datetime
        t = int(v)
        if t <= 0:
            return ""
        return (datetime.datetime(1, 1, 1) + datetime.timedelta(microseconds=t / 10)).isoformat()
    except Exception:                                             # noqa: BLE001
        return str(v or "")


def _norm_graph(raw: dict, source: str) -> dict:
    """归一化：Thoughts→节点，Links→边。**每条都带出处**（数据库行 / API）。"""
    nodes, edges = [], []
    for t in raw.get("thoughts") or []:
        nodes.append({
            "id": t.get("Id"), "label": t.get("Name"),
            "brain": t.get("BrainId"), "type_id": t.get("TypeId"),
            "created": _ticks_to_iso(t.get("CreationDateTime")),
            "modified": _ticks_to_iso(t.get("ModificationDateTime")),
            "forgotten": bool(t.get("ForgottenDateTime")),
            "source": f"{source}:Thoughts.Id={t.get('Id')}",
        })
    by_id = {n["id"]: n for n in nodes}
    for l in raw.get("links") or []:
        a, b = l.get("ThoughtIdA"), l.get("ThoughtIdB")
        rel = l.get("Relation")
        edges.append({
            "id": l.get("Id"), "from": a, "to": b,
            "from_label": (by_id.get(a) or {}).get("label"),
            "to_label": (by_id.get(b) or {}).get("label"),
            "relation": rel, "relation_name": _RELATION.get(rel, f"raw:{rel}"),
            "meaning": l.get("Meaning"), "direction": l.get("Direction"),
            "source": f"{source}:Links.Id={l.get('Id')}",
        })
    return {
        "ok": True, "op": "graph", "source": source,
        "nodes": nodes, "edges": edges,
        "counts": {"nodes": len(nodes), "edges": len(edges)},
        "brain_ids": sorted({n["brain"] for n in nodes if n.get("brain")}),
        "_口径": ("图上的**每个节点、每条边都能指出出处**（`source` 字段）——"
                 "照 brain_graph.py 的铁律：**指不出的，不画**。"
                 "relation 值取自 Orion LinkDto，**未逐值实探** ⇒ 未知值原样报 raw:<n>。"),
    }


def graph(brain_id: str = "", limit: int = 5000, prefer: str = "offline") -> dict:
    """读思维导图。**离线直读 Brain.db 优先**（TheBrain 没跑也读得到）。"""
    brains = _find_brains()
    if not brains:
        return {"ok": False, "op": "graph", "fail_closed": True,
                "error_class": "no_brain_db",
                "error": "没找到 Brain.db（找过 Brains/*/*/Brain.db）",
                "hint": "在 TheBrain 里建/打开一个脑，或确认脑库路径"}
    db = ""
    if brain_id:
        for b in brains:
            if brain_id in b["db"]:
                db = b["db"]
                break
        if not db:
            return {"ok": False, "op": "graph", "fail_closed": True,
                    "error": f"没有匹配 brain_id={brain_id} 的库", "found": [b["db"] for b in brains]}
    else:
        db = brains[0]["db"]
    try:
        raw = _read_brain_db(db, limit)
    except Exception as exc:                                      # noqa: BLE001
        return {"ok": False, "op": "graph", "fail_closed": True,
                "error_class": "db_read_failed", "db": db,
                "error": f"{type(exc).__name__}: {exc}",
                "hint": "TheBrain 独占时文件可能被锁；关掉 TheBrain 或改用在线 Orion 读"}
    g = _norm_graph(raw, "Brain.db")
    g["db"] = db
    return g


def search(q: str, limit: int = 50) -> dict:
    """图内搜索（离线：Thoughts.Name LIKE；只读）。"""
    text = str(q or "").strip()
    if not text:
        return {"ok": False, "op": "search", "fail_closed": True, "error": "q 为空"}
    brains = _find_brains()
    if not brains:
        return {"ok": False, "op": "search", "fail_closed": True,
                "error_class": "no_brain_db", "error": "没找到 Brain.db"}
    hits = []
    for b in brains:
        try:
            con = sqlite3.connect(f"file:{Path(b['db']).as_posix()}?mode=ro", uri=True, timeout=8)
            con.row_factory = sqlite3.Row
            rows = [dict(r) for r in con.execute(
                "SELECT Id, Name, BrainId FROM Thoughts WHERE Name LIKE ? LIMIT ?",
                (f"%{text}%", int(limit)))]
            con.close()
        except Exception as exc:                                  # noqa: BLE001
            rows = [{"_err": f"{type(exc).__name__}: {exc}"}]
        for r in rows:
            hits.append({"id": r.get("Id"), "label": r.get("Name"), "brain": r.get("BrainId"),
                         "db": b["db"], "source": f"Brain.db:Thoughts.Id={r.get('Id')}"})
    return {"ok": True, "op": "search", "q": text, "hits": hits, "count": len(hits),
            "_口径": "离线 LIKE 匹配 Thought 名；在线可走 Orion SearchController.PerformSearchAsync"}


def notes(thought_id: str) -> dict:
    """读某 thought 的笔记 —— **需 TheBrain 运行态 Orion**（离线库不含笔记正文）。"""
    if not thought_id:
        return {"ok": False, "op": "notes", "fail_closed": True, "error": "thought_id 为空"}
    if not _tb_running():
        return {"ok": False, "op": "notes", "fail_closed": True,
                "error_class": "needs_runtime", "error": "读笔记需 TheBrain 运行态（Orion 在线）",
                "orion_api": "GET NotesController.GetNotesTextAsync(brainId, thoughtId)",
                "hint": "先开 TheBrain；离线只读面请用 graph/search"}
    return {"ok": False, "op": "notes", "fail_closed": True,
            "error_class": "orion_port_unknown",
            "error": "TheBrain 在跑，但 Orion 端口是动态端口 —— 本模块不猜端口（见 status.orion）",
            "orion_api": "NotesController.GetNotesHtmlAsync / GetNotesTextAsync",
            "how_to": "从 TheBrain 进程监听表取端口后，用 apiKey 直接 GET；"
                      "本刀的确定读面 = graph/search（离线）"}


# ── 变压器（**本模块的灵魂**）─────────────────────────────────────────────
def _transformer_mod():
    """复用 `tools/transformer_cap` —— **不在本模块重造变压器**。"""
    try:
        from .tools import transformer_cap as tc
        return tc
    except ImportError:                                           # 独立加载
        import importlib.util as _ilu
        sp = _ilu.spec_from_file_location(
            "transformer_cap_sibling", _ROOT / "tools" / "transformer_cap.py")
        m = _ilu.module_from_spec(sp)
        sp.loader.exec_module(m)
        return m


def _llm_ask(prompt: str, system: str = "", timeout: int = 60, max_tokens: int = 2000,
             purpose: str = "thebrain_ask", **kw) -> dict:
    """统一调用口（`llm/unified.ask`）—— 模块自己 import bridge 视为漂移。"""
    try:
        from .llm import unified as LLM
    except ImportError:                                           # 独立加载
        sys.path.insert(0, str(_REPO))
        from gbt_allinone.llm import unified as LLM                # type: ignore
    return LLM.ask(prompt, system=system, timeout=int(timeout), max_tokens=int(max_tokens),
                   purpose=purpose, **kw)


def _graph_context(brain_id: str = "", thought_id: str = "", limit: int = 5000) -> dict:
    """给 AI 的图上下文（文本）：可选限定某 thought 的邻域。"""
    g = graph(brain_id=brain_id, limit=limit)
    if not g.get("ok"):
        return {"ok": False, "context": "", "graph": g}
    lines = []
    if thought_id:
        nb = {thought_id}
        for e in g["edges"]:
            if e.get("from") == thought_id:
                nb.add(e.get("to"))
            if e.get("to") == thought_id:
                nb.add(e.get("from"))
        nodes = [n for n in g["nodes"] if n.get("id") in nb]
        edges = [e for e in g["edges"] if e.get("from") in nb and e.get("to") in nb]
        lines.append(f"[本图上下文 · 焦点 thought={thought_id} · 邻域 {len(nodes)} 节点]")
    else:
        nodes, edges = g["nodes"], g["edges"]
        lines.append(f"[本图上下文 · 整图 {len(nodes)} 节点 / {len(edges)} 边]")
    for n in nodes[:400]:
        lines.append(f"节点 {n['label']} (id={n['id']})")
    for e in edges[:800]:
        lines.append(f"边 {e.get('from_label')} -[{e.get('relation_name')}]-> {e.get('to_label')}")
    return {"ok": True, "context": "\n".join(lines), "graph": g}


def ask(prompt: str, thought_id: str = "", brain_id: str = "",
        use_cache: bool = True, allow_approx: bool = False,
        system: str = "", timeout: int = 60, max_tokens: int = 2000,
        dry_run: bool = False) -> dict:
    """**把 AI 连接上 —— 且过我们的变压器**（主人令的核心一句）。

    链路：图上下文 + 提问 → **`transformer.compress`（省 token）** →
    `cache_get`（省调用）→ `llm/unified.ask`（真模型）→ `cache_put`。
    **必须给前后两个数**（变压器硬判据）。
    """
    text = str(prompt or "").strip()
    if not text:
        return {"ok": False, "op": "ask", "fail_closed": True, "error": "prompt 为空"}
    tc = _transformer_mod()
    ctx = _graph_context(brain_id=brain_id, thought_id=thought_id)
    full = (ctx.get("context") or "") + "\n\n[提问]\n" + text
    comp = tc.compress(full)
    key_text = comp.get("text") or full
    tstats = {"op": "compress", "chars_before": comp.get("chars_before"),
              "chars_after": comp.get("chars_after"), "ratio": comp.get("ratio"),
              "saved_chars": comp.get("saved_chars"), "bypass": comp.get("bypass"),
              "protected_lines": comp.get("protected_lines")}
    if dry_run:
        return {"ok": True, "op": "ask", "dry_run": True,
                "transformer": tstats,
                "note": "只演练：**没查缓存、没调模型、没出网**。真发要过门（external_llm）。"}
    # ② 变压器缓存：精确命中直接给（近似默认只报不返答案 —— 假命中禁令）
    if use_cache:
        hit = tc.cache_get(key_text, allow_approx=allow_approx)
        if hit.get("hit") == "exact":
            _log({"event": "ask", "via": "cache_exact", "transformer": tstats})
            return {"ok": True, "op": "ask", "via": "cache_exact", "answer": hit.get("answer"),
                    "transformer": tstats, "cache": {"hit": "exact", "saved_calls": 1},
                    "_口径": "变压器缓存精确命中 ⇒ **省掉一次真调用**（输出侧省）"}
    # ③ 真调（过门：内容出本机）
    gate = _gate(_GATE_EXTERNAL, f"thebrain_bridge ask → 出网调模型")
    if not gate.get("ok"):
        return {"ok": False, "op": "ask", "denied": True, "fail_closed": True,
                "error_class": "needs_authorization",
                "error": gate.get("error"), "missing": gate.get("missing") or list(_GATE_EXTERNAL),
                "how_to_grant": gate.get("how_to_grant"),
                "why": "调 AI = 把内容送出本机 ⇒ 要授权",
                "口径": "缺授权如实报缺；**不绕门**"}
    sys_p = system or ("你是 GBT小土豆V8 的思维导图助手。下面是 TheBrain 思维导图的图结构"
                       "（节点/边）。基于**给定图**回答，图上没有的不要编。")
    r = _llm_ask(key_text, system=sys_p, timeout=timeout, max_tokens=max_tokens)
    ans = str(r.get("reply") or "")
    if r.get("ok") and ans:
        tc.cache_put(key_text, ans)                               # 写缓存（下次省调用）
    _log({"event": "ask", "via": "llm", "ok": bool(r.get("ok")), "provider": r.get("provider"),
          "transformer": tstats})
    return {"ok": bool(r.get("ok")), "op": "ask", "via": "llm", "answer": ans,
            "transformer": tstats,
            "llm": {"provider": r.get("provider"), "model": r.get("model"),
                    "drift": r.get("drift"), "path": r.get("path")},
            "error": (r.get("error") if not r.get("ok") else None),
            "_口径": "**变压器在链路里**（compress 省 token + cache 省调用）；"
                    "给前后两个数 = 变压器硬判据；真模型经 llm/unified.ask（唯一口）"}


def summarize(brain_id: str = "", thought_id: str = "", **kw) -> dict:
    """对图做 AI 摘要（同走变压器）。"""
    q = ("请用中文总结这张思维导图的结构与要点：主题是什么、有哪些主要分支、"
         "它们之间怎么连的。只基于给定图，图上没有的不要编。")
    return ask(q, thought_id=thought_id, brain_id=brain_id, **kw)


# ── AI 端点接法（只报告，不替主人改配置）────────────────────────────────────

def endpoint(port: int = 31717) -> dict:
    """**报告**「TheBrain 的 AI 该填什么」+ 变压器前置端点的形态。**不替主人改配置**。"""
    up = _probe_our_endpoint()
    return {
        "ok": True, "op": "endpoint",
        "our_ai_endpoint": up,
        "answer": {
            "直接接（**不过变压器**）": {
                "baseUrl": _OUR_ENDPOINT,
                "apiKey": "Bearer gbtv8-<32hex>（统一密钥，见 key_gateway）",
                "note": "TheBrain 后端带 OpenAI.dll（OpenAI 兼容）⇒ 指向本桥即可用我们的模型；"
                        "但这条**不经过变压器**",
            },
            "过变压器接（**主人要的这一条**）": {
                "how": "起本模块的 `serve` op ⇒ 得到 127.0.0.1:<port>/v1 —— 它**每次请求先过变压器**"
                       "再转发上游；把 TheBrain 的 AI baseUrl 指向它",
                "baseUrl": f"http://127.0.0.1:{int(port)}/v1",
                "start": f"py -3.14 -m gbt_allinone.thebrain_bridge serve --port {int(port)}"
                         "   （serve 是 serve_forever 常驻 ⇒ **CLI-only**："
                         "能力位/run_task 调它只返回 cli_only 指引，不会挂住调用方）",
                "chain": f"TheBrain → 127.0.0.1:{int(port)}(过变压器) → {_OUR_ENDPOINT} → 网关 → 模型",
            },
        },
        "诚实边界": ("① 本模块**不写 TheBrain 的配置**（改别人配置=交出控制权，主人没点这个头）；"
                    "② 未订阅下 TheBrain 自带 AI 面可能被它的订阅门挡住 ⇒ 这条以实测为准，"
                    "框不住就退回 `ask`（框架侧，已含变压器）；"
                    "③ 端口以 serve 实际返回为准。"),
    }


# ── 变压器前置的 OpenAI 兼容端点（serve）────────────────────────────────────

def _make_proxy(upstream: str, do_compress: bool = True, threshold: int = 400):
    """造一个 http.server Handler 类：接 OpenAI 兼容请求 → 过变压器 → 转发上游。"""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import urllib.request
    tc = _transformer_mod()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):                                # 静音默认日志
            return

        def _send(self, code: int, body: bytes, ctype: str = "application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):                                         # noqa: N802
            if self.path.rstrip("/") in ("/health", "/thebrain-bridge/health"):
                body = json.dumps({"ok": True, "service": "thebrain_bridge",
                                   "transformer": do_compress, "upstream": upstream},
                                  ensure_ascii=False).encode("utf-8")
                return self._send(200, body)
            return self._forward("GET", b"")

        def do_POST(self):                                        # noqa: N802
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b""
            return self._forward("POST", raw)

        def _forward(self, method: str, raw: bytes):
            body = raw
            saved = None
            if method == "POST" and do_compress and raw:
                try:
                    obj = json.loads(raw.decode("utf-8"))
                    msgs = obj.get("messages") or []
                    before = sum(len(str(m.get("content") or "")) for m in msgs)
                    for m in msgs:
                        c = m.get("content")
                        if isinstance(c, str) and len(c) > threshold:
                            m["content"] = tc.compress(c, target_chars=max(threshold, len(c) // 2),
                                                       bypass_if_lost=True)["text"]
                    after = sum(len(str(m.get("content") or "")) for m in msgs)
                    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
                    saved = {"chars_before": before, "chars_after": after,
                             "saved": before - after}
                    _log({"event": "proxy_compress", **(saved or {})})
                except Exception as exc:                          # noqa: BLE001
                    saved = {"error": f"{type(exc).__name__}: {exc}"}
            url = upstream.rstrip("/") + self.path
            req = urllib.request.Request(url, data=(body if method == "POST" else None),
                                         method=method)
            for k in ("Authorization", "Content-Type", "Accept"):
                if self.headers.get(k):
                    req.add_header(k, self.headers[k])
            try:
                with urllib.request.urlopen(req, timeout=120) as up:
                    ct = up.headers.get("Content-Type", "application/json")
                    data = up.read()
                    self.send_response(up.status)
                    self.send_header("Content-Type", ct)
                    self.send_header("X-Thebrain-Bridge-Transformer",
                                     json.dumps(saved or {}, ensure_ascii=False))
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
            except Exception as exc:                              # noqa: BLE001
                err = json.dumps({"error": {"message": f"upstream 失败: {exc}",
                                            "type": "thebrain_bridge_upstream"}},
                                 ensure_ascii=False).encode("utf-8")
                self._send(502, err)

    return Handler, ThreadingHTTPServer


def make_server(host: str = "127.0.0.1", port: int = 31717,
                upstream: str = "", do_compress: bool = True):
    """造服务（不启动）。**只绑回环** —— 带密钥的上游代理，绑出去=把网关对公网开放。"""
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("拒绝绑非回环地址：本网桥带鉴权，只许 127.0.0.1")
    Handler, Srv = _make_proxy(upstream or _OUR_ENDPOINT, do_compress)
    return Srv((host, int(port)), Handler)


def serve(port: int = 31717, host: str = "127.0.0.1", upstream: str = "",
          do_compress: bool = True, dry_run: bool = False) -> dict:
    """起**变压器前置的 OpenAI 兼容端点**（阻塞）。TheBrain 指向它 ⇒ 真·过变压器。"""
    if dry_run:
        return {"ok": True, "op": "serve", "dry_run": True,
                "would_bind": f"{host}:{int(port)}", "upstream": upstream or _OUR_ENDPOINT,
                "transformer": do_compress,
                "note": "只演练：**没起服务**。真起要过门（process_execute）。"}
    gate = _gate(_GATE_WRITE, "thebrain_bridge serve → 起本地代理端点")
    if not gate.get("ok"):
        return {"ok": False, "op": "serve", "denied": True, "fail_closed": True,
                "error_class": "needs_authorization", "error": gate.get("error"),
                "missing": gate.get("missing") or list(_GATE_WRITE),
                "how_to_grant": gate.get("how_to_grant"),
                "why": "起常驻服务 = 触外部进程 ⇒ 要授权"}
    srv = make_server(host, port, upstream, do_compress)
    bound = srv.server_address
    _log({"event": "serve", "bound": f"{bound[0]}:{bound[1]}", "upstream": upstream or _OUR_ENDPOINT})
    print(json.dumps({"ok": True, "op": "serve", "bound": f"{bound[0]}:{bound[1]}",
                      "baseUrl": f"http://{bound[0]}:{bound[1]}/v1",
                      "upstream": upstream or _OUR_ENDPOINT, "transformer": do_compress},
                     ensure_ascii=False), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return {"ok": True, "op": "serve", "stopped": True}


# ── 写面（Orion；需运行态）────────────────────────────────────────────────

def _orion_write_blocked() -> dict | None:
    if not _tb_running():
        return {"ok": False, "fail_closed": True, "error_class": "needs_runtime",
                "error": "写回 TheBrain 需运行态（Orion 在线）；离线**不改 Brain.db**",
                "orion_api": "ThoughtsController.CreateThoughtAsync / LinksController.CreateLinkAsync",
                "hint": "先开 TheBrain"}
    return None


def think(label: str, parent_id: str = "", dry_run: bool = False) -> dict:
    """新建一个 thought（写回 TheBrain，走 Orion）。"""
    if not str(label or "").strip():
        return {"ok": False, "op": "think", "fail_closed": True, "error": "label 为空"}
    if dry_run:
        return {"ok": True, "op": "think", "dry_run": True, "label": label, "parent_id": parent_id,
                "orion_api": "POST ThoughtsController.CreateThoughtAsync(brainId, model)",
                "note": "只演练：**没写 TheBrain**。真写要过门（process_execute）。"}
    blk = _orion_write_blocked()
    if blk:
        return {**blk, "op": "think"}
    gate = _gate(_GATE_WRITE, "thebrain_bridge think → 写回 TheBrain")
    if not gate.get("ok"):
        return {"ok": False, "op": "think", "denied": True, "fail_closed": True,
                "error_class": "needs_authorization", "error": gate.get("error"),
                "missing": gate.get("missing") or list(_GATE_WRITE),
                "how_to_grant": gate.get("how_to_grant")}
    return {"ok": False, "op": "think", "fail_closed": True,
            "error_class": "orion_port_unknown",
            "error": "Orion 端口动态，本模块不猜端口 ⇒ 写面待端口定位后接通",
            "orion_api": "ThoughtsController.CreateThoughtAsync(brainId, ThoughtCreateModel)",
            "note": "本刀的**确定交付 = 读面 + 变压器 AI**；写面通道如实标为待接通，不假装已通"}


def link(a: str, b: str, relation: int = 1, dry_run: bool = False) -> dict:
    """新建一条 link（写回 TheBrain，走 Orion）。"""
    if not (a and b):
        return {"ok": False, "op": "link", "fail_closed": True, "error": "a/b 不能为空"}
    if dry_run:
        return {"ok": True, "op": "link", "dry_run": True, "a": a, "b": b, "relation": relation,
                "orion_api": "POST LinksController.CreateLinkAsync(brainId, LinkCreateModel)",
                "note": "只演练：**没写 TheBrain**。"}
    blk = _orion_write_blocked()
    if blk:
        return {**blk, "op": "link"}
    return {"ok": False, "op": "link", "fail_closed": True,
            "error_class": "orion_port_unknown",
            "error": "Orion 端口动态，本模块不猜端口 ⇒ 写面待端口定位后接通",
            "orion_api": "LinksController.CreateLinkAsync(brainId, LinkCreateModel)"}


# ── 门（模块内自闸；**不是绕门，是补门**）──────────────────────────────────

def _gate(scopes, detail: str) -> dict:
    """`security/policy.py` 无 `thebrain_bridge` 分支（owner-only，AI 无权改）
    ⇒ 门层零作用域 ⇒ 本模块走授权门的**唯一校验入口** `auth_gate.check_and_consume_many`
    （与 `policy.authorize` 同一个）——**不是绕门，是补门**。"""
    try:
        from . import auth_gate
        from .security import policy as _policy
    except ImportError:                                           # 独立加载
        sys.path.insert(0, str(_REPO))
        from gbt_allinone import auth_gate                        # type: ignore
        from gbt_allinone.security import policy as _policy        # type: ignore
    if _policy.is_trusted():
        return {"ok": True, "trusted": True, "scopes": list(scopes)}
    return auth_gate.check_and_consume_many(list(scopes), detail=detail)


def _log(row: dict) -> None:
    try:
        _LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with open(_LEDGER, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row},
                                ensure_ascii=False) + "\n")
    except Exception:                                             # noqa: BLE001
        pass


# ── 自检 / 定位 ───────────────────────────────────────────────────────────

def verify() -> dict:
    """机检：探针真、读面真、变压器真、门真。"""
    problems = []
    st = status()
    if st["thebrain"]["installed"] and not st["thebrain"]["exe"]:
        problems.append("判了装了却没有 exe 路径")
    if not st["data"]["brains"]:
        problems.append("没读到任何 Brain.db（读面会 fail-closed，先确认路径）")
    if "brain" not in st["data"]["orion_apikey"]:
        pass
    up = st["our_ai_endpoint"]
    if up.get("alive") and not up.get("url"):
        problems.append("端点活着却没 url")
    g = graph()
    if g.get("ok"):
        for n in g["nodes"]:
            if not n.get("source"):
                problems.append(f"节点 {n.get('id')} 没有出处（违反 brain_graph 铁律）")
                break
    else:
        # 读面失败要能解释（无库/被锁），不算问题
        pass
    try:
        tc = _transformer_mod()
        assert hasattr(tc, "compress") and hasattr(tc, "cache_get")
    except Exception as exc:                                      # noqa: BLE001
        problems.append(f"变压器不可用：{type(exc).__name__}: {exc}")
    try:
        from . import auth_gate
        assert hasattr(auth_gate, "check_and_consume_many")
    except Exception as exc:                                      # noqa: BLE001
        problems.append(f"授权门不可用：{type(exc).__name__}: {exc}")
    return {"ok": not problems, "op": "verify", "problems": problems,
            "gates": {"ask/summarize": list(_GATE_EXTERNAL), "think/link/serve": list(_GATE_WRITE)},
            "ledger": str(_LEDGER),
            "_口径": "探针真 · 节点必须有出处 · 变压器可用 · 门走 auth_gate"}


def where() -> dict:
    return {"ok": True, "op": "where", "kind": "thebrain_bridge",
            "entry": "run_task('thebrain_bridge', {...})",
            "ops": ["status", "graph", "search", "notes", "ask", "summarize",
                    "endpoint", "serve", "think", "link", "verify", "where"],
            "ledger": str(_LEDGER),
            "hard_facts": [
                "TheBrain 15 真身 = %LOCALAPPDATA%\\Programs\\TheBrain 15\\TheBrain 15.exe；"
                "脑库 = ~\\Brains\\U01\\B01\\Brain.db（可离线只读直读）",
                "Orion 本地 REST 全程：Thoughts/Links/Notes/Search Controller（auth=ApiKey）；"
                "端口=运行态动态端口 ⇒ 离线不可知",
                "TheBrain 后端带 OpenAI.dll/Anthropic.dll（OpenAI 兼容）；未订阅 ⇒ 自带 AI 面不可用",
                "框架已有 OpenAI 兼容端点 127.0.0.1:31716（llm/genoffice_bridge）"
                "—— **但不过变压器**；本模块补的就是这一环",
                "**变压器在链路里**：ask/summarize 走 compress+cache；serve 起变压器前置端点",
            ],
            "gates": {"ask/summarize": list(_GATE_EXTERNAL), "think/link/serve": list(_GATE_WRITE)},
            "gap": ("`security/policy.py` 无 `thebrain_bridge` 分支（owner-only，AI 无权改）"
                    "⇒ 门在本模块内自闸（auth_gate）；**已如实登记，不擅自改 policy**")}


def run_op(op: str = "status", **params) -> dict:
    op = (op or "status").lower()
    if op == "graph":
        return graph(params.get("brain_id", ""), int(params.get("limit", 5000)))
    if op == "search":
        return search(params.get("q", "") or params.get("query", ""), int(params.get("limit", 50)))
    if op == "notes":
        return notes(params.get("thought_id", "") or params.get("id", ""))
    if op == "ask":
        return ask(params.pop("prompt", "") or params.pop("q", ""), **params)
    if op == "summarize":
        return summarize(**params)
    if op == "endpoint":
        return endpoint(int(params.get("port", 31717)))
    if op == "serve":
        # 🔴 照 genoffice_bridge 的纪律：serve 是 serve_forever 常驻 ⇒ **不许挂能力位入口**
        #    （CODING_DISCIPLINE「穿透传输不阻塞」）。走 CLI 真起。
        return {"ok": False, "op": "serve", "cli_only": True,
                "why": "serve 是 serve_forever 常驻 —— 能力位入口不许挂住调用方",
                "how": f"py -3.14 -m gbt_allinone.thebrain_bridge serve --port "
                       f"{int(params.get('port', 31717) or 31717)}",
                "upstream": params.get("upstream", "") or _OUR_ENDPOINT,
                "note": "真起要过门（process_execute）；CLI 路径下模块内自闸"}
    if op == "think":
        return think(params.get("label", "") or params.get("name", ""), params.get("parent_id", ""),
                     bool(params.get("dry_run")))
    if op == "link":
        return link(params.get("a", "") or params.get("from", ""),
                    params.get("b", "") or params.get("to", ""),
                    int(params.get("relation", 1)), bool(params.get("dry_run")))
    for name, fn in (("status", status), ("verify", verify), ("where", where)):
        if op == name:
            return fn()
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（status/graph/search/notes/ask/summarize/endpoint/"
                     f"serve/think/link/verify/where）"}


def run(payload: dict | None = None) -> dict:
    """能力位入口（api.py 分派到这里）。op 默认 status（**只读**，打开即看底表）。"""
    p = dict(payload or {})
    op = str(p.pop("op", None) or p.pop("action", None) or "status").lower()
    return run_op(op, **p)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="TheBrain 15 思维导图接入桥（thebrain_bridge）")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "graph", "search", "ask", "summarize", "endpoint",
                             "serve", "verify", "where"])
    ap.add_argument("--q", default="")
    ap.add_argument("--thought", default="")
    ap.add_argument("--port", type=int, default=31717)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                                             # noqa: BLE001
        pass
    if a.cmd == "search":
        r = search(a.q)
    elif a.cmd == "ask":
        r = ask(a.q, thought_id=a.thought, dry_run=a.dry_run)
    elif a.cmd == "serve":
        r = serve(port=a.port, dry_run=a.dry_run)
    else:
        r = run_op(a.cmd)
    print(json.dumps(r, ensure_ascii=False, indent=1))            # noqa: T201
    raise SystemExit(0)
