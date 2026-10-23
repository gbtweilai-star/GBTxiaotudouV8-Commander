# -*- coding: utf-8 -*-
"""进攻面两兄弟的真跑探针：`offense_ops`（计划面）与 `pentest`（授权验证面）。

## 为什么单独写它

这两位一直挂在 `needs_input` / `needs_ticket`，而且**旧的记账是手写的**（P9：账没有写手必烂）。
本探针把它们各自真过一遍门，把回执原话写进 `data/offense-pentest-live.json`，
由 `gen-capability-proof.py` ①j 段现读 —— 结论不手抄。

## 口径（重要，不许含糊）

  · **目标只用本机回环**（`127.0.0.1`）：这是 GBT 自证链，不碰第三方资产；
    目标登记走 `pentest op=authorize`（本身是受管动作，要票）；
  · `offense_ops` 只跑 **`op=plan`**（出计划，不动手）；`scope` 如实写「仅本机回环」；
  · `pentest` 跑 `op=verify`：**它要 `network_private` 票**。没票就如实记 `needs_ticket`，
    绝不把「缺票」写成「坏了」；有票时它会真做 TCP 可达 / TLS / 响应头检查。
  · 两位各自走 `api.run_task` 唯一门。

用法：
    py -3.14 -X utf8 tools/codex-scripts/probe-offense-live.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import api                      # noqa: E402

DATA = ROOT / "outputs" / "open-source-release" / "data"
TARGET = "127.0.0.1:8080"     # 本机回环 + 非标准端口：既证明"要登记"，也证明"能连上"
SCOPE = "仅本机回环（GBT 自证链）：只测本机服务、不出网、不碰第三方资产；越界即停"


def _start_listener(port: int = 8080):
    """起一个**本机**监听，让 verify 拿到阳性证据（不是只看"连接被拒"）。

    为什么必须自带监听：`pentest op=verify` 做的是 TCP 可达 + TLS 握手 + GET 响应头，
    端口没人听时只会回 `ConnectionRefusedError` —— 那是**目标没起**，不能拿来证明这一位能跑。
    监听只绑 127.0.0.1，用完就杀，不留后台进程。
    """
    import subprocess
    proc = subprocess.Popen([sys.executable, "-m", "http.server", str(port),
                             "--bind", "127.0.0.1"],
                            cwd=str(ROOT), stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    return proc


def _call(kind: str, payload: dict) -> dict:
    try:
        env = api.run_task(kind, payload)
    except Exception as exc:                       # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)[:300]}
    result = env.get("result") if isinstance(env.get("result"), dict) else {}
    if isinstance(result.get("result"), dict) and "kind" in result:
        result = result["result"]
    return {
        "ok": bool(env.get("ok")),
        "denied": bool(env.get("denied")),
        "missing_scopes": env.get("missing_scopes") or result.get("missing_scopes") or [],
        "result": result,
        "status": env.get("status"),
        "error": env.get("error") or (result or {}).get("message")
                 or (result or {}).get("reason"),
    }


def main() -> int:
    t0 = time.time()
    out: dict = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "schema": "offense-pentest-live-v1", "target": TARGET, "scope": SCOPE}

    plan = _call("offense_ops", {"op": "plan", "target": TARGET, "scope": SCOPE})
    out["offense_ops"] = {
        "ok": plan["ok"] and bool((plan["result"] or {}).get("phases")),
        "op": "plan",
        "phases": (plan["result"] or {}).get("phases"),
        "judges": (plan["result"] or {}).get("judges"),
        "denied": plan["denied"],
        "missing_scopes": plan["missing_scopes"],
        "error": plan["error"],
    }

    listener = _start_listener(8080)          # 本机监听：让 verify 有真东西可连
    verify = _call("pentest", {"op": "verify", "target": TARGET})
    checks = (verify["result"] or {}).get("checks") or []
    out["pentest"] = {
        "ok": verify["ok"] and not verify["denied"],
        "op": "verify",
        "denied": verify["denied"],
        "missing_scopes": verify["missing_scopes"],
        "error": verify["error"],
        "checks": checks,
        "consumed": (verify["result"] or {}).get("auth_consumed"),
        "result_keys": sorted((verify["result"] or {}).keys())[:10],
    }
    if listener is not None:
        try:
            listener.terminate()
            listener.wait(timeout=5)
        except Exception:                              # noqa: BLE001
            pass

    out["elapsed_s"] = round(time.time() - t0, 2)
    out["law"] = ("目标只用本机回环；offense_ops 只跑 plan（不动手）；pentest verify 要 "
                  "network_private 票，没票就如实记 needs_ticket。两位都过 run_task 唯一门。")
    DATA.mkdir(parents=True, exist_ok=True)
    p = DATA / "offense-pentest-live.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print("落账 →", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
