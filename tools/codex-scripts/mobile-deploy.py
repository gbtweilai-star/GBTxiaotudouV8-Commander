# -*- coding: utf-8 -*-
"""mobile-deploy -- 手机部署：打包 + 局域网地址 + 校验。"""
from __future__ import annotations
import argparse, json, shutil, socket, sys
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "state" / "mobile-pack"
PROF = ROOT / "state" / "deploy-profiles.json"
# 🔴 2026-10-17 修（**手机版丢页** · 留痕 · 原口径 / 为什么翻 / 现口径）：
#   原口径：`["holo_pet_w3", "state/blueprints"]` ⇒ 手机包只有 **367 页**。
#   为什么翻（实测）：同一时刻电脑版/直达闸/设备注入用的是
#     `["holo_pet_w3", "state", "state/blueprints", "docs"]` ⇒ **757 页**；
#     差额 **390 页正是 `state/*.html`**（生成的面板/看板）——「手机电脑版本都要在，别丢了」
#     ⇒ 手机包漏掉这 390 页 = 手机上打不开它们。
#   现口径：**与 page-reach / device-deploy 同一份页目录清单**（单一真相），
#     并在 `pack()` 里按**去重后的解析路径**计数（`state` 已含 `state/blueprints`，
#     重复列举不会再重复拷）。
PAGE_DIRS = ["holo_pet_w3", "state", "state/blueprints", "docs"]
# 🔴 2026-10-17 事故剪枝（与 page-reach/device-deploy 同源 · 自反爆炸）：
#   手机包输出就在 `state/mobile-pack`，而 `state` 是页目录 ⇒ 打包会把**包自己**再拷进去。
#   实测失控到 **24,150 文件 / 54.7GB / 4,768 层**。⇒ 打包必须跳过产物目录，并加页数上限。
SKIP_PARTS = {".git", "node_modules", ".pylibs", "vendor", "_upstream", ".scratch",
              "mobile-pack", ".mimosa", "__pycache__", ".wrangler"}
MAX_PAGES = 3000

