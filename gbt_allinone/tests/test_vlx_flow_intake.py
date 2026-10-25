# -*- coding: utf-8 -*-
"""VLX-Flow 接入的判据（七步法第七步：接完必须落一条机器判据）。

为什么要有：接外部件最容易的失败不是「接不上」，而是**接上了、后来悄悄坏了没人知道**。
本仓原话是「判据不抓错，就是装饰」—— 所以本件**带真植入负控**。

判据五条：
  1. 能力位三处齐：注册表（caps_registry.py）· 分派（api.py）
  2. 走唯一门能调到：本体 ok:true（不是只信封 ok）
  3. **两层记忆都在位**：视觉缓存层四个能力（snapshot/stream_record/stream_replay/diff_regions）
     + 语义记忆层（只追加的 semantic_memory.jsonl）
  4. 读面免门 · 写面挂 filesystem_write（未列出的 op fail-closed）
  5. **负控（真植入）**：未列出的 op 必须 fail-closed，不许静默放行

🔴 **不在位时判「如实报缺」也算过**（七步法第七步原文）：上游是纯文档仓这件事本身
   不该让判据变红 —— 但**也不许静默变绿**：必须能把「上游还没放代码」如实报出来。
"""
from __future__ import annotations

import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CAP = ROOT / "gbt_allinone" / "tools" / "vlx_flow_cap.py"
REG = ROOT / "gbt_allinone" / "caps_registry.py"
API = ROOT / "gbt_allinone" / "api.py"


def _load():
    spec = importlib.util.spec_from_file_location("vlx_flow_cap_probe", CAP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestVlxFlowIntake(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load()

    def test_intake_file_and_stamp_present(self):
        self.assertTrue(CAP.is_file(), "能力本体不在位：%s" % CAP)
        src = CAP.read_text(encoding="utf-8")
        self.assertIn("om-ai-lab/VLX-Flow", src, "必须写清接自哪个上游（钢印）")
        self.assertIn("纯文档仓", src, "必须如实写出上游当前没有代码这件事")
        self.assertIn("七步法", src, "必须写清走的是哪套接入规程")

    def test_wired_three_places(self):
        reg = REG.read_text(encoding="utf-8")
        self.assertIn("vlx_flow", reg, "注册表里没有 vlx_flow ⇒ 登记缺失")
        api = API.read_text(encoding="utf-8")
        self.assertIn("vlx_flow", api, "api.py 分派里没有 vlx_flow ⇒ 登记≠接线")

    def test_status_reports_both_layers(self):
        r = self.m.run({"op": "status"})
        self.assertTrue(r.get("ok"), "status 不是 ok：%s" % r)
        self.assertIn("visual_cache_layer", r, "缺视觉缓存层的读数")
        self.assertIn("semantic_memory_layer", r, "缺语义记忆层的读数")
        self.assertIn("Coming soon", r.get("upstream") or "", "上游状态没如实报出来")

    def test_visual_layer_four_capabilities(self):
        r = self.m.run({"op": "status"})
        v = r.get("visual_cache_layer") or {}
        if not v.get("bus_available"):
            self.skipTest("视觉总线取不到（%s）—— 如实跳过，不当通过" % v.get("bus_error"))
        for k in ("has_snapshot", "has_stream_record", "has_stream_replay", "has_grid_diff"):
            self.assertTrue(v.get(k), "视觉缓存层缺能力：%s" % k)

    def test_real_loop_digest_and_recall(self):
        files = self.m._stream_files()
        if not files:
            self.skipTest("本机还没有视觉流记录 —— 如实跳过")
        name = files[0].stem
        before = len(self.m._read_mem())
        d = self.m.run({"op": "digest", "stream": name})
        self.assertTrue(d.get("ok"), "digest 没跑通：%s" % d)
        after = len(self.m._read_mem())
        self.assertEqual(before + 1, after, "digest 应当只追加一条")
        row = d.get("appended") or {}
        self.assertFalse(row.get("semantic_by_model"),
                         "模型那一步没接就不许标成模型产的（不许编来源）")
        q = self.m.run({"op": "recall", "q": name})
        self.assertTrue(q.get("ok"), "recall 没跑通")
        self.assertGreaterEqual(q.get("matched") or 0, 1, "刚写的语义应当能查回来")

    def test_fail_closed_on_unknown_op(self):
        r = self.m.run({"op": "zz_not_an_op"})
        self.assertFalse(r.get("ok"), "未列出的 op 竟然放行了 ⇒ 判据没牙")
        self.assertTrue(r.get("fail_closed"), "必须显式 fail_closed")
        self.assertIn("status", r.get("ops") or [], "必须把可用 op 列出来")

    def test_write_ops_declared(self):
        self.assertEqual(set(self.m._WRITE_OPS), {"digest", "remember"},
                         "写面清单变了 ⇒ 门规约要跟着改，别静默漂移")
        for op in self.m._WRITE_OPS:
            self.assertIn(op, self.m._OPS, "写面 op 必须在可用 op 清单里")


if __name__ == "__main__":
    unittest.main(verbosity=2)