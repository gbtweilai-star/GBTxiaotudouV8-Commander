# -*- coding: utf-8 -*-
"""验证收窄后的加载器（第 4 例改用 cwd 桩，避免 chdir 权限限制）。"""
import re
import pathlib

SRC = r"C:\Python312\Lib\site-packages\sitecustomize.py"
src = pathlib.Path(SRC).read_text(encoding="utf-8")
m = re.search(r"def _find_gatekeeper\(\):.*?\n    return None\n", src, re.S)
fn = m.group(0)
Base = type(pathlib.Path())


class StubPath(Base):
    @classmethod
    def cwd(cls): return cls(r"C:\Users\ADMIN")
    @classmethod
    def home(cls): return cls(r"C:\Users\ADMIN")


def run(path_cls, label):
    g = {"Path": path_cls}
    exec(fn, g)
    got = g["_find_gatekeeper"]()
    print("    %-22s -> %s" % (label, got))


print("[2b] 主目录启动（cwd == home，应仍绑定）")
run(StubPath, "cwd=home")


class StubPath2(Base):
    @classmethod
    def cwd(cls): return cls(r"C:\Users\ADMIN\Documents")
    @classmethod
    def home(cls): return cls(r"C:\Users\ADMIN")


print("[2c] 主目录下其它位置启动（应解绑）")
run(StubPath2, "cwd=~/Documents")

print()
print("[3] 残余加载点排查")
sp = pathlib.Path(r"C:\Python312\Lib\site-packages")
try:
    names = sorted(p.name for p in sp.iterdir())
    print("    entries =", len(names))
    print("    .pth    :", [n for n in names if n.endswith(".pth")])
    print("    custom  :", [n for n in names if "customize" in n.lower()])
except Exception as e:
    print("    枚举失败:", type(e).__name__, e)
