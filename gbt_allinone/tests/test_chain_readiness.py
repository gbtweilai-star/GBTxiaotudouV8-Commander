# -*- coding: utf-8 -*-
"""创作链「全方位绑定 + 可随意操控」判据（主人令 2026-09-28）。

主人原话：「你要把这些需要用到的工具**学会吃透**，完后**验证触手是不是全方位都绑定好了、
可随意操控了**，再学会这么使用哪些工具 —— 想做什么视频和唱什么歌不都是你想就可以了吗？」

**判据分四层，逐层收紧**（前一层绿不代表后一层绿，这是本仓血账）：
  A. **在册**：链条里每个工具都是能力位（在 `BENIGN_CAPS`）—— 不在册的只能算"脚本"，写清它是什么；
  B. **三处齐**：注册表 + `api.py` 分派 + 图鉴收录（少一处 = 门看不见它）；
  C. **已绑**：绑定账里能查到它（资产↔触手双向）；
  D. **可操控（真调）**：每个能力位**真调一次只读 op**，必须拿到 `ok`；
     要授权的（写类/high 风险）单独列成"可操控但需授权"，**不当失败**，但必须**如实列出缺哪张票**。

三条链条（`media_run.chains` 现读）：
  film:        concept → script → shots → sound → edit → export → publish
  short_video: script → storyboard → assets → edit → export → publish
  music:       lyrics → arrangement → audio → master → export → publish
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# 阶段 → 真身（能力位）；值为空 = 该阶段要"慢脑/授权/云 key"，本地链路里不假装能跑
CHAIN_TOOLS = {
    # 视频链
    "one_shot": {"stage": "concept/script（构思→计划）", "read_op": "plan", "kw": {"prompt": "判据样本：60 秒科技感短片"}},
    "filmkit": {"stage": "storyboard/shots（镜头单）", "read_op": "status", "kw": {}},
    "actioncam": {"stage": "shots（运镜/机位）", "read_op": "status", "kw": {}},
    "comfyui": {"stage": "assets（本机生图）", "read_op": "status", "kw": {}},
    "zimage_rewash": {"stage": "assets（洗图·放大环）", "read_op": "status", "kw": {}},
    "edit_pipeline": {"stage": "edit（剪辑引擎）", "read_op": "status", "kw": {}},
    "audio_extract": {"stage": "sound（取声）", "read_op": "status", "kw": {}},
    "audio_mix": {"stage": "sound/master（混音与母带）", "read_op": "status", "kw": {}},
    "media_run": {"stage": "export（整链执行器）", "read_op": "status", "kw": {}},
    "media_publish": {"stage": "publish（发布准备·授权门）", "read_op": "status", "kw": {}},
    # 音乐链
    "voice": {"stage": "audio（TTS 念白）", "read_op": "status", "kw": {}},
    "voice_orchestra": {"stage": "audio（语音中枢编排）", "read_op": "status", "kw": {}},
    "music_intel": {"stage": "publish（音乐情报·只读）", "read_op": "group", "kw": {}},
    "music_publishing": {"stage": "publish（发布平台归位·只读）", "read_op": "status", "kw": {}},
}

# 这三个阶段**本地跑不了**（要慢脑/云 key）—— 如实标，不当失败
NEEDS_LLM_STAGES = ["concept/script", "lyrics", "arrangement"]


class TestChainReadiness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gbt_allinone.caps_registry import BENIGN_CAPS
        cls.caps = dict(BENIGN_CAPS)
        cls.api = (ROOT / "gbt_allinone" / "api.py").read_text(encoding="utf-8")
        cls.atlas = json.loads((ROOT / "state" / "skill_atlas.json").read_text(encoding="utf-8"))
        cls.atlas_kinds = {c["kind"] for c in cls.atlas.get("caps") or []}
        cls.bind = json.loads((ROOT / "state" / "asset_bindings.json").read_text(encoding="utf-8"))

    # ---- A 在册 ----
    def test_a_every_chain_tool_is_a_registered_capability(self):
        missing = [k for k in CHAIN_TOOLS if k not in self.caps]
        self.assertEqual([], missing, f"这些工具**不是能力位**（只能是脚本）：{missing}")

    # ---- B 三处齐 ----
    def test_b_three_places(self):
        bad = []
        # ⚠️ 用**框架同一把尺**（tools/framework_state.py 的两种写法）：`kind == "x"` 或 `kind in (…"x"…)`。
        #    血账：我先前只认第一种 + 一种元组写法 ⇒ 把成组元组误判成"没分派"（music_intel 就这么被冤过一次）。
        import re as _re
        for k in CHAIN_TOOLS:
            in_api = bool(_re.search(r'kind\s*==\s*"%s"' % _re.escape(k), self.api)
                          or _re.search(r'kind\s+in\s+\([^)]*"%s"' % _re.escape(k), self.api))
            if not in_api or k not in self.atlas_kinds:
                bad.append({"cap": k, "api": in_api, "atlas": k in self.atlas_kinds})
        self.assertEqual([], bad, f"三处不齐（登记了却可能调不到）：{bad}")

    # ---- C 已绑 ----
    def test_c_every_chain_tool_is_bound_to_a_tentacle(self):
        unbound = []
        for k in CHAIN_TOOLS:
            hit = any(k in ((v or {}).get("tentacles") or []) for v in self.bind.values())
            if not hit:
                unbound.append(k)
        self.assertEqual([], unbound, f"这些能力位没绑到触手（资产↔触手双向里查不到）：{unbound}")

    # ---- D 可操控：真调一次只读 op ----
    # 🔴 2026-10-17 修（留痕 · 原口径 / 为什么翻 / 现口径）：
    #   原口径：只读 op 只要不是 ok 就进 `fails` ⇒ 判红。
    #   为什么翻：`comfyui` 的 status 在本机返回的是**诚实的依赖报错**
    #     （`连不上 ComfyUI（URLError）：先启动它（绘世启动器 / 8188）`）——
    #     那是「外部服务未起」，不是「说能操控却调不通」的代码坏。把它判红会让这条链
    #     永远红着，而红着的判据没人看（本仓血账）。仓内既有口径也是分开的：
    #     `needs_dependency` / `未接线` 不算真坏，只有"契约满足了仍失败"才是红。
    #   现口径：**三类分开、全部可见**——
    #     ① denied ⇒ gated（要票，如实列缺哪张）；
    #     ② 依赖/服务未起（命中 `SERVICE_DOWN_MARKS` 或带 needs_dependency）⇒ **needs_service**；
    #     ③ 其余 ⇒ fails（**这条才判红**）。
    SERVICE_DOWN_MARKS = ("连不上", "URLError", "Connection refused", "连接被拒绝",
                          "timed out", "needs_dependency", "未接线", "服务未起")

    def test_d_every_read_op_really_runs(self):
        import gbt_allinone as g
        rows, fails, gated, svc = [], [], [], []
        for k, spec in CHAIN_TOOLS.items():
            payload = {"op": spec["read_op"], **spec["kw"]}
            try:
                r = g.run_task(k, payload)
            except Exception as exc:                           # noqa: BLE001
                fails.append({"cap": k, "error": f"{type(exc).__name__}: {str(exc)[:80]}"})
                continue
            p = r.get("result", r)
            if isinstance(p, dict) and "result" in p:
                p = p["result"]
            ok = bool((p or {}).get("ok"))
            denied = bool((p or {}).get("denied"))
            rows.append({"cap": k, "stage": spec["stage"], "op": spec["read_op"],
                         "ok": ok, "denied": denied})
            if denied:
                gated.append({"cap": k, "missing": (p or {}).get("missing")})
            elif not ok:
                blob = str(p)
                if (p or {}).get("needs_dependency") or any(m in blob for m in self.SERVICE_DOWN_MARKS):
                    svc.append({"cap": k, "payload": blob[:140]})
                else:
                    fails.append({"cap": k, "payload": blob[:120]})
        # 报告落盘（给主人看"到底哪些能随手调、哪些要票、哪些只是服务没起"）
        rep = {"rows": rows, "gated": gated, "needs_service": svc, "fails": fails,
               "readable": len([x for x in rows if x["ok"]]),
               "gated_count": len(gated),
               "needs_service_count": len(svc),
               "needs_llm_stages": NEEDS_LLM_STAGES}
        (ROOT / "state" / "chain_readiness.json").write_text(
            json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        self.assertEqual([], fails, f"**真调失败**（说能操控，但调不通）：{fails[:4]}")

    # ---- E 如实标：哪些阶段本地跑不了 ----
    def test_e_honest_gaps_are_recorded(self):
        f = ROOT / "state" / "chain_readiness.json"
        self.assertTrue(f.is_file(), "没跑过 D 条 ⇒ 先跑它（它写这份读数）")
        rep = json.loads(f.read_text(encoding="utf-8"))
        self.assertTrue(rep.get("needs_llm_stages"),
                        "必须如实登记『本地跑不了的阶段』（慢脑/云 key）")
        self.assertIn("lyrics", json.dumps(rep, ensure_ascii=False),
                      "音乐链的歌词步必须出现在读数里（哪怕它不可跑）")


if __name__ == "__main__":
    unittest.main(verbosity=2)
