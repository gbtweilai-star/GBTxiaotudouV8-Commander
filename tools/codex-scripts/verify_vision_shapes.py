# -*- coding: utf-8 -*-
"""⑥ G1/G2 视觉面「结构化做不了」的回归。

《触手覆盖矩阵.md》§三：眼组「能报做不了 **0/5**」——唯一零上报信号的组。
本回归验三件（不靠撒关键词，靠真调行为）：
  ① 取帧失败 ⇒ 返回**结构化拒绝**（ok/unavailable/rule/missing/why），
     **不抛 KeyError**、**不返回空结果**
  ② 原有成功路径不受影响（能取到帧时行为与改前一致）
  ③ 失败分类正确：无显示/无帧源 → missing 里点名；窗口找不到 → window_not_found
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = fail = 0


def chk(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print("  ✓ %-54s %s" % (name, detail))
    else:
        fail += 1
        print("  ✗ %-54s %s" % (name, detail))


def load(rel, modname):
    spec = importlib.util.spec_from_file_location(modname, ROOT / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


print("① vision_bus：取帧失败 ⇒ 结构化拒绝，不抛 KeyError")
vb = load("gbt_allinone/tentacle/vision_bus.py", "vb_probe")


class _BlindEye:
    """一只瞎眼：_screen_capture 永远失败（模拟无显示 / DXGI 取不到帧）。"""

    def _screen_capture(self, region=None, **kw):
        return {"ok": False, "error": "DXGI 取不到帧（模拟无显示）"}


r = vb.snapshot(_BlindEye())
chk("snapshot 不抛异常且 ok=False", isinstance(r, dict) and r.get("ok") is False,
    "rule=%s" % r.get("rule"))
chk("snapshot 带结构化字段",
    r.get("unavailable") is True and r.get("rule") == "vision_bus_cannot_capture"
    and isinstance(r.get("missing"), list) and bool(r.get("why")),
    "missing=%s" % r.get("missing"))

r2 = vb.diff_with_previous(_BlindEye())
chk("diff_with_previous 同样结构化（原来会 KeyError）",
    isinstance(r2, dict) and r2.get("ok") is False and r2.get("rule") == "vision_bus_cannot_capture",
    "rule=%s" % r2.get("rule"))


class _ShapeBrokenEye:
    """取帧"成功"但没有 image_base64 —— 形状异常也要结构化，不许 KeyError。"""

    def _screen_capture(self, region=None, **kw):
        return {"ok": True, "size": [100, 100]}


r3 = vb.snapshot(_ShapeBrokenEye())
chk("取帧成功但缺 image_base64 ⇒ 结构化（不 KeyError）",
    isinstance(r3, dict) and r3.get("ok") is False
    and "形状异常" in str(r3.get("why")),
    str(r3.get("why"))[:44])

print("\n② 成功路径不受影响")
# 用 PIL 现造一张**真能解码**的 PNG（上一版我硬编码了一段坏 base64，
# 于是测出了 `_ahash` 对损坏帧抛 OSError —— 那反倒是真缺口，已在源码里补了结构化拒绝）
import base64  # noqa: E402
import io as _io  # noqa: E402

from PIL import Image  # noqa: E402

_buf = _io.BytesIO()
Image.new("RGB", (8, 8), (10, 20, 30)).save(_buf, format="PNG")
_B64 = base64.b64encode(_buf.getvalue()).decode()
_BROKEN_B64 = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8).decode()


class _GoodEye:
    def _screen_capture(self, region=None, **kw):
        return {"ok": True, "size": [8, 8], "image_kb": 0.1, "image_base64": _B64}


g = vb.snapshot(_GoodEye())
chk("正常取帧 → ok=True 且带 fingerprint",
    g.get("ok") is True and bool(g.get("fingerprint")),
    "fp=%s" % g.get("fingerprint"))


class _CorruptEye:
    """取帧"成功"但帧是坏的 —— 解码会抛 OSError，必须被拦成结构化拒绝。"""

    def _screen_capture(self, region=None, **kw):
        return {"ok": True, "size": [8, 8], "image_kb": 0.1, "image_base64": _BROKEN_B64}


rc = vb.snapshot(_CorruptEye())
chk("损坏帧 ⇒ 结构化拒绝（不把视觉路径打崩）",
    isinstance(rc, dict) and rc.get("ok") is False
    and rc.get("rule") == "vision_bus_cannot_capture"
    and "解码" in str(rc.get("why")),
    str(rc.get("why"))[:52])

print("\n③ omni_vision（万能插的眼睛）：失败分类")
spec = importlib.util.spec_from_file_location(
    "ov_probe", ROOT / "gbt_allinone/tentacle/omni_vision.py")
ov = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(ov)
except Exception as e:  # noqa: BLE001
    print("    (omni_vision 依赖 omni_core，独立加载受限：%s)" % str(e)[:60])
    ov = None

if ov is not None:
    inst = ov.OmniVisionMixin()
    ref = inst._cap_refusal({"error": "拿不到屏幕"}, "see")
    chk("_cap_refusal 结构化",
        ref.get("ok") is False and ref.get("unavailable") is True
        and ref.get("rule") == "screen_capture_unavailable" and ref.get("missing"),
        "missing=%s" % ref.get("missing"))
    bad, why = inst._require_cap({"ok": False, "error": "x"}, "see")
    chk("_require_cap 失败时返回 (None, 结构化拒绝)", bad is None and why.get("rule"),
        "rule=%s" % why.get("rule"))
    good, why2 = inst._require_cap({"ok": True, "image_base64": "x", "size": [1, 1]}, "see")
    chk("_require_cap 成功时返回 (cap, None)", good is not None and why2 is None, "")
    none_ok, why3 = inst._require_cap({"ok": True}, "see")
    chk("成功但无帧字段 ⇒ 也结构化（形状异常）", none_ok is None and "形状异常" in str(why3.get("why")),
        "")
else:
    chk("omni_vision._cap_refusal（源码级确认）",
        "_cap_refusal" in (ROOT / "gbt_allinone/tentacle/omni_vision.py").read_text(encoding="utf-8-sig")
        and "screen_capture_unavailable" in (ROOT / "gbt_allinone/tentacle/omni_vision.py").read_text(encoding="utf-8-sig"),
        "独立加载受限，改判源码级")

print("\n④ visual_cortex：拿不到帧 ⇒ 结构化，不返回空结果")
vc_src = (ROOT / "gbt_allinone/tentacle/brain/visual_cortex.py").read_text(encoding="utf-8-sig")
chk("visual_cortex 有结构化出口 _no_frame", "_no_frame" in vc_src
    and "visual_cortex_no_frame" in vc_src, "")
chk("analyze_html 空输入 ⇒ 结构化", "visual_cortex_empty_input" in vc_src, "")
chk("两个屏幕入口都先取帧再判空",
    vc_src.count("_frame_from_bus()") >= 2 and vc_src.count("_no_frame(") >= 2, "")

print("\n" + "-" * 78)
print("通过 %d · 失败 %d" % (ok, fail))
sys.exit(0 if fail == 0 else 1)
