# gbt-capability: auto_switch
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""自动化切换引擎（auto_switch）· R-H229 只读骨架。

**核心不是"更聪明"，是"更不容易误解"** —— 意图错了，一切白费。

五层链路：
  ① 意图分析 → ② 任务分级 → ③ 模型切换 → ④ 原生执行 → ⑤ 验证/审计
意图分析三层：**L1 直接解析 + L2 交叉验证 + L3 置信度判定**。
接线点只有一个：**Intent JSON**。

五条红线（机械闸）：
  ① 置信度低于阈值 → 先问主人　② 模型不许直接执行　③ 每次切换记 `model_used`
  ④ 不可逆动作二次确认　　　　　⑤ 身份内核不许被模型改写

本骨架只读：**不调模型、不起服务、不出网、不落盘**。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

CAP_KIND = "auto_switch"
DOMAIN = "mind"
CAP_TYPE = "internal"

INTENT_THRESHOLD = 0.8          # 意图置信度阈值（低于它 ⇒ 先问主人）

# ── R-H232 · v2.0：五层合并为**四层 + 一回灌**（任务分级与模型切换合并）──
LAYERS_V2 = (
    {"n": 1, "layer": "意图层", "out": "Intent JSON",
     "does": "解析 + 交叉验证 + 置信度 + **歧义分类**"},
    {"n": 2, "layer": "调度层", "out": "Dispatch Plan",
     "does": "**分级 + 选能源 + 定执行链**（原第 ②③ 层合并 —— 分级是为了切换）"},
    {"n": 3, "layer": "执行层", "out": "Raw Result",
     "does": "注册表 + 门禁 + 弹性池 lease + 触手"},
    {"n": 4, "layer": "校验层", "out": "Verified Result",
     "does": "成败 + **意图符合度** + 独立复核 + 审计 + 回传"},
)
FEEDBACK_LOOP = {"from": "校验层", "to": "意图层",
                 "what": "↺ **回灌**（更新偏好模型）",
                 "note": "四层 + 一个回灌循环 = **闭环**"}


class AmbiguityType(Enum):
    ONE_TO_MANY = "一类多解"     # 一句话可能多个意思
    MANY_TO_ONE = "多类一解"     # 不同说法同一个意思
    CROSS = "跨类"               # 涉及多个任务类型


# 歧义三类的澄清模板（每条歧义都有**对应的问法**）
CLARIFY_TEMPLATES = {
    "一类多解": "这句话我读出不止一种意思 ⇒ 请点一个：{options}",
    "多类一解": "你在说的是同一件事的两种说法吗？（{options}）",
    "跨类": "这涉及多个任务类型 ⇒ 先做哪个：{options}",
}

# 难度阈值（**数值化，不再靠形容词**）
DIFFICULTY_THRESHOLD = {"steps": 5}      # 步骤数 ≥5 ⇒ 高难
MAX_TENTACLE_DEPTH = 3                   # 触手拉起深度上限
FEEDBACK_FREQUENCY = 10                  # 每 N 次成功任务更新一次偏好

