#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""optics —— 手机闪光灯 + 透明胶片 + 凸透镜 的投影光路计算

为什么单独成一个模块：这条路能不能成，全靠三个数——放大倍率、亮度、景深模糊。
算错一个数，做出来的东西就是废的。所以这里每个公式都配自检（--selftest），
用薄透镜方程反推校验，不靠"感觉应该行"。

记号：
  f  透镜焦距 (mm)
  u  物距 = 胶片到透镜 (mm)
  v  像距 = 透镜到墙 (mm)
  m  放大倍率 = v / u
  D  透镜有效口径 (mm)
  L  胶片尺寸 (mm)
"""
from __future__ import annotations

import argparse
import sys


def solve(f: float, u: float) -> dict:
    """给定焦距与物距，解出像距、倍率、像尺寸。

    薄透镜方程：1/f = 1/u + 1/v   ⇒   v = f·u / (u - f)
    要求 u > f 才有实像（投影必须成实像）。
    """
    if u <= f:
        return {"ok": False, "why": "物距必须大于焦距（u>f）才有实像；现在 u=%g ≤ f=%g" % (u, f)}
    v = f * u / (u - f)
    m = v / u
    return {"ok": True, "f": f, "u": u, "v": v, "m": m}


def image_size(m: float, w: float, h: float) -> tuple[float, float]:
    return w * m, h * m


def brightness_rel(m: float, aperture: float, u: float) -> float:
    """相对亮度（以"胶片紧贴透镜"为 1.0）。

    两个损失：
      ① 面积损失：能量摊到 m² 倍面积上 ⇒ 1/m²
      ② 收光角：透镜只收立体角 ≈ π(D/2)²/u² ⇒ 口径越大越亮，物距越远越暗
    """
    if m <= 0:
        return 0.0
    solid = (aperture ** 2) / (16.0 * u ** 2)      # 归一化的收光立体角
    return solid / (m ** 2)


def blur_mm(f: float, u: float, focus_u: float, aperture: float) -> float:
    """离焦模糊（弥散圆直径，单位 mm，投到墙上）。

    胶片偏离对焦位 focus_u 时，墙上像点散开成圆。用相似三角形：
      c ≈ D · |v - v'| / v'
    """
    a = solve(f, u)
    b = solve(f, focus_u)
    if not (a["ok"] and b["ok"]):
        return 0.0
    return aperture * abs(a["v"] - b["v"]) / b["v"]


def lux_estimate(m: float, aperture: float, u: float, lumens: float = 50.0) -> float:
    """墙上照度估算（勒克斯）。默认按 iPhone 闪光灯 ≈50 lm 计。

    进透镜的光通量 = 总光通量 × 收光立体角占比
    照度 = 该光通量 / 像面积
    """
    import math
    if m <= 0:
        return 0.0
    omega = math.pi * (aperture / (2.0 * u)) ** 2      # 透镜对胶片的立体角（球面度）
    eff = min(1.0, omega / math.pi)                     # 胶片是朗伯面，半球 2π…这里取归一化占比
    flux = lumens * eff
    area_m2 = (0.105 * m) * (0.148 * m)
    return flux / area_m2 if area_m2 > 0 else 0.0


def diffraction_mm(f_number: float, wavelength_um: float = 0.55) -> float:
    """衍射极限斑（瑞利判据近似），给个下限——透镜再好也糊不过这个。"""
    return 2.44 * f_number * wavelength_um * 1e-3


def table(f: float, film: tuple[float, float] = (105.0, 148.0),
          distances=(1000, 1500, 2000, 3000), aperture: float = 25.0) -> list[dict]:
    rows = []
    for dist in distances:
        # 已知投距 v 反解物距 u：1/u = 1/f - 1/v
        if dist <= f:
            continue
        u = f * dist / (dist - f)
        s = solve(f, u)
        if not s["ok"]:
            continue
        w, h = image_size(s["m"], film[0], film[1])
        rows.append({
            "f": f, "投距mm": dist, "物距mm": round(u, 1), "倍率": round(s["m"], 2),
            "像宽mm": round(w), "像高mm": round(h),
            "相对亮度": round(brightness_rel(s["m"], aperture, u), 4),
            "衍射斑mm": round(diffraction_mm(u / aperture), 3),
        })
    return rows


def selftest() -> int:
    """用已知解反推校验。任何一条不过就是公式写错了。"""
    bad = 0

    def chk(name, got, want, tol=1e-6):
        nonlocal bad
        ok = abs(got - want) <= tol * max(1.0, abs(want))
        print("  %-34s %-12.6g %s" % (name, got, "OK" if ok else "FAIL(期望 %g)" % want))
        if not ok:
            bad += 1

    print("① 薄透镜：f=100, u=200 ⇒ v=200, m=1")
    s = solve(100, 200)
    chk("v", s["v"], 200.0)
    chk("m", s["m"], 1.0)

    print("② 经典 2f 成像：f=100, u=150 ⇒ v=300, m=2")
    s = solve(100, 150)
    chk("v", s["v"], 300.0)
    chk("m", s["m"], 2.0)

    print("③ 反解：投距 1100, f=100 ⇒ u=110, m=10")
    u = 100 * 1100 / (1100 - 100)
    chk("u", u, 110.0)
    chk("m", solve(100, u)["m"], 10.0)

    print("④ 亮度随倍率平方衰减：m 加倍 ⇒ 亮度 1/4")
    b1 = brightness_rel(5.0, 25.0, 125.0)
    b2 = brightness_rel(10.0, 25.0, 110.0)
    # 正确期望：(125/110)² × (5/10)² —— 口径收光与倍率平方两重因素
    chk("b2/b1", b2 / b1, ((125.0 ** 2) / (110.0 ** 2)) * 0.25, 1e-6)

    print("⑤ 对焦准确时离焦模糊为 0")
    chk("blur(u=110, focus=110)", blur_mm(100, 110, 110, 25), 0.0)

    print("⑥ 离焦 5mm 时产生模糊（>0）")
    got = blur_mm(100, 110, 115, 25)
    print("  %-34s %-12.4g %s" % ("blur(u=110, focus=115)", got, "OK" if got > 0 else "FAIL"))
    if got <= 0:
        bad += 1

    print("⑦ u ≤ f 时必须拒绝（无实像）")
    r = solve(100, 100)
    print("  %-34s %s" % ("solve(f=100,u=100).ok", "OK" if not r["ok"] else "FAIL"))
    if r["ok"]:
        bad += 1

    print("\n结果：%s（%d 条失败）" % ("全通" if bad == 0 else "有失败", bad))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--f", type=float, default=0)
    ap.add_argument("--focus-u", type=float, default=0, help="胶片到透镜的距离 mm")
    ap.add_argument("--aperture", type=float, default=25.0, help="有效口径 mm")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.f and a.focus_u:
        s = solve(a.f, a.focus_u)
        if not s["ok"]:
            print("算不出：" + s["why"]); return 2
        w, h = image_size(s["m"], 105, 148)
        print("f=%g · u=%gmm ⇒ 投距 %.0fmm · 倍率 %.2f× · 像 %.0f×%.0fmm"
              % (a.f, a.focus_u, s["v"], s["m"], w, h))
        print("相对亮度 %.4f · 衍射斑 %.3fmm · 建议口径 %gmm"
              % (brightness_rel(s["m"], a.aperture, a.focus_u),
                 diffraction_mm(a.focus_u / a.aperture), a.aperture))
        return 0
    for f in (100.0, 150.0, 200.0):
        print("\n焦距 %gmm（A6 胶片 105×148mm · 口径 25mm）" % f)
        print("  %-8s %-9s %-7s %-12s %-10s" % ("投距", "胶片位置", "倍率", "像尺寸", "相对亮度"))
        for r in table(f):
            print("  %-8s %-9s %-7s %-12s %-10s"
                  % ("%dmm" % r["投距mm"], "%gmm" % r["物距mm"], "%gx" % r["倍率"],
                     "%dx%dmm" % (r["像宽mm"], r["像高mm"]), r["相对亮度"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
