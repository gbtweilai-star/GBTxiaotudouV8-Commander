# -*- coding: utf-8 -*-
"""路由 n-gram 的**数字噪声**判据（2026-10-13）。

背景（实测）：`semantic_route.grams()` 是全框架唯一实现；原来把**纯数字串**也当词，
于是人话里一带尺寸/端口/时长就成片假命中 —— 单独喂 `"2560"` ⇒ `media_license` /
`media_publish` / `memory_bank` / `tentacle_comfy_bridge` / `code_patch` **各得 3.0**。

本判据只钉**已修的那一条**（纯数字串不入词）+ 一条**已知缺口**（如实标 skip，不许假装过）。
跑法：`py -3.14 -m unittest gbt_allinone.tests.test_router_grams -v`
"""
import json
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone.semantic_route import grams            # noqa: E402

_ATLAS = _REPO / "state" / "skill_atlas.json"


_OMNI = None


def _omni():
    """按路径装载 `omni.py`（它不在包内），只装一次 —— 打分与 `omni ask` **同一套实现**。"""
    global _OMNI
    if _OMNI is not None:
        return _OMNI
    sys.path.insert(0, str(_REPO / "tools" / "codex-scripts"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_omni_probe", _REPO / "tools" / "codex-scripts" / "omni.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    _OMNI = m
    return m


def _score_kind(ig: set, cap: dict, kind: str) -> float:
    return _omni().score_cap(ig, cap)[0]


def _score_all(intent: str):
    """用**现读图鉴**跑一遍真实打分（与 omni ask 同一套 n-gram 与权重）。"""
    m = _omni()
    atlas = json.loads(_ATLAS.read_text(encoding="utf-8"))
    ig = grams(intent)
    rows = [(m.score_cap(ig, c)[0], c["kind"]) for c in atlas.get("caps") or []]
    return sorted([r for r in rows if r[0] > 0], reverse=True)


class TestRouterDigitNoise(unittest.TestCase):
    def test_pure_digits_are_not_words(self):
        self.assertEqual(grams("2560"), set(), "纯数字串不许进词表（它就是噪声源）")
        self.assertEqual(grams("1080"), set())

    def test_alphanumeric_tokens_survive(self):
        """带字母/单位的照留 —— 别把 `4k` / `1080p` 这类真信息一起踢掉。"""
        self.assertIn("4k", grams("4k"))
        self.assertTrue(grams("1080p") - {""}, "1080p 至少该留下带字母的 gram")
        self.assertNotIn("10", grams("1080p"), "纯数字部分仍不许进")

    def test_whitespace_grams_are_not_words(self):
        """🔴 空白不承载语义：**含空白的 gram 一律不算词**。
        实测病象：`把这张图放大到 2560 并锐化一下` 里，三个无关位各拿 4.5，命中项**全是**
        `' 2'` / `'0 '` / `'到 '` 这类跨空格垃圾（真该命中的那条腿只靠 `放大` 拿 1.5）。"""
        g = grams("放大到 2560 并")
        self.assertTrue(all(not any(c.isspace() for c in x) for x in g),
                        "含空白的 gram 混进来了：%s" % sorted(x for x in g if any(c.isspace() for c in x)))
        self.assertIn("放大", g, "非空白的照留")
        self.assertNotIn("a ", grams("a b"))
        self.assertNotIn(" b", grams("a b"))

    @unittest.skipUnless(_ATLAS.is_file(), "图鉴不在 ⇒ 跳过（不假装跑过）")
    def test_negative_control_pure_digits_score_nothing(self):
        """🔴 硬负控：纯数字串对**每一个能力位**都不得产生命中（实修前是 5 个位各 3.0）。"""
        hits = _score_all("2560")
        self.assertEqual(hits, [], "纯数字串还在产生假命中：%s" % hits[:5])

    @unittest.skipUnless(_ATLAS.is_file(), "图鉴不在 ⇒ 跳过")
    def test_positive_control_image_legs_reach_the_front(self):
        """🔴 **硬正控**（上一轮它是以 skip 记的缺口，现在必须真过）：
        `把这张图放大到 2560 并锐化一下` ⇒ `comfy_native` / `zimage_rewash` **至少一条进前三**。"""
        top = _score_all("把这张图放大到 2560 并锐化一下")[:3]
        names = [n for _s, n in top]
        self.assertTrue(set(names) & {"comfy_native", "zimage_rewash"},
                        "图像两条腿都没进前三 ⇒ 路由又把真候选挤掉了：%s" % names)

    @unittest.skipUnless(_ATLAS.is_file(), "图鉴不在 ⇒ 跳过")
    def test_truncation_no_longer_breaks_routing(self):
        """🔴 **截断不许影响路由**（2026-10-13 根修的正控）：
        图鉴把 desc 截到 300 字，但被切掉的那段另存 `desc_tail` 并**接回打分语料**。
        判据：① 每个 `desc_truncated=true` 的位都必须**有非空 desc_tail**；
        ② 取三个被截断位，用**只在尾部出现**的词去问 ⇒ 现读得分必须**高于**"把尾部拿掉"时的得分。
        """
        atlas = json.loads(_ATLAS.read_text(encoding="utf-8"))
        caps = {c["kind"]: c for c in atlas["caps"]}
        trunc = [c for c in caps.values() if c.get("desc_truncated")]
        self.assertTrue(trunc, "图鉴里没有截断位？那这条判据失去对象（不是通过）")
        for c in trunc:
            self.assertTrue((c.get("desc_tail") or "").strip(),
                            "%s 被标截断却没有 desc_tail ⇒ 尾部触发词又丢了" % c["kind"])
        for kind in ("key_gateway", "brain_unify", "ux_doctrine"):
            c = caps.get(kind)
            self.assertIsNotNone(c, "图鉴里找不到 %s（换个位或更新名单）" % kind)
            head_g, tail_g = grams(c["desc"]), grams(c.get("desc_tail") or "")
            # ⚠️ 挑词规矩要跟 `grams` 一致：**不能挑含空白的、也不能挑纯数字的** ——
            #    那种 gram 进不了打分语料（两侧都被踢），拿它当问句会得出"没修好"的**假结论**
            #    （本判据上一版就踩了：探针挑到含空格的 gram ⇒ 意图 n-gram 为空 ⇒ 两边都是 0）。
            only_tail = sorted(g for g in (tail_g - head_g)
                               if not g.isdigit() and not any(c.isspace() for c in g))
            self.assertTrue(only_tail, "%s 没有「只在尾部出现」的词 ⇒ 换一个位" % kind)
            w = only_tail[len(only_tail) // 2]
            ig = grams(w)
            s_off = _score_kind(ig, {**c, "desc_tail": ""}, kind)
            s_on = _score_kind(ig, c, kind)
            self.assertGreater(s_on, s_off,
                               "截断仍在吃掉尾部触发词：%s 问「%s」 截断生效=%.1f 现读=%.1f"
                               % (kind, w, s_off, s_on))

    @unittest.skipUnless(_ATLAS.is_file(), "图鉴不在 ⇒ 跳过")
    def test_skill_side_truncation_also_does_not_break_routing(self):
        """🔴 **技能侧同一个坑**（实测 **97/386** 条描述超 400 字被静默截断）现已同法修：
        截断只影响显示 —— 被切掉的那段另存 `desc_tail` 并接回打分语料。
        判据：① 每个 `desc_truncated` 技能都必须有非空 `desc_tail`；
              ② 取三条截断技能，用「只在尾部出现」的词 ⇒ 现读命中数必须**多于**把尾部拿掉时。"""
        atlas = json.loads(_ATLAS.read_text(encoding="utf-8"))
        trunc = [s for s in atlas["skills"] if s.get("desc_truncated")]
        self.assertTrue(trunc, "技能侧没有截断位？那这条判据失去对象（不是通过）")
        for s in trunc:
            self.assertTrue((s.get("desc_tail") or "").strip(),
                            "技能 %s 被标截断却没有 desc_tail ⇒ 尾部触发词又丢了" % s["name"])
        checked = 0
        for s in trunc:
            head, tail = grams(s["desc"]), grams(s.get("desc_tail") or "")
            only = sorted(g for g in (tail - head)
                          if len(g) >= 2 and not g.isdigit() and not any(c.isspace() for c in g))
            if not only:
                continue
            w = only[len(only) // 2]
            ig = grams(w)
            base = "%s %s %s %s" % (s["name"], s["displayName"], s["desc"], " ".join(s["triggers"]))
            off = len(ig & grams(base))
            on = len(ig & grams(base + " " + (s.get("desc_tail") or "")))
            self.assertGreater(on, off, "技能 %s 的尾部词「%s」仍进不了路由（%d→%d）"
                               % (s["name"], w, off, on))
            checked += 1
            if checked >= 3:
                break
        self.assertGreaterEqual(checked, 3, "没找到三条可测的技能截断位")


if __name__ == "__main__":
    unittest.main(verbosity=2)
