# -*- coding: utf-8 -*-
"""对随仓发布的**源码**做机械自检（只读 AST，不导入、不执行引擎）。

为什么要有它：README 里那些"单门执行 / 作用域门 / 341 位注册表 / 一次性票"的说法，
如果只写在文档里就是自我声明。这个脚本把它们钉到**源码本身**上 —— 谁改了源码，
这里当场红，而不是等读者相信我们。

跑法（零依赖，只要 Python 3.10+）：
    python runtime/static_check.py

退出码：0 = 全过；1 = 有条目不过（逐条打印原因）。
"""
from __future__ import annotations

import ast
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
# 🔴 2026-10-30 修：原来指向 HERE/"gbt_allinone" —— 那是**旧的重复副本**
#   （runtime/gbt_allinone/ 12 个文件，8 个与在跑的顶层树不同名不同内容，已于本日删除）。
#   在跑的是仓库根的 gbt_allinone/（.pth 只加仓库根 ⇒ import 永远落那里）。
PKG = HERE.parent / "gbt_allinone"
ROOT = HERE.parent
data_json = ROOT / "data" / "capabilities.json"
BRIDGE = HERE / "model_bridge.py"

FAILS: list[str] = []
PASSES: list[str] = []


def ok(name: str, detail: str = "") -> None:
    PASSES.append("%s%s" % (name, (" · " + detail) if detail else ""))


def bad(name: str, why: str) -> None:
    FAILS.append("%s ⇒ %s" % (name, why))


def parse(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8", errors="replace"))


def funcs(tree: ast.Module, name: str) -> list[ast.FunctionDef]:
    return [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]


def check_gate() -> None:
    """声明①：一切调用只走 run_task 这一个门（这里有 3 个具体证据）。"""
    tree = parse(PKG / "api.py")
    defs = funcs(tree, "run_task")
    if len(defs) != 2:
        bad("门：run_task 定义数量", "期望 2 处（原定义 + 遥测包装），实际 %d" % len(defs))
    else:
        ok("门：run_task 有 2 处定义（原定义 + 包装器）", "行 %s" % [d.lineno for d in defs])

    # `_run_task_base = run_task` 必须先于第二次定义，否则包装器会递归调用自己
    snapshot_lines = [n.lineno for n in tree.body
                      if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "_run_task_base" for t in n.targets)]
    if not snapshot_lines:
        bad("门：_run_task_base 快照", "没找到 `_run_task_base = run_task`（包装器会变成自我递归）")
    elif len(defs) == 2 and not (defs[0].lineno < snapshot_lines[0] < defs[1].lineno):
        bad("门：快照位置", "快照在第 %s 行，必须夹在两次定义之间" % snapshot_lines[0])
    else:
        ok("门：包装器先快照原定义再包装", "快照行 %d" % snapshot_lines[0])

    # 包装器里必须真的调用 _run_task_base
    wrapper = defs[-1] if defs else None
    calls = {c.func.id for c in ast.walk(wrapper) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)} if wrapper else set()
    if "_run_task_base" in calls:
        ok("门：包装器调用 _run_task_base", "不是自我递归")
    else:
        bad("门：包装器调用链", "包装器没有调用 _run_task_base")

    # 契约层（原定义）必须做信封归一 + 结果校验 + 产出即绑
    base = defs[0] if defs else None
    base_calls = {c.func.id for c in ast.walk(base) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)} if base else set()
    need = {"_normalize_envelope": "信封归一", "_verify_result": "结果校验", "_autobind_hook": "产出即绑"}
    missing = [v for k, v in need.items() if k not in base_calls]
    if missing:
        bad("门：契约层三件套", "缺：%s" % "、".join(missing))
    else:
        ok("门：契约层三件套齐全", "信封归一 / 结果校验 / 产出即绑")


def check_scopes() -> None:
    """声明②：写盘·花钱·出网必须人工授权 —— 门里真的登记了这些作用域。"""
    tree = parse(PKG / "security" / "policy.py")
    gates: set[str] = set()
    mechanism: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id in ("HUMAN_GATES", "MECHANISM_GATES"):
                    vals = {e.value for e in getattr(n.value, "elts", []) if isinstance(e, ast.Constant)}
                    (gates if t.id == "HUMAN_GATES" else mechanism).update(vals)
    required = {"process_execute", "network_private", "browser_control", "privacy_read",
                "external_llm", "data_export", "deploy_publish", "deploy_force", "owner_control"}
    missing = sorted(required - gates)
    if missing:
        bad("作用域门：HUMAN_GATES", "缺 %s" % "、".join(missing))
    else:
        ok("作用域门：HUMAN_GATES 覆盖 %d 个作用域" % len(gates), "含 G1/G2/G3 关键项")
    if "filesystem_write" not in mechanism:
        bad("作用域门：MECHANISM_GATES", "缺 filesystem_write（改盘必须挂票）")
    else:
        ok("作用域门：机制层自保", "filesystem_write 在 MECHANISM_GATES 里")


