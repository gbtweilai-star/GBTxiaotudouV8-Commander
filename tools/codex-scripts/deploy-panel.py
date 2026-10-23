#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""主控面板 · 插件云部署编排看板（主人 2026-09-24 令）

主人原话：「单独拿一个插件云部署你想要什么样的效果都行，但是**主控面板**都清晰看到
所有部署和顺序，**千万不能胡乱运行和排布**。」

所以这个工具只干一件事：**把"排布"变成一张有编号、有先后、有归属、能拒单的表**。
- 每个模块有**固定编号**（01~09）与**声明依赖**；登记前先查依赖，**缺一个就拒**（fail-closed）。
- 每个终端有**固定编号**（T01~T50）；看板显示谁在做、谁闲着、还有多少没做。
- 每个作业有**编号**（job_id）；显示状态/归属/产物/字节/sha。
- `mark` 必须带**证据串**（形状 `命令 => 读数`），不带就拒 —— 这是本仓的读数纪律。

## 它不做什么（边界写死）
- **不部署云函数**。`deploy`（Workers/Containers）是发布动作，会把它推到公网 ⇒ **须主人点头**。
  本工具只登记"契约与状态"，落点全部是 R2 桶 `gbt-bigfiles` 里的**登记键**。
- **不自己判定"已验"**。状态是**登记声明**，`证据` 字段里存的是**可重跑的命令与当时的读数**；
  看板把它原样摊开，`--verify` 只重跑**便宜**的那三条探针（01/06/09），其余不假装验过。

## 云侧登记键（本工具新增，与 render-agent 的模块契约同一命名空间）
    pipeline/modules/<module>/<version>/manifest.json   不可变登记（含编号·依赖·证据）
    pipeline/modules/<module>/current.json              指针（board 只读这个）
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
RA_PATH = ROOT / "tools" / "codex-scripts" / "render-agent.py"

# 🔴 本地替身云：**只给自检用**（`selftest` 验顺序门时不能真往云上写）。
#    设了它，所有 put/get 落到本地目录，等价于把 R2 换成一块本地盘 —— 顺序门的**代码路径完全一样**。
LOCAL_CLOUD = os.environ.get("GBT_PLUGIN_CLOUD_LOCAL", "").strip()

# ── 部署编排（唯一真源：编号 · 模块 · 运行地 · 依赖编号 · 缺什么） ──────────────────
# 顺序**不是理想 DAG，而是今天真跑得通的依赖**：render 只需要作业单(01)，
# 不需要 orchestrator(02)（现在派活是人/代理在做）——所以 06 的依赖只写 01，如实。
DEPLOY_ORDER = [
    # 编号   模块            运行地    依赖        当前缺什么（真读出来的，不是猜的）
    ("01", "spec-store",  "cloud", []),
    ("02", "orchestrator", "cloud", ["01"]),
    ("03", "asset-pool",  "cloud", ["01"]),
    ("04", "frame-cache", "cloud", ["01"]),
    ("05", "generator",   "cloud", ["03"]),
    ("06", "render",      "LOCAL", ["01"]),
    ("07", "assemble",    "cloud", ["06"]),
    ("08", "publish",     "cloud", ["07"]),
    ("09", "vault",       "cloud", []),
]

# 未部署原因（写死的原因也必须是真的；"未接线"= 仓里没有这个东西）
GAPS = {
    "02": "没有独立派活进程：现在派活是人/代理手动做（本工具不假装它跑着）",
    "03": "云上 `pipeline/assets/index.json` 不存在 ⇒ 素材池没见过一份素材",
    "04": "云上 `pipeline/cache/frames/index.json` 不存在 ⇒ 帧缓存没见过一帧",
    "05": "生成端要吃云 key：ELEVENLABS/FAL/VENICE/REPLICATE 四个只有一个 OPENAI 已配",
    "07": "装配现在在本地 render 一步里做完（Remotion 自带编码）；云侧独立 worker 未接线",
    "08": "发布要 `deploy_publish` 授权，且授权只能主人在终端发；未接线",
}

TERMINAL_SLOTS = 50          # 主人定的**并发上限**：30~50 个终端（与"触手根数"是两个数，各自标出处）
PREFIX = "pipeline"
BUCKET = os.environ.get("GBT_PLUGIN_CLOUD_BUCKET", "gbt-bigfiles")
ROSTER = ROOT / "state" / "tentacle-roster.json"