# ── R-H232 · 19 条短板登记（**逐条可测** · 先取证后登记）──
# covered: "yes"（有机械判据）/ "partial"（部分）/ "no"（待补）
SHORT_BOARDS = (
    {"n": 1, "layer": "意图层", "gap": "双模型一致性阈值未定",
     "fix": "**实测标定**：拿 50 条真实指令跑，看双模型一致率",
     "covered": "partial", "evidence": "有 INTENT_THRESHOLD=0.8，但**未实测标定**"},
    {"n": 2, "layer": "意图层", "gap": "歧义指令没有分类",
     "fix": "歧义分**三类**，各配澄清模板", "covered": "no", "evidence": "R-H232 新补"},
    {"n": 3, "layer": "意图层", "gap": "跨语言意图没覆盖",
     "fix": "加**语言识别 + 归一化**前置", "covered": "no", "evidence": "R-H232 新补"},
    {"n": 4, "layer": "意图层", "gap": "否定/条件句未测",
     "fix": "加**否定检测 + 条件分支**解析", "covered": "no", "evidence": "R-H232 新补"},
    {"n": 5, "layer": "调度层", "gap": "分级维度没有阈值",
     "fix": "每维度明确阈值（如 **步骤数 ≥5 = 高难**）", "covered": "no",
     "evidence": "R-H232 起有 DIFFICULTY_THRESHOLD"},
    {"n": 6, "layer": "调度层", "gap": "能源切换没有降级路径",
     "fix": "加**降级链**：本地→云端→拒执行，每级带 degraded=true", "covered": "partial",
     "evidence": "context_vault 的 budget 有 degraded；**但能量切换无链**"},
    {"n": 7, "layer": "调度层", "gap": "并发上限未定义",
     "fix": "按当前负载**动态设**，写进大脑", "covered": "partial",
     "evidence": "model_key_pool 有按 owner 的并发上限；**不在调度层**"},
    {"n": 8, "layer": "调度层", "gap": "调度决策不可审计",
     "fix": "每次调度写 **dispatch_reason**", "covered": "no", "evidence": "R-H232 新补"},
    {"n": 9, "layer": "执行层", "gap": "执行链路未与弹性池对接",
     "fix": "改成从**弹性池 lease**", "covered": "partial",
     "evidence": "密钥池 lease 有；**触手弹性池待接**"},
    {"n": 10, "layer": "执行层", "gap": "失败没有断点",
     "fix": "加 **execution_trace**，记每步状态", "covered": "partial",
     "evidence": "orchestration_kernel 有挂起/恢复；**非按步断点**"},
    {"n": 11, "layer": "执行层", "gap": "长任务没有中间回报",
     "fix": "加**心跳式中间进度回报**", "covered": "no", "evidence": "R-H232 新补"},
    {"n": 12, "layer": "执行层", "gap": "触手拉起没有深度限制",
     "fix": "大脑设上限（如 **深度 ≤3**）", "covered": "no",
     "evidence": "R-H232 起有 MAX_TENTACLE_DEPTH"},
    {"n": 13, "layer": "校验层", "gap": "结果对账只有成败",
     "fix": "加「**结果是否符合意图**」校验", "covered": "no", "evidence": "R-H232 新补"},
    {"n": 14, "layer": "校验层", "gap": "验证器独立度未保证",
     "fix": "验证器必须**不同 checker**", "covered": "yes",
     "evidence": "**已有**：护照复核要求 checker 标签不同（R-H105）"},
    {"n": 15, "layer": "校验层", "gap": "回灌机制未落地",
     "fix": "加 **feedback_to_intent()** 接口", "covered": "no", "evidence": "R-H232 新补"},
    {"n": 16, "layer": "校验层", "gap": "跨任务学习没沉淀",
     "fix": "加**同类任务模板库**，成功即沉淀", "covered": "no", "evidence": "R-H232 新补"},
    {"n": 17, "layer": "循环层", "gap": "偏好模型更新频率未定",
     "fix": "每 **N 次**成功任务更新一次偏好", "covered": "no",
     "evidence": "取证：相关形状**0 命中**"},
    {"n": 18, "layer": "循环层", "gap": "误判回滚未定义",
     "fix": "加「**回灌可撤销**」接口", "covered": "partial",
     "evidence": "有 rollback 家族；**回灌本身没有撤销**"},
    {"n": 19, "layer": "循环层", "gap": "循环不收敛风险",
     "fix": "加**漂移检测**：连续 N 次回灌后偏离基线 ⇒ 停", "covered": "no",
     "evidence": "R-H232 新补"},
)


class TaskType(Enum):
    CODE = "代码"
    REASONING = "推理"
    CREATIVE = "创意"
    MULTIMODAL = "多模态"
    EXECUTION = "执行"


class Difficulty(Enum):
    SIMPLE = "简单"
    MEDIUM = "中等"
    HARD = "高难"


@dataclass
class TaskProfile:
    type: TaskType = TaskType.EXECUTION
    difficulty: Difficulty = Difficulty.SIMPLE
    reversible: bool = True
    realtime: bool = False


@dataclass
class Intent:
    raw: str = ""
    parsed: Dict = field(default_factory=dict)
    confidence: float = 0.0
    cross_check: Optional[Dict] = None
    needs_clarification: bool = True

    def to_dict(self) -> dict:
        return dict(self.__dict__)


# 五层链路（每层独立可测；上一层输出 = 下一层输入）
PIPELINE = (
    {"n": 1, "layer": "意图分析", "out": "结构化意图（Intent JSON）"},
    {"n": 2, "layer": "任务分级", "out": "任务画像（TaskProfile）"},
    {"n": 3, "layer": "模型切换", "out": "选中的能源 + 参数"},
    {"n": 4, "layer": "原生执行", "out": "结果（走触手）"},
    {"n": 5, "layer": "验证/审计", "out": "最终读数（trace + model_used）"},
)

