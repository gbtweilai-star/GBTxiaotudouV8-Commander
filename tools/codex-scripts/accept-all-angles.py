# -*- coding: utf-8 -*-
"""六视角验收 · 一张表一个门（2026-09-23 立）。

## 为什么要这件

Owner 要「以多角度测试验收：用户角度、开发者角度，等等一系列角度」。
**六个角度不能靠"我看过了"** —— 每个角度都要有**可跑的命令**与**可判的结论**。
本件把六个角度跑成**一张表 + 一个退出码**。

## 三态与退出码（与 `desktop-shell-guard.py` 同一套约定）

    PASS     已证实成立
    FAIL     已证实不成立          ⇒ 退出码 1（**任一条 FAIL 就不算验收通过**）
    PENDING  **还没做/还没条件做**  ⇒ 退出码 2（⚠️ **不算 PASS**）
    SKIP     这一轮按参数没跑（如 `--full` 才跑的全量测试）—— 与 PENDING 分开记，
             因为"没跑"和"跑了没过"是两件事
    全 PASS ⇒ 退出码 0

## 六个角度各看什么（每条都给"怎么复现"）

    用户    人一句话能不能落到真东西上（本地工具面排第一 + 每条带可达性）
    开发者  改坏了没有（钉子 + 契约测试；`--full` 才跑全量 9 分钟那套）
    运维    机器面（`quick_scan` 七面 + 安全面；P0/P1 计数；退出码语义）
    安全    门拦不拦得住 + **外面还有没有未决的 P0**（两者都要报，不许只报绿的那半）
    审计    每个动作留没留痕、留得对不对（`synced`/`synced_entry` 覆盖 · 未收步 · brainless_ratio）
    交付    装机面（清单/守卫/打包回执）—— 本阶段预期是 PENDING，**如实 PENDING，不粉饰**

## 用法

    py -3.14 tools/codex-scripts/accept-all-angles.py
    py -3.14 tools/codex-scripts/accept-all-angles.py --full          # 含全量测试（约 9 分钟）
    py -3.14 tools/codex-scripts/accept-all-angles.py --json out.json
    py -3.14 tools/codex-scripts/accept-all-angles.py --only 用户,审计
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
PY = sys.executable
ANGLES = ("用户", "开发者", "运维", "安全", "审计", "交付")


def _run(argv, timeout, env_extra=None) -> tuple:
    """跑一条命令。返回 `(rc, out, err, elapsed)`。**绝不过 shell。**"""
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    if env_extra:
        env.update(env_extra)
    t0 = time.time()
    try:
        p = subprocess.run(argv, cwd=str(ROOT), shell=False, capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, env=env)
        return p.returncode, p.stdout or "", p.stderr or "", time.time() - t0
    except subprocess.TimeoutExpired:
        return 124, "", "超时 >%ds（已掐断）" % timeout, time.time() - t0


# ── 用户 ────────────────────────────────────────────────────────────────────
def angle_user() -> dict:
    rc, out, err, dt = _run([PY, str(ROOT / "tools" / "codex-scripts" / "omni.py"),
                             "ask", "扫一下这台电脑有没有病毒木马后门"], 120)
    if rc != 0:
        return {"state": "FAIL", "why": "omni ask 退出码 %d：%s" % (rc, (err or out)[:160]),
                "how": 'py -3.14 tools/codex-scripts/omni.py ask "<一句话>"'}
    # 判据①：本地工具面必须排在最前，且第一条是真扫描器
    head_local = out.split("── 走本地工具面")[1] if "── 走本地工具面" in out else ""
    first = re.search(r"^\s+\[[\d.]+\]\s+(\S+)", head_local, re.M)
    tools_ok = bool(first) and first.group(1) in (
        "quick_scan", "host_security_scan", "deep_scan", "exec-deck", "media_flow")
    # 判据②：每个候选都要带可达性（R-A：落点必须报可达性）
    reach_ok = "✅ 可达" in out or "🔴" in out
    if not (tools_ok and reach_ok):
        return {"state": "FAIL",
                "why": "本地工具面第一条=%s（期望真扫描器）；可达性标记=%s"
                       % (first.group(1) if first else "无", reach_ok),
                "how": 'py -3.14 tools/codex-scripts/omni.py ask "<一句话>"'}
    return {"state": "PASS", "why": "本地工具面第一条=%s 且每条带可达性" % first.group(1),
            "how": 'py -3.14 tools/codex-scripts/omni.py ask "扫一下这台电脑有没有病毒木马后门"',
            "elapsed_s": round(dt, 1)}


# ── 开发者 ──────────────────────────────────────────────────────────────────
_FAST_TESTS = ["gbt_allinone/tests/test_sync_exec_nail.py",
               "gbt_allinone/tests/test_api_probe.py",
               "gbt_allinone/tests/test_code_patch.py",
               "gbt_allinone/tests/test_git_repo.py",
               "gbt_allinone/tests/test_capability_registry.py",
               "gbt_allinone/tests/test_scan_contracts.py"]


def _dev_once(full: bool) -> dict:
    cmd = [PY, "-m", "pytest"]
    targets = ["gbt_allinone/tests", "holo_pet/tests"] if full else _FAST_TESTS
    cmd += targets + ["-q", "--tb=line", "-p", "no:cacheprovider", "--timeout=900"]
    rc, out, err, dt = _run(cmd, 1200 if full else 300,
                            env_extra={"GBT_STORE_DIR": str(Path(tempfile.gettempdir())
                                                            / "gbt_accept_store")})
    m = re.search(r"(\d+) passed", out)
    f = re.search(r"(\d+) failed", out)
    passed, failed = int(m.group(1)) if m else 0, int(f.group(1)) if f else 0
    failed_names = re.findall(r"^FAILED\s+(\S+)", out, re.M)[:6]
    return {"rc": rc, "passed": passed, "failed": failed, "names": failed_names,
            "elapsed_s": round(dt, 1),
            "how": "py -3.14 -m pytest %s -q" % " ".join(targets)}


def angle_dev(full: bool) -> dict:
    """开发者视角。**失败要复跑一次确认** —— 因为本仓有并发写者。

    🔴 本轮实测：快集首跑报 `2 failed`，同一套复跑 **82 passed** ——
    那 2 条红是**另一个会话正在改文件**时读到的，不是真坏。
    ⇒ 立第四态 **FLAKY**（首跑红、复跑绿）：**不许静默算 PASS**（那会把并发干扰洗白），
    也不算 FAIL（那会天天误报）；它**必须报出来给人看**，退出码与 PENDING 同级（2）。
    """
    first = _dev_once(full)
    if first["failed"] == 0 and first["rc"] == 0:
        return {"state": "PASS",
                "why": "%s：%d passed / 0 failed%s"
                       % ("全量" if full else "快集（钉子+契约）", first["passed"],
                          "" if full else "（本轮只跑快集；全量要加 --full）"),
                "how": first["how"], "elapsed_s": first["elapsed_s"]}
    second = _dev_once(full)
    if second["failed"] == 0 and second["rc"] == 0:
        return {"state": "FLAKY",
                "why": "**首跑红、复跑绿**（首跑 %d failed：%s ⇒ 复跑 %d passed）—— "
                       "本仓有**并发写者**时会出现这种读数；**不许当 PASS，要人看一眼**"
                       % (first["failed"], ",".join(first["names"]) or "?",
                          second["passed"]),
                "how": first["how"], "elapsed_s": round(first["elapsed_s"] + second["elapsed_s"], 1)}
    return {"state": "FAIL",
            "why": "两次都红：首跑 %d failed · 复跑 %d failed（%s）"
                   % (first["failed"], second["failed"],
                      ",".join(second["names"]) or "未给出用例名"),
            "how": first["how"], "elapsed_s": round(first["elapsed_s"] + second["elapsed_s"], 1)}


# ── 运维 ────────────────────────────────────────────────────────────────────
def angle_ops() -> dict:
    rc, out, err, dt = _run([PY, str(ROOT / "tools" / "codex-scripts" / "quick_scan.py"),
                             "--json", str(Path(tempfile.gettempdir()) / "gbt-accept-scan.json")],
                            300)
    line = next((li for li in out.splitlines() if li.startswith("故障：")), "")
    if not line:
        return {"state": "FAIL", "why": "速扫没给出故障行（rc=%d）：%s" % (rc, (err or out)[:160]),
                "how": "py -3.14 tools/codex-scripts/quick_scan.py"}
    m = re.search(r"P0=(\d+)\s+P1=(\d+)\s+P2=(\d+)", line)
    p0, p1 = (int(m.group(1)), int(m.group(2))) if m else (-1, -1)
    if rc == 3:
        return {"state": "FAIL", "why": "速扫自身出错（退出码 3）", "how": "py -3.14 tools/codex-scripts/quick_scan.py"}
    # 退出码语义（0 只有P2 / 1 有P0 / 2 有P1）：有 P0 ⇒ 这是**常态红**，不是本件判它坏
    return {"state": "PASS",
            "why": "速扫跑通：P0=%d P1=%d P2=%s（退出码 %d）—— 数字是**读数**，不是本条的判决"
                   % (p0, p1, m.group(3) if m else "?", rc),
            "how": "py -3.14 tools/codex-scripts/quick_scan.py",
            "open_p0": p0, "open_p1": p1, "elapsed_s": round(dt, 1)}


# ── 安全 ────────────────────────────────────────────────────────────────────
def angle_security() -> dict:
    # 🔴 现读校准（本轮实测）：`five-dim.py cap` 的输出是 **JSON**（`"passed": 5, "total": 5`），
    #    不是 `passed 5 / total 5` 那种文本 —— 第一版按印象写正则，永远匹不上。
    #    加 `--full` 是因为默认会把 result 截到 1500 字，截断后解析会缺字段。
    rc, out, err, dt = _run([PY, str(ROOT / "tools" / "codex-scripts" / "five-dim.py"),
                             "cap", "sec_defenses", "--full"], 300)
    body, passed, total = {}, None, None
    try:
        body = json.loads(out[out.index("{"):out.rindex("}") + 1])
        res = body.get("result") or {}
        passed, total = res.get("passed"), res.get("total")
    except Exception:                                            # noqa: BLE001
        pass
    ok_all = (passed is not None and total is not None and passed == total
              and str(body.get("status")) == "ok")
    # 外面那份未决 P0 也必须看见 —— 只报绿的那半等于替问题遮羞
    scan_json = Path(tempfile.gettempdir()) / "gbt-accept-scan.json"
    open_p0 = []
    try:
        d = json.loads(scan_json.read_text(encoding="utf-8"))
        # 🔴 字段名现读是 **`sev`**（不是 severity）—— 按印象写会静默取到空列表，
        #    于是"外面无未决 P0"变成**假绿**。这条踩过。
        open_p0 = [f.get("code") for f in d.get("faults", []) if f.get("sev") == "P0"]
    except Exception:                                            # noqa: BLE001
        pass
    if not ok_all:
        return {"state": "FAIL",
                "why": "sec_defenses 不是全绿：passed=%s total=%s status=%s"
                       % (passed, total, body.get("status")),
                "how": "py -3.14 tools/codex-scripts/five-dim.py cap sec_defenses --full"}
    if open_p0:
        return {"state": "PENDING",
                "why": "框架自检 %s/%s 全绿，**但外面还有未决 P0 需主人处置**：%s"
                       % (passed, total, ", ".join(open_p0[:4])),
                "how": "py -3.14 tools/codex-scripts/quick_scan.py",
                "elapsed_s": round(dt, 1)}
    return {"state": "PASS", "why": "sec_defenses %s/%s 全绿 且外面无未决 P0" % (passed, total),
            "how": "py -3.14 tools/codex-scripts/five-dim.py cap sec_defenses --full"}


# ── 审计 ────────────────────────────────────────────────────────────────────
def angle_audit() -> dict:
    """审计视角：**口径一律取自 `exec-deck.py`，本件不自己再算一套**。

    🔴 本轮连踩两回，值得写下来：
      ① 第一版拿**全史**算"多少条 call 没带 synced" ⇒ 报 **133,915 条假失败**
         —— `synced` 是 2026-09-22 才加的字段，判据必须知道"这个字段从哪一刻起才有"。
      ② 第二版改成"按**字段引入时刻**切窗口"⇒ 仍不对：字段引入（09-22 18:00）
         **不等于** `auto_envelope` 落地（09-23 06:xx）⇒ 窗口里 699 条"真漏"绝大多数是**改动前**的。
      ⇒ 正解不是再写第三个窗口，而是**复用已经算好那个窗口的地方**（`exec-deck` 的"改动后窗口"
        按 `synced_entry` 存在与否切）。**同一件事只留一套口径** —— 这是本仓最贵的教训。
    """
    store = ROOT / "gbt_allinone" / "store"
    audit = store / "audit.jsonl"
    if not audit.is_file():
        return {"state": "FAIL", "why": "没有审计账本 %s" % audit}

    # ① 完整性（这一条是 exec-deck 不做的）：字段引入后不许再漏记
    intro, post_calls, missing = None, 0, 0
    with audit.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"call"' not in line:
                continue
            try:
                e = json.loads(line)
            except Exception:                                    # noqa: BLE001
                continue
            m = e.get("meta") or {}
            if e.get("event") != "call" or not m.get("kind"):
                continue
            has = "synced" in m
            ts = float(e.get("ts") or 0)
            if has and intro is None:
                intro = ts
            if intro is not None and ts >= intro:
                post_calls += 1
                if not has:
                    missing += 1
    if intro is None:
        return {"state": "PENDING", "why": "账本里一条都没带 synced ⇒ 这把尺子从没装上过"}

    # ② 覆盖与欠账 —— **调 exec-deck 拿**（口径单一）
    tmp = Path(tempfile.gettempdir()) / "gbt-accept-deck.json"
    rc, out, err, dt = _run([PY, str(ROOT / "tools" / "codex-scripts" / "exec-deck.py"),
                             "--json", str(tmp)], 180)
    tagged = {"inside": 0, "outside": 0, "entry": {}}
    open_n, attention, ratio = None, [], None
    try:
        d = json.loads(tmp.read_text(encoding="utf-8"))
        tagged = d.get("tagged") or tagged
        open_n = ((d.get("blocks") or {}).get("C") or {}).get("open_n")
        attention = d.get("attention") or []
        ratio = (((d.get("blocks") or {}).get("A") or {}).get("data") or {}).get("brainless_ratio")
    except Exception as e:                                       # noqa: BLE001
        return {"state": "FAIL", "why": "调 exec-deck 取口径失败：%s" % str(e)[:120],
                "how": "py -3.14 tools/codex-scripts/exec-deck.py"}

    tg_n = tagged.get("inside", 0) + tagged.get("outside", 0)
    # 🔴 `off` 要**剔出去**：那是显式负对照（`--no-envelope`），是**设计**不是漏。
    #    `exec-deck` 已经把 `off` 记在 `tagged.entry.off` 里（口径还在它那边，本件只做减法）。
    off_n = int((tagged.get("entry") or {}).get("off", 0) or 0)
    truly_out = max(0, int(tagged.get("outside", 0)) - off_n)
    why = ("字段引入 %s 后 call %d 条 · 其中缺 synced **%d** 条 ｜ "
           "**改动后窗口**（按 synced_entry 切）%d/%d 在信封内 · "
           "信封外 %s 条（**显式负对照 off %d** / 真漏 **%d**）· entry 分格 %s ｜ "
           "未收步 %s ｜ 全史 brainless_ratio %s"
           % (time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(intro)), post_calls, missing,
              tagged.get("inside", 0), tg_n, tagged.get("outside", 0), off_n, truly_out,
              {k: v for k, v in (tagged.get("entry") or {}).items() if v},
              open_n, ratio))
    if missing:
        return {"state": "FAIL",
                "why": "字段引入后仍有 %d 条 call 没带 synced —— 尺子漏记：%s" % (missing, why),
                "how": "py -3.14 tools/codex-scripts/exec-deck.py"}
    if open_n:
        return {"state": "PENDING", "why": "有 %s 个未收的步（欠的活）：%s" % (open_n, why),
                "how": "py -3.14 tools/codex-scripts/exec-deck.py"}
    if truly_out:
        return {"state": "PENDING",
                "why": "**改动后窗口**里有 %d 条**真·信封外**（已剔掉 off 负对照）：%s" % (truly_out, why),
                "how": "py -3.14 tools/codex-scripts/five-dim.py ruler"}
    if attention:
        return {"state": "PENDING", "why": "exec-deck 报了需要人看的项：%s ｜ %s"
                % ("；".join(attention)[:160], why),
                "how": "py -3.14 tools/codex-scripts/exec-deck.py"}
    return {"state": "PASS", "why": why, "how": "py -3.14 tools/codex-scripts/exec-deck.py"}


# ── 交付 ────────────────────────────────────────────────────────────────────
def angle_delivery() -> dict:
    pkg = ROOT / "holo_pet_w3" / "package.json"
    receipt = ROOT / "state" / "desktop-install-receipt.json"
    guard = ROOT / "tools" / "codex-scripts" / "desktop-shell-guard.py"
    if not guard.is_file():
        return {"state": "FAIL", "why": "没有「不破坏 DSH」守卫脚本"}
    rc, out, err, dt = _run([PY, str(guard)], 120)
    m = re.search(r"PASS (\d+) · FAIL (\d+) · PENDING (\d+)", out)
    pend = int(m.group(3)) if m else -1
    if not pkg.is_file():
        return {"state": "FAIL", "why": "壳没有 package.json ⇒ 打不了包"}
    if not receipt.is_file():
        return {"state": "PENDING",
                "why": "清单在、守卫 %s，但**还没打过包**（无装机回执）；"
                       "且守卫还有 %d 条 PENDING（要主人真接一次对话面）"
                       % (m.group(0) if m else "?", pend),
                "how": "cd holo_pet_w3 && npm run install-less-pack  ← 见 holo_pet_w3/package.json 的 pack"}
    # 🔴 2026-09-23 第 46 轮：**回执文件不做数，现量一遍才算数**。
    # 为什么：回执是**某个时刻**的量；源码此后一改，回执照样全绿 ⇒ 一个 PASS 的回执配一个**过期的包**
    # （实测：第 40 轮打的包，第 43-45 轮改了 window.js/main.cjs/preload.cjs/index.html，
    #  回执仍是 8 项红 0，而包里那四个文件全是旧的）。
    # ⇒ 本格改成**现跑** `pack-receipt.py --dry`（它含"包与源码同源"逐字节比对），红就判红。
    rc2, out2, _e2, _dt2 = _run([PY, str(ROOT / "tools" / "codex-scripts" / "pack-receipt.py"),
                                 "--dry"], 180)
    red = re.search(r"红 (\d+) 项", out2 or "")
    n_red = int(red.group(1)) if red else -1
    if n_red != 0:
        bad = [ln.strip() for ln in (out2 or "").splitlines() if "🔴" in ln]
        return {"state": "FAIL",
                "why": "装机件与当前源码**不同源**或回执量不过（现量红 %d）：%s"
                       % (n_red, bad[0][:150] if bad else (out2 or "")[-150:]),
                "how": "cd holo_pet_w3 && npm run pack  →  py -3.14 tools/codex-scripts/pack-receipt.py"}
    return {"state": "PASS", "why": "清单 + 装机回执都在，**且现量过**（包与源码同源）· 守卫 %s"
            % (m.group(0) if m else "?"),
            "how": "py -3.14 tools/codex-scripts/pack-receipt.py --dry"}


def main() -> int:
    ap = argparse.ArgumentParser(description="六视角验收（一张表一个门）")
    ap.add_argument("--full", action="store_true", help="开发者视角含全量测试（约 9 分钟）")
    ap.add_argument("--only", default="", help="逗号分隔：用户,开发者,运维,安全,审计,交付")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    want = [x.strip() for x in a.only.split(",") if x.strip()] or list(ANGLES)
    bad = [x for x in want if x not in ANGLES]
    if bad:
        print("🔴 不认识的视角：%s（只认 %s）" % (bad, "/".join(ANGLES)))
        return 3

    t0 = time.time()
    print("=" * 78)
    print("六视角验收 · %s" % time.strftime("%Y-%m-%dT%H:%M:%S"))
    print("=" * 78)
    print("  仓根 %s" % ROOT)
    print("  参数 full=%s · only=%s" % (a.full, want))
    print("-" * 78)

    rows = []
    for name in want:
        ts = time.time()
        if name == "用户":
            r = angle_user()
        elif name == "开发者":
            r = angle_dev(a.full)
        elif name == "运维":
            r = angle_ops()
        elif name == "安全":
            r = angle_security()
        elif name == "审计":
            r = angle_audit()
        else:
            r = angle_delivery()
        r["angle"] = name
        r["wall_s"] = round(time.time() - ts, 1)
        rows.append(r)
        mark = {"PASS": "✅", "FAIL": "🔴", "PENDING": "⏳", "FLAKY": "🌗", "SKIP": "⤼"}[r["state"]]
        print("%s %-6s %-7s %5.1fs  %s" % (mark, name, r["state"], r["wall_s"], r["why"][:150]))
        if r.get("how"):
            print("        复现：%s" % r["how"])

    n_fail = sum(1 for r in rows if r["state"] == "FAIL")
    n_pend = sum(1 for r in rows if r["state"] in ("PENDING", "FLAKY"))
    n_flaky = sum(1 for r in rows if r["state"] == "FLAKY")
    print("-" * 78)
    print("  合计 %d 个视角 · PASS %d · FAIL %d · PENDING %d（含 FLAKY %d）· 用时 %.1fs"
          % (len(rows), len(rows) - n_fail - n_pend, n_fail, n_pend, n_flaky, time.time() - t0))
    print("  ⚠️ PENDING / FLAKY **都不算 PASS**（「还没做」与「首跑红复跑绿」都不许读成「没问题」）")
    print("  退出码：**0=六视角全过可交 · 1=有 FAIL · 2=有 PENDING/FLAKY**")
    if a.json:
        Path(a.json).write_text(json.dumps(
            {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "full": a.full,
             "rows": rows, "fail": n_fail, "pending": n_pend, "flaky": n_flaky},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print("  产物: %s" % a.json)
    if n_fail:
        return 1
    return 2 if n_pend else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(3)
