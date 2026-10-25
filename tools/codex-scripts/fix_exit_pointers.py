# -*- coding: utf-8 -*-
"""出口清单登记指针 · 自动对齐器（R121 后续 · 2026-09-23）。

## 为什么要有这件

`holo_pet_w3/shell/main.cjs` 的 `TOOLS_CAPS` 里，每个能力都写着一个**裸行号**
（`registered: "caps_registry.py:585"`）。它是契约：`test_capability_registry` 会逐条核对
"这个行号上真的写着 `"<cap>": {` 吗"。

问题是这个契约**按行号耦合**：只要有人在被引用的行**之前**插入哪怕 1 行，
所有在它后面的指针**集体偏移**，测试当场变红。实测发生过两次：

  · 2026-09-22：注册表插入 24 行 ⇒ `prompt_bridge` / `coze_mail` / `create` 三个指针同时失效
    （当时的判据一次只喊一个 ⇒ 修的人被引进打地鼠，见 test 里那段注释）；
  · 2026-09-23：模块 docstring 加 1 行 ⇒ 同样三个指针又集体偏移 +1。

⇒ 这类红**不是代码坏了**，是**登记簿没跟着走**。手工找行号是纯体力活，而且下次还会再来。
本件把"跟着走"变成一条命令。

## 用法

    py -3.14 tools/codex-scripts/fix_exit_pointers.py            # 看差异，不改盘
    py -3.14 tools/codex-scripts/fix_exit_pointers.py --check    # 有差异就 exit 1（给 CI/门禁用）
    py -3.14 tools/codex-scripts/fix_exit_pointers.py --write    # 真写盘

**只改 `registered:` 那一行**，其它一个字节都不碰；`cap:` 与 `registered:` 必须相邻成对，
找不到配对的如实报出来（不猜、不静默跳过）。

## 一条张力（写在这里，免得下次误判）

`main.cjs:589` 的 R-H295 注释已经判定：**硬编码行号指向别人比不写更坏**
（`voice_orchestra` 曾声明 `:560`，而 560 是 `prompt_bridge` 的行 —— 读者会照假引用查，还查到东西），
所以它**故意**不写 `registered`，改走运行时 `registeredAt(cap)` 现查。
⇒ 本件把"没有静态指针"当**信息**报、**不计入退出码**；只有"写了但指错"才算差异。
真正的出路是**把这 3 条也改成运行时现查**（那就是改 `test_capability_registry` 的契约，属于设计决策，
不在本工具的权限内）；在此之前，本件保证"指针永远跟着注册表走"这件事**只是一条命令**。
"""
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY = ROOT / "gbt_allinone" / "caps_registry.py"
MAIN_CJS = ROOT / "holo_pet_w3" / "shell" / "main.cjs"

# `cap: "xxx",` 紧跟着 `registered: "caps_registry.py:NNN",`（允许中间有空格/注释行）
PAIR_RE = re.compile(
    r'(?P<pre>cap:\s*"(?P<cap>[^"]+)"\s*,\s*\n\s*)'
    r'(?P<line>registered:\s*"caps_registry\.py:)(?P<no>\d+)(?P<post>")')

REG_DEF_RE = re.compile(r'^\s*"(?P<cap>[^"]+)":\s*\{\s*$')


def registry_map() -> dict:
    """现读注册表：cap 名 -> 它那一行的行号（1 基）。"""
    text = REGISTRY.read_bytes().decode("utf-8-sig")
    out = {}
    for i, line in enumerate(text.splitlines(), 1):
        m = REG_DEF_RE.match(line)
        if m:
            # 同名只取第一次出现（注册表里不该有重名；真重名另有判据管）
            out.setdefault(m.group("cap"), i)
    return out


