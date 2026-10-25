# gbt-capability: 可见写盘（原子写 → 兜底写 → **每级留痕 + 返回真假**）
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""写盘的**唯一正确形状**：要么真落盘，要么**留下可读到的痕迹**。

═══ 为什么要有这件（必读清单第 31 / 39 / 40 / 41 条）═══
本仓有两处**逐字同构**的写盘函数（`visual_memory._safe_write` 与
`visual_cortex._safe_json_write`），形状都是「两级兜底、两级都无声」：

    if safe_io is not None:
        try:  safe_io.atomic_write_json(path, data); return
        except Exception: pass      # ① 原子写失败 ⇒ 静默落到"自己手写"
    try:  ... tmp.write_text(...); tmp.replace(path)
    except OSError: pass            # ② 自己手写也失败 ⇒ 静默

**两级都失败时，这次写零痕迹丢失**，而调用方以为存上了 ——
「记忆说记住了，其实什么都没写」= 最典型的错报。
第 41 条说得很直白：**同一个错的形状出现第二遍，就该抽成共享件**，否则第三份还会来。

═══ 口径（四件套，一个字都不许省）═══
  ① **不抛** —— 写不进去不该把调用链带崩；
  ② **每一级都记账** —— 原子写失败记一次、兜底失败再记一次（计数与**实际尝试次数**对齐，
     不与"调用次数"对齐 —— 第 40 条）；
  ③ **返回真假** —— 上层有办法如实报告，而不是"照旧返回成功"；
  ④ **只读口 `health()`** —— `count>0` ⇒ 有产物没真正落盘，必须看得见。

用法：
    from visible_write import write_json
    ok = write_json(path, data, label="visual_memory")   # ok=False ⇒ 没落盘，别报成功
    visible_write.health("visual_memory")                # {'count': n, 'reasons': {...}}
