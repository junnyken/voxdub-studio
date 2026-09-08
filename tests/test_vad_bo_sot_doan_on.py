"""G3 (docs/MINI-SPEC_G3_VAD_Bo_Sot_Doan_On.md) — Silero VAD mặc định
(``threshold=0.5``) bỏ sót cả đoạn thoại thật khi nhạc nền/hiệu ứng dồn dập.
Tái hiện thật trên video *Sing 2* (cảnh cả nhóm chạy trốn): bản VAD BẬT (đúng
đường app dùng) mất TRẮNG 38 giây, 6 câu, dù âm lượng đoạn đó không khác gì
đoạn nghe bình thường (đo bằng ``ffmpeg volumedetect`` — không phải do quá
to). Đo trực tiếp bằng ``faster_whisper.vad.get_speech_timestamps``: hạ
``threshold`` xuống 0.3 giúp phát hiện thêm audio nói, và trên video nói liên
tục (16 phút, 99% có tiếng) hạ threshold KHÔNG làm phình thêm audio "phát
hiện được" (961,3s → 962,6s, +0,1%) — an toàn, không sinh thêm đoạn giả.

Ba nơi dùng chung một model Silero VAD, phải khớp threshold (lớp lỗi #2 của
dự án — sửa một đường quên đường kia): ``asr_whisper_worker.py`` (Whisper,
đường subprocess — đường THẬT của bản .exe), ``transcriber.py`` (Whisper,
đường in-process — chỉ dùng khi chạy từ mã nguồn), ``asr_paraformer_worker.py``
(Paraformer, tiếng Trung — CÙNG rủi ro vì cùng model Silero VAD).

Scope C (thêm sau, cùng ngày): hạ threshold một mình KHÔNG đóng hết được
khoảng trống ở ca cực đoan (ngay cả threshold=0.1 vẫn còn ~15s không phát
hiện được). Thêm cơ chế "vá khoảng trống": sau khi nghe xong, dò khoảng cách
BẤT THƯỜNG giữa 2 câu liên tiếp rồi nghe lại đúng đoạn đó, TẮT HẲN VAD.
"""
from __future__ import annotations

import os
import re
import sys
import textwrap
import wave

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(*parts: str) -> str:
    return open(os.path.join(REPO, *parts), encoding="utf-8").read()


# --------------------------------------------------------------------- #
# Canh cấu hình — rẻ, không cần model, chạy luôn trong CI.

def test_whisper_subprocess_ha_threshold_vad():
    src = _doc("autodub", "speech", "asr_whisper_worker.py")
    assert '"threshold": 0.3' in src, (
        "threshold VAD phải hạ xuống 0.3 (G3) — mặc định 0.5 bỏ sót cả đoạn "
        "thoại thật khi nhạc nền/hiệu ứng dồn dập")


def test_whisper_in_process_khop_threshold_voi_subprocess():
    """Hai đường Whisper (subprocess + in-process) PHẢI cùng threshold — sửa
    một đường quên đường kia là đúng lớp lỗi #2 đã lặp lại nhiều lần."""
    src = _doc("autodub", "speech", "transcriber.py")
    assert '"threshold": 0.3' in src


def test_paraformer_khop_threshold_voi_whisper():
    """Paraformer dùng CHUNG model Silero VAD — cùng bug, cùng ngưỡng."""
    src = _doc("autodub", "speech", "asr_paraformer_worker.py")
    assert "vad_cfg.silero_vad.threshold = 0.3" in src


def test_khong_ha_threshold_qua_thap_ma_khong_ban_ghi():
    """0.3 là ngưỡng ĐÃ ĐO — không phải số đoán. Nếu ai đó đổi tiếp (vd 0.1),
    phải kèm số liệu đo lại (giống G3), không chỉnh tay theo cảm tính. Test
    này chỉ khoá giá trị hiện tại, không cấm đổi — đổi thì phải sửa test
    cùng lúc, đúng nghĩa "chỉnh có chủ đích, không phải quên"."""
    for path, needle in (
        ("autodub/speech/asr_whisper_worker.py", r'"threshold":\s*([\d.]+)'),
        ("autodub/speech/transcriber.py", r'"threshold":\s*([\d.]+)'),
        ("autodub/speech/asr_paraformer_worker.py",
         r"silero_vad\.threshold\s*=\s*([\d.]+)"),
    ):
        src = _doc(*path.split("/"))
        m = re.search(needle, src)
        assert m, f"không tìm thấy threshold trong {path}"
        assert float(m.group(1)) == pytest.approx(0.3), (
            f"{path}: threshold đã đổi khỏi 0.3 (giá trị đã đo ở G3) mà "
            "không có test/tài liệu đo lại đi kèm")


# --------------------------------------------------------------------- #
# Đo thật bằng model Silero VAD thật (đã có sẵn trong .venv-whisper, không
# cần tải gì thêm) — xác nhận CƠ CHẾ, không chỉ tin vào con số trong comment.

