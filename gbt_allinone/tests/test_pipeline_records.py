# -*- coding: utf-8 -*-
"""流水线记录列表：**截断必须报出来**（第 41 轮补的判据）。

由来（同一类错报的第二处）：`pipeline.list_records` 原来返回
`{"records": out, "count": len(out)}`，而 `out` 是 `sorted(...)[:limit]` 之后的一页
⇒ 问"流水线一共多少条记录"会拿到**页大小**。
同仓现成样板是 `tentacle/omni_fs.py:162` 的 `file_list`：`count` 与 `truncated` 一起给。

判据**两边都钉**（只钉"截断时报 True"的话，一个"永远报 True"的实现也能过）：
  ① 空 ⇒ count=0 / total=0 / truncated=False
  ② 未截断 ⇒ count=total=3 / truncated=False
  ③ 截断 ⇒ count=2 / total=3 / truncated=True，且 note 里点明还剩几条没列

安全：记录只写进**隔离 store**（`GBT_STORE_DIR` 指到临时目录，由 tests 包的启动闸保证），
并在用例结束时清掉自己造的那几条；不碰生产。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT, ROOT / "gbt_allinone"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from gbt_allinone import _paths  # noqa: E402
from gbt_allinone import pipeline as P  # noqa: E402


class PipelineRecordListingTests(unittest.TestCase):
    def setUp(self):
        self._rec = Path(_paths.STORE_DIR) / "pipeline" / "records"
        self._made = []

    def tearDown(self):
        for f in self._made:
            try:
                if f.exists():
                    f.unlink()
            except OSError:
                pass

    def _seed(self, n: int):
        self._rec.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            f = self._rec / ("zz_probe_%02d.json" % i)
            f.write_text(json.dumps({"name": "zz_probe_%02d" % i}), encoding="utf-8")
            self._made.append(f)

    # 🔴 第 93 轮修：原来这两条写死 `limit=20`，而**真实 store 里累积的流水线记录早已超过 20 条**
    #    ⇒ `truncated = len(_all) > limit` 是**真的为真** ⇒ 两条"未截断"断言全塌。
    #    **两条断言的意思没错，错在它们依赖"目录几乎是空的"这个前提。**
    #    ⇒ 把页大小放到远大于真实条数（**不再依赖盘上状态**），断言的语义一个字没改。
    #    ⚠️ 截断那条（`test_truncated_listing_must_say_so_and_give_the_real_denominator`）不受影响 ——
    #       它本来就该被截断，所以它照旧用小 limit。
    NO_TRUNC = 10 ** 6

    def test_empty_listing_is_not_truncated(self):
        r = P.list_records(limit=self.NO_TRUNC)
        self.assertEqual(r["total"], len([p for p in self._rec.glob("*.json")])
                         if self._rec.exists() else 0)
        self.assertFalse(r["truncated"], "没截断却报截断 = 另一种错报")
        self.assertIn("未截断", r["count_note"])

    def test_full_listing_reports_equal_count_and_total(self):
        self._seed(3)
        r = P.list_records(limit=self.NO_TRUNC)
        self.assertGreaterEqual(r["total"], 3, "total 是**目录里的真分母**，不许小于造出来的条数")
        self.assertFalse(r["truncated"])
        self.assertEqual(r["count"], r["total"], "没截断时两页数应当相等")

    def test_truncated_listing_must_say_so_and_give_the_real_denominator(self):
        self._seed(3)
        r = P.list_records(limit=2)
        self.assertEqual(r["count"], 2, "count 是本页条数")
        self.assertGreaterEqual(r["total"], 3, "被截断时必须交出真分母")
        self.assertTrue(r["truncated"], "被截断却不说 ⇒ 读的人把页大小当成总数")
        self.assertIn("截断", r["count_note"])
        self.assertIn("没列", r["count_note"], "要说清还有多少条没列出来")


if __name__ == "__main__":
    unittest.main()
