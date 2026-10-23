# gbt-capability: 真 SileroVAD（ONNX）验收 —— 不碰 torch、不联网、不占声卡
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""真 SileroVAD 验收：判它**真在听**，而不是"接口返回了 ok"。

四条硬断言（任一条不成立就说明是假听）：
  ① 数字静音必须被judged为静音（max prob 要低到可忽略）
  ② **真语音**（SAPI 合成到文件，不占声卡）必须被打到高概率
  ③ 同一输入两次、reset 后再跑，结果必须逐帧一致（有状态推理不能随机）
  ④ 不可用时必须**结构化拒绝**，且调用方明确知道该退回轻量法 —— 不许悄悄降级冒充

外加一条环境红线：跑完 `torch` / `torchaudio` 一个都不许被 import
（2026-09 装 silero-vad 包把 torch 降级、打断 torchvision/easyocr 的事故不再重演）。

跑法：
    $env:GBT_STORE_DIR="$env:TEMP\\gbt_test_store"; py -3.14 -m pytest gbt_allinone/tests/test_silero_vad.py -q
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

_TENT = Path(__file__).resolve().parents[1] / "tentacle"
_SV = _TENT / "silero_vad.py"
_MODELS = Path(__file__).resolve().parents[1] / "store" / "models"

pytestmark = pytest.mark.skipif(
    not (_MODELS / "silero_vad.onnx").is_file(),
    reason="store/models 下无 silero_vad.onnx 权重",
)


def _load(name: str, path: Path):
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def sv():
    return _load("silero_vad", _SV)


@pytest.fixture(scope="module")
def speech_wav(tmp_path_factory) -> Path:
    """真语音样本：SAPI 合成写文件（**不用麦克风**，无声音也不会失败）。"""
    p = tmp_path_factory.mktemp("vadfix") / "speech.wav"
    try:
        import pythoncom
        import win32com.client as wc
        pythoncom.CoInitialize()
        st = wc.Dispatch("SAPI.SpFileStream")
        st.Open(str(p), 3, False)
        v = wc.Dispatch("SAPI.SpVoice")
        v.AudioOutputStream = st
        v.Speak("你好，我是小土豆，正在做语音活动检测。")
        st.Close()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"本机 SAPI 无法合成到文件：{type(e).__name__}: {e}")
    if not p.is_file() or p.stat().st_size < 4096:
        pytest.skip("SAPI 未产出有效 WAV")
    return p


# ------------------------------------------------------------------ ① 底数诚实

def test_probe_reports_real_engine(sv):
    p = sv.probe()
    assert p["ok"] is True, p.get("why")
    assert p["engine"] == "silero-vad-onnx"
    assert Path(p["model_path"]).is_file()
    assert p["model_sha256_16"] and len(p["model_sha256_16"]) == 16
    assert p["contract"] in {"stateful_sr", "stateful_nosr", "fixed_window"}
    assert p["providers"] and p["providers"][0] == "CPUExecutionProvider"
    assert p["expected_window"] == 576 and p["hop"] == 512
    assert abs(p["frame_ms"] - 32.0) < 1e-6


def test_all_six_weights_loadable(sv):
    ms = sv.list_models()
    assert len(ms) >= 5
    bad = [m for m in ms if not m.get("loadable")]
    assert not bad, f"权重装载失败: {bad}"
    # 契约必须由真实会话量出，且覆盖多种（不是全同一类）
    assert len({m["contract"] for m in ms}) >= 2
    for m in ms:
        assert m["bytes"] > 100_000
        assert len(m["sha256_16"]) == 16


def test_engine_info_is_manifest_safe(sv):
    i = sv.engine_info()
    assert i["available"] is True
    assert i["engine"] == "silero-vad-onnx"
    assert i["window"] == 576 and i["model_count"] >= 5
    assert "torch" not in str(i).lower()          # 说明里不许出现基于 torch 的说法
    assert i["fallback"] == "audio_vad_energy（轻量能量法）"


# ------------------------------------------------------------------ ② 真在听

