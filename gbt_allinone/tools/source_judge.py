# gbt-capability: 源码判据（AST）—— 调用/导入了没有，不是"提到了没有"
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""源码判据器：把「提到 ≠ 用了」这条家规做成**可调用的判据**。

═══ 为什么要单独成模块 ═══
本仓反复栽在同一件事上（坑册第 34 条 / R-H170 契约 ②）：
**用文本关键词判"有没有用某个 API"** —— 一句注释、一段 docstring、一个字符串字面量，
就能让判据翻面。实测仍在犯的 3 处：

  · `security/security_brain.py:491` `"ok": "os.replace" in src` —— **安全检查**！
    一句注释就能让它报「生产区写保护机制在位」（**假绿**，而且报在最不该假的地方）
  · `ghost_guard.py:162` `if "caps_registry" in src: continue` —— 注释里提一句就被跳过，
    可能**漏掉真的私有注册表**（假阴性）
  · `tools/stigmergy.py:310` `if "locked_append_text" not in src` —— 注释里提一句就过关，
    于是"我没读到真源码"这层保护**失效**（假绿）

═══ 本模块的判据（全部走 AST，因此**天然不吃注释与字符串**）═══
  `imports_module(src, "caps_registry")`  真 import / from-import 了没有
  `calls_attr(src, "os.replace")`         真**调用**了没有（属性调用，含 os.replace(a,b)）
  `uses_name(src, "locked_append_text")`  这个名字被真**引用**了没有（调用/取值/import）
  `evidence(src, 判据…)`                  给出行号 —— **判据要能自证**

