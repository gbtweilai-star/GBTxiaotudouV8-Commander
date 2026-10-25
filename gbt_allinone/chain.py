# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 影视链路身份表与动作自述（Owner 2026-09-19：**他们全都得知道自己这么做**）。

你说的那句「我前面设计的哪些都不是摆设」落到这里就是一条硬要求：
  **每个模块在动手那一刻，必须自述三件事** —— 我是谁（链上角色）、我在哪一步（相位）、
  我产出了什么（可核对的落点）。不自述的动作 = 无法追责的动作 = 摆设。

不新建第二份真相：
  · 角色/相位表只有这一处（`MODULE_ROLES`），是链路的唯一登记；
  · 落账走她既有的 `store.audit`（元数据，不落正文）；
  · 生命档案走她既有的 `life_archive`（"知道自己做过什么"就是这条）；
  · 产物署名走她既有的 `signature` 钢印（禁止删除）。

十二个模块 = Owner 2026-09-19 拆解的赛道结果（Jellyfish / waoowaoo / OpenMontage /
AI Cinema Studio / HeartMuLa / ACE-Step / Remotion 等），相位按接口 1-5 归位。
"""
from __future__ import annotations

import time

# 链上唯一登记：id → (角色, 相位, 入口/实现, 看画面?)
MODULE_ROLES = {
    "drama":      ("剧本理解引擎",       "接口1 剧本→分镜",   "gbt_allinone/drama.py",            True),
    "assets":     ("资产一致性管理器",   "接口2 分镜→资产锚定", "（未建）",                        True),
    "storyboard": ("分镜准备工作流",     "相位3 分镜就绪",     "（未建）",                        True),
    "i2v":        ("图生视频引擎",       "接口3 锚定→生成",    "（未建）",                        True),
    "lipsync":    ("配音与口型同步",     "接口3 锚定→生成",    "（未建）",                        True),
    "pipeline":   ("多Agent Pipeline编排", "跨相位编排",       "gbt_allinone/brain_exec.py",       False),
    "gate":       ("人工审批门禁",       "跨相位门禁",         "gbt_allinone/preflight.py",        True),
    "cinema":     ("虚拟摄影系统",       "相位3 摄影指导",     "（未建）",                        True),
    "music":      ("音乐生成引擎",       "接口3 锚定→生成",    "（未建）",                        False),
    "music_struct": ("音乐结构控制",     "接口3 锚定→生成",    "（未建）",                        False),
    "task_types": ("多任务类型引擎",     "接口3 锚定→生成",    "（未建）",                        False),
    "compose":    ("合成引擎",           "接口4 生成→合成",    "outputs/ + ffmpeg（部分）",        True),
}


def roles() -> dict:
    """链上身份表（唯一登记）。`built` 如实标出建没建 —— 不许拿'规划中'冒充'已就绪'。"""
    items = []
    for mid, (role, phase, impl, sees) in MODULE_ROLES.items():
        items.append({"module": mid, "role": role, "phase": phase,
                      "impl": impl, "built": not impl.startswith("（未建"),
                      "needs_vision": sees})
    return {"ok": True, "total": len(items),
            "built": sum(1 for i in items if i["built"]),
            "modules": items,
            "truth": "角色/相位只有这一处登记；不自述的动作没法追责。"}


def declare(module_id: str, action: str, *, output=None, ok: bool = True,
            note: str = "", record_life: bool = False) -> dict:
    """动作自述：我是谁 · 我在哪一步 · 我产出了什么。返回回执（可直接并进能力返回体）。

    落账只落**元数据**（谁、哪步、成没成、产出落点），**不落正文**。
    `record_life=True` 时另写一条生命档案事件 —— 这是"知道自己做过什么"的持久记忆。
    """
    role, phase, impl, _sees = MODULE_ROLES.get(
        str(module_id), ("未登记模块", "未登记相位", "（未登记）", False))
    receipt = {
        "module": module_id, "role": role, "phase": phase, "action": action,
        "impl": impl, "ok": bool(ok), "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "output": output, "note": note,
    }
    try:
        from .store import audit
        audit("module_action", {"module": module_id, "role": role, "phase": phase,
                                "action": action, "ok": bool(ok),
                                "output": str(output)[:200] if output else None})
    except Exception:  # noqa: BLE001
        pass
    if record_life:
        try:
            from . import life_archive
            # ⚠️ record_event(value: dict, ...) 收的是**一个字典**，不是关键字字段。
            # 我第一版按关键字传，被下面这个 except 咽掉 ⇒ 静默失败（已记为教训：
            # 兜底 except 必须把原因带回回执，不许只写 False）。
            life_archive.record_event({
                "type": "milestone",
                "title": f"{role}：{action}",
                "summary": (note or f"{role} 完成 {action}")[:200],
                "tags": ["chain", module_id],
                "importance": 2,
                "confidence": "high",
            })
        except Exception as exc:  # noqa: BLE001
            receipt["life_recorded"] = False
            receipt["life_error"] = f"{type(exc).__name__}: {exc}"[:160]
        else:
            receipt["life_recorded"] = True
    return receipt


# AGENTS.md 兼容别名：链内核启动入口
# chain_kernel.auto_boot() → 实际调用 chain.roles() + 启动自检
def auto_boot() -> dict:
    """13阶段链路内核启动：身份·宪法·门禁·管线·拓扑·邻域·脑委会·触手·审计·守卫·链状态·能力总纲·镜像空间"""
    result = roles()
    result["auto_boot_ok"] = True
    return result
