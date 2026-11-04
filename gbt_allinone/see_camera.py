# gbt-capability: see_camera
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""see_camera · 摄像头之眼（PC + 手机双端）—— 陪主人看这世间万物。

【为什么存在】
  主人原话（2026-11-04）：「她的摄像头调用可用于跟用户对话，手机版和电脑版都可以，
  可通过摄像头陪用户看世间万物美景」。

  在此之前，`BODY_SENSES` 里早就写明了 `see_camera: 摄像头`（七根感官之一），
  但**没有任何能力位承接它** —— 词汇在册、手是空的。这一位把它接上。

【与 body_eye / body_see 的分工】
  · `body_see` / `body_eye` → 看**屏幕**（截屏 → 理解 → 回坐标）；
  · `see_camera`（本位）→ 看**真实世界**（摄像头取帧 → 交出去理解 → 读出来）。
  两者井水不犯河水：一个看屏，一个看世界。

【op】
  · `status`    只读：枚举摄像头，报 index / 分辨率 / 能不能真读到帧
  · `snapshot`  只读+落盘：抓一帧存 png（`.scratch/camera/`）
  · `watch`     只读+落盘：连拍 N 帧（看动态、看风景流动）
  · `phone`     起/停：局域网页面，手机浏览器打开即用前后摄像头拍帧回传
  · `talk`      取帧 → 交给理解层（默认 `body_eye`）→ 用 `body_say` 说出来

【口径（不许破）】
  · 摄像头打不开（驱动/隐私/被占用）→ 如实 `needs_camera`，**不造帧、不脑补画面**；
  · 没有理解层就不假装看得懂 → `needs_dependency`，并说清缺哪位；
  · 出声只走既定选择（edge-tts `zh-TW-HsiaoChenNeural` → SAPI zh-TW → **不出声并报原因**），
    绝不用大陆腔顶替。
"""
from __future__ import annotations

import base64
import socket
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOT_DIR = ROOT / ".scratch" / "camera"
PHONE_PORT = 8770
_PHONE: dict = {"srv": None, "thread": None, "port": None}

OPS = ("status", "snapshot", "watch", "frame", "phone", "talk")


# ──────────────────────────────────────────────────────────────────────
# 取帧：只有真读到帧才算可用
# ──────────────────────────────────────────────────────────────────────
def _cv():
    import cv2
    return cv2


def _open(index: int, warmup: int = 3):
    """开摄像头并丢掉前几帧（首帧常常是黑的）。

    后端按**能用的先上**依次试：DSHOW → MSMF → ANY。
    🔴 2026-11-04：第一版只试 DSHOW，本机 MSMF 其实也能出帧。
    触手那边（`tentacle/hand_vision.py`）还有一条 WinRT 回退，这里一并挂上——
    **取帧这条路属于触手，不属于本位自造**。
    """
    try:
        cv2 = _cv()
    except ImportError:
        return None, "needs_dependency: 缺 opencv-python"
    tried = []
    for name in ("CAP_DSHOW", "CAP_MSMF", "CAP_ANY"):
        backend = getattr(cv2, name, None)
        if backend is None:
            continue
        cap = cv2.VideoCapture(int(index), backend)
        if not cap.isOpened():
            cap.release()
            tried.append(f"{name}:打不开")
            continue
        for _ in range(max(1, int(warmup))):
            cap.read()
        ok, frame = cap.read()
        if ok and frame is not None:
            return (cap, frame, name.replace("CAP_", "").lower()), None
        cap.release()
        tried.append(f"{name}:开了但读不到帧")

    # 触手 WinRT 回退（hand_vision 里已有实现；脚本缺失时它会返回 None）
    # 只在要 0 号（主摄）时才回退 —— 要 9 号却给 0 号的画面，那是骗人。
    if int(index) == 0:
        try:
            from .tentacle import hand_vision as _hv
            w = _hv._winrt_capture()
            if w:
                img = _read_any(w)
                if img is not None:
                    return (None, img, "winrt"), None
                tried.append("winrt:抓到文件但读不开")
            else:
                tried.append("winrt:不可用")
        except Exception as e:  # noqa: BLE001
            tried.append(f"winrt:{type(e).__name__}")

    return None, (f"needs_camera: 索引 {index} 拿不到帧（被占用 / 无权限 / 无此设备）；"
                  f"试过 {' / '.join(tried)}")


def _probe(max_index: int = 4) -> list[dict]:
    """枚举**真能读到帧**的摄像头。读不到的不列（不报「有设备」来充数）。"""
    out = []
    for i in range(max(int(max_index), 1)):
        got, _why = _open(i, warmup=2)
        if got is None:
            continue
        cap, frame, backend = got
        h, w = frame.shape[:2]
        if cap is not None:
            cap.release()
        out.append({"index": i, "width": int(w), "height": int(h), "backend": backend})
    return out


def _lan_ip() -> str:
    """拿本机在局域网里的地址（UDP 探一下，不发真包）。拿不到回 127.0.0.1。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:  # noqa: BLE001
        return "127.0.0.1"
    finally:
        s.close()


