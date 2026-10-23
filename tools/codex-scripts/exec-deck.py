# -*- coding: utf-8 -*-
"""执行面 · 数据聚合器（一体式桌面壳「窗 C」的数据面，2026-09-23 起）。

## 它是什么 / 不是什么

**是**：把"三条主道到底谁在干活 / 信封覆盖多少 / 欠了几步活 / 还剩哪些能力卡点"
一次现算成**一份 JSON + 一张人读表**。
**不是**：不是渲染层（窗 C 的页面以后读这份 JSON）、不是新口径（**每一项都复用已有工具的输出**）。

## 为什么要单独一件

壳的「执行面」要显示四块。如果页面自己去拼四套读数，就会长出**第五套口径** ——
本仓最贵的教训就是"同一件事三个数"。所以这里定死：**数据面只有这一个出口，且只做汇总不重算**。

| 块 | 数据来自 | 为什么不自己算 |
|---|---|---|
| A 信封覆盖 | `five-dim.py ruler` 的 JSON | `ruler` 已经是那把尺子（含 `auto`/`outer`/`unknown` 分格） |
| B 三条主道 | `audit.jsonl` 现读（事件计数） | 事件名是唯一真源，数一遍即可 |
| C 欠的活 | `sync_steps.json`（**未收步清单**） | 那是步账本体；这里只算"开了多久" |
| D 能力卡点 | `unimplemented_scan.py --json` + `cap_probe_all` 产物（若有） | 那两件已经是卡点的口径 |

## 纪律

  · **缺源就说缺**（`null` + `why`），**不许显示成 0** —— 0 和"没读到"是两件事；
  · 每块都给一句"要动手就跑哪条命令"（人看见数字后知道下一步）；
  · 退出码：`0` 一切正常 · `2` 有需要人看的（悬空步 / 覆盖偏低 / 卡点未清）。

## 用法

    py -3.14 tools/codex-scripts/exec-deck.py
    py -3.14 tools/codex-scripts/exec-deck.py --json "%TEMP%\\gbt-exec-deck.json"
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
STORE = ROOT / "gbt_allinone" / "store"
AUDIT = STORE / "audit.jsonl"
STEPS = STORE / "sync_steps.json"
HOOK = STORE / "sync_hook_since.txt"
FIVE = ROOT / "tools" / "codex-scripts" / "five-dim.py"
UNIMPL = ROOT / "tools" / "codex-scripts" / "unimplemented_scan.py"

# 悬空步的分级：步账是"欠的活"清单，开了太久说明**没人收**
STALE_WARN_S = 6 * 3600
STALE_BAD_S = 48 * 3600


def _read_audit_events() -> tuple:
    """数审计事件。返回 `(全史, 装钩子后, 改动后, since)` 四个。

    🔴 **为什么要第三个窗口**：`since_hook` 覆盖的是一大段时间，而"门口默认同步"
    （`auto_envelope` + `synced_entry`）是**中途才落的** ⇒ 拿整段算覆盖率会把
    "改动前的旧账"算进分子分母，得出"覆盖仅 41%"这种**误导读数**（本轮实测踩到）。
    判据：**带上 `synced_entry` 的那条记录 = 改动之后写的**（那是加了这一格才有的字段）。
    ⇒ 覆盖率该看"改动后窗口"；旧窗口只作对照。
    """
    import collections
    since = 0.0
    try:
        since = float(HOOK.read_text(encoding="utf-8-sig").strip() or 0)
    except Exception:                                               # noqa: BLE001
        since = 0.0
    tot, post = collections.Counter(), collections.Counter()
    tagged = {"inside": 0, "outside": 0, "entry": collections.Counter()}
    if not AUDIT.is_file():
        return tot, post, tagged, since
    with AUDIT.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                e = json.loads(line)
            except Exception:                                       # noqa: BLE001
                continue
            ev = e.get("event") or "?"
            tot[ev] += 1
            if since and float(e.get("ts") or 0) >= since:
                post[ev] += 1
            m = e.get("meta") or {}
            if ev == "call" and "synced_entry" in m:
                if m.get("synced"):
                    tagged["inside"] += 1
                    tagged["entry"][str(m.get("synced_entry"))] += 1
                else:
                    tagged["outside"] += 1
                    tagged["entry"]["off"] += 1
    return tot, post, tagged, since


def block_A_ruler() -> dict:
    """信封覆盖：**复用 `five-dim.py ruler`**（不自己重算）。"""
    out = {"source": "five-dim.py ruler", "why": "", "data": None}
    try:
        p = subprocess.run([sys.executable, str(FIVE), "ruler"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180)
        out["data"] = json.loads(p.stdout or "{}")
    except Exception as e:                                          # noqa: BLE001
        out["why"] = "%s: %s" % (type(e).__name__, str(e)[:120])
    return out


def block_B_paths(tot, post) -> dict:
    """三条主道谁在干活。事件名就是真源。"""
    def pick(c):
        return {
            "call（唯一门）": c.get("call", 0),
            "brain_enter（五维）": c.get("brain_enter", 0),
            "brain_unify（真链入口）": c.get("brain_unify", 0),
            "sync_ear（开步/耳）": c.get("sync_ear", 0),
            "sync_eye（眼）": c.get("sync_eye", 0),
            "sync_mouth（嘴）": c.get("sync_mouth", 0),
            "sync_check（真机检）": c.get("sync_check", 0),
            "sync_abort（耳中止）": c.get("sync_abort", 0),
        }
    return {"全史": pick(tot), "装钩子后": pick(post),
            "要动手": "py -3.14 tools/codex-scripts/five-dim.py cap <kind>  # 走门；omni run 走五维默认路径"}


def block_C_debt() -> dict:
    """欠的活：未收步清单 + 开了多久（悬空分级）。"""
    if not STEPS.is_file():
        return {"steps": None, "why": "没有步账文件（还没开过步）", "open_n": 0,
                "stale_warn": 0, "stale_bad": 0, "items": []}
    try:
        d = json.loads(STEPS.read_text(encoding="utf-8-sig")) or {}
    except Exception as e:                                          # noqa: BLE001
        return {"steps": None, "why": "步账读不动：%s" % str(e)[:80], "open_n": None,
                "stale_warn": None, "stale_bad": None, "items": []}
    now = time.time()
    items, warn, bad = [], 0, 0
    for sid, st in d.items():
        t0 = float((st or {}).get("t0") or 0)
        age = (now - t0) if t0 else None
        if age is not None:
            if age >= STALE_BAD_S:
                bad += 1
            elif age >= STALE_WARN_S:
                warn += 1
        items.append({"step_id": sid, "goal": str((st or {}).get("goal") or "")[:90],
                      "opened_iso": (st or {}).get("opened_iso"),
                      "age_h": round(age / 3600, 1) if age else None})
    items.sort(key=lambda x: -(x["age_h"] or 0))
    return {"steps": str(STEPS.name), "why": "", "open_n": len(d),
            "stale_warn": warn, "stale_bad": bad, "items": items[:20],
            "要动手": "py -3.14 tools/codex-scripts/five-dim.py close <step_id> --evidence <证据>"}


def block_D_gaps() -> dict:
    """能力卡点：复用 `unimplemented_scan.py --json`；探针产物有就读，没有就说没有。"""
    out = {"registered_only": None, "stub_flagged": None, "no_dispatch": None,
           "skill_pointer_stubs": None, "probe": None, "why": "",
           "要动手": "py -3.14 tools/codex-scripts/unimplemented_scan.py"}
    tmp = Path(os.environ.get("TEMP", "/tmp")) / "gbt-unimpl-execdeck.json"
    try:
        subprocess.run([sys.executable, str(UNIMPL), "--json", str(tmp)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
        j = json.loads(tmp.read_text(encoding="utf-8"))
        out["registered_only"] = len(j.get("registered_only") or [])
        out["stub_flagged"] = len(j.get("stub_flagged") or [])
        out["no_dispatch"] = len(j.get("no_dispatch") or [])
        out["skill_pointer_stubs"] = len([s for s in (j.get("skill_dir_stubs") or [])
                                          if s.get("kind") == "pointer"])
    except Exception as e:                                          # noqa: BLE001
        out["why"] = "unimplemented_scan 跑不动：%s: %s" % (type(e).__name__, str(e)[:100])
    pj = Path(os.environ.get("TEMP", "/tmp")) / "gbt-capprobe-full.json"
    if pj.is_file():
        try:
            pr = json.loads(pj.read_text(encoding="utf-8"))
            out["probe"] = {"at": pr.get("at"), "probed": pr.get("probed"),
                            "buckets": {k: len(v) for k, v in (pr.get("buckets") or {}).items()}}
        except Exception as e:                                      # noqa: BLE001
            out["probe"] = {"why": "产物读不动：%s" % str(e)[:80]}
    else:
        out["probe"] = {"why": "**没有探针产物** —— 全能力位覆盖这轮没跑（别读成 0 问题）"}
    return out


def write_html(path: Path, payload: dict) -> str:
    """生成窗 C 页面：**数据内嵌**（快照）+ **视觉层外链**（`../deck3d.css`），供 `loadFile`。

    为什么不用"页面去 fetch 面板服务的新路由"：那要**改 panel_server.py 并重启它** ——
    而它正在跑（8765）。改产品面 + 重启服务是**另一个量级的动作**，不该为了一个视图去做。
    本仓已有同样的做法（`capabilities.html`：快照内嵌 + 页面写明"这是快照、要新读数跑哪条命令"）。
    ⇒ 这条路的代价是"数据是生成那一刻的"，所以页面**必须把快照时刻与重生成命令写在脸上**。

    2026-09-23（风哥令「3D 立体视觉感要做出来」）：立体与配色**全部外链到 `deck3d.css`**，
    本页只留版式。窗 C 与窗 D 因此是**同一套立体语言** —— 一处定义、两页引用；
    内嵌就成两份 CSS，改一处忘一处（本仓最贵的教训）。外链的是**本机文件**，断网照常渲染。
    """
    A, B, C, D = payload["blocks"]["A"], payload["blocks"]["B"], payload["blocks"]["C"], payload["blocks"]["D"]
    sh = ((A.get("data") or {}).get("since_hook") or {})
    tg = payload.get("tagged") or {}
    tg_n = (tg.get("inside") or 0) + (tg.get("outside") or 0)

    def esc(s):
        return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    rows_b = "".join(
        "<tr><td>%s</td><td class=n>%s</td><td class=n>%s</td></tr>"
        % (esc(k), esc(B["全史"][k]), esc(B["装钩子后"][k])) for k in B["全史"])

    att = payload.get("attention") or []
    att_html = ("<ul class=att>" + "".join("<li>%s</li>" % esc(x) for x in att) + "</ul>"
                if att else "<p class=ok>✅ 没有需要人看的项</p>")

    debt_rows = "".join(
        "<tr><td class=mono>%s</td><td class=n>%s</td><td>%s</td></tr>"
        % (esc(i["step_id"]), esc(i["age_h"]), esc(i["goal"]))
        for i in (C.get("items") or [])) or "<tr><td colspan=3 class=dim>（没有未收的步）</td></tr>"

    # 视觉层在不在：**不许猜**，生成时就查一次并写在页上（与窗 D 同一条纪律）
    css_rel = "../deck3d.css"
    css_ok = (path.parent / css_rel).resolve().is_file()
    css_note = ("立体视觉层 <code>%s</code> 已就位" % esc(css_rel) if css_ok else
                "<span class=\"pill fault\">立体视觉层缺 <code>%s</code></span>"
                "（页面仍可读，但没有三维观感）" % esc(css_rel))
    if not css_ok:
        attention = att + ["立体视觉层 %s 没找到 —— 页面会退化成平面" % css_rel]
        att_html = ("<ul class=att>" + "".join("<li>%s</li>" % esc(x) for x in attention)
                    + "</ul>")

    html = """<!doctype html>
