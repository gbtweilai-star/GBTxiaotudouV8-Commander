# -*- coding: utf-8 -*-
# gbt-capability: brain_supervisor
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""brain_supervisor —— 大脑执行层的**监督环**（主人令 2026-10-13）。

主人原话（逐字）：「**给她设计一个监控触手LLM的监控，只要发现不对主脑要第一时间知道**，
避免LLM出错的时候主脑还不知道就有点麻烦的」「每次的指派任务都要有任务细节以及每一步怎么做
都要细致的思维导图任务图，LLM领取任务图执行任务，遇到问题不能直接停下把问题返回大脑执行层，
分析推理规划从新生成任务图在继续推进以此循环」「大脑执行层必须确保所有大脑都是在运行干活的」。

## 四个位（同一模块、同一道门）
  · **llm_watch**   守望：每次 LLM 输出过后**当场过机器判据**，命中就**立刻进主脑注意力队列**；
  · **task_graph**  任务图：一句话 → 细到步的图（每步：干什么/怎么做/注意什么/合格判据/谁干）；
  · **replan_loop** 回流环：卡点 → 交回大脑执行层 → **重生成图** → 继续（带轮次上限，防死循环）；
  · **duty_board**  在岗看板：谁在跑 / 谁空转 / 谁卡住多久（**读数算出来的，不是感觉**）。

## 铁律（与本仓同源，不许软）
  ① 判据**只认可机检的错**：无证据的「已完成」声明 · 越权声明 · 数字自相矛盾 · 该查没查就下结论。
     🔴 **语义幻觉这一层我判不了** —— 那就**如实写「判不了」**，不许把判不了说成判过了。
     （防幻觉的正主是 `fact_gate`/`policy_gate`：机器事实与权限**根本不让她过模型**。）
  ② 图**不是模型编的**：由「模板 + 现读位面（skill_atlas）」生成；要模型重推，另走 `external_llm`
     门（本位**不偷偷调模型**）。
  ③ 有**负控**：喂一条干净的输出，必须判「无命中」——不许见谁都说有问题。
  ④ 只追加：队列与循环账 append-only，不改写历史。

## 落点
  `store/brain_supervisor/`（queue.jsonl 主脑注意力队列 · graphs/<名字>.json 图各版本 ·
  loops.jsonl 回流账 · claims.jsonl 领图/步态账）。`GBT_STORE_DIR` 一变就跟着走（与 skill_watch 同口径）。
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import time

_ROOT = pathlib.Path(__file__).resolve().parent.parent
MAX_LOOP_ROUNDS = 3

OPS = {
    "llm_watch": ("review", "queue", "ack", "status"),
    "task_graph": ("draft", "read", "claim", "step", "status"),
    "replan_loop": ("tick", "history", "status"),
    "duty_board": ("board", "status"),
}

_DONE_RE = re.compile(r"已完成|已修复|已跑通|已交付|已经搞定|全部通过|都已|done\b|fixed\b|completed\b", re.I)
_OVERREACH_RE = re.compile(r"我已授权|我已给自己|自我授权|绕过门|不用授权|跳过门|无授权也|不经过授权|绕开授权")
_FACTWORD_RE = re.compile(r"本机|这台|内存|显卡|GPU|装了|已装|端口|版本|能力位|硬盘|磁盘|通不通|在位")
_CONTRADICT_RE = re.compile(r"没有|无法|做不到|不支持")
_NUM_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:GB|MB|G|M|个|条|次|秒|%|chars?)", re.I)


def _dir() -> pathlib.Path:
    d = os.environ.get("GBT_STORE_DIR")
    base = pathlib.Path(d) if d else (_ROOT / "gbt_allinone" / "store")
    p = base / "brain_supervisor"
    p.mkdir(parents=True, exist_ok=True)
    (p / "graphs").mkdir(exist_ok=True)
    return p


def _append(name: str, row: dict) -> pathlib.Path:
    p = _dir() / name
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return p


