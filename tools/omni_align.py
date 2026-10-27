#!/usr/bin/env python3
"""万能插主执行器 · 348 位原生能力全量对齐

口径（按 gbt-omni 规程，不自己发明）：
  R-B 数字现算：条数一律从 caps_registry / capabilities.json 当场读，本文不抄。
  R-A 落点必报可达性：每一位要说清「探了 / 没探 + 为什么」，
      不许笼统写"全部对齐"。
  R-C/R-D 只读扫描器不许被域过滤误杀：判据是
      readonly ∧ 无作用域 ∧ 无参数 ∧ 无确认要求 ⇒ 才敢真探。
  R-E 一律经**唯一门 run_task** 执行，不直连实现（直连等于绕开信封与账本）。

分类（失败必须分类记账，不许笼统说"失败"）：
  ok            真跑通
  unimplemented impl_missing / 未实现（如实）
  needs_params  需要参数才跑（正常，不是坏）
  denied        过授权门被拒（正常，不是坏）
  needs_dep     缺依赖
  error         真异常
  timeout       超时

用法：
  python3 tools/omni_align.py --plan          # 只出计划：会探谁、跳过谁、为什么
  python3 tools/omni_align.py --run           # 真跑（后台建议）
  python3 tools/omni_align.py --report        # 只看上次报告
"""
from __future__ import annotations

import argparse
import json
import signal
import pathlib
import sys
import time
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "state" / "omni_align.json"
PROBE_TIMEOUT = 8          # 单次探活上限（秒）
SKIP_SCOPED = True         # 有作用域的位不探（会触发副作用）


def caps() -> list[dict]:
    """R-B：现算，且两源必须一致，不一致就当场报。"""
    reg = None
    try:
        from gbt_allinone.caps_registry import all_caps
        reg = [dict(c) for c in all_caps()]
    except Exception:                                         # noqa: BLE001
        reg = []
    js = []
    try:
        d = json.loads((ROOT / "data/capabilities.json").read_text(encoding="utf-8"))
        raw = d if isinstance(d, list) else d.get("capabilities", d)
        js = raw if isinstance(raw, list) else list(raw.values())
    except Exception:                                         # noqa: BLE001
        pass
    if reg and js and len(reg) != len(js):
        print("  ⚠ 两源条数不一致 registry=%d json=%d" % (len(reg), len(js)))

    # 🔴 2026-10-28：两源 **schema 不同**，必须按名字合并才看得见全貌：
    #   registry: name status domain desc handler safe requires_params
    #   json    : name domain desc handler params_hint readonly required
    #             required_hint requires_params scopes_static
    #   只读一份会得出"348 位里 0 位只读"这种荒谬结论（实测踩到）。
    by_name: dict[str, dict] = {}
    for row in js:
        if isinstance(row, dict) and row.get("name"):
            by_name[str(row["name"])] = dict(row)
    for row in reg:
        if not isinstance(row, dict) or not row.get("name"):
            continue
        n = str(row["name"])
        merged = by_name.get(n, {})
        merged.update({k: v for k, v in row.items() if v is not None})
        by_name[n] = merged
    merged_rows = list(by_name.values())
    print("  合并后: registry %d + json %d → 去重 %d 位"
          % (len(reg), len(js), len(merged_rows)))
    return merged_rows


def classify(c: dict) -> tuple[str, str]:
    """(决定, 理由)。只有 decide=probe 的才真跑。"""
    name = str(c.get("name") or "")
    if not name:
        return "skip", "无名字"
    if c.get("requires_params"):
        return "skip", "需参数（不瞎跑）"
    if c.get("needs_confirmation"):
        return "skip", "需人工确认"
    # 🔴 scopes_static 在真源里是**字符串**（如「零作用域（空 payload 下不需要票）」），
    #    不是数组。按数组遍历会把它拆成一个个汉字，误判成"处处要票"。
    sc_raw = c.get("scopes_static")
    if isinstance(sc_raw, str):
        noneed = ("零作用域" in sc_raw) or (not sc_raw.strip())
        sc = [] if noneed else [sc_raw]
    elif isinstance(sc_raw, (list, tuple, set)):
        sc = [x for x in sc_raw if x]
    else:
        sc = [] if not sc_raw else [str(sc_raw)]
    if SKIP_SCOPED and sc:
        return "skip", "有作用域 %s（会触发副作用，不盲探）" % ",".join(map(str, sc[:2]))
    if c.get("readonly"):
        return "probe", "只读·无作用域·无参数"
    return "skip", "非只读且未标只读（不盲探）"


class _Timeout(Exception):
    pass


def _alarm(signum, frame):                                  # noqa: ARG001
    raise _Timeout()


