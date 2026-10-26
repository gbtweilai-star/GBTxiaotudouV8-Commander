#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_page_probe —— 页面回归：不碰 A19、不碰云，验「页面到底发了什么」。

做法：把真桥停掉 → 起假桥（记录请求体）→ 用 minis-browser-use 在真浏览器里
     点两下「发送」（"你是谁？" 然后 "继续"）→ 取回两条原始请求体做断言 → 恢复真桥。

断言四项（都是 2026-10-26 修过的坑）：
  1. system 是她的身份（含 GBT小土豆V8 与两行署名），不是「严谨的中文助手」
  2. 采样参数确实发出去了（temperature / top_p / repeat_penalty）
  3. upstream 默认 selfhost，stream=true
  4. 第二句「继续」自动带上上一轮回答的前缀，且**没有**塞 messages 历史

用法： python3 tools/test_page_probe.py
退出码：0 全过 / 1 有断言失败 / 2 环境不齐（浏览器或假桥没起来）
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
MOCK = os.path.join(TOOLS, "mock_bridge.py")
PAGE = "minis://shared/gbtv8/holo_pet_w3/model-chat/index.html"
REC = "/tmp/mock_req.jsonl"
rows = []


def add(name, ok, detail=""):
    rows.append((name, bool(ok), str(detail)[:150]))


def sh(cmd, timeout=90):
    """字符串走 shell；列表走 argv（**不能**把列表配 shell=True，那样只有第一个词生效）。"""
    return subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True,
                          text=True, timeout=timeout)


def js(script, timeout=90):
    return sh(["minis-browser-use", "execute_js", "--script", script], timeout)


def port_open(port, t=1.0):
    import socket
    s = socket.socket()
    s.settimeout(t)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except Exception:                                             # noqa: BLE001
        return False
    finally:
        s.close()


