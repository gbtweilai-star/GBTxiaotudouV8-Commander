"""探 Wikipedia 六十四卦列表的源码结构（只读·只为看清格式，不落库）。

用法：python tools/codex-scripts/probe_iching_src.py
"""
import json
import re
import sys
import urllib.request

RAW = ("https://en.wikipedia.org/w/index.php?"
       "title=List_of_hexagrams_of_the_I_Ching&action=raw")
UA = "GBT-potato-iching-probe/1.0 (local research; read-only)"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main() -> int:
    req = urllib.request.Request(RAW, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        txt = r.read().decode("utf-8", "replace")
    print("字节数:", len(txt))
    print("行数:", txt.count("\n") + 1)

    # 1) 有多少个 Hexagram 段
    secs = re.findall(r"^==+\s*Hexagram\s+(\d+)", txt, re.M)
    print("Hexagram 段数:", len(secs), "首尾:", secs[:3], secs[-3:] if secs else None)

    # 2) 第一个段的原文（看模板参数名）
    m = re.search(r"^==+\s*Hexagram\s+1\s*==+(.*?)^==+\s*Hexagram\s+2", txt, re.M | re.S)
    print("--- 段1 样本 (前 1200 字) ---")
    print((m.group(1).strip()[:1200] if m else "**没找到段1**"))

    # 3) 全页出现过的模板参数名（去重）
    params = sorted(set(re.findall(r"\|\s*([a-z_]{2,20})\s*=", txt)))
    print("--- 模板参数名 ---")
    print(json.dumps(params, ensure_ascii=False))

    # 4) 八卦符号出现次数（这些符号若成对出现，就是上下卦字段）
    syms = "☰☱☲☳☴☵☶☷"
    print("--- 八卦符号计数 ---")
    print(json.dumps({s: txt.count(s) for s in syms}, ensure_ascii=False))

    # 5) 是否用 Unicode 卦符 ䷀-䷿
    hexs = [c for c in txt if 0x4DC0 <= ord(c) <= 0x4DFF]
    print("Unicode 卦符出现:", len(hexs))

    # 6) 版本号（供出处引用）
    rev = re.search(r"^\s*\|?\s*revision\s*=", txt, re.M)
    print("含 revision 字段:", bool(rev))
    return 0


if __name__ == "__main__":
    sys.exit(main())
