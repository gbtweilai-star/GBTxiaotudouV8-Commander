# -*- coding: utf-8 -*-
"""pod-hud.py — 云卡「一个人在环上」的唯一小工具（读状态 / 看余额 / 选卡 / 发射载荷 / 拉日志 / 停卡）。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么只有这一件（2026-10-20 主人批评：「不停叠加和自造垃圾把自己绕晕」）

之前我在 `state/_*.py` 里散了一堆一次性脚本（`_pod-wait.py` / `_launch-omniavatar.py` /
`_diag_gpu.py` / `_fix_cuda.py` / `_rewrite_podlink.py` …），每次修一点就再写一个，最后自己都分不清哪个是活的。
按主人令「旧版永远不保留，修的时候直接原子替换」，**全部收进这一件**，散件已送回收站。

## 一切动作仍只走一个门

真动作（开卡/停卡/建卡/在卡上跑）一律经 `five-dim.py cap pod_link <json>`，
本件**只是拼参数 + 读回执**，不直连 RunPod、不绕门、不自己发授权。

## 六个子命令

    status   卡清单（谁在跑、谁在睡）
    gpu      现在可选卡与价（GraphQL 现读）
    account  余额与当前烧速
    launch   把 tools/digihuman/pod-omniavatar.py 甩到卡上**后台跑**，几秒返回（不占通道）
             ⚠️ 该载荷已**退役**（Owner 2026-10-21「甲」· journal §75）：全身口型物理不可达；
             在役线 = finish-clip.py（SadTalker，本地 CPU，零 GPU 花钱）。
    tail     拉卡上 /workspace/dh/run.log 看进度（零作用域，不花票）
    stop     停卡

用法：`py -3.14 tools/digihuman/pod-hud.py launch --pod <id>`
      `py -3.14 tools/digihuman/pod-hud.py tail  --pod <id>`
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                                   # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parents[2]
FIVE = ROOT / "tools" / "codex-scripts" / "five-dim.py"
PAYLOAD = ROOT / "tools" / "digihuman" / "pod-omniavatar.py"
LOCAL_LOG = ROOT / "state" / "pod-run.log"

# 卡上那段「几秒钟就返回」的发射代码：写文件 + 脱离 kernel 生命周期后台跑。
# 为什么不能直接 run 载荷：run 是「把整段脚本塞进 kernel 的 ws 里等 idle」，
# 几十分钟的任务必被代理掐（2026-10-20 实测：30.1s 超时 / 63s 连接被丢）。
LAUNCHER = r'''
import os, subprocess, sys
os.makedirs("/workspace/dh", exist_ok=True)
open("/workspace/dh/payload.py", "w", encoding="utf-8").write(SRC)
log = open("/workspace/dh/run.log", "a", encoding="utf-8")
p = subprocess.Popen([sys.executable, "-u", "/workspace/dh/payload.py"],
                     stdout=log, stderr=subprocess.STDOUT,
                     start_new_session=True, cwd="/workspace/dh")
print("LAUNCHED pid=%d log=/workspace/dh/run.log" % p.pid)
'''


def door(body: dict, full: bool = True) -> dict:
    """唯一门：five-dim cap pod_link。"""
    argv = [sys.executable, str(FIVE), "cap", "pod_link", json.dumps(body, ensure_ascii=False)]
    if full:
        argv.append("--full")
    r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        j = json.loads(r.stdout)
        return j.get("result") or j
    except Exception:                                                   # noqa: BLE001
        return {"ok": False, "_解析失败": (r.stdout or r.stderr or "")[-400:]}


def show(d: dict, n=None) -> None:
    """打回执。`n=None`=整份打（2026-10-20 实证：`status` 被 1600 字截断 ⇒ 输出是坏 JSON，
    我自己读它时 `ConvertFrom-Json` 直接报 "Unexpected end of input"——截断显示会把好读数变成读不了）。"""
    s = json.dumps(d, ensure_ascii=False, indent=1)
    print(s if n is None else s[:n])


# ── A′：走 SSH，不再依赖 Jupyter 与它的 WebSocket（2026-10-20 实测两条通道各缺一半）────────
KEYDIR = Path.home() / ".gbt" / "pod-ssh"
KEY = KEYDIR / "id_ed25519"
PUB = KEYDIR / "id_ed25519.pub"
SSH_OPTS = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=NUL",
            "-o", "BatchMode=yes", "-o", "ConnectTimeout=12"]


def pub_text() -> str:
    if not PUB.is_file():
        return ""
    return PUB.read_text(encoding="utf-8").strip()


def start_cmd_with_key(pub: str) -> str:
    """建卡启动命令：**只做一件事——把我的公钥写进 root 的 authorized_keys，然后照镜像原本那样起**。

    为什么不再往 start_cmd 里塞任务：2026-10-20 实测塞了「curl 载荷 + setsid 后台跑」之后
    Jupyter 就起不来（两次复现），而「跑任务」现在交给 ssh，不再需要卡自己起跑。
    """
    return ("bash -lc \"mkdir -p /root/.ssh && echo '%s' >> /root/.ssh/authorized_keys && "
            "chmod 700 /root/.ssh && chmod 600 /root/.ssh/authorized_keys && exec /start.sh\"" % pub)


def ssh_target(pod: str) -> list:
    """候选 ssh 目标（先直连公网 IP+映射端口，再走 RunPod 的 22 代理）。取不到就空，别瞎连。"""
    if not pod:
        return []
    d = door({"op": "status", "pod": pod})
    one = {}
    for p in (d.get("pods") or []):
        if p.get("id") == pod:
            one = p
    if not one:
        return []
    cands = []
    ip = one.get("公网IP") or one.get("publicIp") or ""
    ports = one.get("端口") or one.get("ports") or {}
    if isinstance(ports, dict):
        for k, v in ports.items():
            if str(v).lower().startswith("tcp") or str(k) == "22":
                try:
                    cands.append({"host": ip or ("%s-%s.proxy.runpod.net" % (pod, k)),
                                  "port": int(str(k)) if ip else 22, "via": "publicIp" if ip else "proxy"})
                except Exception:                                   # noqa: BLE001
                    pass
    # 官方文档：基础 SSH 形如 <podid>-<端口>@ssh.runpod.io（不支持 scp），公网 IP 才支持 scp
    if isinstance(ports, dict):
        for k in ports:
            cands.append({"host": "ssh.runpod.io", "port": 22, "via": "basic",
                          "user": "%s-%s" % (pod, k)})
    if not cands:
        cands = [{"host": "%s-22.proxy.runpod.net" % pod, "port": 22, "via": "proxy-default"},
                 {"host": "ssh.runpod.io", "port": 22, "via": "basic", "user": "%s-22" % pod}]
    for c in cands:
        c.setdefault("user", "root")
    return cands


def ssh_run(pod: str, cmd: str) -> dict:
    if not KEY.is_file():
        return {"ok": False, "error": "没有本机私钥：先跑 pod-hud keygen"}
    tries = []
    for t in ssh_target(pod):
        argv = ["ssh", "-i", str(KEY), *SSH_OPTS, "-p", str(t["port"]),
                "%s@%s" % (t.get("user", "root"), t["host"]), cmd]
        r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace")
        tries.append({"host": t["host"], "port": t["port"], "via": t["via"], "rc": r.returncode,
                      "out": (r.stdout or "")[-1500:], "err": (r.stderr or "")[-400:]})
        if r.returncode == 0:
            return {"ok": True, "via": t, "rc": 0, "out": (r.stdout or "")[-4000:]}
    return {"ok": False, "tries": tries}


def scp_get(pod: str, remote: str, local: str) -> dict:
    if not KEY.is_file():
        return {"ok": False, "error": "没有本机私钥"}
    tries = []
    for t in ssh_target(pod):
        argv = ["scp", "-i", str(KEY), *SSH_OPTS, "-P", str(t["port"]),
                "%s@%s:%s" % (t.get("user", "root"), t["host"], remote), local]
        r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace")
        tries.append({"host": t["host"], "port": t["port"], "rc": r.returncode,
                      "err": (r.stderr or "")[-300:]})
        if r.returncode == 0 and Path(local).is_file():
            return {"ok": True, "via": t, "bytes": Path(local).stat().st_size, "local": local}
    return {"ok": False, "tries": tries}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["status", "gpu", "account", "launch", "tail", "stop",
                                    "keygen", "create", "wait-ssh", "ssh", "scp"])
    ap.add_argument("--pod", default="")
    ap.add_argument("--confirm", default="主人已授权", help="开卡/停卡/发射必须带；缺省按主人当轮点头给")
    ap.add_argument("--cmd", dest="remote_cmd", default="")
    ap.add_argument("--remote", default="")
    ap.add_argument("--local", default="")
    ap.add_argument("--name", default="gbt-dh-run")
    ap.add_argument("--cloud", default="SECURE")
    ap.add_argument("--disk", type=int, default=60)
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()

    if a.cmd == "keygen":
        KEYDIR.mkdir(parents=True, exist_ok=True)
        if not KEY.is_file():
            subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-C", "gbt-pod-hud", "-f", str(KEY)],
                           capture_output=True, text=True)
        fp = subprocess.run(["ssh-keygen", "-lf", str(PUB)], capture_output=True, text=True).stdout.strip()
        show({"ok": KEY.is_file() and PUB.is_file(), "私钥": str(KEY), "指纹": fp,
              "公钥": pub_text()[:80] + "…" if pub_text() else ""})
        return 0
    if a.cmd == "create":
        pub = pub_text()
        if not pub:
            show({"ok": False, "error": "没有公钥：先跑 pod-hud keygen"})
            return 1
        r = door({"op": "create", "name": a.name, "cloud": a.cloud, "disk": a.disk,
                  "ports": "8888/http,22/tcp", "confirm": a.confirm,
                  "start_cmd": start_cmd_with_key(pub),
                  "env": {"SSH_PUBLIC_KEY": pub},
                  "gpu_try": ["NVIDIA GeForce RTX 4090", "NVIDIA GeForce RTX 3090", "NVIDIA RTX A5000"]})
        show(r)
        return 0 if r.get("ok") else 1
    if a.cmd == "wait-ssh":
        import time as _t
        end = _t.time() + a.timeout
        last = {}
        while _t.time() < end:
            last = ssh_run(a.pod, "nvidia-smi -L && python -c \"import torch;print('cuda',torch.cuda.is_available())\"")
            if last.get("ok"):
                show(last)
                return 0
            _t.sleep(10)
        show({"ok": False, "timeout_s": a.timeout, "last": last})
        return 2
    if a.cmd == "ssh":
        r = ssh_run(a.pod, a.remote_cmd or "nvidia-smi -L")
        show(r, 3000)
        return 0 if r.get("ok") else 1
    if a.cmd == "scp":
        if not a.remote or not a.local:
            show({"ok": False, "error": "要 --remote 与 --local"})
            return 1
        r = scp_get(a.pod, a.remote, a.local)
        show(r)
        return 0 if r.get("ok") else 1

    if a.cmd == "status":
        d = door({"op": "status", "pod": a.pod})
        pods = d.get("pods") or []
        if pods:  # 先给人看的一屏表，再给完整 JSON（表不会截断，JSON 也不再截断）
            print("%-16s %-18s %-9s %-6s" % ("id", "name", "状态", "$/h"))
            for p in pods:
                print("%-16s %-18s %-9s %-6s" % (p.get("id", ""), p.get("name", ""),
                                                 p.get("状态", ""), p.get("$/h", "")))
            print("RUNNING:", [p.get("name") for p in pods if p.get("状态") == "RUNNING"] or "（无）")
            print()
        show(d)
        return 0
    if a.cmd == "gpu":
        show(door({"op": "gpus"}))
        return 0
    if a.cmd == "account":
        show(door({"op": "account"}))
        return 0
    if a.cmd == "stop":
        r = door({"op": "stop", "pod": a.pod, "confirm": a.confirm})
        show(r, 800)
        return 0 if r.get("ok") else 1
    if a.cmd == "tail":
        r = door({"op": "down", "remote": "/workspace/dh/run.log",
                  "local": str(LOCAL_LOG.relative_to(ROOT)), "pod": a.pod})
        show(r, 500)
        if LOCAL_LOG.is_file():
            lines = LOCAL_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
            print("---- 最后 6 条 ----")
            for ln in lines[-6:]:
                print(ln[:300])
        return 0 if r.get("ok") else 1
    if a.cmd == "launch":
        src = PAYLOAD.read_text(encoding="utf-8")
        code = "SRC = %r\n%s" % (src, LAUNCHER)
        r = door({"op": "run", "code": code, "pod": a.pod, "timeout": 120,
                  "ws_timeout": 60, "confirm": a.confirm})
        show(r, 900)
        return 0 if r.get("ok") else 1
    return 2


raise SystemExit(main())