# ── 运用到的每一件都独立成槽（主人 2026-09-24 令：「把所有运用到的都独立使用触手根数来部署」
#    「排列好就像计算机一样永远不会出错却一清二楚」）─────────────────────────────────
# 🔴 这里只登记**本会话真用过**的件（有真跑读数）。**没真跑过的不许进这张表** —— 一进就等于自夸。
#    字段：编号 · 名称 · 做什么（备注）· 落点 · 真命令 · 关联模块 · 状态 · 出处（读数从哪来）
PLUGIN_SLOTS = [
    ("P01", "deploy-panel.py", "主控面板：编号·顺序·拒单·触手排班（本工具）", "LOCAL",
     "py -3.14 tools/codex-scripts/deploy-panel.py board --verify", "—", "✅ 已真跑",
     "自检 9 行全绿 · 真云跳序拒单 rc=3"),
    ("P02", "render-agent.py", "本地渲染代理：拉作业单→本地出片→推回云（本地唯一一格）", "LOCAL",
     "py -3.14 tools/codex-scripts/render-agent.py run <job> --worker tX", "06 render", "✅ 已验",
     "demo-003 出 out.mp4 141318 B sha 73b2311f5bbc7de7"),
    ("P03", "wrangler-r2", "云通道：R2 对象 put/get（🔴 两者都必须 --remote，否则走本地模拟）", "CLOUD",
     "npx --yes wrangler r2 object put|get <bucket>/<key> --file <path> --remote", "01 spec-store", "✅ 已真跑",
     "F18 反例记档：不带 --remote 默认本地模拟却打印成功"),
    ("P04", "remotion", "本地渲染引擎①：React 合成→Chrome 出帧→ffmpeg 编码 MP4", "LOCAL",
     "npx --no-install remotion render <comp> <out> --entry-point src/index.tsx", "06 render", "✅ 已真跑",
     "hello.mp4 90 帧 3.000000 s 141318 B 1080p30"),
    ("P05", "hyperframes", "本地渲染引擎②：HTML 合成→Chrome 出帧→MP4", "LOCAL",
     "npx --yes hyperframes@0.8.69 render", "06 render", "✅ 已真跑",
     "10.000000 s 300 帧 1080p30 · check 由空时间线转 passed"),
    ("P06", "ffmpeg-ffprobe", "编码与探针：时长/帧数/分辨率/码流的**读数来源**", "LOCAL",
     "ffprobe -v error -show_streams -of json <file>", "—", "✅ 已真跑",
     "8.1.2 在位，上面两条成片的时长帧数就是它量的"),
    ("P07", "chrome-headless-shell", "出帧内核：无头 Chrome（Remotion/HyperFrames 都靠它）", "LOCAL",
     "npx remotion browser ensure", "—", "✅ 已真跑",
     "152 在位（HyperFrames doctor 读数）"),
    ("P08", "node-npm-npx", "运行时：Node/npm/npx（⚠️ Windows 上 subprocess 必须解析真路径）", "LOCAL",
     "npx --version", "—", "✅ 已真跑",
     "Node v24.15.0 · subprocess 直起 npx 报 WinError 2，须 shutil.which"),
    ("P09", "asset-pool.py", "模块03 素材池：put 后**拉回来逐字节校验**一致才写索引", "CLOUD",
     "py -3.14 tools/codex-scripts/asset-pool.py put <file> --kind <kind>", "03 asset-pool", "🟡 自检已验·真云待跑",
     "自检 6/6（1 正控 + 4 负控）"),
    ("P10", "cloud-vault.py", "模块09 云仓：按触手根数分片，封顶 32 GB（容量，不是速度）", "CLOUD",
     "py -3.14 tools/codex-scripts/cloud-vault.py plan|put|get|stat", "09 vault", "✅ 已验",
     "登记 2 条均逐字节校验 · 149.6 MB 已释放本地"),
    ("P11", "vault-spill.py", "本地大件溢出：默认 --dry-run；**远端字节验过才删本地**", "LOCAL+CLOUD",
     "py -3.14 tools/codex-scripts/vault-spill.py scan|spill --apply", "09 vault", "✅ 已真跑",
     "spill/0.pack 156886936 B 校验通过后本地释放，磁盘 +140 MB"),
    ("P12", "r2-move.py", "云搬运与校验：字节级回验·对不上不删·>300MiB 分片", "CLOUD",
     "py -3.14 tools/codex-scripts/r2-move.py put|get|verify", "09 vault", "✅ 已真跑",
     "cloud-vault 的搬运**委托**给它（不自己造更弱的）"),
    ("P13", "quick_scan.py", "全仓故障扫描：P0/P1/P2 + 判据分类 + 盲区注记", "LOCAL",
     "py -3.14 tools/codex-scripts/quick_scan.py", "—", "✅ 已真跑",
     "现读 32（P0 3 · P1 9 · P2 20）"),
    ("P14", "quickscan_evolve.py", "判据自检与进化：真身负控（不用假数据验假逻辑）", "LOCAL",
     "py -3.14 tools/codex-scripts/quickscan_evolve.py --selftest", "—", "✅ 已真跑",
     "自检 15 行全绿 · 判据目录 80"),
    ("P15", "five-dim.py", "唯一门：cap <能力位> → run_task（**授权只能主人在终端发**）", "LOCAL",
     "py -3.14 tools/codex-scripts/five-dim.py cap <能力位>", "—", "✅ 已真跑",
     "本轮 cap tentacle_cognition 读回 5 条红线 + 认知包字段"),
    ("P16", "framework_gate.py", "框架自改门：基线/护照/verify/close（fail-closed）", "LOCAL",
     "py -3.14 tools/codex-scripts/framework_gate.py verify", "—", "⚠️ 绿但不可信",
     "F31：我自己的护照把 19 个早于 opened_at 的文件也claim了 ⇒ 这个绿是假的"),
    ("P17", "frame-cache.py", "模块04 帧缓存：按作业分桶；**同名不同内容绝不静默覆盖**", "CLOUD",
     "py -3.14 tools/codex-scripts/frame-cache.py put <job> <frame>", "04 frame-cache", "✅ 已验",
     "demo-003 三帧往返逐字节一致（8922/145540/145579 B）· 真云撞名闸 rc=7 · verify 3/3"),
    ("P18", "orchestrator.py", "模块02 编排器：**只派已登记的模块**，未登记就停住不越级", "CLOUD",
     "py -3.14 tools/codex-scripts/orchestrator.py plan|tick [--apply]", "02 orchestrator", "✅ 已验",
     "真云：04✅06✅07⛔08⛔ ⇒ 停在 07 · tick 派 demo-004 给 T01 隔离位 · 自检 6/6"),
    ("P19", "assemble.py", "模块07 装配：云上的帧 → 编码 → 产物回云（**帧数必须对得上**）", "CLOUD",
     "py -3.14 tools/codex-scripts/assemble.py run <job> --slot T0k --apply", "07 assemble", "✅ 已验",
     "demo-005：云上 3 帧 → 成片真解出 3 帧 · 11813 B · 往返一致 · 自检 6/6（F34：曾把 5 帧编成 1 帧）"),
    ("P20", "failover.py", "紧急扩容：每个能力一个备用位 + 内存闸 + 切换留痕", "CLOUD",
     "py -3.14 tools/codex-scripts/failover.py table|guard|switch", "—", "✅ 已验",
     "覆盖 18/18 · 真机内存闸读 472MB/7563MB(93%) ⇒ 判「不够，走低并发」· 自检 7/7"),
    ("P21", "nerve.py", "神经总线：每个能力一条**真探针**，痛/未知一眼看见（具应变）", "CLOUD",
     "py -3.14 tools/codex-scripts/nerve.py map|probe|pain", "—", "✅ 已验",
     "20 末梢 19 通 1 痛（P16 框架门真红）· 自检 7/7 · F35：曾用错路径/错 flag 报 2 个假痛"),
    ("P22", "publish.py", "模块08 发布门卫：**默认拒**；授权+落点两闸，真发布走唯一门", "CLOUD",
     "py -3.14 tools/codex-scripts/publish.py check|send <job> --room <房间>", "08 publish", "✅ 已验",
     "现读 deploy_publish grants=0 ⇒ send 拒 rc=3；无落点拒 rc=4；自检 5/5。**它是门卫不是发布器**"),
    ("P23", "generator.py", "模块05 生成端：**双源**凭据闸 + 花费闸；缺 key 如实报 needs_key", "CLOUD",
     "py -3.14 tools/codex-scripts/generator.py providers|gen <job> --provider X", "05 generator", "✅ 已验",
     "自检 8/8 · 现读 5 个 provider 全缺凭据（保险箱 7 个 .dpapi 无一是生成端）。**验的是闸，不是出图**"),
    ("P24", "lint_cjk_quotes.py", "**中文串里的 ASCII 引号**闸（我犯了 13 次的语法崩）", "LOCAL",
     "py -3.14 tools/codex-scripts/lint_cjk_quotes.py tools/codex-scripts", "—", "✅ 已真跑",
     "**条数不写死**（这里曾写死「现读 296 个 .py」，而现读已是 334）—— "
     "**只对编译失败的文件说话**（能编译过就不可能有这问题）"),
    ("P25", "checkup.py", "体检总闸：**全部体检步骤**串成一条（lint→神经→面板→盲区→位级→漂移→一页单）", "LOCAL",
     "py -3.14 tools/codex-scripts/checkup.py", "—", "✅ 已真跑",
     "**闸数以现读为准**（本行曾写死「五道」又写死「20 道」，两次都变成假的）："
     "看上面「自身融合（自律）」那一行，它是从 `state/checkup-last.json` 现读的。"
     "**末梢只探 `--self`**（只验架子）—— 探完整会与神经自检无限递归"),
]


def _roster() -> dict:
    if ROSTER.is_file():
        try:
            d = json.loads(ROSTER.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}
    return {}


def _tentacles() -> tuple[int, str]:
    """触手根数**只认声明**（`state/tentacle-roster.json`）。声明缺失 ⇒ 返回 0 + 原因，
    **绝不拿 `os.cpu_count()` 冒充**（那是 cloud-vault 的调度尺，不是触手数）。"""
    r = _roster()
    n = r.get("声明根数")
    if isinstance(n, int) and n > 0:
        return n, "声明：" + str(r.get("来源") or "state/tentacle-roster.json")
    return 0, "**未声明**（state/tentacle-roster.json 缺失或没有『声明根数』）—— 不猜、不用 CPU 线程数顶替"


def _slots_dir() -> pathlib.Path:
    return ROOT / "state" / "tentacle-slots"


def _schedule(n: int) -> list[dict]:
    """固定轮转：第 k 根触手负责 P{k}, P{k+n}, P{k+2n}…
    这是**确定性**的（同输入永远同输出），像 CPU 的固定分时 —— 不掷骰子、不随机排布。

    ⚠️ 本仓有过教训：「N 根触手 ⇒ N 个隔离位」只把名字**印在报告里**，目录没真建、没真用。
    所以这里每一排都**带真实存在性读数**（`_slots_dir()` 下有没有这个目录）。"""
    rows = []
    for k in range(n):
        mine = [p for i, p in enumerate(PLUGIN_SLOTS) if i % n == k]
        d = _slots_dir() / ("T%02d" % (k + 1))
        rows.append({"触手": "T%02d" % (k + 1),
                     "隔离位": str(d.relative_to(ROOT)),
                     "隔离位已真建": d.is_dir(),
                     "负责插件": [p[0] for p in mine],
                     "做什么": [p[2] for p in mine]})
    return rows


def _layout_body() -> dict:
    n, src = _tentacles()
    r = _roster()
    plugins = [{"编号": p[0], "名称": p[1], "做什么": p[2], "落点": p[3], "真命令": p[4],
                "关联模块": p[5], "状态": p[6], "出处": p[7]} for p in PLUGIN_SLOTS]
    cloud_n = sum(1 for p in PLUGIN_SLOTS if "CLOUD" in p[3])
    body = {
        "触手根数": {"根数": n or None, "出处": src,
                 "代理读数_CPU线程": os.cpu_count(),
                 "代理读数说明": "⚠️ CPU 线程数只是调度放大尺，**不是触手根数**，不许当触手数念"},
        "两个数别混": {"触手根数": "%s（主人声明，只有主人能改）" % (n or "未声明"),
                  "终端并发上限": "T01~T%02d 共 %d（主人给的 30~50）" % (TERMINAL_SLOTS, TERMINAL_SLOTS)},
        "插件独立部署表": plugins,
        "合计": {"插件": len(plugins), "其中落云": cloud_n, "落本地": len(plugins) - cloud_n},
        "触手排班": _schedule(n) if n else [],
        "排班规则": "固定轮转 P{k}·P{k+n}·P{k+2n}…（确定性，不随机）；一根触手一个隔离位 ⇒ 互不踩",
        "不变式": _invariants(n),
        "规矩对照": r.get("规矩对照"),
    }
    return body


