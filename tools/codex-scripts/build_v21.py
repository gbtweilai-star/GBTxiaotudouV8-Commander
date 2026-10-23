# -*- coding: utf-8 -*-
"""构建 V21：修「列向 flex 压扁面板」这个影响所有面板的布局 bug。
修法一行：.chat-body>*,.god-body>*{flex:0 0 auto} —— 已进 refine.css，
本脚本把它补进 V20 两个交付件并重建为 V21。
"""
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# 本目录自 .scratch/ 迁到 tools/codex-scripts/ 后深度 +1：原来的 .parent.parent
# 落在 …\tools\（tools 下 0 个 html）。向上找根标记；改对之后本脚本才会真的
# 走到下面的写盘，也才会真的覆盖已发布的 V21 —— 所以守卫必须同在。
BASE = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
S = BASE / ".scratch"
ALLOW_OVERWRITE = "--allow-overwrite" in sys.argv

FIX_CSS = """
/* ── V21 · 真渲染揪出的布局 bug（影响所有面板）──
   .chat-body 是 display:flex;flex-direction:column;overflow-y:auto。
   列向 flex 的子项默认 flex-shrink:1 —— 内容比容器高时**不是滚动，而是被压缩**，
   再被 .card{overflow:hidden} 把压缩后的溢出裁掉 ⇒ 内容被静默切掉。
   实测：某卡片渲染高 248 / 内容高 268 以上，容器 scrollHeight===clientHeight（根本不滚）。
   修：面板直接子项一律不许收缩，容器这才真的滚动。 */
.chat-body>*,.god-body>*{flex:0 0 auto}
.god-body{overflow-y:auto}
"""

for prot, name in ((True, "V20 GBT小土豆V8-可交互原型.html"), (False, "V20 GBT小土豆V8-无限画布.html")):
    src_p = BASE / name
    if not src_p.exists():
        src_p = BASE / "archive" / name
        assert src_p.exists(), "找不到 " + name
    out = BASE / name.replace("V20 ", "V21 ")
    # 交付物契约：文件名形如 V{N} GBT小土豆V8-*.html 的是已发布版本，禁止原地覆盖。
    # 旧版第 43 行 out.write_text() 直接盖掉已发布的 V21，且第 32 行归档的是 V20 源
    # —— 对 V21 输出零备份。要重建必须显式 --allow-overwrite，且先归档现有版本。
    if out.exists():
        assert ALLOW_OVERWRITE, (
            "拒绝覆盖已发布版本：%s\n"
            "  已发布版本不许原地覆盖。请改产出下一版号（V22），"
            "或显式重跑：py build_v21.py --allow-overwrite（会先归档现有 V21）" % out.name)
        shutil.copy2(out, BASE / "archive" / out.name)
        print("  覆盖前已归档:", out.name)
    shutil.copy2(src_p, BASE / "archive" / name)
    t = src_p.read_text(encoding="utf-8")
    t = t.replace(name.replace("V20 ", "V20 "), name.replace("V20 ", "V21 "))
    t = t.replace("可交互原型 V20", "可交互原型 V21").replace("无限画布 V20", "无限画布 V21")
    t = re.sub(r"\bV20\b", "V21", t)
    # 把修复追加到最后一个 <style id="refine"> 之前（即 refine 块内）
    m = list(re.finditer(r'<style id="refine">', t))
    assert m, "找不到 refine 样式块: " + name
    i = m[-1].end()
    t = t[:i] + FIX_CSS + t[i:]
    out.write_text(t, encoding="utf-8")
    print("写出:", out.name, "%.1f KB" % (out.stat().st_size / 1024))
    if src_p.parent == BASE:
        src_p.unlink()
        print("  移除旧版:", src_p.name)
