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


def _khach_nac(tra_ve):
    """Máy chủ giả trả lời cửa `/v1/ai/scene-stage`."""
    return type("K", (), {"scene_stage": lambda self: tra_ve})()


def test_nac_tat_thi_khong_mo(monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    monkeypatch.setattr("autodub.saas_client.get_client",
                        lambda: _khach_nac({"runMode": "", "videoDuoc": False,
                                            "message": "Tính năng đang tắt."}))
    duoc, loi_nhan = pv.duoc_dung_video()
    assert duoc is False
    assert "đang tắt" in loi_nhan, "phải in nguyên văn lý do của máy chủ"


def test_nac_chay_that_thi_mo_va_KHONG_canh_bao(monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    monkeypatch.setattr("autodub.saas_client.get_client",
                        lambda: _khach_nac({"runMode": "production",
                                            "videoDuoc": True, "canhBao": ""}))
    assert pv.duoc_dung_video() == (True, "")


def test_may_DANG_HIEU_CHINH_thi_dung_duoc_nhung_phai_canh_bao(monkeypatch):
    """C18: chặn nhầm đúng người đang chạy đợt hiệu chỉnh là chặn sai chỗ.

    Nhưng mở mà không nói gì thì họ cầm cái video đi đăng — ảnh trong đó chưa
    ai soi tay. Mở KÈM cảnh báo là chỗ đứng đúng.
    """
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    monkeypatch.setattr("autodub.saas_client.get_client",
                        lambda: _khach_nac({
                            "runMode": "calibration", "videoDuoc": True,
                            "canhBao": "bản dựng thử, đừng đăng bán"}))
    duoc, loi_nhan = pv.duoc_dung_video()
    assert duoc is True
    assert "đừng đăng bán" in loi_nhan


def test_hoi_khong_duoc_may_chu_thi_DONG(monkeypatch):
    """Mặc định phải là đóng, không phải mở."""
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    monkeypatch.setattr("autodub.saas_client.get_client",
                        lambda: type("K", (), {
                            "scene_stage": lambda self: (_ for _ in ()).throw(
                                RuntimeError("mất mạng"))})())
    assert pv.duoc_dung_video()[0] is False


# -- Kiểm liên tục giữa các cảnh (C7) ---------------------------------------
#
# Ranh giới dễ nhầm nhất của cả tính năng: đây là lớp CẢNH BÁO, không phải
# lớp chặn. Lệch liên tục là chuyện video xem có mượt hay không; lệch bao bì
# mới là chuyện bị sàn phạt. Trộn hai mức đó làm một là dạy người dùng bỏ qua
# cả hai.

class _KhachLienTuc:
    def __init__(self, gia_tri="MUOT", ly_do="các cảnh cùng cỡ, cùng tông",
                 no=False):
        self.gia_tri, self.ly_do, self.no = gia_tri, ly_do, no
        self.da_goi = []

    def assist(self, task, input_data, *, job_id, images=None, hold_id=None,
               timeout=45.0):
        self.da_goi.append((task, len(images or [])))
        if self.no:
            raise RuntimeError("máy chủ bận")
        if task == "scene_script":
            return [{"value": f"câu {i}", "reason": "giữ 2 giây"}
                    for i in range(len(input_data.get("scenes", [])))]
        return [{"value": self.gia_tri, "reason": self.ly_do}]


@pytest.fixture()
def co_tai_khoan(monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    monkeypatch.setattr("autodub.saas_client.new_job_id", lambda: "job-1234567")
    monkeypatch.setattr(pv, "_chay_ffmpeg", lambda *a, **k: False)


def test_mot_anh_thi_KHONG_goi_may_chu(tmp_path, co_tai_khoan):
    """Một ảnh không có gì để so — gọi là tiêu tiền lấy câu trả lời hiển nhiên."""
    khach = _KhachLienTuc()
    ket = pv.kiem_lien_tuc([_nguon(str(tmp_path), "a.jpg")], khach=khach)
    assert khach.da_goi == []
    assert not ket.da_kiem


def test_hai_anh_tro_len_thi_goi_MOT_luot_cho_ca_me(tmp_path, co_tai_khoan):
    """So từng cặp thì chi phí nhân theo bình phương số cảnh để đổi lấy một
    câu trả lời không khác gì mấy."""
    anh = [_nguon(str(tmp_path), f"a{i}.jpg") for i in range(4)]
    khach = _KhachLienTuc()
    pv.kiem_lien_tuc(anh, khach=khach)
    assert len(khach.da_goi) == 1, "gọi nhiều lượt = tính tiền theo số cặp"
    assert khach.da_goi[0] == ("scene_continuity", 4)


def test_gui_toi_da_sau_anh(tmp_path, co_tai_khoan):
    anh = [_nguon(str(tmp_path), f"a{i}.jpg") for i in range(8)]
    khach = _KhachLienTuc()
    pv.kiem_lien_tuc(anh, khach=khach)
    assert khach.da_goi[0][1] == 6


def test_bao_lech_kem_ly_do_bang_loi(tmp_path, co_tai_khoan):
    anh = [_nguon(str(tmp_path), f"a{i}.jpg") for i in range(3)]
    khach = _KhachLienTuc("LECH", "ảnh 3: sản phẩm nhỏ hơn hẳn và ám vàng")
    ket = pv.kiem_lien_tuc(anh, khach=khach)
    assert ket.da_kiem and not ket.muot
    assert "ảnh 3" in ket.ly_do


def test_LECH_KHONG_chan_xuat_video(tmp_path, monkeypatch, co_tai_khoan):
    """Ranh giới cốt lõi: cảnh báo, không phải chặn."""
    goi = {}

    class _Chay:
        returncode = 0
        stderr = ""

    def _ffmpeg_gia(*_a, **_k):
        # `setdefault(...) or <đối tượng>` là bẫy: setdefault trả về giá trị
        # truthy nên `or` không bao giờ chạy tới vế sau. Đã mắc hai lần.
        goi["chay"] = True
        open(ra, "wb").close()
        return _Chay()

    anh = [_nguon(str(tmp_path), f"a{i}.jpg") for i in range(2)]
    ra = str(tmp_path / "ra.mp4")
    monkeypatch.setattr(pv.subprocess, "run", _ffmpeg_gia)
    pv.dung_video(anh, ra)
    assert goi.get("chay"), "lệch liên tục mà lại chặn xuất video"


def test_kiem_lien_tuc_KHONG_dung_trong_duong_xuat(tmp_path):
    """Hai lớp kiểm phải độc lập: kiểm liên tục không được len vào đường
    quyết định xuất hay không."""
    from tests.doc_ma import co_goi

    for ham in (pv.dung_video, pv.kiem_lai_truoc_khi_xuat):
        assert not co_goi(ham, "kiem_lien_tuc"), \
            f"{ham.__name__} đang để kiểm liên tục chen vào đường quyết định"


def test_anh_lech_BAO_BI_van_bi_chan_du_lien_tuc_bao_muot(tmp_path, co_tai_khoan):
    """Kiểm liên tục nói 'mượt' không cứu nổi một ảnh lệch bao bì."""
    lech = _nguon(str(tmp_path), "lech.jpg", ket_luan="CONCEPT",
                  ly_do="nhãn khác chữ")
    tot = _nguon(str(tmp_path), "tot.jpg")
    assert pv.kiem_lien_tuc([lech, tot], khach=_KhachLienTuc("MUOT")).muot
    with pytest.raises(PermissionError):
        pv.dung_video([lech, tot], str(tmp_path / "ra.mp4"))


def test_may_chu_hong_thi_im_lang_bo_qua(tmp_path, co_tai_khoan):
    anh = [_nguon(str(tmp_path), f"a{i}.jpg") for i in range(2)]
    ket = pv.kiem_lien_tuc(anh, khach=_KhachLienTuc(no=True))
    assert not ket.da_kiem and ket.muot, "cảnh báo hỏng không được thành báo động"


def test_nhan_la_thi_coi_nhu_chua_kiem(tmp_path, co_tai_khoan):
    anh = [_nguon(str(tmp_path), f"a{i}.jpg") for i in range(2)]
    ket = pv.kiem_lien_tuc(anh, khach=_KhachLienTuc("CHAC_ON"))
    assert not ket.da_kiem


# -- Gợi ý kịch bản ----------------------------------------------------------

def test_goi_y_kich_ban_tra_dung_so_canh(tmp_path, co_tai_khoan):
    anh = [_nguon(str(tmp_path), f"a{i}.jpg") for i in range(3)]
    ra = pv.goi_y_kich_ban(anh, san_pham="trà gừng", khach=_KhachLienTuc())
    assert len(ra) == 3
    assert all(cau and nhip for cau, nhip in ra)


def test_goi_y_hong_thi_tra_rong_khong_no(tmp_path, co_tai_khoan):
    anh = [_nguon(str(tmp_path), "a.jpg")]
    assert pv.goi_y_kich_ban(anh, khach=_KhachLienTuc(no=True)) == []


# -- Nhãn AI-generated ở tầng video (C10) ------------------------------------
#
# C1 đã đóng nhãn lên từng tấm ảnh, nên vì sao còn đóng thêm ở tầng video:
# nhãn của C1 chỉ nằm trên ảnh đi qua đường dựng của C1. Ngày nào ghép thêm
# ảnh từ nguồn khác thì video ra đời không nhãn mà không ai kịp nhận ra.
# `_lenh_ghep` là hàm duy nhất tạo ra tệp video — đóng ở đây là chỗ duy nhất
# phủ được mọi nguồn.

def _bo_loc(lenh: list[str]) -> str:
    return lenh[lenh.index("-filter_complex") + 1]


def test_nhan_ai_co_mat_o_canh_dau():
    loc = _bo_loc(pv._lenh_ghep(["a.jpg", "b.jpg"], "ra.mp4", 2.5, 0.5))
    assert "drawtext" in loc
    assert pv.NHAN_VIDEO in loc
    # Chỉ hiện ở cảnh đầu — mốc phải bám đúng độ dài một ảnh, không phải
    # một con số gõ cứng ở đâu đó.
    assert "enable='lte(t,2.500)'" in loc


def test_mot_anh_cung_phai_co_nhan():
    """Ca dễ lọt nhất: bản cũ có nhánh riêng cho video một ảnh."""
    loc = _bo_loc(pv._lenh_ghep(["a.jpg"], "ra.mp4", 2.5, 0.5))
    assert pv.NHAN_VIDEO in loc


def test_nhan_nam_tren_luong_RA_chu_khong_phai_nhanh_bo_di():
    """Đóng nhãn lên một nhánh rồi không dùng nhánh đó = video trần."""
    loc = _bo_loc(pv._lenh_ghep(["a.jpg", "b.jpg", "c.jpg"], "ra.mp4", 2.5, 0.5))
    cuoi = loc.split(";")[-1]
    assert "drawtext" in cuoi and cuoi.endswith("[ra]")


@pytest.mark.parametrize("giay,chuyen", [(2.5, 0.5), (1.0, 0.2), (6.0, 1.5)])
def test_doi_nhip_the_nao_nhan_van_con(giay, chuyen):
    loc = _bo_loc(pv._lenh_ghep(["a.jpg", "b.jpg"], "ra.mp4", giay, chuyen))
    assert pv.NHAN_VIDEO in loc
    assert f"enable='lte(t,{giay:.3f})'" in loc


def test_khong_co_tham_so_nao_tat_duoc_nhan():
    """Nhãn không được là tuỳ chọn: một cái nút tắt là một cái nút bấm nhầm."""
    import inspect

    for ham in (pv.dung_video, pv._lenh_ghep):
        ten = set(inspect.signature(ham).parameters)
        assert not (ten & {"nhan", "watermark", "dong_nhan", "khong_nhan"}), (
            f"{ham.__name__} có tham số tắt nhãn")


def test_duong_xuat_that_van_mang_nhan(tmp_path, monkeypatch):
    """Chặn đường vòng: sửa `_lenh_ghep` mà quên đường `dung_video` gọi."""
    lenh_da_chay = {}

    def _gia(lenh, **_k):
        lenh_da_chay["lenh"] = lenh
        open(lenh[-1], "wb").write(b"x")
        return type("R", (), {"returncode": 0, "stderr": ""})()

    anh = _nguon(str(tmp_path), "tot.jpg")
    monkeypatch.setattr(pv.subprocess, "run", _gia)
    pv.dung_video([anh], str(tmp_path / "ra.mp4"))
    assert pv.NHAN_VIDEO in _bo_loc(lenh_da_chay["lenh"])
