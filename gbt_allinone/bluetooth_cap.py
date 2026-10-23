# gbt-capability: bluetooth
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""bluetooth 能力 — 通过电脑蓝牙连接并操控外部家居设备（空调/灯/音箱等 BLE 设备）。

三级能力，如实降级：
1. scan   — 扫描附近 BLE 设备（bleak，真实执行，无需配对）
2. connect/read/write — 连接设备并读写 GATT 特征（控制设备核心）
3. classic — 经典蓝牙（BR/EDR，音箱/耳机类）需 Windows 蓝牙栈，暂以状态报告为主

安全边界：
- 只连用户明确指定的设备（MAC 地址），不做无差别扫描入侵
- 写入 GATT 特征需用户显式给出 characteristic UUID + 值
- 不猜设备协议、不越权；设备协议（空调温度码等）由用户提供或后续按型号适配
"""
from __future__ import annotations

import asyncio
import os
# 依赖兜底：唯一真相源走 dependency_paths.activate_local_dependencies()。
# 不再手打 sys.path：手打会漏掉 ABI overlay（.pylibs/<abi>），
# 且会把 legacy 树顶到 sys.path[0]，对撞「系统包优先于 legacy 兜底」的设计。
try:
    from .dependency_paths import activate_local_dependencies
except ImportError:            # 以脚本方式直跑本文件时
    from gbt_allinone.dependency_paths import activate_local_dependencies
activate_local_dependencies()


def _bleak():
    try:
        import bleak
        return bleak, None
    except ImportError as e:
        return None, str(e)


def scan(timeout=5.0, name_filter=None):
    """扫描附近 BLE 设备（真实执行，返回设备名+MAC+RSSI）。"""
    bleak, err = _bleak()
    if bleak is None:
        return {"ok": False, "status": "needs_dependency",
                "missing": "bleak", "install": "python -m pip install bleak",
                "detail": err}
    try:
        from bleak import BleakScanner

        async def _do():
            devices = await BleakScanner.discover(timeout=float(timeout), return_adv=True)
            out = []
            for addr, (dev, adv) in devices.items():
                name = dev.name or adv.local_name or "(未命名)"
                if name_filter and name_filter.lower() not in str(name).lower():
                    continue
                out.append({"address": addr, "name": name, "rssi": adv.rssi})
            return out

        return {"ok": True, "backend": "bleak", "devices": asyncio.run(_do())}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"扫描失败: {str(e)[:200]}",
                "hint": "确认蓝牙已开启（bthserv 运行 + 适配器在位）"}


def _services_and_chars(address):
    """列出设备的 GATT 服务与特征（连接后）."""
    from bleak import BleakClient

    async def _do():
        async with BleakClient(address, timeout=20) as client:
            if not client.is_connected:
                return None
            services = []
            for s in client.services:
                chars = []
                for c in s.characteristics:
                    props = ",".join(c.properties)
                    chars.append({"uuid": c.uuid, "properties": props,
                                  "handle": c.handle})
                services.append({"uuid": s.uuid, "description": s.description,
                                 "characteristics": chars})
            return services

    return asyncio.run(_do())


def connect(address, timeout=20):
    """连接设备并列出 GATT 服务（读控制点前先探查设备能力）。"""
    from bleak import BleakClient

    async def _do():
        async with BleakClient(address, timeout=float(timeout)) as client:
            connected = client.is_connected
            services = []
            for s in client.services:
                chars = []
                for c in s.characteristics:
                    chars.append({"uuid": c.uuid,
                                  "properties": ",".join(c.properties)})
                services.append({"uuid": s.uuid, "chars": chars})
            return {"connected": connected, "services": services}

    try:
        return {"ok": True, "backend": "bleak", "result": asyncio.run(_do())}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"连接失败: {str(e)[:200]}",
                "hint": "确认设备在范围内、未连接、且非经典蓝牙(音箱类)"}


def read(address, char_uuid, timeout=20):
    """读取 GATT 特征值（hex）。"""
    from bleak import BleakClient

    async def _do():
        async with BleakClient(address, timeout=float(timeout)) as client:
            data = await client.read_gatt_char(char_uuid)
            return {"value_hex": data.hex(), "value_bytes": len(data)}

    try:
        return {"ok": True, "backend": "bleak", "result": asyncio.run(_do())}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"读取失败: {str(e)[:200]}"}


def write(address, char_uuid, value_hex, timeout=20):
    """写入 GATT 特征值（控制设备的核心——值由设备协议定义）。

    value_hex: 十六进制字符串，如 '01' 或 '01ff00'（不含 0x 前缀）。
    写入含写回(WRITE)特征时，某些设备需要 WRITE-WITHOUT-RESPONSE，自动尝试。
    """
    from bleak import BleakClient

    if value_hex.lower().startswith("0x"):
        value_hex = value_hex[2:]
    try:
        payload = bytes.fromhex(value_hex)
    except ValueError:
        return {"ok": False, "error": "value_hex 非法：需十六进制字符串（如 '01' 或 '01ff00'）"}

    async def _do():
        async with BleakClient(address, timeout=float(timeout)) as client:
            # 先尝试带响应写，失败退化为无响应写
            try:
                await client.write_gatt_char(char_uuid, payload, response=True)
                method = "write-with-response"
            except Exception:
                await client.write_gatt_char(char_uuid, payload, response=False)
                method = "write-without-response"
            return {"method": method, "bytes": len(payload)}

    try:
        return {"ok": True, "backend": "bleak", "result": asyncio.run(_do())}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"写入失败: {str(e)[:200]}",
                "hint": "确认特征 UUID 支持 WRITE/WRITE_NO_RESPONSE 属性（先 connect 探查）"}


def _classic_status():
    """经典蓝牙（BR/EDR，音箱/耳机类）状态——Windows 蓝牙栈只读报告。"""
    try:
        import subprocess
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | "
             "Select-Object Status,FriendlyName | ConvertTo-Json -Compress"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        import json
        devs = json.loads(r.stdout) if r.stdout.strip() else []
        if isinstance(devs, dict):
            devs = [devs]
        return {"ok": True, "backend": "win-bluetooth-stack",
                "paired_devices": [{"name": d.get("FriendlyName"), "status": d.get("Status")}
                                   for d in devs]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"经典蓝牙枚举失败: {str(e)[:160]}"}


def run(op="scan", **params):
    """bluetooth 统一入口：scan/connect/read/write/classic/status。"""
    if op in ("scan", None):
        return scan(params.get("timeout", 5.0), params.get("name_filter"))
    if op == "connect":
        return connect(params.get("address"), params.get("timeout", 20))
    if op == "read":
        return read(params.get("address"), params.get("char_uuid"), params.get("timeout", 20))
    if op == "write":
        return write(params.get("address"), params.get("char_uuid"),
                     params.get("value_hex"), params.get("timeout", 20))
    if op == "classic":
        return _classic_status()
    if op == "status":
        bleak, err = _bleak()
        return {"ok": True,
                "ble_backend": "bleak" if bleak else f"needs_dependency（{err}）",
                "classic_backend": "win-bluetooth-stack",
                "ops": ["scan", "connect", "read", "write", "classic", "status"],
                "note": "scan/connect/read/write 控制 BLE 设备；classic 报告已配对经典设备"}
    raise ValueError(f"未知 op: {op}（可用: scan/connect/read/write/classic/status）")
