"""V71 — trang Chép lời trong app."""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub.config import Settings  # noqa: E402
from autodub_gui.pages import transcribe_page as tp  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _khong_goi_may_chu_that(monkeypatch):
    """Chặn mọi lượt gọi máy chủ từ bộ test này.

    C60: `test_dong_hong_kem_ly_do` kích đúng nhánh báo hỏng, mà nhánh đó khởi
    động luồng trợ lý gọi THẲNG máy chủ prod (hạn 30 giây). Test đơn vị đi ra
    internet là sai về nguyên tắc, và ở đây còn kéo theo hậu quả: luồng chưa
    xong lúc test kết thúc thì Qt abort cả tiến trình pytest — đã sập thật
    04-09, giữa một lượt chuẩn bị phát hành.
    """
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: False)


@pytest.fixture()
def page(tmp_path):
    settings = Settings()
    settings.output_dir = str(tmp_path)
    return tp.TranscribePage(lambda: settings)


def test_combo_tra_ve_KHOA_chu_khong_phai_nhan(page):
    """`LabeledCombo` nhận (nhãn, khoá). Viết ngược thì combo hiện ra khoá và
    `current_key()` trả về nhãn — lỗi đã mắc thật khi dựng trang này."""
    assert page.formats.current_key() == "txt,srt"
    assert page.language.current_key() == ""
    page.language.set_key("en")
    assert page.language.current_key() == "en"


def test_khong_nhap_gi_thi_khong_chay(page, monkeypatch):
    goi = {}
    monkeypatch.setattr(tp, "TranscribeWorker",
                        lambda *a, **k: goi.setdefault("dung", True))
    page._run()
    assert not goi, "ô rỗng thì không được khởi động worker"


def test_duong_dan_file_sai_bao_ngay_khong_doi_het_buoc_chuan_bi(page, monkeypatch):
    goi = {}
    monkeypatch.setattr(tp, "TranscribeWorker",
                        lambda *a, **k: goi.setdefault("dung", True))
    page.source.set_text("/khong/co/that.mp4")
    page._run()
    assert not goi, "file không tồn tại phải chặn TRƯỚC khi chạy"


def test_lien_ket_khong_bi_kiem_ton_tai_tren_dia(page, monkeypatch):
    """Liên kết không phải đường dẫn — kiểm `os.path.isfile` là chặn nhầm."""
    goi = {}

    class _Sig:
        def connect(self, *_a): ...

    class _W:
        log = progress = item_status = finished_ok = failed = _Sig()
        def __init__(self, *a, **k): ...
        def start(self): goi["chay"] = True
        def isRunning(self): return False

    monkeypatch.setattr(tp, "TranscribeWorker", _W)
    page.source.set_text("https://www.facebook.com/share/r/1EUSdYJeXN/")
    page._run()
    assert goi.get("chay") is True


def test_thu_muc_ket_qua_mac_dinh_nam_trong_output_dir(page, tmp_path):
    assert page._resolve_output_dir().startswith(str(tmp_path))
    assert page._resolve_output_dir().endswith("chep_loi")


def test_thu_muc_go_tay_thang_mac_dinh(page):
    page.output_dir.set_text("/tmp/rieng")
    assert page._resolve_output_dir() == "/tmp/rieng"


def test_bao_loi_noi_NGUYEN_VAN_chu_khong_nuot(page):
    page._on_failed("Video này yêu cầu đăng nhập")
    assert "Video này yêu cầu đăng nhập" in page.status.text(), \
        "nuốt thành 'có lỗi xảy ra' thì người dùng không biết đường xử lý"
    assert page.btn_run.isEnabled(), "hỏng rồi phải cho bấm lại"


def test_xong_thi_mo_duoc_thu_muc_ket_qua(page):
    class _KQ:
        segments = [{"text": "a"}, {"text": "b"}]
        outputs = {"txt": "/x/a.txt", "srt": "/x/a.srt"}

    class _M:
        status = "xong"
        result = _KQ()
        error = ""
        source = "/x/a.mp4"

    page._on_done([_M()])
    assert "2 câu" in page.status.text()
    assert page.btn_open.isEnabled()


