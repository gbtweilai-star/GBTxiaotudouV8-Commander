# -*- coding: utf-8 -*-
"""safe_io 换行符对齐 · 契约测试（风哥 2026-09-17 批「源头防线先落地」）。

守的是《写入必须同换行符》：
    **写到目标文件之前，先读目标文件的换行符**，新增内容按它拼行 ——
    目标主流 CRLF -> 插入行自动 CRLF；主流 LF -> 插入行自动 LF。
    不许「写的时候不管，写完事后修」。

判据的判别性（《扫描器自证律》）：
    正对照 —— 走对齐入口（insert_lines_aligned）插行 -> 混行尾计数 0；
    负对照 —— 同一处插入走未对齐的 atomic_write_text（默认直写）-> 目标里出现少数派换行符。
    两组结果必须不同；负对照红不出来 = 这套判据没有判别性。

测试隔离：整套只在 tempfile 里造样本，绝不碰生产树。
    本文件按路径加载被测模块，不 import gbt_allinone 包 —— 避开包 import 期绑定生产 store。
"""
import hashlib
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PKG = _HERE.parent            # gbt_allinone/
_ROOT = _PKG.parent            # 项目根
SIO_PY = _PKG / "safe_io.py"

CRLF = "\r\n"
LF = "\n"


def _load(path, name):
    """按路径加载被测模块（与 tests/test_checkpoint.py 同路：避开包的重依赖）。"""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SIO = _load(SIO_PY, "safe_io_under_test")


def _counts(path):
    """byte 级换行符计数 —— 判据只认字节，不认 read_text()（它会把 CRLF 归一成 LF）。"""
    b = Path(path).read_bytes()
    crlf = b.count(b"\r\n")
    return {"bytes": len(b), "crlf": crlf, "bare_lf": b.count(b"\n") - crlf,
            "bare_cr": b.count(b"\r") - crlf}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class _Temp(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="gbt_safe_io_")
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def sample(self, name, raw):
        p = self.dir / name
        p.write_bytes(raw)
        return p


class TestDetectNewline(_Temp):
    def test_crlf_dominant(self):
        p = self.sample("crlf.md", b"# T\r\nline1\r\nline2\r\n")
        self.assertEqual(SIO.detect_newline(p), CRLF)

    def test_lf_dominant(self):
        p = self.sample("lf.md", b"# T\nline1\n")
        self.assertEqual(SIO.detect_newline(p), LF)

    def test_missing_uses_default(self):
        self.assertEqual(SIO.detect_newline(self.dir / "nope.md"), LF)
        self.assertEqual(SIO.detect_newline(self.dir / "nope.md", default=CRLF), CRLF)

    def test_empty_uses_default(self):
        p = self.sample("empty.md", b"")
        self.assertEqual(SIO.detect_newline(p, default=CRLF), CRLF)

    def test_mixed_reports_dominant_and_flag(self):
        p = self.sample("mixed.md", b"a\r\nb\r\nc\r\nd\ne\n")
        prof = SIO.newline_profile(p)
        self.assertTrue(prof["mixed"])
        self.assertEqual(prof["dominant"], CRLF)
        self.assertEqual((prof["crlf"], prof["lf"]), (3, 2))
        self.assertEqual(SIO.detect_newline(p), CRLF)

    def test_read_only(self):
        p = self.sample("ro.md", b"a\r\nb\n")
        before = _sha(p)
        SIO.newline_profile(p)
        SIO.detect_newline(p)
        self.assertEqual(_sha(p), before, "检测函数动了盘")


class TestAlignNewlines(unittest.TestCase):
    def test_all_forms_to_crlf(self):
        self.assertEqual(SIO.align_newlines("a\r\nb\nc\rd", CRLF), "a\r\nb\r\nc\r\nd")

    def test_all_forms_to_lf(self):
        self.assertEqual(SIO.align_newlines("a\r\nb\nc\rd", LF), "a\nb\nc\nd")

    def test_idempotent(self):
        self.assertEqual(SIO.align_newlines("a\r\nb\r\n", CRLF), "a\r\nb\r\n")

    def test_rejects_unknown_newline(self):
        with self.assertRaises(SIO.SafeIOError):
            SIO.align_newlines("a\n", "\n\r")


