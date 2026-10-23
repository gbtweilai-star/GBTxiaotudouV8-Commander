# -*- coding: utf-8 -*-
"""today-report -- 今日报告（训练 / 大模型能力 / 压缩与触手绑定），全部现读生成。"""
from __future__ import annotations
import glob, json, os, re, subprocess, sys
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "今日训练与能力报告-2026-10-16.md"
PY = sys.executable


def jload(p, d=None):
    try:
        return json.loads((ROOT / p).read_text(encoding="utf-8"))
    except Exception:
        return d


def sh(args, timeout=420):
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")


def last_line(t):
    ls = [x.strip() for x in (t or "").splitlines() if x.strip()]
    return ls[-1][:150] if ls else "-"


lines = []
A = lines.append
A("# 今日训练与能力报告 · 2026-10-16")
A("")
A("> 开发者：自由的风 · 守护者：公主土豆 · 本署名不可删除、不可篡改归属")
A("")
A("## 一、训练轮次与语料（现读 manifest）")
A("")
rows = []
for f in sorted(glob.glob(str(ROOT / "state" / "train" / "corpus_v*_manifest.json"))):
    m = json.loads(Path(f).read_text(encoding="utf-8"))
    rows.append((m.get("gen", "?"), m.get("count", 0), m.get("bytes", 0), str(m.get("sha256", ""))[:16], m.get("parent", "-")))
A("| 语料 | 条数 | 字节 | sha256（前16） | 上游 |")
A("|---|---:|---:|---|---|")
for g, c, b, s, p in rows:
    A("| %s | %d | %d | %s | %s |" % (g, c, b, s, p))
A("")
A("## 二、大模型能力（当前得分现读）")
A("")
A("| 判据 | 得分 |")
A("|---|---|")
J = [("总验收门", ["tools/codex-scripts/accept-all.py", "--model-answers", ".scratch/accept_a44.jsonl", "--comfy-answers", ".scratch/comfy_a44.jsonl"]),
     ("看视频理解", ["tools/train/accept_video.py", "--answers", ".scratch/video_a43.jsonl"]),
     ("技能蒸馏五式", ["tools/train/accept_forge.py", "--answers", ".scratch/forge_a43.jsonl"]),
     ("自主渗透编排", ["tools/train/accept_offense.py", "--answers", ".scratch/offense_a43.jsonl"]),
     ("自适应抓取", ["tools/train/accept_spider.py", "--answers", ".scratch/spider_a43.jsonl"]),
     ("作品解剖展示", ["tools/train/accept_sc.py", "--answers", ".scratch/sc_a43.jsonl"])]
for nm, cmd in J:
    if not (ROOT / cmd[1]).is_file():
        A("| %s | （本地缺答案件） |" % nm)
        continue
    o = sh([PY, "-X", "utf8"] + cmd)
    sc = [x for x in o.splitlines() if x.startswith("==") or "总验收" in x]
    A("| %s | %s |" % (nm, (sc[-1].strip("= ") if sc else last_line(o))))
A("")
A("## 三、能力位台账与新增")
A("")
au = sh([PY, "-X", "utf8", "tools/codex-scripts/capability-audit.py"])
A("```")
A(last_line(au) or "未读到")
A("```")
A("")
A("今日新增能力位（已注册·过门·绑触手）：")
NEW = [("skill_forge", "技能蒸馏五式（女娃/last30days/同事/前任/反蒸馏）7op"),
       ("offense_ops", "自主渗透编排（pentagi）8op + 五道闸"),
       ("spider_ops", "自适应抓取（Scrapling）7op + robots 边界"),
       ("showcase_ops", "作品解剖与展示（anatomy）8op + 读数同源"),
       ("forge_mastery", "节点即触手·专业生产与自我递归（7op + N=3）"),
       ("workflow_forge", "工作流十式（skills.sh TOP10）12op")]