def probe(name: str) -> dict:
    """单次探活，**带真超时**。

    🔴 2026-10-28：第一版只写了个 PROBE_TIMEOUT 常量却没实现中断，
       实测在第 121 位挂死，整轮审计停在那里不动（日志 4 分钟不动）。
       现在用 signal.alarm 真打断 —— 挂死的位记 timeout，接着往下走。
    """
    t0 = time.perf_counter()
    try:
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(PROBE_TIMEOUT)
    except Exception:                                         # noqa: BLE001
        pass
    try:
        from gbt_allinone.api import run_task
    except Exception as exc:                                  # noqa: BLE001
        return {"status": "error", "error": "能力层不可用: %s" % exc,
                "ms": 0}
    try:
        r = run_task(name, {})
    except _Timeout:
        return {"status": "timeout", "ms": PROBE_TIMEOUT * 1000,
                "error": "超过 %ds 未返回（已打断）" % PROBE_TIMEOUT}
    except Exception as exc:                                  # noqa: BLE001
        msg = "%s: %s" % (type(exc).__name__, exc)
        return {"status": "error", "error": msg[:200],
                "ms": round((time.perf_counter() - t0) * 1000)}
    finally:
        try:
            signal.alarm(0)
        except Exception:                                     # noqa: BLE001
            pass
    ms = round((time.perf_counter() - t0) * 1000)
    if not isinstance(r, dict):
        return {"status": "ok", "ms": ms, "raw_type": type(r).__name__}
    gr = (r.get("gbt_result") or {})
    res = gr.get("result") or r.get("result") or {}
    status = str(gr.get("status") or r.get("status") or "")
    blob = json.dumps(res if isinstance(res, (dict, list)) else str(res),
                      ensure_ascii=False)[:400]

    if "impl_missing" in blob or status == "unimplemented":
        return {"status": "unimplemented", "ms": ms,
                "reason_code": (res or {}).get("reason_code") or "impl_missing"}
    if status == "denied" or "需要人工授权" in blob:
        return {"status": "denied", "ms": ms}
    if "needs_dependency" in blob or "缺失" in blob and "ModuleNotFound" in blob:
        return {"status": "needs_dep", "ms": ms}
    if "needs_params" in blob or "缺参数" in blob or "requires_params" in blob:
        return {"status": "needs_params", "ms": ms}
    if res.get("ok") is False or r.get("ok") is False:
        return {"status": "error", "ms": ms, "detail": blob[:180]}
    return {"status": "ok", "ms": ms}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()

    if a.report:
        if not OUT.is_file():
            print("  还没有报告，先跑 --run")
            return 1
        d = json.loads(OUT.read_text(encoding="utf-8"))
        print("  生成于:", d.get("at"))
        print("  总数 %s · 探了 %s · 跳过 %s" % (d.get("total"), d.get("probed"), d.get("skipped")))
        for k, v in (d.get("by_status") or {}).items():
            print("    %-14s %d" % (k, v))
        return 0

    items = caps()
    rows = []
    for c in items:
        decide, why = classify(c if isinstance(c, dict) else {})
        rows.append({"name": (c or {}).get("name"), "domain": (c or {}).get("domain"),
                     "decide": decide, "why": why})

    probe_n = sum(1 for r in rows if r["decide"] == "probe")
    skip_n = len(rows) - probe_n
    print("  现算总数: %d 位 · 拟探 %d · 跳过 %d" % (len(rows), probe_n, skip_n))
    print()
    from collections import Counter
    print("  跳过的原因分布：")
    for why, n in Counter(r["why"] for r in rows if r["decide"] == "skip").most_common(10):
        print("    %-46s %d" % (why[:46], n))

    if a.plan:
        print()
        print("  拟探的 %d 位（前 30）：" % probe_n)
        for r in [x for x in rows if x["decide"] == "probe"][:30]:
            print("    %-24s %s" % (r["name"], r["domain"]))
        return 0

    if not a.run:
        print("\n  加 --run 才真跑（经唯一门 run_task）")
        return 0

    print("\n  === 真跑（唯一门 run_task · 单位 %ds 超时）===" % PROBE_TIMEOUT)
    t0 = time.time()
    done = 0
    for r in rows:
        if r["decide"] != "probe":
            r["status"] = "skipped"
            continue
        print("    → %s" % r["name"], flush=True)
        r.update(probe(r["name"]))
        done += 1
        if done % 20 == 0:
            print("    …%d/%d  %s" % (done, probe_n,
                                      "%.0fs" % (time.time() - t0)), flush=True)

    by = Counter(r.get("status") for r in rows)
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "total": len(rows), "probed": probe_n, "skipped": skip_n,
           "elapsed_s": round(time.time() - t0, 1),
           "by_status": dict(by),
           "rows": rows}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n  === 结果 ===")
    for k, v in by.most_common():
        print("    %-14s %d" % (k, v))
    print("\n  报告: state/omni_align.json")

    # R-E：把报告也过一遍唯一门，落进镜像维度（不直接写现实）
    try:
        from gbt_allinone.api import run_task
        body = OUT.read_text(encoding="utf-8")
        r = run_task("mirror_shape", {"path": "state/omni_align.json",
                                      "content": body,
                                      "note": "348 位对齐报告 · omni_align"})
        print("  已 shape 进镜像维度:", (r.get("gbt_result") or r).get("status", "?"))
    except Exception as exc:                                  # noqa: BLE001
        print("  ⚠ 进镜像失败（如实报）: %s" % exc)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已停")
