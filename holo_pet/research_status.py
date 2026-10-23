# gbt-capability: filesystem
"""调研信源的采集状态判定 —— 声明 / 实测 / 水位 三处分开读，判定只在本文件。

风哥 2026-09-18 判据 D：「research 源某次采集失败」。
本文件就是这条判据的落点：单源采集失败必须能被读出来，且**不许**退化成
"没这回事"（该源从列表里消失），也**不许**变成绿。

三层（谁写、谁读，写死在 state/README.md）：

    声明层  sources.json.research[]   人写：  "我要用这个源"
    实测层  state/runs/<id>.json      采集器写：最近一次采集的结局（ok / failed）
    水位层  state/last_seen.json      采集器写：**只记最后一次成功**的时刻

四条硬规矩：

1. 失败 != 没这回事，也 != 绿。失败态必须带出上一次成功的水位（有的话）——
   水位是防漏检用的，一次失败不许把它抹掉。
2. 读不出来 = 这轮不知道。状态文件坏掉时不许退回「未采集」，也不许当绿 ——
   本机事实优先于人的声明（与门禁「读实测不读声明」同源）。
3. 单源失败不连坐：判定逐源独立，别的源的结论一个字节都不许变。
4. `enabled` 只是意愿声明：显式 false -> 显示「未启用」，且不计入采集失败。
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

try:  # 同目录模块：面板与测试都把 holo_pet 放进 sys.path
    from social_platforms import ENABLED_LABEL_DISABLED
except ImportError:  # pragma: no cover —— 仅在按文件路径裸导入时走到
    ENABLED_LABEL_DISABLED = "未启用"

STATE_UNREADABLE = "unreadable"
STATE_DISABLED = "disabled"
STATE_FAILED = "failed"
STATE_NEVER_RUN = "never_run"
STATE_STALE = "stale"
STATE_OK = "ok"

# 六态互斥，优先级写死在 evaluate_source 的分支顺序里：
#   unreadable > disabled > failed > never_run / stale / ok
STATE_LABELS = {
    STATE_UNREADABLE: "状态文件不可信",
    STATE_DISABLED: ENABLED_LABEL_DISABLED,
    STATE_FAILED: "最近采集 · 失败",
    STATE_NEVER_RUN: "已登记 · 未采集",
    STATE_STALE: "已登记 · 采集过期",
    STATE_OK: "最近采集 · 正常",
}

# 严重度 = 机器可读的「标红」。面板与 run_report 都读它，
# 不再靠"文案里有没有『失败』两个字"来判颜色。
SEVERITY = {
    STATE_UNREADABLE: "red",
    STATE_FAILED: "red",
    STATE_STALE: "warn",
    STATE_NEVER_RUN: "neutral",
    STATE_DISABLED: "neutral",
    STATE_OK: "ok",
}

INTERVAL_SECONDS = {"daily": 86400, "weekly": 604800}
DEFAULT_INTERVAL_SECONDS = 86400

# 过期判据：**漏一次不算，漏两次算**。
# 采集器按 daily_at 定点跑，跑完那一刻 age 已经贴近 1 个周期，若用 1x 判据，
# 每次正常跑完都会立刻显示"过期"。所以日度源 48h 没成功才算过期，周度源 14 天。
GRACE_MULTIPLIER = 2

# 汇总口径：报警的排前面。disabled 排最后 —— 它是声明，不是故障。
COUNT_ORDER = (
    (STATE_FAILED, "个采集失败"),
    (STATE_UNREADABLE, "个状态文件不可信"),
    (STATE_STALE, "个采集过期"),
    (STATE_OK, "个正常"),
    (STATE_NEVER_RUN, "个已登记 · 未采集"),
    (STATE_DISABLED, "个未启用"),
)


def interval_seconds(value: Any) -> tuple[int, bool]:
    """返回 (秒数, 是否登记了周期)。未登记 -> 按日度判定，并如实带出 known=False。"""
    key = str(value or "").strip().lower()
    if key in INTERVAL_SECONDS:
        return INTERVAL_SECONDS[key], True
    return DEFAULT_INTERVAL_SECONDS, False


def parse_time(value: Any) -> float | None:
    """容忍 epoch 数字与 ISO 字符串。读不出来 -> None，调用方按「没有水位」处理。

    无时区的字符串按**本机本地时间**解释（水位文件是机器本地写的），
    不做 UTC 假定 —— 那会把 age 整体平移一个时区，足以把 fresh 误判成过期。
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        pass
    text = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).timestamp()
        except ValueError:
            continue
    return None