class TestAlignedWrite(_Temp):
    def test_crlf_target_stays_crlf(self):
        p = self.sample("doc.md", b"# T\r\nline1\r\n")
        SIO.atomic_write_text_aligned(p, "# T\nline1\nline2\n")
        c = _counts(p)
        self.assertEqual(c["bare_lf"], 0, "写后出现少数派换行符：%s" % c)
        self.assertEqual(c["crlf"], 3)

    def test_lf_target_stays_lf(self):
        p = self.sample("doc.md", b"# T\nline1\n")
        SIO.atomic_write_text_aligned(p, "# T\r\nline1\r\nline2\r\n")
        c = _counts(p)
        self.assertEqual(c["crlf"], 0, "写后出现少数派换行符：%s" % c)
        self.assertEqual(c["bare_lf"], 3)

    def test_new_file_uses_default_newline(self):
        p = self.dir / "brandnew.md"
        SIO.atomic_write_text_aligned(p, "a\nb\n", default_newline=CRLF)
        c = _counts(p)
        self.assertEqual((c["crlf"], c["bare_lf"]), (2, 0))

    def test_default_path_is_unchanged(self):
        """默认行为不动：align_to_existing 缺省 False —— 既有调用点仍是逐字节直写。

        这条是「默认行为不变」的正面证据：拿老签名、老语义写，混行尾照样漏（负对照的前提）。
        """
        p = self.sample("doc.md", b"# T\r\nline1\r\n")
        SIO.atomic_write_text(p, "# T\r\nline1\nline2\n")
        c = _counts(p)
        # 直写语义：原样落盘 —— 1 个 CRLF + 2 个裸 LF（老写法正是这样漏出少数派换行符的）
        self.assertEqual((c["crlf"], c["bare_lf"]), (1, 2))

    def test_optin_flag_aligns(self):
        p = self.sample("doc.md", b"# T\r\nline1\r\n")
        SIO.atomic_write_text(p, "# T\nline1\n", align_to_existing=True)
        self.assertEqual(_counts(p)["bare_lf"], 0)

    def test_locked_append_optin(self):
        p = self.sample("log.jsonl", b'{"a":1}\r\n')
        SIO.locked_append_text(p, '{"b":2}\n', align_to_existing=True)
        self.assertEqual(_counts(p)["bare_lf"], 0, "追加内容没跟目标对齐")


class TestInsertLinesAligned(_Temp):
    def test_crlf_file_insert_is_crlf(self):
        p = self.sample("bp.md", b"## A\r\n\r\n## B\r\n")
        before = p.read_bytes()
        r = SIO.insert_lines_aligned(p, "## A\r\n", "- O99: x\n- O100: y\n")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["newline"], CRLF)
        c = _counts(p)
        self.assertEqual(c["bare_lf"], 0, "插入后出现少数派换行符：%s" % c)
        self.assertEqual(c["crlf"], 5)
        self.assertIn(b"## A\r\n- O99: x\r\n- O100: y\r\n\r\n## B\r\n", p.read_bytes())
        self.assertTrue(p.read_bytes().startswith(before[:4]), "锚点前的字节被顺手改了")

    def test_lf_file_insert_is_lf(self):
        p = self.sample("bp.md", b"## A\n\n## B\n")
        r = SIO.insert_lines_aligned(p, "## A\n", "- O99: x\r\n")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["newline"], LF)
        c = _counts(p)
        self.assertEqual((c["crlf"], c["bare_lf"]), (0, 4))

    def test_position_before(self):
        p = self.sample("bp.md", b"## A\r\n## B\r\n")
        r = SIO.insert_lines_aligned(p, "## B\r\n", "## A2\r\n", position="before")
        self.assertTrue(r["ok"], r)
        self.assertEqual(p.read_bytes(), b"## A\r\n## A2\r\n## B\r\n")

    def test_anchor_zero_hits_does_not_write(self):
        p = self.sample("bp.md", b"## A\r\n")
        sha = _sha(p)
        r = SIO.insert_lines_aligned(p, "## NOTHERE\r\n", "x\n")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "anchor_count")
        self.assertEqual(r["count"], 0)
        self.assertFalse(r["written"])
        self.assertEqual(_sha(p), sha, "命中 0 却动了盘")

    def test_anchor_two_hits_does_not_write(self):
        p = self.sample("bp.md", b"## A\r\n## A\r\n")
        sha = _sha(p)
        r = SIO.insert_lines_aligned(p, "## A\r\n", "x\n")
        self.assertFalse(r["ok"])
        self.assertEqual(r["count"], 2)
        self.assertFalse(r["written"])
        self.assertEqual(_sha(p), sha, "命中 2 却动了盘")

    def test_mixed_file_keeps_history_lines_untouched(self):
        """混行尾文件：只对齐**插入物**，不把历史裸 LF 顺手归一化。

        反例代价（本项目实测）：PROJECT_BLUEPRINT.md 有 208 行历史裸 LF ——
        为了插 1 行而整文档归一化 = 一次改 200+ 行，超出任何单刀的原子边界。
        """
        p = self.sample("bp.md", b"## A\r\nhist1\nhist2\n## B\r\n")
        before = _counts(p)
        r = SIO.insert_lines_aligned(p, "## B\r\n", "new1\n")
        self.assertTrue(r["ok"], r)
        after = _counts(p)
        self.assertEqual(after["bare_lf"], before["bare_lf"], "历史裸 LF 被顺手改了")
        self.assertEqual(after["crlf"], before["crlf"] + 1)
        self.assertIn(b"## B\r\nnew1\r\n", p.read_bytes())

    def test_tie_uses_anchor_newline(self):
        """目标 CRLF 与裸 LF 打平（主流给不出）-> 用锚点自带的形态兜底。"""
        p = self.sample("bp.md", b"## A\r\n## B\r\nhist1\nhist2\n")
        prof = SIO.newline_profile(p)
        self.assertEqual(prof["dominant"], "", "样本没做成打平：%s" % prof)
        r = SIO.insert_lines_aligned(p, "## B\r\n", "new1\n")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["newline"], CRLF)
        self.assertIn(b"## B\r\nnew1\r\n", p.read_bytes())

    def test_tie_with_mismatched_anchor_refuses(self):
        """打平时锚点换了另一种换行形态 -> 命中 0 -> 不写盘（《锚点必须同换行符》在写入侧的执行）。"""
        p = self.sample("bp.md", b"## A\r\n## B\r\nhist1\nhist2\n")
        sha = _sha(p)
        r = SIO.insert_lines_aligned(p, "## B\n", "new1\r\n")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "anchor_count")
        self.assertEqual(r["count"], 0)
        self.assertEqual(_sha(p), sha, "锚点没命中却动了盘")

    def test_bad_position_rejected(self):
        p = self.sample("bp.md", b"## A\r\n")
        with self.assertRaises(SIO.SafeIOError):
            SIO.insert_lines_aligned(p, "## A\r\n", "x\n", position="around")


