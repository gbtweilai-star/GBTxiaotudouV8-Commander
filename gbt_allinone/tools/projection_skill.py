# -*- coding: utf-8 -*-
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""空间投射技能（spatial_projection）· **只读技能卡片**（R-H108 · Owner 2026-09-19 图纸）。

这一刀只做一件事：把「空间投射」这个技能**定义清楚、列出来**，不接任何执行路径。

为什么它必须只读
----------------
投射是**物理世界的写操作**：光打到墙上，屋里的人当场就看见了，撤不回来。
所以本模块与 `gbt_allinone/tools/launcher_inventory.py` 同口径 —— **只呈现，不执行**：
不导入能力层、不调 `run_task`、不含任何写盘原语。真要跑，那是另开一刀的事
（硬件门禁 + 操作者按键 + 授权门），不在本卡片里。

五条原语（图纸原样，**全部未核实**）
---------------------------------
    采集 CAPTURE → 遮罩 MASK → 映射 MAP → 融合 FUSE → 输出 OUTPUT
闭环：采集 → 遮罩 → 映射 → 融合 → 输出 → **反馈**（摄像头回拍验证，回到采集）。

红线：ARM ≠ LIVE（图纸第四条硬约束）
----------------------------------
1. **准备态（ARM）与投射态（LIVE）严格分离**：准备态只算参数（单应性 / 羽化 / 色彩），**永不点亮**。
2. **GO LIVE 只能由操作者明确按钮触发**：不许作为任何其它动作的副作用 ——「顺手就亮了」= 违规。
3. **硬件门禁未全绿前，不允许进入 LIVE**。

这三条与框架自己的授权门**同构**（Owner 定的口径类比）：准备态 ≈ 镜像维度 ·
LIVE ≈ 生产写入 · 操作者按键 ≈ 授权门。**投影仪不会因为「顺手」就亮了 ——
和 AI 不能自己给自己发授权是同一条纪律。**

诚实口径（不许把「在」写成「能用」）
----------------------------------
5/5 原语**全部标「未核实」**：真实采集设备 / 真实物理面 / 真实投影仪 / 多台边缘融合 /
全绿硬件门禁，**一条都没跑过**（本沙箱既没有硬件在环，也没有出站网络）。
本卡片只保证**能力原语可被路由**（名字、顺序、层级、上下游写清楚了），
**不保证硬件在、不保证能跑**。

参考项目（MapMap / Splash / ofxPiMapper）**全部是口述参考**，一个字没有替它们加工或补全；
要核实（改了哪一条）要另开一刀、联网跑。

用法：
    py -3.10 -m gbt_allinone.tools.projection_skill          # 人读卡片
    py -3.10 -m gbt_allinone.tools.projection_skill --json   # 机读卡片
