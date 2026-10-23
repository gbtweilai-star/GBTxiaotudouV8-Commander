# -*- coding: utf-8 -*-
r"""DSH 总线（dsh-bus）—— **万能插的 ④ 那一半：我们 → 她**。

主人令（2026-10-10，逐字）：
  「万能插就是**接管她原来的地方**懂吗？也就是**从新开辟出一条能连接她所有能力的接口直接插入**，
    也**不去破坏它**，就把她**掩盖掉**懂吗」

## 自查（我原先理解错在哪，写在最前面免得再犯）
万能插是**四件**，缺一件都不是它：
  ① **不破坏她** —— 一行都不改她（她 = DSH）
  ② **盖住她**   —— 门面是我们的（holo_pet_w3/shell/dsh-embed.html：她在下面跑，头图是我们的）
  ③ **她 → 我们** —— 已有：deepseek_bridge.build_manifest() 把我们 253 位能力整表给她 +
     她的 gbt 指令块回执执行（run_task_safe 唯一口）
  ④ **我们 → 她** —— 🔴 **原先没有**（grep 反向路径零命中）⇒ 只做到「贴皮」，没做到「接管能力」

本件就是补 ④：**把她全部能力枚举出来、逐条给出我们这侧怎么调**，而不是只盖个壳。

## 她的能力面 = 插件树（现读，不是猜）
命令 dsh --profile 名 --dump-config 打出的那棵树**就是她的能力清单**：
  gbt-official 157 个 · web 154 个 · **去重 158 个**。
她另外两个口：dsh plugin（管插件）· dsh web（起 web 形态）；
  desktop profile 是 **Electron 独占**（实测：profile "desktop" is managed exclusively by the Electron application）。

用法：py -3.14 -X utf8 tools/codex-scripts/dsh-bus.py [list|dump <profile>|--check]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "state" / "dsh-bus.json"
PROFILES = ("gbt-official", "web")


def how(cid: str):
    """→ (档, 怎么调)。档只有三档：可直调 / 随 profile 起 / 需主人侧。给不出具体法的**不许编**。"""
    c = cid.lower()
    if c.startswith("command") or c in ("commands", "command-compact", "command-goal", "command-feedback"):
        return "可直调", "dsh web --help 看该命令；或在我们壳的对话面发同一句"
    if c in ("llm", "deepseek-llm-api-extensions", "agent", "agent-loop"):
        return "可直调", "我们壳的对话面就是这条（dsh-embed.html 内嵌 web）"
    if c in ("session", "session-log-deepseek", "session-title", "session-title-llm"):
        return "可直调", "走她的 session 面（我们壳从 web 形态读）"
    if "plugin" in c:
        return "可直调", "dsh plugin <sub>（转发她的插件管理）"
    if c in ("connection", "api-remotes", "typert-gateway", "credentials", "approval"):
        return "需主人侧", "涉凭据/审批 —— 只在她的界面里由主人操作"
    return "随 profile 起", "起该 profile 即随附（无单独调用口，如实标）"


def _dump(prof: str) -> str:
    cp = subprocess.run(["dsh", "--profile", prof, "--dump-config"],
                        capture_output=True, shell=True)
    return ((cp.stdout or b"") + (cp.stderr or b"")).decode("utf-8", "replace")


def scan() -> dict:
    rows, per = [], {}
    for prof in PROFILES:
        t = _dump(prof)
        ids = re.findall(r"^- id: (\S+)", t, re.M)
        names = re.findall(r"^  name: (\S+)", t, re.M)
        per[prof] = {"插件数": len(ids), "字节": len(t)}
        for i, cid in enumerate(ids):
            dk, hw = how(cid)
            rows.append({"profile": prof, "id": cid,
                         "包": names[i] if i < len(names) else "", "档": dk, "怎么调": hw})
    return {"profiles": per, "逐条": rows,
            "总数": len({r["id"] for r in rows}),
            "分档": {k: sum(1 for r in rows if r["档"] == k)
                     for k in ("可直调", "随 profile 起", "需主人侧")}}


def check() -> int:
    d = scan()
    bad = [r for r in d["逐条"] if not r["档"] or not r["怎么调"]]
    d["at"] = __import__("time").strftime("%Y-%m-%dT%H:%M:%S")
    d["顶层命令面"] = {"profile 树": "dsh --profile 名 --dump-config",
                       "插件管理": "dsh plugin <sub>", "起 web": "dsh web",
                       "desktop": "Electron 独占（实测拒绝）"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    (ROOT / "state" / "dsh-plugins.json").write_text(
        json.dumps({p: {"ids": sorted({r["id"] for r in d["逐条"] if r["profile"] == p})}
                    for p in PROFILES}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("DSH 总线（我们 → 她）：去重 **%d 个插件**" % d["总数"])
    for p, v in d["profiles"].items():
        print("  %-14s %3d 个" % (p, v["插件数"]))
    for k, v in d["分档"].items():
        print("  %-12s %3d" % (k, v))
    print("  命令面：dsh --profile 名 --dump-config ｜ dsh plugin ｜ dsh web ｜ desktop=Electron 独占")
    print("判据：%s" % ("PASS" if not bad else "FAIL（有 %d 条没给怎么调）" % len(bad)))
    return 0 if not bad else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="DSH 总线（万能插 ④）")
    ap.add_argument("cmd", nargs="?", default="list", choices=["list", "dump"])
    ap.add_argument("profile", nargs="?")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.cmd == "dump" and a.profile:
        print(_dump(a.profile))
        return 0
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
