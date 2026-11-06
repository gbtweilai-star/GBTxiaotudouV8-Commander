# -*- coding: utf-8 -*-
"""接线图口径固化 · 防四处回退（2026-11-05）。

钉死四件事，都可机检、不靠人眼：

  A. **口径版本三方一致**：`wiring-build.WEIGHT_RULE_VERSION` ==
     `wiring.json.weight_rule.version` == `tactile_tree.MY_WEIGHT_RULE`。
     来历：2026-11-05 加 import 层时，wiring-build 改成 v3 而 tactile_tree 仍是 v2 ——
     读端**不报错**，只是悄悄「退回自建」，那张图白算了。这类漂移没有声音，
     所以必须有机检。

  B. **能力位 desc 不写死读数**：`impact_check` 的 desc 里不许出现 4 位以上裸数字。
     来历：原 desc 写「现读 6301 节点 / 951536 有向边」，而图重建三次它错了三次
     （6305→6306，边 97816→102394）。数字一律走 `op=status` 现查。

  C. **生产快照与注册表一致**：`data/capabilities.json` 里 impact_check 的 desc
     必须逐字等于注册表里的 desc。
     来历：这份快照被 cap_self / commander / pulse_core / orchestration / catalog /
     model_bridge / static_check **七个模块**读取，改注册表不重导出，读端拿到的还是旧 desc。

  D. **impl 边在**：`cap:codex_tools` 必须 1 跳直达
     `code:gbt_allinone/codex_bridge.py`。
     来历：v3 之前这条边不存在 —— cap↔code 只靠「文件里出现这个能力名的字符串」，
     而实现件 `codex_bridge.py` 里根本没有 "codex_tools" 四个字（派发写在 api.py），
     于是能力位到本体永远 2 跳。v4 从 api.py 的 `if kind ==` 分支静态挖出实现模块。
"""
from __future__ import annotations

import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WIRING = os.path.join(ROOT, "state", "model-pack", "wiring.json")
BUILDER = os.path.join(ROOT, "tools", "codex-scripts", "wiring-build.py")
SNAPSHOT = os.path.join(ROOT, "data", "capabilities.json")


def _wiring() -> dict | None:
    if not os.path.exists(WIRING):
        return None
    with open(WIRING, encoding="utf-8") as fh:
        return json.load(fh)


class TestWeightRuleVersion(unittest.TestCase):
    """A. 口径版本三方一致。"""

    def test_three_way_consistent(self):
        w = _wiring()
        if w is None:
            self.skipTest("wiring.json 还没建（开发仓正常状态）")
        graph_ver = (w.get("weight_rule") or {}).get("version")

        with open(BUILDER, encoding="utf-8") as fh:
            src = fh.read()
        m = re.search(r"^WEIGHT_RULE_VERSION\s*=\s*(\d+)", src, re.M)
        self.assertIsNotNone(m, "wiring-build.py 里找不到 WEIGHT_RULE_VERSION")
        builder_ver = int(m.group(1))

        from gbt_allinone import tactile_tree as tt
        reader_ver = tt.MY_WEIGHT_RULE

        self.assertEqual(
            graph_ver, builder_ver,
            "图里的口径 v%s 与构建器 v%s 不一致 —— 需要重建 wiring.json"
            % (graph_ver, builder_ver))
        self.assertEqual(
            reader_ver, builder_ver,
            "读端 tactile_tree.MY_WEIGHT_RULE=v%s 跟不上构建器 v%s —— "
            "它不会报错，只会**悄悄退回自建**，那张图白算"
            % (reader_ver, builder_ver))

    def test_impl_kind_registered(self):
        """v4 起 KIND_BASE 必须有 impl 键，否则 impl 边权重无处落。"""
        with open(BUILDER, encoding="utf-8") as fh:
            src = fh.read()
        m = re.search(r"^KIND_BASE\s*=\s*\{([^}]*)\}", src, re.M)
        self.assertIsNotNone(m, "找不到 KIND_BASE")
        self.assertIn('"impl"', m.group(1), "KIND_BASE 缺 impl —— impl 边会按 0 权算")


