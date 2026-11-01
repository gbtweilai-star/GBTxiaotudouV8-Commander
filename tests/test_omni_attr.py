"""test_omni_attr.py · 全开失败归因

判据：
  1. 7 类错误各自归到正确类别（ticket/timeout/missing_dep/missing_file/permission/network/real_bug）；
  2. 按域/职业聚合有数（职业从 professions.json 反查）；
  3. 输出 JSON + Markdown 报告，报告里有分类统计和失败清单；
  4. 空结果不崩（ok=True, failed=0）。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gbt_allinone import omni_attr  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    ok = bool(cond)
    print(("  ok   " if ok else "  FAIL ") + name + ((" · " + str(extra)) if extra else ""))
    if not ok:
        FAILS.append(name)


def main() -> int:
    rows = [
        {"run_id": "T1", "cap": "hand_bridge", "ok": False, "ms": 0,
         "error": "需授权位：没票不执行"},
        {"run_id": "T1", "cap": "slow_cap", "ok": False, "ms": 12000,
         "error": "超时 12s（已 kill）"},
        {"run_id": "T1", "cap": "llm_chat", "ok": False, "ms": 50,
         "error": "ModuleNotFoundError: No module named 'openai'"},
        {"run_id": "T1", "cap": "media_run", "ok": False, "ms": 60,
         "error": "FileNotFoundError: No such file or directory: 'ffmpeg.exe'"},
        {"run_id": "T1", "cap": "filesystem_write", "ok": False, "ms": 40,
         "error": "PermissionError: [WinError 5] 拒绝访问"},
        {"run_id": "T1", "cap": "recon_arxiv", "ok": False, "ms": 300,
         "error": "URLError: Connection timed out"},
        {"run_id": "T1", "cap": "selfscan", "ok": False, "ms": 80,
         "error": "AssertionError: unexpected state"},
        {"run_id": "T1", "cap": "inventory", "ok": True, "ms": 90},
    ]
    tmpdir = ROOT / "state" / "tmp"
    tmpdir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                     encoding="utf-8", dir=str(tmpdir)) as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        path = pathlib.Path(fh.name)

    print("[1] 7 类错误分类")
    out = omni_attr.attribute("T1", results_path=path)
    cats = out.get("categories") or {}
    check("ticket", cats.get("ticket") == 1, cats)
    check("timeout", cats.get("timeout") == 1, cats)
    check("missing_dep", cats.get("missing_dep") == 1, cats)
    check("missing_file", cats.get("missing_file") == 1, cats)
    check("permission", cats.get("permission") == 1, cats)
    check("network", cats.get("network") == 1, cats)
    check("real_bug", cats.get("real_bug") == 1, cats)
    check("总失败 7", out.get("failed") == 7, out.get("failed"))

    print("[2] 聚合与报告")
    check("按域有数", bool(out.get("by_domain")), out.get("by_domain"))
    check("按职业有数", bool(out.get("by_profession")), list(out.get("by_profession") or {})[:4])
    rep = pathlib.Path(out.get("report") or "")
    check("报告文件", rep.is_file(), rep)
    txt = rep.read_text(encoding="utf-8") if rep.is_file() else ""
    check("报告含分类", "按原因" in txt and "ticket" in txt)
    check("报告含失败清单", "失败清单" in txt and "hand_bridge" in txt)
    check("报告签名", "本署名不可删除" in txt)

    print("[3] 空结果不崩")
    _fd, _ep = tempfile.mkstemp(suffix=".jsonl", dir=str(tmpdir))
    import os as _os
    _os.close(_fd)
    empty = pathlib.Path(_ep)
    e = omni_attr.attribute("NOPE", results_path=empty)
    check("空结果 ok", e.get("ok") is True and e.get("failed") == 0, e.get("failed"))

    for _f in (path, empty):
        try:
            _f.unlink()
        except Exception:
            pass

    print()
    if FAILS:
        print("FAILED %d: %s" % (len(FAILS), FAILS))
        return 1
    print("ALL OK —— 失败归因：7 类分类/域职业聚合/报告/空结果 全过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
