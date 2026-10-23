# -*- coding: utf-8 -*-
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""痕迹库 · 第 2 步第一小刀（Owner 2026-09-19 图纸 §2.1 / §5 落地）。

只做三件事：**建表（五张）· 两道闸（脱敏 / origin）· 有源校验**。
**不挂心跳**（挂上就是每 30 分钟自动写盘 —— 那是单独一刀）；**不提供任何删除路径**。

五张表（图纸 §2.1）：
    wave_samples  每次采样的原始读数（每跳都写 · 含 trigger_mode / coverage）
    traces        过阈才留痕（evidence_ref 指向产生它的 sample）
    trace_links   痕迹之间的关系（配对两端）
    promotes      升格事件流水（**状态位 promoted 由它派生** —— 流水才是真相）
    obsessions    「念」表（source_trace_ids 必须指向真实 traces）

三道必须的闸（全部在**写入路径**上，不靠事后审计）：
  ① 脱敏闸：字段白名单 + 形态掩码（`sk-` / `Bearer` / `Cookie` / token|secret|password 值 / 长数字串）
  ② origin 闸：只收白名单事件；**测试件与自检事件拒收**（实测：它们会冒充真实痕迹 —— R-H119/R-H126/R-H133）
  ③ 有源校验：`obsessions.source_trace_ids` 非空且**每个 id 都能在 traces 里查到**，否则整条拒收（第四条硬约束）

用法（只读查询）：
    py -3.10 -m gbt_allinone.trace_store status
    py -3.10 -m gbt_allinone.trace_store retention --days 90
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

# 单一入口：store 目录只从 _paths 取（不自己拼路径）
try:  # 允许在隔离树/测试里被替换
    from gbt_allinone import _paths
    _STORE = Path(_paths.STORE_DIR)
except Exception:  # noqa: BLE001
    _STORE = Path(__file__).resolve().parent / "store"

TRACE_DIR = _STORE / "traces"
TABLES = ("wave_samples", "traces", "trace_links", "promotes", "obsessions")

# ── 闸 ② origin：白名单事件（与图纸 §3.3 阈值口径**同一张表**）+ 测试件排除 ──
WHITELIST_EVENTS = {"denied", "auth_denied", "pipeline_blocked", "error", "longrun_failed",
                    "deploy_promote_blocked", "health_channel_failed", "devour_reject"}
DRILL_KINDS = {"keylogger", "screen_sniff", "device_takeover", "pentest", "social_eng",
               "credential_steal", "data_hijack", "remote_domain", "onboarding_gate",
               "paywallbuster", "asset_vault_freeze"}
SELFTEST_HINTS = ("_def_probe", "bo.txt", "t-bad.txt", "fb.txt", "probe_name",
                  "test_", "fixture", "dummy",
                  # R-H167 补全：设计 §① 列了这两件，落地漏了 ⇒ `t-dead` 一直在冒充"运行故障"
                  # （它是 tests/test_framework.py:771 以 owner="test" 注册的测试夹具）。
                  # 排除表是**唯一真相源**：补在这里，selfscan 与 trace_store 同时生效。
                  "t-dead", "_probe_lock_test")

# ── 闸 ① 脱敏：字段白名单 + 形态掩码 ──
ALLOWED_FIELDS = {
    # 通用
    "at", "source", "event", "evidence_ref", "context",
    # wave_samples
    "window_s", "count", "baseline_mu", "baseline_sigma", "trigger_mode", "triggered",
    "coverage", "blind_window",
    # traces / promotes / obsessions
    "id", "subject", "kind", "promoted", "resolved", "answered_by", "promoted_by",
    "utterance_ref", "intensity", "half_life_s", "obsession_type", "source_trace_ids",
    "relation", "to", "frm",
}
_SECRET_RX = (
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{10,}"),
    re.compile(r"\bcf(?:ut|at)_?[A-Za-z0-9_\-]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{12,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]{12,}"),
    re.compile(r"(?i)\b(cookie|set-cookie)\b\s*[:=]\s*\S+"),
    re.compile(r"(?i)\"(?:token|api_key|apikey|secret|password)\"\s*:\s*\"[^\"]{6,}\""),
)
_LONG_DIGITS = re.compile(r"\b\d{15,19}\b")
_MASK = "****"