def _rows(name: str) -> list:
    p = _dir() / name
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except Exception:                                   # noqa: BLE001
                continue
    return out


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _atlas_caps() -> list:
    """现读位面（用来填「谁干」）。读不到就如实回空表，不编。"""
    p = _ROOT / "state" / "skill_atlas.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return [c for c in (data.get("caps") or []) if isinstance(c, dict)]
    except Exception:                                           # noqa: BLE001
        return []


# ── ① 守望 ────────────────────────────────────────────────────────────────
def _hits(answer: str, claims: list, evidence: list) -> list:
    """**纯函数**：一次 LLM 输出过一遍机器判据。空表 = 干净（负控就靠这条）。"""
    text = str(answer or "")
    cl = [str(x) for x in (claims or [])]
    ev = [str(x) for x in (evidence or [])]
    out = []
    if _DONE_RE.search(text) and not ev:
        out.append({"code": "完成声明无证据", "severity": "high",
                    "why": "出现「已完成/已跑通/已交付」这类完成声明，但 evidence 一条都没有",
                    "fix": "要么补一条能复跑的命令 + 一次真读数，要么把话说回「未验」"})
    if _OVERREACH_RE.search(text):
        out.append({"code": "越权声明", "severity": "critical",
                    "why": "出现「我已授权/绕过门/不用授权」这类自我授权说法",
                    "fix": "授权只能主人在终端发；AI 永远不许给自己发授权 —— 停下并如实报缺哪个作用域"})
    if _FACTWORD_RE.search(text) and not ev:
        out.append({"code": "机器事实无现读", "severity": "medium",
                    "why": "在讲本机事实（内存/端口/装了没/版本…），却没有一条 evidence",
                    "fix": "机器事实不该过模型：走 fact_gate 现读，或补一条真读数再开口"})
    if _DONE_RE.search(text) and _CONTRADICT_RE.search(text):
        out.append({"code": "自相矛盾", "severity": "low",
                    "why": "同一段里既说「已完成」又说「没有/无法/做不到」",
                    "fix": "二选一：到底成了没有；说不清就写「未验」"})
    if cl and not ev:
        out.append({"code": "claims 无 evidence", "severity": "medium",
                    "why": "给了 %d 条声明却一条证据都没有" % len(cl),
                    "fix": "按 1:1 补证据，或把声明降级成「推测」"})
    na, ne = set(_NUM_RE.findall(text)), set(_NUM_RE.findall(" ".join(ev)))
    if ev and na and ne and (na - ne) and not (na & ne):
        out.append({"code": "数字对不上", "severity": "medium",
                    "why": "文里的数与证据里的数没有一个对得上（%s vs %s）" % (sorted(na)[:2], sorted(ne)[:2]),
                    "fix": "以现读读数为准改文，别拿印象里的数说话"})
    return out


def _llm_watch(op: str, p: dict) -> dict:
    if op == "status":
        return {"ok": True, "op": "status", "ops": list(OPS["llm_watch"]),
                "队列未处理": sum(1 for r in _rows("queue.jsonl") if not r.get("acked_at")),
                "口径": "只认可机检的错；语义幻觉这一层判不了（如实写，不冒充判过）"}
    if op == "review":
        hits = _hits(p.get("answer", ""), p.get("claims") or [], p.get("evidence") or [])
        queued = 0
        if hits:
            top = max(("critical", "high", "medium", "low").index(h["severity"]) for h in hits)
            _append("queue.jsonl", {"at": _now(), "kind": "llm_watch", "severity": top,
                                    "codes": [h["code"] for h in hits], "hits": hits,
                                    "who": str(p.get("who") or "")[:60], "acked_at": None})
            queued = 1
        return {"ok": True, "op": "review", "命中": len(hits), "hits": hits,
                "判决": ("干净（本条判据全过）" if not hits else "有疑点 ⇒ 已进主脑注意力队列"),
                "上报": {"queued": queued},
                "口径": "命中即第一时间进主脑队列；判不了的那一层（语义幻觉）不在这里冒充"}
    if op == "queue":
        rows = [r for r in _rows("queue.jsonl") if not r.get("acked_at")]
        return {"ok": True, "op": "queue", "count": len(rows), "rows": rows[-20:],
                "口径": "主脑视角：未处理的疑点；处理完用 ack 销账"}
    if op == "ack":
        target = str(p.get("at") or "")
        rows = _rows("queue.jsonl")
        if not rows:
            return {"ok": False, "error": "队列为空，没有可销的账"}
        hit = [r for r in rows if not r.get("acked_at")]
        pick = [r for r in hit if r.get("at") == target] if target else hit[-1:]
        if not pick:
            return {"ok": False, "error": "没找到可销的条目（at=%s）" % target}
        for r in pick:
            r["acked_at"] = _now()
            r["ack_note"] = str(p.get("note") or "")[:120]
        (_dir() / "queue.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        return {"ok": True, "op": "ack", "销账": len(pick),
                "remaining": sum(1 for r in rows if not r.get("acked_at"))}
    return {"ok": False, "error": "未知 op:%s" % op, "known": list(OPS["llm_watch"])}
