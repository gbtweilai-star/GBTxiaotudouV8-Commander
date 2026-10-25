# gbt-capability: comfyui
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""ComfyUI（秋叶整合版）可控制面 · **一个不漏的双向绑定**（主人令 2026-09-27）。

主人原话：「记得主要是这个必须也是一个不漏的双向绑定好，才能实现**无限制审查生产**。」
（无限制审查生产 = 本地生图/生视频不受外部免费源限制：外面限流限次限内容，本地是自己的机器。）

## 实测（2026-09-27 · 本机 `C:\\Users\\ADMIN\\ComfyUI` · 服务在 **127.0.0.1:8188**）
  · ComfyUI **0.37.0** · python 3.12.10 · 设备 **cpu**（没走 CUDA —— 出片慢但能出，如实记）
  · **966 个节点**（每把=一个可控制键）：model 371 · partner 285 · image 215 · video 143 ·
    conditioning 133 · 3d 85 · latent 78 · sampling 53 …
  · 模型：checkpoints 2 · loras 1 · controlnet 1

## 出网纪律（**硬钉**，不是"看着办"）——安全钩子的 SSRF 判据要求
  ① **只许本机服务**：主机必须是 `127.0.0.1` / `localhost` / `::1`，端口必须是 **8188**；
  ② **只许 http**（本机服务没有 TLS）；**拒重定向**（自定义 opener：302/307 一律不跟）；
  ③ **路径白名单**（前缀制）：只允许 `/prompt /queue /history /interrupt /free /view
     /upload/image /object_info /system_stats /embeddings /models/`；
  ④ 端口/主机可探（`GBT_COMFYUI_BASE`）但**仍必须过上面三条**——换了主机就直接拒，不给旁路。

## 可控制面（四类）
  ① **966 个节点**（`/object_info`，含每把的输入 schema）；② **API 端点**（见上白名单）；
  ③ **模型清单**（checkpoints/loras/controlnet ⇒ 生产前先看有什么）；④ **启动开关**（--port/--lowvram/--cpu…）。
  重扫对比：**节点消失=断连**（插件被卸/升级改名），要解释或补。

ops：status / nodes / models / submit（过门）/ queue / history / free / interrupt / surface / verify
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST = _ROOT / "state" / "comfyui_surface.json"
_OBJECT_INFO = _ROOT / "state" / "comfyui_object_info.json"
_LEDGER = _ROOT / "state" / "comfyui_ops.jsonl"
MIN_NODES = 900                     # 实测 966，阈值留余量

# ── 出网硬钉（SSRF 防线：协议 + 主机 + 端口 + 路径，四条一起过）──────────────────
_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}
_ALLOWED_PORT = 8188
_PATH_PREFIXES = ("/prompt", "/queue", "/history", "/interrupt", "/free", "/view",
                  "/upload/image", "/object_info", "/system_stats", "/embeddings", "/models/")
