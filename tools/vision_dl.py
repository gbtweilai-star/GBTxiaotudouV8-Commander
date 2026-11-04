import os,sys,time,urllib.request,ssl
D=r"C:\Users\Lenovo E14 Gen 5\Desktop\GBT小土豆V8桌面版\payload\state\vision"
os.makedirs(D,exist_ok=True)
B="https://huggingface.co/unsloth/Qwen2.5-VL-3B-Instruct-GGUF/resolve/main"
def get(name):
    url=B+"/"+name; dst=os.path.join(D,name)
    pos=os.path.getsize(dst) if os.path.exists(dst) else 0
    req=urllib.request.Request(url, headers={"Range":"bytes=%d-"%pos} if pos else {})
    try:
        with urllib.request.urlopen(req,timeout=120) as r:
            mode="ab" if pos and r.status==206 else "wb"
            with open(dst,mode) as f:
                got=pos
                while True:
                    b=r.read(1024*1024)
                    if not b: break
                    f.write(b); got+=len(b)
                    if got//(50*1024*1024)!=(got-len(b))//(50*1024*1024):
                        print(name, round(got/1e6,1),"MB",flush=True)
    except Exception as e:
        print("ERR",name,repr(e),flush=True); return False
    return True
for n in ("Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf","mmproj-F16.gguf"):
    print("start",n,flush=True)
    if not get(n): print("FAILED",n,flush=True); sys.exit(1)
print("DONE",flush=True)
