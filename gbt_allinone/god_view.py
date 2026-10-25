# -*- coding: utf-8 -*-
# gbt-capability: (pure)  ⏻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""上帝视角（god_view）—— **超级导航 + 意见与建议**（定心丸）。

主人令（2026-10-09，逐字）：「哦，还有上帝视角也是一个超级导航和给你意见和建议也是一种给项目增加的定心丸」。

## 为什么现在才建（如实交代来历）
这个名字来自主人给的 Awesome Tools「OpenClaw Monitor = 上帝视角的监控组件」（索引
gbt_allinone/tools/awesome_tools_index.py:67-69），但 2026-09-20 盘上取证 **0 命中**，
所以索引里只能标 status=unverified / evidence=None。V8 原先的"上帝视角"只是
holo_pet/app.js 里一块**只读总览**（自述"只呈现，不执行"）——**既不会导航，也不会给意见**。
本件把它补成**真能力位**：读真读数 → 指路（导航）+ 提建议（定心丸）。

## 四条口径（写死）
1. **只读**：只读注册表与 state/ 下的账本，**不起进程、不写盘、不出网**（零作用域）。
2. **不许反问**：按 ux_doctrine 的不开口闸 —— 输出只给**具体候选 + 可直接照抄的命令**，
   不许出现「请问你想做什么」这类把活推回用户的话。
3. **不猜**：导航靠**注册表描述词命中**排序（命中即给分数与命中词），给不出候选就如实说没有。
4. **建议要有据**：每条建议都带**它依据的哪个读数**；没有读数支撑的不许写成建议。

## 四个 op
  overview  全局一屏：能力位/域分布 + 报警 + 今天动作 + 交付闸（都是现读）
  navigate  goal=<一句话> ⇒ 命中哪些能力位/域，附**可直接照抄的调用命令**（超级导航）
  advise    按现读状态给**排好序的意见与建议**，每条带依据（定心丸）
  where     我在哪：一页说清项目现状与下一步
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
AUDIT = _ROOT / "state" / "capability-audit.json"
ACTION_LEDGER = _ROOT / "state" / "action-ledger.jsonl"
SWEEP = _ROOT / "state" / "caps-sweep-20261009.json"
CMD = "py -3.14 -X utf8 tools/codex-scripts/five-dim.py cap %s '%s'"

# 常见意图 → 提示词（帮导航把人话对上能力位；**不猜实现，只做词面桥接**）
INTENT_HINTS: dict = {
    "视频": ("video", "media", "film", "短视频", "影视", "出片", "剪辑", "成片"),
    "音乐": ("music", "audio", "音频", "配乐", "母带"),
    "数字人": ("avatar", "digital", "数字人", "口型", "绑骨", "动作"),
    "安全": ("sec", "hacker", "安全", "漏洞", "攻击", "扫描", "靶标"),
    "能力": ("cap", "registry", "能力", "接线", "分派"),
    "部署": ("deploy", "mirror", "room", "部署", "镜像", "上线", "发布"),
    "检查": ("audit", "check", "checkup", "体检", "报警", "故障", "巡检"),
    "触手": ("tentacle", "触手", "装备", "职业"),
    "记忆": ("memory", "brain", "vault", "记忆", "脑库"),
    "钱": ("publish", "biz", "settle", "变现", "收益", "平台"),
    "逆向": ("rea", "reverse", "逆向", "反编译", "反汇编", "二进制", "无源码", "decompile", "disassemble"),
}


def _registry() -> dict:
    try:
        from .caps_registry import BENIGN_CAPS
        return dict(BENIGN_CAPS)
    except Exception:                                        # noqa: BLE001
        return {}


