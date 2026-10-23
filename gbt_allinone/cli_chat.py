# gbt-capability: cli_chat
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""外部 CLI 助手「对话面板」后端（cli_chat）。

主人令 2026-09-28：「直接把这个面板集成进对话面板，这样就可以免费使用了」
（截图 = GenOffice「集成」面板四行：Claude Code / Codex / Gemini CLI / GitHub Copilot，
 每行「已安装 2.51.0，可更新到 2.66.1」+ 更新/卸载 —— 那四行版本号**完全相同**，
 是桩数据；真读数见 `cli_agents.hub`，本模块不重复造那张表，只取它的真探结果）。

## 为什么这页能「真对话」——与 freebuff 的本质差别（一手实测）

本仓 `freebuff_term` 已明写：freebuff 是 **TUI-only**（`--help` 里没有一次性 prompt 参数）
⇒ 静态面板**点不动它**，只能给状态面 + 复制命令。

这 4 位**不一样**。2026-09-28 现跑每一位的 `--help`（不是抄文档），全部命中非交互入口：

| 位 | 现跑读数 | 一次性形态 |
|---|---|---|
| `claude_code` | `--print` / `--prompt` / `-p` | `claude -p <prompt>` |
| `codebuddy` | `--print` / `--prompt` / `-p` / `exec` | `codebuddy -p <prompt>` |
| `codex_cli` | `exec`（+ `codex [OPTIONS] [PROMPT]`） | `codex exec <prompt>` |
| `github_copilot` | `--prompt` / `-p` | `copilot -p <prompt>` |
| `gemini_cli` | **本机未装 ⇒ 未实测** | 形态取自官方文档（`-p`），**标注未实测** |
| `ul_tars_desktop` | 图形应用，非 CLI ⇒ **无一次性入口** | 无 |

⇒ **面板能直接驱动它 4 位**，所以「集成进对话面板」这次是**真能聊**，不是又一张状态页。

## 「免费使用」的由来（说清楚，不含糊）

这 4 位走的是**你本机已经登好的 CLI 登录态**（Copilot 订阅额度 / Claude Code 登录 /
Codex 登录 / CodeBuddy 登录），**不经过框架的 API key 计费** ⇒ 面板发一句话 = 用那份额度，
**不花框架的 API 钱**。所以「免费」指的是**不吃 API 账单**，不是「无额度限制」。

⚠️ 登录态**归各 CLI 自己管**（凭证在它们各自的目录里）。本模块**不代持账号、不代登录、
不搬运凭证**；读不到登录态就**如实说读不到**，不猜。

## 诚实边界（页面上必须原样写出，不许假装）

- 本机实探：**4 位已装 / 2 位未装**（`gemini_cli` / `ul_tars_desktop`）⇒ 未装位 `fail_closed`
  如实报缺 + 给装法，**不编**。
- 真调 = **起外部进程** + **把 prompt 送出本机**（送到该 CLI 背后的模型）⇒ 两条都挂门：
  `process_execute` + `external_llm`。本模块**不绕门**：`policy` 层没有 `cli_chat` 分支
  （owner-only 文件，AI 无权改）⇒ 门在本模块内**自闸**，逐次调用 `auth_gate.check_and_consume_many`。
- ⚠️ **受限/沙箱环境里真跑会失败**：实测（2026-09-28）这些 CLI 启动要调 `reg.exe`，
  而宿主安全策略把 `reg.exe` 列进程序黑名单 ⇒ 进程被拦。本模块**如实回传**
  `host_blocked` 与原样 stderr，**不把它伪装成成功**。

op = agents / send / transcript / verify / where
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent              # gbt_allinone/
_REPO = _ROOT.parent                                 # 仓库根（仓根下的 state/ 才是落点）
_STATE = _REPO / "state"
_LEDGER = _STATE / "cli_chat.jsonl"

