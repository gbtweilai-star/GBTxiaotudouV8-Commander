"""自动化配置密钥口判据（主人令 2026-09-27「集成进我们 APP 设置里面当自动化配置密钥口」）。

**为什么单独立一份判据**：这个能力位的活是"把框架要用的六种智能接上电"，
它报的每一个「在位/不在位」都会被**上层直接当结论用** —— 今天就是这么翻车的：

    `freellmapi.probe()` 回的是 **`up`**，而 `automation_keys.test` 只读 `ok`
    ⇒ 端口明明在听，也一律判「不可达」。这条**假红**一路传到 `state/health.json`，
    再由**上帝之眼日报**报成短板「免费算力池不可达」。
    键名不同 ≠ 服务不在 —— 报错的方向反了，比不报更费能源（会去修一个没坏的东西）。

所以判据 A 的形状是「**结论必须与它自己带回来的原始读数一致**」——
环境无关、可判定，且正好会抓住上面那个错位。

**判据**：
  A. **结论自洽**：free_pool 的 `ok` 必须等于同一份读数里的 `up`（关掉它必然红）；
  B. **只回引用不回值**：`status` 里的 ref 只能是 `env:` / `vault:` / `local` 三种形状；
  C. **六个槽一个不少**（主人令点名的六种智能）；
  D. **自检是只读的**：跑 `test` 不许改配置（跑前跑后配置逐字节相同）。
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "gbt_allinone" / "tools" / "automation_keys.py"
CFG = ROOT / "state" / "automation_keys.json"


def _load():
    spec = importlib.util.spec_from_file_location("ak_probe", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestAutomationKeys(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load()

    def test_a_free_pool_verdict_matches_its_own_reading(self):
        """A. 结论自洽：`ok` 必须与 `probe.up` 一致（键名漂移 = 假红）。"""
        r = self.m.test("free_pool")
        row = (r.get("results") or [{}])[0]
        pr = row.get("probe") or {}
        if "up" not in pr and "ok" not in pr:
            self.skipTest(f"没有探活读数（本地 FreeLLMAPI 未发现）：{row.get('why')}")
        raw = bool(pr.get("ok") if "ok" in pr else pr.get("up"))
        self.assertEqual(bool(row.get("ok")), raw,
                         f"结论与原始读数打架：ok={row.get('ok')} 而 probe={pr}")
        self.assertTrue(row.get("why"), "不管通不通都要说清为什么")

    def test_b_refs_are_references_never_values(self):
        """B. 密钥口只回**引用**：`env:` / `vault:` / `local`，绝不回值。"""
        st = self.m.status()
        slots = st.get("slots") or []
        self.assertEqual(len(slots), 6, f"六个槽才对：{len(slots)}")
        for s in slots:
            ref = s.get("ref") or ""
            self.assertTrue(ref.startswith(("env:", "vault:", "local")),
                            f"{s.get('slot')} 的引用形状不对：{ref!r}（不许是明文值）")
            self.assertNotIn("sk-", ref, "引用里出现了密钥形状")

    def test_c_six_slots_present(self):
        """C. 主人令点名的六种智能一个不少。"""
        self.assertEqual(sorted(self.m.SLOTS), ["browser", "claude", "codex", "deepseek",
                                                "free_pool", "sec_llm"])

    def test_d_selftest_is_read_only(self):
        """D. 自检不许改配置：跑前跑后逐字节相同。"""
        before = CFG.read_bytes() if CFG.is_file() else b""
        self.m.test()
        after = CFG.read_bytes() if CFG.is_file() else b""
        self.assertEqual(before, after, "只读自检把配置文件改了")

    def test_e_where_contract_declares_entry(self):
        """E. 给 APP 设置看的接线契约必须写清入口（不然设置页接不上）。"""
        w = self.m.where()
        self.assertIn("run_task", json.dumps(w, ensure_ascii=False))
        self.assertTrue(w.get("契约"), "契约是空的 ⇒ 设置页不知道该调什么")


if __name__ == "__main__":
    unittest.main(verbosity=2)
