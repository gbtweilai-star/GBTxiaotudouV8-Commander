# gbt-capability: freebuff_term
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""freebuff 终端集成（主人令 2026-09-28：「把 `freebuff` 这个终端给我集成进我们的对话面板，编程就走这个」）。

## 一手读数（2026-09-28 现跑，不是二手描述）
| 项 | 读数 |
|---|---|
| 入口 | `%APPDATA%\\npm\\freebuff.cmd`（npm 壳）|
| **正常 HOME 下** | ❌ `EPERM: mkdir C:\\Users\\ADMIN\\.config\\manicode` —— 它只往 `$HOME/.config/manicode` 装 |
| **隔离 HOME 下** | ✅ 装成（下载 45.8MB → `freebuff.exe` 121MB + `tree-sitter.wasm`）· `-v` = **0.1.2** |
| 稳定隔离 HOME | `%LOCALAPPDATA%\\gbt-freebuff\\home`（临时目录会被清；放仓库里会污染 git） |
| 身份/模型 | `settings.json`：`mode=DEFAULT` · `freebuffModelDefaultMigration=glm-5.3-flash-2026-09-05` · `adsEnabled=true`（免费档带广告）|
| 登录态 | **尚无凭证文件** ⇒ 要真干活得主人跑一次 `freebuff login`（**只有主人能登**）|
| 能力面 | `freebuff`（无参=TUI 会话）· `login` · `--continue [id]` · `--cwd <dir>` · `--trust-agents` · `-v` · `-h` |

## 🔴 一条决定性事实（决定面板能做多深）
**它是交互式 TUI，`--help` 里没有一次性 prompt 参数**（没有 `-p` / `--prompt` / `exec`）。
⇒ **网页里"点一下就让 freebuff 干活"是做不到的**（静态页不能起进程，它也没有非交互入口）。
所以本件把"集成进对话面板"落成三件**能做到**的事：
1. **状态面**（面板上看得到真身/版本/隔离 HOME/登录态/能力面）；
2. **`launch`**：用隔离 HOME 起一个**真终端**跑 freebuff（`cmd /k` + `--cwd <仓库>`），过 `process_execute` 门；
3. **登录指引**（`login_hint`）：给主人**在隔离 HOME 下**跑 login 的准确命令。
**升级路径**（面板里真对话）：要一个**本地 PTY 桥**（常驻进程 + WebSocket），需 `process_execute` 授权 + 主人点头 —— 如实标为下一步，不假装已有。

op=status / flags / launch / login_hint / verify / where
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_STATE = _ROOT / "state"
_LEDGER = _STATE / "freebuff_term.jsonl"
# 稳定隔离 HOME（**仓外**：121MB 二进制不进 git；%LOCALAPPDATA% 对本用户可写）
_HOME = Path(os.path.expandvars(r"%LOCALAPPDATA%\gbt-freebuff\home"))
_CMD = _ROOT / "freebuff-start.cmd"
# ⚠️ 血账（2026-09-28）：启动脚本原先写在隔离 HOME 里，而脚本内容要带仓库**绝对路径**
#    （仓库名含中文）⇒ 写盘时 `script.encode("ascii")` **当场抛 UnicodeEncodeError**，launch 直接崩。
#    ⇒ 脚本改放**仓库根**，用 `%~dp0` 自定位（文件里只有纯 ASCII），`--cwd` 也就不需要了。
EXE_REL = Path(".config") / "manicode" / "freebuff.exe"


def _log(row: dict) -> None:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row}, ensure_ascii=False) + "\n")


def _meta_version() -> str:
    """它自己的元数据文件里有没有版本号（便宜的真读；读不到返回空）。"""
    p = _HOME / ".config" / "manicode" / "freebuff-metadata.json"
    if not p.is_file():
        return ""
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    for k in ("version", "cliVersion", "currentVersion"):
        v = str(d.get(k) or "").strip()
        if re.match(r"^\d+\.\d+", v):
            return v
    return ""


def _env() -> dict:
    """隔离环境（三条都设：freebuff 只认 $HOME/.config/manicode）。"""
    return {**os.environ, "HOME": str(_HOME), "USERPROFILE": str(_HOME),
            "XDG_CONFIG_HOME": str(_HOME / ".config")}


