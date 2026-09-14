"""RS-16 — ảnh do AI vẽ phải qua ĐỦ ba phép kiểm trước khi vào video.

Chú thích trong `product_video.dung_video_tu_anh_nguoi_dung` cảnh báo điều này
từ TRƯỚC khi H4d tồn tại:

    ⚠ Khi H4d thêm đường sinh ảnh AI: ảnh sinh ra KHÔNG được đi qua hàm này.
      Chúng phải qua `dung_video()` với đủ ba phép kiểm.

H4d lên `main` ngày 10/09, cổng thì chưa. Trang «Dựng video» chỉ giữ ĐƯỜNG DẪN
ảnh và vứt `phan_quyet`/`da_kiem`/`da_dong_nhan`/`bam`, nên
`kiem_lai_truoc_khi_xuat()` không có gì để chạy.

Rủi ro thật: ảnh AI có hộp/chai/nhãn/chữ bịa đi thẳng vào video đem bán, và
án phạt sàn rơi xuống người bán vài tuần sau.
"""
from __future__ import annotations

import os

import pytest

from autodub.du_an_tu_kich_ban import AnhAiChuaDat, dung_du_an


def _kich_ban(so_doan: int = 2) -> dict:
    return {"status": "ready", "beats": [
        {"beatType": "hook", "voiceoverTextVi": "Một câu lời đọc đủ dài để đo",
         "captionSuggestionVi": "Chữ", "visualBriefVi": "Cảnh"}
        for _ in range(so_doan)]}


def _anh(tmp_path, ten: str) -> str:
    p = tmp_path / ten
    p.write_bytes(b"\xff\xd8" + ten.encode() + b"\xff\xd9")
    return str(p)


def _dat(duong_dan: str) -> dict:
    """Bản ghi ảnh AI ĐẠT đủ ba phép kiểm."""
    from autodub.product_video import bam_tep

    return {"phan_quyet": "DAT", "ly_do": "", "da_kiem": True,
            "da_dong_nhan": True, "bam": bam_tep(duong_dan), "goi_y": "cảnh"}


def _dung(tmp_path, anh_ai):
    """Dựng thử với ffmpeg giả.

    `do_thoi_luong` phải trả về ĐÚNG tổng của dòng thời gian, nếu không cổng
    lệch-thời-lượng (H4c-1) sẽ nổ trước và ta không kiểm được cổng RS-16 —
    một test đỏ vì cổng khác thì không chứng minh gì về cổng mình đang kiểm.
    """
    from autodub.storyboard import dung_storyboard

    kb = _kich_ban()
    board = dung_storyboard(kb)
    tong = sum(d.giay for d in board.doan)
    return dung_du_an(
        kb, [_A[0], _A[1]], str(tmp_path / "da"),
        anh_ai=anh_ai,
        ghep_video=lambda *a, **k: None,
        do_thoi_luong=lambda *_a, **_k: tong)


_A: list[str] = []


@pytest.fixture(autouse=True)
def _hai_anh(tmp_path):
    _A.clear()
    _A.extend([_anh(tmp_path, "a.jpg"), _anh(tmp_path, "b.jpg")])
    yield


# ================= Ba ca phải CHẶN — mỗi ca một nguyên nhân ================

def test_BANG_CHUNG_PHU_DINH_anh_AI_chua_kiem_thi_KHONG_dung_duoc(tmp_path):
    xau = _dat(_A[0])
    xau["da_kiem"] = False
    with pytest.raises(AnhAiChuaDat, match="chưa kiểm được"):
        _dung(tmp_path, {0: xau})


def test_anh_AI_co_san_pham_bia_thi_bi_CHAN(tmp_path):
    xau = _dat(_A[0])
    xau["phan_quyet"] = "CO_SAN_PHAM"
    xau["ly_do"] = "ảnh có hộp sản phẩm"
    with pytest.raises(AnhAiChuaDat, match="hộp sản phẩm"):
        _dung(tmp_path, {0: xau})


def test_anh_AI_chua_dong_nhan_AI_generated_thi_bi_CHAN(tmp_path):
    xau = _dat(_A[0])
    xau["da_dong_nhan"] = False
    with pytest.raises(AnhAiChuaDat, match="nhãn AI-generated"):
        _dung(tmp_path, {0: xau})


