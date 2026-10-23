#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""装机副本漂移的**方向判定**：逐文件比源稿与装机副本，并打印差异摘要。

用途：漂移闸只告诉你"不一致"，不告诉你**该往哪边同步**（P23：先看、后动）。
本件只读，不动任何文件。

用法：py -3.14 tools/codex-scripts/installed-drift-inspect.py [--diff-lines 40]
"""
import argparse
import difflib
import hashlib
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = r"C:\Users\ADMIN\Desktop\GBT小土豆V8"
SOURCE = os.path.join(ROOT, "plugins", "gbt-master")
PROFILES = os.path.join(os.path.expanduser("~"), ".dsh", "profiles")
SKIP = {"node_modules", ".git", "__pycache__"}
PKG = "gbt-potato-master-v9"


def walk(root, base=None, out=None):
    base = base or root
    out = [] if out is None else out
    for name in os.listdir(root):
        if name in SKIP:
            continue
        p = os.path.join(root, name)
        if os.path.isdir(p):
            walk(p, base, out)
        else:
            out.append(os.path.relpath(p, base).replace("\\", "/"))
    return out


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]


def text_or_none(p):
    try:
        b = open(p, "rb").read()
        if b"\x00" in b:
            return None
        return b.decode("utf-8", "replace").splitlines()
    except OSError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diff-lines", type=int, default=30)
    a = ap.parse_args()
    src_files = walk(SOURCE)
    print("源稿：%s（%d 件）" % (SOURCE, len(src_files)))
    if not os.path.isdir(PROFILES):
        print("找不到 profile 目录：%s" % PROFILES)
        return 2
    total_bad = 0
    for profile in sorted(os.listdir(PROFILES)):
        nm = os.path.join(PROFILES, profile, "node_modules")
        if not os.path.isdir(nm):
            continue
        for d in sorted(os.listdir(nm)):
            if not d.startswith("gbt-potato-master-v"):
                continue
            inst = os.path.join(nm, d)
            if not os.path.isfile(os.path.join(inst, "package.json")):
                continue
            inst_files = set(walk(inst)) - {".package-lock.json"}
            differ, missing_in_inst, extra_in_inst = [], [], []
            for f in src_files:
                t = os.path.join(inst, f)
                if not os.path.isfile(t):
                    missing_in_inst.append(f)
                elif sha(os.path.join(SOURCE, f)) != sha(t):
                    differ.append(f)
            for f in sorted(inst_files - set(src_files)):
                extra_in_inst.append(f)
            print("\n=== [%s] %s ===" % (profile, d))
            print("  内容不同 %d：%s" % (len(differ), ", ".join(differ) or "（无）"))
            print("  装机缺   %d：%s" % (len(missing_in_inst), ", ".join(missing_in_inst) or "（无）"))
            print("  装机多   %d：%s" % (len(extra_in_inst), ", ".join(extra_in_inst[:8]) or "（无）"))
            total_bad += len(differ) + len(missing_in_inst)
            for f in differ[:6]:
                s = os.path.join(SOURCE, f)
                t = os.path.join(inst, f)
                print("  --- %s  源=%dB 装机=%dB" % (f, os.path.getsize(s), os.path.getsize(t)))
                ls, lt = text_or_none(s), text_or_none(t)
                if ls is None or lt is None:
                    print("      （二进制，不做文本 diff）")
                    continue
                d = list(difflib.unified_diff(lt, ls, fromfile="装机", tofile="源稿", lineterm="", n=1))
                for line in d[:a.diff_lines]:
                    print("      " + line[:160])
                if len(d) > a.diff_lines:
                    print("      …（还有 %d 行差异）" % (len(d) - a.diff_lines))
    print("\n合计内容不同/装机缺：%d 处" % total_bad)
    return 0 if total_bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
