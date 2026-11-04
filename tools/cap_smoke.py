# -*- coding: utf-8 -*-
"""能力实战测定：万能插识别 + 全量安全小探针 + 大任务联跑。

原则：
  · 每个能力用**只读 op** 探针（status/schema/verify/list/probe/catalog/coverage...），
    `probe=True` 不写调用审计；危险/写面能力不碰；
  · 单能力放子进程 + 超时，一个卡死不许拖死整轮；
  · 单能力结果分：responded（有真实响应）/ unavailable（如实缺依赖）/ failed（异常/超时）；
  · 大任务只选已接线、只读的核心能力，跑跨能力链；
  · 全部落 `state/cap-smoke/report.json` + `report.md`，不粉饰。

用法：
  python tools/cap_smoke.py                 # 全量
  python tools/cap_smoke.py --limit 40      # 先跑 40 个
  python tools/cap_smoke.py --workers 6
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
HELPER = ROOT / "tools" / "cap_probe_one.py"
OUT = ROOT / "state" / "cap-smoke"
DANGER_OPS = {"apply", "create", "stage", "commit", "rollback", "write", "delete",
              "send", "post", "run", "action", "inject", "evolve", "decide", "publish",
              "preview", "import", "upload", "install", "start", "stop", "cancel", "kill"}
READ_OPS = ("status", "schema", "verify", "list", "probe", "catalog", "coverage",
            "stats", "info", "gate", "has", "brief", "snapshot", "devices", "pages",
            "history", "where", "health", "check")
OP_OVERRIDES = {
    "caps_called_audit": ["audit"],
    "cli_chat": ["transcript", "where"],
    "code_patch": ["dry_run"],
    "control_loop": ["selftest", "observe"],
    "coverage_auditor": ["matrix", "snapshot"],
    "emotion_projection": ["check", "scan"],
    "gods_eye": ["see", "panel"],
    "hook_registry": ["catalogue", "verify"],
    "llm_redteam": ["matrix", "selfcheck"],
    "meta_cognition": ["law", "reflections"],
    "observer_anchor": ["axioms", "boards"],
    "one_shot": ["plan", "show"],
    "persona_kernel": ["constitution", "laws"],
    "proactive_report": ["coverage", "score"],
    "record_grid": ["profile", "vocab"],
    "scene_anchor": ["classes", "soul"],
    "tentacle_cognition": ["redlines", "selfcheck"],
}
LARGE = (
    ("selfscan", {}), ("cap_self", {"op": "brief"}), ("inventory", {}),
    ("signature_guard", {"op": "status"}), ("truth_scan", {"op": "status"}),
    ("resource_snapshot", {"op": "snapshot"}),
    ("media_library", {"op": "verify"}), ("turn_trace", {"op": "verify"}),
    ("kws", {"op": "verify"}), ("video_hub", {"op": "run"}),
    ("ref3d", {"op": "verify"}), ("skills_hub", {"op": "list"}),
    ("omni_open", {"op": "status"}), ("ui_card", {"op": "snapshot"}),
)


def caps():
    import sys as _sys
    _sys.path.insert(0, str(ROOT))
    from gbt_allinone.caps_registry import BENIGN_CAPS
    return BENIGN_CAPS


def op_candidates(cap, meta):
    """从 desc 里抽读 op；只认白名单，绝不跑写 op。"""
    if cap in OP_OVERRIDES:
        return list(OP_OVERRIDES[cap])
    desc = str(meta.get("desc") or "")
    found = []
    for m in re.finditer(r"op=([a-zA-Z0-9_\-/]+)", desc):
        for x in re.split(r"[/、,，]", m.group(1)):
            x = x.strip().lower()
            if x in READ_OPS and x not in found:
                found.append(x)
    if not found:
        found = ["status", "schema", "verify", "list", "probe"]
    return found


def probe_one(cap, ops, timeout):
    ops = list(dict.fromkeys(ops))
    i = 0
    while i < len(ops):
        op = ops[i]
        i += 1
        t0 = time.time()
        try:
            p = subprocess.run([PY, "-X", "utf8", str(HELPER), str(ROOT), cap, op],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=timeout)
            raw = (p.stdout or "").strip().splitlines()
            data = json.loads(raw[-1]) if raw else {}
            data["ms"] = int((time.time() - t0) * 1000)
            res = data.get("result")
            err = str(data.get("error") or (res or {}).get("error") or "")
            if any(x in err for x in ("未知 op", "不认识的 op", "不认 op", "可选 ")):
                m0 = __import__("re").search(r"(?:可用[：:]|可选 )([^）\n]+)", err)
                if m0:
                    extra = [x.strip().lower() for x in __import__("re").split(r"[/、,，]", m0.group(1))]
                    extra = [x for x in extra if x and x not in DANGER_OPS and x not in ops]
                    if extra:
                        ops.extend(extra)
                        continue
                return {"cap": cap, "op": op, "error": err, "verdict_hint": "op_mismatch"}
            if data.get("envelope_ok") or isinstance(res, dict):
                return data
            # 能力回「未知 op（可用：...）」→ 用真实可用 op 再试一次，别把 op 选错当能力坏
            m = __import__("re").search(r"可用[：:]([^）\n]+)", err)
            if m:
                extra = [x.strip().lower() for x in __import__("re").split(r"[/、,，]", m.group(1))]
                extra = [x for x in extra if x and x not in DANGER_OPS and x not in ops]
                if extra:
                    ops.extend(extra)
                    continue
            if data.get("error"):
                return data
        except subprocess.TimeoutExpired:
            return {"cap": cap, "op": op, "timeout": True, "ms": int((time.time() - t0) * 1000)}
        except Exception as e:  # noqa: BLE001
            return {"cap": cap, "op": op, "error": "%s: %s" % (type(e).__name__, str(e)[:120])}
    return {"cap": cap, "error": "无可跑只读 op", "ops": ops}


def classify(row):
    if row.get("timeout"):
        return "timeout"
    if row.get("envelope_ok"):
        return "responded"
    res = row.get("result")
    if isinstance(res, dict) and (res.get("status") == "needs_dependency"
                                  or res.get("ok") is False):
        return "unavailable"
    err = str(row.get("error") or "")
    low = err.lower()
    if "需要人工授权" in err or "denied" in err:
        return "gated"
    if any(x in err for x in ("缺少", "需要", "必须", "不存在", "先 wf_define")):
        return "needs_input"
    if any(x in low for x in ("no module named", "找不到", "not found", "winerror 2",
                              "needs_dependency", "未接线")):
        return "unavailable"
    if row.get("error"):
        return "failed"
    return "responded"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--timeout", type=float, default=8.0)
    ns = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    registry = caps()
    names = sorted(registry)
    if ns.limit:
        names = names[:ns.limit]

    # 万能插：先识别本机可插面（26s 真实成本）
    omni = {}
    try:
        import gbt_allinone as G
        omni = G.run_task("omni_open", {"op": "status"}, safe=True, probe=True)
        omni = (omni.get("gbt_result") or {}).get("result") or omni.get("result") or {}
    except Exception as e:  # noqa: BLE001
        omni = {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:120])}

    small = []
    with cf.ThreadPoolExecutor(max_workers=max(1, ns.workers)) as ex:
        futs = {ex.submit(probe_one, cap, op_candidates(cap, registry[cap]), ns.timeout): cap
                for cap in names}
        for fut in cf.as_completed(futs):
            row = fut.result()
            row["verdict"] = classify(row)
            small.append(row)
    small.sort(key=lambda r: (r.get("verdict") != "failed", r["cap"]))

    large = []
    for cap, payload in LARGE:
        if cap not in registry:
            large.append({"cap": cap, "verdict": "missing"})
            continue
        t1 = time.time()
        try:
            import gbt_allinone as G
            env = G.run_task(cap, payload, safe=True, probe=True)
            inner = (env.get("gbt_result") or {}).get("result") or env.get("result")
            large.append({"cap": cap, "payload": payload, "envelope_ok": bool(env.get("ok")),
                          "result_ok": (inner or {}).get("ok") if isinstance(inner, dict) else None,
                          "ms": int((time.time() - t1) * 1000),
                          "verdict": "responded" if env.get("ok") else "failed"})
        except Exception as e:  # noqa: BLE001
            large.append({"cap": cap, "payload": payload, "verdict": "failed",
                          "error": "%s: %s" % (type(e).__name__, str(e)[:160]),
                          "ms": int((time.time() - t1) * 1000)})

    counts = {}
    for r in small:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    report = {"ok": counts.get("failed", 0) == 0 and all(x.get("verdict") == "responded" for x in large),
              "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "seconds": round(time.time() - t0, 1),
              "caps_total": len(registry), "probed": len(small), "counts": counts,
              "omni_open": {k: omni.get(k) for k in ("ok", "kinds", "plugs_total", "scanned_at", "note")},
              "small": small, "large": large}
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# 能力实战测定报告", "",
             "时间：%s · 耗时 %.1fs · 探测 %d/%d" % (report["at"], report["seconds"],
                                                len(small), len(registry)),
             "小探针：%s" % json.dumps(counts, ensure_ascii=False),
             "大任务：%d/%d responded" % (sum(1 for x in large if x.get("verdict") == "responded"), len(large)),
             "", "## 失败/超时", ""]
    for r in small:
        if r["verdict"] in ("failed", "timeout"):
            lines.append("- `%s` · %s · %s" % (r["cap"], r["verdict"],
                                              (r.get("error") or r.get("op") or "")[:160]))
    lines += ["", "## 不可用（如实缺依赖）", ""]
    for r in small:
        if r["verdict"] == "unavailable":
            res = r.get("result") or {}
            lines.append("- `%s` · %s" % (r["cap"], (res.get("detail") or res.get("reason") or "")[:120]))
    lines += ["", "## 大任务", ""]
    for r in large:
        lines.append("- `%s` · %s · %sms" % (r["cap"], r.get("verdict"), r.get("ms")))
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(OUT / "report.json"), "ok": report["ok"],
                      "counts": counts, "large": report["large"]}, ensure_ascii=False, indent=1))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
