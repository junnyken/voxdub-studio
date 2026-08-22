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

from tests.doc_ma import co_goi, goi_truoc  # noqa: E402


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

def test_KHONG_goi_mang_tren_luong_giao_dien():
    """Gọi mạng thẳng từ chỗ bấm nút là treo cả cửa sổ.

    `kiem_lien_tuc` chờ tới 60 giây và thu nhỏ tới sáu ảnh bằng ffmpeg;
    `goi_y_kich_ban` chờ 45 giây. Cả hai phải nằm trong luồng nền — đây là
    lỗi tôi tự tạo ra ở C7 và tìm thấy khi rà lại.

    Hỏi CÂY CÚ PHÁP chứ không tìm chuỗi: bản đầu tìm `goi_y_kich_ban(` nên
    khớp luôn dòng `def _goi_y_kich_ban(self)` của chính phương thức đang
    đọc, và đỏ oan (mini-spec C8).
    """
    for ham in (psp.ProductScenePage._dung_video,
                psp.ProductScenePage._goi_y_kich_ban):
        for ten in ("kiem_lien_tuc", "goi_y_kich_ban"):
            assert not co_goi(ham, ten), \
                f"«{ten}» đang chạy trên luồng giao diện ({ham.__name__})"


def test_worker_moi_la_cho_goi_mang():
    from autodub_gui.workers import ProductVideoWorker, SceneScriptWorker

    assert co_goi(ProductVideoWorker.run, "kiem_lien_tuc")
    assert co_goi(SceneScriptWorker.run, "goi_y_kich_ban")


def test_canh_bao_lien_tuc_bay_ra_TRUOC_khi_ghep():
    """Cảnh báo sau khi video đã xong thì không giúp được ai."""
    from autodub_gui.workers import ProductVideoWorker

    assert goi_truoc(ProductVideoWorker.run, "kiem_lien_tuc", "dung_video")


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


# -- Thứ tự cảnh: kéo-thả và bỏ tích (C10) -----------------------------------
#
# Trước C10 thứ tự video là thứ tự ghi trong nhật ký — tức là thứ tự MÁY dựng
# ảnh, không phải thứ tự người bán muốn kể chuyện. Danh sách này là chỗ duy
# nhất người dùng nói được điều đó, nên nó cũng là chỗ dễ mở ra một đường
# vòng nhất: chỉ cần nó nạp nhầm một ảnh chưa kiểm là cả cổng tuân thủ vô
# nghĩa.

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QAbstractItemView  # noqa: E402

from autodub.product_video import AnhNguon  # noqa: E402


def _nguon(duong, boi_canh="ban_go", ket_luan="SAFE", da_kiem=True,
           ly_do="ổn"):
    return AnhNguon(duong, boi_canh, ket_luan, ly_do, da_kiem, True, "bam")


class _WorkerGhiLai:
    """Worker giả: giữ lại danh sách nhận được rồi thôi."""

    nhan: list = []

    class _TinHieu:
        def connect(self, *_a):
            pass

    def __init__(self, anh, ra, **_k):
        _WorkerGhiLai.nhan = anh
        self.xong = self._TinHieu()
        self.hong = self._TinHieu()
        self.canh_bao = self._TinHieu()

    def start(self):
        pass

    def isRunning(self):  # noqa: N802 — theo quy ước của Qt
        return False


@pytest.fixture()
def ghep(page, monkeypatch):
    """Trang đã mở nấc chạy thật, với worker giả ghi lại danh sách nguồn."""
    from autodub import product_video

    _WorkerGhiLai.nhan = []
    monkeypatch.setattr(psp, "ProductVideoWorker", _WorkerGhiLai)
    monkeypatch.setattr(product_video, "duoc_dung_video", lambda: (True, ""))

    def _dat_nhat_ky(anh):
        monkeypatch.setattr(product_video, "doc_nhat_ky", lambda *_a: anh)

    return page, _dat_nhat_ky


def test_danh_sach_thu_tu_chi_co_anh_dang_ban_duoc(ghep):
    trang, dat = ghep
    dat([_nguon("/tot.jpg"), _nguon("/lech.jpg", ket_luan="CONCEPT"),
         _nguon("/chua.jpg", da_kiem=False)])
    trang._nap_thu_tu("ra")
    duong = [trang.thu_tu.item(i).data(Qt.ItemDataRole.UserRole)
             for i in range(trang.thu_tu.count())]
    assert duong == ["/tot.jpg"], "ảnh không đăng bán được lọt vào danh sách"


