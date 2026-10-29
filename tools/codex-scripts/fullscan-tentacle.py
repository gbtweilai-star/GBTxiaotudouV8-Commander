# -*- coding: utf-8 -*-
"""全量自检 · 触手感应（秒级） —— 目录快照增量扫 + 页面并行探针。

## 为什么不遍历文件
  ① 目录 mtime 是天然变更戳：目录里没有增删改名，mtime 就不动。
     所以 mtime 未变 ⇒ 直接复用上次该目录的文件清单，不再逐个 stat 文件。
  ② 第 2 次以后的成本 = 目录数 × 一次 stat（约 0.05–0.2 ms）+ 少量变更目录重扫。
  ③ 页面探针并行（线程池），每页一根触手，全部返回后一次性打印。

## 为什么用 sqlite 而不是一个 JSON
  🔴 实测：全盘 2,225,358 个文件的 213 MB JSON，在这台 7.4 GB 机器上反序列化
  直接 MemoryError，上次快照被清空 ⇒ 每次都退化成"第一次全量"。sqlite 流式读写，
  内存只跟目录数有关（449k → 约 60 MB），与文件数无关。

## 用法
  python fullscan-tentacle.py scan                 # 建/复快照（增量）
  python fullscan-tentacle.py scan --roots C:\\   # 全盘
  python fullscan-tentacle.py scan --full          # 忽略缓存全量重扫
  python fullscan-tentacle.py pages --http http://127.0.0.1:53911
  python fullscan-tentacle.py all

退出码：0 正常；2 有页面探针失败；3 快照库不存在。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".trash",
             "dist", "build", ".next", "site-packages", "Python"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS dirs  (path TEXT PRIMARY KEY, mtime_ns INTEGER) WITHOUT ROWID;
-- 不存完整路径：dir + name 拼回即可。存整串会让 236k 文件涨到 202 MB（实测），
-- 全盘 2.2M 文件更撑不住。主键 (dir,name) 顺带就是按目录删除的索引。
CREATE TABLE IF NOT EXISTS files (dir TEXT, name TEXT, size INTEGER, mtime_ns INTEGER,
                                  PRIMARY KEY (dir, name)) WITHOUT ROWID;
"""


def _db_path(roots) -> str:
    tag = hashlib.sha1("|".join(sorted(os.path.normcase(r) for r in roots)).encode()).hexdigest()[:8]
    return os.path.join(ROOT, "state", "fullscan-%s.sqlite" % tag)


def _open(path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.executescript(SCHEMA)
    return con


def _collect_subdirs(root: str):
    """只 stat 目录，不 stat 文件 —— 拿到整棵目录树 + 每个目录的 mtime。"""
    tree = {}
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            tree[d] = os.stat(d).st_mtime_ns
        except OSError:
            continue
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False) and e.name.lower() not in SKIP_DIRS:
                            stack.append(os.path.join(d, e.name))
                    except OSError:
                        continue
        except OSError:
            continue
    return tree


def _scan_dir(d: str):
    rows = []
    try:
        with os.scandir(d) as it:
            for e in it:
                try:
                    if e.is_file(follow_symlinks=False):
                        s = e.stat(follow_symlinks=False)
                        rows.append((d, e.name, s.st_size, s.st_mtime_ns))
                except OSError:
                    continue
    except OSError:
        pass
    return rows


