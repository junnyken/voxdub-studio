"""C6 — ghép ảnh sản phẩm đã duyệt thành video ngắn.

Video là thứ TikTok Shop đem đi đối chiếu với sản phẩm đang bán. Một tấm ảnh
lệch nhãn lọt vào video thì hậu quả không dừng ở tấm ảnh — nó là cái video bị
gắn cờ. Nên bộ test này không kiểm "video có đẹp không", nó kiểm **không có
đường nào** đưa được ảnh chưa duyệt vào tệp xuất ra.
"""
from __future__ import annotations

import json
import os

import pytest

from autodub import product_video as pv
from autodub.product_scene import NHAT_KY, bam_tep


def _viet_anh(thu_muc, ten, noi_dung=b"\xff\xd8\xff\xe0anh"):
    duong = os.path.join(thu_muc, ten)
    with open(duong, "wb") as f:
        f.write(noi_dung)
    return duong


def _nguon(thu_muc, ten, **thay):
    duong = _viet_anh(thu_muc, ten)
    mac_dinh = dict(duong_dan=duong, boi_canh="ban_go", ket_luan="SAFE",
                    ly_do="chỉ đổi nền", da_kiem=True, da_dong_nhan=True,
                    bam_luc_kiem=bam_tep(duong))
    mac_dinh.update(thay)
    return pv.AnhNguon(**mac_dinh)


# -- Ai được vào video -------------------------------------------------------

def test_anh_dat_thi_dung_duoc(tmp_path):
    assert _nguon(str(tmp_path), "a.jpg").dung_duoc


@pytest.mark.parametrize("thay,vi_sao", [
    ({"ket_luan": "CONCEPT"}, "lệch bao bì"),
    ({"da_kiem": False}, "chưa kiểm được"),
    ({"da_dong_nhan": False}, "chưa đóng được nhãn AI-generated"),
])
def test_thieu_mot_dieu_kien_la_khong_dung_duoc(tmp_path, thay, vi_sao):
    assert not _nguon(str(tmp_path), "a.jpg", **thay).dung_duoc, vi_sao


def test_nhat_ky_ban_cu_thieu_truong_thi_coi_nhu_chua_dat(tmp_path):
    """Mặc định phải nghiêng về phía an toàn, không phải phía tiện."""
    ra = tmp_path / "ra"
    ra.mkdir()
    _viet_anh(str(ra), "cu.jpg")
    (ra / NHAT_KY).write_text(json.dumps({"lich_su": [{"anh_da_dung": [
        # Bản cũ: không có "bam", không có "da_dong_nhan".
        {"tep": "cu.jpg", "boi_canh": "ban_go", "ket_luan": "SAFE",
         "ly_do": "ổn", "da_kiem": True},
    ]}]}), encoding="utf-8")

    anh = pv.doc_nhat_ky(str(ra))
    assert len(anh) == 1
    assert not anh[0].dung_duoc


# -- Phép kiểm lần hai, ngay trước lúc ghép ---------------------------------

def test_tep_bi_thay_ruot_sau_khi_kiem_thi_CHAN(tmp_path):
    """Đường lách thật duy nhất: tên tệp không đổi, ruột thì đổi.

    Nhật ký vẫn ghi "đạt", giao diện vẫn hiện xanh, mà ảnh đã là ảnh khác.
    """
    a = _nguon(str(tmp_path), "a.jpg")
    with open(a.duong_dan, "wb") as f:
        f.write(b"anh-hoan-toan-khac")

    ket = pv.kiem_lai_truoc_khi_xuat([a])
    assert not ket.cho_phep
    assert "đã bị sửa sau khi kiểm" in ket.bi_chan[0][1]


def test_tep_bien_mat_thi_chan(tmp_path):
    a = _nguon(str(tmp_path), "a.jpg")
    os.unlink(a.duong_dan)
    ket = pv.kiem_lai_truoc_khi_xuat([a])
    assert not ket.cho_phep
    assert "không còn tệp" in ket.bi_chan[0][1]


def test_chan_thi_noi_ro_ANH_NAO_va_vi_sao(tmp_path):
    """Người dùng phải sửa được, nên phải biết sửa cái nào."""
    tot = _nguon(str(tmp_path), "tot.jpg")
    xau = _nguon(str(tmp_path), "xau.jpg", ket_luan="CONCEPT",
                 ly_do="nhãn khác chữ so với bản gốc")
    ket = pv.kiem_lai_truoc_khi_xuat([tot, xau])
    assert not ket.cho_phep
    assert len(ket.bi_chan) == 1
    ten, ly_do = ket.bi_chan[0]
    assert ten == "xau.jpg"
    assert "nhãn khác chữ" in ly_do, "phải đọc thẳng lý do trong sổ, không tự chế"


