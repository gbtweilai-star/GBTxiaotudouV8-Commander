# -*- coding: utf-8 -*-
"""代码台 · 数据聚合器（一体式桌面壳「窗 D」的数据面，2026-09-23 起）。

## 它是什么 / 不是什么

**是**：把"这个仓现在长什么样 / 谁依赖谁 / 测试接得住吗 / 改动面收敛没有 /
要动手得先过哪道门"一次现算成**一份 JSON + 一张立体页**。
**不是**：不是编辑器（本页是**快照**，没有一行脚本）、不是新口径
（**每一块都走唯一门 `run_task`，复用已有能力位**）。

## 为什么走 `run_task` 而不是直接 import

`project_context` 与 `git_read` 都是只读、零作用域的能力位，直接调模块函数也能跑通。
但那样这次读取**不进审计账本** —— 于是"代码台自己的读数"就成了账本外的影子，
而这正是本仓最贵的教训（三个数、五套口径）。

⇒ 走门：每次开页，读动作都落到 `audit.jsonl`，**审计格能复查这一页的每一次读取**。
代价是 `git status` 在这个仓要 8 秒左右（2529 个改动文件），可以接受。

## 一条不许越的线：本页**不试探授权**

写动作（`code_patch apply` / `git_write commit`）要 `filesystem_write`。
"现在有没有授权"这件事**不能靠试**：`policy.authorize()` 对受限动作会**消耗一次性人工授权** ——
探一下就烧掉一次，主人下次真要用时反而没了。

⇒ 本页只报**"要什么作用域"**（`policy.evaluate`，纯函数、零副作用）+ **主人该敲哪条命令**，
    **不报"现在有没有"**，并且把这条理由写在脸上。缺什么由真跑那一刻的返回值说了算。

## 纪律

  · **缺源就说缺**（`null` + `why`），**不许显示成 0**；
  · 每块都给一句"要动手就跑哪条命令"；
  · 退出码：`0` 一切正常 · `2` 有需要人看的（结构读不全 / 改动面没收敛 / 测试接不住）。

## 用法

    py -3.14 tools/codex-scripts/code-deck.py
    py -3.14 tools/codex-scripts/code-deck.py --json "%TEMP%\\gbt-code-deck.json"
    py -3.14 tools/codex-scripts/code-deck.py --html holo_pet_w3/code-deck/index.html
"""
import argparse
import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DECK3D = "deck3d.css"           # 视觉层：与窗 C 共用同一份（一处定义，两页引用）
SCOPE = "gbt_allinone"          # 结构面默认只看框架本体（仓根 6600 文件，callgraph 要 78s）

# 改动面收敛线：超过这个数说明工作树已经不成形，人看不出"这次改了什么"
DIRTY_WARN = 200
DIRTY_BAD = 1000


# ── 走门 ──────────────────────────────────────────────────────────────────────
def _run_cap(kind: str, payload: dict, timeout_note: str = "") -> tuple:
    """调唯一门。返回 `(ok, result, why)` —— **失败不抛**，把原因原样带回去给人看。"""
    try:
        from gbt_allinone import api
    except Exception as e:                                          # noqa: BLE001
        return False, None, "框架本体 import 不动：%s: %s" % (type(e).__name__, str(e)[:100])
    try:
        env = api.run_task(kind, payload)
    except Exception as e:                                          # noqa: BLE001
        return False, None, "%s 抛了：%s: %s%s" % (kind, type(e).__name__, str(e)[:140],
                                                ("（%s）" % timeout_note) if timeout_note else "")
    res = (env or {}).get("gbt_result") or {}
    if str(res.get("status") or "") != "ok":
        return False, None, "%s 没跑成：%s" % (kind, json.dumps(res, ensure_ascii=False,
                                                            default=str)[:180])
    return True, res.get("result"), ""


