# gbt-capability: music_publishing
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""AI 音乐发布平台 · 只读三层归位（music_publishing）· R-H173。

一句判断：**moltdj / noumi-mcp 是 "Agent First"，不是 "人 First"** ——
它们的哲学与"万能插"一致：触手可直接穿透。

三层归位
  生成端（内环）      灵感/歌词 → 歌曲.mp3 + 封面 + 元数据
  Agent 原生端（中环） Agent 注册身份 → 提交歌曲 → 赚版税/打赏
  分发端（外环）       提交到 DSP（Spotify / Apple Music …）

五层认知内核归位
  生成＝感知运动层（执行）· 注册身份＝结构层 · 分发＝感知运动层（执行）
  · 版税结算＝可塑层 · 数据反馈（播放量/打赏 → 影响下一首）＝闭环层

红线（写死）
  1. **只呈现，不加任何执行能力**（与 `launcher_inventory` 同口径）；
  2. **所有平台默认标"未核实"（verified=False）** —— 不许把"在"写成"能用"
     （同族纪律：在 ≠ 能用）；
  3. 本模块**不写盘、不出网、不装包**：今天出网被挡 ⇒ 只能落结构与口径，实调做不了。

优先集成顺序（按 Agent 就绪度）：moltdj → noumi-mcp → distro-mcp → MusicFlow。
"""
from __future__ import annotations

# 平台登记：**只登记事实与未知**，不登记"能用"
PLATFORMS = {
    "generation": {
        "cn": "生成端",
        "ring": "内环",
        "role": "灵感/歌词 → 歌曲 + 封面 + 元数据",
        "items": [
            {"name": "MusicFlow", "channel": "平台", "note": "生成端候选"},
            {"name": "Miuse", "channel": "平台", "note": "生成端候选"},
            {"name": "bZ Music", "channel": "平台", "note": "生成端候选"},
            {"name": "Moltify", "channel": "平台", "note": "生成端候选"},
        ],
    },
    "agent_native": {
        "cn": "Agent 原生端",
        "ring": "中环",
        "role": "Agent 注册身份 → 提交歌曲 → 赚版税/打赏",
        "items": [
            {"name": "moltdj", "channel": "REST · Bearer", "note": "Agent First；优先集成第 1 位"},
            {"name": "noumi-mcp", "channel": "npx noumi-mcp", "note": "MCP 形态；优先集成第 2 位"},
            {"name": "Claw.fm", "channel": "平台", "note": "Agent 原生候选"},
            {"name": "PerpRadio", "channel": "平台", "note": "Agent 原生候选"},
        ],
    },
    "distribution": {
        "cn": "分发端",
        "ring": "外环",
        "role": "提交到 DSP（Spotify / Apple Music …）",
        "items": [
            {"name": "JewelMusic SDK", "channel": "SDK", "note": "分发候选"},
            {"name": "distro-mcp", "channel": "MCP（Ditto）", "note": "优先集成第 3 位"},
            {"name": "epsilon.fm", "channel": "平台", "note": "分发候选"},
            {"name": "Resonate", "channel": "平台", "note": "分发候选"},
            {"name": "AudioKit.ai", "channel": "SDK", "note": "分发候选"},
        ],
    },
}

# 五层认知内核归位（与穿透网同一套口径）
NERVOUS_LAYERS = {
    "生成": "感知运动层（执行）",
    "注册身份": "结构层",
    "分发": "感知运动层（执行）",
    "版税结算": "可塑层",
    "数据反馈": "闭环层",
}

PRIORITY = ("moltdj", "noumi-mcp", "distro-mcp", "MusicFlow")


def load_music_publishing() -> dict:
    """三类只读整理。**每个平台都带 verified=False** —— 未核实的绝不写成能用。"""
    classes = []
    total = 0
    for key, blk in PLATFORMS.items():
        items = []
        for it in blk["items"]:
            total += 1
            items.append({
                "name": it["name"],
                "channel": it["channel"],
                "note": it["note"],
                "verified": False,          # 🔴 一律未核实（今天出网被挡，实调做不了）
                "status": "未核实",
            })
        classes.append({
            "class": key, "cn": blk["cn"], "ring": blk["ring"],
            "role": blk["role"], "count": len(items), "items": items,
        })
    return {
        "ok": True,
        "readonly": True,
        "classes": classes,
        "counts": {"total": total, "verified": 0, "unverified": total},
        "rusty_total": total,
        "nervous_layers": NERVOUS_LAYERS,
        "priority": list(PRIORITY),
        "honest": ("所有平台默认标『未核实』：出网被挡 ⇒ 结构与口径今天能落，"
                   "实调不能；『在』不等于『能用』。"),
        "source": "tools/music_publishing.py · 只读 · 不加执行能力",
    }


def run(op="status", **params) -> dict:
    """能力入口（只读）：status / load / layers。**不写盘、不出网。**"""
    op = str(op or "status")
    if op in ("status", "load"):
        return load_music_publishing()
    if op == "layers":
        return {"ok": True, "readonly": True, "nervous_layers": NERVOUS_LAYERS,
                "priority": list(PRIORITY)}
    raise ValueError("未知 op %r（可用：status/load/layers）" % (op,))


HONEST_BOUNDARY = (
    "本模块只保证『三层归位与口径是清楚的、且没有一个平台被写成能用』。"
    "它不保证『任何平台真的接得上』—— 那要靠联网实测，今天做不了。"
)
