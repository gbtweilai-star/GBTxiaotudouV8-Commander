# -*- coding: utf-8 -*-
"""生成《GBT小土豆V8 · 能量总览》Markdown（数据全部来自实时扫描，不手抄）。"""
import sys
import time
from collections import defaultdict
from pathlib import Path

# 原写 `.parent.parent` = `<repo>/tools` —— **差一层**，`import gbt_allinone` 直接 ModuleNotFoundError。
# （2026-09-23 实测：从仓根跑 `py -3.14 tools/codex-scripts/make_energy_report.py` → 报错。）
# 跑脚本时 `sys.path[0]` 是**脚本所在目录**、不是 cwd，所以必须把仓根自己塞进去，不能指望 cwd。
BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）.parent
sys.path.insert(0, str(BASE))

from gbt_allinone import api as API  # noqa: E402
from gbt_allinone import selfscan as SS  # noqa: E402

caps_all = API.list_capabilities(filter_dangerous=False)
caps_ok = API.list_capabilities(filter_dangerous=True)
# 2026-09-23 解禁后：被拒名单为空，`status == "disabled"` 恒为空列表。
# 现在要列的是**只登记未实现**的那 11 条（名字不丢，但它们不是"被挡住的"）。
unimplemented = [c for c in caps_all if c.get("status") == "unimplemented"]

by_domain = defaultdict(list)
for c in caps_ok:
    by_domain[c.get("domain") or "(未标域)"].append(c)

routing = SS.check_routing()
modules = SS.check_modules()
scan = SS.scan(autofix=False)

# 调用点审计（只读，走 run_task 门）
audit = {}
try:
    r = API.run_task("caps_called_audit", {}, safe=True)
    audit = ((r or {}).get("gbt_result") or {}).get("result") or {}
except Exception as exc:  # noqa: BLE001
    audit = {"error": "%s: %s" % (type(exc).__name__, exc)}

wired = {x.get("kind") for x in (audit.get("wired") or [])}
gap = sorted({c.get("name") for c in caps_ok} - wired)

L = []
add = L.append
add("# GBT小土豆V8 · 能量总览（全量扫描）")
add("")
add("> 数据来源：实时扫描 `caps_registry` + `selfscan` + `caps_called_audit`，非手抄。")
add("> 扫描时间：%s ｜ 解释器：Python %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), sys.version.split()[0]))
add("")
add("## 一、总量")
add("")
add("| 指标 | 数值 |")
add("|---|---|")
add("| 注册能力（含禁用） | **%d** |" % len(caps_all))
add("| 可执行能力 | **%d** |" % len(caps_ok))
add("| 登记未实现（禁止已解开） | **%d** |" % len(unimplemented))
add("| 覆盖领域 | **%d** |" % len(by_domain))
add("| 注册↔路由对齐 | **%s / %s**（未路由 %d，幽灵路由 %d） |"
    % (routing.get("routed"), routing.get("registered"), len(routing.get("unrouted") or []),
       len(routing.get("ghost_routes") or [])))
add("| 模块导入体检 | **%s / %s** 通过 |" % (modules.get("checked", 0) - len(modules.get("failed") or []),
                                     modules.get("checked", 0)))
add("| 调用点接线 | **wired %s / total %s**，孤儿 **%s** |"
    % (audit.get("wired_count", "?"), audit.get("total", "?"), audit.get("orphan_count", "?")))
add("| 五维体检总判定 | **%s** |" % scan.get("verdict"))
add("")
add("## 二、按领域分布")
add("")
add("| 领域 | 能力数 | 领域 | 能力数 |")
add("|---|---|---|---|")
ordered = sorted(by_domain.items(), key=lambda kv: (-len(kv[1]), kv[0]))
half = (len(ordered) + 1) // 2
for i in range(half):
    a = ordered[i]
    b = ordered[i + half] if i + half < len(ordered) else ("", "")
    add("| %s | %s | %s | %s |" % (a[0], len(a[1]), b[0], len(b[1]) if b[0] else ""))
add("")
add("## 三、可执行能力全清单（%d 项）" % len(caps_ok))
for dom, items in sorted(by_domain.items(), key=lambda kv: (-len(kv[1]), kv[0])):
    add("")
    add("### %s（%d）" % (dom, len(items)))
    add("")
    for c in sorted(items, key=lambda x: x.get("name", "")):
        desc = (c.get("desc") or "").replace("\n", " ").strip()
        add("- **%s** — %s" % (c.get("name"), desc))
add("")
add("## 四、只登记未实现的名字（%d 项 —— 不是「被禁用」，是没有实现）" % len(unimplemented))
add("")
add("> 2026-09-23 Owner 令把禁止全部解开：被拒名单已清空。这些名字**留在登记里只为名字不丢**，")
add("> 点下去得到的是如实的 `unknown capability`。**别把它读成「门关着、开锁就能用」** —— 门后面没有东西。")
add("")
for c in sorted(unimplemented, key=lambda x: x.get("name", "")):
    add("- `%s` — %s" % (c.get("name"), (c.get("desc") or "").replace("\n", " ")))
add("")
add("## 五、接线缺口（注册了但是我没有查到的调用点）")
add("")
if gap:
    for name in gap:
        add("- `%s`" % name)
else:
    add("- 无")
add("")
add("## 六、体检告警")
add("")
for f in (scan.get("findings") or []):
    add("- %s" % f)
if not scan.get("findings"):
    add("- 无")
add("")
add("---")
add("")
add("> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属")

OUT = BASE / "outputs" / "GBT小土豆V8-能量总览.md"
OUT.write_text("\n".join(L), encoding="utf-8")
print(OUT)
print("gap(%d): %s" % (len(gap), gap))
