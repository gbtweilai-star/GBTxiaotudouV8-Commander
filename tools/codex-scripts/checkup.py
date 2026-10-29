#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""checkup · 一条命令出**体检报告**（把巡检串起来）

## 为什么要有它
「可生产」不是"曾经验过一次"，而是**每天都能一条命令证明它还活着**。
本器把**已存在的闸逐条串成一条**（条数**现算**，见 `_steps()`；曾经这里写死"五道"，
后来又写死"20 道"，**每一次增长都会让写死的数字变成假的**），并把结果落成**带时间戳的报告**：

    ① lint_cjk_quotes  —— 中文串 ASCII 引号（我犯过 15 次的语法崩）
    ② nerve selftest   —— 神经总线自检（覆盖/痛觉/能力位层/真探层）
    ③ deploy-panel selftest —— 主控面板自检（顺序门/排班/编号/图一致）
    ④ nerve caps --drift    —— **能力位健康漂移**（与基线比，只报"变坏"）
    ⑤ gen-scope-page   —— 刷新「待授权清单一页」
    …（其余见 `_steps()`：**这个列表只是历史注释，不是权威**，权威是代码里的表）

**判据**：任一步 rc≠0 ⇒ 整体 rc≠0（**fail-closed**），且**逐条列出谁的 rc 是多少**——
不合并成一句"体检失败"（那样读的人还得自己猜是哪一道）。

## 它不做什么
- **不装计划任务**：计划任务是**机器级配置** ⇒ 要主人点头。本器只**产出报告**，
  并打印可直接用的调度命令（见报告末尾），**装不装由主人定**。
- 不自动修任何东西：**只读 + 只写报告**。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# `parents[2]`，不是 `[1]`：本文件在 `tools/codex-scripts/` 下，仓库根要往上三级。
#    实测踩过（本轮）：写成 `parents[1]` ⇒ ROOT 指到 `tools/`，**当时那几道闸**全部 rc=2
#    （报 `tools\tools\codex-scripts\...` 打不开）。**搬文件会改 `parents[N]` 的含义。**
ROOT = pathlib.Path(__file__).resolve().parents[2]
S = ROOT / "tools" / "codex-scripts"
# 2026-10-09 根因修复：原来 PY 只有 [sys.executable]，**不带 -X utf8** ⇒
#    子进程在 GBK 控制台上打中文就崩（UnicodeEncodeError: 'gbk' codec can't encode），
#    于是一大批闸报 rc≠0 —— **那是假故障**（脚本单跑都是好的，实测对比过）。
#    utf8 模式是进程级的总开关，一处修好，所有子进程都干净。
PY = [sys.executable, "-X", "utf8"]