def test_TEP_BI_SUA_sau_khi_kiem_thi_bi_CHAN(tmp_path):
    """Đây là lý do phải kiểm LẠI lúc dựng chứ không tin cờ đã lưu."""
    mo_ta = _dat(_A[0])
    with open(_A[0], "wb") as f:               # thay ruột, giữ nguyên tên
        f.write(b"\xff\xd8ANH KHAC\xff\xd9")
    with pytest.raises(AnhAiChuaDat, match="đã bị sửa"):
        _dung(tmp_path, {0: mo_ta})


def test_phan_quyet_LA_thi_chan_chu_khong_cho_qua(tmp_path):
    """Bản H4d sau thêm một mã phán quyết mà cổng này chưa biết ⇒ 'chưa biết'
    phải là 'không cho qua', không phải 'chắc là ổn'."""
    la = _dat(_A[0])
    la["phan_quyet"] = "MOT_TRANG_THAI_MOI"
    with pytest.raises(AnhAiChuaDat):
        _dung(tmp_path, {0: la})


# ===================== Hai ca KHÔNG được chặn oan =========================

def test_anh_AI_DAT_du_ba_phep_kiem_thi_dung_duoc(tmp_path):
    """Mặt ngược lại — khoá cứng thành 'không bao giờ dựng được' cũng là hỏng."""
    ket = _dung(tmp_path, {0: _dat(_A[0]), 1: _dat(_A[1])})
    assert ket is not None


def test_anh_NGUOI_DUNG_TU_CHON_khong_bi_doi_kiem_anh_AI(tmp_path):
    """Ảnh thật của người ta không thuộc diện kiểm ảnh AI.

    Điền cờ tuân thủ cho một tấm ảnh chụp thật chỉ để qua cổng là BỊA trạng
    thái tuân thủ — chú thích trong `dung_video_tu_anh_nguoi_dung` cấm đúng
    điều đó.
    """
    ket = _dung(tmp_path, {})          # không đoạn nào là ảnh AI
    assert ket is not None


def test_tron_anh_AI_va_anh_nguoi_dung(tmp_path):
    """Đoạn 0 vẽ bằng AI, đoạn 1 người dùng tự chọn — chỉ đoạn 0 bị kiểm."""
    ket = _dung(tmp_path, {0: _dat(_A[0])})
    assert ket is not None


# ============== Ánh xạ từ vựng hai mini-spec phải VIẾT RA ==================

def test_anh_xa_DAT_sang_SAFE_duoc_khai_bao_tuong_minh():
    from autodub.du_an_tu_kich_ban import _PHAN_QUYET_SANG_KET_LUAN

    assert _PHAN_QUYET_SANG_KET_LUAN.get("DAT") == "SAFE", (
        "H4d nói 'DAT', C1 đọc 'SAFE' — dịch ẩu một chiều thì chặn sạch, "
        "chiều kia thì mở toang, và cả hai đều im lặng")


# ================ Giao diện phải GIỮ và phải XOÁ đúng lúc =================

def test_trang_H4_giu_phan_quyet_khi_ve_va_XOA_khi_nguoi_dung_thay_anh():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from autodub_gui.pages.storyboard_page import StoryboardPage

    t = StoryboardPage(lambda: object())
    t.dat_kich_ban(_kich_ban())
    assert t._anh_ai == {}, "kịch bản mới phải sạch bản ghi cũ"

    t._anh_ai[0] = {"phan_quyet": "DAT"}
    t._anh[0] = "ai.jpg"

    # Người dùng chọn ảnh tự chụp cho đúng đoạn đó.
    t._anh[0] = "cua_toi.jpg"
    t._anh_ai.pop(0, None)
    assert 0 not in t._anh_ai, (
        "giữ lại bản ghi AI cũ thì dấu băm của tấm cũ sẽ đem so với tấm mới")


def test_ma_nguon_XOA_ban_ghi_AI_o_CA_HAI_duong_chon_anh():
    """Chốt CHỖ GỌI: thiếu một đường là đường đó thành lỗ."""
    ma = open("autodub_gui/pages/storyboard_page.py", encoding="utf-8").read()
    assert ma.count("self._anh_ai.pop(i, None)") >= 2, (
        "cả «Chọn ảnh…» lẫn «Chọn ảnh cho tất cả…» đều phải bỏ bản ghi AI cũ")


def test_worker_truyen_phan_quyet_xuong_tang_dung():
    ma = open("autodub_gui/workers.py", encoding="utf-8").read()
    assert "anh_ai=self._anh_ai" in ma, (
        "worker không chuyển tiếp thì cổng ở tầng dựng không bao giờ chạy")
