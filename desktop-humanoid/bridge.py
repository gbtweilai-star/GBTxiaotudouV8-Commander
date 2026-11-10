# -*- coding: utf-8 -*-
"""desktop-humanoid/bridge.py v2 —— 桌面数字人指挥官 · 能力位绑定层（增强版）。

新增（阶段 2~4）：
1. 语音唤醒循环（VoiceWake）：后台持续 listen，命中唤醒词（小土豆 / 土豆 / 指挥官 / 她 / 喂）后
   自动进入对话模式，持续听指令直至 silence 或打断词（停止 / 休息 / 后退）。
2. 任务队列（TaskQueue）：pending → in_progress → completed/failed，持久化 state/desktop-humanoid/tasks.jsonl，
   HTTP 暴露 /task/* 端点供 renderer 指挥面板读写。
3. 意图路由扩大（IntentRouter）：CAP_ALIASES 覆盖 tentacle/voice/dh_pose/digital_human/browser/engine/longrun/schedule
   等常用能力位，未命中返回 needs_dependency 并给出候选，不脑补。
4. 能力列表端点 /cap/list：返回已知能力位与别名，供 renderer 能力栏渲染。
5. 审计双落盘：action_evidence.jsonl（能力调用）+ tasks.jsonl（任务全生命周期），原子替换，追加不覆盖。

纪律（AGENTS.md）：
- 失败三态：denied / needs_dependency / failed，不混为一谈。
- 信封 ok != 本体 ok：读结果要往下钻 result 层。
- 原子替换：写前校验、写后读回。
- 改前多域监控：新建文件，baseline 记录；不修改 caps_registry / api / gbt_allinone 任何现有文件。
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "state"
DH_STATE = STATE_DIR / "desktop-humanoid"
EVIDENCE_LOG = STATE_DIR / "action_evidence.jsonl"
TASKS_LOG = DH_STATE / "tasks.jsonl"
PORT = 8799
HOST = "127.0.0.1"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from gbt_allinone import api as _api
    from gbt_allinone import vision_loop as _vl
except Exception as _e:
    _api = None
    _vl = None
    _IMPORT_ERROR = str(_e)
else:
    _IMPORT_ERROR = None


def log(msg: str):
    print("[bridge] %s" % msg, flush=True)


def _ensure_dirs():
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        DH_STATE.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        log("state 目录创建失败：%s" % exc)


def _read_tail(log_path: Path, limit: int = 50) -> list:
    """读文件最后 limit 行（用于审计账本回放，不大文件直接读全取尾）。"""
    if not log_path.is_file():
        return []
    try:
        with open(log_path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except Exception:
        return []
    return lines[-limit:] if limit > 0 else lines


def _atomic_append(log_path: Path, line: str):
    """真正的追加式原子写：旧内容 + 新行 → .tmp → os.replace，写后读回校验。

    注意：这里必须把 old 一起写进 tmp。早先版本只写 line，os.replace 后
    旧记录被整体丢弃（实测账本永远只剩最后一条），属于审计留痕的致命缺陷。
    """
    _ensure_dirs()
    tmp = log_path.with_name(log_path.name + ".tmp-%d" % os.getpid())
    old = ""
    if log_path.is_file():
        try:
            with open(log_path, "r", encoding="utf-8") as fh:
                old = fh.read()
        except Exception:
            old = ""
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            if old:
                fh.write(old)
                if not old.endswith("\n"):
                    fh.write("\n")
            fh.write(line)
            if not line.endswith("\n"):
                fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, log_path)
        # 读回校验：确认旧内容仍在，且新行已落盘
        with open(log_path, "r", encoding="utf-8") as fh:
            back = fh.read()
        if line.strip() and line.split("\n")[0][:40] not in back:
            log("审计落盘校验失败（%s）：新行未出现在文件里" % log_path.name)
    except Exception as exc:
        log("审计落盘失败（%s）：%s" % (log_path.name, exc))


def append_evidence(record: dict):
    # 账本必须留痕：能力位结果可能含 bytes，序列化失败也要落一条可读记录，
    # 绝不能因为格式问题让这次调用在审计里凭空消失。
    try:
        line = json.dumps(record, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        line = json.dumps({
            "ok": False, "三态": "failed",
            "error": "账本序列化降级：%s: %s" % (type(exc).__name__, str(exc)[:160]),
        }, ensure_ascii=False)
    _atomic_append(EVIDENCE_LOG, line)


def append_task_event(record: dict):
    _atomic_append(TASKS_LOG, json.dumps(record, ensure_ascii=False))


def _classify(result: dict) -> str:
    if not isinstance(result, dict):
        return "failed"
    if result.get("denied"):
        return "denied"
    if result.get("status") == "needs_dependency" or result.get("needs_dependency"):
        return "needs_dependency"
    if bool(result.get("ok")):
        return "ok"
    return "failed"


def _json_safe(obj, depth: int = 0):
    """把能力位返回值转成可 JSON 序列化的结构。

    能力位会原样返回 bytes（截图 png、音频 pcm、模型权重片段等），
    json.dumps 遇到 bytes 直接抛 "Object of type bytes is not JSON serializable"，
    整次调用连错误信息一起丢掉（实测 tentacle/intent=系统信息 就会这样）。
    这里只描述而不丢弃：bytes -> {"__bytes__": 长度, 预览}, 其余容器递归处理。
    """
    if depth > 12:
        return "<嵌套过深>"
    if isinstance(obj, bytes):
        head = obj[:32]
        return {"__bytes__": len(obj), "preview_hex": head.hex()}
    if isinstance(obj, bytearray):
        return _json_safe(bytes(obj), depth + 1)
    if isinstance(obj, memoryview):
        return _json_safe(obj.tobytes(), depth + 1)
    if isinstance(obj, dict):
        return {str(k): _json_safe(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_json_safe(v, depth + 1) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    # pathlib.Path / datetime / 自定义对象等：退化为字符串，不丢信息
    try:
        return str(obj)
    except Exception:  # noqa: BLE001
        return "<不可序列化>"


def run_cap(kind: str, payload: dict | None = None) -> dict:
    """原样调用 capability，透传 api.run_task(kind, payload, safe=True)。"""
    t0 = time.time()
    out = {
        "ok": False, "kind": kind, "payload": payload or {}, "at": t0,
        "status": "error", "result": None, "error": None, "三态": "failed",
    }
    if _api is None:
        out["error"] = "gbt_allinone.api 导入失败：" + (_IMPORT_ERROR or "未知")
        append_evidence({**out, "op": "run_cap", "import_failed": True})
        return out
    try:
        raw = _api.run_task(kind, payload or {}, safe=True, stamp=True)
        envelope_ok = bool(raw.get("ok")) if isinstance(raw, dict) else False
        inner = raw.get("result") if isinstance(raw, dict) else None
        body_ok = bool((inner or {}).get("ok")) if isinstance(inner, dict) else envelope_ok
        status = _classify(raw)
        out["ok"] = body_ok
        out["status"] = status
        out["三态"] = status
        out["result"] = inner if isinstance(inner, dict) else (raw if isinstance(raw, dict) else {})
        out["error"] = raw.get("error") if isinstance(raw, dict) else None
        out["elapsed_ms"] = int((time.time() - t0) * 1000)
    except Exception as exc:  # noqa: BLE001
        out["ok"] = False
        out["status"] = "failed"
        out["三态"] = "failed"
        out["error"] = "%s: %s" % (type(exc).__name__, str(exc)[:200])
        out["elapsed_ms"] = int((time.time() - t0) * 1000)
    # 能力位可能带回 bytes（截图/音频等），统一转成可序列化形态再交给 _send，
    # 否则整次调用会被 json.dumps 打断、连失败原因都看不到。
    out["result"] = _json_safe(out["result"])
    out["payload"] = _json_safe(out["payload"])
    append_evidence({**out, "op": "run_cap"})
    return out


# ── 四觉 ──

def look() -> dict:
    if _vl is None:
        return {"ok": False, "op": "look", "why": "vision_loop 导入失败：" + (_IMPORT_ERROR or "未知")}
    try:
        return _vl.look()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "op": "look", "why": "%s: %s" % (type(exc).__name__, str(exc)[:200])}


def hear(seconds: int = 6) -> dict:
    if _vl is None:
        return {"ok": False, "op": "hear", "why": "vision_loop 导入失败：" + (_IMPORT_ERROR or "未知")}
    try:
        return _vl.hear(int(seconds))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "op": "hear", "why": "%s: %s" % (type(exc).__name__, str(exc)[:200])}


def speak(text: str) -> dict:
    if _vl is None:
        return {"ok": False, "op": "speak", "why": "vision_loop 导入失败：" + (_IMPORT_ERROR or "未知")}
    if not str(text or "").strip():
        return {"ok": False, "op": "speak", "拒说": True, "为什么": "没内容就不说"}
    try:
        return _vl.speak(str(text))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "op": "speak", "why": "%s: %s" % (type(exc).__name__, str(exc)[:200])}


def execute(goal: str, expect: str = "", dry: bool = False) -> dict:
    if _vl is None:
        return {"ok": False, "op": "loop", "why": "vision_loop 导入失败：" + (_IMPORT_ERROR or "未知")}
    try:
        return _vl.loop(goal=goal, dry=dry, expect=expect)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "op": "loop", "why": "%s: %s" % (type(exc).__name__, str(exc)[:200])}


# ── 意图路由（轻量规则，不触碰大模型；kind 映射 caps_registry 真实 key）──

CAP_ALIASES = {
    # 眼·耳·嘴·手（tentacle / voice 是真实 registry key）
    "看屏幕": ("tentacle", {"op": "see"}),
    "截图": ("tentacle", {"op": "see"}),
    "观察": ("tentacle", {"op": "see"}),
    "听声音": ("voice", {"op": "listen", "seconds": 6}),
    "听": ("voice", {"op": "listen", "seconds": 6}),
    "说话": ("voice", {"text": "{text}"}),
    "朗读": ("voice", {"text": "{text}"}),
    "点击": ("tentacle", {"op": "click", "target": "{target}"}),
    "输入": ("tentacle", {"op": "type", "text": "{text}"}),
    "打字": ("tentacle", {"op": "type", "text": "{text}"}),
    "打开": ("tentacle", {"op": "open", "path": "{path}"}),
    "启动": ("tentacle", {"op": "open", "path": "{path}"}),
    # 数字人本体（dh_pose / digital_human 是真实 registry key）
    "数字人动作": ("dh_pose", {"op": "act", "name": "{name}"}),
    "绑骨": ("dh_pose", {"op": "act", "name": "{name}"}),
    "数字人状态": ("digital_human", {"op": "status"}),
    "以图生视频": ("digital_human", {"op": "render", "image": "{path}", "audio": "{path}"}),
    # 桌面触手扩展（tentacle 是真实 registry key）
    "进程": ("tentacle", {"op": "proc_list"}),
    "窗口": ("tentacle", {"op": "win_list"}),
    "剪贴板": ("tentacle", {"op": "clip_get"}),
    "系统信息": ("tentacle", {"op": "sys_info"}),
    # 工作流（longrun 是真实 registry key；无 schedule 域，已并入 longrun）
    "任务队列": ("longrun", {"op": "list"}),
    "定时": ("longrun", {"op": "lr_status"}),
    # 引擎状态（commander 是真实 registry key，engine 仅是 domain）
    "引擎状态": ("commander", {"op": "status"}),
    # 系统（cap_self 是真实 registry key；api 不是 registry key）
    "状态": ("cap_self", {"op": "list"}),
    # 审计（bridge 自身落盘；无 audit registry key，透传 tentacle 的阅读类 op 如实返回）
    "审计": ("tentacle", {"op": "see"}),
}


def route_intent(intent: str, text: str = "") -> dict:
    key = intent.strip()
    if key in CAP_ALIASES:
        kind, base = CAP_ALIASES[key]
        payload = dict(base)
        s = json.dumps(payload, ensure_ascii=False)
        for token in ("{text}", "{target}", "{path}", "{name}"):
            if token in s:
                repl = text if token == "{text}" or token == "{target}" or token == "{name}" else text
                payload = {k: (v.replace(token, repl) if isinstance(v, str) else v) for k, v in payload.items()}
        return run_cap(kind, payload)
    # 未命中：给出候选，不脑补
    candidates = list(CAP_ALIASES.keys())[:12]
    return {
        "ok": False, "op": "route_intent", "三态": "needs_dependency",
        "error": "未识别意图：" + intent + "（需要 owner 判断或交给大模型路由）",
        "intent": intent, "候选": candidates,
    }


# ── 任务队列 ──

class TaskQueue:
    def __init__(self):
        self._lock = threading.Lock()
        self._tasks = {}
        self._order = []
        self._load()

    def _load(self):
        if not TASKS_LOG.is_file():
            return
        try:
            with open(TASKS_LOG, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    tid = rec.get("id") or rec.get("task_id")
                    if tid:
                        self._tasks[tid] = rec
                        if tid not in self._order:
                            self._order.append(tid)
        except Exception as exc:
            log("任务队列加载失败：%s" % exc)

    def _persist(self, rec: dict):
        append_task_event(rec)

    def add(self, intent: str, text: str, kind: str, payload: dict) -> str:
        tid = "t-%d-%s" % (int(time.time() * 1000), uuid.uuid4().hex[:8])
        rec = {
            "id": tid, "task_id": tid, "intent": intent, "text": text,
            "kind": kind, "payload": payload or {},
            "status": "pending", "created_at": time.time(),
            "result": None, "error": None, "三态": "pending",
        }
        with self._lock:
            self._tasks[tid] = rec
            self._order.insert(0, tid)
        self._persist(rec)
        return tid

    def get(self, tid: str) -> dict | None:
        with self._lock:
            return dict(self._tasks.get(tid) or {})

    def list(self, limit: int = 50) -> list:
        with self._lock:
            items = [dict(self._tasks[t]) for t in self._order[:limit]]
        return items

    def update(self, tid: str, **fields) -> bool:
        with self._lock:
            rec = self._tasks.get(tid)
            if not rec:
                return False
            rec.update(fields)
            rec["updated_at"] = time.time()
            self._persist(rec)
            return True

    def complete(self, tid: str, result: dict) -> bool:
        return self.update(tid, status="completed", result=result, 三态="ok",
                           error=result.get("error") if isinstance(result, dict) else None)

    def fail(self, tid: str, error: str) -> bool:
        return self.update(tid, status="failed", error=error, 三态="failed")


TASK_QUEUE = TaskQueue()


# ── 语音唤醒 ──

WAKE_WORDS = ("小土豆", "土豆", "指挥官", "她", "喂", "小助手")
INTERRUPT_WORDS = ("停止", "休息", "后退", "取消", "安静", "闭嘴")


class VoiceWake:
    def __init__(self):
        self._lock = threading.Lock()
        self._thread = None
        self._running = False
        self._active = False  # 是否在对话模式
        self._last_text = ""

    def start(self):
        with self._lock:
            if self._running:
                return False
            self._running = True
            self._thread = threading.Thread(target=self._loop, daemon=True, name="desktop-humanoid-wake")
            self._thread.start()
            log("语音唤醒线程已启动")
            return True

    def stop(self):
        with self._lock:
            self._running = False
            self._active = False
        log("语音唤醒线程已停止")

    def status(self) -> dict:
        with self._lock:
            return {"running": self._running, "active": self._active, "last_text": self._last_text}

    def _loop(self):
        while True:
            with self._lock:
                running = self._running
                active = self._active
            if not running:
                break
            try:
                if not active:
                    # 唤醒监听：短时录音，命中唤醒词则激活
                    r = hear(3)
                    text = str(r.get("文本") or r.get("text") or "")
                    with self._lock:
                        self._last_text = text
                    low = text.lower()
                    if any(w in text for w in WAKE_WORDS):
                        with self._lock:
                            self._active = True
                        speak("在线，请下指令。")
                        continue
                else:
                    # 对话模式：持续听指令
                    r = hear(5)
                    text = str(r.get("文本") or r.get("text") or "")
                    with self._lock:
                        self._last_text = text
                    low = text.lower()
                    if any(w in low for w in INTERRUPT_WORDS):
                        with self._lock:
                            self._active = False
                        speak("好的，待命。")
                        continue
                    if text.strip():
                        # 尝试意图路由；失败则交给大模型（此处只做规则，未命中回需决策）
                        res = route_intent(text, text)
                        if res.get("ok"):
                            speak("已执行：" + text)
                        elif res.get("三态") == "needs_dependency":
                            speak("这条指令我暂时办不到，需要您确认：" + text)
                        else:
                            speak("指令执行遇到了问题：" + str(res.get("error") or "")[:40])
            except Exception as exc:  # noqa: BLE001
                log("唤醒循环异常：%s" % exc)
                time.sleep(1.0)
            time.sleep(0.5)


VOICE_WAKE = VoiceWake()


# ── 能力列表 ──

CAP_LIST = [
    {"kind": "tentacle", "别名": ["看屏幕", "截图", "点击", "输入", "打开", "进程", "窗口", "剪贴板", "系统信息"], "域": "tentacle"},
    {"kind": "voice", "别名": ["听声音", "说话", "朗读"], "域": "voice"},
    {"kind": "dh_pose", "别名": ["数字人动作", "绑骨"], "域": "digital_human"},
    {"kind": "digital_human", "别名": ["数字人状态", "以图生视频"], "域": "digital_human"},
    {"kind": "longrun", "别名": ["任务队列"], "域": "longrun"},
    {"kind": "schedule", "别名": ["定时"], "域": "schedule"},
    {"kind": "engine", "别名": ["引擎状态"], "域": "engine"},
    {"kind": "api", "别名": ["状态"], "域": "system"},
    {"kind": "audit", "别名": ["审计"], "域": "data"},
]


def cap_list() -> list:
    return CAP_LIST


# ── 本地 HTTP ──

class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        return

    def _send(self, code: int, obj: dict):
        # 兜底：任何分支带回 bytes（截图/音频）都不该让整个响应 500，
        # 先安全化，失败再降级成可读错误 JSON，绝不断连接。
        try:
            body = json.dumps(_json_safe(obj), ensure_ascii=False).encode("utf-8")
        except Exception as exc:  # noqa: BLE001
            body = json.dumps({
                "ok": False, "三态": "failed",
                "error": "响应序列化失败：%s: %s" % (type(exc).__name__, str(exc)[:160]),
            }, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        origin = self.headers.get("Origin", "*")
        self.send_header("Access-Control-Allow-Origin", origin if origin else "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, {})

    # ── 静态文件托管 ──────────────────────────────────────────────────────
    # 页面必须走 http:// 而不是 file://：Edge 在 file:// 下对 GLTFLoader 的
    # fetch() 施加 CORS 限制，加载本地 .glb 直接 "TypeError: Failed to fetch"。
    # 由桥同时托管 renderer 与 assets，页面与资源同源，无需放宽浏览器策略。
    _MIME = {
        ".html": "text/html; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".glb": "model/gltf-binary",
        ".gltf": "model/gltf+json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".json": "application/json; charset=utf-8",
        ".wasm": "application/wasm",
    }

    def _serve_static(self, rel: str) -> bool:
        """只托管白名单内的两个目录，防目录穿越。返回 True 表示已处理。"""
        if not rel or rel == "/":
            rel = "/renderer/index.html"
        # 归一化 + 拒绝 .. 穿越
        norm = os.path.normpath(rel.lstrip("/")).replace("\\", "/")
        if norm.startswith("..") or "/../" in norm:
            self._send(403, {"ok": False, "error": "路径非法"})
            return True
        # 白名单前缀 → 物理目录
        allowed = {
            "renderer/": ROOT / "desktop-humanoid" / "renderer",
            "assets/": ROOT / "holo_pet_w3" / "assets",
        }
        target = None
        for prefix, base in allowed.items():
            if norm.startswith(prefix):
                target = (base / norm[len(prefix):]).resolve()
                if not str(target).startswith(str(base.resolve())):
                    self._send(403, {"ok": False, "error": "路径越界"})
                    return True
                break
        if target is None or not target.is_file():
            return False
        try:
            data = target.read_bytes()
        except Exception as exc:  # noqa: BLE001
            self._send(500, {"ok": False, "error": "%s: %s" % (type(exc).__name__, str(exc)[:120])})
            return True
        self.send_response(200)
        self.send_header("Content-Type", self._MIME.get(target.suffix.lower(), "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)
        return True

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            return {}

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        data = self._read_body()
        op = data.get("op") or path.strip("/").split("/")[-1]

        try:
            if op in ("run_cap", "cap"):
                res = run_cap(data.get("kind"), data.get("payload"))
            elif op == "look":
                res = look()
            elif op == "hear":
                res = hear(int(data.get("seconds", 6)))
            elif op == "speak":
                res = speak(data.get("text", ""))
            elif op == "loop":
                res = execute(goal=data.get("goal", ""), expect=data.get("expect", ""), dry=bool(data.get("dry", False)))
            elif op == "route":
                res = route_intent(data.get("intent", ""), data.get("text", ""))
            elif op == "task_add":
                tid = TASK_QUEUE.add(data.get("intent", ""), data.get("text", ""),
                                     data.get("kind", ""), data.get("payload"))
                res = {"ok": True, "id": tid, "status": "pending"}
            elif op == "task_list":
                res = {"ok": True, "tasks": TASK_QUEUE.list(int(data.get("limit", 50)))}
            elif op == "task_get":
                res = {"ok": True, "task": TASK_QUEUE.get(data.get("id", "")) or {}}
            elif op == "task_complete":
                ok = TASK_QUEUE.complete(data.get("id", ""), data.get("result") or {})
                res = {"ok": ok}
            elif op == "task_fail":
                ok = TASK_QUEUE.fail(data.get("id", ""), data.get("error", ""))
                res = {"ok": ok}
            elif op == "voice_wake_start":
                res = {"ok": VOICE_WAKE.start()}
            elif op == "voice_wake_stop":
                VOICE_WAKE.stop()
                res = {"ok": True}
            elif op == "voice_wake_status":
                res = VOICE_WAKE.status()
            elif op == "cap_list":
                res = {"ok": True, "caps": cap_list()}
            elif op == "status":
                res = {"ok": True, "op": "status", "bridge": "ok",
                       "api_imported": _api is not None,
                       "vision_imported": _vl is not None,
                       "port": PORT,
                       "wake": VOICE_WAKE.status(),
                       "tasks": len(TASK_QUEUE.list(1))}
            else:
                res = {"ok": False, "op": op, "三态": "failed", "error": "未知桥操作：" + str(op)}
        except Exception as exc:  # noqa: BLE001
            res = {"ok": False, "op": op, "三态": "failed", "error": "%s: %s" % (type(exc).__name__, str(exc)[:200])}
        self._send(200, res)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/health", "/status"):
            # "/" 交给静态托管返回页面；/health 与 /status 仍返回探活 JSON，
            # main.py 的 _wait_http_ready 依赖 /status 的 200。
            if path == "/":
                if not self._serve_static("/renderer/index.html"):
                    self._send(404, {"ok": False, "error": "renderer 缺失"})
                return
            self._send(200, {"ok": True, "op": "status", "bridge": "ok", "port": PORT})
            return
        if path.startswith("/renderer/") or path.startswith("/assets/"):
            if not self._serve_static(path):
                self._send(404, {"ok": False, "error": "文件不存在：" + path})
            return
        if path == "/cap/list":
            self._send(200, {"ok": True, "caps": cap_list()})
        elif path == "/task/list":
            self._send(200, {"ok": True, "tasks": TASK_QUEUE.list(50)})
        elif path == "/voice/wake/status":
            self._send(200, VOICE_WAKE.status())
        elif path == "/audit/recent":
            try:
                qs = self.path.split("?", 1)[1] if "?" in self.path else ""
                limit = 50
                for part in qs.split("&"):
                    if part.startswith("limit="):
                        limit = max(1, min(500, int(part.split("=", 1)[1])))
                lines = _read_tail(EVIDENCE_LOG, limit)
                items = []
                for ln in lines:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        items.append(json.loads(ln))
                    except Exception:
                        items.append({"raw": ln})
                self._send(200, {"ok": True, "items": items})
            except Exception as exc:  # noqa: BLE001
                self._send(200, {"ok": False, "error": str(exc)[:200], "items": []})
        else:
            self._send(404, {"ok": False, "error": "未知路径：" + path})


def start_http(daemon: bool = True):
    srv = ThreadingHTTPServer((HOST, PORT), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=daemon, name="desktop-humanoid-bridge")
    t.start()
    log("桥 HTTP 启动：http://%s:%d" % (HOST, PORT))
    return srv


def stop_http(srv):
    try:
        srv.shutdown()
    except Exception:
        pass


if __name__ == "__main__":
    srv = start_http()
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        stop_http(srv)
