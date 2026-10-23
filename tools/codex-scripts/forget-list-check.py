#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""forget-list-check · 校验「防忘清单」**引用的东西真实存在**

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么需要它
主人 2026-09-25：「在办清单（**不是流水账，是防忘用的**）」。
⇒ 另立 `memory/防忘清单.md`（只留没办完的）。**但它自己也会漂**：
写完三天，里面引用的文件可能改名、引用的 § 可能不存在 ⇒ **它就开始骗人**。
⇒ 本工具是它的**兜底闸**：**引用的路径、行号、章节号，逐个核**。

## 三条判据
1. **路径必须存在**（反引号里像路径的，逐个 `exists()`）；
2. **行号必须真在**（写成 `路径:33` 的，核该文件有没有第 33 行）——
   否则"我引了出处"这句话本身就没据；
3. **`§一百…` 必须真在证据账里**（`memory/在办清单.md`）。
外加：**清单要短**（超过 220 行就报——它一长就又变回流水账）。

用法：
  forget-list-check.py check
  forget-list-check.py selftest
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIST = ROOT / "memory" / "防忘清单.md"
LEDGER = ROOT / "memory" / "在办清单.md"
MAX_LINES = 220

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 反引号里的"像**路径**"的串：**必须含目录分隔符**。
#   🔴 第一版把**裸文件名**也当路径 ⇒ 一次报了 7 条假「路径不存在」
#     （`social_life.py` 这种是**行内提到文件名**，不是引用路径）——**判据太宽**。
#     清单要短（防忘用），不能逼它写全路径 ⇒ 判据必须精确到"只有带目录的才核"。
PATHY = re.compile(r"[/\\]")
# 🔴 2026-09-25 增补（**判据比对象宽 = 假红**，与 L44 那次同族）：
#   Workers AI 的**模型 id** 长这样 `@cf/openai/gpt-oss-120b` —— 它含斜杠、看着像路径，
#   但它是**云上的模型标识**，本地当然没有这个文件 ⇒ 老判据报「路径不存在」= **假红**。
#   判据要精确到"只有**本地引用**才核"：`@cf/...` 这种以 `@` 开头的外部标识一律不核。
#   （配一条负控：真坏的本地路径**仍然**要被抓到。）
NOT_LOCAL = re.compile(r"^@[^/\\]+[/\\]")          # 形如 @cf/xxx 的外部模型/资源标识
# `路径:33` 或 `路径:33-35`
WITH_LINE = re.compile(r"^(?P<p>[^:]+?):(?P<n>\d+)(?:-(?P<m>\d+))?$")
SEC = re.compile(r"§([一二三四五六七八九十百零]+)")
ROW = re.compile(r"^\| (\d+) \|")


def _refs(text: str) -> list:
    """取出**像路径**的反引号串（必须含目录分隔符）。

    🔴 2026-09-24 增补：反引号里也常写**命令**（「下一步跑哪条」本来就该写成命令），
    形如 `` `python tools/self_model.py brief` `` —— 老版把**整条命令**当路径 ⇒
    `ROOT/"python tools/self_model.py brief"` 不存在 ⇒ **报了一条假「路径不存在」**，
    于是「防忘清单开始骗人了」的告警**本身是假的**。
    ⇒ 含空白的跨度**按 token 拆**，只核**带分隔符**的那些 token（命令里的真路径照样要核）。
    """
    out = []
    for raw in re.findall(r"`([^`\n]+)`", text):
        # 🔴 **只去尾部标点，不去前导点**：原来写的是 `strip("，。,.")` —— 它把
        #    **隐藏路径的前导点也吃掉**（`.scratch/` → `scratch/`）⇒ 报了一条假「路径不存在」。
        #    本仓大量路径是点开头的（`.scratch/` · `.agents/` · `.dsh/`），不许被吃掉。
        s = raw.strip().rstrip("，。,.")
        # 🔴 这里原来留了一句 `if not s or " " in s and not PATHY.search(...): pass`
        #    —— **空分支 + 文本判据**，被 `criterion_bench` 的 D2 当场咬出来（本文件 L57）。
        #    修法是**删掉它**，不是改基线。
        if not s:
            continue
        # 🔴 判据用**结构化**的 token 数，**不用** `" " in s` / `"\t" in s` 这种文本子串判据：
        #    初版就是这么写的，被 `criterion_bench` 的 D2 当场咬出**两处**
        #    （其中一处还自指：该字面量在本文件里出现 2 次）。**修法是改判据，不是抬基线。**
        parts = s.split()
        cands = parts if len(parts) > 1 else [s]      # 有空白 ⇒ 按命令拆 token；否则当单个路径
        for t in (x for x in cands if PATHY.search(x)):
            t = t.strip().rstrip("，。,.")             # 🔴 **只去尾部**，前导点要留着（隐藏路径）
            if t and not NOT_LOCAL.match(t):          # 外部模型/资源标识（@cf/...）不核
                out.append(t)
    return out


