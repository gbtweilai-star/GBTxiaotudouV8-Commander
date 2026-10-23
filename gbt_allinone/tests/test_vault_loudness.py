# -*- coding: utf-8 -*-
"""保险箱「解不开」必须响 —— 蓝图 §9.1 · Q2 的回归判据（2026-10-08 立）。

## 为什么这件必须存在

登记在案的真缺陷（P0 · 静默失效）：`load_from_vault()` 在 DPAPI 解不开时**不抛异常**，
返回 `("", "unreadable")` —— 调用方收到一个空 key，往下走就变成「上游 401」，
人去追 401，真正的原因一个字都没露。

判据只有一条精神：**「没有密钥」与「有密钥但读不出来」必须能被区分，且后者要响。**
两条用例正好互为正负对照：
  · 解不开  → 必须抛 DeepseekKeyError（响）
  · 文件不在 → 必须仍返回 ("", "missing")（那是合法状态，不许也被弄成异常，
    否则每一次"这个 profile 没配"都会变成炸链）

跑法：py -3.14 -m pytest gbt_allinone/tests/test_vault_loudness.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gbt_allinone import deepseek_key as dk  # noqa: E402


def test_解不开必须抛_并点名原因(monkeypatch, tmp_path):
    """有文件、但 DPAPI 解不开 ⇒ 抛 DeepseekKeyError，且报错里带 profile 与文件路径。"""
    vault = tmp_path / "deepseek_api.dpapi"
    vault.write_bytes(b"NOT-A-VALID-DPAPI-BLOB")

    monkeypatch.setattr(dk, "_secret_file", lambda profile=None: vault)

    def _boom(_blob, _name):
        raise ValueError("CryptUnprotectData 失败（换了用户或机器）")

    monkeypatch.setattr(dk, "_unprotect_dpapi", _boom)

    with pytest.raises(dk.DeepseekKeyError) as ei:
        dk.load_from_vault()

    msg = str(ei.value)
    assert "解不开" in msg, "报错必须说清是「解不开」，不是别的：%s" % msg
    assert "deepseek" in msg, "要点名是哪个 profile：%s" % msg
    assert str(vault) in msg, "要点名是哪个文件：%s" % msg
    assert "401" in msg, "要提醒别当上游 401 追：%s" % msg


def test_负对照_文件不在仍返回_missing(monkeypatch, tmp_path):
    """没有那份文件 ⇒ 仍返回 ("", "missing") —— 合法状态，不许也被弄成异常。"""
    monkeypatch.setattr(dk, "_secret_file", lambda profile=None: tmp_path / "根本没有这个文件.dpapi")
    key, source = dk.load_from_vault()
    assert key == ""
    assert source == "missing", "「没有」必须是 missing，不能混成 unreadable/异常：%r" % source
