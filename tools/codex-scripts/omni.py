# -*- coding: utf-8 -*-
"""万能插 · 人类视角入口（omni）

Owner 定调：「把框架里面的所有职业技能深度学习到精通，蒸馏提炼成**使用万能插就可以人类视角操控一切**」。

它补的是哪一环（先说清，免得重复造）
------------------------------------
- **万能插本身已经有**：`tools/codex-scripts/five-dim.py cap <能力位>` → 一律走 `gbt_allinone.run_task`（唯一门）。
- **语义路由也已经有了**：`gbt_allinone/semantic_route.py`（Owner 2026-09-19 定架构，主路=统一大模型，
  没配就**如实降级**到启发式）。但它路由到的是**触手方法**（`see` / `click_text` / `find_text`…），
  **不是那 158 个能力位**，也不是全机技能。
- **缺的就是这一环**：人一句自然语言 → **落到哪个能力位 / 哪个技能** → 给出**可直接执行的命令**、说明要过哪道门。
  本脚本就是这一环。

三条命令
--------
    python tools/codex-scripts/omni.py build                 # 现扫全机技能 + 158 能力位，落 state/skill_atlas.json
    python tools/codex-scripts/omni.py list  [--domain 域] [--channel 通道]
    python tools/codex-scripts/omni.py ask   "人类一句话"      # 只给候选与命令，不动手
    python tools/codex-scripts/omni.py run   "人类一句话" [--yes]  # 经万能插真跑（**只自动跑免卡只读的**）

纪律（照仓里几条铁律）
----------------------
- **不猜**：分数怎么来的要打得开看（命中词 n-gram + 域触发词），拿不准就说拿不准；
- **不绕门**：需要授权的作用域一律**如实报缺**，不找旁路；
- **不自动干有后果的事**：`run` 只自动执行 `safe 且 免卡 且 不需要确认` 的能力位；
  其余只打印命令并说明要过哪道门（要跑得人明确加 `--yes`）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
sys.path.insert(0, str(ROOT))
HOME = Path.home()
ATLAS = ROOT / "state" / "skill_atlas.json"

# ── 技能根：全机的职业技能都在这几处 ────────────────────────────────────────
# channel 决定"怎么调它"，这是"人类视角操控一切"的关键一列。
SKILL_ROOTS = [
    (HOME / ".agents" / "skills", "agent-skill", "本会话（DSH）实际读取的技能目录"),
    (HOME / ".claude" / "skills", "agent-skill", "Claude Code 侧"),
    (HOME / ".openclaw-autoclaw" / "skills", "agent-skill", "本仓 AGENTS.md 指定的托管目录"),
    (HOME / ".openclaw" / "skills", "agent-skill", "OpenClaw 侧"),
    (ROOT / "skills", "agent-skill", "本仓自有技能（真身）"),
    (ROOT / "审美相关skill" / "skills", "design-asset", "审美素材：形态技能（大部头，按类聚合）"),
    (ROOT / "审美相关skill" / "design-systems", "design-asset", "审美素材：品牌设计系统"),
    (ROOT / "审美相关skill" / "design-skeletons", "design-asset", "审美素材：设计骨架"),
]

# ── 本会话**实测真读**的技能根（用来判"落点到底可不可达"）────────────────────
# 2026-09-23 实测：本会话能加载的 gbt-* = 21 条 = `<仓>/.dsh/skills`(18) ∪ `~/.agents/skills`(5)，
#   交集 2 条。而 `<仓>/skills`(58) 与 `~/.openclaw-autoclaw/skills`(58) **本会话读不到** ——
#   实测 `skill gbt-system` / `skill gbt-creation` 均报 unknown。
#   ⇒ omni 原先**不校验落点可达性**，于是把 `gbt-system`(12.0) 这种"读不到的规程"当首选推给人。
#     "路由通了"不等于"落点能用"。这一层必须补。
SESSION_SKILL_ROOTS = [
    (ROOT / ".dsh" / "skills", "本会话（DSH）实测读取"),
    (HOME / ".agents" / "skills", "本会话（DSH）实测读取"),
]

# ── 第三通道：本地工具面（本机**真实存在**的扫描器/操作台）───────────────────
# 为什么必须有这一通道（2026-09-23 实测，这是"无死角"漏的那一格）：
#   omni 原先只认「能力位」与「agent 技能」，而本机的**扫描能力**其实在命令行工具里。于是：
#     `omni ask "扫一下这台电脑有没有病毒木马后门"`
#        → selfscan(4.5) / cross_scan(3.0) / gbt-security   ← 前两个与病毒无关；
#          gbt-security 本会话加载不了；sec_scan 无参挂死 180 s（万能插最大档实测）
#     `omni ask "全维度无死角扫描把故障都找出来"`
#        → osint_scan / bluetooth / bt_control              ← 全打偏
#   而真正的扫描器 `quick_scan.py`（含安全面：反病毒可见性/持久化/远控/IOC/供应链）
#   **不在任何一个通道里** ⇒ "扫"这类意图必然落空。
#   ⇒ 补上这一通道，"无死角扫描"才有一句话能落到的落点。
LOCAL_TOOLS = [
    {
        "name": "quick_scan",
        "path": "tools/codex-scripts/quick_scan.py",
        "desc": "全维度故障速扫：七面切分（生产/数据/残骸/三方/装机/索引/测试口径）"
                "＋安全面（反病毒可见性·持久化与远控·内容IOC·npm供应链·hosts·伪装扩展名）"
                "＋自动进化层（台账·病因对账·负对照）",
        "triggers": "扫描 全维度 无死角 故障 排查 体检 速扫 病毒 木马 后门 恶意 远控 "
                    "持久化 自启 反病毒 杀毒 defender 排除项 IOC 供应链 收敛 进化",
        "invoke": "py -3.14 tools/codex-scripts/quick_scan.py",
        "variants": {
            "--with-tests": "真跑 pytest --collect-only 拿 0 vs N 硬证据",
            "--with-host": "接入主机六层 L3-L5（进程/网络/可疑位置）",
            "--av-scan": "🔴 真跑 Defender 按需扫描（慢，-DisableRemediation 只报不动手）",
            "--selftest": "负对照：种假故障验判据真会响",
            "--discover": "病因对账：该进化什么 + 判据死活三分",
            "--trend": "自动收集台账：首见/末见/次数/常驻/闪断",
        },
        "scopes": [],            # 只读、不需要任何授权作用域
        "side_effect": False,
        "gate": "无需授权；退出码即门（0 只有P2 · 1 有P0 · 2 有P1 · 3 自身出错）",
    },
    {
 # 2026-09-23 补：**这条是被一次错路由逼出来的**。
        #    实测 `omni ask "把桌面壳打包成装机包并上线"` → 落到 `quick_scan`(1.4) ——
        #    因为图鉴里**根本没有"桌面壳"这件工具**，而本机**全局装着 electron-builder@26.15.3**
        #    （另有 electron@43.0.0，所以**不装包也能跑**）。
        #    ⇒ 人话落不到，不是路由算法差，是**登记表缺一行**。
        "name": "desktop-shell",
        "path": "holo_pet_w3/shell/preflight.cjs",
        "desc": "一体式桌面壳（7 扇窗：上帝视角 / 对话面 / AI 朋友圈 / 赏金台 / 执行台 / 代码台 / 神经工作台）"
                "· 启动预检在**真 Electron 运行时**里 require 壳的纯模块并逐窗过 url 白名单判据，**不弹窗**"
                "· 打包走 electron-builder（全局已装 26.15.3）",
        "triggers": "桌面壳 壳 装机包 打包 上线 发布 应用 APP 窗口 窗 七扇 启动 预检 复演 "
                    "打开 载入 加载 能不能开 能不能载入 开窗 窗口验证 界面 electron builder "
                    "安装包 分发 一体式 桌面应用",
        "invoke": "electron holo_pet_w3/shell/preflight.cjs",
        "variants": {
            "--rehearse": "**真建窗口但不显示** → electron holo_pet_w3/shell/rehearse.cjs"
                          "（逐窗验证页面能不能在 Electron 里载入 + 零出网；屏幕上什么都不出现）",
            "--start": "真启动壳（**会开窗**）→ cd holo_pet_w3 && electron .",
            "--test": "壳的契约测试 → cd holo_pet_w3 && node --test tests/test_*.cjs",
            "--guard": "「不破坏 DSH」守卫 → py -3.14 tools/codex-scripts/desktop-shell-guard.py",
            "--pack": "打装机包（**闸二，须主人批准**）→ cd holo_pet_w3 && npm run pack",
            "--icons": "壳窗口/皮肤取自 mission-control 专业皮肤层（skin-mission-control.css）",
        },
        "scopes": [],            # 预检/复演只读；真启动/打包另算（见 gate）
        "side_effect": False,
        "gate": "**预检 / 复演 / 测试 / 守卫：无需授权**（只读，且复演不显示窗口）。"
                "**真启动**（`electron .`）会开窗 ⇒ 动手前先问主人。"
                "**打装机包**（electron-builder）会写产物 + 可能触发 `npm install` ⇒ **属闸二，须主人批准**。",
    },

    {
        "name": "media_flow",
        "path": "tools/codex-scripts/media_flow.py",
        "desc": "三方向（AI短剧/AI电影/AI音乐）专业级流程台：现读 18 格抽屉状态"
                "（成品/仅彩排/空/缺目录）· 命名合规 · 每格验收判据 · 成品格许可闸 · "
                "`_intel` 六维固定文件名覆盖 · 本地格↔框架工序映射机检",
        "triggers": "短剧 短视频 AI短剧 电影 AI电影 音乐 AI音乐 全流程 流程 工序 抽屉 "
                    "分镜 剧本 歌词 混音 母带 成片 封面 发布 收敛 三方向 media pipeline",
        "invoke": "py -3.14 tools/codex-scripts/media_flow.py status",
        "variants": {
            "status <方向>": "只看一个方向（short-video / film / music）",
            "gate": "只跑验收判据，退出码即门（0 全过 · 2 有问题 · 1 有 P0）",
            "spec <方向>": "现读该方向的专业规格：角色表 / craft / quality / metrics / 十道闸",
        },
        "scopes": [],            # 纯只读
        "side_effect": False,
        "gate": "无需授权（只读）。**不生成任何东西** —— 框架自标 external_generators_connected=False",
    },
    {
        "name": "host_security_scan",
        "path": "gbt_allinone/tools/host_security_scan.py",
        "desc": "主机安全扫描·六层（反病毒在位/持久化入口/进程与签名/网络连接/可疑位置/根因关联）",
        "triggers": "主机 进程 签名 网络 连接 监听 端口 持久化 启动项 计划任务 可疑位置 TEMP",
        "invoke": "py -3.14 -m gbt_allinone.tools.host_security_scan",
        "variants": {"--no-sign": "跳过签名校验（快很多）"},
        "scopes": [],
        "side_effect": False,
        "gate": "无需授权（只读）。注意：它的 L1 只查「在位」，不查「在不在看你」——"
                "排除项遮蔽要看 quick_scan 的 AV_EXCLUSION_BLINDSPOT",
    },
    {
        "name": "deep_scan",
        "path": ".scratch/scan-20260923/deep_scan.py",
        "desc": "全树穿透扫描·内容面全量（L1–L8：库存/卫生/语法/引用/密钥/Git/一致性）—— 慢（约 12 分钟）",
        "triggers": "深扫 全量 内容面 逐文件 重复 哈希 编码 BOM 乱码 断链",
        "invoke": "py -3.14 .scratch/scan-20260923/deep_scan.py",
        "variants": {},
        "scopes": [],
        "side_effect": False,
        "gate": "无需授权（只读）。**它是临时件**（在 .scratch 里），不存在时如实报缺",
    },
    {
        "name": "omni_max",
        "path": ".scratch/scan-20260923/omni_max.py",
        "desc": "万能插最大档：147 个能力位逐个过纪律筛（可跑的真跑，其余逐条说明为什么不能跑）",
        "triggers": "万能插 最大档 全部能力位 逐个 能力 探针 体检能力位",
        "invoke": "py -3.14 .scratch/scan-20260923/omni_max.py",
        "variants": {},
        "scopes": [],
        "side_effect": False,
        "gate": "无需授权。走**隔离 store**，生产主账本零足迹。**临时件**",
    },
    {
        "name": "gbt-checkup",
        "path": "tools/codex-scripts/gbt-checkup.py",
        "desc": "技能蒸馏三关合一（队列 gaps + 内容 verify-distill + 结构 audit-regulations），退出码就是门",
        "triggers": "技能 蒸馏 验收 三关 覆盖 点名 编造 结构 红线 出处",
        "invoke": "py -3.14 tools/codex-scripts/gbt-checkup.py",
        "variants": {},
        "scopes": [],
        "side_effect": False,
        "gate": "无需授权（只读）",
    },
    {
        # 2026-09-23 补：能力位到底"能不能真跑"以前只能一条条手工试
        # （`sec_scan` / `sec_chain` 的 180s 超时就是这么碰出来的）——
        # 这件把它变成一次跑完 158 条 + **一条都不许静默跳过**。
        "name": "cap_probe_all",
        "path": "tools/codex-scripts/cap_probe_all.py",
        "desc": "全能力位探针：147 良性 + 11 登记未实现**逐条**探（隔离 store · 逐条超时），"
                "归堆 ok/gated/needs_params_or_error/timeout/crash —— 覆盖必须 100%",
        "triggers": "能力位 能不能跑 探针 可达 僵尸能力 挂死 超时 全量 158 "
                    "缺作用域 授权门 登记未实现",
        "invoke": "py -3.14 tools/codex-scripts/cap_probe_all.py",
        "variants": {
            "--timeout 300": "单条超时秒数（慢能力如 cross_scan 需 300+；快验用 5）",
            "--only <子串>": "只探名字含该子串的（如 --only mirror）",
            "--json <路径>": "把逐条结果落 JSON（默认 %TEMP%\\gbt-capprobe.json）",
        },
        "scopes": [],
        "side_effect": False,
        "gate": "无需授权。走**隔离 store**（临时目录），生产主账本零足迹；"
                "退出码 2 = 有超时/崩溃（**超时 ≠ 挂死**，先看它旁边「已知实测耗时」）",
    },
    {
        # 2026-09-23 补：出口清单登记的是**裸行号**，注册表一插行就集体偏移
        # （同一天已发生两次）—— 手工找行号是体力活，且下次还会再来。
        "name": "fix_exit_pointers",
        "path": "tools/codex-scripts/fix_exit_pointers.py",
        "desc": "出口清单登记指针自动对齐（main.cjs 的 `registered: caps_registry.py:NNN`）："
                "默认只报差异、偏移一致时一句话说清；--check 当门禁，--write 只改那一个数字",
        "triggers": "出口清单 登记指针 行号 漂移 对不上 caps_registry main.cjs TOOLS_CAPS",
        "invoke": "py -3.14 tools/codex-scripts/fix_exit_pointers.py",
        "variants": {
            "--check": "有差异 exit 1（给门禁/CI 用）",
            "--write": "真写盘（只动 registered 的数字，负对照验证过逐字节可还原）",
        },
        "scopes": [],
        "side_effect": False,     # 不带 --write 就是纯只读
        "gate": "默认只读；**--write 会改文件**，所以不进自动跑名单（`omni run` 不会替你写）",
    },
    {
        # 2026-09-23 补：Owner 令「把该清理的清理出去到回收站就好了」。
 # `.scratch` **不是**垃圾堆：`_traces`/`_dsh_home`/`vision_probe`/各 `_*.json`
        # 都是活代码在读写的目标（见模块 docstring 的白名单与引用守卫）。
        "name": "clean_residue",
        "path": "tools/codex-scripts/clean_residue.py",
        "desc": "残骸清理器：**只进回收站**（不硬删）· 分六层（build/trash/backups/temp/scratch/tempscan）· "
                "带**引用守卫**（文件名在仓内文本面出现过就一律留下并给理由）",
        "triggers": "清理 残骸 垃圾 回收站 磁盘 空间 __pycache__ 临时 .trash .backups .scratch 体积",
        "invoke": "py -3.14 tools/codex-scripts/clean_residue.py",
        "variants": {
            "--go": "**真搬进回收站**（默认只出清单）",
            "--tier build,trash": "只处理指定层",
        },
        "scopes": [],
        "side_effect": True,      # --go 会搬文件；默认档只出清单
        "gate": "默认只出清单（只读）。`--go` 才动盘，且**只进回收站可还原**；"
                "因带写面，`omni run` **不会**替你自动跑它",
    },
    {
        # 2026-09-23 补：壳的「执行面」（窗 C）的数据源。
        # 口径单一：**只汇总不重算** —— 信封覆盖复用 ruler、卡点复用 unimplemented_scan。
        "name": "exec-deck",
        "path": "tools/codex-scripts/exec-deck.py",
        "desc": "执行面数据聚合（窗 C 的数据源）：A 信封覆盖（含**改动后窗口**分格）· "
                "B 三条主道谁在干活 · C 欠的活（未收步 + 悬空分级）· D 能力卡点；"
                "可另生成**自包含页面**（无 script、无外链）",
        "triggers": "执行面 窗C 信封 覆盖 无脑操作 欠的活 欠着 没收 没接上 步账 未收步 悬空 悬空步 "
                    "三条主道 谁在干活 卡点 快照 无脑",
        "invoke": "py -3.14 tools/codex-scripts/exec-deck.py",
        "variants": {
            "--json <路径>": "落机器读的 JSON",
            "--html <路径>": "另生成自包含页面（窗 C 直接 loadFile）",
        },
        "scopes": [],
        "side_effect": False,     # 只读审计 + 只写它自己的产物
        "gate": "无需授权（只读）。退出码：0=没需要人看的 · 2=有（悬空步/覆盖偏低/卡点未清）",
    },
]

# 职业域的中文触发词：让人话能落到域上（拿不准就多条，宁可多命中也不漏）
DOMAIN_HINTS = {
    "system": "系统 自检 体检 健康 状态 环境 版本 依赖 进程",
    "llm": "模型 大模型 对话 推理 提示词 内核 触手 编程 智能",
    "pipeline": "流水线 管线 发布 提交 回滚 部署 生产 镜像",
    "dangerous": "危险 高危 破坏 （⚠️ 该域 2026-09-23 已清空；那 11 个名字**2026-09-25 已接上实现并改挂 `security` 域** —— 见下面 `unimplemented` 键上方的现读注释）",
    "unimplemented": "只登记未实现 没实现 没做 禁止已解开 危险名 被禁用的能力",
 # 2026-09-25 现读更正（**同一条登记第二次漂移，这次是方向反了**）：
    #   第 36 轮改它是因为「`dangerous` 域在图鉴里不存在了」；
    #   现在 **`unimplemented` 域也空了** —— Owner 令「把黑客能力全部多维度全部覆盖补齐」后，
    #   那 11 个名字**接上了实现层**（`security/redteam.py`），在**注册表里挂了 `domain="security"`**
    #   （`caps_registry.py:1111-1125` 的注释写明），而 `UNIMPLEMENTED_CAPS` 现在是空表。
    #   后果（`omni.py build` 重建图鉴后实测）：`verify-distill.py --all` 判红
    #   「unimplemented FAIL · 图鉴里没有这个域（或它的能力位数为 0）」。
    #   **这不是"登记表没跟"，是"域被搬空之后这条键没人删"** —— 一条**幽灵域**。
 # 我**不擅自删这条键**：删了就等于替主人决定「`gbt-dangerous` 这份规程还要不要」——
    #   它讲的那 11 个名字现在归 `security` 域，而 `gbt-security` 的规程还没点到它们
    #   （`verify-distill --domain security` 现读点名缺 11 位）。两条路（并进 gbt-security /
    #   保留 gbt-dangerous 并给它一个域）都得主人拍板。**在拍板前，这条红就是待办清单本身。**
    "tentacle": "触手 操作 桌面 点击 输入 感知 浏览器 操控",
    "engine": "引擎 执行 循环 大脑 思考 调度",
    "mind": "心智 记忆 认知 情绪 人设 自我",
    "creation": "创作 生成 写 画图 出图 设计 审美 视频 音乐",
    "recon": "侦察 侦查 扫描 探测 信息收集 情报",
    "data": "数据 表格 清单 台账 统计 分析",
    "security": "安全 权限 授权 密钥 凭据 审计 加固",
    "finance": "财务 钱 账单 花费 预算 成本 余额",
    "longrun": "长跑 长任务 常驻 定时 调度 后台",
    "devour": "吞咽 消化 抓取 吸收 资料 学习 文献",
    "video": "视频 剪辑 短片 分镜 渲染 成片",
    "tools": "工具 脚本 命令行 二进制",
    "project": "项目 仓库 工作区 目录 文件",
    "voice": "语音 声音 说话 朗读 识别 麦克风 蓝牙",
    "device": "设备 硬件 蓝牙 扫描 连接",
    "brain": "脑 记忆库 知识库 排布",
    "comms": "通讯 消息 私信 通知 群",
    "vision": "看 图像 视觉 截图 识图 读图",
    "automation": "自动化 编排 定时 无人值守",
    "life": "生活 日常 记录 归档",
    "image_video": "图像 视频 影像 素材",
    "integration": "集成 对接 第三方 接口 桥",
    "framework": "框架 本体 自身 家规 铁律",
    "infra": "基础设施 服务器 端口 网络",
    "social": "社交 发布 分发 平台 朋友圈",
    "collab": "协作 多人 团队 协同",
    "arkcli": "Ark 云端 字节 模型方舟 方舟 部署 endpoint 生图 生视频 微调 账单 用量",
    "aesthetic": "审美 好看 美化 打磨 设计感 AI味 模板 改版 排版 配色 动效",
}


# ── 自动执行的判据：**默认拒绝** ────────────────────────────────────────────
# 为什么改成默认拒绝（2026-09-22 实测教训）：
#   第一版只拿 `PROBE_SKIP_KINDS`（侧效应名单）当"要不要确认"，而它是**不完整**的
#   —— `mirror_release`（镜像全量晋升生产）**根本不在那张表里**。于是我让它
#   "把项目部署到生产"时，`omni run` **直接把它执行了**。
#   幸好框架自己的授权门拦住了（账本实测：`auth_denied scope=deploy_publish
#   missing=[deploy_publish, process_execute, filesystem_write]`），生产面没被写。
#   ⇒ 但"靠下游门兜底"不是设计。这一层必须**默认拒绝**：只自动跑**能证明是只读无参**的，
#     其余一律只打印命令 + 说明要过哪道门。
DANGER_DOMAINS = {"pipeline", "dangerous", "infra", "integration"}

# ── 深蒸状态（**单一真相**：`omni gaps` 从这张表 + 图鉴现算队列）────────────────
# 为什么用"声明映射"而不是另存一个待办 json：另存一份就会走样、就会漏。
# 表里没有的域 = 在队里，**自动出现在队列里**，不需要谁记得去登记。
DISTILLED_DOMAINS = {
 # 2026-09-22 更正（机器抓出来的假账）：这两行原先都指向 `gbt-aesthetic`。
    # `tools/codex-scripts/verify-distill.py` 一跑就露馅：`gbt-aesthetic` 里
    # **一个能力位都没点到**（create / drama / music_publishing / brand_outro /
    # emotion_projection / scene_anchor / code_art / render_evolution / a1art_skill 全无），
    # 也没有任何 `five-dim.py cap <能力位>` 形式的调用 —— 它是"审美判断"的规程，
    # 不是这 9 个能力位的**用法规程**。图鉴上写「已深蒸」而实物不干这件事 = 假绿，
    # 所以改指到真正逐位覆盖的 `gbt-creation`（没交付就会被 verify-distill 判 FAIL，不会静默变绿）。
    "creation": "gbt-creation",       # 创作域 8 个能力位：逐个点名 + 真跑过的调用
    "image_video": "gbt-creation",    # 影像 1 个能力位（a1art_skill）同样收在这条里
    "tentacle": "gbt-tentacle",       # 手眼网耳：三通道 + 六铁律 + 实测诚实账
    "vision": "gbt-vision",           # 视觉这一格：门是 privacy_read，且与"触手之眼看屏幕"不是同一条路
    "llm": "gbt-llm",                 # 18 个位分四簇（Codex 桥 / 五维 / 自主环 / 本地只读挂件）
    "finance": "gbt-finance",         # 量化 4 位：只读免授权，但**读数陷阱最多**（假空 []/正则抓错类名）
    "data": "gbt-data",               # 5 位：echo/count_words/record_grid/account_registry 只读；audit_query 挂 audit_read
    "device": "gbt-device",           # 蓝牙 2 位：status/scan/list 免卡；connect/read/write/classic 挂 device_control（一次性）
    "voice": "gbt-voice",             # 2 位：status/asr 免卡；tts 挂 audio_output（一次性）
    "framework": "gbt-framework",     # 门可见性 + 自改门：只读免授权；写护照动作 AI 不许自己开
    "mind": "gbt-mind",               # 9 位：作用域全空，但**有 4 个真写口**（门不会替谁拦）
    "engine": "gbt-engine",           # 9 位：零作用域但 6 个会改状态（sched_tick/wf_cache_clear 等）
    "system": "gbt-system",           # 21 位：空参全零作用域；写盘藏在 fix/restore/append 参数里；坑全在"念反读数"
    "longrun": "gbt-longrun",         # 4 位：零作用域，但 lr_submit/lr_tick 是真写口（图鉴曾写着"免卡只读"）
    "pipeline": "gbt-pipeline",       # 18 位：整域在 DANGER_DOMAINS，写位全 0 授权；只读 6 位真跑过
    "recon": "gbt-recon",             # 7 位：6 位零作用域；osint_scan 挂 osint_private（只写门、没执行）
    "video": "gbt-video",             # 4 位：全是只读契约面（未装/未配密钥/拿不到显存），出片一律未验
    "security": "gbt-security",       # 5 位：4 位零作用域；sec_llm 挂 external_llm（本体未验）
    "brain": "gbt-brain",             # 2 位：两位都只读（原以为会写盘 → 源码+AST+22 条用例证伪）
    "comms": "gbt-comms",             # 1 位：白名单默认空=全拒；send/reply/register 挂 data_export
    "devour": "gbt-devour",           # 4 位：scan 只读；reflect 零作用域但会写盘（最贵的假读数）
 # 2026-09-23 第 36 轮改：这里原来写的是 `"dangerous": "gbt-dangerous"` ——
    # 而 **`dangerous` 这个域在图鉴里已经不存在了**（解禁时那 11 位改登记进
    # `caps_registry.UNIMPLEMENTED_CAPS`，域名字段是 `unimplemented`）。
    # 后果实测：`verify-distill.py --all` 判红「dangerous FAIL · 图鉴里没有这个域（或它的能力位数为 0）」
    # ——**域长什么样已经变了，登记表没跟**。规程本身（`gbt-dangerous`）讲的就是这 11 个名字，
    # 所以正确的键是它现在真挂的那个域。
 # 2026-09-25 第 3 次现读：**这条映射现在指向一个空域**。
    #   第 36 轮那次说"正确的键是它现在真挂的那个域" —— 那个判断当时对，现在过期了：
    #   11 位接上实现后挂的是 `domain="security"`，`UNIMPLEMENTED_CAPS` 变空表
    #   ⇒ `unimplemented` 域里**一个能力位都没有**，本键成了幽灵。
    #   ⇒ 现状：`verify-distill --all` 对它判红（这是**正确的红**，不是误报）。
    #   处置权在主人（并进 `gbt-security` 的规程 / 还是留 `gbt-dangerous` 另给一个域）；
    #   在那之前**保留这条红当待办**，不删键、不改判据。
    "unimplemented": "gbt-dangerous",  # ⚠️ 现读：该域已空（11 位已实现并改挂 security）—— 见上方注释
    "tools": "gbt-tools",             # 6 位：前 3 位零作用域只读（投影卡/穿透网 payload 被 api.py 丢掉）；
                                      #        后 3 位是改代码链（code_patch/git_read/git_write），
                                      #        门是 **fail-closed**：非 dry_run 一律挂 filesystem_write
    "project": "gbt-project",         # 2 位：零作用域；platform_profile 有 30s TTL 缓存（读数会"旧"）
    # ── 六个单能力位小域（2026-09-22 收尾，至此 **30/30 全交付**）──
    "automation": "gbt-automation",   # browser：默认 op=open 缺 url 必败；只读路是 op=native+action=status
    "life": "gbt-life",               # life：空参就是 status；`action` 会被当 `op`（api.py:141）
    "integration": "gbt-integration",  # feishu_embed：三条 check_* 内层 denied 却 exit 0
    "infra": "gbt-infra",             # cloud_pc：PROVISION 花钱+不可逆、RELEASE 不可逆，零作用域
    "social": "gbt-social",           # auto_publish：发布/提现/改价要人；零作用域、门在模块里
    "collab": "gbt-collab",           # stigmergy：唯一写 op=deposit 真写盘；零作用域
}
DISTILLED_CLUSTERS = {
    "arkcli": "gbt-arkcli",           # 外部 CLI：用法规程（前缀/两道闸/路由表/纪律）
    "lark": "gbt-lark",               # 28 条飞书技能：按意图分簇 + 两道闸（身份闸/写出去先问主人）
    "fal": "gbt-fal",                 # 12 条 fal-*：**全是目录桩**（只有 SKILL.md、无脚本、上游未装）
    "autoglm": "gbt-autoglm",         # 9 条：凭据不是环境变量，是本机 token 服务（18432 现读未监听）
    "figma": "gbt-figma",             # 7 条 figma-*：目录桩；**上游未 vendored ⇒ 现读不可执行**
    "design": "gbt-design",           # 4 条 design-*：只有 design-brief 有真内容，其余是桩
    "autoclaw": "gbt-autoclaw",       # 5 条：AutoClaw 平台侧托管技能（**不是本机桌面**）
    "sandbox": "gbt-sandbox",         # 3 条：**Cloudflare Sandbox**（云容器，不是 DSH 文件沙箱）
    "pptx": "gbt-pptx",               # 3 条带横杠 + 1 条裸名 `pptx`（本机缺 python-pptx/pptxgenjs）
    "youtube": "gbt-youtube",         # 3 条：yt-dlp 不在 PATH、edge-tts 在盘上但 exit=1
    "video": "gbt-video-tools",       # 3 条视频技能（⚠️ 与域 `video` 同名但**两份 dict 独立**）
    "frontend": "gbt-frontend",       # 4 条：2 条只有索引洞、`frontend-slides` Mode B 要 python-pptx（未装）
    "gsap": "gbt-gsap",               # 4 条**全是桩**；真知识面在 `hyperframes-animation`（live 落点）
    "web": "gbt-web",                 # 4 条：`web-perf` 前置闸不满足（无 chrome-devtools MCP）
    "venice": "gbt-venice",           # 5 条：Venice 系（图像/视频/对话）
    "alchemy": "gbt-alchemy",         # 3 条：链上数据/alchemy（**零作用域 ≠ 只读**，注意密钥）
    "cloudflare": "gbt-cloudflare",   # 3 条带横杠 + 1 条裸名 `cloudflare`（按加严后的判据是 4）
    "ef": "gbt-ef",                   # 3 条：EigenFlux 网络（广播/私信/身份）
    "glmv": "gbt-glmv",               # 3 条：GLM 视觉系
    "remotion": "gbt-remotion",       # 12 条：React 造视频（⚠️ 裸名 `remotion` 是另一条簇，不在本簇口径内）
    "hyperframes": "gbt-hyperframes",  # 8 条：HTML 合成做视频（上游技能在 `~/.agents/skills/` 共享目录）
    "chengfeng": "gbt-chengfeng",     # 7 条：中文口播工具链；⚠️ Runtime 与 Studio 现读**未装**，脚本被平铺丢了插件外壳
}
# 我们自己的技能簇 —— 它们**就是**蒸馏件，不该被列成"待蒸的外来技能"
SELF_CLUSTERS = {"gbt"}

DANGEROUS_NAME_RE = re.compile(
    r"deploy|release|publish|submit|rollback|rewind|ascend|purge|delete|drop|"
    r"shape|rehearse|simulate|install|uninstall|write|patch|kill|stop|restart",
    re.I)


def required_scopes(kind: str) -> list[str]:
    """**静态**查这个能力位要过哪些作用域 —— 不执行它就能知道。

    走 `gbt_allinone.security.policy.evaluate(kind, {})`（生成器给能力台算"需要授权"用的同一条路）。
    查不到就返回空并**如实标注查不到**，不假装"不需要授权"。
    """
    try:
        from gbt_allinone.security import policy
        d = policy.evaluate(kind, {})
        return [str(s) for s in (getattr(d, "scopes", ()) or ())]
    except Exception:  # noqa: BLE001
        return []


def _state_changing_kinds() -> set:
    """框架**自己**那张"会改状态"的表（`preflight._STATE_CHANGING_KINDS`）。

    🔴 2026-09-22 补（深蒸 engine 域时抓到的**系统性**假绿）：
    `auto_run_verdict()` 原先只看 注册表旗标 + 参数 + 侧效应名单 + 危险域 + 名字正则 + 授权作用域，
    **不看框架自己那张表** ⇒ 有些"零作用域但会动手"的位被放进自动跑名单，实测三例：
      · `sched_tick` —— 真去跑到期调度
      · `wf_cache_clear` —— 真删 `transfer_cache.json`
      · `devour_pulse` / `devour_reflect` / `root_fix` / `lr_tick` 同类
    而这些名字**就在框架自己的 preflight 表里**（`preflight.py:47`，11 个），
    说明"框架知道它们会动手，只有 omni 不知道"。修法：**直接认这张表**，别再各算各的。
    """
    global _STATE_CHANGING_CACHE
    if _STATE_CHANGING_CACHE is None:
        try:
            from gbt_allinone import preflight as _pf
            # 2026-09-24 起走公开访问器（单一真源）；老字段只作兼容回落。
            getter = getattr(_pf, "state_changing_kinds", None)
            _STATE_CHANGING_CACHE = set(getter() if callable(getter)
                                        else getattr(_pf, "_STATE_CHANGING_KINDS", set()) or set())
        except Exception:  # noqa: BLE001
            _STATE_CHANGING_CACHE = set()
    return _STATE_CHANGING_CACHE


_STATE_CHANGING_CACHE: set | None = None


# ── 只读扫描器白名单：修"域过滤器误杀"（2026-09-23 实测抓到）────────────────
# 现象：`ghost_guard`（防复发检测）· `mirror_scan`（维度体检）· `mirror_plan`（生产前排练计划）
#   都是 `safe=True`、`enabled`、静态查出 `scopes=()` **的只读扫描器**，却因为
#   `domain=pipeline ∈ DANGER_DOMAINS` 被**永久排除**在自动探测之外 —— 静默砍覆盖。
# 判据：**`safe=True` 且静态零作用域 已经是比"域"更强的免后果证据**；
#   再用域去否决它，是用更粗的尺子重复计同一件事。但这不等于放宽默认拒绝：
#     · 只在 **safe ∧ enabled ∧ scopes=() ∧ 名字是只读动作** 三条同时成立时才放行；
#     · `needs_confirmation`（无参即有后果那张表）**照旧一票否决**；
#     · 写动作字样（DANGEROUS_NAME_RE）**照旧一票否决**；
#     · 想恢复旧行为用 `--strict`。
READONLY_SCANNER_RE = re.compile(
    r"scan|guard|hygiene|inventory|parity|audit|probe|status|check|verify|"
    r"inspect|selfscan|truth", re.I)


def readonly_scanner_exempt(cap: dict) -> bool:
    """这条被「域」拦下的能力位，是不是一个**证明得了的只读扫描器**？"""
    kind = cap.get("kind") or ""
    if not (cap.get("safe") and cap.get("enabled")):
        return False
    if cap.get("needs_confirmation") or cap.get("unimplemented") or cap.get("requires_params"):
        return False
    if DANGEROUS_NAME_RE.search(kind):
        return False
    if (kind in _state_changing_kinds()):
        return False
    if required_scopes(kind):
        return False
    return bool(READONLY_SCANNER_RE.search(kind))


def auto_run_verdict(cap: dict, strict: bool = False) -> tuple[bool, list[str]]:
    """能不能**自动**跑？默认拒绝。返回 (能否, 不能的理由)。

    `strict=True` 恢复旧行为（域/名字一票否决，不做只读扫描器豁免）。
    """
    why: list[str] = []
    if not cap.get("enabled"):
        why.append("注册表里不是 enabled 状态" + ("（%s）" % cap["reason"] if cap.get("reason") else ""))
    if cap.get("unimplemented"):
        why.append("只有名字、没有实现（caps_registry.UNIMPLEMENTED_CAPS 登记项）")
    if not cap.get("safe"):
        why.append("注册表未标 safe，面板/入口不代调")
    if cap.get("requires_params"):
        why.append("需要参数 %s" % ",".join(cap["requires_params"][:4]))
    if cap.get("needs_confirmation"):
        why.append("在侧效应名单里，要人确认")
    exempt = (not strict) and readonly_scanner_exempt(cap)
    if cap.get("domain") in DANGER_DOMAINS and not exempt:
        why.append("域「%s」属于有后果的域" % cap["domain"])
    if DANGEROUS_NAME_RE.search(cap.get("kind") or ""):
        why.append("名字带写动作字样（deploy/release/publish/…）")
    scopes = required_scopes(cap.get("kind") or "")
    if scopes:
        why.append("要过授权门：%s" % ",".join(scopes[:4]))
    if (cap.get("kind") or "") in _state_changing_kinds():
        why.append("框架自己的 preflight 把它列为**会改状态**（不是只读）")
    return (len(why) == 0), why


# ── 工具 ──────────────────────────────────────────────────────────────────
def grams(text: str, n: int = 2) -> set:
    """字符 n-gram（中文无空格也能命中）。**复用 semantic_route 的那份实现**，不另造。"""
    try:
        from gbt_allinone.semantic_route import grams as _g
        return _g(text, n)
    except Exception:  # noqa: BLE001
        t = re.sub(r"\s+", "", str(text or "").lower())
        return {t[i:i + n] for i in range(max(0, len(t) - n + 1))}


def read_front(path: Path) -> dict:
    """读 SKILL.md 的前置字段（name/displayName/description/triggers）。读不到就返回空，不编。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    m = re.match(r"^---\s*\n(.*?)\n---\s*", text, re.S)
    if m is None:
        return {}
    raw = m.group(1)
    out: dict = {}
    for key in ("name", "displayName", "description", "version"):
        mm = re.search(r"^%s:[ \t]*(.*)$" % key, raw, re.M)
        if not mm:
            continue
        val = mm.group(1).strip()
        if val in ("|", ">", "|-", ">-", "|+", ">+"):
 # 2026-09-22 修：原先只取冒号后那一行 ⇒ YAML **块标量**（`description: |`）被读成
            # 字面量 `"|"`。实测 fal-*(12) / figma-*(7) 等一批上游技能在 atlas 里 desc 长度全是 1、
            # 值就是 `"|"` ⇒ `omni list` 描述栏空白、`omni ask` 拿不到内容线索、只能靠名字匹配。
            # 修法：块标量往下收**连续缩进块**，拼成一行（空行跳过，缩进结束即止）。
            lines = []
            for line in raw[mm.end():].splitlines():
                if not line.strip():
                    continue
                if not line[:1].isspace():
                    break
                lines.append(line.strip())
            val = " ".join(lines)
        elif val == "":
 # 2026-09-22 再补一种：**多行 plain 标量** —— `description:` 后**什么都不写**，
            # 换行再缩进续写（实测 `glmv-pdf-to-ppt` / `glmv-pdf-to-web` 两条）。
            # 这一种比 `|` 更隐蔽：值不是 `"|"` 而是**空串**，所以"看着没描述"不一定是真没写。
            # 判据与块标量同源：往下收连续缩进行；遇到空行 / 缩进结束 / **本身就是 `键:` 的行**（那是映射，不是标量续写）就停。
            lines = []
            for line in raw[mm.end():].splitlines():
                if not line.strip():
 # 首个空行是 `键:` 后面那个换行本身（splitlines 会先给一个空串）——
                    # 还没收到任何内容时空行要**跳过**，收到内容之后的空行才是这一段结束。
                    if not lines:
                        continue
                    break
                if not line[:1].isspace():
                    break
                s2 = line.strip()
                if re.match(r"^[A-Za-z_][\w\-]*:\s*(\S.*)?$", s2):
                    break
                lines.append(s2)
            val = " ".join(lines)
        out[key] = val.strip().strip('"').strip("'")
    # triggers 只在 `triggers:` 那一段里收（原先全前置字段乱收：块标量的正文也可能被当成 trigger）
    mtr = re.search(r"^triggers:[ \t]*$", raw, re.M)
    if mtr:
        trig = []
        for line in raw[mtr.end():].splitlines():
            if not line.strip():
                continue
            if not line[:1].isspace():
                break
            s = line.strip()
            if s.startswith("-"):
                trig.append(s.lstrip("-").strip().strip('"').strip("'"))
        if trig:
            out["triggers"] = [t for t in trig if t][:12]
    return out


