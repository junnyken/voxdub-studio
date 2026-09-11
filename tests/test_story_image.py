"""Ảnh minh hoạ sinh từ chữ — mini-spec H4d.

Chốt phải giữ: **ảnh chưa qua kiểm thì không được coi là dùng được**, và mọi
đường hỏng đều nghiêng về phía "không dùng được". Ảnh này sẽ nằm trong một
video bán hàng cạnh sản phẩm thật; đoán sai theo hướng an toàn chỉ mất một
tấm ảnh, đoán sai hướng kia là người bán mất tài khoản.
"""
from __future__ import annotations

import pytest

from autodub import story_image as si


class _KhachGia:
    """Máy chủ giả. `tra_kiem` là thứ tác vụ kiểm sẽ trả về."""

    def __init__(self, tra_kiem=None, loi_kiem=None, co_anh=True):
        self.tra_kiem = tra_kiem
        self.loi_kiem = loi_kiem
        self.co_anh = co_anh
        self.da_goi = []

    def story_image(self, brief, **kw):
        self.da_goi.append(("ve", brief))
        anh = {"mimeType": "image/png", "data": "QUJD"} if self.co_anh else {}
        return {"image": anh, "creditCharged": 30}

    def assist_day_du(self, task, input, **kw):
        """Máy chủ trả NGUYÊN gói, kể cả `creditCharged` — mini-spec H4d-0.

        Mỗi ảnh là HAI lượt tính tiền (vẽ 30 + kiểm 3); gộp làm một thì lúc
        lượt kiểm hỏng không nói được người dùng vừa mất bao nhiêu.
        """
        self.da_goi.append(("kiem", task))
        if self.loi_kiem:
            raise self.loi_kiem
        return {"results": self.tra_kiem, "creditCharged": 3}


@pytest.fixture()
def moi_truong(monkeypatch, tmp_path):
    """Nối mọi thứ ra ngoài về hàng giả — không gọi mạng, không chạy ffmpeg."""
    import autodub.saas_client as sc

    monkeypatch.setattr(sc, "is_configured", lambda: True)
    monkeypatch.setattr(sc, "new_job_id", lambda: "job-gia-0123456789")
    # Thu nhỏ ảnh cần ffmpeg — không phải thứ test này kiểm.
    monkeypatch.setattr(si, "thu_nho_de_gui",
                        lambda p, d, t: {"mimeType": "image/jpeg", "data": "eA=="})
    monkeypatch.setattr(si, "bam_tep", lambda p: "bam-gia")
    monkeypatch.setattr(si, "dong_nhan_chu", lambda p, c: True)
    return tmp_path


def _sinh(khach, moi_truong, **kw):
    return si.sinh_mot_anh("một gian bếp buổi sáng", str(moi_truong),
                           khach=khach, **kw)


# ------------------------------------------------- nghiêng về an toàn ------

def test_kiem_hong_thi_anh_KHONG_dung_duoc(moi_truong):
    k = _KhachGia(loi_kiem=RuntimeError("mạng lỗi"))
    ra = _sinh(k, moi_truong)
    assert ra.phan_quyet == "CO_SAN_PHAM"
    assert ra.da_kiem is False
    assert not ra.dung_duoc
    # Lý do phải mang nguyên văn nguyên nhân: "chưa kiểm được" một mình không
    # cho người dùng biết nên đợi mạng hay báo lỗi.
    assert "mạng lỗi" in ra.ly_do


def test_may_chu_khong_tra_ket_qua_kiem_thi_KHONG_dung_duoc(moi_truong):
    ra = _sinh(_KhachGia(tra_kiem=[]), moi_truong)
    assert ra.phan_quyet == "CO_SAN_PHAM"
    assert not ra.dung_duoc


