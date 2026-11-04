# -*- coding: utf-8 -*-
"""ref3d（我们的数字人 DH-V7 → 可拆解 3D 交互页）契约/技能/接线验收。"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import ref3d as R  # noqa: E402

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
    print("[1] 我们自己的数字人页面")
    v = R.verify()
    check("verify() 全绿", v["ok"] is True, v.get("failed"))
    check("判据 ≥ 10", v["checks"] >= 10, v["checks"])
    check("1 mesh / 66 bones", v["mesh"] == 1 and v["bones"] == 66, (v["mesh"], v["bones"]))
    page = R.PAGE.read_text(encoding="utf-8")
    check("__dh3d API", "__dh3d" in page and "buildFromImage" in page)
    check("加载我们的 GLB", "dh-v7-detail.glb" in page)
    check("拆解/骨架/透明", all(x in page for x in ("skeleton", "applyOpacity", "wire")))
    check("本地 Three/GLTF", R.THREE.is_file() and R.LOADER.is_file())
    check("GLB 在", R.MODEL.is_file() and R.MODEL.stat().st_size > 1000000)
    check("无网络依赖", "http://" not in page and "https://" not in page)

    print("[2] 技能已装进 skills_hub")
    from gbt_allinone.tentacle import skills_hub as S
    got = S.run("get", name="ref-to-3d")
    check("skills_hub 可读", got.get("ok") is True, got.get("error"))
    check("技能是数字人", "DH-V7" in (got.get("text") or ""))
    check("技能可匹配", any(m["name"] == "ref-to-3d"
                            for m in (S.run("match", query="参考图做数字人3D", top=5).get("matches") or [])))

    print("[3] 统一门 / API / APP / 唯一页面")
    reg = (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8")
    srv = (ROOT / "tools/console-server.py").read_text(encoding="utf-8")
    check("注册表 ref3d", '"ref3d": {' in reg and "DH-V7" in reg)
    check("api 分派 ref3d", 'kind == "ref3d"' in api)
    check("server /api/ref3d", '"/api/ref3d"' in srv)
    check("run_task 可达", _gate_ok())
    idx = (ROOT / "holo_pet_w3/console/index.html").read_text(encoding="utf-8")
    check("没有旧 dh 页", 'data-view="dh"' not in idx and "/dh-live/" not in idx)
    check("唯一数字人 3D 页", 'data-view="teardown"' in idx and "数字人 3D" in idx)
    payload = ROOT.parent / "GBT小土豆V8桌面版" / "payload"
    if payload.is_dir():
        check("APP payload 同步",
              (payload / "gbt_allinone/tools/ref3d.py").is_file()
              and (payload / "holo_pet_w3/teardown/index.html").is_file()
              and (payload / "holo_pet_w3/assets/dh/dh-v7-detail.glb").is_file()
              and not (payload / "holo_pet_w3/dh-live").exists())
    check("文档 182 存在", (ROOT / "docs/182-ref3d.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— ref3d（我们的数字人 DH-V7 / 1 mesh / 66 bones / 技能已装 / 旧页已清）全绿")
    return 0


def _gate_ok():
    try:
        import gbt_allinone as g
        r = g.run_task("ref3d", {"op": "verify"}, safe=True)
        inner = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return bool(r.get("ok")) and bool(inner.get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
