# -*- coding: utf-8 -*-
"""APP 部署自检（可反复跑）：把"卡在哪"逐行列出来。

用法：  C:\\Python310\\python.exe holo_pet\\deploy_check.py
口径：  **每个解释器分别测**（写在 3.14 里测出的依赖结论不能代表 3.10/3.12）。
"""
import importlib.util as iu
import json
import os
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PANEL = "http://127.0.0.1:8765"
CANDIDATES = [r"C:\Python310\python.exe", r"C:\Python312\python.exe",
              r"C:\Python311\python.exe", r"C:\Python313\python.exe"]

# 坑册第 2 条：Windows 控制台默认 GBK —— 打中文/emoji 会 UnicodeEncodeError 崩掉脚本。
# 本仓既定解法：显式 reconfigure 成 utf-8（errors=replace 兜底，绝不因打印崩）。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def probe_py(exe, mods):
    code = ("import importlib.util as u,json;"
            "print(json.dumps({m:(u.find_spec(m) is not None) for m in %r}))" % (mods,))
    try:
        p = subprocess.run([exe, "-c", code], capture_output=True, text=True, timeout=25)
        if p.returncode != 0:
            return {"_error": (p.stderr or "").strip().splitlines()[-1][:90]}
        return json.loads(p.stdout.strip().splitlines()[-1])
    except Exception as exc:  # noqa: BLE001
        return {"_error": f"{type(exc).__name__}: {exc}"[:90]}


def main():
    print("=" * 66)
    print("GBT APP 部署自检")
    print("=" * 66)
    print("\n[1] 逐解释器依赖矩阵（面板: fastapi/uvicorn；桌宠: PySide6/live2d）")
    mods = ["PySide6", "live2d", "fastapi", "uvicorn", "requests", "httpx",
            "websockets", "comtypes", "PIL", "numpy"]
    for exe in CANDIDATES:
        if not Path(exe).exists():
            print("  %-26s (不存在)" % exe)
            continue
        got = probe_py(exe, mods)
        if "_error" in got:
            print("  %-26s ⚠️ 起不来：%s" % (exe, got["_error"]))
            continue
        miss = [m for m in mods if not got.get(m)]
        print("  %-26s 缺: %s" % (exe, ", ".join(miss) if miss else "无（全有）"))

    print("\n[2] 启动件")
    for rel in ("potato_pet/main.py", "potato_pet/启动小土豆.bat",
                "holo_pet/launch_panel.py", "holo_pet/panel_server.py",
                "holo_pet/desktop/main.cjs", "holo_pet/启动桌面数字人.bat",
                "holo_pet/node_modules/electron/dist/electron.exe"):
        print("  %-44s %s" % (rel, "✅" if (ROOT / rel).exists() else "❌ 缺"))

    print("\n[3] 面板是否在跑 + 对话通道")
    try:
        with urllib.request.urlopen(PANEL + "/api/state", timeout=4) as r:
            st = json.loads(r.read().decode("utf-8", "replace"))
        cx = st.get("codex") or {}
        print("  /api/state        ✅ HTTP 200")
        print("  codex.connected   %s" % ("✅ true" if cx.get("connected") else "❌ false（未登录 ⇒ 对话走降级大脑）"))
    except Exception as exc:  # noqa: BLE001
        print("  /api/state        ❌ %s（面板没在跑？先执行 start-holo-panel.bat）" % type(exc).__name__)

    print("\n[4] 凭据")
    print("  deepseek_api.dpapi %s" % ("✅" if (ROOT / "gbt_allinone/store/secrets/deepseek_api.dpapi").exists() else "❌"))
    key_env = os.environ.get("GBT_LLM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    print("  env LLM key        %s" % ("✅ 已设（掩码 %s****）" % key_env[:4] if key_env else "❌ 未设（降级大脑会离线）"))

    print("\n[5] 结论指引")
    print("  面板对话可用 = /api/state 200（降级大脑即可答；codex 登录后走内核）")
    print("  桌面数字人   = 双击 holo_pet\\启动桌面数字人.bat（GUI 必须在交互桌面）")
    print("  桌宠形态     = 需先给首选解释器装 PySide6 + live2d-py")


if __name__ == "__main__":
    main()