class TestInsertLinesAlignedBoundary(_Temp):
    """甲案（R105）· **插入点自动归位到行边界** —— 补丁脚本不许再靠"记得自带前导换行"。

    改前六型实测（`.scratch/_r105p_ilal_exact.py`，逐字节）：
      A `after` 锚点不带行尾 -> `甲新增\r\n\r\n乙\r\n`（左粘 **+ 多一个空行**）
      B `after` 同型 + addition 自带空行 -> 多两个空行
      C `after` 锚点自带行尾 -> 已是理想态
      D `before` 锚点**在行首** -> 已是理想态（原稿预判"必粘连"，实测推翻）
      E `before` 在行首但 addition **没尾换行** -> 右粘（文档口径：addition 需自带尾换行）
      F `before` 锚点**不在行首** -> `甲新增\r\n乙\r\n`（左粘）
    判别性（《扫描器自证律》）：同一输入旧实现必红、新实现必绿；红不出来 = 这组判据没牙。
    判据与文件主流匹配（O44）：CRLF 主流与 LF 主流各来一组，不拿错断言对象。
    """

    def test_mid_line_anchor_gets_its_own_line_after_and_before(self):
        """正（前导补齐）· `after` / `before` 对称同判 —— 锁规则 1。"""
        p = self.sample("after.md", "甲\r\n乙\r\n".encode("utf-8"))
        r = SIO.insert_lines_aligned(p, "甲", "新增\r\n")
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(p.read_bytes(), "甲\r\n新增\r\n乙\r\n".encode("utf-8"))

        q = self.sample("before.md", "甲乙\r\n".encode("utf-8"))
        r2 = SIO.insert_lines_aligned(q, "乙", "新增\r\n", position="before")
        self.assertTrue(r2.get("ok"), r2)
        self.assertEqual(q.read_bytes(), "甲\r\n新增\r\n乙\r\n".encode("utf-8"))

        m = self.sample("lf.md", "甲\n乙\n".encode("utf-8"))
        r3 = SIO.insert_lines_aligned(m, "甲", "新增\n")
        self.assertTrue(r3.get("ok"), r3)
        self.assertEqual(m.read_bytes(), "甲\n新增\n乙\n".encode("utf-8"))

    def test_anchor_with_own_newline_is_byte_identical(self):
        """防双换行 —— 锚点自带行尾（现有 11 处契约调用的形态）结果**逐字节不变**。锁规则 2。"""
        raw = "甲\r\n乙\r\n".encode("utf-8")
        p = self.sample("c.md", raw)
        legacy = raw.decode("utf-8").replace("甲\r\n", "甲\r\n新增\r\n", 1).encode("utf-8")
        r = SIO.insert_lines_aligned(p, "甲\r\n", "新增\r\n")
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(p.read_bytes(), legacy, "锚点自带行尾却与改前不一致")
        self.assertNotIn(b"\r\n\r\n", p.read_bytes(), "多灌了一个空行")

    def test_addition_tail_newline_never_doubles(self):
        """尾换行 —— 结果里不得出现连续两个行尾。锁规则 3。"""
        p = self.sample("t.md", "甲\r\n乙\r\n".encode("utf-8"))
        r = SIO.insert_lines_aligned(p, "甲", "新增\r\n")
        self.assertTrue(r.get("ok"), r)
        out = p.read_bytes()
        self.assertNotIn(b"\r\n\r\n", out, "插入物末行 + 原锚点行尾 = 连着两个行尾")
        self.assertEqual(out, "甲\r\n新增\r\n乙\r\n".encode("utf-8"))

    def test_discriminating_pair_old_glues_new_cleans(self):
        """判别性负对照 —— **旧实现必红、新实现必绿**（红不出来说明这条没判别性）。

        旧实现 = 甲案前的拼法：`body = anchor + addition`（`before` 则 `addition + anchor`），
        直接交给 `edit_text_once`，**不判定插入点是否在行边界**。
        """
        raw = "甲\r\n乙\r\n".encode("utf-8")
        glue = "甲新增".encode("utf-8")
        old = self.sample("old.md", raw)
        new = self.sample("new.md", raw)
        SIO.atomic_write_bytes(old, raw.decode("utf-8").replace("甲", "甲新增\r\n", 1).encode("utf-8"))
        r = SIO.insert_lines_aligned(new, "甲", "新增\r\n")
        self.assertTrue(r.get("ok"), r)
        self.assertIn(glue, old.read_bytes(), "旧实现没红 -- 这条判据没判别性")
        self.assertNotIn(glue, new.read_bytes(), "新实现还在粘连")
        self.assertNotEqual(old.read_bytes(), new.read_bytes(), "正负对照必须不同")

    def test_guard_empty_addition_and_anchor_counts(self):
        """守门员（并入规则 5）—— 空 addition **内容零变化**；命中 0 / 2 **不写盘**。

        实测口径（R105）：空 addition 现行实现是「原样重写一次」（`written=True`，内容
        逐字节不变），**不是**「拒绝写盘」—— 本刀**不新增守卫**（那会改默认行为），
        只钉住"零变化"。
        """
        p = self.sample("g.md", "甲\r\n乙\r\n".encode("utf-8"))
        before = _sha(p)
        r = SIO.insert_lines_aligned(p, "甲", "")
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(_sha(p), before, "空 addition 竟然改动了内容")

        z = self.sample("z.md", "甲\r\n乙\r\n".encode("utf-8"))
        zb = _sha(z)
        rz = SIO.insert_lines_aligned(z, "没这个锚点\r\n", "x\r\n")
        self.assertFalse(rz.get("ok"))
        self.assertEqual(rz.get("reason"), "anchor_count")
        self.assertEqual(_sha(z), zb)

        d = self.sample("d.md", "甲\r\n甲\r\n".encode("utf-8"))
        db = _sha(d)
        rd = SIO.insert_lines_aligned(d, "甲\r\n", "x\r\n")
        self.assertFalse(rd.get("ok"))
        self.assertEqual(rd.get("count"), 2)
        self.assertEqual(_sha(d), db)

