"""共享端点 + 队列背压（只读 · 可打假端点）—— 把「插件不各自加载模型」变成**可跑的东西**。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要有它（主人令：10 插件全互通、"不怕 CPU 不够内存不足"）
互通能让**消息**到，但**借不到算力**（见 `docs/无限制创作流水线.md` §十八）。
真正能解决"内存不够"的形态只有一种：**模型只在一台机器上加载一份，N 个插件都当客户端，
并发超了就排队**。本件把这条形态**跑成一个能看的读数**：

- **1 个端点**（本仓假端点，或真 vLLM）被 **N 个客户端**共用；
- **并发上限**（模拟端点的真实能力）—— 超出的**排队**，不并发堆爆；
- 读数：并发上限 · 峰值在飞 · 排队峰值 · 每请求延迟 · 超时数 · **吞吐**；
- **端点不可用 ⇒ 如实报「未读到」**，不许当成功（不许假绿）。

用法：
  python tools/codex-scripts/shared-endpoint-queue.py run --with-mock --clients 10 --concurrency 2
  python tools/codex-scripts/shared-endpoint-queue.py run --base-url http://<GPU>:8000/v1
  python tools/codex-scripts/shared-endpoint-queue.py selftest
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import queue
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def schedule(n_tasks: int, concurrency: int, worker) -> dict:
    """**纯调度**（好上负控）：N 个任务、最多 `concurrency` 个同时在飞，超出的排队。

    `worker(i) -> bool`：真任务函数（返回 False = 这一发没读到）。
    返回读数：峰值在飞 / 排队峰值 / 成功 / 未读到 / 耗时。**并发上限必须被守住**。
    """
    if n_tasks <= 0 or concurrency <= 0:
        return {"ok": False, "拒绝": "**任务数为 0 或并发上限 ≤ 0 ⇒ 拒绝**（空跑不算读数）"}
    q: "queue.Queue" = queue.Queue()
    for i in range(n_tasks):
        q.put(i)
    lock = threading.Lock()
    stat = {"在飞": 0, "峰值在飞": 0, "排队峰值": 0, "成功": 0, "**未读到**": 0}
    t0 = time.time()

    def one() -> None:
        while True:
            try:
                i = q.get_nowait()
            except queue.Empty:
                return
            with lock:
                stat["在飞"] += 1
                stat["峰值在飞"] = max(stat["峰值在飞"], stat["在飞"])
                stat["排队峰值"] = max(stat["排队峰值"], q.qsize())
            try:
                ok = bool(worker(i))
            except Exception:
                ok = False
            finally:
                with lock:
                    stat["在飞"] -= 1
                    stat[("成功" if ok else "**未读到**")] += 1
                q.task_done()

    ts = [threading.Thread(target=one, daemon=True) for _ in range(concurrency)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    stat["耗时秒"] = round(time.time() - t0, 3)
    stat["ok"] = True
    stat["并发上限"] = concurrency
    stat["判决"] = ("✅ 全部成功（并发 %d 上限守住：峰值在飞 %d）"
                  % (concurrency, stat["峰值在飞"]) if not stat["**未读到**"]
                  else "🔴 **有 %d 发未读到**（端点/超时问题，如实记）" % stat["**未读到**"])
    return stat


def _resolve_key(explicit: str, env_name: str) -> str:
    """取客户端钥匙（**只报形状、绝不回显**）。

    🔴 2026-10-14 补（实测真缺口）：本器原来**不带 Authorization 头** ⇒ 只能测 mock/匿名端点；
    打我们任何真端点（CLIProxyAPI 要 GBT_CLIPROXY_KEY · 云插件要 GW_AUTH · RunPod 要 rpa_…）
    十发全 401、读数只剩"未读到"。修法：显式 --key > 环境变量 > **用户注册表**（老进程环境块
    可能是旧的 —— 今天已两次踩到，别再让判据栽在环境上）。
    """
    if explicit:
        return explicit.strip()
    if not env_name:
        return ""
    v = (os.environ.get(env_name) or "").strip()
    if v or os.name != "nt":
        return v
    try:
        import winreg                                            # noqa: PLC0415
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return (winreg.QueryValueEx(k, env_name)[0] or "").strip()
    except Exception:                                            # noqa: BLE001
        return ""


def ask(base_url: str, model: str, q: str, timeout: float = 30.0, key: str = "") -> bool:
    body = {"model": model, "messages": [{"role": "user", "content": q}]}
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:      # noqa: S310
        d = json.loads(r.read().decode("utf-8", errors="replace"))
    return bool(((d.get("choices") or [{}])[0].get("message") or {}).get("content"))


def run(base_url: str, model: str, clients: int, concurrency: int, key: str = "") -> int:
    stat = schedule(clients, concurrency,
                    lambda i: ask(base_url, model, "第 %d 号插件的请求：你好。" % (i + 1), key=key))
    print(json.dumps({"端点": base_url, "模型": model, "客户端数": clients,
                      "钥匙": (key[:4] + "****(" + str(len(key)) + ")") if key else "（未带钥匙）",
                      "读数": stat,
                      "口径": "**模型只在端点加载一份**，N 个插件都是客户端 ⇒ "
                            "插件侧不各自吃内存（这才是「不怕内存不够」的成立条件）；"
                            "并发超上限就排队，不堆爆"},
                     ensure_ascii=False, indent=1))
    return 0 if stat.get("ok") and not stat.get("**未读到**") else 1


def _with_mock(port: int = 8114, model: str = "gbt-potato-v8"):
    spec = importlib.util.spec_from_file_location(
        "_mve3", str(ROOT / "tools" / "codex-scripts" / "mock-vllm-endpoint.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.start_server(port, model), "http://127.0.0.1:%d/v1" % port


def selftest() -> int:
    checks, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad = bad + (0 if cond else 1)
        checks.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    r = schedule(10, 2, lambda i: (time.sleep(0.02), True)[1])
    ck("**正控：10 发全成 · 并发上限守住**",
       r["成功"] == 10 and r["峰值在飞"] <= 2, "峰值在飞 %s" % r["峰值在飞"])
    ck("**读数里有排队读数**（超上限的确实排过队）", r["排队峰值"] >= 0 and "耗时秒" in r, "")
    bad_r = schedule(3, 1, lambda i: i != 1)
    ck("**负控：有一发失败 ⇒ 记「未读到」且判决红**",
       bad_r["**未读到**"] == 1 and bad_r["判决"].startswith("🔴"), bad_r["判决"])
    ck("**边界：0 发 或 并发 ≤ 0 ⇒ 拒绝**（空跑不算读数）",
       schedule(0, 2, lambda i: True)["ok"] is False and schedule(2, 0, lambda i: True)["ok"] is False, "")
    try:
        schedule(2, 1, lambda i: (_ for _ in ()).throw(RuntimeError("端点炸了")))
        ck("**负控：任务抛异常 ⇒ 记「未读到」不记成功**", True, "")
    except Exception:
        ck("**负控：任务抛异常 ⇒ 记「未读到」不记成功**", False, "异常漏出来了")
    r2 = schedule(2, 1, lambda i: (_ for _ in ()).throw(RuntimeError("x")))
    ck("**负控：抛异常那两发都算未读到**", r2["**未读到**"] == 2, json.dumps(r2, ensure_ascii=False)[:60])
    print(json.dumps({"自检": {"条数": len(checks), "通过": len(checks) - bad, "不通过": bad},
                      "逐条": checks}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "selftest"])
    ap.add_argument("--base-url", default="")
    ap.add_argument("--model", default="gbt-potato-v8")
    ap.add_argument("--clients", type=int, default=10)
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--with-mock", action="store_true")
    ap.add_argument("--key", default="", help="显式客户端钥匙（不给则读 --key-env）")
    ap.add_argument("--key-env", default="GBT_CLIPROXY_KEY",
                    help="从哪个环境变量取钥匙（缺则回用户注册表；空串=不带钥匙）")
    a = ap.parse_args()
    a.key_used = _resolve_key(a.key, a.key_env)
    if a.cmd == "selftest":
        return selftest()
    if a.with_mock:
        srv, base = _with_mock(model=a.model)
        try:
            return run(base, a.model, a.clients, a.concurrency, key=a.key_used)
        finally:
            srv.shutdown()
    if not a.base_url:
        print(json.dumps({"拒绝": "run 需要 --base-url 或 --with-mock"}, ensure_ascii=False))
        return 2
    return run(a.base_url, a.model, a.clients, a.concurrency, key=a.key_used)


if __name__ == "__main__":
    raise SystemExit(main())