def _settings() -> dict:
    p = _HOME / ".config" / "manicode" / "settings.json"
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _entry() -> str:
    """freebuff 的真身入口。

    ⚠️ 血账（2026-09-28）：`subprocess.run(["freebuff", ...])` 在 Python 里报
    `FileNotFoundError` —— 因为它是个 **`.cmd` 壳**（`%APPDATA%\\npm\\freebuff.cmd`），
    Python 无 shell 时不解析 PATHEXT；bash 能跑是因为 bash 认。⇒ 这里用 `shutil.which`
    解析出真身，`.cmd/.bat` 一律经 `cmd /c` 调用（程序名字面量，参数才是变量）。
    """
    from shutil import which
    for name in ("freebuff", "freebuff.cmd"):
        p = which(name)
        if p:
            return p
    cand = Path(os.path.expandvars(r"%APPDATA%\npm\freebuff.cmd"))
    return str(cand) if cand.is_file() else ""


def _invoke(args: list, timeout: int = 120) -> dict:
    """真跑一次 freebuff（隔离 HOME）。`.cmd` 走 cmd /c；程序名一律字面量。"""
    ent = _entry()
    if not ent:
        return {"ok": False, "error": "PATH 里找不到 freebuff（npm 全局装了吗）"}
    argv = (["cmd", "/c", ent] if ent.lower().endswith((".cmd", ".bat")) else [ent]) + list(args)
    try:
        cp = subprocess.run(argv, capture_output=True, timeout=timeout, env=_env(),
                            text=True, encoding="utf-8", errors="replace",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {"ok": True, "exit": cp.returncode,
                "text": (cp.stdout or "") + (cp.stderr or ""), "entry": ent}
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:120]}", "entry": ent}


def _version(timeout: int = 120) -> dict:
    """真跑一次 `-v`（隔离 HOME 下）。首次会下载 45.8MB，所以超时给足。"""
    r = _invoke(["-v"], timeout=timeout)
    if not r.get("ok"):
        return r
    lines = [ln.strip() for ln in r["text"].strip().splitlines() if ln.strip()]
    ver = next((ln for ln in reversed(lines) if re.match(r"^\d+\.\d+", ln)), "")
    return {"ok": bool(ver), "version": ver, "exit": r["exit"], "entry": r["entry"],
            "tail": lines[-2:]}


def status(**_kw) -> dict:
    exe = _HOME / EXE_REL
    auth_files = []
    md = _HOME / ".config" / "manicode"
    if md.is_dir():
        auth_files = [p.name for p in md.iterdir()
                      if any(k in p.name.lower() for k in ("token", "auth", "session", "credential"))]
    st = _settings()
    exe_mb = round(exe.stat().st_size / 1048576, 1) if exe.is_file() else 0
    # ⚠️ 版本**真读**（不许写死成常量 —— 那是"匿名数字"）：先看它自己的元数据文件，
    #    读不到再真跑一次 `-v`（慢但真）。
    ver, ver_src = _meta_version(), "metadata"
    if not ver:
        ver, ver_src = (_version().get("version") or ""), "run:-v"
    return {"ok": True, "op": "status", "name": "freebuff", "version": ver or "未知",
            "script": str(_CMD), "script_exists": _CMD.is_file(),
            "version_source": ver_src,
            "home": str(_HOME), "home_exists": _HOME.is_dir(),
            "exe": str(exe), "exe_exists": exe.is_file(), "exe_mb": exe_mb,
            "settings": {"mode": st.get("mode"), "model": st.get("freebuffModelDefaultMigration"),
                         "ads_enabled": st.get("adsEnabled")},
            "logged_in": bool(auth_files), "auth_files": auth_files,
            "installable_here": exe.is_file(),
            "why_not_normal_home": ("正常 HOME 下 EPERM（它只往 $HOME/.config/manicode 装，"
                                    "而那目录建不出来）⇒ 必须给隔离 HOME"),
            "can_be_driven_one_shot": False,
            "note": ("**TUI-only**：没有一次性 prompt 参数 ⇒ 页面里点不动它，要真用必须开终端。"
                     "登录（`freebuff login`）只有主人能做。"),
            "_口径": "真身/版本=现读；在不在=真看盘；登录态=看凭证文件；**能非交互驱动=否**（现读 --help 得）"}


