"""版本库外的回滚点（只读工作区 · 只写自己的快照目录）—— 现读那 22 件"孤岛"。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要有它（2026-09-25 主人问「开源仓库你更新了吗」翻出来的）
现读：**本会话改的 22 件，在 `git status` 里全是 `??`（未跟踪）**；
`docs/` 整棵树 **0 个**已跟踪；`memory/` 只跟踪 10 个（**不含** `在办清单.md` / `防忘清单.md`）。
⇒ 没有历史、没有回滚点。而 `git add/commit` 是**版本库写面**（`git_write` 挂 `filesystem_write`），
**没主人授权我不动**。

在等授权期间，**这件事我可以做**：把这一批文件**按内容+哈希**存一份到自己的快照目录
（只写 `.scratch/snapshots/`，不碰 `.git`、不碰任何被跟踪的文件）⇒ **今天就有回滚点**。

## 口径
- **只快照"关键未跟踪件"**（工具 + 文档 + 账本 + 状态基线），不是全仓 —— 全仓 3.8 万件不是我的活；
- 清单**现读**（`git status --porcelain` 取 `??`），**不写死**；
- 每件记 `sha256 + 字节数`；`verify` 逐件比对**快照 ↔ 工作区**，差异逐条点名；
- **没快照 ⇒ rc=2**；**清单为空 ⇒ 拒绝**（空快照不算快照）。

用法：
  python tools/codex-scripts/untracked-snapshot.py snapshot
  python tools/codex-scripts/untracked-snapshot.py verify [--at <时间戳>]
  python tools/codex-scripts/untracked-snapshot.py selftest
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAPS = ROOT / ".scratch" / "snapshots"
# 只收这些树里的"关键未跟踪件"（现读，不写死清单）
KEEP_TREES = ("tools/codex-scripts/", "docs/", "memory/", "state/")

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def untracked() -> list:
    """现读未跟踪文件（`git status --porcelain` 的 `??` 行），只留关键树。"""
    p = subprocess.run(["git", "status", "--porcelain", "-z"], cwd=str(ROOT),
                       capture_output=True)
    raw = p.stdout.decode("utf-8", errors="replace")
    out = []
    for item in raw.split("\0"):
        if len(item) < 4 or not item.startswith("?? "):
            continue
        rel = item[3:].replace("\\", "/")
        if any(rel.startswith(t) for t in KEEP_TREES) and not rel.endswith("/"):
            f = ROOT / rel
            if f.is_file():
                out.append(rel)
    return sorted(set(out))


def snapshot() -> int:
    files = untracked()
    if not files:
        print(json.dumps({"ok": False, "拒绝": "**清单为空 ⇒ 拒绝**（空快照不算快照）"},
                         ensure_ascii=False, indent=1))
        return 2
    ts = time.strftime("%Y%m%dT%H%M%S")
    dest = SNAPS / ts
    rows = []
    for rel in files:
        src = ROOT / rel
        dst = dest / "files" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        rows.append({"件": rel, "字节": src.stat().st_size, "sha256": _sha(src)})
    (dest / "MANIFEST.json").write_text(json.dumps(
        {"at": ts, "件数": len(rows), "总字节": sum(r["字节"] for r in rows),
         "口径": "只快照关键未跟踪件（工具/文档/账本/状态）—— 等主人授权入库前的回滚点",
         "逐件": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"快照": {"at": ts, "件数": len(rows),
                             "总字节": sum(r["字节"] for r in rows)},
                      "落点": str(dest.relative_to(ROOT))}, ensure_ascii=False, indent=1))
    return 0


def _latest() -> Path | None:
    if not SNAPS.is_dir():
        return None
    ds = sorted([d for d in SNAPS.iterdir() if d.is_dir()])
    return ds[-1] if ds else None


def verify_report(at: str | None = None) -> tuple[int, dict]:
    """**只算不打印**：快照 ↔ 工作区逐件比对。"""
    d = (SNAPS / at) if at else _latest()
    if d is None or not d.is_dir():
        return 2, {"类别": "没快照", "判决": "🔴 **没快照** ⇒ 先 `snapshot`（没有快照就没有回滚点）"}
    man = d / "MANIFEST.json"
    if not man.is_file():
        return 2, {"类别": "未读到清单", "判决": "🔴 **未读到清单**（%s）⇒ 拒" % man.name}
    m = json.loads(man.read_text(encoding="utf-8"))
    if "逐件" not in m or not m["逐件"]:
        return 2, {"类别": "清单为空", "判决": "🔴 **清单是空的** ⇒ 不算快照"}
    changed, gone, missing_copy = [], [], []
    for r in m["逐件"]:
        w = ROOT / r["件"]
        c = d / "files" / r["件"]
        if not w.is_file():
            gone.append(r["件"])
            continue
        if _sha(w) != r["sha256"]:
            changed.append(r["件"])
        if not c.is_file() or _sha(c) != r["sha256"]:
            missing_copy.append(r["件"])
    ok = not (changed or gone or missing_copy)
    return (0 if ok else 1), {
        "类别": "一致" if ok else "有差异", "快照": m["at"], "件数": m["件数"],
        "**工作区已变（自快照后）**": changed, "**工作区已删**": gone,
        "**快照副本坏了（sha 对不上）**": missing_copy,
        "判决": ("✅ 快照与工作区逐件一致（回滚点有效）" if ok else
               "🔴 有差异：变了 %d · 删了 %d · 副本坏了 %d ⇒ 要么是这几轮真改了（重新 snapshot），"
               "要么是副本损坏（别用它回滚）" % (len(changed), len(gone), len(missing_copy)))}


def verify(at: str | None = None) -> int:
    rc, out = verify_report(at)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return rc


def selftest() -> int:
    checks, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad = bad + (0 if cond else 1)
        checks.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    import tempfile as _tf

    with _tf.TemporaryDirectory() as tds:
        global SNAPS                                   # 自检里把快照根指到临时目录
        keep, SNAPS = SNAPS, Path(tds) / "snaps"
        try:
            work = Path(tds) / "work"
            (work / "tools").mkdir(parents=True)
            f = work / "tools" / "a.py"
            f.write_text("x = 1\n", encoding="utf-8")
            # 手工造一份"快照"（不依赖 git，好上负控）
            d = SNAPS / "20260101T000000"
            (d / "files" / "tools").mkdir(parents=True)
            shutil.copy2(f, d / "files" / "tools" / "a.py")
            (d / "MANIFEST.json").write_text(json.dumps(
                {"at": "20260101T000000", "件数": 1,
                 "逐件": [{"件": "tools/a.py", "字节": 6, "sha256": _sha(f)}]},
                ensure_ascii=False), encoding="utf-8")
            global ROOT
            keep_root, ROOT = ROOT, work
            try:
                rc, out = verify_report("20260101T000000")
                ck("**正控：快照与工作区一致 ⇒ rc=0**",
                   rc == 0 and out.get("类别") == "一致", out.get("类别"))
                f.write_text("x = 2\n", encoding="utf-8")
                rc, out = verify_report("20260101T000000")
                ck("**负控：工作区改了一个字节 ⇒ 必须点名**",
                   rc == 1 and out.get("**工作区已变（自快照后）**") == ["tools/a.py"],
                   str(out.get("**工作区已变（自快照后）**")))
                f.unlink()
                rc, out = verify_report("20260101T000000")
                ck("**负控：工作区文件被删 ⇒ 必须点名**",
                   rc == 1 and out.get("**工作区已删**") == ["tools/a.py"], "")
                f.write_text("x = 2\n", encoding="utf-8")
                (d / "files" / "tools" / "a.py").write_text("坏", encoding="utf-8")
                rc, out = verify_report("20260101T000000")
                ck("**负控：快照副本 sha 对不上 ⇒ 必须点名（别用它回滚）**",
                   rc == 1 and out.get("**快照副本坏了（sha 对不上）**") == ["tools/a.py"], "")
                rc, out = verify_report("19990101T000000")
                ck("**边界：指定的快照不在 ⇒ rc=2**", rc == 2, out.get("类别"))
                (d / "MANIFEST.json").write_text(json.dumps({"at": "x", "逐件": []}),
                                                 encoding="utf-8")
                rc, out = verify_report("20260101T000000")
                ck("**边界：清单为空 ⇒ 拒绝**（空快照不算快照）",
                   rc == 2 and out.get("类别") == "清单为空", out.get("类别"))
                (d / "MANIFEST.json").unlink()
                rc, out = verify_report("20260101T000000")
                ck("**边界：清单文件不在 ⇒ rc=2 且类别=未读到清单**",
                   rc == 2 and out.get("类别") == "未读到清单", out.get("类别"))
            finally:
                ROOT = keep_root
        finally:
            SNAPS = keep
    ck("**现读：关键未跟踪件清单非空**（该收的都收得到）",
       len(untracked()) > 0, "现读 %d 件" % len(untracked()))
    print(json.dumps({"自检": {"条数": len(checks), "通过": len(checks) - bad, "不通过": bad},
                      "逐条": checks}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["snapshot", "verify", "selftest"])
    ap.add_argument("--at", help="verify 专用：指定快照时间戳（默认最新）")
    a = ap.parse_args()
    if a.cmd == "selftest":
        return selftest()
    if a.cmd == "snapshot":
        return snapshot()
    return verify(a.at)


if __name__ == "__main__":
    raise SystemExit(main())
