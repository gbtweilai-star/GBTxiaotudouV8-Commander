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
GBT_PERSONA = ("你是 GBT小土豆V8（小土豆），不是普通聊天模型。你运行在本机桌面版，拥有 385 项能力域、触手执行器、"
               "万能插（process/file/api/web/app/ai/dh）、数字人、AI 朋友圈、主动智能体等真实能力。"
               "严禁回答“我只是语言模型/我不能做任何事”。被问能力时按实际能力回答；被要求做事时说明由哪个执行器/入口执行，"
               "不要否认自己的能力。")


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
VOICE_SETTINGS_PATH = REPO / "state" / "voice-settings.json"


def _voice_settings():
    """读本地语音设置（不存在→默认；坏文件→默认 + 不崩）。"""
    try:
        from gbt_allinone.tools import voice_settings as _VS
        if VOICE_SETTINGS_PATH.is_file():
            data = json.loads(VOICE_SETTINGS_PATH.read_text(encoding="utf-8"))
            return _VS.validate(data)
        return dict(_VS.DEFAULTS)
    except Exception:  # noqa: BLE001
        try:
            from gbt_allinone.tools import voice_settings as _VS
            return dict(_VS.DEFAULTS)
        except Exception:
            return {"asr_backend": "auto", "culture": "zh-CN", "auto_speak": True}


def _memory_audit_records():
    """把 memory_bank 的印章行转成审计记录（只读；不把长原文搬进 UI）。"""
    out = []
    f = REPO / "state" / "memory_bank.jsonl"
    if not f.is_file():
        return out
    try:
        for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:  # noqa: BLE001
                out.append({"id": "", "text": "", "at": "", "origin": "memory_bank"})
                continue
            if not isinstance(r, dict):
                continue
            ref = str(r.get("ref") or r.get("path") or "")
            text = str(r.get("why") or r.get("summary") or ref or "")
            out.append({"id": str(r.get("ref") or r.get("sha256") or r.get("at") or ""),
                        "text": text[:2000], "at": r.get("at") or "",
                        "origin": r.get("origin") or ""})
            if len(out) >= 500:
                break
    except Exception:  # noqa: BLE001
        return out
    return out


def _api_slots_snapshot():
    from gbt_allinone.tools import api_slot as _AS
    from gbt_allinone import api as _api
    f = REPO / "state" / "api_slots.json"
    try:
        if f.is_file() and _AS._REG.list().get("count", 0) == 0:
            data = json.loads(f.read_text(encoding="utf-8"))
            for s in (data if isinstance(data, list) else []):
                _api.run_task("api_slot", {"op": "register", "slot": s}, safe=True)
    except Exception:  # noqa: BLE001
        pass
    env = _api.run_task("api_slot", {"op": "list"}, safe=True)
    return ((env.get("gbt_result") or {}).get("result") if isinstance(env, dict) else None) or {}


def _api_slots_save():
    from gbt_allinone.tools import api_slot as _AS
    try:
        f = REPO / "state" / "api_slots.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(_AS._REG.list().get("slots") or [], ensure_ascii=False, indent=1),
                       encoding="utf-8")
        tmp.replace(f)
    except Exception:  # noqa: BLE001
        pass


MEDIA_ROOTS = [REPO / "media", REPO / "交付成片", REPO / "holo_pet_w3" / "kaleido", REPO / "outputs"]


def _turn_rows(limit=500):
    rows = []
    for name in ("orchestration-ledger.jsonl", "action_gate.jsonl"):
        f = REPO / "state" / name
        if not f.is_file():
            continue
        try:
            for ln in f.read_text(encoding="utf-8", errors="replace").splitlines()[-int(limit):]:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    r = json.loads(ln)
                except Exception:  # noqa: BLE001
                    continue
                if isinstance(r, dict):
                    r.setdefault("source", name.replace(".jsonl", ""))
                    rows.append(r)
        except OSError:
            continue
    return rows


def _media_scan(max_items=500):
    from gbt_allinone.tools import media_library as _ML
    out = []
    for root in MEDIA_ROOTS:
        if not root.is_dir():
            continue
        try:
            for p in root.rglob("*"):
                if len(out) >= max_items:
                    break
                if not p.is_file():
                    continue
                if not _ML.classify(str(p)):
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                out.append({"path": p.relative_to(REPO).as_posix(),
                            "size": int(st.st_size), "mtime": float(st.st_mtime)})
        except OSError:
            continue
    return out


def _media_resolve(rel):
    from gbt_allinone.tools import media_library as _ML
    try:
        rel = urllib.parse.unquote(str(rel or "")).replace("\\", "/").strip()
    except Exception:  # noqa: BLE001
        return None
    if not rel or rel.startswith("/") or ".." in rel.split("/") or ":" in rel.split("/")[0]:
        return None
    try:
        cand = (REPO / rel).resolve()
    except OSError:
        return None
    for root in MEDIA_ROOTS:
        try:
            if cand.is_relative_to(root.resolve()) and cand.is_file() and _ML.classify(str(cand)):
                return cand
        except (OSError, ValueError):
            continue
    return None


def _serve_media(handler, f):
    import mimetypes
    size = f.stat().st_size
    ctype = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
    start, end = 0, size - 1
    rng = handler.headers.get("Range") or ""
    status = 200
    if rng.startswith("bytes="):
        try:
            a, _, b = rng[6:].partition("-")
            if a:
                start = int(a)
                end = int(b) if b else size - 1
            else:
                start = max(0, size - int(b or 0))
            if start < 0 or start >= size or end < start:
                handler.send_response(416)
                handler.send_header("Content-Range", "bytes */%d" % size)
                handler.end_headers()
                return
            end = min(end, size - 1)
            status = 206
        except (ValueError, TypeError):
            start, end = 0, size - 1
    length = end - start + 1
    handler.send_response(status)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(length))
    handler.send_header("Accept-Ranges", "bytes")
    if status == 206:
        handler.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    try:
        with open(f, "rb") as fh:
            fh.seek(start)
            left = length
            while left > 0:
                chunk = fh.read(min(65536, left))
                if not chunk:
                    break
                handler.wfile.write(chunk)
                left -= len(chunk)
    except (BrokenPipeError, ConnectionResetError):
        pass


def _stream_rows(limit=300):
    rows = []
    try:
        f = REPO / "state" / "orchestration-ledger.jsonl"
        if f.is_file():
            for ln in f.read_text(encoding="utf-8", errors="replace").splitlines()[-int(limit):]:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rows.append(json.loads(ln))
                except Exception:  # noqa: BLE001
                    rows.append({"kind": "system", "detail": "bad json row"})
        f2 = REPO / "state" / "audit.jsonl"
        if f2.is_file():
            for ln in f2.read_text(encoding="utf-8", errors="replace").splitlines()[-int(limit):]:
                try:
                    rows.append(json.loads(ln))
                except Exception:  # noqa: BLE001
                    pass
    except Exception:  # noqa: BLE001
        pass
    return rows


def _context_candidates():
    """真实候选：焦点栈 + memory_bank 印章 + 最近编排账（只读）。"""
    out = []
    try:
        from gbt_allinone.tools import focus_stack as _FS
        for it in _FS._BOARD.snapshot().get("items") or []:
            out.append({"id": "focus:" + it["id"], "source": "focus",
                        "text": (it.get("title") or "") + ((" · " + it["target"]) if it.get("target") else ""),
                        "at": it.get("at"), "priority": 0.95})
    except Exception:  # noqa: BLE001
        pass
    try:
        import json as _json
        f = REPO / "state" / "memory_bank.jsonl"
        if f.is_file():
            rows = f.read_text(encoding="utf-8", errors="replace").splitlines()[-50:]
            for ln in rows:
                try:
                    r = _json.loads(ln)
                except Exception:  # noqa: BLE001
                    continue
                if not isinstance(r, dict):
                    continue
                ref = str(r.get("ref") or r.get("path") or "")
                text = str(r.get("why") or r.get("summary") or ref or "")
                if text:
                    out.append({"id": "mem:" + (ref or str(len(out))), "source": "memory_bank",
                                "text": text, "at": r.get("at"), "priority": 0.8})
    except Exception:  # noqa: BLE001
        pass
    try:
        import json as _json
        f = REPO / "state" / "orchestration-ledger.jsonl"
        if f.is_file():
            rows = f.read_text(encoding="utf-8", errors="replace").splitlines()[-30:]
            for ln in rows:
                try:
                    r = _json.loads(ln)
                except Exception:  # noqa: BLE001
                    continue
                if not isinstance(r, dict):
                    continue
                text = str(r.get("action") or r.get("kind") or r.get("summary") or "")
                if text:
                    out.append({"id": "ledger:" + str(len(out)), "source": "tool_result",
                                "text": text[:500], "at": r.get("at") or r.get("ts"),
                                "priority": 0.7})
    except Exception:  # noqa: BLE001
        pass
    return out[:200]


