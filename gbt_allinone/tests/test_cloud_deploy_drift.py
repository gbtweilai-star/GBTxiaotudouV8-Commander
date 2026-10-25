"""R-H617（2026-09-25）· **部署漂移对账**自己的判据。

被测对象：`deploy/cloud-10/tools/check-deploy-drift.mjs`

它回答「云上跑的是不是仓里这份」——比的是**可观测的声明面**（`/`、`/mesh`、`/health`、
`/edges`、`/v1/models` 里与绑定无关的那部分）。真跑要联网，所以：

  · **联网那一侧**（对着真地址比）**不进常设判据** —— 判据不该依赖外网；
  · **进常设判据的是它的『牙齿』**：`--selftest` 是**纯离线**的，
    种五处差异（改值 / 云上多键 / 云上少键 / 数组长度 / 嵌套改值）看它是不是每处都逮得住，
    再加两道**防空转**守卫（比对清单不许为空 · pick 必须真选到键）。

为什么必须防这一手：一个"比出来没差异"的对账器，**很可能是因为它其实什么都没比**。
本仓原话「条数不等于牙齿」——对账器也一样：**"零漂移"只有在尺子有牙时才叫结论**。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "deploy" / "cloud-10" / "tools" / "check-deploy-drift.mjs"


class DeployDriftToolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.node = shutil.which("node")
        cls.p = None
        cls.rep = {}
        if cls.node and TOOL.is_file():
            cls.p = subprocess.run([cls.node, str(TOOL), "--selftest", "--json"],
                                   cwd=str(ROOT), capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=180)
            i = cls.p.stdout.find("{")
            cls.rep = json.loads(cls.p.stdout[i:]) if i >= 0 else {}

    def test_node_and_tool_are_present(self) -> None:
        self.assertIsNotNone(self.node, "本机没有 node ⇒ 部署漂移对账无法验；缺工具算红，不许记成跳过")
        self.assertTrue(TOOL.is_file(), "对账器不在：%s" % TOOL)

    def test_selftest_is_green(self) -> None:
        assert self.p is not None
        if self.p.returncode != 0:
            bad = [r["name"] for r in self.rep.get("rows", []) if not r["pass"]]
            self.fail("自检有红：rc=%s · %s" % (self.p.returncode, " / ".join(bad)))

    def test_planted_differences_are_all_caught(self) -> None:
        """五处种植差异——**每一处**都得有一条对应的『逮住』读数。"""
        rows = self.rep.get("rows", [])
        caught = [r for r in rows if r["name"].startswith("自检·种植差异能被逮住")]
        self.assertEqual(5, len(caught), "种植差异的判据条数不对：%d（应为 5）" % len(caught))
        for r in caught:
            with self.subTest(case=r["name"]):
                self.assertTrue(r["pass"], "%s ⇒ %s" % (r["name"], r["reading"]))

    def test_anti_vacuity_guards_are_present(self) -> None:
        names = [r["name"] for r in self.rep.get("rows", [])]
        self.assertTrue(any("不许为空" in n for n in names), "少了『比对清单不许为空』这道防空转守卫")
        self.assertTrue(any("pick 真选到了键" in n for n in names), "少了『pick 真选到键』这道防空转守卫")

    def test_tool_is_readonly_by_source(self) -> None:
        """只读纪律：对账器不许出现写远端/部署的原语。"""
        src = TOOL.read_text(encoding="utf-8")
        for bad in ("method: \"POST\"", "method: 'POST'", "wrangler deploy", "DELETE", "PUT"):
            self.assertNotIn(bad, src, "对账器里出现了非只读原语：%s" % bad)


if __name__ == "__main__":
    unittest.main()
