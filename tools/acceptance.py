#!/usr/bin/env python3
"""闭环验收 —— 把所有建好的东西一次验完，逐项给证据

设计原则：
  · 每项要么 PASS 要么 FAIL，**没有"大概行"**
  · 每项都带**现场读数**作证据（不是"我实现过"）
  · 环境限制项单独列（不冒充 PASS，也不当 FAIL）
  · 退出码：全 PASS=0，有 FAIL=1

覆盖：
  A 服务面    8 路端口 + HTTP 实测
  B 环形上下文 有界 / 跨进程恢复 / 秒查
  C 上下文守护 异常检测 + 确定性纠错 + 并入主脑队列
  D 主脑队列   三源同表 / 排布 / 只销已证明
  E 验证层     reality 面（端口/文件）四例
  F 路由       llm 域对齐（自称谓/词表/语义 三段）
  G 镜像       shape→scan→plan→simulate→parity→verify
  H 巡检       在跑且账在长

用法：
  python3 tools/acceptance.py            # 全跑
  python3 tools/acceptance.py --quick    # 跳过慢项（F/G）
"""
from __future__ import annotations

import argparse
import json
import pathlib
import socket
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RESULTS: list[tuple[str, str, str]] = []   # (状态, 项目, 证据)


def rec(state: str, item: str, ev: str) -> None:
    RESULTS.append((state, item, ev))
    print("  %-6s %-38s %s" % (state, item, ev[:64]), flush=True)


def tcp(port: int, t: float = 2.0) -> bool:
    s = socket.socket(); s.settimeout(t)
    try:
        s.connect(("127.0.0.1", port)); return True
    except OSError:
        return False
    finally:
        s.close()


def http(port: int, path: str = "/", t: float = 8.0):
    s = socket.socket(); s.settimeout(t)
    try:
        s.connect(("127.0.0.1", port))
        s.sendall(("GET %s HTTP/1.0\r\nHost: x\r\nConnection: close\r\n\r\n"
                   % path).encode())
        b = b""
        while True:
            c = s.recv(65536)
            if not c:
                break
            b += c
        first = b.split(b"\r\n")[0].decode("latin-1")
        return ("200" in first), first
    except OSError as e:
        return False, type(e).__name__
    finally:
        s.close()


def rt(cap: str, payload: dict | None = None) -> dict:
    from gbt_allinone.api import run_task
    r = run_task(cap, payload or {})
    return (r.get("gbt_result") or {}).get("result") or r.get("result") or {}


# ── A 服务面 ────────────────────────────────────────────────────────────────
def sec_a() -> None:
    print("\n── A 服务面 ──")
    # 🔴 2026-10-28：:3001 免费池改为**按需启动**（node 9~17 进程，会把内存
    #   吃到 259MB/4GB 并导致 :8790 被静默杀掉；桥的降级链已改为 deepseek 优先）。
    #   它没起是**设计**，不是故障 ⇒ 记 ENV 不记 FAIL。
    OPTIONAL = {3001}
    lanes = [(3001, "/api/ping"), (8080, "/index.html"), (8791, "/health"),
             (8790, "/health"), (8765, "/api/state"), (8792, "/health")]
    ok = 0
    for port, path in lanes:
        good, info = http(port, path)
        ok += 1 if good else 0
        if good:
            rec("PASS", "服务 :%d %s" % (port, path), info)
        elif port in OPTIONAL:
            rec("ENV", "服务 :%d %s" % (port, path),
                "按需启动，未起是设计（省内存）；要它用 FORCE_FLR=1")
        else:
            rec("FAIL", "服务 :%d %s" % (port, path), info)
    rec("PASS" if ok >= len(lanes) - len(OPTIONAL) else "FAIL",
        "服务面合计", "%d/%d 通（:3001 按需）" % (ok, len(lanes)))
    rec("ENV", ":1234 A19", "离线（App 内开关，只能人开；哨兵在等）"
        if not tcp(1234) else "在线")


