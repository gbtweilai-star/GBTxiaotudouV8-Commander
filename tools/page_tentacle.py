#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""page_tentacle —— 每一页都要被触手覆盖（扫描 · 注入 · 记账 · 验通）。

主人令（2026-10-21 / 2026-10-29）：
  「所有的代码页面都要使用触手双向绑定，每一页都要使用触手覆盖每一个代码」
  「实现以后就永远不会出现丢失能力或者打不通的硬性要求」

## 实测缺口（2026-10-29）
  holo_pet_w3 下 28 个活页面：**20 个连 tentacle-kit 都没引**。
  引了的那些依赖 `window.gbtW3` —— 只有 Electron 壳才有 ⇒ 在 Safari 里全是「无桥」。
  ⇒ 「触手覆盖」这件事一直是**名义上有、实际没接**。

## 三件事
  scan     逐页量：有没有 kit / 有没有 web 壳 / 控件几个 / 有没有被触手盖章(data-tentacle)
           / 有没有报到（bridge 的 _tentacle/hello 账）
  enforce  给缺的页面注入两行脚本（web 壳 → kit，顺序不能反），幂等
  ledger   写 state/page_tentacles.json：每页一行，标明覆盖状态

## 口径
  · **不改页面逻辑**，只在 </body> 前插两行 <script>；
  · 幂等：已引用的不重复插；
  · 存档目录（_archive）不动；
  · 判不了就写判不了（比如页面没有 </body>）。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
W3 = ROOT / "holo_pet_w3"
STATE = ROOT / "state" / "page_tentacles.json"
HELLO = ROOT / "state" / "page_tentacle_hello.jsonl"


def pages() -> list:
    out = []
    # 🔴 2026-10-30：原来只扫 index.html ⇒ **独立页（local-llm.html / bench-matvec.html /
    #   probe.html 这类）根本不在规则视野里**，等于树规对它们不存在。
    #   改成扫所有 .html，排除 _archive / _retired / vendor（第三方件不注入）。
    for p in sorted(W3.rglob("*.html")):
        rel = p.relative_to(W3).as_posix()
        if "_archive" in rel or "_retired" in rel or rel.startswith("vendor/") or "/vendor/" in rel:
            continue
        out.append(p)
    return out


def _rel_prefix(p: pathlib.Path) -> str:
    """页面到 holo_pet_w3 的相对前缀（holo_pet_w3/index.html ⇒ ''）。"""
    depth = len(p.relative_to(W3).parts) - 1
    return "../" * depth


def inspect(p: pathlib.Path) -> dict:
    t = p.read_text(encoding="utf-8", errors="replace")
    rel = p.relative_to(W3).as_posix()
    ctrls = len(re.findall(r"<(button|select|input)\b", t, re.I))
    has_kit = bool(re.search(r"tentacle-(kit|boot)\.js", t))
    has_shell = bool(re.search(r"tentacle-bridge\.js", t))
    # 触手盖章：kit 会给每个接管过的元素写 data-tentacle="1"
    stamped = len(re.findall(r'data-tentacle\s*=\s*"1"', t))
    return {"page": rel, "file": str(p), "controls": ctrls,
            "kit": has_kit, "web_shell": has_shell, "stamped": stamped,
            "covered": has_kit and has_shell}


def hello_seen() -> dict:
    """谁真的报到过（= 真在浏览器里跑起来过）。"""
    seen = {}
    if HELLO.is_file():
        for ln in HELLO.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(ln)
            except Exception:                                 # noqa: BLE001
                continue
            # 🔴 2026-10-29 修：页面报上来的是 "holo_pet_w3/panel/index.html"，
            #   扫描用的是相对 holo_pet_w3 的 "panel/index.html" —— **键对不上，
            #   报到数恒 0**，看着像"一次都没连上"，其实连上了。归一化再存。
            pg = str(d.get("page") or "")
            for pre in ("holo_pet_w3/", "/holo_pet_w3/"):
                if pg.startswith(pre):
                    pg = pg[len(pre):]
            seen[pg] = d.get("at")
    return seen


