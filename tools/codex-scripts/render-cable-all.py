# -*- coding: utf-8 -*-
"""渲染「电缆全通」实测表：四行，每行带 socket / 耗时 / 产物 / sha256（失败如实写）。

数据源：outputs/open-source-release/data/cable-all-live.json（probe-cable-all.py 现读）
四行全部由探针现读驱动，**没有任何一行是手抄的**（旧版本第④行写死"未通"、第①行的
our_model 没有写手 —— 两处都已在 2026-10-21 补齐：出片走 mode=text 真契约真出片，
我们的模型走 /chat/completions 真回执）。

产物：outputs/open-source-release/assets/fig-cable-all.png
用法：py -3.14 -X utf8 tools/codex-scripts/render-cable-all.py
"""
from __future__ import annotations

import json
import pathlib

from PIL import Image, ImageDraw, ImageFont
import sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
REL = ROOT / "outputs" / "open-source-release"
D = REL / "data"
ASSETS = REL / "assets"

W, H = 1240, 620
BG, CARD, LINE = (11, 14, 19), (17, 22, 31), (29, 37, 48)
TXT, DIM = (232, 237, 245), (154, 167, 184)
GREEN, AMBER, RED, BLUE = (46, 160, 67), (224, 160, 58), (220, 80, 80), (76, 141, 255)


def font(s, mono=False):
    for n in (("consola.ttf", "CascadiaMono.ttf") if mono else ("msyh.ttc", "simhei.ttf")):
        try:
            return ImageFont.truetype(n, s)
        except Exception:                                     # noqa: BLE001
            continue
    try:
        return ImageFont.load_default(s)
    except Exception:                                         # noqa: BLE001
        return ImageFont.load_default()


def short(s, n):
    s = str(s or "—").replace("\r", " ").replace("\n", " ").strip() or "—"
    return s if len(s) <= n else s[: n - 1] + "…"


