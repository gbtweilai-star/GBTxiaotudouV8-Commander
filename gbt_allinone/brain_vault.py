# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 脑库接入（Obsidian 记忆库）。

设计口径（主人 2026-09-19）：
  **大模型接入大脑记忆，跟着一起上线 —— 写进去的，想忘都忘不了。**

所以这里只做三件事，且都是"记忆"语义：
  recall()   把记忆接上（记忆总纲 + 收集箱最近若干条）—— 开工时读
  remember() 往收集箱追一条（**追加，不覆盖**）—— 这就是"忘不了"的写入口
  status()   库在哪、多少笔记、有没有断链

三条纪律：
  1. **不删任何笔记**；本模块没有任何删除路径。
  2. 收集箱是**追加式**（与 QuickAdd 的落点一致），不是"重写整个文件"。
  3. 库路径可被 `GBT_VAULT_DIR` 覆盖 ⇒ 测试能把它指到临时库，不碰主人的真库。
"""
from __future__ import annotations

import io
import os
import time
from pathlib import Path

_DEFAULT_VAULT = Path(r"C:\Users\ADMIN\Documents\Codex\ObsidianVault")
_INBOX = "收集箱.md"
_MAIN = "地图/记忆总纲.md"


def _cannot(rule: str, why: str, missing, **extra) -> dict:
    """R-H295 · ⑥ G1/G2：脑库**做不了**时的结构化上报。

    《触手覆盖矩阵.md》§三：脑组 6 个模块只有 3 个能报"做不了"，本文件是缺的那一类 ——
    原来只有 {"ok": False, "error": "脑库目录不存在"}：调用方拿不到机器可读的分类
    （是 vault 不在、inbox 不在、还是内容为空？）。脑库是记忆的落点，
    记不进去必须说清是缺哪一样，不能只回一句人话。
    """
    out = {
        "ok": False,
        "unavailable": True,
        "denied": False,
        "rule": str(rule),
        "action": "brain_vault",
        "missing": list(missing or ()),
        "why": str(why)[:240],
        "error": str(why)[:240],  # 向后兼容：老调用方读 error
        "note": "脑库做不了 ⇒ 结构化上报：缺什么写在 missing 里。",
    }
    out.update(extra)
    return out


def vault_dir() -> Path:
    raw = os.environ.get("GBT_VAULT_DIR", "").strip()
    return Path(raw).expanduser() if raw else _DEFAULT_VAULT


def _read(rel: str) -> str:
    path = vault_dir() / rel
    if not path.is_file():
        return ""
    return io.open(path, encoding="utf-8", errors="replace").read()


def status() -> dict:
    """库在哪、有多少东西、有没有断链（只读）。"""
    vault = vault_dir()
    if not vault.is_dir():
        return _cannot("brain_vault_dir_missing", "脑库目录不存在：%s" % vault, ["vault"], vault=str(vault))
    notes = [p for p in vault.rglob("*.md") if ".obsidian" not in p.parts]
    links = 0
    unresolved = set()
    for note in notes:
        text = io.open(note, encoding="utf-8", errors="replace").read()
        links += text.count("[[")
        for chunk in text.split("[[")[1:]:
            name = chunk.split("]]")[0].split("|")[0].split("#")[0].strip()
            if not name:
                continue
            if (vault / (name + ".md")).is_file() or (vault / name).is_file():
                continue
            if any(cand.stem == Path(name).name for cand in notes):
                continue
            unresolved.add(name)
    return {
        "ok": True,
        "vault": str(vault),
        "notes": len(notes),
        "wikilinks": links,
        "unresolved": sorted(unresolved),
        "canvas": len(list(vault.rglob("*.canvas"))),
        "inbox_exists": (vault / _INBOX).is_file(),
        "main_note_exists": (vault / _MAIN).is_file(),
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def recall(limit: int = 10) -> dict:
    """把记忆接上：记忆总纲 + 收集箱最近 limit 条。"""
    vault = vault_dir()
    if not vault.is_dir():
        return _cannot("brain_vault_dir_missing", "脑库目录不存在：%s" % vault, ["vault"], vault=str(vault))
    main = _read(_MAIN)
    inbox_raw = _read(_INBOX)
    lines = [ln for ln in inbox_raw.splitlines() if ln.strip()]
    recent = lines[-max(1, int(limit)):]
    return {
        "ok": True,
        "vault": str(vault),
        "main_note": main[:4000],
        "inbox_lines": len(lines),
        "recent": recent,
        "note": "这是记忆的读入口；写入口是 remember()（追加到收集箱，不覆盖）。",
    }


def remember(text: str) -> dict:
    """往收集箱追一条 —— 追加式，不重写、不删。"""
    body = " ".join(str(text or "").split())
    if not body:
        return _cannot("brain_vault_empty_content", "要记的内容为空（没东西可记）", ["content"])
    vault = vault_dir()
    if not vault.is_dir():
        return _cannot("brain_vault_dir_missing", "脑库目录不存在：%s" % vault, ["vault"], vault=str(vault))
    inbox = vault / _INBOX
    if not inbox.is_file():
        return _cannot("brain_vault_inbox_missing", "收集箱不存在：%s" % inbox, ["inbox"], path=str(inbox))
    stamp = time.strftime("%Y-%m-%d %H:%M")
    before = inbox.stat().st_size
    with io.open(inbox, "a", encoding="utf-8") as fh:
        fh.write("- `%s` %s\n" % (stamp, body))
    after = inbox.stat().st_size
    return {
        "ok": True,
        "wrote": True,
        "path": str(inbox),
        "stamp": stamp,
        "line": "- `%s` %s" % (stamp, body),
        "bytes": {"before": before, "after": after, "delta": after - before},
        "note": "追加式写入：不覆盖、不删；下次 recall() 就能读到。",
    }
