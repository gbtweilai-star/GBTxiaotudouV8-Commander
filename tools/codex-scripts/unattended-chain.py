# -*- coding: utf-8 -*-
"""unattended-chain -- 长线**无人值守**任务执行链（引擎复用 longrun，不另造调度）。

主人令 2026-10-17：「对了你要设计好长线无人值守任务执行链路哈」。

## 设计（失败优先，不是"能跑就行"）
- **引擎**：`cap longrun '{"op":"submit"|"tick"}'` —— 取下一待办→执行→判据验收→重试/停滞/升级，
  这些**不重写**（单一真相），本工具只做"外面那层守护"。
- **链规格**：`state/chains/<名字>.json` = {name, steps:[{desc, kind, params, acceptance,
  priority, depends_on, needs_scopes}], interval_s, max_minutes}。
- **无人值守的硬边界**（AI 不能自授）：
  · 每 tick 前检查**下一步**声明的 `needs_scopes` 是否在账本里活着；缺 ⇒ 状态置
    `blocked_authorization` + 写值班板 + **退出码 2**（**不重试、不烧 attempts、不绕门**）；
  · 蓝图 `see_first` TTL 过期同理（读 `state/blueprints/*.approved` 的 mtime/TTL）。
- **断点续跑**：任务状态在 longrun 里（done/failed/stalled），本工具只推 tick；重跑 `run` 继续。
- **单实例锁**：`state/unattended/<chain>.lock`（PID+时间），已有活锁就拒（防双开互踩）。
- **心跳 + 审计**：`heartbeat.json`（每分钟-ish）+ `<chain>.jsonl` 逐步留痕；`abort` 落停止旗。
- **看护**：每 N tick 跑一次 `watchdog-run.py`（W1 内存 / W2 卡 / W3 训练进度 / W4 OOM / W5 链 / W6 推理），
  红就降速+记账，不杀掉链（无人值守要能自愈，不能一红就死）。
- **selftest**：用隔离 store + 良性能力位（`quant_plan`）跑通 submit→tick→done，
  再验证"缺票 ⇒ 停"（负对照），**不写真实 store**。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
CHAINS = ROOT / "state" / "chains"
STAGE = ROOT / "state" / "unattended"
GATE = ROOT / "tools" / "codex-scripts" / "five-dim.py"
GRANTS = ROOT / "gbt_allinone" / "store" / "auth_grants.jsonl"
BPS = ROOT / "state" / "blueprints"
TTL_S = 7200


def _cap(kind: str, payload: dict, timeout: int = 900) -> dict:
    # 2026-10-17 主人令：自主长线任务里，除转账/黑客能力外由 GBT小土豆V8 自行判断授权
    #   ⇒ 只在本守护器发起的子进程里置 GBT_AUTONOMOUS=1（人工终端调用不受影响）。
    _env = dict(os.environ, GBT_AUTONOMOUS="1")
    p = subprocess.run([sys.executable, "-X", "utf8", str(GATE), "cap", kind,
                        json.dumps(payload, ensure_ascii=False), "--full"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, cwd=str(ROOT), env=_env)
    txt = (p.stdout or "") + (p.stderr or "")
    i = txt.find("{")
    try:
        return json.loads(txt[i:])
    except Exception:                                            # noqa: BLE001
        return {"status": "error", "raw": txt[:400]}


def _grants() -> dict:
    now = time.time()
    out = {}
    if not GRANTS.is_file():
        return out
    for ln in GRANTS.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except Exception:                                        # noqa: BLE001
            continue
        if float(r.get("expires_at") or 0) > now:
            out.setdefault(r.get("scope"), 0)
            out[r.get("scope")] += 1
    return out


def _blueprint_left() -> float:
    if not BPS.is_dir():
        return -1
    best = -1.0
    for p in BPS.glob("*.approved"):
        age = time.time() - p.stat().st_mtime
        best = max(best, TTL_S - age)
    return best


def _load_chain(name: str) -> dict:
    p = CHAINS / (name if name.endswith(".json") else name + ".json")
    if not p.is_file():
        raise SystemExit("链规格不存在：%s（先写 state/chains/<名字>.json）" % p.relative_to(ROOT))
    return json.loads(p.read_text(encoding="utf-8"))


def _lock_path(name: str) -> Path:
    return STAGE / (name + ".lock")


def _acquire_lock(name: str) -> bool:
    STAGE.mkdir(parents=True, exist_ok=True)
    lp = _lock_path(name)
    if lp.is_file():
        try:
            rec = json.loads(lp.read_text(encoding="utf-8"))
            pid = int(rec.get("pid") or 0)
            alive = False
            if pid:
                try:
                    os.kill(pid, 0)                             # 探活（Windows 下对不存在的 PID 会抛）
                    alive = True
                except Exception:                                # noqa: BLE001
                    alive = False
            if alive:
                print("RED 已有活锁：%s（pid=%s，起于 %s）⇒ 拒绝双开"
                      % (lp.relative_to(ROOT), pid, rec.get("started_at")))
                return False
        except Exception:                                        # noqa: BLE001
            pass
    lp.write_text(json.dumps({"pid": os.getpid(), "started_at": time.strftime("%Y-%m-%dT%H:%M:%S")}),
                  encoding="utf-8")
    return True


def _release_lock(name: str) -> None:
    try:
        _lock_path(name).unlink()
    except Exception:                                            # noqa: BLE001
        pass


def _hb(name: str, state: str, **kw) -> None:
    STAGE.mkdir(parents=True, exist_ok=True)
    rec = {"chain": name, "state": state, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "epoch": round(time.time(), 1), **kw}
    (STAGE / (name + "-heartbeat.json")).write_text(json.dumps(rec, ensure_ascii=False, indent=1),
                                                    encoding="utf-8")


def _log(name: str, rec: dict) -> None:
    STAGE.mkdir(parents=True, exist_ok=True)
    with (STAGE / (name + ".jsonl")).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **rec}, ensure_ascii=False) + "\n")


def _duty(name: str, what: str) -> None:
    """写值班板（醒目、可机读；不是聊天消息）。"""
    STAGE.mkdir(parents=True, exist_ok=True)
    (STAGE / (name + "-duty.md")).write_text(
        "# 无人值守值班板 · %s\n\n- 时间：%s\n- 状态：%s\n\n> 这是**需要主人**的事；链会停在这里等，不绕门、不自授。\n"
        % (name, time.strftime("%Y-%m-%dT%H:%M:%S"), what), encoding="utf-8")


def cmd_submit(name: str) -> int:
    ch = _load_chain(name)
    ok = 0
    ids = []
    for st in ch.get("steps") or []:
        payload = {"op": "submit", "description": st.get("desc") or st.get("kind"),
                   "kind": st["kind"], "params": st.get("params") or {},
                   "priority": st.get("priority") or "medium",
                   "depends_on": st.get("depends_on") or [],
                   "acceptance": st.get("acceptance") or [],
                   "max_attempts": int(st.get("max_attempts") or 3),
                   "_needs_scopes": st.get("needs_scopes") or []}
        r = _cap("lr_submit", payload)
        body = (r.get("result") or {})
        good = bool(body.get("ok", body.get("task_id")))
        print("%s %-8s %s" % ("✅" if good else "RED", st["kind"], str(st.get("desc"))[:60]))
        if good:
            ok += 1
            ids.append(body.get("task_id"))
        else:
            print("   回执：", json.dumps(body, ensure_ascii=False)[:240])
    _hb(name, "submitted", submitted=ok, task_ids=ids)
    _log(name, {"event": "submit", "n": ok})
    print("已提交 %d 步到长程任务层" % ok)
    return 0 if ok else 1


def cmd_run(name: str, interval: int, max_minutes: float, watchdog_every: int) -> int:
    ch = _load_chain(name)
    stop = STAGE / (name + ".stop")
    if stop.is_file():
        print("停止旗在（%s）⇒ 先删旗或换名" % stop.relative_to(ROOT))
        return 3
    if not _acquire_lock(name):
        return 4
    t0 = time.time()
    ticks = 0
    try:
        while True:
            if (time.time() - t0) > max_minutes * 60:
                _hb(name, "timeout", ticks=ticks)
                print("到时限 %.0f 分钟，收工（可续跑）" % max_minutes)
                return 0
            if stop.is_file():
                _hb(name, "stopped", ticks=ticks)
                print("收到停止旗 ⇒ 收工")
                return 0
            # ① 先看长程任务层还有没有待办
            st = _cap("lr_status", {})
            body = st.get("result") or {}
            tasks = body.get("tasks") or body.get("list") or []
            pending = [t for t in tasks if str(t.get("status")) in ("pending", "running", "retrying", "")]
            if not pending:
                _hb(name, "done", ticks=ticks, tasks=len(tasks))
                _log(name, {"event": "done", "ticks": ticks})
                print("链上没有待办了 ⇒ 收工（done）")
                return 0
            nxt = pending[0]
            # ② 授权/蓝图预检：缺就停，**不重试不烧票**
            #    2026-10-17 修（留痕）：longrun.submit 只存固定字段，不会把 `needs_scopes` 落进任务；
            #    所以按**链规格**用 kind 反查下一待办需要的票（规格是唯一真相）。
            _need_map = {}
            for _st in (ch.get("steps") or []):
                if _st.get("needs_scopes"):
                    _need_map.setdefault(_st.get("kind"), []).extend(_st["needs_scopes"])
            need = list(_need_map.get(nxt.get("kind")) or [])
            have = _grants()
            missing = [s for s in need if s not in have]
            bp = _blueprint_left()
            if missing or (need and bp < 0):
                why = ("缺作用域 %s" % ",".join(missing)) if missing else ("蓝图已过期（see_first 会拦）")
                _hb(name, "blocked_authorization", waiting=why, ticks=ticks)
                _log(name, {"event": "blocked", "why": why})
                _duty(name, why + "\n\n请主人在终端发对应授权/重批蓝图后，重新 `run` 即可续跑。")
                print("PAUSED：" + why + " ⇒ 已写值班板，退出码 2（不绕门、不自授、不烧重试）")
                return 2
            # ③ 推进一步（引擎自带判据/重试/停滞/升级）
            r = _cap("lr_tick", {"max_tasks": 1})
            rb = r.get("result") or {}
            ticks += 1
            ran = rb.get("ran") or rb.get("results") or []
            last = ""
            try:
                last = str((ran[0] if isinstance(ran, list) and ran else {}).get("status") or "")[:20]
            except Exception:                                    # noqa: BLE001
                pass
            _hb(name, "running", ticks=ticks, last_status=last or "unknown",
                pending=len(pending), blueprint_left_s=round(bp, 0))
            _log(name, {"event": "tick", "n": ticks, "status": last or "unknown"})
            print("[tick %d] %s · 待办 %d · 蓝图剩 %.0fs" % (ticks, last or "unknown", len(pending), bp))
            # ④ 周期性看护（红就降速，不杀链）
            if watchdog_every and ticks % watchdog_every == 0:
                try:
                    p = subprocess.run([sys.executable, "-X", "utf8",
                                        str(ROOT / "tools" / "codex-scripts" / "watchdog-run.py")],
                                       capture_output=True, text=True, encoding="utf-8",
                                       errors="replace", timeout=300, cwd=str(ROOT))
                    tail = [x.strip() for x in (p.stdout or "").splitlines() if x.strip()]
                    verdict = tail[-1] if tail else "未读到"
                    _log(name, {"event": "watchdog", "verdict": verdict[:160]})
                    if "RED" in verdict:
                        print("  看护 RED ⇒ 降速 3×：" + verdict[:120])
                        time.sleep(interval * 2)
                except Exception as e:                           # noqa: BLE001
                    _log(name, {"event": "watchdog_error", "err": str(e)[:160]})
            time.sleep(max(3, int(interval)))
    finally:
        _release_lock(name)


def cmd_status(name: str) -> int:
    hb = STAGE / (name + "-heartbeat.json")
    duty = STAGE / (name + "-duty.md")
    print("链：%s" % name)
    print("心跳：", (hb.read_text(encoding="utf-8").strip()[:600] if hb.is_file() else "未读到（还没跑过）"))
    if duty.is_file():
        print("值班板：", duty.read_text(encoding="utf-8").strip()[:400])
    lock = _lock_path(name)
    print("锁：", (lock.read_text(encoding="utf-8").strip() if lock.is_file() else "无"))
    return 0


def cmd_abort(name: str) -> int:
    STAGE.mkdir(parents=True, exist_ok=True)
    (STAGE / (name + ".stop")).write_text(time.strftime("%Y-%m-%dT%H:%M:%S"), encoding="utf-8")
    print("已落停止旗：%s（下一次循环收工）" % (STAGE / (name + ".stop")).relative_to(ROOT))
    return 0


def cmd_selftest() -> int:
    """隔离 store + 良性能力位：submit→tick→done 通；再验"缺票 ⇒ 停"（负对照）。不碰真实 store。"""
    s = tempfile.mkdtemp(prefix="gbt_chain_store_")
    c = tempfile.mkdtemp(prefix="gbt_chain_create_")
    old = {k: os.environ.get(k) for k in ("GBT_STORE_DIR", "GBT_CREATE_ROOT")}
    os.environ["GBT_STORE_DIR"] = s
    os.environ["GBT_CREATE_ROOT"] = c
    try:
        # 用空闲端口换链名，避免与真实链撞
        name = "_selftest_%d" % int(time.time())
        CHAINS.mkdir(parents=True, exist_ok=True)
        spec = {"name": name, "interval_s": 3, "max_minutes": 2,
                "steps": [{"desc": "数词（良性只读）", "kind": "quant_plan",
                           "params": {"op": "plan"}, "needs_scopes": []}]}
        (CHAINS / (name + ".json")).write_text(json.dumps(spec, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
        rc1 = cmd_submit(name)
        rc2 = cmd_run(name, interval=2, max_minutes=1, watchdog_every=0)
        # 负对照：声明一个不可能有的作用域 ⇒ 必须 PAUSED(2)
        name2 = name + "_neg"
        spec2 = {"name": name2, "interval_s": 2, "max_minutes": 1,
                 "steps": [{"desc": "需要不存在的票", "kind": "quant_plan",
                            "params": {"op": "plan"}, "needs_scopes": ["__no_such_scope__"]}]}
        (CHAINS / (name2 + ".json")).write_text(json.dumps(spec2, ensure_ascii=False, indent=1),
                                               encoding="utf-8")
        cmd_submit(name2)
        rc3 = cmd_run(name2, interval=2, max_minutes=1, watchdog_every=0)
        ok = (rc1 == 0) and (rc2 == 0) and (rc3 == 2)
        print("== 无人值守链自检：%s（submit=%s run=%s 缺票停=%s）==" %
              ("PASS" if ok else "FAIL", rc1, rc2, rc3))
        for nm in (name, name2):
            for suffix in (".json", ".jsonl", "-heartbeat.json", "-duty.md", ".lock", ".stop"):
                try:
                    (CHAINS / (nm + ".json")).unlink(missing_ok=True)
                except Exception:                                # noqa: BLE001
                    pass
                try:
                    (STAGE / (nm + suffix)).unlink(missing_ok=True)
                except Exception:                                # noqa: BLE001
                    pass
        return 0 if ok else 1
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(s, ignore_errors=True)
        shutil.rmtree(c, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="长线无人值守任务执行链（引擎=longrun；缺票停、可续跑）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nm in ("submit", "run", "status", "abort"):
        sp = sub.add_parser(nm)
        sp.add_argument("chain")
        if nm == "run":
            sp.add_argument("--interval", type=int, default=20)
            sp.add_argument("--max-minutes", type=float, default=240)
            sp.add_argument("--watchdog-every", type=int, default=5)
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        return cmd_selftest()
    if a.cmd == "submit":
        return cmd_submit(a.chain)
    if a.cmd == "run":
        return cmd_run(a.chain, a.interval, a.max_minutes, a.watchdog_every)
    if a.cmd == "status":
        return cmd_status(a.chain)
    if a.cmd == "abort":
        return cmd_abort(a.chain)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