# ── B 环形上下文 ────────────────────────────────────────────────────────────
def sec_b() -> None:
    print("\n── B 环形上下文 ──")
    from gbt_allinone.llm.ring_context import RingContext
    rc = RingContext(name="acc_ring", window_chars=1200)
    for i in range(40):
        rc.push("user", "验收第%d条" % i * 6)
    st = rc.stats()
    rec("PASS" if st["window_chars"] <= st["window_budget"] else "FAIL",
        "窗口有界", "%d ≤ %d" % (st["window_chars"], st["window_budget"]))
    rec("PASS" if rc.recall("验收第3条", k=2).get("ok") else "FAIL",
        "秒查（挤出仍可捞）", "recall ok")
    code = ('import sys; sys.path.insert(0,".")\n'
            'from gbt_allinone.llm.ring_context import RingContext\n'
            'b=RingContext(name="acc_ring", window_chars=1200)\n'
            'print(len(b.window()))\n')
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, cwd=str(ROOT)).stdout.strip()
    n = int(out or 0)
    rec("PASS" if n > 0 else "FAIL", "跨进程窗口恢复", "新进程恢复 %d 条" % n)


# ── C 上下文守护 ────────────────────────────────────────────────────────────
def sec_c() -> None:
    print("\n── C 上下文守护 ──")
    out = subprocess.run([sys.executable, "-u", "tools/context_guard.py",
                          "--selftest", "--name", "acc_guard", "--budget", "3000"],
                         capture_output=True, text=True, cwd=str(ROOT), timeout=300)
    log = out.stdout
    rec("PASS" if "触发异常" in log else "FAIL", "异常检测", "触发 near_overflow"
        if "触发异常" in log else "未触发")
    rec("PASS" if "纠错位(规则表)" in log else "FAIL", "确定性纠错", "规则表动作已执行"
        if "纠错位(规则表)" in log else "无")
    rec("PASS" if "已并入主脑队列" in log else "FAIL", "并入主脑队列",
        "severity 已记" if "已并入主脑队列" in log else "未入队")
    rec("PASS" if "老内容仍秒查得到: True" in log else "FAIL", "挤出不丢",
        "秒查 True" if "老内容仍秒查得到: True" in log else "见日志")


# ── D 主脑队列 ──────────────────────────────────────────────────────────────
def sec_d() -> None:
    print("\n── D 主脑队列 ──")
    q = rt("llm_watch", {"op": "queue"})
    rows = q.get("rows") or []
    kinds = {r.get("kind") for r in rows}
    rec("PASS" if len(kinds) >= 2 else "FAIL", "多源同表",
        "来源 %s" % sorted(kinds))
    out = subprocess.run([sys.executable, "-u", "tools/brain_attention.py"],
                         capture_output=True, text=True, cwd=str(ROOT), timeout=180)
    rec("PASS" if "按严重度排序" in out.stdout else "FAIL", "排布看板",
        "分级输出" if "按严重度排序" in out.stdout else "无")


# ── E 验证层 ────────────────────────────────────────────────────────────────
def sec_e() -> None:
    print("\n── E 验证层（reality 面）──")
    cases = [("面板后端 :8765 应该在线", True),
             ("文件 tools/brain_align.py 存在", True),
             ("端口 :9999 应该在线", False),
             ("随便一句话无可验证面", None)]
    ok = 0
    for exp, want in cases:
        r = rt("brain_verify", {"expectation": exp})
        good = (want is None and r.get("verdict") == "unverified_no_surface") or \
               (want is not None and r.get("ok") == want)
        ok += 1 if good else 0
    rec("PASS" if ok == len(cases) else "FAIL", "四种判据全对",
        "%d/%d" % (ok, len(cases)))
    rec("ENV", "vision 面", "不可用（非交互桌面）—— 已由 reality 面替代")