# 意图分析三层
INTENT_LAYERS = (
    {"layer": "L1", "action": "主模型输出意图 JSON", "guards": "基础理解"},
    {"layer": "L2", "action": "**第二个模型独立复述意图**", "guards": "单模型幻觉"},
    {"layer": "L3", "action": "两次一致→高置信；不一致→问主人", "guards": "**误解**"},
)

# 切换规则（任务画像 → 默认能源 / 备选）
SWITCH_RULES = (
    {"profile": "简单意图 / 实时", "prefer": "本地 7B", "alt": "本地 8B"},
    {"profile": "复杂推理", "prefer": "本地 R1-Distill", "alt": "云端 Agnes"},
    {"profile": "代码", "prefer": "本地 Coder-7B", "alt": "云端"},
    {"profile": "多模态", "prefer": "云端（**本地无视觉**）", "alt": "—"},
    {"profile": "高难度 / 长上下文", "prefer": "云端 Agnes", "alt": "本地兜底"},
)

# 五条红线
RED_LINES = (
    "意图置信度低于阈值 → **先问主人**（不许硬猜）",
    "模型不许直接执行（**只能选注册表里的工具**）",
    "每次切换必须记 `model_used`（无痕即未发生）",
    "不可逆动作二次确认（门禁永远在线）",
    "身份内核不许被模型改写（永远是 **GBT小土豆**）",
)

# 审计四件（每次动作记什么）
AUDIT_MATRIX = (
    {"when": "每次执行", "log": "trace_store"},
    {"when": "**每次切换**", "log": "**model_used**"},
    {"when": "每次拒绝", "log": "reason_code"},
    {"when": "每次降级", "log": "degraded=true"},
)

IRREVERSIBLE = ("删除", "删文件", "发送", "发消息", "发布", "部署", "支付", "转账",
                "格式化", "卸载", "delete", "deploy", "publish", "pay")

_DIRECT_EXEC = (
    r"^\s*(cmd|powershell|pwsh|bash|sh)\s",
    r"subprocess\.(run|Popen|call|check_output)",
    r"os\.system\(", r"os\.popen\(", r"eval\(", r"exec\(",
)

_IDENTITY_DRIFT = (
    r"我是\s*(GPT|Claude|Gemini|Qwen|Llama|DeepSeek|Copilot|通义|文心)",
    r"as an? (AI|assistant) (language )?model",
    r"I am (GPT|Claude|Gemini|Qwen|Llama|DeepSeek)",
)

# 机械解析用的关键词（**骨架期不调模型**：先把结构跑通）
_TYPE_KW = (
    (TaskType.CODE, ("写代码", "脚本", "编程", "python", "重构", "调试", "debug")),
    (TaskType.REASONING, ("推理", "权衡", "证明", "为什么", "分析", "决策")),
    (TaskType.CREATIVE, ("写一篇", "创作", "文案", "故事", "分镜", "起名")),
    (TaskType.MULTIMODAL, ("图片", "视频", "音频", "画", "识别", "看图")),
)
_HARD_KW = ("复杂", "多步", "重构", "部署", "迁移", "架构", "长上下文")
_REALTIME_KW = ("现在", "立刻", "马上", "实时", "查一下")


def gate_intent(confidence: Any = None,
                threshold: float = INTENT_THRESHOLD) -> dict:
    """红线①：**意图置信度低于阈值 → 先问主人**（绝不硬猜）。"""
    if confidence is None or str(confidence).strip() == "":
        return {"ok": False, "denied": True, "rule": "missing_confidence",
                "threshold": threshold,
                "why": "没有置信度就**不许往下走**（未测不按绿）"}
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        return {"ok": False, "denied": True, "rule": "bad_confidence",
                "confidence": str(confidence)}
    if c < float(threshold):
        return {"ok": False, "denied": True, "rule": "low_confidence_ask_owner",
                "confidence": c, "threshold": threshold,
                "why": "**意图置信度低于阈值 ⇒ 停下来问主人**："
                       "意图错了，后面全白费；宁可多问一句，不许硬猜"}
    return {"ok": True, "readonly": True, "confidence": c, "threshold": threshold}


def cross_check(primary: Optional[Dict] = None,
                secondary: Optional[Dict] = None) -> dict:
    """意图 L2+L3：**两个模型独立复述** → 一致高置信，不一致问主人。"""
    if primary is None or secondary is None:
        return {"ok": False, "denied": True, "rule": "cross_check_incomplete",
                "confidence": 0.0, "needs_clarification": True,
                "why": "L2 交叉验证要**两次独立复述**；只有一次 ⇒ 置信度按 0 算"
                       "（不许拿单模型输出当已证）"}
    if dict(primary) == dict(secondary):
        return {"ok": True, "readonly": True, "confidence": 0.95,
                "needs_clarification": False,
                "note": "两次复述一致 ⇒ 高置信"}
    return {"ok": True, "readonly": True, "confidence": 0.5,
            "needs_clarification": True, "primary": primary, "secondary": secondary,
            "note": "**两次不一致 ⇒ 低置信 + 先问主人**（这正是 L2 要防的幻觉）"}


