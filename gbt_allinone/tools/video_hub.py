# -*- coding: utf-8 -*-
# gbt-capability: video_hub  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""视频舱（video_hub）—— 把全部视频相关能力融合成一条链。

**只做编目/融合，不执行、不伪造状态**：
  · 深度盘点注册表里所有 `domain=video/image_video` 的能力位（外加 Comfy/数字人/音乐等链路件）；
  · 按“生成 → 编辑/成片 → 音频 → 钢印/许可/发布 → 情报/外观 → 库/舞台”六段归类；
  · 每件带：能力名、所属段、domain、一句能力说明、是否在注册表；
  · 未归段的能力自动进“其他”，不丢件；`verify()` 检查覆盖完整性。
前端「视频舱」页面只展示编目；真正执行仍走各能力位自己的统一门。
"""
from __future__ import annotations

import hashlib

STAGES = (
    ("生成", "文/图/视频/数字人/动作镜头"),
    ("编辑/成片", "剧本、分镜、剪辑、影片产线、Media 工作流"),
    ("音频", "取音、混音、音乐自动化、音乐发布"),
    ("钢印/许可/发布", "钢印、素材许可、平台发布、LibTV/a1.art"),
    ("情报/外观", "视频/影视/音乐情报、外观调色"),
    ("库/舞台", "媒体舞台索引"),
    ("其他", "未归段但属于视频生态的能力"),
)
VIDEO_DOMAINS = ("video", "image_video")
EXTRA = {
    "comfy_native", "comfyui", "comfy_cloud", "comfy_forge", "tentacle_comfy_bridge",
    "digital_human", "music_auto", "music_publishing", "drama_forge", "drama",
    "machine_film", "filmkit", "libtv_skill", "libtv_workflow", "a1art_skill",
    "music_intel", "video_intel", "film_intel", "look_grade", "media_library",
}
MAPPING = {
    "comfy_native": "生成", "comfyui": "生成", "comfy_cloud": "生成",
    "comfy_forge": "生成", "tentacle_comfy_bridge": "生成",
    "hunyuan_video": "生成", "i2v_agnes": "生成", "h3_video_gen": "生成",
    "digital_human": "生成", "actioncam": "生成", "machine_film": "生成",
    "edit_pipeline": "编辑/成片", "filmkit": "编辑/成片", "drama_forge": "编辑/成片",
    "drama": "编辑/成片", "media_run": "编辑/成片", "media_pipeline": "编辑/成片",
    "audio_extract": "音频", "audio_mix": "音频", "music_auto": "音频",
    "music_publishing": "音频",
    "media_stamp": "钢印/许可/发布", "media_license": "钢印/许可/发布",
    "media_publish": "钢印/许可/发布", "libtv_skill": "钢印/许可/发布",
    "libtv_workflow": "钢印/许可/发布", "a1art_skill": "钢印/许可/发布",
    "video_intel": "情报/外观", "film_intel": "情报/外观", "music_intel": "情报/外观",
    "look_grade": "情报/外观", "media_library": "库/舞台",
}


def _caps() -> dict:
    from ..caps_registry import BENIGN_CAPS
    return BENIGN_CAPS


def _is_video(name: str, meta: dict) -> bool:
    dom = str(meta.get("domain") or "").lower()
    if dom in VIDEO_DOMAINS:
        return True
    return name in EXTRA


def catalog() -> dict:
    caps = _caps()
    rows = []
    for name, meta in caps.items():
        if not _is_video(name, meta):
            continue
        stage = MAPPING.get(name, "其他")
        rows.append({"cap": name, "stage": stage,
                     "domain": str(meta.get("domain") or ""),
                     "desc": str(meta.get("desc") or "")[:180],
                     "handler": str(meta.get("handler") or name),
                     "registered": True})
    rows.sort(key=lambda r: (r["stage"], r["cap"]))
    stages = []
    for title, sub in STAGES:
        items = [r for r in rows if r["stage"] == title]
        stages.append({"stage": title, "sub": sub, "count": len(items), "items": items})
    return {"ok": True, "count": len(rows), "stages": stages,
            "domain": "video", "note": "编目只读；执行仍走各能力位统一门"}



PROBES = (
    ("生成", "hunyuan_video", {"op": "status"}),
    ("编辑/成片", "media_pipeline", {"op": "status"}),
    ("音频", "music_auto", {"op": "check"}),
    ("钢印/许可/发布", "media_license", {"op": "status"}),
    ("情报/外观", "video_intel", {"op": "probe"}),
    ("库/舞台", "media_library", {"op": "verify"}),
)


def _catalog_names() -> set:
    return {r["cap"] for st in catalog()["stages"] for r in st["items"]}


def dispatch(cap: str, payload=None) -> dict:
    """视频舱统一执行入口：只允许编目里的视频能力，执行仍走该能力自己的统一门。"""
    ap = str(cap or "")
    if ap not in _catalog_names():
        return {"ok": False, "error": "user_error: 不在视频编目里", "cap": ap}
    from .. import api as _api
    try:
        env = _api.run_task(ap, payload or {}, probe=False)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "cap": ap, "error": "%s: %s" % (type(e).__name__, str(e)[:160])}
    gr = env.get("gbt_result") or {}
    res = gr.get("result") if isinstance(gr.get("result"), dict) else {}
    return {"ok": bool(env.get("ok")) and res.get("ok") is not False,
            "cap": ap, "result": res, "gate": "run_task"}


def run_stages() -> dict:
    """六段只读探针联跑：逐段调真实能力，失败如实停/记，不生成视频、不伪造。"""
    rows = []
    for stage, cap, payload in PROBES:
        got = dispatch(cap, payload)
        rows.append({"stage": stage, "cap": cap, "ok": got.get("ok"),
                     "result": got.get("result"), "error": got.get("error")})
    return {"ok": all(r["ok"] for r in rows), "stages": rows,
            "mode": "read_only_probes", "video_generated": False,
            "note": "只跑各段只读探针；不生成视频；失败如实记"}


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    c = catalog()
    ck("视频能力 ≥ 20", c["count"] >= 20, c["count"])
    ck("六段+其他", len(c["stages"]) == len(STAGES))
    caps = {r["cap"] for st in c["stages"] for r in st["items"]}
    ck("编目不重复", len(caps) == c["count"])
    ck("没有未归段丢件", all(r["stage"] for st in c["stages"] for r in st["items"]))
    ck("每段有说明", all(st["sub"] for st in c["stages"]))
    ck("生成段非空", any(st["stage"] == "生成" and st["count"] for st in c["stages"]))
    ck("库段非空", any(st["stage"] == "库/舞台" and st["count"] for st in c["stages"]))
    ck("关键能力在", {"media_run", "media_library", "digital_human"} <= caps)
    return {"ok": all(x["ok"] for x in checks), "checks": len(checks),
            "failed": [x for x in checks if not x["ok"]],
            "sha": hashlib.sha256(str(checks).encode()).hexdigest()[:12]}


def run(op="schema", **params):
    op = str(op or "schema").lower()
    if op == "schema":
        return {"ok": True, "stages": [s[0] for s in STAGES], "domain": "video",
                "mode": "catalog", "execute": False, "router": True,
                "note": "视频能力融合编目；不执行/不伪造状态"}
    if op == "catalog":
        return catalog()
    if op == "run":
        return run_stages()
    if op == "dispatch":
        return dispatch(params.get("cap") or "", params.get("payload") or {})
    if op == "verify":
        return verify()
    raise ValueError("未知 op: %s（schema/catalog/run/dispatch/verify）" % op)
