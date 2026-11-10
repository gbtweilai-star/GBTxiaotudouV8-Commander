# -*- coding: utf-8 -*-
"""指挥官派发车道：把「指挥官说的命令」真的交给能力位执行。

病根（2026-11-07 主人指出的原话）：「她是指挥官大模型，指挥触手干活为什么还是这样」。
此前 `_chat` 的链路是：

    算子闸门命中 → 只把候选写进 prompt → 免费车道模型说一段「我会去扫描」

模型没有执行权，能力位也没有被调用，于是用户只看到一句空话。本模块补的是中间那一跳：
**命中安全命令目录 ⇒ 走 `api.run_task` 真执行 ⇒ 把真实回执交回对话。**

边界：

* 只放**人工策展的安全命令**，不拿 427 个能力位做无差别自动执行；
* 执行仍走唯一门 `api.run_task`，授权、三态、审计一个字不改；
* 命中但没执行（缺票 / 缺依赖 / 真失败）也如实回执，不退回模型编；
* 本模块不注册新能力位，只做 `_chat` 的派发层 —— 能力位数量与注册表不变。
"""
from __future__ import annotations

import json
import re
import time

from .. import api


# 安全命令目录：cap → 触发词 / 默认 op / 人话标签。
# 只收已经人工核过是只读或低风险的能力位；危险位（写盘、发消息、资金、执行进程）
# 不在此表，仍由 capability_router / 授权门按原路处理。
COMMANDS = {
    "alerts": {
        "label": "红黄警报·近期异常摘要",
        "op": "recent",
        "phrases": (
            "红黄警报", "红黄告警", "红黄", "警报", "告警", "报警",
            "哪里红了", "哪里黄了", "查告警", "看看告警",
            "最近异常", "异常摘要",
        ),
    },
    "signature_guard": {
        "label": "开发者署名完整性",
        "op": "",
        "params": {"scope": "all"},
        "phrases": (
            "署名", "开发者署名", "署名完整性", "检查署名",
            "谁没署名", "缺署名", "署名扫描", "署名检查",
        ),
    },
    "inventory": {
        "label": "全息盘点·归属四分类",
        "op": "",
        "phrases": (
            "异物", "有没有异物", "全息盘点", "盘点", "盘点一下",
            "游离物", "归属分类", "家根盘点", "盘点家根",
        ),
    },
    "legacy_guard": {
        "label": "旧物守卫·逐条明细",
        "op": "scan",
        "phrases": (
            "旧物", "查旧物", "旧代码", "旧面板", "旧副本",
            "重复文档", "备份文件", "清理旧物", "旧物守卫",
        ),
    },
    "page_scan": {
        "label": "按页面绑定全量扫描",
        "op": "scan",
        "phrases": (
            "全量扫描", "全量扫描一遍", "全量扫一遍", "全扫一遍",
            "扫描一遍", "逐页扫描", "扫描页面", "扫描所有页面",
            "检查页面连接", "检查页面是否接好", "检查哪些没接好",
            "看看哪些没接好", "看看还有哪些没接好", "哪些地方没接好",
            "哪些没接好", "哪里没接好", "页面巡检", "页面连接检查",
            "全量检查", "按页扫描", "按绑定逐页并发扫",
        ),
    },
    "selfscan": {
        "label": "系统五维自检",
        "op": "",
        "phrases": (
            "体检一下系统", "系统体检", "系统自检", "框架健康",
            "查毛病", "哪里有问题", "有没有问题", "自检",
        ),
    },
    "brain_health": {
        "label": "大脑执行层健康检查",
        "op": "",
        "phrases": ("大脑健康", "五维健康", "大脑执行层健康", "执行层健康"),
    },
    "caps_called_audit": {
        "label": "能力位调用点审计",
        "op": "",
        "phrases": (
            "能力调用审计", "调用点审计", "零调用点", "孤儿能力",
            "哪些能力没人调用", "能力没人调用",
        ),
    },
    "coverage_auditor": {
        "label": "触手覆盖审计",
        "op": "",
        "phrases": ("覆盖审计", "触手覆盖审计", "覆盖率", "八短板", "死角"),
    },
    "trunk_cover": {
        "label": "代码文件触手覆盖扫描",
        "op": "scan",
        "phrases": ("触手覆盖", "代码覆盖", "文件没认领", "哪些文件没认领", "覆盖扫描"),
    },
    "sync_guard": {
        "label": "双仓同步巡检",
        "op": "verify",
        "phrases": ("双仓同步", "双仓巡检", "交付树对账", "同步巡检"),
    },
    "cap_self": {
        "label": "能力位清单",
        "op": "list",
        "phrases": ("我有什么能力", "能力清单", "能力总览"),
    },
    "tentacle_status": {
        "label": "触手自诊断",
        "op": "",
        "phrases": ("触手状态", "触手自诊断", "触手诊断"),
    },
}

