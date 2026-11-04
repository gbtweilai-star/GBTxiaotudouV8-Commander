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

# 🔴 2026-11-04：冒烟的默认参数原来是**一个固定字典** `{'text':...}` 喂所有位。
#   实测 426 位全开后 25 个失败，其中 13 个是 needs_input —— 不是位坏了，
#   是「喂了它不需要的东西，又没喂它要的东西」。
#   现在按 PARAM_REQUIRED 登记的必填参数补**安全占位值**，让它们能真跑到业务逻辑。
#   ⚠️ 但要过真实目标参数的位（url/repo/target…）**故意不补** ——
#      给假目标会真发网络请求，那比"如实报缺参数"更坏。这类继续落 needs_input。
_SAFE_FILL = {
    "text": "GBT全开自检", "description": "GBT全开自检", "goal": "GBT全开自检",
    "intent": "GBT全开自检", "message": "GBT全开自检", "need": "GBT全开自检",
    "prompt": "GBT全开自检", "query": "自检", "name": "smoke",
    "kind": "status", "action": "caps", "nodes": [], "symbol": "run",
    "thread_id": "smoke", "cwe": "CWE-79",
    "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
}
_NEEDS_REAL_TARGET = ("url", "repo", "target", "domain", "host", "path", "workdir")


def _smoke_payload(cap: str) -> dict:
    """给某一位产冒烟参数：只补**无害**的占位，要真目标的位不补（宁可如实报缺）。"""
    need = []
    try:
        from .caps_registry import PARAM_REQUIRED
        need = ((PARAM_REQUIRED.get(cap) or {}).get("params") or [])
    except Exception:                                              # noqa: BLE001
        pass
    payload = {"text": "GBT全开自检"}
    for k in need:
        if k in _NEEDS_REAL_TARGET:
            continue
        if k in _SAFE_FILL:
            payload[k] = _SAFE_FILL[k]
    return payload


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
        "r=g.run_task(%r, %s);"
        "err = r.get('error') or (r.get('gbt_result') or {}).get('error') or '';"
        # 🔴 2026-11-04：很多 tools 位的返回**本来就没有 ok 字段**（只回业务字段）。
        #   原来 bool(r.get('ok')) 一律判成 False ⇒ 跑成功也记失败（实测 5 个 A 族就是这样）。
        #   现在：没显式 ok 且没 error ⇒ 视为成功，并标 ok_inferred 让人看得见这是推断。
        "okv = r.get('ok');"
        "okv = (not bool(err)) if okv is None else bool(okv);"
        "print(json.dumps({'ok':okv, 'ok_inferred': r.get('ok') is None,"
        " 'error': str(err)[:300]},ensure_ascii=False))"
        % (str(ROOT), cap, json.dumps(_smoke_payload(cap), ensure_ascii=False))
    )
    t0 = time.time()
    try:
        p = subprocess.run([PY, "-X", "utf8", "-c", code], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, cwd=str(ROOT),
                           env=env)
        ms = int((time.time() - t0) * 1000)
        # 防御：某些能力位会把 cross_scan 临时产物写进 CWD（仓根）→ 跑完立刻清
        cleaned = 0
        for junk in list(ROOT.glob("gbt_cross_scan*")) + list(ROOT.glob("tmp*.jsonl")):
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
        if d.get("ok_inferred"):
            out["ok_inferred"] = True          # 该位没回 ok，是按「无 error」推断的成功
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
    blocked_terminal, blocked_transfer = [], []
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
        # 🔴 2026-11-04 主人令（`security/policy.py:1173` 原话逐字）：
        #   「除了她使用**危险能力和转账能力**需要票，其他一切都要以设备算力推理分析来做决策」
        #   原来这里用注册表 `safe` 字段当门 —— 那个字段的含义是「**有没有副作用**」
        #   （会写盘 / 会起进程），**不是**「危险不危险」。
        #   实测全开 426 位时 87 个被这道门挡掉，其中 **78 个是普通干活的位**
        #   （humanizer 去AI味 · chart_html 画图 · skill_finder 检索 · showcase_ops 展示 · music_auto …），
        #   它们被提前拦下，**根本走不到下面那层能区分 hacker / transfer / normal 的判据**。
        #   现在按主人令改口径：**只由 security_policy 判**。
        #   · normal   → 放行（运行时若还需 scope 票，由 security/policy.py 拦，落 blocked_policy）
        #   · hacker   → 要主人终端确认（除非已给 ticket）
        #   · transfer → 永远要票，攻击模式也不例外
        #   ⚠️ 副作用已知：normal 里会写盘的位现在会**真写**（主人 2026-11-04 选「严格按主人令放开」）。
        try:
            from gbt_allinone import security_policy as _sp
            dec = _sp.check(cap)
        except Exception:  # noqa: BLE001
            dec = {"decision": "allow"}
        if dec.get("decision") == "blocked_transfer":
            blocked_transfer.append({"cap": cap, "reason": dec.get("reason")})
            continue
        if dec.get("decision") == "need_terminal_confirm" and not ticket:
            blocked_terminal.append({"cap": cap, "reason": dec.get("reason"),
                                     "hint": "主人终端执行：python tools/confirm-security.py request %s" % cap})
            continue
        to = _timeout_for(cap, timeout_per_cap)
        r = _run_one(cap, to)
        if dec.get("decision") == "attack_self_decision":
            r["self_decision"] = "GBT小土豆V8（攻击模式）"
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
        "blocked_by_terminal_confirm": blocked_terminal,
        "blocked_transfer": blocked_transfer,
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
