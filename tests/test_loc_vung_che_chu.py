"""C63 — bộ quét chữ đề xuất che cả mặt người, và không ai cảnh báo trước.

Bằng chứng thật, lượt chạy 05-09 của chủ dự án trên một clip Douyin cảnh phố
đêm: "Quét chữ tự động" đề xuất ~15 vùng — biển hiệu neon, chữ trên tường, và
cả mặt diễn viên. Bật "Xoá chữ thay vì làm mờ" rồi xuất ra thì **nguyên mảng
người bị kéo nhoè**, xấu hơn hẳn mấy dòng chữ gốc. Còn watermark góc trên phải
— thứ đáng xoá nhất — thì vẫn còn nguyên.

Hai chỗ hỏng, hai cách chữa:

1. Bộ quét không phân biệt **chữ nằm lì** (watermark, phụ đề cháy) với **chữ
   trôi qua** (biển hiệu bên đường). Dấu hiệu rẻ mà đủ: nằm lì thì khung nào
   cũng thấy ở CÙNG vị trí nên được gộp; trôi qua thì mỗi khung một chỗ.
2. `delogo` nội suy từ viền nên vùng rộng chắc chắn ra vệt — phải nói TRƯỚC,
   không để người dùng chờ xuất xong mới biết.
"""
from __future__ import annotations

import pytest

from autodub.media.subtitle import vung_qua_rong_cho_xoa
from autodub.media.text_regions import loc_theo_lap_lai, merge_regions


def _box(x, y, w=0.2, h=0.05, anh=0, conf=0.9):
    return {"x": x, "y": y, "w": w, "h": h, "confidence": conf, "anh": anh}


# ------------------------------- 1. nằm lì vs trôi qua ---

def test_watermark_nam_li_thi_giu(tmp_path):
    """Watermark góc trên phải: khung nào cũng ở đúng chỗ đó."""
    boxes = [_box(0.80, 0.03, anh=i) for i in range(5)]
    giu, bo = loc_theo_lap_lai(merge_regions(boxes), so_khung=5)
    assert len(giu) == 1 and bo == 0


def test_bien_hieu_troi_qua_thi_bo():
    """Cảnh phố đêm: mỗi khung thấy một biển hiệu ở một chỗ khác nhau."""
    boxes = [_box(0.1 + 0.15 * i, 0.2 + 0.1 * i, anh=i) for i in range(5)]
    giu, bo = loc_theo_lap_lai(merge_regions(boxes), so_khung=5)
    assert giu == [] and bo == 5


def test_ca_hai_lan_lon_thi_chi_giu_cai_nam_li():
    """Đúng cảnh trong ảnh chụp: một watermark + một đống biển hiệu trôi."""
    boxes = [_box(0.80, 0.03, anh=i) for i in range(5)]           # watermark
    boxes += [_box(0.1 + 0.15 * i, 0.5, anh=i) for i in range(5)]  # biển hiệu
    giu, bo = loc_theo_lap_lai(merge_regions(boxes), so_khung=5)
    assert len(giu) == 1, "không giữ đúng watermark"
    assert giu[0]["x"] == pytest.approx(0.80, abs=0.02)
    assert bo == 5


def test_phu_de_chay_doi_chu_nhung_cung_cho_thi_van_giu():
    """Phụ đề cháy: chữ đổi mỗi câu nhưng LUÔN nằm ở dải dưới cùng — vẫn phải
    coi là nằm lì. Đây là ca dễ lọc nhầm nhất."""
    boxes = [_box(0.15, 0.86, w=0.7, h=0.07, anh=i) for i in range(4)]
    giu, bo = loc_theo_lap_lai(merge_regions(boxes), so_khung=4)
    assert len(giu) == 1 and bo == 0


def test_quet_duoi_hai_khung_thi_KHONG_loc():
    """Một khung thì không có gì để so — lọc lúc đó là đoán bừa, và sẽ xoá sạch
    mọi đề xuất."""
    boxes = [_box(0.1, 0.2, anh=0), _box(0.6, 0.7, anh=0)]
    giu, bo = loc_theo_lap_lai(merge_regions(boxes), so_khung=1)
    assert len(giu) == 2 and bo == 0