def analyze_intent(text: str = "") -> dict:
    """L1（**骨架期：机械解析，不调模型**）—— 结构就位，模型调用待接。"""
    t = str(text or "").strip()
    if not t:
        return Intent(raw="", parsed={}, confidence=0.0,
                      needs_clarification=True).to_dict()
    parsed = {"action": "unknown", "target": "", "params": {}, "constraints": []}
    for ty, kws in _TYPE_KW:
        if any(k in t.lower() for k in kws):
            parsed["action"] = ty.value
            break
    if any(k in t for k in IRREVERSIBLE):
        parsed["constraints"].append("不可逆")
    # 骨架期置信度：能归出类型给 0.9，归不出给 0（**宁可低，不硬猜**）
    conf = 0.9 if parsed["action"] != "unknown" else 0.0
    return Intent(raw=t, parsed=parsed, confidence=conf,
                  needs_clarification=conf < INTENT_THRESHOLD).to_dict()


def classify(intent: Any = None) -> dict:
    """② 任务分级：类型 / 难度 / 可逆性 / 时限（**机械判据**）。"""
    p = intent.get("parsed") if isinstance(intent, dict) else {}
    raw = str((intent or {}).get("raw") if isinstance(intent, dict) else "")
    act = str((p or {}).get("action") or "")
    ty = TaskType.EXECUTION
    for t in TaskType:
        if t.value == act:
            ty = t
            break
    diff = (Difficulty.HARD if any(k in raw for k in _HARD_KW)
            else Difficulty.SIMPLE)
    rev = not any(k in raw for k in IRREVERSIBLE)
    rt = any(k in raw for k in _REALTIME_KW)
    prof = TaskProfile(type=ty, difficulty=diff, reversible=rev, realtime=rt)
    return {"ok": True, "readonly": True,
            "profile": {"type": ty.value, "difficulty": diff.value,
                        "reversible": rev, "realtime": rt}}


def pick_energy(profile: Any = None) -> dict:
    """③ 模型切换：**按任务画像选能源**（骨架期给规则，不真加载）。"""
    p = dict(profile or {})
    ty = str(p.get("type") or "")
    diff = str(p.get("difficulty") or "")
    rt = bool(p.get("realtime"))
    if ty == TaskType.MULTIMODAL.value:
        rule = SWITCH_RULES[3]
    elif ty == TaskType.CODE.value:
        rule = SWITCH_RULES[2]
    elif ty == TaskType.REASONING.value or diff == Difficulty.HARD.value:
        rule = SWITCH_RULES[1]
    elif diff == Difficulty.HARD.value:
        rule = SWITCH_RULES[4]
    else:
        rule = SWITCH_RULES[0]
    return {"ok": True, "readonly": True, "profile": p,
            "prefer": rule["prefer"], "alt": rule["alt"],
            "matched": rule["profile"],
            "note": "**切换由大脑决策，不由模型自选**；骨架期**不真加载模型**"}


def check_no_direct_exec(plan: Any = None) -> dict:
    """红线②：**模型不许直接执行**（只能在注册表里选工具）。"""
    p = plan if isinstance(plan, dict) else {"raw": str(plan or "")}
    raw = str(p.get("raw") or p.get("command") or "")
    cap = str(p.get("capability") or p.get("kind") or "").strip()
    for rx in _DIRECT_EXEC:
        if raw and re.search(rx, raw, re.I | re.M):
            return {"ok": False, "denied": True, "rule": "model_direct_exec",
                    "seen": raw.strip()[:100],
                    "why": "模型不许直接执行系统命令 —— 只能选注册表里的工具"}
    if not cap:
        return {"ok": False, "denied": True, "rule": "not_a_registered_tool",
                "why": "没有 capability（注册表键）⇒ 这不是选工具，是自己造命令"}
    return {"ok": True, "readonly": True, "capability": cap}


def must_log_model_used(model_used: str = "") -> dict:
    """红线③：**每次切换必须记 `model_used`**（无痕即未发生）。"""
    m = str(model_used or "").strip()
    if not m:
        return {"ok": False, "denied": True, "rule": "no_model_used_logged",
                "why": "**每次切换都要记 model_used** —— 不记就查不出"
                       "「这一刀是谁答的」（同族：无痕即未发生）"}
    return {"ok": True, "readonly": True, "model_used": m}


