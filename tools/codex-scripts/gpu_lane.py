# -*- coding: utf-8 -*-
"""组1「自研模型底座」车道管理器（主人 2026-10-04 蓝图图4：Ninfer 式专用引擎 + 单卡 RTX 5090）。

## 为什么有它
主人令：「5090 硬件必须触手自行完成」。**买卡/插卡是物理动作**，软件执行不了（这不是挑活，是物理边界）；
但围绕它的**全部可执行部分**由本件承担，做到"卡一到就一条命令上线"：
  · `status`：现读三层事实 —— ① 本机有没有 NVIDIA 卡（nvidia-smi / wmic）② 有没有可用的
    **自持/专用端点**（LLM_ENDPOINT / UNCENSORED_ENDPOINT / 本机回环若干口）③ 远端可用的
    算力车道（NVIDIA NIM，钥匙走环境变量）—— **逐层如实报，缺哪层说哪层**；
  · `plan`  ：出「卡到位后的落地清单」（引擎选型/量化档/端口/切换命令/验收判据），只打印不写盘；
  · `set`   ：把组1 车道**切到指定端点**（写用户环境变量 GBT_POTATO_BASE_URL/MODEL + 同步
    CLIProxyAPI 车道的 base-url）—— 这是"一条命令上线"的那条命令。

## 红线
  · 密钥只从环境变量来（本件只读环境变量名，不打印值）；
  · `set` 只改**用户环境变量**与 cliproxy 配置（应用数据区），不进仓、不写源码；
  · 拿不到的事实（无卡、未装引擎）**如实报缺**，不编「已就绪」。

用法：
    py -3.14 tools/codex-scripts/gpu_lane.py status
    py -3.14 tools/codex-scripts/gpu_lane.py plan
    py -3.14 tools/codex-scripts/gpu_lane.py set --base-url http://127.0.0.1:8000/v1 --model qwen3.8-27b

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APPDIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "gbt-cliproxy"
LOCAL_CANDIDATES = [("127.0.0.1", 8000, "vLLM/SGLang 常用口"),
                    ("127.0.0.1", 8111, "旧假端点口（历史）"),
                    ("127.0.0.1", 11434, "Ollama 口")]
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def local_gpus() -> dict:
    """本机 NVIDIA 卡：nvidia-smi 优先，退 wmic；都没有就如实说没有。"""
    out = {"nvidia_smi": False, "cards": [], "note": ""}
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                           capture_output=True, text=True, encoding="mbcs", errors="replace", timeout=20)
        if r.returncode == 0 and (r.stdout or "").strip():
            out["nvidia_smi"] = True
            out["cards"] = [x.strip() for x in r.stdout.strip().splitlines() if x.strip()]
            return out
    except Exception:                                          # noqa: BLE001
        pass
    try:
        r = subprocess.run(["wmic", "path", "win32_VideoController", "get", "name"],
                           capture_output=True, text=True, encoding="mbcs", errors="replace", timeout=25)
        names = [x.strip() for x in (r.stdout or "").splitlines()[1:] if x.strip()]
        out["cards"] = names
        out["note"] = "wmic 列的是显示控制器（含集显）；NVIDIA 专用推理卡以 nvidia-smi 为准"
    except Exception as exc:                                   # noqa: BLE001
        out["note"] = "两路都读不到：" + str(exc)[:80]
    return out


def probe_port(host: str, port: int) -> bool:
    if host not in LOOPBACK:                                   # 只探回环（红线）
        return False
    try:
        with socket.create_connection((host, port), timeout=0.6):
            return True
    except Exception:                                          # noqa: BLE001
        return False


def cmd_status(_a) -> int:
    g = local_gpus()
    print("① 本机算力：")
    print("   nvidia-smi 可用:", g["nvidia_smi"], "| 卡:", g["cards"] or "（无 NVIDIA 卡）")
    if g["note"]:
        print("   ", g["note"])
    print("② 自持/专用端点（环境变量 + 本机回环）：")
    for name in ("LLM_ENDPOINT", "UNCENSORED_ENDPOINT", "IMAGE_ENDPOINT", "GBT_POTATO_BASE_URL"):
        v = (os.environ.get(name) or "").strip()
        print("   %-22s %s" % (name, ("已设：" + v[:48]) if v else "未设"))
    for host, port, why in LOCAL_CANDIDATES:
        print("   回环 %s:%d（%s）→ %s" % (host, port, why, "在听" if probe_port(host, port) else "未听"))
    print("③ 远端算力车道（钥匙只报有无）：")
    for name in ("NVIDIA_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
        has = bool((os.environ.get(name) or "").strip())
        print("   %-18s %s" % (name, "有（形状 %s****）" % os.environ[name][:4] if has else "无"))
    return 0


def cmd_plan(_a) -> int:
    print("组1「自研模型底座」卡到位后的落地清单（照抄执行）：")
    print("""
  1) 引擎（图4 同款思路：从零写的专用推理引擎，只服务自家几个检查点）
       · 首选：Ninfer/vLLM/SGLang 任一 OpenAI 兼容服务；显存 ≥24GB 量化后方可跑 27B 级
       · 量化档：Q4_K_M（省显存首选）→ Q8_0（画质/推理优先）；ppl 回归留判据
  2) 起服务（示例，端口 8000）：
       vllm serve <自家检查点> --port 8000 --max-model-len 32768
  3) 一条命令上线（把组1 车道切到它）：
       py -3.14 tools/codex-scripts/gpu_lane.py set --base-url http://127.0.0.1:8000/v1 --model <模型名>
  4) 验收（三条，缺一不可）：
       · curl http://127.0.0.1:8000/v1/models 回自家模型名
       · py -3.14 tools/codex-scripts/cliproxy.py probe --model <模型名> 回 200
       · 云端 /slots50 里 group1 的 wired 数不变（车道是本机侧，不动云端）
  5) 无卡期间可用的**真算力**（今天就能跑，如实标"权重不是我们的"）：
       · NVIDIA NIM 车道已在统一链里（nvidia-glm / nvidia-flash），钥匙走 NVIDIA_API_KEY
  一句话：**卡是物理件，软件只能做到"卡一到就一条命令上线"**；上面 5 步之外没有软件可省的事。
