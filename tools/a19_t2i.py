#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a19_t2i —— **A19 参与**的四步出图链（她出词，模型出像素）。

分工写死在这里，不许混：
    A19（她的权重）→ 写提示词：题材理解、画面要素、镜头与光
    t2i_qwen（图像模型）→ 出像素
    taste_gate（闸）→ 兜底，不过就报哪一轴
    我 → 逐张看，只改一处

用法：
    python3 tools/a19_t2i.py "齐天大圣 力劈华山" [--seed 11] [--size 1024x1536]
    python3 tools/a19_t2i.py --check        # 只报 A19 在不在

容器不在 ⇒ 直接停，**不拿现成提示词冒充她写的**。
"""
import argparse
import importlib.util
import os
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, ROOT)

WRITER = """你是 GBT小土豆V8。把用户给的一句话变成一条**图像模型提示词**（英文，一行，≤90 词）。
要求：
1. 第一条写清主体、动作、场景，不许只写气氛。
2. 写明镜头与光：焦段/景深/光源方向。
3. 写明材质与质感：皮肤、毛发、石材、织物。
4. 结尾加：photorealistic, no text, no watermark
只输出这一行提示词，不要解释、不要引号、不要 markdown。"""


def ctl():
    spec = importlib.util.spec_from_file_location("a19ctl", os.path.join(TOOLS, "a19_ctl.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("subject", nargs="*")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--size", default="1024x1536")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    c = ctl()
    st = c.status_dict()
    if a.check or not a.subject:
        print("A19 %s · %s" % (st.get("container"), st.get("why") or "ok"))
        return 0 if st.get("container") == "UP" else 2
    if st.get("container") != "UP":
        print("A19 不在（:1234 无监听）—— 不拿现成提示词冒充她写的，停。")
        return 2

    q = " ".join(a.subject)
    r = c.chat_dict([{"role": "system", "content": WRITER},
                     {"role": "user", "content": q}], 300, 0.7)
    if not r.get("ok"):
        print("A19 写词失败：%s" % r.get("why"))
        return 3
    prompt = (r.get("answer") or "").strip().strip('"').splitlines()[0][:1200]
    print("[A19 写的词 · %ss · %s tok/s]\n%s\n" % (r.get("elapsed_s"), r.get("tok_s"), prompt))

    os.environ.setdefault("GBT_T2I_ENDPOINT", "pollinations")
    from gbt_allinone.api import run_task          # noqa: PLC0415
    out = "/var/minis/attachments/a19_t2i.jpg"
    wf = {"nodes": [{"id": 1, "node": "t2i_qwen",
                     "inputs": {"prompt": prompt, "out": out,
                                "size": a.size, "seed": a.seed}}]}
    rr = run_task("comfy_native", {"op": "run", "workflow": wf})
    o = ((rr.get("result", {}).get("result", {}) or {}).get("trace") or [{}])[0].get("out", {})
    print("[出图] %s %s bytes %s" % (o.get("status"), o.get("bytes"),
                                     o.get("能源读数")))
    if not o.get("ok"):
        return 4

    g = subprocess.run([sys.executable, os.path.join(TOOLS, "taste_gate.py"),
                        "--judge", out, "--profile", "photo"],
                       capture_output=True, text=True)
    print("\n".join(l for l in g.stdout.splitlines()
                    if "OK" in l or "FAIL" in l or l.startswith("判定")))
    print("\n产物：%s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