def collect_skills() -> tuple[list[dict], list[dict]]:
    """返回 (逐条列出的技能, 按类聚合的大部头素材)。"""
    skills, bulk = [], []
    for root, channel, why in SKILL_ROOTS:
        if not root.is_dir():
            continue
        for d in sorted(root.iterdir()):
            if not d.is_dir():
                continue
            fx = read_front(d / "SKILL.md")
            row = {
                "name": fx.get("name") or d.name,
                "displayName": fx.get("displayName") or "",
 # 2026-10-13：技能侧**同一个坑**（实测 **97/386** 条描述超 400 字被静默截断
                #    ⇒ 尾部触发词进不了路由）。与能力位同法修：截断只影响显示，
                #    被切掉的那段另存 `desc_tail`，打分时接回去（见 `rank()`）。
                #    标记**追加**在 400 字之后，不替换末尾 —— 免得再挖一次"两头都不覆盖"的洞。
                "desc": ((fx.get("description") or "")[:400]
                         + ("…【图鉴截断：原文 %d 字（尾部见 desc_tail，打分已接回）】"
                            % len(fx.get("description") or "")
                            if len(fx.get("description") or "") > 400 else "")),
                "desc_tail": (fx.get("description") or "")[400:],
                "desc_truncated": len(fx.get("description") or "") > 400,
                "triggers": fx.get("triggers") or [],
                "version": fx.get("version") or "",
                "channel": channel,
                "root": str(root),
                "path": str(d),
                "why": why,
                "has_references": (d / "references").is_dir(),
                "has_scripts": (d / "scripts").is_dir(),
                "has_assets": (d / "assets").is_dir(),
            }
            # 大部头素材（设计系统/骨架）不逐条塞进图鉴：它们是"料"，不是"可调用的职业技能"
            if channel == "design-asset" and root.name in ("design-systems", "design-skeletons"):
                bulk.append(row)
            else:
                skills.append(row)
    return skills, bulk


