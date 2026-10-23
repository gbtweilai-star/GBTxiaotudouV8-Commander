#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""车道后端体检 + 选路（只读，不改云端、不改 Worker）。

为什么要有它（2026-10-22 起）：
  vLLM 官方 2026-10-20 放出 `vllm-torchtpu`——把 vLLM 原样搬到 Google TPU，
  **同一个 OpenAI 兼容 server**。⇒ 我们的车道从此不该绑死在某一块 GPU 上：
  GPU / TPU / 备用端点，对上层都只是「一个 base_url + 一个 model 名」。
  本件就是那张登记表（`state/lane-backends.json`）的读口。

做三件事：
  ① 逐个后端读 health（RunPod /health 或 OpenAI /v1/models），给真读数；
  ② 按 `enabled` + `priority` 排出**当前可用顺序**；
  ③ `--promote <id>` 只写本地 `state/lane-active.json`（**不动云端、不动 Worker**），
     真正的切换仍要走部署门（D5）——本件不替你切。

用法：
  py -3.14 tools/model-bridge/lane-failover.py            # 只体检 + 排序
  py -3.14 tools/model-bridge/lane-failover.py --promote gpu-uncensored
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REG = os.path.join(ROOT, "state", "lane-backends.json")
ACTIVE = os.path.join(ROOT, "state", "lane-active.json")
CRED = os.path.expanduser(r"~\.dsh\.credentials.yaml")


def cred(name):
    try:
        t = open(CRED, encoding="utf-8").read()
    except OSError:
        return None
    m = re.search(re.escape(name) + r":[ \t]*(?:ref:)?[ \t]*[\"']?([A-Za-z0-9_\-]{16,})", t)
    return m.group(1) if m else os.environ.get(name)


def get(url, tok, to=12):
    hdr = {"User-Agent": "gbt-lane/1.0"}
    if tok:
        hdr["Authorization"] = "Bearer " + tok
    req = urllib.request.Request(url, headers=hdr)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=to) as r:
            return {"ok": True, "ms": round((time.time() - t0) * 1000),
                    "body": r.read(400).decode("utf-8", "replace")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "ms": round((time.time() - t0) * 1000),
                "err": "%s: %s" % (type(e).__name__, str(e)[:100])}


def probe(b):
    """返回 (alive:bool, 读数文本)。"""
    tok = cred(b.get("cred_ref") or "") if b.get("cred_ref") else None
    h = b.get("health")
    if h and "runpod.ai/v2/" in h:
        r = get(h, tok)
        if not r["ok"]:
            return False, "health 取不到（%s）" % r.get("err")
        try:
            j = json.loads(r["body"])
        except ValueError:
            return False, "health 回包不是 JSON"
        w = j.get("workers") or {}
        q = (j.get("jobs") or {}).get("inQueue")
        alive = int(w.get("ready") or 0) + int(w.get("running") or 0) > 0
        return alive, "ready=%s running=%s init=%s q=%s" % (
            w.get("ready"), w.get("running"), w.get("initializing"), q)
    # OpenAI 兼容：/v1/models
    base = (b.get("base_url_direct") or "").rstrip("/")
    # 🔴 2026-10-22 自纠：登记表里未开通的后端 `base_url_direct` 是**说明文字**不是 URL，
    #    直接喂给 urllib 会抛 ValueError ⇒ 先判协议头，不是 http(s) 就如实报「未开通」。
    if base and base.startswith("http"):
        r = get(base + "/models", tok)
        if r["ok"] and '"data"' in r["body"]:
            return True, "/v1/models 200（%dms）" % r["ms"]
        return False, "/v1/models 失败（%s）" % r.get("err")
    return False, "未登记可探地址（未开通/未填）"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--promote", default="")
    a = ap.parse_args()
    reg = json.load(open(REG, encoding="utf-8"))
    rows = []
    for b in reg.get("backends") or []:
        alive, reading = probe(b)
        rows.append({"id": b["id"], "label": b.get("label"), "kind": b.get("kind"),
                     "enabled": bool(b.get("enabled")), "priority": b.get("priority"),
                     "alive": alive, "reading": reading})
    rows.sort(key=lambda x: (not x["alive"], x["priority"] or 99))
    print("车道后端体检 · %s" % time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    for r in rows:
        flag = "✅" if r["alive"] else ("⛔" if r["enabled"] else "—")
        print("  %s %-18s %-34s %s" % (flag, r["id"], r["label"], r["reading"]))
    usable = [r for r in rows if r["alive"] and r["enabled"]]
    print("\n当前可用（按优先级）：%s" % ([r["id"] for r in usable] or "**无**"))

    if a.promote:
        pick = next((r for r in rows if r["id"] == a.promote), None)
        if not pick:
            print("没有这个后端 id：%s" % a.promote)
            return 2
        if not pick["alive"]:
            print("拒绝 promote：%s 现在**不可用**（%s）" % (pick["id"], pick["reading"]))
            return 1
        tmp = ACTIVE + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "active": pick["id"],
                       "label": pick["label"], "reading": pick["reading"],
                       "note": "只写本地选路文件；真正切换 Worker 上游仍要走部署门（D5）"},
                      fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        os.replace(tmp, ACTIVE)
        print("\n已把「选路意图」写到 %s ⇒ active=%s" % (ACTIVE, pick["id"]))
        print("注意：这只改**本地意图**，Worker 上游没动（要动它得走部署门 D5）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
