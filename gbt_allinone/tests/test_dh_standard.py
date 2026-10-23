# -*- coding: utf-8 -*-
"""判据 · **数字人标准达标**（Owner 2026-10-18：「画面必须高清 动作自然」「手指都要」「严格按我的要求直到合格为止」）。

## 它咬什么（六条，全部可复算、不看感觉）

  1. **骨架与手指**：正牌模型 skin.joints ≥ 60，其中手指骨 ≥ 40（五指 × 四节 × 双手）
  2. **动作是真的**：模型 animations 必须同时含 `idle` 与 `walk` —— 页面不许拿"晃容器"冒充动作
  3. **高清**：模型内最大贴图边 ≥ 2048；标准 4K 件 `standard/tex/HERO-4096.png` 边 ≥ 4096
  4. **页面真播动画**：`standard/index.html` 必须同时出现 AnimationMixer / crossFadeTo /
     RoomEnvironment（PBR 环境，没它材质发闷）/ anisotropy（斜视纹理不糊）
  5. **不许 iframe**：面板必须是自己渲染，不许嵌别人的页（那一墙链接乱码就是这么来的）
  6. **不许悬空引用**：页面里写到的每个 `.glb` 都必须在盘上；`raw/portrait-bust-low-rigged.glb`
     曾是悬空引用（2026-10-18 实测不存在）—— 这类一律红

## 口径

只读：读 GLB 的 JSON 块、读 PNG 头、读 HTML 文本。不写盘、不起进程、不出网。
`GBT_DH_ROOT` 可替换仓根（用于"对着候选件先量一遍"的排练）。
"""
from __future__ import annotations

import json
import os
import re
import struct
import unittest
from pathlib import Path

ROOT = Path(os.environ.get("GBT_DH_ROOT") or Path(__file__).resolve().parents[2])
DH = ROOT / "holo_pet" / "assets" / "digital-human"
CANON = DH / "raw" / "rig" / "model-rigged-anim.glb"      # 正牌（19 个工具引用它）
STD = DH / "standard"
PAGE = STD / "index.html"
HERO = STD / "tex" / "HERO-4096.png"
AVATAR = DH / "web" / "avatar.html"


def glb_json(p: Path) -> dict:
    with p.open("rb") as f:
        f.read(12)
        ln, _typ = struct.unpack("<II", f.read(8))
        return json.loads(f.read(ln).decode("utf-8", "replace"))


def glb_blob(p: Path) -> bytes:
    with p.open("rb") as f:
        f.read(12)
        ln, _typ = struct.unpack("<II", f.read(8))
        f.read(ln)
        f.read(8)
        return f.read()