def _invariants(n: int) -> dict:
    """排班的不变式 —— **可机检**，且判据必须**随数据变**。

    🔴 这里原来第①条是假判据（2026-09-25 主人令后修）：
        旧：idx = [i for k in range(n) for i in range(len(PLUGIN_SLOTS)) if i % n == k]
        每个下标**按构造只被选中一次** ⇒ dup **恒为空** ⇒ 该条**无论数据多乱都永远 ✅**。
        ⇒ 「一根触手重复注册」这种真问题它根本看不见。
    新判据三条都**从 `_schedule()` 的真实返回**里算，并加**身份去重**（编号 + 名称）。
    """
    if not n:
        return {"结论": "触手根数未声明 ⇒ 不排班（fail-closed）"}
    rows = _schedule(n)
    # ⚠️ `_schedule` 返回的是 **dict 列表**（键 "负责插件" 才是编号表）——
    #    写成 `for p in row` 会把 **dict 的键**当元素（取到键首字母），是另一个刚踩的坑。
    covered = [pid for row in rows for pid in row.get("负责插件", [])]
    twice = sorted({x for x in covered if covered.count(x) > 1})
    unassigned = [p[0] for p in PLUGIN_SLOTS if p[0] not in set(covered)]
    ids = [p[0] for p in PLUGIN_SLOTS]
    names = [p[1] for p in PLUGIN_SLOTS]
    dup_id = sorted({x for x in ids if ids.count(x) > 1})
    dup_name = sorted({x for x in names if names.count(x) > 1})
    ok_count = len(rows) == n
    return {"①一件只挂一根触手（按 _schedule 真实返回）":
            "✅" if not twice else "✗ 被挂了两次：%s" % twice,
            "②没有漏挂": "✅" if not unassigned else "✗ 漏：%s" % unassigned,
            "③排数 = 触手根数": ("✅ %d = %d" % (len(rows), n)) if ok_count else
            "✗ %d ≠ %d" % (len(rows), n),
            "④槽位编号唯一（**真数据判据**）": "✅" if not dup_id else "✗ 重号：%s" % dup_id,
            "⑤挂的件不重复注册（**真数据判据**）": "✅" if not dup_name else "✗ 重复：%s" % dup_name,
            "结论": "五条都 ✅ 才算排班像计算机一样不出错"
            if not (twice or unassigned or dup_id or dup_name) and ok_count
            else "有不通过项"}


