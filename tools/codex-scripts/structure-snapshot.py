# -*- coding: utf-8 -*-
"""framework-structure 快照生成器：真读数 → 自包含 structure-explorer 页面。
数据源：git 文件树 · caps_registry(174) · store/trace 审计轨迹 · git log。
再生成：python tools/codex-scripts/structure-snapshot.py（接新能力后跑一次，页面自动长）"""
import json
import subprocess
import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_HTML = ROOT / "holo_pet" / "assets" / "structure" / "index.html"
SKIP = {".pylibs", "node_modules", "__pycache__", ".git", "my-project", "_upstream", "vendor", ".scratch", "dist"}


def py_tree():
    """真实文件树：两级聚合（顶层 → 子目录/根模块），只数 git 在册的 .py。"""
    tracked = subprocess.run(["git", "ls-files", "*.py"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", cwd=str(ROOT)).stdout.splitlines()
    tree = {}
    for s in tracked:
        parts = s.split("/")
        if any(x in parts for x in SKIP):
            continue
        top = parts[0]
        tree.setdefault(top, {})
        if len(parts) == 2:
            tree[top]["__root__"] = tree[top].get("__root__", 0) + 1
        elif len(parts) >= 3:
            tree[top][parts[1]] = tree[top].get(parts[1], 0) + 1
    return {k: v for k, v in sorted(tree.items(), key=lambda x: -sum(x[1].values()))}


def caps():
    sys.path.insert(0, str(ROOT))
    from gbt_allinone.caps_registry import BENIGN_CAPS
    from gbt_allinone.tools.energy_pool import list_energies

    def LAYER(d):
        return "decision" if d in ("llm", "security", "audit") else "local" if d in ("system", "data", "local") else "all"
    return [{"k": k, "d": m.get("domain", "other"), "s": bool(m.get("safe")),
             "h": str(m.get("handler") or ""), "t": str(m.get("desc") or "")[:90],
             "layer": LAYER(m.get("domain", "other"))}
            for k, m in sorted(BENIGN_CAPS.items())], list_energies()


def traces():
    edges = []
    for p in sorted((ROOT / "store" / "trace").glob("*.jsonl")):
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines()[-60:]:
            try:
                j = json.loads(ln)
                edges.append({"at": j.get("at") or j.get("ts") or "", "kind": str(j.get("kind") or j.get("event") or "?"),
                              "src": p.name, "ok": j.get("ok")})
            except Exception:
                continue
    return edges[-50:]


def commits():
    p = subprocess.run(["git", "log", "-8", "--pretty=format:%h|%ad|%s", "--date=format:%m-%d %H:%M"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
    return [{"h": a, "at": b, "msg": c} for a, b, c in (ln.split("|", 2) for ln in p.stdout.splitlines() if "|" in ln)]


def build_data():
    caps_list, energies = caps()
    return {"generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "tree": py_tree(), "caps": caps_list, "energies": energies,
            "traces": traces(), "commits": commits()}


TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>GBT小土豆V8 · 框架结构总览</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;background:#0b0316;color:#e9e4f5;font-family:"Microsoft YaHei",sans-serif;overflow:hidden}
.hud{display:flex;justify-content:space-between;padding:12px 20px;font:600 11px Consolas,monospace;letter-spacing:2px}
.live{color:#a855f7;animation:blink 1.6s infinite}@keyframes blink{50%{opacity:.25}}
.cols{display:flex;height:calc(100% - 46px);gap:10px;padding:0 12px}
.col{background:#120726d9;border:1px solid #7c3aed44;border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.col h3{font:700 11px Consolas;letter-spacing:2px;color:#22d3ee;padding:9px 12px;border-bottom:1px solid #7c3aed33}
.col .body{flex:1;overflow:auto;padding:8px 10px;font-size:11.5px;line-height:1.9}
#c1{flex:0 0 24%}#c2{flex:1 1 auto;position:relative}#c3{flex:0 0 26%}
.dir{color:#c4b5fd;font-weight:600;cursor:pointer}.dir:hover{color:#22d3ee}
.sub{color:#8d80b5;padding-left:14px;font-variant-numeric:tabular-nums}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px}
.tr{border-bottom:1px solid #ffffff0a;padding:4px 2px;font:10.5px Consolas;font-variant-numeric:tabular-nums}
.tr b{color:#ec4899}.tr i{color:#22d3ee;font-style:normal}
.cm{padding:5px 2px;border-bottom:1px solid #ffffff0a;font:10.5px/1.7 Consolas;color:#b9aadf}
.cm b{color:#34d399}
.en{padding:5px 2px;border-bottom:1px solid #ffffff0a;font-size:11px}
canvas{position:absolute;inset:0;width:100%;height:100%;display:block;cursor:grab}
#tip{position:absolute;display:none;background:#120726f5;border:1px solid #22d3ee;border-radius:8px;padding:8px 10px;font-size:10.5px;max-width:300px;z-index:5;pointer-events:none}
#tip b{color:#f1ecfb}#tip s{text-decoration:none;color:#22d3ee}#tip p{color:#9b8fc0;margin-top:3px;line-height:1.6}
.leg{position:absolute;left:10px;bottom:8px;font:10px Consolas;color:#8d80b5}
footer{text-align:center;color:#5f5680;font:10px Consolas;padding:8px}
</style></head><body>
<div class="hud"><span>◈ SYS ACTIVE · FRAMEWORK STRUCTURE</span><span><span class="live">◉ LIVE</span> · 快照 __GENERATED__ · 数据全真读数</span></div>
<div class="cols">
  <div class="col" id="c1"><h3>◉ 文件树（git 在册 .py）</h3><div class="body" id="tree"></div></div>
  <div class="col" id="c2"><h3>◉ 层-域能力图谱（174 位 · 点气泡看铭牌）</h3>
    <canvas id="g"></canvas><div id="tip"></div>
    <div class="leg">内环=决策层 · 中环=通用层 · 外环=本地层 · 气泡大小=能力数</div></div>
  <div class="col" id="c3"><h3>◉ 运行轨迹 + 能源 + 提交</h3><div class="body" id="rt"></div></div>
</div>
<footer>GBT小土豆V8 · structure-explorer · 数据源 git ls-files / caps_registry / store/trace · 开发者：自由的风</footer>
<script>
const D = __DATA__;
const LAYER = d => ("llm,security,audit".includes(d)&&d? (["llm","security","audit"].includes(d)?"decision":(["system","data","local"].includes(d)?"local":"all")) : "all");
const COL = {decision:"#22d3ee", all:"#a855f7", local:"#ec4899"};
const L2 = d => ["llm","security","audit"].includes(d)?"decision":(["system","data","local"].includes(d)?"local":"all");
// ── 左：文件树 ──
const treeEl = document.getElementById("tree");
for (const [top, subs] of Object.entries(D.tree)) {
  const total = Object.values(subs).reduce((a,b)=>a+b,0);
  const d = document.createElement("div");
  d.className = "dir"; d.textContent = "▾ " + top + "  (" + total + ".py)";
  treeEl.appendChild(d);
  const box = document.createElement("div"); box.className = "sub";
  for (const [sub, n] of Object.entries(subs).slice(0, 14)) {
    const s = document.createElement("div");
    s.textContent = (sub === "__root__" ? "· 根模块" : "· " + sub) + " ×" + n;
    box.appendChild(s);
  }
  treeEl.appendChild(box);
  d.onclick = () => box.style.display = box.style.display === "none" ? "" : "none";
}
// ── 右：轨迹/能源/提交 ──
const rt = document.getElementById("rt");
rt.innerHTML += "<div class='dir'>运行轨迹（store/trace 真边）</div>";
if (!D.traces.length) rt.innerHTML += "<div class='sub'>暂无轨迹记录 —— 万能插跑过会自动长</div>";
for (const t of D.traces) { const x=document.createElement("div"); x.className="tr";
  x.innerHTML = "<i>"+(t.at||"—").slice(0,19)+"</i> kind=<b>"+t.kind+"</b> "+(t.ok===false?"<span style='color:#f59e0b'>✗</span>":""); rt.appendChild(x); }
rt.innerHTML += "<div class='dir' style='margin-top:8px'>能源池（"+D.energies.length+" 条）</div>";
for (const e of D.energies) { const x=document.createElement("div"); x.className="en";
  x.innerHTML = "<span class='dot' style='background:"+(e.name==='qwen-local'?'#22d3ee':'#34d399')+"'></span>"+e.name+
    " · <span style='color:#8d80b5'>"+(e.name==='qwen-local'?(e.status||'接线态'):(e.on_disk?'凭据在盘':'缺凭据'))+"</span>"; rt.appendChild(x); }
rt.innerHTML += "<div class='dir' style='margin-top:8px'>最近提交</div>";
for (const c of D.commits) { const x=document.createElement("div"); x.className="cm";
  x.innerHTML = "<b>"+c.h+"</b> "+c.at+" · "+c.msg.slice(0,42); rt.appendChild(x); }
// ── 中：层-域图谱 ──
const cv = document.getElementById("g"), ctx = cv.getContext("2d");
let W,H; function rs(){ const d=Math.min(2,devicePixelRatio||1); W=cv.clientWidth||cv.parentElement.clientWidth; H=cv.clientHeight||cv.parentElement.clientHeight;
  cv.width=W*d; cv.height=H*d; ctx.setTransform(d,0,0,d,0,0); }
addEventListener("resize",rs); setTimeout(rs,50);
const domAgg = {};
for (const c of D.caps) { (domAgg[c.d]=domAgg[c.d]||{n:0,layer:c.layer,caps:[]}); domAgg[c.d].n++; domAgg[c.d].caps.push(c); }
const LRA = {decision:.55, all:1.0, local:1.45};
const nodes = [];
for (const [d, v] of Object.entries(domAgg)) {
  const keys = Object.keys(domAgg).filter(k=>L2(k)===v.layer);
  const i = keys.indexOf(d), n = keys.length;
  const th = (i/n)*Math.PI*2 + (v.layer==="all"?0:v.layer==="decision"?1.05:2.1);
  nodes.push({d, n:v.n, layer:v.layer, caps:v.caps, th, lr:LRA[v.layer],
    x:0, y:0, r: 6+Math.sqrt(v.n)*3.2});
}
let hover=null, mouse={x:-1,y:-1};
cv.onmousemove = e => { const r=cv.getBoundingClientRect(); mouse={x:e.clientX-r.left,y:e.clientY-r.top}; };
(function draw(){
  if (!W || !H || !isFinite(W)) { rs(); requestAnimationFrame(draw); return; }
  ctx.clearRect(0,0,W,H);
  const R0 = Math.min(W,H)*0.34;
  for (const nd of nodes) {
    nd.x = W/2 + Math.cos(nd.th)*R0*nd.lr;
    nd.y = H/2 + Math.sin(nd.th)*R0*nd.lr*0.82;
  }
  // 层轨道
  for (const [l,a] of Object.entries(LRA)) {
    ctx.strokeStyle = COL[l]+"22"; ctx.lineWidth=1;
    ctx.beginPath(); ctx.ellipse(W/2,H/2,R0*a,R0*a*0.82,0,0,7); ctx.stroke();
  }
  // 核
  const g = ctx.createRadialGradient(W/2,H/2,0,W/2,H/2,46);
  g.addColorStop(0,"#a855f7cc"); g.addColorStop(1,"#a855f700");
  ctx.fillStyle=g; ctx.beginPath(); ctx.arc(W/2,H/2,46,0,7); ctx.fill();
  ctx.fillStyle="#f1ecfb"; ctx.font="700 11px Consolas"; ctx.textAlign="center";
  ctx.fillText("GBT · CORE", W/2, H/2+4);
  hover = null;
  for (const nd of nodes) {
    const hov = Math.hypot(mouse.x-nd.x, mouse.y-nd.y) < nd.r+6;
    if (hov) hover = nd;
    const gr = ctx.createRadialGradient(nd.x,nd.y,0,nd.x,nd.y,nd.r*2.1);
    gr.addColorStop(0, (hov?"#ffffff":COL[nd.layer]) + "cc"); gr.addColorStop(1, COL[nd.layer]+"00");
    ctx.fillStyle = gr; ctx.beginPath(); ctx.arc(nd.x,nd.y,nd.r*2.1,0,7); ctx.fill();
    ctx.fillStyle = hov ? "#fff" : COL[nd.layer];
    ctx.beginPath(); ctx.arc(nd.x,nd.y,nd.r*.55,0,7); ctx.fill();
    ctx.fillStyle = hov ? "#f1ecfb" : "#9b8fc0"; ctx.font="600 8.5px Consolas";
    ctx.fillText(nd.d+" ·"+nd.n, nd.x, nd.y - nd.r - 5);
  }
  requestAnimationFrame(draw);
})();
const tip = document.getElementById("tip");
setInterval(() => {
  if (!hover) { tip.style.display="none"; return; }
  const c = hover.caps[0];
  tip.style.display="block";
  tip.style.left = Math.min(W-310, hover.x+16)+"px"; tip.style.top = (hover.y-20)+"px";
  tip.innerHTML = "<b>"+hover.d+"</b> <s>"+hover.n+" 位 · "+hover.layer+"</s><p>"+
    hover.caps.slice(0,4).map(x=>"· <b>"+x.k+"</b> "+(x.s?"免卡":"过门")).join("<br>")+(hover.n>4?"<br>…":"")+"</p>";
}, 120);
</script></body></html>
"""


def main():
    data = build_data()
    html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":"))) \
                   .replace("__GENERATED__", data["generated"])
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    (ROOT / "output" / "framework-structure.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("page:", OUT_HTML, "| caps:", len(data["caps"]), "| traces:", len(data["traces"]),
          "| commits:", len(data["commits"]), "| tree tops:", len(data["tree"]))


if __name__ == "__main__":
    main()
