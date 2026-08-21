"""C1 — trang Ảnh sản phẩm.

Trọng tâm không phải bố cục mà là những chỗ giao diện có thể LÀM MỜ phán
quyết tuân thủ: nhãn hiển thị sai, câu tổng kết nói "xong hết" khi có ảnh
lệch, hoặc danh sách bối cảnh trôi khỏi danh sách máy chủ chấp nhận.
"""
from __future__ import annotations

import json
import os

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub.config import Settings  # noqa: E402
from autodub.product_scene import KetQua, Phien  # noqa: E402
from autodub_gui.pages import product_scene_page as psp  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture()
def page(tmp_path):
    settings = Settings()
    settings.output_dir = str(tmp_path)
    return psp.ProductScenePage(lambda: settings)


def _ket(boi_canh="ban_go", that="SAFE", da_kiem=True, ly_do="chỉ đổi nền"):
    return KetQua(duong_dan="/khong-co.jpg", boi_canh=boi_canh,
                  che_do_xin="SAFE", che_do_that=that, ly_do=ly_do,
                  da_kiem=da_kiem)


# -- Danh sách bối cảnh phải khớp máy chủ -----------------------------------

def test_boi_canh_khop_voi_may_chu():
    """Chọn một bối cảnh máy chủ không biết = mất tiền gọi rồi nhận lỗi."""
    js = open(os.path.join("control_server", "src", "prompts",
                           "product_scene.js"), encoding="utf-8").read()
    than = js.split("const BOI_CANH = {", 1)[1].split("\n}", 1)[0]
    tren_may_chu = {d.strip()[:-3] for d in than.splitlines()
                    if d.strip().endswith(": {")}
    trong_app = {k for k, _ in psp.BOI_CANH}
    assert trong_app == tren_may_chu, (
        "danh sách bối cảnh trong app lệch khỏi máy chủ")


def test_che_do_mac_dinh_la_giu_nguyen_san_pham(page):
    """Chế độ rủi ro phải là thứ người dùng CHỌN, không phải mặc định."""
    assert page.che_do.current_key() == "SAFE"


def test_nhan_che_do_noi_ro_hau_qua(page):
    """"CONCEPT" không nói cho người bán biết điều gì; câu cảnh báo thì có."""
    nhan = [n for n, k in psp._CHE_DO if k == "CONCEPT"][0]
    assert "KHÔNG đăng kèm" in nhan


# -- Chặn trước khi tốn tiền -------------------------------------------------

def test_khong_co_anh_thi_khong_khoi_dong_worker(page, monkeypatch):
    goi = {}
    monkeypatch.setattr(psp, "ProductSceneWorker",
                        lambda *a, **k: goi.setdefault("dung", True))
    page._chay()
    assert not goi


def test_anh_khong_ton_tai_thi_bao_ngay(page, monkeypatch):
    goi = {}
    monkeypatch.setattr(psp, "ProductSceneWorker",
                        lambda *a, **k: goi.setdefault("dung", True))
    page.anh_goc.set_text("/khong/co/thuc/anh.jpg")
    page._chay()
    assert not goi


def test_khong_chon_boi_canh_thi_khong_chay(page, monkeypatch, tmp_path):
    goi = {}
    monkeypatch.setattr(psp, "ProductSceneWorker",
                        lambda *a, **k: goi.setdefault("dung", True))
    anh = tmp_path / "a.jpg"
    anh.write_bytes(b"x")
    page.anh_goc.set_text(str(anh))
    for o in page._o_boi_canh.values():
        o.setChecked(False)
    page._chay()
    assert not goi


def test_chon_qua_nhieu_boi_canh_bi_chan(page, monkeypatch, tmp_path):
    """Mỗi ảnh là một lượt sinh + một lượt kiểm; chọn cả sáu là hoá đơn bất ngờ."""
    goi = {}
    monkeypatch.setattr(psp, "ProductSceneWorker",
                        lambda *a, **k: goi.setdefault("dung", True))
    anh = tmp_path / "a.jpg"
    anh.write_bytes(b"x")
    page.anh_goc.set_text(str(anh))
    for o in page._o_boi_canh.values():
        o.setChecked(True)
    page._chay()
    assert not goi, "vượt hạn mức mỗi lượt mà vẫn chạy"


# -- Hiển thị phán quyết -----------------------------------------------------

def test_anh_dat_hien_huy_hieu_dang_ban_duoc(page):
    the = page._the_anh(_ket())
    nhan = _cac_huy_hieu(the)
    assert nhan == ["Đăng bán được"]


