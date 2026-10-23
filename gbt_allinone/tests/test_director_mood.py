# -*- coding: utf-8 -*-
"""导演情绪内核四条红线 · 带牙用例（R-H172）。

① 情绪不改数据 —— 逐字节对比调用前后的**原数据**；
② 状态必须可查 —— 五个字段一个都不能少，非法情绪直接拒；
③ 情绪有半衰期 —— 半衰期到一半、多倍半衰期后自动退回"平静"；
④ 导演仍是只读 —— 子进程里跑一整套，受控 store **零文件**；源码里不许有写调用。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import director_mood as dm  # noqa: E402


class RedlineOneEmotionNeverChangesData(unittest.TestCase):
    ROWS = [
        {"kind": "payment_gateway", "signal": "legacy", "count": 4},
        {"kind": "t-dead", "signal": "trace", "count": 1},
    ]

    def test_original_rows_are_byte_identical_after_apply_lens(self):
        before = json.dumps(self.ROWS, ensure_ascii=False, sort_keys=True)
        mood = dm.DirectorMood()
        mood.feel("怒", "闻", intensity=0.9, trigger="有人把待认领写成已完成")
        out = dm.apply_lens(self.ROWS, mood)
        after = json.dumps(self.ROWS, ensure_ascii=False, sort_keys=True)
        self.assertEqual(before, after, "情绪动了原数据 —— 红线 1 破了")
        self.assertIsNot(out, self.ROWS, "必须返回新列表")
        self.assertIsNot(out[0], self.ROWS[0], "必须返回新对象（不许就地改）")
        self.assertNotIn("_lens", self.ROWS[0], "原字典里不许被写入 _lens")

    def test_lens_only_adds_a_key_never_rewrites_facts(self):
        mood = dm.DirectorMood()
        mood.feel("喜", "言", intensity=0.5, trigger="红点清了")
        out = dm.apply_lens(self.ROWS, mood)
        for src, dst in zip(self.ROWS, out):
            self.assertEqual(set(dst) - {"_lens"}, set(src), "情绪只许加镜头，不许改字段")
            for k, v in src.items():
                self.assertEqual(dst[k], v, f"字段 {k} 被情绪改写了")
            self.assertIn("never", dst["_lens"], "每条情绪都必须带『绝不许做什么』")

    def test_every_emotion_declares_its_forbidden_move(self):
        for emo in dm.EMOTIONS + (dm.CALM,):
            lens = dm.LENSES.get(emo) or {}
            self.assertTrue(lens.get("affect"), f"{emo} 缺 affect")
            self.assertTrue(lens.get("never"), f"{emo} 缺 never（情绪越界就没有闸）")


class RedlineTwoStateIsInspectable(unittest.TestCase):
    def test_status_exposes_all_five_fields(self):
        mood = dm.DirectorMood()
        st = mood.feel("哀", "闻", intensity=0.7, trigger="主人说『我一个没看到』", now=1000.0)
        for k in ("emotion", "drive", "intensity", "since", "trigger"):
            self.assertIn(k, st, f"状态缺 {k} —— 不许假装懂")
        self.assertEqual(st["emotion"], "哀")
        self.assertEqual(st["drive"], "闻")
        self.assertEqual(st["drive_meaning"], dm.DRIVES["闻"])
        self.assertEqual(st["since"], 1000.0)
        self.assertIn("主人说", st["trigger"])
        self.assertTrue(st["readonly"], "必须自报『只读』")

    def test_unknown_emotion_is_refused(self):
        mood = dm.DirectorMood()
        with self.assertRaises(ValueError):
            mood.feel("暴怒", "闻")
        with self.assertRaises(ValueError):
            mood.feel("怒", "贪")


class RedlineThreeMoodHasHalfLife(unittest.TestCase):
    def test_half_life_halves_and_then_fades_to_calm(self):
        mood = dm.DirectorMood()
        mood.feel("怒", "闻", intensity=1.0, trigger="越界", half_life_s=100.0, now=0.0)
        half = mood.status(now=100.0)
        self.assertAlmostEqual(half["intensity"], 0.5, places=3, msg="半衰期到点应该剩一半")
        self.assertEqual(half["emotion"], "怒")
        gone = mood.status(now=100.0 * 10)
        self.assertEqual(gone["emotion"], dm.CALM, "多倍半衰期后必须退回平静（不许常驻）")
        self.assertEqual(gone["intensity"], 0.0)
        self.assertEqual(gone.get("faded_from"), "怒", "淡出要说明_from，不许无声消失")

    def test_decay_writes_the_fade_back_into_state(self):
        mood = dm.DirectorMood()
        mood.feel("欲", "繁", intensity=0.4, half_life_s=10.0, now=0.0)
        mood.decay(now=10.0)
        self.assertAlmostEqual(mood.status(now=10.0)["intensity"], 0.2, places=3)
        mood.decay(now=10.0 * 20)
        self.assertTrue(mood.status(now=10.0 * 20)["calm"])
        self.assertEqual(mood.emotion, dm.CALM, "decay 必须把淡出写回状态本体")


class RedlineFourDirectorStaysReadonly(unittest.TestCase):
    def test_module_has_no_write_paths_in_source(self):
        src = Path(dm.__file__).read_text(encoding="utf-8")
        for bad in ("import shutil", "from .store", "from ..store", ".write_text(",
                    ".write_bytes(", "unlink(", "rmtree(", ".open(", "audit("):
            self.assertNotIn(bad, src, f"导演情绪内核里不该出现写路径：{bad}")

    def test_running_everything_writes_nothing_into_the_controlled_store(self):
        """真跑一遍（子进程 + 全新空 store）：**零文件**才叫只读。"""
        iso = tempfile.mkdtemp(prefix="rh172_dm_")
        code = (
            "import sys; sys.path.insert(0, sys.argv[1]);"
            "from gbt_allinone.tools import director_mood as dm;"
            "m = dm.DirectorMood();"
            "m.feel('怒','闻',0.9,'越界',half_life_s=60,now=0);"
            "m.decay(now=30); m.status(now=30); m.lens(now=30);"
            "dm.apply_lens([{'kind':'x'}], m); dm.run('status');"
            "print('ok')"
        )
        import os
        env = dict(os.environ)
        env["GBT_STORE_DIR"] = iso
        p = subprocess.run([sys.executable, "-c", code, str(ROOT)], env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace")[-400:])
        files = [q for q in Path(iso).rglob("*") if q.is_file()]
        self.assertEqual(files, [], f"只读模块写进了受控 store：{files}")


if __name__ == "__main__":
    unittest.main()
