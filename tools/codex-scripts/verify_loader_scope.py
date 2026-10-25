# -*- coding: utf-8 -*-
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径
#    `C:\Users\ADMIN\Desktop\GBT小土豆V8`，Linux/手机上会**造出一个同名垃圾目录**。
#    改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
"""验证收窄后的加载器：三种启动目录下的绑定行为。"""
import os
import re
import pathlib

SRC = r"C:\Python312\Lib\site-packages\sitecustomize.py"
src = pathlib.Path(SRC).read_text(encoding="utf-8")

# 1) 整份语法完整性
compile(src, SRC, "exec")
print("[1] syntax OK, size =", len(src), "chars")

# 2) 抽出 _find_gatekeeper 单独仿真
m = re.search(r"def _find_gatekeeper\(\):.*?\n    return None\n", src, re.S)
assert m, "function not found"
fn = m.group(0)
print("[2] extracted %d chars" % len(fn))

cases = [
    (_GBT_ROOT, "V8 工作区", None),
    (_GBT_ROOT + "/gbt_allinone", "V8 子目录", None),
    (r"C:\Users\ADMIN\Desktop\GBT小土豆", "V5 项目根", r"C:\Users\ADMIN\Desktop\GBT小土豆\brain\gatekeeper.py"),
    (r"C:\Users\ADMIN", "用户主目录", r"C:\Users\ADMIN\brain\gatekeeper.py"),
]
ok = True
for cwd, label, expect in cases:
    os.chdir(cwd)
    g = {"Path": pathlib.Path}
    exec(fn, g)
    got = g["_find_gatekeeper"]()
    got_s = str(got) if got else None
    hit = (got_s == expect) if expect else (got_s is None)
    ok = ok and hit
    print("    %-12s cwd=%-45s -> %s   %s" % (label, cwd, got_s, "OK" if hit else "MISMATCH(expect %s)" % expect))

# 3) 残余加载点排查：site-packages 下的 .pth / usercustomize（可能另起炉灶加载门禁）
sp = pathlib.Path(r"C:\Python312\Lib\site-packages")
try:
    names = sorted(p.name for p in sp.iterdir())
    print("[3] site-packages entries =", len(names))
    print("    .pth:", [n for n in names if n.endswith(".pth")])
    print("    custom:", [n for n in names if "customize" in n.lower()])
except Exception as e:
    print("[3] site-packages 枚举失败:", e)

print("[VERDICT]", "PASS" if ok else "FAIL")