def _body_control_status_or_none():
    pass


def _asr_local(seconds=5.0, culture="zh-CN", wav=None, device=None):
    from gbt_allinone import voice_cap as VC
    r = VC.asr_local(seconds=float(seconds), culture=str(culture or "zh-CN"),
                     min_confidence=0.0, wav=wav, device=device)
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
    else:
        msgs.insert(0, {"role": "system", "content": GBT_PERSONA})
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


def _chat(text: str, context: str = CONTEXT_NAME, use_capabilities: bool = True,
          image=None, image_name: str = "", file=None, file_name: str = "",
          file_type: str = "") -> dict:
    """无限上下文 + 稳定输出：temperature=0，context 走 ring_context。

    2026-11-02 主人令：先过 `capability_router` ——「看屏幕 / 开网页 / 读写文件 / 看图」四类
    命中就**自动调用万能插**真执行（回执里带 call=omni_plug + capability），
    四类之外（或只是提问）照旧走对话模型，行为与接进前一致。
    开关：body 里 `capability:false` 或环境变量 `GBT_CAPABILITY_ROUTER=0`。
    """
    t0 = time.time()
    # 2026-11-02：聊天 + 附图 —— 先做本地视觉读数（零出网/零写盘），再决定回读数还是带图上下文对话
    _img = None
    _visual_note = ""
    _ci = None
    if image:
        try:
            from gbt_allinone import chat_image as _ci
            _img = _ci.analyze(image)
        except Exception as _cie:  # noqa: BLE001
            _img = {"ok": False, "error": "%s: %s" % (type(_cie).__name__, str(_cie)[:160])}
    if _img is not None:
        _ask = bool(_ci is not None and _ci.looks_image_question(str(text or "")))
        if not str(text or "").strip() or _ask:
            return {"ok": bool(_img.get("ok")),
                    "text": (_img.get("brief") if _img.get("ok")
                             else "附图读取失败：" + str(_img.get("error"))[:160]),
                    "via": "vision:local", "capability": _img,
                    "elapsed_ms": int((time.time() - t0) * 1000),
                    "context": {"mode": "local-vision", "name": context}}
        _visual_note = "（用户附了一张图，本地视觉读数：%s）\n" % (
            _img.get("brief") if _img.get("ok") else "读取失败：" + str(_img.get("error"))[:120])
    # 2026-11-02：聊天「发送文件」—— 文本/代码读前 N 字，图片转视觉读数，二进制只报元数据（不假装解析）
    _file = None
    _file_note = ""
    _cf = None
    if file:
        try:
            from gbt_allinone import chat_file as _cf
            _file = _cf.analyze(file_name or "附件", file, file_type)
        except Exception as _fe:  # noqa: BLE001
            _file = {"ok": False, "error": "%s: %s" % (type(_fe).__name__, str(_fe)[:160])}
    if _file is not None:
        _fask = bool(_cf is not None and _cf.looks_file_question(str(text or "")))
        if not str(text or "").strip() or _fask:
            _brief = (_file.get("brief") if _file.get("ok")
                      else "附件读取失败：" + str(_file.get("error"))[:160])
            if _file.get("kind") == "text" and _file.get("preview"):
                _brief = _brief + "\n\n--- 文件前 %d 字 ---\n%s" % (
                    min(len(_file["preview"]), 3000), _file["preview"][:3000])
            return {"ok": bool(_file.get("ok")), "text": _brief,
                    "via": "file:" + str(_file.get("kind") or "file"),
                    "capability": _file,
                    "elapsed_ms": int((time.time() - t0) * 1000),
                    "context": {"mode": "local-file", "name": context}}
        _file_note = "（用户附了一个文件，本地读数：%s）\n" % (_file.get("brief") or "读取失败")
    if use_capabilities and _img is None and _file is None and os.environ.get("GBT_CAPABILITY_ROUTER", "1") != "0":
        try:
            from gbt_allinone import capability_router as _CR
            cap = _CR.run(text, context=context)
            if cap.get("handled"):
                cap.setdefault("context", {"mode": "capability-router", "name": context})
                cap["elapsed_ms"] = int((time.time() - t0) * 1000)
                return cap
        except Exception as _cap_err:  # noqa: BLE001
            # 路由自己坏了绝不许挡正常对话：降级走模型，但**必须在 stderr 留痕**（不许静默）。
            try:
                print("[capability_router] 降级：%s: %s" % (type(_cap_err).__name__,
                                                          str(_cap_err)[:200]), file=sys.stderr)
            except Exception:  # noqa: BLE001
                pass
    m = _settings_load().get("model") or {}
    prompt_text = GBT_PERSONA + "\n\n" + _visual_note + _file_note + "用户说：" + str(text) + "\n\n（请始终以小土豆的身份回答，不要自称其他模型。）"
    # 2026-11-02 主人令：Agnes 只做“反向调用云端算力”，不是聊天模型；
    # 聊天永远先用我们自己的本机权重。除非显式 GBT_ALLOW_EXTERNAL_MODEL=1，否则不允许外部模型接聊天。
    if m.get("base_url") and m.get("name") and os.environ.get("GBT_ALLOW_EXTERNAL_MODEL") == "1":
        r = _openai_chat(prompt_text, m)
        r.setdefault("context", {"mode": "user-model", "name": context})
        r["elapsed_ms"] = int((time.time() - t0) * 1000)
        return r
    try:
        from gbt_allinone import omni_plug as _OP
        _or = _OP.plug_and_run("engine", kind="ai", args={"prompt": prompt_text, "max_tokens": 512}, timeout=300)
        if _or.get("ok") and _or.get("text"):
            return {"ok": True, "text": _or.get("text"), "via": "omni_plug:ai:engine",
                    "ms": int((time.time() - t0) * 1000), "context": {"mode": "omni-ai-engine", "name": context}}
    except Exception:  # noqa: BLE001
        pass
    from gbt_allinone import energy_core as E
    r = E.think([{"role": "system", "content": GBT_PERSONA},
                 {"role": "user", "content": prompt_text}], temperature=0.0,
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


def _omni_impact(target: str = "", n: int = 8) -> dict:
    """多域监控 · 改动影响面：「我这一刀，顺着关系会撞到谁」。

    主人令 2026-11-04 更正口径：本面板**不是**在监控别的页面、别的能力位活着没活着
    —— 那件事归 heartbeat / 服务巡检。这里只回答一个问题：
    **改了这一处，哪些部位必须一起验。**

    判据全部来自 wiring 图（5601 节点 / 65814 有向边），且写侧留痕由
    omni_plug._sync_impact() 在每次真执行时**同步**追加，不经后台补写：

      · 1 跳 = 直接引用它 / 被它引用的部位（改名字、改签名，这些立刻断）
      · 2 跳 = 外圈间接依赖（回归时扫一遍）
      · 不在图里 = 新文件或不在扫描范围，撞不到别处（**如实说，不当成"安全"**）
    """
    import re as _re
    from gbt_allinone.tools import impact_check as IC

    st, err = IC._load()
    if st is None:
        return {"ok": False, "error": "关系图不可用：%s" % err,
                "how": "按顺序重建：repo-pack.py scan → refs → wiring-build.py"}
    adj = st["adj"]
    meta = st.get("meta") or {}
    n = max(3, min(int(n or 8), 20))

    def _split(node):
        kind, sep, path = str(node or "").partition(":")
        if not sep:
            return "cap", str(node or "")
        return kind, path

    def _human(node):
        kind, path = _split(node)
        return {"node": node, "kind": kind, "path": path,
                "label": path.rsplit("/", 1)[-1] or path}

    def _abs(t):
        """留痕里的相对路径要拼回仓根，否则永远对不上图节点（会假报 0 处）。"""
        t = str(t or "").strip()
        if not t:
            return ""
        if _re.match(r"^[A-Za-z]:[\\/]", t) or t.startswith("/"):
            return t
        return str(REPO / t)

    def _reach(node, depth):
        return len(IC.impact(adj, node, depth)) if node in adj else 0

    graph = {"parts": len(adj),
             "links": int(meta.get("edges_directed") or 0),
             "core_share": float(meta.get("largest_share") or 0),
             "islands": int(meta.get("components") or 0),
             "built_at": str(meta.get("at") or "")}

    # ① 现场算一个目标（改之前先查一圈）
    probe = None
    if str(target or "").strip():
        node = IC._to_node(_abs(target))
        in_g = node in adj
        probe = dict(_human(node), input=str(target).strip(), in_graph=in_g,
                     reach1=_reach(node, 1), reach2=_reach(node, 2),
                     sample=[_human(x)["path"] for x in sorted(IC.impact(adj, node, 1))[:24]]
                     if in_g else [])

    # ② 排行：最不能随便动的文件（按 1 跳强依赖数）
    rk = IC.run_op("risky", n=n * 3)
    ranking = []
    for row in (rk.get("top") or []):
        h = _human(row.get("node") or "")
        if h["kind"] != "code":
            continue
        ranking.append({"path": h["path"], "label": h["label"],
                        "reach": int(row.get("strong") or 0),
                        "total": int(row.get("total") or 0),
                        "files": int(row.get("files") or 0),
                        "caps": int(row.get("caps") or 0)})
        if len(ranking) >= n:
            break

    # ③ 时间线：万能插每真执行一刀就有一条（写侧同步落盘，这里只读）
    recent = []
    lp = REPO / "state" / "omni-impact.jsonl"
    rows = []
    if lp.is_file():
        for ln in lp.read_text(encoding="utf-8", errors="replace").splitlines()[-60:]:
            ln = ln.strip()
            if not ln.startswith("{"):
                continue
            try:
                rows.append(json.loads(ln))
            except Exception:  # noqa: BLE001
                continue
    for r in rows[-12:][::-1]:
        node = IC._to_node(_abs(r.get("target")))
        recent.append({"ts": r.get("ts"), "action": r.get("action"),
                       "target": str(r.get("target") or ""), "node": node,
                       "in_graph": node in adj, "ok": bool(r.get("ok")),
                       "reach1": _reach(node, 1), "reach2": _reach(node, 2)})

    # ④ 一句话结论（给不看图的人）
    #   分级按**占比**而不是绝对数：图一共 5601 个部位，658 处是 11.7%（牵连面不小），
    #   4877 处才是 87%（核心区）。只看绝对数会把前者也说成"核心"，结论就不值钱了。
    _parts = max(1, graph["parts"])

    def _say(in_g, r1, r2):
        share = (r2 / _parts * 100.0) if _parts else 0.0
        if not in_g:
            return {"level": "grey", "head": "这一处不在关系图里",
                    "body": "新文件，或不在扫描范围内。改动不会顺着仓库关系撞到别处。"}
        if share >= 25:
            return {"level": "red", "head": "核心区：一改会碰到 %d 处（%.0f%%）" % (r2, share),
                    "body": "先看 1 跳那 %d 处 —— 改了它，这些是最先断的。" % r1}
        if share >= 3:
            return {"level": "amber", "head": "会牵连 %d 处（%.1f%%）" % (r2, share),
                    "body": "1 跳 %d 处必须一起验，外圈跑冒烟即可。" % r1}
        if r2 == 0:
            return {"level": "green", "head": "图上没连到别处",
                    "body": "单独改、单独验就行。"}
        return {"level": "green", "head": "只碰到 %d 处（%.1f%%）" % (r2, share),
                "body": "1 跳 %d 处，范围很小。" % r1}

    verdict = None
    if probe:
        verdict = _say(probe["in_graph"], probe["reach1"], probe["reach2"])
    elif recent:
        worst = max(recent, key=lambda x: x["reach2"])
        verdict = _say(worst["in_graph"], worst["reach1"], worst["reach2"])
        verdict["head"] = "最近一次改动 · " + verdict["head"]
        verdict["body"] = "（%s）%s" % (worst["target"], verdict["body"])

    return {"ok": True, "graph": graph, "probe": probe, "ranking": ranking,
            "recent": recent, "verdict": verdict,
            "note": "1 跳=直接依赖，改了最先断；2 跳=外圈；"
                    "「波及 0 处」只说明它不在仓库关系图里，不等于安全"}


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
                if str(op).lower() == "impact":
                    tgt = (q.get("target") or [""])[0]
                    nn = (q.get("n") or ["8"])[0]
                    try:
                        nn = int(nn)
                    except Exception:  # noqa: BLE001
                        nn = 8
                    return self._json(_omni_impact(tgt, nn))
                if str(op).lower() == "fullopen":
                    return self._json(_omni_fullopen())
                return self._json(_omni_read(op))
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/tianzhen":
            try:
                from gbt_allinone.tools import comfy_native as CN
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                op = (q.get("op") or ["status"])[0]
                allowed = ("status", "nodes", "coverage", "harvest", "contract", "gate", "runs")
                if op not in allowed:
                    return self._json({"ok": False, "op": op,
                                       "error": "user_error: /api/tianzhen 只读；允许 %s" % (allowed,)}, 400)
                return self._json(CN.run({"op": op}))
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
        if path == "/api/stream":
            # 2026-11-02：思考流/行动流（真实读 orchestration-ledger/audit，只读归一化）
            try:
                from gbt_allinone import api as _api
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                limit = int((qs.get("limit") or ["80"])[0] or 80)
                kinds = qs.get("kinds")
                rows = _stream_rows(300)
                env = _api.run_task("thought_stream", {"op": "normalize", "rows": rows,
                                                       "limit": limit, "kinds": kinds}, safe=True)
                res = ((env.get("gbt_result") or {}).get("result")
                       if isinstance(env, dict) else None) or {}
                return self._json(res)
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/context":
            # 2026-11-02：上下文注入预览（focus + memory_bank + 最近编排账；纯确定性选择）
            try:
                from gbt_allinone import api as _api
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                query = str((qs.get("query") or [""])[0])
                try:
                    budget = int((qs.get("budget") or ["3000"])[0])
                except Exception:  # noqa: BLE001
                    budget = 3000
                cands = _context_candidates()
                env = _api.run_task("context_inject", {"op": "select", "query": query,
                                                       "candidates": cands,
                                                       "budget": budget}, safe=True)
                sel = ((env.get("gbt_result") or {}).get("result")
                       if isinstance(env, dict) else None) or {}
                return self._json({"ok": bool(sel.get("ok")), "selection": sel,
                                   "candidates": len(cands),
                                   "sources": ["focus", "memory_bank", "orchestration-ledger"]})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)

        if path == "/api/kws":
            # 2026-11-03：声学 KWS 状态（本机 sherpa-onnx）
            try:
                from gbt_allinone import api as _api
                env = _api.run_task("kws", {"op": "status"}, safe=True)
                res = ((env.get("gbt_result") or {}).get("result")
                       if isinstance(env, dict) else None) or {}
                return self._json(res)
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)

        if path == "/api/update-chain":
            # 2026-11-03：本地更新测试链状态（不下载/不碰正式 APP）
            try:
                from gbt_allinone import api as _api
                env = _api.run_task("update_chain", {"op": "status"}, safe=True)
                st = ((env.get("gbt_result") or {}).get("result")
                      if isinstance(env, dict) else None) or {}
                return self._json(st)
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/update":
            # 2026-11-03：更新校验状态（不下载/不安装）
            try:
                from gbt_allinone import api as _api
                env = _api.run_task("update_verify", {"op": "schema"}, safe=True)
                sch = ((env.get("gbt_result") or {}).get("result")
                       if isinstance(env, dict) else None) or {}
                return self._json({"ok": True, "install_supported": False, "download": False,
                                   "public_key_configured": False, "schema": sch,
                                   "note": "只做离线清单/签名校验；安装器/发布通道未接"})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/lan":
            # 2026-11-03：局域网配对监听状态（不自动启动；start 走 POST）
            try:
                from gbt_allinone import api as _api
                env = _api.run_task("lan_pairing", {"op": "status"}, safe=True)
                st = ((env.get("gbt_result") or {}).get("result")
                      if isinstance(env, dict) else None) or {}
                env2 = _api.run_task("lan_pairing", {"op": "schema"}, safe=True)
                sch = ((env2.get("gbt_result") or {}).get("result")
                       if isinstance(env2, dict) else None) or {}
                env3 = _api.run_task("lan_pairing", {"op": "cert"}, safe=True)
                cert = ((env3.get("gbt_result") or {}).get("result")
                        if isinstance(env3, dict) else None) or {}
                return self._json({"ok": bool(st.get("ok")), "status": st, "schema": sch,
                                   "cert": {k: v for k, v in cert.items() if k != "key"}})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/pairing":
            # 2026-11-03：配对/证书安全原语（只读状态；不开端口/不生成证书）
            try:
                from gbt_allinone import api as _api
                env = _api.run_task("pairing", {"op": "devices"}, safe=True)
                dev = ((env.get("gbt_result") or {}).get("result")
                       if isinstance(env, dict) else None) or {}
                env2 = _api.run_task("pairing", {"op": "schema"}, safe=True)
                sch = ((env2.get("gbt_result") or {}).get("result")
                       if isinstance(env2, dict) else None) or {}
                return self._json({"ok": bool(dev.get("ok")), "devices": dev.get("devices") or [],
                                   "count": dev.get("count") or 0, "active": dev.get("active") or 0,
                                   "max": dev.get("max") or 32, "schema": sch})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)

        if path == "/api/turns":
            # 2026-11-03：轮次追踪（真实读编排账/action_gate，只读归并）
            try:
                from gbt_allinone import api as _api
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                try:
                    gap = int((qs.get("gap") or ["45"])[0])
                except Exception:  # noqa: BLE001
                    gap = 45
                try:
                    limit = int((qs.get("limit") or ["50"])[0])
                except Exception:  # noqa: BLE001
                    limit = 50
                rows = _turn_rows(500)
                env = _api.run_task("turn_trace", {"op": "normalize", "rows": rows,
                                                    "gap_s": gap, "limit": limit}, safe=True)
                res = ((env.get("gbt_result") or {}).get("result")
                       if isinstance(env, dict) else None) or {}
                return self._json(res)
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/ref3d":
            # 2026-11-03：ref-to-3d 技能状态
            try:
                from gbt_allinone import api as _api
                env = _api.run_task("ref3d", {"op": "status"}, safe=True)
                return self._json(((env.get("gbt_result") or {}).get("result")
                                   if isinstance(env, dict) else None) or {})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/video":
            # 2026-11-03：视频能力融合编目（只读）
            try:
                from gbt_allinone import api as _api
                env = _api.run_task("video_hub", {"op": "catalog"}, safe=True)
                return self._json(((env.get("gbt_result") or {}).get("result")
                                   if isinstance(env, dict) else None) or {})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/media":
            # 2026-11-03：媒体舞台索引（只聚合既有产物；不读内容/不转码）
            try:
                from gbt_allinone import api as _api
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                kind = str((qs.get("kind") or [""])[0])
                try:
                    limit = int((qs.get("limit") or ["120"])[0])
                except Exception:  # noqa: BLE001
                    limit = 120
                rows = _media_scan(500)
                env = _api.run_task("media_library", {"op": "build", "items": rows,
                                                       "kind": kind, "limit": limit}, safe=True)
                idx = ((env.get("gbt_result") or {}).get("result")
                       if isinstance(env, dict) else None) or {}
                env2 = _api.run_task("media_library", {"op": "history", "items": rows,
                                                        "limit": 20}, safe=True)
                hist = ((env2.get("gbt_result") or {}).get("result")
                        if isinstance(env2, dict) else None) or {}
                if isinstance(idx, dict):
                    idx["history"] = hist.get("entries") or []
                    idx["roots"] = [r.name for r in MEDIA_ROOTS if r.is_dir()]
                return self._json(idx)
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/media/file":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            f = _media_resolve((q.get("path") or [""])[0])
            if not f:
                return self._json({"ok": False, "error": "not found / not allowed"}, 404)
            return _serve_media(self, f)
        if path == "/api/resources":
            # 2026-11-03：本机资源快照（只读；不写盘/不起进程）
            try:
                from gbt_allinone import api as _api
                env = _api.run_task("resource_snapshot", {"op": "snapshot"}, safe=True)
                res = ((env.get("gbt_result") or {}).get("result")
                       if isinstance(env, dict) else None) or {}
                return self._json(res)
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/reminders":
            # 2026-11-02：提醒（读面免门；写面在能力 handler 过 filesystem_write）
            try:
                from gbt_allinone import api as _api
                env = _api.run_task("reminder", {"op": "list"}, safe=True)
                lst = ((env.get("gbt_result") or {}).get("result")
                       if isinstance(env, dict) else None) or {}
                env2 = _api.run_task("reminder", {"op": "due"}, safe=True)
                due = ((env2.get("gbt_result") or {}).get("result")
                       if isinstance(env2, dict) else None) or {}
                return self._json({"ok": bool(lst.get("ok")), "reminders": lst.get("reminders") or [],
                                   "count": lst.get("count") or 0,
                                   "pending": lst.get("pending") or 0,
                                   "due": due.get("due") or [], "due_count": due.get("count") or 0})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/slots":
            # 2026-11-02：动态 API 槽（只读定义；执行器未接，call 永远 not_supported）
            try:
                from gbt_allinone import api as _api
                snap = _api_slots_snapshot()
                env = _api.run_task("api_slot", {"op": "schema"}, safe=True)
                schema = ((env.get("gbt_result") or {}).get("result")
                          if isinstance(env, dict) else None) or {}
                return self._json({"ok": bool(snap.get("ok")), "slots": snap.get("slots") or [],
                                   "count": snap.get("count") or 0,
                                   "executor": snap.get("executor") or "not_wired",
                                   "schema": schema})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/body":
            # 2026-11-02：body_control 状态口（真实读 state/body_control.json；默认未接线）
            try:
                from gbt_allinone import api as _api
                bindings = None
                bf = REPO / "state" / "body_control.json"
                if bf.is_file():
                    try:
                        bindings = json.loads(bf.read_text(encoding="utf-8"))
                    except Exception:  # noqa: BLE001
                        bindings = None
                env = _api.run_task("body_control", {"op": "status", "bindings": bindings}, safe=True)
                res = ((env.get("gbt_result") or {}).get("result")
                       if isinstance(env, dict) else None) or {}
                return self._json(res)
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/focus":
            # 2026-11-02：焦点栈 + 记忆审计（真实读 state/memory_bank.jsonl，只读体检）
            try:
                from gbt_allinone import api as _api
                recs = _memory_audit_records()
                env = _api.run_task("focus_stack", {"op": "audit", "records": recs}, safe=True)
                audit = ((env.get("gbt_result") or {}).get("result")
                         if isinstance(env, dict) else None) or {}
                env2 = _api.run_task("focus_stack", {"op": "snapshot"}, safe=True)
                focus = ((env2.get("gbt_result") or {}).get("result")
                         if isinstance(env2, dict) else None) or {}
                return self._json({"ok": True, "focus": focus, "audit": audit,
                                   "audit_source": "state/memory_bank.jsonl",
                                   "audit_rows": len(recs)})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/voice/settings":
            try:
                from gbt_allinone.tools import voice_settings as _VS
                s = _voice_settings()
                return self._json({"ok": True, "settings": s, "schema": _VS.schema()})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/ui/cards":
            # 2026-11-02：ACUI 卡片只看板；真实写操作走统一门 ui_card
            try:
                from gbt_allinone import api as _api
                env = _api.run_task("ui_card", {"op": "snapshot"}, safe=True)
                res = ((env.get("gbt_result") or {}).get("result")
                       if isinstance(env, dict) else None) or {}
                return self._json(res)
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
        if path == "/api/voice/audio":
            # 2026-11-02：对讲 TTS 回放（只读 outputs/voice-intercom 下的 wav）
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            name = str((q.get("name") or [""])[0])
            safe = "".join(ch for ch in name if ch.isalnum() or ch in "._-")
            if not safe or safe != name or ".." in safe or not (
                    safe.lower().endswith(".wav") or safe.lower().endswith(".mp3")):
                return self._send(404, b"not found", "text/plain; charset=utf-8")
            f = (REPO / "outputs" / "voice-intercom" / safe)
            if not f.is_file():
                return self._send(404, b"not found", "text/plain; charset=utf-8")
            ctype = "audio/mpeg" if safe.lower().endswith(".mp3") else "audio/wav"
            return self._send(200, f.read_bytes(), ctype)
        if path == "/api/moments":
            try:
                from gbt_allinone import moments_hub as MH
                from gbt_allinone import moments_accounts as MA
                acc = MA.resolve(self.headers.get("X-Moments-Account"))
                if not acc:
                    return self._json(MA.auth_state())
                MH.STATE = MA.data_path(acc["id"])
                d = MH.state()
                d["current"] = MA.public(acc)
                d["needs_auth"] = False
                return self._json(d)
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/proactive":
            try:
                from gbt_allinone import proactive as _PA
                from urllib.parse import parse_qs as _pq
                q = _pq(urllib.parse.urlparse(self.path).query)
                op = (q.get("op") or ["status"])[0]
                if str(op) == "tickets":
                    return self._json(_PA.status())
                return self._json(_PA.status())
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
        if path in ("/api/team-mirror", "/team-mirror", "/team-mirror.html"):
            base = REPO if REPO.is_dir() else __import__("pathlib").Path(__file__).resolve().parents[1]
            jp = base / "state" / "team-mirror.json"
            hp = base / "交付成片" / "团队镜像" / "team-mirror.html"
            if path in ("/team-mirror", "/team-mirror.html"):
                if hp.is_file():
                    return self._send(200, hp.read_bytes(), "text/html; charset=utf-8")
                return self._send(404, b"team-mirror.html not found", "text/plain; charset=utf-8")
            if jp.is_file():
                return self._json({"ok": True, "data": json.loads(jp.read_text(encoding="utf-8")),
                                   "source": str(jp), "ts": time.time()})
            return self._json({"ok": False, "error": "team-mirror.json missing"}, 404)
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
        if path == "/api/tianzhen":
            try:
                from gbt_allinone.tools import comfy_native as CN
                op = str(body.get("op") or "status")
                if op not in ("run", "validate", "gate", "import", "import_dir", "t2i_sdturbo", "t2i_fused", "i2v_svd"):
                    return self._json({"ok": False, "op": op,
                                       "error": "user_error: /api/tianzhen POST 只允许 run/validate/gate/import/t2i_sdturbo/t2i_fused/i2v_svd"}, 400)
                if op in ("t2i_sdturbo", "t2i_fused", "i2v_svd"):
                    from gbt_allinone.native_t2i_bridge import run as native_t2i
                    return self._json(native_t2i(body))
                return self._json(CN.run(dict(body)))
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
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
            # 2026-11-02：数字人页面用 getUserMedia 录好 16k WAV（wav_b64）上传，
            # 这里必须识别上传音频；旧实现忽略上传、改录服务器默认麦 ⇒ 数字人听不到主人说话。
            tmp = None
            try:
                raw_b64 = body.get("wav_b64") or body.get("wav") or ""
                wav_path = None
                if isinstance(raw_b64, str) and raw_b64.strip():
                    import base64 as _b64
                    import tempfile as _tf
                    raw = _b64.b64decode(raw_b64.split(",", 1)[-1])
                    if len(raw) > 12 * 1024 * 1024:
                        return self._json({"ok": False,
                                           "error": "user_error: 上传音频 >12MB"}, 413)
                    if len(raw) < 44:
                        return self._json({"ok": False,
                                           "error": "user_error: 上传音频太短/不是 WAV"}, 400)
                    tmp = _tf.NamedTemporaryFile(prefix="gbt-asr-", suffix=".wav",
                                                 delete=False)
                    tmp.write(raw)
                    tmp.close()
                    wav_path = tmp.name
                if wav_path:
                    # 2026-11-02：按语音设置选后端（auto=Whisper 优先 / whisper=只 Whisper / windows=只系统）
                    _vset = _voice_settings()
                    _backend = str(_vset.get("asr_backend") or "auto")
                    _aw_err = None
                    if _backend != "windows":
                        try:
                            from gbt_allinone.tools import asr_whisper as _AW
                            _av = _AW.available()
                            if _av.get("ok"):
                                _wr = _AW.transcribe(wav_path)
                                if _wr.get("ok"):
                                    _wr["via"] = "whisper:" + _backend
                                    _wr["settings_backend"] = _backend
                                    return self._json(_wr)
                                _aw_err = _wr.get("error") or _wr.get("status")
                            else:
                                _aw_err = _av.get("reason")
                        except Exception as _we:  # noqa: BLE001
                            _aw_err = "%s: %s" % (type(_we).__name__, str(_we)[:120])
                    if _backend == "whisper":
                        return self._json({"ok": False, "status": "error",
                                           "backend": "faster-whisper:base",
                                           "error": _aw_err or "Whisper 不可用",
                                           "hint": "设置里 ASR=whisper（只 Whisper）；要回退请改成 auto/windows"})
                return self._json(_asr_local(body.get("seconds") or 5,
                                             body.get("culture") or "zh-CN",
                                             wav=wav_path, device=body.get("device")))
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
            finally:
                if tmp is not None:
                    try:
                        os.unlink(tmp.name)
                    except Exception:  # noqa: BLE001
                        pass
        if path == "/api/moments":
            try:
                from gbt_allinone import moments_hub as MH
                from gbt_allinone import moments_accounts as MA
                op0 = str(body.get("op") or "post").lower()
                if op0 in ("register", "login", "logout", "accounts"):
                    return self._json(MA.handle(op0, body))
                acc = MA.resolve(self.headers.get("X-Moments-Account"))
                if not acc:
                    return self._json(MA.auth_state())
                MH.STATE = MA.data_path(acc["id"])
                d = MH.op(body)
                d["current"] = MA.public(acc)
                d["needs_auth"] = False
                return self._json(d)
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/proactive":
            try:
                from gbt_allinone import proactive as _PA
                op = str(body.get("op") or "status").lower()
                if op == "start":
                    return self._json(_PA.start())
                if op == "stop":
                    return self._json(_PA.stop())
                if op == "submit":
                    return self._json(_PA.submit(body))
                if op == "blueprint":
                    return self._json(_PA.submit_blueprint(int(body.get("limit") or 5)))
                if op == "tickets":
                    return self._json(_PA.status())
                return self._json(_PA.status())
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
        if path == "/api/world":
            # 2026-11-02 P1：世界锻造只读数据面（spec/gen/step/view3d/summary；纯函数不落盘）
            try:
                from gbt_allinone.tools import world_forge as _WF
                op = str(body.get("op") or "view3d")
                p = {k: v for k, v in body.items() if k != "op"}
                return self._json(_WF.run(op, **p))
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/stream":
            # 2026-11-02：思考流（可传 rows 做归一化/过滤）
            try:
                from gbt_allinone import api as _api
                rows = body.get("rows")
                if not isinstance(rows, list):
                    rows = _stream_rows(300)
                env = _api.run_task("thought_stream", {
                    "op": "normalize", "rows": rows,
                    "limit": body.get("limit") or 80,
                    "kinds": body.get("kinds")}, safe=True)
                return self._json(((env.get("gbt_result") or {}).get("result")
                                   if isinstance(env, dict) else None) or {})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/context":
            # 2026-11-02：上下文注入（预览/选择）；纯选择，不调模型
            try:
                from gbt_allinone import api as _api
                op = str(body.get("op") or "select").lower()
                if op == "select":
                    cands = body.get("candidates")
                    if not isinstance(cands, list):
                        cands = _context_candidates()
                    env = _api.run_task("context_inject", {
                        "op": "select", "query": body.get("query") or "",
                        "candidates": cands,
                        "budget": body.get("budget") or 3000}, safe=True)
                    res = ((env.get("gbt_result") or {}).get("result")
                           if isinstance(env, dict) else None) or {}
                    return self._json(res)
                env = _api.run_task("context_inject", {"op": "schema"}, safe=True)
                return self._json(((env.get("gbt_result") or {}).get("result")
                                   if isinstance(env, dict) else None) or {})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)

        if path == "/api/kws":
            # 2026-11-03：KWS 检测（PCM base64）或状态；只本机
            try:
                from gbt_allinone import api as _api
                op = str(body.get("op") or "status").lower()
                if op == "detect":
                    import base64 as _b64
                    pcm = _b64.b64decode(str(body.get("pcm_base64") or ""), validate=False)
                    env = _api.run_task("kws", {"op": "detect", "pcm": pcm,
                                                "rate": int(body.get("rate") or 16000)}, safe=True)
                else:
                    env = _api.run_task("kws", {"op": "status"}, safe=True)
                return self._json(((env.get("gbt_result") or {}).get("result")
                                   if isinstance(env, dict) else None) or {})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/voice/stream":
            # 2026-11-03：流式语音（PCM 分片；局部/最终 Whisper）
            try:
                from gbt_allinone import api as _api
                import tempfile as _tempfile
                from gbt_allinone.tools import voice_stream as _VS
                from gbt_allinone.tools import asr_whisper as _AW
                op = str(body.get("op") or "start").lower()
                if op == "start":
                    env = _api.run_task("voice_stream", {"op": "start",
                                                         "session": body.get("session")}, safe=True)
                    return self._json(((env.get("gbt_result") or {}).get("result")
                                       if isinstance(env, dict) else None) or {})
                if op in ("chunk", "end", "reset"):
                    sid = body.get("session") or ""
                    if op == "chunk":
                        env = _api.run_task("voice_stream", {"op": "chunk", "session": sid,
                                                             "pcm_base64": body.get("pcm_base64")}, safe=True)
                        res = ((env.get("gbt_result") or {}).get("result")
                               if isinstance(env, dict) else None) or {}
                        if res.get("ok") and body.get("partial") and float(res.get("duration") or 0) >= _VS.PARTIAL_MIN_S:
                            try:
                                with _tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                                    path = tf.name
                                _VS.write_wav(path, _api.run_task("voice_stream", {"op": "end",
                                                                                   "session": sid}, safe=True)
                                              .get("gbt_result", {}).get("result", {}).get("pcm", b"")
                                              if False else b"")
                                # 上面的分支只用于保持导入紧凑；真正局部转写在下方直接取缓冲
                                try:
                                    from gbt_allinone.tools.voice_stream import _STORE as _VS_STORE
                                    _VS.write_wav(path, _VS_STORE.get(sid))
                                    tr = _AW.transcribe(path)
                                    res["partial"] = tr.get("text") or ""
                                    res["partial_status"] = tr.get("status")
                                    res["wake"] = _VS.detect_wake(res["partial"])
                                finally:
                                    try:
                                        import os as _os
                                        _os.unlink(path)
                                    except OSError:
                                        pass
                            except Exception as _pe:  # noqa: BLE001
                                res["partial_error"] = "%s: %s" % (type(_pe).__name__, str(_pe)[:100])
                        try:
                            from gbt_allinone.tools import kws as _KWS
                            from gbt_allinone.tools.voice_stream import _STORE as _VS_STORE
                            if _KWS.available().get("ok"):
                                res["acoustic_wake"] = _KWS.detect_pcm(_VS_STORE.get(sid))
                        except Exception as _ke:  # noqa: BLE001
                            res["acoustic_wake_error"] = "%s: %s" % (type(_ke).__name__, str(_ke)[:80])
                        return self._json(res)
                    env = _api.run_task("voice_stream", {"op": op, "session": sid}, safe=True)
                    res = ((env.get("gbt_result") or {}).get("result")
                           if isinstance(env, dict) else None) or {}
                    if op == "end" and res.get("ok"):
                        pcm = res.get("pcm") or b""
                        try:
                            with _tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                                path = tf.name
                            _VS.write_wav(path, pcm)
                            tr = _AW.transcribe(path)
                            res.pop("pcm", None)
                            res["transcribe"] = tr
                            res["text"] = tr.get("text") or ""
                            res["wake"] = _VS.detect_wake(res["text"])
                            try:
                                from gbt_allinone.tools import kws as _KWS
                                if _KWS.available().get("ok"):
                                    res["acoustic_wake"] = _KWS.detect_pcm(pcm)
                            except Exception as _ke:  # noqa: BLE001
                                res["acoustic_wake_error"] = "%s: %s" % (type(_ke).__name__, str(_ke)[:80])
                        finally:
                            try:
                                import os as _os
                                _os.unlink(path)
                            except Exception:  # noqa: BLE001
                                pass
                    return self._json(res)
                return self._json({"ok": False, "error": "user_error: 未知 op"})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/video":
            # 2026-11-03：视频舱六段只读探针/单能力路由；执行仍走各自统一门
            try:
                from gbt_allinone import api as _api
                op = str(body.get("op") or "run").lower()
                if op == "dispatch":
                    env = _api.run_task("video_hub", {"op": "dispatch",
                                                       "cap": body.get("cap") or "",
                                                       "payload": body.get("payload") or {}}, safe=True)
                else:
                    env = _api.run_task("video_hub", {"op": "run"}, safe=True)
                return self._json(((env.get("gbt_result") or {}).get("result")
                                   if isinstance(env, dict) else None) or {})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/update-chain":
            # 2026-11-03：本地测试链 init/stage/confirm/rollback（只 state/updates-test）
            try:
                from gbt_allinone import api as _api
                op = str(body.get("op") or "status").lower()
                payload = {"op": op}
                if op == "confirm":
                    payload["stage_id"] = body.get("stage_id") or ""
                    payload["token"] = body.get("token") or ""
                env = _api.run_task("update_chain", payload, safe=True)
                res = ((env.get("gbt_result") or {}).get("result")
                       if isinstance(env, dict) else None) or {}
                if res.get("ok") and op in ("init", "stage", "confirm", "rollback"):
                    try:
                        d = REPO / "outputs" / "update-chain"
                        d.mkdir(parents=True, exist_ok=True)
                        safe_res = {k: v for k, v in res.items() if k not in ("confirm_token", "dev_key")}
                        with open(d / "audit.jsonl", "a", encoding="utf-8") as f:
                            f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                                "op": op, "result": safe_res},
                                               ensure_ascii=False) + "\n")
                    except Exception:  # noqa: BLE001
                        pass
                return self._json(res)
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/update":
            # 2026-11-03：离线验签；绝不下载/安装
            try:
                from gbt_allinone import api as _api
                op = str(body.get("op") or "verify").lower()
                if op == "verify":
                    env = _api.run_task("update_verify", {
                        "op": "verify", "manifest": body.get("manifest") or {},
                        "public_key": body.get("public_key") or "",
                        "current_version": body.get("current_version") or "0.0.0"}, safe=True)
                    return self._json(((env.get("gbt_result") or {}).get("result")
                                       if isinstance(env, dict) else None) or {})
                env = _api.run_task("update_verify", {"op": "schema"}, safe=True)
                return self._json(((env.get("gbt_result") or {}).get("result")
                                   if isinstance(env, dict) else None) or {})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/lan":
            # 2026-11-03：start/stop 局域网监听；默认只绑私有地址；无远程命令
            try:
                from gbt_allinone import api as _api
                op = str(body.get("op") or "status").lower()
                payload = {"op": op}
                if op == "start":
                    payload["host"] = body.get("host") or "lan"
                    payload["port"] = body.get("port") or 8767
                env = _api.run_task("lan_pairing", payload, safe=True)
                res = ((env.get("gbt_result") or {}).get("result")
                       if isinstance(env, dict) else None) or {}
                if res.get("ok") and op in ("start", "stop"):
                    try:
                        d = REPO / "outputs" / "pairing"
                        d.mkdir(parents=True, exist_ok=True)
                        with open(d / "audit.jsonl", "a", encoding="utf-8") as f:
                            f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                                "op": "lan_" + op, "result": res},
                                               ensure_ascii=False) + "\n")
                    except Exception:  # noqa: BLE001
                        pass
                return self._json(res)
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/pairing":
            # 2026-11-03：生成码/claim/撤销/证书指纹；不写 token 到审计
            try:
                from gbt_allinone import api as _api
                op = str(body.get("op") or "").lower()
                payload = {"op": op}
                if op == "claim":
                    payload["code"] = body.get("code") or ""
                    payload["name"] = body.get("name") or ""
                elif op == "revoke":
                    payload["id"] = body.get("id") or ""
                elif op in ("cert", "cert_verify"):
                    payload["pem"] = body.get("pem") or ""
                    payload["expected"] = body.get("expected") or ""
                env = _api.run_task("pairing", payload, safe=True)
                res = ((env.get("gbt_result") or {}).get("result")
                       if isinstance(env, dict) else None) or {}
                if res.get("ok") and op in ("code", "claim", "revoke"):
                    try:
                        d = REPO / "outputs" / "pairing"
                        d.mkdir(parents=True, exist_ok=True)
                        safe_res = {k: v for k, v in res.items() if k not in ("device",)}
                        with open(d / "audit.jsonl", "a", encoding="utf-8") as f:
                            f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                                "op": op, "result": safe_res},
                                               ensure_ascii=False) + "\n")
                    except Exception:  # noqa: BLE001
                        pass
                return self._json(res)
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/reminders":
            # 2026-11-02：提醒 create/cancel/complete；写面由 reminder 能力过分filesystem_write 门
            try:
                from gbt_allinone import api as _api
                op = str(body.get("op") or "create").lower()
                payload = {"op": op}
                if op == "create":
                    payload["reminder"] = body.get("reminder") or {}
                if op in ("cancel", "complete"):
                    payload["id"] = body.get("id") or ""
                env = _api.run_task("reminder", payload, safe=True)
                res = ((env.get("gbt_result") or {}).get("result")
                       if isinstance(env, dict) else None) or {}
                if res.get("ok"):
                    try:
                        d = REPO / "outputs" / "reminders"
                        d.mkdir(parents=True, exist_ok=True)
                        with open(d / "audit.jsonl", "a", encoding="utf-8") as f:
                            f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                                "op": op, "result": res},
                                               ensure_ascii=False) + "\n")
                    except Exception:  # noqa: BLE001
                        pass
                return self._json(res)
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/slots":
            # 2026-11-02：注册/删除/调用槽；call 走门但永远返回 not_supported（不发请求）
            try:
                from gbt_allinone import api as _api
                op = str(body.get("op") or "list").lower()
                if op == "register":
                    env = _api.run_task("api_slot", {"op": "register", "slot": body.get("slot")}, safe=True)
                    res = ((env.get("gbt_result") or {}).get("result")
                           if isinstance(env, dict) else None) or {}
                    if res.get("ok"):
                        _api_slots_save()
                    return self._json(res)
                if op == "remove":
                    env = _api.run_task("api_slot", {"op": "remove", "name": body.get("name")}, safe=True)
                    res = ((env.get("gbt_result") or {}).get("result")
                           if isinstance(env, dict) else None) or {}
                    if res.get("ok"):
                        _api_slots_save()
                    return self._json(res)
                if op == "call":
                    env = _api.run_task("api_slot", {"op": "call", "name": body.get("name")}, safe=True)
                    return self._json(((env.get("gbt_result") or {}).get("result")
                                       if isinstance(env, dict) else None) or {})
                return self._json(_api_slots_snapshot())
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/body":
            # 2026-11-02：body_control 只接受 status/inventory/verify/move（move 也如实拒，不执行）
            try:
                from gbt_allinone import api as _api
                op = str(body.get("op") or "status").lower()
                payload = {"op": op}
                if op == "move":
                    payload["action"] = body.get("action") or ""
                env = _api.run_task("body_control", payload, safe=True)
                return self._json(((env.get("gbt_result") or {}).get("result")
                                   if isinstance(env, dict) else None) or {})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/focus":
            # 2026-11-02：焦点栈 push/pop/clear/audit；审计由主循环调用，UI 只读列表
            try:
                from gbt_allinone import api as _api
                op = str(body.get("op") or "snapshot").lower()
                if op == "audit":
                    recs = body.get("records")
                    if not isinstance(recs, list):
                        recs = _memory_audit_records()
                    env = _api.run_task("focus_stack", {"op": "audit", "records": recs}, safe=True)
                    return self._json(((env.get("gbt_result") or {}).get("result")
                                       if isinstance(env, dict) else None) or {})
                if op in ("push", "pop", "clear"):
                    payload = {"op": op}
                    if op == "push":
                        payload["item"] = body.get("item")
                    if op == "pop" and body.get("id"):
                        payload["id"] = body.get("id")
                    env = _api.run_task("focus_stack", payload, safe=True)
                    res = ((env.get("gbt_result") or {}).get("result")
                           if isinstance(env, dict) else None) or {}
                    if res.get("ok"):
                        try:
                            d = REPO / "outputs" / "focus"
                            d.mkdir(parents=True, exist_ok=True)
                            with open(d / "audit.jsonl", "a", encoding="utf-8") as f:
                                f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                                    "op": op, "result": res},
                                                   ensure_ascii=False) + "\n")
                        except Exception:  # noqa: BLE001
                            pass
                    return self._json(res)
                env = _api.run_task("focus_stack", {"op": "snapshot"}, safe=True)
                return self._json(((env.get("gbt_result") or {}).get("result")
                                   if isinstance(env, dict) else None) or {})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/ui/cards":
            # 2026-11-02：ACUI 卡片协议（创建/关闭/动作）；动作只回事件，不执行工具
            try:
                from gbt_allinone import api as _api
                op = str(body.get("op") or "snapshot").lower()
                payload = {"op": op, "id": body.get("id"), "action": body.get("action"),
                           "payload": body.get("payload"), "card": body.get("card"),
                           "reason": body.get("reason")}
                payload = {k: v for k, v in payload.items() if v is not None}
                env = _api.run_task("ui_card", payload, safe=True)
                res = ((env.get("gbt_result") or {}).get("result")
                       if isinstance(env, dict) else None) or {}
                if res.get("ok") and op in ("create", "close", "action"):
                    try:
                        import json as _json
                        d = REPO / "outputs" / "ui-cards"
                        d.mkdir(parents=True, exist_ok=True)
                        row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "op": op,
                               "card": res.get("card") or {}, "result": res.get("event") or {}}
                        with open(d / "audit.jsonl", "a", encoding="utf-8") as f:
                            f.write(_json.dumps(row, ensure_ascii=False) + "\n")
                    except Exception:  # noqa: BLE001
                        pass
                return self._json(res)
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/voice/settings":
            # 2026-11-02：语音设置保存；校验走统一门 voice_settings，落盘在 trusted-owner 本地设置面
            try:
                from gbt_allinone import api as _api
                op = str(body.get("op") or "save").lower()
                if op == "resolve":
                    env = _api.run_task("voice_settings", {
                        "op": "resolve", "settings": body.get("settings") or {},
                        "voices": body.get("voices") or []}, safe=True)
                    res = ((env.get("gbt_result") or {}).get("result")
                           if isinstance(env, dict) else None) or {}
                    return self._json(res)
                if op == "save":
                    env = _api.run_task("voice_settings", {
                        "op": "validate", "settings": body.get("settings") or {}},
                        safe=True)
                    res = ((env.get("gbt_result") or {}).get("result")
                           if isinstance(env, dict) else None) or {}
                    if not res.get("ok"):
                        return self._json(res)
                    settings = res["settings"]
                    VOICE_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
                    tmp = VOICE_SETTINGS_PATH.with_suffix(".tmp")
                    tmp.write_text(json.dumps(settings, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
                    tmp.replace(VOICE_SETTINGS_PATH)
                    try:
                        d = REPO / "outputs" / "voice-settings"
                        d.mkdir(parents=True, exist_ok=True)
                        with open(d / "audit.jsonl", "a", encoding="utf-8") as f:
                            f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                                "settings": settings}, ensure_ascii=False) + "\n")
                    except Exception:  # noqa: BLE001
                        pass
                    return self._json({"ok": True, "settings": settings})
                return self._json({"ok": False, "error": "user_error: 未知 op %s" % op}, 400)
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/voice/intercom":
            # 2026-11-02：语音对讲（蒸馏上游参考项目语音球/唤醒/打断；真录放仍走 voice 能力位）
            try:
                from gbt_allinone import api as _api
                from gbt_allinone.tools import voice_intercom as _VI
                op = str(body.get("op") or "status").lower()

                def _inner(env):
                    return ((env.get("gbt_result") or {}).get("result")
                            if isinstance(env, dict) else None) or {}

                if op == "status":
                    legs = {}
                    try:
                        legs["voice"] = _inner(_api.run_task("voice", {"op": "status"}, safe=True))
                    except Exception as exc:  # noqa: BLE001
                        legs["voice"] = {"ok": False, "error": "%s: %s"
                                         % (type(exc).__name__, str(exc)[:160])}
                    try:
                        from gbt_allinone.tentacle import commander as _C
                        legs["brain"] = _C.alive()
                    except Exception as exc:  # noqa: BLE001
                        legs["brain"] = {"ok": False, "error": str(exc)[:160]}
                    return self._json({"ok": True, "wake_words": list(_VI.WAKE_WORDS),
                                       "states": list(_VI.STATES), "legs": legs,
                                       "verify": _VI.verify()})
                if op == "wake":
                    w = _VI.should_wake(body.get("text"))
                    return self._json({"ok": True, **w})
                if op == "listen":
                    env = _api.run_task("voice", {"op": "listen",
                                                  "seconds": float(body.get("seconds") or 5),
                                                  "culture": str(body.get("culture") or "zh-CN")},
                                        safe=True)
                    res = _inner(env)
                    out = {"ok": bool(res.get("ok")), "heard": bool(res.get("heard")),
                           "text": res.get("text") or "", "status": res.get("status"),
                           "reason": res.get("reason"), "confidence": res.get("confidence"),
                           "denied": bool(env.get("denied") if isinstance(env, dict) else False),
                           "missing_scopes": env.get("missing_scopes") if isinstance(env, dict) else None,
                           "legs": res.get("legs") or []}
                    return self._json(out)
                if op == "say":
                    speech = _VI.speakable(body.get("text"))
                    if not speech:
                        return self._json({"ok": False, "error": "user_error: 没有可朗读文字"}, 400)
                    out_dir = REPO / "outputs" / "voice-intercom"
                    out_dir.mkdir(parents=True, exist_ok=True)
                    wav = out_dir / ("tts-%s.mp3" % time.strftime("%Y%m%d-%H%M%S"))
                    env = _api.run_task("voice", {"op": "tts", "text": speech,
                                                  "out": str(wav), "play": False}, safe=True)
                    res = _inner(env)
                    backend = str(res.get("backend") or "")
                    if "sapi" in backend and wav.is_file():
                        final = wav.with_suffix(".wav")
                        try:
                            wav.replace(final)
                            wav = final
                        except Exception:  # noqa: BLE001
                            pass
                    ok = bool(res.get("ok")) and wav.is_file()
                    return self._json({"ok": ok, "text": speech,
                                       "url": ("/api/voice/audio?name=" + wav.name) if ok else "",
                                       "backend": res.get("backend"), "result": res})
                if op == "turn":
                    env = _api.run_task("voice", {"op": "listen",
                                                  "seconds": float(body.get("seconds") or 5),
                                                  "culture": str(body.get("culture") or "zh-CN")},
                                        safe=True)
                    lres = _inner(env)
                    if not (lres.get("ok") and lres.get("heard")):
                        return self._json({"ok": False, "stage": "listen",
                                           "error": lres.get("reason") or lres.get("status")
                                           or "没听到（不是坏了）",
                                           "listened": lres,
                                           "missing_scopes": env.get("missing_scopes")
                                           if isinstance(env, dict) else None})
                    w = _VI.should_wake(lres.get("text"))
                    q = w.get("query") or lres.get("text")
                    chat = _chat(q, "console-web", use_capabilities=True)
                    reply = str(chat.get("text") or "").strip()
                    speech = _VI.speakable(reply)
                    url = ""
                    say = {}
                    if speech:
                        out_dir = REPO / "outputs" / "voice-intercom"
                        out_dir.mkdir(parents=True, exist_ok=True)
                        wav = out_dir / ("tts-%s.wav" % time.strftime("%Y%m%d-%H%M%S"))
                        env2 = _api.run_task("voice", {"op": "tts", "text": speech,
                                                       "out": str(wav), "play": False}, safe=True)
                        say = _inner(env2)
                        if say.get("ok") and wav.is_file():
                            url = "/api/voice/audio?name=" + wav.name
                    return self._json({"ok": True, "transcript": lres.get("text"),
                                       "wake": w, "query": q, "reply": reply,
                                       "speech": speech, "url": url, "say": say,
                                       "chat": {"ok": chat.get("ok"), "via": chat.get("via"),
                                                "ms": chat.get("elapsed_ms")},
                                       "listen": {"status": lres.get("status"),
                                                  "confidence": lres.get("confidence"),
                                                  "legs": lres.get("legs") or []}})
                if op == "interrupt":
                    return self._json({"ok": True, "state": "idle"})
                return self._json({"ok": False, "error": "user_error: 未知 op %s" % op}, 400)
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/browser":
            # 2026-11-02：内置浏览器页的「原生浏览器（Chrome CDP）」控制面；只走 run_task 门，不绕过
            try:
                from gbt_allinone import api as _api
                act = str(body.get("action") or "status")
                params = {k: v for k, v in body.items() if k not in ("op", "action")}
                env = _api.run_task("browser", {"op": "native", "action": act, **params}, safe=True)
                res = ((env.get("gbt_result") or {}).get("result")
                       if isinstance(env, dict) else None) or {}
                return self._json({"ok": bool(res.get("ok")), "action": act,
                                   "result": res, "envelope_ok": bool(env.get("gbt_result"))
                                   if isinstance(env, dict) else False})
            except Exception as e:  # noqa: BLE001
                return self._json({"ok": False, "error": "%s: %s"
                                   % (type(e).__name__, str(e)[:200])}, 500)
        if path == "/api/chat":
            text = str(body.get("text") or "").strip()
            if not text and not body.get("image") and not body.get("file"):
                return self._json({"ok": False, "error": "user_error: 需要 text / image / file"}, 400)
            try:
                return self._json(_chat(text, str(body.get("context") or CONTEXT_NAME),
                                        use_capabilities=body.get("capability") is not False,
                                        image=body.get("image"),
                                        image_name=str(body.get("image_name") or ""),
                                        file=body.get("file"),
                                        file_name=str(body.get("file_name") or ""),
                                        file_type=str(body.get("file_type") or "")))
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
    print("认知界面: http://127.0.0.1:%d/  （/api/data · /api/chat（含 capability_router 四类）· /api/memory）" % a.port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

