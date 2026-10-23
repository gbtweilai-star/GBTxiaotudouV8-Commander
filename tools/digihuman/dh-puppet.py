# -*- coding: utf-8 -*-
"""dh-puppet.py — 把一张形象图**拆件**成浏览器里能转的"纸片人"（Live2D 那套思路，零 GPU）。

## 为什么另起一件（Owner 2026-10-21：「浏览器以图片播放动作和语音不会吗」）
2.5D 整图平移不叫动（§85 认账）。要做真动作就得**按关节拆件**：
  基座（腿/全身）· 躯干（绕胯转 + 呼吸）· 头+发（绕脖子转，叠在躯干里跟着走）。
拆出来的件全是原图像素，**像素级还是她**；转动的是件，所以动作看得见。

产出（`outputs/dh-puppet/`）：
  base.png · torso.png · head.png · cavity.png · meta.json（枢轴/尺寸/百分比）· index.html（舞台+驱动）

## 用法
  py -3.14 tools/digihuman/dh-puppet.py            # 拆件 + 生成页面
  py -3.14 tools/digihuman/dh-puppet.py --check    # 只报几何/尺寸，不写盘
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
THEATER = ROOT / "holo_pet_w3" / "voice-theater"
SRC_DIR = THEATER / "assets" / "dh2d"
OUT = ROOT / "outputs" / "dh-puppet"

# 件在图（736×1190）里的矩形：x0,y0,x1,y1 —— 按 meta.json 的锚点推的，留了余量好羽化
BOXES = {
    "head":  (238, 6, 488, 246),
    "torso": (244, 196, 494, 436),
}
PIVOTS = {                      # 枢轴（原图像素坐标）
    "head":  (362, 206),        # 脖子
    "torso": (362, 430),        # 胯
}


def feather(w: int, h: int, kind: str, r: float = 0.16) -> np.ndarray:
    """羽化遮罩：head 用椭圆、torso 用圆角矩形 —— 边缘软一点，转动时不露硬边。"""
    yy, xx = np.mgrid[0:h, 0:w]
    nx = (xx / max(1, w - 1)) * 2 - 1
    ny = (yy / max(1, h - 1)) * 2 - 1
    if kind == "head":
        d = np.sqrt((nx / 1.0) ** 2 + (ny / 1.0) ** 2)
    else:
        # 圆角矩形：把外框按圆角半径收一点
        ax, ay = np.abs(nx), np.abs(ny)
        d = np.maximum(ax / 1.0, ay / 1.0)
    m = 1.0 - np.clip((d - (1.0 - r)) / r, 0.0, 1.0)
    return (m * 255).astype(np.uint8)


def cut(img: Image.Image, box, kind: str) -> Image.Image:
    x0, y0, x1, y1 = box
    crop = img.crop(box).convert("RGBA")
    w, h = crop.size
    a = np.asarray(crop)[:, :, 3].astype(np.float32)
    m = feather(w, h, kind).astype(np.float32) / 255.0
    a = a * m
    arr = np.asarray(crop).copy()
    arr[:, :, 3] = a.astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


# ── 上云（与 dh-live 同一条判据：公网回下载比 sha256）────────────────────────
def publish() -> dict:
    import hashlib
    import subprocess
    import urllib.request
    BUCKET = os.environ.get("GBT_R2_BUCKET", "gbt-motion")
    PUBLIC = "https://pub-3b817fc945aa4e1c8d7cce0ea93fa725.r2.dev"
    CT = {".html": "text/html; charset=utf-8", ".png": "image/png",
          ".mp3": "audio/mpeg", ".json": "application/json", ".js": "application/javascript"}
    rows, bad = [], []
    for p in sorted(OUT.iterdir()):
        if not p.is_file():
            continue
        key = "live/puppet-tw-01/%s" % p.name
        env = dict(os.environ, GBT_R2_BUCKET=BUCKET)
        up = subprocess.run(["wrangler", "r2", "object", "put", "%s/%s" % (BUCKET, key),
                             "--file", str(p), "--remote",
                             "--content-type", CT.get(p.suffix, "application/octet-stream")],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", env=env, shell=True, timeout=900)
        blob = (up.stdout or "") + (up.stderr or "")
        if "Upload complete" not in blob:
            bad.append({"file": p.name, "why": "upload", "tail": blob[-200:]})
            continue
        url = "%s/%s" % (PUBLIC, key)
        data = b""
        for _ in range(4):
            try:
                with urllib.request.urlopen(urllib.request.Request(
                        url, headers={"user-agent": "gbt-pub/1.0"}), timeout=120) as s:
                    data = s.read()
                break
            except Exception:                                      # noqa: BLE001
                continue
        want = hashlib.sha256(p.read_bytes()).hexdigest()
        rows.append({"file": p.name, "bytes": p.stat().st_size,
                     "pub": len(data), "sha_match": hashlib.sha256(data).hexdigest() == want})
    ok = not bad and bool(rows) and all(r["sha_match"] for r in rows)
    return {"ok": ok, "page": "%s/live/puppet-tw-01/index.html" % PUBLIC,
            "files": rows, "bad": bad}


PAGE = """<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s</title>
<style>
 html,body{margin:0;height:100%%;background:radial-gradient(120%% 80%% at 50%% 0%%,#1b2233 0%%,#0b0e14 60%%,#07090d 100%%);overflow:hidden}
 #stage{position:fixed;inset:0;display:grid;place-items:center}
 #rig{position:relative;height:96%%;aspect-ratio:%(w)d / %(h)d;will-change:transform}
 #rig img{position:absolute;display:block;pointer-events:none;user-select:none}
 #torso,#head{will-change:transform}
 #bar{position:fixed;left:0;right:0;bottom:0;display:flex;gap:10px;align-items:center;
      padding:10px 14px;font:14px/1.4 system-ui,sans-serif;color:#e8e8ea;
      background:linear-gradient(transparent,rgba(0,0,0,.7))}
 button{font:inherit;padding:8px 16px;border-radius:999px;border:0;background:#f2c14e;color:#20180a;font-weight:600;cursor:pointer}
 #read{opacity:.8;font-size:12px;white-space:pre;font-variant-numeric:tabular-nums}
</style></head><body>
<div id="stage"><div id="rig">
  <img id="base" src="base.png" style="left:0;top:0;width:100%%;height:100%%">
  <div id="torso" style="position:absolute;left:%(tx).3f%%;top:%(ty).3f%%;width:%(tw).3f%%;height:%(th).3f%%;transform-origin:%(tpx).2f%% %(tpy).2f%%">
    <img src="torso.png" style="left:0;top:0;width:100%%;height:100%%">
    <div id="head" style="position:absolute;left:%(hx).3f%%;top:%(hy).3f%%;width:%(hw).3f%%;height:%(hh).3f%%;transform-origin:%(hpx).2f%% %(hpy).2f%%">
      <img src="head.png" style="left:0;top:0;width:100%%;height:100%%">
      <img id="cav" src="cavity.png" style="left:%(mx).2f%%;top:%(my).2f%%;width:%(mw).2f%%;height:%(mh).2f%%;opacity:0;border-radius:50%%;filter:blur(1.2px);transform-origin:50%% 20%%">
    </div>
  </div>
</div></div>
<div id="bar"><button id="go">▶ 讓她說話</button><span id="read">載入…</span></div>
<audio id="au" src="voice.mp3" preload="auto"></audio>
<script>
(function(){
  var rig=document.getElementById('rig'), torso=document.getElementById('torso'),
      head=document.getElementById('head'), cav=document.getElementById('cav'),
      au=document.getElementById('au'), go=document.getElementById('go'),
      read=document.getElementById('read');
  var st={lean:0,breath:0,roll:0,pitch:0,jaw:0,lv:0}, playing=false, ctx, ana, buf, t0=performance.now();
  function setT(el, v){ el.style.transform=v; }
  function loop(){
    var t=(performance.now()-t0)/1000;
    /* 躯干：换重心（绕胯）+ 俯仰呼吸；说话时幅度加大 */
    st.lean  = 2.6*Math.sin(t*0.35) + 1.4*Math.sin(t*0.13) + 1.6*st.lv*Math.sin(t*1.1);
    st.breath= 1.0 + 0.007*Math.sin(t*1.7) + 0.010*st.lv*Math.sin(t*2.3);
    setT(torso,'rotate('+st.lean.toFixed(3)+'deg) scaleY('+st.breath.toFixed(4)+')');
    /* 头：绕脖子 roll + pitch（点头），叠在躯干里所以跟着身体走 */
    st.roll = 3.6*Math.sin(t*0.29) + 1.5*Math.sin(t*0.73) + 2.2*st.lv*Math.sin(t*1.6);
    st.pitch= 2.6*Math.sin(t*0.51) + 5.0*st.lv*Math.sin(t*2.9);
    setT(head,'rotate('+st.roll.toFixed(3)+'deg) translateY('+(st.pitch*0.6).toFixed(2)+'px)');
    /* 嘴：音量驱动 */
    cav.style.opacity = Math.min(0.82, st.jaw*1.35).toFixed(3);
    cav.style.transform='scaleY('+(0.35+1.25*st.jaw).toFixed(3)+')';
    read.textContent='lean '+st.lean.toFixed(2)+'°  roll '+st.roll.toFixed(2)+'°  pitch '+
      st.pitch.toFixed(2)+'  jaw '+st.jaw.toFixed(2)+'  lv '+st.lv.toFixed(2);
    window.__PUPPET={lean:st.lean,roll:st.roll,pitch:st.pitch,jaw:st.jaw,lv:st.lv,breath:st.breath};
    requestAnimationFrame(loop);
  }
  loop();
  function drive(){
    if(!playing) return;
    ana.getByteTimeDomainData(buf);
    var s=0; for(var i=0;i<buf.length;i++){ var v=(buf[i]-128)/128; s+=v*v; }
    var rms=Math.sqrt(s/buf.length), lvl=Math.min(1,rms*6.0);
    st.lv += (lvl-st.lv)*0.25;
    var want = Math.min(1, lvl*1.15);
    st.jaw += (want-st.jaw)*(want>st.jaw?0.55:0.32);
    requestAnimationFrame(drive);
  }
  go.addEventListener('click',function(){
    if(playing){ au.pause(); return; }
    if(!ctx){ ctx=new(window.AudioContext||window.webkitAudioContext)();
      var src=ctx.createMediaElementSource(au); ana=ctx.createAnalyser(); ana.fftSize=1024;
      buf=new Uint8Array(ana.fftSize); src.connect(ana); ana.connect(ctx.destination); }
    ctx.resume(); au.currentTime=0; au.play();
  });
  au.addEventListener('play',function(){playing=true;go.textContent='❚❚ 暫停';drive();});
  au.addEventListener('ended',function(){playing=false;st.lv=0;st.jaw=0;go.textContent='▶ 讓她說話';});
  au.addEventListener('pause',function(){playing=false;st.lv=0;st.jaw=0;go.textContent='▶ 讓她說話';});
})();
</script></body></html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--voice", default="", help="默认沿用 outputs/dh-live/live-tw-01/voice.mp3")
    ap.add_argument("--publish", action="store_true", help="拆完直接上云（公网 sha 回读）")
    a = ap.parse_args()

    alb = SRC_DIR / "albedo.png"
    if not alb.is_file():
        print(json.dumps({"ok": False, "why": "no_albedo", "path": str(alb)}, ensure_ascii=False))
        return 2
    img = Image.open(alb).convert("RGBA")
    W, H = img.size
    meta = json.loads((SRC_DIR / "meta.json").read_text(encoding="utf-8"))
    A = meta["anchors"]
    mouth = A["mouth"]
    mhw, mhh = A.get("mouth_half_w", 27), A.get("mouth_half_h", 9)

    geo = {}
    for name, box in BOXES.items():
        x0, y0, x1, y1 = box
        px, py = PIVOTS[name]
        geo[name] = {
            "box": box, "w_pct": (x1 - x0) / W * 100, "h_pct": (y1 - y0) / H * 100,
            "x_pct": x0 / W * 100, "y_pct": y0 / H * 100,
            "pivot_pct_in_box": [(px - x0) / (x1 - x0) * 100, (py - y0) / (y1 - y0) * 100],
        }
    rep = {"ok": True, "src": str(alb), "image": [W, H], "geo": geo,
           "mouth": mouth, "mouth_half": [mhw, mhh]}
    if a.check:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / "base.png")
    for name, box in BOXES.items():
        cut(img, box, name).save(OUT / f"{name}.png")
    shutil.copyfile(SRC_DIR / "cavity.png", OUT / "cavity.png")
    voice = Path(a.voice) if a.voice else (ROOT / "outputs" / "dh-live" / "live-tw-01" / "voice.mp3")
    if voice.is_file():
        shutil.copyfile(voice, OUT / "voice.mp3")
        rep["voice"] = str(voice)
    rep["voice_ok"] = (OUT / "voice.mp3").is_file()

    th, hd = geo["torso"], geo["head"]
    # head 的 left/top 相对 torso 的框
    hx_rel = (hd["box"][0] - th["box"][0]) / (th["box"][2] - th["box"][0]) * 100
    hy_rel = (hd["box"][1] - th["box"][1]) / (th["box"][3] - th["box"][1]) * 100
    hw_rel = hd["w_pct"] / th["w_pct"] * 100
    hh_rel = hd["h_pct"] / th["h_pct"] * 100
    # 嘴：相对 head 框
    hbx0, hby0 = hd["box"][0], hd["box"][1]
    mx = (mouth[0] - mhw - hbx0) / (hd["box"][2] - hd["box"][0]) * 100
    my = (mouth[1] - hby0) / (hd["box"][3] - hd["box"][1]) * 100 - (2 * mhh) / (hd["box"][3] - hd["box"][1]) * 100 / 2
    mw = (2 * mhw) / (hd["box"][2] - hd["box"][0]) * 100
    mh = (2 * mhh) / (hd["box"][3] - hd["box"][1]) * 100

    html = PAGE % dict(title="小土豆 · 纸片人（拆件转动）", w=W, h=H,
                       tx=th["x_pct"], ty=th["y_pct"], tw=th["w_pct"], th=th["h_pct"],
                       tpx=th["pivot_pct_in_box"][0], tpy=th["pivot_pct_in_box"][1],
                       hx=hx_rel, hy=hy_rel, hw=hw_rel, hh=hh_rel,
                       hpx=hd["pivot_pct_in_box"][0], hpy=hd["pivot_pct_in_box"][1],
                       mx=mx, my=my, mw=mw, mh=mh)
    (OUT / "index.html").write_text(html, encoding="utf-8")
    rep["dir"] = str(OUT)
    rep["files"] = {p.name: p.stat().st_size for p in sorted(OUT.iterdir()) if p.is_file()}
    if a.publish:
        rep["publish"] = publish()
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
