"""call_graph 验收：跨文件调用图 + 四条不许越的线。

重点不在"能建图"，而在**几条诚实性断言**：
  ① 跨文件 import 解析真的通（不是只在本模块里找）
  ② **多解一律不认**（重名不许瞎接主人）
  ③ **Python 内建名不认**（`len` 不许接到我们同名的符号上）
  ④ `dead_code` 分两桶：**按名派单的（名字出现在字符串里）必须进 suspect，不许当 dead**

跑法：
    $env:GBT_STORE_DIR="$env:TEMP\\gbt_test_store"; py -3.14 -m pytest gbt_allinone/tests/test_call_graph.py -q
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_T = Path(__file__).resolve().parents[1] / "tools" / "call_graph.py"


def _load():
    spec = importlib.util.spec_from_file_location("_cg_test", str(_T))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_cg_test"] = mod      # 3.14 dataclass 需要模块在 sys.modules 里
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def repo(tmp_path):
    """造一个小仓，把每条规则都摆一个用例进去。"""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    # a.py：三个函数，helper 被 alpha 调；genuinely_dead 无人调且名字不出现在任何字符串里
    (tmp_path / "pkg" / "a.py").write_text(
        "def helper():\n    return 1\n\n"
        "def alpha():\n    return helper()\n\n"
        "def genuinely_dead():\n    return 2\n\n"
        "def dispatched_by_name():\n    return 3\n",
        encoding="utf-8")
    # b.py：跨文件 from-import 后调用；再放一个同名符号制造"多解"
    (tmp_path / "pkg" / "b.py").write_text(
        "from pkg.a import helper, alpha\n\n"
        "def beta():\n    return alpha() + helper()\n\n"
        "def helper():\n    return 99\n",
        encoding="utf-8")
    # c.py：类内 self.m()；以及一个叫 len 的同名符号（**放在这个模块里，故意遮蔽内建**）
    (tmp_path / "pkg" / "c.py").write_text(
        "class K:\n"
        "    def m(self):\n        return 1\n"
        "    def n(self):\n        return self.m()\n\n"
        "def len(x):\n    return 0\n",
        encoding="utf-8")
    # g.py：**本模块没有定义 len** ⇒ 这里的 len() 是内建，绝不许接到 pkg.c::len 上
    (tmp_path / "pkg" / "g.py").write_text(
        "def use_builtin():\n    return len([1, 2])\n", encoding="utf-8")
    # d.py：按名派单 —— dispatched_by_name 只出现在字符串里
    (tmp_path / "pkg" / "d.py").write_text(
        'REGISTRY = {"x": {"handler": "dispatched_by_name"}}\n',
        encoding="utf-8")
    return _load(), tmp_path


def test_cross_file_import_resolution(repo):
    """① 跨文件：b.beta 调 a.alpha / a.helper 必须解析出来。"""
    cg, root = repo
    g = cg.build(root)
    edges = {(c, t) for c, t, _ in cg.all_edges(g)}
    assert ("pkg.b::beta", "pkg.a::alpha") in edges, "跨文件 from-import 没解析出来"
    # b.py 自己也定义了 helper ⇒ 同名 ⇒ 多解 ⇒ 按唯一性那条不该认，但 import 绑定是明确的
    assert ("pkg.b::beta", "pkg.a::helper") in edges, \
        "import 绑定是明确的（from a import helper），不该被本地同名遮蔽"


def test_same_class_self_method(repo):
    """self.m() 要接到本类方法上。"""
    cg, root = repo
    g = cg.build(root)
    edges = {(c, t) for c, t, _ in cg.all_edges(g)}
    assert ("pkg.c::K.n", "pkg.c::K.m") in edges


def test_builtin_name_is_never_claimed(repo):
    """③ 内建名不认：**本模块没定义 len** 时，`len([1,2])` 绝不许接到别处那个同名符号上。

    （注：如果本模块自己 `def len`，那 Python 语义上就是调它自己 —— 那种遮蔽是**对的**，
      所以这个用例把 use_builtin 放在没有定义 len 的 pkg/g.py 里。）
    """
    cg, root = repo
    g = cg.build(root)
    edges = {(c, t) for c, t, _ in cg.all_edges(g)}
    assert ("pkg.g::use_builtin", "pkg.c::len") not in edges, \
        "把内建 len 接到了别处的同名符号上 —— 这就是「猜」，不许"
    assert any(c == "pkg.g::use_builtin" and raw == "len"
               for c, raw, _ in g.unresolved), "内建调用应当留在 unresolved 里"


def test_local_shadowing_builtin_is_resolved(repo):
    """反过来也要对：**本模块自己 def 了 len**，那 `len()` 就是调它自己 —— Python 语义如此。"""
    (repo[1] / "pkg" / "h.py").write_text(
        "def len(x):\n    return 0\n\ndef caller():\n    return len([1])\n", encoding="utf-8")
    cg, root = repo
    g = cg.build(root)
    edges = {(c, t) for c, t, _ in cg.all_edges(g)}
    assert ("pkg.h::caller", "pkg.h::len") in edges


def test_ambiguous_name_stays_unresolved(repo):
    """② 多解不认：全仓有两个 helper 时，无法 import-aware 解析的调用必须留在 unresolved。"""
    (repo[1] / "pkg" / "e.py").write_text(
        "def outer():\n    return obj.helper()\n", encoding="utf-8")
    cg, root = repo
    g = cg.build(root)
    raws = [raw for _, raw, _ in g.unresolved]
    assert "obj.helper" in raws, "重名情形下应当拒绝解析，而不是挑一个接上"


def test_dead_code_splits_two_buckets(repo):
    """④ 死代码分两桶：真死的 vs 名字出现在字符串里的（按名派单）。"""
    cg, root = repo
    g = cg.build(root)
    d = cg.dead_code(g)
    dead = {x["symbol"] for x in d["dead"]}
    suspect = {x["symbol"] for x in d["suspect"]}
    assert "pkg.a::genuinely_dead" in dead, "真·无人调用、名字也不在任何字符串里 ⇒ 该进 dead"
    assert "pkg.a::dispatched_by_name" in suspect, \
        "名字出现在 REGISTRY 字符串里 ⇒ 必须进 suspect（可能是按名派单），不许当 dead"
    assert "pkg.a::dispatched_by_name" not in dead


def test_callers_and_callees(repo):
    cg, root = repo
    g = cg.build(root)
    cal = cg.callers(g, "alpha")
    assert cal["ok"] and any("beta" in c["symbol"] or c["callers"] for c in cal["results"])
    ce = cg.callees(g, "beta")
    assert ce["ok"]
    assert any("alpha" in t for r in ce["results"] for t in r["callees"])


def test_trace_reports_raw_for_verification(repo):
    """追链每一跳都要带 raw 原文 —— 人才能核对解析对不对。"""
    cg, root = repo
    g = cg.build(root)
    t = cg.trace(g, "helper", depth=2)
    assert t["ok"]
    assert all("raw" in h for h in t["hops"]), "每一跳都必须带原文写法"


def test_unknown_symbol_reports_instead_of_guessing(repo):
    cg, root = repo
    g = cg.build(root)
    r = cg.callers(g, "no_such_symbol_at_all")
    assert r["ok"] is False and "找不到符号" in r["error"]


def test_comments_do_not_create_symbols(repo):
    """注释/字符串里写函数名**不许**变成符号或边 —— AST 才作数。"""
    (repo[1] / "pkg" / "f.py").write_text(
        "# def ghost(): pass\nNOTE = 'calls ghost() everywhere'\n", encoding="utf-8")
    cg, root = repo
    g = cg.build(root)
    assert not any(s.name == "ghost" for s in g.symbols.values())
