"""GBT小土豆V8 · 触手职业表（职业 = 触手的身份，不是装饰）

主人 2026-11-01：「对了最重要的，触手的编程职业呢？」
—— 触手不是一堆能力位，是**有职业的**：编程/审查/测试/安全/运维/架构/数据/视觉/媒体/研究/文档/指挥。
编程是首席职业（code_patch / freebuff_term / git_write / 五处落位 / 真跑测试 / 签名）。

本脚本从 gbt_allinone.caps_registry 现读能力位，按下面写死的职业归属算出：
  · 每个职业覆盖哪些域、多少能力位、代表能力位（真实存在才收）；
  · 输出 data/professions.json（供认知界面「职业」视图与 tools/gen-console-data.py 使用）。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gbt_allinone.caps_registry import BENIGN_CAPS  # noqa: E402

OUT = ROOT / "data" / "professions.json"

# 职业定义：domains 是归属域；patterns 用来挑代表能力位（按名字匹配）；tools/kpi 是这职业真在用的
PROFESSIONS = [
    {
        "id": "coder", "title": "编程工程师", "chief": True,
        "headline": "写代码、改代码、真跑测试、交付到能被别人看懂",
        "domains": ["tools", "pipeline", "project", "automation", "framework"],
        "patterns": ["code_patch", "edit_pipeline", "code_art", "freebuff_term", "git_write",
                     "repo_publish", "platform_profile", "slim_profile", "file_hygiene",
                     "codex_", "claude_code", "codebuddy", "wf_run"],
        "tools": ["终端 / shell", "编辑器读写", "git_read / git_write", "run_task 真跑", "五处落位"],
        "kpi": "改完即测 · 旧物清零 · 签名不丢",
    },
    {
        "id": "reviewer", "title": "代码审查", "chief": False,
        "headline": "审别人的代码，也审自己的；不合格不许合并",
        "domains": ["security", "mind"],
        "patterns": ["code_audit", "review_gate", "execution_guard", "selfscan",
                     "legacy_guard", "signature_guard", "inventory", "trunk_reason"],
        "tools": ["静态审查", "五维自检", "账本对账"],
        "kpi": "0 未审合并 · 审查意见落账",
    },
    {
        "id": "qa", "title": "测试 / 验证", "chief": False,
        "headline": "不信「应该能跑」，只信真跑出来的数字",
        "domains": ["pipeline", "data"],
        "patterns": ["wf_run", "media_run", "quant_backtest", "verify", "test",
                     "doc_counts", "cap_self"],
        "tools": ["pytest 风格断言", "真跑读数字", "截图 / 哈希"],
        "kpi": "每条结论有数字 · 失败即修",
    },
    {
        "id": "security", "title": "安全 / 穿透", "chief": False,
        "headline": "扫描不留死角，疑点必须反思穿透",
        "domains": ["security", "recon"],
        "patterns": ["pentest", "pentest_distill", "devour_github", "ghost_guard",
                     "security", "exposure", "scan"],
        "tools": ["penetrating_cross_scan", "无死角口径", "疑点→反思→穿透"],
        "kpi": "coverage=1.0 · dead_spots=0",
    },
    {
        "id": "ops", "title": "运维 / 守护", "chief": False,
        "headline": "服务在跑、引擎能起、崩了能看",
        "domains": ["system", "engine", "infra", "device", "desktop"],
        "patterns": ["svc_", "engine", "service", "health", "doctor", "breaker",
                     "proc_guard", "watchdog"],
        "tools": ["console-server 自启", "engine-on/off", "服务巡检"],
        "kpi": "服务在线 · 重启自动恢复",
    },
    {
        "id": "architect", "title": "架构 / 设计", "chief": False,
        "headline": "定契约、画链路、管五处落位",
        "domains": ["mind", "tentacle", "framework"],
        "patterns": ["chain_kernel", "code_graph", "trunk", "policy", "registry",
                     "manifest", "cap_self"],
        "tools": ["chain_kernel 七步", "caps_registry", "doс_counts 五处"],
        "kpi": "能力位三处一致（注册/快照/派发）",
    },
    {
        "id": "data", "title": "数据 / 金融", "chief": False,
        "headline": "口径一致，回测可复现",
        "domains": ["data", "finance", "longrun"],
        "patterns": ["quant_", "chart", "db_", "status", "ledger"],
        "tools": ["账本 / 指标", "回测", "数据管道"],
        "kpi": "同一口径两处一致",
    },
    {
        "id": "vision", "title": "视觉 / 图像", "chief": False,
        "headline": "视觉全谱，不止 OCR",
        "domains": ["vision", "image_video", "creation"],
        "patterns": ["vision", "image", "ocr", "screen", "chart_html", "body_see", "gods_eye"],
        "tools": ["11 个视觉能力位", "截图 / 识别 / 图表"],
        "kpi": "看图说得出依据",
    },
    {
        "id": "media", "title": "语音 / 媒体", "chief": False,
        "headline": "说得出、听得懂、剪得动",
        "domains": ["voice", "video", "comms"],
        "patterns": ["voice", "audio", "video", "tts", "asr", "subtitle"],
        "tools": ["语音输入/输出", "视频剪辑", "字幕"],
        "kpi": "产出可播放",
    },
    {
        "id": "recon", "title": "研究 / 侦察", "chief": False,
        "headline": "吸收外部，蒸馏提炼成自己的",
        "domains": ["recon", "devour", "llm"],
        "patterns": ["recon", "devour", "arxiv", "lobe", "absorb", "distill", "search"],
        "tools": ["外部检索", "蒸馏沉淀", "来源标注"],
        "kpi": "每条来源可查",
    },
    {
        "id": "writer", "title": "文档 / 写作", "chief": False,
        "headline": "写给人看，数字不能空话",
        "domains": ["creation", "social"],
        "patterns": ["doc", "readme", "changelog", "write", "page", "post"],
        "tools": ["docs/ 编号", "CHANGELOG", "README 同步"],
        "kpi": "docs 计数与能力位同步",
    },
    {
        "id": "shortvideo", "title": "短视频编导", "chief": False,
        "headline": "3 秒抓人、15 秒讲完、60 秒留人；标题/封面/节奏都要算",
        "domains": ["video", "image_video", "creation"],
        "patterns": ["short", "video_intel", "hunyuan_video", "h3_video_gen", "subtitle",
                     "hook", "caption", "reel"],
        "tools": ["分镜脚本", "视频生成/剪辑", "封面标题", "节奏钩子"],
        "kpi": "完播率 · 前 3 秒留人 · 一稿多版",
    },
    {
        "id": "music", "title": "音乐制作", "chief": False,
        "headline": "写词、编曲、混音、母带，一条链路自己走完",
        "domains": ["voice", "comms"],
        "patterns": ["music_auto", "music_intel", "music_publishing", "audio_mix",
                     "audio_extract", "voice_orchestra", "voice_studio", "hf_voice", "voice"],
        "tools": ["词曲生成", "编曲/混音", "母带", "发行"],
        "kpi": "可听成曲 · 响度达标 · 版权可查",
    },
    {
        "id": "film", "title": "影视 / 电影", "chief": False,
        "headline": "剧本、分镜、镜头调度、成片；一条片从 0 到 1",
        "domains": ["video", "image_video"],
        "patterns": ["film_intel", "filmkit", "machine_film", "one_shot", "shot_director",
                     "storyboard", "cinema"],
        "tools": ["剧本/分镜", "镜头调度", "生成/合成", "成片输出"],
        "kpi": "镜头语言成体系 · 成片可交付",
    },
    {
        "id": "digitalhuman", "title": "数字人 / 直播", "chief": False,
        "headline": "她本人就是产品：形象、骨骼、口型、动作、直播",
        "domains": ["desktop", "device", "creation"],
        "patterns": ["digital_human", "agent_rig", "rig_audit", "rig_fix",
                     "surface_bind", "sec_surface", "live", "avatar"],
        "tools": ["骨骼/绑定", "口型驱动", "动作库", "直播推流"],
        "kpi": "口型对得上 · 不崩脸 · 能直播",
    },
    {
        "id": "design", "title": "设计 / 美术", "chief": False,
        "headline": "配色、字体、版式、品牌；审美闸要能过",
        "domains": ["creation", "image_video"],
        "patterns": ["art_brief", "art_chain", "design_atlas", "brand_outro",
                     "a1art_skill", "chart_html", "code_art", "image_scout", "zimage_rewash"],
        "tools": ["设计令牌", "配色/版式", "品牌资产", "审美闸（emoji/渐变/渐变字）"],
        "kpi": "过审美闸 · 可复用令牌",
    },
    {
        "id": "gamedev", "title": "游戏 / 3D", "chief": False,
        "headline": "建模、绑定、场景、交互；能跑起来才算",
        "domains": ["creation", "device"],
        "patterns": ["blender", "agent_rig", "scene_anchor", "rig_audit", "rig_fix",
                     "three", "glb", "3d"],
        "tools": ["Blender", "Three.js", "骨骼绑定", "场景搭建"],
        "kpi": "60fps · 可交互 · 可导出",
    },
    {
        "id": "orchestrator", "title": "协同 / 指挥", "chief": False,
        "headline": "派单、交接、回喂、留痕",
        "domains": ["tentacle", "collab", "brain", "longrun"],
        "patterns": ["run_task", "orchestration", "tentacle", "task", "brain_", "collab", "handoff"],
        "tools": ["run_task 派单", "orchestration-ledger", "审计"],
        "kpi": "每次派单都有账",
    },
]


def pick_caps(patterns, domains):
    out = []
    for name, meta in BENIGN_CAPS.items():
        dom = (meta or {}).get("domain", "")
        if dom in domains:
            out.append(name)
            continue
        low = name.lower()
        if any(p.lower() in low for p in patterns):
            out.append(name)
    return sorted(set(out))


def main() -> int:
    profs = []
    for d in PROFESSIONS:
        caps = pick_caps(d["patterns"], d["domains"])
        profs.append({
            "id": d["id"], "title": d["title"], "chief": bool(d.get("chief")),
            "headline": d["headline"], "domains": d["domains"],
            "caps": caps, "cap_count": len(caps),
            "tools": d["tools"], "kpi": d["kpi"],
        })
    total = sum(p["cap_count"] for p in profs)
    data = {
        "ok": True,
        "source": "gbt_allinone.caps_registry",
        "total_caps": len(BENIGN_CAPS),
        "professions": profs,
        "sum_cap_count": total,
        "note": "一个能力位可属多职业（协同类会跨域），所以 sum 会大于 385；这是职业视角不是分区。",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("写出:", OUT, "|", len(profs), "个职业 | 覆盖能力位（含重复）", total)
    for p in profs:
        print("  %-10s %-8s 域 %-28s 能力位 %d" % (p["id"], p["title"], ",".join(p["domains"]), p["cap_count"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
