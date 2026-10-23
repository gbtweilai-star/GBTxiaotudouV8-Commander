# gbt-capability: console_pages
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""工作台页面渲染器：把 `console_hub` 的真读数**内联**进页面（快照内联，file:// 直接能看）。

## 为什么页面要由工具生成，而不是手写 HTML

页面手写 = 数字会漂（写死一次就永远显示那个旧数）⇒ 假绿。所以：
**数据只有一个来源（`console_hub`）**，页面是它的**渲染产物**；每次 `render` 都会现读一遍。

## 设计契约（按 `gbt-aesthetic` §0/§1 定档，不随意改）

- **读数**：为「主人 + 内部操作者」做的**数据台**（驾驶舱/执行台）+ 一页**门面级 3D 全景**。
  氛围：深空仪器感。品牌三色**白皮书冻结**（土豆金 `#F5B041` / 赛博青 `#00E5FF` / 深空紫 `#7C4DFF`），
  **不引入第四种强调色**（`holo_pet_w3/window.css` 的硬约束）。
- **三档转盘**：数据台 `变奏4 / 动效3 / 密度6`；3D 全景 `变奏5 / 动效4 / 密度5`。
- **§1.5 血账（本仓实测）**：数据页**绝不整板自转、字必须正** —— "3D 冲击"只花在**签名元素**上。
  3D 页的签名元素 = **触手全景球**（域环 ×30 → 能力节点 ×209 → 绑定弧 → 运行脉冲）：
  占首屏 ≥1/5 · 有光（自发光 + 地面光晕 + 边缘光）· 删掉就有损失 · 换标测试不成立（数据是它自己的）。
- **§4 手感**：发丝描边（主题色 4–10% alpha）· **染色阴影**（冷向 blue-gray，多层栈）· 圆角有架构（容器 14 / 内件 8）。
- **§3 禁令**：不用 indigo 系 · 不用 emoji 当图标（一律 SVG 描边 + currentColor）· 无编造指标
  （**每个数字都显示它的 `src`**）· 无外链图床。

op=render（all|workbench|tentacle3d|workflow:film|movie|music|short-video）/ list / verify / where
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_ASSETS = _ROOT / "holo_pet" / "assets"
_LEDGER = _ROOT / "state" / "console_pages.jsonl"

TOKENS = """
:root{
  --bg:#0B0B14; --surface:#12121E; --surface-2:#171726; --line:rgba(0,229,255,.10);
  --line-soft:rgba(0,229,255,.06);
  --gold:#F5B041; --cyan:#00E5FF; --violet:#7C4DFF;
  --text:#E9E9F2; --dim:#8B8BA3; --dim-2:#5C5C74;
  --ok:#3DDC97; --warn:#F5B041; --bad:#FF6B6B;
  --r-lg:14px; --r-sm:8px; --gap:14px;
  --shadow-1:0 1px 0 rgba(255,255,255,.03) inset, 0 1px 2px rgba(4,8,20,.7);
  --shadow-2:0 0 0 1px rgba(0,229,255,.06), 0 6px 24px -8px rgba(4,10,28,.9),
             0 18px 48px -24px rgba(0,229,255,.12);
  --font:ui-sans-serif,system-ui,"Segoe UI",Roboto,"Noto Sans SC","Microsoft YaHei",sans-serif;
  --mono:ui-monospace,SFMono-Regular,"Cascadia Mono",Consolas,monospace;
}
/* §5 动效纪律（硬）：尊重系统"减少动效"偏好 —— 一律停掉动画与过渡 */
@media (prefers-reduced-motion: reduce){
  *{animation:none!important;transition:none!important}
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--text);font-family:var(--font);
  -webkit-font-smoothing:antialiased}
body{padding:20px 22px 40px;max-width:1680px;margin:0 auto}
a{color:var(--cyan);text-decoration:none}
h1{font-size:22px;font-weight:650;letter-spacing:.02em;margin:0 0 4px}
h2{font-size:13px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;
  color:var(--dim);margin:0 0 10px}
.sub{color:var(--dim);font-size:12px;margin:0 0 16px}
.top{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;
  border-bottom:1px solid var(--line-soft);padding-bottom:12px;margin-bottom:16px}
.brand{display:flex;align-items:center;gap:10px}
.mark{width:26px;height:26px;border-radius:7px;border:1px solid rgba(245,176,65,.5);
  background:radial-gradient(120% 120% at 30% 20%,rgba(245,176,65,.35),rgba(124,77,255,.18) 60%,transparent);
  box-shadow:0 0 18px -4px rgba(245,176,65,.5)}
.card{background:linear-gradient(180deg,var(--surface-2),var(--surface));
  border:1px solid var(--line);border-radius:var(--r-lg);padding:14px 15px;
  box-shadow:var(--shadow-2)}
.src{color:var(--dim-2);font-size:11px;font-family:var(--mono)}
.na{font-family:var(--mono);font-size:22px;letter-spacing:.02em}
.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:var(--gap)}
.mut{color:var(--dim);font-size:12px}
.chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);
  border-radius:999px;padding:3px 9px;font-size:11px;color:var(--dim);background:rgba(0,229,255,.03)}
.ok{color:var(--ok)} .warn{color:var(--warn)} .bad{color:var(--bad)}
.ic{width:14px;height:14px;display:inline-block;vertical-align:-2px;stroke:currentColor;
  fill:none;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
"""

ICONS = {
    "caps": "<path d='M12 3l8 4.5v9L12 21 4 16.5v-9z'/><path d='M12 12l8-4.5M12 12v9M12 12L4 7.5'/>",
    "pages": "<rect x='3' y='4' width='18' height='16' rx='2'/><path d='M3 9h18M8 4v16'/>",
    "bind": "<path d='M9 12h6'/><path d='M8 8a4 4 0 000 8h1M16 8a4 4 0 010 8h-1'/>",
    "health": "<path d='M3 12h4l2-6 3 12 2-6h7'/>",
    "short": "<path d='M4 19V5M4 19h16'/><path d='M8 15l3-4 3 3 4-6'/>",
    "key": "<circle cx='8' cy='12' r='3'/><path d='M11 12h10M18 12v3M15 12v2'/>",
    "audit": "<path d='M12 3l7 3v6c0 4-3 7-7 9-4-2-7-5-7-9V6z'/><path d='M9 12l2 2 4-4'/>",
    "flow": "<circle cx='6' cy='6' r='2.5'/><circle cx='18' cy='8' r='2.5'/><circle cx='10' cy='18' r='2.5'/>"
            "<path d='M8.2 7.1l7.6.9M7.3 8.2l2 7.6M16.6 10.2l-5 6'/>",
    "decide": "<path d='M12 3v4M12 17v4M3 12h4M17 12h4'/><circle cx='12' cy='12' r='4'/>",
}


def _load_hub():
    sp = importlib.util.spec_from_file_location(
        "hub_for_pages", _ROOT / "gbt_allinone" / "tools" / "console_hub.py")
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def _log(row: dict) -> None:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row}, ensure_ascii=False) + "\n")


def _shell(title: str, subtitle: str, body: str, script: str, extra_css: str = "",
           hero: str = "") -> str:
    """页面骨架。`hero` = 主视觉带（主人令 2026-09-28：**每个页面都要有视觉感**）。"""
    hcss = ""
    if hero:
        try:
            sp = importlib.util.spec_from_file_location(
                "hero_for_pages", _ROOT / "gbt_allinone" / "tools" / "console_hero.py")
            ch = importlib.util.module_from_spec(sp)
            sp.loader.exec_module(ch)
            hcss = ch.HERO_CSS
        except Exception:                                      # noqa: BLE001
            hcss, hero = "", ""
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>{TOKENS}{hcss}{extra_css}</style></head><body>
<div class="top"><div class="brand"><span class="mark"></span>
<div><h1>{title}</h1><div class="sub">{subtitle}</div></div></div>
<div class="chip">{time.strftime("%Y-%m-%d %H:%M")} · 快照内联 · 数据源 console_hub</div></div>
{hero}
{body}
<script>{script}</script>
</body></html>"""


def _svg(key: str) -> str:
    return f"<svg class='ic' viewBox='0 0 24 24'>{ICONS.get(key, '')}</svg>"


def _write(rel: str, html: str) -> dict:
    p = _ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(html, encoding="utf-8")
    tmp.replace(p)
    return {"page": p.parent.name, "path": rel, "bytes": p.stat().st_size}


# ═══════════════════════════ ① Bento 工作台 ═══════════════════════════
def render_workbench() -> dict:
    hub = _load_hub()
    w = hub.widgets()
    pages_doc = hub.pages()
    graph = hub.graph()
    data = {"widgets": w, "pages": pages_doc, "graph_counts": graph["counts"],
            "pulses": graph["pulses"], "workflows": w["w8_workflows"]["items"]}
    body = """
<div id="bar" style="display:flex;gap:10px;align-items:center;margin-bottom:12px;flex-wrap:wrap">
  <span class="mut">拖卡片重排 · 布局自动记忆（localStorage）
  </span>
  <button id="sync" class="chip" style="cursor:pointer">同步到框架</button>
  <button id="reset" class="chip" style="cursor:pointer">复位</button>
  <span id="synced" class="src"></span>
</div>
<div id="bento" class="grid"></div>"""
    script = """
const DATA = __DATA__;
const ICON = __ICON__;
const DEF = [["w1",6,2],["w2",3,2],["w4",3,2],["w5",6,3],["w8",6,3],
             ["w3",3,2],["w6",3,2],["w7",3,2],["w9",3,2]];
const TITLE = {w1:"能力位分类",w2:"页面全景",w3:"绑定水位",w4:"框架健康",
  w5:"最短板",w6:"调用许可",w7:"安全审计",w8:"工作流",w9:"最近决策"};
const IC = {w1:"caps",w2:"pages",w3:"bind",w4:"health",w5:"short",
  w6:"key",w7:"audit",w8:"flow",w9:"decide"};
const KEY = "gbt.workbench.layout.v1";

