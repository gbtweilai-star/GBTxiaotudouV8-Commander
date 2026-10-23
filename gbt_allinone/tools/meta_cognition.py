# gbt-capability: meta_cognition
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""元认知循环（meta_cognition）· R-H200 只读骨架。

**知道自己不知道，比什么都知道更重要。**
四步：自省 → 先查内部 → 再查外部（需授权）→ 问主人 → 沉淀 → 进化。

五条红线（做成机械闸）：
  ① 自省不是自责 ② 不懂就问，不许硬猜 ③ 先查后问，不许瞎问
  ④ 问完必须沉淀 ⑤ 大脑也要自省。

本骨架只读：不写盘（**引用** root_fix.work_log 作为落点）、不出网、不执行。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

GAP_TYPES = ("missing_context", "uncertain", "unknown_topic", "missing_param")
GAP_CN = {"missing_context": "缺上下文", "uncertain": "不确定",
          "unknown_topic": "未知领域", "missing_param": "缺参数"}

SCOPES = ("tentacle", "brain", "router", "gate", "audit")

KNOWLEDGE_SPOTS = (
    "gbt_allinone/store/devoured/<主题>/knowledge.json",
    "gbt_allinone/store/pipeline/records/absorbed_knowledge.md-*.json",
    "gbt_allinone/brain_vault.py",
)

EXTERNAL_SCOPES = ("network_private", "external_llm", "data_export")

_SELF_BLAME_HINTS = ("我太差", "我真笨", "我完蛋", "我就是不行", "我不配", "我是废物")

RED_LINES = (
    "自省不是自责——自检只记录『哪里卡了』，不写『我太差了』（情绪归导演，自省归系统）",
    "不懂就问，不许硬猜——缺上下文 missing_context；不确定 uncertain；一律拒执行",
    "先查后问，不许瞎问——先查内部知识库，再查外部资料，最后才提问",
    "问完必须沉淀——得到答案后写入知识库，下次不用再问",
    "大脑也要自省——自省不只针对触手，大脑/路由/门禁/审计也要自检短板",
)


@dataclass
class SelfReflection:
    task_id: str
    scope: str = "tentacle"
    gaps: List[Dict] = field(default_factory=list)
    guesses: List[str] = field(default_factory=list)
    resolution: Optional[str] = None


