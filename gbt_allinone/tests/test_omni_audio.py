"""omni_audio（听与说域）验收。

重点在**四条诚实性断言**：
  ① 设备枚举真读 winmm，读不到就如实说读不到（不许编设备）
  ② WAV 头解析正确，非 WAV 明确拒绝（不假装能放）
  ③ **轻量 VAD 的判定要跟信号对上**（静音不触发、有声触发）
  ④ **采集做不到就返回失败，绝不返回假音频**

跑法：
    $env:GBT_STORE_DIR="$env:TEMP\\gbt_test_store"; py -3.14 -m pytest gbt_allinone/tests/test_omni_audio.py -q
"""

from __future__ import annotations

import importlib.util
import math
import struct
import sys
import wave
from pathlib import Path

import pytest

_T = Path(__file__).resolve().parents[1] / "tentacle" / "omni_audio.py"


def _load():
    if str(_T.parent) not in sys.path:
        sys.path.insert(0, str(_T.parent))
    spec = importlib.util.spec_from_file_location("_oa_test", str(_T))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_oa_test"] = mod
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def au():
    mod = _load()
    return mod, mod.OmniAudioMixin()


@pytest.fixture()
def wav(tmp_path):
    """造一个 440Hz / 1 秒 / 16k / 单声道 的 WAV。"""
    p = tmp_path / "tone.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"".join(
            struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * i / 16000)))
            for i in range(16000)))
    return p


def test_devices_are_reported_honestly(au):
    """① 设备枚举：ok 时给结构，不 ok 时给原因 —— **两种都不许编设备**。"""
    _, t = au
    d = t.audio_devices()
    assert "inputs" in d and "outputs" in d
    if d["ok"]:
        assert d["count_in"] == len(d["inputs"]) and d["count_out"] == len(d["outputs"])
        for x in d["inputs"] + d["outputs"]:
            assert "name" in x or "error" in x, "每条要么有名字要么有错误原因"
    else:
        assert d.get("note") or d.get("error")


def test_wav_info_parses_header(au, wav):
    _, t = au
    info = t.audio_wav_info(str(wav))
    assert info["ok"] is True
    assert info["rate"] == 16000 and info["channels"] == 1 and info["sampwidth"] == 2
    assert info["frames"] == 16000 and info["seconds"] == 1.0


def test_wav_info_refuses_non_wav(au, tmp_path):
    _, t = au
    junk = tmp_path / "x.wav"
    junk.write_bytes(b"not a wave file at all")
    got = t.audio_wav_info(str(junk))
    assert got["ok"] is False and "不是能认的 WAV" in got["error"]


def test_play_refuses_non_wav_extension(au, tmp_path):
    """② 不假装能放：winsound 只放 WAV，别的格式当面拒绝。"""
    _, t = au
    mp3 = tmp_path / "a.mp3"
    mp3.write_bytes(b"\x00" * 16)
    got = t.audio_play_wav(str(mp3))
    assert got["ok"] is False and "只放 WAV" in got["error"]


def test_speak_refuses_empty_text(au):
    _, t = au
    got = t.audio_speak("   ")
    assert got["ok"] is False and "不猜" in got["error"]


def test_vad_matches_the_signal(au):
    """③ VAD 必须跟信号对上：前半静音、后半 300Hz 正弦。"""
    _, t = au
    sil = [0.0] * 8000
    tone = [0.5 * math.sin(2 * math.pi * 300 * i / 16000) for i in range(8000)]
    r = t.audio_vad_energy(sil + tone, rate=16000, frame_ms=30)
    assert r["ok"] is True
    half = len(r["detail"]) // 2
    assert not any(f["voiced"] for f in r["detail"][:half - 2]), "静音段不该被判成有声"
    assert any(f["voiced"] for f in r["detail"][half + 2:]), "有声段必须被判成有声"
    assert 0.3 < r["voiced_ratio"] < 0.7


