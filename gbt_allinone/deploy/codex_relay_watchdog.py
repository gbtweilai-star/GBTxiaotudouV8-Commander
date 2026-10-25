#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codex 中继看门狗 v2 —— 让 4446 中继真的能自愈。

为什么要有这个文件：
  v1（C:\\Users\\ADMIN\\.codex\\deepseek_proxy_watchdog.py）是个死循环脚本，
  但**没有任何东西在启动它**：没有计划任务、没有服务、没有开机项。
  于是"声明了看门狗，实际没人牵"。中继挂了只能靠人肉发现（2026-09-17 早上
  就是这么挂掉的：09-16 23:14 之后 /health 不通，三条会话全 0 token）。

本版遵守《静默失效律》：
  1. 健康检查不只看到"端口有回应"，还要确认 key_source 可用 ——
     没有 key 的代理是"活着但没用"，必须报出来，不许当作健康。
  2. 每一次重启、每一次失败都写日志（含原因与耗时），禁止 except: pass 吞掉。
  3. 退出码即结论，供计划任务/人工判定，不靠"看起来正常"。

用法：
  python codex_relay_watchdog.py --once      # 探一次，必要时拉起（计划任务每分钟跑）
  python codex_relay_watchdog.py --loop      # 常驻模式（30s 一次）
  python codex_relay_watchdog.py --status    # 只读体检报告

退出码：
  0  健康（无需动作）      10 重启成功
  11 重启后仍不健康        12 找不到可用解释器（缺 flask/requests）
  13 代理起来了但 key_source 不可用   14 互斥锁被占用，本次跳过

