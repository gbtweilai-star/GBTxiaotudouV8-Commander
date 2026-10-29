#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""大件搬 R2 · **搬运 + 字节级回验 + 才敢删本地**（含 300 MiB 上限的分片）

## 这个件为什么必须存在（第 79 轮实测，四条教训条条真踩过）
1. 🔴 `wrangler r2 object put` 默认写**本地模拟存储**，却照样打印 `Upload complete`
   —— **绿字是真的，事没干**。⇒ 一律带 `--remote`，并**失败关闭**：输出为空也算没搬成。
2. 🔴 **不指定子进程编码** ⇒ 本机默认 GBK ⇒ 读取线程 `UnicodeDecodeError` ⇒ stdout 变空
   ⇒ 上面那道闸**自己失效**。⇒ 编码写死 utf-8 + replace。
3. 🔴 **wrangler 单对象硬上限 300 MiB**（原话：`Wrangler only supports uploading files up to
   300 MiB in size`）⇒ 689 MiB 的 controlnet 直接被拒。⇒ 超限**自动分片**，每片 ≤ 256 MiB。
4. 🔴 `Path.anchor` 对**相对路径**是空串 ⇒ `shutil.disk_usage('')` 抛 `FileNotFoundError`
   ⇒ 上传+回验都成了、却在"删本地"前崩掉（本地没删、日志没写，看着像没搬）。
   ⇒ 一律用**解析后的绝对路径**。

## 口径
- `put` 成功 ≠ 搬成功；**回验（字节数 + sha256 双对）通过**才叫搬成功；
- 分片时**逐片**回验（证明每一字节），**再把整文件拼回来核一次**（证明拼得回来）；
- 全部对得上才删本地，**删前再核一次**本地哈希没变。

用法：
```
python tools/codex-scripts/r2-move.py put     <本地文件> [--key k]
python tools/codex-scripts/r2-move.py verify  <key> --sha256 <期望> [--bytes N]
python tools/codex-scripts/r2-move.py move    <本地文件> [--key k] [--keep]
python tools/codex-scripts/r2-move.py restore <key前缀> --parts N --sha256 <整文件期望> [--bytes N]
python tools/codex-scripts/r2-move.py list-buckets
```
日志（只追加）：`state/r2-move-log.jsonl` · 分片账：`state/r2-multipart.json`
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "state" / "r2-move-log.jsonl"
PARTS = ROOT / "state" / "r2-multipart.json"
# 2026-10-20 实修：桶名原来是**写死的 gbt-bigfiles**，我拿它往"公网动作库 gbt-motion"传了 4 件，
#    它报 ok、sha 双对、还给了 verify 命令 —— 但对象其实进了 gbt-bigfiles，公网 404。
#    「双对」只证明"传到某个桶里且没坏"，不证明"传到了你要的那个桶"。
#    ⇒ 桶名走环境变量，默认仍是老桶（不改变既有调用方行为）。
BUCKET = os.environ.get("GBT_R2_BUCKET", "gbt-bigfiles")
CHUNK = 1 << 20                       # 流式读写块 1 MiB（内存紧，绝不把整文件读进内存）
WRANGLER_LIMIT = 300 * 1024 * 1024    # wrangler 单对象硬上限 300 MiB
PART_BYTES = 256 * 1024 * 1024        # 我们自己分片 ≤ 256 MiB（留余量）


def wrangler_exe():
    base = Path(os.environ.get("APPDATA", "")) / "npm"
    for n in ("wrangler.cmd", "wrangler.exe"):
        p = base / n
        if p.exists():
            return [str(p)]
    w = shutil.which("wrangler")
    return [w] if w else None


WEXE = wrangler_exe()


