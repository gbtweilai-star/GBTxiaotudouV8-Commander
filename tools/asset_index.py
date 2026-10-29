#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""asset_index —— 资产索引（薄适配，不重写实现）

## 为什么是适配器而不是新引擎
`_TOOL_IMPL` 把它映射到本文件，但仓库里从来只有 `holo_pet_w3/brain/caps/asset_index.html`
（说明书页），**没有实现** —— 对齐全量跑出来就是 `impl_missing`。

而"整棵树扫一次、之后秒查"这件事，`tools/disk_index.py` 已经做完了：
build 扫全盘落 `state/disk_index.json.gz`，find 走索引不扫盘（实测毫秒级）。
所以这里**只做口径转换**：把 asset_index 的 op 翻成 disk_index 的调用，
再加一条它没有的 `wire`（把扫到的资产补触手标签，交给 tentacle_bind 判归属）。
再写一套扫描引擎 = 重复件，纪律不许。

## op
    build   扫一次（委托 disk_index.build）
    find    查询（委托 disk_index.load，路径/文件名模糊匹配）
    stats   读数（数量/体积/耗时）
    wire    给未绑的资产补触手标签（委托 tentacle_bind.gapbind，认不出不硬认）

返回一律带 `via`（走的哪一件）与 `delegated`（是不是转手），
不许让人猜"这数到底谁算的"。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))


def _disk():
    import disk_index as d
    return d


def _safe_load():
    """disk_index.load() 在没索引时直接 sys.exit(2) —— 适配层不能把它漏成退出。"""
    d = _disk()
    try:
        return d.load(), None
    except SystemExit:
        return None, "还没索引 ⇒ 先 build"

def op_build() -> dict:
    d = _disk()
    t = time.time()
    try:
        r = d.build()
    except Exception as exc:                                      # noqa: BLE001
        return {"ok": False, "op": "build", "via": "disk_index.build",
                "error": "%s: %s" % (type(exc).__name__, str(exc)[:120])}
    return {"ok": True, "op": "build", "via": "disk_index.build", "delegated": True,
            "elapsed_s": round(time.time() - t, 1),
            "files": (r or {}).get("files"), "dirs": (r or {}).get("dirs"),
            "index_kb": (r or {}).get("index_kb")}


def op_find(q: str, limit: int = 20) -> dict:
    st, err = _safe_load()
    if err:
        return {"ok": False, "op": "find", "via": "disk_index.load", "error": err}
    rows = st.get("rows") or []
    ql = (q or "").lower()
    hit = [str(x[0]) for x in rows if ql in str(x[0]).lower()]
    return {"ok": True, "op": "find", "via": "disk_index.load", "delegated": True,
            "q": q, "hits": len(hit), "sample": hit[:limit]}


def op_stats() -> dict:
    st, err = _safe_load()
    if err:
        return {"ok": False, "op": "stats", "via": "disk_index.load", "error": err}
    return {"ok": True, "op": "stats", "via": "disk_index.load", "delegated": True,
            "files": st.get("files"), "dirs": st.get("dirs"),
            "scan_ms": st.get("scan_ms"), "built_at": st.get("built_at"),
            "index": str(ROOT / "state" / "disk_index.json.gz")}


def op_wire() -> dict:
    """补触手标签：交给 tentacle_bind.gapbind，认不出的如实不绑。"""
    import subprocess
    try:
        r = subprocess.run([sys.executable, str(TOOLS / "tentacle_bind.py"), "gapbind"],
                           capture_output=True, text=True, timeout=900, cwd=str(ROOT))
        out = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-2:]
        return {"ok": r.returncode == 0, "op": "wire", "via": "tentacle_bind.gapbind",
                "delegated": True, "tail": out}
    except Exception as exc:                                      # noqa: BLE001
        return {"ok": False, "op": "wire", "via": "tentacle_bind.gapbind",
                "error": "%s: %s" % (type(exc).__name__, exc)}


# ── 能力位入口：唯一门按 op 名直接 getattr(module, op) ────────────────────
#   （2026-10-30 实测：只给 op_* 名字会报 module has no attribute 'stats'）
# 签名必须与 gbt_allinone/api.py 的分派**逐字对齐**（2026-10-30 实测：
#   api.py 调 find(q, limit, label, ext) / build(verbose=False) / wire(dry=, limit=)）
def build(verbose: bool = False) -> dict:
    return op_build()


def find(q: str = "", limit: int = 20, label: str = "", ext: str = "") -> dict:
    r = op_find(q, limit)
    if r.get("ok") and (label or ext):
        rows = [x for x in (r.get("sample") or [])
                if (not label or label.lower() in x.lower())
                and (not ext or x.lower().endswith(ext.lower()))]
        r["sample"] = rows
        r["filtered_by"] = {"label": label, "ext": ext}
    return r


def stats() -> dict:
    return op_stats()


def wire(dry: bool = True, limit: int = 0) -> dict:
    """dry=True 只报清单不写盘（api.py 默认 dry=True，安全）。"""
    if dry:
        import subprocess
        try:
            r = subprocess.run([sys.executable, str(TOOLS / "tentacle_bind.py"), "gaps"],
                               capture_output=True, text=True, timeout=600, cwd=str(ROOT))
            miss = [l.split(":", 1)[1].strip() for l in (r.stdout or "").splitlines()
                    if "该绑未绑" in l]
            if limit:
                miss = miss[:limit]
            return {"ok": True, "op": "wire", "dry": True, "would_bind": len(miss),
                    "sample": miss[:20], "via": "tentacle_bind.gaps"}
        except Exception as exc:                                  # noqa: BLE001
            return {"ok": False, "op": "wire", "dry": True,
                    "error": "%s: %s" % (type(exc).__name__, exc)}
    return op_wire()


def run(op: str = "stats", **kw) -> dict:
    op = (op or "stats").lower()
    if op == "build":
        return op_build()
    if op == "find":
        return op_find(str(kw.get("q") or kw.get("query") or ""), int(kw.get("limit") or 20))
    if op == "wire":
        return op_wire()
    return op_stats()


def main(argv: list) -> int:
    op = argv[1] if len(argv) > 1 else "stats"
    kw = {"q": argv[2]} if len(argv) > 2 else {}
    r = run(op, **kw)
    import json
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
