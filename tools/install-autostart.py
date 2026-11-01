"""GBT小土豆V8 · 登录自启（认知界面服务 :8766）

主人 2026-11-01 令：「服务重启后要跑 python tools/console-server.py --port 8766，
这个直接做到原生 APP 里面自动执行就好了。」

做法：在 Windows 登录启动目录放一个 .cmd 包装器（不写注册表、可一眼看穿、可随时删）：
    %APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\GBT-console.cmd
包装器内容 = cd 到仓库 + pyembed\\python.exe 起 console-server（最小化、窗口不弹）。

用法：
    python tools/install-autostart.py --install    # 安装（幂等）
    python tools/install-autostart.py --remove     # 移除
    python tools/install-autostart.py --status     # 查看

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 8766
NAME = "GBT-console.cmd"


def startup_dir() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def target() -> Path:
    return startup_dir() / NAME


def render() -> str:
    py = ROOT / "pyembed" / "python.exe"
    py_line = str(py) if py.is_file() else "python"
    return (
        "@echo off\r\n"
        "rem GBT小土豆V8 · 认知界面服务 :%d 登录自启（删掉本文件即取消）\r\n"
        "cd /d \"%s\"\r\n"
        "start \"\" /min \"%s\" -X utf8 \"tools\\console-server.py\" --port %d\r\n"
        % (PORT, ROOT, py_line, PORT)
    )


def probe(port: int = PORT) -> bool:
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:%d/api/state" % port, timeout=1.2) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def install() -> int:
    d = startup_dir()
    d.mkdir(parents=True, exist_ok=True)
    t = target()
    try:
        t.write_text(render(), encoding="utf-8", errors="replace")
    except PermissionError:
        print("注意：当前进程没有写 Startup 的权限（沙箱/策略限制）—— 不假装装上了。")
        print("  已备好仓库内包装器: tools\\autostart\\GBT-console.cmd")
        print("  一键安装（请主人双击一次，用户态执行即可）: tools\\设置开机自启.cmd")
        print("  目标路径: %s" % t)
        return 2
    print("已安装登录自启: %s" % t)
    print("  端口: %d   (python: %s)" % (PORT, (ROOT / "pyembed" / "python.exe")
                                        if (ROOT / "pyembed" / "python.exe").is_file() else "python"))
    print("  说明: 下次登录自动起服务；本次要生效请现在手动跑一次或重登录。")
    return 0


def remove() -> int:
    t = target()
    if t.is_file():
        t.unlink()
        print("已移除登录自启: %s" % t)
    else:
        print("本来就没有: %s" % t)
    return 0


def status() -> int:
    t = target()
    print("登录自启文件: %s" % t)
    print("  存在: %s" % t.is_file())
    print("  服务在线: %s" % probe())
    if t.is_file():
        print("  内容:")
        for line in t.read_text(encoding="utf-8", errors="replace").splitlines():
            print("    " + line)
    return 0


def main(argv) -> int:
    cmd = argv[1] if len(argv) > 1 else "--status"
    if cmd == "--install":
        return install()
    if cmd == "--remove":
        return remove()
    return status()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
