#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""**注入面诚实性审计器** —— 把「喂给模型的每一段字都得是真的」变成一条常设判据。

为什么要有它（一手账，都在本仓）：
  2026-09-25 一天之内，**同一族病**在「注入给模型的文本」上连撞四处，每处都是
  「看着没问题、其实在编」：

    ① 三个能力总数打架 —— 标题 118 / 索引表 0 / 真值 172（`cloud_llm._build_system`）
    ② 两条调用法是死的 —— `python caps/<cap_id>/run.py`（全库只有 1 个 run.py）+ n8n 5678 无监听
    ③ 自我认知点名的自检命令自己崩 —— `awareness_gap_guard` KeyError
    ④ 安全段是假的 —— 从**不存在的** `brain.cognition` 取，prompt 里 14 个真作用域命中 0 个

  四处都是**分别手修**的。手修的问题是：**下一个新注入块没人管**。
  而这个仓的既定口径是「判据立了不等于门关上了」——
  ⇒ 所以把四处的判据收成**一条跑得动的审计**，覆盖**所有**注入块（含将来新增的）。

它查什么（每条都能指到具体一行/一个字段）：
  A. `python <路径>` —— 那个文件必须在盘上
  B. `python -m <模块或包>` —— `.py` 或 `<包>/__init__.py` 必须在盘上
  C. `N个cap / N个能力位` —— 必须等于活注册表条数（`caps_registry.BENIGN_CAPS`）
  D. 历史硬编码计数（118/158/110/119）不许出现在注入文本里
  E. 自称在讲授权门时，`security/policy.py` 的**每一个**作用域都必须点到

用法：
  python tools/codex-scripts/audit-injection-honesty.py            # 人读
  python tools/codex-scripts/audit-injection-honesty.py --json     # 机读
退出码：0 = 全部诚实；1 = 有假账（逐条列出"哪一段、哪一句、为什么假"）。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gbt_allinone.caps_registry import BENIGN_CAPS          # noqa: E402
from gbt_allinone.security import policy as POLICY          # noqa: E402

PROBE = ROOT / "plugins" / "gbt-master" / "tools" / "verify-state-injection.mjs"

RE_PATH = re.compile(r"\bpython\s+((?:[\w.\-]+[\\/])*[\w.\-]+\.(?:py|cjs|js))\b")
# 🔴 2026-09-25 当场修我自己的假阳性（**首跑就撞上**）：
#   原来写的是 `([\w.]+)` ⇒ `\w` **吃中日韩汉字** ⇒ 台账里那句散文
#   「修我自己一条过窄判据（python -m 包 vs 模块）」被解析成
#   `python -m 包` ⇒ 报「模块/包不存在：包」。**这是"把提到当成用了"的又一例**
#   （本仓 FR-1 同族）。模块名只可能是 ASCII 标识符 ⇒ 收紧字符类。
RE_MOD = re.compile(r"\bpython\s+-m\s+([A-Za-z_][A-Za-z0-9_.]*)")
RE_COUNT = re.compile(r"(\d+)\s*个\s*(?:cap|能力位)")
RE_LEGACY = ("118", "158", "110", "119")
# **自称在讲授权门**才算"该把作用域点全"：只认这种明确的枚举声明，
# 不认"文中出现过『作用域』这个词"—— 否则任何提到"作用域"的散文都会被判假。
RE_GATE_CLAIM = re.compile(r"(唯一授权门|需要人工授权的作用域\s*[（(]\s*\d+\s*个)")
# 引号/反引号里的东西是**引述**，不是声称（"提到 ≠ 用了"）：
_QUOTED = re.compile(r"`[^`]*`|\"[^\"]*\"|'[^']*'|「[^」]*」|【[^】]*】|（[^）]*）|\([^)]*\)")


def _unquote(text: str) -> str:
    """把**引述**部分挖掉，只留"它在声称什么"。"""
    return _QUOTED.sub(" ", text)


def _exists_path(rel: str) -> bool:
    return (ROOT / rel).is_file()


def _exists_module(mod: str) -> bool:
    """`python -m <名>`：**模块**（`<名>.py`）或**包**（`<名>/__init__.py`）都算存在。

    ⚠️ 这条第一版只认模块 ⇒ 对合法的 `python -m gbt_allinone` 判红（判据的错，不是那行的错）。
    """
    base = ROOT.joinpath(*mod.split("."))
    return base.with_suffix(".py").is_file() or (base / "__init__.py").is_file()


