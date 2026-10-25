# gbt-capability: creation_camp
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""创造营编排：**主题 → 逐日营计划**（蒸馏自「AI 视觉创造营」，只吞"营的形式架构"）。

## 抓取口径（本仓规矩：凡抓取必写源·时间·口径）
· **源**：2026-10-01 主人给的截图 —— `ST WORKSHOP · 开营仪式 · AI视觉创造营 / Visual Creation Camp <2025>`
  （装置沙龙；页内文案「很多宝宝问 学完AI视觉能做什么？」「AI保姆级教程」；桌签「7 天」）。
· **时间**：2026-10-01。
· **口径**：截图只承载**营的形式**（开营 → 逐日推进 → 作品产出 → 展陈/发布，7 天节奏）。
  **课程正文内容无料 ⇒ 不编**（`sources` 里如实标「待料」）。只吞形式架构，课程文本等主人补料再进。

## 蒸馏判断：「AI 视觉创造营」的核里我们真缺哪块
| 它的形式 | 我们已有的对位 | 结论 |
|---|---|---|
| 逐日推进的多日节奏（开营→作品→展陈） | `one_shot` 只做**单链**计划；`lr_*`（长程任务层）能承载多日但要人给任务图 | **补这块**：营计划生成器（逐日任务 + 验收点） |
| 视觉创作工具链 | 现成一大把（`comfyui`/`a1art_skill`/`filmkit`/`zimage_rewash`/`edit_pipeline`/`media_run`/`look_grade`/`actioncam`…） | **只引用，不重造** |
| 展陈/发布 | `auto_publish` + `brand_outro` + `media_license` | **只引用** |
| 课程文本/教程内容 | 无料 | **不编**（待主人补） |

## 硬规矩
1. **零网络、零 LLM**：计划是确定性生成的（同输入同输出；可离线复算）。
2. **幽灵能力红**：每一天点名的能力位必须**在注册表里真实存在**（现读 `caps_registry`）；
   缺的落 `缺口` 字段如实标注，**绝不用不存在的名字凑数**。
3. **逐日三件**：任务 / 产出物 / 验收点 —— 缺一件不算成营。
4. **不重造工具**：视觉工具只引用现成的位；本件只管**节奏与验收**。
5. 天数可调（3–14）；7 天为基准节奏（照截图原文「7 天」）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

_CAP = "creation_camp"

SOURCES = {
    "st_workshop_visual_camp": {
        "是什么": "ST WORKSHOP 装置沙龙 · AI视觉创造营 / Visual Creation Camp <2025>",
        "载体": "主人给的截图（开营仪式现场；文案「AI保姆级教程」；桌签「7 天」）",
        "年份": "2025",
        "只吞了": "营的**形式架构**：开营 → 逐日推进 → 作品产出 → 展陈/发布（7 天节奏）",
        "未吞（待料）": "课程正文/教程内容（截图里没有）——主人补课后可再进",
        "口径": "不编课程内容；只出**营计划**（逐日任务 + 产出物 + 验收点）",
    },
}


def _live_caps() -> dict:
    from gbt_allinone import caps_registry as R      # noqa: N806
    return dict(getattr(R, "BENIGN_CAPS", {}) or {})


# ── 7 天基准节奏（照截图：「开营 → 逐日 → 作品 → 展陈」）────────────────────
# 每天点名的都是**现读真位**（运行期再核一次，缺了落"缺口"）。
_PHASES = [
    {"名": "开营·定题与参照系", "任务": ["用一句话定营（主题/受众/交付形态）",
                                   "看赛道情报与风向，立三条参照系"],
     "能力位": ["one_shot", "topic_watch", "trend_watch", "film_intel", "video_intel"],
     "产出物": "主题卡（一句话）+ 参照系三条", "验收点": "主题能一句话说清；参照各带一处出处"},
    {"名": "采样·素材与风格", "任务": ["取参考素材（只读公开页）", "试风格片（小样）"],
     "能力位": ["scrapling", "a1art_skill", "look_grade"],
     "产出物": "素材清单 + 风格小样 3 张", "验收点": "小样能指回参照系；素材带来源"},
    {"名": "构图·分镜与画布", "任务": ["分镜/画布：把主题拆成镜与格", "锚定场景（可复用的场景块）"],
     "能力位": ["filmkit", "flow_canvas", "scene_anchor"],
     "产出物": "分镜表 + 画布页", "验收点": "每格有画面描述与时长；画布可离线打开"},
    {"名": "出图·批量生成", "任务": ["按分镜批量出图/出片（本机优先）", "缺口如实记（谁没就位）"],
     "能力位": ["comfyui", "a1art_skill", "h3_video_gen", "libtv_skill"],
     "产出物": "成包图（≥镜数×2 备选）", "验收点": "每镜至少 2 备选；出图链路读数留档"},
    {"名": "修饰·选片与精修", "任务": ["选片（留/弃 + 理由）", "精修（放大/重绘/调色）"],
     "能力位": ["zimage_rewash", "look_grade", "actioncam"],
     "产出物": "终选片（每镜 1）+ 弃片理由", "验收点": "每弃一条都写得出理由"},
    {"名": "编排·成片与配乐", "任务": ["剪辑/装配（按节拍）", "配乐与混音", "素材许可账登记"],
     "能力位": ["edit_pipeline", "media_run", "audio_mix", "music_publishing", "media_license"],
     "产出物": "成片 v1 + 音乐 + 许可账", "验收点": "能整段播放；许可账无未登记素材"},
    {"名": "展陈·发布与复盘", "任务": ["品牌尾板 + 发布（社媒）", "复盘：留读数（哪儿好哪儿卡）"],
     "能力位": ["brand_outro", "auto_publish", "emotion_projection"],
     "产出物": "发布件 + 复盘一页（带读数）", "验收点": "发布件带署名；复盘每条有读数"},
]