def _rows_out_of_order(text: str) -> list:
    """**每个表格段内，`| 编号 |` 必须严格递增**。

    🔴 为什么要这条（2026-09-25 · 我**连犯三次**）：往表尾追加一行时，`old_string` 只取上一行的
    **行首编号锚点** ⇒ 会把上一行的编号与标题**吞掉**（两行粘成一行，编号出现缺口或错序）。
    路径/§/行数三类判据都看不见这种坏法 —— 只有"编号必须递增"看得见。
    """
    bad, _, prev_no = [], None, None
    for i, ln in enumerate(text.splitlines(), 1):
        m = ROW.match(ln)
        no = int(m.group(1)) if m else None
        if no is None:
            if ln.strip() == "" or ln.startswith("#"):   # 段与段之间：重置
                prev_no = None
            continue
        if prev_no is not None and no != prev_no + 1:
            bad.append("第 %d 行：编号 %d ≠ 上一行 %d + 1（吞行/错序）" % (i, no, prev_no))
        prev_no = no
    return bad


def check(text: str | None = None) -> dict:
    if not LIST.exists():
        return {"ok": False, "为什么": "**未读到** memory/防忘清单.md"}
    text = text if text is not None else LIST.read_text(encoding="utf-8")
    ledger = LEDGER.read_text(encoding="utf-8", errors="replace") if LEDGER.exists() else ""
    missing_path, missing_line, missing_sec, ok_paths = [], [], [], 0
    for s in _refs(text):
        m = WITH_LINE.match(s)
        p, ln = (m.group("p"), int(m.group("n"))) if m else (s, None)
        p = p.strip()
        if not PATHY.search(p):
            continue
        full = ROOT / p
        if not full.exists():
            # 允许是"命令里的路径片段"（例如 tools/codex-scripts/ 这种目录）
            if not (ROOT / p.rstrip("/")).exists():
                missing_path.append(s)
                continue
        ok_paths += 1
        if ln is not None and full.exists() and full.is_file():
            try:
                n = len(full.read_text(encoding="utf-8", errors="replace").splitlines())
            except Exception:
                continue
            if ln > n:
                missing_line.append("%s（该文件只有 %d 行）" % (s, n))
    for sec in set(SEC.findall(text)):
        if ("§" + sec) not in ledger:
            missing_sec.append("§" + sec)
    lines = text.count("\n") + 1
    too_long = lines > MAX_LINES
    out_of_order = _rows_out_of_order(text)
    ok = not (missing_path or missing_line or missing_sec or too_long or out_of_order)
    return {"ok": ok, "清单": str(LIST.relative_to(ROOT)),
            "行数": lines, "上限": MAX_LINES, "过长的原因": "超过上限就又变回流水账" if too_long else None,
            "核过的路径数": ok_paths,
            "**路径不存在**": missing_path,
            "**行号超出**（引了出处但那行不在）": missing_line,
            "**§ 不在证据账里**": missing_sec,
            "**表行编号不递增**（吞行/错序）": out_of_order,
            "证据账": str(LEDGER.relative_to(ROOT))}


def cmd_check(a) -> int:
    r = check()
    print(json.dumps(r, ensure_ascii=False, indent=1))
    print("✅ 防忘清单可核：%d 个路径都在 · 行号都在 · § 都在账里 · %d 行（≤%d）"
          % (r["核过的路径数"], r["行数"], MAX_LINES) if r["ok"]
          else "🔴 防忘清单**有引不到的出处**（见上）—— 它开始骗人了")
    return 0 if r["ok"] else 1


