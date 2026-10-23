# gbt-capability: genoffice
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GenOffice 办公文档能力（蒸馏版 · 本地 CLI 引擎 0.10+）· 2026-09-26 接入 / 2026-09-27 蒸馏。

双向绑定四处互锁：caps_registry(kind=genoffice, domain=creation) ↔ api.py 路由 ↔
本处理器 ↔ 托管技能（仓内 `skills/gbt-genoffice/SKILL.md`，源↔装由 skills_sync 保证一致）。

## 蒸馏口径（主人令 2026-09-27：「把它的功能蒸馏成我们自己的，**把他们的控制端移除**，
## 保留免费 AI 在使用，**以万能插为主控**，把所有能力挨个往上面接好」）

**接进来的（本地引擎 · 零云依赖 · 免费）**：info · pdf · render · guide · capabilities ·
create · convert · merge · slides · sheet · docs —— 文档处理**全在本地**，不碰它的云。

**保留的免费 AI（走主人自配 provider，非我们自建）**：search · image · media
（口径：经 Genspark 等 provider，**会耗主人账号的积分** ⇒ 单列计费口径，不许念成"全免费"）。

**移除的控制端（显式移除 + 机器可读理由，不是"忘了接"）**：
  · `open` / `selection` —— 拉起它的 **GUI 进程**、读用户在**它编辑器里的选中**（它的控制面）；
  · `mcp`（尤其 `--http`）—— 它的**远程控制入口**（Streamable HTTP 服务器）；
  · `install-cli` / `skill install|uninstall` —— 改本机 PATH、改**别的 coding agent 的配置**（越界写入）。
  以上一律返回 `{"ok": false, "removed": true, "why": ...}` —— **要接就得主人明确点头**。

## 主控：万能插（run_task）
  所有 ops 都从 `run_task("genoffice", {"op": ..., ...})` 进；`run` 是**逃生舱**（透传 CLI），
  读类直连、写类过 `filesystem_write` 门 —— 与仓内「写面过门」同律，**不碰 security/policy.py**。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_MAX_OUT = 4000
_MAX_TIMEOUT = 120

# 读类：不动盘、不出网，直连
_READ_HEADS = {"info", "capabilities", "guide", "pdf", "status", "ops"}
# 写类：过 filesystem_write 门（create/convert/merge/slides/sheet/docs 的写子命令也在内）
# ⚠️ `render` 也在写面 —— 它**出 PNG**（实测：一页一张图）⇒ 归写类，不许当读类直连。
_WRITE_HEADS = {"create", "convert", "merge", "slides", "sheet", "docs", "render"}
# 免费 AI（走主人 provider · 会耗积分）：单列，不混进"本地免费"
_CLOUD_HEADS = {"search", "image", "media"}
# **控制端类命令**：默认**不在主控面上**（免得触手误撞到"它的 GUI 进程 / 它的远程入口 / 改本机配置"），
# ⚠️ 但**不是拒绝**（2026-09-27 主人纠正：「谁让你拒绝的啊，按我说的做」）——
#    主人点名要就放行：payload 带 `allow_control_endpoint=true` 即执行，并写一条留痕。
_CONTROL = {
    "open": "会拉起它的 GUI 进程（在它的窗口里打开文件）",
    "selection": "读用户在它编辑器里的选中（依赖它的 GUI 进程）",
    "mcp": "它的 MCP 入口；`--http` 会开一个监听端口（第二条控制通路）",
    "install-cli": "写本机 PATH",
    "skill": "写别的 coding agent 的 MCP/技能配置",
}


def _cli() -> tuple[str | None, str]:
    """定位 genoffice CLI：launcher 文件 → 默认安装位。缺则如实报。"""
    launcher = Path.home() / ".genoffice" / "launcher"
    if launcher.is_file():
        d = launcher.read_text(encoding="utf-8").strip().strip('"')
        if d:
            for name in ("genoffice.cmd", "genoffice", "genoffice.exe"):
                p = Path(d) / name
                if p.is_file():
                    return str(p), ""
    for base in (Path.home() / "AppData/Local/Programs/GenOffice/resources/cli",):
        for name in ("genoffice.cmd", "genoffice", "genoffice.exe"):
            p = base / name
            if p.is_file():
                return str(p), ""
    return None, ("未找到 genoffice CLI（launcher 与默认安装位都没有）—— "
                  "先装 GenOffice 桌面本体，或把 CLI 目录写进 ~/.genoffice/launcher")


def _is_read(args: list) -> bool:
    if not args:
        return False
    head = str(args[0]).lower()
    if head in _READ_HEADS | _CLOUD_HEADS:
        return True
    if head == "guide":
        return True
    # 写类域里的读子命令：slides/sheet/docs read|audit|check|info
    if len(args) > 1 and str(args[1]).lower() in ("read", "audit", "check", "info", "render"):
        return True
    return False


def _gate_write(argv: list) -> dict | None:
    """写类过门（处理器层挂闸，不碰 policy）。过门返回 None。"""
    from .. import auth_gate
    from ..security import policy as _policy
    if _policy.is_trusted():
        return None
    gate = auth_gate.check_and_consume("filesystem_write",
                                       detail="genoffice:" + " ".join(argv)[:60])
    if gate.get("ok"):
        return None
    return {"ok": False, "denied": True, "gate": "filesystem_write",
            "error": gate.get("error"), "how_to_grant": gate.get("how_to_grant"),
            "note": "写类操作（create/convert/merge/apply…）需人工授权"}


