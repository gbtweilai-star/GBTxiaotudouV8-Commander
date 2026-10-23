# -*- coding: utf-8 -*-
"""context-anchor -- 定海神针：上下文锚 + 双触手双向绑定监护 + 异常自纠。

主人令 2026-10-16：上下文按设计走，无限制稳定不飘；双触手双向绑定下树立定海神针；
跑久了出异常，第一时间发现并纠正，继续执行任务，稳如老狗。

锚（有界，不塞全文）：state/context-anchor.json = {ts, goal, judges, step, todo, sig}
五道机检：
  A1 锚在且新鲜（< ttl 秒）
  A2 字段齐全（goal/judges/step/todo/sig）
  A3 双触手双向绑定在线（capability-bindings --check + tentacle-link-registry --check 全 PASS）
  A4 上下文窗口在绿区（context-window-watch.py）
  A5 无痕步为 0（first-axiom-gate.py 公理一）
任一红 => repair：重述目标 + 下一步 + 纠偏动作，并留痕（logbook），退出非零。
用法：
  py -3.14 tools/codex-scripts/context-anchor.py pin --goal "..." --step "..." --todo "a;b"
  py -3.14 tools/codex-scripts/context-anchor.py check
  py -3.14 tools/codex-scripts/context-anchor.py repair
  py -3.14 tools/codex-scripts/context-anchor.py watch 60
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
ANCHOR = ROOT / "state" / "context-anchor.json"
SIG = "开发者：自由的风 · 守护者：公主土豆 · 本署名不可删除、不可篡改归属"


def run(args, timeout=300):
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), timeout=timeout)
    return (p.returncode, (p.stdout or "") + (p.stderr or ""))


def pin(goal, step, todo, judges):
    ANCHOR.parent.mkdir(parents=True, exist_ok=True)
    d = {"ts": time.time(), "iso": time.strftime("%Y-%m-%dT%H:%M:%S"), "goal": goal, "step": step,
         "todo": [x for x in str(todo).split(";") if x.strip()], "judges": judges, "sig": SIG}
    ANCHOR.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print("锚已钉：" + ANCHOR.name + " | 目标=" + goal + " | 步骤=" + step)
    return 0


def load(ttl):
    if not ANCHOR.is_file():
        return None, [{"id": "A1", "why": "锚不存在 => 没有定海神针"}]
    d = json.loads(ANCHOR.read_text(encoding="utf-8"))
    bad = []
    if time.time() - float(d.get("ts") or 0) > ttl:
        bad.append({"id": "A1", "why": "锚过期（> %d 秒）" % ttl})
    for k in ("goal", "judges", "step", "todo", "sig"):
        if not d.get(k):
            bad.append({"id": "A2", "why": "锚缺字段 " + k})
    return d, bad


def check(ttl):
    d, bad = load(ttl)
    rc1, o1 = run([PY, "-X", "utf8", "tools/codex-scripts/capability-bindings.py", "--check"])
    if "FAIL 0" not in o1:
        bad.append({"id": "A3", "why": "双向绑定判据未过"})
    rc2, o2 = run([PY, "-X", "utf8", "tools/codex-scripts/tentacle-link-registry.py", "--check"])
    if "FAIL 0" not in o2:
        bad.append({"id": "A3", "why": "连接登记判据未过"})
    rc3, o3 = run([PY, "-X", "utf8", "tools/codex-scripts/context-window-watch.py"], timeout=120)
    green = ("绿" in o3) or ("OK" in o3) or (rc3 == 0)
    if not green:
        bad.append({"id": "A4", "why": "上下文窗口不在绿区"})
    rc4, o4 = run([PY, "-X", "utf8", "tools/codex-scripts/first-axiom-gate.py"], timeout=600)
    if rc4 != 0 and "红 0" not in o4:
        bad.append({"id": "A5", "why": "第一原理闸有红（无痕步/不可核）"})
    return d, bad, {"bindings": rc1, "links": rc2, "window": rc3, "axiom": rc4}


def repair(d, bad):
    print("发现异常，开始纠偏（稳如老狗）：")
    for b in bad:
        print("  - " + b["id"] + "：" + b["why"])
    if d:
        print("重述目标：" + str(d.get("goal")))
        print("当前步骤：" + str(d.get("step")))
        print("未完成项：" + "; ".join(d.get("todo") or []))
    print("下一步动作：先补锚（pin）→ 再复跑 A1~A5 → 绿了才继续执行任务")
    run([PY, "-X", "utf8", "tools/codex-scripts/logbook.py", "append", "--kind", "change",
         "--what", "context-anchor 纠偏：红 " + str(len(bad)) + " 项 => " + "；".join(b["id"] for b in bad)])
    return 1


def main():
    ap = argparse.ArgumentParser(description="定海神针：上下文锚 + 双触手监护")
    ap.add_argument("cmd", choices=("pin", "check", "repair", "watch"))
    ap.add_argument("--goal", default="")
    ap.add_argument("--step", default="")
    ap.add_argument("--todo", default="")
    ap.add_argument("--ttl", type=int, default=3600)
    ap.add_argument("--every", type=int, default=60)
    a = ap.parse_args()
    if a.cmd == "pin":
        return pin(a.goal or "（未给目标）", a.step or "（未给步骤）", a.todo,
                   ["机检：能力面 · 执行面 · 模型面 · 压力面", "异常即自纠，不飘"])
    if a.cmd == "check":
        d, bad, rc = check(a.ttl)
        print("锚：" + ("在" if d else "缺") + " | 红 " + str(len(bad)))
        for b in bad:
            print("  RED " + b["id"] + "：" + b["why"])
        return 0 if not bad else 1
    if a.cmd == "repair":
        d, bad, rc = check(a.ttl)
        if not bad:
            print("锚健康：无需纠偏（A1~A5 全绿）")
            return 0
        return repair(d, bad)
    while True:
        d, bad, rc = check(a.ttl)
        print(time.strftime("%H:%M:%S") + " 锚=" + ("在" if d else "缺") + " 红=" + str(len(bad)))
        for b in bad:
            print("  RED " + b["id"] + "：" + b["why"])
        time.sleep(a.every)


if __name__ == "__main__":
    raise SystemExit(main())
