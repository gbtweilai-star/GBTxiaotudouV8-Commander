"""授权面形状（只读）—— 主人 2026-09-25 令「把限制去掉、改为人工授权」的**现读**。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 这条令要防的是什么（不是"门多"，而是"有一道授权不了的门"）
主人要的是「**不硬禁，全部走人工授权**」。那么真正的病不是"门有多少道"，
而是：**某个作用域被强制、却不在可授权清单里** ⇒ 主人也发不出那条授权
⇒ 对调用者是**永久不可授权** = **变相禁止**（本仓 2026-09-15 / 09-18 / 09-19 各栽过一次，
每次都记在 `gbt_allinone/auth_gate.py` 的注释里）。

## 它量什么（两侧集合对差）
- ① **门会要的**：`security/policy.py::SCOPE_DESCRIPTIONS`
- ② **主人能发的**：`auth_gate.py::SCOPES`
- **死锁 = ① − ②**（非空 ⇒ 红）。反向差（② − ①，如 `osint_private`，由能力自己那侧强制）
  **不算病，但要点名** —— 不许静默。
- 附：`owner_control` = **一条顶掉该次动作所需的全部未授权作用域**（一次性消耗），
  有框架契约测试 `test_owner_control_substitutes_missing_scopes`；本工具**只报它的存在**，不代它作证。

用法：
  python tools/codex-scripts/auth-shape.py check [--json]
  python tools/codex-scripts/auth-shape.py selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def compare(asked, grantable) -> dict:
    """**纯函数**（好上负控）：两侧集合对差。空表一律**拒绝**，不许念成"没有变相禁止"。"""
    asked, grantable = set(asked or ()), set(grantable or ())
    if not asked:
        return {"ok": False, "拒绝": "**门侧是空的** ⇒ 读不出任何东西（空表不许当合格）"}
    if not grantable:
        return {"ok": False, "拒绝": "**可授权清单是空的** ⇒ 每一道门都发不出授权（= 全部门变相禁止）"}
    dead = sorted(asked - grantable)
    return {"ok": not dead, "门会要的": len(asked), "主人能发的": len(grantable),
            "**授权不了的作用域（= 变相禁止）**": dead,
            "只在授权侧、门里没用到的": sorted(grantable - asked),
            "判决": ("✅ 每一道门都授权得了（没有变相禁止）" if not dead else
                   "🔴 有 %d 个作用域**主人也发不了授权** ⇒ 那是变相禁止" % len(dead))}


def live() -> dict:
    from gbt_allinone.security import policy as P
    from gbt_allinone import auth_gate as G
    r = compare(set(P.SCOPE_DESCRIPTIONS), set(getattr(G, "SCOPES", {}) or {}))
    r["口径"] = ("只比两侧集合、不改任何授权 —— **AI 永远不发授权**；"
               "`owner_control` 一条顶掉该次动作所需的全部未授权作用域（一次性消耗），"
               "它的语义由框架契约测试作证，不是本工具")
    return r


def selftest() -> int:
    checks, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad = bad + (0 if cond else 1)
        checks.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    r = live()
    ck("**正控（现读真两侧）：没有变相禁止**", r.get("ok") is True, r.get("判决", str(r.get("拒绝"))))
    dead = compare({"a", "b"}, {"a"})
    ck("**负控：门里有、主人发不了 ⇒ 必须点名那是变相禁止**",
       dead.get("ok") is False and dead.get("**授权不了的作用域（= 变相禁止）**") == ["b"],
       "点名=%s" % dead.get("**授权不了的作用域（= 变相禁止）**"))
    extra = compare({"a"}, {"a", "osint_private"})
    ck("**边界：只在授权侧有的 ⇒ 不算病，但必须点名**",
       extra.get("ok") is True and extra.get("只在授权侧、门里没用到的") == ["osint_private"],
       "点名=%s" % extra.get("只在授权侧、门里没用到的"))
    ck("**边界：门侧空 ⇒ 拒绝**（不许念成合格）",
       compare(set(), {"a"}).get("ok") is False, str(compare(set(), {"a"}).get("拒绝"))[:44])
    ck("**边界：可授权清单空 ⇒ 拒绝**（那等于全部门变相禁止）",
       compare({"a"}, set()).get("ok") is False, str(compare({"a"}, set()).get("拒绝"))[:44])

    print(json.dumps({"自检": {"条数": len(checks), "通过": len(checks) - bad, "不通过": bad},
                      "逐条": checks}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "selftest"])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.cmd == "selftest":
        return selftest()
    r = live()
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
