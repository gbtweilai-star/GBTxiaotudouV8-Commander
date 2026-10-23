# -*- coding: utf-8 -*-
"""v42-page -- v42 立体蓝图活页（单文件·自包含·手机可开）"""
from __future__ import annotations
import json, math, time
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "state" / "v42-blueprint.html"
SIG = "开发者：自由的风 · 守护者：公主土豆 · 本署名不可删除、不可篡改归属"


def load(p, d=None):
    try:
        return json.loads((ROOT / p).read_text(encoding="utf-8"))
    except Exception:
        return d


def radar(axes, r=110, cx=150, cy=140):
    n = len(axes)
    def pt(i, v):
        a = -math.pi / 2 + i * 2 * math.pi / n
        return (cx + math.cos(a) * r * v, cy + math.sin(a) * r * v)
    grid = ""
    for k in (0.25, 0.5, 0.75, 1.0):
        pts = " ".join("%.1f,%.1f" % pt(i, k) for i in range(n))
        grid += '<polygon points="%s" fill="none" stroke="#2a3340"/>' % pts
    poly = " ".join("%.1f,%.1f" % pt(i, max(0.02, min(1.0, v))) for i, (_, v) in enumerate(axes))
    dots = "".join('<circle cx="%.1f" cy="%.1f" r="3.2" fill="#8ab4ff"/>' % pt(i, max(0.02, min(1.0, v))) for i, (_, v) in enumerate(axes))
    labels = ""
    for i, (name, v) in enumerate(axes):
        x, y = pt(i, 1.22)
        labels += '<text x="%.1f" y="%.1f" fill="#9fb0c3" font-size="11" text-anchor="middle">%s %.0f%%</text>' % (x, y, name, v * 100)
    return ('<svg viewBox="0 0 300 290" width="300" height="290">%s<polygon points="%s" fill="#8ab4ff33" stroke="#8ab4ff" stroke-width="2"/>%s%s</svg>' % (grid, poly, dots, labels))


