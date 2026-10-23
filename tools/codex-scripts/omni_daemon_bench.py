# -*- coding: utf-8 -*-
"""omni_daemon_bench · 加速比实测 + 负控 + 等价性（三判据）。"""
import json, os, socket, subprocess, sys, time, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = sys.executable
HOST, PORT = "127.0.0.1", 8791

def p50(xs):
    xs = sorted(xs); return xs[len(xs) // 2]

def via_daemon(kind, payload, n=5):
    ts = []; last = None
    for _ in range(n):
        s = socket.create_connection((HOST, PORT), timeout=90)
        f = s.makefile("rwb")
        t0 = time.time()
        f.write((json.dumps({"kind": kind, "payload": payload}) + chr(10)).encode("utf-8")); f.flush()
        line = f.readline(); ts.append((time.time() - t0) * 1000)
        last = json.loads(line.decode("utf-8"))
        s.close()
    return ts, last

def baseline(kind):
    t0 = time.time()
    r = subprocess.run([PY, str(ROOT / "tools/codex-scripts/five-dim.py"), "cap", kind],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    ms = (time.time() - t0) * 1000
    try: return ms, json.loads(r.stdout or "{}")
    except Exception: return ms, {"raw": (r.stdout or "")[:120]}

def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    t0 = time.time()
    d = subprocess.Popen([PY, str(ROOT / "tools/codex-scripts/omni_daemon.py")],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         encoding="utf-8", errors="replace")
    ready = d.stdout.readline().strip()
    if not ready:
        err = (d.stderr.readline() or "").strip()
        print("daemon 启动失败（不许静默）：" + (err[-300:] or "无 stderr"))
        d.kill(); return 1
    print("daemon 就绪 %.1fs : %s" % (time.time() - t0, ready))
    try:
        ts, last = via_daemon("health", {}, 5)
        print("daemon 路 health: P50=%.0fms min=%.0f max=%.0f" % (p50(ts), min(ts), max(ts)))
        bms, b = baseline("health")
        print("传统路 health(冷): %.0fms" % bms)
        print("加速比: %.1fx" % (bms / max(p50(ts), 1)))
        eq_a = (b.get("result") or {}).get("platform"), (b.get("result") or {}).get("python")
        eq_d = (last.get("result", {}).get("result") or last.get("result") or {}).get("platform")
        print("等价性: 传统 platform=%s · daemon platform=%s · 同=%s" % (eq_a[0], eq_d, eq_a[0] == eq_d))
        print("daemon 回执 status=%s" % (last.get("result", {}).get("status")))
        s = socket.socket(); s.settimeout(2)
        bad = s.connect_ex((HOST, PORT + 1)); s.close()
        print("负控(错端口 %d): connect_ex=%d（非 0 = 连不上，客户端必须回落旧路径）" % (PORT + 1, bad))
        return 0
    finally:
        d.terminate()
        try: d.wait(timeout=10)
        except Exception: d.kill()

if __name__ == "__main__":
    sys.exit(main())
