"""GBT小土豆V8 · 触手：桌面指挥官（Desktop Commander MCP）。

Owner 想法（2026-09-12）："npx @wonderwhy-er/desktop-commander@latest remote 给GBT小土豆V8整上"。

Desktop Commander = 把「终端 + 文件系统」打包成 MCP 工具集（26 个工具）：
读写文件（含 Excel/PDF/DOCX）、执行命令、进程管理、搜索、会话交互。
本模块把这条触手接进框架，提供两种形态：

1) 本地 stdio（默认，立即可用、无需认证）：
   connect() → tools() → call(tool, args)
   —— 复用 tentacle/mcp_bridge 的 JSON-RPC 桥。

2) remote 设备（把本机挂到桌面指挥官的云端中继，供 ChatGPT/Claude Web 等远程驱动）：
   remote_start() / remote_status() / remote_stop()
   —— remote device 只在你启动时运行，命令在本机以你的用户权限执行，Ctrl+C/stop 即停。

纪律：每次连接/调用/启停落审计；工具不存在或调用失败如实上报，不伪造结果。
"""
import json
import subprocess
import time
from pathlib import Path

from . import mcp_bridge as MB
from .._paths import STORE_DIR

SERVER_KEY = "desktop_commander"
DEFAULT_CMD = ["npx", "-y", "@wonderwhy-er/desktop-commander@latest", "--no-onboarding"]
REMOTE_CMD = ["npx", "-y", "@wonderwhy-er/desktop-commander@latest", "remote"]
_REMOTE_LOG = STORE_DIR / "dc_remote.log"
_REMOTE_PID = STORE_DIR / "dc_remote.pid"
_remote_proc = None


def _resolve_dc_entry():
    """定位 npx 缓存里的 dist/index.js——跳过 npx/cmd 包装层（那层会缓冲 stdout，
    导致 remote 设备日志落盘为空、无法诊断）。找不到则返回 None（回退 npx）。"""
    import glob
    import os
    la = os.environ.get("LOCALAPPDATA") or ""
    pat = os.path.join(la, "npm-cache", "_npx", "*", "node_modules",
                       "@wonderwhy-er", "desktop-commander", "dist", "index.js")
    hits = sorted(glob.glob(pat), key=os.path.getmtime, reverse=True)
    return hits[0] if hits else None


def _remote_cmd():
    """remote 设备启动命令：优先 node 直跑（同步输出到文件）+ 品牌注入 preload，回退 npx。

    品牌：preload 覆写 os.hostname()，让设备以 GBT小土豆V8 身份上报云端（见 dc_brand_preload.js）。

    ⚠️ 2026-09-19 修（回退路径缺品牌注入 · 由单测逐条追根挖出）：
    旧回退直接返回 `REMOTE_CMD`（`npx -y … remote`）—— **回退路径完全没有品牌注入**，
    而 README 承诺"remote 设备通过 preload 注入品牌"。也就是说：**任何没装本地入口的机器**，
    设备会以原名上报，承诺当场失效；而这条红一直被归在"环境"里没人单独验。
    修法：回退时也走 **node 直跑 npx 的 JS 入口**，从而能把 `--require <preload>` 注进去 ——
    **回退路径与主路径同权**（坑册第 16 条）。
    找不到 npx 的 JS 入口时才退回原样，且此时是**真的没有办法**，不是懒得做。
    """
    import shutil
    entry = _resolve_dc_entry()
    node = shutil.which("node")
    preload = Path(__file__).resolve().parent / "dc_brand_preload.js"
    if entry and node:
        if preload.exists():
            return [node, "--require", str(preload), entry, "remote"]
        return [node, entry, "remote"]
    # 回退：用 node 直跑 npx 的 JS 入口，好把品牌 preload 一起注进去
    if node and preload.exists():
        npx = shutil.which("npx") or shutil.which("npx.cmd")
        if npx:
            npx_js = Path(npx).resolve().parent / "node_modules" / "npm" / "bin" / "npx-cli.js"
            if npx_js.is_file():
                return [node, "--require", str(preload), str(npx_js)] + list(REMOTE_CMD[1:])
    return list(REMOTE_CMD)