# 🔴 2026-10-17 新增（主人令：「手机版的补上语音操控」）：
#   老版本手机包有语音操控（百分百验证过），新版打包丢了 ⇒ 这里给**每个手机页**注入
#   一条自包含语音条：Web Speech 识别（iOS Safari 用 webkitSpeechRecognition / 安卓 Chrome 用
#   SpeechRecognition）+ 语音合成反馈 + **命令路由**（打开任意页 / 下一页 / 上一页 / 首页 / 返回 /
#   朗读当前页 / 停止 / 找字），并带**打字命令兜底**（浏览器不支持语音时也能用）。
#   纯本地、无外链、file:// 直开可用；不依赖任何服务器。
VOICE_MARK = "<!-- gbt-mobile-voice -->"
VOICE_JS = r"""
(function(){
  if (window.__gbtVoice) return; window.__gbtVoice = 1;
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  var CSS = "#gbt-voice-bar{position:fixed;left:8px;right:8px;bottom:10px;z-index:99999;display:flex;gap:8px;align-items:center;background:rgba(8,12,20,.92);border:1px solid rgba(0,229,255,.35);border-radius:14px;padding:8px 10px;font:14px/1.5 system-ui;color:#e8ecf1;box-shadow:0 6px 24px rgba(0,0,0,.5)}"+
    "#gbt-voice-bar button{background:linear-gradient(135deg,#F5B041,#00E5FF);color:#081018;border:0;border-radius:10px;padding:8px 12px;font:600 14px system-ui;min-height:44px;touch-action:manipulation}"+
    "#gbt-voice-bar button:active{transform:scale(.97)}#gbt-vstatus{flex:1;color:#9fb3c8;font-size:13px;min-height:20px}"+
    "#gbt-vtext{width:38%;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.14);border-radius:10px;color:#e8ecf1;padding:8px;font:14px system-ui;min-height:44px}"+
    "#gbt-vhit{outline:2px solid #F5B041;outline-offset:2px}";
  var st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st);
  var bar = document.createElement("div"); bar.id = "gbt-voice-bar";
  bar.innerHTML = '<button id="gbt-mic" type="button">语音</button><span id="gbt-vstatus">点「语音」说命令；也可直接打字：打开xxx / 下一页 / 朗读 / 停止</span><input id="gbt-vtext" placeholder="打字命令…" autocomplete="off">';
  document.addEventListener("DOMContentLoaded", function(){ document.body.appendChild(bar); });
  if (document.body && !document.getElementById("gbt-voice-bar")) document.body.appendChild(bar);
  var mic=document.getElementById("gbt-mic"), stt=document.getElementById("gbt-vstatus"), tx=document.getElementById("gbt-vtext");
  function say(t){ try{ if(!window.speechSynthesis) return; window.speechSynthesis.cancel(); var u=new SpeechSynthesisUtterance(String(t).slice(0,220)); u.lang="zh-CN"; u.rate=1.05; window.speechSynthesis.speak(u);}catch(e){} }
  function setS(t){ stt.textContent = t; }
  function links(){ var a=[].slice.call(document.querySelectorAll("#gbt-direct-nav a,#gbt-project-nav a,a[href$='.html']")); return a; }
  function nameOf(a){ return ((a.textContent||"")+" "+(a.getAttribute("href")||"")).toString(); }
  function openByName(q){ q=(q||"").trim(); if(!q) return false; var ls=links(); var i;
    for(i=0;i<ls.length;i++){ if(nameOf(ls[i]).toLowerCase().indexOf(q.toLowerCase())>=0){ ls[i].click(); setS("已打开："+q); say("好的，打开"+q); return true; } }
    var hit=document.body.innerText.indexOf(q); if(hit>=0){ var r=document.createRange(); var w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT); var n2; while((n2=w.nextNode())){ var t=n2.nodeValue||""; var k=t.indexOf(q); if(k>=0){ n2.parentElement.id="gbt-vhit"; n2.parentElement.scrollIntoView({block:"center"}); setS("已跳到："+q); say("找到了"); return true; } } }
    return false; }
  function readPage(){ var t=(document.title||"")+"。"+([].slice.call(document.querySelectorAll("h1,h2,p"),0,8).map(function(e){return e.innerText||"";}).join("。")||"");
    t=t.replace(/\s+/g," ").slice(0,400); say(t||"这一页没有可读的文字"); setS("正在朗读…"); }
  function exec(cmd){ var c=(cmd||"").trim(); if(!c) return; setS("收到："+c);
    if(/^停|停止|闭嘴|安静/.test(c)){ try{ window.speechSynthesis && window.speechSynthesis.cancel(); }catch(e){}; try{ SR && window.__gbtSR && window.__gbtSR.stop(); }catch(e){}; setS("已停止"); return; }
    if(/朗读|念一下|读给我|读一下/.test(c)){ readPage(); return; }
    if(/首页|回首页|回家/.test(c)){ var h=document.querySelector("#gbt-direct-nav a") || null; location.href=(new URL("index.html", location.href)).href; say("回首页"); return; }
    if(/下一页/.test(c)){ var ls=links(); for(var i=0;i<ls.length;i++){ if(ls[i].href===location.href && ls[i+1]){ ls[i+1].click(); say("下一页"); return; } } setS("后面没有页了"); return; }
    if(/上一页/.test(c)){ var ls2=links(); for(var j=0;j<ls2.length;j++){ if(ls2[j].href===location.href && j>0){ ls2[j-1].click(); say("上一页"); return; } } setS("前面没有页了"); return; }
    if(/返回|后退|回去/.test(c)){ history.back(); return; }
    var m=c.match(/^(?:打开|去|跳到|进入|看看|看)\s*(.+)$/);
    if(m){ if(openByName(m[1])) return; }
    if(/^找|搜索|查找/.test(c)){ var q=c.replace(/^(找|搜索|查找)\s*/,""); if(openByName(q)) return; setS("没找到："+q); return; }
    if(openByName(c)) return;
    setS("没听明白："+c+"（试：打开xxx / 下一页 / 朗读 / 停止）"); say("没听明白"); }
  function listen(){ if(!SR){ setS("此浏览器不支持语音识别 → 请用下面输入框打字命令（Safari 需 iOS14.5+，安卓 Chrome 可用）"); return; }
    try{ var r=new SR(); window.__gbtSR=r; r.lang="zh-CN"; r.interimResults=false; r.continuous=false; r.maxAlternatives=1;
      r.onstart=function(){ mic.textContent="听中…"; setS("正在听，请说命令…"); };
      r.onerror=function(e){ mic.textContent="语音"; setS("语音出错："+(e.error||"未知")+"（可用打字命令）"); };
      r.onend=function(){ mic.textContent="语音"; };
      r.onresult=function(e){ var t=e.results[0][0].transcript||""; mic.textContent="语音"; setS("你说："+t); exec(t); };
      r.start(); say("我在听"); }catch(e){ setS("启动语音失败："+e); } }
  mic.addEventListener("click", listen);
  tx.addEventListener("keydown", function(e){ if(e.key==="Enter"){ exec(tx.value); tx.value=""; } });
})();
"""


