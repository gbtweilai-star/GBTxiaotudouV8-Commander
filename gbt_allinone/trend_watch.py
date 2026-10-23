# -*- coding: utf-8 -*-
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 · 爆火作品观察与用户偏好台账（Owner 2026-09-19）。

Owner 原话：「调用触手就要观察每日所有的，爆火作品观察细微点，
至少要知道用户喜欢什么样的东西」。

为什么单独立表：话题追踪管的是"我关心的东西变没变"（产物=动态，会过期）；
这张表管的是"**用户喜欢什么**"（产物=偏好条目，是能反过来指导创作的资产）。
两件事，两张表，不互相冒充。

三条纪律：
  1. 不新建常驻进程 —— 观测挂在现成心跳上，本模块只提供落表/读表/观测计划。
  2. 不编造数据 —— 拿不到就如实报 needs_source；没有真实观测不许写台账。
  3. 写入前查指纹 —— 同一（作品·平台·偏好）不落第二条；不靠事后删。

观测链（技能名取自盘上实况 catalog 73 项，本模块不复制任何技能实现）：
  youtube-watcher → 看作品；video-transcript-downloader → 拿逐字稿挖细微点；
  reddit-readonly → 看网友真实反应；web-search-plus → 查热度/热搜。
"""
from __future__ import annotations

import hashlib
import io
import json
import time
from pathlib import Path

_BASE = Path(__file__).resolve().parent
# 🔴 2026-09-26 修：原来硬编码包内 store —— 绕开 GBT_STORE_DIR 单一来源（隔离测试会写脏真实 store，
#    同 qiankun O35 已修过的病）。现在走 _paths.STORE_DIR，环境可隔离。
from . import _paths as _gbt_paths
_STORE = Path(_gbt_paths.STORE_DIR) / "preferences"
_LEDGER = _STORE / "user_preference_ledger.jsonl"

# 触发词唯一真相：话题追踪那边 import 这一份，不抄第二份。
FAMILY = ("爆火", "爆款", "热门", "热搜", "点赞高", "涨粉快",
          "用户喜欢什么", "什么受欢迎", "偏好", "用户爱看")

OBSERVE_CHAIN = ("youtube-watcher", "video-transcript-downloader",
                 "reddit-readonly", "web-search-plus")

FIELDS = ("work", "platform", "heat", "detail", "preference", "at")


def _fp(row: dict) -> str:
    """指纹：作品·平台·偏好 三件套（不含时间戳，否则同一条永远算新的）。"""
    key = "%s|%s|%s" % (row.get("work"), row.get("platform"), row.get("preference"))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _rows() -> list:
    if not _LEDGER.is_file():
        return []
    out = []
    with io.open(_LEDGER, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:  # noqa: BLE001
                continue
    return out


def observe(work: str = "", platform: str = "", heat=None, detail: str = "",
            preference: str = "") -> dict:
    """落一条偏好观测。写入前查指纹：重复观测如实报 duplicate，不落第二条。"""
    body = " ".join(str(work or "").split())
    pref = " ".join(str(preference or "").split())
    if not body or not pref:
        return {"ok": False, "error": "缺 work 或 preference：没有真实观测就不许写台账"}
    row = {"work": body[:200], "platform": str(platform or "")[:60],
           "heat": heat, "detail": " ".join(str(detail or "").split())[:400],
           "preference": pref[:200], "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    row["fp"] = _fp(row)
    if row["fp"] in {r.get("fp") for r in _rows()}:
        return {"ok": True, "wrote": False, "duplicate": True, "fp": row["fp"],
                "note": "同一（作品·平台·偏好）已有记录 —— 写入前查指纹，不靠事后删"}
    _STORE.mkdir(parents=True, exist_ok=True)
    before = _LEDGER.stat().st_size if _LEDGER.is_file() else 0
    with io.open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return {"ok": True, "wrote": True, "row": row,
            "bytes": {"before": before, "after": _LEDGER.stat().st_size},
            "note": "追加式：不覆盖、不删；下次 ledger 就能读到"}


def ledger(limit: int = 20) -> dict:
    """读台账（最近 N 条）。"""
    rows = _rows()
    return {"ok": True, "path": str(_LEDGER), "count": len(rows),
            "fields": list(FIELDS), "recent": rows[-max(1, int(limit)):],
            "note": "偏好条目是能反过来指导创作的资产，不是一次性动态。"}


def digest(limit: int = 200) -> dict:
    """偏好汇总：把逐条观测收成可数摘要（不写盘、不编）。"""
    rows = _rows()[-max(1, int(limit)):]
    by_platform, prefs = {}, {}
    for r in rows:
        p = str(r.get("platform") or "未标平台")
        by_platform[p] = by_platform.get(p, 0) + 1
        pf = str(r.get("preference") or "").strip()
        if pf:
            prefs[pf] = prefs.get(pf, 0) + 1
    top = sorted(prefs.items(), key=lambda kv: -kv[1])[:10]
    return {"ok": True, "samples": len(rows), "by_platform": by_platform,
            "top_preferences": [{"preference": k, "count": v} for k, v in top],
            "note": "读数：样本数=台账真实行数；样本 0 时这里是空的，不编偏好。"}


def plan() -> dict:
    """观测计划：挂现成心跳，零新增进程；技能逐一对盘校验，缺了如实报 gaps。"""
    try:
        from . import topic_watch as TW
        avail = {x["skill"] for x in (TW.catalog().get("skills") or [])}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"技能盘不可读: {type(exc).__name__}"}
    gaps = [s for s in OBSERVE_CHAIN if s not in avail]
    return {"ok": not gaps, "chain": list(OBSERVE_CHAIN), "gaps": gaps,
            "carrier": "现成心跳（HEARTBEAT.md 定时腿；本模块不含任何进程原语）",
            "writes_to": str(_LEDGER), "fields": list(FIELDS), "family": list(FAMILY),
            "note": "观测要出网取平台数据 ⇒ 属授权范围；未授权时不许编数据填台账。"}


def run(op: str = "status", **kw) -> dict:
    """能力入口（caps_registry: trend_watch）。"""
    op = str(op or "status").strip().lower()
    if op in ("status", "plan"):
        p = plan()
        p["ledger"] = ledger(5)
        p["family"] = list(FAMILY)
        p["ops"] = ["observe", "ledger", "digest", "plan", "status"]
        return p
    if op == "observe":
        return observe(kw.get("work"), kw.get("platform"), kw.get("heat"),
                       kw.get("detail"), kw.get("preference"))
    if op in ("ledger", "list"):
        return ledger(kw.get("limit", 20))
    if op in ("digest", "summary"):
        return digest(kw.get("limit", 200))
    return {"ok": False, "error": f"未知动作: {op}（可用 observe / ledger / digest / plan）"}