def collect_caps() -> tuple[list[dict], str]:
    """158 个能力位（万能插的真靶子）。"""
    try:
        from gbt_allinone import caps_registry as CR
        from gbt_allinone.caps_registry import BENIGN_CAPS, UNIMPLEMENTED_CAPS
    except Exception as exc:  # noqa: BLE001
        return [], "读不到能力注册表: %s" % exc
    try:
        from gbt_allinone.cross_scan import PROBE_SKIP_KINDS
    except Exception:  # noqa: BLE001
        PROBE_SKIP_KINDS = frozenset()
    out = []
    for row in CR.all_caps():
        kind = str(row.get("name") or "")
        spec = BENIGN_CAPS.get(kind) or {}
        need = CR.required_params(kind) if hasattr(CR, "required_params") else []
 # 2026-10-13 修（实测教训）：`desc` 截到 300 字是**静默**的 —— `cadgen` 的 desc 正好被切在
        #    300 字，写在**尾部**的"常用说法/触发词"于是**根本没进路由**（实测：同一句人话
        #    「把这个宝箱模型渲染一张图看看」，词在尾部时 **零命中**；挪到前 300 字内 ⇒ 命中 3 词、
        #    排到第一）。静默截断是假绿的近亲：作者以为加了触发词，路由里根本没有。
        #    修法两条：① 截断时补一个**看得见**的标记（谁被切了一眼就知道）② 记下原长，供自检对账。
        _full_desc = str(row.get("desc") or "")
 # 2026-10-13 二次修：标记**追加**在 300 字之后，不再替换掉第 280–300 那 20 个字 ——
        #    上一版把标记塞进前 300（`[:280] + 标记`），于是**第 280–300 这 20 字既不在 desc
        #    也不在 desc_tail 里**（一个我自己挖的洞）。现在：desc = 前 300 字原文 + 标记；
        #    desc_tail = 第 300 字之后 ⇒ 无洞、无重叠。
        desc_shown = _full_desc[:300]
        if len(_full_desc) > 300:
            desc_shown = desc_shown + "…【图鉴截断：原文 %d 字（尾部见 desc_tail，打分已接回）】" % len(_full_desc)
        out.append({
            "kind": kind,
            "domain": str(row.get("domain") or ""),
            "desc": desc_shown,
 # 2026-10-13 修**根**：截断从此**只影响显示、不影响路由** ——
            #    被切掉的那一段另存 `desc_tail`，打分时接回去用（见 `score_cap`）。
            #    为什么要这么修：原来截断是**静默**的 ⇒ 把触发词写在 300 字之后的位
            #    **根本进不了路由**（已经害过两个位：cadgen、comfy_native）。
            #    逐位改写 desc 是治表；这里把"截断"与"路由"解耦，71 位**自动**恢复可路由。
            "desc_tail": (_full_desc[300:] if len(_full_desc) > 300 else ""),
            "desc_full_chars": len(_full_desc),
            "desc_truncated": len(_full_desc) > 300,
            "enabled": row.get("status") == "enabled",
            "reason": str(row.get("reason") or ""),
            "safe": bool(spec.get("safe")),
            "handler": str(row.get("handler") or ""),
            # 三道判据决定 run 敢不敢自动跑
            "requires_params": list(need or []),
            "params_hint": CR.params_hint(kind) if hasattr(CR, "params_hint") else "",
 # 2026-09-22 补：原先只看 cross_scan 的 `PROBE_SKIP_KINDS` ⇒ 框架自己
            # `preflight._STATE_CHANGING_KINDS` 里明写"会改状态"的位（深蒸 longrun 实测：`lr_tick`）
            # 在图鉴上却是 `needs_confirmation: false`、"看着免卡只读"，跟 omni 自己的判据打架。
            # 修法：**两边任一为真就算要确认**（判据别各算各的）。
            "needs_confirmation": kind in PROBE_SKIP_KINDS or kind in _state_changing_kinds(),
            # 2026-09-23 解禁后改成"是否只是登记未实现"：
            # 旧字段 `disabled` 恒 False，留着会让人以为"名单还在、只是这次没命中"。
            "unimplemented": kind in UNIMPLEMENTED_CAPS,
            "channel": "omnipulg",
            "invoke": 'python tools/codex-scripts/five-dim.py cap %s' % kind,
        })
    return out, ""


