# gbt-capability: filesystem
"""信号入库闸 —— 判据 F / G 的唯一判定处（写死一处，别处不许再判）。

风哥 2026-09-18 判据：

    F  任何 SignalRecord 缺 url -> 拒绝入库 + 控制台报错 + 不入 signals.jsonl
    G  有 value 无 baseline     -> 输出不含增长率（**不是** +0%）

两条同源：**缺 != 0**。

    缺 url      不是"空链接"，是这条信号没有出处 —— 没有出处的不许入库。
    没 baseline 不是"0 增长"，是没有对照 —— 算不出来就不许印出来。

唯一禁止的写法是**用默认值把"缺"填成"有"**。实证先例（本文件不改它，只挡在入库这道闸上）：
`gbt_allinone/recon/last30days/engine/schema.py:218` 与 `:242` 都是
`url=payload.get("url") or ""` —— 缺 url 被静默填成空串。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Iterable

MISSING_URL = "missing_url"
VALUE_WITHOUT_BASELINE = "value_without_baseline"

REJECT_LABEL = "拒绝入库"
CONSOLE_PREFIX = "[signal_ingest]"

# 状态层默认落点。搬去 holo_pet/ 时改这一行（或调用方显式传 path）。
DEFAULT_SIGNALS_PATH = Path(__file__).resolve().parent.parent / "state" / "signals.jsonl"


def url_of(record: Any) -> str | None:
    """取 url。**不做任何默认值填充**；None 表示缺。"""
    if not isinstance(record, dict):
        return None
    value = record.get("url")
    if not isinstance(value, str):
        return None
    return value if value.strip() else None


def has_url(record: Any) -> bool:
    return url_of(record) is not None


def violations(record: Any) -> list[str]:
    """入库硬闸（判据 F）。空列表 = 放行。"""
    return [] if has_url(record) else [MISSING_URL]


def record_label(record: Any, index: int | None = None) -> str:
    """控制台报错用的短标签；认不出就报序号，绝不编一个内容出来。"""
    if isinstance(record, dict):
        for key in ("id", "signal_id", "title", "source"):
            value = record.get(key)
            if value not in (None, ""):
                return "%s=%s" % (key, str(value)[:60])
    return "index=%s" % ("?" if index is None else index)


def _number(value: Any) -> float | None:
    """严格取数：bool 不算数字（True == 1 是"拿默认值顶缺"的另一种马甲）。"""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def baseline_of(record: Any) -> float | None:
    """数字型 baseline 才算。策略字符串（"rolling_7d"）**不是** baseline。"""
    if not isinstance(record, dict):
        return None
    return _number(record.get("baseline"))


def value_of(record: Any) -> float | None:
    if not isinstance(record, dict):
        return None
    return _number(record.get("value"))


def growth_rate(record: Any) -> float | None:
    """有 value 且有非零数字 baseline 才算得出来；否则 None（判据 G）。

    baseline == 0 也返回 None：除以 0 不是"无穷增长"，是没有可用对照。
    """
    value = value_of(record)
    baseline = baseline_of(record)
    if value is None or baseline is None or baseline == 0:
        return None
    return (value - baseline) / baseline


def format_growth(record: Any) -> str | None:
    """人读增长率。**算不出来就返回 None**，调用方必须整键省略 —— 不许印 "+0%"。"""
    rate = growth_rate(record)
    if rate is None:
        return None
    return "%s%.1f%%" % ("+" if rate >= 0 else "", rate * 100.0)


def report_view(record: Any) -> dict:
    """输出视图：算不出增长率时 **growth 键根本不出现**（判据 G）。"""
    view = {"url": url_of(record), "value": value_of(record)}
    rate = format_growth(record)
    if rate is not None:
        view["growth"] = rate
    return view


def ingest(records: Iterable[Any], *, path: str | Path = DEFAULT_SIGNALS_PATH,
           stream=None) -> dict:
    """把信号写进 signals.jsonl；缺 url 的一律拒收（判据 F）。

    - 命中 F：控制台写一行（默认 stderr），**不写盘**。
    - 放行：一行一条 JSON（ensure_ascii=False），append-only。
    - 逐条独立：一条被拒**不连坐**同批其它记录。
    """
    out = sys.stderr if stream is None else stream
    target = Path(path)
    offered = list(records)
    accepted: list = []
    rejected: list = []

    for index, record in enumerate(offered):
        reasons = violations(record)
        if not reasons:
            accepted.append(record)
            continue
        label = record_label(record, index)
        rejected.append({"index": index, "label": label, "reasons": reasons})
        out.write("%s %s #%d %s：%s —— 缺 url 的记录不入 %s\n"
                  % (CONSOLE_PREFIX, REJECT_LABEL, index, label,
                     ",".join(reasons), target.name))
        out.flush()

    written = 0
    if accepted:
        text = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                       for r in accepted)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            from gbt_allinone import safe_io  # 照仓库铁律走 safe_io 追加
        except ImportError:  # pragma: no cover —— 裸按文件路径导入时
            safe_io = None
        if safe_io is not None:
            safe_io.locked_append_text(target, text)
        else:
            with open(target, "a", encoding="utf-8", newline="") as fh:
                fh.write(text)
        written = len(accepted)

    return {
        "ok": True,
        "path": str(target),
        "offered": len(offered),
        "written": written,
        "rejected": len(rejected),
        "rejected_records": rejected,
        "all_written": not rejected,
        "codes": sorted({code for item in rejected for code in item["reasons"]}),
    }


SUMMARY_OK = "ok"
SUMMARY_STALE_REUSE = "stale_reuse"
SUMMARY_UNAVAILABLE = "summary_unavailable"
DEFAULT_FAIL_OPEN_STALE_HOURS = 24


def _epoch(value: Any) -> float | None:
    """epoch 秒 / ISO 字符串 -> epoch；认不出就 None —— 不猜。"""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    try:
        from datetime import datetime
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def summary_block(*, text: Any = None, generated_at: Any = None, model: Any = "",
                  error: Any = "", previous: Any = None, now: float | None = None,
                  fail_open_stale_hours: float = DEFAULT_FAIL_OPEN_STALE_HOURS) -> dict:
    """摘要块（判据 H：**LLM 挂了，窗口必须照样能用**）。

    不许发生三件事：

    1. 失败时把上一次的摘要当成本次的 —— 静默沿用 = 谎报新鲜；
    2. 失败时印空串冒充"有摘要"；
    3. 失败时让整个窗口报错/空白 —— **命门不许交给限流通道**（`window_ok` 恒为 True）。

    `fail_open_stale_hours` 允许在窗口内**带标记**回看上次成功摘要
    （`stale=True` + `age_hours`）；超时就只留"不可用"，不硬凑。
    它只管**窗口可用性 / 摘要这一段**；`run_report` 的数字仍走判据 E 的双袋子，不受影响。
    """
    moment = time.time() if now is None else now
    body = text.strip() if isinstance(text, str) else ""

    if body and not error:
        return {"available": True, "text": body, "stale": False, "age_hours": None,
                "model": str(model or ""), "generated_at": generated_at,
                "error": "", "reason_code": SUMMARY_OK, "window_ok": True}

    reason = str(error or "摘要调用失败（未给出原因）")
    prev_text = ""
    prev_at = None
    prev_doc = previous if isinstance(previous, dict) else {}
    if isinstance(prev_doc.get("text"), str):
        prev_text = prev_doc["text"].strip()
    prev_at = _epoch(prev_doc.get("generated_at"))

    age_hours = None
    if prev_text and prev_at is not None:
        age_hours = max(0.0, (moment - prev_at) / 3600.0)

    if prev_text and age_hours is not None and age_hours <= float(fail_open_stale_hours):
        return {"available": False, "text": prev_text, "stale": True,
                "age_hours": round(age_hours, 1),
                "model": str(prev_doc.get("model") or ""),
                "generated_at": prev_doc.get("generated_at"),
                "error": reason, "reason_code": SUMMARY_STALE_REUSE, "window_ok": True}

    return {"available": False, "text": None, "stale": False, "age_hours": None,
            "model": str(model or ""), "generated_at": generated_at,
            "error": reason, "reason_code": SUMMARY_UNAVAILABLE, "window_ok": True}
