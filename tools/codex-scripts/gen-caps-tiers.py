# -*- coding: utf-8 -*-
"""能力位分档账的生产者（修 P9「账没有写手必烂」）。

## 为什么有这件
`state/caps_tiers.json` 是 `cap-probe.py` 的**输入**（默认只扫只读档），
可是它**没有任何写手**：2026-10-01 人肉跑出来的 239 一直挂到 2026-10-23，
而注册表早已 341 位 —— 账比真少了 102 位，谁按它去扫就等于漏扫三分之一。

本件把它做成**能重跑的派生器**：
  ① 先真跑普查 `caps-write-gate-census.py`（四档：只读 / 模块有写口 / 需授权 / 分派无 import）
  ② 再按 registry 的 domain + 普查的 bucket 切成 cap-probe 认的四个档
  ③ 写 `state/caps_tiers.json`，并**当场自检**：四档之和必须 == 注册表条数（否则非零退出、不写脏账）

用法：
  py -3 tools/codex-scripts/gen-caps-tiers.py           # 重算并写账
  py -3 tools/codex-scripts/gen-caps-tiers.py --check    # 只读判据：账与注册表同数、且新鲜（≤7 天）
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TIERS = os.path.join(ROOT, "state", "caps_tiers.json")
CENSUS = os.path.join(ROOT, "state", "caps_write_gate_census.json")
CENSUS_TOOL = os.path.join(ROOT, "tools", "codex-scripts", "caps-write-gate-census.py")

# 这些域的能力位归「外部档」：跑它们要出境/花别人的额度（与只读、写盘分开管）
EXTERNAL_DOMAINS = {"external_llm", "comms", "social", "integration", "collab", "infra"}
DEVICE_DOMAINS = {"device"}
WRITE_BUCKETS = {"零作用域·模块有写口", "需授权"}


def registry_kinds() -> list:
    sys.path.insert(0, ROOT)
    from gbt_allinone import caps_registry as cr            # noqa: PLC0415
    caps = cr.all_caps()
    # registry 元素的键是 name（不是 kind/cap）—— 2026-10-23 实测：{"name","domain","handler","safe",...}
    return [c.get("name") for c in caps if isinstance(c, dict) and c.get("name")]


def run_census() -> dict:
    r = subprocess.run([sys.executable, "-X", "utf8", CENSUS_TOOL, "--json"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=ROOT, timeout=900)
    if not os.path.isfile(CENSUS):
        raise SystemExit("普查没落盘：%s（rc=%s）\n%s" % (CENSUS, r.returncode, (r.stderr or "")[-400:]))
    return json.load(open(CENSUS, encoding="utf-8"))


def build(census: dict) -> dict:
    rows = [x for x in (census.get("rows") or []) if x.get("cap")]
    kinds = registry_kinds()
    live = set(kinds)
    buckets = {"只读档": [], "写档": [], "外部档": [], "设备档": []}
    seen = set()
    for r in rows:
        cap = r["cap"]
        if cap in seen or cap not in live:
            continue
        seen.add(cap)
        dom = str(r.get("domain") or "")
        if dom in DEVICE_DOMAINS:
            buckets["设备档"].append(cap)
        elif dom in EXTERNAL_DOMAINS:
            buckets["外部档"].append(cap)
        elif r.get("bucket") in WRITE_BUCKETS:
            buckets["写档"].append(cap)
        else:
            buckets["只读档"].append(cap)
    # 普查没覆盖到的位（新增但还没来得及普查）不许丢：按"未档"如实记，让判据红
    missing = sorted(live - seen)
    return {
        "_口径": ("派生器：tools/codex-scripts/gen-caps-tiers.py（写手已接上）。"
                  "源①registry=all_caps() 源②state/caps_write_gate_census.json。"
                  "切档优先级：设备域→设备档 · 外部域→外部档 · 普查 bucket(模块有写口/需授权)→写档 · 其余→只读档。"),
        "_边界": ("本账只回答「按哪一档去扫」，不回答「跑起来对不对」——对了没对由 cap-probe 的五档读数说话。"
                  "四档必须是一个划分（互斥且合计=注册表条数）；对不上就是账坏了，非零退出。"),
        "made_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "registry_total": len(live),
        "total": sum(len(v) for v in buckets.values()),
        "counts": {k: len(v) for k, v in buckets.items()},
        "tiers": {k: [{"kind": c} for c in sorted(v)] for k, v in buckets.items()},
        "missing_from_census": missing,
    }


def write_account(out: dict) -> None:
    if out["total"] != out["registry_total"] or out["missing_from_census"]:
        print(json.dumps({"ok": False, "why": "四档之和 ≠ 注册表条数（不写脏账）",
                          "total": out["total"], "registry_total": out["registry_total"],
                          "missing": out["missing_from_census"][:10]}, ensure_ascii=False, indent=1))
        raise SystemExit(3)
    tmp = TIERS + ".tmp"
    json.dump(out, open(tmp, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    os.replace(tmp, TIERS)
    print(json.dumps({"ok": True, "wrote": TIERS, "total": out["total"],
                      "counts": out["counts"], "made_at": out["made_at"]}, ensure_ascii=False, indent=1))


def check(fresh_days: int = 7) -> int:
    """判据：账可读 · 四档齐 · total == 注册表 · made_at 不旧于 fresh_days。不写任何东西。"""
    live = registry_kinds()
    if not os.path.isfile(TIERS):
        print(json.dumps({"ok": False, "why": "账不存在：" + TIERS}, ensure_ascii=False))
        return 2
    d = json.load(open(TIERS, encoding="utf-8"))
    counts = d.get("counts") or {}
    sum_t = sum(int(v) for v in counts.values())
    made = str(d.get("made_at") or "")
    age_days = None
    try:
        stamp = dt.datetime.fromisoformat(made)
        if stamp.tzinfo is None:                            # 老账是"本地时间不带时区"，按本地解释，别当读不出来
            stamp = stamp.astimezone()
        age_days = (dt.datetime.now().astimezone() - stamp).total_seconds() / 86400
    except Exception:                                       # noqa: BLE001
        age_days = None
    problems = []
    if sum_t != len(live):
        problems.append("四档之和 %d ≠ 注册表 %d" % (sum_t, len(live)))
    if set(counts) != {"只读档", "写档", "外部档", "设备档"}:
        problems.append("四档名不齐：%s" % sorted(counts))
    if age_days is None:
        problems.append("made_at 读不出来（%r）" % made)
    elif age_days > fresh_days:
        problems.append("账已 %.1f 天没重算（上限 %d 天）" % (age_days, fresh_days))
    print(json.dumps({"ok": not problems, "registry": len(live), "tiers_total": sum_t,
                      "counts": counts, "age_days": None if age_days is None else round(age_days, 1),
                      "problems": problems}, ensure_ascii=False, indent=1))
    return 0 if not problems else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只读判据（不重算）")
    ap.add_argument("--fresh-days", type=int, default=7)
    a = ap.parse_args()
    if a.check:
        return check(a.fresh_days)
    census = run_census()
    write_account(build(census))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
