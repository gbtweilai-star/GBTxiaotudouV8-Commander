# gbt-capability: local_brain
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""本地原生脑（local_brain）· R-H227 只读骨架。

**「原生大脑」≠「模型就是大脑」**：
  大脑（主机）= 纪律 + 门禁 + 审计 + 身份内核 + 决策权（**不可换**）
  模型（本地）= **语言皮层** + 意图解析 + 工具选择 + 结果解释（**可换**）

五条红线（做成机械闸）：
  ① 模型不许直接执行系统命令　② 不可逆动作必须二次确认　③ 参数缺失不许猜
  ④ 每次执行必须写 trace_store　⑤ 身份内核不许被模型改写

本骨架只读：**不加载模型、不起服务、不出网、不落盘**。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

CAP_KIND = "local_brain"
DOMAIN = "mind"
CAP_TYPE = "internal"          # 内调型：它是皮层，服从主机

# 五层链路（**模型只做第 ② 和第 ⑧ 步**）
BRAIN_LAYERS = (
    {"n": 1, "layer": "用户说话", "ours": True, "by_model": False},
    {"n": 2, "layer": "本地 7B-8B 模型（意图解析 + 工具选择 + 参数填充）→ JSON",
     "ours": False, "by_model": True},
    {"n": 3, "layer": "能力注册表（工具是否存在 / 参数是否合法）",
     "ours": True, "by_model": False},
    {"n": 4, "layer": "门禁（可逆放行 / 不可逆二次确认）",
     "ours": True, "by_model": False},
    {"n": 5, "layer": "原生触手（搜索/打开应用/读写文件/浏览器/终端）",
     "ours": True, "by_model": False},
    {"n": 6, "layer": "验证器（结果对不对？失败上报）", "ours": True, "by_model": False},
    {"n": 7, "layer": "审计（写 trace_store）", "ours": True, "by_model": False},
    {"n": 8, "layer": "本地模型（把结果解释给用户）", "ours": False, "by_model": True},
)
MODEL_STEPS = tuple(x["n"] for x in BRAIN_LAYERS if x["by_model"])

# 硬件门槛（官方口径）
HARDWARE_TIERS = (
    {"size": "7B-8B", "q4_vram": "4.5-5.5 GB", "rec": "8 GB 显存起步",
     "as_cortex": True},
    {"size": "14B", "q4_vram": "8-10 GB", "rec": "12-16 GB 显存",
     "as_cortex": True},
    {"size": "32B", "q4_vram": "18-20 GB", "rec": "24 GB 显存",
     "as_cortex": True},
)
HARDWARE_RECOMMEND = {"vram_gb": 12, "ram_gb": 32,
                      "quant": "Q4/Q5", "size": "7B-8B",
                      "note": "同时要给浏览器 / 触手 / 工具进程留空间"}

MODEL_CANDIDATES = (
    {"name": "Qwen2.5-7B-Instruct", "pro": "中文强，工具调用好",
     "use": "通用任务 + 中文交互", "pick": True},
    {"name": "Qwen2.5-Coder-7B", "pro": "代码强", "use": "编程 + 自动化脚本",
     "pick": False},
    {"name": "Llama-3.1-8B-Instruct", "pro": "英文强，生态成熟",
     "use": "通用任务", "pick": False},
    {"name": "DeepSeek-R1-Distill-Qwen-7B", "pro": "推理强", "use": "复杂决策",
     "pick": False},
)

# ── R-H228 · 多模型自动切换（主人新指令：都装 + 自动切 + 闲时不占内存）──
# 口径更新：此前「只保留一个」⇒ 改为「**多模型共存磁盘 · 按需加载 · 空闲卸载**」
MULTI_MODEL_POLICY = {
    "install": "**这些候选都装上**（共存于**磁盘**）",
    "disk_vs_memory": "**磁盘占用 ≠ 内存占用**：模型躺在磁盘上**不占显存/内存**，"
                      "只有**被加载**时才占",
    "auto_switch": "按任务类型**自动切换**（切换 = 卸载旧的 → 加载新的）",
    "idle": "**空闲必须卸载**（不许无限期驻留）—— 这就是「没使用时不占内存」的实现",
    "residency": "**同一时刻只驻留一个**（显存门槛 8-12GB，两个 7B 会爆）",
}

