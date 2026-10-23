# -*- coding: utf-8 -*-
"""从 caps_registry 生成**开源发布用**的能力文档（唯一数据源 = 注册表，不手抄）。

产出（都在 --out 目录下）：
  data/capabilities.json          341 位的机器可读全量（含域/说明/是否只读/是否需参数）
  docs/03-capabilities.md         总表：30 个域 × 数量 + 每域的入口链接
  docs/capabilities/<domain>.md   每域详解：位名 / 只读还是需授权 / 一句话用途
用法：
  py -3.14 -X utf8 tools/codex-scripts/gen-open-source-caps.py --out outputs/open-source-release
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

DOMAIN_CN = {
    "creation": "创作", "system": "系统", "llm": "大模型与大脑", "security": "安全",
    "mind": "心智", "tentacle": "触手（手眼网耳）", "pipeline": "流水线与发布",
    "recon": "只读侦察", "video": "视频", "data": "数据", "engine": "引擎（工作流/定时）",
    "tools": "工具与改代码", "integration": "集成（飞书/Notion/CLI）", "devour": "吞天（自我进化）",
    "vision": "视觉", "finance": "财务", "longrun": "长程任务", "voice": "语音",
    "project": "项目测绘", "automation": "浏览器自动化", "device": "设备", "brain": "梦境/闭环",
    "collab": "协作（信息素场地）", "desktop": "桌面智能体", "infra": "基础设施（云电脑）",
    "social": "社交发布", "comms": "通信", "life": "生命档案", "image_video": "图像/视频生成",
    "framework": "框架自省",
}

MAX_CELL = 140     # 表格单元格里说明的最大字数（全文仍留在 data/capabilities.json）


def summary(desc: str) -> str:
    """把注册表原文压成一行可读摘要：去换行、去竖线、超长截断。

    🔴 只截显示，不改事实：完整原文一字不动留在 data/capabilities.json。
    """
    s = " ".join((desc or "").split())
    s = s.replace("|", "\\|")
    if len(s) > MAX_CELL:
        s = s[:MAX_CELL].rstrip() + "…"
    return s or "—"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="outputs/open-source-release")
    a = ap.parse_args()

    from gbt_allinone import caps_registry as R
    from gbt_allinone.security import policy as P

    def static_scopes(name: str) -> str:
        """按**空 payload** 静态算这一位要过哪些作用域（只读工具，不触发任何动作）。

        2026-10-21 补：此前域页只有「类型/需参数/它做什么」三列，读者不知道
        「这一位到底要哪张票、票叫什么名字」，只能自己去翻 policy.py。
        口径写死：空 payload 的静态判定；带 op 的位（如 comfy_cloud / pentest）
        真实作用域随 op 变，这里标出来并友情提示「逐 op 见模块」。
        """
        try:
            d = P.evaluate(name, {})
            scopes = list(getattr(d, "scopes", None) or [])
        except Exception:                                   # noqa: BLE001
            return "（取不到静态作用域）"
        if not scopes:
            return "零作用域（空 payload 下不需要票）"
        return "、".join("`%s`" % s for s in scopes)

    caps = R.all_caps()
    out = pathlib.Path(a.out)
    (out / "data").mkdir(parents=True, exist_ok=True)
    (out / "docs" / "capabilities").mkdir(parents=True, exist_ok=True)

    rows = []
    for c in caps:
        rows.append({
            "name": c["name"],
            "domain": c.get("domain") or "other",
            "desc": (c.get("desc") or "").strip(),
            "readonly": bool(c.get("safe")),
            "requires_params": bool(c.get("requires_params")),
            "params_hint": (c.get("params_hint") or ""),
            "scopes_static": static_scopes(c["name"]),
            "handler": c.get("handler") or c["name"],
        })
    rows.sort(key=lambda r: (r["domain"], r["name"]))

    (out / "data" / "capabilities.json").write_text(
        json.dumps({"count": len(rows), "domains": len({r["domain"] for r in rows}),
                    "note": "由 gbt_allinone.caps_registry 现读生成；readonly=false 表示该位会改状态或出网/花钱，"
                            "调用前需人工授权（作用域门）。",
                    "capabilities": rows}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    by_dom = collections.defaultdict(list)
    for r in rows:
        by_dom[r["domain"]].append(r)

    # 每域详解
    for dom, items in sorted(by_dom.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        cn = DOMAIN_CN.get(dom, dom)
        ro = sum(1 for x in items if x["readonly"])
        lines = [
            "# %s · `%s`（%d 位）" % (cn, dom, len(items)),
            "",
            "> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；"
            "其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出。",
            "",
            "| 能力位 | 类型 | 需参数 | 它做什么 |",
            "|---|---|---|---|",
        ]
        for x in items:
            lines.append("| `%s` | %s | %s | %s |" % (
                x["name"],
                "只读" if x["readonly"] else "**需授权**",
                "是" if x["requires_params"] else "—",
                summary(x["desc"]),
            ))
        lines += ["", "> 表格里是**摘要**（超过 %d 字截断）；下面每位还有**逐位详解**"
                  "（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。"
                  % MAX_CELL, "", "---", "", "## 逐位详解", ""]
        for x in items:
            lines += [
                "### `%s`" % x["name"],
                "",
                "- **域**：`%s`（%s）" % (x["domain"], cn),
                "- **类型**：%s · **需参数**：%s" % (
                    "只读（不改状态、不出网）" if x["readonly"] else "**需授权**（会写盘 / 花钱 / 出网）",
                    ("是 —— " + (x["params_hint"] or "见注册表 params")) if x["requires_params"] else "否"),
                "- **要哪张票（静态）**：%s" % x["scopes_static"],
                "- **它做什么**：%s" % (x["desc"] or "—"),
                "- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap %s '<json>'`"
                % x["name"],
                "- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名"
                "`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，"
                "回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**",
                "",
            ]
        lines += ["---", "", "返回 [能力总表](../03-capabilities.md)", ""]
        (out / "docs" / "capabilities" / ("%s.md" % dom)).write_text("\n".join(lines), encoding="utf-8")

    # 总表
    total_ro = sum(1 for r in rows if r["readonly"])
    lines = [
        "# 能力总表 · 共 %d 位 / %d 个域" % (len(rows), len(by_dom)),
        "",
        "> 自动生成，数据源 `gbt_allinone/caps_registry.py`。机器可读版：[`data/capabilities.json`](../data/capabilities.json)。",
        "",
        "- **只读 %d 位**：不改状态、不出网，可直接调用。" % total_ro,
        "- **改状态/出网 %d 位**：会写盘、花钱或把数据发到外部服务 —— 必须先过人给的授权门。" % (len(rows) - total_ro),
        "",
        "| 域 | 中文 | 位数 | 只读 | 需授权 | 详解 |",
        "|---|---|---|---|---|---|",
    ]
    for dom, items in sorted(by_dom.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        ro = sum(1 for x in items if x["readonly"])
        lines.append("| `%s` | %s | %d | %d | %d | [打开](capabilities/%s.md) |"
                     % (dom, DOMAIN_CN.get(dom, dom), len(items), ro, len(items) - ro, dom))
    lines += ["", "---", "", "回到 [README](../../README.md)", ""]
    (out / "docs" / "03-capabilities.md").write_text("\n".join(lines), encoding="utf-8")

    # 域分布图（真数据画出来的横条图，给 README 当视觉锚点）
    (out / "assets").mkdir(parents=True, exist_ok=True)
    top = sorted(by_dom.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:14]
    w, rh, top_pad, left = 760, 26, 54, 150
    h = top_pad + rh * len(top) + 40
    mx = max(len(v) for _, v in top)
    bars = []
    for i, (dom, items) in enumerate(top):
        n, ro = len(items), sum(1 for x in items if x["readonly"])
        y = top_pad + i * rh
        bw = int((n / mx) * (w - left - 120))
        rw = int(bw * ro / n) if n else 0
        bars.append('<text x="12" y="%d" class="lb">%s</text>' % (y + 15, DOMAIN_CN.get(dom, dom)))
        bars.append('<rect x="%d" y="%d" width="%d" height="16" rx="4" fill="#2ea043"/>'
                    % (left, y + 3, rw))
        bars.append('<rect x="%d" y="%d" width="%d" height="16" rx="4" fill="#d29922"/>'
                    % (left + rw, y + 3, bw - rw))
        bars.append('<text x="%d" y="%d" class="vl">%d（只读 %d）</text>'
                    % (left + bw + 8, y + 16, n, ro))
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" role="img" aria-label="能力位域分布">
  <style>
    .ti { font-family:"Microsoft YaHei","PingFang SC",sans-serif; font-size:16px; font-weight:600; fill:#24292f; }
    .lb { font-family:"Microsoft YaHei","PingFang SC",sans-serif; font-size:12.5px; fill:#24292f; }
    .vl { font-family:Consolas,monospace; font-size:12px; fill:#57606a; }
    .lg { font-family:"Microsoft YaHei","PingFang SC",sans-serif; font-size:12px; fill:#57606a; }
  </style>
  <text x="12" y="26" class="ti">能力位域分布（共 %d 位 / %d 域 · 绿=只读 · 橙=需授权）</text>
  %s
  <rect x="12" y="%d" width="12" height="12" rx="3" fill="#2ea043"/><text x="30" y="%d" class="lg">只读（不改状态/不出网）</text>
  <rect x="210" y="%d" width="12" height="12" rx="3" fill="#d29922"/><text x="228" y="%d" class="lg">需授权（写盘/花钱/出网）</text>
</svg>
""" % (w, h, w, h, len(rows), len(by_dom), chr(10).join(bars),
       h - 26, h - 18, h - 26, h - 18)
    (out / "assets" / "domains.svg").write_text(svg, encoding="utf-8")

    print("生成完毕：%d 位 / %d 域 → %s" % (len(rows), len(by_dom), out))
    print("  data/capabilities.json · docs/03-capabilities.md · docs/capabilities/*.md（%d 个）· assets/domains.svg" % len(by_dom))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
