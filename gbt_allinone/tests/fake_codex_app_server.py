"""伪 Codex App Server：用于离线验证 GBT 桥接层的协议与事件处理。

只实现测试所需的 JSON-RPC 子集，行为与真实 app-server 的帧结构保持一致：
initialize / thread/start / turn/start / turn/interrupt，
并主动发出 item/tool/call、审批请求与流式通知。
"""
from __future__ import annotations

import json
import sys
import threading

_out_lock = threading.Lock()
_pending: dict[int, dict] = {}
_pending_lock = threading.Lock()
_next_server_id = 900


def send(obj: dict) -> None:
    with _out_lock:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def notify(method: str, params: dict) -> None:
    send({"jsonrpc": "2.0", "method": method, "params": params})


def server_request(method: str, params: dict, timeout: float = 20.0):
    """从 server 发起的请求，等待客户端回执。"""
    global _next_server_id
    with _pending_lock:
        _next_server_id += 1
        req_id = _next_server_id
        slot = {"event": threading.Event(), "result": None}
        _pending[req_id] = slot
    send({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})
    if not slot["event"].wait(timeout):
        with _pending_lock:
            _pending.pop(req_id, None)
        return None
    return slot["result"]


def _emit_turn_events(thread_id: str, turn_id: str, text: str) -> None:
    notify("turn/started", {"threadId": thread_id, "turn": {"id": turn_id}})

    if "approve-test" in text:
        verdict = server_request("item/commandExecution/requestApproval", {
            "threadId": thread_id,
            "turnId": turn_id,
            "itemId": "item-cmd-1",
            "command": "echo gbt-approval-probe",
            "cwd": ".",
        })
        notify("item/commandExecution/outputDelta", {
            "threadId": thread_id, "turnId": turn_id,
            "delta": "[approval=" + json.dumps(verdict, ensure_ascii=False) + "]\n",
        })

    call_result = server_request("item/tool/call", {
        "threadId": thread_id,
        "turnId": turn_id,
        "callId": "call-1",
        "tool": "gbt_preflight",
        "arguments": {"kind": "browser", "payload": {"op": "open"}},
    })
    answer = "tool=" + json.dumps(call_result, ensure_ascii=False, sort_keys=True) + "|pong"
    notify("item/agentMessage/delta", {
        "threadId": thread_id, "turnId": turn_id,
        "itemId": "item-msg-1",
        "delta": "tool=" + json.dumps(call_result, ensure_ascii=False, sort_keys=True),
    })
    notify("item/agentMessage/delta", {
        "threadId": thread_id, "turnId": turn_id,
        "itemId": "item-msg-1", "delta": "|pong",
    })
    notify("item/completed", {
        "threadId": thread_id, "turnId": turn_id, "startedAtMs": 1,
        "item": {
            "id": "item-msg-1", "type": "agentMessage",
            "text": answer, "phase": "final_answer",
        },
    })
    notify("turn/completed", {
        "threadId": thread_id,
        "turn": {"id": turn_id, "status": {"type": "completed"}},
    })


def handle(msg: dict) -> None:
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params") or {}

    if method is None and req_id is not None:
        with _pending_lock:
            slot = _pending.pop(req_id, None)
        if slot is not None:
            slot["result"] = msg.get("result", msg.get("error"))
            slot["event"].set()
        return

    if method == "initialize":
        send({"jsonrpc": "2.0", "id": req_id, "result": {
            "userAgent": "FakeCodex/0.0.1 (test)",
            "codexHome": "fake-home",
            "platformFamily": "windows",
            "platformOs": "windows",
        }})
    elif method == "initialized":
        return
    elif method == "thread/start":
        send({"jsonrpc": "2.0", "id": req_id, "result": {
            "thread": {"id": "thread-test-1", "cwd": params.get("cwd"),
                       "ephemeral": True},
            "model": "fake-model",
        }})
    elif method == "thread/resume":
        send({"jsonrpc": "2.0", "id": req_id, "result": {
            "thread": {"id": params.get("threadId")}, "model": "fake-model"}})
    elif method == "turn/start":
        thread_id = params.get("threadId", "thread-test-1")
        turn_id = "turn-test-1"
        send({"jsonrpc": "2.0", "id": req_id, "result": {"turn": {"id": turn_id}}})
        text = ""
        for item in params.get("input") or []:
            if item.get("type") == "text":
                text += item.get("text", "")
        threading.Thread(target=_emit_turn_events,
                         args=(thread_id, turn_id, text), daemon=True).start()
    elif method == "turn/interrupt":
        send({"jsonrpc": "2.0", "id": req_id, "result": {}})
        notify("turn/completed", {
            "threadId": params.get("threadId"),
            "turn": {"id": params.get("turnId"), "status": {"type": "interrupted"}},
        })
    elif method == "model/list":
        send({"jsonrpc": "2.0", "id": req_id, "result": {
            "data": [{"id": "fake-model", "displayName": "Fake"}]}})
    elif method == "account/read":
        send({"jsonrpc": "2.0", "id": req_id, "result": {"account": {"type": "fake"}}})
    elif req_id is not None:
        send({"jsonrpc": "2.0", "id": req_id, "result": {}})


def main() -> int:
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            handle(msg)
        except Exception as exc:  # noqa: BLE001
            if msg.get("id") is not None:
                send({"jsonrpc": "2.0", "id": msg["id"],
                      "error": {"code": -32603, "message": str(exc)}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