def test_vad_accepts_16bit_pcm_bytes(au):
    """16 位 PCM bytes 也要能吃（流水线里拿到的就是 bytes）。"""
    _, t = au
    pcm = b"".join(struct.pack("<h", int(15000 * math.sin(2 * math.pi * 440 * i / 16000)))
                   for i in range(16000))
    r = t.audio_vad_energy(pcm, rate=16000, frame_ms=50)
    assert r["ok"] is True and r["voiced_ratio"] > 0.9
    assert "不是 SileroVAD" in r["note"], "必须写明这不是 Silero"


def test_vad_refuses_empty(au):
    _, t = au
    assert t.audio_vad_energy(b"")["ok"] is False
    assert t.audio_vad_energy([])["ok"] is False


def test_record_never_returns_fake_audio(au, tmp_path):
    """④ **最重要的一条**：麦克风做不到时必须失败，且不许产出任何音频文件。"""
    _, t = au
    out = tmp_path / "should_not_exist.wav"
    got = t.audio_record(seconds=1.0, path=str(out), source="mic")
    assert got["ok"] is False, "本机没有麦克风，不许报成功"
    assert got.get("verified") is False
    assert not out.exists(), "失败路径绝不许留下音频文件（那就是假音频）"
    assert got.get("error")


def test_record_rejects_unknown_source(au):
    _, t = au
    got = t.audio_record(source="telepathy")
    assert got["ok"] is False and "不认识的 source" in got["error"]


# ── WASAPI 回环（真·耳朵）───────────────────────────────────────────────