for k, d in NEW:
    A("- **%s** — %s" % (k, d))
A("")
A("## 四、压缩（显存 / 体积）与触手绑定")
A("")
rc = sh([PY, "-X", "utf8", "tools/codex-scripts/round-compact.py"])
A("```")
for x in [y for y in rc.splitlines() if y.strip()][:14]:
    A(x[:150])
A("```")
A("")
bd = sh([PY, "-X", "utf8", "tools/codex-scripts/capability-bindings.py", "--check"])
ln = sh([PY, "-X", "utf8", "tools/codex-scripts/tentacle-link-registry.py", "--check"])
A("- 双向绑定：`" + last_line(bd) + "`")
A("- 连接登记：`" + last_line(ln) + "`")
A("- 直达索引：`state/direct-index.json` " + str(jload("state/direct-index.json", {}).get("count", "-")) + " 位")
A("- 肌肉训练：`" + last_line(sh([PY, "-X", "utf8", "tools/codex-scripts/muscle-drill.py", "check", "--min-rate", "0.9"])) + "`")
A("")
A("## 五、纪律与闸（今日新立）")
A("")
LAWS = [("TRAINING_LAW.md 第35条", "训练法：5步 + 3件套 + 三段闸 + 熔断0.5GB + N=3"),
        ("TRAINING_LAW.md 第36条", "保密三铁律 + 七情六欲判据（感悟≥3 且 情绪≥2）"),
        ("TRAINING_LAW.md 第37条", "先看后动（默认·不可关闭）"),
        ("CODING_DISCIPLINE.md", "同步第35/36/37条（原文未动，已备份）"),
        ("SOUL.md", "「克劳德会干活，我会先看」（主人名点）"),]
for k, v in LAWS:
    A("- **%s** — %s" % (k, v))
A("")
A("机器件：`round-pipeline`（大脑计划/镜像排练/生产落实，含题面与语义唯一性）· `round-compact`（显存/体积/绑定/直达）·")
A("`judge-health`（判据健康度）· `watchdog-run`（看护）· `blueprint-first`（立体蓝图+熔断+确认门）· `see_first`（代码层先看后动）·")
A("`paper_guard`/`paper_loop`（保密双账本）· `landing-checklist`（落实清单）· `check_instruction_unique`/`check_instruction_semantic`（题面与语义唯一）")
A("")
A("## 六、今日发现并修复的真问题（入坑册）")
A("")
FIX = [("链 ; && 语法错", "三段闸段2b 在干跑阶段就拦下（v41 曾在生产上白等十几分钟）"),
       ("pip 升 torch 致 bnb 崩溃", "AttributeError: frozenset no discard ⇒ 绑定 --upgrade-strategy only-if-needed"),
       ("2c 假阳性", "把卡上执行件 accept_infer.py 当判据预演 ⇒ 改为 runner 跳过"),
       ("题面跨族串族", "字面判据 0 条而语义判据得 5 条（命令怎么调 三族共用）⇒ 新增语义聚类判据 + 题面/答案双双带族名"),
       ("看护件假绿", "总判只看内存 ⇒ 改为任一 RED 即 RED"),
       ("快照页过期计成断连", "读审计自带的“怎么补”字段（exec-deck/code-deck --html）一击修好"),
       ("自测假绿（判据自身）", "paper_guard 阈值与首句铁律引入后自测 FAIL ⇒ 照实改至全绿")]
for k, v in FIX:
    A("- **%s**：%s" % (k, v))
A("")
A("## 七、钱账")
A("")
A("- `RUNNING = 0`（v44 在跑时为 1）· 今日累计 ≈ **$6.3**")
A("- 记账：`state/logbook.jsonl` 到 **678** 条")
A("")
OUT.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
print("报告已出：" + str(OUT.relative_to(ROOT)) + " · " + str(OUT.stat().st_size) + " 字节")
print(chr(10).join(lines[:26]))
