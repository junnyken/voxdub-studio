"""C1 — dựng bối cảnh ảnh sản phẩm, có cổng kiểm tuân thủ TikTok Shop.

Người bán gửi ảnh chụp màn hình: tài khoản bị **cưỡng chế hủy quyền thương mại
điện tử + trừ 1000 điểm CHR** vì "quảng bá sản phẩm không nhất quán" — video
không khớp sản phẩm đang bán. Enforcement chạy tự động bằng thị giác máy tính,
và 6 lần cùng loại trong 90 ngày là mất quyền bán bất kể điểm.

Nên bộ test này không kiểm "ảnh có đẹp không". Nó kiểm đúng ba luật giữ cho
người bán không mất kênh:

1. Mặc định giữ nguyên sản phẩm.
2. Kết quả kiểm ĐÈ LÊN chế độ người dùng chọn — mô hình hứa giữ nguyên là một
   chuyện, nó có giữ hay không là chuyện khác.
3. Không kiểm được thì coi như CONCEPT — nghiêng về phía an toàn.
"""
from __future__ import annotations

import json
import os

import pytest

from autodub import product_scene as ps
from autodub.product_scene import KetQua


class _KhachGia:
    """Máy chủ giả: dựng ảnh gì, kiểm ra sao — điều khiển được từng lượt."""

    def __init__(self, phan_quyet=None, anh_hong=False, no_khi_dung=None):
        self.phan_quyet = phan_quyet or [("SAFE", "chỉ đổi nền và ánh sáng")]
        self.anh_hong = anh_hong
        self.no_khi_dung = no_khi_dung
        self.da_dung = []
        self.da_kiem = []

    def product_scene(self, image, scene, *, job_id, mode="SAFE", note="",
                      hold_id=None, timeout=120.0):
        self.da_dung.append((scene, mode))
        if self.no_khi_dung:
            raise self.no_khi_dung
        if self.anh_hong:
            return {"image": {}}
        return {"image": {"mimeType": "image/jpeg", "data": "//4AAQ=="},
                "mode": mode, "creditCharged": 30}

    def assist(self, task, input_data, *, job_id, images=None, hold_id=None,
               timeout=45.0):
        self.da_kiem.append((task, len(images or [])))
        gia_tri, ly_do = self.phan_quyet[
            min(len(self.da_kiem) - 1, len(self.phan_quyet) - 1)]
        if gia_tri == "__NO__":
            raise RuntimeError(ly_do)
        return [{"value": gia_tri, "reason": ly_do}]


@pytest.fixture()
def cam_may_chu(monkeypatch, tmp_path):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    monkeypatch.setattr("autodub.saas_client.new_job_id", lambda: "job-1234567")
    # Không gọi ffmpeg thật trong test: thu nhỏ và đóng nhãn đều là ffmpeg.
    monkeypatch.setattr(ps, "_chay_ffmpeg", lambda *a, **k: False)
    anh = tmp_path / "san_pham.jpg"
    anh.write_bytes(b"\xff\xd8\xff\xe0" + b"gia-lap-anh")
    return anh


# -- 1. Kết quả kiểm đè lên chế độ người dùng chọn ---------------------------

def test_xin_safe_nhung_anh_lech_thi_van_la_concept(cam_may_chu, tmp_path):
    """Luật quan trọng nhất của cả tính năng."""
    khach = _KhachGia([("CONCEPT", "nhãn khác chữ so với bản gốc")])

    phien = ps.dung_boi_canh(str(cam_may_chu), ["ban_go"], str(tmp_path / "ra"),
                             che_do="SAFE", khach=khach)

    k = phien.ket_qua[0]
    assert k.che_do_xin == "SAFE"
    assert k.che_do_that == "CONCEPT"
    assert not k.dung_duoc_de_ban, "ảnh lệch bao bì mà vẫn cho gắn vào bài bán"


def test_khong_kiem_duoc_thi_coi_nhu_concept(cam_may_chu, tmp_path):
    """Đoán sai theo hướng an toàn thì mất một tấm ảnh; đoán sai hướng kia thì
    mất tài khoản bán hàng."""
    khach = _KhachGia([("__NO__", "mất mạng")])

    phien = ps.dung_boi_canh(str(cam_may_chu), ["ban_go"], str(tmp_path / "ra"),
                             khach=khach)

    k = phien.ket_qua[0]
    assert k.che_do_that == "CONCEPT"
    assert k.da_kiem is False
    assert not k.dung_duoc_de_ban


