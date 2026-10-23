# gbt-capability: action_gate
"""先看 → 动脑 → 执行 前置闸（主人令 2026-09-27）。

主人原话：「实现自我进化做事拥有**先看在动脑执行**，**拒绝所有的无脑操作以及盲猜**。」

## 为什么要有这道闸（不是流程装饰）

本仓的翻车史里，最贵的三类全是"没看就动手"：
- 出货前没看图 ⇒ 做旧的片子交成樱花少女（`brain-eye-hand-sync` 记着）；
- ffmpeg 两轮白跑没看报错（静默失败还报完成）；
- 拿 `-c "…"` 当探针，经 `.cmd` 被转义吃掉 ⇒ 探出 0 键还当"装了"。

所以这道闸把「先看」变成**机器要求**，通不过就不许动：

| 规矩 | 判定 | 拒不拒 |
|---|---|---|
| **先看** | `evidence` 非空，且每条证据**真在盘上**（path 存在） | 空 ⇒ 拒（无脑操作） |
| **看的是新的** | 证据龄 ≤ `fresh_s`（默认 600s），或显式声明 `stale_ok` + 理由 | 旧 ⇒ 拒（拿旧读数当现状） |
| **动脑** | `hypothesis` 必填，且 ≥8 字（写出"我预期发生什么"） | 缺/太短 ⇒ 拒（盲猜） |
| **有票** | 写/执行类动作（`scope` 给了或能力位权限类是 `owner`）要有许可 | 没票 ⇒ 拒，并给出准确授权命令 |

通过后发一个**闸号**（`gate_id`）并落台账 `state/action_gate.jsonl`；动作做完回填结果（`close`），
台账就是"先看→动脑→执行→看到结果"的完整一轮。**只读动作也要证据**（看图、读报错同样是"看"）。

op=observe / preflight / close / status / verify / where
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_STATE = _ROOT / "state"
_LEDGER = _STATE / "action_gate.jsonl"
_EVIDENCE = _STATE / "action_evidence.jsonl"
FRESH_S = 600                      # 证据默认新鲜度窗口
MIN_HYPOTHESIS = 8                 # 盲猜闸：少于这么多字不算"动过脑"
_GATED_SCOPES = {"filesystem_write", "process_execute", "deploy_publish", "remote_device",
                 "external_llm", "data_export", "desktop_control", "device_control",
                 "browser_control", "network_private", "owner_control"}


def _log(row: dict) -> None:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row}, ensure_ascii=False) + "\n")


def _sha(p: Path) -> str:
    try:
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            h.update(fh.read(1 << 20))
        return h.hexdigest()[:16]
    except OSError:
        return ""


def observe(paths: str = "", note: str = "", **_kw) -> dict:
    """**先看**这一步本身：把读到的证据（路径 + sha + 龄）记下来，返回证据捆。"""
    want = [x.strip() for x in (paths or "").split(",") if x.strip()]
    if not want:
        return {"ok": False, "op": "observe", "fail_closed": True,
                "error": "要给 paths（逗号分隔）—— 没看什么就没证据，后面不许动手"}
    now = time.time()
    ev = []
    for w in want:
        p = Path(w)
        if not p.is_absolute():
            p = _ROOT / w
        if not p.exists():
            ev.append({"path": str(p), "exists": False, "why": "**证据不在盘上** ⇒ 这条不算看"})
            continue
        mt = p.stat().st_mtime
        ev.append({"path": str(p), "exists": True, "sha": _sha(p) if p.is_file() else "",
                   "mtime": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(mt)),
                   "age_s": int(now - mt)})
    bundle = hashlib.sha256(json.dumps(ev, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "at_ts": now, "event": "observe", "bundle": bundle,
           "paths": len(ev), "missing": sum(1 for x in ev if not x.get("exists")), "note": note[:200],
           "evidence": ev}
    with open(_EVIDENCE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "op": "observe", "bundle": bundle, "evidence": ev,
            "missing": row["missing"]}


def _recently_observed(path: str, fresh_s: int, now: float) -> bool:
    """这条证据最近被 `observe` 过、而且**之后没被改过**（sha 不变）⇒ 算新鲜。

    为什么要有这条：内容龄 ≠ 认知龄。只看 mtime 的话，"我刚看过它"这个动作等于没用，
    而主人要的恰恰是**先看**这件事本身被机器认账。
    """
    if not _EVIDENCE.is_file():
        return False
    latest = None
    for ln in _EVIDENCE.read_text(encoding="utf-8", errors="replace").splitlines()[-400:]:
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if r.get("event") != "observe":
            continue
        for e in (r.get("evidence") or []):
            if e.get("path") == path and e.get("exists"):
                latest = (r.get("at_ts") or 0, e.get("sha") or "")
    if not latest:
        return False
    at_ts, sha = latest
    if (now - float(at_ts)) > fresh_s:
        return False
    return sha == _sha(Path(path))


def _scope_needed(kind: str, scope: str) -> list:
    """这个动作要哪些票：显式 scope + 能力位权限类（owner ⇒ 要主人许可）。"""
    need = [s for s in (scope or "").split(",") if s.strip()]
    if not kind:
        return need
    try:
        import importlib.util as _iu
        sp = _iu.spec_from_file_location("ct_ag", _ROOT / "gbt_allinone" / "tools" / "cap_tags.py")
        ct = _iu.module_from_spec(sp)
        sp.loader.exec_module(ct)
        c = ct.check(kind=kind)
        if c.get("allowed") is False:
            need.append("owner_permit")
    except Exception:                                          # noqa: BLE001
        need.append("unknown_permission")                      # 读不出来 ⇒ 严
    return need


def preflight(action: str = "", evidence: str = "", hypothesis: str = "",
              scope: str = "", kind: str = "", fresh_s: int = FRESH_S,
              stale_ok: bool = False, **_kw) -> dict:
    """动手前过闸：先看（证据）→ 动脑（假设）→ 有票（授权）→ 发闸号。"""
    if not action.strip():
        return {"ok": False, "op": "preflight", "fail_closed": True, "error": "要给 action（你要干什么）"}
    checks, refuses, checks_note = [], [], []
    # ① 先看
    if not (evidence or "").strip():
        refuses.append({"rule": "无脑操作", "why": "没给 evidence ⇒ 先跑 observe 把读到的东西记下来"})
    else:
        ev = [x.strip() for x in evidence.split(",") if x.strip()]
        missing, stale = [], []
        now = time.time()
        for e in ev:
            p = Path(e)
            if not p.is_absolute():
                p = _ROOT / e
            if not p.exists():
                missing.append(e)
                continue
            age = int(now - p.stat().st_mtime)
            if age > fresh_s and not stale_ok:
                # ② "看过且没变"也算新鲜：**内容龄 ≠ 认知龄**。
                #    一份 40 分钟前写下的读数，我 10 秒前刚看过、且它没再被改过 —— 这就是现状。
                #    （血账：早先只比文件 mtime，把"刚看过的旧文件"判成"拿旧读数当现状"，
                #      于是"先看"这个动作本身变得没用。）
                if _recently_observed(str(p), fresh_s, now):
                    checks_note.append(f"{e}=看过且没变")
                else:
                    stale.append(f"{e}(龄 {age}s > {fresh_s}s，且没有近期观察记录)")
        if missing:
            refuses.append({"rule": "证据不在盘上", "why": f"这些读不到：{missing[:4]}"})
        if stale:
            refuses.append({"rule": "拿旧读数当现状", "why": f"{stale[:3]} ⇒ 先 observe 一次（**看过且没变就算新鲜**），或 stale_ok=true 并说理由"})
        checks.append({"rule": "先看", "ok": not (missing or stale), "n": len(ev),
                       "note": checks_note})
    # ② 动脑
    if len(hypothesis.strip()) < MIN_HYPOTHESIS:
        refuses.append({"rule": "盲猜", "why": f"hypothesis 太短/为空（<{MIN_HYPOTHESIS} 字）⇒ 写出你预期会发生什么"})
    else:
        checks.append({"rule": "动脑", "ok": True, "chars": len(hypothesis.strip())})
    # ③ 有票
    need = _scope_needed(kind, scope)
    if need:
        try:
            sys.path.insert(0, str(_ROOT))
            from gbt_allinone import auth_gate as ag
            sc = (ag.status() or {}).get("scopes") or {}
            lack = [s for s in need
                    if s in _GATED_SCOPES and not (sc.get(s) or {}).get("grants_available")]
            if lack:
                refuses.append({"rule": "没票", "why": f"缺授权：{lack}",
                                "how_to_grant": [f"python -m gbt_allinone auth grant --scope {s} --ttl 600"
                                                 for s in lack if s in _GATED_SCOPES],
                                "owner_permit": ("owner 类能力位要主人的调用许可："
                                                 "python -m gbt_allinone.tools.cap_tags permit --tag <TAG>"
                                                 if "owner_permit" in need else "")})
            else:
                checks.append({"rule": "有票", "ok": True, "scopes": need})
        except Exception as exc:                               # noqa: BLE001
            refuses.append({"rule": "票查不到", "why": f"{type(exc).__name__}: {str(exc)[:80]} ⇒ 按没票算"})
    gid = hashlib.sha256(f"{action}|{evidence}|{hypothesis}|{time.time()}".encode()).hexdigest()[:12]
    verdict = {"ok": not refuses, "op": "preflight", "gate_id": gid if not refuses else "",
               "action": action[:160], "hypothesis": hypothesis.strip()[:200],
               "checks": checks, "refuses": refuses,
               "note": ("过了闸：带着 gate_id 去动手，做完用 close 回填结果"
                        if not refuses else "**没过闸，不许动手**")}
    _log({"event": "preflight", "gate_id": verdict["gate_id"], "action": action[:160],
          "ok": verdict["ok"], "rules": [r["rule"] for r in refuses]})
    return verdict


def close(gate_id: str = "", result: str = "", saw: str = "", **_kw) -> dict:
    """做完回填：**结果 + 看到了什么**（"看到"这一栏不许空 —— 又是一次"先看"）。"""
    if not gate_id or not result.strip():
        return {"ok": False, "op": "close", "fail_closed": True, "error": "gate_id 与 result 都要给"}
    if not saw.strip():
        return {"ok": False, "op": "close", "fail_closed": True,
                "error": "saw 空 ⇒ 做完没看结果。exit 0 不算完成，写你**亲眼看到的**"}
    _log({"event": "close", "gate_id": gate_id, "result": result[:300], "saw": saw[:300]})
    return {"ok": True, "op": "close", "gate_id": gate_id}


def status(limit: int = 8, **_kw) -> dict:
    rows = []
    if _LEDGER.is_file():
        for ln in _LEDGER.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]:
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    opens = {r["gate_id"] for r in rows if r.get("event") == "preflight" and r.get("gate_id")}
    closed = {r.get("gate_id") for r in rows if r.get("event") == "close"}
    refusals = [r for r in rows if r.get("event") == "preflight" and not r.get("ok")]
    by_rule = {}
    for r in refusals:
        for rule in (r.get("rules") or []):
            by_rule[rule] = by_rule.get(rule, 0) + 1
    return {"ok": True, "op": "status", "preflights": sum(1 for r in rows if r.get("event") == "preflight"),
            "closed": len(closed), "open_unclosed": len(opens - closed),
            "refused": len(refusals), "refused_by_rule": by_rule, "tail": rows[-limit:],
            "_口径": "**被拒次数是这个闸的价值**（拒掉的都是无脑/盲猜）；open_unclosed 是过了闸没回填的"}


def verify(**_kw) -> dict:
    problems = []
    st = status()
    if st["preflights"] and st["closed"] == 0:
        problems.append("过了闸却一次都没回填（close 没用起来 ⇒ 台账只剩前半轮）")
    return {"ok": not problems, "op": "verify", "problems": problems, "status": {
        k: v for k, v in st.items() if k not in ("tail", "_口径")},
        "rules": {"fresh_s": FRESH_S, "min_hypothesis": MIN_HYPOTHESIS},
        "_口径": "闸本身不许空转：有 preflight 就该有 close"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "action_gate", "tentacle": "action_gate",
            "entry": "run_task('action_gate', {...})",
            "ops": ["observe", "preflight", "close", "status", "verify", "where"],
            "三步": ["observe(paths) 先看 → preflight(action, evidence, hypothesis[, scope|kind]) 动脑+有票",
                     "动手 → close(gate_id, result, saw) 看到结果"],
            "refuse_rules": ["无脑操作（没证据）", "证据不在盘上", "拿旧读数当现状", "盲猜（没写预期）", "没票"],
            "ledger": str(_LEDGER.relative_to(_ROOT)),
            "contract": [
                {"op": "observe", "params": "paths=逗号分隔", "returns": "bundle + 每条证据的 sha/龄"},
                {"op": "preflight", "params": "action + evidence + hypothesis + (scope|kind)",
                 "returns": "gate_id 或 refuses"},
                {"op": "close", "params": "gate_id + result + saw", "returns": "回填确认"},
            ]}


def run_op(op: str = "status", **params) -> dict:
    op = (op or "status").lower()
    for name, fn in (("observe", observe), ("preflight", preflight), ("close", close),
                     ("status", status), ("verify", verify), ("where", where)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（observe/preflight/close/status/verify/where）"}