# 命令判定：有动作词才算「让她动手」，纯提问仍交给对话模型。
_ACTION_WORDS = (
    "扫描", "扫一遍", "扫一下", "巡检", "检查", "体检", "自检",
    "跑一遍", "执行", "运行", "查一下", "查查", "看看", "来一次",
    "追踪", "排查", "根因", "修复", "优化", "复盘",
)
_QUESTION_WORDS = (
    "是什么", "怎么用", "怎么调", "为什么", "介绍", "说明",
    "文档", "帮助", "能不能", "可以吗", "是不是",
)

# 纯查询类：句子本身就是「看状态」，不额外要求动作词（否则「红黄警报」四个字被拦）。
# 这四位都是只读守卫，命中策展词即可派发；提问词（是什么/为什么/怎么用）仍会拦。
_PURE_QUERY_CAPS = {"alerts", "signature_guard", "inventory", "legacy_guard"}


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def _is_command(text: str) -> bool:
    t = _compact(text)
    if not t:
        return False
    if any(w in t for w in _QUESTION_WORDS):
        return False
    return any(w in t for w in _ACTION_WORDS)


def _is_question(text: str) -> bool:
    t = _compact(text)
    return bool(t) and any(w in t for w in _QUESTION_WORDS)


def _phrase_hit(cap: str, text: str) -> str:
    t = _compact(text)
    for phrase in COMMANDS.get(cap, {}).get("phrases") or ():
        if phrase and _compact(phrase) in t:
            return phrase
    return ""


def _miss(why: str) -> dict:
    return {"ok": True, "hit": False, "why": str(why)[:240],
            "cap": "", "op": "", "params": {}, "label": ""}


def resolve(text: str, gate_result: dict | None = None) -> dict:
    """把一句人话解析成「可安全派发的一条命令」。

    `gate_result` 允许调用方把 `_chat` 已经算过的算子闸门传进来，避免同一句话算两遍。
    命中条件三条同时成立：能力位闸门 hit / top-1 在安全命令目录 / 句子里有命令动作词。
    """
    raw = str(text or "").strip()
    if not raw:
        return _miss("空指令")
    g = gate_result if isinstance(gate_result, dict) else {}
    if not g:
        try:
            from .. import operator_index as OI
            g = OI.gate(raw)
        except Exception as exc:  # noqa: BLE001
            return _miss("算子闸门不可用：%s" % type(exc).__name__)
    if not g.get("hit"):
        return _miss("算子闸门未命中：%s" % (g.get("why") or "无候选"))
    top = (g.get("top") or [{}])[0] or {}
    cap = str(top.get("cap") or "")
    if cap not in COMMANDS:
        return _miss("命中 %s，但不在安全命令目录" % (cap or "?"))
    if _is_question(raw):
        return _miss("问句不派发（交给对话模型说明，别把『是什么』当命令）")
    if cap not in _PURE_QUERY_CAPS and not _is_command(raw):
        return _miss("命中 %s，但这句不像命令（缺动作词）" % cap)
    phrase = _phrase_hit(cap, raw)
    if not phrase:
        return _miss("命中 %s，但没有命令触发词" % cap)
    spec = COMMANDS[cap]
    op = str(spec.get("op") or "")
    params = dict(spec.get("params") or {})
    if op:
        params["op"] = op
    return {
        "ok": True, "hit": True,
        "cap": cap, "op": op, "params": params,
        "label": str(spec.get("label") or cap),
        "phrase": phrase,
        "why": "算子闸门命中 %s（%s），命令词「%s」" % (
            cap, g.get("why") or "稳妥命中", phrase),
        "gate": {"score": top.get("score"), "margin": g.get("margin"),
                 "source": top.get("source"), "why": g.get("why")},
    }