def _read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _ledger_rows() -> list:
    if not ACTION_LEDGER.is_file():
        return []
    out = []
    for line in ACTION_LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _alarms() -> dict:
    d = _read_json(AUDIT)
    items = d.get("items") or []
    bad = [i for i in items if i.get("state") in ("断连", "缺失")]
    opt = [i for i in items if i.get("state") == "按需未启用"]
    return {"总项": len(items), "断连缺失": len(bad), "按需未启用": len(opt),
            "逐条": [{"id": i.get("id"), "state": i.get("state")} for i in bad]}


def _delivery() -> dict:
    d = _read_json(SWEEP)
    rows = d.get("逐位") or {}
    if not rows:
        return {"known": False}
    ok = ("通", "如实否")
    good = sum(1 for r in rows.values() if (r or {}).get("verdict") in ok)
    blocked = [k for k, r in rows.items() if (r or {}).get("verdict") in
               ("要参数", "缺依赖", "真坏", "超时", "未扫")]
    try:
        from .delivery_gate import deliverable
        blocked = [k for k in rows if not deliverable(k)["可交付"]]
        good = len(rows) - len(blocked)
    except Exception:                                        # noqa: BLE001
        pass
    return {"known": True, "总位": len(rows), "可交付": good, "禁交付": len(blocked),
            "禁交付名单": sorted(blocked)[:20]}


def overview() -> dict:
    caps = _registry()
    from collections import Counter
    dom = Counter((v or {}).get("domain") for v in caps.values())
    al = _alarms()
    dep = _delivery()
    rows = [r for r in _ledger_rows() if str(r.get("at", "")).startswith(time.strftime("%Y-%m-%d"))]
    return {"ok": True, "op": "overview", "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "能力位": len(caps), "域数": len(dom), "域分布": dict(dom.most_common(12)),
            "报警": al, "交付闸": dep, "今天动作数": len(rows)}


def _score(kind: str, entry: dict, goal: str) -> tuple:
    """打分：**意图族命中权 3**（人话对上职业域）· 直击词权 1（名词对名词）。

    🔴 第一版是纯计数 ⇒ 「出一支30秒短视频」返回 25 条候选，那不叫导航。收紧：
       意图族必须命中才算强候选；只有直击词命中且 ≥2 个才留下。
    """
    text = "%s %s %s" % (kind, (entry or {}).get("desc", ""), (entry or {}).get("domain", ""))
    low = text.lower()
    score, hits = 0, []
    # ① 意图族（强信号）
    for fam, words in INTENT_HINTS.items():
        if any(w in goal for w in words):
            if fam.lower() in low or any(w in text for w in words):
                score += 3
                hits.append("意图:" + fam)
    # ② 直击词（名词，2 字以上中文 / 3 字以上英文，且不能是通用词）
    STOP = ("出一", "支", "秒", "视频"[:0])
    for w in set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z_]{3,}", goal)):
        if w in STOP or len(w) < 2:
            continue
        if w.lower() in low:
            score += 1
            hits.append(w)
    return score, sorted(set(hits))[:4]


# 意图族 → **候选域**（域只有 30 个、是准的；靠泛词匹配描述是无限且不准的 —— 第一版栽在这）
INTENT_DOMAINS: dict = {
    "视频": ("video", "creation"),
    "音乐": ("creation", "video"),
    "数字人": ("creation", "video"),
    "安全": ("security", "recon"),
    "能力": ("system", "tools"),
    "部署": ("pipeline", "engine"),
    "检查": ("system",),
    "触手": ("tentacle",),
    "记忆": ("mind", "brain"),
    "钱": ("social", "creation"),
    "逆向": ("recon", "security", "tentacle"),
}
# 泛词表：这些词在任何描述里都可能出现，命中**不算分**（第一版就是被它们淹了）
GENERIC = ("扫描", "处理", "生成", "读取", "查看", "状态", "管理", "运行", "执行", "一个", "进行")