def test_may_chu_tra_ket_qua_la_cung_khong_tin(cam_may_chu, tmp_path):
    khach = _KhachGia([("CHAC_LA_ON", "mô hình trả nhãn lạ")])

    phien = ps.dung_boi_canh(str(cam_may_chu), ["ban_go"], str(tmp_path / "ra"),
                             khach=khach)

    assert phien.ket_qua[0].che_do_that == "CONCEPT"
    assert phien.ket_qua[0].da_kiem is False


def test_anh_dat_thi_dung_duoc(cam_may_chu, tmp_path):
    khach = _KhachGia([("SAFE", "chỉ đổi nền và ánh sáng")])

    phien = ps.dung_boi_canh(str(cam_may_chu), ["nen_studio"],
                             str(tmp_path / "ra"), khach=khach)

    k = phien.ket_qua[0]
    assert k.dung_duoc_de_ban
    assert "nền" in k.ly_do
    assert phien.so_dung_duoc == 1


# -- 2. Không có đường tắt bỏ bước kiểm --------------------------------------

def test_moi_anh_deu_bi_kiem(cam_may_chu, tmp_path):
    khach = _KhachGia([("SAFE", "chỉ đổi nền")])

    ps.dung_boi_canh(str(cam_may_chu), ["ban_go", "nen_studio", "gio_qua"],
                     str(tmp_path / "ra"), khach=khach)

    assert len(khach.da_kiem) == 3, "có ảnh không đi qua bước kiểm"
    assert all(t == "packaging_check" and n == 2 for t, n in khach.da_kiem), \
        "phải gửi ĐÚNG 2 ảnh (gốc + mới) cho mỗi lượt kiểm"


def test_mot_boi_canh_hong_khong_giet_ca_me(cam_may_chu, tmp_path, monkeypatch):
    khach = _KhachGia([("SAFE", "chỉ đổi nền")])
    that = khach.product_scene
    goi = {"n": 0}

    def _thinh_thoang_hong(*a, **k):
        goi["n"] += 1
        if goi["n"] == 2:
            raise RuntimeError("máy chủ bận")
        return that(*a, **k)

    khach.product_scene = _thinh_thoang_hong
    phien = ps.dung_boi_canh(str(cam_may_chu), ["ban_go", "nen_studio", "gio_qua"],
                             str(tmp_path / "ra"), khach=khach)
    assert len(phien.ket_qua) == 2, "mất cả mẻ chỉ vì một bối cảnh hỏng"


def test_may_chu_khong_tra_anh_thi_bo_qua_boi_canh_do(cam_may_chu, tmp_path):
    khach = _KhachGia(anh_hong=True)
    phien = ps.dung_boi_canh(str(cam_may_chu), ["ban_go"], str(tmp_path / "ra"),
                             khach=khach)
    assert phien.ket_qua == []


# -- 3. Nhật ký tra soát -----------------------------------------------------

def test_ghi_nhat_ky_du_de_khieu_nai(cam_may_chu, tmp_path):
    khach = _KhachGia([("SAFE", "chỉ đổi nền"), ("CONCEPT", "nhãn khác chữ")])
    ra = tmp_path / "ra"

    ps.dung_boi_canh(str(cam_may_chu), ["ban_go", "gio_qua"], str(ra),
                     khach=khach)

    duong = ra / ps.NHAT_KY
    assert duong.is_file()
    nhat_ky = json.loads(duong.read_text(encoding="utf-8"))
    lan = nhat_ky["lich_su"][-1]
    assert lan["anh_goc"].endswith("san_pham.jpg")
    assert lan["bam_anh_goc"], "thiếu dấu vân tay ảnh gốc thì tra bằng gì"
    assert len(lan["anh_da_dung"]) == 2
    for muc in lan["anh_da_dung"]:
        for khoa in ("tep", "boi_canh", "xin", "ket_luan", "ly_do", "da_kiem"):
            assert khoa in muc, f"nhật ký thiếu «{khoa}»"


def test_nhat_ky_ghi_noi_tiep_khong_de_len(cam_may_chu, tmp_path):
    khach = _KhachGia([("SAFE", "chỉ đổi nền")])
    ra = str(tmp_path / "ra")

    ps.dung_boi_canh(str(cam_may_chu), ["ban_go"], ra, khach=khach)
    ps.dung_boi_canh(str(cam_may_chu), ["gio_qua"], ra, khach=khach)

    nhat_ky = json.loads(open(os.path.join(ra, ps.NHAT_KY),
                              encoding="utf-8").read())
    assert len(nhat_ky["lich_su"]) == 2, "lượt sau xoá mất lượt trước"


# -- 4. Chặn trước khi tốn tiền ----------------------------------------------

