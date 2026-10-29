#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""dsh-plugin-audit · 「插件名单核对」：**别人给我的插件名，先核一遍再信**

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要有这一件（2026-09-25 实测事故）

主人转来一套「10 个插件」方案，名字长得很像真的：

    dsh-llm-qwen-local ／ dsh-force-compact ／ dsh-llm-qwen-abliterated ／ dsh-tool-web
    dsh-tool-file ／ dsh-tool-shell ／ dsh-memory-vector ／ dsh-memory-local
    dsh-policy-guard ／ dsh-observability

**拿装机真身一核：10 个里只有 1 个真的存在**（`dsh-tool-web`），
其余 9 个**全盘零命中**（`node_modules`、`$DSH_HOME`、工作区三处都找过）。
⇒ **这份名单不能照着装**：装不上的包名会让人以为"环境坏了"，
   而真相是"这个名字不存在"。**名字像真的 ≠ 真的存在。**

本件把这件事变成一条命令，并且**给每个名字落一个结论**（在 / 不在 / 真名叫什么）。

## 口径（不许省）
- 「在」= 出现在装机的 `node_modules/@deepseek-ai/` **包目录**里，
  或作为 **row name** 出现在组合文件（`cordis.patch.yml` / preset 的 `agent.cordis.yml`）里；
- 「不在」= 上面两处都没有 ⇒ **不许说"装了但没用"**，就是**不存在**；
- 对照表里的「真实对应件」是**对应关系**（做同一件事的**另一个包**），**不是同一个包** —— 不许混写。

用法：
  dsh-plugin-audit.py audit      # 核默认那份 10 个名字
  dsh-plugin-audit.py list       # 列出装机里真实存在的包与 row
  dsh-plugin-audit.py check --names a,b,c
  dsh-plugin-audit.py selftest
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 装机真身的位置（**现读，不猜**）：npm 缓存里的 npx 安装 + DSH_HOME
NPX = Path(r"C:\Users\ADMIN\AppData\Local\npm-cache\_npx\1e7f6d9597241db0")
DSH_HOME = Path(r"C:\Users\ADMIN\.dsh")
PKG_SCOPE = "@deepseek-ai"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# **被核对的那份名单原样留档**（出处写清）—— 事后要能对账"当时核的是哪 10 个"
CLAIMED = {
    "出处": "主人 2026-09-25 转来的「10 个插件」方案（未标明作者；名字看着都很像真的）",
    "名单": ["dsh-llm-qwen-local", "dsh-force-compact", "dsh-llm-qwen-abliterated",
           "dsh-tool-web", "dsh-tool-file", "dsh-tool-shell", "dsh-memory-vector",
           "dsh-memory-local", "dsh-policy-guard", "dsh-observability"],
    # 「做同一件事」的真实件（**对应关系，不是同一个包**）
    "真实对应件": {
        "dsh-llm-qwen-local": {"真实件": "dsh-llm-pi-ai（provider 适配行）+ dsh-agent-default-model",
                               "为什么": "接入本地/自有端点的机制是**适配行**，没有一个叫 qwen-local 的包",
                               "状态": "机制在 · 该包名不在"},
        "dsh-force-compact": {"真实件": "dsh-compaction + dsh-compaction-basic + dsh-command-compact",
                              "为什么": "压缩是这三件；名字里没有 force-compact",
                              "状态": "机制在 · 该包名不在"},
        "dsh-llm-qwen-abliterated": {"真实件": "（无同名件）",
                                     "为什么": "这是**模型权重**的事，不是插件包；换权重不改插件名",
                                     "状态": "**该包名不在**（且本机跑不动 27B，见 gbt-model-align）"},
        "dsh-tool-web": {"真实件": "dsh-tool-web（**名字就是它，真的存在**）",
                         "为什么": "外加 dsh-web-fetch-http / dsh-web-search-deepseek 两个同族件",
                         "状态": "✅ 在"},
        "dsh-tool-file": {"真实件": "dsh-tool-fs + dsh-tool-fs-search + dsh-fs(+local)",
                          "为什么": "文件工具的真名叫 fs，没有 tool-file",
                          "状态": "机制在 · 该包名不在"},
        "dsh-tool-shell": {"真实件": "dsh-tool-pwsh / dsh-tool-bash（+ pwm/bash-local 沙箱件）",
                           "为什么": "本机是 Windows，真件是 pwsh 系；没有 tool-shell",
                           "状态": "机制在 · 该包名不在"},
        "dsh-memory-vector": {"真实件": "（无向量记忆件）",
                              "为什么": "装机没有向量库件；持久化是 dsh-session-persistence-jsonl 与 dsh-session-query-sqlite",
                              "状态": "**该包名不在**（且无对口机制）"},
        "dsh-memory-local": {"真实件": "dsh-storage(+json) + dsh-session-persistence-jsonl",
                             "为什么": "本地持久化真名是 storage/session-persistence",
                             "状态": "机制在 · 该包名不在"},
        "dsh-policy-guard": {"真实件": "dsh-sandbox-policy + dsh-permission-presets + dsh-user-approval + dsh-authorization",
                             "为什么": "策略/审批是这四件，没有 policy-guard",
                             "状态": "机制在 · 该包名不在"},
        "dsh-observability": {"真实件": "dsh-session-telemetry(+otel) + dsh-session-stats + dsh-session-log-deepseek",
                              "为什么": "可观测性真名是 telemetry/stats/log",
                              "状态": "机制在 · 该包名不在"},
    },
}