def test_keo_tha_duoc_bat(page):
    assert (page.thu_tu.dragDropMode()
            == QAbstractItemView.DragDropMode.InternalMove)


def test_thu_tu_trong_danh_sach_quyet_dinh_thu_tu_video(ghep):
    trang, dat = ghep
    dat([_nguon("/1.jpg"), _nguon("/2.jpg"), _nguon("/3.jpg")])
    trang._nap_thu_tu("ra")

    # Kéo mục đầu xuống cuối — đúng thứ Qt làm khi người dùng thả chuột.
    trang.thu_tu.insertItem(2, trang.thu_tu.takeItem(0))

    trang._dung_video()
    assert [a.duong_dan for a in _WorkerGhiLai.nhan] == \
        ["/2.jpg", "/3.jpg", "/1.jpg"]


def test_bo_tich_thi_anh_do_khong_vao_video(ghep):
    trang, dat = ghep
    dat([_nguon("/1.jpg"), _nguon("/2.jpg")])
    trang._nap_thu_tu("ra")
    trang.thu_tu.item(0).setCheckState(Qt.CheckState.Unchecked)

    trang._dung_video()
    assert [a.duong_dan for a in _WorkerGhiLai.nhan] == ["/2.jpg"]


def test_bo_tich_het_thi_khong_ghep(ghep):
    """Bỏ tích hết mà vẫn ghép "cho đủ" là xuất một video người dùng
    không chọn."""
    trang, dat = ghep
    dat([_nguon("/1.jpg")])
    trang._nap_thu_tu("ra")
    trang.thu_tu.item(0).setCheckState(Qt.CheckState.Unchecked)

    trang._dung_video()
    assert not _WorkerGhiLai.nhan


def test_anh_da_chon_MA_NAY_KHONG_CON_DAT_thi_van_di_xuong(ghep):
    """Không âm thầm bỏ ảnh ra.

    Bỏ ra thì video xuất được, thiếu một cảnh, và không ai biết. Đi xuống
    thì lớp kiểm cuối chặn cả lượt và nói rõ ảnh nào, vì sao — đắt hơn một
    nhịp, nhưng người bán biết chuyện gì đã xảy ra.
    """
    trang, dat = ghep
    dat([_nguon("/1.jpg"), _nguon("/2.jpg")])
    trang._nap_thu_tu("ra")

    # Giữa lúc chọn và lúc bấm ghép, phán quyết của /1.jpg bị lật.
    dat([_nguon("/1.jpg", ket_luan="CONCEPT", ly_do="nhãn khác chữ"),
         _nguon("/2.jpg")])
    trang._dung_video()

    lech = [a for a in _WorkerGhiLai.nhan if a.duong_dan == "/1.jpg"]
    assert lech and not lech[0].dung_duoc
    assert lech[0].ly_do == "nhãn khác chữ"


def test_anh_bien_mat_khoi_nhat_ky_thi_di_xuong_kem_ly_do(ghep):
    trang, dat = ghep
    dat([_nguon("/1.jpg")])
    trang._nap_thu_tu("ra")
    dat([])  # nhật ký bị xoá/ghi đè giữa chừng

    trang._dung_video()
    assert len(_WorkerGhiLai.nhan) == 1
    mat = _WorkerGhiLai.nhan[0]
    assert not mat.dung_duoc
    assert "không còn trong nhật ký" in mat.ly_do


def test_chua_nap_danh_sach_thi_giu_nep_cu(ghep):
    """Mở app rồi ghép thẳng thư mục cũ: vẫn phải chạy, và vẫn chỉ lấy ảnh
    đăng bán được."""
    trang, dat = ghep
    dat([_nguon("/tot.jpg"), _nguon("/lech.jpg", ket_luan="CONCEPT")])
    trang._dung_video()
    assert [a.duong_dan for a in _WorkerGhiLai.nhan] == ["/tot.jpg"]


def test_dung_anh_xong_thi_danh_sach_hien_ra(ghep):
    trang, dat = ghep
    dat([_nguon("/tot.jpg")])
    trang._thu_muc_ket_qua = "ra"
    phien = Phien(anh_goc="a.jpg", thu_muc="ra")
    phien.ket_qua = [_ket()]
    trang._xong(phien)
    assert trang.thu_tu.count() == 1


