# -*- coding: utf-8 -*-
"""AI 工作可视化面板（ai-board）—— **一页看全：谁是谁、什么职位、在休息还是在干活**。

主人令（2026-10-09，逐字）：
  「整个框架所有的编程职业在一页上面做出**每个AI在执行任务的可视化面板**，谁是谁什么职位，
    正在休息还是在工作都要看得见，这样永远不会出现像你们部署项目一样扫描一扫都是漏洞和红黄色警报，
    不扫的话还不知道有什么」

数据来源（全部现读，不编）：
  · state/action-ledger.jsonl  —— 最近动作（谁在干活、干的是什么）
  · gbt_allinone/caps_registry  —— 30 个能力域（工作位）
  · vaults/agency_tentacles     —— 职业册（19 个师 × 272 个职业）
  · state/capability-audit.json —— 报警（红黄一体，不藏）

口径：**近 30 分钟内有动作 ⇒ 工作中**，否则 ⇒ 休息中；两侧都要显示（休息的也要看得见）。

出口清洗（2026-10-26 补，原先是**完全没洗**）：
  本页有三类字段是从别的台账**原样搬来**的 —— 云插件 doctrine、最近动作、缺键计数（None）。
  主人令：页面产物（界面 + 注释）零 emoji。清洗放在 `build_data()` 出口：一处清、两边净
  （页面与 `ai-board-data.js` 是同一份 d，不留两套文本）。细则写在 `_c` / `h` 的注释里。
  实测漏网：`state/cloud_plugins.json` 的 doctrine 原文带 🔴 与 markdown 粗体，直接搬进页面，
  导致 `test_pages_no_emoji` ① 与 `test_page_grid` ④ 双红（ai-board/index.html L49 两处）。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))   # 同目录的 _page_text
from _page_text import clean as _c, scrub as _scrub, esc  # noqa: E402
from _page_emit import clean_html  # noqa: E402
OUT_HTML = ROOT / "holo_pet_w3" / "ai-board" / "index.html"
OUT_JS = ROOT / "holo_pet_w3" / "ai-board" / "ai-board-data.js"
LEDGER = ROOT / "state" / "action-ledger.jsonl"
AUDIT = ROOT / "state" / "capability-audit.json"
WORK_WINDOW_S = 1800

# ── 出口清洗：唯一实现在 `_page_text.py`，别在这里再抄一份 ────────────────────────
# 本页有三个字段是**从别处原样搬来**的，它们的格式不归本页管：
#   · 云插件 doctrine（state/cloud_plugins.json）—— 原文里就带 🔴、markdown 粗体与反引号
#   · 最近动作（state/action-ledger.jsonl 的 what）—— 谁的台账里带记号就原样进来
#   · 计数缺键时是 None —— 直接插值会在界面上印出字面 `None`
# 主人令（2026-10-26）：页面产物（界面 + 注释）零 emoji。
# 🔴 为什么在出口清、而不是渲染时清：`ai-board-data.js` 是同一份 d 的 JSON 落盘。
#    只在 render() 里清 ⇒ 页面干净了、JS 里还是带记号的原文 = 同一份数据两套文本，
#    正是本仓最贵的教训（"两处判断"）。在出口清，两边必然一致。
# 🔴 反过来也要说清：**源文里我自己的 `**` 不是"外来格式"，那是错字** —— 已从字面量
#    （含 CSS 注释）里直接去掉；清洗只是兜底。别因为有了清洗就继续在中文散文里写 markdown。


def _rows() -> list:
    if not LEDGER.is_file():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def build_data() -> dict:
    from gbt_allinone.caps_registry import BENIGN_CAPS
    from collections import Counter
    dom = Counter((v or {}).get("domain") for v in BENIGN_CAPS.values())
    rows = _rows()
    now = time.time()
    # 每人（域）最近一次动作
 # 2026-10-09 修：第一版拿**域名**去撞动作文本 ⇒ 目标多是文件路径，撞不上 ⇒ 全判"休息中"（30/30）。
    #    正解：拿**该域下的能力位名**去撞（动作里常常点名能力位/件名），撞不上再看域名。
    dom2caps = {}
    for kind, v in BENIGN_CAPS.items():
        dom2caps.setdefault((v or {}).get("domain"), []).append(kind.lower())
    last = {}
    for r in rows:
        blob = (str(r.get("target") or "") + " " + str(r.get("what") or "") + " "
                + str(r.get("evidence") or "")).lower()
        at = str(r.get("at") or "")
        try:
            ts = time.mktime(time.strptime(at, "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            ts = 0
        for d, kinds in dom2caps.items():
            if not d:
                continue
            hit = (d in blob) or any(k in blob for k in kinds)
            if hit and (d not in last or ts > last[d][0]):
                last[d] = (ts, r.get("what"), at)
 # 2026-10-11 加：**每位近窗口内的动作数** —— 这就是"这一根触手在动"的进度感。
    #    （原来只有"最近一次动作"，看不出它干了多少。）
    dom_acts = {}
    for r in rows:
        blob = (str(r.get("target") or "") + " " + str(r.get("what") or "") + " "
                + str(r.get("evidence") or "")).lower()
        at = str(r.get("at") or "")
        try:
            ts = time.mktime(time.strptime(at, "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            ts = 0
        if (now - ts) > WORK_WINDOW_S:
            continue
        for d, kinds in dom2caps.items():
            if not d:
                continue
            if (d in blob) or any(k in blob for k in kinds):
                dom_acts[d] = dom_acts.get(d, 0) + 1

    people = []
    for d, n in dom.most_common():
        l = last.get(d)
        working = bool(l and (now - l[0]) <= WORK_WINDOW_S)
        people.append({"职位": d, "工作位": n,
                       "状态": "工作中" if working else "休息中",
                       "最近动作": (l[1] if l else None),
                       "最近时刻": (l[2] if l else None),
                       "窗口内动作数": dom_acts.get(d, 0)})
    al = {}
    try:
        d = json.loads(AUDIT.read_text(encoding="utf-8"))
        items = d.get("items") or []
        al = {"断连缺失": len([i for i in items if i.get("state") in ("断连", "缺失")]),
              "按需未启用": len([i for i in items if i.get("state") == "按需未启用"])}
    except (OSError, ValueError):
        al = {"断连缺失": None}
 # 2026-10-11 加：**云插件那条线**（主人令：「触手运行自身携带云插件独立运行任务」）。
    #    数据源 state/cloud_plugins.json（cloud-plugins.py gen 生成），连它自己的 doctrine 一起报。
    cloud = {}
    try:
        cp = json.loads((ROOT / "state" / "cloud_plugins.json").read_text(encoding="utf-8"))
        cloud = {"在册": cp.get("n"),
                 "形态": cp.get("form"),
                 "分组": len(cp.get("groups") or []),
                 "生成于": cp.get("generated_at"),
                 "口径": (cp.get("doctrine") or [])[:3]}
    except (OSError, ValueError):
        cloud = {"在册": None}

    online = len([p for p in people if p["状态"] == "工作中"])
 # 2026-10-11 加第二条腿（**治那个"全判休息"的老坑**）：
    #    上面那套是"拿域名/能力位名去撞台账文本"（L55 注释记过它撞不上 ⇒ 全休）。
    #    台账里的 target 多是**文件路径**（HEARTBEAT.md 之类），一个域名都撞不到 ⇒
    #    "在线"会长期读成 0，**看着像智能体没在跑** —— 而实际上是撞法不灵。
    #    ⇒ 另给一个**不依赖撞文本**的读数：近窗口内**台账总动作数**。
    #      有动作 = 这台机器在干活（如实）；哪位在动仍按撞法点亮（撞不到的如实显示 0）。
    recent_all = 0
    for r in rows:
        at = str(r.get("at") or "")
        try:
            ts = time.mktime(time.strptime(at, "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            ts = 0
        if (now - ts) <= WORK_WINDOW_S:
            recent_all += 1
    return _scrub({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "职位数": len(people),
            "工作中": online,
 # 2026-10-11：把"工作中"**同时**报成"在线数"，并写死它的口径 ——
            #    主人要的是"让用户知道智能体是可以同时运行的"。
            "在线数": online,
            "近窗口动作数": recent_all,
            "在线口径": ("近 %d 分钟内有动作 = 在跑；这是同时在跑的触手数，"
                         "不是上限 —— 上限由本地能装多少云插件决定，不由数量决定。"
                         "注意：本页有两条腿：① 逐位点亮靠「域名/能力位名撞台账文本」"
                         "（撞不上的如实显示 0，不代表它没在跑）② 全局在跑靠台账总动作数"
                         "（不依赖撞文本）⇒ 现读：近 %d 分钟台账 %d 条动作"
                         % (WORK_WINDOW_S // 60, WORK_WINDOW_S // 60, recent_all)),
            "休息中": len([p for p in people if p["状态"] == "休息中"]),
            "报警": al, "逐位": people,
            "云插件": cloud,
            "台账条数": len(rows),
            "并发说明": ("每根触手自带云插件、各跑各的小任务，跑完把结果交回来；"
                         "一根触手一个小任务 ⇒ 一百根、一千根都行 —— "
                         "瓶颈是本地能安多少云插件，不是并发数。")})


def _pin() -> dict:
    """读分牌器钉下的取向（`state/taste/ai-board.json`）。

    🔴 为什么读盘、而不是每次随机抽：这是**生成页**，每次重生成都换一套视觉 = 噪声不是设计。
       取向由 `taste-deal.py` 抽定一次并钉住（可追溯：pin 里记着 library 的 sha16），
       重建只**消费**它。抽不到时**不假装有**：回落到本页原先的配色，并在页脚如实写"未接入"。
    """
    p = ROOT / "state" / "taste" / "ai-board.json"
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def render(d: dict, pin: dict = None) -> str:
    pin = pin or {}
    tok = pin.get("tokens") or {}
    fon = tok.get("font") or {}
    siz = fon.get("sizes") or {}
    rad = tok.get("radius") or {}

    def tk(key, dflt):
        return str(tok.get(key) or dflt)

    def h(x, dflt="—"):
        """外来文本进 HTML 必须转义 + None 显示成 dflt。实现与理由见 `_page_text.esc`。"""
        return esc(x, dflt)

    rows = "".join(
        '<tr><td>%s</td><td class="n">%d</td><td class="%s">%s</td>'
        '<td class="n">%d</td><td>%s</td><td class="dim">%s</td></tr>'
        % (h(p["职位"]), p["工作位"], "work" if p["状态"] == "工作中" else "rest", p["状态"],
           p.get("窗口内动作数", 0),
           h((p["最近动作"] or "—")[:44]), h((p["最近时刻"] or "—")[11:19]))
        for p in d["逐位"])
    cloud = d.get("云插件") or {}
    _doctrine = "".join("<li>%s</li>" % h(x) for x in (cloud.get("口径") or []))
    cloud_block = (
        '<section class="card"><h2>云插件（触手各自携带、独立跑小任务）</h2>'
        '<p class="kv">在册 <b>%s</b> ｜ 形态 <b>%s</b> ｜ 分组 <b>%s</b> ｜ 台账生成于 %s</p>'
        '<ul class="doc">%s</ul></section>'
        % (h(cloud.get("在册")), h(cloud.get("形态")), h(cloud.get("分组")),
           h(cloud.get("生成于")), _doctrine or "<li>（无口径）</li>"))
    # ── 消费 library 令牌 ────────────────────────────────────────────────
    # 全部来自 vendor/taste-skill/library/app.json 的 data-terminal；
    # 数据色按该风格 identity 第②条换成品牌金（依据写在 pin 的 accent_override 里）。
    # 缺键一律有兜底：library 各风格的 token 键集**并不一致**（data-terminal 就没有 faint）。
    ground = tk("ground", "#0B1120");  surface = tk("surface", "#0a0e14")
    raised = tk("raised", "#111823");  bd = tk("border", "#1d2733")
    rule = tk("rule", "#131b25");      text = tk("text", "#e8eef6")
    muted = tk("muted", "#93a3b8");    accent = tk("accent", "#f5b041")
    neg = tk("negative", "#EF4444")
    r_card = int(rad.get("card") or 6); r_ctl = int(rad.get("control") or 999)
    f_fam = str(fon.get("family") or "Segoe UI"); f_fb = str(fon.get("fallback") or "system-ui")
    fs_title = int(siz.get("title") or 26); fs_sec = int(siz.get("section") or 20)
    fs_body = int(siz.get("body") or 13); fs_small = int(siz.get("small") or 12)
    row_h = int(tok.get("rowHeight") or 42)

    # 取向来源必须写在页面上（有 pin / 没 pin 都如实说，不许静默）
    if pin:
        taste_note = ("方向 <b>%s</b>（外壳 %s）· 版式 <b>%s</b> · 取向钉在 "
                      "<code>state/taste/ai-board.json</code> · 库 sha16 %s"
                      % (pin.get("style", {}).get("name") or "?", pin.get("shell") or "?",
                         pin.get("pattern", {}).get("id") or "?",
                         (pin.get("library") or {}).get("sha16") or "?"))
    else:
        taste_note = ("<b>本页未接入 library</b>（state/taste/ai-board.json 不存在）—— "
                      "跑 <code>taste-deal.py --page ai-board</code> 抽定方向后重生成")

    return f"""<!doctype html>