def _unwrap(env: dict) -> dict:
    body = env.get("result") if isinstance(env, dict) else {}
    # `api.run_task` 的信封可能套两层（normalize 一层、能力本体一层）。
    # 只在「像是在套信封」时往下钻，避免把业务字段 result 误当外层。
    for _ in range(2):
        if not isinstance(body, dict) or not isinstance(body.get("result"), dict):
            break
        if ("status" in body or "kind" in body
                or set(body.keys()) <= {"ok", "result", "error", "status", "kind"}):
            body = body["result"]
        else:
            break
    return body if isinstance(body, dict) else {}


def execute(decision: dict) -> dict:
    """真执行一条已解析的安全命令，回执保留实测耗时与失败三态。"""
    cap = str((decision or {}).get("cap") or "")
    params = dict((decision or {}).get("params") or {})
    t0 = time.perf_counter()
    try:
        env = api.run_task(cap, params, safe=True)
    except Exception as exc:  # noqa: BLE001
        ms = (time.perf_counter() - t0) * 1000
        return {"ok": False, "cap": cap, "params": params, "ms": round(ms, 1),
                "env": {"ok": False, "status": "failed",
                        "error": "%s: %s" % (type(exc).__name__, str(exc)[:200])},
                "body": {}}
    ms = (time.perf_counter() - t0) * 1000
    body = _unwrap(env)
    ok = bool(env.get("ok"))
    if body.get("ok") is False:
        ok = False
    return {"ok": ok, "cap": cap, "params": params, "ms": round(ms, 1),
            "env": env, "body": body}


def _block_state(env: dict, body: dict) -> tuple[str, str]:
    scopes = list(env.get("missing_scopes") or body.get("missing_scopes") or [])
    missing = list(body.get("missing") or env.get("missing") or [])
    status = str(env.get("status") or "")
    if scopes or status == "denied" or body.get("denied") is True:
        return "denied", "缺授权：%s" % (" / ".join(map(str, scopes)) or "（未点名作用域）")
    if missing or status == "needs_dependency":
        return "needs_dependency", "缺依赖：%s（补上再试，不是授权问题）" % (
            " / ".join(map(str, missing)) or "未点名")
    if status == "needs_input" or body.get("needs_input"):
        return "needs_input", "缺参数：%s" % (
            body.get("reason") or env.get("reason") or "请补充参数")
    why = (body.get("why") or body.get("error") or env.get("reason")
           or env.get("error") or status or "原因未报")
    return "failed", "原因：%s" % str(why)[:240]


def _page_scan_text(body: dict, ms: float) -> str:
    lines = ["⚡ **指挥官派发** · `page_scan/scan` · 已真执行（本地派发，未经对话模型生成）"]
    def add(label, key):
        if body.get(key) is not None:
            lines.append("· %s：%s" % (label, body.get(key)))
    add("页数", "页数")
    add("绑好 / 未绑好", "绑好")
    if body.get("未绑好") is not None:
        lines.append("· 未绑好：%s" % body.get("未绑好"))
    for key in ("落点不在盘的页", "无绑定能力位的页", "不在册的声明", "自引用已排除"):
        val = body.get(key)
        if val not in (None, "", "无 ✓"):
            lines.append("· %s：%s" % (key, val))
    if body.get("唯一能力位") is not None:
        lines.append("· 能力位：唯一 %s / 实探 %s" % (
            body.get("唯一能力位"), body.get("实探能力位")))
    lines.append("· 三色：绿 %s · 黄 %s · 红 %s" % (
        body.get("绿"), body.get("黄"), body.get("红")))
    reds = body.get("红名单") or []
    if reds:
        lines.append("· 红名单（契约满足仍失败）：")
        for row in reds[:12]:
            if isinstance(row, dict):
                lines.append("  - %s：%s" % (row.get("cap"), str(row.get("why") or "")[:120]))
            else:
                lines.append("  - %s" % str(row)[:120])
        if len(reds) > 12:
            lines.append("  - …另有 %d 项" % (len(reds) - 12))
    else:
        lines.append("· 红名单：无（零真故障）")
    yellows = body.get("黄名单") or []
    if yellows:
        lines.append("· 黄名单（契约/授权/依赖，不是故障）：")
        for row in yellows[:10]:
            if isinstance(row, dict):
                lines.append("  - %s：%s" % (row.get("cap"), str(row.get("why") or "")[:100]))
            else:
                lines.append("  - %s" % str(row)[:100])
        if len(yellows) > 10:
            lines.append("  - …另有 %d 项" % (len(yellows) - 10))
    lines.append("· 结论：%s" % (body.get("结论") or "见上"))
    lines.append("· 实测耗时：%.1fms" % ms)
    return "\n".join(lines)


