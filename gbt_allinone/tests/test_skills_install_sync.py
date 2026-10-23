"""技能唯一真相判据 · 分叉是红，不是风格问题（主人令 2026-09-27）。

**为什么立这条**：同一份技能有两个真身——仓内 `skills/`（源）与技能枢纽
`~/.agents/skills/`（运行时真正读的那份）。2026-09-27 实测：两者**长期无人对账**
（全仓 `grep -rn "skills-lock" tools/ gbt_allinone/` 零命中），于是 `gbt-security`
源 43K / 装 31K、差 1054 行 —— 我那一整轮"能力覆盖补丁"**只落在源上，运行时一个字节都没看见**。
这与 F18（「盘上对」被念成「生效了」）同型：**改在盘上，不等于改在运行时**。

**判据**（只调 `tools/skills_sync.py`，不重写第二份读数）：
  A. **无分叉**：自有技能里 `源指纹 ≠ 装指纹` 的 = 0；
  B. **无未装**：源里有、枢纽里没有的 = 0；
  C. **无孤儿**：枢纽里有、源里没有的 = 0（只有一边有，也是分叉）；
  D. **不是空集合在过关**：源必须真枚举到技能、枢纽根必须存在 ——
     否则"一个都没扫到"会伪装成"全都一致"（本仓最贵的教训就是假绿）。

红了怎么修（判据里直说，不让人猜）：`python tools/skills_sync.py sync`
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "skills_sync.py"

# 同源镜像对（铁律 11）：左边是**源**，右边是**镜像**，必须逐字节相等。
# 为什么单列：同一份内容两处各写一份 = 下一处分叉的种子。实测两人份 `LAYOUT.md`
# 目前字节一致，但**没有任何判据盯着** ⇒ 谁改一份、另一份就静静变旧。
MIRROR_PAIRS = [
    ("gbt_allinone/LAYOUT.md", "LAYOUT.md"),
]


def _load_tool():
    """按文件路径加载工具（tools/ 不是包，没有 __init__.py）。"""
    spec = importlib.util.spec_from_file_location("skills_sync_probe", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestSkillsInstallSync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = _load_tool()
        cls.survey = cls.tool.survey()

    def test_tool_present_and_ran(self):
        """D. 防假绿：工具必须在位、源必须真枚举到技能、枢纽根必须存在。"""
        self.assertTrue(TOOL.is_file(), f"同步器不在位：{TOOL}")
        self.assertNotIn("error", self.survey, f"对账失败：{self.survey.get('error')}")
        total = len(self.survey["rows"])
        self.assertGreater(total, 50,
                           f"只枚举到 {total} 个技能 —— 要么源目录空了，要么读数漏了"
                           f"（空集合过关=假绿，本判据专门挡它）")
        home = Path(self.survey["home_hub"])
        self.assertTrue(home.is_dir(),
                        f"运行时枢纽不存在：{home} ⇒ 修法：python tools/skills_sync.py sync")

    def test_no_drift(self):
        """A. 无分叉：源与装必须逐字节一致。"""
        bad = [r for r in self.survey["rows"] if r["status"] == "分叉"]
        if bad:
            detail = "；".join(
                f"{r['skill']}（内容异 {len(r['changed'])}"
                + (f" · 残留 {','.join(r['residue'][:1])}" if r["residue"] else "") + "）"
                for r in bad[:6])
            self.fail(f"技能已分叉 {len(bad)} 个：{detail}\n"
                      f"⇒ 修法：python tools/skills_sync.py sync（覆盖前会自动备份枢纽那份）")

    def test_none_missing(self):
        """B. 无未装：源里有技能，枢纽里就必须有 —— 否则运行时读不到它。"""
        bad = [r["skill"] for r in self.survey["rows"] if r["status"] == "未安装"]
        if bad:
            self.fail(f"源里有 {len(bad)} 个技能从未安装到枢纽（运行时看不见）：{', '.join(bad[:8])}\n"
                      f"⇒ 修法：python tools/skills_sync.py sync")

    def test_no_orphan(self):
        """C. 无孤儿：枢纽里有、源里没有 = 只有一边有，同样是分叉。"""
        bad = [r["skill"] for r in self.survey["rows"] if r["status"].startswith("孤儿")]
        if bad:
            self.fail(f"枢纽里有 {len(bad)} 个技能在源里找不到出处：{', '.join(bad[:8])}\n"
                      f"⇒ 要么在仓内 skills/ 补源，要么把枢纽那份归档")

    def test_summary_consistent(self):
        """读数自洽：汇总数字必须与逐行明细对得上（对不上就是读数坏了）。"""
        s = self.survey["summary"]
        rows = self.survey["rows"]
        self.assertEqual(s["drift"], sum(1 for r in rows if r["status"] == "分叉"))
        self.assertEqual(s["missing"], sum(1 for r in rows if r["status"] == "未安装"))
        self.assertEqual(s["orphan"], sum(1 for r in rows if r["status"].startswith("孤儿")))

    def test_mirrors_identical(self):
        """铁律 11：同源镜像必须与源**逐字节相等**（否则就是下一处分叉）。"""
        for src, mirror in MIRROR_PAIRS:
            a, b = ROOT / src, ROOT / mirror
            self.assertTrue(a.is_file(), f"镜像的源不存在：{src}")
            self.assertTrue(b.is_file(), f"镜像不存在：{mirror}")
            if a.read_bytes() != b.read_bytes():
                self.fail(f"镜像已分叉：{src}（{a.stat().st_size}B） ≠ "
                          f"{mirror}（{b.stat().st_size}B）\n"
                          f"⇒ 修法：只改源 {src}，然后 cp {src} {mirror}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