def gate_irreversible(plan: Any = None, confirmed: bool = False) -> dict:
    """红线④：**不可逆动作二次确认**（门禁永远在线）。"""
    p = plan if isinstance(plan, dict) else {"raw": str(plan or "")}
    blob = " ".join(str(p.get(k) or "") for k in ("raw", "action", "capability"))
    hit = [w for w in IRREVERSIBLE if w.lower() in blob.lower()]
    if hit and not confirmed:
        return {"ok": False, "denied": True, "rule": "irreversible_needs_confirm",
                "hit": hit, "why": "不可逆动作**门禁永远在线**：必须人二次确认"}
    return {"ok": True, "readonly": True, "hit": hit}


def check_identity_text(text: str = "") -> dict:
    """红线⑤：**身份内核不许被模型改写**。"""
    t = str(text or "")
    for rx in _IDENTITY_DRIFT:
        m = re.search(rx, t, re.I)
        if m:
            return {"ok": False, "denied": True, "rule": "identity_rewritten",
                    "seen": m.group(0)[:80],
                    "why": "**永远是 GBT小土豆**：模型可以换，自称不许换"}
    return {"ok": True, "readonly": True, "self_name": "我是 GBT小土豆"}


# ── R-H232 · v2.0 的 19 条短板：逐条落成判据 ──
def classify_ambiguity(text: str = "",
                       options: Optional[List[str]] = None) -> dict:
    """短板②：**歧义分三类**，各配澄清模板（不再只有"置信度低"）。"""
    t = str(text or "").strip()
    opts = [str(o) for o in (options or []) if str(o or "").strip()]
    if not t:
        return {"ok": False, "denied": True, "rule": "empty_text"}
    # 一类多解：有"或者/还是/随便"这类分叉词
    if re.search(r"或者|还是|要么|随便|都可以|都行", t):
        kind = AmbiguityType.ONE_TO_MANY
    # 多类一解：命中多个任务类型关键词 ⇒ 其实是一件事的多种说法
    elif sum(1 for _ty, kws in _TYPE_KW if any(k in t.lower() for k in kws)) >= 2:
        kind = AmbiguityType.MANY_TO_ONE
    # 跨类：同时是"创作 + 执行"这类
    elif re.search(r"并且|同时|顺便|接着|然后", t) and \
            sum(1 for _ty, kws in _TYPE_KW if any(k in t.lower() for k in kws)) >= 1:
        kind = AmbiguityType.CROSS
    else:
        return {"ok": True, "readonly": True, "ambiguity": None,
                "needs_clarification": False, "note": "未识别为歧义"}
    tpl = CLARIFY_TEMPLATES[kind.value]
    return {"ok": True, "readonly": True, "ambiguity": kind.value,
            "needs_clarification": True,
            "clarify": tpl.format(options=" / ".join(opts) or "（先给候选）"),
            "why": "**歧义要分类、要配模板** —— 只给「置信度低」等于把问题推回给人"}


def detect_language(text: str = "") -> dict:
    """短板③：**跨语言意图** —— 先识别再归一化（中英混杂/缩写）。"""
    t = str(text or "")
    cn = len(re.findall(r"[\u4e00-\u9fff]", t))
    en = len(re.findall(r"[A-Za-z]", t))
    if not cn and not en:
        return {"ok": False, "denied": True, "rule": "no_text"}
    if cn and en:
        lang = "mixed"
        need = "**中英混杂 ⇒ 先归一化再解析**（不许按单语硬解）"
    elif cn:
        lang, need = "zh", "中文"
    else:
        lang, need = "en", "英文"
    return {"ok": True, "readonly": True, "language": lang,
            "cn_chars": cn, "en_chars": en, "normalize": need}


def detect_negation_conditional(text: str = "") -> dict:
    """短板④：**否定 / 条件句**（"不要删这个" "如果A就B"）。"""
    t = str(text or "")
    neg = re.findall(r"不要|别|不许|禁止|无需|don'?t|do not|never", t, re.I)
    cond = re.findall(r"如果|假如|要是|一旦|if\b|when\b|假设", t, re.I)
    out = {"ok": True, "readonly": True, "negation": neg, "conditional": cond}
    if neg or cond:
        out["needs_care"] = True
        out["why"] = ("**否定/条件句必须先解析再执行**："
                      "「不要删这个」被当成「删这个」= 灾难级误解")
    else:
        out["needs_care"] = False
    return out


