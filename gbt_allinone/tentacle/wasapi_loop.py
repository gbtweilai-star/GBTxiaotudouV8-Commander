# gbt-capability: ctypes, dynamic-import
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""WASAPI 回环采集（Windows Core Audio）—— 触手的**耳朵**。

## 它解决什么

触手此前**没有任何音频采集**。本机实测 `waveInGetNumDevs = 0`（没有麦克风），
所以"听麦克风"这条路在本机根本不通；**但扬声器在**（`扬声器 (Realtek(R) Audio)`）。
⇒ 要让她听见东西，**只有 WASAPI 回环这一条路**：直接抓"电脑正在放什么"。

## 依据（照官方文档，不自己发明）

Microsoft Learn《Loopback Recording》原文给了两处关键改动：
  · `IMMDeviceEnumerator::GetDefaultAudioEndpoint` 的第一个参数
    从 `eCapture` 改成 **`eRender`**；
  · `IAudioClient::Initialize` 的第二个参数 `StreamFlags`
    从 `0` 改成 **`AUDCLNT_STREAMFLAGS_LOOPBACK`**。
另外两条原文约束照录：
  · **回环只能是共享模式**（`AUDCLNT_SHAREMODE_SHARED`）；独占模式不能回环。
  · Windows 10 1703 之前，事件驱动的回环客户端收不到事件（要拿渲染流兜）；
    **1703 及以后**事件驱动回环被支持，不再需要那个绕法。
    本实现走**轮询**（`GetNextPacketSize`），对该差异免疫。

## 依赖说明（零新增）

用 **`comtypes`**（本机已装）手写 COM 接口声明。WASAPI 的接口定义在
`Mmdeviceapi.h` / `Audioclient.h` 里，**没有 typelib**，所以必须自己按 vtable 顺序声明 ——
顺序错一个就静默调错函数，所以下面每个接口都按官方头文件的声明顺序写，并注明来源。

## 诚实边界

- **只在 Windows 上可用**；非 Windows 如实报不可用。
- 没有扬声器/端点不可用时**如实失败**，不产假音频。
- 抓到的格式**由系统给**（`GetMixFormat`），我们不自作主张改采样率 ——
  回环的格式必须与渲染端点一致，改了会静音或直接失败。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""

from __future__ import annotations

import ctypes as _ct
import wave as _wave
from ctypes import POINTER as _P
from ctypes import byref as _byref
from ctypes import c_void_p as _cvoid
from ctypes import cast as _cast
from ctypes import sizeof as _sizeof

_IS_WIN = __import__("sys").platform.startswith("win")

# ── 常量（官方头文件） ─────────────────────────────────────────────────────
_CLSID_MMDeviceEnumerator = "{BCDE0395-E52F-467C-8E3D-C4579291692E}"
_IID_IMMDeviceEnumerator = "{A95664D2-9614-4F35-A746-DE8DB63617E6}"
_IID_IAudioClient = "{1CB9AD4C-DBFA-4c32-B178-C2F568A703B2}"
_IID_IAudioCaptureClient = "{C8ADBD64-E71E-48a0-A4DE-185C395CD317}"

E_RENDER, E_CAPTURE = 0, 1
E_CONSOLE, E_MULTIMEDIA, E_COMMUNICATIONS = 0, 1, 2

AUDCLNT_SHAREMODE_SHARED = 0
AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
AUDCLNT_STREAMFLAGS_EVENTCALLBACK = 0x00040000
AUDCLNT_S_BUFFER_EMPTY = 0x08890001
DEVICE_STATE_ACTIVE = 0x00000001        # Mmdeviceapi.h
DEVICE_STATE_DISABLED = 0x00000002
DEVICE_STATE_NOTPRESENT = 0x00000004
DEVICE_STATE_UNPLUGGED = 0x00000008
DEVICE_STATEMASK_ALL = 0x0000000F

REFTIMES_PER_SEC = 10_000_000
_AUDCLNT_BUFFER_DURATION = REFTIMES_PER_SEC // 2      # 500ms，官方示例用的量级


class _GUID(_ct.Structure):
    _fields_ = [("Data1", _ct.c_ulong), ("Data2", _ct.c_ushort),
                ("Data3", _ct.c_ushort), ("Data4", _ct.c_ubyte * 8)]


class WAVEFORMATEX(_ct.Structure):
    """只取**公共前缀**：`WAVEFORMATEXTENSIBLE` 的前 18 字节与它逐字段一致，
    所以读采样率/声道/位深都对；而传给 `Initialize` 时用的是**原指针**。"""
    _fields_ = [("wFormatTag", _ct.c_ushort), ("nChannels", _ct.c_ushort),
                ("nSamplesPerSec", _ct.c_uint), ("nAvgBytesPerSec", _ct.c_uint),
                ("nBlockAlign", _ct.c_ushort), ("wBitsPerSample", _ct.c_ushort),
                ("cbSize", _ct.c_ushort)]


