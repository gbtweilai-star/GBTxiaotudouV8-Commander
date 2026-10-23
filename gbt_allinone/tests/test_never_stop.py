# -*- coding: utf-8 -*-
"""不停工判据（主人令 2026-10-09：「把你和框架的机制一起修改成看整体没完善就不停工，
除非用户要求停止」）。

锁四件：
  ① 整体完善度是**五处现读**（报警/禁交付/未闭合/门/蓝图），任一处不绿 ⇒ 未完善；
  ② **局部完成 ≠ 可以停**：即使这一件活干完且带证据，只要整体未完善就**不许停**，
     且必须**点出还差哪一项**（不许只说"还没好"）；
  ③ 唯一例外一：危险清单里的授权动作（AI 不许自授权 ⇒ 必须停人要票）；
  ④ 唯一例外二：**主人明确喊停** —— 这条优先级最高。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 🔴 仓约定（照 test_framework.py:11-16）：**先设隔离 store 再导入被测模块** ——
#    否则仓里的保护闸会拒（"拒绝在绑定：真 store，改的就是真（成品）测试"）。
#    我原来四个判据文件都没设 ⇒ 体检里用 pytest 跑时全部 rc=2（实测撞了）。
os.environ.setdefault("GBT_STORE_DIR", tempfile.mkdtemp(prefix="gbt_test_store_"))

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import ux_doctrine as UX  # noqa: E402


class NeverStopTest(unittest.TestCase):

    def test_completeness_is_five_live_readings(self):
        c = UX.completeness(live=False)          # 判据里关掉 live，避免起子进程
        self.assertIn("完善", c)
        names = [i["项"] for i in c["逐项"]]
        for want in ("报警 0", "禁交付 0", "未闭合动作 0"):
            self.assertIn(want, names, "整体完善度必须含「%s」" % want)
        for i in c["逐项"]:
            self.assertTrue(str(i["读数"]).strip(), "%s 必须带读数" % i["项"])
            self.assertTrue(str(i["怎么查"]).strip(), "%s 必须给怎么查" % i["项"])

    def test_local_done_is_not_enough(self):
        """局部完成 + 带证据 ⇒ 只要整体未完善，仍然**不许停**，且要点名还差什么。"""
        c = UX.completeness(live=False)
        s = UX.check_stop("全部跑通并交付", evidence="判据全绿", live=False)
        if not c["完善"]:
            self.assertFalse(s["允许停"], "整体未完善时不许停")
            self.assertTrue(s.get("还差"), "不许停必须点出**还差哪一项**（不许只说还没好）")
        else:
            self.assertTrue(s["允许停"], "整体已完善 ⇒ 交活即停")

    def test_danger_class_can_stop(self):
        s = UX.check_stop("要发布上线", danger_class="对外发布", live=False)
        self.assertTrue(s["允许停"], "危险清单是不可自授权的唯一业务停点")

    def test_owner_stop_outranks_everything(self):
        for w in ("停止", "STOP"):
            self.assertTrue(UX.honor_owner_stop(w)["主人已喊停"], "主人喊停必须认")
        self.assertFalse(UX.honor_owner_stop("继续做")["主人已喊停"])

    def test_no_extra_stop_reasons(self):
        for r in ("我不确定，等你回复", "需要你同意一下", "请你选择"):
            self.assertFalse(UX.check_stop(r, live=False)["允许停"],
                             "「%s」不是合法停点" % r)


if __name__ == "__main__":
    unittest.main()