<html lang="zh-CN" data-data-kind="快照" data-data-at="__AT__"><head><meta charset="utf-8" />
<meta name="color-scheme" content="dark" />
<title>GBT小土豆V8 · 执行面</title>
<link rel="stylesheet" href="__CSS__" />
<style>
  /* 本页只写**版式**，立体与配色一律由 deck3d.css 供（裸色值不在这出现） */
  .two{display:grid;grid-template-columns:1fr 1fr;gap:13px;align-items:start}
  @media (max-width:900px){.two{grid-template-columns:1fr}}
</style></head>
<body class="gbt-stage">
<div class="gbt-board">

  <div class="gbt-head">
    <div class="gbt-core" aria-hidden="true">__FACES__<span class="gbt-core-cast"></span></div>
    <div class="gbt-title">
      <h1>执行面 · 三条主道与欠的活</h1>
      <div class="sub">快照 <b>__AT__</b> ｜ 装钩子 __SINCE__ ｜ 账本 __LINES__ 行 ｜ __CSSNOTE__</div>
    </div>
  </div>

  <div class="gbt-card z-near"><h2>A · 信封覆盖</h2>
    <p class="kv">全史 brainless_ratio <b>__RATIO__</b> ｜ cap_calls_total <b>__CALLS__</b></p>
    <p class="kv">装钩子后（整段·含改动前旧账，只作对照）<b>__SH__</b></p>
    <div class="warnbox"><b>改动后窗口</b>（按 <code>synced_entry</code> 存在与否切，<b>这才是该看的数</b>）：
      <b>__TG__</b> ｜ entry 分格 <span class="mono">__ENT__</span></div>
    <p class="kv" style="margin-top:9px">为什么要两个窗口：`auto_envelope` 是中途才落的，
      拿整段算会把改动前的旧账算进分子分母。</p>
  </div>

  <div class="gbt-card z-mid"><h2>B · 三条主道谁在干活</h2>
    <table><tr><th>事件</th><th>全史</th><th>装钩子后</th></tr>__ROWS_B__</table>
  </div>

  <div class="gbt-card z-mid"><h2>C · 欠的活（未收步）</h2>
    <p class="kv">未收 <b>__OPEN__</b> ｜ 超 6h <b>__WARN__</b> ｜ 超 48h <b>__BAD__</b></p>
    <table><tr><th>step</th><th>开了(h)</th><th>目标</th></tr>__DEBT__</table>
  </div>

  <div class="gbt-card z-far"><h2>D · 能力卡点</h2>
    <p class="kv">只登记未实现 <b>__D1__</b> ｜ 自标骨架 <b>__D2__</b> ｜ 无分派分支 <b>__D3__</b> ｜ 技能真桩 <b>__D4__</b></p>
    <p class="kv">全能力位探针 <span class="mono">__PROBE__</span></p>
  </div>

  <div class="gbt-card z-foot"><h2>需要人看</h2>__ATT__</div>

  <div class="gbt-foot">
    快照 <b>__AT__</b> ｜ 这是<b>快照</b>，不是实时。要新读数：
    <code>py -3.14 tools/codex-scripts/exec-deck.py --html holo_pet_w3/exec-deck/index.html</code><br />
    开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
  </div>