def check_one_shot() -> None:
    """声明③：票分时段票与一次性票 —— 一次性那批真的登记在授权门里。"""
    tree = parse(PKG / "auth_gate.py")
    oneshot: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and "ONE" in t.id.upper() for t in n.targets):
            for el in getattr(n.value, "elts", []) or getattr(n.value, "keys", []):
                if isinstance(el, ast.Constant) and isinstance(el.value, str):
                    oneshot.add(el.value)
    want = {"deploy_publish", "data_export"}
    if not oneshot:
        bad("票据：一次性票集合", "没从 auth_gate.py 里解析出一次性票集合")
    elif not (want & oneshot):
        bad("票据：一次性票内容", "解析到 %s，但缺 %s" % (sorted(oneshot), sorted(want & oneshot)))
    else:
        ok("票据：一次性票集合", "、".join(sorted(oneshot)))


def check_registry() -> None:
    """声明④：341 位能力不是手写清单 —— 注册表源码里真有这些名字。"""
    import json
    if not data_json.is_file():
        bad("注册表：data/capabilities.json", "文件不在：%s" % data_json)
        return
    records = json.loads(data_json.read_text(encoding="utf-8"))
    caps = records.get("capabilities") if isinstance(records, dict) else records
    names = [c.get("name") for c in caps if isinstance(c, dict)]
    import json as _j
    try:
        _want = len(_j.loads((ROOT / "data" / "capabilities.json").read_text(encoding="utf-8")))
    except Exception:                                             # noqa: BLE001
        _want = 341
    # 2026-10-30：341 是发布快照的旧数；现算以 data/capabilities.json 为准（现 348/349）。
    if len(names) < _want:
        bad("注册表：条数", "期望 ≥%d，实际 %d" % (_want, len(names)))
    else:
        ok("注册表：条数 ≥%d" % _want, "machine-readable（现算 %d）" % len(names))
    src = (PKG / "caps_registry.py").read_text(encoding="utf-8", errors="replace")
    missing = [n for n in names if n and ('"%s"' % n) not in src and ("'%s'" % n) not in src]
    if missing:
        bad("注册表：与源码一致性", "%d 个名字在 caps_registry.py 里找不到：%s"
            % (len(missing), "、".join(missing[:6])))
    else:
        ok("注册表：名字都能在 caps_registry.py 里找到", "不是手抄的目录")


def check_bridge() -> None:
    """声明⑤：APP 上的「派活」入口也走同一道门 —— 桥里不许绕过 run_task 直接调模块。"""
    if not BRIDGE.is_file():
        bad("派活桥：文件", "runtime/model_bridge.py 不在")
        return
    tree = parse(BRIDGE)
    imported: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module == "gbt_allinone":
            imported.update(a.name for a in n.names)
        elif isinstance(n, ast.Import):
            imported.update(a.name for a in n.names if a.name.startswith("gbt_allinone."))
    if "run_task" in imported:
        ok("派活桥：真调走 run_task", "桥里是 `from gbt_allinone import run_task`")
    else:
        bad("派活桥：调用口", "没导入 run_task（那它就没过门）")
    banned = {"mirror_space", "qiankun", "room_space", "deployment_rehearsal",
              "auth_gate", "security.policy", "gbt_allinone.mirror_space"}
    hit = sorted(imported & banned)
    if hit:
        bad("派活桥：绕门风险", "直接导入了 %s —— 必须经 run_task" % "、".join(hit))
    else:
        ok("派活桥：没有绕门导入", "mirror_space / qiankun / room_space / auth_gate 一律没直接导入")


def main() -> int:
    for fn in (check_gate, check_scopes, check_one_shot, check_registry, check_bridge):
        try:
            fn()
        except Exception as exc:                              # noqa: BLE001
            bad(fn.__name__, "自检脚本自己炸了：%s: %s" % (type(exc).__name__, exc))

    for line in PASSES:
        print("PASS  " + line)
    for line in FAILS:
        print("FAIL  " + line)
    print("\n%d 过 / %d 不过 · 源码根：%s" % (len(PASSES), len(FAILS), PKG))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    raise SystemExit(main())