def _guid(s: str):
    """**必须用 comtypes 自己的 GUID**。

    实测教训（2026-09-22）：我一开始自己定义了 `_GUID(ctypes.Structure)`，
    comtypes 报两连错 —— 先 `expected LP_GUID instance instead of _GUID`，
    改成 `byref` 之后变成 `expected LP_GUID instance instead of pointer to _GUID`。
    它只认 `comtypes.GUID`，并对 `POINTER(GUID)` 参数**自动转换**，直接传实例即可。
    """
    from comtypes import GUID as _CG
    return _CG(s)


def _comtypes():
    try:
        import comtypes  # noqa: F401
        from comtypes import COMMETHOD, GUID, HRESULT, IUnknown  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _build_interfaces():
    """按官方头文件的**声明顺序**声明 vtable。顺序错=静默调错函数，所以这里逐条对着写。"""
    from comtypes import COMMETHOD, HRESULT, IUnknown
    from comtypes import GUID as _CGUID

    class IMMDevice(IUnknown):
        _iid_ = _CGUID("{D666063F-1587-4E43-81F1-B948E807363F}")
        _methods_ = [
            # Mmdeviceapi.h 声明顺序
            COMMETHOD([], HRESULT, "Activate",
                      (["in"], _P(_CGUID), "iid"),
                      (["in"], _ct.c_ulong, "dwClsCtx"),
                      (["in"], _P(_ct.c_ulong), "pActivationParams"),
                      (["out"], _P(_cvoid), "ppInterface")),
            COMMETHOD([], HRESULT, "OpenPropertyStore"),
            COMMETHOD([], HRESULT, "GetId", (["out"], _P(_ct.c_wchar_p), "ppstrId")),
            COMMETHOD([], HRESULT, "GetState", (["out"], _P(_ct.c_ulong), "pdwState")),
        ]

    class IMMDeviceCollection(IUnknown):
        """Mmdeviceapi.h 声明顺序：GetCount → Item。"""
        _iid_ = _CGUID("{0BD7A1BE-7A1A-44DB-8397-CC5392387B5E}")
        _methods_ = [
            COMMETHOD([], HRESULT, "GetCount", (["out"], _P(_ct.c_uint), "pcDevices")),
            COMMETHOD([], HRESULT, "Item",
                      (["in"], _ct.c_uint, "nDevice"),
                      (["out"], _P(_P(IMMDevice)), "ppDevice")),
        ]

    class IMMDeviceEnumerator(IUnknown):
        _iid_ = _CGUID(_IID_IMMDeviceEnumerator)
        _methods_ = [
            COMMETHOD([], HRESULT, "EnumAudioEndpoints",
                      (["in"], _ct.c_int, "dataFlow"),
                      (["in"], _ct.c_ulong, "dwStateMask"),
                      (["out"], _P(_P(IMMDeviceCollection)), "ppDevices")),
            COMMETHOD([], HRESULT, "GetDefaultAudioEndpoint",
                      (["in"], _ct.c_int, "dataFlow"),
                      (["in"], _ct.c_int, "role"),
                      (["out"], _P(_P(IMMDevice)), "ppEndpoint")),
            COMMETHOD([], HRESULT, "GetDevice"),
            COMMETHOD([], HRESULT, "RegisterEndpointNotificationCallback"),
            COMMETHOD([], HRESULT, "UnregisterEndpointNotificationCallback"),
        ]

    class IAudioCaptureClient(IUnknown):
        _iid_ = _CGUID(_IID_IAudioCaptureClient)
        _methods_ = [
            COMMETHOD([], HRESULT, "GetBuffer",
                      (["out"], _P(_P(_ct.c_ubyte)), "ppData"),
                      (["out"], _P(_ct.c_uint), "pNumFramesToRead"),
                      (["out"], _P(_ct.c_ulong), "pdwFlags"),
                      (["out"], _P(_ct.c_ulonglong), "pu64DevicePosition"),
                      (["out"], _P(_ct.c_ulonglong), "pu64QPCPosition")),
            COMMETHOD([], HRESULT, "ReleaseBuffer",
                      (["in"], _ct.c_uint, "NumFramesRead")),
            COMMETHOD([], HRESULT, "GetNextPacketSize",
                      (["out"], _P(_ct.c_uint), "pNumFramesInNextPacket")),
        ]

    class IAudioClient(IUnknown):
        _iid_ = _CGUID(_IID_IAudioClient)
        _methods_ = [
            COMMETHOD([], HRESULT, "Initialize",
                      (["in"], _ct.c_int, "ShareMode"),
                      (["in"], _ct.c_ulong, "StreamFlags"),
                      (["in"], _ct.c_longlong, "hnsBufferDuration"),
                      (["in"], _ct.c_longlong, "hnsPeriodicity"),
                      (["in"], _P(WAVEFORMATEX), "pFormat"),
                      (["in"], _P(_CGUID), "AudioSessionGuid")),
            COMMETHOD([], HRESULT, "GetBufferSize", (["out"], _P(_ct.c_uint), "p")),
            COMMETHOD([], HRESULT, "GetStreamLatency", (["out"], _P(_ct.c_longlong), "p")),
            COMMETHOD([], HRESULT, "GetCurrentPadding", (["out"], _P(_ct.c_uint), "p")),
            COMMETHOD([], HRESULT, "IsFormatSupported"),
            COMMETHOD([], HRESULT, "GetMixFormat",
                      (["out"], _P(_P(WAVEFORMATEX)), "ppDeviceFormat")),
            COMMETHOD([], HRESULT, "GetDevicePeriod"),
            COMMETHOD([], HRESULT, "Start"),
            COMMETHOD([], HRESULT, "Stop"),
            COMMETHOD([], HRESULT, "Reset"),
            COMMETHOD([], HRESULT, "SetEventHandle"),
            COMMETHOD([], HRESULT, "GetService",
                      (["in"], _P(_CGUID), "riid"),
                      (["out"], _P(_cvoid), "ppv")),
        ]

    return IMMDeviceEnumerator, IAudioClient, IAudioCaptureClient, IMMDeviceCollection


