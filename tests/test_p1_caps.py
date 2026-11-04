# -*- coding: utf-8 -*-
"""P1 验收：world_forge / pentest_flow 注册成能力位 + 接万能插 + 各自 P1 增量。

判据只认真跑：
  ① 注册：两件都在 BENIGN_CAPS，api 分派可达（run_task 统一门 = 万能插门）；
  ② 零作用域：policy.evaluate 对两件返回 scopes=() / restricted=False（不新增攻击面）；
  ③ 世界 P1：spec（一句话→规格，可复现/夹紧）、encode/decode 存档对账与防篡改、view3d 数据面；
  ④ 渗透 P1：surface（源码攻击面图：路由/输入源/危险汇点/信任边界/候选）、
     agent_plan（五类派单 + PoC 契约）、agent_ingest（只让有 PoC 的进 exploited）；
  ⑤ 接线：console-server 有 /api/world；console 有「世界」视图 + 万能插四类快捷条。

跑法：python tests/test_p1_caps.py
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(ROOT))

FAILED = []

FILES = {"server.js": "app.get('/user', (req,res)=>{ const q=req.query.q; res.send(q); "
                      "document.body.innerHTML=q; eval(req.query.code); fetch(req.query.url); });\n"
                      "app.get('/admin/users', (req,res)=>{ res.send('x'); });"}


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)[:300]))
    if not cond:
        FAILED.append(name)


def main() -> int:
    from gbt_allinone import api
    from gbt_allinone.caps_registry import BENIGN_CAPS
    from gbt_allinone.security import policy
    from gbt_allinone.tools import pentest_flow as PF
    from gbt_allinone.tools import world_forge as WF

    print("[1] 注册成能力位")
    for name, domain in (("world_forge", "engine"), ("pentest_flow", "security")):
        cap = BENIGN_CAPS.get(name)
        check("%s 在注册表" % name, isinstance(cap, dict), cap)
        check("%s domain=%s" % (name, domain), (cap or {}).get("domain") == domain)
        check("%s safe=True（零作用域）" % name, (cap or {}).get("safe") is True)
    names = [c.get("name") for c in api.list_capabilities()]
    check("world_forge 出现在能力清单", "world_forge" in names)
    check("pentest_flow 出现在能力清单", "pentest_flow" in names)

    print("[2] 零作用域（不新增攻击面）")
    for name in ("world_forge", "pentest_flow"):
        d = policy.evaluate(name, {"op": "schema"})
        check("%s scopes=()" % name, tuple(getattr(d, "scopes", ())) == (), getattr(d, "scopes", None))
        check("%s restricted=False" % name, getattr(d, "restricted", None) is False,
              getattr(d, "restricted", None))

    print("[3] 万能插唯一门分派（run_task）")
    r1 = api.run_task("world_forge", {"op": "schema"}, safe=True)
    blob1 = json.dumps(r1, ensure_ascii=False)
    check("run_task world_forge ok", r1.get("ok") is True)
    check("分发到 world_forge（回执里有名字）", "world_forge" in blob1)
    r2 = api.run_task("world_forge", {"op": "spec", "prompt": "海边的三个文明，每国两座城，体素世界"},
                      safe=True)
    blob2 = json.dumps(r2, ensure_ascii=False)
    check("run_task world_forge op=spec 可达", r2.get("ok") is True and '"civs":3' in blob2.replace(" ", ""),
          blob2[:200])
    r3 = api.run_task("pentest_flow", {"op": "schema"}, safe=True)
    check("run_task pentest_flow ok", r3.get("ok") is True and "pentest_flow" in json.dumps(r3))
    r4 = api.run_task("pentest_flow", {"op": "scope", "engagement": {}}, safe=True)
    blob4 = json.dumps(r4, ensure_ascii=False)
    check("run_task pentest_flow op=scope fail-closed 可达", r4.get("ok") is True and "authorization_ref" in blob4,
          blob4[:200])

    print("[4] 世界 P1：一句话 → 规格")
    sp = WF.spec_from_prompt("海边的三个文明，每国两座城，体素世界")
    check("spec 出规格", sp.get("ok") is True and sp["spec"]["civs"] == 3
          and sp["spec"]["cities_per_civ"] == 2, sp.get("matched"))
    check("spec 命中词可读", "文明数" in (sp.get("matched") or []) and "体素" in (sp.get("matched") or []),
          sp.get("matched"))
    check("spec 夹紧在边界内", sp["spec"]["water_level"] <= 0.8 and sp["spec"]["civs"] <= 8)
    check("spec 可复现（同句同规格）",
          WF.spec_from_prompt("海边的三个文明，每国两座城，体素世界")["spec"] == sp["spec"])
    sp2 = WF.spec_from_prompt("沙漠里的两个国家，不要3d，seed=42")
    check("spec 沙漠/二维/seed 都认", sp2["spec"]["warmth"] == 0.7
          and sp2["spec"]["voxel"] is False and sp2["spec"]["seed"] == 42, sp2["spec"])

    print("[5] 世界 P1：存档 encode/decode")
    w = WF.gen({"seed": 7, "width": 12, "height": 12, "civs": 2, "cities_per_civ": 2})
    enc = WF.encode(w)
    check("encode 出 sha256/bytes", enc["ok"] and len(enc["sha256"]) == 64 and enc["bytes"] > 0)
    dec = WF.decode(enc["json"], expect_sha256=enc["sha256"])
    check("decode 对账 ok", dec.get("ok") is True, dec.get("error"))
    check("decode 后世界 hash 一致", WF.state_hash(dec["world"]) == WF.state_hash(w))
    tampered = enc["json"].replace('"seed":7', '"seed":8')
    check("被改过的存档拒载", WF.decode(tampered, expect_sha256=enc["sha256"]).get("ok") is False)
    check("坏格式存档拒载", WF.decode('{"format":"nope"}').get("ok") is False)

    print("[6] 世界 P1：view3d 数据面")
    v3 = WF.view3d(w)
    check("view3d ok", v3.get("ok") is True)
    check("列数 = 宽×高", len(v3["columns"]) == w["spec"]["width"] * w["spec"]["height"],
          (len(v3["columns"]), w["spec"]["width"] * w["spec"]["height"]))
    check("城市/文明带上", len(v3["cities"]) == len(w["cities"]) and len(v3["civs"]) == len(w["civs"]))
    check("palette 有生物群系颜色", set(v3["palette"]) >= {"ocean", "grass", "mountain"})
    check("体素层计数带齐", len(v3["layer_counts"]) == len(w["voxels"]), list(v3["layer_counts"])[:3])
    r5 = api.run_task("world_forge", {"op": "view3d", "spec": {"seed": 7, "width": 12, "height": 12}},
                      safe=True)
    check("run_task op=view3d 可达", r5.get("ok") is True and "columns" in json.dumps(r5))

    print("[7] 渗透 P1：源码攻击面图")
    sf = PF.surface(FILES)
    check("surface ok", sf.get("ok") is True)
    check("拍出路由", len(sf["routes"]) >= 2, [r["path"] for r in sf["routes"]])
    cats = {c["category"] for c in sf["candidates"]}
    check("候选含 XSS/注入/SSRF", {"xss", "injection", "ssrf"} <= cats, sorted(cats))
    check("有 source→sink 信任边界", len(sf["trust_boundaries"]) >= 2, len(sf["trust_boundaries"]))
    check("候选带 file:line 证据",
          all(c.get("file") and c.get("line") and "surface:" in (c.get("evidence") or "")
              for c in sf["candidates"]), sf["candidates"][:1])
    check("surface 非映射入参如实拒", PF.surface("not-a-dict").get("ok") is False)

    print("[8] 渗透 P1：五类派单 + validate 闸")
    rec = PF.reconcile([], sf["candidates"])
    plan = PF.agent_plan(rec["queue"])
    agents = [a["agent"] for a in plan["agents"]]
    check("五类代理齐", agents == ["Injection", "XSS", "SSRF", "Auth", "AuthZ"], agents)
    check("每类带 PoC 契约", all("proof_contract" in a for a in plan["agents"]))
    check("任务数 = 队列数", sum(plan["counts"].values()) == len(rec["queue"]),
          (plan["counts"], len(rec["queue"])))
    good = {"candidate": sf["candidates"][0], "proof": {
        "reproduced": True, "request": "GET /user?q=1 HTTP/1.1",
        "response_evidence": "200 reflected", "steps": ["curl"]}}
    bad = {"candidate": sf["candidates"][1], "proof": None}
    ing = PF.agent_ingest([good, bad])
    check("agent_ingest 只让有 PoC 的 exploited",
          ing["exploited"] == 1 and ing["dropped"] == 1, (ing["exploited"], ing["dropped"]))
    only = PF.agent_ingest([bad])
    check("无 PoC 全 dropped（不冒充成功）", only["exploited"] == 0 and only["dropped"] == 1)
    rep = PF.report(ing["findings"], {"id": "ENG", "authorization_ref": "主人授权",
                                      "scope": ["https://staging.example.com"]})
    check("报告只收 exploited", rep["counts"]["exploited"] == 1 and rep["counts"]["dropped"] == 1)
    check("SARIF 2.1.0 只 1 条", rep["sarif"]["version"] == "2.1.0"
          and len(rep["sarif"]["runs"][0]["results"]) == 1)

    print("[9] 接线：APP/服务端/控制台")
    srv = (ROOT / "tools" / "console-server.py").read_text(encoding="utf-8")
    check("console-server 有 /api/world", '"/api/world"' in srv and "world_forge" in srv)
    idx = (ROOT / "holo_pet_w3" / "console" / "index.html").read_text(encoding="utf-8")
    check("console 有「世界」页签", 'data-view="world"' in idx and 'id="world3d-canvas"' in idx)
    check("console 有万能插四类快捷条", 'id="cap-quick"' in idx
          and idx.count('class="cap-chip"') == 4, idx.count('class="cap-chip"'))
    appjs = (ROOT / "holo_pet_w3" / "console" / "app.js").read_text(encoding="utf-8")
    check("app.js 有世界视图加载器", "ensureWorld" in appjs and 'import("./world3d.js")' in appjs)
    check("app.js 有快捷条接线", "CAP_TEMPLATES" in appjs and "cap-quick" in appjs)
    check("world3d.js 存在且用 /api/world", (ROOT / "holo_pet_w3" / "console" / "world3d.js").is_file()
          and "/api/world" in (ROOT / "holo_pet_w3" / "console" / "world3d.js").read_text(encoding="utf-8"))
    check("view3d 数据面不自带攻击面", "fetch(" in (ROOT / "holo_pet_w3" / "console" / "world3d.js")
          .read_text(encoding="utf-8") and '"view3d"' in (ROOT / "holo_pet_w3" / "console" / "world3d.js")
          .read_text(encoding="utf-8"))
    check("app.js 状态自愈（自动重读 /api/data，引擎晚起不死在离线快照）",
          "wireAutoRefresh" in appjs and "loadData(true)" in appjs
          and "window.addEventListener(\"focus\"" in appjs)
    check("console 有「浏览器」页签 / 内嵌 webview",
          'data-view="browser"' in idx and 'id="gbt-webview"' in idx
          and 'id="bw-url"' in idx)
    check("app.js 有内置浏览器接线（地址栏/前进后退/加载失败兜底）",
          all(k in appjs for k in ("ensureBrowser", "gbt-webview", "bw-url",
                                   "did-fail-load", "bwNative")))
    check("console-server 有 /api/browser 原生入口",
          '"/api/browser"' in srv and "native" in srv)
    css4 = (ROOT / "holo_pet_w3" / "console" / "app.css").read_text(encoding="utf-8")
    check("css 有内置浏览器视图样式", "gbt-browser" in css4 and ".bw-url" in css4)
    check("原生浏览器条有「AI 读当前页」（get_text 接线）",
          'id="bw-native-read"' in idx and "bw-native-read" in appjs
          and "get_text" in appjs)

    print("[9b] 对话 + 号附图（后端本地视觉读数 + 前端接线）")
    import base64
    import importlib.util as _ilu
    os.environ["GBT_ENGINE_AUTOSTART"] = "0"
    data_url = "data:image/png;base64," + base64.b64encode(
        (ROOT / "icons" / "avatar.png").read_bytes()).decode()
    _spec = _ilu.spec_from_file_location(
        "console_server_img_test", ROOT / "tools" / "console-server.py")
    sm = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(sm)
    r = sm._chat("", image=data_url)
    check("附图无文字 ⇒ 本地视觉读数",
          r.get("ok") is True and r.get("via") == "vision:local"
          and "512x512" in (r.get("text") or ""), r.get("text"))
    r = sm._chat("看看这张图", image=data_url)
    check("附图问图 ⇒ 本地视觉读数",
          r.get("ok") is True and r.get("via") == "vision:local"
          and "亮度" in (r.get("text") or ""), r.get("text"))
    r = sm._chat("", image="data:image/png;base64,badbadbad")
    check("坏图如实报错（不冒充看见）",
          r.get("ok") is False and "读取失败" in (r.get("text") or ""), r.get("text"))
    srv2 = (ROOT / "tools" / "console-server.py").read_text(encoding="utf-8")
    check("console-server 接 image 入参", 'image=body.get("image")' in srv2
          and "chat_image" in srv2 and "需要 text / image / file" in srv2)
    appjs2 = (ROOT / "holo_pet_w3" / "console" / "app.js").read_text(encoding="utf-8")
    check("app.js 有 + 号附图接线（选图/粘贴/预览/发送）",
          all(k in appjs2 for k in ("setAttach", 'chat-attach', "chat-file",
                                     "readAsDataURL", "msg-attach", "kind === \"image\"")))
    css2 = (ROOT / "holo_pet_w3" / "console" / "app.css").read_text(encoding="utf-8")
    check("app.css 有附图预览样式", all(k in css2 for k in (".attach-thumb", ".msg-attach",
                                                              ".chat-attach-preview")))
    check("chat_image 模块存在", (ROOT / "gbt_allinone" / "chat_image.py").is_file())

    print("[9c] 对话「发送文件」入口（后端本地解析 + 前端接线）")
    import base64 as _b64

    def _du(b, mime):
        return "data:%s;base64,%s" % (mime, _b64.b64encode(b).decode())

    txt_du = _du("# 标题\n内容行\n".encode(), "text/markdown")
    r = sm._chat("", file=txt_du, file_name="note.md", file_type="text/markdown")
    check("文本文件 ⇒ 本地解析（前 N 字）",
          r.get("ok") is True and r.get("via") == "file:text"
          and "文本附件" in (r.get("text") or ""), r.get("text"))
    r = sm._chat("总结这个文件", file=txt_du, file_name="note.md")
    check("文件问句 ⇒ 本地解析（不走模型瞎猜）",
          r.get("ok") is True and r.get("via") == "file:text", r.get("via"))
    r = sm._chat("", file=_du(b"\x00\x01zipdata", "application/zip"), file_name="a.zip")
    check("二进制 ⇒ 只报元数据（不假装解析）",
          r.get("ok") is True and r.get("via") == "file:binary"
          and "二进制附件" in (r.get("text") or ""), r.get("text"))
    r = sm._chat("", file="data:application/octet-stream;base64,@@@", file_name="bad.bin")
    check("坏附件如实报错", r.get("ok") is False and "读取失败" in (r.get("text") or ""),
          r.get("text"))
    appjs3 = (ROOT / "holo_pet_w3" / "console" / "app.js").read_text(encoding="utf-8")
    check("app.js 有文件入口接线",
          all(k in appjs3 for k in ("chat-attach-file", "chat-upload", "setAttach(f, \"file\")",
                                     "file: (_att", "file_name: (_att")))
    idx3 = (ROOT / "holo_pet_w3" / "console" / "index.html").read_text(encoding="utf-8")
    check("index 有文件按钮/隐藏输入",
          'id="chat-attach-file"' in idx3 and 'id="chat-upload"' in idx3)
    css3 = (ROOT / "holo_pet_w3" / "console" / "app.css").read_text(encoding="utf-8")
    check("css 有文件入口/附件样式", ".file-btn" in css3 and ".msg-file" in css3)
    check("chat_file 模块存在", (ROOT / "gbt_allinone" / "chat_file.py").is_file())

    print("[10] 模块自检仍全绿")
    vw = WF.verify()
    vp = PF.verify()
    check("world_forge 自检全绿", vw.get("ok") is True and len(vw.get("checks") or []) >= 19,
          vw.get("failed"))
    check("pentest_flow 自检全绿", vp.get("ok") is True and len(vp.get("checks") or []) >= 28,
          vp.get("failed"))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 两件能力位已注册+接万能插、零作用域、世界/渗透 P1 与 APP 接线全绿")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
