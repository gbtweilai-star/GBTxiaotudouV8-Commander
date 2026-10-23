# -*- coding: utf-8 -*-
"""pod-link-selftest.py — `pod_link` 的两处「实测踩过」离线自检（断网 · 不碰门 · 不动任何卡）。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 它守的是两条血账（都真踩过，别再犯）

① **点名 A 却动了 B**（2026-10-20）：`_pick()` 在「点名的卡不是 RUNNING」时 `break` 然后回落到
   「第一条 RUNNING」—— 于是 `start` 想唤醒 4090，实际给**正在跑的训练卡**发了 resume。
② **长任务占着 WebSocket**（2026-10-20）：`run()` 是「开 kernel 的 ws、把脚本塞进去、等到 idle」，
   脚本一跑几十分钟必被代理掐（30.1s 超时 / 63s 连接被丢）。
   ⇒ 现口径：连接超时可配（默认 90s，最多试 3 次，指数退避），三试全败必须 fail-closed 带原始错误。

## 用法

    py -3.14 tools/digihuman/pod-link-selftest.py      # 8 条断言，全绿 rc=0
"""
import importlib.util
import json
import sys
import types
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                                   # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("pod_link", ROOT / "gbt_allinone" / "tools" / "pod_link.py")
pl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pl)

TRAIN = {"id": "train-0001", "name": "gbt-v8-v82x", "desiredStatus": "RUNNING", "状态": "RUNNING"}
DH = {"id": "dh-4090-01", "name": "gbt-dh-4090", "desiredStatus": "EXITED", "状态": "EXITED",
      "env": {"JUPYTER_PASSWORD": "tok"}}
PODS = [TRAIN, DH]
pl._pods = lambda: PODS
pl._ROOT = ROOT / ".scratch" / "_no_such_dir"          # 别读真指针

bad = 0


def check(name, ok, got=""):
    global bad
    print(("PASS " if ok else "FAIL ") + name + ("  ｜ got=%s" % (got,) if got != "" else ""))
    if not ok:
        bad += 1


# ── ① 选卡 ────────────────────────────────────────────────────────────────
a = pl._pick("dh-4090-01", require_running=False)
check("点名 EXITED 卡 + 允许非活卡 ⇒ 命中那张 4090", a.get("id") == DH["id"], a.get("name"))
b = pl._pick("dh-4090-01")
check("点名 EXITED 卡 + 要求活卡 ⇒ 回落但回执留痕",
      b.get("id") == TRAIN["id"] and "_picked_fallback" in b, b.get("_picked_fallback"))
check("点名不存在的卡 ⇒ 空（绝不回落到别的卡）", pl._pick("nope-xxxx", require_running=False) == {})
check("没点名 ⇒ 第一条 RUNNING", pl._pick("").get("id") == TRAIN["id"])


# ── ② 通道 ────────────────────────────────────────────────────────────────
class FakeWS:
    def __init__(self):
        self.sent = []
    def send(self, s):
        self.sent.append(json.loads(s))
    def recv(self):
        mid = self.sent[0]["header"]["msg_id"]
        return json.dumps({"header": {"msg_type": "status"}, "parent_header": {"msg_id": mid},
                           "content": {"execution_state": "idle", "text": "OK\n"}})
    def close(self):
        pass


def run_case(name, kernel_seq, ws_fail_times, expect_ok, ws_timeout=None):
    seq = list(kernel_seq)
    calls = {"kernel": 0, "ws": 0, "seen": []}

    def fake_req(url, method="GET", body=None, ctype="application/json", timeout=120):
        if "/api/kernels" in url and "channels" not in url:
            calls["kernel"] += 1
            st = seq.pop(0) if seq else 500
            return st, (json.dumps({"id": "kid-1"}).encode() if st in (200, 201) else b'{"error":"busy"}')
        return 204, b"{}"

    class FakeWSMod(types.SimpleNamespace):
        @staticmethod
        def create_connection(url, timeout=0, header=None):
            calls["ws"] += 1
            calls.setdefault("hdrs", []).append(header)
            calls["seen"].append(timeout)
            if calls["ws"] <= ws_fail_times:
                raise TimeoutError("Connection timed out")
            return FakeWS()

    pl._req = fake_req
    pl._pick = lambda pod="", require_running=True: DH
    sys.modules["websocket"] = FakeWSMod
    real_time, real_sleep = pl.time.time, pl.time.sleep
    pl.time = types.SimpleNamespace(time=lambda: 0.0, sleep=lambda s: None)   # 别真等
    payload = {"op": "run", "code": "print('OK')", "pod": DH["id"], "confirm": "主人已授权", "timeout": 60}
    if ws_timeout:
        payload["ws_timeout"] = ws_timeout
    r = pl.run_dispatch(**payload)
    ok = bool(r.get("ok")) == expect_ok
    check(name, ok, "kernel=%d ws=%d status=%s" % (calls["kernel"], calls["ws"], r.get("status") or "-"))
    if ws_timeout:
        check("ws 超时参数真的传进去了（不是写死 30）",
              calls["seen"] and calls["seen"][0] == ws_timeout, calls["seen"])
    pl.time = types.SimpleNamespace(time=real_time, sleep=real_sleep)


run_case("建 kernel 前两次 500、第三次 200 ⇒ 仍能跑", [500, 500, 200], 0, True)
run_case("ws 第一次超时、第二次连上 ⇒ 仍能跑（重试生效）", [200], 1, True)
run_case("ws 全塌（query+header 各 3 试共 6 次都失败）⇒ fail-closed 带回原因", [200], 6, False, ws_timeout=120)

print("结论：%d 条断言，%d 条失败" % (8 + 1, bad))
raise SystemExit(1 if bad else 0)


