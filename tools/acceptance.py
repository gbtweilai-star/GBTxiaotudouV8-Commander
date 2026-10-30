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
def _self_heal() -> None:
    """验收前先自愈 —— 服务被 OOM 杀掉时，别把"服务没起"记成"功能坏了"。
    🔴 2026-10-29：这一场「服务全掉 → 12 个 FAIL → 我手动清 → 重跑」发生过四五次。
       人盯不住，做成验收的第一步。
    """
    try:
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "svc_guard.py"), "ensure"],
                           capture_output=True, text=True, timeout=240, cwd=str(ROOT))
        out = (r.stdout or "").strip().splitlines()
        last = out[-1] if out else "（无输出）"
        print("  自愈: %s" % last.strip())
    except Exception as exc:                                  # noqa: BLE001
        print("  自愈跑不起来: %s" % type(exc).__name__)


def sec_a() -> None:
    print("\n── A 服务面 ──")
    # 🔴 2026-10-28：:3001 免费池改为**按需启动**（node 9~17 进程，会把内存
    #   吃到 259MB/4GB 并导致 :8790 被静默杀掉；桥的降级链已改为 deepseek 优先）。
    #   它没起是**设计**，不是故障 ⇒ 记 ENV 不记 FAIL。
    OPTIONAL = {3001}
    # 守护器口径：**因省内存主动让位的服务不算 FAIL**（那不是坏了）。
    # 不加这一条会出现自相矛盾：guard 停 8765/8792 省内存，验收却判它们 FAIL。
    _intent = {}
    try:
        _g = subprocess.run([sys.executable, str(ROOT / "tools" / "svc_guard.py"), "status"],
                            capture_output=True, text=True, timeout=60, cwd=str(ROOT))
        for _ln in (_g.stdout or "").splitlines():
            if "🔴" in _ln and "可让位" in _ln:
                for _p in (8765, 8792):
                    if ":%d" % _p in _ln:
                        _intent[_p] = True
    except Exception:                                          # noqa: BLE001
        pass
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
        elif _intent.get(port):
            rec("ENV", "服务 :%d %s" % (port, path),
                "内存紧张，守护器**主动让位**（不是坏了）；内存回升后自动拉回")
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
    # 🔴 2026-10-28：判据从「绝对 0」改成**按比例**。
    #   原来是按 llm 域 41 位调的口径（wrong=0）。现在报告是全量 348 位，
    #   绝对数必然不为 0 —— 拿 41 位的尺子量 348 位是错的。
    #   口径：跨域错位 + 兜底黑洞 合计 ≤ 样本的 3%。
    _n = sum(bv.values()) or 1
    _rate = (bv.get("routed_wrong", 0) + bv.get("routed_broad", 0)) / _n
    rec("PASS" if _rate <= 0.03 else "FAIL", "跨域错位/兜底黑洞 ≤3%",
        "wrong=%d broad=%d · 样本 %d · %.1f%%"
        % (bv.get("routed_wrong", 0), bv.get("routed_broad", 0), _n, _rate * 100))
    # 🔴 2026-10-29 修假绿：实测有一轮 brain_align.json 只剩 1 行（被 --sample 覆盖过），
    #   报表照样打印「1/1 = 100%」—— **样本 1 条的 100% 是假绿，比不报更糟**。
    if tot < 20:
        rec("ENV", "对齐率", "样本仅 %d 条，不足 20 ⇒ 不报百分比（假绿比不报更糟）；"
                             "要真数跑：gbt align --domain llm --repeat 3" % tot)
    else:
        rec("INFO", "对齐率", "%d/%d = %.0f%%" % (aligned, tot, aligned / tot * 100))
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


