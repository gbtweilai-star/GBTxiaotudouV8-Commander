"""四批横扫的**并集覆盖**现算：哪几个文件真被看过、红的是谁、谁一次都没进过批。

为什么必须现算并集：分批跑时每批的「全 N 个」是**当时**的文件数，而我在批与批之间
还在往仓里加测试文件（124 → 125 → 126）⇒ **四批的数字不能并排一放就说全仓看过了**。
只有把四份 JSON 的文件名并起来，再对**现在**的仓现数一遍，才能说清"覆盖了多少"。
"""
from __future__ import annotations

import json
from pathlib import Path

# 2026-09-26 自纠：原来写死本机绝对路径 C:\Users\ADMIN\Desktop\GBT小土豆V8 ——
#    换机/换目录就静默指向别处（或 FileNotFoundError），违背"现数、不写死"的立尺初衷。
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output" / "blueprint-audit"


def main() -> int:
    batches = sorted(OUT.glob("2026-09-26-满仓横扫-第*批.json"))
    if not batches:
        print("🔴 一份批次 JSON 都没有 ⇒ 无从现算")
        return 2

    # 本仓现在的测试文件全集（口径与 run-all-tests.py 一致：gbt_allinone/tests/test_*.py）
    now_all = sorted(p.name for p in (ROOT / "gbt_allinone" / "tests").glob("test_*.py"))
    print("本仓现读测试文件：%d 个" % len(now_all))

    seen: dict[str, dict] = {}
    reds: list[tuple[str, str, str]] = []
    timeouts: list[str] = []
    for f in batches:
        rows = json.loads(f.read_text(encoding="utf-8"))
        print("\n— %s：%d 个文件" % (f.name, len(rows)))
        for r in rows:
            name = r["file"]
            seen.setdefault(name, {"batches": [], "results": []})
            seen[name]["batches"].append(f.name)
            seen[name]["results"].append(r["result"])
            if r["result"] not in ("OK", "NO_TESTS"):
                if r["result"] == "TIMEOUT":
                    timeouts.append(name)
                else:
                    for case in (r.get("fails") or ["(未记到用例名)"]):
                        reds.append((name, case, r["result"]))
        bad = [r for r in rows if r["result"] not in ("OK", "NO_TESTS")]
        print("   未过 %d 个：%s" % (len(bad), "、".join(r["file"] for r in bad) or "无"))

    covered = set(seen)
    missing = [n for n in now_all if n not in covered]
    extra = sorted(n for n in covered if n not in now_all)

    print("\n" + "=" * 78)
    print("四批并集覆盖：%d / %d 个现读测试文件（%.1f%%）"
          % (len([n for n in covered if n in set(now_all)]), len(now_all),
             100.0 * len([n for n in covered if n in set(now_all)]) / max(1, len(now_all))))
    if missing:
        print("  🔴 **一次都没进过任何一批**（%d 个）：" % len(missing))
        for n in missing:
            print("     · %s" % n)
    else:
        print("  ✓ 现读的每一个测试文件都至少进过一批")
    if extra:
        print("  ⚠️ 进过批但现在已经不在仓里（%d 个）：%s" % (len(extra), "、".join(extra)))

    print("\n红集（跨四批去重）：%d 条" % len(reds))
    for name, case, res in sorted(set(reds)):
        print("  [%s] %s :: %s" % (res, name, case))
    if timeouts:
        print("超时（**本次无法判定**，不等于红）：%s" % "、".join(sorted(set(timeouts))))

    print("\n" + "=" * 78)
    print("结论口径：只有「并集覆盖 = 现读全集」且「红集为空或每条都已定性」时，")
    print("          才允许说『这一轮全仓看过了』。分批绿 ≠ 一次全量的绿。")
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
