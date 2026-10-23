# -*- coding: utf-8 -*-
"""GPU 车道：用 llama.cpp 的 Vulkan 后端把部分层塞进显卡。

为什么不用最新版：llama.cpp b11840 的 Vulkan 后端在这台机器上**输出乱码**
（"北京GGGGGG"），而 b6000 同一份权重、同一块卡输出正确。已单独验过：
  b6000 + ngl12 = 5.40 tok/s 正确
  b11840 + ngl12 = 5.45 tok/s 乱码
所以版本钉死在 b6000。

还有一条硬纪律：**起了先自检**。用「中国的首都是」问一句，必须包含「北京」才算通；
不通就杀掉、如实报失败，让桥回落到 CPU 车道 —— 宁可慢，不许答错。

用法：
  python gpu_lane.py --start     起服务并自检（通了保持运行）
  python gpu_lane.py --check     只自检，通了退出 0
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
BIN_DIR = os.path.join(HERE, "bin", "llama-vulkan")
EXE = os.path.join(BIN_DIR, "llama-server.exe")
TAG = "b6000"
URL = "https://github.com/ggml-org/llama.cpp/releases/download/%s/llama-%s-bin-win-vulkan-x64.zip" % (TAG, TAG)
MODEL = os.environ.get("GBT_GPU_MODEL") or r"C:\gbtv8\state\weights\gbt-v8-v82-q5_0.gguf"
PORT = int(os.environ.get("GBT_GPU_PORT", "8793"))
NGL = int(os.environ.get("GBT_GPU_NGL", "12"))


def log(msg):
    sys.stderr.write("[gpu] %s\n" % msg)
    sys.stderr.flush()


def ensure_bin() -> bool:
    if os.path.isfile(EXE):
        return True
    os.makedirs(BIN_DIR, exist_ok=True)
    z = os.path.join(BIN_DIR, "_dl.zip")
    log("下载 %s（约 22 MB）…" % TAG)
    r = subprocess.run(["curl.exe", "-L", "--fail", "-s", "-o", z, URL], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(z):
        log("下载失败：%s" % (r.stderr or "")[:120])
        return False
    with zipfile.ZipFile(z) as zf:
        zf.extractall(BIN_DIR)
    os.remove(z)
    log("解包到 %s" % BIN_DIR)
    return os.path.isfile(EXE)


def healthy(timeout=1.5) -> bool:
    try:
        urllib.request.urlopen("http://127.0.0.1:%d/health" % PORT, timeout=timeout).read()
        return True
    except Exception:                                            # noqa: BLE001
        return False


def probe() -> tuple[bool, str]:
    """正确性自检：**严判**，不是「包含关键词」就算过。

    2026-10-24 教训：一开始只查「输出里有没有北京」，结果 GPU 答出
    「中国的首都是**北京**；它与**idepressent**（有效的抗抑郁药）…」，
    前半句对、后半句乱，照样判成通过。现在改成：**答案必须短且干净**，
    任何多余内容都算失败。宁可误杀，不许放一个会说胡话的车道上生产。
    """
    cases = [("中国的首都是", ["北京"], 12), ("1+1=", ["2", "二"], 6)]
    lines = []
    for prompt, expect_any, max_tok in cases:
        body = json.dumps({"prompt": prompt, "n_predict": max_tok, "temperature": 0}).encode()
        req = urllib.request.Request("http://127.0.0.1:%d/completion" % PORT, data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=180).read().decode("utf-8", "replace"))
            txt = (d.get("content") or "").strip()
        except Exception as exc:                                 # noqa: BLE001
            return False, "%s 请求失败 %s" % (prompt, type(exc).__name__)
        ok = (len(txt) <= 12) and any(e in txt for e in expect_any)
        lines.append("%r→%r %s" % (prompt, txt[:24], "OK" if ok else "脏"))
        if not ok:
            return False, "；".join(lines)
    return True, "；".join(lines)


def start() -> int:
    if not ensure_bin():
        return 2
    if healthy():
        ok, detail = probe()
        log("已在跑：自检 %s → %s" % ("通过" if ok else "失败", detail))
        return 0 if ok else 3
    if not os.path.isfile(MODEL):
        log("模型不在：%s" % MODEL)
        return 2
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    log("起 llama-server（ngl=%d, port=%d）…" % (NGL, PORT))
    subprocess.Popen([EXE, "-m", MODEL, "-c", os.environ.get("GBT_GPU_CTX", "256"),
                      "-t", os.environ.get("GBT_GPU_THREADS", "8"), "-ngl", str(NGL),
                      "--port", str(PORT), "--host", "127.0.0.1"],
                     cwd=BIN_DIR, creationflags=flags,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < 120:
        if healthy():
            break
        time.sleep(2)
    if not healthy():
        log("120 秒没起来")
        return 2
    ok, detail = probe()
    log("自检 %s → %s" % ("通过" if ok else "失败", detail))
    if not ok:
        subprocess.run(["powershell", "-NoProfile", "-c",
                        "(Get-NetTCPConnection -LocalPort %d -State Listen -ErrorAction SilentlyContinue).OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }" % PORT],
                       capture_output=True)
        return 3
    print(json.dumps({"ok": True, "port": PORT, "ngl": NGL, "detail": detail}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        print(json.dumps({"ok": healthy(), "port": PORT}))
        raise SystemExit(0)
    raise SystemExit(start())