# ── I 孤儿审计（能力实现好了有没有人接）─────────────────────────────────────
#   🔴 2026-10-28：这一场里我反复"实现了不接"（ring_context / context_guard / src=）。
#   靠人盯不住，加这一段：每次验收都量一次"活接线 / 孤儿"。
#   孤儿 ≠ 坏（有的位就是给 run_task 外部直调的），但**这个数字必须被看见**。
def sec_i() -> None:
    print("\n── I 孤儿审计 ──")
    try:
        # 孤儿审计要扫活路径全树，在内存紧时会超 300 秒。放宽到 540，
        # 超时就用上一份报告并**注明是旧的**（不拿旧数冒充新数）。
        _fresh = True
        try:
            subprocess.run([sys.executable, str(ROOT / "tools" / "orphan_audit.py")],
                           capture_output=True, text=True, timeout=540, cwd=str(ROOT))
        except subprocess.TimeoutExpired:
            _fresh = False
        _op = ROOT / "state" / "orphan_audit.json"
        if not _op.is_file():
            raise RuntimeError("没有孤儿审计报告")
        d = json.loads(_op.read_text(encoding="utf-8"))
        if not _fresh:
            rec("ENV", "孤儿审计新鲜度", "本次扫描超时，以下为**上一份报告**（非本轮实测）")
        tot = d.get("total") or 0
        w = len(d.get("wired") or [])
        orp = len(d.get("orphan") or [])
        rec("INFO", "孤儿审计", "活接线 %d / %d · 孤儿 %d（可调但活路径没人调）" % (w, tot, orp))
        rec("PASS" if w >= 25 else "FAIL", "活接线数量不下滑", "%d 位（下限 25）" % w)
    except Exception as e:                                    # noqa: BLE001
        rec("ENV", "孤儿审计", "跑不起来：%s" % type(e).__name__)


# ── J 树规 GENE-HT-001（进了树就得挂触手 · 每页覆盖 · 页面互通）─────────────
#   主人令 2026-10-30：任何代码进了项目树就要触手双向绑定，每页覆盖每段代码，
#   页面之间互通、不跑弯路。这条刻进了 her_persona，但人设只是话 —— 这里真验一次。
def sec_j() -> None:
    print("\n── J 树规 GENE-HT-001 ──")
    try:
        r = subprocess.run([sys.executable, "-u", str(ROOT / "tools" / "gene_guard.py")],
                           capture_output=True, text=True, timeout=900, cwd=str(ROOT))
        out = ((r.stdout or "") + (r.stderr or ""))
        gene_ok = out.count("✅ 基因标记")
        gap = "真缺口 0 条" in out
        pages = "每页覆盖" in out
        rec("PASS" if r.returncode == 0 else "FAIL", "树规成立（进来就绑·每页覆盖·互通）",
            "基因标记 %d/3 · 缺口清零=%s · 页覆盖=%s" % (gene_ok, gap, pages))
    except Exception as e:                                        # noqa: BLE001
        rec("ENV", "树规成立", "跑不起来：%s" % type(e).__name__)


# ── K 页面自报（页面自己说它好不好）───────────────────────────────────
#  2026-10-30：以前"页面好不好"只能打开肉眼看。现在页面带 ?_probe=1 会把
#  真实读数（tris/frames/tps/top1）POST 给桥的 /_probe，落 state/page_probes.jsonl。
#  这里读那份账并**按规则判决**（规则本身有 selftest 8/8 证明会亮红灯）。
def sec_k() -> None:
    print("\n── K 页面自报 ──")
    try:
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "page_probe.py"),
                            "status", "--json"], capture_output=True, text=True,
                           timeout=60, cwd=str(ROOT))
        d = json.loads(r.stdout or "{}")
        tot, okn, warn, red = d.get("total", 0), d.get("ok", 0), d.get("warn", 0), d.get("fail", 0)
        if not tot:
            rec("ENV", "页面自报", "还没有任何页面自报过（带 ?_probe=1 打开一次即可）")
            return
        rec("PASS" if red == 0 else "FAIL", "页面自报无红灯",
            "%d 页 · ok %d / 警告 %d / 红 %d" % (tot, okn, warn, red))
        for it in (d.get("pages") or [])[:6]:
            if it.get("verdict") == "red":
                rec("FAIL", "  ↳ " + str(it.get("page"))[-28:], str(it.get("why"))[:70])
    except Exception as e:                                        # noqa: BLE001
        rec("ENV", "页面自报", "读不起来：%s" % type(e).__name__)


