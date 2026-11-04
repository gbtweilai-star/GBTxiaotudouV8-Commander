# -*- coding: utf-8 -*-
"""route_cache —— 捷径表：同一句话第二次来，直接走上次那条，不再算。

**为什么需要它**：现在每条查询都要跑一遍 L1 规则 + L2 统计（+ 必要时语义）。
同一句话第 100 次和第 1 次一样慢。而"她日常最常说的那几句"其实高度重复
（orchestration-ledger 24,083 次调用只涉及 72 个能力）。这就是纯浪费。

**规则（宁可慢一点，也不许把错路由固化）**：
  · 只有**权重 ≥ 2** 才直达；
  · 高确定性来源（L1 规则 / 视觉裁决）一次 +2 —— 见过一次就够；
  · 统计猜（L2-STAT）一次 +1 —— 要同一句话两次都对才直达；
  · 语义参考（L2-SEM）**不缓存**（未验证的东西不许变成捷径）；
  · 同一句话被路由到**不同能力**时权重衰减，衰减到 0 就换边 —— 防止早期误判永久生效。

归一化只做无歧义的事：去首尾空白、全角转半角、压空格、去掉问号叹号句号。
**不做**同义词归并（那是猜；宁可少命中也不许张冠李戴）。
"""
from __future__ import annotations

import os
import json
import time

_FILE_REL = os.path.join("state", "route_cache.json")
_MAX_ENTRIES = 5000
_HIT_W = 2              # 权重门槛：<2 一律重算
_W_HIGH = 2             # L1 规则 / 视觉裁决
_W_MID = 1              # L2 统计
_W_NONE = 0             # 语义参考：不缓存

_cache = None


def _root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cache_path() -> str:
    return os.path.join(_root(), _FILE_REL)


def normalize(q: str) -> str:
    """只做无歧义的归一化，绝不猜同义词。"""
    s = str(q or "").strip()
    out = []
    for ch in s:
        o = ord(ch)
        if o == 0x3000:                     # 全角空格
            out.append(" ")
        elif 0xFF01 <= o <= 0xFF5E:         # 全角 ASCII 区
            out.append(chr(o - 0xFEE0))
        else:
            out.append(ch)
    s = "".join(out).lower()
    for ch in "？！。，、；：!?.,;:":
        s = s.replace(ch, "")
    return " ".join(s.split())


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    p = cache_path()
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        _cache = d if isinstance(d, dict) else {}
    except Exception:
        _cache = {}
    _cache.setdefault("version", 1)
    _cache.setdefault("entries", {})
    return _cache


def _atomic_write(path: str, text: str, encoding: str = "utf-8") -> None:
    """原子替换：写临时文件 → fsync 落盘 → os.replace 覆盖。

    **为什么必须这样**：`open(path, "w")` 是「先截断再写」，进程在写一半时挂掉或断电，
    留下的是**半截文件** —— 读的人拿到坏 JSON，而文件看起来"还在"，不报错，
    属于最难查的一类故障（本仓 2026-11-04 已因静默失败栽过一次）。
    `os.replace` 在 Windows 和 POSIX 上都保证原子：要么旧文件完整，要么新文件完整。
    """
    d = os.path.dirname(path) or "."
    tmp = os.path.join(d, ".tmp.%s.%d" % (os.path.basename(path), os.getpid()))
    try:
        with open(tmp, "w", encoding=encoding) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())        # 真正落盘：否则断电后可能只留一个空文件
        os.replace(tmp, path)           # 原子替换（同盘内等价于 rename）
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def _save() -> None:
    c = _load()
    ents = c.get("entries") or {}
    if len(ents) > _MAX_ENTRIES:
        # 留权重高的、新的
        keep = sorted(ents.items(),
                      key=lambda kv: (-int(kv[1].get("w") or 0),
                                      -float(kv[1].get("ts") or 0)))[:_MAX_ENTRIES]
        c["entries"] = dict(keep)
    try:
        _atomic_write(cache_path(),
                      json.dumps(c, ensure_ascii=False, separators=(",", ":")))
    except Exception:
        pass


def lookup(query: str) -> dict:
    """查捷径。只认权重达标的条目。"""
    key = normalize(query)
    if not key:
        return {"hit": False, "reason": "空查询"}
    e = (_load().get("entries") or {}).get(key)
    if not e:
        return {"hit": False, "reason": "没走过"}
    w = int(e.get("w") or 0)
    if w < _HIT_W:
        return {"hit": False, "reason": "权重不足（%d/%d），本次重算" % (w, _HIT_W),
                "kind": e.get("kind")}
    return {"hit": True, "kind": e.get("kind"), "w": w,
            "n": int(e.get("n") or 0), "q": e.get("q") or query}


