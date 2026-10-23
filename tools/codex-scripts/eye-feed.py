# -*- coding: utf-8 -*-
"""触手视觉回传 · 真抓帧 → 真落盘 → 供**独立窗口**像摄像头那样回放。

立场（Owner 2026-09-23）：「专门设立一个独立窗口来显示触手看到的东西，
就像带个摄像头传回画面一样的逼真的视觉感」。
⇒ 那个窗口里**一帧都不许是画的**。画面必须是
`cap tentacle {"action":"see"}`（DXGI 直读显卡帧缓冲，**与显示屏同源**）
真取回来的帧，逐字节落盘再显示。

为什么非要有这个生成器（为什么不让页面自己取）：
  · 窗口走 `file://`，CSP 是 `default-src 'none'; connect-src 'none'` ——
    页面**读不到本地 json，也发不出任何请求**；
  · 所以帧必须是**盘上的真图像文件**，清单一律走**经典脚本**（本仓既有做法：
    `brain/brain-data.js`）。两样都由本件写。

四条不许破的纪律：
  ① **二进制逐字节落盘**：`base64.b64decode` 之后 `write_bytes`，中途不做任何文本编解码
     （把 JPEG 当文本读写 = 当场弄成废物）。
  ② **环形覆盖，不删文件**：帧名是固定 N 个槽位轮转，就地覆盖 ——
     既不产生删除足迹，目录也不会越滚越大。
  ③ **取不到就如实报取不到**：不写占位图、**不拿上一帧冒充新帧**（清单里 `ok:false` + 真原因）。
  ④ **走唯一门**：取帧经 `run_task`，并在信封里跑，账本上记 `synced:true · entry:outer`。

用法:
  py -3.14 tools/codex-scripts/eye-feed.py                    # 抓一帧
  py -3.14 tools/codex-scripts/eye-feed.py --loop             # 持续抓（默认 1.5s 一帧）
  py -3.14 tools/codex-scripts/eye-feed.py --loop -i 1.0 -n 16
  py -3.14 tools/codex-scripts/eye-feed.py --json             # 机器读
"""
import argparse
import base64
import hashlib
import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
EYE = ROOT / "holo_pet_w3" / "eye"
FRAMES = EYE / "frames"
MANIFEST = EYE / "frames.js"
sys.path.insert(0, str(ROOT))


def capture():
    """经**唯一门**取一帧。返回 run_task 的完整信封（不拆，留证据）。

    为什么在信封里调：Owner 令三层默认同步。`sync_exec.envelope()` 让这次取帧
    在账本上记 `synced:true · entry:outer`，而不是又添一条"无脑操作"。
    信封坏了**不能把取帧弄崩** —— 那只是记不上账，不是能力坏了。

    🔴 **`incremental: false` 是本窗的命门**（2026-09-23 实测抓到的真缺陷）：
    `_screen_capture` 默认走**增量模式** —— 画面变化 <15% 时只编码**变化的那块矩形**，
    并把 `delta` 标成 True。对"看一眼发生了什么"是对的；对**视频回传是错的**：
    实测同一分钟里取到的"帧"是 `1136×64` / `428×720` / `1636×68` 这种碎条，
    **根本不成画面**（回传窗会一块一块地闪）。摄像头要的永远是**整帧**。
    这个开关原先在能力位层面**没有出口**，是本次一并开的（见 omni_vision.see 的注释）。
    """
    from gbt_allinone import run_task
    try:
        from gbt_allinone.tools import sync_exec as _se
    except Exception:                                            # noqa: BLE001
        _se = None
    payload = {"action": "see", "kwargs": {"incremental": False}}
    if _se is not None:
        try:
            with _se.envelope():
                return run_task("tentacle", payload)
        except Exception:                                        # noqa: BLE001
            pass
    return run_task("tentacle", payload)


def _body(env):
    """从 run_task 信封里取出能力那一层（`gbt_result`），取不到就退回顶层。"""
    if not isinstance(env, dict):
        return {}
    return env.get("gbt_result") or env


