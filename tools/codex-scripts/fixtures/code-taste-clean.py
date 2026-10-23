# -*- coding: utf-8 -*-
"""正对照 · 一份能过机的代码。

它**故意写得不花哨**：命名有意义、错误显式上报、函数短、嵌套浅、没有占位与调试残留。
判据要求：`audit_code_taste.py` 在本文件上 **P0 = 0**（P1 也应为 0）。
"""
from __future__ import annotations

from pathlib import Path


class RecordError(Exception):
    """本模块自己的错误类型 —— 不用裸 Exception 一把抓。"""


def parse_record(raw: str) -> dict:
    """把一行 "k=v" 解析成字典；解析不了就抛自己的错误类型。"""
    key, sep, value = raw.partition("=")
    if not sep or not key.strip():
        raise RecordError("not a k=v line: %r" % raw[:40])
    return {key.strip(): value.strip()}


def load_records(path: Path) -> list[dict]:
    """读文件并逐行解析；第一处坏行就停下并说明是第几行（不吞、不猜）。"""
    records = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            records.append(parse_record(raw))
        except RecordError as exc:
            raise RecordError("%s:%d: %s" % (path.name, lineno, exc)) from exc
    return records


def count_keys(records: list[dict]) -> dict:
    """统计每个键出现过几次 —— 早返回把嵌套压平。"""
    tally: dict[str, int] = {}
    for record in records:
        for key in record:
            tally[key] = tally.get(key, 0) + 1
    return tally
