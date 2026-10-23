#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""在办目标 · **总验收**（一把跑完三条腿，汇总成一张表）

## 为什么要有它
每条腿各自都有验收器，但**没有一处能一把跑完** ⇒ "可复核"缺最后一环：
下一个人得自己知道该跑哪十几个文件、各自的判据在哪。本件把这件事固定下来。

三条腿（第 76 轮扩的，原来只有第一条）：
- **脑窗**（六项 + ⑥ 的四支）：真 Chrome 取证
- **姿势链**（照片→骨架）：隔离 venv 里的检测器 + 内置真值对关节
- **Figma**：真客户端四态（**离线腿**；在线腿要主人一个 token）

## 口径（三条，写死）
1. **本件不自己判红绿**：它只**转发**各验收器自己的 `verdict` 与判据计数。
   判据长在各自的证据上，这里只做汇总 —— 汇总层自己发明判据就会变成第二处真相。
2. **单项失败不掩盖其它项**：一项红也继续跑完，最后一起报（否则"第一个红就退出"会让人以为别的都过了）。
3. **未验项照实列**：只有主人能开的那几格，最后单独印出来，**不算通过也不算失败**。

## 一条要注意的资源冲突（第 76 轮实测）
本机的稀缺资源是**内存**（7.4GB 总量，常只剩 0.4–0.8GB）。本件会把真 Chrome 拉起来，
而 ComfyUI 出图也在这台机器上 ⇒ **两件事同时跑会把 Chrome 挤到起不来**，
那时的红**不是回归**、是内存不够。⇒ 跑本件时**别同时跑 ComfyUI**；真撞上了就先看内存再念读数。

用法：
  python tools/codex-scripts/verify-brain-objective.py            # 全跑（约 8–12 分钟）
  python tools/codex-scripts/verify-brain-objective.py --only ②③  # 只跑匹配的
  python tools/codex-scripts/verify-brain-objective.py --only 姿势,Figma
退出码：**只有"每一条都是 ✅"才 0**；🟡（只给读数、没全过）/ ⛔（器具不在，起不来）/ ❗（未过）一律 1。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".scratch" / "_objective_verify.json"
PY = sys.executable