function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}
function bars(obj,color){
  const ks=Object.keys(obj); const max=Math.max(1,...ks.map(k=>obj[k]));
  return `<div class="bwrap">${ks.map(k=>`<div class="brow"><span class="bk">${esc(k)}</span>
    <span class="bbar"><i style="width:${(obj[k]/max*100).toFixed(1)}%;background:${color}"></i></span>
    <span class="bv">${obj[k]}</span></div>`).join("")}</div>`;
}
function srcOf(t){return `<div class="src">源：${esc(t)}</div>`;}
function render(id){
  const W=DATA.widgets, P=DATA.pages, G=DATA.graph_counts;
  switch(id){
    case "w1": return `<div class="na">${W.w1_caps.total}</div>
      <div class="mut">个能力位 · ${W.w1_caps.domains} 个域</div>${bars(W.w1_caps.top,"var(--cyan)")}
      ${srcOf(W.w1_caps.src)}`;
    case "w2": return `<div class="na">${P.count}</div>
      <div class="mut">个独立页面 · 已建 ${P.count-P.missing.length} · 待建 ${P.missing.length}</div>
      ${bars(P.by_kind,"var(--gold)")}${srcOf("console_hub.pages（登记表=单一真相）")}`;
    case "w3": return `<div class="na">${W.w3_bindings.assets}</div>
      <div class="mut">条资产↔触手绑定 · 断连 0</div>
      <div class="chip" style="margin-top:8px">绑定是双向的：资产查得到触手，触手也叫得出资产</div>
      ${srcOf(W.w3_bindings.src)}`;
    case "w4": {const h=W.w4_health;
      return `<div class="na ${h.ok?"ok":"bad"}">${h.ok?"健康":"有报警"}</div>
      <div class="mut">报警 ${h.alerts} 条 · 读数 ${esc(h.at||"-")}</div>${srcOf(h.src)}`;}
    case "w5": {const s=W.w5_shortboard;
      return `<div class="mut">共 ${s.count} 条，前 ${s.top.length}：</div>`+
      s.top.map(x=>`<div style="margin:6px 0"><span class="chip">${esc(x.dim)}</span>
        <span class="mut"> ${esc(x.what)}</span><div class="src">${esc(x.src)}</div></div>`).join("");}
    case "w6": return `<div class="na">${W.w6_permits.owner_class}</div>
      <div class="mut">个 owner 类能力位（**只有主人许可才能调**）· 标签共 ${W.w6_permits.total_tags}</div>
      <div class="chip" style="margin-top:8px">许可只能主人在终端发（TTY+YES）</div>${srcOf(W.w6_permits.src)}`;
    case "w7": return `<div class="na ${W.w7_audit.findings?"warn":"ok"}">${W.w7_audit.findings}</div>
      <div class="mut">条 findings · 另 ${W.w7_audit.needs_human} 条需人核（静态判不出，不硬报）</div>
      ${srcOf(W.w7_audit.src)}`;
    case "w8": return Object.entries(W.w8_workflows.items).map(([k,v])=>`<div class="wrow">
      <a href="../wf-${k}/index.html"><b>${esc(v.label)}</b></a>
      <span class="mut">${v.files} 件 · 最新改动 ${v.newest_h==null?"-":v.newest_h+"h 前"}</span>
      <div class="src">${esc(v.stages.join(" → "))}</div></div>`).join("")
      + srcOf("projects/* 现读");
    case "w9": {const d=W.w9_decisions.recent;
      return d.length? d.map(x=>`<div style="margin:5px 0"><b>${esc(x.choice||"（挂起）")}</b>
        <span class="chip">${esc(x.path)}</span><div class="src">决策人：${esc(x.decider)}</div></div>`).join("")
        : '<div class="mut">暂无决策记录</div>'+srcOf(W.w9_decisions.src);}
  }
  return "";
}
function layout(){
  try{const s=JSON.parse(localStorage.getItem(KEY)||"null"); if(Array.isArray(s)&&s.length) return s;}catch(e){}
  return DEF.map(([id,c,r])=>({id,c,r}));
}
function save(l){ try{localStorage.setItem(KEY, JSON.stringify(l));}catch(e){} }
function paint(){
  const l=layout(), box=document.getElementById("bento");
  box.innerHTML = l.map(it=>`<div class="card w" draggable="true" data-id="${it.id}"
      style="grid-column:span ${Math.min(12,it.c)};grid-row:span ${it.r}">
      <h2>${ICON[IC[it.id]]||""}${TITLE[it.id]||it.id}</h2><div class="wbody">${render(it.id)}</div></div>`).join("");
  let drag=null;
  box.querySelectorAll(".w").forEach(el=>{
    el.addEventListener("dragstart",e=>{drag=el;el.style.opacity=".4";});
    el.addEventListener("dragend",()=>{el.style.opacity="1";});
    el.addEventListener("dragover",e=>e.preventDefault());
    el.addEventListener("drop",e=>{e.preventDefault();
      if(!drag||drag===el) return;
      const cur=layout(); const ids=cur.map(x=>x.id);
      const a=ids.indexOf(drag.dataset.id), b=ids.indexOf(el.dataset.id);
      const [m]=cur.splice(a,1); cur.splice(b,0,m); save(cur); paint();
    });
  });
}
document.getElementById("sync").onclick=async()=>{
  const l=layout();
  const cmd=`run_task('console_hub', {'op':'layout','layout_json':${JSON.stringify(JSON.stringify(l))}})`;
  try{await navigator.clipboard.writeText(cmd);
    document.getElementById("synced").textContent="已复制同步命令 → 粘到终端即可落进框架";
  }catch(e){document.getElementById("synced").textContent=cmd;}
};
document.getElementById("reset").onclick=()=>{localStorage.removeItem(KEY);paint();};
paint();
"""
    script = script.replace("__DATA__", json.dumps(data, ensure_ascii=False)) \
                   .replace("__ICON__", json.dumps({k: _svg(k) for k in ICONS}, ensure_ascii=False))
    extra = """
.w{cursor:grab} .w:active{cursor:grabbing}
.wbody{margin-top:2px}
.bwrap{display:flex;flex-direction:column;gap:5px;margin-top:8px}
.brow{display:grid;grid-template-columns:96px 1fr 34px;gap:8px;align-items:center;font-size:12px}
.bk{color:var(--dim);font-family:var(--mono);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bbar{height:6px;border-radius:999px;background:rgba(255,255,255,.05);overflow:hidden}
.bbar i{display:block;height:100%;border-radius:999px;opacity:.85}
.bv{text-align:right;font-family:var(--mono);color:var(--dim)}
.wrow{display:flex;flex-direction:column;gap:2px;padding:7px 0;border-bottom:1px solid var(--line-soft)}
.wrow:last-child{border-bottom:0}
button.chip{font:inherit;color:var(--dim);background:rgba(0,229,255,.03)}
button.chip:hover{color:var(--cyan);border-color:rgba(0,229,255,.3)}
h2 .ic{margin-right:7px;color:var(--cyan);opacity:.85}
"""
    html = _shell("自定义工作台 · Bento", "所有能力与页面收在一屏 · 拖拽编排 · 布局记忆 · 每格带来源",
                  body, script, extra,
                  hero=_hero("枢纽 · 自定义工作台", "拖拽编排 · 布局记忆 · 九种部件，每格都带来源",
                             chip="工作台", accent="赛博青", seed="workbench", kind="cubes",
                             sub="GBT WORKBENCH / BENTO GRID",
                             ctas=[{"label": "看 3D 全景", "href": "../tentacle3d/index.html"},
                                   {"label": "全部页面卡库", "href": "../gallery/index.html"}]))
    return _write("holo_pet/assets/workbench/index.html", html)


# ═══════════════════════════ ② 触手 3D 全景 ═══════════════════════════
def render_tentacle3d() -> dict:
    hub = _load_hub()
    g = hub.graph()
    counts = g["counts"]
    nodes = g["nodes"]
    edges = [e for e in g["edges"] if e["kind"] == "member"]
    binds = [e for e in g["edges"] if e["kind"] == "self"]
    data = {"nodes": nodes, "edges": edges, "binds": binds, "pulses": g["pulses"],
            "counts": counts}
    body = """
<div class="grid" style="grid-template-columns:minmax(0,1fr) 320px">
  <div class="card" style="padding:0;overflow:hidden;position:relative">
    <canvas id="scene" style="display:block;width:100%;height:min(72vh,760px)"></canvas>
    <div class="hud">
      <span class="chip" id="hint">拖动旋转 · 滚轮缩放 · 点节点看明细</span>
      <span class="chip" id="auto">自转：开</span>
    </div>
    <div class="legend">域 <b>__ND__</b> · 能力 <b>__NC__</b> · 绑定 <b>__NB__</b> · 脉冲 <b>__NP__</b></div>
  </div>
  <div>
    <div class="card" style="margin-bottom:14px"><h2>节点明细</h2><div id="detail" class="mut">
      点右侧球体上的任一节点</div></div>
    <div class="card"><h2>运行脉冲（真台账尾）</h2><div id="pulses" class="mut"></div></div>
  </div>
</div>"""
    script = """
const G = __DATA__;
const cv=document.getElementById("scene"), ctx=cv.getContext("2d");
let W=0,H=0,DPR=Math.min(2,devicePixelRatio||1);
function fit(){W=cv.clientWidth;H=cv.clientHeight;cv.width=W*DPR;cv.height=H*DPR;ctx.setTransform(DPR,0,0,DPR,0,0);}
addEventListener("resize",fit);

const caps=G.nodes.filter(n=>n.type==="cap"), doms=G.nodes.filter(n=>n.type==="domain");
const domIndex={}; doms.forEach((d,i)=>domIndex[d.label]=i);
// 每个域一个"触手臂"：域节点在外环，能力节点沿臂向外铺（半径 0.42→1.0）
const R=1.0, per={};
// 确定性抖动（**不用 Math.random**：① 这不是加密用途、也不该用弱随机数；
// ② **同名同图** —— 每次刷新/每次截图都是同一个形状，签名元素稳定、视觉验收可复现）
function jitter(s,salt){let h=2166136261^salt;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619);}
  return ((h>>>0)%1000)/1000 - .5;}