def describe_age(seconds: int | None) -> str:
    """人读时长。用于 hint，不参与任何判定。"""
    if seconds is None:
        return "未知"
    if seconds < 60:
        return "%d 秒" % seconds
    if seconds < 3600:
        return "%d 分钟" % (seconds // 60)
    if seconds < 86400:
        return "%d 小时" % (seconds // 3600)
    return "%d 天" % (seconds // 86400)


def read_watermark(value: Any) -> tuple[float | None, int | None]:
    """水位条目两种形状都收：字符串/数字 = 时刻；对象 = {at, items}。

    对象里的 `items` 是**上一次成功时**的条数 —— 它是历史，只许进 history。
    这条是判据 E「不沿用旧值」的机器边界：调用方拿不到"把历史条数当本次值"的机会。
    """
    if isinstance(value, dict):
        raw = value.get("at")
        if raw is None:
            raw = value.get("checked_at")
        if raw is None:
            raw = value.get("finished_at")
        items = value.get("items")
        if isinstance(items, bool) or not isinstance(items, int):
            items = None
        return parse_time(raw), items
    return parse_time(value), None


def _watermark_raw(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("at", "checked_at", "finished_at"):
            if value.get(key) is not None:
                return str(value[key])
        return ""
    return "" if value is None else str(value)


def _close(block: dict, state: str, hint: str) -> dict:
    """六态收口：state / status_label / severity / hint 一处写，分支不许各写各的。"""
    block["state"] = state
    block["status_label"] = STATE_LABELS[state]
    block["severity"] = SEVERITY[state]
    block["hint"] = hint
    return block


def read_last_seen(path: str | Path) -> tuple[dict, str, bool]:
    """水位层：**只记最后一次成功**。返回 (映射, 读失败原因, 文件是否存在)。"""
    target = Path(path)
    if not target.is_file():
        return {}, "", False
    try:
        doc = json.loads(target.read_text(encoding="utf-8"))
    except OSError as exc:
        return {}, "last_seen.json 不可读：%s" % str(exc)[:120], True
    except ValueError as exc:
        return {}, "last_seen.json 不是合法 JSON：%s" % str(exc)[:120], True
    if not isinstance(doc, dict):
        return {}, "last_seen.json 顶层不是对象", True
    return doc, "", True


def read_runs(run_dir: str | Path) -> tuple[dict, dict, bool]:
    """实测层：state/runs/<id>.json。

    返回 (id -> 文档, id -> 读失败原因, 目录是否存在)。
    单个文件坏掉只影响那一个源，且**必须**留下原因（不许静默忽略）。
    """
    folder = Path(run_dir)
    docs: dict[str, Any] = {}
    errors: dict[str, str] = {}
    if not folder.is_dir():
        return docs, errors, False
    for path in sorted(folder.glob("*.json")):
        sid = path.stem
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            errors[sid] = "读不出来：%s" % str(exc)[:120]
            continue
        except ValueError as exc:
            errors[sid] = "不是合法 JSON：%s" % str(exc)[:120]
            continue
        if not isinstance(doc, dict):
            errors[sid] = "顶层不是对象"
            continue
        docs[sid] = doc
    return docs, errors, True


def _failure_detail(run_doc: dict) -> str:
    parts = []
    http = run_doc.get("http")
    if isinstance(http, int) and not isinstance(http, bool):
        parts.append("HTTP %d" % http)
    reason = str(run_doc.get("reason") or "").strip()
    if reason:
        parts.append(reason[:160])
    if not parts:
        return ""
    return "（%s）" % " · ".join(parts)


def evaluate_source(
    row: dict,
    *,
    last_seen_value: Any = None,
    run_doc: dict | None = None,
    run_error: str = "",
    now: float | None = None,
) -> dict:
    """单个调研信源的六态判定。纯函数：不读盘、不看别的源，所以不会连坐。

    出口分两个袋子，**不许混**（判据 E「不沿用旧值」）：

        this_run —— 本次采集的值，只来自 state/runs/<id>.json；没有就 present=False / None。
        history  —— 历史水位，只来自 state/last_seen.json（最后一次成功）。

    history 里的数字（水位写成 {at, items} 时的 items）**永远不许**流进 this_run：
    本次没采到就是"未知"，不是"和上次一样"。
    """
    stamp = time.time() if now is None else float(now)
    sid = str(row.get("id") or "").strip().lower()
    label = str(row.get("name") or sid)
    seconds, interval_known = interval_seconds(row.get("interval"))

    enabled_declared = "enabled" in row
    enabled = bool(row.get("enabled"))
    ok_at, ok_items = read_watermark(last_seen_value)
    ok_age = None if ok_at is None else max(0, int(stamp - ok_at))
    run_present = isinstance(run_doc, dict)
    outcome = None
    run_at = None
    if run_present:
        outcome = str(run_doc.get("outcome") or "").strip().lower() or None
        run_at = parse_time(run_doc.get("finished_at") or run_doc.get("started_at"))

    def _this(key):
        """本次值取值口：没有本次记录一律 None —— 不回落、不沿用。"""
        return run_doc.get(key) if run_present else None

    block: dict = {
        "id": sid,
        "name": label,
        "kind": str(row.get("kind") or ""),
        "transport": str(row.get("transport") or ""),
        "endpoint": str(row.get("endpoint") or ""),
        "probe": str(row.get("probe") or ""),
        "note": str(row.get("note") or ""),
        "interval": str(row.get("interval") or ""),
        "interval_seconds": seconds,
        "interval_known": interval_known,
        "enabled_declared": enabled_declared,
        "enabled": enabled,
        # 意愿声明：只在**显式** false 时印「未启用」，与社交侧同口径。
        "enabled_label": ENABLED_LABEL_DISABLED if (enabled_declared and not enabled) else "",
        # 兼容层（原字段语义不变）：这几个永远只反映本次。
        "outcome": outcome or "",
        "http": _this("http"),
        "reason": (str(run_doc.get("reason") or "") if run_present else ""),
        "items": _this("items"),
        "attempts": _this("attempts"),
        "run_present": run_present,
        "run_file": ("state/runs/%s.json" % sid),
        "run_error": run_error,
        # 本次值（袋子一）
        "this_run": {
            "present": run_present,
            "source": ("state/runs/%s.json" % sid) if run_present else "",
            "outcome": outcome or "",
            "http": _this("http"),
            "reason": (str(run_doc.get("reason") or "") if run_present else ""),
            "items": _this("items"),
            "attempts": _this("attempts"),
            "finished_at": (str(run_doc.get("finished_at") or run_doc.get("started_at") or "")
                            if run_present else ""),
            "age_seconds": (None if run_at is None else max(0, int(stamp - run_at))),
        },
        # 历史（袋子二）：水位。只报时间与"当时的条数"，且明确标成历史。
        "history": {
            "source": "state/last_seen.json",
            "watermark_at": _watermark_raw(last_seen_value),
            "watermark_age_seconds": ok_age,
            "watermark_age_label": describe_age(ok_age) if ok_age is not None else "",
            "items": ok_items,
            "label": "历史（上一次成功）",
        },
        "last_ok_at": _watermark_raw(last_seen_value),
        "last_ok_age_seconds": ok_age,
        "last_ok_age_label": describe_age(ok_age) if ok_age is not None else "",
        "last_run_at": (str(run_doc.get("finished_at") or run_doc.get("started_at") or "")
                        if run_present else ""),
        "last_run_age_seconds": (None if run_at is None else max(0, int(stamp - run_at))),
        "watermark_present": ok_at is not None,
        # 本次值到底从哪来：没有本次记录就是空串，别让人以为它有值。
        "values_from": "state/runs" if run_present else "",
    }

    # 优先级 1：读不出来 = 这轮不知道。本机事实优先于人的声明 ——
    # 连 enabled:false 也压不住它（读不出来这件事本身最要紧）。
    if run_error:
        return _close(block, STATE_UNREADABLE,
                      "%s 读不出来（%s）：本次结论不可信。先修这个文件，"
                      "不许按「未采集」处理。" % (block["run_file"], run_error))

    # 优先级 2：意愿声明。显式 false -> 未启用；它不是故障，不参与采集统计。
    if enabled_declared and not enabled:
        tail = ""
        if outcome == "failed":
            tail = "（登记文件里还留着上一次采集结局：失败）"
        elif outcome == "ok":
            tail = "（登记文件里还留着上一次采集结局：成功）"
        return _close(block, STATE_DISABLED,
                      "登记表声明本机目前不启用这个源：不采集、不计入失败。%s" % tail)

    # 优先级 3：失败。失败不清水位 —— 有上一次成功就一并带出来（但只放在历史里）。
    if outcome == "failed":
        detail = _failure_detail(run_doc or {})
        if ok_age is None:
            return _close(block, STATE_FAILED,
                          "最近一次采集失败%s；本机没有成功水位 —— 这个源从未成功采过，"
                          "当前没有可用的历史。" % detail)
        return _close(block, STATE_FAILED,
                      "最近一次采集失败%s；上一次成功在 %s 前。失败不清水位："
                      "防漏检水位仍是那一次成功（属历史，不是本次的条数）。"
                      % (detail, describe_age(ok_age)))

    # 优先级 4：从未采过。这是"没采过"，不是"采集失败"，也不是绿。
    if ok_age is None and not run_present:
        return _close(block, STATE_NEVER_RUN,
                      "登记表里有它，本机还没有采过（state/last_seen.json 没有它的水位）。"
                      "没采过 != 失败，也 != 绿。")

    # 优先级 5：自称成功但没写水位 / 水位超出采集周期 —— 都按过期（没有时间戳 = 过期）。
    if ok_age is None:
        return _close(block, STATE_STALE,
                      "最近一次采集自称成功，但 state/last_seen.json 没有它的水位："
                      "没有时间戳 = 过期（state/README.md 第 2 条）。成功必须同时落水位。")

    if ok_age > seconds * GRACE_MULTIPLIER:
        span = ("%d 天" % (seconds // 86400)) if seconds >= 86400 else ("%d 小时" % (seconds // 3600))
        return _close(block, STATE_STALE,
                      "最后一次成功在 %s 前，已超过两个采集周期（%s，漏一次不算、漏两次算）："
                      "按漏采处理。它不等于失败，也不等于绿。" % (describe_age(ok_age), span))

    return _close(block, STATE_OK,
                  "最后一次成功在 %s 前，在采集周期内（%s）。"
                  % (describe_age(ok_age), "日度" if seconds == 86400 else "周度"))


def summarize(blocks: list[dict]) -> tuple[dict, str]:
    """计数 + 一句人读摘要。报警的排前面。"""
    counts = {state: 0 for state, _ in COUNT_ORDER}
    for block in blocks:
        state = str(block.get("state") or "")
        if state in counts:
            counts[state] += 1
    parts = ["%d %s" % (counts[state], suffix) for state, suffix in COUNT_ORDER if counts[state]]
    return counts, "%d 个调研信源：%s" % (len(blocks), " · ".join(parts) if parts else "无")


def build_run_report(blocks: list[dict]) -> dict:
    """本次采集的汇总报告（判据 E）。派生视图，不落盘 —— 落盘由采集器自己决定。

    两条硬规矩，都能被 RG10-RG13 卡住：

      1. **标红**：失败 / 状态文件不可信 -> severity = "red"，并汇总进 failed_sources[]。
      2. **不沿用旧值**：报告只把每个源的 this_run 与 history 两个**分开**的袋子搬出去，
         绝不用 history 的数字去填 this_run 的空 —— 本次没采到就是"未知"。

    （这两条也是为什么报告要派生而不是缓存：缓存正是"沿用旧值"的温床。）
    """
    severity = "neutral"
    if any(block.get("severity") == "red" for block in blocks):
        severity = "red"
    elif any(block.get("severity") == "warn" for block in blocks):
        severity = "warn"
    elif blocks and all(block.get("severity") == "ok" for block in blocks):
        severity = "ok"

    failed = [block.get("id") for block in blocks if block.get("severity") == "red"]
    severity_counts: dict[str, int] = {}
    for block in blocks:
        key = str(block.get("severity") or "neutral")
        severity_counts[key] = severity_counts.get(key, 0) + 1

    finished = [
        block["this_run"]["finished_at"]
        for block in blocks
        if isinstance(block.get("this_run"), dict)
        and block["this_run"].get("present")
        and block["this_run"].get("finished_at")
    ]
    # 本次总条数：只累加**本次成功**（outcome == "ok"）且写了条数的源。
    # 三条排除理由各不同，别混成一句"缺数据"：
    #   present=False        -> 本次没采到，是"未知"，不是 0；
    #   outcome="failed"     -> 连 0 都不是测量值（失败源写 items:0 只表示没采到）；
    #   水位 history.items   -> 历史值，永不参与本次总数。
    counted = [block["this_run"].get("items") for block in blocks
               if isinstance(block.get("this_run"), dict)
               and block["this_run"].get("present")
               and block["this_run"].get("outcome") == "ok"
               and isinstance(block["this_run"].get("items"), int)]

    return {
        "derived": True,
        "source_of_truth": ["state/runs/<id>.json", "state/last_seen.json"],
        "values_from": "state/runs",
        "severity": severity,
        "failed_sources": failed,
        "red_count": len(failed),
        "severity_counts": severity_counts,
        "this_run_finished_at": max(finished) if finished else "",
        "this_run_items_total": sum(counted) if counted else None,
        "this_run_sources_counted": len(counted),
        "sources": [
            {
                "id": block.get("id"),
                "name": block.get("name"),
                "severity": block.get("severity"),
                "state": block.get("state"),
                "status_label": block.get("status_label"),
                "this_run": block.get("this_run"),
                "history": block.get("history"),
                "hint": block.get("hint"),
            }
            for block in blocks
        ],
    }


def build_status(
    sources_doc: Any,
    *,
    run_dir: str | Path,
    last_seen_path: str | Path,
    now: float | None = None,
) -> dict:
    """把三层合起来判一遍。sources_doc 为空/不是对象 -> 空列表，由调用方报错。"""
    rows = sources_doc.get("research") if isinstance(sources_doc, dict) else None
    declared = [row for row in (rows or []) if isinstance(row, dict) and str(row.get("id") or "").strip()]

    watermarks, last_seen_error, last_seen_present = read_last_seen(last_seen_path)
    runs, run_errors, run_dir_present = read_runs(run_dir)

    blocks = [
        evaluate_source(
            row,
            last_seen_value=watermarks.get(str(row.get("id") or "").strip().lower()),
            run_doc=runs.get(str(row.get("id") or "").strip().lower()),
            run_error=run_errors.get(str(row.get("id") or "").strip().lower(), ""),
            now=now,
        )
        for row in declared
    ]

    counts, summary = summarize(blocks)
    return {
        "sources": blocks,
        "counts": counts,
        "summary": summary,
        "count": len(blocks),
        "run_dir_present": run_dir_present,
        "last_seen_present": last_seen_present,
        "last_seen_error": last_seen_error,
        "last_seen_entries": len(watermarks),
        "run_report": build_run_report(blocks),
    }


# --------------------------------------------------------------- 判断账本（state/ledger.jsonl）
#
# 风哥判据：**账本到期未核销 -> 状态保持 open，永远不计入命中。**
#
# 三条不许：
#   不许替人核销 —— 到期的 open 不许自动改成 hit / miss；
#   不许充数 —— 未核销的永远不进命中数（也进不了命中率的分母）；
#   不许装没看见 —— 读不出来的行要报数，不许当成"没有这条判断"。

LEDGER_OPEN = "open"
LEDGER_HIT = "hit"
LEDGER_MISS = "miss"
LEDGER_STATUSES = (LEDGER_OPEN, LEDGER_HIT, LEDGER_MISS)


def read_ledger(path: str | Path) -> tuple[list[dict], int, bool, bool]:
    """逐行读判断账本 -> (条目, 读不出来的行数, 文件在不在, 文件整体可读)。"""
    p = Path(path)
    if not p.is_file():
        return [], 0, False, True
    try:
        raw = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return [], 0, True, False
    entries: list[dict] = []
    unreadable = 0
    for line in raw.split("\n"):
        if not line.strip():
            continue
        try:
            doc = json.loads(line)
        except ValueError:
            unreadable += 1
            continue
        if isinstance(doc, dict):
            entries.append(doc)
        else:
            unreadable += 1
    return entries, unreadable, True, True


def ledger_status_of(entry: Any) -> str:
    """状态归一；认不出的返回原样小写 —— 不猜它是哪一态。"""
    if not isinstance(entry, dict):
        return ""
    return str(entry.get("status") or "").strip().lower()


def is_overdue_open(entry: Any, now: float | None = None) -> bool:
    """到期**且**仍未核销。**只读** —— 绝不修改条目。"""
    if ledger_status_of(entry) != LEDGER_OPEN or not isinstance(entry, dict):
        return False
    due = parse_time(entry.get("due"))
    if due is None:
        return False
    return due < (time.time() if now is None else now)


def ledger_report(path: str | Path, *, now: float | None = None) -> dict:
    """判断账本汇总。到期未核销的**保持 open**，且**永远不计入命中**。

    `hit_rate` 的分母只放**已核销**的（hit + miss）：open（含到期未核销）既不进分子
    也不进分母 —— 没核销不是命中，也不该被当成失败去拉低命中率。
    """
    moment = time.time() if now is None else now
    entries, unreadable, present, readable = read_ledger(path)
    counts = {LEDGER_OPEN: 0, LEDGER_HIT: 0, LEDGER_MISS: 0, "other": 0}
    overdue: list = []
    open_without_due: list = []
    for entry in entries:
        status = ledger_status_of(entry)
        counts[status if status in counts else "other"] += 1
        if status != LEDGER_OPEN:
            continue
        if parse_time(entry.get("due")) is None:
            open_without_due.append(str(entry.get("id") or ""))
        elif is_overdue_open(entry, moment):
            overdue.append(str(entry.get("id") or ""))
    hits = counts[LEDGER_HIT]
    reconciled = hits + counts[LEDGER_MISS]
    return {
        "derived": True,
        "source_of_truth": str(path),
        "present": present,
        "readable": readable,
        "total": len(entries),
        "unreadable_lines": unreadable,
        "counts": counts,
        "hits": hits,
        "reconciled": reconciled,
        "hit_rate": (hits / reconciled) if reconciled else None,
        "overdue_open": overdue,
        "overdue_open_count": len(overdue),
        "open_without_due": open_without_due,
        "note": "到期未核销的条目状态保持 open，永远不计入命中。",
    }
