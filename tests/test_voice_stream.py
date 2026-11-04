# -*- coding: utf-8 -*-
"""voice_stream（流式语音）契约/门/API/面板验收。"""
from __future__ import annotations

import base64
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import voice_stream as VS  # noqa: E402

OK = 0
FAIL = []


def check(name, cond, got=None):
    global OK
    if cond:
        OK += 1
        print("  ok  ", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, "|", repr(got)[:200])


def main() -> int:
    print("[1] 契约（PCM16/时长/WAV）")
    r = VS.verify()
    check("verify() 全绿", r["ok"] is True, r.get("failed"))
    check("判据数 ≥ 12", r["checks"] >= 12, r["checks"])
    pcm = b"\x00\x00" * 8000
    st = VS.stats(pcm)
    check("0.5s 统计", st["duration"] == 0.5 and st["rms"] == 0.0, st)
    check("base64 往返", VS.decode_pcm(base64.b64encode(pcm).decode()) == pcm)
    check("空片拒", _raises(lambda: VS.decode_pcm("")))
    check("坏 base64 拒", _raises(lambda: VS.decode_pcm("!!!")))
    store = VS.StreamStore()
    s = store.start("s1")
    check("start", s["ok"] and s["rate"] == 16000)
    a = store.append("s1", base64.b64encode(pcm).decode())
    check("append", a["ok"] and a["duration"] == 0.5, a)
    check("未知 session", store.append("nope", base64.b64encode(pcm).decode())["ok"] is False)
    check("reset", store.reset("s1")["ok"] and store.get("s1") == b"")
    store.append("s1", base64.b64encode(pcm).decode())
    e = store.end("s1")
    check("end", e["ok"] and e["duration"] == 0.5 and e.get("pcm"))
    check("end 后无会话", store.end("s1")["ok"] is False)
    with tempfile.TemporaryDirectory() as d:
        w = VS.write_wav(pathlib.Path(d) / "x.wav", pcm)
        check("WAV", w["ok"] and pathlib.Path(d).joinpath("x.wav").is_file())
    check("schema", "rate" in VS.run("schema") and "kws" in VS.run("schema"))

    print("[2] 统一门 / API / 面板 / APP")
    reg = (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8")
    check("注册表 voice_stream", '"voice_stream": {' in reg and '"handler": "voice_stream"' in reg)
    check("api 分派", 'kind == "voice_stream"' in api)
    check("run_task 可达", _gate_ok())
    srv = (ROOT / "tools/console-server.py").read_text(encoding="utf-8")
    check("server /api/voice/stream", '"/api/voice/stream"' in srv and "voice_stream" in srv)
    idx = (ROOT / "holo_pet_w3/console/index.html").read_text(encoding="utf-8")
    check("右栏流式语音面板", 'id="vs-start"' in idx and "voice-stream-panel.js" in idx)
    js = (ROOT / "holo_pet_w3/console/voice-stream-panel.js").read_text(encoding="utf-8")
    check("UI PCM/停止", "getUserMedia" in js and "/api/voice/stream" in js and "vs-stop" in idx)
    payload = (ROOT.parent / "GBT小土豆V8桌面版" / "payload")
    if payload.is_dir():
        check("APP payload 已同步 voice_stream",
              (payload / "gbt_allinone/tools/voice_stream.py").is_file()
              and '"voice_stream": {' in (payload / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8"))
    check("文档 docs/177 存在", (ROOT / "docs/177-voice-stream.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— voice_stream（PCM16/时长/WAV/局部+最终接口）+ 统一门/API/面板/APP 全绿")
    return 0


def _raises(fn):
    try:
        fn()
        return False
    except (VS.StreamError, ValueError):
        return True


def _gate_ok():
    try:
        import gbt_allinone as g
        r = g.run_task("voice_stream", {"op": "verify"}, safe=True)
        inner = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return bool(r.get("ok")) and bool(inner.get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