def load_manifest(ring):
    """读回现有清单（用来维护环形序号与历史）。读不出就从零开始，不猜。"""
    if not MANIFEST.is_file():
        return {"seq": 0, "frames": []}
    try:
        txt = MANIFEST.read_text(encoding="utf-8")
        i = txt.find("{")
        j = txt.rfind("}")
        return json.loads(txt[i:j + 1])
    except Exception:                                            # noqa: BLE001
        return {"seq": 0, "frames": []}


def write_manifest(state):
    """清单写成**经典脚本**（不是 .json）：file:// + connect-src 'none' 下页面 fetch 不到 json。"""
    EYE.mkdir(parents=True, exist_ok=True)
    body = json.dumps(state, ensure_ascii=False, indent=1)
    MANIFEST.write_text(
        "/* GBT小土豆V8 · 触手视觉回传清单 · 由 tools/codex-scripts/eye-feed.py 生成\n"
        "   重生成： py -3.14 tools/codex-scripts/eye-feed.py --loop\n"
        "   **不要手改**：下一次抓帧就覆盖。 */\n"
        "window.GBT_EYE = %s;\n" % body, encoding="utf-8")


def _replace(state, new):
    """把新状态**就地**写回调用方的那个 dict。

    🔴 为什么不能写 `state = {...}`（本件第一版就是这么错的，实测当场抓到）：
    那只把**局部名重绑到新 dict**，调用方的 `state` 一个字节都没变。
    症状极隐蔽 —— 帧照写、清单照写、页面照显示，**但 `seq` 永远停在 2**：
    帧名永远是 `f-002.jpg` 就地覆盖，"环形缓冲 12 槽"名存实亡，胶片条永远只有一两张。
    这是同型错误的第 8 次（**看起来生效、其实没生效**）⇒ 从此只用就地更新。
    """
    state.clear()
    state.update(new)


def grab(ring, state):
    """抓一帧，真落盘，写清单。返回这一帧的读数（无论成功失败都返回，不抛）。"""
    t0 = time.time()
    env = capture()
    body = _body(env)
    res = body.get("result") if isinstance(body.get("result"), dict) else {}
    ok = bool(body.get("status") == "ok" and res.get("ok"))

    if not ok:
        # ③ 取不到就如实报取不到：**绝不写占位图、绝不用上一帧冒充**。
        why = (res.get("why") or body.get("message") or body.get("reason")
               or "见信封（能力层没给 why）")
        _replace(state, {
            "ok": False, "seq": int(state.get("seq", 0)), "why": str(why)[:300],
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "failing_since": state.get("failing_since") or time.strftime("%Y-%m-%dT%H:%M:%S"),
            "errors_in_a_row": int(state.get("errors_in_a_row", 0)) + 1,
            "frames": state.get("frames") or [],
            "note": "取帧失败。本清单里**没有**新帧 —— 不拿旧帧冒充新帧。"})
        write_manifest(state)
        return {"ok": False, "why": state["why"], "ms": int((time.time() - t0) * 1000)}

    raw = base64.b64decode(res.get("image_base64") or "")
    if len(raw) < 512 or raw[:2] not in (b"\xff\xd8", b"\x89P"):
        why = "解码后不是一张真图（JPEG 应以 FFD8 开头）—— 不当成帧写盘"
        _replace(state, {
            "ok": False, "why": why, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "seq": int(state.get("seq", 0)), "frames": state.get("frames") or [],
            "note": "形状不对就停下，不写半张图。"})
        write_manifest(state)
        return {"ok": False, "why": why, "ms": int((time.time() - t0) * 1000)}

    seq = int(state.get("seq", 0)) + 1
    slot = seq % ring
    name = "f-%03d.jpg" % slot
    FRAMES.mkdir(parents=True, exist_ok=True)
    (FRAMES / name).write_bytes(raw)                    # ① 逐字节，不经过文本

    digest = hashlib.sha1(raw).hexdigest()[:10]
    w, h = (res.get("size") or [None, None])[:2]
    frame = {"name": name, "seq": seq, "slot": slot,
             "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "epoch": round(time.time(), 2),
             "bytes": len(raw), "kb": round(len(raw) / 1024, 1), "hash": digest,
             "width": w, "height": h}
    # 新帧放最前；同一槽位的历史条目要去掉（那个文件名已被这帧覆盖）
    frames = [f for f in (state.get("frames") or []) if f.get("name") != name]
    frames.insert(0, frame)
    frames = frames[:ring]

    # 整帧自检：增量模式下 `_screen_capture` 会回一块脏矩形。
    # 这里**不假装**那是画面 —— 如实把 `full_frame` 标出来，页面照实显示。
    full = bool(w and h and w >= 320 and h >= 200)
    # 🔴 两个耗时都要报，因为它们**不是一回事**（实测：引擎报 5ms，端到端 350ms）：
    #   · `capture_ms` = DXGI 抓那一帧的时间（引擎自己量的）
    #   · `wall_ms`    = 抓帧 + JPEG 编码 + base64 + 落盘 的**全部**
    # 只报前者会让人以为"这一路很轻"；摄像头回传窗要的是后者。
    wall_ms = int((time.time() - t0) * 1000)
    _replace(state, {
        "ok": True, "seq": seq, "ring": ring, "slots_filled": len(frames),
        "at": frame["at"], "errors_in_a_row": 0, "failing_since": None,
        "engine": res.get("engine"), "fmt": res.get("fmt"),
        "capture_ms": res.get("capture_ms"), "wall_ms": wall_ms, "delta": res.get("delta"),
        "full_frame": full,
        "full_frame_note": ("整帧" if full else
                            "**这是脏矩形不是整帧**（%s×%s）—— 增量模式没关掉？" % (w, h)),
        "width": w, "height": h, "kb": frame["kb"], "hash": digest,
        "source": "DXGI 直读显卡帧缓冲（与显示屏同源）",
        "via": "cap tentacle {\"action\":\"see\",\"kwargs\":{\"incremental\":false}} → run_task 唯一门",
        "frames": frames,
        "note": "画面是真帧，不是画的。清单一帧一哈希；同名即同图。"})
    write_manifest(state)
    return {"ok": True, "seq": seq, "name": name, "kb": frame["kb"], "hash": digest,
            "size": [w, h], "capture_ms": res.get("capture_ms"), "full_frame": full,
            "wall_ms": wall_ms}


