# -*- coding: utf-8 -*-
"""决定性实验：`file://` 下换 query 到底能不能绕开浏览器缓存重读？

为什么非做不可：触手视觉回传窗的"活的"这件事**完全押在这个假设上**。
若假设不成立，那扇窗会显示第一帧然后**永远冻在那里** —— 看着在动、其实是死图，
比没有这扇窗更坏（它会冒充"这是现在"）。所以先证伪，再谈交付。

测两条：
  A) 动态插 `<script src="x.js?t=N">` 换 query → 能不能读到被改过的内容
  B) `<img src="a.png?t=N">` 换 query → 能不能重新加载被改过的图
用法: py -3.14 <本文件>
"""
import pathlib
import sys
import tempfile

from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROBE = """<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
<img id="pic" src="a.png" alt="">
<script>
window.LOG = [];
var n = 0;
function tick(){
  n++;
  var s = document.createElement("script");
  s.src = "x.js?t=" + n;
  s.onload = function(){ window.LOG.push({n:n, val: window.VAL || null, err:null}); s.remove(); };
  s.onerror = function(){ window.LOG.push({n:n, val:null, err:"onerror"}); s.remove(); };
  document.body.appendChild(s);
  document.getElementById("pic").src = "a.png?t=" + n;
}
window.__tick = tick;
</script></body></html>
"""


def main():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="gbt_cacheprobe_"))
    (tmp / "probe.html").write_text(PROBE, encoding="utf-8")
    (tmp / "x.js").write_text("window.VAL='TOKEN-1';", encoding="utf-8")
    (tmp / "a.png").write_text("PNG-1", encoding="utf-8")

    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        pg = b.new_page()
        fails = []
        pg.on("requestfailed", lambda r: fails.append(r.url.split("/")[-1]))
        pg.goto((tmp / "probe.html").as_uri())
        pg.evaluate("__tick()")
        pg.wait_for_timeout(500)
        first = pg.evaluate("window.LOG")

        # 就地改内容，再 tick 一次
        (tmp / "x.js").write_text("window.VAL='TOKEN-2';", encoding="utf-8")
        (tmp / "a.png").write_text("PNG-2", encoding="utf-8")
        pg.evaluate("__tick()")
        pg.wait_for_timeout(700)
        second = pg.evaluate("window.LOG")

        print("A) <script> 换 query 重读：")
        print("   第1次:", first)
        print("   第2次:", second)
        vals = [r["val"] for r in second if r["val"]]
        a_ok = "TOKEN-2" in vals
        print("   结论:", "PASS —— 换 query 能读到新内容" if a_ok
              else "FAIL —— 换 query 读到的还是旧内容（动态清单方案不成立）")

        print("B) <img> 换 query 是否重新请求：")
        print("   requestfailed:", fails or "无")
        b.close()

    return 0 if a_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