<html data-page-id="ai-board" lang="zh-CN"><head><meta charset="utf-8">
<!-- 自动生成，别手改。重建：py -3.14 tools/codex-scripts/ai-board.py -->
<title>GBT小土豆V8 · AI 工作面板</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 :root{{--g-ground:{ground};--g-surface:{surface};--g-raised:{raised};--g-border:{bd};--g-rule:{rule};
  --g-text:{text};--g-muted:{muted};--g-accent:{accent};--g-neg:{neg};
  --g-r-card:{r_card}px;--g-r-ctl:{r_ctl}px;--g-row:{row_h}px}}
 *{{box-sizing:border-box}}
 body{{margin:0;background:var(--g-ground);color:var(--g-text);
  font:{fs_body}px/1.6 "{f_fam}","{f_fb}","Microsoft YaHei",system-ui,sans-serif}}
 /* 层次只靠明度差：卡片比底更深，「不加边框、不加阴影、不加辉光」（该风格 avoid 第 4 条） */
 header{{display:flex;align-items:center;gap:14px;padding:16px 20px;background:var(--g-surface)}}
 .logo{{width:26px;height:26px;flex:0 0 auto}}
 /* 签名动作：强调色只作"与标签同宽的一条 1px 线"，不铺面、不碰按钮/导航 */
 .who{{font-size:{fs_title}px;font-weight:600;letter-spacing:-.01em}}
 .who b{{box-shadow:inset 0 -1px 0 var(--g-accent)}}
 .spacer{{flex:1}}
 .pill{{border:1px solid var(--g-border);border-radius:var(--g-r-ctl);padding:3px 11px;
  font-size:{fs_small}px;color:var(--g-muted);font-variant-numeric:tabular-nums}}
 .pill.ok{{color:var(--g-text)}} .pill.bad{{border-color:var(--g-neg);color:var(--g-neg)}}
 table{{width:100%;border-collapse:collapse;margin:0 0 24px}}
 th,td{{padding:0 20px;height:var(--g-row);border-bottom:1px solid var(--g-rule);text-align:left;
  font-variant-numeric:tabular-nums}}
 th{{color:var(--g-muted);font-weight:500;font-size:{fs_small}px}}
 /* 数字不着色（avoid 第 3 条：别给每个数字上绿红）；状态用「词」+ 明度差表达 */
 .n{{color:var(--g-text)}} .dim{{color:var(--g-muted)}}
 .work{{color:var(--g-text);font-weight:600}} .rest{{color:var(--g-muted)}}
 .card{{padding:16px 20px;background:var(--g-surface);border-radius:var(--g-r-card);margin:0 20px 24px}}
 .card h2{{margin:0 0 8px;font-size:{fs_sec}px;font-weight:400;color:var(--g-muted)}}
 .kv{{margin:4px 0;color:var(--g-muted);font-size:{fs_small}px}} .kv b{{color:var(--g-text)}}
 .doc{{margin:6px 0 0 18px;padding:0;color:var(--g-muted);font-size:{fs_small}px}}
 .note{{padding:10px 20px;color:var(--g-muted);font-size:{fs_small}px;background:var(--g-surface)}}
 .foot{{padding:16px 20px;color:var(--g-muted);font-size:{fs_small}px;line-height:1.8}}
 .foot code{{color:var(--g-text)}}
