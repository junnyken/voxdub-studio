"""Mini-spec V40 (docs/PLAN.md, Phase G) — resume-safety bugs tìm thấy trong
audit sâu 2026-08-16: cache của pipeline chỉ kiểm "file có tồn tại + đúng
shape", chưa từng kiểm có KHỚP tham số của lượt chạy hiện tại không.

1. ``_load_cached_transcript()`` (ASR, Step 3): resume sau khi đổi "Ngôn ngữ
   gốc" từng âm thầm dùng lại transcript nghe SAI ngôn ngữ.
2. ``_ensure_render_mode()`` (TTS, Step 5): resume sau khi đổi giọng đọc
   từng để lại các đoạn .wav CŨ (giọng trước) lẫn với đoạn MỚI (giọng sau)
   trong cùng 1 video.
"""
from __future__ import annotations

import json
import os

from autodub.config import Settings
from autodub.languages import get_target
from autodub.pipeline import DubPipeline


def _pipeline():
    return DubPipeline(Settings())


SEGMENTS = [
    {"id": 1, "start": 0.0, "end": 2.0, "text": "hello"},
    {"id": 2, "start": 2.0, "end": 4.0, "text": "world"},
]


# ------------------------------------------- _load_cached_transcript() ------

def test_no_transcript_file_returns_none(tmp_path):
    transcript = tmp_path / "transcript_original.json"
    marker = tmp_path / ".asr_lang"
    assert DubPipeline._load_cached_transcript(str(transcript), str(marker), "en-US") is None


def test_reuses_transcript_when_no_marker_0_regression(tmp_path):
    """Thư mục từ TRƯỚC V40 (không có marker) — coi như khớp, dùng lại như
    hành vi cũ, không ép nghe lại oan dự án có sẵn."""
    transcript = tmp_path / "transcript_original.json"
    transcript.write_text(json.dumps(SEGMENTS), encoding="utf-8")
    marker = tmp_path / ".asr_lang"   # không tồn tại

    result = DubPipeline._load_cached_transcript(str(transcript), str(marker), "en-US")
    assert result == SEGMENTS


def test_reuses_transcript_when_lang_matches(tmp_path):
    transcript = tmp_path / "transcript_original.json"
    transcript.write_text(json.dumps(SEGMENTS), encoding="utf-8")
    marker = tmp_path / ".asr_lang"
    marker.write_text("en-US", encoding="utf-8")

    result = DubPipeline._load_cached_transcript(str(transcript), str(marker), "en-US")
    assert result == SEGMENTS


def test_rejects_transcript_when_lang_changed(tmp_path):
    """Bug thật V40: đổi 'Ngôn ngữ gốc' rồi resume — transcript cũ (tiếng
    Anh) không được dùng lại cho lượt chạy đã chọn tiếng Trung."""
    transcript = tmp_path / "transcript_original.json"
    transcript.write_text(json.dumps(SEGMENTS), encoding="utf-8")
    marker = tmp_path / ".asr_lang"
    marker.write_text("en-US", encoding="utf-8")

    result = DubPipeline._load_cached_transcript(str(transcript), str(marker), "zh-CN")
    assert result is None   # phải nghe lại, KHÔNG dùng transcript tiếng Anh


def test_corrupt_transcript_json_returns_none(tmp_path):
    transcript = tmp_path / "transcript_original.json"
    transcript.write_text("not json", encoding="utf-8")
    marker = tmp_path / ".asr_lang"
    assert DubPipeline._load_cached_transcript(str(transcript), str(marker), "en-US") is None


def test_transcript_missing_required_fields_returns_none(tmp_path):
    transcript = tmp_path / "transcript_original.json"
    transcript.write_text(json.dumps([{"id": 1, "text": "hello"}]), encoding="utf-8")  # no start/end
    marker = tmp_path / ".asr_lang"
    assert DubPipeline._load_cached_transcript(str(transcript), str(marker), "en-US") is None