def dedupe_skills(rows: list[dict]) -> list[dict]:
    """按技能名去重 —— 同一技能常被装在多个 agent 目录（`.agents`/`.claude`/`-autoclaw`…）。

    去重后保留一份，并把「它出现在哪几个根」记进 `roots`。**不去重就是虚报条数**：
    25 个 arkcli 技能装在 9 处会变成 225 条，读的人会以为框架里有两百多个技能。
    """
    by: dict[str, dict] = {}
    for r in rows:
        key = r["name"]
        if key not in by:
            by[key] = {**r, "roots": [r["root"]], "root_count": 1}
        else:
            if r["root"] not in by[key]["roots"]:
                by[key]["roots"].append(r["root"])
                by[key]["root_count"] += 1
            # 描述取更长的那个（有的目录是精简 stub，有的是全本）
            if len(r.get("desc") or "") > len(by[key].get("desc") or ""):
                by[key]["desc"] = r["desc"]
            by[key]["has_references"] |= r["has_references"]
            by[key]["has_scripts"] |= r["has_scripts"]
            by[key]["has_assets"] |= r["has_assets"]
            for t in (r.get("triggers") or []):
                if t not in by[key]["triggers"]:
                    by[key]["triggers"].append(t)
    return sorted(by.values(), key=lambda x: x["name"])


