# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
import hashlib
import sys
import time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(_GBT_ROOT)

TARGETS = {
    "holo_pet/panel_server.py": "d74caae258dbfd549f49119c7a04a3d8f1ad33f05bca6f8b75112d3134615214",
    "gbt_allinone/api.py": "fd72d385f4d084768930c64e7bc415a984c3f2913e3b3b9eec4bc7f06298577d",
}
EXTRA = ["gbt_allinone/codex_bridge.py", "gbt_allinone/security/policy.py",
         ".scratch/panel_server.py.preblock2.bak",
         ".scratch/codex_v2_mirror/mock_v2_server.py",
         ".scratch/codex_v2_mirror/panel_server_mirror.py",
         ".scratch/codex_v2_mirror/panel_server_mirror2.py"]


def h(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


print("%-52s %-12s %s" % ("file", "size", "mtime"))
print("-" * 100)
for rel, want in TARGETS.items():
    f = ROOT / rel
    got = h(f)
    st = f.stat()
    mt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
    ok = "MATCH" if got == want else "*** MISMATCH ***"
    print("%-52s %-12d %s" % (rel, st.st_size, mt))
    print("    sha256 %s  %s" % (got, ok))
    print("    expect %s" % want)
print()
for rel in EXTRA:
    f = ROOT / rel
    st = f.stat()
    mt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
    print("%-52s %-12d %s  %s" % (rel, st.st_size, mt, h(f)[:16]))
print()
bak = ROOT / ".scratch" / "panel_server.py.preblock2.bak"
prod = ROOT / "holo_pet" / "panel_server.py"
print("preblock2.bak == 生产 panel_server.py :", h(bak) == h(prod))
