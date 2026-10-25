# -*- coding: utf-8 -*-
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""痕迹触手 wave_probe · 第 2 步第二小刀（Owner 2026-09-19 图纸 §3）。

一句话：**被心跳唤醒时量一次"波动"，写一条 `wave_samples`。**

三条纪律（都写进代码，不靠自觉）：
  ① **零新增进程**：本模块不出现子进程 / 线程 / 事件循环 / 第三方调度器 —— 它只"挂在" app 心跳上；
  ② **起步期只记流水**：本次唤醒即使 `triggered=True`，也**只写 `wave_samples`、不写 `traces`**
     （"先量几天，再用读数定 K 与阈值" —— 图纸 §3.3 起步期形态）；
  ③ **口径不另立**：白名单直接从 `trace_store` 取（**同一张表**），不许两处各存一份。

阈值口径（图纸 §3.3 · Owner 定案原文）：
    近 15 分钟 denied/blocked/error 密度 vs 过去 7 天同时段基线，超 3σ 触发一次波动。
    σ 退化兜底：样本<3 ⇒ insufficient（不触发）· σ=0 且 μ=0 ⇒ floor(K=3) · σ=0 且 μ>0 ⇒ count>μ。
    离群日（单日信号数 > 覆盖期中位数 × 5）剔出基线。

用法：
    py -3.10 -m gbt_allinone.tools.wave_probe            # 量一次并写一条 sample（人读）
    py -3.10 -m gbt_allinone.tools.wave_probe --dry      # 只量不写（人读）
    py -3.10 -m gbt_allinone.tools.wave_probe --json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from gbt_allinone import trace_store as TS  # noqa: E402

AUDIT = ROOT / "gbt_allinone" / "store" / "audit.jsonl"
WINDOW_S = 900          # 15 分钟：与 §3.3 同一窗口（全系统只留一个窗口口径）
BASELINE_DAYS = 7
FLOOR_K = 3             # σ=0 且 μ=0 时的绝对下限（§3.3 兜底 ②）
OUTLIER_X = 5           # 单日信号数 > 覆盖期中位数 × 5 ⇒ 离群日，剔出基线
WHITELIST_EVENTS = TS.WHITELIST_EVENTS     # **同一张表**（不是副本）
PROC_PRIMITIVES = ("subprocess", "Popen", "os.system", "Thread(", "asyncio",  # PROC_SCAN_OFF
                   "multiprocessing", "sched.")                               # PROC_SCAN_OFF


def decide(count: int, samples: list, floor_k: int = FLOOR_K) -> tuple:
    """纯函数：`μ+3σ` 判据 + σ 退化兜底。返回 `(triggered, trigger_mode, mu, sigma)`。

    为什么兜底必须有：零膨胀下 7 个样本很可能全是 0 ⇒ σ=0 ⇒ `μ+3σ=0`，
    那样**任何 1 起事件都会"触发"**，等于没有阈值（实测见图纸 §4.10 的 dry-run）。
    """
    if len(samples) < 3:
        return False, "insufficient", 0.0, 0.0
    mu = statistics.fmean(samples)
    sd = statistics.stdev(samples) if len(set(samples)) > 1 else 0.0
    if sd == 0 and mu == 0:
        return count > floor_k, "floor_used", mu, sd
    if sd == 0:
        return count > mu, "sigma_zero", mu, sd
    return count > mu + 3 * sd, "3sigma", mu, sd


