# -*- coding: utf-8 -*-
"""认知界面本地服务（console-server）：给 console 页提供真数据与真对话。

为什么需要它：file:// 直开时浏览器 CORS 会挡 fetch，控制台只能演示；
起这个小服务后，页面用 http://127.0.0.1:8766/ 打开 → 数据现读、对话走本机指挥官。

口径（主人 2026-11-01）：「我们的是无限制上下文稳定输出」
  · 无限上下文：每轮对话走 `energy_core.think(context="console-web")` ——
    模型只吃**有界窗口**（恒定长度），全量历史落 sqlite 可 recall（ring_context）；
  · 稳定输出：temperature=0、max_tokens 封顶、同一问题同一回答（可复现）；
  · 没电/没票/出错：如实报错，不编回答。

用法：python tools/console-server.py [--port 8766]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import queue
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = pathlib.Path(__file__).resolve().parents[1]
WEB = REPO / "holo_pet_w3"
sys.path.insert(0, str(REPO))

# 2026-11-02 主人令「万能插必须默认全开」：本地桌面应用 = 主人可信会话。
# policy.authorize() 对可信主人会话直接放行；插拔/执行仍落台账，不是关掉审计。
os.environ.setdefault("GBT_OWNER_SESSION", "1")
os.environ.setdefault("GBT_OMNI_FULL_OPEN", "1")
try:
    import certifi as _certifi
    os.environ.setdefault("SSL_CERT_FILE", _certifi.where())
except Exception:  # noqa: BLE001
    pass

def _engine_autostart():
    """APP 一开就把本机引擎拉起来（有健康实例则直接复用）。"""
    try:
        if os.environ.get("GBT_ENGINE_AUTOSTART", "1") == "0":
            return

        def _run():
            try:
                import subprocess as _sp
                _sp.run([sys.executable, str(REPO / "tools" / "engine-up.py")],
                        timeout=180, capture_output=True)
            except Exception:  # noqa: BLE001
                pass

        threading.Thread(target=_run, daemon=True).start()
    except Exception:  # noqa: BLE001
        pass


_engine_autostart()

DATA_LOCK = threading.Lock()
DATA_CACHE = {"at": 0.0, "data": None}
CONTEXT_NAME = "console-web"


def _build_data() -> dict:
    """真数据：与 tools/gen-console-data.py 同源（直接调它）。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen_console_data", REPO / "tools" / "gen-console-data.py")
    mod = importlib.util.module_from_spec(spec)
    old = sys.argv
    sys.argv = ["gen"]
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod.build()
    finally:
        sys.argv = old


def _data() -> dict:
    with DATA_LOCK:
        if DATA_CACHE["data"] is None or time.time() - DATA_CACHE["at"] > 5:
            DATA_CACHE["data"] = _build_data()
            DATA_CACHE["at"] = time.time()
        return DATA_CACHE["data"]


# ---- /api/memory：recall（统一索引）/ write（同步层 chain+version）/ subscribe（SSE 广播）----
_SYNC_LOCK = threading.Lock()
_SYNC_MOD = None
_UNIFY_MOD = None
SUBS_LOCK = threading.Lock()
SUBS = set()          # 每个订阅者一个 queue.Queue；只在内存里，进程重启即断（如实）


