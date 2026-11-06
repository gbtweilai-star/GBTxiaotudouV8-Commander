# -*- coding: utf-8 -*-
"""能力登记强制规则 · 契约（R121）。

守的三件事：
  ① caps_registry 的 handler 字段必须与真实分派键（cap 名）一致；
  ② 面板出口清单（holo_pet_w3/shell/main.cjs 的 TOOLS_CAPS）不得引用不存在的能力，
     登记指针（caps_registry.py:NNN）必须真的指向该项；
  ③ 灰态必须有原因——面板可点的每个动作，非 live 状态必须给出理由，
     或显式登记为「运行时按实测填充」。

为什么要有这层：能力库存（caps_registry）与面板货架（TOOLS_CAPS）此前是两张手抄表，
写功能的人不挂出口、挂出口的人没有统一清单，于是"能力越堆越多、界面一动不动"。
本契约把两表钉在一起；纯静态检查，不联网、不写盘。
"""
import ast
import re
import unittest
from pathlib import Path

from .. import caps_registry as CR

ROOT = Path(__file__).resolve().parents[2]
MAIN_CJS = ROOT / "holo_pet_w3" / "shell" / "main.cjs"
INDEX_HTML = ROOT / "holo_pet_w3" / "index.html"
WINDOW_JS = ROOT / "holo_pet_w3" / "window.js"
REGISTRY_PY = ROOT / "gbt_allinone" / "caps_registry.py"
API_PY = ROOT / "gbt_allinone" / "api.py"

# 静态 reason 允许留空、由运行时按实测填充的动作（面板 w3Tools 里的 draftReason）。
RUNTIME_FILLED_REASONS = {("coze_mail", "draft")}
VALID_STATES = ("live", "pending", "not_mounted")


def _registry_lines():
    return REGISTRY_PY.read_bytes().decode("utf-8-sig").splitlines()


def _parse_exit_list(text):
    start = text.find("const TOOLS_CAPS")
    end = text.find("];", start)
    if start < 0 or end < 0:
        raise AssertionError("main.cjs 里找不到 TOOLS_CAPS 出口清单")
    block = text[start:end]
    rows = []
    for chunk in re.split(r"\n  \{", block)[1:]:
        cap_m = re.search(r'cap:\s*"([a-z_0-9]+)"', chunk)
        reg_m = re.search(r'registered:\s*"caps_registry\.py:(\d+)"', chunk)
        if not (cap_m and reg_m):
            continue
        actions = []
        for a_m in re.finditer(
                r'\{\s*name:\s*"([a-z_0-9]+)",\s*state:\s*"([a-z_]+)",'
                r'\s*reason:\s*"(.*?)"\s*\}', chunk, re.S):
            actions.append({"name": a_m.group(1), "state": a_m.group(2),
                            "reason": a_m.group(3).strip()})
        rows.append({"cap": cap_m.group(1), "line": int(reg_m.group(1)),
                     "actions": actions})
    if not rows:
        raise AssertionError("TOOLS_CAPS 解析结果为空——解析器或清单已失效")
    return rows


def _check_handler_convention(caps):
    bad = [c for c, m in caps.items() if m.get("handler") != c]
    if bad:
        raise AssertionError(
            "handler 字段与分派键不一致（api.py 按 cap 名分派，字段是元数据，"
            "必须写真名）：%s" % sorted(bad))


def _check_exit_rows(rows, caps, registry_lines):
    """逐条核对出口清单，**一次把问题报全**。

    🔴 2026-09-22 第 35 轮改（错报治理）：原来是"遇到第一个坏指针就 raise"，
    实测后果：注册表被插入 24 行后，`prompt_bridge` / `coze_mail` / `create` **三个**指针
    同时失效，而这条判据每次只喊一个 —— 于是"修一个、再跑、又红一个"，
    修的人被引进打地鼠，还会以为"只有一条坏了"。
    **读数不完整本身就是错报**：判据的职责是把当下全部不合格项交出来，
    不是替跑的人决定"先看哪一条"。
    """
    errs = []

    def bad(msg):
        errs.append(msg)

    for row in rows:
        cap = row["cap"]
        if cap not in caps:
            bad("出口清单引用了未登记能力：%s" % cap)
            continue
        line_no = row["line"]
        if not (1 <= line_no <= len(registry_lines)):
            bad("%s 登记指针越界：%s" % (cap, line_no))
            continue
        line = registry_lines[line_no - 1]
        if ('"%s": {' % cap) not in line:
            # 顺手把**真实行号**找出来：光说"错了"等于把活儿推回给读的人。
            real = [i for i, l in enumerate(registry_lines, 1) if ('"%s": {' % cap) in l]
            hint = ("应为 %s" % real[0]) if real else "注册表里找不到该项（该删这一行）"
            bad("%s 登记指针失效：caps_registry.py:%d 实际是 %r ⇒ %s"
                % (cap, line_no, line.strip()[:60], hint))
        if not row["actions"]:
            bad("%s 一个动作都没登记" % cap)
        for act in row["actions"]:
            if act["state"] not in VALID_STATES:
                bad("%s.%s 状态非法：%r" % (cap, act["name"], act["state"]))
            elif act["state"] != "live" and not act["reason"] \
                    and (cap, act["name"]) not in RUNTIME_FILLED_REASONS:
                bad("%s.%s 是灰态却没有原因（不许只灰不解释）" % (cap, act["name"]))

    if errs:
        raise AssertionError("出口清单 %d 处不合格：\n  - %s"
                             % (len(errs), "\n  - ".join(errs)))


