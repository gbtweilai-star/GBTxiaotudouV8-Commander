# -*- coding: utf-8 -*-
"""craft-gate 复核器（只读）· GBT小土豆V8 / tools/codex-scripts

作用：用实测口径复核本目录 checker 对《审美相关skill/craft/anti-ai-slop.md》
P0/P1 条目的真实覆盖面，以及已发布交付物里的实际命中。

只读：不改写任何交付物；只打印读数并以非零码退出（有命中即 exit 1）。
用法：py audit_craft_gate.py
"""
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent          # tools/codex-scripts -> 仓库根（本目录 103 个脚本少算了这一级）
PROTO = ROOT / "V21 GBT小土豆V8-可交互原型.html"
CANVAS = ROOT / "V21 GBT小土豆V8-无限画布.html"

# 规则书 anti-ai-slop.md §七宗罪#1 的完整 7 值
RULEBOOK_INDIGO = ["#6366f1", "#4f46e5", "#4338ca", "#3730a3", "#8b5cf6", "#7c3aed", "#a855f7"]
# 各 checker 实际写入清单 —— 旧版是照抄的副本，checker 改了副本不会跟着变，
# 复核器就成了「抄一遍再夸自己抄对了」。改成从 checker 源文件现读。
CHECKER_FILES = {
    "verify_v21.py": HERE / "verify_v21.py",
    "verify_deliverables.py": HERE / "verify_deliverables.py",
}
CHECKER = {}
for _where, _f in CHECKER_FILES.items():
    _t = _f.read_text(encoding="utf-8")
    _m = re.search(r"AI_INDIGO\s*=\s*[\[(]([^\])]*)[\])]", _t)
    CHECKER["%s (%s)" % (_where, "现读" if _m else "未解析")] = (
        re.findall(r"#[0-9a-fA-F]{6}", _m.group(1)) if _m else [])
# emoji 正则同样现读（verify_v21.py 已换成 Unicode 属性口径）
V21_SRC = (HERE / "verify_v21.py").read_text(encoding="utf-8")
EMOJI_MODE = "unicode-property" if "Extended_Pictographic" in V21_SRC else "narrow"
EMOJI_SCANS_CANVAS = "画布 无 emoji" in V21_SRC
EMOJI_NARROW = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")            # 旧口径
EMOJI_NARROW_DELIV = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]")  # verify_deliverables.py 旧口径
EMOJI_PROPERTY = re.compile(r"[\U0001F000-\U0001FAFF\u2190-\u21FF\u2300-\u23FF"
                            r"\u2460-\u24FF\u25A0-\u27BF\u2B00-\u2BFF\uFE0F\u20E3\u00A9\u00AE\u2122]")

fails = []


def report(ok, label, detail=""):
    print("  %s %-46s %s" % ("PASS" if ok else "HIT ", label, detail))
    if not ok:
        fails.append(label)


print("=" * 84)
print("craft-gate 复核 · 只读 · 交付物在 %s" % ROOT)
print("=" * 84)

if not PROTO.exists():
    print("  SKIP 交付物不存在：%s" % PROTO)
    sys.exit(2)
ptext = PROTO.read_text(encoding="utf-8")
ctext = CANVAS.read_text(encoding="utf-8")

print("\n[1] 七宗罪 #1 · 靛蓝清单覆盖面")
for where, lst in CHECKER.items():
    miss = sorted(set(RULEBOOK_INDIGO) - set(lst))
    report(not miss, "%s 覆盖规则书 7 值" % where, "漏 " + " ".join(miss) if miss else "")
live = [t for t in RULEBOOK_INDIGO if t in ptext.lower() or t in ctext.lower()]
report(not live, "交付物无 AI 靛蓝（全 7 值实测）", "命中 " + " ".join(live) if live else "0/7")

print("\n[2] 七宗罪 #3 · emoji 检测面")
print("       verify_v21.py 判定口径：%s · 是否扫画布：%s"
      % (EMOJI_MODE, "是" if EMOJI_SCANS_CANVAS else "否（旧版只扫原型）"))
