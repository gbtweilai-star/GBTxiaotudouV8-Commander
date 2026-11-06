# -*- coding: utf-8 -*-
"""算子层的机器判据（2026-11-05）。

这一层此前只有手跑脚本，改一个权重没人拦得住。这里钉住的是**口径**，不是数字：

  ① 形状：427 个能力位、每个都有 tokens/graph，索引不能悄悄少一半；
  ② 已知正确：16 条主人原话必须命中且命中对那个位；
  ③ 必须弃权：凭二元组覆盖「看着像」的一律不许发火（这条防的是假绿）；
  ④ 否决：摘掉一个说法后，那个位不再认它，接手的是别人或没人；
  ⑤ 抢单：已被别人稳稳占住的词，不许硬抢（curate 的占用检查）；
  ⑥ 留出集：真话里必须能测出「强证据 / 弱证据」两档，否则 heldout 是假的。

纪律：本文件**只读** —— 不写 `state/operator-index.json`，也不写策展层。
所以 curate/veto 一律用 `apply=False`（它本来就等于干跑）。
"""
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone import operator_index as OI   # noqa: E402

# 开发仓专有夹具：`docs/` 是留出集的语料来源，产品包不带它（也不带全量 wiring）。
# 缺夹具时那两条判据**如实跳过**，不许拿「产品包长得不一样」冒充回归 —— 但也
# 绝不能在开发仓里跳过，否则判据就白写了（下面每条都用同一个开关）。
_ROOT_IS_DEV = (_REPO / "docs").is_dir()

KNOWN = [
    ("看屏幕", "body_see"),
    ("截个屏", "body_see"),
    ("截图", "body_see"),
    ("打开摄像头", "see_camera"),
    ("体检一下系统", "selfscan"),
    ("自检", "selfscan"),
    ("查审计账", "audit_query"),
    ("数一数有多少字", "count_words"),
    ("发邮件", "coze_mail"),
    ("抓取网页", "scrapling"),
    ("回滚", "pipeline_rollback"),
    ("记一笔", "ledger_note"),
    ("看一眼屏幕", "body_see"),
    ("识别图片", "vision"),
    ("本地算力", "local_llm"),
    ("提醒我明天九点开会", "reminder"),
]

ABSTAIN = ["生图", "视频", "权限", "看一眼桌面"]


def _top1(g):
    return ((g.get("top") or [{}])[0] or {}).get("cap")


class TestIndexShape(unittest.TestCase):
    def test_build_covers_every_cap(self):
        from gbt_allinone import caps_registry as CR
        idx = OI.build()
        self.assertEqual(idx["count"], len(CR.BENIGN_CAPS))
        self.assertEqual(set(idx["operators"]), set(CR.BENIGN_CAPS))
        self.assertEqual(idx["curated"] + idx["uncurated"], idx["count"])

    def test_every_record_has_scoring_surface(self):
        idx = OI.build()
        for name, op in idx["operators"].items():
            self.assertTrue(op["tokens"], "%s 没有 tokens ⇒ 打不了分" % name)
            self.assertIn("degree", op["graph"])
            self.assertEqual(op["graph"]["via"], "shared-code")

    def test_family_is_not_from_cap_edges(self):
        if not _ROOT_IS_DEV:
            self.skipTest("产品包不带 docs/ 与全量 wiring：同族门槛按开发仓校准")
        # wiring 里 cap→cap 边为 0，同族只能来自共享 code: 节点。
        # 若哪天 wiring 真的长出 cap 边，这条会提醒我们换回直读。
        idx = OI.build()
        body = idx["operators"]["body_see"]["graph"]
        self.assertIn("body_click", body["cap_neighbors"])
        self.assertGreaterEqual(body["cap_overlap"]["body_click"], 3,
                                "同族门槛：共享 3 个以上实现文件才算一家")


class TestKnownMappings(unittest.TestCase):
    def test_known_phrases(self):
        for q, want in KNOWN:
            g = OI.gate(q)
            self.assertTrue(g.get("hit"), "%s 该发火却没发：%s" % (q, g.get("why")))
            self.assertEqual(_top1(g), want, "%s 判给了 %s" % (q, _top1(g)))


