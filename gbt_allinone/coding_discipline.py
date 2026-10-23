# gbt-capability: coding
"""GBT小土豆V8 · 内生编程纪律（Codex-style engineering discipline）。

这是运行时的默认真序，不是需要主人每次提醒的提示词。凡任务被识别为编程/修复/
重构/测试/部署代码，统一入口与 LLM 桥都会自动附上该契约。

原则：增强方法，不删除能力；统一行为，不限制创造。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

CODE_TERMS = (
    "编程", "代码", "源码", "修复", "修bug", "调试", "重构", "实现", "新增功能",
    "接口", "函数", "模块", "脚本", "仓库", "项目", "测试", "单元测试", "回归",
    "报错", "异常", "性能", "安全审计", "代码审查", "部署", "构建", "编译",
    "python", "javascript", "typescript", "java", "golang", "rust", "c++",
    "sql", "html", "css", "react", "vue", "api", "bug", "fix", "refactor",
    "implement", "compile", "build", "test", "pytest", "unittest", "debug",
    "repository", "workspace", "pull request", "commit", "patch",
)

PHASE_ORDER = (
    "orient",
    "define",
    "plan",
    "mirror",
    "implement",
    "verify",
    "harden",
    "report",
)

PHASES = {
    "orient": (
        "先读上下文再写代码：定位仓库、入口、调用链、数据模型、配置、测试和现有风格；"
        "不凭文件名猜行为，不先改后看。"
    ),
    "define": (
        "把问题收束成可验证定义：复现条件、期望行为、不变量、兼容边界、失败模式、"
        "最小成功标准和明确不做的事项。"
    ),
    "plan": (
        "形成最小连贯改动计划：按依赖排序；每个步骤说明要改的文件、原因、验证方式；"
        "拆分互相独立的工作，优先复用现有 API 和项目模式。"
    ),
    "mirror": (
        "在镜像多维度空间先排练生产：明确假设与架构，逐条证伪假设（被推翻立即阻断），"
        "推演依赖、端口、配置、风险和回滚；沙盒环境必须与目标生产环境实测一致"
        "（same_host 的显式断言逐项比对，晋升那一刻再复检环境漂移），"
        "并在镜像维度跑通验收闭环；未全绿不得写生产。"
    ),
    "implement": (
        "小步实现：先根因后表层，保持行为兼容，不改无关代码，不做顺手大重构；"
        "结构化数据用解析器/结构化 API；每次编辑后立即做最窄的语法或行为检查。"
    ),
    "verify": (
        "按证据阶梯验证：语法/静态检查 → 目标单测 → 集成测试 → 负例/错误路径 → "
        "并发与幂等 → 安全边界 → 全量回归。不能运行的项目必须明确说明原因和残余风险。"
    ),
    "harden": (
        "主动检查边界：空值、超时、取消、进程残留、竞态、原子写、路径逃逸、凭证泄露、"
        "资源释放、兼容旧数据和失败回滚；发现问题继续修，不把已知缺陷留给下一轮。"
    ),
    "report": (
        "汇报必须可复核：列出关键文件、行为变化、验证命令与结果、未验证项、剩余风险；"
        "不把推测写成事实，不把部分完成说成全部完成。"
    ),
}

INVARIANTS = (
    "保留并增强已有能力；不得借修复之机删除、禁用、降级或暗中限制原有功能。",
    "优先根因修复，不用吞异常、假成功、无限重试或空实现掩盖问题。",
    "不覆盖用户未提交改动；不清理任务范围外的文件；破坏性操作必须先确认。",
    "高风险动作必须有边界、授权、审计、超时和可回滚路径。",
    "测试隔离生产数据；任何验证若可能污染真实 store，先切换到临时目录。",
    "生产发布前必须在镜像多维空间完成计划、模拟、架构/环境一致性与沙盒闭环；"
    "假设必须可证伪、沙盒与生产环境必须实测一致；"
    "报告未绑定当前镜像和计划指纹、或晋升时刻环境已漂移时不得晋升。",
    "任何有副作用或改变系统状态的动作，执行前必须先感知现实状态与在途动作："
    "已经满足就复用，已经在执行就不重复动手，确认未满足才执行；"
    "force 只能显式表达主人要求重复执行，不能代替执行前观察。",
    "新能力要接进现有统一入口、能力注册、审计和测试，不另造旁路。",
)

VERIFICATION_ORDER = (
    "py_compile / lint / type-check",
    "mirror plan + simulation + production parity",
    "targeted unit tests",
    "sandbox rehearsal closed-loop",
    "integration path",
    "negative and malformed input",
    "concurrency, timeout, cleanup",
    "security and boundary checks",
    "broader regression suite",
)


# 脑部宪法域 · 章目摘要块（方案 §2.4）：只列章号 + 章名，正文按需再读 CHARTER.md。
# 判据：注入文本含「第二十六章」；本块字符数 ≤ 600。
CHARTER_TITLES = (
    "第一章 · 智者条款",
    "第二章 · 两次失败即停律",
    "第三章 · 镜像预演律",
    "第四章 · 方法论入宪",
    "第五章 · 工程行为铁律",
    "第六章 · 心性约束",
    "第七章 · 生效与执行",
    "第八章 · 谦逊与求助",
    "第九章 · 反空壳与反假执行律",
    "第十章 · 静默失效律",
    "第十一章 · 主动汇报律",
    "第十二章 · 原子落地律",
    "第十三章 · 凭据不离屏律",
    "第十四章 · 空不等于不存在律",
    "第十五章 · 结果通道律",
    "第十六章 · 宿主不打扰律",
    "第十七章 · GUI 身份律",
    "第十八章 · 窗口事件通道律",
    "第十九章 · 脚本编码律",
    "第二十章 · 边界来源律",
    "第二十一章 · 指纹算法必须同名",
    "第二十二章 · 判据不许挂在旧数据上",
    "第二十三章 · 署名判据分层",
    "第二十四章 · 锚点必须同换行符",
    "第二十五章 · 终端失败必须响",
    "第二十六章 · 判据必须与文件主流匹配",
)

CHARTER_SUMMARY = "\n".join(
    ("【GBT 工程行为宪章 · 章目摘要 · 默认生效，全文按需再读 CHARTER.md】",) + CHARTER_TITLES
)


def charter_drift() -> dict:
    """章目摘要与 CHARTER.md 的漂移自检（只在被调用时读文件）。"""
    try:
        from pathlib import Path
        doc = Path(__file__).resolve().parents[1] / "CHARTER.md"
        seen = []
        for line in doc.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^##\s+(第[一二三四五六七八九十]+章\s*·\s*.+)$", line.strip())
            if m:
                seen.append(m.group(1).strip())
        return {
            "ok": tuple(seen) == CHARTER_TITLES,
            "charter_heads": len(seen),
            "summary_heads": len(CHARTER_TITLES),
            "missing": [h for h in seen if h not in CHARTER_TITLES],
            "extra": [h for h in CHARTER_TITLES if h not in seen],
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


@dataclass
class CodingContract:
    activated: bool
    reason: str = ""
    phases: dict = field(default_factory=lambda: dict(PHASES))
    invariants: tuple[str, ...] = INVARIANTS
    verification_order: tuple[str, ...] = VERIFICATION_ORDER

    def to_dict(self) -> dict:
        return {
            "activated": self.activated,
            "reason": self.reason,
            "phase_order": list(PHASE_ORDER),
            "phases": self.phases,
            "invariants": list(self.invariants),
            "verification_order": list(self.verification_order),
        }


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_text(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_text(v) for v in value)
    return str(value)


def detect(context) -> bool:
    text = _text(context).lower()
    if not text:
        return False
    for term in CODE_TERMS:
        needle = term.lower()
        if re.search(r"[a-z0-9_+.#-]", needle):
            if re.search(r"(?<![a-z0-9_])" + re.escape(needle) + r"(?![a-z0-9_])", text):
                return True
        elif needle in text:
            return True
    return False


def build(context) -> CodingContract:
    explicit = isinstance(context, dict) and bool(
        context.get("_coding_discipline") or context.get("contract"))
    active = explicit or detect(context)
    reason = ("prepared programming contract" if explicit
              else "detected programming intent" if active else "")
    return CodingContract(activated=active, reason=reason)


def system_prompt(context) -> str:
    contract = build(context)
    if not contract.activated:
        return ""
    lines = [
        "【GBT 内生编程纪律 · 自动生效，无需主人重复提醒】",
        "按以下固定顺序工作，并根据仓库事实调整细节：",
    ]
    for idx, phase in enumerate(PHASE_ORDER, 1):
        lines.append(f"{idx}. {phase}: {PHASES[phase]}")
    lines.append("不可破坏的不变量：")
    lines.extend(f"- {item}" for item in contract.invariants)
    lines.append("验证阶梯：")
    lines.extend(f"- {item}" for idx, item in enumerate(contract.verification_order, 1))
    lines.append(
        "执行要求：在开始编程前完成 orient/define/plan；实施时保持最小连贯改动；"
        "在声称完成前完成与风险相称的验证；最终报告证据与残余风险。"
    )
    lines.append("")
    lines.append(CHARTER_SUMMARY)
    return "\n".join(lines)


def augment_system(system: str = "", context=None) -> str:
    contract = system_prompt(context)
    if not contract:
        return system or ""
    base = str(system or "").strip()
    return f"{base}\n\n{contract}" if base else contract


def prepare_payload(kind: str, payload: dict | None) -> dict:
    """在编程任务载荷中附带内生契约；原字段全部保留。"""
    data = dict(payload or {})
    context = {
        "kind": kind,
        **{k: data.get(k) for k in (
            "goal", "prompt", "q", "message", "task", "description", "intent",
            "content", "name", "target", "repo", "url",
        ) if data.get(k) is not None},
    }
    contract = build(context)
    if contract.activated and "_coding_discipline" not in data:
        data["_coding_discipline"] = contract.to_dict()
    return data


def apply_llm(kind: str, payload: dict | None, prompt: str, system: str = "") -> tuple[str, str]:
    """供 LLM 桥使用：代码相关对话自动附纪律，其它任务原样通过。"""
    data = payload or {}
    context = {
        "kind": kind,
        "prompt": prompt,
        "system": system,
        "contract": data.get("_coding_discipline"),
    }
    return prompt, augment_system(system, context)


def status() -> dict:
    return {
        "ok": True,
        "automatic": True,
        "phase_order": list(PHASE_ORDER),
        "phases": dict(PHASES),
        "invariants": list(INVARIANTS),
        "verification_order": list(VERIFICATION_ORDER),
        "note": "编程任务经统一入口与 LLM 桥自动装载；其它任务不额外注入。",
    }
