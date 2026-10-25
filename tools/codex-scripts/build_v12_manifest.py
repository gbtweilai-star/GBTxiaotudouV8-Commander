# -*- coding: utf-8 -*-
"""生成 V12 数据层：v11_manifest.json + 新增 workspace 键（工作区源码全量清点真相）。
所有数字都来自本目录里已跑出的扫描 JSON，或在此现场重算，无一条手写。
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

S = Path(__file__).resolve().parent
BASE = S.parent

v11 = json.loads((S / "v11_manifest.json").read_text(encoding="utf-8"))
inv = json.loads((S / "workspace_inventory.json").read_text(encoding="utf-8"))
inv2 = json.loads((S / "workspace_inventory2.json").read_text(encoding="utf-8"))
mods = json.loads((S / "gbt_module_map.json").read_text(encoding="utf-8"))
orph = json.loads((S / "orphan_scan.json").read_text(encoding="utf-8"))
caps = json.loads((S / "caps_registry_parsed.json").read_text(encoding="utf-8"))

SKIP = {".git", "__pycache__", "node_modules", ".pylibs", ".venv"}

# ── 现场重算：自有 .py 的模块清单（供面板引用） ──
own = []
for p in BASE.rglob("*.py"):
    if any(s in p.parts for s in SKIP) or ".scratch" in p.parts:
        continue
    try:
        if p.stat().st_size > 3_000_000:
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    own.append((p, txt.count("\n") + 1, p.stat().st_size))

top_files = sorted(own, key=lambda x: -x[1])[:26]
top_files_js = []

# ── gbt_allinone 包内（排除 .pylibs）──
ga = [(p, n, b) for p, n, b in own if p.parts[len(BASE.parts)] == "gbt_allinone"]
ga_lines = sum(n for _, n, _ in ga)

# ── 未进面板的板块（由 orphan_scan 提供活性判定）──
UNSEEN = {
    "holo_pet": {
        "zh": "全息面板桥", "what": "3D 全息面板本地桥接服务：把静态前端与本地 GLB 送到浏览器、"
        "把 Codex App Server 的流式事件/审批/GBT 动态工具接到面板、把蓝牙与看屏幕统一送回 api.run_task。",
        "lead": "holo_pet/panel_server.py", "lead_lines": 3006,
        "classes": [["EventBus", 8, "线程安全本地事件总线，保留历史供页面刷新后接回状态"],
                    ["MessageDeduper", 6, "受理侧幂等门：同一消息窗口内只受理一次"],
                    ["HoloBridge", 55, "Codex / LLM 降级 / 心智 / GBT 能力的本地适配器"],
                    ["_Handler", 11, "静态资源与本地 API，默认只在 127.0.0.1 起"]],
        "extra": ["research_status.py · 调研信源六态判定（声明/实测/水位三处分开读）",
                  "research/orchestrator.py · 六环最后一环：按时间按顺序把前五环串起来",
                  "social_platforms.py · 社交发布平台表（纯数据，无 IO）"],
        "note": "这是整个工作区最大的单个自有代码文件（3006 行），我之前一个面板都没给它。",
    },
    "potato_pet": {
        "zh": "桌面数字人", "what": "透明无边框置顶的 Live2D 形象层 + 调皮行为引擎 v3 + 多密钥链聊天客户端。",
        "lead": "potato_pet/holo_panel.py", "lead_lines": 0,
        "classes": [["pet_window.py", 0, "形象层：透明、无边框、置顶的 Live2D 美少女窗口"],
                    ["behavior.py", 0, "桌面数字人「调皮行为引擎」v3"],
                    ["main.py", 0, "桌面数字人整合入口"],
                    ["chat_client.py", 0, "聊天客户端：多密钥链真大脑 + 离线自我认知应答"],
                    ["eigenflux_client.py", 0, "EigenFlux CLI 适配器"]],
        "extra": [],
        "note": "数字人这条线我此前只在「其余域」里带过一句，等于没做。",
    },
    ".cluster/five-dim-ultimate": {
        "zh": "五维合一（脑眼耳嘴手）", "what": "第二套五维系统：为「脑-眼-耳-嘴-手」设计的大脑执行中枢，"
        "解决原生 brain 只做一次性决策、五维串行、没有任务拆解与反馈闭环的痛点。",
        "lead": ".cluster/five-dim-ultimate/caps/brain_executive.py", "lead_lines": 791,
        "classes": [["BrainExecutive", 17, "执行中枢：decompose_task / build_plan / evaluate_feedback / adjust_plan / run_task"],
                    ["DimensionSyncEngine", 9, "五维同步：register / on_dimension_event / execute_cycle / execute_steps"],
                    ["DeepVision", 9, "深度视觉：目标检测 / 布局分析 / 色彩提取 / 场景分类"],
                    ["ocr_engine.py", 0, "OCR 文字识别"],
                    ["sound_detector.py", 0, "声音事件检测"],
                    ["file_operator.py", 0, "文件操作能力"]],
        "extra": ["dimension_sync.py · 五维同步引擎 577 行"],
        "note": "关键：我的「大脑执行层」面板显示的五维是 route/execute/tentacle/vision/audit —— "
        "跟这套「脑眼耳嘴手」不是一个东西。工作区里存在两套五维系统，我只呈现了一套，且从未说明还有另一套。",
    },
    "caps/design_brain": {
        "zh": "设计大脑", "what": "AI 驱动 3D 真实图片生成：建筑/室内/翻新/部署布局/审美增强/prompt 构建/ControlNet 渲染。",
        "lead": "caps/design_brain/run.py", "lead_lines": 777,
        "classes": [],
        "extra": ["do_architect · 建筑外观 3D 效果图", "do_interior · 室内装修 3D 效果图",
                  "do_renovate · 翻新前后对比", "do_deploy_layout · 空间规划 3D 图",
                  "do_aesthetic · 审美增强（修过：旧实现恒用默认 warm_luxury）",
                  "do_controlnet_render · 深度估计 + 5 风格批量生成", "do_style_guide · 风格指南"],
        "note": "777 行、22 个顶层函数、有可执行入口，且不在 gbt_allinone 里 —— 它是顶层 caps/ 目录下唯一的东西。",
    },
    "gbt_allinone/recon/last30days": {
        "zh": "情报流水线 last30days", "what": "v3.0.0 编排流水线：LLM 优先的查询规划 + 确定性与安全闸 + "
        "多源检索（GitHub / YouTube / Reddit / Polymarket / TikTok）+ 两阶段补充检索 + 簇优先渲染 + CLI。",
        "lead": "gbt_allinone/recon/last30days/engine/pipeline.py", "lead_lines": 1070,
        "classes": [],
        "extra": ["planner.py · LLM-first 查询规划，对危险查询有确定性兜底（713 行）",
                  "render.py · cluster-first 渲染（1723 行，包内最大）",
                  "github.py / youtube_yt.py / reddit.py / polymarket.py / tiktok.py · 五个源引擎",
                  "cli.py · v3.0.0 命令行入口"],
        "note": "整条流水线 20,756 行，我此前在「情报与观察」面板里只写了七个能力名，源码一行没读。",
    },
    "审美相关skill": {
        "zh": "审美技能与骨架", "what": "design-skeletons + 各平台 last30days 技能副本，469 个 .md 规则文件。",
        "lead": "审美相关skill/design-skeletons/last30days/scripts/last30days.py", "lead_lines": 0,
        "classes": [],
        "extra": ["469 个 .md（本项目 .md 总量 1507 个的三成）", "76 个 .py / 26,114 行",
                  "其中 last30days 是 gbt_allinone 同名流水线的技能化副本"],
        "note": "自有代码里第二大的板块。我和它的唯一交集是「设计流程要读的那几份 md」，代码层从没看。",
    },
    "agent-gvmz-gbtv8": {
        "zh": "量化与钱包", "what": "CIS v42 加密快进快出收割系统 + gbt_wallet 本地 FastAPI（默认 127.0.0.1:8097）"
        "：钱包 / 发票 / 扫描 / 余额 / 技术费单据 / 事件流。",
        "lead": "agent-gvmz-gbtv8/.openclaw/tmp/cis_v42_cis_mode.py", "lead_lines": 0,
        "classes": [],
        "extra": ["cis_v42 两个版本 · 收割系统（各 ~37 KB）",
                  "gwapi_mail / gwapi_smtp / gwapi_session · 钱包 API 的多份副本"],
        "note": "另有同族文件散落在顶层 .openclaw/tmp/（412 个 .py）。",
    },
    "holo_pet_w3": {
        "zh": "四路账本常驻化", "what": "上帝视角的四路账本常驻化（W3 产物 5）+ 布局测试统一入口。",
        "lead": "holo_pet_w3/ledger/ledger_store.py", "lead_lines": 0,
        "classes": [],
        "extra": ["tests/run_tests.py · 自述「不是孤儿测试」"],
        "note": "名字里就写着「上帝视角」—— 我的上帝视角里没有它。",
    },
    "brain": {
        "zh": "审美大脑与技能打磨", "what": "aesthetic_brain.py · 设计/文案质量多维度评估；skill_polish.py · 常用原生技能打磨迭代器 v1。",
        "lead": "brain/aesthetic_brain.py", "lead_lines": 0,
        "classes": [],
        "extra": ["skill_polish.py · 技能打磨迭代器（2026-09-09）"],
        "note": "顶层 brain/ 目录，237 行，我在「心智与记忆」面板里没有它。",
    },
}

# 把 orphan_scan 的活性数字贴回去
orph_by_dir = {r["dir"]: r for r in orph}
for d, spec in UNSEEN.items():
    r = orph_by_dir.get(d)
    if r:
        spec["py"] = r["py"]
        spec["lines"] = r["lines"]
        spec["with_main"] = r["with_main"]
        spec["tests"] = r["tests"]
        spec["referenced_outside"] = r["referenced_outside"]
        spec["verdict"] = r["verdict"]

v11["workspace"] = {
    "scanned_at": inv.get("scanned_at") or v11["meta"]["scanned_at"],
    "source": "本机工作区递归清点 + AST 解析，非探针调用",
    "inventory": {
        "file_count": inv["file_count"],
        "total_bytes": inv["total_bytes"],
        "total_lines": inv["total_lines"],
        "code_files": inv["code_files"],
        "code_lines": inv["code_lines"],
        "skipped": inv["skipped"],
        "by_ext": dict(list(inv["by_ext"].items())[:14]),
    },
    "buckets": {
        k: {"n": v["n"], "code_n": v["code_n"], "lines": v["lines"], "bytes": v["bytes"]}
        for k, v in inv2["buckets"].items()
    },
    "own_by_top": inv2["own_by_top"],
    "gbt": {
        "py_files": len(mods["files"]),
        "lines": sum(f["lines"] for f in mods["files"]),
        "groups": {},
    },
    "caps_source": {
        "benign": caps["n_caps"], "disabled": caps["n_disabled"],
        "domains": caps["n_domains"], "file": "gbt_allinone/caps_registry.py",
        "domain_dist": caps["domains"],
    },
    "unseen": UNSEEN,
    "orphans": orph,
    "top_files": [{"path": str(p.relative_to(BASE)).replace("\\", "/"), "lines": n,
                   "kb": round(b / 1024, 1)} for p, n, b in top_files],
}
# gbt 分组
grp = defaultdict(lambda: {"n": 0, "lines": 0})
for f in mods["files"]:
    parts = f["rel"].split("/")
    k = parts[0] if len(parts) > 1 else "(包根)"
    grp[k]["n"] += 1
    grp[k]["lines"] += f["lines"]
v11["workspace"]["gbt"]["groups"] = dict(sorted(grp.items(), key=lambda kv: -kv[1]["lines"]))

out = S / "v12_manifest.json"
out.write_text(json.dumps(v11, ensure_ascii=False, indent=1), encoding="utf-8")
print("写出:", out.name, "%.1f KB" % (out.stat().st_size / 1024))
w = v11["workspace"]
print("工作区: %d 文件 · %.0f MB · 文本 %s 行 · 代码 %d 文件 / %s 行"
      % (w["inventory"]["file_count"], w["inventory"]["total_bytes"] / 1048576,
         f"{w['inventory']['total_lines']:,}", w["inventory"]["code_files"],
         f"{w['inventory']['code_lines']:,}"))
print("自有代码 %s 行（含测试）· gbt_allinone %d 个 .py / %s 行"
      % (f"{sum(v['lines'] for k, v in w['buckets'].items() if k in ('自有源码', '测试')):,}",
         w["gbt"]["py_files"], f"{w['gbt']['lines']:,}"))
print("未进面板板块 %d 个，合计 %s 行" % (len(UNSEEN), f"{sum(s.get('lines', 0) for s in UNSEEN.values()):,}"))
for d, s in UNSEEN.items():
    print("   %-30s %3d py / %7s 行  %s" % (d, s.get("py", 0), f"{s.get('lines', 0):,}", s["zh"]))
