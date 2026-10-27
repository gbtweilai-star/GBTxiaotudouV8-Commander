#!/usr/bin/env python3
"""A19 自动接入哨兵 —— 它一出现，整条链路自己接上并当场验证

为什么需要这个：
  LM Pocket 的服务开关在 App 内部，容器外没有自动化入口（深链、文件关联、
  全端口扫描都试过）。所以人能做的最少动作就是"把 App 打开并开服务"。
  剩下的不该再由人来做 —— 本哨兵负责：

    ① 每 5 秒探 :1234
    ② 一出现 → 问 /v1/models 拿当前加载的模型名
    ③ 跑一次真生成，量首字延迟与 tok/s
    ④ 校验身份自述（是不是她的权重，而不是别人的模型在冒充）
    ⑤ 把结论落 state/a19_ready.json，并打日志
    ⑥ 掉线 → 清标志、记一笔，安静等下一次

  桥那边默认上游本来就是 selfhost，所以**不需要改任何配置**，
  哨兵只负责"证明它真的能答"，答不了就如实记失败原因。

用法：
  python3 tools/a19_attach.py                 # 常驻
  python3 tools/a19_attach.py --once          # 只探一次，给 CI/手工验收用
  python3 tools/a19_attach.py --once --wake   # 探不到就先 apple-open 拉一次
"""
from __future__ import annotations

import argparse
import json
import pathlib
import socket
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "a19_ready.json"
LOG = ROOT / "logs" / "a19_attach.log"
HOST, PORT = "127.0.0.1", 1234
KEY = "gbt"                     # LM Pocket 的 API 密钥（大写会 401）
PROMPT = "用一句话说：你是谁、谁做的你。"


def log(msg: str) -> None:
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def up(timeout: float = 1.5) -> bool:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((HOST, PORT))
        return True
    except OSError:
        return False
    finally:
        s.close()


def http(method: str, path: str, body: dict | None = None,
         timeout: float = 120) -> tuple[int, dict | str]:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((HOST, PORT))
        payload = json.dumps(body, ensure_ascii=False).encode() if body else b""
        req = ("%s %s HTTP/1.0\r\nHost: %s\r\nAuthorization: Bearer %s\r\n"
               "Content-Type: application/json\r\nContent-Length: %d\r\n"
               "Connection: close\r\n\r\n" % (method, path, HOST, KEY, len(payload))
               ).encode() + payload
        s.sendall(req)
        buf = b""
        while True:
            c = s.recv(65536)
            if not c:
                break
            buf += c
        head, _, raw = buf.partition(b"\r\n\r\n")
        first = head.split(b"\r\n")[0].decode("latin-1") if head else ""
        parts = first.split()
        code = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        try:
            return code, json.loads(raw)
        except Exception:                                     # noqa: BLE001
            return code, raw.decode("utf-8", "replace")
    finally:
        s.close()


def wake() -> None:
    try:
        subprocess.run(["apple-open", "lmpocket://"], capture_output=True,
                       timeout=15, check=False)
        log("已发唤醒指令（lmpocket://）")
    except Exception as exc:                                  # noqa: BLE001
        log("唤醒失败：%s" % exc)


def verify() -> dict:
    """容器在线时跑一遍真实验收。返回落盘用的 dict。"""
    t_probe = time.time()
    code, models = http("GET", "/v1/models", timeout=20)
    if code != 200 or not isinstance(models, dict):
        return {"ok": False, "stage": "models", "http": code,
                "detail": str(models)[:200], "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    ids = [m.get("id") for m in (models.get("data") or [])]

    t0 = time.perf_counter()
    code, resp = http("POST", "/v1/chat/completions", {
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 80, "temperature": 0, "stream": False,
    }, timeout=180)
    dt = time.perf_counter() - t0
    if code != 200 or not isinstance(resp, dict):
        return {"ok": False, "stage": "chat", "http": code,
                "models": ids, "detail": str(resp)[:200],
                "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    msg = ((resp.get("choices") or [{}])[0].get("message") or {})
    answer = (msg.get("content") or "").strip()
    usage = resp.get("usage") or {}
    ctok = usage.get("completion_tokens") or 0
    tps = round(ctok / dt, 2) if dt > 0 and ctok else None

    # 身份校验：是不是她的权重在答（关键 —— 不能让别人的模型冒充她）
    ident = ("小土豆" in answer) or ("GBT" in answer.upper()) or ("自由的风" in answer)
    return {"ok": bool(ident), "stage": "identity" if not ident else "ready",
            "container": "UP", "models": ids,
            "answer": answer[:200], "identity_ok": ident,
            "elapsed_s": round(dt, 2), "completion_tokens": ctok,
            "tok_per_s": tps, "probe_s": round(time.time() - t_probe, 2),
            "at": time.strftime("%Y-%m-%dT%H:%M:%S")}


def save(obj: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--wake", action="store_true")
    ap.add_argument("--interval", type=float, default=5.0)
    a = ap.parse_args()

    if a.once:
        if not up():
            if a.wake:
                wake()
                for _ in range(12):
                    time.sleep(5)
                    if up():
                        break
                if not up():
                    log("探不到 :1234（唤醒后等了 60 秒）")
                    save({"ok": False, "container": "DOWN",
                          "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                          "how_to": "打开 LM Pocket → 开启服务 → 密钥填 gbt"})
                    return 1
            else:
                log("探不到 :1234")
                save({"ok": False, "container": "DOWN",
                      "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
                return 1
        r = verify()
        save(r)
        log("验收：%s · 身份 %s · %.2fs · %s tok/s"
            % ("✅" if r["ok"] else "🔴 " + r.get("stage", "?"),
               r.get("identity_ok"), r.get("elapsed_s") or 0, r.get("tok_per_s")))
        if r.get("answer"):
            log("  她答：%s" % r["answer"][:80].replace("\n", " "))
        return 0 if r["ok"] else 1

    log("A19 哨兵启动 · 每 %.0fs 探一次 :1234" % a.interval)
    was = None
    while True:
        now = up()
        if now and was is not True:
            log("容器上线 → 开始验收")
            r = verify()
            save(r)
            if r["ok"]:
                log("✅ 就绪 · %s · %.2fs · %s tok/s · %s"
                    % ((r.get("models") or [""])[0], r.get("elapsed_s") or 0,
                       r.get("tok_per_s"), r.get("answer", "")[:60].replace("\n", " ")))
            else:
                log("🔴 验收没过 @%s：%s" % (r.get("stage"), str(r.get("detail"))[:120]))
        elif not now and was is not True:
            pass
        elif not now and was is True:
            log("容器掉线（iOS 后台回收属正常）· 清标志")
            save({"ok": False, "container": "DOWN",
                  "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
        was = now
        time.sleep(a.interval)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已停。")
