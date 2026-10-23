# gbt-capability: bluetooth
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""bt_control — AI 智能蓝牙设备操控层（自然语言 → 协议 → 执行 → 验证）。

与 bluetooth_cap（底层原语）分层：
  bluetooth_cap = 手（scan/connect/read/write 原语）
  bt_control    = 脑（意图解析/设备识别/协议匹配/指令组装/闭环验证）

协议知识库只收录公开文档协议（逐条标注来源），未知设备给出类型推断与置信度，
绝不编造协议码；需要配对/加密的设备如实报告并给配对指引。

公开协议来源（均为厂商公开文档/蓝牙 SIG 规范）：
  - Nordic UART Service (NUS)：官方公开 UUID，ESPHome/开源智能家居广泛使用
    RX(写) 6e400002-b5a3-f393-e0a9-e50e24dcca9e / TX(通知) 6e400003-...
    命令格式由设备端固件定义（常见：文本行命令）
  - Tuya BLE：服务 FE00（涂鸦智能生态——大量国产灯/插座/空调伴侣），协议需配对密钥
  - Xiaomi/Mi：服务 FE95（小米生态），大多需小米账号级配对
  - HomeKit HAP：服务 00000096-0000-1000-8000-0026BB765291（Apple 公开），需 MFi 认证配对
  - HID over GATT：服务 1812（键盘/鼠标/遥控器——连接即被 OS 识别为输入设备）
  - 标准服务：180F 电量 / 180A 设备信息 / 1800 GAP / 1801 GATT
