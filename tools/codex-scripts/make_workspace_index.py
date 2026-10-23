# -*- coding: utf-8 -*-
"""生成工作区总入口页 index.html —— 一屏看全所有可视化面板，点开即用。

视觉方向：**任务控制台 / 精密仪器**，不走"AI 味"的捷径。
  anti-ai-slop 禁的恰恰是最好走的那条路：紫蓝双色渐变、霓虹光晕、装饰光斑。
  所以未来感靠三件套做，而不是堆渐变：
    ① 单色冷光（只有青色一相，不是"信任感"双色渐变）
    ② 极细工程网格 + 内暗角（撑住"精密"，不喧宾夺主）
    ③ 尺度对比（82px 大标题 vs 11px 等宽元数据）+ 技术图纸定位角
  形状系统三档写进 :root；无 emoji 当图标（宽式判据 + 白名单 `→`）；
  对比度走深底亮字；**不写任何没量到的数字**（读数全部现扫）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = ROOT / "index.html"
SIGN = "开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"

try:
    import regex as _regex
    EMOJI = _regex.compile(r"[\p{Extended_Pictographic}\p{Emoji_Presentation}"
                           r"\u2190-\u21FF\u2300-\u23FF\u2460-\u24FF"
                           r"\u25A0-\u25FF\u2B00-\u2BFF]")
except ImportError:
    EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2190-\u21FF"
                       "\u2300-\u23FF\u2460-\u24FF\u25A0-\u25FF\u2B00-\u2BFF\uFE0F]")
WL = {"\u2192"}

PANELS = [
    ("capabilities.html", "能力球 · 能力台",
     "158 项能力铺在一个真 3D 球面上（手写三维引擎，零依赖）。拖拽旋转，"
     "悬停读数，点节点进它自己的独立页面。形态即状态：实心=免卡、琥珀环=要授权、"
     "空心虚线=桩、暗红=禁用。配色可切（1/2/3/4）。",
     "render/能力球-violet-默认.png"),
    ("holo_pet_w3/index.html", "上帝视角 W3",
     "六页签实时驾驶舱：四视图 / 工作树 / 故障矩阵 / 驾驶舱 / 工具 / 数字人。"
     "数据走 Electron IPC 桥，独立窗口打开。",
     "render/godview/quad_四视图.png",
     # 第 115 轮：`holo_pet_w3/brain/index.html`（神经可视化工作台）在第 112 轮被
     # **手补成一张顶层卡**，挤掉了名册在册的 `pet`（holo_pet/index.html）。
     # 但它是 W3 的**窗 E** —— `holo_pet_w3/window.js` 的页签表里就有它
     # （["神经工作台","brain","能力图与脉冲"]），宿主登记表里**也没有**这一条。
     # ⇒ 口径：**顶层卡 = 名册（host.js PANELS）一一对应**；子窗口做成子入口，
     #    既不占顶层卡位，也不丢直达。若主人要它升为顶层面板，改的是 host.js 名册，不是这一页。
     [("holo_pet_w3/brain/index.html", "神经工作台（窗 E）")]),
    ("holo_pet/index.html", "主控台 W1",
     "桌面宠物主界面。需先起本地服务（holo_pet/panel_server.py），"
     "否则页面拿不到 /api/* 数据。",
     "render/godview/pets_数字人.png"),
    ("V22 GBT小土豆V8-可交互原型.html", "V22 可交互原型",
     "本版交付物之一（App 类）。高保真可交互，单文件自带全部样式与脚本。",
     "render/总览-58画布页.png"),
    ("V22 GBT小土豆V8-无限画布.html", "V22 无限画布",
     "本版交付物之一。自由画布形态，支持拖拽 / 缩放 / 复位。",
     "render/总览-55面板.png"),
    ("projects/_shared/templates/20260921-三方向-HITL1审批屏.html", "HITL#1 审批屏",
     "三件作品的审批面：链状态 + 逐镜待填 + 闸口表 + 编排自审 + 独立审计判定 + 作者认账。",
     "render/hitl1/审批屏-首屏.png"),
    ("projects/_shared/templates/20260921-三方向-HITL1-分镜契约填写页.html", "分镜契约填写页",
     "把「审」变成「填」：旁白摆在输入框左边，契约「先读旁白再决定」被结构性强制的 85 格表单。",
     "render/hitl1/填写页-首屏.png"),
    ("deploy/index.html", "部署版入口",
     "推到部署面的那份（deploy/）：<b>V21 代快照</b>（与根上 V22 有 39 行差，页内自称 V21）。"
     "重新部署＝外网写入 → 先问主人。",
     None),
    # 第 115 轮折回：这一卡第 112 轮是**手补在产物上**的（模板里没有）——
    # 手补的后果有两处，都已在此处修正：
    #   ① 重生成就冲掉（`--check` 报 948 字不一致）；
    #   ② desc 里写了 markdown 字面量 `**现读**`，**会原样渲染到页面上**，
    #      被生成器自检「渲染区无 markdown 泄漏」抓红（此前无人看见，因为 --check 不跑自检）。
    ("media-console.html", "三方向自动化工作流",
     "短视频 / AI电影 / AI音乐 三条链的<b>现读</b>进度：18 格抽屉（有货 · 仅彩排 · 空）+ "
     "许可账（逐件 sha256）+ 发布包（停在主人授权门）+ 试听台 + 输入口判据强度。"
     "数据<b>生成期烘焙</b>（生成器当场读抽屉 / 许可 / 副档），非手抄。"
     "重生成走 <code>media-console.py</code>。",
     None),
    ("holo_pet_w3/h1/index.html", "赏金台 · h1mcp",
     "HackerOne 赏金台（阶段一 · 本机只读）：二进制在位 + 侧车 sha256 比对、"
     "凭据配置状态（只报「已配置 / 未配置」，不回显值、连用户名也不回显）、本地草稿收件箱。"
     "零子进程 / 零网络 / 零写盘；取不到就灰并写明原因，<b>不假绿</b>。"
     "脚注显示本次真实通道（IPC / 同源 / 本机直连）。",
     None),
    ("brain.html", "大脑执行层 · 五维合一",
     "五维合一脑的排布图与连接网络：结构从 brain_exec.py 的 AST 现算"
     "（Sugiyama 分层布局，不是力导向），实时态取 store/audit.jsonl 的真实事件尾部。"
     "<b>源码里查不到的边不画</b> —— 注册表声称的执行链有 3 条在代码里不存在，图上如实标 drawn=false。",
     None),
    ("holo_pet/assets/digital-human/web/avatar.html", "数字人形象页（成品）",
     "数字人主线的成品页：idle 与 walk 交叉淡入状态机 · IBL(RoomEnvironment) + PBR Neutral + "
     "PCFSoft 接触阴影 + SSAA · 皮肤 sheen（SSS 近似）+ 暖轮廓 · HUD 现读。"
     "默认全身动画件（3.37 MB）；<code>?model=bust</code> 换半身件（4.28 MB）—— "
     "<b>两件都在宿主 12 MB 单文件上限内</b>，所以能直接内嵌；4K 件 90.86 MB 超上限，别指过来。",
     None),
]

GALLERIES = [
    ("render/godview", "上帝视角 · 逐页留影"),
    ("render/hitl1", "HITL#1 · 审批与填写"),
    ("render", "总览图"),
]

CSS = """
/* ── 令牌：唯一允许写裸色值的地方（与上帝视角同源） ── */
:root {
  --gold:#F5B041; --cyan:#00E5FF; --violet:#7C4DFF;
  --ok:#22C55E; --warn:#F5B041; --fault:#EF4444; --off:#6B7280;
  --bg:#04060E; --bg-2:#070B18; --panel:rgba(10,15,32,.72);
  --line:rgba(124,77,255,.26); --line-hot:rgba(0,229,255,.42);
  --text:#E8ECF8; --dim:#93A0C0; --faint:rgba(147,160,192,.5);
  --radius:10px; --radius-ctl:6px; --radius-pill:999px;
  --mono:"SF Mono","JetBrains Mono","Cascadia Mono",Consolas,ui-monospace,monospace;
}
/* 形状系统：卡片 10px · 控件 6px · 药丸 999px。整页只此三档，不许裸值。 */
* { box-sizing:border-box; }
html { scroll-behavior:smooth; }
body {
  margin:0; color:var(--text); position:relative; min-height:100vh;
  background:
    radial-gradient(1400px 700px at 8% -14%, rgba(0,229,255,.10), transparent 58%),
    radial-gradient(900px 500px at 96% 4%, rgba(124,77,255,.075), transparent 60%),
    linear-gradient(180deg, var(--bg) 0%, var(--bg-2) 100%);
  font:14px/1.62 "Microsoft YaHei UI","Segoe UI",system-ui,sans-serif;
  -webkit-font-smoothing:antialiased;
}
/* 工程网格 + 内暗角：固定背景，不随滚动跑 */
body::before {
  content:""; position:fixed; inset:0; pointer-events:none; z-index:0;
  background-image:
    linear-gradient(rgba(0,229,255,.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,229,255,.045) 1px, transparent 1px);
  background-size:64px 64px, 64px 64px;
  -webkit-mask-image:radial-gradient(1200px 800px at 50% 0%, #000 25%, transparent 78%);
  mask-image:radial-gradient(1200px 800px at 50% 0%, #000 25%, transparent 78%);
}
body::after {
  content:""; position:fixed; inset:0; pointer-events:none; z-index:0;
  background:radial-gradient(120% 90% at 50% 40%, transparent 42%, rgba(2,4,10,.72) 100%);
}
.wrap { position:relative; z-index:1; max-width:1460px; margin:0 auto; padding:0 34px 56px; }

.topbar {
  display:flex; align-items:center; gap:14px; flex-wrap:wrap;
  padding:13px 0; border-bottom:1px solid var(--line);
  font:500 11.5px/1 var(--mono); letter-spacing:.14em; color:var(--faint);
  text-transform:uppercase;
}
.topbar .dot {
  width:7px; height:7px; border-radius:var(--radius-pill);
  background:var(--ok); box-shadow:0 0 10px var(--ok);
  animation:beat 3.2s ease-in-out infinite;
}
@keyframes beat { 0%,100%{opacity:1} 50%{opacity:.3} }
.topbar .grow { flex:1; }
.topbar b { color:var(--text); font-weight:600; }

.hero { padding:52px 0 26px; }
.eyebrow {
  font:600 11.5px/1 var(--mono); letter-spacing:.3em; color:var(--cyan);
  text-transform:uppercase; margin:0 0 18px;
}
.eyebrow::before { content:"\\25AA\\25AA "; color:var(--violet); letter-spacing:.1em; }
h1 {
  margin:0 0 14px; font-weight:700; letter-spacing:-.03em; line-height:1.02;
  font-size:clamp(40px, 6.2vw, 78px);
  background:linear-gradient(180deg, #FFFFFF 0%, #C3CFEA 58%, rgba(147,160,192,.6) 100%);
  -webkit-background-clip:text; background-clip:text; color:transparent;
}
h1 em {
  font-style:normal; color:var(--cyan);
  text-shadow:0 0 34px rgba(0,229,255,.45);
}
.lede { margin:0; color:var(--dim); max-width:74ch; font-size:15px; }
.lede b { color:var(--gold); }

.stats {
  display:flex; flex-wrap:wrap; margin:28px 0 6px;
  border:1px solid var(--line); border-radius:var(--radius);
  background:linear-gradient(180deg, rgba(0,229,255,.035), transparent);
  overflow:hidden;
}
.stats div { flex:1; min-width:150px; padding:15px 20px; border-right:1px solid var(--line); }
.stats div:last-child { border-right:none; }
.stats .n { display:block; font:700 30px/1 var(--mono); color:var(--text); letter-spacing:-.02em; }
.stats .n.hot { color:var(--cyan); text-shadow:0 0 22px rgba(0,229,255,.4); }
.stats .k {
  display:block; margin-top:6px; font:500 11px/1 var(--mono);
  letter-spacing:.16em; color:var(--faint); text-transform:uppercase;
}

.sec-h {
  display:flex; align-items:baseline; gap:12px; margin:42px 0 16px;
  padding-bottom:10px; border-bottom:1px solid var(--line);
}
.sec-h h2 { margin:0; font-size:15px; font-weight:650; }
.sec-h .cnt { font:500 11px/1 var(--mono); color:var(--faint); letter-spacing:.1em; }

.panel-list { display:flex; flex-direction:column; gap:10px; }
a.card {
  position:relative; display:grid; grid-template-columns:250px 1fr; gap:18px;
  border:1px solid var(--line); border-radius:var(--radius);
  background:var(--panel); padding:13px 16px 13px 13px;
  text-decoration:none; color:inherit; overflow:hidden;
  transition:border-color .18s ease, transform .18s ease, box-shadow .18s ease;
}
a.card::before {
  content:attr(data-i); position:absolute; top:9px; right:13px;
  font:600 11px/1 var(--mono); color:var(--faint); letter-spacing:.1em;
}
a.card::after {
  content:""; position:absolute; left:0; bottom:0; width:16px; height:16px;
  border-left:2px solid var(--violet); border-bottom:2px solid var(--violet); opacity:.55;
}
a.card:hover {
  border-color:var(--line-hot);
  box-shadow:0 0 0 1px rgba(0,229,255,.14), 0 14px 40px -18px rgba(0,229,255,.5);
  transform:translateY(-2px);
}
a.card[aria-disabled="true"] { opacity:.5; }
.thumb {
  display:block; border-radius:var(--radius-ctl); overflow:hidden;
  background:#02040A; aspect-ratio:16/10; border:1px solid var(--line);
}
.thumb img {
  width:100%; height:100%; object-fit:cover; display:block;
  filter:saturate(1.05) contrast(1.04); transition:transform .35s ease;
}
a.card:hover .thumb img { transform:scale(1.035); }
.noimg {
  display:flex; align-items:center; justify-content:center; height:100%;
  color:var(--off); font:500 11px/1 var(--mono); letter-spacing:.14em;
}
.cbody { min-width:0; display:flex; flex-direction:column; gap:6px; justify-content:center; }
.chead { display:flex; align-items:baseline; gap:10px; }
.chead b { font-size:17px; font-weight:650; letter-spacing:-.01em; }
.cdesc { color:var(--dim); font-size:13px; }
.cmeta { color:var(--faint); font:500 11.5px/1.6 var(--mono); overflow-wrap:anywhere; }
.miss { color:var(--fault); font-weight:600; }
.chip {
  border:1px solid currentColor; border-radius:var(--radius-pill);
  padding:1px 9px; font:600 10.5px/1.6 var(--mono); letter-spacing:.08em;
}
.chip-ok { color:var(--ok); box-shadow:0 0 12px -3px currentColor; }
.chip-fault { color:var(--fault); }
code {
  font:12px/1.5 var(--mono); color:var(--cyan);
  background:rgba(0,229,255,.07); padding:1px 6px; border-radius:var(--radius-ctl);
}

.gal { margin:0 0 30px; }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(250px,1fr)); gap:11px; }
a.tile {
  display:block; border:1px solid var(--line); border-radius:var(--radius);
  background:var(--panel); padding:8px; text-decoration:none; color:inherit;
  transition:border-color .18s ease, transform .18s ease;
}
a.tile:hover { border-color:var(--line-hot); transform:translateY(-2px); }
a.tile img {
  width:100%; aspect-ratio:16/10; object-fit:cover; display:block;
  border-radius:var(--radius-ctl); background:#02040A; border:1px solid var(--line);
}
.tname { display:block; margin-top:7px; font-size:12.5px; overflow-wrap:anywhere; }
.tsize { display:block; color:var(--faint); font:500 10.5px/1.7 var(--mono); letter-spacing:.06em; }

/* 卡内子入口（子窗口，不占顶层卡位）：形状沿用令牌，不新造档位 */
.subs {
  display:block; margin-top:6px; color:var(--faint);
  font:500 11px/1.7 var(--mono); letter-spacing:.04em;
}
a.sub { color:var(--cyan); text-decoration:none; border-bottom:1px dotted var(--line-hot); }
a.sub:hover { color:var(--text); border-bottom-color:var(--cyan); }
.sub-miss { color:var(--fault); }

footer.sig {
  margin-top:34px; padding-top:15px; border-top:1px solid var(--line);
  color:var(--faint); font:500 11.5px/1.8 var(--mono); letter-spacing:.06em;
}
@media (max-width:720px) {
  .wrap { padding:0 18px 40px; }
  a.card { grid-template-columns:1fr; }
  .hero { padding:32px 0 20px; }
}
"""


def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def kb(n: int) -> str:
    return f"{n/1024:,.0f} KB" if n >= 1024 else f"{n} B"


def rendered_region(html_text: str) -> str:
    """**真渲染区**：去掉 `<style>` / `<script>` / HTML 注释之后剩下的可见文本。

    第 115 轮修的就是这里。这两条判据原先取样在**整个 body**（注释和脚本也算进去），
    于是量的是**不渲染的区域** ⇒ 模板与产物**双双假红**，而 `--check` 只比字符不跑自检，
    红了很久没人看见。更坏的是：真泄漏（`deploy` 卡 desc 里的 `**V21 代快照**`）
    混在一堆假命中里，**红得没有信息量**。
    ⇒ 取样区收到真渲染区之后，判据才既**准**（不误报注释）又**有牙**（真泄漏照样抓）。
    """
    s = re.sub(r".*?<body[^>]*>", "", html_text, flags=re.S)
    s = re.sub(r"<style.*?</style>", "", s, flags=re.S)
    s = re.sub(r"<script.*?</script>", "", s, flags=re.S)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    return s


def discover_gallery(rel: str) -> list[tuple[str, int]]:
    d = ROOT / rel
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob("*.png")):
        if rel == "render" and not p.name.startswith("总览"):
            continue
        out.append((str(p.relative_to(ROOT)).replace("\\", "/"), p.stat().st_size))
    return out


def build() -> tuple[str, dict]:
    facts = {"panels": [], "missing": [], "gallery": {}}
    cards = []
    for n, item in enumerate(PANELS, 1):
        rel, name, desc, thumb = item[:4]
        subs = item[4] if len(item) > 4 else []
        p = ROOT / rel
        exists = p.is_file()
        size = p.stat().st_size if exists else 0
        th = ROOT / thumb if thumb else None
        th_ok = bool(th and th.is_file())
        facts["panels"].append({"path": rel, "name": name, "exists": exists,
                                "bytes": size, "thumb": th_ok})
        if not exists:
            facts["missing"].append(rel)
        state = ('<span class="chip chip-ok">在</span>' if exists
                 else '<span class="chip chip-fault">缺</span>')
        img = (f'<img src="{esc(thumb)}" alt="{esc(name)} 预览" loading="lazy">'
               if th_ok else '<div class="noimg"><span>NO PREVIEW</span></div>')
        meta = (f'{kb(size)} · <code>{esc(rel)}</code>' if exists
                else f'<span class="miss">文件不存在</span> · <code>{esc(rel)}</code>')
        # 子入口：**不是 `a.card`** —— 判据是「顶层卡 ⇄ 名册一一对应」，
        # 子窗口做成卡内小链，既直达又不冒充顶层面板。缺件当场标缺，不假绿。
        sub_html = ""
        if subs:
            links = []
            for srel, slabel in subs:
                if (ROOT / srel).is_file():
                    links.append(f'<a class="sub" href="{esc(srel)}">{esc(slabel)}</a>')
                else:
                    links.append(f'<span class="sub sub-miss">{esc(slabel)} · 缺</span>')
            sub_html = '<span class="subs">子窗口 · ' + " · ".join(links) + "</span>"
        # ⚠️ `desc` 是**我们自己在 PANELS 里写的可信 HTML**（含 <b>/<code>），所以这里**不转义**；
        #    名称与路径仍然转义。往 PANELS 里加条目时，desc 里出现字面 `<` 必须自己写成 `&lt;`。
        cards.append(f"""
      <a class="card" data-i="{n:02d}" href="{esc(rel)}"{' aria-disabled="true"' if not exists else ''}>
        <span class="thumb">{img}</span>
        <span class="cbody">
          <span class="chead"><b>{esc(name)}</b>{state}</span>
          <span class="cdesc">{desc}</span>
          <span class="cmeta">{meta}</span>{sub_html}
        </span>
      </a>""")

    gal_blocks = []
    for rel, title in GALLERIES:
        imgs = discover_gallery(rel)
        facts["gallery"][rel] = len(imgs)
        if not imgs:
            continue
        tiles = "".join(
            f'<a class="tile" href="{esc(p)}">'
            f'<img src="{esc(p)}" alt="{esc(Path(p).stem)}" loading="lazy">'
            f'<span class="tname">{esc(Path(p).stem)}</span>'
            f'<span class="tsize">{kb(sz)}</span></a>'
            for p, sz in imgs)
        gal_blocks.append(f"""
  <section class="gal">
    <div class="sec-h"><h2>{esc(title)}</h2><span class="cnt">{len(imgs)} 张</span></div>
    <div class="grid">{tiles}</div>
  </section>""")

    sum(1 for p in facts["panels"] if p["exists"])
    sum(p["bytes"] for p in facts["panels"] if p["exists"])
    sum(facts["gallery"].values())

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GBT小土豆V8 · 总入口</title>
<!-- 内联 data: icon：不依赖路径（DSH 宿主 / file:// 都成立）。
     ⚠️ 这条要留在**模板**里：先前它是手补在生成产物上的，一旦重新生成就被冲掉，
     浏览器转而请求 /favicon.ico 拿 404，控制台多一条红字。 -->
<link rel="icon" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAWklEQVR42mNgGAWjYBSMglEwCkbBKBgFo2AUjIJRMApGwSgYBaNgFIyCUTAKRsEoGAWjYBSMglEwCkbBKBgFo2AUjIJRMApGwSgYBaNgFIyCUTAKRsEoAAB2gAH/8kQ0dQAAAABJRU5ErkJggg==">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

  <div class="topbar">
    <span class="dot"></span>
    <span>GBT小土豆V8</span>
    <span class="grow"></span>
    <span>WORKSPACE INDEX</span>
    <span>PANELS <b id="t-panels">—</b></span>
    <span>RENDERS <b id="t-renders">—</b></span>
  </div>

  <div class="hero">
    <p class="eyebrow">Workspace · Panel Index</p>
    <h1>可视化面板<em>总索引</em></h1>
    <p class="lede">一屏看全本工作区所有可视化面板与渲染留影，<b>点开即用</b>。
       本页清单与宿主插件的 PANELS 登记表同源；<b>顶部台账与每张卡片的字节数都是打开这一页时
       现读宿主目录</b>（同源 <code>GET /gbt-master</code>），不是写死的 —— 取不到就显示
       <b>「取不到」</b>并写明原因，<b>不顶一个好看的假数</b>。要逐页真渲染审计请用
       <code>plugins/gbt-master/tools/cross-scan.py</code>（真 Chrome 穿透四层：登记表 / 路由 /
       运行时 / 数据层，抓状态码、控制台错、失败请求、canvas 是否真出画面）。</p>
  </div>

  <div class="stats">
    <div><span class="n hot" id="s-panels">—</span><span class="k">PANELS LIVE</span></div>
    <div><span class="n" id="s-renders">—</span><span class="k">RENDERS</span></div>
    <div><span class="n" id="s-payload">—</span><span class="k">PAYLOAD</span></div>
    <div><span class="n" id="s-missing">—</span><span class="k">MISSING</span></div>
  </div>

  <div class="sec-h"><h2>活面板</h2><span class="cnt" id="live-src">READING…</span></div>
  <div class="panel-list">{''.join(cards)}</div>
{''.join(gal_blocks)}

  <footer class="sig">{SIGN}</footer>
</div>

<script>
/* ── 台账现读 ───────────────────────────────────────────────────────────────
   🔴 这段**必须留在模板里**：先前它是手补在生成产物上的（顶栏写死
   「PANELS 10 / RENDERS 26 / PAYLOAD 1,726 KB」，而宿主目录实测 total 12 / renders 67）
   —— 页面自称"与登记表同源"、数字却是手抄的。**不诚实的自述比没有自述更坏。**
   现在：打开这一页就同源读 `GET /gbt-master`，台账与每张卡片的字节数、在/缺全部按当次真值填；
   **取不到就显示「取不到」并写明原因，不顶假数**。（宿主目录路由与本页同源，不需额外权限。） */
(function () {{
  function kb(n) {{
    if (typeof n !== 'number' || !isFinite(n)) return '—';
    if (n >= 1048576) return (n / 1048576).toFixed(2) + ' MB';
    return Math.round(n / 1024).toLocaleString('en-US') + ' KB';
  }}
  function set(id, v) {{ var el = document.getElementById(id); if (el) el.textContent = String(v); }}
  function fail(why) {{
    ['t-panels', 't-renders', 's-panels', 's-renders', 's-payload', 's-missing'].forEach(function (i) {{ set(i, '取不到'); }});
    set('live-src', '宿主目录取不到：' + why);
    document.querySelectorAll('a.card .cmeta').forEach(function (m) {{
      if (m.childNodes[0]) m.childNodes[0].nodeValue = '取不到 · ';
    }});
  }}
  fetch('/gbt-master', {{ headers: {{ accept: 'application/json' }}, cache: 'no-store' }})
    .then(function (r) {{ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }})
    .then(function (cat) {{
      var panels = (cat && cat.panels) || [];
      var present = panels.filter(function (p) {{ return p.exists; }});
      var payload = present.reduce(function (a, p) {{ return a + (p.size || 0); }}, 0);
      set('t-panels', cat.total);
      set('t-renders', cat.renders === null || cat.renders === undefined ? '—' : cat.renders);
      set('s-panels', cat.present);
      set('s-renders', cat.renders === null || cat.renders === undefined ? '—' : cat.renders);
      set('s-payload', kb(payload));
      set('s-missing', panels.length - present.length);
      set('live-src', 'LIVE · 现读 /gbt-master · ' + new Date().toLocaleTimeString('zh-CN'));

      var byFile = {{}};
      panels.forEach(function (p) {{ byFile[p.file] = p; }});
      // ── 双向对账（第 115 轮补）─────────────────────────────────────────────
      // 原来只测一个方向：**卡片 → 登记表**（不在登记表的卡打「不在登记表」）。
      // 于是「登记表里有、本页却没有卡」的那一半**永远看不见** —— 实测正是它漏掉了
      // 名册在册的 `holo_pet/index.html`（主控台 W1）。关系是对称的，两个方向都得测。
      var listed = {{}};
      var orphan = [];
      document.querySelectorAll('a.card').forEach(function (card) {{
        var f = card.getAttribute('href');
        listed[f] = 1;
        var p = byFile[f];
        var meta = card.querySelector('.cmeta');
        var chip = card.querySelector('.chip');
        if (!p) {{ orphan.push(f); if (chip) {{ chip.textContent = '不在登记表'; chip.className = 'chip chip-fault'; }} return; }}
        if (meta && meta.childNodes[0]) meta.childNodes[0].nodeValue = kb(p.size) + ' · ';
        if (chip) {{
          chip.textContent = p.exists ? '在' : '缺';
          chip.className = 'chip ' + (p.exists ? 'chip-ok' : 'chip-fault');
        }}
      }});
      // 自指豁免：名册把「总索引」本身也登记为一块面板，而**本页不该给自己一张卡**
      // （「从索引进索引」不是导航入口）。豁免写在文案里，不藏着。
      var SELF = 'index.html';
      var unlisted = panels.filter(function (p) {{ return p.file !== SELF && !listed[p.file]; }})
                           .map(function (p) {{ return p.file; }});
      // 每节留影张数：按本页真实 tile 数现算（与盘上 render/ 总数不是一回事，别混）
      document.querySelectorAll('section.gal').forEach(function (sec) {{
        var c = sec.querySelector('.cnt');
        if (c) c.textContent = sec.querySelectorAll('.tile').length + ' 张';
      }});
      var msg = 'LIVE · 现读 /gbt-master · ' + new Date().toLocaleTimeString('zh-CN');
      if (orphan.length) {{
        msg += ' · 本页有 ' + orphan.length + ' 张卡片不在宿主登记表：' + orphan.join(' / ');
      }}
      if (unlisted.length) {{
        msg += ' · 登记表有 ' + unlisted.length + ' 块面板本页没有卡片：' + unlisted.join(' / ');
      }}
      if (orphan.length || unlisted.length) set('live-src', msg);
      else set('live-src', msg + ' · 卡片与登记表一一对应');
    }})
    .catch(function (e) {{ fail(String(e && e.message ? e.message : e)); }});
}})();
</script>
</body>
</html>
""", facts


def main() -> int:
    html, facts = build()
    OUT.write_text(html, encoding="utf-8")
    back = OUT.read_text(encoding="utf-8")
    rendered = rendered_region(back)
    print("=" * 84)
    print("工作区总入口 · 生成（任务控制台视觉方向）")
    print("=" * 84)
    print(f"  落位: {OUT.relative_to(ROOT)}  ({len(back):,} 字)")
    print(f"  署名: {'在' if SIGN in back else '缺!'}")
    for p in facts["panels"]:
        print(f"    [{'在' if p['exists'] else '缺'}] {p['name']:22} {kb(p['bytes']):>9}"
              f" · {'有图' if p['thumb'] else '无图'}")
    print("  图库：" + " · ".join(f"{k} {v} 张" for k, v in facts["gallery"].items()))
    # 判据有牙自检（扰动法）：往**真渲染区**植入一处 markdown 泄漏与一个 emoji，
    # 两条判据**必须报红**。不植扰动就声称"判据活着"，等于没量过。
    leak_probe = rendered.replace("<b>", "<b>**打点**", 1)
    emoji_probe = rendered_region(back.replace("<body", "<body>\U0001F534", 1))
    teeth = (bool(re.search(r"\*\*|`[^`]*`", leak_probe))
             and bool({m.group() for m in EMOJI.finditer(emoji_probe)} - WL))
    checks = {
        "无 indigo 主色": not re.search(r"#(6366f1|4f46e5|4338ca|3730a3|8b5cf6|7c3aed|a855f7)", back, re.I),
        "无双色信任渐变": not re.search(
            r"linear-gradient\([^)]*(purple|indigo|#8b5cf6|#6366f1|#7c3aed)", back, re.I),
        "无 emoji 当图标（宽式·扣白名单·只看真渲染区）":
            not ({m.group() for m in EMOJI.finditer(rendered)} - WL),
        "无裸圆角（0 除外）": not re.search(
            r"border-radius:\s*(?!0\s*;)(?!var\()\d",
            re.sub(r":root\s*\{.*?\}", "", back, flags=re.S)),
        "渲染区无 markdown 泄漏（只看真渲染区）": not re.search(r"\*\*|`[^`]*`", rendered),
        "eyebrow 未泛滥": len(re.findall(r'class="eyebrow"', back)) <= 1,
        "判据有牙（植入泄漏 / emoji 必报红）": teeth,
    }
    print(f"\n  取样区：真渲染区 {len(rendered):,} 字 / 全文 {len(back):,} 字"
          f"（判据只看前者，注释与脚本不再误报）")
    print("  反 AI-slop 自检：")
    ok = True
    for k, v in checks.items():
        print(f"    {'✔' if v else 'x'} {k}")
        ok &= v
    return 0 if ok else 1


def check() -> int:
    """`--check`：**产物是不是这个模板生成的**（漂移就报）。

    为什么要有：这个产物里带着**盘上现算的读数**（面板清单 / 字节数 / 缩略图有无）——
    工作区一变它就过期，而它是个"总入口"页，读者会当真。
    口径同 `make_capability_console.py --check`：临时生成一份，与盘上产物逐字符比。
    """
    html, _facts = build()
    if not OUT.exists():
        print("🔴 产物不在：%s" % OUT)
        return 1
    now = OUT.read_text(encoding="utf-8")
    if now == html:
        print("✅ 产物与模板一致（%d 字）—— 盘上这份就是本生成器产出的" % len(html))
        return 0
    print("🔴 产物与模板**不一致**：盘上 %d 字 vs 生成 %d 字" % (len(now), len(html)))
    print("   ⇒ 要么工作区变了（读数过期：重新生成即可），要么有人只改了产物（手补的会被冲掉）。")
    print("   ⇒ 修法：`py -3.14 tools/codex-scripts/make_workspace_index.py`")
    return 1


if __name__ == "__main__":
    import sys as _sys
    raise SystemExit(check() if "--check" in _sys.argv else main())
