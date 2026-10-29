# -*- coding: utf-8 -*-
"""生成「深蒸交付总账」—— 把每一件交付的**可复核读数**落成一张表（不是手抄，是现算）。

为什么要有它：Owner 的硬要求是「每件都要留下机器可复核的证据」。
零散的终端输出会散失，而**手抄的总账一定会走样**（本会话已经栽过：人写的索引有缝）。
所以这份总账**由脚本现算生成**，随时可重跑；表里每一格都能被三道门复核到。

用法：
    py -3.14 tools/codex-scripts/make-delivery-ledger.py          # 写到 memory/<日期>-深蒸交付总账.md
    py -3.14 tools/codex-scripts/make-delivery-ledger.py --stdout # 只打印
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
OMNI = ROOT / "tools" / "codex-scripts" / "omni.py"
ATLAS = ROOT / "state" / "skill_atlas.json"
MANAGED = Path.home() / ".openclaw-autoclaw" / "skills"


def load_map(name: str) -> dict:
    for node in ast.walk(ast.parse(OMNI.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == name:
            return dict(ast.literal_eval(node.value))
    return {}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def main(argv: list[str]) -> int:
    atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
    caps = atlas.get("caps", [])
    skills = atlas.get("skills", [])
    doms = load_map("DISTILLED_DOMAINS")
    clusters = load_map("DISTILLED_CLUSTERS")

    rows: list[tuple] = []
    for kind, mapping in (("域", doms), ("簇", clusters)):
        for key, skill in sorted(mapping.items()):
            src = ROOT / "skills" / skill / "SKILL.md"
            dst = MANAGED / skill / "SKILL.md"
            if kind == "域":
                size = len([c for c in caps if c.get("domain") == key])
                unit = "能力位"
            else:
                size = len([s for s in skills
                            if (s.get("name") or "") == key or (s.get("name") or "").startswith(key + "-")])
                unit = "技能"
            if not src.exists() or not dst.exists():
                rows.append((kind, key, skill, size, unit, "—", "—", "缺件", "—"))
                continue
            body = src.read_text(encoding="utf-8")
            rows.append((
                kind, key, skill, size, unit,
                str(src.stat().st_size), str(body.count("\n") + 1),
                "同哈希" if sha(src) == sha(dst) else "★不一致",
                str(len(re.findall(r"未验", body))),
            ))

 # 合计必须按**去重后的文件**算：`gbt-creation` 同时映射 creation 与 image_video 两个域，
    # 按"每行相加"会把它的字节/行数**记两遍**（读数虚高 = 我自己在账上撒谎，这种账不采信）。
    uniq = sorted({r[2] for r in rows})
    seen: set[str] = set()
    total_bytes = total_lines = total_unv = 0
    for r in rows:
        if r[2] in seen or not str(r[5]).isdigit():
            continue
        seen.add(r[2])
        total_bytes += int(r[5])
        total_lines += int(r[6])
        total_unv += int(r[8])
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    out: list[str] = []
    out.append("# 深蒸交付总账（**脚本现算 · 不是手抄**）")
    out.append("")
    out.append("> 生成时间：%s ｜ 生成器：`tools/codex-scripts/make-delivery-ledger.py`" % now)
    out.append(">")
    out.append("> **复核方式（五道门 + 一套自带测试，缺一条都算没验）**：")
    out.append(">")
    out.append("> ```powershell")
    out.append("> py -3.14 tools/codex-scripts/gbt-checkup.py        # ① 队列+② 内容+③ 结构+④ 设计全维度+⑤ 技能根一致，一条命令跑完")
    out.append("> py -3.14 tools/codex-scripts/run-tests.py          # 仓库自带测试（1763 项 · 约 9-10 分钟 · 会自设隔离根）")
    out.append("> py -3.14 tools/codex-scripts/verify_active.py      # 现役那一代的交付校验（自动判代次派发）")
    out.append("> ```")
    out.append("")
    out.append("- 职业域映射 **%d** 条 ｜ 技能簇映射 **%d** 条 ｜ 去重后**实际文件 %d 件**"
               % (len(doms), len(clusters), len(uniq)))
    out.append("- 合计 **%d 字节 / %d 行** ｜ 规程里「未验」标记共 **%d 处**（越诚实越该多）"
               % (total_bytes, total_lines, total_unv))
    out.append("- 图鉴现读：能力位 %d（域 %d）· 技能 %d 条"
               % (atlas["counts"]["caps"], atlas["counts"].get("domains"), atlas["counts"]["skills"]))
    out.append("")
    out.append("| 类 | 域/簇 | 深蒸件 | 规模 | 字节 | 行数 | 源↔装 | 未验 |")
    out.append("|---|---|---|---|---|---|---|---|")
    for kind, key, skill, size, unit, b, ln, same, unv in rows:
        out.append("| %s | `%s` | `%s` | %d 个%s | %s | %s | %s | %s |"
                   % (kind, key, skill, size, unit, b, ln, same, unv))
    out.append("")
    out.append("**读法**：`规模` 取自图鉴（域=该域能力位数；簇=`前缀-*` 技能数）；`源↔装` 必须全是「同哈希」；")
    out.append("`未验` 是规程里如实标注的「没跑过」条数 —— **它不扣分，它是诚实度的读数**。")
    out.append("")
    # 元/框架件：既不是职业域也不是技能簇，但确实交付在盘上 ⇒ 旧版整组漏在表外（"没查"被读成"没问题"）。
    meta = sorted(d.name for d in (ROOT / "skills").iterdir()
                  if d.is_dir() and d.name.startswith("gbt-") and d.name not in uniq
                  and (d / "SKILL.md").exists())
    out.append("**元/框架件（不在域/簇登记表里，由 `audit-regulations.py` 按盘上现读补入、同样判四节）：%d 件**"
               % len(meta))
    out.append("")
    for m in meta:
        sk = ROOT / "skills" / m / "SKILL.md"
        body = sk.read_text(encoding="utf-8")
        out.append("- `%s` — %d B / %d 行" % (m, sk.stat().st_size, body.count("\n") + 1))
    out.append("")
    out.append("> 体检 ③ 的件数是 **%d**（登记件 %d + 元/框架件 %d）；只报前者的账是漏的。" % (len(uniq) + len(meta), len(uniq), len(meta)))

    # 工作区里**自有但非 gbt-*** 的技能（例如数字人流水线）：不在两张登记表里，也不是 gbt-* 前缀，
    # 所以上面的表与元件组都收不到它们 —— 但它们是**我们自己写的**，账上不能没有。
    own_other = []
    for d in sorted((ROOT / "skills").iterdir()):
        if not d.is_dir() or d.name.startswith("gbt-"):
            continue
        sk = d / "SKILL.md"
        if not sk.exists():
            continue
        body = sk.read_text(encoding="utf-8", errors="replace")
        if any(sig in body for sig in ("GBT小土豆", "自由的风", "gbt_allinone")):
            managed = (Path.home() / ".openclaw-autoclaw" / "skills" / d.name / "SKILL.md").exists()
            own_other.append((d.name, sk.stat().st_size, body.count("\n") + 1, managed))
    if own_other:
        out.append("")
        out.append("**工作区自有的非 `gbt-*` 技能（%d 条，同样是我们写的）：**" % len(own_other))
        out.append("")
        out.append("| 技能 | 字节 | 行数 | 托管根有装机 |")
        out.append("|---|---|---|---|")
        for name, b, ln, managed in own_other:
            out.append("| `%s` | %d | %d | %s |" % (name, b, ln, "✅" if managed else "🔴 无"))
        out.append("")
        out.append("> 这几条由 `tools/codex-scripts/audit-skill-roots.py` 的 ⑤ 段守着"
                   "（孤本 / 没装机 都是硬失败）。")
    out.append("")
    out.append("> ⚠️ `DISTILLED_CLUSTERS` 里 `video` 与 `DISTILLED_DOMAINS` 里 `video` **键同名**但属两份独立字典；")
    out.append("> 报错文案若说「video 没登记」，先分清是**域**还是**簇**。（已在 `omni.py` 注释里写明。）")

    # ── 跨线总规程：不在域/簇登记表里，读数**由安装回执现算**（没有回执就如实写"未装机"）──
    # 为什么要单列：`design-inventory` 的 88 个成员跨七条线，它**不是一个职业域**，
    # 按域/簇两列枚举会把它整件漏掉 —— 而它恰恰是"融会贯通"那件事的成品。
    receipt_p = ROOT / "state" / "design-mastery-install-receipt.json"
    out.append("")
    out.append("## 跨线总规程（不在域/簇登记表里 · 读数取自安装回执）")
    out.append("")
    if receipt_p.exists():
        rec = json.loads(receipt_p.read_text(encoding="utf-8"))
        out.append("| 件 | 装机根 | 文件 | 合计字节 | 源↔装 |")
        out.append("|---|---|---|---|---|")
        for t in rec.get("targets", []):
            fs = t.get("files", [])
            tb = sum(int(f.get("bytes", 0)) for f in fs)
            ok = t.get("all_identical") and all(f.get("identical") for f in fs)
            out.append("| `gbt-design-mastery` | `%s`（%s） | %d | %d | %s |"
                       % (t.get("dst", "—"), t.get("label", "—"), len(fs), tb,
                          "逐文件同哈希" if ok else "★有不同哈希"))
        out.append("")
        out.append("> 回执：`state/design-mastery-install-receipt.json` · 落盘时间 %s" % rec.get("at", "—"))
        out.append(">")
        out.append("> 🔴 **为什么要装两处（现读实测）**：本机 DSH 的 `dsh-skill-filesystem` 只扫 "
                   "`<项目>/.dsh/skills` · `<项目>/.agents/skills` · `preset/skills` · `$DSH_HOME/skills` · `~/.agents/skills`；"
                   "**`~/.openclaw-autoclaw/skills` 不在其中** —— 只装那里，本会话读不到（用动态插件读技能层实测过）。")
        for t in rec.get("targets", []):
            if t.get("extra_in_dst"):
                out.append("> ⚠️ `%s` 里另有 %d 个多出文件（装机器**只报不删**）：%s"
                           % (t.get("label"), len(t["extra_in_dst"]), "、".join(t["extra_in_dst"][:6])))
    else:
        out.append("🔴 **还没装机**（没有 `state/design-mastery-install-receipt.json`）⇒ 体检第 ④ 关会红。")
    out.append("")
    out.append("**它的门**（与①②③分开，因为域/簇两关天然看不见它）：")
    out.append("")
    out.append("```powershell")
    out.append("py -3.14 tools/codex-scripts/design-inventory.py --check       # 88 个成员点名齐全")
    out.append("py -3.14 tools/codex-scripts/verify-design-mastery.py         # 八节 + 七份深读 + 两个装机根同哈希")
    out.append("py -3.14 tools/codex-scripts/install-design-mastery.py --check # 装机现状逐文件核对")
    out.append("py -3.14 tools/codex-scripts/mirror-design-regulations.py --check # 16 条簇规程在 DSH 根上的副本核对")
    out.append("```")

    # 设计维度 16 条簇规程镜像到 DSH 真扫得到的根（读数取自镜像回执）
    mir_p = ROOT / "state" / "design-regulations-mirror-receipt.json"
    out.append("")
    out.append("### 设计簇规程的「本会话可加载」副本（16 条）")
    out.append("")
    if mir_p.exists():
        mir = json.loads(mir_p.read_text(encoding="utf-8"))
        ps = mir.get("protocols", [])
        tb = sum(int(p.get("bytes", 0)) for p in ps)
        nf = sum(int(p.get("files", 0)) for p in ps)
        ok = mir.get("all_identical") and all(p.get("all_identical") for p in ps)
        out.append("| 落点 | 条数 | 文件 | 合计字节 | 源↔镜像 | 回执 |")
        out.append("|---|---|---|---|---|---|")
        out.append("| `%s` | %d | %d | %d | %s | `state/design-regulations-mirror-receipt.json` · %s |"
                   % (mir.get("dst_root", "—"), len(ps), nf, tb,
                      "全部逐文件同哈希" if ok else "★有不同哈希", mir.get("at", "—")))
        out.append("")
        out.append("> 为什么要有这一份：本机 DSH 只扫 `<项目>/.dsh/skills` 等五个根，**不扫 `~/.openclaw-autoclaw/skills`**；")
        out.append("> 不镜像的话，这些规程在本会话里「读得到、但点不动」。范围由主人 2026-09-22 选定：**只镜像设计维度这 16 条**。")
    else:
        out.append("🔴 **还没镜像**（没有 `state/design-regulations-mirror-receipt.json`）。")

    text = "\n".join(out) + "\n"
    if "--stdout" in argv:
        print(text)
        return 0
    dest = ROOT / "memory" / ("%s-深蒸交付总账.md" % datetime.now().strftime("%Y-%m-%d"))
    dest.write_text(text, encoding="utf-8")
    print("已写出 %s（%d 字节 · %d 件）" % (dest.relative_to(ROOT), len(text.encode("utf-8")), len(uniq)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