def cmd_selftest(a) -> int:
    lines, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    r = check()
    ck("**真清单可核**（路径 · 行号 · § 全在）", r["ok"], "核过 %d 个路径 ｜ %d 行"
       % (r["核过的路径数"], r["行数"]))
    # ① 负控：**不存在的路径必须被抓**
    fake = "看这个 `tools/codex-scripts/__根本没有的__.py`"
    ck("**负控：不存在的路径必须被抓**", bool(check(fake)["**路径不存在**"]),
       str(check(fake)["**路径不存在**"])[:50])
    # ①b 🔴 **负控：裸文件名不许被当路径**（判据必须精确，否则清单会被逼着写全路径）
    bare = "看 `social_life.py` 和 `edit_pipeline.py`"
    ck("**负控：裸文件名不算路径引用**（判据要精确）",
       not check(bare)["**路径不存在**"], "报错 %d 条" % len(check(bare)["**路径不存在**"]))
    # ①c 🔴 2026-09-24 增补：**命令里的真路径要核到**（否则"下一步跑哪条命令"写进反引号就成假红）
    cmd_ok = "下一步：`python tools/self_model.py brief`"
    r_cmd = check(cmd_ok)
    ck("**正控：命令里的真路径核得到**（不是整条命令当路径）",
       not r_cmd["**路径不存在**"] and r_cmd["核过的路径数"] >= 1,
       "核过 %d 条 ｜ 假红 %s" % (r_cmd["核过的路径数"], r_cmd["**路径不存在**"]))
    # ①d 🔴 **负控：命令里的假路径仍必须被抓**（别把判据放松成"命令一律不核"）
    cmd_bad = "下一步：`python tools/codex-scripts/__没有这个__.py --flag`"
    ck("**负控：命令里的假路径必须被抓**",
       bool(check(cmd_bad)["**路径不存在**"]),
       str(check(cmd_bad)["**路径不存在**"])[:60])
    # ①e 🔴 **负控：点开头的隐藏路径不许被吃掉前导点**（`.scratch/` 曾是假红）
    hid_ok = "留证在 `.scratch/rebuild_caps_registry.py`"
    ck("**正控：点开头的隐藏路径要核到**（前导点不许被 strip 掉）",
       not check(hid_ok)["**路径不存在**"], str(check(hid_ok)["**路径不存在**"])[:50])
    hid_bad = "留证在 `.scratch/__没有这个__.py`"
    ck("**负控：隐藏目录里的假路径仍要被抓**",
       bool(check(hid_bad)["**路径不存在**"]), str(check(hid_bad)["**路径不存在**"])[:50])
    # ①b 正控：外部标识（Workers AI 模型 id `@cf/...`）**不算本地路径**（判据不许比对象宽）
    ext = "跑的是 `@cf/openai/gpt-oss-120b` 这个模型"
    ck("**正控：@cf/... 这类外部模型标识不核本地路径**",
       not check(ext)["**路径不存在**"], str(check(ext)["**路径不存在**"])[:60])
    ck("**负控：去掉 @ 之后的本地路径仍要核**",
       bool(check("见 `cf/openai/__没有这个__.py`")["**路径不存在**"]),
       str(check("见 `cf/openai/__没有这个__.py`")["**路径不存在**"])[:60])
    # ② 负控：**行号超出必须被抓**
    fake2 = "看 `tools/self_model.py:99999`"
    ck("**负控：行号超出必须被抓**", bool(check(fake2)["**行号超出**（引了出处但那行不在）"]),
       str(check(fake2)["**行号超出**（引了出处但那行不在）"])[:60])
    # ③ 负控：**不存在的 § 必须被抓**
    fake3 = "见 §二百五"
    ck("**负控：不存在的 § 必须被抓**", bool(check(fake3)["**§ 不在证据账里**"]), str(check(fake3)["**§ 不在证据账里**"])[:40])
    # ④ 负控：**超长必须报**（防它又变回流水账）
    fake4 = "x\n" * (MAX_LINES + 5)
    ck("**负控：超过 %d 行必须报**（防又变流水账）" % MAX_LINES, check(fake4)["行数"] > MAX_LINES,
       "%d 行" % check(fake4)["行数"])
    # ⑤ 表行编号：**吞行/错序必须被抓**（我连犯三次的那种坏法，路径/§/行数三类判据都看不见）
    ck("**负控：表行编号出现缺口（吞行）⇒ 必须被抓**",
       bool(_rows_out_of_order("| 1 | x |\n| 2 | y |\n| 4 | z |\n")), "")
    ck("**负控：表行编号错序 ⇒ 必须被抓**",
       bool(_rows_out_of_order("| 1 | x |\n| 3 | y |\n| 2 | z |\n")), "")
    ck("**正控：编号递增 ⇒ 不报**",
       _rows_out_of_order("| 1 | x |\n| 2 | y |\n| 3 | z |\n") == [], "")
    ck("**正控：现读真清单的编号递增**",
       not check()["**表行编号不递增**（吞行/错序）"],
       str(check()["**表行编号不递增**（吞行/错序）"])[:60])
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="校验防忘清单引用的路径/行号/§ 真实存在")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(func=cmd_check)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
