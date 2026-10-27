#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lens —— 手机投墙的**唯一物理成立方案**：屏幕 + 凸透镜（不是闪光灯）。

原理：屏幕当光源与图像源，凸透镜成实像。
      1/f = 1/u + 1/v      u=屏幕到透镜，v=透镜到墙
      放大倍率 m = v/u      像大小 = 屏幕大小 × m

为什么必须反色+镜像：透镜成的是**倒立左右反转**的实像，所以要在屏幕端先反一次，
投到墙上才是正的。

用法：
    python3 tools/lens.py                 # 生成透镜模式页面 + 打印算距表
    python3 tools/lens.py --f 15 --dist 2 # 按你的透镜焦距/投距算尺寸
"""
import argparse, os, subprocess

OUT = "/var/minis/attachments/lens.html"

HTML = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>透镜投影模式</title>
<style>
 :root{--inv:1;--mir:-1;--bri:1.35}
 *{margin:0;padding:0;box-sizing:border-box}
 html,body{height:100%;background:#fff;overflow:hidden}
 #stage{position:fixed;inset:0;background:#000;color:#fff;display:flex;align-items:center;justify-content:center;
        filter:invert(var(--inv)) brightness(var(--bri));transform:scaleX(var(--mir))}
 .page{width:100%;height:100%;display:none;padding:6vh 6vw;flex-direction:column;justify-content:center}
 .page.on{display:flex}
 /* 亮度策略（反色后屏幕几乎全白）：黑字越少越亮 ⇒ 大字号、少行数、纯二值 */
 h1{font-size:11vh;line-height:1.08;letter-spacing:-.03em;font-weight:800}
 p{font-size:5vh;line-height:1.45;margin-top:4vh;max-width:26ch}
 .page{justify-content:center;align-items:flex-start}
 .grid{position:absolute;inset:0;background-image:
        repeating-linear-gradient(0deg,#fff 0 2px,transparent 2px 10vh),
        repeating-linear-gradient(90deg,#fff 0 2px,transparent 2px 10vw)}
 .bar{position:fixed;left:0;right:0;bottom:0;height:6vh;display:flex;gap:6px;
      align-items:center;justify-content:center;background:#111;color:#eee;font-size:2.6vh;
      transform:translateY(100%);transition:transform .2s}
 body.ui .bar{transform:translateY(0)}
 button{font:inherit;padding:.6vh 1.6vh;border:0;border-radius:99px;background:#333;color:#eee}
</style></head><body>
<div id="stage">
  <section class="page on"><h1>把手机<br>放进透镜后面</h1>
    <p>屏幕朝透镜，反色与镜像已开。<br>关灯，等眼睛适应 30 秒。</p></section>
  <section class="page">
    <div class="grid"></div>
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" style="position:absolute;inset:0">
      <circle cx="50" cy="50" r="18" fill="none" stroke="#fff" stroke-width=".5"/>
      <circle cx="50" cy="50" r="32" fill="none" stroke="#fff" stroke-width=".5"/>
      <circle cx="50" cy="50" r="45" fill="none" stroke="#fff" stroke-width=".5"/>
      <line x1="50" y1="2" x2="50" y2="98" stroke="#fff" stroke-width=".4"/>
      <line x1="2" y1="50" x2="98" y2="50" stroke="#fff" stroke-width=".4"/>
      <rect x="6" y="6" width="88" height="88" fill="none" stroke="#fff" stroke-width=".6"/>
      <text x="50" y="53" text-anchor="middle" font-size="3" fill="#fff">对焦到这里最细</text>
    </svg>
  </section>
  <section class="page" id="vpage"><video id="v" src="__VIDEO__" playsinline muted loop
     style="width:100%;height:100%;object-fit:contain;display:none"></video>
    <h1 id="vhint">没放片子<br><span style="font-size:4vh">用 --video 指定一个 mp4</span></h1></section>
  <section class="page" style="background:#000"></section>
  <section class="page"><h1>GBT小土豆V8</h1>
    <p>开发者：自由的风<br>守护者：公主土豆</p></section>
</div>
<div class="bar">
  <button onclick="toggle()">反色/正色</button>
  <button onclick="mir()">镜像</button>
  <button onclick="next()">下一页</button>
  <button onclick="bri()">亮度</button>
</div>
<script>
let inv=1,mir=-1,bri=1.35,pg=0;
const st=document.getElementById('stage'),pages=[...document.querySelectorAll('.page')];
function apply(){st.style.setProperty('--inv',inv);st.style.setProperty('--mir',mir);
  st.style.setProperty('--bri',bri);}
function toggle(){inv=inv?0:1;apply()}
function mir(){mir=mir<0?1:-1;apply()}
function bri(){bri=bri>=1.8?1.0:+(bri+0.15).toFixed(2);apply()}
function next(){pages[pg].classList.remove('on');pg=(pg+1)%pages.length;pages[pg].classList.add('on')}
document.addEventListener('click',e=>{if(e.target.tagName!=='BUTTON')next()});
let t=null;addEventListener('touchstart',()=>{t=setTimeout(()=>document.body.classList.add('ui'),600)});
addEventListener('touchend',()=>clearTimeout(t));
// 有片子就把提示藏起来、让视频播
const v=document.getElementById('v');
if(v && v.getAttribute('src') && !v.getAttribute('src').includes('__VIDEO__')){
  v.style.display='block'; document.getElementById('vhint').style.display='none';
  v.play().catch(()=>{});
}
apply();
</script></body></html>"""


