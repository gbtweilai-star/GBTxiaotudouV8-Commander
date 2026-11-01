# -*- coding: utf-8 -*-
"""触手推理环（trunk_reason）：**接在 brain_exec 已有五维链上，不另起炉灶**。

主人 2026-11-01：「看清楚源码是怎么写的」「触手主干联通大脑推理，所以触手在执行任务的时候
都能动脑想办法，反思推荐……传统扫描能干嘛？我们的触手扫描能干嘛？」

## 看清源码后的事实（这才是对的接法）

`gbt_allinone/brain_exec.py` 早就写好了大脑执行层：
    route → execute → verify → health（unify）
    heartbeat → **advise**（把触手状态分析成 P0/P1/P2 指令，每条带 why + evidence）
    → **act**（只自动执行 `_AUTO_ACTIONS` 白名单里的动作，表外一律跳过并写明原因）

也就是说：**"触手扫描 → 大脑出指令 → 动手"这条链源码里本来就有**，只是 `advise` 是
**规则表**驱动（`_ADVICE_RULES`），不会"想" —— 它答得出"哪根触手挂了"，
答不出"这次扫描结果意味着什么、要不要补哪一刀"。

所以本能力**不重复造链**，只补缺的那一格：

    brain_exec.advise() 的规则指令（确定性、带证据）
      + 本机 7.6B 权重对「扫描现状」的推理（真风险/误报/下一步）
      = 同一套 instruction schema（priority/id/action/why/evidence）
        ⇒ 仍交给 brain_exec.act() 消费；**LLM 建议不进 _AUTO_ACTIONS ⇒ 不会被自动执行**。

## 判据

- 规则指令与 LLM 指令**分开列出**（不许混成一个"她很聪明"的印象）；
- LLM 不可用 ⇒ 如实报 `llm: unavailable`，规则指令照常返回；
- 全程 `brain_enter / brain_exit` 审计（复用 brain_exec.span 的口径），并落 `state/trunk-reason.jsonl`。

## op
    status  大脑在不在 + 规则表规模
    advise  规则指令 + LLM 补充指令（一条链，同一 schema）
    agent   advise → （可选）brain_exec.act 自动动作 → 复评定级
"""
from __future__ import annotations

import json
import pathlib
import re
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
LOG = ROOT / "state" / "trunk-reason.jsonl"

SYS = ("你是 GBT小土豆V8 的本机总指挥（自有 7.6B 权重）。下面是心跳触手刚扫出来的现状。"
       "请只输出一行 JSON：{\"risks\":[..],\"next\":[..],\"verdict\":\"ok|warn|bad\"}。"
       "risks 必须具体到触手/器官/端口，不许套话；next 只写**只读**检查或低风险动作，最多 3 条。"
       "看不清就少写，不要编。")


def _brain() -> dict:
    try:
        from . import commander as C
        return {"alive": bool(C.alive(timeout=1.0).get("ok")), "endpoint": C.endpoint()}
    except Exception as e:  # noqa: BLE001
        return {"alive": False, "error": "%s: %s" % (type(e).__name__, str(e)[:80])}


def _summary(adv: dict) -> dict:
    """给大脑的"扫描现状"：只取能判断的字段，控制 token。"""
    return {
        "verdict": adv.get("verdict"),
        "headline": adv.get("headline"),
        "score": adv.get("score"),
        "tentacles": "%s/%s" % (adv.get("tentacles_ok"), adv.get("tentacles_total")),
        "counts": adv.get("counts"),
        "rule_instructions": [
            {"p": i.get("priority"), "id": i.get("id"), "action": str(i.get("action"))[:120],
             "why": str(i.get("why"))[:160]}
            for i in (adv.get("instructions") or [])[:8]
        ],
    }


