# -*- coding: utf-8 -*-
"""**仓库自带测试**的统一入口 —— 把"有测试但没人跑"变成一条命令 + 一个退出码。

为什么要有它（2026-09-22 现读实锤）：
  仓库里有真测试（`holo_pet/tests/test_panel_server.py` 一家就 **141 项**，含
  「APP_SURFACE 与真实路由双向对账」这种正是我这几轮在找的门），**但没有任何一条命令会跑它们** ——
  我一整轮的"门清单"里，它们一次都没出现过。⇒ 这就是"**门存在、没人扣扳机**"。
  更糟的是很容易把它当"没有测试"：`py -m pytest gbt_allinone/tests/test_panel_server.py` 会报
  `file or directory not found`（那个文件其实在 `holo_pet/tests/`），**看错地方 = 以为没有**。

口径：
  · 只跑**存在的**测试根（`holo_pet/tests`、`gbt_allinone/tests`、`plugins/**/tests`）；
  · 每个根单独一次 pytest（互不污染），抓末尾摘要行；
  · **"没收集到测试" ≠ "通过"**，如实标 `空`；
  · pytest 不在 / 跑不起来 ⇒ **exit 3（前置不可用）**，不与"测试失败"混为一谈。

用法：
    py -3.14 tools/codex-scripts/run-tests.py            # 全部测试根
    py -3.14 tools/codex-scripts/run-tests.py holo_pet/tests   # 只跑指定的
退出码：0 = 全过；1 = 有失败；3 = 前置不可用（pytest 缺失/跑不起来）。
"""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
CANDIDATE_ROOTS = [
    ROOT / "holo_pet" / "tests",
    ROOT / "gbt_allinone" / "tests",
    ROOT / "plugins" / "gbt-master" / "tests",
]
SUM = re.compile(r"(\d+) (passed|failed|error|errors|skipped)")


def main(argv: list[str]) -> int:
    if importlib.util.find_spec("pytest") is None:
        print("🔴 前置不可用：这个解释器里没有 pytest（`py -3.14 -m pip show pytest` 现读为空）")
        print("   ⇒ 本器**不报「测试通过」**，如实 exit 3。装法（会改环境 ⇒ 先问主人）："
              "`py -3.14 -m pip install pytest pytest-timeout`")
        return 3

    # ⚠️ 传进来的相对路径要**先按仓根解析**：第一版直接 `Path(a)`，
    #    于是 `run-tests.py holo_pet/tests` 在打印时 `relative_to(ROOT)` 抛
    #    `ValueError: 'holo_pet\tests' is not in the subpath of …`（**本器自己崩**）。
    picked = [(Path(a) if Path(a).is_absolute() else (ROOT / a)).resolve()
              for a in argv[1:] if not a.startswith("-")]

    def disp(p: Path) -> str:
        try:
            return str(p.relative_to(ROOT))
        except ValueError:
            return str(p)

    roots = picked or [r for r in CANDIDATE_ROOTS if r.is_dir()]
    if not roots:
        print("🔴 一个测试根都没找到（现读候选：%s）"
              % "、".join(disp(r) for r in CANDIDATE_ROOTS))
        return 3

    print("=" * 88)
    print("仓库自带测试 · %d 个测试根" % len(roots))
    print("=" * 88)
    # 🔴 关键步（不做它，`gbt_allinone/tests` **80/80 全部收集失败**）：
    #    `gbt_allinone/tests/__init__.py` 有一条**生产 store 隔离守卫** ——
    #    父包在 import 期就把 STORE_DIR 绑成常量，而 pytest 收集时会先 import 父包，
    #    于是守卫**故意报错停下**（`拒绝在绑定【生产 store】的进程里跑测试`）。
    #    那是对的（历史上真把 t-sched-run 写进过生产 schedules.json），
    #    但它的表象是"80 个 ERROR"，**看起来像框架坏了**。
    #    解法就是守卫自己写的解法①：**起 Python 之前**把隔离根设进环境变量。
    #    ⇒ 本器替调用方设好（临时目录，一跑一换），并把它打印出来 —— 免得别人以为"测试跑不了"。
    iso_store = tempfile.mkdtemp(prefix="gbt_test_store_")
    iso_create = tempfile.mkdtemp(prefix="gbt_test_create_root_")
    env = dict(os.environ)
    env.setdefault("GBT_STORE_DIR", iso_store)
    env.setdefault("GBT_CREATE_ROOT", iso_create)
    print("隔离根（本器现设，防测试写生产）：")
    print("   GBT_STORE_DIR   = %s" % env["GBT_STORE_DIR"])
    print("   GBT_CREATE_ROOT = %s" % env["GBT_CREATE_ROOT"])
    print("-" * 88)
    totals = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
    bad_roots: list[str] = []
    empty_roots: list[str] = []
    for r in roots:
        t0 = time.time()
        cmd = [sys.executable, "-m", "pytest", str(r), "-q", "--timeout=180", "-p", "no:cacheprovider"]
        out, rc = "", 1
        # ⚠️ 实测撞过一次"**0 收集**"（passed 0 / failed 0；而 `holo_pet/tests` 平时 157 项必过），
        #    随后连跑 3 次不再复现 ⇒ 偶发（temp 目录 / 收集竞态一类）。所以：
        #    **空收集自动重试一次**，并把"空"与"失败"分开写 —— 否则一次抖动会被读成"测试坏了"。
        for attempt in (1, 2):
            try:
                p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, env=env,
                                   encoding="utf-8", errors="replace", timeout=3600)
                out, rc = (p.stdout or "") + (p.stderr or ""), p.returncode
            except Exception as e:  # noqa: BLE001
                print("  🔴 %-28s 跑不起来：%s" % (disp(r), e))
                bad_roots.append(disp(r))
                out, rc = "", -1
                break
            tail_try = [ln for ln in out.strip().splitlines() if ln.strip()][-1] if out.strip() else ""
            if not ((rc == 5) or ("passed" not in tail_try and "failed" not in tail_try)):
                break
            if attempt == 1:
                print("  ⚠ %-28s 第 1 次**空收集**（0 项）⇒ 自动重试一次" % disp(r))
        if rc == -1:
            continue
        tail = [ln for ln in out.strip().splitlines() if ln.strip()][-1] if out.strip() else ""
        counts = {k: int(v) for v, k in SUM.findall(tail)}
        for k in totals:
            totals[k] += counts.get(k, 0)
        dur = time.time() - t0
        passed = (rc == 0 and counts.get("passed", 0) > 0)
        if counts.get("passed", 0) == 0 and rc == 5:
            empty_roots.append(disp(r))
        if not passed:
            bad_roots.append(disp(r))
        print("  %s %-28s %6.1fs  %s"
              % ("✅" if passed else "🔴", disp(r), dur, tail[:110]))
        if not passed and rc != 5:
            for line in out.strip().splitlines()[-12:]:
                if re.search(r"FAILED|ERROR|assert|Error", line):
                    print("        " + line.strip()[:150])

    print("-" * 88)
    print("合计：passed %d · failed %d · error %d · skipped %d"
          % (totals["passed"], totals["failed"], totals["error"], totals["skipped"]))
    if empty_roots:
        print("⚠ 没收集到测试（**不等于通过**）：%s" % "、".join(empty_roots))
    if bad_roots:
        print("结论：**不通过** —— %s" % "、".join(bad_roots))
        return 1
    print("结论：全部测试根通过 ✅（%d 项）" % totals["passed"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
