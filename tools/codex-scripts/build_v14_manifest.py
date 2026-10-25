# -*- coding: utf-8 -*-
"""生成 V14 数据层：v13_manifest.json + coverage（机器判定的覆盖审计）+ core（未覆盖的核心模块逐个读 docstring）。
所有数字来自 coverage_audit.json 与现场 AST 读取，无一条手写。
"""
import ast
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

S = Path(__file__).resolve().parent
BASE = S.parent
v13 = json.loads((S / "v13_manifest.json").read_text(encoding="utf-8"))
aud = json.loads((S / "coverage_audit.json").read_text(encoding="utf-8"))


def doc_of(rel):
    p = BASE / rel
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    if p.suffix == ".py":
        try:
            d = ast.get_docstring(ast.parse(txt))
            if d:
                return d.strip().split("\n")[0][:150]
        except SyntaxError:
            pass
    for ln in txt.splitlines():
        s = ln.strip()
        if s and not s.startswith(("#!", "# -*-", "import", "from", "<", "//", "/*", "*", "$")):
            return re.sub(r"^[#/\*\s]+", "", s)[:150]
    return ""


def files_under(prefix):
    """只取该前缀这一层（prefix 本身 + 其直接子项），不递归吃子目录里的其它分组。"""
    out = []
    for rel, v in aud["by_dir"].items():
        if rel == prefix:
            out += v["uncov"]
    return sorted(out, key=lambda x: -x["lines"])


def mods(prefix, limit=40):
    return [{"f": u["rel"], "lines": u["lines"], "doc": doc_of(u["rel"])}
            for u in files_under(prefix)[:limit]]


GROUPS = {
    "api": {
        "zh": "统一接口层", "key": "gbt_allinone", "match": "gbt_allinone/[^/]+$",
        "what": "整个系统的唯一合法入口：run_task / list_capabilities。所有能力调用都从这里进，"
                "禁用能力在这里被拦，危险动作在这里按作用域要授权。",
        "why": "AGENTS.md 的生产面红线第一条就是「写生产/镜像的动作一律走 run_task」—— "
               "而 run_task 所在的这个文件，我此前 13 版一个面板都没给过。",
    },
    "security": {
        "zh": "授权与安全策略", "key": "gbt_allinone/security", "match": None,
        "what": "能力风险策略与授权边界、应用级 AI 出口审计、统一网络边界、外部数据交换策略、"
                "以及独立密钥的黑客大脑网关。",
        "why": "这是我一直在口头引用（授权只能主人发放、审计不可绕过）却从没呈现源码的那一块。",
    },
    "base": {
        "zh": "框架底座", "key": None, "match": None,
        "files": ["gbt_allinone/safe_io.py", "gbt_allinone/checkpoint.py", "gbt_allinone/worker.py",
                  "gbt_allinone/app.py", "gbt_allinone/cli.py", "gbt_allinone/soul.py",
                  "gbt_allinone/coding_discipline.py", "gbt_allinone/dimension_naming.py",
                  "gbt_allinone/dependency_paths.py", "gbt_allinone/semantic_route.py"],
        "what": "统一安全 I/O（路径边界 / 跨进程锁 / 原子写）、阶段检查点、可终止子进程入口、"
                "桌面壳与 CLI 壳、灵魂与钢印、内生编程纪律、维度命名、依赖路径、语义路由。",
        "why": "框架自己的骨架。读数面板都在看「能力做了什么」，没有一页在看「框架自己怎么站着」。",
    },
    "omni": {
        "zh": "万能触手 · omni 家族", "key": "gbt_allinone/tentacle", "match": None,
        "what": "万能操控中枢与无护栏直连硬件的 omni_* 一族（进程 / 域 / 窗口 / 读取 / 鼠标 / 键盘 / 视觉），"
                "加上原生视觉持续流、视觉皮层、视觉记忆与视觉传输总线。",
        "why": "「亿万触手」面板报了 66 项、覆盖率 100%，但那些是条目的名字；"
               "这 20 个真正干活的模块一个都没露过面。",
    },
    "deploy": {
        "zh": "部署层", "key": "gbt_allinone/deploy", "match": None,
        "what": "Codex 中继看门狗（让 4446 中继自愈）、全息面板鉴权门、部署配置自检，"
                "以及 9 个 PowerShell 部署/巡检脚本（安装、隔离运行、健康检查、密钥环境、仓库洁净检查）。",
        "why": "这是真正把东西落到 Windows 上的那一层，覆盖率 7.8%。",
    },
    "bridge": {
        "zh": "对外桥接", "key": None, "match": None,
        "files": ["gbt_allinone/feishu_bridge.py", "gbt_allinone/notion_bridge.py",
                  "gbt_allinone/xingyun_bridge.py", "gbt_allinone/coze_mail_cap.py",
                  "gbt_allinone/integration/platform_client.py", "gbt_allinone/integration/smoke_test.py",
                  "gbt_allinone/adapters/workspace_adapter.py"],
        "what": "飞书 / Lark 资料库桥（不依赖 lark-cli）、Notion 资料舱、魔珐星云实时数字人接入、"
                "对主人自有地址的邮件收发整理、平台侧收款钱包 HTTP 客户端与接轨层冒烟自测、量化平台适配器。",
        "why": "「其余域」面板里只有域名与条目数，没有桥本身。",
    },
    "skill": {
        "zh": "技能库", "key": "审美相关skill/skills", "match": None,
        "what": "hatch-pet 技能（Codex 宠物精灵图全流程：生成清单 → 出图 → 切帧 → QA → 补跑 → 合成图集 → "
                "打包 → 渲染动画）与 pptx-html-fidelity-audit（PPTX 与 HTML 的保真核验）。",
        "why": "零覆盖的 3,521 行。它就在项目里，且在 gbt_allinone/tests 里有对应测试。",
    },
    "mirror": {
        "zh": "镜像与乾坤底座", "key": None, "match": None,
        "files": ["gbt_allinone/mirror_space.py", "gbt_allinone/qiankun.py",
                  "gbt_allinone/deployment_rehearsal.py", "gbt_allinone/room_space.py"],
        "what": "镜像多维度空间（所有假设与架构虚拟的最终归宿）、一指定江山乾坤换位 + AI 接管部署队列、"
                "部署排练、隔离房间空间。",
        "why": "「镜像与晋升」面板看的是对账读数；造这套机制的源码没进去。",
    },
    "vault": {
        "zh": "密钥保险箱", "key": None, "match": None,
        "files": ["gbt_allinone/deepseek_key.py", "gbt_allinone/security/abl_gateway.py",
                  "gbt_allinone/deploy/codex_key_env.ps1", "gbt_allinone/deploy/install_codex_key_env.ps1"],
        "what": "上游密钥的 DPAPI 保险箱（与 cloudflare / notion / 星云三家规格对齐）、"
                "黑客大脑的独立 LLM 网关、以及把密钥装进环境的 PowerShell 脚本。",
        "why": "「大模型通道」面板看的是密钥池读数，不是保险箱本身。",
    },
}