class TestEditTextOnce(_Temp):
    def test_replace_crlf(self):
        p = self.sample("readme.md", b"old line\r\nother\r\n")
        r = SIO.edit_text_once(p, "old line\n", "new line\n")
        self.assertTrue(r["ok"], r)
        self.assertEqual(p.read_bytes(), b"new line\r\nother\r\n")

    def test_missing_anchor_does_not_write(self):
        p = self.sample("readme.md", b"old line\r\n")
        sha = _sha(p)
        r = SIO.edit_text_once(p, "nope\n", "x\n")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "anchor_count")
        self.assertEqual(_sha(p), sha)

    def test_expected_two(self):
        p = self.sample("readme.md", b"a\nb\na\n")
        r = SIO.edit_text_once(p, "a\n", "A\n", expected=2)
        self.assertTrue(r["ok"], r)
        self.assertEqual(p.read_bytes(), b"A\nb\nA\n")

    def test_missing_target(self):
        r = SIO.edit_text_once(self.dir / "nope.md", "a\n", "b\n")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "missing_target")


class TestEditTextOnceNewlineOverride(_Temp):
    """O37 · 显式 newline 覆盖（风哥 2026-09-17 批「加，默认行为不动」）。

    实证形态 = 目标文件**区段混行尾**：主流 CRLF，但命中行落在**纯 LF 区段**
    （gbt_allinone/tests/test_framework.py 实测：主流 743 CRLF，911-1110 段 200 行纯 LF）。
    判别信号 = **CRLF 增量**：显式覆盖 0（不往纯 LF 区段灌 CRLF）/ 默认 +1（灌了）。
    """

    MIXED = (b"## head\r\n"
             b"\r\n"
             b"para one\r\n"
             b"para two\r\n"
             b"\r\n"
             b"LF-SEC-A\n"
             b"LF-SEC-B\n"
             b"LF-SEC-C\n")

    def test_explicit_lf_keeps_section_pure(self):
        """单行锚点（不带尾换行）落在纯 LF 区段：显式 LF -> CRLF 增量 0。"""
        p = self.sample("mixed.md", self.MIXED)
        before = _counts(p)
        r = SIO.edit_text_once(p, "LF-SEC-A", "LF-SEC-A\nLF-SEC-A2", newline=LF)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["newline"], LF)
        self.assertEqual(r["newline_source"], "explicit")
        after = _counts(p)
        self.assertEqual(after["crlf"], before["crlf"], "显式覆盖后 CRLF 计数变了")
        self.assertEqual(after["bare_lf"] - before["bare_lf"], 1, "新增那一行没按 LF 拼")

    def test_default_is_dominant_and_unchanged(self):
        """默认行为不动：不给 newline -> 仍按主流拼 -> 往纯 LF 区段灌 1 个 CRLF（现状语义，保留）。"""
        p = self.sample("mixed.md", self.MIXED)
        before = _counts(p)
        r = SIO.edit_text_once(p, "LF-SEC-A", "LF-SEC-A\nLF-SEC-A2")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["newline"], CRLF)
        self.assertEqual(r["newline_source"], "dominant")
        after = _counts(p)
        self.assertEqual(after["crlf"] - before["crlf"], 1)
        self.assertEqual(after["bare_lf"], before["bare_lf"])

    def test_discriminating_pair(self):
        """《扫描器自证律》：同一样本、同一锚点，显式 vs 默认 -> 结果必须不同。"""
        a = self.sample("a.md", self.MIXED)
        b = self.sample("b.md", self.MIXED)
        ra = SIO.edit_text_once(a, "LF-SEC-B", "LF-SEC-B2\nX", newline=LF)
        rb = SIO.edit_text_once(b, "LF-SEC-B", "LF-SEC-B2\nX")
        self.assertTrue(ra["ok"], ra)
        self.assertTrue(rb["ok"], rb)
        self.assertNotEqual(_counts(a), _counts(b), "显式与默认结果相同 —— 判据没有判别性")
        self.assertNotEqual(_sha(a), _sha(b))

    def test_explicit_keeps_everything_else_byte_identical(self):
        p = self.sample("mixed.md", self.MIXED)
        before = p.read_bytes()
        r = SIO.edit_text_once(p, "LF-SEC-C", "LF-SEC-C-REPLACED", newline=LF)
        self.assertTrue(r["ok"], r)
        self.assertEqual(p.read_bytes().replace(b"LF-SEC-C-REPLACED", b"LF-SEC-C"), before)

    def test_rejects_unknown_newline_and_does_not_write(self):
        p = self.sample("mixed.md", self.MIXED)
        sha = _sha(p)
        with self.assertRaises(SIO.SafeIOError):
            SIO.edit_text_once(p, "LF-SEC-A", "x", newline="\r")
        self.assertEqual(_sha(p), sha, "非法 newline 竟然写盘了")

    def test_explicit_crlf_on_pure_crlf_file(self):
        p = self.sample("readme.md", b"old line\r\nother\r\n")
        r = SIO.edit_text_once(p, "old line\n", "new line\n", newline=CRLF)
        self.assertTrue(r["ok"], r)
        self.assertEqual(p.read_bytes(), b"new line\r\nother\r\n")