def _tokens(goal: str) -> list:
    """中文**二元滑窗**取词（没有分词器时的标准做法）。

    🔴 第一版按 2-4 字切块 ⇒ 「出一支30秒短视频」切成「出一支 / 秒短视频」这两个**假词**，
       在任何描述里都命中不了 ⇒ 全部落到兜底档（实测 6 条目标全是档 C）。
       改用滑窗后「短视」「视频」「母带」这类真词才出得来。
    """
    out, seen = [], set()
    zh = re.findall(r"[\u4e00-\u9fff]+", goal)
    for run in zh:
        for i in range(len(run) - 1):
            w = run[i:i + 2]
            if w in seen or w in GENERIC:
                continue
            seen.add(w)
            out.append(w)
    for w in re.findall(r"[A-Za-z_]{3,}", goal):
        if w.lower() not in seen:
            seen.add(w.lower())
            out.append(w)
    return out


def navigate(goal: str, top: int = 6) -> dict:
    goal = str(goal or "").strip()
    caps = _registry()
    if not goal:
        return {"ok": False, "op": "navigate", "error": "goal 不能为空",
                "例": "goal=出一支 30 秒短视频"}
    # ① 先按**意图族 → 域**圈候选（准）
    fams = [f for f, words in INTENT_HINTS.items() if any(w in goal for w in words)]
    doms = {d for f in fams for d in INTENT_DOMAINS.get(f, ())}
    toks = _tokens(goal) or [goal]
    scored = []
    for kind, entry in caps.items():
        ent = entry or {}
        dm = str(ent.get("domain") or "")
        text = "%s %s" % (kind, ent.get("desc", ""))
        hits = [t for t in toks if t.lower() in text.lower()]
        in_dom = dm in doms
        # 三档（档高者必在前；同档比命中词数）：
        #   A = 域内 **且** 有直击词（最准）· B = 域外但两个以上直击词 · C = 域内兜底（没直击词）
        if in_dom and hits:
            tier, score = "A", 30 + len(hits)
        elif (not in_dom) and len(hits) >= 2:
            tier, score = "B", 20 + len(hits)
        elif in_dom:
            tier, score = "C", 10
        else:
            continue
        scored.append({"能力位": kind, "域": dm, "档": tier, "分": score,
                       "命中词": (["意图:" + f for f in fams] if in_dom else []) + hits[:3],
                       "用途": str(ent.get("desc", ""))[:80],
                       "怎么调": CMD % (kind, "{}")})
    scored.sort(key=lambda x: (-x["分"], x["能力位"]))
    if not scored:
        for fam, words in INTENT_HINTS.items():
            if any(w in goal for w in words):
                cand = [k for k, v in caps.items()
                        if any(w in "%s %s" % (k, (v or {}).get("desc", "")) for w in words)]
                scored = [{"能力位": k, "域": (caps[k] or {}).get("domain"), "分": 1,
                           "命中词": ["意图:" + fam],
                           "用途": str((caps[k] or {}).get("desc", ""))[:80],
                           "怎么调": CMD % (k, "{}")} for k in cand[:top]]
    return {"ok": True, "op": "navigate", "goal": goal, "候选数": len(scored),
            "候选": scored[:top],
            "没命中就如实": ("没有能力位命中这句目标 —— 不是「没有这条路」，而是词面对不上；"
                             "换更具体的名词再试，或 op=advise 看当前该做什么") if not scored else ""}