def installed_packages() -> set:
    """装机里真实存在的 `@deepseek-ai/*` 包名（**读目录，不猜**）。"""
    out = set()
    for p in (NPX / "node_modules" / PKG_SCOPE, DSH_HOME / "node_modules" / PKG_SCOPE):
        if p.is_dir():
            out |= {d.name for d in p.iterdir() if d.is_dir()}
    return out


def composition_rows() -> dict:
    """组合文件里的 row（id → 包名）—— 这是「插件清单」在装机里的**真身**。

    读的是 `dsh-base/cordis.patch.yml` 与各 preset 的 `agent.cordis.yml`。
    """
    rows, files = {}, []
    cands = [NPX / "node_modules" / PKG_SCOPE / "dsh-base" / "cordis.patch.yml"]
    pres = NPX / "node_modules" / PKG_SCOPE / "dsh-agent-presets" / "presets"
    if pres.is_dir():
        cands += sorted(pres.glob("*/agent.cordis.yml"))
    for p in cands:
        if not p.is_file():
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        files.append(str(p))
        # 只认 `- id: X` 紧跟 `name: Y` 的成对行（不猜别的形状）
        for m in re.finditer(r"-\s*id:\s*([\w.\-]+)\s*\n\s*name:\s*'?([@\w./\-]+)'?", txt):
            rid, name = m.group(1), m.group(2)
            rows.setdefault(rid, set()).add(name.replace(PKG_SCOPE + "/", ""))
    return {"读过的组合文件": files, "row 数": len(rows),
            "rows": {k: sorted(v) for k, v in sorted(rows.items())}}


def audit(names=None, claim: dict | None = None) -> dict:
    claim = claim or CLAIMED
    names = list(names or claim["名单"])
    pkgs = installed_packages()
    comp = composition_rows()
    row_names = {n for v in comp["rows"].values() for n in v}
    out_rows = []
    for n in names:
        short = n.replace(PKG_SCOPE + "/", "")
        in_pkg = short in pkgs
        in_row = short in row_names
        mapping = (claim.get("真实对应件") or {}).get(n) or {}
        out_rows.append({
            "名字": n,
            "包目录里": "在" if in_pkg else "**不在**",
            "组合 row 里": "在" if in_row else "**不在**",
            "结论": ("✅ **真件**" if (in_pkg or in_row) else "🔴 **不存在**（全盘零命中）"),
            "真实对应件": mapping.get("真实件"),
            "对照说明": mapping.get("为什么"),
        })
    real = [r for r in out_rows if r["结论"].startswith("✅")]
    return {"出处": claim.get("出处"), "核了几个": len(out_rows),
            "真的存在": len(real), "**不存在**": len(out_rows) - len(real),
            "逐条": out_rows,
            "装机真实包数": len(pkgs),
            "组合 row 数": comp["row 数"],
            "读过的组合文件": comp["读过的组合文件"],
            "口径": ["「在」= 包目录里或组合 row 里现读命中；",
                   "「不在」= 两处都零命中 ⇒ **就是不存在**，不许念成'装了没用'；",
                   "「真实对应件」是**做同一件事的另一个包**，**不是同一个包**"]}


