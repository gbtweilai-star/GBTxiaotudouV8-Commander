# v26 专业训练脚本（GBT小土豆V8）—— 装箱 + 验证集 + eval
import json, os, random, torch
from datasets import Dataset
from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                          TrainingArguments, Trainer, DataCollatorForLanguageModeling)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
SEED = 1337
BLOCK = 512
random.seed(SEED)
torch.manual_seed(SEED)
BASE = "/workspace/gbt-v8"
CORPUS = os.environ.get("V26_CORPUS", "/workspace/self_knowledge_v26.jsonl")
# 🔴 2026-10-17 参数化输出目录（留痕）：原来是写死 `/workspace/lora_v26` ⇒ v49 点火会**覆盖 v26 适配器**。
#    现口径：`V26_OUT` 由卡上薄壳按代次传入（v49 → /workspace/lora_v49），不传才回落 v26。
OUT = os.environ.get("V26_OUT", "/workspace/lora_v26")
rows = [json.loads(l) for l in open(CORPUS, encoding="utf-8") if l.strip()]
random.shuffle(rows)
n_val = max(32, int(len(rows) * 0.05))
val_rows, tr_rows = rows[:n_val], rows[n_val:]
tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token
# 峰值显存打印（供 round-compact C1 取真读数）
def _peak_gb():
    try:
        import torch as _t
        return round(_t.cuda.max_memory_allocated() / 1024 ** 3, 2)
    except Exception:
        return -1

def to_text(r):
    ins = (r.get("instruction") or "").strip()
    inp = (r.get("input") or "").strip()
    out = (r.get("output") or "").strip()
    user = ins if not inp else ins + chr(10) + inp
    return "<|im_start|>user" + chr(10) + user + "<|im_end|>" + chr(10) + "<|im_start|>assistant" + chr(10) + out + "<|im_end|>"
eos = tok.eos_token_id
def pack(texts, block=BLOCK):
    ids = []
    for t in texts:
        ids.extend(tok(t, add_special_tokens=False)["input_ids"])
        ids.append(eos)
    chunks = [ids[i:i + block] for i in range(0, len(ids), block)]
    chunks = [c for c in chunks if len(c) >= 64]
    return chunks
def ds_of(chunks):
    # 2026-10-16 修：定长 512 补齐 + 正确掩码（原来允许变长块 ⇒ tokenizer.pad 报"长度不齐/类型嵌套"，v28 训练崩在 step 98）
    ids, am, lb = [], [], []
    for c in chunks:
        c = list(c)[:BLOCK]
        pad = BLOCK - len(c)
        ids.append(c + [eos] * pad)
        am.append([1] * len(c) + [0] * pad)
        lb.append(c + [-100] * pad)
    return Dataset.from_dict({"input_ids": ids, "attention_mask": am, "labels": lb})


tr_chunks = pack([to_text(r) for r in tr_rows])
va_chunks = pack([to_text(r) for r in val_rows])
print("corpus %d | train %d | val %d | packed train %d | packed val %d | block %d"
      % (len(rows), len(tr_rows), len(val_rows), len(tr_chunks), len(va_chunks), BLOCK), flush=True)
tr_ds = ds_of(tr_chunks)
va_ds = ds_of(va_chunks)
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16)
print("loading base", flush=True)
model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb, device_map="auto", trust_remote_code=True)
model = prepare_model_for_kbit_training(model)
model.config.use_cache = False
lora = LoraConfig(r=32, lora_alpha=64, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                  target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
model = get_peft_model(model, lora)
model.print_trainable_parameters()
SMOKE = os.environ.get("V26_SMOKE") == "1"
print("SMOKE", SMOKE, flush=True)
kw = {"max_steps": 2} if SMOKE else {}   # 只给 max_steps；再给 num_train_epochs 会与显式参数撞车
args = TrainingArguments(output_dir=OUT, per_device_train_batch_size=1, gradient_accumulation_steps=4,
                         num_train_epochs=3, learning_rate=2e-4, lr_scheduler_type="cosine",
                         warmup_steps=20, bf16=True, logging_steps=5, eval_strategy="epoch",
                         save_strategy="no", report_to=[], seed=SEED, dataloader_num_workers=2,
                         optim="paged_adamw_8bit", gradient_checkpointing=True, **kw)
coll = DataCollatorForLanguageModeling(tokenizer=tok, mlm=False)
tr = Trainer(model=model, args=args, train_dataset=tr_ds, eval_dataset=va_ds, data_collator=coll)
tr.train()
print("EVAL", tr.evaluate(), flush=True)
tr.save_model(OUT)
tok.save_pretrained(OUT)
print("DONE", OUT, flush=True)

print("TRAIN_DONE peak_vram_gb=%s" % _peak_gb(), flush=True)
