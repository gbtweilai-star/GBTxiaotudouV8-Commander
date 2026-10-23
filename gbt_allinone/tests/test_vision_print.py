# -*- coding: utf-8 -*-
"""vision_print（视觉打印）· 判据件。

跑法（与仓里其它判据同族）：

    py -3.14 -m unittest gbt_allinone.tests.test_vision_print -v

## 这个判据件在测什么、不测什么（写清，免得被当成"全绿"读）

- **测**：① 契约面（status/where/未知 op fail-closed）② `print` 无码必须 fail-closed
  ③ **判定层的尺子**（同图 ⇒ 同款；差得远 ⇒ 不像；只改一处文字颜色 ⇒ 不许是"同款"）
  ④ 真渲染那条腿（本机有 Chromium/Edge 时：渲出来零出网、五段链成"同款"、换个页面成"不像"）。
- **不测**：`op=ask_model`（要过 `external_llm` 门 + 花外部模型，判据件一律不跑）。
- **隔离**：产物写进临时目录（`GBT_VISION_PRINT_OUT`），账写进临时 store（`GBT_STORE_DIR`）
  —— 判据件**不许往产物区/真账本里丢东西**。

前提：`tentacle/vision_bus`（尺子）与 `PIL` 在位；浏览器那条腿单独 `skipUnless` 守着
（不在就**明说跳过**，绝不假装跑过）。

🔴 **`GBT_STORE_DIR` 必须在起 Python 之前设**（仓里 `gbt_allinone/tests/__init__.py` 的哨兵：
import 包那一刻就把 store 绑死了，晚设一律拒跑）：

    PowerShell:  $env:GBT_STORE_DIR="$env:TEMP\\gbt_test_store"; py -3.14 -m unittest gbt_allinone.tests.test_vision_print -v
"""
import base64
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_TMP = tempfile.TemporaryDirectory(prefix="gbt-vision-print-test-")
os.environ["GBT_VISION_PRINT_OUT"] = str(Path(_TMP.name) / "out")
# ⚠️ 这里**故意不设** `GBT_STORE_DIR`：起 Python 之前就得设好（见文件头），
#    在这里设已经晚了 —— 包装 import 时就绑定了 store。

from gbt_allinone.tools import vision_print as VP   # noqa: E402


def _browser_ok() -> bool:
    try:
        from playwright.sync_api import sync_playwright   # noqa: F401
        return True
    except Exception:                                     # noqa: BLE001
        return False


def _png(w=240, h=160, rgb=(11, 11, 20)) -> str:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), rgb).save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _textured(bg, fg, w=200, h=140) -> str:
    """带纹理的图（**必须有纹理**：整图 aHash 对纯色图会失明，见下面对应的判据）。"""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    for i in range(0, w, 20):
        d.line([(i, 0), (i, h)], fill=fg, width=3)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


_PAGE_A = ("<!doctype html><html><head><meta charset='utf-8'><style>"
           "body{background:#0B0B14;color:#EDEDF5;margin:0}"
           ".t{height:44px;background:#F5B041}"
           "h1{color:#00E5FF;margin:24px}</style></head><body>"
           "<div class='t'></div><h1>视觉打印 判据页</h1></body></html>")
_PAGE_B = _PAGE_A.replace("#00E5FF", "#FF6B6B")          # 只改一处文字颜色
_PAGE_C = ("<!doctype html><html><head><meta charset='utf-8'><style>"
           "body{background:#F2F2F2;color:#111;margin:0}"
           ".c{height:120px;background:#FFF;border:1px solid #CCC;margin:12px}"
           "</style></head><body><div class='c'></div><div class='c'></div></body></html>")


class TestVisionPrintContract(unittest.TestCase):
    """契约面（不碰浏览器、不碰屏幕）。"""

    def test_status_surface(self):
        st = VP.run("status")
        self.assertTrue(st["ok"], st)
        self.assertEqual(st["stages"], ["see", "print", "render", "diff", "judge"])
        self.assertTrue(st["ruler_present"], "尺子（tentacle.vision_bus）必须在位")

    def test_where_lists_all_ops(self):
        wh = VP.run("where")
        self.assertTrue(wh["ok"])
        for op in ("see", "print", "diff", "loop", "ask_model", "status", "where"):
            self.assertIn(op, wh["ops"])

    def test_unknown_op_fail_closed(self):
        r = VP.run("并没有这个 op")
        self.assertFalse(r["ok"], "未知 op 必须 fail-closed")
        self.assertTrue(r["fail_closed"])

    def test_print_without_code_fail_closed(self):
        r = VP.run("print")
        self.assertFalse(r["ok"], "没给码就不许渲")
        self.assertTrue(r["fail_closed"])
        self.assertEqual(r["status"], "needs_params")

    def test_diff_needs_two_images(self):
        r = VP.run("diff")
        self.assertFalse(r["ok"])
        self.assertTrue(r["fail_closed"])