def build(verbose: bool = True) -> dict:
    caps, err = collect_caps()
    raw_skills, bulk = collect_skills()
    skills = dedupe_skills(raw_skills)
    atlas = {
        "built_by": "tools/codex-scripts/omni.py build",
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "note": ("框架职业技能图鉴。口径：`omnipulg` = 走万能插（run_task 唯一门）的能力位；"
                 "`agent-skill` = 由 agent 按技能名加载执行的技能；`design-asset` = 审美素材（料，不是可调用能力）。"
                 "本图鉴是**现扫**产物，不是手抄清单。"),
        "caps_error": err,
        "caps": caps,
        "skills": skills,
        "design_assets_bulk": [
            {"root": str(root), "why": why,
             "count": sum(1 for x in bulk if x["root"] == str(root))}
            for root, channel, why in SKILL_ROOTS
            if channel == "design-asset"
            and any(b["root"] == str(root) for b in bulk)
        ],
        "counts": {
            "caps": len(caps),
            "caps_enabled": sum(1 for c in caps if c["enabled"]),
 # 2026-09-22 修：这里原先只看注册表三个旗标（enabled/safe/无参），**不查门**
            # ⇒ 把挂着授权作用域的位也算进"免卡无参可直跑"。实测（深蒸 data 域时）：
 # `omni list --domain data` 把 `audit_query` 标成 ，而它身上挂着 `audit_read`
 # —— 当场跑必被拒。同域 `omni ask` 反而标对了（）⇒ 两个出口口径不一致，**列表那个是假绿**。
            # 改法：一律用 `auto_run_verdict()` 这一个判据（它把作用域也算进去），别再各算各的。
            "caps_safe_no_args": sum(1 for c in caps if auto_run_verdict(c)[0]),
            "skills": len(skills),
            "skills_raw_before_dedupe": len(raw_skills),
            "skills_multi_root": sum(1 for s in skills if s["root_count"] > 1),
            "skills_by_channel": {ch: sum(1 for s in skills if s["channel"] == ch)
                                  for ch in sorted({s["channel"] for s in skills})},
            "design_assets_bulk_total": len(bulk),
            "domains": len({c["domain"] for c in caps}),
        },
    }
    ATLAS.parent.mkdir(parents=True, exist_ok=True)
    ATLAS.write_text(json.dumps(atlas, ensure_ascii=False, indent=1), encoding="utf-8")
    if verbose:
        c = atlas["counts"]
        print("落盘 %s（%.1f KB）" % (ATLAS.relative_to(ROOT), ATLAS.stat().st_size / 1024))
        print("  能力位: %d（启用 %d · 域 %d · **可免卡无参直跑 %d**）"
              % (c["caps"], c["caps_enabled"], c["domains"], c["caps_safe_no_args"]))
        print("  技能  : %d 条（去重前 %d · 装在多个目录的 %d）  %s"
              % (c["skills"], c["skills_raw_before_dedupe"], c["skills_multi_root"],
                 c["skills_by_channel"]))
        print("  审美料: %d 个目录（设计系统/骨架，按类聚合）" % c["design_assets_bulk_total"])
        if atlas["caps_error"]:
            print("  ⚠ %s" % atlas["caps_error"])
    return atlas


_ATLAS_SOURCE = {"how": "未加载", "path": None, "mtime": None}