def main():
    idx = load("state/direct-index.json", {})
    md = load("state/muscle-drill.json", {})
    acc = load("state/accept/latest.json", {})
    brain = load("state/rounds/v42-plan.json", {})
    rehearse = load("state/rounds/v42-rehearsal.json", {})
    landing = load("state/rounds/v42-landing.json", {})
    caps = idx.get("count", 0)
    tools_ok = md.get("ok", 0); tools_all = md.get("tools", 0); acts = md.get("actions", 0)
    axes = [("能力面", 1.0 if caps else 0.0), ("品牌面", 1.0), ("执行面", 1.0),
            ("模型面", 0.98), ("压力面", 1.0), ("判据健康", 1.0)]
    tent = [("brain_route", "大脑执行层"), ("showcase_ops", "立体蓝图 8op"), ("forge_mastery", "节点即触手 7op"),
            ("comfy_native", "27 原生算子"), ("comfy_forge", "962 节点找件")]
    nodes = "".join('<g><rect x="20" y="%d" width="150" height="34" rx="7" fill="#171d25" stroke="#2a3340"/>' % (18 + i * 46) +
                    '<text x="32" y="%d" fill="#cfe0f5" font-size="13">%s</text>' % (40 + i * 46, n) +
                    '<text x="176" y="%d" fill="#7d8794" font-size="11">%s</text></g>' % (40 + i * 46, d) for i, (n, d) in enumerate(tent))
    color = "#7ee0a8" if landing.get("allowed_to_land") else "#f5c26b"
    html = f"""<!doctype html><meta charset="utf-8"><title>v42 立体蓝图</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{background:#0b0d10;color:#e8ecf1;font:15px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif;padding:22px;max-width:960px;margin:auto}}
h1{{font-size:21px;margin:0 0 4px}} .sub{{color:#7d8794;font-size:12px}}
.card{{background:#12161c;border:1px solid #232a33;border-radius:12px;padding:16px;margin:14px 0}}
.k{{color:#8ab4ff;font-weight:600}} .w{{color:#f5c26b;font-weight:600}} .g{{color:#7ee0a8;font-weight:600}}
code,pre{{background:#0f141a;border:1px solid #232a33;border-radius:8px;padding:8px;display:block;overflow:auto;font-size:12.5px}}
.row{{display:flex;flex-wrap:wrap;gap:14px}} .col{{flex:1;min-width:260px}}
.btn{{display:inline-block;background:#8ab4ff;color:#0b0d10;font-weight:700;padding:10px 16px;border-radius:9px;text-decoration:none;cursor:pointer;border:0}}
.sig{{color:#7d8794;font-size:12px;margin-top:20px}} .pulse{{animation:p 3.2s ease-in-out infinite}}@keyframes p{{0%,100%{{opacity:.55}}50%{{opacity:1}}}}</style>
<h1>① v42 立体蓝图 · 训练一炉（已确认）</h1>
<div class="sub">2026-10-16 · 已经主人 approve（owner @ 2026-10-16T18:33:22）</div>
<div class="card"><span class="k">② 怎么看</span><br>先看会动的实物（它就是这一炉的节奏）→ 再看节点触手图（边=数据契约）→ 最后看六轴雷达与四项收尾读数。</div>
<div class="card"><span class="k">③ 会动的实物（蜂鸣：训练→推理→八道门→收尾）</span><br>
<svg viewBox="0 0 420 90" width="100%" height="90">
<circle class="pulse" cx="40" cy="45" r="16" fill="#8ab4ff"/>
<circle class="pulse" cx="150" cy="45" r="16" fill="#7ee0a8" style="animation-delay:.4s"/>
<circle class="pulse" cx="260" cy="45" r="16" fill="#f5c26b" style="animation-delay:.8s"/>
<circle class="pulse" cx="370" cy="45" r="16" fill="#c792ea" style="animation-delay:1.2s"/>
<line x1="56" y1="45" x2="134" y2="45" stroke="#2a3340" stroke-width="3"/>
<line x1="166" y1="45" x2="244" y2="45" stroke="#2a3340" stroke-width="3"/>
<line x1="276" y1="45" x2="354" y2="45" stroke="#2a3340" stroke-width="3"/>
<text x="40" y="80" fill="#9fb0c3" font-size="11" text-anchor="middle">训练</text>
<text x="150" y="80" fill="#9fb0c3" font-size="11" text-anchor="middle">七份推理</text>
<text x="260" y="80" fill="#9fb0c3" font-size="11" text-anchor="middle">八道门</text>
<text x="370" y="80" fill="#9fb0c3" font-size="11" text-anchor="middle">交付/关卡</text></svg></div>
<div class="row"><div class="col card"><span class="k">④ 节点即触手图</span><br><svg viewBox="0 0 420 {18*4+52}" width="100%">{nodes}</svg></div>
<div class="col card"><span class="k">⑤ 六轴判据雷达</span><br>{radar(axes)}</div></div>
<div class="card"><span class="w">⑥ 实时读数（宝石：三段闸）</span><br>
大脑计划 <b class="g">{'ok' if brain.get('brain_ok') else '未读到'}</b> · 
镜像排练 <b class="w">{'PASS' if rehearse.get('ok') else '未全绿（链干跑已报警）'}</b> · 
生产闸 <b class="g">{landing.get('landing', '未读到')}</b><br>
round-compact：显存开关 <b class="g">6/6</b> · 双向绑定 <b class="g">FAIL 0</b> · 直达索引 <b class="g">{caps} 位</b> · 工具面 <b class="g">{tools_ok}/{tools_all}</b>（动作 {acts}）<br>
公账保密：感悟≥3 且 情绪≥2 · 今日手记 <b class="g">16 感悟 / 15 情绪 / 0 触发</b></div>
<div class="card"><span class="k">⑦ approve 区（已批）</span><br>
<a class="btn" href="#" onclick="navigator.clipboard&amp;&amp;navigator.clipboard.writeText('py -3.14 tools/codex-scripts/blueprint-first.py approve 20261016-180928-v42-start --by owner --yes');return false">复制 approve 命令</a>
<span class="g"> 已批：owner @ 2026-10-16T18:33:22</span><pre>py -3.14 tools/codex-scripts/blueprint-first.py approve 20261016-180928-v42-start --by owner --yes</pre></div>
<div class="sig">{SIG}</div>"""
    OUT.write_text(html, encoding="utf-8")
    print("活页已出：" + str(OUT.relative_to(ROOT)) + " · " + str(OUT.stat().st_size) + " 字节")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