def flags(**_kw) -> dict:
    """现读它的能力面（`--help` 原文），并**把"没有一次性 prompt"钉成结论**。"""
    r = _invoke(["--help"], timeout=150)
    if not r.get("ok"):
        return r
    txt = r["text"]
    # 🔴 2026-10-04 修（24h 审查实证）：原实现无条件回 ok=True —— `_invoke.ok` 只表示
    #    "子进程跑起来了"，不表示"命令成功了"。实测 `freebuff --help` 失败时（wrapper 里
    #    node 不在 PATH ⇒ 输出"…不是内部或外部命令…"）错误文本被当能力面内联进面板，
    #    页面上仍显示 ok=true / options=[]（假绿）。现在：exit≠0 或输出不像帮助 ⇒ 如实回失败。
    looks_like_help = bool(re.search(r"Usage:|Options:|Commands:", txt))
    if r.get("exit") not in (0, None) or not looks_like_help:
        return {"ok": False, "op": "flags", "exit": r.get("exit"), "entry": r.get("entry"),
                "error": f"`freebuff --help` 没有给出正常帮助输出（exit={r.get('exit')}）",
                "help_excerpt": txt.strip().splitlines()[:6],
                "_口径": "现跑 `freebuff --help` 解析；失败如实回 ok=false（不许把错误文本当能力面）"}
    opts = sorted(set(re.findall(r"(-\w,?\s*--[a-z-]+|--[a-z-]+|-\w)\b", txt)))
    one_shot = bool(re.search(r"(--prompt|\s-p\b|--print|\bexec\b)", txt))
    return {"ok": True, "op": "flags", "options": opts,
            "subcommands": ["login"],
            "entry": r.get("entry"),
            "has_one_shot_prompt": one_shot,
            "verdict": ("**TUI-only**（无一次性 prompt）⇒ 面板不能直接驱动它"
                        if not one_shot else "发现了一次性入口（可改做面板直驱）"),
            "help_excerpt": txt.strip().splitlines()[:14],
            "_口径": "现跑 `freebuff --help` 解析，不抄记忆"}


def launch(dry_run: bool = False, **_kw) -> dict:
    """用隔离 HOME 起**真终端**跑 freebuff（`cmd /k`，工作目录=仓库）。**过 `process_execute` 门**。"""
    exe = _HOME / EXE_REL
    if not exe.is_file():
        return {"ok": False, "op": "launch", "fail_closed": True,
                "error": f"隔离 HOME 里没有 freebuff.exe：{exe}", "how_to_fix": "先跑一次 status（会自动下载 45.8MB）"}
    # ① 生成启动脚本（**CRLF + 纯 ASCII**：LF 会被 cmd.exe 拆错行、中文注释会被当命令执行）
    lines = ["@echo off",
             "chcp 65001 >nul 2>&1",
             "rem run freebuff with the isolated HOME; ASCII-only on purpose",
             'set "HOME=%s"' % _HOME,
             'set "USERPROFILE=%s"' % _HOME,
             'set "XDG_CONFIG_HOME=%s\\.config"' % _HOME,
             'cd /d "%~dp0"',
             "freebuff %*"]
    script = "\r\n".join(lines) + "\r\n"
    if dry_run:
        return {"ok": True, "op": "launch", "dry_run": True, "script_preview": script,
                "note": "没起进程；真起要 process_execute 门"}
    try:
        from .. import auth_gate
        from ..security import policy as _policy
    except ImportError:
        sys.path.insert(0, str(_ROOT))
        import gbt_allinone as _g                            # noqa: F401
        from gbt_allinone import auth_gate                   # type: ignore
        from gbt_allinone.security import policy as _policy  # type: ignore
    if not _policy.is_trusted():
        gate = auth_gate.check_and_consume("process_execute", detail="freebuff_term launch")
        if not gate.get("ok"):
            return {"ok": False, "op": "launch", "denied": True, "fail_closed": True,
                    "error": gate.get("error"), "how_to_grant": gate.get("how_to_grant"),
                    "note": "起终端 = 启动进程 ⇒ 这是要授权的事"}
    _CMD.write_bytes(script.encode("ascii"))
    try:
        os.startfile(str(_CMD))                                # noqa: S606
    except OSError as exc:
        return {"ok": False, "op": "launch", "error": f"{type(exc).__name__}: {exc}"}
    _log({"event": "launch", "cmd": str(_CMD), "home": str(_HOME)})
    return {"ok": True, "op": "launch", "cmd": str(_CMD), "home": str(_HOME),
            "note": "已起终端（隔离 HOME + 仓库为工作目录）；首次要在那个窗口里跑 `freebuff login`"}


def login_hint(**_kw) -> dict:
    """给主人**在隔离 HOME 下**登录的准确命令（登录只有主人能做）。"""
    return {"ok": True, "op": "login_hint",
            "why_isolated": ("它只往 `$HOME/.config/manicode` 装，而你的正常 HOME 下建那个目录会 EPERM "
                            "⇒ 必须在隔离 HOME 里装/登，才起得来"),
            "powershell": [
                '$h = "$env:LOCALAPPDATA\\gbt-freebuff\\home"',
                '$env:HOME=$h; $env:USERPROFILE=$h; $env:XDG_CONFIG_HOME="$h\\.config"',
                'freebuff login',
            ],
            "or_double_click": str(_CMD) + "   （先起终端，再在里面敲 freebuff login）",
            "after_login": "回来跑 run_task('freebuff_term', {'op':'status'}) ⇒ logged_in 应变 True",
            "ai_cannot": "**登录/注册只有主人能做**（不代持账号、不批量注册）"}


