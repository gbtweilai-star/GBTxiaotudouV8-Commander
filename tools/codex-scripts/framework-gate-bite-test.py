#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""框架自改门 · **咬合力反证**（negative control + 还原复原）。

为什么要这一步（P29「量具自己没被真跑过」的直系后代）：
  2026-10-22 我按门自带的 force 出口**重立了基线**，随后门报 green（changed=0）。
  但"重立基线后的 green"必须证明它**不是因为门被废掉了**：门要还能红。
  ⇒ 本件做两连（默认）：
    ① 负控：往一个受监视的源件尾部加一行注释（不改行为）⇒ verify **必须红**（未认领≥1）
    ② 复原：把字节原样写回 ⇒ verify **必须绿**（该件回到基线 sha）
  任何一步不符预期 ⇒ rc=1，并如实打出来。

🔴 2026-10-22 记（为什么正控默认关）：我本来还想"为这次临时改动开一张护照再关"当正控，
   实测教训：复原之后再 verify，那张护照会因**文件在护照关闭后又变了**判成 stale_passport
   ⇒ 探针自己制造一条红灯（哨兵自己污染现场）。而「护照还能认账」本轮已被两次**真实**护照
   当场证明（bite-test-tool / f22-probe-rewrite：开→关→verify 绿）。所以默认跳过；
   要复现就显式 `--with-passport`，跑完记得清那张 stale。

用法：py -3.14 tools/codex-scripts/framework-gate-bite-test.py [--target 相对路径] [--with-passport]
"""
import argparse
import json
import os
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORE = os.path.join(ROOT, "gbt_allinone", "store", "framework_changes")


def gate(*args):
    return subprocess.run([sys.executable, "-X", "utf8", "-m", "gbt_allinone.tools.framework_gate",
                           "--root", ".", "--store", STORE] + list(args),
                          cwd=ROOT, capture_output=True)


def verify():
    r = gate("verify")
    out = r.stdout.decode("utf-8", "replace")
    i = out.find("{")
    if i < 0:
        raise SystemExit("verify 没回 JSON：%s" % out[:300])
    return json.loads(out[i:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="tools/codex-scripts/close-fault.py")
    ap.add_argument("--with-passport", action="store_true",
                    help="额外做正控（会留下一张 stale 护照，跑完自行清理）")
    a = ap.parse_args()
    path = os.path.join(ROOT, a.target.replace("/", os.sep))
    if not os.path.isfile(path):
        print("目标不在：%s" % path)
        return 2

    before = verify()
    print("起点：verdict=%s changed=%s 未认领=%s baseline_at=%s"
          % (before.get("verdict"), before.get("changed_files"), before.get("未认领"), before.get("baseline_at")))
    if before.get("verdict") != "green":
        print("🔴 起点不是绿的 —— 先把门跑绿再来做咬合反证")
        return 1

    orig = open(path, "rb").read()
    results = []
    try:
        with open(path, "ab") as fh:
            fh.write(b"# bite-test probe (framework gate negative control)\n")
        v1 = verify()
        # 🔴 2026-10-22 自纠（P1 判据错尺，第一次真跑就抓到）：我原来只认「未认领≥1」算咬住。
        #    实测：目标件 close-fault.py **早有一张护照**，再改它 ⇒ 门走的是 **stale_passport**
        #    那条路（判红、但 未认领=0）⇒ 门确实咬了，是我的断言太窄，把"咬住"误判成"没咬"。
        #    现口径：**红在哪条路都算咬住**（未认领 / 认领但已过期 / 或 findings 里点到这个件），
        #    并把门自己那条 finding 原话打出来。
        hit = [x for x in (v1.get("findings") or []) if str(x.get("file")) == a.target]
        ok1 = (v1.get("verdict") == "red"
               and (int(v1.get("未认领") or 0) + int(v1.get("认领但已过期") or 0) >= 1 or bool(hit)))
        print("① 负控（改了不记账）：verdict=%s 未认领=%s 过期=%s ⇒ %s"
              % (v1.get("verdict"), v1.get("未认领"), v1.get("认领但已过期"), "✅ 门咬了" if ok1 else "🔴 门没咬"))
        for x in hit[:3]:
            print("     门原话：%s · %s" % (x.get("reason_code"), str(x.get("detail") or "")[:110]))
        results.append(("负控：改成未记账必须红", ok1))

        if a.with_passport:
            r = gate("open", "--reason", "咬合反证：为一次临时注释改动开护照（探针自身，跑完即还原）",
                     "--label", "bite-test")
            out = r.stdout.decode("utf-8", "replace")
            i = out.find("{")
            pid = json.loads(out[i:]).get("id") if i >= 0 else None
            if not pid:
                print("🔴 开护照失败：%s" % out[:200])
                results.append(("正控：护照能认领", False))
            else:
                rc = gate("close", "--id", str(pid),
                          "--evidence", "framework-gate-bite-test：临时注释一行 => verify 由 red 转 green",
                          "--no-review-reason", "咬合反证探针，非真实交付变更",
                          "--no-stamp-reason", "咬合反证探针，无需印章",
                          "--rollback", "把该件字节原样写回（本件自己在第②步做）",
                          "--files", a.target)
                ok_open = '"ok": true' in rc.stdout.decode("utf-8", "replace")
                v2 = verify()
                ok2 = ok_open and v2.get("verdict") == "green"
                print("② 正控（护照认领后）：护照=%s verdict=%s ⇒ %s"
                      % ("关上了" if ok_open else "关不上", v2.get("verdict"), "✅ 门认账" if ok2 else "🔴 门不认"))
                results.append(("正控：有护照必须绿", ok2))
        else:
            print("② 正控：跳过（默认；护照认账已由真实护照当场验证）")
    finally:
        with open(path, "wb") as fh:
            fh.write(orig)
        v3 = verify()
        ok3 = v3.get("verdict") == "green"
        print("③ 复原（字节写回）：verdict=%s changed=%s ⇒ %s"
              % (v3.get("verdict"), v3.get("changed_files"), "✅ 回到基线" if ok3 else "🔴 没回到基线"))
        results.append(("复原：写回后必须绿", ok3))

    print("\n=== 结论 ===")
    for name, ok in results:
        print("  %s %s" % ("✅" if ok else "🔴", name))
    bad = [n for n, ok in results if not ok]
    print("咬合力反证：%s" % ("通过（门还能红、还能回到基线）" if not bad else "🔴 未通过：%s" % "、".join(bad)))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