def _inject_voice(p: Path) -> bool:
    """给一个手机页注入语音条（已注入则跳过）。返回是否新注入。"""
    try:
        t = p.read_text(encoding="utf-8", errors="replace")
    except Exception:                                            # noqa: BLE001
        return False
    if VOICE_MARK in t:
        return False
    block = VOICE_MARK + "\n<script>" + VOICE_JS + "</script>"
    if "</body>" in t:
        t = t.replace("</body>", block + "\n</body>", 1)
    else:
        t = t + block
    p.write_text(t, encoding="utf-8")
    return True


def _skip(p):
    return any(part in SKIP_PARTS for part in p.parts)


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def pack(profile):
    prof = json.loads(PROF.read_text(encoding="utf-8"))
    p = prof["profiles"].get(profile) or prof["profiles"][prof["default"]]
    if PACK.is_dir() and not (PACK / profile).is_dir():
        pass
    # 🔴 2026-10-17 修（**苹果安卓都要 · 两包并存** · 留痕 · 原口径 / 为什么翻 / 现口径）：
    #   原口径：两档共用 `state/mobile-pack`，每次 `shutil.rmtree(PACK)` ⇒ 打安卓会**删掉苹果包**。
    #   为什么翻：主人令「手机是苹果安卓都有的哈」⇒ 必须**两档同时存在**，不能互相覆盖。
    #   现口径：每档一个子目录 `state/mobile-pack/<profile>/`，只清自己的子目录。
    out = PACK / profile
    if out.is_dir():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    seen = set()
    for d in PAGE_DIRS:
        b = ROOT / d
        if not b.is_dir():
            continue
        for f in b.rglob("*.html"):
            if _skip(f):                                # 产物目录（含 mobile-pack 自己）一律不拷
                continue
            key = str(f.resolve()).lower()          # 去重：state 已含 state/blueprints
            if key in seen:
                continue
            seen.add(key)
            if n >= MAX_PAGES:                          # fail-closed：失控就停
                raise SystemExit("手机包页数 > 上限 %d ⇒ 疑似产物自反，拒绝打包" % MAX_PAGES)
            tgt = out / d / f.relative_to(b)
            tgt.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, tgt)
            _inject_voice(tgt)                       # 2026-10-17：手机页补语音操控条（注入失败不挡打包，后续 --check 会咬）
            n += 1
            # 🔴 2026-10-17 修（**数据页上手机变成瞎页** · 留痕 · 原口径 / 为什么翻 / 现口径）：
            #   原口径：只打 *.html ⇒ db-fleet / tentacles 这类数据页的伴生
            #     *-data.js 不在包里，手机打开只剩"读不到 xxx-data.js"兜底句；
            #     连首页壳的 window.js / ef_render.js 也没打（壳功能全瘫）。
            #   现口径：每个 html 把它**同目录**的 *.js 伴生文件一起打
            #     （数据 js + 壳脚本都因此齐活；不递归、不碰 node_modules）。
            for js in f.parent.glob("*.js"):
                if _skip(js):
                    continue
                jtgt = tgt.parent / js.name
                if not jtgt.exists():
                    shutil.copy2(js, jtgt)
    for extra in (ROOT / "holo_pet_w3" / "manifest.webmanifest", ROOT / "state" / "direct-index.json"):
        if extra.is_file():
            shutil.copy2(extra, out / extra.name)
    entry = out / "index.html"
    links = sorted(str(x.relative_to(out)).replace("\\", "/") for x in out.rglob("*.html") if x != entry)
    entry.write_text("<!doctype html><meta charset=\"utf-8\">" +
                     '<meta name="viewport" content="' + prof["profiles"][profile]["viewport"] + '">' +
                     '<meta name="apple-mobile-web-app-capable" content="yes">' +
                     '<meta name="theme-color" content="' + prof["profiles"][profile]["pwa"]["theme_color"] + '">' +
                     "<title>手机入口 · 小土豆V8</title>" +
                     "<body style=\"background:#0b0d10;color:#e8ecf1;font:16px/1.8 system-ui;padding:18px\">" +
                     "<h1>手机入口（" + profile + "）</h1><p>点任一页进入；每页顶部有直达条，任意页可一跳到任意页。</p><ul>" +
                     "".join('<li><a style="color:#8ab4ff" href="%s">%s</a></li>' % (x, x) for x in links[:400]) +
                     "</ul><p style=\"color:#7d8794;font-size:13px\">开发者：自由的风 · 守护者：公主土豆</p></body>",
                     encoding="utf-8")
    ip = lan_ip()
    _inject_voice(entry)                             # 入口页同样带语音操控
    print("手机包已出：" + str(out.relative_to(ROOT)) + " · 档 " + profile + " · 页 %d 张 · 入口 index.html（含语音操控）" % n)
    print("手机打开方式：① 把 " + str(out.relative_to(ROOT)) + " 整个目录拷到手机，点 index.html；")
    print("              ② 或在本机起静态服务器，手机浏览器输：http://" + ip + ":8080/" + profile + "/index.html")
    return 0


