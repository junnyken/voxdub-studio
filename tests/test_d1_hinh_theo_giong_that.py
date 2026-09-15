"""D1 — hình chạy theo GIỌNG ĐỌC THẬT, không theo ước lượng.

`dung_du_an()` dựng slideshow theo ƯỚC LƯỢNG thời gian đọc. Giọng thật lệch
~5% (pilot H4 đo: 19,30s so với 20,31s), và vì các đoạn kịch bản NỐI LIỀN
NHAU — không có khoảng lặng nào để dồn trễ — phần lệch ấy **cộng dồn**: càng
về cuối hình càng chạy trước lời.

Engine vốn xử lý bằng cách NÉN GIỌNG cho vừa chỗ (`timing_max_atempo`). Với
video quay thì đúng. Với slideshow thì ngược mới đúng: ảnh tĩnh không có nhịp
riêng, giữ 2,0 hay 2,3 giây đều không ai nhận ra.
"""
from __future__ import annotations

import json
import os

import pytest

from autodub import du_an_tu_kich_ban as dk


def _ghi_nguon(work_dir, anh, giay_chuyen=0.0):
    from autodub.workdir import data_path
    duong = data_path(work_dir, dk.TEN_NGUON_GOC, create_dir=True)
    os.makedirs(os.path.dirname(duong), exist_ok=True)
    with open(duong, "w", encoding="utf-8") as f:
        json.dump({"anh_moi_doan": anh, "giay_chuyen": giay_chuyen}, f)
    return duong


def _anh(tmp_path, n):
    ra = []
    for i in range(n):
        p = tmp_path / f"anh{i}.png"
        p.write_bytes(b"\x89PNG-gia")
        ra.append(str(p))
    return ra


def _segments(moc_va_cuoi):
    """`[(start, end), …]` → danh sách câu như editor truyền vào."""
    return [{"id": i + 1, "start": a, "end": b}
            for i, (a, b) in enumerate(moc_va_cuoi)]


class _Ghep:
    """Ghi lại lời gọi ghép, không chạy ffmpeg."""

    def __init__(self):
        self.goi = []

    def __call__(self, duong_anh, duong_ra, *, giay_moi_anh, giay_chuyen=0.3):
        self.goi.append({"anh": list(duong_anh), "giay": list(giay_moi_anh),
                         "ra": duong_ra, "chuyen": giay_chuyen})
        with open(duong_ra, "wb") as f:
            f.write(b"video gia")
        return duong_ra


# ================================================================
# Chuyện chính: hình đi theo mốc THẬT
# ================================================================

def test_dung_lai_theo_dung_moc_that_cua_tung_cau(tmp_path):
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    anh = _anh(tmp_path, 3)
    _ghi_nguon(wd, anh)
    # Ước lượng cũ 2+2+2; giọng thật 2,5 + 3,0 + 2,0.
    segs = _segments([(0.0, 2.5), (2.5, 5.5), (5.5, 7.5)])
    ghep = _Ghep()

    ra = dk.dung_lai_video_theo_giong(
        wd, segs, ghep_video=ghep, do_thoi_luong=lambda _p: 7.5)

    assert ra and os.path.basename(ra) == dk.TEN_VIDEO_NGUON
    assert ghep.goi[-1]["giay"] == pytest.approx([2.5, 3.0, 2.0])


def test_giay_chuyen_lay_lai_DUNG_bang_luc_dung_lan_dau(tmp_path):
    """Đổi kiểu chuyển cảnh giữa chừng thì `xfade` ăn mất thời lượng khác đi
    và cổng H4c-1 sẽ báo lệch — phải dùng lại đúng con số đã ghi."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    _ghi_nguon(wd, _anh(tmp_path, 2), giay_chuyen=0.45)
    ghep = _Ghep()
    dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 3.0), (3.0, 6.0)]),
        ghep_video=ghep, do_thoi_luong=lambda _p: 6.0)
    assert ghep.goi[-1]["chuyen"] == pytest.approx(0.45)


# ================================================================
# CHỐT AN TOÀN — đây là đường xuất của MỌI dự án
# ================================================================

def test_du_an_LONG_TIENG_THUONG_khong_bi_dung_lai(tmp_path):
    """Không có tệp truy nguồn ⇒ không phải dự án dựng từ kịch bản. Dựng lại
    ở đây nghĩa là thay video quay thật của người ta bằng một slideshow."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    ghep = _Ghep()
    assert dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 3.0)]), ghep_video=ghep) is None
    assert ghep.goi == [], "đã đụng vào dự án không phải của mình"


