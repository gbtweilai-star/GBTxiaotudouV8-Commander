# -*- coding: utf-8 -*-
"""生成「三方向 HITL#1 · 分镜契约填写页」。

它解决什么：独立审计官判三件作品全部 `return_to_stage`，理由是 §1 三契约
（render / eyeline / depth）逐镜为空。但契约 §1 同时规定这些值
**「先读旁白，再决定」**、且「复制别人的理由 = 失败」——
所以**不许由作者代填**，必须由审批人逐镜定。

于是把「审」变成「填」：一页里把每镜的**旁白**摆在输入框左侧，
右边留 render / eyeline / depth / 理由 四个空位，外加两处全局必填：
  · 全片预设风格 —— 契约 §1：「没有风格的分镜板一律打回」
  · 收尾镜 shot.share —— 契约 §5：「缺了分镜板打回」

**本页不预填任何取值**。作者一个格子都不碰。
填完点导出 → 下载一份 JSON，落 `projects/_inbox/`，由合并脚本写成正式分镜件。

审美纪律同审批屏：单一主色、三档圆角、无 emoji、eyebrow ≤1、空态说明怎么填。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from gbt_allinone import run_task  # noqa: E402

TODAY = "20260921"
SIGN = "开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"
OUT = ROOT / "projects" / "_shared" / "templates" / f"{TODAY}-三方向-HITL1-分镜契约填写页.html"

# 契约 §1 的 render 取值域（照抄，不自造）
RENDER_OPTS = ["静帧（配运镜）", "3D 角色", "3D 物件", "数据图", "生成视频"]
DEPTH_OPTS = ["浅景深（点名锐面）", "深景深（从前到后列出）"]

WORKS = [
    {"dir": "short-video", "kind": "短视频", "name": "AI搬砖人",
     "script": f"projects/short-video/01-script/{TODAY}-AI搬砖人/{TODAY}-short-video-AI搬砖人-01script.md",
     "board": f"projects/short-video/02-storyboard/{TODAY}-AI搬砖人/{TODAY}-short-video-AI搬砖人-02storyboard.md",
     "has_narration": True,
     "share": "不是你不够努力，是你的努力用错了地方。"},
    {"dir": "film", "kind": "电影", "name": "老屋",
     "script": f"projects/film/01-screenplay/{TODAY}-老屋/{TODAY}-film-老屋-01screenplay.md",
     "board": f"projects/film/02-storyboard/{TODAY}-老屋/{TODAY}-film-老屋-02storyboard.md",
     "has_narration": False,
     "share": ""},
    # 音乐没有分镜件（走歌词闸，不走切镜表）—— 但**它仍然是一件作品**，
    # 它的「§3 生成前闸」四项与三项证明照样要在 HITL#1 定。
    # 上一版把它整件漏在 WORKS 之外，于是三方向做成两方向。
    {"dir": "music", "kind": "音乐", "name": "夜航",
     "script": f"projects/music/01-lyrics/{TODAY}-夜航/{TODAY}-music-夜航-01lyrics.md",
     "board": None,
     "has_narration": False,
     "share": ""},
]

# ── 「其余必填」：契约里属 HITL#1、但不属逐镜三契约的项 ──
# 全部用 <select>/<input data-global>，于是自动保存 / 导出 / 导入**复用同一条路径**，
# 不另写第二套读写（上一轮的串镜 bug 就是两套键各写一份导致的）。
YESNO = ["是", "否", "未定"]

ATTEST = [
    {"name": "att_copyright", "label": "版权已核（素材授权可追溯）", "kind": "select",
     "options": YESNO,
     "hint": "对应媒体管线 self_review 的 copyright_attested。没核就是没核，不许勾「是」。"},
    {"name": "att_safety", "label": "安全已审", "kind": "select", "options": YESNO,
     "hint": "对应 safety_reviewed。"},
    {"name": "att_owner", "label": "主人已批（HITL#1 分镜审批签署）", "kind": "select", "options": YESNO,
     "hint": "对应 owner_reviewed，也是 video-pipeline §6 的第一道闸：没审批不许生成。"},
]

EXTRAS = {
    "music": [
        {"name": "gate_source", "label": "来源已核验", "kind": "select",
         "options": ["不适用（本曲虚构抒情，§1 溯源铁律不触发）", "已核验", "未核验"],
         "hint": "契约 §1 的溯源铁律只对纪实/真实事件类专辑生效。"},
        {"name": "gate_flag", "label": "显式标志位已设", "kind": "select", "options": YESNO,
         "hint": "§3 第二项。"},
        {"name": "gate_style_prompt", "label": "风格提示词完整", "kind": "text",
         "placeholder": "例如：慢速钢琴 + 环境声，人声靠后，无鼓组",
         "hint": "§3 第三项。"},
        {"name": "gate_artist_clear", "label": "艺人名已清（避免侵权指向）", "kind": "select",
         "options": YESNO, "hint": "§3 第四项，契约加粗强调。"},
    ],
    "film": [
        {"name": "line_shot", "label": "唯一台词「妈回来了」挂到第几镜", "kind": "shotnum",
         "hint": "剧本件 L55 自述「这句的归属我没把握到位 —— 是对相框里的人说，还是对自己说」；"
                 "两种演法完全不同，必须在这里定死。"},
        {"name": "line_to", "label": "这句是对谁说的", "kind": "select",
         "options": ["对相框里的人（遗像）", "对自己", "两者皆可（留给表演）", "未定"]},
        {"name": "alt_scene", "label": "备选场「院子空镜 6s」是否采纳", "kind": "select",
         "options": ["不采纳（保持 56s 单场）", "采纳（补走位落幅）", "未定"],
         "hint": "剧本件 L20 把该场标为「若需要补一个『走』的落幅」。"},
    ],
    "short-video": [
        {"name": "hook_video", "label": "开场是否用付费视频镜（hook_video）", "kind": "select",
         "options": ["关（契约默认：没有哪个镜头因为它在开头就值得付钱）", "开（需说明理由）", "未定"],
         "hint": "video-pipeline §2.3：hook_video 默认关。"},
    ],
}


def extras_html(direction: str) -> str:
    items = ATTEST + EXTRAS.get(direction, [])
    rows = []
    for it in items:
        if it["kind"] == "select":
            ctl = ('<select class="f" data-global="%s"><option value=""></option>%s</select>'
                   % (it["name"], "".join(f'<option value="{esc(o)}"></option>' for o in it["options"])))
        elif it["kind"] == "shotnum":
            ctl = ('<input class="f fnum" data-global="%s" list="shot-opts" placeholder="镜号">'
                   % it["name"])
        else:
            ctl = ('<input class="f fwide" data-global="%s" placeholder="%s">'
                   % (it["name"], esc(it.get("placeholder", ""))))
        hint = f'<span class="exh">{esc(it.get("hint", ""))}</span>' if it.get("hint") else ""
        rows.append(f'<li><label class="exl">{esc(it["label"])}</label>{ctl}{hint}</li>')
    return f"""
      <div class="extras">
        <p class="ex-h">本件其余必填（契约里属 HITL#1、但不属逐镜三契约的项）</p>
        <ul class="exl-list">{''.join(rows)}</ul>
      </div>"""


TIMED_RE = re.compile(r"## 一、分镜稿输入.*?```\n(.*?)```", re.S)
# 口播稿表行：| 0–3s | 口播 | 作用 |
NARR_RE = re.compile(r"^\|\s*(\d+)[–-](\d+)s\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*$", re.M)


def read(rel) -> str:
    """读盘上文件。**rel 允许为 None**（音乐没有分镜件），返回空串而不是抛 TypeError。"""
    if not rel:
        return ""
    f = ROOT / rel
    return f.read_text(encoding="utf-8") if f.is_file() else ""


def parse_timed(text: str) -> dict:
    r = run_task("drama", {"op": "parse_timed", "text": text})
    res = r.get("result", r) if isinstance(r, dict) else {}
    if isinstance(res, dict) and isinstance(res.get("result"), dict):
        res = res["result"]
    return res if isinstance(res, dict) else {}


# emoji/符号判据：**宽式**，不用窄式。
# 窄式 [\U0001F300-\U0001FAFF\u2600-\u27BF] 漏掉 ←(2190) →(2192) ↔(2194)
# ⇒(21D2) ①(2460)~⑦(2466) ⌘(2318) ◇(25C7) —— 这个覆盖面缺口是并行流的
# `audit_craft_gate.py` 对照规则书逐条量出来的，不是我自己想到的。
try:
    import regex as _regex  # type: ignore
    _EMOJI_RE = _regex.compile(r"[\p{Extended_Pictographic}\p{Emoji_Presentation}"
                               r"\u2190-\u21FF\u2300-\u23FF\u2460-\u24FF"
                               r"\u25A0-\u25FF\u2B00-\u2BFF]")
except ImportError:  # pragma: no cover
    import re as _re2
    _EMOJI_RE = _re2.compile(
        "[\U0001F300-\U0001FAFF\u2600-\u27BF\u2190-\u21FF\u2300-\u23FF"
        "\u2460-\u24FF\u25A0-\u25FF\u2B00-\u2BFF\uFE0F]")

# 唯一白名单：`→`(U+2192)。它在角色链/序列里是**排版分隔符**，不是界面图标；
# 判据保持宽式（不留盲区），只把这一处窄例外写下来 —— 理由同 make_hitl1_screen.py。
_EMOJI_WHITELIST = "\u2192"


def emoji_hits(text: str) -> list[str]:
    return sorted({m.group() for m in _EMOJI_RE.finditer(text)
                   if m.group() not in _EMOJI_WHITELIST})


def esc(s: str) -> str:
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def narration_map(script_text: str) -> dict:
    """把口播稿按时间区间索引起来，供分镜逐镜对齐。"""
    out = {}
    for a, b, line, role in NARR_RE.findall(script_text):
        out[(float(a), float(b))] = {"line": line.strip(), "role": role.strip()}
    return out


def build() -> tuple[str, dict]:
    facts = {"works": []}
    blocks = []
    for w in WORKS:
        btxt, stxt = read(w["board"]), read(w["script"])
        m = TIMED_RE.search(btxt)
        # 没有分镜件**不等于这件作品不存在**：音乐走的是歌词闸，本来就没有切镜表。
        # 上一版在这里 `continue`，于是页面里只剩两件作品 —— 三方向做成了两方向。
        # 现在：无分镜件时 rows=[]，本块照样渲染（逐镜表换成空态说明），
        # 让它的「其余必填」（三项证明 + §3 生成前闸）**照样能被定**。
        rows = []
        if m:
            pr = parse_timed(m.group(1).strip())
            shots = (pr.get("shots") or [])
            narr = narration_map(stxt) if w["has_narration"] else {}
            for s in shots:
                key = (float(s.get("t0", 0)), float(s.get("t1", 0)))
                n = narr.get(key, {})
                rows.append({
                    "idx": s.get("idx"), "t0": s.get("t0"), "t1": s.get("t1"),
                    "dur": s.get("dur"), "title": s.get("title") or "",
                    "size": s.get("shot_size") or "", "camera": s.get("camera") or "",
                    "emotion": s.get("emotion") or "",
                    "narration": n.get("line", ""), "role": n.get("role", ""),
                })
        facts["works"].append({"name": w["name"], "shots": len(rows),
                               "with_narration": sum(1 for r in rows if r["narration"]),
                               "has_board": bool(m)})
        blocks.append(render_work(w, rows))

    shots_total = sum(f["shots"] for f in facts["works"])
    cells_total = shots_total * 4          # render / eyeline / depth / 理由
    g_total = sum(globals_count(w) for w in WORKS)
    return render_page(blocks, facts, shots_total, cells_total, g_total), facts


def render_work(w: dict, rows: list) -> str:
    trs = []
    for r in rows:
        narr = (f'<span class="nr">{esc(r["narration"])}</span>'
                f'<span class="nrole">{esc(r["role"])}</span>') if r["narration"] else \
               ('<span class="nr empty">本片无旁白（虚构叙事）—— '
                '此镜的「理由」请对着上面<b>画面</b>写</span>')
        "".join(f'<option value="{esc(o)}"></option>' for o in RENDER_OPTS)
        "".join(f'<option value="{esc(o)}"></option>' for o in DEPTH_OPTS)
        trs.append(f"""
      <tr data-shot="{r['idx']}">
        <td class="num">{r['idx']}</td>
        <td class="pic">
          <span class="t">{esc(r['title'])}</span>
          <span class="m">{r['t0']}–{r['t1']}s · {r['dur']}s · {esc(r['size'])}</span>
        </td>
        <td class="narr">{narr}</td>
        <td><input class="f" data-field="render" list="render-opts" placeholder="选或填"></td>
        <td><input class="f" data-field="eyeline" placeholder="视线方向"></td>
        <td><input class="f" data-field="depth" list="depth-opts" placeholder="浅 / 深"></td>
        <td><input class="f fw" data-field="reason" placeholder="为什么这么选（不许复制上一镜）"></td>
      </tr>""")
    if rows:
        style_block = """
      <p class="globl">
        <label>全片预设风格（契约 §1：<b>没有风格的分镜板一律打回</b>）
          <input class="f fwide" data-global="style" placeholder="例如：冷调手持纪实 · 无配乐"></label>
      </p>"""
        shots_block = f"""
      <table class="fill">
        <thead><tr>
          <th>镜</th><th>画面（来自 parse_timed）</th><th>旁白 / 动作</th>
          <th>render</th><th>eyeline</th><th>depth</th><th>为什么这么选</th>
        </tr></thead>
        <tbody>{''.join(trs)}</tbody>
      </table>
      <p class="hint">契约 §1 的判据（照抄，不是我给的答案）：
        <b>render</b> 先读旁白再决定，开篇也走同一套；
        <b>depth</b> 数「观众一次要读几样东西」——一样就浅景深并点名锐面，两样以上就深景深并从前到后列出；
        <b>理由</b> 复制别人的 = 失败。</p>"""
    else:
        # 无分镜件 ≠ 本件不存在：音乐走歌词闸，本来就没有切镜表。
        # 空态要**说清这里为什么空、以及该去哪填**，不留白。
        # style 字段也不给音乐 —— 「全片预设风格」是 video-pipeline §1 的要求，
        # 拿视频规矩去标音乐字段就是贴错标签；音乐的对应项是 §3-3「风格提示词完整」（在下方必填里）。
        style_block = ""
        shots_block = """
      <p class="empty">本方向<b>不走切镜表</b>：音乐没有逐镜镜头契约，
        要定的是下面的「§3 生成前闸」四项与三项证明。
        <span class="how">逐镜三契约与「全片预设风格」都只对短视频与电影生效（§1 属 video-pipeline）；
        音乐对应的是 §3-3「风格提示词完整」。</span></p>"""
    share_block = ""
    if w["share"]:
        share_block = f"""
      <p class="sh">收尾镜的 <code>shot.share</code>（契约 §5：<b>缺了分镜板打回</b>）——
         本件已写好一句可转发物，请在下面确认它挂到哪一镜，或改写：
         <span class="quote">{esc(w['share'])}</span></p>
      <p class="sh-line"><label>挂到第 <input class="f fnum" data-global="share_shot" placeholder="镜号"> 镜</label>
         <label>或改写为 <input class="f fwide" data-global="share_text" placeholder="留空则沿用上面这句"></label></p>"""
    return f"""
    <section class="work" data-work="{w['dir']}" data-name="{esc(w['name'])}">
      <header class="wk">
        <h2>{esc(w['kind'])} · 《{esc(w['name'])}》</h2>
        <span class="chip">{'%d 镜 × 4 格 = %d 格待定' % (len(rows), len(rows)*4) if rows else '不走切镜表 · 只填下方必填项'}</span>      </header>

      {style_block}
      {shots_block}
      {share_block}
      <p class="warn"><b>预算闸提醒</b>：选「生成视频」的镜头会触发 §3 预算闸。当前<b>无价格表</b>，
        按契约「未知价格直接失败，不许猜」，这些镜头会被阻断 —— 请知悉后再选。</p>
      {extras_html(w['dir'])}
    </section>"""


def globals_count(w: dict) -> int:
    """本件全局必填项数：风格 1（**只对有分镜件的方向**）
       + （有 share 时 2：挂哪镜 + 文本）+ 三项证明 + 方向专属。
       **必须与实际渲染出的输入框数一致**，否则底栏进度会虚高。"""
    return ((1 if w.get("board") else 0) + (2 if w.get("share") else 0)
            + len(ATTEST) + len(EXTRAS.get(w["dir"], [])))


def render_page(blocks: list, facts: dict, shots: int, cells: int, g_total: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>三方向 · HITL#1 分镜契约填写页</title>
<!-- 内联 data: icon：不依赖路径（DSH 宿主 / file:// 都成立）。
     ⚠️ 这条原先**只补在产物上**、模板里没有 ⇒ 一重新生成就被冲掉（实测：两页各差 244 字，
     差的就是这一行）。教训与 `make_capability_console.py` / `make_workspace_index.py` 同源：**手补的东西必须挪进模板**。 -->
<link rel="icon" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAWklEQVR42mNgGAWjYBSMglEwCkbBKBgFo2AUjIJRMApGwSgYBaNgFIyCUTAKRsEoGAWjYBSMglEwCkbBKBgFo2AUjIJRMApGwSgYBaNgFIyCUTAKRsEoAAB2gAH/8kQ0dQAAAABJRU5ErkJggg==">
<style>
/* ── 令牌：唯一允许写裸色值的地方（与审批屏、上帝视角同源） ── */
:root {{
  --gold:#F5B041; --cyan:#00E5FF; --violet:#7C4DFF;
  --ok:#22C55E; --warn:#F5B041; --fault:#EF4444; --off:#6B7280;
  --bg:#050711; --panel:#0C1022; --line:rgba(124,77,255,.30);
  --text:#E8ECF8; --dim:#9AA4C4;
  --radius:10px; --radius-ctl:6px; --radius-pill:999px;
}}
/* 形状系统：卡片 10px · 控件 6px · 药丸 999px。整页只此三档。 */
* {{ box-sizing:border-box; }}
body {{
  margin:0; padding:26px 30px 120px;
  background:radial-gradient(1100px 460px at 12% -8%, rgba(0,229,255,.07), transparent 62%), var(--bg);
  color:var(--text); font:14px/1.6 "Microsoft YaHei UI","Segoe UI",system-ui,sans-serif;
}}
.wrap {{ max-width:1500px; margin:0 auto; }}
.eyebrow {{ font:600 11.5px/1 ui-monospace,Consolas,monospace; letter-spacing:.16em; color:var(--cyan); text-transform:uppercase; }}
h1 {{ margin:10px 0 6px; font-size:26px; font-weight:650; letter-spacing:-.015em; }}
.lede {{ margin:0 0 6px; color:var(--dim); max-width:82ch; }}
.lede b {{ color:var(--gold); }}
.rule {{ margin:0 0 20px; color:var(--fault); font-size:12.5px; }}

section.work {{ border:1px solid var(--line); border-radius:var(--radius); background:var(--panel); padding:15px 17px 17px; margin:0 0 16px; }}
.wk {{ display:flex; align-items:baseline; gap:12px; margin-bottom:10px; }}
.wk h2 {{ margin:0; font-size:16px; font-weight:620; }}
.chip {{ border:1px solid currentColor; border-radius:var(--radius-pill); padding:1px 10px; font-size:12px; color:var(--warn); }}
.globl {{ margin:0 0 12px; color:var(--dim); font-size:12.5px; }}
.globl b {{ color:var(--gold); }}

table.fill {{ width:100%; border-collapse:collapse; }}
table.fill th {{ text-align:left; font-weight:600; font-size:11.5px; color:var(--dim); border-bottom:1px solid var(--line); padding:6px 7px; letter-spacing:.03em; }}
table.fill td {{ padding:5px 7px; border-bottom:1px solid rgba(124,77,255,.13); vertical-align:top; }}
td.num {{ color:var(--dim); width:30px; }}
td.pic {{ width:210px; }}
td.pic .t {{ display:block; color:var(--text); font-size:12.5px; }}
td.pic .m {{ display:block; color:var(--dim); font-size:11px; margin-top:2px; }}
td.narr {{ width:250px; }}
.nr {{ display:block; color:var(--gold); font-size:12.5px; }}
.nr.empty {{ color:var(--dim); }}
.nr.empty b {{ color:var(--off); }}
.nrole {{ display:block; color:var(--dim); font-size:11px; margin-top:2px; }}

.f {{
  width:100%; background:rgba(0,229,255,.045); color:var(--text);
  border:1px solid var(--line); border-radius:var(--radius-ctl);
  padding:3px 7px; font:12.5px/1.5 inherit; min-width:96px;
}}
.f::placeholder {{ color:var(--off); }}
.f:focus {{ outline:none; border-color:var(--cyan); background:rgba(0,229,255,.09); }}
.f.fw {{ min-width:170px; }}
.f.fwide {{ min-width:300px; }}
.f.fnum {{ min-width:56px; }}
.sh {{ margin:14px 0 6px; padding:9px 12px; border-left:2px solid var(--cyan); border-radius:0; background:rgba(0,229,255,.05); color:var(--dim); font-size:12.5px; }}
.sh b {{ color:var(--gold); }}
.sh .quote {{ display:block; margin-top:5px; color:var(--text); }}
.sh-line {{ margin:0; display:flex; gap:22px; flex-wrap:wrap; color:var(--dim); font-size:12.5px; }}
.hint {{ margin:12px 0 0; color:var(--dim); font-size:12px; }}
.hint b {{ color:var(--text); }}
.warn {{ margin:10px 0 0; padding:8px 12px; border-left:2px solid var(--fault); border-radius:0; background:rgba(239,68,68,.06); color:var(--dim); font-size:12px; }}
.warn b {{ color:var(--fault); }}

/* 其余必填区：与逐镜表分开一条上规，读作「另一类决定」 */
.extras {{ margin-top:15px; padding-top:12px; border-top:1px solid rgba(124,77,255,.20); }}
.ex-h {{ margin:0 0 9px; color:var(--gold); font-size:12.5px; font-weight:600; }}
ul.exl-list {{ list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:9px; }}
ul.exl-list li {{ display:grid; grid-template-columns:250px minmax(240px, 360px) 1fr; gap:12px; align-items:baseline; }}
.exl {{ color:var(--text); font-size:12.5px; }}
.exh {{ color:var(--dim); font-size:11.5px; }}
/* 栅格单元里**不许**再带 min-width：.f.fwide 的 300px 会撑破 240px 的列，
   输入框会跟右侧说明挤在一起（截图看出来的，静态检查查不到）。 */
.extras .f {{ min-width:0; width:100%; }}
select.f {{ appearance:none; -webkit-appearance:none; cursor:pointer; }}
select.f option {{ background:var(--panel); color:var(--text); }}
code {{ font:12px/1.5 ui-monospace,Consolas,monospace; color:var(--cyan); background:rgba(0,229,255,.07); padding:1px 5px; border-radius:var(--radius-ctl); }}

/* 底部动作条：唯一的主色动作，其余中性 */
.bar {{
  position:fixed; left:0; right:0; bottom:0; z-index:9;
  display:flex; gap:14px; align-items:center; flex-wrap:wrap;
  padding:11px 30px; background:rgba(5,7,17,.94);
  border-top:1px solid var(--line); backdrop-filter:blur(6px);
}}
.bar .st {{ color:var(--dim); font-size:12.5px; }}
.bar .st b {{ color:var(--text); }}
button {{ font:inherit; border-radius:var(--radius-ctl); padding:5px 16px; cursor:pointer; border:1px solid var(--line); background:transparent; color:var(--dim); }}
button.pri {{ border-color:var(--cyan); color:var(--cyan); font-weight:600; }}
button:active {{ transform:translateY(1px); }}
footer.sig {{ margin-top:26px; padding-top:12px; border-top:1px solid var(--line); color:var(--dim); font-size:12px; }}
</style>
<datalist id="render-opts">{''.join(f'<option value="{esc(o)}">' for o in RENDER_OPTS)}</datalist>
<datalist id="depth-opts">{''.join(f'<option value="{esc(o)}">' for o in DEPTH_OPTS)}</datalist>
<datalist id="shot-opts">{''.join(f'<option value="{i}">' for i in range(1, 13))}</datalist>
</head>
<body>
<div class="wrap">
  <p class="eyebrow">GBT小土豆V8 · HITL#1 交互</p>
  <h1>分镜契约填写页 · 三方向</h1>
  <p class="lede">独立审计官判三件作品全部<b>退回返工</b>，卡点是 §1 三契约逐镜为空。
     契约 §1 同时规定这些值必须「<b>先读旁白，再决定</b>」、且「<b>复制别人的理由 = 失败</b>」——
     所以<b>不由作者代填</b>。本页把旁白摆在输入框左边，你照着念、照着定。</p>
  <p class="rule">本页一个格子都不预填。作者不碰任何取值。</p>

  <div class="decide" style="margin:0 0 18px;padding:11px 15px;border:1px solid var(--line);border-left:2px solid var(--warn);background:rgba(245,176,65,.055);display:flex;gap:26px;flex-wrap:wrap;">
    <span><span style="color:var(--dim);font-size:12.5px;">待定格子</span>
      <b style="font-size:15px;">{cells}</b>
      <span style="color:var(--dim);font-size:12.5px;">（{shots} 镜 × 4 项）</span></span>
    <span><span style="color:var(--dim);font-size:12.5px;">全局必填</span>
      <b style="font-size:15px;">{g_total} 项</b>
      <span style="color:var(--dim);font-size:12.5px;">（全片风格 / 收尾镜 share / 三项证明 / 方向专属）</span></span>
  </div>

{''.join(blocks)}

  <footer class="sig">{SIGN}</footer>
</div>

<div class="bar">
  <span class="st">已填 <b id="filled">0</b> / <b id="total">{cells + g_total}</b> 格</span>
  <button class="pri" id="btn-export">导出填好的分镜（JSON）</button>
  <button id="btn-import">导入已填的 JSON</button>
  <button id="btn-copy">复制成 markdown</button>
  <button id="btn-clear">清空</button>
  <span class="st" id="save-state">—</span>
  <input type="file" id="file-in" accept=".json,application/json" hidden>
</div>

<script>
(function () {{
  var inputs = Array.prototype.slice.call(document.querySelectorAll('.f'));
  var total = {cells + g_total};
  var KEY = 'gbt-hitl1-fill-v1';   // file:// 下所有本地页共享同一 origin，键必须专属

  /* 自动保存：实测 file:// 下 localStorage 可用且刷新后保留（Chrome），
     所以 64 格不必一次填完，也不怕误关页面。
     但**不同浏览器可能禁用**，所以失败要显式说出来，不能假装保存了。 */
  var LS = (function () {{
    try {{
      localStorage.setItem(KEY + ':probe', '1');
      localStorage.removeItem(KEY + ':probe');
      return {{ ok: true }};
    }} catch (e) {{ return {{ ok: false, why: e.name }}; }}
  }})();

  function say(msg, tone) {{
    var el = document.getElementById('save-state');
    el.textContent = msg;
    el.style.color = tone === 'bad' ? 'var(--fault)' : (tone === 'ok' ? 'var(--ok)' : 'var(--dim)');
  }}

  /* 快照键 = 作品|字段::镜号 —— **镜号绝不能省**。
     上一版写成 作品|字段，于是 8 个镜共用同一个键：
     填第 1 镜、刷新一次，8 镜全被写成同一份值（实测：只填 3 格 → 恢复出 17 格）。
     静态检查查不出来，是功能测试抓到的。 */
  function keyOf(i) {{
    var sec = i.closest('section.work');
    var sid = sec ? sec.getAttribute('data-work') : '_';
    var fd = i.getAttribute('data-field');
    if (fd) {{
      var tr = i.closest('tr[data-shot]');
      return sid + '|' + fd + '::' + (tr ? tr.getAttribute('data-shot') : '');
    }}
    return sid + '|@' + i.getAttribute('data-global');
  }}

  function snapshot() {{
    var o = {{}};
    inputs.forEach(function (i) {{
      if (i.value.trim()) o[keyOf(i)] = i.value;
    }});
    return o;
  }}

  var t = null;
  function save() {{
    if (!LS.ok) return;
    clearTimeout(t);
    t = setTimeout(function () {{
      try {{
        localStorage.setItem(KEY, JSON.stringify(snapshot()));
        var d = new Date();
        say('已自动保存到本机浏览器 · ' + d.toLocaleTimeString('zh-CN'), 'ok');
      }} catch (e) {{ say('保存失败：' + e.name, 'bad'); }}
    }}, 250);
  }}

  function restore() {{
    if (!LS.ok) return 0;
    var raw = null;
    try {{ raw = localStorage.getItem(KEY); }} catch (e) {{ return 0; }}
    if (!raw) return 0;
    var o;
    try {{ o = JSON.parse(raw); }} catch (e) {{ return 0; }}
    return applyMap(o);
  }}

  function applyMap(o) {{
    var n = 0;
    inputs.forEach(function (i) {{
      var v = o[keyOf(i)];          // 键含镜号，一镜一格，不会串
      if (typeof v === 'string' && v) {{ i.value = v; n++; }}
    }});
    return n;
  }}

  function refresh() {{
    var n = inputs.filter(function (i) {{ return i.value.trim(); }}).length;
    document.getElementById('filled').textContent = n;
  }}
  inputs.forEach(function (i) {{
    i.addEventListener('input', function () {{ refresh(); save(); }});
  }});

  function collect() {{
    var out = {{ schema: 'gbt-hitl1-storyboard-fill/v1', filled_at: new Date().toISOString(), works: {{}} }};
    document.querySelectorAll('section.work').forEach(function (sec) {{
      var key = sec.getAttribute('data-work');
      var w = {{ name: sec.getAttribute('data-name'), globals: {{}}, shots: {{}} }};
      sec.querySelectorAll('[data-global]').forEach(function (i) {{
        if (i.value.trim()) w.globals[i.getAttribute('data-global')] = i.value.trim();
      }});
      sec.querySelectorAll('tr[data-shot]').forEach(function (tr) {{
        var s = {{}};
        tr.querySelectorAll('.f[data-field]').forEach(function (i) {{
          if (i.value.trim()) s[i.getAttribute('data-field')] = i.value.trim();
        }});
        if (Object.keys(s).length) w.shots[tr.getAttribute('data-shot')] = s;
      }});
      out.works[key] = w;
    }});
    return out;
  }}

  /* 把导出的 JSON 摊平成与 snapshot() 同形的映射，这样「导入」与「自动恢复」共用一条路径 */
  function flatten(data) {{
    var o = {{}};
    var ws = data.works || {{}};
    Object.keys(ws).forEach(function (sid) {{
      var w = ws[sid] || {{}};
      Object.keys(w.globals || {{}}).forEach(function (g) {{ o[sid + '|@' + g] = w.globals[g]; }});
      Object.keys(w.shots || {{}}).forEach(function (idx) {{
        var s = w.shots[idx] || {{}};
        Object.keys(s).forEach(function (f) {{ o[sid + '|' + f + '::' + idx] = s[f]; }});
      }});
    }});
    return o;
  }}

  function toMd(data) {{
    var L = ['# HITL#1 分镜契约 · 填写回执', '',
             '> 由填写页导出，未由作者代填。', ''];
    Object.keys(data.works).forEach(function (k) {{
      var w = data.works[k];
      L.push('## ' + w.name + ' (' + k + ')', '');
      if (w.globals.style) L.push('- 全片预设风格：' + w.globals.style);
      if (w.globals.share_shot) L.push('- shot.share 挂第 ' + w.globals.share_shot + ' 镜');
      if (w.globals.share_text) L.push('- shot.share 文本：' + w.globals.share_text);
      L.push('', '| 镜 | render | eyeline | depth | 理由 |', '|---|---|---|---|---|');
      Object.keys(w.shots).sort(function (a, b) {{ return a - b; }}).forEach(function (i) {{
        var s = w.shots[i];
        L.push('| ' + i + ' | ' + (s.render || '') + ' | ' + (s.eyeline || '') +
               ' | ' + (s.depth || '') + ' | ' + (s.reason || '') + ' |');
      }});
      L.push('');
    }});
    return L.join('\\n');
  }}

  document.getElementById('btn-export').addEventListener('click', function () {{
    var data = collect();
    var blob = new Blob([JSON.stringify(data, null, 1)], {{ type: 'application/json' }});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'hitl1-storyboard-fill.json';
    a.click();
  }});

  document.getElementById('btn-import').addEventListener('click', function () {{
    document.getElementById('file-in').click();
  }});
  document.getElementById('file-in').addEventListener('change', function (ev) {{
    var f = ev.target.files && ev.target.files[0];
    if (!f) return;
    var rd = new FileReader();
    rd.onload = function () {{
      var data;
      try {{ data = JSON.parse(String(rd.result)); }}
      catch (e) {{ say('导入失败：不是合法 JSON（' + e.name + '）', 'bad'); return; }}
      if (data.schema !== 'gbt-hitl1-storyboard-fill/v1') {{
        say('导入失败：schema 不认（' + data.schema + '）', 'bad'); return;
      }}
      // 把 shots 里的字段摊成 snapshot 同形的键：sid|field::idx
      var flat = {{}};
      var ws = data.works || {{}};
      Object.keys(ws).forEach(function (sid) {{
        var w = ws[sid] || {{}};
        Object.keys(w.globals || {{}}).forEach(function (g) {{ flat[sid + '|@' + g] = w.globals[g]; }});
        Object.keys(w.shots || {{}}).forEach(function (idx) {{
          Object.keys(w.shots[idx] || {{}}).forEach(function (fd) {{
            flat[sid + '|' + fd + '::' + idx] = w.shots[idx][fd];
          }});
        }});
      }});
      var n = 0;
      inputs.forEach(function (i) {{
        var v = flat[keyOf(i)];      // 与 snapshot() 共用同一套键，两条路不会漂移
        if (typeof v === 'string' && v) {{ i.value = v; n++; }}
      }});
      refresh(); save();
      say('已导入 ' + n + ' 格', n ? 'ok' : 'bad');
    }};
    rd.readAsText(f);
    ev.target.value = '';
  }});

  document.getElementById('btn-copy').addEventListener('click', function () {{
    var md = toMd(collect());
    navigator.clipboard.writeText(md).then(function () {{
      document.getElementById('btn-copy').textContent = '已复制';
      setTimeout(function () {{ document.getElementById('btn-copy').textContent = '复制成 markdown'; }}, 1600);
    }});
  }});
  document.getElementById('btn-clear').addEventListener('click', function () {{
    if (!confirm('清空全部已填内容？（本机自动保存也会一并清掉）')) return;
    inputs.forEach(function (i) {{ i.value = ''; }});
    try {{ localStorage.removeItem(KEY); }} catch (e) {{}}
    refresh(); say('已清空', 'bad');
  }});

  var restored = restore();
  refresh();
  if (!LS.ok) say('本机浏览器禁用了自动保存（' + LS.why + '）—— 请用「导出」保存进度', 'bad');
  else if (restored) say('已恢复上次填写的 ' + restored + ' 格', 'ok');
  else say('自动保存已开启 · 填入即存本机浏览器', 'dim');
}})();
</script>
</body>
</html>
"""


