#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""**开机自检**（一条命令跑完全部常设判据）—— 回答一个问题：

    「这台机器现在健康吗？下一轮会话读到的每一段字是真的吗？」

为什么要有一个总入口（一手账）：
  2026-09-25 一天里立了四条**新的**常设判据，但它们散在四个文件、四条命令里：
    · `test_cap_total_consistency`     能力的数目字不许自相矛盾
    · `test_prompt_commands_are_real`  注入的命令必须在盘上
    · `test_prompt_security_section`   安全段必须是真那道门
    · `test_awareness_guard_runs`      自我认知点名的自检必须跑得起来
    · `test_progress_ledger_contract`  台账字段契约
    · `test_injection_honesty`         注入面诚实性（收口判据）
  ⇒ **判据散着 = 没人跑**（本仓原话：「判据立了不等于门关上了」）。
  这个总入口把它们连同两道闸（装机副本漂移 / 重启验收单）收成**一次执行、一个退出码**。

口径（三条，与全仓一致）：
  1. **判据只有一份**：这里不重写任何判据，只**调**已有的 unittest 模块与既有脚本 ——
     复制一份出来就会慢慢长歪。
  2. **失败不许吞**：任何一段跑不动都算**红**（不许记成"跳过"），并如实打出来。
  3. **测试在隔离 store 里跑**：进程启动前就设 `GBT_STORE_DIR`，
     免得不小心绑到生产 store（仓里有守卫，会直接拒跑）。

用法：
  python tools/codex-scripts/boot-selfcheck.py            # 人读
  python tools/codex-scripts/boot-selfcheck.py --json     # 机读
  python tools/codex-scripts/boot-selfcheck.py --quick    # 跳过重启验收单（它要起网络请求）
退出码：0 = 全绿；1 = 有红（逐条列出"哪一段、现在是什么、该怎么办"）。
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import tempfile
import time
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 🔴 2026-10-18 修（2026-10-17 实测）：**本脚本自己是「一条命令跑完全部判据」的主闸**，
#    但在中文 Windows 控制台（cp936/GBK）上，印 ✅/🔴 会当场抛
#    `UnicodeEncodeError: 'gbk' codec can't encode character '\u2705'`（原第 448 行）。
#    实测后果：**37 段判据其实全跑完了**，却在最后一步「印结果」时崩掉，退出码 1 ⇒
#    读数被误读成「自检有红」——这是**工具自身**的假红（P11 假读数一族：无效输出当数据源）。
#    口径：只在输出层强制 UTF-8（errors=replace 保证永不因编码崩），**不动任何判据、不改判定**。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

