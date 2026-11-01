# gbt-capability: sync_guard
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""sync_guard — 双仓同步巡检（2026-11-01）。

## 它是什么
交付树 ↔ live 工作仓 的**只读巡检位**：复用 `tools/codex-scripts/two-way-sync.py` 的
sha1 对账，返回 ALIGNED / DRIFT、差异计数、前 20 条路径、修复命令；DRIFT 时给出 alerts。
- `status`：只报差异（不判）
- `verify`：判 ALIGNED（only_live=0 · differ=0 · 两边 cap 计数相等）
- `patrol`：verify + 可选写 `state/sync_guard.jsonl` 运行台账（record=true 才写）
- `where`：入口与命令

## 诚实边界
- **只读**：不自动 pull/push；修复命令交给使用者执行（防自动覆盖）。
- 交付树路径默认 `~/Desktop/GBT小土豆V8`，可用 payload `delivery` 或环境变量 `GBT_DELIVERY` 覆盖。
- 运行台账只在 live 侧（state 属运行数据，源码交付不含）。
"""
from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repo root（gbt_allinone/tentacle/ 的上两级）
PLANNER = ROOT / "tools" / "codex-scripts" / "two-way-sync.py"
DEFAULT_DELIVERY = Path(os.environ.get(
    "GBT_DELIVERY", str(Path.home() / "Desktop" / "GBT小土豆V8")))

STATUS = {
    "cap": "sync_guard",
    "ops": ["status", "verify", "patrol", "where"],
    "targets": ["delivery", "live"],
    "verdicts": ["ALIGNED", "DRIFT", "needs_config"],
    "readonly": True,
    "record": "patrol 的 record=true 才写 state/sync_guard.jsonl",
}


def _planner():
    spec = importlib.util.spec_from_file_location("two_way_sync_planner", PLANNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("找不到计划器：%s" % PLANNER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _delivery(payload: dict) -> Path:
    raw = payload.get("delivery") or str(DEFAULT_DELIVERY)
    return Path(raw).expanduser().resolve()


def _trim(st: dict, limit: int = 20) -> dict:
    return {
        "verdict": st.get("verdict"),
        "live_caps": st.get("live_caps"),
        "delivery_caps": st.get("delivery_caps"),
        "live_files": st.get("live_files"),
        "delivery_files": st.get("delivery_files"),
        "only_live_n": len(st.get("only_live") or []),
        "only_delivery_n": len(st.get("only_delivery") or []),
        "differ_n": len(st.get("differ") or []),
        "only_live": (st.get("only_live") or [])[:limit],
        "only_delivery": (st.get("only_delivery") or [])[:limit],
        "differ": (st.get("differ") or [])[:limit],
        "quiet_age_s": st.get("quiet_age_s"),
    }


def _alerts(st: dict) -> list:
    if st.get("verdict") == "ALIGNED":
        return []
    out = [{"level": "warn", "code": "sync_drift",
            "message": "双仓源码面漂移：only_live=%d only_delivery=%d differ=%d" %
                       (len(st.get("only_live") or []), len(st.get("only_delivery") or []),
                        len(st.get("differ") or [])),
            "fix": "tools\\two-way-sync.ps1 pull -Apply  # 或 push -Apply -Refresh"}]
    if st.get("live_caps") != st.get("delivery_caps"):
        out.append({"level": "error", "code": "caps_mismatch",
                    "message": "能力位计数不一致：live=%s delivery=%s" % (st.get("live_caps"), st.get("delivery_caps")),
                    "fix": "先 align 源码，再跑 refresh 链"})
    return out


def _audit(st: dict) -> str:
    """把巡检结论写进框架审计（alerts 会读）：DRIFT→error，ALIGNED→ok（标记恢复）。

    只在 `patrol notify=true` 时调用；写不了（如交付树只读）就返回 not_written，不假装。
    """
    try:
        try:
            from ..store import audit as _a
        except Exception:  # noqa: BLE001
            from gbt_allinone.store import audit as _a
        if st.get("verdict") == "ALIGNED":
            _a("ok", {"kind": "sync_guard", "reason": "aligned",
                      "live_caps": st.get("live_caps"), "delivery_caps": st.get("delivery_caps")})
            return "notified_ok"
        _a("error", {"kind": "sync_guard",
                     "reason": "sync_drift only_live=%d only_delivery=%d differ=%d" % (
                         len(st.get("only_live") or []), len(st.get("only_delivery") or []),
                         len(st.get("differ") or [])),
                     "live_caps": st.get("live_caps"), "delivery_caps": st.get("delivery_caps")})
        return "notified_error"
    except Exception as e:  # noqa: BLE001
        return "not_written: %s" % type(e).__name__


def _push_payload(st: dict) -> dict:
    text = ("GBT 双仓同步巡检：DRIFT only_live=%d only_delivery=%d differ=%d；"
            "修复 tools\\two-way-sync.ps1 pull -Apply") % (
        len(st.get("only_live") or []), len(st.get("only_delivery") or []),
        len(st.get("differ") or []))
    return {"source": "sync_guard", "verdict": st.get("verdict"),
            "live_caps": st.get("live_caps"), "delivery_caps": st.get("delivery_caps"),
            "only_live": len(st.get("only_live") or []),
            "only_delivery": len(st.get("only_delivery") or []),
            "differ": len(st.get("differ") or []), "text": text,
            "at": time.strftime("%Y-%m-%dT%H:%M:%S")}


def _post_json(url: str, payload: dict, timeout: float = 5.0) -> int:
    import urllib.request
    req = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "GBT-sync-guard/1.0"},
        method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
        return int(r.status)


def _push_targets() -> list:
    """推送目标：环境变量优先，state/sync_push.json 兜底（计划任务不继承临时 env）。"""
    cfg = {}
    try:
        cfg = json.loads((ROOT / "state" / "sync_push.json").read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        cfg = {}
    out = []
    for label, key, env in (("webhook", "webhook", "GBT_SYNC_PUSH_WEBHOOK"),
                            ("feishu", "feishu", "GBT_FEISHU_WEBHOOK"),
                            ("n8n", "n8n", "GBT_N8N_WEBHOOK")):
        url = os.environ.get(env) or (cfg.get(key) if isinstance(cfg, dict) else None)
        if url:
            out.append((label, str(url)))
    return out


def _push(st: dict) -> str:
    """DRIFT 时按顺序尝试：通用 webhook → 飞书机器人 → n8n → 桌面 toast。

    环境变量（不设就走桌面 toast；设了失败会继续降级并如实记 attempts）：
      GBT_SYNC_PUSH_WEBHOOK   任意 JSON POST 端点（n8n/自建网关/手机推送转发）
      GBT_FEISHU_WEBHOOK      飞书群机器人 webhook
      GBT_N8N_WEBHOOK         n8n webhook（如 http://127.0.0.1:5678/webhook/gbt）
    """
    if st.get("verdict") == "ALIGNED":
        return "skipped（只在 DRIFT 推）"
    payload = _push_payload(st)
    attempts = []
    for label, url in _push_targets():
        body = payload if label != "feishu" else {"msg_type": "text", "content": {"text": payload["text"]}}
        try:
            code = _post_json(url, body)
            if 200 <= code < 300:
                return ("%s_ok" % label) if not attempts else ("%s_ok(after %s)" % (label, ";".join(attempts)))
            attempts.append("%s_http_%d" % (label, code))
        except Exception as e:  # noqa: BLE001
            attempts.append("%s_failed:%s" % (label, type(e).__name__))
    # 降级：桌面通知（WinRT toast；子进程无包身份时脚本内退回托盘气泡）
    try:
        import subprocess
        ps = ROOT / "tools" / "notify-desktop.ps1"
        if not ps.is_file():
            return "not_configured" if not attempts else "failed(%s)" % ";".join(attempts)
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-File", str(ps), "-Title", "GBT 双仓同步巡检", "-Message", payload["text"]],
                           capture_output=True, text=True, timeout=40)
        if r.returncode == 0:
            return "toast_ok" if not attempts else "toast_ok(after %s)" % ";".join(attempts)
        return ("toast_failed" if not attempts else "toast_failed(after %s)" % ";".join(attempts))
    except Exception as e:  # noqa: BLE001
        return "push_exception:%s" % type(e).__name__


def _record(st: dict) -> str:
    try:
        p = ROOT / "state" / "sync_guard.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                           "verdict": st.get("verdict"),
                           "live_caps": st.get("live_caps"),
                           "delivery_caps": st.get("delivery_caps"),
                           "only_live": len(st.get("only_live") or []),
                           "only_delivery": len(st.get("only_delivery") or []),
                           "differ": len(st.get("differ") or []),
                           "alerts": len(_alerts(st))}, ensure_ascii=False)
        with p.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        return str(p)
    except Exception as e:  # noqa: BLE001
        return "not_writable: %s" % type(e).__name__


def run(op="status", **kw):
    op = str(op or "status").strip().lower()
    if op == "where":
        return {"ok": True, "op": "where", **STATUS,
                "module": "gbt_allinone/tentacle/sync_guard.py",
                "entry": "py -3.14 tools/codex-scripts/five-dim.py cap sync_guard '{\"op\":\"verify\"}'",
                "planner": str(PLANNER),
                "delivery_default": str(DEFAULT_DELIVERY)}
    if op not in ("status", "verify", "patrol"):
        return {"ok": False, "op": op, "status": "unknown_op",
                "error": "未知 op：%s" % op, "available": STATUS["ops"], "fail_closed": True}
    try:
        planner = _planner()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "op": op, "status": "needs_dependency",
                "error": "计划器加载失败：%s" % type(e).__name__,
                "how_to_fix": "确认 tools/codex-scripts/two-way-sync.py 在位"}
    live = Path(kw.get("live") or ROOT).resolve()
    deliv = _delivery(kw)
    if not deliv.is_dir():
        return {"ok": False, "op": op, "status": "needs_config",
                "error": "交付树不存在：%s" % deliv,
                "how_to_fix": "payload 传 delivery=... 或设 GBT_DELIVERY"}
    try:
        st = planner.verify(live, deliv) if op != "status" else planner.status(live, deliv)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "op": op, "status": "failed",
                "error": "%s: %s" % (type(e).__name__, str(e)[:200])}
    out = {"ok": True, "op": op, "aligned": st.get("verdict") == "ALIGNED",
           "verdict": st.get("verdict"), "alerts": _alerts(st),
           "reading": _trim(st), "delivery": str(deliv), "live": str(live),
           "fix": "tools\\two-way-sync.ps1 status / pull -Apply / push -Apply -Refresh / verify"}
    if op == "patrol":
        if kw.get("record") is True:
            out["record"] = _record(st)
        else:
            out["record"] = "skipped（record=true 才写台账）"
        if kw.get("notify") is True:
            out["notified"] = _audit(st)
            out["pushed"] = _push(st) if kw.get("push", True) is not False else "skipped（push=false）"
        else:
            out["notified"] = "skipped（notify=true 才写审计/喊 alert）"
            out["pushed"] = "skipped（notify=true 才推桌面通知）"
    return out
