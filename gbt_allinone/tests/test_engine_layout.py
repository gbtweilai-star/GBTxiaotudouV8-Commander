# -*- coding: utf-8 -*-
"""引擎布局契约：exe 与聊天模板在**两种布局**下都必须找得到。

血账（2026-11-06）：
  · `commander._engine_bin()` 原先只扫 `vendor/`，而打包版把 `llama-server.exe`
    放在 `tools/llama/` ⇒ 打包版报「没有 exe」起不来。于是 `tools/engine-up.py`
    被写成两套（开发仓委派 commander、产品自拼命令行），各自只在自家布局里对。
  · `commander.start()` 的聊天模板本来写死 `ROOT/vendor/llama/gbt-user-assistant.jinja`，
    打包版没这个文件 ⇒ 退回 GGUF 内置 Qwen 模板，普通对话里注入
    "You are Qwen, created by Alibaba Cloud."（问「你是谁」答「我叫 OpenClaw 人工智能9号」）。

判据只碰临时目录，不读真权重、不起进程。
"""
import tempfile
import unittest
from pathlib import Path

from ..tentacle import commander as C


class _Rooted:
    """把 commander 的 ROOT/WEIGHTS_DIR/ACTIVE_JSON 临时指到别处，退出时还原。"""

    def __init__(self, root: Path):
        self.root = root

    def __enter__(self):
        self._old = (C.ROOT, C.WEIGHTS_DIR, C.ACTIVE_JSON)
        C.ROOT = self.root
        C.WEIGHTS_DIR = self.root / "state" / "weights"
        C.ACTIVE_JSON = C.WEIGHTS_DIR / "ACTIVE.json"
        return self

    def __exit__(self, *exc):
        C.ROOT, C.WEIGHTS_DIR, C.ACTIVE_JSON = self._old
        return False


def _touch(p: Path, data: bytes = b"x"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


class TestEngineLayout(unittest.TestCase):
    def test_engine_found_in_vendor_and_tools_llama(self):
        """开发仓（vendor/llama）与打包版（tools/llama）两种布局都要命中。"""
        for rel, src_tag in (("vendor/llama", "vendor 扫描"), ("tools/llama", "tools/llama 扫描")):
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                _touch(root / rel / "llama-server.exe")
                with _Rooted(root):
                    got = C._engine_bin()
                self.assertTrue(got.get("ok"), "%s 布局没找到 exe：%s" % (rel, got))
                self.assertEqual(Path(got["path"]).name, "llama-server.exe")
                self.assertEqual(got.get("source"), src_tag)

    def test_engine_absent_says_both_places(self):
        """负对照：两处都没有时，reason 必须把两处都点出来，不许只说 vendor。"""
        with tempfile.TemporaryDirectory() as td:
            with _Rooted(Path(td)):
                got = C._engine_bin()
        self.assertFalse(got.get("ok"))
        self.assertIn("tools/llama", got.get("reason", ""))
        self.assertIn("vendor", got.get("reason", ""))

    def test_chat_template_follows_the_engine(self):
        """模板优先级：exe 旁边 > tools/llama > vendor/llama。"""
        for rel in ("tools/llama", "vendor/llama"):
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                exe = root / rel / "llama-server.exe"
                tpl = root / rel / "gbt-user-assistant.jinja"
                _touch(exe)
                _touch(tpl, b"{{ messages }}")
                if rel == "tools/llama":
                    _touch(root / "vendor/llama/gbt-user-assistant.jinja", b"old")
                else:
                    _touch(root / "tools/llama/gbt-user-assistant.jinja", b"old")
                with _Rooted(root):
                    eng = C._engine_bin()
                    got = C._chat_template(eng.get("path"))
                self.assertIsNotNone(got, "%s 布局没找到模板" % rel)
                self.assertEqual(got.read_bytes(), b"{{ messages }}",
                                 "应当优先取 exe 旁边那份，而不是另一处")

    def test_chat_template_absent_is_none_not_fake(self):
        """负对照：盘上没有就返回 None，不许编一个路径。"""
        with tempfile.TemporaryDirectory() as td:
            with _Rooted(Path(td)):
                self.assertIsNone(C._chat_template(None))

    def test_start_passes_chat_template_flag(self):
        """start() 必须把 --chat-template-file 带上（否则她会顶别人名字说话）。"""
        src = Path(C.__file__).read_text(encoding="utf-8")
        self.assertIn("--chat-template-file", src)
        self.assertIn("_chat_template(", src)


if __name__ == "__main__":
    unittest.main()
