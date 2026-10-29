# -*- coding: utf-8 -*-
"""不开口闸（no-ask-check）—— 框架里**不许有要求用户帮忙的路径**。

主人令（2026-10-09，逐字）：
  「在框架里面出来必须要用户求助帮忙的其他全部给我禁止掉……但你开口要求用户的时候你就输了」
  「可以跟用户商量项目架构和排布，严禁要求用户帮助，AI时代大众用户需要的是一个什么都能自己搞定的伙伴，
    而不是被指挥者」

口径（与主人这句对齐）：
  · **允许**：跟用户**商量项目架构与排布**（那是方向，不是让他干活）；
  · **允许**：用户**身份/账户登录**（只有本人才有的那个身份），且要我方主动跑流程；
  · **禁止**：任何"要用户动手做事"的文案（请你去/麻烦你/你自己配/请提供/你手动…）；
  · **申报才放行**：写给**模型**的提示词、描述设计目标的文档行等**误报**，必须在 DECLARED 里
    **逐条写明理由**才放行 —— 不许静默跳过（本仓最恨静默）。

用法：
  py -3.14 -X utf8 tools/codex-scripts/no-ask-check.py          # 扫并判
  py -3.14 -X utf8 tools/codex-scripts/no-ask-check.py --selftest
退出码：0 无违规 · 1 有违规 · 2 读不动
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# 申报放行（误报）：key = "相对路径:行号"，value = 为什么它不是在要求用户
DECLARED: dict = {
    "gbt_allinone/tools/agent_rig.py:16":
        "文档表格：描述这个能力的设计目标（用主人自己的订阅跑编码 agent），不是让用户做事",
    "gbt_allinone/tools/agent_rig.py:28":
        "**反向句**：正文明写「不是替你去注册」——它在声明我们不做甩锅，不是在甩锅",
    "gbt_allinone/tools/gs_h3_cap.py:260":
        "发给**模型**的提示词（『请你基于下方素材构思』里的『你』指模型，不指用户）",
}


def scan() -> dict:
    from gbt_allinone import ux_doctrine as UX
    files = [p for p in (ROOT / "gbt_allinone").rglob("*.py")
             if "_legacy" not in str(p) and "vendor" not in str(p) and "test" not in p.name
             and p.name != "ux_doctrine.py"]
    hits, declared_hit = [], []
    for p in files:
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            s = line.strip()
            if not s or s.startswith("#") or ('"' not in s and "'" not in s):
                continue
            r = UX.check_ask(s, acted=False)
            if r.get("通过"):
                continue
            key = "%s:%d" % (p.relative_to(ROOT).as_posix(), i)
            row = {"件": key, "命中": r["命中句式"][:1], "原文": s[:110]}
            (declared_hit if key in DECLARED else hits).append(row)
    return {"ok": not hits, "扫描件数": len(files), "违规": hits,
            "已申报放行": declared_hit, "申报表条数": len(DECLARED)}


def selftest() -> int:
    from gbt_allinone import ux_doctrine as UX
    bad = ["请你去 Tripo 点一下导出", "麻烦你把 GLB 拖进下载夹", "你自己先配置一下密钥",
           "请提供你的 API key", "你需要手动上传一下"]
    good = ["请先登录你的账号并授权设备码", "扫码登录后我自动接管",
            "我已导出并收进仓：成片 21.77 秒，读数见台账",
            "我建议架构分四层，你看这个排布行不行"]
    n_bad = sum(1 for t in bad if not UX.check_ask(t, acted=False)["通过"])
    n_good = sum(1 for t in good if UX.check_ask(t, acted=True)["通过"])
    print("负对照·五句「要用户做事」必须全拦 => 拦下 %d/%d" % (n_bad, len(bad)))
    print("正例·身份登录/已有读数/商量架构 必须放行 => 放行 %d/%d" % (n_good, len(good)))
    dismissed = [t for t in ("这个不影响运行", "忽略即可", "下次再说", "小问题")
                 if not UX.check_dismissal(t)["通过"]]
    print("负对照·敷衍句必须全拦 => 拦下 %d/4" % len(dismissed))
    tr = UX.triage([{"现象": "x", "根因": "y", "处置": "z", "证据": "w"},
                    {"现象": "a", "处置": "b"},
                    {"现象": "c", "根因": "d", "处置": "e", "证据": "不影响"}])
    print("负对照·报警闭环闸 => 已闭环 %d · 未闭环 %d · 敷衍 %d"
          % (tr["已闭环"], tr["未闭环"], tr["敷衍句"]))
    # 停点闸：只有两种理由合法
 # 2026-10-10 修**陈了的期望值**：这条自检长期以来是红的（"停点判错: 全部跑通并交付 期望 True
    #    实得 False"），而**代码是对的、期望是旧的** ——
    #    主人令 2026-10-09 把停点收紧了：光"这次活干完了 + 带证据"**不够**，
    #    还要 **completeness() 整体完善**（"看整体没完善就不停工"）。
    #    ⇒ 期望值必须**跟着现算**，不能写死 True。写死就变成"自检红着没人管"，
    #      而长期红着的自检 == 等于没有自检（真坏那天也不会有人多看一眼）。
    _comp = UX.completeness()["完善"]
    stops = [("全部跑通并交付", "", "判据全绿", "", _comp),
             ("我不确定，等你回复", "", "", "", False),
             ("需要你同意一下", "", "", "", False),
             ("要发布上线", "", "", "对外发布", True),
             ("部署完成", "", "", "", False)]
    n_stop = 0
    for reason, kind, ev, dc, want in stops:
        got = UX.check_stop(reason, kind=kind, evidence=ev, danger_class=dc).get("允许停")
        if got is want:
            n_stop += 1
        else:
            print("       ❌ 停点判错:", reason, "期望", want, "实得", got)
    print("负对照·停点闸（只许两种理由）=> 判对 %d/%d" % (n_stop, len(stops)))

 # 2026-10-10 补 **扫描器级**负对照（先前只测了句子分类器）。
    #    上面那些负对照喂的都是**字符串**，而本件的**被测单元是 scan()——它扫盘**。
    #    selftest-audit 把这件分成「纯合成(扫盘件·真缺口)」：==分类器再对，也照不到扫描器的洞==。
    #    ⇒ 真植入一个含违规句的 .py 到扫描范围里，**扫盘必须抓到**；
    #      再把它写进 DECLARED ⇒ **必须转到「已申报放行」、不许留在违规里**
    #      （这一半同样重要：申报放行是本件唯一的放行口，它坏了就等于门形同虚设）。
    NL = chr(10)
 # 起名要避开 scan() 自己的过滤器（第 44 行有 '"test" not in p.name'）——
    #    我第一版叫 _selftest_noask_probe.py ⇒ 含 "test" ⇒ **被自己排除**，负控当场假绿。
    probe = ROOT / "gbt_allinone" / "_noask_probe_tmp.py"
    probe.write_text(NL.join(["# 自检植入件（跑完即删）",
                              'MSG = "请你去 Tripo 点一下导出"', ""]), encoding="utf-8")
    key = "gbt_allinone/_noask_probe_tmp.py:2"
    caught = declared_ok = leaked = False
    try:
        r1 = scan()
        caught = any(x["件"] == key for x in r1["违规"])
        DECLARED[key] = "自检植入件：测申报放行这条路本身还通不通"
        try:
            r2 = scan()
            declared_ok = any(x["件"] == key for x in r2["已申报放行"])
            leaked = any(x["件"] == key for x in r2["违规"])
        finally:
            DECLARED.pop(key, None)
    finally:
        probe.unlink(missing_ok=True)
    print("负对照·扫描器级（真植入）=> 扫盘抓到 %s · 申报后转放行 %s · 申报后仍漏在违规 %s"
          % (caught, declared_ok, leaked))
    return 0 if (n_bad == 5 and n_good == 4 and len(dismissed) == 4
                 and tr["已闭环"] == 1 and tr["未闭环"] == 1 and tr["敷衍句"] == 1
                 and n_stop == len(stops)
                 and caught and declared_ok and not leaked) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="不开口闸")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        rc = selftest()
        print("自检：%s" % ("全过" if rc == 0 else "不过"))
        return rc
    r = scan()
    print("扫描 %d 件 · 违规 %d 条 · 已申报放行 %d 条" % (r["扫描件数"], len(r["违规"]), len(r["已申报放行"])))
    for x in r["违规"]:
        print("  ❌ %-46s %s" % (x["件"], x["原文"]))
    for x in r["已申报放行"]:
        print("  ○  %-46s（已申报）" % x["件"])
    print("\n判据：%s" % ("PASS" if r["ok"] else "FAIL"))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
