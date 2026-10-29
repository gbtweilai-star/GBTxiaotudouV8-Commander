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
sys.path.insert(0, str(Path(__file__).resolve().parent))
# 页面落盘的唯一出口（清洗漏到界面上的 markdown 记号后再写盘）。
# 为什么在生成器出口清、而不是事后洗产物：洗产物下次重生成又漂回来（判据 ③ 的注释原话）。
from _page_emit import clean_html  # noqa: E402
PAGE = ROOT / "holo_pet_w3" / "welcome" / "index.html"
SIG = "开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"

TPL = """<!doctype html>
<html data-page-id="welcome" lang="zh-CN"><head><meta charset="utf-8">
<!-- 自动生成，别手改。重建：py -3.14 tools/codex-scripts/welcome-page.py -->
<title>GBT小土豆V8 · 启动</title>
<!-- 2026-10-26：吃 library 令牌（单一源 state/taste/*.json → theme/taste-tokens.css）。
     口径：**方法用它、内容用我们的** —— 见 holo_pet_w3/theme/gbt-direction.json。
     兜底规则（2026-10-26 主人当场纠正）：**语义色（positive/negative/warning/unknown/accent）
     的兜底一律写令牌真值**，不许写"改之前那个颜色" —— 否则令牌表在不在会是两种颜色，
     等于给同一个状态配两种色，撞方向文件 avoid。中性色（ground/text/border…）兜底可用原值。 -->
<link rel="stylesheet" href="../theme/taste-tokens.css" />
<style>
 /* 模板必须**自带** data-page-id 与接管器：它们是触手网格的入场券。
    以前这两样是生成后用工具补的 —— 一重生成就没了（本仓踩过多次）。
    凡是"生成后补"的东西，要么进模板，要么就得每次记得跑收尾工具，后者靠人会漏。 */
 html,body{height:100%;margin:0}
 body{background:var(--taste-ground,#0B1120);color:var(--taste-text,#e8ecf8);
      font:16px/1.9 "Segoe UI","Microsoft YaHei",system-ui,sans-serif;
      display:flex;align-items:center;justify-content:center;overflow:hidden}
 /* 2026-10-26：底光原是 radial-gradient(...) —— 拿渐变当层次，与方向文件 avoid 冲突，改纯色。
    同日二次改：`.halo` 原是 conic-gradient 三色轮转（仍属渐变态，只能靠"登记例外"过闸）。
    现改成**两团纯色柔光**：底色一层青 + 两个圆形 blur 光斑（金 / 青）。
    效果等价（都是大面积柔光），但 CSS 里**没有 gradient** ⇒ 例外表里这一条可以撤掉。
    为什么用 blur 而不是 box-shadow：`shadow` 是另一条 FAIL 条款，用 blur 才两边都不撞。 */
 .halo{position:fixed;inset:-20%;
       background:color-mix(in srgb,var(--taste-positive,#00E5FF) 13%,transparent);
       filter:blur(90px)}
 .halo::before,.halo::after{content:"";position:absolute;border-radius:50%}
 .halo::before{left:16%;top:20%;width:46%;height:46%;
       background:color-mix(in srgb,var(--taste-accent,#f5b041) 12%,transparent);
       filter:blur(60px)}
 .halo::after{right:12%;bottom:14%;width:40%;height:40%;
       background:color-mix(in srgb,var(--taste-positive,#00E5FF) 10%,transparent);
       filter:blur(70px)}
 .card{position:relative;max-width:820px;padding:44px 52px;border:1px solid var(--taste-border,#1E3A5F);
   border-radius:18px;background:color-mix(in srgb,var(--taste-surface,#111827) 72%,transparent);
   box-shadow:0 30px 90px #000a}
 .brand{font-size:13px;letter-spacing:.34em;color:var(--taste-muted,#9aa4c4);text-transform:uppercase;margin-bottom:22px}
 p{margin:9px 0;font-size:23px;letter-spacing:.5px}
 p.lead{font-size:31px;color:var(--taste-positive,#00E5FF);letter-spacing:.16em;margin-bottom:20px}
 p.sig{color:var(--taste-accent,#f5b041);font-weight:600;margin-top:22px}
 .hint{margin-top:24px;padding-top:16px;border-top:1px solid var(--taste-border,#1E3A5F);
       color:var(--taste-muted,#9aa4c4);font-size:13px}
 .hint.warn{color:var(--taste-accent,#f5b041)} code{color:var(--taste-muted,#9aa4c4);font-size:12px;word-break:break-all}
 .foot{margin-top:14px;color:var(--taste-faint,#6b7280);font-size:12px}
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
<script src="../shell/tentacle-kit.js" defer></script>
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
    PAGE.write_text(clean_html(html), encoding="utf-8")
    print("已渲启动页：%s（音频：%s）" % (PAGE.relative_to(ROOT), audio or "**未造**"))
    return 0 if c["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
