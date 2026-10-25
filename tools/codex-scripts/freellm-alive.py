#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""FreeLLMAPI 网关 · **活体探测 + 把 Codex 钉到活的模型上**

## 为什么要有它（主人的原话：「这么还是显示会掉啊」）
网关是免费池：每个模型背后是**数量不定的上游路由**，配额一耗就整条冷却。网关自己的原话是：

    429 All models exhausted: 1 route checked (1 rate-limited or on cooldown).
        Add more API keys or wait for rate limits to reset.

⇒ **"钉死一个模型"这件事本身就是脆的**：钉得越死，那条路由一冷却就越没得选。
所以正确的做法不是"挑一个最好的钉上就完事"，而是**每次要用之前先看谁活着，再钉活的**。

## 三条口径
1. **先探后钉**：`probe` 逐个发**极小**请求（max_output_tokens=16）判活，
   **不许**拿"名单里有"当"能用"（`/v1/models` 列 260 个，实测绝大多数要么不在目录、要么没配密钥）。
2. **钉子要带备份**：写 `~/.codex/config.toml` 前先备份，且只动 `# freellmapi:start…end` 块里的 `model` 行。
3. **诚实记账**：每个模型的死活连同**网关原话**一起报；`pin` 只用**探到活的**那个。

用法：
```
python tools/codex-scripts/freellm-alive.py probe            # 看现在谁活着
python tools/codex-scripts/freellm-alive.py status           # 现在钉的是谁 + 它还活着吗
python tools/codex-scripts/freellm-alive.py pin              # 钉到第一个活的（自动备份）
python tools/codex-scripts/freellm-alive.py pin --model X    # 钉到指定模型（仍会先探活）
```
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = os.environ.get("FREELMLLMAPI_BASE") or "http://127.0.0.1:31415/v1"
CFG = Path.home() / ".codex" / "config.toml"
STATE = Path(__file__).resolve().parents[2] / "state" / "freellm-alive.json"

# 候选：先试"以前真答过"的，再试 auto/fusion（它们会路由到有容量的上游）
CANDIDATES = [
    "auto",
    "fusion",
    "meta/muse-glimmer-30b",
    "nvidia/nemotron-3-ultra-550b-a55b",
]


def _reg(n):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, n)[0]
    except Exception:                                                      # noqa: BLE001
        return None


def key():
    return (os.environ.get("FREELLMAPI_API_KEY") or _reg("FREELLMAPI_API_KEY")
            or os.environ.get("ZOHO_APP_PASSWORD"))


def probe_one(model, timeout=90):
    body = {"model": model, "input": "ping", "max_output_tokens": 16}
    req = urllib.request.Request(BASE + "/responses", method="POST",
                                 data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer %s" % (key() or ""),
                                          "Content-Type": "application/json"})
    t0 = time.time()
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        j = json.loads(r.read())
        return {"活": True, "状态": r.status, "status": j.get("status"),
                "落到": j.get("model"), "耗时s": round(time.time() - t0, 1)}
    except urllib.error.HTTPError as e:
        txt = e.read(220).decode("utf-8", "replace")
        try:
            msg = (json.loads(txt).get("error") or {}).get("message") or txt
        except Exception:                                                  # noqa: BLE001
            msg = txt
        return {"活": False, "状态": e.code, "为什么": msg[:200],
                "耗时s": round(time.time() - t0, 1)}
    except Exception as e:                                                 # noqa: BLE001
        return {"活": False, "连不上": str(e)[:160], "耗时s": round(time.time() - t0, 1)}


