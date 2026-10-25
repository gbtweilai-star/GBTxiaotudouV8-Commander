# -*- coding: utf-8 -*-
"""offload_distill 判据：**引的出处必须真在盘上** · **四条机制齐** · **边界不许说反** · **整位零作用域零执行**。

跑法：`py -3.14 -m unittest gbt_allinone.tests.test_offload_distill -v`
"""
import ast
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone.tools import offload_distill as OD          # noqa: E402
from gbt_allinone.security import policy as POL               # noqa: E402


class TestOffloadDistill(unittest.TestCase):
    def test_status_identity_and_four_mechanisms(self):
        st = OD.run("status")
        self.assertTrue(st["ok"], st)
        self.assertEqual(set(st["ops"]), {"status", "where", "mechanism", "map", "probe"}, st["ops"])
        up = st["上游"]
        self.assertEqual(up["repo"], "Edge0-AI/Edge0")
        self.assertEqual(up["license"], "Apache-2.0")
        self.assertIn("2609.18063", up["paper"])
        self.assertEqual([m["n"] for m in st["蒸馏条目"]], [1, 2, 3, 4], st["蒸馏条目"])

    def test_every_mechanism_quotes_a_real_upstream_file(self):
        """🔴 **出处纪律**：每条机制引的上游文件必须**真在盘上**（防我编引用）。"""
        if not OD._UP.is_dir():
            self.skipTest("上游不在盘（`_upstream/Edge0` 未落位）⇒ 跳过，不假装跑过")
        r = OD.run("mechanism")
        self.assertEqual(r["共"], 4, r)
        for m in r["items"]:
            for k in ("原文", "我们的话", "用处", "判据"):
                self.assertTrue(m.get(k), "机制 %s 缺「%s」" % (m["n"], k))
            self.assertIn("**", m["我们的话"], "我们的话该是我们自己的口径：%s" % m["我们的话"])
            for token in [t.strip() for t in str(m["src"]).replace("·", " ").split()]:
                if token.endswith(".md"):
                    self.assertTrue((OD._UP / token).is_file(),
                                    "机制 %s 引的文件不在盘：%s" % (m["n"], token))

    def test_mechanism_by_number_and_fail_closed(self):
        one = OD.run("mechanism", n=1)
        self.assertEqual(one["items"][0]["n"], 1, one)
        bad = OD.run("mechanism", n=99)
        self.assertFalse(bad["ok"], bad)
        self.assertTrue(bad["fail_closed"], bad)

    def test_map_is_the_tentacle_language(self):
        mp = OD.run("map")
        self.assertGreaterEqual(mp["条数"], 5, mp)
        text = " ".join(b for _a, b in [(x["它的"], x["我们的触手语言"]) for x in mp["映射"]])
        self.assertIn("触手", text, "映射必须用触手语言说：%s" % text)
        keys = " ".join(x["它的"] for x in mp["映射"])
        for must in ("mmap", "LRU", "prerouter", "重叠", "不合并"):
            self.assertIn(must, keys, "映射缺 %s：%s" % (must, keys))

    def test_probe_reports_routes_honestly(self):
        """🔴 边界不许说反：**非 Apple Silicon 机器上 MLX 那条必须报不能走，并给出原因**。"""
        p = OD.run("probe")
        self.assertTrue(p["ok"], p)
        self.assertIn("total_gb", p["ram"], p["ram"])
        self.assertIn("disk_free_gb", p)
        self.assertGreaterEqual(len(p["routes"]), 2, p["routes"])
        for r in p["routes"]:
            self.assertIn("能走", r, r)
            if not r["能走"]:
                self.assertTrue(r.get("为什么不能"), "不能走就必须说清为什么：%s" % r)
        if p["platform"] != "Darwin/arm64":
            mlx = [r for r in p["routes"] if "MLX" in r["要求"]]
            self.assertTrue(mlx, p["routes"])
            self.assertFalse(mlx[0]["能走"], "非 Apple Silicon 却报 MLX 路线能走 = 说反了：%s" % mlx[0])

    def test_unknown_op_fail_closed(self):
        u = OD.run("frobnicate")
        self.assertFalse(u["ok"], u)
        self.assertTrue(u["fail_closed"], u)

    def test_scope_shape_all_read_zero(self):
        """整位只读 ⇒ 五个 op **全零作用域**（未知名由处理器 fail-closed）。"""
        for op in ("", "status", "where", "mechanism", "map", "probe"):
            self.assertEqual(tuple(POL.evaluate("offload_distill", {"op": op}).scopes), (), op)

    def test_no_execution_or_network_surface(self):
        """机检：**零执行 · 零出网**（不许 subprocess/urllib/socket/eval/exec）。"""
        tree = ast.parse(Path(OD.__file__).read_text(encoding="utf-8", errors="replace"))
        # 🔴 首版把 `os` 与 `run` 也当禁词 ⇒ `import os` 与本件自己的 `def run(op)` 被误报
        #    （同族教训：判据要按「有没有执行面」判，不许按名字一刀切）。
        banned_mods = {"subprocess", "urllib", "requests", "socket", "http",
                       "importlib", "pickle", "multiprocessing"}
        banned_names = {"eval", "exec", "compile", "__import__"}
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[0] in banned_mods:
                        bad.append(("import %s" % a.name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] in banned_mods:
                    bad.append(("from %s" % node.module, node.lineno))
            elif isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name) and fn.id in banned_names:
                    bad.append((fn.id, node.lineno))
                # 🔴 只禁**属主是 os/子进程的**那些（首版按属性名一刀切 ⇒ `platform.system()`
                #    被误报 3 处；`platform.system` 是只读的，跟 `os.system` 完全两回事）。
                if isinstance(fn, ast.Attribute):
                    base = getattr(fn.value, "id", "") or ""
                    if (base == "os" and fn.attr in ("system", "popen", "spawn", "execv", "fork")) \
                       or (base == "shutil" and fn.attr not in ("which", "disk_usage")):
                        bad.append(("%s.%s" % (base, fn.attr), node.lineno))
        # `shutil.which` / `shutil.disk_usage` 是只读的，允许
        self.assertEqual(bad, [], "出现执行/出网面：%s" % bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