def test_phan_quyet_la_thi_KHONG_dung_duoc(moi_truong):
    # Mô hình trả "OK", "YES", hay một câu văn — không cái nào là phán quyết.
    ra = _sinh(_KhachGia(tra_kiem=[{"value": "OK", "reason": "ổn"}]), moi_truong)
    assert ra.phan_quyet == "CO_SAN_PHAM"
    assert not ra.dung_duoc


def test_thay_san_pham_thi_KHONG_dung_duoc(moi_truong):
    k = _KhachGia(tra_kiem=[{"value": "CO_SAN_PHAM",
                             "reason": "có hộp giấy có nhãn ở góc phải"}])
    ra = _sinh(k, moi_truong)
    assert not ra.dung_duoc
    assert "hộp giấy" in ra.ly_do, "lý do phải tới được người dùng"


def test_dat_va_da_dong_nhan_thi_moi_dung_duoc(moi_truong):
    k = _KhachGia(tra_kiem=[{"value": "DAT", "reason": "chỉ có bối cảnh bếp"}])
    ra = _sinh(k, moi_truong)
    assert ra.dung_duoc
    assert ra.vox_ve == 30
    assert ra.vox_kiem == 3, "tiền lượt kiểm phải đọc từ máy chủ, không đoán"
    assert ra.vox == 33, "giá THẬT của một ảnh là 33 Vox, không phải 30"


# ------------------------------------------------------ nhãn bắt buộc ------

def test_dong_nhan_hut_thi_KHONG_dung_duoc(moi_truong, monkeypatch):
    # Chặt hơn C1 có chủ đích: ảnh C1 là ảnh sản phẩm THẬT của người bán, mất
    # nhãn thì nó vẫn là ảnh thật. Ảnh này 100% do máy vẽ — không nhãn là
    # không còn gì phân biệt nó với một khung hình quay thật.
    monkeypatch.setattr(si, "dong_nhan_chu", lambda p, c: False)
    k = _KhachGia(tra_kiem=[{"value": "DAT", "reason": "chỉ có bối cảnh"}])
    ra = _sinh(k, moi_truong)
    assert ra.phan_quyet == "DAT" and ra.da_kiem
    assert not ra.dung_duoc, "đóng nhãn hụt mà vẫn cho ghép vào video"


def test_bam_tinh_SAU_khi_dong_nhan(moi_truong, monkeypatch):
    """Tệp trên đĩa lúc đóng nhãn xong mới là tệp cuối cùng (mini-spec C6)."""
    thu_tu = []
    monkeypatch.setattr(si, "dong_nhan_chu",
                        lambda p, c: thu_tu.append("nhan") or True)
    monkeypatch.setattr(si, "bam_tep", lambda p: thu_tu.append("bam") or "b")
    _sinh(_KhachGia(tra_kiem=[{"value": "DAT", "reason": "ổn"}]), moi_truong)
    assert thu_tu == ["nhan", "bam"]


# ------------------------------------------------------- đường hỏng --------

def test_may_chu_khong_tra_anh_thi_nem_loi(moi_truong):
    with pytest.raises(RuntimeError, match="không trả về ảnh"):
        _sinh(_KhachGia(co_anh=False), moi_truong)


def test_chua_ket_noi_tai_khoan_thi_noi_ro(monkeypatch, tmp_path):
    import autodub.saas_client as sc
    monkeypatch.setattr(sc, "is_configured", lambda: False)
    with pytest.raises(RuntimeError, match="Cài đặt"):
        si.sinh_mot_anh("bếp", str(tmp_path))


# ---------------------------------------------------------- cả mẻ ---------

