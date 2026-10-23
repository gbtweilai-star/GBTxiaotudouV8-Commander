#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""固定用例：framework_gate 的**认领范围**必须可声明（F31/F39 根治后的回归闸）

## 根因（已修）
`cmd_close` 原来写的是 `"changed": _diff(整份基线, after)` —— 护照**没有"范围"这个概念**，
关一张只讲 A 的护照会把 A+B+C…**整批**记进它的账。两次同源事故：
  · F31 `fc-20260924T054911-7m0f` 认领 20 个（19 个早于 opened_at）
  · F39 `fc-20260925T003455-phnb` 理由写 2 个、实际 22 个
两次都因此把 `verify` 的**红洗成了绿**（假绿方向，最危险）。

## 修后应有的行为（本用例逐条咬住）
  ① `--files` 显式声明范围 ⇒ **只认领声明的那些**；其余**仍未认领** ⇒ verify 保持 **red**
  ② 相对基线有 **>1** 个变动却不声明范围 ⇒ **拒关**（fail-closed，不许整批认领）
  ③ `--files` 里塞一个**没有变动**的文件 ⇒ **拒关**（账目虚增一律拒）
  ④ **向后兼容**：变动只有 1 个、不声明范围 ⇒ 放行（等于恰好认领它），verify green
  ⑤ `verify` **分层输出**：`covered_by`（谁用哪条理由认领的）+ `范围含糊的旧护照` 名单

## 隔离保证
全程 `tempfile` + 门自带的 `--root` / `--store`（`framework_gate.py:497-499` help 原文：
「测试可指隔离树」）。**真仓 baseline.json / passports 零写入。**
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
GATE = ROOT / "gbt_allinone" / "tools" / "framework_gate.py"
PY = [sys.executable]
WATCH = ("gbt_allinone", "holo_pet", "holo_pet_w3", "potato_pet")

GOOD_REASON = "只改 gbt_allinone/a.py 这一个文件（回归用例，理由必须够 8 字）"