# ------------------------------------------------- _ensure_render_mode() ----

class _FakeVoice:
    def __init__(self, name):
        self.name = name


def _fake_catalog(monkeypatch, *names):
    """resolve() tra cứu tên trong catalog thật — thay bằng danh mục giả có
    đúng các tên test cần, tránh rơi về giọng mặc định (làm 2 tên giả khác
    nhau vô tình resolve về cùng 1 giọng, làm sai giả định của test)."""
    monkeypatch.setattr(
        "autodub.speech.tts.voices.catalog",
        lambda settings, target: [_FakeVoice(n) for n in names])


def _make_seg_dir(tmp_path, with_wav=True):
    seg_dir = tmp_path / "segments"
    seg_dir.mkdir()
    if with_wav:
        (seg_dir / "0001.wav").write_bytes(b"RIFF....")
    return seg_dir


def test_no_marker_first_run_writes_marker_no_wipe(tmp_path, monkeypatch):
    _fake_catalog(monkeypatch, "Minh Trang")
    pipeline = _pipeline()
    seg_dir = _make_seg_dir(tmp_path, with_wav=False)
    pipeline._ensure_render_mode(str(tmp_path), str(seg_dir), get_target("vi"), "Minh Trang")

    marker = seg_dir / ".render_mode"
    assert marker.exists()
    lines = marker.read_text(encoding="utf-8").splitlines()
    assert lines[0] == DubPipeline.RENDER_MODE
    assert lines[1] == "Minh Trang"


def test_old_single_line_marker_0_regression_no_wipe_from_voice(tmp_path, monkeypatch):
    """Marker cũ (trước V40, chỉ 1 dòng RENDER_MODE) — KHÔNG được coi là đổi
    giọng (current_voice=None nghĩa là "chưa biết"), tránh xóa oan cache của
    dự án tạo trước khi field này tồn tại."""
    _fake_catalog(monkeypatch, "Minh Trang")
    pipeline = _pipeline()
    seg_dir = _make_seg_dir(tmp_path, with_wav=True)
    (seg_dir / ".render_mode").write_text(DubPipeline.RENDER_MODE, encoding="utf-8")

    pipeline._ensure_render_mode(str(tmp_path), str(seg_dir), get_target("vi"), "Minh Trang")

    assert (seg_dir / "0001.wav").exists()   # KHÔNG bị xóa


def test_voice_changed_wipes_cached_wavs(tmp_path, monkeypatch):
    """Bug thật V40: resume sau khi đổi giọng đọc — .wav cũ (giọng A) phải bị
    xóa để không lẫn với .wav mới (giọng B) trong cùng video."""
    _fake_catalog(monkeypatch, "Giong A", "Giong B")
    seg_dir = _make_seg_dir(tmp_path, with_wav=True)
    wav_path = seg_dir / "0001.wav"
    marker = seg_dir / ".render_mode"
    marker.write_text(f"{DubPipeline.RENDER_MODE}\nGiong A", encoding="utf-8")

    pipeline = _pipeline()
    pipeline._ensure_render_mode(str(tmp_path), str(seg_dir), get_target("vi"), "Giong B")

    assert not wav_path.exists()   # cache giọng cũ phải bị xóa
    assert marker.read_text(encoding="utf-8").splitlines()[1] == "Giong B"


def test_same_voice_resume_keeps_cache(tmp_path, monkeypatch):
    """0 regression: resume với ĐÚNG giọng cũ vẫn dùng lại .wav như trước."""
    _fake_catalog(monkeypatch, "Minh Trang")
    pipeline = _pipeline()
    seg_dir = _make_seg_dir(tmp_path, with_wav=True)
    (seg_dir / ".render_mode").write_text(
        f"{DubPipeline.RENDER_MODE}\nMinh Trang", encoding="utf-8")

    pipeline._ensure_render_mode(str(tmp_path), str(seg_dir), get_target("vi"), "Minh Trang")

    assert (seg_dir / "0001.wav").exists()


