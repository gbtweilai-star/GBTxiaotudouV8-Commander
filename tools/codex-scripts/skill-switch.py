# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 技能按需开关（Owner 令 2026-10-14：「只有使用的时候才激活，不使用的时候就停止不占用任何资源」）。

真问题：Codex 把 214 条技能的名字+描述都塞进上下文 => 预算爆掉
（TUI 原文：「Skill descriptions were shortened to fit the skills context budget」；
 更早一版：「All skill descriptions were removed and 212 additional skills were not included」）。
=> 默认全关（零占用），做哪件事现开那一两条，做完再关。

机制（从 codex.exe 挖出的 schema）：~/.codex/config.toml 里的
    [[skills.config]]
    name = "技能名"        # 与 path 二选一，不能同时给
    enabled = false        # 关

判据提醒（本仓已自纠过一次）：codex exec **不打印**那句预算黄字，别拿 exec 当预算判据；
  exec 只用来验「配置没写坏」（不许出现 Error loading config.toml）。预算那句要在 TUI 里看。

用法：
    py -3.14 tools/codex-scripts/skill-switch.py list
    py -3.14 tools/codex-scripts/skill-switch.py off 技能名 [技能名 ...]
    py -3.14 tools/codex-scripts/skill-switch.py on  技能名 [...]
    py -3.14 tools/codex-scripts/skill-switch.py only 技能名 [...]     # 其余全关
    py -3.14 tools/codex-scripts/skill-switch.py selftest

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import tomllib
from pathlib import Path

CFG = Path(r"C:\Users\ADMIN\.codex\config.toml")
BLOCK = re.compile(r"\[\[skills\.config\]\]\s*\n((?:[^\[]|\[(?!\[))*?)(?=\n\[|\Z)", re.S)


def _read() -> str:
    return CFG.read_text(encoding="utf-8")


def entries(txt: str) -> dict:
    out = {}
    for m in BLOCK.finditer(txt):
        body = m.group(1)
        nm = re.search(r'^name\s*=\s*"([^"]+)"', body, re.M)
        en = re.search(r"^enabled\s*=\s*(true|false)", body, re.M)
        if nm:
            out[nm.group(1)] = (en.group(1) == "true") if en else True
    return out


def _set(name: str, enabled: bool) -> None:
    txt = _read()
    pat = re.compile(r"(\[\[skills\.config\]\]\s*\n\s*name\s*=\s*" + re.escape(name) + r"[\s\S]*?enabled\s*=\s*)(true|false)", re.M)
    if pat.search(txt):
        txt = pat.sub(lambda m: m.group(1) + ("true" if enabled else "false"), txt, count=1)
    else:
        txt += '\n[[skills.config]]\nname = "%s"\nenabled = %s\n' % (name, "true" if enabled else "false")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    shutil.copy2(CFG, str(CFG) + ".bak-skillswitch-" + stamp)
    CFG.write_text(txt, encoding="utf-8")
    try:
        tomllib.loads(CFG.read_text(encoding="utf-8"))
    except Exception as exc:                                   # noqa: BLE001
        shutil.copy2(str(CFG) + ".bak-skillswitch-" + stamp, CFG)
        raise SystemExit("WRITE-BROKEN-TOML rolled back: " + str(exc)[:120])


def cmd_list() -> int:
    e = entries(_read())
    print(json.dumps({"cfg": str(CFG), "entries": len(e),
                      "off_zero_cost": sorted(k for k, v in e.items() if not v),
                      "on": sorted(k for k, v in e.items() if v),
                      "note": "not-listed = Codex default (on)"}, ensure_ascii=False, indent=1))
    return 0


def selftest() -> int:
    ck = []
    sample = 'a = 1\n\n[[skills.config]]\nname = "zz-probe"\nenabled = false\n'
    def c(n, ok, d=""):
        ck.append(bool(ok)); print(("OK  " if ok else "BAD ") + n + (" - " + str(d)[:80] if d else ""))
    c("positive: parse name/enabled", entries(sample).get("zz-probe") is False, entries(sample))
    c("negative: empty config no false hit", entries("a = 1\n") == {})
    c("positive: real config parses", isinstance(tomllib.loads(_read()), dict))
    c("positive: real config has disabled entries", any(v is False for v in entries(_read()).values()),
      sorted(k for k, v in entries(_read()).items() if not v)[:5])
    bad = len([x for x in ck if not x])
    print("\nskill-switch selftest: %d/%d" % (len(ck) - bad, len(ck)))
    return 1 if bad else 0


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                      # noqa: BLE001
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "on", "off", "only", "selftest"])
    ap.add_argument("names", nargs="*")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        return selftest()
    if a.cmd == "list":
        return cmd_list()
    if not a.names:
        print("need skill names"); return 2
    if a.cmd == "on":
        for n in a.names:
            _set(n, True)
    elif a.cmd == "off":
        for n in a.names:
            _set(n, False)
    else:
        for n in a.names:
            _set(n, True)
        allnames = []
        try:
            atlas = Path(__file__).resolve().parents[2] / "state" / "skill_atlas.json"
            doc = json.loads(atlas.read_text(encoding="utf-8"))
            allnames = [x.get("name") for x in (doc if isinstance(doc, list) else doc.get("skills", [])) if x.get("name")]
        except Exception:                                      # noqa: BLE001
            pass
        for n in allnames:
            if n not in a.names:
                _set(n, False)
        print("only: enabled %d, disabled the rest %d" % (len(a.names), max(0, len(allnames) - len(a.names))))
    e = entries(_read())
    print(json.dumps({"changed": a.names, "off": sorted(k for k, v in e.items() if not v)[:40],
                      "on": sorted(k for k, v in e.items() if v)[:40]}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
