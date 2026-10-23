# -*- coding: utf-8 -*-
"""⑥ G2 收尾 8 个模块的结构化拒绝回归（正常路径 + 拒绝路径都走一遍）。

覆盖：镜 3（shadow_check / ghost_guard / inventory）· 门 2（data_policy / organ_check）
      脑 1（brain_vault）· 耳 1（voice_orchestra）· 手 1（omni_tentacle 聚合体）

判据（不靠关键词，靠**真调行为**）：
  · 拒绝路径返回结构化形状：ok=False / unavailable=True / denied=False / rule / missing / why
  · **不抛异常**（原来 iterdir() 之类会直接抛）
  · 正常路径不受影响（ok=True 或原字段齐全）
  · 关键：**"扫不了"不许折算成"没发现"**（INCONCLUSIVE ≠ GREEN）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "gbt_allinone" / "tentacle"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = fail = 0
SHAPE = ("ok", "unavailable", "denied", "rule", "missing", "why")


def chk(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print("  ✓ %-56s %s" % (name, detail))
    else:
        fail += 1
        print("  ✗ %-56s %s" % (name, detail))


def is_refusal(r) -> bool:
    return (isinstance(r, dict) and r.get("ok") is False
            and r.get("unavailable") is True and r.get("denied") is False
            and bool(r.get("rule")) and isinstance(r.get("missing"), list)
            and bool(r.get("why")))


print("镜组 3：扫不了 ⇒ 结构化拒绝，且**不许算绿**")
from gbt_allinone.tools import shadow_check as SC  # noqa: E402
n = SC.shadow_report()
chk("shadow_check 正常路径 GREEN", n.get("ok") is True and n.get("verdict") == "GREEN",
    "red=%s" % n.get("red"))
r = SC.shadow_report(root="C:/绝对不存在的根_zzz")
chk("shadow_check 拒绝：结构化", is_refusal(r) and r.get("rule") == "shadow_scan_root_missing",
    "rule=%s" % r.get("rule"))
chk("shadow_check 拒绝：verdict=INCONCLUSIVE（不是 GREEN）",
    r.get("verdict") == "INCONCLUSIVE", str(r.get("verdict")))
r2 = SC.shadow_report(pkg="C:/绝对不存在的包_zzz")
chk("shadow_check pkg 缺失也结构化", is_refusal(r2) and r2.get("rule") == "shadow_scan_pkg_missing",
    "rule=%s" % r2.get("rule"))

from gbt_allinone import ghost_guard as GG  # noqa: E402
g = GG.scan()
chk("ghost_guard 正常路径带显式 ok=True", g.get("ok") is True and g.get("scanned") is True,
    "clean=%s" % g.get("clean"))
import gbt_allinone.ghost_guard as _gg  # noqa: E402
_orig = _gg._ROOT
try:
    _gg._ROOT = _gg._ROOT / "绝对不存在的目录_zzz"
    gr = GG.scan()
    chk("ghost_guard 扫根不在 ⇒ 拒绝（不报『无发现』）",
        is_refusal(gr) and gr.get("rule") == "ghost_scan_root_missing"
        and gr.get("scanned") is False,
        "rule=%s" % gr.get("rule"))
finally:
    _gg._ROOT = _orig

from gbt_allinone import inventory as INV  # noqa: E402
inv = INV.scan()
chk("inventory 正常路径 ok=True", inv.get("ok") is True,
    "foreign=%d" % len((inv.get("items") or {}).get("foreign") or []))

print("\n门组 2：分析器/探针 给不出结论就说给不出")
from gbt_allinone.security import data_policy as DP  # noqa: E402
d = DP.status("sk-abcdefghijklmnopqrstuvwxyz0123 文本")
chk("data_policy 正常路径 ok=True + 仍做脱敏",
    d.get("ok") is True and d.get("redactions"), "redactions=%s" % d.get("redactions"))
d2 = DP.status(None)
chk("data_policy 非文本 ⇒ 结构化拒绝",
    is_refusal(d2) and d2.get("rule") == "data_policy_bad_input", "rule=%s" % d2.get("rule"))
d3 = DP.status(123)
chk("data_policy 数字输入也拒", is_refusal(d3), str(d3.get("why"))[:48])

from gbt_allinone.tools import organ_check as OC  # noqa: E402
chk("organ_check 有结构化探针失败口 _probe_err",
    callable(getattr(OC, "_probe_err", None)), "")
pe = OC._probe_err("vision", ValueError("模拟取不到"))
chk("_probe_err 形状完整", is_refusal(pe) and pe.get("rule") == "organ_probe_unavailable",
    "missing=%s" % pe.get("missing"))

print("\n脑组 1 + 耳组 1：原来是自由文本/无结构，现在是形状")
from gbt_allinone import brain_vault as BV  # noqa: E402
chk("brain_vault 有 _cannot", callable(getattr(BV, "_cannot", None)), "")
bc = BV._cannot("brain_vault_dir_missing", "脑库目录不存在：x", ["vault"])
chk("brain_vault 拒绝形状完整", is_refusal(bc), "missing=%s" % bc.get("missing"))

from gbt_allinone import voice_orchestra as VO  # noqa: E402
v = VO.run("list", domain="NOPE")
chk("voice_orchestra 未知 domain ⇒ 结构化",
    is_refusal(v) and v.get("rule") == "voice_unknown_domain", "missing=%s" % v.get("missing"))
v2 = VO.run("status")
chk("voice_orchestra 正常路径不受影响（仍标 readonly）",
    v2.get("ok") is True and v2.get("readonly") is True,
    "registry_size=%s" % v2.get("registry_size"))

print("\n手组 1：聚合体的统一派单口")
import importlib  # noqa: E402
T = importlib.import_module("omni_tentacle")
agg = T.OmniTentacle()
r = agg.invoke("这个方法不存在_zzz")
chk("未知 action ⇒ 结构化 + 列出可用名",
    is_refusal(r) and r.get("rule") == "tentacle_unknown_action"
    and len(r.get("available") or []) > 0,
    "可用 %d 个" % len(r.get("available") or []))
chk("空 action ⇒ 结构化", is_refusal(agg.invoke(""))
    and agg.invoke("").get("rule") == "tentacle_action_required", "")
lw = agg.invoke("list_windows")
chk("真方法派单不受影响", lw.get("ok") is True and isinstance(lw.get("windows"), list),
    "窗口 %d 个" % len(lw.get("windows") or []))
acts = agg.available_actions()
chk("available_actions 报得出真方法数", isinstance(acts, list) and len(acts) > 50,
    "%d 个" % len(acts))

print("\n" + "-" * 78)
print("通过 %d · 失败 %d" % (ok, fail))
sys.exit(0 if fail == 0 else 1)
