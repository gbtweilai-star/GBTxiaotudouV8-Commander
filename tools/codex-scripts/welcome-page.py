# -*- coding: utf-8 -*-
"""启动欢迎页生成器（welcome-page）—— 文字**从单一真源来**，不手抄。

主人令（2026-10-10）：「启动APP数字人的欢迎语，你来看看说什么，要有 GBT小土豆V8 和
  开发者：自由的风，其他你来想要有未来感的语言」

单一真源：gbt_allinone/welcome.py 的 WELCOME（必含项由 welcome.check() 机械咬住）。
本件只**渲染**，不改文字 —— 要改欢迎语改 welcome.py，再重跑本件。

音频：读 holo_pet_w3/digital-human/welcome-*.wav（预生成的缓存）；**没造就只显示文字**，
并**如实标出来**（不许静默、不许假装播了）。

用法：py -3.14 -X utf8 tools/codex-scripts/welcome-page.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
PAGE = ROOT / "holo_pet_w3" / "welcome" / "index.html"
SIG = "开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"

TPL = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<!-- 自动生成，别手改。重建：py -3.14 tools/codex-scripts/welcome-page.py -->
<title>GBT小土豆V8 · 启动</title>
<style>
 html,body{height:100%;margin:0}
 body{background:radial-gradient(1200px 700px at 50% 30%,#0d1a2b 0%,#06080c 60%,#04060a 100%);
      color:#e8eef6;font:16px/1.9 "Segoe UI","Microsoft YaHei",system-ui,sans-serif;
      display:flex;align-items:center;justify-content:center;overflow:hidden}
 .halo{position:fixed;inset:-20%;background:conic-gradient(from 0deg,#22d3ee22,#f5b04122,#22d3ee22);
       filter:blur(90px);animation:spin 26s linear infinite}
 @keyframes spin{to{transform:rotate(360deg)}}
 .card{position:relative;max-width:820px;padding:44px 52px;border:1px solid #1d2a3a;border-radius:18px;
   background:rgba(8,12,20,.72);box-shadow:0 30px 90px #000a}
 .brand{font-size:13px;letter-spacing:.34em;color:#5f7286;text-transform:uppercase;margin-bottom:22px}
 p{margin:9px 0;font-size:23px;letter-spacing:.5px}
 p.lead{font-size:31px;color:#7fe3f0;letter-spacing:.16em;margin-bottom:20px}
 p.sig{color:#f5b041;font-weight:600;margin-top:22px}
 .hint{margin-top:24px;padding-top:16px;border-top:1px solid #17222f;color:#7d8ea3;font-size:13px}
 .hint.warn{color:#f5b041} code{color:#9fb6cf;font-size:12px;word-break:break-all}
 .foot{margin-top:14px;color:#48586a;font-size:12px}
</style></head><body>
<div class="halo"></div>
<div class="card">
 <div class="brand">GBT · V8 · Commander Framework</div>
 __LINES__
 __AUDIO__
 <div class="foot">__SIG__｜必含项：__REQ__ · 判据 __VERDICT__</div>
</div>
<script>
 var va = document.getElementById("va"), ah = document.getElementById("ah");
 function go() {
   if (!va) { return; }
   va.play().then(function () { ah.textContent = "正在播欢迎语…"; })
            .catch(function (e) { ah.textContent = "音频在盘但没播出去（" + e.name + "）—— 如实报，不假装"; });
   document.removeEventListener("click", go);
 }
 document.addEventListener("click", go);
</script>
</body></html>
"""


def main() -> int:
    from gbt_allinone.welcome import WELCOME, check, REQUIRED

    c = check()
    d = ROOT / "holo_pet_w3" / "digital-human"
    wavs = sorted(d.glob("welcome-*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
    audio = wavs[0].name if wavs else ""
    lines = "".join(
        '<p class="%s">%s</p>' % ("lead" if i == 0 else ("sig" if "自由的风" in t else ""), t)
        for i, t in enumerate(x for x in WELCOME.splitlines() if x.strip()))
    if audio:
        audio_block = ('<audio id="va" src="../digital-human/%s" preload="auto"></audio>'
                       '<div class="hint" id="ah">音频已就绪 —— 点任意处开始</div>' % audio)
    else:
        audio_block = ('<div class="hint warn" id="ah">欢迎语音频<b>还没造</b>（CPU 造声约 150 倍慢于实时，'
                       '须预生成一次）：<br><code>py -3.14 -X utf8 tools/codex-scripts/voicestudio.py speak '
                       '--text &lt;WELCOME_SHORT&gt; --instruct &quot;female, young adult, moderate pitch, '
                       'chinese accent&quot; --language zh</code></div>')
    html = (TPL.replace("__LINES__", lines).replace("__AUDIO__", audio_block)
               .replace("__SIG__", SIG).replace("__REQ__", " 与 ".join(REQUIRED))
               .replace("__VERDICT__", "PASS" if c["ok"] else "FAIL"))
    PAGE.parent.mkdir(parents=True, exist_ok=True)
    PAGE.write_text(html, encoding="utf-8")
    print("已渲启动页：%s（音频：%s）" % (PAGE.relative_to(ROOT), audio or "**未造**"))
    return 0 if c["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
