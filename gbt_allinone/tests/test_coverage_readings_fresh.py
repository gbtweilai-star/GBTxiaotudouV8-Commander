"""覆盖读数的新鲜度与「不新增盲区」判据（主人令 2026-09-27：「全方位无死角覆盖…
没有任何死角和盲区才叫扫描」）。

**为什么立这条**：矩阵（`tools/coverage_matrix.py sweep`）是**那一刻**的读数。
它自己会保证"没扫到的面必须显式列出来"，但**挡不住"盘上后来多了个顶层树"**——
新目录既不在已扫清单里，也不在排除表里，于是它**默默成了盲区**，而读数看起来还是全绿。
这条判据就是那道闸：**盘上的顶层树数量一旦与读数对不上，开机就红**。

判据（全部机检）：
  A. 读数在且**全绿**（有盲区/无理由排除/视觉面有红 ⇒ 红）；
  B. 读数**新鲜**（≤26 小时；定时环每 6 小时刷新一次，一天停机也给够余量）；
  C. **顶层树数量与盘上一致** —— 多一个 = 新增盲区，少一个 = 读数过期，两种都红。

红了怎么修（直说，不让人猜）：`python tools/coverage_matrix.py sweep`（约 50 秒）
"""
from __future__ import annotations

import json
import os
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "state" / "coverage_matrix.json"
MAX_AGE_H = 26


def _live_top_dirs() -> int:
    """盘上真实顶层目录数 —— **口径必须与矩阵一致**：全部目录都算，
    `.git` 也算（它在矩阵里是"排除表里带理由"的一员，不是被无视的）。
    实测血账：本判据首跑就报 `63 != 62` —— 差的就是这里把 `.git` 漏掉了。
    口径不一致的读数对账，比不对账更坏：它会让人去改对的那一边。"""
    return sum(1 for p in ROOT.iterdir() if p.is_dir())


class TestCoverageReadingsFresh(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = MATRIX.read_text(encoding="utf-8") if MATRIX.is_file() else ""
        cls.d = json.loads(cls.raw) if cls.raw else {}

    def test_readings_exist_and_all_green(self):
        """A. 读数在，且全绿（盲区 / 无理由排除 / 视觉面有红 ⇒ 红）。"""
        self.assertTrue(MATRIX.is_file(),
                        f"还没有覆盖矩阵读数 ⇒ 跑：python tools/coverage_matrix.py sweep")
        self.assertTrue(self.d.get("全绿"),
                        f"矩阵不是全绿：盲区 {self.d.get('盲区')} · "
                        f"无理由排除 {self.d.get('无理由排除')} · "
                        f"视觉面 {self.d.get('面E视觉', {}).get('findings')}\n"
                        f"⇒ 修法：python tools/coverage_matrix.py sweep")

    def test_readings_are_fresh(self):
        """B. 读数新鲜（≤26h）—— 过期读数不是读数。"""
        at = self.d.get("at")
        self.assertTrue(at, "读数里没有时间戳")
        age_h = (time.time() - time.mktime(time.strptime(at, "%Y-%m-%dT%H:%M:%S"))) / 3600
        self.assertLess(age_h, MAX_AGE_H,
                        f"覆盖读数已过期 {age_h:.1f} 小时（上限 {MAX_AGE_H}h）\n"
                        f"⇒ 修法：python tools/coverage_matrix.py sweep")

    def test_no_new_tree_became_a_blind_spot(self):
        """C. **不新增盲区**：盘上的顶层树数量必须与读数一致。

        这一条专治"新目录悄悄绕开扫描"：既不在已扫清单、也不在排除表里的目录，
        就是盲区 —— 而读数会显得一切正常。
        """
        live = _live_top_dirs()
        recorded = self.d.get("顶层树")
        self.assertEqual(recorded, live,
                         f"盘上顶层树 {live} 个，读数里是 {recorded} 个 —— "
                         f"差异就是**新增/消失的面**（新增=盲区，消失=读数过期）\n"
                         f"⇒ 修法：python tools/coverage_matrix.py sweep")

    def test_vision_surface_is_hooked(self):
        """E 面单独钉一遍：视觉是我们最敏感的面（那些帧是**主人的整块屏幕**）。"""
        vis = self.d.get("面E视觉") or {}
        self.assertTrue(vis, "读数里没有视觉面")
        self.assertEqual(0, vis.get("eye_frames", {}).get("tracked", -1),
                         "屏幕帧被 git 追踪了（必须为 0）")
        self.assertTrue(vis.get("gitignore_lock"), ".gitignore 里那道屏幕帧锁不见了")
        self.assertTrue(vis.get("ok"), f"视觉面有红：{vis.get('findings')}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
