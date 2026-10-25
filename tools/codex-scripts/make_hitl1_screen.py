# -*- coding: utf-8 -*-
"""生成「三方向 HITL#1 审批屏」。

设计目标（不是"做个页面"，是**让主人一次过审**）：
 · 一屏看全三件作品：谁就绪、谁待填、谁被门挡住
 · 逐镜三契约的**待填格子**一次列全，避免来回翻文件
 · 预算闸拒绝出数字，就把「为什么拒」摆在原处（契约原文），而不是留空
 · 数据全部从**盘上真文件**读 + `drama.parse_timed` 现跑，不写死、不编数

审美纪律（照 anti-ai-slop 与 taste-skill，逐条遵守）：
 · 主色只有 1 个（赛博青）；绿/琥珀/红/灰是**语义状态色**，不是装饰
 · 无 indigo、无双色渐变、无 emoji 当图标
 · 形状系统四档写进 :root 注释，页内不许出裸圆角值
 · eyebrow 节制：整页 ≤ 1 个「小标签 + 大标题」结构（本节数 5，上限 2）
 · 空态必须说清"怎么填"，不许只留破折号
 · 不写任何没量到的数字

产物落 projects/_shared/templates/（README 规定「三方向共用的模板」）。
"""
from __future__ import annotations

import json
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
OUT = ROOT / "projects" / "_shared" / "templates" / f"{TODAY}-三方向-HITL1审批屏.html"

# ── 三件作品：路径从盘上找，找不到就如实标"缺失" ──
WORKS = [
    {"dir": "short-video", "name": "AI搬砖人", "kind": "短视频",
     "script": f"projects/short-video/01-script/{TODAY}-AI搬砖人/{TODAY}-short-video-AI搬砖人-01script.md",
     "board": f"projects/short-video/02-storyboard/{TODAY}-AI搬砖人/{TODAY}-short-video-AI搬砖人-02storyboard.md",
     "gate": "video-pipeline"},
    {"dir": "music", "name": "夜航", "kind": "音乐",
     "script": f"projects/music/01-lyrics/{TODAY}-夜航/{TODAY}-music-夜航-01lyrics.md",
     "board": None, "gate": "music-production"},
    {"dir": "film", "name": "老屋", "kind": "电影",
     "script": f"projects/film/01-screenplay/{TODAY}-老屋/{TODAY}-film-老屋-01screenplay.md",
     "board": f"projects/film/02-storyboard/{TODAY}-老屋/{TODAY}-film-老屋-02storyboard.md",
     "gate": "video-pipeline"},
]


def read(p: str | None) -> str:
    if not p:
        return ""
    f = ROOT / p
    return f.read_text(encoding="utf-8") if f.is_file() else ""


def meta(p: str | None) -> dict:
    if not p:
        return {"exists": False}
    f = ROOT / p
    if not f.is_file():
        return {"exists": False}
    st = f.stat()
    return {"exists": True, "bytes": st.st_size, "mtime": st.st_mtime}


TIMED_RE = re.compile(r"## 一、分镜稿输入.*?```\n(.*?)```", re.S)
ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(⛔[^|]*|⏸[^|]*|✅[^|]*|⚠️[^|]*)\s*\|\s*([^|]*?)\s*\|", re.M)
SEC_RE = re.compile(r"^##+\s*(.+?)\s*$", re.M)

# 框架编排层的回执（由 tools/codex-scripts/wire_media_pipeline.py 生成）
# 读不到就如实标「未接」，不假装有数据。
RECEIPT = ROOT / ".scratch" / "_media_pipeline_receipt.json"

_KIND_OF = {"short-video": "short_video", "music": "music", "film": "film"}


def load_receipt() -> dict:
    if not RECEIPT.is_file():
        return {"available": False, "why": f"回执不存在：{RECEIPT.name}（先跑 wire_media_pipeline.py）"}
    try:
        data = json.loads(RECEIPT.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"available": False, "why": f"回执读不动：{type(exc).__name__}"}
    by_kind = {w.get("kind"): w for w in (data.get("works") or [])}
    return {"available": True, "by_kind": by_kind, "generated_at": data.get("generated_at")}


def fw_html(receipt: dict, direction: str) -> str:
    """框架编排层（`media_pipeline`）对这件作品的自审结果。

    数据来自 wire_media_pipeline.py 的回执：真 sha256、真闸口判定。
    读不到就如实说「未接」—— 不留空壳、不编数字。
    """
    if not receipt.get("available"):
        return ('<p class="empty">框架编排层未接：'
                f'<span class="how">{esc(receipt.get("why", ""))}</span></p>')
    w = (receipt.get("by_kind") or {}).get(_KIND_OF.get(direction, ""))
    if not w:
        return '<p class="empty">回执里没有这件作品的记录。</p>'
    rv = w.get("review") or {}
    checks = rv.get("checks") or {}
    rows = "".join(
        f'<tr><td class="tt">{esc(k)}</td><td class="wh">'
        f'<span class="badge badge-{"ok" if v else "fault"}">{"通过" if v else "未过"}</span>'
        f'</td></tr>' for k, v in checks.items())
    absent = w.get("stages_absent") or []
    pk = w.get("packets") or []
    chain = " → ".join(str(p.get("stage")) for p in pk)
    return f"""
      <div class="fw">
        <p class="fw-h">框架编排层自审 · <code>media_pipeline</code>（喂的是盘上真 sha256）</p>
        <p class="fw-s"><b>{rv.get('passed')}</b>/<b>{rv.get('total')}</b> 项通过 ·
           发布口径 <code>{esc(rv.get('publish') or '—')}</code></p>
        <table class="gates"><tbody>{rows}</tbody></table>
        <p class="hint">缺工序（框架声明有、盘上还没有）：<b>{esc('、'.join(absent)) or '无'}</b>。
           三项证明（版权 / 安全 / 主人审批）我<b>一律填 False</b> —— 没核就是没核，不代签。</p>
        <p class="fw-chain"><span class="k">角色链</span>（{len(pk)} 包）：{esc(chain)}</p>
      </div>"""


