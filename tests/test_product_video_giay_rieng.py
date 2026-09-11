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


def _tong_video(lenh: list[str]) -> float:
    """Thời lượng video ffmpeg sẽ dựng ra, suy từ chính lệnh.

    `xfade` chồng cảnh nên tổng = mốc cuối + độ dài ảnh cuối. Đây mới là con
    số phải khớp dòng thời gian của transcript — độ dài đưa vào từng ảnh chỉ
    là phương tiện, không phải hợp đồng.
    """
    vao = _thoi_luong_dau_vao(lenh)
    moc = _moc_xfade(lenh)
    return vao[0] if not moc else moc[-1] + vao[-1]


# ------------------------------------------------- tương thích đường cũ ----

def test_mot_so_duy_nhat_van_chay_nhu_cu():
    """Một con số = mọi ảnh giữ hình 3,0 giây, tổng video 9,0 giây.

    Độ dài ĐƯA VÀO ffmpeg lớn hơn 3,0 vì mỗi lần chuyển cảnh chồng lấn ăn
    mất 0,5 giây — phần bù đó là chi tiết bên trong, thứ phải đúng là TỔNG
    (mini-spec H4c-1).
    """
    lenh = pv._lenh_ghep(["a.png", "b.png", "c.png"], "ra.mp4", 3.0, 0.5)
    assert _tong_video(lenh) == pytest.approx(9.0)
    assert _thoi_luong_dau_vao(lenh) == [3.5, 3.5, 3.0]


def test_moc_chuyen_canh_dat_dung_RANH_GIOI_doan():
    """Mốc chuyển cảnh = tổng thời lượng các đoạn TRƯỚC nó.

    Bản trước H4c-1 dùng `(giay - chuyen) * i`, tức trừ phần chồng lấn mà
    không bù lại ở đâu. Hệ quả: video ngắn hơn `chuyen × (n-1)` VÀ mọi đoạn
    bị đẩy lên sớm dần — đo thật ba ảnh [2;1;3] ra 5,40s thay vì 6,00s.
    """
    giay, chuyen = 3.0, 0.5
    lenh = pv._lenh_ghep(["a.png", "b.png", "c.png"], "ra.mp4", giay, chuyen)
    assert _moc_xfade(lenh) == pytest.approx([3.0, 6.0])


# --------------------------------------------------- thời lượng riêng -----

def test_moi_anh_mot_thoi_luong_rieng():
    giay = [2.0, 7.5, 4.25]
    lenh = pv._lenh_ghep(["a.png", "b.png", "c.png"], "ra.mp4", giay, 0.5)
    # Mỗi ảnh trừ ảnh CUỐI được cộng thêm phần chuyển cảnh sẽ bị chồng mất.
    assert _thoi_luong_dau_vao(lenh) == [2.5, 8.0, 4.25]
    assert _tong_video(lenh) == pytest.approx(sum(giay))


def test_moc_chuyen_canh_cong_don_theo_thoi_luong_THAT():
    # Đây là chỗ sai thì không ai thấy: video vẫn ra, chỉ lệch dần.
    giay = [2.0, 7.5, 4.25]
    lenh = pv._lenh_ghep(["a.png", "b.png", "c.png"], "ra.mp4", giay, 0.5)
    assert _moc_xfade(lenh) == pytest.approx([sum(giay[:1]), sum(giay[:2])])


@pytest.mark.parametrize("giay,chuyen", [
    ([2.0, 1.0, 3.0], 0.3), ([1.0] * 5, 0.3), ([4.0, 4.0], 0.5),
    ([3.0], 0.3), ([8.4, 5.2, 11.9, 3.1, 6.6], 0.3),
])
def test_TONG_video_luon_bang_tong_thoi_luong_doan(giay, chuyen):
    """Hợp đồng của H4c-1, viết thành một dòng.

    Đây là thứ transcript dựa vào; sai ở đây thì mọi bước sau đặt lên một
    dòng thời gian sai mà không có lỗi nào để thấy.
    """
    lenh = pv._lenh_ghep(["a.png"] * len(giay), "ra.mp4", giay, chuyen)
    assert _tong_video(lenh) == pytest.approx(sum(giay))


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
    assert _tong_video(lenh) == pytest.approx(sum(giay))
    assert vao[1] > vao[0] * 3, "đoạn dài phải giữ hình lâu hơn hẳn đoạn ngắn"
