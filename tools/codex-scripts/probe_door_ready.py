# -*- coding: utf-8 -*-
"""门就位探测：主人应用 policy.py 补丁后跑这个。
只读 —— 只问 policy.evaluate，不调任何能力、不写任何东西。
"""
import sys
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
sys.path.insert(0, str(BASE))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from gbt_allinone.security import policy  # noqa: E402

ok = fail = 0


def chk(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print("  ✓ %-52s %s" % (name, detail))
    else:
        fail += 1
        print("  ✗ %-52s %s" % (name, detail))


def sc(kind, payload):
    return set(policy.evaluate(kind, payload).scopes)


print("=" * 88)
print("资料桥的门就位探测（只读；主人应用补丁后跑）")
print("=" * 88)

# ⚠️ 先验门是否存在：policy 对**未知 kind 一律返回 scopes=()**，
# 所以「只读动作免卡」在没有门的时候也会假过。必须先确认门在，否则下面的 ✓ 全是假的。
_door = (sc("feishu_docs", {"op": "create_doc"})
         or sc("feishu_docs", {"op": "store_credentials"})
         or sc("notion_docs", {"op": "store_token"}))
if not _door:
    print("\n✗ 门不存在 —— notion_docs / feishu_docs 都还是未知 kind，")
    print("  于是 policy 对它们的**任何**动作都返回 scopes=()（含存凭据、建页面、加成员）。")
    print("  这种情况下「只读免卡」是假过，不构成通过。")
    print("\n  ⇒ 请先应用 .scratch/policy_patch_feishu_notion.md，再跑本脚本。")
    print("  ⇒ **门未就位之前不要接分发**（接了就是免门洞）。")
    sys.exit(1)

print()
print("\n● Notion 资料舱（notion_docs）")
for op in ("status", "search", "recent", "page"):
    s = sc("notion_docs", {"op": op})
    chk("只读 %s 免卡" % op, not s, "scopes=%s" % (sorted(s) or "()"))
chk("store_token 卡 filesystem_write",
    "filesystem_write" in sc("notion_docs", {"op": "store_token", "token": "x"}), "")
chk("未登记动作从严卡 data_export",
    "data_export" in sc("notion_docs", {"op": "some_future_write"}), "")

print("\n● 飞书资料库桥（feishu_docs）")
for op in ("status", "wiki_spaces", "wiki_nodes", "get_node", "my_space_id",
           "search_docs", "read_doc"):
    s = sc("feishu_docs", {"op": op})
    chk("只读 %s 免卡" % op, not s, "scopes=%s" % (sorted(s) or "()"))
for op in ("store_credentials", "load_credentials"):
    s = sc("feishu_docs", {"op": op})
    chk("%s 卡 filesystem_write" % op, "filesystem_write" in s, "scopes=%s" % sorted(s))
for op in ("tenant_token", "create_space", "create_node", "create_doc", "append_text"):
    s = sc("feishu_docs", {"op": op})
    chk("%s 卡 data_export" % op, "data_export" in s, "scopes=%s" % sorted(s))
s = sc("feishu_docs", {"op": "add_member"})
chk("add_member 卡 data_export + remote_device",
    {"data_export", "remote_device"} <= s, "scopes=%s" % sorted(s))
chk("未登记动作从严卡 data_export",
    "data_export" in sc("feishu_docs", {"op": "some_future_write"}), "")
chk("别名 feishu / notion 同判",
    sc("feishu", {"op": "create_doc"}) == sc("feishu_docs", {"op": "create_doc"})
    and sc("notion", {"op": "store_token"}) == sc("notion_docs", {"op": "store_token"}), "")

print("\n● 风险等级（高危动作必须被标 high）")
for kind, op in (("feishu_docs", "create_doc"), ("feishu_docs", "add_member"),
                 ("notion_docs", "store_token")):
    d = policy.evaluate(kind, {"op": op})
    chk("%s.%s risk=high" % (kind, op), d.risk == "high", "risk=%s scopes=%s" % (d.risk, d.scopes))

print("\n" + "-" * 88)
if fail == 0:
    print("✓ 门就位（%d 项全过）—— 可以接分发了：告诉 AI「门已上」即可。" % ok)
else:
    print("✗ 还有 %d 项没过（通过 %d）—— 门尚未就位，此时**不要**接分发（接了就是免门洞）。" % (fail, ok))
sys.exit(0 if fail == 0 else 1)