class TestDescNoBakedNumbers(unittest.TestCase):
    """B. desc 不写死会过期的规模读数。"""

    #: 4 位以上裸数字（只抓"数字 + 规模量词"或"数字 节点/边"，避免误伤版本号）
    PAT = re.compile(r"\d[\d,]{3,}\s*(?:节点|条边|有向边|能力位|组件)|\d+\s*跳\s*=\s*\d+")

    def test_impact_check_desc_clean(self):
        from gbt_allinone import caps_registry as cr
        desc = str(cr.BENIGN_CAPS["impact_check"].get("desc") or "")
        self.assertTrue(desc, "impact_check 的 desc 空了")
        hit = self.PAT.findall(desc)
        self.assertEqual(
            hit, [],
            "desc 里又写死了会过期的读数 %r —— 数字应走 op=status 现查"
            % (hit,))

    def test_desc_points_at_status(self):
        """不准写死，就得指个活口 —— 否则调用方无处查。"""
        from gbt_allinone import caps_registry as cr
        desc = str(cr.BENIGN_CAPS["impact_check"].get("desc") or "")
        self.assertIn("op=status", desc,
                      "desc 摘了数字却没指向 op=status，等于把信息也一起删了")


class TestSnapshotInSync(unittest.TestCase):
    """C. data/capabilities.json 与注册表一致（七个模块读它）。"""

    def test_impact_check_desc_matches(self):
        if not os.path.exists(SNAPSHOT):
            self.skipTest("data/capabilities.json 不存在")
        from gbt_allinone import caps_registry as cr
        with open(SNAPSHOT, encoding="utf-8") as fh:
            snap = json.load(fh)
        rows = {c["name"]: c for c in snap.get("capabilities") or []}
        self.assertIn("impact_check", rows, "快照里没有 impact_check")
        self.assertEqual(
            rows["impact_check"].get("desc"),
            cr.BENIGN_CAPS["impact_check"].get("desc"),
            "快照 desc 与注册表不一致 —— 跑 "
            "tools/codex-scripts/export-capabilities.py 重导")


class TestImplEdgePresent(unittest.TestCase):
    """D. 能力位到本体 1 跳（impl 层不能被回退掉）。"""

    def test_codex_tools_reaches_bridge(self):
        w = _wiring()
        if w is None:
            self.skipTest("wiring.json 还没建")
        adj = w.get("adj") or {}
        cap = "cap:codex_tools"
        impl = "code:gbt_allinone/codex_bridge.py"
        self.assertIn(cap, adj, "图里没有 cap:codex_tools")
        self.assertIn(
            impl, adj[cap],
            "cap:codex_tools 不再 1 跳直达 codex_bridge.py —— "
            "impl 边层被回退了？（v4 靠 api.py 的 `if kind ==` 分支静态挖）")

    def test_impl_is_strong(self):
        """impl 是真依赖，必须进强边；掉进弱边就说明权重口径走样。"""
        w = _wiring()
        if w is None:
            self.skipTest("wiring.json 还没建")
        strong = w.get("strong_adj") or {}
        self.assertIn(
            "code:gbt_allinone/codex_bridge.py", strong.get("cap:codex_tools", {}),
            "impl 边不在强边里 —— 查 KIND_BASE['impl'] 与 strong 写入路径")

    def test_review_gate_reaches_terminal_review(self):
        """第 ④ 种 impl 形态：路径**先存变量、再传给 loader**。

        来历（2026-11-05）：`api.py:2705` 写的是

            _rg_path = Path(__file__).resolve().parents[1] / "tools" / "codex-scripts" / "terminal-review.py"

        不是把路径内联进 `spec_from_file_location(...)` 的参数。旧规则只看调用参数，
        抽到的是 `ast.Name` ⇒ 0 条边 ⇒ `review_gate` 被误判成「孤儿位」。
        同批的 `hook_enforcer` / `omission_detector` 路径内联在调用里、② 形态能认，
        它们本来就有强边 —— 「孤儿」这个结论当时错在没区分这两种写法。
        """
        w = _wiring()
        if w is None:
            self.skipTest("wiring.json 还没建")
        adj = w.get("adj") or {}
        cap = "cap:review_gate"
        impl = "code:tools/codex-scripts/terminal-review.py"
        self.assertIn(cap, adj, "图里没有 cap:review_gate")
        self.assertIn(
            impl, adj[cap],
            "cap:review_gate 不再 1 跳直达 terminal-review.py —— "
            "第 ④ 种 impl 形态（路径先存变量）被回退了？")
        strong = w.get("strong_adj") or {}
        self.assertIn(
            impl, strong.get(cap, {}),
            "review_gate → terminal-review.py 掉出强边了 —— impl 必须算真依赖")


if __name__ == "__main__":
    unittest.main(verbosity=2)
