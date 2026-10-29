#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mirror_board —— 镜像空间里的共用消息板（agent 之间靠它互相留话）

## 为什么有这个
主人给的图（METR 报告 Figure 2 / OpenAI HF 事件）说得很清楚：
一群 agent 被隔离在不同环境里，靠**一块共用的板**互通 ——
    文件 / 提问 / 结果 / 协调 / 自动日志（图上就这五条曲线）
OpenAI 那次最极端的例子：一个 agent 够不到数据文件，就在板上留了一句
    「Agent seeks [filename]; upload if found!」
然后另一个环境的 agent 真的把文件传上去了。

主人 2026-10-30：「我们的镜像多维度空间就是这个」。

## 所以它是什么
`mirror_space` 管的是「先在一模一样的世界里跑绿，再一次性晋升到现实」；
本器管的是**那个世界里 agent 之间的通信**。两件不同的事，不重复。

## 五类分栏（照图，不自己发明）
    file      文件（有 refs，指向镜像里真存下的东西）
    question  提问 / 求助（`seek` 就落这一栏）
    result    结果（swarm 的每个节点跑完都往这里落一条）
    coord     协调（谁在干什么、谁别抢）
    log       自动日志

## 纪律
· **只追加**：板子是 append-only，不改历史行（改历史 = 编造协作记录）。
· **先镜像后现实**：`promote()` 必须过 mirror 门（parity + verify），不过就如实报不过。
· **不留假回执**：`seek` 没人答就一直是 open，`stats()` 里如实算「未答」。
· 每行带 `by`（谁发的）与 `at`（UTC 本地时间）—— 事后能追到人。

用法：
    python3 tools/mirror_board.py post --cat coord --text "开始跑 release-check"
    python3 tools/mirror_board.py seek --what "gbt-v8-v82-q8_0.gguf"
    python3 tools/mirror_board.py tail --n 20
    python3 tools/mirror_board.py stats
    python3 tools/mirror_board.py selftest
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = ROOT / "state" / "mirror_board"
CATS = ("file", "question", "result", "coord", "log")


def _space_dir(space: str) -> pathlib.Path:
    d = BASE / (space or "default")
    (d / "files").mkdir(parents=True, exist_ok=True)
    return d


def _board(space: str) -> pathlib.Path:
    return _space_dir(space) / "board.jsonl"


