# -*- coding: utf-8 -*-
"""真正的万能插座 —— 不再有固定的六类，给什么都行（2026-10-30 主人令）

为什么要有这个文件：原来的 omni_plug 只认 process/file/api/web/app/ai 六类，
**给不出第七种**。那不是万能插座，是六个固定格子。

现在的口径：
  ① 你给一个 target（任意字符串），我先**判断它是什么**（classify，纯分析、无副作用）
  ② 判断出 kind 后，**动态生成**对应的适配器（adapt，按 kind 现场拼一个 callable）
  ③ 适配器执行，返回统一形状 {ok, kind, via, evidence, ...}

关键：kind 不是枚举出来的封闭集合，而是"能从 target 里读出来的事实"。
遇到不认识的东西，classify 返回 unknown，adapt 仍会尝试**通用探法**（先当路径、再当主机、再当命令行），
而不是直接说"不支持"。这就是"万能"与"六类"的区别。

policy 那边也 import 这里的 classify（纯字符串分析、不联网），
所以「门」和「执行」看到的是同一个判断 —— 不会出现门按 A 类判、执行按 B 类干。
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import socket
import subprocess
import sys

SCHEME_RE = re.compile(r"^([a-z][a-z0-9+.\-]*):", re.I)
HOSTPORT_RE = re.compile(r"^(\[[0-9a-f:]+\]|[A-Za-z0-9_.\-]+):(\d{1,5})$")


def _is_executable(p: pathlib.Path) -> bool:
    """iSH 上几乎每个文件都是 X_OK，所以**不能**只看权限位 —— 要看真内容。
    ELF(\x7fELF) 或 shebang(#!) 才算可执行。"""
    try:
        with open(p, "rb") as fh:
            head = fh.read(4)
        return head[:4] == b"\x7fELF" or head[:2] == b"#!"
    except Exception:                                             # noqa: BLE001
        return False


def classify(target: str) -> dict:
    """判断 target 是什么。**纯分析、不联网、不落盘** —— policy 也要调用它。"""
    t = (target or "").strip()
    if not t:
        return {"kind": "unknown", "why": "target 为空"}

    m = SCHEME_RE.match(t)
    if m:
        sc = m.group(1).lower()
        if sc in ("http", "https"):
            return {"kind": "http", "scheme": sc, "why": "URL（%s）" % sc}
        if sc == "wss" or sc == "ws":
            return {"kind": "ws", "scheme": sc, "why": "WebSocket（%s）" % sc}
        if sc == "file":
            return {"kind": "path", "path": t[7:], "why": "file:// 路径"}
        if sc in ("ssh", "git", "git+ssh"):
            return {"kind": "remote", "scheme": sc, "why": "%s 远程" % sc}
        if sc == "mcp" or t.startswith("mcp+"):
            return {"kind": "mcp", "scheme": sc, "why": "MCP 端点"}
        if sc == "unix":
            return {"kind": "unix", "path": t[5:], "why": "Unix socket"}
        # 其余的 scheme 一律当「App / 系统接口」（ios: lmpocket: maps: tel: …）
        return {"kind": "scheme", "scheme": sc, "why": "App/系统 scheme（%s）" % sc}

    if HOSTPORT_RE.match(t):
        return {"kind": "tcp", "hostport": t, "why": "host:port"}

    if t.startswith("/") or t.startswith("./") or t.startswith("../") or t.startswith("~"):
        p = pathlib.Path(os.path.expanduser(t))
        if p.is_dir():
            return {"kind": "dir", "path": str(p), "why": "目录"}
        if p.exists():
            if p.is_file() and _is_executable(p):
                return {"kind": "bin", "path": str(p), "why": "可执行文件"}
            return {"kind": "path", "path": str(p), "why": "文件"}
        return {"kind": "path", "path": str(p), "why": "路径（不存在）"}

    # 不带斜杠、也不像主机端口：可能是命令名、包名、或裸域名
    if shutil.which(t):
        return {"kind": "bin", "path": shutil.which(t), "why": "命令（%s）" % shutil.which(t)}
    if "." in t and " " not in t:
        return {"kind": "http", "scheme": "https", "url": "https://" + t, "why": "裸域名 ⇒ 按 https 处理"}
    if " " in t:
        return {"kind": "cmd", "cmd": t, "why": "命令行"}
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_.\-]{1,40}", t):
        # 单个裸词：先按「App / 系统 scheme」试（settings / lmpocket / maps / tel …）
        return {"kind": "scheme", "scheme": t.lower(), "why": "裸词 ⇒ 先按 App/系统 scheme 试"}
    return {"kind": "unknown", "why": "认不出（既不是路径、命令、URL，也不是 scheme）"}


def _run(cmd, timeout=30):
    try:
        p = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True,
                           text=True, timeout=timeout)
        return {"rc": p.returncode, "out": (p.stdout or "")[:800], "err": (p.stderr or "")[:400]}
    except subprocess.TimeoutExpired:
        return {"rc": -1, "out": "", "err": "timeout"}
    except Exception as e:                                        # noqa: BLE001
        return {"rc": -1, "out": "", "err": "%s: %s" % (type(e).__name__, str(e)[:120])}