</style></head><body>
<header>
 <svg class="logo" viewBox="0 0 64 64"><circle cx="32" cy="32" r="26" fill="none" stroke="#38bdf8" stroke-width="4"/><circle cx="32" cy="32" r="9" fill="#f5b041"/></svg>
 <span class="who">GBT<b>小土豆</b>V8 · AI 工作面板</span>
 <span class="spacer"></span>
 <span class="pill">职位 {d['职位数']}</span>
 <span class="pill ok">在线 {d['在线数']}（同时在跑）</span>
 <span class="pill">休息中 {d['休息中']}</span>
 <span class="pill {'bad' if (d['报警'].get('断连缺失') or 0) else 'ok'}">报警 {h(d['报警'].get('断连缺失'))}</span>
</header>
<div class="note">在线口径：{h(d['在线口径'])}</div>
<div class="note">并发说明：{h(d['并发说明'])}</div>
{cloud_block}
<table><thead><tr><th>职位（能力域）</th><th>工作位</th><th>状态</th><th>窗口内动作</th><th>最近动作</th><th>时刻</th></tr></thead>
<tbody>{rows}</tbody></table>
<div class="foot">生成 {d['at']} ｜ 口径：近 30 分钟内有动作 = 工作中，否则休息中（休息的也看得见）｜ 台账 {d['台账条数']} 条 ｜ 重生成 <code>py -3.14 tools/codex-scripts/ai-board.py</code>
<br>{taste_note}
<br>开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属</div>
<script src="../shell/tentacle-kit.js" defer></script>
</body></html>
"""


def main() -> int:
    d = build_data()
    pin = _pin()                 # 取向由 taste-deal.py 抽定并钉在 state/taste/ai-board.json
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(clean_html(render(d, pin)), encoding="utf-8")
 # 2026-10-09 生成器**给自己的产物盖章**（与 capability-audit._head 同一根因）：
    #    产物必须自声明「自动生成 + 重建命令」，框架门才能按**文件自声明**把它认成生成物，
    #    而不是每次重生成都报一条 no_passport（实测撞过：holo_pet_w3/ai-board/ai-board-data.js）。
    OUT_JS.write_text("/* 自动生成，别手改。重建：py -3.14 tools/codex-scripts/ai-board.py */\n"
                      "globalThis.GBT_AI_BOARD = " + json.dumps(d, ensure_ascii=False) + ";\n",
                      encoding="utf-8")
    print("AI 工作面板：职位 %d · 工作中 %d · 休息中 %d · 报警 %s"
          % (d["职位数"], d["工作中"], d["休息中"], d["报警"].get("断连缺失")))
    print("已生成：%s" % OUT_HTML)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