class MetaCognitionLoop:
    """元认知循环（内存态骨架）：自省 → 查内部 → 查外部 → 问 → 沉淀。"""

    def __init__(self) -> None:
        self.reflections: List[SelfReflection] = []
        self.knowledge: Dict[str, str] = {}
        self.lookups: Dict[str, List[str]] = {}
        self.asked: Dict[str, str] = {}
        self.work_log_ref = "root_fix.work_log"

    def reflect(self, task_id: str, gaps: Optional[List[Dict]] = None,
                guesses: Optional[List[str]] = None, scope: str = "tentacle") -> dict:
        sc = str(scope or "tentacle").strip()
        if sc not in SCOPES:
            raise ValueError("未知 scope %r（可用：%s）" % (sc, "/".join(SCOPES)))
        rows = [dict(g) for g in (gaps or []) if isinstance(g, dict)]
        for g in rows:
            if g.get("type") not in GAP_TYPES:
                return {"ok": False, "denied": True, "rule": "unknown_gap_type",
                        "why": "gap 类型必须在 %s 之内（实测：%r）"
                               % ("/".join(GAP_TYPES), g.get("type"))}
        blob = " ".join(str(g.get("note") or "") for g in rows) \
            + " ".join(str(x) for x in (guesses or []))
        hit = [h for h in _SELF_BLAME_HINTS if h in blob]
        if hit:
            return {"ok": False, "denied": True, "rule": "self_blame_not_allowed",
                    "why": "自省不是自责（出现 %s）：情绪归导演，自省归系统 —— 只记『哪里卡了』" % hit}
        ref = SelfReflection(task_id=str(task_id or ""), scope=sc, gaps=rows,
                             guesses=[str(x) for x in (guesses or [])])
        self.reflections.append(ref)
        return {"ok": True, "readonly": True, "task_id": ref.task_id, "scope": ref.scope,
                "gaps": ref.gaps, "guesses": ref.guesses, "log_ref": self.work_log_ref}

    def look_up(self, topic: str, inside: bool = True) -> dict:
        key = str(topic or "").strip()
        if not key:
            raise ValueError("topic 不能为空")
        self.lookups.setdefault(key, [])
        if inside:
            if key in self.knowledge:
                self.lookups[key].append("knowledge_base")
                return {"ok": True, "readonly": True, "source": "knowledge_base",
                        "answer": self.knowledge[key]}
            self.lookups[key].append("internal_spots")
            return {"ok": False, "readonly": True, "reason": "not_in_knowledge_base",
                    "checked": list(KNOWLEDGE_SPOTS), "next": "查外部资料（需授权）或问主人"}
        self.lookups[key].append("external")
        return {"ok": True, "readonly": True, "source": "external",
                "requires_scopes": list(EXTERNAL_SCOPES),
                "note": "外部查证要授权：network_private / external_llm / data_export"}

    def external_scopes(self) -> dict:
        return {"ok": True, "readonly": True, "scopes": list(EXTERNAL_SCOPES),
                "note": "查外部资料必须先拿这三个作用域之一（主人发授权）"}

    def ask_owner(self, question: str, topic: str = "") -> dict:
        key = str(topic or question or "").strip()
        if not self.lookups.get(key):
            return {"ok": False, "denied": True, "rule": "must_look_up_first",
                    "why": "先查后问，不许瞎问：查过内部（必要时外部）再来问主人"}
        if key in self.asked:
            return {"ok": False, "denied": True, "rule": "already_asked_deposit_first",
                    "why": "这个问题问过了：先把答案沉淀进知识库，再谈下一步"}
        self.asked[key] = str(question or "")
        return {"ok": False, "reason": "need_owner_input", "question": str(question or ""),
                "topic": key, "note": "不确定就不执行，等主人回答"}

    def answer(self, topic: str, answer_text: str) -> dict:
        """收到主人答案 ⇒ **必须沉淀**（红线④）。"""
        key = str(topic or "").strip()
        if not str(answer_text or "").strip():
            return {"ok": False, "denied": True, "rule": "empty_answer"}
        self.knowledge[key] = str(answer_text)
        self.asked.pop(key, None)
        return {"ok": True, "readonly": True, "topic": key, "deposited": True,
                "note": "沉淀入知识库：下次不用再问"}

    def decide(self, gaps: Optional[List[Dict]] = None, guess: bool = False) -> dict:
        """下一步该干什么：**有缺口 ⇒ 先查再问，不许硬做**。"""
        rows = [g for g in (gaps or []) if isinstance(g, dict)]
        if guess:
            return {"ok": False, "denied": True, "rule": "no_guessing",
                    "why": "不懂就问，不许硬猜（盲猜即违规）"}
        if rows:
            return {"ok": False, "reason": "need_lookup_or_ask",
                    "gaps": [g.get("type") for g in rows],
                    "next": ["look_up(inside=True)", "look_up(inside=False)", "ask_owner()"],
                    "note": "有缺口就停下：先查内部 → 再查外部 → 最后问主人"}
        return {"ok": True, "readonly": True, "proceed": True}

    def report_short_boards(self, require_brain: bool = True) -> dict:
        """短板汇总（含大脑）：**只记触手不记大脑 ⇒ 拒**（红线⑤）。"""
        boards, scopes = set(), set()
        for ref in self.reflections:
            scopes.add(ref.scope)
            for g in ref.gaps:
                boards.add(g.get("type"))
        out = {"ok": True, "readonly": True, "short_boards": sorted(boards),
                "scopes_seen": sorted(scopes), "reflections": len(self.reflections),
                "bind_to": "native_surface（原生面）"}
        if require_brain and "brain" not in scopes:
            out["ok"] = False
            out["rule"] = "brain_not_covered"
            out["why"] = "大脑也要自省：自省记录里必须出现 scope=brain（不只触手）"
        return out

    # ── R-H295 · ④ 自省**真正落盘**（《待落刀登记.md》§二十 #4）────────────────
    # 台账原文：「自省**真正落盘**（接 `root_fix.work_log`，**现在是引用不是写入**）—— 未接」。
    # 病根就在上面 reflect() 的返回里：`log_ref: "root_fix.work_log"` 是一个**字符串引用**，
    # 全程没有任何一处真的调用它。于是"自省发现了什么"只活在内存里，进程一退就没了，
    # 而这恰恰违背红线④「问完必须沉淀」。
    # 修法：给一条**显式**落盘口。默认三条 op（law / knowledge_spots / external_scopes）
    # 仍然只读、不写盘 —— 谁要写必须点名 `op="persist"`，不许让只读调用产生副作用。
    def persist_reflections(self, task_id: str = "", scope: str = "tentacle",
                            gaps: Optional[List[Dict]] = None,
                            guesses: Optional[List[str]] = None) -> dict:
        """把自省出的缺口写进 `root_fix.work_log`（**唯一会写盘的路径**）。

        写失败一律如实报失败（`ok: False` + `why`），**不许**返回一个"看起来成功"
        的空回执 —— 那会让"沉淀了"变成一句没有人验证过的话。
        """
        rows = [dict(g) for g in (gaps or []) if isinstance(g, dict)]
        if not rows:
            rows = [dict(g) for ref in self.reflections for g in ref.gaps]
        if not rows:
            return {"ok": False, "readonly": True, "why": "没有可落盘的缺口（先 reflect 或传 gaps）",
                    "persisted": 0}
        bad = [g.get("type") for g in rows if g.get("type") not in GAP_TYPES]
        if bad:
            return {"ok": False, "denied": True, "rule": "unknown_gap_type",
                    "why": "gap 类型必须在 %s 之内（实测：%r）" % ("/".join(GAP_TYPES), bad)}

        try:
            from .. import root_fix  # 同包能力层：落点就是它，不经第二套日志
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "why": "接不上 root_fix.work_log：%s" % str(exc)[:120],
                    "persisted": 0}

        # R-H295：`root_fix.work_log` 的落盘是 `_WORKLOG_PATH.open('a')`，**它自己不建目录**。
        # 隔离 store（或任何还没 bootstrap 过的 store）下目录不存在 ⇒ 直接 FileNotFoundError。
        # 落点这一侧负责让落点存在：建不出目录不致命，后面的写入会如实报错，不假装成功。
        try:
            from .. import _paths
            _paths.STORE_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:  # noqa: BLE001
            pass

        import json as _json
        try:
            rec = root_fix.work_log(
                "lesson",
                "元认知自省：%d 处缺口（scope=%s%s）" % (
                    len(rows), scope, ("，task=%s" % task_id) if task_id else ""),
                _json.dumps({"gaps": rows, "guesses": [str(x) for x in (guesses or [])],
                             "scopes_seen": sorted({r.scope for r in self.reflections}),
                             "source": "meta_cognition.persist_reflections"},
                            ensure_ascii=False)[:4000],
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "why": "写 work_log 抛错：%s: %s"
                                         % (type(exc).__name__, str(exc)[:100]), "persisted": 0}

        # root_fix.work_log 自带去重窗口：重复自省同一批缺口会被它拦下并标注 duplicate。
        dup = bool(isinstance(rec, dict) and rec.get("duplicate"))
        return {"ok": True, "readonly": False, "persisted": 0 if dup else 1,
                "duplicate": dup, "gaps": len(rows), "scope": scope,
                "landing": "root_fix.work_log（store/work_log.jsonl）",
                "receipt": rec if isinstance(rec, dict) else {"raw": str(rec)[:200]},
                "note": ("与最近一条重复，work_log 已按去重窗口拦下（不是没写，是同一批不重复记）"
                         if dup else "已落 root_fix.work_log；成长可回放")}