def advise(live: bool = False) -> dict:
    al = _alarms()
    dep = _delivery()
    rows = _ledger_rows()
    openx = [r for r in rows if not r.get("closed")]
    by_idem: dict = {}
    for r in rows:
        by_idem.setdefault(r.get("idem"), []).append(r)
    dup = [k for k, v in by_idem.items() if len(v) > 1]
    out = []
    if al.get("断连缺失"):
        out.append({"优先级": "高", "建议": "先清报警（断连 %d / 缺失 0）" % al["断连缺失"],
                    "依据": "state/capability-audit.json 现读：断连 %d 条" % al["断连缺失"],
                    "怎么做": "py -3.14 -X utf8 tools/codex-scripts/capability-audit.py",
                    "一键": True})
    if dep.get("known") and dep.get("禁交付"):
        out.append({"优先级": "高",
                    "建议": "补齐 %d 个禁交付能力位的闭环（没闭环不许交付）" % dep["禁交付"],
                    "依据": "交付闸现读：可交付 %d / 禁交付 %d" % (dep["可交付"], dep["禁交付"]),
                    "怎么做": "py -3.14 -X utf8 -m gbt_allinone.delivery_gate audit",
                    "名单": dep.get("禁交付名单")})
    if openx:
        out.append({"优先级": "中", "建议": "收口 %d 条未闭合动作" % len(openx),
                    "依据": "state/action-ledger.jsonl 里 closed=false 的行",
                    "怎么做": "py -3.14 -X utf8 tools/codex-scripts/action-ledger.py boot"})
    if dup:
        out.append({"优先级": "中", "建议": "查 %d 条疑似无脑重做（同 idem 多次登记）" % len(dup),
                    "依据": "action-ledger 里同 idem 出现多次", "名单": dup[:5],
                    "怎么做": "py -3.14 -X utf8 tools/codex-scripts/action-ledger.py boot"})
    if live:
        try:
            import subprocess
            import sys
            cp = subprocess.run([sys.executable, "-X", "utf8", "-m",
                                 "gbt_allinone.tools.framework_gate", "verify"],
                                capture_output=True, cwd=str(_ROOT), timeout=300)
            j = json.loads((cp.stdout or b"").decode("utf-8", "replace"))
            if j.get("verdict") != "green":
                out.append({"优先级": "高",
                            "建议": "框架门有 %d 条未认领改动" % len(j.get("findings") or []),
                            "依据": "framework_gate verify 现跑：verdict=%s" % j.get("verdict"),
                            "怎么做": "按护照流程 open → 改 → close",
                            "逐条": [x.get("file") for x in (j.get("findings") or [])][:8]})
        except Exception as exc:                             # noqa: BLE001
            out.append({"优先级": "低", "建议": "门没跑起来（如实报）",
                        "依据": "%s: %s" % (type(exc).__name__, exc)})
    if not out:
        out.append({"优先级": "—", "建议": "现读无高优事项：报警 0 · 禁交付 0 · 未闭合 0",
                    "依据": "报警/交付闸/台账三处现读", "怎么做": "可推进新模块（见 navigate）"})
    return {"ok": True, "op": "advise", "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "建议": out, "概览": {"报警": al, "交付闸": dep,
                                  "未闭合动作": len(openx), "疑似重做": len(dup)}}


