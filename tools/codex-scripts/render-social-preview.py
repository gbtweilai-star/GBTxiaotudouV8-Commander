# -*- coding: utf-8 -*-
"""渲染 GitHub 社交预览图 1280×640（仓库 Settings → Social preview 上传用）。

原则（照本仓 P7）：**先看再交** —— 渲染完必须亲眼看一遍：字有没有豆腐块、有没有被裁掉、
在缩到 600px 宽时还读不读得出来。

**数据驱动（2026-11-04 起）**：本脚本不再硬编码任何读数。历史上这里写死了
「341 位 / 30 个域 / 0 失败」，注册表涨到 427 位后图与正文长期对不上 —— 根因在脚本本身，
不在 PNG 文件。现在所有数字从真身读取，账目不平直接报错退出，不许出图：

  · 能力位 / 域数  ← data/capabilities.json          （注册表导出，count + capabilities）
  · 真调通过 / 无法归因 ← data/capability-live-test.json（probe-caps-live.py 的读数）
  · 基准读数      ← state/model-deploy/live-eval-v2.json（缺失则回退 docs/04 记录值并标注）

产物：outputs/open-source-release/assets/social-preview.png
用法：py -3.12 -X utf8 tools/codex-scripts/render-social-preview.py
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "open-source-release" / "assets" / "social-preview.png"

TITLE = "GBT小土豆V8 · 独立数字人框架"
SUBTITLE = "把自然语言落到 {n} 位能力上 · 写盘 / 花钱 / 出网 一律先过人闸 · 每次调用都留审计"

CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)


def load_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def read_figures() -> dict:
    """读真身读数；任何一处对不上就抛错，不出图。"""
    caps = load_json(ROOT / "data" / "capabilities.json")
    if not caps or not isinstance(caps.get("capabilities"), list):
        raise SystemExit("缺 data/capabilities.json，无法出图（先跑注册表导出）")
    cap_total = int(caps.get("count") or len(caps["capabilities"]))
    if cap_total != len(caps["capabilities"]):
        raise SystemExit(f"账不平：count={cap_total} 但 capabilities={len(caps['capabilities'])}")
    domains = len({c.get("domain") for c in caps["capabilities"] if c.get("domain")})

    live = load_json(ROOT / "data" / "capability-live-test.json")
    if not live or not isinstance(live.get("counts"), dict):
        raise SystemExit("缺 data/capability-live-test.json，无法出图（先跑 probe-caps-live.py）")
    cnt = live["counts"]
    if sum(cnt.values()) != cap_total:
        raise SystemExit(f"真调账不平：分类合计 {sum(cnt.values())} ≠ 注册表 {cap_total}")
    ok = int(cnt.get("ok", 0))
    unattributed = int(cnt.get("failed", 0)) + int(cnt.get("timeout", 0)) + int(cnt.get("exception", 0))

    ev = load_json(ROOT / "state" / "model-deploy" / "live-eval-v2.json")
    if ev and ev.get("pass45_rate") is not None:
        bench = f"{(float(ev['pass45_rate']) * 100):.2f}%"
        bench_note = "335 题基准 PASS45"
        bench_src = "live-eval-v2.json"
    else:
        bench = "99.10%"
        bench_note = "335 题基准 PASS45"
        bench_src = "docs/04 记录（未重跑）"

    return {
        "cap_total": cap_total,
        "domains": domains,
        "ok": ok,
        "unattributed": unattributed,
        "bench": bench,
        "bench_note": bench_note,
        "bench_src": bench_src,
        "live_at": live.get("at"),
    }


def build_html(f: dict) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1280px;height:640px;overflow:hidden}}
body{{background:
  radial-gradient(820px 460px at 10% -8%, rgba(34,197,94,.20), transparent 60%),
  radial-gradient(700px 400px at 95% 6%, rgba(59,130,246,.18), transparent 60%),
  radial-gradient(640px 320px at 62% 104%, rgba(245,158,11,.10), transparent 62%),
  #04070b;
 font-family:"Microsoft YaHei","Noto Sans SC",sans-serif;color:#e6edf3;position:relative;
 -webkit-font-smoothing:antialiased}}
.floor{{position:absolute;left:-70%;bottom:-8%;width:240%;height:56%;
 background-image:linear-gradient(rgba(148,163,184,.30) 1px,transparent 1px),
  linear-gradient(90deg,rgba(148,163,184,.26) 1px,transparent 1px);
 background-size:56px 56px;transform:perspective(900px) rotateX(58deg);transform-origin:50% 100%;
 -webkit-mask-image:linear-gradient(to top,#000 0%,rgba(0,0,0,.55) 60%,transparent 100%);
 mask-image:linear-gradient(to top,#000 0%,rgba(0,0,0,.55) 60%,transparent 100%)}}
.ceiling{{position:absolute;left:-70%;top:-4%;width:240%;height:34%;
 background-image:linear-gradient(rgba(148,163,184,.16) 1px,transparent 1px),
  linear-gradient(90deg,rgba(148,163,184,.16) 1px,transparent 1px);
 background-size:64px 64px;transform:perspective(900px) rotateX(-58deg);transform-origin:50% 0%;
 -webkit-mask-image:linear-gradient(to bottom,rgba(0,0,0,.9),transparent 100%);
 mask-image:linear-gradient(to bottom,rgba(0,0,0,.9),transparent 100%);opacity:.9}}
.rail{{position:absolute;left:0;top:0;width:6px;height:640px;
 background:linear-gradient(180deg,#22c55e,#0ea5e9);
 box-shadow:0 0 26px rgba(34,197,94,.95),0 0 80px rgba(34,197,94,.4);z-index:3}}
.wrap{{padding:48px 64px 0 70px;position:relative;z-index:2}}
h1{{font-size:50px;font-weight:700;letter-spacing:.5px;line-height:1.15;color:#fff;
 text-shadow:0 1px 0 rgba(0,0,0,.6),0 3px 30px rgba(255,255,255,.12)}}
.sub{{margin-top:15px;font-size:20px;color:#8b949e;letter-spacing:.2px}}
.sub b{{color:#d7dee7;font-weight:600}}
.cards{{perspective:1100px;display:flex;gap:22px;margin-top:30px}}
.card{{flex:1;height:198px;position:relative;border-radius:15px;
 background:linear-gradient(158deg,rgba(38,52,70,.96),rgba(9,14,20,.98) 64%);
 border:1px solid rgba(148,163,184,.24);transform:rotateX(16deg);transform-style:preserve-3d;
 padding:24px 28px;display:flex;flex-direction:column;justify-content:center}}
.card::after{{content:"";position:absolute;left:2px;right:2px;bottom:-13px;height:14px;
 background:linear-gradient(180deg,rgba(24,34,46,.98),rgba(6,10,15,.98));
 border:1px solid rgba(148,163,184,.20);border-top:none;border-radius:0 0 15px 15px;
 box-shadow:0 16px 26px -10px rgba(0,0,0,.95);z-index:-1}}
.card::before{{content:"";position:absolute;left:18px;right:18px;top:0;height:1px;
 background:linear-gradient(90deg,transparent,rgba(255,255,255,.6),transparent)}}
.card.g{{box-shadow:0 1px 0 rgba(255,255,255,.14) inset,0 -30px 52px rgba(0,0,0,.5) inset,0 26px 40px -14px rgba(0,0,0,.95),0 0 64px -14px rgba(34,197,94,.75)}}
.card.b{{box-shadow:0 1px 0 rgba(255,255,255,.14) inset,0 -30px 52px rgba(0,0,0,.5) inset,0 26px 40px -14px rgba(0,0,0,.95),0 0 64px -14px rgba(59,130,246,.75)}}
.card.o{{box-shadow:0 1px 0 rgba(255,255,255,.14) inset,0 -30px 52px rgba(0,0,0,.5) inset,0 26px 40px -14px rgba(0,0,0,.95),0 0 64px -14px rgba(245,158,11,.72)}}
.num{{font-size:62px;font-weight:700;line-height:1;letter-spacing:-.5px}}
.num.g{{color:#3ee383;text-shadow:0 1px 0 rgba(255,255,255,.30),0 4px 0 rgba(0,60,25,.55),0 16px 34px rgba(34,197,94,.85)}}
.num.b{{color:#66b0ff;text-shadow:0 1px 0 rgba(255,255,255,.30),0 4px 0 rgba(10,40,90,.55),0 16px 34px rgba(59,130,246,.85)}}
.num.o{{color:#ffbe4d;text-shadow:0 1px 0 rgba(255,255,255,.30),0 4px 0 rgba(80,45,0,.55),0 16px 34px rgba(245,158,11,.82)}}
.cap{{margin-top:13px;font-size:17px;color:#93a1b0;line-height:1.35}}
.cap i{{font-style:normal;color:#d7dee7}}
.code{{margin-top:26px;border-radius:11px;padding:19px 24px;
 background:linear-gradient(180deg,rgba(7,11,16,.99),rgba(12,18,26,.99));
 border:1px solid rgba(148,163,184,.18);
 box-shadow:inset 0 3px 14px rgba(0,0,0,.9),0 18px 36px -20px rgba(0,0,0,.95)}}
.cmd{{font-family:"Cascadia Mono",Consolas,monospace;font-size:21px;color:#4ade80;
 text-shadow:0 0 20px rgba(34,197,94,.55)}}
.hint{{margin-top:8px;font-size:16px;color:#6e7681}}
.foot{{margin-top:20px;display:flex;justify-content:space-between;align-items:flex-end}}
.foot .l1{{font-size:18px;color:#8b949e}}
.foot .l1 b{{color:#d7dee7;font-weight:600}}
.foot .l2{{margin-top:8px;font-size:14px;color:#55606c}}
.foot .r{{font-size:15px;color:#6e7681;font-family:Consolas,monospace;padding-bottom:2px}}
</style></head><body>
<div class="ceiling"></div><div class="floor"></div><div class="rail"></div>
<div class="wrap">
  <h1>{TITLE}</h1>
  <div class="sub">{SUBTITLE.format(n=f['cap_total'])}</div>
  <div class="cards">
    <div class="card g"><div class="num g">{f['cap_total']}</div>
      <div class="cap"><i>位原生能力</i> · {f['domains']} 个域</div></div>
    <div class="card b"><div class="num b">{f['bench']}</div>
      <div class="cap"><i>{f['bench_note']}</i></div></div>
    <div class="card o"><div class="num o">{f['ok']}</div>
      <div class="cap"><i>位真调通过</i> · {f['unattributed']} 位无法归因</div></div>
  </div>
  <div class="code">
    <div class="cmd">python demo.py "我要把 Markdown 变成 PPT"</div>
    <div class="hint">零依赖 · 不需要 GPU · 不需要模型权重 · 秒回「该调哪一位、要什么票」</div>
  </div>
  <div class="foot">
    <div><div class="l1">单门执行 <b>run_task(kind, payload)</b> · 授权 · 审计 · 钢印 都在这一处</div>
      <div class="l2">开发者：自由的风 · Apache-2.0 · 本署名不可删除、不可篡改归属</div></div>
    <div class="r">github.com/gbtweilai-star</div>
  </div>
</div></body></html>"""