def test_du_an_dung_bang_BAN_CU_khong_co_danh_sach_anh(tmp_path):
    """Dự án dựng trước D1 không ghi `anh_moi_doan`. Không phải lỗi — chỉ là
    không làm được, và phải im lặng giữ nguyên."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    from autodub.workdir import data_path
    duong = data_path(wd, dk.TEN_NGUON_GOC, create_dir=True)
    os.makedirs(os.path.dirname(duong), exist_ok=True)
    with open(duong, "w", encoding="utf-8") as f:
        json.dump({"brand_script_id": "x", "so_doan": 2}, f)
    ghep = _Ghep()
    assert dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 3.0), (3.0, 6.0)]), ghep_video=ghep) is None
    assert ghep.goi == []


def test_so_anh_KHAC_so_cau_thi_bo_qua(tmp_path):
    """Người dùng sửa kịch bản thêm/bớt câu — ghép theo thứ tự nữa là ảnh lên
    nhầm đoạn."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    _ghi_nguon(wd, _anh(tmp_path, 3))
    ghep = _Ghep()
    assert dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 3.0), (3.0, 6.0)]), ghep_video=ghep) is None
    assert ghep.goi == []


def test_anh_bi_XOA_hoac_DOI_CHO_thi_bo_qua(tmp_path):
    """Ảnh là tệp của người dùng — họ có quyền dọn ổ đĩa."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    anh = _anh(tmp_path, 2)
    os.unlink(anh[1])
    _ghi_nguon(wd, anh)
    ghep = _Ghep()
    assert dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 3.0), (3.0, 6.0)]), ghep_video=ghep) is None
    assert ghep.goi == []


def test_MOC_KHONG_TANG_DAN_thi_bo_qua_chu_khong_doan(tmp_path):
    """Không lát kín được dòng thời gian thì giữ nguyên, đừng đoán.

    Chú ý ĐÚNG điều kiện: hai câu *chồng tiếng* (``end`` lấn sang câu sau) vẫn
    lát kín được, vì cảnh chỉ cần đổi tại ``start`` của câu kế. Ca thật sự
    hỏng là **mốc không tăng dần** — lúc đó có cảnh dài 0 hoặc âm.

    (Bản đầu của test này dùng dữ liệu chồng tiếng và đỏ: tiền đề của tôi sai,
    không phải mã sai.)
    """
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    _ghi_nguon(wd, _anh(tmp_path, 3))
    ghep = _Ghep()
    assert dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 4.0), (4.0, 5.0), (4.0, 7.0)]),
        ghep_video=ghep) is None
    assert ghep.goi == []


def test_chong_tieng_VAN_lat_kin_duoc_vi_canh_doi_tai_start(tmp_path):
    """Chốt đi kèm test trên: đừng chặn oan ca chồng tiếng bình thường."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    _ghi_nguon(wd, _anh(tmp_path, 3))
    ghep = _Ghep()
    ra = dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 4.0), (2.0, 5.5), (5.0, 7.0)]),
        ghep_video=ghep, do_thoi_luong=lambda _p: 7.0)
    assert ra is not None
    assert ghep.goi[-1]["giay"] == pytest.approx([2.0, 3.0, 2.0])


