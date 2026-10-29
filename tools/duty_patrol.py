#!/usr/bin/env python3
"""低频真实巡检 —— 让生产观测账自然积出干净数据

为什么需要它（2026-10-28）：
  `duty_board` 的判据靠 `skill_watch` 的观测账，而账本一直被**探活**填满：
  实测 361 笔失败里 34% 是我 `--repeat 3` 的连击签名，gate_denied 217 笔里
  140 笔是我的探活。于是主脑看到的是"假积压"。

  探活已隔离到 `state/probe_store/`，但**干净窗口里一笔真实观测都没有**
  ⇒ 看板没有统计意义。

  本器负责"自然产生真实使用"：低频调几个核心位，**带真参数**，
  写进**生产账**（故意不隔离），让数据自己长出来。

纪律（免得它自己变成新的噪声源）：
  · **只调允许的位**：越权类一律不碰，绝不制造 gate_denied 噪声
  · **失败退避**：连败 2 次的位进冷却，等下一轮再说，不连撞
  · **参数是真的**：不用空 payload 硬打（那正是我之前的错）
  · **低频**：默认 5 分钟一轮，不是压测
  · 每一轮的成败都进自己的日志，可回溯

用法：
  python3 tools/duty_patrol.py --once           # 跑一轮（给验收）
  python3 tools/duty_patrol.py --interval 5     # 常驻，每 5 分钟一轮
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 🔴 故意**不**设 GBT_STORE_DIR —— 本器的观测就是要进生产账。
os.environ.pop("GBT_PROBE_ISOLATED", None)

LOG = ROOT / "logs" / "duty_patrol.jsonl"

# 巡检项：(能力位, 真参数, 说明)
# 只选**只读 + 零作用域 + 不需要授权**的位 —— 保证不会制造 gate_denied
PATROL = [
    ("health",           {},                                      "整体健康"),
    ("mirror_status",    {},                                      "镜像维度状态"),
    ("ring_context",     {"op": "stats"},                         "环形上下文读数"),
    ("context_vault",    {},                                      "上下文归档库"),
    ("brain_route",      {"intent": "看看镜像维度现在什么状态"},      "路由：镜像意图"),
    ("brain_route",      {"intent": "整体健康吗"},                   "路由：健康意图"),
    ("duty_board",       {"op": "board"},                         "值班板"),
]

COOLDOWN = {}          # cap -> 剩余冷却轮数
MAX_STREAK = 2         # 连败几次进冷却
COOLDOWN_ROUNDS = 3    # 冷却几轮


def log(rec: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _last_round() -> int:
    """从已有日志里接着数轮次。

    🔴 2026-10-28：原来每次起进程都从 1 开始 ⇒ 日志里出现两个「第1轮」，
       跨进程根本看不出"跑了多少轮"。改成读日志里最大的 round 继续。
    """
    try:
        n = 0
        for ln in open(LOG, encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                n = max(n, int(json.loads(ln).get("round") or 0))
            except Exception:                                 # noqa: BLE001
                continue
        return n
    except OSError:
        return 0


def _ensure_8790() -> str:
    """顺手看护 :8790（asyncio 批量车道）。

    🔴 2026-10-28：它会**无 Traceback 地静默消失**（SIGKILL 特征），
       根因至今没查清（iSH 的内存读数不可信）。既然查不到，就给它自愈：
       每轮巡检发现它 down 就重新拉起，并记一笔"重启过"。
       **这是兜底，不是修复** —— 账上要能看出来它重启过几次。
    """
    import subprocess as _sp
    def up():
        try:
            import socket as _s
            c = _s.socket(); c.settimeout(1.2)
            c.connect(("127.0.0.1", 8790)); c.close(); return True
        except OSError:
            return False
    if up():
        return "up"
    try:
        _sp.run(["sh", "-c",
                 "cd %s && setsid nohup python3 -u runtime/async_gate.py --port 8790 "
                 "> logs/async_gate.log 2>&1 < /dev/null &" % ROOT],
                timeout=20, capture_output=True)
        # 实测启动到端口通需要 6~15 秒，等 6 秒会误报 restart_failed
        import time as _t
        for _ in range(10):
            _t.sleep(2)
            if up():
                return "restarted"
        return "restart_failed"
    except Exception:                                         # noqa: BLE001
        return "restart_error"


def gene_tree_rules(rnd: int) -> dict:
    """树规 GENE-HT-001 自愈（每 6 轮跑一次 ≈ 30 分钟）。

    主人令 2026-10-30：任何代码进了项目树就得挂触手双向绑定、每页覆盖、页面互通。
    这条刻在 her_persona 里，但人设只是话 —— 必须有机器的闸。
    本钩子让它在巡检里常驻：每 30 分钟自愈一次（新增未绑的当场绑上），有缺口记红。
    """
    if rnd % 6 != 0:
        return {}
    try:
        r = subprocess.run([sys.executable, "-u", str(ROOT / "tools" / "gene_guard.py")],
                           capture_output=True, text=True, timeout=900, cwd=str(ROOT))
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        tail = [l.strip() for l in out.splitlines() if l.strip()][-3:]
        return {"round": rnd, "ok": r.returncode == 0, "rc": r.returncode, "tail": tail}
    except Exception as exc:                                      # noqa: BLE001
        return {"round": rnd, "ok": False, "why": "%s: %s" % (type(exc).__name__, exc)}


def one_round(rnd: int) -> dict:
    from gbt_allinone.api import run_task
    rows, ok, bad, skipped = [], 0, 0, 0
    for cap, payload, note in PATROL:
        if COOLDOWN.get(cap, 0) > 0:
            COOLDOWN[cap] -= 1
            skipped += 1
            rows.append({"cap": cap, "skipped": "冷却中", "left": COOLDOWN[cap]})
            continue
        try:
            r = run_task(cap, dict(payload))
        except Exception as exc:                              # noqa: BLE001
            rows.append({"cap": cap, "ok": False,
                         "why": "%s: %s" % (type(exc).__name__, str(exc)[:80])})
            bad += 1
            COOLDOWN[cap] = COOLDOWN[cap] + 1 if COOLDOWN.get(cap) else 0
            continue
        gr = r.get("gbt_result") or {}
        res = gr.get("result") or r.get("result") or {}
        good = (res or {}).get("ok") is not False and gr.get("status") != "denied"
        rows.append({"cap": cap, "note": note, "ok": good,
                     "status": gr.get("status")})
        if good:
            ok += 1
            COOLDOWN[cap] = 0
        else:
            bad += 1
            # 连败计数：用冷却值当连败计数，到阈值就进冷却
            COOLDOWN[cap] = COOLDOWN.get(cap, 0) + 1
            if COOLDOWN[cap] >= MAX_STREAK:
                COOLDOWN[cap] = COOLDOWN_ROUNDS
                # 主人令 2026-10-30：判断先问她的权重，不用传统办法自己拍。
                # 只在**首次**连败时问一次（进冷却后 5 轮不再问），她不在就入她的队列。
                try:
                    _q = ("巡检里 %s 连续 %d 轮失败，最后一处：%s。"
                          "这是代码问题还是环境问题？下一步该动哪里？"
                          % (cap, MAX_STREAK, str(rows[-1].get("why") or "")[:120]))
                    subprocess.run([sys.executable, str(ROOT / "tools" / "her_decide.py"), _q],
                                   capture_output=True, text=True, timeout=180, cwd=str(ROOT))
                except Exception:                                 # noqa: BLE001
                    pass
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "round": rnd,
           "ok": ok, "bad": bad, "skipped": skipped, "items": rows}
    _gt = gene_tree_rules(rnd)
    if _gt:
        rec["tree_rules"] = _gt
        if not _gt.get("ok"):
            print("    🔴 树规 GENE-HT-001 有缺口（详见 gene_guard 输出）")
    log(rec)
    return rec


def show(rec: dict) -> None:
    print("  第 %d 轮 · 成 %d · 败 %d · 跳过 %d"
          % (rec["round"], rec["ok"], rec["bad"], rec["skipped"]))
    for it in rec["items"]:
        if "skipped" in it:
            print("    ⏸ %-16s %s（剩 %s 轮）" % (it["cap"], it["skipped"], it.get("left")))
        else:
            print("    %s %-16s %s" % ("✅" if it["ok"] else "🔴", it["cap"],
                                       it.get("status") or it.get("why") or ""))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=float, default=5.0, help="分钟")
    ap.add_argument("--rounds", type=int, default=0, help="跑几轮后停（0=不停）")
    a = ap.parse_args()

    print("  ⚠ 本器故意**不隔离** —— 观测要进生产账（那正是目的）")
    print("  巡检项 %d 个 · 全部只读零作用域（不制造 gate_denied）" % len(PATROL))
    print()

    if a.once:
        show(one_round(_last_round() + 1))
        return 0

    rnd = _last_round()
    while True:
        rnd += 1
        rec = one_round(rnd)
        show(rec)
        print()
        if a.rounds and rnd >= a.rounds:
            return 0
        time.sleep(a.interval * 60)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已停")
