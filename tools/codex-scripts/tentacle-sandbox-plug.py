# -*- coding: utf-8 -*-
"""tentacle-sandbox-plug · 触手沙箱口（context-mode 思路落到触手上）。

思路出处（现读）：github.com/mksglu/context-mode —— `ctx_execute` 起隔离子进程，
**只有 stdout 进上下文**，原始数据永不离开沙箱；hooks 在调用前**阻断/改道**。

本件把这条思路装到触手上 = 「**双插**」的第二根线：
  · 第 1 根 **原生口（raw）**：真实输出**落盘**（state/tentacle-raw/），留证可复查；
  · 第 2 根 **沙箱口（slim）**：只把**摘要(≤2KB) + 指针 + sha256** 送进上下文。

判据 fail-closed：S1 原生口落盘可读 · S2 摘要 ≤2KB · S3 削减率可算且>0 · S4 取不到=红。
用法：--call <能力位> [--payload-json <json>] | --selftest
开发者：自由的风 · 守护者：公主土豆 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"""
import argparse, datetime, hashlib, json, pathlib, subprocess, sys

R = pathlib.Path(__file__).resolve().parents[2]
RAW = R / "gbt_allinone" / "store" / "mirror_space" / "dimension" / "tentacle-raw"   # 🔴 落**镜像沙箱**（复用既有沙箱，不另造）
SLIM_LIMIT = 2048

def _register(asset: str, tentacle: str) -> dict:
    """把 raw 落件**登记进触手表**（接上触手：双通道产出的原生口必须有登记）。
    失败不静默：原因写进返回值，由调用方如实报。"""
    try:
        import importlib.util as _ilu
        _p = R / "tools" / "tentacle_bind.py"
        _spec = _ilu.spec_from_file_location("_tb", _p)
        _m = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_m)
        res = _m.bind(asset, tentacle, note="sandbox·双插", quiet=True)
        # 🔴 必须看返回值：bind 有**在册闸**（血账 2026-09-27），不在册会 fail-closed 拒收；
        #    上一版我只写 {"ok": True} ⇒ **假绿**（判据说已登记、实际被拒）。
        if isinstance(res, dict) and res.get("ok"):
            return {"ok": True}
        return {"ok": False, "error": str((res or {}).get("error") or res)[:120]}
    except Exception as _e:                                    # noqa: BLE001
        return {"ok": False, "error": str(_e)[:120]}


def call_sandboxed(kind: str, payload: dict | None = None, timeout: int = 180) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    out = subprocess.run(["py", "-3.14", "tools/codex-scripts/five-dim.py", "cap", kind,
                          json.dumps(payload or {}, ensure_ascii=False)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         timeout=timeout, cwd=str(R))
    raw_text = (out.stdout or "") + (out.stderr or "")
    raw_bytes = raw_text.encode("utf-8", "replace")
    p = RAW / ("%s-%s.txt" % (ts, kind))
    p.write_bytes(raw_bytes)
    sha = hashlib.sha256(raw_bytes).hexdigest()
    slim = raw_text[:SLIM_LIMIT]
    # 标签用**真能力位名**（在册）—— 不是自造前缀（那会被在册闸拒收）
    reg = _register(str(p.relative_to(R)).replace("\\", "/"), str(kind))
    return {"kind": kind, "ok": out.returncode == 0, "rc": out.returncode,
            "registered": bool(reg.get("ok")), "register_error": reg.get("error", ""),
            "raw_path": str(p.relative_to(R)), "raw_bytes": len(raw_bytes),
            "slim_bytes": len(slim.encode("utf-8", "replace")), "sha256": sha,
            "reduction_pct": round(100.0 * (1 - len(slim.encode("utf-8", "replace")) / max(len(raw_bytes), 1)), 1),
            "summary": slim}

def selftest() -> int:
    ck = []
    def c(n, ok, d=""):
        ck.append(bool(ok)); print(("OK  " if ok else "BAD ") + n + (" — " + str(d)[:44] if d else ""))
    r = call_sandboxed("health")
    c("S1 原生口落盘", (R / r["raw_path"]).is_file(), r["raw_path"])
    c("S2 摘要 ≤2KB", r["slim_bytes"] <= SLIM_LIMIT, str(r["slim_bytes"]) + "B")
    c("S3 削减率可算", isinstance(r["reduction_pct"], float), str(r["reduction_pct"]) + "%")
    c("S6 原生口已登记进触手表", r.get("registered") is True, r.get("register_error", ""))
    c("S4 哈希可核", len(r["sha256"]) == 64)
    c("S5 raw 落在镜像沙箱内", "mirror_space" in str(RAW) and r["raw_path"].replace("\\", "/").find("mirror_space/dimension") >= 0,
      "落点=" + str(RAW.relative_to(R)))
    bad = len([x for x in ck if not x])
    print("\ntentacle-sandbox-plug selftest: %d/%d · 原生 %d B → 沙箱 %d B（减 %.1f%%）"
          % (len(ck) - bad, len(ck), r["raw_bytes"], r["slim_bytes"], r["reduction_pct"]))
    return 1 if bad else 0

def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--call"); ap.add_argument("--payload-json", default="{}")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest: return selftest()
    if not a.call: print("用法: --call <能力位> | --selftest"); return 2
    try: p = json.loads(a.payload_json)
    except Exception: p = {}
    r = call_sandboxed(a.call, p)
    print(json.dumps({k: r[k] for k in ("kind", "ok", "rc", "raw_path", "raw_bytes",
                                        "slim_bytes", "reduction_pct", "sha256")}, ensure_ascii=False, indent=1))
    return 0 if r["ok"] else 1

if __name__ == "__main__":
    sys.exit(main())
