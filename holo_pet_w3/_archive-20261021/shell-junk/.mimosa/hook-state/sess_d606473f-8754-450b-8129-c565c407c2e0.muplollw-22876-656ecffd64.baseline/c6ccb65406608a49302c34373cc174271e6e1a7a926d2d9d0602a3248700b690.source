#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 上帝视角 · 四路账本 **承载物切换口**（W3 施工项 5）

《W3上帝视角镜像方案.md》§3.2 对常驻化的定义只有一句：
    「常驻化**不改判据**，只是把承载物从 `.scratch/*_ledger.jsonl` 换到 `store/ledger/*.jsonl`。」

所以本模块**只做一件事**：决定四路账本这一行落到哪个承载物上。判据（字段、指纹、
四路对齐规则）一个字都不动 —— 那部分归 `ledger_store` 与各 probe 自己的判定。

为什么要一个切换口而不是直接改路径：
  1. **默认不改行为**：不设 `GBT_LEDGER_PERSIST=1` 时，四路照旧落 `.scratch/`
     —— 探针回归、历史对比脚本（`verify_panel_ledger.py` / `diff_panel_ledger.py`）
     读的还是原来那份，一个字节都不动。
  2. **一旦开启**，承载物换成 `store/ledger/*.jsonl`，且**只追加**、**不建空文件**
     （建空文件会让"看账本"那一格假绿 —— 这条纪律在 `ledger_store` 里，本模块只是转交）。
  3. 换承载物这件事必须**可回退**：删掉环境变量就回到探针态，不留半迁移状态。

四路 ↔ ledger_store 的层名映射（层名以 `ledger_store.LAYERS` 为准）：
    panel  → panel.send     （面板/窗口发出的意图帧）
    bridge → bridge         （桥的出网帧与入站帧）
    route  → route.recv     （路由收到并转发前后的帧）
    mock   → mock.recv      （终点接收帧）

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 四路探针用的 lane 名 → ledger_store 的层名（不是 1:1，必须显式映射，不许猜）
LAYER_OF = {
    "panel": "panel.send",
    "bridge": "bridge",
    "route": "route.recv",
    "mock": "mock.recv",
}

PERSIST_ENV = "GBT_LEDGER_PERSIST"


def persist_enabled() -> bool:
    """承载物是否已切到常驻账本。只认 '1'，别的值一律当没开（不做模糊真值判断）。"""
    return os.environ.get(PERSIST_ENV, "").strip() == "1"


def _ledger_store():
    """按需 import；拿不到就返回 None（承载物切不过去时**如实降级回探针态**，不抛给调用方）。"""
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    try:
        import ledger_store  # type: ignore
        return ledger_store
    except Exception:  # noqa: BLE001
        return None


def carrier_for(lane: str, scratch_path: str | Path, root=None) -> str:
    """这一行的承载物路径（只用于回执/自检显示，不用于写）。

    root 传了就用它当仓库根 —— 让验证能在**临时根**里跑，
    不必为了测一下承载物就往真账本里种合成行（种了就是假绿）。
    """
    if not persist_enabled():
        return str(scratch_path)
    store = _ledger_store()
    if store is None:
        return str(scratch_path)
    try:
        return str(store.ledger_dir(root) / store.LEDGER_FILES[LAYER_OF[lane]])
    except Exception:  # noqa: BLE001
        return str(scratch_path)


def write(record: dict, scratch_path: str | Path, lane: str, root=None) -> dict:
    """把一行账写进**当前承载物**。返回回执（供探针自检，不回显 payload 全文）。

    · 未开启常驻化 → 写 `.scratch`（原样，判据不变）
    · 已开启       → 写 `store/ledger/<lane>.jsonl`（经 ledger_store，append-only + fsync）
    · 常驻化开启但 ledger_store 不可用 → **回落写 .scratch 并在回执里写明降级**
      （不许静默丢行：丢了行，四路对齐判据会变成 INCONCLUSIVE，而没人知道为什么）
    · root 仅为可测性而设：传了就用它当仓库根（验证用临时根，不碰真账本）
    """
    import json

    row = dict(record)
    if persist_enabled():
        store = _ledger_store()
        layer = LAYER_OF.get(lane)
        if store is not None and layer:
            try:
                return store.append(layer, row, root)
            except Exception as exc:  # noqa: BLE001
                fallback = _write_scratch(row, scratch_path)
                fallback["degraded"] = "ledger_store.append 失败，已回落探针态: %s" % str(exc)[:120]
                return fallback
        fallback = _write_scratch(row, scratch_path)
        fallback["degraded"] = "常驻化已开启但 ledger_store 不可用，已回落探针态"
        return fallback
    return _write_scratch(row, scratch_path)


def _write_scratch(record: dict, scratch_path: str | Path) -> dict:
    import json

    path = str(scratch_path)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
    return {"ok": True, "layer": record.get("layer"), "path": path,
            "bytes": len(line.encode("utf-8"))}


def stamp_raw_tid(record: dict, params) -> dict:
    """把权威关联键 `raw_tid` 盖进这一行（《M9判据收口.md》§3.2）。

    判据原文：PASS = 「同一条请求（**同一 `raw_tid`**）在三处都有记录，且
    `frame_bytes_hash` 三处一致」。取值口径**如实**：
      · 帧里真有上游线程 id 才写这个字段；
      · 没有就**不写**（不写 "None"、不填占位符）—— 填了占位符会让
        「没盖到章」看起来像「盖了章」，那比不盖更坏。
    `params` 可以是 dict（取 threadId）或 bytes/str（就地解析 JSON 再取）。
    """
    import json as _json

    data = params
    if isinstance(data, (bytes, bytearray)):
        data = bytes(data).decode("utf-8", "replace").rstrip("\n")
    if isinstance(data, str):
        try:
            data = _json.loads(data)
        except Exception:  # noqa: BLE001
            return record
    if not isinstance(data, dict):
        return record
    src = data.get("params") if isinstance(data.get("params"), dict) else data
    tid = src.get("threadId") or src.get("thread_id")
    if isinstance(tid, str) and tid.strip():
        record["raw_tid"] = tid
    return record


def status() -> dict:
    """当前承载物状态（只读自检，给探针和面板看）。"""
    store = _ledger_store()
    store_dir = None
    if store is not None:
        try:
            store_dir = str(store.ledger_dir())
        except Exception:  # noqa: BLE001
            store_dir = None
    exists = bool(store_dir) and Path(store_dir).is_dir()
    rows = {}
    if exists and store is not None:
        for layer in store.LAYERS:
            try:
                rows[layer] = len(store.tail(layer, 100000))
            except Exception:  # noqa: BLE001
                rows[layer] = None
    return {
        "persist_enabled": persist_enabled(),
        "env": PERSIST_ENV,
        "ledger_store_available": store is not None,
        "store_dir": store_dir,
        "store_dir_exists": exists,
        "rows": rows,
        "note": ("已切到常驻账本 store/ledger/*.jsonl" if persist_enabled()
                 else "仍在探针承载物 .scratch/*_ledger.jsonl（设 %s=1 即切换）" % PERSIST_ENV),
    }


if __name__ == "__main__":
    import json as _json
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass
    print(_json.dumps(status(), ensure_ascii=False, indent=1))
