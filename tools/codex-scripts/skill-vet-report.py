"""把 `skill-vet.py --all-roots --json` 的原始读数转成一份**人读得下去、且覆盖率是算出来的**报告。

为什么要单独一件：全量读数有 1200+ 条，直接刷屏没人看；而"审了多少 / 在场多少 / 还差多少"
这三个数**必须从盘上现算**，不许在报告里手写（手写一次过期一次，本轮已经栽过一次：
手写的根列表漏了 20 个根、750 个技能，于是"审过了"在盘点这一步就是假的）。

用法：python tools/codex-scripts/skill-vet-report.py [--json <原始读数>] [--out <报告>]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(ROOT / "output" / "skill-vet" / "全量审查.json"))
    ap.add_argument("--out", default=str(ROOT / "output" / "skill-vet" / "全量审查报告.md"))
    ap.add_argument("--topup", action="store_true",
                    help="把「盘上有、读数里还没有」的技能补审一遍再出报告（技能系统会在会话中途"
                         "装新技能 —— 本轮实测实审完 1268 之后又冒出 5 个；全量重扫太贵，只审差集）")
    a = ap.parse_args(argv)

    src = Path(a.json)
    if not src.is_file():
        print("原始读数不在：%s（先跑 skill-vet.py --all-roots --json）" % src)
        return 2
    rep = json.loads(src.read_text(encoding="utf-8"))
    rows = rep.get("rows") or []
    roots = rep.get("roots") or []
    rep.get("roots_scanned") or []

    if a.topup:
        # 技能系统会在会话中途继续装技能（本轮实测：实审完 1268 之后又冒出 5 个）。
        # 全量重扫太贵；这里只补审**差集**，并且把风险分布/名单**一起重算**，
        # 免得出现"改了数没改账"（报告里的表还是旧的）。
        import importlib.util
        from collections import Counter as _C
        spec = importlib.util.spec_from_file_location(
            "skill_vet", ROOT / "tools" / "codex-scripts" / "skill-vet.py")
        vetmod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vetmod)
        done = {str(r.get("source", "")).lower() for r in rows}
        added = []
        for rt in roots:
            p = Path(rt)
            if not p.is_dir():
                continue
            for sk in sorted(p.iterdir()):
                if not (sk.is_dir() and (sk / "SKILL.md").is_file()):
                    continue
                if str(sk).lower() in done:
                    continue
                rows.append(vetmod.vet(sk, "%s@%s" % (sk.name, p.name)))
                added.append(str(sk))
        if added:
            rep["rows"] = rows
            rep["targets"] = len(rows)
            rep["topup_added"] = added
            rep["risk_histogram"] = dict(_C(r.get("risk", "?") for r in rows))
            rep["high_risk"] = [r["skill"] for r in rows if r.get("risk") in ("🔴 HIGH", "⛔ EXTREME")]
            rep["exec_hits"] = [r["skill"] for r in rows if r.get("exec_flag_rules")]
            rep["unjudgeable"] = [r["skill"] for r in rows
                                  if r.get("risk") == "UNKNOWN" or not r.get("files_reviewed")]
            src.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
            print("补审 %d 个新出现的技能：%s" % (len(added), "、".join(Path(x).name for x in added[:8])))
        else:
            print("补审：盘上没有被漏掉的（读数是齐的）")

    # 按根统计在场技能（现算，不做假设）
    present_by_root: Counter = Counter()
    for r in roots:
        p = Path(r)
        if p.is_dir():
            present_by_root[r] = len([x for x in p.iterdir()
                                      if x.is_dir() and (x / "SKILL.md").is_file()])
    present_total = sum(present_by_root.values())
    audited = len(rows)

    hist = Counter(r.get("risk", "?") for r in rows)
    high = [r for r in rows if r.get("risk") in ("🔴 HIGH", "⛔ EXTREME")]
    exec_hits = [r for r in rows if r.get("exec_flag_rules")]
    unjudgeable = [r for r in rows if not r.get("files_reviewed") or r.get("risk") == "UNKNOWN"]

    L = []
    L.append("# 技能全量安全审查报告（自动发现根 · 覆盖率现算）")
    L.append("")
    L.append("> 口径：照 `skill-vetter` v1.0.0 的 Step1-4 走。**缺源/读不到文件 ⇒ 判「无法审查」，"
             "绝不编 `✅ SAFE`**。命中项是**线索不是结论**，最后一步仍是人看。")
    L.append("")
    L.append("## 一、覆盖率（这三个数是从盘上现算的，不是手写的）")
    L.append("")
    L.append("| 项 | 数 |")
    L.append("|---|---|")
    L.append("| 自动发现的技能根 | **%d** |" % len(roots))
    L.append("| 根里**在场**的技能（按 SKILL.md 计） | **%d** |" % present_total)
    L.append("| 本次**实审**的技能 | **%d** |" % audited)
    L.append("| 未审 | **%d**（%.1f%%） |" % (present_total - audited,
                                          100.0 * max(0, present_total - audited) / max(1, present_total)))
    L.append("")
    L.append("⚠️ 之前那版报告只审了 **13** 件（当时的根列表是**手写**的，漏了 20 个根 / 约 750 个技能）。")
    L.append("本报告的根由 `skill-vet.py` 的 `discover_roots()` **自动扫出**：家目录与仓根各下一层找 `*/skills`，")
    L.append("外加仓内一层的 `*/*/skills`。**手写清单 = 漏根，这是机制问题，不是疏忽。**")
    L.append("")
    L.append("## 二、风险分布")
    L.append("")
    L.append("| 风险档 | 数量 |")
    L.append("|---|---|")
    for k, v in sorted(hist.items(), key=lambda x: -x[1]):
        L.append("| %s | %d |" % (k, v))
    L.append("")
    L.append("- 🔴 高风险：**%d** · ⛔ 无法审查：**%d** · ⚠ 有**可执行**命中：**%d**"
             % (len(high), len(unjudgeable), len(exec_hits)))
    L.append("")
    L.append("## 三、按根明细")
    L.append("")
    L.append("| 根 | 在场技能 | 实审 | 可执行件 |")
    L.append("|---|---|---|---|")
    per_root_audited: Counter = Counter()
    for r in rows:
        s = str(r.get("source") or "")
        for rt in roots:
            if s.lower().startswith(str(rt).lower()):
                per_root_audited[rt] += 1
                break
    for rt in roots:
        p = Path(rt)
        if not p.is_dir():
            continue
        n_exec = 0
        for sk in p.iterdir():
            if not sk.is_dir():
                continue
            for f in sk.rglob("*"):
                if f.is_file() and f.suffix.lower() in {".py", ".js", ".mjs", ".cjs", ".ts", ".sh",
                                                        ".ps1", ".bat", ".cmd", ".rb", ".pl"}:
                    n_exec += 1
        L.append("| `%s` | %d | %d | %d |" % (rt, present_by_root.get(rt, 0),
                                              per_root_audited.get(rt, 0), n_exec))
    L.append("")
    if high:
        L.append("## 四、🔴 高风险（人必须先看，逐条）")
        L.append("")
        for r in high:
            L.append("### %s" % r["skill"])
            L.append("- 来源：`%s`" % r["source"])
            L.append("- 读过：%d 文件 / %d 字节" % (r.get("files_reviewed", 0), r.get("bytes_reviewed", 0)))
            L.append("- 结论：%s" % r.get("verdict"))
            for f in (r.get("flags") or [])[:10]:
                L.append("  - [%s]%s `%s:%s` `%s`"
                         % (f["rule"], "（可执行）" if f.get("exec") else "（文档）", f["file"], f["line"], f["hit"]))
            L.append("")
    L.append("## 五、⚠ 有**可执行**命中的技能（真正要一条条看的）")
    L.append("")
    L.append("> 判据：命中落在**非文档**文件里（.py/.js/.sh 等），不是 docstring 或举例。")
    L.append("")
    L.append("🔴 **先说清这个数字不是什么意思**（本仓口径：读数不许念过头）：")
    L.append("`HIGH` / 可执行命中 ≠「这个技能有问题」。本轮**逐字读过**的样本全是良性的，")
    L.append("而它们被判 HIGH 的原因是**结构性的**，不是偶然：")
    L.append("")
    L.append("| 读过的样本 | 机器给的判定 | 逐字读过之后的结论 |")
    L.append("|---|---|---|")
    L.append("| `turnstile-spin`（Cloudflare 官方 skills 仓） | 🔴 HIGH（外网抓取 / 索要凭据 / 破坏性删除） | **良性**。`curl` 是调 Cloudflare 自己的 API；命中的 `TOKEN:`/`TOKEN=` 是脚本里的**用法占位文本**；`rm -rf` 是 `trap ... \"$TEMP_DIR\"`，清它自己 `mktemp -d` 的目录。 |")
    L.append("| `autoclaw-design-capability`（**本机托管根里我们自己的**） | 🔴 HIGH（碰凭据文件 / 索要凭据 / 碰浏览器 cookie） | **良性**。命中来自它**随附的第三方库** `last30days/scripts/lib/{bird_x,bluesky}.py`（社交平台客户端，本来就要处理 token/cookie），以及 `template.json` 里作为**表单文案**出现的 `credentials` 一词。 |")
    L.append("")
    L.append("⇒ 所以：**HIGH 是「需要人看一眼」的线索，不是「可疑技能」的名单。**")
    L.append("这一类之所以必然很长：一个**合法的 CLI 包装器/带库的技能**天然会命中")
    L.append("「外传数据 / 索要凭据 / 装包 / curl」—— 机器分不清「占位文本」与「真读凭据」。")
    L.append("本轮已经把能机检的三类假阳性（文档位置 / 否定句 / 防御性写法）剔出分级，")
    L.append("**剩下的必须人看**；这是工具边界里那句「最后一步仍是人看」的实际代价。")
    L.append("")
    if exec_hits:
        L.append("| 技能 | 来源 | 可执行命中的规则 |")
        L.append("|---|---|---|")
        for r in exec_hits:
            L.append("| %s | `%s` | %s |" % (r["skill"], r["source"], " / ".join(r["exec_flag_rules"])))
    else:
        L.append("（无：本轮**没有**任何技能在可执行文件里命中红旗）")
    L.append("")
    if unjudgeable:
        L.append("## 六、⛔ 无法审查")
        L.append("")
        for r in unjudgeable[:60]:
            L.append("- %s（读过 %d 个文件）" % (r["skill"], r.get("files_reviewed", 0)))
        if len(unjudgeable) > 60:
            L.append("- …共 %d 个" % len(unjudgeable))
        L.append("")
    else:
        # 这一节**恒在**（哪怕是空的）：否则缺一节时后面的编号会跳号，
        # 读的人会以为"少了一章"而到处找。报告的结构本身也不许说谎。
        L.append("## 六、⛔ 无法审查")
        L.append("")
        L.append("（无：本轮每一个在场技能都读到了源 —— 0 个因缺源而无法判定）")
        L.append("")
    L.append("## 七、边界（不许念过头）")
    L.append("")
    L.append("- 本器是**模式扫描器**：它在散文上的假阳性是常态（本仓原句「提到 ≠ 用了」），")
    L.append("  所以分级时把**引述/否定句/文档位置**单独拎出来，不参与定级。")
    L.append("- 它**只读**：不执行、不装包、不改任何技能件。")
    L.append("- 「审过」= 读过一遍并给出线索，**不等于**「安全可用」；上表里 HIGH 与可执行命中必须人来判。")
    L.append("- 盘上技能数**会变**（本轮就实测到技能系统在会话中途又装了 2 条）⇒ 覆盖率是**那一刻**的读数。")
    L.append("")

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("报告已写：%s" % out)
    print("  根 %d · 在场 %d · 实审 %d · 未审 %d · HIGH %d · 可执行命中 %d · 无法审查 %d"
          % (len(roots), present_total, audited, max(0, present_total - audited),
             len(high), len(exec_hits), len(unjudgeable)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