class TestHandlerMetadata(unittest.TestCase):
    def test_handler_matches_dispatch_key(self):
        """handler 必须等于 cap 名——它是给人看的真名，不是第二个分派表。"""
        _check_handler_convention(CR.BENIGN_CAPS)

    def test_handler_convention_has_teeth(self):
        """判别性负对照：合成一条 handler 漂移，校验器必须红。"""
        with self.assertRaises(AssertionError):
            _check_handler_convention({"probe": {"handler": "placeholder"}})


def _dispatch_rows(api_py: Path):
    """收集 `api.py` 里 `if kind ...` 的 (cap, If 节点)。

    只认 **If 语句**：`... if kind == "x" else ...` 这类行内三元不是分支，
    否则会把 `omission_detector` 这种正常写法误报成两条分支。
    """
    tree = ast.parse(api_py.read_text(encoding="utf-8"))
    parent = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node
    rows = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name)
                and test.left.id == "kind"):
            continue
        kinds = []
        for op, comp in zip(test.ops, test.comparators):
            if isinstance(op, ast.Eq) and isinstance(comp, ast.Constant) \
                    and isinstance(comp.value, str):
                kinds.append(comp.value)
            elif isinstance(op, ast.In) and isinstance(comp, (ast.Tuple, ast.List, ast.Set)):
                kinds += [e.value for e in comp.elts
                          if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        for k in kinds:
            rows.append((k, node))
    return rows, parent


def _duplicate_dispatch(api_py: Path):
    """同一个 cap 落在两条**互不嵌套**的 if 上 ⇒ 两套实现，后一条是死代码。

    合法的嵌套写法（外层 `if kind in (...)` 里再 `if kind == "x"`）不算重复；
    被它抓的是 2026-11-06 那种整段粘贴：12 位红队分派在 api.py 里出现了两次。
    """
    rows, parent = _dispatch_rows(api_py)
    by_kind = {}
    for k, node in rows:
        by_kind.setdefault(k, []).append(node)

    def _is_ancestor(a, b) -> bool:
        cur = b
        while cur in parent:
            cur = parent[cur]
            if cur is a:
                return True
        return False

    dups = {}
    for k, nodes in by_kind.items():
        for i, a in enumerate(nodes):
            for b in nodes[i + 1:]:
                if _is_ancestor(a, b) or _is_ancestor(b, a):
                    continue
                dups.setdefault(k, sorted({a.lineno, b.lineno}))
    return dups


def _duplicate_literal_keys(registry_py: Path):
    """BENIGN_CAPS 字典**字面量**里重复出现的键 → {名字: [行号, 行号]}。

    只数 ast.Dict.keys，不看 exec 后的结果：Python 对重复键静默取后者，
    `len(ast keys)` 会大于 `len(dict)`，这正是"一个能力两处定义"的指纹。
    """
    tree = ast.parse(registry_py.read_bytes().decode("utf-8-sig"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", None) == "BENIGN_CAPS" for t in node.targets):
            seen = {}
            for k in node.value.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    seen.setdefault(k.value, []).append(k.lineno)
            return {n: lns for n, lns in seen.items() if len(lns) > 1}
    raise AssertionError("caps_registry.py 里找不到 BENIGN_CAPS 字面量")


class TestDispatchUniqueness(unittest.TestCase):
    def test_one_cap_one_branch(self):
        """一个能力位只许有一条分派分支。

        血账（2026-11-06）：12 位授权红队分派被整段粘了两遍，前一条永远先命中、
        后一条是死代码 —— 改错一条就"看起来有两个版本"，而且改的是不生效的那条。
        """
        dups = _duplicate_dispatch(API_PY)
        self.assertFalse(dups, "同一能力位出现多条分派分支：%s" % dups)

    def test_dispatch_uniqueness_has_teeth(self):
        """判别性负对照：合成两条同 kind 的平级分支，校验器必须红。"""
        import tempfile
        import textwrap
        src = textwrap.dedent("""
            def run_task(kind):
                if kind == "probe":
                    return 1
                if kind in ("probe", "other"):
                    return 2
                return 0
        """)
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(src)
            tmp = Path(fh.name)
        try:
            dups = _duplicate_dispatch(tmp)
        finally:
            tmp.unlink()
        self.assertEqual(dups, {"probe": [3, 5]})


class TestRegistryNoDuplicateKeys(unittest.TestCase):
    """BENIGN_CAPS 字面量里一个能力名只许出现一次。

    血账（2026-11-06）：`caps_registry.py` 末尾又"补登"了 4 个能力位
    （body_realtime / vision_grounding / vision_arsenal / ocr），与前面的定义
    逐字相同。Python 字典字面量遇到重复键**静默取后者**，不报错也不警告：
    文件里 ast 数出 431 个键，实际 dict 只有 427 个 —— 一个能力两处定义，
    改前面那处等于没改，正好是"看起来只有一个能力、其实是两个版本"。
    registry 是 427 位的唯一真源，重复键本身就说明有人"在末尾补一遍"
    而不是去改原位。
    """

    def test_no_duplicate_keys_in_registry_literal(self):
        dups = _duplicate_literal_keys(REGISTRY_PY)
        self.assertFalse(
            dups, "能力位在字典字面量里写了多遍（去改原位，别在末尾补）：%s" % dups)

    def test_duplicate_key_checker_has_teeth(self):
        """判别性负对照：合成一份带重复键的注册表，校验器必须红。"""
        import tempfile
        import textwrap
        src = textwrap.dedent("""
            BENIGN_CAPS = {
                "alpha": {"domain": "x", "handler": "alpha"},
                "beta": {"domain": "x", "handler": "beta"},
                "alpha": {"domain": "x", "handler": "alpha"},
            }
        """)
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(src)
            tmp = Path(fh.name)
        try:
            dups = _duplicate_literal_keys(tmp)
        finally:
            tmp.unlink()
        self.assertEqual(dups, {"alpha": [3, 5]})

    def test_registry_has_427_unique_caps(self):
        """427 是契约：字面量键数必须等于去重后的能力数。"""
        self.assertEqual(len(CR.BENIGN_CAPS), 427)
        self.assertFalse(_duplicate_literal_keys(REGISTRY_PY))


class TestNoVersionFragments(unittest.TestCase):
    """活代码目录里不许留同一份源码的旧副本。

    血账（2026-11-06）：`gbt_allinone/` 下 11 个模块各带 1~2 个 `.prev/.bak`，
    外加 4 份能力清单快照 —— Python 不会 import 它们，所以**跑得通**；
    但改的人会改到旧副本上，然后疑惑"为什么改了没生效"。已整体挪到
    `.archive/versions/2026-11-06/`（只移动、不删除）。
    """

    LIVE_DIRS = ("gbt_allinone", "tools", "holo_pet_w3")
    SKIP = {"__pycache__", "store", "node_modules", ".archive", "state", "outputs"}

    def test_no_prev_or_bak_in_live_code(self):
        bad = []
        for d in self.LIVE_DIRS:
            base = ROOT / d
            if not base.is_dir():
                continue
            for p in base.rglob("*"):
                if not p.is_file():
                    continue
                if set(p.relative_to(ROOT).parts) & self.SKIP:
                    continue
                n = p.name
                if n.endswith((".prev", ".orig", ".rej")) or ".bak" in n:
                    bad.append(p.relative_to(ROOT).as_posix())
        self.assertFalse(bad, "活代码目录里还有旧版本残片（挪到 .archive 再改）：%s" % bad)


class TestPanelExitList(unittest.TestCase):
    def test_exit_list_matches_registry(self):
        rows = _parse_exit_list(MAIN_CJS.read_bytes().decode("utf-8"))
        _check_exit_rows(rows, CR.BENIGN_CAPS, _registry_lines())
        self.assertGreaterEqual(len(rows), 1)

    def test_exit_list_validator_has_teeth(self):
        caps = {"probe": {"handler": "probe"}}
        lines = ["", '    "probe": {']
        good = [{"cap": "probe", "line": 2,
                 "actions": [{"name": "status", "state": "live", "reason": ""}]}]
        _check_exit_rows(good, caps, lines)          # 正对照：必须通过
        cases = [
            ("未知能力", [{"cap": "ghost", "line": 2, "actions": [
                {"name": "status", "state": "live", "reason": ""}]}]),
            ("指针失效", [{"cap": "probe", "line": 1, "actions": [
                {"name": "status", "state": "live", "reason": ""}]}]),
            ("状态非法", [{"cap": "probe", "line": 2, "actions": [
                {"name": "status", "state": "maybe", "reason": "x"}]}]),
            ("灰态无原因", [{"cap": "probe", "line": 2, "actions": [
                {"name": "status", "state": "pending", "reason": ""}]}]),
        ]
        for label, bad in cases:
            with self.subTest(label=label):
                with self.assertRaises(AssertionError):
                    _check_exit_rows(bad, caps, lines)


class TestPanelWiring(unittest.TestCase):
    def test_tools_tab_is_wired_end_to_end(self):
        html = INDEX_HTML.read_bytes().decode("utf-8")
        js = WINDOW_JS.read_bytes().decode("utf-8")
        main = MAIN_CJS.read_bytes().decode("utf-8")
        self.assertIn('data-view="tools"', html)
        self.assertIn('id="view-tools"', html)
        self.assertIn('callBridge("tools")', js)
        self.assertIn('ipcMain.handle("w3:tools"', main)
        self.assertIn("function w3Tools(", main)


if __name__ == "__main__":
    unittest.main(verbosity=2)