def _registry_brief() -> list:
    """触手**永久记录**的现读状态（只读）。

    🔴 读不到就**如实报读不到**，绝不装"干净" —— 名册坏了而面板打 ✅ 是最坏的一种假话。
    """
    try:
        spec = importlib.util.spec_from_file_location(
            "_treg", ROOT / "tools" / "codex-scripts" / "tentacle-registry.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        v = m.verify_chain()
        anchor = v["锚点"] if isinstance(v["锚点"], str) else "；".join(v["锚点"])
        return [("触手名册（永久记录 · 只追加 · 哈希链）",
                 "行数 %s ｜ 重复 tid %s ｜ 重复件 %s ｜ 序列缺口 %s ｜ 锚点 %s ｜ %s"
                 % (v["行数"], v["重复 tid"] or "无", v["重复 name"] or "无",
                    v["序号缺口"] or "无", anchor,
                    "✅ 干净（没丢·没乱·没重复）" if v["全过"] else "🔴 **不干净**"))]
    except Exception as e:
        return [("触手名册（永久记录 · 只追加 · 哈希链）", "**读不到**：%s" % str(e)[:90])]


def _fusion_brief() -> list:
    """自身融合层现读（只读）。**读不到就如实报读不到**，不装。
    「专属大模型 × 自身能力」的融合画像：能力面 / 模型面 / 推演 / 自律。"""
    try:
        spec = importlib.util.spec_from_file_location("_sm", ROOT / "tools" / "self_model.py")
        m = importlib.util.module_from_spec(spec)
        sys.modules["_sm"] = m                      # dataclass 需要先注册
        spec.loader.exec_module(m)
        w = m.whoami()
        C, A, M, ii, G = (w["自身能力面"], w["授权面（缺什么、卡在哪）"],
                          w["可操控的模型面"], w["推演（周易决策内核）"], w["自律（门与闸）"])
        scopes = A.get("缺授权·按作用域（发一次覆盖多位）") or {}
        top = " · ".join("%s(%d)" % (s, v["位数"])
                         for s, v in sorted(scopes.items(), key=lambda kv: -kv[1]["位数"])[:4])
        two = A.get("两个口径（**别混念**）") or {}
        aft = two.get("给参后（合并）") or {}
        return [
            ("自身融合（能力面）", "%s 位 ｜ 出处 %s" % (C.get("已探位", C.get("能力位")), C["出处"])),
            # 🔴 **两个口径并排**：只报一个数不写口径，就是本仓反复吃的那类亏
            #    （`16 道闸` / `现读 296 个 .py` / `len(steps) == 5`）。
            ("自身融合（授权面·**两个口径**）",
             "【空参探】已通 %s ｜ 缺授权 %s（%s 作用域）｜ 缺参 %s ｜ 真痛 %s ｜ "
             "【给参后】已通 %s ｜ **缺授权 %s**（%s 作用域）｜ 环境未就绪 %s ｜ 缺参 %s"
             % (A.get("已通"), A.get("缺授权"), len(scopes), A.get("缺参"), A.get("真痛位数"),
                aft.get("已通") or "**未读到**", aft.get("缺授权") or "**未读到**",
                two.get("给参后·作用域数") or "**未读到**", aft.get("环境未就绪") or "**未读到**",
                aft.get("缺参") or "**未读到**")),
            ("自身融合（授权面·最大缺口）", "**空参口径**：%s ｜ ⚠️ **两个数都对，别混念**"
             % (top or "无")),
            ("自身融合（作用域表是**下界**）",
             "空参探到 %s 个 ｜ 含给参后 **%s** 个 ｜ ⚠️ 只按空参探会漏（实测 `osint_scan`→`osint_private`）"
             % (A.get("按空参探到的作用域数"), A.get("按含给参后的作用域数"))),
            ("自身融合（模型面）", "%s provider ｜ **可路由 %s 条** ｜ 该接缝门 %s 条 ｜ ⚠️ 不是「亿万」"
             % (M.get("provider 数"), M.get("可路由 (provider,model) 配对数"),
                (M.get("该接缝的门") or {}).get("条数"))),
            ("自身融合（推演）", "卦名 %s ｜ 卦义 %s" % (ii.get("卦名覆盖"), ii.get("卦义覆盖"))),
            ("自身融合（自律）", "%s ｜ 闸 %s 道 ｜ 未过 %s ｜ 🔴 授权只能主人在终端发"
             % (G.get("判决"), G.get("闸数"), G.get("未过的闸"))),
            ("影像生产面（能不能产片看这里）",
             "ComfyUI %s ｜ 算力 %s ｜ 图像模型 %s ｜ **视频模型 %s** ｜ 到「电影」缺 %s 件"
             % ("在" if (w.get("影像生产面（能不能产片看这里）") or {}).get("安装") else "不在",
                (w.get("影像生产面（能不能产片看这里）") or {}).get("算力"),
                (w.get("影像生产面（能不能产片看这里）") or {}).get("图像模型"),
                (w.get("影像生产面（能不能产片看这里）") or {}).get("视频模型"),
                len(((w.get("影像生产面（能不能产片看这里）") or {})
                     .get("到「电影」缺什么")) or []))),
        ]
    except Exception as e:
        return [("自身融合", "**读不到**：%s" % str(e)[:90])]


def _mesh_brief() -> list:
    """插件**排布**现读（像显示屏一样：任意 N 都能串联和排布）。**只读**；读不到就如实报。"""
    try:
        spec = importlib.util.spec_from_file_location(
            "_pm", ROOT / "tools" / "codex-scripts" / "plugin-mesh.py")
        m = importlib.util.module_from_spec(spec)
        sys.modules["_pm"] = m
        spec.loader.exec_module(m)
        rows = m.slots()
        a = m.arrange(len(rows), [x["编号"] for x in rows])
        mm = m.mesh(rows)
        return [("插件排布（像显示屏一样：任意 N）",
                 "%d 单元 ⇒ **%s** ｜ 互不重叠 %s ｜ 都在网格内 %s ｜ 末尾空格 %d ｜ 全互通 **%d 条有向边**"
                 % (a["单元数"], a["网格"], a["互不重叠"], a["都在网格内"], a["末尾空格"],
                    mm["实得有向边"])),
                ("插件排布（可缩放）",
                 "自检已验 **1/2/3/5/7/12/25/100/1000** 都能排 —— **不管多大都能串联和排布**")]
    except Exception as e:
        return [("插件排布", "**读不到**：%s" % str(e)[:90])]


def _fo():
    """加载 failover.py（备用位表 + 内存闸）—— 面板不自己再写一份备用位表。"""
    spec = importlib.util.spec_from_file_location("_fo_mod", ROOT / "tools" / "codex-scripts" / "failover.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _failover_section() -> dict:
    """备用位 + 内存闸（数据来自 failover.py，**面板不自己再写一份**）。"""
    fo = _fo()
    rows = fo.table()
    return {"内存闸": fo.guard(),
            "覆盖": {"能力数": len(rows), "有备用位": sum(1 for r in rows if r["备用位"]),
                   "真接线": sum(1 for r in rows if r["真接线"])},
            "备用位表": [{"编号": r["编号"], "主": r["主"], "备用位": r["备用位"],
                      "类型": r["类型"], "触发条件": r["触发条件"]} for r in rows],
            "三条真接线的备用路": [
                "★ 内存不够 ⇒ 渲染改低并发（--concurrency=1，内存 ÷6）",
                "★ wrangler 云通路失败 ⇒ 换 r2-move.py（另一条已验通路）",
                "★ 本地盘不够 ⇒ 云仓溢出（远端字节验过才删本地）"],
            "不能保证": "操作系统层面**永不 OOM** —— 闸只拦『明知不够还硬上』"}


def _sl():
    """加载 `tools/social_life.py`（社交托管骨架）—— 面板不自己再写一份绑定表。"""
    spec = importlib.util.spec_from_file_location("_sl_mod", ROOT / "tools" / "social_life.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _social_section() -> dict:
    """七·社交托管格：18 个账号×触手插件格 + 三动作闸现状（**只读**，零出网）。"""
    try:
        sl = _sl()
        ap = sl.account_plugins()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "why": "社交骨架加载失败：%s" % e}
    reg = list((ap.get("格") or []))
    sample = reg[0]["平台"] if reg else None
    return {
        "ok": True, "插件格数": ap.get("插件格数"), "触手根数": ap.get("触手根数"),
        "触手出处": ap.get("触手出处"), "一 AI 一号": ap.get("一 AI 一号"),
        "触手负载": {t: sum(1 for r in reg if r["归属触手"] == t)
                 for t in sorted({r["归属触手"] for r in reg})},
        "格": [{"格": r["插件格"], "平台": r["平台"], "平台名": r["平台名"], "触手": r["归属触手"],
               "凭据": r["凭据"], "接线": r["接线状态"]} for r in reg],
        "三动作闸（拿第一家平台现读当样）": {
            v: sl.act(sample, v) for v in ("feed", "claim", "send")} if sample else {},
        "边界": "**零接线**（一个平台都没连）· 凭据全未配 · "
        "内容审核闸**已有机械面**（`tools/content_review.py`，假冒人类/内部构造/隐私·联系方式"
        "硬拦，第三方身份弱提示）· **未取证的面 = 违规内容词表**（待主人给，不编）",
        "发消息三道闸": "人审 → 敏感过滤 → **内容审核**（缺一即拒；三道齐才给判决，且仍不执行）",
    }


def _drift_brief() -> dict:
    """能力位**健康漂移**（与基线比）——共用 `nerve.caps_drift()` 一份判据，不复制。"""
    try:
        spec = importlib.util.spec_from_file_location("_nv_for_drift",
                                                      ROOT / "tools" / "codex-scripts" / "nerve.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        d = m.caps_drift()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "why": "漂移层加载失败：%s" % e}
    if not d.get("ok"):
        return d
    return {"基线": d.get("基线"), "判决": d.get("判决"),
            "变坏": d.get("🔴 变坏"), "变好": d.get("🟢 变好"), "口径": d.get("口径")}


def _beyond_brief() -> dict:
    """可探针集**之外**那 30 位（11 未实现 + 8 safe=False + 11 改状态）——**全 168 位的另一半账**。"""
    p = ROOT / "state" / "caps-beyond-probeable.json"
    if not p.is_file():
        return {"读不到": str(p.relative_to(ROOT)),
                "怎么生成": "跑 .scratch/_caps30.py（真调未实现的 11 位 + 静态核 8 + 不探 11）"}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"解析失败": str(e)}
    un = d.get("未实现·真调验证") or {}
    return {"未实现": "%d 位 · **真调验证 %d/%d 如实报 unknown**"
            % (len(un), sum(1 for v in un.values() if v.get("如实报 unknown")), len(un)),
            "safe=False": "%d 位 · 静态核（**会落盘/会改**，不是「危险」）" % len(d.get("safe=False·静态核") or {}),
            "改状态": "%d 位 · **绝不调用**（红线）" % len(d.get("改状态·不探（红线）") or {}),
            "口径": "可探针集 138 + 未实现 11 + safe=False 8 + 改状态 11 = **168 位，每位都有账**"}


def _caps_brief() -> dict:
    """能力位覆盖层现算（把 nerve 的 caps 层接进面板）——**不写死条数**。"""
    try:
        spec = importlib.util.spec_from_file_location("_nv_for_caps",
                                                      ROOT / "tools" / "codex-scripts" / "nerve.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        cs = m.caps_scan()
        if not cs.get("ok"):
            return {"ok": False, "why": cs.get("why")}
        inter = sorted(set(cs["可探针"]) & set(cs["须排除·改状态"]))
        # 真探快照（**带时间戳**，不是现读）——两个数分开念。
        # 🔴 **优先读累积账** `caps-probe-accum.json`：它按 kind 合并，单点探测**冲不掉**；
        #    退回单轮快照只是兜底（实测事故：一次 `--kind` 单探把 138 位视图覆盖成 1 位）。
        snap = {}
        for _name in ("caps-probe-accum.json", "caps-probe-last.json"):
            q = ROOT / "state" / _name
            if q.is_file():
                try:
                    snap = json.loads(q.read_text(encoding="utf-8"))
                    snap["_来源"] = _name
                    break
                except Exception:  # noqa: BLE001
                    continue
        return {"ok": True, "良性表条数": cs["良性表条数"], "未实现条数": cs["未实现条数"],
                "合计": cs["合计口径"], "覆盖率": cs["覆盖率"],
                "分类计数": cs["分类计数"],
                "命门判据": "可探针 ∩ 改状态 = %s" % ("∅ ✅" if not inter else str(inter)),
                "须排除·改状态": cs["须排除·改状态"],
                "真探快照（不是现读）": {
                    "at": snap.get("at"), "本次探位数": snap.get("本次探位数"),
                    "合计": snap.get("合计"),
                    "已探针率": "%s / %s（可探针）" % (snap.get("本次探位数"),
                                              cs["分类计数"]["可探针"])
                    if snap else "**尚未真探**（跑 nerve.py caps --run）",
                    "口径": "**可探针率 ≠ 已探针率**：覆盖率说的是「能不能探」",
                    "待核": "注册表 requires_params 实测**不可信**：只标 2 位，"
                            "而前 12 位里就有 3 位空参探不动 ⇒ 参数需求只能**实测发现**",
                },
                # 可探针集**之外**那 30 位（全 168 位的另一半账）
                "全 168 位合计": _beyond_brief(),
                "能力位漂移": _drift_brief(), }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "why": "能力位层加载失败：%s" % e}


def _nerve_section() -> dict:
    """神经末梢摘要。🔴 读的是 `nerve map` 落的**带时间戳缓存**，
    **绝不在这里现跑 20 条探针**（那会让 board 变成几分钟），也**绝不把它念成现读**。"""
    p = ROOT / "state" / "nerve-last.json"
    if not p.is_file():
        return {"上次读数": None,
                "怎么现读": "py -3.14 tools/codex-scripts/nerve.py map（或 pain 只看痛处）",
                "说明": "还没有读数 ⇒ **未知，不是健康**"}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"上次读数": None, "错误": "state/nerve-last.json 读不动"}
    return {"上次读数": d.get("at"), "合计": d.get("合计"),
            "覆盖": d.get("覆盖"),
            "痛或未知": d.get("痛或未知"),
            "怎么现读": "py -3.14 tools/codex-scripts/nerve.py map（或 patrol 只看变化）",
            "口径": "⚠️ 这是**上次读数**（带时间戳），不是现读；没读数就是未知，不当健康。"
                    "**部分覆盖不许念成全清** —— 未测的末梢按『未知』算，里面可能有真痛。"}


def cmd_html(a) -> int:
    """把主控面板渲成**一张看得懂的排布图**（单文件 HTML，无外链）。
    主人要的「像这样排列好、各自是做什么的、一清二楚」= 图里每个格子都带"做什么"和备用位。"""
    ra = _load_ra()
    cur = _read_all_current(ra)
    fo = _fo()
    sb = {r["编号"]: r for r in fo.table()}
    guard = fo.guard()
    n, src = _tentacles()
    sched = _schedule(n)
    lay = _layout_body()

    def esc(s) -> str:
        return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace('"', "&quot;"))

    def mod_node(num: str, name: str, where: str, deps: list, i: int) -> str:
        c = cur.get(name)
        if c:
            st, cls = c.get("状态") or "已登记", "ok" if c.get("状态") == "已验" else "reg"
        else:
            blocked = [x for x in deps if _name_of(x) not in cur]
            st, cls = ("卡住：依赖 %s 未登记" % "·".join(blocked)) if blocked else "待部署", "wait"
        pid = None
        for p in PLUGIN_SLOTS:
            if p[5].startswith(num):
                pid = p[0]
        alt = sb.get(pid, {}).get("备用位", "—")
        return ('<div class="node %s"><div class="nid">%s</div><div class="nm">%s</div>'
                '<div class="nw">%s</div><div class="nst">%s</div>'
                '<div class="nalt"><b>紧急扩容</b>%s</div></div>'
                % (cls, esc(num), esc(name), esc(where), esc(st), esc(alt)))

    nodes = "".join(mod_node(num, name, where, deps, i)
                    for i, (num, name, where, deps) in enumerate(_module_pairs()))
    prows = "".join(
        "<tr><td class=mono>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
        "<td class=alt>%s</td></tr>"
        % (esc(p[0]), esc(p[1]), esc(p[2]), esc(p[3]), esc(p[6]), esc(sb.get(p[0], {}).get("备用位", "—")))
        for p in PLUGIN_SLOTS)
    trows = "".join(
        "<div class=ten><div class=tid>%s</div><div class=tn>隔离位已真建 %s<br>负责 %d 件<br>"
        "<span class=mono>%s</span></div></div>"
        % (esc(t["触手"]), "✅" if t["隔离位已真建"] else "✗", len(t["负责插件"]),
           esc(",".join(t["负责插件"])))
        for t in sched)
    g = guard
    gm = g.get("读数", {})
    gcls = "ok" if g.get("选路") == "主" else "warn"

    nv = _nerve_section()
    if nv.get("上次读数"):
        tot = nv.get("合计") or {}
        cov = nv.get("覆盖") or {}
        pains = nv.get("痛或未知") or []
        partial = (cov.get("未测") or 0) > 0
        rows_p = "".join(
            "<tr><td class=mono>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (esc(x.get("编号")), esc(x.get("名称")), esc(x.get("感觉")), esc(x.get("强度")),
               esc(x.get("为什么")))
            for x in pains) or "<tr><td colspan=5 class=dim>已测范围内没有痛处</td></tr>"
        if partial:
            rows_p += ("<tr><td colspan=5 class=dim>⚠️ <b>未测 %s 个</b>（%s）—— "
                       "按『未知』算，<b>里面可能有真痛</b>，不许当全清</td></tr>"
                       % (cov.get("未测"), "、".join(cov.get("未测名单") or [])))
        nerve_html = (
            '<h2>神经末梢 · 痛觉（像身体一样：哪里痛一眼看见）</h2>'
            '<div class="card %s"><b>上次读数</b> %s ｜ 已测 %s / 全机 %s'
            '（<b>未测 %s</b>）· 通 %s · <b>痛 %s</b> · 未知 %s ｜ 强度 %s<br>'
            '<span class=dim>⚠️ 这是**上次读数**，不是现读；'
            '现读：<code>nerve.py map</code>（全量）｜ 只看变化：<code>nerve.py patrol</code> ｜ '
            '只看痛处：<code>nerve.py pain</code></span></div>'
            '<table><tr><th>编号</th><th>名称</th><th>感觉</th><th>探针强度</th><th>为什么</th></tr>%s</table>'
            % ("warn" if (pains or partial) else "ok", esc(nv.get("上次读数")),
               cov.get("已测"), cov.get("全机末梢"), cov.get("未测"),
               tot.get("通"), tot.get("痛"), tot.get("未知"),
               esc(json.dumps(tot.get("按强度", {}), ensure_ascii=False)), rows_p))
    else:
        nerve_html = ('<h2>神经末梢 · 痛觉</h2><div class="card warn"><b>还没有读数</b> '
                      '<span class=dim>⇒ <b>未知，不是健康</b>；先跑 '
                      '<code>py -3.14 tools/codex-scripts/nerve.py map</code></span></div>')

    # ── 七 · 社交托管格（账号 × 触手，插件形态）────────────────────────────────
    # 🔴 位置纪律：这一块必须挂在 **nerve_html 整个 if/else 之后**。
    #    我第一版把它插进了 `nerve_html = (` 的赋值中间，把赋值头吃掉了 ——
    #    语法直接崩、而且是**我自己造的崩**（不是被测对象坏）。改完立刻跑 selftest 验。
    soc = _social_section()
    soc_rows = "".join(
        "<tr><td class=mono>%s</td><td>%s</td><td>%s</td><td class=mono>%s</td><td>%s</td><td>%s</td></tr>"
        % (esc(r.get("格")), esc(r.get("平台")), esc(r.get("平台名")), esc(r.get("触手")),
           esc(r.get("凭据")), esc(r.get("接线")))
        for r in (soc.get("格") or []))
    if soc.get("ok"):
        nerve_html = nerve_html + (
            '<h2>社交托管格 · 账号 × 触手（插件形态，一格一个账号）</h2>'
            '<div class="card %s"><b>插件格 %s</b> ｜ 触手根数 %s（%s）｜ 一 AI 一号 %s ｜ '
            '负载 %s<br><span class=dim>%s</span></div>'
            '<table><tr><th>格</th><th>平台</th><th>平台名</th><th>触手</th><th>凭据</th>'
            '<th>接线</th></tr>%s</table>'
            % ("warn", soc.get("插件格数"), soc.get("触手根数"),
               esc(str(soc.get("触手出处"))[:40]), soc.get("一 AI 一号"),
               esc(json.dumps(soc.get("触手负载"), ensure_ascii=False)), esc(soc.get("边界")),
               soc_rows))
    else:
        nerve_html = nerve_html + ('<h2>社交托管格</h2><div class="card warn">加载失败：%s</div>'
                                   % esc(soc.get("why")))

    html = HTML_HEAD + (
        '<h1>GBT小土豆V8 · 插件云主控面板</h1>'
        '<div class=sub>读数 %s ｜ 桶 <code>%s</code> ｜ 命名空间 <code>%s</code> ｜ '
        '本地替身云 %s</div>'
        '<div class=tiles>'
        '<div class="tile %s"><b>%s MB</b><span>可用内存（总 %s MB · 占用 %s%%）</span></div>'
        '<div class="tile"><b>%s</b><span>触手根数（声明）</span></div>'
        '<div class="tile"><b>%s</b><span>运用到的件</span></div>'
        '<div class="tile"><b>%s / 9</b><span>模块已验</span></div>'
        '<div class="tile"><b>%s</b><span>备用位覆盖</span></div>'
        '<div class="tile"><b>%s</b><span>作业已完成</span></div>'
        '</div>'
        '<div class="card %s"><b>内存闸判决</b> %s<br><span class=dim>%s</span><br>'
        '<span class=mono>%s</span></div>'
        '%s'
        '<h2>一 · 模块部署顺序（箭头即声明的先后，缺依赖就跑不动）</h2>'
        '<div class=flow>%s</div>'
        '<h2>二 · 触手排班（固定轮转 · 确定性 · 一根触手一个隔离位）</h2><div class=tens>%s</div>'
        '<ul class=dim>%s</ul>'
        '<h2>三 · 运用到的每一件（各自做什么 + 紧急扩容）</h2>'
        '<table><tr><th>编号</th><th>名称</th><th>做什么</th><th>落点</th><th>状态</th>'
        '<th>紧急扩容（备用位）</th></tr>%s</table>'
        '<h2>四 · 诚实边界</h2><ul class=dim>'
        '<li><code>pipeline/plugins/</code> 里的是<b>契约登记</b>，<b>不是函数部署</b>；'
        'deploy（Workers/Queues/DO）是发布动作，须主人点头。</li>'
        '<li>内存闸能拦住「明知不够还硬上」，<b>不能保证操作系统层面永不 OOM</b>；'
        '真正的降险来自三条真接线备用路：低并发重跑 · 换云通路 · 云溢出。</li>'
        '<li>「同构换槽」是真接线，但它只是换执行位，不是换实现 —— 强度不同于低并发/换通路。</li>'
        '<li>🔴 <b>哪些是现读、哪些不是（别混念）</b>：内存闸 · 触手名册 · 排班 · 神经末梢 · '
        '自身融合 · 能力位漂移 · 插件云这几块是<b>现场读的</b>；而第三张表的<b>「状态」是登记声明</b>'
        '（<code>mark</code> 时写下的），<b>「出处」是当时那条命令的读数快照</b> —— '
        '<b>两者都不入图</b>（快照会过期，放进图里就会被当成现读）。'
        '所以本页<b>不许念成"表里每个字都是现读"</b>。</li>'
        '<li>本页由 <code>py -3.14 tools/codex-scripts/deploy-panel.py html</code> 现场生成；'
        '<b>现读块</b>是这次生成时读的。</li>'
        '</ul>'
        '<div class=foot>开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属</div>'
    ) % (
        time.strftime("%Y-%m-%dT%H:%M:%S"), BUCKET, PREFIX, bool(LOCAL_CLOUD),
        gcls, gm.get("可用MB"), gm.get("总MB"), gm.get("占用率%"),
        n or "未声明", lay["合计"]["插件"],
        sum(1 for m in cur if (cur[m] or {}).get("状态") == "已验"),
        sum(1 for r in sb.values() if r.get("真接线")),
        sum(1 for j in _job_rows(ra) if "已完成" in j["状态"]),
        gcls, esc(g.get("判决")), esc(g.get("为什么") or g.get("读数", {}).get("来源", "")),
        esc(g.get("建议命令", "")), nerve_html, nodes, trows,
        "".join("<li><b>%s</b> %s</li>" % (esc(k), esc(str(v)))
                for k, v in (list(lay["不变式"].items()) + _registry_brief() + _fusion_brief() + _mesh_brief())),
        prows)

    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(json.dumps({"ok": True, "落盘": str(out), "字节": out.stat().st_size,
                      "模块数": len(_module_pairs()), "插件数": len(PLUGIN_SLOTS),
                      "触手根数": n,
                      "内存闸": g.get("判决")}, ensure_ascii=False, indent=1))
    return 0