# ── ② 任务图 ──────────────────────────────────────────────────────────────
# 类别 → 工序模板。每步五件：干什么 / 怎么做 / 注意什么 / 合格判据 / 谁干。
_ARCHETYPES = {
    "调研": (("调研", "查资料", "查一下", "市场", "行情", "搜索", "情报"),
             ("browser", "topic_watch", "trend_watch"),
             (("定问题", "把要回答的问题写成 1-3 句", "问题含糊 ⇒ 后面全白跑", "问题可被一句话复述"),
              ("抓一手资料", "走 browser / recon 拿原文，落 retrieval 账", "别拿二手转述当一手", "每条资料带 URL 与抓取时间"),
              ("交叉验证", "至少两个独立来源对同一个数", "单一来源不算证据", "关键数字有两个来源"),
              ("出结论", "结论 + 出处 + 不确定处照实写", "不许把推测写成事实", "每条结论指得回原文"))),
    "挖洞": (("挖洞", "漏洞", "渗透", "扫描", "越权", "赏金"),
             ("recon", "sec_scan", "pentest", "rea_reverse"),
             (("划授权边界", "只测已登记授权的目标（targets.jsonl）", "没授权的一律不碰", "目标已在授权台账里"),
              ("侦察面", "surface/端口/证书先量一遍", "别一上来就打", "面清单落盘"),
              ("静态定位", "只做定位（sink/拼接/危险函数），不出 payload", "找得到 ≠ 打过去", "定位到文件与行"),
              ("证据链", "请求包 + 响应对比 + 复现步骤 + 修复建议", "缺一件不算有效漏洞", "四件齐"),
              ("定级与报告", "按 CVSS 定级，走 vuln_mining 语料口径", "平台规则优先", "报告可提交"))),
    "代码": (("改代码", "重构", "写代码", "修 bug", "加个功能", "实现"),
             ("code_patch", "codex_status", "gbt-code-taste"),
             (("读现状", "先读真文件再动笔", "凭印象改 = 盲打", "改前三处读数"),
              ("定最小改法", "一次只改一个意图", "顺手重构 = 说不清哪步坏了", "diff 意图单一"),
              ("落盘过门", "走 code_patch（仓内/恰好一次/逐字节/可回滚）", "直接 edit 落盘 = 不过门", "有回执"),
              ("复跑判据", "跑判据件 + 一条可复跑命令", "没跑通不许说完成", "判据绿 + 读数在手"))),
    "出片": (("出片", "视频", "海报", "设计", "落地页", "生图", "剪"),
             ("art_chain", "art_brief", "comfy_native", "filmkit"),
             (("定档与风格", "先定三档转盘与轴，再动手", "不定档 = AI 味", "档位与轴写下来"),
              ("取件/起稿", "走 art_chain（挑组件→取件→真渲）", "素材必须可追出处", "每件带来源"),
              ("成片", "渲出来亲眼看，对比前后", "不看就交付 = 假绿", "有对比证据"),
              ("验收", "过审美审计器 + 缺件清单", "审美是可复核检查，不是感觉", "审计器绿"))),
    "部署": (("部署", "上线", "发布", "晋升"),
             ("mirror_space", "deployment_rehearsal", "one_key_deploy"),
             (("进镜像", "所有试跑都在镜像维度里", "生产零修改", "产物在 dimension/"),
              ("排练", "mirror_rehearse 取结论", "未全绿不许晋升", "排练报告在手"),
              ("声明落点", "room= 或 into_global_production=", "不声明落点 = 拒", "落点明确"),
              ("晋升", "mirror_release / one_key_deploy", "未全绿要放行得用专用钥匙（主人终端发）", "护照落盘"))),
}


