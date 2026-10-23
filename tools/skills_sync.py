# gbt-capability: skills_sync
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""技能唯一真相同步器（主人令 2026-09-27：「源代码保护好、整理摆放好，别分路分叉」）。

**问题（实测，不是推测）**：同一份技能长期有两个真身——
  · **源**：仓内 `skills/<名>/`（进 git · 有历史 · 可复核）；
  · **装**：技能枢纽 `<家>/.agents/skills/<名>/`（**运行时真正读的是这里**）。
两份之间**此前没有任何工具盯着**（全仓 `grep -rn "skills-lock" tools/ gbt_allinone/` 零命中）。
于是各自长大、互不知道对方：实测 2026-09-27 `gbt-security` 源 43K / 装 31K，
装的那份还停在「五位总表」而源已到「二十位总表」，**差 1054 行**——
即：我的能力覆盖补丁全部只落在源上，运行时一个字节都没看见（F18 同型：盘上对≠生效了）。
同批读数：65 个 gbt-* 里 **10 个分叉 · 8 个从未安装**。

⇒ 结论：**分叉不是「两处都有」，是「两处不一样」**。没有唯一真相，就没有「源代码保护」。

**本工具的口径**：
  1. **源是唯一真相**：仓内 `skills/` 为准，装的那份永远由源派生，可随时重建；
  2. **覆盖前先备份**：装的那份若有本地改动，先搬进 `.backups/skills-hub/<时间戳>/`，
     **不静默销毁**——「覆盖」与「毁掉」是两件事；
  3. **镜像语义**：装的那份与源逐字节一致；源里没有的残留件（如 `SKILL.md.bak-040816`）搬走；
  4. **判据可机读**：`check --json` + 非零退出码 ⇒ 直接挂 boot-selfcheck / 定时自检。

**归属规则**（谁装进哪个枢纽）：
  · 自有技能（`gbt-*` 与我们自研的）→ **家枢纽** `~/.agents/skills/`（运行时读它）；
  · 第三方技能（出现在 `skills-lock.json` 里的，如 remotion-*/prisma-*）→ **工作区枢纽**
    `.agents/skills/`（桌面端负责装、由它自己的 lock 管；本工具只报不动）。

命令：
  python tools/skills_sync.py check                  # 对账：分叉/未装/孤儿/残留（有分叉退出码 1）
  python tools/skills_sync.py check --json           # 机读读数
  python tools/skills_sync.py sync                   # 源 → 装（覆盖前自动备份）
  python tools/skills_sync.py sync --only gbt-security
  python tools/skills_sync.py lock                   # 只重写安装锁（state/skills_install.lock.json）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
SRC = ROOT / "skills"
HOME_HUB = Path.home() / ".agents" / "skills"
WS_HUB = ROOT / ".agents" / "skills"
LOCK = ROOT / "state" / "skills_install.lock.json"
BACKUPS = ROOT / ".backups" / "skills-hub"
THIRD_LOCK = ROOT / "skills-lock.json"          # 桌面端管的第三方来源锁（只读，判归属用）

# 残留在枢纽里的备份/临时件：**搬走不删**（`*.bak*` 与本仓 .gitignore 同源）
JUNK_MARKERS = (".bak", "~", ".orig", ".tmp", ".rej")