# ── A/B/C 一次结构面调用分三格（同一份读数，不许算三遍）────────────────────────
def block_ABC_structure() -> dict:
    """A 结构 · B 依赖 · C 测试接得住吗 —— 源：`project_context` 的 `structure` 面。"""
    ok, data, why = _run_cap("project_context", {"op": "structure", "root": SCOPE, "limit": 8})
    out = {"source": "run_task('project_context', op=structure, root=%s)" % SCOPE,
           "ok": ok, "why": why, "A": None, "B": None, "C": None}
    if not ok:
        return out
    out["A"] = data.get("symbols") or {}
    out["B"] = data.get("deps") or {}
    out["C"] = data.get("tests") or {}
    return out


def block_D_version() -> dict:
    """D 版本与改动面 —— 源：`git_read` 四档（status / log / branch_list / stash_list）。"""
    out = {"source": "run_task('git_read', …)", "why": "", "status": None, "log": None,
           "branches": None, "stash": None,
           "要动手": "py -3.14 tools/codex-scripts/code-deck.py  # 重跑本页拿新读数"}
    fails = []
    for op, key, payload in (("status", "status", {"op": "status"}),
                             ("log", "log", {"op": "log", "limit": 6}),
                             ("branch_list", "branches", {"op": "branch_list"}),
                             ("stash_list", "stash", {"op": "stash_list"})):
        ok, data, why = _run_cap("git_read", payload)
        if ok:
            out[key] = data
        else:
            fails.append("%s: %s" % (op, why[:90]))
    if fails:
        out["why"] = " ｜ ".join(fails)
    return out


def block_E_gate() -> dict:
    """E 要动手得先过哪道门 —— 源：`policy.evaluate`（**纯函数，零副作用**）。

    见模块头那条红线：本块**不**回答"现在有没有授权"。试一下会烧掉一次性授权。

    ⚠️ 每一步都带 `stage`（2026-09-23 第 41 轮加）：F 块（工作回路）要按**回路顺序**分组，
    若靠"在第几个位置"去猜，改一次顺序就静默错位 —— 本仓已栽过同型（前缀 vs 相等、下标耦合）。
    """
    from gbt_allinone.security import policy
    acts = [
        ("读", "看代码结构", "project_context", {"op": "structure"}),
        ("读", "看依赖", "project_context", {"op": "deps"}),
        ("读", "看调用关系", "project_context", {"op": "calls"}),
        ("看改动面", "看改了哪些文件", "git_read", {"op": "status"}),
        ("试改", "试改（只出预览，不落盘）", "code_patch", {"op": "dry_run"}),
        ("真改", "真改一个文件", "code_patch", {"op": "apply"}),
        ("登记", "把改动登记进版本（stage/commit）", "git_write", {"op": "commit", "paths": ["<文件>"]}),
    ]
    rows = []
    for stage, label, kind, payload in acts:
        try:
            scopes = list(getattr(policy.evaluate(kind, payload), "scopes", ()) or ())
        except Exception as e:                                      # noqa: BLE001
            rows.append({"stage": stage, "label": label, "kind": kind, "op": payload.get("op"),
                         "scopes": None, "why": "%s: %s" % (type(e).__name__, str(e)[:60]),
                         "cmd": ""})
            continue
        rows.append({
            "stage": stage, "label": label, "kind": kind, "op": payload.get("op"),
            "scopes": scopes,
            "why": "", "free": not scopes,
            "cmd": ("" if not scopes else
                    "py -3.14 -m gbt_allinone auth grant --scope %s --ttl 600" % scopes[0]),
        })
    return {"source": "policy.evaluate（纯函数）", "rows": rows,
            "not_asked": "本页**不报**「现在有没有授权」—— 探一次会消耗一次性人工授权，"
                         "所以只报要什么。缺什么由真跑那一刻的返回值说了算。",
            "要动手": "py -3.14 -c \"from gbt_allinone import api;print(api.run_task('code_patch',"
                      "{'op':'dry_run','path':'<文件>','old':'…','new':'…'}))\""}