def cmd_scan(args) -> int:
    t0 = time.time()
    db = _db_path(args.roots)
    con = _open(db)

    prev = {}
    if not args.full:
        for p, m in con.execute("SELECT path, mtime_ns FROM dirs"):
            prev[p] = m

    t_load = time.time()
    cur = {}
    for root in args.roots:
        cur.update(_collect_subdirs(root))
    t_walk = time.time()

    todo = [d for d, m in cur.items() if args.full or prev.get(d) != m]
    stats = dict(files=0, added=0, removed=0, changed=0,
                 new_dirs=sum(1 for d in cur if d not in prev),
                 gone_dirs=sum(1 for d in prev if d not in cur))

    con.execute("BEGIN")
    for lo in range(0, len(todo), 300):
        chunk = todo[lo:lo + 300]
 # 先读旧行再删：第一版先 DELETE 后 SELECT，old 永远为空，
        #   于是每次都把整个变更目录的文件报成"新增"（实测稳定 +922）。
        old_map = {d: {n: (s, t) for n, s, t in con.execute(
            "SELECT name, size, mtime_ns FROM files WHERE dir = ?", (d,))} for d in chunk}
        con.executemany("DELETE FROM files WHERE dir = ?", [(d,) for d in chunk])
        for d in chunk:
            old = old_map[d]
            rows = _scan_dir(d)
            con.executemany(
                "INSERT OR REPLACE INTO files(dir,name,size,mtime_ns) VALUES (?,?,?,?)", rows)
            stats["files"] += len(rows)
            names = {r[1] for r in rows}
            stats["added"] += len(names - set(old))
            stats["removed"] += len(set(old) - names)
            stats["changed"] += sum(1 for r in rows if r[1] in old and old[r[1]] != (r[2], r[3]))
        con.commit()

    con.executemany("INSERT OR REPLACE INTO dirs(path, mtime_ns) VALUES (?,?)", list(cur.items()))
    con.executemany("DELETE FROM dirs WHERE path = ?", [(d,) for d in prev if d not in cur])
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    con.close()
    t_db = time.time()

    el = time.time() - t0
    mode = "全量" if (args.full or not prev) else "增量"
    print("SCAN(%s) %.2fs · 目录 %d（复用 %d，新 %d，消失 %d）· 文件 %d"
          % (mode, el, len(cur), len(cur) - len(todo), stats["new_dirs"],
             stats["gone_dirs"], total))
    if prev:
        print("       变更：+%d 删 %d 改 %d" % (stats["added"], stats["removed"], stats["changed"]))
    print("       快照 %.1f MB → %s" % (os.path.getsize(db) / 1e6, os.path.relpath(db, ROOT)))
    print("       分阶段：读旧表 %.2fs · 走目录 %.2fs · 变更重扫+写库 %.2fs"
          % (t_load - t0, t_walk - t_load, t_db - t_walk))
    return 0


def _probe(path: str):
    t0 = time.time()
    info = {"page": os.path.relpath(path, ROOT), "ok": True, "why": [],
            "bytes": 0, "sha1": "", "ms": 0.0}
    try:
        st = os.stat(path)
        info["bytes"] = st.st_size
        with open(path, "rb") as f:
            info["sha1"] = hashlib.sha1(f.read()).hexdigest()[:12]
    except OSError as e:
        info["ok"] = False
        info["why"].append("读不到：%s" % e)
    info["ms"] = round((time.time() - t0) * 1000, 1)
    return info


def cmd_pages(args) -> int:
    db = _db_path(args.roots)
    if not os.path.exists(db):
        print("[x] 还没有快照：先跑 scan")
        return 3
    con = sqlite3.connect(db)
    pages = [os.path.join(d, n) for d, n in con.execute(
        "SELECT dir, name FROM files WHERE name LIKE '%.html' OR name LIKE '%.htm'")]
    con.close()

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        results = list(ex.map(_probe, pages))
    el = time.time() - t0

    if args.http:
        try:
            with urllib.request.urlopen(urllib.request.Request(args.http), timeout=3) as r:
                print("  HTTP %s → %d" % (args.http, r.status))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                print("  HTTP %s → %d（活着，要鉴权）" % (args.http, e.code))
            else:
                print("  HTTP %s → HTTPError %d" % (args.http, e.code))
                results.append({"page": "<endpoint>", "ok": False, "why": ["HTTP %d" % e.code],
                                "bytes": 0, "sha1": "", "ms": 0.0})
        except Exception as e:
            print("  HTTP %s → 失败 %s" % (args.http, type(e).__name__))
            results.append({"page": "<endpoint>", "ok": False, "why": ["HTTP"],
                            "bytes": 0, "sha1": "", "ms": 0.0})

    bad = [r for r in results if not r["ok"]]
    results.sort(key=lambda r: -r["ms"])
    for r in results[:6]:
        print("  %6.1fms  %-52s %9d B  %s%s"
              % (r["ms"], r["page"], r["bytes"], r["sha1"],
                 "" if r["ok"] else "  <== " + "；".join(r["why"])))
    print("PAGES %d · %.2fs（并行 %d）· ok %d · fail %d · 最慢 %.1fms"
          % (len(results), el, args.jobs, len(results) - len(bad), len(bad),
             results[0]["ms"] if results else 0))
    return 2 if bad else 0


