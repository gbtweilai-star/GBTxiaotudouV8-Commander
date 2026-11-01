"""GBT小土豆V8 · 万能插：全部能力全开 + 同步执行（2026-11-02 主人令）

主人：「把万能插的全部能力设为同步执行，必须每次使用都是打开全部能力。」

口径（写死）：
  · 每次使用 = 枚举**全部 385 个能力位**（一个不漏，full_open=True）；
  · **同步**：按顺序逐个在独立子进程执行，带超时（超时 kill）；
  · safe 位直接执行；**需授权位（85）没票不执行**，进 blocked_by_ticket（打开但被票挡）；
  · 每次执行写 state/omni-plug.json + state/omni-plug.jsonl + orchestration-ledger；
  · 本模块不是新能力位，是万能插的"全开执行器"。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / "pyembed" / "python.exe") if (ROOT / "pyembed" / "python.exe").is_file() else sys.executable
STATE = ROOT / "state" / "omni-plug.json"
LOG = ROOT / "state" / "omni-plug.jsonl"
RESULTS = ROOT / "state" / "omni-results.jsonl"


def cap_table() -> dict:
    sys.path.insert(0, str(ROOT))
    from gbt_allinone.caps_registry import BENIGN_CAPS
    return BENIGN_CAPS


HEAVY_DOMAINS = {"video", "creation", "llm", "recon", "devour", "image_video", "voice"}
HEAVY_CAPS = {"sec_chain", "sec_scan", "cross_scan", "page_scan"}
SMOKE = {"text": "GBT全开自检"}


def _timeout_for(cap: str, base: float) -> float:
    if cap in HEAVY_CAPS:
        return max(base, 90.0)
    meta = (cap_table().get(cap) or {})
    if str(meta.get("domain") or "") in HEAVY_DOMAINS:
        return max(base, 60.0)
    return base


def _run_one(cap: str, timeout: float) -> dict:
    import tempfile
    tmpdir = ROOT / "state" / "tmp" / "omni"
    tmpdir.mkdir(parents=True, exist_ok=True)
    env = dict(**__import__("os").environ)
    env["TEMP"] = str(tmpdir)
    env["TMP"] = str(tmpdir)
    env["TMPDIR"] = str(tmpdir)
    code = (
        "import sys,json;sys.path.insert(0,%r);"
        "import gbt_allinone as g;"
        "r=g.run_task(%r, {'text': 'GBT全开自检'});"
        "err = r.get('error') or (r.get('gbt_result') or {}).get('error') or '';"
        "print(json.dumps({'ok':bool(r.get('ok')), 'error': str(err)[:300]},ensure_ascii=False))"
        % (str(ROOT), cap)
    )
    t0 = time.time()
    try:
        p = subprocess.run([PY, "-X", "utf8", "-c", code], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, cwd=str(ROOT),
                           env=env)
        ms = int((time.time() - t0) * 1000)
        # 防御：某些能力位会把 cross_scan 临时产物写进 CWD（仓根）→ 跑完立刻清
        cleaned = 0
        for junk in list(ROOT.glob("gbt_cross_scan*")):
            try:
                if junk.is_dir():
                    import shutil as _sh
                    _sh.rmtree(junk, ignore_errors=True)
                else:
                    junk.unlink()
                cleaned += 1
            except Exception:  # noqa: BLE001
                pass
        if p.returncode != 0:
            return {"cap": cap, "ok": False, "ms": ms,
                    "error": (p.stderr or p.stdout or "")[-200:]}
        try:
            d = json.loads((p.stdout or "").strip().splitlines()[-1])
        except Exception:  # noqa: BLE001
            return {"cap": cap, "ok": False, "ms": ms,
                    "error": "子进程输出不是 JSON：" + (p.stdout or "")[-120:]}
        out = {"cap": cap, "ok": bool(d.get("ok")), "ms": ms}
        if not out["ok"]:
            out["error"] = str(d.get("error") or "")[:300] or "ok=false（无 error 字段）"
        if cleaned:
            out["cleaned_artifacts"] = cleaned
        return out
    except subprocess.TimeoutExpired:
        return {"cap": cap, "ok": False, "ms": int((time.time() - t0) * 1000),
                "error": "超时 %ss（已 kill）" % timeout}
    except Exception as e:  # noqa: BLE001
        return {"cap": cap, "ok": False, "ms": int((time.time() - t0) * 1000),
                "error": str(e)[:160]}


def run_all_sync(caps: list | None = None, timeout_per_cap: float = 12.0,
                 ticket: str = "", run_id: str = "") -> dict:
    table = cap_table()
    all_caps = list(table.keys())
    target = list(caps) if caps else all_caps
    full_open = caps is None
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
    results, blocked, blocked_policy = [], [], []
    t0 = time.time()

    def _progress(i: int) -> None:
        try:
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps({
                "ok": False, "running": True, "mode": "sync-all", "run_id": run_id,
                "caps_total": len(all_caps), "caps_opened": len(target),
                "full_open": full_open, "progress": i,
                "executed": len(results), "ok_count": sum(1 for x in results if x["ok"]),
                "fail_count": sum(1 for x in results if not x["ok"]),
                "blocked_by_ticket": blocked,
                "elapsed_ms": int((time.time() - t0) * 1000),
                "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    for i, cap in enumerate(target, 1):
        meta = table.get(cap) or {}
        if not bool(meta.get("safe")) and not ticket:
            blocked.append({"cap": cap, "reason": "需授权位：没票不执行（已打开、被票挡）"})
            continue
        to = _timeout_for(cap, timeout_per_cap)
        r = _run_one(cap, to)
        # 授权策略拦截（process_execute/external_llm/deploy_publish/privacy_read）不是失败
        if not r.get("ok") and "需要人工授权" in str(r.get("error") or ""):
            blocked_policy.append({"cap": cap, "reason": r.get("error")})
            continue
        if not r.get("ok") and "超时" in str(r.get("error") or ""):
            # 重型位超时：放宽到 2 倍再试一次（仍失败才算失败）
            r2 = _run_one(cap, to * 2)
            if r2.get("ok"):
                r = r2
                r["retried"] = True
        results.append(r)
        try:
            with RESULTS.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"run_id": run_id, "cap": cap, **r},
                                    ensure_ascii=False) + "\n")
        except Exception:  # noqa: BLE001
            pass
        if i % 5 == 0 or i == len(target):
            _progress(i)
    elapsed = int((time.time() - t0) * 1000)
    ok_n = sum(1 for x in results if x["ok"])
    out = {
        "ok": ok_n == len(results) and bool(results),
        "mode": "sync-all", "run_id": run_id,
        "caps_total": len(all_caps), "caps_opened": len(target),
        "full_open": full_open,
        "executed": len(results), "ok_count": ok_n, "fail_count": len(results) - ok_n,
        "blocked_by_ticket": blocked,
        "blocked_by_policy": blocked_policy,
        "results": results,
        "elapsed_ms": elapsed,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "note": "同步逐个执行；需授权位没票不执行；默认必须全开（caps=None）",
    }
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({k: out[k] for k in ("at", "run_id", "mode", "caps_total",
                                                "caps_opened", "executed", "ok_count",
                                                "fail_count", "elapsed_ms", "full_open")},
                            ensure_ascii=False) + "\n")
    try:
        from gbt_allinone import orchestration as OB
        OB.record("omni", "omni-all-sync",
                  detail="万能插全开同步执行：%d/%d 位，ok %d / fail %d / 票挡 %d"
                         % (len(target), len(all_caps), ok_n, len(results) - ok_n, len(blocked)),
                  evidence="state/omni-plug.json")
    except Exception:  # noqa: BLE001
        pass
    return out


def status() -> dict:
    try:
        d = json.loads(STATE.read_text(encoding="utf-8"))
        return {k: d.get(k) for k in ("ok", "mode", "caps_total", "caps_opened", "full_open",
                                      "executed", "ok_count", "fail_count", "elapsed_ms",
                                      "at", "run_id", "blocked_by_ticket")}
    except Exception:  # noqa: BLE001
        return {"ok": False, "reason": "还没有全开同步执行记录（万能插未使用过）"}