def scan() -> tuple:
    """逐条配对现读。返回 (rows, unpaired, text)。

    `unpaired` = main.cjs 里写了 `cap: "x"` 却**没有紧跟 registered 行**的项 ——
    不替它猜行号，如实交出来。
    """
    text = MAIN_CJS.read_bytes().decode("utf-8-sig")
    reg = registry_map()
    rows, unpaired = [], []

    seen_caps = set()
    for m in PAIR_RE.finditer(text):
        cap, no = m.group("cap"), int(m.group("no"))
        seen_caps.add(cap)
        real = reg.get(cap)
        if real is None:
            rows.append({"cap": cap, "was": no, "now": None,
                         "why": "注册表里已无此项（该删这一行，不是改行号）"})
            continue
        rows.append({"cap": cap, "was": no, "now": real, "why": ""})

    for cap in re.findall(r'cap:\s*"([^"]+)"\s*,', text):
        if cap not in seen_caps and cap not in [u["cap"] for u in unpaired]:
            unpaired.append({"cap": cap, "why": "有 cap 行但没配 registered 行"})
    return rows, unpaired, text


def main() -> int:
    ap = argparse.ArgumentParser(description="出口清单登记指针自动对齐")
    ap.add_argument("--write", action="store_true", help="真写盘（默认只报差异）")
    ap.add_argument("--check", action="store_true", help="有差异 exit 1")
    a = ap.parse_args()

    rows, unpaired, text = scan()
    drift = [r for r in rows if r["now"] is not None and r["was"] != r["now"]]
    gone = [r for r in rows if r["now"] is None]

    print("=" * 74)
    print("出口清单登记指针 · 现读对账")
    print("=" * 74)
    print("  注册表 %s" % REGISTRY.relative_to(ROOT))
    print("  出口清单 %s" % MAIN_CJS.relative_to(ROOT))
    print("  登记项 %d 条 ｜ 偏移 %d ｜ 悬空 %d" % (len(rows), len(drift), len(gone)))

    # 偏移量分布：如果**全部同号**，那就是"上面插了 N 行"，一句话能说清，不必逐条念
    deltas = {r["now"] - r["was"] for r in drift}
    if drift:
        if len(deltas) == 1:
            d = deltas.pop()
            print("  ⚠ 全部指针**同向偏移 %+d 行** —— 典型成因：注册表在被引用行之前插了 %d 行。"
                  % (d, abs(d)))
        else:
            print("  ⚠ 偏移量不一致：%s —— 不是单纯插入行，逐条看下面。"
                  % sorted(deltas))
        for r in drift:
            print("    %-22s %5d -> %-5d (%+d)" % (r["cap"], r["was"], r["now"], r["now"] - r["was"]))
    for r in gone:
        print("    %-22s %5d -> 无此项    %s" % (r["cap"], r["was"], r["why"]))
    for u in unpaired:
        # ⚠️ 这条**不是缺陷**：R-H295 已经判定「硬编码行号指向别人比不写更坏」，
        # 所以 `voice_orchestra` 是**故意**不写 `registered` 的，改走运行时 `registeredAt(cap)` 现查。
        # 因此不配静态指针**不计入退出码**，只如实报出来供人确认。
        print("    %-22s （无静态指针 · 按 R-H295 走运行时 registeredAt() 现查，不是缺陷）" % u["cap"])

    if not drift and not gone:
        print("  ✅ 指针全对（静态指针 %d 条逐条比对，无差异）" % len(rows))
        return 0

    if not a.write:
        print("")
        print("  （未写盘。要对齐请加 --write；要当门禁用请加 --check）")
        return 1 if a.check else 0

    # ── 只改 registered 的数字，别的一个字节不碰 ──
    def _sub(m):
        cap, no = m.group("cap"), int(m.group("no"))
        real = registry_map_cached.get(cap)
        if real is None or real == no:
            return m.group(0)
        return "%s%s%d%s" % (m.group("pre"), m.group("line"), real, m.group("post"))

    registry_map_cached = registry_map()
    new_text, n = PAIR_RE.subn(_sub, text)
    MAIN_CJS.write_bytes(new_text.encode("utf-8"))
    print("")
    print("  ✅ 已写盘：重写 %d 处（只动 registered 的数字）" % n)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(3)