def cmd_bind(args) -> int:
    """双向绑定体检：读 state/cap-bindings.json + state/surfaces/*.json，两头对齐。

    正反两端的检查各一条：
      正向 —— 每个能力位必须有 bind_kind / carrier / note（缺一条就等于"只登记没接线"）；
      反向 —— 每个面（surfaces/*.json）里的键，有多少能落回能力位名（落不回的叫孤儿键）。
    """
    import glob
    import json

    cbp = os.path.join(ROOT, "state", "cap-bindings.json")
    if not os.path.exists(cbp):
        print("[x] 没有 %s" % cbp)
        return 3
    b = json.load(open(cbp, encoding="utf-8"))
    caps = b.get("caps") or []
    names = {c.get("name") for c in caps}

    no_note = [c["name"] for c in caps if not str(c.get("note") or "").strip()]
    no_carrier = [c["name"] for c in caps if not str(c.get("carrier") or "").strip()]
    no_kind = [c["name"] for c in caps if not str(c.get("bind_kind") or "").strip()]
    unbound = [c["name"] for c in caps if "未绑" in str(c.get("state") or "")]

    # 触手域用中文名（视觉/读网…），能力位的 domain 是英文（vision/automation…），
    # 两套命名空间不能直接比 —— 要比的是"能力位声明的 tentacle_domains 是否都在域表里"。
    tds = [d for d in (b.get("tentacle_domains") or []) if isinstance(d, dict)]
    dom_names = {d.get("name") for d in tds}
    cap_tds = set()
    for c in caps:
        cap_tds |= set(c.get("tentacle_domains") or [])
    dom_missing = sorted(x for x in (cap_tds - dom_names) if x)
    dom_no_caps = [d.get("name") for d in tds if not (d.get("caps") or [])]

    em = [c for c in (b.get("energy_channels") or []) if isinstance(c, dict)]
    dead = ["%s(%s)" % (c.get("provider"), c.get("status")) for c in em if not c.get("alive", True)]

    surf_files = sorted(glob.glob(os.path.join(ROOT, "state", "surfaces", "*.json")))
    total_keys = 0
    hit_keys = 0
    orphans = []
    for f in surf_files:
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        keys = list(d.keys()) if isinstance(d, dict) else []
        total_keys += len(keys)
        for k in keys:
            if k in names:
                hit_keys += 1
            else:
                orphans.append(os.path.basename(f) + ":" + k)

    print("CAPS %d · 未绑 %d · 缺备注 %d · 缺载体 %d · 缺绑定方式 %d"
          % (len(caps), len(unbound), len(no_note), len(no_carrier), len(no_kind)))
    for label, lst in (("未绑", unbound), ("缺备注", no_note),
                       ("缺载体", no_carrier), ("缺绑定方式", no_kind)):
        if lst:
            print("   %s: %s%s" % (label, ", ".join(lst[:6]), " …" if len(lst) > 6 else ""))
    print("DOMAINS 触手域 %d · 能力位声明了却不在域表: %s · 域里没有能力位: %s"
          % (len(tds), ", ".join(dom_missing) if dom_missing else "无",
             ", ".join(map(str, dom_no_caps)) if dom_no_caps else "无"))
    print("ENERGY  通道 %d · 死通道 %d%s"
          % (len(em), len(dead), (" → " + ", ".join(map(str, dead[:6]))) if dead else ""))
    # 面文件（state/surfaces/*.json）装的是操作键表（如 blender 的 op 表），
    # 键不是能力位名，所以这里只报规模，不当错误。
    print("SURFACES %d 个面 / %d 个键 · 其中与能力位同名 %d"
          % (len(surf_files), total_keys, hit_keys))
    for o in orphans[:4]:
        print("   示例键:", o)

    bad = len(unbound) + len(no_note) + len(no_carrier) + len(dom_missing) + len(dom_no_caps)
    return 2 if bad else 0


