# -*- coding: utf-8 -*-
"""`code_patch` · 契约测试（2026-09-23 接「改代码过门」时立的钉子）。

守四件事：
  ① **机械闸真的会拒**：not_found / ambiguous / no_change / binary / outside_repo / stale_content
  ② **逐字节保真**：只动 find 那几个字节 —— CRLF / BOM / 其余行一个字节都不许变
     （这是本能力存在的理由之一：文本层替换会把**整个文件的行尾**改掉）
  ③ **默认不写**：`op` 不写 = dry_run，文件哈希必须纹丝不动
  ④ **可回滚**：apply → rollback 必须回到改前哈希；**文件被人动过之后回滚要拒**
  ⑤ **门真的拦**：`op=apply` 挂 `filesystem_write`；未授权时不许写

隔离：临时件放 `<仓>/.scratch/_code_patch_test/`（**必须在仓内** —— 仓外路径本就该被拒，
拿仓外当测试目录会把"闸生效"误读成"功能坏了"）。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("GBT_STORE_DIR", tempfile.mkdtemp(prefix="gbt_cp_test_"))

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gbt_allinone.tools import code_patch as CP          # noqa: E402
from gbt_allinone.security import policy                  # noqa: E402
from gbt_allinone import api                              # noqa: E402


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class _Base(unittest.TestCase):
    def setUp(self):
        self.dir = _ROOT / ".scratch" / "_code_patch_test"
        if self.dir.exists():
            shutil.rmtree(self.dir, ignore_errors=True)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(self.dir, ignore_errors=True))

    def _mk(self, name: str, data: bytes) -> tuple:
        p = self.dir / name
        p.write_bytes(data)
        return p, str(p.relative_to(_ROOT)).replace("\\", "/")


class MechanismTests(_Base):
    """① 机械闸：每一条都要**真的拒**，并给出机读 reason_code。"""

    def _code(self, fn, *a, **kw) -> str:
        try:
            fn(*a, **kw)
        except CP.CodePatchError as e:
            return e.code
        return ""

    def test_not_found(self):
        _, rel = self._mk("a.txt", b"hello world\n")
        self.assertEqual("not_found", self._code(CP.dry_run, rel, "nope", "yes"))

    def test_ambiguous_refuses_to_pick_one(self):
        _, rel = self._mk("b.txt", b"dup\ndup\n")
        self.assertEqual("ambiguous", self._code(CP.dry_run, rel, "dup", "one"))

    def test_no_change_refused(self):
        _, rel = self._mk("c.txt", b"x\n")
        self.assertEqual("no_change", self._code(CP.dry_run, rel, "x", "x"))

    def test_binary_refused(self):
        _, rel = self._mk("d.bin", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
        self.assertEqual("binary_file", self._code(CP.dry_run, rel, "PNG", "JPG"))

    def test_outside_repo_refused(self):
        outside = Path(tempfile.gettempdir()) / "gbt_cp_outside.txt"
        outside.write_bytes(b"zzz")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        self.assertEqual("outside_repo",
                         self._code(CP.dry_run, str(outside), "zzz", "yyy"))

    def test_stale_content_refused(self):
        _, rel = self._mk("e.txt", b"abc\n")
        self.assertEqual("stale_content",
                         self._code(CP.dry_run, rel, "abc", "xyz", "0" * 64))

    def test_unknown_op_refused(self):
        _, rel = self._mk("f.txt", b"abc\n")
        self.assertEqual("unknown_op", self._code(CP.run, {"path": rel, "find": "abc",
                                                           "replace": "x", "op": "nuke"}))


class ByteFidelityTests(_Base):
    """② 逐字节保真 + ③ 默认不写。"""

    CRLF = b"line1\r\nline2\r\nline3\r\n"
    BOM = b"\xef\xbb\xbfalpha\n"

    def test_default_op_does_not_write(self):
        p, rel = self._mk("g.txt", self.CRLF)
        before = _sha(p)
        r = CP.run({"path": rel, "find": "line2", "replace": "LINE-TWO"})
        self.assertEqual("dry_run", r["op"])
        self.assertFalse(r["wrote"])
        self.assertEqual(before, _sha(p), "默认档竟然写了盘")

    def test_apply_preserves_crlf_and_only_touches_find(self):
        p, rel = self._mk("h.txt", self.CRLF)
        before = p.read_bytes()
        r = CP.apply(rel, "line2", "LINE-TWO")
        after = p.read_bytes()
        self.assertTrue(r["wrote"])
        # 只动了那一处：把 replace 换回 find 应当**逐字节**回到原样
        self.assertEqual(before, after.replace(b"LINE-TWO", b"line2"))
        # CRLF 必须原样：改前 3 个（line1/line2/line3 各一个），改后**还是 3 个**
        # （line2 那一行整段被替换，但它的 CRLF 没被吃掉也没被复制）
        self.assertEqual(before.count(b"\r\n"), after.count(b"\r\n"),
                         "CRLF 个数变了 ⇒ 文本层替换把整个文件的行尾改了")
        self.assertEqual(3, after.count(b"\r\n"))
        self.assertIn(b"line1\r\n", after)
        self.assertIn(b"line3\r\n", after)

    def test_apply_preserves_bom(self):
        p, rel = self._mk("i.txt", self.BOM)
        CP.apply(rel, "alpha", "beta")
        self.assertTrue(p.read_bytes().startswith(b"\xef\xbb\xbf"), "BOM 被吃掉了")

    def test_hashes_and_delta_are_reported(self):
        p, rel = self._mk("j.txt", b"aaa\n")
        r = CP.dry_run(rel, "aaa", "bbbb")
        self.assertEqual(_sha(p), r["before_sha256"])
        self.assertEqual(1, r["bytes_delta"])
        self.assertEqual("dry_run", r["op"])


class RollbackTests(_Base):
    """④ 可回滚；**文件被人动过之后回滚要拒**。"""

    def test_apply_then_rollback_returns_to_before_hash(self):
        p, rel = self._mk("k.txt", b"one\ntwo\n")
        before = _sha(p)
        r = CP.apply(rel, "two", "TWO")
        self.assertNotEqual(before, _sha(p))
        rid = r["receipt_id"]
        rr = CP.rollback(rid)
        self.assertTrue(rr["wrote"])
        self.assertEqual(before, _sha(p), "回滚没回到改前哈希")

    def test_receipt_is_written_and_contains_no_whole_file(self):
        p, rel = self._mk("l.txt", b"alpha\nbeta\n")
        r = CP.apply(rel, "beta", "BETA")
        rec = json.loads(Path(r["receipt"]).read_text(encoding="utf-8"))
        for k in ("path", "find", "replace", "before_sha256", "after_sha256"):
            self.assertIn(k, rec, "回执缺 %s" % k)
        self.assertLess(len(json.dumps(rec)), 2000, "回执里塞了整份文件？")

    def test_rollback_refuses_when_file_changed_after_receipt(self):
        p, rel = self._mk("m.txt", b"g1\ng2\n")
        r = CP.apply(rel, "g2", "G2")
        p.write_bytes(b"g1\nSOMEONE-ELSE-EDITED\n")          # 文件被人动过
        try:
            CP.rollback(r["receipt_id"])
        except CP.CodePatchError as e:
            self.assertEqual("stale_content", e.code,
                             "文件被改过还照回滚 ⇒ 会覆盖别人的改动")
        else:
            self.fail("文件变了却仍然回滚成功")


class GateTests(_Base):
    """⑤ 门：apply 挂 filesystem_write；未授权不许写。"""

    def test_scope_is_attached_only_to_writing_ops(self):
        self.assertEqual([], list(policy.evaluate("code_patch", {}).scopes))
        self.assertEqual([], list(policy.evaluate("code_patch", {"op": "dry_run"}).scopes))
        self.assertIn("filesystem_write",
                      list(policy.evaluate("code_patch", {"op": "apply"}).scopes))
        # fail-closed：**没见过的 op** 也要挂（不许靠白名单漏放）
        self.assertIn("filesystem_write",
                      list(policy.evaluate("code_patch", {"op": "brand_new_op"}).scopes))

    def test_apply_through_the_gate_is_denied_without_grant_or_ok_with_it(self):
        """**环境无关**的判据：要么被门拒（缺 filesystem_write），要么真写成并留回执。

        在测试进程里"是不是可信主人会话"取决于环境，所以这里**两种结果都接受** ——
        但**必须恰好是其中一种**：既不能"没拒也没写"（静默空转），
        也不能"拒了却写了"（门形同虚设）。
        """
        p, rel = self._mk("n.txt", b"target\n")
        before = _sha(p)
        raw = api.run_task("code_patch", {"op": "apply", "path": rel,
                                          "find": "target", "replace": "TARGET"})
        # 🔴 2026-10-19（Owner 令「除三道护栏外都去掉」后这条第一次走成全绿分支）：
        #    外层信封有三种形状（gbt_result / result / 本体），原来只剥一种 ⇒ 绿分支读不到 op，
        #    报"静默空转"（假红）。这里统一剥到有 ok/status 的那层。
        body = raw.get("gbt_result") or raw.get("result") or raw
        if isinstance(body, dict) and isinstance(body.get("result"), dict) \
                and "op" not in body:
            body = body["result"]
        st = body.get("status")
        if st == "denied":
            self.assertIn("filesystem_write", list(body.get("missing") or []),
                          "被拒了但没说是缺哪个作用域")
            self.assertEqual(before, _sha(p), "**门说拒了，文件却被改了**")
        else:
            self.assertEqual("apply", body.get("op"), "既没拒也没写成（静默空转）")
            self.assertTrue(body.get("wrote"))
            self.assertNotEqual(before, _sha(p), "报告写了，文件却没变")
            self.assertTrue(body.get("receipt_id"), "写了却没有回执")

    def test_capability_is_registered_unsafe_and_param_required(self):
        from gbt_allinone.caps_registry import BENIGN_CAPS, required_params
        m = BENIGN_CAPS["code_patch"]
        self.assertFalse(m["safe"], "会写盘的能力位不许标 safe（面板/omni 会据此自动代调）")
        self.assertEqual(["path", "find", "replace"], required_params("code_patch"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
