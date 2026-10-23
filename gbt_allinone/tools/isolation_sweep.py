# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 隔离模式回归（每个测试文件一个干净进程 + 一个干净 store）。

# gbt-capability: isolation_sweep
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除

## 为什么必须有它（第 39 轮实证）

第 39 轮在**隔离空 store** 里跑 4 个测试文件，冒出一条**全量跑永远看不到的红**：

    test_selftest_exclusion.py::test_legacy_services_do_not_alarm
        by_signal["legacy"] == 0  ⇒  断言 0 >= 1 失败

而它此前**连续 5 次全量都是绿的** —— 因为它依赖"账本里恰好有那条 V5 遗留服务的账"
（原注释自己写着），全量跑时**别的用例把账本喂饱了**，它就蹭绿了。

⇒ **全量绿 ≠ 判据健康**。全量恰恰是"状态被喂饱"的场景，会**系统性掩盖**
"依赖累积状态"的判据；反过来，只看全量也发现不了"只在干净环境才红"的那类。

    ┌ 全量（同进程、状态累积）── 看跨文件污染
    └ 隔离（单文件、空 store）── 看"依赖累积状态"的判据
    **两种都绿，才叫绿。**

本工具负责第二种。它**只报读数、不下判决**：
"隔离下红、全量下绿"是**可疑**（要么判据不自足，要么它本来就需要历史状态），
该不该修由人按内容判 —— 工具替你做判断，就又成了新的错报源。

## 用法

    python -m gbt_allinone.tools.isolation_sweep                # 全部测试文件
    python -m gbt_allinone.tools.isolation_sweep --only fw      # 只跑文件名含 fw 的
    python -m gbt_allinone.tools.isolation_sweep --selftest     # 两把对照
    python -m gbt_allinone.tools.isolation_sweep --json         # 机器可读
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_HERE = Path(__file__).resolve()
_PKG = _HERE.parents[1]          # gbt_allinone/
ROOT = _PKG.parent               # 仓根
TESTS = _PKG / "tests"


def _summary(text: str):
    """从 pytest 尾巴里取 (passed, failed, skipped)，取不到返回 None。"""
    tail = text[-4000:]
    got = {}
    for name in ("passed", "failed", "error", "errors", "skipped"):
        m = re.findall(r"(\d+)\s+%s\b" % name, tail)
        if m:
            got[name] = int(m[-1])
    if "passed" not in got and "failed" not in got:
        return None
    return {"passed": got.get("passed", 0),
            "failed": got.get("failed", 0) + got.get("error", 0) + got.get("errors", 0),
            "skipped": got.get("skipped", 0)}


def run_one(path: Path, timeout_s: int = 300) -> dict:
    """在**干净子进程 + 干净 store** 里跑单个测试文件。"""
    iso = tempfile.mkdtemp(prefix="gbt_iso_sweep_")
    env = dict(os.environ)
    env["GBT_STORE_DIR"] = os.path.join(iso, "store")
    env["GBT_WEB_ADAPTIVE_DB"] = os.path.join(iso, "adaptive.db")
    env["GBT_CALL_GRAPH_DB"] = os.path.join(iso, "callgraph.db")
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("GBT_OWNER_SESSION", None)      # 基线：不许预先置位主人身份
    t0 = time.perf_counter()
    try:
        p = subprocess.run(
            [sys.executable, "-m", "pytest", str(path), "-q", "--no-header",
             "-p", "no:cacheprovider", "--tb=no"],
            cwd=str(ROOT), env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=timeout_s)
        out = p.stdout.decode("utf-8", "replace")
        s = _summary(out)
        if p.returncode == 0:
            # 🔴 2026-09-26 自纠：原来 iso 目录从不清理 —— 一次满仓横扫在 %TEMP% 留下
            #    126 个带 store/两个 db 的 gbt_iso_sweep_* 目录。现在**绿的当场清**；
            #    红的/超时的保留并在行里带路径（归因证据不许当场销毁）。
            shutil.rmtree(iso, ignore_errors=True)
        return {"file": path.name, "rc": p.returncode,
                "ms": round((time.perf_counter() - t0) * 1000),
                "summary": s, "tail": out[-600:], "timeout": False, "iso": iso}
    except subprocess.TimeoutExpired:
        return {"file": path.name, "rc": None,
                "ms": round((time.perf_counter() - t0) * 1000),
                "summary": None, "tail": "timeout>%ss" % timeout_s, "timeout": True,
                "iso": iso}
    except Exception as exc:                                      # noqa: BLE001
        # 起不来（环境炸/pytest 缺失等）也如实成一排，别让整场横扫中途崩掉
        return {"file": path.name, "rc": None,
                "ms": round((time.perf_counter() - t0) * 1000),
                "summary": None, "tail": "%s: %s" % (type(exc).__name__, str(exc)[:160]),
                "timeout": False, "iso": iso}