def check() -> int:
    """判据：每档手机包**每一页**都要有语音操控（标记 + 识别/合成 API），缺一页就非零。"""
    bad = 0
    total = 0
    if not PACK.is_dir():
        print("RED 手机包目录不在：" + str(PACK.relative_to(ROOT)))
        return 1
    for prof_dir in sorted(x for x in PACK.iterdir() if x.is_dir()):
        pages = sorted(prof_dir.rglob("*.html"))
        miss = []
        for p in pages:
            try:
                t = p.read_text(encoding="utf-8", errors="replace")
            except Exception:                                    # noqa: BLE001
                miss.append(str(p.relative_to(prof_dir)))
                continue
            ok = (VOICE_MARK in t) and ("webkitSpeechRecognition" in t) and ("speechSynthesis" in t) \
                and ("gbt-voice-bar" in t)
            if not ok:
                miss.append(str(p.relative_to(prof_dir)))
        total += len(pages)
        bad += len(miss)
        print("%s %-16s 页 %d · 语音齐 %d · 缺 %d%s"
              % ("✅" if not miss else "RED", prof_dir.name, len(pages), len(pages) - len(miss),
                 len(miss), ("（如 " + miss[0] + "）" if miss else "")))
    print("== 手机语音操控：页 %d · 缺 %d ==" % (total, bad))
    return 0 if bad == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", action="store_true")
    ap.add_argument("--check", action="store_true", help="校验每档每页是否都带语音操控")
    ap.add_argument("--profile", default="apple-iphone17")
    a = ap.parse_args()
    if a.check:
        return check()
    if a.pack:
        return pack(a.profile)
    print("参数：--pack [--profile apple-iphone17|android-mobile] | --check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