def test_anh_lech_khong_bao_gio_hien_la_dang_ban_duoc(page):
    the = page._the_anh(_ket(that="CONCEPT", ly_do="nhãn khác chữ"))
    assert _cac_huy_hieu(the) == ["Chỉ để tham khảo"]


def test_anh_chua_kiem_duoc_hien_rieng_mot_nhan(page):
    """Gộp chung với "chỉ để tham khảo" thì người dùng tưởng ảnh có lỗi;
    sự thật là chưa ai kiểm — hai chuyện khác nhau, cách xử khác nhau."""
    the = page._the_anh(_ket(da_kiem=False, ly_do="không kiểm được"))
    assert _cac_huy_hieu(the) == ["Chưa kiểm được"]


def test_ly_do_hien_ra_cho_nguoi_dung(page):
    the = page._the_anh(_ket(that="CONCEPT", ly_do="nhãn khác chữ so với gốc"))
    chu = " ".join(w.text() for w in the.findChildren(type(page.status)))
    assert "nhãn khác chữ so với gốc" in chu


def _cac_huy_hieu(the):
    from autodub_gui.ui.badges import StatusBadge
    return [b.text() for b in the.findChildren(StatusBadge)]


# -- Câu tổng kết ------------------------------------------------------------

def test_tong_ket_khong_noi_xong_het_khi_co_anh_lech(page):
    phien = Phien(anh_goc="a.jpg", thu_muc="ra")
    phien.ket_qua = [_ket(), _ket("gio_qua", that="CONCEPT", ly_do="đổi nhãn")]
    page._xong(phien)
    chu = page.status.text()
    assert "1 ảnh đăng bán được" in chu
    assert "1 ảnh CHỈ để tham khảo" in chu


def test_tong_ket_khi_tat_ca_deu_dat(page):
    phien = Phien(anh_goc="a.jpg", thu_muc="ra")
    phien.ket_qua = [_ket(), _ket("gio_qua")]
    page._xong(phien)
    assert "đăng bán được" in page.status.text()
    assert "tham khảo" not in page.status.text()


def test_khong_dung_duoc_anh_nao_thi_noi_that(page):
    page._xong(Phien(anh_goc="a.jpg", thu_muc="ra"))
    assert "Không dựng được ảnh nào" in page.status.text()


def test_chay_lai_thi_xoa_ket_qua_cu(page):
    phien = Phien(anh_goc="a.jpg", thu_muc="ra")
    phien.ket_qua = [_ket(), _ket("gio_qua")]
    page._xong(phien)
    assert page.ket_qua.count() == 2
    page._xoa_ket_qua()
    assert page.ket_qua.count() == 0, (
        "ảnh lượt trước còn lại trên màn hình lượt sau = người dùng đọc "
        "phán quyết của ảnh khác")


# -- Dựng video ngắn (C6) ----------------------------------------------------

def test_nac_chua_mo_thi_khong_khoi_dong_worker_video(page, monkeypatch):
    """Kiểm nấc TRƯỚC khi đọc nhật ký: hỏi máy chủ là việc rẻ, còn để người
    dùng chọn xong ảnh rồi mới báo "chưa mở" là bắt họ làm không công."""
    from autodub import product_video

    goi = {}
    monkeypatch.setattr(psp, "ProductVideoWorker",
                        lambda *a, **k: goi.setdefault("dung", True))
    monkeypatch.setattr(product_video, "duoc_dung_video",
                        lambda: (False, "chưa mở"))
    monkeypatch.setattr(product_video, "doc_nhat_ky",
                        lambda *_a: pytest.fail("đọc nhật ký khi nấc chưa mở"))
    page._dung_video()
    assert not goi


def test_khong_co_anh_dat_thi_khong_ghep(page, monkeypatch):
    from autodub import product_video

    goi = {}
    monkeypatch.setattr(psp, "ProductVideoWorker",
                        lambda *a, **k: goi.setdefault("dung", True))
    monkeypatch.setattr(product_video, "duoc_dung_video", lambda: (True, ""))
    monkeypatch.setattr(product_video, "doc_nhat_ky", lambda *_a: [])
    page._dung_video()
    assert not goi


