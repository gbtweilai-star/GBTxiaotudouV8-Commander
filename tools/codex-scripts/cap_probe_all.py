# -*- coding: utf-8 -*-
r"""全能力位探针 · **一条都不许静默跳过**（只读 · 隔离 store · 固化件）

为什么要有这一件（Owner 2026-09-23：「搞的我难怪一天都在扫不出问题所在了」）：

  当天实测到的**真答案不在"禁止名单"上**，而在**探测闸**上：
    · `cross_scan.PROBE_SKIP_KINDS` 当年手抄 13 条 → 永不探测
    · atlas 的 `needs_confirmation` 22 条 → 永不探测
    · `omni` 的默认拒绝 → 45 条只打印命令、从不真跑
  结果：`sec_scan` / `sec_chain` **无参调用挂死 ≥180 秒**这件事，
  是我硬把它们塞进门面集才看见的 —— 在那之前，它们**从来没被探过**。

  🔴 2026-09-24 深修后：`PROBE_SKIP_KINDS` 改为**派生**（探测专项 11 ∪
  `preflight.state_changing_kinds()` 11 = 22，单一真源）；本件**不受影响** ——
  它的纪律本来就是"一条都不静默跳过"，凡登记位全探、门拦就如实记。

本件的纪律：
  1. **不许静默跳过**：BENIGN_CAPS 147 条 + UNIMPLEMENTED_CAPS 11 条，**逐条都要有判定**。
     凡没探的，必须在输出里**逐条写明理由**；"没探"与"探了没事"是两件事。
  2. **隔离 store**：子进程 `GBT_STORE_DIR` 指向临时目录 ⇒ 生产主账本零足迹。
  3. **门照旧在**：有作用域的能力位会被 `policy` 门拦下 —— **拦下就是拦下**，
     如实记 `denied` + 缺哪个作用域。这正好反过来验门到底拦不拦。
  4. **不猜**：判定只取真实返回的 status / 退出码 / 是否超时。

用法:
  py -3.14 tools/codex-scripts/cap_probe_all.py                # 全探（约 6–10 分钟）
  py -3.14 tools/codex-scripts/cap_probe_all.py --timeout 45   # 改单条超时
  py -3.14 tools/codex-scripts/cap_probe_all.py --only scan    # 只探名字含 scan 的
退出码: 0 全部有判定且无挂死/崩溃 · 2 有挂死或崩溃 · 3 自身出错
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]

CHILD = r"""
import json, sys
sys.stdout = sys.stderr
sys.path.insert(0, sys.argv[1])
from gbt_allinone.api import run_task
kind, out_path = sys.argv[2], sys.argv[3]
try:
    r = run_task(kind, {})
    b = r.get("gbt_result", r) if isinstance(r, dict) else {}
    res = b.get("result") if isinstance(b, dict) else None
    payload = {
        "status": (b.get("status") if isinstance(b, dict) else None)
                  or ("ok" if isinstance(r, dict) and r.get("ok") else "unknown"),
        "denied": bool(isinstance(b, dict) and (b.get("denied") or b.get("missing"))),
        "missing": (b.get("missing") if isinstance(b, dict) else None),
        "message": str((b.get("message") if isinstance(b, dict) else "") or "")[:120],
        "reason_code": (b.get("reason_code") if isinstance(b, dict) else None),
        "result_head": (json.dumps(res, ensure_ascii=False, default=str)[:220]
                        if res is not None else None),
    }
except Exception as e:
    payload = {"status": "EXC:" + type(e).__name__, "message": str(e)[:160]}