class TestMustAbstain(unittest.TestCase):
    def test_ambiguous_abstains(self):
        for q in ABSTAIN:
            g = OI.gate(q)
            self.assertFalse(g.get("hit"), "%s 不该发火（%s）" % (q, _top1(g)))

    def test_coverage_alone_cannot_fire(self):
        # 「这位有词」≠「这句命中了它的词」。只靠二元组覆盖中标一律弃权。
        for q in ABSTAIN:
            g = OI.gate(q)
            if g.get("hit"):
                continue
            self.assertNotEqual(g.get("why"), None)
        idx, _ = OI.load()
        self.assertTrue(idx["operators"]["vision"]["curated"],
                        "vision 必须仍是「有词」的位，否则这条判据失去对象")


class TestVeto(unittest.TestCase):
    def test_veto_hands_off(self):
        # 不写死具体词：策展层会变，判据不该跟着碎。从当前索引里取一个**现在真有的**。
        idx, _ = OI.load()
        have = sorted((idx["operators"]["vision"].get("iex") or {}))
        self.assertTrue(have, "vision 的 iex 空了 ⇒ 这条判据失去对象")
        target = have[0]
        r = OI.veto("vision", [target], apply=False)
        self.assertTrue(r.get("ok"), r.get("error"))
        eff = (r.get("effect") or [{}])[0]
        self.assertEqual(eff.get("before"), "vision")
        # 判「该位的证据确实降了」—— 摘一个词不必然让整位失去抓握，
        # 但如果分数没降，说明否决根本没进 build（那才是真 bug）。
        self.assertLess(eff.get("after_score"), eff.get("before_score"),
                        "摘掉「%s」后分数没降 ⇒ 否决没进 build" % target)

    def test_veto_requires_existing_phrase(self):
        r = OI.veto("body_see", ["这句话根本不存在"], apply=False)
        self.assertFalse(r.get("ok"))
        self.assertIn("没有对象", r.get("error") or "")


class TestCurationGuard(unittest.TestCase):
    def test_cannot_steal_owned_phrase(self):
        r = OI.curate("vision", ["截图"], apply=False)
        self.assertFalse(r.get("ok"))
        self.assertIn("占住", str(r.get("conflicts") or r.get("error")))

    def test_dry_run_writes_nothing(self):
        before = OI.INDEX.stat().st_mtime_ns
        OI.curate("reminder", ["提醒我"], apply=False)
        self.assertEqual(OI.INDEX.stat().st_mtime_ns, before)


class TestHeldout(unittest.TestCase):
    def test_two_bands_exist(self):
        if not _ROOT_IS_DEV:
            self.skipTest("产品包不带 docs/：留出集语料只存在开发仓")
        h = OI.heldout(0)
        self.assertGreater(h["sentences"], 100, "留出集太小 ⇒ 判据失去对象")
        self.assertGreater(h["fired"], 0)
        self.assertIn("exact", h["bands"])
        self.assertIn("substring", h["bands"])

    def test_quoted_are_real_owner_words(self):
        items = OI._quoted_sentences()
        self.assertTrue(items)
        for it in items[:20]:
            self.assertTrue(str(it["from"]).endswith(".md"))
            self.assertNotIn(chr(10), it["q"])


