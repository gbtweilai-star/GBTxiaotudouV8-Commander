"""test_console_service.py · 原生壳自启认知界面服务（:8766）

不做"文件存在就算过"的假验证：
  1) 真起一个隔离端口（18766）的 console-server，确认 /api/state 200、caps=当前真源；
  2) 用状态文件里的 pid 真停掉，确认端口回到离线；
  3) 再确保正式端口（8766）在线，状态文件恢复指向正式进程；
  4) 静态检查三条原生入口都挂了自启：Electron main.cjs / Python 桌面壳 app.py / 启动-GBT.cmd。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILS = []


def check(name, cond, extra=""):
    ok = bool(cond)
    print(("  ok   " if ok else "  FAIL ") + name + ((" · " + extra) if extra else ""))
    if not ok:
        FAILS.append(name)


def main() -> int:
    print("[0] 导入 console_service")
    from gbt_allinone import console_service as CS
    check("模块导入", CS is not None)
    check("默认端口 8766", CS.PORT == 8766, str(CS.PORT))

    print("[1] 隔离端口 18766 真起真停")
    down = CS.ping(18766, timeout=0.8)
    check("测前离线", down.get("ok") is False, str(down.get("reason"))[:60])
    r = CS.start(18766, wait_s=25)
    check("start ok", r.get("ok") is True, str(r.get("reason"))[:80])
    from gbt_allinone.tentacle import doc_counts as DC
    expect_caps = DC.current_count()
    # start 的 caps 来自 /api/state 冷缓存，可能为空；状态下真查到的必须等于真源
    check("start 返回 caps 或留空", r.get("caps") in (None, expect_caps), str(r.get("caps")))
    up = CS.ping(18766)
    check("起后在线", up.get("ok") is True)
    stopped = CS.stop()
    check("stop ok", stopped.get("ok") is True, str(stopped))
    import time
    t0 = time.time()
    off = True
    while time.time() - t0 < 15:
        time.sleep(0.5)
        if CS.ping(18766, timeout=0.6).get("ok") is False:
            off = True
            break
        off = False
    check("停后离线", off)

    print("[2] 正式端口 8766 恢复在线（状态文件指向正式进程）")
    a = CS.ensure_server(8766)
    check("8766 在线", a.get("ok") is True, str(a.get("reason"))[:80])
    st = CS.status(8766)
    check("status.up", st.get("up") is True)
    check("status caps=真源", st.get("caps") == expect_caps,
          "%s != %s" % (st.get("caps"), expect_caps))
    _last = st.get("last") or {}
    check("状态文件指向 8766", _last.get("port") == 8766, str(_last))

    print("[2b] 双开事故回归（2026-11-02：健康检查假阴性 + Windows 端口复用 ⇒ 两个 server 抢请求）")
    srv_src = (ROOT / "tools" / "console-server.py").read_text(encoding="utf-8")
    svc_src = (ROOT / "gbt_allinone" / "console_service.py").read_text(encoding="utf-8")
    check("服务端有轻量 /api/ping", '"/api/ping"' in srv_src and '"pong"' in srv_src)
    check("Windows 禁止端口复用（防双开）", 'allow_reuse_address = sys.platform != "win32"' in srv_src)
    check("健康检查先探 /api/ping", '"/api/ping"' in svc_src)
    check("already 分支保留真 pid", 'p.get("pid")' in svc_src)
    check("stop 先验命令行（不误杀）", "_ours(" in svc_src and "console-server.py" in svc_src)
    again = CS.start(8766)
    check("连 start 第二次 already=true（不双开）",
          again.get("ok") is True and again.get("already") is True, str(again)[:140])
    pids = CS._listener_pids(8766)
    check("8766 只有一个监听进程", len(pids) == 1, str(pids))
    check("ping 报的 pid == 监听 pid", again.get("pid") in pids,
          str({"ping": again.get("pid"), "listen": pids}))
    _st2 = json.loads((ROOT / "gbt_allinone" / "store" / "console-server.json").read_text(encoding="utf-8")) \
        if (ROOT / "gbt_allinone" / "store" / "console-server.json").is_file() else {}
    check("状态文件 pid 非 0（stop 才有得杀）", int(_st2.get("pid") or 0) > 0, str(_st2.get("pid")))

    print("[3] 三条原生入口都挂了自启")
    cjs = ROOT / "holo_pet_w3" / "shell" / "console-service.cjs"
    check("Electron 自启模块存在", cjs.is_file())
    cj = cjs.read_text(encoding="utf-8") if cjs.is_file() else ""
    check("模块含 ensureConsoleServer", "ensureConsoleServer" in cj)
    check("模块用 pyembed/python 兜底", "pyembed" in cj and "py" in cj)
    main_cjs = (ROOT / "holo_pet_w3" / "shell" / "main.cjs").read_text(encoding="utf-8")
    check("main.cjs 已 require 自启模块", "console-service.cjs" in main_cjs)
    check("main.cjs 建窗前调用", "ensureConsoleServer()" in main_cjs)
    app_py = (ROOT / "gbt_allinone" / "app.py").read_text(encoding="utf-8")
    check("Python 桌面壳 main() 自启", "from .console_service import ensure_server" in app_py)
    launcher = (ROOT / "启动-GBT.cmd").read_text(encoding="utf-8", errors="replace")
    check("启动器含 console-server", "console-server.py" in launcher and "8766" in launcher)
    check("登录自启包装器", (ROOT / "tools" / "autostart" / "GBT-console.cmd").is_file())
    check("一键安装脚本", (ROOT / "tools" / "设置开机自启.cmd").is_file())
    check("自启安装器存在", (ROOT / "tools" / "install-autostart.py").is_file())

    print()
    if FAILS:
        print("FAILED: " + ", ".join(FAILS))
        return 1
    print("ALL OK —— 原生壳自启真起真停，三条入口都挂了")
    return 0


if __name__ == "__main__":
    sys.exit(main())
