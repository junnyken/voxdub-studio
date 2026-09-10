"""Ghép ảnh với thời lượng RIÊNG từng ảnh — mini-spec H4b.

Vì sao cần: `dung_video()` vốn chia ĐỀU thời lượng cho mọi ảnh. Video dựng từ
kịch bản thì mỗi cảnh phải giữ hình đúng bằng thời gian đọc lời của nó — đoạn
hook hai câu ngắn và đoạn bằng chứng bốn câu dài mà giữ bằng nhau thì hoặc
hụt tiếng hoặc thừa hình.

Chỗ dễ sai âm thầm nhất là **mốc chuyển cảnh**: sai công thức thì video vẫn
dựng ra bình thường, chỉ là hình lệch dần so với tiếng về cuối — không có lỗi
nào để mà thấy.
"""
from __future__ import annotations

import pytest

from autodub import product_video as pv


def _moc_xfade(lenh: list[str]) -> list[float]:
    """Rút các `offset=` trong chuỗi filter ra để kiểm."""
    i = lenh.index("-filter_complex")
    return [float(p.split("offset=")[1].split("[")[0])
            for p in lenh[i + 1].split(";") if "offset=" in p]


def _thoi_luong_dau_vao(lenh: list[str]) -> list[float]:
    return [float(lenh[i + 1]) for i, x in enumerate(lenh) if x == "-t"]


# ------------------------------------------------- tương thích đường cũ ----

def test_mot_so_duy_nhat_van_chay_nhu_cu():
    lenh = pv._lenh_ghep(["a.png", "b.png", "c.png"], "ra.mp4", 3.0, 0.5)
    assert _thoi_luong_dau_vao(lenh) == [3.0, 3.0, 3.0]


def test_moc_chuyen_canh_khop_cong_thuc_cu_khi_deu_nhau():
    # Bản cũ dùng `(giay - chuyen) * i`. Công thức mới cộng dồn phải rút gọn
    # đúng về đó, nếu không là đã âm thầm đổi hành vi của ảnh sản phẩm C1.
    giay, chuyen = 3.0, 0.5
    lenh = pv._lenh_ghep(["a.png", "b.png", "c.png"], "ra.mp4", giay, chuyen)
    assert _moc_xfade(lenh) == pytest.approx(
        [(giay - chuyen) * 1, (giay - chuyen) * 2])


# --------------------------------------------------- thời lượng riêng -----

def test_moi_anh_mot_thoi_luong_rieng():
    lenh = pv._lenh_ghep(["a.png", "b.png", "c.png"], "ra.mp4",
                         [2.0, 7.5, 4.25], 0.5)
    assert _thoi_luong_dau_vao(lenh) == [2.0, 7.5, 4.25]


def test_moc_chuyen_canh_cong_don_theo_thoi_luong_THAT():
    # Đây là chỗ sai thì không ai thấy: video vẫn ra, chỉ lệch dần.
    giay = [2.0, 7.5, 4.25]
    chuyen = 0.5
    lenh = pv._lenh_ghep(["a.png", "b.png", "c.png"], "ra.mp4", giay, chuyen)
    assert _moc_xfade(lenh) == pytest.approx([
        sum(giay[:1]) - chuyen * 1,
        sum(giay[:2]) - chuyen * 2,
    ])


def test_nhan_video_hien_dung_bang_thoi_luong_anh_DAU():
    # Nhãn bật theo `lte(t, ...)`; dùng nhầm thời lượng chung sẽ làm nhãn
    # kéo dài sang cảnh sau hoặc tắt sớm.
    lenh = pv._lenh_ghep(["a.png", "b.png"], "ra.mp4", [2.0, 9.0], 0.5)
    i = lenh.index("-filter_complex")
    assert "lte(t,2.000)" in lenh[i + 1]


def test_khong_chuyen_canh_thi_khong_dung_moc():
    lenh = pv._lenh_ghep(["a.png", "b.png"], "ra.mp4", [2.0, 9.0], 0.5,
                         kieu_chuyen="khong")
    assert _moc_xfade(lenh) == []
    assert _thoi_luong_dau_vao(lenh) == [2.0, 9.0]


# ------------------------------------------------------------ chặn sai ----

def test_so_thoi_luong_lech_so_anh_thi_NEM_LOI():
    # Lệch một cái là mọi cảnh phía sau gán sai thời gian mà không dấu hiệu.
    with pytest.raises(ValueError, match="lệch nhau"):
        pv._lenh_ghep(["a.png", "b.png", "c.png"], "ra.mp4", [2.0, 3.0], 0.5)


def test_thoi_luong_khong_duong_thi_NEM_LOI():
    for xau in ([0.0, 3.0], [-1.0, 3.0]):
        with pytest.raises(ValueError, match="lớn hơn 0"):
            pv._lenh_ghep(["a.png", "b.png"], "ra.mp4", xau, 0.5)


def test_kieu_chuyen_la_van_nem_loi_nhu_cu():
    with pytest.raises(ValueError, match="kiểu chuyển cảnh"):
        pv._lenh_ghep(["a.png"], "ra.mp4", [2.0], 0.5, kieu_chuyen="khong_co_that")


# --------------------------------------------- nối với storyboard H4a -----

def test_thoi_luong_lay_thang_tu_storyboard_dung_thu_tu():
    from autodub import storyboard as sb

    kb = {"status": "ready", "beats": [
        {"beatType": "hook", "voiceoverTextVi": "Thử đi."},
        {"beatType": "proof", "voiceoverTextVi":
            "Cả nhà bốn người có bữa sáng nóng hổi, còn mẹ thì thảnh thơi "
            "pha ly cà phê uống trọn vẹn."},
    ]}
    board = sb.dung_storyboard(kb)
    giay = [d.giay for d in board.doan]
    lenh = pv._lenh_ghep(["a.png", "b.png"], "ra.mp4", giay, 0.3)

    vao = _thoi_luong_dau_vao(lenh)
    assert vao == pytest.approx(giay)
    assert vao[1] > vao[0] * 3, "đoạn dài phải giữ hình lâu hơn hẳn đoạn ngắn"
