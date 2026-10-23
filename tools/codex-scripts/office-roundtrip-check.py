# -*- coding: utf-8 -*-
"""office-roundtrip 判据（Univer 蒸馏 · #1）：改既有 Office 文件时，**只许动目标，别处逐字节不许变**。

为什么这么判：Univer 的口径是 "Office Harness for AI Agents" —— 让 AI 直接做**可编辑**的
表格/文档/PPT（README: Spreadsheets/Documents/Presentations/Bases/Boards/PDFs · formula engine ·
one Facade API）。本机 genoffice 面偏"生成/导出"，**缺往返编辑**；往返编辑最容易翻车的地方不是
"改没改上"，而是"**改一处、悄悄动了别处**"（公式被重算、样式被抹、批注丢失、zip 成员重排）。
⇒ 判据：OOXML 就是 zip 包 ⇒ **逐成员比 sha256**：
   ①目标成员**必须**变  ②非目标成员**必须一字不变**  ③文件仍能当 zip 读回（不损坏）

用法：
  py -3.14 tools/codex-scripts/office-roundtrip-check.py --old <改前> --new <改后> --expect-changed sheet1
  py -3.14 tools/codex-scripts/office-roundtrip-check.py --selftest

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import hashlib
import io
import sys
import zipfile


def members(path):
    out = {}
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:
            raise ValueError("zip 损坏：" + str(path))
        for n in z.namelist():
            out[n] = hashlib.sha256(z.read(n)).hexdigest()
    return out


def check(old, new, expect_changed) -> tuple:
    a, b = members(old), members(new)
    if set(a) != set(b):
        only_a = sorted(set(a) - set(b))[:5]
        only_b = sorted(set(b) - set(a))[:5]
        return False, "成员集合变了（-：%s / +：%s）" % (only_a, only_b)
    changed = sorted(n for n in a if a[n] != b[n])
    hit = [n for n in changed if expect_changed in n]
    extra = [n for n in changed if expect_changed not in n]
    if not hit:
        return False, "目标成员没变（期望含 %r，实际变化：%s）" % (expect_changed, changed[:6])
    if extra:
        return False, "**动了非目标成员**：%s" % extra[:6]
    return True, "只改了目标 %s（共 %d 个成员，其余逐字节一致）" % (hit[:3], len(a))


def selftest() -> int:
    ck = []

    def c(n, ok, d=""):
        ck.append(bool(ok)); print(("OK  " if ok else "BAD ") + n + (" — " + str(d)[:70] if d else ""))

    def mk(p, extra=None):
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("xl/worksheets/sheet1.xml", "<v>1</v>")
            z.writestr("xl/styles.xml", "<s/>")
            z.writestr("docProps/core.xml", "<c/>")
            if extra:
                z.writestr("xl/worksheets/sheet1.xml", extra)

    import tempfile, pathlib
    d = pathlib.Path(tempfile.mkdtemp())
    o, n1, n2 = d / "o.xlsx", d / "n1.xlsx", d / "n2.xlsx"
    mk(o); mk(n1, "<v>2</v>")
    ok1, why1 = check(str(o), str(n1), "sheet1")
    c("正例·只改目标 ⇒ 绿", ok1, why1)
    with zipfile.ZipFile(o, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", "<v>1</v>")
        z.writestr("xl/styles.xml", "<s/>")
    with zipfile.ZipFile(n2, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", "<v>2</v>")
        z.writestr("xl/styles.xml", "<s CHANGED/>")
    ok2, why2 = check(str(o), str(n2), "sheet1")
    c("负例·顺手动了别处 ⇒ 必须红", not ok2, why2)
    ok3, why3 = check(str(o), str(o), "sheet1")
    c("负例·啥都没改 ⇒ 必须红", not ok3, why3)
    bad = len([x for x in ck if not x])
    print("\noffice-roundtrip-check selftest: %d/%d" % (len(ck) - bad, len(ck)))
    return 1 if bad else 0


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                       # noqa: BLE001
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--old"); ap.add_argument("--new"); ap.add_argument("--expect-changed", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not (a.old and a.new):
        print("需要 --old 与 --new；自测用 --selftest")
        return 2
    ok, why = check(a.old, a.new, a.expect_changed)
    print(("PASS " if ok else "FAIL ") + why)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
