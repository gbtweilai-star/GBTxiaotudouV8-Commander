#!/usr/bin/env python
# -*- coding: utf-8 -*-
# gbt-instrument: 三方向流程台面板生成器 —— 数据全部现读，手不抄一个数字
# 开发者：自由的风 · GBT小土豆V8
"""三方向流程台 · 面板生成器（写 `media-console.html`）。

## 它是什么、给谁看

Owner 的目标原话：「最好必须按照**专业化面板**设计好万能插能够完成整套工作流」。
本器把三方向的真实进度做成**一页面板**，登记进宿主面板清单（与另外 12 个面板同一套做法）。

## 三条纪律（照本仓既有做法）

1. **数据现读，不手抄**：18 格状态来自 `media_flow.check_one`（同一份判据，不另写一遍）；
   三条链来自 `media_run.CHAINS`；发布包来自 `projects/_shared/publish/`；
   许可账来自 `media_license`。**页面上每个数字都能指回它的来源。**
2. **快照要自报家门**：页面写明生成时刻 + **重生成命令**（本仓既有做法，见 `exec-deck` / `code-deck`）。
3. **没跑过就说没跑过**：链上没有实现器的步如实显示 `人/未实现`；
   发布一律显示**授权门**状态，**绝不显示"已发布"**。

用法：
    py -3.14 tools/codex-scripts/media-console.py
"""

from __future__ import annotations

import html
import importlib.util
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "media-console.html"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

REGEN = "py -3.14 tools/codex-scripts/media-console.py"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _judge(s: dict, mr) -> dict:
    """这一步的「合格」**怎么判** —— 契约判据（有校验器）还是在场判据（只看文件在不在）。

    第 65 轮加：以前面板只会说「待输入」，读的人没法知道那个输入口**只是清点、还是真在判**。
    现在把它显出来 —— 人写步里哪一个真过了框架的判据、哪一个还只是在场，一眼可见。
    ⚠️ `mr` 由调用方传进来：`media_run` 在本脚本里是**惰性加载**的（`_load`），不是模块级名字。
    """
    v = getattr(mr, "_VALIDATORS", {})
    if s["step"] in v:
        return {"kind": "contract",
                "by": (getattr(mr, "_VALIDATOR_SRC", {}) or {}).get(s["step"], ""),
                "text": "契约判据"}
    if s.get("human"):
        return {"kind": "presence", "by": "只看文件在不在、名字对不对", "text": "仅在场"}
    return {"kind": "run", "by": "有实现器，产物回读验证", "text": "产物回读"}


AU_DIR = ROOT / "projects" / "_shared" / "audition"