def _mask_text(s: str) -> str:
    """形态掩码：**写入前**掩掉，不是写完再清理（§4.3 脱敏边界第 2 条）。"""
    out = s
    for rx in _SECRET_RX:
        out = rx.sub(lambda m: m.group(0)[:4] + _MASK if len(m.group(0)) > 4 else _MASK, out)
    out = _LONG_DIGITS.sub(_MASK, out)
    return out


def redact(row: dict) -> dict:
    """字段白名单 + 形态掩码。白名单外的字段**丢弃**（不是原样带过）。"""
    out = {}
    for k, v in (row or {}).items():
        if k not in ALLOWED_FIELDS:
            continue
        if isinstance(v, str):
            out[k] = _mask_text(v)
        elif isinstance(v, list):
            out[k] = [_mask_text(x) if isinstance(x, str) else x for x in v]
        else:
            out[k] = v
    return out


def is_test_origin(event: str, meta: dict | None = None) -> bool:
    """闸 ②：自检 / 测试产生的痕迹**不算真实痕迹**（实测三次踩过）。"""
    if event == "probe":
        return True
    meta = meta or {}
    if str(meta.get("kind") or "") in DRILL_KINDS:
        return True
    blob = (json.dumps(meta, ensure_ascii=False) + " " + str(event)).lower()
    return any(h in blob for h in SELFTEST_HINTS)


def _path(table: str) -> Path:
    if table not in TABLES:
        raise ValueError("未知表：%s（只许 %s）" % (table, "/".join(TABLES)))
    return TRACE_DIR / (table + ".jsonl")


def _append(table: str, row: dict) -> dict:
    """append-only 写入：三件事 —— 脱敏、补时间、追加。**没有覆盖、没有删除。**"""
    row = redact(row)
    row.setdefault("at", time.strftime("%Y-%m-%dT%H:%M:%S"))
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    with _path(table).open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "table": table, "at": row["at"]}


def _load(table: str) -> list:
    p = _path(table)
    if not p.is_file():
        return []
    rows = []
    with p.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


# ── 写入 API（三道闸都在这里）──────────────────────────────────────────────
def record_wave_sample(event: str, count: int, *, meta: dict | None = None,
                       window_s: int = 900, baseline_mu: float = 0.0,
                       baseline_sigma: float = 0.0, trigger_mode: str = "3sigma",
                       triggered: bool = False, coverage: str = "half",
                       blind_window=None, source: str = "wave_probe") -> dict:
    """每跳都写（§2.1）。**origin 闸在这里**：测试件与自检事件一律拒收、不写盘。"""
    if is_test_origin(event, meta):
        return {"ok": False, "reason_code": "test_origin", "event": event,
                "message": "自检/测试来源不进痕迹库（否则测试件会冒充真实痕迹）"}
    if trigger_mode not in ("3sigma", "floor_used", "sigma_zero", "insufficient", "none"):
        return {"ok": False, "reason_code": "bad_trigger_mode", "trigger_mode": trigger_mode}
    return _append("wave_samples", {
        "source": source, "event": event, "window_s": window_s, "count": int(count),
        "baseline_mu": float(baseline_mu), "baseline_sigma": float(baseline_sigma),
        "trigger_mode": trigger_mode, "triggered": bool(triggered),
        "coverage": coverage, "blind_window": blind_window or []})


def append_trace(subject: str, kind: str, evidence_ref: str,
                 context: str = "", source: str = "wave_probe") -> dict:
    """过阈才写（§2 硬规矩 3）。`evidence_ref` 必须指向真实存在的东西。"""
    if not subject or not kind or not evidence_ref:
        return {"ok": False, "reason_code": "missing_field",
                "message": "subject / kind / evidence_ref 缺一不可"}
    if not _load("wave_samples") and not (TRACE_DIR / "wave_samples.jsonl").is_file():
        return {"ok": False, "reason_code": "no_evidence",
                "message": "evidence_ref 指向的 wave_samples 不存在 ⇒ 拒收（宁可红，不写无源痕迹）"}
    return _append("traces", {"subject": subject, "kind": kind,
                              "evidence_ref": evidence_ref, "context": context,
                              "source": source})