# 工具清单按用途归类（便于人读，不是能力白名单——能力口径仍以服务端 tools/list 为准）
TOOL_GROUPS = {
    "配置": ["get_config", "set_config_value", "get_prompts"],
    "终端": ["start_process", "read_process_output", "interact_with_process",
             "force_terminate", "list_sessions", "list_processes", "kill_process"],
    "文件": ["read_file", "read_multiple_files", "write_file", "write_pdf",
             "create_directory", "list_directory", "move_file", "get_file_info", "edit_block"],
    "搜索": ["start_search", "get_more_search_results", "stop_search", "list_searches"],
    "分析": ["get_usage_stats", "get_recent_tool_calls"],
    "反馈": ["give_feedback_to_desktop_commander"],
}


def _audit(event: str, meta: dict):
    from ..store import audit
    audit(event, meta)


def connect(command=None) -> dict:
    """连接/复用桌面指挥官 MCP 会话（默认 npx stdio）。"""
    cmd = list(command) if command else list(DEFAULT_CMD)
    r = MB.connect(SERVER_KEY, cmd)
    _audit("dc_connect", {"ok": bool(r.get("ok")), "cmd": cmd[0],
                          "server": (r.get("server") or {}).get("name") if isinstance(r.get("server"), dict) else None})
    return r


def tools() -> dict:
    """契约清单 + 按用途归类摘要。"""
    r = MB.list_tools(SERVER_KEY)
    if not r.get("ok"):
        return r
    by_name = {t["name"]: t for t in r.get("tools", [])}
    groups = {g: [n for n in names if n in by_name] for g, names in TOOL_GROUPS.items()}
    return {"ok": True, "count": r.get("count"), "groups": groups, "tools": r.get("tools", [])}


def call(tool: str, arguments=None) -> dict:
    """按契约调用一个工具（终端/文件等）。"""
    if not tool:
        raise ValueError("需要 tool：要调用的桌面指挥官工具名（清单见 tools()）")
    r = MB.call(SERVER_KEY, tool, arguments or {})
    _audit("dc_call", {"tool": tool, "ok": bool(r.get("ok"))})
    return r


def _pid_alive(pid: int) -> bool:
    """跨进程判定 pid 存活（Windows tasklist）。"""
    if not pid:
        return False
    try:
        # 2026-10-04 修（深扫实测抓到）：tasklist 是系统 CLI，中文 Windows 输出 ANSI(GBK)。
        # 原写法 text=True 无编码 ⇒ 在 UTF-8 模式（PYTHONUTF8=1）下读线程直接
        # UnicodeDecodeError('utf-8' codec can't decode byte 0xd0) ⇒ 存活判定恒 False。
        # 口径同 tools/tentacle_fleet.py:321「这类系统工具的读数一律按 mbcs 解」。
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                             capture_output=True, encoding="mbcs", errors="replace",
                             timeout=8).stdout
        return str(pid) in out
    except Exception:
        return False


def _read_pid():
    try:
        return int(_REMOTE_PID.read_text(encoding="utf-8").strip())
    except Exception:
        return 0


def _write_pid(pid: int):
    try:
        _REMOTE_PID.parent.mkdir(parents=True, exist_ok=True)
        _REMOTE_PID.write_text(str(pid), encoding="utf-8")
    except Exception:
        pass


def status() -> dict:
    """会话与 remote 设备状态（只读）。跨进程：以 PID 文件为准。"""
    import shutil
    alive = False
    try:
        alive = bool(MB.status().get("servers", {}).get(SERVER_KEY, {}).get("alive"))
    except Exception:
        alive = False
    pid = _read_pid()
    remote_alive = _pid_alive(pid) or bool(_remote_proc and _remote_proc.poll() is None)
    try:
        from .remote_confinement import ttl_state
        ttl = ttl_state()
    except Exception:                                              # noqa: BLE001
        ttl = {"ok": False}
    return {"ok": True, "server": SERVER_KEY, "connected": alive,
            "remote_running": remote_alive, "remote_pid": (pid or None),
            "ttl": ttl,
            "npx": shutil.which("npx"), "remote_log": str(_REMOTE_LOG)}


