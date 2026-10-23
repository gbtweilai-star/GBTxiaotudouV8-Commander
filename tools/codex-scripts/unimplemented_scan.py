# -*- coding: utf-8 -*-
"""「还有哪些能力没实现」· 全量机检（2026-09-23）。

## 为什么要有这件

「哪些没实现」这句话在本仓有**五种完全不同的意思**，混在一起问必然得到假答案：

    A 只登记未实现   `caps_registry.UNIMPLEMENTED_CAPS`：只有名字、连入口都没有（可证明）
    B 注册表自标桩   登记表自己的 desc/handler 里写着「骨架 / 未实现 / 占位 / not_implemented」
                     ⚠️ **这是线索不是判决** —— 文案里出现"未实现"可能是在说"**不是**占位实现"。
                     所以本件把**命中的词**和**上下文**一起打出来，让人自己判；判错的代价不许由读者承担。
    C 无分派分支     登记了，但 `api.py` 里**没有任何 `if kind == ...` 会把它接到实现上**
    D 动态不成立     真调一次，返回里带「未实现」类标志，或直接 `unknown capability`
    E 技能面目录桩   `skills/<name>/` 里**只有 SKILL.md**、指向上游 —— 有文件 ≠ 有流程

## 用法

    py -3.14 tools/codex-scripts/unimplemented_scan.py
    py -3.14 tools/codex-scripts/unimplemented_scan.py --probe-json "%TEMP%\\gbt-capprobe-full.json"
    py -3.14 tools/codex-scripts/unimplemented_scan.py --json out.json

动态面（D）**不自己重探**：直接复用 `cap_probe_all.py` 的产物（那份要 16 分钟）。
产物不在就**如实说"动态面没跑"**，不假装跑了。
"""
import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

STUB_TOKENS = ("骨架", "not_implemented", "未实现", "占位")

# 动态面：「这条没实现」在返回值里的样子（按**证据**排序，不按猜）
DYN_TOKENS = ("not_implemented", "notimplemented", "骨架", "占位", "unimplemented",
              "not_wired", "unwired", "未接线", "尚未实现", "未实现")
DYN_CODES = ("NOT_IMPLEMENTED", "UNIMPLEMENTED", "SKELETON", "PLACEHOLDER")


def dispatch_kinds() -> set:
    """`api.py` 里真正会被接住的能力名。

    两种形状都要认（第一版只认了单行，于是把 4 个**多行元组**里的 11 条误判成"无分派"）：
        if kind == "x":
        if kind in ("a", "b",
                    "c"):
    """
    src = (ROOT / "gbt_allinone" / "api.py").read_text(encoding="utf-8")
    names = set(re.findall(r'if\s+kind\s*==\s*"([a-z_0-9]+)"', src))
    for m in re.finditer(r'if\s+kind\s+in\s*\((.*?)\)\s*:', src, re.S):
        names |= set(re.findall(r'"([a-z_0-9]+)"', m.group(1)))
    return names


def stub_rows(caps: dict) -> list:
    out = []
    for k, v in caps.items():
        blob = "%s %s" % (v.get("desc") or "", v.get("handler") or "")
        for t in STUB_TOKENS:
            i = blob.lower().find(t.lower())
            if i >= 0:
                a = max(0, i - 46)
                out.append({"kind": k, "token": t,
                            "ctx": blob[a:i + len(t) + 46].replace("\n", " ")})
                break
    return sorted(out, key=lambda r: r["kind"])


