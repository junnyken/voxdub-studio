"""Tiếng Việt trong danh sách "Ngôn ngữ trong video" (22/8/2026).

Người dùng thật hỏi: *"ở đây tôi không thấy có tiếng Việt, và có cần cài thêm
nhận diện giọng tiếng Việt không"*.

Trả lời: **không cần cài gì thêm.** Whisper nghe được tiếng Việt sẵn
(Paraformer mới là bộ riêng, và nó chỉ dành cho tiếng Trung), còn bộ dịch
ngoại tuyến đã biết `vi-VN` từ trước. Thiếu chỉ là thiếu một dòng trong danh
sách chọn.

Nhưng mở nguồn tiếng Việt thì đẻ ra một ca mới: nguồn tiếng Việt + đích tiếng
Việt. Dịch tiếng Việt sang tiếng Việt là trả tiền cho một lượt gọi mô hình để
nhận lại gần đúng câu cũ.
"""
from __future__ import annotations

from autodub_gui import dub_constants as consts


def test_tieng_viet_co_trong_danh_sach_nguon():
    ma = [key for _nhan, key in consts.SOURCE_LANGS]
    assert "vi-VN" in ma


def test_nhan_hien_thi_doc_duoc():
    nhan = dict((k, n) for n, k in consts.SOURCE_LANGS)["vi-VN"]
    assert "Tiếng Việt" in nhan


def test_bo_dich_ngoai_tuyen_da_biet_tieng_viet():
    """Thêm vào danh sách mà bộ dịch không biết mã đó là mở một đường hỏng."""
    from autodub.text.translate_local import LANG_TO_FLORES  # noqa: PLC0415

    assert LANG_TO_FLORES.get("vi-VN") == "vie_Latn"


def test_paraformer_van_chi_danh_cho_tieng_trung():
    """Chọn tiếng Việt kèm Paraformer phải vẫn cảnh báo như cũ."""
    assert consts.paraformer_language_mismatch("paraformer", "vi-VN")
    assert not consts.paraformer_language_mismatch("whisper", "vi-VN")


# -- Nguồn trùng đích --------------------------------------------------------

def test_viet_sang_viet_bi_coi_la_trung():
    assert consts.cung_ngon_ngu("vi-VN", "vi")


def test_cac_cap_trung_khac_cung_bat_duoc():
    assert consts.cung_ngon_ngu("en-US", "en")
    assert consts.cung_ngon_ngu("ja-JP", "ja")
    # Ba biến thể tiếng Trung đều quy về một đích
    for ma in ("zh-CN", "zh-HK", "zh-TW"):
        assert consts.cung_ngon_ngu(ma, "zh"), ma


def test_cap_khac_ngon_ngu_thi_khong_chan():
    assert not consts.cung_ngon_ngu("vi-VN", "en")
    assert not consts.cung_ngon_ngu("zh-CN", "vi")


def test_tu_nhan_dang_thi_khong_ket_luan_duoc():
    """Bỏ trống ngôn ngữ nguồn = để máy tự nghe; chưa biết thì đừng chặn."""
    assert not consts.cung_ngon_ngu("", "vi")


def test_moi_ma_nguon_deu_co_trong_bang_dich():
    """Bộ canh chung: thêm ngôn ngữ nguồn mà quên bảng dịch là hỏng lúc chạy."""
    from autodub.text.translate_local import LANG_TO_FLORES

    thieu = [key for _n, key in consts.SOURCE_LANGS if key not in LANG_TO_FLORES]
    assert thieu == [], f"nguồn {thieu} không có mã dịch tương ứng"