def _steps() -> list[tuple[str, list[str], str]]:
    """(名字, 命令, 判据说明)。顺序固定 —— 便宜的在前，贵的在后。"""
    return [
        ("lint 中文串引号", PY + [str(S / "lint_cjk_quotes.py"), "tools/codex-scripts"],
         "rc=0（0 命中）"),
        ("神经总线自检", PY + [str(S / "nerve.py"), "selftest"], "rc=0（全绿）"),
        ("主控面板自检", PY + [str(S / "deploy-panel.py"), "selftest"], "rc=0（全绿）"),
        ("触手名册自检", PY + [str(S / "tentacle-registry.py"), "selftest"], "rc=0（负控全咬）"),
        ("触手名册完整", PY + [str(S / "tentacle-registry.py"), "verify"],
         "rc=0（连号·链·锚点·身份唯一）"),
        ("署名覆盖面自检", PY + [str(S / "signature_coverage_audit.py"), "--selftest"],
         "rc=0（判据分得开页面/数据/夹具）"),
        ("署名覆盖面闸", PY + [str(S / "signature_coverage_audit.py"), "--gate"],
         "rc=0（可盖章树全页带署名）"),
 # 2026-09-25 补挂：**判据的判据**。仓里已有三次「控制是装饰」的事故
        #    （写死条数恒假 · 闸漏整棵树 · 抽样恒 None）。这道闸**真把靶打坏**再验：
        #    改坏必须见红、改不坏必须说「没咬住」、改崩不许当咬住、锚点不唯一一律拒。
        #    挂的是「跑真规格」，不只是自检 —— 自检只证明这台机器会咬，不证明**这份规格**在咬。
        ("突变证明自检", PY + [str(S / "mutation-proof.py"), "selftest"],
         "rc=0（真刀/假刀/锚点重复/锚点不在/红错地方/改崩 六类都分得开）"),
        ("突变证明（真打坏再验）", PY + [str(S / "mutation-proof.py"), "run"],
         "rc=0（每把刀都咬住点名的那条控制 · 原件逐字节未改 · 零残留）"),
 # 2026-09-25 补挂：证据账（`memory/在办清单.md`）是**只追加**的，而有四个真风险
        #    人工看不出来：署名被挤到中间 · 写盘偷翻换行 · **真账本是 CRLF**（按 `\n` 找分隔线
        #    会一插就拒）· 插入点靠猜。挂「自检 + 现读真账本」两条，闸的就是这四条。
        ("账本追加自检", PY + [str(S / "ledger-append.py"), "selftest"],
         "rc=0（LF/CRLF 两个正控 + 空章节/署名在中间/没署名/没分隔线/混用换行 五类负控都咬）"),
        ("账本现读（只追加账本）", PY + [str(S / "ledger-append.py"), "check"],
         "rc=0（署名在最后一条非空行 · 换行均匀）"),
        ("自身融合层自检", PY + [str(ROOT / "tools" / "self_model.py"), "selftest"],
         "rc=0（每块带出处 · 未读到≠0 · 只读）"),
        ("模型面接缝", PY + [str(S / "model_roster.py"), "gate"],
         "rc=0（缝差不算越界 · 凭据不泄）"),
        ("缺参位安全探针", PY + [str(S / "probe_needparam.py"), "selftest"],
         "rc=0（表外拒 · needs_* 不判痛）"),
        ("影像生产面现读", PY + [str(S / "comfy-surface.py"), "selftest"],
         "rc=0（算力现读 · 视频 0 不吹 · 只读）"),
        ("判据质量台架", PY + [str(S / "criterion_bench.py"), "gate"],
         "rc=0（**一次扫描**：自检全过 + 棘轮没变坏）"),
        ("分短视频拼接（真跑）", PY + [str(S / "shorts-stitch-proof.py"), "run"],
         "rc=0（走唯一门 · 实测时长==预期 · 无残留）"),
 # 2026-09-25 补挂：那条「取不到读数时报真因」的**诚实分支**原来长在 run 里、
        #    **从未被触发过** —— 真触发才发现它 `NameError`。抽成 `why_no_reading()` 之后
        #    四种出口各一条负控。**未验分支 = 待爆的雷**，所以它得单独进体检。
        ("诚实分支（取不到读数的真因）", PY + [str(S / "shorts-stitch-proof.py"), "selftest"],
         "rc=0（四种出口都验过：不可用/缺表/不是对象/追因自己炸）"),
 # 2026-09-25 补挂：**未验分支猎手**。§一百五十八 逮到一条真雷（诚实分支里 `NameError`），
        #    于是把"这条诚实读数到底有没有被控制走到过"变成机器可查。
 # 它量的是**候选**（自检可以间接覆盖）⇒ 挂的两条只保证：
        #    ① 猎手自己分得开（10 条自检）；② **候选不许变多**（新写的诚实读数必须配控制）。
        ("未验分支猎手自检", PY + [str(S / "honest-branch-audit.py"), "selftest"],
         "rc=0（正控/负控/五类边界都分得开）"),
        ("未验分支棘轮", PY + [str(S / "honest-branch-audit.py"), "gate"],
         "rc=0（候选没变多；未立基线一律 rc=2，不许念成合格）"),
 # 2026-09-25 补挂（主人令「把限制去掉、改为人工授权」）：要防的**不是"门多"**，
        #    而是**"有一道授权不了的门"** —— 门里有、可授权清单里没有 ⇒ 主人也发不出授权
        #    ⇒ 对调用者是**永久不可授权** = 变相禁止（本仓 09-15/09-18/09-19 各栽过一次）。
        ("授权面形状自检", PY + [str(S / "auth-shape.py"), "selftest"],
         "rc=0（负控：伪造一道授权不了的门 ⇒ 必须点名）"),
        ("授权面形状（不许有授权不了的门）", PY + [str(S / "auth-shape.py"), "check"],
         "rc=0（门侧 ⊆ 可授权侧；只读，不发任何授权）"),
 # 2026-09-25 补挂（主人令「千万不能出现拒绝的限制，去干净点」）：
        #    先把词分清 —— **授权型 = 门（主人授权可过）** ≠ **硬拒型 = 谁都过不去**。
        #    这道闸只管**门面上**（能力门 + 分派 + 生产写入那条链）的硬拒**不许变多**；
        #    护栏（`*/tools/must_*` 之类质量判据）单列，**不算限制**。
        ("拒绝普查自检", PY + [str(S / "refusal-census.py"), "selftest"],
         "rc=0（授权型/硬拒型/未实现不算拒/门面与护栏分得开 + 棘轮四条出口）"),
        ("拒绝普查棘轮（门面硬拒不许变多）", PY + [str(S / "refusal-census.py"), "gate"],
         "rc=0（门面新增「谁都过不去」的拒绝 ⇒ 红，要么改成人可授权的门、要么写原因重立）"),
 # 2026-09-25 补挂（主人令「限制全改人工授权」的前置）：改「硬拒 → 授权即过」之前，
        #    先把**未授权路径的当前行为**逐条钉住（18 条纯校验探针，不落盘）。
        #    改完再量一遍：**差异必须逐条说得出来** —— 没差异才叫"未授权路径零影响"（= 回滚面）。
        ("等价面自检（改硬拒前先钉行为）", PY + [str(S / "refusal-equivalence-probe.py"), "selftest"],
         "rc=0（拒/过两种读数都取到 · 不可直探的如实列出 · 人为改一条必须点名）"),
        ("等价面现读（未授权路径行为不许变）", PY + [str(S / "refusal-equivalence-probe.py"), "check"],
         "rc=0（与基线逐条一致；未钉基线一律 rc=2）"),
        ("插件全互通矩阵", PY + [str(S / "plugin-mesh.py"), "selftest"],
         "rc=0（N×(N-1) 全覆盖 · 无通道点名）"),
        ("防忘清单自检", PY + [str(S / "forget-list-check.py"), "selftest"],
         "rc=0（判据精确 · 4 条负控）"),
        ("防忘清单可核", PY + [str(S / "forget-list-check.py"), "check"],
         "rc=0（引用的路径/行号/§ 全在 · 不超长）"),
        ("safe=False 只读探针", PY + [str(S / "probe-safefalse.py"), "selftest"],
         "rc=0（只读 op 白名单 · dry_run 专属 · 不探的也上账）"),
        ("零作用域交叉审计", PY + [str(S / "zero-scope-audit.py"), "selftest"],
         "rc=0（两源对撞 · 危险集逐位点名）"),
 # 2026-09-24 补挂：这两件**早就有自检，却一直没进体检** ⇒ 破了「位级写目标」
        #    两次（先 `p.get(` 抽错、后切片吞注释 9/9 全 None）**体检都不会响**。
        #    自检不进体检 = 自检等于没写。顺序不能倒：kinds **单一来源**吃 audit 的 scan()。
        ("门盲区逐位标记", PY + [str(S / "gate-blind-audit.py"), "selftest"],
         "rc=0（带牙/软分得开 · 退化负控在咬）"),
        ("位级写目标抽样", PY + [str(S / "gate-blind-kinds.py"), "selftest"],
         "rc=0（9 位全抽到函数 · 递归一层有正控+边界控）"),
 # 2026-09-24 补挂：体检器**自己那条判据**曾经长成恒假（写死 `== 5`），
        #    而它挂在神经末梢 P25 上 ⇒ **红到没人看**。自检不进体检 = 自检等于没写。
        #    自身那道 `--selftest` **不重跑体检**（只调 `_self_check`）⇒ 不会递归。
        ("体检器自检", PY + [str(S / "checkup.py"), "--selftest"],
         "rc=0（条数没写死 · 缺脚本/空表/不成形三类负控都咬）"),
 # 2026-09-25 事故后补挂：能力注册表**会被反复改写坏**（写手未查明）。
        #    挂在这里的意义：**坏了要点得出名**，并且红字里直接带着复原命令 ——
        #    而不是让 5 道闸各红一次、报一堆离根因三层远的 KeyError。
        ("能力注册表哨兵", PY + [str(S / "caps-registry-guard.py"), "check"],
         "rc=0（可导入 · all_caps=168 · DISABLED=0 · UNIMPL>=11）；红了就照红字复原"),
 # 2026-09-25 补挂（主人立项「无限制创作流水线」）：红线 2 的词表**留空是刻意状态**，
        #    这道闸保证「空词表」永远不会被念成「审过了」（**未接线 ≠ 合规**）。
        ("红线2 词表哨兵", PY + [str(S / "wordlist-guard.py"), "check"],
         "rc=0（未接线也如实报；空表却报「通过」才会红）"),
 # 2026-09-25 补挂：流水线**动手前的前置检查**。挂的是**判据自检**（4 条正负控），
        #    不是那个会 BLOCK 的 `check`（前置条件真没满足时它 rc=3，挂上去会让体检长期带红）。
        ("流水线前置判据", PY + [str(S / "pipeline-preflight.py"), "selftest"],
         "rc=0（四绿才 READY · 缺一条必 BLOCKED · 未读到不许当满足）"),
 # 2026-09-25 补挂（主人令：专属大模型要对标对齐 + 所有运行读它）：
        #    这两件一个管「所有运行读的是不是同一个模型门」，一个管「别人给的插件名是不是真的」。
        ("大模型对标对齐卡", PY + [str(S / "gbt-model-align.py"), "selftest"],
         "rc=0（唯一门有负控 · 宣传语不当读数 · 未读到不冒充）"),
        ("插件名单核对", PY + [str(S / "dsh-plugin-audit.py"), "selftest"],
         "rc=0（真件判在 · 编的判不在 · 我写的对照件名也现读核过）"),
        ("能力位漂移", PY + [str(S / "nerve.py"), "caps", "--drift"], "rc=0（无变坏）"),
 # 2026-09-25 补挂（主人令「不部署在本地，直接以模块化部署在云插件上，再做 10 插件拼接运行」）：
        #    这一簇把「10 位 × 其余 9 位 = 90 条边」从一句话变成**表 + 件 + 对账**三件套。
        #    ① 自检：真源合格性 / 漂移检测 / 边读数 / 模板占位符 / 身份掩码 —— 33 项含负控；
        #    ② 对账：`mesh.json`（单一真源）与生成件逐字段比，**表改了件没改必须点名**；
        #    ③ 边读数：90 条按模块数**现算**（不写死）；④ 形状验收：10 位在不在、90 条通不通、
        #    门开不开（授权前 403 / 授权后 200 / 宽度不外溢 / 读写作用域分开 / 门开了没接线仍拒）；
        #    ⑤ 可部署性走**离线**口径 —— 真云侧现读（whoami/list）按需手跑，
        #    **不许让整个体检依赖 Cloudflare 可达**，否则网一抖体检全红、红因还离根因很远。
        ("10 云插件拼接网自检", PY + [str(S / "cloud-mesh.py"), "selftest"],
         "rc=0（真源/漂移/边/占位符/掩码/真跑判决 等 60 项含负控）"),
        ("10 云插件拼接网对账", PY + [str(S / "cloud-mesh.py"), "check"],
         "rc=0（表↔件无漂移 · 件里相对 import 全指得到）"),
        ("10 云插件拼接网边读数", PY + [str(S / "cloud-mesh.py"), "edges"],
         "rc=0（有向边=模块数现算 · 每位绑其余 9 位 · 无自环 · 双向对称）"),
        ("10 云插件拼接网形状验收", ["node", str(ROOT / "deploy" / "cloud-10" / "tools" / "run-mesh-local.mjs")],
         "rc=0（43 项全过 · 门分两层 · 不碰主人原有键）"),
        ("10 云插件拼接网可部署性（离线）", PY + [str(S / "cloud-mesh.py"), "readiness", "--no-live"],
         "rc=0（生效占位符清零 · 注释处说明留存 · 不断言云侧可达）"),
 # 2026-09-25 补挂（主人令「把他们按比例最小化模块部署到云插件」）：
        #    「按比例最小化」（量化）是真技术，但**能小到多少有下界**：下界由参数量决定。
        #    这道闸把「真文件体积 × 真上限」算出来（上限取官方 limits 文档现读），
        #    并连**1 bit/参数的假想地板**一起算 —— 地板都装不下就不必再谈"再压一点"。
        ("量化体积 × 云上限 判定", PY + [str(S / "min-quant-fit.py"), "selftest"],
         "rc=0（上限取官方口径 · 装不下必须给倍数 · 未读到不许当 0 · imatrix 标定件不算权重）"),
 # 2026-09-25 补挂（主人令「所有的东西都要跑起来了才算合格」）：
        #    图像触手**在本机真跑**（ComfyUI + 真 SD1.5 权重 + LCM · CPU）⇒ 两条闸盯着它：
        #    一条盯"能真出一张图"（节点图/PNG 判定），一条盯"能包成网里认得的端点"（没就绪必须 503 未读到）。
        ("本机出图链路", PY + [str(S / "local-comfy-image.py"), "selftest"],
         "rc=0（节点图 8 节 · LCM 接在模型链上 · PNG 签名与尺寸解析 · 不许编宽高）"),
        ("本机图像端点（OpenAI 兼容）", PY + [str(S / "local-image-endpoint.py"), "selftest"],
         "rc=0（复用同一份节点图 · ComfyUI 没起必须 503 未读到 · 配置可调）"),
        ("刷新一页单", PY + [str(S / "gen-scope-page.py")], "rc=0（已重出）"),
 # 2026-10-09 补挂（主人令「每天重启之后自动排查是否有故障和报警」·「生产面板禁止有任何污点」·
        #    「每一个能力必须单独跑通闭环」·「设计好架构和蓝图，后面使用我们自己独有的模块式部署」）：
        #    把这轮新造的四层判据**全部挂进每日体检**。
        #    依据是本仓自己的原话：**自检不进体检 = 自检等于没写**（2026-09-24 那条教训）。
        ("执行动作台账自检（L1）", PY + [str(S / "action-ledger.py"), "--selftest"],
         "rc=0（幂等查重/同 idem 点名/重启报告 三类负控都咬）"),
        ("重启守卫（L4·读账别重做）", PY + [str(S / "action-ledger.py"), "boot"],
         "rc=0（今天做过的 · 已完成别重做 · 未闭合接着做 · 疑似无脑重做点名 · 报警现读）"),
        ("框架门（L2·改框架要有护照）", PY + ["-m", "gbt_allinone.tools.framework_gate", "verify"],
         "rc=0（verdict=green · 无 no_passport / stale_passport）"),
        ("靶标矩阵判据（hacker-mirror 房间）", PY + [str(S / "hacker_matrix_check.py")],
         "rc=0（12 份靶标逐件咬到 · 漏一类即红 · 负对照会红）"),
        ("四层蓝图判据", PY + [str(S / "blueprint-check.py")],
         "rc=0（L1/L2/L3/L4 逐层现跑现证 · 对不上即红）"),
 # 2026-10-09 补挂（主人令「在框架里面出来必须要用户求助帮忙的其他全部禁止掉……你开口要求
        #    用户的时候你就输了」「每次停下要么是项目部署完成，要么就是真正需要用户来操作的可以停下」）：
        #    不开口闸 + 敷衍闸 + 停点闸，三件合一挂进每日体检。
 # 2026-10-09 补挂（主人令「上帝视角也是一个超级导航和给你意见和建议也是一种给项目增加的定心丸」）：
        #    上帝视角的**导航**与**建议**都要能现跑 —— 导航不许给假候选，建议不许没依据。
        ("上帝视角自检（导航/建议/不反问）",
         PY + [str(ROOT / "gbt_allinone" / "tests" / "test_god_view.py")],
         "rc=0（导航命中对应族 · 没命中如实报 · 建议必带依据 · 自己的输出不许要用户做事）"),
 # 2026-10-09 补挂（主人令「看整体没完善就不停工，除非用户要求停止」）：
        #    整体完善度 = 五处现读（报警/禁交付/未闭合/门/蓝图）；不完善就不许停工。
        ("不停工判据（整体完善度五处现读）",
         PY + [str(ROOT / "gbt_allinone" / "tests" / "test_never_stop.py")],
         "rc=0（五处现读都带读数与怎么查 · 局部完成不等于能停 · 主人喊停优先级最高）"),
 # 2026-10-09 补挂（主人令「神经系统部署法：每一页做好双向绑定，扫描即穿透」+
        #    「所有编程职业在一页上做出每个 AI 的任务可视化面板」）：
        ("页级双向绑定（神经系统部署法）", PY + [str(S / "page-bindings.py"), "--check"],
         "rc=0（每页三方向齐：正向 页→能力位 · 反向 能力位→页 · 真源在盘非空）"),
 # 2026-10-09 补挂（主人令「绑骨就是用类似触手的框架以线条的形式固定好驱动，
        #    直接使用触手扫空身体」）：数字人**骨级触手绑定** —— 每根骨可寻址+有线+有驱动，零死角。
        #    负对照：拔掉全部动画 ⇒ 必须冒出 19 个死角。
 # 2026-10-09 补挂（主人令「视觉每次都要跟手分开去使用传统的瞎子操作……钉死在上面」+
        #    「她每次执行任务就是瞎还没脑」+「还有耳，嘴」）：四觉闭环 —— 眼耳嘴手缺一觉就拒动/拒说。
 # 2026-10-09 补挂（主人令「把这条『扫空身体』扩到整个框架 —— 每一页/每个能力位/
        #    每根触手都按同一套『寻址+线条+驱动+双向绑定』扫一遍」）：通法扫空，四平面一起判。
        ("通法扫空（四平面×四列）", PY + [str(S / "neural-scan.py"), "--check"],
         "rc=0（页/能力位/触手域/骨 四平面同一套四列模型；死角合计 0）"),
        ("原生四觉闭环（眼耳嘴手·缺一觉拒动）",
         PY + [str(ROOT / "gbt_allinone" / "tests" / "test_vision_loop.py")],
         "rc=0（四觉齐 · 看不到不动 · 没脑不动 · 没内容不说 · 门与内层同口径）"),
        ("视觉钉死闸（没有眼睛就没有手）", PY + [str(S / "vision-pinned-check.py")],
         "rc=0（凡 desktop_control 必须同时有 privacy_read；瞎子缝 0）"),
        ("骨级触手绑定（扫空身体·无死角）",
         PY + [str(ROOT / "tools" / "digihuman" / "bone-tentacle-bind.py"), "--check"],
         "rc=0（19 骨逐根：寻址/线条/驱动三件齐；有死角即红）"),
 # 2026-10-10 补挂（主人截图暴露：跑的是旧打包件 ⇒ 新页一样没进包）：
        #    electron-builder 的 build.files 是**手工白名单**，新建一页就要人肉补一行 ⇒ 迟早漏。
 # 2026-10-10 补挂（主人令「你都不审查，不登记的吗？不调用跑一遍全部能力那里有问题就一目了然了」）：
        #    框架总账 = 六本子账汇总成一页（真坏/缺依赖/未配置，每条带根因与该谁给）。
        ("框架总账（六本子账汇总·一目了然）", PY + [str(S / "health-ledger.py"), "--check"],
         "rc=0（每条都有状态与归属；真坏 = 我的活没干完，其余 = 等票但已逐条登记）"),
 # 2026-10-10 补挂（主人令「下一轮」：把这套判据挂进每日体检，让哑片和响度不达标**开机就报警**）：
        #    这两件是抓样本定合格线时追出来的 —— 现有片场 7 支哑片、我那条片响度比样本低 12dB，
        #    都是**我抓样本时才撞见**的。挂进体检 ⇒ 以后开机就报，不用等撞。
 # 2026-10-10 补挂（主人给的 3D 权威口径：Khronos glTF 2.0 / Tripo 检查单 / Game-Ready 2026）：
        #    十道工序落成机检 —— 能机检的一律机检，机检不了的如实标「未检」（明写不装会）。
        ("3D 资产机检（十道工序）", PY + [str(S / "verify-3d-asset.py")],
         "rc=0（在役件都检到；面数/包围盒/关节/NORMAL/UV/蒙皮权重归一/动画逐条真读）"),
        ("影片音轨（哑片不许出厂）", PY + [str(S / "film-audio-guard.py")],
         "rc=0（出厂面凡有视频却 0 音轨即红；中间件允许无音轨但要标明；彩排/演示件不判但必须标出来）"),
        ("样本合格线（时长/响度对样本区间）", PY + [str(S / "sample-baseline.py")],
         "rc=0（合格线=真样本读数区间；越界即红；**音轨不在这里判**——那是上一道的活）"),
        ("打包白名单（新增页不许漏出包）", PY + [str(S / "pack-files-check.py")],
         "rc=0（面板 PAGES 里落在 holo_pet_w3/ 下的页，其目录必须被 build.files 覆盖）"),
        ("AI 工作面板现读", PY + [str(S / "ai-board.py")],
         "rc=0（30 职位逐位带状态与最近动作；报警如实显示）"),
        ("不开口闸（严禁要用户做事）", PY + [str(S / "no-ask-check.py")],
         "rc=0（违规 0；5 句要用户做事必须全拦 + 身份登录/商量架构放行 + 停点闸只许两种理由）"),
        ("交付闸（每能力单独闭环才准交付）", PY + ["-m", "gbt_allinone.delivery_gate", "audit"],
         "rc=0（禁交付 0；要参数/缺依赖/真坏/未扫 ⇒ 禁交付）"),
    ]