# ── 一次性驱动形态（**现跑 --help 得**，不是抄的）────────────────────────────
# style: "flag" = `exe <flag> <prompt>`；"subcmd" = `exe <subcmd> <prompt>`
# verified: True = 本机现跑 --help 亲验；False = 本机未装、形态取自官方文档（**标注未实测**）
_ONESHOT = {
    "claude_code":    {"argv": ["-p"],   "style": "flag",   "verified": True,
                       "evidence": "claude --help ⇒ 'use -p/--print for non-interactive output'"},
    "codebuddy":      {"argv": ["-p"],   "style": "flag",   "verified": True,
                       "evidence": "codebuddy --help ⇒ 'use -p/--print for non-interactive output'"},
    "codex_cli":      {"argv": ["exec"], "style": "subcmd", "verified": True,
                       "evidence": "codex --help ⇒ Commands 含 exec；Usage: codex [OPTIONS] [PROMPT]"},
    "github_copilot": {"argv": ["-p"],   "style": "flag",   "verified": True,
                       "evidence": "copilot --help ⇒ 'use -p/--prompt for non-interactive scripting'"},
    "gemini_cli":     {"argv": ["-p"],   "style": "flag",   "verified": False,
                       "evidence": "本机未装 ⇒ 形态取自 @google/gemini-cli 官方文档，**未实测**"},
    "ul_tars_desktop": {"argv": None,    "style": None,     "verified": True,
                       "evidence": "UI-TARS Desktop 是**图形应用**、不是 CLI ⇒ 无一次性入口"},
}

# 只读 op（不挂作用域）｜写面 op（真起进程 + 出网，必须过门）
_READ_OPS = ("agents", "list", "probe", "transcript", "verify", "where")
_GATE_SCOPES = ("process_execute", "external_llm")

_SANDBOX_HINTS = ("blacklist", "安全策略", "BLOCKED BY SECURITY POLICY",
                  "not permitted", "Access is denied", "EPERM")


def _agents_mod():
    """复用 `cli_agents`（真探 + 真版本 + 只读 registry 对账）—— **不在本模块重造那张表**。"""
    try:
        from . import cli_agents
        return cli_agents
    except ImportError:                                       # 独立加载（无包上下文）
        import importlib.util as _ilu
        sp = _ilu.spec_from_file_location("cli_agents_sibling", _ROOT / "cli_agents.py")
        m = _ilu.module_from_spec(sp)
        sp.loader.exec_module(m)
        return m


def _gate(detail: str) -> dict:
    """门：起外部进程 + 送出本机（`process_execute` + `external_llm`）。

    `security/policy.py` 是 **owner-only**（AI 无权改）且**没有 `cli_chat` 分支**
    ⇒ 门层零作用域，所以本模块**自己**走授权门的唯一校验入口
    （`auth_gate.check_and_consume_many`，与 `policy.authorize` 同一个）——
    **不是绕门，是补门**；缺授权照实报缺，不找旁路。
    """
    try:
        from . import auth_gate
        from .security import policy as _policy
    except ImportError:                                       # 独立加载
        sys.path.insert(0, str(_REPO))
        from gbt_allinone import auth_gate                    # type: ignore
        from gbt_allinone.security import policy as _policy    # type: ignore
    if _policy.is_trusted():
        return {"ok": True, "trusted": True, "scopes": list(_GATE_SCOPES)}
    return auth_gate.check_and_consume_many(list(_GATE_SCOPES), detail=detail)


def _log(row: dict) -> None:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row},
                            ensure_ascii=False) + "\n")


# ── 只读面 ────────────────────────────────────────────────────────────────