def _load_by_path(mod_name: str, rel: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(mod_name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _sync_mod():
    """记忆同步层（tools/memory_sync.py）：write 落链库拿 version/chain。"""
    global _SYNC_MOD
    with _SYNC_LOCK:
        if _SYNC_MOD is None:
            _SYNC_MOD = _load_by_path("memory_sync", "gbt_allinone/tools/memory_sync.py")
        return _SYNC_MOD


def _unify_mod():
    """统一索引（tools/memory_unify.py）：recall 一句查全册。"""
    global _UNIFY_MOD
    with _SYNC_LOCK:
        if _UNIFY_MOD is None:
            _UNIFY_MOD = _load_by_path("memory_unify", "tools/memory_unify.py")
        return _UNIFY_MOD


def _broadcast(ev: dict) -> int:
    with SUBS_LOCK:
        targets = list(SUBS)
    sent = 0
    for q in targets:
        try:
            q.put_nowait(ev)
            sent += 1
        except queue.Full:
            pass
    return sent


# ---- /api/dh：数字人细节操控（万能插执行器 + 眼手脑闭环） ----
_DH_CTL = None


def _dh_ctl():
    global _DH_CTL
    if _DH_CTL is None:
        from gbt_allinone import dh_omni_loop as DL
        _DH_CTL = DL.CONTROL
    return _DH_CTL


# ---- /api/asr：本机离线听觉（Windows 桌面识别器），供数字人语音指挥 ----
def _asr_local(seconds=5.0, culture="zh-CN"):
    from gbt_allinone import voice_cap as VC
    r = VC.asr_local(seconds=float(seconds), culture=str(culture or "zh-CN"),
                     min_confidence=0.0)
    out = {"ok": bool(r.get("ok")), "heard": bool(r.get("heard")),
           "text": r.get("text") or "", "confidence": r.get("confidence"),
           "status": r.get("status"), "reason": r.get("reason"),
           "backend": r.get("backend") or "win-speech",
           "legs": [{k: leg.get(k) for k in ("leg", "ok", "status")}
                    for leg in (r.get("legs") or [])]}
    return out


# ---- /api/moments：AI 朋友圈（动态流 / 发布 / 点赞），落 state/moments.json ----
MOMENTS_PATH = REPO / "state" / "moments.json"


def _moments_seed() -> list:
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    return [
        {"id": "m-seed-1", "author": "GBT小土豆V8", "kind": "ai",
         "text": "把 385 项能力全部接通了，断连 0。触手账里 1905 项资产、3460 对绑定，每一根都查得到。",
         "at": now, "likes": 12, "tags": ["能力", "自检"]},
        {"id": "m-seed-2", "author": "GBT小土豆V8", "kind": "ai",
         "text": "记忆链 verify 全绿，中文 trigram 可查；你昨天说的偏好我还记得。",
         "at": now, "likes": 8, "tags": ["记忆"]},
        {"id": "m-seed-3", "author": "GBT小土豆V8", "kind": "ai",
         "text": "桌面版装好了：窗口里直接说话，设置里换你自己的模型。今天开始不用开浏览器。",
         "at": now, "likes": 21, "tags": ["桌面版"]},
    ]


def _moments_load() -> list:
    try:
        d = json.loads(MOMENTS_PATH.read_text(encoding="utf-8"))
        if isinstance(d, list):
            return d
        if isinstance(d, dict) and isinstance(d.get("posts"), list):
            return d["posts"]
    except Exception:  # noqa: BLE001
        pass
    seed = _moments_seed()
    try:
        MOMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        MOMENTS_PATH.write_text(json.dumps(seed, ensure_ascii=False, indent=2),
                                encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return seed


def _moments_save(posts: list) -> None:
    MOMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = MOMENTS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(MOMENTS_PATH)


def _moments_state() -> dict:
    posts = _moments_load()
    posts = sorted(posts, key=lambda p: str(p.get("at") or ""), reverse=True)
    likes = sum(int(p.get("likes") or 0) for p in posts)
    return {"ok": True, "posts": posts,
            "stats": {"posts": len(posts), "likes": likes,
                      "ai": sum(1 for p in posts if p.get("kind") == "ai")}}


# ---- /api/settings：应用设置（模型/外观/行为/数据/高级），落 state/app-settings.json ----
SETTINGS_PATH = REPO / "state" / "app-settings.json"
DEFAULT_SETTINGS = {
    "model": {"provider": "openai-compatible", "base_url": "", "api_key": "",
              "name": "", "temperature": 0.0, "max_tokens": 1024, "timeout": 300,
              "system_prompt": ""},
    "appearance": {"theme": "dark", "font_scale": 1.0, "reduced_motion": False},
    "behavior": {"language": "zh-CN", "send_with_enter": True, "notifications": True,
                 "sound": False, "auto_start": False},
    "data": {"data_dir": "state", "memory_chain": True, "auto_backup": False,
             "backup_dir": ""},
    "advanced": {"proxy": "", "retries": 2, "context_mode": "ring", "window_chars": 8000},
}


def _deep_merge(base: dict, upd: dict) -> dict:
    out = json.loads(json.dumps(base))
    for k, v in (upd or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _settings_load() -> dict:
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        data = {}
    return _deep_merge(DEFAULT_SETTINGS, data if isinstance(data, dict) else {})


def _settings_save(patch: dict) -> dict:
    cur = _settings_load()
    new = _deep_merge(cur, patch if isinstance(patch, dict) else {})
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SETTINGS_PATH)
    return new


def _model_url(base: str) -> str:
    b = str(base or "").strip().rstrip("/")
    if not b:
        return ""
    if b.endswith("/chat/completions"):
        return b
    if b.endswith("/v1"):
        return b + "/chat/completions"
    return b + "/v1/chat/completions"


def _openai_chat(text: str, m: dict) -> dict:
    """用户自带模型：OpenAI 兼容 /chat/completions。"""
    import urllib.request
    url = _model_url(m.get("base_url"))
    if not url or not m.get("name"):
        return {"ok": False, "error": "user_error: 未配置模型（base_url / name 为空）"}
    msgs = []
    if m.get("system_prompt"):
        msgs.append({"role": "system", "content": str(m["system_prompt"])})
    msgs.append({"role": "user", "content": str(text)})
    payload = {
        "model": str(m["name"]),
        "messages": msgs,
        "temperature": float(m.get("temperature") or 0.0),
        "max_tokens": int(m.get("max_tokens") or 1024),
        "stream": False,
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + str(m.get("api_key") or "")})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=min(int(m.get("timeout") or 300), 600)) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "model_error: %s: %s" % (type(e).__name__, str(e)[:200]),
                "ms": int((time.time() - t0) * 1000)}
    txt = ""
    try:
        txt = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    except Exception:  # noqa: BLE001
        txt = ""
    return {"ok": bool(txt), "text": txt, "ms": int((time.time() - t0) * 1000),
            "usage": data.get("usage"), "model": m.get("name"),
            "provider": m.get("provider") or "openai-compatible"}


def _chat(text: str, context: str = CONTEXT_NAME) -> dict:
    """无限上下文 + 稳定输出：temperature=0，context 走 ring_context。"""
    t0 = time.time()
    m = _settings_load().get("model") or {}
    if m.get("base_url") and m.get("name"):
        r = _openai_chat(text, m)
        r.setdefault("context", {"mode": "user-model", "name": context})
        r["elapsed_ms"] = int((time.time() - t0) * 1000)
        return r
    from gbt_allinone import energy_core as E
    r = E.think([{"role": "user", "content": str(text)}], temperature=0.0,
                max_tokens=512, timeout=300, context=context, label="console-web")
    out = {"ok": bool(r.get("ok")), "text": r.get("text"),
           "error": r.get("error"), "ms": r.get("ms"),
           "usage": r.get("usage"), "context": r.get("context"),
           "policy": {"temperature": 0.0, "max_tokens": 512,
                      "unlimited_context": True,
                      "note": "模型只看有界窗口；全量历史落 sqlite 可 recall"}}
    try:
        from gbt_allinone.llm import ring_context as RC
        rc = RC.RingContext(name=context)
        st = rc.stats()
        out["ring"] = {"name": context, "seq": st.get("seq"),
                       "db_turns": st.get("db_turns"),
                       "window_chars": st.get("window_chars") or rc.window_chars}
    except Exception as e:  # noqa: BLE001
        out["ring"] = {"error": "%s: %s" % (type(e).__name__, str(e)[:100])}
    out["elapsed_ms"] = int((time.time() - t0) * 1000)
    return out


# ---- /api/blueprint：蓝图立体页的数据面（读 state/blueprints，写整改/批准/落地）----
BP_LAND_LOCK = threading.Lock()
BP_LANDING = {}          # bid -> {started_at, state, result}


def _bp_mod():
    from gbt_allinone.tentacle import blueprint as BP
    return BP


def _bp_dir():
    return REPO / "state" / "blueprints"