def _fingerprint(with_rows: bool = False, subdir: str = "") -> dict:
    """整棵（剪枝后）代码树的内容指纹 —— 用来证明**这次扫描期间树没被改**。

    🔴 2026-09-23 第 52 轮加。由来：第 51 轮这一份扫描的读数**被并发写入污染**了
    （`caps_registry.py` 08:59 落在扫描窗口内），而我是**事后按 mtime 考古**才发现的。
    ⇒ 现在起，扫描自己带"扫之前/之后树长什么样"，**干净与否不再靠我事后解释**。
    实现只有一份，在 `scan_scope.tree_fingerprint`（与所有扫描器同一套 `SKIP_DIRS`）。

    `with_rows=True` ⇒ 另带逐文件明细，好在"树被改了"时**指名是谁动的**（第 53 轮加）。
    `subdir` ⇒ **只算依赖面那一刀**（第 56 轮加）：实测依赖面 199 个文件全在包里，
    而近几轮"导致不作收据"的 13 个改动里 **12 个在包外、与本次读数无关**。
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from scan_scope import tree_fingerprint
        return tree_fingerprint(ROOT, with_rows=with_rows, subdir=(subdir or None))
    except Exception as e:                                   # noqa: BLE001
        return {"sha256": None, "files": None, "bytes": None,
                "unreadable": [], "error": "%s: %s" % (type(e).__name__, e)}


def _diff(before: dict, after: dict) -> dict:
    """是谁动的 —— "不作收据"必须能指名，否则又绕回考古（第 53 轮）。"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from scan_scope import diff_trees
        return diff_trees(before, after)
    except Exception as e:                                   # noqa: BLE001
        return {"available": False, "added": [], "removed": [], "changed": [],
                "note": "取不出差异：%s: %s" % (type(e).__name__, e)}


# 依赖面 = 包（**保守超集**：实测依赖面 199 个文件 ⊂ 包内 351+ 个 .py）
DEPS_SUBDIR = "gbt_allinone"


