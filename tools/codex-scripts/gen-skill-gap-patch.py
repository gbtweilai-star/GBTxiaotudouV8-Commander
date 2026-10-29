#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""**生成「域规程待补清单」** —— 只出补丁内容，**绝不改技能件**。

为什么要有它（一手账）：
  `verify-distill.py --all` 现读 5 个域判红（data 缺 1 · llm 缺 2 · security 缺 11 ·
  video 缺 6 · unimplemented 是幽灵域）。判据说"规程没点到这些能力位"，但**没给内容** ——
  于是"要不要补"这件事一直卡在"得先知道补什么"。
  本器把那份内容**机器生成**出来：每个域缺哪几位、每位是什么、过哪道门、贴到哪一段。

🔴 它**只读**（不写任何 `SKILL.md`）。理由有三条，都不是"我懒"：
  1. 技能件有**两个根**（工作区源稿 + managed 安装件），`verify-distill` 要求**逐字节一致**
     ⇒ 只改一个根就是把"绿"变成"红"；
  2. managed 那个根属**托管技能目录**，改它得有主人明确的授权；
  3. 补规程涉及"这份规程还要不要"（`gbt-dangerous` ↔ 幽灵域 `unimplemented`）——
     那是**口径决定**，不是排版活。

用法：
  python tools/codex-scripts/gen-skill-gap-patch.py            # 人读：逐域给出可粘贴的补丁段
  python tools/codex-scripts/gen-skill-gap-patch.py --json     # 机读
  python tools/codex-scripts/gen-skill-gap-patch.py --domain security   # 只看一个域
退出码：0 = 没有待补；1 = 有待补（清单已打印）；2 = 跑不起来。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gbt_allinone.caps_registry import BENIGN_CAPS          # noqa: E402
from gbt_allinone.security import policy as POLICY          # noqa: E402

MANAGED = Path.home() / ".openclaw-autoclaw" / "skills"
OMNI = ROOT / "tools" / "codex-scripts" / "omni.py"


def _omni():
    spec = importlib.util.spec_from_file_location("omni_mod", OMNI)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _scope_of(kind: str) -> str:
    """这位要过哪道门（空参）＋说明它还会在哪些动作/字段上收口。"""
    try:
        d = POLICY.evaluate(kind, {})
        sc = list(d.scopes or ())
    except Exception:                                            # noqa: BLE001
        sc = []
    if sc:
        return "、".join("`%s`" % s for s in sc)
    return "**空参零作用域**（但注意：写动作/字段可能另行收口，见 policy.py）"


def _doc_mentions(text: str, kind: str) -> bool:
    import re
    return re.search(r"(?<![\w])" + re.escape(kind) + r"(?![\w])", text) is not None


def collect(only: str = "") -> dict:
    omni = _omni()
    dom2skill = dict(getattr(omni, "DISTILLED_DOMAINS", {}) or {})
    rows = []
    for domain, skill in sorted(dom2skill.items()):
        if only and domain != only:
            continue
        kinds = sorted(k for k, v in BENIGN_CAPS.items()
                       if (v or {}).get("domain") == domain)
        src = ROOT / "skills" / str(skill) / "SKILL.md"
        dst = MANAGED / str(skill) / "SKILL.md"
        row = {"domain": domain, "skill": skill, "kinds_in_registry": len(kinds),
               "src": str(src), "dst": str(dst),
               "src_exists": src.is_file(), "dst_exists": dst.is_file(),
               "two_roots_identical": None, "missing": [], "note": ""}
        if src.is_file() and dst.is_file():
            row["two_roots_identical"] = src.read_bytes() == dst.read_bytes()
        if not kinds:
            row["note"] = ("**该域在注册表里一位都没有** —— 幽灵域。"
                           "要么删 `omni.DISTILLED_DOMAINS` 这条键，"
                           "要么决定这份规程的去留（属口径决定，等主人拍板）。")
            rows.append(row)
            continue
        text = src.read_text(encoding="utf-8", errors="replace") if src.is_file() else ""
        row["missing"] = [k for k in kinds if not _doc_mentions(text, k)]
        if not src.is_file():
            row["note"] = "工作区源稿不存在 ⇒ 先确认这份规程在哪"
        rows.append(row)
    return {"rows": rows, "gap_domains": [r["domain"] for r in rows if r["missing"] or r["note"]]}


def render(rep: dict) -> str:
    out = []
    out.append("═══ 域规程待补清单（**只出内容，不动技能件**）═══")
    out.append("判据来源：`verify-distill.py` —— 「域规程必须点到该域每一个能力位」。")
    out.append("改法铁律：**两个根一起改**（工作区源稿 + managed 安装件必须逐字节一致），"
               "改完跑 `verify-distill.py --all` 复核。")
    out.append("")
    for r in rep["rows"]:
        if not (r["missing"] or r["note"]):
            continue
        out.append("─" * 78)
        out.append("【域 %s → 规程 %s】注册表 %d 位 · 缺 %d 位"
                   % (r["domain"], r["skill"], r["kinds_in_registry"], len(r["missing"])))
        out.append("  工作区源稿：%s（%s）" % (r["src"], "在" if r["src_exists"] else "**不在**"))
        out.append("  managed ：%s（%s）" % (r["dst"], "在" if r["dst_exists"] else "**不在**"))
        if r["two_roots_identical"] is not None:
            out.append("  两个根逐字节一致：%s" % ("是" if r["two_roots_identical"] else "**否 ⇒ 先同步再改**"))
        if r["note"]:
            out.append("  ⚠ %s" % r["note"])
        if r["missing"]:
            out.append("  待补的能力位（把下面这段贴进该域规程的「能力位清单」一节）：")
            out.append("")
            for k in r["missing"]:
                meta = BENIGN_CAPS.get(k) or {}
                desc = str(meta.get("desc") or "").strip()
                out.append("    - `%s`：%s" % (k, desc[:120] or "（注册表没写 desc）"))
                out.append("      - 门：%s" % _scope_of(k))
                out.append("      - 调法：`python tools/codex-scripts/five-dim.py cap %s '{}'`" % k)
            out.append("")
    out.append("─" * 78)
    out.append("待补域：%s" % ("、".join(rep["gap_domains"]) or "（无）"))
    out.append("🔴 本器**没有**改任何文件：技能件有两个根、managed 属托管目录、"
               "且 `gbt-dangerous` ↔ 幽灵域的归属是口径决定 ⇒ 都要主人点头。")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="域规程待补清单（只读）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--domain", default="")
    a = ap.parse_args(argv)
    try:
        rep = collect(only=a.domain)
    except Exception as e:                                       # noqa: BLE001
        print("跑不起来：%s: %s" % (type(e).__name__, e), file=sys.stderr)
        return 2
    rep["gap_count"] = len(rep["gap_domains"])
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(render(rep))
    return 1 if rep["gap_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