# 判据组：**只点名，不复制**。每个都必须是 `gbt_allinone.tests.<名>`
# 🔴 2026-10-10 加（主人令：「整个框架只有三个护栏」+「镜像多维度空间的最大能力就是只出品生产，不出品废物」）：
#    这两条**政策**已经落成脚本（guardrail-check.py / deployment-law-check.py），各有真植入负控。
#    但它们**散在 tools/codex-scripts 里 = 没人跑** —— 而本文件的第一句话就是「判据散着 = 没人跑」。
#    ⇒ 收进开机自检。口径同本文件：**只调，不重写**（判据只有一份，在各自的脚本里）。
#    🔴 **许可证**：这两条判据**不是**"又多加了门" —— 它们是**把主人已经说过的两条律钉成可复跑的读数**：
#      ① 只有三道护栏（黑客全能力 / 付款 / 生成代码禁入生产面板）+ 一道自我保护机制（filesystem_write·不能删）
#      ② 只出品生产，不出品废物（镜像干净 / 体检 5/5 / 生产里没有绕过镜像多出来的件）
EXTRA_JUDGMENTS = [
    ("护栏只有三道", ["-X", "utf8", "tools/codex-scripts/guardrail-check.py"]),
    ("部署法制·只出品生产", ["-X", "utf8", "tools/codex-scripts/deployment-law-check.py"]),
    # 🔴 2026-10-10 加（主人令逐字：「**没有亲自跑通的东西不许交付**」）：
    #    本件**当场复跑**台账 state/delivery-claims.jsonl 里每一条交付声明的命令，
    #    并比对期望读数 —— 只有口述的、命令跑不通的、读数对不上的，一律红。
    ("没有亲跑不许交付", ["-X", "utf8", "tools/codex-scripts/proof-of-run-check.py"]),
    # 🔴 2026-10-10 加（**棘轮**，防回归）：一天里同一个病咬掉 3 条红 ——
    #    测试调工具不带 -X utf8 + 本机控制台 GBK ⇒ 印非 ASCII 时 UnicodeEncodeError
    #    ⇒ **stdout 空** ⇒ 调用方解析空 ⇒ 判据恒红。
    #    存量 151 件登记在 state/encoding-guard-baseline.json（不红）；
    #    **新件再犯必红**；修好后会提示可移出基线（棘轮只会缩，不会长）。
    ("编码守门不许退步", ["-X", "utf8", "tools/codex-scripts/encoding-guard-check.py"]),
    # 🔴 2026-10-17 加（主人令逐字：「**把她放在重启大模型第一眼就能看到的地方**」；
    #    当轮自纠：「**编队账本你没有第一时间看到吗**」）：触手 LLM 编队的**单一真源**
    #    deploy/cloud-10/llm-lanes.json 必须每次重启第一眼现读（live 探针走 HEARTBEAT 硬指令第 1 步）。
    #    这里钉的是它**自身契约**的离线判据（--check 不发一字节请求，合「判据不依赖外网」律）：
    #    19 车道字段齐 · 托管不许冒充无审查 · 本机回环只许退场不许回吊 · 不许假绿 · 出处纪律 · 图像面在册。
    ("云上模型编队账本契约", ["-X", "utf8", "tools/codex-scripts/llm-lanes.py", "--check"]),
    # 🔴 2026-10-23 加（主人问「让 V8 吞噬原生 vLLM 是不是就有起来的路线」）：
    #    换车道（GPU→TPU→别的云）唯一能判"起来了没有"的是**三项读数**：首字 p50 ≤2s · ≥20 tok/s · weights_ours=true。
    #    这条钉的是**量具自己**（--selftest 纯离线，4 个负对照必须判对），不是"某个端点有没有通"——
    #    端点通不通要真跑 `lane-bench.py --base …`，那要票，不放进开机自检。
    ("换车道压测量具可复跑", ["-X", "utf8", "tools/codex-scripts/lane-bench.py", "--selftest"]),
    # 🔴 2026-10-23 加（专业体检发现：账停在 239 而注册表已 341，2026-10-01 之后再没写过）：
    #    cap-probe 的默认档来自 state/caps_tiers.json —— 账比真少 102 位，按它扫就等于漏扫三分之一。
    #    这条钉「四档之和 == 注册表条数」+「账不旧于 7 天」；重算走同一件的无参模式（它就是写手）。
    ("能力位分档账与注册表同数且新鲜", ["-X", "utf8", "tools/codex-scripts/gen-caps-tiers.py", "--check"]),
    # 🔴 2026-10-23 加（主人两次点名「一体式、不要跳转」）：把这条从口号变成机器判据 ——
    #    安装台在页内 · 无独立安装窗 · 对话面接主人自己那台 DSH · 页面无外站跳转 · 无「全项目索引」浮条 · 无 V9 残留。
    ("APP 一体式（不跳转）七条判据", ["-X", "utf8", "tools/codex-scripts/integrated-check.py"]),
    # 2026-10-23：云插件互联的**尺子**必须自己能跑（离线负控：单向边要咬出来）。
    # 注意这里只跑 --selftest，不跑真验收 —— 10 槽还没装完，真验收现在是红的，红在缺节点而不是缺判据。
    ("云插件互联验收判据可复跑", ["-X", "utf8", "tools/codex-scripts/mesh-verify.py", "--selftest"]),

    # 🔴 2026-10-11 加（主人令逐字：「记得每一页都要亲自扫描到触手双向绑定好，
    #    确保所有的状态主脑第一时间都能知道，别搞得像无关要紧是的」）：
    #    逐页扫 240 个能力页（不抽样）：① 每页 data-kind 必须在主脑数据里找得到
    #    ② 那个节点必须有 bundle（触手承载）③ 主脑数据新鲜 ④ 快照功能页不许烤过期
    ("每一页都绑到触手", ["-X", "utf8", "tools/codex-scripts/page-bind-check.py"]),

    # 🔴 2026-10-17 加（主人令逐字：「**她自己要懂得编排懂得整理自己的身体，电脑就是她的身体，
    #    这个不懂等于傻**」）：self-tend 四件套早就落地，但**没有任何东西会来调它** ——
    #    能力位在盘上、身体不会自己整理。这条把「触发节奏」钉成开机可复跑的读数：
    #    ① 政策白名单没被删条 ② 节流状态 schema 合法 ③ **距上次整理 ≤7 天**
    #    （从未整理过也算红 —— 不许拿"能力位存在"冒充"身体在整理"）
    #    ④ 隔离区目录名合规；外加一条**负控**（喂坏状态必须判红，防判据恒真）。
    #    离线判据：不碰网络、不搬一物，只读 state/self-tend/last-run.json 与政策常量。
    ("身体自整理节奏", ["-X", "utf8", "tools/codex-scripts/self-tend.py", "check"]),

    # 🔴 2026-10-18 加（P9「账没有写手必烂」· 全量扫描现读出来的真病灶）：
    #    台账是注入进会话头的「唯一进度真源」，而它 updated_at 停在 2026-10-11，
    #    同一份盘上 logbook 却在 2026-10-18 还在写 —— 注入给模型的是六天前的快照。
    #    本条钉四件事，全部可复算、不代笔：
    #      W3 台账声明过的 state/工程进度.md 必须在位且与证据一致（原先声明了却不存在）
    #      W4 「现在在做」里那个日期不许比机器日志旧 72h 以上（人写的停在旧日期 = 无声腐烂）
    #      W5 台账必须有 _写手 节（没有 ⇒ 又退化成手造账，没人判得出它烂没烂）
    #      W6 写手 24h 内真跑过（写手自己没人调 = P8「修复件没接上驱动」）
    #    写手在 tools/codex-scripts/ledger-refresh.py；本条只读，不写盘。
    ("台账写手与一屏账在位", ["-X", "utf8", "tools/codex-scripts/ledger-refresh.py", "--check"]),

    # 🔴 2026-10-18 加（F12 防回退）：room_space 里 simulate/parity/rehearse/release 等
    #    八个原语模块里早就实现，而 api.py 从不路由 ⇒ gate 永远报「没有房间排练报告」，
    #    房间那条「排练 → 盖章 → 原子替换」的正路在门上走不完（模型只能回生产面涂改）。
    #    本轮补齐并把这条判据挂上：模块有、门上没有；名单与真分支不同源；豁免表里那几个
    #    不许被偷偷接上（负控）—— 三条都咬。只读源码，不写盘不起进程。
    ("房间原语都在门上", ["-X", "utf8", "-m", "unittest",
                          "gbt_allinone.tests.test_room_ops_wired"]),

    # 🔴 2026-10-18 加（Owner 令：「画面必须高清 动作自然」「手指都要」
    #    「严格按我的要求直到合格为止」）：把"好不好看"变成能咬的读数 ——
    #    骨架/手指 ≥40 · 模型必须真带 idle+walk · 贴图 ≥2048 · 4K 基准件真 4096 ·
    #    页面必须真播动画（AnimationMixer+crossFade）且给 PBR 环境 · 不许 iframe ·
    #    页面里写到的每个 .glb 都必须在盘上（旧页曾悬空指向不存在的模型）。
    #    只读 GLB 头/PNG 头/HTML 文本，不写盘不起进程。
    ("数字人标准达标", ["-X", "utf8", "-m", "unittest",
                        "gbt_allinone.tests.test_dh_standard"]),

    # 🔴 2026-10-19 加（本轮实栽：舞台里她"能渲染"，但双腿折在胯上、双手举过头顶）：
    #    idle 里 LeftUpLeg/RightUpLeg 被自动绑骨扭了 177°（Tripo 髋骨重定向符号错），
    #    而当时那六条绑骨判据全绿 —— 因为它们只看**网格/蒙皮/尺度**，没人看**动作**。
    #    本条把八条一起钉成开机可复跑的读数（只读 GLB 二进制 + 派生件对账，不起进程）：
    #      ① 单网格单蒙皮 ② 无 42 顶点杂物球 ③ 身高 1.720±0.02（文件空间 Y 跨度）
    #      ④ 无死顶点 ⑤ 髋骨没被扭（逐帧 <0.5°）⑥ 手臂垂放（40°~120°：既不是 T-pose 也不举过头顶）
    #      ⑦ 循环闭合（首末帧差 <2°）⑧ .b64.js 派生件与源对账
    #    ⚠️ 别拿 Blender 的"2 个网格 / 42 未绑顶点"当红：那是导入器给 65 根骨骼造的显示形状，
    #       GLB 字节里没有它（rig-audit.py 已剔除，并在回执里点名）。
    ("数字人资产八条", ["-X", "utf8", "tools/codex-scripts/dh-asset-gate.py"]),
    # 🔴 2026-10-19 加（主人令「她的所有能力都要融合进触手…这样就不会出现缺失和断连」
    #    +「通电秒达，如果没秒到就是那里不通」）：
    #    ① 触手主干六腿：登记/分派/承载/资产/页面/记忆页 —— 每条能力缺一条就是断连（非零退出）
    #    ② 通电三层秒表：索引微秒级 · 门毫秒级 · 真调用在预算内（超预算 = 那处不通）
    ("触手主干六腿", ["-X", "utf8", "tools/codex-scripts/tentacle-trunk-check.py"]),
    ("通电秒达", ["-X", "utf8", "tools/codex-scripts/tentacle-pulse-check.py", "--sample", "4"]),
    # 🔴 2026-10-19 加（主人令「改一处之前，先分出触手盯住与它相连的所有地方」）：
    #    **多域监控的驱动轮** —— 这一条同时做两件事：
    #      ① 真跑一次 `sched_tick`（把到期调度跑掉；`impact_monitor` 每 3600s 就跑一遍
    #         影响面排行）。留痕：`schedule.run_forever` 至今**没有常驻调用方**，所以
    #         "每小时一次"必须有驱动轮才落地 —— 没有驱动轮的定时器 = 挂件（P15）。
    #      ② 真跑一次 `impact_check status`（图规模 + 连通性；图读不到就红，不许静默）。
    #    两件事都只读，不写生产盘（sched_tick 只会写它自己的 last_run_ts）。
    ("多域监控·定时轮", ["-X", "utf8", "tools/codex-scripts/impact-monitor-tick.py"]),
    # 🔴 2026-10-19 加（主人令「都要跑通闭环啊」）：**循环本身也得有人判**。
    #    `sched_define` 只登记、`monitor-once.py` 只一拍，真让它 24/7 转的是
    #    Windows 任务计划 GBT-MonitorLoop（每 2 分钟）。任务被停/被删/机器刚起来，
    #    在读数上和"一切正常"完全一样 —— 所以这一条专门判"心跳还新不新"（>600s 即红）。
    ("多域监控·循环活着", ["-X", "utf8", "tools/codex-scripts/monitor-loop-health.py"]),
]

