"""omni_fs（文件操作域）验收。

重点不是"能不能复制"，而是**几条不许破的纪律**：
  ① 回收站失败时**文件必须还在**（绝不许偷偷降级成永久删）—— 这是本文件最重要的一条
  ② 默认不覆盖
  ③ 干跑一个字节都不许动
  ④ 失败必须带原因，不许抛裸异常、不许假装成功

跑法：
    $env:GBT_STORE_DIR="$env:TEMP\\gbt_test_store"; py -3.14 -m pytest gbt_allinone/tests/test_omni_fs.py -q
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_TENT = Path(__file__).resolve().parents[1] / "tentacle"


def _load():
    if str(_TENT) not in sys.path:
        sys.path.insert(0, str(_TENT))
    spec = importlib.util.spec_from_file_location("_omni_fs_test", str(_TENT / "omni_fs.py"))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def fs(tmp_path):
    mod = _load()
    return mod, mod.OmniFsMixin(), tmp_path


# ── 看 ────────────────────────────────────────────────────────────────────

def test_list_dir(fs):
    _, t, d = fs
    (d / "a.txt").write_text("A", encoding="utf-8")
    (d / "sub").mkdir()
    got = t.file_list(str(d))
    assert got["ok"] is True and got["count"] == 2
    names = {e["name"] for e in got["entries"]}
    assert names == {"a.txt", "sub"}


def test_list_dir_recursive_and_hidden(fs):
    _, t, d = fs
    (d / "sub").mkdir()
    (d / "sub" / "deep.txt").write_text("x", encoding="utf-8")
    (d / ".hidden").write_text("h", encoding="utf-8")
    assert t.file_list(str(d))["count"] == 1, "默认不列隐藏项"
    assert t.file_list(str(d), hidden=True)["count"] == 2
    assert t.file_list(str(d), recursive=True)["count"] == 2, "递归要能看到 sub/deep.txt"


def test_list_missing_path_reports(fs):
    _, t, d = fs
    got = t.file_list(str(d / "nope"))
    assert got["ok"] is False and "不存在" in got["error"]


def test_file_info_and_exists(fs):
    _, t, d = fs
    f = d / "x.bin"
    f.write_bytes(b"12345")
    info = t.file_info(str(f))
    assert info["ok"] and info["bytes"] == 5 and info["file"] and not info["dir"]
    assert t.path_exists(str(f))["exists"] is True
    assert t.path_exists(str(d / "no"))["exists"] is False
    assert t.file_info(str(d / "no"))["ok"] is False


# ── 改（写盘）────────────────────────────────────────────────────────────

def test_dir_create_and_refuse_existing(fs):
    _, t, d = fs
    got = t.dir_create(str(d / "new" / "deep"))
    assert got["ok"] is True and (d / "new" / "deep").is_dir()
    again = t.dir_create(str(d / "new"))
    assert again["ok"] is False and "已经存在" in again["error"]


def test_copy_and_overwrite_protection(fs):
    _, t, d = fs
    src, dst = d / "s.txt", d / "t.txt"
    src.write_text("hello", encoding="utf-8")
    dst.write_text("原有内容", encoding="utf-8")

    refused = t.file_copy(str(src), str(dst))
    assert refused["ok"] is False and "不静默覆盖" in refused["error"]
    assert dst.read_text(encoding="utf-8") == "原有内容", "被拒之后目标必须一个字没变"

    ok = t.file_copy(str(src), str(dst), overwrite=True)
    assert ok["ok"] is True and dst.read_text(encoding="utf-8") == "hello"


def test_copy_missing_source(fs):
    _, t, d = fs
    got = t.file_copy(str(d / "no.txt"), str(d / "y.txt"))
    assert got["ok"] is False and "源不存在" in got["error"]


def test_move_and_rename(fs):
    _, t, d = fs
    f = d / "a.txt"
    f.write_text("v", encoding="utf-8")
    assert t.file_move(str(f), str(d / "b.txt"))["ok"] is True
    assert not f.exists() and (d / "b.txt").exists()

    got = t.file_rename(str(d / "b.txt"), "c.txt")
    assert got["ok"] is True and (d / "c.txt").exists() and not (d / "b.txt").exists()


def test_rename_rejects_empty_and_illegal(fs):
    _, t, d = fs
    f = d / "a.txt"
    f.write_text("v", encoding="utf-8")
    assert t.file_rename(str(f), "  ")["ok"] is False
    assert "不猜" in t.file_rename(str(f), "")["error"]
    bad = t.file_rename(str(f), "x/y.txt")
    assert bad["ok"] is False and "非法字符" in bad["error"]
    assert f.exists(), "被拒之后原文件必须还在"


# ── 删除：本文件的核心安全断言 ───────────────────────────────────────────

def test_delete_dry_run_touches_nothing(fs):
    _, t, d = fs
    f = d / "keep.txt"
    f.write_text("v", encoding="utf-8")
    got = t.file_delete(str(f), dry_run=True)
    assert got["ok"] is True and got["dry_run"] is True
    assert f.exists(), "干跑必须一个字节都不动"


def test_delete_permanent_is_explicit_and_flagged(fs):
    _, t, d = fs
    f = d / "gone.txt"
    f.write_text("v", encoding="utf-8")
    got = t.file_delete(str(f), permanent=True)
    assert got["ok"] is True and not f.exists()
    assert got["permanent"] is True, "永久删必须自己标明，不许含糊"
    assert "捞不回来" in got["note"]


def test_delete_never_silently_downgrades_to_permanent(fs):
    """🔴 本域最重要的一条：回收站不成 ⇒ **文件必须原封不动**。

    如果哪天有人把"送回收站失败"改成"那就直接删了吧"，这条会当场报红。
    """
    _, t, d = fs
    f = d / "safe.txt"
    f.write_text("v", encoding="utf-8")
    got = t.file_delete(str(f))          # 默认：送回收站
    assert "permanent" in got
    assert got["permanent"] is False, "默认路径绝不许是永久删"
    if got["ok"]:
        assert not f.exists(), "报成功就该真没了"
    else:
        assert f.exists(), "回收站失败却把文件删了 —— 这就是偷偷降级，绝对不允许"
        assert got["error"] and "回收站" in got["error"]


def test_delete_missing_reports(fs):
    _, t, d = fs
    got = t.file_delete(str(d / "no.txt"))
    assert got["ok"] is False and "不存在" in got["error"]


# ── 读写文本 ─────────────────────────────────────────────────────────────

def test_write_read_roundtrip_and_append(fs):
    _, t, d = fs
    f = d / "t.txt"
    assert t.file_write_text(str(f), "第一行\n")["ok"] is True
    assert t.file_write_text(str(f), "第二行\n", append=True)["ok"] is True
    got = t.file_read_text(str(f))
    assert got["ok"] is True and got["text"] == "第一行\n第二行\n"
    assert got["truncated"] is False


def test_write_creates_parent_dirs(fs):
    _, t, d = fs
    f = d / "x" / "y" / "z.txt"
    assert t.file_write_text(str(f), "v")["ok"] is True
    assert f.read_text(encoding="utf-8") == "v"


def test_write_dry_run_reports_without_touching(fs):
    _, t, d = fs
    f = d / "nope.txt"
    got = t.file_write_text(str(f), "abc", dry_run=True)
    assert got["ok"] is True and got["would"] == "新建" and got["bytes"] == 3
    assert not f.exists(), "干跑不许建文件"


def test_read_truncation_is_declared(fs):
    _, t, d = fs
    f = d / "big.txt"
    f.write_text("x" * 500, encoding="utf-8")
    got = t.file_read_text(str(f), max_bytes=100)
    assert got["ok"] is True and got["truncated"] is True
    assert got["read"] == 100 and got["bytes"] == 500


def test_write_to_directory_is_refused(fs):
    _, t, d = fs
    got = t.file_write_text(str(d), "v")
    assert got["ok"] is False and "写不进去" in got["error"]