def test_bo_dem_dung_so_vung_da_bo():
    """Số bỏ đi phải chính xác — giao diện in con số này cho người dùng."""
    boxes = [_box(0.80, 0.03, anh=i) for i in range(3)]
    boxes += [_box(0.1, 0.5, anh=0), _box(0.4, 0.6, anh=1)]
    giu, bo = loc_theo_lap_lai(merge_regions(boxes), so_khung=3)
    assert len(giu) == 1 and bo == 2


# ------------------------------- 2. cảnh báo vùng rộng ---

def test_dai_chu_mong_KHONG_bi_canh_bao():
    """Đúng ca `delogo` làm tốt: dải chữ mỏng ngang màn hình. Cảnh báo ở đây là
    kêu nhầm, mà bộ canh hay kêu nhầm thì bị tắt đi (V90)."""
    assert vung_qua_rong_cho_xoa([{"x": 0.1, "y": 0.86, "w": 0.5, "h": 0.06}]) == []


def test_vung_trum_ca_nguoi_bi_canh_bao():
    """Đúng vùng đã làm hỏng khung hình trong lượt chạy 05-09."""
    rong = vung_qua_rong_cho_xoa([{"x": 0.2, "y": 0.2, "w": 0.35, "h": 0.5}])
    assert len(rong) == 1


def test_vung_qua_ngang_bi_canh_bao():
    assert vung_qua_rong_cho_xoa([{"x": 0.05, "y": 0.5, "w": 0.9, "h": 0.05}])


def test_nhieu_vung_thi_dem_dung_so_vung_dang_lo():
    vung = [
        {"x": 0.1, "y": 0.86, "w": 0.4, "h": 0.05},   # ổn
        {"x": 0.2, "y": 0.2, "w": 0.4, "h": 0.4},     # rộng
        {"x": 0.0, "y": 0.0, "w": 0.9, "h": 0.1},     # quá ngang
    ]
    assert len(vung_qua_rong_cho_xoa(vung)) == 2


def test_du_lieu_hong_khong_lam_do_ca_luot():
    """Vùng vẽ tay có thể thiếu trường hoặc sai kiểu — cảnh báo hỏng thì thôi,
    không được kéo đổ cả lượt xuất video."""
    assert vung_qua_rong_cho_xoa([{"x": 0.1}, {"w": "abc", "h": None}, {}]) == []
    assert vung_qua_rong_cho_xoa([]) == []
    assert vung_qua_rong_cho_xoa(None) == []


# ------------------------------- 3. cắm vào giao diện ---

def test_giao_dien_canh_bao_khi_bat_xoa_chu():
    """Viết ra phép kiểm mà không ai gọi thì nó chỉ là một hàm nằm im."""
    pytest.importorskip("PySide6")
    import inspect

    from autodub_gui import style_dialog

    ma = inspect.getsource(style_dialog.StyleDialog)
    assert "_canh_bao_vung_rong" in ma
    assert "vung_qua_rong_cho_xoa" in ma


def test_giao_dien_noi_ra_so_vung_da_bo():
    """Lọc âm thầm thì người dùng không hiểu vì sao chữ họ NHÌN THẤY trên hình
    lại không được đề xuất che."""
    pytest.importorskip("PySide6")
    import inspect

    from autodub_gui import style_dialog

    ma = inspect.getsource(style_dialog.StyleDialog)
    assert "so_vung_da_bo" in ma
    assert "chỉ thấy ở một khung" in ma


def test_giao_dien_goi_dung_ten_nut_xoa():
    """Thông báo từng nhắc nút "Xoá hết" trong khi nút thật tên "Xoá tất cả"."""
    pytest.importorskip("PySide6")
    import inspect

    from autodub_gui import style_dialog

    ma = inspect.getsource(style_dialog.StyleDialog)
    assert "Xoá hết" not in ma, "vẫn còn tên nút không tồn tại"
    assert "Xoá tất cả" in ma