def _co_faster_whisper() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _co_faster_whisper(), reason=(
    "Cần faster-whisper — chạy bằng .venv-whisper/bin/python hoặc "
    ".venv-test/bin/python (cả hai đều có) nếu muốn tự verify."))
def test_threshold_thap_hon_phat_hien_nhieu_audio_hon_tren_nhieu_tren():
    """Không dùng audio thật (bản quyền phim Sing 2) — tổng hợp tín hiệu mô
    phỏng ĐÚNG cơ chế đã đo: một đoạn giống-giọng-nói cường độ thấp bị chôn
    trong nhiễu, để xác nhận HƯỚNG tác động của threshold mà không cần audio
    thật. Không kỳ vọng khớp số liệu tuyệt đối của G3 (đó là môi trường thật,
    xem docs/TEST_LOG.md) — chỉ khoá đúng HƯỚNG: threshold thấp hơn không
    bao giờ phát hiện ÍT audio hơn threshold cao hơn."""
    import numpy as np
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    rng = np.random.default_rng(0)
    sr = 16000
    # Nhiễu nền liên tục (mô phỏng nhạc/hiệu ứng) trộn với vài đoạn biên độ
    # cao hơn xen kẽ (mô phỏng có lời nói nhưng bị nhiễu che bớt) — không
    # cần giống giọng người thật, chỉ cần tạo tín hiệu mà độ tin cậy VAD
    # dao động quanh ngưỡng 0.3-0.5 để thấy chênh lệch.
    duration_s = 20
    n = duration_s * sr
    noise = rng.normal(0, 0.02, n).astype("float32")
    for start_s in (3, 8, 13):
        seg = slice(start_s * sr, (start_s + 2) * sr)
        noise[seg] += (rng.normal(0, 0.06, 2 * sr)).astype("float32")

    ts_cao = get_speech_timestamps(
        noise, VadOptions(threshold=0.5, min_silence_duration_ms=500),
        sampling_rate=sr)
    ts_thap = get_speech_timestamps(
        noise, VadOptions(threshold=0.3, min_silence_duration_ms=500),
        sampling_rate=sr)
    tong_cao = sum(t["end"] - t["start"] for t in ts_cao)
    tong_thap = sum(t["end"] - t["start"] for t in ts_thap)
    assert tong_thap >= tong_cao, (
        "threshold thấp hơn phải phát hiện được audio NHIỀU HƠN HOẶC BẰNG, "
        "không bao giờ ít hơn — nếu test này đỏ, model VAD hoặc API đã đổi "
        "hành vi, cần điều tra lại trước khi tin số liệu G3")


# --------------------------------------------------------------------- #
# Scope C — vá khoảng trống. `_tim_khoang_trong_bat_thuong` là hàm thuần,
# test trực tiếp không cần audio/model.

def test_khong_co_khoang_trong_thi_khong_vá_gì():
    from autodub.speech.transcriber import _tim_khoang_trong_bat_thuong

    segs = [{"start": 0.0, "end": 2.0}, {"start": 3.0, "end": 5.0},
            {"start": 6.0, "end": 8.0}]
    assert _tim_khoang_trong_bat_thuong(segs) == []


def test_khoang_trong_ngan_binh_thuong_khong_bi_coi_la_bat_thuong():
    """Ngừng lấy hơi/dấu chấm câu vài giây là chuyện bình thường, không phải
    dấu hiệu VAD bỏ sót — chỉ khoảng RẤT DÀI mới đáng nghi."""
    from autodub.speech.transcriber import _tim_khoang_trong_bat_thuong

    segs = [{"start": 0.0, "end": 2.0}, {"start": 8.0, "end": 10.0}]  # 6s
    assert _tim_khoang_trong_bat_thuong(segs) == []


def test_khoang_trong_dai_bat_thuong_duoc_phat_hien_dung_moc():
    from autodub.speech.transcriber import _tim_khoang_trong_bat_thuong

    segs = [{"start": 0.0, "end": 45.5}, {"start": 91.2, "end": 95.0}]  # 45.7s
    assert _tim_khoang_trong_bat_thuong(segs) == [(45.5, 91.2)]


def test_nhieu_khoang_trong_deu_duoc_liet_ke():
    from autodub.speech.transcriber import _tim_khoang_trong_bat_thuong

    segs = [
        {"start": 0.0, "end": 10.0},
        {"start": 30.0, "end": 32.0},   # khoảng 1: 20s
        {"start": 34.0, "end": 36.0},   # bình thường: 2s
        {"start": 60.0, "end": 62.0},   # khoảng 2: 24s
    ]
    assert _tim_khoang_trong_bat_thuong(segs) == [(10.0, 30.0), (36.0, 60.0)]


# --------------------------------------------------------------------- #
# Tích hợp thật: `_va_khoang_trong` cắt audio thật bằng ffmpeg rồi gọi lại
# đúng đường subprocess thật (worker giả, đúng khuôn
# test_translate_local_watchdog.py — không mock Popen, chạy tiến trình con
# thật để canh đúng hành vi thật, không phải hành vi giả lập của mock).

