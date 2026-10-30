# -*- coding: utf-8 -*-
"""三条铁律的机器判据（主人令 2026-10-11）。

## 铁律原文（主人逐字）
  1. **禁止脑补**：所有关于线上状态、文件内容、部署列表的结论，必须来自**最近一次
     tool-shell / tool-file 的原始输出**，禁止用记忆回答。
  2. **必须带参**：wrangler / state 读取必须带**绝对路径**和 **--name**；
     deploy/xxx.toml 这种不存在路径**禁止直接引用**，先 ls 确认。
  3. **先纠错再回答**：如果上一条说「没有 Worker」但 tool 返回里有 gbt-potato-cloud-10，
     必须**第一句就承认「我上一条错了」**。

## 本件怎么咬（每条都要能机检）
  铁律1 → 交付声明必须带「命令 → 读数」形状，且读数可复跑（与 closed-loop-gate 同源，
          本件只查**形状**：evidence 里必须有 cmd 与原始输出片段）。
  铁律2 → 扫**活跃代码/脚本**（.py/.ps1/.cmd/.bat）里的 wrangler 调用：
          **必须**带 --name / --config / 指向真实存在的 wrangler.toml；
          并且**引用的路径必须先在盘上**。
          ⚠️ 不看 .md / SKILL.md —— 那里的反引号是**示例**不是调用（否则假红）。
  铁律3 → 纠正必须**留痕**：state/corrections.jsonl（只追加）；
          本件检查它**存在且格式对**，并把最近几条打出来供人核。

用法: py -3.14 -X utf8 tools/codex-scripts/iron-rules-check.py [--json] [--selftest]

════════════════════════════════════════════════════════════════════════
铁律 4~12（主人令 2026-10-30：「把她的习惯和部署规则给我定死了」）
每一条都对应一次**真实翻车**，不是凭空立的。条款正文见 AGENTS.md 同名小节。
════════════════════════════════════════════════════════════════════════

【部署 D】
 4. 双仓不许搞错 —— origin 必须是私有仓 paysssk-creator/GBT-V8；
    公开仓 gbtweilai-star/GBTxiaotudouV8-Commander 是**另一个仓、历史不相交**。
 5. 非法路径零容忍 —— 仓里文件名不许是绝对路径 / 含冒号或反斜杠。
    实测：公开仓被塞进 `C:\\Users\\...\\state/.autobind_stamp` 三个 ⇒ **Windows 上整个仓无法检出**。
 6. 抽屉有上限 —— state/heartbeat 的 scan-*.json ≤ KEEP_SCANS，环形保留**无条件**执行。
    实测：prune 原来只在 --clean 时跑，而定时链路从不传 clean ⇒ 6 次 23→28 份，288 份/天。

【习惯 H】
 7. 跳过 ≠ 通过 —— `ok=None`（分档跳过）不许算绿，必须配"上次真跑是什么时候"的记账。
    实测：light 档跳过 body_map，12/12 全绿，而七感官六动作**从没被体检过**。
 8. 只测绿等于没测 —— 必须有负控（喂故障必须判红）。
 9. 护栏只增不减 —— 修过的坑必须留用例，`state/iron-rules-baseline.json` 记基线。
10. 缺字段 ≠ 值为假 —— 不许替调用方编造默认值。
    实测：简报没带 deep，被当成"从未深检" ⇒ 常驻循环每拍补跑一次全身体检（churn）。
11. 同一个全局根因只开一张单 —— 12 根各报一遍等于把病灶念成 12 个问题。
12. 闭环必须端到端接上 —— 常驻循环要真调 `act()`，不能只 advise。
    实测：act() 只有 CLI 和测试在调，"自动补齐"在真实运行里根本没发生过。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")           # type: ignore[attr-defined]
    except Exception:
        pass

WS = pathlib.Path(__file__).resolve().parents[2]
CORRECTIONS = WS / "state" / "corrections.jsonl"

# 只看**活跃代码/脚本**（文档里的示例不算调用 —— 否则满仓假红）
ACTIVE_EXT = (".py", ".ps1", ".cmd", ".bat", ".cjs", ".mjs")
# 2026-10-11 自纠（**假红**）：原来只写 "_legacy"，而实际目录叫 **_legacy_sources**
#    ⇒ 没跳过 ⇒ 报「85 处 wrangler 没带 --name」，列出来的**全在那个历史源里**
#    ⇒ 跳过名单改成**前缀匹配**，并把历史/遗留源一并纳入。
SKIP_DIRS = ("_baseline_wt", "_legacy", "_legacy_sources", "_upstream", "node_modules",
             "__pycache__", ".mimosa", ".wrangler", ".scratch", ".git", "vendor", "store",
             "archive", ".backups")
WRANGLER_CALL = re.compile(r"\bwrangler\s+(deployments|secret|containers|deploy|tail|kv|r2|d1|versions|pages)\b")
HAS_NAME = re.compile(r"--name\b|--config\b|wrangler\.(toml|json)")


def _active_files():
    for p in WS.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in ACTIVE_EXT:
            continue
        s = str(p).replace("\\", "/")
        # 前缀匹配（不是精确段匹配）—— 免得 "_legacy" 漏掉 "_legacy_sources"
        if any(("/" + d) in s for d in SKIP_DIRS):
            continue
        yield p


def rule2() -> dict:
    """必须带参：活跃脚本里的 wrangler 调用必须带 --name/--config/真 toml。"""
    hits, bad = [], []
    for p in _active_files():
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, ln in enumerate(txt.splitlines(), 1):
            if not WRANGLER_CALL.search(ln) or ln.strip().startswith("#"):
                continue
            m = WRANGLER_CALL.search(ln)
 # 2026-10-11 自纠（假红）：把「字符串字面量里的 wrangler」也当成了调用
            #    （实测：cliproxy.py 的 print(...) 帮助文本、keys-page.py 的 dict 值、以及
            #    本判据自己的负控探针 probe='wrangler deployments list' 全被误报）。
            #    ⇒ 正解：**调用行里 wrangler 不该在引号里**；引号里的只是说明文字。
            # 引号或**反引号**（docstring/注释里的说明文字）都算字面量，不是调用。
            # （实测又抓两处：r2-move.py 与 test_cloud_config_wiring.py 里反引号内的 wrangler。）
            if any(c in ln[:m.start()] for c in ('"', "'", "`")):
                continue
            rec = "%s:%d  %s" % (p.relative_to(WS), i, ln.strip()[:88])
            hits.append(rec)
            if not HAS_NAME.search(ln):
                bad.append(rec)
    return {"calls": len(hits), "violations": bad,
            "ok": not bad,
            "gap": ("%d 处 wrangler 调用没带 --name/--config" % len(bad)) if bad else ""}


def rule1() -> dict:
    """禁止脑补：交付声明的 evidence 必须是「命令 → 读数」形状。"""
    f = WS / "state" / "delivery-claims.jsonl"
    if not f.is_file():
        return {"claims": 0, "bad": [], "ok": False, "gap": "声明台账不在"}
    bad = []
    n = 0
    for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except Exception:                          # noqa: BLE001
            continue
        n += 1
 # 2026-10-11 自纠（**假红**）：原来拿 evidence 字段判"读数形状"，但本仓声明把
        #    期望读数存在 **expect_contains** 里（cmd + expect_contains 是 delivery-claims 的写死形状）
        #    ⇒ 改成查 expect_contains。实测：closed-loop-gate --sweep 已证明那 15 条**全部**带
        #    cmd+expect_contains 且复跑命中，而本判据却报"15 条缺读数形状" ⇒ 是我查错字段。
 # 2026-10-11 自纠（又一处假红）：声明里**根本没有 evidence 字段** ——
        #    字段写死是 id/what/cmd/expect_contains/scope/at。cmd+expect_contains **就是**
        #    「命令→读数」形状。上一版多查了 evidence 并判「太短」，把 15 条全冤枉了。
        has_cmd = bool(r.get("cmd"))
        has_read = bool(r.get("expect_contains"))
        if not (has_cmd and has_read):
            bad.append("%s（cmd=%s expect_contains=%s）" % (r.get("id"), has_cmd, has_read))
    return {"claims": n, "bad": bad, "ok": not bad,
            "gap": ("%d 条声明缺「命令→读数」形状" % len(bad)) if bad else ""}


def rule3() -> dict:
    """先纠错再回答：纠正必须留痕（state/corrections.jsonl，只追加）。"""
    if not CORRECTIONS.is_file():
        return {"n": 0, "last": [], "ok": True,
                "gap": "纠正台账**还没建**（首条由本件自举写入）"}
    rows = []
    for ln in CORRECTIONS.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except Exception:                          # noqa: BLE001
            continue
    shape_bad = [r for r in rows if not (r.get("at") and r.get("said_wrong") and r.get("corrected"))]
    return {"n": len(rows), "last": rows[-3:], "ok": not shape_bad,
            "gap": ("%d 条纠正记录缺字段（要 at/said_wrong/corrected）" % len(shape_bad)) if shape_bad else ""}


# ══════════════════════════════════════════════════════════════════
# 铁律 4~12（主人令 2026-10-30）
# 条款正文在上方模块 docstring；这里只放判据。每条都只读，不写生产面。
# ══════════════════════════════════════════════════════════════════

HB_STATE = WS / "state" / "heartbeat"
IRON_BASELINE = WS / "state" / "iron-rules-baseline.json"
HB_TESTS = WS / "gbt_allinone" / "tests" / "test_heartbeat_tentacle.py"
PRIVATE_MUST = "paysssk-creator/GBT-V8"
PUBLIC_REF = "refs/remotes/realtarget/main"


def _g(*args) -> str:
    try:
        r = subprocess.run(["git", *args], capture_output=True, cwd=str(WS))
        return r.stdout.decode("utf-8", "replace").strip()
    except Exception:  # noqa: BLE001
        return ""


def _jsonl(p: pathlib.Path) -> list:
    if not p.is_file():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:  # noqa: BLE001
            continue
    return out


def rule4() -> dict:
    """铁律4 双仓不许搞错：origin 必须是私有仓。"""
    url = _g("remote", "get-url", "origin")
    ok = PRIVATE_MUST in url
    return {"ok": ok, "origin": url or "(无)",
            "gap": "" if ok else "origin 不是 %s —— 双仓搞错了，推错地方就是生产事故" % PRIVATE_MUST}


def rule5() -> dict:
    """铁律5 非法路径零容忍（冒号/反斜杠/绝对路径 ⇒ Windows 无法检出）。"""
    checked, bad = [], []
    for ref in ("HEAD", PUBLIC_REF):
        if not _g("rev-parse", "--verify", ref):
            continue
        checked.append(ref)
        r = subprocess.run(["git", "ls-tree", "-r", "-z", "--name-only", ref],
                           capture_output=True, cwd=str(WS))
        for raw in r.stdout.split(b"\0"):
            if not raw:
                continue
            s = raw.decode("utf-8", "surrogateescape")
            if ":" in s or "\\" in s or s.startswith("/"):
                bad.append("%s:%s" % (ref, s[:70]))
    if not checked:
        return {"ok": False, "checked": [], "bad": [], "gap": "一个 ref 都读不到"}
    return {"ok": not bad, "checked": checked, "bad": bad[:5],
            "gap": ("%d 个非法路径，仓在 Windows 上无法检出" % len(bad)) if bad else ""}


def rule6() -> dict:
    """铁律6 抽屉有上限：scan-*.json ≤ KEEP_SCANS（环形保留无条件执行）。"""
    if not HB_STATE.is_dir():
        return {"ok": True, "scans": 0, "gap": "抽屉还没建（首跳自建）"}
    keep = 20
    try:
        sys.path.insert(0, str(WS))
        from gbt_allinone.heartbeat_tentacle import KEEP_SCANS as keep  # noqa: PLC0415
    except Exception:  # noqa: BLE001
        pass
    n = len(list(HB_STATE.glob("scan-*.json")))
    return {"ok": n <= keep, "scans": n, "keep": keep,
            "gap": ("%d 份 > 上限 %d —— 环形保留没在跑" % (n, keep)) if n > keep else ""}


def rule7() -> dict:
    """铁律7 跳过≠通过：ok=None 必须配 deep 记账，否则 12/12 绿是"没测的绿"。"""
    f = HB_STATE / "latest.json"
    if not f.is_file():
        return {"ok": True, "gap": "还没打过心跳（无读数可查）"}
    try:
        d = json.loads(f.read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        return {"ok": False, "gap": "latest.json 不是合法 JSON"}
    if "deep" not in d:
        return {"ok": False, "gap": "报告没有 deep 记账 —— 跳过就等于通过（假绿）"}
    skipped = [c for c, st in (d.get("statuses") or {}).items()
               if ((st.get("checks") or {}).get("probe") or {}).get("ok") is None]
    return {"ok": True, "skipped_categories": skipped,
            "deep_ever": (d.get("deep") or {}).get("ever")}


def rule8() -> dict:
    """铁律8 只测绿等于没测：必须有负控用例。"""
    try:
        src = HB_TESTS.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return {"ok": False, "gap": "护栏测试文件不在"}
    has_neg = ("NegativeControl" in src) or ("负控" in src)
    has_red = ('"red"' in src) or ("'red'" in src)
    return {"ok": has_neg and has_red,
            "negative_control": has_neg, "red_assertion": has_red,
            "gap": "" if (has_neg and has_red) else "缺负控或缺判红断言 —— 只测绿等于没测"}


def rule9() -> dict:
    """铁律9 护栏只增不减（基线存 state/iron-rules-baseline.json）。"""
    try:
        src = HB_TESTS.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return {"ok": False, "gap": "护栏测试文件不在"}
    n = len(re.findall(r"^    def test_", src, re.M))
    base = {}
    if IRON_BASELINE.is_file():
        try:
            base = json.loads(IRON_BASELINE.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            base = {}
    prev = int((base or {}).get("guardrail_count") or 0)
    if n < prev:
        return {"ok": False, "now": n, "baseline": prev,
                "gap": "护栏从 %d 掉到 %d —— 有用例被删了" % (prev, n)}
    if n > prev:
        try:
            IRON_BASELINE.parent.mkdir(parents=True, exist_ok=True)
            base["guardrail_count"] = n
            IRON_BASELINE.write_text(json.dumps(base, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    return {"ok": True, "now": n, "baseline": prev or "本次建立"}


def rule10() -> dict:
    """铁律10 缺字段≠假：不许替调用方编造"从未深检"。"""
    try:
        sys.path.insert(0, str(WS))
        from gbt_allinone import brain_exec as _be  # noqa: PLC0415
        adv = _be.advise({"taxonomy": {"ok": True}, "signals": []})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "gap": "调不起来：%s: %s" % (type(e).__name__, str(e)[:60])}
    ids = [x.get("id") for x in (adv.get("instructions") or [])]
    bad = [i for i in ids if i in ("never_deep_checked", "deep_check_stale")]
    return {"ok": not bad, "instructions": ids,
            "gap": ("缺 deep 却被判成深检缺失：%s" % bad) if bad else ""}


def rule11() -> dict:
    """铁律11 同一个全局根因只开一张单。"""
    try:
        sys.path.insert(0, str(WS))
        from gbt_allinone import brain_exec as _be  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "gap": "调不起来：%s" % type(e).__name__}
    fake = {"taxonomy": {"ok": True}, "signals": [
        {"level": "P0", "code": "persist_failed", "category": c,
         "tentacle": "heartbeat-%s" % c, "msg": "写不进"}
        for c in ("身", "感", "知", "言", "造", "工", "察", "守", "调", "数", "群", "进")]}
    adv = _be.advise(fake)
    hits = [x for x in (adv.get("instructions") or []) if x.get("id") == "persist_failed"]
    return {"ok": len(hits) == 1, "tickets": len(hits),
            "gap": ("12 条同源信号开出 %d 张单，必须 1 张" % len(hits)) if len(hits) != 1 else ""}


def rule12() -> dict:
    """铁律12 闭环端到端接上：常驻循环必须真调 act() 并记 acted。"""
    try:
        src = (WS / "tools" / "codex-scripts" / "monitor-loop.py").read_text(
            encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return {"ok": False, "gap": "monitor-loop.py 读不到"}
    calls = "_be.act(" in src
    records = '"acted"' in src
    return {"ok": calls and records, "calls_act": calls, "records_acted": records,
            "gap": "" if (calls and records) else "常驻循环没真执行指令 —— 闭环只是纸面上的"}


_NEW_RULES = [
    ("铁律4·双仓不许搞错", rule4),
    ("铁律5·非法路径零容忍", rule5),
    ("铁律6·抽屉有上限", rule6),
    ("铁律7·跳过≠通过", rule7),
    ("铁律8·必须有负控", rule8),
    ("铁律9·护栏只增不减", rule9),
    ("铁律10·缺字段≠假", rule10),
    ("铁律11·全局根因单票", rule11),
    ("铁律12·闭环真接上", rule12),
]


# --quick 跳过的条目：只跳**贵的**，不跳重要的。
# 实测逐条耗时：铁律2（全仓 rglob 扫活跃脚本）2382ms，其余合计约 500ms。
# 开工自检每秒都值钱，所以 quick 只跳它；铁律5（非法路径，266ms）留着 —— 那是能把仓写坏的那条。
QUICK_SKIP = frozenset({"铁律2·必须带参"})


def check(quick: bool = False) -> dict:
    parts = {"铁律1·禁止脑补": rule1(), "铁律2·必须带参": rule2(), "铁律3·先纠错再回答": rule3()}
    parts.update({name: fn() for name, fn in _NEW_RULES})
    skipped = []
    if quick:
        skipped = [k for k in parts if k in QUICK_SKIP]
        for k in skipped:
            parts.pop(k)
    bad = [k for k, v in parts.items() if not v.get("ok")]
    return {"ok": not bad, "parts": parts, "bad": bad, "quick_skipped": skipped}


def selftest() -> int:
    ok = []
    r2 = rule2()
    ok.append(("真件·铁律2 能扫活跃脚本", isinstance(r2.get("calls"), int), "%d 处调用" % r2.get("calls")))
    # 真植入负控：一个没有 --name 的 wrangler 调用必须被抓
    probe = 'wrangler deployments list'
    ok.append(("真植入负控·无 --name 的调用必须被抓",
               bool(WRANGLER_CALL.search(probe)) and not HAS_NAME.search(probe), probe))
    good = 'wrangler deployments list --name gbt-potato-cloud-10'
    ok.append(("真植入正控·带 --name 的不该被抓",
               bool(WRANGLER_CALL.search(good)) and bool(HAS_NAME.search(good)), good))
    # 文档里的反引号示例**不该**被算作调用（ACTIVE_EXT 不含 .md）
    ok.append(("真植入负控·.md 不在扫描面（防假红）", ".md" not in ACTIVE_EXT, str(ACTIVE_EXT)))
    r1 = rule1()
    ok.append(("真件·铁律1 能读声明形状", isinstance(r1.get("claims"), int), "%d 条" % r1.get("claims")))
    r3 = rule3()
    ok.append(("真件·铁律3 纠正台账可判", isinstance(r3.get("ok"), bool), "n=%s" % r3.get("n")))
    bad = [n for n, c, _ in ok if not c]
    for n, c, d in ok:
        print("  %-46s %s  (%s)" % (n, "✅" if c else "❌", d))
    print("")
    print("iron-rules-check 自检: %s（%d 条）"
          % ("全部通过" if not bad else "%d 条失败" % len(bad), len(ok)))
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="铁律 1~12 的机器判据")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--quick", action="store_true",
                    help="跳过贵的条目（铁律2 全仓扫描 2.4s），供开工自检调用")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    r = check(quick=a.quick)
    # 🔴 2026-10-30 修：`--json` 原来是"先打人读文本、再把 JSON 接在后面"
    #    ⇒ stdout 根本不是合法 JSON，下游 `json.load` 报 `Expecting value: line 1 column 1`。
    #    跟 heartbeat CLI 同一个病（那次也是这个错）。现在 --json 时**只打 JSON**，
    #    散文一律不打 —— 机器读的东西不许掺人话。
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["ok"] else 1
    print("=" * 76)
    print("铁律审查（1~3 主人令 2026-10-11 · 4~12 主人令 2026-10-30）")
    print("=" * 76)
    if r.get("quick_skipped"):
        print("  （--quick 跳过：%s）" % "、".join(r["quick_skipped"]))
    for name, v in r["parts"].items():
        mark = "✅" if v.get("ok") else "🔴"
        print("  %s %s" % (mark, name))
        for k, vv in v.items():
            if k in ("ok",):
                continue
            if isinstance(vv, list) and vv:
                print("      %s:" % k)
                for x in vv[:6]:
                    print("        %s" % x)
            else:
                print("      %s: %s" % (k, vv))
    print("")
    print("  结论：%s" % ("**全绿**" if r["ok"] else "**红：%s**" % "、".join(r["bad"])))
    print("")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