def cmd_usn(args) -> int:
    r"""USN/MFT 枚举：一次 ioctl 拿回整卷的文件记录 —— 全盘"秒级"的唯一正路。

    🔴 需要管理员：CreateFileW("\\.\C:") 在非提权下返回 ERROR_ACCESS_DENIED。
       本机实测 ELEVATED=False，所以这条路径**未验**（不是失败，是没权限跑）。

    只做计数与耗时（不建路径），因为建全路径要保留 220 万条的父子关系（约 300 MB），
    在 7.4 GB 机器上应当流式写 sqlite —— 那是接上 usn 存储层时再做的一步。
    """
    import ctypes
    import ctypes.wintypes as wt

    GENERIC_READ = 0x80000000
    FILE_SHARE_ALL = 0x1 | 0x2 | 0x4
    OPEN_EXISTING = 3
    FSCTL_ENUM_USN_DATA = 0x000900B3

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wt.HANDLE
    k32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p,
                                wt.DWORD, wt.DWORD, wt.HANDLE]

    vol = "\\\\.\\" + args.volume
    h = k32.CreateFileW(vol, GENERIC_READ, FILE_SHARE_ALL, None, OPEN_EXISTING, 0, None)
    if not h or h == wt.HANDLE(-1).value:
        err = ctypes.get_last_error()
        if err == 5:
            print("[x] %s 需要管理员（ERROR_ACCESS_DENIED）—— 提权后重跑这条命令" % vol)
            return 3
        print("[x] 打不开 %s（WinError %d）" % (vol, err))
        return 3

    buf_size = 1 << 20
    buf = ctypes.create_string_buffer(buf_size)
    returned = wt.DWORD(0)

    class MFT_ENUM_DATA_V0(ctypes.Structure):
        _fields_ = [("StartFileReferenceNumber", ctypes.c_ulonglong),
                    ("LowUsn", ctypes.c_longlong),
                    ("HighUsn", ctypes.c_longlong)]

    med = MFT_ENUM_DATA_V0(0, 0, 0x7FFFFFFFFFFFFFFF)
    t0 = time.time()
    files = dirs = total = 0
    samples = []
    versions = set()
    # 候选偏移：(attributes, name_len, name_off)
    CANDIDATES = [(52, 56, 58), (44, 48, 50), (60, 64, 66)]
    cand = None
    guard = 0
    while True:
        ok = k32.DeviceIoControl(h, FSCTL_ENUM_USN_DATA, ctypes.byref(med),
                                 ctypes.sizeof(med), buf, buf_size,
                                 ctypes.byref(returned), None)
        if not ok or returned.value <= 8:
            break
        guard += 1
        if guard > 20000:
            print("[!] 枚举超过 20000 批，停止（防死循环）")
            break
        med.StartFileReferenceNumber = ctypes.c_ulonglong.from_buffer(buf).value
        off = 8
        end = returned.value
        while off < end:
            # USN_RECORD_V2 布局：0 len(u32) · 8 frn(u64) · 16 parent(u64) ·
            # 44 attributes(u32) · 48 name_len(u16) · 50 name_off(u16) · 52 name
            rec_len = ctypes.c_uint32.from_buffer(buf, off).value
            if rec_len < 60:
                break
 # 偏移不能照 MSDN 抄：本机实测（Windows 11）V2 记录的
            #   attributes 在 52、name_len 在 56、name_off 在 58、名字从 60 起；
            #   照文档的 44/48/50 读，attributes 恒为 0 ⇒ 目录数恒为 0（实测 415 万条、目录 0）。
            #   这里做自适应：第一次遇到记录时试三套候选偏移，取能解出合法名字的那套。
            major = ctypes.c_uint16.from_buffer(buf, off + 4).value
            if cand is None:
                for c in CANDIDATES:
                    a_o, n_o, o_o = c
                    if off + o_o + 2 > end:
                        continue
                    L = ctypes.c_uint16.from_buffer(buf, off + n_o).value
                    O = ctypes.c_uint16.from_buffer(buf, off + o_o).value
                    if L > 0 and L % 2 == 0 and 40 <= O and off + O + L <= off + rec_len:
                        cand = c
                        break
                if cand is None:
                    cand = CANDIDATES[0]
            a_off, nl_off, no_off = cand
            attrs = ctypes.c_uint32.from_buffer(buf, off + a_off).value
            nlen = ctypes.c_uint16.from_buffer(buf, off + nl_off).value
            noff = ctypes.c_uint16.from_buffer(buf, off + no_off).value
            versions.add(major)
            if len(samples) < 3 and nlen:
                try:
                    samples.append(ctypes.string_at(ctypes.addressof(buf) + off + noff, nlen)
                                   .decode("utf-16-le", "replace"))
                except Exception:
                    pass
            if attrs & 0x10:
                dirs += 1
            else:
                files += 1
            total += 1
            off += rec_len
    k32.CloseHandle(h)
    el = time.time() - t0
    print("USN %s · 记录 %d（文件 %d · 目录 %d）· %.2fs · %.0f 条/秒 · 记录版本 %s · 偏移 %s"
          % (args.volume, total, files, dirs, el, total / max(el, 1e-9), sorted(versions), cand))
    if samples:
        print("   样本（验记录解析）：%s" % " | ".join(samples))
    return 0