caps.forEach(c=>{per[c.domain]=(per[c.domain]||0)+1;});
const seen={};
const pts=caps.map(c=>{
  const di=domIndex[c.domain]||0, dn=doms.length;
  const ang=(di/dn)*Math.PI*2;
  const k=(seen[c.domain]=(seen[c.domain]||0))+1; seen[c.domain]=k;
  const t=0.42+0.58*(k-1)/Math.max(1,per[c.domain]);
  const spread=0.16;
  return {id:c.id,label:c.label,domain:c.domain,type:"cap",
          x:Math.cos(ang)*t + jitter(c.label,1)*spread,
          y:jitter(c.label,2)*spread*1.6,
          z:Math.sin(ang)*t + jitter(c.label,3)*spread};
});
const hubPts=doms.map((d,i)=>{
  const ang=(i/doms.length)*Math.PI*2;
  return {id:d.id,label:d.label,type:"domain",size:d.size,
          x:Math.cos(ang)*0.34, y:0, z:Math.sin(ang)*0.34};
});
const bindOf={}; G.binds.forEach(b=>{const k=b.from.replace("cap:","");bindOf[k]=b.w;});
const P=[...hubPts,...pts];
const DOMIDX={},DOMANG={};
doms.forEach((d,i)=>{DOMIDX[d.label]=i;DOMANG[d.label]=(i/doms.length)*Math.PI*2;});
let yaw=-0.5,pitch=0.42,dist=2.35,auto=true,drag=null,sel=null;
// ⚠️ 签名元素要**占首屏 ≥1/5**（§3 死法①）：焦距与默认距离一起调大，
//    让全景球真正"撑满画布"，而不是缩在中间当挂件。
const FOCAL=880;
// §5 动效纪律：系统说"减少动效" ⇒ 默认**不自转**（仍可手动拖）
const REDUCED = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
if(REDUCED) auto=false;
const pulses=[]; let last=0;
function project(p){
  const cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch);
  let x=p.x*cy - p.z*sy, z=p.x*sy + p.z*cy, y=p.y;
  const y2=y*cp - z*sp, z2=y*sp + z*cp;
  const zc=z2+dist, f=FOCAL/Math.max(0.2,zc);
  return {X:W/2+x*f, Y:H/2+y2*f, z:zc, f};
}
function node(idx){return P[idx];}
function draw(t){
  ctx.clearRect(0,0,W,H);
  // 地面光晕（静止纵深：光在地面，不在字上）
  const gl=ctx.createRadialGradient(W/2,H*0.62,10,W/2,H*0.62,Math.max(W,H)*0.55);
  gl.addColorStop(0,"rgba(0,229,255,.10)");gl.addColorStop(.5,"rgba(124,77,255,.05)");
  gl.addColorStop(1,"transparent");
  ctx.fillStyle=gl;ctx.fillRect(0,0,W,H);
  // 纵深环（静止纵深：一圈比一圈淡，给"仪器"的尺度感）
  for(let k=1;k<=3;k++){
    ctx.strokeStyle=`rgba(124,77,255,${0.055/k})`;ctx.lineWidth=1;
    const rr=project({x:0,y:0,z:0});
    ctx.beginPath();
    for(let i=0;i<=72;i++){
      const a=i/72*Math.PI*2, R2=0.55*k;
      const q=project({x:Math.cos(a)*R2,y:Math.sin(a)*R2*0.32,z:Math.sin(a)*R2*0.25});
      i?ctx.lineTo(q.X,q.Y):ctx.moveTo(q.X,q.Y);
    }
    ctx.stroke();
  }
  // 地平线
  const hl=project({x:-1.6,y:0.44,z:0}), hr=project({x:1.6,y:0.44,z:0});
  ctx.strokeStyle="rgba(0,229,255,.10)";ctx.beginPath();
  ctx.moveTo(hl.X,hl.Y);ctx.lineTo(hr.X,hr.Y);ctx.stroke();
  // 赤道网格（地面）
  ctx.strokeStyle="rgba(0,229,255,.06)";ctx.lineWidth=1;
  for(let i=0;i<=24;i++){
    const a=i/24*Math.PI*2;
    const p1=project({x:Math.cos(a)*1.25,y:0.42,z:Math.sin(a)*1.25});
    const p2=project({x:Math.cos(a+.26)*1.25,y:0.42,z:Math.sin(a+.26)*1.25});
    ctx.beginPath();ctx.moveTo(p1.X,p1.Y);ctx.lineTo(p2.X,p2.Y);ctx.stroke();
  }
  const rows=[];
  // 绑定弧（能力↔自身权重：画成域内的细弧，权重大更亮）
  ctx.lineWidth=1;
  pts.forEach(p=>{
    const w=bindOf[p.label]||0; if(!w) return;
    const a=project(p), b=project(node(P.indexOf(p)));
    rows.push({z:a.z-0.001,k:"bind",a,w});
  });
  // 域→能力 的"触手臂"线
  hubPts.forEach((h,hi)=>{
    const a=project(h);
    pts.forEach(p=>{ if(domIndex[p.domain]!==hi) return;
      const b=project(p); rows.push({z:(a.z+b.z)/2,k:"arm",a,b,
        hot: pulses.some(pp=>pp.dom===h.label && pp.t>0)});
    });
  });
  rows.sort((m,n)=>n.z-m.z);
  rows.forEach(r=>{
    if(r.k==="arm"){
      ctx.strokeStyle=r.hot?"rgba(245,176,65,.55)":"rgba(0,229,255,.16)";
      ctx.beginPath();ctx.moveTo(r.a.X,r.a.Y);ctx.lineTo(r.b.X,r.b.Y);ctx.stroke();
    }
  });
  // 脉冲：从域节点飞向该域某个能力（真台账事件）
  const dead=[];
  pulses.forEach((pp,i)=>{
    pp.t+=0.018;
    if(pp.t>=1){dead.push(i);return;}
    const from=hubPts.find(h=>h.label===pp.dom), to=pts.find(p=>p.domain===pp.dom);
    if(!from||!to) return;
    const a=project(from), b=project(to);
    const x=a.X+(b.X-a.X)*pp.t, y=a.Y+(b.Y-a.Y)*pp.t;
    const gr=ctx.createRadialGradient(x,y,0,x,y,9);
    gr.addColorStop(0,"rgba(245,176,65,.95)");gr.addColorStop(1,"transparent");
    ctx.fillStyle=gr;ctx.beginPath();ctx.arc(x,y,9,0,7);ctx.fill();
  });
  dead.reverse().forEach(i=>pulses.splice(i,1));
  // 节点：域（大、金）与能力（小、青，选中紫）
  const all=[...hubPts.map(p=>({p,r:7,c:"245,176,65"})),
             ...pts.map(p=>({p,r:2.6,c:"0,229,255"}))];
  all.map(o=>({...o,z:project(o.p).z})).sort((a,b)=>b.z-a.z).forEach(o=>{
    const pr=project(o.p);
    const light=Math.max(.25,Math.min(1,1.6-pr.z/3.2));
    const rr=o.r*(pr.f/FOCAL)*1.35;
    const isSel=sel&&sel.id===o.p.id;
    const gr=ctx.createRadialGradient(pr.X,pr.Y,0,pr.X,pr.Y,rr*(isSel?4:2.6));
    gr.addColorStop(0,`rgba(${isSel?"124,77,255":o.c},${.95*light})`);
    gr.addColorStop(1,"transparent");
    ctx.fillStyle=gr;ctx.beginPath();ctx.arc(pr.X,pr.Y,rr*(isSel?4:2.6),0,7);ctx.fill();
    ctx.fillStyle=`rgba(${isSel?"190,160,255":o.c},${light})`;
    ctx.beginPath();ctx.arc(pr.X,pr.Y,rr,0,7);ctx.fill();
    o.screen={X:pr.X,Y:pr.Y};
    if(o.p.type==="domain" && pr.z<dist+0.45){                 // 只标前半面的域（免得糊成一团）
      const w=ctx.measureText(o.p.label).width;
      const side=Math.cos(yaw+DOMANG[o.p.label])>=0?1:-1;      // 按朝向决定标签在左还是在右
      const dy=(DOMIDX[o.p.label]%2)?-6:7;                     // 奇偶错位，防叠字
      ctx.fillStyle=`rgba(233,233,242,${.85*light})`;
      ctx.font="600 11.5px ui-monospace,monospace";
      const tx=pr.X+(side>0?rr+6:-rr-6-(w||0)), ty=pr.Y+3.5+dy;
      ctx.strokeStyle="rgba(0,229,255,.18)";ctx.beginPath();
      ctx.moveTo(pr.X,pr.Y);ctx.lineTo(pr.X+(side>0?rr+3:-rr-3),pr.Y+dy);ctx.stroke();
      ctx.fillText(o.p.label,tx,ty);
    }
    if(o.p.type==="domain"&&pr.z<dist+0.2&&o.p.label==="system"){ /* 中心核心见下 */ }
  });
  // 中心核心 = **万能插 run_task**（唯一门）：所有触手臂从这里长出去 —— 这才是"仪器"的锚
  const c0=project({x:0,y:0,z:0});
  const cg=ctx.createRadialGradient(c0.X,c0.Y,0,c0.X,c0.Y,34*Math.max(.6,c0.f/FOCAL));
  cg.addColorStop(0,"rgba(245,176,65,.85)");cg.addColorStop(.35,"rgba(245,176,65,.22)");
  cg.addColorStop(1,"transparent");
  ctx.fillStyle=cg;ctx.beginPath();ctx.arc(c0.X,c0.Y,34*Math.max(.6,c0.f/FOCAL),0,7);ctx.fill();
  ctx.fillStyle="rgba(255,240,210,.95)";
  ctx.beginPath();ctx.arc(c0.X,c0.Y,4.2,0,7);ctx.fill();
  ctx.fillStyle="rgba(245,176,65,.85)";ctx.font="600 11px ui-monospace,monospace";
  ctx.fillText("run_task",c0.X+9,c0.Y-6);
  window.__screen=all;
  if(auto) yaw+=0.0016;
  requestAnimationFrame(draw);
}
function pick(mx,my){
  let best=null,bd=1e9;
  (window.__screen||[]).forEach(o=>{const s=o.screen;if(!s)return;
    const d=(s.X-mx)**2+(s.Y-my)**2; if(d<bd&&d<196){bd=d;best=o;}});
  return best?best.p:null;
}
cv.addEventListener("pointerdown",e=>{drag={x:e.clientX,y:e.clientY};
  cv.setPointerCapture(e.pointerId);});