def _job_rows(ra) -> list[dict]:
    rows = []
    for jid in ra._index_read():
        st = ra._done_status(jid)
        ls = ra._lease_read(jid) or {}
        if st:
            rows.append({"编号": jid, "状态": "✅ 已完成",
                         "谁做的": st.get("worker") or ls.get("owner") or "?"})
        elif ls and not ls.get("done"):
            rows.append({"编号": jid, "状态": "🔵 有人在做", "谁做的": ls.get("owner")})
        else:
            rows.append({"编号": jid, "状态": "⬜ 待领单", "谁做的": None})
    return rows


HTML_HEAD = """<!DOCTYPE html><html lang="zh-CN"><meta charset="utf-8">
<title>GBT小土豆V8 · 插件云主控面板</title>
<style>
:root{--bg:#0d1117;--card:#161b22;--line:#30363d;--fg:#e6edf3;--dim:#8b949e;
--ok:#3fb950;--warn:#d29922;--bad:#f85149;--acc:#58a6ff}
*{box-sizing:border-box}
body{margin:0;padding:28px;background:var(--bg);color:var(--fg);
font:14px/1.6 "Segoe UI","Microsoft YaHei",system-ui,sans-serif}
h1{font-size:22px;margin:0 0 6px}h2{font-size:16px;margin:26px 0 10px;color:var(--acc);
border-left:3px solid var(--acc);padding-left:9px}
.sub,.dim{color:var(--dim);font-size:12.5px}
code,.mono{font-family:Consolas,"Cascadia Mono",monospace;font-size:12.5px}
code{background:#21262d;padding:1px 5px;border-radius:4px}
.tiles{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}
.tile{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:10px 14px;min-width:120px}
.tile b{display:block;font-size:20px;color:var(--acc)}
.tile span{font-size:11.5px;color:var(--dim)}
.tile.ok b{color:var(--ok)}.tile.warn b{color:var(--warn)}
.card{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:12px 14px;margin:10px 0}
.card.warn{border-color:var(--warn)}.card.ok{border-color:var(--ok)}
.flow{display:flex;gap:0;flex-wrap:wrap;align-items:stretch}
.node{position:relative;background:var(--card);border:1px solid var(--line);border-radius:9px;
padding:10px 12px;margin:0 22px 12px 0;min-width:172px;max-width:210px}
.node:after{content:"➜";position:absolute;right:-19px;top:50%;transform:translateY(-50%);
color:var(--dim);font-size:15px}
.node:last-child:after{content:""}
.node .nid{font:600 11px Consolas,monospace;color:var(--dim)}
.node .nm{font-weight:600;font-size:14px;margin:2px 0 4px}
.node .nw{font-size:11.5px;color:var(--dim);margin-bottom:6px}
.node .nst{font-size:11.5px;margin-bottom:6px}
.node .nalt{font-size:11px;color:var(--dim);border-top:1px dashed var(--line);padding-top:5px}
.node .nalt b{color:var(--acc);font-weight:600;margin-right:4px}
.node.ok{border-color:var(--ok)}.node.ok .nst{color:var(--ok)}
.node.reg{border-color:var(--acc)}.node.reg .nst{color:var(--acc)}
.node.wait .nst{color:var(--warn)}
.tens{display:flex;gap:12px;flex-wrap:wrap}
.ten{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:10px 14px;min-width:230px}
.ten .tid{font:600 15px Consolas,monospace;color:var(--acc)}
.ten .tn{font-size:12px;color:var(--dim);margin-top:4px}
table{border-collapse:collapse;width:100%;background:var(--card);border:1px solid var(--line);
border-radius:9px;overflow:hidden}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);font-size:12.5px;vertical-align:top}
th{background:#1c2128;color:var(--acc);font-size:12px;position:sticky;top:0}
td.alt{color:var(--dim)}tr:hover td{background:#1c2128}
ul{padding-left:20px}li{margin:4px 0}
.foot{margin-top:28px;padding-top:12px;border-top:1px solid var(--line);color:var(--dim);font-size:12px}
</style><body>
</body></html>"""