def sweep(only: str = "", timeout_s: int = 300, verbose: bool = True) -> dict:
    fp_before = _fingerprint(with_rows=True)
    dep_before = _fingerprint(with_rows=True, subdir=DEPS_SUBDIR)
    files = sorted(TESTS.glob("test_*.py"))
    if only:
        files = [f for f in files if only in f.name]
    rows = []
    for f in files:
        r = run_one(f, timeout_s=timeout_s)
        rows.append(r)
        s = r["summary"] or {}
        flag = ("超时" if r["timeout"] else
                ("红" if (r["rc"] or 0) != 0 else "绿"))
        if verbose:
            print("%-4s %-40s passed=%-5s failed=%-4s skipped=%-3s %6sms"
                  % (flag, r["file"], s.get("passed", "?"), s.get("failed", "?"),
                     s.get("skipped", "?"), r["ms"]), flush=True)
    fp_after = _fingerprint(with_rows=True)
    dep_after = _fingerprint(with_rows=True, subdir=DEPS_SUBDIR)
    both = bool(fp_before.get("sha256")) and bool(fp_after.get("sha256"))
    changed = (not (fp_before["sha256"] == fp_after["sha256"])) if both else None
    delta = _diff(fp_before, fp_after) if changed else None
    # 🔴 第 56 轮：**收据的有效性看依赖面，不看整仓**。
    #    实测依赖面 199 个文件全在包里；近几轮 13 个"导致不作收据"的改动里 12 个在包外
    #    （`holo_pet_w3/*` · `tools/codex-scripts/*`），**与本次读数无关**。
    dep_both = bool(dep_before.get("sha256")) and bool(dep_after.get("sha256"))
    deps_changed = (not (dep_before["sha256"] == dep_after["sha256"])) if dep_both else None
    dep_delta = _diff(dep_before, dep_after) if deps_changed else None
    if verbose:
        if changed is None or deps_changed is None:
            print("⚠️ 树指纹**取不到** ⇒ 无法证明『扫描期间树没被改』（%s / %s）"
                  % (fp_before.get("error"), dep_before.get("error")))
        elif not deps_changed:
            print("依赖面未变 = True（%d 个文件 / %s…）⇒ **收据成立**"
                  % (dep_after.get("files"), str(dep_after["sha256"])[:12]))
            if changed:
                # 面外动过 —— 要说出来，但它**不影响**这份读数
                names = []
                for kind in ("changed", "added", "removed"):
                    names += (delta or {}).get(kind) or []
                print("   （面外另有 %d 个文件动过：%s%s —— **与本次读数无关**）"
                      % (len(names), "、".join(names[:4]),
                         "…" if len(names) > 4 else ""))
        else:
            print("!! **依赖面在扫描中途被改了** —— 这份读数**不能当收据**，只能当冒烟：")
            print("   扫前 %s…  扫后 %s…"
                  % (str(dep_before["sha256"])[:12], str(dep_after["sha256"])[:12]))
            if not (dep_delta or {}).get("available"):
                print("   ⚠️ %s" % (dep_delta or {}).get("note"))
            else:
                for kind, label in (("changed", "改了"), ("added", "新增"), ("removed", "删了")):
                    ns = dep_delta.get(kind) or []
                    if ns:
                        print("   %s %d 个：%s" % (label, len(ns),
                                                  "、".join(ns[:6]) + ("…" if len(ns) > 6 else "")))
    bad = [r["file"] for r in rows if r["timeout"] or (r["rc"] or 0) != 0]
    # 🔴 2026-09-23 第 52 轮修（**"没扫"被读成了"干净"**）：
    #    实测当场撞到：`--only test_scan_scope`（**没有这个测试文件**）⇒
    #    `扫过 0 个测试文件；红的 = 0` 且**退出码 0** —— 一次**空绿**。
    #    而 `--only` 拼错正是最容易发生的事（本会话第 43 轮同款：审计器"一个文件都没扫到"）。
    #    ⇒ 空集必须**喊出来**，并且**退出码非 0**（fail-closed）。
    vacuous = len(files) == 0
    if verbose and vacuous:
        print("⚠️ **一个测试文件都没扫到** —— 这不是『干净』，是『没扫』；"
              "本次读数**不作数**。请检查 `--only` 是否拼对（或测试目录是否还在）。")
    return {"ok": (not bad) and (not vacuous), "files": len(rows), "failed_files": bad,
            "rows": rows, "vacuous": vacuous,
            "tree_before": fp_before, "tree_after": fp_after, "tree_changed": changed,
            "tree_delta": delta,
            # 🔴 第 56 轮：**收据的有效性看依赖面**。`deps_changed is False` ⇒ 收据成立；
            #    为 True ⇒ 不作收据；为 None ⇒ 无法判定。整仓的 `tree_changed` 只作披露。
            "deps_subdir": DEPS_SUBDIR,
            "deps_before": dep_before, "deps_after": dep_after,
            "deps_changed": deps_changed, "deps_delta": dep_delta,
            "note": ("隔离模式下红的文件：见 failed_files。"
                     "**与全量结果对照**才有意义：隔离红+全量绿 = 判据依赖累积状态（可疑，逐条判）；"
                     "隔离绿+全量红 = 跨文件污染。"
                     # ⚠️ 措辞纪律（第 52 轮自纠）：note 里**不许出现 `tree_changed=True` 这种
                     #    "看着就是取值"的写法** —— 第一版我这么写了，于是**正常那一跑**（指纹未变）
                     #    的 note 里也挂着 `tree_changed=True`，跟上面那行『树指纹未变 = True』
                     #    恰好相反，读者会以为它报了"树被改了"。**字段名照写，取值别照抄。**
                     "读法：**收据看 `deps_changed`**（依赖面 = 包）——它标 True 时本次读数不作收据，"
                     "此时看 `deps_delta` 指名是谁动的；`tree_changed` 只管**整仓**，"
                     "面外改动（如 `holo_pet_w3/*`）**不影响**这份读数，但仍如实列出。"
                     "`vacuous` 字段标 True 时，**一个文件都没扫到**，读数不作数。")}


