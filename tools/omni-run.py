"""GB T小土豆V8 · 万能插全开同步执行（CLI）

用法：
    python tools/omni-run.py                    # 全开：385 位，同步执行
    python tools/omni-run.py --timeout 20       # 单能力位超时（秒）
    python tools/omni-run.py --ticket <ticket>  # 带票（需授权位才执行）
    python tools/omni-run.py --status           # 看最近一次结果

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gbt_allinone import omni_all  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=float, default=12.0)
    ap.add_argument("--ticket", default="")
    ap.add_argument("--run-id", default="")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.status:
        print(json.dumps(omni_all.status(), ensure_ascii=False, indent=2))
        return 0
    r = omni_all.run_all_sync(timeout_per_cap=a.timeout, ticket=a.ticket, run_id=a.run_id)
    print(json.dumps({k: r.get(k) for k in ("ok", "mode", "run_id", "caps_total",
                                           "caps_opened", "full_open", "executed",
                                           "ok_count", "fail_count", "elapsed_ms")},
                     ensure_ascii=False, indent=2))
    print("票挡:", len(r.get("blocked_by_ticket") or []))
    print("结果文件: state/omni-plug.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
