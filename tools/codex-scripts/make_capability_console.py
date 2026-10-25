# -*- coding: utf-8 -*-
"""能力台 v3 · 真 3D 能力球 —— 手写三维引擎，零依赖，单文件。

═══ 为什么手写而不用 three（Owner 2026-09-22：「科技风格做好 3D 风的立体」）═══

框架里装着 three（holo_pet/node_modules/three），但单文件页面不该依赖它：
  · 要加载模块 → 得配 server 或打包 → 又一个"跑不起来"的坑
  · 而这个页面要能在**双击**的情况下就出真三维
⇒ 所以自己写：Fibonacci 球面 + 旋转矩阵 + 透视投影 + 画家算法深度排序。
   一百来行数学，换来"零依赖 + 真立体"。

立体怎么做的（不是画个圆叫 3D）：
  ① **真球面分布** —— 每个节点用 Fibonacci 螺旋铺在球面上，均匀不结块
     （条数不写死：注册表能力 + 禁用项 + Ark 云端能力面，生成时现算）
  ② **真透视投影** —— 相机在 z 轴外，近大远小；节点半径与亮度随深度变化
  ③ **画家算法** —— 背面的节点先画，被核心遮住的真的在后面
  ④ **拖拽旋转 + 自动慢转** —— 转起来才看得出是球
  ⑤ **真光照** —— 单一光源（左上），球面明暗与节点高光同源

风格上仍是上一版的立意，只是从平面升到立体：
  · 暖色（赭石/泥土）当**身体**，青色当**神经信号** —— 别家清一色冷蓝黑
  · **形态即状态**：桩=空心，只登记未实现=暗红，要授权=琥珀环
  · 加科技感：经纬线框 + 轨道环 + 扫描面 + HUD 读数
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = ROOT / "capabilities.html"
SIGN = "开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"

from gbt_allinone import caps_registry as CR          # noqa: E402
from gbt_allinone.security import policy              # noqa: E402

BENIGN = getattr(CR, "BENIGN_CAPS", {}) or {}
DISABLED = getattr(CR, "DISABLED_CAPS", set()) or set()
# 2026-09-23 解禁：被拒名单已清空；名字转在这里登记（只有名字、没有实现）
UNIMPLEMENTED = getattr(CR, "UNIMPLEMENTED_CAPS", set()) or set()
PARAMS = getattr(CR, "PARAM_REQUIRED", {}) or {}

DOMAIN_CN = {
    "system": "系统", "llm": "内核", "tentacle": "触手", "device": "设备",
    "data": "数据", "finance": "金融", "project": "项目", "recon": "侦察",
    "security": "安全", "engine": "引擎", "longrun": "长程", "pipeline": "产出",
    "creation": "创作", "comms": "通信", "life": "生命", "mind": "心智",
    "vision": "视觉", "voice": "语音", "automation": "自动化",
    "digital_human": "数字人", "devour": "吞天", "brain": "脑域", "collab": "协作",
    "framework": "框架", "image_video": "影像", "infra": "基建",
    "integration": "集成", "social": "社交", "tools": "工具", "video": "视频",
    "dangerous": "禁用",
}


def one(kind: str) -> dict:
    meta = BENIGN.get(kind) or {}
    d = policy.evaluate(kind, {})
    scopes = list(getattr(d, "scopes", ()) or ())
    handler = str(meta.get("handler") or "")
    desc = str(meta.get("desc") or "")
    dom = str(meta.get("domain") or "")
    low = (desc + " " + handler).lower()
    is_stub = any(t in low for t in ("骨架", "not_implemented", "未实现", "占位"))
    if kind in DISABLED or kind in UNIMPLEMENTED:
        state = "disabled"
    elif is_stub:
        state = "stub"
    elif scopes:
        state = "guarded"
    else:
        state = "free"
    return {"kind": kind, "domain": dom, "domain_cn": DOMAIN_CN.get(dom, dom),
            "desc": desc, "handler": handler, "scopes": scopes,
            "risk": getattr(d, "risk", "low"),
            "params": list(PARAMS.get(kind) or []), "state": state}


def fib_sphere(n: int) -> list:
    """Fibonacci 球面：把 n 个点均匀铺在单位球上。确定性，无随机。"""
    pts = []
    ga = math.pi * (3.0 - math.sqrt(5.0))        # 黄金角
    for i in range(n):
        y = 1.0 - (i / max(1, n - 1)) * 2.0
        r = math.sqrt(max(0.0, 1.0 - y * y))
        th = ga * i
        pts.append((math.cos(th) * r, y, math.sin(th) * r))
    return pts


CSS = """
:root{
  --ochre:#C9884A;--earth:#7A5230;--flesh:#F0D9B5;
  --deep:#0B0805;--deep2:#150E08;
  --sig:#00E5FF;                 /* 信号青：只在激活/选中/扫描时 */
  --ok:#D9964F;--warn:#E8B04A;--stub:#6B5540;--fault:#A2453A;--ark:#8E6BD8;
  --line:rgba(201,136,74,.22);--text:#F4E9D8;--dim:#BCA88F;
  --faint:rgba(188,168,143,.45);
  --r:12px;--rc:7px;--rp:999px;
  --mono:"SF Mono","JetBrains Mono",Consolas,ui-monospace,monospace;
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;color:var(--text);overflow:hidden;
  background:radial-gradient(1100px 760px at 50% 44%,rgba(201,136,74,.13),transparent 64%),
    radial-gradient(700px 520px at 84% 8%,rgba(0,229,255,.055),transparent 62%),
    linear-gradient(180deg,var(--deep),var(--deep2));
  font:14px/1.6 "Microsoft YaHei UI","Segoe UI",system-ui,sans-serif;-webkit-font-smoothing:antialiased}

/* ── 3D 舞台 ── */
#stage{position:fixed;inset:0;cursor:grab}
#stage.drag{cursor:grabbing}
#gl{display:block;width:100%;height:100%}

/* ── HUD：科技感靠这几层叠出来 ── */
.hud{position:fixed;pointer-events:none;z-index:5;
  font:500 10.5px/1.7 var(--mono);letter-spacing:.1em;color:var(--faint);text-transform:uppercase}
.hud.tl{top:20px;left:24px}
.hud.tr{top:20px;right:24px;text-align:right}
.hud.bl{bottom:20px;left:24px}
.hud.br{bottom:20px;right:24px;text-align:right}
.hud b{color:var(--text);font-weight:600}
.hud .cy{color:var(--sig)}
.topbar{display:flex;align-items:center;gap:12px;margin-bottom:6px}
.heart{width:9px;height:9px;border-radius:var(--rp);background:var(--ochre);
  box-shadow:0 0 14px var(--ochre);animation:beat 3.4s ease-in-out infinite}