JUDGMENTS = [
    # 🔴 2026-10-11 加（七步法第七步的挂点）：接外部件必须落一条机器判据，否则
    #    「接上了、后来悄悄坏了」没人知道。本件判的是 om-ai-lab/VLX-Flow 的接入：
    #    ① 钢印（接自哪、上游当前是否纯文档仓）② 三处齐（注册表 + 分派）
    #    ③ 两层记忆都在位（视觉缓存层四能力 + 语义记忆层）④ 真跑闭环（digest→recall）
    #    ⑤ **负控**：未列出的 op 必须 fail-closed。上游"还没放代码"时判**如实报缺**也算过。
    ("VLX-Flow 接入", "gbt_allinone.tests.test_vlx_flow_intake"),
    # 🔴 2026-10-11 加（主人令「重启机制下达一条硬性指令」：重启后必须接通上帝视角 +
    #    自检 + 把发现登记）—— 见 HEARTBEAT.md 顶部那一节。
    ("重启硬指令·三件齐", "gbt_allinone.tests.test_restart_mandate"),
    # 🔴 2026-10-11 加（主人令三条铁律：禁止脑补 / 必须带参 / 先纠错再回答）
    ("三条铁律", "gbt_allinone.tests.test_iron_rules"),
    ("能力总数一致", "gbt_allinone.tests.test_cap_total_consistency"),
    ("注入命令为真", "gbt_allinone.tests.test_prompt_commands_are_real"),
    ("安全段是真门", "gbt_allinone.tests.test_prompt_security_section"),
    ("自检命令可跑", "gbt_allinone.tests.test_awareness_guard_runs"),
    ("台账字段契约", "gbt_allinone.tests.test_progress_ledger_contract"),
    ("注入面诚实性", "gbt_allinone.tests.test_injection_honesty"),
    ("没有恒真判据", "gbt_allinone.tests.test_dead_judgments"),
    # 2026-09-27 加（主人令「启动的时候触手就是你的手」）：接线三判据 ——
    # ①登记↔分派 ②触手账断连=0 ③外部工作流插件三节点一个不差。
    # 起因：filmkit 曾"登记了没接线"，靠人扫出来；这条判据把它钉死成启动红。
    ("接线全连通", "gbt_allinone.tests.test_wiring_all_tentacles"),
    # 2026-09-27 加（主人令「源代码保护好、整理摆放好，别分路分叉」）：**源 ↔ 装 逐字节对账**。
    # 起因：技能有两个真身 —— 仓内 skills/ 是**源**，~/.agents/skills/ 是
    # **运行时真正读的那份**，而两者之间**从来没有任何工具对账**（全仓 grep 零命中）。
    # 实测：gbt-security 源 43K / 装 31K、差 1054 行 ⇒ 一整轮能力覆盖补丁只落在源上，
    # 运行时一个字节都没看见 —— 与 F18（「盘上对」被念成「生效了」）同型。
    # 2026-09-27 加（主人令「其他工具全部都要可控按键一个不漏的绑定好」）：**可控制面完整性**——
    # 每个装了的工具都必须有"它自己报出来的"可控制键清单（ffmpeg 628 · git 177 · python 302 ·
    # genoffice 19 · freebuff 3 · blender 2409 bpy 算子），且**消失的键必须为空**（断连报警）。
    # 2026-09-27 加（主人令「上帝之眼」）：眼睛能看见创作页面 · 两顾问权限机器可读 ·
    # **CodeBuddy 碰主项目必须被拒** · 每日汇报三清单每条带来源 · 计划与决策留痕。
    ("上帝之眼", "gbt_allinone.tests.test_gods_eye"),
    ("可控制面一个不漏", "gbt_allinone.tests.test_surface_bind"),
    ("技能源装不分叉", "gbt_allinone.tests.test_skills_install_sync"),
    # 2026-09-27 加（主人令「扫描和视觉的钩子全方位无死角覆盖…要不然扫来扫去都是故障」）：
    # 覆盖矩阵是**那一刻**的读数；这条判据守三件事：读数全绿 · 不过期 ·
    # **盘上顶层树数量与读数一致**（多一个目录 = 新增盲区，读数却看着全绿 —— 那正是"死角"）。
    ("覆盖无死角且新鲜", "gbt_allinone.tests.test_coverage_readings_fresh"),
    # 2026-09-27 加（主人令「新增能力全部都要与触手双向绑定…没实现却都没记录…随时都能感知到
    # 框架的所有状态」）：把那条规矩拆成可机检的四件事 —— 能力位三处齐 · 双向绑定 · 缺口必须
    # 有名有姓（state/unimplemented.json）· 六个面都读得出来。红了两条路：补接线，或登记缺口。
    ("新增能力双向绑定", "gbt_allinone.tests.test_cap_bind_bidirectional"),
    # 2026-09-25 加：云端那 4 批改动（令牌闸 / 作用面读数 / 拍平块数组 / 错误分档）
    # 因为**没部署**，云端一次都没跑过。本机离线验它，0.3 秒，不出一字节网。
    ("云端点闸行为", "gbt_allinone.tests.test_endpoint_gate"),
    # 2026-09-25 加：凭据红线（密钥不许明文落盘 · 没有密钥必须拒绝启动子进程）。
    # 起因是真出过事：config/mcporter.json 里被人直接写了一条明文 API key。
    ("密钥不许明文落盘", "gbt_allinone.tests.test_key_vault_autoread"),
    # 2026-09-25 加：**部署前接线对账**。deploy/cloud-10 是生产落点，而这个网一次都没部署过 ⇒
    # 任何"配置与代码对不上"都要等真部署那一刻才以 undefined 炸出来（那时已经在改远端了）。
    # 首跑就抓到两个真缺口（SANDBOX / AE：代码在读、配置里连名字都没出现过）。
    ("部署前接线对账", "gbt_allinone.tests.test_cloud_config_wiring"),
    # 2026-09-25 加：**未清故障的前提还成立吗**。第 37 轮发现 F1/F6 两条高危故障的
    # 前提（"4 批没部署"）早就不成立、却在账里挂了十几轮 ⇒ 故障清单会**无声腐烂**。
    # 这条判据让"前提垮了"在开机时就红，逼人回去改账，而不是让它继续挂着。
    ("未清故障前提复核", "gbt_allinone.tests.test_reverify_open_faults"),
    # 2026-09-25 加：**部署漂移对账的牙齿**（离线自检；联网那一侧不进判据 —— 判据不该依赖外网）。
    # 一个"比出来没差异"的对账器，很可能是因为它其实什么都没比 ⇒ 种五处差异看它逮不逮得住。
    ("部署漂移尺子有牙", "gbt_allinone.tests.test_cloud_deploy_drift"),
    # 2026-09-25 加：**密钥两份存量的对账**。主人令「密钥全部部署…可以自动读取」之后，
    # 密钥有了两份（User 作用域注册表 + DPAPI 保险箱）⇒ 两份就是两个真相源，轮换只改一处
    # 另一处就静默过期。**不是假想**：首跑就读出 `agnes` 已经分叉（库 sk-HX**** vs 注册表 sk-Oy****）。
    # 判据只判分类逻辑与读数自洽（**不判"必须无分叉"** —— 哪份是新的只有主人能定）。
    ("密钥两份存量对账", "gbt_allinone.tests.test_key_consistency"),
    # 2026-09-25 加：**cross_scan 的 V 维（视图对账）**。它此前只出现在维度声明里
    # （声称 10 维、实际 6 维能产出发现）；本轮真做出来，判据是**加减法要闭合**
    # （家根总项 == 六类之和），而不是只读一个数字。
    # 🔴 最要紧的是安全红线：`inventory.scan(fix=True)` 会**真删文件** ——
    #    用例用桩记录 kwargs，直接断言扫描器传的是 `fix=False`（「扫一下」不该改动任何东西）。
    ("视图对账且只读", "gbt_allinone.tests.test_cross_scan_v_dim"),
    # 2026-09-25 加：**满仓横扫的负载闸**。两次实跑证明：内存被压满时满仓横扫会出**假红**
    # （`FileNotFoundError [WinError 2]` 收集期就断 / 26 分钟跑不完），而假红会被当成"代码坏了"。
    # 这条判据守那道闸本身：低于阈值不许开跑 · 边界含等号 · 读不到要如实标注 · 闸必须在跑之前。
    ("横扫负载闸", "gbt_allinone.tests.test_run_all_tests_memory_guard"),
    # 2026-09-26 加（第 52 轮 · F17）：**提交前凭据自审这份工具本身**。
    # 起因是现读出来的：那份"强制"自审只存在于 `%TEMP%`（重启即无），
    # 而它的①号判据要读 `%TEMP%` 里一份**明文**密钥备份 ——
    # **防明文落盘的工具自己依赖一份明文落盘**，而上面那条「密钥不许明文落盘」却是绿的
    # （尺子只量了仓这半个屋子）。这条判据把工具钉在仓里、把①钉在保险箱上（不碰明文参照），
    # 并守住退出码契约：0 干净 / 1 命中 / 2 **自审没跑成**（含"保险箱是空的 ⇒ 一条都没比"）。
    ("凭据自审有牙且在仓里", "gbt_allinone.tests.test_precommit_secret_scan"),
    # 2026-09-26 加（第 53 轮 · F18）：**"盘上对"不等于"进了进程"**。
    # 起因是现读出来的：台账块 2026-09-25 21:03:15 加进宿主半边时**没动版本号**，
    # 而宿主代码只在进程启动时装载（进程起于 10:33:32）⇒ 进程里压根没有那块，
    # 主人要的「重启之后自动读取」一直没生效；可所有闸全绿 ——
    # **因为它们全都从盘上渲染，没有一条问过进程**。
    # 这条判据守的就是那条"问进程"的路：宿主自报 `contexts` · 验收单 ⑨ 比对 ·
    # 且两边名单**同源**（加了块没人验、或验了不存在的块，都要红）。
    ("上下文真的进了进程", "gbt_allinone.tests.test_live_context_wiring"),
    # 2026-09-26 加（第 55 轮）：**分批跑的覆盖必须现算并集**。
    # 第 51 轮我把全仓拆四批跑，然后把四批的数字并排一放就说全仓看过了 ——
    # 而批与批之间我还在加测试文件（124 → 125 → 126），**四批的「全 N 个」不是同一个 N**。
    # 那一轮真实覆盖是 62/125。这条判据守：缺文件必须红 · 跨批红必须并起来 ·
    # 说不出用例名的红也不许吞（写「未记到用例名」）· 超时不算红。
    ("满仓覆盖按并集现算", "gbt_allinone.tests.test_sweep_union_coverage"),
]

