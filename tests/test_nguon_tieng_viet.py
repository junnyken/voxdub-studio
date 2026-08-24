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


# -- Chốt "nguồn trùng đích" phải có ở MỌI đường vào (mini-spec C22) ---------
#
# Chốt này thêm ngày 22/8 nhưng chỉ ở trang Tạo dự án. Xử lý hàng loạt và
# `voxdub dub` vẫn nhận nguồn trùng đích — và trả tiền cho một lượt gọi mô
# hình mỗi video để nhận lại gần đúng câu cũ.

def test_phep_so_nam_o_LOI_de_dong_lenh_dung_duoc():
    """Dòng lệnh không được nhập gói giao diện, nên phép so phải ở lõi."""
    from autodub.languages import cung_ngon_ngu as o_loi
    from autodub_gui.dub_constants import cung_ngon_ngu as o_gui

    assert o_loi is o_gui, "gói giao diện đang giữ một bản chép riêng"


def test_khong_con_bang_chep_tay_trong_goi_giao_dien():
    import io

    s = io.open("autodub_gui/dub_constants.py", encoding="utf-8").read()
    assert "_NGUON_SANG_DICH = {" not in s, \
        "hai bản chép là có ngày lệch nhau"


def test_tu_nhan_dang_thi_khong_ket_luan(monkeypatch):
    """Chặn oan còn tệ hơn không chặn."""
    from autodub.languages import cung_ngon_ngu

    assert cung_ngon_ngu("auto", "vi") is False
    assert cung_ngon_ngu("", "vi") is False


def test_dong_lenh_chan_nguon_trung_dich():
    """`voxdub dub --source-lang vi-VN --target vi` phải bị chặn."""
    from tests.doc_ma import co_goi
    from autodub.cli import _cmd_dub

    assert co_goi(_cmd_dub, "cung_ngon_ngu"), "dòng lệnh chưa có chốt"


def test_dong_lenh_chan_TRUOC_khi_tai_video():
    """Tải xong mới báo là đã tốn băng thông và thời gian của người dùng."""
    from tests.doc_ma import cac_luot_goi
    from autodub.cli import _cmd_dub

    goi = cac_luot_goi(_cmd_dub)
    assert "cung_ngon_ngu" in goi
    # Mọi lượt gọi liên quan tới tải/chạy pipeline phải đứng SAU.
    i = goi.index("cung_ngon_ngu")
    sau = goi[i:]
    for ten in ("run", "DubPipeline"):
        if ten in goi:
            assert ten in sau, f"«{ten}» chạy trước khi kiểm ngôn ngữ"


def test_xu_ly_hang_loat_chan_o_MOT_cho_duy_nhat():
    """Chặn ở nơi gọi thì thêm đường vào thứ ba là sót."""
    from tests.doc_ma import co_goi
    from autodub_gui.pages.batch_page import BatchPage

    assert co_goi(BatchPage._launch, "_chan_cung_ngon_ngu"), \
        "đường chạy mẻ chưa có chốt"
    # Hai đường vào đều đi qua `_launch`, nên KHÔNG cần chặn riêng ở chúng.
    for ham in (BatchPage._start_all, BatchPage._run_single):
        assert co_goi(ham, "_launch")


def test_xu_ly_hang_loat_chan_ca_duong_len_may_chu():
    """Đường đẩy lên máy chủ cũng phải bị chặn — nó tốn tiền hơn."""
    from tests.doc_ma import goi_truoc
    from autodub_gui.pages.batch_page import BatchPage

    assert goi_truoc(BatchPage._launch, "_chan_cung_ngon_ngu", "_launch_cloud")
