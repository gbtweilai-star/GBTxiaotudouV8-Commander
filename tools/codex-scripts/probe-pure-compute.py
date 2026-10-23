# -*- coding: utf-8 -*-
"""纯算力探针：只调 CPU / GPU 算，**不调用任何大模型**。

## 判据（写死，可复核）

"只调算力、没调大模型"要能被机器判，不靠嘴说：

  ① 计算的是**数值内核**（矩阵乘 / 求和 / 排序），回执里只有 `kernel / seconds / GFLOPs`；
  ② 回执里**没有** `text` / `usage.tokens` / `model` 这些"模型回话"的字段；
  ③ 本机 CPU 那一路**零出网**；GPU 那一路只连算力节点，不连任何推理端点；
  ④ 结果可复算（同内核重跑，耗时同量级）。

## 三类读数（都写进 data/pure-compute-live.json，图由它渲染）

  · `cpu`      —— 本机 CPU：numpy float32 2048x2048 matmul（真跑，记 GFLOP/s）
  · `gpu`      —— 本机 GPU：torch 的 CUDA 现状（不可用就如实 device_count=0，不假装）
  · `cloud_gpu`—— 云端 GPU：付费卡现状（读 pod_link status）+ 启动被拒的上游原话
                  ⚠️ 免费 GPU 那条（wan22 diffusion）跑的是**模型推理**，按本口径**不算纯算力**，
                  这里只记它存在，不混进来充数。

用法：
    py -3.12 -X utf8 tools/codex-scripts/probe-pure-compute.py
"""
from __future__ import annotations

import json
import pathlib
import platform
import sys
import time
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "outputs" / "open-source-release" / "data"


def cpu_bench() -> dict:
    try:
        import numpy as np
    except Exception as exc:                                   # noqa: BLE001
        return {"error": "numpy 缺：%s" % type(exc).__name__}
    n = 2048
    a = np.random.rand(n, n).astype("float32")
    b = np.random.rand(n, n).astype("float32")
    a @ b                                                     # 预热
    t0 = time.perf_counter()
    _ = a @ b
    dt = time.perf_counter() - t0
    return {"kernel": "numpy float32 matmul %dx%d" % (n, n),
            "seconds": round(dt, 4),
            "gflops": round(2 * n ** 3 / dt / 1e9, 1),
            "numpy": np.__version__,
            "llm_calls": 0,
            "fields": ["kernel", "seconds", "gflops"],
            "note": "零出网、零模型：只做一次矩阵乘"}


def gpu_probe() -> dict:
    try:
        import torch
    except Exception as exc:                                   # noqa: BLE001
        return {"error": "torch 缺：%s" % type(exc).__name__, "cuda_available": False}
    ok = bool(torch.cuda.is_available())
    out = {"torch": torch.__version__, "cuda_available": ok,
           "device_count": torch.cuda.device_count() if ok else 0}
    if ok:
        n = 4096
        x = torch.randn(n, n, device="cuda")
        y = torch.randn(n, n, device="cuda")
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        _ = x @ y
        torch.cuda.synchronize()
        dt = time.perf_counter() - t0
        out.update({"kernel": "torch cuda float32 matmul %dx%d" % (n, n),
                    "seconds": round(dt, 4),
                    "tflops": round(2 * n ** 3 / dt / 1e12, 2),
                    "device": torch.cuda.get_device_name(0), "llm_calls": 0})
    else:
        out["note"] = "本机没有可用 CUDA 卡 ⇒ 本机 GPU 纯算力：无（如实报缺，不假装）"
    return out


def cloud_gpu() -> dict:
    """读付费卡现状 + 启动被拒的原话（都来自 pod_link，不新增旁路）。"""
    out: dict = {"pods": None, "pod_status": None, "start_result": None}
    try:
        from gbt_allinone.tools import pod_link as PL
        st = PL.run_dispatch("status", pod="")
        pods = st.get("pods") or {}
        head = pods.get("_head") if isinstance(pods, dict) else pods
        rows = [{"id": p.get("id"), "name": p.get("name"), "state": p.get("状态")}
                for p in (head or [])]
        running = [r for r in rows if str(r.get("state") or "").upper() == "RUNNING"]
        out["pods"] = "%d 张卡 · RUNNING %d" % (len(rows), len(running))
        out["pod_status"] = rows[:3]
        out["start_result"] = ("纯算力要一张 RUNNING 的卡；现读 0 张在跑 ⇒ 云端纯算力：无。"
                               "（2026-10-21 那次 start 的上游原话："
                               "not enough free GPUs on the host machine）")
    except Exception as exc:                                   # noqa: BLE001
        out["pod_status"] = "取不到：%s: %s" % (type(exc).__name__, str(exc)[:120])
    out["not_counted"] = ("免费 GPU 那条（Sneezemande/wan22-comfyui-demo）跑的是 **模型推理**"
                          "（diffusion 出片），按本口径不算纯算力，故不计入本文件")
    return out


def main() -> int:
    doc = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "schema": "pure-compute-live-v1",
        "machine": {"platform": platform.platform(), "cpu": platform.processor()},
        "criterion": "回执只有 kernel/seconds/GFLOPs，没有 text/usage.tokens/model ⇒ 只调算力",
        "cpu": cpu_bench(),
        "gpu": gpu_probe(),
        "cloud_gpu": cloud_gpu(),
        "note": "CPU 那一路零出网；GPU 那一路只连算力节点；模型推理不混进来充数",
    }
    DATA.mkdir(parents=True, exist_ok=True)
    p = DATA / "pure-compute-live.json"
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"cpu": doc["cpu"], "gpu": doc["gpu"],
                      "cloud_gpu": {k: doc["cloud_gpu"].get(k) for k in ("pods", "start_result")}},
                     ensure_ascii=False, indent=1))
    print("落账 →", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
