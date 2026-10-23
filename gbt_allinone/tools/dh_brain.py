# gbt-capability: dh_brain
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""数字人本体（dh_brain）· **只读能力位**（主人令 2026-10-08）。

主人点名：「她的元数据你是不是都没接入啊」—— 实证：盘上元数据**齐全**（骨架/动作/干净尺/
案例库/语音路由/验收），但**框架侧没有她的能力位** ⇒ 登记表、触手绑定、能力栏、神经感知
**全都看不见她**。本件就是把她**接入统一门**。

## 口径（三条，不许破）
1. **只读单一真源、零写面**：op 一律**现读**下列真源文件，**不复制第二份**（单一真源纪律）。
2. **读不到就如实报 `未探测`**，**不许折绿**（fail-closed）。
3. **零写动作**：本能力位没有任何写面（不改 rig、不渲染、不刷页、不记账）。刷页/记账是**另外的
   工具调用**，不是能力位 —— 因为它是"读类直连"，故**无需任何 policy 条目**（未列出的只读 kind
   走零作用域；它没有任何写动作可"裸奔"）。

## 真源（现读 · 只读）
  · `state/digital-human-rig.json`     骨架/蒙皮/动作/导出/渲染/判据/负对照
  · `state/digital-human.json`         人读面（id/标题/页/rig/actions/voice）
  · `state/dh_status_audit.json`       状态文件审计（引用/在场/缺失/尺寸）
  · `state/voice-control-route.json`   语音操控路由（gate/routes/asr/user_model）
  · `state/voicestudio_acceptance.json` 语音工作室验收（服务/模型/腿/接线/缺口）
  · `projects/digital-human/out/*.json` rig_core / rig_report / trace / 三份 negctl（只读）

op：`status` / `spec` / `actions` / `voice` / `metadata` / `health` / `where`
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_CAP = "dh_brain"

SOURCES = {
    "rig": "state/digital-human-rig.json",
    "human": "state/digital-human.json",
    "status_audit": "state/dh_status_audit.json",
    "voice_route": "state/voice-control-route.json",
    "voice_accept": "state/voicestudio_acceptance.json",
    "out_rig_core": "projects/digital-human/out/rig_core.json",
    "out_rig_report": "projects/digital-human/out/rig_report.json",
    "out_trace": "projects/digital-human/out/trace.json",
    "out_negctl_bone": "projects/digital-human/out/negctl_bone-len.json",
    "out_negctl_frozen": "projects/digital-human/out/negctl_frozen-frames.json",
    "out_negctl_lock": "projects/digital-human/out/negctl_lock-ends.json",
}
PAGE = "holo_pet_w3/digital-human/index.html"


def _load(rel: str):
    """现读单一真源。读不到返回 (None, 原因) —— **不许折绿**。"""
    p = ROOT / rel
    if not p.is_file():
        return None, "不在盘：%s" % rel
    try:
        return json.loads(p.read_text(encoding="utf-8")), None
    except Exception as e:                                    # noqa: BLE001
        return None, "在盘但读不动（%s）：%s" % (type(e).__name__, rel)


def _keys(d) -> list:
    return sorted(d.keys()) if isinstance(d, dict) else []


def _size(rel: str):
    p = ROOT / rel
    return p.stat().st_size if p.is_file() else None


def metadata(**_kw) -> dict:
    """元数据面：**逐源在场/尺寸**（现读；读不到如实报）。"""
    rows = {}
    n_ok = 0
    for k, rel in SOURCES.items():
        d, why = _load(rel)
        rows[k] = {"source": rel, "present": d is not None,
                   "bytes": _size(rel), "keys": _keys(d) if d is not None else [],
                   "at": (d or {}).get("updated_at") or (d or {}).get("at")
                         or (d or {}).get("generated_at") if d is not None else None,
                   "why": why}
        n_ok += 1 if d is not None else 0
    pg = ROOT / PAGE
    return {"ok": True, "op": "metadata", "kind": _CAP,
            "sources_total": len(SOURCES), "sources_ok": n_ok,
            "page": {"file": PAGE, "present": pg.is_file(), "bytes": pg.stat().st_size if pg.is_file() else None},
            "sources": rows,
            "_口径": "只读单一真源、零写面；读不到=未探测（不折绿）"}


def status(**_kw) -> dict:
    """状态面：骨架/动作/语音各就位与否（现读）。"""
    rig, w1 = _load(SOURCES["rig"])
    human, w2 = _load(SOURCES["human"])
    audit, w3 = _load(SOURCES["status_audit"])
    missing = [w for w in (w1, w2) if w]
    if rig is None and human is None:
        return {"ok": False, "op": "status", "kind": _CAP, "unprobed": True,
                "why": "核心真源读不到 ⇒ 未探测（不折绿）：%s" % "；".join(missing)}
    return {"ok": True, "op": "status", "kind": _CAP,
            "id": (human or rig or {}).get("id") or _CAP,
            "title": (human or {}).get("title") or (rig or {}).get("schema"),
            "skeleton": (rig or {}).get("skeleton"),
            "actions": (rig or {}).get("actions") or (human or {}).get("actions"),
            "voice": (human or {}).get("voice"),
            "status_audit": {"present": (audit or {}).get("present"),
                             "missing": (audit or {}).get("missing"),
                             "size_ok": (audit or {}).get("size_ok")} if audit else None,
            "negative_controls": (human or {}).get("negative_controls") or (rig or {}).get("negative_controls"),
            "unprobed_sources": missing or None,
            "_口径": "现读 state/digital-human-rig.json + digital-human.json + dh_status_audit.json"}


