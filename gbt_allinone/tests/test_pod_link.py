# -*- coding: utf-8 -*-
"""pod_link 判据：**契约面 · 作用域形状 · 传完必须对账 · 令牌不回显 · 零执行面**。

跑法：`py -3.14 -m unittest gbt_allinone.tests.test_pod_link -v`
（没有卡钥匙/没有卡时，联网类用例**如实 skip**，不假装跑过。）
"""
import ast
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone.tools import pod_link as PL                 # noqa: E402
from gbt_allinone.security import policy as POL               # noqa: E402


def _has_key() -> bool:
    return bool(PL._key())


class TestPodLink(unittest.TestCase):
    def test_contract_face(self):
        w = PL.run_dispatch("where")
        self.assertTrue(w["ok"], w)
        # 🔴 2026-10-17 翻正（留痕 · 原断言 / 为什么翻 / 现口径）：
        #   原断言：ops 恰好是 6 个只读/传输 op，且 hard_rules 必须含「不创建」。
        #   为什么翻：主人令 2026-10-16「换新卡记得关旧的别浪费钱」之后，`pod_link` 真加了
        #     `start`/`stop`/`create`（**花钱**）与 `gpus`（只读列卡）；三者都**强制**
        #     `confirm="主人已授权"`。旧断言把**新设计当故障**，还要求一条与实现相反的文案。
        #   现口径：① ops 认全部 10 个；② 花钱 op 的**人闸**改成硬判据（缺 confirm 必拒）；
        #     ③ 令牌不回显 / 传完对账 两条铁律照旧咬。
        # 🔴 2026-10-25 再翻一次（留痕 · 原期望 / 新口径 / 为什么翻）：
        #   原期望：ops **恰好**是上面硬写的 10 个。
        #   新口径：与派生源 PL._OPS 对齐；并仍然咬住三条牙 ——
        #           ① 那 10 个历史 op 缺任何一个照样红（能力被砍就是真故障）；
        #           ② ops 不许有重复项（注册表被写坏）；
        #           ③ hard_rules 里「不回显」那条照旧咬（下面已有）。
        #   为什么翻：实现后来真加了 ccount / ports / logs 三个只读 op，
        #     硬写的 10 个把**新增当故障** ⇒ 报「first set 多出 ports, logs」。
        #   这不是放宽：缺一个历史 op、或出现重复，都还是红。
        ops = list(w["ops"])
        self.assertEqual(set(ops), set(PL._OPS),
                         "where 报的 ops 必须与派生源 _OPS 一致：%r vs %r" % (ops, list(PL._OPS)))
        for core in ("status", "ls", "up", "down", "run", "where",
                     "start", "stop", "gpus", "create"):
            self.assertIn(core, ops, "历史 op 丢了：%s（现读 %r）" % (core, ops))
        self.assertEqual(len(ops), len(set(ops)), "ops 有重复项：%r" % (ops,))
        for k in ("走的路", "hard_rules", "作用域"):
            self.assertIn(k, w, "契约面缺 %s" % k)
        hard = " ".join(w["hard_rules"])
        self.assertIn("不回显", hard, hard)
        self.assertIn("对账", hard, hard)
        self.assertIn("主人已授权", hard, "花钱 op 的人闸必须写在契约面上")
        # 负对照：花钱 op 缺 confirm ⇒ 必拒，且理由是 need_owner_confirm（不许"没人点头也花钱"）
        for op in ("start", "stop", "create"):
            r = PL.run_dispatch(op)
            self.assertFalse(r.get("ok"), (op, r))
            self.assertEqual(r.get("reason"), "need_owner_confirm", (op, r))

    def test_status_lists_pods_without_leaking_token(self):
        if not _has_key():
            self.skipTest("没配卡钥匙 ⇒ 跳过，不假装跑过")
        st = PL.run_dispatch("status")
        self.assertTrue(st["ok"], st)
        blob = str(st)
        # 🔴 令牌绝不进返回（连片段都不许）：拿真 token 反查
        tok = (PL._pick().get("env") or {}).get("JUPYTER_PASSWORD") or ""
        if tok:
            self.assertNotIn(tok, blob, "返回里出现了卡的 JUPYTER_PASSWORD！")
        self.assertIn("pod_count", st, st)

    def test_ls_roundtrip_against_real_pod(self):
        if not _has_key() or not PL._pick():
            self.skipTest("没有卡 ⇒ 跳过")
        r = PL.run_dispatch("ls", path="/")
        if not r.get("ok"):
            self.skipTest("卡上 Jupyter 不通 ⇒ 跳过（%s）" % r.get("error"))
        self.assertIn("count", r, r)

    def test_up_needs_both_ends_fail_closed(self):
        for kw in ({}, {"local": "x"}, {"remote": "/y"}):
            r = PL.run_dispatch("up", **kw)
            self.assertFalse(r["ok"], r)
            self.assertTrue(r["fail_closed"], r)

    def test_down_up_报告里必须带对账字段(self):
        r = PL.run_dispatch("down", remote="", local="")
        self.assertFalse(r["ok"], r)
        self.assertTrue(r["fail_closed"], r)
        src = Path(PL.__file__).read_text(encoding="utf-8")
        for must in ("回读", "sha256_16", "落盘"):
            self.assertIn(must, src, "对账字段少了 %s" % must)

    def test_unknown_op_fail_closed(self):
        r = PL.run_dispatch("frobnicate")
        self.assertFalse(r["ok"], r)
        self.assertTrue(r["fail_closed"], r)

    def test_scope_shape_matches_what_it_really_does(self):
        """公网读=零 · 送数据出去=data_export · 远端跑=process_execute · 未知名挂满。"""
        zero = ["", "status", "ls", "down", "where"]
        for op in zero:
            self.assertEqual(tuple(POL.evaluate("pod_link", {"op": op}).scopes), (), op)
        self.assertEqual(tuple(POL.evaluate("pod_link", {"op": "up"}).scopes),
                         ("data_export", "filesystem_write"))
        # 口径一致性（同族 mcp_call / cadgen）：远端跑代码 = process_execute，**不叠出境闸**
        self.assertEqual(tuple(POL.evaluate("pod_link", {"op": "run"}).scopes),
                         ("process_execute",))
        self.assertEqual(tuple(POL.evaluate("pod_link", {"op": "nope"}).scopes),
                         ("process_execute", "data_export", "filesystem_write"))

    def test_no_local_execution_surface(self):
        """机检：本件**不在本机跑进程**（远端执行走 WebSocket，不是 subprocess）。"""
        tree = ast.parse(Path(PL.__file__).read_text(encoding="utf-8", errors="replace"))
        # 🔴 第 4 次栽在同一个坑：**按名字禁词**（`import os` 被当执行面）而不是**按行为判**。
        #    正解：只禁 `subprocess`；`os` 只禁**属主是 os 的**那几个危险调用（os.environ 是只读的）。
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[0] == "subprocess":
                        bad.append("import " + a.name)
            elif isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name) and fn.id in ("eval", "exec", "compile"):
                    bad.append(fn.id)
                if isinstance(fn, ast.Attribute) and getattr(fn.value, "id", "") == "os" \
                        and fn.attr in ("system", "popen", "spawn", "execv", "fork"):
                    bad.append("os." + fn.attr)
        self.assertEqual(bad, [], "本机不该有执行面：%s" % bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