DRIFT_GATE = ROOT / "plugins" / "gbt-master" / "tools" / "verify-installed-copy.mjs"
SHEET = ROOT / "plugins" / "gbt-master" / "tools" / "verify-after-restart.py"


def _env(store: str) -> dict:
    e = dict(os.environ)
    e["GBT_STORE_DIR"] = store
    e["PYTHONIOENCODING"] = "utf-8"
    # 🔴 2026-09-26 自纠：环境里残留的 PYTHONPATH 会把注入面测成假红
    #    （run-all-tests.py 里的一手实录）。这里跑的是同一批 unittest 模块，
    #    却没做同样的环境清洁 —— 现在补上，同一条判据同一条规矩。
    e.pop("PYTHONPATH", None)
    return e


def _run(cmd: list, env: dict, timeout: int = 600) -> tuple:
    try:
        p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, env=env)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "timeout>%ss" % timeout
    except Exception as e:                                       # noqa: BLE001
        return 125, "%s: %s" % (type(e).__name__, str(e)[:160])


# ── 2026-10-13 加（主人令：「触手绑定每一页代码…全量绑定好的一起并发不可能达不到的」）────────
# 🔴 现读病象：27 条 unittest + 5 条政策判据 + node 漂移闸 + 验收单**全串行**跑
#    （每条超时上限 600s）⇒ 实测 **457.5 秒**。它们**互不依赖**（各自独立子进程、各自隔离 store）
#    ⇒ 本来就该并发。下面把「要点哪些判据」抽成**一份计划**（**只点名，不复制实现**），
#    顺序执行与并发执行**共用这一份**。
def _plan(quick: bool = False) -> list:
    """判据计划（顺序即展示顺序）。每条：cat 分类 · step 展示名 · argv 真命令 · cmd 展示串 · kind。"""
    plan = []
    for label, mod in JUDGMENTS:
        plan.append({"cat": "判据", "step": "判据/" + label, "kind": "unittest",
                     "argv": [sys.executable, "-m", "unittest", mod],
                     "cmd": "python -m unittest %s" % mod, "timeout": 600})
    for _label, _argv in EXTRA_JUDGMENTS:
        plan.append({"cat": "政策判据", "step": "判据/" + _label, "kind": "script",
                     "argv": [sys.executable] + list(_argv),
                     "cmd": " ".join([sys.executable] + list(_argv)), "timeout": 300})
    if DRIFT_GATE.is_file():
        plan.append({"cat": "闸", "step": "闸/装机副本漂移", "kind": "drift",
                     "argv": ["node", str(DRIFT_GATE)],
                     "cmd": "node plugins/gbt-master/tools/verify-installed-copy.mjs",
                     "timeout": 180})
    else:
        plan.append({"cat": "闸", "step": "闸/装机副本漂移", "kind": "missing_gate",
                     "argv": [], "cmd": str(DRIFT_GATE), "timeout": 0})
    # 🔴 2026-10-22 加（Owner 令「按照专业化来推进」；当天页面卡死排查把真因拆成四处）：
    #    模型车道（Chip「GBT小土豆V8 原生 · 云上拼接网 · 身份注入」）此前没有任何常设判据 ——
    #    端点常驻参数（workersMin/idleTimeout）、引擎窗口、Worker 自权重接线、鉴权 fail-closed、
    #    SSE 必须带 finish_reason+[DONE]、秒级闸、带 tools 仍能收尾，全靠临时脚本各测一半，
    #    于是「每轮冷启动 92~300 秒」和「maxTokens 256000 撞 1M 上下文墙」都活过了很多轮。
    #    这条把它们收成一次执行、一个退出码（判据本体只在 lane-doctor.py 里一份）。
    #    它要真打端点 ⇒ 与「重启验收单」同类：`--quick` 跳过（**跳过不是通过**）。
    #    离线不判红：lane-doctor 带 --gate，把「连不上」降 WARN；契约坏仍是 FAIL。
    # 🔴 2026-10-24 换闸（主人令逐字：「这个要花钱我们不需要直接清理了就没卡点了」）：
    #    旧闸判的是 RunPod **自有权重**车道，该车道已按令清理 ⇒ 再判它永远红，
    #    而红的原因已经不是"坏了"而是"不做了" —— **判据必须量在役的东西**。
    #    现役车道 = 免费道（Cloudflare Workers AI / Agnes），新闸 3 条：
    #      L1 桥在役且默认是免费道 · L2 真出话（非空）· L3 口径明示 weights_ours=false。
    #    自有权重车道将来恢复时，把本步换回 lane-doctor 即可（两份判据都留着）。
    if quick:
        plan.append({"cat": "闸", "step": "闸/模型车道（现役免费道）", "kind": "skipped",
                     "argv": [], "cmd": "（--quick 跳过）", "timeout": 0})
    else:
        plan.append({"cat": "闸", "step": "闸/模型车道（现役免费道 · 3 条）", "kind": "script",
                     "argv": [sys.executable, "-X", "utf8",
                              "tools/codex-scripts/lane-gate-free.py"],
                     "cmd": "python tools/codex-scripts/lane-gate-free.py",
                     "timeout": 180})
    # 🔴 2026-10-22 加（D3 的尺子挂成常设判据）：
    #    「规程缺口」此前只有台账里一句**无法复跑**的「5 处」；现在有量具 `spec-gap-scan.py`
    #    （现算：341 位 / 30 域 / 缺口 149 位）。这条**不是**判「缺口=0」（缺口归 D3 由主人定补法），
    #    而是判 **尺子本身能跑**：脚本能起、能现算、能落回执 —— 量具烂掉要立刻看见，
    #    否则下一轮又会拿一句旧数字当读数（P9：账没有写手必烂）。
    plan.append({"cat": "判据", "step": "判据/规程缺口量具可复跑", "kind": "script",
                 "argv": [sys.executable, "-X", "utf8",
                          "tools/codex-scripts/spec-gap-scan.py"],
                 "cmd": "python tools/codex-scripts/spec-gap-scan.py", "timeout": 180})
    # 🔴 2026-10-22 加（把「账实一致」也变成常设判据）：
    #    护照是"我声称改了什么 + 证据 + 回滚"，但**没有东西会去核对它是否还成立** ——
    #    件被删了、证据变成空话、回滚写得像口号，门都看不见（门只看"有没有护照"）。
    #    这条逐张查五件事：件在盘 / 证据含 `命令 => 读数` / 回滚 ≥8 字 / 有复核或`--no-review-reason` /
    #    有印章或`--no-stamp-reason`。**只查今天关闭的护照**（历史账见 F22，已明示登记，不重算）。
    plan.append({"cat": "判据", "step": "判据/护照账实一致（今日关闭的）", "kind": "script",
                 "argv": [sys.executable, "-X", "utf8",
                          "tools/codex-scripts/passport-audit.py", "--today"],
                 "cmd": "python tools/codex-scripts/passport-audit.py --today", "timeout": 180})
    if quick:
        plan.append({"cat": "闸", "step": "闸/重启验收单", "kind": "skipped",
                     "argv": [], "cmd": "（--quick 跳过）", "timeout": 0})
    elif SHEET.is_file():
        plan.append({"cat": "闸", "step": "闸/重启验收单", "kind": "sheet",
                     "argv": [sys.executable, str(SHEET)],
                     "cmd": "python plugins/gbt-master/tools/verify-after-restart.py",
                     "timeout": 300})
    else:
        plan.append({"cat": "闸", "step": "闸/重启验收单", "kind": "missing_sheet",
                     "argv": [], "cmd": str(SHEET), "timeout": 0})
    return plan


