"""从公开来源取六十四卦的**三个不歧义字段**：卦名 · 下卦 · 上卦。

🔴 设计要点：**不要来源的二进制位**。各家位序（自下而上/自上而下、阴阳谁为 1）不统一，
   直接抄位串就是把别人的约定当成自己的事实。本脚本只取「卦名 / inner(lower) / outer(upper)」
   三个**不歧义**字段，**六爻位串由我们自己的 TRIGRAMS 推导**。

🔴 硬闸（任一不过 ⇒ 拒绝出表，rc≠0，绝不产出半张表）：
   1) 必须正好 64 段、编号恰为 1..64；
   2) 每段必须解出卦名 + 下卦；上卦要么是符号、要么是 identical；
   3) 八卦符号总数必须 == 120（64 下卦 + 56 个显式上卦；8 个纯卦的上卦写作 identical）；
   4) 推导出的 64 个位串必须**互不相同**（64 卦 ↔ 64 态的**双射**）；
   5) 纯卦（上==下）必须正好 8 个，且各自的三爻宽度即该八卦宽度。

输出：state/iching-king-wen.json —— 含来源 URL + wikitext 的 sha256 + 字节数（可复核）。

用法：python tools/codex-scripts/fetch_iching_table.py [--check-only]
"""
import argparse
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ("https://en.wikipedia.org/w/index.php?"
       "title=List_of_hexagrams_of_the_I_Ching&action=raw")
UA = "GBT-potato-iching/1.0 (local research; read-only)"

SYMS = "☰☱☲☳☴☵☶☷"
SYM_CLS = "[%s]" % SYMS          # 🔴 必须字符类：写成 (☰☱☲…) 是**字面序列**，永远匹配不上
# 🔴 符号 → 三爻（**爻自下而上**，阳=1 阴=0）：乾三连 兑上缺 离中虚 震仰盂 巽下断 坎中满 艮覆碗 坤六断
SYM_BITS = {
    "☰": "111",  # 乾 三连
    "☱": "110",  # 兑 上缺（自下而上：阳 阳 阴）
    "☲": "101",  # 离 中虚
    "☳": "100",  # 震 仰盂（初爻阳）
    "☴": "011",  # 巽 下断（初爻阴）
    "☵": "010",  # 坎 中满
    "☶": "001",  # 艮 覆碗（上爻阳）
    "☷": "000",  # 坤 六断
}
SYM_NAME = {"☰": "乾", "☱": "兑", "☲": "离", "☳": "震",
            "☴": "巽", "☵": "坎", "☶": "艮", "☷": "坤"}

# 历史上公认的「纯卦落在哪些王序编号」——**只作呈报，不作硬闸**
# （我的记忆错了不该把好源判死；数学不变量才硬闸）
PURE_EXPECT = {1: "乾", 2: "坤", 29: "坎", 30: "离",
               51: "震", 52: "艮", 57: "巽", 58: "兑"}

# 🔴 源用**繁体**。这里是一张**显式**繁→简表：凡不在表中的字**原样保留并计入 residue**，
#    由硬闸报告出来（**绝不静默穿过** —— 静默正是"看着对了其实没转"的来源）。
T2S = {
    "兌": "兑", "離": "离", "訟": "讼", "師": "师", "謙": "谦", "隨": "随",
    "蠱": "蛊", "臨": "临", "觀": "观", "賁": "贲", "剝": "剥", "復": "复",
    "頤": "颐", "過": "过", "恆": "恒", "遯": "遁", "壯": "壮",
    "晉": "晋", "損": "损", "漸": "渐", "歸": "归", "豐": "丰", "渙": "涣",
    "節": "节", "濟": "济",
}
# 🔴 **观察名单**：64 卦名里「繁体写法与简体不同、但本源恰好已经用了简体」的字。
#   它们不该出现在活跃映射表里（不命中就是死条目=假判据），但**输出里也绝不许出现**。
#   实测：源是**混用**的 —— `兌`/`離` 用繁体，`无妄` 的 `无` 却是简体。
T2S_WATCH = {"無": "无"}
# 64 卦名都是 1–2 个字（结构性事实，可当硬闸）
NAME_LEN = (1, 2)

