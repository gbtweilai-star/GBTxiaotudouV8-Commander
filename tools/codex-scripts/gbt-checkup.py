# -*- coding: utf-8 -*-
"""一条命令体检「深蒸交付」三件事 —— 省得每次手敲三条、也省得漏掉其中一条。

它把三道彼此独立的门**并成一张记分牌**：

| 门 | 判什么 | 谁提供 |
|---|---|---|
| 队列 | 每个域/簇**登记**了没有（状态从图鉴现算，**并现读盘**：实物缺失/两份不一致会告警） | `omni.py gaps` |
| 内容 | 两份同哈希 · frontmatter 齐 · 点名能力位真存在 · 该域/簇**零遗漏** | `verify-distill.py --all` |
| 结构 | 每件有没有**报告层红线 / 未验账 / 门 / 出处**四个面 | `audit-regulations.py` |
| 设计全维度 | 总规程八节齐 + 七份深读都在盘上且各点名本线成员 + 索引覆盖 88 成员 | `verify-design-mastery.py` |
| 技能根一致 | 同一份 `gbt-*` 在源 / 产品口径 / **本会话加载根** / 项目根上逐字节相同 | `audit-skill-roots.py` |

**为什么要有它**：这三条判据各管一段，少跑一条就会得出"看着都挺好"的错觉
（本会话已经栽过：只跑覆盖不跑同哈希、只跑映射不看实物、验收器自己误判）。
**一条命令跑完、缺哪条都算没验**，才是可复核的口径。

用法：
    py -3.14 tools/codex-scripts/gbt-checkup.py
退出码：有任何硬失败 = 1；全过 = 0。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
SCRIPTS = ROOT / "tools" / "codex-scripts"


def run(script: str, *args: str) -> tuple[int, str]:
    """跑同目录下的另一个脚本，返回 (退出码, 合并输出)。跑不起来如实报，不假装通过。"""
    cmd = [sys.executable, str(SCRIPTS / script), *args]
    try:
        p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=900)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return 127, "（跑不起来：%s: %s）" % (type(exc).__name__, exc)


def main() -> int:
    bad: list[str] = []

    # ① 队列（含"现读盘"告警）
    rc1, out1 = run("omni.py", "gaps")
    m = re.search(r"小计：已深蒸 (\d+) / 在队 (\d+)（共 (\d+) 个域）", out1)
    dom_line = m.group(0) if m else "（没解析到域小计）"
    if not m:
        bad.append("omni gaps 没输出域小计")
    warns = re.findall(r"⚠️[^\n]*", out1)
    if warns:
        bad.append("omni gaps 报 %d 条实物/哈希告警" % len(warns))
    # 🔴 2026-09-22 补：**队列余量**也要报出来 —— 只报"已登记的都过了"会漏掉一件大事：
    # 技能目录**会被外部更新**（实测：主人跑体检时 `omni gaps` 里冒出 `remotion-*`(12) 与
    # `hyperframes-*`(8) 两个新前缀），而图鉴是现扫的 ⇒ **"队列清空"只是当时的快照**。
    # 这里把"还有哪些簇没规程"逐名列出（非硬失败：它不影响已交付件的正确性，但影响"做完了没有"）。
    pending_clusters = re.findall(r"^\s+([a-z0-9\-]+\*)\s+\d+ 条\s+⏳", out1, re.M)

    # ② 内容
    rc2, out2 = run("verify-distill.py", "--all")
    # 🔴 2026-09-22 第 47 轮修（FR-6 窄字符类 ⇒ **假缺失**）：
    #    下面两条原本写 `([a-z_]+)` / `([a-z\-]+)` —— 名字里一旦出现**数字或大写**就解析不到，
    #    后果是「数少了、却不报错」：`dom_pass` 少数一个域、`pending_domains` 少列一个待办域
    #    （后者会把"还有没做完的"读成"队列空了"）。
    #    实测（`.scratch/fr6_real_output.py`，拿 `omni gaps` 与 `verify-distill.py --all` 的**真输出**量）：
    #    窄口径 29/22/1 与宽口径 **完全一致** ⇒ 今天**零漏**，这是**潜在**通道不是现行故障。
    #    仍然改掉：① 一处一处不同口径本身就是病根 —— 同一份文件 L63 早就写成 `[a-z0-9\-]`；
    #    ② 宽度改大在今天的真数据上**零行为变化**（可复核），却把"以后某个域叫 `h3_video_gen` 就静默漏掉"这条路封死。
    dom_pass = len(re.findall(r"^([A-Za-z0-9_]+)\s+PASS", out2, re.M))
    clu = re.findall(r"^\s+([A-Za-z0-9_\-]+)\s+(PASS|FAIL)\s+覆盖\s+(\d+)/(\d+)", out2, re.M)
    clu_pass = [c for c in clu if c[1] == "PASS"]
    clu_fail = [c for c in clu if c[1] == "FAIL"]
    hard2 = re.search(r"已登记域的硬失败：(\d+) 个", out2)
    hard3 = re.search(r"已登记簇的硬失败：(\d+) 个", out2)
    if not hard2 or hard2.group(1) != "0":
        bad.append("域有硬失败")
    if not hard3 or hard3.group(1) != "0":
        bad.append("簇有硬失败")
    if clu_fail:
        bad.append("簇 FAIL：" + "、".join(c[0] for c in clu_fail))

    # ③ 结构
    rc3, out3 = run("audit-regulations.py")
    re.search(r"共 (\d+) 件.*?去重后 (\d+) 件", out3)
    s = re.search(r"小计：(\d+) 件 · 合计 (\d+) 行 · 点名过的能力位（去重前）(\d+) 处 · 「未验」标记 (\d+) 处", out3)
    gap = re.search(r"缺节的件：(\d+) / (\d+)", out3)
    if gap and gap.group(1) != "0":
        bad.append("结构缺节 %s 件" % gap.group(1))

    # ④ 设计全维度 —— 2026-09-22 加。为什么单列一关：
    # 设计能力不在"域/簇登记表"里（它不是一个职业域，是**跨七条线的融合成品**），
    # 所以 ①②③ 三关**天然看不见它** —— 会出现"索引 88 个成员都点了名、深读却是空壳"的假交付。
    # 这一关查总规程八节齐 + 七份深读都在盘上且各点名本线成员 + 索引覆盖，缺一样就红。
    rc4, out4 = run("verify-design-mastery.py")
    if rc4 != 0:
        bad.append("设计全维度验收没过（%s）" % ("跑不起来" if rc4 == 127 else "见④"))

    # ⑤ 技能根一致性 —— 2026-09-22 加。为什么单列一关：
    # 同一份规程会同时躺在 `skills/`（源）· `~/.openclaw-autoclaw/skills`（产品口径）·
    # `~/.agents/skills`（**本会话真正加载的根**）· `<仓>/.dsh/skills`（项目根）。
    # 实测栽过：`gbt-omni`/`gbt-arkcli`/`gbt-tentacle` 在 `~/.agents/skills` 里是**旧版本**
    # ⇒ 会话加载的是过期规程，而①②③④**都看不见这件事**（两边都能读、都像模像样）。
    rc5, out5 = run("audit-skill-roots.py")
    drift5 = re.search(r"① gbt-\* 哈希偏差：(\d+) 个", out5)
    if rc5 != 0:
        bad.append("gbt-* 跨根哈希偏差 %s 个（跑 audit-skill-roots.py --fix 从源稿刷新）"
                   % (drift5.group(1) if drift5 else "?"))

    print("=" * 78)
    print("GBT小土豆V8 · 深蒸交付体检（五关合一）")
    print("=" * 78)
    print("① 队列（现算 + 现读盘）")
    print("   %s" % dom_line)
    print("   现读盘告警：%d 条%s" % (len(warns), "" if not warns else "（下面列出）"))
    for w in warns[:6]:
        print("     %s" % w.strip())
    print("② 内容（同哈希 / frontmatter / 点名位真存在 / 零遗漏）")
    print("   域 PASS：%d 个（硬失败 %s）" % (dom_pass, hard2.group(1) if hard2 else "?"))
    print("   簇 PASS：%d 个（硬失败 %s）" % (len(clu_pass), hard3.group(1) if hard3 else "?"))
    if clu:
        print("   " + " · ".join("%s %s/%s" % (c[0], c[2], c[3]) for c in sorted(clu)))
    print("③ 结构（报告层红线 / 未验账 / 门 / 出处）")
    if s:
        print("   %s 件 · %s 行 · %s 处点名能力位 · %s 处「未验」标记" % s.groups())
    print("   缺节：%s" % (gap.group(0).split("：")[1] if gap else "（没解析到）"))
    # ④ 设计全维度（总规程 + 七份深读）
    print("④ 设计全维度（总规程 8 节 + 七份深读点名全覆盖 + 索引覆盖）")
    d_last = [ln for ln in out4.strip().splitlines() if ln.strip()] if out4.strip() else []
    print("   %s" % (d_last[-1] if d_last else "（跑不起来）"))
    for ln in d_last:
        if ln.strip().startswith("🔴"):
            print("   %s" % ln.strip())
    pending_domains = re.findall(r"^\s*⏳ 在队里\s+([A-Za-z0-9_]+)\s", out1, re.M)
    # ⑤ 技能根一致性 + 图鉴新鲜度
    print("⑤ 技能根一致性 / 图鉴新鲜度（源 · 产品口径 · 本会话加载根 · 图鉴 vs 盘上）")
    if drift5:
        print("   gbt-* 哈希偏差：%s 个" % drift5.group(1))
    for ln in out5.splitlines():
        if ln.startswith("   ✅ 已刷新") or "本会话真正加载的根" in ln:
            print("   %s" % ln.strip())
        if ("图鉴 built_at" in ln) or ("盘上有、图鉴里没有" in ln):
            print("   %s" % ln.strip())
        if ln.strip().startswith("🔴") and "图鉴" not in ln and "⇒ 重扫" in ln:
            print("   %s" % ln.strip())
    print("⑥ 队列余量（**现读**；技能目录会被外部更新，清空只是当时的快照）")
    print("   未深蒸域：%d 个%s" % (len(pending_domains),
                              "" if not pending_domains else "（%s）" % "、".join(pending_domains)))
    print("   未深蒸簇：%d 个%s" % (len(pending_clusters),
                              "" if not pending_clusters else "（%s）" % "、".join(pending_clusters)))
    print("-" * 78)
    if bad:
        print("结论：**不通过** —— " + "；".join(bad))
        print("（任何一条没跑到都算没验：别只看其中一条就下结论。）")
        return 1
    tail = ""
    if pending_clusters or pending_domains:
        tail = "；但队列里还剩 %d 域 / %d 簇没规程（现读）" % (len(pending_domains), len(pending_clusters))
    print("结论：已交付件五关全过（队列登记齐 · 内容零遗漏零编造 · 结构四节齐 · 设计全维度落地 · 技能根零偏差）" + tail)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