def bump(query: str, kind: str, layer: str = "") -> dict:
    """正常路由跑完后记一笔。权重按**来源确定性**给，不给语义参考记账。"""
    lay = str(layer or "")
    if not kind:
        return {"ok": False, "reason": "缺 kind"}
    if lay.startswith("L2-SEM"):
        return {"ok": True, "skipped": "语义参考不入捷径（未验证）"}
    w_inc = _W_HIGH if (lay.startswith("L1") or lay.startswith("L0")) else _W_MID
    if w_inc <= _W_NONE:
        return {"ok": True, "skipped": "该来源不记账"}

    key = normalize(query)
    if not key:
        return {"ok": False, "reason": "空查询"}
    c = _load()
    ents = c["entries"]
    e = ents.get(key) or {"kind": kind, "w": 0, "n": 0, "ts": 0, "q": str(query)[:120]}
    if e.get("kind") == kind:
        e["w"] = int(e.get("w") or 0) + w_inc
    else:
        # 同一句话被路由到别处：衰减旧边；掉到 0 以下就换边
        e["w"] = int(e.get("w") or 0) - w_inc
        if e["w"] <= 0:
            e["kind"] = kind
            e["w"] = w_inc
    e["n"] = int(e.get("n") or 0) + 1
    e["ts"] = time.time()
    e["q"] = str(query)[:120]
    ents[key] = e
    _save()
    return {"ok": True, "kind": e["kind"], "w": e["w"], "n": e["n"]}


def touch(query: str) -> None:
    """捷径命中时只更新「用过几次 / 最后一次」，**不加权重**。

    为什么不加权重：它已经是捷径了，再加就会让早期条目权重无限膨胀，
    掩盖后来的真实变化。权重只由"重新算过并算对"来增长。
    """
    key = normalize(query)
    if not key:
        return
    e = (_load().get("entries") or {}).get(key)
    if not e:
        return
    e["n"] = int(e.get("n") or 0) + 1
    e["ts"] = time.time()
    _save()


def seed_from_ledger() -> dict:
    """把台账里已有的 (原话 → 实际用了哪个) 真值对**直接种进捷径**（w 给满）。

    这些是"她真的这么调用过"的记录，比任何统计都硬 —— 种进去之后，
    已经用过的说法立刻能直达。
    """
    try:
        from . import route_ledger as RL
        ex = RL.export()
    except Exception as e:                                        # noqa: BLE001
        return {"ok": False, "reason": "%s: %s" % (type(e).__name__, str(e)[:80])}
    n = 0
    for row in ex.get("data") or []:
        q, k = row.get("query"), row.get("chosen")
        if not q or not k:
            continue
        key = normalize(q)
        if not key:
            continue
        c = _load()
        e = c["entries"].get(key) or {"kind": k, "w": 0, "n": 0, "ts": time.time(),
                                      "q": str(q)[:120]}
        if e.get("kind") == k:
            e["w"] = max(int(e.get("w") or 0), _HIT_W)
            e["n"] = int(e.get("n") or 0) + 1
            e["ts"] = time.time()
            c["entries"][key] = e
            n += 1
    _save()
    return {"ok": True, "seeded": n, "total_entries": len(_load()["entries"])}


def stats() -> dict:
    c = _load()
    ents = c.get("entries") or {}
    ready = [k for k, v in ents.items() if int(v.get("w") or 0) >= _HIT_W]
    return {"ok": True, "entries": len(ents), "ready_for_shortcut": len(ready),
            "threshold_w": _HIT_W, "max_entries": _MAX_ENTRIES,
            "file": cache_path(),
            "rule": "L1/视觉 +2 · L2统计 +1 · 语义不记；同一句路由到别处则衰减",
            "top": [{"q": v.get("q"), "kind": v.get("kind"), "w": v.get("w"),
                     "n": v.get("n")}
                    for k, v in sorted(ents.items(),
                                       key=lambda kv: -int(kv[1].get("w") or 0))[:10]]}


def run(op: str = "stats", **kw) -> dict:
    o = str(op or "stats").strip()
    if o in ("stats", "status"):
        return stats()
    if o in ("lookup", "get"):
        return lookup(kw.get("query") or kw.get("q") or "")
    if o in ("bump", "put"):
        return bump(kw.get("query") or kw.get("q") or "",
                    kw.get("kind") or "", kw.get("layer") or "")
    if o in ("seed", "import"):
        return seed_from_ledger()
    if o == "reset":
        global _cache
        _cache = {"version": 1, "entries": {}}
        _save()
        return {"ok": True, "reset": True}
    return {"ok": False, "reason": "未知 op: %s" % o,
            "supported": ["lookup", "bump", "seed", "stats", "reset"]}
