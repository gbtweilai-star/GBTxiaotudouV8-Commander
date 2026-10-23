# -*- coding: utf-8 -*-
"""knowledge_lib 判据：**无源会被点名 · 悬空边不许静默 · 回滚不删历史 · 解析手没接就说没接**。

跑法：`py -3.14 gbt_allinone/tests/test_knowledge_lib.py`
（全程写隔离 store；零作用域与"不出网/不起进程"两条是现读 + 静态判据。）
"""
import ast
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone import knowledge_lib as KL                    # noqa: E402
from gbt_allinone.security import policy as POL                 # noqa: E402


class TestKnowledgeLib(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="gbt_kl_test_store_")
        cls._files = tempfile.mkdtemp(prefix="gbt_kl_test_files_")
        cls._old = os.environ.get("GBT_STORE_DIR")
        os.environ["GBT_STORE_DIR"] = cls._tmp

    @classmethod
    def tearDownClass(cls):
        if cls._old is None:
            os.environ.pop("GBT_STORE_DIR", None)
        else:
            os.environ["GBT_STORE_DIR"] = cls._old

    def test_contract_and_fail_closed(self):
        for kind, ops in KL.OPS.items():
            r = KL.run(kind, {"op": "status"})
            self.assertTrue(r["ok"], r)
            self.assertEqual(tuple(r["ops"]), ops, kind)
        self.assertFalse(KL.run("wiki_graph", {"op": "nope"})["ok"])
        self.assertFalse(KL.run("no_such_cap", {})["ok"])

    def test_put_get_and_empty_body_rejected(self):
        put = KL.run("wiki_graph", {"op": "put", "slug": "k1", "title": "算术",
                                    "body": "1+1=2", "sources": ["selftest"]})
        self.assertTrue(put["ok"], put)
        self.assertEqual(put["rev"], 1, put)
        got = KL.run("wiki_graph", {"op": "get", "slug": "k1"})
        self.assertEqual(got["page"]["body"], "1+1=2", got)
        self.assertFalse(KL.run("wiki_graph", {"op": "put", "title": "空",
                                               "body": "  "})["ok"], "空正文不许入库")

    def test_no_source_page_is_named(self):
        KL.run("wiki_graph", {"op": "put", "slug": "nosrc", "title": "无源页", "body": "x"})
        v = KL.run("wiki_graph", {"op": "verify"})
        self.assertIn("nosrc", v["无源页"], v["无源页"])
        self.assertFalse(v["ok"], "有项不过时 verify 必须为 False（判据有牙）")

    def test_dangling_edge_is_named_not_silent(self):
        KL.run("wiki_graph", {"op": "put", "slug": "d1", "title": "指向不存在",
                              "body": "x", "sources": ["selftest"], "links": ["不存在页"]})
        g = KL.run("wiki_graph", {"op": "graph"})
        self.assertTrue(any(e["to"] == "不存在页" for e in g["dangling_edges"]), g["dangling_edges"])
        self.assertIn("不存在页", [e["to"] for e in g["dangling_edges"]])

    def test_rollback_keeps_history(self):
        KL.run("wiki_graph", {"op": "put", "slug": "r1", "title": "版本页", "body": "v1",
                              "sources": ["selftest"]})
        KL.run("wiki_graph", {"op": "put", "slug": "r1", "title": "版本页", "body": "v2",
                              "sources": ["selftest"]})
        rb = KL.run("wiki_graph", {"op": "rollback", "slug": "r1", "rev": 1})
        self.assertTrue(rb["ok"], rb)
        self.assertEqual(rb["新版本"], 3, "回滚=产生新版本，不是改写")
        cur = KL.run("wiki_graph", {"op": "get", "slug": "r1"})["page"]
        self.assertEqual(cur["body"], "v1", cur)
        self.assertEqual(cur["rolled_back_from"], 1, cur)
        hist = KL.run("wiki_graph", {"op": "history", "slug": "r1"})
        self.assertEqual(len(hist["versions"]), 3, "历史一版都不许少")
        self.assertFalse(KL.run("wiki_graph", {"op": "rollback", "slug": "r1", "rev": 99})["ok"])

    def test_neighbors_walk(self):
        # 三页都要**真建**（只把它写成链接目标 = 悬空边，不算建页 —— 模块会如实报悬空）
        for s, links in (("n1", ["n2"]), ("n2", ["n3"]), ("n3", [])):
            KL.run("wiki_graph", {"op": "put", "slug": s, "title": s, "body": "x",
                                  "sources": ["selftest"], "links": links})
        nb = KL.run("wiki_graph", {"op": "neighbors", "slug": "n1", "depth": 2})
        self.assertEqual(set(nb["邻域"]), {"n1", "n2", "n3"}, nb)

    def test_intake_local_text_and_unwired_type(self):
        md = Path(self._files) / "笔记.md"
        md.write_text("# 标题\n\n正文一\n", encoding="utf-8")
        r = KL.run("doc_intake", {"op": "intake", "path": str(md)})
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["入库"], "笔记", r)
        self.assertTrue(r["出处"], r)
        self.assertIn("正文一", KL.run("wiki_graph", {"op": "get", "slug": "笔记"})["page"]["body"])
        binp = Path(self._files) / "x.bin"
        binp.write_bytes(b"\x00\x01\x02")
        bad = KL.run("doc_intake", {"op": "intake", "path": str(binp)})
        self.assertFalse(bad["ok"], "未接的解析手必须如实拒，不许拿空页充数")
        self.assertIn("解析手未接", bad["error"], bad)

    def test_sources_reports_honestly(self):
        s = KL.run("doc_intake", {"op": "sources"})
        self.assertEqual(s["本地文件"]["状态"][:2], "可用", s)
        self.assertTrue(s["外部源（飞书 / GitLab）"], "外部源必须逐条报状态（没接就说没接）")

    def test_zero_scope_by_real_read(self):
        for kind in KL.KINDS:
            for op in KL.OPS[kind]:
                d = POL.evaluate(kind, {"op": op})
                self.assertEqual(tuple(getattr(d, "scopes", ())), (), "%s.%s 必须零作用域" % (kind, op))

    def test_no_network_no_subprocess_static(self):
        src = (_REPO / "gbt_allinone" / "knowledge_lib.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)
                    for a in n.names}
        imported |= {(n.module or "").split(".")[0] for n in ast.walk(tree)
                     if isinstance(n, ast.ImportFrom)}
        self.assertFalse(imported & {"subprocess", "socket", "urllib", "requests", "http"},
                         "知识库不许自己出网/起进程：%s" % sorted(imported))

    def test_registered_in_registry(self):
        from gbt_allinone import caps_registry as CR
        for kind in KL.KINDS:
            self.assertIn(kind, CR.BENIGN_CAPS, "能力位没登记进注册表：%s" % kind)
            # 🔴 2026-10-17 翻正（留痕）：`handler` 现在只表示**分派键真名**（必须==cap 名，
            #   由 test_capability_registry 咬住）；"共享实现在 knowledge_lib" 这件事改记 `impl`。
            #   原先这条要求 handler=="knowledge_lib"，与 test_capability_registry 的
            #   "handler 必须写分派真名"直接冲突 ⇒ 两条判据必有一红。
            self.assertEqual(CR.BENIGN_CAPS[kind].get("impl"), "knowledge_lib")


if __name__ == "__main__":
    unittest.main(verbosity=2)
