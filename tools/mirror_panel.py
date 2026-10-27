#!/usr/bin/env python3
"""用镜像多维度空间跑一遍真实变更（不拿现实当试验场）

变更内容：把 10 个镜像位接进生产面板（holo_pet_w3/panel/index.html）
          + 面板后端新增 /api/mirror（转发到能力层，白名单 fail-closed）

口径见 docs/09：先在镜像维度成形 → 体检 → 计划 → 推演 → 一致性 → 排练
                → 一次性晋升（过 deploy_publish 门）。

用法：
  python3 tools/mirror_panel.py --emit      # 只打印计划（不写任何东西）
  python3 tools/mirror_panel.py --run       # 依次跑 shape/scan/plan/simulate/parity
  python3 tools/mirror_panel.py --plan      # 只跑 plan
"""
from __future__ import annotations

import argparse
import json
import pathlib
import socket
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PANEL = "holo_pet_w3/panel/index.html"
NAME = "panel-mirror"
HOST, PORT = "127.0.0.1", 8765


def call(op: str, payload: dict | None = None) -> dict:
    body = json.dumps({"op": op, "payload": payload or {}}).encode()
    s = socket.socket()
    s.settimeout(300)
    try:
        s.connect((HOST, PORT))
        s.sendall(b"POST /api/mirror HTTP/1.0\r\nHost: x\r\n"
                  b"Content-Type: application/json\r\n"
                  b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
        buf = b""
        while True:
            c = s.recv(65536)
            if not c:
                break
            buf += c
        return json.loads(buf.split(b"\r\n\r\n", 1)[1])
    finally:
        s.close()


def result(r: dict) -> dict:
    return (r.get("gbt_result") or {}).get("result") or r.get("result") or {}


def build_plan() -> dict:
    return {
        "name": NAME,
        "plan": {
            "goal": "把镜像多维度空间（10 位）接进生产面板，且不改变现实树既有行为",
            "assumptions": [
                {"statement": "注入区块后原有导航与自卫挂件仍在",
                 "verify": "浏览器实读 DOM：gbt-mirror 存在、7 按钮、原 .rail 仍在"},
                {"statement": "/api/mirror 转发到能力层且白名单 fail-closed",
                 "verify": "POST op=bogus_op 应返回『未列出的 op（fail-closed）』"},
                {"statement": "面板后端在缺 research_status/social_platforms 时仍能启动",
                 "verify": "启动日志出现『GBT小土豆 3D 全息面板』且 :8765 可连"},
            ],
            "architecture": {
                "components": [
                    {"id": "panel_page", "responsibility": "面板页：展示镜像读数与七步入口",
                     "depends_on": []},
                    {"id": "panel_server", "responsibility": "面板后端 :8765：提供 /api/mirror",
                     "depends_on": []},
                    {"id": "capability_layer", "responsibility": "能力层 run_task：唯一真源与授权门",
                     "depends_on": []},
                    {"id": "mirror_space", "responsibility": "镜像维度存储：shape/scan/ascend",
                     "depends_on": ["capability_layer"]},
                ],
                "entrypoints": [PANEL, "holo_pet/panel_server.py"],
                "data_flow": [
                    {"from": "panel_page", "to": "panel_server"},
                    {"from": "panel_server", "to": "capability_layer"},
                    {"from": "capability_layer", "to": "mirror_space"},
                ],
            },
            "steps": [
                {"id": "S1", "action": "shape 面板页到镜像维度"},
                {"id": "S2", "action": "scan 五项体检"},
                {"id": "S3", "action": "simulate 静态推演"},
                {"id": "S4", "action": "parity 环境一致性"},
                {"id": "S5", "action": "rehearse 排练出指纹报告"},
                {"id": "S6", "action": "release 一次性晋升（过 deploy_publish 门）"},
            ],
            # 每个服务都带**可验证信号** —— 计划要求 health_url / heartbeat_file /
            # windows_service 三选一，否则报"缺少可验证信号"（实测踩到）
            "services": [
                {"name": "panel_server", "port": 8765, "host": "127.0.0.1",
                 "health_url": "http://127.0.0.1:8765/api/state"},
                {"name": "static_pages", "port": 8080, "host": "127.0.0.1",
                 "health_url": "http://127.0.0.1:8080/index.html"},
            ],
            "files": [PANEL, "holo_pet/panel_server.py"],
            # 🔴 rollback 是**计划顶层**字段，不是 rehearsal 的子键（实测踩到）
            "rollback": {
                "strategy": "command",
                "action": {"id": "rewind",
                           "argv": ["python3", "tools/mirror_rewind.py"],
                           "timeout": 120},
            },
            # 验收闭环：计划要求"代码/服务部署必须定义 rehearsal.acceptance"
            # acceptance 是**命令 id 列表**，必须引用 rehearsal.commands 里存在的 id
            # （实测：写成 {statement,evidence} 会报"acceptance 引用了不存在的命令"）
            "rehearsal": {
                "commands": [
                    {"id": "accept_probe",
                     "argv": ["python3", "tools/mirror_check.py"],
                     "timeout": 120},
                    {"id": "panel_alive",
                     "argv": ["python3", "tools/svcprobe.py", "tcp", "8765"],
                     "timeout": 30},
                ],
                "acceptance": ["accept_probe", "panel_alive"],
            },
            # 生产就在本机（同宿主）—— 计划要求显式声明，不能默认
            "environment": {
                "production": {"mode": "same_host", "platform": "linux",
                               "python": ".".join(sys.version.split()[0].split(".")[:2])},
            },
        },
    }


def show(op: str, r: dict) -> None:
    x = result(r)
    keys = [k for k in ("ok", "clean", "plan_sha", "report_sha", "tree_sha",
                        "passed", "blocked", "status", "files")
            if k in x]
    print("  %-9s ok=%-6s %s" % (op, r.get("ok"),
          " · ".join("%s=%s" % (k, str(x[k])[:60]) for k in keys)))
    if r.get("ok") is False:
        print("        错误: %s" % str(r.get("error") or x)[:240])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()

    plan = build_plan()
    if a.emit:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    if a.plan:
        show("plan", call("plan", plan))
        return 0

    if a.run:
        content = (ROOT / PANEL).read_text(encoding="utf-8")
        show("shape", call("shape", {"path": PANEL, "content": content,
                                     "note": "面板接入镜像多维度空间"}))
        srv_path = "holo_pet/panel_server.py"
        srv = (ROOT / srv_path).read_text(encoding="utf-8")
        show("shape", call("shape", {"path": srv_path, "content": srv,
                                     "note": "面板后端新增 /api/mirror"}))
        show("scan", call("scan"))
        show("plan", call("plan", plan))
        show("simulate", call("simulate", {"name": NAME}))
        show("parity", call("parity", {"name": NAME}))
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