def _http_get(url, timeout=15):
    import urllib.error
    import urllib.request
    try:
        r = urllib.request.urlopen(url, timeout=timeout)
        body = r.read(400)
        return {"ok": True, "http": r.status, "head": body.decode("utf-8", "replace")[:200]}
    except urllib.error.HTTPError as e:
        return {"ok": True, "http": e.code, "head": "(HTTPError)"}   # 对端有应答，算可达
    except Exception as e:                                        # noqa: BLE001
        return {"ok": False, "err": "%s: %s" % (type(e).__name__, str(e)[:100])}


def _tcp_probe(hostport, timeout=3):
    h, _, p = hostport.rpartition(":")
    h = h.strip("[]")
    try:
        s = socket.create_connection((h, int(p)), timeout=timeout)
        s.close()
        return {"ok": True, "detail": "TCP 通 %s" % hostport}
    except Exception as e:                                        # noqa: BLE001
        return {"ok": False, "detail": "%s" % type(e).__name__}


def execute(target: str, verb: str = "", args: dict | None = None) -> dict:
    """万能入口：判断 → 生成适配器 → 执行。verb 不传就按 kind 选默认动作。"""
    args = args or {}
    info = classify(target)
    kind = info["kind"]
    verb = (verb or "").lower()

    if kind == "http":
        url = info.get("url") or target
        r = _http_get(url)
        return {"ok": bool(r.get("ok")), "kind": "http", "via": "omni:http",
                "evidence": "GET %s → http=%s %s" % (url, r.get("http"), r.get("err") or ""),
                "result": r}

    if kind == "tcp":
        r = _tcp_probe(info["hostport"])
        return {"ok": r["ok"], "kind": "tcp", "via": "omni:tcp", "evidence": r["detail"], "result": r}

    if kind in ("path", "dir", "bin"):
        p = info["path"]
        if verb == "" and info["kind"] == "bin":
            verb = "exec"                     # 可执行文件默认是「跑」，不是「读」
        if verb in ("read", "cat", ""):
            if os.path.isdir(p):
                return {"ok": True, "kind": "dir", "via": "omni:fs",
                        "evidence": "目录 %s（%d 项）" % (p, len(os.listdir(p)))}
            if not os.path.isfile(p):
                return {"ok": False, "kind": "path", "via": "omni:fs", "evidence": "不存在：%s" % p}
            try:
                data = pathlib.Path(p).read_bytes()[:600]
                return {"ok": True, "kind": "path", "via": "omni:fs",
                        "evidence": "读 %s · %d 字节（截断显示）" % (p, os.path.getsize(p)),
                        "head": data.decode("utf-8", "replace")[:200]}
            except Exception as e:                                # noqa: BLE001
                return {"ok": False, "kind": "path", "via": "omni:fs", "evidence": str(e)[:100]}
        if verb in ("stat", "info"):
            st = os.stat(p)
            return {"ok": True, "kind": kind, "via": "omni:fs",
                    "evidence": "%s · %d 字节 · mode=%o" % (p, st.st_size, st.st_mode)}
        r = _run([p] + [str(x) for x in (args.get("argv") or [])])
        return {"ok": r["rc"] == 0, "kind": "bin" if info["kind"] == "bin" else kind,
                "via": "omni:exec", "evidence": "rc=%s %s" % (r["rc"], r["err"][:60]), "result": r}

    if kind == "scheme":
        # iOS / 系统 scheme：交给 apple-open（真派发），并回报 opened
        r = _run(["apple-open", target], timeout=20)
        return {"ok": r["rc"] == 0, "kind": "scheme", "via": "omni:ios-scheme",
                "evidence": "scheme=%s rc=%s" % (info.get("scheme"), r["rc"]),
                "result": {"out": r["out"][:200]}}

    if kind == "unix":
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect(info["path"])
            s.close()
            return {"ok": True, "kind": "unix", "via": "omni:unix", "evidence": "已连通"}
        except Exception as e:                                    # noqa: BLE001
            return {"ok": False, "kind": "unix", "via": "omni:unix", "evidence": str(e)[:100]}

    if kind == "cmd":
        r = _run(info["cmd"])
        return {"ok": r["rc"] == 0, "kind": "cmd", "via": "omni:shell",
                "evidence": "rc=%s %s" % (r["rc"], r["err"][:60]), "result": r}

    if kind in ("mcp", "ws", "remote"):
        # 这三类需要各自协议栈；现在如实说"认得，但还没接执行器"，不假装成功
        return {"ok": False, "kind": kind, "via": "omni:%s" % kind,
                "evidence": "认得出是 %s（%s），但执行器还没接 —— 不冒充成功"
                            % (kind, info.get("why"))}

    # 认不出：仍给一次通用尝试（当命令跑），但标明是猜的
    r = _run(target)
    return {"ok": r["rc"] == 0, "kind": "unknown", "via": "omni:fallback",
            "evidence": "认不出，按命令试跑 rc=%s %s" % (r["rc"], r["err"][:60]), "result": r}


def main(argv):
    import json
    if len(argv) < 2:
        print(json.dumps({"usage": "omni_adapter.py <target> [verb]",
                          "examples": ["https://example.com get", "/etc/hostname read",
                                       "127.0.0.1:8791 probe", "settings launch",
                                       "python3 stat"]}, ensure_ascii=False, indent=1))
        return 2
    target = argv[1]
    verb = argv[2] if len(argv) > 2 else ""
    print(json.dumps({"classify": classify(target), "run": execute(target, verb)},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