def test_mot_doan_hong_khong_giet_ca_me(moi_truong, monkeypatch):
    goi = {"n": 0}

    def _sinh_gia(goi_y, thu_muc, **kw):
        goi["n"] += 1
        if goi["n"] == 2:
            raise RuntimeError("mô hình từ chối vẽ")
        return si.AnhMinhHoa(duong_dan=f"/tmp/{goi['n']}.jpg", goi_y=goi_y,
                             phan_quyet="DAT", ly_do="ổn", da_kiem=True,
                             da_dong_nhan=True)

    monkeypatch.setattr(si, "sinh_mot_anh", _sinh_gia)
    me = si.sinh_nhieu_anh([(0, "a"), (1, "b"), (2, "c")], str(moi_truong))
    assert me.so_dung_duoc == 2
    assert [(h.chi_so, h.ly_do) for h in me.hong] == [(1, "mô hình từ chối vẽ")]
    # Máy chủ chỉ trừ tiền SAU khi vẽ xong, nên đoạn ném lỗi = chưa mất Vox.
    assert me.hong[0].vox == 0
    assert me.hong[0].thu_lai_duoc is True


def test_cua_dang_tat_thi_DUNG_ca_me_ngay(moi_truong, monkeypatch):
    # Thử tiếp năm đoạn nữa cũng ra đúng câu trả lời đó, mà người dùng lại
    # nhận về "thử lại sau ít phút" — sai hẳn việc phải làm (bài học C15).
    goi = {"n": 0}

    def _sinh_gia(goi_y, thu_muc, **kw):
        goi["n"] += 1
        e = RuntimeError("Tính năng dựng ảnh sản phẩm đang tắt.")
        e.code = "IMAGE_STAGE_OFF"
        raise e

    monkeypatch.setattr(si, "sinh_mot_anh", _sinh_gia)
    with pytest.raises(RuntimeError, match="đang tắt"):
        si.sinh_nhieu_anh([(0, "a"), (1, "b"), (2, "c")], str(moi_truong))
    assert goi["n"] == 1, "đã biết cửa đóng mà vẫn thử tiếp"


def test_ten_tep_theo_so_doan_de_tra_lai_duoc(moi_truong):
    k = _KhachGia(tra_kiem=[{"value": "DAT", "reason": "ổn"}])
    ra = si.sinh_mot_anh("bếp", str(moi_truong), ten_tep="doan_03.jpg", khach=k)
    assert ra.duong_dan.endswith("doan_03.jpg")


# -------------------------------------------------- gọi đúng tác vụ -------

def test_goi_dung_tac_vu_kiem_va_gui_dung_MOT_anh(moi_truong):
    k = _KhachGia(tra_kiem=[{"value": "DAT", "reason": "ổn"}])
    _sinh(k, moi_truong)
    assert ("kiem", "kiem_anh_minh_hoa") in k.da_goi
    assert [t for t, _ in k.da_goi] == ["ve", "kiem"], "phải sinh rồi mới kiểm"


def test_khong_dung_lai_cong_kiem_bao_bi_cua_C1(moi_truong):
    """`packaging_check` so ảnh mới với ảnh GỐC — ở đây không có ảnh gốc nào,
    nên nó sẽ không kiểm được gì mà vẫn trả về một phán quyết trông như thật.
    """
    k = _KhachGia(tra_kiem=[{"value": "DAT", "reason": "ổn"}])
    _sinh(k, moi_truong)
    assert not any(t == "packaging_check" for _, t in k.da_goi)


def test_nhan_dong_len_anh_noi_ro_la_anh_minh_hoa():
    assert "AI-generated" in si.NHAN, (
        "từ 13/5/2026 TikTok bắt buộc nhãn này cho nội dung AI")
    assert "minh hoa" in si.NHAN, "phải phân biệt được với ảnh sản phẩm thật"


def test_nhan_KHONG_dung_dau_tieng_viet():
    """Bộ chữ mặc định của ffmpeg trên máy người dùng không chắc có dấu tiếng
    Việt, mà một dòng nhãn vỡ chữ còn khó hiểu hơn là không có nhãn.
    """
    import unicodedata

    for ky_tu in si.NHAN:
        ten = unicodedata.name(ky_tu, "")
        assert "WITH" not in ten, f"«{ky_tu}» là chữ có dấu — {ten}"