def test_cua_so_thap_thi_KHONG_ep_be_o_nhap(page):
    """Cửa sổ thấp hơn nội dung thì phải CUỘN, không được ép các ô nhập.

    Bug thật, chủ dự án báo trên v3.6.1: các ô "Chế độ", "Ghi chú thêm",
    "Thư mục lưu ảnh" bị cắt ngang, trông như chồng lên nhau. Trang không nằm
    trong vùng cuộn, mà thẻ "Thứ tự cảnh" thêm ở C10 làm nội dung dài thêm —
    Qt hết chỗ thì ép mọi widget xuống dưới chiều cao tối thiểu của chúng.

    Đo bằng chính định nghĩa của lỗi: không widget nào được thấp hơn
    `sizeHint()` của nó.
    """
    from PySide6.QtWidgets import QComboBox, QLineEdit, QListWidget

    page.resize(1400, 700)
    page.show()
    QApplication.processEvents()

    ep = [f"{type(w).__name__} cao {w.height()}px < cần {w.sizeHint().height()}px"
          for loai in (QLineEdit, QComboBox, QListWidget)
          for w in page.findChildren(loai)
          if w.height() < w.sizeHint().height()]
    assert not ep, "widget bị ép bẹp: " + "; ".join(ep)


def test_trang_nam_trong_vung_cuon(page):
    """Chốt cấu trúc: gỡ vùng cuộn ra thì test trên chỉ đỏ ở đúng vài kích
    thước cửa sổ, còn đây đỏ ngay."""
    from PySide6.QtWidgets import QScrollArea

    assert page.findChildren(QScrollArea), "trang không có vùng cuộn"


def test_phan_hoi_nam_TREN_danh_sach_thu_tu(page):
    """Bấm nút xong phải thấy phản hồi, không phải cuộn đi tìm.

    Bản đầu của C10 chèn thẻ "Thứ tự cảnh" ngay dưới hàng nút, đẩy dòng trạng
    thái, khung Nhật ký và cả lưới ảnh xuống dưới đáy màn hình. Chủ dự án bấm
    "Dựng ảnh", chờ 14 giây, không thấy gì — trong khi máy chủ đã dựng xong
    ảnh và trừ 30 Vox.
    """
    page.resize(1400, 900)
    page.show()
    QApplication.processEvents()

    # `y()` tính theo widget cha, mà danh sách nằm trong một thẻ Card nên số
    # của nó nhỏ hơn hẳn dù đứng dưới. Phải quy về cùng một hệ toạ độ —
    # chính bẫy này làm bản đầu của test đỏ oan.
    def cao_do(w):
        return w.mapTo(page, w.rect().topLeft()).y()

    assert cao_do(page.status) < cao_do(page.thu_tu), "dòng trạng thái nằm dưới danh sách"
    assert cao_do(page.log) < cao_do(page.thu_tu), "khung Nhật ký nằm dưới danh sách"
    assert page.ket_qua.geometry().y() < cao_do(page.thu_tu), "lưới ảnh nằm dưới danh sách"


def test_chay_va_xong_deu_keo_man_hinh_toi_phan_hoi():
    """Đúng thứ tự khối vẫn chưa đủ khi cửa sổ thấp — phải kéo tới nơi."""
    from tests.doc_ma import co_goi

    for ham in (psp.ProductScenePage._chay, psp.ProductScenePage._xong):
        assert co_goi(ham, "_cuon_toi_trang_thai"), (
            f"{ham.__name__} không kéo màn hình tới chỗ có phản hồi")


def test_ly_do_hong_hien_LEN_MAN_HINH(page):
    """Máy chủ báo thành công, app báo hỏng, người dùng không biết vì sao —
    đã xảy ra ba lượt liên tiếp, mỗi lượt 30 Vox."""
    from autodub.product_scene import Phien

    phien = Phien(anh_goc="a.jpg", thu_muc="ra")
    phien.hong = [("ban_go", "mô hình từ chối vẽ nhãn")]
    page._xong(phien)

    assert "mô hình từ chối vẽ nhãn" in page.status.text()
    assert "mô hình từ chối vẽ nhãn" in page.log.toPlainText()


# -- Chọn nơi gọi mô hình (C17) ----------------------------------------------

def test_mac_dinh_la_TU_DONG(page):
    """Không chọn gì thì phải giữ nguyên nếp cũ, không tự ghim một nhà cung cấp."""
    assert page.noi_goi.current_key() == ""


