# -*- coding: utf-8 -*-
# gbt-capability: read_only  ⬻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""创作融合台（comfy_forge）—— 用秋叶版 ComfyUI 的**节点**来融合她的**创作能力**。

主人令（2026-10-15）：「借助秋叶版的节点来融合她的创作能力」。

为什么是一个**只读台**而不是又一个"ComfyUI 控制器"：
  控制器已经有三个了（`comfyui` 全控 · `comfy_native`/GBT天真 · `tentacle_comfy_bridge` 第1530根触手），
  不重造第四个。本位只做一件它们都没做的事：**把 962 个节点按创作用途
  分成族，并说清每族饲哪些创作能力位** —— 让她知道"这件事我可以用哪几把节点做"。

读的是**盘上已抓下来的快照**：
  · `state/comfyui_surface.json`（面表：节点/端点/启动开关）
  · `state/comfyui_object_info.json`（每把节点的完整输入 schema）
  ⇒ **ComfyUI 本体没在跑也能用**（本机只有 C 盘、AMD 无 CUDA）。
  但**快照就是快照**：读数里如实报采集时间与文件 mtime，不冒充"现在连着"。

只读、零作用域（不起进程、不出网、不写盘）。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SURFACE = ROOT / "state" / "comfyui_surface.json"
OBJECT_INFO = ROOT / "state" / "comfyui_object_info.json"
MIN_NODES = 900
READ_OPS = ("families", "map", "find", "evidence")
WRITE_OPS = ()

# 节点类目 → 创作用途族 × 饲哪些创作能力位
FAMILIES = (
    ("生图", ("image", "latent", "sampling", "loaders", "conditioning", "_for_testing"),
     ("create", "comfyui", "a1art_skill")),
    ("控图预处理", ("ControlNet Preprocessors", "ipadapter", "ImpactPack", "mask"),
     ("emotion_projection", "scene_anchor", "create")),
    ("视频", ("Video Helper Suite", "Animate Diff", "Frame-Interpolation", "api node"),
     ("media_pipeline", "h3_video_gen", "libtv_workflow")),
    ("音频", ("audio",), ("music_publishing", "voice")),
    # 3D 族（Load3D/Preview3D/SaveGLB/VoxelToMesh）饲场景锚定与资产生成；
    #   注：`digihuman` 是**技能**不是能力位（判据当场咬出，2026-10-15）。
    ("3D", ("3d",), ("scene_anchor", "create")),
    ("模型与补丁", ("model_patches", "advanced", "utils"),
     ("comfy_native", "comfyui"))
)


