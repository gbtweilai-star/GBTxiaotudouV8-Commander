"""首次实战：拿 old-links 的三文件练 record_grid（画像 → 解析 → 自证）。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from gbt_allinone import record_grid as RG  # noqa: E402

DATA = Path(".scratch/oldlinks/links.txt")


def show(title, obj, limit=1400):
    text = json.dumps(obj, ensure_ascii=False, indent=1, default=str)
    print(f"\n===== {title} =====")
    print(text[:limit])


def main():
    raw = DATA.read_bytes()
    text, enc, replaced = RG.decode_bytes(raw)
    print("encoding:", enc, "| replaced:", replaced, "| bytes:", len(raw))

    prof = RG.profile_text(text)
    show("profile（结构画像）", {k: v for k, v in prof.items() if k != "columns"})
    show("profile.columns", prof["columns"], 2200)

    plan = RG._preset("link_index")
    parsed = RG.parse_text(text, plan, encoding=enc)
    print("\n===== parse =====")
    print("records:", len(parsed["records"]), "| invalid:", len(parsed["invalid"]),
          "| findings:", len(parsed["findings"]))
    print("stats:", parsed["stats"])
    show("前 3 条记录", parsed["records"][:3])
    show("坏行样本", parsed["invalid"][:3])
    show("词表越界样本", parsed["findings"][:3])

    ver = RG.verify_roundtrip(text, plan)
    show("verify（回写自证）", ver)

    drafted = RG.draft_plan(prof, "old_links_draft")
    show("draft_plan（画像→骨架）", drafted)

    # 骨架自证：用画像起草的 plan 也要能解析 + 幂等（否则骨架只是好看）
    print("\n===== 骨架实测（draft plan 全量解析） =====")
    draft_plan = RG.Plan.from_dict({k: v for k, v in drafted.items()
                                    if k in ("name", "sep", "quoted", "fields", "url_schemes")})
    d = RG.parse_text(text, draft_plan, encoding=enc)
    print("records:", len(d["records"]), "| invalid:", len(d["invalid"]),
          "| findings:", len(d["findings"]))
    show("坏行样本", d["invalid"][:3])
    show("首条记录", d["records"][:1])
    print("roundtrip:", RG.verify_roundtrip(text, draft_plan)["ok"])

    # 边界推演：故意喂坏行，验证不中断 + 诊断可执行
    print("\n===== 边界：三类坏行 =====")
    bad_text = (
        "Good One* http://a.example/x intro.list fine comment\n"
        "NoUrl At All intro.list missing url here\n"
        "Bad Packed http://b.example/y .list no tags\n"
        "\n"
        "Title With http://inside.example/word url http://c.example/z intro.com title contains scheme\n"
    )
    b = RG.parse_text(bad_text, plan, encoding="utf-8")
    print("records:", len(b["records"]), "| invalid:", len(b["invalid"]), "| blank skipped:", b["stats"]["blank"])
    show("坏行诊断", b["invalid"], 1600)
    show("仍被救回的行", b["records"], 900)


if __name__ == "__main__":
    main()
