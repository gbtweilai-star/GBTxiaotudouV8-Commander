# -*- coding: utf-8 -*-
"""黑客大脑扫描器的**范围 / 精度 / 诚实账**回归（2026-10-09 根因修复固化作）。

锁住四类已修根因，任何一条回归都会红：
  ① 范围：只扫自有代码面（scan_scope 唯一口径），不再把 _upstream(29032 个 .py) 当自有代码；
  ② 精度：CWE-338 弱随机数不再把桌面宠物的 random.choice 报成 medium；
  ③ 精度：命令注入必须是**调用**（os.system( ），规则表里的中文说明不算；
  ④ 诚实：坏正则不许被逐文件静默吞掉变成「0 条 = 干净」（fail-open 假绿）。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gbt_allinone.security.security_brain import (  # noqa: E402
    HackerBrain, _owned_py_files, ROOT)

_EXTERNAL = {"_upstream", "vendor", "_legacy_sources", "quant_workspace",
             ".shadow-repo", ".scratch", ".backups", "archive", "node_modules",
             ".git", "store", "__pycache__", ".pylibs"}


def _scan_in(text: str, severity: str = "medium") -> dict:
    """把一段源码放进隔离目录扫一遍（不动真仓）。"""
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "sample.py").write_text(text, encoding="utf-8")
        hb = HackerBrain()
        hb.project_root = Path(td)
        return hb.scan_vulnerabilities(severity)


class HackerScanScopeTest(unittest.TestCase):

    def test_no_broken_regex_patterns(self):
        """④ 任何一条模式写坏，必须能被报出来（而不是让全仓变 0 条）。"""
        hb = HackerBrain()
        self.assertEqual(hb.pattern_errors, [], hb.pattern_errors)
        self.assertEqual(len(hb._compiled), len(hb.vuln_db))
        self.assertGreater(len(hb.vuln_db), 10)

    def test_owned_files_exclude_external_corpora(self):
        """① 剪枝必须在进入子目录之前生效：外部语料一个文件都不许进。"""
        files = list(_owned_py_files(ROOT))
        self.assertGreater(len(files), 50, "自有代码面不该被剪空")
        for f in files:
            top = f.relative_to(ROOT).parts[0]
            self.assertNotIn(top, _EXTERNAL, "外部语料混进扫描面: %s" % f)

    def test_attack_surface_is_scoped_and_density_based(self):
        """① 攻击面只算自有代码 + 风险档按密度判（不再恒定饱和 100）。"""
        hb = HackerBrain()
        r = hb.map_attack_surface()
        self.assertTrue(r["ok"])
        self.assertEqual(r["scope"], "own_code_only")
        self.assertIn("boundary", r)
        self.assertIn("risk_density", r)
        # 全仓 rglob 会是 4 万+；剪枝后是千级
        self.assertLess(r["files_scanned"], 5000)
        self.assertGreater(r["files_scanned"], 50)

    def test_placeholder_and_fragment_secrets_not_reported(self):
        """② 顺序占位串 / 被 + 拼接的片段不许报成密钥泄露（两条 critical 假报）。"""
        r = _scan_in('API_KEY = "sk-abcdefghijklmnopqrstuvwxyz0123"\n'
                     'token = "gbtv8-" + "0" * 32\n')
        self.assertEqual(r["total"], 0, r.get("vulnerabilities"))
        counts = r["exempted"]["counts"]
        self.assertGreaterEqual(counts.get("secret_placeholder", 0), 1)
        self.assertGreaterEqual(counts.get("secret_fragment", 0), 1)

    def test_os_system_prose_is_not_injection(self):
        """③ 命令注入必须是调用；规格说明里的 os.system 字样不算漏洞。"""
        r = _scan_in('WHAT = "subprocess/os.system 吃变量"\n')
        self.assertEqual(r["total"], 0, r.get("vulnerabilities"))

    def test_os_system_call_still_reported(self):
        """③ 反向对照：真调用必须照报（豁免不许把检测器弄瞎）。"""
        r = _scan_in('import os\nos.system(user_input)\n')
        self.assertGreaterEqual(r["critical"], 1, r.get("vulnerabilities"))

    def test_bare_except_in_comment_not_reported(self):
        """② 注释里的 except: 不会执行 —— 与执行类同判据豁免。"""
        r = _scan_in("# 原来这里是 except: pass\nx = 1\n")
        self.assertEqual(r["total"], 0, r.get("vulnerabilities"))

    def test_decorative_random_downgraded_but_registered(self):
        """② 装饰性 random.choice 不再报 medium，但必须**仍登记**（info 可取回）。"""
        src = "import random\nmsg = random.choice(['a', 'b'])\n"
        self.assertEqual(_scan_in(src, "medium")["total"], 0)
        info = _scan_in(src, "info")
        self.assertGreaterEqual(info["total"], 1, "裸 random.* 必须仍可检索")
        self.assertTrue(any("仅登记" in v["title"] for v in info["vulnerabilities"]))

    def test_security_random_still_high(self):
        """② 反向对照：安全值取弱随机数仍报 high。"""
        r = _scan_in("import random\ntoken = str(random.random())\n")
        self.assertGreaterEqual(r["high"], 1, r.get("vulnerabilities"))

    def test_scan_reports_scanner_status(self):
        r = _scan_in("x = 1\n")
        self.assertEqual(r.get("scanner_status"), "ok")
        self.assertEqual(r.get("pattern_errors"), [])


if __name__ == "__main__":
    unittest.main()