def main() -> int:
    html, facts = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    back = OUT.read_text(encoding="utf-8")
    print("=" * 78)
    print("生成 HITL#1 分镜契约填写页")
    print("=" * 78)
    print(f"  落位: {OUT.relative_to(ROOT)}")
    print(f"  大小: {len(back)} 字")
    print(f"  署名: {'在' if SIGN in back else '缺失!'}")
    print("\n  逐镜数据（来自盘上产物 + parse_timed 现跑）：")
    for w in facts["works"]:
        print(f"    {w['name']:10} {w['shots']} 镜，其中 {w['with_narration']} 镜带旁白")
    # 纪律自检：页面里不许出现任何**预填的取值**
    body = re.sub(r".*?<body[^>]*>", "", back, flags=re.S)
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    prefill = re.findall(r'class="f[^"]*"[^>]*\svalue="[^"]+"', body)
    checks = {
        "无预填取值（作者不代填）": not prefill,
        "无 indigo 主色": not re.search(r"#(6366f1|4f46e5|4338ca|3730a3|8b5cf6|7c3aed|a855f7)", back, re.I),
        # 宽式判据（与交付物侧同口径）：窄式漏 ←→↔⇒①②③◇⌘，覆盖面缺口由 audit_craft_gate.py 量出
        "无 emoji 当图标（宽式·扣白名单）": not emoji_hits(back),
        "无裸圆角（0 除外）": not re.search(r"border-radius:\s*(?!0\s*;)(?!var\()\d",
                                    re.sub(r":root\s*\{.*?\}", "", back, flags=re.S)),
        "渲染区无 markdown 泄漏": not re.search(r"\*\*|`[^`]*`", body),
        "无 lorem/占位文": not re.search(r"lorem ipsum|placeholder text|sample content", back, re.I),
    }
    print("\n  自检：")
    ok = True
    for k, v in checks.items():
        print(f"    {'✔' if v else 'x'} {k}")
        ok &= v
    if prefill:
        for p in prefill[:5]:
            print(f"      ! 预填: {p[:110]}")
    return 0 if ok else 1


def check() -> int:
    """`--check`：**产物是不是这个模板生成的**（口径同 `make_capability_console.py --check`）。

    这一页里带着**盘上现读的读数**（逐镜数据 / 旁白映射 / 全局必填项计数）——工作区一变就过期；
    而它是"填写页"，读者会拿它当事实。产物必须能由模板复现，不能靠手补。
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
    print("   ⇒ 要么盘上读数变了（重新生成即可），要么有人只改了产物（手补的会被冲掉）。")
    print("   ⇒ 修法：`py -3.14 tools/codex-scripts/make_storyboard_fill_page.py`")
    return 1


if __name__ == "__main__":
    import sys as _sys
    raise SystemExit(check() if "--check" in _sys.argv else main())