def _goal_kind(goal: str) -> str:
    g = str(goal or "").lower()
    for kind, (words, _caps, _steps) in _ARCHETYPES.items():
        if any(w.lower() in g for w in words):
            return kind
    return ""


def _build_steps(kind: str, goal: str) -> list:
    steps = []
    if kind:
        _w, caps, tpl = _ARCHETYPES[kind]
        for i, (what, how, watch, judge) in enumerate(tpl, 1):
            steps.append({"id": "S%d" % i, "what": what, "how": how, "watch": watch,
                          "judge": judge, "who": caps[i - 1] if i - 1 < len(caps) else caps[-1],
                          "state": "pending", "evidence": []})
        return steps
    steps.append({"id": "S1", "what": "定意图", "how": "把「%s」拆成可判定的 1-3 句" % str(goal)[:40],
                  "watch": "没命中工序模板 ⇒ 这是粗图，不是细图", "judge": "意图可被一句话复述",
                  "who": "brain_route", "state": "pending", "evidence": []})
    for i, (what, how) in enumerate((("选路", "brain_route 现读候选位"),
                                     ("补齐细节", "按 detail_habit 五问补：输入/动作/明细/判据/接点"),
                                     ("再出图", "补齐后用 task_graph draft 重出一版")), 2):
        steps.append({"id": "S%d" % i, "what": what, "how": how, "watch": "别跳过",
                      "judge": "每步五件齐", "who": "", "state": "pending", "evidence": []})
    return steps


def _markmap(goal: str, kind: str, steps: list) -> str:
    lines = ["# %s" % (str(goal)[:60] or "任务"), "", "## 类别",
             "- %s" % (kind or "未命中模板（粗图）"), ""]
    for s in steps:
        lines += ["## %s %s" % (s["id"], s["what"]),
                  "- 怎么做：%s" % s["how"],
                  "- 注意：%s" % s["watch"],
                  "- 合格判据：%s" % s["judge"],
                  "- 谁干：%s" % (s["who"] or "（待定：先 brain_route 现读）"),
                  "- 状态：%s" % s.get("state", "pending"), ""]
    return "\n".join(lines)


def _graph_path(name: str) -> pathlib.Path:
    safe = re.sub(r"[^0-9A-Za-z_\u4e00-\u9fff-]", "_", str(name or "task"))[:60]
    return _dir() / "graphs" / (safe + ".json")


def _load_graph(name: str) -> dict | None:
    p = _graph_path(name)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        return None


