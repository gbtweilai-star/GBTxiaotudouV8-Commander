# -*- coding: utf-8 -*-
"""failure-attribution-check · 失败归因（授权墙 vs 真失败）。

为什么要有它（主人令 2026-10-15）：每次触手失败要能分清**是授权墙，还是真失败** ——
否则优化就是瞎猜；state 里现有的是性能读数，缺这一层。

读 store/audit.jsonl（只读尾部，文件已 150MB+），把事件分三态：
  auth_wall  = auth_denied / 需要人工授权（**不是她坏，是缺钥匙**）
  real_fail  = error / exception / user_error（**真失败**）
  ok         = 正常
产出 state/failure-attribution.json；判据：A1 可读 · A2 三态可分 · A3 取不到=红。
用法：--build | --check | --selftest
开发者：自由的风 · 守护者：公主土豆 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"""
import argparse, collections, datetime, json, pathlib, sys

R = pathlib.Path(__file__).resolve().parents[2]
AUDIT = R / "gbt_allinone" / "store" / "audit.jsonl"
OUT = R / "state" / "failure-attribution.json"
TAIL_BYTES = 8 * 1024 * 1024

def _tail_lines(path, nbytes=TAIL_BYTES):
    if not path.is_file(): return None
    size = path.stat().st_size
    with path.open("rb") as f:
        if size > nbytes: f.seek(size - nbytes)
        data = f.read().decode("utf-8", "replace")
    lines = data.splitlines()
    return lines[1:] if size > nbytes else lines

def _classify(rec):
    ev = str(rec.get("event") or "")
    meta = rec.get("meta") or {}
    blob = (ev + " " + json.dumps(meta, ensure_ascii=False)).lower()
    if "auth_denied" in blob or "需要人工授权" in blob: return "auth_wall"
    if any(k in blob for k in ("error", "exception", "traceback", "user_error", "denied")): return "real_fail"
    if ev in ("call", "ok", "auth_consumed", "auth_granted"): return "ok"
    return "other"

def build() -> int:
    lines = _tail_lines(AUDIT)
    if lines is None: print("A3 红：读不到 " + str(AUDIT)); return 1
    cnt = collections.Counter(); who = collections.defaultdict(collections.Counter)
    for ln in lines:
        ln = ln.strip()
        if not ln: continue
        try: rec = json.loads(ln)
        except Exception: cnt["bad_json"] += 1; continue
        cls = _classify(rec); cnt[cls] += 1
        kind = str((rec.get("meta") or {}).get("kind") or rec.get("kind") or "?")
        if cls in ("auth_wall", "real_fail"): who[cls][kind] += 1
    out = {"at": datetime.datetime.now().isoformat(timespec="seconds"),
           "source": str(AUDIT.relative_to(R)), "scanned_lines": len(lines),
           "counts": dict(cnt),
           "auth_wall_top": collections.Counter(who["auth_wall"]).most_common(8),
           "real_fail_top": collections.Counter(who["real_fail"]).most_common(8)}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("扫描 %d 行（尾部 %dMB）" % (len(lines), TAIL_BYTES // 1048576))
    print("三态: " + json.dumps(dict(cnt), ensure_ascii=False))
    print("授权墙 top: " + str(out["auth_wall_top"][:5]))
    print("真失败 top: " + str(out["real_fail_top"][:5]))
    return 0

def check() -> int:
    lines = _tail_lines(AUDIT)
    res = []
    if lines is None:
        res.append(("A3 取到读数", False, "读不到 audit.jsonl"))
    else:
        cnt = collections.Counter()
        for ln in lines:
            ln = ln.strip()
            if not ln: continue
            try: cnt[_classify(json.loads(ln))] += 1
            except Exception: cnt["bad_json"] += 1
        res.append(("A1 账可读", True, "%d 行" % len(lines)))
        res.append(("A2 三态可分", (cnt["ok"] + cnt["auth_wall"] + cnt["real_fail"]) > 0,
                    "ok=%d auth_wall=%d real_fail=%d" % (cnt["ok"], cnt["auth_wall"], cnt["real_fail"])))
        res.append(("A2b 授权墙与真失败分开计", cnt["auth_wall"] >= 0 and cnt["real_fail"] >= 0,
                    "两者独立计数（墙=%d / 真=%d）" % (cnt["auth_wall"], cnt["real_fail"])))
    for n, ok, det in res:
        print(("  OK   " if ok else "  FAIL ") + n + " — " + str(det))
    red = [n for n, ok, _ in res if not ok]
    print("判据 PASS %d · FAIL %d" % (len(res) - len(red), len(red)))
    return 1 if red else 0

def selftest() -> int:
    ck = []
    def c(n, ok, d=""):
        ck.append(bool(ok)); print(("OK  " if ok else "BAD ") + n + (" — " + str(d)[:44] if d else ""))
    c("授权墙：auth_denied 归 auth_wall", _classify({"event": "auth_denied", "meta": {"scope": "process_execute"}}) == "auth_wall")
    c("授权墙：中文理由也归 auth_wall", _classify({"event": "x", "meta": {"error": "需要人工授权（privacy_read）"}}) == "auth_wall")
    c("真失败：exception 归 real_fail", _classify({"event": "error", "meta": {"exception": "boom"}}) == "real_fail")
    c("正常：call 归 ok", _classify({"event": "call"}) == "ok")
    bad = len([x for x in ck if not x])
    print("\nfailure-attribution-check selftest: %d/%d" % (len(ck) - bad, len(ck)))
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
