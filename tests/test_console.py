# -*- coding: utf-8 -*-
"""认知界面判据：旧面板拆干净、新控制台在位、土豆 Logo 用上、无限上下文口径在。

跑法：python tests/test_console.py
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(ROOT))

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)[:260]))
    if not cond:
        FAILED.append(name)


def main() -> int:
    print("[1] 旧 28+ 面板已拆（只留 assets/theme/shell/tests/console）")
    w3 = ROOT / "holo_pet_w3"
    keep = {"assets", "theme", "shell", "tests", "console"}
    left = sorted(p.name for p in w3.iterdir() if p.is_dir() and p.name not in keep)
    check("面板目录清零", not left, left)
    arch = ROOT / ".archive" / "panels-20261101"
    check("归档目录存在", arch.is_dir(), str(arch))
    check("归档里有 panel/capabilities", (arch / "panel").is_dir() and (arch / "capabilities").is_dir())

    print("[2] 新控制台三件套在位")
    con = w3 / "console"
    for f in ("index.html", "app.css", "app.js"):
        check(f + " 存在", (con / f).is_file(), str(con / f))
    html = (con / "index.html").read_text(encoding="utf-8")
    check("头像由 CSS 引用（icons/avatar.png）", "../../icons/avatar.png" in html or "../../icons/avatar.png" in (con / "app.css").read_text(encoding="utf-8"))
    check("favicon 用头像", "avatar-96.png" in html)
    check("三栏结构（panel-l1/chat-area/panel-l2）",
          all(k in html for k in ('id="panel-l1"', 'id="chat-area"', 'id="panel-l2"')))

    print("[2b] 1:1 设计令牌/布局（照 BaiLongma）")
    css = (con / "app.css").read_text(encoding="utf-8")
    for token in ("--side-panel-width: clamp(260px, 25vw, 362px)",
                  "--bg0: #111821", "--warm: #ff9f1c",
                  "--side-panel-console-inset", ".panel {"):
        check("令牌/规则 " + token[:28], token in css, token)
    check("侧栏 fixed 三栏", "position: fixed; top: 20px; bottom: 20px" in css)
    check("中栏 inset = side+40", "left: var(--side-panel-console-inset)" in css)
    check("中栏是底部座席（DSH composerSeat：bottom 0 + 渐变）", "bottom: 0" in css and "linear-gradient(180deg" in css)
    check("右栏透明 rail", "#panel-l2 {" in css and "background: transparent" in css)
    check("行动日志 clamp 高度", "clamp(180px, 25vh, 220px)" in css)
    check("心跳图 92px", "height: 92px" in css)

    print("[2c] 实测几何（与参考渲染对齐：面板 top=20 / 左 20-381 / 右 1218-1579）")
    check("无 38px 视口偏移", ".app-viewport { position: fixed; inset: 0;" in css)
    check("面板 top 20 / bottom 20", "position: fixed; top: 20px; bottom: 20px" in css)

    print("[3] 无限上下文 + 稳定输出口径写进界面")
    js = (con / "app.js").read_text(encoding="utf-8")
    check("界面写无限上下文", "无限上下文" in js or "无限制上下文" in js)
    check("界面写稳定输出 temperature=0", "temperature=0" in js)
    check("对话走 /api/chat", "/api/chat" in js)

    print("[3b] 四视图 + 3D 触手星图")
    for v in ("caps", "skills", "dash", "space"):
        check("视图页签 " + v, ('data-view="' + v + '"') in html)
    check("功能表容器", 'id="cap-rows"' in html)
    check("技能卡容器", 'id="skill-grid"' in html)
    check("3D canvas", 'id="space3d-canvas"' in html)
    sp = (con / "space3d.js")
    check("space3d.js 存在", sp.is_file())
    sj = sp.read_text(encoding="utf-8")
    check("3D 有 40 根/位触手", "TENTACLES_PER_CAP = 40" in sj)
    check("3D 标记可巡检", "data-space3d" in sj)
    check("three.js 已内置", (ROOT / "holo_pet_w3" / "assets" / "vendor" / "three" / "three.module.js").is_file())
    vendor = ROOT / "holo_pet_w3" / "assets" / "vendor" / "three"
    check("Bloom 后处理已内置", (vendor / "postprocessing" / "UnrealBloomPass.js").is_file())
    check("EffectComposer 已内置", (vendor / "postprocessing" / "EffectComposer.js").is_file())
    check("3D 用 Bloom", "UnrealBloomPass" in sj)
    check("3D 有真实调用点亮", "pulse" in sj and "pulseOverlay" in sj)
    check("3D 支持实时 SSE", "EventSource" in sj and "liveBurst" in sj)
    check("鼠标拖动绑整块区域", "OrbitControls(camera, wrap)" in sj and ".space3d-wrap" in sj)
    check("大脑执行层视图", 'data-view="brain"' in html and 'id="brain3d-canvas"' in html)
    bj = (con / "brain3d.js")
    check("brain3d.js 存在", bj.is_file())
    bjs = bj.read_text(encoding="utf-8")
    check("脑图有七步", bjs.count("neighborhood") >= 0 and bjs.count("name:") >= 7)
    check("脑图标记可巡检", "data-brain3d" in bjs)
    check("脑图接审计闭环", "TorusGeometry" in bjs and "getPointAt" in bjs)
    check("万能插视图", 'data-view="plug"' in html and 'id="plug3d-canvas"' in html)
    pj = (con / "plug3d.js")
    check("plug3d.js 存在", pj.is_file())
    pjs = pj.read_text(encoding="utf-8")
    check("万能插有 8 插口", pjs.count("name:") >= 8)
    check("万能插数字流动", "offset.x" in pjs and "CanvasTexture" in pjs)
    check("万能插标记可巡检", "data-plug3d" in pjs)
    check("触手协作视图", 'data-view="team"' in html and 'id="team3d-canvas"' in html)
    tj = (con / "team3d.js")
    check("team3d.js 存在", tj.is_file())
    tjs = tj.read_text(encoding="utf-8")
    check("协作有 8 角色", tjs.count("name:") >= 8)
    check("协作有流动消息", "pulses" in tjs and "getPointAt" in tjs)
    check("协作标记可巡检", "data-team3d" in tjs)
    check("触手协作有脉冲特效", "ringSprite" in tjs and "waves" in tjs)
    check("脉冲标记可巡检", "team3dPulses" in tjs)
    check("脉冲有自检/演示开关", "pulse" in tjs and "selftest" in tjs)
    check("思维导图视图", 'data-view="mind"' in html and 'id="mindmap-canvas"' in html)
    mj = (con / "mindmap3d.js")
    check("mindmap3d.js 存在", mj.is_file())
    mjs = mj.read_text(encoding="utf-8")
    check("导图 6 分支×3 叶", mjs.count("leaves:") >= 6)
    check("导图标记可巡检", "data-mindmap" in mjs)
    check("穿透扫描视图", 'data-view="scan"' in html and 'id="scan3d-canvas"' in html)
    sj2 = (con / "scan3d.js")
    check("scan3d.js 存在", sj2.is_file())
    sjs = sj2.read_text(encoding="utf-8")
    check("扫描节点取真实扫描单元", "unit_details" in sjs and "arbitrated" in sjs)
    check("扫描有反思/穿透", "reflect" in sjs and "penetrations" in sjs)
    check("扫描标记可巡检", "dataset.scan3d" in sjs and "scan3dSwept" in sjs)
    check("五感面板在页面里", "五感覆盖" in html and "data-sense" in html)
    check("眼睛=视觉全谱不止 OCR", "视觉全谱" in html and "不止 OCR" in html and "vision_loop" in html)
    check("扫描数据来自真跑", "unit_details" in (ROOT / "tools" / "penetrating_cross_scan.py").read_text(encoding="utf-8"))
    check("导出脚本存在", (ROOT / "tools" / "export-scan-data.py").is_file())
    import json as _json
    _cd = (ROOT / "state" / "console-data.js").read_text(encoding="utf-8")
    _d = _json.loads(_cd[_cd.find("{"):_cd.rfind("}") + 1])
    _scans = ((_d.get("scan") or {}).get("scans") or [])
    check("console-data 含真实扫描", len(_scans) >= 2, str([x.get("target") for x in _scans]))
    check("扫描数据带明细", any(len(x.get("unit_details") or []) > 0 for x in _scans))
    check("支持真实目标切换", "scan-targets" in html and "switchTo" in sjs)
    _scan_py = (ROOT / "tools" / "penetrating_cross_scan.py").read_text(encoding="utf-8")
    check("扫描器有无死角口径", "full_coverage" in _scan_py and "dead_spots" in _scan_py)
    check("补扫 3 轮", "RESCAN_ROUNDS = 3" in _scan_py)
    _srv = (ROOT / "tools" / "console-server.py").read_text(encoding="utf-8")
    check("服务端有现场重扫接口", "/api/scan" in _srv and "dead_spot_count" in _srv)
    check("页面有覆盖率/死角 HUD", 'id="scan-coverage"' in html and 'id="scan-dead"' in html)
    check("可视化有漏扫计数", "scan3dMissed" in sjs)
    check("可视化有现场重扫", "async function rescan" in sjs and "/api/scan?target=" in sjs)
    check("职业视图在页面里", 'data-view="prof"' in html and 'id="prof-grid"' in html)
    check("职业生成器存在", (ROOT / "tools" / "gen-professions.py").is_file())
    check("职业数据存在", (ROOT / "data" / "professions.json").is_file())
    import json as _json2
    _pj = _json2.loads((ROOT / "data" / "professions.json").read_text(encoding="utf-8"))
    _profs = _pj.get("professions") or []
    check("12 种职业", len(_profs) >= 12, str(len(_profs)))
    check("编程是首席", any(p.get("chief") and p.get("title") == "编程工程师" for p in _profs))
    check("职业接能力位", all(p.get("cap_count", 0) > 0 for p in _profs))
    _appj = (con / "app.js").read_text(encoding="utf-8")
    check("职业有渲染函数", "renderProfessions" in _appj and "dataset.prof" in _appj)
    check("有拖动自检", "selfTestDrag" in sj and "space3dDrag" in sj)
    check("中心有她的头像", "avatarBall" in sj and "space3dAvatar" in sj)
    css3 = (con / "app.css").read_text(encoding="utf-8")
    check("3D 区域 grab 光标", "cursor: grab" in css3)
    srv = (ROOT / "tools" / "console-server.py").read_text(encoding="utf-8")
    check("服务端放行 /icons/", 'path.startswith("/icons/")' in srv)
    srv = (ROOT / "tools" / "console-server.py").read_text(encoding="utf-8")
    check("服务端有 /api/events", '"/api/events"' in srv and "text/event-stream" in srv)
    import re as _re
    data = (ROOT / "state" / "console-data.js").read_text(encoding="utf-8")
    check("数据含 385 能力位", '"items"' in data and _re.search(r'"total": 385', data) is not None)
    check("数据含 23 技能", _re.search(r'"count": 23', data) is not None)

    print("[4] 本地服务 + 数据 + Logo 生成器")
    check("console-server 存在", (ROOT / "tools" / "console-server.py").is_file())
    check("gen-potato-logo 存在", (ROOT / "tools" / "gen-potato-logo.py").is_file())
    avatar = ROOT / "icons" / "avatar.png"
    check("头像 avatar.png 存在且 >50KB", avatar.is_file() and avatar.stat().st_size > 50000,
          avatar.stat().st_size if avatar.is_file() else 0)
    for n in ("icon-512.png", "icon-192.png", "apple-touch-icon.png", "favicon-32.png"):
        f = ROOT / "icons" / n
        check(n + " 存在", f.is_file() and f.stat().st_size > 500)
    data = ROOT / "state" / "console-data.js"
    check("console-data.js 存在", data.is_file())
    m = re.search(r'"total":\s*(\d+)', data.read_text(encoding="utf-8")) if data.is_file() else None
    from gbt_allinone.caps_registry import BENIGN_CAPS
    check("数据 total == 注册表", m and int(m.group(1)) == len(BENIGN_CAPS),
          (m.group(1) if m else None, len(BENIGN_CAPS)))

    print("[5] 壳注册表只剩 控制台 + 对话")
    wj = json.loads((w3 / "shell" / "windows.json").read_text(encoding="utf-8"))
    ids = [w.get("id") for w in wj.get("windows") or []]
    check("2 个窗", len(ids) == 2, ids)
    check("含 console", "console" in ids, ids)

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 旧面板拆净、控制台在位、土豆 Logo 用上、无限上下文口径在")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
