#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""满载红灯猎手（F19 专用）—— 把「复现不出来」变成「有回执的复现尝试」。

F19 的原文（台账）：
  「满仓横扫里 `test_regression_stamp.py` 报红，**复现不出来**（同入口单跑、同 store、同批次重跑
    共三次全绿）⇒ 按本仓纪律『一个由负载决定的对错就是错报』，这是一条假红，但**失败用例名没留住**。」

缺的东西只有两件：
  ① **负载**：之前所有复跑都是"空载"的 —— 假红是负载相关，空载当然复现不出来；
  ② **留存**：红了也不记用例名 ⇒ 下次还是"说不清"。
本件就补这两件：造负载 → 反复跑 → **把失败用例名逐条记进回执**（红了照实记，绿了也照实记"X 次未复现"）。
它不改任何判据、不写生产账，只往 `state/load-red-hunt.json` 写一份自己的回执。

用法：
  py -3.14 tools/codex-scripts/load-red-hunt.py                 # 默认：4 个负载进程 · 5 轮 · 目标回归印章
  py -3.14 tools/codex-scripts/load-red-hunt.py --runs 8 --load 6
  py -3.14 tools/codex-scripts/load-red-hunt.py --target gbt_allinone.tests.test_regression_stamp
  py -3.14 tools/codex-scripts/load-red-hunt.py --status        # 只读上次回执
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RECEIPT = os.path.join(ROOT, "state", "load-red-hunt.json")
DEFAULT_TARGET = "gbt_allinone.tests.test_regression_stamp"

# 负载进程：纯 CPU 忙等（不碰盘、不出网）。用 python 自己的循环，免得依赖外部工具。
LOADER = "import time\nend=time.time()+60\nn=0\nwhile time.time()<end:\n    n+=1\n"


def spawn_load(n):
    procs = []
    for _ in range(max(0, n)):
        p = subprocess.Popen([sys.executable, "-c", LOADER],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        procs.append(p)
    return procs


def kill_load(procs):
    for p in procs:
        try:
            p.terminate()
        except Exception:  # noqa: BLE001
            pass
    for p in procs:
        try:
            p.wait(timeout=5)
        except Exception:  # noqa: BLE001
            try:
                p.kill()
            except Exception:  # noqa: BLE001
                pass


def run_once(target, load, timeout=600):
    """在隔离 store 里跑一轮；返回 rc / 失败用例名 / 耗时 / 输出尾巴。"""
    store = os.path.join(tempfile.gettempdir(), "gbt_loadhunt_store")
    env = dict(os.environ)
    env["GBT_STORE_DIR"] = store
    env["PYTHONIOENCODING"] = "utf-8"
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", "-m", "unittest", target, "-v"],
                           cwd=ROOT, capture_output=True, timeout=timeout, env=env)
        out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
        rc = r.returncode
    except subprocess.TimeoutExpired as e:
        out = ((e.stdout or b"") + (e.stderr or b"")).decode("utf-8", "replace")
        rc = -9
    names = []
    for m in re.finditer(r"^(?:FAIL|ERROR):\s+(\S+)\s*\(([^)]+)\)", out, re.M):
        names.append("%s (%s)" % (m.group(1), m.group(2)))
    for m in re.finditer(r"^(?:FAILED|ERROR)\s+(\S+)", out, re.M):
        names.append(m.group(1))
    tail = [ln for ln in out.strip().splitlines() if ln.strip()][-4:]
    return {"rc": rc, "failures": sorted(set(names)), "ms": round((time.time() - t0) * 1000),
            "load_procs": load, "tail": tail}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=DEFAULT_TARGET)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--load", type=int, default=4, help="负载进程数（0=空载对照）")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    if a.status:
        if not os.path.isfile(RECEIPT):
            print("还没有回执：%s" % RECEIPT)
            return 2
        j = json.load(open(RECEIPT, encoding="utf-8"))
        print("上次回执：%s · 目标 %s · 负载 %s · %d 轮 · 复现 %s"
              % (j.get("at"), j.get("target"), j.get("load"), len(j.get("runs") or []),
                 "是" if j.get("reproduced") else "否"))
        for r in (j.get("runs") or []):
            print("  第%d轮 rc=%s %sms 失败=%s" % (r["round"], r["rc"], r["ms"], r["failures"] or "无"))
        return 0

    print("满载红灯猎手 · 目标 %s · 负载 %d 进程 · %d 轮" % (a.target, a.load, a.runs))
    procs = spawn_load(a.load)
    runs = []
    try:
        for i in range(1, a.runs + 1):
            r = run_once(a.target, a.load)
            r["round"] = i
            runs.append(r)
            print("  第%d轮 rc=%s %sms 失败=%s" % (i, r["rc"], r["ms"], r["failures"] or "无"), flush=True)
    finally:
        kill_load(procs)

    bad = [r for r in runs if r["rc"] != 0]
    receipt = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "target": a.target,
        "load": a.load,
        "runs": runs,
        "reproduced": bool(bad),
        "failure_names": sorted({n for r in runs for n in r["failures"]}),
        "note": ("满载下复现：" + "、".join(sorted({n for r in runs for n in r["failures"]})))
        if bad else ("满载 %d 进程 × %d 轮**未复现**（这是回执，不是『不存在』）" % (a.load, a.runs)),
    }
    tmp = RECEIPT + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(receipt, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, RECEIPT)
    print("\n回执 → %s" % RECEIPT)
    print(receipt["note"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
