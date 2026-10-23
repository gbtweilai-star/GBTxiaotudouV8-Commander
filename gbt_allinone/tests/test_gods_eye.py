"""上帝之眼判据（主人令 2026-09-27）。

主人原话：「上帝之眼是能看到**创作页面**这些…**克劳德**给意见和建议、商量架构与方向，**决策权在你这里**；
把 **CodeBuddy 也部署进上帝之眼**，做杂事，**主项目她没有执行权**，只有服从安排和随时候命；
以及**每日的 GBT 探针汇报和每日全量扫描框架**指出**缺点、短板、卡点**；然后你自己跟克劳德
在上帝之眼里面**计划优化和提升整体实力**。」

**判据（都可判定）**：
  A. **眼睛**：创作页面 ≥7 个且**文件真在**；服务读数来自**真连端口**（不是"应该开着"）；
  B. **顾问权限是机器可读的**：两位顾问都在册，且各自带 `may` / `may_not`；
  C. **CodeBuddy 越权必拒**：给它一个点了主项目路径的任务 ⇒ 必须 `refused=True`；
  D. **每日汇报三张清单**：缺点/短板/卡点都在，且**每条带 `src`**（来源）；
  E. **计划面留痕**：提案与决策都能写进 `state/gods_eye_plan.jsonl`（决策权在主体）；
  F. **日报新鲜**（≤26h，把"每日"做成开机判据，见类注释）；
  G. **判据能红**（防假绿）：喂一条 30 小时前的快照必须判过期。
"""
from __future__ import annotations

import importlib.util
import json
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "gbt_allinone" / "tools" / "gods_eye.py"
PLAN = ROOT / "state" / "gods_eye_plan.jsonl"
PANEL = ROOT / "holo_pet" / "assets" / "godview" / "index.html"
DAILY_MAX_HOURS = 26


def _daily_age_hours(snap: Path) -> float:
    """日报龄（小时）。F 与 G 共用这一把尺：同函数、同上限，改一个数字两边一起动。"""
    return (time.time() - snap.stat().st_mtime) / 3600.0