def test_DUNG_SUA_QUA_TAY_uoc_luong_da_dung_thi_KHONG_dung_lai(tmp_path):
    """Dựng lại tốn hàng chục giây ffmpeg. Thay một tệp đang đúng bằng một tệp
    cũng đúng là rủi ro không đổi lại được gì."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    _ghi_nguon(wd, _anh(tmp_path, 2))
    with open(os.path.join(wd, dk.TEN_VIDEO_NGUON), "wb") as f:
        f.write(b"video cu")
    ghep = _Ghep()
    # Giọng thật 6,0 giây, video đang có 6,05 giây — lệch 0,05 < ngưỡng.
    assert dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 3.0), (3.0, 6.0)]),
        ghep_video=ghep, do_thoi_luong=lambda _p: 6.05) is None
    assert ghep.goi == []


def test_lech_VUA_DU_nguong_thi_van_dung_lai(tmp_path):
    """Chốt của chốt trên: ngưỡng phải là ngưỡng thật, không phải cái cớ để
    không bao giờ dựng lại."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    _ghi_nguon(wd, _anh(tmp_path, 2))
    with open(os.path.join(wd, dk.TEN_VIDEO_NGUON), "wb") as f:
        f.write(b"video cu")
    ghep = _Ghep()
    goi = {"n": 0}

    def do(_p):
        goi["n"] += 1
        return 5.0 if goi["n"] == 1 else 6.0     # lượt 1: video cũ; lượt 2: mới

    assert dk.dung_lai_video_theo_giong(
        wd, _segments([(0.0, 3.0), (3.0, 6.0)]),
        ghep_video=ghep, do_thoi_luong=do) is not None
    assert ghep.goi


def test_cong_thoi_luong_H4c1_VAN_CHAY_tren_video_moi(tmp_path):
    """Dựng lại mà lệch thì phải hỏng TO TIẾNG, không âm thầm ghi đè một video
    sai lên một video đúng."""
    wd = str(tmp_path / "duan"); os.makedirs(wd)
    _ghi_nguon(wd, _anh(tmp_path, 2))
    ghep = _Ghep()
    with pytest.raises(dk.VideoLechThoiLuong):
        dk.dung_lai_video_theo_giong(
            wd, _segments([(0.0, 3.0), (3.0, 6.0)]),
            ghep_video=ghep, do_thoi_luong=lambda _p: 99.0)


# ================================================================
# Nối dây: dung_du_an có GIỮ danh sách ảnh không
# ================================================================

def test_dung_du_an_GHI_LAI_danh_sach_anh_va_giay_chuyen(tmp_path):
    """Trước D1, hàm này dựng video xong rồi VỨT danh sách ảnh đi — nên về sau
    không còn gì để dựng lại."""
    wd = str(tmp_path / "duan")
    anh = _anh(tmp_path, 2)
    kich_ban = {"status": "ready", "beats": [
        {"beatType": "hook", "voiceoverTextVi": "Một hai ba."},
        {"beatType": "cta", "voiceoverTextVi": "Bốn năm sáu bảy."}]}
    from autodub.storyboard import dung_storyboard
    tong = dung_storyboard(kich_ban).tong_giay

    dk.dung_du_an(kich_ban, anh, wd, giay_chuyen=0.4,
                  ghep_video=_Ghep(), do_thoi_luong=lambda _p: tong)

    from autodub.workdir import data_path
    with open(data_path(wd, dk.TEN_NGUON_GOC), encoding="utf-8") as f:
        nguon = json.load(f)
    assert nguon["anh_moi_doan"] == anh
    assert nguon["giay_chuyen"] == pytest.approx(0.4)


def test_duong_xuat_CHI_dung_lai_khi_video_dung_la_slideshow():
    """`rebuild_output` là đường xuất CHUNG. Đọc mã nguồn để chắc điều kiện
    còn nguyên — mất nó thì một dự án lồng tiếng thường sẽ bị thay video."""
    import inspect

    from autodub import editor
    ma = inspect.getsource(editor.rebuild_output)
    assert "dung_lai_video_theo_giong" in ma
    assert "os.path.basename(video_path) == TEN_VIDEO_NGUON" in ma, (
        "mất điều kiện này thì video quay thật của người dùng sẽ bị thay bằng "
        "slideshow")


def test_dung_lai_HONG_khong_duoc_giet_luot_xuat():
    """Bản cũ vẫn dùng được, chỉ là hình lệch dần. Nói to rồi đi tiếp."""
    import inspect

    from autodub import editor
    ma = inspect.getsource(editor.rebuild_output)
    i = ma.index("dung_lai_video_theo_giong")
    assert "except Exception" in ma[i:i + 900]
