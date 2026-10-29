# -*- coding: utf-8 -*-
"""面板连通性审计器（**扰动法**）—— 回答「面板的功能到底连没连上」。

## 口径（这一件就是口径的载体）

> 改**源头** → 重生成面板 → 看读数**跟不跟着动**。
> **跟得动 = 活的（真连着）**；**纹丝不动 = 写死的**。
> 且**必须有反向对照** —— 没有反向对照，"什么都动"也能骗过检查。

## 四条扰动（都可逆，跑完各自复检基线）

| 扰 | 动谁 | 期望 |
|---|---|---|
| 许可账 | 登记一件临时件再撤 | 面板「许可账 N 条」±1 再复原 |
| 发布包 | 放一件 `*.publish.json` 再回收 | 「发布包 N 份」±1 再复原 |
| 有货 | 往**空**抽屉放一件成品名件再回收 | 「有货」标记 +1 再复原 |
| 试听台 | 改 `audition.json` 的时长（**音频不动**）再还原 | 时长徽章跟着变；**独立 ffprobe 复核当场报「对不上」** |

第 4 扰一箭双雕：既验"读得活"，又验**那条独立复核不是摆设**。

## 三条纪律（踩过才知道）

1. **扰动必须可逆，且改完复检基线**（抽屉回 `.gitkeep` · 许可账/发布包回原数 · 闸门汇总逐字不变）。
2. **选对扰动对象**：`music/03-arrange` **不是** `license_required` 的成品格 ⇒
   往它放件**不会顺带把闸门弄红**。乱选一格 = **自己造一条 P0**。
3. **"算出来的" ≠ "已证活的"** —— 前者看源码能定，后者要扰动才敢说。**两者不许合并。**

## 已知的两处取数坑（我自己踩过）

- 许可账/发布包条数在**生成器 stdout**（`许可账 11 条 · 发布包 3 份`），**不在 HTML 里**。
- 数 HTML 里 `>有货<` 会把**汇总行那一次**也算进去 ⇒ 绝对值偏大 1 ⇒ **只看增量**。

## 跑法

    py -3.14 tools/codex-scripts/panel-connectivity.py          # 四扰全跑
    py -3.14 tools/codex-scripts/panel-connectivity.py --only lic pub
"""

import json
import re
import subprocess
import sys
import time
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# 换目录后 `parents[1]` 不再指仓根 —— 按全仓通用写法找带 `gbt_allinone` 的那一层。
ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
sys.path.insert(0, str(ROOT))

PANEL = ROOT / "media-console.html"
GEN = ROOT / "tools" / "codex-scripts" / "media-console.py"


def _cr():
    s = spec_from_file_location("cr", ROOT / "tools" / "codex-scripts" / "clean_residue.py")
    m = module_from_spec(s)
    s.loader.exec_module(m)
    return m


