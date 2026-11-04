# -*- coding: utf-8 -*-
"""team_mirror — 生成 GBT天真多维度团队/任务/成片状态镜像 HTML（单文件，无外链）。"""
from __future__ import annotations

import argparse
import html
import json
import os
import time

CSS = """
:root{--bg:#0b0d12;--card:#121621;--line:#232a3a;--txt:#e8edf7;--dim:#8d98ad;
--ok:#36d399;--run:#60a5fa;--warn:#fbbd23;--bad:#f87272;--gold:#e8c46a}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(1200px 600px at 20% -10%,#1a2130,#0b0d12 60%);
color:var(--txt);font:14px/1.55 "Segoe UI","Microsoft YaHei",sans-serif;padding:28px}
h1{font-size:22px;margin:0 0 4px;letter-spacing:.5px}.sub{color:var(--dim);margin-bottom:20px}
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:20px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px}
.kpi b{display:block;font-size:24px;color:var(--gold)}.kpi span{color:var(--dim);font-size:12px}
.grid{display:grid;grid-template-columns:1.05fr .95fr;gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin-bottom:16px}
.card h2{font-size:15px;margin:0 0 12px;color:#cfd8ea;letter-spacing:.4px}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:8px 6px;border-bottom:1px solid #1b2231;vertical-align:top}
th{color:var(--dim);font-weight:500}code{color:#a9c1ef;font-size:12px}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:1px}
.run{background:var(--run);box-shadow:0 0 8px var(--run)}.ok{background:var(--ok)}.warn{background:var(--warn)}.bad{background:var(--bad)}.idle{background:#556}
.agent{display:flex;justify-content:space-between;gap:10px;padding:9px 0;border-bottom:1px solid #1b2231}
.agent:last-child{border:0}.agent .name{font-weight:600}.agent .task{color:var(--dim);font-size:12px}
.badge{border:1px solid var(--line);border-radius:99px;padding:1px 9px;font-size:11px;color:var(--dim);white-space:nowrap}
.pill{display:inline-block;border-radius:6px;padding:1px 7px;font-size:11px;margin:1px 3px 1px 0;border:1px solid #2b3448;color:#b9c5dc}
.oktxt{color:var(--ok)}.badtxt{color:var(--bad)}.warntxt{color:var(--warn)}.dim{color:var(--dim)}
.film{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.shot{border:1px solid #2a3347;border-radius:10px;padding:10px;background:#0f1420}
.shot b{color:var(--gold)}.shot .st{font-size:11px;margin-top:3px}
.bar{height:7px;background:#1a2130;border-radius:99px;overflow:hidden;margin-top:8px}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#60a5fa,#36d399);width:var(--w)}
a{color:#8fb8ff;text-decoration:none}a:hover{text-decoration:underline}
pre{white-space:pre-wrap;background:#0d121c;border:1px solid #1f2838;border-radius:10px;padding:10px;font-size:12px;color:#b9c5dc}
.foot{color:#67728a;font-size:12px;margin-top:18px}
@media(max-width:1100px){.kpis{grid-template-columns:repeat(3,1fr)}.grid{grid-template-columns:1fr}.film{grid-template-columns:repeat(2,1fr)}}
"""


def esc(x):
    return html.escape(str(x), quote=True)


def badge(status):
    m = {"running": ("run", "运行中"), "in_progress": ("run", "进行中"),
         "completed": ("ok", "完成"), "pending": ("warn", "待处理"),
         "blocked": ("bad", "阻塞"), "inactive": ("idle", "空闲"),
         "failed": ("bad", "失败")}
    cls, label = m.get(status, ("idle", status))
    return '<span class="badge"><span class="dot %s"></span>%s</span>' % (cls, esc(label))


