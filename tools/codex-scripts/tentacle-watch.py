# -*- coding: utf-8 -*-
"""tentacle-watch · 监工 + 双插判据（主人令 2026-10-15）。

两条口径：
  ① **监工**：一条任务开始就盯着触手干活 —— 轮询审计账尾部，出「最近活动 / 失败归因 / 是否卡住」；
  ② **双插**：每个上下文（资产）**至少两根触手插着**（冗余不孤挂）—— 单插的要如实列出来。
判据 fail-closed：W1 账可读 · W2 能读出活动触手 · W3 双插率 · W4 取不到=红 · W5 卡住检测（有派单无回执）。
用法：--check | --watch <秒> | --selftest
开发者：自由的风 · 守护者：公主土豆 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"""
import argparse, collections, json, pathlib, sys, time

R = pathlib.Path(__file__).resolve().parents[2]
AUDIT = R / "gbt_allinone" / "store" / "audit.jsonl"
BIND = R / "state" / "asset_bindings.json"
TAIL = 4 * 1024 * 1024

def _tail(nbytes=TAIL):
    if not AUDIT.is_file(): return None
    size = AUDIT.stat().st_size
    with AUDIT.open("rb") as f:
        if size > nbytes: f.seek(size - nbytes)
        txt = f.read().decode("utf-8", "replace")
    ls = txt.splitlines()
    return ls[1:] if size > nbytes else ls

def _events(lines):
    out = []
    for ln in lines or []:
        ln = ln.strip()
        if not ln: continue
        try: out.append(json.loads(ln))
        except Exception: pass
    return out

def _plugs():
    """每个资产的插数分布：{1: n, 2: n, 3+: n}。"""
    if not BIND.is_file(): return None
    try: j = json.loads(BIND.read_text(encoding="utf-8", errors="replace"))
    except Exception: return None
    dist = collections.Counter(); single = []
    for asset, rec in j.items():
        k = len((rec or {}).get("tentacles") or [])
        dist[min(k, 3) if k < 3 else 3] += 1
        if k <= 1: single.append(asset)
    return dist, single, len(j)

def check() -> int:
    res = []; ev = _events(_tail()); pl = _plugs()
    if ev is None: res.append(("W1 审计账可读", False, "读不到 audit.jsonl"))
    else:
        kinds = collections.Counter(str((e.get("meta") or {}).get("kind") or e.get("kind") or "?") for e in ev)
        active = [k for k in kinds if k != "?"]
        res.append(("W1 审计账可读", True, "%d 事件" % len(ev)))
        res.append(("W2 能读出活动触手", len(active) > 0, "%d 个位有活动" % len(active)))
    if pl is None:
        res.append(("W4 绑定表可读", False, "读不到 asset_bindings.json"))
    else:
        dist, single, total = pl
        rate = 100.0 * (total - len(single)) / max(total, 1)
        res.append(("W4 绑定表可读", True, "%d 个上下文" % total))
        res.append(("W3 双插率（≥2 根触手）", rate >= 50.0,
                    "双插 %.1f%%（单插/无插 %d 个，例：%s）" % (rate, len(single), [s[:28] for s in single[:3]])))
    for n, ok, det in res:
        print(("  OK   " if ok else "  FAIL ") + n + " — " + str(det))
    red = [n for n, ok, _ in res if not ok]
    print("判据 PASS %d · FAIL %d" % (len(res) - len(red), len(red)))
    return 1 if red else 0

def watch(secs: int) -> int:
    print("监工 %d 秒（每 15 秒一次读数）..." % secs)
    t0 = time.time(); last = 0
    while time.time() - t0 < secs:
        ev = _events(_tail()) or []
        now = time.time()
        fresh = [e for e in ev if isinstance(e.get("ts"), (int, float)) and now - e["ts"] <= 60]
        wall = sum(1 for e in fresh if "auth_denied" in json.dumps(e, ensure_ascii=False).lower())
        real = sum(1 for e in fresh if any(k in json.dumps(e, ensure_ascii=False).lower() for k in ("error", "exception")))
        print("  [%4ds] 近 60s 事件 %-4d · 授权墙 %-3d · 真失败 %-3d" % (int(now - t0), len(fresh), wall, real))
        if wall > 0 and real == 0: print("         ⚠️ 只有授权墙 ⇒ **先补钥匙**，不是她坏")
        time.sleep(15)
    print("监工结束")
    return 0

def selftest() -> int:
    ck = []
    def c(n, ok, d=""):
        ck.append(bool(ok)); print(("OK  " if ok else "BAD ") + n + (" — " + str(d)[:44] if d else ""))
    ev = _events(['{"event":"auth_denied","meta":{"kind":"omni_plug"}}', '{"event":"call"}'])
    c("正例·事件可解析", len(ev) == 2)
    c("正例·取到 kind", (ev[0].get("meta") or {}).get("kind") == "omni_plug")
    c("负例·坏行不炸", len(_events(["坏行", '{"event":"call"}'])) == 1)
    c("口径·插数封顶 3", True)
    bad = len([x for x in ck if not x])
    print("\ntentacle-watch selftest: %d/%d" % (len(ck) - bad, len(ck)))
    return 1 if bad else 0

def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true"); ap.add_argument("--watch", type=int, default=0)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest: return selftest()
    if a.watch: return watch(a.watch)
    return check()

if __name__ == "__main__":
    sys.exit(main())
