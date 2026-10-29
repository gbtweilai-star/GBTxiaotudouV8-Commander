#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""规程补洞写手（D3 甲）—— 把「该域在册的每一位」自动写进 `gbt-<域>/SKILL.md` 的一个标记段。

设计（这就是"设计好的实现"，不是新点子）：
  · `spec-gap-scan.py` 量出 149 位「在注册表、但该域规程正文没点到名字」；
  · 手写 149 条必烂（P9），所以**由生成器写**：在每份 `SKILL.md` 末尾维护**一个标记段**
      `<!-- caps-auto:begin ... -->` … `<!-- caps-auto:end -->`
    段内逐行列该域的位（名字 + 一句说明 + 有没有作用域要求）。
  · **幂等**：段存在就整段替换，不存在就追加；段外内容一个字都不动。
  · **可回滚**：写前把原文件备份到 `state/skill-backup/<域>__SKILL.md.bak`（带时间戳），
    并把前后 sha256 记进回执 `state/spec-gap-patch.json`。

用法：
  py -3.14 tools/codex-scripts/spec-gap-patch.py --dry-run     # 只看会改哪些文件、改几行
  py -3.14 tools/codex-scripts/spec-gap-patch.py --apply       # 真写（先备份）
  py -3.14 tools/codex-scripts/spec-gap-patch.py --apply --only llm,data
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCAN = os.path.join(ROOT, "state", "spec-gap-scan.json")
RECEIPT = os.path.join(ROOT, "state", "spec-gap-patch.json")
BACKUP = os.path.join(ROOT, "state", "skill-backup")
BEGIN = "<!-- caps-auto:begin（由 tools/codex-scripts/spec-gap-patch.py 生成，手改会被覆盖） -->"
END = "<!-- caps-auto:end -->"


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


def block_for(domain, caps):
    lines = [BEGIN, "", "## 本域在册能力位（自动清单）", "",
             "> 本节由 `spec-gap-patch.py` 从能力注册表现读生成，**手改会被下一次生成覆盖**。",
             "> 作用域列写的是「空载荷下的门」；带 `op` 依赖的位在调用时可能换一套（见各域正文说明）。", "",
             "| 能力位 | 说明 | 空载荷作用域 |", "|---|---|---|"]
    for c in caps:
        lines.append("| `%s` | %s | %s |" % (c["cap"], c["desc"], c["scopes"]))
    lines += ["", END, ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    if not os.path.isfile(SCAN):
        print("先跑 spec-gap-scan.py（缺 %s）" % SCAN)
        return 2
    scan = json.load(open(SCAN, encoding="utf-8"))
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    sys.path.insert(0, ROOT)
    from gbt_allinone import caps_registry as CR
    from gbt_allinone.security import policy as POL

    rows = []
    for r in scan.get("rows") or []:
        dom = r["domain"]
        if only and dom not in only:
            continue
        spec = r.get("spec")
        if not spec:
            rows.append({"domain": dom, "spec": None, "skipped": "该域没有规程件"})
            continue
        full = spec if os.path.isabs(spec) else os.path.join(ROOT, spec)
        caps = []
        for name in sorted(r.get("missing") or []):
            meta = (CR.BENIGN_CAPS or {}).get(name) or {}
            try:
                sc = list(getattr(POL.evaluate(name, {}), "scopes", ()) or ())
            except Exception:  # noqa: BLE001
                sc = ["<evaluate失败>"]
            caps.append({"cap": name,
                         "desc": (str(meta.get("desc") or "").strip().replace("|", "\\|") or "—")[:70],
                         "scopes": "、".join(sc) if sc else "（无）"})
        rows.append({"domain": dom, "spec": full, "caps": caps})

    todo = [r for r in rows if r.get("caps")]
    print("待补域 %d 个 · 待写入位 %d 个" % (len(todo), sum(len(r["caps"]) for r in todo)))
    for r in rows:
        if r.get("skipped"):
            print("  ⚠️ %-14s %s" % (r["domain"], r["skipped"]))

    receipt = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "dry_run": not a.apply,
               "files": [], "note": "只维护 caps-auto 标记段；段外内容不动；写前备份到 state/skill-backup/"}
    os.makedirs(BACKUP, exist_ok=True)
    for r in todo:
        p = r["spec"]
        txt = open(p, encoding="utf-8", errors="replace").read()
        blk = block_for(r["domain"], r["caps"])
        if BEGIN in txt and END in txt:
            new = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), blk.rstrip("\n"),
                         txt, flags=re.S)
            how = "替换标记段"
        else:
            new = txt.rstrip("\n") + "\n\n" + blk
            how = "追加标记段"
        before, after = sha(txt.encode("utf-8")), sha(new.encode("utf-8"))
        rel = os.path.relpath(p, ROOT) if p.startswith(ROOT) else p
        print("  %-14s %-28s %s · %d 位 · %s→%s" % (r["domain"], os.path.basename(os.path.dirname(p)) + "/SKILL.md",
                                                    how, len(r["caps"]), before, after))
        receipt["files"].append({"domain": r["domain"], "spec": p, "how": how,
                                 "caps": len(r["caps"]), "sha_before": before, "sha_after": after})
        if not a.apply:
            continue
        bak = os.path.join(BACKUP, "%s__SKILL.md.bak-%s" % (r["domain"], time.strftime("%Y%m%dT%H%M%S")))
        with open(bak, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(new)
        os.replace(tmp, p)
        receipt["files"][-1]["backup"] = bak
 # 2026-10-25 · **两个根一起维护**（缺陷修正，不是新功能）：
        # 原来只写 scan 给的**一个**路径（那个路径指向托管根 `~/.openclaw-autoclaw/skills`），
        # 源稿 `skills/<名>/SKILL.md` 从来没收到过自动段 ⇒ `verify-distill` 的 A 项
        # （源稿 vs 托管**逐字节相同**）一次报 20 个域 FAIL；而 `audit-skill-roots.py --fix`
        # 从源稿刷新副本时，又把**只存在于托管**的自动段整段覆盖掉（实测：17 段的
        # caps-auto 全部消失）。⇒ 现在同一次写入把孪生件也写成**同一份字节**，两个根从源头一致。
        twin = os.path.join(ROOT, "skills", os.path.basename(os.path.dirname(p)), "SKILL.md")
        if os.path.abspath(twin) != os.path.abspath(p) and os.path.isdir(os.path.dirname(twin)):
            tb = os.path.join(BACKUP, "%s__src-SKILL.md.bak-%s"
                              % (r["domain"], time.strftime("%Y%m%dT%H%M%S")))
            if os.path.isfile(twin):
                with open(tb, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(open(twin, encoding="utf-8", errors="replace").read())
                receipt["files"][-1]["backup_src"] = tb
            ttmp = twin + ".tmp"
            with open(ttmp, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(new)
            os.replace(ttmp, twin)
            receipt["files"][-1]["twin"] = twin

    tmp = RECEIPT + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(receipt, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, RECEIPT)
    if not a.apply:
        print("\n（dry-run：一个文件都没写。要落盘加 --apply）")
        return 0
    print("\n已写 %d 个 SKILL.md；备份在 %s；回执 %s"
          % (len(receipt["files"]), BACKUP, RECEIPT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