class TestDiscriminatingControl(_Temp):
    def test_aligned_and_unaligned_differ(self):
        """《扫描器自证律》：两组结果必须不同，否则这套判据没有判别性。"""
        raw = b"## A\r\n\r\n## B\r\n"
        add = "- added\n"
        good = self.sample("good.md", raw)
        bad = self.sample("bad.md", raw)

        r = SIO.insert_lines_aligned(good, "## A\r\n", add)
        self.assertTrue(r["ok"], r)

        # 负对照：同一次插入，走未对齐的默认直写（老写法的形态）
        SIO.atomic_write_text(
            bad, bad.read_bytes().decode("utf-8").replace("## A\r\n", "## A\r\n" + add))

        gc, bc = _counts(good), _counts(bad)
        self.assertEqual(gc["bare_lf"], 0, "正对照没全对齐：%s" % gc)
        self.assertEqual(
            bc["bare_lf"], 1, "负对照没红 —— 默认直写竟然也全 CRLF，判据无判别性：%s" % bc)
        self.assertNotEqual(gc, bc, "正负对照必须不同")


class TestCookieBomNulPolicy(_Temp):
    """R98/R99/R100 取证转契约（风哥 2026-09-18 拍「三条实证全补」）。

    判别性要求：**断言 reason，不断言 type** —— BOM + bogus 在 bytes 层因 cookie 冲突红、
    在 str 层因 U+FEFF 红，同为 SyntaxError 但成因完全不同；只断言类型的用例两条路径都过，
    什么也没证明（风哥 2026-09-18 点出的方法论雷）。
    """

    BOGUS = b"# -*- coding: bogus-9 -*-\nx = 1\n"
    CJK = "\u4e2d"
    BOM = b"\xef\xbb\xbf"

    def test_bogus_cookie_is_rejected_with_reason(self):
        p = self.dir / "bogus.py"
        with self.assertRaises(SIO.WriteRejected) as ctx:
            SIO.atomic_write_bytes(p, self.BOGUS, validator=SIO._py_syntax_validator)
        self.assertIn("unknown encoding: bogus-9", ctx.exception.reason)
        self.assertFalse(p.exists())

    def test_bom_with_bogus_cookie_reason_names_the_conflict(self):
        """这条能区分字节层与 str 层两种成因：bytes 层理由含 `with BOM`，str 层是 U+FEFF。"""
        p = self.dir / "bom_bogus.py"
        with self.assertRaises(SIO.WriteRejected) as ctx:
            SIO.atomic_write_bytes(p, self.BOM + self.BOGUS, validator=SIO._py_syntax_validator)
        self.assertIn("with BOM", ctx.exception.reason)
        self.assertFalse(p.exists())

    def test_str_path_false_greens_on_bogus_cookie(self):
        """判别性：同内容 str 层放行 -> 差异来自 bytes 路径，不是文件本身坏。"""
        compile(self.BOGUS.decode("utf-8"), "x.py", "exec")
        with self.assertRaises(SIO.WriteRejected):
            SIO.atomic_write_bytes(self.dir / "b.py", self.BOGUS, validator=SIO._py_syntax_validator)

    def test_bom_python_passes_bytes_and_false_reds_str(self):
        """本仓实测 10 个 .py 是 BOM 开头：bytes 必须放行，str 必须假红，落盘零改动。"""
        bom = self.BOM + ('# -*- coding: utf-8 -*-\ns = "' + self.CJK + '"\n').encode("utf-8")
        with self.assertRaises(SyntaxError):
            compile(bom.decode("utf-8"), "x.py", "exec")
        p = self.dir / "bom.py"
        SIO.atomic_write_bytes(p, bom, validator=SIO._py_syntax_validator)
        self.assertEqual(p.read_bytes(), bom)

    def test_valid_utf8_cookie_with_cjk_passes(self):
        good = ('# -*- coding: utf-8 -*-\ns = "' + self.CJK + '"\n').encode("utf-8")
        p = self.dir / "good.py"
        SIO.atomic_write_bytes(p, good, validator=SIO._py_syntax_validator)
        self.assertEqual(p.read_bytes(), good)

    def test_unicode_decode_error_is_not_reachable_via_compile(self):
        """风哥 2026-09-18 撤回：decode 失败被 tokenizer 包成 SyntaxError，不是 UnicodeDecodeError。"""
        raw = b's = "caf\xe9"\n'
        with self.assertRaises(SyntaxError):
            compile(raw, "x.py", "exec")
        with self.assertRaises(SIO.WriteRejected) as ctx:
            SIO.atomic_write_bytes(self.dir / "bad.py", raw, validator=SIO._py_syntax_validator)
        self.assertIn("SyntaxError", ctx.exception.reason)
        self.assertNotIn("UnicodeDecodeError", ctx.exception.reason)

    def test_nul_reason_is_valueerror_not_syntaxerror(self):
        with self.assertRaises(SIO.WriteRejected) as ctx:
            SIO.atomic_write_bytes(self.dir / "n.py", b"x = 1\x00\n",
                                   validator=SIO._py_syntax_validator)
        self.assertIn("ValueError", ctx.exception.reason)
        self.assertNotIn("SyntaxError", ctx.exception.reason)

    def test_unexpected_exception_becomes_validator_unexpected(self):
        """兜底分支：compile 抛非两型异常 -> 必须变成 WriteRejected，不许漏到写入中途。"""
        from unittest import mock
        with mock.patch("builtins.compile", side_effect=LookupError("boom")):
            with self.assertRaises(SIO.WriteRejected) as ctx:
                SIO._py_syntax_validator(b"x = 1\n", "x.py")
        self.assertIn("validator_unexpected: LookupError", ctx.exception.reason)


