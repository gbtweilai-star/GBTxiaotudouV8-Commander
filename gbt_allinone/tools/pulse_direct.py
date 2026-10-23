# -*- coding: utf-8 -*-
# gbt-capability: pulse_direct
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""pulse_direct —— 脉冲直达（主人令 2026-10-11 · 逐字）。

主人原话：「把**脉冲**给大模型，让她把所有的能力按照**触手双向绑定**的部署方式进行**急速运行**，
以及可以**省去不必要的多绕** —— 好比如本来的向前跨一步就到的东西，结果跑了一大圈才跨那一步」。

⚠️ 与既有的 `tools/pulse.py`（万能插脉冲 · 每日情报调研执行层 · Owner 2026-10-03 批准）**不是一件东西**：
   那一件跑"每日调研链"；本件只管**一步直达**（意图 → 该用哪个能力位 → 那一条命令），
   并把「绕了几个弯」变成可量读数。**不覆盖、不合并**（判据/件只有一份，但这两份各管一摊）。

## 干什么
  一句自然语言意图 ⇒ **一步**解析到该用哪个能力位 ⇒ 给出**那一条命令**与**要过的门**，
  并把 hops（绕弯数）写进账：
    · hops=1 ⇒ 直接命中（跨一步就到 ✓）
    · hops=2 ⇒ 命中的是"页面/包装"中间层 ⇒ 还得再走一步（这一跳该收敛掉 ✓）
    · hops=0 ⇒ 没命中（如实报，**不许编** ✓）
  另一份 op=audit 读回"一步命中率"⇒ 越直越高 ✓（把"省多绕"变成可量的事 ✓）。

## 三根支柱（都现读，不写第二份）
  ① 能力位册 `caps_registry`   ② 双向绑定 `state/cap-bindings.json` + `state/page-caps.json`（显式申报）
  ③ 唯一门 `run_task` / `five-dim.py cap <kind>`

## 铁律
  · 不许编：没命中就 hops=0；命中的名字必须是册里真有的；
  · 读数说话：每次 resolve 落账（意图/命中/hops/依据）；
  · 只报不跑：本件只解析与给命令，真执行仍走唯一门（门照样咬 ✓）。
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import time

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_STOP = {"的", "了", "把", "给", "让", "她", "他", "我", "你", "和", "与", "在", "是", "有", "要", "就", "都", "不", "也", "这", "那", "一个", "一下", "怎么", "什么", "如何", "可以", "现在", "我们", "能力"}


def _store() -> pathlib.Path:
    d = os.environ.get("GBT_STORE_DIR")
    base = pathlib.Path(d) if d else (_ROOT / "gbt_allinone" / "store")
    p = base / "pulse_direct"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _ledger(row: dict) -> None:
    with (_store() / "ledger.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + chr(10))


def _tokens(s: str) -> set:
    out = set()
    for t in re.findall(r"[A-Za-z_]{3,}|[\u4e00-\u9fff]{2,4}", str(s or "")):
        if t.lower() not in _STOP:
            out.add(t.lower())
    return out


def _caps() -> dict:
    try:
        from ..caps_registry import BENIGN_CAPS as B
        return dict(B)
    except Exception:                                       # noqa: BLE001
        return {}


def _bindings() -> tuple:
    cb, pc = {}, {}
    try:
        p = _ROOT / "state" / "cap-bindings.json"
        if p.is_file():
            cb = json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                       # noqa: BLE001
        cb = {}
    try:
        p = _ROOT / "state" / "page-caps.json"
        if p.is_file():
            pc = json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                       # noqa: BLE001
        pc = {}
    return cb, pc


_PAGEISH = ("html", "page", "pages", "board", "panel", "deck", "view", "页面", "看板", "面板")
_SYN = {"蓝牙": ("blue", "bt"), "音频": ("audio", "voice", "music"), "图": ("image", "art", "vision"),
        "视频": ("video", "film"), "部署": ("deploy", "release", "pipeline"), "推": ("push", "publish", "git"),
        "仓": ("repo", "git", "publish"), "记忆": ("memory", "vault"), "密钥": ("key",), "扫": ("scan",)}


def resolve(intent: str) -> dict:
    caps = _caps()
    cb, pc = _bindings()
    tk = _tokens(intent)
    for k, v in list(_SYN.items()):
        if k in str(intent):
            tk.update(v)
    scored = []
    for kind, info in caps.items():
        d = info if isinstance(info, str) else json.dumps(info, ensure_ascii=False)
        hay = (str(kind) + " " + d).lower()
        score = 0
        for t in tk:
            if t in str(kind).lower():
                score += 5
            elif t in hay:
                score += 2
        if score:
            scored.append((score, str(kind)))
    scored.sort(reverse=True)
    hit = scored[0][1] if scored else None
    hops, why = 0, "没命中：册里没有能接这句的能力位（如实报，不编）"
    if hit:
        hops, why = 1, "直接命中能力位（跨一步就到）"
        if any(w in hit.lower() for w in _PAGEISH):
            hops, why = 2, "命中的是页面/包装层 ⇒ 还得再走一步到真能力位（这一跳该收敛掉）"
    cmd = ("py -3.14 -X utf8 tools/codex-scripts/five-dim.py cap %s '{...}'" % hit) if hit else None
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "intent": str(intent)[:120], "hit": hit,
           "hops": hops, "why": why, "top": [h for _, h in scored[:5]]}
    _ledger(row)
    return {"ok": True, "intent": str(intent)[:120], "hit": hit, "hops": hops, "why": why,
            "one_step_cmd": cmd, "alternatives": [h for _, h in scored[1:5]],
            "bindings": {"cap_bindings_loaded": bool(cb), "page_caps_loaded": bool(pc),
                         "pages_declared": len(pc) if isinstance(pc, dict) else 0},
            "note": "只解析与给命令；真执行仍走唯一门（门照样咬）"}


def audit(limit: int = 200) -> dict:
    p = _store() / "ledger.jsonl"
    if not p.is_file():
        return {"ok": True, "observed": 0, "note": "无观测"}
    rows = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        if line.strip():
            try:
                rows.append(json.loads(line))
            except Exception:                               # noqa: BLE001
                pass
    h1 = sum(1 for r in rows if r.get("hops") == 1)
    return {"ok": True, "observed": len(rows), "一步命中": h1,
            "多绕": sum(1 for r in rows if (r.get("hops") or 0) > 1),
            "没命中": sum(1 for r in rows if not r.get("hops")),
            "一步命中率": round(h1 / max(len(rows), 1), 3),
            "verdict": "越直越好（一步命中率越高越好）"}


def run(payload: dict | None = None) -> dict:
    p = dict(payload or {})
    op = str(p.get("op") or "resolve").strip().lower()
    if op == "resolve":
        return resolve(str(p.get("intent") or p.get("q") or ""))
    if op == "audit":
        return audit(int(p.get("limit") or 200))
    return {"ok": False, "fail_closed": True, "error": "user_error: 未列出的 op（fail-closed）",
            "ops": ["resolve", "audit"]}
