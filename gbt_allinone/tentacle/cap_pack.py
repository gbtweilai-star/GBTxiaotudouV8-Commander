# -*- coding: utf-8 -*-
"""能力包（cap_pack）：蒸馏自 v5 `capability_protocol` 的"清单发现 + 动态装载"。

v5 的做法：目录里有 `capability.json` 就当一个能力模块，读 manifest（name/version/entry/actions/
auto_exec），运行时按 entry 起子进程。我们**不搬它的引擎**（我们已有 caps_registry + api 分派），
只取两件对我们有用的：

  1. **外挂包发现**：把"能力"从框架代码里解耦 —— 丢一个目录（含 `capability.json`）就能被看见；
  2. **安全默认**：`auto_exec` 默认 false（只登记、不执行）；真要执行外部程序必须同时满足
     `auto_exec: true` **且** 主人发 `process_execute` 票（与 `body_open` 同一道门）。

子进程执行走上一轮蒸馏出的 `proc_guard`（超时杀整棵树 / 输出封顶 / 环境净化）。

op:
    discover {"paths": [...]}   # 扫包（默认 packs/、state/packs/、$GBT_CAP_PACKS）
    info     {"name": "..."}    # 看一个包的 manifest
    status                      # 一句话：几个包 / 几个可执行
    run      {"name","action","params"?}  # 执行（要 auto_exec + 票）
"""
from __future__ import annotations

import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_ROOTS = [ROOT / "packs", ROOT / "state" / "packs"]
MANIFEST = "capability.json"


def _roots(paths=None) -> list:
    out = []
    env = os.environ.get("GBT_CAP_PACKS", "")
    for p in [x for x in env.split(os.pathsep) if x]:
        out.append(pathlib.Path(p))
    out.extend(pathlib.Path(p) for p in (paths or []))
    out.extend(DEFAULT_ROOTS)
    seen, uniq = set(), []
    for p in out:
        k = str(p.resolve()) if p.exists() else str(p)
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    return uniq


def _load_manifest(path: pathlib.Path) -> dict | None:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(d, dict) or not d.get("name"):
        return None
    entry = d.get("entry") or {}
    if not isinstance(entry, dict) or not entry.get("program"):
        return None
    acts = d.get("actions")
    if isinstance(acts, dict):
        acts = list(acts.keys())
    elif isinstance(acts, list):
        acts = [str(a) for a in acts]
    else:
        acts = []
    return {"name": str(d["name"]), "version": str(d.get("version") or "0.0.0"),
            "description": str(d.get("description") or ""),
            "program": str(entry["program"]),
            "args": [str(a) for a in (entry.get("args") or [])],
            "actions": acts,
            "auto_exec": bool(d.get("auto_exec")),
            "timeout_s": float(d.get("timeout_s") or 60),
            "manifest": str(path.parent), "raw": d}


def discover(paths=None) -> dict:
    packs, errors = [], []
    for root in _roots(paths):
        if not root.is_dir():
            continue
        for p in sorted(root.glob("*/" + MANIFEST)):
            m = _load_manifest(p)
            if m:
                packs.append({k: m[k] for k in ("name", "version", "description", "program",
                                                "actions", "auto_exec", "manifest")})
            else:
                errors.append({"path": str(p), "why": "manifest 不合法（缺 name 或 entry.program）"})
    names = [x["name"] for x in packs]
    dup = sorted({n for n in names if names.count(n) > 1})
    return {"ok": True, "count": len(packs), "packs": packs, "errors": errors,
            "duplicates": dup,
            "executable": sum(1 for x in packs if x["auto_exec"]),
            "note": "auto_exec 默认 false：只登记不执行；执行要过 process_execute 门"}


def info(name: str) -> dict:
    d = discover()
    for p in d["packs"]:
        if p["name"] == name:
            return {"ok": True, "pack": p}
    return {"ok": False, "error": "user_error: 没找到能力包：%s" % name,
            "have": [x["name"] for x in d["packs"]]}


def status() -> dict:
    d = discover()
    return {"ok": True, "count": d["count"], "executable": d["executable"],
            "roots": [str(r) for r in _roots()],
            "rule": "丢一个含 capability.json 的目录 = 多一个能力；执行要 auto_exec + process_execute 票"}


def _gate():
    """执行外部程序：必须过 process_execute 门（与 body_open 同一道）。"""
    from ..security import policy as P
    if P.is_trusted():
        return {"ok": True, "trusted": True}
    from .. import auth_gate
    r = auth_gate.check_and_consume_many(["process_execute"], detail="cap_pack:run")
    if not r.get("ok"):
        return {"ok": False, "denied": True, "missing": r.get("missing"),
                "how_to_grant": r.get("how_to_grant"),
                "error": "denied: 执行外部能力包需要 process_execute 票"}
    return {"ok": True, "consumed": r.get("consumed", [])}


def run(name: str = "", action: str = "", params=None) -> dict:
    name, action = str(name or "").strip(), str(action or "").strip()
    if not name:
        return {"ok": False, "error": "user_error: 需要 name"}
    found = None
    for p in discover()["packs"]:
        if p["name"] == name:
            found = p
            break
    if not found:
        return {"ok": False, "error": "user_error: 没找到能力包：%s" % name}
    if not found["auto_exec"]:
        return {"ok": False, "refused": True,
                "error": "refused: 该包 auto_exec=false（只登记不执行）；"
                         "要执行请在 manifest 里显式写 auto_exec: true", "pack": name}
    if action and found["actions"] and action not in found["actions"]:
        return {"ok": False, "error": "user_error: 该包没有 action=%s（有：%s）"
                % (action, ", ".join(found["actions"]))}
    g = _gate()
    if not g.get("ok"):
        return {"ok": False, "denied": True, "gate": g,
                "error": g.get("error") or "denied: 没票"}
    from .proc_guard import run_capped
    cmd = [found["program"]] + found["args"]
    if action:
        cmd.append(action)
    if params:
        cmd.append(json.dumps(params, ensure_ascii=False))
    r = run_capped(cmd, timeout=float(found.get("timeout_s") or 60), max_chars=200_000)
    r.update({"pack": name, "action": action, "gate": {"ok": True},
              "manifest": found["manifest"]})
    return r


def run_op(op: str = "status", **kw) -> dict:
    op = (op or "status").lower()
    if op == "discover":
        return discover(kw.get("paths"))
    if op == "info":
        return info(str(kw.get("name") or ""))
    if op == "status":
        return status()
    if op == "run":
        return run(str(kw.get("name") or ""), str(kw.get("action") or ""), kw.get("params"))
    return {"ok": False, "error": "cap_pack 不认 op=%s（discover/info/status/run）" % op}