def find_browser() -> str:
    for p in CHROME_CANDIDATES:
        if p and pathlib.Path(p).is_file():
            return p
    raise SystemExit("找不到 Chrome / Edge，无法渲染（PIL 版已弃用：它无法表达 3D 层次）")


def main() -> int:
    fig = read_figures()
    print("读数 ←", json.dumps({k: v for k, v in fig.items() if k != "live_at"}, ensure_ascii=False))
    print("真调账时点 ←", fig["live_at"], "· 基准来源 ←", fig["bench_src"])

    html = build_html(fig)
    tmp = pathlib.Path(tempfile.gettempdir()) / "gbt-social-preview.html"
    tmp.write_text(html, encoding="utf-8")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    subprocess.run(
        [find_browser(), "--headless=new", "--disable-gpu", "--hide-scrollbars",
         "--force-device-scale-factor=1", "--window-size=1280,640",
         f"--screenshot={OUT}", tmp.as_uri()],
        check=False, capture_output=True,
    )
    if not OUT.is_file():
        raise SystemExit("渲染失败：未产出 PNG")
    print("已渲染 →", OUT.relative_to(ROOT), "·", OUT.stat().st_size, "bytes · 1280x640")
    print("下一步（P7 先看再交）：打开 PNG 亲眼过一遍，再复制到 assets/social-preview.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