**不猜**：源码解析不了时返回 `None`（未知），**不许**折算成 False ——
"没查到"与"不存在"是两件事（本仓第 26 条）。
"""
from __future__ import annotations

import ast


def _tree(src: str):
    try:
        return ast.parse(src)
    except (SyntaxError, ValueError, RecursionError):
        return None


def _dotted(node):
    """把 Attribute/Name 链拼成 `a.b.c`；不是名字链就返回 ''。"""
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""


def imports_module(src: str, mod: str):
    """真 import / from … import 了 `mod` 吗？（`None` = 解析不了，未知）"""
    tree = _tree(src)
    if tree is None:
        return None
    want = mod.strip()
    tail = want.rsplit(".", 1)[-1]
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name == want or a.name.startswith(want + "."):
                    return True
        elif isinstance(n, ast.ImportFrom):
            base = n.module or ""
            if base == want or base.startswith(want + "."):
                return True
            # 单段名（如 `caps_registry`）：`from . import caps_registry`（module=None）
            # 与 `from gbt_allinone import caps_registry` 都必须认出来。
            # 第一版只比 `base == want.rsplit('.',1)[0]`，而单段名 rsplit 出来还是它自己 ⇒
            # 这两种写法全漏（**被本模块自己的正对照抓出来的**）。
            if "." not in want:
                if any(a.name == want for a in n.names):
                    return True
            else:
                parent, tail = want.rsplit(".", 1)
                if base.endswith(parent) and any(a.name == tail for a in n.names):
                    return True
    return False


def calls_attr(src: str, dotted: str):
    """真**调用**了 `dotted` 吗？（只认 Call 上的属性链，注释/字符串天然不算）

    `os.replace` 这种：`os.replace(a, b)` 命中；`"os.replace"`（字符串）不命中；
    `# os.replace`（注释）不命中；`os.replaced(...)` 不命中。
    """
    tree = _tree(src)
    if tree is None:
        return None
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and _dotted(n.func) == dotted:
            return True
    return False


def uses_name(src: str, name: str):
    """这个名字被真引用了吗？（调用 / 取值 / import 都算；注释与字符串不算）"""
    tree = _tree(src)
    if tree is None:
        return None
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id == name:
            return True
        if isinstance(n, ast.Attribute) and n.attr == name:
            return True
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                if (a.asname or a.name).split(".")[-1] == name:
                    return True
    return False


def lines_of(src: str, dotted: str, kind: str = "call"):
    """给出**行号证据** —— 判据要能自证，不能只回一个 True/False。"""
    tree = _tree(src)
    if tree is None:
        return None
    hits = []
    for n in ast.walk(tree):
        if kind == "call" and isinstance(n, ast.Call) and _dotted(n.func) == dotted:
            hits.append(getattr(n, "lineno", 0))
        elif kind == "import" and isinstance(n, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in n.names] + [n.module or ""]
            if any(dotted == x or x.startswith(dotted + ".") for x in names):
                hits.append(getattr(n, "lineno", 0))
        elif kind == "name" and isinstance(n, ast.Name) and n.id == dotted:
            hits.append(getattr(n, "lineno", 0))
    return sorted(set(h for h in hits if h))


def judge(src: str, dotted: str, kind: str = "call") -> dict:
    """一站式：返回 `{ok, value, evidence, unknown}`。

    `value` 可能是 `None` —— 意思是**判不了**（源码解析失败），
    调用方必须把 None 当"未知"处理，**不许**当 False。
    """
    if kind == "call":
        v = calls_attr(src, dotted)
        ev = lines_of(src, dotted, "call")
    elif kind == "import":
        v = imports_module(src, dotted)
        ev = lines_of(src, dotted, "import")
    else:
        v = uses_name(src, dotted)
        ev = lines_of(src, dotted, "name")
    return {"ok": v is True, "value": v, "evidence": ev or [],
            "unknown": v is None, "judged": "%s:%s" % (kind, dotted)}


# ───────────────────────────────────────────── 两把对照

def selftest(verbose: bool = True) -> int:
    pos = [
        ("import caps_registry", "imports_module", "caps_registry", True),
        ("from . import caps_registry", "imports_module", "caps_registry", True),
        ("from gbt_allinone import caps_registry", "imports_module", "caps_registry", True),
        ("os.replace(a, b)", "calls_attr", "os.replace", True),
        ("import os\nos.replace(x, y)", "calls_attr", "os.replace", True),
        ("locked_append_text(p, t)", "uses_name", "locked_append_text", True),
        ("from ..safe_io import locked_append_text", "uses_name", "locked_append_text", True),
    ]
    neg = [
        ("# caps_registry 在这里被提到", "imports_module", "caps_registry", False),
        ('"""os.replace 是一种原子写法"""', "calls_attr", "os.replace", False),
        ("x = 'locked_append_text'", "uses_name", "locked_append_text", False),
        ("os.replaced(a, b)", "calls_attr", "os.replace", False),
        ("caps_registry_extra()", "imports_module", "caps_registry", False),
        ("# os.replace(a, b) 被注释掉了", "calls_attr", "os.replace", False),
    ]
    bad = []
    for src, fn, arg, want in pos + neg:
        got = globals()[fn](src, arg)
        if got is not want:
            bad.append("%s(%r, %r) = %r，应为 %r" % (fn, src[:34], arg, got, want))
    # 未知不许折成 False
    unk = calls_attr("def broken(:\n", "os.replace")
    if unk is not None:
        bad.append("解析失败应回 None（未知），实回 %r ⇒ 未知被折成了判定" % unk)
    # judge 的信封
    j = judge("import os\nos.replace(1, 2)\n", "os.replace", "call")
    if not (j["ok"] and j["evidence"] == [2] and j["unknown"] is False):
        bad.append("judge 信封不对：%r" % j)
    if verbose:
        print("═══ 源码判据器 · 两把对照 ═══")
        print("正对照 %d 条 · 负对照 %d 条" % (len(pos), len(neg)))
        print("证据行号示例：%r" % (judge("import os\nos.replace(1, 2)\n", "os.replace"),))
        print("结论：%s" % ("两把对照都过 ✅" if not bad else "✗ 判红：%s" % bad))
    return 0 if not bad else 1


if __name__ == "__main__":                                     # pragma: no cover
    raise SystemExit(selftest())
