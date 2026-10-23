# v49 卡上验收薄壳（GBT小土豆V8）—— 底座 + LoRA → 逐题生成 answers.jsonl
# 路径全走 env；本壳只负责把仓内 accept_infer.py 落成卡上文件并带 env 起跑。
import os
import pathlib
import subprocess

WS = pathlib.Path(os.environ.get("GBT_CARD_WS", "/workspace"))
SRC = WS / "_accept_src.txt"
SCRIPT = WS / "accept_infer.py"
Q = WS / "accept_q.json"
A = WS / "accept_a_v60.jsonl"
LOG = WS / "accept_v49.log"
BASE = WS / "gbt-v8"
LORA = pathlib.Path(os.environ.get("ACCEPT_LORA", str(WS / "lora_v60")))

# 🔴 2026-10-17 省票改造（同 card_launch）：**验收器 + 题库都内嵌 base64**，
#   验收阶段不再单独占 upload 票（data_export 是一次性）。
EMB_SCRIPT = "__GBT_ACCEPT_SRC_B64__"
EMB_Q = "__GBT_ACCEPT_Q_B64__"
if EMB_SCRIPT and not EMB_SCRIPT.startswith("__GBT_ACCEPT_SRC"):
    import base64 as _b64
    src = _b64.b64decode(EMB_SCRIPT).decode("utf-8")
    SCRIPT.write_text(src, encoding="utf-8")
    print("accept script bytes(embedded)", len(src), flush=True)
elif SRC.is_file():
    SCRIPT.write_text(SRC.read_text(encoding="utf-8"), encoding="utf-8")
    print("accept script bytes(uploaded)", len(SCRIPT.read_text(encoding="utf-8")), flush=True)
else:
    raise SystemExit("缺验收器本体 %s（或由 accept 内嵌 base64）" % SRC)
if EMB_Q and not EMB_Q.startswith("__GBT_ACCEPT_Q"):
    import base64 as _b64
    Q.write_text(_b64.b64decode(EMB_Q).decode("utf-8"), encoding="utf-8")
    print("accept q bytes(embedded)", Q.stat().st_size, flush=True)
elif not Q.is_file():
    raise SystemExit("缺题库 %s（或由 accept 内嵌 base64）" % Q)
if not LORA.is_dir():
    raise SystemExit("缺适配器目录 %s（先跑 launch）" % LORA)
print("base", BASE, "| lora", LORA, "| q", Q, "| a", A, "| log", LOG, flush=True)

subprocess.run(["bash", "-lc", "ps -eo pid,cmd | grep '[a]ccept_infer.py' | grep -v bash | awk '{print \\$1}' | xargs -r kill; sleep 1"], capture_output=True, text=True)
env_prefix = ('ACCEPT_BASE="%s" ACCEPT_LORA="%s" ACCEPT_Q="%s" ACCEPT_A="%s" '
              % (BASE, LORA, Q, A))
cmd = ("nohup bash -lc '" + env_prefix + "python -u " + str(SCRIPT) + "' > " + str(LOG) +
       " 2>&1 & echo $!")
p = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True)
print("ACCEPT_PID", (p.stdout or "").strip(), flush=True)