class TestRealFilesReadOnly(unittest.TestCase):
    """只读交叉验证：helper 判定必须与 byte 级复算逐一致（全程不写盘）。"""

    CASES = ["PROJECT_BLUEPRINT.md", "HEARTBEAT.md", "CHARTER.md", "gbt_allinone/safe_io.py"]

    def test_detect_matches_byte_recount(self):
        checked = 0
        for rel in self.CASES:
            p = _ROOT / rel
            if not p.exists():
                continue
            checked += 1
            b = p.read_bytes()
            crlf = b.count(b"\r\n")
            lf = b.count(b"\n") - crlf
            want = CRLF if crlf > lf else (LF if lf > crlf else None)
            self.assertEqual(SIO.detect_newline(p, default=None), want,
                             "%s 判定与 byte 级复算不一致" % rel)
        self.assertGreater(checked, 0, "一个样本都没读到 —— 判据没跑（《空不等于不存在律》）")


def _undo_exact(text_after, fragment):
    """还原判据的唯一合法写法：把片段**精确整体**替换掉，不猜切片边界。"""
    if fragment not in text_after:
        raise AssertionError("片段不在文中 -- 判据没得还原，不许退化成切片猜")
    return text_after.replace(fragment, "", 1)


def _undo_by_boundary_guess(text_after, fragment):
    """R94 落地/复验脚本的写法：按「片段不含尾部空行」切边界 -- 猜错就还原不出来。"""
    body = fragment[:-2]
    if body not in text_after:
        raise AssertionError("片段不在文中")
    return text_after.replace(body, "", 1)


class TestByteModeReadContract(_Temp):
    """机制一：**文件读取一律 byte 模式**（契约用例 · 风哥 2026-09-17 批，写进本文件）。

    实证（R94 · O51 第 9 次）：判据用**文本模式**读 CRLF 文件 -> 通用换行把 ``\r\n`` 折叠成 ``\n`` -> ``## R`` 段头数成 0，拿**假数字**判红。
    契约：读盘一律 ``Path.read_bytes()``（会把 CRLF 归一掉的文本模式读法一律算违规）。
    判别性（《扫描器自证律》）：同一份 CRLF 样本 -- byte 模式读到 4 个 CRLF，
    文本模式读到 0 个；两组必须不同，负对照红不出来 = 这条契约是空壳。
    """

    RAW = "# 标题\r\n\r\n正文一\r\n正文二\r\n"

    def test_byte_mode_keeps_crlf(self):
        p = self.sample("crlf.md", self.RAW.encode("utf-8"))
        raw = p.read_bytes()
        self.assertEqual(raw.decode("utf-8"), self.RAW)
        self.assertEqual(raw.count(b"\r\n"), 4, "byte 模式必须原样保留 CRLF")

    def test_discriminating_pair_text_mode_collapses(self):
        p = self.sample("crlf.md", self.RAW.encode("utf-8"))
        via_bytes = p.read_bytes().decode("utf-8")
        with open(p, "r", encoding="utf-8") as fh:
            via_text = fh.read()
        self.assertNotEqual(via_bytes, via_text, "正负对照必须不同")
        self.assertEqual(via_text.count("\r\n"), 0, "文本模式必须把 CRLF 折叠掉")
        self.assertEqual(via_text.count("\n"), 4, "折叠后只剩 4 个裸 LF")


