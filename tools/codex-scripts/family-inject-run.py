# -*- coding: utf-8 -*-
"""family-inject-run -- 族路由注入实验的完整跑手。
流程：建卡(/复用) -> 传件(infer/pfx×3/chain.sh) -> 点火 -> **轮询到取齐** -> 族判别 -> 关卡。
纪律：命令链走卡上 .sh（代码纯 ASCII）；口令落盘；**未取齐不关卡**。
用法：py -3.14 tools/codex-scripts/family-inject-run.py [--reuse] [--poll 8]
"""
from __future__ import annotations
import argparse, json, os, secrets, ssl, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
PFX = {"offense_q": ("自主渗透编排", "offense_ops"), "spider_q": ("自适应抓取", "spider_ops"),
       "sc_q": ("作品解剖展示", "showcase_ops")}
NEED = {"offense_q": 9, "spider_q": 7, "sc_q": 8}


def key():
    k = (os.environ.get("GBT_RUNPOD_API_KEY") or "").strip()
    if not k:
        p = ROOT / ".scratch" / ".runpod_key"
        k = p.read_text(encoding="utf-8").strip() if p.is_file() else ""
    return k


def create(k, pw):
    body = {"name": "gbt-v8-family-inject", "imageName": "runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04",
            "gpuTypeIds": ["NVIDIA GeForce RTX 4090"], "gpuCount": 1, "cloudType": "SECURE", "containerDiskInGb": 40,
            "networkVolumeId": "atc4ya6vpu", "volumeMountPath": "/workspace", "volumeInGb": 0,
            "ports": ["8888/http", "22/tcp"], "env": {"JUPYTER_PASSWORD": pw}}
    for _ in range(3):
        try:
            rq = urllib.request.Request("https://rest.runpod.io/v1/pods", method="POST", data=json.dumps(body).encode(),
                                        headers={"Authorization": "Bearer " + k, "Content-Type": "application/json", "User-Agent": "M"})
            with urllib.request.urlopen(rq, timeout=90) as s:
                return json.loads(s.read().decode())["id"]
        except urllib.error.HTTPError as e:
            print("create", e.code, flush=True); time.sleep(8)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse", action="store_true")
    ap.add_argument("--poll", type=int, default=8)
    a = ap.parse_args()
    k = key()
    if not k:
        print("无 RunPod 密钥"); return 2
    pw = (ROOT / ".scratch" / ".pod_pw").read_text(encoding="ascii").strip() if (ROOT / ".scratch" / ".pod_pw").is_file() else secrets.token_urlsafe(18)
    PID = (ROOT / ".scratch" / ".pod_id").read_text(encoding="ascii").strip() if a.reuse and (ROOT / ".scratch" / ".pod_id").is_file() else create(k, pw)
    if not PID:
        print("建卡失败"); return 1
    (ROOT / ".scratch" / ".pod_id").write_text(PID, encoding="ascii")
    (ROOT / ".scratch" / ".pod_pw").write_text(pw, encoding="ascii")
    print("POD", PID, flush=True)
    ctx = ssl.create_default_context()
    B = "https://%s-8888.proxy.runpod.net" % PID
    for i in range(12):
        try:
            with urllib.request.urlopen(urllib.request.Request(B + "/api/status?token=" + urllib.parse.quote(pw), headers={"User-Agent": "M"}), timeout=20, context=ctx):
                print("Jupyter OK @%ds" % ((i + 1) * 20), flush=True); break
        except Exception:
            time.sleep(20)
    def put(path, text):
        body = json.dumps({"type": "file", "format": "text", "content": text}).encode()
        rq = urllib.request.Request(B + path + "?token=" + urllib.parse.quote(pw), method="PUT", data=body,
                                    headers={"Authorization": "token " + pw, "Content-Type": "application/json", "User-Agent": "M"})
        with urllib.request.urlopen(rq, timeout=240, context=ctx) as s:
            return s.status
    def get(n):
        return urllib.request.urlopen(urllib.request.Request(B + "/files/workspace/" + n + "?token=" + urllib.parse.quote(pw), headers={"User-Agent": "M"}), timeout=90, context=ctx).read().decode("utf-8", "replace")
    put("/api/contents/workspace/accept_infer.py", (ROOT / "tools" / "train" / "accept_infer.py").read_text(encoding="utf-8"))
    lines = ["set -e", "pip install -q --upgrade-strategy only-if-needed transformers==4.46.3 peft==0.13.2 bitsandbytes datasets accelerate"]
    for q, (fam, cap) in PFX.items():
        put("/api/contents/workspace/pfx_" + q + ".txt", "本题所属族＝" + fam + "；本族位＝" + cap + "；答前必须先复述这两项，再答内容。")
        lines.append('ACCEPT_Q=/workspace/' + q + '.jsonl ACCEPT_A=/workspace/' + q + '_inj.jsonl ACCEPT_PREFIX="$(cat /workspace/pfx_' + q + '.txt)" python -u /workspace/accept_infer.py > /workspace/' + q + '_inj.log 2>&1')
    lines.append("echo CHAIN_EXIT=$?")
    put("/api/contents/workspace/chain_inj.sh", chr(10).join(lines) + chr(10))
    code = "import subprocess; p=subprocess.Popen(['nohup','bash','/workspace/chain_inj.sh'],stdout=open('/workspace/chain_inj2.log','w'),stderr=subprocess.STDOUT); print('CHAIN_PID', p.pid)"
    assert all(ord(c) < 128 for c in code)
    (ROOT / ".scratch" / "_fire_runner.json").write_text(json.dumps({"op": "run", "pod": PID, "code": code, "confirm": "主人已授权"}, ensure_ascii=False), encoding="utf-8")
    rr = subprocess.run([PY, "-X", "utf8", "tools/codex-scripts/five-dim.py", "cap", "pod_link", "--stdin", "--full"],
                        stdin=open(ROOT / ".scratch" / "_fire_runner.json", "rb"), capture_output=True, text=True, encoding="utf-8", errors="replace")
    o = (rr.stdout or "") + (rr.stderr or "")
    d = json.loads(o[o.find("{"):]); res = d.get("result") or {}
    print("FIRE:", json.dumps(res, ensure_ascii=False)[:160], flush=True)
    if not res.get("ok"):
        print("点火未成：卡保留（不关），等发票后 --reuse"); return 1
    # 轮询到取齐
    for i in range(a.poll * 15):
        time.sleep(60)
        miss = []
        for q, n in NEED.items():
            try:
                c = get(q + "_inj.jsonl").count(chr(10))
            except Exception:
                c = 0
            if c < n:
                miss.append("%s(%d/%d)" % (q, c, n))
        print("poll %d min: %s" % (i + 1, ("全齐" if not miss else ", ".join(miss))), flush=True)
        if not miss:
            for q in NEED:
                (ROOT / ".scratch" / (q + "_inj.jsonl")).write_text(get(q + "_inj.jsonl"), encoding="utf-8")
            for q, (fam, cap) in PFX.items():
                r = subprocess.run([PY, "-X", "utf8", "tools/train/check_family_discrimination.py", "--answers", ".scratch/" + q + "_inj.jsonl", "--cap", cap],
                                   capture_output=True, text=True, cwd=str(ROOT))
                print(((r.stdout or "") + (r.stderr or "")).strip()[:300], flush=True)
            rq = urllib.request.Request("https://rest.runpod.io/v1/pods/" + PID + "/stop", method="POST", data=b"{}",
                                        headers={"Authorization": "Bearer " + k, "Content-Type": "application/json", "User-Agent": "M"})
            with urllib.request.urlopen(rq, timeout=45) as s:
                print("取齐 -> stop", s.status, flush=True)
            return 0
    print("超时未取齐 ⇒ **不关卡**")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