# ------------------------------------------ V72: chọn nhiều file + nút Dừng
def test_tach_nhieu_nguon_bang_dau_gach_dung(page):
    """Đường dẫn Windows chứa cả dấu phẩy lẫn chấm phẩy; `|` là ký tự Windows
    CẤM đặt tên file nên không bao giờ đụng độ."""
    page.source.set_text(r"D:\a, b.mp4 | E:\c; d.mp3 | https://youtu.be/x")
    assert page._sources() == [r"D:\a, b.mp4", r"E:\c; d.mp3", "https://youtu.be/x"]


def test_bo_qua_muc_rong_khi_tach(page):
    page.source.set_text("  |  /tmp/a.mp4 |  ")
    assert page._sources() == ["/tmp/a.mp4"]


def test_thu_muc_la_dau_vao_hop_le(page, tmp_path, monkeypatch):
    goi = {}

    class _Sig:
        def connect(self, *_a): ...

    class _W:
        log = progress = item_status = finished_ok = failed = _Sig()
        def __init__(self, *a, **k): ...
        def start(self): goi["chay"] = True
        def isRunning(self): return False

    monkeypatch.setattr(tp, "TranscribeWorker", _W)
    page.source.set_text(str(tmp_path))
    page._run()
    assert goi.get("chay") is True, "chép lời cả thư mục là hợp lệ"


def test_nut_dung_chi_bat_khi_dang_chay(page):
    assert not page.btn_stop.isEnabled(), "chưa chạy thì không có gì để dừng"


def test_bam_dung_noi_DANG_dung_chu_khong_phai_da_dung(page, monkeypatch):
    class _W:
        def isRunning(self): return True
        def cancel(self): goi["huy"] = True

    goi = {}
    page._worker = _W()
    page.btn_stop.setEnabled(True)
    page._stop()

    assert goi.get("huy") is True
    assert "Đang dừng" in page.status.text(), \
        "mục đang chạy còn chạy nốt câu hiện tại — nói 'đã dừng' là nói sai"
    assert not page.btn_stop.isEnabled()


def _muc(status, so_cau=2, outputs=("txt",)):
    class _KQ:
        segments = [{"text": "x"}] * so_cau
        outputs_ = {f: f"/x/a.{f}" for f in outputs}
    kq = _KQ()
    kq.outputs = kq.outputs_

    class _M:
        pass
    m = _M()
    m.status = status
    m.result = kq if status == "xong" else None
    m.error = "lỗi gì đó" if status == "hong" else ""
    m.source = "/x/a.mp4"
    return m


def test_bao_cao_hang_loat_noi_ro_so_muc_hong(page):
    page._on_done([_muc("xong"), _muc("hong"), _muc("xong")])
    assert "hỏng 1" in page.status.text(), \
        "báo 'xong' trong khi có mục hỏng là nói dối"
    assert page.btn_run.isEnabled() and not page.btn_stop.isEnabled()


def test_bao_cao_khi_bi_huy_giu_nguyen_muc_da_xong(page):
    page._on_done([_muc("xong"), _muc("huy"), _muc("huy")])
    assert "Xong 1" in page.status.text()
    assert "đã huỷ 2" in page.status.text()


def test_mot_muc_duy_nhat_van_bao_kieu_cu(page):
    page._on_done([_muc("xong", so_cau=20, outputs=("txt", "srt"))])
    assert "Xong 20 câu" in page.status.text()
    assert "srt" in page.status.text()


# -- V73: dòng HỎNG phải kèm LÝ DO --------------------------------------------

def test_dong_hong_kem_ly_do(page):
    """Người dùng báo (2026-08-18, bản v3.4.0): chỉ thấy ``[1/1] HỎNG: <link>``
    trống trơn, không biết sai gì.

    Lý do có sẵn ở `BatchItem.error` nhưng bị vứt đi hai lần: tín hiệu
    `item_status` của `TranscribeWorker` không mang nó, còn cảnh báo của lõi
    thì bị `log_text.notice_for` lọc bỏ (thông báo lạ có URL). Dòng này là chỗ
    DUY NHẤT lý do lên tới được người dùng."""
    page._on_item(0, 1, "https://youtube.com/watch?v=x",
                  "hong", "Video này có khoá, cần đăng nhập.")
    text = page.log.toPlainText()
    assert "HỎNG" in text
    assert "Video này có khoá, cần đăng nhập." in text


