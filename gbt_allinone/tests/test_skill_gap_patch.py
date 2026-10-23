"""R-H613（2026-09-25）· 「域规程待补清单」生成器 —— **只出内容，绝不动技能件**。

被测对象：`tools/codex-scripts/gen-skill-gap-patch.py`

为什么要守它（而不是只跑一次看看）：
  它读的是**技能规程**（两个根：工作区源稿 + managed 托管目录），而那两个根
  `verify-distill` 要求**逐字节一致**；managed 又属**托管技能目录**。
  ⇒ 一个"顺手帮你补上"的实现会把仓推到红，而且是在**没授权**的地方动的刀。
  所以这里钉的第一条就是**它一个字节都不许写**。

判据（四条，都要有牙）：
  1. **只读**：跑一遍 `collect()` + `render()`，两个根里所有文件的 sha256 必须**一个都没变**；
  2. **与验收器同源**：它报的"待补域"必须与 `verify-distill.py --all` 判红的域**完全一致**
     （不是各算各的）；不一致就说明两边判据漂开了；
  3. 只对**真有缺口**的域出清单；没有缺口的域**不许**出现"待补"字样；
  4. 每位待补项都要带**是什么 / 过哪道门 / 怎么调**三件套 —— 少了就只是"缺"，
     不是"可粘贴的补丁内容"。
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "codex-scripts" / "gen-skill-gap-patch.py"
VERIFY = ROOT / "tools" / "codex-scripts" / "verify-distill.py"


def _load():
    spec = importlib.util.spec_from_file_location("gen_skill_gap_patch", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GEN = _load()


def _snapshot(dirs) -> dict:
    out = {}
    for d in dirs:
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            if p.is_file():
                out[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


class GeneratorIsReadOnlyTest(unittest.TestCase):
    def test_it_writes_nothing(self) -> None:
        roots = [ROOT / "skills", GEN.MANAGED]
        before = _snapshot(roots)
        self.assertTrue(before, "两个根一个文件都没扫到 ⇒ 判据空转（假绿）")
        rep = GEN.collect()
        text = GEN.render(rep)
        self.assertGreater(len(text), 200, "清单是空的 ⇒ 判据没意义")
        after = _snapshot(roots)
        changed = [k for k in set(before) | set(after) if before.get(k) != after.get(k)]
        self.assertEqual([], changed, "生成器**改动了技能件**（它只许读）：%s" % changed[:5])


class GapSetMatchesVerifierTest(unittest.TestCase):
    def test_same_domains_as_verify_distill(self) -> None:
        r = subprocess.run([sys.executable, str(VERIFY), "--all"], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=600)
        out = (r.stdout or "") + (r.stderr or "")
        verdict_domains = set(re.findall(r"(?m)^(\w+)\s+FAIL", out))
        self.assertTrue(verdict_domains, "验收器没报出任何 FAIL 域 ⇒ 判据无法交叉核对")
        mine = set(GEN.collect()["gap_domains"])
        self.assertEqual(verdict_domains, mine,
                         "生成器与验收器各算各的：验收器 %s / 生成器 %s"
                         % (sorted(verdict_domains), sorted(mine)))


class PatchContentShapeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rep = GEN.collect()
        cls.text = GEN.render(cls.rep)

    def test_only_gap_domains_are_listed(self) -> None:
        clean = [r for r in self.rep["rows"] if not r["missing"] and not r["note"]]
        for r in clean:
            self.assertNotIn("【域 %s " % r["domain"], self.text,
                             "%s 没有缺口却被列进待补" % r["domain"])

    def test_each_missing_item_has_three_fields(self) -> None:
        for r in self.rep["rows"]:
            for k in r["missing"]:
                block = self.text.split("`%s`" % k, 1)[-1][:400]
                self.assertIn("门：", block, "%s 没写『过哪道门』" % k)
                self.assertIn("调法：", block, "%s 没给调法" % k)

    def test_says_it_did_not_touch_anything(self) -> None:
        self.assertIn("没有**改任何文件", self.text.replace("本器**没有**改任何文件", "没有**改任何文件"),
                      "输出里没写明它没动文件 ⇒ 读的人会以为已经补好了")

    def test_json_mode_is_parsable(self) -> None:
        r = subprocess.run([sys.executable, str(TOOL), "--json"], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=300)
        data = json.loads(r.stdout)
        self.assertIn("gap_domains", data)
        self.assertEqual(data["gap_count"], len(data["gap_domains"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