for tag, txt in (("原型", ptext), ("画布", ctext)):
    hits = EMOJI_NARROW.findall(txt)
    report(not hits, "%s 无 emoji（旧窄式口径，仅作对照）" % tag,
           "命中 " + "".join(sorted(set(hits))[:8]) if hits else "0")
report(EMOJI_NARROW.match("\u2B50") is not None, "窄式能识别 ⭐U+2B50（不能=盲区）")
report(EMOJI_NARROW.match("\U0001F004") is not None, "窄式能识别 🀄U+1F004（不能=盲区）")
report(EMOJI_MODE == "unicode-property" and EMOJI_SCANS_CANVAS,
       "verify_v21.py 已改 Unicode 属性口径且扫两件")
for tag, txt in (("原型", ptext), ("画布", ctext)):
    missed = sorted({c for c in EMOJI_PROPERTY.findall(txt) if not EMOJI_NARROW.match(c)})
    print("       %s：宽式符号集命中 %d 个码位，其中窄式会漏 %d 个 %s"
          % (tag, len(EMOJI_PROPERTY.findall(txt)), len(missed),
             " ".join("%s U+%04X" % (c, ord(c)) for c in missed[:10])))
    # 真 emoji 面：\p{Extended_Pictographic}（= verify_v21.py 现在的口径）。
    # 上面那行是「符号集」不是 emoji 集 —— 实测 ← → ⇒ ① ⑦ ◇ ⌘ 全都不属于
    # Extended_Pictographic，把它们当 emoji 会误报一片正文内容。
    try:
        import regex as _u
        _ep = _u.compile(r"(?![\u2194])\p{Extended_Pictographic}").findall(txt)
    except ImportError:  # noqa: BLE001
        _ep = ["<regex 模块不可用>"]
    report(not _ep, "%s 无 emoji（\\p{Extended_Pictographic}，白名单 ↔）" % tag,
           "命中 " + "".join(sorted(set(_ep))[:8]) if _ep else "0")

print("\n[3] 七宗罪 #2 · trust 渐变检测面")
grads = sorted(set(re.findall(r"linear-gradient\([^()]*(?:\([^()]*\)[^()]*)*\)", ptext + ctext)))
report("linear-gradient(135deg" not in ptext, "verify_deliverables.py 字面量检查已废弃（改解析式）",
       "交付物里 linear-gradient 共 %d 条" % len(grads))
for g in grads:
    if "," in g and "transparent" not in g and "1px" not in g:
        print("       两段式：", g)

print("\n[4] P1 · 令牌漂移")


def token_block_lines(lines):
    """含 :root / [data-theme] 的令牌块行区间（1-based，花括号配对）。"""
    spans, i, n = [], 0, len(lines)
    while i < n:
        if re.match(r"\s*(:root|\[data-theme)", lines[i]):
            depth, j = 0, i
            while j < n:
                depth += lines[j].count("{") - lines[j].count("}")
                if depth <= 0 and j >= i:
                    break
                j += 1
            spans.append((i + 1, j + 1))
            i = j + 1
        else:
            i += 1
    return spans


for tag, path in (("原型", PROTO), ("画布", CANVAS)):
    lines = path.read_text(encoding="utf-8").splitlines()
    spans = token_block_lines(lines)
    uniq, occ = set(), 0
    for idx, ln in enumerate(lines, 1):
        if any(a <= idx <= b for a, b in spans):
            continue
        for h in re.findall(r"#[0-9a-fA-F]{6}\b", ln):
            uniq.add(h.lower())
            occ += 1
    report(len(uniq) <= 12, "%s 令牌块外裸 hex ≤ 12" % tag,
           "去重 %d 个 / 出现 %d 次（块 L%s）"
           % (len(uniq), occ, ",".join("%d-%d" % s for s in spans)))

cbad = "".join(re.findall(r":root\s*\{[^}]*\}", ctext))
acc = len(re.findall(r"var\(--accent\)", ctext)) - len(re.findall(r"var\(--accent\)", cbad))
report(acc <= 6, "画布正文 var(--accent) ≤ 6", "实测 %d 次" % acc)

print("\n" + "-" * 84)
print("命中 %d 项" % len(fails))
for f in fails:
    print("   - " + f)
sys.exit(1 if fails else 0)