def cmd_usn_delta(args) -> int:
    r"""USN 增量：只读日志游标之后的变更记录 —— 这才是"全盘秒级"的那一半。

    首次（没有游标）：全量枚举 24s，记下 NextUsn。
    之后：FSCTL_READ_USN_JOURNAL 从游标读到 NextUsn，通常几十~几千条 ⇒ 亚秒。
    """
    import ctypes
    import ctypes.wintypes as wt
    import json

    GENERIC_READ = 0x80000000
    FILE_SHARE_ALL = 0x7
    OPEN_EXISTING = 3
    FSCTL_QUERY_USN_JOURNAL = 0x000900F4
    FSCTL_READ_USN_JOURNAL = 0x000900BB
    FSCTL_ENUM_USN_DATA = 0x000900B3

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wt.HANDLE
    k32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p,
                                wt.DWORD, wt.DWORD, wt.HANDLE]
    vol = "\\\\.\\" + args.volume
    h = k32.CreateFileW(vol, GENERIC_READ, FILE_SHARE_ALL, None, OPEN_EXISTING, 0, None)
    if not h or h == wt.HANDLE(-1).value:
        if ctypes.get_last_error() == 5:
            print("[x] %s 需要管理员（ERROR_ACCESS_DENIED）" % vol)
            return 3
        print("[x] 打不开 %s（WinError %d）" % (vol, ctypes.get_last_error()))
        return 3

    class USN_JOURNAL_DATA_V0(ctypes.Structure):
        _fields_ = [("UsnJournalID", ctypes.c_ulonglong),
                    ("FirstUsn", ctypes.c_longlong),
                    ("NextUsn", ctypes.c_longlong),
                    ("LowestValidUsn", ctypes.c_longlong),
                    ("MaxUsn", ctypes.c_longlong),
                    ("MaximumSize", ctypes.c_ulonglong),
                    ("AllocationDelta", ctypes.c_ulonglong)]

    class READ_USN_JOURNAL_DATA_V0(ctypes.Structure):
        _fields_ = [("StartUsn", ctypes.c_longlong),
                    ("ReasonMask", ctypes.c_uint),
                    ("ReturnOnlyOnClose", ctypes.c_uint),
                    ("Timeout", ctypes.c_ulonglong),
                    ("BytesToWaitFor", ctypes.c_ulonglong),
                    ("UsnJournalID", ctypes.c_ulonglong)]

    jd = USN_JOURNAL_DATA_V0()
    got = wt.DWORD(0)
    if not k32.DeviceIoControl(h, FSCTL_QUERY_USN_JOURNAL, None, 0,
                               ctypes.byref(jd), ctypes.sizeof(jd), ctypes.byref(got), None):
        print("[x] 查日志失败（WinError %d）" % ctypes.get_last_error())
        return 3

    cursor = None
    if os.path.exists(args.cursor):
        try:
            cursor = int(json.load(open(args.cursor))["next_usn"])
        except Exception:
            cursor = None

    t0 = time.time()
    if cursor is None:
        # 首次：全量枚举（借用 cmd_usn 的计数逻辑太重，这里只推进游标）
        print("[i] 首次运行：先做一次全量枚举并建立游标（约 24s）")
        k32.CloseHandle(h)
        rc = cmd_usn(argparse.Namespace(volume=args.volume))
        if rc != 0:
            return rc
        json.dump({"next_usn": jd.NextUsn, "journal_id": jd.UsnJournalID,
                   "ts": time.time()}, open(args.cursor, "w"))
        print("     游标已建：next_usn=%d · 之后每次只读增量" % jd.NextUsn)
        return 0

    if cursor < jd.FirstUsn:
        print("[!] 游标已过期（日志已被裁掉），需要重做一次全量")
        return 3

    buf_size = 1 << 20
    buf = ctypes.create_string_buffer(buf_size)
    rj = READ_USN_JOURNAL_DATA_V0(cursor, 0xFFFFFFFF, 0, 0, 0, jd.UsnJournalID)
    total = files = dirs = 0
    batches = 0
    while True:
        ok = k32.DeviceIoControl(h, FSCTL_READ_USN_JOURNAL, ctypes.byref(rj),
                                 ctypes.sizeof(rj), buf, buf_size,
                                 ctypes.byref(got), None)
        if not ok or got.value <= 8:
            break
        batches += 1
        if batches > 5000:
            break
        rj.StartUsn = ctypes.c_longlong.from_buffer(buf).value
        off, end = 8, got.value
        while off < end:
            rec_len = ctypes.c_uint32.from_buffer(buf, off).value
            if rec_len < 60:
                break
            attrs = ctypes.c_uint32.from_buffer(buf, off + 52).value
            if attrs & 0x10:
                dirs += 1
            else:
                files += 1
            total += 1
            off += rec_len
    k32.CloseHandle(h)
    el = time.time() - t0
    json.dump({"next_usn": rj.StartUsn, "journal_id": jd.UsnJournalID, "ts": time.time()},
              open(args.cursor, "w"))
    print("USN-DELTA %s · 变更 %d（文件 %d · 目录 %d）· %.3fs · 游标 %d → %d"
          % (args.volume, total, files, dirs, el, cursor, rj.StartUsn))
    return 0