def _hash_tree(d: Path) -> tuple[str, dict]:
    """技能树指纹：逐文件 sha256（按相对路径排序）再整体 sha256 —— 与文件顺序/时间无关。"""
    files: dict[str, str] = {}
    if not d.is_dir():
        return "", files
    for p in sorted(d.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(d)).replace("\\", "/")
        if "__pycache__" in rel.split("/"):
            continue
        files[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    blob = "\n".join(f"{k}:{files[k]}" for k in sorted(files)).encode()
    return hashlib.sha256(blob).hexdigest()[:16], files


def _is_junk(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    return any(m in name for m in JUNK_MARKERS)


def _third_party() -> set[str]:
    try:
        d = json.loads(THIRD_LOCK.read_text(encoding="utf-8"))
        return set(d.get("skills", {}))
    except Exception:                                    # noqa: BLE001
        return set()


def hub_for(name: str, third: set[str]) -> Path:
    """自有 → 家枢纽（运行时读它）；第三方 → 工作区枢纽（桌面端管，本工具只报）。"""
    return WS_HUB / name if name in third else HOME_HUB / name


def survey() -> dict:
    """全量对账（只读）。返回每技能状态 + 汇总。"""
    third = _third_party()
    rows, summary = [], {"ok": 0, "missing": 0, "drift": 0, "orphan": 0, "residue": 0,
                         "third_party_skipped": 0}
    if not SRC.is_dir():
        return {"error": f"源目录不存在：{SRC}", "rows": [], "summary": summary}
    for s in sorted(SRC.iterdir()):
        if not s.is_dir() or s.name.startswith("."):
            continue
        h = hub_for(s.name, third)
        own = s.name not in third
        src_hash, src_files = _hash_tree(s)
        hub_hash, hub_files = _hash_tree(h)
        residue = sorted(k for k in hub_files if _is_junk(k))
        if not h.exists():
            st = "未安装" if own else "第三方未装"
            summary["missing" if own else "third_party_skipped"] += 1
        elif src_hash == hub_hash and not residue:
            st = "一致"
            summary["ok"] += 1
        elif not own:
            st = "第三方(桌面端管)"
            summary["third_party_skipped"] += 1
        else:
            only_src = sorted(set(src_files) - set(hub_files))
            only_hub = sorted(k for k in set(hub_files) - set(src_files) if not _is_junk(k))
            changed = sorted(k for k in set(src_files) & set(hub_files) if src_files[k] != hub_files[k])
            st = "分叉"
            summary["drift"] += 1
            if residue:
                summary["residue"] += 1
            rows.append({"skill": s.name, "hub": str(h), "status": st, "own": own,
                         "only_src": only_src, "only_hub": only_hub, "changed": changed,
                         "residue": residue, "src_files": len(src_files),
                         "hub_files": len(hub_files)})
            continue
        if residue:
            summary["residue"] += 1
        rows.append({"skill": s.name, "hub": str(h), "status": st, "own": own,
                     "only_src": [], "only_hub": [], "changed": [], "residue": residue,
                     "src_files": len(src_files), "hub_files": len(hub_files)})
    # 孤儿：枢纽里有、源里没有的自有技能（只有一边有 = 也是分叉）
    if HOME_HUB.is_dir():
        for h in sorted(HOME_HUB.glob("gbt-*")):
            if not (SRC / h.name).is_dir():
                summary["orphan"] += 1
                rows.append({"skill": h.name, "hub": str(h), "status": "孤儿(hub有源无)",
                             "own": True, "only_src": [], "only_hub": [], "changed": [],
                             "residue": [], "src_files": 0, "hub_files": len(_hash_tree(h)[1])})
    return {"src": str(SRC), "home_hub": str(HOME_HUB), "ws_hub": str(WS_HUB),
            "rows": rows, "summary": summary}


def do_sync(only: str = "") -> dict:
    """源 → 装：备份 → 镜像 → 写锁。**先备份**，任何本地改动都不会被静默销毁。"""
    st = survey()
    ts = time.strftime("%Y%m%d-%H%M%S")
    done, backed, skipped = [], [], []
    for r in st["rows"]:
        if only and r["skill"] != only:
            continue
        if not r["own"]:
            skipped.append({"skill": r["skill"], "why": "第三方，桌面端管"})
            continue
        if r["status"] == "一致" and not r["residue"]:
            continue
        src, hub = SRC / r["skill"], Path(r["hub"])
        if hub.exists():
            dst = BACKUPS / ts / r["skill"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(hub, dst)                     # 覆盖前留全份（含残留件）
            backed.append({"skill": r["skill"], "to": str(dst)})
        if hub.exists():
            shutil.rmtree(hub)
        hub.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, hub, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        done.append({"skill": r["skill"], "was": r["status"],
                     "files": len(_hash_tree(hub)[1])})
    lock = write_lock()
    return {"synced": done, "backed_up": backed, "skipped": skipped,
            "backup_root": str(BACKUPS / ts), "lock": lock}


def write_lock() -> dict:
    """安装锁：记录「哪份源、装到哪、几件、什么指纹、什么时候」——可复核、可重建。"""
    third = _third_party()
    skills = {}
    for s in sorted(SRC.iterdir()):
        if not s.is_dir() or s.name.startswith("."):
            continue
        h = hub_for(s.name, third)
        sh, sf = _hash_tree(s)
        hh, _ = _hash_tree(h)
        skills[s.name] = {"hub": "home" if s.name not in third else "workspace",
                          "installed": h.exists(), "src_hash": sh, "hub_hash": hh,
                          "files": len(sf), "in_sync": bool(sh) and sh == hh}
    out = {"version": 1, "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "source": str(SRC), "home_hub": str(HOME_HUB), "ws_hub": str(WS_HUB),
           "count": len(skills),
           "in_sync": sum(1 for v in skills.values() if v["in_sync"]),
           "skills": skills}
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"path": str(LOCK), "count": out["count"], "in_sync": out["in_sync"]}


def _print(st: dict) -> None:
    s = st["summary"]
    print(f"源：{st['src']}")
    print(f"枢纽：家 {st['home_hub']} ｜ 工作区 {st['ws_hub']}")
    print(f"一致 {s['ok']} · 分叉 {s['drift']} · 未安装 {s['missing']} · "
          f"孤儿 {s['orphan']} · 残留 {s['residue']} · 第三方未装/不动 {s['third_party_skipped']}")
    for r in st["rows"]:
        if r["status"] in ("一致",):
            continue
        line = f"  [{r['status']}] {r['skill']:<26} 源{r['src_files']}件/装{r['hub_files']}件"
        if r["changed"]:
            line += f" · 内容异 {len(r['changed'])}（{', '.join(r['changed'][:3])}）"
        if r["only_hub"]:
            line += f" · 装件多 {len(r['only_hub'])}"
        if r["only_src"]:
            line += f" · 源件多 {len(r['only_src'])}"
        if r["residue"]:
            line += f" · 残留 {', '.join(r['residue'][:2])}"
        print(line)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="技能唯一真相同步器（源=仓内 skills/）")
    ap.add_argument("cmd", choices=["check", "sync", "lock"])
    ap.add_argument("--json", action="store_true", help="机读输出")
    ap.add_argument("--only", default="", help="只处理某个技能（sync 用）")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        st = survey()
        if a.json:
            print(json.dumps(st, ensure_ascii=False, indent=2))
        else:
            _print(st)
        s = st["summary"]
        bad = s["drift"] + s["missing"] + s["orphan"]
        if bad and not a.json:
            print(f"\n⇒ 有分叉/缺口 {bad} 处。修法：python tools/skills_sync.py sync")
        return 1 if bad else 0
    if a.cmd == "sync":
        out = do_sync(a.only)
        if a.json:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            for d in out["synced"]:
                print(f"  ✓ {d['skill']:<26} 装好（原状态：{d['was']}）· {d['files']} 件")
            for b in out["backed_up"]:
                print(f"  ⤶ 覆盖前备份：{b['skill']} → {b['to']}")
            for s in out["skipped"]:
                print(f"  · 跳过 {s['skill']}（{s['why']}）")
            print(f"锁：{out['lock']['path']} 同步 {out['lock']['in_sync']}/{out['lock']['count']}")
            print(f"备份区：{out['backup_root']}")
        return 0
    out = write_lock()
    print(f"锁已写：{out['path']}（同步 {out['in_sync']}/{out['count']}）" if not a.json
          else json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