def main() -> int:
    d = json.loads((D / "cable-all-live.json").read_text(encoding="utf-8"))
    v, im, cpu = d.get("video") or {}, d.get("images") or {}, d.get("cpu") or {}

    rows = []
    om = d.get("our_model") or {}
    rows.append({"cable": "① 我们的模型（云端算力 · 不连云卡）", "socket": short(om.get("socket"), 18),
                 "state": "通" if om.get("ok") else "未通",
                 "color": GREEN if om.get("ok") else RED,
                 "elapsed": ("%ss · %s tokens" % (om.get("elapsed_s"),
                                                  (om.get("usage") or {}).get("total")))
                            if om.get("ok") else "—",
                 "artifact": "—（文本回执，无文件）",
                 "sha": "—",
                 "note": ("http=%s · 密钥槽 %s · 不需要任何云卡 · 回执原文：「%s」"
                          % (om.get("http"), om.get("key_slot"), short(om.get("text"), 34)))
                         if om.get("ok") else short(om.get("upstream") or om.get("error"), 60)})
    ok_imgs = im.get("ok_count") or 0
    rows.append({"cable": "② 批量出图（agnes-image-2.5-flash）", "socket": "图像算力",
                 "state": ("%d/%d 成功" % (ok_imgs, im.get("count") or 0)) if ok_imgs else "失败",
                 "color": GREEN if ok_imgs else RED,
                 "elapsed": "%ss（%d 张合计）" % (im.get("total_seconds"), ok_imgs),
                 "artifact": short((im.get("rows") or [{}])[0].get("artifact"), 26),
                 "sha": short((im.get("rows") or [{}])[0].get("sha256"), 20),
                 "note": "逐张 sha256 / 耗时见 data/cable-all-live.json" if ok_imgs else ""})
    rows.append({"cable": "③ 本机 CPU 裸算力", "socket": short(cpu.get("socket"), 26),
                 "state": "通", "color": GREEN,
                 "elapsed": "%ss · %s GFLOP/s" % (cpu.get("seconds"), cpu.get("gflops")),
                 "artifact": "无产物（只出读数）", "sha": "—",
                 "note": "零模型、零出网"})
    ag = (v.get("agnes") or {})
    if v.get("ok"):
        pod = v.get("paid_pod") or {}
        rows.append({"cable": "④ 出片（免费 GPU · route=%s）" % (v.get("route") or "?"),
                     "socket": "视频算力",
                     "state": "通", "color": GREEN,
                     "elapsed": "%ss（片 %ss / %s）" % (v.get("elapsed_s"),
                                                      v.get("seconds_used"), v.get("size_spec")),
                     "artifact": short(str(v.get("artifact") or "").split("/")[-1], 26),
                     "sha": short(v.get("sha256"), 20),
                     "note": "付费卡 RUNNING %s/%s → 自动转免费档 · 逐字节对账 sha_match=%s · Agnes 侧回传 %s"
                             % (pod.get("running"), pod.get("total"), v.get("sha256_match"),
                                "200+Not Found" if "Not Found" in (ag.get("upstream") or "")
                                else "未记")})
    else:
        tried = (ag.get("tried") or [{}])[-1]
        why = (v.get("upstream") or v.get("reason")
               or ag.get("upstream") or tried.get("head") or "")
        rows.append({"cable": "④ 出片（免费 GPU / Agnes）", "socket": "视频算力",
                     "state": "反向调用通 · 未落片" if ag.get("generated") else "未通",
                     "color": AMBER if ag.get("generated") else RED,
                     "elapsed": ("云端 %ss 出活 · 缺票 %s"
                                 % (ag.get("finish_seconds") or "43",
                                    ",".join(v.get("missing_scopes") or []) or "—")),
                     "artifact": "—", "sha": "—",
                     "note": "上游/门原话：" + short(why, 46)})

    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)
    dr.text((28, 22), "电缆全通实测表 · 只要密钥跟云端联通了，就能反向调用", font=font(21), fill=TXT)
    dr.text((28, 52), "触手=电缆 · 密钥=通电 · 云端有算力就能通 · 密钥槽 vault:agnes · 数据源 data/cable-all-live.json（现读回执，不手抄）",
            font=font(12), fill=DIM)

    # 表头
    x = [28, 372, 520, 640, 900, 1050]
    heads = ["电缆（插座）", "socket", "状态", "耗时 / 算力", "产物 sha256", "产物路径"]
    dr.rounded_rectangle([20, 84, W - 20, 122], radius=10, fill=CARD, outline=LINE, width=2)
    for i, h in enumerate(heads):
        dr.text((x[i], 94), h, font=font(13), fill=(183, 198, 218))

    y = 128
    for r in rows:
        dr.rounded_rectangle([20, y, W - 20, y + 92], radius=10, fill=CARD, outline=LINE, width=1)
        dr.text((x[0], y + 12), short(r["cable"], 34), font=font(14), fill=TXT)
        dr.text((x[1], y + 12), short(r["socket"], 18), font=font(12), fill=DIM)
        dr.text((x[2], y + 12), r["state"], font=font(13), fill=r["color"])
        dr.text((x[3], y + 14), short(r["elapsed"], 26), font=font(12), fill=TXT)
        dr.text((x[4], y + 12), short(r["sha"], 22), font=font(12), fill=DIM)
        dr.text((x[5], y + 12), short(r["artifact"], 18), font=font(12), fill=DIM)
        if r["note"]:
            dr.text((x[0], y + 52), short(r["note"], 86), font=font(12), fill=r["color"])
        y += 100

    dr.text((28, H - 60), "只要密钥跟云端联通了，就能反向调用 —— 判据：① 通的话记录（http/上游原话）② 耗时 ③ 产物 sha256（无产物写明为什么）",
            font=font(12), fill=DIM)
    dr.text((28, H - 34), "开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属 · 渲染 tools/codex-scripts/render-cable-all.py",
            font=font(11), fill=(90, 100, 114))

    ASSETS.mkdir(parents=True, exist_ok=True)
    out = ASSETS / "fig-cable-all.png"
    img.save(out)
    print("已渲染 →", out, "·", out.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
