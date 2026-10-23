#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 上帝视角 · 四路账本常驻化（W3 · 产物 5）

把探针态的账本扶正为常驻：``store/ledger/`` 下四路 append-only jsonl。

纪律三条（《W3上帝视角镜像方案.md》§3.2）：
  1. **append-only** —— 只追加，不许改写历史行。
  2. **不记 payload 全文** —— 只记指纹与字节数（与《凭据不离屏律》同源）。
  3. **四路同一帧的 ``frame_bytes_hash`` 必须一致** —— 这是对齐判据的物理证明。

字段名沿用仓内权威名 ``frame_bytes_hash``（**不是** ``frame_sha256_16``——那是历史笔误）。

本模块**只在自己被第一次追加时才建目录/建文件**：空文件会让"看账本"那一格假绿，
没行就是没行，按《反空壳律》如实显示。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

LAYERS = ("panel.send", "bridge", "route.recv", "mock.recv")

LEDGER_FILES = {
    "panel.send": "panel.send.jsonl",
    "bridge": "bridge.jsonl",
    "route.recv": "route.recv.jsonl",
    "mock.recv": "mock.recv.jsonl",
}

HERE = Path(__file__).resolve().parent


def repo_root(start: Path | None = None) -> Path | None:
    """向上找到含 ``gbt_allinone/`` 的仓库根。维度内与晋升后的现实里都能定位。"""
    cur = Path(start or HERE).resolve()
    while True:
        if (cur / "gbt_allinone").is_dir():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent


def ledger_dir(root: Path | None = None) -> Path:
    base = Path(root) if root is not None else repo_root()
    if base is None:
        raise RuntimeError("定位不到仓库根（缺 gbt_allinone/）")
    return base / "gbt_allinone" / "store" / "ledger"


def frame_fingerprint(payload) -> tuple[int, str]:
    """把一帧压成 (字节数, 前 16 位 sha256)。**不返回原文**。"""
    if isinstance(payload, (bytes, bytearray)):
        raw = bytes(payload)
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return len(raw), hashlib.sha256(raw).hexdigest()[:16]