def remote_start(wait=16, *, profile: str = "", ttl_s: int = 0,
                 acknowledge_host_execution: bool = False, grant=None) -> dict:
    """启动 remote 设备（后台、脱离父进程），输出落 store/dc_remote.log，PID 落盘。

    用 node 直跑 dist/index.js（避开 npx/cmd 的 stdout 缓冲）——日志即时可读。

    🔴 2026-10-09（主人点破「执行的人没被关进沙箱」）：本函数**先过隔离闸**——
       未隔离 + 无 remote_device 票 ⇒ **一律拒启**（fail-closed），并如实说清怎么才能开。
       闸在 tentacle/remote_confinement.py；本函数不自判、不自授权。
    """
    from .remote_confinement import (guard_start, mark_started, DEFAULT_TTL_S)
    _g = guard_start(profile=profile, grant=grant, ttl_s=(ttl_s or DEFAULT_TTL_S),
                     acknowledge_host_execution=acknowledge_host_execution)
    if not _g.get("ok"):
        _audit("dc_remote_start_blocked", {"reason": _g.get("reason"),
                                           "why": str(_g.get("why"))[:200]})
        return {"ok": False, "blocked": True, "拒绝": _g}
    global _remote_proc
    pid = _read_pid()
    if _pid_alive(pid) or (_remote_proc and _remote_proc.poll() is None):
        return {"ok": True, "note": "remote 设备已在运行", "pid": pid or _remote_proc.pid}
    try:
        _REMOTE_LOG.parent.mkdir(parents=True, exist_ok=True)
        f = open(_REMOTE_LOG, "a", encoding="utf-8")
        f.write(f"\n=== remote device start {time.strftime('%Y-%m-%dT%H:%M:%S')} ===\n")
        f.flush()
        _remote_proc = subprocess.Popen(
            MB.MCPBridge._resolve_cmd(_remote_cmd()),
            stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8",
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"[:160]}
    _write_pid(_remote_proc.pid)
    mark_started(_remote_proc.pid, _g.get("profile") or "unknown", ttl_s or DEFAULT_TTL_S)  # TTL 看门狗
    _audit("dc_remote_start", {"pid": _remote_proc.pid, "profile": _g.get("profile")})
    time.sleep(wait)  # 等握手：连接云端 + 恢复会话 + 标记在线
    return {"ok": True, "pid": _remote_proc.pid, "log": str(_REMOTE_LOG),
            "tail": remote_status().get("tail", "")}


def remote_status(tail_lines=40) -> dict:
    """读取 remote 设备状态与日志尾部（设备在线信息 / 报错）。跨进程以 PID 文件为准。"""
    pid = _read_pid()
    running = _pid_alive(pid) or bool(_remote_proc and _remote_proc.poll() is None)
    tail = ""
    online = False
    if _REMOTE_LOG.exists():
        try:
            lines = _REMOTE_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
            tail = "\n".join(lines[-tail_lines:])
            # 在线判定用独立窗口（不随调用者的 tail_lines 缩水）
            win = "\n".join(lines[-max(tail_lines, 200):])
            online = ("Device ready" in win or "marked as online" in win) and "Disconnected" not in win
        except Exception:
            tail = ""
    return {"ok": True, "running": running, "online": online,
            "pid": (pid or None), "tail": tail}


def remote_stop() -> dict:
    """停止 remote 设备（跨进程：按 PID 文件 taskkill）。"""
    global _remote_proc
    pid = _read_pid()
    if not (_pid_alive(pid) or (_remote_proc and _remote_proc.poll() is None)):
        return {"ok": True, "note": "remote 设备未在运行"}
    pid = pid or _remote_proc.pid
    try:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, text=True, timeout=10)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}
    try:
        _REMOTE_PID.unlink()
    except Exception:
        pass
    _audit("dc_remote_stop", {"pid": pid})
    return {"ok": True, "stopped_pid": pid}


def summary() -> str:
    s = status()
    return (f"桌面指挥官触手 · 已连接={s['connected']} · remote设备={s['remote_running']}")
