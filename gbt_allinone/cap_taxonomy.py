# -*- coding: utf-8 -*-
# gbt-capability: heartbeat_tentacle
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""cap_taxonomy —— 能力位与操控部位的**严格分类真源**（12 大类）。

## 为什么有这个件

主人令 2026-10-30：「把所有原生能力以及操控部位分类好**必须严格分类好**，
然后每一个分类部署一根心跳触手来对分类内的一切进行定点自检和状态返回给大脑执行层分析
再返回执行指令」。

真源只有一个：`gbt_allinone/caps_registry.py` 的 `BENIGN_CAPS`（349 条）。
本件**不复制**能力表，只做「归类」——把 30 个 domain 精确分到 12 个大类，
并**在调用 audit() 时自校验**：任一条能力必须且只能落在一个类里，总数必须等于真源。

## 为什么是 12 类而不是 30 类

30 个 domain 里有 8 个只有 1~2 条（comms/life/image_video/framework/social/infra/collab/desktop），
按 domain 一域一根触手会得到 30 根里 8 根只盯一两条的空壳触手 —— 那是凑数，不是分类。
12 类是**按器官职能**切的（身/感/知/言/造/工/察/守/调/数/群/进），每类都有实义。

## 三层结构（不混）

| 层 | 内容 | 真源 |
|---|---|---|
| 能力层 | 349 条能力位，30 个 domain | `caps_registry.BENIGN_CAPS` |
| 部位层 | 七根感官 + 六根动作（身体） | `body_map` 实测 |
| 动作层 | 13 个触手动作域 | `tentacle.bridge.TENTACLE_NEIGHBORHOOD_MAP` |