def gen():
    p = subprocess.run([sys.executable, str(GEN)], cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    o, h = p.stdout or "", PANEL.read_text(encoding="utf-8")

    def _n(pat, src):
        m = re.search(pat, src)
        return int(m.group(1)) if m else None

    return {"许可账": _n(r"许可账 (\d+) 条", o), "发布包": _n(r"发布包 (\d+) 份", o),
            "有货标记": len(re.findall(r">有货<", h)),
            "试听秒数": _n(r"A 小调 · (\d+) s", h),
            "复核不一致": "与副档对不上" in h}


def main() -> int:
    only = set(a for a in sys.argv[1:] if not a.startswith("--")) or {"lic", "pub", "arr", "aud"}
    from gbt_allinone.tools import media_license as ML
    CR = _cr()
    print("=" * 74)
    print("面板连通性 · 扰动法（改源头 → 看重生成后的读数动不动）")
    print("=" * 74)
    a = gen()
    print("  基线：%s\n" % a)
    res = {}

    if "lic" in only:
        p = ROOT / "projects" / "_shared" / "_conn_probe.txt"
        p.write_text("probe", encoding="utf-8")
        ML.run("register", path=p.relative_to(ROOT).as_posix(),
               source="连通性扰动测试", license="自有")
        b = gen()
        ML.run("unregister", path=p.relative_to(ROOT).as_posix(), why="连通性扰动测试，用完撤")
        c = gen()
        CR._recycle_batch([p] if p.exists() else [])
        res["许可账"] = (a["许可账"], b["许可账"], c["许可账"])
        print("  扰① 许可账：%s → %s → %s" % res["许可账"])

    if "pub" in only:
        pubd = ROOT / "projects" / "_shared" / "publish" / "film"
        pubd.mkdir(parents=True, exist_ok=True)
        f = pubd / "99999999-film-_connprobe-rehearsal.publish.json"
        f.write_text(json.dumps({"product": {"file": "（扰动测试件）"}, "targets": []},
                                ensure_ascii=False), encoding="utf-8")
        b = gen()
        CR._recycle_batch([f] if f.exists() else [])
        c = gen()
        res["发布包"] = (a["发布包"], b["发布包"], c["发布包"])
        print("  扰② 发布包：%s → %s → %s" % res["发布包"])

    if "arr" in only:
        arr = ROOT / "projects" / "music" / "03-arrange"
        arr.mkdir(parents=True, exist_ok=True)
        f = arr / ("%s-music-connprobe-02arrangement.mid" % time.strftime("%Y%m%d"))
        f.write_bytes(b"MThd" + b"\x00" * 10)
        b = gen()
        CR._recycle_batch([f] if f.exists() else [])
        c = gen()
        res["有货标记"] = (a["有货标记"], b["有货标记"], c["有货标记"])
        print("  扰③ 有货  ：%s → %s → %s（绝对值含汇总行，**只看增量**）" % res["有货标记"])

    if "aud" in only:
        side = ROOT / "projects" / "_shared" / "audition" / "audition.json"
        if not side.exists():
            print("  扰④ 试听台：跳过（副档不在盘上）")
        else:
            raw = side.read_bytes()
            try:
                d = json.loads(raw.decode("utf-8"))
                d["时长_s"] = 41.5
                side.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
                b = gen()
            finally:
                side.write_bytes(raw)
            c = gen()
            res["试听秒数"] = (a["试听秒数"], b["试听秒数"], c["试听秒数"])
            res["复核不一致"] = (a["复核不一致"], b["复核不一致"], c["复核不一致"])
            print("  扰④ 试听台：秒数 %s ｜ 复核报不一致 %s"
                  % (res["试听秒数"], res["复核不一致"]))

    print("\n=== 判读 ===")
 # 「+1」只对**计数**成立。试听秒数是**换了个值**（52→42→52）⇒ 判据是"变了、且复原"。
    #    第一版我对所有项一律用 +1 ⇒ 把**明明跟得动**的试听秒数印成「纹丝不动 = 写死的」
    #    —— **那是我的判词错，不是面板错**。**假红比不报更坏**（会让人不再信这条警告）。
    RULE = {"试听秒数": lambda x, y, z: (y != x and z == x)}
    ok = True
    for k, (x, y, z) in ((k, v) for k, v in res.items() if k != "复核不一致"):
        good = RULE.get(k, lambda x, y, z: (y == x + 1 and z == x))(x, y, z)
        ok &= good
        print("  %-8s %s → %s → %s ⇒ %s" % (k, x, y, z,
              "✅ **活的**" if good else "❌ 纹丝不动 = 写死的"))
    if "复核不一致" in res:
        x, y, z = res["复核不一致"]
        good = (not x) and y and (not z)
        ok &= good
        print("  独立复核 基线%s → 扰动后%s → 还原后%s ⇒ %s"
              % (x, y, z, "✅ **是真的**（撒的谎被抓）" if good else "❌ 摆设"))
    print("\n  ⚠️ 本器**改完必复原**；跑完请自行复检基线（抽屉/许可账/发布包/闸门汇总）。")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