"""
from __future__ import annotations

import importlib
import json
import time
from pathlib import Path

# label -> {"count", "reasons", "last_at", "last_where"}；按调用方分账，便于定位是谁没落盘
_LABELS: dict = {}


def _bucket(label: str) -> dict:
    return _LABELS.setdefault(str(label or "?"),
                              {"count": 0, "reasons": {}, "last_at": None, "last_where": ""})


def note(label: str, where: str, exc) -> None:
    """记一次降级：计数 + 记因 + **同类只在首次出声**（不刷屏，免得淹掉真故障）。"""
    b = _bucket(label)
    b["count"] += 1
    b["last_at"] = round(time.time(), 3)
    b["last_where"] = where
    k = type(exc).__name__
    b["reasons"][k] = b["reasons"].get(k, 0) + 1
    if b["reasons"][k] == 1:
        try:
            import sys as _s
            print("⚠️ %s: 落盘降级（%s @%s: %s）⇒ 产物可能缺件（累计 %d 次）"
                  % (label, k, where, str(exc)[:100], b["count"]), file=_s.stderr)
        except Exception:                                       # noqa: BLE001
            pass


def health(label: str | None = None) -> dict:
    """只读：降级读数。给 `label` 只看那一家；不给则汇总各家。"""
    if label is not None:
        b = dict(_bucket(label))
        b.update({"ok": True, "readonly": True, "label": str(label),
                  "note": "count>0 ⇒ 有产物没真正落盘（不是内部细节，是必须被看见的读数）"})
        return b
    total = sum(v["count"] for v in _LABELS.values())
    return {"ok": True, "readonly": True, "total": total,
            "by_label": {k: {"count": v["count"], "reasons": dict(v["reasons"]),
                             "last_where": v["last_where"]} for k, v in _LABELS.items()},
            "note": "total>0 ⇒ 有产物没真正落盘"}


def _safe_io():
    """按本仓惯例双路径拿 safe_io（包路径优先，失败退顶层名）。拿不到返回 None。"""
    for name in ("gbt_allinone.safe_io", "safe_io"):
        try:
            return importlib.import_module(name)
        except Exception:                                       # noqa: BLE001
            continue
    return None


def _write(path, payload: bytes, label: str, atomic_name: str, fallback) -> bool:
    """两级写：① safe_io 原子写 → ② 自己手写（tmp + replace）。**每级失败都记账。**"""
    path = Path(path)
    mod = _safe_io()
    if mod is not None:
        fn = getattr(mod, atomic_name, None)
        if callable(fn):
            try:
                fn(path, payload)
                return True
            except Exception as _e:                             # noqa: BLE001
                note(label, "%s->%s" % (atomic_name, path.name), _e)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        fallback(tmp, payload)
        tmp.replace(path)
        return True
    except OSError as _e:
        note(label, "fallback->%s" % path.name, _e)
        return False


def write_json(path, data, label: str = "?") -> bool:
    """写 JSON。`safe_io.atomic_write_json` 优先（传对象），兜底自己序列化。"""
    path = Path(path)
    mod = _safe_io()
    if mod is not None and callable(getattr(mod, "atomic_write_json", None)):
        try:
            mod.atomic_write_json(path, data)
            return True
        except Exception as _e:                                 # noqa: BLE001
            note(label, "atomic_write_json->%s" % path.name, _e)
    blob = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    return _write(path, blob, label, "__no_atomic__",
                  lambda tmp, b: tmp.write_bytes(b))


def write_bytes(path, data: bytes, label: str = "?") -> bool:
    return _write(path, bytes(data), label, "atomic_write_bytes",
                  lambda tmp, b: tmp.write_bytes(b))


def write_text(path, text: str, label: str = "?") -> bool:
    """写文本。

    🔴 **本函数不能复用 `_write`**：`_write` 只吞 bytes，而 `safe_io.atomic_write_text`
    收的是 **str**。第一版把 bytes 塞给了它，落盘内容不对 ——
    **是本模块自己的负对照当场抓出来的**（"文本内容不对"）。
    ⇒ 与 `write_json` 同构：原子层传 str（文本模式），兜底层也用文本模式写。
    """
    path = Path(path)
    mod = _safe_io()
    if mod is not None and callable(getattr(mod, "atomic_write_text", None)):
        try:
            mod.atomic_write_text(path, str(text))
            return True
        except Exception as _e:                                 # noqa: BLE001
            note(label, "atomic_write_text->%s" % path.name, _e)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(str(text), encoding="utf-8")
        tmp.replace(path)
        return True
    except OSError as _e:
        note(label, "fallback_text->%s" % path.name, _e)
        return False


# ───────────────────────────────────────────── 两把对照

def selftest(verbose: bool = True) -> int:
    import contextlib
    import io as _io
    import sys as _sys
    import tempfile
    bad = []
    d = Path(tempfile.mkdtemp(prefix="vw_selftest_"))
    base = health("selftest")["count"]
    # 负对照：真写必须成功、必须落盘、**不许记账**
    ok1 = write_json(d / "a.json", {"k": 1}, label="selftest")
    ok2 = write_bytes(d / "b.bin", b"xyz", label="selftest")
    ok3 = write_text(d / "c.txt", "hello", label="selftest")
    if not (ok1 and ok2 and ok3):
        bad.append("真写返回了假：%s/%s/%s" % (ok1, ok2, ok3))
    for f in ("a.json", "b.bin", "c.txt"):
        if not (d / f).is_file():
            bad.append("真写却没落盘：%s" % f)
    if health("selftest")["count"] != base:
        bad.append("正常路径竟然记账了")
    if json.loads((d / "a.json").read_text(encoding="utf-8")) != {"k": 1}:
        bad.append("JSON 内容不对")
    if (d / "c.txt").read_text(encoding="utf-8") != "hello":
        bad.append("文本内容不对")
    # 正对照：两级都失败 ⇒ 返回 False + **记两次**（原子一次、兜底一次）+ 只出声一次
    bad_path = Path("Z:/definitely/not/writable/x.json")
    buf = _io.StringIO()
    with contextlib.redirect_stderr(buf):
        got = write_json(bad_path, {"k": 2}, label="selftest_bad")
    n = health("selftest_bad")["count"]
    lines = [l for l in buf.getvalue().splitlines() if l]
    if got is not False:
        bad.append("两级都失败却返回了 %r（应 False）" % got)
    if n != 2:
        bad.append("两级失败应记 2 次（实际尝试次数），实记 %d" % n)
    if len(lines) != 1:
        bad.append("同类应只出声 1 次，实际 %d 次" % len(lines))
    if verbose:
        print("═══ visible_write · 两把对照 ═══")
        print("负对照：真写 3 种全成功且落盘 · 未记账 = %s" % (not any("真写" in b or "竟然" in b for b in bad)))
        print("正对照：两级失败 → 返回 False · 记账 2 次 · 出声 1 次 = %s" % (got is False and n == 2 and len(lines) == 1))
        print("汇总读数 = %s" % json.dumps(health(), ensure_ascii=False)[:180])
        print("结论：%s" % ("两把对照都过 ✅" if not bad else "✗ 判红：%s" % bad))
    return 0 if not bad else 1


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(selftest())