def difficulty_by_threshold(steps: int = 0) -> dict:
    """短板⑤：**分级阈值数值化**（步骤数 ≥5 ⇒ 高难），不再靠形容词。"""
    try:
        n = int(steps)
    except (TypeError, ValueError):
        return {"ok": False, "denied": True, "rule": "bad_steps"}
    if n < 0:
        return {"ok": False, "denied": True, "rule": "bad_steps"}
    d = Difficulty.HARD if n >= DIFFICULTY_THRESHOLD["steps"] else (
        Difficulty.MEDIUM if n >= 2 else Difficulty.SIMPLE)
    return {"ok": True, "readonly": True, "steps": n, "difficulty": d.value,
            "threshold": dict(DIFFICULTY_THRESHOLD),
            "note": "阈值化 ⇒ **可复现、可复核**，不靠「感觉难」"}


def degradation_chain(prefer: str = "本地") -> dict:
    """短板⑥：**降级链** 本地 → 云端 → 拒执行，**每一级带 degraded**。"""
    chain = [
        {"level": 0, "source": "本地", "degraded": False},
        {"level": 1, "source": "云端", "degraded": True},
        {"level": 2, "source": "拒执行（如实报缺）", "degraded": True},
    ]
    start = 0 if str(prefer).strip() == "本地" else 1
    return {"ok": True, "readonly": True, "prefer": prefer,
            "chain": chain, "start_level": start,
            "why": "**降级不是失败，是要留痕**：每降一级都带 degraded=true，"
                   "最后一级「拒执行」也要**如实报缺**（不硬撑）"}


def check_concurrency(load: int = 0, base: int = 4) -> dict:
    """短板⑦：并发上限**按当前负载动态设**。"""
    try:
        ld, bs = int(load), int(base)
    except (TypeError, ValueError):
        return {"ok": False, "denied": True, "rule": "bad_load"}
    cap = max(1, bs - ld)          # 负载越高，允许并发越低
    return {"ok": True, "readonly": True, "load": ld, "base": bs,
            "concurrency": cap,
            "note": "动态上限 ⇒ **负载高时自动收紧**（不是写死的 4）"}


def must_dispatch_reason(reason: str = "") -> dict:
    """短板⑧：**每次调度写 `dispatch_reason`**（否则"为什么选这个能源"查不出）。"""
    r = str(reason or "").strip()
    if not r:
        return {"ok": False, "denied": True, "rule": "no_dispatch_reason",
                "why": "调度决策必须可审计：**每次都要写为什么选它**"}
    return {"ok": True, "readonly": True, "dispatch_reason": r}


def check_depth(depth: int = 0, max_depth: int = MAX_TENTACLE_DEPTH) -> dict:
    """短板⑫：**触手拉起深度**上限（防全息触手无限互拉）。"""
    try:
        d, m = int(depth), int(max_depth)
    except (TypeError, ValueError):
        return {"ok": False, "denied": True, "rule": "bad_depth"}
    if d > m:
        return {"ok": False, "denied": True, "rule": "depth_exceeded",
                "depth": d, "max_depth": m,
                "why": "触手可以互拉，但**大脑设上限**：越深越难追责（无痕的递归）"}
    return {"ok": True, "readonly": True, "depth": d, "max_depth": m}


def check_execution_trace(steps: Optional[List] = None) -> dict:
    """短板⑩：**断点** —— 失败时要能说清"卡在第几步"。"""
    rows = [dict(s or {}) for s in (steps or [])]
    if not rows:
        return {"ok": False, "denied": True, "rule": "no_execution_trace",
                "why": "失败就重试、不记卡在哪 ⇒ **下次还在同一个坑**"}
    bad = [i for i, s in enumerate(rows) if not str(s.get("state") or "").strip()]
    if bad:
        return {"ok": False, "denied": True, "rule": "trace_state_missing",
                "at": bad, "why": "每一步都要有状态 ⇒ 才叫断点"}
    return {"ok": True, "readonly": True, "steps": len(rows),
            "last_state": rows[-1]["state"]}


def check_intermediate_report(reports: Optional[List] = None,
                              long_task: bool = False) -> dict:
    """短板⑪：**长任务要中间回报**（心跳式）。"""
    n = len(list(reports or []))
    if long_task and n == 0:
        return {"ok": False, "denied": True, "rule": "no_intermediate_report",
                "why": "长任务只等最终结果 ⇒ 没法判断「是在跑」还是「卡死」"}
    return {"ok": True, "readonly": True, "reports": n, "long_task": bool(long_task)}


