#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Codex 驱动臂 · **一根触手专用**（非交互、可复跑、带 429 自愈 + 留痕）

## 它解决什么
主人要的分工是：「**忙的时候可以单独一根触手操控她**，其他触手作别的」。
⇒ 那就得有一个**单一职责、可复跑、不占对话**的驱动臂：一条命令把任务交给 Codex，
拿到答复 + 留痕；我这边的其它触手（subagent / 别的活）同时干别的。

## 三条纪律
1. 🔴 **必带本仓现状**（`--state` 默认塞 `memory/在办清单.md` 的**尾部若干节**）——
   实测教训：不带现状时她会**从零规划**，于是把已经跑通的东西（OpenPose+LoRA 闭环）
   当"待建"、并按**本机没有的显卡**（RTX 12GB+）出方案。
2. 🔴 **429 自愈但要诚实**：先打一发；若命中网关的"路由冷却"（原话
   `All models exhausted: N route checked`），调 `freellm-alive.py pin` 换一条活路由**重试一次**，
   并把"换过钉/换成了谁"写进留痕。**只重试一次**，不许无限重试掩盖问题。
3. 🔴 **只读沙箱**：默认 `--sandbox read-only`。要让她动文件必须显式 `--write`，
   且那属于有后果动作（本仓规矩：写盘先问主人）。

用法：
```
python tools/codex-scripts/codex-drive.py "你的任务"                 # 带现状、只读
python tools/codex-scripts/codex-drive.py --task-file task.md         # 从文件读任务
python tools/codex-scripts/codex-drive.py --no-state "只回答 PONG"    # 不带现状
python tools/codex-scripts/codex-drive.py --write "…"                # 允许她改文件（有后果）
```
## 要她给什么（第 86 轮实测补的一条）
**要结论与结构，不要细节。** 实测：她的"细节化方案"9 条里 7 条是编的
（`controlnet_name`/`control_image` 这类入参名、`{"nodes":[...]}` 这类格式、几处路径/文件名），
而她给的结构判断（分段、三件套同卡、轮询兜底、审核闸）全对 —— **她的价值在结构与边界，不在细节**。
⇒ 任务里**明确要"结构 + 边界 + 未验项"**；凡她给到 API/路径/文件名那一层，
**一律以本仓盘上的实物为准**，经手方**逐条落盘核**。

## 器具账
起服务这类"起完还要等"的动作**必须挂后台**（前台等会把工具调用耗到超时 —— 第 86 轮实测过一次）。

留痕：`state/codex-drive/<时间戳>.json`
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "state" / "codex-drive"
CODEX = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "OpenAI" / "Codex" / "bin" / "codex.exe"
LEDGER = ROOT / "memory" / "在办清单.md"
ALIVE = ROOT / "tools" / "codex-scripts" / "freellm-alive.py"


def env_key():
    v = os.environ.get("FREELLMAPI_API_KEY")
    if v:
        return v
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, "FREELLMAPI_API_KEY")[0]
    except Exception:                                                      # noqa: BLE001
        return None


def tail_state(n=3):
    """取在办清单**最后 n 节**当现状（全文 120 KB 太大；尾部才是最新收口）。"""
    if not LEDGER.exists():
        return "(找不到在办清单)"
    t = LEDGER.read_text(encoding="utf-8")
    secs = list(re.finditer(r"^## .+$", t, re.M))
    if not secs:
        return t[-6000:]
    start = secs[max(0, len(secs) - n)].start()
    return t[start:start + 9000]


