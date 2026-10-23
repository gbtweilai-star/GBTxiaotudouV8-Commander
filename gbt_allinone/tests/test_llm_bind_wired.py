"""三能力位「触手双向绑定」点名判据 —— key_gateway / multimodal_port / genoffice_bridge。

主人令（2026-09-27）：「**从现在开始不管新增能力全部都要与触手双向绑定**，确保触手随时
使用**不会有故障和断连**，以及**都没实现却都没记录**必须时刻随时都能感知到框架的所有状态。」

────────────────────────────────────────────────────────────────────
本文件补的是**既判据补不上的那一格** —— 为什么必须另立一条：

  `tests/test_cap_bind_bidirectional.py` 判 A/B/C/D 四面，但它**只遍历 `BENIGN_CAPS`**。
  没注册进注册表的模块，它**看不见，因而不会红**。

  实测（2026-09-28 修前，一手读数）：
    · 三模块在「注册表 / api.py 分派 / 图鉴 / unimplemented」四处**全部为 0**；
    · `python tools/framework_state.py` 照样打 **`✅ 全绿`**（`registry=202 · undispatched=[]`）；
    · `test_cap_bind_bidirectional` 照样 **`Ran 5 tests · OK`**；
    · 而 `run_task("key_gateway", {...})` 的真实返回是
      **`unknown capability（没有这个能力位名）`** —— **触手根本叫不出来**。
    （尤其荒唐的一条：`genoffice_bridge` 被邻近匹配建议成 `genoffice`。）

  ⇒ 「判据全绿」在这里**既非必要、也非充分**。死角不是不会，是**不会还不说**
    （`docs/触手覆盖矩阵.md:32`）。
  ⇒ 故本文件把三个名字**写死**（不从句柄、从注册表反推），做成**点名判据**：
    谁撤了注册 / 撤了分派 / 撤了图鉴条目 / 摘了写类的门，这里**当场红**。
  ⇒ 另配**合成负对照**（`test_checker_has_teeth`），证明这把尺子真会咬 ——
    照 `test_capability_registry.TestHandlerMetadata.test_handler_convention_has_teeth` 的先例：
    "0 条不合格"只有在"尺子能报出不合格"时才成立。

────────────────────────────────────────────────────────────────────
口径（三处，都是硬约束，不商量）：

  · **注册是硬前提**：`api.py::_run_task_core_body` 第 1772 行 `if kind not in BENIGN_CAPS`
    直接回 "unknown capability" ⇒ 没登记 = 触手无权调用（不只是"没记录"）。
  · **作用域挂 cap 边界**：写类/出网类的门声明在 `security/policy.py::evaluate`，
    与本域既有口径一致（`llm/unified.py::status()` 的 `gate` 字段：
    "external_llm 人工授权门装在 cap 边界"）。**不在模块里自挂第二道闸**
    —— 同一件事两处真相，迟早漂移。
  · **`evaluate()` 对未列出的 kind 是 fail-open**（`scopes=()` ⇒ 不 restricted ⇒ 放行）
    ⇒ 只注册名字而不声明作用域，等于让新位**带着写盘与出网能力裸奔**
    ⇒ 故本判据把"写类必须收口"也钉进来。
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ⚠️ 点名清单：**写死**，不从注册表反推（反推就又会漏掉"没注册"的那一格）。
_NAMES = ("key_gateway", "multimodal_port", "genoffice_bridge")

# 读类 op：必须零作用域（只读、不落盘、不外发、不铸钥）。
_READ_OPS = {
    "key_gateway": ("status", "whoami", "energy", "plan", "keys", "compat",
                    "mask", "classify", "verify", "selftest"),
    "multimodal_port": ("status", "port", "catalog", "redlines", "selftest"),
    "genoffice_bridge": ("status", "probe"),
}
# 写类 / 出网类 op：必须**至少**收口到这些作用域之一（不收口即裸奔）。
_GATED_OPS = {
    "key_gateway": {
        "mint": ("filesystem_write",), "revoke": ("filesystem_write",),
        "note": ("filesystem_write",), "reset": ("filesystem_write",),
        "materialize": ("external_llm",),
    },
    "multimodal_port": {"probe": ("external_llm",)},
    "genoffice_bridge": {
        "selftest": ("filesystem_write", "network_private", "external_llm"),
    },
}


def _gaps(names) -> dict:
    """逐名字查四处互锁；返回 {名字: [缺口…]}，缺口为空 = 该名字四处齐。

    判据**与框架读数同源**（`tools/framework_state.py` 的 A 面口径），不另造第二套逻辑：
      · 正向：`caps_registry` 登记 · `api.py` 有分派 · 图鉴收录；
      · 反向：名字在触手有效标签里（能绑、能用）。
    """
    from gbt_allinone.caps_registry import BENIGN_CAPS
    src = (ROOT / "gbt_allinone" / "api.py").read_text(encoding="utf-8")
    atlas = json.loads((ROOT / "state" / "skill_atlas.json").read_text(encoding="utf-8"))
    atlas_kinds = {c.get("kind") for c in (atlas.get("caps") or [])}

    labels = set()
    try:
        import importlib.util as _iu
        sp = _iu.spec_from_file_location("tb_probe", ROOT / "tools" / "tentacle_bind.py")
        tb = _iu.module_from_spec(sp)
        sp.loader.exec_module(tb)
        labels = set(tb._valid_labels() or [])
    except Exception as e:                                          # noqa: BLE001
        labels = set()
        _labels_err = "%s: %s" % (type(e).__name__, e)
    else:
        _labels_err = None

    out = {}
    for n in names:
        g = []
        if n not in BENIGN_CAPS:
            g.append("未注册 caps_registry.BENIGN_CAPS（⇒ run_task 会回 unknown capability）")
        elif str((BENIGN_CAPS.get(n) or {}).get("handler") or "") != n:
            g.append("handler 字段与能力位名不一致（契约 test_handler_matches_dispatch_key）")
        if not (re.search(r'kind\s*==\s*"%s"' % re.escape(n), src)
                or re.search(r'kind\s+in\s+\([^)]*"%s"' % re.escape(n), src)):
            g.append("api.py 无分派分支")
        if n not in atlas_kinds:
            g.append("图鉴 state/skill_atlas.json 未收录")
        if _labels_err:
            g.append("触手字典读不出：%s" % _labels_err)
        elif labels and n not in labels:
            g.append("触手有效标签里叫不出这个名字（反向绑定断）")
        out[n] = g
    return out


class TestThreeCapsAreBidirectionallyBound(unittest.TestCase):
    """三个名字必须四处互锁齐 —— 一处不齐即红。"""

    def test_all_four_points_are_wired(self):
        gaps = _gaps(_NAMES)
        bad = {k: v for k, v in gaps.items() if v}
        self.assertFalse(
            bad,
            "以下能力位与触手**未双向绑定**（不许无声挂着）：\n  - "
            + "\n  - ".join("%s：%s" % (k, "；".join(v)) for k, v in bad.items())
            + "\n修法：caps_registry 注册 + api.py 分派 + 重建图鉴"
              "（python tools/codex-scripts/omni.py build）；"
              "暂时做不出来就登记 state/unimplemented.json（有名有姓 + 谁有权修）")

    def test_registered_as_unsafe_and_not_claiming_safe(self):
        """三处都有写类/出网 op ⇒ **必须** safe: False（否则面板/入口会代调）。"""
        from gbt_allinone.caps_registry import BENIGN_CAPS
        for n in _NAMES:
            with self.subTest(cap=n):
                self.assertIn(n, BENIGN_CAPS)
                self.assertIs(BENIGN_CAPS[n].get("safe"), False,
                              "%s 有写类/出网 op，safe 不许标 True（面板会据此代调）" % n)
                self.assertEqual(BENIGN_CAPS[n].get("domain"), "llm")

    def test_not_listed_as_unimplemented(self):
        """它们是**已实现**的：不许出现在"只有名字没实现"的登记表里。"""
        p = ROOT / "state" / "unimplemented.json"
        und = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
        kinds = {i.get("kind") for i in (und.get("items") or [])}
        for n in _NAMES:
            with self.subTest(cap=n):
                self.assertNotIn(n, kinds, "%s 有实现，却登记成未实现" % n)


class TestCallableFromTentacle(unittest.TestCase):
    """不只看登记 —— **真叫一次**，确认返回的不是 unknown capability。"""

    def test_status_is_reachable_and_not_unknown(self):
        from gbt_allinone import api
        for n in _NAMES:
            with self.subTest(cap=n):
                r = api.run_task(n, {"op": "status"}, probe=True)
                msg = json.dumps(r, ensure_ascii=False)
                self.assertNotIn("unknown capability", msg,
                                 "%s 被触手叫成未知能力（注册或分派缺一格）" % n)
                self.assertEqual(r.get("status"), "ok",
                                 "%s op=status 没跑通：%s" % (n, msg[:200]))


class TestGateIsMountedAtCapBoundary(unittest.TestCase):
    """读类零作用域 · 写类/出网必须收口 · 未知 op fail-closed。

    为什么这条重要：`policy.evaluate()` 对**未列出的 kind 是 fail-open**
    （`scopes=()` ⇒ 不 restricted ⇒ `authorize()` 放行）。只注册名字不声明作用域，
    新位就带着写盘与出网能力裸奔 —— 仓内"读类直连、写类过门"的收口在此处失守。
    """

    def test_read_ops_are_zero_scope(self):
        from gbt_allinone.security import policy as P
        for n, ops in _READ_OPS.items():
            for op in ops:
                with self.subTest(cap=n, op=op):
                    d = P.evaluate(n, {"op": op})
                    self.assertEqual(
                        list(d.scopes), [],
                        "%s op=%s 是读类，不该挂作用域（挂了会拦掉正常只读调用）" % (n, op))

    def test_write_and_net_ops_are_gated(self):
        from gbt_allinone.security import policy as P
        for n, ops in _GATED_OPS.items():
            for op, need in ops.items():
                with self.subTest(cap=n, op=op):
                    got = set(P.evaluate(n, {"op": op}).scopes)
                    missing = set(need) - got
                    self.assertFalse(
                        missing,
                        "%s op=%s 未收口，缺作用域 %s（got=%s）—— 写盘/出网裸奔"
                        % (n, op, sorted(missing), sorted(got)))

    def test_unknown_op_fails_closed(self):
        """未列出的 op 不许当只读放行 —— 将来加写动作时不能被静默放过。"""
        from gbt_allinone.security import policy as P
        for n in _NAMES:
            with self.subTest(cap=n):
                self.assertTrue(
                    P.evaluate(n, {"op": "__definitely_not_an_op__"}).scopes,
                    "%s 的未知 op 被当只读放行（fail-open）—— 新写动作会裸奔" % n)


class TestCheckerHasTeeth(unittest.TestCase):
    """判别性负对照：喂一个**不存在**的名字，尺子必须报出来。

    照 `test_handler_convention_has_teeth` 的先例 —— 没有这一条，
    「四处齐」可能只是"尺子瞎了"。
    """

    def test_synthetic_missing_name_is_reported(self):
        gaps = _gaps(["zz_definitely_not_a_real_cap"])
        self.assertTrue(gaps["zz_definitely_not_a_real_cap"],
                        "尺子对不存在的名字都说'齐' ⇒ 这把尺子恒真，测不出任何东西")

    def test_synthetic_name_reports_all_three_positive_points(self):
        """缺的格子要**逐条**报出来（不是只回一句"不合格"）。"""
        g = _gaps(["zz_definitely_not_a_real_cap"])["zz_definitely_not_a_real_cap"]
        joined = " | ".join(g)
        for expect in ("未注册", "api.py 无分派", "未收录"):
            self.assertIn(expect, joined,
                          "缺口读数不全，漏报「%s」；实得：%s" % (expect, joined))


if __name__ == "__main__":
    unittest.main()
