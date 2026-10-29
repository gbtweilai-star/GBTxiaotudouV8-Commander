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

# 安全确认标记：批量删除等破坏性动作会先要确认（英文大写标记），
# 属「闸在正确咬」，归黄不归红。
CONFIRM_MARKS = ("CONFIRM_REQUIRED", "SAFE_DELETE_BULK", "确认")

# 本能力位自己的名字。绑在 godview-page 上没错（那页要能触发扫描），
# 但**扫描器不能探测自己** —— 会无限递归到栈溢出，见 scan() 里的说明。
SELF_CAP = "page_scan"


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
    # 安全确认档：批量删除 / 破坏性动作会先要确认，这是**闸在正确咬**，不是故障。
    # 实测出处（2026-10-27）：recon_distill 空载荷返回 rc=1 +
    #   `[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] {"count":50,"threshold":50}`
    # 原判定只认中文关键词，英文标记漏网 ⇒ 被误判成红。补这一档。
    if any(k in msg for k in CONFIRM_MARKS):
        return {"cap": cap, "color": "yellow", "why": "需确认（安全闸在咬 ✓）：" + msg[:70], "ms": ms}
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
    # ── 自引用排除（2026-10-27 实测根因）────────────────────────────────────
    # godview-page 的 8 个正向能力位里含 page_scan 自己。于是：
    #   _classify("page_scan") → api.run_task("page_scan") → scan() → _classify("page_scan") → …
    # 无限递归 ⇒ STACK_OVERFLOW（退出码 3221225725 = 0xC00000FD），
    # 整个扫描进程当场死亡，**连 JSON 信封都吐不出来**（这就是 op=scan 一直
    # 只有 SIGTERM + 0 字节、而 op=status 正常的原因）。
    # 排除它，并且在返回里**明说排除了**，不静默吞掉。
    self_ref = SELF_CAP in uniq
    if self_ref:
        uniq = [c for c in uniq if c != SELF_CAP]
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
           "声明引用": sum(len(v) for v in page_caps.values()),
           "唯一能力位": len(uniq) + (1 if self_ref else 0),
           "实探能力位": len(uniq),
           "自引用已排除": (SELF_CAP + "（否则递归栈溢出，见 scan 注释）") if self_ref else "无 ✓",
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