class TestVisionPrintRuler(unittest.TestCase):
    """判定层的尺子（PIL 合成图，不碰浏览器）。"""

    def test_same_image_is_tongkuan(self):
        a = _png()
        d = VP.run("diff", a=a, b=a)
        self.assertEqual(d["verdict"], "同款", d)
        self.assertEqual(d["aHash距离"], 0)
        self.assertTrue(d["尺度一致"], d)

    def test_far_image_is_buxiang(self):
        d = VP.run("diff", a=_textured((11, 11, 20), (0, 229, 255)),
                   b=_textured((242, 242, 242), (17, 17, 17)))
        self.assertEqual(d["verdict"], "不像", d)
        self.assertTrue(d["尺度一致"], d)

    def test_flat_images_blind_the_global_ruler_but_never_the_verdict(self):
        """🔴 **整图 aHash 对纯色图失明**（实测：纯黑 vs 纯白 ⇒ aHash 距离 0 ⇒ 全局档『同款』）。

        这条不是"测试挑刺"，是**真实盲区**：aHash 是"像素 > 均值"二值化，
        纯色图里**没有像素高于均值** ⇒ 两边都变成全 0 串 ⇒ 距离 0。
        ⇒ 所以：① verdict 取两把尺子**更严**的那个（这里 局部档 判『不像』⇒ 结论 不像）；
              ② `尺度一致=false` 必须如实报出来，不许把这种"整屏看着一样"念成"还原成功"。
        """
        d = VP.run("diff", a=_png(rgb=(0, 0, 0)), b=_png(rgb=(255, 255, 255)))
        self.assertEqual(d["verdict"], "不像", "纯黑 vs 纯白 必须是 不像：%s" % d)
        self.assertEqual(d["全局档"], "同款", "记录盲区：全局尺子在这里会失明：%s" % d)
        self.assertNotEqual(d["局部档"], "同款", d)
        self.assertFalse(d["尺度一致"], d)
        self.assertGreater(d["平均亮度差"], 200, "差异如此 blatant，别的数必须看得出来：%s" % d)

    def test_small_local_change_must_not_read_as_tongkuan(self):
        """🔴 本条是这根触手诞生当天抓到的**假绿**的回归锁：
        只改一块小面积（整图 aHash 与平均值都看不见），**不许**判成「同款」。"""
        from PIL import Image
        base = Image.new("RGB", (240, 160), (11, 11, 20))
        img = base.copy()
        for x in range(10, 60):                 # 一小块明显不同（约占面积 8%）
            for y in range(10, 30):
                img.putpixel((x, y), (255, 107, 107))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        changed = base64.b64encode(buf.getvalue()).decode()
        buf2 = io.BytesIO()
        base.save(buf2, "PNG")
        plain = base64.b64encode(buf2.getvalue()).decode()
        d = VP.run("diff", a=plain, b=changed)
        self.assertNotEqual(d["verdict"], "同款", "小面积真变被判成同款 = 尺子瞎了：%s" % d)
        self.assertGreater(d["变化像素占比"], 0.0, "局部敏感项必须真的动起来：%s" % d)