def test_digital_silence_is_silent(sv):
    v = sv.SileroVad()
    ps = v.probs(np.zeros(16000, dtype=np.float32))
    assert len(ps) == 16000 // 512
    assert max(ps) < 0.05, f"静音被判成语音：max={max(ps)}"
    r = sv.vad_silero(np.zeros(16000, dtype=np.float32))
    assert r["ok"] and r["has_speech"] is False and r["segment_count"] == 0


def test_real_speech_fires(sv, speech_wav):
    a = sv.read_wav_mono16k(speech_wav)
    assert a.size > 16000, f"样本太短：{a.size}"
    assert a.dtype == np.float32 and float(np.max(np.abs(a))) <= 1.0
    r = sv.vad_silero(a)
    assert r["ok"] is True
    assert r["max_prob"] > 0.5, f"真语音没被判出来：max={r['max_prob']}"
    assert r["speech_frames"] > 0
    assert r["has_speech"] is True
    assert r["segment_count"] >= 1
    for s in r["segments"]:
        assert 0.0 <= s["start_s"] < s["end_s"] <= r["duration_s"] + 0.05
        assert s["max_prob"] >= 0.5


def test_speech_scores_far_above_silence(sv, speech_wav):
    """相对判据：真语音的峰值概率必须**远离**静音水线，不是擦边。"""
    v = sv.SileroVad()
    sil = max(v.probs(np.zeros(32000, dtype=np.float32)))
    sp = max(v.probs(sv.read_wav_mono16k(speech_wav)))
    assert sp - sil > 0.5, f"语音 {sp:.4f} 与静音 {sil:.4f} 拉不开差距"


# ------------------------------------------------------------------ ③ 确定性

def test_deterministic_two_runs(sv, speech_wav):
    a = sv.read_wav_mono16k(speech_wav)
    v = sv.SileroVad()
    assert v.probs(a) == v.probs(a)


def test_reset_restores_initial_state(sv, speech_wav):
    a = sv.read_wav_mono16k(speech_wav)
    v = sv.SileroVad()
    first = v.probs(a)
    v.probs(np.zeros(16000, dtype=np.float32))        # 污染状态
    v.reset()
    assert v.probs(a) == first, "reset 后结果不一致 ⇒ 流间状态串了"


def test_frame_math(sv):
    v = sv.SileroVad()
    for n in (512, 1024, 9999, 16000):
        assert len(v.probs(np.zeros(n, dtype=np.float32))) == n // 512


def test_wrong_frame_size_rejected(sv):
    v = sv.SileroVad()
    with pytest.raises(ValueError):
        v.prob(np.zeros(511, dtype=np.float32))
    with pytest.raises(ValueError):
        v.prob(np.zeros(576, dtype=np.float32))


def test_threshold_monotonic(sv, speech_wav):
    a = sv.read_wav_mono16k(speech_wav)
    lo = sv.vad_silero(a, threshold=0.3)["speech_frames"]
    hi = sv.vad_silero(a, threshold=0.9)["speech_frames"]
    assert 0 <= hi <= lo, f"阈值升高反而更多语音帧：{hi} > {lo}"


# ------------------------------------------------------------------ ④ 分段

def test_segments_stay_inside_speech_region(sv, speech_wav):
    """静音-语音-静音 拼装：**所有**语音段必须落在中段，静音头尾一个都不许漏进来。

    注意：不假设"合成语音是连续一句" —— 实测这句话自带 2 处自然停顿（250/320ms），
    默认 min_silence_ms=100 下**本就该切成多段**。所以这里只断言"不越界、不吞静音"。
    """
    sp = sv.read_wav_mono16k(speech_wav)
    head = np.zeros(16000, dtype=np.float32)
    tail = np.zeros(16000, dtype=np.float32)
    a = np.concatenate([head, sp, tail])
    r = sv.vad_silero(a)
    assert r["ok"]
    assert r["segment_count"] >= 1, "真语音一段都没切出来"
    lo, hi = 1.0 - 0.08, 1.0 + len(sp) / 16000 + 0.08
    for s in r["segments"]:
        assert lo <= s["start_s"], f"段起点 {s['start_s']} 侵入前导静音"
        assert s["end_s"] <= hi, f"段终点 {s['end_s']} 侵入尾部静音"
    # 纯静音区单独判：必须零段（证明段不是"到处都有"）
    assert sv.vad_silero(head)["segment_count"] == 0
    assert sv.vad_silero(tail)["segment_count"] == 0