@keyframes beat{0%,100%{opacity:1;transform:scale(1)}45%{opacity:.32;transform:scale(.7)}}
.title{font:700 15px/1.2 "Microsoft YaHei UI",system-ui,sans-serif;letter-spacing:.02em;color:var(--text)}
h1.big{margin:2px 0 4px;font:700 clamp(20px,2.3vw,30px)/1.1 "Microsoft YaHei UI",system-ui,sans-serif;
  letter-spacing:-.02em;
  background:linear-gradient(180deg,#FFF7EA,var(--flesh) 58%,rgba(188,168,143,.5));
  -webkit-background-clip:text;background-clip:text;color:transparent}
.hint{color:var(--dim);font-size:11.5px;max-width:52ch;letter-spacing:0;text-transform:none;
  font-family:"Microsoft YaHei UI",system-ui,sans-serif;line-height:1.55}
.hint b{color:var(--ochre)}
.hint i{color:var(--sig);font-style:normal}
.legend{display:flex;flex-direction:column;gap:5px;align-items:flex-end}
.legend s{text-decoration:none;display:flex;align-items:center;gap:7px;justify-content:flex-end}
.legend i{display:inline-block;width:10px;height:10px;border-radius:var(--rp)}
.li-free{background:var(--ok);box-shadow:0 0 9px var(--ok)}
.li-guarded{background:transparent;border:1.6px solid var(--warn)}
.li-stub{background:transparent;border:1.6px dashed var(--stub)}
.li-disabled{background:var(--fault)}
.li-unimplemented{background:var(--fault);opacity:.62}
.li-external{background:transparent;border:1.6px solid var(--ark)}
.kv{display:flex;gap:14px;justify-content:flex-end}
.kv span{color:var(--faint)}
.kv b{color:var(--text)}

/* ── 配色切换器：颜色可切，是这一版对"颜色还是没变"的正面回答 ── */
.pal{display:flex;align-items:center;gap:8px;justify-content:flex-end;margin-top:9px;
  pointer-events:auto}
.pal-lbl{font:500 10px/1 var(--mono);letter-spacing:.1em;color:var(--faint)}
.pal-lbl b{color:var(--text);font-weight:600}
.pi{width:22px;height:22px;padding:0;border-radius:var(--rp);cursor:pointer;
  border:2px solid rgba(255,255,255,.16);background:transparent;transition:transform .15s ease}
.pi:hover{transform:scale(1.16)}
.pi.on{border-color:#fff;box-shadow:0 0 12px rgba(255,255,255,.45);transform:scale(1.1)}
.pi-ochre{background:linear-gradient(135deg,#E0A45E,#8A5A2C)}
.pi-cyan{background:linear-gradient(135deg,#7CF3FF,#1E7FA8)}
.pi-violet{background:linear-gradient(135deg,#C79BF5,#5B2A96)}
.pi-bio{background:linear-gradient(135deg,#8CFFD4,#1E9E6E)}
/* 换了配色，界面底色也跟着走 —— 不然只是球变了、壳没变 */
html[data-p="cyan"] body{background:
  radial-gradient(1100px 760px at 50% 44%,rgba(63,182,216,.15),transparent 64%),
  radial-gradient(700px 520px at 84% 8%,rgba(124,243,255,.06),transparent 62%),
  linear-gradient(180deg,#04090E,#08141C)}
html[data-p="violet"] body{background:
  radial-gradient(1100px 760px at 50% 44%,rgba(162,107,232,.16),transparent 64%),
  radial-gradient(700px 520px at 84% 8%,rgba(229,155,255,.06),transparent 62%),
  linear-gradient(180deg,#08050F,#150A24)}
html[data-p="bio"] body{background:
  radial-gradient(1100px 760px at 50% 44%,rgba(63,214,154,.14),transparent 64%),
  radial-gradient(700px 520px at 84% 8%,rgba(140,255,212,.06),transparent 62%),
  linear-gradient(180deg,#03090A,#06161A)}

/* 悬浮读数：鼠标靠近哪个节点就报哪个 */
#peek{position:fixed;z-index:6;pointer-events:none;padding:7px 11px;border:1px solid var(--line);
  border-radius:var(--rc);background:rgba(11,8,5,.92);backdrop-filter:blur(6px);
  font:600 11px/1.5 var(--mono);color:var(--text);display:none;white-space:nowrap}
#peek em{font-style:normal;color:var(--dim);font-weight:400}
#peek .st{color:var(--sig)}

/* ── 单项页面：从 3D 里"拉出来"的一张卡 ── */
#sheet{position:fixed;inset:0;z-index:20;display:none;
  background:linear-gradient(180deg,rgba(11,8,5,.86),rgba(21,14,8,.94));
  -webkit-backdrop-filter:blur(3px);backdrop-filter:blur(3px);
  overflow:auto;padding:30px 26px 60px}
#sheet.on{display:block;animation:rise .26s ease}
@keyframes rise{from{opacity:0;transform:translateY(14px) scale(.99)}to{opacity:1;transform:none}}
.sheet-in{max-width:1040px;margin:0 auto}
.crumb{font:500 10px/1 var(--mono);color:var(--faint);letter-spacing:.16em;text-transform:uppercase}
h2.big{margin:9px 0 6px;font:700 clamp(26px,3.3vw,42px)/1.06 "Microsoft YaHei UI",system-ui,sans-serif;
  letter-spacing:-.025em;
  background:linear-gradient(180deg,#FFF7EA,var(--flesh) 58%,rgba(188,168,143,.5));
  -webkit-background-clip:text;background-clip:text;color:transparent}
.badges{display:flex;gap:8px;flex-wrap:wrap;margin:11px 0 20px}
.b{border:1px solid currentColor;border-radius:var(--rp);padding:2px 11px;
  font:600 10.5px/1.7 var(--mono);letter-spacing:.06em}
.b-free{color:var(--ok)}.b-guarded{color:var(--warn)}.b-stub{color:var(--stub)}
.b-disabled{color:var(--fault)}.b-external{color:var(--ark)}.b-dom{color:var(--sig)}.b-risk{color:var(--dim)}
.b-unimplemented{color:var(--fault);opacity:.8}
.lede{color:var(--dim);font-size:14.5px;max-width:74ch;margin:0 0 22px}
.card{border:1px solid var(--line);border-radius:var(--r);background:rgba(21,14,8,.72);
  padding:17px 19px;margin:0 0 15px;box-shadow:0 22px 50px -30px rgba(0,0,0,.9)}
.card h3{margin:0 0 11px;font:650 11px/1 var(--mono);letter-spacing:.12em;
  text-transform:uppercase;color:var(--faint)}
table{width:100%;border-collapse:collapse;font-size:12.5px}
td{padding:6px 0;border-bottom:1px solid rgba(201,136,74,.13);vertical-align:top}
td:first-child{width:158px;color:var(--faint);font:11.5px/1.6 var(--mono)}
code{font:12px/1.5 var(--mono);color:var(--sig);background:rgba(0,229,255,.07);
  padding:1px 6px;border-radius:var(--rc)}
label{display:block;margin:0 0 11px}
label span{display:block;font:600 10.5px/1 var(--mono);color:var(--faint);
  letter-spacing:.1em;margin-bottom:5px}
input,textarea{width:100%;padding:9px 11px;border:1px solid var(--line);border-radius:var(--rc);
  background:rgba(8,6,4,.8);color:var(--text);font:13px/1.5 var(--mono)}
input:focus,textarea:focus{outline:none;border-color:var(--sig);
  box-shadow:0 0 0 3px rgba(0,229,255,.1)}
button{margin-top:5px;padding:10px 22px;border:1px solid var(--sig);border-radius:var(--rc);
  background:rgba(0,229,255,.12);color:var(--sig);font:600 13px/1 inherit;cursor:pointer}
button:hover{background:rgba(0,229,255,.2)}
button[disabled]{opacity:.4;cursor:not-allowed;border-color:var(--line);
  color:var(--faint);background:transparent}
button.ghost{border-color:var(--line);color:var(--dim);background:transparent;margin-right:9px}
button.ghost:hover{border-color:var(--ochre);color:var(--ochre)}
pre{margin:0;padding:13px;border:1px solid var(--line);border-radius:var(--rc);
  background:rgba(8,6,4,.85);color:var(--dim);font:12px/1.6 var(--mono);
  overflow:auto;max-height:400px;white-space:pre-wrap;word-break:break-word}
.empty{color:var(--faint);font-size:12.5px}
.warnbox{border-color:rgba(162,69,58,.6);background:rgba(162,69,58,.1)}
.sig{margin-top:34px;padding-top:13px;border-top:1px solid var(--line);
  color:var(--faint);font:500 11px/1.8 var(--mono);letter-spacing:.06em}
@media(max-width:760px){.hud.tr,.hud.br{display:none}}
"""

JS = r"""
'use strict';
/* ── 现读优先：内嵌快照只当"外观字典"与离线兜底 ─────────────────────────────
   🔴 2026-09-22：**这段必须留在模板里**（同上一条 favicon 的教训）——
   先前"写死 183 项 / 31 域 / 图例五个数字"是在**生成产物**上手补的，一旦重新生成就被冲掉；
   而生成时的数字（`len(allc)`、`stats[...]`）**生成完就冻结**，注册表一变面板就开始骗人。
   现在模板产出的页面：**先按快照画**（不白屏）→ 拿 `/api/capabilities` 现读 → **以现读为准重建**；
   提示语与图例数字全部现算；取不到现读就保持快照并写明「快照 · 取不到现读」。 */
const CAPS_SNAPSHOT=__CAPS__;
const byKind={}, domDir={}, nodes=[];
let ORDERED=[], ptsO=[], CAPS=[], CAPS_SOURCE='snapshot', CAPS_HIDDEN=0, CAPS_LIVE_TOTAL=null;
let CAPS_LIVE_REG=null, CAPS_LIVE_ARK=null, CAPS_ARK_TOTAL=null, ARK_MISSING=false;
const cv=document.getElementById('gl'), stage=document.getElementById('stage');
const peek=document.getElementById('peek'), sheet=document.getElementById('sheet'),
      sheetIn=document.getElementById('sheet-in'), ctx=cv.getContext('2d');

/* ═══ 3D ─────────────────────────────────────────────────────────────
   右手系：+x 右，+y 下（屏幕），+z 朝观察者。相机在 z=CAM 处看向原点。
   旋转：先绕 Y 自转(ry)，再绕 X 微倾(rx)。拖拽改 ry/rx，松手保持。      */
const R3=1.0, CAM=2.15, FOV=1.42;   /* 相机推近、视场加大 —— 让球占满画面，冲击力才够 */
let ry=-0.5, rx=-0.34, spin=0.0022, dragging=false, lx=0, ly=0;
const HALO=[], RINGS=[];

/* 由一份能力清单重建球面几何（初始用快照，现读到手后复用同一个函数重建）。
   ⚠️ `nodes`/`domDir`/`LINKS` 都是**原地改** —— 渲染循环按引用持有它们。 */
function rebuild(list){
  CAPS=list;
  Object.keys(byKind).forEach(function(k){ delete byKind[k]; });
  Object.keys(domDir).forEach(function(k){ delete domDir[k]; });
  nodes.length=0;
  list.forEach(function(c){ byKind[c.kind]=c; });
  ORDERED=list.slice().sort(function(a,b){ return a.domain<b.domain?-1:a.domain>b.domain?1:
    (a.kind<b.kind?-1:1); });
  ptsO=fibSphere(ORDERED.length);
  ORDERED.forEach(function(c,i){ nodes.push({c, p:ptsO[i], sx:0, sy:0, sc:0, sz:0}); });
  ORDERED.forEach(function(c,i){
    const d=domDir[c.domain]||(domDir[c.domain]={x:0,y:0,z:0,n:0});
    d.x+=ptsO[i][0]; d.y+=ptsO[i][1]; d.z+=ptsO[i][2]; d.n++;
  });
  Object.values(domDir).forEach(function(d){
    const L=Math.hypot(d.x,d.y,d.z)||1; d.x/=L; d.y/=L; d.z/=L;
  });
  LINKS.length=0;
  const byDom={};
  ORDERED.forEach(function(c,i){ (byDom[c.domain]=byDom[c.domain]||[]).push(i); });
  Object.keys(byDom).forEach(function(k){
    const idxs=byDom[k];
    for(let j=0;j<idxs.length-1;j++) LINKS.push([idxs[j], idxs[j+1]]);
    if(idxs.length>3) LINKS.push([idxs[idxs.length-1], idxs[0]]);
  });
  updateCounts();
}

function updateCounts(){
  const n={free:0,guarded:0,stub:0,disabled:0,external:0,unimplemented:0}, doms={};
  CAPS.forEach(function(c){ if(n[c.state]!==undefined) n[c.state]++; doms[c.domain]=1; });
  const set=function(id,v){ const el=document.getElementById(id); if(el) el.textContent=v; };
  set('h-caps', CAPS.length+' 项能力');
  set('h-doms', Object.keys(doms).length+' 个域');
  set('lg-free', n.free); set('lg-guarded', n.guarded); set('lg-stub', n.stub);
  /* 解禁后口径：旧快照里叫 disabled，现读里叫 unimplemented —— 两种都归到同一格，
     标签写「只登记未实现」：它们不是"被策略挡住的"，是**后面什么都没有**。 */
  set('lg-disabled', n.unimplemented + n.disabled); set('lg-external', n.external);
  const src=document.getElementById('h-src');
  if(src){
    if(CAPS_SOURCE==='live'){
      const comp=(CAPS_LIVE_REG!==null)
        ? '：注册表 '+CAPS_LIVE_REG+(CAPS_LIVE_ARK?(' + Ark 云端 '+CAPS_LIVE_ARK):'')
          + (CAPS_ARK_TOTAL&&CAPS_LIVE_ARK!==CAPS_ARK_TOTAL?('（Ark 接口报 '+CAPS_ARK_TOTAL+'，只拿到 '+CAPS_LIVE_ARK+'）'):'')
        : '';
      src.textContent='（现读 /api/capabilities'+comp
        +(CAPS_HIDDEN?(' · 快照里 '+CAPS_HIDDEN+' 条已不在现读面，未画'):'')
        +(ARK_MISSING?' · ⚠ Ark 通道只报了数、没给条目，紫环节点缺失':'')+'）';
    }else{
      src.textContent='（内嵌快照 · 取不到现读；数字可能过期）';
    }
  }
  try{ window.__gbtPanelCaps={source:CAPS_SOURCE, count:CAPS.length,
        domains:Object.keys(doms).length, hidden:CAPS_HIDDEN, liveTotal:CAPS_LIVE_TOTAL,
        liveRegistry:CAPS_LIVE_REG, liveArk:CAPS_LIVE_ARK, arkTotal:CAPS_ARK_TOTAL,
        arkMissing:ARK_MISSING, byState:n}; }catch(e){}
}

/* 现读对齐：注册表 `items` + Ark `app.ark.skills` **两条通道都并**。
   ⚠️ 接口原文：「能力分四条通道 …… `total` 只数第一条，别拿它当全量」（`total_all_channels`）。 */
function applyLive(payload){
  if(!payload) return false;
  const reg=(payload.items)||[];
  const ark=((payload.app&&payload.app.ark&&payload.app.ark.skills)||[]);
  if(!reg.length&&!ark.length) return false;
  const snap={}; CAPS_SNAPSHOT.forEach(function(c){ snap[c.kind]=c; });
  const liveKinds={}; const merged=[];
  reg.forEach(function(it){
    liveKinds[it.kind]=1;
    const old=snap[it.kind]||{};
    let state;
    if(it.enabled===false) state=(it.status==='unimplemented')?'unimplemented':'disabled';
    else if(old.state==='stub') state='stub';
    else state = it.needs_confirmation ? 'guarded' : 'free';
    merged.push({
      kind:it.kind, domain:it.domain||old.domain||'unknown',
      domain_cn:old.domain_cn||it.domain||'未分类',
      desc:(it.desc&&String(it.desc).trim())||old.desc||'',
      handler:old.handler||it.kind, scopes:old.scopes||[], risk:old.risk||'unknown',
      params:it.params||old.params||[], params_hint:it.params_hint||'',
      enabled:it.enabled!==false, needs_confirmation:!!it.needs_confirmation, state:state
    });
  });
  const ARK_TOTAL=(payload.app&&payload.app.ark&&payload.app.ark.total)||ark.length;
  if(!ark.length&&ARK_TOTAL>0) ARK_MISSING=true;
  ark.forEach(function(a){
    const name=a.name||a.kind;
    if(!name) return;
    liveKinds[name]=1;
    const old=snap[name]||{};
    merged.push({
      kind:name, domain:'ark', domain_cn:'Ark 云端',
      desc:(a.desc&&String(a.desc).trim())||old.desc||'',
      handler:old.handler||'arkcli', scopes:old.scopes||[], risk:old.risk||'external',
      params:[], params_hint:a.cli_help||'', enabled:true, needs_confirmation:false,
      state:'external', version:a.version||'', cli_help:a.cli_help||'', bins:a.bins||[]
    });
  });
  CAPS_HIDDEN=CAPS_SNAPSHOT.filter(function(c){ return !liveKinds[c.kind]; }).length;
  CAPS_LIVE_TOTAL=merged.length;
  CAPS_LIVE_REG=reg.length; CAPS_LIVE_ARK=ark.length; CAPS_ARK_TOTAL=ARK_TOTAL;
  CAPS_SOURCE='live';
  rebuild(merged);
  return true;
}

function fibSphere(n){
  const out=[], ga=Math.PI*(3-Math.sqrt(5));
  for(let i=0;i<n;i++){
    const y=1-(i/Math.max(1,n-1))*2, r=Math.sqrt(Math.max(0,1-y*y)), th=ga*i;
    out.push([Math.cos(th)*r, y, Math.sin(th)*r]);
  }
  return out;
}
/* 域分组：同一域的节点在球面上相邻（Fibonacci 是按序铺的，所以按域排序后再铺）
   —— 这段住在 `rebuild()` 里（快照 / 现读共用同一条铺法）。 */

function rot(p){
  const cy=Math.cos(ry), sy=Math.sin(ry), cx=Math.cos(rx), sx=Math.sin(rx);
  let x=p[0]*R3, y=p[1]*R3, z=p[2]*R3;
  let x1= x*cy + z*sy, z1= -x*sy + z*cy;      // 绕 Y
  let y1= y*cx - z1*sx, z2= y*sx + z1*cx;     // 绕 X
  return [x1,y1,z2];
}
function proj(v){
  const zc=CAM - v[2];
  const k=(FOV*Math.min(cv.width,cv.height)*0.5)/Math.max(0.15,zc);
  return {x:cv.width/2 + v[0]*k, y:cv.height/2 + v[1]*k, k, z:v[2], zc};
}

function resize(){
  const dpr=Math.min(2, window.devicePixelRatio||1);
  cv.width=Math.round(innerWidth*dpr); cv.height=Math.round(innerHeight*dpr);
  cv.style.width=innerWidth+'px'; cv.style.height=innerHeight+'px';
}
addEventListener('resize',resize); resize();

const C={ok:'#D9964F', warn:'#E8B04A', stub:'#6B5540', fault:'#A2453A', sig:'#00E5FF', ark:'#8E6BD8'};

/* ═══ 四套配色（可切）══════════════════════════════════════════════════
   Owner 2026-09-22：「这么颜色还是没变？」
   ⇒ 我读错了"科技风格"：一直守着暖赭石（把它当"创新"），但你要的可能是
     正经的科技配色。**继续猜是浪费 —— 所以把颜色做成能切的，你看着挑。**
   每套驱动全部：星云 / 星场 / 节点 / 核心 / 轨道环 / 扫描带 / 界面。
   键 1 赭石(暖) · 2 深空青(冷·正统科技) · 3 星紫 · 4 生物荧光           */
const PALETTES={
  ochre:{cn:'赭石 · 暖', core:['#FFF3DC','#E0A45E','#A9691F','#4A2F14'],
    ok:'#D9964F', warn:'#E8B04A', stub:'#6B5540', fault:'#A2453A', sig:'#00E5FF', ark:'#8E6BD8',
    nebA:'rgba(122,82,48,.30)', nebB:'rgba(0,140,170,.16)',
    starW:'#F0D9B5', starC:'#9FD8E4', rgb:'201,136,74'},
  cyan:{cn:'深空青 · 冷', core:['#EAFBFF','#63D3F0','#1E7FA8','#0A2C3C'],
    ok:'#4FD2F0', warn:'#F0C24A', stub:'#3E5A66', fault:'#E0564A', sig:'#7CF3FF', ark:'#9B7CF0',
    nebA:'rgba(20,80,120,.34)', nebB:'rgba(0,190,220,.18)',
    starW:'#DCF3FF', starC:'#6FE6FF', rgb:'63,182,216'},
  violet:{cn:'星紫 · 幻', core:['#F6ECFF','#C79BF5','#7A3FC0','#2A1044'],
    ok:'#B47CF0', warn:'#F0A94A', stub:'#4E3F63', fault:'#E0507A', sig:'#E59BFF', ark:'#4FD2F0',
    nebA:'rgba(90,40,150,.34)', nebB:'rgba(230,90,190,.14)',
    starW:'#F2E6FF', starC:'#E59BFF', rgb:'162,107,232'},
  bio:{cn:'生物荧光 · 生机', core:['#EFFFF6','#7BE8BC','#1E9E6E','#08301F'],
    ok:'#4FE0A4', warn:'#D8E04A', stub:'#3A5A4A', fault:'#E06A5A', sig:'#8CFFD4', ark:'#B47CF0',
    nebA:'rgba(20,110,80,.32)', nebB:'rgba(180,220,60,.12)',
    starW:'#E6FFF2', starC:'#8CFFD4', rgb:'63,214,154'},
};
/* ⚠️ 存储键**必须带版本号**。
   踩过的坑（2026-09-22）：Owner 反馈"颜色还是没变"。实测原因是——他以前打开过
   赭石版，浏览器里存着 capPalette=ochre；而读取逻辑是"有存储就用存储"，
   于是**旧值永远压着代码里的新默认**，改多少次默认都不生效。
   ⇒ 版本号一升，老键自然失效：新默认生效一次，之后用户的选择照常记住。
      这是"用户偏好"与"开发者改默认"之间必须留的那道口子。               */
const LSKEY='capPalette.v2';
let PKEY='violet';   /* Owner 2026-09-22 选定：星紫 */
try{ const s=localStorage.getItem(LSKEY); if(s&&PALETTES[s]) PKEY=s; }catch(e){}
function PAL(){ return PALETTES[PKEY]; }
function applyPalette(k){
  PKEY=PALETTES[k]?k:'violet';
  try{ localStorage.setItem(LSKEY,PKEY); }catch(e){}
  document.documentElement.setAttribute('data-p',PKEY);
  const p=PAL();
  C.ok=p.ok; C.warn=p.warn; C.stub=p.stub; C.fault=p.fault; C.sig=p.sig; C.ark=p.ark;
  /* 这几行是补一个既有缺口：CSS 里的 --ok/--warn/… 原先**写死在 :root**，
     切成别的配色时只有 canvas 跟着变，**徽章颜色一直不变** ——
     Owner 那句"颜色还是没变"里，有一部分就是这个。现在两处一起跟着配色走。 */
  try{ const rs=document.documentElement.style;
    rs.setProperty('--ok',p.ok); rs.setProperty('--warn',p.warn);
    rs.setProperty('--stub',p.stub); rs.setProperty('--fault',p.fault);
    rs.setProperty('--sig',p.sig); rs.setProperty('--ark',p.ark);
  }catch(e){}
  const lbl=document.getElementById('pname'); if(lbl) lbl.textContent=p.cn;
  document.querySelectorAll('[data-pk]').forEach(function(b){
    b.classList.toggle('on', b.dataset.pk===PKEY); });
}

/* ═══ 空间参照物：为什么"纯黑"看起来不立体 ═══════════════════════════
   一个球悬在纯黑里，眼睛**没有参照** —— 感觉不到它在哪、多大、转多快。
   所以"更立体"和"背景别太空"其实是同一件事：**补参照系**。
   补五样：
     ① 3D 星场（三层视差）—— 近的星转得快，远的几乎不动 ⇒ 一眼看出深度
     ② 星云 —— 暖赭 + 冷青两团软云，给虚空一个"底"
     ③ 径向深度钉 —— 每个节点向球心连一小段线，把"球面"这件事画实
     ④ 域内连线 —— 同域节点在球面上连起来 ⇒ 球面长出"组织"
     ⑤ 加色发光 + 核心扩散环 + 暗角 —— 冲击力与聚焦
   ⚠️ 全部确定性（不用随机数），同一份注册表每次画出来一样。          */
const STAR_LAYERS=[
  {n:230, r0:2.6, r1:4.6, sp:0.14, sz:0.85, a:0.30},   // 远：几乎不动
  {n:130, r0:1.8, r1:2.6, sp:0.34, sz:1.5,  a:0.46},   // 中
  {n:64,  r0:1.42,r1:1.75,sp:0.68, sz:2.3,  a:0.58},   // 近：贴着球飞
];
const GA=Math.PI*(3-Math.sqrt(5));
const STARS=[];
STAR_LAYERS.forEach(function(L,li){
  for(let i=0;i<L.n;i++){
    const y=1-(i/Math.max(1,L.n-1))*2, rr=Math.sqrt(Math.max(0,1-y*y)), th=GA*i;
    const rad=L.r0+(((i*2654435761)>>>0)%1000)/1000*(L.r1-L.r0);  // 确定性"随机"
    STARS.push({p:[Math.cos(th)*rr*rad, y*rad, Math.sin(th)*rr*rad],
                sp:L.sp, sz:L.sz, a:L.a});
  }
});
/* 域内连线容器：内容由 `rebuild()` 现算（快照与现读共用）。 */
const LINKS=[];
/* ① 先用内嵌快照画出来（不白屏）；② 再去拿现读 —— 到手就用现读重建整颗球。 */
rebuild(CAPS_SNAPSHOT);
fetch('/api/capabilities',{cache:'no-store'}).then(function(r){ return r.json(); })
  .then(function(j){ if(j&&j.ok!==false) applyLive(j); })
  .catch(function(){ /* 取不到就保持快照，提示语里已写明"快照 · 取不到现读" */ });
let tGlobal=0;

/* ═══ 能源输送引擎 ═══════════════════════════════════════════════════
   Owner：「只要 AI 在动，她能力球里面相对应的能力就会像输送能源一样的动起来」

   🔴 铁律：动画**只被真实调用点亮**。源拿不到 ⇒ HUD 显示"实时源未接"且不发光。
      绝不许自己空转 —— 那是好看但骗人的装饰（铁律 6）。

   数据源：GET /api/recent-calls  → {ok, calls:[{kind, at, ok}], source}
   拿不到（file:// 双击打开、或面板没跑）⇒ 不报错、不假装，如实显示。      */
const HEAT={};            /* kind -> 0..1，被点亮后随时间衰减 */
const RIPPLE=[];          /* 涟漪：{x,y,r,a} */
const SPARK=[];           /* 沿链路的脉冲：{from,to,t,dom} */
let FEED_STATE='unknown'; /* unknown | live | absent */
let FEED_TRIES=0, lastCallAt=0;

function lightUp(kind,strength){
  if(!byKind[kind]) return;                 /* 注册表里没有的 kind，不猜、不点亮 */
  HEAT[kind]=Math.min(1.6,(HEAT[kind]||0)+(strength||1));
  const n=nodes.find(function(x){return x.c.kind===kind;});
  if(n) RIPPLE.push({x:n.sx,y:n.sy,r:2,a:0.85,dom:n.c.domain});
}
function pollFeed(){
  FEED_TRIES++;
  fetch('/api/recent-calls',{cache:'no-store'}).then(function(r){
    if(!r.ok) throw new Error('HTTP '+r.status);
    return r.json();
  }).then(function(j){
    FEED_STATE='live';
    const calls=(j&&j.calls)||[];
    calls.forEach(function(c){
      if(c.at && c.at>lastCallAt){ lastCallAt=c.at; lightUp(c.kind,1); }
    });
    const el=document.getElementById('feed'); if(el) el.textContent='实时源 · 已接';
  }).catch(function(){
    FEED_STATE='absent';
    const el=document.getElementById('feed');
    if(el) el.textContent='实时源 · 未接（面板没跑或 file:// 打开）';
  });
}

function draw(){
  const W=cv.width,H=cv.height,cx=W/2,cy=H/2;
  ctx.clearRect(0,0,W,H);

  /* ⓪-a 星云：给虚空一个"底"，别让球悬在纯黑里 */
  (function(){
    const g1=ctx.createRadialGradient(cx-W*0.22,cy-H*0.16,0,cx-W*0.22,cy-H*0.16,W*0.62);
    g1.addColorStop(0,PAL().nebA); g1.addColorStop(0.5,'rgba(0,0,0,0)');
    g1.addColorStop(1,'rgba(0,0,0,0)');
    ctx.fillStyle=g1; ctx.fillRect(0,0,W,H);
    const g2=ctx.createRadialGradient(cx+W*0.26,cy+H*0.20,0,cx+W*0.26,cy+H*0.20,W*0.50);
    g2.addColorStop(0,PAL().nebB); g2.addColorStop(0.55,'rgba(0,0,0,0)');
    g2.addColorStop(1,'rgba(0,0,0,0)');
    ctx.fillStyle=g2; ctx.fillRect(0,0,W,H);
  })();

  /* ⓪-b 3D 星场：三层视差 —— 这一层就是"立体感"的来源 */
  ctx.save();
  ctx.globalCompositeOperation='lighter';
  STARS.forEach(function(s){
    const c=Math.cos(ry*s.sp), sn=Math.sin(ry*s.sp);
    const x1=s.p[0]*c + s.p[2]*sn, z1=-s.p[0]*sn + s.p[2]*c;
    const v=rot([x1,s.p[1],z1]), q=proj(v);
    if(q.zc<0.2) return;
    const a=s.a*Math.max(0,Math.min(1,(q.z+1.35)/2.35));
    const r=Math.max(0.5,s.sz*q.k*0.0016);
    ctx.globalAlpha=a;
    ctx.fillStyle= (s.p[1]>0.25)?PAL().starW:PAL().starC;
    ctx.beginPath(); ctx.arc(q.x,q.y,r,0,Math.PI*2); ctx.fill();
  });
  ctx.restore();

  /* ⓪-c 暗角：把视线压回中心 */
  (function(){
    const g=ctx.createRadialGradient(cx,cy,Math.min(W,H)*0.30,cx,cy,Math.max(W,H)*0.72);
    g.addColorStop(0,'rgba(0,0,0,0)'); g.addColorStop(1,'rgba(0,0,0,.62)');
    ctx.fillStyle=g; ctx.fillRect(0,0,W,H);
  })();

  /* ① 经纬线框（科技感的底）—— 背面淡、正面亮 */
  const seg=64, R=R3;
  ctx.lineWidth=Math.max(1,Math.min(W,H)/1400);
  for(let lat=-60; lat<=60; lat+=30){
    const la=lat*Math.PI/180, y=Math.sin(la), rr=Math.cos(la);
    ctx.beginPath();
    for(let i=0;i<=seg;i++){
      const t=i/seg*Math.PI*2, v=rot([Math.cos(t)*rr,y,Math.sin(t)*rr]), s=proj(v);
      i?ctx.lineTo(s.x,s.y):ctx.moveTo(s.x,s.y);
    }
    ctx.strokeStyle='rgba('+PAL().rgb+','+(lat===0?0.20:0.10)+')'; ctx.stroke();
  }
  for(let lon=0; lon<180; lon+=30){
    const lo=lon*Math.PI/180;
    ctx.beginPath();
    for(let i=0;i<=seg;i++){
      const t=i/seg*Math.PI*2;
      const v=rot([Math.cos(lo)*Math.cos(t), Math.sin(t), Math.sin(lo)*Math.cos(t)]), s=proj(v);
      i?ctx.lineTo(s.x,s.y):ctx.moveTo(s.x,s.y);
    }
    ctx.strokeStyle='rgba('+PAL().rgb+',0.085)'; ctx.stroke();
  }

  /* ② 域的同心弧 —— 让"域"在球面上看得见成片 */
  ctx.lineWidth=Math.max(1,Math.min(W,H)/1100);
  Object.keys(domDir).forEach(k=>{
    const d=domDir[k], seen=new Set();
    ORDERED.forEach((c,i)=>{
      if(c.domain!==k) return;
      const p=ptsO[i], key=i;
      if(seen.has(key)) return; seen.add(key);
      const v=rot([p[0]*0.985,p[1]*0.985,p[2]*0.985]), s=proj(v);
      if(s.z<-0.15) return;                    // 背面的不画
      ctx.beginPath();
      ctx.arc(s.x,s.y,Math.max(1.2,s.k*0.012),0,Math.PI*2);
      ctx.strokeStyle='rgba('+PAL().rgb+',0.07)'; ctx.stroke();
    });
  });

  /* ③ 节点：画家算法 —— 按 z 从远到近画 */
  nodes.forEach(n=>{
    const v=rot(n.p), s=proj(v);
    n.sx=s.x; n.sy=s.y; n.k=s.k; n.z=s.z;
    const depth=(s.z+1)/2;                       // 0 远 → 1 近
    n.sc=depth; n.sz=s.z;
  });
  const sorted=nodes.slice().sort((a,b)=>a.sz-b.sz);

  /* ③-a 域内连线 + 径向深度钉
     连线让"域"在球面上真的成片；深度钉把"这是球面、不是散点"画实。*/
  ctx.save();
  ctx.globalCompositeOperation='lighter';
  ctx.lineWidth=Math.max(1,Math.min(W,H)/1600);
  LINKS.forEach(function(pr){
    const A=nodes[pr[0]], B=nodes[pr[1]];
    const zm=(A.sz+B.sz)/2, a=Math.max(0, (zm+0.6)/1.6);
    if(a<=0.02) return;
    ctx.strokeStyle='rgba('+PAL().rgb+','+(0.16*a)+')';
    ctx.beginPath(); ctx.moveTo(A.sx,A.sy); ctx.lineTo(B.sx,B.sy); ctx.stroke();
  });
  sorted.forEach(function(n){
    if(n.sz<-0.35) return;
    const a=0.10+0.26*((n.sz+1)/2);
    ctx.strokeStyle='rgba('+PAL().rgb+','+a+')';
    ctx.beginPath(); ctx.moveTo(n.sx,n.sy);
    ctx.lineTo(cx+(n.sx-cx)*0.80, cy+(n.sy-cy)*0.80);   // 朝球心收 20%
    ctx.stroke();
  });
  ctx.restore();

  ctx.save();
  sorted.forEach(n=>{
    const c=n.c, d=n.sc;
    const rad=Math.max(1.6, n.k*(0.0055 + 0.0072*d));   // 近大远小
    const a=0.28 + 0.72*d*d;                            // 近亮远暗
    const x=n.sx,y=n.sy;
    ctx.globalAlpha=a;
    if(c.state==='free'){
      const g=ctx.createRadialGradient(x,y,0,x,y,rad*3.4);
      g.addColorStop(0,'rgba(217,150,79,'+(0.85*a)+')');
      g.addColorStop(0.45,'rgba(217,150,79,'+(0.28*a)+')');
      g.addColorStop(1,'rgba(217,150,79,0)');
      ctx.fillStyle=g; ctx.beginPath(); ctx.arc(x,y,rad*3.4,0,Math.PI*2); ctx.fill();
      ctx.fillStyle=C.ok; ctx.beginPath(); ctx.arc(x,y,rad,0,Math.PI*2); ctx.fill();
      ctx.fillStyle='rgba(255,240,214,'+(0.5*a)+')';
      ctx.beginPath(); ctx.arc(x-rad*0.3,y-rad*0.3,rad*0.34,0,Math.PI*2); ctx.fill();
    } else if(c.state==='guarded'){
      ctx.strokeStyle=C.warn; ctx.lineWidth=Math.max(1,rad*0.42);
      ctx.beginPath(); ctx.arc(x,y,rad,0,Math.PI*2); ctx.stroke();
    } else if(c.state==='stub'){
      ctx.strokeStyle=C.stub; ctx.lineWidth=Math.max(1,rad*0.38);
      ctx.setLineDash([rad*0.85, rad*0.75]);
      ctx.beginPath(); ctx.arc(x,y,rad,0,Math.PI*2); ctx.stroke();
      ctx.setLineDash([]);
    } else if(c.state==='external'){
      /* Ark 云端（外部 CLI）：紫环 + 半实心核。
         不复用 guarded 的琥珀环 —— 两者含义不同：guarded 是"她自己的能力、过门可用"，
         external 是"不归本仓能力口管、要经 arkcli 出去"，混成一个颜色就是骗人。 */
      ctx.strokeStyle=C.ark; ctx.lineWidth=Math.max(1,rad*0.42);
      ctx.beginPath(); ctx.arc(x,y,rad,0,Math.PI*2); ctx.stroke();
      ctx.globalAlpha=a*0.55;
      ctx.fillStyle=C.ark;
      ctx.beginPath(); ctx.arc(x,y,rad*0.48,0,Math.PI*2); ctx.fill();
      ctx.globalAlpha=a;
    } else {
      ctx.fillStyle=C.fault; ctx.beginPath(); ctx.arc(x,y,rad*0.86,0,Math.PI*2); ctx.fill();
    }
    ctx.globalAlpha=1;
  });
  ctx.restore();


  /* ③-b 能源输送：热节点 —— 被真实调用点亮的那些 */
  ctx.save();
  ctx.globalCompositeOperation='lighter';
  sorted.forEach(function(n){
    const h=HEAT[n.c.kind]||0; if(h<=0.02) return;
    const a=Math.min(1,h);
    const x=n.sx,y=n.sy, base=Math.max(1.6,n.k*0.011);
    /* 白热内核 */
    const g=ctx.createRadialGradient(x,y,0,x,y,base*7*(0.6+0.7*h));
    g.addColorStop(0,'rgba(255,255,255,'+(0.85*a)+')');
    g.addColorStop(0.30,'rgba(220,190,255,'+(0.5*a)+')');
    g.addColorStop(1,'rgba(160,110,240,0)');
    ctx.fillStyle=g;
    ctx.beginPath(); ctx.arc(x,y,base*7*(0.6+0.7*h),0,Math.PI*2); ctx.fill();
    ctx.fillStyle='rgba(255,255,255,'+(0.95*a)+')';
    ctx.beginPath(); ctx.arc(x,y,base*(0.9+0.9*h),0,Math.PI*2); ctx.fill();
    /* 沿该域的连线，从核心方向往节点"充电" —— 能源输送的观感来源 */
    const A=nodes.find(function(z){return z.c.kind===n.c.kind;});
    ctx.strokeStyle=PAL().sig;
    ctx.globalAlpha=0.30*a;
    ctx.lineWidth=Math.max(1.2,Math.min(W,H)/900);
    ctx.beginPath(); ctx.moveTo(cx,cy); ctx.lineTo(x,y); ctx.stroke();
    ctx.globalAlpha=1;
  });
  ctx.restore();

  /* ③-c 涟漪：从被点亮的节点向外扩，边扩边淡 */
  ctx.save();
  ctx.globalCompositeOperation='lighter';
  for(let i=RIPPLE.length-1;i>=0;i--){
    const p=RIPPLE[i];
    p.r+=2.6; p.a*=0.955;
    if(p.a<0.02){ RIPPLE.splice(i,1); continue; }
    ctx.strokeStyle='rgba(200,160,255,'+p.a+')';
    ctx.lineWidth=Math.max(1,Math.min(W,H)/1300);
    ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,Math.PI*2); ctx.stroke();
  }
  ctx.restore();

  /* ④ 核心：光源在左上，与球面明暗同源 */
  const coreP=proj([0,0,0]);
  const cr=coreP.k*0.098;
  const cg=ctx.createRadialGradient(coreP.x-cr*0.35,coreP.y-cr*0.4,cr*0.06,coreP.x,coreP.y,cr);
  const CC=PAL().core;
  cg.addColorStop(0,CC[0]); cg.addColorStop(0.34,CC[1]);
  cg.addColorStop(0.72,CC[2]); cg.addColorStop(1,CC[3]);
  ctx.fillStyle=cg; ctx.beginPath(); ctx.arc(coreP.x,coreP.y,cr,0,Math.PI*2); ctx.fill();
  /* 大气层 */
  const ag=ctx.createRadialGradient(coreP.x,coreP.y,cr*0.9,coreP.x,coreP.y,cr*2.3);
  ag.addColorStop(0,'rgba('+PAL().rgb+',.34)'); ag.addColorStop(1,'rgba('+PAL().rgb+',0)');
  ctx.fillStyle=ag; ctx.beginPath(); ctx.arc(coreP.x,coreP.y,cr*2.3,0,Math.PI*2); ctx.fill();
  /* 轨道环：倾斜的科技环 */
  [1.42,1.72].forEach((rr,idx)=>{
    ctx.beginPath();
    for(let i=0;i<=110;i++){
      const t=i/110*Math.PI*2, tilt=(idx?0.9:-0.55);
      const v=rot([Math.cos(t)*rr, Math.sin(t)*rr*Math.sin(tilt), Math.sin(t)*rr*Math.cos(tilt)]);
      const s=proj(v); i?ctx.lineTo(s.x,s.y):ctx.moveTo(s.x,s.y);
    }
    ctx.strokeStyle=idx?PAL().sig.replace(')',',.24)').replace('#','rgba(').replace('rgb','rgb'):'rgba('+PAL().rgb+',.24)';
    ctx.lineWidth=Math.max(1,Math.min(W,H)/1500); ctx.stroke();
  });
  /* 核心文字 */
  ctx.textAlign='center'; ctx.textBaseline='middle';
  ctx.fillStyle='rgba(20,13,7,.92)';
  ctx.font='700 '+Math.round(cr*0.42)+'px "Microsoft YaHei UI",system-ui,sans-serif';
  ctx.fillText('小土豆', coreP.x, coreP.y-cr*0.16);
  ctx.font='600 '+Math.round(cr*0.24)+'px ui-monospace,Consolas,monospace';
  ctx.fillStyle='rgba(20,13,7,.72)';
  ctx.fillText('CAPS '+CAPS.length, coreP.x, coreP.y+cr*0.32);

  /* ⑤ 扫描面（科技感的动）—— 一道横掠的冷光 */
  const sy=(performance.now()/5200)%1;
  const yy=sy*H;
  const sg=ctx.createLinearGradient(0,yy-70,0,yy+70);
  sg.addColorStop(0,'rgba(0,229,255,0)'); sg.addColorStop(0.5,'rgba(0,229,255,.075)');
  sg.addColorStop(1,'rgba(0,229,255,0)');
  ctx.fillStyle=sg; ctx.fillRect(0,yy-70,W,140);
}

let mouse={x:-999,y:-999};
function hitTest(){
  let best=null, bd=1e9;
  nodes.forEach(n=>{
    if(n.sz<-0.05) return;                       // 背面的不响应
    const dx=n.sx-mouse.x, dy=n.sy-mouse.y, d=dx*dx+dy*dy;
    if(d<bd){bd=d;best=n;}
  });
  return (best && bd < 26*26) ? best : null;
}
function loop(){
  ry += spin;
  tGlobal += 1;
  /* 热值衰减：调用过去后自己退场，不留假亮 */
  Object.keys(HEAT).forEach(function(k){
    HEAT[k]*=0.972; if(HEAT[k]<0.015) delete HEAT[k]; });
  /* 真实源轮询：每 ~1.6s 一次 */
  if(tGlobal%96===0) pollFeed();
  draw();
  const h=hitTest();
  if(h && !dragging){
    const cn={free:'免卡',guarded:'要授权',stub:'桩',disabled:'禁用',unimplemented:'只登记未实现',external:'Ark云端'}[h.c.state];
    peek.style.display='block';
    peek.style.left=(h.sx+14)+'px'; peek.style.top=(h.sy-30)+'px';
    peek.innerHTML=h.c.kind+' <em>· '+h.c.domain_cn+' ·</em> <span class="st">'+cn+'</span>';
  } else peek.style.display='none';
  requestAnimationFrame(loop);
}

/* 拖拽转球（鼠标 + 触摸） */
function down(e){dragging=true;stage.classList.add('drag');
  const t=e.touches?e.touches[0]:e; lx=t.clientX; ly=t.clientY;}
function move(e){
  const t=e.touches?e.touches[0]:e;
  mouse.x=t.clientX*Math.min(2,devicePixelRatio||1);
  mouse.y=t.clientY*Math.min(2,devicePixelRatio||1);
  if(!dragging) return;
  ry += (t.clientX-lx)*0.0062; rx -= (t.clientY-ly)*0.0055;
  rx=Math.max(-1.2,Math.min(1.2,rx)); lx=t.clientX; ly=t.clientY;
  if(e.cancelable) e.preventDefault();
}
function up(){dragging=false;stage.classList.remove('drag');}
stage.addEventListener('mousedown',down); addEventListener('mousemove',move);
addEventListener('mouseup',up); stage.addEventListener('touchstart',down,{passive:true});
addEventListener('touchmove',move,{passive:false}); addEventListener('touchend',up);
stage.addEventListener('click',()=>{const h=hitTest(); if(h) openCap(h.c.kind);});
addEventListener('keydown',e=>{ if(e.key==='Escape') closeCap(); });

/* ═══ 单项页面 ═══ */
function closeCap(){ sheet.classList.remove('on'); }
function openCap(kind){
  const c=byKind[kind];
  if(!c){ sheetIn.innerHTML='<h2 class="big">没有这项能力</h2><p class="lede">注册表里查不到 <code>'+
    String(kind).replace(/[<>&]/g,'')+'</code>。前端不猜一个出来。</p>'+
    '<button class="ghost" onclick="closeCap()">← 回到能力球</button>'; sheet.classList.add('on'); return; }
  const scopes=c.scopes.length?c.scopes.map(s=>'<code>'+s+'</code>').join(' '):
    '<span class="empty">无（免卡）</span>';
  const pr=c.params.length?c.params.map(p=>'<label><span>'+p+'</span><input data-param="'+
    p+'" placeholder="'+p+' 的值（JSON 或纯文本）"></label>').join(''):
    '<p class="empty">注册表未声明必填参数 —— 可直接调用，或按需在下方 JSON 里补 payload。</p>';
  const dis=(c.state==='disabled'||c.state==='unimplemented');
  const ext=c.state==='external';
  const cn={free:'可用（免卡）',guarded:'要授权',stub:'还是桩',disabled:'曾被拒（历史状态）',
            unimplemented:'只有名字 · 没有实现',external:'Ark 云端 · 外部 CLI'}[c.state];
  /* 外部 CLI 能力（Ark）：**不给"调用"按钮** —— 给了就是骗人，它根本不走 /api/capability。
     如实写清它走哪条路、真实命令入口是什么。入口来自技能 SKILL.md 的 cliHelp（现读）。 */
  const callCard = ext
    ? '<div class="card"><h3>怎么调它</h3>'+
        '<p class="empty">它<strong>不走本仓的能力口</strong> <code>/api/capability</code>，'+
        '也<strong>不受 run_task 那道授权门管</strong> —— 它是 Ark 云端的 CLI 能力，要经 <code>arkcli</code> 出去。'+
        '所以这里<strong>故意没有"调用"按钮</strong>：不是按钮坏了，是不该有这个按钮。</p>'+
        (c.cli_help
          ? '<p>它自己的真实入口：<code>'+c.cli_help+'</code></p>'
          : '<p class="empty">该技能没写 <code>cliHelp</code> —— <strong>别猜命令</strong>，去看它的 SKILL.md。</p>')+
        '<p class="empty">调用规矩：先过<strong>登录闸</strong>（<code>arkcli auth status</code>）、'+
        '再过<strong>账号验证闸</strong>（<code>identity.verified</code>；false 时计费写入会被挡）、'+
        '计费动作<strong>先报价再确认</strong>。详见技能 <code>gbt-arkcli</code>。</p>'+
      '</div>'
    : '<div class="card"><h3>调用</h3>'+pr+
        '<label><span>payload JSON（可选，非空则以此为准）</span>'+
        '<textarea rows="3" id="pj" placeholder=\'{"op":"status"}\'></textarea></label>'+
        '<button id="go"'+(dis?' disabled':'')+'>调用'+(dis?'（调不通）':'')+'</button>'+
        (c.scopes.length&&!dis?'<p class="empty" style="margin-top:10px">这项要授权。面板走同一道门：'+
          '缺授权就如实报缺，页面不绕。</p>':'')+
      '</div>';
  sheetIn.innerHTML=
    '<button class="ghost" onclick="closeCap()">← 回到能力球</button>'+
    '<p class="crumb" style="margin-top:16px">'+c.domain+' · '+c.domain_cn+'</p>'+
    '<h2 class="big">'+c.kind+'</h2>'+
    '<div class="badges"><span class="b b-'+c.state+'">'+cn+'</span>'+
    '<span class="b b-dom">'+c.domain_cn+'</span>'+
    '<span class="b b-risk">risk: '+c.risk+'</span></div>'+
    '<p class="lede">'+(c.desc||'（注册表未写说明）')+'</p>'+
    (dis?'<div class="card warnbox"><h3>为什么调不通</h3><p class="empty">它<strong>只有名字、没有实现</strong>'+
      '（2026-09-23 禁止已全部解开，但解禁**不等于**有实现 —— 全仓零实现文件）。'+
      '点下去得到的是如实的 <code>unknown capability</code>，<strong>不是</strong>"被安全策略挡住"。'+
      '本页面不提供调用入口 —— 不是"按钮坏了"，是<strong>后面什么都没有</strong>。</p></div>':'')+
    (c.state==='stub'?'<div class="card warnbox"><h3>诚实提示</h3><p class="empty">注册表自己标注了它是'+
      '<strong>骨架 / 未实现</strong>。球面上它是<strong>空心虚线节点</strong>。这里照样给得出页面，但'+
      '<strong>调它大概率返回占位</strong> —— 那是真实结果，不是页面坏了。</p></div>':'')+
    '<div class="card"><h3>事实</h3><table>'+
      '<tr><td>kind</td><td><code>'+c.kind+'</code></td></tr>'+
      '<tr><td>'+(ext?'CLI 入口':'handler')+'</td><td>'+
        (ext?(c.cli_help?'<code>'+c.cli_help+'</code>':'<span class="empty">技能未写 cliHelp</span>')
            :(c.handler?'<code>'+c.handler+'</code>':'<span class="empty">注册表未写</span>'))+'</td></tr>'+
      '<tr><td>需要授权</td><td>'+(ext?'<span class="empty">不适用（不走本仓那道门）</span>':scopes)+'</td></tr>'+
      '<tr><td>'+(ext?'来源':'风险等级')+'</td><td>'+(ext?'Ark 云端（外部 CLI）':c.risk)+'</td></tr>'+
      '</table></div>'+
    callCard+
    (ext?'':'<div class="card"><h3>结果</h3><pre id="out">（还没调用）</pre></div>')+
    '<div class="sig">__SIGN__</div>';
  const go=document.getElementById('go');
  if(go&&!dis)go.onclick=async()=>{
    const out=document.getElementById('out'); out.textContent='调用中…';
    let payload={};
    const raw=(document.getElementById('pj').value||'').trim();
    if(raw){try{payload=JSON.parse(raw)}catch(e){out.textContent='payload 不是合法 JSON：'+e.message;return}}
    document.querySelectorAll('[data-param]').forEach(i=>{
      const v=i.value.trim(); if(!v) return;
      try{payload[i.dataset.param]=JSON.parse(v)}catch(e){payload[i.dataset.param]=v}});
    try{
      const r=await fetch('/api/capability',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({kind:c.kind,payload})});
      out.textContent=JSON.stringify(await r.json(),null,2);
    }catch(e){out.textContent='调用失败（原样显示，不美化）：'+e;}
  };
  sheet.classList.add('on');
}
window.closeCap=closeCap; window.openCap=openCap;
window.applyPalette=applyPalette;
applyPalette(PKEY);
pollFeed();
addEventListener('keydown',function(e){
  const M={'1':'ochre','2':'cyan','3':'violet','4':'bio'};
  if(M[e.key]) applyPalette(M[e.key]);
});
loop();
"""


def ark_entries() -> tuple[list[dict], dict]:
    """Ark 云端能力面（外部 CLI）。

    **单一真相**：读 `holo_pet/ark_surface.json` —— 那份声明由
    `tools/codex-scripts/make_ark_surface.py` 现读本地 arkcli 技能目录生成。
    面板服务 `/api/capabilities` 读的是同一份，这里不另抄一张表。

    与注册表能力的三点不同，都写进条目里（页面据此渲染，不靠猜）：
      · `state='external'` —— 紫环 + 半实心核，**不给"调用"按钮**（它不走 /api/capability）
      · `handler` 放它**真实 CLI 入口**（来自技能 SKILL.md 的 cliHelp）
      · `scopes=[]`、`risk='external'` —— 本仓的授权门对它不适用
    """
    path = ROOT / "holo_pet" / "ark_surface.json"
    meta: dict = {}
    if path.exists():
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"  ⚠ Ark 能力面声明解析失败，本次不并入（如实少报，不编）：{exc}")
    out = []
    for s in (meta.get("skills") or []):
        name = str(s.get("name") or "").strip()
        if not name:
            continue
        out.append({
            "kind": name, "domain": "arkcli", "domain_cn": "Ark 云端",
            "desc": str(s.get("desc") or ""),
            "handler": str(s.get("cli_help") or ""),
            "cli_help": str(s.get("cli_help") or ""),
            "scopes": [], "risk": "external", "params": [], "state": "external",
        })
    return out, meta


def main() -> int:
    caps = [one(k) for k in sorted(BENIGN)]
    dis = [{"kind": k, "domain": "unimplemented", "domain_cn": "只登记未实现",
            "desc": "只有名字、没有实现（**不是**被安全策略挡住 —— 2026-09-23 禁止已全部解开）",
            "handler": "", "scopes": [], "risk": "none", "params": [], "state": "unimplemented"}
           for k in sorted(UNIMPLEMENTED)]
    ark, ark_meta = ark_entries()
    allc = caps + dis + ark
    # 统计口径与状态词表一一对应：加一个 state 就必须在这里加一格，
    # 否则新增状态会被**静默漏计**（页面上少几个节点，谁也不会发现）。
    _STATES = ("free", "guarded", "stub", "disabled", "unimplemented", "external")
    stats = {s: sum(1 for c in allc if c["state"] == s) for s in _STATES}
    assert sum(stats.values()) == len(allc), (
        "状态词表漏了：allc=%d, 统计=%d, 词表=%s" % (len(allc), sum(stats.values()), _STATES))
    js = (JS.replace("__CAPS__", json.dumps(allc, ensure_ascii=False))
            .replace("__SIGN__", SIGN))

    doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>能力球 · GBT小土豆V8</title>
<!-- 内联 data: icon：不依赖路径（DSH 宿主 / file:// 都成立）。
     ⚠ 这条要留在**模板**里：先前它是手补在生成产物上的，一旦重新生成就被冲掉，
     浏览器转而去请求 /favicon.ico 拿 404，控制台就挂一条红字（实测踩过）。 -->
<link rel="icon" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAWklEQVR42mNgGAWjYBSMglEwCkbBKBgFo2AUjIJRMApGwSgYBaNgFIyCUTAKRsEoGAWjYBSMglEwCkbBKBgFo2AUjIJRMApGwSgYBaNgFIyCUTAKRsEoAAB2gAH/8kQ0dQAAAABJRU5ErkJggg==">
<style>{CSS}</style>
</head>
<body>

<div id="stage"><canvas id="gl"></canvas></div>
<div id="peek"></div>

<div class="hud tl">
  <div class="topbar"><span class="heart"></span><span class="title">GBT小土豆V8</span></div>
  <h1 class="big">能力球</h1>
  <div class="hint" id="hint"><b id="h-caps">…</b>铺在一个真球面上，按 <b id="h-doms">…</b>成片。
    <b>拖拽转它</b>，鼠标停在节点上看读数，<i>点节点进它的独立页面</i>。
    <span id="h-src" style="opacity:.75"></span></div>
</div>

<div class="hud tr">
  <div class="legend">
    <s><span>免卡 <b id="lg-free">…</b></span><i class="li-free"></i></s>
    <s><span>要授权 <b id="lg-guarded">…</b></span><i class="li-guarded"></i></s>
    <s><span><b>空心＝桩 <b id="lg-stub">…</b></b></span><i class="li-stub"></i></s>
    <s><span>只登记 · 未实现 <b id="lg-disabled">…</b></span><i class="li-unimplemented"></i></s>
    <s><span>Ark 云端 <b id="lg-external">…</b></span><i class="li-external"></i></s>
  </div>
</div>

<div class="hud bl">
  <div class="kv"><span>形态即状态</span><b>实心＝可动</b><span>·</span>
    <b>琥珀环＝过门可用</b><span>·</span><b>空心虚线＝还没长出来</b><span>·</span>
    <b>紫环＝Ark 云端（外部 CLI，本页不代调）</b></div>
</div>

<div class="hud br">
  <div class="kv"><span>拖拽旋转</span><span>·</span><span>悬停读数</span><span>·</span>
    <span class="cy">1/2/3/4 换配色</span><span>·</span><span class="cy">ESC 关闭</span></div>
  <div class="kv" style="margin-top:6px">
    <span id="feed">实时源 · 检测中…</span>
  </div>
  <div class="pal">
    <span class="pal-lbl">配色 · <b id="pname">星紫 · 幻</b></span>
    <button data-pk="ochre"  class="pi pi-ochre"  onclick="applyPalette('ochre')"  title="赭石 · 暖"></button>
    <button data-pk="cyan"   class="pi pi-cyan"   onclick="applyPalette('cyan')"   title="深空青 · 冷"></button>
    <button data-pk="violet" class="pi pi-violet" onclick="applyPalette('violet')" title="星紫 · 幻"></button>
    <button data-pk="bio"    class="pi pi-bio"    onclick="applyPalette('bio')"    title="生物荧光 · 生机"></button>
  </div>
</div>

<div id="sheet"><div class="sheet-in" id="sheet-in"></div></div>

<script>{js}</script>
</body>
</html>
"""
    OUT.write_text(doc, encoding="utf-8")
    print("=" * 84)
    print("能力球 v3 · 真 3D · 生成")
    print("=" * 84)
    print(f"  落位: {OUT.relative_to(ROOT)}  ({len(doc):,} 字)")
    print(f"  快照节点 {len(allc)} · 域 {len({c['domain'] for c in allc})} · 球面 Fibonacci 分布")
    print(f"  快照形态: 实心 {stats['free']} · 琥珀环 {stats['guarded']} · "
          f"**空心桩 {stats['stub']}** · 暗红(只登记未实现) {stats['unimplemented']} · "
          f"**紫环(Ark外部) {stats['external']}**")
    print("  ⚠ 上面这些是**快照**（画完立刻用 /api/capabilities 现读重建）；"
          "页面里不再写死任何数字")
    if ark:
        snap = (ark_meta.get("auth_snapshot") or {})
        print(f"  Ark 能力面: {len(ark)} 条 · arkcli {ark_meta.get('arkcli_version') or '?'} · "
              f"读自 {(ark_meta.get('generated_from') or '?')}")
        print(f"    登录快照（{ark_meta.get('generated_at') or '?'} 时点）: "
              f"logged_in={snap.get('logged_in')} · identity_verified={snap.get('identity_verified')}")
    print(f"  署名: {'在' if SIGN in doc else '缺!'}")
    print("  3D 要素: 旋转矩阵 · 透视投影 · 画家算法 · 经纬线框 · 轨道环 · 扫描面")
    print("  依赖: **零**（手写引擎，双击即开）")
    return 0


def check() -> int:
    """`--check`：**产物是不是这个模板生成的**（漂移就报，别让人手补过的东西悄悄留在盘上）。

    为什么必须有：本产物被手补过两次（favicon、以及"写死 183/31/图例数字"），两次都是
    **生成器不动、只改产物** ⇒ 下一次重新生成就冲掉。现在生成器与产物必须能对上：
    对不上就说明"有人只改了产物"，跑一次生成器重新生成即可。

    做法：把 `OUT` 临时指到一个 `.checktmp`，跑一遍 `main()`（现算 + 写盘），再逐字符比，最后删临时件。
    """
    global OUT
    real = OUT
    tmp = real.with_name(real.name + ".checktmp")
    try:
        OUT = tmp
        main()
    finally:
        OUT = real
    if not tmp.exists():
        print("🔴 生成器没产出临时件，无法比对")
        return 1
    generated = tmp.read_text(encoding="utf-8")
    tmp.unlink()
    if not real.exists():
        print("🔴 产物不在：%s" % real)
        return 1
    now = real.read_text(encoding="utf-8")
    if now == generated:
        print("✅ 产物与模板一致（%d 字）—— 盘上这份就是本生成器产出的" % len(generated))
        return 0
    print("🔴 产物与模板**不一致**：盘上 %d 字 vs 生成 %d 字" % (len(now), len(generated)))
    print("   ⇒ 有人只改了产物（没改生成器）：手补的东西下次重新生成会被冲掉。")
    print("   ⇒ 修法：`py -3.14 tools/codex-scripts/make_capability_console.py` 重新生成；")
    print("     若手补的是**该留的**（例如 favicon / 现读重建那段），就把它挪进本模板（`JS` / `doc`）。")
    return 1


if __name__ == "__main__":
    import sys as _sys
    raise SystemExit(check() if "--check" in _sys.argv else main())