def cmd_audit(a) -> int:
    r = audit()
    print("插件名单核对（装机真身现读）")
    print("=" * 74)
    print("出处：%s" % r["出处"])
    print("核了 %d 个 ｜ **真的存在 %d 个** ｜ **不存在 %d 个** ｜ 装机真实包 %d 个 ｜ 组合 row %d 个"
          % (r["核了几个"], r["真的存在"], r["**不存在**"], r["装机真实包数"], r["组合 row 数"]))
    print("-" * 74)
    for x in r["逐条"]:
        print("%-28s %s" % (x["名字"], x["结论"]))
        if x["真实对应件"]:
            print("      真件 → %s" % x["真实对应件"])
            if x["对照说明"]:
                print("      说明 → %s" % x["对照说明"])
    print("=" * 74)
    for c in r["口径"]:
        print("  ⚠️ %s" % c)
    return 0


def cmd_list(a) -> int:
    pkgs = installed_packages()
    comp = composition_rows()
    print(json.dumps({"装机包（%d）" % len(pkgs): sorted(pkgs),
                      "组合 row（%d）" % comp["row 数"]: comp["rows"],
                      "读过的组合文件": comp["读过的组合文件"]},
                     ensure_ascii=False, indent=1))
    return 0


def cmd_check(a) -> int:
    names = [x.strip() for x in (a.names or "").split(",") if x.strip()]
    r = audit(names=names, claim={"出处": "命令行给的名单", "名单": names, "真实对应件": {}})
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r["**不存在**"] == 0 else 4


def cmd_selftest(a) -> int:
    lines, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    pkgs = installed_packages()
    ck("**真读到装机包**（不是空表）", len(pkgs) > 10, "%d 个包" % len(pkgs))
    comp = composition_rows()
    ck("**真读到组合文件**（清单真身）", comp["row 数"] > 5,
       "%d 个 row ｜ 读过 %d 个文件" % (comp["row 数"], len(comp["读过的组合文件"])))
    # ① 正控：**真件必须判"在"**
    ok = audit(names=["dsh-tool-web"], claim={"出处": "自检", "名单": [], "真实对应件": {}})
    ck("**正控：真件 `dsh-tool-web` 判在**", ok["真的存在"] == 1 and ok["**不存在**"] == 0,
       ok["逐条"][0]["结论"])
    # ② 负控：**编的名字必须判"不存在"**（本件的存在理由）
    fake = audit(names=["dsh-tool-shell"], claim={"出处": "自检", "名单": [], "真实对应件": {}})
    ck("**负控：编造的 `dsh-tool-shell` 判不存在**",
       fake["**不存在**"] == 1, fake["逐条"][0]["结论"])
    # ③ 真读数：那份 10 个的名单，结论必须是「1 真 9 假」——**写死判据会被数据变化咬**，
    #    所以这里只断言"真的存在 == 1"，并把它打印出来供对账。
    r = audit()
    ck("**真读数：那份 10 个名单里只有 1 个真存在**",
       r["真的存在"] == 1 and r["核了几个"] == 10,
       "真存在 %d ｜ 不存在 %d ｜ 真件是 %s"
       % (r["真的存在"], r["**不存在**"],
          [x["名字"] for x in r["逐条"] if x["结论"].startswith("✅")]))
    # ④ 每个名字都要有结论（不许静默丢）
    ck("**逐条都有结论**（不许静默丢）",
       all(x["结论"] for x in r["逐条"]) and len(r["逐条"]) == 10, "%d 条" % len(r["逐条"]))
 # ⑤ **我自己写的「真实对应件」也必须逐个现读核过** ——
    #    否则我就在犯本件要抓的那个错：**编一个像真的包名**。
    mine, ghost = 0, []
    for claimed, mp in (CLAIMED.get("真实对应件") or {}).items():
        for t in re.findall(r"\b(dsh-[a-z0-9\-]+|cordis-plugin-[a-z0-9\-]+)\b",
                            str(mp.get("真实件") or "")):
            mine += 1
            if t not in pkgs:
                ghost.append("%s→%s" % (claimed, t))
    ck("**我写的对照件名也全部现读命中**（不许我自己编包名）",
       mine > 0 and not ghost,
       "核了我写的 %d 个名字 ｜ 不存在的：%s" % (mine, ghost or "无"))
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="插件名单核对（装机真身只读）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("audit").set_defaults(func=cmd_audit)
    sub.add_parser("list").set_defaults(func=cmd_list)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    c = sub.add_parser("check")
    c.add_argument("--names", default="", help="逗号分隔的包名")
    c.set_defaults(func=cmd_check)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