</div>
</body></html>
"""
    repl = {
        "__CSS__": esc(css_rel), "__CSSNOTE__": css_note,
        "__FACES__": "<i></i>" * 11,   # 7 经 + 5 纬由视觉层定；这里只补面数
        "__AT__": esc(payload.get("at")),
        "__SINCE__": esc(time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(payload.get("since_hook") or 0))
                         if payload.get("since_hook") else "（无标记）"),
        "__LINES__": esc(payload.get("audit_lines")),
        "__RATIO__": esc((A.get("data") or {}).get("brainless_ratio")),
        "__CALLS__": esc((A.get("data") or {}).get("cap_calls_total")),
        "__SH__": esc("%s/%s（rate %s）" % (sh.get("inside"), sh.get("calls"), sh.get("rate_inside"))),
        "__TG__": esc(("%d/%d（rate %s）" % (tg.get("inside", 0), tg_n, round((tg.get("inside", 0) / tg_n), 4))
                       if tg_n else "还没有带 synced_entry 的调用（一次都没走过新口径）")),
        "__ENT__": esc(dict(tg.get("entry") or {})),
        "__ROWS_B__": rows_b,
        "__OPEN__": esc(C.get("open_n")), "__WARN__": esc(C.get("stale_warn")),
        "__BAD__": esc(C.get("stale_bad")), "__DEBT__": debt_rows,
        "__D1__": esc(D.get("registered_only")), "__D2__": esc(D.get("stub_flagged")),
        "__D3__": esc(D.get("no_dispatch")), "__D4__": esc(D.get("skill_pointer_stubs")),
        "__PROBE__": esc(json.dumps(D.get("probe"), ensure_ascii=False)),
        "__ATT__": att_html,
    }
    for k, v in repl.items():
        html = html.replace(k, str(v))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return str(path)


def main() -> int:
    ap = argparse.ArgumentParser(description="执行面数据聚合（窗 C 的数据源）")
    ap.add_argument("--json", default="")
    ap.add_argument("--html", default="", help="另生成自包含页面（窗 C 直接读它）")
    a = ap.parse_args()

    tot, post, tagged, since = _read_audit_events()
    A = block_A_ruler()
    B = block_B_paths(tot, post)
    C = block_C_debt()
    D = block_D_gaps()

    # ── 改动后窗口的覆盖率（**这才是该看的那个数**）──
    tg_n = tagged["inside"] + tagged["outside"]
    tg_rate = (tagged["inside"] / tg_n) if tg_n else None

    # ── 需要人看的项（决定退出码）──
    attention = []
    if C.get("stale_bad"):
        attention.append("悬空步 %d 步超过 48h（欠的活没人收）" % C["stale_bad"])
    elif C.get("stale_warn"):
        attention.append("悬空步 %d 步超过 6h" % C["stale_warn"])
    for name, blk in (("A 信封覆盖", A), ("D 能力卡点", D)):
        if blk.get("why"):
            attention.append("%s 取不到：%s" % (name, blk["why"][:80]))
    # 🔴 判据用**改动后窗口**：拿 since_hook 整段算会把改动前的旧账算进来（本轮实测误导过）。
    if isinstance(tg_rate, (int, float)) and tg_n >= 10 and tg_rate < 0.5:
        attention.append("**改动后**信封覆盖仅 %.0f%%（%d/%d）" % (tg_rate * 100,
                                                         tagged["inside"], tg_n))
    sh = ((A.get("data") or {}).get("since_hook") or {}) if A.get("data") else {}

    print("=" * 78)
    print("执行面 · 数据聚合（窗 C 的数据源）")
    print("=" * 78)
    print("  仓根 %s" % ROOT)
    print("  账本 %s（%s 行）" % (AUDIT.name, sum(tot.values())))
    print("  装钩子时刻 %s" % (time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(since)) if since else "（无标记）"))
    print("-" * 78)

    print("【A】信封覆盖 —— 源：%s" % A["source"])
    if A.get("why"):
        print("    🔴 取不到：%s" % A["why"])
    else:
        d = A["data"] or {}
        print("    全史 brainless_ratio = %s · cap_calls_total = %s"
              % (d.get("brainless_ratio"), d.get("cap_calls_total")))
        if sh:
            print("    装钩子后（**整段·含改动前旧账，只作对照**）：%s/%s（rate %s）· via=%s · entry=%s"
                  % (sh.get("inside"), sh.get("calls"), sh.get("rate_inside"),
                     sh.get("inside_via"), sh.get("inside_entry")))
        # 🔴 该看的那个数：带上 `synced_entry` 的记录 = 门口默认同步落地**之后**写的
        if tg_n:
            print("    **改动后窗口**（按 `synced_entry` 存在与否切）：%d/%d 在信封内（rate %s）"
                  % (tagged["inside"], tg_n, round(tg_rate, 4)))
            print("        entry 分格：%s" % dict(tagged["entry"]))
        else:
            print("    **改动后窗口**：还没有带 `synced_entry` 的调用（一次都没走过新口径）")

    print()
    print("【B】三条主道谁在干活（事件名即真源）")
    keys = list(B["全史"].keys())
    print("    %-24s %10s %12s" % ("事件", "全史", "装钩子后"))
    for k in keys:
        print("    %-24s %10d %12d" % (k, B["全史"][k], B["装钩子后"][k]))

    print()
    print("【C】欠的活 —— 源：%s" % (C.get("steps") or "（没有步账）"))
    if C.get("why"):
        print("    %s" % C["why"])
    print("    未收步 %s · 超 6h %s · 超 48h %s"
          % (C.get("open_n"), C.get("stale_warn"), C.get("stale_bad")))
    for it in (C.get("items") or [])[:8]:
        print("      %-14s %6sh  %s" % (it["step_id"], it["age_h"], it["goal"]))

    print()
    print("【D】能力卡点（复用 unimplemented_scan 与探针产物）")
    if D.get("why"):
        print("    🔴 %s" % D["why"])
    print("    只登记未实现 %s · 自标骨架 %s · 无分派分支 %s · 技能真桩 %s"
          % (D.get("registered_only"), D.get("stub_flagged"),
             D.get("no_dispatch"), D.get("skill_pointer_stubs")))
    print("    全能力位探针：%s" % json.dumps(D.get("probe"), ensure_ascii=False))

    print("-" * 78)
    if attention:
        print("  需要人看（%d 条）：" % len(attention))
        for x in attention:
            print("    · %s" % x)
    else:
        print("  ✅ 没有需要人看的项")
    print("  下一步命令：")
    for k in ("A", "C", "D"):
        blk = {"A": A, "C": C, "D": D}[k]
        if blk.get("要动手"):
            print("    [%s] %s" % (k, blk["要动手"]))

    payload = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "since_hook": since,
        "audit_lines": sum(tot.values()),
        "tagged": {"inside": tagged["inside"], "outside": tagged["outside"],
                   "entry": dict(tagged["entry"])},
        "blocks": {"A": A, "B": B, "C": C, "D": D},
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
