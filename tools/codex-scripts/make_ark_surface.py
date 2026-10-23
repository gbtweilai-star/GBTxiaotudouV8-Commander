"""生成「Ark 云端能力面」的单一声明：holo_pet/ark_surface.json

为什么要有这个东西
------------------
总面板的能力台（capabilities.html）**不调接口**：158 项能力是生成时烤进页面的静态数组
（`const CAPS=[...]`）。所以要把 Ark CLI 那批能力也摆上球面，就必须走**生成器 + 一份声明**，
而不是手改页面（手改的下一次生成就没了）。

同时面板服务 `/api/capabilities` 也要报这块能力面。**两处读同一份声明** —— 不做第二份真相。

数据从哪来（现读，不手抄、不猜）
--------------------------------
arkcli 技能装在本地时，每个技能目录里都有 `SKILL.md`，前置字段里带着：
  - `name` / `version`
  - `description`：这个技能是干什么的（官方原文）
  - `metadata.requires.bins`：要哪个可执行文件
  - `metadata.cliHelp`：**真实命令入口**（例如 `arkcli billing list --help`）
所以这里逐目录现读，读不到就如实少报，绝不凭空补一条。

用法：
    python tools/codex-scripts/make_ark_surface.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
OUT = ROOT / "holo_pet" / "ark_surface.json"
HOME = Path.home()

# 现读优先级：本仓声明的托管目录优先（Ark 用 +connect --path 装进去的那份），
# 后面几个是 Ark 自己认的 agent 目录，全当兜底。
SKILL_DIRS = [
    HOME / ".openclaw-autoclaw" / "skills",
    HOME / ".agents" / "skills",
    HOME / ".claude" / "skills",
]

# 前置字段只取我们真要用的，别把整段 front matter 抄进声明。
FM = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def read_front_matter(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    m = FM.match(text)
    if m is None:
        return {}
    raw = m.group(1)
    out: dict = {}
    for line in raw.splitlines():
        # 只认顶层 `key: value`（缩进的是子字段，单独处理）
        mm = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if mm is None:
            continue
        key, val = mm.group(1), mm.group(2).strip()
        if val.startswith('"') and val.endswith('"') and len(val) >= 2:
            val = val[1:-1]
        out[key] = val
    bins = re.search(r'bins:\s*\[([^\]]*)\]', raw)
    if bins is not None:
        out["bins"] = [b.strip().strip('"').strip("'")
                       for b in bins.group(1).split(",") if b.strip()]
    # `cliHelp` 在 `metadata:` 下面**带缩进**，顶层那个正则抓不到 —— 单独抓（第一版就栽在这）。
    help_m = re.search(r'^\s*cliHelp:\s*(.+)$', raw, re.M)
    if help_m is not None:
        out["cliHelp"] = help_m.group(1).strip().strip('"').strip("'")
    return out


def short_desc(text: str, limit: int = 150) -> str:
    """只取第一句 —— 官方 description 常常是一整段，球面上放不下。"""
    text = " ".join((text or "").split())
    if not text:
        return ""
    cut = re.split(r"(?<=[.。;；])\s", text, maxsplit=1)[0]
    if len(cut) < 24:            # 太短就退回首句 + 补到 limit
        cut = text
    return cut if len(cut) <= limit else cut[: limit - 1].rstrip() + "…"


def arkcli_version() -> str:
    """现读已装版本；取不到就如实写 unknown，不编。"""
    for cmd in (["arkcli", "--version"], ["cmd", "/c", "arkcli", "--version"]):
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=20)
            txt = (p.stdout or b"").decode("utf-8", "replace").strip()
            if p.returncode == 0 and txt:
                m = re.search(r"(\d+\.\d+\.\d+)", txt)
                return m.group(1) if m else txt[:40]
        except Exception:  # noqa: BLE001
            continue
    return "unknown"


def auth_snapshot() -> dict:
    """生成时刻的登录快照 —— **只取安全字段**。

    为什么不放进面板服务的每次请求里：那等于在 HTTP 处理链上起进程（可能挂住、可能被刷爆）。
    这里读一次、连时间戳一起写进声明，页面照实显示「截至生成时刻」的状态，
    要新读数就跑一次本脚本 —— 新鲜度是**写明的**，不是装出来的。
    🔴 绝不落 token / API key / STS 到声明里（声明是给页面看的）。
    """
    import os
    env = dict(os.environ)
    env["ARKCLI_NO_UPDATE_NOTIFIER"] = "1"
    env["ARKCLI_CALLER_TYPE"] = "ai_agent"
    env["ARKCLI_CALLER_NAME"] = "unknown_agent"
    env["ARKCLI_SKILL_NAME"] = "arkcli-shared"
    for cmd in (["arkcli", "auth", "status", "--format", "json"],
                ["cmd", "/c", "arkcli", "auth", "status", "--format", "json"]):
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=40, env=env)
            if p.returncode != 0 or not p.stdout:
                continue
            data = json.loads(p.stdout.decode("utf-8", "replace"))
            prof = data.get("active_profile") or {}
            ident = ((data.get("byteplus_sso") or {}).get("identity") or {})
            key = data.get("ark_api_key") or {}
            return {
                "logged_in": bool(data.get("logged_in")),
                "auth_method": str(data.get("auth_method") or ""),
                "profile": str(prof.get("name") or ""),
                "profile_type": str(prof.get("type") or ""),
                "region": str(prof.get("region") or ""),
                "project": str(prof.get("project") or ""),
                # 账号验证闸：false ⇒ 计费写入（部署/微调/建 Endpoint/建 Agent）会被挡
                "identity_verified": ident.get("verified"),
                "identity_name": str(ident.get("name") or ""),
                "api_key_status": str(key.get("status") or ""),
            }
        except Exception:  # noqa: BLE001
            continue
    return {"logged_in": None, "note": "取不到 auth status（没装、没登录或命令超时）"}


def main() -> int:
    skills, source_dir = [], None
    for d in SKILL_DIRS:
        if not d.is_dir():
            continue
        found = sorted([p for p in d.iterdir() if p.is_dir() and p.name.startswith("arkcli-")])
        if not found:
            continue
        source_dir = d
        for p in found:
            fm = read_front_matter(p / "SKILL.md")
            if not fm.get("name"):
                # 没有可读前置字段的目录不当成一条能力 —— 少报胜过编报
                continue
            skills.append({
                "name": str(fm.get("name")),
                "version": str(fm.get("version") or ""),
                "desc": short_desc(str(fm.get("description") or "")),
                "cli_help": str(fm.get("cliHelp") or ""),
                "bins": list(fm.get("bins") or []),
                "path": str(p),
            })
        break

    import time
    payload = {
        "generated_by": "tools/codex-scripts/make_ark_surface.py",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "generated_from": str(source_dir) if source_dir else "",
        "arkcli_version": arkcli_version(),
        "auth_snapshot": auth_snapshot(),
        "note": ("Ark 云端能力面（外部 CLI）：经 arkcli 调用，**不走本仓的能力口** "
                 "`/api/capability`，也不受 run_task 那道授权门管；"
                 "每条的 `cli_help` 是它自己的真实命令入口，来自该技能 SKILL.md 的前置字段（现读，非手抄）。"
                 "`auth_snapshot` 是**生成时刻**的读数，不是每次打开都现扫。"),
        "skills": skills,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("落盘 %s" % OUT.relative_to(ROOT))
    print("  arkcli 版本 : %s" % payload["arkcli_version"])
    print("  现读目录    : %s" % (payload["generated_from"] or "（一个都没有）"))
    print("  技能条数    : %d" % len(skills))
    for s in skills:
        print("    - %-26s %s" % (s["name"], s["cli_help"] or "（无 cliHelp）"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
