# gbt-capability: integration
"""魔珐星云（Xingyun）实时数字人接入桥。

凭证读取顺序：
1. ``GBT_XINGYUN_APP_ID`` / ``GBT_XINGYUN_APP_SECRET`` 环境变量；
2. 框架 store 下的 Windows DPAPI 加密文件。

本模块只负责凭证与 SDK 状态，不替主人做任何外发动作。App Secret 只会在
本机回环请求、且在面板显式进入星云形象时返回给前端 SDK；任何日志、审计和
状态接口都只输出掩码，不输出明文。
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
from pathlib import Path

from ._paths import STORE_DIR
from .safe_io import atomic_write_bytes

GATEWAY_SERVER = "https://nebula-agent.xingyun3d.com/user/v1/ttsa_v2/session"
SDK_CDN = "https://media.xingyun3d.com/xingyun3d/general/litesdk/xmovAvatar_e2e@latest.js"
_DPAPI_ENTROPY = b"GBTxiaotudouV8:xingyun:v1"
_DEFAULT_SECRET_FILE = Path(STORE_DIR) / "secrets" / "xingyun_app.dpapi"
SDK_FILE = Path(__file__).resolve().parent.parent / "holo_pet" / "xingyun_e2e.latest.js"
_HEX32 = set("0123456789abcdef")


class XingyunError(RuntimeError):
    """星云接入错误。"""


def _secret_file() -> Path:
    raw = os.environ.get("GBT_XINGYUN_SECRET_FILE", "").strip()
    return Path(raw).expanduser().resolve() if raw else _DEFAULT_SECRET_FILE


def _env_credentials() -> tuple[str, str, str]:
    app_id = os.environ.get("GBT_XINGYUN_APP_ID", "").strip()
    app_secret = os.environ.get("GBT_XINGYUN_APP_SECRET", "").strip()
    if app_id and app_secret:
        return app_id, app_secret, "env:GBT_XINGYUN_APP_ID"
    return "", "", ""


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_ulong),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _blob(raw: bytes):
    buf = ctypes.create_string_buffer(raw, len(raw))
    return (_DataBlob(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))), buf)


def _protect_dpapi(data: bytes) -> bytes:
    if os.name != "nt":
        raise XingyunError("当前系统不支持 Windows DPAPI")
    try:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        crypt32.CryptProtectData.argtypes = [
            ctypes.POINTER(_DataBlob), ctypes.c_wchar_p,
            ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_ulong, ctypes.POINTER(_DataBlob),
        ]
        crypt32.CryptProtectData.restype = ctypes.c_int
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p

        input_blob, input_buf = _blob(data)
        entropy_blob, entropy_buf = _blob(_DPAPI_ENTROPY)
        output = _DataBlob()
        ok = crypt32.CryptProtectData(
            ctypes.byref(input_blob),
            "GBT小土豆V8 Xingyun credential",
            ctypes.byref(entropy_blob),
            None,
            None,
            0x1,
            ctypes.byref(output),
        )
        _keepalive = (input_buf, entropy_buf)
        if not ok:
            raise XingyunError("DPAPI 加密失败")
        try:
            return ctypes.string_at(output.pbData, output.cbData)
        finally:
            kernel32.LocalFree(output.pbData)
    except XingyunError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise XingyunError(f"DPAPI 不可用：{str(exc)[:160]}") from exc


def _unprotect_dpapi(data: bytes) -> bytes:
    if os.name != "nt":
        raise XingyunError("当前系统不支持 Windows DPAPI")
    try:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        crypt32.CryptUnprotectData.argtypes = [
            ctypes.POINTER(_DataBlob), ctypes.POINTER(ctypes.c_wchar_p),
            ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_ulong, ctypes.POINTER(_DataBlob),
        ]
        crypt32.CryptUnprotectData.restype = ctypes.c_int
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p

        input_blob, input_buf = _blob(data)
        entropy_blob, entropy_buf = _blob(_DPAPI_ENTROPY)
        output = _DataBlob()
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(input_blob),
            None,
            ctypes.byref(entropy_blob),
            None,
            None,
            0x1,
            ctypes.byref(output),
        )
        _keepalive = (input_buf, entropy_buf)
        if not ok:
            raise XingyunError("DPAPI 解密失败")
        try:
            return ctypes.string_at(output.pbData, output.cbData)
        finally:
            kernel32.LocalFree(output.pbData)
    except XingyunError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise XingyunError(f"DPAPI 不可用：{str(exc)[:160]}") from exc


def _valid_credential(value: str, *, name: str) -> str:
    text = str(value or "").strip()
    if len(text) != 32 or any(ch not in _HEX32 for ch in text.lower()):
        raise XingyunError(f"{name} 应为 32 位十六进制字符串")
    return text


def mask(value: str) -> str:
    text = str(value or "")
    return f"{text[:4]}****" if len(text) >= 4 else ""


def store_credentials(app_id: str, app_secret: str) -> dict:
    """把星云应用凭证加密保存到当前 Windows 用户的 DPAPI 文件，不返回明文。"""
    try:
        safe_id = _valid_credential(app_id, name="App ID")
        safe_secret = _valid_credential(app_secret, name="App Secret")
    except XingyunError as exc:
        return {"ok": False, "error": str(exc)}
    payload = json.dumps({"appId": safe_id, "appSecret": safe_secret},
                         ensure_ascii=False).encode("utf-8")
    try:
        target = _secret_file()
        atomic_write_bytes(target, _protect_dpapi(payload), mode=0o600)
        return {
            "ok": True,
            "configured": True,
            "credential": "dpapi",
            "app_id_masked": mask(safe_id),
            "path": str(target),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:200]}


def load_credentials() -> tuple[str, str, str]:
    """返回 (appId, appSecret, source)；不打印任何密钥材料。"""
    app_id, app_secret, source = _env_credentials()
    if app_id:
        return app_id, app_secret, source
    target = _secret_file()
    if not target.is_file():
        return "", "", "missing"
    try:
        raw = json.loads(_unprotect_dpapi(target.read_bytes()).decode("utf-8"))
    except Exception:  # noqa: BLE001
        return "", "", "unreadable"
    app_id = str(raw.get("appId") or "").strip()
    app_secret = str(raw.get("appSecret") or "").strip()
    if not app_id or not app_secret:
        return "", "", "missing"
    return app_id, app_secret, "dpapi"


def sdk_state() -> dict:
    try:
        size = SDK_FILE.stat().st_size
    except OSError:
        size = 0
    return {
        "local_bundle": SDK_FILE.name if size else "",
        "local_bytes": size,
        "available": size > 0,
        "cdn": SDK_CDN,
    }


def status() -> dict:
    """返回凭证与 SDK 状态，不返回任何密钥材料。"""
    app_id, _secret, source = load_credentials()
    return {
        "ok": True,
        "configured": bool(app_id),
        "credential_source": source,
        "credential_protected": source == "dpapi",
        "app_id_masked": mask(app_id),
        "gateway_server": GATEWAY_SERVER,
        "sdk": sdk_state(),
    }


def issue_session() -> dict:
    """仅供本机回环前端在进入星云形象时获取一次连接参数。"""
    app_id, app_secret, source = load_credentials()
    if not app_id or not app_secret:
        return {
            "ok": False,
            "configured": False,
            "error": "尚未配置星云应用凭证",
            "app_id_masked": "",
        }
    return {
        "ok": True,
        "configured": True,
        "appId": app_id,
        "appSecret": app_secret,
        "gatewayServer": GATEWAY_SERVER,
        "sdk": sdk_state(),
        "credential_source": source,
    }


def _cmd_status(_args: argparse.Namespace) -> int:
    print(json.dumps(status(), ensure_ascii=False, indent=2))
    return 0


def _cmd_set(args: argparse.Namespace) -> int:
    app_secret = args.app_secret or ""
    if not app_secret:
        app_secret = sys.stdin.readline().strip()
    result = store_credentials(args.app_id, app_secret)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="魔珐星云数字人凭证桥")
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="查看凭证与 SDK 状态（掩码）")
    p_status.set_defaults(func=_cmd_status)

    p_set = sub.add_parser("set", help="保存 App ID / App Secret（DPAPI 加密）")
    p_set.add_argument("--app-id", required=True)
    p_set.add_argument("--app-secret", default="",
                       help="省略时从标准输入读取，避免密钥出现在进程参数中")
    p_set.set_defaults(func=_cmd_set)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
