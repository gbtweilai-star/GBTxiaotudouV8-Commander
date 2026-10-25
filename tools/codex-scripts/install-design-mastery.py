# -*- coding: utf-8 -*-
"""把设计全维度总规程（`skills/gbt-design-mastery/`，含 7 份深读）**装到两个技能根**，并留回执。

为什么要专门一个装机器、而不是手 Copy-Item：
  1. 这一件是**目录型技能**（`SKILL.md` + `references/*.md`），旧的门只比 `SKILL.md`
     一个文件 —— 会把"索引装了、深读没装"判成通过。
  2. "装了"必须留**机器可复核**的证据：逐文件 sha256 + 字节数 + 落盘时间，写进
     `state/design-mastery-install-receipt.json`；下次谁都能拿它对。
  3. **半成品不许装**：references 份数不是 7、或哪份字节数 < 800（空壳），直接拒绝。

🔴 **为什么要装两处（2026-09-22 现读实锤，不是保险起见）**：
  本机 DSH 的 `dsh-skill-filesystem` 只扫这五个根 ——
  `<项目>/.dsh/skills` · `<项目>/.agents/skills` · `preset/skills` · `$DSH_HOME/skills` · `~/.agents/skills`；
  **`~/.openclaw-autoclaw/skills` 不在其中**。实测（用动态插件读本会话自己的技能层）：
  本会话共 **78** 条技能，`gbt-*` 只有 **4** 条，全部来自 `source: user-agents`（`~/.agents/skills`），
  而装到 `~/.openclaw-autoclaw/skills` 的那 51 件**一条都没被本会话看到**。
  ⇒ 只装 `.openclaw-autoclaw`（AGENTS.md 写的 managed 目录，AutoClaw 产品口径）= **对 DSH 无效**。
  所以两个根都装：`~/.openclaw-autoclaw/skills/`（产品口径）+ `<仓>/.dsh/skills/`（本会话真扫得到的项目根）。

用法：
    py -3.14 tools/codex-scripts/install-design-mastery.py            # 装机（两处）+ 留回执
    py -3.14 tools/codex-scripts/install-design-mastery.py --check     # 只核对现状，不写盘
退出码：0 = 两处都逐字节一致；1 = 有缺件/不同哈希/被拒绝。
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
SRC = ROOT / "skills" / "gbt-design-mastery"
# ① AutoClaw 产品口径的 managed 目录（AGENTS.md 指定）
# ② 本机 DSH 真正会扫的项目技能根（现读自 dsh-skill-filesystem 的 roots 列表）
TARGETS = [
    ("openclaw-managed", Path.home() / ".openclaw-autoclaw" / "skills" / "gbt-design-mastery"),
    ("dsh-project", ROOT / ".dsh" / "skills" / "gbt-design-mastery"),
]
RECEIPT = ROOT / "state" / "design-mastery-install-receipt.json"
WANT_REFS = 7          # 七条线，一条一份
MIN_REF_BYTES = 800    # 与 verify-design-mastery.py 同一口径：比这短就是空壳


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest().upper()


def main(argv: list[str]) -> int:
    dry = "--check" in argv
    if not SRC.exists():
        print("🔴 源目录不在：%s" % SRC)
        return 1
    refs = sorted((SRC / "references").glob("*.md")) if (SRC / "references").exists() else []
    files = [SRC / "SKILL.md"] + refs

    # ── 装机前的自检：半成品不许装 ────────────────────────────────
    bad: list[str] = []
    if not (SRC / "SKILL.md").exists():
        bad.append("源里没有 SKILL.md")
    if len(refs) != WANT_REFS:
        bad.append("references 只有 %d 份（要 %d 份）—— 七条线没齐就别装" % (len(refs), WANT_REFS))
    for r in refs:
        if r.stat().st_size < MIN_REF_BYTES:
            bad.append("%s 只有 %d B（< %d）⇒ 空壳，不装" % (r.name, r.stat().st_size, MIN_REF_BYTES))
    if bad:
        for b in bad:
            print("🔴 %s" % b)
        return 1

    targets: list[dict] = []
    ok_all = True
    for label, dst in TARGETS:
        if not dry:
            (dst / "references").mkdir(parents=True, exist_ok=True)
            for f in files:
                target = dst / f.relative_to(SRC)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, target)
        print("设计全维度装机%s [%s] → %s" % ("（核对模式，不写盘）" if dry else "", label, dst))
        rows = []
        for f in files:
            rel = f.relative_to(SRC).as_posix()
            target = dst / rel
            s = sha(f)
            if target.exists():
                d = sha(target)
                ok = (s == d)
            else:
                d, ok = "（不在）", False
            rows.append({"rel": rel, "bytes": f.stat().st_size, "sha256": s,
                         "installed_sha256": d, "identical": ok})
            if not ok:
                print("   🔴 %s（%d B）落盘不是同一份" % (rel, f.stat().st_size))
        # 装机目录里多出来的（旧版本残留 / 人手加的）—— 只报不删
        extra = []
        if dst.exists():
            have = {r["rel"] for r in rows}
            for p in sorted(dst.rglob("*")):
                if p.is_file() and p.relative_to(dst).as_posix() not in have:
                    extra.append(p.relative_to(dst).as_posix())
        sub_ok = all(r["identical"] for r in rows)
        ok_all = ok_all and sub_ok
        print("   %s %d 个文件%s%s"
              % ("✅" if sub_ok else "🔴", len(rows), "逐字节一致" if sub_ok else "有不一致",
                 "" if not extra else "；多出 %d 个文件（只报不删）：%s" % (len(extra), "、".join(extra[:5]))))
        targets.append({"label": label, "dst": str(dst), "files": rows,
                        "extra_in_dst": extra, "all_identical": sub_ok})

    if not dry:
        RECEIPT.write_text(json.dumps({
            "at": datetime.now().isoformat(timespec="seconds"),
            "src": str(SRC.relative_to(ROOT)),
            "targets": targets,
            "all_identical": ok_all,
            "why_two_targets": "本机 DSH 的 dsh-skill-filesystem 不扫 ~/.openclaw-autoclaw/skills；"
                               "只装那里对 DSH 会话无效（现读实测）。",
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print("回执 → %s" % RECEIPT.relative_to(ROOT))
    n = len([r for t in targets for r in t["files"]])
    print("结论：%s（%d 处 × %d 个文件 = %d 次比对）"
          % ("两处都逐字节一致 ✅" if ok_all else "有不一致 🔴", len(targets), len(files), n))
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