# ── F 工作回路（2026-09-23 第 41 轮加）────────────────────────────────────────
LOOP_ORDER = ["读", "看改动面", "试改", "真改", "验证", "登记"]

# ⑤ 验证：**它不是能力位** —— 如实登记，并写清「要成为能力位需要主人做什么」。
VERIFY_STAGE = {
    "stage": "验证", "label": "跑测试与四元组印章（判「改完还是不是好的」）",
    "kind": "（不是能力位）", "op": "", "scopes": None, "free": False, "not_a_cap": True,
    "why": "🔴 **它不过 policy 门、不落审计信封**：`policy.py` 里没有它的 kind 分支，"
           "而「新建一个 kind 却不加分支」= **零作用域**（本仓登记在册的坑：零作用域 ≠ 只读）。"
           "加分支要改 `policy.py` —— 那**只有主人能改**（AI 一律不许改 policy.py）。",
    "cmd": "py -3.14 tools/codex-scripts/run-tests.py",
    "cmd2": "py -3.14 -m gbt_allinone.tools.regression_stamp run "
            "--expect-python 3.14 --store fresh -- <命令>",
}


def block_F_loop(E: dict) -> dict:
    """F 工作回路 —— 把 A–E 的读数**排成一条能走的流水线**。

    ## 为什么单列一块（这是"设计"上的判断，不是又一格读数）

    A–E 各报一面（结构 / 依赖 / 覆盖 / 版本 / 门），读的人得**自己在脑子里排顺序**。
    那就不叫"专业级编程工作台"，叫五张报表。
    本块把它们钉成**一条回路**：读 → 看改动面 → 试改 → 真改 → 验证 → 登记，
    每步写清「走哪个能力位 / 过什么门 / 敲哪条命令」。

    ## 两条纪律

    ① **不顺下标猜**：分组靠 E 行自带的 `stage` 字段（见 block_E_gate 的说明），
       不靠"第几个位置" —— 下标耦合改一次顺序就静默错位。
    ② **不替注册表说话**：每个能力位都要**现查 `caps_registry`** 确认真身存在；
       查不到就当场打 fault 标，而不是照样渲染一个漂亮的名字。
    """
    from gbt_allinone import caps_registry as CR
    known = set()
    for attr in ("BENIGN_CAPS", "UNIMPLEMENTED_CAPS"):
        d = getattr(CR, attr, None)
        if isinstance(d, dict):
            known |= set(d)

    by_stage: dict = {}
    unknown = []
    for r in E.get("rows") or []:
        stage = r.get("stage") or "其它"
        rr = dict(r)
        rr["in_registry"] = r.get("kind") in known
        if not rr["in_registry"]:
            unknown.append(r.get("kind"))
        by_stage.setdefault(stage, []).append(rr)
    by_stage.setdefault("验证", []).append(dict(VERIFY_STAGE))

    stages = []
    for s in LOOP_ORDER:
        rows = by_stage.get(s) or []
        if rows:
            stages.append({"stage": s, "rows": rows})
    return {"stages": stages,
            "order": LOOP_ORDER,
            "checked_against": "caps_registry.BENIGN_CAPS / UNIMPLEMENTED_CAPS（现查）",
            "unknown_kinds": sorted(set(unknown)),
            "note": "第 ⑤ 步「验证」**不是能力位** —— 这一步是本回路唯一没被统一门罩住的一格，"
                    "已在页上写明原因与补救条件（要主人改 policy.py）。"}