def _load():
    spec = importlib.util.spec_from_file_location("gods_eye_probe", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestGodsEye(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load()

    def test_a_eye_sees_creation_pages(self):
        """A. 眼睛：创作页面 ≥7 且真在（不是登记了看不见）。"""
        s = self.m.see()
        self.assertGreaterEqual(s["pages_total"], 7, "创作页面少于 7 个（眼睛看不全）")
        self.assertEqual(s["pages_ok"], s["pages_total"],
                         f"有页面文件不在：{[p['page'] for p in s['pages'] if not p['exists']]}")
        for svc in s["services"]:
            self.assertIn("listening", svc, "服务读数缺字段（必须是真连端口的结果）")

    def test_b_advisors_machine_readable(self):
        """B. 两位顾问在册，权限为机器可读表（may / may_not）。"""
        a = self.m.advisors()
        self.assertEqual({"claude", "codebuddy"}, set(a["advisors"]),
                         f"顾问位不对：{sorted(a['advisors'])}")
        for k, v in a["advisors"].items():
            self.assertTrue(v.get("may"), f"{k} 缺 may")
            self.assertTrue(v.get("may_not"), f"{k} 缺 may_not")
        self.assertIn("决策", a.get("decider", ""), "必须写明决策权在主体")

    def test_c_codebuddy_has_no_exec_authority(self):
        """C. **CodeBuddy 对主项目没有执行权**：点主项目路径必须被拒。"""
        r = self.m.ask("codebuddy", "把 projects/movie/产线 里的清单都改一遍")
        self.assertTrue(r.get("refused"), f"竟然没拒：{r}")
        self.assertFalse(r.get("ok"), "越权请求不许通过")

    def test_d_daily_three_lists_with_src(self):
        """D. 每日汇报：缺点/短板/卡点三张清单都在，且每条带来源。"""
        d = self.m.daily()
        s = d["全量扫描"]
        for cat in ("缺点", "短板", "卡点"):
            self.assertIn(cat, s, f"缺 {cat} 清单")
            for x in s[cat]:
                self.assertTrue(x.get("src"), f"{cat} 里有条目没写来源：{x}")
        self.assertIn("探针汇报", d, "缺探针汇报")

    def test_e_plan_has_trail(self):
        """E. 计划面留痕：提案与决策都能落进台账。

        ⚠️ 判据**不许往真账本里写**：早先这条把 6 组「判据自检用提案」写进了
        `state/gods_eye_plan.jsonl`（每跑一次多两行），真账本被自检污染 ⇒ 现在换成**临时账本**，
        真实提案与决策只由人和 `plan op=add|decide` 产生。
        """
        import tempfile
        real = self.m._PLAN
        with tempfile.TemporaryDirectory() as td:
            self.m._PLAN = Path(td) / "plan.jsonl"
            try:
                self.m.plan("add", item="判据自检用提案", src="test_gods_eye")
                r = self.m.plan("decide", item="判据自检用提案", decision="采纳")
                self.assertTrue(r.get("ok"), f"决策没记上：{r}")
                rows = self.m.plan("list")
                self.assertGreaterEqual(rows.get("count", 0), 2, "临时账本里没留下提案+决策")
                # ⚠️ 2026-09-28 主人令改了口径：**决策由 Jev 拍板**（原先写"决策权在主体"）。
                #    判据跟着改，别让旧口径留在判据里变成"看着在判、其实判的是老规矩"。
                dec = rows.get("decider", "")
                self.assertIn("Jev", dec, "决策人应当是 Jev（主人令 2026-09-28）")
                self.assertIn("拍板", dec, "决策人的措辞里要写明是拍板")
            finally:
                self.m._PLAN = real
        self.assertTrue(PLAN.is_file(), "计划台账不存在")
        self.assertTrue(PANEL.is_file(), "上帝之眼页面不存在 ⇒ 跑 panel")


class TestJevDecides(unittest.TestCase):
    """**Jev 拍板 + 四岗分工**（主人令 2026-09-28）。

    主人原话：「把 Jev 的推理模型接入上帝之眼来做决策，设计好要以 Jev 来做决策，
    克劳德给意见和建议以及可以商量，这么来好了之后由 Jev 做决策，Codex 专注编程，
    DeepSeek Harness 专注执行层。」

    判据 A~G：分工机器可读 · 没证据不拍板 · 证据不在盘上不拍板 · 读数够就拍 ·
    **选不出不许硬猜**（升慢脑或挂起，不许给"猜的"选择）· 风险词扣分 · 预算闸在。
    """

    @classmethod
    def setUpClass(cls):
        cls.m = _load()

    def test_a_four_roles_are_machine_readable(self):
        r = self.m.roles()
        need = {"jev": "决策", "claude": "意见", "codex": "编程", "deepseek": "执行层"}
        for name, kw in need.items():
            self.assertIn(name, r["roles"], f"缺岗：{name}")
            v = r["roles"][name]
            self.assertTrue(v.get("may"), f"{name} 没有 may 清单")
            self.assertTrue(v.get("may_not"), f"{name} 没有 may_not 清单")
            self.assertIn(kw, json.dumps(v, ensure_ascii=False), f"{name} 的职责里没写清「{kw}」")
        jev = json.dumps({k: r["roles"]["jev"][k] for k in ("role", "may")}, ensure_ascii=False)
        self.assertTrue(any(w in jev for w in ("决策", "拍板", "裁决")),
                        f"Jev 的职责里没有『决策/拍板/裁决』这类词：{jev}")
        for other in ("claude", "codex", "deepseek"):
            self.assertIn("决策", json.dumps(r["roles"][other]["may_not"], ensure_ascii=False),
                          f"{other} 的 may_not 必须写明不许决策（拍板是 Jev 的活）")

    def test_h_availability_is_fail_closed(self):
        """**可用性不许 fail-open**：探针读不到读数 ⇒ 必须报"不可用"，不许默认成能用。

        血账：第一版写成 `bool(d.get("available", d.get("found", True)))`（默认真），
        而 `codex_chat`/`llm_chat` 的 status 会被门拒、返回里没有那两个键 ⇒
        "探针没给读数"被当成了"可用"。这正是本仓反复吃的"读不到当成没问题"。
        """
        old = self.m._gate
        self.m._gate = lambda *a, **k: {"ok": True, "gate_ok": True, "payload": {}}
        try:
            r = self.m.roles()
            for name in ("claude", "codex", "deepseek"):
                self.assertFalse(r["roles"][name]["available"],
                                 f"{name} 在探针无读数时被默认成可用了 ⇒ fail-open 又回来了")
        finally:
            self.m._gate = old

    def test_b_no_evidence_no_verdict(self):
        r = self.m.decide(question="先干哪个？", options="A方案,B方案")
        self.assertFalse(r.get("ok"), "没有证据竟然拍了板")
        self.assertTrue(r.get("refused"), "拒的形状不对")
        self.assertIn("Jev", str(r.get("decider")))

    def test_c_evidence_off_disk_is_refused(self):
        r = self.m.decide(question="先干哪个？", options="A,B", evidence="no/such/reading.json")
        self.assertFalse(r.get("ok"), "盘上没有的证据也敢当依据")
        self.assertIn("证据不在盘上", str(r.get("why")))

    def test_d_reading_backed_choice_is_decided_by_jev(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            ev = Path(td) / "现写读数.json"
            ev.write_text("{}", encoding="utf-8")
            r = self.m.decide(question="先干哪个？", options="修未清故障,做个新面板",
                              evidence=str(ev))
            self.assertTrue(r.get("ok"), f"有证据却没拍出来：{r}")
            self.assertEqual("Jev（推理模型）", r.get("decider"))
            self.assertEqual("修未清故障", r.get("choice"), "压在最短板上那条该赢")
            self.assertEqual("fast", r.get("path"))

    def test_e_undecidable_must_not_guess(self):
        """**选不出不许硬猜**：要么升慢脑（path=slow），要么挂起（blocked）—— 不许给"猜的"选择。

        这条是 Jev 协议的核心（`tool/control_loop.py` 同款规矩：宁可 BLOCKED，也不乱选）。
        """
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            ev = Path(td) / "读数.json"
            ev.write_text("{}", encoding="utf-8")
            r = self.m.decide(question="选哪种蓝？", options="深蓝,浅蓝", evidence=str(ev))
            if r.get("ok"):
                self.assertEqual("slow", r.get("path"), "低置信过了却没走慢脑 ⇒ 可能是硬猜")
            else:
                self.assertTrue(r.get("blocked"), f"既没慢脑也没挂起，那是什么：{r}")
                self.assertTrue(r.get("how_to_unblock"), "挂起要说清怎么解锁")

    def test_f_risk_words_lose(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            ev = Path(td) / "读数.json"
            ev.write_text("{}", encoding="utf-8")
            r = self.m.decide(question="先做哪个？", options="修未清故障,直接上线改生产",
                              evidence=str(ev))
            self.assertTrue(r.get("ok"))
            self.assertEqual("修未清故障", r.get("choice"), "带风险词的候选不该赢")
            risks = [s for s in r["scores"] if s["option"] == "直接上线改生产"][0]["风险词"]
            self.assertTrue(risks, "风险词没认出来")

    def test_g_budget_gate_exists(self):
        b = self.m._decide_budget()
        self.assertEqual(self.m.DECIDE_MAX_PER_MIN, b["limit"])
        self.assertIn("last_min", b)


class TestDailyIsFresh(unittest.TestCase):
    """F. **日报必须新鲜**（主人令：「**每日**的 GBT 探针汇报和每日全量扫描」）。

    为什么做成判据：宿主的自动化功能**不接受从计划任务会话里再建任务**（实测原文：
    `Cannot create a scheduled task inside a session that already belongs to a scheduled task`），
    所以"每日"这条**不靠宿主**、靠**开机判据**兜：每次开工都自检日报新鲜度 ——
    过期就红，并直说"该跑日报了"。这样"每日"是**被验证的节律**，不是一句承诺。
    """

    def test_f_daily_snapshot_is_fresh(self):
        snap = ROOT / "state" / "gods_eye.json"
        self.assertTrue(snap.is_file(),
                        "没有日报快照 ⇒ 跑 run_task('gods_eye', {'op': 'daily'})")
        age_h = _daily_age_hours(snap)
        self.assertLess(age_h, DAILY_MAX_HOURS,
                        "日报已过期 %.1f 小时（上限 %dh）⇒ 跑 run_task('gods_eye', "
                        "{'op': 'daily'}) 并刷新 panel" % (age_h, DAILY_MAX_HOURS))

    def test_g_stale_snapshot_would_turn_red(self):
        """G. **判据本身要能红**（防假绿）：同一把尺、同一个上限，喂一条 30 小时前的快照必须判过期。

        没有这条，F 条只证明"现在绿"，不证明"过期会红" —— 尺子是不是真能量，得拿一个
        确定过期的样本量一次。
        """
        import os
        import shutil
        import tempfile
        import time
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "gods_eye.json"
            shutil.copyfile(ROOT / "state" / "gods_eye.json", fake)
            old = time.time() - 30 * 3600          # 30 小时前
            os.utime(fake, (old, old))
            age_h = _daily_age_hours(fake)
            self.assertGreaterEqual(age_h, DAILY_MAX_HOURS,
                                    "30h 前的快照竟判为新鲜 ⇒ 上限形同虚设")


class TestAskWiring(unittest.TestCase):
    """H. **问顾问的载荷要真的能被底下认出来**（防"接上了用不了"）。

    实测血账：`cli_agents.run` 认 `prompt` / `q`，而 `gods_eye.ask` 早先只传 `text=` ——
    授权给了也只会回「缺少 prompt」。这条判据盯的就是那个键：`_ask_payload` 里没有
    `prompt`（或与 `text` 不等），直接红。
    """

    @classmethod
    def setUpClass(cls):
        cls.m = _load()

    def test_h_payload_carries_prompt_key(self):
        p = self.m._ask_payload("来点意见", 90)
        self.assertEqual(p.get("prompt"), "来点意见", "底下认的是 prompt/q ⇒ 必须带 prompt")
        self.assertEqual(p.get("text"), "来点意见", "text 留着给权限校验看原话")
        self.assertEqual(p.get("timeout"), 90, "timeout 要透传（不给就默认）")
        self.assertEqual(p.get("op"), "ask")

    def test_i_claude_slot_is_wired_not_faked(self):
        """I. claude 槽要么真给意见，要么如实说"缺授权/缺 CLI" —— **不许假装答了**。

        可用性是从 PATH 真探出来的；被门拒时不许把拒绝理由塞进 `answer` 冒充顾问意见。
        """
        r = self.m.ask(advisor="claude", text="一句话：下一步最该修什么？")
        if r.get("denied"):
            self.assertNotIn("answer", r, "被拒 ≠ 顾问答了：不许有 answer")
            self.assertTrue(r.get("how_to") or r.get("why"), "被拒要说清怎么才能通")
        else:
            self.assertTrue(r.get("available") is False or r.get("answer"),
                            f"既没答也没说缺什么：{r}")


class TestAuthReadingsAreLive(unittest.TestCase):
    """J. **授权面读数必须真读得到**（防"接上了没生效"）。

    实测血账：`_scan_findings` 原来按**文件路径**装 `auth_gate.py`，而它的第一行是
    `from . import _paths`（相对导入）⇒ ImportError，又被 `except: pass` 吞掉
    ⇒ 「要授权才能干活」这条卡点**从来没在日报里出现过**。
    这条判据盯住读数本身：读不到就直接红，不许静默降级。
    """

    @classmethod
    def setUpClass(cls):
        cls.m = _load()

    def test_j_auth_status_reads(self):
        st = self.m._auth_status()
        self.assertTrue(st, "授权面读数读不到 ⇒ 日报会漏掉『要授权』这条卡点（别用 except: pass 糊它）")
        sc = st.get("scopes") or {}
        self.assertIn("process_execute", sc, "读数里没有 process_execute ⇒ 拿到的不是授权门状态")

    def test_k_blocker_is_derived_from_the_reading(self):
        """K. 卡点由**读数**推出来，不是写死的一句话（授权窗口一变，结论要跟着变）。"""
        st = self.m._auth_status()
        sc = st.get("scopes") or {}
        have = [(sc.get(s) or {}).get("grants_available") for s in ("process_execute", "external_llm")]
        f = self.m._scan_findings()
        text = json.dumps(f, ensure_ascii=False)
        if all((n or 0) > 0 for n in have):
            self.assertIn("授权在窗口内", text, "有票时该报『窗口内』")
        else:
            self.assertIn("要授权才能问", text, "没票时该报『要授权』")


if __name__ == "__main__":
    unittest.main(verbosity=2)
