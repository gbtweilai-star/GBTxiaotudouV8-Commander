# gbt-capability: drama_forge
"""女声固化判据（2026-11-01 改：本地优先）：默认 local（不联网 Edge），rate/pitch 不加工；代码/脚本/配置三处一致。"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def main() -> int:
    print("[1] 代码默认：local 本地优先，rate/pitch 不加工")
    mod = (ROOT / "gbt_allinone" / "tentacle" / "drama_forge.py").read_text(encoding="utf-8", errors="replace")
    check("VOICE_DEFAULT", 'VOICE_DEFAULT = "local"' in mod)
    check("VOICE_RATE 空", 'VOICE_RATE = ""' in mod)
    check("VOICE_PITCH 空", 'VOICE_PITCH = ""' in mod)
    ps = (ROOT / "tools" / "drama-build.ps1").read_text(encoding="utf-8", errors="replace")
    check("build Voice 默认", '[string]$Voice = "local"' in ps)
    check("build Rate 空", '[string]$Rate = "",' in ps)
    check("build Pitch 空", '[string]$Pitch = "",' in ps)

    print("[2] live 配置（有就读）")
    cfg_p = ROOT / "state" / "voice.json"
    if cfg_p.is_file():
        cfg = json.loads(cfg_p.read_text(encoding="utf-8-sig"))
        check("配置 default", cfg.get("default") == "local", cfg)
        check("配置 natural", cfg.get("style") in ("local_pending_zh_tw", "local_zh_tw", "taiwan_natural"), cfg)
        check("配置 rate 空", not cfg.get("rate"), cfg)
        check("配置 pitch 空", not cfg.get("pitch"), cfg)

    print("[3] 交付成片存在且不是占位")
    for e in ("E01", "E02", "E03"):
        p = ROOT / "交付成片" / "顶替新娘" / ("顶替新娘-%s.mp4" % e)
        check("%s 存在" % e, p.is_file() and p.stat().st_size > 1_000_000, p)

    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