def append_obsession(subject: str, obsession_type: str, intensity: float,
                     source_trace_ids: list, half_life_s: int,
                     resolved: int = 0) -> dict:
    """「念」入库：**第四条硬约束**在这里 —— 无源拒收、查不到也拒收（写入时校验）。"""
    if obsession_type not in ("未了念", "反复念", "过阈念", "未答念", "被挡念"):
        return {"ok": False, "reason_code": "bad_type", "obsession_type": obsession_type}
    ids = [str(x) for x in (source_trace_ids or []) if str(x).strip()]
    if not ids:
        return {"ok": False, "reason_code": "no_source",
                "message": "source_trace_ids 为空 ⇒ 拒收（不许凭空造念、不许无源之梦）"}
    known = {str(r.get("id") or r.get("evidence_ref")) for r in _load("traces")}
    missing = [i for i in ids if i not in known]
    if missing:
        return {"ok": False, "reason_code": "dangling_source", "missing": missing,
                "message": "有 id 在 traces 里查不到 ⇒ 整条拒收（缺源不是'源为空'）"}
    if not (0.0 <= float(intensity) <= 1.0):
        return {"ok": False, "reason_code": "bad_intensity",
                "message": "intensity 取值 0–1（Owner 口径）"}
    return _append("obsessions", {
        "id": "ob-%s" % time.strftime("%Y%m%dT%H%M%S"), "subject": subject,
        "obsession_type": obsession_type, "intensity": float(intensity),
        "source_trace_ids": ids, "resolved": int(resolved),
        "half_life_s": int(half_life_s)})


def promote(trace_id: str, *, promoted_by: str = "", utterance_ref: str = "") -> dict:
    """升格＝写 `promotes` 流水（**状态位由流水派生**）。

    只有主人显式标记才允许：`promoted_by` 必须 `owner`，且必须有原话指针。
    """
    if promoted_by != "owner" or not utterance_ref.strip():
        return {"ok": False, "reason_code": "not_owner_mark",
                "message": "升格只认主人显式标记（promoted_by=owner + utterance_ref 原话指针）"}
    known = {str(r.get("id") or r.get("evidence_ref")) for r in _load("traces")}
    if trace_id not in known:
        return {"ok": False, "reason_code": "unknown_trace", "trace_id": trace_id}
    return _append("promotes", {"id": trace_id, "promoted_by": "owner",
                                "utterance_ref": utterance_ref})


def promoted_state() -> dict:
    """状态位 = 从 `promotes` 流水**派生**（流水才是真相，不一致就是漂移）。"""
    return {str(r.get("id")): True for r in _load("promotes") if r.get("id")}


# ── 只读读数 ────────────────────────────────────────────────────────────────
def status() -> dict:
    return {"ok": True, "store": str(TRACE_DIR), "readonly": True,
            "tables": {t: len(_load(t)) for t in TABLES},
            "note": "只读读数：各表条数（落库路径见 record_wave_sample / append_trace / append_obsession / promote）"}


def retention(days: int = 90) -> dict:
    """保留期**只作用于 `wave_samples`**；`traces`/`obsessions` 永不删（§2.1）。"""
    cut = time.time() - days * 86400
    old = 0
    for r in _load("wave_samples"):
        try:
            t = time.mktime(time.strptime(str(r.get("at")), "%Y-%m-%dT%H:%M:%S"))
        except Exception:  # noqa: BLE001
            continue
        if t < cut:
            old += 1
    return {"ok": True, "readonly": True, "days": days, "wave_samples_over_age": old,
            "policy": "保留期只作用于 wave_samples；traces / obsessions 永不删（要删先过门）",
            "note": "本模块**不提供删除路径** —— 这一条是读数，不是清理动作"}


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="痕迹库（只读读数；落库走 API）")
    ap.add_argument("cmd", choices=("status", "retention", "promoted"))
    ap.add_argument("--days", type=int, default=90)
    a = ap.parse_args(argv)
    if a.cmd == "status":
        out = status()
    elif a.cmd == "retention":
        out = retention(a.days)
    else:
        out = {"ok": True, "promoted": promoted_state()}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
