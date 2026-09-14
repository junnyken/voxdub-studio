"""RS-10, RS-14, RS-15, RS-17, RS-19 — nhóm rà soát Phase H phía Python.

Xem `docs/BACKLOG_PHASE_H.md`. Mỗi mục đã được kiểm chứng độc lập trước khi
sửa; hai mục (RS-13, RS-14) hoá ra bị mô tả quá — ghi lại đúng mức thật ở
backlog thay vì sửa theo lời mô tả.
"""
from __future__ import annotations

import os

import pytest


# ------------------------------------------------------------------ RS-10 ---

def test_danh_sach_hong_van_la_list_nhung_mang_ly_do():
    from autodub.saas_client import DanhSachCoLoi

    hong = DanhSachCoLoi.hong("Không kết nối được máy chủ")
    assert isinstance(hong, list), "đổi kiểu trả về là làm hỏng 4 chỗ gọi cũ"
    assert list(hong) == [] and len(hong) == 0
    assert hong.loi == "Không kết nối được máy chủ"

    binh_thuong = DanhSachCoLoi([{"id": "a"}])
    assert binh_thuong.loi == "", "hỏi được thì không có lý do lỗi nào"

    rong_that = DanhSachCoLoi([])
    assert rong_that.loi == "", "rỗng THẬT khác rỗng vì hỏng — đây là cả mini-spec"


def test_list_tra_ve_danh_sach_mang_loi_khi_mat_mang(monkeypatch):
    from autodub import saas_client

    c = saas_client.SaasClient()

    def _no(*a, **kw):
        raise saas_client.SaasError("mạng đứt")
    monkeypatch.setattr(c, "_request", _no)

    for ten in ("list_brand_profiles", "list_flow_blueprints", "list_brand_scripts"):
        ds = getattr(c, ten)()
        assert ds == [], f"{ten} phải vẫn trả rỗng, không được ném"
        assert getattr(ds, "loi", ""), f"{ten} nuốt mất lý do hỏng"


def test_bang_phan_biet_rong_that_voi_rong_vi_hong():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from autodub_gui.ui.table import Column, DataTable

    bang = DataTable([Column("A", stretch=True)])

    bang.clear_rows()
    bang.auto_state()
    assert bang.currentWidget() is bang.empty

    bang.clear_rows()
    bang.auto_state("Không kết nối được máy chủ")
    assert bang.currentWidget() is bang.error, (
        "mất mạng mà hiện 'chưa có mục nào' là để người dùng đi tạo lại thứ "
        "họ đang có")

    # Có dữ liệu cũ thì vẫn cho xem, đừng thay bằng màn hình lỗi trắng trơn.
    bang.add_row()
    bang.auto_state("vẫn đang hỏng")
    assert bang.currentWidget() is bang.table


def test_BAY_or_rong_vut_mat_ly_do():
    """Chốt đúng cái bẫy đã suýt làm cả bản vá RS-10 thành vô nghĩa.

    `DanhSachCoLoi.hong(...)` RỖNG, mà rỗng là falsy — nên `ket or []` trả về
    một `list` trần và mất sạch `.loi`. `list(ket)` cũng vậy. Cả hai lối viết
    đó đều đang có thật trong ba trang lúc bắt đầu sửa.
    """
    from autodub.saas_client import DanhSachCoLoi

    ket = DanhSachCoLoi.hong("mạng đứt")
    assert getattr(ket or [], "loi", "") == "", "đây chính là cái bẫy"
    assert getattr(list(ket), "loi", "") == "", "và đây là biến thể của nó"
    # Lối viết đã dùng trong ba trang:
    giu = ket if isinstance(ket, list) else []
    assert getattr(giu, "loi", "") == "mạng đứt"


@pytest.mark.parametrize("tep,bien", [
    ("autodub_gui/pages/flow_blueprint_page.py", "_history"),
    ("autodub_gui/pages/brand_script_page.py", "_scripts"),
    ("autodub_gui/pages/brand_profile_page.py", "_profiles"),
])
def test_ba_trang_khong_dung_lai_loi_viet_lam_mat_ly_do(tep, bien):
    """Chốt CHỖ GÁN, không chỉ chốt hàm — chỗ gán mới là nơi `.loi` bị vứt."""
    tho = open(tep, encoding="utf-8").read()
    assert f"self.{bien} = ket or []" not in tho, (
        f"{tep}: `ket or []` vứt mất `.loi` vì danh sách rỗng là falsy")
    assert f"self.{bien} = list(ket or [])" not in tho, (
        f"{tep}: `list(...)` đổi kiểu nên cũng mất `.loi`")
    assert f'auto_state(getattr(self.{bien}, "loi", ""))' in tho, (
        f"{tep}: lấy được lý do rồi mà không truyền xuống bảng thì vô ích")


