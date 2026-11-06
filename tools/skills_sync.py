# -*- coding: utf-8 -*-
"""skills_sync —— 技能**源** ↔ 技能**枢纽** 的指纹对账与同步（**按技能平铺装**）。

## 为什么有这个文件

`gbt_allinone/tests/test_skills_install_sync.py`（判据）与
`tools/tentacle_bind.py:627-633`（运行时 autobind）**两处**都在调它，
而 2026-11-05 实测该文件**不存在** —— 判据崩在 `FileNotFoundError`（崩 ≠ 红）。

## 契约（由消费方定义）

    st  = survey()      # rows[]{skill, own, status, changed, missing, residue} / summary / home_hub
    out = do_sync()     # synced[]{skill} / backup_root

## 口径：一个技能 = 一个目录，**带自己的 SKILL.md**，装在枢纽根下**平铺**

| 角色 | 位置 |
|---|---|
| 源（唯一真相） | `skills/` · `gbt_allinone/skills/` |
| 装（派生物） | `~/.agents/skills/<技能名>/`（自有）· `.agents/skills/<技能名>/`（第三方） |

### 「集合包」必须拆开装（2026-11-05 血账）

`skills/superpowers/` 是插件集合：20 个子目录各带 `SKILL.md`，**自身没有根 SKILL.md**。
早先本工具**按包整拷**成 `<hub>/superpowers/<子技能>/`，于是运行时按
`<hub>/<技能名>/SKILL.md` 一个都找不到 —— 183 个文件都拷了、`check` 报"四条全过"，
**实际 27 个子技能一条都加载不了**。

这就是「盘上对」被念成「生效了」的最贵一版。现在：

- 目录**有**根 `SKILL.md` ⇒ 它自己就是一个技能；
- 目录**没有**根 `SKILL.md` ⇒ 它的每个带 `SKILL.md` 的直接子目录**各算一个技能**，平铺安装。

判据见 `tools/codex-scripts/omni.py` 与 `tools/codex-scripts/audit-skill-roots.py`
（两处按 `rglob` 数技能，33 条），以及 `tests/test_skill_count_agreement.py`。

## 纪律：装不上就说装不上

枢纽根不存在时 `summary.ok = false` 并写明原因；
**绝不**允许"两边都空 ⇒ 全部一致"。

用法：
    python tools/skills_sync.py check          # 四条判据（默认）
    python tools/skills_sync.py sync           # 真同步（覆盖前先备份）
    python tools/skills_sync.py sync --dry     # 只看不动
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import re
import shutil
import sys
import time

# Windows 控制台默认 GBK，打印 ❌/✅ 会 UnicodeEncodeError 直接崩。
# 工具自己负责自己的输出编码 —— 不能要求调用方先 chcp 65001。
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:            # 老解释器/被重定向到不支持的对象
    pass

ROOT = pathlib.Path(__file__).resolve().parents[1]

# 源：目录树，技能按下面的规则从中解析
SOURCES = [
    {"key": "repo", "path": ROOT / "skills", "label": "仓内 skills/"},
    {"key": "pkg", "path": ROOT / "gbt_allinone" / "skills", "label": "包内 gbt_allinone/skills/"},
]

# 第三方包：整包（或其子技能）都装到仓内第三方枢纽
VENDOR = {
    "gsap": "GreenSock GSAP（上游发行）",
    "gsap-official": "GreenSock GSAP 官方",
    "ref-to-3d": "第三方 3D 参考技能",
    "superpowers": "第三方（目录内带 LICENSE）",
    "taste-skill": "第三方审美技能",
}

HUBS = {
    "home": pathlib.Path.home() / ".agents" / "skills",   # 自有技能
    "repo": ROOT / ".agents" / "skills",                  # 第三方技能
}

SKIP = {"__pycache__", ".git", "node_modules", ".venv", ".mypy_cache"}
BACKUP_BASE = ROOT / "state" / "skills-hub-backup"

STATUS_OK = "一致"
STATUS_DRIFT = "分叉"
STATUS_MISSING = "未安装"
STATUS_ORPHAN = "孤儿（仅枢纽）"


# ── 基础 ────────────────────────────────────────────────────────────────────
def _files(d: pathlib.Path) -> dict:
    """目录 → {posix 相对路径: 内容}。目录不存在返回 {}。"""
    out = {}
    if not d.is_dir():
        return out
    for dp, dns, fns in os.walk(d):
        dns[:] = sorted(x for x in dns if x not in SKIP)
        for fn in sorted(fns):
            p = pathlib.Path(dp) / fn
            try:
                out[p.relative_to(d).as_posix()] = p.read_bytes()
            except OSError:
                out[p.relative_to(d).as_posix()] = b"<unreadable>"
    return out


def _digest(files: dict) -> str:
    """内容指纹：相对路径 + 内容依次进 sha256。

    不看 mtime（复制/解压会改它而不改内容）、不只看大小（改一字节长度不变）。
    **内容才是真相。**
    """
    h = hashlib.sha256()
    for rel in sorted(files):
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(files[rel])
        h.update(b"\0")
    return h.hexdigest()


def _diff(src: dict, dst: dict) -> dict:
    return {
        "changed": sorted(k for k in (set(src) & set(dst)) if src[k] != dst[k]),
        "missing": sorted(set(src) - set(dst)),
        "residue": sorted(set(dst) - set(src)),
    }


def _skill_name(skill_dir: pathlib.Path) -> str:
    """技能真名：frontmatter `name:`，拿不到退回目录名。

    为什么不用目录名：`skills/taste-skill/SKILL.md` 里写的是
    `name: design-taste-frontend`，安装目录必须按**真名**建，否则运行时装不到。
    """
    sk = skill_dir / "SKILL.md"
    try:
        head = sk.read_text(encoding="utf-8", errors="replace")[:2000]
    except OSError:
        return skill_dir.name
    m = re.search(r"(?m)^name:\s*(.+?)\s*$", head)
    return (m.group(1).strip().strip("'\"") or skill_dir.name) if m else skill_dir.name


def _units() -> dict:
    """源里所有**技能单元**：{技能名: {"path", "own", "vendor_reason", "package", "root"}}。

    规则（2026-11-05 定稿，实测 33 条）：
      · 目录有根 SKILL.md            → 它自己是一个技能
      · 目录没有根 SKILL.md          → 每个带 SKILL.md 的直接子目录各是一个技能
    为什么不用 rglob 一把梭：有根 SKILL.md 的技能（如 `taste-skill`）内部可能再带
    子件，那是**按需加载的章节**，不是独立技能；先判根、再下探一层，才两种形态都对。
    """
    out = {}
    for s in SOURCES:
        base = s["path"]
        if not base.is_dir():
            continue
        for pkg in sorted(base.iterdir()):
            if not pkg.is_dir() or pkg.name in SKIP:
                continue
            vendor_reason = VENDOR.get(pkg.name, "")
            own = pkg.name not in VENDOR
            root_skill = pkg / "SKILL.md"

            if root_skill.is_file():
                name = _skill_name(pkg)
                out.setdefault(name, {"path": pkg, "own": own, "package": pkg.name,
                                      "root": s["label"], "vendor_reason": vendor_reason})
                continue

            for sub in sorted(pkg.iterdir()):
                if not sub.is_dir() or sub.name in SKIP:
                    continue
                if not (sub / "SKILL.md").is_file():
                    continue
                name = _skill_name(sub)
                out.setdefault(name, {"path": sub, "own": own, "package": pkg.name,
                                      "root": s["label"], "vendor_reason": vendor_reason})
    return out


def _hub_skills(hub: pathlib.Path) -> dict:
    """枢纽里已装好的**技能**：{技能名: 目录}。按 `<hub>/<名>/SKILL.md` 认。"""
    out = {}
    if not hub.is_dir():
        return out
    for d in sorted(hub.iterdir()):
        if not (d.is_dir() and d.name not in SKIP and (d / "SKILL.md").is_file()):
            continue
        # **按目录名认，不按 frontmatter 名** —— 加载器找的就是 `<root>/<目录名>/SKILL.md`。
        # 血账：早先这里用 `_skill_name(d)` 做键，于是枢纽里叫 `taste-skill/` 的目录被当成
        # 技能 `design-taste-frontend` 并判"一致"，可加载器按 `design-taste-frontend/` 根本找不到它。
        # 目录名错了就是装错了，必须报出来重装。
        out[d.name] = d
    return out


def _target_hub(own: bool) -> pathlib.Path:
    """自有 → ~/.agents/skills；第三方 → 仓内 .agents/skills（LAYOUT.md:86）。"""
    return HUBS["home"] if own else HUBS["repo"]


# ── 主读数 ──────────────────────────────────────────────────────────────────
def survey() -> dict:
    """{rows, summary, home_hub, hubs, sources}。**不抛异常**：拿不到就如实报。"""
    units = _units()
    home = _hub_skills(HUBS["home"])
    repo = _hub_skills(HUBS["repo"])

    rows = []
    for name in sorted(units):
        u = units[name]
        hub = _target_hub(u["own"])
        installed = (home if u["own"] else repo).get(name)
        src_files = _files(u["path"])

        if installed is None:
            status = STATUS_MISSING
            d = {"changed": [], "missing": sorted(src_files), "residue": []}
        else:
            d = _diff(src_files, _files(installed))
            status = STATUS_DRIFT if (d["changed"] or d["missing"] or d["residue"]) else STATUS_OK

        rows.append({
            "skill": name,
            "own": u["own"],
            "status": status,
            "package": u["package"],
            "source": u["root"],
            "target": str(hub),
            "files": len(src_files),
            "changed": d["changed"],
            "missing": d["missing"],
            "residue": d["residue"],
            "vendor_reason": u["vendor_reason"],
        })

    seen = set(units)
    for hub_key, entries in (("home", home), ("repo", repo)):
        for name, path in sorted(entries.items()):
            if name in seen:
                continue
            seen.add(name)
            rows.append({
                "skill": name, "own": False, "status": STATUS_ORPHAN,
                "package": "", "source": "(无)", "target": str(HUBS[hub_key]),
                "files": len(_files(path)), "changed": [], "missing": [],
                "residue": sorted(_files(path)), "vendor_reason": "",
            })

    drift = [r["skill"] for r in rows if r["status"] == STATUS_DRIFT]
    missing = [r["skill"] for r in rows if r["status"] == STATUS_MISSING]
    orphan = [r["skill"] for r in rows if r["status"].startswith("孤儿")]

    why = []
    if not units:
        why.append("源一个技能都没枚举到（%s）" % " / ".join(s["label"] for s in SOURCES))
    for key, hub in HUBS.items():
        if not hub.is_dir():
            why.append("枢纽根不存在：%s（%s）" % (hub, "自有技能" if key == "home" else "第三方技能"))

    return {
        "rows": rows,
        "summary": {
            "ok": not drift and not missing and not orphan and not why,
            "total": len(rows),
            "drift": len(drift),
            "missing": len(missing),
            "orphan": len(orphan),
            "ok_count": sum(1 for r in rows if r["status"] == STATUS_OK),
            "why": why,
        },
        "home_hub": str(HUBS["home"]),
        "hubs": {k: {"path": str(v), "exists": v.is_dir()} for k, v in HUBS.items()},
        "sources": [{"key": s["key"], "path": str(s["path"]), "exists": s["path"].is_dir()}
                    for s in SOURCES],
        "vendor": VENDOR,
    }


# ── 同步 ────────────────────────────────────────────────────────────────────
def _backup(name: str, hub: pathlib.Path, stamp: str) -> str:
    src = hub / name
    if not src.is_dir():
        return ""
    dst = BACKUP_BASE / stamp / hub.name / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return str(dst)


def do_sync(only=None) -> dict:
    """把「未安装 / 分叉」的技能补到枢纽。**只补不删** —— 删孤儿要人判断。"""
    st = survey()
    units = _units()
    stamp = time.strftime("%Y%m%d-%H%M%S")

    todo = [r for r in st["rows"]
            if r["status"] in (STATUS_MISSING, STATUS_DRIFT)
            and (only is None or r["skill"] in only)]

    synced, failed, backups = [], [], []
    for r in todo:
        name = r["skill"]
        u = units.get(name)
        if not u:
            failed.append({"skill": name, "error": "源里找不到这个技能"})
            continue
        hub = _target_hub(u["own"])
        try:
            b = _backup(name, hub, stamp) if r["status"] == STATUS_DRIFT else ""
            if b:
                backups.append(b)
            hub.mkdir(parents=True, exist_ok=True)
            dst = hub / name
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(u["path"], dst)
            # 回读验证：复制完必须指纹一致，否则不算成功
            if _digest(_files(dst)) != _digest(_files(u["path"])):
                failed.append({"skill": name, "error": "回读指纹不符（复制不完整）"})
                continue
            synced.append({"skill": name, "hub": str(hub), "action": r["status"],
                           "files": r["files"], "backup": b})
        except OSError as e:
            failed.append({"skill": name, "error": "%s: %s" % (type(e).__name__, e)})

    return {
        "ok": not failed,
        "stamp": stamp,
        "synced": synced,
        "failed": failed,
        "backup_root": str(BACKUP_BASE / stamp) if backups else "",
        "how": "回滚：把 backup_root 下 <hub>/<技能名>/ 拷回对应枢纽即可",
    }


# ── CLI ─────────────────────────────────────────────────────────────────────
def _print_report(st: dict) -> int:
    s = st["summary"]
    print("源 :")
    for x in st["sources"]:
        print("   %-42s %s" % (x["path"], "在" if x["exists"] else "❌ 不存在"))
    print("枢纽:")
    for k, v in st["hubs"].items():
        print("   %-42s %s（%s）" % (v["path"], "在" if v["exists"] else "❌ 不存在",
                                    "自有" if k == "home" else "第三方"))
    print()
    print("  技能 %d 条（一个技能 = 一个带 SKILL.md 的目录，枢纽里平铺）" % s["total"])
    print("  一致 %d / 分叉 %d / 未安装 %d / 孤儿 %d"
          % (s["ok_count"], s["drift"], s["missing"], s["orphan"]))
    print()
    for r in st["rows"]:
        mark = {STATUS_OK: "✅", STATUS_DRIFT: "⚠️", STATUS_MISSING: "❌", STATUS_ORPHAN: "👻"}.get(
            r["status"], "?")
        extra = ""
        if r["status"] == STATUS_DRIFT:
            bits = []
            if r["changed"]:
                bits.append("内容异 %d" % len(r["changed"]))
            if r["missing"]:
                bits.append("缺 %d" % len(r["missing"]))
            if r["residue"]:
                bits.append("多 %d" % len(r["residue"]))
            extra = "（%s）" % " · ".join(bits)
        elif r["status"] == STATUS_MISSING:
            extra = "（%d 件待装 → %s）" % (len(r["missing"]), "home" if r["own"] else "repo")
        pkg = "" if r["package"] in ("", r["skill"]) else "  ← 来自包 %s" % r["package"]
        print("  %s %-32s %-14s%s%s" % (mark, r["skill"], r["status"], extra, pkg))
    print()
    for w in s["why"]:
        print("  ❌ " + w)
    print("结论:", "四条全过（源 ↔ 装 逐技能一致）" if s["ok"]
          else "有判据没过 —— 别宣称技能已同步；修法：python tools/skills_sync.py sync")
    return 0 if s["ok"] else 1


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "check"

    if cmd in ("check", "status", ""):
        return _print_report(survey())

    if cmd == "sync":
        if "--dry" in argv or "--dry-run" in argv:
            st = survey()
            todo = [r["skill"] for r in st["rows"]
                    if r["status"] in (STATUS_MISSING, STATUS_DRIFT)]
            print("待同步 %d 条：%s" % (len(todo), ", ".join(todo) if todo else "无"))
            print("（这是干跑；去掉 --dry 才真复制）")
            return 0 if not todo else 1
        out = do_sync()
        print("已同步 %d 条：%s" % (len(out["synced"]),
                                    ", ".join(x["skill"] for x in out["synced"]) or "无"))
        if out["backup_root"]:
            print("备份: %s" % out["backup_root"])
        for f in out["failed"]:
            print("  ❌ %s: %s" % (f["skill"], f["error"]))
        return 0 if out["ok"] else 1

    print("不认的命令：%s" % cmd)
    print("用法: python tools/skills_sync.py [check|sync [--dry]]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