def spec(**_kw) -> dict:
    """规格面：骨架/蒙皮/导出/渲染/判据（现读 rig.json）。"""
    rig, why = _load(SOURCES["rig"])
    if rig is None:
        return {"ok": False, "op": "spec", "kind": _CAP, "unprobed": True, "why": why}
    return {"ok": True, "op": "spec", "kind": _CAP, "schema": rig.get("schema"),
            "height_units": rig.get("height_units"), "height_basis": rig.get("height_basis"),
            "skeleton": rig.get("skeleton"), "skinning": rig.get("skinning"),
            "export": rig.get("export"), "render": rig.get("render"),
            "criteria": rig.get("criteria"), "negative_controls": rig.get("negative_controls"),
            "source": SOURCES["rig"]}


def actions(**_kw) -> dict:
    """动作面：动作清单 + 干净尺（现读 rig.json / digital-human.json）。"""
    rig, w1 = _load(SOURCES["rig"])
    human, w2 = _load(SOURCES["human"])
    a = (rig or {}).get("actions") or (human or {}).get("actions")
    if a is None:
        return {"ok": False, "op": "actions", "kind": _CAP, "unprobed": True,
                "why": "动作清单读不到：%s" % (w1 or w2)}
    return {"ok": True, "op": "actions", "kind": _CAP, "actions": a,
            "source": SOURCES["rig"] if (rig or {}).get("actions") else SOURCES["human"]}


def voice(**_kw) -> dict:
    """语音面：控制路由 + 工作室验收（现读两份真源）。"""
    route, w1 = _load(SOURCES["voice_route"])
    acc, w2 = _load(SOURCES["voice_accept"])
    if route is None and acc is None:
        return {"ok": False, "op": "voice", "kind": _CAP, "unprobed": True,
                "why": "语音真源读不到：%s；%s" % (w1, w2)}
    return {"ok": True, "op": "voice", "kind": _CAP,
            "route": {"gate": (route or {}).get("gate"), "routes": (route or {}).get("routes"),
                      "asr": (route or {}).get("asr"), "user_model": (route or {}).get("user_model")}
                     if route else None,
            "accept": {"service": (acc or {}).get("service"), "models": (acc or {}).get("models"),
                       "legs": (acc or {}).get("legs"), "wiring": (acc or {}).get("wiring"),
                       "honest_gaps": (acc or {}).get("honest_gaps")} if acc else None,
            "unprobed_sources": [w for w in (w1, w2) if w] or None}


def health(**_kw) -> dict:
    """健康面：状态文件审计（现读 dh_status_audit.json）。"""
    audit, why = _load(SOURCES["status_audit"])
    if audit is None:
        return {"ok": False, "op": "health", "kind": _CAP, "unprobed": True, "why": why}
    miss = audit.get("missing")
    return {"ok": True, "op": "health", "kind": _CAP, "at": audit.get("at"),
            "status_file": audit.get("status_file"), "referenced": audit.get("referenced"),
            "present": audit.get("present"), "missing": miss,
            "size_ok": audit.get("size_ok"), "size_warn": audit.get("size_warn"),
            "verdict": "有缺失（见 missing）" if miss else "无缺失（引用项都在场且尺寸合规）",
            "_口径": "现读 state/dh_status_audit.json；missing 非空即如实报缺"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": _CAP, "tentacle": _CAP,
            "entry": "run_task('dh_brain', {'op': 'status'})",
            "ops": ["status", "spec", "actions", "voice", "metadata", "health", "where"],
            "read_only": True,
            "route": "gbt_allinone/api.py::_run_benign 的 dh_brain 分支 → gbt_allinone/tools/dh_brain.py",
            "sources": SOURCES,
            "page": PAGE,
            "policy": "读类直连 ⇒ **无需 policy 条目**（未列出的只读 kind 走零作用域；本件零写面）",
            "contract": [
                {"op": "status", "returns": "骨架/动作/语音就位 + 负对照 + 状态审计摘要"},
                {"op": "spec", "returns": "rig 规格（骨架/蒙皮/导出/渲染/判据）"},
                {"op": "actions", "returns": "动作清单（rig 优先，回落 human）"},
                {"op": "voice", "returns": "语音控制路由 + 工作室验收（含 honest_gaps）"},
                {"op": "metadata", "returns": "逐源在场/尺寸/键（现读，读不到如实报）"},
                {"op": "health", "returns": "状态文件审计（present/missing/size_ok）"},
            ],
            "red_lines": ["只读单一真源、零写面", "读不到=未探测（不折绿）",
                          "不改 rig/不渲染/不刷页/不记账（那些是另外的工具调用）"]}


_OPS = {"status": status, "spec": spec, "actions": actions, "voice": voice,
        "metadata": metadata, "health": health, "where": where}


def run(op: str = "status", **kw) -> dict:
    op = (op or "status").lower()
    fn = _OPS.get(op)
    if fn is None:
        return {"ok": False, "fail_closed": True, "kind": _CAP,
                "error": "未知 op:%s（status/spec/actions/voice/metadata/health/where）" % op}
    return fn(**kw)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="数字人本体（只读能力位）")
    ap.add_argument("op", nargs="?", default="status")
    a = ap.parse_args()
    print(json.dumps(run(a.op), ensure_ascii=False, indent=1))