def _row(layer: str, event: str, frame_bytes: int, frame_bytes_hash: str, **extra) -> dict:
    row = {
        "event": event,
        "layer": layer,
        "frame_bytes": int(frame_bytes),
        "frame_bytes_hash": str(frame_bytes_hash),
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    for key, value in extra.items():
        if value is not None:
            row[key] = value
    return row


def append(layer: str, row: dict, root: Path | None = None) -> dict:
    """追加一行。返回回执（含落盘路径与行数），**不回显 payload**。"""
    if layer not in LEDGER_FILES:
        raise ValueError("未知账本层: %s（只认 %s）" % (layer, "/".join(LAYERS)))
    directory = ledger_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / LEDGER_FILES[layer]
    line = json.dumps(row, ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
    return {"ok": True, "layer": layer, "path": str(path), "bytes": len(line.encode("utf-8"))}


def note_roundtrip(round_id: str, payload, route_from: str = "", route_to: str = "",
                   method: str = "", layer_events: dict | None = None,
                   root: Path | None = None) -> dict:
    """一次往返：同一帧落四路，指纹一致——这就是 V2 要的可复算证据。"""
    size, digest = frame_fingerprint(payload)
    events = dict(layer_events or {})
    out = {"round_id": round_id, "frame_bytes": size, "frame_bytes_hash": digest, "wrote": []}
    for layer in LAYERS:
        row = _row(
            layer,
            events.get(layer, "ledger.%s" % layer),
            size,
            digest,
            round_id=round_id,
            route_from=route_from or None,
            route_to=route_to or None,
            method=method or None,
        )
        out["wrote"].append(append(layer, row, root))
    return out


def tail(layer: str, n: int = 20, root: Path | None = None) -> list:
    """只读尾部 N 行。文件不存在 → 返回空表，不建文件。"""
    if layer not in LEDGER_FILES:
        raise ValueError("未知账本层: %s" % layer)
    path = ledger_dir(root) / LEDGER_FILES[layer]
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    rows = []
    for line in lines[-n:]:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:  # noqa: BLE001
            rows.append({"raw": line[:160]})
    return rows


def verify(key: str, root: Path | None = None, key_field: str | None = None,
           layers=None) -> dict:
    """四路对齐判据 —— 逐条照《M9判据收口.md》§3.2 实现。

    权威口径（原文）：
      · 关联键：**`raw_tid`**（上游线程 id），用来把同一条请求串起来
      · 帧指纹：**`frame_bytes_hash`**（8 字节十六进制）
      · `frame_bytes` 用于二次核对 —— **hash 相等而长度不等，按异常处理**
      · PASS         同一条请求（同一 `raw_tid`）在各处都有记录，且 hash 一致
      · FAIL         各处都有记录，但 hash 不一致（帧被改过 / 被截断）
      · INCONCLUSIVE 任一处没有记录 —— 自成一档，不许折算 PASS

    R-H295 更正（原实现的 bug）：原来按 `round_id` 对齐，而
      ① 四路探针**从来不写 `round_id`**；
      ② `raw_tid`（权威关联键）在 `codex_bridge.py` / `panel_server.py` / 三个探针镜像里
         **出现 0 次** —— 即 PASS 条件按构造不可达，这条判据一直是空转的。
    现在：默认按 `raw_tid` 找；找不到该键的行就**如实报 INCONCLUSIVE 并说明缺的是哪个键**，
    绝不拿 `frame_bytes_hash` 当关联键替代 —— §3.1 的判例已经否掉过这条路
    （「上一轮看到的 2 个跨层命中是帧字节恰好相同，不是同一条链」）。
    `key_field` 仅用于显式指定别的键（如历史数据的 `round_id`），默认 None = 按 raw_tid。

    R-H295 · `layers`：**默认仍然是全部四路（严格）**。之所以加这个口，是因为
    权威判据与账本层数**对不上**：M9 §一.2 载明「面板层探针**已被块 4 收口作废**」、
    §一 更直接写了原四层判据「**作废——它在结构上不可能成立**」，存活的是
    **三观测点**（panel_emit / singleton_emit / upstream_recv ↔ panel.send / bridge / mock.recv）。
    于是按四路严格判，`panel.send` 永远填不上 ⇒ 永远 INCONCLUSIVE，判据变成一句空话。
    调用方可以显式传自己认的观测点；回执里会带上 `layers_required` 与 `layers_absent`，
    **谁把哪几路算进判据是可审计的** —— 不许悄悄放宽。
    """
    fields = [key_field] if key_field else ["raw_tid", "round_id"]
    required = list(layers) if layers else list(LAYERS)
    unknown = [x for x in required if x not in LAYERS]
    if unknown:
        return {"verdict": "INVALID", "key": key, "key_field": None,
                "why": "未知账本层：%s（只认 %s）" % (unknown, "/".join(LAYERS)),
                "layers_required": required}
    used_field = None
    hashes: dict[str, list] = {}
    lens: dict[str, list] = {}

    for layer in required:
        hits = []
        for fld in fields:
            hits = [r for r in tail(layer, 500, root) if r.get(fld) == key]
            if hits:
                used_field = used_field or fld
                break
        # R-H295：按**该键下的全部行**比对指纹集合，不是"每路取最后一行"。
        # 实测教训：一条 thread（raw_tid=t1）上会有多条请求（hash 各不相同），
        # 「取最后一行」会把不同请求拿来互比 —— 那是在比两条不同的请求，结论没意义。
        hashes[layer] = sorted(str(r.get("frame_bytes_hash")) for r in hits
                               if r.get("frame_bytes_hash"))
        lens[layer] = sorted(int(r.get("frame_bytes")) for r in hits
                             if r.get("frame_bytes") is not None)

    empty = [k for k, v in hashes.items() if not v]
    if empty:
        return {
            "verdict": "INCONCLUSIVE", "key": key, "key_field": used_field,
            "missing": empty, "hashes": hashes, "rows": {k: len(v) for k, v in hashes.items()},
            "layers_required": required,
            "layers_absent": [x for x in LAYERS if x not in required],
            "note": ("缺观测点 = 没验成，必须重跑；不许折算 PASS。"
                     + ("" if used_field else
                        "（四路都没有带 raw_tid/round_id 的行 —— 关联键没被任何观测点盖章，"
                        "这不是「一致」，是「没得比」）")),
        }

    # 该键下各路的帧指纹集合必须逐条一致
    unique = {tuple(v) for v in hashes.values()}
    if len(unique) != 1:
        return {"verdict": "FAIL", "key": key, "key_field": used_field,
                "hashes": hashes, "rows": {k: len(v) for k, v in hashes.items()},
                "layers_required": required,
                "note": "该键下各路的帧指纹集合不一致（帧在链路上被改过 / 被截断 / 漏记）"}

    # 指纹集合一致 → 再按 frame_bytes 二次核对（权威口径：长度不等按异常处理）
    if len({tuple(v) for v in lens.values()}) != 1:
        return {"verdict": "FAIL", "key": key, "key_field": used_field,
                "hashes": hashes, "frame_bytes": lens,
                "layers_required": required,
                "note": "指纹一致但 frame_bytes 不等 —— 按异常处理（二次核对不过）"}

    return {"verdict": "PASS", "key": key, "key_field": used_field,
            "hashes": hashes[required[0]], "rows": {k: len(v) for k, v in hashes.items()},
            "frame_bytes": lens, "layers_required": required}


def self_test(root: Path | None = None) -> dict:
    """在临时目录里真跑一次"落四路 → 校验对齐"，**不碰真账本**。"""
    with tempfile.TemporaryDirectory(prefix="gbt_ledger_self_test_") as tmp:
        fake = Path(tmp)
        (fake / "gbt_allinone" / "store").mkdir(parents=True, exist_ok=True)
        payload = {"method": "initialize", "req_id": 1, "probe": "w3-self-test"}
        res = note_roundtrip("selftest", payload, route_from="panel", route_to="mock", root=fake)
        verdict = verify("selftest", root=fake)
        rows = {layer: len(tail(layer, 10, root=fake)) for layer in LAYERS}
    return {"ok": verdict["verdict"] == "PASS", "roundtrip": res, "verdict": verdict, "rows": rows}


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass
    print(json.dumps(self_test(), ensure_ascii=True))
