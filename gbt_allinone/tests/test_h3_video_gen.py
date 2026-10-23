# -*- coding: utf-8 -*-
"""H3mini 视频生成 · 带牙用例（R-H250）。

三条**带牙**用例必须真咬人：明文密钥 / 只给远程链接 / 散文式提示词 —— 都要被拒。
另有：硬件门槛先验（验不到不许说能跑）· 不绕官方入口 · 引用不复制（不落 SKILL.md 内容）。
"""
from __future__ import annotations

import unittest

from gbt_allinone.tools import h3_video_gen as h3


class PrimitiveTests(unittest.TestCase):
    def test_four_primitives_exact(self):
        got = [p["key"] for p in h3.PRIMITIVES]
        self.assertEqual(got, ["T2VA", "I2VA", "FL2VA", "Ref2VA"])

    def test_status_shape(self):
        st = h3.run("status")
        self.assertTrue(st["ok"])
        self.assertTrue(st["readonly"])
        self.assertEqual(st["type"], "external")
        self.assertTrue(st["requires_external_key"])
        self.assertFalse(st["key_present"])

    def test_core_skill_is_markdown_only_reference(self):
        sk = h3.run("skills")
        self.assertEqual(sk["official"]["core"], "h3-prompt-writing")
        self.assertIn("不复制", sk["official"]["ref_not_copy"])
        self.assertEqual(sk["official"]["count"], 9)


class TeethCaseTests(unittest.TestCase):
    """三条带牙用例。"""

    def test_case1_plaintext_key_rejected(self):
        r = h3.run("gate_key", payload="mm-abcdefghijklmnop1234")
        self.assertFalse(r["ok"])
        self.assertEqual(r["rule"], "plaintext_key")
        self.assertTrue(h3.run("gate_key", payload="key_id=k-1 掩码 sk-a1****")["ok"])

    def test_case2_remote_only_result_rejected(self):
        r = h3.run("gate_localize", targets=["https://cdn.example.com/a.mp4"])
        self.assertFalse(r["ok"])
        self.assertEqual(r["rule"], "result_not_localized")
        self.assertTrue(h3.run("gate_localize",
                               targets=["work/out.mp4"])["ok"])
        self.assertFalse(h3.run("gate_localize", targets=[])["ok"])

    def test_case3_prose_prompt_rejected(self):
        prose = "一个女孩在雨里跑过街道非常电影感镜头慢慢推近"
        r = h3.run("gate_prompt", prompt=prose)
        self.assertFalse(r["ok"])
        self.assertEqual(r["rule"], "prose_prompt_rejected")

    def test_case3_six_sections_accepted(self):
        r = h3.run("gate_prompt", sections=["a", "b", "c", "d", "e", "f"])
        self.assertTrue(r["ok"])
        self.assertEqual(r["sections"], 6)

    def test_case3_incomplete_sections_rejected(self):
        for bad in (["a", "b", "c"], ["a", "b", "c", "d", "e", ""]):
            r = h3.run("gate_prompt", sections=bad)
            self.assertFalse(r["ok"], bad)
            self.assertEqual(r["rule"], "prompt_sections_incomplete")

    def test_case3_no_input_rejected(self):
        self.assertEqual(h3.run("gate_prompt")["rule"], "prompt_missing")

    def test_section_names_not_invented(self):
        # 六段**段名**未取证 ⇒ 只判"有没有按段给"，不编段名
        self.assertFalse(h3.PROMPT_SECTIONS_EVIDENCED)
        self.assertIn("不编段名", h3.PROMPT_SECTIONS_NOTE)


class HardwareTests(unittest.TestCase):
    """红线④：硬件门槛先验。"""

    def test_local_without_reading_is_denied(self):
        r = h3.run("gate_hw", mode="local")
        self.assertFalse(r["ok"])
        self.assertEqual(r["rule"], "hardware_unverified")

    def test_local_below_threshold_denied(self):
        r = h3.run("gate_hw", mode="local", vram_gb=16)
        self.assertFalse(r["ok"])
        self.assertEqual(r["rule"], "hardware_below_threshold")
        self.assertEqual(r["need_gb"], 32.0)

    def test_local_with_enough_vram_ok(self):
        self.assertTrue(h3.run("gate_hw", mode="local", vram_gb=48)["ok"])

    def test_api_mode_needs_external_key(self):
        r = h3.run("gate_hw", mode="api")
        self.assertTrue(r["ok"])
        self.assertTrue(r["requires_external_key"])
        self.assertFalse(r["local_vram_needed"])

    def test_bad_mode_rejected(self):
        self.assertEqual(h3.run("gate_hw", mode="whatever")["rule"], "bad_mode")


class OfficialEntryTests(unittest.TestCase):
    def test_handmade_request_rejected(self):
        r = h3.run("gate_official", entry="handmade_api_request")
        self.assertFalse(r["ok"])
        self.assertEqual(r["rule"], "not_via_official")

    def test_official_entries_ok(self):
        for e in ("h3-prompt-writing", "official_skill", "official_api"):
            self.assertTrue(h3.run("gate_official", entry=e)["ok"], e)

    def test_unspecified_entry_rejected(self):
        self.assertEqual(h3.run("gate_official")["rule"], "entry_unspecified")


class RedLineTests(unittest.TestCase):
    def test_five_red_lines(self):
        rl = h3.run("redlines")["red_lines"]
        self.assertEqual(len(rl), 5)
        joined = " ".join(rl)
        for kw in ("DPAPI", "落盘", "官方入口", "硬件门槛", "留痕"):
            self.assertIn(kw, joined)

    def test_unknown_op_rejected(self):
        with self.assertRaises(ValueError):
            h3.run("nope")


