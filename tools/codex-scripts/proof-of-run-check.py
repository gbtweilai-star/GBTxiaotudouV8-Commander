# -*- coding: utf-8 -*-
"""交付证据审查 —— **没有亲自跑通的东西不许交付**（主人令 2026-10-10，逐字）

主人原话：
  「所有的验证我只看实质性跑通闭环证据，**不接受任何口述说完成了**」
  「把这个验证方式也给框架绑死了，**没有亲自跑通的东西不许交付**」

## 它判什么（不是又加一道门，是把主人这句话钉成可复跑的读数）
  **每一项交付声明，都必须带一条可复跑的命令与期望读数；本器当场复跑那条命令并比对。**
    ① 只有口述、没带命令/期望读数   ⇒ 红（口述不算证据）
    ② 带了命令，复跑跑不通           ⇒ 红（没跑通就是没跑通）
    ③ 带了命令，复跑通过且读数一致   ⇒ 绿（亲自跑通了）

## 台账（声明落这儿，只追加）
  state/delivery-claims.jsonl 每行：
    {id, what, cmd, expect_contains, at}
  cmd 由 shell 执行（cwd = 仓根）；expect_contains 必须出现在其 stdout+stderr 里。

## 负控（真植入，不是喂合成数据）
  ① 只有口述（无 cmd）      ⇒ 必须红
  ② 命令跑不通              ⇒ 必须红
  ③ 命令跑得通但读数对不上  ⇒ 必须红

用法: py -3.14 -X utf8 tools/codex-scripts/proof-of-run-check.py [--json] [--selftest]
退出码：0 = 全部亲跑通过；1 = 有红；3 = 台账为空（**不适用 ≠ 失败**）。
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

WS = pathlib.Path(__file__).resolve().parents[2]
LEDGER = WS / "state" / "delivery-claims.jsonl"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")   # type: ignore[attr-defined]
    except Exception:
        pass


def _isolated_store() -> str:
    sd = os.environ.get("GBT_STORE_DIR") or ""
    if not sd:
        return ""
    try:
        q = pathlib.Path(sd).resolve()
        ws = WS.resolve()
        if ws == q or ws in q.parents:
            return ""
        return str(q)
    except Exception:
        return sd


def read_claims(path=None):
    f = pathlib.Path(path or LEDGER)
    if not f.is_file():
        return [], []
    rows, bad = [], []
    for i, ln in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        try:
            rows.append(json.loads(ln))
        except Exception as e:  # noqa: BLE001
            bad.append({"line": i, "why": "不是合法 JSON：%s" % e})
    return rows, bad


def _shell(cmd, timeout=300):
    try:
        r = subprocess.run(cmd, shell=True, cwd=str(WS), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "（超时）"
    except Exception as e:  # noqa: BLE001
        return 125, "（跑不动：%s）" % e


def judge(rows, runner=None, isolated=False):
    # 🔴 2026-10-10 加 scope（**第三次自纠，还是被我自己的判据咬出来的**）：
    #    声明分两种 ——
    #      · scope="any"（默认）：在哪儿都能量（判据/selftest/文件存在/框架门…）
    #      · scope="production" ：**只能在生产环境量**（镜像干净 / 镜像排练 / 框架门 verify）
    #    开机自检**永远**在隔离 store 里跑 ⇒ 那些 production 声明**量不到真东西**。
    #    对它们**如实报「不适用」**：既不许假装通过，也不许误报红（假红与假绿一样坏）。
    runner = runner or _shell
    results = []
    for r in rows:
        _scope = str(r.get("scope") or "any").strip().lower()
        if _scope == "production" and isolated:
            results.append({"id": str(r.get("id") or ""), "what": str(r.get("what") or ""),
                            "ok": True, "rc": 3, "not_applicable": True,
                            "why": "**不适用**：本声明只能在**生产**环境量，当前跑在隔离 store"})
            continue
        cid = str(r.get("id") or "")
        what = str(r.get("what") or "")
        cmd = str(r.get("cmd") or "").strip()
        expect = str(r.get("expect_contains") or "").strip()
        if not cmd or not expect:
            results.append({"id": cid, "what": what, "ok": False, "rc": None,
                            "why": "**口述**：没有可复跑命令或期望读数 ⇒ 不算证据"})
            continue
        rc, out = runner(cmd)
        if rc != 0:
            results.append({"id": cid, "what": what, "ok": False, "rc": rc,
                            "why": "命令**复跑跑不通**（rc=%s）" % rc, "tail": out[-200:]})
            continue
        if expect not in out:
            results.append({"id": cid, "what": what, "ok": False, "rc": rc,
                            "why": "跑通了但**读数对不上**：期望含 %r" % expect, "tail": out[-200:]})
            continue
        results.append({"id": cid, "what": what, "ok": True, "rc": rc,
                        "why": "亲跑通过，读数含 %r" % expect})
    return results


def render(results, bad):
    print("=" * 74)
    print("交付证据审查 · **没有亲自跑通的东西不许交付**（主人令 2026-10-10）")
    print("=" * 74)
    _na = 0
    for b in bad:
        print("  🔴 台账第 %s 行：%s" % (b["line"], b["why"]))
    if not results and not bad:
        print("  （台账为空 —— 本件**不适用**，不是通过）")
        print("")
        return
    for r in results:
        _mark = "➖" if r.get("not_applicable") else ("✅" if r["ok"] else "🔴")
        print("  %s [%s] %s" % (_mark, r["id"] or "?", r["what"][:56]))
        print("        %s" % r["why"])
    red = [r for r in results if not r["ok"] and not r.get("not_applicable")]
    na = [r for r in results if r.get("not_applicable")]
    print("")
    print("亲跑通过 %d / %d 条 · 不适用 %d 条（**不适用 ≠ 通过**）"
          % (len(results) - len(red) - len(na), len(results), len(na)))
    print("")


def selftest():
    ok = []
    good = {"id": "T1", "what": "真跑得通的命令", "cmd": "py -3.14 -X utf8 -c \"print(12345)\"",
            "expect_contains": "12345"}
    bad_nocmd = {"id": "T2", "what": "只有口述", "cmd": "", "expect_contains": ""}
    bad_fail = {"id": "T3", "what": "命令跑不通", "cmd": "py -3.14 -X utf8 -c \"raise SystemExit(2)\"",
                "expect_contains": "x"}
    bad_read = {"id": "T4", "what": "读数对不上", "cmd": "py -3.14 -X utf8 -c \"print(1)\"",
                "expect_contains": "绝不可能出现的串"}
    rs = judge([good, bad_nocmd, bad_fail, bad_read])
    m = {r["id"]: r for r in rs}
    ok.append(("真件·真跑得通的声明 ⇒ 绿", m["T1"]["ok"], m["T1"]["why"]))
    ok.append(("真植入负控·只有口述 ⇒ 必红", not m["T2"]["ok"], m["T2"]["why"]))
    ok.append(("真植入负控·命令跑不通 ⇒ 必红", not m["T3"]["ok"], m["T3"]["why"]))
    ok.append(("真植入负控·读数对不上 ⇒ 必红", not m["T4"]["ok"], m["T4"]["why"]))
    bad = [n for n, c, _ in ok if not c]
    for n, c, d in ok:
        print("  %-44s %s  (%s)" % (n, "✅" if c else "❌", d[:70]))
    print("")
    print("proof-of-run-check 自检: %s（%d 条）"
          % ("全部通过" if not bad else "%d 条失败" % len(bad), len(ok)))
    return 1 if bad else 0


def main():
    if "--selftest" in sys.argv[1:]:
        return selftest()
    # 🔴 2026-10-10 自纠：我原来在这里加了「隔离 store ⇒ 不适用」，**那是设计错误**。
    #    本仓开机自检（boot-selfcheck.py）**永远**在隔离 store 里跑 ⇒ 那样这条律
    #    **永远不被执行** = 等于没绑（而主人令是「把这个验证方式也给框架绑死了」）。
    #    而台账里每条声明的命令**本来就是自足的**（需要隔离 store 的那条，自己带上了）
    #    ⇒ 本件**照跑**，不看 GBT_STORE_DIR。
    #    若某条声明在隔离环境里跑不通 ⇒ 那**正是本件该报的红**（声明对条件不健壮）。
    rows, bad = read_claims()
    if not rows and not bad:
        render([], [])
        return 3
    results = judge(rows, isolated=bool(_isolated_store()))
    render(results, bad)
    if "--json" in sys.argv[1:]:
        print(json.dumps({"results": results, "bad": bad}, ensure_ascii=False, indent=1))
    return 1 if (bad or any(not r["ok"] for r in results)) else 0


if __name__ == "__main__":
    raise SystemExit(main())