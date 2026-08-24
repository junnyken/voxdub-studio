"""C25 — cắt tệp dài thành nhiều đoạn.

Người dùng có tệp `.m4a` dài 3 giờ 43 và **không có phần mềm cắt nào**. ffmpeg
thì app đã cần sẵn cho mọi việc khác, nên "phải cài thêm phần mềm" là câu trả
lời sai.
"""
from __future__ import annotations

import os
import subprocess

import pytest

from autodub.media import cat_tep


def _co_ffmpeg() -> bool:
    from autodub.ffmpeg_deps import co_ffmpeg
    return co_ffmpeg()


needs_ffmpeg = pytest.mark.skipif(not _co_ffmpeg(), reason="máy chưa có ffmpeg")


@pytest.fixture()
def tep_thu(tmp_path):
    """Một tệp âm thanh THẬT dài 310 giây."""
    ra = tmp_path / "thu.m4a"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=310", "-c:a", "aac", "-b:a", "48k",
         str(ra)], check=True, timeout=120)
    return str(ra)


# -- Chặn trước khi chạy -----------------------------------------------------

def test_tep_khong_ton_tai_thi_bao_ngay(tmp_path):
    with pytest.raises(FileNotFoundError):
        cat_tep.cat_deu(str(tmp_path / "khong-co.m4a"))


@pytest.mark.parametrize("phut", [0, -5, 999])
def test_do_dai_doan_vo_ly_bi_chan(tmp_path, phut):
    tep = tmp_path / "a.m4a"
    tep.write_bytes(b"x")
    with pytest.raises(ValueError, match="phút"):
        cat_tep.cat_deu(str(tep), phut=phut)


# -- Cắt thật ----------------------------------------------------------------

@needs_ffmpeg
def test_cat_dung_so_doan_va_KHONG_MAT_thoi_luong(tep_thu, tmp_path):
    """Tổng thời lượng các đoạn phải bằng tệp gốc — mất một giây là mất lời."""
    phan = cat_tep.cat_deu(tep_thu, str(tmp_path / "ra"), phut=2)
    assert len(phan) == 3, "310 giây chia 120 giây phải ra 3 đoạn"
    tong = sum(cat_tep.do_dai_giay(p) for p in phan)
    assert abs(tong - 310) < 2, f"tổng {tong:.1f}s, gốc 310s"


@needs_ffmpeg
def test_ten_tep_mang_MOC_BAT_DAU(tep_thu, tmp_path):
    """Sau khi cắt, mốc trong mỗi bản chép lời chạy lại từ 0. Không nói ra thì
    người đọc tưởng phút 5 của phần 3 là phút 5 của cả buổi."""
    phan = cat_tep.cat_deu(tep_thu, str(tmp_path / "ra"), phut=2)
    ten = [os.path.basename(p) for p in phan]
    assert "tu_00-00-00" in ten[0]
    assert "tu_00-02-00" in ten[1]
    assert "tu_00-04-00" in ten[2]


@needs_ffmpeg
def test_thu_tu_doan_dung_theo_thoi_gian(tep_thu, tmp_path):
    phan = cat_tep.cat_deu(tep_thu, str(tmp_path / "ra"), phut=2)
    assert phan == sorted(phan), "thứ tự trả về không theo thời gian"


@needs_ffmpeg
def test_tep_ngan_hon_mot_doan_thi_TRA_VE_CHINH_NO(tep_thu, tmp_path):
    """Cắt tệp 5 phút thành «một đoạn 5 phút» chỉ tạo thêm bản sao vô ích."""
    assert cat_tep.cat_deu(tep_thu, str(tmp_path / "ra"), phut=30) == [tep_thu]
    assert not os.path.exists(str(tmp_path / "ra" / "thu_phan_01.m4a"))


@needs_ffmpeg
def test_moi_doan_van_MO_DUOC(tep_thu, tmp_path):
    """Cắt xong mà tệp không phát được thì cắt để làm gì."""
    phan = cat_tep.cat_deu(tep_thu, str(tmp_path / "ra"), phut=2)
    for p in phan:
        assert cat_tep.do_dai_giay(p) > 0, f"{p} không đọc được độ dài"
        assert os.path.getsize(p) > 1000


# -- Không mã hoá lại --------------------------------------------------------

def test_CHEP_LUONG_khong_ma_hoa_lai():
    """Mã hoá lại tệp 3 giờ mất hàng chục phút để đổi lấy một tệp xấu hơn."""
    import inspect

    than = inspect.getsource(cat_tep.cat_deu)
    assert '"-c", "copy"' in than
    for cam in ("-b:a", "libx264", "aac"):
        assert cam not in than, f"đang mã hoá lại bằng «{cam}»"


def test_dat_lai_moc_thoi_gian_cho_tung_doan():
    """Thiếu cờ này thì đoạn 2 mang mốc của phút 30 và nhiều trình phát tưởng
    tệp hỏng."""
    import inspect

    assert '"-reset_timestamps", "1"' in inspect.getsource(cat_tep.cat_deu)


def test_giao_dien_chay_cat_trong_LUONG_NEN():
    """Cắt tệp vài GB trên ổ chậm vẫn có thể mất chục giây."""
    from tests.doc_ma import co_goi

    from autodub_gui.pages.transcribe_page import TranscribePage

    assert not co_goi(TranscribePage._cat_tep, "cat_deu"), \
        "đang cắt thẳng trên luồng giao diện"
    assert co_goi(TranscribePage._cat_tep, "CatTepWorker")
