# -*- coding: utf-8 -*-
"""`risky` 榜的派生物分流 · 防回退（2026-11-05）。

**起因**：口径收紧到「按强边排」之后，`risky` 榜第二名变成了
`code:state/console-data.js`（强边 777）—— 但它是 `tools/gen-console-data.py`
的产物，文件头明写「自动生成，勿手改」。谁照着榜单去"修最危险的件"，
改的就是它：白改，下次跑生成器就没了。

`_is_copy` 已经把历史副本（`state/mirror/`、`atomic-sync/backup/`、`.archive/`）
单列成 `copies`；派生物是**同类干扰、不同成因**（副本是快照，派生物是产物），
所以另立 `derived`，不合并 —— 跟进动作不一样：副本要跟，派生物要重跑生成器。

三条判据：
  A. `_is_derived` 认得出已知派生物（生成器产物）
  B. `_is_derived` 不误伤源码（api.py 这种必须有内建依赖的件）
  C. 端到端：派生物不出现在 `top`，必须进 `derived`
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# gbt_allinone/tests 会拒绝在已绑定生产 store 的进程里跑，先钉一个临时 store
os.environ.setdefault(
    "GBT_STORE_DIR",
    os.path.join(os.environ.get("TEMP", "/tmp"), "gbt_test_store"),
)

DERIVED_SAMPLE = "code:state/console-data.js"
SOURCE_SAMPLE = "code:gbt_allinone/api.py"


def _is_derived(node):
    from gbt_allinone.tools.impact_check import _is_derived as f
    return f(node)


def _risky(n=10):
    from gbt_allinone import api
    r = api.run_task("impact_check", {"op": "risky", "n": n})
    for _ in range(5):
        if isinstance(r, dict) and isinstance(r.get("result"), dict):
            r = r["result"]
        else:
            break
    assert isinstance(r, dict) and r.get("op") == "risky", "risky 返回体异常：%r" % (r,)
    return r


class TestDerivedDetect(unittest.TestCase):
    """A/B · 纯函数判据（不加载图）"""

    def test_a_known_derived_recognised(self):
        if not os.path.isfile(os.path.join(ROOT, DERIVED_SAMPLE[5:])):
            self.skipTest("state/console-data.js 不存在（未跑过生成器）")
        self.assertTrue(
            _is_derived(DERIVED_SAMPLE),
            "认不出 %s —— 生成器产物必须被判为派生物，否则它会挤进 risky 榜" % DERIVED_SAMPLE,
        )

    def test_b_source_not_misjudged(self):
        self.assertFalse(
            _is_derived(SOURCE_SAMPLE),
            "把 %s 误判成派生物 —— 它是真源码，排除掉就会漏掉最危险的那个件" % SOURCE_SAMPLE,
        )

    def test_b2_non_code_nodes_ignored(self):
        for node in ("cap:impact_check", "page:AGENTS.md", "dir:tools"):
            self.assertFalse(_is_derived(node), "%s 不该进入派生物判定" % node)


class TestRiskyRouting(unittest.TestCase):
    """C · 端到端：分流真的生效"""

    def test_c_derived_not_in_top(self):
        r = _risky(10)
        top = [x["node"] for x in (r.get("top") or [])]
        derived = [x["node"] for x in (r.get("derived") or [])]
        self.assertNotIn(
            DERIVED_SAMPLE, top,
            "派生物又挤回 top 了 —— 榜首应当是源码，不是改了会被覆盖的产物",
        )
        if os.path.isfile(os.path.join(ROOT, DERIVED_SAMPLE[5:])):
            self.assertIn(
                DERIVED_SAMPLE, derived,
                "派生物既不在 top 也不在 derived —— 它被吞掉了，读者再也看不到它",
            )

    def test_c2_api_still_first(self):
        r = _risky(5)
        top = r.get("top") or []
        self.assertTrue(top, "risky 返回空榜")
        self.assertEqual(
            top[0]["node"], SOURCE_SAMPLE,
            "榜首应是 api.py（强边最高、且是真源码），实得 %r" % (top[0]["node"],),
        )

    def test_c3_counts_add_up(self):
        r = _risky(10)
        self.assertEqual(
            r["scanned"], r["main_scanned"] + r["copies_scanned"] + r["derived_scanned"],
            "scanned 应等于三类之和：%r" % {k: r.get(k) for k in
                                            ("scanned", "main_scanned",
                                             "copies_scanned", "derived_scanned")},
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