def test_min_silence_merges_natural_pauses(sv, speech_wav):
    """把 min_silence_ms 抬过自然停顿宽度，多段应**合并成一段** —— 合并逻辑是真的在工作。

    实测本句自然停顿 ≈250/320ms，故 100ms 切开、600ms 合一。两个方向都断言。
    """
    sp = sv.read_wav_mono16k(speech_wav)
    many = sv.vad_silero(sp, min_silence_ms=100.0)
    one = sv.vad_silero(sp, min_silence_ms=600.0)
    assert many["segment_count"] >= 2, f"默认参数下自然停顿未切开：{many['segment_count']} 段"
    assert one["segment_count"] == 1, f"600ms 合并后应只剩 1 段，实得 {one['segment_count']}"
    # 合并后总时长应≈各段之和（相同阈值下语音帧数一致）
    assert one["speech_frames"] == many["speech_frames"]
    assert one["segments"][0]["end_s"] - one["segments"][0]["start_s"] > max(
        s["end_s"] - s["start_s"] for s in many["segments"])


def test_min_speech_filters_blip(sv):
    """极短噪声不该成段（min_speech_ms 生效）。"""
    v = sv.SileroVad()
    a = np.zeros(16000, dtype=np.float32)
    a[8000:8016] = 0.9
    assert v.segments(a, min_speech_ms=250.0) == []


# ------------------------------------------------------------------ ⑤ 不静默降级

def test_missing_model_is_structured_refusal(sv, tmp_path, monkeypatch):
    empty = tmp_path / "empty_models"
    empty.mkdir()
    monkeypatch.setattr(sv, "models_dir", lambda: empty)
    r = sv.vad_silero(np.zeros(16000, dtype=np.float32))
    assert r["ok"] is False and r["unavailable"] is True and r["denied"] is False
    assert r["rule"] == "silero-vad-onnx:weights"
    assert r["fallback"].startswith("audio_vad_energy")
    assert r["missing"], "拒绝时必须说清缺什么"
    with pytest.raises(sv.SileroVadUnavailable) as ei:
        sv.SileroVad()
    assert ei.value.info["unavailable"] is True and ei.value.info["denied"] is False


def test_named_model_missing_is_refusal(sv):
    with pytest.raises(sv.SileroVadUnavailable) as ei:
        sv.SileroVad(model="__no_such__.onnx")
    assert ei.value.info["rule"] == "silero-vad-onnx:model"
    assert ei.value.info["available"], "拒绝时要报出真正可选的权重"


def test_non_16k_sr_refused_not_silently_wrong(sv):
    with pytest.raises(sv.SileroVadUnavailable) as ei:
        sv.SileroVad(sr=8000)
    assert ei.value.info["rule"] == "silero-vad-onnx:sr"


# ------------------------------------------------------------------ ⑥ 输入形态

def test_int16_and_float_agree(sv, speech_wav):
    a = sv.read_wav_mono16k(speech_wav)
    i16 = np.clip(a * 32767.0, -32768, 32767).astype(np.int16)
    r_f = sv.vad_silero(a)
    r_i = sv.vad_silero(i16)
    assert r_i["ok"] and abs(r_f["max_prob"] - r_i["max_prob"]) < 1e-6


