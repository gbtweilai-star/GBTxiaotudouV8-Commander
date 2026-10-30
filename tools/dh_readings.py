#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dh_readings —— 把「页面八步」的读数收回来，喂给 dh_realism.check()

主人令（2026-10-30）：
「补读数采集：页面采集八步的运行时读数 → dh_realism check 能给出『过几步』的硬数字
（这一步不做，后面全是盲改）」

## 两档，各自如实标来源
  live    真开页面，跑 `window.GBT_DH3D.readings()`（真运行时）
  static  解析 dh3d.js 里的常量（exposure/灯强/材质），**标注 static，不冒充运行时**

为什么要 static 兜底：本机 iSH 里 8080 常被冻住、WebGL 也不一定有 ——
读不到就如实降级，不许把"没读到"说成"过了"。

## 输出
    {"via":"live|static", "readings":{...}, "passed":N, "failed":M, "unknown":K,
     "verdict":"过 N/M 判据（K 项没读数）", "rows":[...]}

用法：
    python3 tools/dh_readings.py                # 先试 live，失败退 static
    python3 tools/dh_readings.py --static       # 只跑 static
    python3 tools/dh_readings.py --json         # 机读
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE = "holo_pet_w3/voice-theater/index.html"
JS = ROOT / "holo_pet_w3" / "voice-theater" / "dh3d.js"
# 2026-10-30：3D 舞台是 ?dh3d=1 才懒加载的（默认页面走 2D，不拉 600K 的 three）
# 2026-10-30：3D 读数走**独立页**。原因实测：WebView 会吞掉 query（location.search 为空），
# 所以主页面上的 ?dh3d=1 懒加载器永不触发。stage3d.html 直挂脚本，不靠 query。
URLS = ("http://127.0.0.1:8080/holo_pet_w3/voice-theater/stage3d.html",
        "http://127.0.0.1:8765/holo_pet_w3/voice-theater/stage3d.html")