_DEFAULT_BASE = "http://127.0.0.1:8188"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """拒重定向（防被 302 拐到别处）。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):   # noqa: D102
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)

API_ENDPOINTS = [
    ("/prompt", "提交工作流（写图）", "write"), ("/queue", "队列", "read"),
    ("/history", "历史", "read"), ("/interrupt", "打断当前", "write"),
    ("/free", "释放显存/内存", "write"), ("/view", "取输出图", "read"),
    ("/upload/image", "上传图", "write"), ("/object_info", "节点注册表", "read"),
    ("/system_stats", "系统读数", "read"), ("/embeddings", "embedding 列表", "read"),
    ("/models/{family}", "模型家族清单", "read"),
]
LAUNCH_FLAGS = ["--port", "--listen", "--lowvram", "--novram", "--cpu", "--highvram",
                "--preview-method", "--disable-smart-memory", "--force-fp16", "--bf16-unet",
                "--reserve-vram", "--temp-directory", "--output-directory", "--extra-model-paths-config"]


def _guard(path: str) -> tuple:
    """四条一起过：http + 主机白名单 + 端口 + 路径前缀。返回 (base, 原因)。"""
    base = (os.environ.get("GBT_COMFYUI_BASE") or _DEFAULT_BASE).strip()
    try:
        u = urllib.parse.urlparse(base)
    except ValueError as e:
        return "", f"base 解析失败：{e}"
    if u.scheme != "http":
        return "", f"只许 http（本机服务无 TLS），收到 {u.scheme!r}"
    if (u.hostname or "") not in _ALLOWED_HOSTS:
        return "", f"主机 {u.hostname!r} 不在白名单（只许 {sorted(_ALLOWED_HOSTS)}）—— 拒，不给旁路"
    if (u.port or 80) != _ALLOWED_PORT:
        return "", f"端口 {u.port} != {_ALLOWED_PORT}（只许 ComfyUI 本机服务）"
    if not path.startswith("/") or not any(path.startswith(p) for p in _PATH_PREFIXES):
        return "", f"路径 {path!r} 不在白名单前缀里（{_PATH_PREFIXES[:5]}…）"
    return f"http://{u.hostname}:{u.port}", ""


def _http(path: str, payload: dict | None = None, timeout: int = 300) -> dict:
    """只对本机 ComfyUI（127.0.0.1:8188）说话：**四条硬钉先过，再发请求**。"""
    base, why = _guard(path)
    if not base:
        return {"ok": False, "error": f"出网闸拒绝：{why}", "fail_closed": True}
    url = base + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")
            return {"ok": True, "status": r.status, "data": (json.loads(body) if body else {})}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "error": (e.read().decode("utf-8", "replace") or "")[:300]}
    except (urllib.error.URLError, OSError) as e:
        return {"ok": False, "error": f"连不上 ComfyUI（{type(e).__name__}）：先启动它（绘世启动器 / 8188）"}


def _log(row: dict) -> None:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row},
                            ensure_ascii=False) + "\n")


def _gate_write(detail: str) -> dict | None:
    try:
        from .. import auth_gate
        from ..security import policy as _policy
    except ImportError:
        sys.path.insert(0, str(_ROOT))
        import gbt_allinone as _g                             # noqa: F401
        from gbt_allinone import auth_gate                    # type: ignore
        from gbt_allinone.security import policy as _policy   # type: ignore
    if _policy.is_trusted():
        return None
    gate = auth_gate.check_and_consume("filesystem_write", detail=detail)
    if gate.get("ok"):
        return None
    return {"ok": False, "denied": True, "gate": "filesystem_write",
            "error": gate.get("error"), "how_to_grant": gate.get("how_to_grant")}


def status(**_kw) -> dict:
    r = _http("/system_stats", timeout=30)
    if not r.get("ok"):
        return {"ok": False, "op": "status", **r}
    d = r["data"]
    dev = (d.get("devices") or [{}])[0]
    return {"ok": True, "op": "status",
            "version": (d.get("system") or {}).get("comfyui_version"),
            "device": dev.get("name"), "type": dev.get("type"),
            "vram_total_gb": round((dev.get("vram_total") or 0) / 2 ** 30, 1),
            "_口径": "**本机服务**（127.0.0.1:8188）：不花外部积分；设备若是 cpu ⇒ 出片慢但能出"}


def nodes(q: str = "", limit: int = 40, **_kw) -> dict:
    r = _http("/object_info", timeout=300)
    if not r.get("ok"):
        return {"ok": False, "op": "nodes", **r}
    oi = r["data"]
    names = sorted(oi)
    if q:
        names = [n for n in names if q.lower() in n.lower()]
    cats = {}
    for n in oi:
        for c in (oi[n].get("category") or "未分类").split("/"):
            cats[c] = cats.get(c, 0) + 1
    return {"ok": True, "op": "nodes", "total": len(oi), "matched": len(names),
            "names": names[:limit], "top_categories": sorted(cats.items(), key=lambda x: -x[1])[:12],
            "_口径": "每把节点=一个可控制键（含输入 schema）；`q` 子串过滤"}


def models(**_kw) -> dict:
    out = {}
    for f in ("checkpoints", "loras", "vae", "controlnet", "clip", "unet", "diffusion_models",
              "embeddings", "upscale_models"):
        r = _http(f"/models/{f}", timeout=60)
        if r.get("ok"):
            v = r["data"] or []
            out[f] = {"count": len(v), "sample": v[:5]}
    return {"ok": True, "op": "models", "families": out,
            "_口径": "模型清单=可选底模/LoRA（生产前先看有什么）"}


def submit(workflow: dict | None = None, **_kw) -> dict:
    if not isinstance(workflow, dict) or not workflow:
        return {"ok": False, "error": "workflow 必须是非空字典（ComfyUI API 格式）", "fail_closed": True}
    denied = _gate_write("comfyui.submit")
    if denied:
        return denied
    r = _http("/prompt", {"prompt": workflow}, timeout=300)
    _log({"event": "submit", "ok": r.get("ok"), "status": r.get("status"),
          "prompt_id": (r.get("data") or {}).get("prompt_id")})
    return {"ok": bool(r.get("ok")), "op": "submit",
            "prompt_id": (r.get("data") or {}).get("prompt_id"), "error": r.get("error"),
            "_口径": "**写面**：它会往输出目录写图（过 filesystem_write 门）"}


def queue(**_kw) -> dict:
    r = _http("/queue", timeout=30)
    d = r.get("data") or {}
    return {"ok": bool(r.get("ok")), "op": "queue",
            "running": len(d.get("queue_running") or []), "pending": len(d.get("queue_pending") or [])}


def history(limit: int = 10, **_kw) -> dict:
    r = _http("/history", timeout=60)
    d = r.get("data") or {}
    items = list(d.items())[-int(limit):]
    return {"ok": bool(r.get("ok")), "op": "history", "count": len(d),
            "recent": [{"prompt_id": k, "status": (v.get("status") or {}).get("status_str")} for k, v in items]}


def free(unload_models: bool = False, free_memory: bool = True, **_kw) -> dict:
    denied = _gate_write("comfyui.free")
    if denied:
        return denied
    r = _http("/free", {"unload_models": bool(unload_models), "free_memory": bool(free_memory)}, timeout=60)
    _log({"event": "free", "ok": r.get("ok")})
    return {"ok": bool(r.get("ok")), "op": "free", "error": r.get("error")}


def interrupt(**_kw) -> dict:
    denied = _gate_write("comfyui.interrupt")
    if denied:
        return denied
    r = _http("/interrupt", {}, timeout=60)
    _log({"event": "interrupt", "ok": r.get("ok")})
    return {"ok": bool(r.get("ok")), "op": "interrupt", "error": r.get("error")}


def _persist_object_info(data: dict, path=None) -> dict:
    """把 `/object_info` **原样落盘** —— 这就是「**节点配置**」那一格。

    🔴 2026-10-13 补（主人令：「把秋叶版ComfyUI，**全部能力以及节点配置**精准抓取」）：
      此前 `surface()` 只把**节点类名**（966 个字符串）写进清单，**每个节点的配置没落盘**
      ⇒ 要回答"我们的排布是不是跟它一样"，缺的正是这一格（输入/输出类型 + 默认值都在这里面）。
    纯函数：**不联网、不起进程**（喂 dict 即可）—— 自检就靠它，本体没开也能验。
    """
    import hashlib
    p = Path(path) if path is not None else _OBJECT_INFO
    p.parent.mkdir(parents=True, exist_ok=True)
    nodes = data if isinstance(data, dict) else {}
    blob = json.dumps(nodes, ensure_ascii=False, sort_keys=True).encode("utf-8")
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_bytes(blob)
    os.replace(tmp, p)
    one = next(iter(sorted(nodes)), "")
    return {"path": str(p), "bytes": len(blob),
            "sha16": hashlib.sha256(blob).hexdigest()[:16], "nodes": len(nodes),
            "样例节点": one, "样例字段": sorted((nodes.get(one) or {}).keys())[:8] if one else [],
            "_口径": "原样落盘（不裁字段）；sha16 进账 ⇒ 本体一变就看得出来"}


def surface(rescan: bool = True, **_kw) -> dict:
    """可控制面清单：966 节点 + 端点 + 模型家族 + 启动开关；与上次对比（节点消失=断连）。"""
    prev = {}
    if _MANIFEST.is_file():
        try:
            prev = json.loads(_MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prev = {}
    r = _http("/object_info", timeout=300)
    if not r.get("ok"):
        return {"ok": False, "op": "surface", **r}
    node_names = sorted(r["data"])
    oi = _persist_object_info(r["data"])          # 「节点配置」那一格（2026-10-13 补）
    gone = sorted(set(prev.get("nodes") or []) - set(node_names))
    added = sorted(set(node_names) - set(prev.get("nodes") or []))
    fam = (models().get("families") or {})
    m = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "nodes": node_names,
         "counts": {"nodes": len(node_names), "endpoints": len(API_ENDPOINTS),
                    "launch_flags": len(LAUNCH_FLAGS),
                    "models": sum(v.get("count", 0) for v in fam.values())},
         "endpoints": [{"path": p, "why": w, "kind": k} for p, w, k in API_ENDPOINTS],
         "launch_flags": LAUNCH_FLAGS, "gone": gone[:200], "added": added[:200],
         "节点配置": oi,
         "_口径": "**让 ComfyUI 自己报**（/object_info，只许本机 8188）；节点消失=断连"}
    _MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = _MANIFEST.with_name(_MANIFEST.name + ".tmp")
    tmp.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, _MANIFEST)
    _log({"event": "surface", **m["counts"], "gone": len(gone), "added": len(added),
          "object_info_bytes": oi["bytes"], "object_info_sha16": oi["sha16"]})
    # 🔴 2026-10-13 修（自检抓出来的）：清单被指到**仓外**（临时靶 / 隔离 store）时
    #    `relative_to` 会抛 ValueError ⇒ 按本仓既有口径：**不在仓里就给全路径，不抛**。
    try:
        _mpath = str(_MANIFEST.relative_to(_ROOT))
    except ValueError:                                          # noqa: PERF203
        _mpath = str(_MANIFEST)
    return {"ok": True, "op": "surface", "counts": m["counts"], "gone_total": len(gone),
            "added_total": len(added), "gone_sample": gone[:5],
            "节点配置": oi,
            "manifest": _mpath}


def verify(**_kw) -> dict:
    problems = []
    if not _MANIFEST.is_file():
        problems.append("没有可控制面清单（先跑 surface）")
    else:
        d = json.loads(_MANIFEST.read_text(encoding="utf-8"))
        n = (d.get("counts") or {}).get("nodes") or 0
        if n < MIN_NODES:
            problems.append(f"节点 {n} < 阈值 {MIN_NODES}（**有漏**）")
        if d.get("gone"):
            problems.append(f"**断连**：{len(d['gone'])} 个节点消失（例：{d['gone'][:3]}）")
    return {"ok": not problems, "op": "verify", "problems": problems, "min_nodes": MIN_NODES,
            "_口径": "阈值来自实测（966）；节点消失=断连，要解释或补"}


def run_op(op: str = "status", **params) -> dict:
    op = (op or "status").lower()
    for name, fn in (("status", status), ("nodes", nodes), ("models", models), ("submit", submit),
                     ("queue", queue), ("history", history), ("free", free),
                     ("interrupt", interrupt), ("surface", surface), ("verify", verify)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（status/nodes/models/submit/queue/history/free/interrupt/surface/verify）"}
