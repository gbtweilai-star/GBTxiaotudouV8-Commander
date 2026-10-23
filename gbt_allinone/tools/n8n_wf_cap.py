# gbt-capability: n8n_wf
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""n8n 工作流控制（我们自己的 n8n · 2026-09-26 主人令「原生部署自己说了算」）。

双向中的**框架 → n8n** 这一向：
  status   n8n 实例健康（HTTP 5678 + 版本 + 工作流清单）
  list     工作流清单（n8n list:workflow）
  export   全量导出（--output 到指定路径）
  import   导入工作流文件（过 filesystem_write 门）
  active   启用/停用工作流（过门）
  hook     POST 调 webhook（如 /webhook/gbt），触发 n8n 里的工作流

边界：
  · 一切 HTTP 走 _safe_request 单点出口（net_guard 校验在先，本地回环属本能力位
    的目标域，显式 allow_private 并在注释中声明理由）；
  · import/export/active/hook 过 filesystem_write 门（改盘或触发外部执行）。
"""
from __future__ import annotations

import json
import shutil
import subprocess

_URL = "http://127.0.0.1:5678"
_MAX_OUT = 4000


def _cli() -> str | None:
    return shutil.which("n8n")


def _safe_request(url: str, method: str = "GET", payload: dict | None = None) -> dict:
    """本能力位唯一的 HTTP 出口：net_guard 校验 → curl 子进程（对本地服务稳）。

    allow_private=True 的理由：本能力位的**设计目标**就是本机 n8n（127.0.0.1:5678），
    回环地址是它的正门而非越界；其余一切仍受 net_guard 协议/端口/地址规则约束。
    """
    from ..security import net_guard
    net_guard.validate_url(str(url), allow_private=True)
    cmd = ["curl", "-s", "-m", "20", "-w", "\n__HTTP__%{http_code}", str(url)]
    if method == "POST":
        cmd += ["-X", "POST", "-H", "Content-Type: application/json",
                "-d", json.dumps(payload or {}, ensure_ascii=False)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=40)
        out = (p.stdout or "")
        code = None
        if "__HTTP__" in out:
            out, _, tail = out.rpartition("__HTTP__")
            try:
                code = int(tail.strip())
            except Exception:                                  # noqa: BLE001
                pass
        return {"ok": p.returncode == 0 and code not in (None, 0) and code < 400,
                "status": code, "text": out.strip()[:1500],
                "error": None if p.returncode == 0 else (p.stderr or "")[:160]}
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}


def _gate(what: str) -> dict | None:
    from .. import auth_gate
    from ..security import policy as _policy
    if _policy.is_trusted():
        return None
    g = auth_gate.check_and_consume("filesystem_write", detail=f"n8n:{what}"[:60])
    if g.get("ok"):
        return None
    return {"ok": False, "denied": True, "gate": "filesystem_write",
            "error": g.get("error"), "how_to_grant": g.get("how_to_grant")}


def _run(args: list, timeout: int = 180) -> dict:
    cli = _cli()
    if not cli:
        return {"ok": False, "error": "n8n CLI 不在 PATH（npm i -g n8n）"}
    try:
        p = subprocess.run([cli] + args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return {"ok": p.returncode == 0, "exit": p.returncode,
                "out": ((p.stdout or "") + (p.stderr or "")).strip()[-_MAX_OUT:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"n8n 超时（>{timeout}s）"}
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}


def status(**_kw) -> dict:
    probe = _safe_request(_URL + "/healthz")
    out = {"ok": bool(probe.get("ok")) and probe.get("status") == 200,
           "kind": "n8n_wf", "url": _URL, "http": probe.get("status"),
           "note": "我们自己的自托管 n8n（数据在 ~/.n8n）；管理脚本 tools/n8n-ctl.bat"}
    if probe.get("status") != 200:
        root = _safe_request(_URL + "/")
        out["http"] = root.get("status")
        out["ok"] = root.get("status") == 200
        probe = root
    if out["ok"]:
        v = _run(["list:workflow"], timeout=90)
        out["workflows"] = v.get("out", "")[:600]
    else:
        out["error"] = probe.get("error") or f"HTTP {probe.get('status')}"
    return out


def run(op: str = "status", **p) -> dict:
    op = (op or "status").lower()
    if op == "status":
        return status(**p)
    if op == "list":
        return _run(["list:workflow"], timeout=120)
    if op == "export":
        deny = _gate("export")
        if deny:
            return deny
        return _run(["export:workflow", "--all",
                     "--output=" + str(p.get("output") or "config/n8n-export.json")], timeout=180)
    if op == "import":
        deny = _gate("import")
        if deny:
            return deny
        f = p.get("file")
        if not f:
            return {"ok": False, "error": "需 file=工作流 json 路径"}
        return _run(["import:workflow", "--input=" + str(f)], timeout=180)
    if op == "active":
        deny = _gate("active")
        if deny:
            return deny
        wid = p.get("id")
        if not wid:
            return {"ok": False, "error": "需 id=工作流 id"}
        on = str(p.get("on", "true")).lower() == "true"
        return _run(["update:workflow", f"--id={wid}", f"--active={'true' if on else 'false'}"], timeout=120)
    if op == "hook":
        deny = _gate("hook")
        if deny:
            return deny
        path = str(p.get("path") or "/webhook/gbt")
        url = _URL + (path if path.startswith("/") else "/" + path)
        return _safe_request(url, method="POST", payload=p.get("payload") or {})
    return {"ok": False, "error": f"未知 op:{op}（status/list/export/import/active/hook）",
            "fail_closed": True}