# ------------------------------------------- _build_quality_report() --------

def test_quality_report_includes_empty_background_separation_by_default():
    report = DubPipeline._build_quality_report(get_target("vi"), SEGMENTS, {}, None)
    assert report["background_separation"] == {}


def test_quality_report_carries_vocals_quality_when_provided():
    vq = {"level": "warn", "reasons": ["Âm lượng rất nhỏ"]}
    report = DubPipeline._build_quality_report(
        get_target("vi"), SEGMENTS, {}, None, vocals_quality=vq)
    assert report["background_separation"] == vq


# --------------------------------------- _resolve_background() quality gate -
# Bug thật V40: Demucs "chạy không lỗi" không có nghĩa là tách SẠCH — trước
# đây không có tín hiệu nào phát hiện vocals.wav gần như câm. Tái dùng
# heuristic RMS/khoảng-lặng đã có ở V35 (audio_quality.analyze).

def test_resolve_background_flags_near_silent_vocals_track(monkeypatch, tmp_path):
    from pydub import AudioSegment

    def fake_separate(input_wav, output_dir, **kwargs):
        vocals = os.path.join(output_dir, "vocals.wav")
        no_vocals = os.path.join(output_dir, "no_vocals.wav")
        AudioSegment.silent(duration=500).export(vocals, format="wav")   # gần như câm
        AudioSegment.silent(duration=500).export(no_vocals, format="wav")
        return {"vocals": vocals, "no_vocals": no_vocals}

    monkeypatch.setattr(
        "autodub.media.vocal_separator.separate_vocals", fake_separate)

    pipeline = _pipeline()
    audio_path = str(tmp_path / "in.wav")
    from pydub.generators import Sine
    Sine(220).to_audio_segment(duration=200).export(audio_path, format="wav")

    pipeline._resolve_background("demucs", 0.0, audio_path, str(tmp_path))

    assert pipeline._last_vocals_quality["level"] == "fail"


def test_resolve_background_ok_vocals_no_warning(monkeypatch, tmp_path):
    from pydub import AudioSegment
    from pydub.generators import Sine

    def fake_separate(input_wav, output_dir, **kwargs):
        vocals = os.path.join(output_dir, "vocals.wav")
        no_vocals = os.path.join(output_dir, "no_vocals.wav")
        # -12dB: giọng thật không bao giờ chạm biên độ như sine full-scale
        # (mới trip đúng ngưỡng cắt tiếng của audio_quality.py) — tránh nhầm
        # "tách sạch" với "cắt tiếng" trong fixture giả này.
        tone = Sine(220).to_audio_segment(duration=2000).apply_gain(-12)
        tone.export(vocals, format="wav")
        AudioSegment.silent(duration=2000).export(no_vocals, format="wav")
        return {"vocals": vocals, "no_vocals": no_vocals}

    monkeypatch.setattr(
        "autodub.media.vocal_separator.separate_vocals", fake_separate)

    pipeline = _pipeline()
    audio_path = str(tmp_path / "in.wav")
    Sine(220).to_audio_segment(duration=200).export(audio_path, format="wav")

    pipeline._resolve_background("demucs", 0.0, audio_path, str(tmp_path))

    assert pipeline._last_vocals_quality["level"] == "ok"


def test_resolve_background_no_bg_mode_leaves_quality_empty(tmp_path):
    """0 regression: bg_mode khác "demucs" (vd "none"/"duck") không chạy
    Demucs -> không có gì để đo, field giữ nguyên rỗng mặc định."""
    pipeline = _pipeline()
    audio_path = str(tmp_path / "in.wav")
    from pydub.generators import Sine
    Sine(220).to_audio_segment(duration=200).export(audio_path, format="wav")

    pipeline._resolve_background("none", 0.0, audio_path, str(tmp_path))

    assert pipeline._last_vocals_quality == {}