class TestHintNote(unittest.TestCase):
    """候选提示：只提示、不给执行权；弃权时一个字都不许塞。

    这是「427 压到几个」真正进对话的地方 —— 提示错了不会执行任何东西，
    但会把本机模型往错的方向带，所以判据比 gate 本身更严：只认 hit。
    """

    def test_hit_names_the_cap(self):
        g = OI.gate("看屏幕")
        n = OI.hint_note("看屏幕", gate_result=g)
        self.assertTrue(n["hit"])
        self.assertIn("body_see", n["note"])
        self.assertIn("427", n["note"])
        self.assertLessEqual(len(n["note"]), 200)

    def test_abstain_gives_empty_note(self):
        # 负对照：闸门弃权时必须空 —— 提示里塞候选等于绕过弃权
        for q in ("生图", "视频", "权限"):
            g = OI.gate(q)
            self.assertFalse(g["hit"], q + " 本该弃权")
            n = OI.hint_note(q, gate_result=g)
            self.assertEqual(n["note"], "")
            self.assertEqual(n["caps"], [])

    def test_weak_hit_is_not_injected(self):
        # 「提醒我明天九点开会」gate 是命中的（0.46），但只是"说法被包在长句里"。
        # 提示比路由更严：宁可不说，也不把模型往错的方向带。
        g = OI.gate("提醒我明天九点开会")
        self.assertTrue(g["hit"], "这条本来就该命中，否则判据没对象")
        self.assertLess(float(g["top"][0]["score"]), 1.0)
        n = OI.hint_note("提醒我明天九点开会", gate_result=g)
        self.assertEqual(n["note"], "")
        self.assertIn("弱证据", n["why"])

    def test_topk_is_respected(self):
        g = OI.gate("看屏幕", topk=5)
        n = OI.hint_note("看屏幕", topk=2, gate_result=g)
        self.assertLessEqual(len(n["caps"]), 2)
        self.assertLessEqual(n["note"].count(" / "), 1)

    def test_budget_too_small_returns_empty(self):
        # 装不下就宁可不提示，不许返回半句话
        n = OI.hint_note("看屏幕", gate_result=OI.gate("看屏幕"), max_chars=10)
        self.assertTrue(n["hit"])
        self.assertEqual(n["note"], "")

    def test_never_raises_on_empty_verdict(self):
        n = OI.hint_note(None, gate_result={})
        self.assertFalse(n["hit"])
        self.assertEqual(n["note"], "")


class TestShortPhraseDiscipline(unittest.TestCase):
    """2 字以内的**desc 自动抽出物**不许靠子串把整句判给该位（2026-11-05）。

    血账：`uia_tree` 的「常用说法」里有个裸词「控件」，于是「往控件里输入」
    被判成"读控件树"，真动作 `body_type` 只排第二。同形态还有
    量化 / 原生 / 按钮 / 边界 / 加载 / 通知 / 映射。

    为什么按**出处**切、不按长度切：`desc` 的「常用说法」是正则从散文里抠的，
    抠出来 1~2 字的是**术语**（概念），不是「一句话怎么说」；人工策展层
    （`state/operator-curation.json`）是照着原话写的，2 字的「截屏 / 截图」
    本来就是指令，不能误伤。
    """

    def test_two_char_desc_word_does_not_fire(self):
        for q in ("7.6 B 的量化权重", "Vulkan 快但输出乱码，已判死"):
            g = OI.gate(q)
            self.assertFalse(g.get("hit"), "%s 被 2 字 desc 词判给了 %s" % (q, _top1(g)))

    def test_two_char_curated_word_still_fires(self):
        g = OI.gate("帮我截屏")
        self.assertTrue(g.get("hit"), "策展词「截屏」被误伤：%s" % g.get("why"))
        self.assertEqual(_top1(g), "body_see")

    def test_same_word_counts_only_when_curated(self):
        # 同一个 2 字词：desc 抽出来的不算证据，人写进策展层的算。
        def idx_with(phrases, curation):
            return {"operators": {"p": {
                "cap": "p", "kind": "cap", "name": "p", "domain": "x",
                "tokens": [], "phrases": list(phrases), "lexicon": [],
                "iex": {}, "curation": list(curation), "curated": True}}}

        q = "这段量化权重很安静"
        auto = OI.rank(idx_with(["量化"], []), q)
        hand = OI.rank(idx_with(["量化"], ["量化"]), q)
        self.assertFalse(auto["top"][0]["phrase_hit"], "desc 抽出的 2 字词仍被当成证据")
        self.assertTrue(hand["top"][0]["phrase_hit"], "策展的 2 字词被误伤")


class TestPhrasesOf(unittest.TestCase):
    def test_stop_markers(self):
        self.assertEqual(OI.phrases_of("常用说法：看屏幕 / 截个屏。其余略"), ["看屏幕", "截个屏"])
        self.assertEqual(OI.phrases_of("没有任何标记的说明"), [])


if __name__ == "__main__":
    unittest.main()
