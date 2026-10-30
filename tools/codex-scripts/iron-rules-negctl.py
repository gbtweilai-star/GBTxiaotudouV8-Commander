# -*- coding: utf-8 -*-
"""rule13 负控（临时件 · 跑完即删）：三种故障必须判红。

铁律8「只测绿等于没测」：判据必须先证明自己会红，才算判据。
每次改完立刻 run_rule13() 收读数，最后**无条件还原**（finally 里写回原文）。
"""
import importlib.util as iu
import pathlib
import shutil
import sys

WS = pathlib.Path(__file__).resolve().parents[2]
OMNI = WS / "gbt_allinone" / "tentacle" / "omni_tentacle.py"
WELCOME = WS / "gbt_allinone" / "welcome.py"
PAGE = WS / "holo_pet_w3" / "welcome" / "index.html"


def load():
    spec = iu.spec_from_file_location("_irc_neg", str(WS / "tools" / "codex-scripts" / "iron-rules-check.py"))
    m = iu.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run_rule13():
    # 每次重载：清掉 bridge 的 _manifest 缓存，否则读到的还是上一轮的校正值
    for k in [k for k in sys.modules if k.startswith("gbt_allinone.tentacle")]:
        sys.modules.pop(k, None)
    m = load()
    return m.rule13()


def main() -> int:
    orig = {OMNI: OMNI.read_text(encoding="utf-8"),
            WELCOME: WELCOME.read_text(encoding="utf-8"),
            PAGE: PAGE.read_text(encoding="utf-8")}
    rows = []
    try:
        ok0 = run_rule13()
        rows.append(("正控·未改动必须绿", ok0["ok"] is True, "标题 %s 域" % ok0.get("标题域数")))

        # 故障①：绕过现算回填（模拟"有人把修复删了"）
        OMNI.write_text(orig[OMNI].replace(
            "TENTACLE_MANIFEST = _sync_manifest_title(_sync_manifest_counts(TENTACLE_MANIFEST))",
            "TENTACLE_MANIFEST = TENTACLE_MANIFEST"), encoding="utf-8")
        r = run_rule13()
        rows.append(("负控①·停掉现算回填必须红", r["ok"] is False,
                     (r.get("gap") or "")[:60]))
        OMNI.write_text(orig[OMNI], encoding="utf-8")

        # 故障②：自我介绍写死域数
        WELCOME.write_text(orig[WELCOME].replace("满身触手听你调度", "十域触手听你调度"), encoding="utf-8")
        r = run_rule13()
        rows.append(("负控②·自我介绍写死数字必须红", r["ok"] is False,
                     (r.get("gap") or "")[:60]))
        WELCOME.write_text(orig[WELCOME], encoding="utf-8")

        # 故障③：启动页漂移（少渲染一句）
        PAGE.write_text(orig[PAGE].replace("满身触手听你调度", "×××"), encoding="utf-8")
        r = run_rule13()
        rows.append(("负控③·启动页漂移必须红", r["ok"] is False,
                     (r.get("gap") or "")[:60]))
        PAGE.write_text(orig[PAGE], encoding="utf-8")
    finally:
        for p, t in orig.items():
            p.write_text(t, encoding="utf-8")

    # 还原后必须回到绿（证明还原干净，不是把判据改绿灯）
    back = run_rule13()
    rows.append(("还原后必须回到绿", back["ok"] is True, "标题 %s 域" % back.get("标题域数")))

    bad = [n for n, c, _ in rows if not c]
    for n, c, d in rows:
        print("  %-34s %s  (%s)" % (n, "✅" if c else "❌", d))
    print("\nrule13 负控：%s（%d 条）" % ("全过" if not bad else "%d 条失败" % len(bad), len(rows)))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
