# -*- coding: utf-8 -*-
"""视觉钉死闸（vision-pinned-check）—— **没有眼睛就没有手**。

主人令（2026-10-09，逐字）：
  「组主要的还是她的**视觉**，让我想不通的是我设计没错，测试也没错为什么她的视觉每次都要
    **跟手分开**去使用传统的**瞎子操作**……把视觉这么使用给她**钉死在上面**，别再使用传统瞎子操作」

判据（静态，扫门表源码 —— 门只写一处，所以扫这一处就够）：
  · 凡出现 add("desktop_control" ...) 的地方，**同一行必须同时带 privacy_read**；
    缺 ⇒ 那是一条"看不到也能动手"的缝 ⇒ **红**。
  · 允许的例外：**显式申报**的只读/非落点动作（申报表在下面，逐条写理由）。

负对照：合成一行只带 desktop_control 的 ⇒ 必须被判红。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "gbt_allinone" / "security" / "policy.py"
# 显式申报的例外（逐条写理由；没有理由的不许列）
EXEMPT = {
    # 形如 "行号或特征串": "为什么它可以只看不动 / 只动不看"
}
PAT = re.compile(r'add\(\s*"desktop_control"[^)]*\)')


def scan(text: str = "") -> dict:
    src = text if text else POLICY.read_text(encoding="utf-8", errors="replace")
    bad, good = [], []
    for i, line in enumerate(src.splitlines(), 1):
        for m in PAT.finditer(line):
            call = m.group(0)
            if "privacy_read" in call:
                good.append({"行": i, "调用": call})
            else:
                key = "L%d" % i
                if key in EXEMPT:
                    good.append({"行": i, "调用": call, "申报": EXEMPT[key]})
                else:
                    bad.append({"行": i, "调用": call, "原文": line.strip()[:110]})
    return {"ok": not bad, "落点动作数": len(good) + len(bad),
            "眼手同钉": len(good), "瞎子缝": bad}


def selftest() -> int:
    # 负对照：合成一行只带 desktop_control ⇒ 必须被抓
    fake = '        if x:\n            add("desktop_control")\n'
    r1 = scan(fake)
    red1 = len(r1["瞎子缝"]) == 1
    print("负对照·只动手不动眼 ⇒ 抓出 %d 条（必须 1）" % len(r1["瞎子缝"]))
    fake2 = '            add("desktop_control", "privacy_read")\n'
    r2 = scan(fake2)
    ok2 = len(r2["瞎子缝"]) == 0
    print("正例·眼手同钉 ⇒ 缝 %d 条（必须 0）" % len(r2["瞎子缝"]))
    real = scan()
    print("现读·落点动作 %d · 眼手同钉 %d · 瞎子缝 %d"
          % (real["落点动作数"], real["眼手同钉"], len(real["瞎子缝"])))
    ok = red1 and ok2
    print("自检：%s" % ("全过" if ok else "不过"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="视觉钉死闸（没有眼睛就没有手）")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    r = scan()
    print("视觉钉死闸：落点动作 %d 处 · 眼手同钉 %d 处 · **瞎子缝 %d**"
          % (r["落点动作数"], r["眼手同钉"], len(r["瞎子缝"])))
    for x in r["瞎子缝"]:
        print("  ❌ L%-4d %s" % (x["行"], x["原文"]))
    print("\n判据：%s" % ("PASS（没有眼睛就没有手）" if r["ok"] else "FAIL"))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