# 按任务类型路由（自动切换的判据）
MODEL_ROUTING = (
    {"task": "中文交互 / 通用任务", "model": "Qwen2.5-7B-Instruct",
     "kw": ("中文", "聊天", "通用", "问答", "写作")},
    # ⚠️ 判据要卡在真问题上（实测踩过）：只写"编程/自动化脚本"匹配不到
    #    「帮我写个 Python 脚本」⇒ 把真实说法都列进 kw
    {"task": "编程 / 自动化脚本", "model": "Qwen2.5-Coder-7B",
     "kw": ("编程", "代码", "脚本", "python", "自动化", "重构", "debug", "调试")},
    {"task": "英文 / 生态工具", "model": "Llama-3.1-8B-Instruct",
     "kw": ("英文", "english", "翻译", "生态")},
    {"task": "**复杂决策 / 推理**", "model": "DeepSeek-R1-Distill-Qwen-7B",
     "kw": ("复杂", "决策", "推理", "权衡", "分析", "证明", "规划")},
)

# 空闲卸载：keep_alive 必须设（秒）；0 = 用后立刻卸
DEFAULT_KEEP_ALIVE_S = 300

# 五条红线（写死）
RED_LINES = (
    "模型不许直接执行系统命令（**只能选注册表里的工具**）",
    "不可逆动作必须二次确认（删文件 / 发消息 / 部署 / 支付**永远卡**）",
    "参数缺失不许猜（缺参 = `missing_params`，拒执行）",
    "每次执行必须写 `trace_store`（**无痕即未发生**）",
    "身份内核不许被模型改写（**输出永远是「我是 GBT小土豆」**）",
)

# 不可逆动作（**永远卡**）
IRREVERSIBLE = ("删除", "删文件", "发送", "发消息", "发布", "部署", "支付", "转账",
                "格式化", "卸载", "kill", "drop", "truncate", "delete", "deploy",
                "publish", "pay")

# 允许的通道：**只能在注册表里选工具**（不许模型自己造命令）
_DIRECT_EXEC = (
    r"^\s*(cmd|powershell|pwsh|bash|sh)\s",
    r"subprocess\.(run|Popen|call|check_output)",
    r"os\.system\(",
    r"os\.popen\(",
    r"eval\(", r"exec\(",
)

# 身份自称：**输出永远是「我是 GBT小土豆」**
IDENTITY_SELF = ("我是 GBT小土豆", "GBT小土豆", "小土豆")
_IDENTITY_DRIFT = (
    r"我是\s*(GPT|Claude|Gemini|Qwen|Llama|DeepSeek|Copilot|通义|文心)",
    r"as an? (AI|assistant) (language )?model",
    r"I am (GPT|Claude|Gemini|Qwen|Llama|DeepSeek)",
)


def check_no_direct_exec(plan: Any = None) -> dict:
    """红线①：**模型不许直接执行系统命令** —— 只能在能力注册表里选工具。"""
    p = plan if isinstance(plan, dict) else {"raw": str(plan or "")}
    raw = str(p.get("raw") or p.get("command") or "")
    cap = str(p.get("capability") or p.get("kind") or "").strip()
    if raw:
        for rx in _DIRECT_EXEC:
            if re.search(rx, raw, re.I | re.M):
                return {"ok": False, "denied": True, "rule": "model_direct_exec",
                        "seen": raw.strip()[:100],
                        "why": "模型不许直接执行系统命令 —— "
                               "**只能在能力注册表里选工具**"}
        if not cap:
            return {"ok": False, "denied": True, "rule": "not_a_registered_tool",
                    "why": "没有任何 capability（注册表键）却给了命令 ⇒ 这不是"
                           "「选工具」，是「自己造命令」"}
    if not cap:
        return {"ok": False, "denied": True, "rule": "missing_capability",
                "why": "要先说清走哪个**已登记**的能力位"}
    return {"ok": True, "readonly": True, "capability": cap,
            "note": "走注册表 ⇒ 才谈得上「工具存在、参数合法」"}


def must_confirm_irreversible(plan: Any = None, confirmed: bool = False) -> dict:
    """红线②：**不可逆动作必须二次确认**（永远卡）。"""
    p = plan if isinstance(plan, dict) else {"raw": str(plan or "")}
    blob = " ".join(str(p.get(k) or "") for k in
                    ("raw", "action", "capability", "kind", "text"))
    hit = [w for w in IRREVERSIBLE if w.lower() in blob.lower()]
    if hit:
        if confirmed:
            return {"ok": True, "readonly": True, "irreversible": hit,
                    "note": "人已二次确认 ⇒ 放行（但**留痕**）"}
        return {"ok": False, "denied": True, "rule": "irreversible_needs_confirm",
                "hit": hit,
                "why": "不可逆动作**永远卡**：删 / 发 / 部署 / 支付 —— "
                       "必须由人二次确认，模型不许自己拍板"}
    return {"ok": True, "readonly": True, "irreversible": [],
            "note": "未识别为不可逆 ⇒ 可逆动作放行"}