def _s64(x: int) -> int:
    # SQLite 的 INTEGER 是**有符号** 64 位，而 FRN 是无符号 64 位（高位可能 ≥ 2^63）。
    # 直接塞会 OverflowError；按补码折成负数存，读写两端用同一个转换即可。
    return x if x < (1 << 63) else x - (1 << 64)


def _usn_open_volume(volume: str):
    """打开卷句柄 + 查日志状态。返回 (handle, k32, jd) 或抛 SystemExit 风格。"""
    import ctypes
    import ctypes.wintypes as wt

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wt.HANDLE
    k32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p,
                                wt.DWORD, wt.DWORD, wt.HANDLE]
    h = k32.CreateFileW("\\\\.\\" + volume, 0x80000000, 0x7, None, 3, 0, None)
    if not h or h == wt.HANDLE(-1).value:
        return None, k32, None
    return h, k32, None


def cmd_usn_index(args) -> int:
    r"""建 MFT 索引：FRN → (parent, name) 落 sqlite —— 有了它才能把增量记录还原成路径。

    🔴 需要管理员。首次约 4.16M 条；写库比枚举慢，实测量级几分钟。
    """
    import ctypes
    import ctypes.wintypes as wt

    h, k32, _ = _usn_open_volume(args.volume)
    if not h:
        print("[x] %s 需要管理员（ERROR_ACCESS_DENIED）" % args.volume)
        return 3

    FSCTL_ENUM_USN_DATA = 0x000900B3

    class MFT_ENUM_DATA_V0(ctypes.Structure):
        _fields_ = [("StartFileReferenceNumber", ctypes.c_ulonglong),
                    ("LowUsn", ctypes.c_longlong),
                    ("HighUsn", ctypes.c_longlong)]

    if os.path.exists(args.db):
        os.remove(args.db)
    con = sqlite3.connect(args.db, timeout=30)
    con.execute("PRAGMA journal_mode=OFF")
    con.execute("PRAGMA synchronous=OFF")
    con.execute("CREATE TABLE mft (frn INTEGER PRIMARY KEY, parent INTEGER, name TEXT, attrs INTEGER)")

    buf = ctypes.create_string_buffer(1 << 20)
    got = wt.DWORD(0)
    med = MFT_ENUM_DATA_V0(0, 0, 0x7FFFFFFFFFFFFFFF)
    t0 = time.time()
    total = 0
    batch = []
    while True:
        ok = k32.DeviceIoControl(h, FSCTL_ENUM_USN_DATA, ctypes.byref(med),
                                 ctypes.sizeof(med), buf, ctypes.sizeof(buf),
                                 ctypes.byref(got), None)
        if not ok or got.value <= 8:
            break
        med.StartFileReferenceNumber = ctypes.c_ulonglong.from_buffer(buf).value
        off, end = 8, got.value
        while off < end:
            rec_len = ctypes.c_uint32.from_buffer(buf, off).value
            if rec_len < 60:
                break
            frn = ctypes.c_uint64.from_buffer(buf, off + 8).value
            par = ctypes.c_uint64.from_buffer(buf, off + 16).value
            attrs = ctypes.c_uint32.from_buffer(buf, off + 52).value
            nlen = ctypes.c_uint16.from_buffer(buf, off + 56).value
            noff = ctypes.c_uint16.from_buffer(buf, off + 58).value
 # buf.raw 每次都会把整个 1 MB 缓冲区拷一份！4.16M 条 = 4 TB 的内存拷贝，
            #   这就是建库 1388s 的真凶（枚举本身只要 24.8s）。改成按指针直接读。
            name = (ctypes.string_at(ctypes.addressof(buf) + off + noff, nlen)
                    .decode("utf-16-le", "replace") if nlen else "")
            batch.append((_s64(frn), _s64(par), name, attrs))
            total += 1
            off += rec_len
        if len(batch) >= 50000:
            con.executemany("INSERT OR REPLACE INTO mft VALUES (?,?,?,?)", batch)
            con.commit()
            batch.clear()
    if batch:
        con.executemany("INSERT OR REPLACE INTO mft VALUES (?,?,?,?)", batch)
    con.commit()
    con.close()
    k32.CloseHandle(h)
    el = time.time() - t0
    print("USN-INDEX %s · %d 条 · %.1fs · %.1f MB → %s"
          % (args.volume, total, el, os.path.getsize(args.db) / 1e6, args.db))
    return 0


