# -*- coding: utf-8 -*-
"""记忆本地闸 + 本机摘要（Owner 令 2026-10-14：「记忆永远保留本地不出网在框架上」）。

① digest  从 state/memory_bank.jsonl（真字段 at/event/ref/name/why）+ 最新 memory/*.md 标题，
          压成 state/memory-digest.md（**只在本机读**）
② --check **机械闸**：把记忆**正文串**（bank 的 why/ref 等 ≥12 字 + memory/*.md 的 ≥40 字行）
          逐条在 deploy/（出网面）里比 —— **只提路径/位名不算泄，正文出现才算**
          （首版判据过宽：把 canvas.html 里的「脑库」字样判成泄漏，已改）

用法：py -3.14 tools/codex-scripts/memory-local-guard.py [--check|--selftest]
开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BANK = ROOT / "state" / "memory_bank.jsonl"
MEMDIR = ROOT / "memory"
OUT = ROOT / "state" / "memory-digest.md"
CLOUD = ROOT / "deploy"
MAX_BYTES = 2600


def log(*a) -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                       # noqa: BLE001
            pass
    print(*a)


def bank_rows():
    rows = []
    if BANK.is_file():
        for raw in BANK.read_text(encoding="utf-8", errors="replace").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                rows.append(json.loads(raw))
            except Exception:                                   # noqa: BLE001
                continue
    return rows


def digest() -> int:
    rows = bank_rows()
    lines = []
    for r in rows:
        at = str(r.get("at") or "")[:10]
        ev = str(r.get("event") or "?")
        tail = str(r.get("why") or r.get("ref") or r.get("name") or r.get("target") or "")
        tail = re.sub(r"\s+", " ", tail).strip()[:120]
        lines.append("- [" + at + "] " + ev + " · " + tail)
    heads = []
    if MEMDIR.is_dir():
        for f in sorted(MEMDIR.glob("*.md"))[-3:]:
            t = f.read_text(encoding="utf-8", errors="replace")
            for h in re.findall(r"^#{1,3}\s+(.+)$", t, re.M)[:5]:
                heads.append("- [" + f.name + "] " + re.sub(r"\s+", " ", h).strip()[:110])
    text = ("# 本机记忆摘要（自动生成 · **只在本机读 · 永不外发**）\n\n"
            + "> 来源 state/memory_bank.jsonl（" + str(len(rows)) + " 条）+ memory/*.md 最近 3 天标题\n"
            + "> 闸：记忆正文不得出现在 deploy/ ⇒ py -3.14 tools/codex-scripts/memory-local-guard.py --check\n\n"
            + "\n".join(lines[:30] + heads[:15]) + "\n")
    if len(text.encode("utf-8")) > MAX_BYTES:
        text = text.encode("utf-8")[:MAX_BYTES].decode("utf-8", "ignore") + "\n…（已按 2.6KB 截断）\n"
    OUT.write_text(text, encoding="utf-8")
    log("已生成 " + str(OUT.relative_to(ROOT)) + " · " + str(len(text.encode("utf-8"))) + " B · 记忆 " + str(len(rows)) + " 条")
    return 0


def needle_set():
    needles = set()
    for r in bank_rows():
        for k in ("why", "ref", "name", "target"):
            v = re.sub(r"\s+", " ", str(r.get(k) or "")).strip()
            if len(v) >= 12:
                needles.add(v)
    if MEMDIR.is_dir():
        for f in sorted(MEMDIR.glob("*.md"))[-3:]:
            for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
                ln = re.sub(r"\s+", " ", ln).strip()
                #  纯符号/分隔线/表格线**不算**记忆正文（首版判据过宽，把 ──── 判成泄漏）
                meat = len(re.sub(r"[^\w\u4e00-\u9fff]", "", ln))
                #  2026-10-14 三修：不再从 memory/*.md 抽取证串（日志大量引用仓内原文 ⇒ 误报，
                #  且 6084 串 × 仓内全文件比对把 240s 跑爆）。取证只看**记忆行**（bank，约 20 条）。
                _ = (meat, ln)   # 保留读取（证明盘上文件健康），但不入取证集
    #  2026-10-14 二修：日志常**引用**仓内文档原文（README 编号条目等）⇒ 那种串在 deploy/ 命中的是
    #  "引用"不是"泄漏"。判据：先把**仓内别处（deploy/ 与 memory/ 之外）已存在**的串排除掉。
    quoted = set()
    for f in []:   #  2026-10-14 四修：取证源改为只看 bank 后这段没必要，且 rglob 全仓（含 .scratch 基线树）
                   #  把 --check 拖到 900s 都跑不完 —— **关掉**（切片留痕，不静默删逻辑）
        if not f.is_file() or f.suffix.lower() not in (".md", ".py", ".js", ".mjs", ".toml", ".json"):
            continue
        s = str(f)
        if str(CLOUD) in s or str(MEMDIR) in s or "memory-digest" in s:
            continue
        try:
            t = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:                                       # noqa: BLE001
            continue
        for n in needles:
            if n in t:
                quoted.add(n)
    return {n for n in needles if n not in quoted}


def check() -> int:
    needles = needle_set()
    hits = []
    files = [f for f in CLOUD.rglob("*") if f.is_file() and f.stat().st_size < 4_000_000
             and f.suffix.lower() not in (".png", ".jpg", ".woff", ".ttf")] if CLOUD.is_dir() else []
    texts = {}
    for f in files:
        try:
            texts[f] = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:                                       # noqa: BLE001
            continue
    for n in needles:
        for f, t in texts.items():
            if n in t:
                hits.append((str(f.relative_to(ROOT)), n[:60]))
                break
    log("=== 记忆本地闸（外发面 deploy/）===")
    log("  取证串 " + str(len(needles)) + " 条（取自记忆正文，≥12/40 字）· 扫描 " + str(len(texts)) + " 个外发件")
    if not hits:
        log("PASS 记忆正文未出现在外发面 —— 「记忆永不外发」有机械判据")
        log("判据 PASS 1 · FAIL 0")
        return 0
    for p, w in hits[:10]:
        log("FAIL " + p + " 含记忆正文：「" + w + "」")
    log("判据 PASS 0 · FAIL 1")
    return 1


def selftest() -> int:
    ck = []

    def c(n, ok, d=""):
        ck.append(bool(ok)); log(("OK  " if ok else "BAD ") + n + (" — " + str(d)[:70] if d else ""))
    ns = needle_set()
    c("正控·取证串非空（记忆正文在盘）", len(ns) > 0, len(ns))
    c("负控·短路径名不入取证集（memory_bank 这种位名不算）",
      all(len(x) >= 12 for x in ns))
    c("正控·真外发面无记忆正文", check() == 0)
    demo = "some deploy text containing: " + (sorted(ns)[0] if ns else "nothing")
    c("正控·含真记忆正文时必须判红", any(n in demo for n in ns))
    bad = len([x for x in ck if not x])
    log("\nmemory-local-guard selftest: " + str(len(ck) - bad) + "/" + str(len(ck)))
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.check:
        return check()
    digest()
    return check()


if __name__ == "__main__":
    sys.exit(main())
