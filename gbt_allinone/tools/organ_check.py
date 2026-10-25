"""器官化门禁（organ_check）—— 把「功能 vs 器官」四条判据变成可跑的断言。

四条判据（Owner · 2026-09-18 · 每一条都对应一个可观测行为差异）：
  C1 挂在哪     功能=挂在清单上（`caps_registry.py` 里能查到名字）／器官=长在身体里（装配期默认就绪，不查清单）
  C2 要调用吗   功能=代码里有显式 `run_task("xxx")`／器官=行为发生时不产生调用指令
  C3 要选择吗   功能=上下文里出现「该用哪个能力」的推理／器官=没有这个推理步骤
  C4 什么时候用 功能=依赖「用户提了这个需求」／器官=默认挂载，随时在位

本工具**只报实测**：探不到的写 `unknown`，不许拿「感觉上像器官了」顶账。
判定规则：四项全绿 = 器官；有一项不是绿 = 仍是功能（四条是合取）。

用法：python -m gbt_allinone.tools.organ_check
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
WORKSPACE = HERE.parents[2]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

GREEN, RED, UNK = True, False, None

# 生命档案「常驻上下文段」的段标记：只有真加了常驻段才会出现。
# 只查「生命档案」三个字会把既有文字提醒误判成挂载（本工具首跑实测踩过）。
LIFE_MARK = "【生命档案·常驻】"


def _caps() -> dict:
    try:
        from gbt_allinone.caps_registry import BENIGN_CAPS
        return dict(BENIGN_CAPS)
    except Exception:  # noqa: BLE001
        return {}


def _on_list(caps: dict, prefixes: tuple) -> list:
    """C1 功能侧证据：能力名在清单（注册表）里查得到。"""
    return sorted(n for n in caps if any(n == p or n.startswith(p) for p in prefixes))


def _probe_err(organ: str, exc: BaseException) -> dict:
    """R-H295 · ⑥ G1/G2：探针**量不了**时的结构化证据。

    《触手覆盖矩阵.md》§三：门组 4 个模块只有 3 个能报"做不了"，本文件是缺的那个。
    原来失败记的是自由文本 `f"err {type(exc).__name__}"` —— 人看得见，
    机器读不出"是缺依赖、契约变了、还是导入不到"。证据要能被机器读，才算证据。
    （值仍是 JSON 可显示的 dict，不改变 ev 的用法。）
    """
    return {
        "ok": False,
        "unavailable": True,
        "denied": False,
        "rule": "organ_probe_unavailable",
        "action": "probe_" + str(organ),
        # 🔴 2026-09-22 修（错报治理）：原来只给 `missing`，而这一支是**探针量不了**，
        # 不是"这个器官不存在"。机器读 `missing` 会得出"缺件"的错误结论 ⇒
        # 补 `unknown`（未测）并把口径写进 note：**未测 ≠ 不存在**。
        # `missing` 保留不动（不破坏既有消费者），但语义由 note 说清。
        "missing": [str(organ)],
        "unknown": [str(organ)],
        "note": "探针**量不了**（未测）—— 不等于该器官不存在；缺依赖 / 契约变了 / 导入不到，"
                "看 why 里的异常类型",
        "why": "%s: %s" % (type(exc).__name__, str(exc)[:160]),
        "text": "err %s" % type(exc).__name__,   # 保留原可读文本，便于人眼对照
    }


def probe_vision(caps):
    """视觉总线：器官侧=装配期就绪（冷态第一次取眼即成功）。"""
    ev = {}
    try:
        from gbt_allinone.tentacle import bridge as TB
        ev["装配期就绪 eye_ready()"] = TB.eye_ready()
    except Exception as exc:  # noqa: BLE001
        ev["装配期就绪 eye_ready()"] = _probe_err("装配期就绪 eye_ready()", exc)
    listed = _on_list(caps, ("vision", "tentacle_vision", "shot", "screenshot"))
    c1 = ("清单条目 " + str(listed), GREEN if listed else UNK)
    c2 = ("默认路径无显式取帧调用", UNK)
    c3 = ("取帧是否需显式指名", UNK)
    c4 = ("是否默认挂载", UNK)
    return c1, c2, c3, c4, ev


def probe_tentacle(caps):
    """亿万触手意图库：器官侧=意图进来自动命中（无需显式给 action）。"""
    ev = {}
    try:
        from gbt_allinone.tentacle import bridge as TB
        import inspect
        sig = str(inspect.signature(TB.invoke))
        ev["invoke 契约"] = sig
        ev["action 是否必填"] = "method" in sig
    except Exception as exc:  # noqa: BLE001
        ev["invoke 契约"] = _probe_err("invoke 契约", exc)
    try:
        from gbt_allinone.tentacle import bridge as TB
        ev["邻域映射条目"] = len(getattr(TB, "TENTACLE_NEIGHBORHOOD_MAP", {}) or {})
    except Exception:  # noqa: BLE001
        pass
    listed = _on_list(caps, ("tentacle", "eye", "domain_"))
    must_name = ev.get("action 是否必填") is True
    return (listed, GREEN), ("调用契约要求显式指名" if must_name else "默认路径无显式调用", RED if must_name else UNK), \
           ("仍需先选能力名" if must_name else "无需选择", RED if must_name else UNK), ("默认挂载", UNK), ev


def probe_life(caps):
    """生命档案：器官侧=默认挂载上下文（默认指令里已含档案段）。"""
    ev = {}
    txt = ""
    try:
        from gbt_allinone import codex_bridge as CB
        dev = str(CB.default_developer_instructions() or '')
        tools = str(CB.dynamic_tool_specs() or '')
        both = dev + tools
        # 两来源分开记账：工具清单里出现「生命档案」= 工具在，不等于上下文挂载。
        ev['默认指令字符数'] = len(dev)
        ev['工具清单字符数'] = len(tools)
        ev['默认指令里含「生命档案」'] = '生命档案' in dev
        ev['工具清单里含「生命档案」'] = '生命档案' in tools
        ev['含常驻段标记 ' + LIFE_MARK] = LIFE_MARK in both
        ev['只有文字提醒（未挂载）'] = (LIFE_MARK not in both) and ('生命档案' in both)
    except Exception as exc:  # noqa: BLE001
        ev["默认指令"] = _probe_err("默认指令", exc)
    listed = _on_list(caps, ("life", "archive", "memory"))
    mounted = bool(ev.get("含常驻段标记 " + LIFE_MARK))
    return ("清单条目 " + str(listed), GREEN if listed else UNK), ("默认路径无显式查询", UNK), \
           ("是否需显式查询档案", UNK), \
           ("默认挂载，随时在位" if mounted else "未进默认上下文（只有文字提醒）",
            GREEN if mounted else RED), ev


def probe_charter(caps):
    """脑部宪法域：器官侧=system_prompt() 里默认生效。"""
    ev = {}
    try:
        from gbt_allinone import coding_discipline as CD
        # system_prompt(context) 是**带参**入口：无参调用必 TypeError。
        # 旧写法把它吞成空串，写出「字符数 = 0」的假数字（判据对、证据假）。
        txt = str(CD.system_prompt({'_coding_discipline': True}) or '')
        ev['契约段字符数'] = len(txt)
        ev['含章号区段'] = '第' in txt and '章' in txt
        try:
            from gbt_allinone import codex_bridge as _CB
            ev['契约已进默认指令'] = bool(txt) and txt in _CB.default_developer_instructions()
        except Exception:  # noqa: BLE001
            ev['契约已进默认指令'] = 'err'
    except Exception as exc:  # noqa: BLE001
        ev["system_prompt"] = _probe_err("system_prompt", exc)
    listed = _on_list(caps, ("charter", "constitution"))
    return ("清单条目 " + str(listed), GREEN if listed else UNK), ("默认路径无显式调用", UNK), \
           ("是否需显式调用", UNK), ("默认生效" if ev.get("含章号区段") else "未注入（CHARTER 章号区段不在注入面）", GREEN if ev.get("含章号区段") else RED), ev


def probe_brainexec(caps):
    """大脑执行层：器官侧=装配期自检就绪（health 全绿）。"""
    ev = {}
    try:
        from gbt_allinone import brain_exec as BE
        h = BE.health()
        ev["health ok"] = h.get("ok")
        ev["score"] = h.get("score")
        ev["healthy/total"] = f'{h.get("healthy_dims")}/{h.get("total_dims")}'
    except Exception as exc:  # noqa: BLE001
        ev["health"] = _probe_err("health", exc)
    listed = _on_list(caps, ("brain_",))
    return (listed, GREEN if listed else RED), ("要显式调 brain_unify 才走全链", RED), \
           ("需先决定调哪个 brain_*", RED), ("装配期自检就绪" if ev.get("health ok") else "未自检",
                                            GREEN if ev.get("health ok") else RED), ev


# ── C3 判据的机械面：默认路径上「必须写出能力名」的调用点数（显式指名点）──

NAMING_RE = None


def scan_explicit_naming(prefixes: tuple) -> list:
    """数「显式指名点」：代码里把能力名当字面量传给 run_task / invoke 的地方。

    「需要选择」的可观测形态就是这个 —— 不写出名字，能力不会被命中；
    找出处长 = 判据有牙齿，不需要争论"模型当时有没有在做选择"。
    """
    import re
    from pathlib import Path
    pat = re.compile(r'(?:run_task|invoke|dispatch)\s*\(\s*[\'"]([A-Za-z_][\w.]*)[\'"]')
    hits = []
    for py in sorted((WORKSPACE / "gbt_allinone").rglob("*.py")):
        parts = py.relative_to(WORKSPACE).parts   # Windows 上 str(rel) 是反斜杠，用 parts 判才准
        rel = "/".join(parts)
        if "tests" in parts or "tools" in parts or ".scratch" in parts:
            continue
        try:
            for i, line in enumerate(py.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                for m in pat.finditer(line):
                    name = m.group(1)
                    if any(name == p or name.startswith(p) for p in prefixes):
                        hits.append(f"{rel}:{i} -> {name}")
        except Exception:  # noqa: BLE001
            continue
    return hits


TOPIC_SEEDS = (
    "帮我盯着这个话题，有变化告诉我",
    "追踪一下 AI 行业最新动态",
    "每天给我一份早报",
)


def probe_topicwatch(caps):
    """话题追踪：器官侧=说人话就命中（不产生「该用哪个能力」的判断）。

    C3 口径（2026-09-18 修）：原版把 C3 写成「进备选」——但 route() 的 alternatives 天然排除
    best，所以 best 命中时 C3 永远红 —— 判据自相矛盾（与 O51 同族，续计）。
    改成可观测的正确形态：**句子里不出现能力名字面量，路由仍选中它**。
    """
    ev = {}
    hits = []
    try:
        from gbt_allinone.brain_exec import route as _route
        for s in TOPIC_SEEDS:
            r = _route(s)
            best = (r.get("best") or {}).get("kind")
            alts = [a.get("kind") for a in (r.get("alternatives") or [])]
            hits.append({"seed": s, "best": best,
                         "best_hit": best == "topic_watch",
                         "no_name_in_seed": "topic_watch" not in s,
                         "in_alt": "topic_watch" in alts})
    except Exception as exc:  # noqa: BLE001
        ev["route 探针"] = _probe_err("route 探针", exc)
    n = len(TOPIC_SEEDS)
    best_n = sum(1 for h in hits if h["best_hit"])
    c3_n = sum(1 for h in hits if h["best_hit"] and h["no_name_in_seed"])
    ev["种子句 best 命中"] = f"{best_n}/{n}"
    ev["不写能力名仍命中"] = f"{c3_n}/{n}"
    ev["明细"] = hits
    listed = _on_list(caps, ("topic_watch",))
    c1 = ("清单条目 " + str(listed), GREEN if listed else UNK)
    c2 = (f"说人话即命中（best {best_n}/{n}）",
          GREEN if hits and best_n == n else (RED if hits else UNK))
    c3 = (f"句中不含能力名字面量仍命中（{c3_n}/{n}）",
          GREEN if hits and c3_n == n else (RED if hits else UNK))
    t4 = {}
    try:
        from gbt_allinone import topic_watch as _TW
        t4 = _TW.timer()
    except Exception as exc:  # noqa: BLE001
        t4 = {"err": type(exc).__name__}
    ev["定时腿"] = {k: t4.get(k) for k in
                    ("ok", "heartbeat_every", "heartbeat_every_path",
                     "heartbeat_md_marked", "process_primitives", "carrier", "gaps")}
    ev["定时腿下次触发"] = t4.get("next_fires")
    c4 = ("现成心跳承载（心跳 " + str(t4.get("heartbeat_every") or "?")
          + " · 段标记 " + ("在" if t4.get("heartbeat_md_marked") else "缺")
          + " · 新增进程 " + str(t4.get("process_primitives", "?")) + "）",
          GREEN if t4.get("ok") is True else (RED if t4.get("ok") is False else UNK))
    return c1, c2, c3, c4, ev


PREFIXES = {
    "原生视觉总线": ("vision", "shot", "screenshot"),
    "亿万触手意图库": ("tentacle", "domain_", "eye"),
    "生命档案": ("life", "archive", "memory"),
    "脑部宪法域": ("charter", "constitution"),
    "大脑执行层": ("brain_",),
    "话题追踪": ("topic_watch",),
}


TARGETS = [
    ("亿万触手意图库", probe_tentacle),
    ("原生视觉总线", probe_vision),
    ("生命档案", probe_life),
    ("脑部宪法域", probe_charter),
    ("大脑执行层", probe_brainexec),
    ("话题追踪", probe_topicwatch),
]


def _score(verdicts) -> int:
    """四条各 25%：绿=25，红=0，未测=0（未测不按绿算 —— 《反假绿律》）。"""
    return sum(1 for v in verdicts if v is True) * 25


_GRADES = {100: "器官", 75: "准器官", 50: "半功能", 25: "功能", 0: "未落地"}


def _grade(score: int) -> str:
    return _GRADES.get(score, "")


def _pad(text, width: int) -> str:
    """按东亚宽度补空格（CJK 算 2 列），让表格真正对齐。"""
    from unicodedata import east_asian_width
    used = sum(2 if east_asian_width(ch) in ("W", "F") else 1 for ch in text)
    return text + " " * max(1, width - used)


def _mark(v) -> str:
    return "绿" if v is True else ("红" if v is False else "未测")


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="器官化门禁：四条判据 x 五个能力 -> 分数")
    ap.add_argument("--organ", default=None, help="只测一个器官（名字模糊匹配，如 触手）")
    ap.add_argument("--json", action="store_true", help="只输出 JSON（供脚本消费）")
    args = ap.parse_args(argv)

    caps = _caps()
    targets = [t for t in TARGETS if args.organ in t[0]] if args.organ else list(TARGETS)
    if args.organ and not targets:
        print("[organ_check] 没匹配到「" + args.organ + "」；可选：" + " / ".join(t[0] for t in TARGETS))
        return 2
    if not args.json:
        print(f"[organ_check] 注册表 cap 数 = {len(caps)} · 目标 {len(targets)} 个")

    rows, table = [], []
    for name, fn in targets:
        try:
            c1, c2, c3, c4, ev = fn(caps)
        except Exception as exc:  # noqa: BLE001
            rows.append({"cap": name, "error": f"{type(exc).__name__}: {exc}"})
            table.append((name, None, 0, "探针异常"))
            continue
        hits = scan_explicit_naming(PREFIXES.get(name, ()))
        if hits:
            c3 = (f"仍需写出能力名（显式指名点 {len(hits)} 处，例 {hits[0]}）", RED)
        quad = (c1, c2, c3, c4)
        score = _score([q[1] for q in quad])
        rows.append({"cap": name, "score": score, "grade": _grade(score),
                     "C1_挂在哪": c1, "C2_要调用吗": c2, "C3_要选择吗": c3, "C4_什么时候用": c4,
                     "显式指名点": hits, "evidence": ev})
        table.append((name, quad, score, _grade(score)))
        if args.json:
            continue
        print(f"\n-- {name} -- {_grade(score)}（{score}%）")
        for label, item in zip(("C1 挂在哪", "C2 要调用吗", "C3 要选择吗", "C4 什么时候用"), quad):
            print(f"   {label}: [{_mark(item[1])}] {item[0]}")
        for k, v in ev.items():
            print(f"      证据 {k} = {v}")
        for h in hits[:5]:
            print(f"      显式指名点 {h}")

    overall = (sum(t[2] for t in table) // len(table)) if table else 0
    payload = {"overall": overall, "grade": _grade(overall),
               "organs": sum(1 for t in table if t[2] == 100), "total": len(table), "rows": rows}

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=1, default=str))
    else:
        print("\n" + "-" * 58)
        print(_pad("器官", 14) + _pad("C1", 6) + _pad("C2", 6) + _pad("C3", 6) + _pad("C4", 6)
              + _pad("分数", 8) + "状态")
        for name, quad, score, grade in table:
            cells = "".join(_pad(_mark(q[1]), 6) for q in quad) if quad else " " * 24
            print(_pad(name, 14) + cells + _pad(str(score) + "%", 8) + grade)
        print("-" * 58)
        print(_pad("整体", 14) + " " * 24 + str(overall) + "%")
        print("\n[organ_check] 器官 = " + str(payload["organs"]) + "/" + str(payload["total"])
              + " · 整体 " + str(overall) + "%（四条各 25%；绿=25%，红=0%，未测=0%——未测不按绿算）")

    out = Path(WORKSPACE) / ".scratch" / "_organ_check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
