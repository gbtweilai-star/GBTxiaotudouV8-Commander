# -*- coding: utf-8 -*-
"""tentacle-link-registry · 触手连接登记（反向索引 + 漏登/泛绑/口径判据）。

关键口径（2026-10-15 定）：归类 ≠ 连接。
  · 归类（note=sweep / asset_index.wire / autobind 分类摆放）：按后缀或批量贴标签（如 .md 到 project_context），
    这是资产类型，不是某触手承担了某项工作；
  · 绑定（note=autobind）：产出即绑，这才是真连接。

判据 fail-closed：L1 表可读 · L2 每条登记触手 · L3 bound_at 可追 · L4 触手名可枚举 · L5 取不到=红 ·
  L6（黄）触手名混入 domain: 前缀 · L7 泛绑：真连接(autobind)里单个触手 >60% 才红（归类不算）。
用法：--build | --check | --selftest
开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"""
import argparse, collections, datetime, json, pathlib, sys

R = pathlib.Path(__file__).resolve().parents[2]
BIND = R / "state" / "asset_bindings.json"
OUT = R / "state" / "tentacle-links.json"
RED_PCT = 60.0

def _cls(note):
    n = (note or "").strip()
    if n == "autobind": return "bind"
    if n in ("sweep", "asset_index.wire") or n.startswith("autobind"): return "classify"
    return "other"

def _load():
    if not BIND.is_file(): return None
    try: j = json.loads(BIND.read_text(encoding="utf-8", errors="replace"))
    except Exception: return None
    return j if isinstance(j, dict) else None

def _idx(bind):
    idx = collections.defaultdict(list); empty = []; noat = []; ns = collections.defaultdict(list)
    cls = collections.defaultdict(collections.Counter)
    for asset, rec in bind.items():
        rec = rec or {}; ts = rec.get("tentacles") or []
        if not ts: empty.append(asset); continue
        c = _cls(rec.get("note"))
        for t in ts:
            (ns if str(t).startswith("domain:") else idx)[t].append(asset)
            cls[t][c] += 1
        if not rec.get("bound_at"): noat.append(asset)
    return idx, empty, noat, ns, cls

def build() -> int:
    bind = _load()
    if bind is None: print("L5 红：读不到 " + str(BIND)); return 1
    idx, empty, noat, ns, cls = _idx(bind)
    out = {"at": datetime.datetime.now().isoformat(timespec="seconds"),
           "source": "state/asset_bindings.json", "assets": len(bind), "tentacles": len(idx),
           "namespaces_domain": len(ns), "unregistered": len(empty), "no_bound_at": len(noat),
           "kou_jing": "classify 与 bind 分开计；L7 只看 bind",
           "links": {t: {"assets": len(v), "classify": cls[t]["classify"],
                         "bind": cls[t]["bind"], "other": cls[t]["other"]}
                     for t, v in sorted(idx.items(), key=lambda kv: -len(kv[1]))}}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("登记表已写 %s" % OUT.name)
    print("资产 %d · 真触手 %d · 命名空间 %d · 未登记 %d · 缺 bound_at %d"
          % (len(bind), len(idx), len(ns), len(empty), len(noat)))
    print("按真连接(bind) 排:")
    for t, c in sorted(cls.items(), key=lambda kv: -kv[1]["bind"])[:6]:
        print("   %-18s bind=%-5d classify=%-5d other=%-4d" % (t, c["bind"], c["classify"], c["other"]))
    if ns: print("   [domain: 命名空间] " + ", ".join("%s=%d" % (k, len(v)) for k, v in sorted(ns.items())))
    return 0

def check() -> int:
    bind = _load(); res = []
    if bind is None:
        res.append(("L5 取到读数", False, "读不到 asset_bindings.json"))
    else:
        idx, empty, noat, ns, cls = _idx(bind)
        bt = sum(c["bind"] for c in cls.values())
        top = max(((t, c["bind"]) for t, c in cls.items()), key=lambda kv: kv[1], default=("", 0))
        pct = 100.0 * top[1] / max(bt, 1)
        res.append(("L1 表可读", True, "%d 条资产" % len(bind)))
        res.append(("L2 每条登记触手", not empty, ("未登记 %d" % len(empty)) if empty else "齐"))
        res.append(("L3 bound_at 可追", not noat, ("缺 %d" % len(noat)) if noat else "齐"))
        res.append(("L4 触手名可枚举", len(idx) > 0, "%d 个" % len(idx)))
        res.append(("L6 domain: 命名空间已分流（黄）", True, ("%d 个（不阻断，登记表已单列）" % len(ns)) if ns else "齐"))
        res.append(("L7 真连接不泛绑（单触手 <=60%）", pct <= RED_PCT,
                    "真连接 %d 条；%s 占 %.1f%%" % (bt, top[0], pct)))
    for n, ok, det in res:
        print(("  OK   " if ok else "  FAIL ") + n + " — " + str(det))
    red = [n for n, ok, _ in res if not ok]
    print("判据 PASS %d · FAIL %d" % (len(res) - len(red), len(red)))
    return 1 if red else 0

def selftest() -> int:
    ck = []
    def c(n, ok, d=""):
        ck.append(bool(ok)); print(("OK  " if ok else "BAD ") + n + (" — " + str(d)[:44] if d else ""))
    b = {"a.md": {"tentacles": ["project_context"], "note": "sweep", "bound_at": "t"},
         "b.py": {"tentacles": ["filmkit"], "note": "autobind", "bound_at": "t"},
         "c.py": {"tentacles": [], "note": "autobind", "bound_at": "t"},
         "d.py": {"tentacles": ["domain:tools"], "note": "autobind", "bound_at": "t"}}
    idx, empty, noat, ns, cls = _idx(b)
    c("正例·sweep 归 classify 不算真连接", cls["project_context"]["bind"] == 0)
    c("正例·autobind 计 bind", cls["filmkit"]["bind"] == 1)
    c("负例·空触手进未登记", empty == ["c.py"])
    c("负例·domain: 分流进命名空间", "domain:tools" in ns)
    bad = len([x for x in ck if not x])
    print("\ntentacle-link-registry selftest: %d/%d" % (len(ck) - bad, len(ck)))
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
