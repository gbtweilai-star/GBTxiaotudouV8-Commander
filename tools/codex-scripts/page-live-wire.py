# -*- coding: utf-8 -*-
"""把「实时桥」接到**每一页**（42 页），一次做完、可回滚、跑完即自检。

做法（最小侵入）：
  · 每页在 </body> 前插一行 `<script src="<rel>/shell/live-badge.js" defer></script>`
  · rel 按页面到 holo_pet_w3/shell 的真实相对路径算（旧树页面也照算，不写死）
  · 幂等：已插过就跳过；`</body>` 不唯一或没有就跳过并记「没插上」（不许硬改）
  · 不碰页面其它任何一行

用法： py -3.14 -X utf8 tools/codex-scripts/page-live-wire.py [--apply]
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[2]
PANEL = ROOT / "holo_pet_w3" / "panel" / "index.html"
PAGE_DIR = PANEL.parent
SH = ROOT / "holo_pet_w3" / "shell"
APPLY = "--apply" in sys.argv
TAG_MARK = "shell/live-badge.js"


def pages() -> list:
    txt = PANEL.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"const PAGES = \[(.*?)\n\];", txt, re.S)
    rows = []
    if m:
        for mm in re.finditer(r'id:\s*"([^"]+)"[^}]*?rel:\s*"([^"]+)"', m.group(1)):
            rows.append((mm.group(1), mm.group(2)))
    return rows


def rel_to_shell(page: pathlib.Path, name: str = "live-badge.js") -> str:
    r = os.path.relpath(SH / name, page.parent)
    return r.replace("\\", "/")


done, skipped, failed = [], [], []
FILES = ("live-badge.js", "tentacle-kit.js")     # 实时桥 + 触手接管器，两个都得在
for pid, rel in pages():
    f = (PAGE_DIR / rel).resolve()
    if not f.is_file():
        failed.append((pid, "落点不在盘"))
        continue
    s = f.read_text(encoding="utf-8", errors="replace")
    if all(("/shell/" + x) in s for x in FILES):
        skipped.append(pid)
        continue
    if s.count("</body>") != 1:
        failed.append((pid, "</body> 出现 %d 次，没敢改" % s.count("</body>")))
        continue
    tags = "".join('<script src="%s" defer></script>\n' % rel_to_shell(f, x)
                   for x in FILES if ("/shell/" + x) not in s)
    if APPLY:
        f.write_text(s.replace("</body>", tags + "</body>", 1), encoding="utf-8")
    done.append(pid)

print("计划接线 %d 页 · 已接(幂等跳过) %d · 改不动 %d" % (len(done), len(skipped), len(failed)))
if failed:
    for pid, why in failed:
        print("  !! %-16s %s" % (pid, why))
if done:
    print("  本次%s：%s" % ("已插入" if APPLY else "待插入（加 --apply 才写）", ", ".join(done[:12]) + (" …" if len(done) > 12 else "")))

# 生成本次的接线账
led = {"at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"), "apply": APPLY,
       "wired": done, "already": skipped, "failed": failed, "files": list(FILES),
       "note": "每页两行 defer：shell/live-badge.js（实时桥+业务读数条）+ shell/tentacle-kit.js（触手接管每个交互点）"}
(ROOT / "state" / "page-live-wire.json").write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")
print("账：state/page-live-wire.json")