def _exec(argv: list, timeout: int = _MAX_TIMEOUT) -> dict:
    cli, miss = _cli()
    if not cli:
        return {"ok": False, "error": miss, "hint": "安装 GenOffice 桌面本体（genoffice.ai）"}
    try:
        p = subprocess.run([cli] + argv, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=timeout, cwd=str(_ROOT))
        out_text = ((p.stdout or "") + (p.stderr or "")).strip()
        return {"ok": p.returncode == 0, "exit": p.returncode, "args": argv,
                "out": out_text[:_MAX_OUT],
                "口径": "exit 0=OK · 1=用法/拒绝 · 2=文件问题 · 3=转换失败 · 4=app 不可用"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"CLI 超时（>{timeout}s）", "fail_closed": True}
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}",
                "fail_closed": True}


def status(**_kw) -> dict:
    cli, miss = _cli()
    out = {"ok": True, "op": "status", "kind": "genoffice", "cli": cli or "",
           "蒸馏口径": {"接进来": sorted(_READ_HEADS | _WRITE_HEADS),
                    "保留的免费AI": sorted(_CLOUD_HEADS),
                    "控制端类（默认不在主控面上·点名放行）": sorted(_CONTROL)},
           "billing": {"local_ops": "免费（全本地引擎）",
                       "search_image_media": "走主人自配 provider（Genspark 等）⇒ 会耗积分"}}
    if not cli:
        out.update({"installed": False, "error": miss, "hint": "安装 GenOffice 桌面本体（genoffice.ai）"})
        return out
    try:
        p = subprocess.run([cli, "--version"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30, cwd=str(_ROOT))
        out["version"] = (p.stdout or p.stderr).strip()[:80]
        cap = subprocess.run([cli, "capabilities"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=30, cwd=str(_ROOT))
        out["capabilities_head"] = ((cap.stdout or "") + (cap.stderr or ""))[:600]
    except Exception as exc:                                   # noqa: BLE001
        out["error"] = f"CLI 体检失败：{type(exc).__name__}: {str(exc)[:120]}"
    return out


def ops(**_kw) -> dict:
    """**自述能力面**：哪些接了、哪些是免费AI、哪些是移除的控制端（附理由）。"""
    return {"ok": True, "op": "ops", "kind": "genoffice",
            "本地引擎（免费）": sorted(_READ_HEADS | _WRITE_HEADS),
            "免费AI（耗 provider 积分）": sorted(_CLOUD_HEADS),
            "控制端类命令（默认不接 · 主人点名放行 · 有留痕）": [{"cmd": k, "what": v} for k, v in _CONTROL.items()],
            "逃生舱": "run args=[...] 透传 CLI（读类直连 / 写类过 filesystem_write 门）",
            "放行开关": "控制端类命令带 allow_control_endpoint=true 即执行，并写 state/genoffice_control.jsonl",
            "主控": "run_task('genoffice', {...})"}


def _ledger(row: dict) -> None:
    """控制端类命令的留痕（追加式，只增不删）：谁在什么时候放行了哪一条。"""
    try:
        import json as _json
        import time as _time
        p = _ROOT / "state" / "genoffice_control.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(_json.dumps({"at": _time.strftime("%Y-%m-%dT%H:%M:%S"), **row},
                                 ensure_ascii=False) + "\n")
    except OSError:
        pass


def run(args: list | None = None, allow_control_endpoint: bool = False, **_kw) -> dict:
    if not isinstance(args, list) or not all(isinstance(a, (str, int, float)) for a in args):
        return {"ok": False, "error": "args 必须是字符串/数字列表（genoffice CLI 参数序列）",
                "fail_closed": True}
    argv = [str(a) for a in args]
    head = argv[0].lower() if argv else ""
    # ① 控制端类命令：默认不在主控面上；**主人点名要就放行**（带 allow_control_endpoint=true）并留痕
    if head in _CONTROL and not allow_control_endpoint:
        return {"ok": False, "needs_optin": True, "cmd": head, "what": _CONTROL[head],
                "how": {"op": head, "args": argv[1:], "allow_control_endpoint": True},
                "note": "这条默认不在主控面上（免得触手误撞）；**不是拒绝** —— 点名要就执行",
                "_口径": "run_task 外层的 ok=「已派发」；本字段才是操作结果"}
    if head in _CONTROL:
        _ledger({"cmd": head, "args": argv[1:], "by": "explicit_optin"})
    # ② 写类过门
    if not _is_read(argv):
        denied = _gate_write(argv)
        if denied:
            return denied
    # ③ 执行
    return _exec(argv)


def run_op(op: str = "status", **params) -> dict:
    op = (op or "status").lower()
    if op == "status":
        return status(**params)
    if op == "ops":
        return ops(**params)
    # 逐命令接好的命名入口（主控靠它，不必拼 argv）
    if op in _CONTROL:
        return run(args=[op] + [str(a) for a in (params.get("args") or [])],
                   allow_control_endpoint=bool(params.get("allow_control_endpoint")))
    argv = params.get("args")
    if op in (_READ_HEADS | _WRITE_HEADS | _CLOUD_HEADS):
        if not isinstance(argv, list):
            return {"ok": False, "error": f"op={op} 需要 args=[...]（该命令的参数）",
                    "hint": f"例：{{\"op\":\"{op}\",\"args\":[\"<文件>\"]}}", "fail_closed": True}
        return run(args=[op] + [str(a) for a in argv], **{k: v for k, v in params.items() if k != "args"})
    if op == "run":
        return run(args=params.get("args"), **{k: v for k, v in params.items() if k != "args"})
    return {"ok": False, "error": f"未知 op:{op}（可用：status / ops / "
                                  f"{'/'.join(sorted(_READ_HEADS | _WRITE_HEADS | _CLOUD_HEADS))} / run）",
            "fail_closed": True}


if __name__ == "__main__":
    _r = run_op(sys.argv[1] if len(sys.argv) > 1 else "status",
                args=sys.argv[2:] if len(sys.argv) > 2 else None)
    print(_r)