退出码：0 = 正常读出 · 2 = 参数错。**本模块没有任何写路径。**
"""
from __future__ import annotations

import argparse
import json
import sys

SKILL_KEY = "spatial_projection"
SKILL_NAME = "空间投射"
UNVERIFIED = "未核实"
PROVENANCE = "owner-claim-20260919"

# 整张卡的诚实状态：**未核实** —— 因为硬件门禁一次都没跑过。不许写 True。
VERIFIED = False
HONEST_STATUS_NOTE = (
    "5/5 原语未核实：硬件门禁（采集设备 / 物理面 / 投影仪 / 多机融合 / 全绿门）一条都没跑过 —— "
    "本卡只保证『原语可被路由』，不保证『硬件在、能跑』。"
)
SOURCE_NOTE = (
    "Owner 2026-09-19 口述的技能蒸馏（图纸）；参考项目与硬件形态**均未联网核实、未上机实测**。"
)

# 五条能力原语（`status` 一律未核实；`layer` 是归位到五层认知内核的口径）
PRIMITIVES = [
    {"key": "CAPTURE", "name": "采集", "duty": "视频 / 摄像头 / 图片 → 源素材",
     "layer": "感知运动层（感知）", "upstream": "摄像头 · 文件系统", "downstream": "源素材",
     "status": UNVERIFIED, "why_unverified": "需要真实采集设备验证"},
    {"key": "MASK", "name": "遮罩", "duty": "在不规则物理面上画形状",
     "layer": "结构层", "upstream": "物理面坐标", "downstream": "形状遮罩",
     "status": UNVERIFIED, "why_unverified": "需要真实物理面验证"},
    {"key": "MAP", "name": "映射", "duty": "把源贴到目标面（含单应性变换）",
     "layer": "结构层", "upstream": "源素材 + 遮罩", "downstream": "单应性矩阵",
     "status": UNVERIFIED, "why_unverified": "需要真实投影仪验证"},
    {"key": "FUSE", "name": "融合",
     "duty": "多台投影仪边缘融合 + 色彩统一（纯软件形态亦可：边缘羽化 / 色彩校正，此时不依赖多机）",
     "layer": "感知运动层（执行）", "upstream": "多投影仪 + 映射（或单机软件融合）",
     "downstream": "无缝信号", "status": UNVERIFIED,
     "why_unverified": "需要多台投影仪；或退一步，需要一轮真实的软件融合实测"},
    {"key": "OUTPUT", "name": "输出", "duty": "投影信号实际投射",
     "layer": "感知运动层（执行）", "upstream": "融合结果 + 硬件门禁", "downstream": "投影信号",
     "status": UNVERIFIED, "why_unverified": "需要真实硬件门禁全绿"},
]

# 两态 —— 这就是「ARM ≠ LIVE」的机械版：准备态**永不带**点亮能力
PHASES = [
    {"key": "ARM", "name": "准备态",
     "means": "标定与预演：只算映射 / 羽化 / 色彩参数，算完什么都不发生",
     "lights_screen": False,
     "who_can_enter": "读侧全部可进（包括本卡片、沙盘看板）—— 因为进来也不会点亮任何东西"},
    {"key": "LIVE", "name": "投射态",
     "means": "真实投射：信号真的打到物理面上，屋里的人当场看得见，撤不回来",
     "lights_screen": True,
     "who_can_enter": "只有操作者明确按下按钮；不许作为任何其它动作的副作用；硬件门禁未全绿不进"},
]

CONSTRAINTS = [
    "ARM ≠ LIVE：准备态与投射态严格分离（准备态永不点亮）",
    "GO LIVE 只能由操作者明确按钮触发，不做任何其它动作的副作用",
    "硬件门禁未全绿前，不允许进入 LIVE",
    "本卡片只读：不含任何执行路径，不许从卡片直接点亮设备",
]

CLOSED_LOOP = ["采集", "遮罩", "映射", "融合", "输出", "反馈（摄像头回拍验证 → 回到采集）"]

# 与框架自己的门同构（Owner 定的**口径类比**，不是等价性证明）
GATE_ANALOGY = {
    "ARM": "准备态 ≈ 镜像维度（随便排练，不碰真实世界）",
    "LIVE": "投射态 ≈ 生产写入（一次性、不可撤销，屋里的光撤不回来）",
    "operator_button": "操作者按钮 ≈ 授权门（只能主人发，AI 不能自授）",
    "one_line": "投影仪不会因为『顺手』就亮了 —— 和 AI 不能自己给自己发授权是同一条纪律。",
}

REFERENCE_PROJECTS = [
    {"name": "MapMap", "repo": "mapmapteam/mapmap", "provenance": PROVENANCE, "verified": False},
    {"name": "Splash", "repo": "", "provenance": PROVENANCE, "verified": False},
    {"name": "ofxPiMapper", "repo": "", "provenance": PROVENANCE, "verified": False},
]

EXECUTION = "无：本卡片只被读取呈现，不接任何执行路径（与 launcher_inventory 同口径）"


def run(op="status", **params) -> dict:
    """能力入口（只读 · R-H194 补）：status / card。**只读卡片：不执行、不写盘。**

    为什么补：本能力位此前没有 `run()`，编排内核/工作区接不上 ⇒ 孤儿。
    """
    op = str(op or "status")
    if op in ("status", "card"):
        got = skill_card()
        if op == "card":
            return {"ok": True, "readonly": True, **got}
        return {"ok": True, "readonly": True,
                "primitive_count": len(got.get("primitives") or []),
                "note": "空间投射只读卡片：5 原语全标未核实 · ARM ≠ LIVE"}
    raise ValueError("未知 op %r（可用：status/card）" % (op,))


def skill_card() -> dict:
    """整张卡片 —— **单一来源**：沙盘与 CLI 都从这里取，别处不许再抄一份。只读、无副作用。"""
    return {
        "ok": True,
        "readonly": True,
        "readonly_note": "只呈现，不执行：不导入能力层、不调 run_task、无任何写盘原语",
        "skill": SKILL_KEY,
        "name": SKILL_NAME,
        "status": UNVERIFIED,
        "verified": VERIFIED,
        "honest_status_note": HONEST_STATUS_NOTE,
        "source_note": SOURCE_NOTE,
        "primitives": [dict(p) for p in PRIMITIVES],
        "primitive_count": len(PRIMITIVES),
        "unverified_count": sum(1 for p in PRIMITIVES if p["status"] == UNVERIFIED),
        "phases": [dict(p) for p in PHASES],
        "constraints": list(CONSTRAINTS),
        "closed_loop": list(CLOSED_LOOP),
        "gate_analogy": dict(GATE_ANALOGY),
        "reference_projects": [dict(r) for r in REFERENCE_PROJECTS],
        "execution": EXECUTION,
    }


def render_lines(card: dict | None = None) -> list:
    """人读版（纯函数，只拼字符串）。"""
    card = card or skill_card()
    out = ["%s（%s）· 只读技能卡片" % (card["name"], card["skill"]),
           "  状态：%s（%d/%d 原语未核实）"
           % (card["status"], card["unverified_count"], card["primitive_count"]),
           "  原语：" + " → ".join("%s %s" % (p["name"], p["key"]) for p in card["primitives"]),
           "  闭环：" + " → ".join(card["closed_loop"]),
           "  红线："]
    out += ["    - " + c for c in card["constraints"]]
    out += ["  诚实口径：" + card["honest_status_note"],
            "  " + card["execution"]]
    return out


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001 —— 控制台重配失败不影响读卡片
        pass
    ap = argparse.ArgumentParser(description="空间投射技能 · 只读卡片（只呈现，不执行）")
    ap.add_argument("--json", action="store_true", help="机读整张卡片")
    a = ap.parse_args(argv)
    card = skill_card()
    if a.json:
        print(json.dumps(card, ensure_ascii=False, indent=1))
    else:
        print("\n".join(render_lines(card)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