def _wav_im_lang(path: str, seconds: float = 100.0) -> None:
    """Audio giả (im lặng) đủ dài để cắt — worker giả không thật sự nghe."""
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))


def _worker_gia_tra_ve(tmp_path, cau: list[dict]) -> str:
    """Worker giả mô phỏng đúng giao thức JSON của asr_whisper_worker.py —
    LUÔN trả về `cau` bất kể audio thật là gì (test hành vi ghép/dời mốc
    thời gian của `_va_khoang_trong`, không test chất lượng nghe)."""
    path = tmp_path / "fake_asr_worker.py"
    path.write_text(textwrap.dedent(f"""
        import json, sys
        print(json.dumps({{"ready": True}}), flush=True)
        line = sys.stdin.readline()
        req = json.loads(line)
        assert req.get("vad_filter") is False, (
            "vá khoảng trống PHẢI gọi với vad_filter=False, nếu không thì "
            "gặp lại đúng bug đang sửa")
        for c in {cau!r}:
            print(json.dumps({{"seg": True, **c}}), flush=True)
        print(json.dumps({{"done": True}}), flush=True)
    """), encoding="utf-8")
    return str(path)


def _settings_gia(monkeypatch, worker_path):
    from autodub.config import Settings

    settings = Settings()
    monkeypatch.setattr(settings, "whisper_venv_configured", lambda: True)
    monkeypatch.setattr(settings, "whisper_venv_python_path",
                        lambda: sys.executable)
    monkeypatch.setattr(settings, "whisper_model_dir_path", lambda: "/tmp")
    monkeypatch.setattr("autodub.speech.transcriber._WHISPER_WORKER_SCRIPT",
                        worker_path)
    return settings


def test_va_khoang_trong_chen_dung_cau_moi_va_doi_moc_thoi_gian(
        monkeypatch, tmp_path):
    from autodub.speech.transcriber import _va_khoang_trong

    audio_path = str(tmp_path / "goc.wav")
    _wav_im_lang(audio_path, seconds=100)
    # Worker giả "nghe" ra 1 câu ở giây 2 CỦA ĐOẠN CẮT — sau khi vá phải
    # thành 47.5s (45.5 + 2) trong hệ mốc thời gian audio GỐC.
    worker = _worker_gia_tra_ve(
        tmp_path, [{"id": 1, "start": 2.0, "end": 4.0, "text": "câu bị lọt"}])
    settings = _settings_gia(monkeypatch, worker)

    segments = [{"id": 1, "start": 0.0, "end": 45.5, "text": "a"},
               {"id": 2, "start": 91.2, "end": 95.0, "text": "b"}]
    ket_qua = _va_khoang_trong(segments, audio_path, "en", settings)

    assert len(ket_qua) == 3
    vá = next(s for s in ket_qua if s["text"] == "câu bị lọt")
    assert vá["start"] == pytest.approx(47.5)
    assert vá["end"] == pytest.approx(49.5)
    # Câu vá nằm ĐÚNG VỊ TRÍ theo thời gian, giữa câu 1 và câu 2 cũ.
    assert [s["text"] for s in ket_qua] == ["a", "câu bị lọt", "b"]


def test_khong_co_khoang_trong_thi_khong_goi_asr_them(monkeypatch, tmp_path):
    """Video bình thường (không có khoảng trống bất thường) không được tốn
    thêm một lượt ASR nào — vá chỉ kích hoạt đúng lúc cần."""
    from autodub.speech.transcriber import _va_khoang_trong

    goi = {"so_lan": 0}

    def _khong_duoc_goi(*a, **k):
        goi["so_lan"] += 1
        return []

    monkeypatch.setattr("autodub.speech.transcriber._nghe_lai_khong_vad",
                        _khong_duoc_goi)
    settings = object()  # không cần dùng nếu không có khoảng trống
    segments = [{"id": 1, "start": 0.0, "end": 2.0, "text": "a"},
               {"id": 2, "start": 3.0, "end": 5.0, "text": "b"}]
    ket_qua = _va_khoang_trong(segments, "khong-can-dung", "en", settings)
    assert ket_qua == segments
    assert goi["so_lan"] == 0


def test_nghe_lai_khong_vad_that_tu_nuot_loi_ffmpeg(tmp_path):
    """`_nghe_lai_khong_vad` THẬT (không mock) phải tự nuốt lỗi ffmpeg (audio
    không tồn tại) và trả về [] — vá thêm là VỚT, không được văng lỗi làm
    hỏng cả lượt chép lời chính vì một đoạn vá phụ thất bại."""
    from autodub.config import Settings
    from autodub.speech.transcriber import _nghe_lai_khong_vad

    ket_qua = _nghe_lai_khong_vad(
        str(tmp_path / "khong_ton_tai.wav"), 10.0, 20.0, "en", Settings())
    assert ket_qua == []