def _save(frame, tag: str = "shot") -> Path:
    """落帧。

    🔴 血账（2026-11-04）：一开始用 `cv2.imwrite(str(p), frame)` —— **静默失败返回 False**，
    因为本仓路径含中文（「GBT小土豆V8桌面版」），OpenCV 的 imwrite 在 Windows 上对
    非 ASCII 路径写不进去。结果是 snapshot 报 ok=True、文件却不在盘上，后面读它全炸。
    改成 `imencode` + `Path.write_bytes`：编码走内存，写盘走 Python，跟路径字符集无关。
    """
    import cv2
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    p = SHOT_DIR / f"{tag}-{time.strftime('%Y%m%d-%H%M%S')}-{int(time.time() * 1000) % 1000:03d}.png"
    ok, buf = cv2.imencode(".png", frame)
    if not ok:
        raise RuntimeError("PNG 编码失败（imencode 返回 False）")
    p.write_bytes(buf.tobytes())
    if not p.is_file():
        raise RuntimeError(f"写盘后文件不存在：{p}")
    return p


def _brightness(frame) -> float:
    try:
        import numpy as np
        return round(float(np.asarray(frame).mean()), 2)
    except Exception:  # noqa: BLE001
        return -1.0


def _read_any(path) -> "object | None":
    """读一张图，返回 BGR ndarray；读不开回 None。

    🔴 血账（2026-11-04 · 同一类坑的第二次）：
      `cv2.imread(str(p))` 在 Windows 上遇到**非 ASCII 路径**会直接返回 None
      （stderr: `cv::findDecoder imread_('…'): can't open/read file`），
      而本仓路径含「GBT小土豆V8桌面版」⇒ WinRT 回退明明抓到了 83 KB 的真图，
      却因为读不开被判成「抓到文件但读不开」。
      改走 PIL（它走 Python 的文件句柄，不吃字符集这一套），再手工转 BGR。
      这和 `_save()` 里 `cv2.imwrite` 静默失败是**同一个根因**：OpenCV 的路径处理。
    """
    try:
        import numpy as np
        from PIL import Image
        im = Image.open(str(path)).convert("RGB")
        return np.asarray(im)[:, :, ::-1].copy()       # RGB → BGR
    except Exception:  # noqa: BLE001
        return None


# ──────────────────────────────────────────────────────────────────────
# op: status / snapshot / watch
# ──────────────────────────────────────────────────────────────────────
def status(**_kw) -> dict:
    cams = _probe()
    return {"ok": bool(cams), "op": "status", "kind": "see_camera",
            "sense": "see_camera", "cameras": cams, "count": len(cams),
            "phone_url": f"http://{_lan_ip()}:{PHONE_PORT}/" if _PHONE.get("srv") else None,
            "ops": list(OPS),
            "口径": "读不到帧的不列；PC 走 cv2，手机走局域网页面"}


