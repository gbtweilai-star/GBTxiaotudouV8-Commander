# -*- coding: utf-8 -*-
"""a1.art API 技能 · 带牙用例（R-H206）。

① 五原语齐且顺序对（LOOKUP→UPLOAD→GENERATE→OPTIMIZE→POLL）；
② 红线①：返回值带明文 apiKey ⇒ 拒；
③ 红线②：**只回链接不落盘 ⇒ 拒**（链接会失效）；
④ 红线③：**不调不支持的组件** ⇒ 拒；
⑤ 红线④：余额不足（810012）⇒ 如实报 + **不重试**；
⑥ 取证如实（盘上 0 命中 / 密钥未配 / 接口文档不在盘上）；
⑦ 只读骨架里不许有网络 / 写盘路径；登记在册且**落地即接线**。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import a1art_skill as a1  # noqa: E402
from gbt_allinone.tools import orchestration_kernel as ok  # noqa: E402
from gbt_allinone import caps_registry as CR  # noqa: E402


class PrimitiveTests(unittest.TestCase):
    def test_five_primitives_in_order(self):
        got = [p["key"] for p in a1.run("primitives")["primitives"]]
        self.assertEqual(got, ["lookup", "upload", "generate", "optimize", "poll"],
                         "五原语缺一即开环，顺序也不能乱")
        st = a1.run("status")
        self.assertEqual(st["type"], "external", "它是门，不是内调型")
        # R-H215：官方口径 domain = image_video（此前我们写 image，已按官方修正）
        self.assertEqual(st["domain"], "image_video")

    def test_policy_is_official(self):
        p = a1.run("policy")
        self.assertIn("3 积分/张", p["credits"])
        self.assertIn("不重试", p["error_810012"])
        self.assertIn("失效", p["link_expiry"])
        self.assertIn("逐步停止服务", p["lifecycle"])
        self.assertEqual(list(p["unsupported_components"]),
                         ["数字分身", "wordart", "合照", "Video 组件"])


class RedLineTests(unittest.TestCase):
    def test_plaintext_key_in_return_is_refused(self):
        bad = a1.assert_no_plaintext({"apiKey": "sk-a1art-abcdefghijklmnop1234"})
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["rule"], "plaintext_key_in_return")
        self.assertTrue(a1.assert_no_plaintext(
            {"key_id": "ai-image-1", "leased": True})["ok"])

    def test_link_only_result_is_refused(self):
        """红线②：只回 a1.art 链接 ⇒ 拒（生成地址会失效）。"""
        bad = a1.must_localize({"url": "https://a1.art/result/xxx.png"})
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["rule"], "link_only_result")
        good = a1.must_localize({"local_path": "store\\a1art\\out\\xxx.png"})
        self.assertTrue(good["ok"])

    def test_unsupported_components_are_refused(self):
        for comp in a1.UNSUPPORTED_COMPONENTS:
            out = a1.refuse_unsupported("调用 %s 组件" % comp)
            self.assertFalse(out["ok"], "不支持的组件必须拒：%s" % comp)
            self.assertEqual(out["rule"], "unsupported_component")
        self.assertTrue(a1.refuse_unsupported("图生图")["ok"])
        self.assertEqual(a1.refuse_unsupported("")["rule"], "missing_component")

    def test_insufficient_credit_is_reported_not_retried(self):
        out = a1.classify_error(810012)
        self.assertFalse(out["ok"])
        self.assertEqual(out["rule"], "insufficient_credit")
        self.assertFalse(out["retry"], "余额不足**不许重试**（重试只会继续烧额度）")
        self.assertEqual(a1.classify_error("")["rule"], "missing_error_code")
        self.assertTrue(a1.classify_error(0, "ok")["ok"])

    def test_lease_requires_owner_and_never_falls_back_to_env(self):
        self.assertEqual(a1.lease_key("")["rule"], "missing_owner_ai_id")
        out = a1.lease_key("ai-not-configured-xyz", tentacle_id="t-a1art")
        self.assertFalse(out["ok"], "池里没有就是没有——不许从 env 偷一份顶上")
        self.assertEqual(out["rule"], "no_key_for_owner")
        src = Path(a1.__file__).read_text(encoding="utf-8")
        for bad in ("import os", "os.environ", "getenv("):
            self.assertNotIn(bad, src, "不许有第二套密钥路径：%s" % bad)


class SkeletonTests(unittest.TestCase):
    def test_forensics_is_honest_not_dressed_up(self):
        fo = a1.run("forensics")
        self.assertEqual(fo["a1art_hits_on_disk"], 0)
        self.assertEqual(fo["key_envs_set"], 0)
        self.assertFalse(fo["a1art_dpapi_on_disk"], "保险箱里确实没有 a1art 密钥")
        self.assertFalse(fo["api_doc_on_disk"],
                         "真实接口文档不在盘上 ⇒ 不许编造 endpoint")
        self.assertNotIn("a1art", " ".join(fo["dpapi_on_disk"]).lower(),
                         "保险箱清单里不该出现 a1art（没有就是没有）")
        self.assertEqual(len(fo["dpapi_on_disk"]), 5, "现有 5 个 dpapi，如实报数")

    def test_module_has_no_network_or_write_paths(self):
        src = Path(a1.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket",
                    "import subprocess", "subprocess.run", ".write_text(",
                    ".write_bytes(", "unlink(", "shutil.copy"):
            self.assertNotIn(bad, src, "只读骨架里不该出现：%s" % bad)


class WiringTests(unittest.TestCase):
    def test_registered_as_external_gate(self):
        cap = CR.BENIGN_CAPS.get("a1art_skill")
        self.assertIsNotNone(cap, "a1.art 技能必须登记进能力注册表")
        self.assertEqual(cap["handler"], "a1art_skill")
        self.assertEqual(cap["domain"], "image_video",
                         "R-H215 起按官方口径：image_video")
        self.assertTrue(cap["safe"])

    def test_landed_then_wired_no_new_orphan(self):
        self.assertIn("a1art_skill", ok._READONLY_MODULES)
        self.assertIs(ok._READONLY_MODULES["a1art_skill"], a1)


class ApiMatrixTests(unittest.TestCase):
    """R-H211 · API 能力矩阵（**实测印证 R-H206 五原语，一条不差**）。"""

    def test_five_endpoints_match_the_five_primitives(self):
        api = a1.run("api")
        self.assertEqual([e["primitive"] for e in api["endpoints"]],
                         ["lookup", "upload", "generate", "optimize", "poll"])
        self.assertEqual([e["n"] for e in api["endpoints"]], [1, 2, 3, 4, 5])
        self.assertEqual(api["map"]["lookup"], "/open-api/v1/a1/apps/{appId}")
        self.assertEqual(api["map"]["poll"], "/open-api/v1/a1/tasks/{taskId}")
        self.assertIn("创建类", api["rule"])

    def test_endpoint_gate_whitelists_official_only(self):
        self.assertEqual(a1.check_endpoint("")["rule"], "missing_endpoint")
        self.assertEqual(
            a1.check_endpoint("https://evil.example.com/api/v1/gen")["rule"],
            "handmade_api_request", "别的域名/别的 API 一律不认")
        self.assertEqual(
            a1.check_endpoint("/open-api/v1/a1/images/delete")["rule"],
            "unknown_endpoint", "矩阵之外不认")
        self.assertEqual(
            a1.check_endpoint("/open-api/v1/a1/images/generate")["primitive"],
            "generate")
        self.assertEqual(
            a1.check_endpoint("/open-api/v1/a1/tasks/abc123")["primitive"], "poll")

    def test_lookup_is_mandatory_before_generate(self):
        self.assertEqual(a1.must_lookup_first(True, "")["rule"], "missing_app_id")
        bad = a1.must_lookup_first(False, "app-1")
        self.assertEqual(bad["rule"], "lookup_required",
                         "官方口径：图生图/图生视频前**必须调用** LOOKUP")
        self.assertTrue(a1.must_lookup_first(True, "app-1")["ok"])

    def test_task_id_is_the_key_and_lost_key_costs_credits(self):
        bad = a1.must_task_id("", "poll")
        self.assertEqual(bad["rule"], "missing_task_id")
        self.assertIn("不再充值", bad["why"],
                      "丢了钥匙只能重新生成 —— 而积分不再充值，所以代价是真钱")
        self.assertTrue(a1.must_task_id("t-1", "optimize")["ok"])

    def test_service_window_is_a_consumable_not_infrastructure(self):
        w = a1.run("service_window")
        self.assertFalse(w["topup_available"], "不再提供 API 积分充值")
        self.assertEqual(w["action"], "plan_as_consumable")
        self.assertIn("一次性存量", a1.run("policy")["no_topup"])

    def test_scale_conflict_is_recorded_not_merged(self):
        s = a1.run("scale")
        self.assertTrue(s["conflict"], "两个规模数字不一样 ⇒ 不许擅自合并")
        nums = [f["n"] for f in s["figures"]]
        self.assertIn("45,000+", nums)
        self.assertIn("100,000+", nums)
        self.assertIn("开放的内容社区", s["position"])


class InterfaceDetailTests(unittest.TestCase):
    """R-H213 · 接口详情（参数契约 + 硬限制，全部来自官方口径）。"""

    def test_auth_and_param_surface(self):
        p = a1.run("params")
        self.assertEqual(p["auth"]["base_url"], "https://a1.art")
        self.assertEqual(p["auth"]["header"], "apiKey")
        self.assertEqual(p["size_id_map"][7], "9:16")
        self.assertEqual(len(p["size_id_map"]), 7)
        self.assertEqual(p["task_states"][20], "失败")
        self.assertEqual(p["section_cn"], "cn")
        self.assertTrue(p["credits"]["unknown"],
                        "积分消耗体系主人未给 ⇒ 必须自曝 unknown，不许编")

    def test_upload_limits_have_teeth(self):
        self.assertEqual(a1.check_upload([])["rule"], "missing_file_or_url")
        self.assertTrue(a1.check_upload([], "https://x/a.png")["ok"],
                        "file 与 imageUrl **传其一**即可")
        self.assertEqual(
            a1.check_upload([{"name": "a.gif", "size": 100}])["rule"],
            "unsupported_file_type", "仅 png/jpg/jpeg")
        self.assertEqual(
            a1.check_upload([{"name": "a.png", "size": 11 * 1024 * 1024}])["rule"],
            "file_too_large", "≤10M")
        self.assertEqual(
            a1.check_upload([{"name": "a.png"}, {"name": "b.png"}])["rule"],
            "too_many_files", "每次仅可上传一张")
        ok = a1.check_upload([{"name": "a.PNG", "size": 1024}])
        self.assertTrue(ok["ok"], "扩展名大小写不敏感（判据不许扩大化）")
        self.assertIn("path", ok["returns"])

    def test_generate_param_contract(self):
        self.assertEqual(a1.check_generate_params({})["rule"], "missing_param")
        base = {"appId": "a1", "versionId": "v1", "generateNum": "2"}
        self.assertTrue(a1.check_generate_params(base)["ok"])
        bad = dict(base, generateNum="5")
        self.assertEqual(a1.check_generate_params(bad)["rule"], "num_out_of_range",
                         "生成数量只允许 1～4 张")
        self.assertEqual(
            a1.check_generate_params(dict(base, size={"sizeId": 9}))["rule"],
            "bad_size_id", "sizeId 只允许 1-7")

    def test_optimize_limits(self):
        self.assertEqual(a1.check_optimize("", "")["rule"], "missing_upload_refs",
                         "path + imageUrl 都必须是上传接口返回值")
        self.assertEqual(
            a1.check_optimize("p", "u", width=4096)["rule"],
            "optimize_size_limit", "精绘尺寸上限 2048×2048")
        ok = a1.check_optimize("p", "u", width=2048, height=2048)
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["points"], 3, "每次消耗 3 个点数")

    def test_task_state_four_values(self):
        self.assertEqual(a1.check_task_state(None)["rule"], "missing_state",
                         "未测不按绿")
        self.assertEqual(a1.check_task_state(99)["rule"], "bad_state")
        self.assertTrue(a1.check_task_state(10)["done"])
        self.assertTrue(a1.check_task_state(20)["failed"])
        self.assertIn("继续轮询", a1.check_task_state(30)["note"])
        self.assertIn("地址会失效", a1.check_task_state(10)["note"])

    def test_persistence_is_official_not_ours(self):
        p = a1.run("persistence")
        self.assertIn("自己的 CDN", p["official"],
                      "官方原话：建议保存到自己的 CDN ⇒ 我们的『必须落盘』有出处了")
        self.assertIn("临时链接", p["our_rule"])


class ErrorCodeAndPricingTests(unittest.TestCase):
    """R-H214 · 18 个错误码 + 定价 + 使用范式（含**两处未解冲突**如实并排）。"""

    def test_eighteen_codes_closed(self):
        r = a1.run("error_codes")
        # R-H215 口径修正：官方标题写「18 个」，但**18 不是上限**（后续又给 3 个）
        self.assertEqual(r["official_title_count"], 18)
        self.assertEqual(r["count"], 21, "截至本次采集共 21 个")
        self.assertFalse(r["is_exhaustive"],
                         "**不承诺全集** —— 用 as_of 语义，不写 closed")
        self.assertTrue(str(r["as_of"]).strip())
        codes = [x["code"] for x in r["codes"]]
        for c in ("0", "10001", "10410", "20000", "324010", "324018",
                  "810012", "400000", "400001", "400003", "400006"):
            self.assertIn(c, codes)

    def test_retry_rule_separates_money_from_pacing(self):
        """核心判据：**钱的问题不重试，节奏的问题才退避**。"""
        r = a1.run("error_codes")
        self.assertEqual(sorted(r["retryable"]), ["20000", "20002", "20003"],
                         "只有限流 / 服务器 / 内部错误可退避")
        self.assertFalse(a1.check_retry("810012")["ok"], "余额不足 ⇒ 不许重试")
        self.assertEqual(a1.check_retry("810012")["rule"], "retry_not_allowed")
        self.assertTrue(a1.check_retry("20000", attempts=0)["ok"])
        self.assertEqual(a1.check_retry("20000", attempts=3)["rule"],
                         "retry_exhausted", "不许无限重试")

    def test_classify_uses_official_table(self):
        self.assertEqual(a1.classify_error("0")["ok"], True)
        self.assertEqual(a1.classify_error("810012")["msg_cn"], "账户余额不足")
        self.assertEqual(a1.classify_error("810012")["retry"], False)
        stale = a1.classify_error("324013")
        self.assertEqual(stale["action"], "relookup",
                         "版本更新 ⇒ 重新 LOOKUP，不许拿旧 versionId 硬重试")
        self.assertEqual(a1.classify_error("20000")["rule"], "retryable_transient")
        self.assertEqual(a1.classify_error("999999")["rule"], "unknown_error_code",
                         "表外码如实报未知，不许硬塞")
        self.assertIn("user upload", a1.classify_error("324010")["detail"])

    def test_pricing_conflict_is_declared(self):
        p = a1.run("pricing")
        self.assertEqual(p["packages"][0]["points"], 1000)
        self.assertTrue(p["unit_conflict"],
                        "套餐折算单价($0.016~0.020) 与标称($0.010) 对不上 ⇒ 必须自曝")
        self.assertNotEqual(p["unit_check"]["1000"], 0.010)

    def test_paradigms_have_different_pricing(self):
        rows = {x["key"]: x for x in a1.run("paradigms")["paradigms"]}
        self.assertEqual(rows["form_app"]["pricing"], "1 积分/张")
        self.assertEqual(rows["optimize"]["pricing"], "3 积分/张")
        self.assertEqual(rows["image_to_video"]["pricing"], "10 积分/个")
        self.assertIn("按节点个数", rows["node_app"]["pricing"])
        self.assertIn("自己的", rows["form_app"]["unpublished"])
        self.assertIn("不支持", rows["node_app"]["unpublished"])
        self.assertEqual(a1.estimate_cost("image_to_video", 3)["total"], 30)
        self.assertEqual(a1.estimate_cost("")["rule"], "unknown_paradigm",
                         "计价因范式而异，先说哪种")

    def test_open_conflicts_are_not_silently_resolved(self):
        c = a1.run("conflicts")
        self.assertTrue(c["topup"]["pending"], "定价表 vs 不再充值 ⇒ 未解，不许擅自选")
        self.assertTrue(c["unit"]["pending"], "点数 vs 积分 ⇒ 未解，不许擅自等同")
        self.assertIn("API 侧", c["topup"]["likely"])
        w = a1.run("service_window")
        self.assertFalse(w["topup_available"])
        self.assertTrue(w["conflict"]["pending"],
                        "已关账的闸不许擅自翻转；冲突要挂在它身上一起报")


class Rh215FixTests(unittest.TestCase):
    """R-H215 · 四件口径收口（其中一件是**已落闸的缺口**，照报照补）。"""

    def test_upload_dimension_gap_is_fixed(self):
        """400006 ⇒ 上传**也有尺寸限制**；此前 check_upload 只查后缀/数量/体积。"""
        self.assertEqual(
            a1.check_upload([{"name": "a.png", "width": 4096}])["rule"],
            "image_too_large_dimension")
        self.assertEqual(
            a1.check_upload([{"name": "a.png", "height": 3000}])["rule"],
            "image_too_large_dimension")
        ok = a1.check_upload([{"name": "a.png", "width": 2048, "height": 2048}])
        self.assertTrue(ok["ok"], "正好 2048 要放行（判据不许扩大化）")
        self.assertEqual(a1.UPLOAD_LIMITS["max_side"], 2048)

    def test_three_new_codes_are_in(self):
        rows = {x["code"]: x for x in a1.run("error_codes")["codes"]}
        self.assertEqual(rows["400001"]["gate"], "too_many_files")
        self.assertEqual(rows["400003"]["gate"], "file_too_large")
        self.assertEqual(rows["400006"]["gate"], "image_too_large_dimension")

    def test_official_five_primitives_are_double_sourced(self):
        o = a1.run("primitives_official")
        self.assertEqual(o["count"], 5)
        self.assertTrue(o["double_source"])
        self.assertEqual([x["primitive"] for x in o["map"]],
                         ["lookup", "upload", "generate", "optimize", "poll"])
        self.assertEqual(o["map"][4]["cn"], "查询任务结果")

    def test_video_component_now_has_evidence(self):
        e = a1.run("unsupported_evidence")
        self.assertIn("Video 组件", e["official"],
                      "R-H215 起 Video 组件不再是『待核』")
        self.assertIn("Video 组件", e["components"])
        self.assertEqual(e["codes"], ("324010", "324018"))


class OfficialTeethTests(unittest.TestCase):
    """R-H216 · 官方三条带牙用例 **3/3 与我方一致**（双源印证）+ 落点清单。"""

    def test_three_cases_all_match(self):
        t = a1.run("teeth_cases")
        self.assertEqual(t["count"], 3)
        self.assertTrue(t["all_match"])
        for x in t["cases"]:
            self.assertTrue(x["our_gates"], "每条都要挂到我们的闸上")

    def test_second_case_brings_the_landing_list(self):
        t = a1.run("teeth_cases")
        self.assertEqual(t["allowed_landings"],
                         ["本地 CDN", "工作区", "local_cdn", "workspace"])
        self.assertIn("本地 CDN", t["cases"][1]["official"])
        self.assertIn("工作区", t["cases"][1]["official"])

    def test_localize_accepts_official_landings_and_rejects_others(self):
        ok = a1.must_localize({"local_path": "ws/a1/out.png", "landing": "工作区"})
        self.assertTrue(ok["ok"], "工作区是官方认可落点")
        ok2 = a1.must_localize({"local_path": "cdn/a.png", "landing": "本地 CDN"})
        self.assertTrue(ok2["ok"])
        bad = a1.must_localize({"local_path": "x.png", "landing": "某第三方网盘"})
        self.assertEqual(bad["rule"], "landing_not_allowed",
                         "落点只认可控的两种；别又落回不明第三方")
        self.assertEqual(a1.must_localize({})["rule"], "link_only_result")


class PreflightTests(unittest.TestCase):
    """R-H217 · 官方四条红线 4/4 对账 + **请求前必须预检**。"""

    def test_four_official_redlines_all_have_gates(self):
        r = a1.run("redlines_official")
        self.assertEqual(r["count"], 4)
        self.assertTrue(r["all_have_gates"], "四条全都要落到现有闸上（不新造）")
        for x in r["redlines"]:
            self.assertTrue(x["our_gates"])

    def test_lookup_has_three_roles(self):
        roles = [x["role"] for x in a1.run("lookup_roles")["roles"]]
        self.assertEqual(len(roles), 3)
        self.assertIn("拿依赖参数", roles[0])
        self.assertIn("续期", roles[1])
        self.assertIn("预检组件", roles[2])

    def test_preflight_blocks_before_sending(self):
        self.assertEqual(a1.must_preflight(["数字分身"], looked_up=False)["rule"],
                         "preflight_requires_lookup",
                         "预检的数据来自 LOOKUP ⇒ 没 LOOKUP 不许预检")
        self.assertEqual(a1.must_preflight([], looked_up=True)["rule"],
                         "no_components_declared",
                         "拿不到组件清单 ⇒ 不许当作「干净」（未测不按绿）")
        blocked = a1.must_preflight(["图生图", "wordart 组件"], looked_up=True)
        self.assertEqual(blocked["rule"], "preflight_blocked")
        self.assertIn("wordart", " ".join(blocked["components"]))
        self.assertTrue(a1.must_preflight(["图生图", "高清"], looked_up=True)["ok"])

    def test_preflight_covers_all_four_components(self):
        for comp in a1.UNSUPPORTED_COMPONENTS:
            self.assertEqual(
                a1.must_preflight([comp], looked_up=True)["rule"],
                "preflight_blocked", "四个组件都要被预检拦住：%s" % comp)


if __name__ == "__main__":
    unittest.main()