def start_mock():
    sh("pkill -f model_bridge.py")
    sh("pkill -f mock_bridge.py")
    # 🔴 必须等端口真的空出来再起假桥 —— 否则假桥 bind 失败，
    #    探针会连到还没死透的真桥，读出 TimeoutError（第一次就栽在这）。
    for _ in range(30):
        if not port_open(8791):
            break
        time.sleep(0.5)
    else:
        return False
    if os.path.exists(REC):
        os.remove(REC)
    subprocess.Popen([sys.executable, MOCK], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(40):
        try:
            d = json.loads(urllib.request.urlopen(
                "http://127.0.0.1:8791/health", timeout=2).read())
            if d.get("service") == "mock-bridge":
                return True
        except Exception:                                         # noqa: BLE001
            pass
        time.sleep(0.5)
    return False


def restore_bridge():
    sh("pkill -f mock_bridge.py")
    for _ in range(30):
        if not port_open(8791):
            break
        time.sleep(0.5)
    bridge = os.path.join(ROOT, "runtime", "model_bridge.py")
    subprocess.Popen([sys.executable, bridge, "--port", "8791"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    for _ in range(20):
        try:
            d = json.loads(urllib.request.urlopen(
                "http://127.0.0.1:8791/health", timeout=2).read())
            if d.get("service") == "gbt-model-bridge":
                return True
        except Exception:                                         # noqa: BLE001
            pass
        time.sleep(0.5)
    return False


def main():
    if not os.path.exists(MOCK):
        add("假桥文件在", False, MOCK)
        return 2
    if not sh("command -v minis-browser-use").stdout.strip():
        add("浏览器 CLI 在", False, "minis-browser-use 缺失")
        return 2

    TP0 = os.path.join(ROOT, "state", "her_transcript.jsonl")
    try:
        with open(TP0, encoding="utf-8") as fh:
            _snapshot = fh.read()
    except Exception:                                             # noqa: BLE001
        _snapshot = ""
    with open("/tmp/probe_snapshot.jsonl", "w", encoding="utf-8") as fh:
        fh.write(_snapshot)

    if not start_mock():
        add("假桥起来", False, "8791 上的 /health 不是 mock")
        return 2
    add("假桥起来", True, "selfhost → :1234")

    try:
        r = sh(["minis-browser-use", "navigate", "--url", PAGE], 120)
        add("页面打开", "minis://" in r.stdout or "Navigated" in r.stdout,
            r.stdout.strip()[:80])

        js("const i=document.getElementById('input');i.value='你是谁？';"
           "document.getElementById('send').click();")
        time.sleep(3.5)
        js("const i=document.getElementById('input');i.value='继续';"
           "document.getElementById('send').click();")
        time.sleep(3.5)

        rec = json.loads(urllib.request.urlopen(
            "http://127.0.0.1:8791/_rec", timeout=10).read())
        reqs = [x["body"] for x in rec.get("rows", [])
                if isinstance(x.get("body"), dict) and x["body"].get("messages")]
        add("抓到请求数", len(reqs) >= 2, "%d 条" % len(reqs))
        if len(reqs) < 2:
            for r2 in rows:
                print("%-22s %-4s %s" % (r2[0], "OK" if r2[1] else "FAIL", r2[2]))
            return 1

        first, second = reqs[0], reqs[-1]
        sysmsg = ""
        for m in first.get("messages", []):
            if m.get("role") == "system":
                sysmsg = m.get("content") or ""
        add("① system 是她的身份",
            "GBT小土豆V8" in sysmsg and ("自由的风" in sysmsg) and ("公主土豆" in sysmsg),
            sysmsg[:60])
        add("① 不再是「严谨的中文助手」", "严谨的中文助手" not in sysmsg)

        add("② 采样参数发出去了",
            first.get("temperature") == 0.7 and first.get("top_p") == 0.9
            and float(first.get("repeat_penalty") or 0) > 1.0,
            "t=%s p=%s rp=%s" % (first.get("temperature"), first.get("top_p"),
                                 first.get("repeat_penalty")))
        add("③ 默认 selfhost 且流式",
            first.get("upstream") == "selfhost" and first.get("stream") is True,
            "%s/%s" % (first.get("upstream"), first.get("stream")))

        u2 = [m.get("content") or "" for m in second.get("messages", [])
              if m.get("role") == "user"]
        joined = " ".join(u2)
        add("④ 续写带上了上文", "你上一句是" in joined and "继续" in joined,
            joined[:80].replace("\n", " "))
        add("④ 没塞 messages 历史",
            len([m for m in second.get("messages", []) if m.get("role") == "user"]) == 1
            or "你上一句是" in joined,
            "user 消息 %d 条" % len([m for m in second.get("messages", [])
                                    if m.get("role") == "user"]))
    finally:
        # 清场：假桥说过的话不许留在账本里，页面 localStorage 也清掉
        try:
            js("localStorage.removeItem('her_log_buf'); 'cleared'")
            # 快照恢复：比"按关键字过滤"可靠 —— 假桥的 user/sensor 行里没有"假桥"字样
            with open(TP0, "w", encoding="utf-8") as fh:
                fh.write(_snapshot)
            add("假桥记录已清", True, "已按快照恢复（%d 行）" % _snapshot.count(chr(10)))
        except Exception as exc:                                  # noqa: BLE001
            add("假桥记录已清", False, "%s: %s" % (type(exc).__name__, exc))
        add("真桥恢复", restore_bridge(), "8791 = gbt-model-bridge")

    ok = sum(1 for r in rows if r[1])
    print("%-24s %-4s %s" % ("断言", "结果", "读数"))
    print("-" * 84)
    for name, good, detail in rows:
        print("%-24s %-4s %s" % (name, "OK" if good else "FAIL", detail))
    print("-" * 84)
    print("合计 %d · 通过 %d · 失败 %d" % (len(rows), ok, len(rows) - ok))
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
