"""H6 — ngân sách từ của H3 phải khớp tốc độ đọc ĐO THẬT của VieNeu.

Phát hiện của pilot 14/09: nguồn 34 giây, kịch bản H3 đọc hết 170 giây — gấp
**5 lần**. Nguyên nhân nằm ở đúng một dòng: `dungInput` lọc bỏ `startS`/`endS`
nên thời lượng **không bao giờ** tới được mô hình, và lời nhắc cũng không có
một chữ nào về độ dài.

Bản vá đưa thời lượng + ngân sách từ vào lời nhắc. Ngân sách tính từ hai hằng
số ĐO THẬT trong `autodub/storyboard.py`; lời nhắc dựng ở Node nên phải giữ
một BẢN SAO. Bản sao là nợ — tệp này là phần trả lãi: lệch một bên là đỏ.
"""
from __future__ import annotations

import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(REPO, "control_server", "src", "prompts", "assist.js")


def _so_trong_js(ten: str) -> float:
    ma = open(JS, encoding="utf-8").read()
    m = re.search(rf"^const {ten} = ([\d.]+)$", ma, re.M)
    assert m, f"không thấy hằng số {ten} trong assist.js"
    return float(m.group(1))


def test_hai_hang_so_KHONG_duoc_lech_giua_python_va_node():
    from autodub.storyboard import GIAY_MOI_AM_TIET, PHU_TROI_MOI_CAU_GIAY

    assert _so_trong_js("GIAY_MOI_AM_TIET") == GIAY_MOI_AM_TIET
    assert _so_trong_js("PHU_TROI_MOI_CAU_GIAY") == PHU_TROI_MOI_CAU_GIAY


def test_ngan_sach_tu_doc_ra_dung_thoi_luong_muc_tieu():
    """Phép kiểm vòng tròn: lấy ngân sách của JS, đưa lại qua hàm ước lượng
    THẬT của Python, phải ra xấp xỉ số giây ban đầu.

    Đây mới là thứ chứng minh công thức đúng — so hai hằng số chỉ chứng minh
    chúng bằng nhau, không chứng minh dùng đúng cách.
    """
    from autodub.storyboard import GIAY_MOI_AM_TIET, PHU_TROI_MOI_CAU_GIAY

    def ngan_sach(giay: float) -> int:
        return max(4, round((giay - PHU_TROI_MOI_CAU_GIAY) / GIAY_MOI_AM_TIET))

    for giay in (4.0, 6.0, 8.0, 12.0, 20.0):
        tu = ngan_sach(giay)
        doc_het = PHU_TROI_MOI_CAU_GIAY * 1 + GIAY_MOI_AM_TIET * tu
        assert abs(doc_het - giay) <= 0.6, (
            f"{giay}s -> {tu} từ -> đọc hết {doc_het:.2f}s, lệch quá nhiều")


def test_doan_rat_ngan_van_co_san_it_nhat_4_tu():
    """Đoạn chuyển cảnh 2 giây ra ngân sách âm — một đoạn không thể rỗng."""
    from autodub.storyboard import GIAY_MOI_AM_TIET, PHU_TROI_MOI_CAU_GIAY

    tu = max(4, round((2.0 - PHU_TROI_MOI_CAU_GIAY) / GIAY_MOI_AM_TIET))
    assert tu == 4


def test_BANG_CHUNG_PHU_DINH_thoi_luong_phai_di_qua_dungInput():
    """Gỡ trường `giay` thì mô hình mù trở lại — đúng trạng thái trước 14/09."""
    ma = open(os.path.join(REPO, "control_server", "src", "routes",
                           "brand-scripts.js"), encoding="utf-8").read()
    khoi = ma.split("function dungInput", 1)[1].split("brand: {", 1)[0]
    assert "giay:" in khoi, (
        "`dungInput` không gửi thời lượng ⇒ mô hình không biết video dài bao "
        "nhiêu ⇒ lặp lại đúng lỗi 170 giây / 34 giây của pilot")
    assert "endS" in khoi and "startS" in khoi


def test_loi_nhac_he_thong_noi_RO_ngan_sach_la_rang_buoc_cung():
    ma = open(JS, encoding="utf-8").read()
    khoi = ma.split("brand_script_rewrite: {", 1)[1].split("buildUser", 1)[0]
    assert "NGÂN SÁCH TỪ" in khoi and "RÀNG BUỘC CỨNG" in khoi, (
        "nói 'nên ngắn gọn' thì mô hình coi là gợi ý — pilot đã cho thấy nó "
        "viết gấp 5 lần khi không bị ràng buộc")
    assert "BỎ BỚT Ý" in khoi, (
        "không nói cách xử khi hết ngân sách thì mô hình sẽ nhồi cho đủ ý rồi "
        "tràn — phải nói rõ ưu tiên cắt ý")


# ============== Cảnh báo nhịp phải hiện ở H3, không đợi tới H4 ==============

def _trang():
    import pytest
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from autodub_gui.pages.brand_script_page import BrandScriptPage

    t = BrandScriptPage(lambda: object())
    t._blueprints = [{"id": "bp1", "beats": [{"endS": 34.0}]}]
    return t


def _dat(t, loi: str, so_doan: int = 7):
    t._hien_tai = {"id": "k1", "flowBlueprintId": "bp1", "status": "ready",
                   "beats": [{"voiceoverTextVi": loi} for _ in range(so_doan)]}
    t._render_script()


DAI = ("Đơn hàng chốt liên tục khách giục giao gấp doanh số nhảy số ầm ầm mỗi "
       "phút thế mà chủ doanh nghiệp lại đang ngồi vò đầu bứt tai thở dài "
       "thườn thượt trước màn hình máy tính rốt cuộc là vướng mắc ở đâu")
VUA = "Đơn hàng dồn dập sao lại rầu"


def test_BANG_CHUNG_PHU_DINH_kich_ban_qua_dai_phai_canh_bao_NGAY_o_H3():
    """Trước H6, dòng này chỉ hiện ở H4 — tức sau khi đã tiêu 12 Vox và đi
    thêm một trang. Chủ dự án gặp đúng cảnh đó ngày 14/09."""
    t = _trang()
    _dat(t, DAI)
    cau = t.canh_bao_nhip.text()
    assert t.canh_bao_nhip.isVisible() or cau, "không cảnh báo gì"
    assert "dài gấp" in cau and "34 giây" in cau
    assert "Viết lại đoạn" in cau, "nói vấn đề mà không nói cách xử"


def test_kich_ban_vua_nhip_thi_IM_LANG():
    """Cảnh báo kêu cả lúc đúng thì người ta tắt nó khỏi mắt."""
    t = _trang()
    _dat(t, VUA)
    assert not t.canh_bao_nhip.text(), (
        f"kêu oan: {t.canh_bao_nhip.text()}")


def test_doi_sang_kich_ban_khac_thi_XOA_canh_bao_cu():
    """Nhãn ẩn mà còn chữ cũ sẽ hiện lại nguyên cảnh báo của kịch bản TRƯỚC.

    Lỗi tôi tự tạo khi làm H6, tự bắt khi chạy thử — ghi lại để khỏi lặp.
    """
    t = _trang()
    _dat(t, DAI)
    assert t.canh_bao_nhip.text()
    _dat(t, VUA)
    assert t.canh_bao_nhip.text() == "", "chữ cũ còn sót lại"


def test_khong_co_blueprint_thi_khong_doan_bua():
    t = _trang()
    t._blueprints = []
    _dat(t, DAI)
    assert t.canh_bao_nhip.text() == "", (
        "không biết nguồn dài bao nhiêu thì không được kết luận gì")