def must_have_params(params: Optional[Dict] = None,
                     required: Optional[List[str]] = None) -> dict:
    """红线③：**参数缺失不许猜**（缺参 = `missing_params`，拒执行）。"""
    p = dict(params or {})
    req = [str(x) for x in (required or []) if str(x or "").strip()]
    if not req:
        return {"ok": False, "denied": True, "rule": "no_param_contract",
                "why": "没说清这个能力需要哪些参数 ⇒ **不许硬跑**"}
    missing = [k for k in req if not str(p.get(k) or "").strip()]
    if missing:
        return {"ok": False, "denied": True, "rule": "missing_params",
                "missing": missing, "required": req,
                "why": "缺参 ⇒ **拒执行**：不许拿默认值填"
                       "（猜出来的参数等于替人做决定）"}
    return {"ok": True, "readonly": True, "required": req}


def must_trace_call(trace_ref: str = "") -> dict:
    """红线④：**每次执行必须写 `trace_store`**（无痕即未发生）。"""
    ref = str(trace_ref or "").strip()
    if not ref:
        return {"ok": False, "denied": True, "rule": "call_not_traced",
                "why": "**每次执行**都要留痕（调用级）；"
                       "没写 trace 的调用等于没发生"}
    return {"ok": True, "readonly": True, "trace_ref": ref,
            "note": "trace 要能回答：谁批的、走了哪层、结果是什么"}


def check_identity_text(text: str = "") -> dict:
    """红线⑤：**身份内核不许被模型改写**（输出永远是「我是 GBT小土豆」）。"""
    t = str(text or "")
    for rx in _IDENTITY_DRIFT:
        m = re.search(rx, t, re.I)
        if m:
            return {"ok": False, "denied": True, "rule": "identity_rewritten",
                    "seen": m.group(0)[:80],
                    "why": "身份内核不许被模型改写 —— **输出永远是「我是 GBT小土豆」**；"
                           "模型可以换，自称不许换"}
    return {"ok": True, "readonly": True, "self_name": IDENTITY_SELF[0],
            "note": "没发现身份漂移"}


def route_model(task: str = "") -> dict:
    """R-H228 · **按任务类型自动挑模型**（自动切换的判据）。"""
    t = str(task or "").strip()
    if not t:
        return {"ok": False, "denied": True, "rule": "missing_task",
                "routing": [dict(x) for x in MODEL_ROUTING],
                "why": "要按任务类型切 ⇒ 先说清是什么任务"}
    low = t.lower()
    for row in MODEL_ROUTING:
        kw = [str(w) for w in (row.get("kw") or ())]
        if any(w.lower() in low for w in kw):
            return {"ok": True, "readonly": True, "task": t,
                    "model": row["model"], "matched": row["task"],
                    "kw": kw}
    return {"ok": False, "denied": True, "rule": "no_model_for_task",
            "task": t, "routing": [dict(x) for x in MODEL_ROUTING],
            "why": "没有匹配的模型 ⇒ **如实说不匹配**，不许随便挑一个顶上"}


def plan_switch(current: str = "", target: str = "",
                resident: Optional[List] = None) -> dict:
    """R-H228 · **自动切换序列**：卸载旧的 → 加载新的；**同一时刻只驻留一个**。

    为什么要显式排序列：显存门槛只有 8-12 GB，**新旧同时驻留就爆**。
    """
    cur, tgt = str(current or "").strip(), str(target or "").strip()
    res = [str(x) for x in (resident or []) if str(x or "").strip()]
    if not tgt:
        return {"ok": False, "denied": True, "rule": "missing_target_model",
                "why": "要说清切到哪个模型"}
    if cur == tgt and tgt in res:
        return {"ok": True, "readonly": True, "steps": [],
                "note": "目标已在驻留 ⇒ **无需切换**（不要白卸载再加载）"}
    if len(res) > 1:
        return {"ok": False, "denied": True, "rule": "vram_overcommit",
                "resident": res,
                "why": "**同一时刻只许驻留一个**：8-12GB 显存带不动两个 7B —— "
                       "先把别的卸掉再加载"}
    steps = []
    for r in res:
        if r != tgt:
            steps.append({"action": "unload", "model": r})
    if tgt not in res:
        steps.append({"action": "load", "model": tgt,
                      "keep_alive_s": DEFAULT_KEEP_ALIVE_S})
    return {"ok": True, "readonly": True, "target": tgt, "steps": steps,
            "note": "**先卸后载**（不许新旧重叠）；加载时带 keep_alive ⇒ "
                    "空闲到点自动卸 ⇒ **没使用时不占内存**"}


