# -*- coding: utf-8 -*-
r"""V8 实时眼（eye-stream）—— **把"按需截图"换成"连续帧流"**（照 V9 core/vision_loop.py 的架构）。

主人令（2026-10-10）：「还有视觉你最好**深度分析一下再动手**，要不然，**限制了她的能力发挥**」

## 深度分析结论（先摆事实，再动手）
V9 与 V8 的视觉**不是同一个架构**：
| | V9（core/vision_loop.py） | V8（gbt_allinone/vision_loop.py） |
|---|---|---|
| 取景 | **连续帧流**：独立抓帧线程 + 只留最新帧 | 🔴 **按需截图**（V9 自己承认过的病根：「一帧一停，等于盲人摸象」） |
| 脑取帧 | latest() **不阻塞**，永远拿最新 | 每次现场截 ⇒ 帧龄=截图耗时 |
| 帧龄 | 恒定很低（端到端约 24ms） | 波动大 |
| 帧率 | 全屏 22.6 / **640x360 75.3** / 320x40 132 fps | 无（每发动作才截一次） |

⇒ **所以"帧龄 ≤ 400ms"这条闸，在她那儿几乎不会触发（眼是 24ms 的流）；
  我拿按需截图的眼去配 400ms ⇒ 频繁拒动 ⇒ 真的限制了她的能力发挥。**
  **根因不在阈值，在架构**——阈值是对的方向，但**必须先把眼换成流**。

## 本件做什么（照她架构，不自己发明）
独立抓帧线程（mss）· 只留最新帧 · latest() 不阻塞 · fps_cap=240 ·
默认区域 **640x360**（她实测 75.3fps；全屏只有 22.6）·
**overwritten（被新帧顶掉·设计如此）与 drops（抓帧异常）分开记**。

用法：py -3.14 -X utf8 tools/codex-scripts/eye-stream.py [--check|--selftest]
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "state" / "eye-stream.json"
FPS_CAP = 240
LOOPS: dict = {}


class Eye:
    """一条实时眼：独立线程抓，只留最新帧，脑取最新不等。"""

    def __init__(self, name="main", full=False, region=None, fps_cap=FPS_CAP, keep_pixels=False):
 # 2026-10-10 补 keep_pixels（主人令「本地录制」那条链要用它）：
        #    本件原来**只存元数据（seq/ts/size）不存像素** —— 它是为"视觉闭环"造的
        #    （脑只需要判断帧新不新），**录不了像**。
        #    正路不是另造采集器（那是平行实现），而是**给框架自己的眼加一个可选的像素槽**。
 # 代价如实说：下面注释里那条实测（读 .rgb 会逼出整块像素拷贝，75fps→24.6fps）
        #       **在 keep_pixels=True 时必然要付** —— 所以默认 False，**谁要录像谁显式开**，
        #       并且 fps() 照实报（开了之后帧率会掉，读数上看得见）。
        self.name, self.full, self.region, self.fps_cap = name, full, region, fps_cap
        self.keep_pixels = keep_pixels
        self._pix = None
        self._lock = threading.Lock()
        self._slot = None
        self._stop = threading.Event()
        self._th = None
        self.seq = 0
        self.grabbed = 0
        self.drops = 0            # 抓帧异常丢的
        self.overwritten = 0      # 被新帧顶掉（设计如此，不算丢）
        self.taken = 0
        self.t0 = time.time()
        self.error = ""
        self.engine = ""

    def start(self):
        if self._th and self._th.is_alive():
            return {"ok": True, "已在跑": True}
        self._stop.clear()
        self._th = threading.Thread(target=self._grab_loop, name="eye-" + self.name, daemon=True)
        self._th.start()
        time.sleep(0.5)
        return {"ok": True, "跑起来了": True, "引擎": self.engine,
                "区域": self.region or ("全屏" if self.full else "默认 640x360")}

    def _grab_loop(self):
        try:
            import mss
 # 2026-10-10 抓到真 bug：原来写 getattr(mss, "MSS", None) or mss.mss
            #    —— **mss.MSS 是抽象基类**（mss.base.MSS），它存在 ⇒ 这行永远选中抽象基类，
            #    抓帧线程卡在那儿：engine 空、error 空、grabbed 0（不报错但不干活）。
            #    正解用**小写工厂** mss.mss()（平台实现）。
            MSS = getattr(mss, "mss", None) or mss.mss
            with MSS() as s:
                if self.full:
                    box = s.monitors[1]
                else:
                    if self.region is None:
                        mon = s.monitors[1]
                        self.region = {"left": mon["left"] + 640, "top": mon["top"] + 360,
                                       "width": 640, "height": 360}
                    box = self.region
                self.engine = "mss"
                while not self._stop.is_set():
                    raw = s.grab(box)
                    self.seq += 1
                    self.grabbed += 1
 # 2026-10-10 实测：我原来每帧做 len(raw.rgb) —— 那会**逼出整块像素拷贝**
                    #    ⇒ 帧率只有 24.6fps（她 640x360 实测 75.3）⇒ **每帧开销就在这一行**。
                    #    修法：**不碰像素**（尺寸从 grab 的对象上取，不读 .rgb）。
                    f = {"seq": self.seq, "ts": time.time(), "size": (raw.width, raw.height)}
                    if self.keep_pixels:
                        # 只留**最新一帧**的像素（有界内存）——录像是从这个槽里按目标帧率取的。
                        self._pix = (self.seq, time.time(),
                                     bytes(raw.rgb), raw.width, raw.height)
                    with self._lock:
                        if self._slot is not None and self._slot["seq"] != self.taken:
                            self.overwritten += 1
                        self._slot = f
        except Exception as exc:                                # noqa: BLE001
            self.error = "%s: %s" % (type(exc).__name__, str(exc)[:100])

    def latest(self):
        with self._lock:
            f = self._slot
            if f is not None:
                self.taken = f["seq"]
            return f

    def frame(self):
        """**取最新一帧的像素**（keep_pixels=True 时才有）。给"本地录制"用。

        返回 (seq, ts, rgb_bytes, w, h)；没开像素槽或还没抓到 ⇒ None。
        """
        p = self._pix
        return p

    def look(self):
        f = self.latest()
        if f is None:
            return {"ok": False, "帧号": None, "age_ms": None, "帧龄ms": None,
                    "为什么": self.error or "还没抓到帧"}
        age = round((time.time() - f["ts"]) * 1000, 1)
        return {"ok": True, "帧号": f["seq"], "尺寸": f["size"], "age_ms": age, "帧龄ms": age,
                "口径": "脑永远看最新，不追旧帧；帧龄=我看到的是多久前的世界"}

    def fps(self):
        dt = time.time() - self.t0
        return round(self.grabbed / dt, 1) if dt > 0 else 0.0

    def stats(self):
        return {"帧号": self.seq, "抓了": self.grabbed, "fps": self.fps(),
                "顶掉旧帧": self.overwritten, "丢帧": self.drops, "脑取": self.taken,
                "引擎": self.engine, "错误": self.error or None}

    def stop(self):
        self._stop.set()
        if self._th:
            self._th.join(timeout=2)
        return self.stats()


def eyes(name="main", **kw) -> Eye:
    lp = LOOPS.get(name)
    if lp is None or (lp._th is None or not lp._th.is_alive()):
        lp = Eye(name=name, **kw)
        lp.start()
        LOOPS[name] = lp
    return lp


def self_check(name="main") -> dict:
    lp = LOOPS.get(name)
    if lp is None:
        return {"我有眼": False, "原因": "眼睛还没起（先 eyes()）"}
    s = lp.stats()
    return {"我有眼": s["帧号"] > 0, **s, "口径": "她自己知道有眼睛：实况帧率/帧号/顶掉数都报出来"}


def check() -> int:
    lp = eyes("probe")
    time.sleep(3.0)
    lk = lp.look()
    st = lp.stats()
    # 再量一次全屏做对照（她的实测：全屏 22.6 / 640x360 75.3）
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "架构": "连续帧流（独立抓帧线程 + 只留最新帧 + latest 不阻塞）—— 照 V9 core/vision_loop.py",
           "默认区域": "640x360（她实测 75.3fps；全屏仅 22.6）",
           "fps_cap": FPS_CAP,
           "640x360": st,
           "look()": lk,
           "口径": "帧龄恒定很低时，'帧龄 ≤ 400ms' 才是一条**兜底**闸而不是**常用**闸"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(row, ensure_ascii=False, indent=1), encoding="utf-8")
    print("V8 实时眼（连续帧流）")
    print("  引擎 %s · 抓了 %d 帧 · **fps %s** · 顶掉旧帧 %d · 丢帧 %d"
          % (st["引擎"], st["抓了"], st["fps"], st["顶掉旧帧"], st["丢帧"]))
    print("  look(): 帧号 %s · 尺寸 %s · **帧龄 %sms**" % (lk.get("帧号"), lk.get("尺寸"), lk.get("age_ms")))
    print("  self_check(): %s" % json.dumps(self_check("probe"), ensure_ascii=False)[:200])
    print("  对照她的实测：全屏 22.6fps / 640x360 75.3fps / 320x40 132fps")
    ok = bool(st["抓了"]) and st["fps"] > 5 and (lk.get("age_ms") is not None and lk["age_ms"] <= 400)
    print("判据：%s" % ("PASS（眼在跑 · 帧龄 <=400ms）" if ok else "FAIL（眼没跑起来/帧龄过大）"))
    return 0 if ok else 1


def selftest() -> int:
    lp = eyes("st")
    time.sleep(2.0)
    s1 = lp.stats()
    time.sleep(1.5)
    s2 = lp.stats()
    grow = s2["抓了"] > s1["抓了"]
    lk = lp.look()
    print("负对照A·两秒内帧号在长 => %s（必须 True）" % grow)
    print("负对照B·顶掉旧帧与丢帧分开记 => 顶掉 %d · 丢帧 %d" % (s2["顶掉旧帧"], s2["丢帧"]))
    print("负对照C·latest 不阻塞 => look() 立即返回，帧龄 %sms（应远小于 400）" % lk.get("age_ms"))
    ok = grow and lk.get("age_ms") is not None and lk["age_ms"] < 400
    print("自检：%s" % ("全过" if ok else "不过"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="V8 实时眼（连续帧流）")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    return selftest() if a.selftest else check()


if __name__ == "__main__":
    raise SystemExit(main())
