#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""doctor —— 一条命令体检整套系统：哪一环活着、哪一环缺件。

为什么需要：今天做了太多东西（装置/素材/判据/出片/投屏/她的嘴），
换会话或隔天再看，说不清"现在到底哪里能用"。这里全部量一遍。

只读，不改任何东西。退出码：全绿 0，有红 1。
"""
import json, os, socket, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = []
FIX = "--fix" in sys.argv
ACTIONS = []


def heal():
    """--fix：只做**可逆且安全**的修复。删文件一律不自动做。"""
    # ① 桥不起就起
    if not up(8791):
        sh([os.path.join(ROOT, "tools", "ensure_bridge.sh")], timeout=60)
        if up(8791):
            ACTIONS.append("拉起模型桥 :8791")
    # ② 页面服务不起就起
    if not up(8080):
        subprocess.Popen([sys.executable, "-m", "http.server", "8080"],
                         cwd=os.path.join(ROOT, "holo_pet_w3"),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        for _ in range(20):
            import time as _t
            _t.sleep(0.3)
            if up(8080):
                ACTIONS.append("拉起页面服务 :8080")
                break
    # ③ 素材缺指纹就补
    try:
        r = sh([sys.executable, os.path.join(ROOT, "tools", "ingest.py"), "--backfill"])
        if "回填" in r.stdout and "回填 0 条" not in r.stdout:
            ACTIONS.append(r.stdout.strip().splitlines()[-1])
    except Exception:                                             # noqa: BLE001
        pass


def add(name, ok, detail=""):
    rows.append((name, bool(ok), str(detail)[:70]))


def up(port, t=0.6):
    s = socket.socket(); s.settimeout(t)
    try: s.connect(("127.0.0.1", port)); return True
    except Exception: return False
    finally: s.close()


def sh(cmd, cwd=None, timeout=60):
    return subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True,
                          text=True, timeout=timeout, cwd=cwd)


if FIX:
    heal()

# ① 运行时
add("容器 A19 :1234", up(1234), "UP" if up(1234) else "DOWN（需 LM Pocket 点一次）")
add("模型桥 :8791", up(8791), "UP" if up(8791) else "DOWN（ensure_bridge.sh 可拉起）")
add("页面服务 :8080", up(8080), "UP" if up(8080) else "DOWN（gbt beam 会拉起）")

# ② 装置页面
p = os.path.join(ROOT, "holo_pet_w3", "kaleido", "v8.html")
add("视觉装置 v8", os.path.exists(p), "%.1f KB" % (os.path.getsize(p) / 1024) if os.path.exists(p) else "缺")

# ③ 素材库
A = "/var/minis/attachments/assets"
MP = os.path.join(A, "manifest.json")
try:
    man = json.load(open(MP, encoding="utf-8"))
    have = set(os.listdir(A)) - {"manifest.json"}
    reg = {e.get("file") for e in man}
    orph, lost = have - reg, reg - have
    nohash = [e["file"] for e in man if not e.get("sha256")]
    add("素材台账", not (orph or lost or nohash),
        "%d 条 · 孤儿 %d · 缺失 %d · 缺指纹 %d" % (len(man), len(orph), len(lost), len(nohash)))
except Exception as exc:                                          # noqa: BLE001
    add("素材台账", False, "%s" % exc)

# ④ 判据（拿一张图跑）
sample = os.path.join(ROOT, "holo_pet_w3", "kaleido", "v8.html")
img = "/var/minis/attachments/tz_P1.jpg"
if os.path.exists(img):
    r = sh([sys.executable, os.path.join(ROOT, "tools", "taste_gate.py"),
            "--judge", img, "--profile", "photo"])
    add("品味判据", "判定" in r.stdout,
        [l for l in r.stdout.splitlines() if l.startswith("判定")][:1] or "无输出")
else:
    add("品味判据", False, "样图不在")

# ⑤ 人格与内核
for f, name in (("state/her_persona_lite.txt", "人格精简版"),
                ("state/taste_kernel.txt", "品味内核")):
    fp = os.path.join(ROOT, f)
    add(name, os.path.exists(fp),
        "%d 字" % len(open(fp, encoding="utf-8").read()) if os.path.exists(fp) else "缺")

# ⑥ 文档与原生工程
docs = len([f for f in os.listdir(os.path.join(ROOT, "docs")) if f.endswith(".md")])
add("文档", docs >= 30, "%d 份" % docs)
ios = os.path.join(ROOT, "ios", "SpaceBeamLite", "Sources")
swift = len([f for f in os.listdir(ios) if f.endswith(".swift")]) if os.path.isdir(ios) else 0
metal = len([f for f in os.listdir(ios) if f.endswith(".metal")]) if os.path.isdir(ios) else 0
add("原生工程源码", swift >= 5 and metal >= 1, "%d swift + %d metal" % (swift, metal))

# ⑦ 演示包（有就校验，没有就标待办）
import glob as _g
packs = sorted(_g.glob(os.path.join(ROOT, "dist", "demo-*")))
if packs:
    latest = max(packs, key=os.path.getmtime)
    r = sh([sys.executable, os.path.join(ROOT, "tools", "pack.py"), "--verify", latest])
    add("演示包", "判定 PASS" in r.stdout,
        "%s · %s" % (os.path.basename(latest),
                     "校验通过" if "判定 PASS" in r.stdout else "校验未过"))
else:
    add("演示包", False, "还没有（gbt pack 打一个）")

# ⑧ 工具入口
add("gbt 入口", os.path.exists("/usr/local/bin/gbt"), "已安装" if os.path.exists("/usr/local/bin/gbt") else "缺")

ok = sum(1 for r in rows if r[1])
print("%-18s %-5s %s" % ("检查项", "结果", "读数"))
print("-" * 76)
for n, good, d in rows:
    print("%-18s %-5s %s" % (n, "OK" if good else "FAIL", d))
print("-" * 76)
if FIX and ACTIONS:
    print("自愈  " + "；".join(ACTIONS))
elif FIX:
    print("自愈  没有需要修的（或修不了）")
print("合计 %d · 通过 %d · 未通 %d" % (len(rows), ok, len(rows) - ok))
return_code = 0 if ok == len(rows) else 1
sys.exit(return_code)