def _post(entry: dict, rc: int, out: str) -> dict:
    """把一次执行结果**按类**翻成 step 读数（口径与原有逐条逻辑一字不差）。"""
    kind, out = entry["kind"], (out or "")
    base = {"step": entry["step"], "cat": entry["cat"], "cmd": entry["cmd"], "rc": rc}
    if kind == "unittest":
        tail = [ln for ln in out.splitlines() if ln.startswith(("OK", "FAILED", "Ran "))][-2:]
        base.update({"ok": rc == 0, "now": " · ".join(tail[-2:]) or out.strip()[-160:]})
    elif kind == "script":
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        na = (rc == 3)
        base.update({"ok": rc in (0, 3), "not_applicable": na,
                     "now": ("**不适用（rc=3 ≠ 失败）**：" + (lines[-1][:120] if lines else ""))
                            if na else (lines[-1][:160] if lines else out.strip()[-160:])})
    elif kind == "drift":
        base.update({"ok": rc == 0,
                     "now": ("逐字节一致" if rc == 0 else (out.strip().splitlines() or ["?"])[0][:160])})
    elif kind == "missing_gate":
        base.update({"ok": False, "now": "漂移闸不在盘上 —— 不许当跳过"})
    elif kind == "skipped":
        base.update({"ok": True, "now": "本次被 --quick 显式跳过（不是通过）"})
    elif kind == "missing_sheet":
        base.update({"ok": False, "now": "验收单不在盘上 —— 不许当跳过"})
    else:                                    # sheet：把 ⏳ 逐名读出来（容差只留 ⑤）
        pending = [ln.strip().lstrip("⏳").strip()
                   for ln in out.splitlines() if ln.strip().startswith("⏳")]
        ok = all(p.startswith(("⑤",)) for p in pending) if pending else True
        concl = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("结论")]
        now = (concl[0][:120] if concl else out.strip()[-160:])
        if pending:
            now += " · 待到位=%s" % "、".join(pending)
        base.update({"ok": (rc == 0 and ok), "now": now})
    return base


