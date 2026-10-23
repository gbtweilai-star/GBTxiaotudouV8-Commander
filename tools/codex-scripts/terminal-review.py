# -*- coding: utf-8 -*-
# gbt-capability: terminal-review（接线件 · 不在 caps_registry 内，不占能力位）
"""GBT小土豆V8 · 独立终审位（C-15「验收方 ≠ 产出方」最小实现 · 2026-10-08）。

## 为什么要这件（缺口原文）

`docs/AI指挥手册-蒸馏.md` §3 与 `state/command-playbook.json` C-15 判：
「缺独立终审位 —— `lr_tick` 在**同一能力位内**跑完自己判（longrun.tick 内 run_task 后直接 `_judge`）」。
即：**产出方自报 status 就成了唯一证据**。本件把"终审"从产出位上剥出来，做成**可独立跑、可复核**的一步。

## 最小实现的三条边（缺一即不成立）

1. **产出方**：任意产出口（演示用 `wf_run` 节点 → `create op=write`，过 `filesystem_write` 门）；
   产出的"完成"由它自报 —— 本件**一概不采信**。
2. **终审方**（本件）：**只读盘**——现算 sha256 / 字节数 / 空否 / BOM / 关键词命中，
   判据只用四种非 LLM 判据（`file_exists:` / `contains:` / `no_error` / `status_ok` 的判据族，
   与本仓 `longrun._judge` 同口径）；另可用 `--producer-run` 取产出方**自报**的 sha，
   与盘上真值**逐项对**，把「自报 vs 真值」的**背离**逐条列出来（这才是终审的意义）。
3. **留痕**：本件**默认零写盘**（只打印读数与判决）；把判决写进台账请走既有账本能力位
   （`lr_submit` 的 acceptance / `memory_bank` 的印章 / `logbook.py`），不另造第二本账。

## 判据（fail-closed）

- 判据**未知**一律拒（同 `longrun._judge`：未知验收标准 ⇒ 失败）；
- 缺 `--token` 且缺 `--expect-sha256` ⇒ 拒（没有可判的判据 = 不许放行）；
- 文件不存在 / 空 / 有 BOM / 关键词不命中 / sha 对不上 ⇒ 拒。

## 用法

    py -3.14 tools/codex-scripts/terminal-review.py review --artifact outputs/…txt --token C15-XXX [--expect-sha256 <64hex>] [--producer-run <run_id>]
    py -3.14 tools/codex-scripts/terminal-review.py escalate --task T006X [--ttl-hours 72]
    py -3.14 tools/codex-scripts/terminal-review.py reflow --task T006X --acceptance "status_ok,file_exists:…,contains:…" [--submit] [--tick]
    py -3.14 tools/codex-scripts/terminal-review.py retro [--handoff]

退出码：review 过 ⇒ 0，拒 ⇒ 1（可当闸用）。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

STORE = ROOT / "gbt_allinone" / "store"
TASKS = STORE / "tasks.json"
RUNS = STORE / "wf_runs"


def _sha256_of(path: Path) -> tuple:
    """现读盘：文件级 sha256（读字节，与 memory_bank / closeout 同口径）。"""
    h = hashlib.sha256()
    n = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
            n += len(chunk)
    return h.hexdigest(), n


def _resolve(rel: str) -> Path:
    p = Path(str(rel))
    return p if p.is_absolute() else (ROOT / p)


def _read_claim(run_id: str) -> dict:
    """读产出方的**自报**（只读它的运行记录；本件不采信，只用于对账）。"""
    cand = RUNS / (str(run_id) + ".json")
    if not cand.is_file():
        cands = sorted(RUNS.glob("*%s*.json" % run_id))
        if not cands:
            return {"found": False, "why": "运行记录不在盘上：%s" % (RUNS / (str(run_id) + ".json"))}
        cand = cands[-1]
    try:
        doc = json.loads(cand.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"found": False, "why": "运行记录不可解析：%s" % exc}
    rec = doc.get("record") or {}
    claims = []

    def _walk(o, node=None):
        if isinstance(o, dict):
            k_node = o.get("id") if isinstance(o.get("id"), str) and "kind" in o else node
            if "sha256" in o and isinstance(o.get("sha256"), str):
                claims.append({"node": k_node, "self_reported_sha256": o.get("sha256"),
                               "path": o.get("path") or o.get("abs")})
            for k, v in o.items():
                _walk(v, k_node)
        elif isinstance(o, list):
            for v in o:
                _walk(v, node)

    for nid, env in (doc.get("results") or {}).items():   # 运行记录里 results 的键就是节点名
        _walk(env, nid)
    return {"found": True, "file": str(cand.relative_to(ROOT)), "run_id": rec.get("run_id", run_id),
            "producer_self_status": rec.get("status"), "node_status": rec.get("nodes"),
            "self_reported": claims}


def cmd_review(a) -> int:
    """终审：只读盘判；可选与产出方自报对账。"""
    art = _resolve(a.artifact)
    readings = {"artifact": str(a.artifact), "abs": str(art), "exists": art.is_file()}
    verdict, reasons = True, []
    if not art.is_file():
        verdict = False
        reasons.append("文件不存在（判据 file_exists: 不满足）")
    else:
        sha, nbytes = _sha256_of(art)
        raw = art.read_bytes()
        readings.update({"bytes": nbytes, "sha256": sha, "sha16": sha[:16],
                         "empty": nbytes == 0, "bom": raw[:3] == b"\xef\xbb\xbf"})
        if nbytes == 0:
            verdict = False
            reasons.append("文件为空（空产不算产出）")
        if readings["bom"]:
            verdict = False
            reasons.append("有 UTF-8 BOM（字节层有杂质）")
        # 判据①：关键词（非 LLM，纯字节/文本层）
        if a.token:
            text = raw.decode("utf-8", errors="replace")
            hit = a.token in text
            readings["token"] = a.token
            readings["token_found"] = hit
            if not hit:
                verdict = False
                reasons.append("缺少关键词: %s（判据 contains: 不满足）" % a.token)
        # 判据②：sha 全等（判据先行给的期望值）
        if a.expect_sha256:
            eq = sha == a.expect_sha256.lower()
            readings["expect_sha256"] = a.expect_sha256.lower()
            readings["sha_match"] = eq
            if not eq:
                verdict = False
                reasons.append("sha256 对不上（盘上 %s… ≠ 期望 %s…）" % (sha[:16], a.expect_sha256[:16]))
        if not a.token and not a.expect_sha256:
            verdict = False
            reasons.append("没有可判的判据（缺 --token 且缺 --expect-sha256）⇒ 拒（fail-closed）")
    # 对账：产出方自报 vs 盘上真值（背离逐条列）
    divergences = []
    claim = None
    if a.producer_run:
        claim = _read_claim(a.producer_run)
        if claim.get("found"):
            if claim.get("producer_self_status") != "ok":
                divergences.append("产出方自报整体 status=%s（非 ok）" % claim.get("producer_self_status"))
            for c in claim.get("self_reported") or []:
                if c.get("self_reported_sha256") and not readings.get("sha256"):
                    divergences.append("节点 %s 自报 sha=%s… 但盘上**无此文件** ⇒ 自报无盘上物支撑"
                                       % (c.get("node"), str(c["self_reported_sha256"])[:16]))
                elif c.get("self_reported_sha256") and readings.get("sha256") \
                        and c["self_reported_sha256"] != readings["sha256"]:
                    divergences.append("节点 %s 自报 sha=%s… 与盘上 %s… 不一致"
                                       % (c.get("node"), str(c["self_reported_sha256"])[:16],
                                          str(readings.get("sha256"))[:16]))
                if c.get("path") and str(c["path"]).replace("\\", "/").split("outputs/")[-1] != str(a.artifact).replace("\\", "/").split("outputs/")[-1] \
                        and Path(str(c.get("path"))).name != Path(str(a.artifact)).name:
                    divergences.append("节点 %s 自报路径 %s 与被审路径 %s 不一致"
                                       % (c.get("node"), c.get("path"), a.artifact))
        else:
            divergences.append("取不到产出方自报：%s" % claim.get("why"))
    out = {"ok": verdict, "op": "review", "verdict": "通过" if verdict else "拒",
           "标准": "独立终审：只读盘 + 非 LLM 判据（file_exists/contains/sha256）",
           "reading": readings, "reasons": reasons,
           "producer_claim": (claim or {"note": "未给 --producer-run ⇒ 未对账（终审只认盘）"}),
           "divergences": divergences,
           "判据来源": "tools/codex-scripts/terminal-review.py（C-15 接线件；与 longrun._judge 同口径）",
           "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if verdict else 1


def _task(task_id: str) -> dict:
    doc = json.loads(TASKS.read_text(encoding="utf-8"))
    t = next((x for x in doc.get("tasks", []) if x.get("task_id") == task_id), None)
    if t is None:
        raise SystemExit("任务不存在: %s（现读 %s）" % (task_id, TASKS.relative_to(ROOT)))
    return t


def cmd_escalate(a) -> int:
    """升级件（C-19）：五选项 + 决策人 + 期限（从失败任务的真读数现算）。"""
    t = _task(a.task_id)
    why = t.get("last_error") or "（无 why 读数）"
    opts = [
        {"plan": "① 拆分任务", "cost": "把当前任务拆成更小步骤，多跑几轮",
         "when": "目标正确但单步太大", "动作": "lr_submit 拆条重派（params 带 _prev_error）"},
        {"plan": "② 换验收口径", "cost": "需确认验收标准是否过严/写错",
         "when": "执行其实完成了，是判据对不上", "动作": "lr_submit 带修正后的 acceptance"},
        {"plan": "③ 差异化重试（失败数据回流）", "cost": "把 why 回流进参数再跑一次，不是同因复读",
         "when": "失败原因可定位且可修", "动作": "terminal-review.py reflow --task %s --acceptance …" % a.task_id},
        {"plan": "④ 换执行位", "cost": "换另一个能力位/触手承担同一产物",
         "when": "现执行位本身不适配", "动作": "command_chain plan/commit 重派（带许可标签）"},
        {"plan": "⑤ 人工介入并暂停", "cost": "任务挂起，等主人新指示",
         "when": "目标本身需要重新确认", "动作": "不自动重试；升级件交主人"},
    ]
    out = {"ok": True, "op": "escalate", "task_id": a.task_id, "task_status": t.get("status"),
           "attempts": t.get("attempts"), "blocked_by": why,
           "fingerprints": t.get("fingerprints") or [],
           "options": opts, "决策人": "主人（owners）", "期限": "%d 小时内须有人拍一个" % a.ttl_hours,
           "src": "%s（任务 %s 真读数）" % (TASKS.relative_to(ROOT), a.task_id),
           "纪律": "升级件只出选项与代价，不代替决策；产出方/执行位不得自批自己的升级件",
           "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def cmd_reflow(a) -> int:
    """差异化重试（C-20）：把失败数据**回流**进下一次输入（不是同因复读）。"""
    from gbt_allinone.api import run_task
    t = _task(a.task_id)
    why = t.get("last_error") or ""
    acc = [x.strip() for x in str(a.acceptance).split(",") if x.strip()] if a.acceptance else None
    if not acc:
        raise SystemExit("reflow 要 --acceptance（修正后的判据；本件不替你编判据）")
    params = dict(t.get("params") or {})
    params["_prev_error"] = why                      # ← 失败数据回流（核心）
    params["_prev_attempts"] = int(t.get("attempts") or 0)
    params["_prev_fingerprints"] = (t.get("fingerprints") or [])[-3:]
    params["_reflow_of"] = t.get("task_id")
    payload = {"description": "[差异化重试] " + str(t.get("description") or "")[:80],
               "kind": t.get("kind"), "params": params, "priority": t.get("priority", "high"),
               "acceptance": acc, "max_attempts": 1}
    out = {"ok": True, "op": "reflow", "of": t.get("task_id"), "回流": {
               "_prev_error": why, "_prev_attempts": params["_prev_attempts"]},
           "新判据": acc, "提交": None, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if a.submit:
        r = run_task("lr_submit", payload)
        out["提交"] = r.get("gbt_result", {}).get("result")
    if a.tick:
        r = run_task("lr_tick", {"max_tasks": 1})
        out["推进"] = r.get("gbt_result", {}).get("result", {}).get("ran")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def cmd_retro(a) -> int:
    """冲刺级复盘三问（C-26）：①做完什么 ②卡在哪/为什么 ③Action items（含承接处）。"""
    doc = json.loads(TASKS.read_text(encoding="utf-8"))
    tasks = doc.get("tasks", [])
    done = [t for t in tasks if t.get("status") == "done"]
    bad = [t for t in tasks if t.get("status") in ("failed", "stalled")]
    runs = sorted(RUNS.glob("*.json"))
    whys = {}
    for t in bad:
        w = str(t.get("last_error") or "（无）")[:80]
        whys.setdefault(w, []).append(t.get("task_id"))
    q1 = {"问": "这一冲刺做完什么（可复算）",
          "读数": {"任务总数": len(tasks), "done": len(done), "wf_runs 记录数": len(runs),
                  "最近三条 run": [p.stem for p in runs[-3:]]}}
    q2 = {"问": "卡在哪、为什么（逐条真读数）",
          "读数": {"failed_stalled": len(bad),
                  "按原因归类": {k: v for k, v in sorted(whys.items(), key=lambda x: -len(x[1]))[:6]}}}
    actions = []
    for w, ids in sorted(whys.items(), key=lambda x: -len(x[1]))[:3]:
        actions.append({"action": "对原因『%s』出一次差异化重试或换口径" % w,
                        "涉及": ids, "承接处": "lr_submit（带 _prev_error 回流）或 terminal-review.py reflow"})
    q3 = {"问": "下一步 Action items 落到哪个承接处", "items": actions or
          [{"action": "无挂起失败 ⇒ 固化本轮判据/工作流", "承接处": "wf_define 复刻 + logbook 记一条"}]}
    out = {"ok": True, "op": "retro", "三问": [q1, q2, q3],
           "src": {str(TASKS.relative_to(ROOT)): "真读数", "wf_runs": "现读 %d 条" % len(runs)},
           "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if a.handoff:
        from gbt_allinone.api import run_task
        r = run_task("handoff", {"op": "write",
                     "topic": "C-26 冲刺级复盘三问（%s）" % out["at"],
                     "agent": "terminal-review.py",
                     "arch": [json.dumps(q1, ensure_ascii=False)],
                     "failed": [json.dumps(q2, ensure_ascii=False)],
                     "todo": [json.dumps(x, ensure_ascii=False) for x in q3["items"]],
                     "src": "terminal-review.py retro 现读 %s + wf_runs %d 条"
                            % (TASKS.relative_to(ROOT), len(runs))})
        out["承接处已写"] = r.get("gbt_result", {}).get("result")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GBT小土豆V8 · 独立终审位（C-15）+ 升级件（C-19）· 差异化重试（C-20）· 复盘三问（C-26）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("review", help="独立终审：只读盘 + 非 LLM 判据")
    p.add_argument("--artifact", required=True, help="被审产物（仓内相对或绝对路径）")
    p.add_argument("--token", default="", help="期望出现的关键词（判据 contains:）")
    p.add_argument("--expect-sha256", default="", help="判据先行给的期望 sha256（64 hex）")
    p.add_argument("--producer-run", default="", help="产出方 run_id（可选：取它的自报来对账）")
    p.set_defaults(fn=cmd_review)

    p = sub.add_parser("escalate", help="升级件：五选项 + 决策人 + 期限")
    p.add_argument("--task", dest="task_id", required=True)
    p.add_argument("--ttl-hours", type=int, default=72)
    p.set_defaults(fn=cmd_escalate)

    p = sub.add_parser("reflow", help="差异化重试：失败数据回流")
    p.add_argument("--task", dest="task_id", required=True)
    p.add_argument("--acceptance", required=True, help="修正后的判据（逗号分隔）")
    p.add_argument("--submit", action="store_true")
    p.add_argument("--tick", action="store_true")
    p.set_defaults(fn=cmd_reflow)

    p = sub.add_parser("retro", help="冲刺级复盘三问")
    p.add_argument("--handoff", action="store_true", help="把 Action items 写进 handoff 承接处")
    p.set_defaults(fn=cmd_retro)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
