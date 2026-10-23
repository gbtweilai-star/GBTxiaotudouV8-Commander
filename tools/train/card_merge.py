# v49 卡上合并薄壳（GBT小土豆V8）
# 🔴 2026-10-17 修（留痕 · 原口径 / 为什么翻 / 现口径）：
#   原薄壳：`nohup python -u /workspace/post_v26.py` —— 而 `post_v26.py` **全仓不存在**
#     （仓库里既没有它、launch/merge 也从没上传过它）⇒ 合并步骤是**幽灵步骤**，必失败。
#   现口径：launcher 先把仓内 `tools/train/merge_lora.py` 传成 `/workspace/_merge_src.txt`，
#     本壳写成 `/workspace/merge_lora.py`，再用 env 指定 BASE/LORA/OUT 真跑；
#     路径由 `GBT_CARD_WS` 可改（本地空跑校验用，默认 /workspace）。
import os
import pathlib
import subprocess

WS = pathlib.Path(os.environ.get("GBT_CARD_WS", "/workspace"))
SRC = WS / "_merge_src.txt"
SCRIPT = WS / "merge_lora.py"
BASE = WS / "gbt-v8"
LORA = WS / "lora_v60"
OUT = WS / "gbt-v8-v60"
LOG = WS / "merge_v60.log"

# 🔴 2026-10-17 省票改造（同 card_launch）：合并器内嵌 base64，不再单独占 upload 票。
EMBEDDED = "__GBT_MERGE_B64__"
if EMBEDDED and not EMBEDDED.startswith("__GBT_MERGE"):
    import base64 as _b64
    src = _b64.b64decode(EMBEDDED).decode("utf-8")
    SCRIPT.write_text(src, encoding="utf-8")
    print("merge script bytes(embedded)", len(src), flush=True)
elif SRC.is_file():
    SCRIPT.write_text(SRC.read_text(encoding="utf-8"), encoding="utf-8")
    print("merge script bytes(uploaded)", len(SCRIPT.read_text(encoding="utf-8")), flush=True)
else:
    raise SystemExit("缺合并器本体 %s（或由 merge 内嵌 base64）" % SRC)
if not LORA.is_dir():
    raise SystemExit("缺适配器目录 %s（先跑 launch 训出 lora_v60）" % LORA)
print("base", BASE, "| lora", LORA, "| out", OUT, "| log", LOG, flush=True)

subprocess.run(["bash", "-lc", "ps -eo pid,cmd | grep '[m]erge_lora.py' | grep -v bash | awk '{print \\$1}' | xargs -r kill; sleep 1"], capture_output=True, text=True)
env_prefix = 'MERGE_BASE="%s" MERGE_LORA="%s" MERGE_OUT="%s" ' % (BASE, LORA, OUT)
cmd = ("nohup bash -lc '" + env_prefix + "python -u " + str(SCRIPT) + "' > " + str(LOG) +
       " 2>&1 & echo $!")
p = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True)
print("MERGE_PID", (p.stdout or "").strip(), flush=True)