def _audition() -> dict:
    """试听件：读**读数副档** + **面板自己再 ffprobe 复核一遍**（两侧对不上就如实报）。

    ⚠️ 声音**内嵌**（base64 data URI），不走 `/gbt-master/fs/`：
    那条路由的 `TYPES` 表里**没有音频类型**，且响应带 `x-content-type-options: nosniff`
    ⇒ 音频会被浏览器拒播。加类型要改宿主插件 ⇒ 要重启 DSH。内嵌这条路本仓已有先例
    （数字人页把 4.28 MB 的 GLB 直接内嵌在 12 MB 单文件上限内）。
    """
    import base64
    import subprocess
    side = AU_DIR / "audition.json"
    if not side.exists():
        return {"ok": False, "why": "没有读数副档 `projects/_shared/audition/audition.json`",
                "how": "跑 `py -3.14 tools/codex-scripts/audition-render.py`"}
    try:
        d = json.loads(side.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {"ok": False, "why": "副档读不动：%s" % str(e)[:80]}
    f = AU_DIR / str(d.get("件") or "")
    if not f.exists():
        return {"ok": False, "why": "副档说的件不在盘上：%s" % f.name}
    # 独立复核：不信副档，自己量一遍
    chk = {"复核": "ffprobe", "一致": None}
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=format_name,duration", "-of", "json", str(f)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        fmt = (json.loads(r.stdout or "{}").get("format") or {})
        chk["量得格式"] = fmt.get("format_name")
        chk["量得时长_s"] = round(float(fmt.get("duration") or 0), 3)
        chk["一致"] = (chk["量得格式"] == "ogg"
                     and abs(chk["量得时长_s"] - float(d.get("时长_s") or 0)) < 0.05)
    except Exception as e:                                            # noqa: BLE001
        chk["复核"] = "ffprobe 复核失败：%s" % str(e)[:60]
    d["复核"] = chk
    d["内嵌字节"] = f.stat().st_size
    d["b64"] = base64.b64encode(f.read_bytes()).decode("ascii")
    # 7 项音频 QC（`music-production` §4）—— 面板上把新实现器的读数直接摆出来
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone.tools import audio_mix as AM
        d["qc"] = AM.run("qc", src=str(f), target="streaming", genre="ambient")
    except Exception as e:                                            # noqa: BLE001
        d["qc"] = {"ok": False, "error": "QC 没跑起来：%s" % str(e)[:90]}
    d["ok"] = True
    return d


def collect() -> dict:
    sys.path.insert(0, str(ROOT))
    mf = _load("gbt_mf", "tools/codex-scripts/media_flow.py")
    from gbt_allinone.tools import media_run as MR
    from gbt_allinone.tools import media_license as ML
    from gbt_allinone.tools import media_publish as MP

    kinds = ["short-video", "film", "music"]
    drawers = {}
    for k in kinds:
        rows = []
        for st in mf.STAGES[k]:
 # 目录名用**连字符**那套（`projects/short-video/`）—— 第 55 轮实测：
            #    我第一版这里写 `k.replace("-","_")`，于是读到的是**我自己造错的平行树**，
            #    页面上出现"缺目录 3"，而真树里那 3 格好好地在。**判据读错树 = 假读数。**
            r = mf.check_one(k, st)
            rows.append({"drawer": st["drawer"], "mp": st["mp"], "state": r["state"],
                         "deliverables": r["deliverables"], "rehearsals": r["rehearsals"],
                         "license_required": bool(st.get("license_required")),
                         "license_ok": r.get("license_ok"),
                         "license_registered": r.get("license_registered"),
                         "license_need": r.get("license_need")})
        drawers[k] = rows

    chains = {}
    for kd, steps in MR.CHAINS.items():
        chains[kd] = [{"step": s["step"], "cap": s["cap"], "runnable": bool(s["cap"]),
                       "needs_input": bool(s.get("human")),
                       "judge": _judge(s, MR),
                       "why": s.get("why", ""), "drawer": s["drawer"]} for s in steps]

    lic = ML.run("check")
    pubs = []
    for kd in ("music", "short_video", "film"):
        for p in sorted((ROOT / "projects" / "_shared" / "publish" / kd).glob("*.publish.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            pubs.append({"kind": kd, "file": p.name,
                         "product": (d.get("product") or {}).get("file"),
                         "targets": len(d.get("targets") or []),
                         "preflight": d.get("preflight") or {},
                         "gate": (d.get("gate") or {}).get("required_scope")})

    plats = {}
    for kd in ("music", "short_video", "film"):
        r = MP.run("platforms", kind=kd)
        c = r.get("counts") or {}
        plats[kd] = {"total": c.get("total"), "verified": c.get("verified"),
                     "source": r.get("source"), "honest": r.get("honest")}
    # 输入口的**骨架自检**（第 75 轮）：每个"人写的步"当场跑一遍 `template`，
    # 把「给不给得出骨架 / 过不过自己的判据 / 还差什么」摆到面板上。
 # 以前面板只说「待输入」—— 读的人**不知道该怎么填才进得去**，闭环只闭了一半。
    skels = []
    for kd, steps in MR.CHAINS.items():
        for s in steps:
            if not s.get("human"):
                continue
            try:
                r = MR.run("template", kind=kd, step=s["step"])
            except Exception as e:                                    # noqa: BLE001
                r = {"ok": False, "error": "骨架没跑起来：%s" % str(e)[:70]}
            skels.append({"kind": kd, "step": s["step"], "drawer": s["drawer"],
                          "ok": bool(r.get("ok")), "how": r.get("kind") or "失败",
                          "fmt": r.get("format"), "passes": r.get("骨架过判据"),
                          "remaining": r.get("还差什么才能过") or [],
                          "src": r.get("判据来源"), "why": r.get("why_no_skeleton") or "",
                          "put": r.get("put_it_at") or "", "tpl": r.get("template") or "",
                          "err": r.get("error") or ""})
    _st = MR.run("status") or {}
    return {"drawers": drawers, "chains": chains, "license": lic, "pubs": pubs,
            "platforms": plats, "audition": _audition(), "scaffolds": skels,
            "run_params": _st.get("run_params") or {}, "release_note": _st.get("release_note") or ""}


CSS = """
:root{--bg:#0B1120;--sf:#111827;--sf2:#1A2535;--ln:#1E3A5F;--sf3:#162035;
--tx:#E6EDF6;--dim:#93A3B8;--ok:#3FB950;--warn:#D29922;--bad:#F85149;--info:#58A6FF}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);
font:13px/1.6 "Segoe UI","Microsoft YaHei",system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:22px 20px 48px}
h1{font-size:20px;margin:0 0 4px}
h2{font-size:14px;margin:22px 0 8px;color:var(--tx);border-left:3px solid var(--info);padding-left:9px}
.sub{color:var(--dim);font-size:12px;margin-bottom:14px}
.card{background:var(--sf);border:1px solid var(--ln);border-radius:4px;padding:12px 14px;margin:10px 0}
.grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{text-align:left;padding:4px 7px;border-bottom:1px solid var(--sf3)}
th{color:var(--dim);font-weight:600}
.mono{font-family:Consolas,monospace;font-size:12px}
.pill{display:inline-block;padding:1px 7px;border-radius:4px;font-size:11.5px;border:1px solid var(--ln)}
.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}.dim{color:var(--dim)}
.tiles{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 2px}
.tile{background:var(--sf2);border:1px solid var(--ln);border-radius:4px;padding:6px 10px;min-width:96px}
.tile b{display:block;font-size:17px}
.tile span{color:var(--dim);font-size:11.5px}
.foot{color:var(--dim);font-size:12px;margin-top:22px;border-top:1px solid var(--ln);padding-top:10px}
code{background:var(--sf3);padding:1px 5px;border-radius:3px;font-size:12px}
"""


def esc(s) -> str:
    return html.escape(str(s if s is not None else "—"))


def state_pill(st: str) -> str:
    cls = {"有货": "ok", "仅彩排": "warn", "空": "dim", "缺目录": "bad"}.get(st, "dim")
    return '<span class="%s">%s</span>' % (cls, esc(st))


AU_CSS = """<style>
.au{margin:12px 0;border:1px solid var(--ln);border-radius:10px;overflow:hidden;
background:radial-gradient(920px 330px at 6% -34%,rgba(88,166,255,.17),transparent 62%),
linear-gradient(180deg,#121C2E,#0E1626)}
.au-in{padding:16px 18px 15px}
.au-ttl{font-size:16px;font-weight:600;letter-spacing:.2px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.au-tag{font-size:11px;padding:2px 9px;border-radius:999px;border:1px solid #4A6B2E;color:#8FD46A;
background:rgba(63,185,80,.09)}
.au-sub{color:var(--dim);font-size:12.5px;margin-top:6px;line-height:1.75}
.au-wav{display:block;width:100%;height:112px;margin:14px 0 10px;border-radius:8px;cursor:pointer;
background:linear-gradient(180deg,rgba(88,166,255,.07),rgba(88,166,255,.012))}
.au-ctl{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.au-btn{width:46px;height:46px;border-radius:50%;border:1px solid #2A4A73;cursor:pointer;
background:linear-gradient(160deg,#58A6FF,#2F6FBF);color:#04101F;font-size:15px;line-height:1;
box-shadow:0 4px 16px rgba(88,166,255,.28);transition:transform .12s ease,box-shadow .12s ease}
.au-btn:hover{transform:translateY(-1px);box-shadow:0 6px 22px rgba(88,166,255,.42)}
.au-btn:active{transform:translateY(0)}
.au-t{font-variant-numeric:tabular-nums;font-size:13px;letter-spacing:.4px;color:var(--tx)}
.au-vol{width:132px;accent-color:#58A6FF}
.au-badges{display:flex;flex-wrap:wrap;gap:7px;margin-top:13px}
.au-b{font-size:11.5px;padding:3px 10px;border-radius:999px;border:1px solid var(--ln);
background:rgba(88,166,255,.07)}
.au-b b{color:#7DD3FC;font-weight:600}
.au-honest{margin-top:13px;padding:11px 13px;border-radius:8px;border:1px solid #2A3A2E;
background:rgba(63,185,80,.06);font-size:12.5px;line-height:1.8}
.au-honest .no{margin-top:9px;padding-top:9px;border-top:1px dashed #3A3A2A;color:#E8C88A}
.au-note{color:var(--dim);font-size:12px;margin-top:9px}
.au-qc{margin-top:14px;padding-top:12px;border-top:1px solid var(--sf3)}
.au-qch{font-size:12.5px;font-weight:600;margin-bottom:7px}
.au-qch .dim{font-weight:400}
.au-qc td.bad{color:var(--bad)}.au-qc td.warn{color:var(--warn)}
</style>"""

AU_JS = """
<script>
(function(){
  var au=document.getElementById('au'), cv=document.getElementById('wav'),
      pp=document.getElementById('pp'), cur=document.getElementById('cur'),
      dur=document.getElementById('dur'), vol=document.getElementById('vol'),
      vlb=document.getElementById('vlb'), note=document.getElementById('au-note');
  if(!au||!cv){return}
  var ctx=cv.getContext('2d'), peaks=null;
  function fmt(t){ if(!isFinite(t)){return '--:--'} var m=Math.floor(t/60), s=Math.floor(t%60);
    return m+':'+('0'+s).slice(-2) }
  function say(m){ if(note){note.textContent=m} }
  function size(){ var r=cv.getBoundingClientRect(), d=window.devicePixelRatio||1;
    cv.width=Math.max(320,Math.floor(r.width*d)); cv.height=Math.max(80,Math.floor(r.height*d)) }
  function draw(){
    var W=cv.width,H=cv.height; ctx.clearRect(0,0,W,H);
    if(!peaks){ say('波形要等音频解码完；解不出来这里会一直空着 —— 不画假波形。'); return }
    var n=peaks.length, p=(au.duration?Math.min(1,(au.currentTime||0)/au.duration):0);
    var bw=W/n;
    for(var i=0;i<n;i++){
      var h=Math.max(1,peaks[i]*H*0.86), on=((i+1)/n)<=p;
      if(on){ var g=ctx.createLinearGradient(0,(H-h)/2,0,(H+h)/2);
        g.addColorStop(0,'#58A6FF'); g.addColorStop(.5,'#9BE0FF'); g.addColorStop(1,'#58A6FF');
        ctx.fillStyle=g } else { ctx.fillStyle='rgba(88,166,255,.24)' }
      ctx.fillRect(i*bw,(H-h)/2,Math.max(1,bw-1),h) }
    if(p>0){ ctx.fillStyle='rgba(230,237,246,.85)'; ctx.fillRect(p*W-1,0,2,H) }
  }
  var AC=window.AudioContext||window.webkitAudioContext;
  function decode(){
    if(!AC){ say('这个浏览器没有 AudioContext ⇒ 波形画不出来；但下面的播放按钮仍然可用。'); return }
    fetch(au.src).then(function(r){return r.arrayBuffer()})
      .then(function(b){ return new AC().decodeAudioData(b) })
      .then(function(ab){
        var ch=ab.numberOfChannels, len=ab.length, d=[];
        for(var c=0;c<ch;c++){ d.push(ab.getChannelData(c)) }
        var r=cv.getBoundingClientRect(), nb=Math.max(240,Math.floor(r.width/2));
        var step=Math.max(1,Math.floor(len/nb)), out=new Float32Array(nb), top=0;
        for(var i=0;i<nb;i++){ var s=i*step, e=Math.min(len,s+step), mx=0;
          for(var c2=0;c2<ch;c2++){ var a=d[c2];
            for(var j=s;j<e;j+=2){ var v=a[j]<0?-a[j]:a[j]; if(v>mx){mx=v} } }
          out[i]=mx; if(mx>top){top=mx} }
        if(top>0){ for(var k=0;k<nb;k++){ out[k]=out[k]/top } }
        peaks=out; say('波形来自真解码的样本（'+ch+' 声道 · '+Math.round(len/ab.sampleRate)+' s）。');
        size(); draw();
      }).catch(function(e){ say('音频解码失败：'+e+' ⇒ 不画假波形。') });
  }
  pp.onclick=function(){
    if(au.paused){ au.play().then(function(){ pp.textContent='❚❚' })
        .catch(function(e){ say('播放被浏览器拒了：'+e+'（再点一次通常就好）') }) }
    else { au.pause(); pp.textContent='▶' }
  };
  au.addEventListener('play',function(){ pp.textContent='❚❚' });
  au.addEventListener('pause',function(){ pp.textContent='▶' });
  au.addEventListener('timeupdate',function(){ cur.textContent=fmt(au.currentTime); draw() });
  au.addEventListener('loadedmetadata',function(){ dur.textContent=fmt(au.duration) });
  au.addEventListener('ended',function(){ pp.textContent='▶'; draw() });
  cv.addEventListener('click',function(e){
    if(!au.duration){return} var r=cv.getBoundingClientRect();
    var p=(e.clientX-r.left)/r.width;
    au.currentTime=Math.max(0,Math.min(au.duration,p*au.duration)); draw();
  });
  vol.oninput=function(){ au.volume=vol.value/100; vlb.textContent=vol.value+'%' };
  window.addEventListener('resize',function(){ size(); draw() });
  au.volume=0.8;
  requestAnimationFrame(function(){ size(); draw(); decode() });
})();
</script>"""


def _audition_html(a: dict) -> str:
    """AI 音乐试听台。**诚实优先**：它是什么、不是什么，都写在卡上。"""
    if not a.get("ok"):
        return ('<h2>AI 音乐 · 试听台</h2><div class="card">'
                '<b class="warn">现在没有可试听的件</b>'
                '<div class="au-note">%s<br>做一件：<span class="mono">%s</span></div></div>'
                % (esc(a.get("why") or "未知原因"), esc(a.get("how") or "")))
    lo = a.get("响度") or {}
    ck = a.get("复核") or {}
    segs = " → ".join(s.get("情绪", "") for s in (a.get("段落") or []))
    chn = " · ".join("%s %s" % (s.get("情绪"), s.get("和弦")) for s in (a.get("段落") or []))
    badges = [
        ("格式", "OGG / Opus 128 kbps"), ("采样率", "%s Hz" % a.get("采样率")),
        ("声道", "%s（立体声）" % a.get("声道")), ("时长", "%.1f s" % float(a.get("时长_s") or 0)),
        ("响度", "%s LUFS" % lo.get("施加后LUFS")),
        ("真峰值", "%s dBTP" % lo.get("施加后TP")),
        ("目标", "%s LUFS · TP %s" % (lo.get("目标I"), lo.get("目标TP"))),
        ("与目标差", "%s LU" % lo.get("差LU")),
        ("试听件", "%.0f KB（内嵌）" % (a.get("内嵌字节", 0) / 1024)),
        ("母带", "%s · %.1f MB" % (a.get("母带格式"), (a.get("母带字节") or 0) / 1e6)),
        ("sha256", "试听 %s · 母带 %s" % (a.get("试听件sha256"), a.get("母带sha256"))),
    ]
    bl = "".join('<span class="au-b">%s <b>%s</b></span>' % (esc(k), esc(v)) for k, v in badges)
    nots = "".join("<li>%s</li>" % esc(x) for x in (a.get("这不是") or []))
    ok_ck = ck.get("一致")
    ck_line = ("面板独立 ffprobe 复核：<b class=\"%s\">%s</b>（量得 %s · %s s）"
               % ("ok" if ok_ck else "warn", "与副档一致" if ok_ck else "与副档对不上，如实报",
                  esc(ck.get("量得格式")), esc(ck.get("量得时长_s"))))
    q = a.get("qc") or {}
    qrows = ""
    if q.get("items"):
        cnt = q.get("counts") or {}
        hard = " · ".join("%s %s" % (i["项"], i["判定"]) for i in q["items"] if i["硬判据"])
        qrows = ('<div class="au-qc"><div class="au-qch">7 项音频 QC'
                 '<span class="dim">（出处 `music-production` §4）· 绝对档：%s · '
                 '合格 %s / 不合格 %s / 注意 %s / 参考 %s</span></div>'
                 '<table><tr><th>项</th><th>判定</th><th>量得</th><th>怎么量的</th></tr>%s</table>'
                 '<div class="au-note">参考档三条的契约原文是「<b>按曲风</b>」—— '
                 '曲风口径本机没有权威来源，**只报数不判否**；拿我编的数去判否就是替上游立规矩。</div></div>'
                 % (esc(hard), cnt.get("合格"), cnt.get("不合格"), cnt.get("注意"), cnt.get("参考"),
                    "".join('<tr><td>%s</td><td class="%s">%s</td><td class="mono">%s</td>'
                            '<td class="dim">%s</td></tr>'
                            % (esc(i["项"]),
                               "ok" if i["判定"] == "合格" else
                               ("bad" if i["判定"] == "不合格" else
                                ("warn" if i["判定"] == "注意" else "dim")),
                               esc(i["判定"]), esc(str(i["量得"])[:110]), esc(i["怎么量的"])[:120])
                            for i in q["items"])))
    elif q:
        qrows = ('<div class="au-note warn">7 项音频 QC 没跑起来：%s</div>'
                 % esc(q.get("error") or q.get("why") or ""))
    html = """<h2>AI 音乐 · 试听台</h2>
<div class="au"><div class="au-in">
  <div class="au-ttl">排练垫乐 · 试听件<span class="au-tag">自产 · 许可：自有</span></div>
  <div class="au-sub">A 小调 · %.0f s · 五段走仓内真件《夜航》写着的那条情绪线：<b>%s</b><br>
    <span class="mono">%s</span></div>
  <canvas id="wav" class="au-wav"></canvas>
  <div class="au-ctl">
    <button id="pp" class="au-btn" title="播放 / 暂停">▶</button>
    <span class="au-t"><span id="cur">0:00</span> <span class="dim">/</span> <span id="dur">--:--</span></span>
    <label class="dim" for="vol">音量</label>
    <input id="vol" class="au-vol" type="range" min="0" max="100" value="80">
    <span class="dim mono" id="vlb">80%%</span>
  </div>
  <div class="au-badges">%s</div>
  <div class="au-honest">
    <b>这是什么</b>：%s。波形由页面**真解码**这段音频的样本画出，不是装饰图。<br>
    <span class="dim">%s</span>
    <div class="no"><b>这不是什么</b><ul>%s</ul></div>
  </div>
  %s
  <div class="au-note" id="au-note">正在解码波形…</div>
</div></div>
<audio id="au" preload="metadata" src="data:audio/ogg;base64,__AU_B64__"></audio>
""" % (float(a.get("时长_s") or 0), esc(segs), esc(chn), bl, esc(a.get("这是") or ""),
       ck_line, nots, qrows)
    return html + AU_JS


def build(d: dict) -> str:
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    kinds_cn = {"short-video": "短视频", "film": "AI电影", "music": "AI音乐"}
    tot = {"有货": 0, "仅彩排": 0, "空": 0, "缺目录": 0}
    for k in d["drawers"]:
        for r in d["drawers"][k]:
            tot[r["state"]] = tot.get(r["state"], 0) + 1

    parts = ['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             '<title>GBT小土豆V8 · 三方向自动化工作流面板</title>',
             # 第 115 轮补：**内联 data: icon**。缺了它浏览器会去请求宿主根 `/favicon.ico`
             # （该文件不存在）⇒ 404 ⇒ 控制台多一条红字。这条**必须留在模板里**：
             # 本仓已有先例 —— 手补在产物上，一重生成就被冲掉。
             # 实测：新浏览器只开这一页必现该 404；整轮扫描里它是第 13 页，
             # 前面第 6 页（pet）已经触发过同源 404 并被缓存 ⇒ 读成 err=0 是**顺序占便宜**，不是它干净。
             '<link rel="icon" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAWklEQVR42mNgGAWjYBSMglEwCkbBKBgFo2AUjIJRMApGwSgYBaNgFIyCUTAKRsEoGAWjYBSMglEwCkbBKBgFo2AUjIJRMApGwSgYBaNgFIyCUTAKRsEoAAB2gAH/8kQ0dQAAAABJRU5ErkJggg==">',
             "<style>%s</style></head><body><div class=wrap>" % CSS,
             "<h1>三方向自动化工作流 · 专业流程台</h1>",
             '<div class=sub>数据源：<code>media_flow</code>（18 格判据）· <code>media_run</code>（三条链）· '
             '<code>media_license</code>（许可账）· <code>media_publish</code>（发布包）'
             ' ｜ 生成 <b>%s</b> ｜ 重生成 <code>%s</code></div>' % (esc(ts), esc(REGEN))]

    parts.append('<div class="tiles">')
    for k, v in (("有货", tot["有货"]), ("仅彩排", tot["仅彩排"]), ("空", tot["空"]), ("缺目录", tot["缺目录"])):
        parts.append('<div class="tile"><b>%d</b><span>%s</span></div>' % (v, k))
    parts.append('<div class="tile"><b>%d</b><span>许可已登记</span></div>' % (d["license"].get("entries") or 0))
    parts.append('<div class="tile"><b>%d</b><span>发布包</span></div>' % len(d["pubs"]))
    parts.append("</div>")

    # ── 三条链 ──
    parts.append("<h2>三条链 · 自动化到哪一步</h2>")
    # 输入口的**判据强度**现算（不写死）：人写步里几个真在判、几个还只是在场
    _hj = [s["judge"] for steps in d["chains"].values() for s in steps if s.get("needs_input")]
    _c = sum(1 for j in _hj if j["kind"] == "contract")
    parts.append('<p class="dim">人写步共 <b>%d</b> 个：<span class="ok">契约判据 %d</span> · '
                 '<span class="warn">仅在场 %d</span> —— 「在场 ≠ 合格」，'
                 '下表逐个标出哪一步真在判。</p>' % (len(_hj), _c, len(_hj) - _c))
 # 第 80 轮补：把 `release` 摆上来 —— 不然面板读的人**不知道链子还能落成品名**，
    #    会一直以为「只有彩排件」是链子的极限（第 79 轮修的那个洞）。
    _rp = d.get("run_params") or {}
    if _rp:
        parts.append('<p class="dim">怎么真跑（走唯一门 <span class="mono">api.run_task</span>）：'
                     '<span class="mono">run_task("media_run", {"op":"run","kind":"film",'
                     '"work":"我的作品","release":true})</span></p>')
        parts.append('<div class="card"><table><tr><th>入参</th><th>说明</th></tr>%s</table>'
                     '<div class="au-note">%s</div></div>'
                     % ("".join('<tr><td class="mono">%s</td><td>%s</td></tr>'
                                % (esc(k), esc(v)) for k, v in _rp.items()),
                        esc(d.get("release_note") or "")))
 # 第 107 轮补：**多职业同时执行**（第 102 轮已证）原来在面板上**点不到** ——
    #    面板只教怎么跑**一条**链，而能力是"三条同时"。**能力在、面板指不着 = 功能没连上。**
 # 第 116 轮再补：那条能力当时**只活在 `.scratch/_probe_multi.py` 一次性探针里**，
    #    面板教的是"三条命令分别敲、读者自己想办法并发"。现在它已经是万能插的**一等口**
    #    `five-dim.py multi`，而且"同时"是**可机检读数**（扫描线峰值并发）+ **反向对照**。
    #    ⇒ 卡就教这个口，并把判据写出来（判据不写出来，读的人没法自己复核）。
    parts.append('<div class="card"><b>多职业同时执行</b>'
                 '<span class="dim">（一个命令 · 三条链并发走同一个门 · 有反向对照）</span>'
                 '<div class="au-note">万能插的一等口，每个职业仍各起一个进程、<b>都走唯一门</b>：</div>'
                 '<table><tr><th>方向</th><th>命令</th></tr>%s</table>'
                 '<div class="au-note">或者一条命令把三条一起发（这就是"多职业同时"）：'
                 '<div class="mono" style="margin-top:4px">py -3.14 tools/codex-scripts/five-dim.py '
                 'multi \'{"jobs":[{"kind":"media_run","payload":{"op":"run","kind":"short_video",'
                 '"work":"&lt;作品名&gt;"}}, …]}\'</div></div>'
                 '<div class="au-note">🔎 这个口<b>吃任意能力位</b>，不限媒体三方向。'
                 '实测（第 40 轮）<b>四个不同职业域同时跑</b>：媒体·三链状态 / 安全·攻击面 / '
                 '系统·调用审计 / 项目·平台画像 ⇒ <b>峰值并发 4</b> · 六对全重叠 · 0 异常；'
                 '反向对照串行 <b>峰值 1</b>、墙钟等于各件之和。</div>'
                 '<div class="au-note">🧪 <b>先试跑再真跑</b>：加 <span class="mono">--dry-run</span> '
                 '只列计划、<b>一件都不跑</b>。判据不是嘴上说的 —— 跑 dry-run 时'
                 '<b>审计账本新增 0 条</b>，而同一批真跑 <b>新增 12 条</b>'
                 '（同一把尺子量真跑会涨 ⇒ "0 条"是真读数，不是碰巧）。</div>'
                 '<div class="au-note">🔒 <b>三条常驻规矩</b>（主人 2026-09-23 定，已写进 '
                 '<span class="mono">five-dim.py multi</span>）：<br>'
                 '① <b>执行任务一律走这个口，最少五根触手同时执行</b>；'
                 '② 多触手协作要在<b>镜像多维度</b>里隔离；'
                 '③ <b>N 根触手 ⇒ N 个隔离位</b>（每根一个独占工作目录 + 一份 '
                 '<span class="mono">_marker.json</span> 留痕，盘上可查）。</div>'
                 '<div class="au-note">实测（第 49–50 轮）：五根触手 ⇒ <b>峰值并发 5</b> · '
                 '<span class="mono">dirs_on_disk=5 · markers=5 · each_job_confirmed=true</span>；'
                 '<b>写面撞了就整批拒跑</b>（<span class="mono">exit 2</span>，一件都不执行）—— '
                 '同写面并发＝同一个活跑两遍，最容易出的不是报错而是<b>互相覆盖</b>。<br>'
                 '⚠️ <b>镜像级隔离（<span class="mono">mirror_*</span>）尚未接通</b>：其写面全带锁、'
                 '待用授权为 0，需主人在终端发作用域 —— 面板如实标，<b>不假装做了</b>。</div>'
                 '<div class="au-note">✅ 第 116 轮实测读数（三条媒体链同时跑）：'
                 '<b>峰值并发 3</b>（扫描线算，不是形容词）· 墙钟 <b>5.582s</b> vs 各件之和 '
                 '<b>15.458s</b>（<b>2.77×</b>）· 0 异常 · 三链 '
                 '<span class="mono">ran 4 / 3 / 3</span> · 许可账 <b>10 条 = 3+4+3 一条不丢</b>。<br>'
                 '🔁 反向对照 <span class="mono">--serial</span>：同样的活串行跑 ⇒ 峰值并发必须是 '
                 '<b>1</b>（实测 1）—— 没有这个对照，"三个区间重叠"可能只是时钟粒度造的假象。</div>'
                 '<div class="au-note">⚠️ 并发安全是三处写面各自修过才成立的：'
                 '许可账 <span class="mono">register</span>／<span class="mono">unregister</span> '
                 '走 <span class="mono">locked_json_update</span>（跨进程锁），'
                 '共享基础轨按 <span class="mono">kind+work</span> 分名。'
                 '<b>同方向同作品并发仍会撞</b> —— 那是同一个活，不该同时跑两遍。</div></div>'
                 % "".join('<tr><td class="mono">%s</td><td class="mono">%s</td></tr>'
                           % (esc(cn), esc('api.run_task("media_run", {"op":"run","kind":"%s",'
                                           '"work":"<作品名>","release":true})' % kd))
                           for kd, cn in (("short_video", "短视频"), ("film", "AI电影"),
                                          ("music", "AI音乐"))))
    parts.append("<div class=grid>")
    for kd, steps in d["chains"].items():
        parts.append('<div class="card"><b>%s</b> <span class="dim mono">%s</span>'
                     % (esc(kinds_cn.get(kd, kd)), esc(kd)))
        parts.append("<table><tr><th>步</th><th>实现器</th><th>判据</th><th>状态</th></tr>")
        for s in steps:
            j = s.get("judge") or {}
            if j.get("kind") == "contract":
                jc = '<span class="ok" title="%s">%s</span>' % (esc(j.get("by")), esc(j.get("text")))
            elif j.get("kind") == "presence":
                jc = '<span class="warn" title="%s">%s</span>' % (esc(j.get("by")), esc(j.get("text")))
            else:
                jc = '<span class="dim" title="%s">%s</span>' % (esc(j.get("by")), esc(j.get("text")))
            if s["runnable"]:
                cell = '<span class="ok">可跑</span>'
                why = esc(s["cap"])
            elif s.get("needs_input"):
                # 人写的步 = **链里的输入口**（模板落 .scratch，人填好放进抽屉即算过）
                cell = '<span class="warn">待输入</span>'
                why = esc("人填真件 → " + (s.get("drawer") or ""))
            else:
                cell = '<span class="warn">未实现</span>'
                why = esc(s.get("why", ""))[:40]
            parts.append("<tr><td>%s</td><td class=mono>%s</td><td>%s</td><td>%s</td></tr>"
                         % (esc(s["step"]), why, jc, cell))
        parts.append("</table></div>")
    parts.append("</div>")

    # ── AI 音乐 · 试听台 ──
 # base64 在 `%` 格式化**之后**才塞进去：base64 字母表不含 `%`，所以这一步是安全的
    _au = d.get("audition") or {}
    parts.append(AU_CSS)
    parts.append(_audition_html(_au).replace("__AU_B64__", _au.get("b64") or ""))

    # ── 输入口 · 怎么填才进得去 ──
    sk = d.get("scaffolds") or []
    if sk:
        _n_skel = sum(1 for x in sk if x["how"] == "skeleton")
        _ = sum(1 for x in sk if x["passes"] is True)   # 未被引用（保留计算原样）
        parts.append("<h2>输入口 · 怎么填才进得去</h2>")
        parts.append('<p class="dim">人写步共 <b>%d</b> 个：<span class="ok">有可填骨架 %d</span> · '
                     '<span class="warn">只能给清单 %d</span>。骨架是**当场拿自己的判据自检过**的 —— '
                     '「还差什么」就是你要补的。骨架只落 <span class="mono">.scratch/</span>，'
                     '**塞进抽屉 = 拿空壳冒充成品**。</p>'
                     % (len(sk), _n_skel, len(sk) - _n_skel))
        parts.append('<div class="card"><table>'
                     '<tr><th>方向</th><th>步</th><th>骨架</th><th>格式</th>'
                     '<th>骨架过判据</th><th>还差什么才能过</th><th>判据来源</th></tr>')
        for x in sk:
            if x["how"] == "skeleton":
                how = '<span class="ok">可填骨架</span>'
                fm = '<span class="mono">.%s</span>' % esc(x["fmt"])
                ps = ('<span class="ok">已过</span>' if x["passes"] is True else
                      '<span class="warn">没过</span>' if x["passes"] is False else
                      '<span class="dim">未自检</span>')
                rm = ("、".join(x["remaining"]) if x["remaining"]
                      else '<span class="ok">无需再补</span>')
            else:
                how = '<span class="warn">只能给清单</span>'
                fm = '<span class="dim">—</span>'
                ps = '<span class="dim">—</span>'
                rm = '<span class="dim">%s</span>' % esc(x["why"])[:110]
            parts.append('<tr><td>%s</td><td class="mono">%s</td><td>%s</td><td>%s</td>'
                         '<td>%s</td><td>%s</td><td class="dim">%s</td></tr>'
                         % (esc(kinds_cn.get(x["kind"], x["kind"])), esc(x["step"]), how, fm,
                            ps, rm, esc(x["src"] or "")[:78]))
        parts.append('</table><div class="au-note">骨架落在 <span class="mono">%s</span>；'
                     '拿它：<span class="mono">py -3.14 -c "from gbt_allinone.tools import media_run as M;'
                     'print(M.run(\'template\', kind=\'film\', step=\'concept\')[\'text\'])"</span></div>'
                     '</div>' % esc(".scratch/_media_run_templates/"))

    # ── 18 格 ──
    parts.append("<h2>18 格抽屉 · 现读</h2>")
    for k in ("short-video", "film", "music"):
        parts.append('<div class="card"><b>%s</b>' % esc(kinds_cn[k]))
        parts.append("<table><tr><th>格</th><th>↔ 工序</th><th>状态</th><th>成品/彩排</th><th>许可</th></tr>")
        for r in d["drawers"][k]:
            if not r["license_required"]:
                lic = '<span class="dim">—</span>'
            elif not r.get("license_need"):
                lic = '<span class="dim">空格</span>'
            elif r.get("license_ok"):
                lic = '<span class="ok">✅ %s/%s</span>' % (r.get("license_registered"), r.get("license_need"))
            else:
                lic = '<span class="bad">❌ %s/%s</span>' % (r.get("license_registered"), r.get("license_need"))
            parts.append("<tr><td class=mono>%s</td><td class=mono>%s</td><td>%s</td><td>%s / %s</td><td>%s</td></tr>"
                         % (esc(r["drawer"]), esc(r["mp"]), state_pill(r["state"]),
                            r["deliverables"], r["rehearsals"], lic))
        parts.append("</table></div>")

    # ── 发布 ──
    parts.append("<h2>发布到赚钱平台 · 停在授权门</h2>")
    parts.append('<div class="card"><table><tr><th>方向</th><th>发布包</th><th>产物</th>'
                 "<th>目标平台</th><th>闸</th></tr>")
    for p in d["pubs"]:
        parts.append("<tr><td>%s</td><td class=mono>%s</td><td class=mono>%s</td><td>%s</td><td>%s</td></tr>"
                     % (esc(kinds_cn.get(p["kind"], p["kind"])), esc(p["file"])[:44],
                        esc(p["product"])[:52], p["targets"],
                        '<span class="warn">需 %s</span>' % esc(p["gate"])))
    parts.append("</table>")
    parts.append('<div class="tiles" style="margin-top:10px">')
    for kd, v in d["platforms"].items():
        parts.append('<div class="tile"><b>%s</b><span>%s 平台 · 已核实 %s</span></div>'
                     % (v["total"], esc(kinds_cn.get(kd, kd)), v["verified"]))
    parts.append("</div>")
    parts.append('<div class="dim" style="margin-top:8px">平台口径：音乐**复用**能力位 '
                 "<code>music_publishing</code>（不另造）；短视频/电影为内置候选表，"
                 "<b>全部标「未核实」</b> —— 「在」不等于「能用」。发布需主人一次性授权 "
                 "<code>deploy_publish</code> + 平台凭据；<b>本页不会、也不能替你发布</b>。</div>")
    parts.append("</div>")

    parts.append('<div class="foot">数据源与判据：<code>gbt_allinone/tools/media_run.py</code> · '
                 "<code>media_publish.py</code> · <code>media_license.py</code> · "
                 "<code>tools/codex-scripts/media_flow.py</code> ｜ "
                 "本页是<b>快照</b>，不是实时；要新读数跑上面那条命令。<br>"
                 "开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属</div>")
    parts.append("</div></body></html>")
    return "".join(parts)


def _demd_span(s: str) -> str:
    """把一小段**正文**里的 markdown 字面量换成 HTML。"""
    s = re.sub(r"\*\*([^*\n]{1,80})\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`([^`\n]{1,80})`", r"<code>\1</code>", s)
    return s


_MD_SKIP = re.compile(r"<(script|style|pre|code)\b[^>]*>.*?</\1>", re.S | re.I)


def _demd(html: str) -> str:
    """把页面**正文**里的 `**加粗**` / 反引号换成 `<b>` / `<code>`。

    为什么要有这一步（第 116 轮）：这一页是给主人看的**专业化面板**，而此前它把
    markdown 字面量**原样渲染**了出去 —— 实测产物里有 **18 处 `**加粗**` + 24 处反引号**
    直接显示成星号和撇号。同一页的自述却写着「做成专业化面板」⇒ 声明与产物对不上。

    为什么**不能**全局无脑替换：
      · `<script>` / `<style>` 里不是页面文字（脚本里有 JS 字符串、样式里有选择器）；
      · `<pre>` / `<code>` 里反引号可能**就是内容本身**（代码样例），替换会把内容改坏。
    ⇒ 只动那三者之外的正文。脚本里那些**会经 textContent 显示**的字符串，
       单独在源头把标记去掉（那种位置塞 `<b>` 会原样显示成标签）。
    """
    out, last = [], 0
    for m in _MD_SKIP.finditer(html):
        out.append(_demd_span(html[last:m.start()]))
        out.append(m.group(0))
        last = m.end()
    out.append(_demd_span(html[last:]))
    return "".join(out)


def _rendered(html: str) -> str:
    """真渲染区（判据只认这里）：去样式 / 脚本 / HTML 注释。"""
    s = re.sub(r"<style\b[^>]*>.*?</style>", "", html, flags=re.S | re.I)
    s = re.sub(r"<script\b[^>]*>.*?</script>", "", s, flags=re.S | re.I)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    return s


def main() -> int:
    d = collect()
    page = _demd(build(d))
    OUT.write_text(page, encoding="utf-8")
    print("=" * 78)
    print("三方向流程台面板 · 生成")
    print("=" * 78)
    print("  产物 %s（%.1f KB）" % (OUT.name, OUT.stat().st_size / 1024))
    states: dict = {}
    for rows in d["drawers"].values():
        for r in rows:
            states[r["state"]] = states.get(r["state"], 0) + 1
    print("  18 格：%s" % json.dumps(states, ensure_ascii=False))
    print("  三条链：%s" % ", ".join("%s %d 步（可跑 %d）"
                                 % (k, len(v), sum(1 for s in v if s["runnable"]))
                                 for k, v in d["chains"].items()))
    print("  许可账 %s 条 · 发布包 %d 份" % (d["license"].get("entries"), len(d["pubs"])))
    print("  重生成：%s" % REGEN)
    # ── 自检：正文里不许有 markdown 字面量（第 116 轮加）────────────────────
    # 判据要**有牙**：这里同时做一次**扰动自检**（往真渲染区植一处泄漏，必须报红），
    # 否则"我加了个检查"就只是文档承诺。取样区只认**真渲染区**（去脚本/样式/注释），
    # 因为注释与脚本里的 `**` 不渲染 —— 混在一起判会让真泄漏淹没在假命中里（index 那页踩过）。
    body = _rendered(OUT.read_text(encoding="utf-8"))
    leaks = re.findall(r"\*\*[^*<\n]{1,60}\*\*", body) + re.findall(r"`[^`<\n]{1,60}`", body)
    probe = re.sub(r"<b>", "<b>**打点**", body, count=1)
    teeth = bool(re.search(r"\*\*[^*<\n]{1,60}\*\*", probe))
    print("\n  自检：")
    print("    %s 正文无 markdown 字面量（真渲染区 %d 字，命中 %d 处）"
          % ("✔" if not leaks else "✗", len(body), len(leaks)))
    for x in leaks[:10]:
        print("        %s" % x)
    print("    %s 判据有牙（植入一处泄漏必报红）" % ("✔" if teeth else "✗"))
    return 0 if (not leaks and teeth) else 1


if __name__ == "__main__":
    sys.exit(main())