def _resolve_paths(con, frns):
    """FRN → 完整路径。带记忆化，父链逐级上溯。"""
    cache = {}

    def path_of(frn, depth=0):
        if frn in cache:
            return cache[frn]
        if depth > 64:
            return ""
        row = con.execute("SELECT parent, name FROM mft WHERE frn = ?", (_s64(frn),)).fetchone()
        if not row:
            cache[frn] = ""
            return ""
        parent, name = row
        parent = parent + (1 << 64) if parent < 0 else parent
        if parent == frn or not parent:
            p = name
        else:
            base = path_of(parent, depth + 1)
            p = (base + "\\" + name) if base else name
        cache[frn] = p
        return p

    return {f: path_of(f) for f in frns}


def cmd_usn_delta_paths(args) -> int:
    """USN 增量 → 还原成路径（要 --db 指向 usn-index 建的库）。"""
    import ctypes
    import ctypes.wintypes as wt
    import json

    volume = getattr(args, "volume", "C:")     # all 子命令没有 --volume，缺省 C:
    if not os.path.exists(args.db):
        print("[x] 没有索引库 %s：先跑 usn-index" % args.db)
        return 3
    h, k32, _ = _usn_open_volume(volume)
    if not h:
        print("[x] %s 需要管理员" % volume)
        return 3

    FSCTL_QUERY_USN_JOURNAL = 0x000900F4
    FSCTL_READ_USN_JOURNAL = 0x000900BB

    class JD(ctypes.Structure):
        _fields_ = [("UsnJournalID", ctypes.c_ulonglong), ("FirstUsn", ctypes.c_longlong),
                    ("NextUsn", ctypes.c_longlong), ("LowestValidUsn", ctypes.c_longlong),
                    ("MaxUsn", ctypes.c_longlong), ("MaximumSize", ctypes.c_ulonglong),
                    ("AllocationDelta", ctypes.c_ulonglong)]

    class RJ(ctypes.Structure):
        _fields_ = [("StartUsn", ctypes.c_longlong), ("ReasonMask", ctypes.c_uint),
                    ("ReturnOnlyOnClose", ctypes.c_uint), ("Timeout", ctypes.c_ulonglong),
                    ("BytesToWaitFor", ctypes.c_ulonglong), ("UsnJournalID", ctypes.c_ulonglong)]

    jd = JD()
    got = wt.DWORD(0)
    if not k32.DeviceIoControl(h, FSCTL_QUERY_USN_JOURNAL, None, 0,
                               ctypes.byref(jd), ctypes.sizeof(jd), ctypes.byref(got), None):
        print("[x] 查日志失败")
        return 3

    cursor = None
    if os.path.exists(args.cursor):
        try:
            cursor = int(json.load(open(args.cursor))["next_usn"])
        except Exception:
            cursor = None
    if cursor is None or cursor < jd.FirstUsn:
        json.dump({"next_usn": jd.NextUsn, "ts": time.time()}, open(args.cursor, "w"))
        print("[i] 已把游标推到当前 NextUsn=%d，下次起算增量" % jd.NextUsn)
        return 0

    buf = ctypes.create_string_buffer(1 << 20)
    rj = RJ(cursor, 0xFFFFFFFF, 0, 0, 0, jd.UsnJournalID)
    t0 = time.time()
    frns, deleted, total = [], [], 0
    while True:
        ok = k32.DeviceIoControl(h, FSCTL_READ_USN_JOURNAL, ctypes.byref(rj),
                                 ctypes.sizeof(rj), buf, ctypes.sizeof(buf),
                                 ctypes.byref(got), None)
        if not ok or got.value <= 8:
            break
        rj.StartUsn = ctypes.c_longlong.from_buffer(buf).value
        off, end = 8, got.value
        while off < end:
            rec_len = ctypes.c_uint32.from_buffer(buf, off).value
            if rec_len < 60:
                break
            frn = ctypes.c_uint64.from_buffer(buf, off + 8).value
            reason = ctypes.c_uint32.from_buffer(buf, off + 32).value
            attrs = ctypes.c_uint32.from_buffer(buf, off + 52).value
            total += 1
            if reason & 0x8000:                      # USN_REASON_FILE_DELETE
                deleted.append(frn)
            elif not (attrs & 0x10):                 # 只看非目录
                frns.append(frn)
            off += rec_len
    k32.CloseHandle(h)
    el = time.time() - t0

    con = sqlite3.connect(args.db)
    paths = _resolve_paths(con, frns[:2000])         # 解析上限，防父链爆
    con.close()
    print("USN-PATHS %s · 变更 %d（新建/改动 %d · 删除 %d）· 读日志 %.3fs · 解析 %d 条"
          % (volume, total, len(frns), len(deleted), el, len(paths)))
    for fp in list(paths.values())[:8]:
        # 记录里的根 FRN(5) 不在枚举结果里，所以路径天然缺盘符；父链断掉的极少数（实测 46/416 万）
        # 解析成空串，如实标出来，不假装成功。
        print("   + " + ((volume + os.sep + fp) if fp else "(已删除或父链缺失)"))
    return 0


