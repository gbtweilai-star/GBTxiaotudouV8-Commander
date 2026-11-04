# -*- coding: utf-8 -*-
"""capability_router 验收：四类判准 / 自动调用万能插 / 门 / 真执行 / /api/chat 接线。

主人令 2026-11-02：「写 capability_router 接进 /api/chat：看屏幕、开网页、读写文件、看图四类，
自动调用万能插并验收」。

判据（每条都跑真的，不拿"文件存在"冒充验收）：
  ① 判类：四类各命中，四类之外不抢话，像提问的句子不擅自动手；
  ② 自动调用万能插：spy `api.run_task`，证明每次执行 kind=omni_plug（不是旁路脚本）；
  ③ 门在生效：非可信会话跑「看屏幕」⇒ denied + missing（万能插的作用域门真的挡）；
  ④ 真执行：写文件真落字节、读文件命中内容、看图真出 512x512 分析、看屏幕真取帧；
  ⑤ 开网页：本测试只验证"万能插 web 插座真驱动"（打桩浏览器记录 URL，不弹窗）；
     要真弹浏览器时设 GBT_ROUTER_TEST_WEB_OPEN=1；
  ⑥ /api/chat 接线：直接调 console-server 的 _chat，命中的句子回 via=capability_router。

跑法：python tests/test_capability_router.py
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import sys
import time
import webbrowser

ROOT = pathlib.Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(ROOT))

FAILED = []
TRUSTED_KEY = "GBT_OWNER_SESSION"
TEST_DIR = ROOT / "outputs" / "router-accept"


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)[:300]))
    if not cond:
        FAILED.append(name)


def main() -> int:
    os.environ["GBT_ENGINE_AUTOSTART"] = "0"
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    from gbt_allinone import capability_router as CR
    from gbt_allinone import api as API

    print("[0] 模块自述 / 四类齐")
    caps = CR.capabilities()
    check("自述 ok", caps.get("ok") is True)
    check("四类齐", [x.get("intent") for x in caps.get("intents") or []]
          == ["screen", "web", "file", "image"], caps.get("intents"))
    check("执行器 = 万能插唯一门", "omni_plug" in (caps.get("executor") or ""))
    check("不新增能力位（router 不在注册表）",
          "capability_router" not in __import__("gbt_allinone.caps_registry",
                                                fromlist=["BENIGN_CAPS"]).BENIGN_CAPS)

    print("[1] 判类（纯文本，不执行）")
    cases = [
        ("帮我看看屏幕", "screen", "see"),
        ("截个屏发我", "screen", "see"),
        ("打开 https://example.com", "web", "open"),
        ("开网页 example.com", "web", "open"),
        ("读文件 outputs/router-accept/demo.txt", "file", "read"),
        ("打开文件 outputs/router-accept/demo.txt", "file", "read"),
        ("写文件 outputs/router-accept/demo.txt 内容 你好，万能插", "file", "write"),
        ("把 验收通过 保存到 outputs/router-accept/demo.txt", "file", "write"),
        ("看图 icons/avatar.png", "image", "view"),
        ("看看这张图 icons/avatar.png", "image", "view"),
    ]
    bad = []
    for text, intent, action in cases:
        r = CR.classify(text)
        if r.get("intent") != intent or r.get("action") != action or r.get("error"):
            bad.append((text, r.get("intent"), r.get("action"), r.get("error")))
    check("10 例判类全中", not bad, bad)

    print("[1b] 不抢话 / 不擅自动手 / 缺目标如实报")
    for text in ("你好，你是谁", "今天天气怎么样", "帮我写一首诗", "记住这件事"):
        r = CR.classify(text)
        check("四类之外 handled=False：" + text[:10], r.get("intent") == "", r.get("intent"))
    r = CR.classify("你会看屏幕吗？")
    check("提问句不擅自动手", r.get("intent") == "" and r.get("question") is True,
          (r.get("intent"), r.get("question")))
    r = CR.classify("开网页")
    check("开网页缺网址 ⇒ user_error", r.get("intent") == "web" and "url" in (r.get("missing") or [])
          and "user_error" in (r.get("error") or ""), r.get("error"))
    r = CR.classify("写文件 outputs/router-accept/x.txt")
    check("写文件缺内容 ⇒ user_error", "content" in (r.get("missing") or [])
          and "user_error" in (r.get("error") or ""), r.get("error"))
    r = CR.classify("看图 notes.md")
    check("看图给了非图片 ⇒ user_error", "image_file" in (r.get("missing") or [])
          and "user_error" in (r.get("error") or ""), r.get("error"))
    res = CR.run("开网页")
    check("缺网址 run 也如实回、不调万能插", res.get("handled") is True
          and res.get("ok") is False and "call" not in res, res.get("error"))

    print("[1c] 独立验收回归（F1 读→写 / F2 占位正文 / F3 URL 抢类 / F5 含空格路径 / F7 语义白名单）")
    _f1 = [CR.classify(t) for t in (
        "读文件 outputs/router-accept/demo.txt 里写的结论",
        "把 outputs/router-accept/demo.txt 里写的结论发给我",
        "总结一下 outputs/router-accept/demo.txt 里写的结论")]
    check("F1 读里带「写」字仍是 read（不是覆盖写）",
          all(x.get("intent") == "file" and x.get("action") == "read" for x in _f1),
          [(x.get("action"), x.get("error")) for x in _f1])
    _f1b = CR.classify("把 outputs/router-accept/a.txt 里的内容保存到 outputs/router-accept/b.txt")
    check("F1b 多路径/复制写不猜目标（如实拒）",
          _f1b.get("action") == "write"
          and (set(_f1b.get("missing") or []) & {"single_target", "copy_unsupported"})
          and "user_error" in (_f1b.get("error") or ""), _f1b)
    _ph = [CR.classify(t) for t in (
        "把这段文字存到 outputs/router-accept/placeholder.txt",
        "把上面的内容存到 outputs/router-accept/placeholder2.txt")]
    check("F2 占位词不当正文（如实报缺内容）",
          all("content" in (x.get("missing") or []) and "user_error" in (x.get("error") or "")
              for x in _ph), [_clean for _clean in (_ph[0].get("error"), _ph[1].get("error"))])
    r = CR.classify("把这段文字存到 outputs/router-accept/x.txt 内容 123")
    check("F2b 内容标记优先于指代词",
          r.get("action") == "write" and r.get("write_text") == "123", r.get("write_text"))
    r = CR.classify("读文件 outputs/router-accept/demo.txt 里 https://example.com 那段")
    check("F3 读文件不被句中 URL 抢去开浏览器",
          r.get("intent") == "file" and r.get("action") == "read", r)
    r = CR.classify("https://example.com")
    check("F3b 只贴一条链接不擅自动手", r.get("intent") == "", r)
    spaced = "C:/Users/Lenovo E14 Gen 5/Desktop/GBT小土豆V8/icons/avatar.png"
    r = CR.classify("看图 " + spaced)
    check("F5 含空格的绝对路径完整取到",
          r.get("intent") == "image" and r.get("target") == spaced, r.get("target"))
    try:
        CR.build_call({"intent": "image", "target": "fake.png",
                       "target_abs": "C:\\Windows\\System32\\whoami.exe"})
        bad7 = False
    except ValueError:
        bad7 = True
    check("F7 非图片 target 拒绝拼 payload", bad7)
    r = CR.execute({"intent": "image", "target": "fake.png",
                    "target_abs": "C:\\Windows\\System32\\whoami.exe"})
    check("F7 execute 不派发（不把 whoami 当看图跑）",
          r.get("handled") is True and r.get("ok") is False and "call" not in r, r.get("error"))
    _n1 = [CR.classify(t) for t in (
        "写 outputs/router-accept/n1.txt 内容 裸写",
        "保存 outputs/router-accept/n1.txt 内容 裸写",
        "新建 outputs/router-accept/n1.txt 内容 裸写")]
    check("N1 句首裸写动词仍判 write（不是 read）",
          all(x.get("action") == "write" and x.get("write_text") for x in _n1),
          [(x.get("action"), x.get("write_text")) for x in _n1])
    _n2 = CR.classify("看一下文件 outputs/router-accept/demo.txt")
    check("N2 看一下文件 X ⇒ file/read",
          _n2.get("intent") == "file" and _n2.get("action") == "read", _n2)
    _n3 = CR.classify("写文件 outputs/router-accept/a.txt 内容 参考 projects/b.txt")
    check("N3 正文里的路径不算目标冲突",
          _n3.get("action") == "write" and _n3.get("write_text") == "参考 projects/b.txt",
          _n3.get("error") or _n3.get("write_text"))

    print("[2] payload 白名单（只有四种形状）")
    for text, kind, sock, do in (
            ("看屏幕", "run", "app", "see"),
            ("打开 https://example.com", "run", "web", "open"),
            ("读文件 outputs/router-accept/demo.txt", "run", "file", "read"),
            ("写文件 outputs/router-accept/demo.txt 内容 x", "run", "file", "write"),
            ("看图 icons/avatar.png", "universal", None, "view")):
        route = CR.classify(text)
        payload = CR.build_call(route)
        check("payload %s" % text[:8],
              payload.get("op") == kind
              and (sock is None or payload.get("socket") == sock)
              and str(payload.get("do")) == do, payload)
    try:
        CR.build_call({"intent": "process", "target": "whoami"})
        check("白名单拒绝第五类", False)
    except ValueError:
        check("白名单拒绝第五类", True)

    print("[3] 每次执行 kind=omni_plug（spy run_task）+ 门在生效")
    seen = []
    orig_run_task = API.run_task

    def _spy(kind, payload=None, **kw):
        seen.append((kind, dict(payload or {})))
        return orig_run_task(kind, payload, **kw)

    old_trusted = os.environ.pop(TRUSTED_KEY, None)
    try:
        API.run_task = _spy
        denied = CR.run("看屏幕")
        check("非可信会话：拒绝", denied.get("ok") is False and denied.get("denied") is True,
              (denied.get("error"), denied.get("missing")))
        missing = [str(x) for x in (denied.get("missing") or [])]
        check("缺的作用域如实点名（读屏隐私门）",
              bool(set(missing) & {"privacy_read", "desktop_control"}), missing)
        check("被拒也走的是万能插（spy 记到 kind=omni_plug）",
              bool(seen) and seen[-1][0] == "omni_plug", seen[-1:] if seen else None)

        print("[4] 真执行（可信主人会话 = 桌面版口径）")
        os.environ[TRUSTED_KEY] = "1"
        seen.clear()
        API.run_task = _spy

        r = CR.run("写文件 outputs/router-accept/demo.txt 内容 你好，万能插")
        target = TEST_DIR / "demo.txt"
        check("写文件经万能插 ok", r.get("ok") is True and r.get("handled") is True,
              r.get("error") or r.get("capability"))
        check("写文件真落盘且字节对得上",
              target.is_file() and target.read_text(encoding="utf-8") == "你好，万能插",
              target.read_text(encoding="utf-8") if target.is_file() else "not found")
        check("写文件回执带 wrote_bytes",
              (r.get("capability") or {}).get("wrote_bytes") ==
              len("你好，万能插".encode("utf-8")), (r.get("capability") or {}).get("wrote_bytes"))

        r = CR.run("写文件 outputs/router-accept/new/deep/nested.txt 内容 新目录真能建")
        nf = ROOT / "outputs" / "router-accept" / "new" / "deep" / "nested.txt"
        check("F4 新目录写文件（父目录不在也放行）",
              r.get("ok") is True and nf.is_file(), r.get("error") or str(nf))

        r = CR.run("看图 outputs/router-accept/nope.png")
        check("F6 看图目标不存在 ⇒ 结构化报缺（不当命令跑）",
              r.get("ok") is False and "不存在" in str((r.get("capability") or {}).get("evidence") or ""),
              r.get("capability"))

        r = CR.run("读文件 outputs/router-accept/demo.txt")
        read = str((r.get("capability") or {}).get("read") or "")
        check("读文件经万能插 ok", r.get("ok") is True, r.get("error"))
        check("读回执命中内容", "你好，万能插" in read, read[:80])

        r = CR.run("看图 icons/avatar.png")
        inner = (r.get("capability") or {}).get("result") or {}
        check("看图经万能插 ok", r.get("ok") is True and inner.get("ok") is True,
              r.get("error") or (r.get("capability") or {}).get("evidence"))
        check("看图真出尺寸 512x512", inner.get("size") == [512, 512], inner.get("size"))
        check("看图回执带亮度/对比度",
              inner.get("brightness") is not None and inner.get("contrast") is not None,
              inner)

        r = CR.run("帮我看看屏幕")
        look = (r.get("capability") or {}).get("看") or {}
        check("看屏幕经万能插 app 插座", r.get("call", {}).get("payload", {}).get("socket") == "app",
              r.get("call"))
        # 采集是环境依赖：取到帧算绿；取不到必须是**结构化如实拒绝**（不许冒充成功）
        check("看屏幕：取到帧或如实报不可用",
              (r.get("ok") is True and bool(look.get("size")))
              or (bool(look.get("why")) and bool(look.get("missing"))),
              {"ok": r.get("ok"), "look": look, "error": r.get("error")})

        print("[5] 开网页：万能插 web 插座真驱动（打桩浏览器，不弹窗）")
        opened = []
        real_open = webbrowser.open
        try:
            webbrowser.open = lambda url, *a, **k: (opened.append(url), True)[1]
            r = CR.run("打开 https://example.com")
        finally:
            webbrowser.open = real_open
        check("web 插座 ok", r.get("ok") is True, r.get("error"))
        check("真把 URL 交给浏览器（记录到 example.com）",
              opened == ["https://example.com"], opened)
        check("回执带 backend", (r.get("capability") or {}).get("backend")
              == "system-default-browser", r.get("capability"))
        if os.environ.get("GBT_ROUTER_TEST_WEB_OPEN") == "1":
            r = CR.run("打开 https://example.com")
            check("真弹浏览器（opt-in）", r.get("ok") is True, r.get("error"))

        check("全部真执行都经 omni_plug（spy 计数）",
              len(seen) >= 5 and all(k == "omni_plug" for k, _ in seen), seen[:2])
    finally:
        API.run_task = orig_run_task
        if old_trusted is None:
            os.environ.pop(TRUSTED_KEY, None)
        else:
            os.environ[TRUSTED_KEY] = old_trusted

    print("[6] /api/chat 接线（真调 console-server 的 _chat，不经过模型）")
    srv = ROOT / "tools" / "console-server.py"
    src = srv.read_text(encoding="utf-8")
    check("/api/chat 前先过 capability_router", "capability_router as _CR" in src
          and "_CR.run(" in src and "handled" in src)
    check("有开关（body capability / env）", 'capability") is not False' in src
          and "GBT_CAPABILITY_ROUTER" in src)
    spec = importlib.util.spec_from_file_location("console_server_under_test", srv)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    r = mod._chat("读文件 outputs/router-accept/demo.txt")
    check("_chat 命中四类 ⇒ via=capability_router", r.get("via") == "capability_router"
          and r.get("intent") == "file", {k: r.get(k) for k in ("via", "intent", "error")})
    check("_chat 回执带万能插 call", (r.get("call") or {}).get("kind") == "omni_plug", r.get("call"))
    # 「关掉路由就回对话模型」这条要真调一次 _chat；模型侧用桩（不烧算力、不联网），
    # 只验“分派真的分流了”，不冒充模型回答。
    from gbt_allinone import omni_plug as _OP
    from gbt_allinone import energy_core as _EC
    _orig_plug, _orig_think = _OP.plug_and_run, _EC.think
    try:
        _OP.plug_and_run = lambda *a, **k: {"ok": False, "error": "test-stub"}
        _EC.think = lambda *a, **k: {"ok": True, "text": "（测试桩：走对话模型）", "ms": 1}
        r2 = mod._chat("读文件 outputs/router-accept/demo.txt", use_capabilities=False)
    finally:
        _OP.plug_and_run, _EC.think = _orig_plug, _orig_think
    check("关掉路由 ⇒ 不返回 capability_router（回到对话模型）",
          r2.get("via") != "capability_router" and "测试桩" in str(r2.get("text")),
          {k: r2.get(k) for k in ("via", "text", "error")})

    print()
    # 验收产物自己清掉（不把 outputs/ 弄脏；测试可复跑、每次自己重建）
    try:
        import shutil
        shutil.rmtree(TEST_DIR, ignore_errors=True)
    except Exception:  # noqa: BLE001
        pass
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 四类判准、每次执行都走万能插、门在挡、文件/图/屏真跑、/api/chat 已接线")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

