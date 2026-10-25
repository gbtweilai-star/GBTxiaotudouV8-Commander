# gbt-capability: agent_council
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""多智能体议事会：**角色 + 轮次 + 发言权 + 终止投票 + 纪要**（蒸馏自 AutoGen，只取架构）。

## 抓取口径（本仓规矩：凡抓取必写源·时间·口径）
· **源**：2026-09-28 主人给的周榜卡 `AutoGen`（61.2k★ · Python · 微软开源）的公开一句话介绍：
  「多智能体框架，让好几个 AI 分工协作、自己开会，复杂任务拆给团队干（多智能体/协作）」。
  —— 一手仓库与文档本轮**未联网核验**（主人令：不出网花钱的动作），只蒸馏**开会这一面的架构**，
  不引用它的类名/代码/性能数字。
· **时间**：2026-09-28。
· **口径**：GBT 已有的对位不重造——**并行干活**走 `agent_rig`（orca 蒸馏），**拍板**走 Jev 四角色
  决策引擎；本件只补 AutoGen 真正独有的那块：**几个 AI 怎么"开会"**（轮次、发言权、终止投票、纪要）。

## 硬规矩
1. **发言权**：round_robin 下轮到谁谁说，**抢话 ⇒ 结构化拒绝**（fail-closed），不假装顺序没问题。
2. **大脑走门**：`speak_auto` 经 `run_task('llm_chat', …)` 取真话（`external_llm` 闸管）；
   `speak` 收**已备好的文本**（判据/主人手动喂），两者都如实记是谁说的。
3. **终止要投票**：会议结束 = 全员投「结束」**或**轮次用尽；差一票就继续，不许主持人独断。
4. **纪要带印**：纪要 = 主题 + 轮次 + 投票 + 全文 sha256；篡改发言记录 ⇒ 纪要校验当场报"被改过"。
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_DIR = _ROOT / "state" / "agent_councils"          # 每会一个 jsonl（追加式）
_INDEX = _ROOT / "state" / "agent_councils.json"   # 会议索引（元数据）
_DEFAULT_ROLES = ["jev", "claude", "codex", "deepseek"]   # 对位 Jev 四角色决策引擎


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _transcript(cid: str) -> Path:
    return _DIR / ("%s.jsonl" % cid)


def _rows(cid: str) -> list:
    p = _transcript(cid)
    if not p.is_file():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def _log(cid: str, row: dict) -> None:
    _DIR.mkdir(parents=True, exist_ok=True)
    with open(_transcript(cid), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row},
                            ensure_ascii=False) + "\n")


