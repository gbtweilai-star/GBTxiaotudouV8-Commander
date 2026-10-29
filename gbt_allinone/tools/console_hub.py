# gbt-capability: console_hub
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""工作台中枢：**所有独立页面的唯一数据源**（主人令 2026-09-28「把所有触手连接全面专业化 3D 可视化…
每个工作流的独立页面需要精细设计排布…必须先全面扫描一遍确保不能遗漏」）。

## 为什么要有这一位（不是"顺手加个接口"）

页面自己编数 = 假绿（本仓最贵的错）。所以规矩是：**页面的每个数字都必须来自这里的一次真实读数**，
而且**读数带口径**（在量什么 / 什么时候 / 哪个文件）。

## 四类数据（对应四个交付物）

| op | 给谁用 | 内容 |
|---|---|---|
| `pages` | 全站导航 + **「不能遗漏」判据** | 全部独立页面清单（现有 9 + 新增），带 workflow/域归属、是否存在、字节数 |
| `graph` | **触手 3D 全景** | 节点（209 能力位 + 30 域）· 边（域→能力、能力→触手绑定）· **运行脉冲**（最近真调用） |
| `widgets` | **Bento 自定义工作台** | 9 种部件的数据（能力分类 / 最近运行 / 健康 / 短板 / 绑定 / 页面 / 工作流 / 审计 / 决策） |
| `layout` | 工作台布局记忆 | `get` / `save`（落 `state/console_layout.json`；页面另有 localStorage 双保险） |

**扫描的"不能遗漏"是机检的**：`scan` 会现读盘上所有页面（含仓根那两个老页），
与本模块登记的清单**双向比对** —— 盘上有而清单没有 = 漏登记；清单有而盘上没有 = 断链。两者都报。