# (标签, 命令, 说明, 分组, 器具清单[缺一件就"起不来，不是未过"]) —— 每条命令都用**仓根**做 cwd
STEPS = [
    # ── 尺子的尺子（第 76 轮加）：先验「本件那道闸」真的挡得住，再看对象 ─────────
    #    理由写在 _verify_runner_preflight.py 里：本仓已经栽过一次「判据看着对、跑出来是错数」。
    #    放第一位 ⇒ 尺子坏了**当场**就知道，不会拿一把坏尺子量完十几步再判。
    ("⓪ 总验收器自检（器具不在 ≠ 未过）", [PY, ".scratch/_verify_runner_preflight.py"], None,
     "自检", ()),
    # 主人要的邮箱双向绑定（收+发）：不验"绑上了没有"（要真凭据，只有主人能开），
    # 只验**这件仪器可不可信** —— 会不会编成功、会不会把密码写出去（见 §三十一）
    ("⓪b 邮箱绑定件自检（失败关闭 + 不落盘）", [PY, ".scratch/_verify_mail_bind.py"], None,
     "自检", ("tools/codex-scripts/mail-bind.py",)),
    ("① 取读数", [PY, ".scratch/_brain_shot.py", "r_obj.png", "15"], None, "脑窗", ()),
    ("① 排布（密度/取景）", [PY, ".scratch/_brain_readings.py", ".scratch/_r_obj.txt"],
     "取读数的脚本不吃 JSON，按关键行判", "脑窗", (".scratch/_brain_readings.py",)),
    ("② 电弧打在对应依赖边上", [PY, ".scratch/_verify_arc_edges.py"], None, "脑窗", ()),
    ("③ 快照失败关闭（三态）", [PY, ".scratch/_verify_snapshot_failclosed.py"], None, "脑窗", ()),
    ("④ 高清（上限/合成器/辉光/resize）", [PY, ".scratch/_verify_hd_hard.py"], None, "脑窗", ()),
    ("④b 高清（1× vs 2× 对照）", [PY, ".scratch/_verify_hd.py"], None, "脑窗", ()),
    ("视图固化（真重启 + 双向绑定）", [PY, ".scratch/_verify_view_persist.py"], None, "脑窗", ()),
    ("⑤ lobe-ui 可复核性", [PY, ".scratch/_verify_lobe_ui.py"], None, "脑窗", ()),
    ("⑥ 成品清点 + 宿主 5 条对账", [PY, ".scratch/_verify_intercom_acceptance.py"], None, "脑窗", ()),
    ("⑥ 收件箱渲染（两态）", [PY, ".scratch/_verify_inbox_render.py"], None, "脑窗", ()),
    ("⑥ 门留痕（账本信封）", [PY, ".scratch/_verify_voice_ledger.py", "3"], None, "脑窗", ()),
    ("⑥ 面板那一格（真 Chrome 两态）", [PY, ".scratch/_verify_ear_rail.py"], None, "脑窗", ()),
    ("⑥ 子进程杀得干净（真 node）", ["node", "holo_pet_w3/shell/intercom-kill-test.cjs"], None,
     "脑窗", ()),
    # ── 第 76 轮扩的两条腿（原来这份"总验收"只盖脑窗，另两条腿各自散着）─────────
    ("⑦ 姿势链（照片→骨架 · 七条判据）", [PY, ".scratch/_verify_pose_chain.py"], None,
     "姿势链", (".scratch/pose-venv/Scripts/python.exe",
             "tools/codex-scripts/openpose-extract.py",
             "tools/codex-scripts/openpose-skeleton.py",
             "render/comfy-pose/1790183271-lora-RAW_photo_full_body.png")),
    # 单张图的误差**证明不了**"换姿势跑通了" ⇒ 判别力那一条单列（见 §二十九）
    ("⑦b 多姿势判别力（对角必须全胜）", [PY, ".scratch/_verify_pose_multi.py"], None, "姿势链", ()),
    ("⑧ Figma 离线腿（四态八条）", [PY, ".scratch/_verify_figma.py"], None,
     "Figma", ("tools/codex-scripts/figma-fetch.py",)),
]

# 哪些步骤的输出**要落盘**（因为下一步要读它）—— 命令不带 shell，重定向只能在这里做
STEP_SAVE = {
    tuple([PY, ".scratch/_brain_shot.py", "r_obj.png", "15"]): ".scratch/_r_obj.txt",
}

# 🟡 只有主人能开的那几格 —— **不算通过也不算失败**，单独印出来
OWNER_GATED = [
    "⑥ **真出声**：`python -m gbt_allinone auth grant --scope audio_output --ttl 600`（一次性；一次授权=一次出声）",
    "⑥ **真听到**：插一个物理麦克风 / 3.5mm 耳麦（本机录音端点在场的 0 个；内置麦也没有）",
    "① 径向分布要不要更贴「均匀填球」（现读偏中心是 L997「向心力 ∝ q」的**刻意设计**）",
    "④ 真高 DPI 屏上的观感与帧率（本机 1920×1080 / dpr=1，只能模拟）",
    "⑥ 真壳里的会话表（`listening` 与会话归零的最后一环，要 Electron 起来）",
    "⑦ 姿势链：**换人**（真人照片）未验 —— 本轮的检测器只吃过一张真人照 + 一张生成图",
    "⑦ 姿势链：`tpose` 预设未验（`walk`/`sit` 见 §二十九）",
    "⑧ Figma **在线腿**：要主人一个 Personal Access Token（`setx FIGMA_TOKEN`，**不要贴给 AI**）",
    "📮 邮箱双向绑定：**凭据不被 Zoho 接受**（IMAP×4 + SMTP×3 全拒）⇒ 要主人在 Zoho 后台"
    "**开 IMAP 访问 + 生成应用专用密码**，再本机 `setx GBT_IMAP_PASS`（值不贴给 AI）",
]

# 命令里看不出、但缺了就会"起不来"的器具（venv / 数据件 / 被调工具）
# —— 主脚本自己从命令里认（见 subject_of），这里只补**命令里没写**的那些
EXTRA_REQUIRES = {
    "① 排布（密度/取景）": (".scratch/_r_obj.txt",),
}