def test_chi_dua_anh_DAT_vao_video(page, monkeypatch, tmp_path):
    """Giao diện không được tự quyết danh sách nguồn."""
    from autodub import product_video
    from autodub.product_video import AnhNguon

    dat = AnhNguon(str(tmp_path / "tot.jpg"), "ban_go", "SAFE", "ổn",
                   True, True, "abc")
    lech = AnhNguon(str(tmp_path / "xau.jpg"), "gio_qua", "CONCEPT",
                    "lệch nhãn", True, True, "def")
    chua = AnhNguon(str(tmp_path / "chua.jpg"), "nen_studio", "SAFE",
                    "không kiểm được", False, True, "ghi")

    nhan = {}

    class _WorkerGia:
        """Worker giả: ghi lại danh sách nhận được rồi thôi."""

        class _TinHieu:
            def connect(self, *_a):
                pass

        def __init__(self, anh, ra, **_k):
            nhan["anh"] = anh
            self.xong = self._TinHieu()
            self.hong = self._TinHieu()
            self.canh_bao = self._TinHieu()

        def start(self):
            pass

        def isRunning(self):  # noqa: N802 — theo quy ước của Qt
            return False

    monkeypatch.setattr(psp, "ProductVideoWorker", _WorkerGia)
    monkeypatch.setattr(product_video, "duoc_dung_video", lambda: (True, ""))
    monkeypatch.setattr(product_video, "doc_nhat_ky", lambda *_a: [dat, lech, chua])
    page._dung_video()

    assert [a.boi_canh for a in nhan["anh"]] == ["ban_go"]


def test_bi_chan_thi_in_NGUYEN_VAN_ly_do(page):
    loi = ("Không xuất được video vì có ảnh không dùng để bán được — "
           "xau.jpg: nhãn khác chữ so với bản gốc")
    page._video_hong(loi)
    assert "xau.jpg" in page.status.text()
    assert "nhãn khác chữ" in page.status.text()


# -- Kiểm liên tục và gợi ý kịch bản (C7) ------------------------------------

def test_KHONG_goi_mang_tren_luong_giao_dien(tmp_path):
    """Gọi mạng thẳng từ chỗ bấm nút là treo cả cửa sổ.

    `kiem_lien_tuc` chờ tới 60 giây và thu nhỏ tới sáu ảnh bằng ffmpeg;
    `goi_y_kich_ban` chờ 45 giây. Cả hai phải nằm trong luồng nền — đây là
    lỗi tôi tự tạo ra ở C7 và tìm thấy khi rà lại.
    """
    import inspect

    than = (inspect.getsource(psp.ProductScenePage._dung_video)
            + inspect.getsource(psp.ProductScenePage._goi_y_kich_ban))
    # Tìm LƯỢT GỌI có tên mô-đun, không tìm trần tên hàm: `goi_y_kich_ban(`
    # khớp luôn dòng `def _goi_y_kich_ban(self)` của chính phương thức đang
    # đọc, và test đỏ oan.
    for ten in ("product_video.kiem_lien_tuc(", "product_video.goi_y_kich_ban("):
        assert ten not in than, f"«{ten}» đang chạy trên luồng giao diện"


def test_worker_moi_la_cho_goi_mang(tmp_path):
    import inspect

    from autodub_gui.workers import ProductVideoWorker, SceneScriptWorker

    assert "kiem_lien_tuc(" in inspect.getsource(ProductVideoWorker.run)
    assert "goi_y_kich_ban(" in inspect.getsource(SceneScriptWorker.run)


def test_canh_bao_lien_tuc_chi_IN_RA_khong_chan(page):
    """Ranh giới: cảnh báo, không phải chặn — hàm này chỉ ghi Nhật ký."""
    page._canh_bao_lien_tuc("ảnh 3 ám vàng")
    chu = page.log.toPlainText()
    assert "ảnh 3 ám vàng" in chu
    assert "vẫn" in chu, "phải nói rõ video vẫn ghép được"


def test_goi_y_kich_ban_chi_IN_RA_khong_dan_vao_video(page, monkeypatch, tmp_path):
    from autodub.product_video import AnhNguon

    page._anh_kich_ban = [AnhNguon(str(tmp_path / "a.jpg"), "ban_go", "SAFE",
                                   "ổn", True, True, "x")]
    monkeypatch.setattr(psp, "ProductVideoWorker",
                        lambda *a, **k: pytest.fail("gợi ý mà lại ghép video"))
    page._kich_ban_xong([("Ấm bụng mỗi sáng", "giữ 3 giây")])
    chu = page.log.toPlainText()
    assert "Ấm bụng mỗi sáng" in chu
    assert "tham khảo" in chu, "phải nói rõ đây chỉ là gợi ý"
