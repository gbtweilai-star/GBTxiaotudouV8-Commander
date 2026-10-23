import os, sys, time, json
os.environ.setdefault("HF_HUB_OFFLINE", "1")
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MD = r"state\weights\gbt-v8-v82-stream"
OFF = r"state\weights\_offload"
os.makedirs(OFF, exist_ok=True)
print("可用内存(GB):", round(__import__("psutil").virtual_memory().available/1024**3, 2) if __import__("importlib").util.find_spec("psutil") else "psutil缺失", flush=True)
print("→ 按需激活：max_memory 限 2.2GB 常驻，其余层离芯（offload_folder）", flush=True)
t0 = time.time()
tok = AutoTokenizer.from_pretrained(MD, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    MD, trust_remote_code=True,
    device_map="auto",                         # 让 accelerate 排层
    max_memory={0: "0GiB", "cpu": "2200MiB"},  # 只许 2.2GB 常驻 ⇒ 其余落盘、逐层激活
    offload_folder=OFF,
    low_cpu_mem_usage=True,
)
model.eval()
print("加载完成 %.1fs" % (time.time() - t0), flush=True)
try:
    print("device_map 分布:", json.dumps({k: str(v) for k, v in list(model.hf_device_map.items())[:6]}, ensure_ascii=False), flush=True)
except Exception as e:
    print("device_map 读不到:", e, flush=True)

txt = tok.apply_chat_template([{"role": "user", "content": "只回三个字：我到了"}], tokenize=False, add_generation_prompt=True)
ids = tok(txt, return_tensors="pt")
t1 = time.time()
with torch.no_grad():
    out = model.generate(**ids, max_new_tokens=8, do_sample=False, pad_token_id=tok.eos_token_id)
dt = time.time() - t1
ans = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
print("生成耗时 %.1fs · 新 token %d · 约 %.2f tok/s" % (dt, out.shape[1]-ids["input_ids"].shape[1], (out.shape[1]-ids["input_ids"].shape[1])/max(dt,1e-6)), flush=True)
print("回答:", repr(ans)[:120], flush=True)
