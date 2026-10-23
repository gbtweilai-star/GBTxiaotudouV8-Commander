# -*- coding: utf-8 -*-
"""hands-on-aa-check · 逐字节判据 + manifest 真源 + notebook 索引（只索引不转述）。
用法：--build（重生成 manifest+索引）/ --check（逐文件比对）/ --selftest
开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"""
import argparse, hashlib, json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CORPUS = ROOT / "vendor" / "hands-on-aa"
MANIFEST = ROOT / "vendor" / "hands-on-aa.manifest.json"
INDEX = ROOT / "vendor" / "hands-on-aa.index.md"

def _entries():
    out = []
    for p in sorted(CORPUS.rglob("*")):
        if p.is_file() and ".git" not in p.parts:
            out.append((str(p.relative_to(CORPUS)).replace(chr(92), "/"), p))
    return out

def _sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def _cmp(want, have):
    missing = sorted(k for k in want if k not in have)
    extra = sorted(k for k in have if k not in want)
    changed = sorted(k for k in want if k in have and have[k] != want[k])
    return missing, extra, changed

def build() -> int:
    es = _entries()
    rows = [{"path": rel, "bytes": p.stat().st_size, "sha256": _sha(p)} for rel, p in es]
    head = subprocess.run(["git", "-C", str(CORPUS), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    MANIFEST.write_text(json.dumps({"corpus": "vendor/hands-on-aa", "commit": head,
        "files": len(rows), "total_bytes": sum(r["bytes"] for r in rows), "entries": rows},
        indent=1, ensure_ascii=False), encoding="utf-8")
    nb = [(rel, p) for rel, p in es if rel.endswith(".ipynb")]
    L = ["# Hands-on-AA 语料索引（**只索引，不转述正文**；要内容就现读原文）", "",
         "- 语料根：vendor/hands-on-aa/", "- commit：" + head[:12],
         "- 文件 %d · 字节 %d · notebook %d" % (len(rows), sum(r["bytes"] for r in rows), len(nb)), ""]
    for rel, p in nb:
        try:
            j = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            cells = j.get("cells", [])
            heads = []
            for c in cells:
                if c.get("cell_type") != "markdown": continue
                for ln in "".join(c.get("source", [])).splitlines():
                    if ln.strip().startswith("#"): heads.append(ln.strip()[:70])
                if len(heads) >= 4: break
            L.append("- `%s` · cells=%d · %s" % (rel, len(cells), " | ".join(heads[:4]) or "(无标题)"))
        except Exception as e:
            L.append("- `%s`（解析失败：%s）" % (rel, str(e)[:40]))
    INDEX.write_text(chr(10).join(L) + chr(10), encoding="utf-8")
    print("manifest=%d 条 · notebook=%d · bytes=%d" % (len(rows), len(nb), sum(r["bytes"] for r in rows)))
    print("commit=" + head[:12])
    return 0

def check() -> int:
    if not MANIFEST.is_file():
        print("  FAIL C1 未读到 manifest（不许当空语料绿）"); return 1
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    want = {e["path"]: e["sha256"] for e in m["entries"]}
    have = {rel: _sha(p) for rel, p in _entries()}
    missing, extra, changed = _cmp(want, have)
    ok = not (missing or extra or changed)
    print("  C1 manifest %d 条（commit %s / bytes %s）" % (len(want), str(m.get("commit"))[:12], m.get("total_bytes")))
    print("  C2 逐字节一致 %d/%d" % (len(want) - len(changed), len(want)))
    print("  C3 缺件 %s" % (missing[:5] or "无"))
    print("  C4 多件 %s" % (extra[:5] or "无"))
    print("  C5 改字节 %s" % (changed[:5] or "无"))
    print("判据 PASS %d · FAIL %d" % (1 if ok else 0, 0 if ok else 1))
    return 0 if ok else 1

def selftest() -> int:
    ck = []
    def c(n, ok, d=""):
        ck.append(bool(ok)); print(("OK  " if ok else "BAD ") + n + (" — " + str(d)[:50] if d else ""))
    c("正控·全一致 ⇒ 无红", _cmp({"a": "x"}, {"a": "x"}) == ([], [], []))
    c("负控·改一字节 ⇒ changed", _cmp({"a": "x"}, {"a": "y"})[2] == ["a"])
    c("负控·少件 ⇒ missing", _cmp({"a": "x", "b": "y"}, {"a": "x"})[0] == ["b"])
    c("负控·多件 ⇒ extra", _cmp({"a": "x"}, {"a": "x", "b": "y"})[1] == ["b"])
    bad = len([x for x in ck if not x])
    print("\nhands-on-aa-check selftest: %d/%d" % (len(ck) - bad, len(ck)))
    return 1 if bad else 0

def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true"); ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest: return selftest()
    if a.check: return check()
    return build()

if __name__ == "__main__":
    sys.exit(main())