class TestRoundtripJudgeExactReplacement(_Temp):
    """机制二：**还原判据必须用精确串替换，禁止切片边界猜**（写进 tests/）。

    实证（R94 · O51 第 11 / 12 次）：撤销 ``insert_lines_aligned(..., position="before")``
    时按「先删尾部换行、再删整块」两步切片 -> 多去一个换行 -> 写入本身正确却判
    ``GO FAILED rc=1``；复验脚本又在**已含尾部空行**的切片上补一个 CRLF -> 假红。
    两次都不是文件错，是判据在猜边界。
    判别性（《扫描器自证律》）：精确串替换 -> 逐字节等于原文；按边界猜 -> 还原不出来。
    """

    BEFORE = "# 头\r\n\r\n甲\r\n乙\r\n"
    FRAGMENT = "新增一行\r\n\r\n"

    def _after_insert(self):
        p = self.sample("rt.md", self.BEFORE.encode("utf-8"))
        r = SIO.insert_lines_aligned(p, anchor="甲", addition=self.FRAGMENT,
                                     position="before")
        self.assertTrue(r.get("ok"), r)
        return p.read_bytes().decode("utf-8")

    def test_exact_replacement_roundtrips_byte_identical(self):
        self.assertEqual(_undo_exact(self._after_insert(), self.FRAGMENT), self.BEFORE)

    def test_discriminating_pair_boundary_guess_fails(self):
        after = self._after_insert()
        self.assertNotEqual(_undo_by_boundary_guess(after, self.FRAGMENT), self.BEFORE,
                            "边界猜必须还原不出来 -- 红不出来说明这条判据没判别性")