def test_resample_from_22k_wav(sv, tmp_path):
    src = tmp_path / "22k.wav"
    t = np.arange(11025) / 22050.0
    x = (0.3 * np.sin(2 * np.pi * 220 * t) * 32767).astype("<i2")
    with wave.open(str(src), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(x.tobytes())
    a = sv.read_wav_mono16k(src)
    assert a.dtype == np.float32
    assert abs(a.size - 8000) <= 2, f"重采样后长度 {a.size} 偏离 8000"
    assert float(np.max(np.abs(a))) <= 1.0


def test_stereo_wav_downmixed(sv, tmp_path):
    src = tmp_path / "st.wav"
    left = (0.5 * np.sin(2 * np.pi * 300 * np.arange(8000) / 16000) * 32767).astype("<i2")
    inter = np.empty(16000, dtype="<i2")
    inter[0::2], inter[1::2] = left, -left
    with wave.open(str(src), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(inter.tobytes())
    a = sv.read_wav_mono16k(src)
    assert a.size == 8000
    assert float(np.max(np.abs(a))) < 0.01, "左右反相后单声道化应几乎抵消"


# ------------------------------------------------------------------ ⑦ 环境红线

def test_torch_is_never_imported():
    """子进程验证：只走真 VAD 的路径，重型 ML 栈一个都不许被 import。

    判据用**具名黑名单**（这才是真判据）；模块总数只作参考上界——
    实测 numpy+onnxruntime 本身的真实开销就是 215 个模块，不能拿拍脑袋的 120 当红线。
    """
    heavy = ("torch", "torchaudio", "torchvision", "easyocr", "cv2",
             "transformers", "tensorflow", "keras", "jax")
    code = (
        "import sys, json, numpy as np;"
        f"sys.path.insert(0, r'{_TENT}');"
        "import silero_vad as sv;"
        "r = sv.vad_silero(np.zeros(16000, dtype=np.float32));"
        f"heavy = {heavy!r};"
        "print(json.dumps({'ok': r['ok'],"
        " 'loaded': [m for m in heavy if m in sys.modules],"
        " 'mods': len(sys.modules)}))"
    )
    cp = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    assert cp.returncode == 0, cp.stderr[-800:]
    import json
    got = json.loads(cp.stdout.strip().splitlines()[-1])
    assert got["ok"] is True
    assert got["loaded"] == [], f"真 VAD 路径加载了重型 ML 栈：{got['loaded']}"
    assert got["mods"] < 400, f"模块数异常膨胀：{got['mods']}"


def test_no_network_and_no_store_writes(sv):
    """健壮性：模块只读权重，绝不在 store/models 里造文件。"""
    before = {p.name: p.stat().st_mtime_ns for p in _MODELS.iterdir()}
    sv.vad_silero(np.zeros(16000, dtype=np.float32))
    after = {p.name: p.stat().st_mtime_ns for p in _MODELS.iterdir()}
    assert before == after, "权重目录被改动"


# ------------------------------------------------------------------ ⑧ 触手接线

@pytest.fixture(scope="module")
def tent():
    mod = _load("_ot_vad_test", _TENT / "omni_tentacle.py")
    return mod.OmniTentacle()


def test_tentacle_exposes_vad_methods(tent):
    acts = tent.available_actions()
    names = set(acts) if isinstance(acts, (list, tuple, set)) else set(acts.keys())
    for m in ("audio_vad_silero", "audio_vad_models", "audio_vad_energy"):
        assert m in names, f"触手未暴露 {m}"


def test_tentacle_vad_models_probe(tent):
    r = tent.audio_vad_models()
    assert r["ok"] is True and r["engine"] == "silero-vad-onnx"
    assert r["model_count"] >= 5 if "model_count" in r else len(r["models"]) >= 5


def test_tentacle_vad_on_silence_is_honest(tent):
    r = tent.audio_vad_silero(audio=np.zeros(16000, dtype=np.float32))
    assert r["ok"] is True and r["has_speech"] is False
    assert r["note"].startswith("真 SileroVAD")


def test_manifest_gap_no_longer_claims_no_silero(tent):
    """MANIFEST 里不许再出现"不是 SileroVAD"这种过期说法，也不许说没有流式。"""
    import gbt_allinone.tentacle.omni_audio as oa  # noqa: PLC0415
    blob = " ".join(oa.AUDIO_GAPS)
    assert "已有**真 SileroVAD**" in blob
    assert "不是 SileroVAD" not in blob
    assert "无实时打断" not in blob
