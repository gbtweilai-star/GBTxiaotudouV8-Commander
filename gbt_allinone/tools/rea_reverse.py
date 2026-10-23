# gbt-capability: rea_reverse
"""REA 桥 —— 吞天吞进来的第一件外部能力（主人 2026-10-11 图片）。

## 来历（一句话，带出处，不靠回忆）
主人发来 https://rea.tools/ 首页的图，一句「让触手把这个吞噬了」。
触手现读：首页 51,313 B（title「REA — Reverse Engineering for Your Coding Agent」）·
README 18,481 B ⇒ 吞天 devour_github 真吞成胶囊 devoured_morluto_rea
（morluto/rea · TypeScript · MIT · npm rea-agents 6.4.0）。

## 能干什么（全部可复核）
- status / knowledge / commands / plan / where —— 只读。
- **cli —— 真能跑**（2026-10-12 接上，实测见下）：把一条 REA 命令交给框架**已有的手**
  desktop_commander（tentacle 域）去起进程；**门在它身上**（process_execute，policy.py:168-171）。
  实测：连上 desktop-commander 0.2.52 ⇒ start_process 跑 npx -y rea-agents@latest --version
  ⇒ 真返回 **6.4.0**（PID 12796，powershell.exe）。

## 🔴 为什么执行面这样接（口径写死，别念错）
**本位自己不起进程**：本文件里没有 subprocess、没有 os.system、不写盘。
原因：policy.evaluate("rea_reverse", …) 落到函数末尾兜底 ⇒ scopes=() （**fail-open**）。
若在这里私接 subprocess，就等于「执行免票」——本仓在 obsidian_vault / room_space 上栽过同一跟头
（见 security/policy.py:348-380 的根因注释）。
**走已有的闸门**是正解：进程由 desktop_commander 起，票也在它那过 ⇒ **门只有一处**，没有第二道缝。
另外：`setup` 一律拒（它会改写 Claude Code / Codex / Cursor 等 agent 的配置文件）。

## 读数来源（不许把「记着的」念成「现读的」）
- **现读**：胶囊文件在不在盘上、node/npm/npx 在不在 PATH（shutil.which，不起进程）、文件字节数。
- **记着**：版本号 / 命令名 / help 指纹来自 state/rea_probe.json，那个文件里写着探测时刻。

op=status / knowledge / commands / plan / cli / where
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_CAPSULE = _ROOT / "gbt_allinone" / "store" / "devoured" / "devoured_morluto_rea"
_PROBE = _ROOT / "state" / "rea_probe.json"

# 会改写别的软件配置的命令：一律拒，只给理由（判据见 README：Setup adds REA MCP server，
# with backups of existing configuration）
_REFUSE = {
    "setup": "setup 会改写 Claude Code / Codex / Cursor / Gemini CLI 等 agent 的配置文件"
             "（README 原文：with backups of existing configuration）⇒ 本位一律不代跑；"
             "要装由主人在终端自己决定。",
}

# 只点出有 README / help 直接撑腰的那几条；名字全量走 op=commands（真 help 解析出来的 129 条）
_KNOWN = {
    "analyze": "给一个应用出总览",
    "analyze-javascript-application": "静态重建本地 JS/Electron 应用（只看文件，不运行它）",
    "analyze-web-bundle": "抓并静态分析页面 bundle（默认当前选中 origin）",
    "decompile": "把应用某一部分读成代码",
    "capabilities": "列 provider 能力与副作用",
    "compare": "比对两个 canonical Evidence 包",
    "doctor": "体检本机依赖（provider / browser / 反汇编器 …）",
}


def _read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _probe() -> dict:
    return _read_json(_PROBE) or {}


def _capsule_files() -> list:
    if not _CAPSULE.is_dir():
        return []
    out = []
    for f in sorted(_CAPSULE.iterdir()):
        if f.is_file():
            out.append({"name": f.name, "bytes": f.stat().st_size})
    return out


def _unwrap(r) -> dict:
    """把 run_task 的返回剥到本体（有 gbt_result 信封就剥）。"""
    r = r or {}
    if isinstance(r, dict) and "gbt_result" in r:
        r = (r.get("gbt_result") or {})
        if isinstance(r.get("result"), dict):
            r = r["result"]
    return r if isinstance(r, dict) else {}


def status(**_kw) -> dict:
    """现读：PATH 上有没有 node/npm/npx + 胶囊在不在盘上；另附探测时刻的版本账。"""
    pr = _probe()
    files = _capsule_files()
    body = next((f for f in files if f["name"] == "absorbed_knowledge.md"), None)
    return {
        "ok": True, "op": "status", "kind": "rea_reverse",
        "来源": {"上游": "https://rea.tools/ · github.com/morluto/rea · npm rea-agents",
                 "吞入": "devour_github（2026-10-11 真跑）", "胶囊": "devoured_morluto_rea"},
        "现读": {"node_on_path": shutil.which("node") or "", "npm_on_path": shutil.which("npm") or "",
                 "npx_on_path": shutil.which("npx") or "",
                 "capsule_dir": str(_CAPSULE), "capsule_exists": _CAPSULE.is_dir(),
                 "capsule_files": files, "knowledge_bytes": (body or {}).get("bytes", 0)},
        "记着": {"probe_at": pr.get("at", ""), "node": pr.get("node", ""), "npm": pr.get("npm", ""),
                 "rea_agents_version": pr.get("rea_agents_version", ""),
                 "command_count": pr.get("command_count", 0),
                 "help_sha256_16": pr.get("help_sha256_16", ""),
                 "probe_file": str(_PROBE.relative_to(_ROOT)) if _PROBE.is_file() else ""},
        "执行面": "cli 走 desktop_commander（门在它身上：process_execute）；本位自身不起进程",
        "口径": "「现读」= 此刻盘上与 PATH；「记着」= 探测时刻写进 state/rea_probe.json 的读数，别当现状念",
    }


def knowledge(limit: int = 4000, full: bool = False, **_kw) -> dict:
    """读吞噬胶囊正文（默认截 4000 字，full=True 给全文）。"""
    p = _CAPSULE / "absorbed_knowledge.md"
    if not p.is_file():
        return {"ok": False, "op": "knowledge", "fail_closed": True, "error": f"胶囊正文不在盘上：{p}"}
    txt = p.read_text(encoding="utf-8", errors="replace")
    n = len(txt)
    body = txt if full else txt[: max(0, int(limit))]
    return {"ok": True, "op": "knowledge", "path": str(p), "chars": n, "shown": len(body),
            "truncated": len(body) < n, "text": body}


def commands(q: str = "", limit: int = 0, **_kw) -> dict:
    """列 REA 的真命令名（从实测 help 里解析，不是我编的）。q=子串过滤，limit=截断。"""
    pr = _probe()
    cmds = list(pr.get("commands") or [])
    if q:
        needle = str(q).lower()
        cmds = [c for c in cmds if needle in c]
    if limit:
        cmds = cmds[: int(limit)]
    known = {k: v for k, v in _KNOWN.items() if not q or str(q).lower() in k}
    return {"ok": bool(pr), "op": "commands", "count": len(cmds), "q": q, "commands": cmds,
            "known": known,
            "source": {"probe": str(_PROBE.relative_to(_ROOT)) if _PROBE.is_file() else "",
                       "at": pr.get("at", ""), "version": pr.get("rea_agents_version", ""),
                       "help_sha256_16": pr.get("help_sha256_16", "")},
            "note": "命令名来自 npx -y rea-agents@latest --help 的真输出解析；help 指纹在 source 里可复核",
            "refused": _REFUSE}


def plan(target: str = "", intent: str = "", **_kw) -> dict:
    """只出**可直接照抄的命令行**，不执行。给了 target 就按 README 里那两条只读路径出。"""
    t = (target or "").strip()
    steps = [{"why": "装/接（**本位一律不代跑**）", "cmd": "npx rea-agents@latest setup",
              "refused": True, "reason": _REFUSE["setup"]}]
    if t:
        steps += [
            {"why": "JS/Electron 应用：静态重建（只读文件，不运行它）· 出处 README 快速上手",
             "cmd": 'npx -y rea-agents@latest analyze-javascript-application "' + t + '" --json'},
            {"why": "网页 bundle：抓并静态分析 · 出处 README 的 Websites 一行",
             "cmd": 'npx -y rea-agents@latest analyze-web-bundle "' + t + '" --json'},
        ]
    else:
        steps.append({"why": "给了 target 我再出上面两条（JS/Electron 与网页）", "cmd": ""})
    return {"ok": True, "op": "plan", "target": t, "intent": intent, "steps": steps,
            "native_note": "native（二进制）那一路要 Hopper / Ghidra / IDA —— 本机 PATH 上四个都没有"
                           "（2026-10-12 现读），所以现在能真用的是 JS-Electron / .NET / 网页 / 包与资源那几路。",
            "怎么真跑": "op=cli（dry=False）—— 交给 desktop_commander 起进程，门在它身上",
            "where_to_run": "主人终端粘贴，或直接 op=cli"}


def _q(s: str) -> str:
    s = str(s)
    return '"' + s + '"' if " " in s else s


def cli(argv=None, dry: bool = True, wait_s: int = 20, **_kw) -> dict:
    """把一条 REA 命令交给框架**已有的手**（desktop_commander）去跑；默认 dry=True 只回命令。

    **本位不起进程**：start_process / read_process_output 都在 desktop_commander 那边，
    票（process_execute）也在它那过 ⇒ 门只有一处。给了 dry=False 才真跑。
    """
    import shlex
    if isinstance(argv, str):
        argv = shlex.split(argv)
    argv = [str(a) for a in (argv or [])]
    if not argv:
        return {"ok": False, "op": "cli", "fail_closed": True,
                "error": "要给 argv（那串 REA 参数，第一项是命令名）",
                "例": ["analyze-javascript-application", "D:/apps/example", "--json"]}
    head = argv[0].lstrip("-")
    if head in _REFUSE:
        return {"ok": False, "op": "cli", "refused": True, "argv": argv, "reason": _REFUSE[head]}
    cmd_list = ["npx", "-y", "rea-agents@latest"] + argv
    base = {"op": "cli", "argv": argv, "cmd": " ".join(cmd_list),
            "通过谁跑": "万能插 omni_plug（socket=process）· 门在它身上：process_execute",
            "一步": "run_task('omni_plug', {'op':'run','socket':'process','target':'npx -y rea-agents@latest',"
                    "'args':{'cmd':[<argv…>],'max_out':8000},'timeout':<wait_s>})",
            "本位": "不自起进程：本文件没有 subprocess —— 进程由万能插的 process 插座起，票也在它那过"}
    if dry:
        return {"ok": True, "dry": True, **base, "note": "dry=True：只出命令；要真跑给 dry=False"}
    from ..api import run_task
    got = _unwrap(run_task("omni_plug", {"op": "run", "socket": "process",
                                         "target": "npx -y rea-agents@latest",
                                         "args": {"cmd": cmd_list, "max_out": 8000},
                                         "timeout": max(10, int(wait_s))}))
    return {"ok": bool(got.get("ok")), "dry": False, **base,
            "rc": got.get("rc"), "stdout": got.get("stdout"), "stderr": got.get("stderr"),
            "ms": got.get("ms"), "万能插返回": got}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "rea_reverse", "tentacle": "rea_reverse",
            "entry": "run_task('rea_reverse', {'op': …})",
            "ops": ["status", "knowledge", "commands", "plan", "cli", "where"],
            "files": {"handler": "gbt_allinone/tools/rea_reverse.py",
                      "胶囊": "gbt_allinone/store/devoured/devoured_morluto_rea/",
                      "探测读数": "state/rea_probe.json"},
            "scopes": "本位只读 + 只代理 ⇒ policy 无本 kind 分支（零作用域）；"
                      "**真跑的门在 desktop_commander 的 process_execute 上**（门只有一处）",
            "contract": [
                {"op": "status", "params": "无", "returns": "现读 PATH/胶囊 + 探测时刻的版本账"},
                {"op": "knowledge", "params": "limit / full", "returns": "吞噬胶囊正文"},
                {"op": "commands", "params": "q / limit", "returns": "REA 真命令名 + help 指纹"},
                {"op": "plan", "params": "target / intent", "returns": "可照抄的命令行"},
                {"op": "cli", "params": "argv / dry / wait_s",
                 "returns": "dry=True 只回命令；dry=False 交给 desktop_commander 真跑并回捕获输出"},
            ],
            "why_not_here": "本位若私接 subprocess = 执行免票（policy 对本 kind 无分支 ⇒ fail-open）；"
                            "走已有的 desktop_commander 就是「门只有一处」"}


_OPS = {"status": status, "knowledge": knowledge, "commands": commands,
        "plan": plan, "cli": cli, "where": where}
_ALLOWED = {"status": set(), "knowledge": {"limit", "full"}, "commands": {"q", "limit"},
            "plan": {"target", "intent"}, "cli": {"argv", "dry", "wait_s"}, "where": set()}


def run_op(op: str = "status", **params) -> dict:
    op = (op or "status").strip().lower()
    fn = _OPS.get(op)
    if fn is None:
        return {"ok": False, "op": op, "fail_closed": True, "error": f"未知 op：{op}",
                "ops": sorted(_OPS), "how": "run_task('rea_reverse', {'op': …})"}
    extra = set(params) - _ALLOWED[op]
    if extra:
        return {"ok": False, "op": op, "fail_closed": True,
                "error": f"不认的参数：{sorted(extra)}", "allowed": sorted(_ALLOWED[op])}
    return fn(**params)
