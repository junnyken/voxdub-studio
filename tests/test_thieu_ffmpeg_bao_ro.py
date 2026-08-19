"""V82 — thiếu FFmpeg phải nói ra ở ĐÚNG chỗ người dùng đang đứng.

Người dùng báo (ảnh chụp 2026-08-19, v3.4.5) sau nhiều lượt loay hoay:

    [1/1] HỎNG: C:/Users/.../tap01_clip.mp4 — [WinError 2] The system cannot
          find the file specified
    [1/1] HỎNG: https://youtube.com/shorts/... — ERROR: You have requested
          merging of multiple formats but ffmpeg is not installed.

Cùng một nguyên nhân (máy chưa có FFmpeg) nhưng hiện ra bằng hai câu không
ai đoán được — một câu là mã lỗi của Windows, một câu là lời than của yt-dlp.
Người dùng chỉ thấy "bữa giờ chưa khắc phục được".

Hai việc phải làm, khoá lại ở đây: dừng SỚM với lời rõ ràng thay vì để từng
thư viện con gãy theo kiểu riêng, và dịch cả hai câu lỗi kia sang tiếng người
ở chỗ chúng hiện ra.
"""
from __future__ import annotations

import os

import pytest

from autodub import ffmpeg_deps


def test_tim_thay_ffmpeg_trong_thu_muc_bin_canh_app(tmp_path, monkeypatch):
    """Bản đóng gói nối bin/ vào PATH lúc khởi động, nhưng CLI thì không —
    phép kiểm phải tự nhìn cả hai chỗ."""
    monkeypatch.setattr(ffmpeg_deps, "app_root", lambda: str(tmp_path))
    monkeypatch.setattr("shutil.which", lambda ten: None)
    assert ffmpeg_deps.co_ffmpeg() is False

    (tmp_path / "bin").mkdir()
    ten = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    (tmp_path / "bin" / ten).write_text("")
    assert ffmpeg_deps.co_ffmpeg() is True


def test_thieu_thi_nem_loi_dung_lop_cua_tang_goi(tmp_path, monkeypatch):
    """Ném RuntimeError trần là rơi vào nhánh "lỗi ngoài dự tính" của giao
    diện; phải là lớp lỗi mà tầng gọi đã có chỗ hiển thị tử tế."""
    monkeypatch.setattr(ffmpeg_deps, "app_root", lambda: str(tmp_path))
    monkeypatch.setattr("shutil.which", lambda ten: None)

    class LoiRieng(Exception):
        pass

    with pytest.raises(LoiRieng, match="chưa có FFmpeg"):
        ffmpeg_deps.bao_dam_co_ffmpeg(LoiRieng)


def test_chep_loi_dung_ngay_tu_dau_khong_de_thu_vien_con_gay(tmp_path,
                                                             monkeypatch):
    """Đúng ca người dùng gặp: bấm Bắt đầu chép lời khi máy chưa có FFmpeg."""
    from autodub.config import Settings
    from autodub.transcribe_tool import TranscribeError, transcribe_media

    monkeypatch.setattr(ffmpeg_deps, "app_root", lambda: str(tmp_path))
    monkeypatch.setattr("shutil.which", lambda ten: None)
    monkeypatch.setattr(
        "autodub.transcribe_tool.prepare_audio",
        lambda *a, **k: pytest.fail("phải dừng TRƯỚC khi đụng tới ffmpeg"))

    with pytest.raises(TranscribeError, match="chưa có FFmpeg"):
        transcribe_media("/tmp/phim.mp4", str(tmp_path / "ra"), Settings())


@pytest.mark.parametrize("loi_that", [
    # Nguyên văn hai dòng trong ảnh chụp của người dùng.
    "[WinError 2] The system cannot find the file specified",
    "ERROR: You have requested merging of multiple formats but ffmpeg is not "
    "installed. Aborting due to --abort-on-error",
])
def test_hai_dong_loi_that_deu_duoc_dich_sang_tieng_nguoi(loi_that):
    from autodub_gui.dub_constants import friendly_error

    soan = friendly_error(loi_that)
    assert soan is not None, f"vẫn để nguyên văn: {loi_that[:40]}"
    tieu_de, cach_chua = soan
    assert "FFmpeg" in tieu_de
    assert "Tải giúp tôi" in cach_chua or "thư mục bin" in cach_chua


def test_trang_chep_loi_dich_loi_truoc_khi_in_ra():
    """Dòng HỎNG trên trang Chép lời là chỗ DUY NHẤT người dùng thấy lý do
    (bộ lọc Nhật ký của lõi loại mọi thông báo có đường dẫn/URL)."""
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = open(os.path.join(repo, "autodub_gui", "pages", "transcribe_page.py"),
               encoding="utf-8").read()
    i = src.find('if status == "hong" and detail:')
    assert i > 0
    khuc = src[i:i + 800]
    assert "friendly_error" in khuc


def test_loi_nhac_thong_nhat_giua_cac_noi():
    """Người dùng đọc ở preflight, ở Nhật ký hay ở hộp thoại đều phải thấy
    cùng một cách chữa — ba lời khuyên khác nhau là ba lần thử sai."""
    from autodub_gui.dub_constants import friendly_error

    _tieu_de, cach_chua = friendly_error("ffmpeg is not installed")
    assert "thư mục bin" in cach_chua
    assert "thư mục bin" in ffmpeg_deps.THIEU_FFMPEG