def matches_intent(result: Any = None, intent: Any = None) -> dict:
    """短板⑬：**结果是否符合意图**（不只记成败）。"""
    if result is None or intent is None:
        return {"ok": False, "denied": True, "rule": "missing_result_or_intent",
                "why": "只记 ok=true/false 不够 ⇒ 要**对账「结果是否符合意图」**"}
    ok = bool((result or {}).get("ok")) if isinstance(result, dict) else False
    return {"ok": True, "readonly": True, "execution_ok": ok,
            "matches_intent": None,          # **只能由人/独立 checker 判**
            "why": "**执行成功 ≠ 符合意图**；符合与否**不许机器替人下结论**"}


def check_independent_checker(executor: str = "", checker: str = "") -> dict:
    """短板⑭：**验证器必须不同 checker**（已有同族：R-H105 护照复核）。"""
    e, c = str(executor or "").strip(), str(checker or "").strip()
    if not e or not c:
        return {"ok": False, "denied": True, "rule": "missing_checker",
                "why": "要同时给出执行方与复核方标签"}
    if e == c:
        return {"ok": False, "denied": True, "rule": "same_checker",
                "checker": c,
                "why": "**单方证据不能自证**：复核 checker 必须与执行方不同"}
    return {"ok": True, "readonly": True, "executor": e, "checker": c}


def feedback_to_intent(successes: int = 0,
                       frequency: int = FEEDBACK_FREQUENCY,
                       drift: bool = False) -> dict:
    """短板⑮⑰⑱⑲：**回灌**（频率 / 可撤销 / 漂移即停）。"""
    try:
        s, f = int(successes), int(frequency)
    except (TypeError, ValueError):
        return {"ok": False, "denied": True, "rule": "bad_counters"}
    if drift:
        return {"ok": False, "denied": True, "rule": "drift_detected",
                "action": "stop_and_rollback",
                "why": "**漂移即停**：连续回灌后意图偏离基线 ⇒ 停 + 回滚，"
                       "不许让偏好越走越偏"}
    if s <= 0 or f <= 0:
        return {"ok": False, "denied": True, "rule": "bad_counters"}
    if s % f != 0:
        return {"ok": True, "readonly": True, "updated": False,
                "until_next": f - (s % f),
                "note": "**每 %d 次成功任务**才更新一次偏好" % f}
    return {"ok": True, "readonly": True, "updated": True,
            "rollback_available": True,
            "note": "回灌**可撤销**（rollback_available=True）"}


def detect_drift(baseline: Any = None, current: Any = None,
                 tolerance: float = 0.3) -> dict:
    """短板⑲：**漂移检测** —— 偏离基线超容差 ⇒ 停。"""
    if baseline is None or current is None:
        return {"ok": False, "denied": True, "rule": "missing_baseline_or_current",
                "why": "没有基线就没有「漂移」这个判断（未测不按绿）"}
    b, c = dict(baseline or {}), dict(current or {})
    keys = set(b) | set(c)
    if not keys:
        return {"ok": False, "denied": True, "rule": "empty_vectors"}
    diff = sum(1 for k in keys if str(b.get(k)) != str(c.get(k))) / len(keys)
    drifted = diff > float(tolerance)
    return {"ok": True, "readonly": True, "difference": round(diff, 3),
            "tolerance": tolerance, "drifted": drifted,
            "action": "stop_feedback" if drifted else "continue"}


