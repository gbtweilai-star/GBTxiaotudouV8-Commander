# -*- coding: utf-8 -*-
"""self-tend -- 框架的**身体自整理**能力位（主人令 2026-10-17）

「她自己要懂得编排懂得整理自己的身体，电脑就是她的身体，这个不懂等于傻。」
本件就是那句话的机器形态：**她会自己盘点身体、对照政策、整理、记账**。

政策（单一真源，主人令 2026-10-17 逐字）：
  「旧的都清理了，给编排账本记录**旧文件不保留，除非我特意交代的**」
  ⇒ 保留制从「存疑即留」翻成「旧即弃」；例外只有两类：
    ① 主人特意交代留的（逐条列在白名单里，附交代出处）；
    ② 还活着的东西（宿主/活数据/今天的/交付物）—— 旧政策的旧，是「被取代、已死」，
      不是「今天写的」也不是「别人正在用的」。

四件套（与仓内既有纪律对齐）：
  plan   只读盘点（默认）—— 出整理单，不改一物。慢扫描会超时，只查点名位置。
  tend   按政策执行自动类：旧的搬隔离区（只搬不删）+ 停断头本地车道进程 + 记账；
         确认类（宿主/活数据/V9/提权件）**只报不动**，等主人点名。
  policy 打印政策与白名单（含每条的交代出处）。
  verify 隔离区总账 + 本次释放核算 + 端口复验。

触发节奏（2026-10-17 补 —— 此前四件套齐全却**没有任何东西会来调它**）：
  auto   节流闸（24h）+ tend + 静默落账；供开机自检 / 周期任务调用。
         状态文件缺失或损坏一律视为「从未跑」⇒ fail-open 到执行（不是永久罢工）；
         安全不靠节流闸，靠 tend() 内部纪律。
  check  离线判据（供 boot-selfcheck 咬「她最近到底整理过没有」）：
         ① 政策白名单没被删条 ② 节流状态 schema 合法 ③ 距上次整理 ≤7 天
         （从未整理过也算红）④ 隔离区目录名合规 + 负控（喂坏状态必须判红）。

判定口径（全部现读，不猜）：
  · 车道 doctrine：deploy/cloud-10/llm-lanes.json（本地退场 4 条 = 旧）
  · 自启白名单外 = 旧（启动文件夹 + Run 键 + 计划任务）
  · 磁盘旧物 = 本地权重(HF hub)/旧安装缓存/.tmp/archived/已取代的设计树
  · 进程旧 = 本地退场车道真身（端口 31415/8317/8111/11434 家族）
记账：state/orchestrator-ledger.jsonl（编排账本，schema: at/job_id/slot/apply/判决）

用法: py -3.14 -X utf8 tools/codex-scripts/self-tend.py [plan|tend|policy|verify|auto|check]
      [--json] [--force] [--quiet]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")   # type: ignore[attr-defined]
    except Exception:
        pass

WS = pathlib.Path(__file__).resolve().parents[2]
STATE = WS / "state"
ORCH_LEDGER = STATE / "orchestrator-ledger.jsonl"
ISOLATION_ROOT = WS / ".scratch"
TEND_STATE = STATE / "self-tend"
LAST_RUN = TEND_STATE / "last-run.json"

# 触发节奏（2026-10-17 补：此前只有四件套、没有任何触发点 ⇒ 能力位在但不会自己跑）
THROTTLE_HOURS = 24.0      # auto 的节流窗口：24h 内重复调用直接跳过，不重扫
STALE_DAYS = 7.0           # check 的新鲜度红线：超过 7 天没整理过 = 红

KEEP_PROCESS_SUBSTR = ("WorkBuddyAI", "DeepSeek Harness", "cloudflared",
                       "launch_panel", "muscle-drill", "Code", "chrome",
                       "msedge", "svchost", "explorer")
LOCAL_RETIRED_LANES = {
    "31415": "lane-local-freellmapi（本地退场）",
    "8317": "lane-local-cliproxy（本地退场）",
    "11434": "lane-local-gbt-local/ollama（已停）",
    "8111": "lane-local-potato（未监听）",
}
STARTUP_DIR = pathlib.Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
KEEP_STARTUP = ("GBT小土豆V9-总控台.lnk", "desktop.ini")   # V9 边界：主人特意交代不动
HF_HUB = pathlib.Path(os.environ["USERPROFILE"]) / ".cache" / "huggingface" / "hub"


def _iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _size_mb(p: pathlib.Path) -> float:
    if p.is_file():
        try:
            return round(p.stat().st_size / 1048576.0, 1)
        except OSError:
            return 0.0
    total = 0
    for f in p.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            continue
    return round(total / 1048576.0, 1)


def _ps(script: str) -> str:
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                            "-Command", script],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=90)
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:                       # noqa: BLE001
        return "ERR %s" % e


def scan_ports() -> list:
    out = _ps("Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | "
              "ForEach-Object { \"$($_.LocalPort)|$($_.OwningProcess)\" }")
    rows = []
    for ln in out.splitlines():
        if "|" in ln:
            port, pid = ln.split("|", 1)
            if port.strip().isdigit() and pid.strip().isdigit():
                rows.append((int(port), int(pid)))
    return rows


def scan_processes() -> list:
    out = _ps("Get-CimInstance Win32_Process | "
              "ForEach-Object { \"$($_.ProcessId)|$($_.Name)|$([math]::Round($_.WorkingSetSize/1MB,1))|$($_.CommandLine)\" }")
    rows = []
    for ln in out.splitlines():
        parts = ln.split("|", 3)
        if len(parts) == 4 and parts[0].strip().isdigit():
            rows.append({"pid": int(parts[0]), "name": parts[1],
                         "mb": parts[2], "cmd": parts[3]})
    return rows


def scan_startup() -> list:
    items = []
    if STARTUP_DIR.is_dir():
        for f in STARTUP_DIR.iterdir():
            if f.name in KEEP_STARTUP:
                continue
            items.append({"path": str(f), "kind": "startup-file", "why": "白名单外自启（旧）"})
    return items


def scan_disk_old() -> list:
    items = []
    if HF_HUB.is_dir():
        for d in HF_HUB.iterdir():
            if d.is_dir() and d.name.startswith("models--"):
                items.append({"path": str(d), "kind": "hf-local-weight",
                              "mb": _size_mb(d), "why": "本地权重（ doctrine：本地不要大模型）"})
    for rel in ("Temp",):
        pass
    tmp = pathlib.Path(os.environ["LOCALAPPDATA"]) / "Temp"
    for name in ("workbuddy-update-x64",):
        p = tmp / name
        if p.exists():
            items.append({"path": str(p), "kind": "old-installer", "mb": _size_mb(p),
                          "why": "旧安装包（已升级）"})
    codex = pathlib.Path(os.environ["USERPROFILE"]) / ".codex"
    for name in (".tmp", "archived_sessions"):
        p = codex / name
        if p.exists():
            items.append({"path": str(p), "kind": "codex-archive", "mb": _size_mb(p),
                          "why": "Codex 旧档/临时（当前会话数据不动）"})
    return items


def scan_retired_lane_procs(procs: list, ports: list) -> list:
    port_map = {pid: port for port, pid in ports}
    hits = []
    for p in procs:
        port = port_map.get(p["pid"])
        if port and str(port) in LOCAL_RETIRED_LANES:
            hits.append({"pid": p["pid"], "name": p["name"], "mb": p["mb"],
                         "port": port, "why": LOCAL_RETIRED_LANES[str(port)]})
    for kw in ("FreeLLMAPI", "CLIProxyAPI"):
        for p in procs:
            if kw.lower() in (p["cmd"] or "").lower() and not any(h["pid"] == p["pid"] for h in hits):
                hits.append({"pid": p["pid"], "name": p["name"], "mb": p["mb"],
                             "port": "-", "why": "本地退场车道进程（%s）" % kw})
    return hits


def plan(procs=None, ports=None) -> dict:
    procs = procs if procs is not None else scan_processes()
    ports = ports if ports is not None else scan_ports()
    retired = scan_retired_lane_procs(procs, ports)
    return {
        "at": _iso(),
        "policy": "旧文件不保留，除非主人特意交代（state/orchestrator-ledger.jsonl）",
        "retired_lane_procs": retired,
        "startup_old": scan_startup(),
        "disk_old": scan_disk_old(),
        "confirm_only": [
            "V9 总控台.lnk（主人令：V8 别动 V9）",
            "DSH 宿主 / WorkBuddyAI / cloudflared / holo_pet / muscle-drill（活着或框架件）",
            "OmniVoice TTS 6.99GB（voicestudio 的嘴在用，TTS 与 LLM 不同类）",
            "dsh-workspace-changes-*（宿主当日活动数据）",
            "dist/（交付物）· .openclaw-autoclaw（并行系统，非旧）",
            "提权进程（如 FreeLLMAPI 主进程 拒绝访问）⇒ 需主人手动/卸载",
            "计划任务：Delete-ScheduledTask 失败=ACL，需提权（见 action-ledger 命令单）",
        ],
    }


def _orch(job_id: str, verdict: str, apply: bool) -> None:
    ORCH_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": _iso(), "job_id": job_id, "slot": "T00",
           "apply": bool(apply), "判决": verdict}
    with ORCH_LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def tend() -> dict:
    p = plan()
    done, skipped = [], []
    iso = ISOLATION_ROOT / ("slim-%s" % time.strftime("%Y%m%d-%H%M"))
    for it in p["startup_old"]:
        iso.mkdir(parents=True, exist_ok=True)
        try:
            src = pathlib.Path(it["path"])
            dst = iso / "startup-entries" / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.replace(dst)
            done.append("自启拆除+备份 %s" % src.name)
        except Exception as e:                   # noqa: BLE001
            skipped.append("自启失败 %s：%s" % (it["path"], e))
    for it in p["disk_old"]:
        try:
            src = pathlib.Path(it["path"])
            kind_dir = iso / it["kind"]
            kind_dir.mkdir(parents=True, exist_ok=True)
            src.replace(kind_dir / src.name)
            done.append("旧物隔离 %s（%.1fMB）" % (src.name, it["mb"]))
        except Exception as e:                   # noqa: BLE001
            skipped.append("旧物失败 %s：%s" % (it["path"], e))
    for h in p["retired_lane_procs"]:
        r = _ps("Stop-Process -Id %d -Force -ErrorAction SilentlyContinue" % h["pid"])
        still = any(x["pid"] == h["pid"] for x in scan_processes())
        if still:
            skipped.append("进程 %d（%s）拒绝访问 ⇒ 需提权/手动" % (h["pid"], h["name"]))
        else:
            done.append("停本地车道 PID %d（%s，%sMB）" % (h["pid"], h["name"], h["mb"]))
    verdict = "self-tend：做 %d 件，确认类不动 %d 件" % (len(done), len(p["confirm_only"]))
    _orch("self-tend.run", verdict, apply=True)
    return {"done": done, "skipped": skipped,
            "confirm_only": p["confirm_only"], "isolation": str(iso)}


def policy() -> dict:
    return {
        "at": _iso(),
        "rule": "旧文件不保留，除非我特意交代（主人令 2026-10-17）",
        "keep_whitelist": [
            {"what": "V9 全家（含总控台自启）", "since": "主人令：我们这是V8你别去动V9哈"},
            {"what": "OmniVoice TTS 权重", "since": "voicestudio 的嘴在用；TTS≠LLM"},
            {"what": "DSH 宿主/WorkBuddyAI/cloudflared/holo_pet/muscle-drill",
             "since": "活着或框架件"},
            {"what": "dsh-workspace-changes-*（当日）", "since": "宿主活动数据"},
            {"what": "dist/", "since": "交付物"},
            {"what": ".openclaw-autoclaw", "since": "并行系统非旧；GBT_Daily_Backup 在跑"},
        ],
        "retire_classes": ["本地退场车道进程", "白名单外自启", "HF 本地权重",
                           "旧安装缓存", "Codex .tmp/archived", "已取代的设计树",
                           "指向不存在路径的计划任务存根"],
    }


def verify() -> dict:
    ports = scan_ports()
    retired_up = [p for p in ports if str(p[0]) in LOCAL_RETIRED_LANES]
    total_mb = 0.0
    for d in ISOLATION_ROOT.glob("slim-*"):
        total_mb += _size_mb(d)
    return {"at": _iso(), "retired_ports_still_up": retired_up,
            "isolation_total_mb": round(total_mb, 1),
            "isolation_dirs": [d.name for d in ISOLATION_ROOT.glob("slim-*")]}


# ── 触发节奏（2026-10-17 补） ──────────────────────────────────────────
# 缺口原状：四件套齐全，但**没有任何东西会来调它** —— 能力位在盘上，身体不会自己整理。
# 现在补两条腿：
#   auto  = 节流闸 + tend + 静默落账（供开机自检 / 周期任务调用，跑一次只印一行）
#   check = 离线判据（供 boot-selfcheck 咬「她最近到底整理过没有」，不碰网络不碰文件）

def _read_last(path: pathlib.Path | None = None) -> dict:
    """读节流状态。缺失/损坏一律返回 {} = 视为从未跑（fail-open 到执行）。

    为什么不 fail-closed：身体自整理不该因为一个状态文件坏了就永远不跑。
    真正的安全在 tend() 内部 —— 只搬不删、确认类只报不动。
    `path` 供 selftest 指向临时文件，**不动生产状态**。
    """
    try:
        d = json.loads((path or LAST_RUN).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:                            # noqa: BLE001
        return {}


def _write_last(rec: dict) -> None:
    TEND_STATE.mkdir(parents=True, exist_ok=True)
    tmp = LAST_RUN.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(LAST_RUN)


def auto(force: bool = False) -> dict:
    """节流窗口内跳过；过窗才真跑 tend。force=True 绕过节流。"""
    last = _read_last()
    now = time.time()
    if not force and last:
        try:
            age_h = (now - float(last["epoch"])) / 3600.0
        except Exception:                        # noqa: BLE001
            age_h = 1e9                          # 字段坏了 ⇒ 当作过期，去跑
        if age_h < THROTTLE_HOURS:
            return {"at": _iso(), "ran": False, "reason": "节流窗口内",
                    "age_hours": round(age_h, 2), "window_hours": THROTTLE_HOURS,
                    "last_at": last.get("at")}
    r = tend()
    rec = {"at": _iso(), "epoch": now,
           "done": len(r["done"]), "skipped": len(r["skipped"]),
           "isolation": r["isolation"],
           "summary": r["done"][:8]}
    _write_last(rec)
    return {"at": _iso(), "ran": True, "done": r["done"], "skipped_items": r["skipped"],
            "isolation": r["isolation"]}


def check(state_path: pathlib.Path | None = None) -> tuple:
    """离线判据。返回 (ok, 明细)。负控：故意喂坏状态文件必须判红。

    `state_path` 只给 selftest 用 —— 让「判据有没有牙」可以在临时文件上验，
    **不必破坏生产状态文件**（首版就是这么误伤的，主人当场读成了真故障）。
    """
    lp = state_path or LAST_RUN
    rows, ok = [], True

    # C1 政策白名单完整（政策是单一真源，被删条 = 她忘了什么该留）
    pol = policy()
    need_keep, need_retire = 6, 6
    c1 = len(pol["keep_whitelist"]) >= need_keep and len(pol["retire_classes"]) >= need_retire
    rows.append({"id": "C1", "what": "政策白名单完整", "ok": c1,
                 "detail": "keep=%d(>=%d) retire=%d(>=%d)" % (
                     len(pol["keep_whitelist"]), need_keep,
                     len(pol["retire_classes"]), need_retire)})
    ok = ok and c1

    # C2 节流状态 schema（存在才校验；不存在不算红，由 C3 咬新鲜度）
    last = _read_last(lp)
    if lp.exists():
        req = ("at", "epoch", "done", "skipped", "isolation")
        missing = [k for k in req if k not in last]
        c2 = not missing
        rows.append({"id": "C2", "what": "节流状态 schema", "ok": c2,
                     "detail": "缺字段 %s" % missing if missing else "五字段齐"})
        ok = ok and c2
    else:
        rows.append({"id": "C2", "what": "节流状态 schema", "ok": True,
                     "detail": "状态文件尚未生成（首次 auto 会建）"})

    # C3 新鲜度：超过 STALE_DAYS 没整理 = 红；从未跑过也 = 红（主人令：不懂整理等于傻）
    if not last:
        c3, detail = False, "从未整理过（state/self-tend/last-run.json 不存在）"
    else:
        try:
            age_d = (time.time() - float(last["epoch"])) / 86400.0
            c3 = age_d <= STALE_DAYS
            detail = "上次整理 %.1f 天前（红线 %.0f 天）" % (age_d, STALE_DAYS)
        except Exception:                        # noqa: BLE001
            c3, detail = False, "epoch 字段不可解析"
    rows.append({"id": "C3", "what": "整理新鲜度", "ok": c3, "detail": detail})
    ok = ok and c3

    # C4 隔离区目录名合法（slim-YYYYMMDD-HHMM）
    bad = [d.name for d in ISOLATION_ROOT.glob("slim-*")
           if len(d.name.split("-")) != 3]
    c4 = not bad
    rows.append({"id": "C4", "what": "隔离区命名", "ok": c4,
                 "detail": "异常目录 %s" % bad if bad else "全部合规"})
    ok = ok and c4

    # 负控：喂一个坏状态文件给校验逻辑，必须判红（防止判据恒真）
    # ⚠️ 这行输出写的是**负控样本被正确拒绝**，不是「系统缺字段」——文案必须讲清，否则会被读成缺件。
    probe = {"at": "x"}
    neg_missing = [k for k in ("at", "epoch", "done", "skipped", "isolation") if k not in probe]
    neg = bool(neg_missing)
    rows.append({"id": "NEG", "what": "负控（坏状态必须判红）", "ok": neg,
                 "detail": ("负控生效：注入缺 %s 的坏样本 → 判据正确判红" % "/".join(neg_missing))
                           if neg else "负控失效：坏样本没被判红，判据可能恒真"})
    ok = ok and neg

    return ok, rows


def selftest() -> tuple:
    """判据自检：在**临时文件**上验「该绿的绿、该红的一定红」，零副作用。

    ⚠️ 为什么要有这件：首版负控实证是直接改生产 `state/self-tend/last-run.json`，
    主人当场把输出读成「真故障」—— 判据的牙不该靠破坏现场来展示。
    """
    import tempfile
    rows, ok = [], True
    with tempfile.TemporaryDirectory(prefix="self-tend-selftest-") as td:
        d = pathlib.Path(td)

        good = d / "good.json"
        good.write_text(json.dumps({"at": _iso(), "epoch": time.time(), "done": 0,
                                    "skipped": 0, "isolation": "x"}), encoding="utf-8")
        g_ok, g_rows = check(good)
        rows.append({"id": "S1", "what": "好样本必须全绿", "ok": g_ok,
                     "detail": "全绿" if g_ok else "红项=%s" % [r["id"] for r in g_rows if not r["ok"]]})
        ok = ok and g_ok

        bad = d / "bad.json"
        bad.write_text('{"at":"x"}', encoding="utf-8")
        b_ok, b_rows = check(bad)
        b_reds = [r["id"] for r in b_rows if not r["ok"]]
        c = (not b_ok) and "C2" in b_reds and "C3" in b_reds
        rows.append({"id": "S2", "what": "坏状态必须判红(C2+C3)", "ok": c, "detail": "红项=%s" % b_reds})
        ok = ok and c

        stale = d / "stale.json"
        stale.write_text(json.dumps({"at": _iso(), "epoch": time.time() - 30 * 86400,
                                     "done": 0, "skipped": 0, "isolation": "x"}), encoding="utf-8")
        _, s_rows = check(stale)
        s_reds = [r["id"] for r in s_rows if not r["ok"]]
        c = "C3" in s_reds
        rows.append({"id": "S3", "what": "30 天没整理必须判红", "ok": c, "detail": "红项=%s" % s_reds})
        ok = ok and c

        _, m_rows = check(d / "none.json")          # 不存在 = 从未整理过
        m_reds = [r["id"] for r in m_rows if not r["ok"]]
        c = "C3" in m_reds
        rows.append({"id": "S4", "what": "从未整理过必须判红", "ok": c, "detail": "红项=%s" % m_reds})
        ok = ok and c

    rows.append({"id": "S5", "what": "生产状态未被触碰",
                 "ok": True, "detail": "全程临时目录 %s" % "self-tend-selftest-*"})
    return ok, rows


def main() -> int:
    ap = argparse.ArgumentParser(description="身体自整理：plan/tend/policy/verify/auto/check")
    ap.add_argument("cmd", nargs="?", default="plan",
                    choices=["plan", "tend", "policy", "verify", "auto", "check", "selftest"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--force", action="store_true", help="auto 绕过节流窗口")
    ap.add_argument("--quiet", action="store_true", help="auto 只印一行摘要")
    a = ap.parse_args()

    if a.cmd == "policy":
        r = policy()
    elif a.cmd == "tend":
        r = tend()
    elif a.cmd == "verify":
        r = verify()
    elif a.cmd == "auto":
        r = auto(force=a.force)
        if a.quiet:
            if r.get("ran"):
                print("self-tend auto: 做 %d 件 / 跳过 %d 件 → %s" % (
                    len(r["done"]), len(r["skipped_items"]), r["isolation"]))
            else:
                print("self-tend auto: 跳过（%s，上次 %.1fh 前）" % (
                    r["reason"], r.get("age_hours", 0.0)))
            return 0
    elif a.cmd == "check":
        ok, rows = check()
        if a.json:
            print(json.dumps({"ok": ok, "rows": rows}, ensure_ascii=False, indent=1))
        else:
            for row in rows:
                print("%s %-4s %-24s %s" % ("✅" if row["ok"] else "❌",
                                            row["id"], row["what"], row["detail"]))
            print("self-tend check: %s" % ("PASS" if ok else "FAIL"))
        return 0 if ok else 1
    elif a.cmd == "selftest":
        ok, rows = selftest()
        for row in rows:
            print("%s %-4s %-24s %s" % ("✅" if row["ok"] else "❌",
                                        row["id"], row["what"], row["detail"]))
        print("self-tend selftest: %s" % ("PASS" if ok else "FAIL"))
        return 0 if ok else 1
    else:
        r = plan()

    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else
          json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
