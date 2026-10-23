# -*- coding: utf-8 -*-
"""S2 门 · T-pose 姿态规范 —— **严格对齐技能源码口径**（不是我自己发明的判据）

源码口径（`skills/digihuman-pipeline/scripts/run-pipeline.ps1:64,73` + `SKILL.md:33`）：
    五条判据 = 水平双臂 / 直立双腿 / 正面全身 / **无遮挡物** / 白底
    ⚠ **必做人工复核**：打开规范化图看，五条全过才继续
    （SKILL.md:34 另有一条机器代理：`臂展≈身高` —— 属下游阶段）

所以本门的正确语义是：
  · 机器只给**代理读数**（剪影/白底/直立），**仅作提示，不能单独判过**；
  · **必须存在人工确认记录** `.digihuman/S2-human-ok.json`（人看过图、勾了五条）才算过。

    python tools/digihuman/tpose-check.py                      # 门：无人工确认 ⇒ 判「待人工确认」
    python tools/digihuman/tpose-check.py --confirm "<复核人>"   # 人看过图后落确认记录
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import struct
import sys
import time

# 🔴 2026-09-26 补：Windows 管道/重定向下 stdout 回落 GBK，emoji 一打印就崩；与 self_model.py 同一款补丁
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


WS = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_GLB = WS / "holo_pet/assets/digital-human/raw/phase2a-lowpoly-glb/tripo-out/gbt-tpose-lowpoly-glb-convert-16d8db89/model.glb"
REF = WS / "holo_pet/assets/digital-human/raw/phase2a-tpose/T-pose参考-规范化.png"
GLB = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else DEFAULT_GLB
OK_FILE = WS / ".digihuman/S2-human-ok.json"
FIVE = ["双臂水平", "双腿直立", "正面全身", "无遮挡物", "白底"]


def positions(p: pathlib.Path):
    import numpy as np
    raw = p.read_bytes()
    jl, = struct.unpack_from("<I", raw, 12)
    J = json.loads(raw[20:20 + jl].decode("utf-8"))
    off = 20 + jl + ((-jl) % 4)
    bl, = struct.unpack_from("<I", raw, off)
    BIN = raw[off + 8: off + 8 + bl]
    a = J["accessors"][J["meshes"][0]["primitives"][0]["attributes"]["POSITION"]]
    bv = J["bufferViews"][a["bufferView"]]
    return np.frombuffer(BIN, np.float32, a["count"] * 3, bv.get("byteOffset", 0)).reshape(-1, 3).astype("float32")


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else ""


def silhou(REF_png: pathlib.Path) -> dict:
    """**剪影四项代理读数**（白底图上量）—— 这才是"机器能帮人看"的那部分。

    🔴 2026-10-10 补：原件只量了一个"白底（边缘亮度/饱和）"，而**我渲废的那张图也是白底**
    （扭曲碎片铺在白底上，边缘照样 253/0.1）⇒ 那条代理**放过了废图**。
    现补四项真能分辨废图的读数（全部从**非白像素的剪影**里量，不需要人眼）：
      ① 主体高度占比 —— 全身图应占 ≥55% 画高；碎片图会很小。
      ② 水平居中   —— 剪影横向中心应贴近画幅中心（±12%）。
      ③ 双臂带     —— 找"最宽那一行"所处高度；T-pose 的宽度峰应在**肩高带（上 1/3~1/2）**，
                       而不是在中轴附近（废图的宽度峰位置乱）。
      ④ 双腿分离   —— 下半段（髋以下）应出现**两段互不相连**的剪影（腿间有空隙）；
                       粘连成一坨 = 不成人形。
    """
    import numpy as np
    from PIL import Image
    out = {}
    im = np.asarray(Image.open(REF_png).convert("L"), dtype="float32")
    H, W = im.shape
    fg = im < 235                                   # 非白 = 主体
    if fg.sum() < 100:
        return {"剪影": "**几乎没有主体**（全白或近全白）"}
    ys, xs = np.nonzero(fg)
    out["① 主体高度占比"] = "%.0f%%（应≥55%%）" % (100.0 * (ys.max() - ys.min() + 1) / H)
    out["② 水平居中"] = "偏离中心 %.1f%%（应≤12%%）" % (100.0 * abs((xs.min() + xs.max()) / 2 - W / 2) / W)
    widths = fg.sum(axis=1)
    peak = int(np.argmax(widths))
    out["③ 双臂带（最宽行在画高）"] = "%.0f%%（T-pose 应在上 1/3~1/2）" % (100.0 * peak / H)
    # ④ 双腿分离：在下半段取一条水平扫描线，数连通段
    band = fg[int(H * 0.72):int(H * 0.88)]
    if band.size:
        col = band.any(axis=0).astype("int8")
        seg = 0
        for i in range(1, len(col)):
            if col[i] == 1 and col[i - 1] == 0:
                seg += 1
        out["④ 双腿分离（下半段连通段）"] = "%d 段（双腿直立应为 2）" % seg
    return out


def proxies():
    """机器代理读数（**仅提示**：源码把判定权交给人工复核）。"""
    import numpy as np
    out = {}
    if GLB.exists():
        P = positions(GLB)
        y0, y1 = float(P[:, 1].min()), float(P[:, 1].max())
        H = max(1e-6, y1 - y0)
        span = float(max(P[:, 0].max() - P[:, 0].min(), P[:, 2].max() - P[:, 2].min()))
        out["臂展/身高（源码口径：≈身高）"] = f"{span/H:.2f}（高 {H:.3f}）"
        lo = P[P[:, 1] <= y0 + H * 0.33]
        mid = P[(P[:, 1] > y0 + H * 0.33) & (P[:, 1] <= y0 + H * 0.66)]
        w = lambda q: float(max(q[:, 0].max() - q[:, 0].min(), q[:, 2].max() - q[:, 2].min())) if len(q) else 0.0
        out["下/中段水平半宽（腿细于躯干）"] = f"{w(lo):.3f}/{w(mid):.3f}"
    if REF.exists():
        try:
            from PIL import Image
            im = np.asarray(Image.open(REF).convert("RGB"), dtype="float32")
            b = np.concatenate([im[:6].reshape(-1, 3), im[-6:].reshape(-1, 3),
                                im[:, :6].reshape(-1, 3), im[:, -6:].reshape(-1, 3)])
            out["白底（边缘亮度/饱和）"] = f"{b.mean():.0f} / {(b.max(axis=1)-b.min(axis=1)).mean():.1f}"
            out.update(silhou(REF))
        except Exception as e:
            out["白底"] = f"读图失败 {type(e).__name__}"
    return out


def selftest() -> int:
    """**常驻负对照**（本仓律：判据没有负对照就是摆设）。

    三条，全部真跑：
      ① 旧格式记录（无 sha256）⇒ 必须判红（"无法证明它复核的是现在这张图"）
      ② 把图换成另一张     ⇒ 必须判红（"复核已失效"）
      ③ 换回原图           ⇒ 必须判绿
    """
    import shutil
    print("S2 门自检（三条负对照 · 真跑真换图）")
    if not REF.is_file():
        print("  **参考图不在，自检做不了**（如实报）"); return 1
    bak = REF.with_suffix(".png.selftest-bak")
    other = WS / "state" / "dh-v2-preview.png"
    shutil.copyfile(REF, bak)
    try:
        # ① 旧格式记录
        keep = OK_FILE.read_text(encoding="utf-8") if OK_FILE.exists() else None
        if keep:
            rec = json.loads(keep); rec.pop("sha256", None)
            OK_FILE.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        r1 = _run_gate()          # 🔴 别调 main() —— sys.argv 里还带着 --selftest，会无限递归
        print("  ① 旧格式记录(无 sha256) => %s" % ("红 ✅" if r1 != 0 else "**绿（漏了）**"))
        # ② 换图
        if not other.is_file():
            print("  ② 跳过（没有第二张图可用）"); return 1
        if keep:
            rec = json.loads(keep); rec["sha256"] = _sha(REF)
            OK_FILE.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        shutil.copyfile(other, REF)
        r2 = _run_gate()
        print("  ② 图片换掉 => %s" % ("红 ✅" if r2 != 0 else "**绿（漏了）**"))
        # ③ 换回
        shutil.copyfile(bak, REF)
        r3 = _run_gate()
        print("  ③ 换回原图 => %s" % ("绿 ✅" if r3 == 0 else "**红（误伤）**"))
        ok = (r1 != 0 and r2 != 0 and r3 == 0)
        print("自检：%s" % ("全过" if ok else "**不过**"))
        return 0 if ok else 1
    finally:
        shutil.copyfile(bak, REF)
        bak.unlink()


def _run_gate() -> int:
    """只跑判定部分，不重新打印代理读数（供自检用）。"""
    if not OK_FILE.exists() or not REF.is_file():
        return 1
    rec = json.loads(OK_FILE.read_text(encoding="utf-8"))
    was = rec.get("sha256") or ""
    now = _sha(REF)
    return 0 if (now and was and was == now) else 1


def main():
    if "--selftest" in sys.argv:
        return selftest()
    if "--confirm" in sys.argv:
        who = sys.argv[sys.argv.index("--confirm") + 1] if len(sys.argv) > sys.argv.index("--confirm") + 1 else "unknown"
        OK_FILE.parent.mkdir(parents=True, exist_ok=True)
        OK_FILE.write_text(json.dumps({
            "confirmed_by": who, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "artifact": str(REF.relative_to(WS)) if REF.exists() else None,
            # 🔴 2026-10-10 **核心修复**：复核必须绑到**这张图的哈希**上。
            #    原来只记路径、门也只查"记录文件在不在" ⇒ **图换了，18 天前的复核照样放行**
            #    （实测：我那张渲废的扭曲图也被判 ✅）。现在记 sha256，门必须比对。
            "sha256": _sha(REF),
            "five": FIVE, "note": "人工复核：打开规范化图逐条看过（源码 run-pipeline.ps1:73 要求）",
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"已落人工确认记录 → {OK_FILE.relative_to(WS)}（复核人 {who}）")
        return 0

    print("S2 姿态门（源码口径：五条判据 **必做人工复核**；机器只给代理读数，不单独判过）")
    for k, v in proxies().items():
        print(f"  · 代理读数 {k}  {v}")
    print(f"  待人工复核图: {REF.relative_to(WS) if REF.exists() else '（缺图）'}")
    print("  五条判据: " + " / ".join(FIVE))

    if not OK_FILE.exists():
        print("S2 门: ⏳ 待人工确认 —— 打开上图逐条看过，然后：")
        print('        python tools/digihuman/tpose-check.py --confirm "<复核人>"')
        return 1
    rec = json.loads(OK_FILE.read_text(encoding="utf-8"))
    # 🔴 2026-10-10 **核心修复**：比对"记录里的哈希"与"现在这张图的哈希"。
    #    旧记录没有 sha256 字段 ⇒ 一律视为**过期**（不能证明它复核的是现在这张图）。
    #    图一换（重渲/换绑骨）⇒ 复核自动失效，必须重新看过再 confirm。这就是反静默。
    now_sha = _sha(REF)
    was_sha = rec.get("sha256") or ""
    if not now_sha:
        print("S2 门: ⏳ 待人工确认 —— 图不在，没得看")
        return 1
    if not was_sha:
        print(f"S2 门: ⏳ 待人工确认 —— 复核记录**没有绑定图片哈希**"
              f"（旧格式，无法证明它复核的是现在这张图）· 记录 {rec.get('confirmed_by')} @ {rec.get('at')}")
        print('        重新看过再落：python tools/digihuman/tpose-check.py --confirm "<复核人>"')
        return 1
    if was_sha != now_sha:
        print(f"S2 门: ❌ **复核已失效** —— 图片换过了（记录 sha256 {was_sha[:12]}… ≠ 现在 {now_sha[:12]}…）")
        print(f"        记录复核的是旧图（{rec.get('confirmed_by')} @ {rec.get('at')}）⇒ 必须重新逐条看过再 confirm")
        print('        python tools/digihuman/tpose-check.py --confirm "<复核人>"')
        return 1
    print(f"S2 门: ✅ 人工已复核（{rec.get('confirmed_by')} @ {rec.get('at')}）· "
          f"图哈希吻合 {now_sha[:12]}… · 五条 = {' / '.join(rec.get('five', FIVE))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
