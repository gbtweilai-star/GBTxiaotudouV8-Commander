"""审美审计器 · 把「AI 味」从感觉变成能跑的检查。

为什么要有它
------------
审美最容易变成"我觉得不好看"—— 那种结论没法复核、也没法交给别人执行。
但「AI 味」里有一大半其实是**可机检的具体模式**：默认 indigo 强调色、紫蓝两段渐变 hero、
emoji 当图标、lorem ipsum 填充文案、编造的指标、外链占位图床……

本仓 `审美相关skill/craft/anti-ai-slop.md` 写明了这套规则（它来自 Open Design 的 daemon，
那条 daemon 有个 `apps/daemon/src/lint-artifact.ts` 做自动检查）。**我们没有那个 daemon**，
所以这里把规则落成能跑的检查器：规则一条条对应、能指到文件哪一行、P0 会真的让退出码非零。

诚实口径（照仓里《零猜测律》）
------------------------------
每条规则都标 `auto`（本脚本真能查）或 `manual`（只能人看，脚本不假装能查）。
查不了的规则**照样列出来**并写明"没实现"，绝不把"没查"折算成"没问题"。

用法：
    python tools/codex-scripts/audit_aesthetic.py <文件或目录> [...]
    python tools/codex-scripts/audit_aesthetic.py --json out.json capabilities.html
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())

# ── 规则表 ────────────────────────────────────────────────────────────────
# tier: P0 必修 / P1 该修 / P2 可修；check: auto 机器可查 / manual 只能人看
INDIGO = ["#6366f1", "#4f46e5", "#4338ca", "#3730a3", "#8b5cf6", "#7c3aed", "#a855f7"]
TRUST_GRADIENT_PAIRS = [
    ("#8b5cf6", "#3b82f6"), ("#7c3aed", "#2563eb"), ("#6366f1", "#06b6d4"),
    ("#4f46e5", "#06b6d4"), ("#a855f7", "#3b82f6"), ("purple", "blue"),
]
PLACEHOLDER_CDNS = ["unsplash.com", "placehold.co", "placekitten.com", "picsum.photos",
                    "via.placeholder.com", "dummyimage.com"]
FILLER = [r"lorem ipsum", r"\bfeature one\b", r"\bfeature two\b", r"\bfeature three\b",
          r"\bplaceholder text\b", r"\bsample content\b", r"\byour text here\b",
          r"\bfoo bar baz\b"]
INVENTED_METRICS = [r"\b\d+(?:\.\d+)?\s*[x×]\s*(?:faster|more|better|cheaper)\b",
                    r"\b99\.9+\s*%\s*uptime\b", r"\b10x\b", r"\b100%\s*(?:uptime|secure|reliable)\b"]
EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\u2b00-\u2bff]")
DEFAULT_SECTION_ORDER = ["hero", "feature", "pricing", "faq", "cta"]

MANUAL_RULES = [
    ("M1", "P0", "display 字体是否被硬写成 Inter/Roboto/system-ui（需要先知道 seed 绑了什么字体）"),
    ("M2", "P1", "Hero→Features→Pricing→FAQ→CTA 的骨架是否照抄模板（结构判断，需人看）"),
    ("M3", "P2", "对称布局是否完全没有视觉张力（主观）"),
    ("M4", "P0", "配色/间距/层级是否一眼就像模板（主观，靠截图对比与人眼）"),
]


def _lines(text: str):
    return text.splitlines()


def _find(lines, pattern, flags=re.I, limit=6):
    rx = re.compile(pattern, flags)
    hits = []
    for i, ln in enumerate(lines, 1):
        if rx.search(ln):
            hits.append({"line": i, "text": ln.strip()[:160]})
            if len(hits) >= limit:
                break
    return hits


def audit_html(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = _lines(text)
    findings: list[dict] = []

    def add(rid, tier, title, hits, note=""):
        if hits:
            findings.append({"id": rid, "tier": tier, "title": title,
                             "count": len(hits), "hits": hits, "note": note})

    # ── P0 ──
    hits = []
    for hexv in INDIGO:
        for h in _find(lines, re.escape(hexv)):
            h["text"] = ("%s  ← 默认 Tailwind indigo 系" % h["text"])
            hits.append(h)
    add("P0-1", "P0", "默认 Tailwind indigo 当强调色（AI 味第一名）", hits[:8],
        "换成项目自己的 --accent；indigo 是教科书的 AI 指纹")

    hits = []
    for a, b in TRUST_GRADIENT_PAIRS:
        for m in re.finditer(r"linear-gradient\([^)]*\)", text, re.I):
            seg = m.group(0)
            if a in seg.lower() and b in seg.lower():
                ln = text[: m.start()].count("\n") + 1
                hits.append({"line": ln, "text": seg[:150]})
    add("P0-2", "P0", "hero 上的两段「信任渐变」（紫→蓝 / 蓝→青 / indigo→粉）", hits[:6],
        "一块平实的表面 + 有想法的字，胜过这个")

    hits = []
    for i, ln in enumerate(lines, 1):
        if "<" not in ln:
            continue
        for m in EMOJI.finditer(ln):
            # 允许：正文里 emoji 本身就是内容（聊天气泡那类）—— 这里只抓"出现在标签/属性里"
            before = ln[: m.start()]
            if before.rstrip().endswith(">") or "=" in before[-40:]:
                hits.append({"line": i, "text": "%s  ← emoji 出现在标签/属性位" % ln.strip()[:140]})
                break
    add("P0-3", "P0", "emoji 当 UI 元素（图标/头像/导航/配图）", hits[:6],
        "改用 1.6–1.8px 描边的单线 SVG + currentColor")

    hits = []
    for pat in FILLER:
        hits += _find(lines, pat)
    add("P0-4", "P0", "填充文案（lorem ipsum / feature one / placeholder text）", hits[:6],
        "空段落是**构图问题**，用版式解决，别编字")

    hits = []
    for pat in INVENTED_METRICS:
        hits += _find(lines, pat)
    add("P0-5", "P0", "编造的指标（10× faster / 99.9% uptime）", hits[:6],
        "要真有出处，要么用标明是占位的假数据")

    hits = []
    for c in PLACEHOLDER_CDNS:
        hits += _find(lines, re.escape(c))
    add("P0-6", "P0", "外链占位图床（unsplash / placehold / picsum …）", hits[:6],
        "又脆又一眼假")

    # ── P1 ──
    # 令牌表可能不止 :root 一处：单文件应用常把调色板写成 JS 表（`const PALETTES={...}`）。
    # 规则的意图是「令牌没被尊重」，不是「不许出现 hex」—— 所以把 **JS 令牌表**也算进令牌区，
    # 否则就会对着正当写法喊狼来了（第一版对 capabilities.html 就是这么误报的）。
    hex_all = re.findall(r"#[0-9a-fA-F]{6}\b", text)
    root = re.search(r":root\s*\{(.*?)\}", text, re.S)
    in_root = len(re.findall(r"#[0-9a-fA-F]{6}\b", root.group(1))) if root else 0
    in_js_tokens = 0
    for m in re.finditer(
            r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*\{(.*?)\n\};", text, re.S):
        if re.search(r"PALETTE|TOKEN|THEME|COLOR|COLOUR", m.group(1), re.I):
            in_js_tokens += len(re.findall(r"#[0-9a-fA-F]{6}\b", m.group(2)))
    outside = len(hex_all) - in_root - in_js_tokens
    if outside > 12:
        findings.append({"id": "P1-1", "tier": "P1",
                         "title": "强调色没被当令牌用：令牌区之外裸 hex 过多",
                         "count": outside, "hits": [{"line": 0, "text":
                                                     ":root 内 %d · JS 令牌表内 %d · **令牌区之外 %d**（阈值 12）"
                                                     % (in_root, in_js_tokens, outside)}],
                         "note": "令牌没被尊重，后面就没法整体换肤"})

    accent_uses = len(re.findall(r"var\(\s*--accent\s*\)", text))
    if accent_uses >= 6:
        findings.append({"id": "P1-2", "tier": "P1",
                         "title": "`var(--accent)` 被用太多（一屏最多 2 处可见）",
                         "count": accent_uses, "hits": [{"line": 0, "text":
                                                         "出现 %d 次（阈值 6）" % accent_uses}],
                         "note": "强调色用滥 = 哪里都不强调"})

    order_pos = {}
    for name in DEFAULT_SECTION_ORDER:
        m = re.search(r"(?:id|class)\s*=\s*[\"'][^\"']*%s" % name, text, re.I)
        if m:
            order_pos[name] = m.start()
    if len(order_pos) >= 4:
        seq = [k for k, _ in sorted(order_pos.items(), key=lambda kv: kv[1])]
        findings.append({"id": "P1-3", "tier": "P1",
                         "title": "默认模板骨架（hero→feature→pricing→faq→cta 顺序照抄）",
                         "count": len(seq), "hits": [{"line": 0, "text": " → ".join(seq)}],
                         "note": "至少塞一节不按套路的（整幅引言墙 / 与现状对比的定价 / 内嵌小样机）"})

    # ── P2 ──
    hits = _find(lines, r"<svg[^>]*>.*?(?:blob|wave|ellipse)", limit=3)
    hits += _find(lines, r"class=\"[^\"]*(?:blob|wave)[^\"]*\"", limit=3)
    add("P2-1", "P2", "装饰性 blob / wave 背景（没有意义的几何）", hits[:4])

    {f["id"] for f in findings}
    missing = []
    if not any(f["id"].startswith("P0") for f in findings):
        missing.append("（本文件没有命中任何 P0 —— 但**没命中 ≠ 没问题**，见下面的 manual 清单）")

    return {
        "file": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "bytes": path.stat().st_size,
        "findings": findings,
        "p0": sum(1 for f in findings if f["tier"] == "P0"),
        "p1": sum(1 for f in findings if f["tier"] == "P1"),
        "p2": sum(1 for f in findings if f["tier"] == "P2"),
        "manual_rules_not_implemented": [
            {"id": i, "tier": t, "what": w} for i, t, w in MANUAL_RULES],
        "note": missing,
    }


def collect(targets: list[str]) -> list[Path]:
    out: list[Path] = []
    for t in targets:
        p = Path(t)
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        if p.is_dir():
            out += sorted([q for q in p.rglob("*.html") if q.is_file()])
        elif p.is_file():
            out.append(p)
    return out


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    json_out = None
    if "--json" in argv:
        i = argv.index("--json")
        if i + 1 < len(argv):
            json_out = Path(argv[i + 1])
            args = [a for a in args if a != argv[i + 1]]
    if not args:
        print(__doc__)
        return 2

    files = collect(args)
    if not files:
        print("没找到任何 .html")
        return 2

    print("=" * 84)
    print("审美审计 · %d 个文件" % len(files))
    print("=" * 84)
    results, total_p0 = [], 0
    for f in files:
        r = audit_html(f)
        results.append(r)
        total_p0 += r["p0"]
        flag = "🔴" if r["p0"] else ("🟡" if r["p1"] else "✅")
        print("\n%s %s  (P0 %d · P1 %d · P2 %d)" % (flag, r["file"], r["p0"], r["p1"], r["p2"]))
        for fd in r["findings"]:
            print("   [%s] %s —— %s（命中 %d）" % (fd["tier"], fd["id"], fd["title"], fd["count"]))
            for h in fd["hits"][:2]:
                where = ("第 %d 行" % h["line"]) if h["line"] else "合计"
                print("        %s: %s" % (where, h["text"][:120]))
            if fd["note"]:
                print("        → %s" % fd["note"])
        if not r["findings"]:
            print("   本文件机器可查的规则全部通过（**不等于好看**，见下方人看清单）")

    print("\n" + "=" * 84)
    print("机器查不了的（照样列出来，不假装查过）")
    for m in MANUAL_RULES:
        print("   [%s] %s  %s" % (m[1], m[0], m[2]))
    print("=" * 84)
    print("P0 命中合计: %d %s" % (total_p0, "⇒ 需修" if total_p0 else "⇒ 无"))

    if json_out:
        json_out.write_text(json.dumps({"results": results, "p0_total": total_p0},
                                       ensure_ascii=False, indent=1), encoding="utf-8")
        print("落盘: %s" % json_out)
    return 1 if total_p0 else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