""")


def cmd_set(a) -> int:
    base = (a.base_url or "").strip().rstrip("/")
    model = (a.model or "").strip()
    if not base or not model:
        print("🔴 要 --base-url 与 --model")
        return 2
    parts = urllib.parse.urlsplit(base)
    if parts.scheme not in ("http", "https"):
        print("🔴 只接受 http/https")
        return 2
    if parts.hostname not in LOOPBACK and a.allow_remote is not True:
        print("🔴 远端端点要显式 --allow-remote（默认只切本机端点）：%s" % parts.hostname)
        return 2
    if os.name == "nt":
        for k, v in (("GBT_POTATO_BASE_URL", base), ("GBT_POTATO_MODEL", model)):
            r = subprocess.run(["setx", k, v], capture_output=True, text=True,
                               encoding="mbcs", errors="replace", timeout=20)
            print("setx %s → %s" % (k, "ok" if r.returncode == 0 else (r.stderr or "")[:80]))
    print("已切组1 车道 → %s（模型 %s）。**新开的框架进程**生效；当前进程请重启终端。" % (base, model))
    print("同步路由器车道：CLIProxyAPI 重启后按新 base-url 出车道（cliproxy.cmd up）")
    return 0


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                      # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="组1 自研模型底座车道管理")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("plan").set_defaults(fn=cmd_plan)
    s = sub.add_parser("set")
    s.add_argument("--base-url", required=True)
    s.add_argument("--model", required=True)
    s.add_argument("--allow-remote", action="store_true", help="显式允许切到非回环端点")
    s.set_defaults(fn=cmd_set)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
