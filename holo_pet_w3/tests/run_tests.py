# -*- coding: utf-8 -*-
"""GBT小土豆V8 · W3 · 布局测试统一入口（不是孤儿测试）。

为什么要这个入口：`test_layout_snap.cjs` 是 JS 测试，跑法叫 `node --test`。
如果只留一个 .cjs 文件，任何回归框架都不知道该怎么调它——那就成了孤儿测试。
本入口把「怎么跑 / 结果长什么样 / 退出码怎么解释」固定下来：

  * 命令行：`py -3.10 run_tests.py`            -> 打印摘要 + 落 JSON + 退出码即结论
  * 编程调用：`from run_tests import run; run()` -> 返回 dict（回归框架可直接接）

结果一律落文件（《结果通道律》：结果不走 stdout 当唯一通道）。
退出码：0 全绿 / 1 有失败 / 2 环境不可用（找不到 node）

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _repo_root() -> Path:
    """向上找带 gbt_allinone 的目录（与 shell/main.cjs 的 findRepoRoot 同口径）。"""
    cur = HERE
    for _ in range(12):
        if (cur / "gbt_allinone").is_dir():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return HERE


# 运行产物不许落在维度里（否则晋升时会跟着进 reality）。
# 默认落 .scratch/；找不到仓库根时退回本目录旁的 .tmp。
_ROOT = _repo_root()
DEFAULT_JSON = (_ROOT / ".scratch" / "_w3_layout_tests_result.json") if (_ROOT / "gbt_allinone").is_dir() \
    else (HERE / ".tmp_layout_tests_result.json")

_NODE_CANDIDATES = [
    r"C:\Program Files\nodejs\node.exe",
    r"C:\Program Files (x86)\nodejs\node.exe",
]


def find_node() -> str | None:
    found = shutil.which("node")
    if found:
        return found
    for cand in _NODE_CANDIDATES:
        if Path(cand).exists():
            return cand
    return None


def run(json_out: str | Path | None = None) -> dict:
    """跑布局契约测试。返回 dict（ok/passed/failed/total/exit_code/输出摘要/落盘路径）。"""
    out_path = Path(json_out) if json_out else DEFAULT_JSON
    started = time.time()
    node = find_node()
    if not node:
        result = {"ok": False, "error": "NO_NODE", "hint": "PATH 与常见安装目录都没找到 node",
                  "passed": 0, "failed": 0, "total": 0, "exit_code": 2}
    else:
        # 显式列出测试文件：`node --test <目录>` 的自动发现不认 `test_*.cjs`
        # （Node 只认 *.test.cjs / test-*.cjs / **/test/** 那几类），传目录会「0 个用例」静默跑空。
        files = sorted(p for p in HERE.glob("test_*.cjs") if p.is_file())
        if not files:
            result = {"ok": False, "error": "NO_TESTS_FOUND", "exit_code": 2,
                      "hint": "tests/ 下没有 test_*.cjs", "passed": 0, "failed": 0, "total": 0}
            result["elapsed_s"] = round(time.time() - started, 2)
            result["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf8")
            result["json"] = str(out_path)
            return result
        cmd = [node, "--test", "--test-reporter=tap"] + [str(p) for p in files]
        try:
            cp = subprocess.run(cmd, cwd=str(HERE), capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=180)
            raw = (cp.stdout or "") + (cp.stderr or "")
            passed = _first_int(raw, r"^#\s*pass\s+(\d+)")
            failed = _first_int(raw, r"^#\s*fail\s+(\d+)")
            total = _first_int(raw, r"^#\s*tests\s+(\d+)")
            if total is None and passed is not None:
                total = (passed or 0) + (failed or 0)
            result = {
                "ok": cp.returncode == 0 and not failed,
                "passed": passed, "failed": failed or 0, "total": total,
                "exit_code": cp.returncode,
                "node": node,
                "files": [p.name for p in files],
                "tap_tail": "\n".join(raw.strip().splitlines()[-14:]),
            }
        except subprocess.TimeoutExpired:
            result = {"ok": False, "error": "TIMEOUT", "exit_code": 2,
                      "passed": 0, "failed": 0, "total": 0}
    result["elapsed_s"] = round(time.time() - started, 2)
    result["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf8")
        result["json"] = str(out_path)
    except Exception as err:
        result["json_error"] = str(err)
    return result


def _first_int(text: str, pattern: str) -> int | None:
    m = re.search(pattern, text, re.M)
    return int(m.group(1)) if m else None


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    res = run()
    print("== W3 布局契约测试 ==")
    print("  node    :", res.get("node"))
    print("  tests   :", "{0} 通过 / {1} 失败 / 共 {2}".format(
        res.get("passed"), res.get("failed"), res.get("total")))
    print("  elapsed :", res.get("elapsed_s"), "s")
    print("  结论    :", "PASS" if res.get("ok") else "FAIL")
    if res.get("json"):
        print("  落盘    :", res["json"])
    if not res.get("ok") and res.get("tap_tail"):
        print("  --- TAP 尾部 ---")
        print(res["tap_tail"])
    return 0 if res.get("ok") else (2 if res.get("error") else 1)


if __name__ == "__main__":
    sys.exit(main())