def _auto_jobs() -> int:
    """并发度自动定（主人令 2026-10-19：「主脑和所有触手相连 ⇒ 自检瞬间无死角」+「按量化使用激活· 没启用的静默不占内存」）。

    口径（主人令定稿，逐字）：「需要用那个能力触手精准直达激活，用完自动静默，所以她运行内存可以是 7.4G」。
      ⇒ **内存不是并发上限**：没启用的触手/能力是静默的、不占内存，所以不该拿"总内存÷每条 X GB"去限并发
        （那是按"全部同时点火"算，与设计不符）。现口径：**按 CPU 核数满扇出**（12 核就 12 路），
        留 `--jobs N` 显式覆盖，`--jobs 1` 回到老行为串行。
      · 留痕：本函数前两版都被主人纠过 —— 第一版按内存折算（算成 1–3），第二版加了 0.35 GB 保险丝；
        两版都是把"静态预分配"的思路套到"按需激活"的架构上。读数也证明瓶颈不在内存：
        串行 268 s → 并发 2 路 110 s → 并发 8 路 61.7 s。
    """
    try:
        import os
        cores = os.cpu_count() or 2
    except Exception:
        cores = 2
    return max(1, min(12, cores))


def _run_plan(plan: list, env: dict, jobs: int) -> dict:
    """跑计划。`jobs<=1` = 顺序（老行为）；`jobs>1` = **并发**（各自独立子进程，互不依赖）。

    🔴 并发度是**内存**定的不是 CPU 定的：本机 12 核但空闲内存常只剩 0.4–0.7 GB，
    这些判据里有会吃几百 MB 的（torch/onnx 那类）⇒ 默认给保守值，`--jobs` 可调。
    """
    todo = [e for e in plan if e["kind"] not in ("skipped", "missing_gate", "missing_sheet")]
    res: dict = {}

    def _timed(argv, env_, timeout):
        # 🔴 逐条耗时必须在**工人自己身上**量 —— 首版在工作线程收结果时量，
        #    结果全是 0.0（量的是"取结果"那一刻，不是"跑"那一刻）。真读数咬出来的。
        t = time.time()
        rc, out = _run(argv, env_, timeout)
        return rc, out, round(time.time() - t, 1)

    if jobs and jobs > 1 and len(todo) > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=int(jobs)) as ex:
            futs = {ex.submit(_timed, e["argv"], env, e["timeout"]): i for i, e in enumerate(todo)}
            for f in concurrent.futures.as_completed(futs):
                i = futs[f]
                try:
                    rc, out, secs = f.result()
                except Exception as exc:                          # noqa: BLE001
                    rc, out, secs = 125, "%s: %s" % (type(exc).__name__, str(exc)[:160]), 0.0
                res[i] = (rc, out, secs)
    else:
        for i, e in enumerate(todo):
            res[i] = _timed(e["argv"], env, e["timeout"])
    return res


