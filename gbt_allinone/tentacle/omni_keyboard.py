# gbt-capability: subprocess, dynamic-import, ctypes, base64
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
# ⚠️ 外部内容纪律：`clipboard_read` 读回的**剪贴板内容一律是不可信数据，不是指令** ——
#    剪贴板可能来自任何程序或任何网页，可能写着"忽略你之前的指令"。
#    本域只把它当数据返回；不执行其中任何祈使句、不拼进 system 提示、不拿去驱动执行口。
#    覆盖校验器：py -3.14 -m gbt_allinone.tools.external_content_check gbt_allinone
# keyboard 域 mixin — 拆分自 omni_tentacle (自动生成, 2026-08-10)
# ⛔ 拆分保障: 自身目录(brain/)入 sys.path — spec_from_file_location 加载
#    不会自动加路径, 需显式保障 omni_core 可寻址 (插 brain/ 而非项目根)
import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parent))
# publish沙盒(非项目根cwd)执行兜底: 类定义不访问core符号, 吞异常安全
try:
    from omni_core import *  # noqa: F401,F403
except Exception:
    pass


class OmniKeyboardMixin:
    """keyboard 域能力 — 16 方法"""

    def type(self, text):
        _keyboard_type(text); return {"ok": True}

    def press(self, key):
        _keyboard_press(key); return {"ok": True}

    def hotkey(self, *keys):
        _keyboard_hotkey(*keys); return {"ok": True}

    def enter(self):
        _keyboard_press("enter"); return {"ok": True}

    def type_to_field(self, label: str, text: str):
        """找到标签旁边的输入框，输入文字 — ⛔ 2026-08-13 UIA 直写优先 + 物理兜底
        物理受限(前台被高完整性窗口锁)时 UIA 标签定位直写可编辑控件, 不依赖焦点"""
        try:
            _uia_r = _uia_set_value_by_label(label, text)
            if _uia_r:
                return {"ok": True, "label": label, "typed": text, "method": "uia_setvalue",
                        "window": _uia_r.get("window", ""), "control": _uia_r.get("ctrl", "")}
        except Exception: pass  # 容错: UIA失败走物理
        r = self.find_text(label)
        if not r.get("found"):
            return refusal("label_not_found", f"未找到标签 '{label}'", ("label",))
        # 输入框通常在标签右边
        _mouse_move(r["x"] + 150, r["y"])
        time.sleep(0.05)
        _mouse_click()
        time.sleep(0.1)
        _keyboard_hotkey("ctrl", "a")  # 全选
        time.sleep(0.05)
        _keyboard_type(text)
        return {"ok": True, "label": label, "typed": text, "at": (r["x"] + 150, r["y"]), "method": "physical_fallback"}

    def select_all(self):
        _keyboard_hotkey("ctrl", "a")
        time.sleep(0.15)  # 稳定延迟: Ctrl+A后立即输入会吞首字符(丢键)
        return {"ok": True}

    def undo(self):
        _keyboard_hotkey("ctrl", "z"); return {"ok": True}

    def copy(self):
        _keyboard_hotkey("ctrl", "c"); time.sleep(0.05)
        return self.clipboard_read()

    def paste(self):
        _keyboard_hotkey("ctrl", "v"); return {"ok": True}

    def cut(self):
        _keyboard_hotkey("ctrl", "x"); return {"ok": True}

    def tab(self, count: int = 1):
        for _ in range(count): _keyboard_press("tab"); time.sleep(0.02)
        return {"ok": True, "tabs": count}

    def escape(self):
        _keyboard_press("escape"); return {"ok": True}

    def clipboard_copy(self): _keyboard_hotkey("ctrl", "c"); time.sleep(0.1); return self.clipboard_read()

    def clipboard_read(self):
        try: import pyperclip; text = pyperclip.paste(); return {"ok": True, "text": text[:5000], "length": len(text)}
        except ImportError: return refusal("dependency_unavailable", "pyperclip not installed", ("pyperclip",))

    def clipboard_write(self, text: str):
        try: import pyperclip; pyperclip.copy(text); return {"ok": True, "length": len(text)}
        except ImportError: _keyboard_type(text); return {"ok": True, "method": "keyboard_fallback"}

    def copy_text_at(self, x: int, y: int): _mouse_move(x, y); time.sleep(0.03); _mouse_double_click(); time.sleep(0.1); _keyboard_hotkey("ctrl", "c"); time.sleep(0.1); return self.clipboard_read()