def _alive(url: str, timeout: float = 4.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= getattr(r, "status", 200) < 400
    except Exception:                                             # noqa: BLE001
        return False


def collect_live() -> dict:
    """真开页面取运行时读数。取不到就返回 {ok:False}，不编。

    2026-10-30 实测：`minis-browser-use execute_js` 的回包是
        {"ok":true,"data":{"success":true,"text":"<JSON 字符串>"}}
    结果在 data.text 里**且是字符串** —— 第一次按 dict 解析所以永远失败。
    """
    url = next((u for u in URLS if _alive(u.split("?")[0])), None)
    if not url:
        return {"ok": False, "why": "页面打不开（8080/8765 都不通）"}
    js = ("var r=(window.GBT_DH3D&&window.GBT_DH3D.readings)?window.GBT_DH3D.readings():null;"
          " return r;")
    try:
        subprocess.run(["minis-browser-use", "navigate", "--url", url],
                       capture_output=True, text=True, timeout=90)
        # 3D 是懒加载：等 three + GLB 落地
        for _ in range(6):
            import time as _t
            _t.sleep(5)
            p2 = subprocess.run(["minis-browser-use", "execute_js", "--script", js],
                                capture_output=True, text=True, timeout=90)
            out = p2.stdout or ""
            i = out.find("{")
            if i < 0:
                continue
            try:
                env = json.loads(out[i:out.rfind("}") + 1])
            except Exception:                                     # noqa: BLE001
                continue
            txt = (env.get("data") or {}).get("text") or ""
            txt = txt.split("  tab_id:")[0].strip()
            j = txt.find("{")
            if j < 0:
                continue
            try:
                r = json.loads(txt[j:txt.rfind("}") + 1])
            except Exception:                                     # noqa: BLE001
                continue
            if isinstance(r, dict) and r.get("webgl") is not None and r.get("status") == "ready":
                return {"ok": True, "readings": r, "url": url}
        return {"ok": False, "why": "页面没回 readings（3D 未 ready / WebGL 没起）"}
    except Exception as exc:                                      # noqa: BLE001
        return {"ok": False, "why": "%s: %s" % (type(exc).__name__, exc)}


def collect_static() -> dict:
    """从 dh3d.js 的常量里取（**标注 static**，不冒充运行时）。"""
    if not JS.is_file():
        return {"ok": False, "why": "dh3d.js 不在"}
    s = JS.read_text(encoding="utf-8", errors="replace")
    r = {"source": "static", "file": str(JS.relative_to(ROOT))}

    def num(pat, default=None):
        m = re.search(pat, s)
        return float(m.group(1)) if m else default

    r["environment"] = bool(re.search(r"scene\.environment\s*=", s)) or \
        bool(re.search(r"PMREMGenerator|RoomEnvironment", s))
    dirs = [float(x) for x in re.findall(r"new THREE\.DirectionalLight\([^,]+,\s*([\d.]+)\)", s)]
    r["dir_light_sum"] = round(sum(dirs), 3) if dirs else None
    hemi = [float(x) for x in re.findall(r"new THREE\.HemisphereLight\([^,]+,[^,]+,\s*([\d.]+)\)", s)]
    r["hemi"] = round(sum(hemi), 3) if hemi else None
    r["exposure"] = num(r"toneMappingExposure\s*=\s*([\d.]+)")
    r["tone_mapping"] = "ACESFilmic" if "ACESFilmicToneMapping" in s else None
    r["color_space"] = "SRGBColorSpace" if "SRGBColorSpace" in s else None
    # 材质：从源码里真读赋值（2026-10-30 之前是写死 None，等于永远"没读数"）
    def m_num(prop):
        m = re.search(r"m\." + prop + r"\s*=\s*([\d.]+)", s)
        return float(m.group(1)) if m else None

    r["metalness_mean"] = m_num("metalness")
    r["ior"] = m_num("ior")
    r["specular"] = m_num("specularIntensity")
    r["clearcoat"] = m_num("clearcoat")
    r["diffuse_roughness"] = m_num("roughness")
    r["body_tex_px"] = None
    r["detail_normal"] = None
    return {"ok": True, "readings": r}


def grade(readings: dict) -> dict:
    sys.path.insert(0, str(ROOT))
    from gbt_allinone.tools import dh_realism as DR
    # check 是类方法；模块入口是 run(op="check", render_readings=...)
    res = DR.run("check", readings=readings)
    rows = res.get("明细") or res.get("checks") or res.get("rows") or []
    if not rows:
        return {"ok": False, "why": "check 没回明细", "raw": json.dumps(res, ensure_ascii=False)[:200]}
    p = res.get("过", sum(1 for x in rows if x.get("pass") is True))
    f = res.get("不过", sum(1 for x in rows if x.get("pass") is False))
    u = res.get("未给读数", sum(1 for x in rows if x.get("pass") is None))
    return {"ok": True, "passed": p, "failed": f, "unknown": u,
            "total": len(rows),
            "verdict": "过 %d/%d 判据（%d 项没读数）· %s"
                       % (p, len(rows), u, res.get("结论") or ""),
            "rows": rows}


def main() -> int:
    want_static = "--static" in sys.argv
    got = {"ok": False, "why": "跳过 live"}
    if not want_static:
        got = collect_live()
    via = "live"
    if not got.get("ok"):
        live_why = got.get("why")
        got = collect_static()
        via = "static"
        got["live_why"] = live_why
    if not got.get("ok"):
        print("  收不到读数：%s" % got.get("why"))
        return 2
    g = grade(got["readings"])
    out = {"via": via, "readings": got["readings"], **g}
    if got.get("live_why"):
        out["live_why"] = got["live_why"]
    if "--json" in sys.argv:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print("  读数来源：%s%s" % (via, ("（live 失败：%s）" % out["live_why"]) if out.get("live_why") else ""))
        for x in g.get("rows") or []:
            mark = "✅" if x.get("pass") is True else ("🔴" if x.get("pass") is False else "⚪")
            print("   %s %-16s got=%-10s want=%s"
                  % (mark, x.get("判据"), str(x.get("got"))[:10], x.get("want")))
        print("  判决：%s" % g.get("verdict"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