def _generic_text(decision: dict, body: dict, ms: float) -> str:
    cap = str(decision.get("cap") or "")
    op = str(decision.get("op") or "(默认)")
    lines = ["⚡ **指挥官派发** · `%s/%s` · 已真执行（本地派发，未经对话模型生成）"
             % (cap, op)]
    txt = body.get("text")
    if isinstance(txt, str) and txt.strip():
        lines.append(txt.strip()[:1600])
    skip = {"ok", "op", "at", "elapsed_ms", "text"}
    shown = 0
    for key, val in body.items():
        if key in skip or shown >= 12:
            continue
        if isinstance(val, (str, int, float, bool)) or val is None:
            lines.append("· %s：%s" % (key, str(val)[:240]))
            shown += 1
        elif isinstance(val, list):
            lines.append("· %s：%d 项" % (key, len(val)))
            shown += 1
        elif isinstance(val, dict):
            lines.append("· %s：%s" % (key, ", ".join(list(val)[:8]) or "空"))
            shown += 1
    if not shown and not txt:
        lines.append("· 返回字段：%s" % (" / ".join(sorted(body)[:12]) or "空"))
    lines.append("· 实测耗时：%.1fms" % ms)
    return "\n".join(lines)


def _guards_text(cap: str, body: dict, ms: float) -> str:
    """红黄来源四位的专用回执：不只给 verdict，把「为什么」和名单一起摊开。"""
    head = "⚡ **指挥官派发** · `%s` · 已真执行（本地派发，未经对话模型生成）" % cap
    lines = [head]
    if cap == "alerts":
        quiet = bool(body.get("quiet"))
        lines.append("· 结论：%s" % ("quiet（窗口内没有现行故障）" if quiet
                                  else "有信号，需要逐条看"))
        def _v(x):
            return "未报" if x is None else x
        lines.append("· runtime_faults：%s（runtime=要追的病）" % _v(body.get("runtime_faults")))
        lines.append("· anomalies：%s（guard=%s / trace=%s / legacy=%s / recovered=%s）" % (
            _v(body.get("anomalies")),
            _v((body.get("by_signal") or {}).get("guard")),
            _v((body.get("by_signal") or {}).get("trace")),
            _v((body.get("by_signal") or {}).get("legacy")),
            _v((body.get("by_signal") or {}).get("recovered"))))
        lines.append("· needs_a_look：%s（在册能力位异常才为 True）" % body.get("needs_a_look"))
        foot = body.get("unregistered_footprints") or []
        lines.append("· 不在册足迹：%d 个%s" % (
            len(foot), ("（" + " / ".join(map(str, foot[:8])) + "）") if foot else ""))
        events = body.get("by_event") or {}
        if events:
            lines.append("· 事件分布：%s" % " / ".join("%s=%s" % (k, v) for k, v in events.items()))
        off = body.get("top_offenders") or []
        if off:
            lines.append("· 聚合到能力位（前 5）：")
            for row in off[:5]:
                lines.append("  - %s：runtime=%s guard=%s trace=%s legacy=%s" % (
                    row.get("capability"), row.get("runtime"), row.get("guard"),
                    row.get("trace"), row.get("legacy")))
    elif cap == "signature_guard":
        lines.append("· 结论：%s" % body.get("verdict"))
        lines.append("· 检查页数：%s" % body.get("pages_checked"))
        missing = body.get("missing") or []
        lines.append("· 缺署名：%d" % len(missing))
        for x in missing[:12]:
            lines.append("  - %s" % x)
        if len(missing) > 12:
            lines.append("  - …另有 %d 项" % (len(missing) - 12))
        restored = body.get("restored") or []
        if restored:
            lines.append("· 本次补回：%d 页" % len(restored))
    elif cap == "inventory":
        lines.append("· 结论：%s" % body.get("verdict"))
        dv = body.get("dual_view") or {}
        if dv:
            lines.append("· 双视图：%s" % " / ".join("%s=%s" % (k, v) for k, v in dv.items()))
        items = body.get("items") or {}
        foreign = items.get("foreign") or []
        runtime = items.get("runtime") or []
        lines.append("· 异物：%d%s" % (len(foreign), ("（" + " / ".join(map(str, foreign[:12])) + "）") if foreign else ""))
        lines.append("· 运行态：%d（本机可再生，不是异物）%s" % (
            len(runtime), ("（" + " / ".join(map(str, runtime[:10])) + "）") if runtime else ""))
    elif cap == "legacy_guard":
        lines.append("· 结论：%s" % body.get("verdict"))
        cats = body.get("categories") or {}
        for name, val in cats.items():
            if not isinstance(val, dict):
                lines.append("· %s：%s" % (name, val))
                continue
            bits = []
            for k, v in val.items():
                bits.append("%s=%s" % (k, v))
            lines.append("· %s：%s" % (name, " / ".join(bits)))
        paths = body.get("paths") or {}
        for name in ("backup-files",):
            rows = paths.get(name) or []
            if rows:
                lines.append("· 散落备份（%d）：" % len(rows))
                for x in rows[:12]:
                    lines.append("  - %s" % x)
        notes = (body.get("notes") or {}).get("doc-number-collisions") or {}
        if notes.get("groups"):
            lines.append("· 编号撞车：%s 组（只提示，不计入 verdict；不同标题不是重复内容）"
                         % notes.get("groups"))
    lines.append("· 实测耗时：%.1fms" % ms)
    return "\n".join(lines)