def _self_check(steps: list | None = None) -> dict:
    """**只自证架子在**（列出全部步骤 + 不执行它们）。

    🔴 为什么必须有这个模式（**递归陷阱**）：把 checkup 挂成神经末梢时，
    `nerve selftest` 会探它；若探针跑**完整** checkup，而 checkup 第②步正是 `nerve selftest`
    ⇒ **探针 → checkup → nerve selftest → 探针 …** 无限递归。
    ⇒ 探针只验"步骤还在、脚本还能起"，**不重跑体检**。

    🔴 **这里写死过 `len(steps) == 5`** —— 体检从 5 步长到 22 步之后它就成了**恒假**，
    `--self` 恒 `rc=4`，神经末梢 P25 **长期 ⛔ 痛**，而 `nerve selftest` 用的是
    合成探针（`__selftest_ok__` 那几条）**从不真跑 P25** ⇒ **没人看得见**。
    2026-09-24 现跑坐实（`nerve.py probe P25` ⇒ 痛 rc=4）。
    **判据不许写死条数**：要写"条数是正的、每条都成形、引用的脚本都在"。

    `steps` 可传入（**只给自检的负控用**），默认取真表。
    """
    steps = _steps() if steps is None else steps
    if not steps:
        return {"ok": False, "步数": 0, "步骤": [], "缺脚本": [],
                "口径": "**没有任何步骤 = 不合格**（空体检不许念成合格）"}
    ok = all(isinstance(c, list) and c and isinstance(n, str) and n
             and isinstance(cr, str) and cr for n, c, cr in steps)
 # 2026-09-25：这里原来先看 `c[-1].endswith(".py")`（**末位**是不是脚本），
    #    不是才退回扫全命令 —— 台架 D7（位置型判据）点了它，**点得对**：
    #    命令表长这样 `[python, 脚本.py, "--selftest"]`，**末位常常是参数不是脚本**。
    #    那个特例只在"无参命令"上起作用，等于**用位置猜**。改成一律 `any` 扫全命令：
    #    **行为等价**（无参时 any 一样找到脚本；找不到的照样点名），但不再依赖位置。
 # 2026-09-25 二修：这条判据**只认 `.py`** ⇒ 2026-09-25 挂上第一道 node 闸
    #    （`10 云插件拼接网形状验收`）时，它把**存在的** `.mjs` 报成「缺脚本」。
    #    **判据比对象窄 = 假红**（与"判据比对象宽 = 假绿"同族）：脚本后缀要按**现读**认，
    #    不能按"我这仓里全是 python"认。认的后缀写在一处，加新后缀只改这一行。
    SCRIPT_SUFFIXES = (".py", ".mjs", ".cjs", ".js")

    def _has_target(c) -> bool:
        """这条命令有没有**可验的真实靶**（文件脚本 **或** 「-m 模块」形式）。

        🔴 2026-10-10 第三修（体检 rc=1：体检器自检 自己红）：原来**只认文件后缀** ⇒
            本仓有多步是 **py -m 模块** 形式（框架门 / 交付闸 都是我挂的），
            它们**没有文件参数** ⇒ 被判「缺脚本」 ⇒ **假红**。
            这与上面 2026-09-25 那次「只认 .py ⇒ 把存在的 .mjs 报缺」**同族**：
            **判据比对象窄 = 假红**。⇒ 按 **importlib 现读解析模块**，不按后缀/位置猜。
        """
        xs = [str(x) for x in c]
        if any(x.endswith(SCRIPT_SUFFIXES) and pathlib.Path(x).is_file() for x in xs):
            return True
        if "-m" in xs:
            i = xs.index("-m")
            if i + 1 < len(xs):
                mod = xs[i + 1]
                # ① 路径回退（**最稳**：不依赖 sys.path 与导入副作用）
                rel = mod.replace(".", "/")
                if ((ROOT / (rel + ".py")).is_file()
                        or (ROOT / rel / "__init__.py").is_file()):
                    return True
                # ② 再试 importlib（仓根不在 sys.path 时 find_spec 会解析不到 —— 实测撞过）
                try:
                    import importlib.util as _iu
                    return _iu.find_spec(mod) is not None
                except Exception:                            # noqa: BLE001
                    return False
        return False

    missing = [n for n, c, _ in steps if not _has_target(c)]
    return {"ok": bool(ok and not missing), "步数": len(steps),
            "步骤": [n for n, _, _ in steps], "缺脚本": missing,
            "口径": "**只验架子，不重跑体检** —— 否则 nerve selftest → checkup → nerve selftest 无限递归；"
            "**步数不写死**（写死过一次 ⇒ 末梢长期假痛）"}


