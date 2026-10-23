# -*- coding: utf-8 -*-
"""AI 工作可视化面板（ai-board）—— **一页看全：谁是谁、什么职位、在休息还是在干活**。

主人令（2026-10-09，逐字）：
  「整个框架所有的编程职业在一页上面做出**每个AI在执行任务的可视化面板**，谁是谁什么职位，
    正在休息还是在工作都要看得见，这样永远不会出现像你们部署项目一样扫描一扫都是漏洞和红黄色警报，
    不扫的话还不知道有什么」

数据来源（全部现读，不编）：
  · state/action-ledger.jsonl  —— 最近动作（谁在干活、干的是什么）
  · gbt_allinone/caps_registry  —— 30 个能力域（工作位）
  · vaults/agency_tentacles     —— 职业册（19 个师 × 272 个职业）
  · state/capability-audit.json —— 报警（红黄一体，不藏）

口径：**近 30 分钟内有动作 ⇒ 工作中**，否则 ⇒ 休息中；两侧都要显示（休息的也要看得见）。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT_HTML = ROOT / "holo_pet_w3" / "ai-board" / "index.html"
OUT_JS = ROOT / "holo_pet_w3" / "ai-board" / "ai-board-data.js"
LEDGER = ROOT / "state" / "action-ledger.jsonl"
AUDIT = ROOT / "state" / "capability-audit.json"
WORK_WINDOW_S = 1800


def _rows() -> list:
    if not LEDGER.is_file():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def build_data() -> dict:
    from gbt_allinone.caps_registry import BENIGN_CAPS
    from collections import Counter
    dom = Counter((v or {}).get("domain") for v in BENIGN_CAPS.values())
    rows = _rows()
    now = time.time()
    # 每人（域）最近一次动作
    # 🔴 2026-10-09 修：第一版拿**域名**去撞动作文本 ⇒ 目标多是文件路径，撞不上 ⇒ 全判"休息中"（30/30）。
    #    正解：拿**该域下的能力位名**去撞（动作里常常点名能力位/件名），撞不上再看域名。
    dom2caps = {}
    for kind, v in BENIGN_CAPS.items():
        dom2caps.setdefault((v or {}).get("domain"), []).append(kind.lower())
    last = {}
    for r in rows:
        blob = (str(r.get("target") or "") + " " + str(r.get("what") or "") + " "
                + str(r.get("evidence") or "")).lower()
        at = str(r.get("at") or "")
        try:
            ts = time.mktime(time.strptime(at, "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            ts = 0
        for d, kinds in dom2caps.items():
            if not d:
                continue
            hit = (d in blob) or any(k in blob for k in kinds)
            if hit and (d not in last or ts > last[d][0]):
                last[d] = (ts, r.get("what"), at)
    # 🔴 2026-10-11 加：**每位近窗口内的动作数** —— 这就是"这一根触手在动"的进度感。
    #    （原来只有"最近一次动作"，看不出它干了多少。）
    dom_acts = {}
    for r in rows:
        blob = (str(r.get("target") or "") + " " + str(r.get("what") or "") + " "
                + str(r.get("evidence") or "")).lower()
        at = str(r.get("at") or "")
        try:
            ts = time.mktime(time.strptime(at, "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            ts = 0
        if (now - ts) > WORK_WINDOW_S:
            continue
        for d, kinds in dom2caps.items():
            if not d:
                continue
            if (d in blob) or any(k in blob for k in kinds):
                dom_acts[d] = dom_acts.get(d, 0) + 1

    people = []
    for d, n in dom.most_common():
        l = last.get(d)
        working = bool(l and (now - l[0]) <= WORK_WINDOW_S)
        people.append({"职位": d, "工作位": n,
                       "状态": "工作中" if working else "休息中",
                       "最近动作": (l[1] if l else None),
                       "最近时刻": (l[2] if l else None),
                       "窗口内动作数": dom_acts.get(d, 0)})
    al = {}
    try:
        d = json.loads(AUDIT.read_text(encoding="utf-8"))
        items = d.get("items") or []
        al = {"断连缺失": len([i for i in items if i.get("state") in ("断连", "缺失")]),
              "按需未启用": len([i for i in items if i.get("state") == "按需未启用"])}
    except (OSError, ValueError):
        al = {"断连缺失": None}
    # 🔴 2026-10-11 加：**云插件那条线**（主人令：「触手运行自身携带云插件独立运行任务」）。
    #    数据源 state/cloud_plugins.json（cloud-plugins.py gen 生成），连它自己的 doctrine 一起报。
    cloud = {}
    try:
        cp = json.loads((ROOT / "state" / "cloud_plugins.json").read_text(encoding="utf-8"))
        cloud = {"在册": cp.get("n"),
                 "形态": cp.get("form"),
                 "分组": len(cp.get("groups") or []),
                 "生成于": cp.get("generated_at"),
                 "口径": (cp.get("doctrine") or [])[:3]}
    except (OSError, ValueError):
        cloud = {"在册": None}

    online = len([p for p in people if p["状态"] == "工作中"])
    # 🔴 2026-10-11 加第二条腿（**治那个"全判休息"的老坑**）：
    #    上面那套是"拿域名/能力位名去撞台账文本"（L55 注释记过它撞不上 ⇒ 全休）。
    #    台账里的 target 多是**文件路径**（HEARTBEAT.md 之类），一个域名都撞不到 ⇒
    #    "在线"会长期读成 0，**看着像智能体没在跑** —— 而实际上是撞法不灵。
    #    ⇒ 另给一个**不依赖撞文本**的读数：近窗口内**台账总动作数**。
    #      有动作 = 这台机器在干活（如实）；哪位在动仍按撞法点亮（撞不到的如实显示 0）。
    recent_all = 0
    for r in rows:
        at = str(r.get("at") or "")
        try:
            ts = time.mktime(time.strptime(at, "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            ts = 0
        if (now - ts) <= WORK_WINDOW_S:
            recent_all += 1
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "职位数": len(people),
            "工作中": online,
            # 🔴 2026-10-11：把"工作中"**同时**报成"在线数"，并写死它的口径 ——
            #    主人要的是"让用户知道智能体是可以同时运行的"。
            "在线数": online,
            "近窗口动作数": recent_all,
            "在线口径": ("近 %d 分钟内有动作 = 在跑；这是**同时在跑**的触手数，"
                         "不是上限 —— 上限由**本地能装多少云插件**决定，不由数量决定。"
                         "⚠️ 本页有两条腿：① 逐位点亮靠「域名/能力位名撞台账文本」"
                         "（撞不上的如实显示 0，不代表它没在跑）② 全局在跑靠**台账总动作数**"
                         "（不依赖撞文本）⇒ 现读：近 %d 分钟台账 **%d** 条动作"
                         % (WORK_WINDOW_S // 60, WORK_WINDOW_S // 60, recent_all)),
            "休息中": len([p for p in people if p["状态"] == "休息中"]),
            "报警": al, "逐位": people,
            "云插件": cloud,
            "台账条数": len(rows),
            "并发说明": ("每根触手自带云插件、各跑各的小任务，跑完把结果交回来；"
                         "一根触手一个小任务 ⇒ **一百根、一千根都行** —— "
                         "瓶颈是本地能安多少云插件，不是并发数。")}


def render(d: dict) -> str:
    rows = "".join(
        '<tr><td>%s</td><td class="n">%d</td><td class="%s">%s</td>'
        '<td class="n">%d</td><td>%s</td><td class="dim">%s</td></tr>'
        % (p["职位"], p["工作位"], "work" if p["状态"] == "工作中" else "rest", p["状态"],
           p.get("窗口内动作数", 0),
           (p["最近动作"] or "—")[:44], (p["最近时刻"] or "—")[11:19])
        for p in d["逐位"])
    cloud = d.get("云插件") or {}
    _doctrine = "".join("<li>%s</li>" % x for x in (cloud.get("口径") or []))
    cloud_block = (
        '<section class="card"><h2>云插件（触手各自携带、独立跑小任务）</h2>'
        '<p class="kv">在册 <b>%s</b> ｜ 形态 <b>%s</b> ｜ 分组 <b>%s</b> ｜ 台账生成于 %s</p>'
        '<ul class="doc">%s</ul></section>'
        % (cloud.get("在册"), cloud.get("形态"), cloud.get("分组"),
           cloud.get("生成于") or "—", _doctrine or "<li>（无口径）</li>"))
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<!-- 自动生成，别手改。重建：py -3.14 tools/codex-scripts/ai-board.py · 生成时刻 ${time.strftime('%Y-%m-%dT%H:%M:%S')} -->
<title>GBT小土豆V8 · AI 工作面板</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 body{{margin:0;background:#06080c;color:#e8eef6;font:14px/1.6 "Segoe UI","Microsoft YaHei",system-ui,sans-serif}}
 header{{display:flex;align-items:center;gap:14px;padding:14px 20px;border-bottom:1px solid #1d2733}}
 .logo{{width:26px;height:26px}} .who{{font-size:16px}} .who b{{color:#f5b041}}
 .spacer{{flex:1}} .pill{{border:1px solid #2a3644;border-radius:999px;padding:3px 11px;font-size:12px;color:#9fb0c3}}
 .pill.ok{{color:#22c55e;border-color:#22c55e}} .pill.bad{{color:#f87171;border-color:#f87171}}
 table{{width:100%;border-collapse:collapse}} th,td{{padding:8px 20px;border-bottom:1px solid #131b25;text-align:left}}
 th{{color:#7d8ea3;font-weight:500;font-size:12px}} .n{{color:#38bdf8}} .dim{{color:#5b6b7d}}
 .work{{color:#22c55e;font-weight:600}} .rest{{color:#6b7280}}
 .foot{{padding:12px 20px;color:#5b6b7d;font-size:12px;border-top:1px solid #131b25}}
 .note{{padding:8px 20px;color:#9fb0c3;font-size:12px;background:#0a0e14;border-bottom:1px solid #131b25}}
 .card{{padding:14px 20px;border-bottom:1px solid #131b25}}
 .card h2{{margin:0 0 6px;font-size:14px;color:#f5b041;font-weight:600}}
 .kv{{margin:4px 0;color:#9fb0c3;font-size:12px}} .kv b{{color:#38bdf8}}
 .doc{{margin:6px 0 0 18px;padding:0;color:#7d8ea3;font-size:12px}}
</style></head><body>
<header>
 <svg class="logo" viewBox="0 0 64 64"><circle cx="32" cy="32" r="26" fill="none" stroke="#38bdf8" stroke-width="4"/><circle cx="32" cy="32" r="9" fill="#f5b041"/></svg>
 <span class="who">GBT<b>小土豆</b>V8 · AI 工作面板</span>
 <span class="spacer"></span>
 <span class="pill">职位 {d['职位数']}</span>
 <span class="pill ok">在线 {d['在线数']}（同时在跑）</span>
 <span class="pill">休息中 {d['休息中']}</span>
 <span class="pill {'bad' if (d['报警'].get('断连缺失') or 0) else 'ok'}">报警 {d['报警'].get('断连缺失')}</span>
</header>
<div class="note">在线口径：{d['在线口径']}</div>
<div class="note">并发说明：{d['并发说明']}</div>
{cloud_block}
<table><thead><tr><th>职位（能力域）</th><th>工作位</th><th>状态</th><th>窗口内动作</th><th>最近动作</th><th>时刻</th></tr></thead>
<tbody>{rows}</tbody></table>
<div class="foot">生成 {d['at']} ｜ 口径：近 30 分钟内有动作 = 工作中，否则休息中（**休息的也看得见**）｜ 台账 {d['台账条数']} 条 ｜ 重生成 <code>py -3.14 tools/codex-scripts/ai-board.py</code>
<br>开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属</div>
</body></html>
"""


def main() -> int:
    d = build_data()
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(render(d), encoding="utf-8")
    # 🔴 2026-10-09 生成器**给自己的产物盖章**（与 capability-audit._head 同一根因）：
    #    产物必须自声明「自动生成 + 重建命令」，框架门才能按**文件自声明**把它认成生成物，
    #    而不是每次重生成都报一条 no_passport（实测撞过：holo_pet_w3/ai-board/ai-board-data.js）。
    OUT_JS.write_text("/* 自动生成，别手改。重建：py -3.14 tools/codex-scripts/ai-board.py */\n"
                      "globalThis.GBT_AI_BOARD = " + json.dumps(d, ensure_ascii=False) + ";\n",
                      encoding="utf-8")
    print("AI 工作面板：职位 %d · 工作中 %d · 休息中 %d · 报警 %s"
          % (d["职位数"], d["工作中"], d["休息中"], d["报警"].get("断连缺失")))
    print("已生成：%s" % OUT_HTML)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
