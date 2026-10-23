# gbt-capability: filesystem
"""六环里的最后一环：编排（发动机）。

前五环各自都能跑，但没有东西按时间、按顺序把它们串起来 —— `research.json` 里的
`daily_at` / `per_run_deadline_s` 一直是死配置（零消费者）。这一环就是那台发动机。

一轮的顺序不许乱：

    1. 读 research.json
    2. 逐个源采集（每源 per_source_timeout_s，整轮 per_run_deadline_s）
    3. 落盘三袋（结局 / 水位 / 入库）—— 复用 collector，不另写一套
    4. 算摘要段（判据 H）—— LLM 挂了窗口照样能用
    5. 写本轮记录 state/orchestrator.json
    6. 用 research_status.build_status 复核并印一行

五条自制：

1. **超 deadline 的源标 skipped，不标 failed**：「本轮没轮到」不是「采集失败」，
   两者混了就把「我们没跑」写成「平台挂了」。
2. **没实现的源什么都不写**（继承 collector 的口径，不冒充已采集）。
3. **摘要失败不许影响数字**：window_ok 恒为 True；数字全来自 state/runs，不经过摘要。
4. **水位只记成功**（判据 D）；失败一个字节都不碰。
5. **--due 幂等**：今天在 daily_at 之后跑过就不再跑。调度器可以每几分钟敲一次也不会连发
   —— 调度器只管定时，幂等归这里。

用法：

    python holo_pet/research/orchestrator.py                # 立刻跑一轮
    python holo_pet/research/orchestrator.py --due          # 到点才跑（给调度器用）
    python holo_pet/research/orchestrator.py --dry-run      # 只印计划，不写盘
    python holo_pet/research/orchestrator.py --only arxiv --limit 3
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
HOLO = HERE.parent
STATE = ROOT / "state"
RUNS = STATE / "runs"
LAST_SEEN = STATE / "last_seen.json"
SIGNALS = STATE / "signals.jsonl"
SOURCES = ROOT / "sources.json"
CONFIG = HOLO / "research.json"
RUN_LOG = STATE / "orchestrator.json"
SUMMARY_CACHE = STATE / "summary.json"

for _p in (str(HERE), str(HOLO), str(ROOT / "gbt_allinone")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import collector  # noqa: E402
import research_status  # noqa: E402
import signal_ingest  # noqa: E402

try:
    import safe_io
except ImportError:  # pragma: no cover
    safe_io = None

DEFAULT_CONFIG = {
    "daily_at": "08:10",
    "per_run_deadline_s": 420,
    "per_source_timeout_s": 60,
    "llm_summary": {"enabled": True, "max_calls_per_run": 1, "max_chars": 200},
    "max_signals_shown": 20,
    "fail_open_stale_hours": 24,
}


def _now_iso(moment=None):
    moment = time.time() if moment is None else moment
    return datetime.fromtimestamp(moment).astimezone().isoformat(timespec="seconds")


def read_json(path):
    """-> (文档, 错误串)。读不出来是事实，不许当成空。"""
    target = Path(path)
    if not target.is_file():
        return {}, ""
    try:
        doc = json.loads(target.read_text(encoding="utf-8"))
    except OSError as exc:
        return {}, "不可读：%s" % str(exc)[:120]
    except ValueError as exc:
        return {}, "不是合法 JSON：%s" % str(exc)[:120]
    return (doc if isinstance(doc, dict) else {}), ""


def write_json(path, payload):
    target = Path(path)
    if safe_io is not None:
        safe_io.atomic_write_json(target, payload)
    else:  # pragma: no cover
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                          encoding="utf-8")


def load_config(path=CONFIG):
    """-> (配置, 错误串)。缺失/坏 -> 用默认值，但把错误带出去（不许静默）。"""
    target = Path(path)
    if not target.is_file():
        return dict(DEFAULT_CONFIG), "本机没有 %s，按默认值跑" % target.name
    try:
        doc = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return dict(DEFAULT_CONFIG), "%s 读不出来（%s），按默认值跑" % (
            target.name, str(exc)[:80])
    if not isinstance(doc, dict):
        return dict(DEFAULT_CONFIG), "%s 顶层不是对象，按默认值跑" % target.name
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(doc)
    return cfg, ""


def parse_hhmm(value):
    parts = str(value or "").strip().split(":")
    if len(parts) != 2:
        return None
    try:
        hh, mm = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None
    return hh, mm


def due_state(cfg, now=None):
    """今天到点了吗、今天跑过了吗 -> (该不该跑, 理由)。"""
    moment = time.time() if now is None else now
    hhmm = parse_hhmm(cfg.get("daily_at"))
    if hhmm is None:
        return True, "daily_at 不可解析，按「立刻跑」处理"
    hh, mm = hhmm
    today_at = datetime.fromtimestamp(moment).astimezone().replace(
        hour=hh, minute=mm, second=0, microsecond=0).timestamp()
    log, _err = read_json(RUN_LOG)
    last = research_status.parse_time(log.get("finished_at")) if log else None
    if moment < today_at:
        return False, "未到 %02d:%02d" % (hh, mm)
    if last is None:
        return True, "已过 %02d:%02d，且从未跑过" % (hh, mm)
    if last >= today_at:
        return False, "今天 %02d:%02d 之后已跑过" % (hh, mm)
    return True, "已过 %02d:%02d，今天还没跑" % (hh, mm)


def _load_watermark():
    if not LAST_SEEN.is_file():
        return {}, ""
    doc, err = read_json(LAST_SEEN)
    return doc, err


def _digest(report, max_chars):
    """给摘要器的原料：只喂本轮的机械事实，不喂我自己的判断。"""
    lines = []
    for entry in report.get("sources") or []:
        lines.append("%s outcome=%s http=%s items=%s %s" % (
            entry.get("id"), entry.get("outcome"), entry.get("http"),
            entry.get("items"), entry.get("reason") or ""))
    for entry in report.get("skipped") or []:
        lines.append("%s skipped: %s" % (entry.get("id"), entry.get("why")))
    return "\n".join(lines)[:int(max_chars)]


def run_once(*, sources_path=SOURCES, config_path=CONFIG, only="", limit=None,
             dry_run=False, now=None, summarizer=None, stream=sys.stdout):
    started = time.time() if now is None else now
    cfg, cfg_error = load_config(config_path)
    rows = collector.load_sources(sources_path)
    wanted = {s.strip().lower() for s in str(only or "").split(",") if s.strip()}
    per_source = float(cfg.get("per_source_timeout_s") or 60)
    deadline_s = float(cfg.get("per_run_deadline_s") or 420)
    deadline = started + deadline_s

    report = {
        "started_at": _now_iso(started), "finished_at": "", "dry_run": bool(dry_run),
        "config_error": cfg_error, "config_hint": Path(config_path).name,
        "per_source_timeout_s": per_source, "per_run_deadline_s": deadline_s,
        "sources": [], "skipped": [], "watermark_written": [],
        "ingest": {}, "summary": None, "elapsed_s": None, "verify": None,
    }

    watermark, wm_error = _load_watermark()
    if wm_error:
        report["watermark_error"] = wm_error

    print("[orchestrator] 登记 %d 个源；可采 %d 个：%s"
          % (len(rows), len(collector.COLLECTORS), ", ".join(sorted(collector.COLLECTORS))))
    print("[orchestrator] 每源超时 %.0fs · 整轮 deadline %.0fs%s"
          % (per_source, deadline_s, "（dry-run，不写盘）" if dry_run else ""))

    for row in rows:
        sid = str(row.get("id") or "").strip().lower()
        if wanted and sid not in wanted:
            continue
        if not row.get("enabled"):
            report["skipped"].append({"id": sid, "why": "未启用（enabled=false）"})
            continue
        if sid not in collector.COLLECTORS:
            report["skipped"].append(
                {"id": sid, "why": "本编排未实现该源的采集器，不写盘（保持未采集）"})
            continue
        if time.time() >= deadline:
            report["skipped"].append(
                {"id": sid, "why": "本轮已过 deadline（%.0fs），未轮到" % deadline_s})
            continue
        budget = min(per_source, max(1.0, deadline - time.time()))
        doc, records = collector.run_source(row, timeout=budget, limit=limit)
        doc["timeout_used_s"] = round(budget, 1)
        if not dry_run:
            write_json(RUNS / ("%s.json" % sid), doc)
        report["sources"].append(
            {"id": sid, "outcome": doc["outcome"], "http": doc["http"],
             "items": doc["items"], "reason": doc["reason"]})
        print("[orchestrator] %-12s outcome=%s http=%s items=%s %s"
              % (sid, doc["outcome"], doc["http"], doc["items"], doc["reason"]))
        if doc["outcome"] == "ok":
            # 水位只记成功 —— 失败一个字节都不许碰（判据 D）。
            watermark[sid] = {"at": doc["finished_at"], "items": doc["items"]}
            report["watermark_written"].append(sid)
            if not dry_run:
                res = signal_ingest.ingest(records, path=SIGNALS, stream=stream)
                report["ingest"][sid] = res
                print("[orchestrator] %-12s 入库 offered=%d written=%d rejected=%d codes=%s"
                      % (sid, res["offered"], res["written"], res["rejected"], res["codes"]))

    # ---- 摘要段（判据 H）：失败也不许影响上面那些数字 ----
    previous, _perr = read_json(SUMMARY_CACHE)
    summary_text, summary_model, summary_error = None, "", ""
    if summarizer is None:
        summary_error = "摘要器未接线（llm_summary 有配置，但本机没有可调用的摘要函数）"
    else:
        try:
            max_chars = int((cfg.get("llm_summary") or {}).get("max_chars") or 200)
        except (TypeError, ValueError):
            max_chars = 200
        try:
            produced = summarizer(_digest(report, max_chars))
            summary_text, summary_model = produced if isinstance(produced, tuple) else (produced, "")
        except Exception as exc:  # 摘要器怎么炸都不许带塌整轮
            summary_error = "%s: %s" % (type(exc).__name__, str(exc)[:120])

    block = signal_ingest.summary_block(
        text=summary_text,
        generated_at=_now_iso() if summary_text else None,
        model=summary_model, error=summary_error, previous=previous, now=time.time(),
        fail_open_stale_hours=float(
            cfg.get("fail_open_stale_hours")
            or signal_ingest.DEFAULT_FAIL_OPEN_STALE_HOURS))
    report["summary"] = block
    if not dry_run and block.get("available"):
        # 只有真出了新摘要才覆盖缓存 —— 失败/stale 不许顶掉上一次成功的那份。
        write_json(SUMMARY_CACHE, {"text": block.get("text"), "model": block.get("model"),
                                   "generated_at": block.get("generated_at")})
    print("[orchestrator] 摘要段 code=%s window_ok=%s available=%s%s"
          % (block.get("reason_code"), block.get("window_ok"), block.get("available"),
             (" " + str(block.get("error"))[:80]) if block.get("error") else ""))

    report["finished_at"] = _now_iso()
    report["elapsed_s"] = round(time.time() - started, 2)

    if not dry_run:
        if report["watermark_written"]:
            write_json(LAST_SEEN, watermark)
            print("[orchestrator] 水位已更新：%s" % ", ".join(sorted(report["watermark_written"])))
        else:
            print("[orchestrator] 本轮无成功源 —— 水位一个字节都没动")

    # ---- 复核：复用既有口径，不另造一套 ----
    sources_doc, sources_error = read_json(sources_path)
    if isinstance(sources_doc, dict) and sources_doc:
        status = research_status.build_status(sources_doc, run_dir=RUNS,
                                              last_seen_path=LAST_SEEN)
        rr = status.get("run_report") or {}
        report["verify"] = {"severity": rr.get("severity"),
                            "summary": status.get("summary"),
                            "counts": status.get("counts"),
                            "sources_error": sources_error}
        print("[orchestrator] 复核 severity=%s | %s" % (rr.get("severity"), status.get("summary")))
    else:
        report["verify"] = {"sources_error": sources_error or "sources.json 读不出来"}
        print("[orchestrator] 复核跳过：%s" % report["verify"]["sources_error"])

    if not dry_run:
        write_json(RUN_LOG, report)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="调研编排（六环第 6 环）")
    ap.add_argument("--only", default="", help="只跑指定的源 id，逗号分隔")
    ap.add_argument("--limit", type=int, default=0, help="覆盖 limit_per_run")
    ap.add_argument("--due", action="store_true", help="到点且今天没跑过才跑（幂等，给调度器用）")
    ap.add_argument("--dry-run", action="store_true", help="只印计划，不写盘")
    ap.add_argument("--config", default=str(CONFIG))
    ap.add_argument("--sources", default=str(SOURCES))
    args = ap.parse_args(argv)

    cfg, cfg_error = load_config(args.config)
    if cfg_error:
        print("[orchestrator] 配置提示：%s" % cfg_error)

    if args.due:
        should, why = due_state(cfg)
        print("[orchestrator] --due：%s" % why)
        if not should:
            return 0

    RUNS.mkdir(parents=True, exist_ok=True)
    report = run_once(sources_path=args.sources, config_path=args.config,
                      only=args.only, limit=args.limit or None, dry_run=args.dry_run)
    return 0 if report.get("verify", {}).get("severity") != "red" else 0


if __name__ == "__main__":
    raise SystemExit(main())