def test_chua_co_tai_khoan_thi_khong_goi_ra_ngoai(tmp_path, monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: False)
    monkeypatch.setattr("autodub.saas_client.get_client",
                        lambda: pytest.fail("chưa có tài khoản mà vẫn gọi"))
    anh = tmp_path / "a.jpg"
    anh.write_bytes(b"x")

    with pytest.raises(RuntimeError, match="Cài đặt"):
        ps.dung_boi_canh(str(anh), ["ban_go"], str(tmp_path / "ra"))


def test_khong_co_anh_thi_bao_ngay(tmp_path, monkeypatch):
    monkeypatch.setattr(ps, "_chay_ffmpeg", lambda *a, **k: False)
    with pytest.raises(FileNotFoundError):
        ps.chuan_bi_anh(str(tmp_path / "khong-co.jpg"), str(tmp_path))


def test_anh_qua_nang_thi_bao_bang_tieng_nguoi(tmp_path, monkeypatch):
    monkeypatch.setattr(ps, "_chay_ffmpeg", lambda *a, **k: False)
    monkeypatch.setattr(ps, "_TRAN_BASE64", 10)
    anh = tmp_path / "to.jpg"
    anh.write_bytes(b"x" * 500)

    with pytest.raises(ValueError, match="quá nặng"):
        ps.chuan_bi_anh(str(anh), str(tmp_path))


# -- 5. Nhãn AI-generated ----------------------------------------------------

def test_anh_concept_duoc_dong_nhan_manh_hon(tmp_path, monkeypatch):
    lenh = {}
    monkeypatch.setattr(ps, "_chay_ffmpeg",
                        lambda args, **k: lenh.setdefault("args", args) or True)
    anh = tmp_path / "a.jpg"
    anh.write_bytes(b"x")

    ps.dong_nhan_ai(str(anh), "CONCEPT")
    chu = " ".join(lenh["args"])
    assert "AI-generated" in chu
    assert "khong phai san pham dang ban" in chu, (
        "ảnh ý tưởng phải nói rõ là ý tưởng, không thì nó y hệt ảnh bán hàng")


def test_khong_dong_duoc_nhan_thi_bao_that_bai(tmp_path, monkeypatch):
    monkeypatch.setattr(ps, "_chay_ffmpeg", lambda *a, **k: False)
    anh = tmp_path / "a.jpg"
    anh.write_bytes(b"x")
    assert ps.dong_nhan_ai(str(anh), "SAFE") is False, (
        "trả True khi chưa đóng được nhãn là nói dối phía trên")


# -- 6. Lý do không-thử-lại-được phải tới tận người dùng (C2) ----------------

def test_tinh_nang_dang_tat_thi_dung_ngay_khong_thu_tiep(cam_may_chu, tmp_path):
    """Thử tiếp năm bối cảnh nữa cũng ra đúng câu trả lời đó, mà người dùng
    lại nhận về "thử lại sau ít phút" — sai hẳn việc phải làm."""
    from autodub.saas_client import SaasError

    loi = SaasError("Tính năng dựng ảnh sản phẩm đang tắt.",
                    code="IMAGE_STAGE_OFF", status=409)
    khach = _KhachGia(no_khi_dung=loi)

    with pytest.raises(SaasError, match="đang tắt"):
        ps.dung_boi_canh(str(cam_may_chu), ["ban_go", "gio_qua", "nen_studio"],
                         str(tmp_path / "ra"), khach=khach)
    assert len(khach.da_dung) == 1, "đã biết là tắt mà vẫn gọi tiếp"


def test_may_chua_duoc_phep_chay_thu_cung_dung_ngay(cam_may_chu, tmp_path):
    from autodub.saas_client import SaasError

    khach = _KhachGia(no_khi_dung=SaasError(
        "chưa mở cho máy này.", code="IMAGE_STAGE_CALIBRATION", status=409))
    with pytest.raises(SaasError):
        ps.dung_boi_canh(str(cam_may_chu), ["ban_go", "gio_qua"],
                         str(tmp_path / "ra"), khach=khach)
    assert len(khach.da_dung) == 1


def test_truc_trac_nhat_thoi_thi_VAN_thu_boi_canh_con_lai(cam_may_chu, tmp_path):
    """Ranh giới ngược lại: lỗi mạng thì đừng bỏ cả mẻ."""
    from autodub.saas_client import SaasError

    khach = _KhachGia(no_khi_dung=SaasError("máy chủ bận", code="AI_UNAVAILABLE",
                                            status=503))
    phien = ps.dung_boi_canh(str(cam_may_chu), ["ban_go", "gio_qua"],
                             str(tmp_path / "ra"), khach=khach)
    assert len(khach.da_dung) == 2, "lỗi nhất thời mà đã bỏ luôn bối cảnh sau"
    assert phien.ket_qua == []
