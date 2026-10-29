#!/usr/bin/env python
# gbt-capability: subprocess
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""run-all-tests.py —— 全仓测试**普查**（不是抽样）。

为什么要有它
------------
2026-09-25 排雷时发现：仓里长期存在**红着的判据没人管**（`test_false_report_audit.py`
因为两条行号锚失效而长期 FAILED，而处置方法就写在被审计文件自己的注释里）。
零散跑十几个文件看不出全貌 —— 必须**全量跑一遍，把所有红收上来**，
再逐个归因（是我改坏的？还是老账？），否则"自检全过"这句话永远没有依据。

做法
----
逐个 `test_*.py` 直接跑（本仓口径：`python -m unittest` 在绑生产 store 时会拒绝，
所以**逐个文件直跑**），每个文件独立进程 + 独立超时，互不污染。

产出
----
* 屏幕：一行一文件的 通过/失败/超时 + 末尾汇总
* `--json out.json`：完整明细（含每个失败用例名），供后续归因

用法
----
    python tools/codex-scripts/run-all-tests.py                 # 全量
    python tools/codex-scripts/run-all-tests.py --filter contract
    python tools/codex-scripts/run-all-tests.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "gbt_allinone" / "tests"
PY = sys.executable


def run_one(path: Path, timeout: float, env: dict) -> dict:
    """跑一个测试文件。

    🔴 2026-09-25 **自纠（第一版跑法错了）**：第一版是「直接 `python <文件>`」。
       实测：这样跑时 `sys.path[0]` 是**脚本所在目录**（`gbt_allinone/tests`），
       不是仓根 ⇒ `import gbt_allinone` 失败 ⇒ 报
       `ModuleNotFoundError: No module named 'gbt_allinone'`。
       我据此报了"17 个测试加载不起来" —— **那是假警报**。
       实测对照（`test_absorb_loop.py`）：
           直接跑文件              → ModuleNotFoundError
           `python -m unittest …`  → OK（17 项）
           从仓根跑（cwd 在 path） → OK（17 项）
       全仓 100 个文件里 **79 个自带 `sys.path` 引导**、**21 个没有** ⇒ 两种跑法并存，
       没有引导的那些**必须从仓根跑**（本仓口径也是 `-m unittest`）。
       ⇒ 现在改成 **`python -m unittest gbt_allinone.tests.<name>` + `PYTHONPATH=仓根`**，
         这样两种文件都能跑；同时保留"0 个用例"的如实标记（有些 test_*.py 根本不是 unittest 模块）。
    """
    t0 = time.time()
    mod = "gbt_allinone.tests." + path.stem
    try:
        p = subprocess.run([PY, "-m", "unittest", mod], cwd=str(ROOT), env=env,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"file": path.name, "result": "TIMEOUT", "ran": None,
                "secs": round(time.time() - t0, 1), "fails": [], "tail": "", "via": "m"}
    out = (p.stdout or "") + (p.stderr or "")
    ran = None
    m = re.search(r"Ran (\d+) tests?", out)
    if m:
        ran = int(m.group(1))
    if re.search(r"(?m)^OK", out):
        res = "OK"
    elif re.search(r"(?m)^FAILED", out):
        res = "FAILED"
    elif ran == 0:
 # **收集为 0 不等于出错**：pytest 风格的文件（无 unittest.TestCase）
        #    在 `-m unittest` 下必然收集 0 个，且 `unittest` 会以非零码退出并喊
        #    "NO TESTS RAN"。第一版我把它归成 ERROR ⇒ 汇总里把它们列成"未过"，
        #    **与紧接着 pytest 跑出 156 passed 的事实自相矛盾**。
        #    ⇒ 单独一类 NO_TESTS；真正的判词交给第二遍 pytest。
        res = "NO_TESTS"
    elif p.returncode != 0:
        res = "ERROR"
    else:
        res = "?"
    fails = re.findall(r"(?m)^(?:FAIL|ERROR): (\S+)", out)
    return {"file": path.name, "result": res, "ran": ran, "via": "m",
            "secs": round(time.time() - t0, 1), "fails": fails[:20],
            "tail": "\n".join(out.strip().splitlines()[-4:])[:400]}


