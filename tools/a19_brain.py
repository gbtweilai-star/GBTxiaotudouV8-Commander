# -*- coding: utf-8 -*-
"""A19 后台大脑（2026-10-31 · 主人令：A19 是必须的）

为什么需要它 —— 这是 iOS 前台互斥下唯一能常驻的形状：
  你在 Minis 里打字时，LM Pocket 会被挂起（前台互斥）。
  但**后台进程发起请求时**，apple-open 可以把 LM Pocket 拉到前台，
  此时 Minis 在后台、iSH 仍在跑（实测过心跳不断）—— **A19 就是活的**。

所以分工：
  ① 本守护**主动**把 A19 拉起/维持（不等谁来问）
  ② 桥把"此刻 A19 不可用"的请求**排队**（state/local_jobs.jsonl）
  ③ 本守护拿着 A19 真的算完，把结果写回（state/local_results.jsonl）
  ④ 桥那边按 id 取回结果 → 用户拿到答案

口径：判活只认 /v1/models 真 200；遇 429 退避重试（15s 级），不当失败。
"""
from __future__ import annotations

import json
import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
JOBS = ROOT / "state" / "local_jobs.jsonl"
RESULTS = ROOT / "state" / "local_results.jsonl"
HB = ROOT / "state" / "a19_brain.json"
LOG = ROOT / "state" / "a19_brain.jsonl"
KEY = os.environ.get("GBT_A19_KEY") or "gbt"
MODEL = os.environ.get("GBT_A19_MODEL") or "gbt-v8-v82-q5_0"


def http_ok(tmo: float = 5.0) -> bool:
    try:
        req = urllib.request.Request("http://127.0.0.1:1234/v1/models",
                                     headers={"Authorization": "Bearer " + KEY})
        with urllib.request.urlopen(req, timeout=tmo) as r:
            return r.status == 200
    except Exception:                                               # noqa: BLE001
        return False


def wake(wait_s: float = 45.0) -> bool:
    try:
        subprocess.run(["apple-open", "lmpocket://"], capture_output=True, timeout=25)
    except Exception:                                               # noqa: BLE001
        pass
    t0 = time.time()
    while time.time() - t0 < wait_s:
        if http_ok(4):
            return True
        time.sleep(1.5)
    return False


def chat(text: str, max_tokens: int = 64, tmo: float = 180.0) -> dict:
    body = json.dumps({"model": MODEL,
                       "messages": [{"role": "user", "content": text}],
                       "max_tokens": max(8, min(512, max_tokens))}).encode()
    for attempt, wait_s in enumerate((0, 15, 30)):
        if wait_s:
            time.sleep(wait_s)
        req = urllib.request.Request("http://127.0.0.1:1234/v1/chat/completions", data=body,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + KEY})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=tmo) as r:
                d = json.loads(r.read())
                ch = (d.get("choices") or [{}])[0]
                txt = str((ch.get("message") or {}).get("content") or "")
                return {"ok": True, "text": txt, "sec": round(time.time() - t0, 2),
                        "tokens": (d.get("usage") or {}).get("completion_tokens")}
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                continue                                   # 限流：退避再来
            return {"ok": False, "err": "http=%s" % e.code}
        except Exception as e:                                  # noqa: BLE001
            return {"ok": False, "err": type(e).__name__}
    return {"ok": False, "err": "429 x3"}


def _done_ids() -> set:
    out = set()
    if RESULTS.is_file():
        for line in RESULTS.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.add(json.loads(line).get("id"))
                except Exception:                                # noqa: BLE001
                    pass
    return out


def pending() -> list:
    if not JOBS.is_file():
        return []
    done = _done_ids()
    out = []
    for line in JOBS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            j = json.loads(line)
        except Exception:                                        # noqa: BLE001
            continue
        if j.get("id") not in done:
            out.append(j)
    return out[-3:]                                              # 新的优先，最多 3 条


def beat(state: str, extra: dict | None = None) -> None:
    rec = {"at": time.time(), "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "state": state, "pid": os.getpid()}
    if extra:
        rec.update(extra)
    try:
        HB.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    except Exception:                                            # noqa: BLE001
        pass


def log(rec: dict) -> None:
    try:
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:                                            # noqa: BLE001
        pass


def run(interval: float = 8.0) -> None:
    print("  A19 后台大脑启动 · 每 %.0fs 一轮 · model=%s" % (interval, MODEL), flush=True)
    while True:
        up = http_ok()
        if not up:
            beat("waking")
            ok = wake(45)
            up = ok
            log({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "act": "wake", "ok": ok})
            print("  %s 唤醒%s" % (time.strftime("%H:%M:%S"), "成功" if ok else "失败"), flush=True)
        if up:
            beat("online")
            jobs = pending()
            if jobs:
                for j in jobs:
                    r = chat(str(j.get("text") or ""), int(j.get("max_tokens") or 64))
                    rec = {"id": j.get("id"), "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                           "text": r.get("text") if r.get("ok") else "",
                           "backend": "a19" if r.get("ok") else "err",
                           "tokPerSec": None, "tokens": r.get("tokens"),
                           "sec": r.get("sec"), "err": r.get("err")}
                    with RESULTS.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    log({"at": rec["at"], "act": "answer", "id": rec["id"],
                         "ok": r.get("ok"), "sec": r.get("sec")})
                    print("  答完 %s · %s · %ss → %s" % (rec["id"], rec["backend"],
                          rec["sec"], str(rec["text"])[:40]), flush=True)
        else:
            beat("down")
        time.sleep(interval)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        print(json.dumps({"http_ok": http_ok(), "pending": len(pending())}, ensure_ascii=False))
        sys.exit(0)
    run(float(sys.argv[1]) if len(sys.argv) > 1 else 8.0)