class TestVisionPrintFalseGreenGuards(unittest.TestCase):
    """🔴 假绿闸（fail-closed）—— 每一条都是当场抓到过的假绿通道，**不许**再绿。"""

    def _write(self, name, data: bytes) -> str:
        p = Path(_TMP.name) / name
        p.write_bytes(data)
        return str(p)

    def test_see_flags_blank_frame_and_file_provenance(self):
        """纯色帧必须被标 `frame_suspect`；用文件当帧必须如实标 `file`。"""
        plain = self._write("blank.png", base64.b64decode(_png(rgb=(11, 11, 20))))
        s = VP.run("see", image=plain, name="judge-see-blank")
        self.assertTrue(s["ok"], s)
        self.assertEqual(s["frame_from"], "file")
        self.assertTrue(s.get("frame_suspect"), "纯色帧没被标可疑 = 假绿通道开着：%s" % s)
        self.assertLess(s["std_l"], 2.0)

    def test_see_marks_screen_provenance(self):
        """原生眼取屏必须标 `screen`（取不到就如实报 unavailable，不返回假帧）。"""
        s = VP.run("see", name="judge-see-screen")
        if not s.get("ok"):
            self.assertTrue(s.get("unavailable"), "取不到屏必须是 unavailable，不许是别的样子：%s" % s)
            self.skipTest("本进程拿不到交互桌面（如实报 unavailable）⇒ 这条腿跳过")
        self.assertEqual(s["frame_from"], "screen")

    def test_region_actually_crops_or_fails_closed(self):
        """🔴 静默偏差锁：`region` **必须真裁**。

        实测（2026-10-13）：`omni_core._screen_capture` 的 dxcam 分支**无视 region** ——
        要 320×200 回来 1920×1080 且**不报错**。本件因此自己裁；裁不了（越界/非法）必须 fail-closed。
        """
        plain = self._write("for-crop.png", base64.b64decode(_png(w=240, h=160)))
        ok = VP.run("see", image=plain, region={"x": 20, "y": 10, "w": 100, "h": 60},
                    name="judge-crop")
        self.assertTrue(ok["ok"], ok)
        self.assertEqual(ok["size"], [100, 60], "region 没被真裁：%s" % ok)
        self.assertTrue(ok["region_applied"])
        bad = VP.run("see", image=plain, region={"x": 200, "y": 0, "w": 100, "h": 50},
                     name="judge-crop-bad")
        self.assertFalse(bad["ok"], "越界 region 必须 fail-closed，不许静默给整屏：%s" % bad)
        self.assertTrue(bad["fail_closed"])

    @unittest.skipUnless(_browser_ok(), "本机没有 playwright ⇒ 渲那条腿**跳过**（不假装跑过）")
    def test_blank_frame_must_not_be_tongkuan(self):
        page = ("<!doctype html><html><body style='margin:0;background:#000'>"
                "</body></html>")
        p = VP.run("print", code=page, name="judge-blank", width=120, height=80)
        self.assertTrue(p["ok"], p)
        lp = VP.run("loop", code=page, image=p["png"], name="judge-blank2", width=120, height=80)
        self.assertEqual(lp["verdict"], VP._VERDICT_UNKNOWN, lp.get("diff"))
        self.assertFalse(lp["可信"])
        self.assertTrue(any("近空白" in r for r in lp["无法判定理由"]), lp["无法判定理由"])

    @unittest.skipUnless(_browser_ok(), "本机没有 playwright ⇒ 渲那条腿**跳过**（不假装跑过）")
    def test_render_error_voids_the_verdict(self):
        page = ("<!doctype html><html><body style='margin:0;background:#123456'>"
                "<script>throw new Error('boom')</script></body></html>")
        p = VP.run("print", code=page, name="judge-err")
        self.assertTrue(p["ok"], p)
        self.assertTrue(p["render"]["errors"], "页面自报错必须被记下来（不记就是假绿）：%s" % p["render"])
        lp = VP.run("loop", code=page, image=p["png"], name="judge-err2")
        self.assertEqual(lp["verdict"], VP._VERDICT_UNKNOWN, lp.get("diff"))
        self.assertTrue(any("渲得不可信" in r for r in lp["无法判定理由"]), lp["无法判定理由"])

    @unittest.skipUnless(_browser_ok(), "本机没有 playwright ⇒ 渲那条腿**跳过**（不假装跑过）")
    def test_blocked_outbound_voids_the_verdict(self):
        """页面夹带外链（本件禁网会拦掉）⇒ 渲出来的**不是真实浏览器的样子** ⇒ 不许下结论。"""
        page = ("<!doctype html><html><body style='margin:0;background:#0B0B14'>"
                "<img src='https://example.com/nope.png' width='40' height='40'></body></html>")
        p = VP.run("print", code=page, name="judge-blocked")
        self.assertTrue(p["ok"], p)
        self.assertTrue(p["render"]["blocked"], "外链请求必须被拦并记名：%s" % p["render"])
        lp = VP.run("loop", code=page, image=p["png"], name="judge-blocked2")
        self.assertEqual(lp["verdict"], VP._VERDICT_UNKNOWN, lp.get("diff"))
        self.assertTrue(any("出网请求被拦" in r for r in lp["无法判定理由"]), lp["无法判定理由"])


