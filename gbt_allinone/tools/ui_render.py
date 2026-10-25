# gbt-capability: ui_render
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""受控界面渲染：**模型输出只能落在预定义组件与动作里**（蒸馏自 json-render，只取约束核）。

## 抓取口径（本仓规矩：凡抓取必写源·时间·口径）
· **源**：2026-09-28 主人给的周榜卡 `vercel-labs/json-render`（#09 · 当周 +1,210★ · GENERATIVE UI）：
  「把模型输出限制在预定义组件和动作中，按提示生成可控界面，并支持 React、原生应用、视频、PDF、
  邮件和终端等多种渲染目标。」
  —— 一手仓库与文档本轮**未联网核验**（主人令：不出网花钱的动作），只蒸馏**约束渲染架构**，
  不引用它的实现/代码/组件库。
· **时间**：2026-09-28。
· **口径**：**约束优先**——模型产出的不是 HTML，而是一份 **JSON 规格（spec）**；
  只有白名单里的组件能出现，未知组件/任意脚本/外部资源**一律当场拒**。
  与「画面问题」直接相关：让模型在**可控组件**里表达，而不是让模型随手画（那会得到糊图）。

## 蒸馏判断：json-render 的核里我们真缺哪块
| 它的能力 | 我们已有的对位 | 结论 |
|---|---|---|
| 生成式 UI | `console_pages`（快照内联页）· `flow_canvas`（自包含 SVG） | **已有渲染器，缺"约束层"** |
| **把模型输出限制在预定义组件/动作** | 无 | **补这块（本件）** |
| 多渲染目标 | 页面（HTML）为主 | **只做 HTML 自包含**（其余目标如实标未做） |

## 硬规矩
1. **白名单是硬的**：组件名必须逐字命中 `COMPONENTS`；未命中 ⇒ `fail_closed` 拒（不"尽量渲染"）。
2. **零脚本零外链**：产物页面不引任何 http(s) 资源、不带 `<script>`（与 console/画布同一条纪律）。
3. **动作也受控**：spec 里的 `actions` 只允许白名单动作名（`open_page`/`copy`/`download`），
   未知动作 ⇒ 拒；**渲染器不执行任何动作**（只把它渲染成可见标签，执行另走门）。
4. **不编数**：spec 里的数值必须带 `src`（出处）；没 src 的数**照渲但在页面上标红**（不许悄悄进页面）。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_OUT = _ROOT / "outputs" / "ui-render"

# 组件白名单：一个组件一个形状（名字即契约，逐字命中才算）
COMPONENTS = {
    "title": {"fields": ("text",), "desc": "标题"},
    "text": {"fields": ("text",), "desc": "段落"},
    "metric": {"fields": ("label", "value", "src"), "desc": "指标（**必须带 src**）"},
    "list": {"fields": ("items",), "desc": "列表"},
    "steps": {"fields": ("items",), "desc": "编号步骤"},
    "badge": {"fields": ("text", "tone"), "desc": "徽标（tone: ok|warn|bad）"},
    "table": {"fields": ("head", "rows"), "desc": "表格"},
    "divider": {"fields": (), "desc": "分隔线"},
}
ACTIONS = ("open_page", "copy", "download")
_TONES = ("ok", "warn", "bad")


def spec(**_kw) -> dict:
    """报告**组件契约**（模型/调用方照这份写 spec；白名单是唯一真相）。"""
    return {"ok": True, "op": "spec", "components": COMPONENTS, "actions": list(ACTIONS),
            "_口径": "只有这些组件能出现；未知组件/未列动作/脚本/外链一律拒"}