class TestAtomicWriteFailFast(_Temp):
    """R97 gai fa 1 -- write-side fail-fast (`WriteRejected`).

    判据不许挂在旧数据上：样本全部现造在 tempfile 里。
    判别性（《扫描器自证律》）：同一个坏内容，带 validator -> 红；不带 -> 照写。
    守门员：`validator 跑完目标目录零新增文件` —— 零落盘的 `compile()` 下它自动成立，
    但它是这条规矩的看门人，不能省（`py_compile` 会让它假绿）。
    """

    GOOD = b"def scan():\n    return 1\n"
    BAD = b"def scan(:\n    return 1\n"

    def test_valid_python_is_written(self):
        p = self.dir / "mod.py"
        SIO.atomic_write_bytes(p, self.GOOD, validator=SIO._py_syntax_validator)
        self.assertEqual(p.read_bytes(), self.GOOD)

    def test_default_signature_is_unchanged(self):
        """不带 validator -> 默认行为不动（坏内容照写）。"""
        p = self.dir / "raw.py"
        SIO.atomic_write_bytes(p, self.BAD)
        self.assertEqual(p.read_bytes(), self.BAD)

    def test_broken_python_is_rejected_and_target_untouched(self):
        p = self.sample("mod.py", self.GOOD)
        before = _sha(p)
        with self.assertRaises(SIO.WriteRejected):
            SIO.atomic_write_bytes(p, self.BAD, validator=SIO._py_syntax_validator)
        self.assertEqual(_sha(p), before)
        self.assertEqual(p.read_bytes(), self.GOOD)

    def test_rejected_write_leaves_no_tmp_and_no_new_files(self):
        p = self.sample("mod.py", self.GOOD)
        with self.assertRaises(SIO.WriteRejected):
            SIO.atomic_write_bytes(p, self.BAD, validator=SIO._py_syntax_validator)
        self.assertEqual(sorted(q.name for q in self.dir.iterdir()), ["mod.py"])

    def test_validator_receives_bytes_not_str(self):
        seen = {}

        def spy(data, path):
            seen["type"] = type(data)
            seen["path"] = path

        p = self.dir / "x.py"
        SIO.atomic_write_bytes(p, b"a = 1\n", validator=spy)
        self.assertIs(seen["type"], bytes)
        self.assertEqual(seen["path"], str(p.resolve()))

    def test_bytes_layer_avoids_two_false_reds(self):
        """判别性成对（R97 实测更正）：str 层校验会假红两次，bytes 层必须过。

        更正：`compile(str)` 带 coding cookie 在 CPython 3.10 **不抛** —— 风哥原判据在
        本机不成立（实测 `str with utf-8 cookie: OK`）。真会假红的是「先自己 decode 再 compile」：
          · latin-1 声明且含 0xE9 字节 -> UnicodeDecodeError
          · UTF-8 BOM 开头 -> SyntaxError: invalid non-printable character U+FEFF
        决策不变（validator 必须收 bytes），理由按实测改。
        """
        latin = ('# -*- coding: latin-1 -*-\nname = "caf\u00e9"\n').encode("latin-1")
        with self.assertRaises(UnicodeDecodeError):
            compile(latin.decode("utf-8"), "x.py", "exec")
        SIO.atomic_write_bytes(self.dir / "latin.py", latin,
                               validator=SIO._py_syntax_validator)
        bom = b"\xef\xbb\xbfx = 1\n"
        with self.assertRaises(SyntaxError):
            compile(bom.decode("utf-8"), "x.py", "exec")
        SIO.atomic_write_bytes(self.dir / "bom.py", bom,
                               validator=SIO._py_syntax_validator)


    def test_edit_text_once_rejects_broken_python(self):
        p = self.sample("m2.py", self.GOOD)
        before = _sha(p)
        with self.assertRaises(SIO.WriteRejected):
            SIO.edit_text_once(p, "return 1", "return (")
        self.assertEqual(_sha(p), before)

    def test_multistep_py_insert_intermediate_state_is_rejected(self):
        """守门员：往 .py 分步插入时中间态语法坏 -> 必须抛，不许静默写盘，不许放宽 validator。"""
        p = self.sample("m3.py", self.GOOD)
        before = _sha(p)
        with self.assertRaises(SIO.WriteRejected):
            SIO.insert_lines_aligned(p, "def scan():\n", "    try:\n", position="after")
        self.assertEqual(_sha(p), before)

    def test_non_python_target_skips_validator(self):
        p = self.sample("doc.md", b"# T\n\n## A\n")
        r = SIO.edit_text_once(p, "## A\n", "## A\n    (\n")
        self.assertTrue(r.get("ok"), r)

    def test_nul_bytes_are_rejected_not_crashed(self):
        """R97 验收点：NUL 字节抛的是 ValueError —— 只抓 SyntaxError 会让它逃出去。"""
        p = self.dir / "nul.py"
        with self.assertRaises(SIO.WriteRejected) as ctx:
            SIO.atomic_write_bytes(p, b"x = 1\x00\n", validator=SIO._py_syntax_validator)
        self.assertIn("ValueError", ctx.exception.reason)
        self.assertFalse(p.exists())

    def test_reject_path_creates_zero_files(self):
        """R97 时序升级：validator 跑在 mkstemp 之前 -> 拒绝路径结构上不产生文件。"""
        p = self.dir / "nul.py"
        with self.assertRaises(SIO.WriteRejected) as ctx:
            SIO.atomic_write_bytes(p, b"a\x00b\n", validator=SIO._py_syntax_validator)
        self.assertEqual(list(self.dir.iterdir()), [])
        self.assertEqual(ctx.exception.tmp, "")

    def test_existing_target_mode_is_preserved(self):
        """R97 验收点：os.replace 前回填目标原 mode，不许静默改权限。"""
        p = self.sample("m5.py", self.GOOD)
        if os.name != "nt":
            os.chmod(p, 0o644)
        before_mode = os.stat(p).st_mode & 0o777
        SIO.atomic_write_bytes(p, self.GOOD + b"# x\n",
                               validator=SIO._py_syntax_validator)
        self.assertEqual(os.stat(p).st_mode & 0o777, before_mode)

    def test_validator_exception_types_are_caught(self):
        """三类都变 WriteRejected；其余异常原样上抛（不许吞）。"""
        p = self.dir / "x.py"

        def make(exc):
            def v(_data, _path, _e=exc):
                raise _e
            return v

        for exc in (SyntaxError("bad"), ValueError("nul"),
                    UnicodeDecodeError("utf-8", b"\xff", 0, 1, "boom")):
            with self.assertRaises(SIO.WriteRejected):
                SIO.atomic_write_bytes(p, b"x = 1\n", validator=make(exc))

        def boom(_data, _path):
            raise RuntimeError("not mine to swallow")

        with self.assertRaises(RuntimeError):
            SIO.atomic_write_bytes(p, b"x = 1\n", validator=boom)
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_crlf_python_is_not_a_false_red(self):
        """O44 同族：本仓 .py 主流是 CRLF —— validator 必须吃 CRLF，且一个字节都不改。

        实测口径：tokenizer 在解析前做通用换行归一，所以 CRLF / 光杆 CR / 混合行尾
        都能过；validator 只读不改，落盘仍是原字节。
        """
        good = b"def f():\r\n    return 1\r\n"
        p = self.dir / "crlf.py"
        SIO.atomic_write_bytes(p, good, validator=SIO._py_syntax_validator)
        self.assertEqual(p.read_bytes(), good)
        self.assertEqual(_counts(p)["crlf"], 2)
        self.assertEqual(_counts(p)["bare_lf"], 0)
        bad = b"def f(:\r\n    return 1\r\n"
        with self.assertRaises(SIO.WriteRejected):
            SIO.atomic_write_bytes(p, bad, validator=SIO._py_syntax_validator)
        self.assertEqual(p.read_bytes(), good)
        self.assertEqual(sorted(q.name for q in self.dir.iterdir()), ["crlf.py"])

    def test_replay_first_case_keeps_original(self):
        """复现首例：坏内容重放 -> 盘上仍是改前 sha256。"""
        p = self.sample("cross_scan.py", self.GOOD)
        before = _sha(p)
        with self.assertRaises(SIO.WriteRejected):
            SIO.atomic_write_bytes(p, self.BAD, validator=SIO._py_syntax_validator)
        self.assertEqual(_sha(p), before)
        self.assertEqual(p.read_bytes(), self.GOOD)

    def test_anchor_count_still_returns_instead_of_raising(self):
        """原返回契约不动：命中数 != expected 仍返回 ok=False，不抛。"""
        p = self.sample("m4.py", self.GOOD)
        before = _sha(p)
        r = SIO.edit_text_once(p, "NOTHERE", "x")
        self.assertFalse(r.get("ok"))
        self.assertEqual(r.get("reason"), "anchor_count")
        self.assertEqual(_sha(p), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