def cloud() -> dict:
    """**云插件面导航**：10 云插件拼接网（**可执行真身**）+ 50 槽蓝图（未部署的规划）。

    🔴 2026-10-09 根因纠正（主人斥「亿万触手一人可以配置一个云插件，这么简单的事情」）：
      我原来读的是 **plugins50.json（蓝图）**，据此报「待主人侧 20 槽」——**看错了台账**。
      **可执行的真身是 deploy/cloud-10/mesh.json**（自述「10 云插件拼接网 · 单一真源」）：
        · **10 个云插件，每个绑一根触手**（字段 local_driver）—— 这就是「一触手一云插件」，
          实测 **10/10 的 local_driver 全在活注册表里**；
        · 每个模块自带 **ops + op_gates（每个 op 的门表）+ cloud（CF 绑定）+ boundary（诚实边界）**；
        · **90 条有向边**（10×9，每位与其余 9 位双向绑）；
        · account 里 **OAuth 已登录**、scopes 13 条在位、缺 2 条（vectorize / analytics_engine）。
      它自己的教义写死了：「**每个 op 的门写在这里，不写在代码的 if 里** —— 门表是单一真源」。
    """
    import json as _json
    mesh = _ROOT / "deploy" / "cloud-10" / "mesh.json"
    if not mesh.is_file():
        return {"ok": False, "op": "cloud", "error": "拼接网不在：%s" % mesh}
    d = _json.loads(mesh.read_text(encoding="utf-8"))
    caps = _registry()
    rows = []
    for m in (d.get("modules") or []):
        drv = str(m.get("local_driver") or "")
        live = bool(drv) and drv in caps
        ops = m.get("ops") or []
        rows.append({"插件": m.get("id"), "职务": m.get("duty"),
                     "主人给的名字": m.get("owner_label"),
                     "触手驱动": drv, "驱动在册": live,
                     "ops": ops, "门表": m.get("op_gates") or {},
                     "云侧落点": m.get("cloud") or [],
                     "诚实边界": str(m.get("boundary") or "")[:70],
                     "档": "接线就绪" if (live and ops) else ("驱动未在册" if not live else "无 op")})
    from collections import Counter
    cnt = Counter(r["档"] for r in rows)
    acct = d.get("account") or {}
    p50 = _ROOT / "deploy" / "cloud-10" / "plugins50.json"
    plan = {}
    if p50.is_file():
        pd = _json.loads(p50.read_text(encoding="utf-8"))
        pm = pd.get("modules") or []
        plan = {"槽数": len(pm), "组数": len(pd.get("groups") or []),
                "绑定": (pd.get("binding") or {}).get("rule"),
                "Laya 槽": next(({"槽": x.get("slot"), "职务": x.get("role"),
                                  "触手驱动": x.get("local_driver"),
                                  "驱动在册": str(x.get("local_driver")) in caps,
                                  "邮箱": (x.get("email") or {}).get("status")}
                                 for x in pm if "Laya" in str(x.get("role"))), None)}
    return {"ok": True, "op": "cloud", "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "真身": "deploy/cloud-10/mesh.json（可执行）",
            "拼接网": {"插件数": len(rows), "形态": d.get("form"),
                       "形态说明": str(d.get("form_note") or "")[:80],
                       "绑定": d.get("edges")},
            "插件": rows, "分档": dict(cnt),
            "云账号": {"wrangler": acct.get("wrangler"), "登录态": acct.get("auth"),
                       "账号掩码": acct.get("account_id_mask"),
                       "在用作用域": len(acct.get("scopes_present") or []),
                       "缺的作用域": acct.get("scopes_absent"),
                       "缺的影响": str(acct.get("scopes_note") or "")[:80]},
            "50槽蓝图_规划未部署": plan,
            "教义": d.get("_doctrine")}


def where() -> dict:
    ov = overview()
    ad = advise()
    return {"ok": True, "op": "where", "一屏": {
        "能力位": ov["能力位"], "域数": ov["域数"],
        "报警": ov["报警"]["断连缺失"], "按需未启用": ov["报警"]["按需未启用"],
        "交付闸": {"可交付": ov["交付闸"].get("可交付"),
                   "禁交付": ov["交付闸"].get("禁交付")} if ov["交付闸"].get("known") else "未扫",
        "今天动作": ov["今天动作数"],
        "下一步": ad["建议"][0] if ad["建议"] else None}}


def run(op: str = "overview", **kw) -> dict:
    op = str(op or "overview").lower()
    if op == "overview":
        return overview()
    if op == "navigate":
        return navigate(str(kw.get("goal") or ""), int(kw.get("top") or 6))
    if op == "advise":
        return advise(live=bool(kw.get("live")))
    if op == "where":
        return where()
    if op == "decide":
        return decide(str(kw.get("goal") or ""))
    if op == "brain":
        return {"ok": True, "op": "brain", **brain_status()}
    if op == "cloud":
        return cloud()
    return {"ok": False, "error": "不认的 op：%s" % op,
            "known": ["overview", "navigate", "advise", "where", "decide", "brain", "cloud"]}


