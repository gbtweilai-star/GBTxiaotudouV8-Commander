"""GBT小土豆V8 · 外部 CLI 智能体接入层（claude_code / codebuddy / ul_tars_desktop）。

## 为什么要有这个文件（不是"顺手加的"）

这 3 个名字**登记在 `BENIGN_CAPS` 里，却长期没有分派分支** ——
真调返回 `{"status": "ok", "result": None}`：**报成功，但什么都没干**。
比"没这个能力"更坏：调用方分不清「干了没输出」和「根本没干」。

哨兵闸 `tools/codex-scripts/caps-registry-guard.py` 的 ⑥（登记 vs 接线）一直在点它们的名：
    🔴 3 位在整个 api.py 里一次都没出现：claude_code、codebuddy、ul_tars_desktop

`api.py` 末尾那条兜底 return（2026-09-25 加的）把**隐式 None** 改成了如实的
`status: not_wired` —— 那是止血。本模块是**接通**：探测 → 真调 → 不在就如实报缺哪个。

## 口径

- **探测**走 `shutil.which`（真查 PATH，不猜）；**版本**走 `--version` 真跑一次。
- **真调**走 `subprocess`，超时可设，stdout/stderr 全带回，**不吞错**。
- **不在就如实说不在**：`needs_dependency` + 缺哪个可执行文件 + 怎么装。
  ⚠️ 这是**有真调用的**缺件报告（`shutil.which` 真跑过），不是"空话分支"——
  哨兵闸的 ⑦ 专抓"只回一句未实现"的假实现，本模块每一位都先真探再答。
- **落审计**：真调外部智能体 = `process_execute` + `external_llm`，由 policy 管，本模块不管门。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time

# 每位：可执行文件名候选 → 安装提示。探测顺序即优先级。
_AGENTS = {
    "claude_code": {
        "bins": ["claude", "claude.cmd", "claude.ps1"],
        "label": "Claude Code（Anthropic 官方 CLI）",
        "install": "npm i -g @anthropic-ai/claude-code",
        "prompt_flag": "-p",
    },
    "codebuddy": {
        "bins": ["codebuddy", "codebuddy.exe", "codebuddy.cmd"],
        "label": "CodeBuddy CLI",
        "install": "见 CodeBuddy 官方安装页（本机曾在 %LOCALAPPDATA%\\codebuddy\\bin）",
        "prompt_flag": "-p",
    },
    "ul_tars_desktop": {
        "bins": ["tars", "ul-tars", "ui-tars", "UITARS"],
        "label": "UI-TARS Desktop（桌面 GUI 智能体）",
        "install": "UI-TARS Desktop 是**图形应用**，不是 CLI —— 装完把它的可执行目录加进 PATH，"
                   "或用 op=exe 直接给绝对路径",
        "prompt_flag": "",
    },
}


def _probe(kind: str) -> dict:
    """真探：这个 CLI 到底在不在本机。**返回的是探测结果，不是猜测。**"""
    spec = _AGENTS[kind]
    found = []
    for b in spec["bins"]:
        p = shutil.which(b)
        if p:
            found.append({"name": b, "path": p})
    return {"kind": kind, "label": spec["label"], "found": found,
            "available": bool(found), "searched": spec["bins"],
            "install_hint": spec["install"]}



# ── 只读查最新发布版（npm registry）────────────────────────────────────────────
# 🔴 2026-10-09 修：`cli_chat.agents()` 一直在调 `ca._latest(kind)`，而本模块**从来没有这个函数**
#    ⇒ `cap cli_chat` 整条崩（AttributeError: module 'gbt_allinone.cli_agents' has no attribute '_latest'）。
#    这是**接线断了一头**，不是「要参数」。现在把这一头补上：真去只读查，查不到就如实说查不到。
_NPM_PKG = {
    "claude_code": "@anthropic-ai/claude-code",
    "codebuddy": "",            # 本仓没登记它的 npm 包名 ⇒ 不编，如实说查不到
    "ul_tars_desktop": "",      # 图形应用，不是 npm 包
}


def _npm_pkg(kind: str) -> str:
    """包名从登记表现推（install 提示里写了 `npm i -g <pkg>` 才能推出来）。"""
    import re
    pk = _NPM_PKG.get(kind)
    if pk:
        return pk
    inst = str((_AGENTS.get(kind) or {}).get("install") or "")
    m = re.search(r"npm\s+i(?:nstall)?\s+-g\s+([@\w./-]+)", inst)
    return m.group(1) if m else ""


def _latest(kind: str, timeout: int = 8) -> dict:
    """只读查最新发布版（过 security/net_guard 的出网边界）。**查不到就说查不到，绝不编。**"""
    pkg = _npm_pkg(kind)
    if not pkg:
        return {"ok": False, "kind": kind,
                "reason": "这一位没登记 npm 包名（或不是 npm 包），本机无法只读查 latest"}
    url = "https://registry.npmjs.org/%s/latest" % pkg
    try:
        from .security import net_guard as _ng
        r = _ng.safe_request_json(url, timeout=timeout)
        js = r.get("json") or {}
        v = str(js.get("version") or "")
        if int(r.get("status") or 0) == 200 and v:
            return {"ok": True, "kind": kind, "pkg": pkg, "latest": v}
        return {"ok": False, "kind": kind, "pkg": pkg, "reason": "npm 回 %s" % r.get("status")}
    except Exception as exc:                                       # noqa: BLE001
        return {"ok": False, "kind": kind, "pkg": pkg,
                "reason": ("%s: %s" % (type(exc).__name__, exc))[:140]}


def _version(exe: str, timeout: int = 20) -> dict:
    """真跑一次 --version。跑不起来也如实返回，不吞。"""
    for flag in ("--version", "-v", "version"):
        try:
            cp = subprocess.run([exe, flag], capture_output=True, timeout=timeout,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception as exc:                                # noqa: BLE001
            return {"ok": False, "flag": flag, "error": f"{type(exc).__name__}: {exc}"}
        out = ((cp.stdout or b"") + (cp.stderr or b"")).decode("utf-8", "replace").strip()
        if out:
            return {"ok": True, "flag": flag, "exit": cp.returncode, "output": out[:400]}
    return {"ok": False, "error": "三个版本旗标都没有输出"}


def run(kind: str, payload: dict) -> dict:
    """统一入口。op = status（只探）| version（真跑版本）| exec（真调）。"""
    if kind not in _AGENTS:
        return {"ok": False, "error": f"未知 CLI 智能体:{kind}", "known": sorted(_AGENTS)}
    p = dict(payload or {})
    op = str(p.get("op") or p.get("action") or "status").lower()
    spec = _AGENTS[kind]

    probe = _probe(kind)
    if op in ("status", "list", "probe"):
        return {"ok": True, "op": "status", "kind": kind, "dimension": "llm",
                **probe,
                "口径": "真查 PATH（shutil.which），不是读配置猜的"}

    if not probe["available"]:
        # 走到这里说明**真的探过了**，只是没探到 —— 如实报缺，并给出装法。
        return {"ok": False, "status": "needs_dependency", "kind": kind,
                "error_class": "needs_dependency",
                "missing": f"{spec['label']} 的可执行文件（找过：{'、'.join(probe['searched'])}）",
                "install_hint": spec["install"],
                "probe": probe,
                "读法": ("**不是「坏了」，也不是「被门拒」** —— 是本机没装这个 CLI。"
                         "装完再调即可；`op=exe` 也能直接给绝对路径绕过 PATH。"),
                "口径": "先真探再答；没探到才说没有"}

    exe = p.get("exe") or probe["found"][0]["path"]

    if op in ("version", "ver"):
        return {"ok": True, "op": "version", "kind": kind, "exe": exe,
                "version": _version(exe, int(p.get("timeout", 20))),
                "probe": probe}

    if op in ("exec", "run", "chat", "ask"):
        prompt = str(p.get("prompt") or p.get("q") or "")
        if not prompt:
            return {"ok": False, "error": "缺少 prompt", "kind": kind,
                    "hint": 'op=exec 要给 prompt；只想看装没装用 op=status'}
        argv = [exe] + ([spec["prompt_flag"]] if spec["prompt_flag"] else []) + [prompt]
        timeout = int(p.get("timeout", 300))
        t0 = time.time()
        try:
            cp = subprocess.run(argv, capture_output=True, timeout=timeout,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                cwd=p.get("cwd") or None)
        except subprocess.TimeoutExpired:
            return {"ok": False, "status": "timeout", "kind": kind, "exe": exe,
                    "timeout": timeout, "prompt_len": len(prompt),
                    "error": f"外部智能体 {timeout}s 未返回"}
        except Exception as exc:                                # noqa: BLE001
            return {"ok": False, "kind": kind, "exe": exe,
                    "error": f"{type(exc).__name__}: {exc}"}
        out = (cp.stdout or b"").decode("utf-8", "replace")
        err = (cp.stderr or b"").decode("utf-8", "replace")
        return {"ok": cp.returncode == 0, "op": "exec", "kind": kind, "exe": exe,
                "exit": cp.returncode, "ms": round((time.time() - t0) * 1000, 1),
                "stdout": out[-8000:], "stderr": err[-2000:],
                "口径": "真跑外部进程；stdout/stderr 原样带回，不吞错"}

    return {"ok": False, "error": f"未知 op:{op}",
            "known": ["status", "version", "exec"], "kind": kind}


def claude_code(payload: dict | None = None) -> dict:
    return run("claude_code", payload or {})


def codebuddy(payload: dict | None = None) -> dict:
    return run("codebuddy", payload or {})


def ul_tars_desktop(payload: dict | None = None) -> dict:
    return run("ul_tars_desktop", payload or {})


def probe_all() -> dict:
    """只读：三个 CLI 各自的探测结果（给面板/体检用）。"""
    rows = {k: _probe(k) for k in _AGENTS}
    return {"ok": True, "dimension": "llm", "agents": rows,
            "available": sorted(k for k, v in rows.items() if v["available"]),
            "missing": sorted(k for k, v in rows.items() if not v["available"]),
            "口径": "真查 PATH；不是读配置"}


if __name__ == "__main__":
    print(json.dumps(probe_all(), ensure_ascii=False, indent=2))
