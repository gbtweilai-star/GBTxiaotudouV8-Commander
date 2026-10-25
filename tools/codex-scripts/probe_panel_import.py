# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
import os
import sys
import tempfile
import traceback
WS = _GBT_ROOT
os.environ["GBT_STORE_DIR"] = tempfile.mkdtemp(prefix="gbt_panel_import_")
os.environ["GBT_SERVICE_DISCOVERY"] = "0"
os.environ["GBT_OWNER_SESSION"] = "1"
sys.path.insert(0, WS)
sys.path.insert(0, os.path.join(WS, "holo_pet"))
sys.path.insert(0, os.path.join(WS, "potato_pet"))
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "panel_server_probe", os.path.join(WS, "holo_pet", "panel_server.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["panel_server_probe"] = mod
    spec.loader.exec_module(mod)
    print("IMPORT_OK")
    print("HoloBridge:", bool(getattr(mod, "HoloBridge", None)))
    print("ChatClient:", getattr(mod, "ChatClient", None) is not None)
    print("CB:", bool(getattr(mod, "CB", None)))
except Exception:
    print("IMPORT_FAIL")
    traceback.print_exc()