def check_idle_policy(keep_alive_s: Any = None) -> dict:
    """R-H228 · **空闲卸载策略**：`keep_alive` 必须显式设（不许无限驻留）。"""
    if keep_alive_s is None or str(keep_alive_s).strip() == "":
        return {"ok": False, "denied": True, "rule": "idle_policy_missing",
                "default_keep_alive_s": DEFAULT_KEEP_ALIVE_S,
                "why": "**空闲必须卸载**：不设 keep_alive = 模型无限期占着显存，"
                       "那就违背了「没使用时不占内存」"}
    try:
        v = int(keep_alive_s)
    except (TypeError, ValueError):
        return {"ok": False, "denied": True, "rule": "bad_keep_alive",
                "keep_alive_s": str(keep_alive_s),
                "why": "keep_alive 必须是秒数（0 = 用后立刻卸）"}
    if v < 0:
        return {"ok": False, "denied": True, "rule": "bad_keep_alive",
                "keep_alive_s": v, "why": "keep_alive 不许为负"}
    return {"ok": True, "readonly": True, "keep_alive_s": v,
            "note": "空闲 %s 秒后自动卸载" % ("立刻" if v == 0 else v)}


def run(op="status", **params) -> dict:
    """能力入口（只读骨架）：status / layers / redlines / hardware / models /
    check_exec / check_irreversible / check_params / check_trace / check_identity。
    不加载模型、不起服务、不出网、不落盘。"""
    op = str(op or "status")
    if op == "status":
        return {"ok": True, "readonly": True, "kind": CAP_KIND, "domain": DOMAIN,
                "type": CAP_TYPE,
                "positioning": "本地模型 = **原生脑皮层**（可换）；"
                               "主机 = **纪律层**（门禁/审计/身份内核，不可换）",
                "model_steps": list(MODEL_STEPS),
                "layers": len(BRAIN_LAYERS),
                "note": "**模型只做第 ② 和第 ⑧ 步**；中间全走原生能力栈"}
    if op == "layers":
        return {"ok": True, "readonly": True,
                "layers": [dict(x) for x in BRAIN_LAYERS],
                "model_steps": list(MODEL_STEPS),
                "note": "模型只做 %s 步" % ("/".join(str(n) for n in MODEL_STEPS))}
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES),
                "irreversible": list(IRREVERSIBLE[:8])}
    if op == "hardware":
        return {"ok": True, "readonly": True,
                "tiers": [dict(x) for x in HARDWARE_TIERS],
                "recommend": dict(HARDWARE_RECOMMEND)}
    if op == "models":
        return {"ok": True, "readonly": True,
                "candidates": [dict(x) for x in MODEL_CANDIDATES]}
    if op == "check_exec":
        return check_no_direct_exec(params)
    if op == "check_irreversible":
        return must_confirm_irreversible(params, bool(params.get("confirmed")))
    if op == "check_params":
        return must_have_params(params.get("params"), params.get("required"))
    if op == "check_trace":
        return must_trace_call(params.get("trace_ref") or "")
    if op == "check_identity":
        return check_identity_text(params.get("text") or "")
    # ── R-H228 · 多模型自动切换 ──
    if op == "multi_model":
        return {"ok": True, "readonly": True, **MULTI_MODEL_POLICY,
                "routing": [dict(x) for x in MODEL_ROUTING],
                "default_keep_alive_s": DEFAULT_KEEP_ALIVE_S,
                "supersedes": "此前「只保留一个 / 清理其他模型」的口径**已由本条更新**"}
    if op == "route":
        return route_model(params.get("task") or "")
    if op == "plan_switch":
        return plan_switch(params.get("current") or "",
                           params.get("target") or "",
                           params.get("resident"))
    if op == "check_idle":
        return check_idle_policy(params.get("keep_alive_s"))
    raise ValueError("未知 op %r（可用：status/layers/redlines/hardware/models/"
                     "check_exec/check_irreversible/check_params/check_trace/"
                     "check_identity/multi_model/route/plan_switch/"
                     "check_idle）" % (op,))


HONEST_BOUNDARY = (
    "本地脑只保证『模型只在注册表里选工具、不可逆必卡、缺参必拒、每次留痕、"
    "身份自称不许换』。它**不保证**：本机能跑得动 8B（**显存读数未取到**）、"
    "模型服务已经起来（**实测未运行**）、以及『回答质量更好』—— "
    "本地脑比裸模型强在**结构与可靠**，不在聪明；好不好只能由人判。"
)
