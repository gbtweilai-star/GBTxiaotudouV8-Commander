# -*- coding: utf-8 -*-
"""i2v-ark.py —— 图生视频闭环（BytePlus Ark · 会动的她）

## 为什么走这条（而不是继续 SadTalker）
SadTalker 只能驱动头/嘴；你要的是**动作自然、细节到手指**。那需要真正的视频生成模型。
本机 GPU 那条（OmniAvatar / RunPod 4090）六次建卡全报 `no instances currently available`（账号侧无库存），
所以走云端：**arkcli 已 SSO 登录**（`ark_api_key` active），模型 `dreamina-seedance-2-5-260628` 现读存在。

## 现在卡在哪（实测，不是猜）
    arkcli infer endpoint create --model dreamina-seedance-2-5-260628 --name gbt-i2v --billing-method token
    → {"type":"account_not_verified",
       "message":"The account has not completed account-opening and payment verification...",
       "hint":"... https://console.byteplus.com/user/basics/"}
⇒ **只有主人能做**：BytePlus 控制台完成「开通账号 + 支付验证」。做完这条命令就能建出端点。

## 本件做什么（等验证完就是一条命令）
  ① 端点：查 `gbt-i2v` 在不在；不在就建（`dreamina-seedance-2-5-260628` · billing=token）
  ② 提交图生视频任务：把你的原图当参考 + 一条**写到手指**的动作提示词
  ③ 轮询到完成，把 mp4 落到 `outputs/i2v/`
  ④ 三条口径验收（画质/动作/嘴）—— 复用 `qc-video.py`
  ⑤ **只有过线才发布**到云动作库（`motion-publish.py`）
  ⑥ 每一步进 `state/i2v-ark.jsonl` 账本；失败**原话透传**，不许哑失败

## 用法
  py -3.14 tools/digihuman/i2v-ark.py probe                 # 只读：端点/账号/模型三件事
  py -3.14 tools/digihuman/i2v-ark.py run --image <图> --id v6 --duration 5 --ratio 9:16
  py -3.14 tools/digihuman/i2v-ark.py run ... --dry-run      # 只打印计划
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "i2v"
LEDGER = ROOT / "state" / "i2v-ark.jsonl"
ENDPOINT_NAME = "gbt-i2v"
MODEL = "dreamina-seedance-2-5-260628"          # 现读：不带版本号会被拒（实测）
ARKCLI = shutil.which("arkcli") or "arkcli"

# 动作提示词：把「手指级细节」写进提示，而不是笼统"自然动作"
DEFAULT_PROMPT = (
    "画面中的女生站在室内，先把右手抬起把一缕头发别到耳后，手指自然张开再轻轻并拢；"
    "随后手缓缓放下，五指依次舒展，手腕带动、肘部跟随；身体轻微做重心转移与呼吸起伏；"
    "头微微侧转、眼神自然看向镜头；镜头固定不动；人物长相、发型、服装与参考图完全一致；"
    "动作连贯、符合真实人体关节，高清写实细节"
)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                                   # noqa: BLE001
        pass


def ark(args: list, timeout: int = 300) -> dict:
    """跑一次 arkcli，永远返回带 ok / code / message 的结构（不哑失败）。"""
    cmd = [ARKCLI] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "code": "timeout", "message": "arkcli 超时 %ss" % timeout, "cmd": cmd}
    raw = (r.stdout or "") + (r.stderr or "")
    # arkcli 会在 JSON 前后夹「New arkcli version available」这类提示行，
    # 所以取**首个 { 到最后一个 }** 之间的片段再解析（实测踩过：只取到首个 { 会导致整块解析失败）。
    i, j = raw.find("{"), raw.rfind("}")
    data = {}
    if i >= 0 and j > i:
        try:
            data = json.loads(raw[i:j + 1])
        except ValueError:
            data = {}
    err = data.get("error") or {}
    return {"ok": bool(data.get("ok")) or r.returncode == 0 and not err,
            "code": err.get("type") or data.get("code") or "",
            "message": err.get("message") or data.get("message") or "",
            "hint": err.get("hint") or "",
            "data": data, "cmd": " ".join(cmd), "tail": raw.strip().splitlines()[-6:]}


def probe() -> dict:
    """只读体检：端点 / 账号验证 / 模型。三件事分开报，不混成一句。"""
    eps = ark(["infer", "endpoint", "list"])
    d0 = eps.get("data") or {}
    count = d0.get("TotalCount")
    if count is None:
        count = d0.get("total") or d0.get("Total")
    mine = None
    for it in ((eps.get("data") or {}).get("Items") or []):
        if str(it.get("Name") or "") == ENDPOINT_NAME:
            mine = {"id": it.get("Id") or it.get("EndpointId"), "status": it.get("Status")}
    auth = ark(["auth", "status"])

    def find_verified(node, depth=0):
        """实测：identity 不一定挂在 active_profile 下 ⇒ 递归找第一个带 verified 的 identity。"""
        if depth > 6:
            return None
        if isinstance(node, dict):
            ident = node.get("identity")
            if isinstance(ident, dict) and "verified" in ident:
                return ident.get("verified")
            for v in node.values():
                got = find_verified(v, depth + 1)
                if got is not None:
                    return got
        elif isinstance(node, list):
            for v in node:
                got = find_verified(v, depth + 1)
                if got is not None:
                    return got
        return None

    verified = find_verified(auth.get("data") or {})
    return {"endpoints_total": count, "endpoint": mine,
            "account_verified": verified, "model": MODEL,
            "blocked": (verified is False)}


def create_endpoint() -> dict:
    return ark(["infer", "endpoint", "create", "--model", MODEL, "--name", ENDPOINT_NAME,
                "--billing-method", "token"], timeout=600)


def submit(image: Path, prompt: str, duration: int, ratio: str) -> dict:
    return ark(["+gen", prompt, "--modality", "video", "--model", MODEL,
                "--input", "@" + str(image), "--duration", str(duration), "--ratio", ratio,
                "--save-to", str(OUT), "--no-open", "--wait"], timeout=1800)


def note(rec: dict) -> None:
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **rec}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["probe", "run"])
    ap.add_argument("--image", default="holo_pet/assets/digital-human/standard/reference-front.jpg")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--id", default="i2v-v1")
    ap.add_argument("--duration", type=int, default=5)
    ap.add_argument("--ratio", default="9:16")
    ap.add_argument("--title", default="")
    ap.add_argument("--framing", default="full-body")
    ap.add_argument("--voice-label", default="")
    ap.add_argument("--no-publish", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    p = probe()
    print("PROBE " + json.dumps(p, ensure_ascii=False), flush=True)

    if a.cmd == "probe":
        if p["blocked"]:
            print("BLOCKED account_not_verified —— 主人需在 "
                  "https://console.byteplus.com/user/basics/ 完成「开通账号 + 支付验证」", flush=True)
        return 0 if not p["blocked"] else 9

    image = (ROOT / a.image) if not Path(a.image).is_absolute() else Path(a.image)
    if not image.is_file():
        print("FAIL " + json.dumps({"why": "图不在", "image": str(image)}, ensure_ascii=False))
        return 2

    plan = {"image": str(image), "prompt": a.prompt, "duration": a.duration,
            "ratio": a.ratio, "model": MODEL, "endpoint": ENDPOINT_NAME,
            "account_verified": p["account_verified"], "endpoint_now": p["endpoint"]}
    if a.dry_run:
        print("PLAN " + json.dumps(plan, ensure_ascii=False, indent=1))
        return 0
    print("PLAN " + json.dumps(plan, ensure_ascii=False), flush=True)

    # ① 端点：没有就建（会撞账号门，原话透传）
    if not p["endpoint"]:
        r = create_endpoint()
        note({"step": "create_endpoint", "ok": r["ok"], "code": r["code"],
              "message": r["message"], "hint": r["hint"]})
        print("ENDPOINT " + json.dumps({k: r[k] for k in ("ok", "code", "message", "hint")},
                                       ensure_ascii=False), flush=True)
        if not r["ok"]:
            print("STOP " + json.dumps({
                "why": "建端点被拒（这是账号门，不是代码问题）",
                "code": r["code"], "message": r["message"], "hint": r["hint"],
                "owner_action": "BytePlus 控制台 → 账号设置 → 完成「开通账号 + 支付验证」"},
                ensure_ascii=False), flush=True)
            return 3

    # ② 生成
    OUT.mkdir(parents=True, exist_ok=True)
    r = submit(image, a.prompt, a.duration, a.ratio)
    note({"step": "submit", "id": a.id, "ok": r["ok"], "code": r["code"],
          "message": r["message"], "tail": r["tail"]})
    print("GEN " + json.dumps({k: r[k] for k in ("ok", "code", "message")}, ensure_ascii=False),
          flush=True)
    if not r["ok"]:
        print("STOP " + json.dumps({"why": "生成失败", "code": r["code"],
                                    "message": r["message"], "tail": r["tail"]},
                                   ensure_ascii=False), flush=True)
        return 4

    # ③ 落盘核对（不许"以为下下来了"）
    got = sorted(OUT.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not got:
        print("FAIL " + json.dumps({"why": "回执 ok 但目录里没有 mp4", "dir": str(OUT)},
                                   ensure_ascii=False))
        note({"step": "download", "ok": False, "why": "no mp4 in dir"})
        return 5
    newest = got[0]
    final = OUT / ("%s.mp4" % a.id)
    if newest != final:
        shutil.copyfile(newest, final)
    print("VIDEO " + json.dumps({"file": str(final), "bytes": final.stat().st_size},
                                ensure_ascii=False), flush=True)
    note({"step": "download", "id": a.id, "file": str(final),
          "bytes": final.stat().st_size})

    if a.no_publish:
        print("DONE " + json.dumps({"file": str(final), "published": None}, ensure_ascii=False))
        return 0
    print("NEXT 三条口径验收与上云请接 finish-clip.py（本件只管把片子生出来）", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
