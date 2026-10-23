# -*- coding: utf-8 -*-
"""云空间盘点 · 问题分析（本地计算，不再调接口）。

输入：.scratch/_lark_inventory.json（lark_inventory.py 的产物）
输出：结构问题清单 + 分类建议。**只分析，不写入任何东西。**
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
INV = ROOT / ".scratch" / "_lark_inventory.json"

d = json.loads(INV.read_text(encoding="utf-8"))
items = d["items"]
folders = [i for i in items if i["type"] == "folder"]

# 目录 → 其下所有项的路径前缀
paths = [i["path"] for i in items]

CACHE = re.compile(r"(^|/)(__pycache__|\.wrangler|node_modules|\.cache|\.venv|venv|"
                   r"dist|build|\.next|\.turbo|\.pytest_cache|\.mypy_cache|"
                   r"\.git|target|out|coverage)(/|$)", re.I)
TEMP = re.compile(r"(^|/)(tmp|temp|test|tests|demo|sample|bak|backup|old|旧|临时|待整理)(/|$)", re.I)
# 代码/工程文件特征
CODE_EXT = re.compile(r"\.(py|js|mjs|cjs|ts|tsx|jsx|json|yaml|yml|toml|lock|map|css|scss|"
                      r"html|sh|ps1|bat|h|c|hpp|cpp|rs|go|java|sql|db|sqlite|log|pyc|whl)$", re.I)
DOC_EXT = re.compile(r"\.(md|txt|docx?|pdf|pptx?|xlsx?|csv)$", re.I)


def under(folder_path):
    pre = folder_path + "/"
    return [i for i in items if i["path"].startswith(pre)]


print("=" * 86)
print("云空间盘点 · 问题分析（只读 · 不写入）")
print("=" * 86)
print(f"  数据源：{INV.name} · 共 {len(items)} 项 · 覆盖 {d['counts']['scanned_dirs']} 个目录")
print(f"  完全覆盖：{'否（见 blocker）' if d['partial'] else '是'}")

# ① 缓存/构建目录
cache_dirs = [f for f in folders if CACHE.search(f["path"])]
cache_items = [i for i in items if CACHE.search(i["path"])]
print("\n① 缓存 / 构建 / 依赖目录（不该进知识库）")
print(f"    目录 {len(cache_dirs)} 个 · 波及 {len(cache_items)} 项")
worst = Counter()
for i in cache_items:
    m = CACHE.search(i["path"])
    worst[m.group(2)] += 1
print(f"    构成：{dict(worst.most_common(10))}")

# ② 空目录
empty = [f for f in folders if not under(f["path"])]
print("\n② 空目录")
print(f"    {len(empty)} 个")
for f in empty[:10]:
    print(f"      {f['path']}")
if len(empty) > 10:
    print(f"      … 另 {len(empty)-10} 个")

# ③ 代码 vs 文档
files = [i for i in items if i["type"] == "file"]
code = [i for i in files if CODE_EXT.search(i["title"])]
doc = [i for i in files if DOC_EXT.search(i["title"])]
other = [i for i in files if i not in code and i not in doc]
print("\n③ 内容性质（这是本次整理最关键的一条）")
print(f"    代码/工程文件 {len(code)} 项（{len(code)*100//max(1, len(files))}%）")
print(f"    文档类        {len(doc)} 项（{len(doc)*100//max(1, len(files))}%）")
print(f"    其它文件      {len(other)} 项")
print(f"    在线文档      {len([i for i in items if i['type'] in ('doc', 'docx', 'sheet', 'bitable', 'slides', 'mindnote')])} 项")

# ④ 命名问题
emoji = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")
longname = [i for i in items if len(i["title"]) > 60]
spacename = [i for i in items if " " in i["title"].strip()]
emojiname = [i for i in items if emoji.search(i["title"])]
print("\n④ 命名")
print(f"    含 emoji      {len(emojiname)} 项  {[i['title'] for i in emojiname[:5]]}")
print(f"    超长（>60字）  {len(longname)} 项")
print(f"    含空格        {len(spacename)} 项")

# ⑤ 深度分布 + 重复名
depth = Counter(i["depth"] for i in items)
print(f"\n⑤ 层级分布：{dict(sorted(depth.items()))}")
byname = defaultdict(list)
for i in items:
    if i["type"] != "folder":
        byname[i["title"]].append(i["path"])
dups = {k: v for k, v in byname.items() if len(v) > 1}
print(f"    同名文件 {len(dups)} 组")
for k, v in list(dups.items())[:6]:
    print(f"      {k[:46]:48} ×{len(v)}")

# ⑥ 一级目录构成
print("\n⑥ 三个一级目录的构成")
for f in [x for x in folders if x["depth"] == 0]:
    sub = under(f["path"])
    tys = Counter(x["type"] for x in sub)
    cd = len([x for x in sub if CODE_EXT.search(x["title"])])
    print(f"    {f['title']:26} {len(sub):>5} 项 · 类型 {dict(tys)} · 代码类 {cd}")

print(f"\n{'='*86}")
print("结论：这是一份代码工作区同步，不是文档库。")
print("      「整理」的正确形态不是按主题归类文档，而是**把不该在云端的东西收口/排除**。")
print(f"{'='*86}")