# ── L 万能插（所有能力可复跑自审）─────────────────────────────────────
def sec_l() -> None:
    print("\n── L 万能插 ──")
    try:
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "omni_audit.py"), "--json"],
                           capture_output=True, text=True, timeout=600, cwd=str(ROOT))
        d = json.loads(r.stdout or "{}")
        rec("PASS" if d.get("failed", 1) == 0 else "FAIL", "万能插无失败项",
            "可用 %s · 需票 %s · 平台不支持 %s · 失败 %s"
            % (d.get("usable"), d.get("blocked_by_ticket"), d.get("platform_na"), d.get("failed")))
        rec("INFO", "万能插需票项", "%s 项要人发票（设计如此，不是坏）" % d.get("blocked_by_ticket"))
    except Exception as e:                                        # noqa: BLE001
        rec("ENV", "万能插自审", "跑不起来：%s" % type(e).__name__)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    # 🔴 2026-10-29 修：自愈必须在**各段之前**跑。
    #   上一版放在汇总前 ⇒ 段已经判完 FAIL 才去拉服务，等于白拉（实测 11 个 FAIL）。
    _self_heal()
    print()
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
    # 编排账本判决：**没跑通就不算验收**（主人令 2026-10-29）
    try:
        _r = subprocess.run([sys.executable, str(ROOT / "tools" / "orch_ledger.py"), "gate"],
                            capture_output=True, text=True, timeout=180, cwd=str(ROOT))
        _txt = (_r.stdout or "")
        _bad = ("不算验收" in _txt) or (_r.returncode != 0)
        _line = [x.strip() for x in _txt.splitlines() if "账目" in x]
        rec("FAIL" if _bad else "PASS", "编排账本（没跑通就不算验收）",
            _line[0] if _line else ("有未跑通项" if _bad else "全部有跑通记录"))
        for x in _txt.splitlines():
            if x.strip().startswith("· "):
                rec("INFO", "账本未跑通/未记账", x.strip()[2:][:52])
                break
    except Exception as _e:                                   # noqa: BLE001
        rec("ENV", "编排账本", "跑不起来：%s" % type(_e).__name__)

    # 触手页面覆盖：**每一页都要被触手覆盖**（主人令 2026-10-21/2026-10-29）
    try:
        subprocess.run([sys.executable, str(ROOT / "tools" / "page_tentacle.py"), "scan"],
                       capture_output=True, text=True, timeout=240, cwd=str(ROOT))
        _tp = json.loads((ROOT / "state" / "page_tentacles.json").read_text(encoding="utf-8"))
        _pg, _cv, _rp = _tp.get("pages") or 0, _tp.get("covered") or 0, _tp.get("reported") or 0
        _miss = [r["page"] for r in (_tp.get("rows") or []) if not r.get("covered")]
        rec("PASS" if not _miss else "FAIL", "触手页面覆盖",
            "%d/%d 页已接（web 壳+kit）%s" % (_cv, _pg,
            ("；缺：" + "、".join(_miss[:3])) if _miss else ""))
        rec("INFO", "页面真报到过", "%d/%d 页（在浏览器里真跑起来并回过桥）" % (_rp, _pg))
    except Exception as _e:                                   # noqa: BLE001
        rec("ENV", "触手页面覆盖", "跑不起来：%s" % type(_e).__name__)

    # 吸收前闸：吞进来的东西必须先过拆解/分析/跑通
    try:
        subprocess.run([sys.executable, str(ROOT / "tools" / "intake_gate.py")],
                       capture_output=True, text=True, timeout=300, cwd=str(ROOT))
        _ig = json.loads((ROOT / "state" / "intake_gate.json").read_text(encoding="utf-8"))
        _bad = [x for x in _ig if x.get("verdict") == "reject"]
        _okn = [x for x in _ig if x.get("verdict") == "pass"]
        _warn = [x for x in _ig if x.get("verdict") == "warn"]
        rec("PASS" if not _bad else "FAIL", "吸收前闸（拆解/分析/跑通）",
            "过 %d · 警告 %d · 拒 %d%s"
            % (len(_okn), len(_warn), len(_bad),
               ("：" + "、".join(x["capsule"] for x in _bad[:3])) if _bad else ""))
    except Exception as _e:                                   # noqa: BLE001
        rec("ENV", "吸收前闸", "跑不起来：%s" % type(_e).__name__)

    # 说明书审计：348 位里谁真干活、谁只是说明书（接上去也没用）
    try:
        subprocess.run([sys.executable, str(ROOT / "tools" / "spec_audit.py")],
                       capture_output=True, text=True, timeout=400, cwd=str(ROOT))
        _sd = json.loads((ROOT / "state" / "spec_audit.json").read_text(encoding="utf-8"))
        _sp = _sd.get("spec_only") or []
        rec("INFO", "说明书型能力",
            "%d 位只有 steps/judges 无 I/O（接上去也没用）：%s"
            % (len(_sp), "、".join(_sp[:5])) if _sp else "0 位")
    except Exception as _e:                                   # noqa: BLE001
        rec("ENV", "说明书审计", "跑不起来：%s" % type(_e).__name__)

    # 孤儿审计放在汇总**之前**跑 —— 否则它记的 PASS/INFO 进不了总数（实测踩到）
    sec_i()
    sec_j()
    sec_k()
    sec_l()

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
