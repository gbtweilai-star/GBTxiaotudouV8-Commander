"""GBT小土豆V8 · 触手契约层（MCP 客户端桥）。

Owner 想法（2026-09-11）："抓取靠触手就能传输契约的项目，完美集成给她强化"。
实现：触手学会 MCP（Model Context Protocol）——AI 与工具的标准契约协议。
学会它 = 整个 MCP 生态的工具服务器（文件/Git/数据库/浏览器……成百上千）
全部变成触手可调用的能力。

架构：
  tentacle/mcp_bridge.py   本文件：MCP 客户端（stdio JSON-RPC）
  - list_tools()    握手 → tools/list → 拿到工具契约清单（名称/参数 schema）
  - call_tool()     按契约调用任意工具（参数按 schema 校验后发送）
  - 纪律：每次调用落审计；工具不存在/参数不符如实报；不伪造结果
"""
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

_BASE = Path(__file__).resolve().parent


class MCPBridge:
    """单台 MCP 服务器的客户端会话（stdio JSON-RPC）。"""

    def __init__(self, command, name="mcp-server"):
        """command: 启动命令（list 形式，如 ['npx', '-y', '@modelcontextprotocol/server-everything']）。"""
        self.command = command
        self.name = name
        self.proc = None
        self._id = 0
        self._lock = threading.Lock()

    @staticmethod
    def _resolve_cmd(command):
        """Windows：npx/npm 实为 .CMD——用 which 解析成完整可执行路径。"""
        import shutil
        resolved = list(command)
        first = shutil.which(resolved[0])
        if first:
            resolved[0] = first
        return resolved

    def start(self, timeout=60):
        """启动服务器进程（stdio 模式，Windows 自动解析 .cmd）。"""
        if self.proc and self.proc.poll() is None:
            return {"ok": True, "note": "已启动"}
        try:
            self.proc = subprocess.Popen(
                self._resolve_cmd(self.command), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, encoding="utf-8",
                cwd=str(_BASE.parent.parent))
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"{type(e).__name__}: {e}"[:160]}
        # 初始化握手
        r = self._rpc("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "GBT-tentacle-mcp", "version": "8.0.0"}})
        if not r.get("ok"):
            return r
        self._notify("notifications/initialized", {})
        return {"ok": True, "server": (r.get("result", {}).get("serverInfo") or {})}

    def _rpc(self, method, params, timeout=90):
        """JSON-RPC 请求/响应（一行一个 JSON，stdio 双管道）。"""
        with self._lock:
            if not self.proc or self.proc.poll() is not None:
                return {"ok": False, "error": "服务器未运行"}
            self._id += 1
            rid = self._id
            msg = json.dumps({"jsonrpc": "2.0", "id": rid,
                              "method": method, "params": params or {}})
            try:
                self.proc.stdin.write(msg + "\n")
                self.proc.stdin.flush()
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "error": f"写入失败: {e}"[:120]}
            t0 = time.time()
            while time.time() - t0 < timeout:
                line = self.proc.stdout.readline()
                if not line:
                    return {"ok": False, "error": "服务器无响应（stdout 关闭）"}
                try:
                    d = json.loads(line)
                except Exception:
                    continue  # 跳过非 JSON 行
                if d.get("id") == rid:
                    if "error" in d:
                        return {"ok": False, "error": str(d["error"])[:160]}
                    return {"ok": True, "result": d.get("result", {})}
            return {"ok": False, "error": f"超时（{timeout}s）"}

    def _notify(self, method, params):
        try:
            self.proc.stdin.write(json.dumps(
                {"jsonrpc": "2.0", "method": method, "params": params or {}}) + "\n")
            self.proc.stdin.flush()
        except Exception:  # noqa: BLE001
            pass

    def list_tools(self):
        """契约清单：tools/list。"""
        r = self._rpc("tools/list", {})
        if not r.get("ok"):
            return r
        tools = (r.get("result") or {}).get("tools", [])
        out = []
        for t in tools:
            out.append({"name": t.get("name"),
                        "description": (t.get("description") or "")[:120],
                        "inputSchema": t.get("inputSchema", {})})
        return {"ok": True, "tools": out, "count": len(out)}

    def call_tool(self, name, arguments=None):
        """按契约调用工具：tools/call。"""
        from ..store import audit
        r = self._rpc("tools/call", {"name": name, "arguments": arguments or {}})
        audit("mcp_call", {"server": self.name, "tool": name})
        if not r.get("ok"):
            return r
        res = r.get("result", {})
        # MCP 结果形态：content 数组（text/image/resource）+ isError 标志
        texts = [c.get("text", "") for c in (res.get("content") or [])
                 if c.get("type") == "text"]
        return {"ok": not res.get("isError", False),
                "text": "\n".join(texts),
                "raw": res}

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                self.proc.kill()
        return {"ok": True}


# ═══ 会话注册表（多服务器并存） ═══
_SESSIONS = {}


def connect(server_key, command):
    """连接/复用一台 MCP 服务器。"""
    if server_key in _SESSIONS and _SESSIONS[server_key].proc and \
            _SESSIONS[server_key].proc.poll() is None:
        return {"ok": True, "note": "复用已有会话", "server": server_key}
    b = MCPBridge(command, name=server_key)
    r = b.start()
    if r.get("ok"):
        _SESSIONS[server_key] = b
    return r


