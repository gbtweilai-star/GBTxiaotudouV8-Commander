# -*- coding: utf-8 -*-
"""云空间 · 可删候选清单生成器（**只生成清单，绝不删除**）。

为什么单独立这个：`knowledge_organize` 工作流的 Non-goals 明文禁止删除，
所以清理缓存垃圾**不在那个工作流范围内**，必须按 R3（destructive）单独走。

R3 要求我给出：恢复边界 · 执行日志 · 分批策略 · 失败停止条件 · 单独确认。
本脚本产出前两项所需的事实（准确清单 + 每项理由 + token）+ 分批方案。

**判据从严**：只列「可被工具重新生成、且不含人写内容」的东西，绝不列"看着没用"的。
  ① `__pycache__` 目录及其 .pyc —— Python 字节码缓存，导入时自动重建
  ② `.wrangler` / `.wrangler/cache` —— Cloudflare Wrangler 构建缓存
  ③ 空目录 —— 无内容可失，但**是否要删由你定（有些是占位）**

产物：.scratch/_lark_deletable.json（含 token，供确认后执行）
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
INV = ROOT / ".scratch" / "_lark_inventory.json"
OUT = ROOT / ".scratch" / "_lark_deletable.json"

d = json.loads(INV.read_text(encoding="utf-8"))
items = d["items"]
folders = [i for i in items if i["type"] == "folder"]
files = [i for i in items if i["type"] == "file"]

PYCACHE = re.compile(r"(^|/)__pycache__($|/)")
WRANGLER = re.compile(r"(^|/)\.wrangler($|/)")


def under(p):
    pre = p + "/"
    return [i for i in items if i["path"].startswith(pre)]


def bucket(name, why, cands, kind):
    return {"bucket": name, "why": why, "kind": kind,
            "count": len(cands),
            "items": [{"path": i["path"], "type": i["type"],
                       "token": i["token"], "title": i["title"]} for i in cands]}


# ① __pycache__ —— 只取**目录**（删目录即连带内容）
py_dirs = [f for f in folders if PYCACHE.search(f["path"])]
py_inside = [i for i in items if PYCACHE.search(i["path"]) and i["type"] != "folder"]

# ② .wrangler
wr_dirs = [f for f in folders if WRANGLER.search(f["path"])]
wr_inside = [i for i in items if WRANGLER.search(i["path"]) and i["type"] != "folder"]

# ③ 空目录
empty = [f for f in folders if not under(f["path"])]

# ④ 冗余：__pycache__ 里除了 .pyc 之外还有别的吗（若有，说明判据要收窄）
odd = [i for i in py_inside if not i["title"].lower().endswith((".pyc", ".pyo"))]

buckets = [
    bucket("A · Python 字节码缓存目录", "__pycache__：Python 导入时自动重建，不含任何手写内容",
           py_dirs, "drive_folder"),
    bucket("B · Wrangler 构建缓存", ".wrangler / .wrangler/cache：构建缓存，可重新生成",
           wr_dirs, "drive_folder"),
    bucket("C · 空目录", "无任何内容，删除不丢数据；但可能是占位，需你判断",
           empty, "drive_folder"),
]

report = {
    "generated_from": INV.name,
    "scope": d["scope"], "identity": d["identity"],
    "inventory_partial": d["partial"],
    "counts": {
        "all_items": len(items),
        "A_pycache_dirs": len(py_dirs),
        "A_inside_items": len(py_inside),
        "A_odd_non_pyc": len(odd),
        "B_wrangler_dirs": len(wr_dirs),
        "B_inside_items": len(wr_inside),
        "C_empty_dirs": len(empty),
    },
    "caveats": [],
    "buckets": buckets,
}

# 诚实标注边界
if d["partial"]:
    report["caveats"].append(
        "盘点未穷尽（深度≤3 分批检查点）：更深层可能还有同类缓存未被列出，"
        "故本清单是**已知范围内的可删项**，不是全量。")
if odd:
    report["caveats"].append(
        f"__pycache__ 内有 {len(odd)} 个非 .pyc/.pyo 文件，已单独列出待你判断，"
        "未直接归入 A 桶。")
report["caveats"].append(
    "本清单**只列可被工具重建的缓存与空目录**，不含任何文档、代码源文件、素材。")
report["caveats"].append(
    "删除**不可从飞书回收站以外恢复**；执行前我会先取一次完整 token 快照留档。")

OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

print("=" * 86)
print("云空间 · 可删候选清单（只生成，未删除任何东西）")
print("=" * 86)
print(f"  数据源 {INV.name} · 盘点覆盖：{'未穷尽' if d['partial'] else '已穷尽'}")
print(f"  总资源 {len(items)} 项\n")
for b in buckets:
    print(f"  {b['bucket']}")
    print(f"      数量 {b['count']} 个 · 理由：{b['why']}")
    for it in b["items"][:6]:
        print(f"        {it['path']}")
    if b["count"] > 6:
        print(f"        … 另 {b['count']-6} 个")
    print()
if odd:
    print(f"  ⚠ __pycache__ 内非 .pyc 文件 {len(odd)} 个（未归入 A 桶）：")
    for i in odd[:8]:
        print(f"      {i['path']}")

print(f"{'='*86}")
print("诚实标注：")
for c in report["caveats"]:
    print(f"  · {c}")
print(f"\n  清单 -> {OUT.relative_to(ROOT)}  ({OUT.stat().st_size:,} B)")
print(f"{'='*86}")
print("**下一步：等你逐桶确认。确认前我不会删任何一个。**")
