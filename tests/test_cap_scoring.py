# -*- coding: utf-8 -*-
"""能力位路由判据 · 打分是**安全面**（`omni run` 据此自动执行），必须有金标准。

## 为什么立这条

2026-11-05 实测：`score_cap` 的三项（名命中 ×3 / 说明命中 ×1.5 / 域词命中 ×1.0）
**都没有按语料长度归一**，于是：

    无关句「今天天气不错适合出去走走」   → 1.50
    噪声词「嗯嗯好的可以我想一下再说」   → **4.50**
    真查询（打开摄像头 / 扫病毒 …）      → 3 ~ 6

三者**完全重叠** ⇒ cap 通道当时根本没有可用的阈值，`omni ask` 把噪声和真命中排成一模一样。

## 金标准从哪来（**不是我编的**）

能力位自己的 `desc` 里写着「常用说法：A / B / C」（`AGENTS.md` §4.1 就是用它抽触发词的）。
那是**仓内作者写下的真实人话**，用它当金标准，判据就不会被我自己编的句子带着走。

剔除规则：**同一句话被多个能力位声明 = 天生歧义，剔除**（例如 `卡片` 同时被 `ui_kit`
和 `design_atlas` 声明、`动画` 被三个位声明）。留着等于要求模型猜作者的偏好。

## 读数（2026-11-05 改打分前后）

| 指标 | 改前 | 改后 |
|---|---|---|
| top-1 命中（203 句干净集） | 69% | **76%** |
| top-3 命中 | 85% | **91%** |
| 噪声句最高分 | 4.50 | **1.71** |
| 正确位分数中位 | — | 6.32（94% 在 5.0 以上） |

噪声 ≤1.71、真命中 ≥5.0（绝大多数）⇒ `rank(min_hit_cap=2.0)` 这个阈值**有据可依**。

## 已知歧义（数据层，不是打分能解决的）

`万能插` 这 3 个字被 **8 个位**同时自称（`omni_plug` 本体 + `wf_*` 全家 + `omni_open`），
因为 `wf_*` 的 desc 都以「万能插执行引擎：」开头。所以「万能插」这一句 top-1 拿到的是
`wf_cache_clear` 而非 `omni_plug` —— **要修得改那 8 条 desc 的措辞**，属编辑决策，
不在打分这一层。本判据不把它算进指标（`assert` 只看比例，不逐句锁死）。
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import sys
import unittest
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
OMNI = ROOT / "tools" / "codex-scripts" / "omni.py"

# 「常用说法：A / B / C」——能力位 desc 里的自述人话
PHRASE = re.compile(r"常用说法[：:]\s*([^。\n]+)")

# 噪声句：必须一条都不命中（阈值 2.0 之下）
NOISE = [
    "今天天气不错适合出去走走",
    "嗯嗯好的可以我想一下再说",
]

# 改打分实测基线（2026-11-05）：留 2 个点余量以免 desc 微调就红，
# 但**只许往上，不许往下** —— 掉下来说明尺子又歪了。
MIN_TOP1 = 0.74
MIN_TOP3 = 0.89


def _load_omni():
    spec = importlib.util.spec_from_file_location("omni_for_capscore", OMNI)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # type: ignore[union-attr]
    return mod


def _golden() -> list:
    """(人话, 期望能力位)。来源：能力位 desc 的「常用说法」，剔除多名声明的歧义句。"""
    sys.path.insert(0, str(ROOT))
    from gbt_allinone import caps_registry as CR

    raw = []
    for c in CR.all_caps():
        m = PHRASE.search(c.get("desc") or "")
        if not m:
            continue
        for ph in re.split(r"[／/、]", m.group(1)):
            ph = ph.strip()
            if 2 <= len(ph) <= 16:
                raw.append((ph, c["name"]))

    owners = defaultdict(set)
    for ph, name in raw:
        owners[ph].add(name)
    return [(ph, name) for ph, name in raw if len(owners[ph]) == 1]


class TestCapScoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.omni = _load_omni()
        cls.golden = _golden()

    def test_golden_set_is_real(self):
        """金标准必须真来自盘上（空集合过关 = 假绿）。"""
        self.assertGreaterEqual(len(self.golden), 150,
                                "金标准只剩 %d 句 —— 要么 desc 里的『常用说法』被改没了，"
                                "要么抽取规则坏了" % len(self.golden))
        self.assertGreaterEqual(len({n for _, n in self.golden}), 15,
                                "金标准覆盖的能力位太少")

    def _accuracy(self):
        top1 = top3 = 0
        miss = []
        for q, want in self.golden:
            r = self.omni.rank(q, top=8)
            top = [c["kind"] for c in r["caps"][:3]]
            if top and top[0] == want:
                top1 += 1
            elif want in top:
                top3 += 1
            else:
                miss.append((q, want, top[:2]))
        n = len(self.golden)
        return top1 / n, (top1 + top3) / n, miss

    def test_top1_ratchet(self):
        """top-1 命中率只许升不许降。"""
        a1, a3, miss = self._accuracy()
        self.assertGreaterEqual(
            a1, MIN_TOP1,
            "能力位 top-1 命中掉到 %.0f%%（基线 76%%，本次 %d 句里打偏 %d 句）。\n"
            "⇒ 检查 `score_cap` 的三项是否又被改回「不按长度归一」：\n"
            "   说明命中*1.5 / 域词命中*1.0 不归一时会与噪声重叠（实测 4.50）。\n"
            "打偏样例：%s" % (a1 * 100, len(self.golden), len(miss), miss[:6]))
        self.assertGreaterEqual(
            a3, MIN_TOP3,
            "能力位 top-3 命中掉到 %.0f%%（基线 91%%）" % (a3 * 100))

    def test_noise_scores_below_threshold(self):
        """噪声句必须一个 cap hit 都没有 —— 这是阈值 2.0 存在的意义。

        改打分的**直接动机**就是这条：改前噪声词能拿 4.50，与真命中重叠，
        `omni ask` 于是把噪声排得和真命中一模一样。
        """
        for q in NOISE:
            r = self.omni.rank(q, top=8)
            self.assertEqual(
                [c["kind"] for c in r["caps"]], [],
                "噪声句「%s」居然命中了能力位：%s\n"
                "⇒ `score_cap` 又没按语料长度归一了（噪声会与真命中重叠）"
                % (q, [(c["kind"], c["score"]) for c in r["caps"][:3]]))

    def test_real_query_hits(self):
        """真查询必须命中（否则阈值把正经需求也挡了）。"""
        r = self.omni.rank("打开摄像头", top=8)
        kinds = [c["kind"] for c in r["caps"]]
        self.assertIn("see_camera", kinds,
                      "「打开摄像头」没打到 see_camera，实得 %s" % kinds[:5])
        self.assertEqual(kinds[0], "see_camera",
                         "「打开摄像头」首选不是 see_camera：%s" % kinds[:3])

    def test_brand_word_disambiguated(self):
        """「万能插」必须落到本体 `omni_plug`，不许被借名的兄弟抢走。

        2026-11-05 处置：7 个 `wf_*` 的 desc 前缀原是「万能插执行引擎：」、`omni_open` 是
        「万能插·全自动打开：」，于是「万能插」这 3 个字被 8 个位同时自称。
        已把前缀改准（工作流引擎 / 全自动打开），并恢复标题精确匹配。
        """
        r = self.omni.rank("万能插", top=8)
        kinds = [c["kind"] for c in r["caps"]]
        self.assertTrue(kinds, "「万能插」一个位都没命中")
        self.assertEqual(kinds[0], "omni_plug",
                         "「万能插」首选不是 omni_plug，实得 %s\n"
                         "⇒ 检查是不是又有位的 desc 拿「万能插」当前缀了" % kinds[:4])

    def test_quotation_is_preserved(self):
        """**引述主人原话的段落一个字不许动** —— 防后人（包括我）做"清理"时把史料洗掉。

        `train_ground` 的 desc 里有主人令原话：「必须使用万能插来无死角训练大模型…」。
        改动措辞时如果顺手把「万能插」全替换掉，就把引文篡改了。
        """
        sys.path.insert(0, str(ROOT))
        from gbt_allinone import caps_registry as CR
        cap = next((c for c in CR.all_caps() if c["name"] == "train_ground"), None)
        self.assertIsNotNone(cap, "找不到 train_ground")
        desc = cap.get("desc") or ""
        self.assertIn("必须使用万能插来无死角训练",
                      desc,
                      "train_ground 里主人令的原话被改了 —— 引述不许动")

    def test_gate_is_not_loosened_by_scoring(self):
        """**安全面**：打分只决定排序，能不能自动执行由 `auto_run_verdict` 单独判。

        这条钉死"改排序不许顺手把门放松"：凡有必填参数或带侧效应的位，
        无论分数多高，都不许被自动执行。
        """
        atlas = self.omni.load_atlas()
        risky = [c for c in atlas["caps"]
                 if (c.get("requires_params") or c.get("needs_confirmation"))][:40]
        self.assertGreater(len(risky), 0, "一个需要参数/需确认的位都没有？注册表读坏了")
        bad = []
        for c in risky:
            ok, _why = self.omni.auto_run_verdict(c)
            if ok:
                bad.append(c["kind"])
        self.assertEqual(bad, [],
                         "这些位需要参数或带侧效应，却被判定可以自动执行：%s\n"
                         "⇒ 打分重写不许改动 `auto_run_verdict` 的判据" % bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
