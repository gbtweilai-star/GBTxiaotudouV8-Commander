"""块2 镜像：在块1镜像之上叠加「面板自建实例废弃 / 连接所有权移交」。

产物：.scratch/codex_v2_mirror/panel_server_mirror2.py（块1镜像 + 块2补丁）
本脚本自校验：
  1) 每个锚点唯一命中（不许猜）
  2) difflib 行级对照，输出块2 的真实改动区间
  3) 未改动区间与块1镜像逐行一致
"""
from __future__ import annotations
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])

import difflib
import hashlib
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(_GBT_ROOT)
SRC = ROOT / ".scratch" / "codex_v2_mirror" / "panel_server_mirror.py"
DST = ROOT / ".scratch" / "codex_v2_mirror" / "panel_server_mirror2.py"
LINEMAP = ROOT / ".scratch" / "panel_server_mirror2.line-map.md"

src = SRC.read_text(encoding="utf-8")
text = src


def sub(old: str, new: str, tag: str) -> None:
    global text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"ANCHOR-FAIL[{tag}] count={n}")
    text = text.replace(old, new, 1)
    print(f"  ok  {tag}")


print("=" * 72)
print("块2 镜像构建（基座 = 块1镜像 panel_server_mirror.py）")
print("=" * 72)

# ---------- T0：模块级 helper（谁挂谁摘的身份判定） ----------
old_clip = '''def _clip(value, limit: int = 320) -> str:'''
new_clip = '''def _is_same_hook(current, target) -> bool:
    """块2 用：判断 server 上的钩子是否就是"自己挂上去的那一个"。

    收口后共享连接归路由所有，面板只许摘掉自己挂的钩子（S3 谁挂谁摘）；
    别人的钩子一个也不许碰。绑定方法每次属性访问都会新建对象，
    所以先用 is 再用 ==（绑定方法 == 比较 __self__/__func__）。
    """
    if current is None or target is None:
        return False
    if current is target:
        return True
    try:
        return bool(current == target)
    except Exception:  # noqa: BLE001
        return False


def _clip(value, limit: int = 320) -> str:'''
sub(old_clip, new_clip, "T0 helper _is_same_hook")

# ---------- T1：__init__ 不再自持就绪布尔位 ----------
old_init = '''        self._codex = None
        self._codex_ready = False
'''
new_init = '''        # 块2：_codex 是"共享连接的本地句柄"（只引用、不拥有）；
        # _codex_ready 已改为派生属性（见同 class 的 @property），面板不再自持就绪布尔位。
        self._codex = None
'''
sub(old_init, new_init, "T1 __init__ 去掉 _codex_ready 赋值")

# ---------- T2：派生属性（唯一真值源） ----------
old_load = '''    def _load_config(self) -> dict:'''
new_load = '''    @property
    def _codex_ready(self) -> bool:
        """块2 收口：就绪 == 路由共享连接可用（唯一真值源，不再面板自持）。

        收口前：谁建的谁记账，面板私有实例死了也可能仍报 ready。
        收口后：连接所有权在路由，面板只是借用方 → "就绪"必须问共享单例本身。
        先看本地句柄（常路径，零开销），再回落问 CB.status()，两处同源不会打架。
        """
        server = self._codex
        if server is not None and server.alive:
            return True
        return bool(CB.status().get("connected"))

    def _load_config(self) -> dict:'''
sub(old_load, new_load, "T2 _codex_ready 派生属性")

# ---------- T3：start() 改挂载 ----------
old_start = '''    def start(self, wait_seconds: float = 0.0) -> bool:
        """启动本地面板桥；等待秒数为 0 时在后台初始化 Codex。"""
        self._ensure_fallback()
        if not wait_seconds:
            threading.Thread(
                target=self._start_codex,
                name="gbt-holo-codex-start",
                daemon=True,
            ).start()
            return True
        return self._start_codex(wait_seconds=wait_seconds)'''
