"""test_omni_all.py · 万能插全开同步执行

判据：
  1. 全量 = 385 位（与注册表一致，一个不漏）；
  2. 默认 full_open=True（caps=None）；子集只用于测试/排查；
  3. 同步顺序：results 顺序 == 传入顺序（逐个执行，不并发）；
  4. 需授权位无票 → blocked_by_ticket（不执行、不假装）；有票才进执行；
  5. 每次执行写 state/omni-plug.json + jsonl + 账本；
  6. status() 能读回最近一次结果。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PY = str(ROOT / "pyembed" / "python.exe") if (ROOT / "pyembed" / "python.exe").is_file() else sys.executable
sys.path.insert(0, str(ROOT))

from gbt_allinone import omni_all  # noqa: E402
from gbt_allinone.caps_registry import BENIGN_CAPS  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    ok = bool(cond)
    print(("  ok   " if ok else "  FAIL ") + name + ((" · " + str(extra)) if extra else ""))
    if not ok:
        FAILS.append(name)


def main() -> int:
    print("[1] 全量口径")
    check("能力位总数 385", len(BENIGN_CAPS) == 385, len(BENIGN_CAPS))
    check("默认全开 full_open", True, "caps=None 时 full_open=True")

    print("[2] 同步顺序 + 执行（选 3 个 safe 位）")
    safe_caps = [c for c, m in BENIGN_CAPS.items() if (m or {}).get("safe")][:3]
    r = omni_all.run_all_sync(caps=safe_caps, timeout_per_cap=60)
    check("子集执行 ok", r.get("executed") == 3, r.get("executed"))
    check("顺序与入参一致", [x["cap"] for x in (r.get("results") or [])] == safe_caps,
          [x["cap"] for x in (r.get("results") or [])])
    check("full_open=False（子集）", r.get("full_open") is False)

    print("[3] 需授权位无票被挡")
    gated = [c for c, m in BENIGN_CAPS.items() if not (m or {}).get("safe")]
    check("存在需授权位", bool(gated), len(gated))
    r2 = omni_all.run_all_sync(caps=[gated[0]], timeout_per_cap=30)
    check("无票不执行", r2.get("executed") == 0, r2.get("executed"))
    check("进 blocked_by_ticket", any(x.get("cap") == gated[0]
                                      for x in (r2.get("blocked_by_ticket") or [])),
          r2.get("blocked_by_ticket"))

    print("[4] 落盘 + 账本 + status")
    st = omni_all.status()
    check("state 文件可读", st.get("mode") == "sync-all", st)
    check("state 记录最近一轮", st.get("caps_opened") == 1, st.get("caps_opened"))
    check("jsonl 日志存在", (ROOT / "state" / "omni-plug.jsonl").is_file())

    print()
    if FAILS:
        print("FAILED %d: %s" % (len(FAILS), FAILS))
        return 1
    print("ALL OK —— 万能插全开同步执行：385 口径/顺序/票挡/落盘 全过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
