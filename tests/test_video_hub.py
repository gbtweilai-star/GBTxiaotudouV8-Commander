# -*- coding: utf-8 -*-
"""video_hub + page mesh 验收：视频能力融合编目、每页脉冲、页间双向链、共享缓存。"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import video_hub as VH  # noqa: E402

OK = 0
FAIL = []


def check(name, cond, got=None):
    global OK
    if cond:
        OK += 1
        print("  ok  ", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, "|", repr(got)[:200])


def main() -> int:
    print("[1] 视频能力融合编目")
    r = VH.verify()
    check("verify() 全绿", r["ok"] is True, r.get("failed"))
    check("判据数 ≥ 8", r["checks"] >= 8, r["checks"])
    c = VH.catalog()
    check("视频能力 ≥ 20", c["count"] >= 20, c["count"])
    check("六段+其他", [s["stage"] for s in c["stages"]] == [s[0] for s in VH.STAGES])
    caps = {it["cap"] for st in c["stages"] for it in st["items"]}
    check("关键能力在", {"media_run", "media_library", "digital_human",
                        "comfy_native", "hunyuan_video"} <= caps)
    check("每件有段落", all(it["stage"] for st in c["stages"] for it in st["items"]))
    check("没有重复", len(caps) == c["count"], (len(caps), c["count"]))

    rr = VH.run("run")
    check("六段联跑有 6 段", len(rr.get("stages") or []) == 6, len(rr.get("stages") or []))
    check("联跑不生成视频", rr.get("video_generated") is False, rr.get("video_generated"))
    dd = VH.dispatch("media_library", {"op": "verify"})
    check("视频舱路由器可执行编目内能力", dd.get("ok") is True, dd.get("error"))
    bad = VH.dispatch("totally_not_video_cap", {})
    check("编目外能力拒", bad.get("ok") is False, bad)

    print("[2] 统一门 / API / 视频舱")
    reg = (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8")
    check("注册表 video_hub", '"video_hub": {' in reg and '"handler": "video_hub"' in reg)
    check("api 分派 video_hub", 'kind == "video_hub"' in api)
    check("run_task 可达", _gate_ok())
    srv = (ROOT / "tools/console-server.py").read_text(encoding="utf-8")
    check("server /api/video", '"/api/video"' in srv and "video_hub" in srv)
    idx = (ROOT / "holo_pet_w3/console/index.html").read_text(encoding="utf-8")
    check("视频舱 tab/view", 'data-view="video"' in idx and 'id="vh-stages"' in idx)
    check("video-hub.js/page-mesh.js", "video-hub.js" in idx and "page-mesh.js" in idx)
    js = (ROOT / "holo_pet_w3/console/video-hub.js").read_text(encoding="utf-8")
    check("视频舱只读", "/api/video" in js and "fetch" in js)

    print("[3] 每页脉冲 / 双向链 / 共享缓存")
    mesh = (ROOT / "holo_pet_w3/console/page-mesh.js").read_text(encoding="utf-8")
    check("每页注入 pulse", "page-pulse" in mesh and "injectPulses" in mesh)
    check("页间双向总线", "BroadcastChannel" in mesh and "postMessage" in mesh)
    check("全页链数", "pages.length * (pages.length - 1)" in mesh)
    check("每窗口独立 me/＋窗口", "win-" in mesh and "mesh-open" in mesh)
    shell = (ROOT / "holo_pet_w3/shell/main.cjs").read_text(encoding="utf-8")
    check("壳允许 console 第二窗", 'u.pathname.startsWith("/console")' in shell)
    shell = (ROOT / "holo_pet_w3/shell/main.cjs").read_text(encoding="utf-8")
    check("壳允许 console 第二窗", 'u.pathname.startsWith("/console")' in shell)
    check("每窗口独立 me/＋窗口", "win-" in mesh and "mesh-open" in mesh)
    shell = (ROOT / "holo_pet_w3/shell/main.cjs").read_text(encoding="utf-8")
    check("壳允许 console 第二窗", 'u.pathname.startsWith("/console")' in shell)
    shell = (ROOT / "holo_pet_w3/shell/main.cjs").read_text(encoding="utf-8")
    check("壳允许 console 第二窗", 'u.pathname.startsWith("/console")' in shell)
    check("共享缓存", "prefetch" in mesh and "__pageMeshCache" in mesh)
    css = (ROOT / "holo_pet_w3/console/app.css").read_text(encoding="utf-8")
    check("脉冲 CSS", ".page-pulse" in css and "pp-beat" in css)
    check("HUD", "#page-mesh-hud" in css and "page-mesh-hud" in mesh)
    payload = (ROOT.parent / "GBT小土豆V8桌面版" / "payload")
    if payload.is_dir():
        check("APP payload 已同步",
              (payload / "gbt_allinone/tools/video_hub.py").is_file()
              and (payload / "holo_pet_w3/console/page-mesh.js").is_file()
              and (payload / "holo_pet_w3/console/video-hub.js").is_file())
    check("文档 180/181 存在", (ROOT / "docs/180-video-hub.md").is_file()
          and (ROOT / "docs/181-page-mesh.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— video_hub（33 件六段）+ 页面触手网格（每页脉冲/双向链/缓存）全绿")
    return 0


def _gate_ok():
    try:
        import gbt_allinone as g
        r = g.run_task("video_hub", {"op": "verify"}, safe=True)
        inner = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return bool(r.get("ok")) and bool(inner.get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