def _meta() -> dict:
    if _INDEX.is_file():
        try:
            return json.loads(_INDEX.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_meta(meta: dict) -> None:
    _DIR.mkdir(parents=True, exist_ok=True)
    _INDEX.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def convene(topic: str = "", roles=None, rounds: int = 3, policy: str = "round_robin", **_kw) -> dict:
    """开一场会：定题、定角色、定轮次与发言权策略。**只立会，不说话**。"""
    if not str(topic or "").strip():
        return {"ok": False, "fail_closed": True, "error": "topic 要给（会议主题）"}
    roles = [str(r) for r in (roles or _DEFAULT_ROLES) if str(r).strip()]
    if len(roles) < 2:
        return {"ok": False, "fail_closed": True,
                "error": "至少两个角色（一个人的会不叫开会）"}
    cid = "council-%s-%s" % (time.strftime("%Y%m%d"), str(int(time.time() * 1000))[-6:])
    meta = _meta()
    meta[cid] = {"topic": str(topic)[:200], "roles": roles, "rounds": int(rounds),
                 "policy": policy, "opened_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "closed": False}
    _save_meta(meta)
    _log(cid, {"event": "convene", "topic": str(topic)[:200], "roles": roles,
               "rounds": int(rounds), "policy": policy})
    return {"ok": True, "op": "convene", "council_id": cid, "roles": roles,
            "rounds": int(rounds), "policy": policy,
            "_口径": "只立会不说话；发言权按 policy；结束要投票或轮次用尽"}


def _whose_turn(meta: dict, cid: str) -> str | None:
    m = meta.get(cid) or {}
    roles = m.get("roles") or []
    if not roles or m.get("policy") != "round_robin":
        return None                                  # free 策略不排发言权
    turns = [r for r in _rows(cid) if r.get("event") == "speak"]
    return roles[len(turns) % len(roles)]


def _resolve_cid(cid: str, council_id: str = "", **_kw) -> str:
    """两个名字都要认：**过门调用传 `council_id`，直接调用传 `cid`**。

    实测事故（2026-09-28 产能测试 C 站）：过门调用传 `council_id` 而形参叫 `cid`
    ⇒ 走 `**_kw` 被静默丢弃 ⇒ cid 落空 ⇒ 报出**误导性的**「没有这场会」（其实会开好了）。
    教训入册：参数名失配 = 静默失配 + 误导报错，属 P1 一族。
    """
    return str(cid or council_id or _kw.get("council_id") or "").strip()


def speak(cid: str = "", role: str = "", text: str = "", council_id: str = "",
          **_kw) -> dict:
    cid = _resolve_cid(cid, council_id, **_kw)
    """记一条发言（**已备好的文本**）；round_robin 下抢话 ⇒ 结构化拒绝。"""
    meta = _meta()
    m = meta.get(cid or "")
    if not m:
        return {"ok": False, "fail_closed": True,
                "error": "没有这场会：%s（先 convene；注意 id 没传进来也会落到这里）"
                         % (cid or "‹id 为空›")}
    if m.get("closed"):
        return {"ok": False, "fail_closed": True, "error": "会议已散（closed），要发言先重开一场"}
    turn = _whose_turn(meta, cid)
    if turn and role != turn:
        return {"ok": False, "fail_closed": True, "denied": True,
                "error": "抢话：轮到 %s 说，不是 %s" % (turn, role),
                "how": "按发言权顺序来；要自由发言就在 convene 时给 policy='free'"}
    if not str(text or "").strip():
        return {"ok": False, "fail_closed": True, "error": "text 要给（发言内容）"}
    turns = [r for r in _rows(cid) if r.get("event") == "speak"]
    _log(cid, {"event": "speak", "role": role, "round": len(turns) // max(1, len(m.get("roles") or [1])) + 1,
               "text_sha": _sha(str(text)), "text_head": str(text)[:120]})
    return {"ok": True, "op": "speak", "council_id": cid, "role": role,
            "turn_now": len(turns) + 1}


def speak_auto(cid: str = "", role: str = "", prompt: str = "", council_id: str = "",
               **_kw) -> dict:
    cid = _resolve_cid(cid, council_id, **_kw)
    """让某角色**真说话**：经门取大模型的话（external_llm 闸管），再按发言权入账。"""
    meta = _meta()
    m = meta.get(cid or "")
    if not m:
        return {"ok": False, "fail_closed": True, "error": "没有这场会：%s" % cid}
    turn = _whose_turn(meta, cid)
    if turn and role != turn:
        return {"ok": False, "fail_closed": True, "denied": True,
                "error": "抢话：轮到 %s" % turn}
    from .. import run_task as _door                # ⛔ 大脑走唯一门
    r = _door("llm_chat", {"prompt": prompt or (m.get("topic") or "")})
    inner = (r.get("result") or {}).get("result") if isinstance(r.get("result"), dict) else None
    text = (inner or {}).get("text") or (inner or {}).get("reply") or ""
    if not str(text).strip():
        return {"ok": False, "fail_closed": True,
                "error": "门里没取到话（inner_ok=%s，多半是缺 external_llm 票）"
                         % (inner or {}).get("ok"),
                "envelope_status": r.get("status"), "denied": bool(r.get("denied"))}
    return speak(cid=cid, role=role, text=str(text))


def vote(cid: str = "", role: str = "", decision: str = "", council_id: str = "",
         **_kw) -> dict:
    cid = _resolve_cid(cid, council_id, **_kw)
    """投票：decision ∈ {继续, 结束}；**终止要全员**，差一票就继续。"""
    if decision not in ("继续", "结束"):
        return {"ok": False, "fail_closed": True, "error": "decision 只许 继续/结束"}
    meta = _meta()
    m = meta.get(cid or "")
    if not m or m.get("closed"):
        return {"ok": False, "fail_closed": True, "error": "没有这场会（或已散）：%s" % cid}
    if role not in (m.get("roles") or []):
        return {"ok": False, "fail_closed": True, "error": "%s 不在会场（roles=%s）" % (role, m.get("roles"))}
    votes = {r["role"]: r["decision"] for r in _rows(cid) if r.get("event") == "vote"}
    votes[role] = decision
    _log(cid, {"event": "vote", "role": role, "decision": decision})
    all_end = all(v == "结束" for v in votes.values()) and len(votes) == len(m.get("roles") or [])
    return {"ok": True, "op": "vote", "votes": votes, "all_end": all_end,
            "_口径": "终止要全员投结束；差一票就继续"}


def minutes(cid: str = "", council_id: str = "", **_kw) -> dict:
    cid = _resolve_cid(cid, council_id, **_kw)
    """散会纪要：主题 + 轮次 + 投票 + **全文 sha**；要终止投票全过或轮次用尽才准散。"""
    meta = _meta()
    m = meta.get(cid or "")
    if not m:
        return {"ok": False, "fail_closed": True, "error": "没有这场会：%s" % cid}
    rows = _rows(cid)
    turns = [r for r in rows if r.get("event") == "speak"]
    votes = {r["role"]: r["decision"] for r in rows if r.get("event") == "vote"}
    roles = m.get("roles") or []
    rounds_used = (len(turns) + len(roles) - 1) // max(1, len(roles))
    all_end = bool(votes) and all(v == "结束" for v in votes.values()) and len(votes) == len(roles)
    rounds_done = rounds_used >= int(m.get("rounds") or 0)
    if not (all_end or rounds_done):
        return {"ok": False, "fail_closed": True,
                "error": "散会条件不满足：终止投票未全员通过（%s）且轮次未用尽（%d/%d）"
                         % (votes or "无人投票", rounds_used, m.get("rounds")),
                "how": "让每个角色 vote(decision='结束')，或把轮次开完"}
    body = json.dumps({"topic": m.get("topic"), "turns": turns, "votes": votes},
                      ensure_ascii=False, sort_keys=True)
    digest = _sha(body)
    meta[cid]["closed"] = True
    meta[cid]["minutes_sha"] = digest
    _save_meta(meta)
    _log(cid, {"event": "minutes", "minutes_sha": digest, "turns": len(turns)})
    return {"ok": True, "op": "minutes", "council_id": cid, "topic": m.get("topic"),
            "rounds_used": rounds_used, "turns": len(turns), "votes": votes,
            "minutes_sha": digest,
            "_口径": "纪要带全文 sha；事后改发言记录 ⇒ verify 当场报被改过"}


def verify(cid: str = "", council_id: str = "", **_kw) -> dict:
    cid = _resolve_cid(cid, council_id, **_kw)
    """纪要校验：重算全文 sha，对不上 ⇒ **这条会被改过**，不假装它还是原样。"""
    meta = _meta()
    m = meta.get(cid or "")
    if not m:
        return {"ok": False, "fail_closed": True, "error": "没有这场会：%s" % cid}
    rows = _rows(cid)
    turns = [r for r in rows if r.get("event") == "speak"]
    votes = {r["role"]: r["decision"] for r in rows if r.get("event") == "vote"}
    body = json.dumps({"topic": m.get("topic"), "turns": turns, "votes": votes},
                      ensure_ascii=False, sort_keys=True)
    now = _sha(body)
    want = m.get("minutes_sha")
    if not want:
        return {"ok": True, "op": "verify", "verdict": "未散会（没有纪要印章）", "minutes_sha_now": now}
    same = (now == want)
    return {"ok": same, "op": "verify", "verdict": "一致" if same else "**被改过**",
            "minutes_sha_want": want, "minutes_sha_now": now}


def status(**_kw) -> dict:
    meta = _meta()
    return {"ok": True, "op": "status",
            "councils": [{"council_id": k, "topic": v.get("topic"), "roles": v.get("roles"),
                          "closed": bool(v.get("closed"))} for k, v in meta.items()],
            "count": len(meta)}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "agent_council", "tentacle": "agent_council",
            "entry": "run_task('agent_council', {...})",
            "ops": ["convene", "speak", "speak_auto", "vote", "minutes", "verify", "status", "where"],
            "distilled_from": "2026-09-28 主人给的周榜卡 AutoGen（61.2k★ · Python · 微软）——只取**开会架构**",
            "not_copied": "不引它的 GroupChat/Agent 类与代码；并行干活仍走 agent_rig（orca），"
                          "拍板仍走 Jev 四角色引擎——本件只补『几个 AI 怎么开会』这一面",
            "hard_rules": ["round_robin 下抢话 ⇒ 结构化拒绝（fail-closed）",
                           "大脑走门：speak_auto 经 llm_chat（external_llm 闸），没票如实报",
                           "终止要全员投票或轮次用尽，主持人不许独断",
                           "纪要带全文 sha；篡改 ⇒ verify 当场报被改过"],
            "files": {"会议记录": str(_DIR.relative_to(_ROOT)), "会议索引": str(_INDEX.relative_to(_ROOT))},
            "contract": [
                {"op": "convene", "params": "topic [roles rounds policy]", "returns": "council_id"},
                {"op": "speak", "params": "council_id+role+text（已备好）", "returns": "入账（抢话拒）"},
                {"op": "speak_auto", "params": "council_id+role [prompt]", "returns": "经门取话再入账"},
                {"op": "vote", "params": "council_id+role+decision(继续/结束)", "returns": "票形"},
                {"op": "minutes", "params": "council_id", "returns": "纪要（含全文 sha）"},
                {"op": "verify", "params": "council_id", "returns": "纪要被改过没有"},
            ]}


def run_op(op: str = "status", **params) -> dict:
    op = (op or "status").lower()
    for name, fn in (("convene", convene), ("speak", speak), ("speak_auto", speak_auto),
                     ("vote", vote), ("minutes", minutes), ("verify", verify),
                     ("status", status), ("where", where)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（convene/speak/speak_auto/vote/minutes/verify/status/where）"}


if __name__ == "__main__":                                    # 主人的终端入口
    import argparse
    ap = argparse.ArgumentParser(description="多智能体议事会（AutoGen 架构蒸馏 · 只取开会面）")
    ap.add_argument("cmd", nargs="?", default="status")
    ap.add_argument("--council", default="")
    ap.add_argument("--topic", default="")
    a = ap.parse_args()
    if a.cmd == "convene":
        print(json.dumps(run_op("convene", topic=a.topic), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(run_op(a.cmd, council_id=a.council), ensure_ascii=False, indent=1))