def _save_graph(g: dict) -> pathlib.Path:
    p = _graph_path(g.get("name") or "task")
    p.write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def _task_graph(op: str, p: dict) -> dict:
    if op == "status":
        gs = sorted(x.name for x in (_dir() / "graphs").glob("*.json"))
        return {"ok": True, "op": "status", "ops": list(OPS["task_graph"]), "图": gs,
                "口径": "一句话 → 细到步的图；没模板就给粗图并如实标注（不假装细）"}
    if op == "draft":
        goal = str(p.get("goal") or "").strip()
        if not goal:
            return {"ok": False, "error": "缺 goal：任务一句话"}
        name = str(p.get("name") or goal[:24]).strip()
        kind = str(p.get("kind") or "").strip() or _goal_kind(goal)
        steps = _build_steps(kind, goal)
        g = {"name": name, "goal": goal, "kind": kind, "rev": 1, "at": _now(),
             "steps": steps, "status": "drafted", "claimed_by": None,
             "markmap": _markmap(goal, kind, steps),
             "口径": "图由模板 + 现读位面生成（不是模型编的）；要模型重推另走 external_llm 门"}
        return {"ok": True, "op": "draft", "name": name, "rev": 1, "kind": kind,
                "steps": steps, "markmap": g["markmap"], "落点": str(_save_graph(g)),
                "细度": "template" if kind else "coarse（未命中模板，这是粗图）"}
    if op == "read":
        g = _load_graph(str(p.get("name") or ""))
        if not g:
            return {"ok": False, "error": "没有这张图（name=%s）" % p.get("name")}
        return {"ok": True, "op": "read", "graph": g}
    if op == "claim":
        name, who = str(p.get("name") or ""), str(p.get("who") or "tentacle").strip()
        g = _load_graph(name)
        if not g:
            return {"ok": False, "error": "没有这张图（name=%s）" % name}
        g["claimed_by"], g["claimed_at"], g["status"] = who, _now(), "claimed"
        _save_graph(g)
        _append("claims.jsonl", {"at": g["claimed_at"], "name": name, "who": who, "op": "claim"})
        return {"ok": True, "op": "claim", "name": name, "claimed_by": who, "图": g["markmap"],
                "口径": "领图 = 领这张图去执行；步态用 step 回报"}
    if op == "step":
        name, sid = str(p.get("name") or ""), str(p.get("id") or "")
        g = _load_graph(name)
        if not g:
            return {"ok": False, "error": "没有这张图（name=%s）" % name}
        row = next((s for s in g["steps"] if s["id"] == sid), None)
        if not row:
            return {"ok": False, "error": "图里没有这一步（id=%s）" % sid,
                    "known": [s["id"] for s in g["steps"]]}
        state = str(p.get("state") or "running")
        if state not in ("pending", "running", "done", "blocked"):
            return {"ok": False, "error": "state 只认 pending/running/done/blocked"}
        row["state"] = state
        if p.get("evidence") is not None:
            row["evidence"] = [str(x) for x in (p.get("evidence") or [])]
        done = [s for s in g["steps"] if s["state"] == "done"]
        g["status"] = ("blocked" if any(s["state"] == "blocked" for s in g["steps"])
                       else ("done" if len(done) == len(g["steps"]) else "running"))
        _save_graph(g)
        _append("claims.jsonl", {"at": _now(), "name": name, "id": sid, "state": state,
                                 "evidence": row["evidence"]})
        out = {"ok": True, "op": "step", "name": name, "id": sid, "state": state,
               "进度": "%d/%d" % (len(done), len(g["steps"])), "图状态": g["status"]}
        if state == "blocked":
            out["下一步"] = ("不许直接停下问用户：把卡点交给 replan_loop.tick ⇒ "
                           "回大脑执行层重规划、重生成这张图，再继续")
        return out
    return {"ok": False, "error": "未知 op:%s" % op, "known": list(OPS["task_graph"])}