def capture(seconds: float = 3.0, *, flow: str = "loopback", chunk_ms: int = 100) -> dict:
    """WASAPI 采集。`flow="loopback"` = 听电脑在放什么；`flow="mic"` = 听录音端点（麦克风）。

    🔴 **实测教训（2026-09-22，很重要）**：我曾据 `winmm` 的 `waveInGetNumDevs = 0`
    断言"本机真的没有麦克风"—— **那是错的**。
    `Get-PnpDevice -Class AudioEndpoint` 显示本机**有**一个状态 OK 的录音端点：
    `麦克风 (iPhone Hands-Free HF Audio)`（蓝牙免提）。
    **winmm 的 waveIn 只枚举传统 MME 设备**，现代蓝牙/WASAPI-only 端点不在其内。
    ⇒ **一个数不等于事实，必须交叉验证**（这条已写进 AUDIO_GAPS 与交付报告）。
    """
    if not _IS_WIN:
        return {"ok": False, "error": "WASAPI 是 Windows 的", "verified": False}
    if not _comtypes():
        return {"ok": False, "needs_dependency": "comtypes",
                "error": "comtypes 不可用", "verified": False}
    try:
        import comtypes
        import comtypes.client as _cc
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "comtypes 导入失败：%s" % str(e)[:120], "verified": False}
    try:
        comtypes.CoInitialize()
    except Exception:  # noqa: BLE001
        pass
    is_loop = str(flow).lower() in ("loopback", "loop", "system", "render")
    data_flow = E_RENDER if is_loop else E_CAPTURE
    stream_flags = AUDCLNT_STREAMFLAGS_LOOPBACK if is_loop else 0
    try:
        IMMDeviceEnumerator, IAudioClient, IAudioCaptureClient, IMMDeviceCollection = _build_interfaces()
        enumerator = _cc.CreateObject(_CLSID_MMDeviceEnumerator, interface=IMMDeviceEnumerator)
        used_fallback = None
        device = None
        try:
            device = enumerator.GetDefaultAudioEndpoint(data_flow, E_CONSOLE)
        except Exception as e:  # noqa: BLE001
            # 🔴 实测（2026-09-22）：本机有录音端点（PnP 显示 OK），但**没被设成默认录音设备**，
            #    于是 GetDefaultAudioEndpoint(eCapture) 抛 `ERROR_NOT_FOUND 找不到元素`。
            #    ⇒ **不能只靠"默认端点"**，必须退回枚举活动端点。这一条是"麦克风好像没有"
            #    的真正原因 —— 设备在，只是没设默认。
            used_fallback = {"why": "GetDefaultAudioEndpoint 失败：%s" % str(e)[:80]}
        if device is None:
            coll = enumerator.EnumAudioEndpoints(data_flow, DEVICE_STATE_ACTIVE)
            cnt = int(coll.GetCount())
            if cnt <= 0:
                return {"ok": False, "verified": False, "flow": flow, "active_endpoints": 0,
                        "error": "该方向没有**活动**端点（%s 侧）—— 设备可能被禁用或未插入"
                                 % ("渲染" if is_loop else "录音")}
            device = coll.Item(0)
            used_fallback = dict(used_fallback or {}, active_endpoints=cnt, picked_index=0)
        if device is None:
            return {"ok": False, "verified": False, "flow": flow,
                    "error": "没有可用端点（%s 侧）" % ("渲染" if is_loop else "录音")}
        raw = device.Activate(_guid(_IID_IAudioClient), 0x17, None)
        client = _cast(raw, _P(IAudioClient))
        pwfx = client.GetMixFormat()
        fmt = pwfx.contents
        if fmt.nSamplesPerSec <= 0 or fmt.nChannels <= 0:
            return {"ok": False, "error": "GetMixFormat 给出的格式不合法", "verified": False}
        hr = client.Initialize(AUDCLNT_SHAREMODE_SHARED, stream_flags,
                               _AUDCLNT_BUFFER_DURATION, 0, pwfx, None)
        if hr not in (0, None) and int(hr or 0) < 0:
            return {"ok": False, "verified": False, "flow": flow,
                    "error": "IAudioClient::Initialize 失败 hr=%s（flags=0x%X）" % (hr, stream_flags)}
        cap = _cast(client.GetService(_guid(_IID_IAudioCaptureClient)), _P(IAudioCaptureClient))
        block = fmt.nBlockAlign or (fmt.nChannels * max(1, fmt.wBitsPerSample // 8))
        want = int(fmt.nSamplesPerSec * float(seconds))
        buf = bytearray()
        client.Start()
        try:
            import time as _t
            deadline = _t.time() + float(seconds) + 1.0
            while len(buf) < want * block and _t.time() < deadline:
                n = cap.GetNextPacketSize()
                if n == 0:
                    _t.sleep(max(0.005, chunk_ms / 1000.0 / 4.0))
                    continue
                data, frames, _flags, _pos, _qpc = cap.GetBuffer()
                if frames:
                    buf += _ct.string_at(data, frames * block)
                cap.ReleaseBuffer(frames)
        finally:
            client.Stop()
        got = len(buf) // block if block else 0
        # ⚠️ 诚实性（实测教训）：**链路开成功 ≠ 真抓到东西**。
        #    首轮我让 0 帧也回 `verified=True` —— 那是过度声称。
        #    现在分开：`chain_ok` = 链路打通；`verified` = **还真的抓到了帧**。
        chain_ok = True
        out = {"ok": True, "pcm": bytes(buf), "channels": fmt.nChannels,
               "rate": fmt.nSamplesPerSec, "bits": fmt.wBitsPerSample,
               "block_align": block, "frames": got,
               "seconds": round(got / fmt.nSamplesPerSec, 3) if fmt.nSamplesPerSec else None,
               "silent": (not any(buf[:4096])) if buf else None,
               "format_tag": fmt.wFormatTag, "chain_ok": chain_ok,
               "verified": bool(chain_ok and got > 0),
               "flow": "loopback" if is_loop else "mic",
               "used_fallback": used_fallback,
               "source": "IMMDeviceEnumerator(%s) + IAudioClient(flags=0x%X) + IAudioCaptureClient"
                         % ("eRender" if is_loop else "eCapture", stream_flags)}
        if got == 0:
            out["note"] = ("链路已打通（chain_ok=true），但**一帧都没抓到** —— "
                           "此刻该端点没有数据在流（回环=系统没在出声；麦克风=没在采集）。"
                           "**不把它算作 verified。**")
        return out
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "verified": False, "flow": flow,
                "error": "%s: %s" % (type(e).__name__, str(e)[:180])}
    finally:
        try:
            import comtypes
            comtypes.CoUninitialize()
        except Exception:  # noqa: BLE001
            pass


def loopback_capture(seconds: float = 3.0, *, chunk_ms: int = 100,
                     render: int = E_RENDER) -> dict:
    """抓"系统正在播放的声音"（= `capture(flow="loopback")` 的兼容入口）。"""
    return capture(seconds, flow="loopback", chunk_ms=chunk_ms)


def mic_capture(seconds: float = 3.0, *, chunk_ms: int = 100) -> dict:
    """抓**录音端点**（麦克风）。本机端点：`麦克风 (iPhone Hands-Free HF Audio)`。"""
    return capture(seconds, flow="mic", chunk_ms=chunk_ms)


def write_wav(path: str, pcm: bytes, *, channels: int, rate: int, bits: int) -> dict:
    """把抓到的 PCM 落成 WAV。**只写真正抓到的字节**，不补齐、不造静音。"""
    try:
        with _wave.open(str(path), "wb") as w:
            w.setnchannels(int(channels))
            w.setsampwidth(max(1, int(bits) // 8))
            w.setframerate(int(rate))
            w.writeframes(pcm)
        return {"ok": True, "path": str(path), "bytes": len(pcm)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:140])}