def subject_of(cmd):
    """从命令里认出"这条步骤真正要跑的那个脚本" ⇒ 它不在就该报**起不来**，不是**未过**。

    🔴 第 76 轮补的一道闸：原来 `python .scratch/缺了.py` 的失败形态是
    `exit 2` + 空 stdout ⇒ 汇总层只好念 `(无 verdict，exit=2)` 判红 ⇒
    **把"器具不在"念成了"对象未过"**。这两件事的处置完全不同（一个去补器具，一个去修对象）。
    """
    for a in cmd[1:]:
        if a.endswith((".py", ".cjs", ".ps1")):
            return a
    return None


def last_json(txt):
    """取输出里最后一段完整 JSON（各验收器都把自己的报告打成 JSON）。"""
    i = txt.find("{")
    while i >= 0:
        for j in range(len(txt), i, -1):
            try:
                return json.loads(txt[i:j])
            except Exception:                                              # noqa: BLE001
                continue
        i = txt.find("{", i + 1)
    return None


def preflight(label, cmd, reqs):
    """跑之前先看器具在不在。缺了 ⇒ 报「起不来（器具不在）」，**不报「未过」**。

    两件事的处置不一样：器具不在是"去补器具"，未过是"去修对象"。
    把前者念成后者，下一个人就会去改一个没坏的东西。
    """
    miss = []
    for r in tuple(reqs) + EXTRA_REQUIRES.get(label, ()):
        if not (ROOT / r).exists():
            miss.append(r)
    # 🔴 第 76 轮自检抓出来的洞：`subject_of()` **写了没接上** ⇒
    #    "主脚本不在"这一条根本没被拦住（靠崩溃兜底才没念错）。
    #    自检判据 B 就是为这种"函数写对了、调用处没接上"设的 —— 它当场报了 false。
    sub = subject_of(cmd)
    if sub and not (ROOT / sub).exists():
        miss.append(sub)
    # 解释器：命令第一个字是绝对路径且不存在（venv 被删过就会这样）
    if Path(cmd[0]).is_absolute() and not Path(cmd[0]).exists():
        miss.append(cmd[0])
    return list(dict.fromkeys(miss))          # 去重（主脚本可能同时也列在 reqs 里）


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="只跑标签里含这些字的（逗号分隔）")
    a = ap.parse_args()
    pick = [s for s in a.only.split(",") if s.strip()]

    rows, started = [], time.time()
    for label, cmd, note, group, reqs in STEPS:
        if pick and not any(p in label for p in pick):
            continue
        t0 = time.time()
        miss = preflight(label, cmd, reqs)
        if miss:
            rows.append({"项": label, "组": group, "类": "起不来",
                         "结论": "器具不在：" + "、".join(miss), "耗时s": round(time.time() - t0, 1),
                         "ok": False})
            continue
        try:
            cp = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=1800)
            out, code = cp.stdout or "", cp.returncode
            err = (cp.stderr or "").strip()
            # 🔴 第 67 轮修（**跑测器自己的 bug**）：第一步只是**捕获**了 `_brain_shot.py` 的
            #    输出，**没落盘** ⇒ 第二步 `_brain_readings.py .scratch/_r_obj.txt` 找不到文件
            #    ⇒ 0.1 秒就红。命令不带 shell，所以重定向要在这里手工做。
            save = STEP_SAVE.get(tuple(cmd))
            if save:
                (ROOT / save).parent.mkdir(parents=True, exist_ok=True)
                (ROOT / save).write_text(out, encoding="utf-8")
        except subprocess.TimeoutExpired:
            rows.append({"项": label, "组": group, "类": "未过",
                         "结论": "超时 1800s（**没等到判决**，不是「过」）",
                         "耗时s": round(time.time() - t0, 1), "ok": False})
            continue
        except Exception as e:                                             # noqa: BLE001
            rows.append({"项": label, "组": group, "类": "起不来",
                         "结论": "起不来：%s" % str(e)[:90], "耗时s": round(time.time() - t0, 1),
                         "ok": False})
            continue
        j = last_json(out)
        verdict = None
        if isinstance(j, dict):
            verdict = j.get("verdict") or j.get("_判据")
        if verdict is None:                       # 取读数那支没有 verdict，按关键行判
            keep = [ln.strip() for ln in out.splitlines()
                    if any(k in ln for k in ("密度判定", "取景判定", "重叠率", "空壳判定", "聚簇判定"))]
            # 脚本自己崩了（有 traceback / 空 stdout）⇒ 也归"起不来"，别把崩溃念成"对象未过"
            crash = code != 0 and not out.strip()
            verdict = (" · ".join(keep[:4]) or
                       ("脚本没吐出报告%s：%s" % (
                           "（%s）" % (subject_of(cmd) or "?") if subject_of(cmd) else "",
                           err.splitlines()[-1][:90] if err else "空输出")))
            if crash:
                rows.append({"项": label, "组": group, "类": "起不来", "结论": str(verdict)[:200],
                             "耗时s": round(time.time() - t0, 1), "exit": code, "ok": False})
                continue
        if isinstance(verdict, list):
            verdict = " / ".join(str(x) for x in verdict)
        v = str(verdict)
        # 🟡 第三态（第 76 轮加）：验收器自己说"跑通了但没全过、只有读数"（verdict 以 🟡 开头）。
        # 既不该念成 ✅，也不该念成 ❗ —— 本仓的三态纪律（✅已验 / 🟡已落盘未验 / ⛔等主人）同一条。
        #
        # 🔴 第 76 轮同轮修的一个**判据错**：原来还看 `"未过" not in v`，
        #    结果 `⓪ 总验收器自检` 的**成功**文本里写着「…念『起不来』而不是『未过』」⇒
        #    它自己把自己判成了红（✅ 六条全过 却打 ❗）。判据只看**印章字符**（各验收器的约定：
        #    失败一律以 ❗ 开头），不看自然语言里出现过什么词 —— 拿文本词当判据，迟早被自己的说明打脸。
        partial = v.startswith("🟡")
        ok = code == 0 and ("❗" not in v)
        rows.append({"项": label, "组": group, "类": "部分" if (ok and partial) else ("过" if ok else "未过"),
                     "结论": v[:200], "耗时s": round(time.time() - t0, 1),
                     "exit": code, "ok": ok})

    bad = [r["项"] for r in rows if r.get("类") == "未过"]
    dead = [r["项"] for r in rows if r.get("类") == "起不来"]
    part = [r["项"] for r in rows if r.get("类") == "部分"]
    if not rows:
        total = "⛔ 一条都没跑（--only 没匹上？）"
    elif not bad and not dead and not part:
        total = "✅ 全部通过"
    else:
        total = ""
        if bad:
            total += "❗有未过项：" + "、".join(bad)
        if dead:
            total += ("　" if total else "") + "⛔起不来（器具不在，**不是**未过）：" + "、".join(dead)
        if part:
            total += ("　" if total else "") + "🟡只给读数、没全过：" + "、".join(part)
    report = {"总验收": rows, "主人闸门（不算通过也不算失败）": OWNER_GATED,
              "全跑耗时s": round(time.time() - started, 1), "总判": total}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), "utf8")

    print("=" * 92)
    g = None
    for r in rows:
        if r.get("组") != g:
            g = r.get("组")
            print("── %s " % g + "─" * (88 - len(str(g))))
        print("%s %-34s %6.1fs  %s" % (
            {"过": "✅", "部分": "🟡", "起不来": "⛔"}.get(r.get("类"), "❗"),
            r["项"], r.get("耗时s", 0), r["结论"]))
    print("=" * 92)
    print("总判：%s（全跑 %ss）" % (report["总判"], report["全跑耗时s"]))
    print("\n🟡 只有主人能开的几格（**不算通过也不算失败**）：")
    for x in OWNER_GATED:
        print("   · " + x)
    print("\n报告落盘：%s" % OUT)
    # 退出码只认"每一条都是 ✅"：🟡（只给读数）与 ⛔（起不来）**都不算全过**
    return 0 if rows and all(r.get("类") == "过" for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
