"""Phân giọng không được phụ thuộc torchcodec, và smoke test phải chạy thật.

Lỗi thật, nhật ký của người dùng 26/08/2026: cài xong, `smoke test PASS`, rồi
MỌI lượt chạy đều chết:

    Could not load libtorchcodec ...
    FileNotFoundError: Could not find module 'libtorchcodec_core9.dll'

Hai lỗi chồng lên nhau:

1. pyannote 4.x giải mã âm thanh bằng `torchcodec`, mà torchcodec đòi bản
   FFmpeg "full-shared" có DLL trên Windows. App chỉ mang `ffmpeg.exe` — đủ
   cho mọi việc khác nhưng không đủ cho torchcodec.
2. Smoke test của bộ cài chỉ `Pipeline.from_pretrained(...)` rồi in OK. Nạp
   model KHÔNG chạm tới đường giải mã, nên nó báo PASS cho một cài đặt hỏng
   100%. Smoke test chứng minh quá ít thì bằng không có.
"""
from __future__ import annotations

import ast
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(ten: str) -> str:
    return open(os.path.join(REPO, ten), encoding="utf-8").read()


def test_khong_dua_duong_dan_thang_cho_pyannote():
    """Đưa đường dẫn = để pyannote tự giải mã = phụ thuộc torchcodec."""
    src = _doc("autodub/speech/diarize_worker.py")
    assert "pipeline(args.audio" not in src, (
        "vẫn đưa đường dẫn cho pyannote — nó sẽ tự giải mã bằng torchcodec")
    assert "_nguon_am_thanh(args.audio)" in src


def test_nap_song_am_va_tron_xuong_mono():
    src = _doc("autodub/speech/diarize_worker.py")
    for nut in ast.walk(ast.parse(src)):
        if isinstance(nut, ast.FunctionDef) and nut.name == "_nguon_am_thanh":
            than = ast.get_source_segment(src, nut) or ""
            break
    else:
        raise AssertionError("không còn hàm _nguon_am_thanh")
    assert "waveform" in than and "sample_rate" in than
    assert "mean(axis=1)" in than, (
        "nhiều kênh mà chỉ lấy một kênh là mất người nói chỉ có ở kênh kia")
    assert "wave.open" in than, "phải đọc bằng thư viện chuẩn, không thêm phụ thuộc"


def test_doc_truot_thi_van_co_duong_lui():
    """WAV lạ (24-bit, float) không được làm hỏng cả lượt — máy nào có
    torchcodec lành lặn vẫn chạy được."""
    src = _doc("autodub/speech/diarize_worker.py")
    i = src.index("def _nguon_am_thanh")
    than = src[i:src.index("\ndef ", i + 10)]
    assert "return duong" in than, "đọc trượt là dừng hẳn, không có đường lui"
    assert "print(json.dumps" in than, "rơi đường lui mà không để lại dấu vết"


def test_smoke_test_phai_chay_that_khong_chi_nap_model():
    """Nạp model không chạm tới đường giải mã — đúng chỗ hỏng thật."""
    src = _doc("scripts/setup_diarization.py")
    assert "SMOKE_DECODE_FAIL" in src, (
        "smoke test không chạy thử giải mã — vẫn báo PASS cho cài đặt hỏng")
    assert "wave.open" in src, "không dựng âm thanh thật để chạy thử"
    assert "pl(d)" in src, "không thật sự chạy pipeline trên âm thanh"


def test_bao_loi_giai_ma_khong_do_toi_cho_token():
    """Lỗi giải mã mà báo 'kiểm tra token' là gửi người dùng đi sai hướng."""
    src = _doc("scripts/setup_diarization.py")
    i = src.rindex('if "SMOKE_DECODE_FAIL"')
    khoi = src[i:i + 1200]
    assert "torchcodec" in khoi and "full-shared" in khoi