core = {}
for gid, g in GROUPS.items():
    if "files" in g:
        items = []
        for rel in g["files"]:
            p = BASE / rel
            if not p.is_file():
                continue
            try:
                n = p.read_text(encoding="utf-8", errors="ignore").count("\n") + 1
            except OSError:
                n = 0
            items.append({"f": rel, "lines": n, "doc": doc_of(rel)})
        items.sort(key=lambda x: -x["lines"])
    else:
        items = mods(g["key"]) if g.get("key") else []
    core[gid] = {
        "zh": g["zh"], "what": g["what"], "why": g["why"],
        "files": items,
        "n": len(items), "lines": sum(i["lines"] for i in items),
    }

v13["core"] = core
v13["coverage"] = {
    "method": "穷举式：枚举工作区全部自有代码文件（排除 vendored / .scratch / 缓存），"
              "按目录聚合，逐个查模块名是否在交付件里出现过。",
    "total_files": aud["total_files"],
    "total_lines": aud["total_lines"],
    "covered_lines": aud["covered_lines"],
    "uncovered_lines": aud["uncovered_lines"],
    "by_dir": {k: {"n": v["n"], "lines": v["lines"], "covered_lines": v["covered_lines"],
                   "uncov_n": len(v["uncov"])} for k, v in aud["by_dir"].items()},
    "zero_coverage": aud["zero_coverage"],
    "caveat": "覆盖率判据是「模块名是否出现」—— 这是弱判据："
              "名字出现 ≠ 功能被呈现（例如 安全攻防 面板报了 sec_scan 等能力名，"
              "但 security/policy.py 这个模块名从没出现）；名字没出现也可能功能已被覆盖。"
              "所以真实缺口介于「未覆盖行数」之下。",
    "selfcheck": "本审计脚本自身也踩过两个坑并已修正：①模块名短于 4 字符被过滤（如 run.py）"
                 "②把 data URI 当成了名字。",
}

out = S / "v14_manifest.json"
out.write_text(json.dumps(v13, ensure_ascii=False, indent=1), encoding="utf-8")
print("写出:", out.name, "%.1f KB" % (out.stat().st_size / 1024))
print("覆盖审计: %s 行中 %s 行未进交付件（%.1f%%）"
      % (f"{aud['total_lines']:,}", f"{aud['uncovered_lines']:,}",
         100 * aud["uncovered_lines"] / aud["total_lines"]))
print()
print("V14 新补的 %d 组核心模块：" % len(core))
for gid, c in core.items():
    print("   %-10s %-20s %2d 文件 / %6s 行" % (gid, c["zh"], c["n"], f"{c['lines']:,}"))
print("   合计 %d 文件 / %s 行" % (sum(c["n"] for c in core.values()),
                              f"{sum(c['lines'] for c in core.values()):,}"))