def run(args: list[str], root: pathlib.Path, store: pathlib.Path) -> tuple[int, dict]:
    """🔴 `--root` / `--store` 是**顶层参数，必须在子命令之前**
    （usage: `framework_gate.py [-h] [--root ROOT] [--store STORE] {snapshot,open,...} ...`）。

    🔴 加固：**永远返回 dict**。第一版在 JSON 解析失败时 `return (rc, txt[-400:])` 返回**字符串**，
    调用处当 dict 用 ⇒ 在印章那次跑里炸成
    `AttributeError: 'str' object has no attribute 'get'`（rc=1），
    而失败原因被这个二次异常盖住了 —— **量具自己把病因吞了**。
    现在解析失败也要给出结构化结果（`_raw` + `_parse_error`），让判据去红、并带上原文。
    """
    r = subprocess.run(PY + [str(GATE), "--root", str(root), "--store", str(store), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    txt = (r.stdout or "") + (r.stderr or "")
    i = txt.find("{")
    if i >= 0:
        # 🔴 加固（2026-09-25 印章那次跑抓到的第三个"量具病"）：**不能假设输出是一整段干净 JSON**。
        #    实测 `json.loads(txt[i:])` 炸在 `Extra data: line 8 column 1` —— 门吐的 JSON 后面
        #    还跟着别的行（`[stamp] …`）。于是 `open` 明明返回了 `id`，我却当成"没返回 id"，
        #    全 9 条连锁红。修法：`raw_decode` **只取第一个 JSON 值**，尾随内容一概忽略。
        dec = json.JSONDecoder()
        try:
            d, _end = dec.raw_decode(txt[i:])
            if isinstance(d, dict):
                return r.returncode, d
        except Exception as e:  # noqa: BLE001
            return r.returncode, {"_parse_error": str(e), "_raw": txt[-400:]}
    return r.returncode, {"_no_json": True, "_raw": txt[-400:]}


def scenario(td: str, name: str, changed: list[str]) -> tuple[pathlib.Path, pathlib.Path]:
    """造一棵隔离树 → 立基线 → 改指定的几个文件。返回 (tree, store)。"""
    tree = pathlib.Path(td) / name / "tree"
    store = pathlib.Path(td) / name / "store"
    for d in WATCH:
        (tree / d).mkdir(parents=True, exist_ok=True)
    for rel in ("gbt_allinone/a.py", "gbt_allinone/b.py", "holo_pet/c.py", "potato_pet/d.py"):
        p = tree / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# v1\n", encoding="utf-8")
    rc, _ = run(["snapshot", "--label", "repro"], tree, store)
    assert rc == 0, "基线立不起来"
    for rel in changed:
        (tree / rel).write_text("# v2 changed\n", encoding="utf-8")
    return tree, store


def main() -> int:
    lines, bad = [], 0

    # 🔴 开工自检（**先验量具，再量东西**）：印章那次跑里全部 9 条都以 rc=2 红掉，
    #    而 rc=2 正是"python 打不开脚本"的退出码 —— 也就是**量具本身没找对被测对象**。
    #    没有这道自检，这种失败会伪装成"被测对象坏了"（又一次假故障）。
    diag = {"cwd": str(pathlib.Path.cwd()), "ROOT": str(ROOT), "GATE": str(GATE),
            "GATE存在": GATE.is_file(), "解释器": sys.executable}
    if not GATE.is_file():
        print(json.dumps({"ok": False, "why": "**量具找不到被测对象**：GATE 路径不存在",
                          **diag}, ensure_ascii=False, indent=1))
        return 3

    def ck(name: str, cond: bool, detail: str) -> None:
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    with tempfile.TemporaryDirectory() as td:
        # ── ① 声明范围 ⇒ 只认领声明的；其余仍未认领 ⇒ verify 保持 red ──────────────
        tree, store = scenario(td, "s1", ["gbt_allinone/a.py", "gbt_allinone/b.py", "holo_pet/c.py"])
        _, o = run(["open", "--reason", GOOD_REASON], tree, store)
        pid = o.get("id") if isinstance(o, dict) else None
        rc, c = run(["close", "--id", str(pid), "--files", "gbt_allinone/a.py",
                     "--evidence", "cat a.py => # v2 changed",
                     "--review", "repro-reviewer: cat a.py => # v2 changed",
                     "--rollback", "git blob 无（隔离树无 git）",
                     "--no-stamp-reason", "隔离树回归用例，不跑回归印章"], tree, store)
        claimed = (c.get("changed") if isinstance(c, dict) else None) or []
        ck("①a 声明范围 ⇒ 只认领声明的那个",
           rc == 0 and claimed == ["gbt_allinone/a.py"],
           "rc=%d · claimed=%s · **open返回**=%s · raw=%s"
           % (rc, claimed, str(o)[:180],
              str(c.get("_raw") or c.get("_parse_error") or "")[:160]
              if isinstance(c, dict) else "?"))
        ck("①b 范围外的文件被记为**仍未认领**",
           isinstance(c, dict) and set(c.get("**仍未认领**") or []) == {"gbt_allinone/b.py", "holo_pet/c.py"},
           "仍未认领=%s" % (c.get("**仍未认领**") if isinstance(c, dict) else "?"))
        rc2, v = run(["verify", "--json"], tree, store)
        found = sorted(f["file"] for f in (v.get("findings") or [])) if isinstance(v, dict) else []
        ck("①c 范围外仍未认领 ⇒ verify **保持 red**（不再被一张护照洗绿）",
           rc2 == 1 and v.get("verdict") == "red" and found == ["gbt_allinone/b.py", "holo_pet/c.py"],
           "rc=%d · verdict=%s · findings=%s" % (rc2, v.get("verdict"), found))

        # ── ② 多变动不声明范围 ⇒ 拒关 ────────────────────────────────────────────
        tree, store = scenario(td, "s2", ["gbt_allinone/a.py", "gbt_allinone/b.py"])
        _, o = run(["open", "--reason", GOOD_REASON], tree, store)
        rc3, c3 = run(["close", "--id", str(o.get("id")), "--evidence", "x => y",
                       "--review", "r: x => y", "--rollback", "git blob 无（隔离树无 git）",
                       "--no-stamp-reason", "回归用例"], tree, store)
        probs = " ".join(c3.get("problems") or []) if isinstance(c3, dict) else str(c3)
        ck("② 多变动不声明范围 ⇒ **拒关**（fail-closed，不许整批认领）",
           rc3 == 2 and "认领范围未声明" in probs, "rc=%d · %s" % (rc3, probs[:90]))

        # ── ③ 认领"没变动"的文件 ⇒ 拒关 ─────────────────────────────────────────
        tree, store = scenario(td, "s3", ["gbt_allinone/a.py"])
        _, o = run(["open", "--reason", GOOD_REASON], tree, store)
        rc4, c4 = run(["close", "--id", str(o.get("id")),
                       "--files", "gbt_allinone/a.py", "--files", "gbt_allinone/b.py",
                       "--evidence", "x => y", "--review", "r: x => y",
                       "--rollback", "git blob 无（隔离树无 git）",
                       "--no-stamp-reason", "回归用例"], tree, store)
        probs4 = " ".join(c4.get("problems") or []) if isinstance(c4, dict) else str(c4)
        ck("③ 认领一个**没变动**的文件 ⇒ 拒关（账目虚增一律拒）",
           rc4 == 2 and "没有变动" in probs4, "rc=%d · %s" % (rc4, probs4[:90]))

        # ── ④ 向后兼容：只 1 个变动、不声明范围 ⇒ 放行 ────────────────────────────
        tree, store = scenario(td, "s4", ["gbt_allinone/a.py"])
        _, o = run(["open", "--reason", GOOD_REASON], tree, store)
        rc5, c5 = run(["close", "--id", str(o.get("id")), "--evidence", "x => y",
                       "--review", "r: x => y", "--rollback", "git blob 无（隔离树无 git）",
                       "--no-stamp-reason", "回归用例"], tree, store)
        rc6, v5 = run(["verify", "--json"], tree, store)
        ck("④ 兼容：变动只有 1 个、不声明范围 ⇒ 放行且 verify green",
           rc5 == 0 and rc6 == 0 and v5.get("verdict") == "green",
           "close rc=%d · verify rc=%d · verdict=%s" % (rc5, rc6, v5.get("verdict")))

        # ── ⑤ verify 分层输出 ───────────────────────────────────────────────────
        cb = (v5.get("covered_by") if isinstance(v5, dict) else None) or {}
        entry = cb.get("gbt_allinone/a.py") or {}
        ck("⑤ verify 分层：covered_by 能说出『谁用哪条理由认领的』",
           entry.get("现状") == "已覆盖且新鲜"
           and isinstance(entry.get("认领护照"), list) and bool(entry["认领护照"])
           and "reason" in entry["认领护照"][0],
           "a.py 现状=%s · 认领护照=%s" % (entry.get("现状"), (entry.get("认领护照") or [{}])[0].get("id")))

        # ── ⑥ **历史格式**（没有 declared_scope 键）也必须被抓出来 ────────────────
        # 实测教训：真仓那批老护照**根本没有** declared_scope / claimed_all_pending 两个键
        # （fhnb：两键皆 None）⇒ 第一版探测器写 `p.get("claimed_all_pending") and …`
        # ⇒ **历史那批一个都抓不到**，而它们恰恰就是 F31/F39 那一批。这里造一个老格式护照咬住它。
        # 🔴 路径别照抄真仓：`--store` 传进去的**就是账本根**，护照落在 `<store>/passports/`
        #    （真仓那串 `gbt_allinone/store/framework_changes` 是 `_default_store()` 的**返回值**，
        #     不是相对结构）。我第一版写成 `<store>/framework_changes/passports/` ⇒ 文件写到了没人读的地方。
        legacy = store / "passports" / "fc-legacy-00000000-zzzz.json"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(json.dumps({
            "id": "fc-legacy-00000000-zzzz", "opened_at": "2026-01-01T00:00:00",
            "closed_at": "2026-01-01T00:10:00", "reason": "老格式护照（没有 declared_scope 键）",
            "changed": {"potato_pet/d.py": {"before": "x", "after": "y"},
                        "holo_pet/c.py": {"before": "x", "after": "y"}},
            "after": {"potato_pet/d.py": "y", "holo_pet/c.py": "y"},
            "evidence": ["e => r"], "review": ["r: e => r"], "rollback": "git blob 无",
            "stamp": None,
        }, ensure_ascii=False), encoding="utf-8")
        rc7, v7 = run(["verify", "--json"], tree, store)
        bad_legacy = sorted((v7 or {}).get("范围含糊的旧护照") or [])
        ck("⑥ 老格式护照（无 declared_scope、认领 >1）⇒ 必须被点名（我自己的洞）",
           "fc-legacy-00000000-zzzz" in bad_legacy,
           "范围含糊的旧护照=%s · verify rc=%d" % (bad_legacy, rc7))
        ck("⑥b 分层输出现状：a.py 新鲜 / 其余未认领能被分别读出",
           isinstance((v7 or {}).get("covered_by"), dict)
           and (v7.get("covered_by") or {}).get("gbt_allinone/a.py", {}).get("现状") == "已覆盖且新鲜"
           and all(k in (v7 or {}) for k in ("已认领且新鲜", "未认领", "认领但已过期")),
           "计数键齐：%s" % [k for k in ("已认领且新鲜", "未认领", "认领但已过期") if k in (v7 or {})])

    print(json.dumps({
        "被验的修复": "framework_gate 护照**认领范围可声明**（F31/F39 根因）",
        "根因": "cmd_close 的 changed 由 _diff(整份基线, after) 得出 ⇒ 护照没有范围概念",
        "隔离保证": "全程 tempfile + --root/--store；真仓 baseline.json / passports 零写入",
        "开工自检": diag,
        "自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
        "逐条": lines,
    }, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