def main(argv):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("-i", "--interval", type=float, default=1.5)
    ap.add_argument("-n", "--ring", type=int, default=12)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args(argv)

    ring = max(2, min(64, a.ring))
    state = load_manifest(ring)
    state.setdefault("seq", 0)
    state.setdefault("frames", [])

    if not a.loop or a.once:
        r = grab(ring, state)
        if a.json:
            print(json.dumps(r, ensure_ascii=False))
        else:
            if r["ok"]:
                print("取帧 ok · 第 %d 帧 · %s · %s×%s · %s KB · 采集 %sms · 墙钟 %sms"
                      % (r["seq"], r["name"], r["size"][0], r["size"][1], r["kb"],
                         r["capture_ms"], r["wall_ms"]))
            else:
                print("取帧失败：%s" % r["why"])
        return 0 if r["ok"] else 1

    print("触手视觉回传 · 持续抓帧 · 每 %.2fs 一帧 · 环形 %d 槽 · Ctrl+C 停" % (a.interval, ring))
    n_ok = n_bad = 0
    try:
        while True:
            t = time.time()
            r = grab(ring, state)
            if r["ok"]:
                n_ok += 1
                print("[%s] 帧 #%-4d %s %s×%-5s %6sKB 采集%6sms %s"
                      % (time.strftime("%H:%M:%S"), r["seq"], r["name"],
                         r["size"][0], r["size"][1], r["kb"], r["capture_ms"],
                         "整帧" if r.get("full_frame") else "⚠脏矩形"))
            else:
                n_bad += 1
                print("[%s] 失败：%s" % (time.strftime("%H:%M:%S"), r["why"]))
            time.sleep(max(0.05, a.interval - (time.time() - t)))
    except KeyboardInterrupt:
        print("\n停。累计成功 %d · 失败 %d" % (n_ok, n_bad))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
