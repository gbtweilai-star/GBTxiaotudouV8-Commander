# -*- coding: utf-8 -*-
"""把**设计维度的 16 条簇用法规程**镜像到本机 DSH 真会扫的技能根（`<仓>/.dsh/skills/`）。

为什么需要它（2026-09-22 现读实锤，不是保险起见）：
  本机 DSH 的 `dsh-skill-filesystem` 只扫五个根 ——
  `<项目>/.dsh/skills` · `<项目>/.agents/skills` · `preset/skills` · `$DSH_HOME/skills` · `~/.agents/skills`；
  **`~/.openclaw-autoclaw/skills` 不在其中**。实测（用动态插件读本会话技能层）：
  不传 `cwd` 共 78 条技能、`gbt-*` 只有 4 条（全来自 `~/.agents/skills`）；
  传上本工作区 `cwd` 后 92 条 —— 说明**项目根确实被扫**，只是原来没往那里放过东西。
  ⇒ 已交付的规程若只躺在 `.openclaw-autoclaw`，**本会话"自动发现/自动触发"这一层等于没有**。

范围（**由主人 2026-09-22 选**）：只镜像**设计维度相关的那 16 条**，不铺全部 51 件。
名单**不手抄**：从总规程 §7「各簇用法规程」那一行**现读解析**出来 —— 一处真源，免得两头走样。

用法：
    py -3.14 tools/codex-scripts/mirror-design-regulations.py            # 镜像 + 留回执
    py -3.14 tools/codex-scripts/mirror-design-regulations.py --check     # 只核对，不写盘
退出码：0 = 16 条全部逐文件同哈希；1 = 有缺件/不同哈希/名单对不上。
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
MASTER = ROOT / "skills" / "gbt-design-mastery" / "SKILL.md"
DST_ROOT = ROOT / ".dsh" / "skills"          # DSH 的 project-dsh 根（现读确认会被扫）
RECEIPT = ROOT / "state" / "design-regulations-mirror-receipt.json"
WANT = 16                                    # 设计维度 16 条簇用法规程（主人选定范围）


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest().upper()


def names_from_master() -> list[str]:
    """从总规程 §7 的「各簇用法规程」行现读解析 16 个名字（不手抄）。"""
    body = MASTER.read_text(encoding="utf-8")
    row = [ln for ln in body.splitlines() if ln.startswith("| 各簇用法规程")]
    if not row:
        return []
 # 那一行里**第一条**写成 `skills/gbt-aesthetic`，其余写成 `gbt-figma` ——
    # 第一版正则只要紧贴反引号的 `gbt-`，于是把 `gbt-aesthetic` 漏掉（15 ≠ 16，门当场报红）。
    found = re.findall(r"`(?:skills/)?(gbt-[a-z0-9\-]+)`", row[0])
    seen, out = set(), []
    for n in found:
        if n not in seen and n != "gbt-design-mastery":
            seen.add(n)
            out.append(n)
    return out


def main(argv: list[str]) -> int:
    dry = "--check" in argv
    names = names_from_master()
    if len(names) != WANT:
        print("🔴 总规程 §7 里解析出 %d 条簇用法规程（期望 %d）：%s" % (len(names), WANT, "、".join(names)))
        return 1
    print("镜像名单（现读自总规程 §7）：%d 条 —— %s" % (len(names), "、".join(names)))
    print("落点：%s%s" % (DST_ROOT, "（核对模式，不写盘）" if dry else ""))

    rows, bad = [], []
    for n in names:
        src_dir = ROOT / "skills" / n
        if not src_dir.exists():
            bad.append("%s 源目录不在" % n)
            continue
        files = sorted(p for p in src_dir.rglob("*") if p.is_file())
        dst_dir = DST_ROOT / n
        if not dry:
            for f in files:
                target = dst_dir / f.relative_to(src_dir)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, target)
        mism = 0
        for f in files:
            target = dst_dir / f.relative_to(src_dir)
            ok = target.exists() and sha(target) == sha(f)
            if not ok:
                mism += 1
                bad.append("%s/%s 未同哈希" % (n, f.relative_to(src_dir).as_posix()))
        tb = sum(f.stat().st_size for f in files)
        rows.append({"name": n, "files": len(files), "bytes": tb,
                     "rel": [f.relative_to(src_dir).as_posix() for f in files],
                     "all_identical": mism == 0})
        print("  %s %-20s %2d 文件 / %7d B" % ("✅" if mism == 0 else "🔴", n, len(files), tb))

    ok_all = not bad
    if not dry:
        RECEIPT.write_text(json.dumps({
            "at": datetime.now().isoformat(timespec="seconds"),
            "src_root": "skills/", "dst_root": str(DST_ROOT.relative_to(ROOT)),
            "why": "本机 DSH 的 dsh-skill-filesystem 不扫 ~/.openclaw-autoclaw/skills；"
                   "只装那里本会话读不到（现读实测）。范围由主人 2026-09-22 选定：只镜像设计维度 16 条。",
            "names_from": "skills/gbt-design-mastery/SKILL.md §7「各簇用法规程」行（现读解析）",
            "count": len(rows), "protocols": rows, "all_identical": ok_all,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print("回执 → %s" % RECEIPT.relative_to(ROOT))
    if bad:
        for b in bad[:10]:
            print("   🔴 %s" % b)
        print("结论：**不通过**（%d 处问题）" % len(bad))
        return 1
    print("结论：%d 条 × 全部文件逐字节一致 ✅（合计 %d 文件 / %d B）"
          % (len(rows), sum(r["files"] for r in rows), sum(r["bytes"] for r in rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
