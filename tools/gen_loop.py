#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_loop v2 —— 出图 → 过闸 → **换构件**（不是堆形容词）→ 再出。

v1 的病：判定不过就往后追加一句"minimal background"，三句一叠，提示词自相矛盾，图也不变。
v2 改成**分构件拼装**，一次只换一个构件：

    主体 subject  ·  镜头 shot  ·  光 light  ·  材质 material

判据不过时，只替换对应构件（例如「留白不够」⇒ 换镜头为远景、主体降到下三分一）。
这样每轮改的是**构图决策**，不是措辞。

用法： python3 tools/gen_loop.py "Sun Wukong" --rounds 4
"""
import argparse
import json
import os
import sys
import time

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, ROOT)

SUBJECT = "{who}"
SHOT = {"开场": "medium close-up, shallow depth of field",
        "远景": "wide establishing shot, the subject small in the lower third, "
                "the upper two thirds smooth empty sky",
        "特写": "tight close-up on hands and material, background fully out of focus"}
LIGHT = {"开场": "hard key light from camera left",
         "单光": "single hard key light from camera left, everything else falls into shadow, "
                 "no glow, no god rays, no rim lights",
         "逆光": "strong backlight, subject half silhouetted"}
MATERIAL = ("photorealistic, skin pores and fur strands, real stone and metal texture, "
            "film grain, ARRI Alexa, no text, no watermark")

# 判据 → 换哪个构件（一次一个）
REPAIR = {
    "留白占比":     ("shot", "远景"),
    "焦点块数":     ("light", "单光"),
    "焦点占比":     ("light", "逆光"),
    "边缘密度":     ("shot", "远景"),
    "对比(亮度sd)": ("light", "逆光"),
}


def build(subject, shot, light):
    return "%s, %s, %s, %s" % (subject, SHOT[shot], LIGHT[light], MATERIAL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("subject", nargs="+")
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--seed", type=int, default=31)
    ap.add_argument("--gap", type=int, default=50)
    ap.add_argument("--size", default="1024x1536")
    ap.add_argument("--profile", default="photo")
    a = ap.parse_args()

    os.environ.setdefault("GBT_T2I_ENDPOINT", "pollinations")
    from gbt_allinone.api import run_task          # noqa: PLC0415

    who = " ".join(a.subject)
    shot, light = "开场", "开场"
    out = "/var/minis/attachments/gen_loop.jpg"
    hist = []

    for rnd in range(1, min(a.rounds, 5) + 1):
        prompt = build(who, shot, light)
        wf = {"nodes": [{"id": 1, "node": "t2i_qwen",
                         "inputs": {"prompt": prompt, "out": out,
                                    "size": a.size, "seed": a.seed + rnd}}]}
        rr = run_task("comfy_native", {"op": "run", "workflow": wf, "taste": a.profile})
        o = ((rr.get("result", {}).get("result", {}) or {}).get("trace") or [{}])[0].get("out", {})
        if not o.get("ok"):
            print("第 %d 轮出图失败：%s" % (rnd, str(o.get("回包") or o.get("error"))[:110]))
            if "402" in str(o.get("回包") or ""):
                print("  额度没恢复，等 %ds 再来" % a.gap)
                time.sleep(a.gap)
                continue
            break

        t = o.get("taste") or {}
        fails = t.get("fails") or []
        hist.append({"round": rnd, "shot": shot, "light": light,
                     "verdict": t.get("verdict"), "fails": fails,
                     "readings": t.get("readings")})
        print("第 %d 轮  镜头=%s 光=%s  →  %s  %s"
              % (rnd, shot, light, t.get("verdict"), ",".join(fails) or "-"))
        if t.get("verdict") == "PASS":
            print("过闸 ✅  %s" % out)
            break

        # 在**所有**不过的轴里，挑第一个"还没换过、且换得动"的构件。
        # （v2 首版只看 fails[0]，遇到"已经是单光"就直接停 —— 那是死锁，不是收敛。）
        applied = None
        for axis in fails:
            fix = REPAIR.get(axis)
            if not fix:
                continue
            key, val = fix
            if key == "shot" and shot != val:
                shot = val
                applied = (axis, key, val)
                break
            if key == "light" and light != val:
                light = val
                applied = (axis, key, val)
                break
        if not applied:
            print("  剩下的轴都没有可换构件了（不过：%s），停 —— 这是模型上限，不是循环问题"
                  % ",".join(fails))
            break
        print("  换构件：%s → %s（依据：%s 不过）" % (applied[1], applied[2], applied[0]))
        print("  等 %ds 让额度恢复…" % a.gap)
        time.sleep(a.gap)

    json.dump({"subject": who, "rounds": hist}, open("/tmp/gen_loop.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n纪录 /tmp/gen_loop.json · 产物 %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