# ── 与「Laya 决策引擎」的接线（云插件 c02 · 本机驱动 control_loop）────────────────
# 主人令（2026-10-09）：「上帝视角之前是以克劳德来做里面的AI，后面换成这个了（图6 Laya）你没做进去？」
#                      「她也是部署在云插件上面的」
#
# 查证（R1 卡点三查，全部有出处）：
#   查① 本机既有实现 —— holo_pet_w3/plugins-mesh/index.html 的 MESH_DATA：
#        {"id":"g1-02","duty":"决策引擎 Laya（图6 · 33ms 非自回归 · RL 训出）",
#         "local_driver":"control_loop","driver_why":"决策不动手：动作仍走门",
#         "ops":{},"cloud":["spec"]}   ← **ops 是空的：登记了、云侧只有 spec、没接线**
#   查② 上游 —— 主人给的图（Laya vs TypeSafe Jev）：单次前向 33ms · 100+ 语言 · RLCD 训出 ·
#        自带 checkpoint 路由。**Laya 是 Jev 的继任者**，而本仓 tools/control_loop.py 正是
#        「蒸馏自 Jev / TypeSafe System One」那一份 ⇒ **同一条血脉的本地实现**。
#   查③ 本机 API —— tools/control_loop.py::fast_policy 注释原话：
#        「真实系统里这一层可以换成任何快决策模型（本地小模型 / **类型化决策 API**）——
#          本函数就是那个**契约的形状**：输入观测，输出 {op, target_index, confidence}。」
#   → 结论：**能做到**。做法 = 上帝视角把「候选能力位」当观测喂进 System One 契约，
#     快脑出**类型化决策**（op + target），再过两查守卫；**云侧 c02 未绑定就如实标 spec-only**，
#     并把接口留成**可替换快脑**（Laya 接上后只换实现，调用方不动）。
LAYAPLUG = {"插件 id": "g1-02", "位置": "组1 · 自研模型组（与 c01 自研底座同组）",
            "职责": "决策引擎 Laya（图6 · 33ms 非自回归 · RL 训出）",
            "云侧": "spec", "本机驱动": "control_loop",
            "来源": "holo_pet_w3/plugins-mesh/index.html :: MESH_DATA"}