# ── ③ 回流环 ──────────────────────────────────────────────────────────────
def _replan_loop(op: str, p: dict) -> dict:
    if op == "status":
        return {"ok": True, "op": "status", "ops": list(OPS["replan_loop"]),
                "轮次上限": MAX_LOOP_ROUNDS,
                "口径": "卡点 → 回大脑执行层 → 重生成图 → 继续；轮次到顶就如实报到顶，不许假装还在推"}
    if op == "history":
        name = str(p.get("name") or "")
        rows = [r for r in _rows("loops.jsonl") if not name or r.get("name") == name]
        return {"ok": True, "op": "history", "count": len(rows), "rows": rows[-20:]}
    if op == "tick":
        name, sid = str(p.get("name") or ""), str(p.get("id") or "")
        blocker = str(p.get("blocker") or "").strip()
        g = _load_graph(name)
        if not g:
            return {"ok": False, "error": "没有这张图（name=%s）" % name}
        if not blocker:
            return {"ok": False, "error": "缺 blocker：卡在哪、卡成什么样（照实写）"}
        rounds = [r for r in _rows("loops.jsonl") if r.get("name") == name]
        if len(rounds) >= MAX_LOOP_ROUNDS:
            _append("loops.jsonl", {"at": _now(), "name": name, "id": sid,
                                    "round": len(rounds) + 1, "blocker": blocker[:200],
                                    "result": "rounds_exhausted"})
            return {"ok": False, "error": "回流轮次到顶（%d 轮）" % MAX_LOOP_ROUNDS,
                    "口径": "到顶如实报，不假装还能推；要接着走请主人给方向或放宽轮次",
                    "history": rounds}
        row = next((s for s in g["steps"] if s["id"] == sid), None)
        if row:
            row["state"] = "blocked"
            row["evidence"] = list(row.get("evidence") or []) + ["卡点：%s" % blocker[:160]]
        new_id = "R%d" % (len(rounds) + 1)
        g["steps"].append({"id": new_id, "what": "排因（回流第 %d 轮）" % (len(rounds) + 1),
                           "how": "把卡点拆成可判定的原因，逐条验：%s" % blocker[:80],
                           "watch": "不许把猜的原因当成真的原因", "judge": "每条原因有一条读数",
                           "who": "brain_route", "state": "pending", "evidence": []})
        g["rev"] = int(g.get("rev", 1)) + 1
        g["status"], g["at"] = "replanned", _now()
        g["markmap"] = _markmap(g["goal"], g.get("kind", ""), g["steps"])
        _save_graph(g)
        _append("loops.jsonl", {"at": g["at"], "name": name, "id": sid, "round": len(rounds) + 1,
                                "blocker": blocker[:200], "result": "replanned",
                                "new_step": new_id, "rev": g["rev"]})
        return {"ok": True, "op": "tick", "name": name, "round": len(rounds) + 1,
                "rev": g["rev"], "新步": new_id, "图": g["markmap"],
                "口径": "这一版是本地重排（模板+读数）；要模型重推另走 external_llm 门（需授权）"}
    return {"ok": False, "error": "未知 op:%s" % op, "known": list(OPS["replan_loop"])}


# ── ④ 在岗看板 ────────────────────────────────────────────────────────────
def _sw_rows() -> list:
    """现读 skill_watch 的观测账（谁用过、成没成）。读不到就如实回空表。"""
    d = os.environ.get("GBT_STORE_DIR")
    base = pathlib.Path(d) if d else (_ROOT / "gbt_allinone" / "store")
    p = base / "skill_watch" / "ledger.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except Exception:                                   # noqa: BLE001
                continue
    return out


