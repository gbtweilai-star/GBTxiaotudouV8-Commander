# -*- coding: utf-8 -*-
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""启动与安装入口·只读清单（DD-03 交付物）。

Owner 2026-09-19（DD-03 结案口径）：**缺的是呈现，不是能力。**
盘上已经有启动/引导入口，但面板里看不见它们 —— 所以这里只做**呈现**：

  · 逐条**现场校验**（`Test-Path` 级），不存在的如实标"缺失"，不假装在；
  · **只读**：本工具不执行任何 `.bat`；给面板加"点一下就跑"是**权限边界变更**，
    要和 `auth_gate` 口径对齐后由主人拍板（DD-03 报告第四节第 2 条）；
  · 桌面快捷方式同样**只列出是否存在**，不解析目标（解析目标是另一枪）。

用法：
    python -m gbt_allinone.tools.launcher_inventory          # 人读
    python -m gbt_allinone.tools.launcher_inventory --json   # 机读
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# (相对路径, 用途) —— 全部是 DD-03 里核实过**真实存在**的入口
ENTRIES = [
    ("holo_pet/open-full-panel.bat",        "浏览器全尺寸完整面板"),
    ("holo_pet/restart-digital-human.bat",  "重启数字人（先关旧面板）"),
    ("holo_pet/start-holo-panel.bat",       "起面板"),
    ("holo_pet/启动3D数字人.bat",             "W3 3D 版入口"),
    ("holo_pet/启动桌面数字人.bat",            "桌宠壳入口"),
    ("holo_pet/部署-今天就能用.md",           "部署单（人读）"),
]

DESKTOP_SHORTCUTS = ("小土豆完整面板.lnk", "启动桌面数字人.lnk", "GBT小土豆.lnk", "Codex.lnk")


def inventory(root: Path | None = None) -> dict:
    base = Path(root or ROOT)
    rows = []
    for rel, use in ENTRIES:
        p = base / rel
        rows.append({"entry": rel, "use": use, "exists": p.is_file(),
                     "bytes": p.stat().st_size if p.is_file() else 0})
    desk = Path.home() / "Desktop"
    shortcuts = [{"name": n, "exists": (desk / n).is_file()} for n in DESKTOP_SHORTCUTS]
    return {"ok": True, "read_only": True,
            "note": "只呈现不执行；给面板加执行能力属权限边界变更，需主人拍板",
            "launchers": rows, "launchers_present": sum(1 for r in rows if r["exists"]),
            "launchers_total": len(rows),
            "desktop": {"dir": str(desk), "shortcuts": shortcuts,
                        "shortcuts_present": sum(1 for s in shortcuts if s["exists"])}}


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    data = inventory()
    if "--json" in argv:
        print(json.dumps(data, ensure_ascii=False, indent=1))
        return 0
    print("启动与安装入口（只读清单 · 逐条现场校验）")
    for r in data["launchers"]:
        print("  %s %-38s %8s B  %s"
              % ("✔" if r["exists"] else "✘", r["entry"], r["bytes"], r["use"]))
    print("  小计 %s/%s 在" % (data["launchers_present"], data["launchers_total"]))
    print("  桌面快捷方式 %s/%s 在（%s）"
          % (data["desktop"]["shortcuts_present"],
             len(data["desktop"]["shortcuts"]), data["desktop"]["dir"]))
    print("  ⚠️ 只呈现不执行；执行能力属权限边界，需主人拍板")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