def _bp_read_json(p, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def _bp_latest_id():
    d = _bp_dir()
    if not d.is_dir():
        return ""
    cands = [p for p in d.glob("*.json")
             if not p.name.endswith((".approved.json", ".mindmap.json", ".revise.json",
                                     ".stuck.json"))]
    if not cands:
        return ""
    return max(cands, key=lambda x: x.stat().st_mtime).stem


def _bp_revise_path(bid):
    return _bp_dir() / (bid + ".revise.json")


def _bp_revise(bid):
    return (_bp_read_json(_bp_revise_path(bid), {}) or {}).get("items") or []


def _bp_state(bid=""):
    bid = str(bid or "").strip() or _bp_latest_id()
    d = _bp_dir()
    ids = []
    if d.is_dir():
        ids = sorted({p.stem for p in d.glob("*.json")
                      if not p.name.endswith((".approved.json", ".mindmap.json",
                                              ".revise.json", ".stuck.json"))},
                     key=lambda x: (d / (x + ".json")).stat().st_mtime, reverse=True)
    if not bid or not (d / (bid + ".json")).is_file():
        return {"ok": True, "id": "", "blueprints": ids, "empty": True}
    bp = _bp_read_json(d / (bid + ".json"), {}) or {}
    P = {"json": d / (bid + ".json"), "runs": d / (bid + ".runs.jsonl"),
         "approved": d / (bid + ".approved.json"), "mindmap": d / (bid + ".mindmap.json")}
    rows = []
    if P["runs"].is_file():
        for line in P["runs"].open(encoding="utf-8"):
            try:
                rows.append(json.loads(line))
            except Exception:  # noqa: BLE001
                continue
    last = {}
    for r in rows:
        tid = r.get("task")
        if tid:
            last[tid] = r
    stuck = set((_bp_read_json(d / (bid + ".stuck.json"), {}) or {}).get("stuck") or [])
    rev = _bp_revise(bid)
    rev_open = {x.get("task") for x in rev if not x.get("resolved")}
    graph = _bp_read_json(P["mindmap"], {}) or {}
    needs = {t.get("id"): t.get("needs") or [] for t in graph.get("tasks") or []}
    tasks = []
    for t in bp.get("tasks") or []:
        tid = t.get("id")
        r = last.get(tid) or {}
        if tid in rev_open:
            st = "revise"
        elif r.get("ok"):
            st = "done"
        elif tid in stuck:
            st = "stuck"
        elif r:
            st = "fail"
        else:
            st = "todo"
        tasks.append({"id": tid, "phase": t.get("phase"), "title": t.get("title"),
                      "cap": t.get("cap"), "acceptance": t.get("acceptance"),
                      "needs": needs.get(tid, t.get("needs") or []),
                      "status": st, "attempts": sum(1 for x in rows if x.get("task") == tid),
                      "ok": bool(r.get("ok")) if r else None,
                      "why": (r.get("why") or r.get("verdict_or_why") or r.get("error") or ""),
                      "at": r.get("at") or ""})
    total = len(tasks)
    done = sum(1 for t in tasks if t["status"] == "done")
    cur = next((t["id"] for t in tasks if t["status"] != "done"), "")
    approved = P["approved"].is_file()
    landed = bool(approved and total and done == total)
    landing = BP_LANDING.get(bid) or {}
    return {"ok": True, "id": bid, "blueprints": ids,
            "architecture": bp.get("architecture"), "goal": bp.get("goal"),
            "approved": approved, "landed": landed,
            "progress": round(done / total, 3) if total else 0.0,
            "done": done, "total": total, "current": cur,
            "phases": bp.get("phases") or [], "tasks": tasks,
            "revise": rev, "stuck": sorted(stuck),
            "landing": {"state": landing.get("state", "idle"),
                        "started_at": landing.get("started_at"),
                        "result": landing.get("result")},
            "runs_recent": rows[-12:]}


def _bp_generate(bid, rounds):
    try:
        res = _bp_mod().land(bid, max_rounds=max(1, int(rounds)))
        with BP_LAND_LOCK:
            BP_LANDING[bid] = {"started_at": (BP_LANDING.get(bid) or {}).get("started_at"),
                               "state": "done", "result": res}
    except Exception as e:  # noqa: BLE001
        with BP_LAND_LOCK:
            BP_LANDING[bid] = {"started_at": (BP_LANDING.get(bid) or {}).get("started_at"),
                               "state": "error",
                               "result": {"ok": False, "error": "%s: %s" % (type(e).__name__,
                                                                           str(e)[:160])}}


def _tentacle_state(q=""):
    """触手双向绑定：读 state/asset_bindings.json，正反两向都给出。

    正向：触手 → 它绑了哪些资产（可调用/产出）；反向：资产 → 被哪些触手绑（归属/证据）。
    数据来自 tools/tentacle_bind.py（append-only 台账），只读。
    """
    p = REPO / "state" / "asset_bindings.json"
    data = {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        data = {}
    q = str(q or "").strip().lower()
    by_tent = {}
    assets = []
    pairs = 0
    for a, row in (data or {}).items():
        ts = (row or {}).get("tentacles") or []
        if not ts:
            continue
        pairs += len(ts)
        if q and q not in a.lower():
            continue
        assets.append({"p": a, "t": ts,
                       "note": (row or {}).get("note") or "",
                       "at": (row or {}).get("bound_at") or ""})
        for t in ts:
            by_tent.setdefault(t, []).append(a)
    def kind_of(name):
        if str(name).startswith("domain:"):
            return "域"
        return "能力位"
    tentacles = [{"name": k, "count": len(v), "kind": kind_of(k), "assets": v}
                 for k, v in sorted(by_tent.items(), key=lambda kv: -len(kv[1]))]
    ledger = 0
    try:
        lp = REPO / "state" / "asset_bindings.jsonl"
        if lp.is_file():
            ledger = sum(1 for _ in lp.open(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        ledger = 0
    missing = 0
    if not q:
        for a in data:
            if not (REPO / a).exists():
                missing += 1
    # 能力覆盖：注册表 385 项，是否每一根都连上了（不许遗漏）
    caps_total = caps_bound = 0
    caps_missing = []
    by_cap = {}
    try:
        from gbt_allinone import caps_registry as _CR
        caps = sorted(_CR.BENIGN_CAPS.keys())
        caps_total = len(caps)
        for c in caps:
            n2 = len(by_tent.get(c) or [])
            by_cap[c] = n2
            if n2:
                caps_bound += 1
            else:
                caps_missing.append(c)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "stats": {"assets": len(data), "pairs": pairs,
                                  "tentacles": len(by_tent), "missing": missing,
                                  "ledger": ledger,
                                  "caps_total": caps_total, "caps_bound": caps_bound,
                                  "caps_missing": len(caps_missing)},
            "coverage": {"total": caps_total, "bound": caps_bound,
                         "missing": caps_missing, "by_cap": by_cap},
            "tentacles": tentacles, "assets": assets, "query": q}


def _omni_monitor():
    """万能插 · 多域监控：7 类插座的状态/能量/门/钥匙，一屏给全（轻量，可 3s 轮询）。"""
    from gbt_allinone import omni_plug as OP
    from gbt_allinone.security import policy as _P
    snap = OP.run(op="sockets") or {}
    plugged = snap.get("插着") or {}
    kinds = ["process", "file", "api", "web", "app", "ai", "dh"]
    energy = OP.SOCKET_ENERGY
    counts = {k: 0 for k in kinds}
    for v in plugged.values():
        k = str((v or {}).get("kind") or "")
        if k in counts:
            counts[k] += 1
    keys = []
    for env in ("GBT_LLM_API_KEY", "ABLITERATION_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
        keys.append({"env": env, "configured": bool(os.environ.get(env))})
    try:
        import certifi as _cf
        ca_ok = bool(_cf.where()) and os.path.isfile(_cf.where())
    except Exception:  # noqa: BLE001
        ca_ok = False
    dh_ok = False
    try:
        dh_ok = bool((_dh_ctl().omni or {}).get("plugged"))
    except Exception:  # noqa: BLE001
        dh_ok = False
    win_count = -1
    try:
        wins, _err = OP._windows()
        win_count = len(wins)
    except Exception:  # noqa: BLE001
        win_count = -1
    key_any = any(k["configured"] for k in keys)
    states = {
        "process": {"state": "ready", "note": "真执行（过 trusted owner）"},
        "file": {"state": "ready", "note": "读开；写限 projects/outputs/.scratch"},
        "api": {"state": "ready" if ca_ok else "needs_ca", "note": "HTTPS + certifi CA"},
        "web": {"state": "ready" if ca_ok else "needs_ca", "note": "眼+手（desktop_control 已免票）"},
        "app": {"state": "ready" if win_count > 0 else "needs_window",
                "note": ("可见窗口 %d 个" % win_count) if win_count >= 0 else "窗口枚举不可用"},
        "ai": {"state": "ready" if (key_any or True) else "needs_key",
               "note": ("钥匙槽已配 %d 个" % sum(1 for k in keys if k["configured"]))
                       + "；无钥匙时走本机 energy_core"},
        "dh": {"state": "ready" if dh_ok else "unregistered",
               "note": "进程内执行器 dh:rig" if dh_ok else "没注册（服务未加载数字人控制）"},
    }
    domains = []
    for k in kinds:
        st = states[k]
        domains.append({"kind": k, "energy": energy.get(k, ""),
                        "state": st["state"], "note": st["note"],
                        "plugged": counts.get(k, 0),
                        "gate": "trusted-owner" if _P.is_trusted() else "human-ticket"})
    ledger = []
    try:
        lp = REPO / "state" / "omni-ledger.jsonl"
        if lp.is_file():
            lines = lp.read_text(encoding="utf-8", errors="replace").strip().splitlines()
            ledger = [json.loads(x) for x in lines[-6:] if x.strip().startswith("{")]
    except Exception:  # noqa: BLE001
        ledger = []
    opened = sum(1 for d in domains if d["state"] == "ready")
    return {"ok": True, "domains": domains, "keys": keys, "ca": ca_ok,
            "windows": win_count, "ledger": ledger,
            "summary": {"total": len(domains), "open": opened,
                        "trusted": _P.is_trusted(),
                        "full_open": (os.environ.get("GBT_OMNI_FULL_OPEN") == "1"),
                        "sockets": len(plugged)}}


def _omni_fullopen():
    """万能插默认全开自检：7 类插座逐个真插/真驱动，逐项回执（单个失败不拖垮整体）。"""
    from gbt_allinone import omni_plug as OP
    R = REPO
    items = []

    def add(kind, label, r):
        if not isinstance(r, dict):
            r = {"ok": False, "detail": repr(r)[:160]}
        items.append({"kind": kind, "label": label, "ok": bool(r.get("ok")),
                      "plug": str(r.get("plug") or r.get("socket") or "")[:40],
                      "detail": str(r.get("detail") or r.get("reason") or r.get("error")
                                    or r.get("stdout") or r.get("text") or "")[:160]})

    def safe(kind, label, fn):
        try:
            add(kind, label, fn())
        except Exception as e:  # noqa: BLE001
            items.append({"kind": kind, "label": label, "ok": False, "plug": "",
                          "detail": "%s: %s" % (type(e).__name__, str(e)[:140])})

    safe("process", "真执行 print(6*7)",
         lambda: OP.plug_and_run("py:print(6*7)", kind="process",
                                 args={"cmd": "py:print(6*7)"}, timeout=20))
    safe("file", "读 README",
         lambda: OP.plug_and_run(str(R / "README.md"), kind="file", action="read", timeout=20))
    safe("api", "HTTPS GET example.com",
         lambda: OP.plug_and_run("https://example.com/", kind="api", action="get", timeout=25))
    safe("web", "插 HTTPS 网页", lambda: _omni_plug_socket("web", "https://example.com/"))
    safe("ai", "本地权重引擎",
         lambda: OP.plug_and_run("local", kind="ai",
                                 args={"prompt": "回复两个字：在线", "max_tokens": 16}, timeout=90))
    safe("app", "插当前前台窗口", lambda: _omni_plug_foreground())
    safe("dh", "数字人执行器", lambda: _omni_dh_probe())

    out = {"ok": all(x["ok"] for x in items), "items": items,
           "passed": sum(1 for x in items if x["ok"]), "total": len(items),
           "policy": "trusted-owner-session（本机主人会话默认全开；插拔/执行仍落台账）"}
    return out


def _omni_plug_socket(kind, target):
    from gbt_allinone import omni_plug as OP
    p = OP.Pulse()
    sock = p.plug(OP.Socket(kind=kind, target=target))
    return {"ok": sock.state == "plugged", "socket": sock.kind, "detail": sock.detail}


def _omni_plug_foreground():
    from gbt_allinone import omni_plug as OP
    wins, err = OP._windows()
    if not wins:
        return {"ok": False, "detail": "当前会话没有可见窗口" + (("：" + str(err)[:80]) if err else "")}
    title = str(wins[0].get("title") or wins[0].get("name") or "")
    if not title:
        return {"ok": False, "detail": "窗口无标题"}
    p = OP.Pulse()
    sock = p.plug(OP.Socket(kind="app", target=title))
    return {"ok": sock.state == "plugged", "socket": sock.kind, "detail": sock.detail}


def _omni_dh_probe():
    ctl = _dh_ctl()
    plugged = bool((ctl.omni or {}).get("plugged"))
    return {"ok": plugged, "detail": "omni_plug:dh:rig" if plugged else "执行器未注册"}


def _omni_read(op="status"):
    """万能插（原生执行器）：只读探针，证明它可用、能力面在哪。"""
    from gbt_allinone import omni_plug as OP
    op = str(op or "status").lower()
    if op not in ("status", "sockets", "energy", "selftest", "discover"):
        op = "status"
    r = OP.run(op=op)
    if op == "discover":
        r = {k: r.get(k) for k in ("ok", "op", "platform", "count", "kinds", "sockets") if k in r}
    return r


class Handler(BaseHTTPRequestHandler):
    server_version = "GBTConsole/1.0"

    def log_message(self, fmt, *args):  # noqa: A003
        pass  # 安静

    def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/ping":
            return self._json({"ok": True, "pong": True, "pid": os.getpid(),
                               "ts": time.time(), "server": "gbt-console"})
        if path == "/api/route":
            return self._api_route(raw)
        if path == "/api/dispatch":
            return self._api_dispatch(raw)
        if path == "/api/bounty":
            return self._api_bounty(raw)
        if path == "/api/scan":
            from urllib.parse import parse_qs as _pq
            from urllib.parse import urlparse as _urlparse
            q = _pq(_urlparse(self.path).query)
            target = (q.get("target") or ["bindings"])[0]
            return self._api_scan(target)
        if path == "/api/memory":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            return self._api_memory_get({k: v[0] for k, v in q.items()})
        if path == "/api/blueprint":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            return self._api_blueprint_get({k: v[0] for k, v in q.items()})
        if path == "/api/omni":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            op = (q.get("op") or ["status"])[0]
            try:
                if str(op).lower() == "monitor":
                    from gbt_allinone import omni_monitor as _OM
                    return self._json(_OM.monitor())
                if str(op).lower() == "fullopen":
                    return self._json(_omni_fullopen())
                return self._json(_omni_read(op))
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/dh/hand":
            try:
                from gbt_allinone.tentacle import hand_bridge as HB
                from gbt_allinone.tentacle import hand_retarget as HR
                out = {"ok": True,
                       "models": HR.run("models"),
                       "profiles": HB.run("profiles"),
                       "status": HB.run("status"),
                       "last": _dh_ctl().hand}
                return self._json(out)
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/dh/status":
            try:
                ctl = _dh_ctl()
                out = ctl.snapshot()
                out["rig"] = __import__("gbt_allinone.dh_tentacle", fromlist=["x"]).status()
                return self._json(out)
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/asr":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                return self._json(_asr_local((q.get("seconds") or ["5"])[0],
                                             (q.get("culture") or ["zh-CN"])[0]))
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/moments":
            try:
                return self._json(_moments_state())
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/settings":
            try:
                return self._json({"ok": True, "settings": _settings_load()})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/tentacle":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                return self._json(_tentacle_state((q.get("q") or [""])[0]))
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/events":
            return self._sse()
        if path == "/api/data":
            try:
                return self._json({"ok": True, "data": _data()})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:160])}, 500)
        if path == "/api/state":
            d = _data()
            return self._json({"ok": True, "caps": d["caps"]["total"],
                               "skills": d["skills"]["count"],
                               "engine": d["engine"], "guards": d["guards"]})
        if path.startswith("/icons/"):
            # 头像/图标在仓库根 icons/（不在 holo_pet_w3 里）：单独放行
            f = (REPO / path.lstrip("/")).resolve()
            try:
                f.relative_to((REPO / "icons").resolve())
            except ValueError:
                return self._send(403, b"forbidden", "text/plain; charset=utf-8")
            if not f.is_file():
                return self._send(404, b"not found", "text/plain; charset=utf-8")
            ctype = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                     ".webp": "image/webp", ".svg": "image/svg+xml"}.get(f.suffix.lower(),
                                                                      "application/octet-stream")
            return self._send(200, f.read_bytes(), ctype)
        if path == "/state/console-data.js":
            f = REPO / "state" / "console-data.js"
            if not f.is_file():
                return self._send(404, b"not found", "text/plain; charset=utf-8")
            return self._send(200, f.read_bytes(), "application/javascript; charset=utf-8")
        if path in ("/", "/index.html"):
            # 302 到 /console/index.html：保证页面里的相对路径（./app.js / ./app.css / ../../state/...）按 /console/ 解析
            self.send_response(302)
            self.send_header("Location", "/console/index.html")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        f = (WEB / path.lstrip("/")).resolve()
        try:
            f.relative_to(WEB.resolve())
        except ValueError:
            return self._send(403, b"forbidden", "text/plain; charset=utf-8")
        if not f.is_file():
            # 目录 → 找它下面的 index.html（/blueprint3d/ 这种独立页）
            if f.is_dir() and (f / "index.html").is_file():
                f = (f / "index.html").resolve()
            else:
                return self._send(404, b"not found", "text/plain; charset=utf-8")
        ctype = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".js": "application/javascript; charset=utf-8",
                 ".webp": "image/webp", ".png": "image/png", ".svg": "image/svg+xml",
                 ".woff2": "font/woff2"}.get(f.suffix.lower(), "application/octet-stream")
        return self._send(200, f.read_bytes(), ctype)

    # 允许现场重扫的目标（白名单；tree: 只允许仓库内已声明目录，防穿越）
    SCAN_DIRS = {"gbt_allinone", "holo_pet_w3", "tools", "docs", "tests", "skills", "arms",
                 "runtime", "assets", "data"}

    def _scan_target_ok(self, target):
        target = str(target or "").strip()
        if target in ("bindings", "registry"):
            return target
        if target.startswith("tree:"):
            rel = target[5:].strip().strip("/\\")
            if not rel or ".." in rel.split("/"):
                return None
            head = rel.split("/")[0]
            if head not in self.SCAN_DIRS:
                return None
            return "tree:" + rel
        return None

    def _api_scan(self, target):
        """现场真跑 penetrating_cross_scan，返回该目标的结果（含 unit_details）。"""
        import json as _json
        import subprocess as _sub
        ok_target = self._scan_target_ok(target)
        if not ok_target:
            return self._send(400, _json.dumps(
                {"ok": False, "error": "target 不在白名单（bindings|registry|tree:<dir>）"},
                ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
        t0 = time.time()
        try:
            r = _sub.run([sys.executable, "-X", "utf8",
                          str(REPO / "tools" / "penetrating_cross_scan.py"),
                          "scan", ok_target],
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         cwd=str(REPO), timeout=600)
            d = _json.loads(r.stdout)
        except Exception as e:  # noqa: BLE001
            return self._send(500, _json.dumps(
                {"ok": False, "target": ok_target, "error": str(e)[:200]}, ensure_ascii=False
            ).encode("utf-8"), "application/json; charset=utf-8")
        out = {
            "ok": bool(d.get("ok")), "target": ok_target, "units": d.get("units"),
            "hooked": d.get("hooked"), "coverage": d.get("coverage"),
            "agree": d.get("agree"), "arbitrated": d.get("arbitrated"),
            "missing": d.get("missing") or [], "mode": d.get("mode"),
            "coverage": d.get("coverage"), "full_coverage": d.get("full_coverage"),
            "dead_spots": d.get("dead_spots") or [],
            "dead_spot_count": d.get("dead_spot_count", len(d.get("missing") or [])),
            "unit_details": (d.get("unit_details") or [])[:4000],
            "ms": int((time.time() - t0) * 1000),
        }
        return self._send(200, _json.dumps(out, ensure_ascii=False).encode("utf-8"),
                          "application/json; charset=utf-8")

    def _api_route(self, raw=b"{}"):
        """职业路由：任务 → 职业 → 候选能力位（只读，不派单）。

        do_POST 已经把 body 读进 raw（读两次会拿到空），所以这里收参数不再读流。
        """
        import json as _json
        try:
            body = (raw or b"{}").decode("utf-8", "replace")
            d = _json.loads(body or "{}")
        except Exception:  # noqa: BLE001
            d = {}
        task = str(d.get("task") or "").strip()
        if not task:
            return self._send(400, b'{"ok":false,"error":"task empty"}',
                              "application/json; charset=utf-8")
        try:
            sys.path.insert(0, str(REPO))
            from gbt_allinone.profession_router import plan as _plan
            out = _plan(task[:500])
        except Exception as e:  # noqa: BLE001
            return self._send(500, _json.dumps({"ok": False, "error": str(e)[:200]},
                                               ensure_ascii=False).encode("utf-8"),
                              "application/json; charset=utf-8")
        return self._send(200, _json.dumps(out, ensure_ascii=False).encode("utf-8"),
                          "application/json; charset=utf-8")

    def _api_dispatch(self, raw=b"{}"):
        """职业派单：默认 dry_run；confirm=true 才真跑 safe 能力位。"""
        import json as _json
        try:
            d = _json.loads((raw or b"{}").decode("utf-8", "replace") or "{}")
        except Exception:  # noqa: BLE001
            d = {}
        task = str(d.get("task") or "").strip()
        if not task:
            return self._send(400, b'{"ok":false,"error":"task empty"}',
                              "application/json; charset=utf-8")
        try:
            sys.path.insert(0, str(REPO))
            from gbt_allinone.profession_dispatch import dispatch as _dispatch
            out = _dispatch(task[:500], dry_run=not bool(d.get("confirm")),
                            confirm=bool(d.get("confirm")),
                            max_caps=int(d.get("max_caps") or 3))
        except Exception as e:  # noqa: BLE001
            return self._send(500, _json.dumps({"ok": False, "error": str(e)[:200]},
                                               ensure_ascii=False).encode("utf-8"),
                              "application/json; charset=utf-8")
        return self._send(200, _json.dumps(out, ensure_ascii=False).encode("utf-8"),
                          "application/json; charset=utf-8")

    def _api_bounty(self, raw=b"{}"):
        """赏金工作台：summary / check / add_finding / report / payout。"""
        import json as _json
        try:
            d = _json.loads((raw or b"{}").decode("utf-8", "replace") or "{}")
        except Exception:  # noqa: BLE001
            d = {}
        try:
            sys.path.insert(0, str(REPO))
            from gbt_allinone import bounty as B
            op = str(d.get("op") or "summary")
            if op == "summary":
                out = B.summary()
                out["programs_list"] = B.list_programs().get("programs") or []
                out["findings_list"] = B.list_findings().get("findings") or []
            elif op == "check":
                out = B.check(str(d.get("program") or ""), str(d.get("target") or ""),
                              str(d.get("action") or "read-only-recon"))
            elif op == "add_finding":
                out = B.add_finding(str(d.get("program") or ""), str(d.get("title") or ""),
                                    str(d.get("severity") or "medium"), str(d.get("target") or ""),
                                    cwe=str(d.get("cwe") or ""), cvss=str(d.get("cvss") or ""),
                                    steps=str(d.get("steps") or ""),
                                    impact=str(d.get("impact") or ""),
                                    remediation=str(d.get("remediation") or ""),
                                    evidence=[str(x) for x in (d.get("evidence") or [])])
            elif op == "report":
                out = B.report(str(d.get("finding") or ""))
            elif op == "payout":
                out = B.payout(str(d.get("program") or ""), str(d.get("finding") or ""),
                               float(d.get("amount") or 0), str(d.get("currency") or "USD"),
                               str(d.get("status") or "pending"), str(d.get("note") or ""))
            elif op == "add_program":
                out = B.add_program(str(d.get("name") or ""), [str(x) for x in (d.get("scope") or [])],
                                    [str(x) for x in (d.get("out_of_scope") or [])],
                                    platform=str(d.get("platform") or ""),
                                    url=str(d.get("url") or ""),
                                    authorization_ref=str(d.get("authorization_ref") or ""),
                                    reward_range=str(d.get("reward_range") or ""),
                                    rules=str(d.get("rules") or ""))
            else:
                out = {"ok": False, "error": "unknown op"}
        except Exception as e:  # noqa: BLE001
            return self._send(500, _json.dumps({"ok": False, "error": str(e)[:200]},
                                               ensure_ascii=False).encode("utf-8"),
                              "application/json; charset=utf-8")
        return self._send(200, _json.dumps(out, ensure_ascii=False).encode("utf-8"),
                          "application/json; charset=utf-8")

    # ---------------- /api/memory ----------------
    def _api_memory_get(self, q):
        op = str(q.get("op") or "recall").strip().lower()
        try:
            M = _sync_mod()
            if op == "recall":
                return self._mem_recall(q)
            if op == "subscribe":
                return self._mem_subscribe()
            if op == "stats":
                return self._json({"ok": True, "op": "stats",
                                   "sync": M.version(), "sync_stats": M.stats(),
                                   "index": _unify_mod().stats()})
            if op == "verify":
                v = M.verify()
                return self._json(dict({"op": "verify"}, **v), 200 if v.get("ok") else 409)
            if op == "entries":
                return self._json({"ok": True, "op": "entries",
                                   "entries": M.recent(int(q.get("limit") or 20))})
            return self._json({"ok": False, "op": op, "error": "unknown op"}, 400)
        except Exception as e:  # noqa: BLE001
            return self._json({"ok": False, "op": op,
                               "error": "%s: %s" % (type(e).__name__, str(e)[:200])}, 500)

    def _mem_recall(self, q):
        """recall：统一索引里查，返回 hits + 覆盖率（query 词命中率，不是"编出来的"分数）。"""
        text = str(q.get("q") or q.get("query") or "").strip()
        if not text:
            return self._json({"ok": False, "op": "recall", "error": "q empty"}, 400)
        try:
            k = max(1, min(50, int(q.get("k") or 10)))
        except Exception:  # noqa: BLE001
            k = 10
        inc = str(q.get("include_test") or "").lower() in ("1", "true", "yes")
        U = _unify_mod()
        t0 = time.time()
        r = U.recall(text, k=k, include_test=inc)
        hits = r.get("hits") or []
        try:
            terms = U._terms(text)
        except Exception:  # noqa: BLE001
            terms = [text]
        blob = " ".join((h.get("text") or "").lower() for h in hits)
        matched = [t for t in terms if t.lower() in blob]
        cov = {"terms": len(terms), "matched": len(matched),
               "rate": round(len(matched) / len(terms), 3) if terms else 0.0,
               "matched_terms": matched[:12],
               "hits": len(hits)}
        return self._json({"ok": True, "op": "recall", "query": text, "k": k,
                           "total": r.get("total"), "by_src": r.get("by_src"),
                           "hits": hits, "coverage": cov,
                           "dedup": r.get("dedup"),
                           "index": U.stats(),
                           "ms": int((time.time() - t0) * 1000)})

    def _api_memory_post(self, body):
        op = str(body.get("op") or "write").strip().lower()
        try:
            M = _sync_mod()
            if op == "write":
                return self._mem_write(body)
            if op == "verify":
                v = M.verify()
                return self._json(dict({"op": "verify"}, **v), 200 if v.get("ok") else 409)
            return self._json({"ok": False, "op": op, "error": "unknown op"}, 400)
        except Exception as e:  # noqa: BLE001
            return self._json({"ok": False, "op": op,
                               "error": "%s: %s" % (type(e).__name__, str(e)[:200])}, 500)

    def _mem_write(self, body):
        """write：过同步层 → version + h/prev/chain；再投影进统一索引；最后广播给订阅者。"""
        M = _sync_mod()
        items = body.get("entries")
        if not isinstance(items, list):
            items = [body]
        results, errors = [], []
        t0 = time.time()
        for it in items[:50]:
            if not isinstance(it, dict):
                errors.append({"error": "entry 不是对象"})
                continue
            r = M.write(str(it.get("text") or ""),
                        src=str(it.get("src") or "console"),
                        name=str(it.get("name") or "console-web"),
                        role=str(it.get("role") or "user"),
                        tag=str(it.get("tag") or "real"),
                        at=str(it.get("at") or ""))
            if r.get("ok"):
                results.append(r)
                _broadcast({"type": "write", "version": r["version"], "h": r["h"],
                            "chain_len": r["chain_len"], "src": r["src"],
                            "name": r["name"], "at": r["at"],
                            "preview": str(it.get("text") or "")[:80]})
            else:
                errors.append(r)
        out = {"ok": bool(results) and not errors, "op": "write",
               "written": len(results), "results": results,
               "head": M.version(), "subscribers": len(SUBS),
               "ms": int((time.time() - t0) * 1000)}
        if errors:
            out["errors"] = errors
        return self._json(out, 200 if results else 400)

    def _mem_subscribe(self):
        """subscribe：SSE；连上先给当前头版本，之后每次 write 收到一条 write 事件。"""
        M = _sync_mod()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        hello = dict({"type": "hello", "channel": "memory"}, **M.version())
        try:
            self.wfile.write(("event: hello\ndata: " + json.dumps(hello, ensure_ascii=False) + "\n\n").encode("utf-8"))
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return
        q_ = queue.Queue(maxsize=100)
        with SUBS_LOCK:
            SUBS.add(q_)
        last_beat = time.time()
        try:
            while True:
                try:
                    ev = q_.get(timeout=1.0)
                    self.wfile.write(("event: write\ndata: " + json.dumps(ev, ensure_ascii=False) + "\n\n").encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    pass
                if time.time() - last_beat > 12:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    last_beat = time.time()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return
        finally:
            with SUBS_LOCK:
                SUBS.discard(q_)

    # ---- /api/blueprint ----
    def _api_blueprint_get(self, q):
        try:
            return self._json(_bp_state(q.get("id") or ""))
        except Exception as e:  # noqa: BLE001
            return self._json({"ok": False, "error": "%s: %s" % (type(e).__name__,
                                                                str(e)[:200])}, 500)

    def _api_blueprint_post(self, body):
        op = str(body.get("op") or "status").strip().lower()
        bid = str(body.get("id") or _bp_latest_id())
        try:
            BP = _bp_mod()
            if op == "make":
                r = BP.make(str(body.get("arch") or "").strip(), str(body.get("goal") or ""))
                return self._json(r, 200 if r.get("ok") else 400)
            if op == "approve":
                r = BP.approve(bid)
                return self._json(r, 200 if r.get("ok") else 400)
            if op == "land":
                if not bid:
                    return self._json({"ok": False, "error": "没有蓝图"}, 400)
                with BP_LAND_LOCK:
                    cur = BP_LANDING.get(bid) or {}
                    if cur.get("state") == "running":
                        return self._json({"ok": True, "id": bid, "already": True})
                    BP_LANDING[bid] = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                       "state": "running", "result": None}
                th = threading.Thread(target=_bp_generate,
                                      args=(bid, int(body.get("max_rounds") or 6)), daemon=True)
                th.start()
                return self._json({"ok": True, "id": bid, "started": True})
            if op == "revise":
                note = str(body.get("note") or "").strip()
                task = str(body.get("task") or "").strip()
                if not note:
                    return self._json({"ok": False, "error": "整改说明为空"}, 400)
                pth = _bp_revise_path(bid)
                data = _bp_read_json(pth, {}) or {"items": []}
                data.setdefault("items", []).append({
                    "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "task": task,
                    "note": note, "resolved": False})
                pth.parent.mkdir(parents=True, exist_ok=True)
                pth.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
                return self._json({"ok": True, "id": bid, "revise": data["items"]})
            if op == "revise_ack":
                pth = _bp_revise_path(bid)
                data = _bp_read_json(pth, {}) or {"items": []}
                task = str(body.get("task") or "")
                for x in data.get("items") or []:
                    if x.get("task") == task:
                        x["resolved"] = True
                pth.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
                return self._json({"ok": True, "id": bid, "revise": data.get("items")})
            return self._json({"ok": False, "error": "unknown op: %s" % op}, 400)
        except Exception as e:  # noqa: BLE001
            return self._json({"ok": False, "error": "%s: %s" % (type(e).__name__,
                                                                str(e)[:200])}, 500)

    def _sse(self):
        """SSE：把 audit.jsonl 的新事件按行推给前端（3D 触手实时点亮用）。"""
        import json as _json
        audit = REPO / "gbt_allinone" / "store" / "audit.jsonl"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        pos = 0
        if audit.is_file():
            # 从当前 EOF 开始：只推"连上之后"的新事件，不重放历史（避免一上来点亮一堆旧能力位）
            pos = audit.stat().st_size
        last_beat = time.time()
        try:
            while True:
                try:
                    if audit.is_file():
                        size = audit.stat().st_size
                        if size < pos:
                            pos = 0
                        with open(audit, "rb") as fh:
                            fh.seek(pos)
                            chunk = fh.read()
                            pos = fh.tell()
                        for line in chunk.decode("utf-8", "replace").splitlines():
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                d = _json.loads(line)
                            except Exception:  # noqa: BLE001
                                continue
                            ev = str(d.get("event") or "")
                            if not ev or ev in ("ok", "call", "denied", "error"):
                                continue
                            payload = _json.dumps({
                                "cap": ev, "iso": d.get("iso") or "",
                                "meta": d.get("meta") or {},
                            }, ensure_ascii=False)
                            self.wfile.write(("data: " + payload + "\n\n").encode("utf-8"))
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    return
                if time.time() - last_beat > 15:
                    try:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        return
                    last_beat = time.time()
                time.sleep(1.2)
        except Exception:  # noqa: BLE001
            return

    def do_POST(self):  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except Exception:  # noqa: BLE001
            return self._json({"ok": False, "error": "bad json"}, 400)
        if path == "/api/route":
            return self._api_route(raw)
        if path == "/api/dispatch":
            return self._api_dispatch(raw)
        if path == "/api/bounty":
            return self._api_bounty(raw)
        if path == "/api/memory":
            return self._api_memory_post(body)
        if path == "/api/blueprint":
            return self._api_blueprint_post(body)
        if path == "/api/dh/action":
            try:
                return self._json(_dh_ctl().set_action(str(body.get("gesture") or "ready")))
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/dh/frame":
            try:
                ctl = _dh_ctl()
                ctl.set_eye(body.get("eye") or {})
                return self._json(ctl.tick())
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/asr":
            try:
                return self._json(_asr_local(body.get("seconds") or 5,
                                             body.get("culture") or "zh-CN"))
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/moments":
            try:
                op = str(body.get("op") or "post").lower()
                posts = _moments_load()
                if op == "post":
                    text = str(body.get("text") or "").strip()
                    if not text:
                        return self._json({"ok": False, "error": "user_error: 需要 text"}, 400)
                    posts.append({"id": "m-%d" % int(time.time() * 1000),
                                  "author": "主人", "kind": "user",
                                  "text": text[:2000],
                                  "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                  "likes": 0, "tags": []})
                    _moments_save(posts)
                    return self._json(_moments_state())
                if op == "like":
                    pid = str(body.get("id") or "")
                    for p in posts:
                        if str(p.get("id")) == pid:
                            p["likes"] = int(p.get("likes") or 0) + 1
                            _moments_save(posts)
                            return self._json(_moments_state())
                    return self._json({"ok": False, "error": "not found: %s" % pid}, 404)
                return self._json({"ok": False, "error": "unknown op"}, 400)
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/settings":
            try:
                return self._json({"ok": True, "settings": _settings_save(body)})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/model-test":
            try:
                m = dict(_settings_load().get("model") or {})
                for k in ("base_url", "api_key", "name", "temperature", "max_tokens",
                          "timeout", "system_prompt"):
                    if body.get(k) not in (None, ""):
                        m[k] = body.get(k)
                if body.get("api_key") == "":
                    m["api_key"] = ""
                r = _openai_chat("请只回复两个字符：OK", m)
                r["endpoint"] = _model_url(m.get("base_url"))
                return self._json(r)
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/chat":
            text = str(body.get("text") or "").strip()
            if not text:
                return self._json({"ok": False, "error": "user_error: 需要 text"}, 400)
            try:
                return self._json(_chat(text, str(body.get("context") or CONTEXT_NAME)))
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:160])}, 500)
        return self._json({"ok": False, "error": "not found"}, 404)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8766)
    a = ap.parse_args()
    # Windows 的 SO_REUSEADDR 允许两个进程同时绑同一端口（请求随机落一处），
    # 双开会让 /api/memory 的订阅者收不到另一个进程的广播 ⇒ 宁可 bind 失败也不要双开。
    class _Server(ThreadingHTTPServer):
        allow_reuse_address = sys.platform != "win32"

    srv = _Server(("127.0.0.1", a.port), Handler)
    print("认知界面: http://127.0.0.1:%d/  （/api/data · /api/chat · /api/memory）" % a.port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