def test_loopback_capture_is_real_or_honestly_fails(au, tmp_path):
    """⑤ 回环：**契约分两层** —— `chain_ok`（链路打通）与 `verified`（真抓到帧）。

    这是实测逼出来的细化：首版让 0 帧也回 `verified=True`，那是**过度声称**。
    现在：0 帧 ⇒ `verified=False` 且必须带 `note` 说明为什么；有帧 ⇒ `verified=True`
    且格式必须自洽（字节数是块的整数倍）+ 落盘能复读。
    """
    _, t = au
    out = tmp_path / "loop.wav"
    got = t.audio_loopback(seconds=0.4, path=str(out))
    if not got.get("ok"):
        assert got.get("verified") is not True
        assert got.get("error")
        pytest.skip("本机回环不可用（如实失败）：%s" % got.get("error"))
    assert got["chain_ok"] is True, "ok 就意味着链路打通了"
    if got["frames"] == 0:
        assert got["verified"] is False, "**0 帧不许算 verified**"
        assert got.get("note"), "没抓到帧必须说明原因"
        # 0 帧落盘会产生一个**只有 44 字节头的合法 WAV**（那是正常的），
        # 所以判据是"里面没有音频帧"，不是"文件是 0 字节"。
        if out.exists():
            assert t.audio_wav_info(str(out))["frames"] == 0
        pytest.skip("链路通了但此刻该端点没有数据在流（如系统没在出声）")
    assert got["verified"] is True
    assert got["rate"] > 0 and got["channels"] > 0 and got["bits"] in (8, 16, 24, 32)
    block = got["channels"] * (got["bits"] // 8)
    assert got["bytes"] % block == 0, "字节数必须是块的整数倍（否则帧对齐就是错的）"
    assert out.exists(), "给了 path 就必须落盘"
    info = t.audio_wav_info(str(out))
    assert info["ok"] and info["rate"] == got["rate"] and info["channels"] == got["channels"]
    assert "silent" in got, "`silent` 只说明此刻系统没出声，**不是**采集失败 —— 这个语义必须带上"


def test_loopback_format_is_not_forced(au, tmp_path):
    """回环格式由系统定（官方约束：必须与渲染端点一致）——
    调用方传的 rate 不许覆盖它，只能如实提示。"""
    _, t = au
    got = t.audio_record(seconds=0.3, rate=8000, source="loopback")
    if not got.get("ok"):
        pytest.skip("本机回环不可用：%s" % got.get("error"))
    assert got["rate"] != 8000 or "note_format" in got, \
        "回环下系统给的采样率不该被 8000 悄悄改掉"


def test_gaps_are_declared(au):
    """缺口必须写在模块里（和 MANIFEST 同口径）。"""
    mod, _ = au
    gaps = " ".join(mod.AUDIO_GAPS)
    assert "麦克风" in gaps and "流式" in gaps and "声纹" in gaps and "SileroVAD" in gaps


# ── 流式分段（流式 ASR 的前置件 + 打断的判据）────────────────────────────

def _tone(rate, sec, f=300, amp=0.5):
    return [amp * math.sin(2 * math.pi * f * i / rate) for i in range(int(rate * sec))]


def _sil(rate, sec):
    return [0.0] * int(rate * sec)


def test_segment_finds_exactly_the_speech_spans(au):
    """⑥ 分段必须切在真语音上：静0.5+语0.6+静0.5+语0.4+静0.8 ⇒ **恰好 2 段**，
    且边界含 0.1s 前导（防切字头）。"""
    _, t = au
    rate = 16000
    pcm = (_sil(rate, 0.5) + _tone(rate, 0.6) + _sil(rate, 0.5)
           + _tone(rate, 0.4) + _sil(rate, 0.8))
    r = t.audio_segment(pcm, rate=rate, frame_ms=30,
                        min_speech_ms=150, min_silence_ms=300, pad_ms=100)
    assert r["ok"] is True and r["count"] == 2, "应当恰好切出 2 段：%s" % r["segments"]
    a, b = r["segments"]
    assert abs(a["start_s"] - 0.40) < 0.08 and abs(a["end_s"] - 1.10) < 0.08, a
    assert abs(b["start_s"] - 1.50) < 0.08 and abs(b["end_s"] - 2.00) < 0.08, b
    assert a["open"] is False and b["open"] is False, "都等到了静音，不该标 open"


def test_segment_marks_open_when_no_trailing_silence(au):
    """末尾没等到静音 ⇒ 那段也要收，且**如实标 open=True**（不假装正常收尾）。"""
    _, t = au
    rate = 16000
    pcm = _sil(rate, 0.3) + _tone(rate, 0.8)
    r = t.audio_segment(pcm, rate=rate, min_speech_ms=150, min_silence_ms=300)
    assert r["count"] == 1 and r["segments"][0]["open"] is True


def test_segment_ignores_too_short_blips(au):
    """太短的响声（< min_speech_ms）不该被当成一句 —— 那是噪声。"""
    _, t = au
    rate = 16000
    pcm = _sil(rate, 0.3) + _tone(rate, 0.05) + _sil(rate, 0.6)
    r = t.audio_segment(pcm, rate=rate, min_speech_ms=150, min_silence_ms=300)
    assert r["count"] == 0, "50ms 的响声不该算一句：%s" % r["segments"]


def test_segment_returns_pcm_slices_for_bytes(au):
    """喂 16 位 PCM bytes 时，每段要能切出对应字节（下游 ASR 要的就是这段）。"""
    _, t = au
    rate = 16000
    vals = _sil(rate, 0.3) + _tone(rate, 0.5) + _sil(rate, 0.5)
    pcm = b"".join(struct.pack("<h", int(v * 32767)) for v in vals)
    r = t.audio_segment(pcm, rate=rate, min_speech_ms=150, min_silence_ms=300)
    assert r["count"] == 1
    seg = r["segments"][0]
    assert isinstance(seg["pcm"], bytes) and len(seg["pcm"]) > 0
    assert len(seg["pcm"]) % 2 == 0


def test_segment_refuses_empty(au):
    _, t = au
    assert t.audio_segment(b"")["ok"] is False
    assert t.audio_segment([])["ok"] is False


def test_stream_and_barge_in_fail_honestly_without_endpoint(au):
    """⑦ 流式与打断：听不到就必须如实说听不到，**不许假装打断成功**。"""
    _, t = au
    got = t.audio_stream(seconds=0.3, flow="mic")
    if not got.get("ok"):
        assert got.get("error")
    bi = t.audio_barge_in(flow="mic", seconds=0.3)
    assert "interrupted" in bi
    if not bi.get("ok"):
        assert bi["interrupted"] is False
        assert "不假装" in (bi.get("note") or "") or bi.get("error")