op=pages / graph / widgets / layout / scan / verify / where
"""
from __future__ import annotations

import collections
import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_STATE = _ROOT / "state"
_LAYOUT = _STATE / "console_layout.json"
_LEDGER = _STATE / "console_hub.jsonl"

# ── 页面登记表（**单一真相**；新增页面必须登记在这里，否则 scan 会报"盘上有而清单无"）──
PAGES = [
    # 🔴 2026-10-25 · 补登记两页（此前**盘上有、登记表没有** ⇒ console_hub.verify 报盲区，
    #    test_console_workspace::test_a_no_unregistered_page_on_disk 因此红）：
    #    这两页确实在盘上、也确实有内容（数字人云投射 / 模型云端通道现状），
    #    属于「漏登记」而不是「垃圾残留」⇒ 按单一真相补进来，不删文件。
    {"page": "digital-human", "path": "holo_pet/assets/digital-human/index.html", "kind": "原型",
     "workflow": "media", "what": "数字人云投射到 APP（本地资产 → 云端动作库 → APP 播放）"},
    {"page": "llm", "path": "holo_pet/assets/llm/index.html", "kind": "监控",
     "workflow": "engine", "what": "模型云端通道现状（读面：通道/密钥是否已配，只报状态不动手）"},
    {"page": "console", "path": "holo_pet/assets/console/index.html", "kind": "枢纽",
     "workflow": "全部", "what": "总控台（一体化工作空间骨架 · GBT 品牌：能力矩阵 · 云插件连接器 · 第二大脑 · **编队群**——职业只出本域意见，决策执行只属主脑）"},
    {"page": "home", "path": "holo_pet/assets/home/index.html", "kind": "门面",
     "workflow": "全部", "what": "工作空间首页（统一品牌门面：中央对话框真接面板桥 /api/message · 能力丝带按套件分组 · 运行读数现取）"},
    {"page": "keys", "path": "holo_pet/assets/keys/index.html", "kind": "密钥台",
     "workflow": "security", "what": "密钥台（10 槽位 · **只含掩码** · 零脚本零外链；由 tools/codex-scripts/keys-page.py 重生成）"},
    {"page": "freebuff", "path": "holo_pet/assets/freebuff/index.html", "kind": "执行台",
     "workflow": "programming", "what": "freebuff 对话面板（编程走这个 · 隔离 HOME · 现读状态与命令）"},
    {"page": "gallery", "path": "holo_pet/assets/gallery/index.html", "kind": "枢纽",
     "workflow": "全部", "what": "全部页面卡库（每页一张主视觉 · 一屏看全 · 点卡即开）"},
    {"page": "workbench", "path": "holo_pet/assets/workbench/index.html", "kind": "枢纽",
     "workflow": "全部", "what": "Bento 自定义工作台（9 部件 · 拖拽编排 · 布局记忆）"},
    {"page": "tentacle3d", "path": "holo_pet/assets/tentacle3d/index.html", "kind": "全景",
     "workflow": "全部", "what": "触手 3D 全景（域→能力→绑定 + 运行脉冲）"},
    {"page": "wf-film", "path": "holo_pet/assets/wf-film/index.html", "kind": "工作流",
     "workflow": "film", "what": "电影产线独立页（阶段/判据/近产出）"},
    {"page": "wf-movie", "path": "holo_pet/assets/wf-movie/index.html", "kind": "工作流",
     "workflow": "movie", "what": "成片线独立页"},
    {"page": "wf-music", "path": "holo_pet/assets/wf-music/index.html", "kind": "工作流",
     "workflow": "music", "what": "音乐产线独立页"},
    {"page": "wf-short-video", "path": "holo_pet/assets/wf-short-video/index.html", "kind": "工作流",
     "workflow": "short-video", "what": "短视频产线独立页"},
    {"page": "console3d", "path": "holo_pet/assets/console3d/index.html", "kind": "执行台",
     "workflow": "engine", "what": "3D 大脑执行层（原有）"},
    {"page": "automation", "path": "holo_pet/assets/automation/index.html", "kind": "执行台",
     "workflow": "automation", "what": "自动化面板（原有）"},
    {"page": "structure", "path": "holo_pet/assets/structure/index.html", "kind": "执行台",
     "workflow": "framework", "what": "结构浏览器（原有）"},
    {"page": "godview", "path": "holo_pet/assets/godview/index.html", "kind": "决策台",
     "workflow": "framework", "what": "上帝之眼（原有）"},
    {"page": "health-panel", "path": "holo_pet/assets/health-panel/index.html", "kind": "监控",
     "workflow": "security", "what": "健康面板（安全棒，原有）"},
    {"page": "task-manager", "path": "holo_pet/assets/task-manager/index.html", "kind": "监控",
     "workflow": "system", "what": "任务管理器（原有）"},
    {"page": "music", "path": "holo_pet/assets/music/index.html", "kind": "执行台",
     "workflow": "music", "what": "音乐台（原有）"},
    # ── 扫描抓到的**真盲区**（5 个）：先前谁都不知道它们在盘上，现在登记进来 ──────────
    {"page": "entry", "path": "index.html", "kind": "枢纽",
     "workflow": "全部", "what": "**总入口**（仓根，30KB）"},
    {"page": "media-console", "path": "media-console.html", "kind": "执行台",
     "workflow": "media", "what": "三方向自动化工作流面板（1.3MB）"},
    {"page": "skin-preview", "path": "skin-preview.html", "kind": "门面",
     "workflow": "design", "what": "仙侠×科技 皮肤预览"},
    {"page": "v22-prototype", "path": "V22 GBT小土豆V8-可交互原型.html", "kind": "原型",
     "workflow": "design", "what": "能力中枢·可交互原型（V21/V22）"},
    {"page": "v22-canvas", "path": "V22 GBT小土豆V8-无限画布.html", "kind": "原型",
     "workflow": "design", "what": "能力中枢·无限画布（V21/V22）"},
    # 仓根两个老页：**扫描抓到的漏项**，登记进来（不再是"没人知道的页面"）
    {"page": "brain", "path": "brain.html", "kind": "执行台",
     "workflow": "engine", "what": "大脑执行层（仓根老页，2026-09-13 前）"},
    {"page": "capabilities", "path": "capabilities.html", "kind": "全景",
     "workflow": "framework", "what": "能力球（仓根老页，2026-09-13 前）"},
]

WORKFLOWS = {
    "film": {"label": "电影产线", "dir": "projects/film",
             "stages": ["01-剧本", "02-分镜", "03-拍摄", "04-素材", "05-剪辑", "06-成片"],
             "caps": ["filmkit", "actioncam", "beatgrid", "filmgrade", "film_intel", "video"]},
    "movie": {"label": "成片线", "dir": "projects/movie",
              "stages": ["产线", "成片", "交付"], "caps": ["filmkit", "filmgrade", "deliver_check"]},
    "music": {"label": "音乐产线", "dir": "projects/music",
              "stages": ["01-作词", "02-作曲", "03-编曲", "04-混音", "05-母带", "06-发行"],
              "caps": ["music", "voice", "beatgrid"]},
    "short-video": {"label": "短视频产线", "dir": "projects/short-video",
                    "stages": ["01-script", "02-storyboard", "03-raw", "04-cut", "05-publish"],
                    "caps": ["shortvideo", "video", "one_shot", "actioncam"]},
}


def _load(rel: str, default):
    p = _STATE / rel
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return default
    return default


def _caps() -> dict:
    sys.path.insert(0, str(_ROOT))
    from gbt_allinone.caps_registry import BENIGN_CAPS
    return dict(BENIGN_CAPS)


def _log(row: dict) -> None:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row}, ensure_ascii=False) + "\n")


def _exists(rel: str) -> tuple:
    p = _ROOT / rel
    if not p.is_file():
        return False, 0
    return True, p.stat().st_size


def pages(**_kw) -> dict:
    """全部独立页面（**单一真相**）+ 盘上是否存在 + workflow 归属。"""
    rows = []
    for spec in PAGES:
        ok, size = _exists(spec["path"])
        rows.append({**spec, "exists": ok, "bytes": size, "kb": round(size / 1024, 1)})
    by_kind = collections.Counter(r["kind"] for r in rows)
    by_wf = collections.Counter(r["workflow"] for r in rows)
    return {"ok": True, "op": "pages", "count": len(rows), "rows": rows,
            "by_kind": dict(by_kind), "by_workflow": dict(by_wf),
            "missing": [r["path"] for r in rows if not r["exists"]],
            "_口径": "登记表 = 单一真相；scan 会拿它跟盘上现读双向比对"}


def scan(**_kw) -> dict:
    """**不能遗漏**的机检：盘上现读 vs 登记表，双向比对。"""
    on_disk = []
    for base, pat in (("holo_pet/assets", "*/index.html"), (".", "*.html")):
        d = _ROOT / base
        if d.is_dir():
            for p in sorted(d.glob(pat)):
                if p.is_file():
                    on_disk.append(str(p.relative_to(_ROOT)).replace("\\", "/"))
    on_disk = [x for x in on_disk if not x.startswith(("out/", "delivery/", "agent-", "_upstream/"))]
    reg = {p["path"] for p in PAGES}
    unregistered = sorted(set(on_disk) - reg)     # 盘上有、清单没有 ⇒ **漏登记（盲区）**
    broken = sorted(reg - set(on_disk))           # 清单有、盘上没有 ⇒ 断链（或还没建）
    return {"ok": not unregistered, "op": "scan",
            "on_disk": len(on_disk), "registered": len(reg),
            "unregistered": unregistered, "broken": broken,
            "note": ("`broken` 里是**登记了但还没建**的页面（本轮要建的就是它们）；"
                     "`unregistered` 才是真盲区 —— 它为 0 才算「不能遗漏」达标"),
            "_口径": "盘上现读 = holo_pet/assets/*/index.html + 仓根 *.html（排除生成物/交付物）"}


def graph(**_kw) -> dict:
    """3D 全景数据：域节点 + 能力节点 + 边 + **运行脉冲**（最近真调用，来自台账尾）。"""
    caps = _caps()
    doms = collections.Counter(str(v.get("domain")) for v in caps.values())
    nodes, edges = [], []
    # ① 域节点（外环）与能力节点（域内）
    for i, (d, n) in enumerate(sorted(doms.items())):
        nodes.append({"id": "domain:" + d, "type": "domain", "label": d, "size": n,
                      "ring": 0})
    for kind, spec in caps.items():
        d = str(spec.get("domain"))
        nodes.append({"id": "cap:" + kind, "type": "cap", "label": kind, "domain": d,
                      "safe": bool(spec.get("safe")), "ring": 1})
        edges.append({"from": "domain:" + d, "to": "cap:" + kind, "kind": "member", "w": 1})
    # ② 能力→触手绑定（按"能力位实现文件 ↔ 触手"这类绑定聚合；不把 6470 条全画出来，聚合到能力级）
    bind = _load("asset_bindings.json", {}) or {}
    per_cap = collections.Counter()
    for asset, row in bind.items():
        for t in ((row or {}).get("tentacles") or []):
            if t in caps:
                per_cap[t] += 1
    for k, n in per_cap.most_common(400):
        edges.append({"from": "cap:" + k, "to": "cap:" + k, "kind": "self", "w": n})
    # ③ 运行脉冲：台账尾部的真调用（近窗口）
    pulses, now = [], time.time()
    for name in ("asset_bindings.jsonl", "control_loop.jsonl", "action_gate.jsonl",
                 "gods_eye_decisions.jsonl", "console_hub.jsonl", "code_audit.jsonl",
                 "agent_console.jsonl", "obsidian_memory.jsonl"):
        p = _STATE / name
        if not p.is_file():
            continue
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines()[-6:]:
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            ev = str(r.get("event") or r.get("op") or "")
            if ev:
                pulses.append({"ledger": name, "event": ev, "at": r.get("at", ""),
                               "age_s": None})
    return {"ok": True, "op": "graph", "nodes": nodes, "edges": edges,
            "counts": {"domains": len(doms), "caps": len(caps),
                       "member_edges": len(caps),
                       "binding_weight": sum(per_cap.values()), "pulses": len(pulses)},
            "pulses": pulses[-12:],
            "_口径": "节点=注册表现读；绑定边=绑定账按能力聚合；脉冲=各台账尾部真记录（不是动画装饰）"}


def widgets(**_kw) -> dict:
    """Bento 九种部件的数据（每个数都带来源）。"""
    caps = _caps()
    doms = collections.Counter(str(v.get("domain")) for v in caps.values())
    health = _load("health.json", {}) or {}
    board = _load("shortboard.json", {}) or {}
    bind = _load("asset_bindings.json", {}) or {}
    tags = _load("cap_tags.json", {}) or {}
    audit = _load("code_audit_findings.json", {}) or {}
    decisions = []
    dp = _STATE / "gods_eye_decisions.jsonl"
    if dp.is_file():
        for ln in dp.read_text(encoding="utf-8", errors="replace").splitlines()[-3:]:
            try:
                decisions.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    wf = {}
    for key, spec in WORKFLOWS.items():
        d = _ROOT / spec["dir"]
        files = [p for p in d.rglob("*") if p.is_file()] if d.is_dir() else []
        newest = max((p.stat().st_mtime for p in files), default=0)
        wf[key] = {"label": spec["label"], "dir": spec["dir"], "files": len(files),
                   "stages": spec["stages"],
                   "newest_h": round((time.time() - newest) / 3600, 1) if newest else None}
    return {"ok": True, "op": "widgets", "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "w1_caps": {"total": len(caps), "domains": len(doms),
                        "top": dict(doms.most_common(8)), "src": "caps_registry 现读"},
            "w2_pages": {"total": len(PAGES),
                         "exists": sum(1 for p in PAGES if _exists(p["path"])[0]),
                         "src": "console_hub.pages"},
            "w3_bindings": {"assets": len(bind),
                            "src": "state/asset_bindings.json"},
            "w4_health": {"ok": health.get("ok"), "alerts": len(health.get("alerts") or []),
                          "at": health.get("at"), "src": "state/health.json"},
            "w5_shortboard": {"count": board.get("count"),
                              "top": [{"dim": x.get("dim"), "what": str(x.get("what"))[:60],
                                       "src": x.get("src")} for x in (board.get("top") or [])[:3]],
                              "src": "state/shortboard.json"},
            "w6_permits": {"owner_class": sum(1 for v in (tags.get("tags") or {}).values()
                                              if v.get("permission") == "owner"),
                           "total_tags": tags.get("count"), "src": "state/cap_tags.json"},
            "w7_audit": {"findings": len(audit.get("findings") or []),
                         "needs_human": len(audit.get("needs_human") or []),
                         "src": "state/code_audit_findings.json"},
            "w8_workflows": {"items": wf, "src": "projects/* 现读（文件数 + 最新改动时龄）"},
            "w9_decisions": {"recent": [{"choice": d.get("choice"), "path": d.get("path"),
                                         "decider": d.get("decider")} for d in decisions],
                             "src": "state/gods_eye_decisions.jsonl"},
            "_口径": "九个部件九个数；**每个都带 src**（页面上要显示来源，不许匿名数字）"}


def layout(layout_json: str = "", **_kw) -> dict:
    """布局记忆：get（读）/ save（写；`layout_json` 给 JSON 数组）。"""
    if not layout_json.strip():
        return {"ok": True, "op": "layout.get", "layout": _load("console_layout.json", {"items": []}),
                "note": "页面另有 localStorage 双保险（离线可用）"}
    try:
        items = json.loads(layout_json)
    except json.JSONDecodeError as exc:
        return {"ok": False, "op": "layout.save", "error": f"layout_json 不是合法 JSON：{exc}"}
    if not isinstance(items, list):
        return {"ok": False, "op": "layout.save", "error": "layout_json 要是数组（部件顺序表）"}
    doc = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "items": items[:64]}
    tmp = _LAYOUT.with_name(_LAYOUT.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, _LAYOUT)
    _log({"event": "layout.save", "items": len(doc["items"])})
    return {"ok": True, "op": "layout.save", "items": len(doc["items"]),
            "file": str(_LAYOUT.relative_to(_ROOT))}


def verify(**_kw) -> dict:
    problems = []
    s = scan()
    if s["unregistered"]:
        problems.append(f"**盘上有却没登记的页面**（盲区）：{s['unregistered'][:5]}")
    # 每个登记页要么在盘上，要么在"本轮要建"的清单里 —— 这里只要求归属字段齐
    for p in PAGES:
        if not p.get("workflow") or not p.get("kind"):
            problems.append(f"{p['page']} 缺归属（workflow/kind）⇒ 分类不全")
    if len({p["page"] for p in PAGES}) != len(PAGES):
        problems.append("页面名有重复")
    g = graph()
    if g["counts"]["caps"] < 200:
        problems.append(f"3D 图的能力节点只有 {g['counts']['caps']} 个 ⇒ 数据源不对")
    w = widgets()
    for k in list(w):
        if k.startswith("w") and not (w[k] or {}).get("src"):
            problems.append(f"部件 {k} 没有来源 ⇒ 匿名数字不许上页")
    return {"ok": not problems, "op": "verify", "problems": problems,
            "counts": {"pages": len(PAGES), "registered_exists": s["registered"] - len(s["broken"]),
                       "graph_caps": g["counts"]["caps"], "pulses": g["counts"]["pulses"]},
            "_口径": "无盲区（盘上有必登记）· 每页有归属 · 图能力节点数对得上 · 部件都带 src"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "console_hub", "tentacle": "console_hub",
            "entry": "run_task('console_hub', {...})",
            "ops": ["pages", "graph", "widgets", "layout", "scan", "verify", "where"],
            "consumers": ["holo_pet/assets/workbench（Bento 工作台）",
                          "holo_pet/assets/tentacle3d（3D 全景）",
                          "holo_pet/assets/wf-*（每工作流独立页）"],
            "files": {"页面登记": "console_hub.PAGES", "布局记忆": str(_LAYOUT.relative_to(_ROOT)),
                      "台账": str(_LEDGER.relative_to(_ROOT))},
            "hard_rules": ["页面不许自己编数：每个数字来自这里的一次真读数，且带 src",
                           "「不能遗漏」机检：scan 双向比对，unregistered 必须为 0"]}


def run_op(op: str = "pages", **params) -> dict:
    op = (op or "pages").lower()
    for name, fn in (("pages", pages), ("graph", graph), ("widgets", widgets),
                     ("layout", layout), ("scan", scan), ("verify", verify), ("where", where)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（pages/graph/widgets/layout/scan/verify/where）"}