def calc(f_cm, dist_m, screen=(6.5, 14.0)):
    """返回 (屏幕到透镜距离 cm, 放大倍率, 像尺寸 cm)"""
    f, D = f_cm, dist_m * 100.0
    u = D * f / (D + f)          # 1/f = 1/u + 1/v, v≈D
    m = D / u
    return round(u, 1), round(m, 1), (round(screen[0] * m, 0), round(screen[1] * m, 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--f", type=float, default=0)
    ap.add_argument("--dist", type=float, default=0)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--video", help="把一段 mp4 作为一页投出去（照样反色+镜像）")
    a = ap.parse_args()

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    html = HTML
    if a.video:
        src = "minis://" + os.path.relpath(a.video, "/var/minis") if a.video.startswith("/var/minis") else a.video
        html = html.replace("__VIDEO__", src)
        print("片子：%s（第 3 页）" % src)
    open(a.out, "w", encoding="utf-8").write(html)
    print("透镜模式页：%s（全屏打开，反色+镜像默认开；点屏幕翻页，长按出控制条）" % a.out)

    if a.f and a.dist:
        u, m, size = calc(a.f, a.dist)
        print("\n透镜 f=%.0fcm · 投距 %.1fm" % (a.f, a.dist))
        print("  屏幕到透镜 %.1f cm · 放大 %.1f 倍 · 像 ≈ %.0f×%.0f cm" % (u, m, size[0], size[1]))
        print("  亮度提示：像面积越大越暗，投到 %.0fcm 宽时约剩 %.0f%% 亮度"
              % (size[0], max(2, 100 / (m ** 2 / 9))))
        return 0

    print("\n常用透镜算距表（手机屏幕按 6.5×14 cm 估）")
    print("  %-6s %-8s %-10s %-14s %s" % ("焦距", "投距", "屏到镜头", "墙上像尺寸", "相对亮度"))
    for f in (10, 15, 20):
        for d in (1.0, 2.0, 3.0):
            u, m, size = calc(f, d)
            print("  %-6s %-8s %-10s %-14s %s"
                  % ("%dcm" % f, "%.0fm" % d, "%.1fcm" % u,
                     "%.0f×%.0fcm" % size, "%.0f%%" % max(2, 100 / (m ** 2 / 9))))
    print("\n现实预期：全黑房间里能看清，白天基本无效；边缘会有色差与畸变。")
    print("亮度换算：屏幕满白 ≈ 手机亮度 ×(1-透过率损失)，靠'画面留白多'而不是'字多'。")
    print("硬件最小清单：凸透镜 f≈20cm（直径≥5cm，¥20-60）· 纸筒支架 · 全黑房间")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
