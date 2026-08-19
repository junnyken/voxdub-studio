"""V78 — việc vẫn chạy tiếp nhưng KẾT QUẢ đã khác đi thì phải nói ra.

Quét toàn bộ `logger.warning/error` của lõi rồi cho chạy qua chính
`log_text.notice_for`: 43 dòng không bao giờ tới được khung Nhật ký (rơi tự
do rồi bị `_TECH_RE` chặn vì có chữ "demucs"/"gpu"/"json"...). Phần lớn đúng
là chi tiết kỹ thuật nên ẩn — nhưng những dòng dưới đây thì người dùng LÃNH
HẬU QUẢ THẬT mà không được báo tiếng nào. Cùng lớp lỗi với V75 (canh chữ hỏng
âm thầm) và V76.

Thông báo dưới đây COPY NGUYÊN VĂN từ lõi. Đổi lời trong lõi mà quên bảng
NOTICES là dòng đó lại chìm — test này bắt đúng ca đó.
"""
from __future__ import annotations

import logging

import pytest

from autodub_gui.log_text import notice_for

# (thông báo thật của lõi, chữ BẮT BUỘC phải có trong dòng hiện ra)
CA = [
    # autodub/media/vocal_separator.py:213 — nặng nhất: video ra thiếu hẳn
    # nhạc/tiếng động nền mà người dùng chỉ phát hiện khi mở video lên nghe.
    ("Demucs separation failed: hết VRAM; falling back to silent base.",
     "nhạc"),
    ("Post-processing Demucs output failed: lỗi ffmpeg", "nhạc"),
    # autodub/editor.py:559,572 — dựng lại trong Trình chỉnh sửa
    ("no_vocals.wav missing — rebuild will use a silent base", "nhạc nền"),
    ("ai_music.wav missing — rebuild will use a silent base", "nhạc nền"),
    # Chạy được nhưng CHẬM HƠN NHIỀU — người dùng tưởng app treo
    ("Demucs GPU worker quá 60 phút — chuyển sang CPU", "CPU"),
    ("Demucs GPU worker failed (CUDA out of memory) — dùng CPU", "CPU"),
    ("Không chạy được Whisper trên GPU — dùng CPU", "CPU"),
    # Chất lượng đầu ra kém đi
    ("Model chấm câu tiếng Trung (CT-Transformer) không có — transcript sẽ "
     "KHÔNG có dấu câu, chất lượng dịch giảm", "dấu câu"),
    # Lựa chọn trong Cài đặt bị bỏ qua
    ("Paraformer chưa cài (đúp chuột 'Cai dat ASR tieng Trung "
     "(Paraformer).bat') — dùng Whisper", "Paraformer"),
    ("Paraformer chỉ hỗ trợ tiếng Trung — dùng Whisper cho ngôn ngữ 'ja'",
     "Whisper"),
    # Tiếng lệch hình
    ("atempo lỗi trên seg_12.wav — giữ tốc độ gốc (1.15)", "tốc độ"),
    ("VOICE_SPEED=3.0 ngoài khoảng [0.5, 2.0] của atempo — dùng 2.0",
     "tốc độ"),
    # Tốn tiền thật ở lượt chạy lại
    ("Không ghi được sổ dịch tạm (đĩa đầy) — chạy lại sẽ phải dịch lại các "
     "lô này", "dịch lại"),
]


@pytest.mark.parametrize("msg,phai_co", CA)
def test_nguoi_dung_duoc_bao(msg, phai_co):
    line = notice_for(msg, logging.WARNING)
    assert line is not None, f"chìm mất: {msg[:60]}"
    assert phai_co.lower() in line[0].lower(), line[0]


@pytest.mark.parametrize("msg,_p", CA)
def test_khong_lot_chu_ky_thuat_ra_giao_dien(msg, _p):
    """Lời mới phải là tiếng người: không tên tệp, không tên thư viện."""
    line = notice_for(msg, logging.WARNING)[0]
    for cam in ("demucs", "atempo", "voice_speed", ".wav", "vram", "cuda",
                "ct-transformer"):
        assert cam not in line.lower(), f"{cam!r} lọt ra Nhật ký: {line}"


def test_ra_soat_ban_dich_van_co_y_de_an():
    """Không lật quyết định cũ: dòng này đã bị ẩn có chủ đích từ trước
    (`(r"Rà soát bản dịch lỗi|Soát lại câu .* lỗi", None, ...)`). Ghi lại
    thành test để lần sau ai đổi ý thì đổi có ý thức."""
    assert notice_for("Rà soát bản dịch lỗi (hết Vox) — dùng bản lượt đầu",
                      logging.WARNING) is None


def test_chi_tiet_ky_thuat_van_bi_an():
    """Không phải cái gì cũng đẩy lên — dòng thuần kỹ thuật vẫn phải chìm."""
    assert notice_for("Share page JSON parse failed for abc: xyz",
                      logging.WARNING) is None
    assert notice_for("Worker OCR trả kết quả sai định dạng (list)",
                      logging.WARNING) is None
