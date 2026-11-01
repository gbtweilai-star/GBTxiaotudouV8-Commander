"""test_scope_import.py · 平台 scope 导入（离线）

判据：
  1. HackerOne 示例：URL/WILDCARD/IP 归一化正确；bounty=false 的资产进 out；out_of_scope 保留；
  2. Bugcrowd 示例：in_scope/out_of_scope 都解析；network 变 CIDR；
  3. **默认 dry-run 不落库**；confirm=True 才建项目，且 authorization_ref 写清"需人工核对授权"；
  4. 建出来的项目过范围闸：in-scope 允许、out-of-scope 拒绝、CIDR 允许、外部域拒绝；
  5. 空 scope 拒绝导入（不造空项目）。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gbt_allinone import bounty as B  # noqa: E402
from gbt_allinone import scope_import as SI  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    ok = bool(cond)
    print(("  ok   " if ok else "  FAIL ") + name + ((" · " + str(extra)) if extra else ""))
    if not ok:
        FAILS.append(name)


def clear(name: str) -> None:
    progs = B._read_json(B.PROGRAMS, [])
    progs = [p for p in progs if p.get("name") != name]
    B.PROGRAMS.write_text(__import__("json").dumps(progs, ensure_ascii=False, indent=1),
                          encoding="utf-8")


def main() -> int:
    print("[1] HackerOne 示例归一化")
    loaded = SI.load_sample("data/scope-samples/hackerone-sample.json")
    check("样本能读", loaded.get("ok") is True, loaded.get("reason"))
    n = SI.normalize(loaded["doc"])
    scope = n.get("scope") or []
    out = n.get("out_of_scope") or []
    check("URL 去协议/去路径", "www.example.com" in scope, scope)
    check("通配符去 *", "api.example.com" in scope, scope)
    check("IP 保留", "203.0.113.10" in scope, scope)
    check("bounty=false → out", "intranet.example.com" in out, out)
    check("显式 out 保留", "mail.example.com" in out, out)

    print("[2] Bugcrowd 示例归一化")
    l2 = SI.load_sample("data/scope-samples/bugcrowd-sample.json")
    n2 = SI.normalize(l2["doc"])
    s2, o2 = n2.get("scope") or [], n2.get("out_of_scope") or []
    check("website 归一化", "shop.example.net" in s2, s2)
    check("api 归一化", "api.example.net" in s2, s2)
    check("network → CIDR", "198.51.100.0/24" in s2, s2)
    check("out: website", "pay.example.net" in o2, o2)
    check("out: 字符串也认", "status.example.net" in o2, o2)
    check("平台识别", n2.get("platform") == "bugcrowd", n2.get("platform"))

    print("[3] 默认 dry-run 不落库；confirm 才建项")
    clear("Acme VDP（示例·虚构）")
    preview = SI.import_doc(loaded["doc"], confirm=False)
    check("dry-run ok", preview.get("ok") is True)
    check("dry-run 不落库", not any(p.get("name") == "Acme VDP（示例·虚构）"
                                   for p in B.list_programs()["programs"]))
    committed = SI.import_doc(loaded["doc"], confirm=True)
    pid = (committed.get("program") or {}).get("id")
    check("confirm 建项", committed.get("created") is True and bool(pid), pid)
    check("授权依据写明来源+需核对",
          "hackerone" in (committed.get("authorization_ref") or "")
          and "需人工核对授权" in (committed.get("authorization_ref") or ""),
          committed.get("authorization_ref"))

    print("[4] 导入项目过范围闸")
    check("in-scope 域名允许", B.check(pid, "www.example.com").get("ok") is True)
    check("通配域允许", B.check(pid, "v1.api.example.com").get("ok") is True)
    check("IP 允许", B.check(pid, "203.0.113.10").get("ok") is True)
    check("out-of-scope 拒绝", B.check(pid, "mail.example.com").get("blocked") is True)
    check("bounty=false 拒绝", B.check(pid, "intranet.example.com").get("blocked") is True)
    check("外部域拒绝", B.check(pid, "evil.example.org").get("blocked") is True)

    print("[5] 空 scope 拒绝")
    empty = SI.import_doc({"name": "空项目", "scope": []}, confirm=True)
    check("空 scope 被拒", empty.get("ok") is False, empty.get("reason"))

    print()
    if FAILS:
        print("FAILED %d: %s" % (len(FAILS), FAILS))
        return 1
    print("ALL OK —— 平台 scope 导入：归一化/dry-run/确认落库/范围闸 全链路")
    return 0


if __name__ == "__main__":
    sys.exit(main())