def _read(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _provenance() -> dict:
    s = _read(SURFACE)
    oi = _read(OBJECT_INFO)
    def _mtime(p: Path):
        try:
            return int(p.stat().st_mtime)
        except OSError:
            return None
    nodes = list(oi.keys())
    n_surface = len(s.get("nodes") or [])
    return {"surface_file": str(SURFACE), "object_info_file": str(OBJECT_INFO),
            "captured_at": s.get("at"), "surface_nodes": n_surface,
            "schema_nodes": len(nodes), "min_nodes": MIN_NODES,
            "surface_mtime_age_s": (int(time.time() - _mtime(SURFACE)) if _mtime(SURFACE) else None),
            "endpoints": len(s.get("endpoints") or []),
            "launch_flags": len(s.get("launch_flags") or []),
            "counts": s.get("counts") or {},
            "口径": s.get("_口径") or "让 ComfyUI 自己报（/object_info）",
            "honest": ("读的是**盘上快照**（ComfyUI 本体未在跑）；快照不等于现在连着"
                       if n_surface else "快照读不到（未读到，不当空）")}


def _family_of(node: dict) -> str:
    cat = str((node or {}).get("category") or "")
    for fam, keys, _caps in FAMILIES:
        for k in keys:
            if k.lower() in cat.lower():
                return fam
    return "其他"


def families() -> dict:
    """按创作用途分族：每族多少把节点、样本、饲哪些创作能力位。"""
    oi = _read(OBJECT_INFO)
    if not oi:
        return {"ok": False, "reason": "no_snapshot", "detail": "节点快照读不到",
                "path": str(OBJECT_INFO)}
    buckets = {fam: [] for fam, _k, _c in FAMILIES}
    buckets["其他"] = []
    for name, node in oi.items():
        buckets[_family_of(node)].append(name)
    out = []
    for fam, _keys, caps in FAMILIES:
        ns = sorted(buckets[fam])
        out.append({"family": fam, "nodes": len(ns), "sample": ns[:12],
                    "feeds_capabilities": list(caps)})
    out.append({"family": "其他", "nodes": len(buckets["其他"]),
                "sample": sorted(buckets["其他"])[:12], "feeds_capabilities": []})
    return {"ok": True, "op": "families", "total_nodes": len(oi),
            "families": out, "provenance": _provenance()}


def map_nodes(family: str = "") -> dict:
    """节点 → 创作能力 的双向对照（可选只看一族）。"""
    r = families()
    if not r.get("ok"):
        return r
    fams = r["families"]
    if family:
        fams = [f for f in fams if f["family"] == family]
        if not fams:
            return {"ok": False, "reason": "unknown_family", "family": family,
                    "known": [f["family"] for f in r["families"]]}
    by_cap: dict = {}
    for f in fams:
        for c in f["feeds_capabilities"]:
            by_cap.setdefault(c, {"capability": c, "families": [], "nodes": 0})
            by_cap[c]["families"].append(f["family"])
            by_cap[c]["nodes"] += f["nodes"]
    return {"ok": True, "op": "map", "family": family or "all",
            "families": fams, "by_capability": sorted(by_cap.values(),
                                                    key=lambda x: -x["nodes"]),
            "provenance": r["provenance"]}


# 她用中文问，节点名全是英文 ⇒ **中→英 桥**（实测：问“视频”0 命中，问 video 151 命中）。
#   只做词桥，不做语义推理；桥不到就如实回 0（不猜）。
CN_EN = {
    "视频": ("video", "animate", "vhs", "frame"),
    "生图": ("image", "sampler", "latent", "checkpoint"),
    "图像": ("image", "mask", "preprocessor"),
    "控图": ("controlnet", "preprocessor", "pose", "depth"),
    "姿态": ("pose", "openpose", "dwpose"),
    "脸": ("face", "facedetector"),
    "音频": ("audio", "sound"),
    "声音": ("audio",),
    "3d": ("3d", "glb", "mesh", "voxel"),
    "三维": ("3d", "glb", "mesh", "voxel"),
    "上色": ("color", "palette"),
    "超分": ("upscale", "esrgan", "resize"),
    "放大": ("upscale", "resize"),
    "字幕": ("text", "prefix", "suffix"),
    "动画": ("animate", "animation", "motion"),
    "模型": ("model", "lora", "clip", "checkpoint"),
    "提示词": ("text", "prompt", "clip"),
    "合成": ("composite", "merge", "blend", "overlay"),
    "拼接": ("batch", "combine", "concat", "merge"),
    "渐变": ("gradient",),
    "调色": ("hue", "saturation", "level", "color", "blend"),
    "对比度": ("level", "contrast"),
    "亮度": ("level", "hue", "saturation"),
    "镜像": ("transpose", "flip"),
    "翻转": ("transpose", "flip", "rotate"),
    "旋转": ("rotate",),
    "遮罩": ("mask",),
    "窗口": ("mask", "image"),
    "锐化": ("sharpen", "blur"),
    "模糊": ("blur",),
    "水印": ("text", "composite"),
    "缩放": ("scale", "resize"),
}


def _expand_query(q: str) -> list:
    """中文关键词扩成英文同义组（原词也留着）。"""
    key = str(q or "").strip().lower()
    keys = [key]
    for cn, ens in CN_EN.items():
        if cn in key:
            keys.extend(ens)
    return [k for k in dict.fromkeys(keys) if k]


def find(q: str = "", limit: int = 40) -> dict:
    """按关键词找节点（她问“这件事有没有节点”时用）。"""
    key = str(q or "").strip().lower()
    if not key:
        return {"ok": False, "reason": "need_query", "detail": "给个关键词（不许猜）"}
    oi = _read(OBJECT_INFO)
    if not oi:
        return {"ok": False, "reason": "no_snapshot", "path": str(OBJECT_INFO)}
    keys = _expand_query(key)
    hits = []
    for name, node in oi.items():
        cat = str((node or {}).get("category") or "")
        dn = str((node or {}).get("display_name") or "")
        if any(k in name.lower() or k in cat.lower() or k in dn.lower() for k in keys):
            hits.append({"node": name, "category": cat, "family": _family_of(node),
                         "output_node": bool((node or {}).get("output_node"))})
    return {"ok": True, "op": "find", "query": q, "total": len(hits),
            "nodes": hits[:max(1, int(limit))], "provenance": _provenance()}


def evidence() -> dict:
    """出处与新鲜度（不许假绿：读不到就说读不到）。"""
    p = _provenance()
    ok = bool(p.get("surface_nodes")) and bool(p.get("schema_nodes"))
    return {"ok": ok, "op": "evidence", "provenance": p,
            "verdict": ("可用（离线快照）" if ok else "读不到（未读到）")}


def run(op: str = "families", **kw) -> dict:
    """能力位入口。未知 op fail-closed。"""
    o = (op or "families").strip().lower()
    if o == "families":
        return families()
    if o == "map":
        return map_nodes(kw.get("family", ""))
    if o == "find":
        return find(kw.get("q", ""), int(kw.get("limit", 40) or 40))
    if o == "evidence":
        return evidence()
    return {"ok": False, "reason": "unknown_op", "op": o,
            "known": list(READ_OPS) + list(WRITE_OPS),
            "detail": "未知 op 只回错（fail-closed）"}