# ── F 路由对齐 ──────────────────────────────────────────────────────────────
def sec_f() -> None:
    print("\n── F 路由（llm 域对齐）──")
    p = ROOT / "state" / "brain_align.json"
    if not p.is_file():
        rec("SKIP", "对齐报告", "无 state/brain_align.json")
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    bv = d.get("by_verdict") or {}
    tot = sum(bv.values())
    aligned = bv.get("aligned", 0)
    bad = bv.get("routed_wrong", 0) + bv.get("routed_broad", 0)
    rec("PASS" if bad == 0 else "FAIL", "无跨域错位/兜底黑洞",
        "wrong=%d broad=%d" % (bv.get("routed_wrong", 0), bv.get("routed_broad", 0)))
    rec("INFO", "对齐率", "%d/%d = %.0f%%" % (aligned, tot, aligned / tot * 100 if tot else 0))
    for r in (d.get("rows") or []):
        if r.get("verdict") == "routed_parent":
            rec("ENV", "同域近似（素材分不开）", "%s → %s"
                % (r.get("name"), r.get("routed_to")))


# ── G 镜像流程 ──────────────────────────────────────────────────────────────
def sec_g() -> None:
    print("\n── G 镜像流程 ──")
    out = subprocess.run([sys.executable, "-u", "tools/mirror_panel.py", "--run"],
                         capture_output=True, text=True, cwd=str(ROOT), timeout=600)
    log = out.stdout
    # 🔴 2026-10-28：原来按「4 个空格 + 名字」切分，而 mirror_panel 的 show()
    #   实际是「2 个空格 + %-9s」⇒ 切不中，五个项全被错判成 FAIL。
    #   改成按行正则解析：^\s*<op>\s+ok=(\w+)
    import re as _re
    parsed: dict[str, str] = {}
    for ln in log.splitlines():
        m = _re.match(r"[ \t]*(\w+)[ \t]+ok=(\w+)", ln)
        if m:
            parsed[m.group(1)] = m.group(2)
    for key, name in (("scan", "① scan 五项体检"), ("plan", "③ plan"),
                      ("simulate", "④ simulate"), ("parity", "⑤ parity"),
                      ("verify", "⑥ verify 现实面")):
        v = parsed.get(key)
        rec("PASS" if v == "True" else "FAIL", "镜像 " + name,
            "ok=%s" % (v or "未输出"))
    rec("PASS" if "现实全过" in log else "FAIL", "镜像放行前现实全过",
        "可以进 release" if "现实全过" in log else "未过")


# ── H 巡检 ──────────────────────────────────────────────────────────────────
def sec_h() -> None:
    print("\n── H 巡检 ──")
    running = subprocess.run(["pgrep", "-f", "duty_patrol.py"],
                             capture_output=True, text=True).returncode == 0
    rec("PASS" if running else "FAIL", "巡检在跑", "进程在" if running else "没跑")
    lp = ROOT / "logs" / "duty_patrol.jsonl"
    if lp.is_file():
        rows = [json.loads(x) for x in lp.read_text(encoding="utf-8").splitlines() if x.strip()]
        rec("INFO", "巡检已跑轮次", "%d 轮" % len(rows))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    print("═══ 闭环验收 · %s ═══" % time.strftime("%Y-%m-%d %H:%M:%S"))
    for fn in (sec_a, sec_b, sec_c, sec_d, sec_e):
        try:
            fn()
        except Exception as exc:                              # noqa: BLE001
            rec("FAIL", fn.__name__, "%s: %s" % (type(exc).__name__, str(exc)[:60]))
    if not a.quick:
        for fn in (sec_f, sec_g, sec_h):
            try:
                fn()
            except Exception as exc:                          # noqa: BLE001
                rec("FAIL", fn.__name__, "%s: %s" % (type(exc).__name__, str(exc)[:60]))
    from collections import Counter
    c = Counter(s for s, _, _ in RESULTS)
    print("\n═══ 汇总 · 用时 %.1fs ═══" % (time.time() - t0))
    for k in ("PASS", "FAIL", "ENV", "SKIP", "INFO"):
        if c.get(k):
            print("  %-6s %d" % (k, c[k]))
    fails = [x for x in RESULTS if x[0] == "FAIL"]
    if fails:
        print("\n  未过项:")
        for s, i, e in fails:
            print("    🔴 %-38s %s" % (i, e[:70]))
    return 0 if not fails else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已停")
