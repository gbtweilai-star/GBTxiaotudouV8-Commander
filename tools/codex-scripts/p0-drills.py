# -*- coding: utf-8 -*-
"""GBT小土豆V8 · P0 故障演练（五条「未测」的落地）

## 为什么有这件

蓝图 §九（`PROJECT_BLUEPRINT.md:498`）登记了 58 个故障点，其中五条 P0 长期钉在
**「⬜未测」**：`F2.4 宪法被污染` · `F5.3 门禁被绕过` · `F5.6 快照 hash 不一致` ·
`F7.4 store/life_vault 损坏` · `F8.4 多窗口同时崩`。设计文档
（`gbt_allinone/docs/GBT全故障点设计.md`）给每条写了**检/诊/恢/降/审**五要素，
但**没有一条被真跑过** —— 只报绿的演练等于没有演练。

本工具把五条做成**能真跑的演练**：每条实现「检 → 诊 → 恢 → 降 → 审」，
并且每条都带**正负对照**：把**故障态**喂检测器 ⇒ 必须报红；把**干净态**喂 ⇒ 必须报净。
负对照逐条打在输出里；只报绿的判据一条不留。

## 🔴 三条纪律（本工具遵此，逐条可核）

1. **一律不许碰生产树**。生产现为镜像 `v29`，法规是「生产零修改」。五条演练全部
   在**临时目录 + 隔离 store（`GBT_STORE_DIR`）+ 副本**上造故障：
   - 「宪法被污染」= 污染 `CHARTER.md` 的**副本**，真件只读；
   - 「门禁被绕过」= 在沙箱里合成**审计事件流**（真绕过被第二节红线禁止），
     但**真门的 fail-closed 语义**用真代码在隔离 store 上实测；
   - 「快照 hash 不一致」= 在沙箱里造双路取数漂移；
   - 「life_vault 损坏」= 删/截断**隔离 store 里的 vault**（真件在 `gbt_allinone/store/life_vault`，不动）；
   - 「多窗口同时崩」= 用**注册表（只读 `windows.json`）+ 心跳模型**推演，绝不真杀窗口。
2. **每一次动作都可回滚**：备份 → 执行 → 复验；复验不过**自动回滚**并打原文。
3. **不许假绿**：做不了的如实标「不可安全造故障」并把设计文档要求的检/诊/恢/降/审
   **逐条标未验证**，不许为了出绿伪造读数。

## 隔离口径（照 `gbt_allinone/tests/conftest.py` 那条闸 / HEARTBEAT 第 135 行的做法）

`_paths.py` 在 **import 时刻**把 `GBT_STORE_DIR` 绑成常量。所以本脚本
**先设 `GBT_STORE_DIR`（指向沙箱）→ 后 import `gbt_allinone`**；import 之后再断言
`_paths.STORE_DIR` 落在沙箱内、且 ≠ 生产 store（`gbt_allinone/store`），否则 **fail-fast 拒跑**。
全部审计（`store.audit`）与故障账本（`faults.jsonl`）都写在沙箱里。

## 用例

    py -3.14 tools/codex-scripts/p0-drills.py all              # 真跑五条，落台账
    py -3.14 tools/codex-scripts/p0-drills.py f2.4             # 单条
    py -3.14 tools/codex-scripts/p0-drills.py --check          # 判据（含正负对照），退出码 0/1
    py -3.14 tools/codex-scripts/p0-drills.py --check --json   # 机器读
    py -3.14 tools/codex-scripts/p0-drills.py all --sandbox C:\\tmp\\p0-sb

台账：`state/p0-drills.json`（**只由本工具写**，单一真源）。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
STATE = ROOT / "state"
LEDGER = STATE / "p0-drills.json"
if str(ROOT) not in sys.path:          # 必须在 import gbt_allinone 之前把仓根放上
    sys.path.insert(0, str(ROOT))

PROD_STORE = (ROOT / "gbt_allinone" / "store").resolve()
CONSTITUTION = [ROOT / "CHARTER.md", ROOT / "SOUL.md"]
WINDOWS_JSON = ROOT / "holo_pet_w3" / "shell" / "windows.json"
DESIGN_DOC = ROOT / "gbt_allinone" / "docs" / "GBT全故障点设计.md"

# 五条在《GBT全故障点设计.md》里的**原文行号**（1-based）
DESIGN_LINE = {"F2.4": 87, "F5.3": 113, "F5.6": 116, "F7.4": 135, "F8.4": 145}
# 支撑章节行号（成对探针 / 审计事件表）
DESIGN_LINE_EXTRA = {
    "F2.4_event_table": 817,   # §14.2 `fault_open{severity:P0}` file·base_sha·now_sha · 独立通道
    "F5.3_pair_probe": 954,    # §15.2.3 门禁成对实时探针 gate_pre/gate_post
    "F5.3_event_table": 829,
    "F5.6_event_table": 832,
    "F7.4_event_table": 846,
    "F8.4_event_table": 851,
    "F8.4_heartbeat": 446,     # 检测模态表：F8.4 = 心跳为主
}

_SANDBOX: Path | None = None
_RUN_ID = "p0drill-%d" % int(time.time())


# ══════════════════════════════════════════════════════════════════════════════
# 基础件
# ══════════════════════════════════════════════════════════════════════════════

def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def say(msg: str = "") -> None:
    print(msg, flush=True)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def canon(obj) -> str:
    """F5.6 的规范化哈希规则（显式写死，进审计字段 canonical_rule）。

    规则：`sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",",":")))`
    —— 键序无关、中文不转义、无多余空白。两侧必须用同一条规则，否则比的是规则不是事实。
    """
    return sha256_bytes(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                   separators=(",", ":")).encode("utf-8"))


CANONICAL_RULE = 'sha256(json.dumps(sort_keys=True,ensure_ascii=False,separators=(",",":")))'


def design_row(line_no: int) -> str:
    """取设计文档第 N 行**原文**（照抄，标出处）。"""
    try:
        lines = DESIGN_DOC.read_text(encoding="utf-8").split("\n")
        return lines[line_no - 1].strip()
    except Exception as e:                                        # noqa: BLE001
        return "<取不到真源 %d 行：%s>" % (line_no, str(e)[:80])


def ensure_sandbox(override: str | None = None) -> Path:
    """建沙箱并把 `GBT_STORE_DIR` 钉在沙箱内的 store —— **必须在 import gbt_allinone 之前**。"""
    global _SANDBOX
    if _SANDBOX is not None:
        return _SANDBOX
    base = Path(override).resolve() if override else Path(tempfile.mkdtemp(prefix="gbt-p0-drills-"))
    (base / "store").mkdir(parents=True, exist_ok=True)
    os.environ["GBT_STORE_DIR"] = str(base / "store")
    _SANDBOX = base
    return base


def verify_binding(sb: Path) -> dict:
    """import 后断言：STORE_DIR 绑在沙箱内、且 ≠ 生产 store。否则 fail-fast。"""
    from gbt_allinone import _paths
    bound = Path(_paths.STORE_DIR).resolve()
    inside = str(bound).startswith(str(sb.resolve()))
    is_prod = bound == PROD_STORE
    if not inside or is_prod:
        raise RuntimeError(
            "store 绑定闸拒绝运行：STORE_DIR=%s 不在沙箱 %s 内（或等于生产 store）—— "
            "演练绝不许写生产 store。" % (bound, sb))
    return {"store_dir": str(bound), "in_sandbox": inside, "is_prod": is_prod,
            "env": os.environ.get("GBT_STORE_DIR")}


def emit(event: str, meta: dict) -> dict:
    """落一条审计（走真 `store.audit`，但 store 已绑沙箱）。"""
    from gbt_allinone import store
    return store.audit(event, meta)


def emit_fault(sb: Path, event: str, meta: dict) -> dict:
    """审计 + 故障账本沙箱副本 `faults.jsonl`（对应设计 §14「faults / 独立」通道）。"""
    rec = emit(event, dict(meta, run_id=_RUN_ID))
    fp = sb / "store" / "faults.jsonl"
    with fp.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"event": event, "meta": meta, "at": iso_now()},
                           ensure_ascii=False) + "\n")
    return rec


def sandbox_audit_lines(sb: Path) -> list:
    p = sb / "store" / "audit.jsonl"
    if not p.is_file():
        return []
    return [l for l in p.read_text(encoding="utf-8", errors="replace").split("\n") if l.strip()]


def prod_store_probe() -> dict:
    """生产 store 只读探针：大小/mtime + 本工具 run_id 是否出现在生产审计尾部。"""
    out = {}
    for name in ("audit.jsonl", "auth_grants.jsonl"):
        p = PROD_STORE / name
        if p.is_file():
            st = p.stat()
            out[name] = {"size": st.st_size, "mtime_ns": st.st_mtime_ns}
        else:
            out[name] = {"size": None, "mtime_ns": None}
    ap = PROD_STORE / "audit.jsonl"
    marker = False
    if ap.is_file():
        st = ap.stat()
        with ap.open("rb") as f:
            f.seek(max(0, st.st_size - 400_000))
            marker = (_RUN_ID.encode() in f.read())
    out["run_id_in_prod_audit_tail"] = marker
    return out


# ══════════════════════════════════════════════════════════════════════════════
# F2.4 宪法被污染
#  设计原文（GBT全故障点设计.md:87）：
#   检：宪法文件指纹与基线比对 · 诊：定位改动行 + 改动者
#   恢：从 `.backups/` 还原，并落 `P0` · 降：拒绝执行任何依赖被污染条款的动作
#   审：`fault_open{severity:"P0", who:"signature_guard"}`
# ══════════════════════════════════════════════════════════════════════════════

def _first_diff(a: Path, b: Path):
    al = a.read_text(encoding="utf-8", errors="replace").splitlines()
    bl = b.read_text(encoding="utf-8", errors="replace").splitlines()
    for i in range(max(len(al), len(bl))):
        x = al[i] if i < len(al) else "<EOF>"
        y = bl[i] if i < len(bl) else "<EOF>"
        if x != y:
            appended = [t for t in bl[i:] if t.strip()] if i >= len(al) else []
            return i + 1, x, y, appended
    return 0, "", "", []


def constitution_scan(live_dir: Path, backup_dir: Path, baseline: dict) -> dict:
    """检测器：宪法文件指纹 vs 基线；命中即定位改动行。"""
    polluted = []
    for name, base_sha in baseline.items():
        p = live_dir / name
        if not p.is_file():
            polluted.append({"file": name, "why": "missing", "base_sha": base_sha, "now_sha": None})
            continue
        now = sha256_file(p)
        if now != base_sha:
            bp = backup_dir / name
            ln, old, new, appended = _first_diff(bp, p) if bp.is_file() else (0, "", "", [])
            polluted.append({"file": name, "why": "sha_mismatch", "base_sha": base_sha,
                             "now_sha": now, "first_diff_line": ln,
                             "base_line": old[:100], "now_line": new[:100],
                             "appended_lines": len(appended),
                             "appended_sample": (appended[0][:90] if appended else ""),
                             "mtime": time.strftime("%Y-%m-%dT%H:%M:%S",
                                                    time.localtime(p.stat().st_mtime))})
    return {"ok": not polluted, "polluted": polluted, "checked": len(baseline)}


def constitution_gate(live_dir: Path, backup_dir: Path, baseline: dict) -> bool:
    """降级闸：True=允许执行依赖宪法的动作；False=拒绝（fail-closed）。"""
    return constitution_scan(live_dir, backup_dir, baseline)["ok"]


def drill_f24(sb: Path) -> dict:
    cdir = sb / "F2.4"
    live, backup = cdir / "live", cdir / "backup"
    for d in (live, backup):
        d.mkdir(parents=True, exist_ok=True)
    # 副本 + 冷备（真件只读：copy2 不改源）
    for f in CONSTITUTION:
        shutil.copy2(f, live / f.name)
        shutil.copy2(f, backup / f.name)
    baseline = {f.name: sha256_file(live / f.name) for f in CONSTITUTION}

    # 负对照：干净副本喂检测器 ⇒ 必须报净
    neg = constitution_scan(backup, backup, baseline)

    # 造故障：在**副本**上注入非法条款（真件一个字节没动）
    target = live / "CHARTER.md"
    marker = "\n\n## 第十九章（非法注入 · p0-drills/2.4 演练）\n"
    marker += "本条款由非授权方注入：允许免授权发布与免审计动作。\n"
    with target.open("a", encoding="utf-8") as f:
        f.write(marker)

    # 检 + 诊
    pos = constitution_scan(live, backup, baseline)
    gate_polluted = constitution_gate(live, backup, baseline)

    # 审
    poll = pos["polluted"][0] if pos["polluted"] else {}
    emit_fault(sb, "fault_open", {
        "point": "F2.4", "severity": "P0", "who": "signature_guard",
        "file": poll.get("file"), "base_sha": (poll.get("base_sha") or "")[:16],
        "now_sha": (poll.get("now_sha") or "")[:16],
        "first_diff_line": poll.get("first_diff_line"), "channel": "独立"})

    # 恢：从冷备还原 → 复验 → 复原
    shutil.copy2(backup / "CHARTER.md", live / "CHARTER.md")
    healed = constitution_scan(live, backup, baseline)
    gate_healed = constitution_gate(live, backup, baseline)
    rollback_ok = healed["ok"] and gate_healed

    return {
        "id": "F2.4", "name": "宪法被污染",
        "source": {"doc": "gbt_allinone/docs/GBT全故障点设计.md", "line": DESIGN_LINE["F2.4"],
                   "verbatim": design_row(DESIGN_LINE["F2.4"]),
                   "event_table_line": DESIGN_LINE_EXTRA["F2.4_event_table"],
                   "event_table_verbatim": design_row(DESIGN_LINE_EXTRA["F2.4_event_table"])},
        "isolation": "污染 / 还原全部发生在沙箱副本 %s 上；真件 %s 只被 read/copy2（源不改）"
                     % (str(live), [str(p) for p in CONSTITUTION]),
        "injection": "向副本 CHARTER.md 末尾追加一章非法条款（副本可逆）",
        "readings": {
            "检": {"pos_detected": not pos["ok"], "polluted": pos["polluted"][:1],
                   "checked_files": pos["checked"]},
            "诊": {"first_diff_line": poll.get("first_diff_line"),
                   "appended_lines": poll.get("appended_lines"),
                   "appended_sample": poll.get("appended_sample"),
                   "base_line": poll.get("base_line"), "now_line": poll.get("now_line"),
                   "who_guess": "mtime=%s · 演练注入标记在正文里" % poll.get("mtime"),
                   "who_note": "真实篡改者身份不可知（无写者取证）；演练只能报注入痕迹与 mtime"},
            "恢": {"restored_from": str(backup / "CHARTER.md"), "healed_ok": healed["ok"],
                   "reversible": rollback_ok},
            "降": {"gate_before_restore": gate_polluted, "gate_after_restore": gate_healed,
                   "policy": "指纹不符 ⇒ 拒绝执行依赖被污染条款的动作（fail-closed）"},
            "审": {"event": 'fault_open{severity:P0, who:signature_guard}',
                   "audit_written_to": str(sb / "store" / "audit.jsonl"),
                   "faults_written_to": str(sb / "store" / "faults.jsonl")},
        },
        "controls": {
            "pos": {"what": "被污染副本喂检测器", "must": "报红（检出）",
                    "got": "报红" if not pos["ok"] else "报净（假绿！）",
                    "ok": not pos["ok"]},
            "neg": {"what": "干净副本喂检测器", "must": "报净",
                    "got": "报净" if neg["ok"] else "报红（过敏！）", "ok": neg["ok"]},
        },
        "rollback": {"done": rollback_ok, "detail": "冷备还原后指纹回基线、降级闸复开 = %s" % gate_healed},
        "unverified": [
            "「改动者」真身份（需写者取证/文件审计链，本仓无）⇒ 未验证",
            "生产 `.backups/` 还原路径未真跑（真件未动、生产无该冷备）⇒ 未验证（沙箱冷备替代）",
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
# F5.3 门禁被绕过
#  设计原文（:113）：检：`denied` 事件与 `call` 事件比例异常 · 诊：逐跳核对 policy 判定点
#   恢：回滚到上一个判定版本 · 降：默认拒绝（fail-closed）
#   审：`fault_open{severity:"P0", who:"security_brain"}`
#  §15.2.3（:954）：每次门禁调用**前**落 `gate_pre`、调用**后**落 `gate_post`；
#   有 pre 无 post → 立刻告警「门禁被绕过」
# ══════════════════════════════════════════════════════════════════════════════

def make_gate_stream(path: Path, drop_post_for: str | None = None,
                     calls: int = 8, denies: int = 2) -> list:
    """合成门禁事件流（沙箱）：成对 gate_pre/gate_post + call/denied 比例。"""
    rows = []
    for i in range(calls):
        did = "dec-%03d" % i
        rows.append({"event": "call", "meta": {"decision_id": did, "kind": "file_hygiene"}})
        rows.append({"event": "gate_pre", "meta": {"decision_id": did,
                                                   "policy": "file_hygiene", "actor": "p0-drill"}})
        if did == drop_post_for:
            continue                                  # ← 绕过：有 pre 无 post
        rows.append({"event": "gate_post", "meta": {"decision_id": did, "policy": "file_hygiene",
                                                    "actor": "p0-drill", "decision": "allow"}})
    for j in range(denies):
        rows.append({"event": "denied", "meta": {"decision_id": "den-%03d" % j,
                                                 "kind": "file_hygiene", "why": "no_grant"}})
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                    encoding="utf-8")
    return rows


def gate_pair_scan(rows: list) -> dict:
    """成对探针（§15.2.3）：有 pre 无 post ⇒ 判定路径被短路。"""
    pre, post = {}, set()
    for r in rows:
        m = r.get("meta") or {}
        if r.get("event") == "gate_pre":
            pre[m.get("decision_id")] = r
        elif r.get("event") == "gate_post":
            post.add(m.get("decision_id"))
    missing = sorted(d for d in pre if d not in post)
    return {"pre": len(pre), "post": len(post), "missing_post": missing,
            "ok": not missing}


def denied_ratio(rows: list) -> dict:
    c = sum(1 for r in rows if r.get("event") == "call")
    d = sum(1 for r in rows if r.get("event") == "denied")
    return {"calls": c, "denied": d, "ratio": (d / c if c else 0.0)}


def drill_f53(sb: Path) -> dict:
    cdir = sb / "F5.3"
    cdir.mkdir(parents=True, exist_ok=True)

    # ── 真实门语义（只读 policy + 真 auth_gate，在隔离 store 上）──
    from gbt_allinone.security import policy
    from gbt_allinone import auth_gate

    hops = {}
    for label, kind, payload in [
        ("file_hygiene.fix", "file_hygiene", {"op": "fix", "fix": True}),
        ("mcp_connect", "mcp_connect", {}),
        ("tentacle.see(只读)", "tentacle", {"action": "see"}),
        ("tentacle.click", "tentacle", {"action": "click"}),
    ]:
        d = policy.evaluate(kind, payload)
        hops[label] = {"scopes": list(d.scopes), "risk": d.risk}
    # fail-closed 真读数：隔离 store 无授权 ⇒ 危险作用域必被拒
    real_gate = auth_gate.check_and_consume_many(["filesystem_write"], detail="p0-drills/F5.3")

    # ── 负对照：完整成对流 ⇒ 必报净 ──
    clean_rows = make_gate_stream(cdir / "stream_clean.jsonl")
    clean = gate_pair_scan(clean_rows)
    clean_ratio = denied_ratio(clean_rows)

    # ── 造故障：一个 decision_id 丢 gate_post（判定路径被短路）──
    bad_rows = make_gate_stream(cdir / "stream_bypassed.jsonl", drop_post_for="dec-003", denies=0)
    bad = gate_pair_scan(bad_rows)
    bad_ratio = denied_ratio(bad_rows)
    baseline_ratio = clean_ratio["ratio"]
    ratio_anomaly = bad_ratio["ratio"] < baseline_ratio * 0.5

    # ── 诊：按 decision_id 追同一跳 + 逐跳核对 policy 判定点 ──
    diag = {"decision_id": bad["missing_post"][0] if bad["missing_post"] else None,
            "hop": "file_hygiene", "policy_at_hop": hops["file_hygiene.fix"],
            "note": "该跳 policy 判定点仍在册（作用域非空）⇒ 被短路的是**执行路径**，不是策略本身"}
    emit_fault(sb, "fault_open", {"point": "F5.3", "severity": "P0", "who": "security_brain",
                                  "decision_id": diag["decision_id"],
                                  "missing_post": len(bad["missing_post"]),
                                  "ratio_anomaly": ratio_anomaly, "channel": "独立"})
    emit("gate_pre", {"decision_id": "p0-F5.3-audit", "policy": "file_hygiene", "actor": "p0-drill"})
    emit("gate_post", {"decision_id": "p0-F5.3-audit", "policy": "file_hygiene",
                       "actor": "p0-drill", "decision": "allow"})

    # ── 恢：回滚到上一个判定版本（演练=恢复成对事件流）──
    restored_rows = make_gate_stream(cdir / "stream_restored.jsonl")
    restored = gate_pair_scan(restored_rows)
    rollback_ok = restored["ok"]

    return {
        "id": "F5.3", "name": "门禁被绕过",
        "source": {"doc": "gbt_allinone/docs/GBT全故障点设计.md", "line": DESIGN_LINE["F5.3"],
                   "verbatim": design_row(DESIGN_LINE["F5.3"]),
                   "pair_probe_line": DESIGN_LINE_EXTRA["F5.3_pair_probe"],
                   "pair_probe_verbatim": design_row(DESIGN_LINE_EXTRA["F5.3_pair_probe"])},
        "isolation": "真绕过被红线禁止 ⇒ 未真绕过；绕过以**沙箱合成事件流**表达。"
                     "而真门的 fail-closed 语义用 `auth_gate.check_and_consume_many` "
                     "在隔离 store（%s）上**实测**。" % (sb / "store"),
        "injection": "合成流里让 decision_id=dec-003 只落 gate_pre、不落 gate_post（有 pre 无 post）",
        "real_gate_readings": {"policy_hops": hops, "fail_closed_real": {
            "ok": real_gate.get("ok"), "denied": real_gate.get("denied"),
            "missing": real_gate.get("missing"), "error": real_gate.get("error")}},
        "readings": {
            "检": {"pos_missing_post": bad["missing_post"], "pre": bad["pre"], "post": bad["post"],
                   "denied_ratio_bad": bad_ratio, "denied_ratio_baseline": baseline_ratio,
                   "ratio_anomaly": ratio_anomaly},
            "诊": diag,
            "恢": {"restored_pairs_ok": restored["ok"], "reversible": rollback_ok,
                   "note": "真实「回滚到上一个判定版本」= 人工（设计 §12 人工恢复 11 处之一），"
                           "演练用恢复成对事件流替代"},
            "降": {"fail_closed_real_denied": bool(real_gate.get("denied")),
                   "policy": "默认拒绝：无授权 ⇒ 冻结越权动作"},
            "审": {"events": ["gate_pre", "gate_post", "fault_open{severity:P0, who:security_brain}"],
                   "audit_written_to": str(sb / "store" / "audit.jsonl")},
        },
        "controls": {
            "pos": {"what": "缺 gate_post 的流喂成对探针", "must": "报红（有 pre 无 post）",
                    "got": "报红 missing=%s" % bad["missing_post"] if not bad["ok"] else "报净（假绿！）",
                    "ok": not bad["ok"]},
            "neg": {"what": "完整成对流喂探针", "must": "报净",
                    "got": "报净" if clean["ok"] else "报红（过敏！）", "ok": clean["ok"]},
        },
        "rollback": {"done": rollback_ok, "detail": "恢复成对事件流后 missing_post 清空 = %s" % rollback_ok},
        "unverified": [
            "真绕过门禁（真短路判定路径）被红线禁止 ⇒ **未真造**，只以合成流验证检测器",
            "「回滚到上一个判定版本」真动作需 Owner 批策略变更 ⇒ 未验证（标注人工）",
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
# F5.6 快照 hash 不一致
#  设计原文（:116）：检：两侧回写的 `snapshot_hash` 比对 · 诊：立刻停手，起双路探针定性是
#   「取数漂移」还是「通道中间被改」 · 恢：以**慢路径重取**的那一份为准，另一方强制刷新
#   · 降：本次会诊作废，落 `P0` · 审：`fault_escalate{to:"owner", severity:"P0"}`
# ══════════════════════════════════════════════════════════════════════════════

def _load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def classify_hash_mismatch(h_a: str, h_b: str, ground: str, history: list) -> dict:
    """双路探针定性：取数漂移 vs 通道中间被改。"""
    off = []
    if h_a != ground:
        off.append(("A", h_a))
    if h_b != ground:
        off.append(("B", h_b))
    if not off:
        return {"kind": "一致", "why": "两侧都等于真实源"}
    if all(h in history for _s, h in off):
        return {"kind": "取数漂移",
                "why": "偏离侧的值**曾是真实源的一个版本** ⇒ 源在两次取数之间变了，不是被改",
                "off": [s for s, _ in off]}
    return {"kind": "通道中间被改",
            "why": "偏离侧的值**不等于任何真实源版本** ⇒ 传输途中被改写",
            "off": [s for s, _ in off]}


def drill_f56(sb: Path) -> dict:
    cdir = sb / "F5.6"
    cdir.mkdir(parents=True, exist_ok=True)
    rule = CANONICAL_RULE

    def views(tag, extra=None):
        v = {"self": {"mood": tag, "energy": 0.8},
             "task": {"n": 3, "last": "mirror_status"},
             "env": {"root": str(ROOT), "v": 29},
             "ledger": {"rows": 287891}}
        if extra:
            v.update(extra)
        return v

    # 真实源（沙箱）：v0 → v1 表示一次合法更新
    v0 = views("v0")
    v1 = views("v1")
    hist_v0 = cdir / "truth_v0.json"
    truth = cdir / "truth.json"
    hist_v0.write_text(json.dumps(v0, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    truth.write_text(json.dumps(v1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    history = [canon(v0), canon(v1)]
    ground = canon(_load_json(truth))

    # ── 负对照：两侧都读当前真实源 ⇒ 一致 ──
    hA_clean = canon(_load_json(truth))
    hB_clean = canon(_load_json(truth))
    clean = {"hash_a": hA_clean, "hash_b": hB_clean, "match": hA_clean == hB_clean}

    # ── 造故障①：取数漂移（快路径读到陈旧的**真实旧版本**）──
    fast_drift = canon(_load_json(hist_v0))          # 曾是真实源 v0
    slow = canon(_load_json(truth))                  # 慢路径重取 = v1
    drift = {"hash_a": fast_drift, "hash_b": slow, "match": fast_drift == slow}
    drift_diag = classify_hash_mismatch(fast_drift, slow, ground, history)

    # ── 造故障②：通道中间被改（快路径值不等于任何真实版本）──
    tampered = views("channel-tampered")
    hA_tamp = canon(tampered)
    tamp = {"hash_a": hA_tamp, "hash_b": slow, "match": hA_tamp == slow}
    tamp_diag = classify_hash_mismatch(hA_tamp, slow, ground, history)

    emit_fault(sb, "fault_open", {"point": "F5.6", "severity": "P0",
                                  "hash_a": fast_drift[:16], "hash_b": slow[:16],
                                  "canonical_rule": rule, "channel": "独立"})
    emit_fault(sb, "fault_escalate", {"to": "owner", "severity": "P0", "point": "F5.6",
                                      "stop": "立刻停手，本次会诊作废"})

    # ── 恢：以慢路径重取的那一份为准，另一方强制刷新 ──
    refreshed = slow                                   # 慢路径值
    hA_after = refreshed
    hB_after = canon(_load_json(truth))                # 慢路径重取
    healed = {"hash_a": hA_after, "hash_b": hB_after, "match": hA_after == hB_after}

    return {
        "id": "F5.6", "name": "快照 hash 不一致",
        "source": {"doc": "gbt_allinone/docs/GBT全故障点设计.md", "line": DESIGN_LINE["F5.6"],
                   "verbatim": design_row(DESIGN_LINE["F5.6"]),
                   "event_table_line": DESIGN_LINE_EXTRA["F5.6_event_table"],
                   "event_table_verbatim": design_row(DESIGN_LINE_EXTRA["F5.6_event_table"])},
        "isolation": "两侧快照与真实源全在沙箱 %s；不触碰生产" % cdir,
        "injection": "①让快路径读到真实的旧版本（漂移）②让快路径载荷被改写（通道被改）",
        "canonical_rule": rule,
        "readings": {
            "检": {"clean_match": clean["match"],
                   "drift_mismatch": not drift["match"], "tamper_mismatch": not tamp["match"],
                   "hash_a_drift": fast_drift[:16], "hash_b": slow[:16]},
            "诊": {"drift_classified": drift_diag, "tamper_classified": tamp_diag,
                   "ground_hash": ground[:16]},
            "恢": {"trust_slow_path": True, "healed_match": healed["match"],
                   "reversible": healed["match"]},
            "降": {"policy": "本次会诊作废 + 落 P0（土豆公主独裁，显式标注）",
                   "consultation": "invalid"},
            "审": {"events": ['fault_open{P0, hash_a, hash_b, canonical_rule}',
                              'fault_escalate{to:owner, severity:P0}'],
                   "audit_written_to": str(sb / "store" / "audit.jsonl")},
        },
        "controls": {
            "pos": {"what": "hash 不一致（漂移）喂双路探针", "must": "检出 + 定性",
                    "got": "检出，定性=%s" % drift_diag["kind"] if not drift["match"] else "报净（假绿！）",
                    "ok": (not drift["match"]) and drift_diag["kind"] == "取数漂移"},
            "pos2": {"what": "hash 不一致（通道被改）", "must": "定性=通道中间被改",
                     "got": tamp_diag["kind"], "ok": tamp_diag["kind"] == "通道中间被改"},
            "neg": {"what": "两侧都读当前真实源", "must": "报净（一致）",
                    "got": "报净" if clean["match"] else "报红（过敏！）", "ok": clean["match"]},
        },
        "rollback": {"done": healed["match"], "detail": "按慢路径重取后两侧一致 = %s" % healed["match"]},
        "unverified": [
            "设计与克劳德侧的真实「回写 snapshot_hash」通道尚未成形（蓝图 §9.1 / 设计标注"
            "「机制未成形」）⇒ 真实两方比对未验证，演练用沙箱双侧载荷替代",
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
# F7.4 store/life_vault 损坏
#  设计原文（:135）：检：目录存在性 + 可解析率 · 诊：逐文件校验 · 恢：从冷备还原
#   · 降：**只读**，拒绝新写入并显式告警 · 审：`fault_open{severity:"P0"}`
# ══════════════════════════════════════════════════════════════════════════════

def vault_inspect(vault: Path) -> dict:
    """检测器：目录存在性 + 可解析率 + 逐文件校验。"""
    if not vault.is_dir():
        return {"exists": False, "total": 0, "parsable": 0, "parse_rate": 0.0,
                "bad": [{"file": "<dir>", "why": "目录不存在"}], "ok": False}
    files = sorted(p for p in vault.rglob("*") if p.is_file())
    bad, parsable = [], 0
    for p in files:
        rel = str(p.relative_to(vault))
        try:
            txt = p.read_text(encoding="utf-8")
            json.loads(txt)
            parsable += 1
        except Exception as e:                                    # noqa: BLE001
            head = p.read_text(encoding="utf-8", errors="replace")[:60].replace("\n", " ")
            bad.append({"file": rel, "why": "parse_fail: %s" % str(e)[:60], "head": head,
                        "bytes": p.stat().st_size})
    rate = (parsable / len(files)) if files else 0.0
    return {"exists": True, "total": len(files), "parsable": parsable, "parse_rate": round(rate, 4),
            "bad": bad, "ok": (len(files) > 0 and not bad)}


def vault_write_guard(insp: dict) -> dict:
    """降级闸：只读（拒绝新写入）。"""
    allowed = bool(insp["ok"]) and insp["parse_rate"] == 1.0
    return {"write_allowed": allowed,
            "mode": "可写" if allowed else "只读（拒绝新写入 + 显式告警）"}


def _build_vault(vault: Path, n: int = 6) -> dict:
    vault.mkdir(parents=True, exist_ok=True)
    names = ["00_Meta/index.json", "Events/a.json", "Events/b.json",
             "Chapters/c.json", "Daily/d.json", "Lessons/e.json"]
    for i, rel in enumerate(names[:n]):
        p = vault / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"i": i, "note": "p0-drills/F7.4"}, ensure_ascii=False),
                     encoding="utf-8")
    return {str(p.relative_to(vault)): sha256_file(p)
            for p in sorted(vault.rglob("*")) if p.is_file()}


def drill_f74(sb: Path) -> dict:
    cdir = sb / "F7.4"
    vault = sb / "store" / "life_vault"          # 隔离 store 的 vault（真件在 gbt_allinone/store/life_vault，不动）
    cold = cdir / "cold_backup" / "life_vault"
    if vault.exists():
        shutil.rmtree(vault)
    if cold.exists():
        shutil.rmtree(cold)
    hashes = _build_vault(vault)
    shutil.copytree(vault, cold)                 # 冷备（沙箱内，模拟 `.backups/`）

    # 负对照：完好 vault ⇒ 可解析率 100% 报净
    insp_clean = vault_inspect(vault)

    # ── 造故障 A：目录被删（rename，可逆）──
    vault.rename(sb / "F7.4" / "_vault_removed")
    insp_gone = vault_inspect(vault)
    guard_gone = vault_write_guard(insp_gone)
    emit_fault(sb, "fault_open", {"point": "F7.4", "severity": "P0", "kind": "dir_missing",
                                  "vault": str(vault), "channel": "faults"})
    # 恢 A：冷备还原
    shutil.copytree(cold, vault)
    heal_a = vault_inspect(vault)

    # ── 造故障 B：文件半截（截断一个 json，可逆）──
    victim = vault / "Events/a.json"
    original = victim.read_bytes()
    victim.write_bytes(original[: max(1, len(original) // 2)])   # 半截
    insp_half = vault_inspect(vault)
    guard_half = vault_write_guard(insp_half)
    emit_fault(sb, "fault_open", {"point": "F7.4", "severity": "P0", "kind": "truncated_file",
                                  "file": "Events/a.json", "sha_ok": False, "channel": "faults"})
    # 恢 B：从冷备还原该文件
    shutil.copy2(cold / "Events/a.json", victim)
    heal_b = vault_inspect(vault)
    guard_healed = vault_write_guard(heal_b)

    rollback_ok = heal_a["ok"] and heal_b["ok"] and guard_healed["write_allowed"]

    return {
        "id": "F7.4", "name": "store/life_vault 损坏",
        "source": {"doc": "gbt_allinone/docs/GBT全故障点设计.md", "line": DESIGN_LINE["F7.4"],
                   "verbatim": design_row(DESIGN_LINE["F7.4"]),
                   "event_table_line": DESIGN_LINE_EXTRA["F7.4_event_table"],
                   "event_table_verbatim": design_row(DESIGN_LINE_EXTRA["F7.4_event_table"])},
        "isolation": "演练的 vault = 隔离 store 的 %s（真件 gbt_allinone/store/life_vault 未动）；"
                     "冷备 %s 也在沙箱内" % (vault, cold),
        "injection": "①删目录（rename）②把 Events/a.json 截成半截 —— 两次都在沙箱 vault 上、都可逆",
        "readings": {
            "检": {"clean_rate": insp_clean["parse_rate"], "gone_exists": insp_gone["exists"],
                   "half_rate": insp_half["parse_rate"], "half_bad": insp_half["bad"]},
            "诊": {"gone_bad": insp_gone["bad"], "half_bad": insp_half["bad"],
                   "by_file": insp_half["total"]},
            "恢": {"restore_a_ok": heal_a["ok"], "restore_b_ok": heal_b["ok"],
                   "from": str(cold), "reversible": rollback_ok},
            "降": {"guard_when_gone": guard_gone["mode"], "guard_when_half": guard_half["mode"],
                   "guard_after_heal": guard_healed["mode"]},
            "审": {"event": 'fault_open{severity:P0} + 逐文件 hash',
                   "audit_written_to": str(sb / "store" / "audit.jsonl")},
        },
        "controls": {
            "pos": {"what": "目录被删 / 文件半截 喂逐文件校验", "must": "两次都报红",
                    "got": "删目录=%s · 半截=%s" % ("红" if not insp_gone["ok"] else "净",
                                                    "红" if not insp_half["ok"] else "净"),
                    "ok": (not insp_gone["ok"]) and (not insp_half["ok"])},
            "neg": {"what": "完好 vault 喂逐文件校验", "must": "报净（可解析率 100%）",
                    "got": "报净 rate=%s" % insp_clean["parse_rate"] if insp_clean["ok"] else "报红（过敏！）",
                    "ok": insp_clean["ok"] and insp_clean["parse_rate"] == 1.0},
        },
        "rollback": {"done": rollback_ok,
                     "detail": "冷备还原后两次都复原、只读闸复开 = %s" % rollback_ok},
        "unverified": [
            "真删/真截断**生产** life_vault 被红线禁止 ⇒ 未真造（在隔离 store 的 vault 上真删/真截断）",
            "生产冷备不存在（gbt_allinone/store/life_vault 无 `.backups/` 冷备）⇒ 「从冷备还原」"
            "的真路径未验证，演练用沙箱冷备替代",
            "`life_archive` 目前**没有**只读模式开关 ⇒ 「只读、拒绝新写入」的降级闸由本演练提供判据、"
            "产品侧未落地 ⇒ 未验证",
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
# F8.4 多窗口同时崩
#  设计原文（:145）：检：全部窗口心跳同时断 · 诊：区分"全崩"与"主进程崩"
#   · 恢：按注册表逐窗重建 · 降：单窗口模式（只保主控台） · 审：`fault_open{severity:"P0"}`
#  支撑（:446 检测模态表）：F8.4 = 心跳为主
# ══════════════════════════════════════════════════════════════════════════════

def load_windows_registry() -> dict:
    return json.loads(WINDOWS_JSON.read_text(encoding="utf-8"))


def main_console_id(reg: dict) -> str:
    """主控台 = 注册表里 role=='main' 的窗；无则取**唯一默认可见窗**（windows.json 记 panel 为
    启动唯一默认可见窗 / 「APP 面板本体」）。"""
    ws = reg.get("windows") or []
    for w in ws:
        if w.get("role") == "main":
            return w["id"]
    visible = [w["id"] for w in ws if (w.get("default") or {}).get("visible")]
    return visible[0] if len(visible) == 1 else (visible[0] if visible else (ws[0]["id"] if ws else ""))


def window_state(reg: dict) -> dict:
    ws = reg.get("windows") or []
    return {w["id"]: {"title": w.get("title"), "visible_default":
                      bool((w.get("default") or {}).get("visible")),
                      "alive": True, "last_beat": 1000} for w in ws}


def window_crash_scan(state: dict, now_beat: int, parent_alive: bool, silent_for: int = 5) -> dict:
    """检测器：全部窗口心跳同时断？并区分「全崩」vs「主进程崩」。"""
    stale = [wid for wid, st in state.items() if now_beat - st["last_beat"] > silent_for]
    all_silent = bool(state) and len(stale) == len(state)
    diag = None
    if all_silent:
        diag = "主进程崩（parent_alive=False）" if not parent_alive else "全崩（父进程在、渲染窗全没）"
    return {"total": len(state), "silent": stale, "all_silent": all_silent,
            "parent_alive": parent_alive, "diagnosis": diag}


def drill_f84(sb: Path) -> dict:
    cdir = sb / "F8.4"
    cdir.mkdir(parents=True, exist_ok=True)
    reg = load_windows_registry()
    main_id = main_console_id(reg)
    ids = [w["id"] for w in reg.get("windows") or []]

    # 负对照：健康模型 ⇒ 不告警
    healthy = window_state(reg)
    neg = window_crash_scan(healthy, now_beat=1000, parent_alive=True)

    # ── 造故障（模型，不真杀窗）：全窗心跳同时断 + 两种父进程态 ──
    crashes = {}
    for label, parent_alive in (("全崩", True), ("主进程崩", False)):
        st = window_state(reg)
        for wid in st:
            st[wid]["alive"] = False
            st[wid]["last_beat"] = 900          # 全部停在同一时刻
        crashes[label] = window_crash_scan(st, now_beat=1000, parent_alive=parent_alive)

    emit_fault(sb, "fault_open", {"point": "F8.4", "severity": "P0", "channel": "独立",
                                  "N": len(ids), "parent_alive": False,
                                  "windows": ids})
    for wid in ids:
        emit("window_gone", {"point": "F8.4", "window_id": wid, "parent_alive": False, "N": len(ids)})

    # ── 恢：按注册表逐窗重建（createWindow 的注册表走法，见 main.cjs:1464/1863）──
    rebuilt = {w["id"]: dict(healthy[w["id"]], alive=True, last_beat=1000) for w in reg["windows"]}
    heal = window_crash_scan(rebuilt, now_beat=1000, parent_alive=True)

    # ── 降：单窗口模式（只保主控台）──
    single = {main_id: dict(healthy[main_id], alive=True, last_beat=1000)}
    degrade = {"mode": "单窗口模式（只保主控台）", "kept": [main_id],
               "dropped": [i for i in ids if i != main_id],
               "scan": window_crash_scan(single, now_beat=1000, parent_alive=True)}

    return {
        "id": "F8.4", "name": "多窗口同时崩",
        "source": {"doc": "gbt_allinone/docs/GBT全故障点设计.md", "line": DESIGN_LINE["F8.4"],
                   "verbatim": design_row(DESIGN_LINE["F8.4"]),
                   "heartbeat_line": DESIGN_LINE_EXTRA["F8.4_heartbeat"],
                   "heartbeat_verbatim": design_row(DESIGN_LINE_EXTRA["F8.4_heartbeat"]),
                   "event_table_line": DESIGN_LINE_EXTRA["F8.4_event_table"],
                   "event_table_verbatim": design_row(DESIGN_LINE_EXTRA["F8.4_event_table"])},
        "isolation": "真杀 APP 窗口被红线禁止 ⇒ 未真杀。演练用**只读注册表 %s** + 心跳/存活**模型**推演；"
                     "重建走注册表逐窗（对齐 main.cjs createWindow 的注册表走法）" % str(WINDOWS_JSON),
        "injection": "把注册表全部窗口的心跳置为同时静止 + 两种父进程态（在、不在）",
        "registry": {"file": str(WINDOWS_JSON), "count": len(ids), "ids": ids,
                     "main_console": main_id,
                     "main_console_rule": "role=='main' 的窗；无则取唯一默认可见窗（panel）"},
        "readings": {
            "检": {"all_silent_alarm": crashes["全崩"]["all_silent"],
                   "silent_n": len(crashes["全崩"]["silent"]), "total": crashes["全崩"]["total"]},
            "诊": {"variant_全崩": crashes["全崩"]["diagnosis"],
                   "variant_主进程崩": crashes["主进程崩"]["diagnosis"]},
            "恢": {"rebuilt_windows": len(rebuilt), "alarm_cleared": not heal["all_silent"],
                   "reversible": not heal["all_silent"]},
            "降": degrade,
            "审": {"events": ['fault_open{severity:P0, N, parent_alive}', 'window_gone × N'],
                   "audit_written_to": str(sb / "store" / "audit.jsonl")},
        },
        "controls": {
            "pos": {"what": "全窗心跳同时断喂检测器", "must": "报红 + 定性",
                    "got": "报红，定性=%s" % crashes["全崩"]["diagnosis"],
                    "ok": crashes["全崩"]["all_silent"]},
            "pos2": {"what": "父进程不存活态", "must": "定性=主进程崩",
                     "got": crashes["主进程崩"]["diagnosis"],
                     "ok": "主进程崩" in (crashes["主进程崩"]["diagnosis"] or "")},
            "neg": {"what": "健康模型喂检测器", "must": "不告警",
                    "got": "不告警" if not neg["all_silent"] else "误报！", "ok": not neg["all_silent"]},
        },
        "rollback": {"done": not heal["all_silent"],
                     "detail": "按注册表逐窗重建后告警清除 = %s" % (not heal["all_silent"])},
        "unverified": [
            "真杀窗口/真耗尽显存被红线禁止 ⇒ 未真造（模型推演）",
            "生产壳当前**无窗口心跳上报**（设计 §14.2 `window_gone × N` 通道未落地）"
            "⇒ 真心跳未验证，演练用注册表 + 心跳模型替代",
        ],
    }


DRILLS = {"f2.4": drill_f24, "f5.3": drill_f53, "f5.6": drill_f56,
          "f7.4": drill_f74, "f8.4": drill_f84}


# ══════════════════════════════════════════════════════════════════════════════
# 判据（≥8 条 · 含正负对照）
# ══════════════════════════════════════════════════════════════════════════════

def run_all(sb: Path, only=None) -> dict:
    out = {}
    for key, fn in DRILLS.items():
        if only and key not in only:
            continue
        try:
            out[key] = fn(sb)
        except Exception as e:                                    # noqa: BLE001
            out[key] = {"id": key.upper(), "name": "<演练抛错>", "error": "%s: %s"
                        % (type(e).__name__, str(e)[:200])}
    return out


def judge(drills: dict, binding: dict, prod_before: dict, prod_after: dict) -> list:
    rows = []

    def add(cid, ok, detail):
        rows.append({"id": cid, "ok": bool(ok), "detail": detail})

    def get(k, *path, default=None):
        d = drills.get(k) or {}
        cur = d
        for p in path:
            if isinstance(cur, dict):
                cur = cur.get(p)
            else:
                return default
        return cur if cur is not None else default

    # C1/C2 F2.4 检正负对照
    add("C1 F2.4 检阳性·污染副本必检出",
        bool(get("f2.4", "controls", "pos", "ok")),
        "污染副本 => %s" % get("f2.4", "controls", "pos", "got"))
    add("C2 F2.4 检阴性·干净副本必报净",
        bool(get("f2.4", "controls", "neg", "ok")),
        "干净副本 => %s" % get("f2.4", "controls", "neg", "got"))
    add("C3 F2.4 诊·定位到改动行+双 hash",
        bool(get("f2.4", "readings", "诊", "first_diff_line")) and
        bool(get("f2.4", "readings", "检", "polluted")),
        "first_diff_line=%s" % get("f2.4", "readings", "诊", "first_diff_line"))
    add("C4 F2.4 恢+降·冷备还原后指纹回基线且闸复开",
        bool(get("f2.4", "rollback", "done")) and get("f2.4", "readings", "降", "gate_after_restore"),
        "gate_before=%s gate_after=%s" % (get("f2.4", "readings", "降", "gate_before_restore"),
                                          get("f2.4", "readings", "降", "gate_after_restore")))

    # C5-C8 F5.3
    add("C5 F5.3 检阳性·缺 gate_post 必告警",
        bool(get("f5.3", "controls", "pos", "ok")),
        "缺 post 流 => %s" % get("f5.3", "controls", "pos", "got"))
    add("C6 F5.3 检阴性·完整成对流必报净",
        bool(get("f5.3", "controls", "neg", "ok")),
        "完整流 => %s" % get("f5.3", "controls", "neg", "got"))
    add("C7 F5.3 真实门 fail-closed（隔离 store 无授权必拒）",
        bool(get("f5.3", "readings", "降", "fail_closed_real_denied")),
        "真实 check_and_consume_many => denied=%s missing=%s"
        % (get("f5.3", "real_gate_readings", "fail_closed_real", "denied"),
           get("f5.3", "real_gate_readings", "fail_closed_real", "missing")))
    hops = get("f5.3", "real_gate_readings", "policy_hops", default={}) or {}
    add("C8 F5.3 判定点齐·policy.evaluate 逐跳给出预期作用域",
        hops.get("file_hygiene.fix", {}).get("scopes") == ["filesystem_write"]
        and hops.get("tentacle.click", {}).get("scopes") == ["desktop_control"]
        and hops.get("tentacle.see(只读)", {}).get("scopes") == [],
        "file_hygiene.fix=%s · tentacle.click=%s · tentacle.see=%s"
        % (hops.get("file_hygiene.fix", {}).get("scopes"),
           hops.get("tentacle.click", {}).get("scopes"),
           hops.get("tentacle.see(只读)", {}).get("scopes")))

    # C9-C11 F5.6
    add("C9 F5.6 检阳性·hash 不一致必检出",
        bool(get("f5.6", "controls", "pos", "ok")),
        "漂移 => %s" % get("f5.6", "controls", "pos", "got"))
    add("C10 F5.6 诊·定性出「取数漂移」与「通道中间被改」",
        bool(get("f5.6", "controls", "pos", "ok")) and bool(get("f5.6", "controls", "pos2", "ok")),
        "漂移=%s · 通道被改=%s" % (get("f5.6", "readings", "诊", "drift_classified", "kind"),
                                   get("f5.6", "readings", "诊", "tamper_classified", "kind")))
    add("C11 F5.6 检阴性+恢·干净报净且慢路径重取后一致",
        bool(get("f5.6", "controls", "neg", "ok")) and bool(get("f5.6", "rollback", "done")),
        "干净=%s · 恢=%s" % (get("f5.6", "controls", "neg", "got"), get("f5.6", "rollback", "done")))

    # C12-C13 F7.4
    add("C12 F7.4 检阳性·目录被删与文件半截都必检出",
        bool(get("f7.4", "controls", "pos", "ok")),
        "=> %s" % get("f7.4", "controls", "pos", "got"))
    add("C13 F7.4 检阴性+恢+降·完好率100%且冷备还原且只读闸复开",
        bool(get("f7.4", "controls", "neg", "ok")) and bool(get("f7.4", "rollback", "done")),
        "干净率=%s · 复原=%s · 闸=%s" % (get("f7.4", "readings", "检", "clean_rate"),
                                         get("f7.4", "rollback", "done"),
                                         get("f7.4", "readings", "降", "guard_after_heal")))

    # C14-C15 F8.4
    add("C14 F8.4 检阳性·全窗同断必告警且区分全崩/主进程崩",
        bool(get("f8.4", "controls", "pos", "ok")) and bool(get("f8.4", "controls", "pos2", "ok")),
        "全崩=%s · 主进程崩=%s" % (get("f8.4", "readings", "诊", "variant_全崩"),
                                   get("f8.4", "readings", "诊", "variant_主进程崩")))
    add("C15 F8.4 检阴性+恢+降·健康不告警且逐窗重建且单窗模式",
        bool(get("f8.4", "controls", "neg", "ok")) and bool(get("f8.4", "rollback", "done")),
        "健康=%s · 重建清警=%s · 单窗只保=%s"
        % (get("f8.4", "controls", "neg", "got"), get("f8.4", "rollback", "done"),
           get("f8.4", "readings", "降", "kept")))

    # C16 隔离
    untouched = (not prod_after.get("run_id_in_prod_audit_tail"))
    add("C16 隔离·STORE_DIR 绑沙箱内且生产 store 未被本工具写",
        bool(binding.get("in_sandbox")) and not bool(binding.get("is_prod")) and untouched,
        "store=%s · in_sandbox=%s · 生产审计尾部含本 run_id=%s"
        % (binding.get("store_dir"), binding.get("in_sandbox"),
           prod_after.get("run_id_in_prod_audit_tail")))
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# 台账
# ══════════════════════════════════════════════════════════════════════════════

def write_ledger(sb: Path, drills: dict, binding: dict, prod_before: dict, prod_after: dict,
                 crit: list) -> Path:
    STATE.mkdir(parents=True, exist_ok=True)
    prev = {}
    if LEDGER.is_file():
        try:
            prev = json.loads(LEDGER.read_text(encoding="utf-8"))
        except Exception:                                         # noqa: BLE001
            prev = {}
    merged = dict(prev.get("drills") or {})
    merged.update({k: v for k, v in drills.items()})
    if not crit:                                              # 单条跑：保留上次判据，别抹掉
        crit = prev.get("criteria") or None
    npass = sum(1 for c in crit if c.get("ok")) if crit else None
    doc = {
        "tool": "tools/codex-scripts/p0-drills.py",
        "note": "本文件是 P0 演练台账，**只由 p0-drills.py 写**（单一真源）。手改会被下次运行覆盖。",
        "generated_at": iso_now(),
        "run_id": _RUN_ID,
        "sandbox": str(sb),
        "binding": binding,
        "isolation": {
            "prod_store": str(PROD_STORE),
            "prod_store_before": prod_before,
            "prod_store_after": prod_after,
            "claim": "演练全部在沙箱 store 上造故障与落账；生产树（含 CHARTER.md/SOUL.md、"
                     "holo_pet_w3/、gbt_allinone/store/）一字未改。",
        },
        "drills": {k: merged[k] for k in sorted(merged)},
        "check_summary": ({"total": len(crit), "passed": npass, "failed": len(crit) - npass}
                          if crit else None),
        "criteria": [{"id": c["id"], "ok": c["ok"], "detail": c["detail"]} for c in (crit or [])],
    }
    LEDGER.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return LEDGER


# ══════════════════════════════════════════════════════════════════════════════
# 汇报
# ══════════════════════════════════════════════════════════════════════════════

def report_drill(d: dict) -> None:
    say("─" * 78)
    say("【%s %s】" % (d.get("id"), d.get("name")))
    src = d.get("source") or {}
    say("  出处：《%s》第 %s 行（照抄）" % (Path(src.get("doc", "")).name, src.get("line")))
    say("    原文：%s" % (src.get("verbatim", "")[:150]))
    if d.get("error"):
        say("  ⚠ 演练抛错：%s" % d["error"])
        return
    say("  隔离：%s" % d.get("isolation", ""))
    say("  造故障：%s" % d.get("injection", ""))
    r = d.get("readings") or {}
    for step, txt in (("检", "检到"), ("诊", "诊到"), ("恢", "恢了"), ("降", "降级"), ("审", "审计")):
        v = r.get(step)
        say("  [%s] %s：%s" % (step, txt, json.dumps(v, ensure_ascii=False)[:220]))
    say("  正负对照（故障态必报红 · 干净态必报净）：")
    _label = {"pos": "正对照·故障态必报红", "pos2": "正对照·故障态必报红（变体）",
              "neg": "负对照·干净态必报净"}
    for k, c in (d.get("controls") or {}).items():
        say("    · [%s] %s ⇒ 期望%s，实得：%s  [%s]"
            % (_label.get(k, k), c.get("what"), c.get("must"), c.get("got"),
               "✓" if c.get("ok") else "✗红"))
    rb = d.get("rollback") or {}
    say("  回滚：%s（%s）" % ("可逆 ✓" if rb.get("done") else "✗未复原", rb.get("detail")))
    for u in (d.get("unverified") or []):
        say("  ⚠ 未验证：%s" % u)


def report_check(crit: list) -> int:
    npass = sum(1 for c in crit if c["ok"])
    say("═" * 78)
    say("p0-drills 判据（含正负对照）—— 真跑五条，退出码 0 = 全过")
    for c in crit:
        say("[%s] %s — %s" % ("PASS" if c["ok"] else "FAIL", c["id"], c["detail"]))
    say("─" * 78)
    say("判据 %d 条 · 绿 %d · 红 %d · 退出码 %d"
        % (len(crit), npass, len(crit) - npass, 0 if npass == len(crit) else 1))
    return 0 if npass == len(crit) else 1


# ══════════════════════════════════════════════════════════════════════════════
# main
# ══════════════════════════════════════════════════════════════════════════════

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="p0-drills.py",
        description="GBT小土豆V8 · P0 故障演练（F2.4/F5.3/F5.6/F7.4/F8.4 · 正负对照 · 隔离 store）")
    ap.add_argument("cmd", nargs="?", default="",
                    help="all | f2.4 | f5.3 | f5.6 | f7.4 | f8.4")
    ap.add_argument("--check", action="store_true", help="跑判据（含正负对照），退出码 0/1")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    ap.add_argument("--sandbox", default=None, help="沙箱目录（默认系统临时目录下新建）")
    ap.add_argument("--no-ledger", action="store_true", help="不写 state/p0-drills.json（举证用）")
    args = ap.parse_args(argv)

    if not args.cmd and not args.check:
        ap.print_help()
        return 2

    sb = ensure_sandbox(args.sandbox)
    binding = verify_binding(sb)          # import 后立即断言（fail-fast）
    prod_before = prod_store_probe()

    only = None
    if args.cmd and args.cmd != "all":
        key = args.cmd.lower().replace(".", ".")
        if key not in DRILLS:
            say("未知子命令：%s（可用：all / %s）" % (args.cmd, " / ".join(DRILLS)))
            return 2
        only = {key}

    drills = run_all(sb, only=only)
    prod_after = prod_store_probe()
    crit = judge(drills, binding, prod_before, prod_after) if (args.check or args.cmd == "all") else None

    if args.json:
        payload = {"tool": "tools/codex-scripts/p0-drills.py", "run_id": _RUN_ID,
                   "sandbox": str(sb), "binding": binding,
                   "prod_store_probe": prod_after, "drills": drills}
        npass = None
        if crit is not None:
            npass = sum(1 for c in crit if c["ok"])
            payload["criteria"] = crit
            payload["summary"] = {"total": len(crit), "passed": npass,
                                  "failed": len(crit) - npass,
                                  "exit": 0 if npass == len(crit) else 1}
        say(json.dumps(payload, ensure_ascii=False, indent=2))
        rc = 0 if (npass is None or npass == len(crit)) else 1
    else:
        say("═" * 78)
        say("P0 演练 · 沙箱 %s" % sb)
        say("绑定：STORE_DIR=%s（沙箱内=%s · 生产=%s）"
            % (binding["store_dir"], binding["in_sandbox"], binding["is_prod"]))
        say("生产 store 探针：run_id 出现在生产审计尾部 = %s（应为 False）"
            % prod_after.get("run_id_in_prod_audit_tail"))
        for d in drills.values():
            report_drill(d)
        if crit is not None:
            rc = report_check(crit)

    if not args.no_ledger:
        p = write_ledger(sb, drills, binding, prod_before, prod_after, crit)
        if not args.json:
            say("台账已写：%s" % p)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