new_start = '''    def start(self, wait_seconds: float = 0.0) -> bool:
        """启动本地面板桥；等待秒数为 0 时在后台挂载 Codex 共享连接。"""
        self._ensure_fallback()
        if not wait_seconds:
            threading.Thread(
                target=self._attach_shared,
                name="gbt-holo-codex-start",
                daemon=True,
            ).start()
            return True
        return self._attach_shared(wait_seconds=wait_seconds)'''
sub(old_start, new_start, "T3 start() 改 _attach_shared")

# ---------- T4：自建实例 -> 挂载共享单例 ----------
old_make = '''    def _start_codex(self, wait_seconds: float = 25.0) -> bool:
        with self._lock:
            if self._codex_ready and self._codex is not None:
                return True
            if not CB.find_codex():
                self._last_error = "Codex executable not found"
                self.bus.publish("status", codex="unavailable", detail=self._last_error)
                return False
            try:
                codex_cfg = self.config.get("codex", {}) or {}
                server = CB.CodexAppServer(
                    cwd=codex_cfg.get("cwd") or str(_ROOT),
                    codex_home=codex_cfg.get("codex_home") or None,
                    on_event=self._on_codex_event,
                    on_approval=self._on_approval,
                )
                server.start(timeout=wait_seconds)
                self._codex = server
                self._codex_ready = True
                self._last_error = ""
                self.bus.publish(
                    "status",
                    codex="ready",
                    detail=_clip(server.status().get("server"), 200),
                )
                return True
            except Exception as exc:  # noqa: BLE001
                self._codex_ready = False
                self._last_error = str(exc)[:240]
                self.bus.publish("status", codex="degraded", detail=self._last_error)
                return False'''
new_make = '''    def _attach_shared(self, wait_seconds: float = 25.0) -> bool:
        """块2：不再自建 app-server，改为挂载路由的共享单例（连接所有权移交）。

        收口前 —— 面板 new 一个 CodexAppServer，自己 start/stop，连接是面板私产。
        收口后 —— 面板只是借用方；共享连接的生命周期归路由（codex_bridge._shared）。

        诚实声明（不假装已解决）：get_shared_server(**kwargs) 的 kwargs
        只在"首次创建"时生效（codex_bridge.py:1334-1348）；若共享单例已由别的
        调用方建好，本次传入的 on_event/on_approval 不会挂上去。事件流归属
        由块4（事件流改道）处理，本块只做所有权移交。
        """
        with self._lock:
            if self._codex is not None and self._codex.alive:
                return True
            if not CB.find_codex():
                self._last_error = "Codex executable not found"
                self.bus.publish("status", codex="unavailable", detail=self._last_error)
                return False
            try:
                codex_cfg = self.config.get("codex", {}) or {}
                server = CB.get_shared_server(
                    cwd=codex_cfg.get("cwd") or str(_ROOT),
                    codex_home=codex_cfg.get("codex_home") or None,
                    on_event=self._on_codex_event,
                    on_approval=self._on_approval,
                )
                if not server.alive:
                    server.start(timeout=wait_seconds)
                self._codex = server
                self._last_error = ""
                self.bus.publish(
                    "status",
                    codex="ready",
                    detail=_clip(server.status().get("server"), 200),
                )
                return True
            except Exception as exc:  # noqa: BLE001
                self._last_error = str(exc)[:240]
                self.bus.publish("status", codex="degraded", detail=self._last_error)
                return False'''
sub(old_make, new_make, "T4 _start_codex -> _attach_shared（get_shared_server）")

# ---------- T5：stop() 只解挂，绝不销毁 ----------
old_stop = '''    def stop(self) -> None:
        with self._lock:
            server = self._codex
            self._codex = None
            self._codex_ready = False
        if server is not None:
            try:
                server.stop()
            except Exception:
                pass'''
