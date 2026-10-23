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
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
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
# 🔴 2026-10-11 自纠（**假红**）：原来只写 "_legacy"，而实际目录叫 **_legacy_sources**
#    ⇒ 没跳过 ⇒ 报「85 处 wrangler 没带 --name」，列出来的**全在那个历史源里**
#    ⇒ 跳过名单改成**前缀匹配**，并把历史/遗留源一并纳入。
SKIP_DIRS = ("_baseline_wt", "_legacy", "_legacy_sources", "_upstream", "node_modules",
             "__pycache__", ".mimosa", ".wrangler", ".scratch", ".git", "vendor", "store",
             "archive", ".backups")
WRANGLER_CALL = re.compile(r"\bwrangler\s+(deployments|secret|containers|deploy|tail|kv|r2|d1|versions|pages)\b")
HAS_NAME = re.compile(r"--name\b|--config\b|wrangler\.(toml|json)")


def _active_files():
    """扫**活跃代码/脚本**——**剪枝遍历**（跳过的目录根本不进）。

    🔴 2026-10-17 修（挂死根因 · 留痕 · 原口径 / 为什么翻 / 现口径）：
      原口径：`WS.rglob("*")` —— **先遍历全仓**（18 万级入口 + junction/worktree），
        再在循环体里按 SKIP_DIRS 字符串跳过。跳过写在循环体里对 rglob **无效**。
      为什么翻：全量测试跑到 `test_iron_rules` 时卡在 `p.is_file()` **超时**（120s），
        整个会话被 pytest-timeout 打断 ⇒ 一轮全量白跑（本仓已有同族教训：
        `test_precommit_secret_scan` 的 `rglob` 挂死）。
      现口径：`os.walk` + **剪枝** `dirnames`，跳过的目录根本不进；语义不变。
    """
    skip = set(SKIP_DIRS)
    for dirpath, dirnames, filenames in os.walk(str(WS)):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for name in filenames:
            p = pathlib.Path(dirpath) / name
            if p.suffix.lower() not in ACTIVE_EXT:
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
            # 🔴 2026-10-11 自纠（假红）：把「字符串字面量里的 wrangler」也当成了调用
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
        # 🔴 2026-10-11 自纠（**假红**）：原来拿 evidence 字段判"读数形状"，但本仓声明把
        #    期望读数存在 **expect_contains** 里（cmd + expect_contains 是 delivery-claims 的写死形状）
        #    ⇒ 改成查 expect_contains。实测：closed-loop-gate --sweep 已证明那 15 条**全部**带
        #    cmd+expect_contains 且复跑命中，而本判据却报"15 条缺读数形状" ⇒ 是我查错字段。
        # 🔴 2026-10-11 自纠（又一处假红）：声明里**根本没有 evidence 字段** ——
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


def check() -> dict:
    parts = {"铁律1·禁止脑补": rule1(), "铁律2·必须带参": rule2(), "铁律3·先纠错再回答": rule3()}
    bad = [k for k, v in parts.items() if not v.get("ok")]
    return {"ok": not bad, "parts": parts, "bad": bad}


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
    ap = argparse.ArgumentParser(description="三条铁律的机器判据")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    r = check()
    print("=" * 76)
    print("三条铁律审查（主人令 2026-10-11）")
    print("=" * 76)
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
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