class TestVisionPrintPolishContract(unittest.TestCase):
    """调优那条链的**契约面**（不跑链、不起进程）。"""

    def test_polish_needs_image_and_knobs(self):
        a = VP.run("polish")
        self.assertFalse(a["ok"], "没给图必须 fail-closed：%s" % a)
        self.assertEqual(a["status"], "needs_params")
        png = Path(_TMP.name) / "for-polish.png"
        png.write_bytes(base64.b64decode(_png()))
        b = VP.run("polish", image=str(png))
        self.assertFalse(b["ok"], "一个旋钮都没给必须 fail-closed：%s" % b)
        self.assertEqual(b["status"], "needs_params")
        c = VP.run("polish", image=str(Path(_TMP.name) / "没有这张图.png"), size=1024)
        self.assertFalse(c["ok"])
        self.assertEqual(c["status"], "not_found")

    def test_where_lists_polish(self):
        self.assertIn("polish", VP.run("where")["ops"])
        self.assertIn("清晰度", VP.run("status")["polish_legs"])

    def test_every_knob_of_both_legs_is_reachable(self):
        """🔴 主人令「**每一个调节都要触手可控**」的**机检**（不跑链、纯契约）：
        两条腿的每一个旋钮都必须出现在本位的可调清单里 —— 缺一个就红。
        这防的是"藏在代码里的常数"：参数看着有、其实传不进去。"""
        from gbt_allinone.tools import comfy_native as CN
        declared = set(VP._KNOBS_DECLARED)
        node_knobs = {str(x).rstrip("?") for x in CN.NODES["upscale_4k"]["in"]} - {"image", "out"}
        self.assertTrue(node_knobs <= declared,
                        "天真 upscale_4k 有旋钮挂不上本位：%s" % sorted(node_knobs - declared))
        for k in ("look", "look_intent", "grain"):     # 外观库那条腿的旋钮
            self.assertIn(k, declared, "外观库那条腿的旋钮 %s 挂不上" % k)
        self.assertIn("node_inputs", declared, "要有直通口：将来节点加旋钮也不用改包装")

    def test_node_inputs_unknown_key_fails_closed(self):
        """直通口不许把**没声明的键**静默丢掉（那就是『参数写了其实没生效』）。"""
        png = Path(_TMP.name) / "for-passthrough.png"
        png.write_bytes(base64.b64decode(_png()))
        r = VP.run("polish", image=str(png), node_inputs={"并没有这个键": 1})
        self.assertFalse(r["ok"], r)
        self.assertTrue(r["fail_closed"])
        self.assertIn("并没有这个键", r["error"])

    def test_grade_grain_is_a_real_knob(self):
        """外观库的**颗粒**必须是真旋钮（原先藏在代码里：preview 根本传不进 grain）。"""
        import importlib.util
        fg = _REPO / "tools" / "filmgrade.py"
        spec = importlib.util.spec_from_file_location("_fg_probe", fg)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        a, b = m.grade_chain("做旧", 2), m.grade_chain("做旧", 14)
        self.assertNotEqual(a, b, "颗粒旋钮没接上（两条链一模一样）：%s" % a)
        self.assertIn("alls=2", a)
        self.assertIn("alls=14", b)
        self.assertIn("grade_chain", dir(m))

    def _filmgrade(self):
        import importlib.util
        fg = _REPO / "tools" / "filmgrade.py"
        spec = importlib.util.spec_from_file_location("_fg_probe2", fg)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_say_table_only_maps_to_declared_knobs(self):
        """🔴 「人话 → 旋钮」的表**不许指向挂不上的旋钮**（表漂移了就是"看着能说、其实没动"）。"""
        declared = set(VP._KNOBS_DECLARED) | {"brightness", "contrast", "saturation", "gamma"}
        for words, fam, delta in VP._SAY_TABLE:
            self.assertTrue(words, "人话表里有一条没有词")
            for k in delta:
                self.assertIn(k, declared, "人话表把 %r 映射到了挂不上的旋钮 %s" % (words[0], k))

    def test_parse_say_pure_recognize_and_fallback(self):
        p = VP._parse_say("更清晰一点，太暗了提亮")
        self.assertTrue(p["recognized"], p)
        self.assertEqual(p["旋钮"].get("sharpen"), 0.9, p)
        self.assertEqual(p["旋钮"].get("brightness"), 0.06, p)
        self.assertEqual(len(p["命中"]), 2, p)
        q = VP._parse_say("把它弄得更有韵味一点")
        self.assertFalse(q["recognized"], "表里没有的说法必须**认不出**，不许猜：%s" % q)
        self.assertTrue(q["认识的说法"], "认不出时要把认识的说法摆出来")

    def test_say_unknown_and_conflict_fail_closed(self):
        png = Path(_TMP.name) / "for-say.png"
        png.write_bytes(base64.b64decode(_png()))
        a = VP.run("polish", image=str(png), say="把它弄得更有韵味一点")
        self.assertFalse(a["ok"], a)
        self.assertEqual(a["status"], "say_not_recognized")
        b = VP.run("polish", image=str(png), say="太暗了，又太亮了")
        self.assertFalse(b["ok"], b)
        self.assertEqual(b["status"], "say_conflict")

    def test_adjust_limits_are_enforced(self):
        """补光族独立旋钮：只认四个键、越界即拒（不许静默丢掉一个越界值）。"""
        fg = self._filmgrade()
        self.assertIn("brightness=0.06", fg.adjust_chain({"brightness": 0.06}))
        self.assertEqual(fg.adjust_chain({}), "")
        with self.assertRaises(ValueError):
            fg.adjust_chain({"brightness": 5})
        with self.assertRaises(ValueError):
            fg.adjust_chain({"并没有这个键": 1})

    def test_plain_look_exists_for_knob_only_edits(self):
        """「只想调旋钮、不套味道」必须有出口 —— 否则等于**替用户加戏**。"""
        fg = self._filmgrade()
        self.assertIn("原样", fg.LOOKS, "缺「原样」味道 ⇒ 只想提亮会被迫连带套上一个味道")
        self.assertEqual(fg.grade_chain("原样"), "null")