# ── 页面（自包含数据 + 共用视觉层）────────────────────────────────────────────
def write_html(path: Path, payload: dict) -> str:
    """生成窗 D 页面：**数据内嵌**（快照）+ **视觉层外链**（`../deck3d.css`）。

    为什么视觉层不内嵌：窗 C 与窗 D 必须是**同一套立体语言**。内嵌 = 两份 CSS =
    改一处忘一处（本仓最贵的教训）。外链的是**本机文件**，不是网络资源 —— 断网照常渲染。
    缺了它会怎样：本函数**会检查并在页上写明**（不许"看着还行"就当没事）。
    """
    A, B, C = payload["blocks"]["ABC"]["A"], payload["blocks"]["ABC"]["B"], payload["blocks"]["ABC"]["C"]
    D, E = payload["blocks"]["D"], payload["blocks"]["E"]
    F = payload["blocks"]["F"]
    payload["blocks"]["ABC"]["ok"]

    def esc(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def md(s):
        """行内 Markdown → HTML（**只认 `**粗体**` 这一种**）。

        为什么必须转：页面是 **HTML**，`**粗体**` 会**原样显示成星号**。
        实测就是这样的 —— 页面上渲染出「每一步的能力位都**现查** …」，
        两个星号明晃晃挂在那儿。本仓审美纪律里这属于**渲染缺陷**（"AI 味"），
        不是"文档风格"。
        只认粗体：不做完整 Markdown 解析（多余的事不做，也不会引进来一个新依赖）。
        ⚠️ 只喂**纯散文**：已经拼好的 HTML（如 `<span class=pill>`）别喂进来 ——
           本函数会先 esc，把那些标签转义掉。
        """
        parts = esc(s).split("**")
        return "".join("<strong>%s</strong>" % seg if i % 2 else seg
                       for i, seg in enumerate(parts))

    def n(v):
        return "—" if v is None else v

    # 「缺源就说缺」：取不到的结构面一律显 `—`，绝不留 0
    A = A or {}
    B = B or {}
    C = C or {}
    top_files = (A.get("top_files") or [])[:6]
    ext = (B.get("external_top") or [])[:6]
    un = (C.get("unmentioned_sample") or [])[:6]
    st = D.get("status") or {}
    commits = (D.get("log") or {}).get("commits") or []

    rows_top = "".join("<tr><td class=mono>%s</td><td class=n>%s</td></tr>"
                       % (esc(f.get("path")), esc(f.get("defs"))) for f in top_files) \
        or "<tr><td colspan=2 class=dim>（取不到）</td></tr>"
    rows_ext = "".join("<tr><td class=mono>%s</td><td class=n>%s</td></tr>"
                       % (esc(x.get("name")), esc(x.get("count"))) for x in ext) \
        or "<tr><td colspan=2 class=dim>（取不到）</td></tr>"
    rows_un = "".join("<tr><td class=mono>%s</td></tr>" % esc(x) for x in un) \
        or "<tr><td class=dim>（取不到）</td></tr>"
    rows_cm = "".join("<li class=mono>%s</li>" % esc(c) for c in commits) \
        or "<li class=dim>（取不到）</li>"
    rows_dirty = "".join("<tr><td class=mono>%s</td></tr>" % esc(x)
                         for x in (st.get("dirty_sample") or [])[:8]) \
        or "<tr><td class=dim>（取不到）</td></tr>"

    rows_gate = "".join(
        "<tr><td>%s</td><td class=mono>%s.%s</td><td>%s</td></tr>" % (
            esc(r["label"]), esc(r["kind"]), esc(r["op"]),
            ("<span class=\"pill ok\">免卡直跑</span>" if r.get("free") else
             "<span class=\"pill warn\">要 %s</span>" % esc("、".join(r.get("scopes") or ["?"])))
            if not r.get("why") else "<span class=\"pill fault\">%s</span>" % esc(r["why"]))
        for r in E["rows"])

    # ── F 工作回路的渲染（排在最前：它是这一页的骨架，A–E 是它的证据）──
    def _loop_pill(r):
        if r.get("not_a_cap"):
            return '<span class="pill fault">不是能力位</span>'
        if r.get("why"):
            return '<span class="pill fault">%s</span>' % esc(r["why"])
        if not r.get("in_registry", True):
            return '<span class="pill fault">注册表里查不到 %s</span>' % esc(r.get("kind"))
        if r.get("free"):
            return '<span class="pill ok">免卡直跑</span>'
        return '<span class="pill warn">要 %s</span>' % esc("、".join(r.get("scopes") or ["?"]))

    loop_html = ""
    for i, st in enumerate(F["stages"], 1):
        items = ""
        for r in st["rows"]:
            cmds = ""
            for c in (r.get("cmd"), r.get("cmd2")):
                if c:
                    cmds += "<div class=cmd><code>%s</code></div>" % esc(c)
            items += ("<li><b>%s</b> <span class=mono>%s</span> %s%s</li>"
                      % (esc(r["label"]), esc(r["kind"]), _loop_pill(r), cmds))
        loop_html += ('<li class=stage><h3>%d · %s</h3><ul class=cm>%s</ul></li>'
                      % (i, esc(st["stage"]), items))

    loop_meta = md("每一步的能力位都**现查** %s。" % F["checked_against"])
    if F.get("unknown_kinds"):
        loop_meta += ('<span class="pill fault">查不到：%s</span>'
                      % esc("、".join(F["unknown_kinds"])))
    else:
        loop_meta += "真身全部命中。"

    dirty_n = st.get("dirty_n")
    dirty_cls = "faultbox" if (isinstance(dirty_n, int) and dirty_n >= DIRTY_BAD) else \
                "warnbox" if (isinstance(dirty_n, int) and dirty_n >= DIRTY_WARN) else "kv"

    att = payload.get("attention") or []
    # 2026-10-26：原来这里是 `✅ 没有需要人看的项` —— 只在**一切正常**时才输出，
    # 等于一颗潜伏地雷：哪天全绿了才冒出来撞审美闸的 emoji 条款（同类问题在 exec-deck 已踩过一次）。
    att_html = ("<ul class=att>" + "".join("<li>%s</li>" % md(x) for x in att) + "</ul>"
                if att else "<p class=ok>没有需要人看的项</p>")

    # 视觉层在不在：**不许猜**，生成时就查一次并写在页上
    css_rel = "../" + DECK3D
    css_ok = (path.parent / css_rel).resolve().is_file()
    css_note = ("立体视觉层 <code>%s</code> 已就位" % esc(css_rel) if css_ok else
                "<span class=\"pill fault\">立体视觉层缺 <code>%s</code></span>"
                "（页面仍可读，但没有三维观感）" % esc(css_rel))
    if not css_ok:
        att = att + ["立体视觉层 %s 没找到 —— 页面会退化成平面" % css_rel]

    html = """<!doctype html>
<html data-page-id="code-deck" lang="zh-CN" data-data-kind="快照" data-data-at="__AT__"><head><meta charset="utf-8" />
<meta name="color-scheme" content="dark" />
<title>GBT小土豆V8 · 代码台</title>
<link rel="stylesheet" href="../page-skins.css" />
<link rel="stylesheet" href="__CSS__" />
<style>
  /* 本页只写版式，立体与配色一律由 deck3d.css 供（裸色值不在这出现） */
  .two{display:grid;grid-template-columns:1fr 1fr;gap:13px;align-items:start}
  .two > .gbt-card{margin:0}
  ul.cm{margin:0;padding-left:18px}
  ul.cm li{margin:3px 0;font-size:12.5px;color:var(--gbt-dim)}
  /* F 工作回路：只用版式，颜色一律取自视觉层 token（裸色值不在这出现） */
  ol.loop{list-style:none;margin:0;padding:0;display:grid;gap:9px}
  ol.loop > li.stage{border-left:2px solid var(--gbt-dim);padding:1px 0 1px 11px}
  ol.loop h3{margin:0 0 5px;font-size:13px}
  div.cmd{margin:3px 0 0}
  div.cmd code{font-size:11.5px;word-break:break-all}
  @media (max-width:900px){.two{grid-template-columns:1fr}}
</style></head>
<body class="gbt-stage">
<div class="gbt-board">

  <div class="gbt-head">
    <div class="gbt-core" aria-hidden="true">__FACES__<span class="gbt-core-cast"></span></div>
    <div class="gbt-title">
      <h1>代码台 · 这个仓现在长什么样</h1>
      <div class="sub">
        快照 <b>__AT__</b> ｜ 结构面 <b>__ROOT__</b> ｜ 账本今次读取已走门
        <code>run_task</code> ｜ __CSSNOTE__
      </div>
    </div>
  </div>

  <div class="gbt-card z-near">
    <h2>F · 工作回路 —— 一次专业级改动怎么走完</h2>
    <p class="kv">__LOOP_ORDER__ ｜ __LOOP_META__</p>
    <ol class="loop">__LOOP__</ol>
    <p class="kv" style="margin-top:10px">__LOOP_NOTE__</p>
  </div>

  <div class="gbt-card z-near">
    <h2>A · 代码结构</h2>
    <p class="kv">文件 <b>__A_FILES__</b> ｜ 符号 <b>__A_SYM__</b> ｜ 解析不了的文件 <b>__A_UNP__</b></p>
    <table><tr><th>定义最多的文件</th><th>defs</th></tr>__ROWS_TOP__</table>
    <p class="kv" style="margin-top:9px">要动手：<code>py -3.14 -c "from gbt_allinone import api;
      print(api.run_task('project_context',{'op':'symbols','name':'&lt;名字&gt;'}))"</code></p>
  </div>

  <div class="two">
    <div class="gbt-card z-mid">
      <h2>B · 依赖网</h2>
      <p class="kv">内部边 <b>__B_EDGES__</b> ｜ 解析不了 <b>__B_UNP__</b></p>
      <table><tr><th>外部依赖（按出现文件数）</th><th>次数</th></tr>__ROWS_EXT__</table>
    </div>

    <div class="gbt-card z-mid">
      <h2>C · 测试接得住吗</h2>
      <p class="kv">源模块 <b>__C_SRC__</b> ｜ 测试文件 <b>__C_TF__</b> ｜
        被提到 <b>__C_MEN__</b> ｜ <b>__C_UNM__</b> 没被提到（占 <b>__C_RATE__</b>）</p>
      <table><tr><th>没被任何测试提到的模块（示例）</th></tr>__ROWS_UN__</table>
      <p class="kv" style="margin-top:9px">边界：这是<strong>提到过</strong>的代理，<strong>不是行覆盖</strong> ——
        没被提到 ≠ 没被测，被提到 ≠ 测得好。</p>
    </div>
  </div>

  <div class="gbt-card z-far">
    <h2>D · 版本与改动面</h2>
    <p class="kv">分支 <b>__D_BR__</b> ｜ 改动文件 <b>__D_DIRTY__</b> ｜
      分支数 <b>__D_BRN__</b> ｜ stash <b>__D_STASH__</b></p>
    <div class="__DIRTYCLS__">改动面 <b>__D_DIRTY__</b> 个文件未收敛
      （过 __DW__ 该看一眼、过 __DB__ 说明工作树已经不成形）——
      git status 本身是只读免卡的，收敛与否是<strong>卫生读数</strong>，不是本页的判决。</div>
    <div class="two" style="margin-top:11px">
      <div>
        <p class="kv">最近提交</p><ul class="cm">__ROWS_CM__</ul>
      </div>
      <div>
        <p class="kv">改动样例（前 8 条）</p>
        <table>__ROWS_DIRTY__</table>
      </div>
    </div>
  </div>

  <div class="gbt-card z-far">
    <h2>E · 要动手得先过哪道门（现算，非抄写）</h2>
    <table><tr><th>动作</th><th>能力位</th><th>门</th></tr>__ROWS_GATE__</table>
    <div class="warnbox" style="margin-top:10px">__NOTASKED__</div>
    <p class="kv" style="margin-top:9px">要动手（改文件先出预览，不落盘）：
      <code>__E_CMD__</code></p>
  </div>

  <div class="gbt-card z-foot">
    <h2>需要人看</h2>__ATT__
  </div>

  <div class="gbt-foot">
    快照 <b>__AT__</b> ｜ 这是<strong>快照</strong>，不是实时。要新读数：
    <code>py -3.14 tools/codex-scripts/code-deck.py --html holo_pet_w3/code-deck/index.html</code><br />
    开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
  </div>
</div>
</body></html>
"""
    rate = None
    if isinstance(C.get("source_modules_n"), int) and C.get("source_modules_n"):
        rate = "%.1f%%" % (100.0 * (C.get("unmentioned_n") or 0) / C["source_modules_n"])
    repl = {
        "__CSS__": esc(css_rel), "__CSSNOTE__": css_note,
        # 核心球的面数由**视觉层**决定（7 经 + 5 纬 = 11 条环 + 1 个光斑）。
        # 写在这里而不是页面上：几何归设计系统管，页面只管"这里放签名元素"。
        "__FACES__": "<i></i>" * 11,
        "__AT__": esc(payload.get("at")), "__ROOT__": esc(SCOPE),
        "__A_FILES__": esc(n(A.get("files"))), "__A_SYM__": esc(n(A.get("symbols_total"))),
        "__A_UNP__": esc(n(A.get("unparsed_n"))), "__ROWS_TOP__": rows_top,
        "__B_EDGES__": esc(n(B.get("internal_edges_n"))), "__B_UNP__": esc(n(B.get("unparsed_n"))),
        "__ROWS_EXT__": rows_ext,
        "__C_SRC__": esc(n(C.get("source_modules_n"))), "__C_TF__": esc(n(C.get("test_files_n"))),
        "__C_MEN__": esc(n(C.get("mentioned_n"))), "__C_UNM__": esc(n(C.get("unmentioned_n"))),
        "__C_RATE__": esc(rate if rate else "—"), "__ROWS_UN__": rows_un,
        "__D_BR__": esc(st.get("branch_line") or "—"),
        "__D_DIRTY__": esc(n(dirty_n)),
        "__D_BRN__": esc(len(((D.get("branches") or {}).get("items") or [])) if D.get("branches") else None),
        "__D_STASH__": esc(len(((D.get("stash") or {}).get("items") or [])) if D.get("stash") else None),
        "__DIRTYCLS__": dirty_cls, "__DW__": esc(DIRTY_WARN), "__DB__": esc(DIRTY_BAD),
        "__ROWS_CM__": rows_cm, "__ROWS_DIRTY__": rows_dirty,
        "__ROWS_GATE__": rows_gate, "__NOTASKED__": md(E["not_asked"]),
        "__LOOP__": loop_html, "__LOOP_META__": loop_meta,
        "__LOOP_ORDER__": esc(" → ".join(F["order"])),
        "__LOOP_NOTE__": md(F["note"]),
        "__E_CMD__": esc(E["要动手"]), "__ATT__": att_html,
    }
    for k, v in repl.items():
        html = html.replace(k, str(v))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return str(path)


# ── 主流程 ────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="代码台数据聚合（窗 D 的数据源）")
    ap.add_argument("--json", default="")
    ap.add_argument("--html", default="", help="另生成立体页（窗 D 直接读它）")
    a = ap.parse_args()

    t0 = time.time()
    ABC = block_ABC_structure()
    D = block_D_version()
    E = block_E_gate()
    F = block_F_loop(E)

    A, B, C = ABC.get("A") or {}, ABC.get("B") or {}, ABC.get("C") or {}
    st = D.get("status") or {}

    # ── 需要人看的项（决定退出码）──
    attention = []
    if not ABC.get("ok"):
        attention.append("结构面取不到：%s" % (ABC.get("why") or "")[:100])
    elif A.get("unparsed_n"):
        attention.append("有 %s 个文件解析不了 —— 上面的结构读数**是不全的**" % A["unparsed_n"])
    if D.get("why"):
        attention.append("版本面部分取不到：%s" % D["why"][:100])
    dn = st.get("dirty_n")
    if isinstance(dn, int) and dn >= DIRTY_BAD:
        attention.append("改动面没收敛：%s 个文件（过 %d 说明工作树已不成形）" % (dn, DIRTY_BAD))
    elif isinstance(dn, int) and dn >= DIRTY_WARN:
        attention.append("改动面偏大：%s 个文件（线 %d）" % (dn, DIRTY_WARN))
    if isinstance(C.get("source_modules_n"), int) and C["source_modules_n"]:
        r = (C.get("unmentioned_n") or 0) / C["source_modules_n"]
        if r >= 0.5:
            attention.append("**超一半**源模块（%.0f%%）没被任何测试提到" % (r * 100))

    print("=" * 78)
    print("代码台 · 数据聚合（窗 D 的数据源）")
    print("=" * 78)
    print("  仓根 %s" % ROOT)
    print("  结构面范围 %s（%s）" % (SCOPE, ABC.get("source") or ""))
    print("-" * 78)

    print("【A】代码结构")
    if not ABC.get("ok"):
        print("    🔴 取不到：%s" % ABC.get("why"))
    else:
        print("    文件 %s · 符号 %s · 解析不了 %s"
              % (A.get("files"), A.get("symbols_total"), A.get("unparsed_n")))
        for f in (A.get("top_files") or [])[:5]:
            print("      %-58s %s" % (f.get("path"), f.get("defs")))

    print()
    print("【B】依赖网")
    print("    内部边 %s · 解析不了 %s" % (B.get("internal_edges_n"), B.get("unparsed_n")))
    print("    外部 top：%s" % ", ".join("%s×%s" % (x.get("name"), x.get("count"))
                                      for x in (B.get("external_top") or [])[:6]))

    print()
    print("【C】测试接得住吗（**提到过**的代理，不是行覆盖）")
    r = None
    if isinstance(C.get("source_modules_n"), int) and C["source_modules_n"]:
        r = (C.get("unmentioned_n") or 0) / C["source_modules_n"]
    print("    源模块 %s · 测试文件 %s · 被提到 %s · 没被提到 %s%s"
          % (C.get("source_modules_n"), C.get("test_files_n"), C.get("mentioned_n"),
             C.get("unmentioned_n"), ("（%.1f%%）" % (r * 100)) if r is not None else ""))

    print()
    print("【D】版本与改动面")
    if D.get("why"):
        print("    ⚠️ %s" % D["why"])
    print("    分支 %s" % (st.get("branch_line") or "—"))
    print("    改动文件 %s · 分支 %s · stash %s"
          % (st.get("dirty_n"),
             len(((D.get("branches") or {}).get("items") or [])) if D.get("branches") else "—",
             len(((D.get("stash") or {}).get("items") or [])) if D.get("stash") else "—"))
    for c in ((D.get("log") or {}).get("commits") or [])[:4]:
        print("      %s" % c[:96])

    print()
    print("【E】要动手得先过哪道门（现算）")
    for row in E["rows"]:
        if row.get("why"):
            print("    %-30s 🔴 %s" % (row["label"], row["why"]))
        elif row.get("free"):
            print("    %-30s ✅ 免卡直跑（%s.%s）" % (row["label"], row["kind"], row["op"]))
        else:
            print("    %-30s 🔑 要 %s" % (row["label"], "、".join(row["scopes"])))
    print("    🔴 %s" % E["not_asked"])

    print("-" * 78)
    if attention:
        print("  需要人看（%d 条）：" % len(attention))
        for x in attention:
            print("    · %s" % x)
    else:
        print("  ✅ 没有需要人看的项")
    print("  用时 %.1fs" % (time.time() - t0))

    payload = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_s": round(time.time() - t0, 1),
        "root": SCOPE,
        "blocks": {"ABC": ABC, "D": D, "E": E, "F": F},
        "attention": attention,
    }
    if a.json:
        Path(a.json).write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str),
                                encoding="utf-8")
        print("  产物: %s" % a.json)
    if a.html:
        p = write_html(Path(a.html), payload)
        print("  页面快照: %s" % p)
    return 2 if attention else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(3)
