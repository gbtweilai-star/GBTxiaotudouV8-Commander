# -*- coding: utf-8 -*-
"""kws（声学唤醒）契约/API/接线验收。"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import kws as K  # noqa: E402

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
    print("[1] 契约/模型/唤醒")
    r = K.verify()
    check("verify() 全绿", r["ok"] is True, r.get("failed"))
    check("判据数 ≥ 7", r["checks"] >= 7, r["checks"])
    st = K.available()
    check("sherpa 可用", st.get("ok") is True, st)
    check("本地/无密钥", st.get("local") is True and st.get("key_required") is False)
    check("关键词小土豆", "小土豆" in str(st.get("keywords")))
    fixture = ROOT / "tests" / "fixtures" / "kws-wake.wav"
    hit = K.detect_wav(fixture)
    check("TTS 唤醒", hit.get("wake") is True and hit.get("word") == "小土豆", hit)
    silent = K.detect_pcm(b"\x00\x00" * 8000)
    check("静音不唤醒", silent.get("wake") is False, silent)
    check("空 PCM 不唤醒", K.detect_pcm(b"")["wake"] is False)

    print("[2] 统一门 / API / 语音流 / APP")
    reg = (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8")
    check("注册表 kws", '"kws": {' in reg and '"handler": "kws"' in reg)
    check("api 分派 kws", 'kind == "kws"' in api)
    check("run_task 可达", _gate_ok())
    srv = (ROOT / "tools/console-server.py").read_text(encoding="utf-8")
    check("server /api/kws", '"/api/kws"' in srv and "kws" in srv)
    check("语音流接声学唤醒", "acoustic_wake" in srv and "detect_pcm" in srv)
    js = (ROOT / "holo_pet_w3/console/voice-stream-panel.js").read_text(encoding="utf-8")
    check("UI 显示声学唤醒", "acoustic_wake" in js and "声学唤醒" in js)
    payload = (ROOT.parent / "GBT小土豆V8桌面版" / "payload")
    if payload.is_dir():
        check("APP payload 已同步 kws",
              (payload / "state/kws/keywords.txt").is_file()
              and (payload / "state/kws/sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01/tokens.txt").is_file()
              and (payload / "gbt_allinone/tools/kws.py").is_file())
    check("文档 docs/179 存在", (ROOT / "docs/179-kws.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— kws（sherpa-onnx 声学唤醒/静音不唤醒/语音流接线）全绿")
    return 0


def _gate_ok():
    try:
        import gbt_allinone as g
        r = g.run_task("kws", {"op": "verify"}, safe=True)
        inner = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return bool(r.get("ok")) and bool(inner.get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
