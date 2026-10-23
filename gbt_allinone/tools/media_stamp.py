# -*- coding: utf-8 -*-
# gbt-capability: media-stamp  ⏛ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""音视频**钢印**能力位（media_stamp）—— 把「作品带出处」从管线内部维度变成**可单独点名的能力**。

由来：主人 2026-10-09 问「元数据给她接入了吗？」—— 当时只接了一半：
钢印会打在 `media_run` 每件产物上，但**不能单独叫**。现补齐三处（能力表 + api 分派 + 门作用域）。

口径：签名写进**容器元数据**（title/artist/album/comment/description），并**回读校验**（不是许愿）。
为什么要它：本仓 `signature` 钢印只盖文本页（.md/.html/.txt/.csv），音视频不在它范围里。

op：
  status  只读——可打类型清单 + 钢印句子 + 台账读数
  tags    只读——ffprobe 现读一件的容器标签
  verify  只读——扫一件或一个目录（逐件报「带/不带钢印」，**不报合计**）
  stamp   写类——打钢印 + 回读校验（过 `filesystem_write` 门；写面自收窄到 projects/ · outputs/ · .scratch/）
"""
from __future__ import annotations

import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
READ_OPS = ("status", "tags", "verify")
WRITE_OPS = ("stamp",)
_EXTS = (".mp4", ".mov", ".mkv", ".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus")


def _core():
    from . import media_run as _mr
    return _mr


def _iter_media(target: Path):
    if target.is_file():
        yield target
        return
    for p in sorted(target.rglob("*")):
        if p.is_file() and p.suffix.lower() in _EXTS:
            yield p


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status").lower()
    mr = _core()
    if op == "status":
        return {"ok": True, "op": "status", "stampable": list(_EXTS),
                "signature": mr._SIG_LINE,
                "read_ops": list(READ_OPS), "write_ops": list(WRITE_OPS),
                "note": "钢印写**容器元数据**并回读校验；文本页钢印仍走 `signature`。"}
    if op == "tags":
        p = _ROOT / str(kw.get("file") or "")
        if not p.is_file():
            return {"ok": False, "error": "件不在：%s" % p}
        t = mr._read_media_tags(p)
        blob = " ".join(str(v) for v in t.values())
        return {"ok": True, "op": "tags", "file": str(kw.get("file")), "tags": t,
                "has_steel_stamp": ("自由的风" in blob and "不可篡改归属" in blob)}
    if op == "verify":
        target = _ROOT / str(kw.get("path") or "projects")
        if not target.exists():
            return {"ok": False, "error": "路径不在：%s" % target}
        rows = []
        for p in _iter_media(target):
            t = mr._read_media_tags(p)
            blob = " ".join(str(v) for v in t.values())
            rows.append({"件": p.relative_to(_ROOT).as_posix(),
                         "带钢印": ("自由的风" in blob and "不可篡改归属" in blob),
                         "标签数": len(t)})
        missing = [r["件"] for r in rows if not r["带钢印"]]
        return {"ok": not missing, "op": "verify", "path": str(kw.get("path") or "projects"),
                "明细": rows, "带钢印": len(rows) - len(missing), "总数": len(rows),
                "缺钢印": missing}
    if op == "stamp":
        files = kw.get("files") or ([kw.get("file")] if kw.get("file") else [])
        if isinstance(files, str):
            files = [files]
        if not files:
            return {"ok": False, "error": "stamp 需要 files（一件或一列）"}
        rows = []
        for f in files:
            g = mr.write_guard(str(f))
            if not g.get("ok"):
                rows.append({"件": str(f), "ok": False, "why": g.get("why")})
                continue
            p = Path(g["abs"])
            r = mr._stamp_media(p, str(kw.get("work") or p.stem), str(kw.get("kind") or ""), "stamp")
            rows.append({"件": str(f), "ok": bool(r.get("ok")),
                         "回读": r.get("verified"), "字节": r.get("bytes"),
                         "tags": r.get("tags"), "error": r.get("error")})
        return {"ok": bool(rows) and all(x.get("ok") for x in rows), "op": "stamp",
                "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "明细": rows,
                "打了几件": sum(1 for x in rows if x.get("ok")), "总数": len(rows)}
    return {"ok": False, "error": "不认的 op：%s" % op,
            "known": list(READ_OPS) + list(WRITE_OPS)}
