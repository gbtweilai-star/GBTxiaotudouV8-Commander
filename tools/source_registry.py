#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""source_registry —— 触手插座注册表：**任何东西挂上来 = 加一行**。

主人 2026-10-29（看 EchoBird 127.0.0.1:55536 那张图）：
  「触手可以把任何东西像这样连接起来使用。」

原理（EchoBird 三句）：
  ① 本地固定端点跑代理，应用只认一个地址 ⇒ 免切换
  ② 同时讲两套协议（OpenAI + Anthropic）
  ③ 上游挂一堆源 ⇒ 可负载、可故障转移

我们已有 ①②。**这里补 ③ 的可插拔**：上游不写死在代码里，而是一张表。
桥（runtime/model_bridge.py）启动时读 state/upstreams.extra.json，
格式与 omni_plug 插座描述符同形 ⇒ 插一次 = 接上一个源，不用改代码。

## 纪律
  · `ours` 不写 true 就**不算自有权重** —— 绝不冒充
  · 钥匙只写槽名（env:XXX / file:path），**不回显明文**
  · 加之前先探活（--probe），连不上也允许加，但在表里标 last_probe
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
TBL = ROOT / "state" / "upstreams.extra.json"


def load() -> list:
    try:
        return json.loads(TBL.read_text(encoding="utf-8")) if TBL.is_file() else []
    except Exception:                                         # noqa: BLE001
        return []


def save(rows: list) -> None:
    TBL.parent.mkdir(parents=True, exist_ok=True)
    TBL.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def probe(base: str, timeout: float = 12.0) -> dict:
    u = base.rstrip("/") + "/models"
    try:
        t0 = time.perf_counter()
        with urllib.request.urlopen(urllib.request.Request(
                u, headers={"User-Agent": "gbt-probe"}), timeout=timeout) as r:
            d = json.loads(r.read())
        ids = [x.get("id") for x in (d.get("data") or [])][:4]
        return {"ok": True, "ms": round((time.perf_counter() - t0) * 1000),
                "models": ids}
    except Exception as e:                                    # noqa: BLE001
        # 🔴 401/403 不等于"连不上"：**端点活着，只是缺钥匙**。
        #   把两者混成一个红点，会让人以为源坏了（实测：openai-public 探出 401，
        #   我差点当成不可用）。分开记：reachable / needs_key / unreachable。
        code = getattr(e, "code", None)
        if code in (401, 403):
            return {"ok": False, "reachable": True, "needs_key": True,
                    "why": "HTTP %d：端点活着，缺钥匙" % code}
        return {"ok": False, "reachable": False,
                "why": "%s: %s" % (type(e).__name__, str(e)[:70])}


def cmd_add(args: list) -> int:
    def opt(n, d=None):
        return args[args.index(n) + 1] if n in args else d
    name, base = opt("--name"), opt("--base")
    if not name or not base:
        print("  要给 --name 与 --base（如 https://host/v1）"); return 2
    rows = [r for r in load() if r.get("name") != name]
    row = {"name": name, "base": base, "model": opt("--model") or "",
           "key": opt("--key") or "", "timeout": float(opt("--timeout") or 60),
           "ours": ("--ours" in args), "added_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if "--probe" in args:
        row["last_probe"] = probe(base)
        p = row["last_probe"]
        if p["ok"]:
            print("  探活：✅ 可达 %.0fms %s" % (p["ms"], p.get("models")))
        elif p.get("needs_key"):
            print("  探活：🟡 %s（可达，补钥匙即可用）" % p.get("why"))
        else:
            print("  探活：🔴 不可达 %s" % p.get("why"))
    rows.append(row)
    save(rows)
    print("  ✅ 已接上：%s → %s（ours=%s）" % (name, base, row["ours"]))
    print("     桥重启后生效：sh tools/up.sh up")
    return 0


def cmd_list(args: list) -> int:
    rows = load()
    print("  ═══ 可插拔上游 %d 个 ═══\n" % len(rows))
    for r in rows:
        p = r.get("last_probe") or {}
        mark = ("✅" if p.get("ok") else
                ("🟡" if p.get("needs_key") else ("🔴" if p else "·")))
        print("  %s %-18s %-46s ours=%-5s key=%s"
              % (mark, r.get("name"), str(r.get("base"))[:46],
                 r.get("ours"), r.get("key") or "—"))
    if not rows:
        print("  （空）加一个：gbt source add --name x --base https://host/v1 --probe")
    return 0


def cmd_rm(args: list) -> int:
    def opt(n, d=None):
        return args[args.index(n) + 1] if n in args else d
    name = opt("--name")
    rows = load()
    left = [r for r in rows if r.get("name") != name]
    save(left)
    print("  %s 已移除（剩 %d）" % (name, len(left)) if len(left) != len(rows)
          else "  没找到 %s" % name)
    return 0


def main(argv: list) -> int:
    op = argv[1] if len(argv) > 1 else "list"
    a = argv[2:]
    if op == "add":
        return cmd_add(a)
    if op == "rm":
        return cmd_rm(a)
    return cmd_list(a)


if __name__ == "__main__":
    import os
    os.environ.setdefault("GBT_AUTONOMOUS", "1")
    raise SystemExit(main(sys.argv))
