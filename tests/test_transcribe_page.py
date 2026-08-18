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
    class _W:
        def __init__(self, *a, **k): ...
        log = progress = finished_ok = failed = None
        def start(self): goi["chay"] = True
        def isRunning(self): return False

    goi = {}

    class _Sig:
        def connect(self, *_a): ...

    _W.log = _W.progress = _W.finished_ok = _W.failed = _Sig()
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

    page._on_done(_KQ())
    assert "2 câu" in page.status.text()
    assert page.btn_open.isEnabled()
