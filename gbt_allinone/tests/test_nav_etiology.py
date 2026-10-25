# gbt-capability: 导航病因钩子验收
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""nav_etiology 与「63 处吞错收口 + 5 处导航入口钩子」的验收。

这里每一条都是**挡住一次真实事故**的：
  ① 八类病因必须每类都判得出（一类判不出 = 那一维是瞎的）+ 负对照（成功路径不许被碰）
  ② **真收口判别**：`_record_swallow` 的真身必须是 `nav_etiology`，不是退回的垫片
     —— 实测事故：shim 插在 `sys.path.insert` **之前** ⇒ 导入期失败 ⇒ 静默退回垫片
     ⇒ 63 处"收口"一个病因都没真记上（**假收口**）
  ③ 吞错点必须**全部**收口：tentacle 下不许再有无收口的裸 print
  ④ 装饰器：抛错必须变成带病因的结构化失败，而不是炸穿调用方

跑法：
    $env:GBT_STORE_DIR="$env:TEMP\\gbt_test_store"; py -3.14 -m pytest gbt_allinone/tests/test_nav_etiology.py -q
"""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest

_T = Path(__file__).resolve().parents[1] / "tentacle"
if str(_T) not in sys.path:
    sys.path.insert(0, str(_T))

import nav_etiology as ne  # noqa: E402


# ─────────────────────────────────────── ① 八类病因 + 两把对照

def test_both_controls_pass():
    assert ne.selftest(verbose=False) == 0


def test_all_eight_causes_classified():
    cases = {
        "timeout": TimeoutError("timed out after 15s"),
        "element_not_found": RuntimeError("element not found"),
        "window_lost": OSError("Invalid window handle"),
        "modal_blocked": RuntimeError("blocked by dialog"),
        "denied_by_gate": PermissionError("Access is denied"),
        "backend_unavailable": ModuleNotFoundError("No module named 'uiautomation'"),
        "stale_target": RuntimeError("element is stale"),
        "action_no_effect": ValueError("whatever"),
    }
    for want, exc in cases.items():
        assert ne.classify(exc) == want, "%s 判成了 %s" % (want, ne.classify(exc))
    assert len(ne.CAUSE_KEYS) == 8
    for k in ne.CAUSE_KEYS:
        assert ne.CAUSE_CN[k] and len(ne.RETRY_HINT[k]) >= 8, "每类病因都要有中文名与重试策略"


def test_enrich_never_touches_success():
    ok = {"ok": True, "text": "hello"}
    assert ne.enrich(dict(ok), "omni_read", "read_text") == ok


def test_enrich_does_not_overwrite_existing_cause():
    r = {"ok": False, "cause": "window_lost", "error": "超时: 窗口"}
    out = ne.enrich(dict(r), "omni_window", "wait_window")
    assert out["cause"] == "window_lost", "已有的判定不许被事后猜的覆盖"


def test_enrich_maps_flags_to_causes():
    a = ne.enrich({"ok": False, "unavailable": True, "why": "no backend"}, "x", "y")
    b = ne.enrich({"ok": False, "denied": True, "why": "need scope"}, "x", "y")
    assert a["cause"] == "backend_unavailable"
    assert b["cause"] == "denied_by_gate", "被门拒绝必须判成 denied_by_gate（不许当成普通失败）"


def test_decorator_turns_raise_into_etiology():
    @ne.etiology("omni_nav_unit", "boom")
    def boom():
        raise TimeoutError("click timed out")

    r = boom()
    assert r["ok"] is False and r["cause"] == "timeout"
    assert r["evidence"]["module"] == "omni_nav_unit" and r["evidence"]["exc_type"] == "TimeoutError"


def test_decorator_passes_success_byte_for_byte():
    @ne.etiology("omni_nav_unit", "fine")
    def fine():
        return {"ok": True, "clicked": True, "n": 3}

    assert fine() == {"ok": True, "clicked": True, "n": 3}


# ─────────────────────────────────────── ② 真收口判别（挡假收口）

NAV_MODULES = ("omni_read", "omni_mouse", "omni_domain", "omni_core",
               "omni_window", "omni_web", "omni_fs", "omni_audio")
WIRED = {"omni_read": 1, "omni_window": 3, "omni_controller": 1}


@pytest.mark.parametrize("mod", NAV_MODULES)
def test_record_swallow_is_the_real_module_not_a_stub(mod):
    """**假收口判别**：真身必须是 `nav_etiology`。

    实测事故：shim 放在 `sys.path.insert` 之前 ⇒ `from nav_etiology import …` 导入期失败
    ⇒ 静默退回本地垫片 ⇒ 63 处收口**一个病因都没记上**，而表面上"收口完成"。
    这条断言就是那次事故的钉子。
    """
    m = importlib.import_module(mod)
    fn = getattr(m, "_record_swallow", None)
    assert fn is not None, "%s 没有收口函数" % mod
    assert fn.__module__ == "nav_etiology", \
        "%s 的 _record_swallow 来自 %s ⇒ 是退回的垫片，收口是假的" % (mod, fn.__module__)


@pytest.mark.parametrize("mod,count", sorted(WIRED.items()))
def test_navigation_entries_carry_etiology_hooks(mod, count):
    m = importlib.import_module(mod)
    assert getattr(m, "_etiology", None) is not None
    assert getattr(m, "_etiology").__module__ == "nav_etiology"
    src = (_T / (mod + ".py")).read_text(encoding="utf-8-sig")
    assert len(re.findall(r"@_etiology\(", src)) == count, \
        "%s 应挂 %d 个病因钩子" % (mod, count)


# ─────────────────────────────────────── ③ 吞错必须全部收口

def test_no_bare_swallow_print_remains():
    """tentacle 下不许再有**无收口**的裸 print —— 吞错要么不收，要么带病因记下来。"""
    pat = re.compile(r'print\(f"⚠️\s*\w+:\s*吞错:\s*\{_?e\}",\s*file=')
    left = []
    for p in sorted(_T.glob("*.py")):
        txt = p.read_text(encoding="utf-8-sig")
        # 垫片内部那一行是允许的（模块不可用时的兜底），其余一律不许
        for i, line in enumerate(txt.splitlines(), 1):
            if pat.search(line) and "_record_swallow" not in txt.splitlines()[max(0, i - 6):i][0]:
                in_shim = any("def _record_swallow(" in l for l in txt.splitlines()[max(0, i - 4):i])
                if not in_shim:
                    left.append("%s:%d" % (p.name, i))
    assert left == [], "仍有未收口的裸吞错：%s" % left[:6]


def test_swallow_actually_records_a_cause():
    """收口之后，账本里必须真的多出一条**带病因**的记录。"""
    ne.clear()
    ne.record_swallow(TimeoutError("unit-test timeout"), "omni_unit", "op_x")
    s = ne.stats()
    assert s["total"] == 1
    assert s["by_cause"]["timeout"]["n"] == 1
    assert s["by_module"] == {"omni_unit": 1}
    assert s["unknown_causes"] == []
    rows = ne.ledger()["rows"]
    assert rows[0]["exc_type"] == "TimeoutError" and rows[0]["module"] == "omni_unit"
    ne.clear()


# ─────────────────────────────────────── ④ 真实导航入口（活体）

def test_live_navigation_failure_carries_cause():
    """拿**真实**导航原语验：失败必须带病因。

    后端不可用时允许判成 backend_unavailable —— 那也是**正确的病因**，
    因为"没有后端"本来就不是"没找到元素"。这里不许把两种病混成一种。
    """
    from omni_tentacle import OmniTentacle
    ne.clear()
    t = OmniTentacle()
    r = t.wait_text("绝不存在的文字XYZQW", 0.2)
    assert r["ok"] is False
    assert r.get("cause") in ("timeout", "backend_unavailable", "element_not_found"), r
    assert r.get("retry_hint"), "带病因就必须带重试策略"
    assert r.get("evidence", {}).get("module") == "omni_read"
    w = t.wait_window("绝不存在的窗口XYZQW", 0.2)
    assert w["ok"] is False and w.get("cause") in ("timeout", "window_lost", "backend_unavailable")
    assert ne.stats()["total"] >= 1, "失败发生了却没进病因账"
    ne.clear()
