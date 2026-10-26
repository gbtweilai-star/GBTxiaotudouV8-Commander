#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_a19_chain —— A19 链路的连接点断言（跑一遍就知道哪一环断了，而不是猜）。

纪律：**只报实测**。容器不在 ⇒ 相关项如实记 "skip/down"，不许拿"应该没问题"糊过去。
用法： python3 tools/test_a19_chain.py
"""
import importlib.util
import json
import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
PORT = 1234
BRIDGE = 8791
rows = []


def add(name, ok, detail=""):
    rows.append({"点": name, "ok": bool(ok), "detail": str(detail)[:160]})


def up(port, t=1.0):
    s = socket.socket()
    s.settimeout(t)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except Exception:                                             # noqa: BLE001
        return False
    finally:
        s.close()


def load(path):
    spec = importlib.util.spec_from_file_location("m_" + path.stem, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    # 1 文件面
    for f in ("a19_ctl.py", "a19_ask.py", "a19_prefill.py", "a19_sentinel.py", "body.py"):
        add("文件 %s" % f, (TOOLS / f).exists())
    add("文件 model_bridge.py", (ROOT / "runtime" / "model_bridge.py").exists())

    # 2 语法面
    bad = []
    for f in ("a19_ctl.py", "a19_ask.py", "a19_prefill.py", "a19_sentinel.py", "body.py",
              str(pathlib.Path("..") / "runtime" / "model_bridge.py"),
              str(pathlib.Path("..") / "gbt_allinone" / "omni_plug.py")):
        p = TOOLS / f
        try:
            import ast
            ast.parse(p.read_text(encoding="utf-8"))
        except Exception as exc:                                  # noqa: BLE001
            bad.append("%s:%s" % (p.name, type(exc).__name__))
    add("语法全通过", not bad, ",".join(bad) or "7 份")

    # 3 容器面
    port = up(PORT)
    add("容器 :1234 监听", port, "UP" if port else "DOWN（宿主未点 Load & Start Server）")

    # 4 控制面（返回值版）
    ctl = load(TOOLS / "a19_ctl.py")
    st = ctl.status_dict()
    add("a19_ctl.status_dict", st.get("container") in ("UP", "DOWN"), st.get("container"))
    add("容器规格 ctx=4096 登记", st.get("ctx") == 4096, st.get("ctx"))

    # 5 容器不在时不许编造
    q = ctl.ask_dict("测试")
    add("ask 容器不在 ⇒ offline", (q.get("status") == "offline") if not port else q.get("ok"),
        q.get("status"))

    # 6 主执行器（omni_plug op=a19）
    sys.path.insert(0, str(ROOT))
    try:
        from gbt_allinone.api import run_task
        r = run_task("omni_plug", {"op": "a19", "do": "status"})
        inner = r.get("result", {})
        inner = inner.get("result", inner)
        add("run_task op=a19 status", inner.get("op") == "a19", inner.get("container"))
    except Exception as exc:                                      # noqa: BLE001
        add("run_task op=a19 status", False, "%s: %s" % (type(exc).__name__, exc))

    # 7 择活不许静默降级云端
    try:
        body = load(TOOLS / "body.py")
        r = body.resolve("推理")
        manual_only = getattr(body, "MANUAL_ONLY", set())
        cloud_auto = any(t.get("impl", "").startswith("@cloud")
                         for t in (r.get("tried") or [])) and r.get("ok")
        add("MANUAL_ONLY 生效", manual_only == {"@cloud", "@engine"} and not cloud_auto,
            "cloud 不参与自动择活" if manual_only else "常量缺失")
    except Exception as exc:                                      # noqa: BLE001
        add("MANUAL_ONLY 生效", False, "%s: %s" % (type(exc).__name__, exc))

    # 8 桥：严格模式（A19 不通不许落到云端）
    if up(BRIDGE):
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:%d/v1/chat/completions" % BRIDGE,
                data=json.dumps({"upstream": "selfhost", "max_tokens": 4,
                                 "messages": [{"role": "user", "content": "在吗"}]}).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            t = time.time()
            d = json.loads(urllib.request.urlopen(req, timeout=20).read())
            dt = time.time() - t
            if port:
                add("桥 selfhost 直答", d.get("ok") is True, "%.2fs" % dt)
            else:
                tried = d.get("tried") or []
                only_self = [x.get("upstream") for x in tried] == ["selfhost"]
                add("桥不降级云端", d.get("ok") is False and only_self,
                    "tried=%s" % [x.get("upstream") for x in tried])
        except Exception as exc:                                  # noqa: BLE001
            add("桥 selfhost 直答", False, "%s: %s" % (type(exc).__name__, exc))
        try:
            h = json.loads(urllib.request.urlopen(
                "http://127.0.0.1:%d/health" % BRIDGE, timeout=10).read())
            names = [u["name"] for u in h.get("upstreams") or []]
            add("桥 /health 200", h.get("ok") is True, "%d 条车道" % len(names))
            add("桥有 deepseek-pro 车道", "deepseek-pro" in names)
        except Exception as exc:                                  # noqa: BLE001
            add("桥 /health 200", False, "%s: %s" % (type(exc).__name__, exc))
    else:
        add("桥 :8791 在线", False, "未启动")

    # 9 队列 / worker / 哨兵
    qf = "/tmp/a19_queue.jsonl"
    n = sum(1 for _ in open(qf, encoding="utf-8")) if os.path.exists(qf) else 0
    add("队列可读", True, "%d 条待算" % n)
    ps = subprocess.run(["ps", "aux"], capture_output=True, text=True).stdout
    add("worker 在跑", "a19_worker" in ps, "容器一通即补算")
    add("哨兵在跑", "a19_sentinel" in ps, "容器一通即验收")

    # 10 文档
    doc = ROOT / "docs" / "17-phone-a19-runtime.md"
    txt = doc.read_text(encoding="utf-8") if doc.exists() else ""
    add("容器口径已落文档", "MANUAL_ONLY" in txt and "lmpocket://start" in txt)

    # 11 落盘面（2026-10-26 新增：一份账本，两个来源）
    TP = str(ROOT / "state" / "her_transcript.jsonl")
    def _lines(path):
        if not os.path.exists(path):
            return 0
        with open(path, encoding="utf-8") as fh:
            return sum(1 for x in fh if x.strip())

    if up(BRIDGE):
        try:
            n0 = _lines(TP)
            req = urllib.request.Request(
                "http://127.0.0.1:%d/_log/message" % BRIDGE,
                data=json.dumps({"role": "assistant", "text": "chain-selftest",
                                 "upstream": "selftest", "source": "selftest"}).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            w = json.loads(urllib.request.urlopen(req, timeout=10).read())
            n1 = _lines(TP)
            add("落盘写入", w.get("ok") is True and n1 == n0 + 1, "%d→%d" % (n0, n1))

            d = json.loads(urllib.request.urlopen(
                "http://127.0.0.1:%d/_log/tail?n=1" % BRIDGE, timeout=10).read())
            row = (d.get("rows") or [{}])[-1]
            add("source 字段贯通", row.get("source") == "selftest", row.get("source"))
        except Exception as exc:                                  # noqa: BLE001
            add("落盘写入", False, "%s: %s" % (type(exc).__name__, exc))

        # 容器不在时 her.py 必须**不落盘**（没发生的对话不记账）
        try:
            n2 = _lines(TP)
            r = subprocess.run([sys.executable, str(TOOLS / "her.py"), "断言自测"],
                               capture_output=True, text=True, timeout=60)
            n3 = _lines(TP)
            if port:
                add("容器在时 her.py 落盘", n3 > n2, "%d→%d" % (n2, n3))
            else:
                add("容器不在不落盘", r.returncode == 2 and n3 == n2, "exit=%d 行数 %d→%d"
                    % (r.returncode, n2, n3))
        except Exception as exc:                                  # noqa: BLE001
            add("容器不在不落盘", False, "%s: %s" % (type(exc).__name__, exc))

        # 清掉自测行（账本只留她真说过的话）
        try:
            with open(TP, encoding="utf-8") as fh:
                keep = [x for x in fh if "chain-selftest" not in x and "断言自测" not in x]
            with open(TP, "w", encoding="utf-8") as fh:
                fh.writelines(keep)
            add("账本清理", True, "自测行已剔除 · 余 %d 行" % len(keep))
        except Exception as exc:                                  # noqa: BLE001
            add("账本清理", False, "%s: %s" % (type(exc).__name__, exc))
    else:
        add("落盘面", False, "桥不在，跳过")

    try:
        r = subprocess.run([sys.executable, str(TOOLS / "her.py"), "--tail", "3"],
                           capture_output=True, text=True, timeout=60)
        add("her.py --tail 可用", r.returncode == 0, (r.stdout or r.stderr).strip()[:60])
    except Exception as exc:                                      # noqa: BLE001
        add("her.py --tail 可用", False, "%s: %s" % (type(exc).__name__, exc))

    ok = sum(1 for r in rows if r["ok"])
    print("%-26s %-5s %s" % ("连接点", "结果", "读数"))
    print("-" * 88)
    for r in rows:
        print("%-26s %-5s %s" % (r["点"], "OK" if r["ok"] else "FAIL", r["detail"]))
    print("-" * 88)
    print("合计 %d 点 · 通过 %d · 失败 %d" % (len(rows), ok, len(rows) - ok))
    down = [r["点"] for r in rows if not r["ok"]]
    if down:
        print("未通过：", "、".join(down))
    json.dump({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "rows": rows,
               "ok": ok, "total": len(rows)},
              open("/tmp/a19_chain_report.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
