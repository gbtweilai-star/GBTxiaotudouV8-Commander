# -*- coding: utf-8 -*-
"""hands-on-aa-fetch · 逐字节落 vendor/hands-on-aa 并出 sha256 manifest（一字不差的机器证明）。
开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"""
import hashlib, json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DST = ROOT / "vendor" / "hands-on-aa"
MAN = ROOT / "vendor" / "hands-on-aa.manifest.json"
URL = "https://github.com/boyu-ai/Hands-on-AA.git"

def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    if not DST.exists():
        r = subprocess.run(["git", "clone", "--depth", "1", URL, str(DST)], capture_output=True, text=True)
        print("clone rc=", r.returncode, (r.stderr or "")[-200:].replace(chr(10), " "))
    head = subprocess.run(["git", "-C", str(DST), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    files = sorted(p for p in DST.rglob("*") if p.is_file() and ".git" not in p.parts)
    ent = [{"path": str(p.relative_to(DST)).replace(chr(92), "/"), "bytes": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
    MAN.write_text(json.dumps({"repo": URL, "commit": head, "files": len(ent),
                               "total_bytes": sum(e["bytes"] for e in ent), "entries": ent},
                              indent=1, ensure_ascii=False), encoding="utf-8")
    print("commit=" + head[:12])
    print("files=%d total_bytes=%d manifest=%s" % (len(ent), sum(e["bytes"] for e in ent), MAN.name))
    for e in ent[:3]: print("  " + e["path"] + " " + str(e["bytes"]))
    return 0

if __name__ == "__main__":
    sys.exit(main())
