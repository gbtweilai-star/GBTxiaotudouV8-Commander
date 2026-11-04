# -*- coding: utf-8 -*-
"""media_library（媒体舞台/音乐库/历史索引）契约/API/视图/APP 验收。"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import media_library as ML  # noqa: E402

OK = 0
FAIL = []


def check(name, cond, got=None):
    global OK
    if cond:
        OK += 1
        print("  ok  ", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, "|", repr(got)[:200])


def main() -> int:
    print("[1] 契约（分类/去重/排序/过滤/路径拒绝）")
    r = ML.verify()
    check("verify() 全绿", r["ok"] is True, r.get("failed"))
    check("判据数 ≥ 15", r["checks"] >= 15, r["checks"])
    rows = [{"path": "交付成片/片A.mp4", "size": 1000000, "mtime": 100},
            {"path": "交付成片/图A.png", "size": 200000, "mtime": 200},
            {"path": "交付成片/声A.wav", "size": 300000, "mtime": 300},
            {"path": "交付成片/片A.mp4", "size": 1000000, "mtime": 100},
            {"path": "交付成片/a.exe", "size": 1, "mtime": 1},
            {"path": "../evil.mp4", "size": 1, "mtime": 1}]
    b = ML.build(rows)
    check("去重/拒坏", b["count"] == 3, b["count"])
    check("分组计数", b["counts"] == {"video": 1, "image": 1, "audio": 1}, b["counts"])
    check("mtime 倒序", [x["kind"] for x in b["items"]] == ["audio", "image", "video"])
    check("kind 过滤", ML.build(rows, kind="video")["count"] == 1)
    check("路径穿越拒", _raises(lambda: ML.normalize_item({"path": "../x.mp4", "size": 1, "mtime": 1})))
    check("绝对路径拒", _raises(lambda: ML.normalize_item({"path": "C:/x.mp4", "size": 1, "mtime": 1})))
    check("坏扩展拒", _raises(lambda: ML.normalize_item({"path": "x.exe", "size": 1, "mtime": 1})))
    check("负数拒", _raises(lambda: ML.normalize_item({"path": "x.mp4", "size": -1, "mtime": 1})))
    check("非数组拒", _raises(lambda: ML.build("x")))
    check("kind 非法拒", _raises(lambda: ML.build(rows, kind="doc")))
    check("limit 截断", ML.build(rows, limit=2)["count"] == 2)
    check("历史", ML.history(rows, limit=2)["count"] == 2)

    print("[2] 统一门 / API / 视图 / APP")
    reg = (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8")
    check("注册表 media_library", '"media_library": {' in reg and '"handler": "media_library"' in reg)
    check("api 分派 media_library", 'kind == "media_library"' in api)
    check("run_task 可达", _gate_ok())
    srv = (ROOT / "tools/console-server.py").read_text(encoding="utf-8")
    check("server /api/media + 文件服务", '"/api/media"' in srv and "/api/media/file" in srv
          and "_media_resolve" in srv)
    idx = (ROOT / "holo_pet_w3/console/index.html").read_text(encoding="utf-8")
    check("console 媒体舞台视图", 'data-view="media"' in idx and 'id="ms-grid"' in idx
          and "media-stage.js" in idx)
    js = (ROOT / "holo_pet_w3/console/media-stage.js").read_text(encoding="utf-8")
    check("视图只读索引/播放", "/api/media" in js and "/api/media/file" in js)
    payload = (ROOT.parent / "GBT小土豆V8桌面版" / "payload")
    if payload.is_dir():
        check("APP payload 已同步 media_library",
              (payload / "gbt_allinone/tools/media_library.py").is_file()
              and '"media_library": {' in (payload / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8"))
        check("APP 媒体根已打包", (payload / "media").is_dir())
    check("文档 docs/172 存在", (ROOT / "docs/172-media-stage.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— media_library（分类/去重/排序/路径拒绝）+ 统一门/文件服务/视图/APP 全绿")
    return 0


def _raises(fn):
    try:
        fn()
        return False
    except (ML.MediaError, ValueError):
        return True


def _gate_ok():
    try:
        import gbt_allinone as g
        r = g.run_task("media_library", {"op": "verify"}, safe=True)
        inner = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return bool(r.get("ok")) and bool(inner.get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
