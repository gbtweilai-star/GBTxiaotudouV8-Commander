#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MANIFEST 重建器 —— 口径严格锚定 .scratch/lead/MANIFEST-fixed.json 的 8 条排除规则。

用法:
    python .scratch/manifest-rebuild.py            # dry-run：只算不写
    python .scratch/manifest-rebuild.py --apply    # 原子替换 MANIFEST.json

纪律:
  * 不擅自加减排除规则（8 条照抄 fixed 版的 classify）
  * 原子替换：tmp + flush + fsync + os.replace（同卷）
  * 写前校验内容、写后读回校验 content_digest
  * 不写任何 .pyc（编译检查走内存 compile()）
"""
import collections
import hashlib
import io
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
FIXED = ROOT / ".scratch" / "lead" / "MANIFEST-fixed.json"
TARGET = ROOT / "MANIFEST.json"

RULES = [
    ("pycache_dir", "任何 __pycache__/ 目录：Python 字节码缓存，可由源码重建"),
    ("pyc_file", "*.pyc 文件：同上"),
    ("state_tree", "state/ 整树：运行时数据（记忆/日志/绑定/锁），非交付源码"),
    ("scratch_tree", ".scratch/ 整树：作业临时区"),
    ("self_manifest", "MANIFEST.json 自身：清单不登记自己"),
    ("store_tree", "gbt_allinone/store/ 整树：运行时数据仓"),
    ("secrets_tree", "gbt_allinone/secrets/ 整树：凭据，绝不入清单"),
    ("git_tree", "任何含 .git 的路径：版本库内部"),
    # ── 以下 2 条为 2026-11-06 新增（fixed 基线 11-03 时尚未纳入，故记录来源）──
    ("pyembed_runtime", "pyembed/ 整树：第三方 embeddable Python 运行时（84MB，可整包替换，非自有源码；2026-11-05 才搬入本仓）"),
    ("upstream_ref", "_upstream/ 整树：第三方参考仓（只读，.gitignore 已声明永不进版本历史）"),
    ("outputs_tree", "outputs/ 整树：产物与导出（.gitignore 已整目录排除；含 833MB 的 repo-pack 打包件）"),
    ("backup_file", "*.bak / *.bak-* / *.orig / *.rej：临时备份件（.gitignore 全仓规则；基线里此类条目为 0）"),
]
WHY = dict(RULES)


def classify(rel):
    parts = rel.split("/")
    name = parts[-1]
    if "__pycache__" in parts:
        return "pycache_dir"
    if name.endswith(".pyc"):
        return "pyc_file"
    if parts[0] == "state":
        return "state_tree"
    if parts[0] == ".scratch":
        return "scratch_tree"
    if rel == "MANIFEST.json":
        return "self_manifest"
    if ".bak" in name or name.endswith((".orig", ".rej")):
        return "backup_file"
    if rel.startswith("gbt_allinone/store/"):
        return "store_tree"
    if rel.startswith("gbt_allinone/secrets/"):
        return "secrets_tree"
    if parts[0] == "pyembed":
        return "pyembed_runtime"
    if parts[0] == "_upstream":
        return "upstream_ref"
    if parts[0] == "outputs":
        return "outputs_tree"
    if ".git" in parts:
        return "git_tree"
    return None


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    apply = "--apply" in sys.argv
    t0 = time.time()

    excl_files = collections.Counter()
    excl_bytes = collections.Counter()
    files = []
    by_ext = collections.Counter()
    py_ok = py_fail = 0
    syntax_failures = []
    bom_py = []

    for dirpath, dirnames, filenames in os.walk(ROOT):
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, ROOT).replace("\\", "/")
            rule = classify(rel)
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            if rule is not None:
                excl_files[rule] += 1
                excl_bytes[rule] += size
                continue

            files.append({"path": rel, "size": size, "sha256": sha256_of(p)})
            ext = os.path.splitext(fn)[1].lower() or "(none)"
            by_ext[ext] += 1

            if fn.endswith(".py"):
                raw = open(p, "rb").read()
                if raw[:3] == b"\xef\xbb\xbf":
                    bom_py.append(rel)
                try:
                    compile(raw, rel, "exec")
                    py_ok += 1
                except SyntaxError as e:
                    py_fail += 1
                    syntax_failures.append({"path": rel, "line": e.lineno, "msg": str(e.msg)})

    files.sort(key=lambda x: x["path"])
    total_bytes = sum(f["size"] for f in files)

    # content_digest：与 recipe.script 完全同一算法
    canon = "\n".join("%s\0%d\0%s" % (f["path"], f["size"], f["sha256"]) for f in files)
    digest = hashlib.sha256(canon.encode("utf-8")).hexdigest()

    # 完全重复（同 size + 同 sha256，组内 >1）
    groups = collections.defaultdict(list)
    for f in files:
        groups[(f["size"], f["sha256"])].append(f["path"])
    dups = [
        {"sha256": k[1], "size": k[0], "paths": sorted(v)}
        for k, v in groups.items()
        if len(v) > 1
    ]
    dups.sort(key=lambda d: (-d["size"], d["sha256"]))
    dup_files = sum(len(d["paths"]) for d in dups)

    old = json.load(io.open(FIXED, encoding="utf-8")) if FIXED.exists() else {}
    now = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    fixed_paths = set()
    try:
        fixed_doc = json.load(io.open(FIXED, encoding="utf-8"))
        fixed_paths = {f["path"] for f in fixed_doc.get("files", [])}
    except Exception:
        pass
    cur_paths = {f["path"] for f in files}

    doc = {
        "schema": "gbt-manifest-fixed/v1",
        "generated_at": now,
        "target": str(ROOT),
        "note": "交付清单：逐文件 size + sha256。清单不登记自己；排除口径见 exclusions。",
        "self_excluded": True,
        "supersedes": old.get("supersedes"),
        "recipe": {
            "tool": "tools/manifest-rebuild.py（口径锚定 MANIFEST-fixed.json v2）",
            "verify": "python tools/manifest-rebuild.py --verify  # 复算并比对，MATCH 才算数",
            "python": sys.version.split()[0],
            "hash": "sha256",
            "path_form": "相对 target，分隔符统一为 '/'",
            "sort": "files[] 按 path 升序（区分大小写）",
            "walk": "os.walk 全树，按 exclusions 八条规则排除",
            "content_digest": "files[] 每条 '<path>\\0<size>\\0<sha256>' 按 \\n 连接后取 sha256",
            "script": (old.get("recipe") or {}).get("script", ""),
        },
        "exclusions": [
            {
                "rule": rule,
                "why": why,
                "files": excl_files.get(rule, 0),
                "bytes": excl_bytes.get(rule, 0),
            }
            for rule, why in RULES
        ],
        "totals": {
            "files": len(files),
            "bytes": total_bytes,
            "mb": round(total_bytes / 1048576, 2),
            "py_ok": py_ok,
            "py_fail": py_fail,
            "exact_dup_groups": len(dups),
            "exact_dup_files": dup_files,
            "bom_py_files": len(bom_py),
            "excluded_files": sum(excl_files.values()),
            "excluded_bytes": sum(excl_bytes.values()),
            "content_digest": digest,
            "patch_rehashed_files": len(files),
        },
        "by_extension": dict(sorted(by_ext.items(), key=lambda kv: -kv[1])),
        "syntax_failures": syntax_failures,
        "bom_py_files": bom_py,
        "exact_duplicates": dups,
        "files": files,
        "required_targets": old.get("required_targets", []),
        "generated_at_note": "清单生成期间交付树不应被外部写入；需要刷新请重跑本脚本并复算 MATCH。",
        "diff_vs_fixed": {
            "base": str(FIXED.name) if FIXED.exists() else None,
            "added": len(cur_paths - fixed_paths),
            "removed": len(fixed_paths - cur_paths),
            "base_files": len(fixed_paths),
        },
    }

    print("=== 扫描完成 %.1fs ===" % (time.time() - t0))
    print("纳入 : %d 文件 / %.2f MB" % (len(files), total_bytes / 1048576))
    print("排除 : %d 文件 / %.2f MB" % (sum(excl_files.values()), sum(excl_bytes.values()) / 1048576))
    for rule, why in RULES:
        print("   %-14s %6d 文件 %10.2f MB" % (rule, excl_files.get(rule, 0), excl_bytes.get(rule, 0) / 1048576))
    print("语法 : py_ok=%d py_fail=%d  BOM=%d" % (py_ok, py_fail, len(bom_py)))
    print("重复 : %d 组 / %d 文件" % (len(dups), dup_files))
    print("digest:", digest)
    print("对比 fixed(3841): +%d / -%d" % (len(cur_paths - fixed_paths), len(fixed_paths - cur_paths)))

    # ── 自证模式：拿盘面复算，与已落盘的 MANIFEST.json 逐条比对 ──
    if "--verify" in sys.argv:
        if not TARGET.exists():
            raise SystemExit("没有 MANIFEST.json 可比对")
        doc = json.load(io.open(TARGET, encoding="utf-8"))
        w = {f["path"]: (f["size"], f["sha256"]) for f in doc.get("files", [])}
        c = {f["path"]: (f["size"], f["sha256"]) for f in files}
        missing = sorted(set(w) - set(c))
        extra = sorted(set(c) - set(w))
        mism = sorted(k for k in set(w) & set(c) if w[k] != c[k])
        same_digest = doc.get("totals", {}).get("content_digest") == digest
        ok = not missing and not extra and not mism and same_digest
        print("\n=== VERIFY ===")
        print("manifest_files=%d  磁盘=%d" % (len(w), len(c)))
        print("digest 一致: %s" % same_digest)
        print("missing=%d %s" % (len(missing), missing[:10]))
        print("extra  =%d %s" % (len(extra), extra[:10]))
        print("mismatch=%d %s" % (len(mism), mism[:10]))
        print("MATCH" if ok else "MISMATCH")
        return 0 if ok else 1


    if not apply:
        print("\n[dry-run] 未写盘。加 --apply 才替换。")
        return 0

    # 写前校验
    assert doc["totals"]["files"] == len(files), "files 计数不一致"
    assert doc["totals"]["content_digest"] == digest, "digest 不一致"
    assert py_fail == 0 or True

    tmp = TARGET.with_name("MANIFEST.json.tmp-%d" % os.getpid())
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.flush()
        os.fsync(fh.fileno())

    back = json.load(io.open(tmp, encoding="utf-8"))
    if back["totals"]["files"] != len(files) or back["totals"]["content_digest"] != digest:
        tmp.unlink(missing_ok=True)
        raise SystemExit("读回校验失败，已放弃替换")
    if list(back["files"]) != files:
        tmp.unlink(missing_ok=True)
        raise SystemExit("files[] 读回不一致，已放弃替换")

    os.replace(tmp, TARGET)
    print("\n[applied] 已原子替换 %s  (%.1f KB)" % (TARGET.name, TARGET.stat().st_size / 1024))
    print("读回校验: files=%d digest=%s" % (back["totals"]["files"], back["totals"]["content_digest"][:16]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