def verify(**_kw) -> dict:
    problems = []
    exe = _HOME / EXE_REL
    if not exe.is_file():
        problems.append(f"隔离 HOME 里没有 freebuff.exe（{exe}）⇒ 先 status 触发一次下载")
    if not _SETTINGS_OK():
        problems.append("settings.json 读不动 ⇒ 隔离 HOME 可能半成品")
    f = flags()
    if f.get("ok") and f.get("has_one_shot_prompt"):
        problems.append("发现了一次性 prompt 入口 —— 那么'面板不能直驱'这条结论要重写")
    # 启动脚本必须 CRLF + ASCII（血账）
    if _CMD.is_file():
        raw = _CMD.read_bytes()
        if b"\r\n" not in raw:
            problems.append("启动脚本不是 CRLF ⇒ cmd.exe 会拆错行（血账）")
        try:
            raw.decode("ascii")
        except UnicodeDecodeError:
            problems.append("启动脚本含非 ASCII ⇒ GBK 控制台会当命令执行（血账）")
    return {"ok": not problems, "op": "verify", "problems": problems,
            "home": str(_HOME), "exe_exists": exe.is_file(),
            "_口径": "隔离 HOME 有二进制 · settings 可读 · 'TUI-only' 结论仍成立 · 启动脚本 CRLF+ASCII"}


def _SETTINGS_OK() -> bool:
    p = _HOME / ".config" / "manicode" / "settings.json"
    if not p.is_file():
        return False
    try:
        json.loads(p.read_text(encoding="utf-8"))
        return True
    except json.JSONDecodeError:
        return False


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "freebuff_term", "tentacle": "freebuff_term",
            "entry": "run_task('freebuff_term', {...})",
            "ops": ["status", "flags", "launch", "login_hint", "verify", "where"],
            "home": str(_HOME), "version": _meta_version() or "未知",
            "hard_facts": ["正常 HOME 下 EPERM（只认 $HOME/.config/manicode）",
                           "隔离 HOME 下装成并验活（-v = 0.1.2）",
                           "**TUI-only：没有一次性 prompt ⇒ 面板不能直接驱动**",
                           "登录只有主人能做（不代持账号）"],
            "gates": {"launch": "process_execute"},
            "next_step_for_panel_chat": ("要在面板里真对话 ⇒ 需本地 PTY 桥（常驻进程 + WebSocket），"
                                        "要 process_execute 授权 + 主人点头；**现在没有**，不假装有")}


def script_write(**_kw) -> dict:
    """把启动脚本**写出来**（`freebuff-start.cmd`，CRLF + 纯 ASCII）。

    为什么与 `launch` 分开：**写脚本不起进程**（它是生成物，与 `state/` 那些同类）⇒ 不需要票；
    真正要 `process_execute` 的是"起终端"那一下。分开之后主人可以**先双击脚本用**，不必等我拿票。
    """
    lines = ["@echo off",
             "chcp 65001 >nul 2>&1",
             "rem run freebuff with the isolated HOME; ASCII-only on purpose",
             'set "HOME=%s"' % _HOME,
             'set "USERPROFILE=%s"' % _HOME,
             'set "XDG_CONFIG_HOME=%s\\.config"' % _HOME,
             'cd /d "%~dp0"',
             "freebuff %*"]
    script = "\r\n".join(lines) + "\r\n"
    _CMD.write_bytes(script.encode("ascii"))
    _log({"event": "script_write", "cmd": str(_CMD), "bytes": _CMD.stat().st_size})
    return {"ok": True, "op": "script_write", "cmd": str(_CMD), "bytes": _CMD.stat().st_size,
            "note": "双击它即可用隔离 HOME 起 freebuff；首次在里面跑 `freebuff login`"}


def run_op(op: str = "status", **params) -> dict:
    op = (op or "status").lower()
    for name, fn in (("status", status), ("flags", flags), ("launch", launch),
                     ("script_write", script_write),
                     ("login_hint", login_hint), ("verify", verify), ("where", where)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（status/flags/launch/script_write/login_hint/verify/where）"}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="freebuff 终端集成（隔离 HOME）")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "flags", "launch", "login_hint", "verify", "where"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                                          # noqa: BLE001
        pass
    print(json.dumps(run_op(a.cmd, dry_run=a.dry_run), ensure_ascii=False, indent=1))  # noqa: T201
    raise SystemExit(0)