本件把三层钉在一起：能力层 12 大类 → 每类一根心跳触手；部位层与动作层作为
「该类怎么自检」的探针来源挂到对应类上。
"""
from __future__ import annotations

import sys

# ── 12 大类（严格、互斥、全覆盖）──────────────────────────────────────────
# key 用单字代号：既是分类 id，也是触手命名（heartbeat-身 / heartbeat-感 …）
# 🔴 这里**不写探针名**。2026-10-30 实测踩过：本表原带 `"probe": "selfscan"`
#    之类的标注，而触手实际跑的是 modules/policy/runtime ⇒ 两处口径打架，
#    `taxonomy` 打印出来的"怎么自检"是假的。探针唯一真源 = `heartbeat_tentacle.PROBES`。
CATEGORIES: dict = {
    "身": {
        "title": "身 · 操控部位",
        "domains": ["device", "desktop", "tentacle"],
        "desc": "这台机器的七根感官与六根动作，以及桌面操控与触手本体。",
    },
    "感": {
        "title": "感 · 感知输入",
        "domains": ["vision", "voice"],
        "desc": "看（屏幕/图像/接地）与听（语音识别/合成/编队）。",
    },
    "知": {
        "title": "知 · 认知推理",
        "domains": ["mind", "brain"],
        "desc": "思维、意图、好奇、探索、议会、深推理等内在认知。",
    },
    "言": {
        "title": "言 · 语言与模型",
        "domains": ["llm"],
        "desc": "大模型接入、密钥网关、上下文环、云端/本地推理。",
    },
    "造": {
        "title": "造 · 内容生产",
        "domains": ["creation", "video", "image_video"],
        "desc": "图文、视频、音频、数字人、剪辑、调色、发布准备。",
    },
    "工": {
        "title": "工 · 工具与流水线",
        "domains": ["tools", "engine", "pipeline"],
        "desc": "工具链、执行引擎、镜像房间与流水线编排。",
    },
    "察": {
        "title": "察 · 侦察溯源",
        "domains": ["recon"],
        "desc": "溯源、窗口链、UI 元素抽取、域穿透侦察。",
    },
    "守": {
        "title": "守 · 安全与许可",
        "domains": ["security"],
        "desc": "授权门、策略、出网硬钉、数据分级、审计、密钥保护。",
    },
    "调": {
        "title": "调 · 系统运维",
        "domains": ["system", "infra"],
        "desc": "进程、文件、注册表、网络、巡检、基础设施。",
    },
    "数": {
        "title": "数 · 数据与资产",
        "domains": ["data", "project", "finance"],
        "desc": "数据结构、项目台账、量化与账目。",
    },
    "群": {
        "title": "群 · 协作与集成",
        "domains": ["social", "collab", "comms", "integration"],
        "desc": "社交平台、协作、通讯、第三方集成的接入面。",
    },
    "进": {
        "title": "进 · 进化与自动化",
        "domains": ["devour", "automation", "longrun", "life", "framework"],
        "desc": "吞噬学习、自动化链、长跑任务、生命账、框架自身。",
    },
}

# ── 部位层：七根感官 + 六根动作（body_map 实测所得，不手抄猜测）──────────
BODY_SENSES: dict = {
    "see_screen": "屏幕/多显示器",
    "see_camera": "摄像头",
    "hear_mic": "麦克风",
    "speak_out": "扬声器",
    "feel_power": "电量/CPU/内存",
    "net_reach": "网络与身份",
    "bt_nearby": "蓝牙适配器",
}

BODY_ACTUATORS: dict = {
    "see": "截屏",
    "say": "发声(TTS)",
    "type": "键入",
    "click": "点按",
    "volume": "音量",
    "open": "打开",
}

# 动作名 → 能力位名（六根动作各自落到哪个能力位）
ACTUATOR_CAPS: dict = {
    "see": "body_see",
    "say": "body_say",
    "type": "body_type",
    "click": "body_click",
    "volume": "body_volume",
    "open": "body_open",
}
BODY_MAP_CAP = "body_map"  # 身体清单本身（第 7 条 body_*）

# ── 动作层：13 个触手动作域 → 归到哪个大类 ───────────────────────────────
ACTION_DOMAIN_TO_CATEGORY: dict = {
    "感知域": "感",
    "听觉域": "感",
    "信息域": "感",
    "读网域": "感",
    "媒体域": "造",
    "桌面域": "身",
    "侦察域": "察",
    "安全域": "守",
    "运维域": "调",
    "文件域": "数",
    "金融域": "数",
    "AI编程": "工",
    "自动化": "进",
}


# ── 派生逻辑 ──────────────────────────────────────────────────────────────


def category_of(cap_name: str) -> str:
    """返回该能力所属大类代号；未归类返回空串。"""
    from .caps_registry import BENIGN_CAPS

    meta = BENIGN_CAPS.get(cap_name) or {}
    dom = meta.get("domain")
    for code, spec in CATEGORIES.items():
        if dom in spec["domains"]:
            return code
    return ""


def members(code: str) -> list:
    """返回该大类下的全部能力位名（按字母序）。"""
    from .caps_registry import BENIGN_CAPS

    spec = CATEGORIES.get(code)
    if not spec:
        return []
    doms = set(spec["domains"])
    return sorted(n for n, m in BENIGN_CAPS.items() if m.get("domain") in doms)


def all_members() -> dict:
    """{大类代号: [能力位…]}"""
    return {code: members(code) for code in CATEGORIES}


def audit() -> dict:
    """严格分类自校验：不重、不漏、总数对齐真源。

    判据（任一不满足即 ok=False）：
      ① 真源每条能力必须落进且只落进一个大类
      ② 各大类成员数之和 == 真源总数
      ③ 所有 domain 必须全部被某个大类认领（没有孤儿 domain）
      ④ 13 个动作域必须全部有归属大类
    """
    from .caps_registry import BENIGN_CAPS

    total = len(BENIGN_CAPS)
    buckets = all_members()

    unclassified, duplicated = [], []
    for name, meta in BENIGN_CAPS.items():
        dom = meta.get("domain")
        hits = [c for c, spec in CATEGORIES.items() if dom in spec["domains"]]
        if not hits:
            unclassified.append(name)
        elif len(hits) > 1:
            duplicated.append((name, hits))

    s = sum(len(v) for v in buckets.values())

    claimed = {d for spec in CATEGORIES.values() for d in spec["domains"]}
    all_doms = {m.get("domain") for m in BENIGN_CAPS.values()}
    orphan_domains = sorted(x for x in (all_doms - claimed) if x)

    try:
        from .tentacle import bridge as _TB

        action_doms = list(_TB.TENTACLE_NEIGHBORHOOD_MAP.keys())
    except Exception:  # noqa: BLE001
        action_doms = []
    unmapped_actions = [d for d in action_doms if d not in ACTION_DOMAIN_TO_CATEGORY]

    ok = (not unclassified and not duplicated and s == total
          and not orphan_domains and not unmapped_actions)

    return {
        "ok": ok,
        "source_total": total,
        "classified_total": s,
        "categories": len(CATEGORIES),
        "buckets": {k: len(v) for k, v in buckets.items()},
        "unclassified": unclassified[:20],
        "duplicated": duplicated[:10],
        "orphan_domains": orphan_domains,
        "unmapped_action_domains": unmapped_actions,
        "body_senses": len(BODY_SENSES),
        "body_actuators": len(BODY_ACTUATORS),
        "action_domains": len(action_doms),
    }


def describe(probes: dict = None) -> dict:
    """人读总览：12 大类各自管什么、多少条、怎么自检。

    探针名**不从这里出** —— 唯一真源是 `heartbeat_tentacle.PROBES`，要显示就传进来；
    不传就如实写 None，绝不拿旧标注冒充现读（2026-10-30 踩过：分类表写 selfscan、
    触手实际跑 modules，两处口径打架，打印出来的"怎么自检"是假的）。
    """
    buckets = all_members()
    out = []
    for code, spec in CATEGORIES.items():
        p = (probes or {}).get(code) or {}
        out.append({
            "code": code,
            "title": spec["title"],
            "desc": spec["desc"],
            "domains": spec["domains"],
            "cap_count": len(buckets[code]),
            "probe": p.get("name") if p.get("kind") == "cap" else (p.get("kind") or None),
            "probe_note": p.get("note"),
            "action_domains": [d for d, c in ACTION_DOMAIN_TO_CATEGORY.items() if c == code],
        })
    return {
        "categories": out,
        "body": {"senses": BODY_SENSES, "actuators": BODY_ACTUATORS},
        "audit": audit(),
    }


if __name__ == "__main__":
    import json

    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

    print(json.dumps(describe(), ensure_ascii=False, indent=1))
