# -*- coding: utf-8 -*-
"""抽查：每个能力独立页的本地引用是否都真存在（防"看着对、点开 404"）。

用法：py -3.14 tools/codex-scripts/check-cap-links.py [--all]
"""
import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent.parent
CAPS = ROOT / "holo_pet_w3" / "brain" / "caps"
REF = re.compile(r'(?:href|src)="([^"]+)"')
# 🔴 必须先剥掉 `<script>…</script>`（首跑在这里误报过一条）：
#    总目录页是**用 JS 拼链接**的，源码里长这样 —— `href="' + encodeURIComponent(n.id) + '.html"`
#    不剥脚本就会把这段**代码文本**当成一个静态 href，报出一条并不存在的断链。
#    扫描器报假红，比不报更贵：它会让人开始不信红灯。
SCRIPT = re.compile(r"<script\b.*?</script>", re.S | re.I)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="全部 162 页都查（默认抽 8 页）")
    a = ap.parse_args()

    files = sorted(CAPS.glob("*.html"))
    if not files:
        print("🔴 没有能力页 —— 先跑 cap-pages.py")
        return 2
    sample = files if a.all else files[:8]
    bad, checked = [], 0
    for f in sample:
        for m in REF.findall(SCRIPT.sub(" ", f.read_text(encoding="utf-8"))):
            if m.startswith(("http", "#", "data:")):
                continue
            checked += 1
            # 🔴 2026-10-17 翻正（留痕 · 原始口径已翻，为什么翻，原期望是什么）：
            #   原口径：`(f.parent / m).resolve()` —— 把 href **原样**当文件名去 exists()。
            #   病因：页面 href 是 **URL 编码**的（真实案例 `../../../state/dingtalk-14%E6%B4%BB%E9%A1%B5.html`
            #         ⇒ 解码后是 `state/dingtalk-14活页.html`，文件**真实存在**）。
            #         Path.resolve() 不解码 ⇒ 拿 `%E6%B4%BB...` 当字面文件名 ⇒ 永远不存在。
            #   原期望：编码后的 href 应能解析到真文件；实测 311 页报 311 条断链 = **全是同一条假红**。
            #   现口径：先 unquote + 剥掉 ?query / #fragment，再 resolve。
            #   （判据报假红比不报更贵：它会让人开始不信红灯。）
            from urllib.parse import unquote
            _target = unquote(m.split("#", 1)[0].split("?", 1)[0])
            if not _target:
                continue
            if not (f.parent / _target).resolve().exists():
                bad.append((f.name, m))
    print("=" * 70)
    print("能力页引用可达性")
    print("=" * 70)
    print("  查了 %d 页 · %d 个本地引用" % (len(sample), checked))
    if bad:
        print("  🔴 %d 条断链：" % len(bad))
        for n, m in bad[:20]:
            print("      %s -> %s" % (n, m))
        return 1
    print("  ✅ 零断链")
    print("  全量复跑：py -3.14 tools/codex-scripts/check-cap-links.py --all")
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