def _llm_instructions(summary: dict) -> dict:
    """让本机权重在规则指令之外再想一层；输出仍按 instruction schema。"""
    if not _brain().get("alive"):
        return {"ok": False, "error": "llm unavailable（本机引擎不在）", "instructions": []}
    from .. import energy_core as EC
    t0 = time.time()
    # 从**能源核心**取电（排队 + 记账），不再直连引擎
    r = EC.think([{"role": "system", "content": SYS},
                  {"role": "user", "content": "心跳现状：\n" + json.dumps(summary, ensure_ascii=False)[:1500]}],
                 temperature=0.0, max_tokens=260, timeout=300, label="trunk_reason.llm")
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error"), "instructions": []}
    txt = (r.get("text") or "").strip()
    m = re.search(r"\{[\s\S]*\}", txt)
    try:
        d = json.loads(m.group(0)) if m else {}
    except Exception:  # noqa: BLE001
        d = {}
    ins = []
    for i, nxt in enumerate((d.get("next") or [])[:3]):
        # 2026-11-01 主人严令：架构给完后，除 danger/transfer 外不许回头问主人。
        # 模型爱写"要不要我…/需要你确认"——这里按契约**改写为自主推进**并记账。
        action_txt = str(nxt)[:200]
        try:
            from . import autonomy as _AU
            g_ = _AU.guard(action_txt)
            if g_.get("rewritten"):
                action_txt = g_.get("text") or action_txt
        except Exception:  # noqa: BLE001
            pass
        ins.append({
            "priority": "P1" if (d.get("verdict") in ("warn", "bad")) else "P2",
            "id": "llm_next_%d" % (i + 1),
            "action": action_txt,
            "why": "本机权重对当前扫描的推断（规则表未覆盖）",
            "evidence": {"source": "brain_llm", "llm_verdict": d.get("verdict"),
                         "risks": (d.get("risks") or [])[:5]},
        })
    return {"ok": True, "ms": int((time.time() - t0) * 1000), "verdict": d.get("verdict"),
            "risks": (d.get("risks") or [])[:6], "raw": txt[:300], "instructions": ins}


def advise(mode: str = "light", with_llm: bool = True) -> dict:
    """规则指令（brain_exec.advise）+ LLM 补充指令，**分开列出、同一 schema**。"""
    from .. import brain_exec as BE
    from .. import heartbeat_tentacle as HB

    with BE.span("trunk_reason_advise"):
        rep = HB.scan_all(mode=mode, persist=True)
        rule = BE.advise(rep, mode=mode)
        summ = _summary(rule)
        llm = _llm_instructions(summ) if with_llm else {"ok": False, "instructions": [],
                                                       "error": "with_llm=False"}
    merged = list(rule.get("instructions") or []) + list(llm.get("instructions") or [])
    out = {
        "ok": rule.get("ok"),
        "verdict": rule.get("verdict"),
        "headline": rule.get("headline"),
        "score": rule.get("score"),
        "tentacles": summ["tentacles"],
        "rule_instructions": rule.get("instructions") or [],
        "rule_counts": rule.get("counts"),
        "llm": {"ok": llm.get("ok"), "verdict": llm.get("verdict"),
                "risks": llm.get("risks"), "error": llm.get("error"),
                "ms": llm.get("ms"), "instructions": llm.get("instructions") or []},
        "instructions": merged,
        "note": ("规则指令来自 brain_exec.advise（确定性·带证据）；LLM 指令来自本机权重，"
                 "source=brain_llm，**不在 act 的自动白名单内 ⇒ 不会被自动执行**"),
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": out["at"], "op": "advise", "verdict": out["verdict"],
                             "rule": len(out["rule_instructions"]),
                             "llm": len(out["llm"]["instructions"]),
                             "llm_risks": out["llm"]["risks"]}, ensure_ascii=False) + "\n")
    return out


def agent(mode: str = "light", auto_act: bool = False, dry_run: bool = True) -> dict:
    """闭环：advise（规则+LLM）→ act（只跑源码白名单的自动动作）→ 复评。"""
    from .. import brain_exec as BE

    a1 = advise(mode=mode, with_llm=True)
    before = {"verdict": a1.get("verdict"), "counts": a1.get("rule_counts")}
    act_out = None
    after = None
    if auto_act:
        with BE.span("trunk_reason_act"):
            act_out = BE.act(mode=mode, dry_run=dry_run)
        a2 = advise(mode=mode, with_llm=False)
        after = {"verdict": a2.get("verdict"), "counts": a2.get("rule_counts")}
    return {"ok": a1.get("ok"), "mode": mode, "before": before,
            "rule_instructions": len(a1["rule_instructions"]),
            "llm_instructions": len(a1["llm"]["instructions"]),
            "llm_risks": a1["llm"]["risks"], "llm_error": a1["llm"].get("error"),
            "act": act_out, "after": after,
            "note": "规则=确定性；LLM=推断（不自动执行）；act 只跑 _AUTO_ACTIONS 白名单"}


def status() -> dict:
    n = 0
    if LOG.exists():
        n = sum(1 for _ in LOG.open("rb"))
    return {"ok": True, "brain": _brain(), "log_lines": n,
            "note": "本能力接在 brain_exec.advise/act 上，不另造链"}


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status").lower()
    if op == "status":
        return status()
    if op == "advise":
        return advise(mode=str(kw.get("mode") or "light"),
                      with_llm=bool(kw.get("with_llm", True)))
    if op == "agent":
        return agent(mode=str(kw.get("mode") or "light"),
                     auto_act=bool(kw.get("auto_act", False)),
                     dry_run=bool(kw.get("dry_run", True)))
    return {"ok": False, "error": "trunk_reason 不认 op=%s（status/advise/agent）" % op}
