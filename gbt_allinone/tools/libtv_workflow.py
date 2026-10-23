# gbt-capability: libtv_workflow
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""LibTV 节点式工作流（libtv_workflow）· R-H246 只读骨架。

LibTV 的核心**不是「写提示词」，是「搭工作流」**：
无限画布 + 节点式工作流 —— 剧本 / 分镜 / 镜头 / 剪辑全在同一个空间里。

五动作：`create_node` · `connect` · `set_params` · `run` · `batch_run`
五大基础节点（物料层）：文本 / 图片 / 视频 / 音频 / **脚本**

四条红线：**与 R-H204 / R-H207 / R-H212 / R-H221 已落的一字不差**（引用，不重造）。

来源：**主人提供**（画布项目分析）· 盘上无命中 · **未独立取证**（出网受限 + 画布需登录）。
本骨架只读：**不建节点、不连线、不跑任务、不出网、不落盘**。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

CAP_KIND = "libtv_workflow"
DOMAIN = "video"
CAP_TYPE = "external"
TRACE_SOURCE_KIND = "libtv"

ACTIONS = (
    {"key": "create_node", "cn": "在画布上创建指定类型的节点"},
    {"key": "connect", "cn": "连接两个节点，建立数据流"},
    {"key": "set_params", "cn": "设置节点参数"},
    {"key": "run", "cn": "执行节点，生成内容"},
    {"key": "batch_run", "cn": "批量执行一个资源组内的所有节点"},
)

NODE_TYPES = (
    {"key": "text", "cn": "文本节点", "what": "故事大纲 / 产品卖点 / 关键描述",
     "note": "可调内置创意脚本 → 生成结构化分镜脚本"},
    {"key": "image", "cn": "图片节点", "what": "角色设定图 / 场景参考图 / 产品主图"},
    {"key": "video", "cn": "视频节点", "what": "参考视频 / 待编辑素材"},
    {"key": "audio", "cn": "音频节点", "what": "背景音乐 / 配音"},
    {"key": "script", "cn": "脚本节点", "what": "核心「生产」节点",
     "note": "右键 → 添加节点 → 脚本节点 → 「通过角色生成分镜脚本」"
             "⇒ 批量分镜图与视频生成"},
)
QUICK_ADD = ("上传", "从图库上传")

PARAM_CONTRACT = {
    "generator_params": {"flag": "-s",
                         "rule": "走模型 schema 校验，**schema 外的键会被拒绝**"},
    "node_top_level": {"flag": "-u", "rule": "节点顶层属性"},
    "history_defaults": {"model": "StarVideo 2.0", "aspect": "16:9",
                         "resolutions": ("720p（预览）", "1080p（定稿）")},
}

PITFALLS = (
    {"key": "group_bind", "cn": "资源组绑定",
     "what": "建组后**必须** `libtv group use -r` 从**标准输入**读 key 绑定资源，"
             "否则节点可能**找不到依赖的素材**"},
    {"key": "stdout_suppress", "cn": "管道输出",
     "what": "**终点节点**建议 `>/dev/null` 抑制 stdout，避免输出误流到外层管道，"
             "导致下游程序**收不到预期的 key**"},
)

RED_LINES = (
    "密钥只存 DPAPI：LIBTV_ACCESS_KEY 走密钥池，不许明文落盘",
    "结果必须落盘：生成结果必须下载到本地，不许只留远程链接",
    "每次操作留痕：写 trace_store，source_kind=libtv",
    "不绕官方入口：必须走 libtv-skill 脚本，不许自己拼 API 请求",
)
RED_LINES_SOURCE = ("引用自 R-H204（密钥三条）+ R-H207（不绕官方入口）+ "
                    "R-H212（DPAPI/留痕）+ R-H221（OSS/官方入口）—— 双源印证，不重造")

HOWTO = (
    {"n": 1, "cn": "入口", "what": "登录 liblib.tv → 「开始创作」→ 无限画布"},
    {"n": 2, "cn": "起步策略",
     "what": "先做「开场 / 主体 / 收尾」三个镜头的最小单元，把基础逻辑跑通再扩序列长度；"
             "切忌一上来就几十秒（人物错位 / 场景跳脱 ⇒ 反复返工）"},
    {"n": 3, "cn": "工作流模式",
     "what": "核心是「脚本 → 分镜图组（script storyboard）」："
             "先建组、绑定资源，然后整组按序跑"},
    {"n": 4, "cn": "批量生成",
     "what": "把「脚本→分镜图→视频片段→合成」拆成可复用节点"},
)

_KEYISH = re.compile(r"\b(?:sk|ak|lt|ghp)[-_][A-Za-z0-9_\-]{16,}\b")


def check_group_bound(bound_keys: Optional[List[str]] = None,
                      stage: str = "run") -> dict:
    """避坑①：**资源组没绑定就不许跑**（否则节点找不到依赖素材）。"""
    keys = [str(k) for k in (bound_keys or []) if str(k or "").strip()]
    if not keys:
        return {"ok": False, "denied": True, "rule": "group_not_bound",
                "stage": stage,
                "why": "建组后必须 `libtv group use -r` 从标准输入读 key 绑定资源；"
                       "未绑定就 run / batch_run ⇒ 节点找不到依赖素材"}
    return {"ok": True, "readonly": True, "bound": len(keys)}


