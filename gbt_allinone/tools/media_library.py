# -*- coding: utf-8 -*-
# gbt-capability: media_library  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""媒体舞台 / 音乐库 / 历史（P2-9）—— 只聚合既有产物。

对照上游参考项目的媒体舞台：只蒸**索引/分组/历史判据**，不搬它的上传/转码/云存储。
本件只处理调用方给的条目（路径/大小/mtime），纯归一化：
  · 视频 mp4/webm/mov/m4v/mkv；图片 png/jpg/jpeg/webp/gif；音频 mp3/wav/m4a/ogg/flac；
  · 去重、按 kind 分组、按 mtime 倒序、上限 120；绝不读文件内容/不生成缩略图；
  · 只读、零作用域；文件服务由 console-server 在**允许根内**单独做。
"""
from __future__ import annotations

import hashlib
import os
import time

VIDEO = {".mp4", ".webm", ".mov", ".m4v", ".mkv"}
IMAGE = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
AUDIO = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
KINDS = ("video", "image", "audio")
MAX_ITEMS = 500
DEFAULT_LIMIT = 120


class MediaError(ValueError):
    pass


def classify(path) -> str:
    ext = os.path.splitext(str(path or ""))[1].lower()
    if ext in VIDEO:
        return "video"
    if ext in IMAGE:
        return "image"
    if ext in AUDIO:
        return "audio"
    return ""


def _clean_rel(path) -> str:
    rel = str(path or "").replace("\\", "/").strip()
    if not rel:
        raise MediaError("path 为空")
    if rel.startswith("/") or rel.startswith("~") or ":" in rel.split("/")[0]:
        raise MediaError("只许仓库内相对路径")
    parts = [p for p in rel.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise MediaError("path 不许含 ..")
    if "\x00" in rel or len(rel) > 300:
        raise MediaError("path 非法/超长")
    return "/".join(parts)


def _num(value, name, lo=0.0) -> float:
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        raise MediaError("%s 必须是数字" % name)
    if v < lo:
        raise MediaError("%s 不能为负" % name)
    return v


def normalize_item(raw) -> dict:
    if not isinstance(raw, dict):
        raise MediaError("item 必须是对象")
    rel = _clean_rel(raw.get("path"))
    kind = classify(rel)
    if not kind:
        raise MediaError("不支持的媒体扩展名: %s" % os.path.splitext(rel)[1])
    size = _num(raw.get("size"), "size")
    mtime = _num(raw.get("mtime"), "mtime")
    title = str(raw.get("title") or os.path.splitext(os.path.basename(rel))[0]).strip()[:120]
    iid = "md-" + hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12]
    return {"id": iid, "path": rel, "kind": kind,
            "ext": os.path.splitext(rel)[1].lower(),
            "title": title or os.path.basename(rel),
            "size": int(size), "size_mb": round(size / 1e6, 2),
            "mtime": mtime,
            "at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(mtime)) if mtime else ""}


def build(items, kind=None, limit=DEFAULT_LIMIT) -> dict:
    if not isinstance(items, list):
        raise MediaError("items 必须是数组")
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        raise MediaError("limit 必须是整数")
    limit = max(1, min(DEFAULT_LIMIT, limit))
    kind = str(kind or "").lower()
    if kind and kind not in KINDS:
        raise MediaError("kind 只许 %s" % ",".join(KINDS))
    rows, seen = [], set()
    for raw in items[:MAX_ITEMS]:
        try:
            it = normalize_item(raw)
        except MediaError:
            continue
        if it["path"] in seen:
            continue
        seen.add(it["path"])
        rows.append(it)
    counts = {k: 0 for k in KINDS}
    for it in rows:
        counts[it["kind"]] += 1
    if kind:
        rows = [it for it in rows if it["kind"] == kind]
    rows.sort(key=lambda x: (-x["mtime"], x["path"]))
    total = len(rows)
    rows = rows[:limit]
    return {"ok": True, "items": rows, "count": len(rows), "total": total,
            "counts": counts, "bytes": sum(it["size"] for it in rows),
            "kind": kind or "all", "limit": limit}


def history(items, limit=40) -> dict:
    built = build(items, limit=min(DEFAULT_LIMIT, max(1, int(limit or 40))))
    entries = [{"at": it["at"], "id": it["id"], "kind": it["kind"],
                "title": it["title"], "path": it["path"]} for it in built["items"]]
    return {"ok": True, "entries": entries, "count": len(entries)}


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    rows = [
        {"path": "交付成片/片A.mp4", "size": 1000000, "mtime": 100},
        {"path": "交付成片/图A.png", "size": 200000, "mtime": 200},
        {"path": "交付成片/声A.wav", "size": 300000, "mtime": 300},
        {"path": "交付成片/片A.mp4", "size": 1000000, "mtime": 100},
        {"path": "../evil.mp4", "size": 1, "mtime": 1},
        {"path": "交付成片/a.exe", "size": 1, "mtime": 1},
    ]
    b = build(rows)
    ck("去重/拒坏", b["count"] == 3, b["count"])
    ck("分组计数", b["counts"] == {"video": 1, "image": 1, "audio": 1}, b["counts"])
    ck("mtime 倒序", [x["kind"] for x in b["items"]] == ["audio", "image", "video"])
    ck("kind 过滤", build(rows, kind="video")["count"] == 1)
    ck("id 形态", b["items"][0]["id"].startswith("md-"))
    ck("size_mb", b["items"][0]["size_mb"] == 0.3, b["items"][0]["size_mb"])
    ck("路径穿越拒", _raises(lambda: normalize_item({"path": "../x.mp4", "size": 1, "mtime": 1})))
    ck("绝对路径拒", _raises(lambda: normalize_item({"path": "C:/x.mp4", "size": 1, "mtime": 1})))
    ck("坏扩展拒", _raises(lambda: normalize_item({"path": "x.exe", "size": 1, "mtime": 1})))
    ck("负数拒", _raises(lambda: normalize_item({"path": "x.mp4", "size": -1, "mtime": 1})))
    ck("非数组拒", _raises(lambda: build("x")))
    ck("kind 非法拒", _raises(lambda: build(rows, kind="doc")))
    ck("limit 截断", build(rows, limit=2)["count"] == 2)
    ck("历史", history(rows, limit=2)["count"] == 2)
    ck("空表", build([])["count"] == 0)
    ck("schema 可达", set(run("schema")["kinds"]) == set(KINDS))
    ck("未知 op 拒", _raises(lambda: run("teleport")))
    return {"ok": all(c["ok"] for c in checks), "checks": len(checks),
            "failed": [c for c in checks if not c["ok"]],
            "sha": hashlib.sha256(str(checks).encode()).hexdigest()[:12]}


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except (MediaError, ValueError):
        return True


def run(op="schema", **params):
    op = str(op or "schema").lower()
    if op == "schema":
        return {"ok": True, "kinds": list(KINDS), "video": sorted(VIDEO),
                "image": sorted(IMAGE), "audio": sorted(AUDIO),
                "max_items": MAX_ITEMS, "default_limit": DEFAULT_LIMIT,
                "note": "只聚合既有产物；不读内容/不转码/不上传"}
    if op == "build":
        try:
            return build(params.get("items") or [], params.get("kind"),
                         params.get("limit") or DEFAULT_LIMIT)
        except MediaError as e:
            return {"ok": False, "error": "user_error: %s" % e}
    if op == "history":
        try:
            return history(params.get("items") or [], params.get("limit") or 40)
        except MediaError as e:
            return {"ok": False, "error": "user_error: %s" % e}
    if op == "verify":
        return verify()
    raise ValueError("未知 op: %s（schema/build/history/verify）" % op)
