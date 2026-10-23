# -*- coding: utf-8 -*-
"""生成 V13 数据层：v12_manifest.json + brand 段；并把 Logo 真正接上的席位计入已实现。"""
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

S = Path(__file__).resolve().parent
BASE = S.parent
v12 = json.loads((S / "v12_manifest.json").read_text(encoding="utf-8"))
emb = json.loads((S / "logo_embed.json").read_text(encoding="utf-8"))

# ── Logo 接上后，这三个席位从「缺口」变成「已实现」 ──
ADDED = {
    "sidebar.brand.mark": "侧栏品牌标 · Logo（App Logo）",
    "sidebar.brand.name": "侧栏品牌名 · GBT小土豆V8 字样",
    "conversation.hero.brand.mark": "空态引导品牌标 · Logo（64px）",
}
d = v12["dsh"]
have = {x["slot"] for x in d["implemented"]}
for slot, how in ADDED.items():
    assert slot in d["slot_owner"], "席位不存在: " + slot
    if slot not in have:
        d["implemented"].append({"slot": slot, "how": how})
d["implemented"].sort(key=lambda x: x["slot"])
impl = {x["slot"] for x in d["implemented"]}
d["missing"] = [s for s in d["slots_real"] if s not in impl]
d["n_implemented"] = len(d["implemented"])
d["n_missing"] = len(d["missing"])

v12["brand"] = {
    "owner_supplied": True,
    "name": "GBT小土豆 · 科技土豆",
    "source": {"sha256": emb["source_sha256"], "bytes": emb["source_bytes"],
               "dims": emb["source_dims"], "format": emb["source_format"]},
    "cutout": emb["cutout"],
    "embed": emb["embed"],
    "colors": emb["colors"],
    "variants": emb["variants"],
    "usage": {
        "sidebar": "32px 透明底 + 青色 drop-shadow（原先是 30px 文字方块 GBT）",
        "hero": "64px 透明底（对话空态 orb，原先是 SVG 四方格图标）",
        "canvas_bar": "22px 透明底（画布每页标题栏的品牌徽标）",
        "favicon": "32px PNG 内嵌（标签页图标）",
    },
    "rule": "原始 JPEG 与全部派生件存于 assets/brand/；两个交付件各自把它们内嵌成 data URI，"
            "保证单文件自包含、离线可开。",
}

out = S / "v13_manifest.json"
out.write_text(json.dumps(v12, ensure_ascii=False, indent=1), encoding="utf-8")
print("写出:", out.name, "%.1f KB" % (out.stat().st_size / 1024))
print("席位：已实现 %d · 缺口 %d（原 7 / 74）" % (d["n_implemented"], d["n_missing"]))
print("新接上的三个席位：")
for slot, how in ADDED.items():
    print("   ✓ %-32s %s" % (slot, how))
print("Logo 尺寸件 %d 个 · 内嵌：原型 %d B / 画布 %d B / favicon %d B"
      % (len(emb["variants"]), emb["embed"]["prototype"]["base64_bytes"],
         emb["embed"]["canvas"]["base64_bytes"], emb["embed"]["favicon"]["base64_bytes"]))
print("品牌色：发光青 %s · 均值青 %s · 土豆皮 %s（--accent %s，均值青距 %.1f）"
      % (emb["colors"]["glow_cyan"], emb["colors"]["mean_cyan"], emb["colors"]["skin"],
         emb["colors"]["accent"], emb["colors"]["delta_mean_vs_accent"]))