def png_size(b: bytes):
    if b[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", b[16:24])


def jpg_size(b: bytes):
    i = 2
    while i < len(b) - 9:
        if b[i] != 0xFF:
            i += 1
            continue
        m = b[i + 1]
        if m in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", b[i + 5:i + 9])
            return (w, h)
        i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    return None


FINGER = re.compile(r"hand(index|middle|ring|pinky|thumb)", re.I)


class DhStandardTest(unittest.TestCase):
    def test_canonical_model_exists(self) -> None:
        self.assertTrue(CANON.is_file(), "正牌模型不在：%s" % CANON)

    def test_bones_and_fingers(self) -> None:
        """手指都要 —— 五指四节，双手合计 ≥40 根。"""
        j = glb_json(CANON)
        names = [n.get("name", "") for n in (j.get("nodes") or [])]
        joints = set()
        for s in (j.get("skins") or []):
            joints.update(s.get("joints") or [])
        bones = len(joints)
        fingers = len([n for i, n in enumerate(names) if i in joints and FINGER.search(n)])
        self.assertGreaterEqual(bones, 60, "骨数 %d < 60 —— 骨架不全" % bones)
        self.assertGreaterEqual(fingers, 40, "手指骨 %d < 40 —— 手指缺失（Owner 明确要求）" % fingers)

    def test_has_idle_and_walk(self) -> None:
        """动作自然的前提：模型里必须有真动画轨，且 idle/walk 都在。"""
        j = glb_json(CANON)
        got = {str(a.get("name") or "") for a in (j.get("animations") or [])}
        missing = {"idle", "walk"} - got
        self.assertEqual(set(), missing, "模型缺动画轨：%s（现有：%s）" % (sorted(missing), sorted(got)))

    def test_textures_are_hd(self) -> None:
        """高清：模型里最大贴图 ≥2048。"""
        j = glb_json(CANON)
        blob = glb_blob(CANON)
        bvs = j.get("bufferViews") or []
        sizes = []
        for im in (j.get("images") or []):
            bv = bvs[im["bufferView"]] if "bufferView" in im else None
            if not bv:
                continue
            off, ln = bv.get("byteOffset", 0), bv.get("byteLength", 0)
            data = blob[off:off + ln]
            sz = png_size(data) or jpg_size(data)
            if sz:
                sizes.append(max(sz))
        self.assertTrue(sizes, "模型里一张贴图都没解出来（解析坏了？）")
        self.assertGreaterEqual(max(sizes), 2048,
                                "最大贴图 %d < 2048 —— 不够高清（各张：%s）" % (max(sizes), sorted(sizes)))

    def test_hero_4k_asset(self) -> None:
        """天真 出的 4K 基准件必须在，且真的 4096。"""
        self.assertTrue(HERO.is_file(), "4K 基准件不在：%s" % HERO)
        sz = png_size(HERO.read_bytes())
        self.assertIsNotNone(sz, "HERO-4096.png 不是合法 PNG")
        self.assertGreaterEqual(min(sz), 4096, "HERO 只有 %sx%s —— 不到 4K" % sz)

    def test_page_really_plays_animation(self) -> None:
        """动作自然 = 真播动画 + 真给 PBR 环境 + 真开各向异性。"""
        self.assertTrue(PAGE.is_file(), "标准形象页不在：%s" % PAGE)
        s = PAGE.read_text(encoding="utf-8", errors="replace")
        for need, why in (
            ("AnimationMixer", "没有 AnimationMixer ⇒ 不会播动画"),
            ("crossFadeTo", "没有交叉淡入 ⇒ 切换硬切、看起来假"),
            ("RoomEnvironment", "没有 PBR 环境 ⇒ 材质发闷（实测过）"),
            ("anisotropy", "没有各向异性过滤 ⇒ 斜视纹理糊"),
            ("自由的风", "署名被删了（契约要求不可删）"),
        ):
            self.assertIn(need, s, why)

    def test_page_has_no_iframe(self) -> None:
        """面板必须自己渲染；嵌别人的页就会重演"一墙乱码"。"""
        s = PAGE.read_text(encoding="utf-8", errors="replace")
        self.assertNotIn("<iframe", s.lower(), "标准形象页里出现了 iframe")

    def test_no_dangling_glb_references(self) -> None:
        """页面里写到的每个 .glb 都必须在盘上（旧页曾指向不存在的 portrait-bust）。"""
        for page in (PAGE, AVATAR):
            if not page.is_file():
                continue
            s = page.read_text(encoding="utf-8", errors="replace")
            # ⚠️ 2026-10-18 自纠：第一版写成 `\\.glb`（转义过头）⇒ 要求"反斜杠+glb"，
            #    而路径全是正斜杠 ⇒ **永远匹配不到、判据恒绿**（本仓 P1 假绿那一类）。
            refs = set(re.findall(r"/gbt-master/fs/(holo_pet/[^\"'\s)]+?\.glb)", s))
            refs |= set(re.findall(r"[\"'](raw/[^\"'\s)]+?\.glb)[\"']", s))
            bad = []
            for r in sorted(refs):
                p = ROOT / r if r.startswith("holo_pet/") else DH / r
                if not p.is_file():
                    bad.append("%s → 缺 %s" % (page.name, r))
            self.assertEqual([], bad, "悬空引用：%s" % bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