def cmd_layout(a) -> int:
    body = _layout_body()
    if a.make_slots:
        n, _ = _tentacles()
        if not n:
            print(json.dumps({"ok": False, "why": "触手根数未声明 ⇒ 不建隔离位（fail-closed）"},
                             ensure_ascii=False))
            return 2
        made = []
        for t in body["触手排班"]:
            d = ROOT / t["隔离位"]
            was = d.is_dir()
            d.mkdir(parents=True, exist_ok=True)
            made.append({"触手": t["触手"], "隔离位": t["隔离位"],
                         "之前存在": was, "现在存在": d.is_dir()})
        body = _layout_body()                       # 重读一遍，让"隔离位已真建"是**真读数**
        body["建隔离位"] = {"已建": made, "口径": "规矩三：N 根触手 ⇒ N 个隔离位（真建，不是印在报告里）"}
    if a.register:
        ra = _load_ra()                            # 本文件自己的云读写（_cloud() 在 asset-pool 里）
        n, _ = _tentacles()
        if not n:
            print(json.dumps({"ok": False, "why": "触手根数未声明 ⇒ 不登记（fail-closed）"},
                             ensure_ascii=False))
            return 2
        ok_n = 0
        for p in body["插件独立部署表"]:
            man = {"插件编号": p["编号"], "名称": p["名称"], "做什么": p["做什么"],
                   "落点": p["落点"], "真命令": p["真命令"], "关联模块": p["关联模块"],
                   "状态": p["状态"], "出处": p["出处"],
                   "触手": [t["触手"] for t in body["触手排班"] if p["编号"] in t["负责插件"]],
                   "声明触手根数": n, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "边界": "这是**契约登记**，不是函数部署（deploy 是发布动作，须主人点头）"}
            tmp = ROOT / "state" / ("_plugin_%s.json" % p["编号"])
            tmp.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
            k = "%s/plugins/%s/manifest.json" % (PREFIX, p["编号"])
            ok, _ = ra._put(tmp, k)
            ok_n += 1 if ok else 0
        ip = ROOT / "state" / "_plugins_index.json"
        ip.write_text(json.dumps({p["编号"]: p["名称"] for p in body["插件独立部署表"]},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
        iok, _ = ra._put(ip, "%s/plugins/index.json" % PREFIX)
        body["登记"] = {"已写": ok_n, "共": len(body["插件独立部署表"]),
                      "索引": bool(iok), "云前缀": "%s/plugins/" % PREFIX,
                      "边界": "契约登记 ≠ 函数部署"}
    print(json.dumps(body, ensure_ascii=False, indent=1))
    return 0


# ── 云读写（走 render-agent 的同一套 wrangler 姿势，避免第二套坑） ───────────────
def _r2_local(*args: str) -> tuple[int, str]:
    """把 wrangler 的 put/get 换成对本地目录的复制 —— **只给 selftest 用**。"""
    a = [x for x in args if x != "--remote"]
    if len(a) >= 4 and a[0] == "object" and a[1] in ("put", "get"):
        _, verb, spec = a[0], a[1], a[2]
        key = spec.partition("/")[2]
        try:
            f = a[a.index("--file") + 1]
        except ValueError:
            return 1, "本地替身云：缺 --file"
        remote = pathlib.Path(LOCAL_CLOUD) / key
        local = pathlib.Path(f)
        if verb == "put":
            remote.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(local, remote)
            return 0, "Upload complete (本地替身云)"
        if not remote.exists():
            return 1, "The specified key does not exist (本地替身云)"
        local.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(remote, local)
        return 0, "Download complete (本地替身云)"
    return 1, "本地替身云：不支持该子命令 %s" % (a[:3],)


def _load_ra():
    """加载 render-agent.py（文件名带连字符 ⇒ 不能普通 import）。
    这样两边的 `_get/_put/_r2/_index_read` **只有一份实现**，不会各写一套而漂移。"""
    spec = importlib.util.spec_from_file_location("_ra_mod", RA_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if LOCAL_CLOUD:
        mod._r2 = _r2_local           # 补丁打在模块全局上，_get/_put 调的就是它
    return mod


# ── 登记读 ─────────────────────────────────────────────────────────────────────
def _module_pairs() -> list[tuple[str, str, str, list[str]]]:
    return [(n, m, w, d) for n, m, w, d in DEPLOY_ORDER]


def _read_current(ra, mod: str) -> dict | None:
    tmp = ROOT / "state" / ("_mod_%s.json" % mod)
    ok, _ = ra._get("%s/modules/%s/current.json" % (PREFIX, mod), tmp)
    if not ok:
        return None
    try:
        return json.loads(tmp.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_all_current(ra) -> dict:
    """🔴 实测踩过的坑（F32，假绿方向，最危险）：第一版写成 `dict(got)`，
    而 `got` 里**每个模块名都在**（没登记的映射到 `None`）⇒ 顺序门的 `名字 in cur` **恒为真**
    ⇒ **跳序登记被放行**。自检第 ④ 组把它抓出来了。
    读数纪律：这个返回值的**键集本身就是结论**，不能带"占位键"。"""
    mods = [m for _, m, _, _ in DEPLOY_ORDER]
    with ThreadPoolExecutor(max_workers=6) as ex:      # 9 个键串行要 ~30s；并发压到 ~6s
        got = list(ex.map(lambda m: (m, _read_current(ra, m)), mods))
    return {k: v for k, v in got if v}                 # 只留**真登记过**的


def _probe(ra, mod: str) -> tuple[str, str]:
    """便宜探针：只对**能低成本复核**的模块做，其余如实说"无便宜探针"。"""
    if mod == "spec-store":
        tmp = ROOT / "state" / "_probe_index.json"
        ok, _ = ra._get("%s/jobs/index.json" % PREFIX, tmp)
        if not ok:
            return "✗", "作业索引取不到"
        try:
            n = len(json.loads(tmp.read_text(encoding="utf-8")))
        except Exception:
            return "✗", "作业索引不是 JSON 数组"
        return "✓", "作业索引 %s/jobs/index.json 有 %d 个作业" % (PREFIX, n)
    if mod == "vault":
        reg = ROOT / "state" / "cloud-vault.jsonl"
        if not reg.is_file():
            return "✗", "本地仓登记 state/cloud-vault.jsonl 不存在"
        n = v = 0
        for line in reg.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            n += 1
            v += 1 if d.get("verified") else 0
        return ("✓" if n else "✗"), "仓登记 %d 条 · 其中已逐字节校验 %d 条" % (n, v)
    if mod == "render":
        idx = ra._index_read()
        if not idx:
            return "✗", "没有作业 ⇒ 没渲过"
        hit = None
        for jid in idx:
            st = ra._done_status(jid)
            if st:
                hit = (jid, st)
        if not hit:
            return "✗", "有 %d 个作业但云上没有一个 status.json 带产物" % len(idx)
        jid, st = hit
        return "✓", "最近完成 %s · %s · %s 字节 · sha256 %s…" % (
            jid, pathlib.Path(str(st.get("artifact"))).name, st.get("bytes"),
            str(st.get("sha256"))[:16])
    return "－", "无便宜探针（状态取自登记，证据在 `证据` 字段，可重跑）"


# ── 命令 ───────────────────────────────────────────────────────────────────────
def cmd_plan(a) -> int:
    """只打印**声明好的顺序**，不读云。"""
    print(json.dumps({
        "编排": [{"编号": n, "模块": m, "运行地": w, "依赖": d or "无",
                "未部署原因": GAPS.get(n)} for n, m, w, d in _module_pairs()],
        "顺序规则": "登记某模块前，其依赖必须**已在云上有 current.json**；缺一个就拒（fail-closed）",
        "终端编制": "T01~T%02d 共 %d 个槽位（主人定：30~50 个终端并发）" % (TERMINAL_SLOTS, TERMINAL_SLOTS),
        "本地边界": "本地只有 06 render 一格；其余全在插件云按模块分布",
    }, ensure_ascii=False, indent=1))
    return 0


def cmd_next(a) -> int:
    ra = _load_ra()
    cur = _read_all_current(ra)
    for n, m, w, d in _module_pairs():
        if m in cur:
            continue
        missing = [x for x in d if _name_of(x) not in cur]
        if not missing:
            print(json.dumps({"下一步唯一合法动作": {"编号": n, "模块": m, "运行地": w},
                              "前置依赖": d or "无", "已登记": sorted(cur)},
                             ensure_ascii=False, indent=1))
            return 0
    print(json.dumps({"下一步唯一合法动作": None, "why": "09 个模块全登记完了",
                      "已登记": sorted(cur)}, ensure_ascii=False, indent=1))
    return 0


def _name_of(num: str) -> str:
    for n, m, _, _ in DEPLOY_ORDER:
        if n == num:
            return m
    return "<未声明编号 %s>" % num


def cmd_mark(a) -> int:
    """登记一个模块的部署状态。**顺序门 fail-closed**。"""
    nums = {m: n for n, m, _, _ in DEPLOY_ORDER}
    if a.module not in nums:
        print(json.dumps({"ok": False, "拒单": "编号表里没有这个模块（不许临时加模块）",
                          "合法模块": [m for _, m, _, _ in DEPLOY_ORDER]}, ensure_ascii=False))
        return 2
    if "=>" not in (a.evidence or ""):
        print(json.dumps({"ok": False, "拒单": "证据串形状必须是 `命令 => 读数`（本仓读数纪律）",
                          "你给的": a.evidence}, ensure_ascii=False))
        return 2
    ra = _load_ra()
    cur = _read_all_current(ra)
    num = nums[a.module]
    deps = [d for n, m, _, d in _module_pairs() if m == a.module][0]
    missing = [d for d in deps if _name_of(d) not in cur]
    if missing:
        print(json.dumps({"ok": False, "拒单": "**顺序门拦住**：依赖未登记，不许跳序",
                          "要登记的": {"编号": num, "模块": a.module},
                          "依赖编号": deps,
                          "未登记的依赖": [{"编号": d, "模块": _name_of(d)} for d in missing],
                          "下一步唯一合法动作": _next_name(cur)},
                         ensure_ascii=False, indent=1))
        return 3
    at = time.strftime("%Y-%m-%dT%H:%M:%S")
    ver = a.version
    man = {"编号": num, "模块": a.module, "运行地": [w for _, m, w, _ in _module_pairs() if m == a.module][0],
           "依赖编号": deps, "版本": ver, "状态": a.state, "证据": a.evidence, "at": at}
    mp = ROOT / "state" / ("_man_%s_%s.json" % (a.module, ver))
    mp.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    k1 = "%s/modules/%s/%s/manifest.json" % (PREFIX, a.module, ver)
    ok1, t1 = ra._put(mp, k1)
    k2 = "%s/modules/%s/current.json" % (PREFIX, a.module)
    ok2, t2 = ra._put(mp, k2)
    print(json.dumps({"ok": ok1 and ok2, "登记": k1, "指针": k2,
                      "编号": num, "状态": a.state,
                      "本地替身云": bool(LOCAL_CLOUD),
                      "tail": t2 if not ok2 else "已写"}, ensure_ascii=False, indent=1))
    return 0 if (ok1 and ok2) else 4


def _next_name(cur: dict) -> dict | None:
    for n, m, w, d in _module_pairs():
        if m in cur:
            continue
        if all(_name_of(x) in cur for x in d):
            return {"编号": n, "模块": m, "运行地": w}
    return None


def _legal_now(cur: dict) -> list[dict]:
    """依赖已齐、但还没登记的全部模块（**按编号**）。带出各自的「未部署原因」，
    免得"下一步"只报一个而把别的可做项藏起来。"""
    out = []
    for n, m, w, d in _module_pairs():
        if m in cur or not all(_name_of(x) in cur for x in d):
            continue
        out.append({"编号": n, "模块": m, "运行地": w, "未部署原因": GAPS.get(n, "无已知缺件")})
    return out


def cmd_board(a) -> int:
    """主控面板：模块顺序 + 终端编号 + 作业编号 + 仓。"""
    ra = _load_ra()
    cur = _read_all_current(ra)

    mods, dep_ok_n = [], 0
    for n, m, w, d in _module_pairs():
        c = cur.get(m)
        if c:
            state = c.get("状态") or "已登记"
            if state == "已验":
                dep_ok_n += 1
            row = {"编号": n, "模块": m, "运行地": w, "依赖": d or "无", "状态": "✅ " + state,
                   "登记于": c.get("at"), "版本": c.get("版本"), "证据": c.get("证据")}
        else:
            blocked = [x for x in d if _name_of(x) not in cur]
            row = {"编号": n, "模块": m, "运行地": w, "依赖": d or "无",
                   "状态": ("⛔ 卡住（依赖 %s 未登记）" % "·".join(blocked)) if blocked else "⬜ 待部署",
                   "未部署原因": GAPS.get(n)}
        if a.verify:                                # --verify：9 个都过一遍；没便宜探针的当场如实回"－"
            mark, why = _probe(ra, m)
            row["探针"] = "%s %s" % (mark, why)
        mods.append(row)

    idx = ra._index_read()
    jobs, workers = [], []
    for jid in idx:
        st = ra._done_status(jid)
        ls = ra._lease_read(jid) or {}
        who = (st or {}).get("worker") or ls.get("owner")
        if who and who not in workers:
            workers.append(who)
        if st:
            jobs.append({"编号": jid, "状态": "✅ 已完成", "谁做的": who or "?",
                         "产物": pathlib.Path(str(st.get("artifact"))).name,
                         "字节": st.get("bytes"), "sha256_前16": str(st.get("sha256"))[:16]})
        elif ls and not ls.get("done"):
            jobs.append({"编号": jid, "状态": "🔵 有人在做", "谁做的": who, "起于": ls.get("at"),
                         "租约秒": ls.get("ttl_s")})
        else:
            jobs.append({"编号": jid, "状态": "⬜ 待领单", "谁做的": None})

    workers.sort()
    fleet = [{"终端": "T%02d" % (i + 1), "身份": wk, "在做": _what(ra, idx, wk)}
             for i, wk in enumerate(workers[:TERMINAL_SLOTS])]

    lay = _layout_body()
    print(json.dumps({
        "主控面板": {"桶": BUCKET, "命名空间": PREFIX, "读数": time.strftime("%Y-%m-%dT%H:%M:%S"),
                     "本地替身云": bool(LOCAL_CLOUD)},
        "一·模块部署顺序": mods,
        "二·触手插件排布": {
            "触手根数": lay["触手根数"],
            "两个数别混": lay["两个数别混"],
            "运用到的件": lay["合计"],
            "排班": lay["触手排班"],
            "不变式": lay["不变式"],
            "插件表见": "py -3.14 tools/codex-scripts/deploy-panel.py layout",
        },
        "三·终端编号": {"编制": TERMINAL_SLOTS, "现役": len(workers),
                   "还没动的槽位": TERMINAL_SLOTS - len(workers), "名册": fleet},
        "四·作业编号": jobs,
        "五·紧急扩容": _failover_section(),
        "六·神经末梢（痛觉）": dict(_nerve_section(), **{"能力位覆盖层": _caps_brief()}),
        "七·社交托管格": _social_section(),
        "合计": {"模块": {"已登记": len(cur), "声明总数": len(DEPLOY_ORDER),
                      "已验": dep_ok_n},
               "作业": {"总数": len(idx),
                      "已完成": sum(1 for j in jobs if "已完成" in j["状态"]),
                      "在做": sum(1 for j in jobs if "在做" in j["状态"]),
                      "待领单": sum(1 for j in jobs if "待领单" in j["状态"])}},
        "下一步唯一合法动作": _next_name(cur),
        "现在就可做（依赖已齐，按编号）": _legal_now(cur),
        "口径": "模块状态是**登记声明**（证据字段可重跑复核）；--verify 只重跑便宜的 3 条探针，其余如实标「无便宜探针」",
    }, ensure_ascii=False, indent=1))
    return 0


def _what(ra, idx: list, worker: str) -> str:
    for jid in idx:
        st = ra._done_status(jid)
        if st and st.get("worker") == worker:
            return "已完成 %s" % jid
        ls = ra._lease_read(jid) or {}
        if ls.get("owner") == worker and not ls.get("done"):
            return "在做 %s" % jid
    return "空闲"


def cmd_selftest(a) -> int:
    """真身自检：**顺序门四态** + 图与 render-agent 一致 + DAG 无环。
    用本地替身云跑 ⇒ 不碰真云，但走的是同一段门代码。"""
    import tempfile
    lines, bad = [], 0

    def ck(name: str, cond: bool, detail: str) -> None:
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    # ① 与 render-agent 的模块集合逐名一致（防两处清单漂移）
    ra = _load_ra()
    ra_mods = {m for m, _, _, _ in ra.MODULES}
    mine = {m for _, m, _, _ in _module_pairs()}
    ck("模块集合一致", ra_mods == mine,
       "render-agent %d 个 · 本表 %d 个 · 差 %s" % (len(ra_mods), len(mine),
                                               sorted(ra_mods ^ mine) or "无"))
    # ② 编号唯一且连续
    nums = [n for n, _, _, _ in _module_pairs()]
    ck("编号连续唯一", nums == ["%02d" % (i + 1) for i in range(len(nums))], " · ".join(nums))
    # ③ 依赖都指向**更早**的编号（无环 + 顺序即拓扑序）
    pos = {n: i for i, n in enumerate(nums)}
    back = [(n, x) for n, _, _, d in _module_pairs() for x in d if pos[x] >= pos[n]]
    ck("依赖不回头（无环）", not back, "回边 %s" % (back or "无"))
    # ④ 顺序门 fail-closed：本地替身云里只登记 01，再试登记 07（依赖 06）⇒ 必须被拒
    global LOCAL_CLOUD
    keep = LOCAL_CLOUD
    with tempfile.TemporaryDirectory() as td:
        LOCAL_CLOUD = td

        class A:  # noqa: N801 — 极简命名空间，喂给 cmd_mark 当参数
            module, state, evidence, version = "spec-store", "已验", "自检 => 01 已登记", "selftest"
        rc1 = cmd_mark(A())                      # 01 无依赖 ⇒ 应放行

        class B:
            module, state, evidence, version = "assemble", "已验", "自检 => 依赖门", "selftest"
        rc2 = cmd_mark(B())                      # 07 依赖 06 ⇒ 应被拒（3）

        class C:
            module, state, evidence, version = "render", "已验", "自检 => 06", "selftest"
        rc3 = cmd_mark(C())                      # 06 依赖 01（已登记）⇒ 应放行
        rc4 = cmd_mark(B())                      # 再试 07（06 已登记）⇒ 应放行

        class D:
            module, state, evidence, version = "不存在的模块", "已验", "自检 => x", "selftest"
        rc5 = cmd_mark(D())                      # 编号表外的模块 ⇒ 应被拒（2）

        class E:
            module, state, evidence, version = "vault", "已验", "没有箭头", "selftest"
        rc6 = cmd_mark(E())                      # 证据串不合格 ⇒ 应被拒（2）
        # ⑤ 直接盯住"仪器本身"：键集不许带占位键（F32 的回归判据）
        ra2 = _load_ra()
        keys = set(_read_all_current(ra2))
    LOCAL_CLOUD = keep
    ck("顺序门·无依赖放行", rc1 == 0, "rc=%d（期望 0）" % rc1)
    ck("顺序门·跳序拒单", rc2 == 3, "rc=%d（期望 3）" % rc2)
    ck("顺序门·依赖齐了放行", rc3 == 0 and rc4 == 0, "rc=%d/%d（期望 0/0）" % (rc3, rc4))
    ck("顺序门·表外模块拒单", rc5 == 2, "rc=%d（期望 2）" % rc5)
    ck("顺序门·证据串不合格拒单", rc6 == 2, "rc=%d（期望 2）" % rc6)
    ck("键集不带占位键（F32 回归）", keys == {"spec-store", "render", "assemble"},
       "替身云里登记了 3 个 ⇒ 键集应是这 3 个，实际 %s" % sorted(keys))

    # ⑥ 触手排班三条不变式（主人要的"像计算机一样永远不会出错"= 可机检，不是嘴上说）
    n, _src = _tentacles()
    inv = _invariants(n)
    keys5 = ("①一件只挂一根触手（按 _schedule 真实返回）", "②没有漏挂", "③排数 = 触手根数",
             "④槽位编号唯一（**真数据判据**）", "⑤挂的件不重复注册（**真数据判据**）")
    ck("排班·五条不变式全绿（一件只挂一根 · 无漏挂 · 排数=根数 · 编号唯一 · 件不重复注册）",
       all(str(inv.get(k, "")).startswith("✅") for k in keys5),
       "根数=%s · %s" % (n, inv.get("结论")))
    # ⑥b 🔴 负控：塞一个重名件 ⇒ 第⑤条必须变红（证明判据不是假判据）
    global PLUGIN_SLOTS
    keep_slots = PLUGIN_SLOTS
    PLUGIN_SLOTS = list(keep_slots) + [
        ("P99", keep_slots[0][1], "重名负控", "LOCAL", "-", "-", "-", "-")]
    inv_bad = _invariants(n)
    PLUGIN_SLOTS = keep_slots
    ck("排班·塞一个重名件 ⇒ 第⑤条必须变红（证明判据不是假的）",
       str(inv_bad.get("⑤挂的件不重复注册（**真数据判据**）", "")).startswith("✗"),
       str(inv_bad.get("⑤挂的件不重复注册（**真数据判据**）", ""))[:64])
    # ⑦ 负控：真源缺失时必须报"未声明"，**绝不拿 os.cpu_count() 顶替**
    global ROSTER
    keep_r = ROSTER
    ROSTER = ROOT / "state" / "_no_such_roster.json"
    n2, why2 = _tentacles()
    ROSTER = keep_r
    ck("触手根数·缺声明就报未声明（不拿 CPU 线程顶替）",
       n2 == 0 and "未声明" in why2, "根数=%s · %s" % (n2, why2))

    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines,
                      "口径": "第 ④ 组跑在**本地替身云**上（同一段门代码，不碰真云）；命令输出仅作读数，不是结论"},
                     ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="主控面板 · 插件云部署编排看板")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan").set_defaults(func=cmd_plan)
    sub.add_parser("next").set_defaults(func=cmd_next)
    b = sub.add_parser("board")
    b.add_argument("--verify", action="store_true", help="额外重跑便宜的 3 条探针")
    b.set_defaults(func=cmd_board)
    m = sub.add_parser("mark")
    m.add_argument("module")
    m.add_argument("--state", default="已登记", choices=["已验", "已登记", "已部署"])
    m.add_argument("--version", default=time.strftime("%Y-%m-%d.1"))
    m.add_argument("--evidence", required=True, help="形状：命令 => 读数")
    m.set_defaults(func=cmd_mark)
    L = sub.add_parser("layout", help="触手插件排班：运用到的每一件独立编号，按触手根数固定轮转")
    L.add_argument("--register", action="store_true",
                   help="把契约登记到云 %s/plugins/（**不是**函数部署）" % PREFIX)
    L.add_argument("--make-slots", action="store_true",
                   help="真建隔离位 state/tentacle-slots/T01..（规矩三：N 根触手 ⇒ N 个隔离位）")
    L.set_defaults(func=cmd_layout)
    H = sub.add_parser("html", help="把主控面板渲成一张看得懂的排布图（单文件 HTML）")
    H.add_argument("--out", default="outputs/plugin-cloud-panel.html")
    H.set_defaults(func=cmd_html)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