def snapshot(index: int = 0, warmup: int = 3, save: bool = True, **_kw) -> dict:
    got, why = _open(index, warmup)
    if got is None:
        return {"ok": False, "op": "snapshot", "status": "needs_camera", "error": why,
                "index": int(index)}
    cap, frame, backend = got
    try:
        h, w = frame.shape[:2]
        out = _save(frame, "pc") if save else None
        return {"ok": True, "op": "snapshot", "source": "pc", "index": int(index),
                "backend": backend, "size": [int(w), int(h)], "yavg": _brightness(frame),
                "out": str(out) if out else None,
                "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    finally:
        if cap is not None:
            cap.release()


def watch(index: int = 0, frames: int = 12, interval: float = 0.2,
          save_every: int = 4, **_kw) -> dict:
    """连拍：看动态用。只留每隔 save_every 帧的一张，不把盘塞满。"""
    got, why = _open(index)
    if got is None:
        return {"ok": False, "op": "watch", "status": "needs_camera", "error": why}
    cap, first, backend = got
    saved, ys, n = [], [], 0
    t0 = time.perf_counter()
    try:
        # WinRT 回退只能给一张，这里如实只报一帧，不假装有流
        if cap is None:
            ys.append(_brightness(first))
            saved.append(str(_save(first, "watch")))
            return {"ok": True, "op": "watch", "index": int(index), "backend": backend,
                    "frames": 1, "saved": saved, "yavg": ys[0],
                    "boundary": "WinRT 单帧回退，不是实时流"}
        while n < max(1, int(frames)):
            ok, f = cap.read()
            if not ok:
                break
            ys.append(_brightness(f))
            if n % max(1, int(save_every)) == 0:
                saved.append(str(_save(f, "watch")))
            n += 1
            time.sleep(max(0.0, float(interval)))
    finally:
        if cap is not None:
            cap.release()
    el = max(time.perf_counter() - t0, 1e-6)
    return {"ok": n > 0, "op": "watch", "index": int(index), "backend": backend,
            "frames": n, "saved": saved,
            "yavg": round(sum(ys) / len(ys), 2) if ys else -1.0,
            "fps": round(n / el, 2), "seconds": round(el, 2),
            "boundary": "逐帧真读；掉帧如实计数"}


def frame_b64(index: int = 0, **_kw) -> dict:
    """给**触手流水线**用的：取一帧、带指纹、回 base64。

    触手的视觉总线（`tentacle/vision_bus.py`）只认屏幕眼（`_screen_capture`），
    摄像头眼要进总线得自带帧源 —— 这个 op 就是那个帧源。
    指纹口径与总线一致（sha1 前 16 位），同画面可被上层判重。
    """
    import hashlib
    got, why = _open(index)
    if got is None:
        return {"ok": False, "op": "frame", "status": "needs_camera", "error": why}
    cap, frame, backend = got
    try:
        ok, buf = _cv().imencode(".png", frame)
        if not ok:
            return {"ok": False, "op": "frame", "status": "failed", "error": "PNG 编码失败"}
        raw = buf.tobytes()
        h, w = frame.shape[:2]
        return {"ok": True, "op": "frame", "eye": "see_camera", "index": int(index),
                "backend": backend, "w": int(w), "h": int(h), "bytes": len(raw),
                "sha": hashlib.sha1(raw).hexdigest()[:16],
                "b64": base64.b64encode(raw).decode("ascii"),
                "yavg": _brightness(frame)}
    finally:
        if cap is not None:
            cap.release()


# ──────────────────────────────────────────────────────────────────────
# op: phone — 手机浏览器当摄像头
# ──────────────────────────────────────────────────────────────────────
_PHONE_HTML = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>小土豆 · 手机之眼</title><style>
*{box-sizing:border-box}body{margin:0;background:#0b0e14;color:#e6edf3;font:15px/1.6 -apple-system,
"PingFang SC","Microsoft YaHei",sans-serif;padding:14px}
h1{font-size:17px;margin:0 0 10px;font-weight:600}
video{width:100%;border-radius:14px;background:#000;display:block}
.row{display:flex;gap:8px;margin-top:12px}
button{flex:1;padding:13px 10px;border:0;border-radius:12px;font-size:15px;font-weight:600;
background:#1f6feb;color:#fff}button.sec{background:#21262d;color:#c9d1d9}
button:disabled{opacity:.45}
#st{margin-top:12px;font-size:13px;color:#8b949e;white-space:pre-wrap;word-break:break-all}
img#last{width:100%;border-radius:12px;margin-top:12px;display:none}
</style></head><body>
<h1>🥔 小土豆 · 手机之眼</h1>
<video id="v" autoplay playsinline muted></video>
<div class="row"><button id="go">开始看</button><button id="flip" class="sec">翻转</button></div>
<div class="row"><button id="auto" class="sec">自动连拍：关</button></div>
<div id="st">未开始。点「开始看」并允许摄像头。</div>
<img id="last" alt="last">
<script>
let stream=null,facing="environment",timer=null;
const v=document.getElementById('v'),st=document.getElementById('st'),last=document.getElementById('last');
async function open(){
  if(stream)stream.getTracks().forEach(t=>t.stop());
  stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:facing,width:{ideal:1280}},audio:false});
  v.srcObject=stream; st.textContent="摄像头已开（"+facing+"）";
}
document.getElementById('go').onclick=async()=>{
  try{await open();}catch(e){st.textContent="打不开摄像头："+e.message;} };