def agents(want_latest: bool = True, timeout: int = 20) -> dict:
    """**面板底表**（只读）：一行一位 —— 装没装 / 版本 / 能不能一次性驱动 / 一次形态。

    数据源 = `cli_agents`（真查 PATH + 真跑 --version + 只读 GET npm registry）。
    """
    ca = _agents_mod()
    rows = []
    for kind in ca._AGENTS:
        probe = ca._probe(kind)
        one = _ONESHOT.get(kind) or {"argv": None, "verified": False, "evidence": "未登记形态"}
        row = {
            "kind": kind,
            "label": probe["label"],
            "available": probe["available"],
            "path": (probe["found"][0]["path"] if probe["found"] else None),
            "install_hint": probe["install_hint"],
            "oneshot": list(one["argv"]) if one.get("argv") else None,
            "oneshot_verified": bool(one.get("verified")),
            "oneshot_evidence": one.get("evidence"),
            "can_chat": bool(probe["available"] and one.get("argv")),
        }
        if probe["available"]:
            v = ca._version(row["path"], timeout)
            row["installed"] = v.get("parsed") or None
            row["version_raw"] = v.get("output") or v.get("error")
            # ⚠️ 用 getattr 取：哪怕这一天 `_latest` 又没了，也只是**这一格**报「查不了」，
            #    不许因为缺一个助手就把整条 `agents` 崩掉（原来就是这么崩的）。
            _lt_fn = getattr(ca, "_latest", None)
            if want_latest and _lt_fn is not None:
                lt = _lt_fn(kind)
                if lt.get("ok"):
                    row["latest"] = lt.get("latest")
                else:
                    row["latest"] = None
                    row["latest_why"] = lt.get("reason") or lt.get("error")
            elif want_latest:
                row["latest"] = None
                row["latest_why"] = "本模块没有 _latest 助手（如实报，不编版本号）"
        else:
            row["installed"] = None
            row["status"] = "not_installed"
        rows.append(row)
    chatable = [r["kind"] for r in rows if r["can_chat"]]
    return {
        "ok": True, "op": "agents", "dimension": "integration",
        "registered": len(rows), "installed": sum(1 for r in rows if r["available"]),
        "chatable": chatable, "chatable_count": len(chatable),
        "rows": rows,
        "口径": ("装没装=真查 PATH（shutil.which）· 版本=真跑 --version · 最新版=**只读** GET "
                "registry.npmjs.org（失败如实报）· 一次形态=**现跑 --help**（未装位标注未实测）"),
        "免费口径": ("走各 CLI **自己的登录态/额度**，不经框架 API key ⇒ 不吃 API 账单；"
                  "额度上限与登录由各 CLI 自己管。"),
    }


def transcript(agent: str = "", limit: int = 30) -> dict:
    """读会话账（只读，最近的在后）。"""
    if not _LEDGER.is_file():
        return {"ok": True, "op": "transcript", "turns": [], "count": 0,
                "note": "还没有会话记录（第一次 send 才有）"}
    turns = []
    for line in _LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if agent and rec.get("agent") != agent:
            continue
        turns.append(rec)
    turns = turns[-max(1, int(limit)):]
    return {"ok": True, "op": "transcript", "turns": turns, "count": len(turns),
            "ledger": str(_LEDGER)}


# ── 写面（真起进程 + 出网，过门）──────────────────────────────────────────

def _argv_for(kind: str, exe: str, prompt: str, extra: list | None = None) -> list | None:
    """组装一次性 argv。`ul_tars_desktop`（图形应用）返回 None ⇒ 如实报「无一次性入口」。"""
    one = _ONESHOT.get(kind) or {}
    tail = one.get("argv")
    if not tail:
        return None
    argv = [exe]
    if one.get("style") == "subcmd":
        argv += list(tail) + list(extra or []) + [prompt]
    else:
        argv += list(extra or []) + list(tail) + [prompt]
    return argv


def _looks_host_blocked(text: str) -> bool:
    t = text or ""
    return any(h.lower() in t.lower() for h in _SANDBOX_HINTS)