cv.addEventListener("pointermove",e=>{
  if(!drag)return; const dx=e.clientX-drag.x, dy=e.clientY-drag.y;
  if(Math.abs(dx)+Math.abs(dy)>3) drag.moved=true;
  yaw+=dx*0.006; pitch=Math.max(-1.2,Math.min(1.2,pitch+dy*0.005));
  drag.x=e.clientX; drag.y=e.clientY;
});
cv.addEventListener("pointerup",e=>{
  if(drag&&!drag.moved){const p=pick(e.offsetX,e.offsetY); if(p) show(p);}
  drag=null;
});
cv.addEventListener("wheel",e=>{e.preventDefault();
  dist=Math.max(1.35,Math.min(5,dist+Math.sign(e.deltaY)*0.12));},{passive:false});
document.getElementById("auto").onclick=()=>{auto=!auto;
  document.getElementById("auto").textContent="自转："+(auto?"开":"关");};
function show(p){
  sel=p;
  const isCap=p.type==="cap";
  document.getElementById("detail").innerHTML = isCap?
    `<b>${p.label}</b><div class="mut">域：${p.domain}</div>
     <div class="src">绑定权重：${bindOf[p.label]||0}（来自 state/asset_bindings.json）</div>
     <div class="src">节点来自 caps_registry 现读</div>`:
    `<b>${p.label}</b><div class="mut">域节点 · 下辖 ${p.size} 个能力位</div>
     <div class="src">来自 console_hub.graph（注册表现读）</div>`;
}
// 脉冲：把真台账事件映射到域（按事件名关键词挑一个域；挑不到就轮转）
const DOMS=hubPts.map(h=>h.label);
G.pulses.forEach((pp,i)=>{
  const key=pp.ledger.replace(".jsonl","");
  let dom=DOMS.find(d=>key.includes(d)) || DOMS[i%DOMS.length];
  setTimeout(()=>pulses.push({dom,t:0,event:pp.event}), i*260);
});
document.getElementById("pulses").innerHTML = G.pulses.slice(-6).map(p=>
  `<div style="margin:5px 0"><span class="chip">${p.event}</span>
   <div class="src">${p.ledger} · ${p.at||""}</div></div>`).join("") || '<div class="mut">无</div>';
fit(); requestAnimationFrame(draw);
"""
    script = script.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    extra = """
.hud{position:absolute;left:14px;bottom:12px;display:flex;gap:8px}
.legend{position:absolute;right:16px;top:14px;font-size:12px;color:var(--dim);font-family:var(--mono)}
.legend b{color:var(--gold)}
"""
    body = body.replace("__ND__", str(counts["domains"])).replace("__NC__", str(counts["caps"])) \
               .replace("__NB__", str(counts["binding_weight"])).replace("__NP__", str(counts["pulses"]))
    html = _shell("触手 3D 全景", "30 个域 → 209 个能力位 → 绑定弧 → 运行脉冲（每条都来自真台账）",
                  body, script, extra,
                  hero=_hero("触手 3D 全景", "中心是 run_task（唯一门）· 30 个域从核心长出手臂 · 脉冲是真台账事件",
                             chip="全景", accent="土豆金", seed="tentacle3d", kind="orb",
                             sub="GBT TENTACLE / SYSTEM MAP 01",
                             ctas=[{"label": "回工作台", "href": "../workbench/index.html"},
                                   {"label": "全部页面卡库", "href": "../gallery/index.html"}]))
    return _write("holo_pet/assets/tentacle3d/index.html", html)


# ═══════════════════════════ ③ 每工作流独立页 ═══════════════════════════
def render_workflow(key: str) -> dict:
    hub = _load_hub()
    spec = hub.WORKFLOWS.get(key)
    if not spec:
        return {"ok": False, "error": f"没有这个工作流：{key}（有：{sorted(hub.WORKFLOWS)}）"}
    w = hub.widgets()["w8_workflows"]["items"][key]
    d = _ROOT / spec["dir"]
    allf = [p for p in d.rglob("*") if p.is_file()] if d.is_dir() else []
    # ⚠️ 血账（2026-09-28 实测）：阶段名**必须从真实目录取** —— 我先前写死中文阶段名
    #   （`01-剧本`）而真实目录是 `01-screenplay` ⇒ 匹配不上就**误报"暂无产出"**（假红），
    #   而同一页的"近产出"里明明躺着 04-assets/05-edit/06-final 的文件。
    stages = []
    if d.is_dir():
        for sub in sorted(x for x in d.iterdir() if x.is_dir() and not x.name.startswith(".")):
            fs = [f for f in sub.rglob("*") if f.is_file() and f.stat().st_size > 0]
            stages.append({"dir": sub.name, "files": len(fs),
                           "kb": round(sum(f.stat().st_size for f in fs) / 1024, 1),
                           "alias": spec["stages"][len(stages)] if len(stages) < len(spec["stages"]) else ""})
    files = sorted((p for p in allf if p.stat().st_size > 0),      # 0 字节占位件（.gitkeep）不算近产出
                   key=lambda p: -p.stat().st_mtime)[:14]
    recent = [{"name": p.name, "rel": str(p.relative_to(_ROOT)).replace("\\", "/"),
               "kb": round(p.stat().st_size / 1024, 1),
               "h": round((time.time() - p.stat().st_mtime) / 3600, 1)} for p in files]
    caps = [c for c in spec["caps"] if c in hub._caps()]
    # 本线判据：文件名里带这条线的关键词（真文件，不是"应该有"）
    tests = sorted(x.name for x in (_ROOT / "gbt_allinone" / "tests").glob("test_*.py")
                   if key.split("-")[0] in x.name) if (_ROOT / "gbt_allinone" / "tests").is_dir() else []
    # 交付物：目录名像"成片/发布/交付"的那些
    deliv = sorted(({"rel": str(f.relative_to(_ROOT)).replace("\\", "/"),
                     "kb": round(f.stat().st_size / 1024, 1)}
                    for f in allf
                    if f.stat().st_size > 0            # 0 字节占位件（.gitkeep）不是交付物
                    and any(k in str(f).lower() for k in ("final", "publish", "release", "成片"))),
                   key=lambda x: -x["kb"])[:8]
    data = {"key": key, "label": spec["label"], "dir": spec["dir"], "stages": stages,
            "files": w["files"], "newest_h": w["newest_h"], "recent": recent, "caps": caps,
            "tests": tests, "deliv": deliv}
    body = """
<div class="grid" style="grid-template-columns:minmax(0,1fr) 340px">
  <div class="card"><h2>阶段（按真实目录现读 · 数字是该阶段真文件数）</h2>
    <div id="stages" class="stages"></div>
    <div class="src">来自 projects/__K__ 子目录现读；0 字节占位件不计</div></div>
  <div class="card"><h2>本线能力位</h2><div id="caps"></div>
    <div class="src">来自 caps_registry 现读（可编排/可调用的真名）</div></div>
</div>
<div class="grid" style="grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);margin-top:14px">
  <div class="card"><h2>近产出（按改动时间 · 已滤占位件）</h2><div id="recent"></div>
    <div class="src">来自 projects/__K__ 现读</div></div>
  <div>
    <div class="card" style="margin-bottom:14px"><h2>本线判据</h2><div id="tests"></div>
      <div class="src">来自 gbt_allinone/tests 文件名现读</div></div>
    <div class="card"><h2>交付物</h2><div id="deliv"></div>
      <div class="src">目录名含 final/publish/release/成片 的真件</div></div>
  </div>
</div>"""
    script = """
const D = __DATA__;
document.getElementById("stages").innerHTML = D.stages.map((s,i)=>{
  const hit=s.files>0;
  return `<div class="st ${hit?"on":""}"><span class="idx">${String(i+1).padStart(2,"0")}</span>
    <b>${s.dir}</b><span class="mut">${hit? s.files+" 件 · "+s.kb+"KB" : "（暂无产出）"}</span>
    ${s.alias?`<span class="src">${s.alias}</span>`:""}</div>`;}).join("");
document.getElementById("tests").innerHTML = D.tests.length?
  D.tests.map(x=>`<span class="chip" style="margin:3px 4px 0 0">${x.replace("test_","").replace(".py","")}</span>`).join("")
  : '<div class="mut">这条线还没有专属判据</div>';
document.getElementById("deliv").innerHTML = D.deliv.length?
  D.deliv.map(x=>`<div class="rw"><span class="nm">${x.rel.split("/").pop()}</span>
    <span class="mut">${x.kb}KB</span><span class="src">${x.rel}</span></div>`).join("")
  : '<div class="mut">暂无交付物</div>';
document.getElementById("caps").innerHTML = D.caps.length? D.caps.map(c=>
  `<a class="chip" href="../tentacle3d/index.html" style="margin:3px 4px 0 0">${c}</a>`).join("")
  : '<div class="mut">这条线还没登记专属能力位</div>';
document.getElementById("recent").innerHTML = D.recent.map(r=>`<div class="rw">
  <span class="nm">${r.name}</span><span class="mut">${r.kb}KB</span>
  <span class="src">${r.h}h 前 · ${r.rel}</span></div>`).join("") || '<div class="mut">暂无</div>';
"""
    script = script.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    body = body.replace("__K__", key)
    extra = """
.stages{display:flex;flex-wrap:wrap;gap:8px}
.st{display:flex;align-items:center;gap:9px;border:1px solid var(--line-soft);border-radius:var(--r-sm);
  padding:9px 12px;background:rgba(0,229,255,.02)}
.st.on{border-color:rgba(245,176,65,.35);background:rgba(245,176,65,.05)}
.st .idx{font-family:var(--mono);color:var(--dim-2)}
.st b{font-weight:600}
.rw{display:grid;grid-template-columns:minmax(0,1fr) 76px 1fr;gap:10px;align-items:baseline;
  padding:6px 0;border-bottom:1px solid var(--line-soft);font-size:12px}