def cmd_probe(a):
    models = a.model or CANDIDATES
    if a.sample:
        try:
            r = urllib.request.urlopen(urllib.request.Request(
                BASE + "/models", headers={"Authorization": "Bearer %s" % (key() or "")}),
                timeout=40)
            allids = [x.get("id") for x in (json.loads(r.read()).get("data") or [])
                      if isinstance(x, dict)]
            step = max(1, len(allids) // a.sample)
            models = list(dict.fromkeys(allids[::step][:a.sample]))
        except Exception as e:                                             # noqa: BLE001
            print("取名单失败：%s" % str(e)[:120])
    res = {}
    for m in models:
        res[m] = probe_one(m)
        print("%s %-40s %s" % ("✅" if res[m]["活"] else "❌", m[:40],
                               ("落到 " + str(res[m].get("落到"))) if res[m]["活"]
                               else str(res[m].get("为什么") or res[m].get("连不上"))[:110]))
    alive = [m for m, v in res.items() if v["活"]]
    out = {"探测时间": time.strftime("%Y-%m-%dT%H:%M:%S"), "逐个": res,
           "活着的": alive, "死了的": [m for m in res if m not in alive],
           "_口径": "每个模型只发一次 max_output_tokens=16 的极小请求；死活以网关回包为准，"
           "不看 /v1/models 名单（名单里有 ≠ 能用）。"}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf-8")
    print("\n活着的 %d 个：%s" % (len(alive), "、".join(alive) or "（一个都没有 ⇒ 等配额恢复）"))
    print("账落：%s" % STATE)
    return 0 if alive else 1


def pinned():
    if not CFG.exists():
        return None, None
    t = CFG.read_text(encoding="utf-8")
    m = re.search(r"# freellmapi:start(.*?)# freellmapi:end", t, re.S)
    if not m:
        return None, None
    mm = re.search(r'^\s*model\s*=\s*"([^"]+)"', m.group(1), re.M)
    return (mm.group(1) if mm else None), t


def cmd_status(a):
    cur, _ = pinned()
    v = probe_one(cur) if cur else {"活": False, "为什么": "配置里没读到 model 行"}
    print(json.dumps({"现在钉的": cur, "它还活着吗": v["活"], "读数": v,
                      "_提示": "不活就跑 freellm-alive.py pin 钉到活的"}, ensure_ascii=False, indent=1))
    return 0 if v.get("活") else 1


def cmd_pin(a):
    cur, t = pinned()
    target = a.model
    if not target:
        for m in CANDIDATES:
            if probe_one(m)["活"]:
                target = m
                break
    if not target:
        print(json.dumps({"ok": False, "status": "no_alive_model",
                          "_结论": "一个活的都没有 ⇒ 不钉（钉了也是死），等配额恢复再跑本件"},
                         ensure_ascii=False, indent=1))
        return 1
    v = probe_one(target)
    if not v["活"]:
        print(json.dumps({"ok": False, "status": "target_dead", "目标": target, "读数": v,
                          "_结论": "指定要钉的那个现在不活 ⇒ 不钉"}, ensure_ascii=False, indent=1))
        return 1
    if cur == target:
        print(json.dumps({"ok": True, "status": "already", "钉的": target, "读数": v},
                         ensure_ascii=False, indent=1))
        return 0
    bak = CFG.with_name(CFG.name + ".bak-%s-pin" % time.strftime("%H%M%S"))
    shutil.copy2(CFG, bak)
    m = re.search(r"(# freellmapi:start)(.*?)(# freellmapi:end)", t, re.S)
    newblock = re.sub(r'(^\s*model\s*=\s*")[^"]+(")', r"\g<1>%s\g<2>" % target,
                      m.group(2), count=1, flags=re.M)
    CFG.write_text(t[:m.start(2)] + newblock + t[m.end(2):], encoding="utf-8")
    back = CFG.read_text(encoding="utf-8")
    m2 = re.search(r"# freellmapi:start(.*?)# freellmapi:end", back, re.S)
    got = re.search(r'^\s*model\s*=\s*"([^"]+)"', m2.group(1), re.M)
    print(json.dumps({"ok": got and got.group(1) == target, "status": "pinned",
                      "改前": cur, "改后": got.group(1) if got else None, "备份": str(bak),
                      "探活读数": v,
                      "_口径": "只动 # freellmapi:start…end 块里的 model 行；块外一字未动；改后回读核对。"},
                     ensure_ascii=False, indent=1))
    return 0


def main():
    ap = argparse.ArgumentParser(description="网关活体探测 + 把 Codex 钉到活的模型上")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("probe")
    p.add_argument("--model", nargs="*", default=[])
    p.add_argument("--sample", type=int, default=0, help="从 /v1/models 里等距抽样 N 个")
    p.set_defaults(fn=cmd_probe)
    p = sub.add_parser("status")
    p.set_defaults(fn=cmd_status)
    p = sub.add_parser("pin")
    p.add_argument("--model", default="")
    p.set_defaults(fn=cmd_pin)
    a = ap.parse_args()
    if not getattr(a, "fn", None):
        ap.print_help()
        return 2
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
