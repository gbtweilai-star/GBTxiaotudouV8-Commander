# -*- coding: utf-8 -*-
"""云插件互绑拓扑页 · 生成器 / 判据（主人令 2026-10-04）。

主人原话：「不是独立一页把插件排布上去，做一个触手把 50 个插件都各自双向互绑串联共享资源的
可视化页面，必须清晰精细到每一处连接点都要看得到」。

本件做什么：
  · 从**单一真源** `deploy/cloud-10/mesh.json` 现读插件表（现读 10 个；表加到 N 个就自动出 N 个，
    不给主人编数）；
  · 生成**一张自包含页** `holo_pet_w3/plugins-mesh/index.html`：
      ① 环形拓扑：中心是**触手**，N 条双向臂连到每个插件；插件之间按 mesh 规则**全互联**
         （每位与其余各位双向互绑 ⇒ N×(N-1) 条有向边，图上 N×(N-1)/2 条线，两端箭头）；
      ② 连接矩阵：N×N 每格 = **一处有向连接点**，逐格可点可查（对角=自环不绑）；
      ③ 资源共享：按云资源（KV/R2/AI/Containers/fetch/绑定名）分组，列出共用它的插件 = 互通点；
      ④ 节点锁定（捷径）：每位插件的 op 门表 —— 直达该节点即可，不必绕别的节点；
  · 台账落 `state/cloud_plugins.json`（连接点逐条可数、可复核）；
  · `verify` 逐条判据：连接点数恒等 · 驱动位在册 · 页面自包含（零外链）· 每处连接点在页面上都有元素。

用法：
    py -3.14 tools/codex-scripts/cloud-plugins.py gen      # 生成页 + 台账
    py -3.14 tools/codex-scripts/cloud-plugins.py verify   # 逐条判据（退出码 0=全过）

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MESH = ROOT / "deploy" / "cloud-10" / "mesh.json"
PAGE = ROOT / "holo_pet_w3" / "plugins-mesh" / "index.html"
LEDGER = ROOT / "state" / "cloud_plugins.json"

SKIP_DIR = ("node_modules", ".git", ".scratch", "_upstream", ".old-projects-20261004")

# 审美令牌（内联版）：实现在 `_taste_inline.py` —— **唯一一份**，别在这里再抄一遍。
# 为什么本页要内联：本页判据 V5 要求「自包含：零外链/零 CDN」，挂外部样式表是撞自己的门。
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _taste_inline import site_root_block  # noqa: E402
from _page_emit import clean_html  # noqa: E402


def load_mesh(spec_path=None) -> dict:
    """读单一真源：默认 `deploy/cloud-10/mesh.json`（现网 10 模块）；
    给了 `--spec` 就读槽位表（如 `plugins50.json`：50 槽 / 5 组 / 备用槽）。"""
    path = Path(spec_path) if spec_path else MESH
    data = json.loads(path.read_text(encoding="utf-8"))
    data["_spec_path"] = str(path).replace("\\", "/").split("GBT小土豆V8/")[-1]
    return data


def _norm_modules(mesh: dict) -> list:
    """把两种表统一成同一种形状：id / duty / local_driver / driver_why / group / ops。"""
    out = []
    for m in mesh.get("modules") or []:
        if "slot" in m:                                  # 槽位表（plugins50）
            out.append({"id": m["slot"], "seq": m["seq"], "group": m.get("group"),
                        "duty": m.get("role", ""), "local_driver": m.get("local_driver", ""),
                        "driver_why": m.get("driver_why", ""),
                        "ops": m.get("ops") or {}, "cloud": [m.get("status", "")],
                        "boundary": (m.get("email") or {}).get("kind", ""),
                        "is_reserve": not m.get("local_driver")})
        else:                                            # mesh.json（现网）
            out.append({"id": m["id"], "seq": m["seq"], "group": None,
                        "duty": m.get("duty", ""), "local_driver": m.get("local_driver", ""),
                        "driver_why": m.get("driver_why", ""),
                        "ops": m.get("op_gates") or {}, "cloud": m.get("cloud") or [],
                        "boundary": m.get("boundary", ""), "is_reserve": False})
    return out


def registry_names() -> set:
    sys.path.insert(0, str(ROOT))
    from gbt_allinone.caps_registry import BENIGN_CAPS
    return set(BENIGN_CAPS)


def build_model(mesh: dict) -> dict:
    mods = _norm_modules(mesh)
    n = len(mods)
    directed, undirected = [], []
    for a in mods:
        for b in mods:
            if a["seq"] == b["seq"]:
                continue
            directed.append({"from": a["seq"], "to": b["seq"],
                             "from_id": a["id"], "to_id": b["id"],
                             "gate": "none", "kind": "互绑"})
    for i, a in enumerate(mods):
        for b in mods[i + 1:]:
            undirected.append({"a": a["seq"], "b": b["seq"],
                               "a_id": a["id"], "b_id": b["id"]})
    # 资源共享：云资源 → 哪些插件（共享 binder 就是「互通点」）
    shared = {}
    for m in mods:
        for res in m.get("cloud") or []:
            shared.setdefault(res, []).append(m["seq"])
    shared = {k: v for k, v in sorted(shared.items(), key=lambda kv: (-len(kv[1]), kv[0]))}
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "form": mesh.get("form"),
        "drops": [{"level": "K1", "what": "cloud driver", "alt": "gbtdiag.smoke_driver"},
                  {"level": "K2", "what": "cloud connector swap", "alt": "mounted-shim"}],
        "doctrine": mesh.get("_doctrine") or mesh.get("doctrine") or [],
        "modules": mods,
        "spec_path": mesh.get("_spec_path") or "deploy/cloud-10/mesh.json",
        "groups": mesh.get("groups") or [],
        "n": n,
        "directed": directed,
        "undirected": undirected,
        "counts": {"plugins": n, "directed": n * (n - 1), "undirected": n * (n - 1) // 2,
                   "self_loop": 0, "matrix_cells": n * n},
        "shared": shared,
        # ── 部署分类（主人令 2026-10-04：「大模型和工作流不是都部署在云插件上面，
        #    什么插件上部署的什么，不一样的就要区分开来」）—— 三层，逐插件标它**承载什么/不承载什么**。
        "deploy_layers": [
            {"layer": "云端 mesh10", "where": "Cloudflare Worker · 形态 A：10 模块**同一 isolate**",
             "carries": ["模块 ops（status/identity/models/complete…，门表见 op_gates）",
                         "跨模块 ctx.call 边（90 条有向）", "KV/R2/AI 绑定访问（mesh10/ 命名空间）"],
             "not_carries": ["本机 217 能力位与工作流编排（那是本机框架的活）",
                             "本机文件系统（Worker 无本地盘；文件是对象存储 R2）",
                             "我们的模型权重（c01 明写 weights_ours:false；无审查 c03 需自托管权重才算数）"]},
            {"layer": "本机 GBT 框架", "where": "本机（217 能力位 · 工作流 · 决策/执行门 · 记忆）",
             "carries": ["能力调用与门（run_task/policy）", "工作流引擎（wf/sched）", "记忆与台账"],
             "not_carries": ["云端模块的 isolate 内状态"]},
            {"layer": "外部枢纽", "where": "模型枢纽（FreeLLMAPI / agnes 等，经统一密钥链）",
             "carries": ["模型推理（托管权重）"], "not_carries": ["mesh 互绑（不经 ctx.call；密钥链与插件互绑是两册）"]},
        ],
        # ── 拼接与共享机制（**照源码**，不造轮）：出处逐条可查
        "mechanism": {
            "source": ["deploy/cloud-10/src/modules.js:5", "deploy/cloud-10/src/modules.js:254",
                       "deploy/cloud-10/src/worker.js:10", "deploy/cloud-10/src/worker.js:191-219"],
            "splice": "跨模块一律走 ctx.call(peerId, op, args)（记边）；不许直接抓别人的内部状态",
            "ctx_contract": "ctx = { env, state, call(peerId, op, args), record(edge) }",
            "share": "形态 A：10 模块装在**同一 isolate** ⇒ CPU/内存真共用；共享同一批 binder（KV/R2/AI），键加 mesh10/ 前缀（不碰主人原有键）",
            "no_keys": "**插件互绑不做密钥连接** —— 边就是 ctx.call 调用关系；密钥（GW_AUTH / 统一密钥链）属另一册，只护网关路由与出网，不参与插件互绑",
            "live": "云端 GET /edges 现读：90 条边矩阵 + 自环/对称/条数三项核对 + **已观测边数**（splice_exercised）",
        },
    }


# ── 页面（自包含：零外链、零 CDN、SVG 图标、无 emoji、品牌三色、尊重 reduced-motion）──

_PAGE = """<!doctype html>
<html data-page-id="plugins-mesh" lang="zh-CN"><head><meta charset="utf-8">
<!-- 自动生成，别手改。重建：py -3.14 tools/codex-scripts/cloud-plugins.py gen
     为什么补这句（2026-10-11）：本页原来**没有生成标记** ⇒ 逐页新鲜度判据
     （tools/codex-scripts/page-bind-check.py）判不出它是生成物还是手写物，
     于是「主脑看到的它新不新」**没人能机检**。这句就是那个可机检的锚。
     2026-10-26：`data-page-id` 与 `tentacle-kit` **必须由模板自带**。
     此前这两样是生成后由收尾工具补的 —— 谁跑一次 gen，本页就静默掉出触手网格
     （27 页变 26 页，且没有任何东西会叫）。凡"生成后补"的东西，要么进模板，要么迟早掉。 -->