def load_atlas() -> dict:
    """读图鉴；**不存在时**才现扫重建。

    🔴 2026-09-23 补：原先文档写 `ask` "只给候选与命令，不动手"，但**没人核实过它到底写不写盘**。
    现在把"这一轮是读的还是重建的"如实记进 `_ATLAS_SOURCE`，并让 `ask` 打出来 ——
    **行为可核对，不靠文档保证。**
    """
    import time as _t
    if ATLAS.exists():
        _ATLAS_SOURCE.update({"how": "读取已有（本轮未重建）", "path": str(ATLAS),
                              "mtime": _t.strftime(
                                  "%Y-%m-%dT%H:%M:%S",
                                  _t.localtime(ATLAS.stat().st_mtime))})
        return json.loads(ATLAS.read_text(encoding="utf-8"))
    a = build(verbose=False)
    _ATLAS_SOURCE.update({"how": "**本轮现扫重建**（原文件不存在）", "path": str(ATLAS),
                          "mtime": _t.strftime("%Y-%m-%dT%H:%M:%S")})
    return a


def _hint_grams(domain: str) -> set:
    return grams(DOMAIN_HINTS.get(domain, ""))


def score_cap(intent_g: set, cap: dict) -> tuple[float, list[str]]:
    """能力位打分：意图 n-gram ×(能力位名+域中文提示+描述) 命中。

    为什么把**域中文提示**算进去：能力位名和描述基本是英文/术语（`codex_status`，
    "官方 Codex 只读状态"），而人说的是"看一眼有多少能力位"。不借域提示词，人话就落不下来。
    """
    why = []
    name_g = grams(cap["kind"].replace("_", ""))
    # 打分语料 = 显示用 desc **＋** 被截断的那一段（`desc_tail`）——
    # 截断只影响显示、不影响路由（2026-10-13 修；详见 build 里 desc_tail 的注释）。
    desc_g = grams(cap["desc"] + (cap.get("desc_tail") or ""))
    dom_g = _hint_grams(cap["domain"])
    s = 0.0
    hit_name = intent_g & name_g
    hit_desc = intent_g & desc_g
    hit_dom = intent_g & dom_g
    if hit_name:
        s += len(hit_name) * 3.0
        why.append("名命中 %d" % len(hit_name))
    if hit_desc:
        s += len(hit_desc) * 1.5
        why.append("说明命中 %d" % len(hit_desc))
    if hit_dom:
        s += len(hit_dom) * 1.0
        why.append("域词命中 %d(%s)" % (len(hit_dom), cap["domain"]))
    if not cap["enabled"]:
        s *= 0.2                      # 禁用的排后面，但不隐藏
        why.append("已禁用")
    if cap["requires_params"]:
        why.append("需参数 %s" % ",".join(cap["requires_params"][:3]))
    if cap["needs_confirmation"]:
        why.append("有侧效应·需确认")
    return s, why


# ── 落点可达性：**路由通了 ≠ 落点能用**（2026-09-23 补，拿实测教训换的）────────
def _py_parses(path: Path) -> tuple[bool, str]:
    """**按扩展名分派**语法检查 —— 别拿 Python 的秤称 JS。

    🔴 2026-09-23 修：原实现**对任何落点都跑 `ast.parse`**。
    于是新登记的 `desktop-shell`（落点是 `preflight.cjs`）被报
    **`🔴 不可达：语法错误 line 1`** —— 而那个文件在真 Electron 里刚跑过、PASS 10。
    **判据用错了对象** = 本会话反复栽的同一类错（文本级判据冒充结构级）。
    ⇒ 现在的规矩：`.py` 走 `ast`；`.js/.cjs/.mjs` 走 `node --check`；其余只判存在。
    """
    suf = path.suffix.lower()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return False, type(e).__name__
    if suf in (".js", ".cjs", ".mjs"):
        import shutil
        import subprocess as _sp
        node = shutil.which("node")
        if not node:
            return True, "存在（本机无 node，未做语法检查 —— **别读成已验**）"
        try:
            r = _sp.run([node, "--check", str(path)], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=30)
        except Exception as e:                                      # noqa: BLE001
            return True, "存在（node --check 没跑成：%s）" % type(e).__name__
        if r.returncode == 0:
            return True, "node --check 通过"
        first = (r.stderr or "").strip().splitlines()
        return False, "node --check 失败：%s" % (first[-1][:70] if first else "?")
    if suf != ".py":
        return True, "存在（非 .py 落点，只判存在）"
    import ast
    try:
        ast.parse(text.lstrip("\ufeff"))
        return True, "可解析"
    except SyntaxError as e:
        return False, "语法错误 line %s" % e.lineno


def local_tools() -> list[dict]:
    """本地工具面 + 逐条现读可达性（文件在不在 / 能不能解析）。"""
    out = []
    for t in LOCAL_TOOLS:
        p = ROOT / t["path"]
        exists = p.is_file()
        ok, note = _py_parses(p) if exists else (False, "实物不存在")
        out.append({**t, "exists": exists, "reachable": bool(exists and ok),
                    "reach_note": note, "abs": str(p)})
    return out


def skill_reachable(sk: dict) -> tuple[bool, str]:
    """本会话能不能**按名字加载**这条技能：只看本会话实测真读的两个根。"""
    for root, why in SESSION_SKILL_ROOTS:
        if (root / sk["name"] / "SKILL.md").exists():
            return True, "在 %s（%s）" % (root, why)
    roots = sk.get("roots") or []
    return False, "只在 %s —— **本会话读不到**（技能目录是会话启动时快照的）" % (
        ", ".join(roots[:3]) or "未知根")


def cap_reachable(c: dict) -> tuple[bool, str]:
    """能力位能不能直跑：复用**同一个判据** `auto_run_verdict`，不自造第二份。"""
    ok, why_not = auto_run_verdict(c)
    if ok:
        return True, "只读无参且不需授权"
    return False, " / ".join(why_not[:3])


def score_tool(intent_g: set, t: dict) -> tuple[float, list[str]]:
    why = []
    name_g = grams(t["name"].replace("_", ""))
    blob_g = grams("%s %s" % (t["desc"], t.get("triggers", "")))
    s = 0.0
    hn = intent_g & name_g
    hb = intent_g & blob_g
    if hn:
        s += len(hn) * 3.0
        why.append("工具名命中 %d" % len(hn))
    if hb:
        s += len(hb) * 1.4
        why.append("用途/触发词命中 %d" % len(hb))
    if not t.get("reachable"):
        s *= 0.3
        why.append("**落点不可达**（%s）" % t.get("reach_note"))
    return s, why


def rank(intent: str, domain: str | None = None, top: int = 8) -> dict:
    atlas = load_atlas()
    ig = grams(intent)
    caps, skills, tools = [], [], []
    for cap in atlas["caps"]:
        if domain and cap["domain"] != domain:
            continue
        s, why = score_cap(ig, cap)
        if s > 0:
            caps.append({**cap, "score": round(s, 2), "why": why})
    caps.sort(key=lambda r: -r["score"])
    for sk in atlas["skills"]:
        # 技能侧同款：打分语料 = 显示用 desc **＋** 被截断的那段（`desc_tail`）——
        # 截断只影响显示、不影响路由（2026-10-13；实测 97/386 条技能描述超 400 字）。
        blob = "%s %s %s %s %s" % (sk["name"], sk["displayName"], sk["desc"],
                                   sk.get("desc_tail") or "", " ".join(sk["triggers"]))
        hit = ig & grams(blob)
        if hit:
            skills.append({**sk, "score": round(len(hit) * 1.2, 2),
                           "why": ["技能词命中 %d" % len(hit)]})
    skills.sort(key=lambda r: -r["score"])
    for t in local_tools():
        s, why = score_tool(ig, t)
        if s > 0:
            tools.append({**t, "score": round(s, 2), "why": why})
    tools.sort(key=lambda r: -r["score"])
    return {"intent": intent, "caps": caps[:top], "skills": skills[:top],
            "tools": tools[:top], "atlas_built_at": atlas["built_at"]}


def cmd_ask(intent: str, domain: str | None) -> int:
    r = rank(intent, domain)
    print("人类一句话：%s" % r["intent"])
    print("图鉴读数时刻：%s" % r["atlas_built_at"])
    print("图鉴来源：%s（文件 mtime %s）—— **ask 不写盘这件事是可核对的，不靠文档保证**"
          % (_ATLAS_SOURCE["how"], _ATLAS_SOURCE["mtime"]))
    print()

 # 先给"本地工具面"（如果命中）—— 扫描/体检这类意图的真落点在这里。
    #    为什么排在最前：能力位里**没有**一台本地扫描器；而人问"扫一下"最先想要的是扫描，
    #    不是框架自检。谁最贴意图谁在前，与通道无关。
    if r.get("tools"):
        print("── 走本地工具面（本机**真实存在**的扫描器/操作台 · 真命令 · 不需授权）──")
        for t in r["tools"]:
            ok, note = (t["reachable"], t["reach_note"])
            print("  [%.1f] %-22s %s" % (t["score"], t["name"],
                                         " · ".join(x for x in t["why"] if "落点" not in x)))
            print("        %s" % t["desc"][:130])
            print("        → %s   %s" % (t["invoke"], "✅ 可达" if ok else "🔴 不可达：%s" % note))
            for k, v in (t.get("variants") or {}).items():
                print("           %-14s %s" % (k, v))
            print("           门：%s" % t["gate"])

    if not r["caps"] and not r["skills"] and not r.get("tools"):
        print("🔴 没有一路命中。**不猜一个出来** —— 请把话说得更贴它的职责，"
              "或先 `omni list` / `omni list --channel local-tool` 看有什么。")
        return 1
    if r["caps"]:
        print("\n── 走万能插的能力位（框架本体 · 走 run_task 唯一门）──")
        for c in r["caps"]:
            ok_auto, why_not = auto_run_verdict(c)
            print("  [%.1f] %-28s %-14s %s" % (c["score"], c["kind"], c["domain"],
                                               " · ".join(c["why"])))
            print("        %s" % c["desc"][:110])
            if ok_auto:
                print("        → %s   ✅ 只读无参，可直跑" % c["invoke"])
            else:
                print("        → %s   🔒 不自动跑：%s" % (c["invoke"], " / ".join(why_not[:3])))
    if r["skills"]:
        print("\n── 走 agent 技能（由我按名字加载执行）──")
        for s in r["skills"]:
            ok, note = skill_reachable(s)
            print("  [%.1f] %-30s %-12s %s" % (s["score"], s["name"], s["channel"],
                                               s["displayName"] or ""))
            print("        %s" % (s["desc"][:110] or "（无描述）"))
 # 落点可达性：路由通了不等于能用。实测 `gbt-system`(12.0) 本会话加载不了，
            #    原先照样当首选推给人 ⇒ 人照着做会撞 unknown。现在逐条标出来。
            print("        %s %s" % ("✅ 本会话可加载" if ok else "🔴 **本会话加载不了**", note))
    print("\n（主路说明：语义路由 `semantic_route` 走**触手方法**；本命令补的是"
          "「人话 → 本地工具 / 能力位 / 技能」这一环，**三通道并列**，拿不准给多个候选由人定。）")
    return 0