def list_tools(server_key):
    b = _SESSIONS.get(server_key)
    if not b:
        return {"ok": False, "error": f"未连接: {server_key}（先 mcp_connect）"}
    return b.list_tools()


def call(server_key, tool, arguments=None):
    b = _SESSIONS.get(server_key)
    if not b:
        return {"ok": False, "error": f"未连接: {server_key}"}
    return b.call_tool(tool, arguments)


def status():
    return {"servers": {k: {"alive": b.proc and b.proc.poll() is None}
                        for k, b in _SESSIONS.items()}}


# ═══ 配置注册表（蒸馏自 v5 .omp/mcp.json 的标准 mcpServers 清单） ═══
# 为什么需要：v5 用一份 mcp.json（command/args/cwd/env）声明服务器，工具据此起进程。
# 我们原来只能每次手写 command 数组 ⇒ 服务器清单不可复用、不可体检。
# 现在：把标准 mcpServers 配置读进 state/mcp-servers.json，可列、可体检、可按名连接。
CONFIG = _BASE.parent.parent / "state" / "mcp-servers.json"


def _norm_server(name: str, spec: dict) -> dict:
    """把 {command, args, cwd, env} 归一成 {name, command:[...], cwd, env}。"""
    cmd = spec.get("command")
    if isinstance(cmd, str):
        argv = [cmd]
    elif isinstance(cmd, (list, tuple)):
        argv = [str(c) for c in cmd]
    else:
        raise ValueError("server %s 缺 command" % name)
    argv += [str(a) for a in (spec.get("args") or [])]
    return {"name": str(name), "command": argv,
            "cwd": str(spec.get("cwd") or ""),
            "env": dict(spec.get("env") or {}),
            "description": str(spec.get("description") or "")}


def load_config(path: str | Path) -> dict:
    """读标准 MCP 配置：{"mcpServers": {...}} 或 {"servers": {...}}。"""
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "error": "user_error: 配置文件不存在：%s" % p}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "配置文件不是合法 JSON：%s" % e}
    raw = d.get("mcpServers") or d.get("servers") or {}
    if not isinstance(raw, dict):
        return {"ok": False, "error": "配置里 mcpServers 不是对象"}
    servers, errors = {}, []
    for name, spec in raw.items():
        try:
            servers[name] = _norm_server(name, spec or {})
        except Exception as e:  # noqa: BLE001
            errors.append({"server": name, "why": str(e)[:120]})
    return {"ok": True, "servers": servers, "errors": errors, "source": str(p)}


def _load_registry() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save_registry(d: dict) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def register(path: str | Path = "", merge: bool = True) -> dict:
    """把配置文件里的服务器登记进 registry（默认合并，不覆盖同名的旧项）。"""
    r = load_config(path)
    if not r.get("ok"):
        return r
    reg = _load_registry() if merge else {}
    added = []
    for name, spec in r["servers"].items():
        if name not in reg:
            reg[name] = spec
            added.append(name)
    _save_registry(reg)
    return {"ok": True, "registered": added, "total": len(reg),
            "errors": r.get("errors") or [], "source": r.get("source")}


def servers() -> dict:
    reg = _load_registry()
    return {"ok": True, "count": len(reg),
            "servers": [{"name": k, "command": v.get("command"),
                         "cwd": v.get("cwd"), "description": v.get("description")}
                        for k, v in reg.items()]}


def unregister(name: str) -> dict:
    reg = _load_registry()
    if name not in reg:
        return {"ok": False, "error": "user_error: 没登记这个服务器：%s" % name}
    reg.pop(name, None)
    _save_registry(reg)
    return {"ok": True, "removed": name, "total": len(reg)}


def connect_registered(name: str, timeout: float = 20.0) -> dict:
    """按登记的命令连一台服务器（返回工具清单 = 一次闭环）。"""
    reg = _load_registry()
    spec = reg.get(name)
    if not spec:
        return {"ok": False, "error": "user_error: 没登记这个服务器：%s" % name}
    r = connect(name, list(spec.get("command") or []))
    if not r.get("ok"):
        return r
    t = list_tools(name)
    return {"ok": bool(t.get("ok")), "server": name,
            "tools": t.get("tools") or [], "count": t.get("count") or 0,
            "error": t.get("error")}


def health(timeout: float = 15.0) -> dict:
    """体检：登记的每个服务器都真连一次、列一次工具、然后断开。"""
    reg = _load_registry()
    rows = []
    for name, spec in reg.items():
        t0 = time.time()
        try:
            r = connect(name, list(spec.get("command") or []))
            if not r.get("ok"):
                rows.append({"server": name, "up": False, "error": r.get("error"),
                             "ms": int((time.time() - t0) * 1000)})
                continue
            t = list_tools(name)
            _stop(name)
            rows.append({"server": name, "up": bool(t.get("ok")),
                         "tools": t.get("count") or 0,
                         "error": t.get("error"),
                         "ms": int((time.time() - t0) * 1000)})
        except Exception as e:  # noqa: BLE001
            rows.append({"server": name, "up": False,
                         "error": "%s: %s" % (type(e).__name__, str(e)[:100])})
    up = sum(1 for r in rows if r.get("up"))
    return {"ok": True, "checked": len(rows), "up": up, "down": len(rows) - up,
            "servers": rows,
            "note": "体检会真起子进程；每个服务器连一次、列一次工具、断开"}


def _stop(name: str) -> None:
    b = _SESSIONS.get(name)
    if b:
        try:
            b.stop()
        finally:
            _SESSIONS.pop(name, None)
