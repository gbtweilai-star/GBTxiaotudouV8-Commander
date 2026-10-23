# v49 卡上薄壳（GBT小土豆V8）—— 读已上传的训练脚本体 + 锁版 pip + QLoRA 点火
# 🔴 2026-10-17 修（留痕 · 原口径 / 为什么翻 / 现口径）：
#   原薄壳：读 `/workspace/_v26_src.txt`（**launch 侧从没上传过它** ⇒ 必 FileNotFound），
#     且直接 `python -u train_v26_qlora.py` **不带任何 env** ⇒ 训练脚本回落默认
#     `V26_CORPUS=/workspace/self_knowledge_v26.jsonl` ⇒ 「点火了却拿 v26 数据训 v49」。
#   现口径：脚本体路径 / 语料 / 输出目录都由本壳显式定成 v49，并以 env 传给训练脚本；
#     `GBT_CARD_WS` 只为本地空跑校验用（默认 /workspace，不影响卡上行为）。
import os
import pathlib
import subprocess

WS = pathlib.Path(os.environ.get("GBT_CARD_WS", "/workspace"))
SRC = WS / "_train_src.txt"
TRAINER = WS / "train_qlora.py"
DATA = WS / "self_knowledge_v60.jsonl"
OUT = WS / "lora_v60"
LOG = WS / "train_v60.log"

# 🔴 2026-10-17 省票改造（留痕）：`data_export` 是**一次性**的，而每次 `up` 吃一张。
#   ⇒ 训练脚本体**内嵌进本壳代码**（launch 侧把占位符替换成 base64 源码），
#   这样点火只需**上传语料**这一张票；脚本体不再单独 `up`。
EMBEDDED = "__GBT_TRAINER_B64__"
if EMBEDDED and not EMBEDDED.startswith("__GBT_TRAINER"):
    import base64 as _b64
    src = _b64.b64decode(EMBEDDED).decode("utf-8")
    TRAINER.write_text(src, encoding="utf-8")
    print("train script bytes(embedded)", len(src), flush=True)
elif SRC.is_file():
    src = SRC.read_text(encoding="utf-8")
    TRAINER.write_text(src, encoding="utf-8")
    print("train script bytes(uploaded)", len(src), flush=True)
else:
    raise SystemExit("缺训练脚本体 %s（或由 launch 内嵌 base64）" % SRC)
if not DATA.is_file():
    raise SystemExit("缺语料 %s（launch 必须先 up self_knowledge_v60.jsonl）" % DATA)
print("data", DATA, "| out", OUT, "| log", LOG, flush=True)

subprocess.run(["bash", "-lc", "ps -eo pid,cmd | grep '[t]rain_qlora.py' | grep -v bash | awk '{print \\$1}' | xargs -r kill; sleep 3"], capture_output=True, text=True)
env_prefix = 'V26_CORPUS="%s" V26_OUT="%s" V26_SMOKE="${V26_SMOKE:-0}" ' % (DATA, OUT)
cmd = ("nohup bash -lc 'pip install -q \"transformers==4.46.3\" \"peft==0.13.2\" "
       "bitsandbytes datasets accelerate && " + env_prefix + "python -u " + str(TRAINER) +
       "' > " + str(LOG) + " 2>&1 & echo $!")
p = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True)
print("PID", (p.stdout or "").strip(), flush=True)