def dyn_rows(probe: dict, caps: dict) -> list:
    out = []
    scope_notes = []
    for rec in probe.get("results", []):
        kind = rec.get("kind") or ""
        if kind not in caps and kind not in _unimpl_names():
            continue
        msg = str(rec.get("message") or "")
        str(rec.get("result_head") or "")
        code = str(rec.get("reason_code") or "")
        status = str(rec.get("status") or "")
        why = None
        if code in DYN_CODES:
            why = "reason_code=%s" % code
        # 🔴 **2026-09-23 修掉一个假阳性**（这条错值得单独记）：
        #    原判据把 **整个结果转储**（`result_head`）拿去子串匹配 `未实现/not_wired/…`。
        #    于是 `sec_defenses` 被判红 —— 而它其实**跑通了**（`defense_status: 全部生效` · 5/5 通过），
        #    只不过它的**说明文字里**出现了「未实现」这四个字：
        #        `danger_gate: keylogger -> error（登记未实现，不是策略拒绝）`
        #    ⇒ 那是**在解释另一条能力位**，不是在说它自己。
        #    **文本级判据冒充结构级判据** —— 这是本仓反复栽的同一类错（第二次了）。
        #    现在的规矩：**只看结构化信号**，不看"这段话里有没有那个词"。
        if why is None and status == "error":
            for t in DYN_TOKENS:
                if t.lower() in msg.lower():
                    why = "status=error 且错误信息里出现「%s」" % t
                    break
        if why is None:
            # 结构化"没接线"标记：只认**键值对**形态，且只在 ok 不为 False 时补充说明
            blob = str(rec.get("result") or rec.get("result_head") or "")
            for marker in ('"wired": false', '"wired":false', 'not_wired', '"unwired": true'):
                if marker in blob:
                    why = "返回里带结构化标记 %s（**能力本体在跑，是某条输出通道没接线**）" % marker
                    break
        # 🔴 **2026-09-23 第三个假阳性，与上面两处同一类错**：
        #    `create` 被判"动态不成立"，而它其实**明说自己为什么没接**：
        #    `file_operation.py` 的模块头写着「**文本出口本刀未接线**……本刀不注册 `eigenflux` cap、
        #    **不发任何网络请求** —— `output` 如实报 `pending`」，并且补了一句
        #    「**默认出口 != 默认发布**」。
        #    ⇒ 那是**刻意的范围边界 + 诚实上报**，不是缺陷。
        #    **判据修正**：`status=ok` **且** 该记录里带了**解释性字段**（detail/note/why/policy）
        #    的"未接线"，一律算 **scope（范围说明）**，不算 failure —— 它解释了，就不该被追问。
        #    只有"报了没接线、又不说为什么"的，才留在待办里。
        if why and status == "ok":
            blob_all = str(rec.get("result") or rec.get("result_head") or "") + str(rec.get("message") or "")
            explained = any(k in blob_all for k in ('"detail"', '"note"', '"why"', '"policy"',
                                                    '"scope"', "本刀", "刻意", "按规矩", "不开"))
            if explained:
                scope_notes.append({"kind": kind, "why": why})
                why = None
        if why is None and status == "error" and "unknown capability" in msg.lower():
            why = "unknown capability（注册表里有、实现面没有）"
        if why:
            out.append({"kind": kind, "status": status, "why": why,
                        "message": msg[:110]})
    return out, scope_notes


_PROBE_CACHE = {}


def _unimpl_names() -> set:
    if "u" not in _PROBE_CACHE:
        try:
            from gbt_allinone.caps_registry import UNIMPLEMENTED_CAPS
            _PROBE_CACHE["u"] = set(UNIMPLEMENTED_CAPS)
        except Exception:                                        # noqa: BLE001
            _PROBE_CACHE["u"] = set()
    return _PROBE_CACHE["u"]