def test_danh_sach_nap_ve_luon_giu_TU_DONG_o_dau(page):
    page._nap_noi_goi([("gemini-anh", "Gemini"), ("openai-anh", "OpenAI")])

    keys = [page.noi_goi.combo.itemData(i)
            for i in range(page.noi_goi.combo.count())]
    assert keys == ["", "gemini-anh", "openai-anh"]
    assert page.noi_goi.combo.itemText(1) == "Gemini", "phải hiện NHÃN, không phải tên máy"


def test_danh_sach_rong_thi_van_con_TU_DONG(page):
    """Hỏi máy chủ hỏng thì mất một tiện nghi, không được mất cả trang."""
    page._nap_noi_goi([])
    assert page.noi_goi.combo.count() == 1
    assert page.noi_goi.current_key() == ""


def test_lua_chon_di_xuong_worker(page, monkeypatch, tmp_path):
    nhan = {}

    class _WorkerGia:
        class _TinHieu:
            def connect(self, *_a):
                pass

        def __init__(self, *a, **k):
            nhan.update(k)
            self.tien_trinh = self._TinHieu()
            self.xong = self._TinHieu()
            self.hong = self._TinHieu()

        def start(self):
            pass

        def isRunning(self):  # noqa: N802 — theo quy ước của Qt
            return False

    anh = tmp_path / "a.jpg"
    anh.write_bytes(b"\xff\xd8\xff\xe0x")
    page.anh_goc.set_text(str(anh))
    page._nap_noi_goi([("openai-anh", "OpenAI")])
    page.noi_goi.combo.setCurrentIndex(1)
    monkeypatch.setattr(psp, "ProductSceneWorker", _WorkerGia)

    page._chay()

    assert nhan.get("noi_goi") == "openai-anh"


def test_hoi_danh_sach_KHONG_tren_luong_giao_dien():
    """Một lượt gọi mạng nhỏ vẫn là gọi mạng — bài học C7."""
    from tests.doc_ma import co_goi

    assert not co_goi(psp.ProductScenePage.on_shown, "danh_sach_noi_goi"), \
        "hỏi máy chủ ngay trong on_shown là treo cửa sổ lúc mở trang"

    from autodub_gui.workers import ImageProvidersWorker

    assert co_goi(ImageProvidersWorker.run, "danh_sach_noi_goi"), \
        "worker mới là chỗ được phép gọi mạng"


def test_ten_san_pham_di_vao_goi_y_kich_ban(page, monkeypatch, tmp_path):
    """Gợi ý kịch bản không nhìn thấy ảnh — tên sản phẩm là thứ DUY NHẤT nói
    cho nó biết đang bán cái gì."""
    from autodub import product_video

    nhan = {}

    class _WorkerGia:
        class _TinHieu:
            def connect(self, *_a):
                pass

        def __init__(self, anh, mo_ta, **_k):
            nhan["mo_ta"] = mo_ta
            self.xong = self._TinHieu()

        def start(self):
            pass

        def isRunning(self):  # noqa: N802 — theo quy ước của Qt
            return False

    monkeypatch.setattr(psp, "SceneScriptWorker", _WorkerGia)
    monkeypatch.setattr(product_video, "doc_nhat_ky",
                        lambda *_a: [_nguon("/1.jpg")])
    page.ten_san_pham.set_text("thức ăn hạt cho mèo Catsrang 400g")
    page.ghi_chu.set_text("đặt cạnh ly cà phê")

    page._goi_y_kich_ban()

    assert nhan["mo_ta"] == "thức ăn hạt cho mèo Catsrang 400g", (
        "ghi chú bối cảnh bị dùng thay tên sản phẩm — đúng lỗi C17 đi sửa")


def test_chua_dien_ten_thi_lui_ve_ghi_chu(page, monkeypatch):
    """Không có tên thì gửi ghi chú còn hơn gửi rỗng."""
    from autodub import product_video

    nhan = {}

    class _WorkerGia:
        class _TinHieu:
            def connect(self, *_a):
                pass

        def __init__(self, anh, mo_ta, **_k):
            nhan["mo_ta"] = mo_ta
            self.xong = self._TinHieu()

        def start(self):
            pass

        def isRunning(self):  # noqa: N802
            return False

    monkeypatch.setattr(psp, "SceneScriptWorker", _WorkerGia)
    monkeypatch.setattr(product_video, "doc_nhat_ky",
                        lambda *_a: [_nguon("/1.jpg")])
    page.ghi_chu.set_text("đặt cạnh ly cà phê")

    page._goi_y_kich_ban()

    assert nhan["mo_ta"] == "đặt cạnh ly cà phê"
