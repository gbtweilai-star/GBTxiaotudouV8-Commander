import json, os, hashlib, subprocess
def sh(c):
    return subprocess.run(["bash", "-lc", c], capture_output=True, text=True).stdout.strip()
o = {}
o["log_tail"] = sh("tail -c 300 /workspace/train_v26_pro.log 2>/dev/null | tr \"\n\" \" |\"")[-300:]
o["proc"] = sh("ps -eo pid,etime,cmd | grep -E \"train_v26|pip install\" | grep -v grep | head -2")[:200]
o["gpu"] = sh("nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader")[:60]
p = "/workspace/self_knowledge_v26.jsonl"
if os.path.exists(p):
    b = open(p, "rb").read()
    o["corpus"] = {"lines": b.count(b"\n"), "bytes": len(b), "sha256_16": hashlib.sha256(b).hexdigest()[:16]}
else:
    o["corpus"] = None
print(json.dumps(o, ensure_ascii=False))
