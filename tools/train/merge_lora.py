# 卡上合并器（GBT小土豆V8）—— LoRA 适配器 → bf16 全量权重
# 语义：BASE（/workspace/gbt-v8）+ LORA（/workspace/lora_v49）→ MERGE_OUT（/workspace/gbt-v8-v49）
# 全部路径走 env（由 card_merge.py 传入），不写死代次。
import os
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE = os.environ.get("MERGE_BASE", "/workspace/gbt-v8")
LORA = os.environ.get("MERGE_LORA", "/workspace/lora_v49")
OUT = os.environ.get("MERGE_OUT", "/workspace/gbt-v8-v49")

print("merge base=%s lora=%s out=%s" % (BASE, LORA, OUT), flush=True)
tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.bfloat16,
                                             device_map="cpu", trust_remote_code=True)
model = PeftModel.from_pretrained(model, LORA)
merged = model.merge_and_unload()
merged.save_pretrained(OUT, safe_serialization=True)
tok.save_pretrained(OUT)
print("MERGE_DONE", OUT, flush=True)
