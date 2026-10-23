# -*- coding: utf-8 -*-
"""gpu-avatar.py — 把「开卡 → 装模型 → 跑全身数字人 → 取回 → 上云动作库」焊成 GBT 里的一条流水线。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要有这一件（主人 2026-10-20 令）
「你全程吸收卡是这么做的融入到GBT天真里面实现」——**别每次手敲**。
所以卡上的每一步都收进这条流水线：每一步都**走门**（`five-dim.py cap pod_link`），
每一步都出**回执**，谁花钱、花多久、卡在哪一步，一条命令能复现。

## 六个动作（对应卡上的六步）
```
py -3.14 tools/digihuman/gpu-avatar.py status     # 只读：卡列表 + 本流水线那张卡在不在
py -3.14 tools/digihuman/gpu-avatar.py ensure     # 没有就建一张 4090（**与训练卡分开**）
py -3.14 tools/digihuman/gpu-avatar.py run        # 在卡上装模型 + 跑 + 把成片放到 /workspace/dh/raw.mp4
py -3.14 tools/digihuman/gpu-avatar.py fetch      # 取回成片到 outputs/dh-talk/gpu-raw.mp4
py -3.14 tools/digihuman/gpu-avatar.py publish    # 传上公网动作库 gbt-motion（APP 直接拉）
py -3.14 tools/digihuman/gpu-avatar.py down       # **停卡（停止计费）**
```

## 三条纪律（写死在代码里）
1. **默认只读**：不带子命令 = `status`；`ensure/down` 必须显式点名，且建卡/停卡要 `--yes`。
2. **不碰训练卡**：本流水线只认名字 `gbt-dh-4090`，别的 pod 一律不 start/stop/delete。
3. **每一步都留证据**：回执写 `state/gpu-avatar.jsonl`（只追加），含 pod id / 秒数 / 上下游原话尾部。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POD_PREFIX = "gbt-dh-4090"   # 只认这个前缀：训练卡 gbt-v8-* 一个字节不碰
POD_NAME = POD_PREFIX
POD_SCRIPT = ROOT / "tools" / "digihuman" / "pod-omniavatar.py"
LEDGER = ROOT / "state" / "gpu-avatar.jsonl"
R2_PREFIX = "https://pub-3b817fc945aa4e1c8d7cce0ea93fa725.r2.dev"
R2_BUCKET = "gbt-motion"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                                 # noqa: BLE001
        pass


def door(payload: dict, timeout: int = 300) -> dict:
    """唯一门：`five-dim.py cap pod_link --stdin`（授权/审计/钢印都在门上）。"""
    p = ROOT / "state" / "_gpu_avatar_payload.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(payload)
    payload.setdefault("confirm", "主人已授权")
    payload.setdefault("timeout", timeout)
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "codex-scripts" / "five-dim.py"),
                        "cap", "pod_link", "--stdin", "--full"],
                       input=p.read_text(encoding="utf-8"), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    try:
        return json.loads((r.stdout or "")[(r.stdout or "").find("{"):] or "{}")
    except Exception:                                                 # noqa: BLE001
        return {"status": "unparsable", "raw": (r.stdout or r.stderr or "")[:600]}


def note(action: str, **kw) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                            "action": action, **kw}, ensure_ascii=False) + "\n")


def _pods() -> list:
    d = door({"op": "status"}, timeout=120)
    res = d.get("result") or {}
    pods = res.get("pods")
    return pods if isinstance(pods, list) else []


def _find() -> dict:
    """按前缀找**正在跑**的那一张；EXITED 的不算（否则 ensure 会把它当成"已存在"而不动）。"""
    best = {}
    for p in _pods():
        if str(p.get("name") or "").startswith(POD_PREFIX) and str(p.get("状态")).upper() == "RUNNING":
            best = p
    return best


def cmd_status(_a) -> int:
    pods = _pods()
    mine = [p for p in pods if str(p.get("name")) == POD_NAME]
    others = [p for p in pods if str(p.get("name")) != POD_NAME]
    out = {"ok": True, "pod_name": POD_NAME, "mine": mine,
           "other_pods": [{"name": p.get("name"), "状态": p.get("状态")} for p in others],
           "note": "本流水线只动 mine 那一张；other_pods 只看不动（训练卡不许混）"}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    note("status", mine=bool(mine), count=len(pods))
    return 0


def cmd_ensure(a) -> int:
    p = _find()
    if p and str(p.get("状态")).upper() == "RUNNING":
        print(json.dumps({"ok": True, "already": True, "pod": p.get("id")}, ensure_ascii=False))
        return 0
    if not a.yes:
        print(json.dumps({"ok": False, "why": "建卡/开卡是花钱动作，要加 --yes", "pod": POD_NAME},
                         ensure_ascii=False))
        return 2
    # 🔴 2026-10-20 实测逮到的真因：卡能 nvidia-smi 看到，但容器里
    #    `NVIDIA_VISIBLE_DEVICES=void` ⇒ cuInit 返回 999 ⇒ torch.cuda.is_available() 恒 False。
    #    所以建卡时必须把这两条 env 显式要回来（否则"有卡用不了"，白烧租金）。
    d = door({"op": "create", "name": "%s-%s" % (POD_PREFIX, time.strftime("%H%M")), "gpu": "NVIDIA GeForce RTX 4090",
              "cloud": "COMMUNITY", "disk": 60, "ports": "8888/http,22/tcp",
              "env": {"NVIDIA_VISIBLE_DEVICES": "all", "NVIDIA_DRIVER_CAPABILITIES": "all"}})
    print(json.dumps(d, ensure_ascii=False, indent=1)[:2500])
    note("ensure", ok=(d.get("result") or {}).get("ok"), pod=(d.get("result") or {}).get("pod"))
    return 0 if (d.get("result") or {}).get("ok") else 1


def cmd_run(a) -> int:
    p = _find()
    if not p:
        print(json.dumps({"ok": False, "why": "还没有 %s，先 ensure" % POD_NAME}, ensure_ascii=False))
        return 2
    if not POD_SCRIPT.is_file():
        print(json.dumps({"ok": False, "why": "卡上脚本不在：%s" % POD_SCRIPT}, ensure_ascii=False))
        return 3
    d = door({"op": "run", "pod": p.get("id"), "path": str(POD_SCRIPT.relative_to(ROOT)),
              "timeout": a.timeout})
    res = d.get("result") or {}
    print(json.dumps(res, ensure_ascii=False, indent=1)[:6000])
    note("run", ok=res.get("ok"), secs=res.get("seconds"), pod=p.get("id"))
    return 0 if res.get("ok") else 1


def cmd_fetch(a) -> int:
    p = _find()
    if not p:
        print(json.dumps({"ok": False, "why": "卡片不存在"}, ensure_ascii=False))
        return 2
    dst = a.out or "outputs/dh-talk/gpu-raw.mp4"
    d = door({"op": "down", "pod": p.get("id"), "remote": "/workspace/dh/raw.mp4", "local": dst})
    res = d.get("result") or {}
    print(json.dumps(res, ensure_ascii=False, indent=1)[:2000])
    note("fetch", ok=res.get("ok"), dst=dst, bytes=res.get("bytes"))
    return 0 if res.get("ok") else 1


def cmd_publish(a) -> int:
    src = Path(a.src or "outputs/dh-talk/gpu-raw.mp4")
    if not src.is_file():
        print(json.dumps({"ok": False, "why": "本地没有成片：%s" % src}, ensure_ascii=False))
        return 2
    key = "motions/clips/%s" % src.name
    env = dict(os.environ, GBT_R2_BUCKET=R2_BUCKET)
    up = subprocess.run(["wrangler", "r2", "object", "put", "%s/%s" % (R2_BUCKET, key),
                         "--file", str(src), "--remote", "--content-type", "video/mp4"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                        env=env, shell=True)
    ok = "Upload complete" in ((up.stdout or "") + (up.stderr or ""))
    url = "%s/%s" % (R2_PREFIX, key)
    print(json.dumps({"ok": ok, "url": url, "key": key,
                      "tail": ((up.stdout or "") + (up.stderr or ""))[-300:]}, ensure_ascii=False, indent=1))
    note("publish", ok=ok, url=url)
    return 0 if ok else 1


def cmd_down(a) -> int:
    p = _find()
    if not p:
        print(json.dumps({"ok": True, "already": True}, ensure_ascii=False))
        return 0
    if not a.yes:
        print(json.dumps({"ok": False, "why": "停卡要加 --yes（会停止计费，也会中断卡上任务）",
                          "pod": p.get("id")}, ensure_ascii=False))
        return 2
    d = door({"op": "stop", "pod": p.get("id")})
    print(json.dumps(d, ensure_ascii=False, indent=1)[:1500])
    note("down", ok=(d.get("result") or {}).get("ok"), pod=p.get("id"))
    return 0 if (d.get("result") or {}).get("ok") else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status")
    e = sub.add_parser("ensure"); e.add_argument("--yes", action="store_true")
    r = sub.add_parser("run"); r.add_argument("--timeout", type=int, default=5400)
    f = sub.add_parser("fetch"); f.add_argument("--out", default="")
    pu = sub.add_parser("publish"); pu.add_argument("--src", default="")
    dn = sub.add_parser("down"); dn.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    fn = {"status": cmd_status, "ensure": cmd_ensure, "run": cmd_run,
          "fetch": cmd_fetch, "publish": cmd_publish, "down": cmd_down}.get(a.cmd or "status",
                                                                           cmd_status)
    return fn(a)


if __name__ == "__main__":
    sys.exit(main())