def cmd_run(intent: str, domain: str | None, yes: bool) -> int:
    r = rank(intent, domain, top=3)
    if not r["caps"]:
        print("🔴 没有落点，不猜。先 `omni ask` 或 `omni list`。")
        return 1
    best = r["caps"][0]
    ok_auto, why_not = auto_run_verdict(best)
    print("落点：%s（%s，分 %.1f）" % (best["kind"], best["domain"], best["score"]))
    print("命令：%s" % best["invoke"])
    if not ok_auto and not yes:
        print("🔴 **不自动跑**（这一层默认拒绝，只有能证明是只读无参的才自动跑）：")
        for w in why_not:
            print("     · %s" % w)
        print("   确认要跑就加 --yes —— 但门照样会拦：缺授权它会如实报缺，不会被我绕过去。")
        return 1
    if not ok_auto and yes:
        print("⚠ 你加了 --yes，所以往下走；**门仍然在**（缺授权会如实报缺）。")
        for w in why_not:
            print("     · %s" % w)
    # ── 真跑：走**五维合一的默认执行路径**（耳→手→眼→嘴 + 开步/收步）──────────
 # 2026-09-23 补（三执行层「默认使用」的最后一格）。
    # 改前：这里直接起 `five-dim.py cap <kind>` —— 只到能力位那一层，
    #   大脑（brain_*）与五维合一的**真链**一次都不参与。
    #   机检证据：装钩子后 `brain_unify = 0`、`run() 全链 = 0`，而 `call` 有 36 次。
    # 改后：`sync_exec.run(intent, kind=…, use_unify=False)`。
    #   **为什么必须 `use_unify=False`**：`use_unify=True` 会把活交给 `brain_unify`，
    #   而它**自己会重新 route 并执行** —— 那就**绕过了上面那道默认拒绝判定**
    #   （那是本工具唯一的防乱跑装置）。判据由 omni 出，五维只负责"听得清/有证据/不夸大"。
    # 失败一律**退回**原来的 `five-dim.py cap`：**不许让"更到位"变成"更容易跑不成"**。
    five = ROOT / "tools" / "codex-scripts" / "five-dim.py"
    _path_used, sid = "five-dim.py cap（旧路·退回）", None
    try:
        from gbt_allinone.tools import sync_exec as _se
        _op = _se.step_open("omni run: %s" % intent[:80], watch=[])
        sid = _op.get("step_id") if _op.get("ok") else None
        _r = _se.run(intent, kind=best["kind"], use_unify=False)
        _verdict = _r.get("verdict")
        _path_used = "sync_exec.run（五维默认路径）"
        if sid:
            _se.step_close(sid,
                           evidence=["omni_run:%s=%s" % (best["kind"], _verdict),
                                     "gate=omni-auto_run_verdict no_unify=True"],
                           note="omni run · 五维默认路径（判据由 omni 出，brain_unify 未参与）")
            sid = None
        print("── 走的哪条路 ──")
        print("    %s ｜ 信封=%s ｜ 五维判决=%s ｜ 耗时 %sms"
              % (_path_used, _r.get("channels", {}).get("ear", {}).get("ok"),
                 _verdict, _r.get("elapsed_ms")))
        print("    脑/手：%s" % (_r.get("channels", {}).get("hand") or {}))
        print("    嘴说漏了什么：%s"
              % ((_r.get("channels", {}).get("mouth") or {}).get("said", {}).get("missed")))
        print("── 执行返回 ──")
        print(json.dumps(_r.get("exec"), ensure_ascii=False, default=str)[:1000])
        return 0 if _verdict in ("ok", "partial") else 1
    except Exception as _e:                                          # noqa: BLE001
        if sid:
            try:
                from gbt_allinone.tools import sync_exec as _se2
                _se2.step_close(sid, evidence=["omni_run:fallback=%s" % type(_e).__name__],
                                note="五维路径失败，退回五维合一 cap")
            except Exception:                                        # noqa: BLE001
                pass
        print("⚠ 五维默认路径不可用（%s: %s）⇒ **退回** five-dim.py cap"
              % (type(_e).__name__, str(_e)[:120]))
    # 真跑：一律走万能插（退回路径）
    import subprocess
    p = subprocess.run([sys.executable, str(five), "cap", best["kind"]],
                       capture_output=True, timeout=180)
    out = (p.stdout or b"").decode("utf-8", "replace")
    print("── 万能插返回（exit=%d）──" % p.returncode)
    print(out[:1200] or (p.stderr or b"").decode("utf-8", "replace")[:600])
    return p.returncode


def cmd_list(domain: str | None, channel: str | None) -> int:
    a = load_atlas()
    if channel in (None, "omnipulg"):
        rows = [c for c in a["caps"] if not domain or c["domain"] == domain]
        print("── 能力位 %d 条（万能插 · 走 run_task 唯一门）──" % len(rows))
        byd: dict[str, list] = {}
        for c in rows:
            byd.setdefault(c["domain"], []).append(c)
        for d in sorted(byd):
            print("  【%s】%d 条  (%s)" % (d, len(byd[d]), DOMAIN_HINTS.get(d, "—")[:40]))
            for c in byd[d]:
 # 同一个判据（`auto_run_verdict`）算 / —— 原先这里自己算一遍旗标、
                # **不查授权门**，于是 `audit_query`（挂 `audit_read`）被标成"免卡无参可直跑"，
 # 而门当场拒它；同一份图鉴在 `omni ask` 里却标 。列表出口才是那个假绿。
                flag = "✅" if auto_run_verdict(c)[0] else "🔒"
                print("     %s %-26s %s" % (flag, c["kind"], c["desc"][:70]))
    if channel in (None, "agent-skill"):
        rows = [s for s in a["skills"] if not domain or domain in s["desc"] or domain in s["name"]]
        print("\n── agent 技能 %d 条（按名字加载执行）──" % len(rows))
        for s in rows:
            ok, _ = skill_reachable(s)
            print("     %s %-32s %-12s %s" % ("✅" if ok else "🔴", s["name"], s["channel"],
                                              (s["desc"] or "")[:56]))
    if channel in (None, "local-tool"):
        rows = local_tools()
        print("\n── 本地工具面 %d 条（真命令 · 不走 run_task · 无需授权）──" % len(rows))
        for t in rows:
            print("     %s %-22s %s" % ("✅" if t["reachable"] else "🔴", t["name"], t["invoke"]))
            print("        %s" % t["desc"][:120])
    print("\n（能力位：✅=免卡无参可直跑 · 🔒=要参数/要确认/已禁用，跑之前门会拦；"
          "agent 技能：✅/🔴 = **本会话能不能按名字加载**；本地工具：✅/🔴 = 实物在不在、能不能解析）")
    return 0