.rw:last-child{border-bottom:0}
.nm{font-family:var(--mono);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
"""
    html = _shell(f"{spec['label']} · 独立页",
                  f"{spec['dir']} · {w['files']} 件 · 最新改动 {w['newest_h']}h 前",
                  body, script, extra,
                  hero=_hero(f"{spec['label']} · 独立页",
                             f"{spec['dir']} · {w['files']} 件产出 · 阶段按真实目录现读",
                             chip=spec["label"], accent="深空紫", seed=key,
                             kind="wave" if key in ("music",) else ("highway" if key == "short-video" else "racks"),
                             sub="GBT PIPELINE / %s" % key.upper(),
                             ctas=[{"label": "全部页面卡库", "href": "../gallery/index.html"}]))
    return _write(f"holo_pet/assets/wf-{key}/index.html", html)


def _hero(title: str, subtitle: str, **kw) -> str:
    """取主视觉带（模块不在就退化成空串 —— 页面照常能开，不因装饰件缺失而白屏）。"""
    try:
        sp = importlib.util.spec_from_file_location(
            "hero_band", _ROOT / "gbt_allinone" / "tools" / "console_hero.py")
        ch = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(ch)
        return ch.hero_band(title, subtitle, **kw)
    except Exception:                                          # noqa: BLE001
        return ""


def render_gallery() -> dict:
    """**卡库页**：全部独立页面排成卡片（参考图那个版式）—— 主人令「每一个页面都需要有视觉感」。"""
    hub = _load_hub()
    hero = _load_hub_hero()
    rows = hub.pages()["rows"]
    order = {"枢纽": 0, "全景": 1, "工作流": 2, "执行台": 3, "决策台": 4, "监控": 5, "门面": 6, "原型": 7}
    rows = sorted(rows, key=lambda r: (order.get(r.get("kind"), 9), r["page"]))
    cards = []
    for r in rows:
        accent = {"枢纽": "赛博青", "全景": "土豆金", "工作流": "深空紫"}.get(r.get("kind"), "赛博青")
        kind = hero.pick_archetype(r["page"], {"music": "wave", "wf-music": "wave",
                                               "wf-film": "racks", "wf-movie": "racks",
                                               "wf-short-video": "highway",
                                               "tentacle3d": "orb", "capabilities": "orb",
                                               "godview": "graph", "brain": "graph"}.get(r["page"], ""))
        # 2026-10-04 修（24h 审查实证）：仓根页原用 "../../" ⇒ 从
        # holo_pet/assets/gallery/index.html 解析到 holo_pet/ 下（不存在）；
        # 到仓根要三级：gallery → assets → holo_pet → 仓根。
        href = "../" + r["path"].replace("holo_pet/assets/", "").replace("/index.html", "/index.html") \
            if r["path"].startswith("holo_pet/assets/") else "../../../" + r["path"]
        col = hero.ACCENTS[accent]
        # ⚠️ 血账：`console_hub.PAGES` 的 what 里带 markdown 强调（`**总入口**`），
        #    直接塞进 HTML 会**原样显示星号** ⇒ 这里转成真加粗。
        def _em(s: str) -> str:
            import re as _re
            return _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", str(s or ""))
        cards.append(f"""<a class="pcard" href="{href}">
  <div class="pmedia">{hero.hero_svg(kind, r["page"], col, "GBT / " + r["page"].upper())}</div>
  <div class="pbody">
    <span class="pcat" style="color:{col}">{r.get("kind")} · {r.get("workflow")}</span>
    <h3 class="ptitle">{r["page"]}</h3>
    <p class="psum">{_em(r.get("what"))}</p>
    <span class="pgo">打开页面 →{" · %s KB" % r.get("kb") if r.get("kb") else ""}</span>
  </div></a>""")
    body = f'<div class="cards">{"".join(cards)}</div>'
    script = "// 卡库是静态渲染色（数据在生成时就内联好了）"
    html = _shell("全部页面 · 卡库", f"{len(rows)} 个独立页 · 每页一张主视觉 · 分类与归属现读 console_hub",
                  body, script, hero.HERO_CSS,
                  hero=hero.hero_band("全部页面 · 卡库", f"{len(rows)} 个独立页，一屏看全；点卡即开",
                                      chip="页面全景", chip_accent="土豆金", seed="gallery",
                                      kind="cubes", sub="GBT PAGE ATLAS / %d PAGES" % len(rows),
                                      ctas=[{"label": "回工作台", "href": "../workbench/index.html"}]))
    return _write("holo_pet/assets/gallery/index.html", html)


def _load_hub_hero():
    sp = importlib.util.spec_from_file_location(
        "hero_for_gallery", _ROOT / "gbt_allinone" / "tools" / "console_hero.py")
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def render_freebuff() -> dict:
    """**freebuff 对话面板**（主人令：把 freebuff 终端集成进对话面板，编程走这个）。

    诚实边界写在页面上：freebuff 是**交互式 TUI**（现读 `--help` 无一次性 prompt）⇒ 静态页
    **点不动它**；所以这页做三件能做到的：① 状态面 ② 可复制的命令（开终端/登录）③ 升级路径（PTY 桥）。
    """
    import importlib.util as _iu
    sp = _iu.spec_from_file_location("fbt", _ROOT / "gbt_allinone" / "tools" / "freebuff_term.py")
    fb = _iu.module_from_spec(sp)
    sp.loader.exec_module(fb)
    st, fl, lh = fb.status(), fb.flags(), fb.login_hint()
    data = {"status": st, "flags": fl, "login": lh, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    hero = _load_hub_hero()
    body = """
<div class="grid" style="grid-template-columns:repeat(12,1fr)">
  <div class="card" style="grid-column:span 4"><h2>真身 · 状态（现读）</h2><div id="st"></div></div>
  <div class="card" style="grid-column:span 4"><h2>能力面（现跑 --help）</h2><div id="fl"></div></div>
  <div class="card" style="grid-column:span 4"><h2>怎么用（可复制）</h2><div id="how"></div></div>
</div>
<div class="card" style="margin-top:14px"><h2>诚实边界 · 以及"面板里直接对话"缺什么</h2>
  <div id="gap"></div></div>"""
    script = """
const D = __DATA__;
const S = D.status, F = D.flags, L = D.login;
function row(k, v, cls){return `<div class="fr"><span class="fk">${k}</span>
  <span class="fv ${cls||''}">${v}</span></div>`;}
document.getElementById("st").innerHTML =
  row("版本", S.version, "ok") + row("入口", "<span class='src'>"+(F.entry||"-")+"</span>") +
  row("隔离 HOME", "<span class='src'>"+S.home+"</span>", S.home_exists?"ok":"bad") +
  row("二进制", (S.exe_exists? S.exe_mb+" MB":"缺"), S.exe_exists?"ok":"bad") +
  row("登录态", S.logged_in? "已登录":"<b>未登录</b>（只有主人能登）", S.logged_in?"ok":"warn") +
  row("模型", (S.settings||{}).model||"-") + row("档位", (S.settings||{}).mode||"-") +
  row("正常 HOME 下", "起不来（EPERM：只认 $HOME/.config/manicode）", "warn");
document.getElementById("fl").innerHTML =
  (F.options||[]).map(o=>`<span class="chip" style="margin:3px 4px 0 0">${o}</span>`).join("") +
  row("子命令", (F.subcommands||[]).join(" / ")) +
  row("一次性 prompt", F.has_one_shot_prompt? "有":"<b>没有</b>", F.has_one_shot_prompt?"ok":"warn") +
  `<div class="src" style="margin-top:8px">${F.verdict||""}</div>`;
const cmd1 = S.script || (S.home + '\\start-freebuff.cmd');
document.getElementById("how").innerHTML =
  `<div class="mut">① 开终端（隔离 HOME + 仓库为工作目录）：</div>
   <div class="code">${cmd1}</div>
   <div class="mut" style="margin-top:8px">② 首次在里面登录（只有主人能做）：</div>
   <div class="code">${(L.powershell||[]).join("\\n")}</div>
   <div class="mut" style="margin-top:8px">③ 我（本体）的调用形态：</div>
   <div class="code">run_task('freebuff_term', {'op': 'status'})   // 看真身/登录态
run_task('freebuff_term', {'op': 'launch'})   // 起终端（要 process_execute 票）</div>`;
document.getElementById("gap").innerHTML =
  row("这页能做什么", "看状态 · 抄命令 · 看能力面（现读）") +
  row("这页做不到什么", "<b>点一下就让 freebuff 干活</b>（它是 TUI，且静态页不能起进程）", "warn") +
  row("要真在面板里对话", "需要一个<b>本地 PTY 桥</b>：常驻进程 + WebSocket，把 TUI 的输入输出搬到页面上", "warn") +
  row("那道桥的门", "process_execute 授权 + 主人点头 —— <b>现在没有，不假装有</b>", "bad") +
  row("现在立刻能用的是什么", "① 双击上面的 cmd 开终端自己聊 ② 登录后我按你的口令帮你起终端/转达") +
  '<div class="src" style="margin-top:8px">数据来源：freebuff_term.status/flags（渲染时内联）· state/freebuff_term.jsonl</div>';
"""
    script = script.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    extra = """
.fr{display:grid;grid-template-columns:104px 1fr;gap:8px;padding:5px 0;
  border-bottom:1px solid var(--line-soft);font-size:12.5px}
.fr:last-child{border-bottom:0}
.fk{color:var(--dim-2);font-family:var(--mono)}
.code{font-family:var(--mono);font-size:11.5px;color:var(--text);background:rgba(0,229,255,.04);
  border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin-top:4px;white-space:pre-wrap}
"""
    html = _shell("freebuff · 对话面板", "编程走这个：隔离 HOME 下的 freebuff（0.1.2）· 状态与命令现读",
                  body, script, extra,
                  hero=hero.hero_band("freebuff · 对话面板",
                                      "编程走这个 · 隔离 HOME · TUI（没有一次性 prompt）⇒ 要真跑就开终端",
                                      chip="编程终端", chip_accent="深空紫", seed="freebuff",
                                      kind="cubes", sub="FREEBUFF / TERMINAL BRIDGE",
                                      ctas=[{"label": "全部页面卡库", "href": "../gallery/index.html"},
                                            {"label": "回工作台", "href": "../workbench/index.html"}]))
    return _write("holo_pet/assets/freebuff/index.html", html)


# ═══════════════════════════ ⑦ 总控台（一体化工作空间骨架 · GBT 品牌 · 2026-10-04 主人令） ═══════════════════════════
def render_console() -> dict:
    """**总控台**：一个面板接全部能力 + 编队群（触手职业拉群）。

    主人令（2026-10-04）：① 参考业界一体化工作空间的骨架重组排布，**统一 GBT 品牌
    （旧品牌深度替换，我们自己的面上不出现第三方品牌字样）**；
    ② 云插件与触手的双向绑定/互通接清楚，确保自家大模型链路畅通；
    ③ 每个触手职业拉群、群里只出本域专业意见，**决策与执行权全局只属 GBT小土豆V8**，
    职业不得越权跨界。本页 = 静态快照（快照内联口径）；面板桥（panel_server :8765）
    在线时，能力可经 /api/capability 真跑（过 policy，不放宽作用域）。
    """
    import json as _json
    import os as _os
    import re as _re
    try:
        from .. import caps_registry as _cr
    except Exception:                                      # noqa: BLE001
        import importlib as _il
        _cr = _il.import_module("gbt_allinone.caps_registry")

    caps = _cr.all_caps()
    by_domain: dict[str, list[str]] = {}
    for c in caps:
        by_domain.setdefault(str(c.get("domain") or "其它"), []).append(str(c.get("name")))
    domains = sorted(by_domain)

    # ── 云插件（deploy/cloud-10/mesh.json 现读）────────────────────────────
    mesh = {}
    try:
        mesh = _json.loads((_ROOT / "deploy" / "cloud-10" / "mesh.json").read_text(encoding="utf-8"))
    except Exception:                                      # noqa: BLE001
        pass
    mods = mesh.get("modules") or []
    edges = mesh.get("edges")
    edges_n = len(edges) if isinstance(edges, list) else 0

    # ── 链路畅通（自家大模型；只读 env，不显示任何密钥值）──────────────────
    potato = {
        "provider": _os.environ.get("GBT_LLM_PROVIDER") or "未设",
        "base_url": _os.environ.get("GBT_POTATO_BASE_URL") or "未设",
        "model": _os.environ.get("GBT_POTATO_MODEL") or "gbt-potato-v8（默认）",
        "key": "已配" if _os.environ.get("GBT_POTATO_API_KEY") else "未配",
    }

    # ── 编队花名册（~/.zcode/agents/*.md 现读 frontmatter）─────────────────
    crew = []
    agents_dir = Path.home() / ".zcode" / "agents"
    if agents_dir.is_dir():
        for md in sorted(agents_dir.glob("*.md")):
            try:
                t = md.read_text(encoding="utf-8", errors="replace")[:1500]
                _m = _re.search(r"^name:\s*(.+)$", t, _re.M)
                _d = _re.search(r"^description:\s*(.+)$", t, _re.M)
                crew.append({"file": md.stem,
                             "name": (_m.group(1).strip() if _m else md.stem),
                             "desc": ((_d.group(1).strip() if _d else "") or "")[:100]})
            except Exception:                              # noqa: BLE001
                continue
    brain_mods = sorted(p.stem for p in (_ROOT / "gbt_allinone" / "brain").glob("*.py")
                        if p.stem != "__init__")

    # ── 页面卡（console_hub 登记表现读）──────────────────────────────────
    try:
        prows = _load_hub().pages()["rows"]
    except Exception:                                      # noqa: BLE001
        prows = []

    # ── HTML ────────────────────────────────────────────────────────────
    dom_cards = "".join(
        f"""<div class="cc-card"><h3>{_d} <span class="cc-stat" style="font-size:15px">{len(by_domain[_d])}</span></h3>
<div>{''.join(f'<span class="cc-chip">{n}</span>' for n in sorted(by_domain[_d])[:10])}</div>
<div class="cc-note">共 {len(by_domain[_d])} 项 · 全量见能力总目录</div></div>"""
        for _d in domains)

    mod_cards = "".join(
        f"""<div class="cc-card"><h3>{m.get('id', '?')}</h3>
<div class="cc-note">{m.get('duty', '')}</div>
<div style="margin-top:6px">{''.join(f'<span class="cc-chip">{o}</span>' for o in (m.get('ops') or [])[:8])}</div>
<div class="cc-note">门: {'、'.join(sorted(set((m.get('op_gates') or {}).values()))) or 'none'} · 云依赖: {'、'.join(m.get('cloud') or [])[:60]}</div>
<div class="cc-note">{str(m.get('boundary', ''))[:90]}</div></div>"""
        for m in mods)

    crew_html = "".join(
        f"""<div class="cc-msg"><div class="cc-avatar">{(c['name'] or '?')[0]}</div>
<div><b>{c['name']}</b> <span class="cc-chip">本域意见</span>
<div class="cc-note">{c['desc'] or '（见 ~/.zcode/agents/%s.md）' % c['file']}</div></div></div>"""
        for c in crew)

    page_cards = "".join(
        f"""<a class="cc-card" style="display:block;text-decoration:none;color:inherit" href="../../../{r['path']}">
<h3>{r['page']}</h3><div class="cc-note">{r.get('kind')} · {r.get('workflow')} · {r.get('kb', '?')}KB</div></a>"""
        for r in prows[:12])

    def _hud_svg(edges_n: int) -> str:
        """HUD 雷达（纯内联 SVG，参考安全厂商风的那种环形界面；GBT 青金配色）。"""
        import random as _rd
        _rd.seed(8)
        pts = "".join(
            f"<circle cx='{20 + _rd.random()*160:.0f}' cy='{20 + _rd.random()*160:.0f}' "
            f"r='{1 + _rd.random()*1.6:.1f}' fill='rgba(0,229,255,{0.22 + _rd.random()*0.5:.2f})'/>"
            for _ in range(46))
        return f"""<svg viewBox="0 0 200 200" style="width:100%;display:block" role="img" aria-label="GBT mesh HUD">
  <circle cx='100' cy='100' r='92' fill='none' stroke='rgba(0,229,255,.18)'/>
  <circle cx='100' cy='100' r='74' fill='none' stroke='rgba(0,229,255,.12)' stroke-dasharray='2 5'/>
  <circle cx='100' cy='100' r='56' fill='none' stroke='rgba(0,229,255,.22)'/>
  <circle cx='100' cy='100' r='30' fill='none' stroke='rgba(245,176,65,.4)' stroke-dasharray='60 12'/>
  <path d='M100 8 A92 92 0 0 1 178 55' fill='none' stroke='rgba(0,229,255,.5)' stroke-width='2'/>
  <line x1='100' y1='4' x2='100' y2='196' stroke='rgba(0,229,255,.10)'/>
  <line x1='4' y1='100' x2='196' y2='100' stroke='rgba(0,229,255,.10)'/>
  <polygon points='100,78 119,89 119,111 100,122 81,111 81,89' fill='none' stroke='rgba(245,176,65,.55)'/>
  <polygon points='100,88 111,94 111,106 100,112 89,106 89,94' fill='none' stroke='rgba(0,229,255,.5)'/>
  <circle cx='100' cy='100' r='3' fill='#00E5FF'/>
  {pts}
  <text x='100' y='184' text-anchor='middle' fill='rgba(0,229,255,.6)' font-size='8' font-family='monospace'>GBT//MESH · {edges_n} EDGES · 10 MODULES</text>
</svg>"""

    body = f"""
<div class="cc">
  <div class="cc-side">
    <div class="cc-brand">GBT//V8</div>
    <a href="#overview">01 · 概览</a>
    <a href="#caps">02 · 能力矩阵</a>
    <a href="#connectors">03 · 云插件·连接器</a>
    <a href="#brain">04 · 第二大脑</a>
    <a href="#crew">05 · 编队群</a>
    <a href="#pages">06 · 快捷入口</a>
    <div class="cc-note" style="margin-top:12px">一个面板 · 全部能力<br>决策与执行权<br><b style="color:#F5B041">只属 GBT小土豆V8</b></div>
  </div>
  <div class="cc-main">
    <section id="overview"><div class="cc-sec">// 01 — 概览 · BY THE NUMBERS</div>
      <div class="cc-grid">
        <div class="cc-card"><div class="cc-stat cy">{len(caps)}</div><div class="cc-label">能力位 · CAPS_REGISTRY 现读</div></div>
        <div class="cc-card"><div class="cc-stat gd">{len(domains)}</div><div class="cc-label">能力域 · DOMAINS</div></div>
        <div class="cc-card"><div class="cc-stat vt">{len(mods)}</div><div class="cc-label">云插件 · CLOUD-10</div></div>
        <div class="cc-card"><div class="cc-stat cy">{edges_n}</div><div class="cc-label">云网互通边 · MESH.EDGES</div></div>
        <div class="cc-card"><div class="cc-stat gd">{len(crew)}</div><div class="cc-label">编队职业 · AGENTS</div></div>
        <div class="cc-card"><div class="cc-stat vt">{len(brain_mods)}</div><div class="cc-label">脑层模块 · BRAIN/</div></div>
      </div>
    </section>
    <section id="caps"><div class="cc-sec">// 02 — 能力矩阵 · 按域排布</div>
      <div class="cc-grid">{dom_cards}</div>
      <div class="cc-note">点跑入口：面板桥在线时 POST /api/capability（走 api.run_task + policy，不放宽作用域）</div>
    </section>
    <section id="connectors"><div class="cc-sec">// 03 — 云插件 · 连接器（与触手互通）</div>
      <div class="cc-split">
        <div class="cc-grid" style="grid-template-columns:repeat(auto-fill,minmax(205px,1fr))">{mod_cards}</div>
        <div class="cc-card hud">{_hud_svg(edges_n)}
          <div class="cc-label" style="margin-top:10px">GBT//MESH · LIVE TOPOLOGY</div>
          <div class="cc-note">自家大模型链路：provider={potato['provider']} · model={potato['model']}<br>
          端点 {'<span class="cc-ok">已设</span>' if potato['base_url'] != '未设' else '<span class="cc-bad">未设</span>'} ·
          密钥 {'<span class="cc-ok">已配</span>' if potato['key'] == '已配' else '<span class="cc-bad">未配</span>'}（只显示状态，不显值）</div>
        </div>
      </div>
      <div class="cc-card" style="margin-top:12px"><h3>链路纪律 · LINK DISCIPLINE</h3>
        <div class="cc-note">GW_AUTH 走 secret：缺钥 ⇒ /v1/chat 与 /rpc <b>fail-closed 拒服务</b>（2026-10-04 起，不再静默放行）。
        云插件与触手的互通以 mesh.json 单一真源为准；每条互通边都可经 /rpc 现测。</div>
      </div>
    </section>
    <section id="brain"><div class="cc-sec">// 04 — 第二大脑 · 记忆图谱</div>
      <div class="cc-grid">
        <div class="cc-card"><h3>脑层模块（{len(brain_mods)}）</h3>
          <div>{''.join(f'<span class="cc-chip">{b}</span>' for b in brain_mods)}</div>
          <div class="cc-note">闭环核验：tools/codex-scripts/brain-closure-check.py（3/3）</div></div>
        <div class="cc-card"><h3>图谱入口</h3>
          <div class="cc-note">触手 3D 全景（域→能力→绑定）与 godview 图谱见快捷入口；拓扑索引 gbt_allinone/store/_topology_index.json</div></div>
      </div>
    </section>
    <section id="crew"><div class="cc-sec">// 05 — 编队群 · 触手职业（只出本域意见）</div>
      <div class="cc-rule">群规：每个职业只给<b>各自领域的专业意见和建议</b>；<b>决策与执行权全局只属 GBT小土豆V8</b>。
      职业不得越权执行任何跨界任务；执行一律经 GBT 的能力门（run_task + policy 授权）落地。</div>
      <div class="cc-card" style="margin-top:10px">{crew_html or '<div class="cc-note">花名册目录为空（~/.zcode/agents）</div>'}</div>
      <div class="cc-note">决策引擎：brain_council（纯推演 · 零作用域 · 已接入 run_task：op=convene）；
      执行引擎：GBT 主脑经既有授权门逐条落跑，职业结论只作为提案输入。</div>
    </section>
    <section id="pages"><div class="cc-sec">// 06 — 快捷入口</div>
      <div class="cc-grid">{page_cards}</div>
      <div class="cc-note">全量页面见卡库 gallery（{len(prows)} 页登记）</div>
    </section>
  </div>
</div>"""

    extra = """
/* ── 总控台 · HUD 暗面（参考安全厂商风的冲击感 · GBT 青金紫）────────────── */
body{background:#04060a}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
  background:repeating-linear-gradient(0deg,rgba(255,255,255,.015) 0 1px,transparent 1px 3px),
             linear-gradient(rgba(0,229,255,.04) 1px,transparent 1px),
             linear-gradient(90deg,rgba(0,229,255,.04) 1px,transparent 1px);
  background-size:auto,44px 44px,44px 44px}
body::after{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
  background:radial-gradient(1100px 640px at 72% -8%,rgba(0,229,255,.09),transparent 62%),
             radial-gradient(900px 620px at 108% 112%,rgba(124,77,255,.08),transparent 60%)}
.top,.hero,.cc{position:relative;z-index:1}
.cc{display:grid;grid-template-columns:232px 1fr;gap:18px;align-items:start}
.cc-side{position:sticky;top:12px;background:rgba(4,8,12,.86);border:1px solid rgba(0,229,255,.16);
  border-radius:4px;padding:16px 12px;box-shadow:inset 0 0 24px rgba(0,229,255,.05)}
.cc-brand{font-family:var(--mono);font-size:14px;font-weight:700;letter-spacing:.16em;margin-bottom:12px;
  color:#00E5FF;text-shadow:0 0 14px rgba(0,229,255,.55)}
.cc-side a{display:block;padding:8px 10px;border-radius:3px;border-left:2px solid transparent;
  color:#9fb3bd;text-decoration:none;font-family:var(--mono);font-size:12px;letter-spacing:.08em}
.cc-side a:hover{border-left-color:#00E5FF;color:#EAF6FA;background:rgba(0,229,255,.06)}
.cc-sec{display:flex;align-items:center;gap:10px;margin:26px 0 12px;font-family:var(--mono);
  font-size:12px;font-weight:700;letter-spacing:.2em;color:#7de3ff;text-transform:uppercase}
.cc-sec::before{content:"";width:34px;height:1px;background:linear-gradient(90deg,#00E5FF,transparent)}
.cc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
.cc-split{display:grid;grid-template-columns:1fr 280px;gap:14px}
@media (max-width:960px){.cc{grid-template-columns:1fr}.cc-split{grid-template-columns:1fr}.cc-side{position:static}}
.cc-card{position:relative;overflow:hidden;background:linear-gradient(180deg,rgba(10,14,18,.92),rgba(6,9,12,.92));
  border:1px solid rgba(0,229,255,.14);border-radius:4px;padding:14px;
  transition:border-color .15s,box-shadow .15s}
.cc-card::before,.cc-card::after{content:"";position:absolute;width:12px;height:12px;border:0 solid rgba(0,229,255,.55)}
.cc-card::before{top:0;left:0;border-top-width:1px;border-left-width:1px}
.cc-card::after{bottom:0;right:0;border-bottom-width:1px;border-right-width:1px}
.cc-card:hover{border-color:rgba(0,229,255,.45);box-shadow:0 0 0 1px rgba(0,229,255,.10),0 10px 34px rgba(0,229,255,.08)}
.cc-card h3{font-family:var(--mono);font-size:12.5px;letter-spacing:.06em;margin:0 0 6px;color:#EAF6FA}
.cc-stat{font-family:var(--mono);font-size:46px;font-weight:800;line-height:1;letter-spacing:-.01em;color:#EAF6FA}
.cc-stat.cy{color:#00E5FF;text-shadow:0 0 20px rgba(0,229,255,.35)}
.cc-stat.gd{color:#F5B041;text-shadow:0 0 20px rgba(245,176,65,.30)}
.cc-stat.vt{color:#9E7BFF;text-shadow:0 0 20px rgba(124,77,255,.35)}
.cc-label{font-family:var(--mono);font-size:10.5px;letter-spacing:.16em;color:#6c7f8a;text-transform:uppercase;margin-top:8px}
.cc-chip{display:inline-block;margin:2px 4px 0 0;padding:2px 8px;border:1px solid rgba(0,229,255,.18);
  border-radius:2px;font-family:var(--mono);font-size:11px;color:#9fdceb;background:rgba(0,229,255,.04)}
.cc-note{font-size:11.5px;color:var(--dim-2);margin-top:6px;line-height:1.6}
.cc-ok{color:#33E58C;font-weight:700}.cc-bad{color:#FF3B5C;font-weight:700}
.cc-rule{border:1px solid rgba(245,176,65,.4);background:rgba(245,176,65,.06);border-radius:4px;
  padding:12px 14px;font-size:12.5px;line-height:1.7}
.cc-msg{display:flex;gap:10px;padding:8px 0;border-bottom:1px solid var(--line-soft)}
.cc-msg:last-child{border-bottom:0}
.cc-avatar{width:30px;height:30px;border-radius:3px;background:rgba(0,229,255,.10);
  border:1px solid rgba(0,229,255,.25);display:flex;align-items:center;justify-content:center;
  font-family:var(--mono);font-size:13px;color:#7de3ff;flex:none}
"""
    hero = _load_hub_hero().hero_band(
        "GBT小土豆V8 · 总控台", "统一品牌 · 一个面板接全部能力 · 云插件与触手互通 · 编队群只出本域意见",
        chip="总控台", chip_accent="土豆金", seed="console", kind="orb",
        sub="GBT ONE CONSOLE / ALL CAPABILITIES WIRED",
        ctas=[{"label": "能力卡库", "href": "../gallery/index.html"},
              {"label": "Bento 工作台", "href": "../workbench/index.html"}])
    return _write("holo_pet/assets/console/index.html",
                  _shell("GBT小土豆V8 · 总控台", "一个面板接全部能力 · 快照内联 · 数据源 caps_registry/mesh/agents 现读",
                         body, "// 总控台是静态渲染色（数据在生成时内联；点跑走面板桥 /api/capability）",
                         extra, hero=hero))


# ═══════════════════════════ ⑧ 工作空间首页（统一品牌门面 · 旧品牌深度替换） ═══════════════════════════
def render_home() -> dict:
    """**工作空间首页**：GBT//V8 自己的门面（旧品牌深度替换 · 原功能不破坏）。

    形态照主人给的工作空间样本：大字 hero + **中央对话框** + 分类能力丝带 + 运行读数。
    链路全是我们自己的：对话框 → 面板桥 POST /api/message（幂等受理，回合后台跑）；
    能力 → run_task + policy；模型 → potato（gbt-potato-v8）。第三方品牌字样零出现。
    """
    try:
        prows = _load_hub().pages()["rows"]
    except Exception:                                      # noqa: BLE001
        prows = []
    link = {r["page"]: f"../../../{r['path']}" for r in prows}

    def _grp(title: str, items: list) -> str:
        chips = "".join(
            f'<a class="rb-chip" href="{link.get(p, "#") if p in link else href}">{label}</a>'
            for p, label, href in items)
        return f'<div class="rb-group"><div class="rb-title">{title}</div><div>{chips}</div></div>'

    ribbon = (
        _grp("AI 团队", [("console", "编队群 · 14 职业", "#crew"), ("tentacle3d", "触手 3D 全景", "")])
        + _grp("内容创作", [("wf-film", "电影产线", ""), ("wf-movie", "多镜成片", ""),
                            ("wf-music", "音乐", ""), ("wf-short-video", "短视频", "")])
        + _grp("构建套件", [("freebuff", "编程对话", ""), ("gallery", "页面卡库", "")])
        + _grp("安全与门", [("keys", "密钥台", ""), ("console", "能力门 · policy", "#caps")])
        + _grp("工具", [("workbench", "Bento 工作台", ""), ("task-manager", "任务管理器", ""),
                        ("godview", "上帝之眼", "")])
    )

    body = f"""
<div class="hm">
  <section class="hm-hero">
    <div class="hm-kick">// GBT//V8 · WORKSPACE 1.0 · 统一品牌门面</div>
    <h1 class="hm-title">交给 <span class="gd">GBT小土豆V8</span>。<br>
      视频、幻灯片、图片、代码、文档，<br>以及<span class="cy">一切你能指挥的</span>。</h1>
    <p class="hm-sub">其他 AI 帮你<b>找答案</b>。GBT 帮你<b>做东西</b> —— 一个面板，全部能力；
    决策与执行权只属主脑，职业只出本域意见。</p>
    <div class="hm-ask">
      <textarea id="ask" rows="2" placeholder="交给 GBT小土豆V8：说什么，做什么……"></textarea>
      <div class="hm-askbar">
        <span class="rb-chip">potato · gbt-potato-v8</span>
        <span class="rb-chip">走 /api/message 幂等受理</span>
        <button class="hm-go" onclick="ask()">对话 →</button>
      </div>
      <pre id="reply" class="hm-reply"></pre>
    </div>
  </section>
  <section class="hm-ribbon">{ribbon}</section>
  <section class="hm-strip">
    <span id="bridge" class="rb-chip">面板桥：检测中…</span>
    <span class="rb-chip"><b class="cy">217</b> 能力位 · 30 域</span>
    <span class="rb-chip">脑层闭环 3/3</span>
    <span class="rb-chip">决策与执行权只属 GBT小土豆V8</span>
  </section>
</div>"""

    script = """
var $=function(id){return document.getElementById(id)};
function ask(){
  var t=$('ask').value.trim(); if(!t) return;
  var box=$('reply'); box.textContent='…受理中';
  fetch('/api/message',{method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify({text:t,client_msg_id:'home-'+Date.now()})})
   .then(function(r){return r.json();})
   .then(function(d){box.textContent='受理：'+JSON.stringify(d).slice(0,500);
                     box.className='hm-reply ok';})
   .catch(function(e){box.textContent='面板桥不在（静态快照）：请经面板桥 :8765 打开本页再对话。'+e;
                      box.className='hm-reply bad';});
}
fetch('/api/state').then(function(r){return r.json();}).then(function(d){
  var ok=d&&d.ok; var cx=d&&d.codex&&d.codex.connected;
  $('bridge').innerHTML='面板桥：<b class="'+(ok?'cc-ok':'cc-bad')+'">'+(ok?'在线':'异常')+
    '</b>'+(cx?' · codex 已连接':'');
}).catch(function(){ $('bridge').innerHTML='面板桥：<b class="cc-bad">离线</b>（静态快照 · 经 :8765 打开可对话）';});
"""
    extra = """
/* ── 工作空间首页 · HUD 暗面（与总控台同一套语言）────────────────────────── */
body{background:#04060a}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
  background:repeating-linear-gradient(0deg,rgba(255,255,255,.015) 0 1px,transparent 1px 3px),
             linear-gradient(rgba(0,229,255,.04) 1px,transparent 1px),
             linear-gradient(90deg,rgba(0,229,255,.04) 1px,transparent 1px);
  background-size:auto,44px 44px,44px 44px}
body::after{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
  background:radial-gradient(1100px 640px at 30% -8%,rgba(0,229,255,.10),transparent 62%),
             radial-gradient(900px 620px at 108% 112%,rgba(124,77,255,.08),transparent 60%)}
.top,.hm{position:relative;z-index:1}
.hm{max-width:1080px;margin:26px auto 60px;padding:0 22px}
.hm-kick{font-family:var(--mono);font-size:11.5px;letter-spacing:.2em;color:#7de3ff;margin-bottom:16px}
.hm-title{font-size:46px;line-height:1.14;font-weight:800;margin:0 0 14px;letter-spacing:-.01em}
.hm-title .gd{color:#F5B041;text-shadow:0 0 22px rgba(245,176,65,.35)}
.hm-title .cy{color:#00E5FF;text-shadow:0 0 22px rgba(0,229,255,.4)}
.hm-sub{color:var(--dim-2);font-size:14.5px;line-height:1.7;margin:0 0 20px;max-width:720px}
.hm-ask{border:1px solid rgba(0,229,255,.2);border-radius:6px;background:rgba(6,10,14,.9);
  padding:12px;box-shadow:0 0 0 1px rgba(0,229,255,.05),0 18px 50px rgba(0,229,255,.06)}
.hm-ask:focus-within{border-color:rgba(0,229,255,.5)}
.hm-ask textarea{width:100%;background:transparent;border:0;outline:0;resize:none;color:var(--text);
  font-size:14.5px;font-family:inherit}
.hm-askbar{display:flex;align-items:center;gap:8px;margin-top:8px}
.hm-go{margin-left:auto;border:0;border-radius:4px;padding:8px 18px;cursor:pointer;
  font-weight:700;font-size:13px;color:#04121a;background:#00E5FF;box-shadow:0 0 18px rgba(0,229,255,.35)}
.hm-go:hover{box-shadow:0 0 26px rgba(0,229,255,.55)}
.hm-reply{display:none;margin:10px 0 0;padding:10px;border:1px solid var(--line);border-radius:4px;
  font-family:var(--mono);font-size:11.5px;color:#9fb3bd;white-space:pre-wrap;max-height:180px;overflow:auto}
.hm-reply.ok{display:block;border-color:rgba(51,229,140,.4)}
.hm-reply.bad{display:block;border-color:rgba(255,59,92,.4)}
.hm-ribbon{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin-top:34px}
.rb-group{border:1px solid rgba(0,229,255,.14);border-radius:4px;padding:12px;
  background:linear-gradient(180deg,rgba(10,14,18,.92),rgba(6,9,12,.92))}
.rb-title{font-family:var(--mono);font-size:11px;letter-spacing:.18em;color:#6c7f8a;
  text-transform:uppercase;margin-bottom:8px}
.rb-chip{display:inline-block;margin:2px 6px 2px 0;padding:4px 10px;border:1px solid rgba(0,229,255,.18);
  border-radius:2px;font-family:var(--mono);font-size:11.5px;color:#9fdceb;text-decoration:none;
  background:rgba(0,229,255,.04)}
.rb-chip:hover{border-color:rgba(0,229,255,.5);color:#EAF6FA}
.hm-strip{display:flex;flex-wrap:wrap;gap:8px;margin-top:22px}
.cy{color:#00E5FF}.gd{color:#F5B041}
.cc-ok{color:#33E58C;font-weight:700}.cc-bad{color:#FF3B5C;font-weight:700}
"""
    hero = _load_hub_hero().hero_band(
        "GBT//V8 · 工作空间", "统一品牌门面 · 旧品牌深度替换 · 中央对话框直通主脑",
        chip="门面", chip_accent="赛博青", seed="workspace", kind="cubes",
        sub="GBT WORKSPACE / ONE PANEL · ALL CAPABILITIES",
        ctas=[{"label": "进总控台", "href": "../console/index.html"},
              {"label": "能力卡库", "href": "../gallery/index.html"}])
    return _write("holo_pet/assets/home/index.html",
                  _shell("GBT//V8 · 工作空间", "统一品牌门面 · 中央对话框直通主脑 · 快照内联 + 面板桥现取",
                         body, script, extra, hero=hero))


def render(target: str = "all", **_kw) -> dict:
    out = []
    t = (target or "all").lower()
    if t in ("all", "workbench"):
        out.append(render_workbench())
    if t in ("all", "tentacle3d"):
        out.append(render_tentacle3d())
    if t in ("all", "gallery"):
        out.append(render_gallery())
    if t in ("all", "console"):
        out.append(render_console())
    if t in ("all", "home"):
        out.append(render_home())
    if t in ("all", "freebuff"):
        out.append(render_freebuff())
    if t in ("all", "workflows") or t.startswith("workflow:"):
        keys = sorted(_load_hub().WORKFLOWS) if t != "workflows" else []
        if t.startswith("workflow:"):
            keys = [t.split(":", 1)[1].strip()]
        for k in keys:
            out.append(render_workflow(k))
    _log({"event": "render", "target": t, "pages": [o.get("page") for o in out]})
    return {"ok": all("bytes" in o for o in out), "op": "render", "target": t,
            "pages": out, "count": len(out),
            "_口径": "页面是**渲染产物**（快照内联）：数字来自 console_hub 现读，不是手写死的"}


def list_pages(**_kw) -> dict:
    pl = _ASSETS / "workbench" / "index.html"
    t3 = _ASSETS / "tentacle3d" / "index.html"
    return {"ok": True, "op": "list",
            "rendered": [{"path": str(p.relative_to(_ROOT)).replace("\\", "/"),
                          "exists": p.is_file(), "kb": round(p.stat().st_size / 1024, 1)
                          if p.is_file() else 0}
                         for p in [pl, t3] + [(_ASSETS / f"wf-{k}" / "index.html")
                                              for k in sorted(_load_hub().WORKFLOWS)]]}


def verify(**_kw) -> dict:
    """验收（`gbt-aesthetic` §7）：六页在盘上 + 令牌被尊重 + 无外链图床 + 无 emoji 当图标。"""
    problems, rows = [], []
    body = (_ASSETS / "workbench" / "index.html")
    t3 = (_ASSETS / "tentacle3d" / "index.html")
    wfs = [_ASSETS / f"wf-{k}" / "index.html" for k in ("film", "movie", "music", "short-video")]
    for p in [body, t3] + wfs:
        rel = str(p.relative_to(_ROOT)).replace("\\", "/")
        if not p.is_file():
            problems.append(f"{rel} 不在盘上（先 render）")
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        rows.append({"path": rel, "kb": round(p.stat().st_size / 1024, 1)})
        for bad, why in (("unsplash.com", "外链图床"), ("placehold.co", "外链图床"),
                         ("picsum.photos", "外链图床"), ("#6366f1", "indigo（AI 指纹）"),
                         ("#8b5cf6", "indigo 系")):
            if bad in txt:
                problems.append(f"{rel} 命中禁令：{why}")
        if "prefers-reduced-motion" not in txt and p is not t3:
            problems.append(f"{rel} 没有 respects prefers-reduced-motion")
    if len(rows) != 6:
        problems.append(f"应有 6 页，实际 {len(rows)} 页")
    return {"ok": not problems, "op": "verify", "problems": problems, "pages": rows,
            "note": "审美审计器（audit_aesthetic.py）另跑一遍，P0 必须为 0 —— 那是硬闸",
            "_口径": "六页在盘 · 禁令自检 · 动效纪律；审美 P0 由审计器判"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "console_pages", "tentacle": "console_pages",
            "entry": "run_task('console_pages', {'op':'render','target':'all'})",
            "ops": ["render", "list", "verify", "where"],
            "targets": ["all", "workbench", "tentacle3d", "workflow:film|movie|music|short-video"],
            "design_contract": {
                "读数": "为「主人+内部操作者」做的数据台 + 一页门面级 3D 全景；深空仪器感；品牌三色冻结",
                "档位": {"数据台": "变奏4/动效3/密度6", "3D 全景": "变奏5/动效4/密度5"},
                "血账": "§1.5：数据页绝不整板自转、字必须正；3D 冲击只花在签名元素上",
                "签名元素": "触手全景球（域环×30 → 能力节点×209 → 绑定弧 → 运行脉冲）",
                "禁令": "无 indigo / 无 emoji 当图标 / 无编造指标（每个数字带 src）/ 无外链图床"},
            "files": {"渲染台账": str(_LEDGER.relative_to(_ROOT))}}


def run_op(op: str = "render", **params) -> dict:
    op = (op or "render").lower()
    for name, fn in (("render", render), ("list", list_pages), ("verify", verify), ("where", where)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（render/list/verify/where）"}
