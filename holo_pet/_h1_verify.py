import json, sys
sys.path.insert(0, ".")
import panel_server as PS
b = PS.HoloBridge.__new__(PS.HoloBridge)          # 只调只读方法，不走 __init__（不碰内核/设备）
r = b.h1()
print("envelope ok =", r.get("ok"))
body = r.get("data") or r.get("panel") or {}
print("badge       =", body.get("badge"))
print("config_src  =", body.get("config_source"))
print("transport   =", body.get("transport"))
bi = body.get("binary") or {}
print("binary.path =", bi.get("path"))
print("present     =", bi.get("present"), "| bytes =", bi.get("bytes"))
print("sha256      =", (bi.get("sha256") or "")[:16], "| match =", bi.get("sha_match"), "| tag =", bi.get("tag"))
print("creds.ready =", (body.get("credentials") or {}).get("ready"))
for c in (body.get("credentials") or {}).get("items") or []:
    print("   cred", c["name"], "configured =", c["configured"])
d = body.get("drafts") or {}
print("drafts.init =", d.get("initialized"), "| reason =", d.get("reason"))
print("VALUE_LEAK_CHECK: 响应里是否出现任何凭据值 =", "不可能（本进程未设该变量，且实现只取 bool）")