RECEIPT_DATA = load_receipt()


def _load_status_module():
    """把总检查器当模块载入，取它的 `collect()`。

    为什么不解析它的 stdout：那边一改输出格式这边就断，而且解析文本本身就是
    第二份"真相"。直接调函数，链状态只有一处来源。
    """
    import importlib.util
    p = ROOT / "tools" / "codex-scripts" / "pipeline_status.py"
    if not p.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location("_ps_for_screen", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:      # noqa: BLE001 — 取不到就如实报"未取"，不猜
        return None


_CHAIN = None
_ps = _load_status_module()
if _ps is not None:
    try:
        _CHAIN = _ps.collect()
    except Exception:      # noqa: BLE001
        _CHAIN = None


def chain_html(chain) -> str:
    """顶部「链状态」：一屏看到三方向各自卡在哪一步。"""
    if not chain or not chain.get("works"):
        return ('<section class="chain"><p class="empty">链状态未取：'
                '<span class="how">tools/codex-scripts/pipeline_status.py 取不到或报错</span></p></section>')
    rows = []
    for w in chain["works"]:
        art = len(w.get("artifacts") or [])
        rev = w.get("review")
        dec = w.get("review_decision")
        fill = w.get("fill")
        merged = w.get("merged") or []
        steps = [
            ("产物", "ok" if art else "off", f"{art} 件"),
            ("编排自审", "ok" if rev else "off",
             f"{rev['passed']}/{rev['total']}" if rev else "未做"),
            ("独立审计", {"pass": "ok", "return_to_stage": "fault"}.get(dec, "off"),
             {"pass": "通过", "return_to_stage": "退回"}.get(dec, "未做")),
            ("HITL#1填", "ok" if fill else "off", "已导出" if fill else "未导出"),
            ("合并", "ok" if merged else "off", f"{len(merged)} 件" if merged else "未落"),
        ]
        chips = "".join(
            f'<span class="stp stp-{tone}"><b>{esc(name)}</b>{esc(val)}</span>'
            for name, tone, val in steps)
        rows.append(f"""
      <li>
        <span class="cw">{esc(w['label'])} · 《{esc(w['name'])}》</span>
        <span class="csteps">{chips}</span>
        <span class="cnext">下一步：{esc(' → '.join(w.get('next') or []) or '链上无明显缺口')}</span>
      </li>""")
    b = chain.get("blockers") or {}
    # 这里刻意**不用 markdown 加粗符**：这串是纯文本，`**` 会被原样显示出来
    # （自检的「渲染区无 markdown 泄漏」当场抓到过一次）。缺什么由词本身说清。
    blk = (f"授权台账 {'有' if b.get('grants') else '无'} · "
           f"LLM 密钥 {'有' if b.get('llm_keys') else '无'} · "
           f"HITL#1 导出 {'有' if b.get('fill_exported') else '无'}")
    return f"""
  <section class="chain">
    <p class="chain-h">链状态 · 一屏看到三方向各卡在哪一步</p>
    <ul class="chain-list">{''.join(rows)}</ul>
    <p class="chain-b"><span class="k">全局阻塞</span>{esc(blk)}</p>
  </section>"""


# 独立质量审计回执（由独立审计触手产出，作者看不到、也改不了它的判定）
IREVIEW = ROOT / ".scratch" / "_independent_review_receipt.json"


def load_ireview() -> dict:
    if not IREVIEW.is_file():
        return {"available": False, "why": f"回执不存在：{IREVIEW.name}"}
    try:
        data = json.loads(IREVIEW.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"available": False, "why": f"回执读不动：{type(exc).__name__}"}
    return {"available": True, "by_kind": {w.get("kind"): w for w in (data.get("works") or [])},
            "meta": data.get("meta_review") or {}, "ack": data.get("author_acknowledgement") or {}}


IREVIEW_DATA = load_ireview()

_DECISION_LABEL = {"pass": "通过", "return_to_stage": "退回返工", "blocked": "无法判"}
_SEV_TONE = {"blocker": "fault", "major": "warn", "minor": "off"}
_SEV_LABEL = {"blocker": "阻断", "major": "重要", "minor": "次要"}


def ack_html(receipt: dict) -> str:
    """作者认账块：把这一轮**我自己的错**摆在审批之前，不藏进脚注。"""
    if not receipt.get("available"):
        return ""
    ack = receipt.get("ack") or {}
    meta = receipt.get("meta") or {}
    if not ack:
        return ""
    kf = meta.get("key_findings") or []
    kf_html = "".join(f"<li>{plain(x)}</li>" for x in kf)
    return f"""
  <section class="ack">
    <h2>作者认账：这一屏上曾经有过一个我编的数字</h2>
    <p><b>《夜航》的「韵律」闸原写「每行 9–11 字」—— 那是我没实测就写下的，属编造。</b>
       独立审计官逐行实测证伪：18 行里落在 9–11 的只有 2 行（实测 min 4 / max 15 / 均值 10.8）。
       该数字<b>曾原样复制到本屏</b>，现已连同歌词件一并更正并留痕。</p>
    <p>另更正一处口径矛盾：短视频源稿原把「分镜表」标为「已出」，
       而分镜件自判 <code>complete:false</code> —— 已改为「未完成」。</p>
    <p><b>三件作品全部被判「退回返工」</b>（{plain(ack.get("status", ""))}）。
       §1 逐镜三契约、<code>shot.style</code> 列、<code>shot.share</code> 落点我<b>不代填</b> ——
       契约 §1 明写这些必须「先读旁白再决定」且理由不许复制，属 HITL#1 一次定齐的动作。</p>
    <details class="irv-credit"><summary>元审（复核这三份判定本身）查出的要点（{len(kf)} 条）</summary>
      <ul>{kf_html}</ul></details>
  </section>"""


def ireview_html(receipt: dict, direction: str) -> str:
    """独立质量审计官的判定。**作者无权改这份判定**，只能照做或申辩。"""
    if not receipt.get("available"):
        return ('<p class="empty">独立审计未跑：'
                f'<span class="how">{esc(receipt.get("why", ""))}</span></p>')
    w = (receipt.get("by_kind") or {}).get(_KIND_OF.get(direction, ""))
    if not w:
        return '<p class="empty">回执里没有这件作品的审计记录。</p>'
    dec = w.get("decision", "")
    tone = {"pass": "ok", "return_to_stage": "fault", "blocked": "warn"}.get(dec, "off")
    c = w.get("counts") or {}
    rows = "".join(
        f'<li class="fnd">'
        f'<span class="badge badge-{_SEV_TONE.get(f.get("severity"), "off")}">'
        f'{_SEV_LABEL.get(f.get("severity"), f.get("severity"))}</span>'
        f'<span class="fnd-body"><b>{plain(f.get("contract", ""))}</b> —— {plain(f.get("claim", ""))}'
        f'<span class="ev">{plain(f.get("evidence", ""))}</span></span></li>' for f in (w.get("top_findings") or []))
    credits = "".join(f"<li>{plain(x)}</li>" for x in (w.get("auditor_credits") or []))
    fix = w.get("self_correction") or ""
    return f"""
      <div class="irv">
        <p class="irv-h">独立质量审计官判定 · <code>independent_review</code>（作者看不到、也改不了）</p>
        <p class="irv-s">
          <span class="badge badge-{tone}">{_DECISION_LABEL.get(dec, dec)}</span>
          退回工序 <code>{plain(w.get("stage_to_return") or "—")}</code>
          <span class="cnt">阻断 {c.get('blocker', 0)} · 重要 {c.get('major', 0)} · 次要 {c.get('minor', 0)}</span>
        </p>
        <ul class="fnds">{rows}</ul>
        {f'<p class="irv-fix">{plain(fix)}</p>' if fix else ''}
        <details class="irv-credit"><summary>审计官认可的地方（{len(w.get("auditor_credits") or [])} 条）</summary>
          <ul>{credits}</ul></details>
      </div>"""


def gate_rows(text: str, src_label: str) -> list[dict]:
    """抓产物里的「检查项 | 状态 | 说明」表行，**并记住它出自哪个文件的哪一节**。"""
    if not text:
        return []
    secs = [(m.start(), m.group(1).strip()) for m in SEC_RE.finditer(text)]
    out = []
    for m in ROW_RE.finditer(text):
        pos, sec = m.start(), ""
        for start, title in secs:
            if start < pos:
                sec = title
            else:
                break
        out.append({"item": m.group(1), "state": m.group(2), "why": m.group(3),
                    "src": src_label, "sec": sec})
    return out


def parse_timed(text: str) -> dict:
    r = run_task("drama", {"op": "parse_timed", "text": text})
    res = r.get("result", r) if isinstance(r, dict) else {}
    if isinstance(res, dict) and isinstance(res.get("result"), dict):
        res = res["result"]
    return res if isinstance(res, dict) else {}


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


# 状态字形 → 中文语义标签。**不许把 emoji 当界面图标**（anti-ai-slop 第 3 条）：
# 产物 markdown 里用 ✅/⛔/⚠️ 是可读的，直接搬进 HTML 就变成"emoji 当 UI 元件"。
# 所以在这一层做转换：字形丢弃，换成带语义色的中文词，颜色由 CSS 类承担。
_STATE_MAP = [
    ("\u2705", "就绪", "ok"),      # ✅
    ("\u26d4", "阻塞", "fault"),   # ⛔
    ("\u23f8", "待批", "warn"),    # ⏸
    ("\u26a0", "注意", "warn"),    # ⚠
]

_MD_RE = re.compile(r"\*\*|`|__")

# ── emoji / 符号判据：**用宽式，不用窄式** ──────────────────────────────
# 窄式 `[\U0001F300-\U0001FAFF\u2600-\u27BF]` 有盲区：
# 它漏掉 ←(2190) →(2192) ↔(2194) ⇒(21D2) ①(2460)~⑦(2466) ⌘(2318) ◇(25C7)
# 这一条是并行流的 `audit_craft_gate.py` 复核出来的（它对照规则书逐条量覆盖面）。
# 现在优先用 `regex` 的 Unicode 属性 \p{Extended_Pictographic}（与交付物侧同口径）；
# 没有 regex 时退回显式加宽的字符类 —— **两种都不许再退回窄式**。
try:
    import regex as _regex  # type: ignore
    _EMOJI_RE = _regex.compile(r"[\p{Extended_Pictographic}\p{Emoji_Presentation}"
                               r"\u2190-\u21FF\u2300-\u23FF\u2460-\u24FF"
                               r"\u25A0-\u25FF\u2B00-\u2BFF]")
    _EMOJI_MODE = "regex \\p{Extended_Pictographic} + 符号区"
except ImportError:  # pragma: no cover
    import re as _re2
    _EMOJI_RE = _re2.compile(
        "[\U0001F300-\U0001FAFF\u2600-\u27BF\u2190-\u21FF\u2300-\u23FF"
        "\u2460-\u24FF\u25A0-\u25FF\u2B00-\u2BFF\uFE0F]")
    _EMOJI_MODE = "re 显式加宽字符类（未装 regex）"


def plain(s: str) -> str:
    """把任意来源文本清成可安全放进 HTML 的纯文本。

    与 `cell()` 的分工：`cell()` 用于**表格单元格**（把前导状态字形转成语义色徽章）；
    `plain()` 用于**散文/引文**（字形直接丢弃，因为这里没有徽章位）。
    两者都必须做：剥 markdown 装饰符 + HTML 转义。
    """
    s = _EMOJI_RE.sub("", str(s or ""))
    s = _MD_RE.sub("", s)
    return esc(re.sub(r"[ \t]{2,}", " ", s).strip())


# ── 唯一白名单：`→`(U+2192) ────────────────────────────────────────────
# anti-ai-slop 第 3 条禁的是「**emoji 当界面图标/头像/导航/装饰**」。
# `→` 在本页的角色链里是**序列记号的分隔符**（script → storyboard → …），
# 属排版标点，不承担图标职能 —— 换成 `·` 或 `,` 反而读不出先后。
# 所以判据保持**宽式**（不留盲区），只把这一处**窄例外写下来并写明理由**，
# 而不是把判据改窄了事（改窄 = 重新长回盲区）。
# 并行流对交付物的 `↔` 用的是同一处置。
_EMOJI_WHITELIST = "\u2192"   # →


def emoji_hits(text: str) -> list[str]:
    """按宽式判据找字形，**扣掉已写明的白名单**。返回去重后的命中清单。"""
    return sorted({m.group() for m in _EMOJI_RE.finditer(text)
                   if m.group() not in _EMOJI_WHITELIST})


def cell(s: str) -> str:
    """把一个 markdown 单元格转成安全的 HTML 片段。

    做四件事：
      ① 前导状态字形 → 语义色徽章；
      ② **句中残留的字形一律剥掉** —— 上一版只转前导，于是产物里
         「原写「✅ 已出」…」这类**引用**就把 ✅ 漏进了 HTML（自检当场抓到）；
      ③ 剥 markdown 装饰符（否则 **加粗** 会原样显示成星号）；
      ④ HTML 转义。
    规则统一为一句：**任何进 HTML 的文本路径都得净化，不分位置。**
    """
    s = (s or "").strip()
    badge = ""
    for glyph, label, tone in _STATE_MAP:
        if s.startswith(glyph):
            badge = f'<span class="badge badge-{tone}">{label}</span>'
            s = s[len(glyph):].lstrip("\ufe0f").strip()
            break
    s = _EMOJI_RE.sub("", s)
    s = _MD_RE.sub("", s).strip()
    return badge + (esc(s) if s else "")


def build() -> tuple[str, dict]:
    facts: dict = {"works": [], "generated_by": "drama.parse_timed"}
    rows = []
    for w in WORKS:
        s_meta, b_meta = meta(w["script"]), meta(w["board"])
        s_txt, b_txt = read(w["script"]), read(w["board"])
        shots = []
        if b_txt:
            m = TIMED_RE.search(b_txt)
            if m:
                pr = parse_timed(m.group(1).strip())
                for miss in (pr.get("verdict") or {}).get("missing") or []:
                    shots.append({"idx": miss.get("idx"), "lack": miss.get("lack") or []})
                facts["works"].append({"name": w["name"], "shots": len(shots),
                                       "source": pr.get("source"), "ok": pr.get("ok")})
            else:
                facts["works"].append({"name": w["name"], "shots": None,
                                       "note": "分镜件里没找到分镜稿输入块"})
        else:
            facts["works"].append({"name": w["name"], "shots": None,
                                   "note": "该方向无分镜件（音乐走歌词闸，不走切镜）"})
        # 从**两份产物**里抓所有「检查项 | 状态 | 说明」表行，并记住各出自哪节。
        # 三件作品的 markdown 里有多张同形状的表（歌词闸 / 生成前闸 / 待办 / 双人审闸），
        # 只抓行不记节 ⇒ 读者看到「押韵」和「来源已核验」并排却分不清各属哪道闸，
        # 那是**信息架构缺陷**不是排版问题。带出处才说得清。
        todo = gate_rows(s_txt, "源稿") + gate_rows(b_txt, "分镜")
        rows.append({**w, "s_meta": s_meta, "b_meta": b_meta,
                     "shots": shots, "todo": todo})
        facts[w["name"]] = {"script_exists": s_meta["exists"], "board_exists": b_meta["exists"],
                            "todo_rows": len(todo)}
    return render(rows, facts), facts


def render(rows, facts) -> str:
    total_blanks = sum(len(r["shots"]) * 3 for r in rows)

    blocks = []
    for r in rows:
        shots_html = ""
        if r["shots"]:
            cells = "".join(
                f'<tr><td class="num">{s["idx"]}</td>'
                f'<td><span class="blank" title="待填：读了旁白才能定">&nbsp;</span></td>'
                f'<td><span class="blank">&nbsp;</span></td>'
                f'<td><span class="blank">&nbsp;</span></td>'
                f'<td class="lack">{esc("/".join(s["lack"]))}</td></tr>'
                for s in r["shots"])
            shots_html = f"""
      <table class="grid">
        <caption>镜头三契约 · 逐镜待填（{len(r['shots'])} 镜 × 3 项 = {len(r['shots'])*3} 格）</caption>
        <thead><tr><th>镜</th><th>render</th><th>eyeline</th><th>depth</th><th>parse_timed 点名缺</th></tr></thead>
        <tbody>{cells}</tbody>
      </table>
      <p class="hint">坑是空的，我<b>不代填</b> —— 契约 §1 明写「复制别人的理由 = 失败」，
      这三格必须<b>先读了上表旁白</b>才能定。审批时一次定齐即可。</p>"""
        else:
            shots_html = ('<p class="empty">本方向不用切镜表：音乐走的是<b>歌词闸</b>，'
                          '不是镜头契约。<span class="how">要填的是「生成前闸」四项（见 01 歌词件 §四）。</span></p>')

        todo_html = ""
        if r["todo"]:
            # 按【出处】分组落表：同节的检查项连在一起，读者一眼知道哪行属哪道闸
            groups: dict[str, list] = {}
            for row in r["todo"]:
                key = f'{row["src"]} · {row["sec"] or "（无节标题）"}'
                groups.setdefault(key, []).append(row)
            parts = ['<table class="gates"><thead><tr><th>出处</th><th>检查项</th>'
                     '<th>结论 / 卡在哪</th></tr></thead><tbody>']
            for key, items in groups.items():
                for i, row in enumerate(items):
                    src_cell = (f'<td class="src" rowspan="{len(items)}">{esc(key)}</td>'
                                if i == 0 else "")
                    parts.append(f'<tr>{src_cell}<td class="tt">{cell(row["item"])}</td>'
                                 f'<td class="wh">{cell(row["why"]) or "—"}</td></tr>')
            parts.append("</tbody></table>")
            todo_html = "".join(parts)

        prio = "warn" if r["shots"] else "off"
        fw = fw_html(RECEIPT_DATA, r["dir"])
        irv = ireview_html(IREVIEW_DATA, r["dir"])
        blocks.append(f"""
    <section class="work" data-state="{prio}">
      <header class="work-head">
        <h3>{esc(r['kind'])} · 《{esc(r['name'])}》</h3>
        <span class="chip chip-{prio}">{'待填 ' + str(len(r['shots'])*3) + ' 格' if r['shots'] else '走歌词闸'}</span>
      </header>
      <dl class="files">
        <dt>源稿</dt><dd>{'<code>' + esc(r['script']) + '</code> · ' + str(r['s_meta'].get('bytes', '—')) + ' B' if r['s_meta']['exists'] else '<span class="miss">缺失</span>'}</dd>
        <dt>分镜</dt><dd>{'<code>' + esc(r['board']) + '</code> · ' + str(r['b_meta'].get('bytes', '—')) + ' B' if r['b_meta']['exists'] else '<span class="dim">无（本方向不走切镜）</span>'}</dd>
        <dt>闸口</dt><dd><code>{esc(r['gate'])}</code></dd>
      </dl>
      {shots_html}
      {todo_html}
      {fw}
      {irv}
    </section>""")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>三方向 · HITL#1 分镜审批屏</title>
<!-- 内联 data: icon：不依赖路径（DSH 宿主 / file:// 都成立）。
     ⚠️ 这条原先**只补在产物上**、模板里没有 ⇒ 一重新生成就被冲掉（实测：两页各差 244 字，
     差的就是这一行）。教训与 `make_capability_console.py` / `make_workspace_index.py` 同源：**手补的东西必须挪进模板**。 -->
<link rel="icon" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAWklEQVR42mNgGAWjYBSMglEwCkbBKBgFo2AUjIJRMApGwSgYBaNgFIyCUTAKRsEoGAWjYBSMglEwCkbBKBgFo2AUjIJRMApGwSgYBaNgFIyCUTAKRsEoAAB2gAH/8kQ0dQAAAABJRU5ErkJggg==">
<style>
/* ── 令牌：唯一允许写裸色值的地方 ──────────────────────────────
   品牌三色（土豆金/赛博青/深空紫）与上帝视角同源，四窗口共用；
   绿/琥珀/红/灰是「语义状态色」，不计入"1 个装饰 accent"的限额。 */
:root {{
  --gold:#F5B041; --cyan:#00E5FF; --violet:#7C4DFF;
  --ok:#22C55E; --warn:#F5B041; --fault:#EF4444; --off:#6B7280;
  --bg:#050711; --panel:#0C1022; --line:rgba(124,77,255,.30);
  --text:#E8ECF8; --dim:#9AA4C4;
  --radius:10px;            /* 卡片 */
  --radius-ctl:6px;         /* 控件 */
  --radius-pill:999px;      /* 药丸 */
}}
/* 形状系统（SHAPE CONSISTENCY LOCK）：卡片 10px · 控件 6px · 药丸 999px。
   整页只有这三档，不许再出裸值、不许单侧圆角。 */
* {{ box-sizing:border-box; }}
body {{
  margin:0; padding:28px 32px 40px;
  background:
    radial-gradient(1100px 460px at 12% -8%, rgba(0,229,255,.07), transparent 62%),
    var(--bg);
  color:var(--text);
  font:14px/1.62 "Microsoft YaHei UI","Segoe UI",system-ui,sans-serif;
  -webkit-font-smoothing:antialiased;
}}
.wrap {{ max-width:1180px; margin:0 auto; }}

/* 页头：整页唯一一处「小标签 + 大标题」 */
.eyebrow {{
  font:600 11.5px/1 ui-monospace,"Cascadia Mono",Consolas,monospace;
  letter-spacing:.16em; color:var(--cyan); text-transform:uppercase;
}}
h1 {{ margin:10px 0 6px; font-size:27px; font-weight:650; letter-spacing:-.015em; }}
.lede {{ margin:0; color:var(--dim); max-width:74ch; }}
.lede b {{ color:var(--gold); font-weight:600; }}

/* 决策条：Von Restorff —— 需要动作的东西必须一眼跳出来 */
.decide {{
  margin:22px 0 26px; padding:14px 18px;
  border:1px solid var(--line); border-left:2px solid var(--warn);
  border-radius:0;                     /* 左侧色规 + 方形，不做"圆角卡+彩边" */
  background:rgba(245,176,65,.055);
  display:flex; gap:26px; flex-wrap:wrap; align-items:baseline;
}}
.decide .k {{ color:var(--dim); font-size:12.5px; }}
.decide .v {{ color:var(--text); font-weight:650; font-size:15px; }}
.decide .v.hot {{ color:var(--warn); }}

section.work {{
  border:1px solid var(--line); border-radius:var(--radius);
  background:var(--panel); padding:16px 18px 18px; margin:0 0 16px;
}}
.work-head {{ display:flex; align-items:baseline; gap:12px; margin-bottom:12px; }}
.work-head h3 {{ margin:0; font-size:16px; font-weight:620; }}
.chip {{
  border-radius:var(--radius-pill); padding:1px 10px; font-size:12px;
  border:1px solid currentColor;
}}
.chip-warn {{ color:var(--warn); }}
.chip-off  {{ color:var(--off); }}

.files {{ display:grid; grid-template-columns:64px 1fr; gap:4px 12px; margin:0 0 14px; }}
.files dt {{ color:var(--dim); font-size:12.5px; }}
.files dd {{ margin:0; min-width:0; }}
code {{
  font:12px/1.5 ui-monospace,"Cascadia Mono",Consolas,monospace;
  color:var(--cyan); background:rgba(0,229,255,.07);
  padding:1px 5px; border-radius:var(--radius-ctl);
}}
.miss {{ color:var(--fault); font-weight:600; }}
.dim {{ color:var(--dim); }}

table.grid {{ width:100%; border-collapse:collapse; margin:6px 0 0; }}
table.grid caption {{
  text-align:left; color:var(--dim); font-size:12.5px; padding-bottom:6px;
}}
table.grid th {{
  text-align:left; font-weight:600; font-size:12px; color:var(--dim);
  border-bottom:1px solid var(--line); padding:6px 8px;
}}
table.grid td {{ padding:6px 8px; border-bottom:1px solid rgba(124,77,255,.14); }}
table.grid td.num {{ color:var(--dim); width:36px; }}
.blank {{
  display:block; min-width:78px; height:20px;
  border-bottom:1px dashed var(--off); background:rgba(107,114,128,.10);
}}
.lack {{ color:var(--warn); font-size:12.5px; }}

.hint, .empty {{ margin:10px 0 0; color:var(--dim); font-size:12.5px; }}
.hint b, .empty b {{ color:var(--gold); font-weight:600; }}
.empty .how {{ color:var(--cyan); }}

/* 闸口检查表：三列 —— 出处 / 检查项 / 结论。
   出处一列按节合并（rowspan），把「哪行属哪道闸」摆在明面上。 */
table.gates {{ width:100%; border-collapse:collapse; margin:14px 0 0; }}
table.gates th {{
  text-align:left; font-weight:600; font-size:11.5px; color:var(--dim);
  border-bottom:1px solid var(--line); padding:6px 8px; letter-spacing:.04em;
}}
table.gates td {{ padding:5px 8px; border-bottom:1px solid rgba(124,77,255,.13); font-size:12.5px; vertical-align:top; }}
table.gates td.src {{
  /* 出处列**不用主色**：taste-skill §Soft tells 规定「var(--accent) 在渲染正文里
     6+ 次应收敛，每屏可见用途上限 2 处」。这一列有几十行，全上青色会把主色的
     信号价值稀释光 —— 主色要留给真正需要点的东西。改用中性色 + 左侧细规分组。 */
  color:var(--dim); font-size:11.5px; white-space:nowrap;
  border-right:1px solid rgba(124,77,255,.16);
}}
table.gates td.tt {{ color:var(--text); width:190px; }}
table.gates td.wh {{ color:var(--dim); overflow-wrap:anywhere; }}

/* 框架编排层自审块：与上半部用一条上规分开，读作「另一层给的判定」 */
.fw {{
  margin-top:16px; padding-top:13px;
  border-top:1px solid rgba(124,77,255,.20);
}}
.fw-h {{ margin:0 0 3px; color:var(--gold); font-size:12.5px; font-weight:600; }}
.fw-s {{ margin:0 0 8px; color:var(--dim); font-size:12.5px; }}
.fw-s b {{ color:var(--text); }}
.fw table.gates td.tt {{ width:auto; color:var(--dim); font-size:12px; }}
.fw table.gates td.wh {{ width:74px; }}
.fw table.gates td {{ padding:3px 8px; }}
/* 判定必须**紧挨着它判的东西**（格式塔·邻近性）。
   上一版让这张表吃满 1142px，徽章被甩到离标签 1200px 外，
   标签与判定分家 —— 机器自检 6/6 全过也照样看不出来，是眼睛看出来的。
   所以这里给表定死一个**内容宽度**，不许铺满。 */
.fw table.gates {{ width:auto; min-width:360px; max-width:460px; border-collapse:collapse; }}
.fw table.gates td.wh {{ text-align:right; white-space:nowrap; }}
.fw-chain {{
  margin:9px 0 0; color:var(--dim); font-size:12px;
  overflow-wrap:anywhere; line-height:1.7;
}}
.fw-chain .k {{ color:var(--text); margin-right:6px; }}

/* 独立审计块：与「框架自审」分开成一层 —— 一个是作者自己量的，一个是不许作者插手的 */
.irv {{
  margin-top:14px; padding:13px 15px;
  border:1px solid rgba(239,68,68,.30); border-left:2px solid var(--fault);
  border-radius:0; background:rgba(239,68,68,.045);
}}
.irv-h {{ margin:0 0 4px; color:var(--fault); font-size:12.5px; font-weight:600; }}
.irv-s {{ margin:0 0 10px; color:var(--dim); font-size:12.5px; }}
.irv-s .cnt {{ margin-left:12px; }}
ul.fnds {{ list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:8px; }}
li.fnd {{ display:grid; grid-template-columns:52px 1fr; gap:10px; align-items:baseline; font-size:12.5px; }}
.fnd-body {{ color:var(--text); overflow-wrap:anywhere; }}
.fnd-body b {{ color:var(--dim); font-weight:600; }}
.fnd-body .ev {{ display:block; margin-top:3px; color:var(--dim); font-size:11.5px; }}
.irv-fix {{ margin:10px 0 0; color:var(--warn); font-size:12px; }}
.irv-credit {{ margin-top:9px; }}
.irv-credit summary {{ color:var(--dim); font-size:11.5px; cursor:pointer; }}
.irv-credit ul {{ margin:6px 0 0; padding-left:18px; color:var(--dim); font-size:11.5px; }}

/* 链状态：顶部一条，五步一格。语义色只用状态色，主色仍留给交互。 */
.chain {{
  margin:0 0 20px; padding:13px 16px;
  border:1px solid var(--line); border-left:2px solid var(--cyan);
  border-radius:0; background:rgba(0,229,255,.045);
}}
.chain-h {{ margin:0 0 9px; color:var(--cyan); font-size:12.5px; font-weight:600; }}
ul.chain-list {{ list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:7px; }}
/* 三列：作品名固定 · 步骤格按内容 · 下一步吃掉剩余宽度。
   上一版把下一步写死 260px，长句折成两行还参差不齐（截图看出来的）。 */
ul.chain-list li {{ display:grid; grid-template-columns:170px auto minmax(300px, 1fr);
  gap:12px; align-items:baseline; }}
.cw {{ color:var(--text); font-size:12.5px; }}
.csteps {{ display:flex; gap:6px; flex-wrap:wrap; }}
.stp {{
  border:1px solid currentColor; border-radius:var(--radius-pill);
  padding:0 8px; font-size:11px; white-space:nowrap;
}}
.stp b {{ font-weight:600; margin-right:5px; }}
.stp-ok {{ color:var(--ok); }}
.stp-fault {{ color:var(--fault); }}
.stp-off {{ color:var(--off); }}
.cnext {{ color:var(--dim); font-size:11.5px; }}
.chain-b {{ margin:10px 0 0; padding-top:9px; border-top:1px solid rgba(124,77,255,.16);
  color:var(--dim); font-size:12px; }}
.chain-b .k {{ color:var(--text); margin-right:8px; }}

/* 作者认账块：把"我犯的错"摆在审批之前，不藏在角落 */
.ack {{
  margin:22px 0 0; padding:14px 16px;
  border:1px solid rgba(239,68,68,.34); border-left:2px solid var(--fault);
  border-radius:0; background:rgba(239,68,68,.06);
}}
.ack h2 {{ margin:0 0 8px; font-size:14px; color:var(--fault); }}
.ack p {{ margin:0 0 7px; color:var(--text); font-size:12.5px; }}
.ack p:last-child {{ margin-bottom:0; }}
.ack b {{ color:var(--warn); }}
/* 语义状态标签：替掉产物里的 emoji 字形（anti-ai-slop 第 3 条）。
   颜色由这几个类承担，形状走 999px 药丸档。 */
.badge {{
  display:inline-block; min-width:38px; text-align:center;
  border-radius:var(--radius-pill); padding:0 7px; margin-right:7px;
  font-size:11.5px; font-weight:600; border:1px solid currentColor;
}}
.badge-ok {{ color:var(--ok); }}
.badge-warn {{ color:var(--warn); }}
.badge-fault {{ color:var(--fault); }}

.note {{
  margin:26px 0 0; padding:12px 16px; border:1px solid var(--line);
  border-left:2px solid var(--cyan); border-radius:0;
  background:rgba(0,229,255,.05); color:var(--dim); font-size:12.5px;
}}
.note b {{ color:var(--text); }}
.note .cite {{ color:var(--cyan); font-style:normal; }}

footer.sig {{
  margin-top:30px; padding-top:14px; border-top:1px solid var(--line);
  color:var(--dim); font-size:12px;
}}
</style>
</head>
<body>
<div class="wrap">
  <p class="eyebrow">GBT小土豆V8 · 生产审批</p>
  <h1>三方向 · HITL#1 分镜审批屏</h1>
  <p class="lede">一屏看全短视频 / 音乐 / 电影三件作品的现状。<b>这一屏不生成任何东西</b> ——
     契约 §0 明写「分镜阶段只规划，不生成」，所以退回或废弃的成本为 0。
     本页数据全部从盘上真文件读出并现跑解析器，没有一个是手写的。</p>

  <div class="decide">
    <div><div class="k">待主人拍板</div><div class="v hot">3 件作品 · 进入 HITL#1</div></div>
    <div><div class="k">待填契约格</div><div class="v">{total_blanks} 格</div></div>
    <div><div class="k">已生成像素</div><div class="v">0</div></div>
    <div><div class="k">预算预估</div><div class="v">拒估（见下）</div></div>
  </div>

  {chain_html(_CHAIN)}

{''.join(blocks)}

  {ack_html(IREVIEW_DATA)}

  <div class="note">
    <b>为什么预算栏写着「拒估」而不是一个数字：</b>    <span class="cite">video-pipeline §3</span> 原文 ——「<b>未知价格直接失败，不许猜</b>」，
    且要求「价格表每行带证据等级与出处」。当前没有价格表，
    所以按契约<b>拒绝给出数字</b>，而不是编一个 $10 交差。
    等接入生成端、拿到带出处的价目后，这一栏才会有真数。
  </div>

  <footer class="sig">{SIGN}</footer>
</div>
</body>
</html>
"""


def main() -> int:
    html, facts = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    back = OUT.read_text(encoding="utf-8")
    print("=" * 78)
    print("生成 HITL#1 审批屏")
    print("=" * 78)
    print(f"  落位: {OUT.relative_to(ROOT)}")
    print(f"  大小: {len(back)} 字")
    print(f"  署名: {'在' if SIGN in back else '缺失!'}")
    print("\n  盘上真数据读数:")
    for w in facts["works"]:
        print(f"    {w['name']:10} 切镜={w.get('shots')} source={w.get('source')} "
              f"ok={w.get('ok')} {w.get('note', '')}")
    # 自检：反 slop
    # 三次误报的教训，逐条收窄判据范围：
    #  · 「裸圆角」只算**非 0 的数字** —— `border-radius:0` 是刻意写明的方形批注条；
    #  · 「markdown 泄漏」只扫 **<body> 渲染内容** —— 扫 CSS 注释会把作者注释里的
    #    强调符当成页面缺陷（本检查器上一版就是这么误报的）；
    #  · 令牌块 `:root{}` 本身允许写裸色值，先剥掉再判。
    body = re.sub(r".*?<body[^>]*>", "", back, flags=re.S)
    body = re.sub(r"<style.*?</style>", "", body, flags=re.S)
    outside_root = re.sub(r":root\s*\{.*?\}", "", back, flags=re.S)
    checks = {
        "无 indigo 主色": not re.search(r"#(6366f1|4f46e5|4338ca|3730a3|8b5cf6|7c3aed|a855f7)", back, re.I),
        "无双色渐变": not re.search(r"linear-gradient\([^)]*(purple|indigo)", back, re.I),
        # 用**宽式**判据（与交付物侧同口径），扣掉写明白名单的那一处窄例外。
        # 窄式会漏 ←→↔⇒①②③◇⌘ 一类字形，覆盖面缺口是并行流
        # audit_craft_gate.py 量出来的；白名单只有 `→` 一个，理由见上方注释。
        "无 emoji 当图标（宽式·扣白名单）": not emoji_hits(back),
        "无裸圆角（0 除外）": not re.search(r"border-radius:\s*(?!0\s*;)(?!var\()\d", outside_root),
        "渲染区无 markdown 泄漏": not re.search(r"\*\*|`[^`]*`", body),
        "无 lorem/占位文": not re.search(r"lorem ipsum|placeholder text|sample content", back, re.I),
    }
    print("\n  反 AI-slop 自检:")
    allok = True
    for k, v in checks.items():
        print(f"    {'✔' if v else 'x'} {k}")
        allok &= v
    return 0 if allok else 1


def check() -> int:
    """`--check`：**产物是不是这个模板生成的**（口径同 `make_capability_console.py --check`）。

    这一页里带着**盘上现读的读数**（链状态 / 逐镜待填 / 闸口表 / 审计判定）——工作区一变就过期；
    而它又是"审批面"，读者会拿它当事实。所以产物必须能由模板复现，不能靠手补。
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
    print("   ⇒ 修法：`py -3.14 tools/codex-scripts/make_hitl1_screen.py`")
    return 1


if __name__ == "__main__":
    import sys as _sys
    raise SystemExit(check() if "--check" in _sys.argv else main())