OUT = ROOT / "state" / "iching-king-wen.json"


def to_simp(s: str):
    """→ (简体串, 本次真正转换掉的字集)。

    🔴 第一版这里写成「凡不在表里的 CJK 字都记残留」—— **判据写坏了**：中/乾/井 这些
    **本来简繁同形**，被误报成残留（实测一次报了 46 个假残留）。正确判据是：
    **输出里不许再出现 T2S 的 key**（有繁体字活到输出才是真残留）。
    """
    res, fired = [], set()
    for ch in s:
        if ch in T2S:
            res.append(T2S[ch])
            fired.add(ch)
        else:
            res.append(ch)
    return "".join(res), fired


def fetch() -> str:
    req = urllib.request.Request(RAW, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def parse(txt: str):
    """→ {序: {"name":…, "lower":sym, "upper":sym}}；解不出就抛（fail-closed）。"""
    marks = [(int(m.group(1)), m.start())
             for m in re.finditer(r"^==+\s*Hexagram\s+(\d+)\s*==+", txt, re.M)]
    if not marks:
        raise ValueError("一段都没切出来：段标记正则没命中")
    out, names_seen = {}, {}
    fired_all = set()
    NAME_PATS = (
        r"named\s*\{\{\s*lang\s*\|\s*zh\s*\|\s*([^}|]+?)\s*\}\}",           # {{lang|zh|乾}}
        r"named\s*\{\{\s*linktext\s*\|\s*lang\s*=\s*zh\s*\|\s*([^}|]+?)\s*\}\}",  # {{linktext|lang=zh|巽}}
    )
    for i, (num, pos) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(txt)
        sec = txt[pos:end]
        raw = None
        for pat in NAME_PATS:
            m = re.search(pat, sec)
            if m:
                raw = m.group(1)
                break
        if raw is None:
            raise ValueError("第 %d 卦解不出卦名（两种模板都没命中）" % num)
        name, fired = to_simp(raw)
        fired_all |= fired
        if not (NAME_LEN[0] <= len(name) <= NAME_LEN[1]):
            raise ValueError("第 %d 卦名「%s」长度 %d 不在 %s —— 转换可疑"
                             % (num, name, len(name), NAME_LEN))
        if name in names_seen:
            raise ValueError("卦名撞车：「%s」第%d卦 与 第%d卦"
                             % (name, names_seen[name], num))
        names_seen[name] = num
        ml = re.search(r"inner\s*\(lower\).*?is\s*(" + SYM_CLS + r")", sec, re.S)
        if not ml:
            raise ValueError("第 %d 卦解不出下卦" % num)
        mo = re.search(r"outer\s*\(upper\)[^.]*?is\s+(?:the\s+same|identical|(" + SYM_CLS + r"))",
                       sec, re.S)
        if not mo:
            raise ValueError("第 %d 卦解不出上卦（既不是符号也不是 identical）" % num)
        out[num] = {"name": name, "raw": raw,
                    "lower": ml.group(1),
                    "upper": mo.group(1) or ml.group(1)}   # identical ⇒ 上=下
    return out, fired_all


def build(rows):
    """卦名/下卦/上卦 → 六爻位串（**推导**，不是抄的）。"""
    table, errs = {}, []
    for num in sorted(rows):
        r = rows[num]
        bits = SYM_BITS[r["lower"]] + SYM_BITS[r["upper"]]   # 下三爻 + 上三爻
        if bits in table:
            errs.append("位串撞车：%s ← 第%d卦(%s) 与 第%d卦(%s)"
                        % (bits, table[bits]["n"], table[bits]["name"], num, r["name"]))
            continue
        table[bits] = {
            "n": num, "name": r["name"], "raw": r["raw"],
            "lower": SYM_NAME[r["lower"]], "upper": SYM_NAME[r["upper"]],
            "lower_sym": r["lower"], "upper_sym": r["upper"],
            "uni": chr(0x4DC0 + num - 1),                        # ䷀ = U+4DC0 = 第1卦
        }
    return table, errs


def gates(txt, rows, table, errs, fired):
    """全部硬闸。返回 (ok, 逐条读数, 纯卦集)。"""
    sym_total = sum(txt.count(s) for s in SYMS)
    pure = {b: v for b, v in table.items() if v["lower_sym"] == v["upper_sym"]}
    nums = sorted(rows)
    names = [r["name"] for r in rows.values()]
    survived = sorted(set("".join(names)) & set(T2S))      # 繁体字活到输出 = 真残留
    watch_hit = sorted(set("".join(names)) & set(T2S_WATCH))
    dead = sorted(set(T2S) - fired)                        # 映射表里没命中的条目 = 死条目
    bad_len = [r["name"] for r in rows.values() if not (NAME_LEN[0] <= len(r["name"]) <= NAME_LEN[1])]
    checks = [
        ("段数恰为 64", len(rows) == 64, "%d 段" % len(rows)),
        ("编号恰为 1..64", nums == list(range(1, 65)),
         "首 %s 尾 %s" % (nums[:3], nums[-3:])),
        ("八卦符号总数 == 120", sym_total == 120,
         "%d（=64 下卦 + 56 显式上卦）" % sym_total),
        ("每符号各出现 15 次", all(txt.count(s) == 15 for s in SYMS),
         json.dumps({s: txt.count(s) for s in SYMS}, ensure_ascii=False)),
        ("位串互不相同（64↔64 双射）", len(table) == 64 and not errs,
         "%d 个不同位串" % len(table)),
        ("纯卦恰 8 个", len(pure) == 8, "%d 个" % len(pure)),
        ("纯卦位串 = 该卦三爻叠两次",
         all(b == SYM_BITS[v["lower_sym"]] * 2 for b, v in pure.items()),
         ", ".join("%s=%s" % (v["name"], b) for b, v in sorted(pure.items(),
                                                               key=lambda kv: kv[1]["n"]))),
        ("卦名互不相同", len(set(names)) == 64, "%d 个不同名" % len(set(names))),
        ("卦名长度都在 %s" % (NAME_LEN,), not bad_len, "越界: %s" % (bad_len or "无")),
        ("繁→简：输出无繁体残留", not survived,
         "命中 %d 字 %s ｜ 残留 %s" % (len(fired), "".join(sorted(fired)), survived or "无")),
        ("繁→简：映射表无死条目", not dead,
         ("死条目 %s" % "".join(dead)) if dead else "全部 %d 条都真命中" % len(T2S)),
        ("繁→简：观察名单未出现（源未用该繁体）", not watch_hit,
         ("⚠️ 出现了 %s ⇒ 需并入活跃表" % "".join(watch_hit)) if watch_hit
         else "观察 %d 字 %s 全未出现" % (len(T2S_WATCH), "".join(sorted(T2S_WATCH)))),
    ]
    ok = all(c[1] for c in checks)
    return ok, checks, pure


MODULE = ROOT / "tools" / "iching_king_wen.py"


def emit_module(table, sha, nbytes, checks):
    """把表写成可 import 的模块 —— **不让任何人手打 64 行**（手抄即错源）。"""
    L = ['"""六十四卦表（王序）—— **自动生成，不要手改**。',
         "",
         "生成器：tools/codex-scripts/fetch_iching_table.py",
         "来源　：%s" % RAW,
         "sha256：%s" % sha,
         "字节　：%d" % nbytes,
         "",
         "取了什么／没取什么：",
         "  取　：卦名 · 下卦 · 上卦 —— 三个**不歧义**字段；",
         "  没取：来源的二进制位串 —— 各家位序约定不一（自下而上/自上而下、阴阳谁为 1），",
         "        直接抄位串就是把别人的约定当自己的事实；",
         "  推导：六位 ＝ 下三爻 ＋ 上三爻（**爻自下而上**，阳=1 阴=0），对照本仓 TRIGRAMS。",
         "",
         "生成时 12 道硬闸的实际读数："]
    for name, ok, reading in checks:
        L.append("  %s %-30s %s" % ("[OK]" if ok else "[BAD]", name, reading))
    L += ['"""',
          "",
          "# bits: (王序号, 卦名, 下卦, 上卦, Unicode 卦符)",
          "KING_WEN = {"]
    for bits, v in sorted(table.items(), key=lambda kv: kv[1]["n"]):
        L.append('    "%s": (%d, "%s", "%s", "%s", "%s"),'
                 % (bits, v["n"], v["name"], v["lower"], v["upper"], v["uni"]))
    L += ["}",
          "",
          "PROVENANCE = {",
          '    "来源": %r,' % RAW,
          '    "sha256": %r,' % sha,
          '    "字节数": %d,' % nbytes,
          '    "卦数": %d,' % len(table),
          '    "位串约定": "六位 = 下三爻 + 上三爻；爻自下而上；阳=1 阴=0",',
          '    "来源字段": "卦名/下卦/上卦（位串由本仓推导，非抄录）",',
          "}",
          ""]
    MODULE.write_text("\n".join(L), encoding="utf-8")
    return MODULE


def main() -> int:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true", help="只验表，不落盘")
    a = ap.parse_args()

    txt = fetch()
    sha = hashlib.sha256(txt.encode("utf-8")).hexdigest()
    rows, fired = parse(txt)
    table, errs = build(rows)
    ok, checks, pure = gates(txt, rows, table, errs, fired)

    print("来源:", RAW)
    print("字节数:", len(txt), "｜ sha256:", sha[:16], "…")
    print("--- 硬闸 ---")
    for name, passed, reading in checks:
        print("  %s %-28s %s" % ("✓" if passed else "🔴", name, reading))
    if errs:
        print("--- 撞车明细 ---")
        for e in errs:
            print("  ", e)

    print("--- 纯卦落位（历史锚点·只呈报）---")
    for b, v in sorted(pure.items(), key=lambda kv: kv[1]["n"]):
        exp = PURE_EXPECT.get(v["n"])
        mark = "✅" if exp == v["name"] else ("⚠️ 我记的是 %s" % exp if exp else "—")
        print("   第%2d卦 %s %s  %s" % (v["n"], v["name"], b, mark))

    print("--- 全 64 卦（位串 ← 下卦+上卦 推导）---")
    for bits, v in sorted(table.items(), key=lambda kv: kv[1]["n"]):
        mark = "纯" if v["lower_sym"] == v["upper_sym"] else "  "
        raw = "" if v["raw"] == v["name"] else " (源:%s)" % v["raw"]
        print("   %2d %s %s %s 下%s 上%s%s"
              % (v["n"], v["uni"], bits, v["name"], v["lower"], v["upper"], raw + mark))

    if not ok:
        print("🔴 硬闸未全过 ⇒ **拒绝出表**（不落盘、不产出半张表）")
        return 2
    if a.check_only:
        print("✅ --check-only：全闸过，未落盘")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "来源": RAW, "sha256": sha, "字节数": len(txt),
        "字段": "卦名/下卦/上卦 取自来源；六爻位串由本仓 TRIGRAMS 推导",
        "位串约定": "六位＝下三爻+上三爻；爻自下而上；阳=1 阴=0",
        "卦数": len(table),
        "表": table,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("✅ 落盘 %s ｜ %d 字节" % (OUT.relative_to(ROOT), OUT.stat().st_size))
    mod = emit_module(table, sha, len(txt), checks)
    print("✅ 生成 %s ｜ %d 字节" % (mod.relative_to(ROOT), mod.stat().st_size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