new_stop = '''    def stop(self) -> None:
        """块2 / S2 铁律：只解挂，不销毁。

        共享连接的所有权在路由（codex_bridge._shared）；面板交出的只是
        "本地句柄 + 自己挂上去的那些钩子"。这里绝不许出现
        server.stop() / CB.shutdown_shared()——那会顺手把路由正在用的桥干掉
        （收口前 :208 server.stop() 正是这颗雷）。
        """
        with self._lock:
            server = self._codex
            self._codex = None
        if server is None:
            return
        # S3 谁挂谁摘：只摘自己挂上的，别人的钩子一个也不碰。
        try:
            if _is_same_hook(getattr(server, "on_event", None), self._on_codex_event):
                server.on_event = None
        except Exception:  # noqa: BLE001
            pass
        try:
            if _is_same_hook(getattr(server, "on_approval", None), self._on_approval):
                server.on_approval = None
        except Exception:  # noqa: BLE001
            pass'''
sub(old_stop, new_stop, "T5 stop() 只解挂（拆 :208 雷）")

# ---------- T6：state() 两个口径同源 ----------
old_state = '''            "codex_ready": bool(self._codex_ready),'''
new_state = '''            "codex_ready": self._codex_ready,'''
sub(old_state, new_state, "T6 state().codex_ready 同源")

DST.write_text(text, encoding="utf-8", newline="")

# ---------------- 自校验 ----------------
a = src.splitlines()
b = text.splitlines()
sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
print("\n-- 块2 行级改动区间（块1镜像 -> 块2镜像，1-based）--")
rows = []
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == "equal":
        continue
    rows.append((tag, i1 + 1, i2, j1 + 1, j2, i2 - i1, j2 - j1))
    print(f"  {tag:8s} mirror1[{i1+1:>4}-{i2:>4}] -> mirror2[{j1+1:>4}-{j2:>4}]  "
          f"(-{i2-i1} / +{j2-j1})")

equal_ok = all(
    a[i1:i2] == b[j1:j2]
    for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag == "equal"
)
print(f"\n未改动区间逐行一致: {equal_ok}")
print(f"块1镜像 sha256: {hashlib.sha256(SRC.read_bytes()).hexdigest()}")
print(f"块2镜像 sha256: {hashlib.sha256(DST.read_bytes()).hexdigest()}")
_lf_only = b"\r\n" not in DST.read_bytes()
print(f"块２镜像行数: {len(b)}  LF-only: {_lf_only}")

rows_md = "\n".join(
    f"| {t} | {i1}-{i2} | {j1}-{j2} | -{d1} / +{d2} |" for t, i1, i2, j1, j2, d1, d2 in rows
)
LINEMAP.write_text(f"""# 块2 镜像行号对照表（panel_server_mirror.py -> panel_server_mirror2.py）

- 基座：`.scratch/codex_v2_mirror/panel_server_mirror.py`（块1镜像，净增 +24）
- 产物：`.scratch/codex_v2_mirror/panel_server_mirror2.py`（块1 + 块2）
- 块1镜像 sha256：`{hashlib.sha256(SRC.read_bytes()).hexdigest()}`
- 块2镜像 sha256：`{hashlib.sha256(DST.read_bytes()).hexdigest()}`
- 未改动区间逐行一致：`{equal_ok}`

## 块2 改动区间（1-based）

| op | mirror1 | mirror2 | 行数变化 |
|---|---|---|---|
{rows_md}

## 块2 七处补丁

| tag | 内容 |
|---|---|
| T0 | 模块级 `_is_same_hook()`：谁挂谁摘的身份判定（绑定方法用 `==`） |
| T1 | `__init__` 去掉 `self._codex_ready = False`（改为派生属性） |
| T2 | `@property _codex_ready`：唯一真值源 = 路由共享连接可用 |
| T3 | `start()` 后台目标 `_start_codex` -> `_attach_shared` |
| T4 | `_start_codex()` -> `_attach_shared()`：`CB.get_shared_server()` 取代自建实例 |
| T5 | `stop()` 只解挂：拆掉原 `:208 server.stop()` 这颗雷（S2） |
| T6 | `state().codex_ready` 与 `codex["connected"]` 同源 |

> 生产 `holo_pet/panel_server.py` 本块一行未动；块1 的三处入口（P1/P2/P3）本块一行未动。
""", encoding="utf-8", newline="")
print("行号对照表:", LINEMAP)