def available_mb():
    """本机**可用物理内存**（MB）。读不到 ⇒ 返回 None（不许瞎猜一个数）。"""
    try:
        import ctypes

        class _MEMSTATUS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        st = _MEMSTATUS()
        st.dwLength = ctypes.sizeof(_MEMSTATUS)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return None
        return int(st.ullAvailPhys // (1024 * 1024))
    except Exception:  # noqa: BLE001
        return None


def scope_threshold(min_free_mb: float, filtered: bool) -> float:
    """**按范围给阈值** —— 全量与"只看几个文件"不该用同一把尺子。

    🔴 为什么加（2026-09-26 第 50 轮）：连续 6 轮内存都在 200–550MB，全量被闸挡着 ⇒
    **想做的验证一直做不了**。但"挡全量"和"挡三个文件的定向跑"是两件事：
      · 全量的结论是「**整个仓**都绿」—— 那个断言需要机器有余量，否则会拿负载假红当代码坏了；
      · 定向跑（`--filter`）的结论只是「**这几个文件**绿」—— 范围小、内存需求小，
        而且**本次范围会印在抬头里**，不会被误读成全量。
    ⇒ 所以：全量用 `min_free_mb`（默认 700）；带 `--filter` 时用 `min(min_free_mb, 250)`。
    **这不是放水**：全量那把尺子一字未动，且定向跑必须显式给 `--filter`（想蒙混就得主动缩小范围，
    而缩小范围本身会让结论变小、并被打在抬头里）。`--force` 仍然可用，且仍会警告。
    """
    return float(min(min_free_mb, 250.0)) if filtered else float(min_free_mb)


def threshold_for(n_files: int, total_files: int, min_free_mb: float = 700.0) -> float:
    """**按"这次要跑几个文件"给阈值** —— 结论有多大，就要求多少余量。

    🔴 为什么从"按范围两档"再往前走一步（2026-09-26 第 51 轮）：
      第 50 轮我做了"全量 700 / 定向 250"两档，但那条线还是**拍出来的**：
      跑 3 个文件与跑 60 个文件都算"定向"，都按 250 判 —— 而它们要的内存差得远。
      ⇒ 现在按**文件数**线性给：`180 + 4.3×n`，上限仍是 `min_free_mb`。
        实测口径（本机 124 个测试文件）：
          1 个 → 184MB · 6 个 → 206MB · 20 个 → 266MB · 60 个 → 438MB · 124 个（全量）→ **700MB**
      **全量那把尺子一字未动**（`n_files >= total_files` 直接回 `min_free_mb`）；
      `total_files` 由调用方**现数**传入，所以本函数里**没有任何写死的总数**。
    ⚠️ 它管的只是"**看起来**够不够跑完"，不是保修（真正的保证是跑完后的读数自洽）。
    """
    if n_files >= total_files:
        return float(min_free_mb)
    return float(max(180.0, min(float(min_free_mb), 180.0 + 4.3 * n_files)))


def memory_verdict(free_mb, min_free_mb):
    """纯函数：**这次普查在负载上站不站得住**。返回 (能不能跑, 一句话为什么)。

    🔴 为什么要这道闸（两次实跑换来的，不是理论风险）：
      · 第 42 轮满仓横扫里 `test_isolation_sweep` 报 rc=2，子进程 tail 是
        `FileNotFoundError [WinError 2]` + `Interrupted: 1 error during collection`
        —— **内层 pytest 一个测试都没跑**；卸掉负载后同一个探针连跑两次都是绿。
      · 第 43 轮复跑**26 分钟没回来**（常态 4–5 分钟）⇒ 去量机器：**可用 0.08 GB**、
        提交 30.8 GB vs 物理 7.5 GB（重度换页）。
      ⇒ **一个由负载决定的对错，就是错报。** 认不出来的"红"比没有读数更坏 ——
        它会被人当成"代码坏了"去修，把假红制度化。
      ⇒ 所以默认**不在内存被压满时开跑**，并给出可操作的两条出路（等一会儿 / 显式 --force）。

    `free_mb=None`（平台读不到）⇒ **放行但标注**：读不到 ≠ 有问题，也 ≠ 没问题。
    """
    if free_mb is None:
        return True, "读不到可用内存（非 Windows 或接口不可用）⇒ 本次不判负载，如实标注"
    if free_mb >= min_free_mb:
        return True, "可用 %d MB ≥ 阈值 %d MB" % (free_mb, min_free_mb)
    return False, ("可用仅 %d MB < 阈值 %d MB ⇒ 满仓横扫在这种负载下会出**假红**"
                   "（实测证据见本函数 docstring）" % (free_mb, min_free_mb))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--filter", default=None, help="只跑文件名含该子串的")
    ap.add_argument("--timeout", type=float, default=300.0, help="单文件超时秒数")
    ap.add_argument("--json", default=None)
    ap.add_argument("--min-free-mb", type=float, default=700.0,
                    help="可用内存低于这个数就**不开跑**（默认 700MB）—— 防止把负载假红读成代码坏了")
    ap.add_argument("--force", action="store_true",
                    help="明知内存紧也照跑（结果自行按『负载污染』对待）")
    ap.add_argument("--batch", default="",
                    help="分批跑：`--batch 2/4` = 只跑第 2 批（共 4 批）。"
                         "内存紧时用它把全仓拆成几段跑完 —— **每批都会印出自己的范围**，"
                         "拼起来才是全仓结论（分段跑出来的绿**不等于**一次全量的绿）")
    ap.add_argument("--no-pytest", action="store_true",
                    help="跳过第二遍：不把 unittest 收集为 0 的文件交给 pytest 重跑")
    args = ap.parse_args()

    # 负载闸**不在这里** —— 它被移到「选出本次要跑哪些文件」之后（见下面 `threshold_for` 那段）：
    # 阈值要按**文件数**取，那就得先知道文件数。第 50 轮它在这里时只能按"全量/定向"两档拍。

    env = dict(os.environ)
    # 本仓口径：必须隔离 store（否则测试包守卫会拒绝，或写脏生产）
    env.setdefault("GBT_STORE_DIR", str(ROOT / ".scratch" / "alltests-store"))
    env.setdefault("PYTHONIOENCODING", "utf-8")
 # 2026-09-25 **第二处自纠：绝不要设 PYTHONPATH。**
    #    我第一版修完跑法后顺手加了 `PYTHONPATH=仓根` —— 那是**画蛇添足且有害**：
    #    `python -m unittest` 本身就会把 **cwd（`''`）** 放进 sys.path，
    #    仓根已经在里面了，`import gbt_allinone` 本来就成立。
    #    而额外的 `PYTHONPATH=仓根` 会让 `test_dependency_face` 把"注入面"测成 `.`：
    #        设 PYTHONPATH   → FAILED（注入面落在非剪枝区：. ⇒ 收据既看不见又不覆盖 = 真洞）
    #        不设 PYTHONPATH → OK (skipped=1)
    #    ⇒ 那是**我自己的环境挖出来的洞**，测试报得对，错的是我。
    #    若不拆掉，这支普查器会让这条测试**每次都被误判成红**（把假红制度化）。
    env.pop("PYTHONPATH", None)

    files = sorted(TESTS.glob("test_*.py"))
    _total_files = len(files)                      # 🔴 现数（不写死总数）
    if args.filter:
        files = [f for f in files if args.filter in f.name]
        if not files:
 # 2026-09-26 自纠：--filter 拼错时原版会空跑 0 个文件然后退出 0（"全绿"）——
            #    isolation_sweep 对同款「空绿」已立过判据：一次**没扫**不许当干净。
            print("🔴 --filter %r 没有匹配到任何测试文件 —— 本次一个都没扫，不许当全绿" % args.filter)
            return 2
    _batch_note = ""
    if args.batch:
        # 分批：内存紧时把全仓拆成几段跑完。**每批印出自己的范围** —— 拼起来才是全仓结论。
        try:
            _i, _n = (int(x) for x in str(args.batch).split("/", 1))
            if not (1 <= _i <= _n) or _n < 1:
                raise ValueError
        except Exception:  # noqa: BLE001
            print("🔴 --batch 用法：`--batch 2/4`（1 ≤ i ≤ N）")
            return 4
        import math as _math
        _size = _math.ceil(len(files) / _n)
        _all = files
        files = _all[(_i - 1) * _size: _i * _size]
        _batch_note = "第 %d/%d 批（%d 个 / 全 %d 个）" % (_i, _n, len(files), _total_files)
        if not files:
            print("🔴 第 %d/%d 批是空的 ⇒ 批号超出范围" % (_i, _n))
            return 4

    # ── 开跑前的负载闸（有意挡在**跑之前**：跑完再标注就晚了，红已经产生）────────
    # 阈值按**这次要跑几个文件**取（见 `threshold_for`）：全量那把尺子未动（默认 700MB），
    # 小批量/分批走低档 —— 但**抬头必须印出本次范围**，结论只覆盖这几个文件。
    free_mb = available_mb()
    _thr = threshold_for(len(files), _total_files, args.min_free_mb)
    can_run, why = memory_verdict(free_mb, _thr)
    print("本次范围：%s / 共 %d 个测试文件（阈值 %.0f MB —— %s）"
          % ((_batch_note or ("**定向 %d 个**：文件名含 %r 的" % (len(files), args.filter))) if (args.batch or args.filter)
             else "**全量 %d 个**" % len(files),
             _total_files, _thr,
             "全量档（一字未动）" if len(files) >= _total_files else "按文件数缩放的定向档"))
    print("负载读数：可用内存 %s · %s"
          % (("%d MB" % free_mb) if free_mb is not None else "读不到", why))
    if _batch_note:
        print("⚠️ **分批跑**：这一批的绿只覆盖这一批；**拼起来才是全仓结论**，"
              "而「分段绿」与「一次全量的绿」不是同一件事（分段之间可能有相互影响）。")
    if not can_run and not args.force:
        print("")
        print("🔴 **本次不开跑**（这是判据，不是建议）：%s" % why)
        print("   三条出路：① 等内存宽松些再跑（本机内存被并发活儿压着时抖动很大）；")
        print("             ② 只跑你真正要看的那几个文件：加 `--filter <文件名子串>`"
              "（跑得越少、要求的余量越小，抬头会写明本次范围）；")
        print("             ③ 明知在压着也要全量跑 ⇒ 加 `--force`，但那份结果**只能当『负载污染样本』**，")
        print("                不许当成『代码坏了』的证据。")
        return 3
    if not can_run and args.force:
        print("⚠️  --force：明知内存紧仍开跑 ⇒ **这份结果不许当权威读数**（可能含负载假红）。")
        print("   本次范围 %d/%d 个文件。" % (len(files), _total_files))
    print()
    print("全量普查：%d 个测试文件（单文件超时 %.0fs，store=%s）"
          % (len(files), args.timeout, env["GBT_STORE_DIR"]))
    print()

    rows = []
    time.time()
    for i, f in enumerate(files, 1):
        r = run_one(f, args.timeout, env)
        rows.append(r)
        flag = {"OK": "✅", "FAILED": "❌", "ERROR": "❌", "TIMEOUT": "⏰", "?": "?",
                "NO_TESTS": "🏃"}[r["result"]]
        print("%3d/%d %s %-46s ran=%-4s %5.1fs %s"
              % (i, len(files), flag, r["file"], r["ran"], r["secs"],
                 ("失败 %d 个: %s" % (len(r["fails"]), ", ".join(r["fails"][:3]))) if r["fails"] else ""))

    ok = [r for r in rows if r["result"] == "OK"]
    bad = [r for r in rows if r["result"] not in ("OK", "NO_TESTS")]
    zero = [r for r in rows if r["result"] == "NO_TESTS" or (r["ran"] == 0)]

 # 2026-09-25 **第三处自纠：unittest 收不到 ≠ 这个文件没有测试。**
    #    实测有 8 个文件是 **pytest 风格**（没有 unittest.TestCase，但有 10~41 个 `def test_*`）：
    #    `-m unittest` 对它们收集到 0 个用例 ⇒ 我第一版据此把它们当成"跑不起来"，
    #    实际用 pytest 跑是 **156 passed, 1 skipped** —— 全是好的。
    #    ⇒ 这里补一遍：对 unittest 收集为 0 的文件，改用 pytest 重跑，并**分开报**，
    #      不把"工具跑不了"混进"测试没过"。
    py_rows = []
    if zero and not args.no_pytest:
        names = [str(TESTS / r["file"]) for r in zero]
        print()
        print("--- unittest 收集为 0 的 %d 个文件，改用 pytest 重跑 ---" % len(names))
        t0 = time.time()
        try:
            p = subprocess.run([PY, "-m", "pytest", "-q"] + names, cwd=str(ROOT), env=env,
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=args.timeout * max(2, len(names)))
            out = (p.stdout or "") + (p.stderr or "")
            tail = "\n".join(out.strip().splitlines()[-6:])
            m = re.search(r"(\d+) passed", out)
            f = re.search(r"(\d+) failed", out)
            py_rows = [{"file": r["file"], "via": "pytest"} for r in zero]
            print("  pytest 合计: %s passed / %s failed  （%.1fs）"
                  % (m.group(1) if m else "?", f.group(1) if f else "0", time.time() - t0))
            print("  " + tail.replace("\n", "\n  "))
            if p.returncode != 0:
                bad = bad + [{"file": r["file"], "result": "PYTEST_FAIL", "ran": None,
                              "secs": 0, "fails": [], "tail": tail} for r in zero]
        except Exception as exc:  # noqa: BLE001
 # 2026-09-26 自纠：pytest 二遍跑不动（超时/异常）时原版只印一行就当没事 ——
            #    这批文件停在 NO_TESTS，而 bad 的收集条件不含 NO_TESTS ⇒
            #    "pytest 文件一个没验证成"却计"未过 0 个"退出 0（报成功但没干）。
            #    现在如实记成 PYTEST_ERROR 进 bad：它不是"测试红"，是"没跑成"，fail-closed。
            print("  pytest 跑不动：%s: %s" % (type(exc).__name__, exc))
            bad = bad + [{"file": r["file"], "result": "PYTEST_ERROR", "ran": None,
                          "secs": 0, "fails": [], "tail": str(exc)[:200]} for r in zero]

    print()
    print("=" * 78)
    print("unittest 风格：通过 %d / %d" % (len(ok), len(rows)))
    if py_rows:
        print("pytest  风格：%d 个文件（见上面的 pytest 合计）" % len(py_rows))
    print("合计：unittest 通过 %d ，pytest 通过见上，未过 %d 个" % (len(ok), len(bad)))
 # 2026-09-25 补：**把「超时」与「失败」分开报**。
    #    由来（一手）：我连着几轮用 `--timeout 180` 覆盖了本工具的默认 300 ⇒
    #    `test_framework.py`（单跑现读 **137.9s / 148 条**）在满仓横扫里被 180s 掐断，
    #    汇总却写「未过 1 个」—— 读的人会当成**红了**，而真相是**跑不完 = 本次无法判定**。
    #    本仓在 `test_isolation_sweep` 上已立过同一条口径：「超时 ⇒ 说『本次无法判定』，
    #    **不许**说成『扫描器分不出红绿』」。这里照同一条办。
    _to = [r for r in bad if r.get("result") == "TIMEOUT"]
    if _to:
        print("  ⏰ 其中**超时 %d 个**（本次无法判定，**不等于红**）：%s"
              % (len(_to), "、".join(r["file"] for r in _to)))
        print("     ⇒ 提高 --timeout（本工具默认 300s）后单独复跑；或先量一次它的单跑耗时。")
    if bad:
        print()
        print("未过清单：")
        for r in bad:
            print("  [%s] %-46s ran=%-4s" % (r["result"], r["file"], r["ran"]))
            for x in r["fails"][:6]:
                print("        · %s" % x)
    if args.json:
        Path(args.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
        print()
        print("明细已写", args.json)
 # 2026-09-26 自纠：原来无条件 return 0 —— 调用方/CI 无法用退出码区分"全绿"与"未过 8 个"。
    #    现在口径：0=全绿 · 1=有未过 · 2=定向空扫 · 3=负载闸拒绝 · 4=--batch 用法错。
    #    PYTEST_ERROR/PYTEST_FAIL 都在 bad 里 ⇒ 一并算"未过"，不许静默归零。
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