# ------------------------------------------------------------------ RS-14 ---

def test_doc_chu_may_chu_dung_may_khach_CHUNG():
    tho = open("autodub/media/doc_chu_may_chu.py", encoding="utf-8").read()
    assert "saas_client.get_client()" in tho
    assert "client = saas_client.SaasClient()" not in tho, (
        "dựng máy khách riêng ở đây là có một phiên HTTP thứ hai và không "
        "chịu ảnh hưởng của `reset_client()` — đổi địa chỉ máy chủ giữa chừng "
        "thì đường này trỏ một nơi, mọi đường khác trỏ nơi khác")


# ------------------------------------------------------------------ RS-15 ---

def test_cot_trang_thai_noi_tieng_viet():
    from autodub_gui.pages.flow_blueprint_page import _NHAN_TRANG_THAI

    for khoa in ("queued", "running", "ready", "failed"):
        assert khoa in _NHAN_TRANG_THAI, f"thiếu nhãn cho {khoa}"
        assert _NHAN_TRANG_THAI[khoa] != khoa


def test_trang_thai_LA_thi_hien_nguyen_van_khong_nuot():
    """Máy chủ thêm trạng thái mới mà bị nuốt thành 'Không rõ' là mất đúng
    manh mối cần cho lần gỡ lỗi sau."""
    from autodub_gui.pages.flow_blueprint_page import _NHAN_TRANG_THAI

    la = "trang_thai_moi_tinh"
    assert _NHAN_TRANG_THAI.get(la, la) == la


# ------------------------------------------------------------------ RS-17 ---

def test_loi_thoi_luong_noi_ro_DOAN_NAO():
    from autodub.product_video import _chuan_hoa_giay

    anh = ["a.jpg", "b.jpg", "c.jpg", "d.jpg"]
    with pytest.raises(ValueError) as e:
        _chuan_hoa_giay(anh, [2.0, 0.0, 3.0, 0.0])

    cau = str(e.value)
    assert "2" in cau and "4" in cau, (
        f"phải chỉ đúng đoạn 2 và 4 (đánh số từ 1), nhận được: {cau}")
    assert "lời đọc" in cau, "phải nói nguyên nhân thường gặp, không chỉ nói hỏng"


def test_thoi_luong_du_thi_khong_bao_oan():
    from autodub.product_video import _chuan_hoa_giay

    assert _chuan_hoa_giay(["a.jpg", "b.jpg"], [1.5, 2.5]) == [1.5, 2.5]


# ------------------------------------------------------------------ RS-19 ---

def test_don_anh_tam_sau_khi_kiem(tmp_path, monkeypatch):
    """Tệp tạm nằm ngay trong THƯ MỤC KẾT QUẢ, cạnh ảnh người dùng sẽ mở xem."""
    from autodub import story_image

    thu_muc = str(tmp_path)
    ra_path = os.path.join(thu_muc, "anh_1.jpg")
    open(ra_path, "wb").write(b"\xff\xd8\xff\xd9")

    tam = os.path.join(thu_muc, "_anh_kiem_tam.jpg")

    def _gia_thu_nho(nguon, thu_muc_ra, ten):
        open(os.path.join(thu_muc_ra, ten), "wb").write(b"x")
        return {"data": "eA==", "mimeType": "image/jpeg"}
    from autodub import saas_client

    monkeypatch.setattr(story_image, "thu_nho_de_gui", _gia_thu_nho)
    monkeypatch.setattr(story_image, "kiem_anh",
                        lambda *a, **kw: ("SAFE", "", True, 3))
    monkeypatch.setattr(story_image, "dong_nhan_chu", lambda *a, **kw: True)
    monkeypatch.setattr(story_image, "bam_tep", lambda p: "bam")
    # `is_configured`/`new_job_id` được nhập LƯỜI bên trong hàm, nên phải vá ở
    # module nguồn chứ không phải ở `story_image`.
    monkeypatch.setattr(saas_client, "is_configured", lambda: True)
    monkeypatch.setattr(saas_client, "new_job_id", lambda: "j" * 12)

    class _Khach:
        def story_image(self, goi_y, job_id=None, provider=""):
            return {"image": {"data": "eA==", "mimeType": "image/jpeg"}}

    story_image.sinh_mot_anh("một cái bếp", thu_muc, khach=_Khach(),
                             ten_tep="anh_1.jpg")

    assert not os.path.exists(tam), (
        "để lại `_anh_kiem_tam.jpg` trong thư mục kết quả là bắt người dùng "
        "đoán xem nó có phải ảnh của mình không")
    assert os.path.exists(ra_path), "ảnh THẬT thì không được đụng vào"