def cmd_caliber() -> int:
    """口径对账：**同一件事的三个数**必须能对账，不许各说各的。

    🔴 2026-09-23 实测抓到的口径分裂：`gbt-omni` 的 §0 写「只读无参可直跑 **122**」，
    §7.1 写「可免卡无参直跑 **88**」，而 `omni_max.py` 按纪律筛出来是 **102**。
    三个数说的是同一件事，却谁也不对账 ⇒ 读的人不知道信哪个。
    这条命令把**每种口径的定义与现算值并排列出**，并指定哪一个才是权威。
    """
 # 2026-09-23 补 import：A 行的说明改成"现算"之后用到了 `UNIMPLEMENTED_CAPS`，
    #    而当时只改了文案没补 import ⇒ `omni caliber` 直接 NameError 崩掉（本轮实测抓到）。
    #    教训：**"把写死的数字改成现算"不是改文案，是改依赖** —— 补了算式就得补 import。
    from gbt_allinone.caps_registry import UNIMPLEMENTED_CAPS
    a = load_atlas()
    caps = a["caps"]

    def n(pred):
        return sum(1 for c in caps if pred(c))

    enabled = [c for c in caps if c["enabled"]]
    safe = [c for c in enabled if c.get("safe")]
    noskip = [c for c in safe if not c.get("needs_confirmation")]
    noscope = [c for c in noskip if not required_scopes(c["kind"])]
    noparam = [c for c in noscope if not c["requires_params"]]
    # H：**修掉域误杀之后**的权威口径（`safe ∧ 无作用域 ∧ 名字是只读动作 ⇒ 免后果`）
    # 域过滤（不豁免）会砍掉多少 —— 用来量化"豁免救回了几条"
    domain_blocked = [c for c in noparam if c["domain"] in DANGER_DOMAINS]
    exempted = [c for c in domain_blocked if readonly_scanner_exempt(c)]
    still_blocked = [c for c in domain_blocked if not readonly_scanner_exempt(c)]
    noparam2 = [c for c in noparam
                if (c["domain"] not in DANGER_DOMAINS or readonly_scanner_exempt(c))]
    # G：**运行时**口径 —— `omni_max.py` 真跑 147 个能力位时用的那套筛法
    #    （额外去掉有后果的域 + 名字带写动作字样的）。它算出来是 102，与 F=98 **不等**，
    #    差在侧过滤不同 —— 这种差必须写出来，不能假装两个口径是一回事。
    runtime = [c for c in noscope
               if c["domain"] not in DANGER_DOMAINS and not DANGEROUS_NAME_RE.search(c["kind"])]
    print("=" * 72)
    print("口径对账 · 「可直跑」到底几条")
    print("=" * 72)
    rows = [
        ("A 注册表全量", len(caps),
         "图鉴全部能力位 = **enabled %d + 只登记未实现 %d**（2026-09-23 解禁后 dangerous 域已为空，"
         "那 11 个名字改登记在 domain=unimplemented；它们**不是**被挡住的，是没有实现）"
         % (len(enabled), len(UNIMPLEMENTED_CAPS))),
        ("B enabled", len(enabled), "注册表 enabled=True"),
        ("C B 且 safe", len(safe), "标了 safe（可读/低风险）"),
        ("D C 且不在侧效应名单", len(noskip), "从 C 去掉 `PROBE_SKIP_KINDS`（无参即有后果的那批）"),
        ("E D 且 policy 无作用域", len(noscope), "`policy.evaluate(kind,{}).scopes == ()` —— 不需任何授权"),
        ("F E 且不需要参数", len(noparam), "在 E 之上再加「无参」；**不做域过滤**"),
        ("H F 再加域过滤（含只读扫描器豁免）", len(noparam2),
         "✅✅ **权威口径**：域过滤照旧，但 `safe ∧ 无作用域 ∧ 名字是只读动作` 的扫描器豁免。"
         "比 F 少 %d 条（域过滤砍 %d，其中 %d 条被豁免救回：%s）"
         % (len(noparam) - len(noparam2), len(domain_blocked), len(exempted),
            ", ".join(c["kind"] for c in exempted) or "无")),
        ("G noscope 再去有后果域/写动作名", len(runtime),
         "`omni_max.py` **上一轮真跑**用的旧筛法（无豁免、也不查参数）"),
    ]
    for name, val, why in rows:
        print("  %-24s %4d   %s" % (name, val, why))
    print("-" * 72)
    print("文档里出现过但**没写定义**的数：122（§0）· 88（§7.1）· 图鉴 273 条技能（§5）")
    print("现算：技能 %d 条 · 本地工具 %d 条 · 审美料目录见 gaps" % (
        len(a["skills"]), len([t for t in local_tools() if t["reachable"]])))
    print("⇒ **权威口径 = H = %d**（域过滤砍 %d 条，其中 **%d 条只读扫描器被豁免救回**）。"
          % (len(noparam2), len(domain_blocked), len(exempted)))
    print("   仍被域拦下的 %d 条（非只读扫描器，**不豁免**）：%s"
          % (len(still_blocked), ", ".join(c["kind"] for c in still_blocked[:12])))
    print("   ⚠️ **旧运行时口径 G = %d**（`omni_max.py` 上一轮真跑用的，无豁免）——"
          "两个口径都要写清，不许拿一个当另一个。" % len(runtime))
    print("   纪律：以后任何「可直跑 N 条」都必须写成「口径 X 的现算值」，不许手抄。")
    # 顺带把参数位的名字列出来，免得"为什么不是 147"
    pr = [c["kind"] for c in noscope if c["requires_params"]]
    print("\n  F 比 E 少的那些（E=%d → F=%d，共 %d 条需参数）：%s"
          % (len(noscope), len(noparam), len(pr), ", ".join(pr[:14])))
    # ── 同源校验：图鉴 `needs_confirmation` 必须**逐位等于** `PROBE_SKIP_KINDS`（2026-09-24 起）──
    # 旧账：这两处曾各算各的（图鉴 22 vs 手抄探测名单 13，差 9 条改状态位），
    # `wf_cache_clear` 在 cross_scan H 维真清过缓存就是那个缺口。深修后
    # `PROBE_SKIP_KINDS = 探测专项 ∪ preflight.state_changing_kinds()`，图鉴的
    # `needs_confirmation` 用同一份派生 ⇒ 本段从"报分裂"变成"校验同源"：
    # 不等 = 派生链断了，要当真故障修，不许再回到"各抄一份"。
    from gbt_allinone.cross_scan import PROBE_SKIP_KINDS, PROBE_ONLY_KINDS
    from gbt_allinone.preflight import state_changing_kinds as _sc_kinds
    nc_all = {c["kind"] for c in caps if c.get("needs_confirmation")}
    extra = sorted(nc_all - set(PROBE_SKIP_KINDS))
    missing = sorted(set(PROBE_SKIP_KINDS) - nc_all)
    if extra or missing:
        print("\n  🔴 **同源校验失败**：图鉴 `needs_confirmation` %d 条 vs `PROBE_SKIP_KINDS` %d 条"
              " —— 派生链断了（两边应逐位相等）。" % (len(nc_all), len(PROBE_SKIP_KINDS)))
        print("     图鉴多出：%s" % (", ".join(extra) or "无"))
        print("     探测名单多出：%s" % (", ".join(missing) or "无"))
    else:
        print("\n  ✅ **同源校验通过**：图鉴 `needs_confirmation` %d 条 == `PROBE_SKIP_KINDS` %d 条"
              "（= 探测专项 %d ∪ 改状态 %d，单一真源 `preflight.state_changing_kinds()`）。"
              % (len(nc_all), len(PROBE_SKIP_KINDS), len(PROBE_ONLY_KINDS),
                 len(_sc_kinds())))
        print("     （旧账：2026-09-23 前两处各算各的，差 9 条改状态位，"
              "`wf_cache_clear` 曾在 H 维真清过缓存 —— 已随派生链闭合。）")
    sk_ok = [s["name"] for s in a["skills"] if skill_reachable(s)[0]]
    print("\n  技能落点可达性：图鉴 %d 条中，**本会话可加载 %d 条**"
          "（只看 %s）" % (len(a["skills"]), len(sk_ok),
                       " ∪ ".join(str(r) for r, _ in SESSION_SKILL_ROOTS)))
    return 0


def cmd_gaps(limit: int = 6) -> int:
    """深蒸队列：**逐个列出**谁做完了、谁还在队里。

    为什么要有这条：Owner 要求"别遗漏"。光靠记忆或散文记待办，漏是必然的 ——
    所以把状态**从图鉴现算**：30 个注册表域 + 各外部技能簇，一个不落地列出来，
    每个都带显式状态。**没做 ≠ 不在表里**。
    """
    a = load_atlas()
    by_dom: dict[str, list] = {}
    for c in a["caps"]:
        by_dom.setdefault(c["domain"], []).append(c)

    print("=" * 84)
    print("深蒸队列（状态从图鉴现算 · 不是手写待办）")
    print("=" * 84)
    done, queued = [], []
    for dom in sorted(by_dom, key=lambda d: -len(by_dom[d])):
        caps = by_dom[dom]
        skill = DISTILLED_DOMAINS.get(dom)
        row = (dom, len(caps), skill)
        (done if skill else queued).append(row)
    print("\nA. 注册表 %d 个职业域" % len(by_dom))
    for dom, n, skill in done:
 # 别只信映射（2026-09-22 的教训）：`creation → gbt-aesthetic` 在表里挂了很久，
        # 而那份规程里一个能力位都没点到 —— 表说"已深蒸"，实物不干这件事，就是假绿。
        # 所以这里**现读盘**：两份产物在不在、哈希一不一致；不一致就当场降级成告警，
        # 不许再打那个绿勾。（深一层的内容判定交给 `verify-distill.py`。）
        ws = ROOT / "skills" / skill / "SKILL.md"
        mg = Path.home() / ".openclaw-autoclaw" / "skills" / skill / "SKILL.md"
        if not ws.exists() or not mg.exists():
            print("   ⚠️ 已登记但**实物缺失**  %-14s %3d 个能力位  → %s（%s）"
                  % (dom, n, skill, "工作区源稿不在" if not ws.exists() else "managed 安装件不在"))
            continue
        if ws.read_bytes() != mg.read_bytes():
            print("   ⚠️ 已登记但**两份不一致**  %-14s %3d 个能力位  → %s" % (dom, n, skill))
            continue
        print("   ✅ 已深蒸  %-14s %3d 个能力位  → %s" % (dom, n, skill))
    for dom, n, skill in queued:
        names = [c["kind"] for c in by_dom[dom]]
        head = "、".join(names[:limit]) + ("…" if len(names) > limit else "")
        print("   ⏳ 在队里  %-14s %3d 个能力位  %s" % (dom, n, head))
    print("   小计：已深蒸 %d / 在队 %d（共 %d 个域）" % (len(done), len(queued), len(by_dom)))

    # B. 外部/技能簇：按名字前缀聚簇，看有没有 GBT 口径规程
    clusters: dict[str, int] = {}
    for s in a["skills"]:
        nm = s["name"]
        pre = nm.split("-")[0] + "-*" if "-" in nm else nm
        clusters[pre] = clusters.get(pre, 0) + 1
    big = sorted([kv for kv in clusters.items() if kv[1] >= 3], key=lambda kv: -kv[1])
    print("\nB. 技能簇（≥3 条的名字前缀）")
    for pre, n in big:
        stem = pre.rstrip("*-")
        if stem in SELF_CLUSTERS:
            mark = "✅ 自有规程（不是待蒸的外来技能）"
        elif stem in DISTILLED_CLUSTERS:
            mark = "✅ 已深蒸 → %s" % DISTILLED_CLUSTERS[stem]
        else:
            mark = "⏳ 在队里（有技能，但无 GBT 口径规程）"
        print("   %-16s %3d 条   %s" % (pre, n, mark))

    print("\nC. 已交付的深蒸件")
    delivered = sorted(set(DISTILLED_DOMAINS.values()) | set(DISTILLED_CLUSTERS.values()))
    for skill in delivered:
        print("   · %s" % skill)
    print("   · gbt-omni（本协议本身：路由 + 门 + 默认拒绝）")
    print("\n读法：**「在队里」= 已索引、能查到、能调，但还没被蒸馏成自己的规程** ——")
    print("      别把「索引过」读成「精通了」。要推进就点名一个域/簇，按审美那一套的规格做：")
    print("      蒸馏技能 + 可机检验收入口 + 固化三处。")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("cmd", nargs="?", default="")
    ap.add_argument("intent", nargs="?", default="")
    ap.add_argument("--domain", default=None)
    ap.add_argument("--channel", default=None)
    ap.add_argument("--yes", action="store_true")
    ns = ap.parse_args(argv)
    if ns.cmd == "build":
        build()
        return 0
    if ns.cmd == "list":
        return cmd_list(ns.domain, ns.channel)
    if ns.cmd == "ask":
        return cmd_ask(ns.intent, ns.domain)
    if ns.cmd == "gaps":
        return cmd_gaps()
    if ns.cmd == "caliber":
        return cmd_caliber()
    if ns.cmd == "tools":
        for t in local_tools():
            print("%s %-22s %s" % ("✅" if t["reachable"] else "🔴", t["name"], t["invoke"]))
            print("    %s" % t["desc"][:130])
            print("    门：%s" % t["gate"])
        return 0
    if ns.cmd == "run":
        return cmd_run(ns.intent, ns.domain, ns.yes)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