document.getElementById('flip').onclick=async()=>{
  facing=facing==="environment"?"user":"environment";
  try{await open();}catch(e){st.textContent="翻转失败："+e.message;} };
async function shot(tag){
  if(!stream)return;
  const c=document.createElement('canvas');
  c.width=v.videoWidth||720;c.height=v.videoHeight||1280;
  c.getContext('2d').drawImage(v,0,0,c.width,c.height);
  const b64=c.toDataURL('image/jpeg',0.82).split(',')[1];
  try{
    const r=await fetch('frame',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({jpeg:b64,facing:tag||facing,w:c.width,h:c.height})});
    const j=await r.json();
    st.textContent="已传一帧 · "+new Date().toLocaleTimeString()+"\\n"+(j.out||j.error||"");
    last.src="data:image/jpeg;base64,"+b64; last.style.display="block";
  }catch(e){st.textContent="上传失败："+e.message;}
}
document.getElementById('auto').onclick=(e)=>{
  if(timer){clearInterval(timer);timer=null;e.target.textContent="自动连拍：关";return;}
  timer=setInterval(()=>shot(),2500);e.target.textContent="自动连拍：开（2.5s）";
};
</script></body></html>"""


def _make_app():
    from aiohttp import web

    async def index(_req):
        return web.Response(text=_PHONE_HTML, content_type="text/html", charset="utf-8")

    async def frame(req):
        try:
            data = await req.json()
            raw = base64.b64decode(str(data.get("jpeg") or ""))
        except Exception as e:  # noqa: BLE001
            return web.json_response({"ok": False, "error": f"帧解析失败：{e}"}, status=400)
        if len(raw) < 512:
            return web.json_response({"ok": False, "error": "帧太小，像空图"}, status=400)
        SHOT_DIR.mkdir(parents=True, exist_ok=True)
        p = SHOT_DIR / f"phone-{time.strftime('%Y%m%d-%H%M%S')}-{int(time.time()*1000)%1000:03d}.jpg"
        p.write_bytes(raw)
        return web.json_response({"ok": True, "out": str(p), "bytes": len(raw),
                                 "facing": data.get("facing"), "w": data.get("w"),
                                 "h": data.get("h")})

    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_post("/frame", frame)
    return app


def phone(action: str = "start", port: int = PHONE_PORT, **_kw) -> dict:
    """起/停局域网页面。手机与电脑在同一 WiFi 下，手机浏览器打开 URL 即可。"""
    act = (action or "start").lower()
    if act in ("stop", "off"):
        srv = _PHONE.get("srv")
        loop = _PHONE.get("loop")
        if not srv or loop is None:
            return {"ok": True, "op": "phone", "state": "already_stopped"}
        try:
            import asyncio
            fut = asyncio.run_coroutine_threadsafe(srv.cleanup(), loop)
            fut.result(timeout=5)
            loop.call_soon_threadsafe(loop.stop)
            _PHONE.update({"srv": None, "thread": None, "port": None, "loop": None})
            return {"ok": True, "op": "phone", "state": "stopped"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "op": "phone", "status": "failed", "error": f"停不掉：{e}"}

    if _PHONE.get("srv"):
        return {"ok": True, "op": "phone", "state": "already_running",
                "url": f"http://{_lan_ip()}:{_PHONE['port']}/"}

    try:
        from aiohttp import web
    except ImportError:
        return {"ok": False, "op": "phone", "status": "needs_dependency",
                "error": "缺 aiohttp，手机端页面起不来"}

    import asyncio

    loop = asyncio.new_event_loop()
    started = threading.Event()
    box: dict = {}

    def _run():
        asyncio.set_event_loop(loop)
        runner = web.AppRunner(_make_app())
        loop.run_until_complete(runner.setup())

        async def _start():
            site = web.TCPSite(runner, "0.0.0.0", int(port))
            await site.start()
            box["runner"] = runner
            started.set()
        try:
            loop.run_until_complete(_start())
            loop.run_forever()
        except Exception as e:  # noqa: BLE001
            box["error"] = str(e)
            started.set()

    th = threading.Thread(target=_run, daemon=True, name="see_camera_phone")
    th.start()
    started.wait(timeout=8)
    if "error" in box:
        return {"ok": False, "op": "phone", "status": "failed",
                "error": f"端口 {port} 起不来：{box['error']}"}

    _PHONE.update({"srv": box.get("runner"), "thread": th, "port": int(port), "loop": loop})
    url = f"http://{_lan_ip()}:{port}/"
    return {"ok": True, "op": "phone", "state": "running", "url": url, "port": int(port),
            "how": f"手机连同一个 WiFi，浏览器打开 {url} → 点「开始看」并允许摄像头",
            "landing": str(SHOT_DIR),
            "boundary": "手机拍的帧落 .scratch/camera/phone-*.jpg；本页不做人脸识别、不留云端"}


# ──────────────────────────────────────────────────────────────────────
# op: talk — 看 → 懂 → 说
# ──────────────────────────────────────────────────────────────────────
# COCO 80 类里常出现的中文名（检测层回的是英文类名，说出来得有中文）
_COCO_ZH = {
    "person": "人", "bicycle": "自行车", "car": "车", "motorcycle": "摩托车", "bus": "公交车",
    "train": "火车", "truck": "卡车", "traffic light": "红绿灯", "fire hydrant": "消防栓",
    "stop sign": "路牌", "bench": "长椅", "bird": "鸟", "cat": "猫", "dog": "狗", "horse": "马",
    "sheep": "羊", "cow": "牛", "elephant": "大象", "bear": "熊", "zebra": "斑马",
    "giraffe": "长颈鹿", "backpack": "背包", "umbrella": "伞", "handbag": "手提包",
    "tie": "领带", "bottle": "瓶子", "wine glass": "酒杯", "cup": "杯子", "fork": "叉子",
    "knife": "刀", "spoon": "勺", "bowl": "碗", "banana": "香蕉", "apple": "苹果",
    "orange": "橙子", "broccoli": "西兰花", "carrot": "胡萝卜", "pizza": "披萨",
    "donut": "甜甜圈", "cake": "蛋糕", "chair": "椅子", "couch": "沙发",
    "potted plant": "盆栽", "bed": "床", "dining table": "桌子", "toilet": "马桶",
    "tv": "电视", "laptop": "笔记本", "mouse": "鼠标", "remote": "遥控器",
    "keyboard": "键盘", "cell phone": "手机", "microwave": "微波炉", "oven": "烤箱",
    "toaster": "烤面包机", "sink": "水槽", "refrigerator": "冰箱", "book": "书",
    "clock": "钟", "vase": "花瓶", "scissors": "剪刀", "teddy bear": "玩偶",
    "hair drier": "吹风机", "toothbrush": "牙刷",
}

_DEFAULT_TALK_OPS = ("detect", "ocr")


def _unwrap(r, limit: int = 3) -> dict:
    """剥信封：api.run_task 的 result 可能套两层。"""
    x, n = r, 0
    while isinstance(x, dict) and isinstance(x.get("result"), dict) and n < limit:
        x = x["result"]
        n += 1
    return x if isinstance(x, dict) else {}


def _describe(det: dict) -> str:
    """把 detect 的 summary 说成人话。检测层只回类名，不编情节。"""
    summ = det.get("summary") or det.get("counts") or {}
    if not isinstance(summ, dict) or not summ:
        return ""
    parts = []
    for k, v in sorted(summ.items(), key=lambda kv: -int(kv[1] or 0)):
        name = _COCO_ZH.get(str(k).lower(), str(k))
        parts.append(f"{v} {name}" if int(v or 0) > 1 else name)
    return "我看到" + "、".join(parts[:8])


def talk(index: int = 0, question: str = "", speak: bool = True,
         ops: tuple | list | None = None, **_kw) -> dict:
    """看 → 懂 → 说。

    🔴 血账（2026-11-04）：最初把帧路径塞给 `body_eye` 的 `op=see`，
    结果 `see` **根本不看传进来的图，它自己截屏**（`vision_eye.py:90` 写明：
    「需要在入参里给出 image 的 op（`see` 例外，它自己截）」）。
    于是 `talk` 会拿**屏幕**的 OCR 冒充「摄像头看到的」，等于让她瞎编。
    现在改用**真吃外部图**的 op：`detect`（COCO 80 类真实物体）+ `ocr`（读画面里的字），
    并且校验 `image_size` 必须与我这帧一致，对不上就如实报不可信。
    """
    shot = snapshot(index=index)
    if not shot.get("ok"):
        return shot | {"op": "talk", "stage": "snapshot"}
    frame = shot.get("out")
    fw, fh = (shot.get("size") or [0, 0])[:2]
    res: dict = {"ok": False, "op": "talk", "frame": frame, "size": shot.get("size"),
                 "yavg": shot.get("yavg")}

    from . import api as _api
    said, notes = [], []

    for op in (ops or _DEFAULT_TALK_OPS):
        try:
            inner = _unwrap(_api.run_task("body_eye", {"op": op, "image": frame}))
        except Exception as e:  # noqa: BLE001
            notes.append(f"{op}: {type(e).__name__}: {e}")
            continue
        if not inner.get("ok"):
            notes.append(f"{op}: {inner.get('error') or inner.get('reason') or '无回应'}")
            continue

        if op == "detect":
            size = inner.get("image_size") or []
            if size and fw and fh and (int(size[0]), int(size[1])) != (int(fw), int(fh)):
                notes.append(f"detect 看的不是我这帧（{size} ≠ {[fw, fh]}），不采信")
                continue
            sent = _describe(inner)
            res["objects"] = inner.get("summary") or inner.get("counts")
            res["detect_backend"] = inner.get("backend")
            if sent:
                said.append(sent)
        elif op == "ocr":
            lanes = inner.get("lanes") or {}
            txt = inner.get("text") or ""
            if isinstance(lanes, dict):
                txt = txt or " ".join(str(v) for v in lanes.values() if isinstance(v, str))
            res["text"] = (txt or "")[:300]
            if txt:
                said.append(f"画面里有字：{txt[:80]}")

    if not said:
        res.update({"status": "needs_dependency", "op": "talk",
                    "error": "理解层没给出可说的内容（本位不脑补画面）",
                    "notes": notes[:4]})
        return res

    line = "；".join(said)
    if question:
        line += "。" + f"（问的是「{question}」：本地这层只报认得出的东西，不编答案）"
    res["said"] = line
    res["notes"] = notes[:4]

    if speak:
        try:
            sr = _unwrap(_api.run_task("body_say", {"text": line[:400]}))
            res["say"] = {"ok": bool(sr.get("ok")),
                          "backend": sr.get("backend"), "voice": sr.get("voice"),
                          "error": sr.get("error")}
        except Exception as e:  # noqa: BLE001
            res["say"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    res["ok"] = True
    res["boundary"] = "看的是摄像头真帧；认的是 COCO 80 类 + 画面文字，不做开放式问答"
    return res


def run(op: str = "status", **kw) -> dict:
    o = (op or "status").lower()
    if o == "status":
        return status(**kw)
    if o == "snapshot":
        return snapshot(index=int(kw.get("index") or 0), **_rest(kw, "index"))
    if o == "watch":
        return watch(index=int(kw.get("index") or 0), **_rest(kw, "index"))
    if o == "frame":
        return frame_b64(index=int(kw.get("index") or 0), **_rest(kw, "index"))
    if o == "phone":
        return phone(action=str(kw.get("action") or "start"), **_rest(kw, "action"))
    if o == "talk":
        return talk(index=int(kw.get("index") or 0), **_rest(kw, "index"))
    return {"ok": False, "op": o, "status": "needs_input", "fail_closed": True,
            "error": f"未知 op:{op}（{'/'.join(OPS)}）"}


def _rest(kw: dict, *used) -> dict:
    return {k: v for k, v in kw.items() if k not in used}