def run_codex(prompt, write=False, timeout=900, cd=None):
    if not CODEX.exists():
        return {"exit": 127, "out": "", "why": "codex.exe 不在 %s" % CODEX}
    args = [str(CODEX), "exec", "--skip-git-repo-check",
            "--sandbox", "workspace-write" if write else "read-only"]
    if cd:
        args += ["-C", str(cd)]
    args.append(prompt)
    env = dict(os.environ)
    k = env_key()
    if k:
        env["FREELLMAPI_API_KEY"] = k
    t0 = time.time()
    try:
        cp = subprocess.run(args, cwd=str(cd or ROOT), capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout, env=env)
        return {"exit": cp.returncode, "out": cp.stdout or "", "err": cp.stderr or "",
                "耗时s": round(time.time() - t0, 1)}
    except subprocess.TimeoutExpired:
        return {"exit": -1, "out": "", "why": "超时 %ss（没等到答复）" % timeout,
                "耗时s": round(time.time() - t0, 1)}


def is_cooldown(txt):
    return bool(re.search(r"All models exhausted|rate-limited or on cooldown|429 Too Many Requests", txt or ""))


def repin():
    cp = subprocess.run([sys.executable, str(ALIVE), "pin"], cwd=str(ROOT),
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    try:
        j = json.loads((cp.stdout or "")[((cp.stdout or "").find("{")):])
    except Exception:                                                      # noqa: BLE001
        j = {"raw": (cp.stdout or cp.stderr or "")[-300:]}
    return j


def main():
    ap = argparse.ArgumentParser(description="Codex 驱动臂（一根触手专用）")
    ap.add_argument("prompt", nargs="?", default="")
    ap.add_argument("--task-file", default="")
    ap.add_argument("--no-state", action="store_true", help="不带本仓现状（默认带）")
    ap.add_argument("--state-sections", type=int, default=3)
    ap.add_argument("--write", action="store_true", help="允许她改文件（有后果，默认只读）")
    ap.add_argument("--timeout", type=float, default=900)
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    task = a.prompt
    if a.task_file:
        task = Path(a.task_file).read_text(encoding="utf-8")
    if not task.strip():
        print("❗没给任务（位置参数或 --task-file）")
        return 2
    prompt = task if a.no_state else (
        "【本仓现状（在办清单最后 %d 节，原文）】\n%s\n\n【你的任务】\n%s\n\n"
        "⚠️ 先读现状再回答：**现状里已经验过的不要重做**，也不要按本机没有的硬件出方案"
        "（本机无 CUDA、内存 7.4GB、已有可复跑的验收器）。回答要短、要能落地。"
        % (a.state_sections, tail_state(a.state_sections), task))

    rec = {"时间": time.strftime("%Y-%m-%dT%H:%M:%S"), "带现状": not a.no_state,
           "沙箱": "workspace-write" if a.write else "read-only",
           "任务": task[:2000], "提示字数": len(prompt)}
    r = run_codex(prompt, write=a.write, timeout=a.timeout)
    rec["第一次"] = {"exit": r.get("exit"), "耗时s": r.get("耗时s"),
                  "命中冷却": is_cooldown((r.get("out") or "") + (r.get("err") or ""))}
    healed = None
    if rec["第一次"]["命中冷却"]:
        healed = repin()
        rec["换钉"] = healed
        r = run_codex(prompt, write=a.write, timeout=a.timeout)
        rec["重试一次"] = {"exit": r.get("exit"), "耗时s": r.get("耗时s")}
    out = r.get("out") or ""
    rec["答复"] = out[-6000:]
    rec["成败"] = ("✅ 拿到答复" if out.strip() and not is_cooldown(out) else "❗没拿到")
    OUT.mkdir(parents=True, exist_ok=True)
    p = Path(a.json) if a.json else OUT / ("%s.json" % time.strftime("%Y%m%d-%H%M%S"))
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=1), "utf-8")

    print("=" * 74)
    print(out.strip()[-4000:] if out.strip() else "(空答复)")
    print("=" * 74)
    print("驱动读数：%s · exit=%s · %ss%s" % (rec["成败"], r.get("exit"), r.get("耗时s"),
                                         ("　（换过一次钉：%s）" % healed.get("改后")) if healed else ""))
    print("留痕：%s" % p)
    return 0 if rec["成败"].startswith("✅") else 1


if __name__ == "__main__":
    raise SystemExit(main())