def test_khong_co_anh_nao_thi_khong_cho_phep(tmp_path):
    assert not pv.kiem_lai_truoc_khi_xuat([]).cho_phep


# -- Hàm xuất là chỗ cuối cùng nói được KHÔNG -------------------------------

def test_dung_video_tu_kiem_lai_du_ben_goi_da_kiem(tmp_path, monkeypatch):
    """Không tin bên gọi: đây là hàm DUY NHẤT tạo ra tệp video."""
    monkeypatch.setattr(pv.subprocess, "run",
                        lambda *a, **k: pytest.fail("đã gọi ffmpeg dù ảnh lệch"))
    xau = _nguon(str(tmp_path), "xau.jpg", ket_luan="CONCEPT", ly_do="lệch nhãn")
    with pytest.raises(PermissionError, match="không dùng để bán được"):
        pv.dung_video([xau], str(tmp_path / "ra.mp4"))


def test_chua_chon_anh_nao_thi_bao_ngay(tmp_path):
    with pytest.raises(ValueError):
        pv.dung_video([], str(tmp_path / "ra.mp4"))


def test_chan_tran_so_anh_moi_video(tmp_path):
    anh = [_nguon(str(tmp_path), f"a{i}.jpg") for i in range(9)]
    with pytest.raises(ValueError, match="tối đa"):
        pv.dung_video(anh, str(tmp_path / "ra.mp4"))


# -- Lệnh ghép ---------------------------------------------------------------

def test_anh_duoc_DEM_chu_khong_bi_CAT(tmp_path):
    """Cắt cho vừa khung là có ngày cắt mất chính cái nhãn mà cả tính năng
    này sinh ra để giữ."""
    lenh = pv._lenh_ghep(["a.jpg", "b.jpg"], "ra.mp4", 2.0, 0.4)
    loc = lenh[lenh.index("-filter_complex") + 1]
    assert "force_original_aspect_ratio=decrease" in loc
    assert "pad=" in loc
    assert "crop" not in loc


def test_thu_tu_anh_giu_nguyen(tmp_path):
    lenh = pv._lenh_ghep(["dau.jpg", "giua.jpg", "cuoi.jpg"], "ra.mp4", 2.0, 0.4)
    vao = [lenh[i + 1] for i, x in enumerate(lenh) if x == "-i"]
    assert vao == ["dau.jpg", "giua.jpg", "cuoi.jpg"]


def test_mot_anh_van_ghep_duoc(tmp_path):
    """Không có chuyển cảnh nào để làm — đừng dựng bộ lọc xfade rỗng."""
    lenh = pv._lenh_ghep(["a.jpg"], "ra.mp4", 2.0, 0.4)
    loc = lenh[lenh.index("-filter_complex") + 1]
    assert "xfade" not in loc


def test_moc_chuyen_canh_tinh_theo_thoi_luong_that(tmp_path):
    # Đặt mốc sai thì video hoặc đen giữa chừng, hoặc cụt mất ảnh cuối.
    lenh = pv._lenh_ghep(["a.jpg", "b.jpg", "c.jpg"], "ra.mp4", 3.0, 0.5)
    loc = lenh[lenh.index("-filter_complex") + 1]
    assert "offset=2.500" in loc
    assert "offset=5.000" in loc


# -- Cổng nấc ---------------------------------------------------------------

def test_chua_co_tai_khoan_thi_khong_mo(monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: False)
    duoc, ly_do = pv.duoc_dung_video()
    assert not duoc and "tài khoản" in ly_do


def test_chi_mo_o_nac_chay_that(monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    for nac, mong in [("off", False), ("calibration", False), ("production", True)]:
        monkeypatch.setattr("autodub.saas_client.get_client",
                            lambda n=nac: type("K", (), {
                                "app_config": lambda self: {"imageSceneStage": n}})())
        assert pv.duoc_dung_video()[0] is mong, nac


def test_hoi_khong_duoc_may_chu_thi_DONG(monkeypatch):
    """Mặc định phải là đóng, không phải mở."""
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    monkeypatch.setattr("autodub.saas_client.get_client",
                        lambda: type("K", (), {
                            "app_config": lambda self: (_ for _ in ()).throw(
                                RuntimeError("mất mạng"))})())
    assert pv.duoc_dung_video()[0] is False