@unittest.skipUnless(_browser_ok(), "本机没有 playwright ⇒ 渲那条腿**跳过**（不假装跑过）")
class TestVisionPrintPolishChain(unittest.TestCase):
    """调优链真跑：视觉打印的产物 → 天真（清晰度）→ 外观库（补光/味道）→ 读数。

    ⚠️ 两条腿都是**嵌套走唯一门**（run_task）去调既有位 ⇒ 若本进程被门拒（要主人授权），
    本判据**如实跳过**，绝不假装跑过；跑得动就断言"两腿齐 + 读数齐 + 产物在盘"。
    """

    def test_polish_chain_and_readings(self):
        p = VP.run("print", code=_PAGE_A, name="judge-polish-src", width=640, height=400)
        self.assertTrue(p["ok"], p)
        src = _REPO / p["png"]
        out = Path(_TMP.name) / "polished.jpg"
        r = VP.run("polish", image=str(src), out=str(out), size=1280, sharpen=0.8,
                   look="filmic", name="judge-polish")
        if not r.get("ok"):
            self.skipTest("嵌套那两条腿被门拒（要主人授权）⇒ 跳过，不假装跑过：%s"
                          % (r.get("missing_scopes") or r.get("error")))
        steps = r.get("steps") or []
        self.assertEqual([s["step"] for s in steps], ["upscale_4k", "preview(味道)"], r)
        self.assertTrue(all(s["ok"] for s in steps), r)
        self.assertTrue(all(s.get("gate") == "ok" for s in steps), "两条腿都要过唯一门：%s" % r)
        self.assertTrue(out.is_file(), r)
        q = r["锐度_同尺寸"]
        for k in ("调前", "放大后", "成品"):
            self.assertIsNotNone(q.get(k), r)
        # 尺子必须在动（方向是数据说了算的，本判据不替它下方向结论）
        self.assertNotEqual(q["调前"], q["放大后"], "放大前后同尺寸锐度读数一模一样 = 尺子没动：%s" % r)
        self.assertIn("亮度差", r["补光与味道"] or {}, r)
        self.assertIn(r["verdict"], ("清晰度提升", "清晰度下降", "基本持平"), r)


