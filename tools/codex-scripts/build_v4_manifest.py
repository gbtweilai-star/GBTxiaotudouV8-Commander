# -*- coding: utf-8 -*-
"""V4 数据层：在 HUD 读数之上，补「对话面板」要用的真实字段。
产出 .scratch/v4_manifest.json = hud_manifest + activity/git/model/auth
真实来源：store/audit.jsonl（36MB 真实审计）、git、.dsh/settings.yaml、~/.codex/config.toml
"""
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
sys.path.insert(0, str(BASE))
HUD = BASE / ".scratch" / "hud_manifest.json"
OUT = BASE / ".scratch" / "v4_manifest.json"
AUDIT = BASE / "gbt_allinone" / "store" / "audit.jsonl"

M = json.loads(HUD.read_text(encoding="utf-8"))

# ── git（真实） ──


def sh(args):
    try:
        r = subprocess.run(args, cwd=str(BASE), capture_output=True, text=True, timeout=25)
        return (r.stdout or "").strip()
    except Exception:  # noqa: BLE001
        return ""


branch = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
porcelain = sh(["git", "status", "--porcelain"])
changed = len([ln for ln in porcelain.splitlines() if ln.strip()])

# ── 模型 / 权限（真实） ──
dsh_home = Path.home() / ".dsh" / "settings.yaml"
model_provider, model_name, effort, permission = "—", "—", "—", "—"
if dsh_home.exists():
    txt = dsh_home.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"agent-default-model:\s*\n\s*provider:\s*(\S+)\s*\n\s*model:\s*(\S+)\s*\n\s*reasoningEffort:\s*(\S+)", txt)
    if m:
        model_provider, model_name, effort = m.group(1), m.group(2), m.group(3)
    m2 = re.search(r"permission:\s*\n\s*defaultPreset:\s*(\S+)", txt)
    if m2:
        permission = m2.group(1)

codex_cfg = Path.home() / ".codex" / "config.toml"
codex_model = ""
if codex_cfg.exists():
    t = codex_cfg.read_text(encoding="utf-8", errors="ignore")
    m3 = re.search(r'^model\s*=\s*"([^"]+)"', t, re.M)
    if m3:
        codex_model = m3.group(1)

# ── 真实审计活动（末 400 行足够） ──
lines = []
if AUDIT.exists():
    with AUDIT.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if '"event"' in line:
                lines.append(line)
    lines = lines[-400:]

by_kind = defaultdict(lambda: {"n": 0, "last": "", "last_event": ""})
events = []
for raw in lines:
    try:
        o = json.loads(raw)
    except Exception:  # noqa: BLE001
        continue
    k = (o.get("meta") or {}).get("kind") or "(未标)"
    iso = o.get("iso") or ""
    ev = o.get("event") or ""
    rec = by_kind[k]
    rec["n"] += 1
    if iso >= rec["last"]:
        rec["last"], rec["last_event"] = iso, ev
    if ev in ("error", "denied", "svc_down"):
        events.append({"event": ev, "kind": k, "at": iso,
                       "reason": str((o.get("meta") or {}).get("reason") or "")[:120]})

activity = sorted(by_kind.items(), key=lambda kv: kv[1]["last"], reverse=True)[:12]
activity = [{"kind": k, "count": v["n"], "last": v["last"].replace("T", " "), "last_event": v["last_event"]}
            for k, v in activity]

M["runtime"].update({
    "git_branch": branch, "git_changed": changed,
    "model_provider": model_provider, "model": model_name,
    "effort": effort, "permission": permission, "codex_model": codex_model,
})
M["activity"] = activity
M["recent_events"] = events[-8:]
M["audit_lines_scanned"] = len(lines)

OUT.write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
print("写出:", OUT)
print("git:", branch, "改动", changed, "| 模型:", model_provider, model_name, effort, "| 权限:", permission)
print("活动条目:", len(activity), "| 最近异常:", len(M["recent_events"]))
for a in activity[:6]:
    print("   -", a["kind"], a["count"], a["last"], a["last_event"])