def _selftest() -> int:
    """体检器**自己**的自检：判据要真会咬，且**不许写死条数**。

    🔴 为什么要它：`--self` 那条判据曾经**长成恒假**（写死 `== 5`），
    而它挂在神经末梢 P25 上 —— **红的，没人看**。一个"红到没人看"的探针
    等于没有探针。这里把"它会咬"变成可复核的负控。
    """
    lines, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    real = _self_check()
    ck("真数据：架子自证通过", real["ok"] is True,
       "步数=%s ｜ 缺脚本=%s" % (real["步数"], real["缺脚本"] or "无"))
 # ③ **回归负控**：只有 1 步也**必须**合格。
    #    写死 `== 5` 的那一版在这里会判不合格 —— 这正是当年那个 bug 的形状。
    one = [("假步骤", [sys.executable, str(S / "checkup.py"), "--self"], "rc=0")]
    r1 = _self_check(one)
    ck("**回归负控：只有 1 步也合格（条数没被写死）**", r1["ok"] is True,
       "步数=%s ok=%s" % (r1["步数"], r1["ok"]))
    # ② 负控：引用的脚本不在 ⇒ 必须判不合格，且**点名缺哪个**
    miss = [("假步骤", [sys.executable, str(S / "__没有这个脚本__.py")], "rc=0")]
    r2 = _self_check(miss)
    ck("**负控：引用的脚本不在 ⇒ 不合格并点名**",
       r2["ok"] is False and r2["缺脚本"] == ["假步骤"], str(r2)[:90])
    # ④ 负控：空表 ⇒ **不许念成合格**
    r3 = _self_check([])
    ck("**负控：空表 ⇒ 不合格（空体检不是合格）**", r3["ok"] is False, str(r3)[:70])
    # ⑤ 负控：三件不成形（缺判据说明）⇒ 不合格
    r4 = _self_check([("假步骤", [sys.executable, str(S / "checkup.py")], "")])
    ck("**负控：步骤不成形（缺判据说明）⇒ 不合格**", r4["ok"] is False, str(r4)[:70])
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def _streak() -> dict:
    """**连续全过**趋势：读体检历史（次数与**覆盖天数**分开报，不混念）。

    诚实口径：单次全过 ≠ 稳定 ⇒ 要看**连续性**；但"连续 N 天"**不能靠一分钟内连跑 N 次冒充**
    ⇒ 这里同时报「连续全过**次数**」与「覆盖**不同日期数**」，谁都不能顶替谁。
    """
    p = ROOT / "state" / "checkup-history.jsonl"
    if not p.is_file():
        return {"历史": "还没有（本次是第一次）"}
    rows = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln:
            try:
                rows.append(json.loads(ln))
            except Exception:  # noqa: BLE001
                pass
    streak = 0
    for r in reversed(rows):
        if r.get("rc") == 0:
            streak += 1
        else:
            break
    last_fail = next((r.get("at") for r in reversed(rows) if r.get("rc") != 0), None)
    return {"总次数": len(rows), "连续全过次数": streak,
            "覆盖不同日期数": len({str(r.get("at") or "")[:10] for r in rows}),
            "最近一次失败": last_fail or "（无）",
            "口径": "**连续全过次数 ≠ 连续天数** —— 两个数分开报，谁也顶替不了谁"}