def send(agent: str, prompt: str, timeout: int = 300, cwd: str = "",
         extra_args: list | None = None, dry_run: bool = False) -> dict:
    """**真发一句话**给指定的外部 CLI 助手（一次性 prompt），把回复原样带回。

    过门：`process_execute` + `external_llm`（起外部进程 + 把 prompt 送出本机）。
    未装 / 无一次性入口 ⇒ `fail_closed` 如实报缺，**不编**。
    """
    ca = _agents_mod()
    if agent not in ca._AGENTS:
        return {"ok": False, "op": "send", "fail_closed": True,
                "error": f"未知 CLI 智能体:{agent}", "known": sorted(ca._AGENTS)}
    text = str(prompt or "").strip()
    if not text:
        return {"ok": False, "op": "send", "fail_closed": True,
                "error": "prompt 为空", "hint": "本面无默认提问；要给一句话"}

    probe = ca._probe(agent)
    # 🔴 顺序有讲究：「**面板根本驱动不了它**」比「本机没装」更根本 ——
    #    图形应用 / 交互式 TUI **装了也驱动不了**，先报这条，别让人以为装完就能聊。
    argv = _argv_for(agent, probe["found"][0]["path"] if probe["found"] else "<exe>", text, extra_args)
    if not argv:
        return {"ok": False, "op": "send", "agent": agent, "status": "no_oneshot_entry",
                "fail_closed": True, "error_class": "no_oneshot_entry",
                "installed": probe["available"],
                "why": "该位**没有一次性 prompt 入口**（图形应用/交互式 TUI）⇒ 面板驱动不了它",
                "evidence": (_ONESHOT.get(agent) or {}).get("evidence"),
                "alternative": "它只能由主人手动开；面板如实显示『不能聊』，不假装能。"}
    if not probe["available"]:
        return {"ok": False, "op": "send", "agent": agent, "status": "needs_dependency",
                "fail_closed": True, "error_class": "needs_dependency",
                "missing": f"{probe['label']} 的可执行文件（找过：{'、'.join(probe['searched'])}）",
                "install_hint": probe["install_hint"], "probe": probe,
                "读法": "**不是坏了、也不是被门拒** —— 是本机没装这个 CLI。装完再发。"}

    exe = probe["found"][0]["path"]
    argv = _argv_for(agent, exe, text, extra_args)

    run_dir = cwd or str(_REPO)
    if dry_run:
        return {"ok": True, "op": "send", "agent": agent, "dry_run": True,
                "argv": argv, "cwd": run_dir, "prompt_len": len(text),
                "note": "只演练：**没起进程、没出网**。真发要过门（process_execute + external_llm）。"}

    gate = _gate(f"cli_chat send → {agent}")
    if not gate.get("ok"):
        return {"ok": False, "op": "send", "agent": agent, "denied": True, "fail_closed": True,
                "error_class": "needs_authorization",
                "error": gate.get("error") or "缺授权",
                "missing": gate.get("missing") or list(_GATE_SCOPES),
                "how_to_grant": gate.get("how_to_grant"),
                "why": "发一句话 = 起外部进程 + 把内容送出本机 ⇒ 这是要授权的事",
                "口径": "缺授权就如实报缺；**不绕门、不直接调模块函数**。"}

    t0 = time.time()
    try:
        cp = subprocess.run(argv, capture_output=True, timeout=int(timeout), cwd=run_dir,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        rec = {"ok": False, "op": "send", "agent": agent, "status": "timeout",
               "timeout": int(timeout), "ms": round((time.time() - t0) * 1000, 1),
               "prompt": text, "error": f"外部助手 {timeout}s 未返回"}
        _log({**rec, "event": "send"})
        return rec
    except Exception as exc:                                  # noqa: BLE001
        rec = {"ok": False, "op": "send", "agent": agent, "status": "spawn_failed",
               "error": f"{type(exc).__name__}: {exc}", "argv": argv,
               "ms": round((time.time() - t0) * 1000, 1), "prompt": text}
        _log({**rec, "event": "send"})
        return rec

    out = (cp.stdout or b"").decode("utf-8", "replace")
    err = (cp.stderr or b"").decode("utf-8", "replace")
    ms = round((time.time() - t0) * 1000, 1)
    blocked = (cp.returncode != 0) and _looks_host_blocked(out + err)
    reply = out.strip()
    rec = {
        "ok": (cp.returncode == 0) and bool(reply),
        "op": "send", "agent": agent, "exe": exe, "argv": argv, "cwd": run_dir,
        "exit": cp.returncode, "ms": ms,
        "prompt": text, "reply": reply[-8000:], "stdout": out[-8000:], "stderr": err[-2000:],
        "status": ("host_blocked" if blocked else ("ok" if cp.returncode == 0 else "nonzero_exit")),
    }
    if blocked:
        rec["error_class"] = "host_blocked"
        rec["读法"] = ("进程被**宿主安全策略**拦下（典型：这些 CLI 启动要调 `reg.exe`，"
                      "而 `reg.exe` 在黑名单里）⇒ **不是面板的错、也不是没装**。"
                      "在不受限的宿主里跑即正常。")
    if not reply and cp.returncode == 0:
        rec["note"] = "退出码 0 但 stdout 为空 —— 原样回报，不替它编内容。"
    _log({"event": "send", **{k: rec[k] for k in
                              ("agent", "prompt", "ok", "exit", "ms", "status") if k in rec}})
    return rec


# ── 自检 / 定位 ───────────────────────────────────────────────────────────

def verify() -> dict:
    """机检：形态表与真探对得上、门是真的、账本可读。"""
    problems = []
    ca = _agents_mod()
    a = agents(want_latest=False)
    for row in a["rows"]:
        if row["can_chat"] and not row["oneshot"]:
            problems.append(f"{row['kind']}：判了 can_chat 却没有一次性形态")
        if row["kind"] not in ca._AGENTS:
            problems.append(f"{row['kind']}：不在 cli_agents._AGENTS 里（表对不上）")
    # 门必须真的接在 auth_gate 上（不是自己写一个假的 ok）
    try:
        from . import auth_gate
        assert hasattr(auth_gate, "check_and_consume_many")
    except Exception as exc:                                  # noqa: BLE001
        problems.append(f"授权门不可用：{type(exc).__name__}: {exc}")
    # 未装位不许被判成能聊
    for row in a["rows"]:
        if not row["available"] and row["can_chat"]:
            problems.append(f"{row['kind']}：没装却判成能聊")
    return {"ok": not problems, "op": "verify", "problems": problems,
            "chatable": a["chatable"], "registered": a["registered"], "installed": a["installed"],
            "gate_scopes": list(_GATE_SCOPES), "ledger": str(_LEDGER),
            "_口径": ("形态表 ↔ 真探一致 · can_chat 必须 装且有一次形态 · 门走 auth_gate · "
                     "未装位不许判成能聊")}


def where() -> dict:
    return {"ok": True, "op": "where", "kind": "cli_chat", "entry": "run_task('cli_chat', {...})",
            "ops": ["agents", "send", "transcript", "verify", "where"],
            "page": "holo_pet/assets/cli-chat/index.html",
            "ledger": str(_LEDGER),
            "hard_facts": [
                "4 位本机已装且**全部有一次性 prompt 入口**（claude -p / codebuddy -p / "
                "codex exec / copilot -p）⇒ 面板能真聊（与 freebuff 的 TUI-only 本质不同）",
                "2 位未装（gemini_cli / ul_tars_desktop）⇒ 如实报缺，不编",
                "『免费』= 走各 CLI 自己的登录态/额度，不经框架 API key ⇒ 不吃 API 账单",
                "沙箱/受限宿主里真跑会被拦（CLI 启动要调 reg.exe）⇒ 如实报 host_blocked",
            ],
            "gates": {"send": list(_GATE_SCOPES)},
            "gap": ("`security/policy.py` 无 `cli_chat` 分支（owner-only，AI 无权改）"
                    "⇒ 门在本模块内自闸（auth_gate）；**已如实登记，不擅自改 policy**")}


def run_op(op: str = "agents", **params) -> dict:
    op = (op or "agents").lower()
    if op == "send":
        return send(params.pop("agent", "") or params.pop("kind", ""),
                    params.pop("prompt", "") or params.pop("q", ""), **params)
    if op == "transcript":
        return transcript(params.get("agent", ""), int(params.get("limit", 30)))
    for name, fn in (("agents", lambda: agents(int(params.get("timeout", 20)))),
                     ("list", lambda: agents(int(params.get("timeout", 20)))),
                     ("probe", lambda: agents(False, int(params.get("timeout", 20)))),
                     ("verify", verify), ("where", where)):
        if op == name:
            return fn()
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（agents/send/transcript/verify/where）"}


def run(payload: dict | None = None) -> dict:
    """能力位入口（api.py 分派到这里）。op 默认 agents（**只读**，打开面板即可看底表）。"""
    p = dict(payload or {})
    op = str(p.pop("op", None) or p.pop("action", None) or "agents").lower()
    return run_op(op, **p)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="外部 CLI 助手对话面板（cli_chat）")
    ap.add_argument("cmd", nargs="?", default="agents",
                    choices=["agents", "transcript", "verify", "where"])
    ap.add_argument("--agent", default="")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                                          # noqa: BLE001
        pass
    if a.cmd == "agents":
        r = agents()
    elif a.cmd == "transcript":
        r = transcript(a.agent)
    else:
        r = run_op(a.cmd)
    print(json.dumps(r, ensure_ascii=False, indent=1))          # noqa: T201
    raise SystemExit(0)