def _duty_board(op: str, p: dict) -> dict:
    if op not in ("board", "status"):
        return {"ok": False, "error": "未知 op:%s" % op, "known": list(OPS["duty_board"])}
    # 🔴 2026-10-28：判据原来**没有时间窗** —— 用整本观测账的累计失败数。
    #   后果：位修好了也永远显示"卡住"（实测 brain_route 历史 29 笔失败，
    #   而现在每次都 ok=True，看板仍报它卡住）⇒ 看板失去可操作性。
    #   改成只看**最近 WINDOW 笔**：窗口内的失败才算数。
    WINDOW = 20
    obs = _sw_rows()
    _recent: dict = {}
    for r in obs:
        c = str(r.get("cap") or "")
        if not c:
            continue
        _recent.setdefault(c, []).append(r)
    obs = [r for c, rows in _recent.items() for r in rows[-WINDOW:]]
    per: dict = {}
    for r in obs:
        cap = str(r.get("cap") or "")
        if not cap:
            continue
        d = per.setdefault(cap, {"n": 0, "ok": 0, "last": "", "fail": 0,
                                 "err": "", "deny": 0})
        d["n"] += 1
        d["ok"] += 1 if r.get("ok") else 0
        d["last"] = max(d["last"], str(r.get("at") or ""))
        if not r.get("ok"):
            d["fail"] += 1
            d["err"] = str(r.get("error_class") or "")[:40]
            if "denied" in d["err"] or "denied" in str(r.get("error_class") or ""):
                d["deny"] += 1
    # 🔴 2026-10-28：原来把**所有失败**都算「卡住」，包括 `gate_denied`。
    #   实测主脑队列里 57% 的"卡住"是 `gate_denied` —— 那是**闸在工作**
    #   （位在等主人发票），不是脑卡住。把它算成故障就是假警报。
    #   现在拆成三档：等授权 / 真卡住 / 跑过但有失败。
    running, worn, stuck, awaiting = [], [], [], []
    for cap, d in sorted(per.items()):
        denied_only = d["deny"] >= 2 and d["fail"] <= d["deny"]
        if denied_only:
            awaiting.append({"位": cap, "被拒笔数": d["deny"],
                             "说明": "过授权门被拒 —— 等主人在终端发票，不是故障"})
        elif d["fail"] >= 2:
            stuck.append({"位": cap, "失败笔数": d["fail"], "最近错误类": d["err"]})
        elif d["fail"] == 0:
            running.append({"位": cap, "用了": d["n"], "最后": d["last"]})
        else:
            worn.append({"位": cap, "用了": d["n"], "成了": d["ok"], "最后": d["last"]})
    atlas = _atlas_caps()
    never = [str(c.get("kind")) for c in atlas
             if str(c.get("kind")) not in per and c.get("enabled")
             and not c.get("unimplemented") and not c.get("needs_confirmation")][:20]
    if op == "status":
        return {"ok": True, "op": "status", "ops": list(OPS["duty_board"]),
                "观察窗口": "每位最近 %d 笔 —— 历史失败不再永久挂账"
                            "（修好了不会永远显示卡住）" % WINDOW,
                "口径": "忙闲按读数算（skill_watch 观测账 + 图鉴位面）；"
                        "读不到就如实说读不到；**等授权 ≠ 卡住**"}
    if stuck:
        _append("queue.jsonl", {"at": _now(), "kind": "duty_board", "severity": "high",
                               "codes": ["有脑卡住"], "hits": stuck, "acked_at": None})
    return {"ok": True, "op": "board", "观测笔数": len(obs), "有观测的位": len(per),
            "在跑（零失败）": running[-10:], "跑过但有失败": worn[-10:],
            "卡住（失败≥2笔·已排除等授权）": stuck,
            "等授权（过门被拒，不是故障）": awaiting,
            "从未用过（图鉴在册·观测账 0 笔）": never,
            "上报": {"queued": 1 if stuck else 0},
            "观察窗口": "每位最近 %d 笔（历史失败不再永久挂账）" % WINDOW,
            "口径": "卡住的主动进主脑队列；空转/从未用过照实列出，不美化"}


KINDS = tuple(OPS)
DEFAULT_OP = {"llm_watch": "status", "task_graph": "status",
              "replan_loop": "status", "duty_board": "board"}


def run(kind: str, payload: dict | None = None) -> dict:
    """能力位统一入口（`api.run_task` 的 if 链调它）。四个位同一道门。"""
    k = str(kind or "").strip()
    if k not in OPS:
        return {"ok": False, "error": "未知能力位:%s" % k, "known": list(OPS)}
    p = dict(payload or {})
    op = str(p.get("op") or p.get("action") or "").strip() or DEFAULT_OP[k]
    fn = {"llm_watch": _llm_watch, "task_graph": _task_graph,
          "replan_loop": _replan_loop, "duty_board": _duty_board}[k]
    try:
        out = fn(op, {kk: vv for kk, vv in p.items() if kk not in ("op", "action")})
    except Exception as exc:                                    # noqa: BLE001
        return {"ok": False, "kind": k, "error": "%s: %s" % (type(exc).__name__, str(exc)[:160])}
    out.setdefault("kind", k)
    return out