def check(spec_obj=None, **_kw) -> dict:
    """校验一份 spec：组件白名单 + 字段齐 + 动作白名单 + 指标带 src。全过才 ok。"""
    if not isinstance(spec_obj, dict):
        return {"ok": False, "fail_closed": True, "error": "spec 要给（对象，形如 {'blocks':[...]}）"}
    blocks = spec_obj.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        return {"ok": False, "fail_closed": True, "error": "spec.blocks 要是非空列表"}
    problems, warn = [], []
    for i, b in enumerate(blocks):
        if not isinstance(b, dict):
            problems.append("块 %d 不是对象" % i)
            continue
        name = str(b.get("type") or "")
        if name not in COMPONENTS:
            problems.append("块 %d 组件不在白名单：%r" % (i, name))
            continue
        for f in COMPONENTS[name]["fields"]:
            if f not in b and not (name == "metric" and f == "src"):
                problems.append("块 %d（%s）缺字段 %s" % (i, name, f))
        if name == "metric" and not str(b.get("src") or "").strip():
            warn.append("块 %d 的指标『%s』没写 src（页面上会标红）" % (i, b.get("label")))
        if name == "badge" and b.get("tone") and b.get("tone") not in _TONES:
            problems.append("块 %d 的 tone 非 ok|warn|bad：%r" % (i, b.get("tone")))
    for a in spec_obj.get("actions") or []:
        if a not in ACTIONS:
            problems.append("动作不在白名单：%r" % (a,))
    raw = json.dumps(spec_obj, ensure_ascii=False).lower()
    for bad in ("<script", "javascript:", "http://", "https://"):
        if bad in raw:
            problems.append("spec 里出现禁字 %r（零脚本零外链是硬规矩）" % bad)
    return {"ok": not problems, "op": "check", "problems": problems, "warnings": warn,
            "blocks": len(blocks)}


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render(spec_obj=None, name: str = "ui", **_kw) -> dict:
    """spec → **自包含页面**（零脚本零外链）。**先过 check**，不过 ⇒ 拒渲（不"尽量渲染"）。"""
    c = check(spec_obj=spec_obj)
    if not c.get("ok"):
        return {"ok": False, "fail_closed": True, "op": "render",
                "error": "spec 没过白名单校验 ⇒ 拒渲", "problems": c.get("problems")}
    blocks, body = spec_obj.get("blocks") or [], []
    body.append("<h1>%s</h1>" % _esc(spec_obj.get("title") or "受控界面"))
    for b in blocks:
        t = b.get("type")
        if t == "title":
            body.append("<h2>%s</h2>" % _esc(b.get("text")))
        elif t == "text":
            body.append("<p>%s</p>" % _esc(b.get("text")))
        elif t == "divider":
            body.append("<hr>")
        elif t == "metric":
            src = str(b.get("src") or "").strip()
            flag = "" if src else " <span class='miss'>缺 src，需人看</span>"
            body.append("<div class='metric'><span class='k'>%s</span>"
                        "<span class='v'>%s</span><span class='src'>源：%s</span>%s</div>"
                        % (_esc(b.get("label")), _esc(b.get("value")), _esc(src or "（无）"), flag))
        elif t == "list":
            body.append("<ul>%s</ul>" % "".join("<li>%s</li>" % _esc(i)
                                                for i in (b.get("items") or [])))
        elif t == "steps":
            body.append("<ol>%s</ol>" % "".join("<li>%s</li>" % _esc(i)
                                                for i in (b.get("items") or [])))
        elif t == "badge":
            tone = b.get("tone") or "ok"
            body.append("<span class='badge %s'>%s</span>" % (_esc(tone), _esc(b.get("text"))))
        elif t == "table":
            head = "".join("<th>%s</th>" % _esc(h) for h in (b.get("head") or []))
            rows = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % _esc(c2) for c2 in row)
                           for row in (b.get("rows") or []))
            body.append("<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (head, rows))
    acts = spec_obj.get("actions") or []
    if acts:
        body.append("<p class='acts'>动作（**只展示不执行**）：%s</p>"
                    % "、".join("<code>%s</code>" % _esc(a) for a in acts))
    html = ("<!doctype html><html><head><meta charset='utf-8'><title>%s</title><style>"
            "body{background:#0B0B14;color:#EDEDF5;font-family:sans-serif;margin:24px;max-width:960px}"
            "h1{color:#F5B041}h2{color:#00E5FF}.metric{border-left:3px solid #7C4DFF;padding:6px 10px;margin:6px 0}"
            ".metric .k{color:#8A8AA3}.metric .v{font-size:20px;margin-left:8px}"
            ".metric .src{color:#8A8AA3;font-size:12px;margin-left:12px}"
            ".miss{color:#F5B041;font-size:12px}table{border-collapse:collapse}"
            "th,td{border:1px solid #333;padding:4px 8px;font-size:13px}"
            ".badge{padding:2px 8px;border-radius:10px;background:#141428}"
            ".ok{color:#00E5FF}.warn{color:#F5B041}.bad{color:#FF6B6B}.acts{color:#8A8AA3;font-size:13px}"
            "</style></head><body>%s<p class='acts'>渲染器：ui_render（受控组件白名单 · 零脚本零外链 · "
            "生成于 %s）</p></body></html>" % (_esc(spec_obj.get("title") or "受控界面"),
                                             "".join(body), time.strftime("%Y-%m-%d %H:%M")))
    _OUT.mkdir(parents=True, exist_ok=True)
    page = _OUT / ("%s.html" % "".join(ch for ch in str(name) if ch.isalnum() or ch in "-_")[:40] or "ui")
    page.write_text(html, encoding="utf-8")
    return {"ok": True, "op": "render", "page": str(page.relative_to(_ROOT)),
            "bytes": page.stat().st_size, "blocks": len(blocks),
            "warnings": c.get("warnings") or [],
            "_口径": "先过白名单再渲；零脚本零外链；动作只展示不执行"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "ui_render", "tentacle": "ui_render",
            "entry": "run_task('ui_render', {...})",
            "ops": ["spec", "check", "render", "where"],
            "distilled_from": "2026-09-28 主人给的周榜卡 vercel-labs/json-render（#09 · +1,210★ · "
                              "GENERATIVE UI）——只取**约束渲染架构**",
            "not_copied": "不引它的 React/原生/视频/PDF/邮件等渲染目标实现；本件只做 HTML 自包含页"
                          "（其余目标如实标未做）",
            "hard_rules": ["组件白名单逐字命中，未知组件 ⇒ 拒（不『尽量渲染』）",
                           "零脚本零外链（禁字扫描进 check）",
                           "动作只允许 open_page/copy/download 且**只展示不执行**",
                           "指标必须带 src；没带的照渲但页面标红（不编数）"],
            "files": {"产物": str(_OUT.relative_to(_ROOT))},
            "contract": [
                {"op": "spec", "params": "—", "returns": "组件契约（模型照它写 spec）"},
                {"op": "check", "params": "spec_obj", "returns": "白名单校验（problems/warnings）"},
                {"op": "render", "params": "spec_obj + name", "returns": "自包含页面（先过 check）"},
            ]}


def run_op(op: str = "spec", **params) -> dict:
    op = (op or "spec").lower()
    for n, fn in (("spec", spec), ("check", check), ("render", render), ("where", where)):
        if op == n:
            return fn(**params)
    return {"ok": False, "fail_closed": True, "error": f"未知 op:{op}（spec/check/render/where）"}


if __name__ == "__main__":                                     # 主人的终端入口
    import argparse
    ap = argparse.ArgumentParser(description="受控界面渲染（json-render 架构蒸馏 · 白名单约束）")
    ap.add_argument("cmd", nargs="?", default="spec")
    a = ap.parse_args()
    print(json.dumps(run_op(a.cmd), ensure_ascii=False, indent=1))