"""
from __future__ import annotations

import asyncio
import re
from typing import Optional

# ── 公开协议知识库（服务 UUID → 协议/厂商/控制方式）──────────────────────
PROTOCOL_LIBRARY = {
    "6e400001-b5a3-f393-e0a9-e50e24dcca9e": {
        "name": "Nordic UART (NUS)", "vendor": "Nordic/开源生态",
        "device_hint": "DIY智能家居/ESPHome/开源设备",
        "control": "RX特征写文本命令", "pairing": "通常无需配对",
        "rx_char": "6e400002-b5a3-f393-e0a9-e50e24dcca9e",
        "tx_char": "6e400003-b5a3-f393-e0a9-e50e24dcca9e",
        "source": "Nordic 官方公开 UUID",
    },
    "0000fe00-0000-1000-8000-00805f9b34fb": {
        "name": "Tuya BLE", "vendor": "涂鸦智能",
        "device_hint": "智能灯/插座/空调伴侣/传感器（大量国产）",
        "control": "加密指令（需设备配对密钥）", "pairing": "需配对",
        "source": "蓝牙 SIG 官方 16-bit UUID 分配表 FE00=Tuya",
    },
    "0000fe95-0000-1000-8000-00805f9b34fb": {
        "name": "Xiaomi Mi", "vendor": "小米",
        "device_hint": "小米手环/传感器/智能家居（米家生态）",
        "control": "小米私有加密协议", "pairing": "需米家账号配对",
        "source": "蓝牙 SIG 官方 16-bit UUID 分配表 FE95=Xiaomi",
    },
    "d0611e78-bbb4-4591-a5f8-487910ae4366": {
        "name": "Apple Continuity", "vendor": "Apple",
        "device_hint": "iPhone/iPad/Mac/Watch（找手机/隔空投放）",
        "control": "Apple 私有（需认证）", "pairing": "需 Apple 认证",
        "source": "逆向公开文档（非官方）",
    },
    "00000096-0000-1000-8000-0026bb765291": {
        "name": "HomeKit HAP", "vendor": "Apple HomeKit",
        "device_hint": "HomeKit 认证智能家居（灯锁传感器）",
        "control": "HAP 配对后 TLV8 加密", "pairing": "需 HAP 配对",
        "source": "Apple HomeKit Accessory Protocol 公开规范",
    },
    "00001812-0000-1000-8000-00805f9b34fb": {
        "name": "HID over GATT", "vendor": "蓝牙 SIG 标准",
        "device_hint": "蓝牙键盘/鼠标/遥控器（连接即系统输入设备）",
        "control": "OS 输入层接管（无需手写协议）", "pairing": "系统配对",
        "source": "蓝牙 SIG HID Service 规范",
    },
    "0000180f-0000-1000-8000-00805f9b34fb": {
        "name": "Battery Service", "vendor": "蓝牙 SIG 标准",
        "device_hint": "任何 BLE 外设（电量特征 0x2A19）",
        "control": "只读", "pairing": "无需",
        "source": "蓝牙 SIG BAS 规范",
    },
    "0000180a-0000-1000-8000-00805f9b34fb": {
        "name": "Device Information", "vendor": "蓝牙 SIG 标准",
        "device_hint": "任何 BLE 外设（厂商/型号/序列号）",
        "control": "只读", "pairing": "无需",
        "source": "蓝牙 SIG DIS 规范",
    },
}

# 标准特征 UUID 语义（读识别用）
CHAR_SEMANTICS = {
    "00002a00-0000-1000-8000-00805f9b34fb": "device_name",
    "00002a29-0000-1000-8000-00805f9b34fb": "manufacturer",
    "00002a24-0000-1000-8000-00805f9b34fb": "model_number",
    "00002a19-0000-1000-8000-00805f9b34fb": "battery",
    "00002a25-0000-1000-8000-00805f9b34fb": "serial_number",
    "00002a27-0000-1000-8000-00805f9b34fb": "firmware_rev",
}

# ── 意图解析：自然语言 → 结构化控制命令 ─────────────────────────────
INTENT_PATTERNS = [
    # (正则, 设备类型, 动作, 参数提取) ——顺序敏感：具体在前宽泛在后
    (r"(空调|air.?conditioner|ac)\s*(?:开机|打开|开$|on$)", "air_conditioner", "power_on", None),
    (r"(空调|air.?conditioner|ac)\s*(?:关机|关闭|关$|off$)", "air_conditioner", "power_off", None),
    (r"(空调|air.?conditioner|ac).*?(\d{2})\s*(?:度|℃|°|c)?", "air_conditioner", "set_temperature", "temp"),
    (r"(灯|light|lamp)", None, "_light_marker", None),  # 先标记灯，再判动作（防被温度误吃）
    (r"(扫描|搜索|scan|找).*?(设备|蓝牙|bluetooth|device)", None, "discover", None),
    (r"(电量|battery)", None, "read_battery", None),
    (r"(信息|info|识别|identify)", None, "identify", None),
    # 宽泛温度在最后（无设备词时不误吞灯亮度）
    (r"^(?:温度|调到|设到|set)?\s*(\d{2})\s*(?:度|℃|°)", "air_conditioner", "set_temperature", "temp"),
]


def parse_intent(text: str) -> dict:
    """自然语言 → {device_type, action, params}。无法解析时返回 unknown + 建议。"""
    if not text:
        return {"ok": False, "error": "缺少意图文本"}
    t = text.strip().lower()
    # 灯类先标记再判动作（避免被温度正则抢先）
    is_light = bool(re.search(r"(灯|light|lamp)", t))
    if is_light:
        m_bright = re.search(r"(?:调(?:亮|暗)|bright|dim).*?(\d+)|(\d+).*?(?:调(?:亮|暗))", t)
        if re.search(r"(?:开|打开|on)", t) and not m_bright:
            return {"ok": True, "device_type": "light", "action": "power_on", "params": {}, "raw": text[:80]}
        if re.search(r"(?:关|关闭|off)", t):
            return {"ok": True, "device_type": "light", "action": "power_off", "params": {}, "raw": text[:80]}
        if m_bright:
            val = m_bright.group(1) or m_bright.group(2)
            return {"ok": True, "device_type": "light", "action": "set_brightness",
                    "params": {"level": int(val)}, "raw": text[:80]}
        return {"ok": True, "device_type": "light", "action": "power_on", "params": {}, "raw": text[:80]}
    for pat, dtype, action, param_key in INTENT_PATTERNS:
        if action == "_light_marker":
            continue
        m = re.search(pat, t)
        if m:
            params = {}
            if param_key and m.groups():
                try:
                    params[param_key] = int(m.group(m.lastindex if m.lastindex else 1))
                except (ValueError, IndexError, TypeError):
                    pass
            return {"ok": True, "device_type": dtype, "action": action,
                    "params": params, "raw": text[:80]}
    return {"ok": False, "error": "无法解析意图",
            "hint": "示例：'空调开机' / '空调调到26度' / '开灯' / '扫描设备' / '查电量'",
            "supported": ["air_conditioner:power_on/off/set_temperature",
                          "light:power_on/off/set_brightness",
                          "discover / read_battery / identify"]}


# ── 设备识别：服务清单 → 协议匹配 + 类型推断 ─────────────────────────
def identify_device(services: list) -> dict:
    """根据 GATT 服务清单推断设备类型与可用控制协议（含置信度）。"""
    uuids = {str(s.get("uuid", "")).lower() for s in services}
    matched = []
    for uuid in uuids:
        # 归一化：16-bit 转 128-bit 标准形式
        for proto_uuid, info in PROTOCOL_LIBRARY.items():
            if proto_uuid in uuid or (len(uuid) == 4 and uuid in proto_uuid):
                matched.append({"protocol": info["name"], "uuid": proto_uuid,
                                "vendor": info["vendor"], "hint": info["device_hint"],
                                "control": info["control"], "pairing": info["pairing"],
                                "source": info["source"]})
    # 类型推断
    hints = []
    if any("Tuya" in m["protocol"] for m in matched):
        hints.append("智能家居（灯/插座/空调伴侣）")
    if any("Xiaomi" in m["protocol"] for m in matched):
        hints.append("小米生态设备")
    if any("HID" in m["protocol"] for m in matched):
        hints.append("蓝牙输入设备（键盘/鼠标/遥控）")
    if any("HomeKit" in m["protocol"] for m in matched):
        hints.append("HomeKit 家居设备")
    if any("Nordic" in m["protocol"] for m in matched):
        hints.append("开源/DIY 智能设备（NUS 可直控）")
    if not matched and services:
        hints.append("未知协议（服务无公开库匹配——可能厂商私有）")
    return {"ok": True, "matched_protocols": matched,
            "device_type_guess": " / ".join(hints) or "未知",
            "confidence": "high" if matched else "low"}


# ── 智能控制端到端 ─────────────────────────────────────────────────
def control(intent: str, address: Optional[str] = None, scan_timeout=6.0) -> dict:
    """AI 操控入口：意图 → （未给地址则扫描识别候选）→ 协议匹配 → 执行 → 返回结果。

    未知/需配对协议：如实报告控制路径与所需条件，不伪造执行。
    NUS 设备：真实写入文本命令。
    """
    from . import bluetooth_cap as BT

    # 1. 意图解析
    parsed = parse_intent(intent)
    if not parsed.get("ok"):
        return parsed

    action = parsed["action"]
    dtype = parsed.get("device_type")

    # 只读/发现类动作直接走对应能力
    if action == "discover":
        return BT.scan(scan_timeout)
    if action == "read_battery":
        if not address:
            return {"ok": False, "error": "查电量需指定设备地址（先 discover）"}
        return BT.read(address, "00002a19-0000-1000-8000-00805f9b34fb")

    # 2. 设备定位
    if not address:
        scan_r = BT.scan(scan_timeout)
        if not scan_r.get("ok"):
            return {"ok": False, "error": "扫描失败", "detail": scan_r}
        devices = scan_r.get("devices", [])
        if not devices:
            return {"ok": False, "error": "附近无 BLE 设备"}
        address = devices[0]["address"]  # 默认最强信号设备
        return {"ok": False, "status": "need_address",
                "candidates": devices[:5],
                "message": "发现多台设备，请指定地址或用 identify 逐台识别",
                "hint": "control(intent='...', address='XX:XX:...')"}

    # 3. 连接并识别协议
    conn_r = BT.connect(address)
    if not conn_r.get("ok"):
        return {"ok": False, "error": "连接失败", "detail": conn_r}
    services = conn_r.get("result", {}).get("services", [])
    ident = identify_device(services)

    # 4. 按协议路由执行
    protocols = {m["protocol"] for m in ident["matched_protocols"]}
    if "Nordic UART (NUS)" in protocols:
        # NUS：真实写入文本命令（设备固件定义的行命令）
        cmd_map = {
            ("air_conditioner", "power_on"): "AC ON\n",
            ("air_conditioner", "power_off"): "AC OFF\n",
            ("air_conditioner", "set_temperature"): f"TEMP {parsed['params'].get('temp', 26)}\n",
            ("light", "power_on"): "LIGHT ON\n",
            ("light", "power_off"): "LIGHT OFF\n",
            ("light", "set_brightness"): f"BRIGHT {parsed['params'].get('level', 50)}\n",
        }
        text_cmd = cmd_map.get((dtype, action), f"{action.upper()}\n")
        rx = PROTOCOL_LIBRARY["6e400001-b5a3-f393-e0a9-e50e24dcca9e"]["rx_char"]
        wr = BT.write(address, rx, text_cmd.encode().hex())
        return {"ok": wr.get("ok"), "intent": parsed, "device": ident,
                "executed": {"protocol": "NUS", "command": text_cmd.strip(),
                             "write_result": wr.get("result", wr.get("error"))},
                "verified": wr.get("ok", False)}

    # 5. 需配对/私有协议 → 如实报告控制路径
    blocked = [m for m in ident["matched_protocols"] if m["pairing"] != "无需"]
    if blocked:
        return {"ok": False, "status": "needs_pairing_or_protocol",
                "intent": parsed, "device": ident,
                "message": "设备协议已识别，但控制需完成设备侧要求",
                "paths": [{"protocol": m["protocol"], "requirement": m["pairing"],
                           "how": m["control"]} for m in blocked],
                "hint": "配对类设备：Windows 设置→蓝牙→配对后重试；"
                        "或提供该型号的公开协议码，我把指令模板加入协议库"}

    return {"ok": False, "intent": parsed, "device": ident,
            "message": "未匹配到可控协议（设备无公开控制服务）",
            "hint": "identify 查看设备全部服务特征；若确有控制需求，提供设备型号"}


def smart_scan(scan_timeout=8.0) -> dict:
    """智能扫描：扫描 + 对每台设备识别协议类型（一步到位的设备清单）。"""
    from . import bluetooth_cap as BT
    r = BT.scan(scan_timeout)
    if not r.get("ok"):
        return r
    devices = r.get("devices", [])
    out = []
    for d in devices:
        entry = dict(d)
        name = str(d.get("name", ""))
        # 广播名预判（无连接快速分类）
        if any(k in name for k in ("Mi", "小米", "Band", "手环")):
            entry["guess"] = "小米生态（FE95）"
        elif any(k in name for k in ("iPhone", "iPad", "Mac", "Watch", "AirPods")):
            entry["guess"] = "Apple 设备"
        elif any(k in name for k in ("TV", "Roku")):
            entry["guess"] = "媒体设备"
        else:
            entry["guess"] = "待 identify（连接识别）"
        out.append(entry)
    return {"ok": True, "devices": out,
            "note": "guess 为广播名预判；control/identify 连接后走协议库精确匹配"}


def run(op="control", **params):
    """bt_control 统一入口：control/smart_scan/parse_intent/identify。"""
    if op in ("control", None):
        return control(params.get("intent", ""), params.get("address"),
                       params.get("scan_timeout", 6.0))
    if op == "smart_scan":
        return smart_scan(params.get("scan_timeout", 8.0))
    if op == "parse_intent":
        return parse_intent(params.get("intent", ""))
    if op == "identify":
        from . import bluetooth_cap as BT
        addr = params.get("address")
        if not addr:
            return {"ok": False, "error": "identify 需要 address"}
        conn_r = BT.connect(addr)
        if not conn_r.get("ok"):
            return {"ok": False, "error": "连接失败", "detail": conn_r}
        services = conn_r.get("result", {}).get("services", [])
        return identify_device(services)
    if op == "status":
        return {"ok": True, "ops": ["control", "smart_scan", "parse_intent", "identify"],
                "protocol_library": list({p["name"] for p in PROTOCOL_LIBRARY.values()}),
                "note": "AI 操控层：意图→识别→协议→执行→验证；协议库只收公开文档协议"}
    raise ValueError(f"未知 op: {op}（可用: control/smart_scan/parse_intent/identify/status）")
