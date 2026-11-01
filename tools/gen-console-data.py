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

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "caps": {"total": len(caps), "safe": safe, "unsafe": len(caps) - safe,
                 "items": cap_items,
                 "check": _cap("cap_self", {"op": "verify"}).get("counts") or {},
                 "docs": docs.get("verdict")},
        "skills": {"count": skills.get("count"), "validate": validate.get("verdict"),
                   "names": skill_names, "items": skill_items},
        "engine": {"alive": bool(alive.get("ok")), "base": alive.get("base"),
                   "weights": w.get("name"), "size_gb": w.get("size_gb"),
                   "models": alive.get("models"), "breaker": breaker.get("state")},
        "meter": {k: meter.get(k) for k in ("calls", "calls_ok", "failed",
                                           "power_tok_s", "avg_ms")},
        "guards": {"selfscan": _cap("selfscan").get("verdict"),
                   "signature": _cap("signature_guard", {"scope": "all"}).get("verdict"),
                   "inventory": _cap("inventory").get("verdict"),
                   "legacy": _cap("legacy_guard", {"op": "status"}).get("verdict")},
        "domains": all_domains, "domains_top": domains,
        "pulse": pulse, "pulse_total": sum(x["n"] for x in pulse),
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
