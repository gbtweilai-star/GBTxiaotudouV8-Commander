#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把今天 **11 次自纠**完整写进 P33（原来是 4 条，与事实不符）—— 原子替换台账字段。"""
import json
import os
import sys
import tempfile
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
L = os.path.join(ROOT, "state", "排查台账.json")
j = json.load(open(L, encoding="utf-8"))
pat = j["根因模式表"]

pat["P33_量具自身的系统错（11 次实证）"] = (
    "2026-10-22 单轮内**自纠 11 次**，全部是**量具/读数**错，不是盘错。按族分：\n"
    "  ① **键名当事实**（3 次）：logbook 时间字段是 `ts` 不是 `at` ⇒ 833 条一条没解析上，归因「0 件」；"
    "护照认领文件在 `changed`(dict) 不是 `files` ⇒「47/47 件在盘」是**空检查**（0 件）；"
    "注册表 `handler` 是**裸名**不是模块路径 ⇒ 341 位里 278 位被判「无 handler」。\n"
    "  ② **弱键当证据**（2 次）：按 mtime ±2h 找最近 logbook 当理由，把 `.wrangler` 临时件归到「数字人脚本挂掉」；"
    "按 basename 匹配，一条记录一次「认领」了 24 个不同目录的 `index.html`。\n"
    "  ③ **口径/单位不同却当结论**（4 次）：根=每个技能目录 vs 根=容器（8131 vs 850）；"
    "容器定义不同（1335 vs 704）；名字 vs 目录（92 vs 181）；frontmatter 名 vs 目录名（5 个「该补」里 4 个其实在册）。\n"
    "  ④ **实现写错**（2 次）：`hits.append` 写在过滤**循环外** ⇒ `resolve/frozenset/splitlines/loads` 全被当写盘原语（492 vs 97）；"
    "`_DIMS_NOT_IMPL` 定义在函数内却 `getattr(module,…)` 取 ⇒「没读到」被判「已不成立」。\n"
    "根治三条（写死）：**(a) 每个量具出数前先做负例自检**（喂一个已知不该命中的对象，看它会不会被命中）；"
    "**(b) 读不到/字段缺一律记「未读到」，不许推出结论**；**(c) 输出必须自带单位与粒度**，"
    "两把尺子数不同先统一口径再报数（后者见 P34）。"
)
j.setdefault("log", []).append({
    "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "what": "P33 按事实订正：4 条 → 11 条（分四族：键名当事实/弱键当证据/口径与单位/实现写错）",
    "text": "旧 P33 写「4 次」，实际单轮 11 次；已逐条列出并给三条根治",
    "note": "tools/codex-scripts/ledger-p33-full.py（原子替换）",
})
fd, tmp = tempfile.mkstemp(prefix="ledger-", suffix=".json", dir=os.path.dirname(L))
with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(j, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
os.replace(tmp, L)
print("P33 已订正为 11 条实证（分四族）· 根因模式表 %d 条" % len(pat))
