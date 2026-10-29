# -*- coding: utf-8 -*-
"""深蒸件验收器：把"这件的规程能不能信"变成可跑的检查（不是通读一遍说"看着挺好"）。

为什么要有它：Owner 的硬要求是「每件都要有机器可复核的证据」「不许把没验过的命令写进规程」。
人眼通读 27 份规程是审不动的，而且**我自己就是最不可靠的那一环** —— 所以把可判定的部分交给机器：

  A. 两份产物在不在、**逐字节相同**（工作区源稿 vs managed 安装件）
  B. frontmatter 有 name / description（能被 skill 目录认出来）
  C. `omni.py` 的 `DISTILLED_DOMAINS` 里这个域**已登记成已深蒸**（图鉴口径一致）
  D. 规程里出现的每一发 `five-dim.py cap <能力位>` —— **这个能力位必须在图鉴里真存在**
     （= 抓"编出来的命令"）
     ⚠️ 写规程时的注意：域内的**子方法**名（例如触手域的 `tentacle_manifest` 之类）
     不在图鉴的 kind 里，所以**别用 `cap <子方法名>` 这种写法**去引它 —— 那会被本器判成"编造"。
     子方法直接写完整命令或换个说法即可。本器宁可保守：它只认注册位。
  E. 这个域的**每一个**能力位都在规程正文里被点到（= 抓"遗漏"，Owner 明说过别遗漏）

不可判定的部分（叙述质量、坑写得准不准）本器**不假装能判**，只在报告里列出来留给人看。

用法：
    py -3.14 tools/codex-scripts/verify-distill.py --domain system
    py -3.14 tools/codex-scripts/verify-distill.py --all
    py -3.14 tools/codex-scripts/verify-distill.py --domain system --json
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
ATLAS = ROOT / "state" / "skill_atlas.json"
OMNI = ROOT / "tools" / "codex-scripts" / "omni.py"
MANAGED = Path.home() / ".openclaw-autoclaw" / "skills"
CAP_CMD = re.compile(r"five-dim\.py\s+cap\s+([A-Za-z0-9_\-]+)")


def _dict_from_omni(name: str) -> dict:
    """从 omni.py 里取一个字面量 dict（能 AST 就 AST，取不到才退回正则）。"""
    src = OMNI.read_text(encoding="utf-8")
    try:
        for node in ast.walk(ast.parse(src)):
            targets = getattr(node, "targets", None)
            if isinstance(node, ast.Assign) and targets:
                for t in targets:
                    if getattr(t, "id", None) == name:
                        return dict(ast.literal_eval(node.value))
    except Exception as err:  # noqa: BLE001
        print("⚠️ AST 取 %s 失败（%s），退回正则" % (name, err), file=sys.stderr)
    m = re.search(name + r"\s*=\s*\{(.*?)\}", src, re.S)
    if not m:
        return {}
    return dict(re.findall(r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]", m.group(1)))


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check(domain: str, atlas: dict, dist: dict) -> dict:
    out: dict = {"domain": domain, "fail": [], "warn": [], "facts": {}}
    caps = [c for c in atlas.get("caps", []) if c.get("domain") == domain]
    out["facts"]["caps_in_atlas"] = len(caps)
    if not caps:
        out["fail"].append("图鉴里没有这个域（或它的能力位数为 0）")

    skill = dist.get(domain)
    out["facts"]["skill"] = skill
    if not skill:
        out["fail"].append("omni.py 的 DISTILLED_DOMAINS 里没登记这个域（不算已深蒸）")
        return out

    src = ROOT / "skills" / skill / "SKILL.md"
    dst = MANAGED / skill / "SKILL.md"
    for label, p in (("工作区源稿", src), ("managed 安装件", dst)):
        if not p.exists():
            out["fail"].append("%s 不在：%s" % (label, p))
    if out["fail"]:
        return out

    hs, hd = sha(src), sha(dst)
    out["facts"]["bytes"] = src.stat().st_size
    out["facts"]["sha256_head"] = hs[:16]
    out["facts"]["identical"] = hs == hd
    if hs != hd:
        out["fail"].append("两份不是逐字节相同（源稿 %s vs 安装件 %s）" % (hs[:12], hd[:12]))

    body = src.read_text(encoding="utf-8")
    if not body.startswith("---"):
        out["fail"].append("没有 frontmatter（skill 目录会认不出来）")
    else:
        fm = body.split("---", 2)[1]
        for field in ("name", "description"):
            if not re.search(r"^%s\s*:" % field, fm, re.M):
                out["fail"].append("frontmatter 缺 %s" % field)

    # D. 规程里点名的能力位必须真存在
    named = sorted(set(CAP_CMD.findall(body)))
    kinds = {c.get("kind") for c in atlas.get("caps", [])}
    out["facts"]["cap_cmds_named"] = len(named)
    invented = [n for n in named if n not in kinds]
    if invented:
        out["fail"].append("规程里点了图鉴里不存在的能位：%s" % ", ".join(invented))
    if not named:
        out["warn"].append("规程里没有任何 `five-dim.py cap <能力位>` 形式的命令 —— 是没写，还是换了别的方式？")

    # E. 这个域的能力位一个都不能漏
    missing = [c["kind"] for c in caps if not re.search(r"(?<![\w\-])%s(?![\w\-])" % re.escape(c["kind"]), body)]
    out["facts"]["caps_covered"] = len(caps) - len(missing)
    if missing:
        out["fail"].append("规程没点到这 %d 个能力位：%s" % (len(missing), ", ".join(missing)))

    # 不可判定的部分：如实计数，不当成通过
    out["facts"]["honest_unverified_marks"] = len(re.findall(r"未验", body))
    out["facts"]["lines"] = body.count("\n") + 1
    return out


def check_cluster(c: str, atlas: dict, clusters: dict) -> dict:
    """簇的验收（域的对应物）：两份同哈希 + frontmatter + **该簇每条技能都被点到**。"""
    skill = clusters.get(c)
    row: dict = {"cluster": c, "skill": skill, "fail": [], "facts": {}}
    names = [s["name"] for s in atlas.get("skills", [])
             # 判据＝**与前缀口径一致**：`<前缀>-*`。
 # 2026-09-22 **改回来**（上一轮我曾把裸名并进来，那条改动是错的）：
             #   `omni.py gaps` 的聚类是 `nm.split("-")[0] + "-*" if "-" in nm else nm`
             #   —— **裸名 `remotion` 是它自己的另一条簇**，不是 `remotion-*` 的成员。
             #   实测后果：`remotion-*` 12 条 + 裸名 1 条（`design-asset` 审美桩）
             #   ⇒ 旧判据算出 13，而规程按 12 条写、条条点到，却被判 FAIL —— **那是判据错，不是件错**。
             #   裸名兄弟改为**只报告不计入**（见下面 bare_name_sibling），由作者决定要不要一并写。
             if str(s.get("name") or "").startswith(c + "-")]
    bare = [s["name"] for s in atlas.get("skills", []) if str(s.get("name") or "") == c]
    if bare:
        row["facts"]["bare_name_sibling"] = bare  # 信息项：同名的**另一条簇**，不计入覆盖
    row["facts"]["skills_in_atlas"] = len(names)
    if not skill:
        row["fail"].append("omni.py 的 DISTILLED_CLUSTERS 里没登记这个簇")
        return row
    src = ROOT / "skills" / skill / "SKILL.md"
    dst = MANAGED / skill / "SKILL.md"
    if not src.exists() or not dst.exists():
        row["fail"].append("规程不在：%s" % (src if not src.exists() else dst))
        return row
    hs, hd = sha(src), sha(dst)
    row["facts"]["bytes"] = src.stat().st_size
    row["facts"]["identical"] = hs == hd
    if hs != hd:
        row["fail"].append("两份不是逐字节相同")
    body = src.read_text(encoding="utf-8")
    fm = body.split("---", 2)[1] if body.startswith("---") else ""
    for field in ("name", "description"):
        if not re.search(r"^%s\s*:" % field, fm, re.M):
            row["fail"].append("frontmatter 缺 %s" % field)
    missing = [n for n in names
               if not re.search(r"(?<![\w\-])%s(?![\w\-])" % re.escape(n), body)]
    row["facts"]["skills_covered"] = len(names) - len(missing)
    if missing:
        row["fail"].append("规程没点到这 %d 条技能：%s" % (len(missing), ", ".join(missing)))
    return row


def main(argv: list[str]) -> int:
    atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
    doms = _dict_from_omni("DISTILLED_DOMAINS")
    clusters = _dict_from_omni("DISTILLED_CLUSTERS")
    want: list[str] = []
    if "--all" in argv:
        want = sorted(doms.keys())
    elif "--domain" in argv:
        want = [argv[argv.index("--domain") + 1]]
        # --skill：拿某个域去"探"一份**还没登记**的规程（用来判"这个域是不是其实已经有人写了"，
        # 免得重复劳动；也用来审老件到底覆盖了没有）。
        if "--skill" in argv:
            doms = dict(doms)
            doms[want[0]] = argv[argv.index("--skill") + 1]
    elif "--cluster" in argv:
        want = [argv[argv.index("--cluster") + 1]]
    else:
        print(__doc__)
        return 2

    if "--cluster" in argv:
 # 2026-09-22 补：簇也要有**内容级**验收，不能只看"两份在不在"。
        # 域的覆盖判据是"该域每个能力位都被点到"；簇的对应判据是
        # **"该簇每条技能名都被点到"**（图鉴里 name 以 `<stem>-` 开头的那批）。
        rows = [check_cluster(c, atlas, clusters) for c in want]
        hard = [r for r in rows if r["fail"]]
        print(json.dumps({"clusters": rows, "hard_failures": len(hard),
                          "verdict": "PASS" if not hard else "FAIL"},
                         ensure_ascii=False, indent=1))
        return 1 if hard else 0

    results = [check(d, atlas, doms) for d in want]
    # 已登记为已深蒸的域：这些**必须**全过；在队里的域查出来是 FAIL 属正常
    for r in results:
        r["registered"] = r["domain"] in doms
    hard = [r for r in results if r["registered"] and r["fail"]]
    pending = [r for r in results if not r["registered"]]
    for r in pending:
        r["fail"] = [f for f in r["fail"] if "没登记" not in f]  # 在队 = 正常，不算缺陷

    if "--json" in argv:
        print(json.dumps({"results": results, "hard_failures": len(hard)}, ensure_ascii=False, indent=1))
    else:
        for r in results:
            tag = "在队（未深蒸）" if not r["registered"] else ("PASS" if not r["fail"] else "FAIL")
            print("=" * 78)
            print("%-12s %s" % (r["domain"], tag))
            for k, v in r["facts"].items():
                print("   · %-24s %s" % (k, v))
            for f in r["fail"]:
                print("   ✗ %s" % f)
            for w in r["warn"]:
                print("   ! %s" % w)
        print("=" * 78)
        print("已登记域的硬失败：%d 个%s" % (len(hard), "（这就是不合格件，必须回到那份规程里修）" if hard else " —— 已交付件全过"))
        if "--all" in argv and clusters:
            # `--all` 也要管**簇那一半**：只查域会让 20 个技能簇永远没人验收。
            crows = [check_cluster(c, atlas, clusters) for c in sorted(clusters.keys())]
            print("-" * 78)
            print("技能簇 %d 个（已登记）" % len(crows))
            for r in crows:
                tag = "PASS" if not r["fail"] else "FAIL"
                print("   %-14s %-4s 覆盖 %s/%s  %s" % (
                    r["cluster"], tag, r["facts"].get("skills_covered", "-"),
                    r["facts"].get("skills_in_atlas", "-"),
                    "；".join(r["fail"])[:70]))
            chard = [r for r in crows if r["fail"]]
            print("已登记簇的硬失败：%d 个%s" % (len(chard), "" if chard else " —— 簇也全过"))
    return 1 if (hard or (("--all" in argv) and clusters
                          and any(check_cluster(c, atlas, clusters)["fail"] for c in clusters))) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