class ModalityTests(unittest.TestCase):
    """R-H251/R-H252：维度表（输入已确认 · 输出已确认 · 分辨率留空带理由）。"""

    def test_input_modalities_four_exact(self):
        self.assertEqual(list(h3.INPUT_MODALITIES),
                         ["文本", "图片", "视频", "音频"])
        self.assertIn("全模态", h3.INPUT_NOTE)

    def test_output_is_video_plus_dual_channel_audio(self):
        self.assertEqual(list(h3.OUTPUT_MODALITIES), ["视频", "原生双声道音频"])
        self.assertIn("不用后期配音", h3.OUTPUT_NOTE)

    def test_output_wording_variants_kept_side_by_side(self):
        # 两处措辞（立体声 / 双声道音频）并排记，不擅自合并
        texts = [v["text"] for v in h3.OUTPUT_WORDING_VARIANTS]
        self.assertIn("原生立体声", texts)
        self.assertIn("原生双声道音频", texts)
        self.assertIn("以官方原文定", h3.OUTPUT_WORDING_NOTE)

    def test_resolution_is_max_2k_via_regenerate(self):
        # 逐字登记：分辨率 = 最高 2K（通过 H3-Regenerate-2K）
        self.assertEqual(h3.RESOLUTION, "最高 2K")
        self.assertIn("H3-Regenerate-2K", h3.RESOLUTION_NOTE)
        self.assertIn("通过", h3.RESOLUTION_NOTE)

    def test_duration_verbatim_keeps_en_dash(self):
        # 逐字登记：2–15 秒（en dash 原样保留，不转成连字符）
        self.assertEqual(h3.DURATION, "2–15 秒")
        self.assertIn("–", h3.DURATION)
        self.assertNotIn("-", h3.DURATION)
        self.assertIn("原样保留", h3.DURATION_NOTE)

    def test_duration_selfconsistency_gate(self):
        # 自校验：逐字文本 ↔ 机械提取区间，必须对得上（不许两处真相）
        self.assertEqual(h3.run("gate_duration")["range"], (2, 15))
        saved = h3.DURATION_SECONDS_RANGE
        try:
            h3.DURATION_SECONDS_RANGE = (1, 30)
            r = h3.run("gate_duration")
            self.assertFalse(r["ok"], r)
            self.assertEqual(r["rule"], "duration_mismatch")
        finally:
            h3.DURATION_SECONDS_RANGE = saved

    def test_frame_rate_verbatim(self):
        # 逐字登记：24 FPS（单位照留大写）
        self.assertEqual(h3.FRAME_RATE, "24 FPS")
        self.assertEqual(h3.FRAME_RATE_FPS, 24)
        self.assertIn("FPS", h3.FRAME_RATE_NOTE)

    def test_verbatim_gate_covers_both_fields(self):
        # R-H255~R-H259：闸是通用的 —— 现有五个字段都要过
        r = h3.run("gate_verbatim")
        self.assertTrue(r["ok"], r)
        self.assertEqual(sorted(r["checked"]),
                         ["audio", "duration", "frame_rate", "language",
                          "param_scale"])
        self.assertTrue(h3.run("gate_verbatim", field="frame_rate")["ok"])
        self.assertTrue(h3.run("gate_verbatim", field="audio")["ok"])
        self.assertTrue(h3.run("gate_verbatim", field="language")["ok"])
        self.assertTrue(h3.run("gate_verbatim", field="param_scale")["ok"])

    def test_verbatim_gate_catches_framerate_mismatch(self):
        saved = h3.FRAME_RATE_FPS
        try:
            h3.FRAME_RATE_FPS = 30
            r = h3.run("gate_verbatim")
            self.assertFalse(r["ok"], r)
            self.assertEqual(r["rule"], "frame_rate_mismatch")
        finally:
            h3.FRAME_RATE_FPS = saved

    def test_audio_verbatim(self):
        # 逐字登记：32 kHz 立体声
        self.assertEqual(h3.AUDIO, "32 kHz 立体声")
        self.assertEqual(h3.AUDIO_SAMPLE_RATE_KHZ, 32)
        self.assertIn("kHz", h3.AUDIO_NOTE)

    def test_wording_variants_now_three(self):
        # 措辞并排表第 3 条：音频行的「立体声」；仍不合并
        texts = [v["text"] for v in h3.OUTPUT_WORDING_VARIANTS]
        self.assertEqual(len(texts), 3)
        self.assertEqual(texts.count("立体声"), 1)
        self.assertIn("立体声 ×2", h3.OUTPUT_WORDING_NOTE)

    def test_verbatim_gate_catches_audio_mismatch(self):
        saved = h3.AUDIO_SAMPLE_RATE_KHZ
        try:
            h3.AUDIO_SAMPLE_RATE_KHZ = 48
            r = h3.run("gate_verbatim")
            self.assertFalse(r["ok"], r)
            self.assertEqual(r["rule"], "audio_mismatch")
        finally:
            h3.AUDIO_SAMPLE_RATE_KHZ = saved

    def test_language_verbatim(self):
        # 逐字登记：稳定支持 11 种语言的对话（「稳定」二字照留）
        self.assertEqual(h3.LANGUAGE, "稳定支持 11 种语言的对话")
        self.assertEqual(h3.LANGUAGE_COUNT, 11)
        self.assertIn("稳定", h3.LANGUAGE_NOTE)
        self.assertIn("以官方为准", h3.LANGUAGE_NOTE)

    def test_verbatim_gate_catches_language_mismatch(self):
        saved = h3.LANGUAGE_COUNT
        try:
            h3.LANGUAGE_COUNT = 13
            r = h3.run("gate_verbatim")
            self.assertFalse(r["ok"], r)
            self.assertEqual(r["rule"], "language_mismatch")
        finally:
            h3.LANGUAGE_COUNT = saved

    def test_param_scale_verbatim_with_decimal(self):
        # 逐字登记：33.1B DiT（扩散 Transformer）—— **小数照留**
        self.assertEqual(h3.PARAM_SCALE, "33.1B DiT（扩散 Transformer）")
        self.assertEqual(h3.PARAM_SCALE_B, 33.1)

    def test_numbers_extractor_supports_decimals(self):
        # R-H259：提取器从整数扩成支持小数（其余字段读数不变）
        self.assertEqual(h3._numbers("33.1B DiT"), [33.1])
        self.assertEqual(h3._numbers("2–15 秒"), [2, 15])
        self.assertEqual(h3._numbers("24 FPS"), [24])

    def test_verbatim_gate_catches_param_scale_mismatch(self):
        saved = h3.PARAM_SCALE_B
        try:
            h3.PARAM_SCALE_B = 32.0
            r = h3.run("gate_verbatim")
            self.assertFalse(r["ok"], r)
            self.assertEqual(r["rule"], "param_scale_mismatch")
        finally:
            h3.PARAM_SCALE_B = saved

    def test_purpose_verbatim_keeps_arrow(self):
        # R-H262：逐字登记「文本 → 带音频视频」（箭头原样保留）
        self.assertEqual(h3.PURPOSE, "文本 → 带音频视频")
        self.assertIn("→", h3.PURPOSE)
        self.assertIn("三处互证", h3.PURPOSE_NOTE)

    def test_purpose_attribution_is_pending(self):
        # 归属是**推断** ⇒ 单独登记待确认（不许当成已确认）
        self.assertIsNone(h3.PURPOSE_ATTRIBUTION)
        self.assertTrue(h3.PURPOSE_ATTRIBUTION_PENDING_REASON.strip())
        self.assertIn("归属", h3.PURPOSE_ATTRIBUTION_PENDING_REASON)
        self.assertIn("确认", h3.PURPOSE_ATTRIBUTION_PENDING_REASON)

    def test_h3_mode_row_filled_and_crosschecked(self):
        # 新行『对应 H3 模式』= T2VA，与四原语第一项逐字一致（互证，不改写原语表）
        self.assertEqual(h3.H3_MODE, "T2VA")
        self.assertEqual(h3.H3_MODE, h3.PRIMITIVES[0]["key"])
        self.assertIn("互证", h3.H3_MODE_NOTE)

    def test_h3_mode_2_is_candidate_without_row_name(self):
        # R-H263：只给了值 I2VA，行名没给 ⇒ 候补行 + 归属待补
        self.assertEqual(h3.H3_MODE_2, "I2VA")
        self.assertEqual(h3.H3_MODE_2, h3.PRIMITIVES[1]["key"])   # 与原语第二项互证
        self.assertIn("互证", h3.H3_MODE_2_NOTE)
        self.assertIsNone(h3.H3_MODE_2_ATTRIBUTION)
        self.assertIn("行名没给", h3.H3_MODE_2_PENDING_REASON)
        self.assertIn("不猜", h3.H3_MODE_2_PENDING_REASON)

    def test_purpose_2_parallels_first_group(self):
        # R-H264：第二组「图片 → 带音频视频」——与第一组结构对仗，与 I2VA 推论配对
        self.assertEqual(h3.PURPOSE_2, "图片 → 带音频视频")
        self.assertIn("→", h3.PURPOSE_2)
        self.assertIn("结构对仗", h3.PURPOSE_2_NOTE)
        self.assertIn("推论配对", h3.PURPOSE_2_NOTE)
        self.assertIn("待主人确认", h3.PURPOSE_2_NOTE)
        self.assertIn("推论配对", h3.H3_MODE_2_PENDING_REASON)

    def test_h3_mode_3_candidate_and_crosschecked(self):
        # R-H265：第三个候补值 FL2VA —— 与四原语第三项互证、行名待补
        self.assertEqual(h3.H3_MODE_3, "FL2VA")
        self.assertEqual(h3.H3_MODE_3, h3.PRIMITIVES[2]["key"])
        self.assertIn("互证", h3.H3_MODE_3_NOTE)
        self.assertIsNone(h3.H3_MODE_3_ATTRIBUTION)
        self.assertIn("不猜", h3.H3_MODE_3_PENDING_REASON)

    def test_candidate_summary_is_a_reading_not_a_conclusion(self):
        # R-H267：候补值三项全到；汇总仍如实标「出现 ≠ 对上了」
        self.assertEqual(list(h3.CANDIDATE_MODES), ["I2VA", "FL2VA", "Ref2VA"])
        self.assertIn("全部到达", h3.CANDIDATE_SUMMARY_NOTE)
        self.assertIn("不等于", h3.CANDIDATE_SUMMARY_NOTE)

    def test_h3_mode_4_candidate_and_crosschecked(self):
        # 第四个候补值 Ref2VA —— 与四原语第四项互证、行名待补
        self.assertEqual(h3.H3_MODE_4, "Ref2VA")
        self.assertEqual(h3.H3_MODE_4, h3.PRIMITIVES[3]["key"])
        self.assertIn("互证", h3.H3_MODE_4_NOTE)
        self.assertIsNone(h3.H3_MODE_4_ATTRIBUTION)
        self.assertIn("不猜", h3.H3_MODE_4_PENDING_REASON)

    def test_purpose_3_keeps_shorter_tail_verbatim(self):
        # R-H266：第三行尾段是「视频」（**比前两行短**）⇒ 逐字保留，不擅自补成「带音频视频」
        self.assertEqual(h3.PURPOSE_3, "首尾帧 → 视频")
        self.assertIn("结构不同", h3.PURPOSE_3_NOTE)
        self.assertIn("不擅自补成", h3.PURPOSE_3_NOTE)
        self.assertNotIn("带音频", h3.PURPOSE_3)      # 值本身一个字没加

    def test_tail_variants_side_by_side(self):
        # R-H268：尾段措辞并排变成 2:2；计数只是读数
        self.assertEqual(list(h3.TAIL_VARIANTS),
                         ["带音频视频", "带音频视频", "视频", "视频"])
        self.assertIn("带音频视频」×2", h3.TAIL_NOTE)
        self.assertIn("视频」×2", h3.TAIL_NOTE)
        self.assertIn("计数只是读数", h3.TAIL_NOTE)

    def test_purpose_4_verbatim_both_separators(self):
        # 第四组：斜杠与箭头都原样保留，输入是双形态
        self.assertEqual(h3.PURPOSE_4, "参考图/视频 → 视频")
        self.assertIn("/", h3.PURPOSE_4)
        self.assertIn("→", h3.PURPOSE_4)
        self.assertIn("双形态", h3.PURPOSE_4_NOTE)
        self.assertIn("推论配对", h3.PURPOSE_4_NOTE)

    def test_groups_note_separates_appearance_from_confirmation(self):
        # 四组齐是「出现」层面的齐，不是「确认」层面的齐
        self.assertIn("出现", h3.GROUPS_NOTE)
        self.assertIn("不是确认", h3.GROUPS_NOTE)

    def test_pending_row_label_has_two_readings(self):
        # R-H269：只给两个字「用例」⇒ 两种读法并排，不擅自判定
        self.assertEqual(h3.PENDING_ROW_LABEL, "用例")
        self.assertIsNone(h3.PENDING_ROW_LABEL_ATTRIBUTION)
        r = h3.PENDING_ROW_LABEL_REASON
        for kw in ("新行名", "要求看用例", "不许猜"):
            self.assertIn(kw, r)

    def test_case_items_verbatim_and_crosschecked(self):
        # R-H270~R-H272：主人五条用例条目逐字齐
        self.assertEqual(len(h3.CASE_ITEMS), 5)
        self.assertEqual(h3.CASE_ITEMS[-2],
                         "生成的视频必须下载到本地，不许只留远程链接")
        self.assertEqual(h3.CASE_ITEMS[-1], "提示词必须走官方结构")
        self.assertIn("5 条", h3.CASE_ITEMS_NOTE)
        self.assertIn("逐条配对", h3.CASE_ITEMS_NOTE)
        self.assertIn("待主人确认", h3.CASE_ITEMS_NOTE)
        # 读法①证据 +1 已记进 PENDING_ROW_LABEL_REASON
        self.assertIn("R-H270", h3.PENDING_ROW_LABEL_REASON)

    def test_case_pairing_is_per_item(self):
        # 配对是**逐条**的，不是笼统"对上了"
        self.assertEqual(len(h3.CASE_PAIRING), 5)
        self.assertEqual([x["owner"] for x in h3.CASE_PAIRING],
                         list(h3.CASE_ITEMS))
        # 第 1、2 条都落在 plaintext_key；第 3 条落在结果落盘
        self.assertEqual(h3.CASE_PAIRING[0]["ours"], "plaintext_key")
        self.assertEqual(h3.CASE_PAIRING[1]["ours"], "plaintext_key")
        self.assertIn("key 具体化", h3.CASE_PAIRING[1]["how"])
        self.assertIn("localized", h3.CASE_PAIRING[2]["ours"])
        self.assertIn("音轨", h3.CASE_PAIRING[2]["how"])

    def test_our_extra_cleared_but_wording_gap_recorded(self):
        # R-H272：主人也列了提示词那条 ⇒ 多出项清零；但**界宽差异单独立账**
        self.assertEqual(list(h3.OUR_EXTRA_CASES), [])
        self.assertIn("多出项清零", h3.OUR_EXTRA_NOTE)
        self.assertEqual(len(h3.CASE_WORDING_GAPS), 1)
        gap = h3.CASE_WORDING_GAPS[0]
        self.assertEqual(gap["owner"], "提示词必须走官方结构")
        self.assertIn("六段式", gap["ours"])
        self.assertIn("（宽）", gap["gap"])
        self.assertIn("（窄", gap["gap"])
        self.assertIn("不擅自", gap["gap"])
        # 那条闸仍然真在带牙用例里（没被删、也没被改名）
        self.assertTrue(any("六段式" in c for c in h3.TEETH_CASES))

    def test_wording_gap_closed_by_owner(self):
        # R-H273：主人明示「H3 有文档化的六段式输出格式」⇒ 界宽差异**闭合**
        gap = h3.CASE_WORDING_GAPS[0]
        self.assertTrue(gap.get("closed"))
        self.assertIn("文档化的六段式", gap["closed_by"])
        self.assertIn("同指", h3.CASE_WORDING_GAPS[0]["closed_by"])

    def test_prose_reject_reason_has_source(self):
        # 散文被拒**不是风格偏好**，有理由：散文会省略结构显式化的关系
        self.assertIn("结构显式化", h3.PROSE_REJECT_REASON)
        self.assertIn("主人提供", h3.PROSE_REJECT_REASON)
        # 理由接到了闸的返回值里（不只在文档里）
        r = h3.run("gate_prompt", prompt="一个女孩在雨里跑过街道非常电影感")
        self.assertEqual(r["rule"], "prose_prompt_rejected")
        self.assertIn("结构显式化", r["why"])

    def test_red_lines_row_is_two_readings(self):
        # R-H273：「五条红线」按老规矩登记（两读法），并对我方 RED_LINES 对账
        self.assertEqual(h3.PENDING_ROW_LABEL_2, "五条红线")
        self.assertIsNone(h3.PENDING_ROW_LABEL_2_ATTRIBUTION)
        r = h3.PENDING_ROW_LABEL_2_REASON
        for kw in ("新的行名", "宣告红线清单", "不擅自判定"):
            self.assertIn(kw, r)
        self.assertEqual(len(h3.RED_LINES), 5)   # 我方恰好也是五条（对账读数）
        self.assertIn("5 条", r)

    def test_red_line_item_1_crosschecked(self):
        # R-H274 → R-H278：主人红线条目（现 8 条）逐字 + 与我方红线逐条配对
        self.assertEqual(len(h3.RED_LINE_ITEMS), 8)
        self.assertEqual(h3.RED_LINE_ITEMS[0], "密钥只存 DPAPI")
        self.assertEqual(h3.RED_LINE_ITEMS[2], "结果必须落盘")
        self.assertEqual(h3.RED_LINE_ITEMS[3], "不绕官方入口")
        self.assertEqual(h3.RED_LINE_ITEMS[4],
                         "必须走官方 skill 脚本，不许自己拼 API 请求")
        self.assertEqual(h3.RED_LINE_ITEMS[5], "硬件门槛先验")
        self.assertEqual(h3.RED_LINE_ITEMS[6],
                         "本地跑需要 32GB 显存起步，先验再装")
        self.assertEqual(h3.RED_LINE_ITEMS[7], "每次操作留痕")
        self.assertTrue(str(h3.RED_LINES[0]).startswith("密钥只存 DPAPI"))
        note = h3.RED_LINE_ITEMS_NOTE
        for kw in ("逐条配对", "我方更具体", "待主人确认", "不擅自补齐"):
            self.assertIn(kw, note)
        # 读法②证据 +1 已记进 PENDING_ROW_LABEL_2_REASON
        self.assertIn("R-H274", h3.PENDING_ROW_LABEL_2_REASON)

    def test_red_line_pairing_is_per_item(self):
        # 配对逐条：① 原理层 ② 同条具体化 ③ 我方第二条；且**条数不同也要说清**
        self.assertEqual(len(h3.RED_LINE_PAIRING), len(h3.RED_LINE_ITEMS))
        self.assertIn("原理层", h3.RED_LINE_PAIRING[0]["how"])
        self.assertIn("具体化层", h3.RED_LINE_PAIRING[1]["how"])
        self.assertIn("RED_LINES[1]", h3.RED_LINE_PAIRING[2]["ours"])
        self.assertIn("我方更具体", h3.RED_LINE_PAIRING[2]["how"])
        self.assertIn("RED_LINES[2]", h3.RED_LINE_PAIRING[3]["ours"])
        # 三对主人条目 ≈ 我方第一 / 第三 / 第四条（说明白「条数不等」这件事）
        self.assertIn("合起来", h3.RED_LINE_ITEMS_NOTE)
        self.assertIn("RED_LINES[2]", h3.RED_LINE_PAIRING[4]["ours"])
        self.assertIn("具体化层", h3.RED_LINE_PAIRING[4]["how"])
        self.assertIn("RED_LINES[3]", h3.RED_LINE_PAIRING[5]["ours"])
        self.assertIn("我方更具体", h3.RED_LINE_PAIRING[5]["how"])
        self.assertIn("RED_LINES[3]", h3.RED_LINE_PAIRING[6]["ours"])
        self.assertIn("具体化层", h3.RED_LINE_PAIRING[6]["how"])
        self.assertIn("先验再装", h3.RED_LINE_PAIRING[6]["how"])
        self.assertIn("RED_LINES[4]", h3.RED_LINE_PAIRING[7]["ours"])

    def test_merge_reading_is_computed_not_written(self):
        # R-H278 归并读数：主人 8 条 → 识别 3 对（原理 + 具体化）→ 归并 5 组，
        #              且 5 组与我方 5 条红线**一一对应（双射）**⇒ 与行名「五条红线」吻合
        mr = h3.RED_LINE_MERGE_READING
        self.assertEqual(mr["owner_count"], 8)
        self.assertEqual(mr["ours_unmatched"], ())
        self.assertTrue(str(mr["ours_unmatched_reason"]).strip(),
                        "有理由的空必须带理由（§57）")
        self.assertTrue(mr["derived"], "归并读数是**推论** ⇒ 必须标 derived=True")
        self.assertIn("推论", mr["derivation_note"])
        self.assertIn("待主人", mr["derivation_note"])
        g = h3.run("gate_merge")
        self.assertTrue(g["ok"], g)
        self.assertEqual(g["merged_owner_count"], 5)
        self.assertEqual(len(g["map"]), 5)
        self.assertEqual(g["arithmetic"], "8 - 3 = 5")
        self.assertEqual(g["plus_unmatched"], "5 + 0 = 5")
        self.assertTrue(g["bijective"])
        self.assertEqual(g["row_label"], "五条红线")
        self.assertEqual(g["row_label_count"], 5)
        self.assertTrue(g["matches_row_label"])
        self.assertTrue(g["derived"])
        self.assertIn("推论", g["note"])

    def test_merge_map_covers_every_owner_item_exactly_once(self):
        # 覆盖性：主人每一条都被归并用到 —— 一条不剩、一条不重
        used = [x for grp in h3.RED_LINE_MERGE_MAP for x in grp["owner_items"]]
        self.assertEqual(len(used), len(h3.RED_LINE_ITEMS))
        self.assertEqual(sorted(used), sorted(h3.RED_LINE_ITEMS))

    def test_merge_reading_goes_red_when_written_number_is_stale(self):
        # 带牙①：把手写的归并读数改错 ⇒ 闸必须当场红（读数是算出来的，不是抄来的）
        saved = h3.RED_LINE_MERGE_READING["merged_owner_count"]
        h3.RED_LINE_MERGE_READING["merged_owner_count"] = 99
        try:
            g = h3.run("gate_merge")
        finally:
            h3.RED_LINE_MERGE_READING["merged_owner_count"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "merge_reading_stale")

    def test_merge_reading_goes_red_when_owner_item_uncovered(self):
        # 带牙②：把主人的一条从映射里换掉 ⇒ 覆盖性破（漏一条 + 多一条）⇒ 红
        saved = h3.RED_LINE_MERGE_MAP[0]["owner_items"]
        h3.RED_LINE_MERGE_MAP[0]["owner_items"] = ("这条盘上没有",)
        try:
            g = h3.run("gate_merge")
        finally:
            h3.RED_LINE_MERGE_MAP[0]["owner_items"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "merge_map_not_covering")

    def test_merge_reading_goes_red_when_not_bijective(self):
        # 带牙③：两组指同一条我方红线 ⇒ 双射破（多对一）⇒ 红
        saved = h3.RED_LINE_MERGE_MAP[1]["ours"]
        h3.RED_LINE_MERGE_MAP[1]["ours"] = "RED_LINES[0]"
        try:
            g = h3.run("gate_merge")
        finally:
            h3.RED_LINE_MERGE_MAP[1]["ours"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "merge_map_not_bijective")

    def test_hw_threshold_matches_owner_and_disk(self):
        # R-H278 ⑦：主人给的显存门槛数字必须与盘上 HARDWARE 一致，且顺序是「先验再装」
        g = h3.run("gate_hw_threshold")
        self.assertTrue(g["ok"], g)
        self.assertEqual(g["owner_gb"], g["disk_gb"])
        self.assertTrue(g["ordered_before_install"])
        self.assertIn("先验再装", g["owner_item"])

    def test_hw_threshold_goes_red_when_number_drifts(self):
        # 带牙：盘上的门槛数字被偷偷改成 24 ⇒ 红（两边各写一遍就会漂，必须有一处对账）
        saved = h3.HARDWARE["local_min_vram_gb"]
        h3.HARDWARE["local_min_vram_gb"] = 24.0
        try:
            g = h3.run("gate_hw_threshold")
        finally:
            h3.HARDWARE["local_min_vram_gb"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "hw_threshold_drift")


    def test_trace_kind_gap_recorded_not_unified(self):
        # R-H279：主人给 source_kind=h3、盘上钉 h3mini ⇒ **取值差异入账**，不许静默统一
        gap = h3.TRACE_KIND_GAP
        self.assertEqual(gap["owner_kind"], "h3")
        self.assertEqual(h3.TRACE_SOURCE_KIND, "h3mini")
        self.assertTrue(gap["kind_differs"])
        self.assertIsNone(gap["resolution"], "谁对 ⇒ 待主人定，不许自己填")
        self.assertIn("h3", str(gap["owner_spec"]))
        self.assertEqual(str(gap["prefix_agreed"]), "写 trace_store")
        self.assertIsNone(h3.TRACE_KIND_ROW_ATTRIBUTION)
        self.assertTrue(str(h3.TRACE_KIND_ROW_REASON).strip())

    def test_gate_source_kind_ok_and_self_reports_dispute(self):
        g = h3.run("gate_source_kind", source_kind="h3mini")
        self.assertTrue(g["ok"], g)
        self.assertTrue(g["kind_disputed"], "取值有争议 ⇒ 闸必须自报，不许假装没有")
        self.assertEqual(g["owner_kind"], "h3")
        self.assertIn("待主人", g["note"])

    def test_gate_source_kind_missing_and_mismatch(self):
        # 无源不许记（无痕即未发生）
        r = h3.run("gate_source_kind")
        self.assertFalse(r["ok"], r)
        self.assertEqual(r["rule"], "source_kind_missing")
        # 错值必须红，且红里要带出「主人给的是 h3」
        r2 = h3.run("gate_source_kind", source_kind="h3")
        self.assertFalse(r2["ok"], r2)
        self.assertEqual(r2["rule"], "source_kind_mismatch")
        self.assertEqual(r2["owner_kind"], "h3")
        self.assertTrue(r2["kind_disputed"])

    def test_trace_kind_gap_stale_goes_red(self):
        # 带牙①：只把盘上常量改了、没改记录 ⇒ 记录与盘上不一致 ⇒ 红
        saved = h3.TRACE_SOURCE_KIND
        h3.TRACE_SOURCE_KIND = "h3"
        try:
            g = h3.run("gate_source_kind", source_kind="h3")
        finally:
            h3.TRACE_SOURCE_KIND = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "trace_kind_gap_stale")
        self.assertTrue(h3.run("gate_source_kind", source_kind="h3mini")["ok"])

    def test_trace_kind_silent_unify_goes_red(self):
        # 带牙②：把两边都改成一致、**却没有主人一句话** ⇒ 红（静默统一比起留差异更糟）
        saved_kind = h3.TRACE_SOURCE_KIND
        saved_ours = h3.TRACE_KIND_GAP["ours_kind"]
        saved_diff = h3.TRACE_KIND_GAP["kind_differs"]
        h3.TRACE_SOURCE_KIND = "h3"
        h3.TRACE_KIND_GAP["ours_kind"] = "h3"
        h3.TRACE_KIND_GAP["kind_differs"] = False
        try:
            g = h3.run("gate_source_kind", source_kind="h3")
        finally:
            h3.TRACE_SOURCE_KIND = saved_kind
            h3.TRACE_KIND_GAP["ours_kind"] = saved_ours
            h3.TRACE_KIND_GAP["kind_differs"] = saved_diff
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "trace_kind_silently_unified")
        self.assertTrue(h3.run("gate_source_kind", source_kind="h3mini")["ok"])

    def test_trace_kind_gap_flag_is_recomputed(self):
        # 带牙③：把「差异」那一格手写成 False ⇒ 红（那几格必须机械重算）
        saved = h3.TRACE_KIND_GAP["kind_differs"]
        h3.TRACE_KIND_GAP["kind_differs"] = False
        try:
            g = h3.run("gate_source_kind", source_kind="h3mini")
        finally:
            h3.TRACE_KIND_GAP["kind_differs"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "trace_kind_gap_stale")

    def test_hardware_threshold_row_is_blank_with_reason(self):
        # R-H279：新行名「本地部署的硬件门槛」+ 表头「项目」，内容截断 ⇒ 留空带理由（§57）
        self.assertEqual(h3.PENDING_ROW_LABEL_3, "本地部署的硬件门槛")
        self.assertEqual(h3.PENDING_ROW_LABEL_3_TABLE_HEADER, "项目")
        self.assertIsNone(h3.PENDING_ROW_LABEL_3_ATTRIBUTION)
        r = h3.PENDING_ROW_LABEL_3_REASON
        for kw in ("新的一行", "重复/展开", "不擅自判定", "实测读数"):
            self.assertIn(kw, r)
        self.assertIn("pending_row_label_3_attribution", h3.OPEN_FIELDS)
        self.assertIn("trace_kind_row_attribution", h3.OPEN_FIELDS)
        self.assertTrue(h3.run("gate_blank")["ok"], "空必须带理由 ⇒ gate_blank 仍应绿")


    def test_hw_table_peak_row_filled_verbatim(self):
        # R-H281：峰值显存 = 31.7 GB（三个检查点都一样）—— 逐字 + 机器数 + 来源 + 「主人重新给的」
        self.assertEqual(h3.HW_TABLE_HEADER, "项目")
        rows = h3.HW_TABLE_ROWS
        self.assertEqual([r["label"] for r in rows],
                         ["峰值显存", "系统内存", "推荐检查点", "8 秒片段耗时",
                          "32GB 显存"])
        peak = rows[0]
        self.assertEqual(peak["value"], 31.7)
        self.assertEqual(peak["value_verbatim"], "31.7 GB（三个检查点都一样）")
        self.assertIn("R-H281", str(peak["source"]))
        self.assertTrue(str(peak["reaffirmed_by_owner"]).strip(),
                        "与盘上旧数同值 ⇒ 必须写清是主人**重新**给的")
        g = h3.run("gate_hw_rows")
        self.assertTrue(g["ok"], g)
        self.assertEqual(g["row_count"], 5)
        self.assertTrue(g["rows"][0]["has_value"])
        self.assertTrue(g["rows"][1]["has_value"])
        self.assertTrue(g["rows"][2]["has_value"])
        self.assertTrue(g["rows"][3]["has_value"])
        self.assertFalse(g["rows"][4]["has_value"])
        self.assertFalse(g["complete"], "第五行「32GB 显存」还没值 ⇒ 表未齐")

    def test_hw_row_blank_without_reason_goes_red(self):
        # 带牙：把**空着的那行**的理由抹掉 ⇒ 红（有理由的空 ≠ 没写理由的空）
        # R-H286 起「空」这一格在第五行「32GB 显存」（前四行都已有值）
        row = h3.HW_TABLE_ROWS[4]
        saved = row["pending_reason"]
        row["pending_reason"] = ""
        try:
            g = h3.run("gate_hw_rows")
        finally:
            row["pending_reason"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "hw_row_blank_without_reason")
        self.assertTrue(h3.run("gate_hw_rows")["ok"])

    def test_hw_row_value_without_source_goes_red(self):
        # 带牙：填了数却没写来源 ⇒ 红（无源数字不许进表）
        row = h3.HW_TABLE_ROWS[0]
        saved = (row["value"], row["source"])
        row["value"] = 24.0
        row["source"] = ""
        try:
            g = h3.run("gate_hw_rows")
        finally:
            row["value"], row["source"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "hw_row_value_without_source")

    def test_hw_row_old_number_reused_goes_red(self):
        # 带牙（R-H280 立 · R-H281 第一次被主人真触发）：值 = 盘上旧数，
        # 却没写「主人重新给的」 ⇒ 红（数一样不代表来源一样）
        row = h3.HW_TABLE_ROWS[0]
        saved = (row["value"], row["value_verbatim"], row["source"],
                 row["reaffirmed_by_owner"])
        row["value"] = h3.HARDWARE["local_peak_vram_gb"]
        row["value_verbatim"] = "31.7 GB"
        row["source"] = "R-H281"
        row["reaffirmed_by_owner"] = None
        try:
            g = h3.run("gate_hw_rows")
        finally:
            (row["value"], row["value_verbatim"], row["source"],
             row["reaffirmed_by_owner"]) = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "hw_row_old_number_reused")
        self.assertEqual(g["old_on_disk"], 31.7)
        # 写明是主人**重新**给的 ⇒ 放行（差异不在数字，在来源）
        row["value"] = h3.HARDWARE["local_peak_vram_gb"]
        row["value_verbatim"] = "31.7 GB"
        row["source"] = "主人提供 · R-H281"
        row["reaffirmed_by_owner"] = "主人 R-H281 重新给出"
        try:
            g2 = h3.run("gate_hw_rows")
        finally:
            (row["value"], row["value_verbatim"], row["source"],
             row["reaffirmed_by_owner"]) = saved
        self.assertTrue(g2["ok"], g2)
        self.assertTrue(g2["rows"][0]["has_value"], "第一行有值")
        self.assertTrue(g2["rows"][1]["has_value"], "第二行有值")
        self.assertTrue(g2["rows"][2]["has_value"], "第三行有值")
        self.assertTrue(g2["rows"][3]["has_value"], "第四行有值")
        self.assertFalse(g2["rows"][4]["has_value"], "第五行「32GB 显存」还没值 ⇒ 表未齐")
        self.assertFalse(g2["complete"], "表未齐（第五行仍空）")
        self.assertTrue(h3.run("gate_hw_rows")["ok"])

    def test_hw_row_verbatim_must_match_value(self):
        # 带牙①：逐字没写 ⇒ 红；带牙②：逐字与机器数对不上 ⇒ 红
        row = h3.HW_TABLE_ROWS[0]
        saved = row["value_verbatim"]
        row["value_verbatim"] = ""
        try:
            g = h3.run("gate_hw_rows")
        finally:
            row["value_verbatim"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "hw_row_value_without_verbatim")
        row["value_verbatim"] = "32 GB（三个检查点都一样）"
        try:
            g2 = h3.run("gate_hw_rows")
        finally:
            row["value_verbatim"] = saved
        self.assertFalse(g2["ok"], g2)
        self.assertEqual(g2["rule"], "hw_row_verbatim_mismatch")
        self.assertTrue(h3.run("gate_hw_rows")["ok"])

    def test_hw_row_memory_must_not_equal_vram(self):
        # 带牙：把「系统内存」填成上一行的显存数 ⇒ 红（内存 ≠ 显存：两个数一样必有一处抄错）
        row = h3.HW_TABLE_ROWS[1]
        saved = dict(row)
        row.update({"value": h3.HW_TABLE_ROWS[0]["value"],
                    "value_verbatim": "31.7 GB",
                    "units": ("GB",), "extra_numbers": (),
                    "ignored_numbers": (), "ignored_reason": None,
                    "source": "主人提供 · R-H282",
                    "reaffirmed_by_owner": "主人 R-H282 重新给出"})
        try:
            g = h3.run("gate_hw_rows")
        finally:
            row.update(saved)
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "hw_row_memory_equals_vram")
        self.assertTrue(h3.run("gate_hw_rows")["ok"])

    def test_hw_row_system_memory_filled_dual_units(self):
        # R-H282：系统内存 = 128 GB 预算（完整 INT8 峰值 93.1 GiB）
        # **一格两数两单位** ⇒ 逐字并存，主数 + 其余数 + 两个单位都记着
        row = h3.HW_TABLE_ROWS[1]
        self.assertEqual(row["label"], "系统内存")
        self.assertEqual(row["value"], 128)
        self.assertEqual(row["value_verbatim"],
                         "128 GB 预算（完整 INT8 峰值 93.1 GiB）")
        self.assertEqual(tuple(row["units"]), ("GB", "GiB"))
        self.assertEqual(tuple(row["extra_numbers"]), (93.1,))
        g = h3.run("gate_hw_rows")
        self.assertTrue(g["ok"], g)
        self.assertTrue(g["rows"][1]["has_value"])
        self.assertFalse(g["complete"], "第三行「推荐检查点」还没值 ⇒ 表未齐")
        self.assertIn("不合并", str(g["rows"][1]["note"]))

    def test_hw_row_numbers_must_all_be_accounted(self):
        # 带牙（R-H286 核心）：把同格里的 93.1 从 extra_numbers 拿掉 ⇒ 那个数**没交代** ⇒ 红
        row = h3.HW_TABLE_ROWS[1]
        saved = row["extra_numbers"]
        row["extra_numbers"] = ()
        try:
            g = h3.run("gate_hw_rows")
        finally:
            row["extra_numbers"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "hw_row_number_unaccounted")
        self.assertIn(93.1, g["in_verbatim"])
        self.assertTrue(h3.run("gate_hw_rows")["ok"])

    def test_hw_row_ignored_number_needs_reason(self):
        # 带牙：豁免可以，但**必须写理由** —— 不写就是静默丢数
        row = h3.HW_TABLE_ROWS[1]
        saved = row["ignored_reason"]
        row["ignored_reason"] = ""
        try:
            g = h3.run("gate_hw_rows")
        finally:
            row["ignored_reason"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "hw_row_ignore_without_reason")
        self.assertTrue(h3.run("gate_hw_rows")["ok"])

    def test_hw_row_scope_missing_goes_red(self):
        # 带牙：每行都要写「这行说的是哪个量」—— 表里有两行都在说「显存」
        row = h3.HW_TABLE_ROWS[4]
        saved = row["scope"]
        row["scope"] = ""
        try:
            g = h3.run("gate_hw_rows")
        finally:
            row["scope"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "hw_row_scope_missing")
        self.assertTrue(h3.run("gate_hw_rows")["ok"])

    def test_hw_row_unit_drift_goes_red(self):
        # 带牙：把逐字里的 GiB 顺手写成 GB（换成数字没变）⇒ 红（1 GiB ≠ 1 GB）
        row = h3.HW_TABLE_ROWS[1]
        saved = row["value_verbatim"]
        row["value_verbatim"] = "128 GB 预算（完整 INT8 峰值 93.1 GB）"
        try:
            g = h3.run("gate_hw_rows")
        finally:
            row["value_verbatim"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "hw_row_unit_drift")
        self.assertEqual(g["in_verbatim"], ["GB", "GB"])
        self.assertEqual(g["kept"], ["GB", "GiB"])
        self.assertTrue(h3.run("gate_hw_rows")["ok"])

    def test_hw_row_recommended_checkpoint_filled_with_sibling(self):
        # R-H283：推荐检查点 = 精简 INT8（约 21 GB，速度最快）
        # **非数值行值** + 同格一个数 + 与盘上旧记录**前缀一致但整串不同** ⇒ 三样都要记着
        row = h3.HW_TABLE_ROWS[2]
        self.assertEqual(row["label"], "推荐检查点")
        self.assertEqual(row["value"], "精简 INT8")
        self.assertEqual(row["value_verbatim"], "精简 INT8（约 21 GB，速度最快）")
        self.assertEqual(tuple(row["extra_numbers"]), (21,))
        self.assertEqual(tuple(row["units"]), ("GB",))
        self.assertIn("前缀一致", str(row["prefix_sibling"]))
        self.assertIn("不合并", str(row["prefix_sibling"]))
        g = h3.run("gate_hw_rows")
        self.assertTrue(g["ok"], g)
        self.assertTrue(g["rows"][2]["has_value"])
        self.assertFalse(g["complete"], "第四行「8 秒片段耗时」还没值 ⇒ 表未齐")

    def test_hw_row_checkpoint_old_record_not_reused(self):
        # 带牙：把第三行填成**盘上那条旧记录**（同一句话）却没写「主人重新给的」 ⇒ 红
        row = h3.HW_TABLE_ROWS[2]
        saved = dict(row)
        row.update({"value": h3.HARDWARE["local_slim_checkpoint"],
                    "value_verbatim": str(h3.HARDWARE["local_slim_checkpoint"]),
                    "units": (), "extra_numbers": (),
                    "source": "R-H282"})
        try:
            g = h3.run("gate_hw_rows")
        finally:
            row.update(saved)
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "hw_row_old_number_reused")
        self.assertTrue(h3.run("gate_hw_rows")["ok"])

    def test_hw_row_prefix_sibling_unrecorded_goes_red(self):
        # 带牙：把「与旧记录前缀一致」那句抹掉 ⇒ 红（像但不等于，不许静默合并）
        row = h3.HW_TABLE_ROWS[2]
        saved = row["prefix_sibling"]
        row["prefix_sibling"] = None
        try:
            g = h3.run("gate_hw_rows")
        finally:
            row["prefix_sibling"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "hw_row_prefix_sibling_unrecorded")
        self.assertEqual(g["common_prefix"], "精简 INT8")
        self.assertTrue(h3.run("gate_hw_rows")["ok"])

    def test_hw_row_non_numeric_value_must_appear_verbatim(self):
        # 带牙：非数值行值被改写成简称 ⇒ 红（名字也不许改写）
        row = h3.HW_TABLE_ROWS[2]
        saved = row["value"]
        row["value"] = "INT8 精简版"
        try:
            g = h3.run("gate_hw_rows")
        finally:
            row["value"] = saved
        self.assertFalse(g["ok"], g)
        self.assertEqual(g["rule"], "hw_row_verbatim_mismatch")
        self.assertTrue(h3.run("gate_hw_rows")["ok"])

    def test_hw_row_eight_second_filled_two_tiers(self):
        # R-H286：8 秒片段耗时 = 0.3MP 约 2 分钟 / 1.0MP 约 13 分钟
        # 🔴 这一格有**四个数**，其中 0.3 / 1.0 **黏在单位 MP 上**
        #    —— 上一刀那把「独立数字」尺子会把它们跳过 ⇒ 本刀换成「每个数都要有交代」
        row = h3.HW_TABLE_ROWS[3]
        self.assertEqual(row["label"], "8 秒片段耗时")
        self.assertEqual(row["value_verbatim"], "0.3MP 约 2 分钟 / 1.0MP 约 13 分钟")
        self.assertEqual(tuple(row["extra_numbers"]), (0.3, 2, 1.0, 13))
        self.assertEqual(tuple(row["ignored_numbers"]), ())
        self.assertEqual(tuple(row["units"]), ("MP", "分钟", "MP", "分钟"))
        self.assertIn("能生成多长", str(row["scope"]))
        g = h3.run("gate_hw_rows")
        self.assertTrue(g["ok"], g)
        self.assertTrue(g["rows"][3]["has_value"])

    def test_hw_row_32gb_vram_blank_with_reason(self):
        # R-H286：第五行「32GB 显存」只有行名 ⇒ 留空带理由 + **两读法并排**
        row = h3.HW_TABLE_ROWS[4]
        self.assertEqual(row["label"], "32GB 显存")
        self.assertIsNone(row["value"])
        r = str(row["pending_reason"])
        for kw in ("两种读法", "新的一行", "补充说明", "不擅自判定"):
            self.assertIn(kw, r)
        # scope 必须写明它与第一行「峰值显存 31.7 GB」**不是同一个量**
        self.assertIn("31.7", str(row["scope"]))
        self.assertIn("不擅自合并", str(row["scope"]))
        p = h3.run("pending")
        self.assertEqual(p["blank_rows"], ["32GB 显存"])
        self.assertEqual(p["total"], len(p["open_fields"]) + 1)
        self.assertEqual(p["total"], 11)

    def test_pending_total_covers_both_places(self):
        # 「待补位」分散两处（字段格 + 表行）⇒ 必须给合计数，且**两边的清单都要列**
        p = h3.run("pending")
        self.assertTrue(p["ok"], p)
        self.assertEqual(len(p["open_fields"]), len(h3.OPEN_FIELDS))
        self.assertEqual(p["blank_rows"], ["32GB 显存"])
        self.assertEqual(p["total"], len(p["open_fields"]) + len(p["blank_rows"]))
        self.assertEqual(p["total"], 11)

    def test_case_reading_counts_from_disk(self):
        # 用例读数是**从盘上数出来的**，不是手写
        rd = h3.run("test_cases")
        self.assertTrue(rd["ok"], rd)
        self.assertEqual(rd["file"], h3.TEST_FILE)
        self.assertGreater(rd["count"], 0, "读到 0 条 ⇒ 先怀疑读取路径（§45）")
        self.assertEqual(len(rd["teeth_cases"]), 3)

    def test_case_reading_red_when_file_missing(self):
        # 文件读不到 ⇒ 红（**不许报数字**）
        from pathlib import Path as _P
        import tempfile as _t
        rd = h3.test_case_reading(_P(_t.mkdtemp()))
        self.assertFalse(rd["ok"])
        self.assertEqual(rd["rule"], "test_file_missing")

    def test_purpose_3_attribution_pending_two_things(self):
        self.assertIsNone(h3.PURPOSE_3_ATTRIBUTION)
        r = h3.PURPOSE_3_PENDING_REASON
        for kw in ("归属", "措辞差异", "不许猜"):
            self.assertIn(kw, r)

    def test_table_opened_by_new_row(self):
        # 八行齐的表被新行打开若干格 ⇒ 仍如实标未齐；R-H279 起 **10 格**
        # （+ 本地部署的硬件门槛那行 + 红线⑧具体化那条的归属）
        # 注：下面只硬写**一处**清单（认账用），第二处断言直接读 OPEN_FIELDS
        #     —— 两处手写迟早各漂各的（R-H278 的教训），所以只留一处。
        self.assertEqual(sorted(h3.OPEN_FIELDS),
                         ["h3_mode_2_attribution", "h3_mode_3_attribution",
                          "h3_mode_4_attribution", "pending_row_label_2_attribution",
                          "pending_row_label_3_attribution",
                          "pending_row_label_attribution", "purpose_3_attribution",
                          "purpose_4_attribution", "purpose_attribution",
                          "trace_kind_row_attribution"])
        r = h3.run("gate_blank")
        self.assertTrue(r["ok"], r)          # 有理由的空 ⇒ 放行
        self.assertEqual(r["open_fields"], sorted(h3.OPEN_FIELDS))
        self.assertEqual(len(r["open_fields"]), 10)
        self.assertFalse(r["table_complete"])

    def test_audio_remote_only_rejected(self):
        # 红线②扩成「视频 + 音轨一起落盘」：音轨只留远程 ⇒ 单独报 audio_not_localized
        r = h3.run("gate_localize", targets=["work/out.mp4"],
                   audio=["https://cdn.x/a.mp3"])
        self.assertFalse(r["ok"], r)
        self.assertEqual(r["rule"], "audio_not_localized")
        ok = h3.run("gate_localize", targets=["work/out.mp4"],
                    audio=["work/out.mp3"])
        self.assertTrue(ok["ok"])

    def test_gate_blank_passes_because_reason_present(self):
        self.assertTrue(h3.run("gate_blank")["ok"])

    def test_gate_blank_rejects_reasonless_blank(self):
        # 待补位表已清空 ⇒ 用合成的一条"无理由的空"验闸**仍然带牙**
        saved = dict(h3.OPEN_FIELDS)
        try:
            h3.OPEN_FIELDS["synthetic_gap"] = "synthetic_reason"
            r = h3.run("gate_blank")
            self.assertFalse(r["ok"], r)
            self.assertEqual(r["rule"], "blank_without_reason")
            self.assertEqual(r["blank"], ["synthetic_gap"])
        finally:
            h3.OPEN_FIELDS.clear()
            h3.OPEN_FIELDS.update(saved)

    def test_status_carries_both_modality_columns(self):
        st = h3.run("status")
        self.assertEqual(st["input_modalities"], ["文本", "图片", "视频", "音频"])
        self.assertEqual(st["output_modalities"], ["视频", "原生双声道音频"])
        self.assertEqual(st["resolution"], "最高 2K")
        self.assertEqual(st["duration"], "2–15 秒")
        self.assertEqual(st["duration_seconds_range"], [2, 15])
        self.assertEqual(st["frame_rate"], "24 FPS")
        self.assertEqual(st["frame_rate_fps"], 24)
        self.assertEqual(st["audio"], "32 kHz 立体声")
        self.assertEqual(st["audio_sample_rate_khz"], 32)
        self.assertEqual(st["language"], "稳定支持 11 种语言的对话")
        self.assertEqual(st["language_count"], 11)
        self.assertEqual(st["param_scale"], "33.1B DiT（扩散 Transformer）")
        self.assertEqual(st["param_scale_b"], 33.1)
        self.assertEqual(st["purpose"], "文本 → 带音频视频")
        self.assertIsNone(st["purpose_attribution"])
        self.assertTrue(st["purpose_attribution_pending_reason"])
        self.assertEqual(st["h3_mode"], "T2VA")
        self.assertEqual(st["h3_mode_2"], "I2VA")
        self.assertEqual(st["purpose_2"], "图片 → 带音频视频")
        self.assertEqual(st["h3_mode_3"], "FL2VA")
        self.assertEqual(st["purpose_3"], "首尾帧 → 视频")
        self.assertEqual(st["tail_variants"],
                         ["带音频视频", "带音频视频", "视频", "视频"])
        self.assertEqual(st["purpose_4"], "参考图/视频 → 视频")
        self.assertEqual(len(st["case_items"]), 5)
        self.assertEqual(len(st["case_pairing"]), 5)
        self.assertEqual(len(st["our_extra_cases"]), 0)
        self.assertEqual(len(st["case_wording_gaps"]), 1)
        self.assertEqual(st["pending_row_label_2"], "五条红线")
        self.assertEqual(st["red_lines_count"], 5)
        self.assertEqual(len(st["red_line_items"]), 8)
        self.assertEqual(len(st["red_line_pairing"]), 8)
        self.assertTrue(st["red_line_merge_gate"]["ok"], st["red_line_merge_gate"])
        self.assertEqual(st["trace_source_kind"], "h3mini")
        self.assertEqual(st["trace_kind_gap"]["owner_kind"], "h3")
        self.assertTrue(st["trace_kind_gate"]["kind_disputed"])
        self.assertEqual(st["pending_row_label_3"], "本地部署的硬件门槛")
        self.assertEqual(st["pending_row_label_3_table_header"], "项目")
        self.assertEqual(st["hw_table_header"], "项目")
        self.assertEqual(st["hw_table_rows"][0]["label"], "峰值显存")
        self.assertTrue(st["hw_rows_gate"]["ok"], st["hw_rows_gate"])
        self.assertFalse(st["hw_rows_gate"]["complete"])
        self.assertEqual(st["pending"]["total"], 11)
        self.assertIn("不是确认", st["groups_note"])
        self.assertEqual(st["h3_mode_4"], "Ref2VA")
        self.assertEqual(st["candidate_modes"], ["I2VA", "FL2VA", "Ref2VA"])
        self.assertFalse(st["table_complete"])

    def test_modalities_op_shape(self):
        m = h3.run("modalities")
        self.assertEqual(m["input"], ["文本", "图片", "视频", "音频"])
        self.assertEqual(m["output"], ["视频", "原生双声道音频"])
        self.assertEqual(m["resolution"], "最高 2K")
        self.assertEqual(m["duration"], "2–15 秒")
        self.assertEqual(m["frame_rate"], "24 FPS")
        self.assertEqual(m["audio"], "32 kHz 立体声")
        self.assertEqual(m["language"], "稳定支持 11 种语言的对话")
        self.assertEqual(m["param_scale"], "33.1B DiT（扩散 Transformer）")
        self.assertEqual(m["purpose"], "文本 → 带音频视频")
        self.assertIsNone(m["purpose_attribution"])
        self.assertEqual(m["h3_mode"], "T2VA")
        self.assertEqual(m["h3_mode_2"], "I2VA")
        self.assertEqual(m["purpose_2"], "图片 → 带音频视频")
        self.assertEqual(m["h3_mode_3"], "FL2VA")
        self.assertEqual(m["purpose_3"], "首尾帧 → 视频")
        self.assertEqual(m["h3_mode_4"], "Ref2VA")
        self.assertEqual(m["purpose_4"], "参考图/视频 → 视频")
        self.assertEqual(len(m["case_items"]), 5)
        self.assertEqual(len(m["red_line_items"]), 8)
        self.assertEqual(len(m["red_line_pairing"]), 8)
        self.assertEqual(m["trace_source_kind"], "h3mini")
        self.assertTrue(m["trace_kind_gate"]["ok"], m["trace_kind_gate"])
        self.assertEqual(m["pending_row_label_3"], "本地部署的硬件门槛")
        self.assertFalse(m["table_complete"])


if __name__ == "__main__":
    unittest.main()