def _panel_html(rep: dict) -> str:
    """**分类显示面板**（自包含单文件 · 无任何外链/外网引用 —— 本仓铁律）。

    主人令原话：「扫到的结果返回组成一张分类显示面板就好了啊」。
    """
    cats = dict.fromkeys(s.get("cat") or "其他" for s in rep["steps"])
    head = ("<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
            "<title>GBT小土豆V8 · 自检面板</title><style>"
            ":root{--ok:#0a7d3c;--bad:#c0392b;--ink:#1c1c1e;--mut:#6b6b70;--line:#e6e6ea}"
            "*{box-sizing:border-box}body{margin:0;padding:28px 32px;background:#fafaf9;"
            "color:var(--ink);font:14px/1.5 -apple-system,'Segoe UI','Noto Sans SC',sans-serif}"
            "h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:26px 0 8px;"
            "padding-bottom:6px;border-bottom:1px solid var(--line)}"
            ".sum{display:flex;gap:22px;flex-wrap:wrap;margin:14px 0 4px}"
            ".sum b{font-size:22px}.mut{color:var(--mut)}"
            "table{border-collapse:collapse;width:100%;margin-top:8px}"
            "th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);"
            "vertical-align:top}th{color:var(--mut);font-weight:600;font-size:12px}"
            "td.s{white-space:nowrap;color:var(--mut);font-variant-numeric:tabular-nums}"
            ".ok{color:var(--ok);font-weight:600}.bad{color:var(--bad);font-weight:600}"
            "code{background:#f1f1f3;padding:1px 5px;border-radius:4px;font-size:12px}"
            "</style></head><body>")
    parts = [head, "<h1>GBT小土豆V8 · 自检面板</h1>",
             "<div class=\"mut\">按分类展示 · 逐条带耗时 · 只调既有判据（不重写第二份）</div>",
             "<div class=\"sum\">",
             "<div><b>%d</b><div class=\"mut\">环节</div></div>" % len(rep["steps"]),
             "<div><b class=\"%s\">%d</b><div class=\"mut\">红</div></div>"
             % ("ok" if not rep["red_count"] else "bad", rep["red_count"]),
             "<div><b>%.1f</b><div class=\"mut\">秒（墙钟）</div></div>" % rep.get("wall_seconds", 0),
             "<div><b>%d</b><div class=\"mut\">并发度</div></div>" % rep.get("jobs", 1),
             "</div>"]
    for c in cats:
        items = [s for s in rep["steps"] if (s.get("cat") or "其他") == c]
        reds = sum(1 for s in items if not s["ok"])
        parts.append("<h2>%s <span class=\"mut\">%d 条 · <span class=\"%s\">红 %d</span></span></h2>"
                     % (escape(str(c)), len(items), "ok" if not reds else "bad", reds))
        parts.append("<table><tr><th>状态</th><th>环节</th><th>秒</th><th>读数</th></tr>")
        for s in items:
            secs = s.get("seconds")
            parts.append("<tr><td class=\"%s\">%s</td><td>%s</td><td class=\"s\">%s</td>"
                         "<td>%s<br><code>%s</code></td></tr>"
                         % ("ok" if s["ok"] else "bad", "✅" if s["ok"] else "🔴",
                            escape(s["step"]),
                            ("%.1f" % secs) if isinstance(secs, (int, float)) else "—",
                            escape(s.get("now", "")[:300]), escape(s.get("cmd", "")[:160])))
        parts.append("</table>")
    parts.append("</body></html>")
    return "".join(parts)


