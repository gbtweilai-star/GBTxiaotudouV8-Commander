# gbt-capability: asset_index
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""资产索引 · **整棵树都连上 + 连上即可秒查**（主人令 2026-09-27）。

主人原话：「必须确保触手连接所有能力**以及整个项目树的文件每一页都要连接**，
以及**设计好快速搜索，只要连接的瞬间就可以找到**。」

## 三件事，一个工具
  1. **索引（index）**：把整棵树扫进一张表（路径/名/扩展名/大小/时间/所属触手标签），
     落 `state/asset_index.db`（SQLite，标准库，无外部依赖）；
  2. **连接（wire）**：给**每一个**文件补上触手标签 —— 启发式认不出就用**回退标签**
     （`project_context`），于是"每页都连着"，**不留无标签的裸文件**；
     ⚠️ 回退标签是**诚实标注**（"这页归项目上下文管"），不是假装认出了它属于哪个专门触手；
  3. **秒查（find）**：查的是**索引**不是盘 —— 连上的瞬间就能按文件名/路径/标签找到它。
     实测口径：查询走 SQLite（`state/asset_index.db`），**不 rglob、不 resolve**。

## 为什么不是"再扫一遍盘"
早先每次查都要 walk 一遍树（218k 文件，几十秒）——**查一次疼一次**。
索引把"找"从"扫"里拆出来：**扫一次（建索引），之后毫秒级**。

命令：
  python tools/asset_index.py build                 # 建/重建索引（扫全树）
  python tools/asset_index.py wire [--dry]          # 给未连接的文件补标签（默认先干跑）
  python tools/asset_index.py find <关键词> [--limit 20] [--label X] [--ext .py]
  python tools/asset_index.py stats                 # 索引与连接率读数
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sqlite3
import sys
import time
from pathlib import Path

# 🔴 2026-10-30 修：硬编码 Windows 根在 Linux 上会被当成**相对路径**，
#   于是每次运行都在仓里造一个叫 `C:\Users\ADMIN\...` 的垃圾目录。
ROOT = Path(__import__("os").environ.get("GBT_ROOT")
            or Path(__file__).resolve().parents[1])
DB = ROOT / "state" / "asset_index.db"
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".pylibs", ".mimosa", ".scratch",
             ".trash", ".backups", "dist", "vendor", "_upstream", ".fleet"}


def _tb():
    """复用绑定系统（**一处定义两处用**：跳过面与标签建议都不抄第二份）。"""
    sp = importlib.util.spec_from_file_location("tb_idx", ROOT / "tools" / "tentacle_bind.py")
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def _walk(labels: dict, note=print):
    """扫全树 → yield (rel, name, ext, size, mtime)。跳过面与绑定系统一致。"""
    n = 0
    for dp, dn, fn in os.walk(ROOT, onerror=lambda e: None):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            p = Path(dp) / f
            try:
                st = p.stat()
            except OSError:
                continue
            rel = str(p.relative_to(ROOT)).replace("\\", "/")
            yield rel, f, p.suffix.lower(), st.st_size, int(st.st_mtime)
            n += 1
            if n % 50000 == 0:
                note(f"  … 已索引 {n}")


