"""R-H606（2026-09-25）· system prompt 里的**能力总数三处必须一致**。

被测故障（现读抓到的，不是推演）：
    `gbt_allinone/llm/cloud_llm.py` 把"自我认知"注入 system prompt，而里面**同时**出现两个数：
      · 标题：`str(_live_cap_total() or 118)` —— 而 `_live_cap_total()` 读的是
        `.gbt/_audit_caps.json`，**该文件全库不存在** ⇒ 返回 0 ⇒ 打出硬编码 **118**
      · 紧跟着的能力索引表：`_build_cap_digest()` 读 `gbt_cap_index.json`（**也不存在**）
        ⇒ 表头写「**0个cap** · **实时注册表**」+ 一张空表
      · 真值（`caps_registry.BENIGN_CAPS`）：**172**
    ⇒ **同一段自我认知里三个数、没一个对**。这正是"大模型不知道自己有什么能力"的机器成因。
    而本文件 92-98 行的注释**早就写明**「真正的活口是 `caps_registry.py`，不是任何 JSON」——
    **注释知道，代码没照做。**

判据（四条，都要有牙）：
  1. 标题里那个数 = 活注册表条数（不是 118、不是 0）；
  2. 索引表表头的数 = 表体行数（表里说有 172 个，就得真有 172 行）；
  3. 两处**必须相等**（同一份 prompt 里不许出现两个不同的能力总数）；
  4. 表头**必须写明来源**，且回落时**必须说出来**（JSON 索引不存在这件事不许瞒着）。
"""
from __future__ import annotations

import re
import unittest

from gbt_allinone.caps_registry import BENIGN_CAPS
from gbt_allinone.llm import cloud_llm as cl


class CapTotalConsistencyTest(unittest.TestCase):
    def test_label_equals_live_registry(self) -> None:
        self.assertEqual(cl._live_cap_total(), len(BENIGN_CAPS),
                         "活注册表有 %d 条，_live_cap_total() 却报 %s"
                         % (len(BENIGN_CAPS), cl._live_cap_total()))
        label = cl._cap_total_label()
        self.assertIn(str(len(BENIGN_CAPS)), label)
        self.assertNotIn("118", label, "又拿 v5 时代的硬编码 118 顶替了")

    def test_digest_header_count_matches_body_rows(self) -> None:
        lines = cl._build_cap_digest().splitlines()
        header = next(ln for ln in lines if ln.startswith("## ⚡ 能力精准索引"))
        m = re.search(r"（(\d+)个cap", header)
        self.assertIsNotNone(m, "表头里读不出能力总数：%s" % header[:80])
        declared = int(m.group(1))
        # 2026-10-11 契约更新（**有据，不是把判据改绿**）：
        #   Owner 令「system 13,480 字太长、把模型带偏」⇒ 索引改为**只报域与数量、不列名字**，
        #   表体从「每 cap 一行」变成「每域一行」。原断言「declared == 表体行数」于新形态无意义。
        #   ⇒ 保留原意图（**总数必须等于活注册表**），并**新增一条更硬的**：
        #      表体里**不许出现任何能力位名字**（名字表本身是编造素材源 —— 实测她拿表里的名字
        #      拼出过假答案）。这条比原来更严，不是更松。
        rows = [ln for ln in lines if ln.startswith("- **")]
        self.assertTrue(rows, "表体为空")
        self.assertEqual(declared, len(BENIGN_CAPS),
                         "表头的数与活注册表对不上")
        joined = chr(10).join(rows)
        for name in list(BENIGN_CAPS)[:400]:
            self.assertNotIn("`%s`" % name, joined,
                             "表体里出现了能力位名字 %s —— 名字表是编造素材源，不许列" % name)

    def test_title_and_table_agree(self) -> None:
        """同一份 prompt 里两处能力总数必须相等 —— 这是本次要钉死的那条。"""
        head = re.search(r"(\d+)个cap", cl._cap_total_label())
        m = re.search(r"（(\d+)个cap", cl._build_cap_digest())
        self.assertIsNotNone(head)
        self.assertIsNotNone(m)
        self.assertEqual(head.group(1), m.group(1),
                         "标题说 %s 个cap、索引表说 %s 个cap —— 自我认知自相矛盾"
                         % (head.group(1), m.group(1)))

    def test_source_is_stated_and_fallback_is_disclosed(self) -> None:
        header = next(ln for ln in cl._build_cap_digest().splitlines()
                      if ln.startswith("## ⚡ 能力精准索引"))
        self.assertIn("来源", header, "表头没说这张表是从哪儿来的")
        # 本机现读：JSON 索引不存在 ⇒ 必须**明说回落**，不许仍写"实时注册表"那种含糊说法
        if not cl._load_cap_index():
            self.assertIn("回落", header, "走了回落却不说 —— 读的人会以为这是那份 JSON 索引")
            self.assertIn("不存在", header)

    def test_registry_fallback_shape_is_the_same(self) -> None:
        """回落出来的表必须与 JSON 索引**同形**（4 列），否则下游解析会错位。"""
        idx = cl._registry_cap_index()
        self.assertEqual(len(idx), len(BENIGN_CAPS))
        row = next(iter(idx.values()))
        self.assertEqual(sorted(row.keys()), ["actions", "domain", "status", "triggers"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