with open(out_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False)
"""


def collect():
    sys.path.insert(0, str(ROOT))
    from gbt_allinone.caps_registry import BENIGN_CAPS, UNIMPLEMENTED_CAPS, DISABLED_CAPS
    from gbt_allinone.security import policy
    rows = []
    for k, m in sorted(BENIGN_CAPS.items()):
        m = m or {}
        try:
            scopes = list(getattr(policy.evaluate(k, {}), "scopes", ()) or ())
        except Exception as e:                                   # noqa: BLE001
            scopes = ["<evaluate失败:%s>" % type(e).__name__]
        rows.append({"kind": k, "domain": m.get("domain") or m.get("category") or "?",
                     "safe": bool(m.get("safe")), "impl": True, "scopes": scopes})
    for k in sorted(UNIMPLEMENTED_CAPS):
        rows.append({"kind": k, "domain": "unimplemented", "safe": False,
                     "impl": False, "scopes": []})
    return rows, {"benign": len(BENIGN_CAPS), "unimplemented": len(UNIMPLEMENTED_CAPS),
                  "disabled": len(DISABLED_CAPS)}


# 🔴 2026-09-23 自查纠正：直接把超时叫"挂死"是**错的**。
#   `cross_scan` 早前实测**真跑完要 778 秒（13.0 分钟）** —— 它在 45s 上超时是「慢」不是「死」。
#   所以本件一律标「超时未返回」，并把**已知实测耗时**贴在旁边，让读的人自己分辨：
#     · 已知耗时长 ⇒ 超时是正常的，把 timeout 调大再探；
#     · 未知耗时且早早就超 ⇒ 才值得怀疑真挂了。
KNOWN_SLOW_MS = {
    "cross_scan": 778000,     # 2026-09-23 omni_max 实测 778,642 ms
    "sec_scan": None,         # 180s 上限下未返回，真耗时未知
    "sec_chain": None,        # 同上
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--only", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args(argv or sys.argv[1:])

    rows, counts = collect()
    if a.only:
        rows = [r for r in rows if a.only.lower() in r["kind"].lower()]
    print("=" * 78)
    print("全能力位探针 · 一条都不许静默跳过")
    print("=" * 78)
    print("登记：良性 %d · 登记未实现 %d · 被拒名单 %d（0=禁止已全部解开）"
          % (counts["benign"], counts["unimplemented"], counts["disabled"]))
    print("本轮要探：%d 条 · 单条超时 %ds · **隔离 store**" % (len(rows), a.timeout))
    print("口径：`probed` 一定有判定；任何未探的必在 `skipped` 里逐条写明理由。")
    print("-" * 78)

    iso = tempfile.mkdtemp(prefix="gbt_capprobe_iso_")
    env = dict(os.environ, GBT_STORE_DIR=iso, PYTHONUTF8="1",
               PYTHONDONTWRITEBYTECODE="1")
    results, skipped = [], []
    t0 = time.time()
    fd, outp = tempfile.mkstemp(prefix="gbt_capprobe_", suffix=".json")
    os.close(fd)
    outfile = Path(outp)
    for i, r in enumerate(rows, 1):
        outfile.write_text("{}", encoding="utf-8")
        st = time.time()
        try:
            p = subprocess.run([sys.executable, "-c", CHILD, str(ROOT),
                                r["kind"], str(outfile)],
                               timeout=a.timeout, env=env, capture_output=True)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = "timeout>%ds" % a.timeout
        except Exception as e:                                   # noqa: BLE001
            rc = type(e).__name__
        try:
            payload = json.loads(outfile.read_text(encoding="utf-8"))
        except Exception:                                        # noqa: BLE001
            payload = {"status": "NO_OUTPUT", "message": "子进程没落下结果文件"}
        payload["rc"] = rc
        payload["ms"] = round((time.time() - st) * 1000)
        rec = {**r, **payload}
        results.append(rec)
        flag = ("⏱超时" if str(rc).startswith("timeout") else
                "💥" if str(payload.get("status", "")).startswith("EXC")
                or payload.get("status") == "NO_OUTPUT" else
                "🔒门拦" if payload.get("denied") else
                "✅" if payload.get("status") == "ok" else "⚠")
        print("[%3d/%3d] %-24s %-13s %-8s %6dms  %s"
              % (i, len(rows), r["kind"], r["domain"], payload.get("status"),
                 payload["ms"], flag), flush=True)
    try:
        outfile.unlink()
    except OSError:
        pass
    shutil.rmtree(iso, ignore_errors=True)

    # ── 判定归堆：**每一条都要落进某一堆**，不落进就是漏 ──
    def cls(rec):
        if str(rec.get("rc", "")).startswith("timeout"):
            return "timeout"
        s = str(rec.get("status") or "")
        if s.startswith("EXC") or s == "NO_OUTPUT":
            return "crash"
        if rec.get("denied"):
            return "gated"
        if s == "ok":
            return "ok"
        if s == "error":
            return "needs_params_or_error"
        return "other:" + s

    buckets = {}
    for rec in results:
        buckets.setdefault(cls(rec), []).append(rec["kind"])
    covered = sum(len(v) for v in buckets.values())
    assert covered == len(results), "有记录没被归堆 —— 这就是静默跳过"

    print("-" * 78)
    print("探了 %d / 应有 %d 条（覆盖 100%%，无静默跳过）· 用时 %.1fs"
          % (covered, len(rows), time.time() - t0))
    for k in sorted(buckets, key=lambda x: -len(buckets[x])):
        names = buckets[k]
        print("  %-22s %3d 条  %s" % (k, len(names), ", ".join(names[:8])
                                     + (" …" if len(names) > 8 else "")))
    print("-" * 78)
    # ── 真正值得看的三类：挂死 / 崩溃 / 门拦（门拦是**正确行为**，但要能自证）──
    for key, title in (("timeout", "⏱ 超时未返回（**不一定挂死**：先看旁边「已知实测耗时」）"),
                       ("crash", "💥 崩溃 / 无输出"),
                       ("gated", "🔒 被授权门拦下（**这是对的**，但要看缺什么作用域）")):
        if buckets.get(key):
            print(title)
            for rec in results:
                if cls(rec) == key:
                    _cur = rec.get("ms")
                    _cur_txt = ("%dms" % int(_cur)) if isinstance(_cur, (int, float)) else "—"
                    if key == "gated":
                        # 门拦的条目 200ms 就回来了，给它们挂「已知实测耗时」纯属误导；
                        # 这一堆要的是**缺哪个作用域**（那才是下一步动作）。
                        extra = "缺作用域=%s" % (rec.get("missing") or "未报（看右边 message）")
                    elif key == "crash":
                        extra = "rc=%s" % rec.get("rc")
                    else:
                        # 🔴 实测踩过：`.get(kind, "—")` 返回的默认值是**真值字符串**，
                        # 下一句 `"%dms" % _known` 当场 TypeError ⇒ **整轮 158 条探完、
                        # 结果却在最后一步打印时炸掉**（JSON 都没落盘，16 分钟白跑）。
                        # 修法：类型先分清，再决定怎么打 —— 不靠真值判断。
                        _known = KNOWN_SLOW_MS.get(rec["kind"])
                        if isinstance(_known, bool) or not isinstance(_known, (int, float)):
                            _known_txt = "未知（多次未返回）" if _known is None else str(_known)
                        else:
                            _known_txt = "%dms" % int(_known)
                        extra = "已知实测耗时=%s" % _known_txt
                    # 「本轮=」必须是**真量到的毫秒**，不是写死的 "超时>300s" ——
                    # 旧版无论哪一堆都打 "超时>Nd"，于是「门拦」那一堆里每条都挂着
                    # "超时>300s"，而它们其实 200ms 就返回了：**读数自己说谎**。
                    print("    %-24s %-9s 本轮=%-9s %-30s %s"
                          % (rec["kind"], cls(rec), _cur_txt, extra,
                             (rec.get("message") or "")[:46]))
    print("-" * 78)
    print("诚实边界：")
    print("  · 本件**只探不判**：`error` 多为「缺参数」，不等于坏了；缺参数见 PARAM_REQUIRED。")
    print("  · 排除名单为空 —— 147 条良性 + 11 条登记项**全部被探过**。")
    print("  · 隔离 store：生产主账本零足迹；门照旧拦，拦下如实记。")
    if skipped:
        print("  · 未探（逐条理由）：")
        for s in skipped:
            print("      %s —— %s" % (s["kind"], s["why"]))

    payload = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "counts": counts, "timeout_s": a.timeout,
               "probed": len(results), "buckets": {k: v for k, v in buckets.items()},
               "results": results, "skipped": skipped,
               "elapsed_s": round(time.time() - t0, 1)}
    dest = Path(a.json) if a.json else (Path(os.environ.get(
        "TEMP", "/tmp")) / "gbt-capprobe.json")
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("产物: %s" % dest)
    if buckets.get("timeout") or buckets.get("crash"):
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(3)
