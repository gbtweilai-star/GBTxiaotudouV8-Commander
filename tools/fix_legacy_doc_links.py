# -*- coding: utf-8 -*-
"""把 docs/legacy 归档后的 Markdown 引用改到新位置，避免断链。"""
import pathlib
import re

R = pathlib.Path(r"C:\Users\Lenovo E14 Gen 5\Desktop\GBT小土豆V8")
legacy = R / "docs/legacy"
names = sorted(p.name for p in legacy.glob("*.md"))
changed = []
for md in R.rglob("*.md"):
    if "docs/legacy" in md.as_posix() or ".archive" in md.as_posix() or "node_modules" in md.as_posix():
        continue
    t = md.read_text(encoding="utf-8", errors="replace")
    orig = t
    for name in names:
        # markdown 相对链接：](name) / ](./name) → ](legacy/name)
        t = re.sub(r"(\]\()(?:\./)?" + re.escape(name) + r"(\))",
                   r"\1legacy/" + name + r"\2", t)
        # 绝对 docs/name → docs/legacy/name
        t = t.replace("docs/" + name, "docs/legacy/" + name)
    if t != orig:
        md.write_text(t, encoding="utf-8")
        changed.append(str(md.relative_to(R)))
print("changed", len(changed))
for x in changed[:30]:
    print(x)
