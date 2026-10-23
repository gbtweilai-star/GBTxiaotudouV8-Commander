# -*- coding: utf-8 -*-
"""LibTV 技能（libtv_skill）· 带牙用例（R-H204）。

① 红线①：**返回值带明文 key ⇒ 拒**（`plaintext_key_in_return`）；
② 红线②：**不经密钥池取 key ⇒ 拒** —— 池里没有该身份就如实报缺，
   不许回落环境变量（源码里不许有 `import os` / `os.environ` / `getenv`）；
③ 红线③：**结果不落 trace ⇒ 拒**（`no_trace`，无痕即未发生）；
④ 只读骨架里不许出现网络 / 写盘路径；
⑤ 它是**门**（`type=external`）：登记在册，且**落地即接线**（编排内核真 import）。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import libtv_skill as lt  # noqa: E402
from gbt_allinone.tools import orchestration_kernel as ok  # noqa: E402
from gbt_allinone import caps_registry as CR  # noqa: E402


def _code_only(path) -> str:
    """只留**代码**（剥掉注释与字符串字面量）。

    为什么需要它：本模块的 `KEY_INJECTION["forbidden"]` 里**写着**"不许 os.environ"，
    裸字符串扫描会把「文档里的禁令」当成「代码里的违规」——
    和今天的「注释提过 ≠ 真接线」同族。**判据要卡在真问题上，别扩大化。**
    """
    import io
    import tokenize
    out = []
    with open(path, "rb") as f:
        for tok in tokenize.tokenize(f.readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(tok.string)
    return " ".join(out)


class RedLineTests(unittest.TestCase):
    def test_plaintext_key_in_return_is_refused(self):
        """红线①：返回值里出现明文 key ⇒ 拒（只回 key_id / masked / leased）。"""
        bad = lt.assert_no_plaintext({"key": "sk-live-abcdefghijklmnop1234"},
                                     where="probe")
        self.assertFalse(bad["ok"])
        self.assertTrue(bad["denied"])
        self.assertEqual(bad["rule"], "plaintext_key_in_return")
        good = lt.assert_no_plaintext({"key_id": "ai-music-1", "leased": True,
                                       "key_masked": "****"})
        self.assertTrue(good["ok"], "脱敏形状必须能过——判据不许扩大化")

    def test_lease_requires_owner_ai_id(self):
        """一 AI 一号：没有 owner_ai_id 就没有可借的钥匙（拒执行并上报）。"""
        out = lt.lease_key("")
        self.assertFalse(out["ok"])
        self.assertTrue(out["denied"])
        self.assertEqual(out["rule"], "missing_owner_ai_id")

    def test_lease_refuses_when_pool_has_no_key(self):
        """红线②要有牙：池里没有该身份 ⇒ `no_key_for_owner`，**不回落环境变量**。"""
        out = lt.lease_key("ai-not-configured-xyz", tentacle_id="t-libtv")
        self.assertFalse(out["ok"], "没配就是没配——不许从 env 偷一份顶上")
        self.assertTrue(out["denied"])
        self.assertEqual(out["rule"], "no_key_for_owner")
        self.assertFalse(out.get("leased"))

    def test_source_has_no_second_key_path(self):
        """红线②的静态面：**代码**不许自己去读密钥（第二套路径的典型形状）。"""
        src = Path(lt.__file__).read_text(encoding="utf-8")
        self.assertIn("model_key_pool", src, "唯一的钥匙来源必须是密钥池")
        code = _code_only(lt.__file__)
        for bad in ("import os", "os.environ", "getenv", "environ"):
            self.assertNotIn(bad, code,
                             "**代码**里不许出现取密钥的第二套路径：%s"
                             "（文档里写禁令不算违规——判据不许扩大化）" % bad)

    def test_no_trace_means_it_did_not_happen(self):
        """红线③：无痕即未发生——没有 trace_ref 的结果不许当产出。"""
        bad = lt.must_trace({"files": ["a.png", "b.mp4"]})
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["rule"], "no_trace")
        good = lt.must_trace(trace_ref="trace-libtv-0001")
        self.assertTrue(good["ok"])
        self.assertEqual(good["trace_ref"], "trace-libtv-0001")


class SkeletonTests(unittest.TestCase):
    def test_three_action_faces_are_declared(self):
        """功能面三条（会话进展 / 切项目 / 批量下载）必须登记，且不许自吹能跑。"""
        acts = lt.run("actions")
        self.assertEqual([a["key"] for a in acts["actions"]],
                         ["session_progress", "switch_project", "download_assets"])
        st = lt.run("status")
        self.assertEqual(st["type"], "external", "它是门，不是内调型")
        self.assertEqual(st["domain"], "video")
        self.assertIn("未接", st["note"])
        self.assertFalse(st["forensics"]["key_configured"])

    def test_forensics_is_honest_not_dressed_up(self):
        """取证读数如实：盘上命中 0、密钥未配——『在』不等于『能用』。"""
        fo = lt.run("forensics")
        self.assertEqual(fo["libtv_hits_on_disk"], 0)
        self.assertEqual(fo["key_configured"], False)

    def test_module_has_no_network_or_write_paths(self):
        src = Path(lt.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket",
                    "import subprocess", "subprocess.run", ".write_text(",
                    ".write_bytes(", "unlink(", "shutil.copy", "cp -r"):
            self.assertNotIn(bad, src, "只读骨架里不该出现：%s" % bad)


class WiringTests(unittest.TestCase):
    def test_registered_as_external_gate(self):
        cap = CR.BENIGN_CAPS.get("libtv_skill")
        self.assertIsNotNone(cap, "LibTV 技能必须登记进能力注册表")
        self.assertEqual(cap["handler"], "libtv_skill")
        self.assertEqual(cap["domain"], "video")
        self.assertTrue(cap["safe"])

    def test_landed_then_wired_no_new_orphan(self):
        """落地即接线：编排内核里必须是**真 import 的模块**，不是注释里的名字。"""
        self.assertIn("libtv_skill", ok._READONLY_MODULES)
        self.assertIs(ok._READONLY_MODULES["libtv_skill"], lt)


class ContractTests(unittest.TestCase):
    """R-H205 · 契约蒸馏（把官方指南蒸成"可查、可判"的原生契约）。"""

    def test_contract_faces_are_present(self):
        c = lt.run("contract")
        self.assertTrue(c["cli"], "命令面不许空——蒸馏至少要能回答『怎么调』")
        self.assertEqual(c["node_ref"]["key_form"], "{{Node <Node Key>}}")
        self.assertEqual(c["node_ref"]["name_form"], '{{Node "节点名"}}')
        self.assertGreaterEqual(len(c["failure_classes"]), 6)
        self.assertIn("input", c["canvas_zones"])
        self.assertIn("qc", c["canvas_zones"], "质检与重跑区必须有落点")
        self.assertEqual(len(c["delivery"]), 7)

    def test_policies_are_official_not_our_wish(self):
        p = lt.run("policies")
        self.assertIn("以平台当前规则为准", p["credits"],
                      "『失败一定不消耗』不许当承诺——口径归平台")
        self.assertIn("浏览器", p["workspace"], "空间口径：CLI 登录态跟着浏览器账号走")
        self.assertIn("不代签", p["human_login"], "登录这一步必须是人做的")

    def test_failure_classifier_refuses_to_guess(self):
        self.assertEqual(lt.classify_failure("")["rule"], "empty_failure_text")
        out = lt.classify_failure("今天天气不错")
        self.assertEqual(out["rule"], "unknown_failure_class",
                         "归不进六类就如实报 unknown —— 不许硬塞一个原因")
        self.assertIn("safety_review",
                      [c["key"] for c in lt.classify_failure("生成被安全审核拦截")["classes"]])
        self.assertIn("transient",
                      [c["key"] for c in lt.classify_failure("网络波动，任务超时")["classes"]])

    def test_rerun_needs_diagnosis_and_minimal_scope(self):
        self.assertEqual(lt.must_diagnose_before_rerun({})["rule"],
                         "rerun_without_diagnosis")
        self.assertEqual(lt.must_diagnose_before_rerun({"rebuild_canvas": True})["rule"],
                         "canvas_rebuild", "一条报错不该赔掉整张图")
        self.assertEqual(
            lt.must_diagnose_before_rerun({"diagnosed": "第 3 个节点没结果 URL"})["rule"],
            "scope_unspecified", "要给最小修复范围，不许『全部重跑』")
        ok = lt.must_diagnose_before_rerun({"diagnosed": "引用顺序错", "scope": ["u3-video"]})
        self.assertTrue(ok["ok"])

    def test_node_ref_syntax_gate(self):
        self.assertEqual(lt.check_node_ref("用 {{节点A}} 生成视频")["rule"],
                         "bad_node_ref_syntax", "少了 `Node ` 前缀就是坏形状")
        self.assertEqual(lt.check_node_ref("用 {{Node}} 生成视频")["rule"],
                         "bad_node_ref_syntax", "有 Node 没名字也是坏形状")
        # 判据不许把中文名误伤：{{Node 角色A}} 是**合法**的（这条是被自己的用例抓出来的）
        self.assertTrue(lt.check_node_ref("场景用 {{Node 场景1}}")["ok"])
        good = lt.check_node_ref('角色当主角用 {{Node "角色A"}}，场景用 {{Node 场景1}}')
        self.assertTrue(good["ok"])
        hint = lt.check_node_ref("{{Node 角色A}} 生成一段视频")
        self.assertIn("hint", hint, "有引用却不说用途 ⇒ 必须提醒（这是身份混淆的根因）")

    def test_delivery_must_not_be_a_lone_video_link(self):
        bad = lt.delivery_check({"最终视频链接": "https://x"})
        self.assertEqual(bad["rule"], "incomplete_delivery")
        self.assertIn("项目链接", bad["missing"])
        full = lt.delivery_check({k: "x" for k in lt.DELIVERY_ITEMS})
        self.assertTrue(full["ok"])

    def test_cli_redlines_are_declared_alongside_old_three(self):
        rl = lt.run("redlines")
        self.assertEqual(len(rl["red_lines"]), 3, "R-H204 的三条一条都不许动")
        self.assertEqual(len(rl["red_lines_cli"]), 4)
        self.assertTrue(any("重建整张画布" in x for x in rl["red_lines_cli"]))


class InteractionAndRequirementTests(unittest.TestCase):
    """R-H207 · 交互面 + 要求面 + **三条带牙用例**（按主人给的那三条落）。"""

    def test_interaction_is_human_side(self):
        it = lt.run("interaction")
        self.assertEqual(it["canvas"], "无限画布")
        self.assertEqual(it["authoring"], "手动拖拽节点")
        self.assertIn("不许假装能替人", it["boundary"],
                      "布局审美是人的位置，Agent 不许自称能替")

    def test_four_requirements_each_carry_criteria(self):
        reqs = lt.run("requirements")["requirements"]
        self.assertEqual([r["key"] for r in reqs],
                         ["upload_ref", "poll_progress", "batch_download",
                          "switch_project"])
        for r in reqs:
            self.assertTrue(str(r.get("criteria") or "").strip(),
                            "%s 缺判据 —— 没有判据的要求只是口号" % r["key"])

    # ── 带牙用例 ①：返回值不许带明文 LIBTV_ACCESS_KEY ──
    def test_teeth_1_no_plaintext_key_in_return(self):
        self.assertEqual(lt.must_mask_key(
            {"LIBTV_ACCESS_KEY": "lt-live-abcdefghijklmnop1234"})["rule"],
            "plaintext_key_in_return")
        self.assertTrue(lt.must_mask_key(
            {"key_id": "ai-video-1", "key_masked": "****（池内持有，不出池）"})["ok"])

    # ── 带牙用例 ②：结果必须下载到本地，不许只留 OSS 链接 ──
    def test_teeth_2_oss_link_alone_is_refused(self):
        out = lt.must_localize_oss({"oss_url": "https://oss.example.com/a.mp4"})
        self.assertFalse(out["ok"])
        self.assertEqual(out["rule"], "oss_link_only")
        self.assertTrue(lt.must_localize_oss(
            {"oss_url": "https://oss.example.com/a.mp4",
             "local_path": "store\\libtv\\a.mp4"})["ok"])

    # ── 带牙用例 ③：必须走 libtv-skill 脚本，不许自己拼 API 请求 ──
    def test_teeth_3_handmade_api_request_is_refused(self):
        bad = lt.must_use_skill_script(
            {"via": "libtv-skill run", "url": "https://api.libtv.example/v1/gen"})
        self.assertEqual(bad["rule"], "handmade_api_request")
        bad2 = lt.must_use_skill_script({"via": "自己写的 requests 调用"})
        self.assertEqual(bad2["rule"], "not_via_skill_script")
        self.assertTrue(lt.must_use_skill_script(
            {"via": "libtv-skill node --run"})["ok"])

    def test_requirement_criteria_have_teeth(self):
        self.assertEqual(lt.must_poll_incrementally("")["rule"],
                         "poller_without_cursor")
        self.assertEqual(lt.must_poll_incrementally("", full_refetch=True)["rule"],
                         "poller_without_cursor")
        ok = lt.must_poll_incrementally("cur-001")
        self.assertTrue(ok["ok"])
        self.assertIn("没有变化", ok["note"], "『没有变化』不许当失败（长任务是常态）")
        self.assertEqual(lt.must_project_bound("")["rule"], "no_project_bound",
                         "没绑定就操作 ⇒ 可能在错的项目里花钱")
        self.assertTrue(lt.must_project_bound("proj-shortdrama-01")["ok"])

    def test_new_skill_redline_is_declared(self):
        rl = lt.run("redlines")
        self.assertIn("libtv-skill 脚本", " ".join(rl["red_lines_skill"]))
        self.assertEqual(len(rl["red_lines"]), 3, "R-H204 三条依旧一条不动")


class PlatformAndKeyPolicyTests(unittest.TestCase):
    """R-H208 · 平台面 + 安装面 + **密钥口径撞车点的收口**。"""

    def test_platform_is_dual_entry(self):
        p = lt.run("platform")
        self.assertIn("human", p["dual_entry"], "人用画布")
        self.assertIn("agent", p["dual_entry"], "Agent 用 Skill")
        self.assertGreaterEqual(len(p["coverage"]), 10, "能力覆盖要如实列全")
        self.assertIn("Seedance 2.0", p["models"])
        self.assertTrue(any("局部编辑" in c for c in p["coverage"]))

    def test_install_surface_is_official_only(self):
        ins = lt.run("install")
        self.assertIn("npx skills add", ins["method_npx"])
        self.assertIn("git clone", ins["method_clone"])
        self.assertIn("Python 标准库", ins["deps"], "官方口径：无需额外依赖")
        self.assertTrue(ins["requires_network"], "npx / git clone 都要出网")
        self.assertTrue(ins["needs_owner_authorization"], "装技能要主人点头")
        self.assertIn("未安装", ins["status"])

    def test_gate_install_refuses_unknown_method(self):
        self.assertEqual(lt.check_install("")["rule"], "missing_install_method")
        self.assertEqual(lt.check_install("pip install libtv")["rule"],
                         "unknown_install_method")
        self.assertTrue(lt.check_install("npx")["ok"])

    # ── 本刀最重要的收口：官方只认 env，我们不许明文落盘 ──
    def test_key_injection_splits_source_from_sink(self):
        self.assertEqual(
            lt.check_key_injection({"source": "env", "inject_to_child_env": True})["rule"],
            "key_source_not_pool", "从 env 取密钥 = 第二套密钥路径")
        self.assertEqual(
            lt.check_key_injection({"source": "dotenv"})["rule"],
            "key_source_not_pool")
        self.assertEqual(
            lt.check_key_injection({"inject_to_child_env": True})["rule"],
            "key_source_unspecified", "要说清密钥从哪来")
        self.assertEqual(
            lt.check_key_injection({"source": "model_key_pool", "persist": True})["rule"],
            "key_persisted_to_file", "写进 .env / 配置文件 = 明文落盘")
        self.assertEqual(
            lt.check_key_injection({"source": "model_key_pool"})["rule"],
            "injection_channel_unspecified", "技能包只认 env ⇒ 要显式声明注入")
        ok = lt.check_key_injection({"source": "model_key_pool",
                                     "inject_to_child_env": True})
        self.assertTrue(ok["ok"], "**取归池、放归进程** —— 正确形状必须放行")
        self.assertEqual(ok["injection"], "child_process_env_only")

    def test_key_policy_states_the_conflict_honestly(self):
        kp = lt.run("key_policy")
        self.assertIn("环境变量", kp["conflict"], "撞车点要写明，不许藏着")
        self.assertIn("DPAPI", kp["conflict"])
        self.assertTrue(any("明文落盘" in f for f in kp["forbidden"]))
        self.assertIn("来源归池", kp["why"])


class SkillScriptTests(unittest.TestCase):
    """R-H209 · 技能包的 5 个脚本（**只抄不猜**：推定项必须自曝）。"""

    def test_five_scripts_in_official_order(self):
        s = lt.run("scripts")
        self.assertEqual(s["count"], 5)
        self.assertEqual([x["script"] for x in s["scripts"]],
                         ["create_session.py", "query_session.py",
                          "change_project.py", "upload_file.py",
                          "download_results.py"])
        self.assertEqual([x["n"] for x in s["scripts"]], [1, 2, 3, 4, 5])

    def test_evidenced_vs_inferred_is_declared_not_blurred(self):
        s = lt.run("scripts")
        # R-H210 起：#2 也升为实证 —— 主人给了实测调用形态
        # `query_session.py <SESSION_ID> --after-seq 5`（增量游标有真形状了）
        self.assertEqual(s["evidenced"],
                         ["create_session.py", "query_session.py", "upload_file.py"],
                         "这三条有主人原话/实测调用形态")
        self.assertEqual(s["inferred"], 2, "推定项必须如实计数，不许混成已证")
        for x in s["scripts"]:
            self.assertIsInstance(x["evidenced"], bool)
            self.assertTrue(str(x["cn"]).strip(), "%s 缺作用" % x["script"])

    def test_upload_file_ties_back_to_the_oss_redline(self):
        row = [x for x in lt.run("scripts")["scripts"]
               if x["script"] == "upload_file.py"][0]
        self.assertIn("OSS", row["cn"])
        self.assertIn("必须下载到本地", row["note"],
                      "素材进 OSS ⇒ 结果也在 OSS ⇒ 这就是『不许只留 OSS 链接』的由来")

    def test_gate_script_refuses_home_made_scripts(self):
        self.assertEqual(lt.check_script("")["rule"], "missing_script")
        self.assertEqual(lt.check_script("my_own_uploader.py")["rule"],
                         "unknown_script", "技能包之外一律不认")
        self.assertTrue(lt.check_script("create_session.py")["ok"])
        self.assertTrue(lt.check_script("C:\\x\\libtv\\upload_file.py")["ok"],
                        "带路径也要能认（取 basename）")
        out = lt.check_script("query_session.py")
        self.assertTrue(out["evidenced"], "R-H210 起有实测调用形态 ⇒ 实证")
        hint = lt.check_script("change_project.py")
        self.assertFalse(hint["evidenced"])
        self.assertIn("hint", hint, "推定项要**自曝**它的作用是推定")


class SessionContractTests(unittest.TestCase):
    """R-H210 · 调用形态 + 会话契约（**钥匙丢了只能重建会话 = 白花钱**）。"""

    def test_contract_records_the_two_observed_forms(self):
        c = lt.run("session_contract")
        self.assertEqual(c["scripts_dir"], "scripts/")
        self.assertIn("python3 scripts/", c["invocation"])
        self.assertEqual(tuple(c["returns"]), ("projectUuid", "sessionId"))
        self.assertIn("--after-seq", c["poll_cursor"])
        self.assertIn("自然语言", c["creation_style"],
                      "所有创作靠发自然语言消息，不许绕开去自己拼参数")

    def test_observed_usage_is_recorded_verbatim(self):
        rows = {x["script"]: x for x in lt.run("scripts")["scripts"]}
        self.assertEqual(rows["create_session.py"]["usage"],
                         'python3 scripts/create_session.py "生一个动漫视频"')
        self.assertEqual(rows["query_session.py"]["usage"],
                         "python3 scripts/query_session.py <SESSION_ID> --after-seq 5")

    def test_poll_args_gate_needs_session_id_and_cursor(self):
        self.assertEqual(lt.check_poll_args("", 5)["rule"], "missing_session_id")
        self.assertEqual(lt.check_poll_args("s-1", None)["rule"],
                         "poller_without_cursor", "不带游标 = 全量重拉 = 烧 token")
        self.assertEqual(lt.check_poll_args("s-1", "abc")["rule"], "bad_after_seq")
        ok = lt.check_poll_args("s-1", "5")
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["cursor"], "--after-seq 5")
        self.assertIn("没有新增", ok["note"])

    def test_session_refs_gate_keeps_the_keys(self):
        bad = lt.check_session_refs("", "")
        self.assertEqual(bad["rule"], "missing_session_refs")
        self.assertEqual(sorted(bad["missing"]), ["projectUuid", "sessionId"])
        self.assertTrue(lt.check_session_refs("p-1", "s-1")["ok"])


class AccessRedlineTests(unittest.TestCase):
    """R-H212 · 接入安全与合规红线 9 条（**三簇**）落机械闸。"""

    def test_nine_redlines_in_three_groups(self):
        r = lt.run("access_redlines")
        self.assertEqual(r["count"], 9)
        self.assertEqual(r["groups"], ["key", "identity", "trace"])
        self.assertFalse(r["closed"],
                         "主人没说『就这些』⇒ 不许当定稿，要留追加位")
        for x in r["redlines"]:
            self.assertTrue(str(x["gate"]).strip(), "%s 没写闸" % x["cn"])

    def test_key_cluster(self):
        self.assertEqual(lt.check_key_storage("C:/x/.env")["rule"],
                         "key_must_be_dpapi", "明文 / .env 里的密钥一律不认")
        self.assertEqual(lt.check_key_storage("secrets/libtv.dpapi")["rule"],
                         "key_source_not_pool", "存 DPAPI 还不够：来源必须是池")
        self.assertTrue(lt.check_key_storage("secrets/libtv.dpapi",
                                             from_pool=True)["ok"])

    def test_identity_cluster(self):
        self.assertEqual(lt.check_no_bypass(True, "人机验证")["rule"],
                         "bypass_verification")
        self.assertEqual(lt.check_identity_keys([])["rule"],
                         "missing_identity_keys")
        self.assertEqual(
            lt.check_identity_keys([{"owner_ai_id": "", "key_id": "k1"}])["rule"],
            "missing_owner_ai_id")
        shared = lt.check_identity_keys([{"owner_ai_id": "ai-a", "key_id": "k1"},
                                         {"owner_ai_id": "ai-b", "key_id": "k1"}])
        self.assertEqual(shared["rule"], "shared_key_across_identities",
                         "多个 AI 身份必须各自独立密钥")
        ok = lt.check_identity_keys([{"owner_ai_id": "ai-a", "key_id": "k1"},
                                     {"owner_ai_id": "ai-b", "key_id": "k2"}])
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["identities"], 2)

    def test_trace_cluster(self):
        self.assertEqual(lt.must_trace_call("", "libtv")["rule"],
                         "call_not_traced", "**每次调用**都要留痕，不只是结果")
        self.assertEqual(lt.must_trace_call("t-1", "a1art")["rule"],
                         "bad_source_kind")
        self.assertEqual(lt.must_trace_call("t-1", "a1art")["expected"], "libtv")
        self.assertTrue(lt.must_trace_call("t-1", "libtv")["ok"])
        self.assertEqual(lt.must_pass_review("")["rule"], "review_required")
        self.assertEqual(lt.must_pass_review("rejected")["rule"], "review_required")
        self.assertTrue(lt.must_pass_review("approved")["ok"])


class OfficialFiveRedlinesTests(unittest.TestCase):
    """R-H218 · 官方《五条红线》= 我们 9 条的**前 5 条**（标签修正，防两处真相）。"""

    def test_front_five_are_the_official_five(self):
        r = lt.run("access_redlines")
        self.assertEqual(r["official_count"], 5)
        self.assertEqual(len(r["official"]), 5)
        official = [x["cn"] for x in r["official"]]
        self.assertEqual(official, [
            "密钥只存 DPAPI",
            "LIBTV_ACCESS_KEY 必须走密钥池，不许明文落盘",
            "不绕验证",
            "走官方 OpenAPI，不绕过平台验证",
            "一 AI 一号",
        ])
        self.assertEqual(len(r["extra_requirements"]), 4,
                         "后 4 条应单列为『追加要求』，不许混成官方九条")
        # R-H219：追加要求的**出处已落实**（原来是"主人另给·待核"，过度保守）
        self.assertIn("都出自官方", r["note"])
        self.assertIn("分属两节", r["note"])
        self.assertIn("官方", r["extra_source"])

    def test_capability_three_classes_and_new_items(self):
        p = lt.run("platform")
        cls = p["capability_classes"]
        self.assertEqual(sorted(cls), ["complex", "edit", "generate"])
        self.assertIn("视频续写", cls["generate"])
        self.assertIn("元素替换（把纸船换成爱心）", cls["edit"])
        self.assertTrue(any("剧本→分镜→成片" in x for x in cls["complex"]))
        self.assertIn("三分类", p["coverage_note"])

    def test_upload_gains_the_precondition(self):
        row = [x for x in lt.run("scripts")["scripts"]
               if x["script"] == "upload_file.py"][0]
        self.assertIn("必须先上传", row["precondition"],
                      "编辑已有素材前必须先上传 —— 与 LOOKUP 的『必调』同族")

    def test_second_source_is_declared(self):
        self.assertIn("第二出处", lt.run("scripts")["second_source"])
        self.assertIn("通过 Skill 调用 OpenAPI", lt.run("platform")["agent_entry"])


class LibtvPrimitivesTests(unittest.TestCase):
    """R-H220 · 官方五原语（能力维度）↔ 5 脚本（文件清单）**一一对上**。"""

    def test_five_primitives_map_to_five_scripts(self):
        p = lt.run("primitives")
        self.assertEqual(p["count"], 5)
        self.assertEqual([x["primitive"] for x in p["primitives"]],
                         ["SESSION", "UPLOAD", "QUERY", "DOWNLOAD", "PROJECT"])
        self.assertEqual([x["script"] for x in p["primitives"]],
                         ["create_session.py", "upload_file.py",
                          "query_session.py", "download_results.py",
                          "change_project.py"])
        # 5 个脚本与 R-H209 的清单**集合相同**（只是顺序不同）
        ours = {x["script"] for x in lt.run("scripts")["scripts"]}
        theirs = {x["script"] for x in p["primitives"]}
        self.assertEqual(ours, theirs)

    def test_two_orders_are_stated_separately(self):
        n = lt.run("primitives")["order_note"]
        self.assertIn("两套顺序不同", n)
        self.assertIn("不许当同一个排序", n)

    def test_script_primitive_map_is_available(self):
        m = lt.run("scripts")["primitive_map"]
        self.assertEqual(m["create_session.py"], "SESSION")
        self.assertEqual(m["change_project.py"], "PROJECT")

    def test_publish_chain_and_domain_second_source(self):
        p = lt.run("primitives")
        self.assertIn("内容审核队列", p["publish_chain"])
        self.assertIn("确认合规后才发布", p["publish_chain"])
        self.assertEqual(p["domain"], "video",
                         "LibTV 官方 domain=video（与 a1.art 的 image_video 不同）")


class OfficialTeethTests(unittest.TestCase):
    """R-H221 · 官方三条带牙用例 **3/3 与我们已落的一致**。"""

    def test_three_cases_all_match(self):
        t = lt.run("teeth_cases")
        self.assertEqual(t["count"], 3)
        self.assertTrue(t["all_match"])
        for x in t["cases"]:
            self.assertTrue(x["our_gates"], "每条都要挂到我们的闸上")

    def test_first_case_names_the_exact_key(self):
        c = lt.run("teeth_cases")["cases"][0]
        self.assertIn("LIBTV_ACCESS_KEY", c["official"],
                      "官方把 key 具体化了（比我们写的泛称更精确）")
        self.assertIn("plaintext_key_in_return", c["our_gates"])

    def test_third_case_is_principle_not_a_second_rule(self):
        c = lt.run("teeth_cases")["cases"][2]
        self.assertIn("不绕过官方入口", c["official"], "官方写的是**原理**")
        self.assertIn("handmade_api_request", c["our_gates"], "我们落的是**形态**")
        self.assertIn("原理", c["increment"])
        self.assertIn("不是两条不同的红线", c["increment"])

    def test_oss_link_wording_is_recorded(self):
        c = lt.run("teeth_cases")["cases"][1]
        self.assertIn("OSS", c["official"])
        self.assertIn("link_only_result", c["our_gates"])


if __name__ == "__main__":
    unittest.main()