def check_schema_keys(keys: Optional[List[str]] = None,
                      allowed: Optional[List[str]] = None) -> dict:
    """参数契约：`-s` 生成器参数**走 schema**，schema 外的键会被拒。"""
    ks = [str(k) for k in (keys or []) if str(k or "").strip()]
    al = {str(k) for k in (allowed or []) if str(k or "").strip()}
    if not ks:
        return {"ok": False, "denied": True, "rule": "no_generator_params",
                "why": "`-s` 是生成器参数入口；要给出参数键才能校验"}
    if not al:
        return {"ok": False, "denied": True, "rule": "schema_unknown",
                "why": "拿不到模型 schema ⇒ 不许凭记忆写键（schema 外的会被平台拒）"}
    bad = [k for k in ks if k not in al]
    if bad:
        return {"ok": False, "denied": True, "rule": "schema_key_rejected",
                "bad": bad, "allowed": sorted(al),
                "why": "`-s` 生成器参数必须严格符合模型 schema；用错键会被直接拒绝"}
    return {"ok": True, "readonly": True, "keys": ks}


def check_stdout_suppressed(is_terminal: bool = False,
                            suppressed: bool = False) -> dict:
    """避坑②：**终点节点**要抑制 stdout（否则下游收不到预期的 key）。"""
    if is_terminal and not suppressed:
        return {"ok": False, "denied": True, "rule": "stdout_not_suppressed",
                "why": "终点节点建议 `>/dev/null` 抑制 stdout，"
                       "避免输出误流到外层管道 ⇒ 下游程序收不到预期 key"}
    return {"ok": True, "readonly": True, "terminal": bool(is_terminal),
            "suppressed": bool(suppressed)}


def check_no_plaintext_key(payload: Any = None) -> dict:
    """红线①：返回值/参数里不许有明文密钥。"""
    m = _KEYISH.search(str(payload or ""))
    if m:
        return {"ok": False, "denied": True, "rule": "plaintext_key",
                "seen": m.group(0)[:10],
                "why": "密钥只从 DPAPI / 密钥池取；返回值只许带 key_id / 掩码"}
    return {"ok": True, "readonly": True}


def run(op="status", **params) -> dict:
    """能力入口（只读骨架）：status / actions / node_types / params / pitfalls /
    howto / redlines / gate_group / gate_schema / gate_stdout / gate_key。
    不建节点、不连线、不跑任务、不出网、不落盘。"""
    op = str(op or "status")
    if op == "status":
        return {"ok": True, "readonly": True, "kind": CAP_KIND, "domain": DOMAIN,
                "type": CAP_TYPE, "actions": len(ACTIONS),
                "node_types": [x["cn"] for x in NODE_TYPES],
                "core": "不是「写提示词」，是「搭工作流」",
                "evidence": "五动作与已落两套（3 actions / 5 原语）全不相同 ⇒ 真新增量",
                "source": "主人提供 · 盘上无命中 · 未独立取证（出网受限 + 画布需登录）"}
    if op == "actions":
        return {"ok": True, "readonly": True, "actions": [dict(a) for a in ACTIONS]}
    if op == "node_types":
        return {"ok": True, "readonly": True,
                "nodes": [dict(x) for x in NODE_TYPES],
                "quick_add": list(QUICK_ADD),
                "note": "连线在节点间传素材 / 参数 / 文本；"
                        "非线性的好处：改一处参数就能驱动整条流水线重跑"}
    if op == "params":
        return {"ok": True, "readonly": True,
                "generator": dict(PARAM_CONTRACT["generator_params"]),
                "node_top_level": dict(PARAM_CONTRACT["node_top_level"]),
                "history_defaults": dict(PARAM_CONTRACT["history_defaults"])}
    if op == "pitfalls":
        return {"ok": True, "readonly": True,
                "pitfalls": [dict(x) for x in PITFALLS]}
    if op == "howto":
        return {"ok": True, "readonly": True, "steps": [dict(x) for x in HOWTO]}
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES),
                "source": RED_LINES_SOURCE,
                "note": "不新造红线：四条与已落的一字不差"}
    if op == "gate_group":
        return check_group_bound(params.get("bound_keys"), params.get("stage") or "run")
    if op == "gate_schema":
        return check_schema_keys(params.get("keys"), params.get("allowed"))
    if op == "gate_stdout":
        return check_stdout_suppressed(bool(params.get("is_terminal")),
                                       bool(params.get("suppressed")))
    if op == "gate_key":
        return check_no_plaintext_key(params.get("payload"))
    raise ValueError("未知 op %r（可用：status/actions/node_types/params/pitfalls/"
                     "howto/redlines/gate_group/gate_schema/gate_stdout/gate_key）"
                     % (op,))


HONEST_BOUNDARY = (
    "本骨架保证『五动作 / 五节点 / 参数契约 / 两条避坑 / 四条红线』可查、可判；"
    "它不保证「LibTV 画布能被我们自动编排」——"
    "技能包未装、密钥未配、CLI 未跑通（前几刀已实测）；"
    "而且本刀依据的细节**来自主人提供**（画布项目分析），"
    "盘上无命中、未独立取证 ⇒ 一律按「主人提供 · 待核」对待，不写进「已确认」。"
)