def check_block(source: str, text: str) -> list:
    """对一段注入文本做全部检查。返回问题列表（空 = 诚实）。

    🔴 首跑就被自己的假阳性打回（三条），根都是同一句话：**"提到 ≠ 用了"**。
       修法见上面三条正则旁的注释 —— 判据必须分得清「它在**声称**什么」
       和「它在**引述/解释**什么」，否则审计器自己就成了错报源。
    """
    bad = []
    said = _unquote(text)          # 「声称」面：挖掉引号/括号里的引述
    for p in sorted(set(RE_PATH.findall(said))):
        if not _exists_path(p):
            bad.append({"source": source, "rule": "A/路径不存在", "detail": p})
    for m in sorted(set(RE_MOD.findall(said))):
        if not _exists_module(m):
            bad.append({"source": source, "rule": "B/模块或包不存在", "detail": m})

    real = len(BENIGN_CAPS)
    for n in sorted(set(int(x) for x in RE_COUNT.findall(said))):
        if n != real:
            bad.append({"source": source, "rule": "C/能力总数与活注册表不符",
                        "detail": "文本说 %d，活注册表是 %d" % (n, real)})

    for tok in RE_LEGACY:
        if re.search(r"(?<![\d.])" + tok + r"(?![\d])", said):
            bad.append({"source": source, "rule": "D/历史硬编码计数", "detail": tok})

    if RE_GATE_CLAIM.search(said):
        missing = [s for s in POLICY.SCOPE_DESCRIPTIONS if s not in text]
        if missing:
            bad.append({"source": source, "rule": "E/自称在讲授权门却没点全作用域",
                        "detail": "缺 %d 个：%s" % (len(missing), missing[:6])})
    return bad


def collect_blocks() -> tuple:
    """(块列表, 诊断)。块 = 插件三块（走仓里既有的探针，不另造 ctx 假件）+ LLM system prompt。"""
    blocks, diag = [], []
    if PROBE.is_file():
        try:
            r = subprocess.run(["node", str(PROBE), "--json"], cwd=str(ROOT), capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=180)
            raw = (r.stdout or "")
            i = raw.find('{"runs"')
            if i < 0:
                diag.append("探针没吐出可解析的 JSON（stderr: %s）" % (r.stderr or "")[:120])
            else:
                data = json.loads(raw[i:])
                for run in data.get("runs", []):
                    for b in run.get("blocks", []):
                        blocks.append(("插件块 %s ［%s］" % (b.get("name"), run.get("tag")),
                                       str(b.get("text") or "")))
        except Exception as e:                                   # noqa: BLE001
            diag.append("探针跑不动：%s: %s" % (type(e).__name__, str(e)[:120]))
    else:
        diag.append("探针不在：%s" % PROBE)
    try:
        from gbt_allinone.llm import cloud_llm as cl
        blocks.append(("LLM system prompt", cl._build_system()))
    except Exception as e:                                       # noqa: BLE001
        diag.append("system prompt 取不到：%s: %s" % (type(e).__name__, str(e)[:120]))
    return blocks, diag


def audit() -> dict:
    blocks, diag = collect_blocks()
    problems = []
    for source, text in blocks:
        problems.extend(check_block(source, text))
    return {
        "ok": True, "readonly": True,
        "blocks": len(blocks),
        "block_names": [s for s, _ in blocks],
        "real_cap_total": len(BENIGN_CAPS),
        "real_scopes": sorted(POLICY.SCOPE_DESCRIPTIONS),
        "problems": problems,
        "problem_count": len(problems),
        "diagnostics": diag,
        "note": ("只查**可机判**的四类：盘上有没有那个路径/模块 · 能力总数对不对 · "
                 "有没有历史硬编码计数 · 自称讲授权门时作用域点全了没。"
                 "**不判**叙述好不好、坑写得准不准 —— 那些留给人看。"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="注入面诚实性审计（只读）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rep = audit()
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print("═══ 注入面诚实性审计 · %s ═══" % ROOT)
        print("查了 %d 段注入：%s" % (rep["blocks"], " ｜ ".join(rep["block_names"])))
        print("口径：活注册表 %d 位 · 真门 %d 个作用域"
              % (rep["real_cap_total"], len(rep["real_scopes"])))
        for d in rep["diagnostics"]:
            print("  ⚠ %s" % d)
        if rep["problems"]:
            print("\n🔴 假账 %d 条：" % rep["problem_count"])
            for p in rep["problems"]:
                print("  [%s] %s —— %s" % (p["rule"], p["source"], p["detail"]))
        else:
            print("\n✅ 0 条假账（各段注入里的路径/模块/计数/作用域都对得上盘上真身）")
        print("\n边界：%s" % rep["note"])
    return 1 if rep["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