def inject(p: pathlib.Path) -> dict:
    t = p.read_text(encoding="utf-8", errors="replace")
    rel = p.relative_to(W3).as_posix()
    prefix = _rel_prefix(p)
    add = []
    if "tentacle-bridge.js" not in t:
        add.append('<script src="%sshell/tentacle-bridge.js?v=20261029"></script>' % prefix)
    if "tentacle-kit.js" not in t:
        # 2026-10-30：改成**按需激活**引导器（立即放代理 gbtW3，真件空闲/首次调用才加载）
        add.append('<script src="%sshell/tentacle-boot.js?v=20261030"></script>' % prefix)
    if not add:
        # 两件都有，但要查**顺序**：kit 依赖 window.gbtW3（由 web 壳提供），
        # 壳排在 kit 后面 ⇒ kit 启动时 gbtW3 还不存在 ⇒ 等于没接。
        # 🔴 2026-10-29 实测 11/28 页就是这么坏的（kit 在 <head>，我把壳注到了 </body>）。
        ia, ib = t.find("tentacle-bridge.js"), t.find("tentacle-kit.js")
        if ia != -1 and ib != -1 and ia < ib:
            return {"page": rel, "changed": False, "why": "已覆盖且顺序正确"}
        # 顺序反了：把壳搬到 kit 那个 <script> 之前
        m = re.search(r'<script[^>]*tentacle-kit\.js[^>]*></script>', t)
        if not m:
            return {"page": rel, "changed": False, "why": "找不到 kit 的 script 标签"}
        shell_tag = '<script src="%sshell/tentacle-bridge.js?v=20261029"></script>\n' % prefix
        t2 = t[:m.start()] + shell_tag + t[m.start():]
        p.write_text(t2, encoding="utf-8")
        return {"page": rel, "changed": True, "why": "顺序修正：壳提到 kit 之前"}
    block = "\n<!-- 触手覆盖（page_tentacle.py 自动注入 · 顺序不能反：先 web 壳再 kit） -->\n" \
            + "\n".join(add) + "\n"
    if "</body>" in t:
        t2 = t.replace("</body>", block + "</body>", 1)
    elif "</html>" in t:
        t2 = t.replace("</html>", block + "</html>", 1)
    else:
        return {"page": rel, "changed": False, "why": "没有 </body> 也没有 </html>，判不了不敢瞎插"}
    p.write_text(t2, encoding="utf-8")
    return {"page": rel, "changed": True, "added": len(add)}


def run_enforce() -> dict:
    rows = []
    for p in pages():
        rows.append(inject(p))
    return {"ok": True, "enforced": rows,
            "changed": len([r for r in rows if r.get("changed")])}


def run_scan(write: bool = True) -> dict:
    seen = hello_seen()
    rows = []
    for p in pages():
        r = inspect(p)
        r["reported"] = seen.get(r["page"])
        r["reachable"] = bool(r["reported"])
        rows.append(r)
    tot = len(rows)
    cov = len([r for r in rows if r["covered"]])
    rep = len([r for r in rows if r["reachable"]])
    out = {"ok": True, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "pages": tot, "covered": cov, "reported": rep,
           "rows": rows}
    if write:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def main(argv: list) -> int:
    op = argv[1] if len(argv) > 1 else "scan"
    if op == "enforce":
        r = run_enforce()
        print("  ✅ 注入完成：改了 %d 页" % r["changed"])
        for x in r["enforced"]:
            if x.get("changed"):
                print("     + %s" % x["page"])
        s = run_scan()
        print("  复查：%d/%d 页已覆盖（web 壳 + kit）" % (s["covered"], s["pages"]))
        return 0
    if op == "scan":
        s = run_scan()
        print("  ═══ 触手页面覆盖 ═══\n")
        print("  页面 %d · 已覆盖 %d · 真报到过 %d\n" % (s["pages"], s["covered"], s["reported"]))
        for r in s["rows"]:
            mark = "✅" if r["covered"] else "🔴"
            print("  %s %-34s 控件 %3d · kit=%s 壳=%s 报到=%s"
                  % (mark, r["page"][:34], r["controls"],
                     "有" if r["kit"] else "无", "有" if r["web_shell"] else "无",
                     (r["reported"] or "—")[:19]))
        print("\n  报告: %s" % STATE)
        return 0
    print("  usage: page_tentacle.py scan|enforce")
    return 2


if __name__ == "__main__":
    import os
    os.environ.setdefault("GBT_AUTONOMOUS", "1")
    raise SystemExit(main(sys.argv))
