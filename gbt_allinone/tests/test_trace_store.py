# -*- coding: utf-8 -*-
"""痕迹库（第 2 步第一小刀）契约测试：**三道闸都要有牙**。

① origin 闸：测试件 / 自检事件拒收且**不写盘**
② 脱敏闸：白名单外字段丢弃；形态命中**写入前**掩码
③ 有源校验：空源拒收；有 id 查不到 ⇒ 整条拒收（第四条硬约束）
④ 升格只认主人标记；状态位由 `promotes` 流水**派生**
⑤ 只读 / 无删除路径；保留期只是读数
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


class TraceStoreTests(unittest.TestCase):
    """trace_store 契约。

    🔴 2026-10-17 修（**跨用例污染真凶** · 留痕 · 原口径 / 为什么翻 / 现口径）：
      原实现：`setUp` 把 `GBT_STORE_DIR` 改成临时根，并 `sys.modules.pop` 掉
        `gbt_allinone.trace_store` **和 `gbt_allinone._paths`**；`tearDown` **无条件**
        `os.environ.pop("GBT_STORE_DIR")`。
      为什么翻（全量跑实测）：pop 掉 `_paths` 后它被**重新 import** ⇒ 进程里出现**第二个
        `_paths` 口径**（`STORE_DIR_ENV_AT_BIND` = 临时根），而 `tearDown` 又把 env 清成 None
        ⇒ `verify_store_binding()` 之后对**每一次写盘**都抛
        「store 绑定与环境变量不一致，拒绝写入 —— …当前 GBT_STORE_DIR=None」
        ⇒ `test_vision_print` 的 `comfy_native run` 等**所有要写盘的用例**跟着假红（2 条）。
      现口径：① **不再 pop `_paths`**（本判据已显式改 `ts._STORE`，不需要 reload 父模块）；
        ② env **原样还原**（老值是 None 才 pop），env 与绑定始终自洽。
    """

    def setUp(self):
        self._old_store_env = os.environ.get("GBT_STORE_DIR")
        self.tmp = tempfile.TemporaryDirectory(prefix="gbt_traces_")
        os.environ["GBT_STORE_DIR"] = self.tmp.name
        sys.modules.pop("gbt_allinone.trace_store", None)
        self.ts = importlib.import_module("gbt_allinone.trace_store")
        # 显式把库指向隔离目录：`_paths.STORE_DIR` 是 import 时绑定的常量，
        # 只靠环境变量在"父包已被导入"的情况下不一定生效 —— 直接改模块级常量最确定。
        self.ts._STORE = Path(self.tmp.name)
        self.ts.TRACE_DIR = self.ts._STORE / "traces"

    def tearDown(self):
        # 原样还原（老值是 None 才 pop）——**不许无条件 pop**，理由见类文档
        if self._old_store_env is None:
            os.environ.pop("GBT_STORE_DIR", None)
        else:
            os.environ["GBT_STORE_DIR"] = self._old_store_env
        self.tmp.cleanup()

    def _rows(self, table):
        p = Path(self.tmp.name) / "traces" / (table + ".jsonl")
        if not p.is_file():
            return []
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]

    def test_test_origin_is_rejected_and_nothing_is_written(self):
        for ev, meta in (("probe", {}), ("denied", {"kind": "keylogger"}),
                         ("pipeline_blocked", {"name": "_def_probe.txt"})):
            r = self.ts.record_wave_sample(ev, 5, meta=meta)
            self.assertFalse(r["ok"], (ev, meta, r))
            self.assertEqual(r["reason_code"], "test_origin")
        self.assertEqual(self._rows("wave_samples"), [], "被拒的样本不许写盘")
        ok = self.ts.record_wave_sample("auth_denied", 4, meta={"scope": "deploy_publish"})
        self.assertTrue(ok["ok"], ok)
        self.assertEqual(len(self._rows("wave_samples")), 1)

    def test_redaction_drops_unknown_fields_and_masks_secrets(self):
        out = self.ts.redact({"event": "denied", "meta": {"api_key": "sk-abc"},
                              "prompt": "full private prompt",
                              "authorization": "Bearer abcdefghijklmnop",
                              "context": "id sk-a1b2c3d4e5 长号 4111111111111111"})
        self.assertNotIn("meta", out, "白名单外字段必须丢弃")
        self.assertNotIn("prompt", out)
        self.assertNotIn("authorization", out)
        self.assertNotIn("sk-a1b2c3d4e5", out["context"], "形态命中必须掩码")
        self.assertNotIn("4111111111111111", out["context"], "长数字串必须掩码")
        self.assertIn("****", out["context"])

    def test_obsession_without_source_or_with_dangling_id_is_rejected(self):
        r = self.ts.append_obsession("事", "未了念", 0.5, [], 3600)
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason_code"], "no_source")
        self.assertEqual(self._rows("obsessions"), [])
        r2 = self.ts.append_obsession("事", "未了念", 0.5, ["tr-not-exist"], 3600)
        self.assertFalse(r2["ok"])
        self.assertEqual(r2["reason_code"], "dangling_source")
        self.assertEqual(self._rows("obsessions"), [], "有 id 查不到 ⇒ 整条拒收")

    def test_obsession_with_real_source_is_accepted(self):
        self.ts.record_wave_sample("auth_denied", 3, meta={"scope": "deploy_publish"})
        tr = self.ts.append_trace("auth/deploy_publish", "被挡念", "ws-1")
        self.assertTrue(tr["ok"], tr)
        r = self.ts.append_obsession("auth/deploy_publish", "被挡念", 0.7, ["ws-1"], 3600)
        self.assertTrue(r["ok"], r)
        self.assertEqual(len(self._rows("obsessions")), 1)

    def test_promote_requires_owner_mark_and_state_is_derived(self):
        self.ts.record_wave_sample("auth_denied", 3, meta={"scope": "deploy_publish"})
        self.ts.append_trace("auth/deploy_publish", "被挡念", "ws-1")
        bad = self.ts.promote("ws-1", promoted_by="ai", utterance_ref="")
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["reason_code"], "not_owner_mark")
        bad2 = self.ts.promote("ws-1", promoted_by="owner", utterance_ref="")
        self.assertFalse(bad2["ok"], "没有原话指针不算标记")
        self.assertEqual(self.ts.promoted_state(), {})
        good = self.ts.promote("ws-1", promoted_by="owner", utterance_ref="升格 ws-1")
        self.assertTrue(good["ok"], good)
        self.assertEqual(self.ts.promoted_state(), {"ws-1": True})

    def test_module_has_no_delete_path_and_retention_is_a_reading(self):
        import inspect
        src = inspect.getsource(self.ts)
        for bad in ("os.remove", "unlink(", "shutil", "write_text(", "rmtree"):
            self.assertNotIn(bad, src, f"痕迹库不许有删除/覆盖原语：{bad}")
        r = self.ts.retention(days=90)
        self.assertTrue(r["ok"])
        self.assertIn("永不删", r["policy"])
        self.assertEqual(self._rows("wave_samples"), [], "retention 不许动数据")
        st = self.ts.status()
        self.assertTrue(st["readonly"])
        self.assertEqual(set(st["tables"]), set(self.ts.TABLES))


if __name__ == "__main__":
    unittest.main()
