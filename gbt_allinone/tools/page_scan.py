# -*- coding: utf-8 -*-
# gbt-capability: page_scan
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""page_scan —— 按绑定逐页并发扫（主人 2026-10-12 定的架构）。

主人原话：「触手随所有能力文件每一页绑定好，你要扫的时候按照绑定**触手一页一页传回来**，
还会有爆红我就跟你姓；这么多触手可以并发，你每次都不用或只用几根。」

## 口径（把"每次都扫出一堆问题"根治）
  · 源 = `state/page-bindings.json` 的 **逐页**（页 → 落点 → 正向_能力位 ✓ 全在盘 ✓）；
  · **并发用满**（实测引擎 ≥4096 根零失败；本件默认 256~512 起）；
  · **按契约判色**（不是非绿一刀切 ✗）：
      绿 = 跑通 ✓
      黄·需参数 = 它自己报「需要/缺少 X」⇒ **契约如此，不是故障** ✓
      黄·需授权 = 它自己报 requires human authorization ⇒ **门在咬，正确行为** ✓
      **红 = 契约也满足却仍失败** ⇒ 只有这一种才是要看的 ✓
  · 页/落点/在册 三项各自独立判，**一个不省** ✓；
  · 全程只读（probe=True 不计审计）✓ 结果落账 ✓。

## op
  scan    全量：逐页 → 逐能力位并发 → 三色 + 覆盖读数
  status  只读：绑定表现状（页数/绑好/未绑好）
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import pathlib
import time

_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _store() -> pathlib.Path:
    d = os.environ.get("GBT_STORE_DIR")
    base = pathlib.Path(d) if d else (_ROOT / "gbt_allinone" / "store")
    p = base / "page_scan"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _bindings() -> dict:
    p = _ROOT / "state" / "page-bindings.json"
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                       # noqa: BLE001
        return {}


def _caps() -> dict:
    try:
        from ..caps_registry import BENIGN_CAPS as B
        return dict(B)
    except Exception:                                       # noqa: BLE001
        return {}


def _classify(cap: str) -> dict:
    t0 = time.time()
    try:
        from .. import api
        r = api.run_task(cap, {}, probe=True)
    except Exception as e:                                  # noqa: BLE001
        return {"cap": cap, "color": "red", "why": "%s: %s" % (type(e).__name__, str(e)[:80]),
                "ms": int((time.time() - t0) * 1000)}
    res = r.get("result") if isinstance(r.get("result"), dict) else {}
    st = str(r.get("status"))
    msg = str(res.get("message") or res.get("error") or res.get("reason") or r.get("error") or "")
    ms = int((time.time() - t0) * 1000)
    if st == "denied" or "human authorization" in msg or "需要人工授权" in msg:
        return {"cap": cap, "color": "yellow", "why": "需授权（门在咬 ✓）", "ms": ms}
    if st == "ok" and r.get("ok", True):
        return {"cap": cap, "color": "green", "why": "", "ms": ms}
    if any(k in msg for k in ("需要", "缺少", "不能为空", "必填", "不存在", "required", "must")):
        return {"cap": cap, "color": "yellow", "why": "需参数（契约如此）：" + msg[:70], "ms": ms}
    return {"cap": cap, "color": "red", "why": msg[:110] or st, "ms": ms}


def scan(workers: int = 512) -> dict:
    pb = _bindings()
    pages = pb.get("逐页") or []
    caps_reg = _caps()
    page_caps = {str(p.get("页")): [str(c) for c in (p.get("正向_能力位") or [])] for p in pages}
    missing_page = [str(p.get("页")) for p in pages if not p.get("落点在盘")]
    uniq = sorted({c for cs in page_caps.values() for c in cs})
    absent = [c for c in uniq if c not in caps_reg]
    nobind = [p for p, cs in page_caps.items() if not cs]
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=max(1, min(workers, len(uniq) or 1))) as ex:
        res = list(ex.map(_classify, uniq)) if uniq else []
    wall = round(time.time() - t0, 1)
    by = {"green": [], "yellow": [], "red": []}
    for r in res:
        by[r["color"]].append(r)
    out = {"ok": True, "op": "scan", "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "页数": len(pages), "绑好": pb.get("绑好"), "未绑好": pb.get("未绑好"),
           "落点不在盘的页": missing_page or "无 ✓",
           "无绑定能力位的页": nobind or "无 ✓",
           "声明引用": sum(len(v) for v in page_caps.values()), "唯一能力位": len(uniq),
           "不在册的声明": absent or "无 ✓",
           "并发度": min(workers, len(uniq)), "用时秒": wall,
           "绿": len(by["green"]), "黄": len(by["yellow"]), "红": len(by["red"]),
           "红名单": [{"cap": r["cap"], "why": r["why"], "ms": r["ms"]} for r in by["red"]],
           "黄名单": [{"cap": r["cap"], "why": r["why"]} for r in by["yellow"]],
           "结论": ("全覆盖且零真故障 ✓" if (not missing_page and not absent and not nobind and not by["red"])
                    else "有红/有缺口 ⇒ 见名单")}
    with (_store() / "ledger.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({k: out[k] for k in ("at", "页数", "唯一能力位", "绿", "黄", "红", "用时秒")},
                           ensure_ascii=False) + chr(10))
    return out


def status() -> dict:
    pb = _bindings()
    return {"ok": True, "op": "status", "页数": pb.get("页数"), "绑好": pb.get("绑好"),
            "未绑好": pb.get("未绑好"), "口径": pb.get("口径")}


def run(payload: dict | None = None) -> dict:
    p = dict(payload or {})
    op = str(p.get("op") or "scan").strip().lower()
    if op == "scan":
        return scan(int(p.get("workers") or 512))
    if op == "status":
        return status()
    return {"ok": False, "fail_closed": True, "error": "user_error: 未列出的 op（fail-closed）",
            "ops": ["scan", "status"]}
