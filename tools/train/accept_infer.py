# 卡上验收推理（省显存版）：底座 + LoRA -> 逐题生成 -> answers.jsonl
# 2026-10-16：low_cpu_mem_usage + SDPA + OOM 自动降级 4bit + 显存读数
#           + JSON/工作流题给 1200 token（图 JSON 会被 200 token 截断）
import gc, json, os, torch
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

BASE = os.environ.get("ACCEPT_BASE", "/workspace/gbt-v8")
LORA = os.environ.get("ACCEPT_LORA", "/workspace/lora_v26")
Q = os.environ.get("ACCEPT_Q", "/workspace/accept_q.jsonl")
A = os.environ.get("ACCEPT_A", "/workspace/accept_a.jsonl")
PREFIX = os.environ.get("ACCEPT_PREFIX", "")   # 2026-10-17 族路由注入：推理侧防串族

tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)


def load(mode):
    if mode == "4bit":
        bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                 bnb_4bit_compute_dtype=torch.bfloat16)
        m = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb, device_map="auto",
                                                 low_cpu_mem_usage=True, attn_implementation="sdpa",
                                                 trust_remote_code=True)
        return m, PeftModel.from_pretrained(m, LORA)
    m = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.bfloat16, device_map="auto",
                                             low_cpu_mem_usage=True, attn_implementation="sdpa",
                                             trust_remote_code=True)
    m = PeftModel.from_pretrained(m, LORA)
    return m, m.merge_and_unload()


MODE = os.environ.get("ACCEPT_MODE", "bf16")
try:
    m, model = load(MODE)
except torch.OutOfMemoryError:
    print("OOM on", MODE, "-> fallback 4bit", flush=True)
    gc.collect(); torch.cuda.empty_cache()
    MODE = "4bit"
    m, model = load(MODE)
model.eval()
print("MODE", MODE, "| max_mem_alloc GB", round(torch.cuda.max_memory_allocated() / 1024 ** 3, 2), flush=True)

qs = [json.loads(l) for l in open(Q, encoding="utf-8") if l.strip()]
f = open(A, "w", encoding="utf-8")
print("questions", len(qs), flush=True)
for i, it in enumerate(qs):
    q = it["q"]
    if "能力位" in q or "有哪些能力" in q:
        ntok = 700
    elif "JSON" in q or "工作流" in q or "节点" in q:
        ntok = 1200
    else:
        ntok = 220
    p = "<|im_start|>user" + chr(10) + ((PREFIX + chr(10)) if PREFIX else "") + q + "<|im_end|>" + chr(10) + "<|im_start|>assistant" + chr(10)
    ids = tok(p, return_tensors="pt").to(model.device)
    with torch.no_grad():
        g = model.generate(**ids, max_new_tokens=ntok, do_sample=False, pad_token_id=tok.eos_token_id)
    a = tok.decode(g[0][ids["input_ids"].shape[1]:], skip_special_tokens=True).strip()
    f.write(json.dumps({"group": it.get("group", ""), "q": q, "a": a}, ensure_ascii=False) + chr(10))
    f.flush()
    del g, ids
    if i % 10 == 0:
        torch.cuda.empty_cache()
        print(i, "=>", a[:50].replace(chr(10), " "), "| peak GB", round(torch.cuda.max_memory_allocated() / 1024 ** 3, 2), flush=True)
    else:
        print(i, "=>", a[:60].replace(chr(10), " "), flush=True)
print("DONE peak GB", round(torch.cuda.max_memory_allocated() / 1024 ** 3, 2), flush=True)