def main() -> int:
    ap = argparse.ArgumentParser(description="一条命令出体检报告（%d 道闸串联，fail-closed）"
                                             % len(_steps()))
    ap.add_argument("--quiet", action="store_true", help="不打印每一步的输出尾")
    ap.add_argument("--self", action="store_true",
                    help="只自证架子在（供神经末梢探测，**不重跑体检**，避免递归）")
    ap.add_argument("--selftest", action="store_true",
                    help="**体检器自己的自检**（判据真会咬 · 条数没写死 · 空表不合格）")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    if a.self:
        r = _self_check()
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["ok"] else 4

    t0 = time.time()
    rows, worst = [], 0
    for name, cmd, criterion in _steps():
        s0 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=str(ROOT))
        tail = ((r.stdout or "") + (r.stderr or "")).strip().replace("\n", " ")[-160:]
        rows.append({"步骤": name, "rc": r.returncode, "判据": criterion,
                     "秒": round(time.time() - s0, 1), "输出尾": tail})
        worst = max(worst, r.returncode)
        if not a.quiet:
            print("%s %-16s rc=%d  %.1fs  %s" % ("✓" if r.returncode == 0 else "✗",
                                                 name, r.returncode, time.time() - s0, tail[:100]))

    at = time.strftime("%Y-%m-%dT%H:%M:%S")
    # 体检历史（趋势要它）：**追加**一条，再算连续全过
    hist = ROOT / "state" / "checkup-history.jsonl"
    hist.parent.mkdir(parents=True, exist_ok=True)
    with open(hist, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": at, "rc": worst, "耗时秒": round(time.time() - t0, 1),
                            "逐条rc": {x["步骤"]: x["rc"] for x in rows}}, ensure_ascii=False) + "\n")
    streak = _streak()
    report = {
        "at": at, "总耗时秒": round(time.time() - t0, 1),
        "判决": ("✅ %d 道闸全过" % len(rows)) if worst == 0
        else "🔴 **有闸没过**（看逐条 rc；共 %d 道）" % len(rows),
        "逐条": rows,
        "连续全过（趋势）": streak,
        "口径": "**任一步 rc≠0 ⇒ 整体 rc≠0（fail-closed）**；逐条列 rc，不合并成一句『体检失败』",
        "调度命令（**装不装要主人点头**：计划任务是机器级配置）":
            'schtasks /Create /TN "GBT-health-checkup" /SC DAILY /ST 09:00 '
            '/TR "py -3.14 %s"' % (S / "checkup.py"),
        "它不做什么": "不装计划任务 · 不自动修东西 · 只读 + 只写报告",
    }
    out_p = ROOT / "state" / "checkup-last.json"
    out_p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    md = ROOT / "docs" / "体检报告.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("\n".join(
        ["# 体检报告（一条命令出）", "",
         "> 开发者：自由的风 · 守护者：公主土豆 · 本署名不可删除、不可篡改归属", ">",
         "> 读数 %s ｜ 总耗时 %.1fs ｜ **%s**" % (at, time.time() - t0, report["判决"]), "",
         "**连续全过（趋势）**：%s" % json.dumps(streak, ensure_ascii=False), "",
         "| 步骤 | rc | 判据 | 秒 |", "|---|---|---|---|"]
        + ["| %s | %s | %s | %s |" % (x["步骤"], x["rc"], x["判据"], x["秒"]) for x in rows]
        + ["", "**口径**：任一步 `rc≠0` ⇒ 整体 `rc≠0`（fail-closed）；逐条列 rc，不合并成一句「体检失败」。", "",
           "**调度**（装不装要主人点头）：", "", "```",
           report["调度命令（**装不装要主人点头**：计划任务是机器级配置）"], "```", "",
           "> 生成器：`tools/codex-scripts/checkup.py`（它不装计划任务、不自动修东西）", ""]),
        encoding="utf-8")
    print(json.dumps({"判决": report["判决"], "落盘": [str(out_p.relative_to(ROOT)),
                                                 str(md.relative_to(ROOT))],
                      "逐条 rc": {x["步骤"]: x["rc"] for x in rows},
                      "总耗时秒": report["总耗时秒"]}, ensure_ascii=False, indent=1))
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
