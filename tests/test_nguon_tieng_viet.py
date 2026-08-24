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


# -- Cùng ngôn ngữ = BỎ KHÂU DỊCH, không phải chặn (mini-spec C23) ----------
#
# C22 chặn cả ba đường vào. Chặn thì đúng về tiền nhưng bỏ mất một việc người
# dùng thật sự cần: đổi giọng cho video tiếng Việt sẵn có. C23 đổi thành bỏ
# hẳn khâu dịch — vừa làm được việc, vừa không tốn một đồng nào cho phần dịch.

def test_phep_so_nam_o_LOI_de_dong_lenh_dung_duoc():
    """Dòng lệnh không được nhập gói giao diện, nên phép so phải ở lõi."""
    from autodub.languages import cung_ngon_ngu as o_loi
    from autodub_gui.dub_constants import cung_ngon_ngu as o_gui

    assert o_loi is o_gui, "gói giao diện đang giữ một bản chép riêng"


def test_khong_con_bang_chep_tay_trong_goi_giao_dien():
    import io

    s = io.open("autodub_gui/dub_constants.py", encoding="utf-8").read()
    assert "_NGUON_SANG_DICH = {" not in s, "hai bản chép là có ngày lệch nhau"


def test_tu_nhan_dang_thi_khong_ket_luan():
    """Chặn oan còn tệ hơn không chặn."""
    from autodub.languages import cung_ngon_ngu

    assert cung_ngon_ngu("auto", "vi") is False
    assert cung_ngon_ngu("", "vi") is False


def test_duong_ong_BO_KHAU_DICH_khi_cung_ngon_ngu():
    from tests.doc_ma import co_goi
    from autodub.pipeline import DubPipeline

    # `run()` chỉ là lớp vỏ bọc lỗi; việc thật nằm ở `_run_impl`.
    assert co_goi(DubPipeline._run_impl, "cung_ngon_ngu"), \
        "đường ống không hề biết tới ca cùng ngôn ngữ"
    # Và phải hỏi TRƯỚC khi giữ tiền, không phải sau.
    from tests.doc_ma import goi_truoc

    assert goi_truoc(DubPipeline._run_impl, "cung_ngon_ngu", "_setup_hold"), \
        "giữ tiền xong mới biết là không cần dịch thì đã giữ thừa"


def test_KHONG_giu_cho_tien_dich_khi_khong_dich():
    """Giữ chỗ rồi không dùng nghĩa là người dùng bị chặn vì «không đủ Vox»
    cho một việc không hề tốn Vox — với video dài đó là hàng chục nghìn Vox."""
    import io

    s = io.open("autodub/billing.py", encoding="utf-8").read()
    assert "and not khong_can_dich" in s, \
        "cờ không đi vào auto_translate của lệnh giữ tiền"


def test_cau_dich_chinh_la_cau_goc():
    """Bỏ khâu dịch mà quên gán câu thì các bước sau nhận chuỗi rỗng."""
    import io

    s = io.open("autodub/pipeline.py", encoding="utf-8").read()
    assert 'seg[target.text_field] = seg.get("text", "")' in s


def test_KHONG_con_chan_o_bat_ky_duong_vao_nao():
    """Chặn là bỏ mất việc đổi giọng — ca có thật."""
    import io

    from tests.doc_ma import cay_ham
    import ast
    from autodub_gui.pages.batch_page import BatchPage

    # `_chan_cung_ngon_ngu` phải luôn trả về False (chỉ thông báo).
    tra_ve = [n for n in ast.walk(cay_ham(BatchPage._chan_cung_ngon_ngu))
              if isinstance(n, ast.Return)]
    assert tra_ve, "hàm không trả về gì"
    assert all(isinstance(n.value, ast.Constant) and n.value.value is False
               for n in tra_ve), "vẫn còn đường chặn cả mẻ"

    s = io.open("autodub/cli.py", encoding="utf-8").read()
    i = s.index("if cung_ngon_ngu(args.source_lang")
    assert "CliArgError" not in s[i:i + 400], "dòng lệnh vẫn chặn"


def test_van_noi_cho_nguoi_dung_biet():
    """Im lặng cũng không được: người chọn Tiếng Việt vì tưởng phải khai đúng
    ngôn ngữ video, chứ không biết mình vừa chọn một luồng khác."""
    import io

    for tep, chu in [("autodub_gui/pages/batch_page.py", "TOASTS.info"),
                     ("autodub_gui/pages/new_project_page.py", "TOASTS.info"),
                     ("autodub/cli.py", "bỏ qua khâu dịch")]:
        s = io.open(tep, encoding="utf-8").read()
        assert chu in s, f"{tep} không nói gì với người dùng"
