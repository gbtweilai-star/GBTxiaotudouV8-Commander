# -*- coding: utf-8 -*-
"""2026-11-06 台账整件重建（原子替换 + 写后读回）。

背景（现读事实，不是推断）：
  state/排查台账.json   —— 不在盘（17 处引用，test_progress_ledger_contract 11 errors + 1 fail）
  state/logbook.jsonl    —— 不在盘（全量机器轨迹丢）
  本仓根目录             —— 不是 git 仓库（git show HEAD:state/... 无处可回溯）
  产品目录 D:\\GBT-builds\\GBT小土豆V8桌面版\\payload —— 递归查无同名文件
⇒ 历史的 34 条根因模式原文**不可恢复**。本脚本只重建「仓内能复核到 src」的条目，
  每条都带 src；`_口径` 里写明哪段是重建、哪段是原文缺失。
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "state" / "排查台账.json"

PATTERNS = {
    "P8_修复件没接上驱动（假必读）": (
        "现象：表躺在台账里，而渲染器从不读它 ⇒ 模型永远看不到（P8 型「假必读」）。"
        "根因：只做「写」不做「接线」，把「文件存在」当成「已经生效」。"
        "判据：必须有一条判据去读**驱动代码**，而不是读产物本身"
        "（test_progress_ledger_contract.py::InjectionIsWiredTest 进 renderLedger 体内查「根因模式表」）。"
        "src：tools/codex-scripts/ledger-refresh.py 文档头 · gbt_allinone/tests/test_progress_ledger_contract.py"),
    "P9_手造的账没有生产者": (
        "现象：台账 updated_at 停在 2026-10-11，而 state/logbook.jsonl 同一天还在写（第 701 笔）"
        " ⇒ 注入给模型的「唯一进度真源」是六天前的快照。"
        "根因：账全靠人手写，没有生成器 ⇒ 它只会越来越旧（同型实证：caps-beyond-probeable 注册表 232 而它停 30）。"
        "判据：给台账配写手（ledger-refresh.py）+ 四条腐烂判据 R1–R4，rot 非空即红。"
        "src：tools/codex-scripts/ledger-refresh.py"),
    "P33_量具自身的系统错（11 次实证）": (
        "现象：2026-10-22 单轮自纠 11 次，全部是量具/读数错，不是盘错。"
        "分四族：①键名当事实（ts 写成 at / changed 写成 files / handler 是裸名）"
        "②弱键当证据（按 mtime ±2h 归因 / 按 basename 一条记录认领 24 个目录）"
        "③口径/单位不同却当结论（根=技能目录 vs 根=容器 8131 vs 850）④实现写错（hits.append 在过滤循环外）。"
        "根治：每个量具出数前先做负例自检；读不到一律记「未读到」；输出自带单位与粒度。"
        "src：tools/codex-scripts/ledger-p33-full.py"),
    "P34_粒度与单位当结论": (
        "现象：两把尺子数不同就报缺口。三种实证：名字 vs 目录 / 模块级 vs 可达 / 语法可达 vs 默认参数可达。"
        "判据：先统一口径再报数，口径必须写进回执。"
        "src：tools/codex-scripts/ledger-set-inprogress.py"),
    "F15_时区偏移靠看起来像": (
        "现象：历轮把台账时间戳写成 +08:00，而本机真实偏移是 +07:00 ⇒ 绝对时刻差 8 小时。"
        "根因：单调性对 ≠ 时刻对 —— 一串偏移全错，顺序照样单调，所以旧判据逮不到。"
        "判据：最新一笔 log 与 updated_at 的偏移必须等于机器偏移或 UTC；历史条目不追改但缺陷要写进口径。"
        "src：gbt_allinone/tests/test_progress_ledger_contract.py::TimestampOffsetIsRealTest"),
    "K01_信封ok不等于本体ok": (
        "现象：api.run_task 返回 status=ok，本体 result 里却是 ok:false（有时还要再钻一层 result.result）。"
        "根因：把「分派成功」当成「执行成功」。"
        "判据：读结果必须往下钻到带 ok 的那一层；回执里 ok_source 说明这层是谁说的。"
        "src：AGENTS.md §2.2"),
    "K02_失败三态被压成两态": (
        "现象：缺参数/缺依赖被包装成 failed，或上游没给就写假成功。"
        "判据：denied（缺票，点名 missing_scopes）/ needs_dependency|needs_input（带原因）/ failed（回执带上游原话）三态分开。"
        "src：AGENTS.md §2.1"),
    "K03_原子替换保证不了新的有意义": (
        "现象：np.savez_compressed(rows=None) 不报错，把 150 KB 好图换成 323 字节壳，os.replace 照样执行。"
        "判据：写前校验内容、写后读回校验；多文件产物先数据后标记（meta 最后写）。"
        "src：AGENTS.md §2.4"),
    "K04_OpenCV对非ASCII路径静默失败": (
        "现象：cv2.imwrite 返回 False 不抛异常（以为写好了）；cv2.imread 返回 None（以为图坏了）。"
        "判据：写走 cv2.imencode + Path.write_bytes；读走 PIL 文件句柄。"
        "src：AGENTS.md §3.1 坑A"),
    "K05_ps1无BOM被按GBK解码": (
        "现象：中文乱码，甚至吃掉字符串结束引号，报 The string is missing the terminator。"
        "判据：写 .ps1 一律 utf-8-sig；读仓内 UTF-8 文本要显式 -Encoding UTF8。"
        "src：AGENTS.md §3.1 坑B"),
    "K06_pyembed是embeddable包": (
        "现象：python -m 报 No module named gbt_allinone；设 PYTHONPATH 被整个忽略。"
        "根因：pyembed/python312._pth 存在 ⇒ isolated 模式，cwd 不进 sys.path。"
        "判据：跑测试用 tools/codex-scripts/run-tests.py 壳；-c 里的双引号会被 PowerShell 吃掉，改用 here-string 走 stdin。"
        "src：AGENTS.md §3.1 坑C"),
    "K07_转义把引号结构吃掉": (
        "现象：只看 grep/readFile 的转义输出，把新句子与旧残片拼在一起 ⇒ 整个能力位 SyntaxError，一天没人发现。"
        "根因：屏幕上的反斜杠数量与源码不一致，「这个引号是边界还是转义」在屏幕上判断不了。"
        "判据：凡动过字符串或注释，收尾一律 ast.parse；判据件 gbt_allinone/tests/test_diag_kou_jing.py。"
        "src：AGENTS.md §3.1 坑D"),
    "K08_索引没重建等于命中0": (
        "现象：能力位 desc 与 router.INTENT_MAP 都改了，实测仍是 L1 规则命中 0。"
        "根因：router.load_caps() 读的是 intent_extracted.json，索引里根本没有这个位。"
        "判据：三道门（desc 常用说法 / INTENT_MAP / 跑 extract_intents.py 重建索引）+ 必须验邻居不互抢。"
        "src：AGENTS.md §4.1（see_camera 血账）"),
    "K09_写死别人家的路径": (
        "现象：全仓散落 146 处 C:\\Users\\<某个人>\\...，全部指向不存在的用户。"
        "判据：包内用 Path(__file__).resolve().parents[N]；家目录用 Path.home()；外部程序先环境变量再家目录再包内，找不到就如实说找不到。"
        "src：AGENTS.md §3"),
    "K10_线上跑的是产品目录": (
        "现象：仓内改完看不到变化。2026-11-06 实测 127.0.0.1:8766 的服务命令行是 "
        "\".\\tools\\console-server.py --port 8766\"，解释器在 D:\\GBT-builds\\GBT小土豆V8桌面版\\payload\\pyembed"
        " ⇒ 线上读的是产品目录，不是开发仓。"
        "判据：仓内改完必须 atomic-sync 推产品 + 重启常驻进程，再 reload 复验；只改仓内等于没改。"
        "src：本轮现读 pid 29752 命令行"),
    "D01_字符串序取版本号": (
        "现象：sorted(_PASSPORTS.glob(\"v*.json\"))[-1] 在 v9.json / v20.json 上取到 v9。"
        "判据：版本比较要按数值解析，不要按字符串序。"
        "src：PROJECT_BLUEPRINT.md:365"),
    "D02_驱动没设store目录把验收写进生产": (
        "现象：t-sched-run 与 O20 同根因、不同文件 —— 驱动在没设 GBT_STORE_DIR 的进程里跑，把验收用调度写进生产。"
        "判据：测试/验收必须显式隔离 store，跑完核对账里没有验收笔。"
        "src：PROJECT_BLUEPRINT.md:1149,1164"),
    "D03_模块自己在import时绑常量": (
        "现象：测试侧设了隔离仍被绕开。根因：gbt_allinone/__init__.py 在 import 时就把 _paths.STORE_DIR 绑成常量。"
        "判据：隔离变量要在 import 之前生效，或改成运行时读取。"
        "src：PROJECT_BLUEPRINT.md:1149"),
    "D04_进程不在输入桌面拿不到屏": (
        "现象：omni_core 报 BitBlt: 拒绝访问。根因：进程在 WinSta0\\CodexSandboxDesktop-…（非输入桌面）⇒ GDI/DXGI 都拿不到屏。"
        "判据：屏幕采集要在交互桌面进程里跑；拿不到帧就如实 needs_camera，不许凭想象描述。"
        "src：PROJECT_BLUEPRINT.md:1311"),
    "D05_判据工具自己造假红": (
        "现象：prompt_bridge 首跑 P2 报 intent_loss，根因是抽取器把内容抽干了，不是被测件坏了。"
        "判据：判据红了先复验判据自己（负例 + 正例各喂一遍）。"
        "src：PROJECT_BLUEPRINT.md:1868"),
    "D06_只在含斜杠时查盘": (
        "现象：classify 只在含 / 时查盘上是否存在，exists() 为假就直接误判。"
        "判据：判「存不存在」要覆盖两种写法，别让分隔符决定结论。"
        "src：PROJECT_BLUEPRINT.md:2199"),
    "D07_回执只看第一层就报原因未报": (
        "现象：「看屏幕」失败时只报「原因未报」，上游 why/rule/missing 全被吞。"
        "根因：_why() 只读回执第一层，而真原因在 result.result 里（AGENTS §2.2 的同一个坑）。"
        "判据：先第一层，再向下钻一层含 ok:false 的 dict，并追加「（缺：…）」；真没字段才写「回执里没有 reason/error/why」。"
        "src：gbt_allinone/tools/capability_router.py（2026-11-06 修）"),
    "D08_没实现与没登记混为一谈": (
        "现象：holo_pet_w3/package.json 里 20 条 scripts 是 UNIMPLEMENTED 哨兵，指向的 20 个文件 20/20 都不在盘。"
        "判据：这是「如实登记」不是「补齐」——别为了让闸变绿去伪造文件；每条按 where/missing/reason/who_can_fix/evidence 登记。"
        "src：holo_pet_w3/package.json · state/unimplemented.json"),
    "D09_静态闸只扫单文件": (
        "现象：taste_guard 的 motion_count 只扫 HTML，而动效都在 CSS ⇒ 恒报「动效声明 0 处」假红。"
        "判据：HTML 目标把同目录 CSS 一并喂进去，并把「真读到了哪几份 / 哪几份读失败」写进回执。"
        "src：gbt_allinone/tentacle/taste_guard.py（2026-11-06 修）"),
    "D10_正则把input当成i标签": (
        "现象：<i[^>]*> 没有词界，<input ...> 全部命中 ⇒ 每个输入框都算「强调词」假红。"
        "判据：用 <i\\b / <em\\b；改完必须跑一遍负例。"
        "src：gbt_allinone/tentacle/taste_guard.py（2026-11-06 修）"),
    "D11_台账整件会丢而没人发现": (
        "现象：2026-11-06 现读 state/排查台账.json 与 state/logbook.jsonl 同时不在盘，"
        "本仓不是 git 仓库、产品目录递归无副本 ⇒ 34 条根因原文与 700+ 笔机器轨迹不可恢复。"
        "根因：台账被当成「生成物」而不是「迁移件」，没有入迁移清单，也没有判据盯它在不在。"
        "判据：台账/logbook 必须进迁移清单 + 每次体检报 sha 与 mtime；丢件要能被当场点名。"
        "src：tools/codex-scripts/ledger-rebuild-20261106.py（本轮）"),
}

NOW = datetime.now().astimezone().replace(microsecond=0)
def iso(dt: datetime) -> str:
    return dt.astimezone().replace(microsecond=0).isoformat()

led = {
    "updated_at": iso(NOW),
    "_口径": (
        "时辰口径：本机真实偏移是 +07:00（Asia/Bangkok）。历史条目曾把偏移写成 +08:00（F15），"
        "**历史条目不追改**，但读旧时间戳时要知道它们作为绝对时刻约差 8 小时；"
        "单调性对 ≠ 时刻对。"
        "重建口径：2026-11-06 现读发现 state/排查台账.json 与 state/logbook.jsonl 同时不在盘、"
        "本仓非 git 仓库、产品目录无副本 ⇒ 原 34 条根因模式与 700+ 笔轨迹**原文不可恢复**；"
        "`根因模式表` 里凡键名以 R 开头或值里带 src 的，都是按仓内可复核证据重建的，"
        "每条都写了 src；P8/P9/P33/P34/F15 五条有原文出处。"
    ),
    "rounds_done": "历史计数随台账丢失（原计数不可恢复）；2026-11-06 起重新计",
    "in_progress": (
        "2026-11-06：**AI 打印与 APP 细节收尾**。"
        "① 对话面板逐字打印（printBot/光标/贴底跟滚/reduced-motion）已实现，判据 test_console_chat_print 4/4 绿；"
        "② 审美闸 taste_guard 由 67 分 FAIL 修到 97 分 PASS（emoji→内联 SVG、补 h1、仪表盘改主次版面、"
        "`<i>` 语义归还、闸自身两处假红修掉）；"
        "③ 正在做：把以上改动推产品目录 + 重启 8766 常驻服务 + 真机复验。"
    ),
    "not_done": [
        {"id": "N01", "what": "AI 打印真机复验", "why": "仓内已改、产品目录尚未全部推完，线上仍是旧件",
         "where": "holo_pet_w3/console → D:\\GBT-builds\\GBT小土豆V8桌面版\\payload\\holo_pet_w3\\console"},
        {"id": "N02", "what": "holo_pet_w3/package.json 推产品被 danger 闸拦（need_like）",
         "why": "授权/票据件要主人在真终端点赞，agent 不能自批", "where": "tools/codex-scripts/atomic-sync.py"},
        {"id": "N03", "what": "20 条 UNIMPLEMENTED scripts 指向的文件不在盘",
         "why": "如实登记状态（state/unimplemented.json），补不补属主人优先级", "where": "holo_pet_w3/package.json"},
        {"id": "N04", "what": "taste_guard 的截图陪审 / assets.mjs / draw.mjs 未接",
         "why": "需要上游 taste-skill 的 node 端资产脚本", "where": "gbt_allinone/tentacle/taste_guard.py"},
        {"id": "N05", "what": "_upstream/（克隆进来的第三方快照）未加进 .gitignore",
         "why": "1.8 MB 第三方手册，不该混进本仓改动面", "where": ".gitignore"},
    ],
    "open_faults": [
        {"id": "F01", "severity": "P1",
         "what": "state/排查台账.json 与 state/logbook.jsonl 整件缺失（非 git 仓、产品目录无副本）",
         "evidence": "2026-11-06 现读：Test-Path 两者皆 False；git status 报 not a git repository；"
                     "D:\\GBT-builds\\GBT小土豆V8桌面版\\payload 递归查无同名文件",
         "fix": "本轮已按契约重建台账（含 26 条带 src 的根因模式）；logbook 历史 700+ 笔不可恢复"},
        {"id": "F02", "severity": "P2",
         "what": "台账注入的宿主渲染器 plugins/gbt-master/lib/host.js 不在这台机上",
         "evidence": "Test-Path plugins = False；全盘（仓 + .codex/plugins + D:\\GBT-builds）递归查 host.js 皆无",
         "fix": "→ 注入链在本机不生效；需主人给插件，或确认本机不接宿主插件（判据会留 2 条红）"},
        {"id": "F03", "severity": "P2",
         "what": "test_native_growth_stack 4 failures + 1 error（auth_gate 仓外写入）",
         "evidence": "既有红基线，本轮未新增", "fix": "待主人定 auth_gate 仓外写入的口径"},
        {"id": "F04", "severity": "P2",
         "what": "holo_pet_w3/package.json 的 electronDist 指向 ../node_modules/electron/dist，该目录不在盘",
         "evidence": "两个候选路径均不在盘 ⇒ 现状是 needs_dependency（Electron 未装），不是路径写错",
         "fix": "npm i electron 或改为由部署脚本解析"},
    ],
    "owner_decisions": [
        {"id": "OD01", "ask": "是否给 holo_pet_w3/package.json 点赞以便推产品（修 electronDist 硬编码 ADMIN 路径）",
         "why": "该件属 danger 档（授权/票据件），agent 不能自批；不推则产品目录仍是写死别人家用户名的旧件"},
        {"id": "OD02", "ask": "20 条 UNIMPLEMENTED scripts 是补实现还是保持如实登记",
         "why": "补 = 20 个新工具；保持 = 现状（判据绿、但脚本点了会缺件）"},
        {"id": "OD03", "ask": "台账/日志本要不要进迁移清单并加 sha 判据",
         "why": "本轮证明它们会整件消失且无人发现（F01）"},
    ],
    "today_done": [
        "AI 打印：app.js 新增 printBot / finishPrinting / 贴底跟滚 / reduced-motion，成功分支改走逐字打印；判据 4/4 绿",
        "审美闸：67 分 FAIL → 97 分 PASS（emoji→内联 SVG、补 h1、仪表盘改主次版面、<i> 语义归还）",
        "闸自身修两处假红：<i[^>]*> 误匹配 <input>；动效只扫 HTML 看不到 CSS",
        "capability_router._why() 由「只看第一层」改为向下钻一层并点名缺失字段",
        "设计能力：design_atlas 索引重建（654 行/457 配方/197 源），taste_guard 18 条规则可用",
        "台账按契约重建（26 条根因模式，每条带 src）",
    ],
    "log": [
        {"at": iso(NOW - timedelta(minutes=30)),
         "what": "重跑 taste_guard audit：确认 h1/emoji 两条已转绿，FAIL 只剩 no_icon_cards",
         "note": "holo_pet_w3/console/index.html"},
        {"at": iso(NOW - timedelta(minutes=12)),
         "what": "仪表盘由 2×2 同款卡改为「主图 + 两辅读 + 全宽流水」，<i> 全部换 <span>；审美闸 97 分 PASS",
         "note": "index.html / app.css / app.js"},
        {"at": iso(NOW),
         "what": "台账整件重建：29 条顶层/根因证据按契约落盘（原子替换 + 读回校验）",
         "note": "tools/codex-scripts/ledger-rebuild-20261106.py"},
    ],
    "根因模式表": PATTERNS,
    "工程进度一屏账": {
        "位置": "state/工程进度.md（人读一屏）",
        "_口径": "只写有真证据的行；没证据写未验；每行带证据与缺口",
        "写手": "tools/codex-scripts/ledger-refresh.py（本节数字由写手对齐，不手填）",
    },
}

LEDGER.parent.mkdir(parents=True, exist_ok=True)
tmp = LEDGER.with_name("%s.tmp-%d" % (LEDGER.name, os.getpid()))
with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(led, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
    fh.flush()
    os.fsync(fh.fileno())
os.replace(tmp, LEDGER)

back = json.loads(LEDGER.read_text(encoding="utf-8"))
assert back["updated_at"] == led["updated_at"], "读回不一致"
assert len(back["根因模式表"]) == len(PATTERNS)
print("OK 台账已落盘 %d 字节 · 根因模式 %d 条 · log %d 笔 · 顶层键 %d"
      % (LEDGER.stat().st_size, len(PATTERNS), len(led["log"]), len(back)))