@unittest.skipUnless(_browser_ok(), "本机没有 playwright ⇒ 渲那条腿**跳过**（不假装跑过）")
class TestVisionPrintLoop(unittest.TestCase):
    """五段链真跑（要浏览器；本机有 Edge/Chrome 才跑）。"""

    def test_self_compare_must_be_unknown_not_tongkuan(self):
        """🔴 拿**我们自己渲出来的图**当"所见帧" ⇒ 必然逐字节同一张 ⇒ 只许「无法判定」。
        （这是上一轮的"正控"原形：那是**自比**，拿它念成"还原成功"就是假绿。）"""
        p = VP.run("print", code=_PAGE_A, name="judge-self-a")
        self.assertTrue(p["ok"], p)
        self.assertTrue(p["render"]["zero_outbound"], "自包含页不许有出网请求：%s" % p["render"])
        lp = VP.run("loop", code=_PAGE_A, image=p["png"], name="judge-self-b")
        self.assertEqual(lp["verdict"], VP._VERDICT_UNKNOWN, lp.get("diff"))
        self.assertTrue(any("逐字节同一张" in r for r in lp["无法判定理由"]), lp["无法判定理由"])

    def test_chain_reproduces_a_frame_it_never_rendered(self):
        """正向自证（**非自比**）：所见帧由 PIL 画（不是我们的渲染器产的），
        码用 CSS 逐块复刻 ⇒ 渲回来必须与原帧成「同款」。
        ⚠️ 边界：本条证的是**链能跑通且尺子标定对**；「用 CSS 复刻真实界面」那条要靠她的码 + 真靶子，
        判据件不替它下结论。"""
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (300, 200), (18, 22, 34))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 299, 59], fill=(245, 176, 65))
        d.rectangle([20, 90, 139, 179], fill=(0, 229, 255))
        d.rectangle([170, 90, 279, 179], fill=(124, 77, 255))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        frame = Path(_TMP.name) / "seen-by-eye.png"
        frame.write_bytes(buf.getvalue())
        code = ("<!doctype html><html><head><meta charset='utf-8'><style>"
                "html,body{margin:0;padding:0;overflow:hidden;background:#121622}"
                "div{position:absolute}"
                "#a{left:0;top:0;width:300px;height:60px;background:#F5B041}"
                "#b{left:20px;top:90px;width:120px;height:90px;background:#00E5FF}"
                "#c{left:170px;top:90px;width:110px;height:90px;background:#7C4DFF}"
                "</style></head><body><div id='a'></div><div id='b'></div><div id='c'></div>"
                "</body></html>")
        lp = VP.run("loop", code=code, image=str(frame), name="judge-reproduce",
                    width=300, height=200)
        self.assertTrue(lp["ok"], lp)
        self.assertEqual(lp["verdict"], "同款", lp.get("diff"))
        self.assertTrue(lp["可信"], lp.get("无法判定理由"))

    def test_other_page_reads_as_buxiang(self):
        p = VP.run("print", code=_PAGE_A, name="judge-c1")
        self.assertTrue(p["ok"], p)
        lp = VP.run("loop", code=_PAGE_C, image=p["png"], name="judge-neg")
        self.assertIn(lp.get("verdict"), ("接近", "不像"), lp.get("diff"))
        self.assertNotEqual(lp.get("verdict"), "同款", "完全不搭的码不许判同款：%s" % lp.get("diff"))

    def test_small_color_change_is_never_tongkuan(self):
        """🔴 诞生当天那条假绿的**端到端**回归锁：只改一处文字颜色，**不许**判「同款」。"""
        p = VP.run("print", code=_PAGE_A, name="judge-mid-a")
        self.assertTrue(p["ok"], p)
        lp = VP.run("loop", code=_PAGE_B, image=p["png"], name="judge-mid-b")
        self.assertNotEqual(lp.get("verdict"), "同款", "改了一处颜色还判同款 = 尺子又瞎了：%s" % lp.get("diff"))
        self.assertGreater(lp["diff"]["变化像素占比"], 0.0, "局部敏感项必须动起来：%s" % lp["diff"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