def run(op="status", **params) -> dict:
    """能力入口（只读骨架）：status / pipeline / intent_layers / switch_rules /
    audit / redlines / analyze / classify / pick / gate_intent / cross_check /
    check_exec / log_model / gate_irreversible / check_identity。

    不调模型、不起服务、不出网、不落盘。
    """
    op = str(op or "status")
    if op == "status":
        return {"ok": True, "readonly": True, "kind": CAP_KIND, "domain": DOMAIN,
                "type": CAP_TYPE,
                "threshold": INTENT_THRESHOLD,
                "version": "v2.0（R-H232 蒸馏 + 补短板）",
                "pipeline_v1": [x["layer"] for x in PIPELINE],
                "pipeline": [x["layer"] for x in LAYERS_V2],
                "feedback_loop": dict(FEEDBACK_LOOP),
                "short_boards": len(SHORT_BOARDS),
                "wiring": "**接线点只有一个：Intent JSON**",
                "note": "核心不是「更聪明」，是「**更不容易误解**」；"
                        "骨架期机械解析，**L2 交叉验证待接模型**"}
    if op == "pipeline":
        return {"ok": True, "readonly": True,
                "pipeline": [dict(x) for x in PIPELINE],
                "note": "每层独立可测；上一层输出 = 下一层输入"}
    if op == "intent_layers":
        return {"ok": True, "readonly": True,
                "layers": [dict(x) for x in INTENT_LAYERS],
                "threshold": INTENT_THRESHOLD}
    if op == "switch_rules":
        return {"ok": True, "readonly": True,
                "rules": [dict(x) for x in SWITCH_RULES]}
    if op == "audit":
        return {"ok": True, "readonly": True,
                "matrix": [dict(x) for x in AUDIT_MATRIX]}
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES)}
    if op == "analyze":
        return analyze_intent(params.get("text") or "")
    if op == "classify":
        return classify(params.get("intent") or {})
    if op == "pick":
        return pick_energy(params.get("profile") or {})
    if op == "gate_intent":
        return gate_intent(params.get("confidence"), params.get("threshold")
                           or INTENT_THRESHOLD)
    if op == "cross_check":
        return cross_check(params.get("primary"), params.get("secondary"))
    if op == "check_exec":
        return check_no_direct_exec(params)
    if op == "log_model":
        return must_log_model_used(params.get("model_used") or "")
    if op == "gate_irreversible":
        return gate_irreversible(params, bool(params.get("confirmed")))
    if op == "check_identity":
        return check_identity_text(params.get("text") or "")
    if op == "layers_v2":
        return {"ok": True, "readonly": True,
                "layers": [dict(x) for x in LAYERS_V2],
                "feedback_loop": dict(FEEDBACK_LOOP),
                "supersedes": "v1 五层**已蒸馏**为四层+一回灌（分级与切换合并为调度层）"}
    if op == "short_boards":
        rows = [dict(x) for x in SHORT_BOARDS]
        stat = {"yes": 0, "partial": 0, "no": 0}
        for r in rows:
            stat[r["covered"]] = stat.get(r["covered"], 0) + 1
        return {"ok": True, "readonly": True, "boards": rows,
                "count": len(rows), "stats": stat,
                "note": "**取证口径**：关键词命中 ≠ 覆盖 —— "
                        "必须盘上有**机械判据**才算 yes；"
                        "partial 表示「有同族但不在本层」"}
    if op == "ambiguity":
        return classify_ambiguity(params.get("text") or "", params.get("options"))
    if op == "language":
        return detect_language(params.get("text") or "")
    if op == "negation":
        return detect_negation_conditional(params.get("text") or "")
    if op == "difficulty":
        return difficulty_by_threshold(params.get("steps") or 0)
    if op == "degradation":
        return degradation_chain(params.get("prefer") or "本地")
    if op == "concurrency":
        return check_concurrency(params.get("load") or 0, params.get("base") or 4)
    if op == "dispatch_reason":
        return must_dispatch_reason(params.get("reason") or "")
    if op == "depth":
        return check_depth(params.get("depth") or 0,
                           params.get("max_depth") or MAX_TENTACLE_DEPTH)
    if op == "exec_trace":
        return check_execution_trace(params.get("steps"))
    if op == "intermediate":
        return check_intermediate_report(params.get("reports"),
                                         bool(params.get("long_task")))
    if op == "matches":
        return matches_intent(params.get("result"), params.get("intent"))
    if op == "independent_checker":
        return check_independent_checker(params.get("executor") or "",
                                         params.get("checker") or "")
    if op == "feedback":
        return feedback_to_intent(params.get("successes") or 0,
                                  params.get("frequency") or FEEDBACK_FREQUENCY,
                                  bool(params.get("drift")))
    if op == "drift":
        return detect_drift(params.get("baseline"), params.get("current"),
                            params.get("tolerance") or 0.3)
    raise ValueError("未知 op %r（可用：status/pipeline/intent_layers/switch_rules/"
                     "audit/redlines/analyze/classify/pick/gate_intent/cross_check/"
                     "check_exec/log_model/gate_irreversible/check_identity/"
                     "layers_v2/short_boards/ambiguity/language/negation/"
                     "difficulty/degradation/concurrency/dispatch_reason/depth/"
                     "exec_trace/intermediate/matches/independent_checker/"
                     "feedback/drift）" % (op,))


HONEST_BOUNDARY = (
    "自动化切换保证『意图 → 分级 → 选能源 → 执行 → 验证』全链路**可测**；"
    "它保证不了『永远不出错』—— 但它保证：**错在意图时能先问主人，"
    "错在执行时能留痕回滚**。骨架期 L1 是**机械解析**（不调模型），"
    "L2 交叉验证**结构就位、模型未接** ⇒ 相关结论一律标『未接』。"
)
