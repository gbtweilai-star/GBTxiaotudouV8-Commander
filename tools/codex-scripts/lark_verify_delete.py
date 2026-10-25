# -*- coding: utf-8 -*-
"""云空间 · 删除验证（fresh read 比对，不信自己的日志）。

判据：删前快照里的每个 token，都不应再出现在**重盘后的**清单里。
  · 出现在新清单 = 没删掉（FAIL）
  · 不出现       = 已删（OK）
这与"日志说成功了"是两回事 —— 日志是自述，重盘是事实。

另外统计：清理后总项数、剩余缓存项（可能有漏网的更深层缓存）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SNAP = ROOT / ".scratch" / "_lark_rollback_snapshot.json"
INV = ROOT / ".scratch" / "_lark_inventory.json"

snap = json.loads(SNAP.read_text(encoding="utf-8"))
inv = json.loads(INV.read_text(encoding="utf-8"))
items = inv["items"]

snap_tokens = {i["token"] for i in snap["items"]}
now_tokens = {i["token"] for i in items}
alive = snap_tokens & now_tokens

PYCACHE = re.compile(r"(^|/)__pycache__($|/)")
WRANGLER = re.compile(r"(^|/)\.wrangler($|/)")

print("=" * 84)
print("云空间 · 删除验证（重盘比对）")
print("=" * 84)
print(f"  删前快照 : {snap['count']} 项（{snap['taken_at']}）")
print(f"  重盘清单 : {len(items)} 项 · 覆盖 {inv['counts']['scanned_dirs']} 个目录"
      f" · {'未穷尽' if inv['partial'] else '已穷尽'}")

print("\n  ① 目标是否真的消失")
print(f"      快照 token {len(snap_tokens)} 个")
print(f"      仍在云端   {len(alive)} 个  {'✓ 全部清除' if not alive else '✗ 有残留'}")
for i in snap["items"]:
    if i["token"] in alive:
        print(f"        残留：{i['path']}  ({i['token']})")

print("\n  ② 残留缓存普查（可能有更深处漏网的）")
left = [i for i in items if PYCACHE.search(i["path"]) or WRANGLER.search(i["path"])]
print(f"      仍含 __pycache__/.wrangler 的项：{len(left)}")
for i in left[:10]:
    print(f"        {i['path']}")
if len(left) > 10:
    print(f"        … 另 {len(left)-10} 项")
if left:
    print("      说明：本次盘点深度≤3，清单只覆盖到 depth3；")
    print("            这些是更深处（或本次盘点未达）的同类缓存，属**已知未清**，不是遗漏执行。")

print("\n  ③ 前后对比")
print(f"      总项数 1592 → {len(items)}  （差 {1592 - len(items)}）")
print(f"{'='*84}")
verdict = "PASS" if not alive else "FAIL"
print(f"  结论：{verdict}")
print(f"{'='*84}")
sys.exit(0 if not alive else 1)
