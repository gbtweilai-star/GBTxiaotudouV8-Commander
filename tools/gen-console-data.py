# -*- coding: utf-8 -*-
"""生成控制台数据（state/console-data.js）——给 file:// 直开的控制台用。

为什么不写 JSON：file:// 页面 fetch 本地 JSON 会被 Chrome 的 CORS 挡死；
写成 `window.GBT_CONSOLE = {...}` 的 JS 文件，`<script src>` 直接可用，离线也能看。

用法：python tools/gen-console-data.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

OUT = REPO / "state" / "console-data.js"

def _engine_ctx(base):
    """如实读引擎真实上下文窗口（/props 的 n_ctx）；读不到返回 None（界面显示 —），不编造。"""
    if not base:
        return None
    try:
        import urllib.request
        with urllib.request.urlopen(str(base).rstrip("/") + "/props", timeout=2) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
        return ((j.get("default_generation_settings") or {}).get("n_ctx")) or None
    except Exception:
        return None



def _cap(kind, payload=None):
    import gbt_allinone as g
    try:
        r = g.run_task(kind, payload or {}, probe=True)["gbt_result"]["result"]
        return r if isinstance(r, dict) else {}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:80])}


def build() -> dict:
    from gbt_allinone.caps_registry import BENIGN_CAPS
    from gbt_allinone import energy_core as E
    from gbt_allinone.tentacle import commander as C
    from gbt_allinone.tentacle import skills_hub as SH
    from gbt_allinone.tentacle import doc_counts as DC

    caps = BENIGN_CAPS
    safe = sum(1 for v in caps.values() if v.get("safe", True))

    try:
        alive = C.alive()
    except Exception as e:  # noqa: BLE001
        alive = {"ok": False, "error": str(e)[:80]}
    try:
        w = C.weights()
    except Exception:  # noqa: BLE001
        w = {}
    try:
        meter = E.meter(limit=20)
        breaker = E.breaker_state()
    except Exception:  # noqa: BLE001
        meter, breaker = {}, {}

    skills = SH.run("list")
    validate = SH.validate()
    docs = DC.check()

    panel = _cap("orchestration", {"op": "panel", "limit": 8})
    ledger = panel.get("ledger_recent") or panel.get("rows") or []

    # 域分布（给"记忆图"当节点：每个域一个节点，大小=能力数）
    import collections
    by_dom = collections.Counter((v.get("domain") or "?") for v in caps.values())
    domains = [{"domain": d, "count": n} for d, n in by_dom.most_common(14)]

    # 技能清单（给左栏"消息处理器"当流事件用）
    skill_names = [s["name"] for s in (skills.get("skills") or [])][:24]

    # 功能表：385 位全量（前端可搜索/按域筛）
    cap_items = []
    for name, meta in caps.items():
        cap_items.append({
            "name": name,
            "domain": meta.get("domain") or "?",
            "safe": bool(meta.get("safe", True)),
            "desc": (meta.get("desc") or "")[:140],
        })
    cap_items.sort(key=lambda x: (x["domain"], x["name"]))

    # 技能栏：每个技能一张卡（名称/描述/来源/refs 数/合规）
    skill_items = []
    for s_name in (skills.get("skills") or []):
        nm = s_name.get("name")
        refs = []
        try:
            d = SH._dir_of({"path": s_name.get("path") or ""}).parent
            rp = d / "references"
            if rp.is_dir():
                refs = [str(x.relative_to(d)).replace("\\", "/") for x in rp.rglob("*") if x.is_file()]
        except Exception:  # noqa: BLE001
            refs = []
        skill_items.append({
            "name": nm,
            "source": s_name.get("source"),
            "desc": (s_name.get("desc") or "")[:160],
            "refs": refs,
            "path": s_name.get("path"),
        })

    # 域全量（图表用）
    all_domains = [{"domain": d, "count": n} for d, n in by_dom.most_common()]

    # 最近编排流水（给右栏"行动日志"/仪表盘）：直接读账本尾部，结构稳定
    import json as _json
    import collections as _collections
    flow = []
    ledger_path = REPO / "state" / "orchestration-ledger.jsonl"
    if ledger_path.is_file():
        tail = [ln for ln in ledger_path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()][-12:]
        for ln in tail:
            try:
                r = _json.loads(ln)
            except Exception:  # noqa: BLE001
                continue
            flow.append({"at": r.get("at"), "action": r.get("action"),
                         "target": r.get("target"), "result": r.get("result")})

    # 触手职业表（tools/gen-professions.py 产出；「职业」视图用）
    professions = None
    prof_path = REPO / "data" / "professions.json"
    if prof_path.is_file():
        try:
            professions = _json.loads(prof_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            professions = None

    # 真实穿透扫描数据（tools/export-scan-data.py 产出；给"穿透扫描"视图用）
    scan = None
    scan_path = REPO / "state" / "scan-data.json"
    if scan_path.is_file():
        try:
            scan = _json.loads(scan_path.read_text(encoding="utf-8"))
            for sc in (scan.get("scans") or []):
                sc["unit_details"] = (sc.get("unit_details") or [])[:2000]
        except Exception:  # noqa: BLE001
            scan = None

    # 最近实际调用（给 3D 触手点亮）：读 store/audit.jsonl 尾部，按事件(=能力位)计数
    pulse = []
    audit_path = REPO / "gbt_allinone" / "store" / "audit.jsonl"
    if audit_path.is_file():
        try:
            lines = audit_path.read_text(encoding="utf-8", errors="replace").splitlines()[-800:]
            cnt = _collections.Counter()
            for ln in lines:
                try:
                    ev = _json.loads(ln).get("event") or ""
                except Exception:  # noqa: BLE001
                    continue
                if ev:
                    cnt[ev] += 1
            pulse = [{"cap": k, "n": v} for k, v in cnt.most_common(40)]
        except Exception:  # noqa: BLE001
            pulse = []

    # ── 守卫：verdict 只给结论；details 给「为什么」（2026-11-07 红黄追踪）──
    # 原来只取 verdict，APP 上看到 signature · missing / inventory · foreign_found /
    # legacy · legacy_found 三条红，却看不到缺的是哪几页、异物是什么、旧物在哪。
    # 这里把能力位已经算出来的明细原样带出去（不二次解释、不改 verdict）。
    g_self = _cap("selfscan")
    g_sig = _cap("signature_guard", {"scope": "all"})
    g_inv = _cap("inventory")
    g_leg = _cap("legacy_guard", {"op": "status"})
    g_alr = _cap("alerts", {"op": "recent"})
    _sigs = (g_sig.get("missing") or [])[:12]
    _inv_items = g_inv.get("items") or {}
    _leg_cats = g_leg.get("categories") or {}
    guard_details = {
        "selfscan": {
            "verdict": g_self.get("verdict"),
            "routing": ((g_self.get("sections") or {}).get("routing") or {}),
            "modules": ((g_self.get("sections") or {}).get("modules") or {}),
            "audit_runtime_faults": (((g_self.get("sections") or {}).get("audit") or {})
                                     .get("runtime_faults")),
        },
        "signature": {"pages_checked": g_sig.get("pages_checked"),
                      "missing_count": len(g_sig.get("missing") or []),
                      "missing": _sigs,
                      "restored_count": len(g_sig.get("restored") or [])},
        "inventory": {"foreign": _inv_items.get("foreign") or [],
                      "runtime": _inv_items.get("runtime") or [],
                      "dual_view": g_inv.get("dual_view") or {}},
        "legacy": {"categories": _leg_cats,
                   "notes": g_leg.get("notes") or {}},
        "alerts": {"quiet": g_alr.get("quiet"),
                   "runtime_faults": g_alr.get("runtime_faults"),
                   "anomalies": g_alr.get("anomalies"),
                   "needs_a_look": g_alr.get("needs_a_look"),
                   "unregistered_footprints": (g_alr.get("unregistered_footprints") or [])[:12]},
    }

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "caps": {"total": len(caps), "safe": safe, "unsafe": len(caps) - safe,
                 "items": cap_items,
                 "check": _cap("cap_self", {"op": "verify"}).get("counts") or {},
                 "docs": docs.get("verdict")},
        "skills": {"count": skills.get("count"), "validate": validate.get("verdict"),
                   "errors": (validate.get("errors") or [])[:8],
                   "warnings": len(validate.get("warnings") or []),
                   "names": skill_names, "items": skill_items},
        "engine": {"alive": bool(alive.get("ok")), "base": alive.get("base"),
                   "weights": w.get("name"), "size_gb": w.get("size_gb"),
                   "models": alive.get("models"), "breaker": breaker.get("state"),
                   "n_ctx": _engine_ctx(alive.get("base"))},
        "meter": {k: meter.get(k) for k in ("calls", "calls_ok", "failed",
                                           "power_tok_s", "avg_ms")},
        "guards": {"selfscan": g_self.get("verdict"),
                   "signature": g_sig.get("verdict"),
                   "inventory": g_inv.get("verdict"),
                   "legacy": g_leg.get("verdict"),
                   "alerts": ("quiet" if g_alr.get("quiet")
                              else ("needs_look" if g_alr.get("any_signal") else "unknown"))},
        "guard_details": guard_details,
        "domains": all_domains, "domains_top": domains,
        "pulse": pulse, "pulse_total": sum(x["n"] for x in pulse),
        "scan": scan,
        "professions": professions,
        "flow": flow,
        "ledger": [{"at": r.get("at"), "action": r.get("action"),
                    "target": r.get("target"), "result": (r.get("result") or "")[:60]}
                   for r in ledger[-8:]],
        "note": "所有数字来自框架现读（cap_self / skills_hub / commander / energy_core / orchestration）",
    }


def main() -> int:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "/* 自动生成，勿手改：python tools/gen-console-data.py */\n"
        "window.GBT_CONSOLE = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n",
        encoding="utf-8")
    print("写出:", OUT, "|", OUT.stat().st_size, "B")
    print("caps:", data["caps"]["total"], "| skills:", data["skills"]["count"],
          "| engine:", data["engine"]["alive"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
