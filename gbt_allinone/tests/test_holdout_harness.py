# -*- coding: utf-8 -*-
"""留出集评测**装置**的判据（只守装置，不守准确率）。

🔴 为什么只守装置、不守准确率 —— 这是主人定的纪律，不是我偷懒：
`gbt_allinone/tentacle/bridge.py` 里三批句子旁边写着：
  · 「留出集：先写死，再动别名表。判据：≥80% 才算 §2.2 收工」
  · 「第三批：**这批写下来的那一刻就跑，跑出什么报什么，不得据此调任何词表/权重**。
     一旦为它改过一行，它就废了，必须再写第四批。」
  · 「第四批：同样纪律…若据此调参，第四批作废。」
⇒ 把准确率写成断言，等于**给"照着答案改词表"装了个开关**：测试一红就会有人去调词表，
  那三批句子当场作废。所以这里**只断言装置没坏**：
  ① 三个集合都存在且非空、元素形状是 `(句子, 期望方法)`；
  ② `route_method` 对每句都能给出**结构化**返回（best/confident 字段在），不抛异常。
**实测数字只写在下面的 docstring 里当"某日基线记录"，不作断言。**

## 2026-09-22 首次实跑（第 46 轮 · 补主人那条"写完就跑一次"）
| 集合 | 命中 | 说明 |
|---|---|---|
| `HELD_OUT_PHRASES`（留出集/批1） | **39/39 = 100.0%** | 达到"≥80% 才算收工"的门 |
| `HOLDOUT3_PHRASES`（第三批） | **18/24 = 75.0%** | 未命中 6 条 |
| `HOLDOUT4_PHRASES`（第四批） | **5/16 = 31.2%** | 未命中 11 条 |
| `SEED_PHRASES`（种子集，非留出） | 11/12 = 91.7% | 未命中 1 条 |

⚠️ 口径：批 3/4 是**今天第一次跑**，而词表在这中间被改过很多次 ⇒
这个数是「**当前词表 vs 当年写下的句子**」，**不是**「第一次见的泛化读数」。
⚠️ 另一个实测事实（写进这里备查，不作断言）：批 3/4 的未命中里**过半带 `confident=True`**
（自信地答错），例如「弹窗挡住了，关掉它」期望 `handle_any_dialog` 实得 `kill`、
「把整个屏幕截下来」期望 `screenshot` 实得 `see`。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT, ROOT / "gbt_allinone"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from gbt_allinone.tentacle import bridge as TB  # noqa: E402

SETS = ("HELD_OUT_PHRASES", "HOLDOUT3_PHRASES", "HOLDOUT4_PHRASES", "SEED_PHRASES")


class HoldoutHarnessTests(unittest.TestCase):
    def test_all_batches_exist_and_are_non_empty(self):
        """三批 + 种子集都必须在盘上、非空 —— 少一批就说明有人把评测面删掉了。"""
        for name in SETS:
            rows = getattr(TB, name, None)
            self.assertIsNotNone(rows, "缺少集合 %s（评测面被删/改名了）" % name)
            self.assertGreater(len(rows), 0, "%s 是空的 ⇒ 这条评测没得跑" % name)

    def test_each_entry_is_sentence_expected_method_pair(self):
        """每项必须是 `(句子, 期望方法)` —— 形状坏了，命中率就没有意义。"""
        for name in SETS:
            for i, item in enumerate(getattr(TB, name)):
                self.assertGreaterEqual(len(item), 2, "%s[%d] 不足两项：%r" % (name, i, item))
                sent, want = item[0], item[1]
                self.assertIsInstance(sent, str)
                self.assertTrue(sent.strip(), "%s[%d] 句子是空的" % (name, i))
                self.assertIsInstance(want, str)
                self.assertTrue(want.strip(), "%s[%d] 期望方法是空的" % (name, i))

    def test_router_returns_structured_result_for_every_holdout_sentence(self):
        """`route_method` 对每一句都要给**结构化**返回（不抛异常、字段在位）。

        这条守的是"装置能跑"：只要它不炸、形状在，命中率才是可比的数字。
        **不断言命中率**（理由见模块 docstring：断言准确率=给"照答案改词表"装开关）。
        """
        for name in SETS:
            for sent, want in ((r[0], r[1]) for r in getattr(TB, name)):
                r = TB.route_method(sent)
                self.assertIsInstance(r, dict, "%s: route_method 没回字典（%r）" % (name, sent))
                self.assertIn("best", r, "%s: 缺 best 字段（%r）" % (name, sent))
                self.assertIn("confident", r, "%s: 缺 confident 字段（%r）" % (name, sent))

    def test_confidence_is_boolean_so_calibration_is_measurable(self):
        """`confident` 必须是真布尔 —— 否则"自信地答错"这件事就量不出来。"""
        for name in SETS:
            for sent in (r[0] for r in getattr(TB, name)):
                self.assertIsInstance(TB.route_method(sent).get("confident"), bool,
                                      "%s: confident 不是 bool（%r）" % (name, sent))


if __name__ == "__main__":
    unittest.main()