开发者：自由的风 · GBT小土豆V8
"""
from __future__ import annotations
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

# ---------------------------------------------------------------- 常量
PROXY = r"C:\Users\ADMIN\.codex\deepseek_proxy.py"
REPO = _GBT_ROOT
PORT = int(os.environ.get("GBT_RELAY_PORT", "4446"))
HEALTH_URL = os.environ.get("GBT_RELAY_HEALTH_URL", "http://127.0.0.1:%d/health" % PORT)
LOG_DIR = os.environ.get("GBT_RELAY_LOG_DIR", r"C:\Users\ADMIN\.codex\log")
LOG_FILE = os.path.join(LOG_DIR, "relay_watchdog.log")
STATE_FILE = os.path.join(LOG_DIR, "relay_watchdog.state.json")
LOCK_FILE = os.path.join(LOG_DIR, "relay_watchdog.lock")

# 按顺序找第一个同时具备 flask + requests 的解释器（代理依赖这两个）。
PY_CANDIDATES = [r"C:\Python310\python.exe", r"C:\Python312\python.exe"]

FAIL_THRESHOLD = int(os.environ.get("GBT_RELAY_FAIL_THRESHOLD", "3"))
START_TIMEOUT = float(os.environ.get("GBT_RELAY_START_TIMEOUT", "30"))
LOOP_INTERVAL = float(os.environ.get("GBT_RELAY_INTERVAL", "30"))


# ---------------------------------------------------------------- 基础设施
def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str, level: str = "INFO") -> None:
    """写日志；日志本身失败也必须可见（stderr），不许静默。"""
    line = "%s [%s] %s" % (_now(), level, message)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("%s (日志写入失败: %s)\n" % (line, exc))
    if level in ("WARN", "ERROR"):
        sys.stderr.write(line + "\n")


def _read_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_state(state: dict) -> None:
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2)
    except Exception as exc:  # noqa: BLE001
        log("状态文件写入失败: %s" % exc, "WARN")


class SingleInstance:
    """防止计划任务与常驻循环同时跑（也防止上一次没跑完就叠下一次）。"""

    def __init__(self, path: str):
        self.path = path
        self.acquired = False

    def __enter__(self):
        pid = os.getpid()
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as fh:
                    raw = fh.read().strip()
                other = int(raw) if raw.isdigit() else 0
                if other and other != pid and _pid_alive(other):
                    return self
            with open(self.path, "w", encoding="utf-8") as fh:
                fh.write(str(pid))
            self.acquired = True
        except Exception as exc:  # noqa: BLE001
            log("互斥锁处理失败（继续执行）: %s" % exc, "WARN")
            self.acquired = True
        return self

    def __exit__(self, *exc_info):
        if self.acquired:
            try:
                os.remove(self.path)
            except Exception:
                pass
        return False


def _pid_alive(pid: int) -> bool:
    try:
        # 2026-10-04 修：系统 CLI 输出是 ANSI(GBK)；text=True 无编码在 UTF-8 模式下会炸读线程。
        out = subprocess.run(
            ["tasklist", "/FI", "PID eq %d" % pid, "/NH"],
            capture_output=True, encoding="mbcs", errors="replace", timeout=15,
        ).stdout
        return str(pid) in out
    except Exception:
        return False


# ---------------------------------------------------------------- 探针
def port_open() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=2):
            return True
    except Exception:
        return False


def probe() -> dict:
    """返回 {reachable, ok, detail, model, base, key_source}。"""
    result = {"reachable": False, "ok": False, "detail": "", "model": "",
              "base": "", "key_source": ""}
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=6) as resp:
            body = resp.read().decode("utf-8", "ignore")
        result["reachable"] = True
    except Exception as exc:  # noqa: BLE001
        result["detail"] = "健康接口不可达: %s" % str(exc)[:160]
        return result

    try:
        data = json.loads(body)
    except Exception:
        result["detail"] = "健康接口返回非 JSON: %s" % body[:160]
        return result

    result["model"] = str(data.get("model", ""))
    result["base"] = str(data.get("base", ""))
    result["key_source"] = str(data.get("key_source", ""))

    if not result["model"] or not result["base"]:
        result["detail"] = "健康接口缺少 model/base 字段（版本可能不是 v2）"
        return result

    src = result["key_source"]
    if not src or src == "none" or "no key found" in src:
        result["detail"] = "代理在跑，但取不到上游密钥（key_source=%s）" % (src or "缺失")
        return result

    result["ok"] = True
    result["detail"] = "model=%s base=%s key=%s" % (
        result["model"], result["base"], src)
    return result


# ---------------------------------------------------------------- 进程
def listener_pids() -> list[int]:
    """谁在监听 4446。用 netstat 解析，避免依赖 psutil。"""
    try:
        # 2026-10-04 修：netstat 与 tasklist 同病（系统 CLI = ANSI/GBK 输出），
        # text=True 无编码在 UTF-8 模式（PYTHONUTF8=1）下会炸读线程 ⇒ 恒返回 []。
        out = subprocess.run(["netstat", "-ano", "-p", "tcp"],
                             capture_output=True, encoding="mbcs", errors="replace",
                             timeout=20).stdout
    except Exception as exc:  # noqa: BLE001
        log("netstat 调用失败: %s" % exc, "WARN")
        return []
    pids: list[int] = []
    pattern = re.compile(r"^\s*TCP\s+\S+:%d\s+\S+\s+LISTENING\s+(\d+)\s*$" % PORT)
    for line in out.splitlines():
        hit = pattern.match(line)
        if hit:
            pids.append(int(hit.group(1)))
    return pids


def kill_pid(pid: int) -> bool:
    try:
        done = subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                              capture_output=True, text=True, timeout=20)
        ok = done.returncode == 0
        log("杀掉无响应代理 pid=%d -> %s" % (pid, "成功" if ok else done.stderr.strip()[:120]),
            "WARN" if not ok else "INFO")
        return ok
    except Exception as exc:  # noqa: BLE001
        log("杀进程失败 pid=%d: %s" % (pid, exc), "ERROR")
        return False


def pick_python() -> str | None:
    for exe in PY_CANDIDATES:
        if not os.path.isfile(exe):
            continue
        try:
            done = subprocess.run([exe, "-c", "import flask, requests"],
                                  capture_output=True, text=True, timeout=25)
        except Exception as exc:  # noqa: BLE001
            log("解释器探测失败 %s: %s" % (exe, exc), "WARN")
            continue
        if done.returncode == 0:
            return exe
        log("解释器缺少依赖，跳过 %s: %s" % (exe, done.stderr.strip()[:160]), "WARN")
    return None


def start_proxy(python_exe: str) -> bool:
    flags = 0
    if hasattr(subprocess, "DETACHED_PROCESS"):
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write("%s [INFO] 拉起代理: %s %s\n" % (_now(), python_exe, PROXY))
    except Exception:
        pass
    try:
        subprocess.Popen([python_exe, PROXY], creationflags=flags, close_fds=True,
                         cwd=os.path.dirname(PROXY))
        return True
    except Exception as exc:  # noqa: BLE001
        log("拉起代理失败: %s" % exc, "ERROR")
        return False


def inject_vault_key() -> str:
    """从 DPAPI 保险箱取上游密钥，注入本进程环境，让代理不必依赖明文文件。

    代理的取密钥顺序是 GBT_DEEPSEEK_KEY > .deepseek_key > legacy.bak，
    所以在拉起它之前注入环境变量，明文文件就不再是必需项。

    这里**只认保险箱**（load_from_vault），不用 load_key()：
    环境里若存在来路不明的一份 key，不应该顶掉保险箱里的那一份 ——
    "取材错误必须可见"，所以来源会写进日志。
    取不到时如实记一条 WARN（代理会自己回落到文件），不静默吞掉。
    """
    try:
        if REPO not in sys.path:
            sys.path.insert(0, REPO)
        from gbt_allinone.deepseek_key import load_from_vault  # noqa: PLC0415
        key, source = load_from_vault()
        if not key:
            log("DPAPI 保险箱不可用（%s），代理将回落到 .deepseek_key 明文文件"
                % source, "WARN")
            return "vault:" + source
        os.environ["GBT_DEEPSEEK_KEY"] = key
        os.environ.setdefault("DEEPSEEK_API_KEY", key)
        return "vault:dpapi"
    except Exception as exc:  # noqa: BLE001
        log("DPAPI 保险箱注入异常（代理将回落到 .deepseek_key 明文文件）: %s"
            % str(exc)[:160], "WARN")
        return "unavailable"


# ---------------------------------------------------------------- 主逻辑
def run_once() -> int:
    state = _read_state()
    fails = int(state.get("consecutive_failures", 0) or 0)

    result = probe()
    if result["ok"]:
        if fails:
            log("中继恢复健康（上次连续失败 %d 次）：%s" % (fails, result["detail"]))
        state.update({"consecutive_failures": 0, "last_ok": _now(),
                      "last_detail": result["detail"]})
        _write_state(state)
        return 0

    fails += 1
    log("中继不健康（连续第 %d 次）：%s" % (fails, result["detail"]), "WARN")

    # 端口有响应但健康检查失败、且连续失败到阈值 → 判定为僵死，杀掉重来。
    if fails >= FAIL_THRESHOLD:
        pids = listener_pids()
        if pids:
            log("连续 %d 次不健康，判定僵死，重启（pid=%s）"
                % (fails, ",".join(str(p) for p in pids)), "ERROR")
            for pid in pids:
                kill_pid(pid)
            time.sleep(2)

    if listener_pids():
        state.update({"consecutive_failures": fails, "last_detail": result["detail"]})
        _write_state(state)
        return 11

    key_source = inject_vault_key()
    log("代理密钥来源: %s" % key_source, "INFO" if key_source != "unavailable" else "WARN")

    python_exe = pick_python()
    if not python_exe:
        log("找不到可用解释器（需要 flask + requests）", "ERROR")
        state.update({"consecutive_failures": fails, "last_detail": "no interpreter"})
        _write_state(state)
        return 12

    log("拉起代理，解释器 %s" % python_exe)
    if not start_proxy(python_exe):
        state.update({"consecutive_failures": fails, "last_detail": "start failed"})
        _write_state(state)
        return 11

    deadline = time.time() + START_TIMEOUT
    while time.time() < deadline:
        time.sleep(1.5)
        again = probe()
        if again["ok"]:
            log("代理重启成功，耗时 %.1fs：%s"
                % (START_TIMEOUT - (deadline - time.time()), again["detail"]))
            state.update({"consecutive_failures": 0, "last_ok": _now(),
                          "last_detail": again["detail"], "last_restart": _now(),
                          "restart_count": int(state.get("restart_count", 0) or 0) + 1})
            _write_state(state)
            return 10
        if again["reachable"] and "取不到上游密钥" in again["detail"]:
            log("代理已监听但密钥不可用：%s" % again["detail"], "ERROR")
            state.update({"consecutive_failures": fails, "last_detail": again["detail"]})
            _write_state(state)
            return 13

    log("代理拉起后 %.0fs 内仍未健康，放弃本轮" % START_TIMEOUT, "ERROR")
    state.update({"consecutive_failures": fails, "last_detail": "restart timeout"})
    _write_state(state)
    return 11


def run_status() -> int:
    result = probe()
    pids = listener_pids()
    state = _read_state()
    print("时间: %s" % _now())
    print("监听: %s" % (",".join(str(p) for p in pids) if pids else "无"))
    print("健康: %s" % ("是" if result["ok"] else "否"))
    print("详情: %s" % result["detail"])
    print("连续失败: %s" % state.get("consecutive_failures", 0))
    print("累计重启: %s" % state.get("restart_count", 0))
    print("最近健康: %s" % state.get("last_ok", "-"))
    print("日志: %s" % LOG_FILE)
    return 0 if result["ok"] else 11


def main() -> int:
    parser = argparse.ArgumentParser(description="Codex 中继看门狗 v2")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--once", action="store_true", help="探一次，必要时拉起（默认）")
    group.add_argument("--loop", action="store_true", help="常驻循环模式")
    group.add_argument("--status", action="store_true", help="只读体检")
    parser.add_argument("--interval", type=float, default=LOOP_INTERVAL,
                        help="循环模式间隔秒数（默认 30）")
    args = parser.parse_args()

    if args.status:
        return run_status()

    if args.loop:
        log("看门狗进入常驻模式，间隔 %.0fs" % args.interval)
        while True:
            try:
                run_once()
            except Exception as exc:  # noqa: BLE001
                log("本轮异常（不退出）: %s" % exc, "ERROR")
            time.sleep(max(5.0, args.interval))

    with SingleInstance(LOCK_FILE) as lock:
        if not lock.acquired:
            log("已有看门狗实例在跑，本轮跳过")
            return 14
        return run_once()


if __name__ == "__main__":
    sys.exit(main())