def receipt(decision: dict, ex: dict, *, context: str = "",
            elapsed_ms: int | None = None) -> dict:
    """把一次派发执行变成对话可直接渲染的回执。"""
    cap = str((decision or {}).get("cap") or (ex or {}).get("cap") or "")
    op = str((decision or {}).get("op") or "")
    ms = float((ex or {}).get("ms") or 0.0)
    body = (ex or {}).get("body") or {}
    env = (ex or {}).get("env") or {}
    ok = bool((ex or {}).get("ok"))
    if ok:
        if cap == "page_scan" and op == "scan":
            text = _page_scan_text(body, ms)
        elif cap in ("alerts", "signature_guard", "inventory", "legacy_guard"):
            text = _guards_text(cap, body, ms)
        else:
            text = _generic_text(decision, body, ms)
        status = "ok"
    else:
        state, line = _block_state(env, body)
        status = state
        text = "\n".join([
            "⚡ **指挥官派发** · `%s/%s` · 已派发，但没有完成"
            % (cap, op or "(默认)"),
            line,
            "（走 `api.run_task` 唯一门，授权与审计照旧；没有退回模型编造。）",
        ])
    return {
        "ok": ok,
        "status": status,
        "text": text,
        "via": "commander-dispatch:" + cap,
        "capability": {
            "cap": cap,
            "op": op,
            "params": (decision or {}).get("params") or {},
            "phrase": (decision or {}).get("phrase"),
            "gate": (decision or {}).get("gate"),
        },
        "commander": {
            "label": (decision or {}).get("label"),
            "why": (decision or {}).get("why"),
            "hit": True,
        },
        "result": body,
        "ms_run": round(ms, 1),
        "elapsed_ms": int(elapsed_ms if elapsed_ms is not None else ms),
        "context": {"mode": "commander-dispatch", "name": context},
    }


def run(text: str, gate_result: dict | None = None, *, context: str = "") -> dict:
    """一行入口：解析 → 真执行 → 对话回执。未命中时返回 hit=False，调用方照旧走模型。"""
    t0 = time.time()
    decision = resolve(text, gate_result=gate_result)
    if not decision.get("hit"):
        return {"ok": True, "hit": False, "why": decision.get("why"),
                "elapsed_ms": int((time.time() - t0) * 1000)}
    ex = execute(decision)
    out = receipt(decision, ex, context=context,
                  elapsed_ms=int((time.time() - t0) * 1000))
    out["hit"] = True
    return out