def _collect(now: float | None = None) -> dict:
    """只读账本，折成 `(day, bucket) -> count`；白名单 + 排除测试件（共用 origin 闸口径）。"""
    now = now or time.time()
    per_day = defaultdict(Counter)
    day_total = Counter()
    if not AUDIT.is_file():
        return {"ok": False, "reason_code": "no_ledger", "error": "审计账本不在：%s" % AUDIT}
    with AUDIT.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if '"event"' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            ev = str(d.get("event") or "")
            ts = d.get("ts")
            if ev not in WHITELIST_EVENTS or not isinstance(ts, (int, float)):
                continue
            if TS.is_test_origin(ev, d.get("meta") or {}):
                continue
            day = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            per_day[day][int(ts // WINDOW_S)] += 1
            day_total[day] += 1
    return {"ok": True, "per_day": per_day, "day_total": day_total, "now": now}


def measure(now: float | None = None) -> dict:
    """量一次：本次 15 分钟的次数 + 同段基线 ⇒ 判据结果。**只读，不写盘。**"""
    got = _collect(now)
    if not got["ok"]:
        return got
    per_day, day_total, now = got["per_day"], got["day_total"], got["now"]
    today = datetime.fromtimestamp(now).strftime("%Y-%m-%d")
    cur_bucket = int(now // WINDOW_S)
    days = sorted(per_day)
    med = statistics.median(day_total.values()) if day_total else 0
    outliers = {d for d, n in day_total.items() if med and n > med * OUTLIER_X}
    count = per_day.get(today, Counter()).get(cur_bucket, 0)
    samples = [per_day.get(d, Counter()).get(cur_bucket, 0)
               for d in days if d != today and d not in outliers][-BASELINE_DAYS:]
    triggered, mode, mu, sd = decide(count, samples)
    start = datetime.fromtimestamp(cur_bucket * WINDOW_S).strftime("%Y-%m-%dT%H:%M:%S")
    blind = [start, datetime.fromtimestamp(cur_bucket * WINDOW_S + WINDOW_S).strftime("%H:%M:%S")]
    return {"ok": True, "at": datetime.fromtimestamp(now).strftime("%Y-%m-%dT%H:%M:%S"),
            "window_s": WINDOW_S, "count": count, "baseline_mu": mu, "baseline_sigma": sd,
            "samples": samples, "triggered": triggered, "trigger_mode": mode,
            "coverage": "half", "blind_window": blind,
            "outlier_days": sorted(outliers), "days_covered": len(days)}


def beat(*, dry: bool = False, now: float | None = None) -> dict:
    """一次唤醒：量一次 → 写一条 `wave_samples`（**起步期不写 traces**）。"""
    m = measure(now)
    if not m.get("ok"):
        return m
    if dry:
        m["wrote"] = False
        return m
    wrote = TS.record_wave_sample("wave_beat", m["count"], window_s=WINDOW_S,
                                  baseline_mu=m["baseline_mu"],
                                  baseline_sigma=m["baseline_sigma"],
                                  trigger_mode=m["trigger_mode"],
                                  triggered=m["triggered"], coverage=m["coverage"],
                                  blind_window=m["blind_window"], source="wave_probe")
    m["wrote"] = bool(wrote.get("ok"))
    m["write_result"] = wrote
    m["traces_written"] = 0
    m["note"] = ("起步期：只记流水（wave_samples）；即使 triggered=True 也不写 traces —— "
                 "先用读数定 K 与阈值，再开留痕")
    return m


def process_primitives(path: Path | None = None) -> list:
    """本模块源码里的"起进程"原语命中点（行号:原语）—— 空 = 零新增进程。"""
    hits = []
    src = (path or Path(__file__)).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(src, 1):
        if "PROC_SCAN_OFF" in line:         # 扫描器自己的模式表，不算命中（同 topic_watch）
            continue
        code = line.split("#", 1)[0]
        for pat in PROC_PRIMITIVES:
            if pat in code:
                hits.append("%d:%s" % (i, pat))
    return hits


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="痕迹触手：唤醒时量一次波动（起步期只记流水）")
    ap.add_argument("--dry", action="store_true", help="只量不写")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    out = beat(dry=a.dry)
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        if not out.get("ok"):
            print("量不了：%s" % out.get("error"))
            return 2
        print("本次 %d 分钟窗口：%d 条 · 基线 μ=%.2f σ=%.2f · 触发=%s（模式=%s）· 写入 sample=%s"
              % (WINDOW_S // 60, out["count"], out["baseline_mu"], out["baseline_sigma"],
                 out["triggered"], out["trigger_mode"], out.get("wrote")))
        print("覆盖=%s · 盲区=%s · 离群日=%s" % (out["coverage"], out["blind_window"],
                                              out["outlier_days"] or "无"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
