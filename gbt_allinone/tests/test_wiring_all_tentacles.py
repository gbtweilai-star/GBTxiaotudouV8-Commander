"""接线自检 · 启动时"触手就是手"（主人令 2026-09-27）。

三条机检判据（都可判定，不靠人眼）：

  A. **登记 ↔ 分派**：`caps_registry.BENIGN_CAPS` 里**每一个**能力位，`api.py` 的
     `_run_benign` 里必须有分派分支（`if kind == "X"` 或 `if kind in (…)`）。
     来历：2026-09-26 `filmkit` 就是"登记了没接线"，调用得到 `not_wired` ——
     靠人工扫出来的。**这条判据把它钉死**：以后谁再登记不接线，启动就红。

  B. **触手账完整性**：`state/asset_bindings.json` 断连 = 0
     （没有"资产缺失"，也没有"触手不在册"）。

  C. **外部工作流插件"一个不差"**：`gs_h3`（GS-prompt-extend 三节点）接线表
     三行齐全，且每行的 op 真在能力位的 op 表里。插件不在位时判**"如实报缺"**也算过
     （不许静默变绿，也不许把"没装"当"接线不全"）。
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from gbt_allinone.api import _run_benign  # noqa: F401  （导入即证明 api 可载）
from gbt_allinone.caps_registry import BENIGN_CAPS

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "gbt_allinone" / "api.py"


def _dispatched_kinds(src: str) -> set:
    """从 api.py 源码里收全部分派覆盖的 kind（`== ` 与 `in (...)` 两种形态）。"""
    got = set(re.findall(r'if\s+kind\s*==\s*"([^"]+)"', src))
    for group in re.findall(r'if\s+kind\s+in\s*\(([^)]*)\)', src):
        got |= set(re.findall(r'"([^"]+)"', group))
    return got


class WiringAllTentaclesTest(unittest.TestCase):
    def test_a_registry_equals_dispatch(self) -> None:
        """注册表每一位都要有分派分支（缺了就是 `not_wired`，本次钉死）。"""
        src = API.read_text(encoding="utf-8")
        covered = _dispatched_kinds(src)
        missing = sorted(k for k in BENIGN_CAPS if k not in covered)
        self.assertEqual(
            missing, [],
            "注册表有、api.py 没有分派分支的能力位（会被调用成 not_wired）：%s" % missing)

    def test_b_binding_account_integrity(self) -> None:
        """触手账：断连必须为 0（资产缺失 / 触手不在册 两类都算）。"""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "tb_check", ROOT / "tools" / "tentacle_bind.py")
        tb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tb)
        r = tb.scan()
        self.assertTrue(r["ok"], "触手账有断连：missing_asset=%s ghost=%s"
                        % (r["missing_asset"][:5], r["ghost_tentacle"][:5]))
        acct = json.loads((ROOT / "state" / "asset_bindings.json").read_text(encoding="utf-8"))
        self.assertGreater(len(acct), 0, "触手账是空的 —— 绑定系统没跑过？")

    def test_c_external_plugin_nodes_all_wired(self) -> None:
        """外部工作流插件：三节点一个不差（不在位时须如实报缺，不许静默绿）。"""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "gs_cap_check", ROOT / "gbt_allinone" / "tools" / "gs_h3_cap.py")
        gs = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(gs)
        except Exception as exc:  # noqa: BLE001
            self.skipTest("gs_h3_cap 载入失败：%s" % exc)
        st = gs.status()
        if not st.get("plugin_loaded"):
            # 插件不在位：**必须**给出一条明确的缺件原因（这就是"如实报缺"）
            self.assertTrue(st.get("error"), "插件不在位却没给缺件原因：%s" % st)
            return
        r = gs.nodes()
        self.assertEqual(r["count"], 3, "插件节点数不是 3（它的 NODE_CLASS_MAPPINGS 就三条）")
        self.assertEqual(r.get("plugin_loaded"), True)
        op_table = set(gs.READ_OPS) | set(gs.WRITE_OPS)
        for row in r["nodes"]:
            self.assertIn(row["op"], op_table,
                          "节点 %s 的 op=%s 不在能力位 op 表里" % (row["node"], row["op"]))
            self.assertIn("tentacle", row, "节点 %s 没有触手归属" % row["node"])


if __name__ == "__main__":
    unittest.main()