def test_dong_xong_khong_bi_dinh_them_gi(page):
    page._on_item(0, 1, "/phim/tap1.mp4", "xong", "")
    assert page.log.toPlainText().strip().endswith("/phim/tap1.mp4")


def test_worker_chay_that_gui_kem_ly_do(tmp_path, monkeypatch):
    """Trang có chỗ nhận thì worker phải có chỗ gửi — `TranscribeWorker` từng
    là worker DUY NHẤT trong workers.py thiếu trường `detail` này.

    Chạy worker thật với một mục hỏng thật (không vá `item_status`), để nếu
    ai đó đổi lại tín hiệu về 4 tham số thì Qt báo lỗi ngay ở đây."""
    from autodub_gui import workers as w

    def _hong(sources, output_dir, settings, **kw):
        from autodub.transcribe_tool import BatchItem
        item = BatchItem(source=sources[0], status="hong",
                         error="Video này có khoá, cần đăng nhập.")
        kw["on_item"](0, 1, item)
        return [item]

    monkeypatch.setattr("autodub.transcribe_tool.transcribe_many", _hong)
    nhan: list[tuple] = []
    worker = w.TranscribeWorker(["https://youtube.com/watch?v=x"],
                                str(tmp_path), Settings())
    worker.item_status.connect(lambda *a: nhan.append(a))
    worker.run()          # chạy thẳng, không cần dựng luồng cho test

    assert nhan, "worker phải phát item_status"
    assert nhan[0][3] == "hong"
    assert nhan[0][4] == "Video này có khoá, cần đăng nhập.", \
        "tín hiệu phải mang theo lý do hỏng"


def test_luong_tro_ly_KHONG_gan_lam_con_cua_trang(page, monkeypatch):
    """C60 — bug thật, và nó giết cả tiến trình.

    Luồng trợ lý gọi máy chủ với hạn 30 giây. Gắn nó `parent=self` nghĩa là
    người dùng đóng trang (hoặc thoát app) trước khi lượt gọi xong thì Qt huỷ
    QThread lúc CÒN ĐANG CHẠY rồi gọi abort() — app chết ngay sau một thông
    báo lỗi, đúng lúc người dùng đang bực nhất.

    Đã sập thật 04-09 giữa một lượt chuẩn bị phát hành: trang bị thu gom cuối
    test, cả tiến trình pytest bị abort.
    """
    from autodub_gui import workers

    tao = []
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    monkeypatch.setattr(workers.ExplainErrorWorker, "start",
                        lambda self: tao.append(self))

    page._nho_tro_ly_giai_thich("lỗi gì đó")

    assert tao, "không khởi động luồng trợ lý"
    w = tao[0]
    assert w.parent() is None, (
        "luồng gọi mạng KHÔNG được làm con của trang — trang bị huỷ trước khi "
        "luồng xong là Qt abort cả tiến trình")
    assert w in workers._DANG_CHAY, (
        "không giữ tham chiếu thì QThread bị thu gom giữa chừng — cũng crash")


def test_luong_xong_thi_duoc_don_khoi_danh_sach():
    """Giữ tham chiếu mãi mãi là rò rỉ. Xong phải tự dọn.

    Dùng QThread CON có `run()` trả về ngay: QThread trần chạy vòng lặp sự kiện
    nên không bao giờ kết thúc (chính tôi vấp lúc viết test này).
    """
    from PySide6.QtCore import QThread

    from autodub_gui import workers

    class _XongNgay(QThread):
        def run(self):
            return

    w = _XongNgay()
    workers.giu_song(w)
    assert w in workers._DANG_CHAY
    w.start()
    assert w.wait(5000), "luồng thử không kết thúc"
    # `finished` phát ở luồng chủ — cho vòng lặp sự kiện một nhịp để chạy slot.
    QApplication.processEvents()
    assert w not in workers._DANG_CHAY, "xong rồi mà vẫn giữ tham chiếu"