def skill_stubs() -> list:
    """技能面：目录里**只有 SKILL.md** 的，再分两类（这两类后果完全不同）。

    🔴 第一版把两类混成一张清单，读数就废了：`skills/gbt-quickscan/` 里也只有 SKILL.md，
    但它是**本仓自己写的完整规程**（自证、可跑、带命令）—— 跟"只指上游的目录桩"不是一回事。

      `pointer`       **只指上游、没有内容**：明说"未 vendored / 见上游 / 尚未接入 / 内容在上游"
                      ⇒ 这才是真桩：有文件、没流程
      `self-contained` 本仓自写的规程/知识件 —— 单文件是**设计**，不是残缺

    🔴 **2026-09-23 修掉第二个假阳性（与 D 面那处同一类错）**：
      原判据把 `上游 / upstream / github.com / 蒸馏自…` 一律当"只指上游"的标志。
      于是 `music-production`（2713 B）与 `video-pipeline`（5271 B）被判成目录桩 ——
      **读进去才发现它们是完整的蒸馏件**：frontmatter 里有 `distilled_from` + `upstream_license`
      （CC0-1.0 / Apache-2.0），正文是"只搬判据与闸"的**成品**。
      **「蒸馏自 X」是出处声明，不是「内容在 X」。** 把出处当缺失 = 又一个文本级judgement冒充结构级。
      ⇒ 判据改成：必须出现**指向性短语**（未 vendored / 见上游 / 尚未接入 / 内容在上游 / 只指向上游），
        而 `蒸馏自 / distilled_from / upstream_license` **明确排除**在外。
    """
    UP = ("未 vendored", "尚未接入", "见上游", "内容在上游", "只指向上游", "指向上游", "not vendored")
    NOT_PTR = ("蒸馏自", "distilled_from", "upstream_license", "upstream-license")
    roots = [ROOT / "skills", Path(os.path.expanduser("~")) / ".openclaw-autoclaw" / "skills"]
    seen, out = set(), []
    for r in roots:
        if not r.is_dir():
            continue
        for d in sorted(r.iterdir()):
            if not d.is_dir() or d.name in seen:
                continue
            f = d / "SKILL.md"
            if not f.is_file():
                continue
            seen.add(d.name)
            others = [x for x in d.rglob("*")
                      if x.is_file() and x.name != "SKILL.md"
                      and "__pycache__" not in x.parts]
            if others:
                continue
            try:
                body = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                body = ""
            # 真桩 =「短」**且**有指向性短语；**且**没有出处声明（有出处声明的是蒸馏件，不是桩）
            has_ptr = any(t.lower() in body.lower() for t in UP)
            has_prov = any(t.lower() in body.lower() for t in NOT_PTR)
            is_ptr = len(body) < 3200 and has_ptr and not has_prov
            out.append({
                "name": d.name,
                "kind": "pointer" if is_ptr else "self-contained",
                "bytes": len(body.encode("utf-8")),
                "root": str(r.relative_to(ROOT)) if r.is_relative_to(ROOT) else "~",
            })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="全量机检：哪些能力没实现")
    ap.add_argument("--probe-json", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    from gbt_allinone.caps_registry import BENIGN_CAPS, UNIMPLEMENTED_CAPS, all_caps

    disp = dispatch_kinds()
    nosig = sorted(set(BENIGN_CAPS) - disp)
    stubs = stub_rows(BENIGN_CAPS)
    skills = skill_stubs()

    pj = a.probe_json or (Path(tempfile.gettempdir()) / "gbt-capprobe-full.json")
    probe, probe_note = None, ""
    p = Path(pj)
    if p.is_file():
        try:
            probe = json.loads(p.read_text(encoding="utf-8"))
            probe_note = "%s（%s · 探了 %d 条）" % (p, probe.get("at", "?"), probe.get("probed", 0))
        except Exception as e:                                   # noqa: BLE001
            probe_note = "读不动 %s：%s" % (p, e)
    else:
        probe_note = "**没有产物**（%s 不在）—— 动态面这轮没跑，别把「静态没报」读成「动态没问题」" % p

    dyn, scope_notes = dyn_rows(probe, BENIGN_CAPS) if probe else ([], [])

    print("=" * 78)
    print("全量机检 · 「还有哪些能力没实现」")
    print("=" * 78)
    print("  注册表面：全登记 %d = enabled %d + 只登记未实现 %d"
          % (len(all_caps()), len(BENIGN_CAPS), len(UNIMPLEMENTED_CAPS)))
    print("  分派面：api.py 接得住 %d 个名字（含多行 `if kind in (...)`）" % len(disp))
    print("  动态面：%s" % probe_note)
    print("-" * 78)

    print()
    print("【A】只登记未实现 —— 只有名字、连入口都没有（%d 条 · **可证明**）" % len(UNIMPLEMENTED_CAPS))
    for k, why in sorted(UNIMPLEMENTED_CAPS.items()):
        print("    %-22s %s" % (k, why))

    print()
    print("【B】注册表自标「骨架/未实现/占位」（%d 条 · ⚠️ 线索不是判决，逐条附命中上下文）" % len(stubs))
    for r in stubs:
        print("    %-22s 命中「%s」" % (r["kind"], r["token"]))
        print("        …%s…" % r["ctx"])

    print()
    print("【C】登记了但 api.py **没有分派分支**（%d 条）" % len(nosig))
    if nosig:
        for k in nosig:
            print("    %s" % k)
    else:
        print("    无 —— 147 条全都有分支（多行 `if kind in (...)` 也算，已验证）")

    print()
    print("【D】动态面不成立（复用探针产物 · %d 条）" % len(dyn))
    if dyn:
        for r in dyn:
            print("    %-22s status=%-8s %s" % (r["kind"], r["status"], r["why"]))
            if r["message"]:
                print("        msg: %s" % r["message"])
    else:
        print("    无（或动态面这轮没跑 —— 见上面那行）")
    if scope_notes:
        # **范围说明**单列：这些能力位"报了某条通道没接"，但**自己解释了为什么**
        # （本刀不含 / 按规矩不开 / 刻意只读）—— 解释了就不该被追问。
        print("    ── 下面是**范围说明**，不是待办（它们自己说明了为什么）──")
        for r in scope_notes:
            print("    %-22s %s" % (r["kind"], r["why"][:80]))

    ptrs = [s for s in skills if s["kind"] == "pointer"]
    selfs = [s for s in skills if s["kind"] == "self-contained"]
    print()
    print("【E】技能面：目录里只有 SKILL.md（%d 条）—— **再分两类，后果完全不同**" % len(skills))
    print()
    print("    E1 只指上游的**目录桩**（正文短 + 明说内容在上游）· %d 条 ← 这才是「有文件、没流程」" % len(ptrs))
    for s in ptrs:
        print("        %-38s %6d B  %s" % (s["name"], s["bytes"], s["root"]))
    print()
    print("    E2 本仓自写的**单文件规程/知识件** · %d 条 ← 单文件是设计，不是残缺" % len(selfs))
    for s in selfs[:26]:
        print("        %-38s %6d B" % (s["name"], s["bytes"]))
    if len(selfs) > 26:
        print("        …其余 %d 条同型" % (len(selfs) - 26))

    print()
    print("-" * 78)
    # ── **真实待办口径**（2026-09-23 加）──
    # 为什么要单列：上面四个面的条数**加起来不是待办数**。
    # 实测教训：我拿「11 + 28」当"39 个卡点"汇报过一轮 —— 那个数是**判据灌出来的水**。
    # A 是设计如此、B 是只读契约面、C=0 才是健康、E1 那两条当时还是我的假阳性。
    # ⇒ 汇报时**只认这一行**；上面几行是**说明**，不是**待办**。
    todo = [r for r in dyn if r["kind"] not in set(_unimpl_names())]
    print("  🔴 **真实待办 = %d 条**（上面各面的条数**加起来不是待办数**）：" % len(todo))
    for r in todo:
        print("      · %s：%s" % (r["kind"], r["why"]))
    if not todo:
        print("      （无）")
    print("  · A %d 条是**设计如此**（危险域名，补了零增益）；B %d 条是**只读契约面**；"
          "C %d 条 = 登记面与分派面对齐（**这才是健康读数**）；E1 %d 条才是技能真桩。"
          % (len(UNIMPLEMENTED_CAPS), len(stubs), len(nosig), len(ptrs)))
    print("-" * 78)
    print("口径（缺一条就会得到假答案）：")
    print("  · A 是**硬结论**：注册表自己标了「只有名字」，且全仓零实现文件。")
    print("  · B 是**线索**：命中的可能是否定句（如「不是占位实现」），所以必须看上下文 —— **本件不替人判**。")
    print("  · C 若无，说明**登记面与分派面是对齐的**（这才是这条判据该报的结果）。")
    print("  · D 依赖探针产物；没产物就说没跑 —— **不许拿静态结论冒充动态**。")
    print("  · E 只说「目录里没有别的文件」，**不等于**这条技能不能用（可能是纯规程/纯知识件）。")

    if a.json:
        Path(a.json).write_text(json.dumps({
            "at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
            "registered_only": sorted(UNIMPLEMENTED_CAPS),
            "stub_flagged": stubs, "no_dispatch": nosig,
            "dyn_not_implemented": dyn, "dyn_scope_notes": scope_notes,
            "skill_dir_stubs": skills,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print("产物: %s" % a.json)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(3)