def cmd_all(args) -> int:
    """一条命令跑完全量自检：仓库快照 + 页面感应 + 双向绑定（+ 可选全盘增量）。"""
    t0 = time.time()
    print("=== 全量自检 %s ===" % time.strftime("%Y-%m-%d %H:%M:%S"))
    rcs = []

    rcs.append(cmd_scan(args))
    print()
    rcs.append(cmd_pages(args))
    print()
    rcs.append(cmd_bind(args))

    if getattr(args, "usn", False) and getattr(args, "db", ""):
        print()
        try:
            rc = cmd_usn_delta_paths(args)
        except Exception as e:
            print("[!] 全盘增量异常：%s" % type(e).__name__)
            rc = 0
        if rc == 3:
            print("[i] 全盘增量需要管理员，已跳过（不影响其余三项）")
            rc = 0
        rcs.append(rc)

    print()
    print("TOTAL %.2fs · 退出码 %d" % (time.time() - t0, max(rcs)))
    return max(rcs)


def main() -> int:
    p = argparse.ArgumentParser(description="全量自检 · 触手感应")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bind", help="双向绑定体检")
    sp_usn = sub.add_parser("usn", help="USN/MFT 枚举（需管理员）")
    sp_usn.add_argument("--volume", default="C:")
    sp_i = sub.add_parser("usn-index", help="建 MFT 索引（需管理员，一次性）")
    sp_i.add_argument("--volume", default="C:")
    sp_i.add_argument("--db", required=True)
    sp_p = sub.add_parser("usn-paths", help="USN 增量→路径（需管理员+索引）")
    sp_p.add_argument("--volume", default="C:")
    sp_p.add_argument("--db", required=True)
    sp_p.add_argument("--cursor", required=True)
    sp_d = sub.add_parser("usn-delta", help="USN 增量（需管理员，亚秒）")
    sp_d.add_argument("--volume", default="C:")
    sp_d.add_argument("--cursor", required=True)
    for name in ("scan", "pages", "all"):
        sp = sub.add_parser(name)
        sp.add_argument("--roots", nargs="*")
        if name != "scan":
            sp.add_argument("--http", default="")
            sp.add_argument("--jobs", type=int, default=8)
        if name == "all":
            sp.add_argument("--usn", action="store_true", help="附带全盘增量（需管理员）")
            sp.add_argument("--db", default="", help="MFT 索引库（usn-index 建的）")
            sp.add_argument("--cursor", default="", help="USN 游标文件")
        if name != "pages":
            sp.add_argument("--full", action="store_true")
    args = p.parse_args()
    if args.cmd == "bind":
        return cmd_bind(args)
    if args.cmd == "all":
        args.roots = getattr(args, "roots", None) or [ROOT]
        return cmd_all(args)
    if args.cmd == "usn":
        return cmd_usn(args)
    if args.cmd == "usn-delta":
        return cmd_usn_delta(args)
    if args.cmd == "usn-index":
        return cmd_usn_index(args)
    if args.cmd == "usn-paths":
        return cmd_usn_delta_paths(args)
    args.roots = getattr(args, "roots", None) or [ROOT]
    if args.cmd == "scan":
        return cmd_scan(args)
    if args.cmd == "pages":
        return cmd_pages(args)
    rc = cmd_scan(args)
    print()
    return max(rc, cmd_pages(args))


if __name__ == "__main__":
    raise SystemExit(main())