# -*- coding: utf-8 -*-
"""mirror_space 契约测试（风哥 2026-09-17 批 · 条件 2）。

守的是《版本号字符串序陷阱》：
`sorted(paths)[-1]` 取"最新版本"——字符串序下 v9.json 排在 v20.json 之后。
实证现场：mirror_space.py:218，v20 是第一个两位数版本时才炸。

测试隔离：整套测试只在临时目录里造护照/维度/现实，绝不碰生产 store。
"""
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

_HERE = Path(__file__).resolve().parent
_PKG = _HERE.parent          # gbt_allinone/
_ROOT = _PKG.parent          # 项目根
MIRROR_PY = _PKG / "mirror_space.py"
MIRROR_PY_TWIN = _ROOT / "mirror_space.py"

# 契约：按整数序取最新
VERSIONS = ["v1", "v2", "v9", "v10", "v20"]


def _load_mirror_module():
    """按路径加载被测模块，避开 gbt_allinone 包的重依赖与生产 store。"""
    spec = importlib.util.spec_from_file_location("mirror_space_under_test", MIRROR_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestLatestPassportIsNumeric(unittest.TestCase):
    """条件 2 要求的契约点：取"最新版本"必须按整数序。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gbt_vsort_"))
        self.passports = self.tmp / "passports"
        self.passports.mkdir(parents=True, exist_ok=True)
        for stem in VERSIONS:
            (self.passports / (stem + ".json")).write_text("{}", encoding="utf-8")

    def test_latest_passport_is_numeric(self):
        files = list(self.passports.glob("v*.json"))
        numeric = sorted(files, key=lambda p: int(p.stem[1:]))[-1].name
        self.assertEqual(numeric, "v20.json")

    def test_string_sort_would_pick_v9(self):
        """反向证明：本测试有效——字符串序确实会取到 v9，不是空跑。"""
        files = list(self.passports.glob("v*.json"))
        self.assertEqual(sorted(files)[-1].name, "v9.json")
        self.assertNotEqual(sorted(files)[-1].name, "v20.json")

    def test_mixed_non_numeric_does_not_crash_if_guarded(self):
        """现状说明：整数序 key 假设 passports 目录里只有 v<数字>.json。

        这不是缺陷断言，是口径记录——目录里混入非数字名会抛 ValueError，
        目前该目录由 mirror_space 自己写，名字恒定形如 v<N>.json。
        """
        (self.passports / "vax.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            sorted(list(self.passports.glob("v*.json")), key=lambda p: int(p.stem[1:]))


class TestMirrorStatusUsesLatestPassport(unittest.TestCase):
    """端到端契约：mirror_status 必须拿 v20 当基线，不能拿 v9。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gbt_vsort_e2e_"))
        self.m = _load_mirror_module()
        self.dim = self.tmp / "dimension"
        self.reality = self.tmp / "reality"
        self.timelines = self.tmp / "timelines"
        self.passports = self.tmp / "passports"
        for d in (self.dim, self.reality, self.timelines, self.passports):
            d.mkdir(parents=True, exist_ok=True)

        (self.dim / "a.txt").write_text("A", encoding="utf-8")
        (self.dim / "new.txt").write_text("N", encoding="utf-8")
        (self.reality / "a.txt").write_text("A", encoding="utf-8")
        (self.reality / "new.txt").write_text("N", encoding="utf-8")

        sha_a = self.m._sha_file(self.reality / "a.txt")
        sha_n = self.m._sha_file(self.reality / "new.txt")
        stale = {"a.txt": {"sha": sha_a, "size": 1}}
        fresh = {"a.txt": {"sha": sha_a, "size": 1}, "new.txt": {"sha": sha_n, "size": 1}}
        for stem in VERSIONS:
            manifest = fresh if stem == "v20" else stale
            (self.passports / (stem + ".json")).write_text(
                json.dumps({"version": int(stem[1:]), "manifest": manifest}), encoding="utf-8")

        self.m._DIM = self.dim
        self.m._REALITY = self.reality
        self.m._TIMELINES = self.timelines
        self.m._PASSPORTS = self.passports

    def test_mirror_status_is_clean_against_v20(self):
        st = self.m.mirror_status()
        self.assertEqual(st["dimension_vs_reality"], [])
        self.assertEqual(st["reality_drift"], [], "基线取错（v9 而非 v20）时这里必然非空")
        self.assertTrue(st["clean"], "现实与 v20 完全一致，clean 必须为 True")
        self.assertEqual(st["reality"]["version"], len(VERSIONS))

    def test_fixture_is_discriminating(self):
        """若基线退回字符串序，本 fixture 会立刻报漂移——证明上面那条不是空跑。"""
        files = list(self.passports.glob("v*.json"))
        wrong_baseline = json.loads(sorted(files)[-1].read_text(encoding="utf-8"))
        self.assertEqual(wrong_baseline["version"], 9)
        self.assertNotIn("new.txt", wrong_baseline["manifest"])

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestTwoCopiesStayInSync(unittest.TestCase):
    """条件 1：家根不许有影子 —— 两份并存时必须逐字节相同（O49 归档后口径）。

    R113 修正：原先是"根副本必须存在"，那是 O49 家根影子大扫之前的旧口径。
    """

    def test_copies_identical(self):
        """家根不许有影子；若两处同时存在则必须逐字节相同。

        R113 修正：本用例原先无条件断言根副本存在并要求字节相同 —— 那是 **O49 家根
        影子大扫（2026-09-17）之前**的口径。归档后家根顶层 .py = 0，常驻防线是
        gbt_allinone/tools/shadow_check.py（门禁 W 维 · shadow_verdict=GREEN）。
        旧断言与现行设计直接冲突，且长期无声变红（不在任何回归清单里）。
        现改为"影子不许复活"的正向判据：两份并存时仍逐字节比对。
        """
        self.assertTrue(MIRROR_PY.exists(), str(MIRROR_PY))
        if not MIRROR_PY_TWIN.exists():
            return   # O49 归档后的正常态：家根没有同名副本
        h1 = hashlib.sha256(MIRROR_PY.read_bytes()).hexdigest()
        h2 = hashlib.sha256(MIRROR_PY_TWIN.read_bytes()).hexdigest()
        self.assertEqual(h1, h2, "两处副本分叉了——必须同步修")
    def test_fix_is_present(self):
        src = MIRROR_PY.read_text(encoding="utf-8")
        self.assertIn('key=lambda p: int(p.stem[1:])', src)
        self.assertNotIn('sorted(_PASSPORTS.glob("v*.json")) if', src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
