# -*- coding: utf-8 -*-
"""card_accept_all -- **卡上一发跑完全部验收套件**（主 54 + 6 族，串行、题库/答案文件各自独立）。

为什么要有它（2026-10-17 主人令「必须把细节做到位」）：
  逐族发射要 7 次 `process_execute` + 每次重载模型（~40s），票易过期、墙钟太长；
  但**并发跑**又会互踩同名文件（accept_infer.py / accept_q.json 固定路径）。
  ⇒ 本壳一次发射：把 accept_infer.py + 全部题库**内嵌**进 run(code=)（不占上传票），
    逐个族用**独立** Q/A 文件名串行执行，跑完打 `ACCEPT_ALL_DONE`。

占位符（由 train_ground.accept_all 替换为 base64）：
  __GBT_ACCEPT_INFER_B64__ : accept_infer.py 原文
  __GBT_BANKS_B64__        : {"<套件名>": ["<题库 jsonl 行>", ...], ...}
"""
import base64
import json
import os
import pathlib
import subprocess
import sys

WS = pathlib.Path(os.environ.get("GBT_CARD_WS", "/workspace"))
INFER = WS / "accept_infer.py"
INFER.write_bytes(base64.b64decode("__GBT_ACCEPT_INFER_B64__"))
print("infer bytes", INFER.stat().st_size, flush=True)

BANKS = json.loads(base64.b64decode("__GBT_BANKS_B64__").decode("utf-8"))
LORA = os.environ.get("GBT_ACCEPT_LORA", "/workspace/lora_v51")  # 由 train_ground.accept_all 按现役代次替换默认值
BASE = os.environ.get("GBT_ACCEPT_BASE", "/workspace/gbt-v8")
print("suites", list(BANKS), "| lora", LORA, flush=True)

for name, lines in BANKS.items():
    q = WS / ("q_%s.jsonl" % name)
    q.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # 2026-10-17 修：答案文件名按**适配器代次**自动取（不再写死 v51，避免跨代覆盖）
    _ver = LORA.rsplit("_v", 1)[-1] if "_v" in LORA else "run"
    a = WS / ("accept_a_%s_v%s.jsonl" % (name, _ver))
    env = dict(os.environ)
    env.update({"ACCEPT_BASE": BASE, "ACCEPT_LORA": LORA, "ACCEPT_Q": str(q), "ACCEPT_A": str(a)})
    print("SUITE_START", name, "| need", len(lines), flush=True)
    subprocess.run([sys.executable, "-u", str(INFER)], env=env, check=False)
    n = sum(1 for _ in a.open(encoding="utf-8")) if a.is_file() else 0
    print("SUITE_DONE", name, "| answers", n, flush=True)

print("ACCEPT_ALL_DONE", flush=True)