def render(data):
    agents = data.get("agents", [])
    tasks = data.get("tasks", [])
    film = data.get("film", {})
    shots = film.get("shots", [])
    running = sum(1 for a in agents if a.get("status") == "running")
    done = sum(1 for t in tasks if t.get("status") == "completed")
    active = sum(1 for t in tasks if t.get("status") in ("in_progress", "pending"))
    kpis = [
        (len(agents), "触手总数"), (running, "正在运行"),
        (active, "活动任务"), (done, "已完成任务"),
        (film.get("version", "-"), "成片版本"), (film.get("duration", "-"), "成片时长"),
    ]
    k = "".join('<div class="kpi"><b>%s</b><span>%s</span></div>' % (esc(v), esc(l)) for v, l in kpis)

    arows = []
    for a in agents:
        arows.append(
            '<div class="agent"><div><div class="name">%s <span class="dim">%s</span></div>'
            '<div class="task">%s</div></div><div>%s</div></div>' % (
                esc(a.get("name")), esc(a.get("role", "")),
                esc(a.get("task", "")), badge(a.get("status"))))

    trows = []
    for t in tasks:
        trows.append(
            "<tr><td><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                esc(t.get("id")), esc(t.get("subject", "")), esc(t.get("owner", "")),
                badge(t.get("status")), esc(", ".join(t.get("outputs", [])))))

    shot_html = []
    for s in shots:
        state = s.get("state", "pending")
        cls = {"ok": "oktxt", "fixed": "oktxt", "pending": "warntxt", "old": "badtxt"}.get(state, "dim")
        shot_html.append(
            '<div class="shot"><b>%s</b><div class="dim">%s</div>'
            '<div class="st %s">%s</div><div class="bar"><i style="--w:%s%%"></i></div></div>' % (
                esc(s.get("name")), esc(s.get("req", "")), cls,
                esc(s.get("note", "")), int(s.get("progress", 0))))

    artifacts = data.get("artifacts", [])
    arts = "".join('<div class="agent"><div><div class="name">%s</div><div class="task">%s</div></div>'
                   '<div class="dim">%s</div></div>' % (esc(x.get("name")), esc(x.get("path")), esc(x.get("note", "")))
                   for x in artifacts)

    manifest = data.get("manifest", {})
    mline = manifest.get("summary", "")
    qa = data.get("qa", [])

    return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="10">
<title>GBT天真 · 多维度状态镜像</title><style>%s</style></head><body>
<h1>GBT天真 · 多维度状态镜像</h1>
<div class="sub">触手 / 任务 / 成片 / 交付四维状态 · 快照 %s · 每 10s 刷新</div>
<div class="kpis">%s</div>
<div class="grid">
<div>
  <div class="card"><h2>触手状态</h2>%s</div>
  <div class="card"><h2>成片维度 · E01-01</h2>
    <div class="film">%s</div>
    <div class="foot">%s</div></div>
  <div class="card"><h2>交付与产物</h2>%s</div>
</div>
<div>
  <div class="card"><h2>任务板</h2><table><thead><tr><th>ID</th><th>任务</th><th>Owner</th><th>状态</th><th>产物</th></tr></thead><tbody>%s</tbody></table></div>
  <div class="card"><h2>验收 / 缺陷</h2>%s</div>
  <div class="card"><h2>账簿</h2><div class="%s">%s</div></div>
</div></div>
<div class="foot">本镜像由 team_mirror.py 生成；状态源为 DSH Team 面板快照。文件路径均指向本机工作区。</div>
</body></html>""" % (
        CSS, esc(data.get("updated", "")), k, "".join(arows), "".join(shot_html),
        esc(film.get("note", "")), arts, "".join(trows),
        "".join("<div class='agent'><div><div class='name'>%s</div><div class='task %s'>%s</div></div></div>" % (
            esc(x.get("name")), "oktxt" if x.get("ok") else "badtxt", esc(x.get("detail", ""))) for x in qa),
        "warntxt" if manifest.get("ok") is False else "oktxt", esc(mline))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    data = json.load(open(args.data, encoding="utf-8"))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    open(args.out, "w", encoding="utf-8").write(render(data))
    print(json.dumps({"ok": True, "out": args.out, "updated": data.get("updated")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