def caps(domain: str = "") -> dict:
    """现读创作侧可用能力（**从注册表现算**，不写死）。"""
    B = _live_caps()
    want = {str(domain)} if domain else {"creation", "video", "social", "recon", "mind", "image_video"}
    out = {}
    for k, v in B.items():
        d = str((v or {}).get("domain") or "")
        if d in want:
            out.setdefault(d, []).append(k)
    for d in out:
        out[d].sort()
    return {"ok": True, "op": "caps", "按域": out,
            "总数": sum(len(v) for v in out.values()),
            "_口径": "现读 caps_registry（不写死条数）；本件的计划只能点名这里存在的位"}


def plan(theme: str = "", days: int = 7, audience: str = "", form: str = "") -> dict:
    """主题 → 逐日营计划（**确定性**：同输入同输出；缺的能力落『缺口』）。"""
    theme = str(theme or "").strip()
    if not theme:
        return {"ok": False, "fail_closed": True, "error": "缺 theme：营要有主题（一句话）"}
    days = max(3, min(14, int(days or 7)))
    B = _live_caps()
    roster = _PHASES
    # 天数映射：7 天基准；更少 ⇒ 末尾相邻几段并成一天（成片/展陈保底），更多 ⇒ 末尾加"迭代日"
    if days < len(roster):
        keep_head = roster[:days - 1]
        tail = roster[days - 1:]
        merged = {"名": "合并日·" + "+".join(t["名"].split("·")[-1] for t in tail),
                  "任务": [x for t in tail for x in t["任务"]],
                  "能力位": sorted({k for t in tail for k in t["能力位"]}),
                  "产出物": " · ".join(t["产出物"] for t in tail),
                  "验收点": " · ".join(t["验收点"] for t in tail)}
        roster = keep_head + [merged]
    elif days > len(roster):
        roster = roster + [{"名": "迭代日·再打磨", "任务": ["按复盘读数改一版", "只改被点名的短板"],
                            "能力位": ["one_shot", "zimage_rewash", "edit_pipeline"],
                            "产出物": "成片 v2", "验收点": "v2 的每条改动能指回复盘读数"}
                           for _ in range(days - len(roster))]
    out_days, gaps = [], []
    for i, ph in enumerate(roster, 1):
        real, missing = [], []
        for k in ph["能力位"]:
            (real if k in B else missing).append(k)
        if missing:
            gaps.extend(missing)
        out_days.append({"day": i, "名": ph["名"], "任务": ph["任务"],
                         "能力位": real, "缺口": missing,
                         "产出物": ph["产出物"], "验收点": ph["验收点"]})
    return {"ok": True, "op": "plan", "theme": theme, "days": len(out_days),
            "audience": str(audience or "未读到"), "form": str(form or "视觉作品（片/展/册）"),
            "营": out_days,
            "缺口": sorted(set(gaps)),
            "_口径": "确定性生成（零网络零 LLM）；能力位现读注册表，缺的落『缺口』；逐日三件（任务/产出物/验收点）",
            "_来源": "形式架构蒸馏自 2026-10-01 主人给的截图（AI视觉创造营 · 7 天）；课程内容无料不编"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": _CAP, "tentacle": _CAP,
            "entry": "run_task('creation_camp', {...})",
            "ops": ["sources", "caps", "plan", "where"],
            "distilled_from": "2026-10-01 主人给的截图 ST WORKSHOP · AI视觉创造营 Visual Creation Camp <2025>"
                              "——只吞**营的形式架构**（7 天：开营→采样→构图→出图→修饰→编排→展陈）",
            "not_copied": "不搬课程内容（截图里没有 ⇒ 不编）；不重造视觉工具（只引用现成位）",
            "hard_rules": ["零网络零 LLM（确定性；同输入同输出）",
                           "幽灵能力红：点名的位必须现读存在，缺的落『缺口』",
                           "逐日三件：任务 / 产出物 / 验收点",
                           "不重造工具：只管节奏与验收"],
            "contract": [
                {"op": "sources", "params": "—", "returns": "源与口径（含『待料』如实标注）"},
                {"op": "caps", "params": "[domain]", "returns": "现读创作侧可用能力（按域）"},
                {"op": "plan", "params": "theme + [days=7] + [audience] + [form]", "returns": "逐日营计划"},
            ]}


def sources() -> dict:
    return {"ok": True, "op": "sources", "sources": SOURCES}


def run_op(op: str = "sources", **params) -> dict:
    op = (op or "sources").lower()
    for n, fn in (("sources", sources), ("caps", caps), ("plan", plan), ("where", where)):
        if op == n:
            return fn(**params)
    return {"ok": False, "fail_closed": True, "error": "未知 op:%s（sources/caps/plan/where）" % op}


if __name__ == "__main__":                                     # 主人的终端入口
    import argparse
    import json
    ap = argparse.ArgumentParser(description="创造营编排（AI 视觉创造营形式蒸馏 · 逐日营计划）")
    ap.add_argument("cmd", nargs="?", default="sources")
    ap.add_argument("--theme", default="")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--audience", default="")
    a = ap.parse_args()
    out = run_op("plan", theme=a.theme, days=a.days, audience=a.audience) if a.cmd == "plan" else run_op(a.cmd)
    print(json.dumps(out, ensure_ascii=False, indent=1))