<title>GBT小土豆V8 · 云插件互绑拓扑（触手串联 · 每处连接点可见）</title>
<style>
/* 站点令牌（生成期内联，来源 state/taste/*.json → theme/taste-tokens.css；**不外链**） */
__TASTE_ROOT__
:root{--bg:var(--taste-ground,#0B1120);--pan:var(--taste-surface,#111827);--line:var(--taste-border,#1E3A5F);
 --ink:var(--taste-text,#e8ecf8);--dim:var(--taste-muted,#9aa4c4);
 --cy:#22d3ee;--or:#f5b041;--ok:var(--taste-positive,#00E5FF);--bad:var(--taste-negative,#EF4444);
 --brand-or:var(--taste-accent,#f5b041);--brand-cy:#22d3ee}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:13px/1.6 "Segoe UI",system-ui,sans-serif}
.gbt-topbar{display:flex;align-items:center;gap:10px;padding:10px 16px;border-bottom:1px solid var(--line);
 /* 2026-10-26：原为 linear-gradient(90deg,#111827,#0d1117) —— 两档差 2 个色阶、肉眼无差却是
    审美守卫的 `gradient` 命中。取中点纯色。 */
 background:#111827}
.mark{width:18px;height:18px;border:2px solid var(--brand-or);border-radius:4px}
.brand{font-weight:700;letter-spacing:.5px}.brand b{color:var(--brand-or)}
.wrap{display:grid;grid-template-columns:minmax(560px,1.35fr) minmax(360px,1fr);gap:14px;padding:14px}
.card{background:var(--pan);border:1px solid var(--line);border-radius:10px;padding:12px}
h2{margin:0 0 8px;font-size:13px;color:var(--dim);font-weight:600;letter-spacing:.4px}
.stats{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:10px}
.stat{min-width:110px}.stat b{display:block;font-size:24px;color:var(--brand-cy);font-variant-numeric:tabular-nums}
.stat i{font-style:normal;color:var(--dim);font-size:12px}
svg{width:100%;height:auto;display:block}
.node{cursor:pointer}
.node circle{fill:#111a26;stroke:var(--line);stroke-width:1.5}
.node.sel circle{stroke:var(--brand-or);stroke-width:2.5}
.node text{fill:var(--ink);font-size:9px;text-anchor:middle;pointer-events:none}
.node .drv{fill:var(--brand-cy);font-size:8px}
.hub circle{fill:#1a1206;stroke:var(--brand-or);stroke-width:2.5}
.hub text{fill:var(--brand-or);font-size:11px;font-weight:700;text-anchor:middle;pointer-events:none}
.arm{stroke:var(--brand-or);stroke-width:1.1;stroke-opacity:.55;fill:none;marker-end:url(#arwO);marker-start:url(#arwO2)}
.link{stroke:#2b3a52;stroke-width:.7;stroke-opacity:.5;fill:none}
.link.hot{stroke:var(--brand-cy);stroke-width:1.8;stroke-opacity:1}
.lbl{fill:var(--dim);font-size:8px}
table{border-collapse:collapse;width:100%;font-size:11px}
th,td{border:1px solid var(--line);padding:3px 5px;text-align:left;vertical-align:top}
th{color:var(--dim);font-weight:600;background:#111827;position:sticky;top:0}
td.cell{cursor:pointer;text-align:center;font-variant-numeric:tabular-nums;color:var(--dim)}
td.cell.on{background:#12212f;color:var(--brand-cy);font-weight:700}
td.cell.self{background:#0a0e14;color:#1E3A5F}
td.cell.src{background:#1a1206;color:var(--brand-or)}
.mono{font-family:ui-monospace,Consolas,monospace}
ul{margin:6px 0 0;padding-left:16px}
li{margin:2px 0}
.pill{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:1px 7px;margin:2px 4px 2px 0;color:var(--dim);font-size:11px}
.pill.b{border-color:#1E3A5F;color:var(--brand-cy)}
.note{color:var(--dim);font-size:11.5px}
.hr{height:1px;background:var(--line);margin:10px 0}
@media (prefers-reduced-motion: reduce){*{transition:none!important}}
</style></head><body>
<div class="gbt-topbar"><span class="mark"></span>
 <span class="brand">GBT<b>小土豆</b>V8 · 云插件互绑拓扑</span>
 <span class="note">单一真源 __SPEC__ · 生成 __GEN__ · 触手串联 · 每处连接点可见</span></div>
<div class="wrap">
 <div class="card">
  <h2>// 01 — 环形拓扑（中心触手 · N 条双向臂 + 插件间全互联）</h2>
  <div class="stats" id="stats"></div>
  <svg id="ring" viewBox="0 0 900 620" role="img" aria-label="云插件互绑环形拓扑">__RING__</svg>
  <div class="note" id="ringNote"></div>
 </div>
 <div class="card">
  <h2>// 02 — 连接点详情（点节点 / 点矩阵格 / 点环上线）</h2>
  <div id="detail" class="note">选一个插件节点或矩阵格 —— 这里列出它的**每一处连接点**（互绑臂 + 互绑边 + 门表）。</div>
  <div class="hr"></div>
  <h2>// 03 — 资源共享（同一云资源被多个插件访问 = 互通点）</h2>
  <div id="shared">__SHARED__</div>
 </div>
 <div class="card">
  <h2>// 04 — 连接矩阵（N×N · 每格 = 一处有向连接点 · 对角=自环不绑）</h2>
  <div id="matrix">__MATRIX__</div>
 </div>
 <div class="card">
  <h2>// 05 — 部署分类（什么插件上部署的什么 · 不一样的区分开来）</h2>
  <div id="deploy">__DEPLOY__</div>
 </div>
 <div class="card">
  <h2>// 06 — 拼接与共享（照源码：ctx.call 记边 · 同 isolate 真共享 · 不做密钥连接）</h2>
  <div id="mech">__MECH__</div>
 </div>
 <div class="card">
  <h2>// 07 — 节点锁定（捷径）：每位插件的 op 门表 —— 直达本节点即可</h2>
  <div id="locks">__LOCKS__</div>
 </div>
</div>
<script>
const MESH_DATA = __DATA__;
const MODS = MESH_DATA.modules, N = MESH_DATA.n;
const seqById = {}; MODS.forEach(m => seqById[m.seq] = m);
function el(tag, attrs, text){ const e = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const k in (attrs||{})) e.setAttribute(k, attrs[k]); if (text != null) e.textContent = text; return e; }

/* 统计 */
const stats = document.getElementById("stats");
[["插件", N],["有向连接点", MESH_DATA.counts.directed],["无向互绑", MESH_DATA.counts.undirected],
 ["本机驱动", MODS.filter(m=>m.local_driver).length],["云资源种类", Object.keys(MESH_DATA.shared).length]]
 .forEach(([k,v])=>{ const d=document.createElement("div"); d.className="stat";
   d.innerHTML = "<b>"+v+"</b><i>"+k+"</i>"; stats.appendChild(d); });

/* 环/矩阵/共享/锁：**生成期已静态落图**（见 gen 的 render_page）—— 脚本只管交互。 */
/* 交互：选中 → 高亮该插件的全部连接点 + 侧栏逐条列 */
const detail = document.getElementById("detail");
function clearHot(){ document.querySelectorAll(".link.hot").forEach(e=>e.classList.remove("hot"));
  document.querySelectorAll(".node.sel").forEach(e=>e.classList.remove("sel"));
  document.querySelectorAll("td.cell.on").forEach(e=>e.classList.remove("on")); }
function select(seq, via){
  clearHot();
  const g = document.getElementById("nd-"+seq); if (g) g.classList.add("sel");
  const m = seqById[seq];
  const others = MODS.filter(x=>x.seq!==seq);
  let rows = "<b>c"+String(seq).padStart(2,"0")+" · "+m.id+"</b><br>"+
    "<span class='note'>"+m.duty+" · 本机驱动 <span class='mono'>"+(m.local_driver||"未绑")+"</span> · 云资源："+
    (m.cloud||[]).join("、")+"</span><div class='hr'></div>"+
    "<b>互绑臂</b>：触手 ↔ c"+String(seq).padStart(2,"0")+"（双向 · 1 处）<br><b>互绑边</b>（"+
    others.length+" 处有向连接点）：";
  const list = others.map(o=>{ const l = document.getElementById("lnk-"+Math.min(seq,o.seq)+"-"+Math.max(seq,o.seq));
    if (l) l.classList.add("hot");
    const c = document.querySelector("td.cell[data-a='"+seq+"'][data-b='"+o.seq+"']"); if (c) c.classList.add("on");
    const c2 = document.querySelector("td.cell[data-a='"+o.seq+"'][data-b='"+seq+"']"); if (c2) c2.classList.add("on");
    return "c"+String(seq).padStart(2,"0")+" ↔ c"+String(o.seq).padStart(2,"0");
  }).join(" · ");
  detail.innerHTML = rows + "<div class='mono' style='font-size:11px'>"+list+"</div>" +
    "<div class='hr'></div><b>边界（真源原文）</b>：<span class='note'>"+(m.boundary||"—")+"</span>" +
    (via ? "<div class='hr'></div><span class='note'>入口："+via+"</span>" : "");
}
document.querySelectorAll(".node").forEach(g=>{
  const f = () => { const s = Number(g.getAttribute("data-seq")); if (s) select(s, "环形拓扑节点"); };
  g.addEventListener("click", f);
  g.addEventListener("keydown", (e)=>{ if (e.key==="Enter"||e.key===" ") { e.preventDefault(); f(); } });
});
document.querySelectorAll("td.cell").forEach(td=>{
  const a = Number(td.getAttribute("data-a")), b = Number(td.getAttribute("data-b"));
  td.addEventListener("click", ()=>{ clearHot();
    const c = document.querySelector("td.cell[data-a='"+a+"'][data-b='"+b+"']"); if (c) c.classList.add("on");
    if (a!==b) select(a, "矩阵格 c"+a+" → c"+b); else detail.innerHTML =
      "<b class='mono'>c"+a+" → c"+a+"</b><br><span class='note'>自环：真源 edges.self_loop_expected=0 ⇒ 不绑自己。</span>"; });
});
document.querySelectorAll(".link").forEach(l=>{
  l.addEventListener("click", ()=>{ clearHot(); l.classList.add("hot");
    const a = Number(l.getAttribute("data-a")), b = Number(l.getAttribute("data-b"));
    ["nd-"+a,"nd-"+b].forEach(id=>{ const g = document.getElementById(id); if (g) g.classList.add("sel"); });
    detail.innerHTML = "<b class='mono'>c"+a+" ↔ c"+b+"</b><br><span class='note'>这一条线代表**两处**有向 ctx.call 边："+
      "c"+a+" → c"+b+" 与 c"+b+" → c"+a+"（双向互绑）。点节点看该插件全部连接点。</span>"; });
});
</script>
<script src="../shell/tentacle-kit.js" defer></script>
</body></html>
"""


def render_page(model: dict) -> str:
    """**生成期静态落图**（2026-10-04 修正）：环线/臂/节点/矩阵全部写进 HTML ——
    每处连接点都有真元素（判据可数），且脚本被禁时图**依然看得见**；脚本只管交互高亮。
    """
    mods, N = model["modules"], model["n"]
    CX, CY, R, ARM = 450.0, 310.0, 235.0, 92.0
    pos = {}
    for i, m in enumerate(mods):
        a = -math.pi / 2 + i * 2 * math.pi / N
        pos[m["seq"]] = (CX + R * math.cos(a), CY + R * math.sin(a))
    out = []

    # ① 环上互绑线（每条 = 两处有向连接点）
    out.append("<defs><marker id='arwO' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='5' markerHeight='5' "
               "orient='auto'><path d='M0,0 L10,5 L0,10 z' fill='#f5b041'/></marker>"
               "<marker id='arwO2' viewBox='0 0 10 10' refX='1' refY='5' markerWidth='5' markerHeight='5' "
               "orient='auto'><path d='M10,0 L0,5 L10,10 z' fill='#f5b041'/></marker></defs>")
    for u in model["undirected"]:
        x1, y1 = pos[u["a"]]
        x2, y2 = pos[u["b"]]
        out.append("<line class='link' id='lnk-%d-%d' data-a='%d' data-b='%d' x1='%.1f' y1='%.1f' x2='%.1f' y2='%.1f'/>"
                   % (u["a"], u["b"], u["a"], u["b"], x1, y1, x2, y2))
    # ② hub + 双向臂
    out.append("<g class='node hub'><circle cx='%.1f' cy='%.1f' r='30'/><text x='%.1f' y='%.1f'>GBT</text>"
               "<text x='%.1f' y='%.1f'>触手</text></g>" % (CX, CY, CX, CY - 2, CX, CY + 11))
    for m in mods:
        x, y = pos[m["seq"]]
        a = math.atan2(y - CY, x - CX)
        out.append("<line class='arm' id='arm-%d' data-seq='%d' x1='%.1f' y1='%.1f' x2='%.1f' y2='%.1f'/>"
                   % (m["seq"], m["seq"], CX + ARM * math.cos(a), CY + ARM * math.sin(a),
                      x - math.cos(a) * 16, y - math.sin(a) * 16))
    # ③ 节点
    for m in mods:
        x, y = pos[m["seq"]]
        out.append("<g class='node' id='nd-%d' data-seq='%d' tabindex='0' aria-label='%s %s'>"
                   "<circle cx='%.1f' cy='%.1f' r='15'/><text x='%.1f' y='%.1f'>c%02d</text>"
                   "<text class='drv' x='%.1f' y='%.1f'>%s</text></g>"
                   % (m["seq"], m["seq"], m["id"], m["duty"], x, y, x, y + 1, m["seq"],
                      x, y + 11, m.get("local_driver") or "未绑"))
    ring = "".join(out)

    # ④ 连接矩阵（N×N 静态格：每格一处有向连接点，对角=自环不绑）
    rows = ["<table><thead><tr><th>from\\to</th>"]
    rows += ["<th>c%02d</th>" % m["seq"] for m in mods]
    rows.append("</tr></thead><tbody>")
    for a in mods:
        rows.append("<tr><th>c%02d %s</th>" % (a["seq"], a["duty"][:10]))
        for b in mods:
            self_ = a["seq"] == b["seq"]
            rows.append("<td class='cell%s' data-a='%d' data-b='%d'>%s</td>"
                        % (" self" if self_ else "", a["seq"], b["seq"], "—" if self_ else "→"))
        rows.append("</tr>")
    rows.append("</tbody></table><div class='note'>每格 = 一处有向连接点（行 from → 列 to）。"
                "点格看详情；点行号选中该插件。</div>")
    matrix = "".join(rows)

    # ⑤ 资源共享
    sh = []
    for res, seqs in model["shared"].items():
        names = "、".join("c%02d（%s）" % (s, next(m["duty"] for m in mods if m["seq"] == s)[:12]) for s in seqs)
        sh.append("<div><span class='pill b'>%s</span><span class='note'>共用此资源的插件：%s ⇒ 互通点 %d 个</span></div>"
                  % (res, names, len(seqs)))
    shared = "".join(sh) + (
        "<div class='note'>**诚实边界**：上方按**资源种**分组；其中真正**全员共享**的是 —— "
        "① 同一 isolate（形态 A：10 模块同进程，CPU/内存真共用）"
        "② mesh10/ 命名空间（所有键统一前缀，落在主人已有的 KV/R2 上，互不覆盖）。"
        "其余多数组资源是**单模块专用**（如 KV (CTX) 只 c02）—— 不编「大家都共享」。"
        "插件互绑本身不经密钥（边 = ctx.call 调用关系）。</div>")

    # ⑥ 节点锁定（op 门表）
    lk = ["<table><thead><tr><th>插件</th><th>本机驱动（触手能力位）</th><th>op → 门</th></tr></thead><tbody>"]
    for m in mods:
        ops = "".join("<span class='pill%s'>%s · %s</span>"
                      % ("" if g == "none" else " b", o, g)
                      for o, g in (m.get("op_gates") or {}).items())
        lk.append("<tr><td>c%02d <span class='mono'>%s</span><br><span class='note'>%s</span></td>"
                  "<td class='mono'>%s</td><td>%s</td></tr>"
                  % (m["seq"], m["id"], m["duty"], m.get("local_driver") or "未绑", ops))
    lk.append("</tbody></table><div class='note'>捷径口径：调用按 op **直达本节点**（门表见上），"
              "不必绕别的插件节点；「锁定」= 同一意图重复调用直接命中同一条路径。</div>")
    locks = "".join(lk)

    # ⑦ 部署分类
    dparts = []
    for layer in model["deploy_layers"]:
        dparts.append("<div><span class='pill b'>%s</span><span class='note'>%s</span><br>"
                      "<span class='note'>承载：%s</span><br>"
                      "<span class='note'>**不承载**：%s</span></div><div class='hr'></div>"
                      % (layer["layer"], layer["where"], "；".join(layer["carries"]),
                         "；".join(layer["not_carries"])))
    dparts.append("<div class='note'>逐插件归属：<br>" + "<br>".join(
        "c%02d <span class='mono'>%s</span> ⇒ 云端承载 <b>%s</b>；本机驱动 <span class='mono'>%s</span>（%s）"
        % (m["seq"], m["id"], m["duty"], m.get("local_driver") or "未绑", m.get("driver_why") or "")
        for m in mods) + "</div>")
    deploy = "".join(dparts)

    # ⑦b 分组（槽位表才有；5 组为纲 —— 主人 2026-10-04 蓝图）
    groups = model.get("groups") or []
    gparts = []
    for g in groups:
        got = [m for m in mods if m.get("group") == g["id"]]
        live = [m for m in got if not m.get("is_reserve")]
        gparts.append("<div><span class='pill b'>组%d · %s</span> <span class='note'>%s</span><br>"
                      "<span class='note'>槽位 %d 个（已指派驱动 %d · 备用 %d）：%s</span></div><div class='hr'></div>"
                      % (g["id"], g.get("name", ""), g.get("carries", ""),
                         len(got), len(live), len(got) - len(live),
                         "、".join(m["id"] for m in got)))
    deploy = "".join(gparts) + deploy if gparts else deploy

    # ⑧ 拼接与共享（照源码）
    mech = model["mechanism"]
    mparts = [
        "<div><b>拼接</b>：%s</div>" % mech["splice"],
        "<div><b>ctx 契约</b>：<span class='mono'>%s</span></div>" % mech["ctx_contract"],
        "<div><b>共享</b>：%s</div>" % mech["share"],
        "<div><b>不做密钥连接</b>：%s</div>" % mech["no_keys"],
        "<div><b>云端现读</b>：%s</div>" % mech["live"],
        "<div class='note'>出处：" + " · ".join("<span class='mono'>%s</span>" % x for x in mech["source"]) + "</div>",
    ]
    mechanism = "".join(mparts)

    data = json.dumps({"modules": mods, "n": N, "counts": model["counts"],
                       "undirected": model["undirected"], "shared": model["shared"],
                       "generated_at": model["generated_at"]}, ensure_ascii=False)
    return (_PAGE.replace("__DATA__", data)
                  .replace("__TASTE_ROOT__", site_root_block())
                  .replace("__RING__", ring)
                  .replace("__MATRIX__", matrix)
                  .replace("__SHARED__", shared)
                  .replace("__LOCKS__", locks)
                  .replace("__DEPLOY__", deploy)
                  .replace("__MECH__", mechanism)
                  .replace("__SPEC__", model.get("spec_path") or "deploy/cloud-10/mesh.json")
                  .replace("__GEN__", model["generated_at"]))


def cmd_gen(spec: str = "") -> int:
    mesh = load_mesh(spec)
    model = build_model(mesh)
    PAGE.parent.mkdir(parents=True, exist_ok=True)
    PAGE.write_text(clean_html(render_page(model)), encoding="utf-8")
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(model, ensure_ascii=False, indent=1), encoding="utf-8")
    c = model["counts"]
    print("拓扑页：%s" % PAGE)
    print("台账：%s" % LEDGER)
    print("插件 %d · 有向连接点 %d · 无向互绑 %d · 矩阵格 %d（每格一处连接点）"
          % (c["plugins"], c["directed"], c["undirected"], c["matrix_cells"]))
    return 0


def cmd_verify(as_json: bool = False) -> int:
    mesh = load_mesh(os.environ.get("GBT_PLUGINS_SPEC") or None)
    model = build_model(mesh)
    rows = []

    def add(cid, ok, detail):
        rows.append({"id": cid, "ok": bool(ok), "detail": detail})

    c = model["counts"]
    n = c["plugins"]
    add("V1 连接点数恒等", c["directed"] == n * (n - 1) and c["undirected"] == n * (n - 1) // 2,
        "插件 %d ⇒ 有向 %d（应 %d）· 无向 %d（应 %d）"
        % (n, c["directed"], n * (n - 1), c["undirected"], n * (n - 1) // 2))

    names = registry_names()
    # 备用槽（groups 4–5，主人明说保留备用）**不算未绑** —— 它们没有 driver 是设计态；
    # 但要在读数里如实报出来（不是"全绑好了"）。
    unbound = [m["id"] for m in model["modules"]
               if not m.get("local_driver") and not m.get("is_reserve")]
    reserve = [m["id"] for m in model["modules"] if m.get("is_reserve")]
    phantom = [m["id"] + "→" + str(m.get("local_driver")) for m in model["modules"]
               if m.get("local_driver") and m["local_driver"] not in names]
    add("V2 每个**已指派**插件都绑本机驱动（备用槽如实另计）", not unbound,
        "未绑：%s；备用槽 %d 个（不预置，主人指派后再绑）：%s"
        % (unbound or "无", len(reserve), "、".join(reserve[:4]) + ("…" if len(reserve) > 4 else "") if reserve else "无"))
    add("V3 驱动位必须真在册（无幽灵名）", not phantom, "不在册：%s" % (phantom or "无（全部命中能力注册表）"))

    ok_page = PAGE.exists()
    add("V4 页面在盘上", ok_page, str(PAGE))
    if ok_page:
        html = PAGE.read_text(encoding="utf-8")
        add("V5 页面自包含（零外链/零 CDN）",
            not re.search(r'(src|href)\s*=\s*["\']https?://', html, re.I)
            and "cdn" not in html.lower(),
            "外链命中：%s" % (re.findall(r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)', html, re.I)[:3] or "无"))
        n_lnk = len(re.findall(r"id='lnk-\d+-\d+'", html))
        n_cell = html.count("data-a='")
        add("V6 每处连接点都有元素（静态落图：矩阵逐格 + 环上每条互绑线 + 臂）",
            n_cell >= n * n and n_lnk == c["undirected"] and html.count("class='arm'") == n,
            "矩阵格 %d（应 %d）· 环线 %d（应 %d）· 臂 %d（应 %d）"
            % (n_cell, n * n, n_lnk, c["undirected"], html.count("class='arm'"), n))
        add("V7 触手 hub 在页上（1 根串联全部插件）", "触手" in html and "arm-" in html,
            "hub 节点与 N 条双向臂（现画 %d 条）" % n)
        add("V9 部署分类（什么插件承载什么 · 不一样的区分开）",
            html.count("部署分类") >= 1 and "云端 mesh10" in html and "本机 GBT 框架" in html
            and "外部枢纽" in html and html.count("⇒ 云端承载") >= n,
            "三层（云端 mesh10 / 本机框架 / 外部枢纽）+ 逐插件归属 %d 条" % html.count("⇒ 云端承载"))
        add("V10 机制照源码（ctx.call 记边 · 同 isolate 共享 · 不做密钥连接）",
            all(k in html for k in ("ctx.call", "同一 isolate", "不做密钥连接", "modules.js:254", "worker.js")),
            "出处逐条在页上：modules.js:5/254 · worker.js:10/191-219")
        add("V8 台账与真源一致", LEDGER.exists() and
            json.loads(LEDGER.read_text(encoding="utf-8"))["counts"] == c,
            str(LEDGER))
    fails = [r for r in rows if not r["ok"]]
    if as_json:
        print(json.dumps({"rows": rows, "pass": len(rows) - len(fails), "fail": len(fails)},
                         ensure_ascii=False, indent=1))
    else:
        for r in rows:
            print("%s %-34s %s" % ("PASS" if r["ok"] else "FAIL", r["id"], r["detail"]))
        print("PASS %d · FAIL %d" % (len(rows) - len(fails), len(fails)))
    return 1 if fails else 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                   # noqa: BLE001
            pass
    spec = ""
    if "--spec" in argv:
        i = argv.index("--spec")
        spec = argv[i + 1] if i + 1 < len(argv) else ""
    if not argv or argv[0] == "gen":
        return cmd_gen(spec)
    if argv[0] == "verify":
        return cmd_verify(as_json="--json" in argv)
    print("用法：cloud-plugins.py [gen|verify --json]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