def build(verbose: bool = True) -> dict:
    t0 = time.time()
    tb = _tb()
    binds = tb._load()
    DB.parent.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(str(DB))
    # ⚠️ 血账（2026-09-27）：键必须**跟随联接点**（与绑定系统同口径）——`.claude/skills`、
    # `.aider-desk/skills` 等是指向 `.agents/skills/` 的软链，按遍历路径做键会把同一份真身
    # 数成好几遍（实测 4057 件抽样里键不同的占三成，于是"未连接 11,936"是重复计数）。
    # 键 = tb._rel(p)（物理真身）；rel = 遍历路径（人读用）。
    con.execute("CREATE TABLE assets(key TEXT PRIMARY KEY, rel TEXT, name TEXT, ext TEXT, "
                "size INTEGER, mtime INTEGER, label TEXT, asset INTEGER)")
    con.execute("CREATE INDEX i_name ON assets(name)")
    con.execute("CREATE INDEX i_label ON assets(label)")
    batch, total, labeled, aliases, assets_n = [], 0, 0, 0, 0
    seen_keys = set()
    for rel, name, ext, size, mtime in _walk({}, note=(print if verbose else (lambda *_: None))):
        key = tb._rel(ROOT / rel)
        if key in seen_keys:                    # 软链别名：同一物理文件只入一次
            aliases += 1
            continue
        seen_keys.add(key)
        row = binds.get(key) or {}
        lbl = ",".join(row.get("tentacles") or [])
        # **是不是资产**：用绑定系统自己的口径判（store/config/缓存/瞬态件 → 非资产）。
        # 不这么分，"未连接"里会混进几千件按政策就该跳过的文件 ⇒ 读数自相矛盾（实测踩过）。
        try:
            is_asset = 0 if tb._skippable(rel) else 1
        except Exception:                                      # noqa: BLE001
            is_asset = 1
        if lbl:
            labeled += 1
        assets_n += is_asset
        batch.append((key, rel, name, ext, size, mtime, lbl, is_asset))
        total += 1
        if len(batch) >= 20000:
            con.executemany("INSERT OR REPLACE INTO assets VALUES (?,?,?,?,?,?,?,?)", batch)
            batch.clear()
    if batch:
        con.executemany("INSERT OR REPLACE INTO assets VALUES (?,?,?,?,?,?,?,?)", batch)
    con.commit()
    con.close()
    out = {"ok": True, "indexed": total, "asset": assets_n, "labeled": labeled,
           "资产未连接": assets_n - labeled if assets_n >= labeled else 0,
           "非资产(按口径跳过)": total - assets_n, "软链别名去重": aliases, "db": str(DB),
           "耗时s": round(time.time() - t0, 1)}
    if verbose:
        print(f"索引完成：{total} 个**物理**文件（软链别名去重 {aliases}）")
        print(f"  其中**资产**（按绑定口径）{assets_n}：已连接 {labeled} · 未连接 {assets_n - labeled}")
        print(f"  非资产 {total - assets_n}（store/config/缓存/瞬态件，按政策跳过）")
        print(f"  {out['耗时s']}s → {DB}")
    return out


def wire(dry: bool = True, limit: int = 0) -> dict:
    """**每一页都连上**：未连接的文件补标签（启发式优先；认不出用回退标签）。"""
    tb = _tb()
    binds = tb._load()
    todo = []
    for dp, dn, fn in os.walk(ROOT, onerror=lambda e: None):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            p = Path(dp) / f
            rel = str(p.relative_to(ROOT)).replace("\\", "/")
            # 判断"该不该算资产"用绑定系统自己的口径（跳过面一处定义）
            try:
                if tb._skippable(rel):
                    continue
            except Exception:                                  # noqa: BLE001
                pass
            if tb._rel(p) in binds:               # 同口径键：软链别名不会重复补绑
                continue
            lbl = tb.suggest(rel) or "project_context"      # 回退标签：诚实标注归属
            todo.append((tb._rel(p), lbl))
            if limit and len(todo) >= limit:
                break
        if limit and len(todo) >= limit:
            break
    if dry:
        return {"ok": True, "dry": True, "would_bind": len(todo),
                "sample": [f"{r} → {l}" for r, l in todo[:12]],
                "_口径": f"回退标签 project_context 用于启发式认不出的文件；本机共 {len(todo)} 件（限 {limit or '无'}）"}
    bound = 0
    for key, lbl in todo:
        tb.bind(str(ROOT / key), lbl, note="asset_index.wire", quiet=True)
        bound += 1
    return {"ok": True, "dry": False, "bound": bound,
            "_口径": "全部走 tentacle_bind.bind（追加式台账只增不删）"}