# ── 两把对照 ────────────────────────────────────────────────────────────────
_CTL_PASS = '''# -*- coding: utf-8 -*-
"""对照：必然通过。"""
import unittest


class T(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(1, 1)
'''

_CTL_FAIL = '''# -*- coding: utf-8 -*-
"""对照：必然失败。"""
import unittest


class T(unittest.TestCase):
    def test_bad(self):
        self.assertEqual(1, 2, "对照用的故意失败")
'''


def selftest() -> int:
    """两把对照：① 必过的文件必须报绿；② 必红的文件必须被报红。

    🔴 2026-09-23 第 50 轮修（**对照文件原来写在真测试目录里，等于给别人递假红**）：
      原来把这两个对照文件写进 `gbt_allinone/tests/`（**共享的真目录**），跑完再删。
      后果：**在那几秒里，任何并发的全量回归都会收集到它们** ——
      而 `_CTL_FAIL` **是故意要红的** ⇒ 别人那一跑会多出两条红，
      **而红的成因跟他的代码毫无关系**。（第 48 轮我自己就因为"不愿给并发会话递假红"
        而**拒绝**往真包里种坏文件；同一件事，这里却一直这么干着，只是没人注意。）
      ⇒ 改写到**临时目录**：对照的**机制一模一样**（让 pytest 去跑一个必然红/必然绿的文件），
        但**不再碰共享的测试树**。
    """
    tmp = Path(tempfile.mkdtemp(prefix="gbt_iso_ctl_"))
    ok_p = tmp / "test_zz_sweep_ctl_pass.py"
    ok_f = tmp / "test_zz_sweep_ctl_fail.py"
    try:
        ok_p.write_text(_CTL_PASS, encoding="utf-8")
        ok_f.write_text(_CTL_FAIL, encoding="utf-8")
        rp = run_one(ok_p)
        rf = run_one(ok_f)
        # 🔴 2026-09-23 第 54 轮修（**自检自己"由负载决定对错"**）：
        #    `green`/`red` 原来都拿 `summary` 当准绳，而 `summary` 来自
        #    `_summary()` —— **正则解析内层 pytest 的人类尾巴**。内层跑崩/被杀时
        #    （内存紧时真会发生，本机现读 `avail ~1 GB / 换页中`）尾巴里没有
        #    "N passed"/"N failed"，`_summary` **如实返回 None** ⇒
        #      green = (rc==0 and {}.get("failed",1)==0) → 1==0 → **False**
        #      red   = (rc!=0 and {}.get("failed",0)>=1) → 0>=1 → **False**
        #    ⇒ 自检打印「✗ 判红：扫描器分不出红绿」——**而扫描器其实分得出**，
        #      是它没读懂输出。**一个由负载决定的对错，就是错报**（第 1745 行那条）。
        #    实测证据：`.scratch/prove_selftest_load_dependence.py` 三种情形逐条列出。
        #    ⇒ `rc` 是**权威信号**（它不依赖解析人类尾巴）；`summary` 只做**自洽性**检查。
        sm_p, sm_f = rp["summary"], rf["summary"]
        timed_out = bool(rp.get("timeout") or rf.get("timeout"))
        # 🔴 2026-09-26 第 50 轮补（**F13 的遗漏面**）：上面只挡了「超时」与「summary 读不出」，
        #    但还有一种**同一族**的情形 —— 内层 pytest **在收集期就被打断**（rc=2）：
        #      子进程 tail 逐字：`collected 0 items / 1 error` +
        #      `FileNotFoundError: [WinError 2]` + `Interrupted: 1 error during collection`
        #    ⇒ **它一个测试都没跑**。此时 `rp["rc"] == 2` ⇒ `green` 算成 False ⇒
        #      自检打印「✗ 判红：扫描器分不出红绿」—— **而扫描器根本没开口**。
        #    实测：第 50 轮定向核对里 `test_selftest_leaves_no_residue` 就是这么红的
        #    （同一台机器、同一分钟，卸掉负载后 ①必过文件 rc=0）。**一个由负载决定的对错，就是错报。**
        #    ⇒ 判据：rc=2 **且** tail 有 `during collection`/`Interrupted` **且** 无摘要
        #      = 「**本次无法判定**」，既不判红也不判绿；其余情形照旧按 rc 判。
        def _never_collected(r: dict) -> bool:
            tail = str(r.get("tail") or "")
            return (r.get("rc") == 2 and r.get("summary") is None
                    and ("during collection" in tail or "Interrupted" in tail))

        inconclusive = _never_collected(rp) or _never_collected(rf)
        green = (rp["rc"] == 0) and (sm_p is None or sm_p.get("failed", 1) == 0)
        red = (rf["rc"] not in (0, None)) and (sm_f is None or sm_f.get("failed", 0) >= 1)
        print("① 必过文件 → 报绿 =", green, "| rc =", rp["rc"], "| summary =", sm_p)
        print("② 必红文件 → 报红 =", red, "| rc =", rf["rc"], "| summary =", sm_f)
        if sm_p is None or sm_f is None:
            print("   （有 summary 读不出 ⇒ **不是『扫描器分不出红绿』**，只是没读懂输出；"
                  "判红绿看 rc。）")
        if inconclusive:
            print("   ⚠️ 内层 pytest **收集期就被打断**（rc=2 · 一个测试都没跑）⇒ **本次无法判定**："
                  "这既不是「扫描器分不出红绿」，也不是「扫描器没问题」。")
        if timed_out:
            print("   ⚠️ 对照跑超时 ⇒ **本次无法判定**（这不等于扫描器坏了）")
        # 顺带钉一条：**共享测试树里不许留下任何对照文件**（第 50 轮修的那件事的守门句）
        residue = sorted(p.name for p in TESTS.glob("test_zz_sweep_ctl_*.py"))
        print("共享测试树里无对照残留 =", not residue, ("残留：%s" % residue) if residue else "")
        verdict = green and red and not residue and not timed_out and not inconclusive
        print("结论：", "两把对照都过 ✅" if verdict
              else ("✗ 判红：本次无法判定（对照超时或收集期被打断）"
                    if (timed_out or inconclusive)
                    else "✗ 判红：扫描器分不出红绿（或有残留）"))
        # 退出码：**沿用本函数原有的契约** —— 跑不成/判不出都返回 1（非零），
        # 「无法判定」与「判红」的区别**由上面那两行结论文字承担**。
        # 🔴 自纠（2026-09-26 第 50 轮）：我一度把"无法判定"改成返回 **2**，
        #    结果被本文件自己的用例 `test_timeout_says_cannot_tell_not_scanner_broken` 当场抓红
        #    （它钉的是 `rc == 1`，且超时那条路**本来**就是"打印无法判定 + 返回 1"）。
        #    ⇒ **我发明了一个新退出码，却没先查这个函数已有的契约。** 已改回 1。
        #    （要区分「判红」与「无法判定」的调用方，看**输出文字**；要真正给码，应先改契约再改用例。）
        return 0 if verdict else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        print("临时对照目录已清干净 =", not tmp.exists())


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="隔离模式回归（单文件 + 空 store）")
    ap.add_argument("--only", default="", help="只跑文件名含该子串的")
    ap.add_argument("--timeout", type=int, default=300, help="单文件超时秒")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    r = sweep(only=a.only, timeout_s=a.timeout, verbose=not a.json)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print()
        print("扫过 %d 个测试文件；隔离模式下红的 = %d" % (r["files"], len(r["failed_files"])))
        for n in r["failed_files"]:
            print("   -", n)
        print(r["note"])
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