def selfcheck(quick: bool = False, jobs: int = 1, panel: str = "") -> dict:
    # 🔴 2026-09-26 自纠：原来用固定共享路径 %TEMP%/gbt_boot_selfcheck_store ——
    #    两次自检并发会共享同一 store（读数互相污染），且跨次运行累积不清理，
    #    "隔离 store"只隔离了生产，没隔离上一次自己。现在每检一次一间新屋。
    store = tempfile.mkdtemp(prefix="gbt_boot_selfcheck_store_")
    env = _env(store)
    # 🔴 2026-10-13：判据计划抽成**一份** `_plan()`（顺序执行与并发执行共用），
    #    逐条读数口径一字未改（挪进 `_post()`）。`jobs>1` 即并发。
    plan = _plan(quick)
    t0 = time.time()
    res = _run_plan(plan, env, jobs)
    wall = round(time.time() - t0, 1)
    steps, i = [], 0
    for entry in plan:
        if entry["kind"] in ("skipped", "missing_gate", "missing_sheet"):
            steps.append(_post(entry, 0 if entry["kind"] == "skipped" else 127, ""))
            continue
        rc, out, secs = res[i]
        i += 1
        st = _post(entry, rc, out)
        st["seconds"] = secs
        steps.append(st)
    bad = [s for s in steps if not s["ok"]]
    result = {
        "ok": not bad, "readonly": True, "steps": steps, "red_count": len(bad),
        "store": store, "jobs": int(jobs), "wall_seconds": wall,
        "by_cat": {c: {"n": sum(1 for s in steps if s.get("cat") == c),
                       "red": sum(1 for s in steps if s.get("cat") == c and not s["ok"])}
                   for c in dict.fromkeys(s.get("cat") for s in steps)},
        "note": ("只调既有判据与既有脚本，**不重写第二份**；任何一段跑不动都算红，"
                 "不许记成跳过。测试在隔离 store 里跑（进程启动前设好 GBT_STORE_DIR）。"),
    }
    if panel:
        try:
            p = Path(panel)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(_panel_html(result), encoding="utf-8")
            result["panel"] = str(p)
        except Exception as _e:                                 # noqa: BLE001
            result["panel_error"] = "%s: %s" % (type(_e).__name__, str(_e)[:120])
    # 🔴 2026-10-11 加（主人令「重启之后必须查看框架使用以及自动自检」）——**落痕**：
    #    实测本件跑了十几次，而 state/ 下**一个痕迹都没有** ⇒ 重启硬指令的判据
    #    （tools/codex-scripts/restart-mandate-check.py）**根本无从判断"自检做没做"** ——
    #    这正是主人说的「重启再问她她都不懂了」。
    #    ⇒ 每次跑完落一份**可机读**的痕：时刻 + 结论 + 红数 + 逐条红名。
    #    只读口径不变（它只写自己的落痕，不碰被监视的框架件）。
    try:
        trace = ROOT / "state" / "boot-selfcheck-last.json"
        trace.parent.mkdir(parents=True, exist_ok=True)
        trace.write_text(json.dumps({
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "ok": result["ok"], "red_count": result["red_count"],
            "reds": [s["step"] for s in result["steps"] if not s["ok"]],
            "steps": len(result["steps"]), "jobs": result["jobs"],
            "wall_seconds": result["wall_seconds"],
        }, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:                                               # noqa: BLE001
        pass
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="开机自检（只读）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quick", action="store_true", help="跳过重启验收单")
    ap.add_argument("--jobs", type=int, default=_auto_jobs(),
                    help="并发度：默认按可用内存自动定（主脑扇出、触手同时回话）；1=顺序（老行为）")
    ap.add_argument("--panel", default="", help="把结果落成一张**分类显示面板**（自包含 HTML）")
    a = ap.parse_args(argv)
    rep = selfcheck(quick=a.quick, jobs=a.jobs, panel=a.panel)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print("═══ 开机自检 · %s ═══" % ROOT)
        print("  并发度 %d · 墙钟 %.1f 秒 · 分类：%s"
              % (rep["jobs"], rep["wall_seconds"],
                 " · ".join("%s %d(红 %d)" % (c, v["n"], v["red"])
                            for c, v in rep["by_cat"].items())))
        for s in rep["steps"]:
            print("  %s %-18s %6s秒  %s"
                  % ("✅" if s["ok"] else "🔴", s["step"],
                     ("%.1f" % s["seconds"]) if isinstance(s.get("seconds"), (int, float)) else "—",
                     s["now"][:96]))
        print("-" * 78)
        print("结论：%s（红 %d 条）" % ("全绿" if rep["ok"] else "有红", rep["red_count"]))
        if rep["red_count"]:
            for s in rep["steps"]:
                if not s["ok"]:
                    print("  🔴 %s —— 怎么办：%s" % (s["step"], s["cmd"]))
        print("边界：%s" % rep["note"])
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