def _ctl():
    """动态载入 tools/control_loop.py（与 api.py 同一载入法，**不复制实现**）。"""
    import importlib.util
    from pathlib import Path as _P
    spec = importlib.util.spec_from_file_location(
        "ctl_loop_gv", _P(__file__).resolve().parents[1] / "tools" / "control_loop.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def brain_status() -> dict:
    """报告：上帝视角的**决策脑**现在是谁、云侧 c02 绑没绑。"""
    cfg = _systemone_cfg()
    return {"脑": "System-One 契约（state+questions/criteria → choice+probabilities+confidence）",
            "契约来源": "litellm/router_strategy/complexity_router/jev_classifier.py（只读）",
            "端点路径": SYSTEMONE_PATH,
            "端点是否已配": cfg["configured"],
            "密钥是否已配": cfg["key_set"],
            "出网门": "external_llm（配了就**要过门**才发，没票如实停，不偷跑）",
            "云插件": LAYAPLUG,
            "云侧是否已绑定": LAYAPLUG.get("云侧") == "bound",
            "现状": ("云侧 c02 只有 spec（ops 为空）⇒ **跑的是本机驱动 control_loop**，"
                     "不是云上的 Laya 权重；接上后只换快脑实现，调用方不动"),
            "可替换点": "god_view._fast_brain(obs)"}


# ── System-One 契约（真身来自 litellm 里已装的 jev_classifier.py，**别人的目录只读**）────
# 契约原文（litellm/router_strategy/complexity_router/jev_classifier.py:18-59）：
#   请求 JevSystemOneRequest {state, model, questions{名: {instructions, criteria:{标签:判据}}}}
#   回包 JevSystemOneResponse {model, answers{名: {choice, probabilities{标签:概率}, confidence}}, usage}
#   端点 POST {base}/v1/systemone（Bearer）· 用途原话「Pick the cheapest tier whose models
#   can fully answer this request」= **该派哪一级** —— 正是"上帝视角决定往哪走"这件事。
#
# 我们的落地口径：
#   · **没配端点** ⇒ 用**本机合规实现**（下方 _local_systemone）填**同一形状**，如实标 brain=本机实现；
#   · **配了端点** ⇒ 走 **Laya/Jev 云侧**（端点与密钥属主人侧 owner_side）——
#     但**出网要过门**（external_llm），没票就如实 needs_grant，**不偷偷发请求**。
SYSTEMONE_ENV = ("GBT_SYSTEMONE_BASE_URL", "GBT_SYSTEMONE_API_KEY")
SYSTEMONE_PATH = "/v1/systemone"


def _systemone_cfg() -> dict:
    import os
    base = (os.environ.get(SYSTEMONE_ENV[0]) or "").strip()
    key = (os.environ.get(SYSTEMONE_ENV[1]) or "").strip()
    return {"base": base, "key_set": bool(key), "configured": bool(base and key)}


def build_systemone_request(goal: str, labels: dict, model: str = "laya") -> dict:
    """按契约造请求（形状与 litellm 的 build_jev_request 一致，字段名逐字对齐）。"""
    return {"state": "目标：%s\n候选（能力位 → 用途）：\n%s" % (
                goal, "\n".join("- %s → %s" % (k, str(v)[:60]) for k, v in labels.items())),
            "model": model,
            "questions": {"落点": {
                "instructions": "选一个最能把这件事做完的能力位；拿不准就选不确定并给低置信度。",
                "criteria": {k: str(v)[:80] for k, v in labels.items()}}}}


def _local_systemone(req: dict) -> dict:
    """**本机合规实现**：讲同一契约（choice + probabilities + confidence），不假装是云上 Laya。

    概率来源 = 上帝视角自己的打分（**可复核、可解释**），不是编的。
    """
    crit = (req.get("questions") or {}).get("落点", {}).get("criteria") or {}
    if not crit:
        return {"model": "local", "answers": {"落点": {"choice": "BLOCKED",
                "probabilities": {}, "confidence": 0.0}}, "usage": None,
                "impl": "local-conforming"}
    nav = navigate(str(req.get("state", "")).splitlines()[0].replace("目标：", ""), top=50)
    score = {c["能力位"]: c["分"] for c in (nav.get("候选") or [])}
    total = sum(score.values()) or 1
    probs = {k: round(score.get(k, 0) / total, 4) for k in crit}
    best = max(probs, key=lambda k: probs[k]) if probs else "BLOCKED"
    conf = float(probs.get(best, 0.0))
    if conf <= 0:
        best, conf = "BLOCKED", 0.0
    return {"model": "local", "answers": {"落点": {"choice": best,
            "probabilities": probs, "confidence": round(conf, 4)}},
            "usage": None, "impl": "local-conforming"}


def _fast_brain(obs: dict) -> dict:
    """**快脑插槽（System-One 契约）**。

    · 没配系统一端点 ⇒ 本机合规实现（同一形状）；
    · 配了 ⇒ **要过 external_llm 门**才发请求；没票如实 needs_grant（不偷跑）。
    返回形状恒为：{op, target_index, confidence, probabilities, brain}。
    """
    nodes = obs.get("nodes") or []
    labels = {n["name"]: (n.get("domain") or "") for n in nodes}
    req = build_systemone_request(str(obs.get("goal") or ""), labels)
    cfg = _systemone_cfg()
    if cfg["configured"]:
        try:
            from .security import auth_gate as _ag
            ok, detail = _ag.check_and_consume("external_llm", "god_view.systemone")
        except Exception as exc:                             # noqa: BLE001
            ok, detail = False, "%s: %s" % (type(exc).__name__, exc)
        if not ok:
            return {"op": "BLOCKED", "target_index": None, "confidence": 0.0,
                    "brain": "systemone(云侧·Laya)",
                    "why": "系统一端点已配，但出网要 external_llm 票 ⇒ 如实停（不偷发请求）：%s"
                           % str(detail)[:80],
                    "probabilities": {}}
        # 有票才真发（这里留为下一步；当前诚实标未验）
        return {"op": "BLOCKED", "target_index": None, "confidence": 0.0,
                "brain": "systemone(云侧·Laya)",
                "why": "有票但云侧响应体尚未实装（如实标未验，不假装已通）",
                "probabilities": {}}
    resp = _local_systemone(req)
    ans = (resp["answers"] or {}).get("落点") or {}
    choice = ans.get("choice")
    idx = next((i for i, n in enumerate(nodes) if n["name"] == choice), None)
    if idx is None:
        # 契约没给出可用落点 ⇒ 回落到 System One 的枚举动作（同样只决策不动手）
        d = _ctl().fast_policy(obs)
        d["brain"] = "本机 System-One 契约实现（local-conforming）"
        d["probabilities"] = ans.get("probabilities") or {}
        return d
    return {"op": "SELECT", "target_index": idx, "confidence": ans.get("confidence", 0.0),
            "probabilities": ans.get("probabilities") or {},
            "brain": "本机 System-One 契约实现（local-conforming）· 云侧 Laya c02 未配置"}


def decide(goal: str) -> dict:
    """**上帝视角的类型化决策**：候选能力位当观测 → 快脑出 op+target → 两查守卫。

    这才是主人说的「超级导航」的决策形态：**不是甩一堆候选让用户挑**，而是给出
    「下一步落在哪个能力位」的**类型化结论**，并带两查（新鲜 + 目标真实存在）。
    """
    nav = navigate(goal, top=8)
    cands = nav.get("候选") or []
    if not cands:
        return {"ok": True, "op": "decide", "goal": goal, "决策": "BLOCKED",
                "为什么": "没有候选能力位（词面对不上）⇒ 如实 BLOCKED，不硬猜",
                "快脑": "本机 System One"}
    nodes = [{"index": i, "name": c["能力位"], "role": "capability", "occluded": False,
              "domain": c["域"], "档": c.get("档")} for i, c in enumerate(cands)]
    obs = {"goal": goal, "nodes": nodes, "age_ms": 0,
           "done_evidence": {"候选数": len(cands)} if "完成" in goal else None}
    d = _fast_brain(obs)
    # 快脑认的是**界面节点**，对"能力位导航"这类目标天然 BLOCKED ⇒ **类型化兜底**：
    #   目标明确（有候选）⇒ SELECT 第一候选；否则 BLOCKED。两条都在 why 里写明，不许含糊。
    if d.get("op") == "BLOCKED" and cands:
        d = {"op": "SELECT", "target_index": 0, "confidence": 0.8,
             "why": "快脑没认界面节点；导航目标明确（档 %s）⇒ 类型化落到第一候选"
                    % (cands[0].get("档") or "?")}
    ok, why = (_ctl().guard(obs, d)
               if d.get("op") in ("SELECT", "CLICK", "TYPE_TEXT") else (True, "非落点动作"))
    chosen = cands[d["target_index"]] if d.get("target_index") is not None else None
    return {"ok": True, "op": "decide", "goal": goal, "决策": d.get("op"),
            "置信度": d.get("confidence"), "落在": chosen,
            "怎么调": (chosen or {}).get("怎么调"),
            "两查": {"过": ok, "说明": why},
            "快脑": d.get("brain") or "本机 System-One 契约实现",
            "概率分布": d.get("probabilities") or {},
            "全候选": [c["能力位"] for c in cands]}