def find(q: str, limit: int = 20, label: str = "", ext: str = "") -> dict:
    """**秒查**：查索引，不扫盘。"""
    if not DB.is_file():
        return {"ok": False, "why": "没有索引 ⇒ 先跑：python tools/asset_index.py build"}
    t0 = time.perf_counter()
    con = sqlite3.connect(str(DB))
    sql = "SELECT rel, size, label FROM assets WHERE (rel LIKE ? OR key LIKE ? OR name LIKE ?)"
    args = [f"%{q}%", f"%{q}%", f"%{q}%"]
    if label:
        sql += " AND label LIKE ?"
        args.append(f"%{label}%")
    if ext:
        sql += " AND ext = ?"
        args.append(ext if ext.startswith(".") else "." + ext)
    sql += " ORDER BY size DESC LIMIT ?"
    args.append(limit)
    rows = con.execute(sql, args).fetchall()
    total = con.execute("SELECT COUNT(*) FROM assets WHERE rel LIKE ? OR key LIKE ? OR name LIKE ?",
                        [f"%{q}%", f"%{q}%", f"%{q}%"]).fetchone()[0]
    con.close()
    ms = (time.perf_counter() - t0) * 1000
    return {"ok": True, "q": q, "hits": total, "shown": len(rows),
            "ms": round(ms, 2),
            "rows": [{"rel": r, "size": s, "label": l or "（未连接）"} for r, s, l in rows],
            "_口径": "查的是 state/asset_index.db（SQLite），**不扫盘**；ms 为查询耗时"}


def stats() -> dict:
    if not DB.is_file():
        return {"ok": False, "why": "没有索引 ⇒ 先跑 build"}
    con = sqlite3.connect(str(DB))
    total = con.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    labeled = con.execute("SELECT COUNT(*) FROM assets WHERE label != ''").fetchone()[0]
    assets_n = con.execute("SELECT COUNT(*) FROM assets WHERE asset = 1").fetchone()[0]
    by_ext = con.execute("SELECT ext, COUNT(*) c FROM assets GROUP BY ext ORDER BY c DESC LIMIT 12").fetchall()
    by_lbl = con.execute("SELECT label, COUNT(*) c FROM assets WHERE label != '' "
                         "GROUP BY label ORDER BY c DESC LIMIT 12").fetchall()
    con.close()
    return {"ok": True, "indexed": total, "asset": assets_n, "labeled": labeled,
            "资产未连接": max(0, assets_n - labeled), "非资产": total - assets_n,
            "资产连接率": round(labeled / max(1, assets_n), 4),
            "按扩展名": dict(by_ext), "按触手标签": dict(by_lbl)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="资产索引：整树连接 + 秒查")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    s = sub.add_parser("wire"); s.add_argument("--dry", action="store_true"); s.add_argument("--limit", type=int, default=0)
    s = sub.add_parser("find"); s.add_argument("q"); s.add_argument("--limit", type=int, default=20)
    s.add_argument("--label", default=""); s.add_argument("--ext", default="")
    sub.add_parser("stats")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        r = build(); return 0
    if a.cmd == "wire":
        r = wire(dry=True) if a.dry else wire(dry=False, limit=a.limit)
        if r.get("dry"):
            print(f"干跑：将连接 {r['would_bind']} 件（回退标签 project_context）")
            for s_ in r["sample"]:
                print("   ", s_)
        else:
            print(f"已连接 {r['bound']} 件（全部走 tentacle_bind.bind，台账只增不删）")
        return 0
    if a.cmd == "find":
        r = find(a.q, a.limit, a.label, a.ext)
        if not r.get("ok"):
            print(r["why"]); return 2
        print(f"「{a.q}」命中 {r['hits']} 件 · 查询 {r['ms']}ms（查索引，不扫盘）")
        for row in r["rows"]:
            print(f"  {row['size']:>10}  [{row['label']}]  {row['rel']}")
        return 0
    if a.cmd == "stats":
        r = stats()
        print(f"索引 {r['indexed']} 件：资产 {r['asset']}（已连接 {r['labeled']} · "
              f"未连接 {r['资产未连接']} · **资产连接率 {r['资产连接率']}**）· "
              f"非资产 {r['非资产']}")
        print("  按扩展名：", r["按扩展名"])
        print("  按触手标签：", r["按触手标签"])
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