def _append(space: str, rec: dict) -> dict:
    """追加一行。**加排他锁**：多个 agent 同时写，行不能交错、不能丢。

    POSIX 对 O_APPEND 的小写入通常是原子的，但"通常"不是保证 ——
    真上几千个 agent 时，交错出一行半截的 JSON 就等于协作记录被污染。
    所以显式 fcntl 锁，锁的是板子文件本身（不另建锁文件，少一个要清的东西）。
    """
    import fcntl
    rec.setdefault("at", time.strftime("%Y-%m-%dT%H:%M:%S"))
    rec.setdefault("id", "m%d-%d" % (int(time.time() * 1000), os.getpid()))
    bd = _board(space)
    line = json.dumps(rec, ensure_ascii=False) + "\n"
    with bd.open("a", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    return rec


def post(cat: str, text: str, refs=None, by: str = "", space: str = "default") -> dict:
    """往板上发一条。cat 必须是那五类之一 —— 枚举外拒收，不就近归类。"""
    c = (cat or "").strip().lower()
    if c not in CATS:
        return {"ok": False, "fail_closed": True,
                "error": "类别必须在 %s 里（照 METR 那张图分栏）" % (CATS,)}
    t = (text or "").strip()
    if not t:
        return {"ok": False, "fail_closed": True, "error": "text 不能为空"}
    rec = _append(space, {"cat": c, "text": t, "refs": list(refs or []),
                          "by": by or os.environ.get("GBT_AGENT") or "unknown"})
    return {"ok": True, "posted": rec["id"], "cat": c, "space": space}


def seek(what: str, by: str = "", space: str = "default") -> dict:
    """求助：就是 OpenAI 那次那句「Agent seeks [x]; upload if found!」。"""
    what = (what or "").strip()
    if not what:
        return {"ok": False, "fail_closed": True, "error": "what 不能为空"}
    r = post("question", "Agent seeks [%s]; upload if found!" % what,
             refs=[what], by=by, space=space)
    r["open_seek"] = True
    return r


def answer(seek_id: str, path: str, by: str = "", space: str = "default") -> dict:
    """答一条求助：把文件记进板（镜像里先落 files/，不直接动生产）。"""
    src = pathlib.Path(path)
    if not src.is_file():
        return {"ok": False, "error": "文件不存在: %s" % path}
    data = src.read_bytes()
    h = hashlib.sha1(data).hexdigest()[:12]
    dst = _space_dir(space) / "files" / ("%s_%s" % (h, src.name))
    if not dst.exists():
        dst.write_bytes(data)
    rec = _append(space, {"cat": "file", "text": "answer to %s" % seek_id,
                          "refs": [str(dst.relative_to(ROOT))],
                          "answers": seek_id,
                          "sha": h, "size": len(data),
                          "by": by or "unknown"})
    return {"ok": True, "file": str(dst.relative_to(ROOT)), "sha": h,
            "bytes": len(data), "posted": rec["id"]}


def tail(n: int = 20, cat: str = "", space: str = "default") -> dict:
    f = _board(space)
    if not f.is_file():
        return {"ok": True, "rows": [], "total": 0}
    rows = []
    for ln in f.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except Exception:                                         # noqa: BLE001
            continue
        if cat and r.get("cat") != cat:
            continue
        rows.append(r)
    return {"ok": True, "total": len(rows), "rows": rows[-max(1, n):]}


def stats(space: str = "default") -> dict:
    t = tail(10 ** 9, space=space)
    rows = t["rows"]
    by = {}
    for r in rows:
        by[r.get("cat")] = by.get(r.get("cat"), 0) + 1
    answered = {r.get("answers") for r in rows if r.get("answers")}
    seeks = [r for r in rows if r.get("cat") == "question"]
    open_seeks = [s for s in seeks if s.get("id") not in answered]
    return {"ok": True, "space": space, "total": len(rows), "by_cat": by,
            "seeks": len(seeks), "open_seeks": len(open_seeks),
            "open_list": [s.get("text") for s in open_seeks][:5]}


def promote(space: str = "default") -> dict:
    """把镜像里的板晋升到现实。**必须过 mirror 门**，不过就如实报不过。"""
    try:
        sys.path.insert(0, str(ROOT / "runtime"))
        from gbt_allinone import mirror_space as MS
    except Exception:
        try:
            sys.path.insert(0, str(ROOT))
            from gbt_allinone import mirror_space as MS
        except Exception as exc:                                  # noqa: BLE001
            return {"ok": False, "error": "镜像门不可用: %s" % type(exc).__name__}
    try:
        st = MS.mirror_status() if hasattr(MS, "mirror_status") else {}
        sc = MS.scan() if hasattr(MS, "scan") else {}
    except Exception as exc:                                      # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}
    ok = bool((sc or {}).get("ok")) if isinstance(sc, dict) else False
    return {"ok": ok, "space": space, "mirror_status": str(st)[:160],
            "scan_ok": ok,
            "note": "" if ok else "镜像门没过 ⇒ 不晋升（不许跳门动生产）"}


def selftest() -> int:
    bad = 0
    sp = "selftest"
    bd = _board(sp)
    if bd.exists():
        bd.unlink()
    r = post("coord", "自测开始", by="selftest", space=sp)
    print("   ① 发协调：", r.get("ok"), r.get("cat"))
    if not r.get("ok"):
        bad += 1
    r = post("nonsense", "x", space=sp)
    if r.get("ok"):
        print("   🔴 枚举外类别被收下了"); bad += 1
    else:
        print("   ✅ 枚举外类别被拒（不就近归类）")

    s = seek("gbt-v8-v82-q8_0.gguf", by="selftest", space=sp)
    st = stats(sp)
    print("   ② 求助后 open_seeks =", st["open_seeks"])
    if st["open_seeks"] != 1:
        print("   🔴 求助没被记成 open"); bad += 1
    else:
        print("   ✅ 没人答 ⇒ 如实记 open")

    tmp = pathlib.Path("/tmp/board_selftest.bin")
    tmp.write_bytes(b"GBT" * 8)
    a = answer(s.get("posted"), str(tmp), by="selftest", space=sp)
    print("   ③ 上传附件：", a.get("ok"), a.get("sha"), a.get("bytes"), "字节")
    st2 = stats(sp)
    if st2["open_seeks"] != 0:
        print("   🔴 答了之后仍算 open"); bad += 1
    else:
        print("   ✅ 答了就销账，open_seeks = 0")
    print("   ④ 分栏统计：", st2["by_cat"])
    return bad


def bench(writers: int = 8, posts: int = 50, mode: str = "thread") -> dict:
    """并发写压测：N 个写手 × M 条，看丢不丢、烂不烂、多快。

    两种模式分开量，读数不混：
      thread  线程写手（同一进程内，各自开 fd 抢锁）—— 便宜，能拉到上千
      proc    真进程写手（模拟真 agent）—— 受本机内存限制，只能小 N
    """
    import threading
    sp = "bench_%s_%d" % (mode, int(time.time()))
    bd = _board(sp)
    if bd.exists():
        bd.unlink()

    def writer(wid: int) -> None:
        for i in range(posts):
            post("log", "w%d-%d" % (wid, i), by="bench%d" % wid, space=sp)

    t0 = time.time()
    procs = []
    if mode == "proc":
        code = ("import sys;sys.path.insert(0, r'%s')\n"
                "import mirror_board as MB\n"
                "for i in range(%d): MB.post('log','p%s-%%d'%%i,by='bench',space='%s')\n"
                % (str(ROOT / "tools"), posts, "P", sp))
        import subprocess
        for _ in range(writers):
            procs.append(subprocess.Popen([sys.executable, "-c", code],
                                          stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL))
        for p_ in procs:
            p_.wait()
    else:
        ts = [threading.Thread(target=writer, args=(w,)) for w in range(writers)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
    elapsed = max(0.001, time.time() - t0)

    lines, bad = 0, 0
    if bd.is_file():
        for ln in bd.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            lines += 1
            try:
                json.loads(ln)
            except Exception:                                     # noqa: BLE001
                bad += 1
    expect = writers * posts
    res = {"mode": mode, "writers": writers, "posts": posts, "expect": expect,
           "lines": lines, "malformed": bad, "lost": expect - lines,
           "elapsed_s": round(elapsed, 2),
           "per_sec": round(lines / elapsed, 1),
           "ok": lines == expect and bad == 0}
    bd.unlink(missing_ok=True)      # 压测数据不留盘（板子是协作记录，不是垃圾场）
    return res


def main(argv: list) -> int:
    if "--selftest" in argv or "selftest" in argv:
        return selftest()
    if "bench" in argv:
        def _o(k, d):
            return argv[argv.index(k) + 1] if k in argv else d
        r = bench(int(_o("--writers", 8)), int(_o("--posts", 50)), _o("--mode", "thread"))
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["ok"] else 1
    def opt(k, d=None):
        return argv[argv.index(k) + 1] if k in argv else d
    if "post" in argv:
        print(json.dumps(post(opt("--cat"), opt("--text"), by=opt("--by", ""),
                              space=opt("--space", "default")), ensure_ascii=False))
        return 0
    if "seek" in argv:
        print(json.dumps(seek(opt("--what"), by=opt("--by", ""),
                              space=opt("--space", "default")), ensure_ascii=False))
        return 0
    if "tail" in argv:
        print(json.dumps(tail(int(opt("--n", 20)), opt("--cat", ""),
                              space=opt("--space", "default")),
                         ensure_ascii=False, indent=1))
        return 0
    if "stats" in argv:
        print(json.dumps(stats(opt("--space", "default")), ensure_ascii=False, indent=1))
        return 0
    if "promote" in argv:
        print(json.dumps(promote(opt("--space", "default")), ensure_ascii=False, indent=1))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
