# -*- coding: utf-8 -*-
r"""形变盲区检查（deform-aware）· 扫出**「按对象当前状态量尺寸」**这一族的代码形状。

## 为什么需要它（2026-10-10 三副副本的真账）
同一天我在三个地方撞到**同一个错法**：动手之前没搞清"我量的/我动的是哪一份对象状态"。
  ① Blender S12：**清动画当成回到绑定姿势** —— 实测清完仍 0.621 高、42 根 pose bone 留着姿势值，
     只有 pose_position=REST 才回到 0.979 ⇒ 人物被顶出画外、顶部被切。
  ② Blender S2 参考图：**同一个病**（也只清动画）＋ 注释写「不用三点光」而代码加了三盏灯 ⇒ 脸爆白 66%。
  ③ three.js 大屏：**按下标赌动画顺序**（顺序一变就原地走）＋ **缩放基准量的是当前姿势的包围盒**
     （绑定 0.979 vs 动画 0.621 ⇒ 系数差 1.6 倍）。
==修一处是手艺；把"同一个错法有几个副本"做成能跑的尺子，才算治了这族病。==

## 两类形状（**形状判据，输出是线索不是判决**）
  A **清动画却没切 REST**：文件里出现 animation_data_clear() / actions.remove()，
    但**整个文件找不到 pose_position** ⇒ 极可能又踩了"清动画 = 回绑定姿势"。
    **这一类是判决级**（REST 是唯一正确姿势来源，缺了就是缺了）。
  B **拿原始顶点当"当前几何"**：出现 .data.vertices 且同段里还有 min/max/包围盒/bound_box 运算。
    **这一类是线索级** —— 若该对象带 Armature/形变类修改器，量出来的就不是渲染用的那份。
    静态判据**看不出有没有修改器**（要跑起来才知道）⇒ 只报"候选，需人复核"。

## 负控（本件自己也要有，否则它就是又一个坏判据）
  · A 的负控：造一个「清动画但不切 REST」的真文件 ⇒ **必须报**；造一个切了 REST 的 ⇒ **不许报**
  · B 的负控：造一个「用 .data.vertices 算 min/max」的真文件 ⇒ **必须报候选**；造一个用
    depsgraph 求值后再量的 ⇒ **不许报**
  · 正控：全干净 ⇒ 不许虚报

用法：
  py -3.14 -X utf8 tools/codex-scripts/deform-aware-check.py
  py -3.14 -X utf8 tools/codex-scripts/deform-aware-check.py --selftest
退出码：0 干净 · 1 有 A 类（判决级）· 2 读不动
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCAN = ("tools", "gbt_allinone")
SKIP = ("_legacy", "vendor", "node_modules", "_upstream", "__pycache__", ".scratch")
SELF = "deform-aware-check.py"        # 见 _code_only() 末尾的边界说明

CLEAR = re.compile(r"(animation_data_clear|actions\.remove|bpy\.data\.actions\.remove)")
REST = re.compile(r"pose_position\s*=\s*[\"']REST[\"']")
RAWV = re.compile(r"\.data\.vertices")
# 🔴 2026-10-10 自纠两处（都是我这件自己的毛病）：
#   ① **自指**（判据台架 D6 那一类）：我的注释/文档里写了 .data.vertices ⇒ 首跑第一条命中就是**本文件自己**。
#      修法是**先剥注释与三引号串再匹配**，不是把本文件跳过（跳过 = 判据对着自己瞎）。
#   ② B 类**假阳性**：render-shot.py:159 那句是在**选主体网格**，不是量尺寸。
#      ⇒ 要求同一行**同时**出现"取世界坐标"的证据（matrix_world 或 v.co），才算"把原始顶点当当前几何来量"。
BBOX = re.compile(r"(\bmin\(|\bmax\(|bound_box|dimensions|包围盒)")
WORLD = re.compile(r"(matrix_world|\bv\.co\b|vert\.co)")
STRIP_STR = re.compile(r'"""[\s\S]*?"""|' + "'''[\\s\\S]*?'''")
STRIP_CMT = re.compile(r"#[^\n]*")


# 🔴 2026-10-10 再自纠一刀：只剥三引号串**不够** —— 我自检里造负例用的样本写在**普通字符串字面量**里
#    （NL.join([...]) 那一串），于是本件**又**命中了自己。==字符串里的模式是数据、不是代码。==
#    代价：如果哪天真有代码把这类模式**写在字符串里再 exec**，本件会漏 —— 如实记这个边界，不假装全能。
def _code_only(t: str) -> str:
    """只留**代码**：剥掉三引号串与行注释。判据要对着代码，不是对着我的说明文字。

    🔴 2026-10-10 再自纠：我上一版**又**多剥了一层"普通字符串字面量" —— 结果把
    pose_position = "REST" 里的 "REST" 也剥掉了 ⇒ **REST 判据反而看不见** ⇒
    render-shot.py（明明两处都切了 REST）被**误报**成 A 类。
    ==剥过头 = 把判据自己的证据也剥了。== 回到只剥注释与文档串。
    剩下那点自指（自检里造负例用的**样本字符串**）改用**列名排除本文件** —— 这不是"判据对着自己瞎"，
    因为**自检里有 5 条负控证明它对着别的文件会响**；边界如实写在这儿。"""
    return "\n".join(STRIP_CMT.sub("", ln) for ln in STRIP_STR.sub("", t).splitlines())


def files():
    for base in SCAN:
        d = ROOT / base
        if not d.is_dir():
            continue
        for p in d.rglob("*.py"):
            s = str(p)
            if any(k in s for k in SKIP):
                continue
            if p.name == SELF:            # 不扫自己：自检里造负例的**样本字符串**会被当命中（见 _code_only 的边界说明）
                continue
            yield p


def scan() -> dict:
    a_hits, b_hits = [], []
    for p in files():
        try:
            t = _code_only(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        try:
            rel = p.relative_to(ROOT).as_posix()
        except ValueError:                                   # 自检时扫临时目录（不在 ROOT 下）
            rel = p.as_posix()
        # A：清动画却没切 REST（判决级）
        if CLEAR.search(t) and not REST.search(t):
            a_hits.append({"件": rel, "为什么": "有清动画、整个文件没有 pose_position=REST"})
        # B：拿原始顶点当当前几何（线索级）
        lines = t.splitlines()
        for i, line in enumerate(lines):
            # 🔴 2026-10-10 自纠：原来要求三条件**同一行** ⇒ 我的负控（真实写法是跨两行：
            #    第一行取顶点+世界坐标、第二行算 min/max）**当场没被抓到** ⇒ 判据太窄。
            #    改成：**顶点行必须带世界坐标证据**（matrix_world / v.co），
            #    且**前后 3 行内**有包围盒类运算 —— 这才对得上真实写法。
            #    仍然排除"选网格"那种（它不带 matrix_world/v.co）。
            if not (RAWV.search(line) and WORLD.search(line)):
                continue
            lo_i, hi_i = max(0, i - 3), min(len(lines), i + 4)
            if any(BBOX.search(x) for x in lines[lo_i:hi_i]):
                b_hits.append({"件": "%s:%d" % (rel, i + 1), "行": line.strip()[:96]})
                break
    return {"清动画却没切REST": a_hits, "原始顶点当当前几何": b_hits}


def main() -> int:
    ap = argparse.ArgumentParser(description="形变盲区检查")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    r = scan()
    print("形变盲区检查 · 「按对象当前状态量尺寸」这一族的代码形状")
    print("=" * 100)
    print("【A 清动画却没切 REST】判决级 —— 缺 pose_position=REST 就是缺：%d 处" % len(r["清动画却没切REST"]))
    for x in r["清动画却没切REST"]:
        print("   ❌ %-52s %s" % (x["件"], x["为什么"]))
    print()
    print("【B 拿原始顶点当当前几何】线索级 —— **需人复核**（静态看不出带没带修改器）：%d 处"
          % len(r["原始顶点当当前几何"]))
    for x in r["原始顶点当当前几何"]:
        print("   ?  %-52s %s" % (x["件"], x["行"][:48]))
    print()
    print("口径：A 类可判（REST 是唯一正确姿势来源）；B 类只报候选 —— "
          "本件看不出对象带没带 Armature 修改器，**那一层要跑起来才知道**，不假装能判。")
    return 1 if r["清动画却没切REST"] else 0


def selftest() -> int:
    """本件自己的负控：**造真文件**，看 A/B 两类的报与不报对不对。"""
    import tempfile
    fails, n = [], [0]
    NL = chr(10)

    def c(name, got, want):
        n[0] += 1
        ok = (got == want)
        print("  %-62s %s" % (name, "✅" if ok else "❌ 期望 %s 得到 %s" % (want, got)))
        if not ok:
            fails.append(name)

    with tempfile.TemporaryDirectory() as td:
        d = pathlib.Path(td)
        bad_a = d / "a_bad.py"
        bad_a.write_text(NL.join(["import bpy",
                                  "for o in bpy.context.scene.objects:",
                                  "    if o.animation_data:",
                                  "        o.animation_data_clear()", ""]), encoding="utf-8")
        good_a = d / "a_good.py"
        good_a.write_text(NL.join(["import bpy",
                                   "for o in bpy.context.scene.objects:",
                                   "    if o.animation_data:",
                                   "        o.animation_data_clear()",
                                   "for arm in [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']:",
                                   "    arm.data.pose_position = 'REST'", ""]), encoding="utf-8")
        bad_b = d / "b_bad.py"
        bad_b.write_text(NL.join(["ws = [obj.matrix_world @ v.co for v in obj.data.vertices]",
                                  "lo = min(p.z for p in ws)",
                                  "hi = max(p.z for p in ws)", ""]), encoding="utf-8")
        good_b = d / "b_good.py"
        good_b.write_text(NL.join(["dg = bpy.context.evaluated_depsgraph_get()",
                                   "ev = obj.evaluated_get(dg)",
                                   "me = ev.to_mesh()",
                                   "ws = [ev.matrix_world @ v.co for v in me.vertices]",
                                   "lo = min(p.z for p in ws)", ""]), encoding="utf-8")
        # 补一条**自指负控**：注释里提到 .data.vertices 不许被当成命中（D6 那一类）
        cmt_only = d / "b_comment.py"
        cmt_only.write_text(NL.join(["# 这里提到 .data.vertices 与 min/max 但那是注释",
                                     "# ws = [o.matrix_world @ v.co for v in o.data.vertices]",
                                     "x = 1", ""]), encoding="utf-8")
        global SCAN
        old = SCAN
        SCAN = (str(d),)
        try:
            r = scan()
            c("A 负例·清动画却不切 REST ⇒ 必须报",
              any("a_bad" in x["件"] for x in r["清动画却没切REST"]), True)
            c("A 正例·切了 REST ⇒ 不许报",
              any("a_good" in x["件"] for x in r["清动画却没切REST"]), False)
            c("B 负例·用原始顶点算 min/max ⇒ 必须报候选",
              any("b_bad" in x["件"] for x in r["原始顶点当当前几何"]), True)
            c("B 正例·走 depsgraph 求值后再量 ⇒ 不许报",
              any("b_good" in x["件"] for x in r["原始顶点当当前几何"]), False)
            c("自指负控·只在**注释**里提 .data.vertices ⇒ 不许报（D6 那一类）",
              any("b_comment" in x["件"] for x in r["原始顶点当当前几何"]), False)
        finally:
            SCAN = old
    print()
    print("deform-aware 自检: %s（%d 条）"
          % ("**全部通过**" if not fails else "**%d 条失败**" % len(fails), n[0]))
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