def run_wrangler(args):
    """文本输出（编码写死 utf-8 —— 见文件头教训 2）。"""
    if not WEXE:
        return 127, "", "wrangler 不在 PATH"
    cp = subprocess.run(WEXE + args, cwd=str(ROOT), stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    return cp.returncode, (cp.stdout or ""), (cp.stderr or "")


def sha256_file(p):
    h = hashlib.sha256()
    n = 0
    with open(p, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
            n += len(b)
    return h.hexdigest(), n


def log(rec):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    rec = dict(rec)
    rec["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def free_of(p):
    """磁盘剩余：**必须用解析后的绝对路径**（相对路径的 `.anchor` 是空串，会抛 FileNotFoundError）。"""
    rp = Path(p).resolve()
    base = rp if rp.is_dir() else rp.parent
    return shutil.disk_usage(str(base)).free


def do_put(local, key):
    rc, out, err = run_wrangler(["r2", "object", "put", "%s/%s" % (BUCKET, key),
                                 "--file", str(local), "--remote"])
    blob = (out or "") + (err or "")
    local_sim = "Resource location: local" in blob
    said_done = ("Upload complete" in blob) or ("Uploaded" in blob)
    over_limit = ("only supports uploading files up to" in blob) or ("300 MiB" in blob)
    ok = bool(rc == 0 and said_done and not local_sim and blob.strip() and not over_limit)
    return {"exit": rc, "有输出": bool(blob.strip()), "说了完成": said_done,
            "其实是本地模拟": local_sim, "超300MiB上限": over_limit, "搬成了": ok,
            "输出摘要": blob.strip().replace("\n", " | ")[:300]}


def pipe_object(key, sink=None):
    """把远端对象**管成字节流**：sink 为 None 时只算 sha256（不落盘）。"""
    cp = subprocess.Popen(WEXE + ["r2", "object", "get", "%s/%s" % (BUCKET, key),
                                  "--remote", "--pipe"],
                          cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    h = hashlib.sha256()
    n = 0
    while True:
        b = cp.stdout.read(CHUNK)
        if not b:
            break
        h.update(b)
        n += len(b)
        if sink is not None:
            sink.write(b)
    cp.stdout.close()
    err = (cp.stderr.read() or b"").decode("utf-8", "replace")
    cp.stderr.close()
    cp.wait()
    return {"字节": n, "sha256": h.hexdigest(), "exit": cp.returncode, "stderr摘要": err.strip()[:200]}


def do_verify(key, want_sha, want_bytes):
    t0 = time.time()
    v = pipe_object(key)
    ok = (bool(v["sha256"] == want_sha if want_sha else True)
          and (want_bytes is None or v["字节"] == want_bytes) and v["exit"] == 0)
    return {**v, "key": key, "耗时s": round(time.time() - t0, 1),
            "字节对得上": (want_bytes is None or v["字节"] == want_bytes),
            "sha256对得上": (not want_sha or v["sha256"] == want_sha),
            "对得上": ok}


def key_of(path, override):
    if override:
        return override
    p = Path(path)
    return "%s/%s" % (p.parent.name, p.name)


def put_and_verify(local, key):
    sha, n = sha256_file(local)
    r = do_put(local, key)
    if not r["搬成了"]:
        return False, {"阶段": "put失败", "本地字节": n, "本地sha256": sha, **r}
    v = do_verify(key, sha, n)
    return bool(v["对得上"]), {"阶段": "回验通过" if v["对得上"] else "回验不过",
                            "本地字节": n, "本地sha256": sha,
                            "远端字节": v["字节"], "远端sha256": v["sha256"],
                            "回验耗时s": v["耗时s"]}


def cmd_put(a):
    local = Path(a.local)
    if not local.exists():
        print(json.dumps({"ok": False, "status": "no_file", "路径": str(local)}, ensure_ascii=False))
        return 4
    key = key_of(local, a.key)
    ok, det = put_and_verify(local, key)
    log({"动作": "put", "本地": str(local), "key": key, **det})
    print(json.dumps({"ok": ok, "status": "put", "key": key, **det,
                      "_下一步": "python tools/codex-scripts/r2-move.py verify %s --sha256 %s --bytes %s"
                                % (key, det.get("本地sha256"), det.get("本地字节"))},
                     ensure_ascii=False, indent=1))
    return 0 if ok else 1


def cmd_verify(a):
    v = do_verify(a.key, a.sha256, a.bytes)
    log({"动作": "verify", "key": a.key, "结论": "对得上" if v["对得上"] else "对不上", **v})
    print(json.dumps({"ok": v["对得上"], "status": "verify",
                      "verdict": ("✅ 字节数 + sha256 双对 ⇒ 云端那份与本地逐字节相同"
                                  if v["对得上"] else "❗对不上（**不许删本地**）"), **v},
                     ensure_ascii=False, indent=1))
    return 0 if v["对得上"] else 5


def cmd_list_buckets(a):
    rc, out, err = run_wrangler(["r2", "bucket", "list"])
    print(json.dumps({"ok": rc == 0, "exit": rc,
                      "桶": [ln.strip() for ln in (out or "").splitlines() if ln.strip()],
                      "stderr": (err or "")[:200]}, ensure_ascii=False, indent=1))
    return 0 if rc == 0 else 1


def move_chunked(local, key, keep):
    """超 300 MiB ⇒ 分片：逐片 put+回验，**再整文件拼回来核一次**，全对才删本地。"""
    size = local.stat().st_size
    nparts = (size + PART_BYTES - 1) // PART_BYTES
    whole_sha, whole_n = sha256_file(local)
    rec = {"文件": str(local), "key": key, "整文件字节": whole_n, "整文件sha256": whole_sha,
           "分片数": nparts, "每片上限MiB": PART_BYTES // (1 << 20), "分片": []}
    tmpd = Path(tempfile.mkdtemp(prefix="gbt-r2part-"))
    try:
        with open(local, "rb") as f:
            for i in range(nparts):
                tp = tmpd / ("part%03d" % i)
                left = min(PART_BYTES, size - i * PART_BYTES)
                with open(tp, "wb") as g:
                    while left > 0:
                        b = f.read(min(CHUNK, left))
                        if not b:
                            break
                        g.write(b)
                        left -= len(b)
                pk = "%s.part%03d" % (key, i)
                ok, det = put_and_verify(tp, pk)
                rec["分片"].append({"片": i, "key": pk, **det})
                if not ok:
                    log({"动作": "move-chunked", "阶段": "第%d片失败" % i, **rec})
                    print(json.dumps({"ok": False, "status": "part_failed", "第几片": i,
                                      "明细": det, "_结论": "**没删本地**"}, ensure_ascii=False, indent=1))
                    return 1
                tp.unlink()
                print("  片 %d/%d ✅ %s（%.1f MB）" % (i + 1, nparts, pk, det["本地字节"] / 1e6))
        # 整文件拼回来核：证明**拼得回来**（不是只看每片）
        rb = tmpd / "rejoin.bin"
        with open(rb, "wb") as g:
            for i in range(nparts):
                pipe_object("%s.part%03d" % (key, i), sink=g)
        rsha, rn = sha256_file(rb)
        rejoin_ok = (rsha == whole_sha and rn == whole_n)
        rec["拼回来核对"] = {"字节": rn, "sha256": rsha, "对得上": rejoin_ok}
        rb.unlink()
        if not rejoin_ok:
            log({"动作": "move-chunked", "阶段": "拼回来对不上", **rec})
            print(json.dumps({"ok": False, "status": "rejoin_failed", "_结论": "**没删本地**",
                              "记录": rec}, ensure_ascii=False, indent=1))
            return 5
        if keep:
            log({"动作": "move-chunked", "阶段": "done-保留本地", **rec})
            print(json.dumps({"ok": True, "status": "moved_kept", "记录": rec},
                             ensure_ascii=False, indent=1))
            return 0
        sha2, n2 = sha256_file(local)
        if (sha2, n2) != (whole_sha, whole_n):
            print(json.dumps({"ok": False, "status": "changed_before_delete",
                              "前": [whole_sha, whole_n], "后": [sha2, n2]}, ensure_ascii=False, indent=1))
            return 6
        f0 = free_of(local)
        local.unlink()
        f1 = free_of(local)
        rec["释放字节"] = f1 - f0
        log({"动作": "move-chunked", "阶段": "done", **rec})
        P = json.loads(PARTS.read_text(encoding="utf-8")) if PARTS.exists() else {}
        P[key] = {k: rec[k] for k in ("整文件字节", "整文件sha256", "分片数", "每片上限MiB")}
        P[key]["恢复命令"] = ("python tools/codex-scripts/r2-move.py restore %s --parts %d "
                          "--sha256 %s --bytes %d" % (key, nparts, whole_sha, whole_n))
        PARTS.parent.mkdir(parents=True, exist_ok=True)
        PARTS.write_text(json.dumps(P, ensure_ascii=False, indent=1), "utf-8")
        print(json.dumps({"ok": True, "status": "moved_deleted_chunked", "记录": rec,
                          "释放字节": f1 - f0, "分片账": str(PARTS),
                          "_口径": "逐片字节级回验 + **整文件拼回来再核一次** ⇒ 才删本地"},
                         ensure_ascii=False, indent=1))
        return 0
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)


def cmd_move(a):
    local = Path(a.local)
    if not local.exists():
        print(json.dumps({"ok": False, "status": "no_file", "路径": str(local)}, ensure_ascii=False))
        return 4
    key = key_of(local, a.key)
    size = local.stat().st_size
    print("本地 %s：%.1f MB ⇒ %s" % (local.name, size / 1e6, key))
    if size > WRANGLER_LIMIT or a.force_chunk:
        print("超 wrangler 单对象上限（300 MiB）⇒ 分片搬（每片 ≤ 256 MiB）")
        return move_chunked(local, key, a.keep)
    ok, det = put_and_verify(local, key)
    if not ok:
        log({"动作": "move", "阶段": det.get("阶段"), "本地": str(local), "key": key, **det})
        print(json.dumps({"ok": False, "status": "put_failed", "key": key, **det},
                         ensure_ascii=False, indent=1))
        return 1
    if a.keep:
        print(json.dumps({"ok": True, "status": "moved_kept", "key": key, **det},
                         ensure_ascii=False, indent=1))
        return 0
    sha2, n2 = sha256_file(local)
    if (sha2, n2) != (det["本地sha256"], det["本地字节"]):
        print(json.dumps({"ok": False, "status": "changed_before_delete",
                          "前": [det["本地sha256"], det["本地字节"]], "后": [sha2, n2]},
                         ensure_ascii=False, indent=1))
        return 6
    f0 = free_of(local)
    local.unlink()
    f1 = free_of(local)
 # 注意键序：`**det` 里也带「阶段」⇒ 必须放在后面，否则会把 done 盖成「回验通过」，
    #    日志就分不出"搬完没有"了（第 79 轮实测的坏读数）。
    log({"动作": "move", "本地": str(local), "key": key,
         "字节": n2, "sha256": sha2, "释放字节": f1 - f0, **det, "阶段": "done"})
    print(json.dumps({"ok": True, "status": "moved_deleted", "key": key, "字节": n2, "sha256": sha2,
                      "释放字节": f1 - f0, "回验": det,
                      "_口径": "put(--remote) → 云端对象管进 sha256 回验 → 双对才删；删前又核一次本地哈希没变。"},
                     ensure_ascii=False, indent=1))
    return 0


def cmd_restore(a):
    """把分片取回来拼成一个文件，并核对**整文件** sha256（搬回来 / 验证"拼得回来"）。"""
    out = Path(a.keep_out) if a.keep_out else Path(tempfile.gettempdir()) / ("gbt-restore-" + os.urandom(4).hex())
    h = hashlib.sha256()
    n = 0
    with open(out, "wb") as g:
        for i in range(a.parts):
            cp = subprocess.Popen(WEXE + ["r2", "object", "get", "%s/%s.part%03d" % (BUCKET, a.key, i),
                                          "--remote", "--pipe"],
                                  cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            while True:
                b = cp.stdout.read(CHUNK)
                if not b:
                    break
                h.update(b)
                n += len(b)
                g.write(b)
            cp.stdout.close()
            cp.stderr.close()
            cp.wait()
    got = h.hexdigest()
    ok = (not a.sha256 or got == a.sha256) and (a.bytes is None or n == a.bytes)
    log({"动作": "restore", "key": a.key, "分片数": a.parts, "字节": n, "sha256": got,
         "结论": "对得上" if ok else "对不上"})
    print(json.dumps({"ok": ok, "status": "restore",
                      "verdict": ("✅ 拼回来的整文件与期望逐字节相同" if ok else "❗拼回来对不上"),
                      "分片数": a.parts, "字节": n, "sha256": got,
                      "落点": str(out) if a.keep_out else "(临时文件已删)",
                      "_口径": "逐片取字节 → 顺序拼接 → 对**整文件** sha256；这是「每片都对」之外的第二道证明。"},
                     ensure_ascii=False, indent=1))
    if not a.keep_out:
        out.unlink(missing_ok=True)
    return 0 if ok else 5


def cmd_download(a):
    """把云端对象（可分片）**取回落到指定路径**，并核对期望 sha256/字节数。

    与 `restore` 的区别：`restore` 只证明"拼得回来"（默认用完就删）；`download` 是**真恢复** ——
    落到你要的那个路径（比如模型的原位），落完再核一次哈希，**对不上就把坏副本删掉**，不留半成品。
    """
    out = Path(a.to) if a.to else (ROOT / "restore-download.bin")
    out.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    n = 0
    with open(out, "wb") as g:
        keys = (["%s.part%03d" % (a.key, i) for i in range(a.parts)] if a.parts else [a.key])
        for k in keys:
            cp = subprocess.Popen(WEXE + ["r2", "object", "get", "%s/%s" % (BUCKET, k),
                                          "--remote", "--pipe"],
                                  cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            while True:
                b = cp.stdout.read(CHUNK)
                if not b:
                    break
                h.update(b)
                n += len(b)
                g.write(b)
            cp.stdout.close()
            cp.stderr.close()
            cp.wait()
    got = h.hexdigest()
    ok = (not a.sha256 or got == a.sha256) and (a.bytes is None or n == a.bytes)
    log({"动作": "download", "key": a.key, "分片数": a.parts or 1, "落点": str(out),
         "字节": n, "sha256": got, "结论": "对得上" if ok else "对不上"})
    print(json.dumps({"ok": ok, "status": "download", "落点": str(out), "字节": n, "sha256": got,
                      "verdict": ("✅ 取回来的文件与期望逐字节相同" if ok else "❗取回来对不上（**别用它**）"),
                      "分片数": a.parts or 1}, ensure_ascii=False, indent=1))
    if not ok:
        out.unlink(missing_ok=True)
        print("（对不上 ⇒ 已把这个坏副本删掉，不留半成品）")
    return 0 if ok else 5


def main():
    ap = argparse.ArgumentParser(description="大件搬 R2（字节级回验，对不上不删；>300MiB 自动分片）")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("put")
    p.add_argument("local")
    p.add_argument("--key", default="")
    p.set_defaults(fn=cmd_put)
    p = sub.add_parser("download")
    p.add_argument("key")
    p.add_argument("--to", default="")
    p.add_argument("--parts", type=int, default=0)
    p.add_argument("--sha256", default="")
    p.add_argument("--bytes", type=int, default=None)
    p.set_defaults(fn=cmd_download)
    p = sub.add_parser("verify")
    p.add_argument("key")
    p.add_argument("--sha256", default="")
    p.add_argument("--bytes", type=int, default=None)
    p.set_defaults(fn=cmd_verify)
    p = sub.add_parser("move")
    p.add_argument("local")
    p.add_argument("--key", default="")
    p.add_argument("--keep", action="store_true")
    p.add_argument("--force-chunk", action="store_true")
    p.set_defaults(fn=cmd_move)
    p = sub.add_parser("restore")
    p.add_argument("key")
    p.add_argument("--parts", type=int, required=True)
    p.add_argument("--sha256", default="")
    p.add_argument("--bytes", type=int, default=None)
    p.add_argument("--keep-out", default="")
    p.set_defaults(fn=cmd_restore)
    p = sub.add_parser("list-buckets")
    p.set_defaults(fn=cmd_list_buckets)
    a = ap.parse_args()
    if not getattr(a, "fn", None):
        ap.print_help()
        return 2
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