_DEFAULT = MetaCognitionLoop()
# 落盘计数：让只读口也能如实报"沉淀了几条"（此前这个数字根本不存在，
# 因为从来没有真的写过 —— 台账 §二十 #4「现在是引用不是写入」）。
_PERSISTED = {"count": 0, "last": None}


def run(op="law", **params) -> dict:
    """能力入口。

    **只读** op（不写盘、不出网、不执行）：law / knowledge_spots / external_scopes /
    reflections / short_boards / decide。
    **唯一会写盘**的 op：`persist` —— 把自省出的缺口落进 `root_fix.work_log`
    （台账 §二十 #4「自省真正落盘」）。除它以外一律只读，谁要写必须点名。
    """
    op = str(op or "law")
    if op == "law":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES),
                "gap_types": [{"key": k, "cn": GAP_CN[k]} for k in GAP_TYPES],
                "scopes": list(SCOPES), "log_ref": _DEFAULT.work_log_ref,
                "knowledge_spots": list(KNOWLEDGE_SPOTS),
                # 让"引用不是写入"这件事**看得见**：只读口如实报已落盘多少条
                "persisted_reflections": _PERSISTED["count"],
                "ops": ["law", "knowledge_spots", "external_scopes", "reflect",
                        "reflections", "short_boards", "decide", "persist"],
                "non_readonly_op": "persist（会写 root_fix.work_log）"}
    if op == "knowledge_spots":
        return {"ok": True, "readonly": True, "spots": list(KNOWLEDGE_SPOTS),
                "note": "没有统一 KB：三处口径未收口（登记在册）"}
    if op == "external_scopes":
        return _DEFAULT.external_scopes()
    if op == "reflect":
        return _DEFAULT.reflect(str(params.get("task_id") or ""),
                                params.get("gaps"), params.get("guesses"),
                                str(params.get("scope") or "tentacle"))
    if op == "reflections":
        return {"ok": True, "readonly": True, "count": len(_DEFAULT.reflections),
                "reflections": [{"task_id": r.task_id, "scope": r.scope,
                                 "gaps": r.gaps, "guesses": r.guesses}
                                for r in _DEFAULT.reflections],
                "persisted": _PERSISTED["count"]}
    if op == "short_boards":
        return _DEFAULT.report_short_boards(bool(params.get("require_brain", True)))
    if op == "decide":
        return _DEFAULT.decide(params.get("gaps"), bool(params.get("guess", False)))
    if op == "persist":
        out = _DEFAULT.persist_reflections(
            str(params.get("task_id") or ""), str(params.get("scope") or "tentacle"),
            params.get("gaps"), params.get("guesses"))
        if out.get("ok"):
            _PERSISTED["count"] += int(out.get("persisted") or 0)
            _PERSISTED["last"] = out
        return out
    raise ValueError("未知 op %r（可用：law/knowledge_spots/external_scopes/reflect/"
                     "reflections/short_boards/decide/persist）" % (op,))


HONEST_BOUNDARY = (
    "元认知循环保证『自省、查证、提问、沉淀』四步可执行；"
    "它保证不了『永远不犯同一个错』——但它能保证同一个坑不会静默地再踩一次。"
)
