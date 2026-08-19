"""V89 giai đoạn 2 — bốn tác vụ còn lại và ba chỗ bấm thật.

Nguyên tắc giữ nguyên từ giai đoạn 1: app gửi TÊN tác vụ, mọi kết quả kèm lý
do, và hỏng thì người dùng vẫn làm việc bình thường được (trợ lý là lớp bồi
thêm, không phải đường chính).
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub.config import Settings  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# -- 1. Lời báo lỗi: hỏng trợ lý KHÔNG được dựng thành sự cố -----------------

@pytest.mark.parametrize("loi,phai_co", [
    ("Chưa cấu hình máy chủ VoxDub.", "Cài đặt"),
    ("INSUFFICIENT_CREDIT: không đủ Vox", "vẫn dùng bình thường"),
    ("read timeout", "thử lại"),
    ("chuyện lạ chưa từng thấy", "làm tiếp bình thường"),
])
def test_loi_tro_ly_noi_ro_con_dung_duoc_gi(loi, phai_co):
    from autodub_gui.dub_constants import friendly_assist_error

    ra = friendly_assist_error(loi)
    assert phai_co.lower() in ra.lower()
    for cam in ("exception", "traceback", "http", "500", "assist"):
        assert cam not in ra.lower(), f"lọt từ kỹ thuật: {cam}"


# -- 2. Worker chung ---------------------------------------------------------

def test_chua_co_tai_khoan_thi_khong_goi_ra_ngoai(qapp, monkeypatch):
    from autodub_gui.workers import AssistWorker

    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: False)
    monkeypatch.setattr("autodub.saas_client.get_client",
                        lambda: pytest.fail("chạy thuần trên máy mà vẫn gọi ra ngoài"))
    nhan = []
    w = AssistWorker("video_summary", {"transcript": "x"})
    w.failed.connect(nhan.append)
    w.run()
    assert nhan and "Cài đặt" in nhan[0]


def test_may_chu_tra_rong_thi_bao_that_bai_chu_khong_im(qapp, monkeypatch):
    from autodub_gui.workers import AssistWorker

    class _Khach:
        def assist(self, *a, **k):
            return []

    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: _Khach())
    monkeypatch.setattr("autodub.saas_client.new_job_id", lambda: "j-12345678")
    nhan = []
    w = AssistWorker("video_summary", {"transcript": "x"})
    w.failed.connect(nhan.append)
    w.finished_ok.connect(lambda r: pytest.fail("rỗng mà báo thành công"))
    w.run()
    assert nhan


# -- 3. Ba chỗ bấm thật ------------------------------------------------------

def test_trang_chep_loi_co_nut_tom_tat(qapp):
    from autodub_gui.pages.transcribe_page import TranscribePage

    trang = TranscribePage(lambda: Settings())
    assert trang.btn_tom_tat.text() == "Tóm tắt video"
    # Chưa chép lời thì không có gì để tóm tắt — nút phải tắt.
    assert not trang.btn_tom_tat.isEnabled()


def test_tom_tat_hien_ca_ban_tom_va_tu_khoa(qapp):
    from autodub_gui.pages.transcribe_page import TranscribePage

    trang = TranscribePage(lambda: Settings())
    dong = []
    trang.log.append_log = lambda text, level=20: dong.append(text)
    trang._hien_tom_tat([
        {"value": "Video hướng dẫn nấu phở bò.", "reason": "tóm tắt"},
        {"value": "xương ống", "reason": "hai ký xương ống"},
        {"value": "nước dùng", "reason": "nước dùng mới trong"},
    ])
    assert any("Tóm tắt:" in d for d in dong)
    assert any("xương ống" in d and "nước dùng" in d for d in dong)


def test_loi_thoai_qua_ngan_thi_khong_ton_vox(qapp, monkeypatch):
    from autodub_gui.pages.transcribe_page import TranscribePage

    trang = TranscribePage(lambda: Settings())
    trang._loi_thoai_gan_nhat = ["chào"]
    monkeypatch.setattr("autodub_gui.workers.AssistWorker",
                        lambda *a, **k: pytest.fail("vài chữ mà vẫn gọi trợ lý"))
    trang._tom_tat_video()


def test_editor_co_nut_rut_gon_tren_tung_dong(qapp):
    from autodub_gui.pages.editor_panels import SegmentRow, SubtitleListPanel

    assert hasattr(SegmentRow, "tighten_requested")
    assert hasattr(SubtitleListPanel, "tighten_requested")


def test_cau_da_doc_kip_thi_khong_goi_tro_ly(qapp, monkeypatch):
    """Rút gọn một câu vốn đã vừa vặn là tốn Vox vô ích."""
    from autodub_gui.pages.editor_page import EditorPage

    trang = EditorPage(lambda: Settings())
    trang._segments = [{"id": 1, "text_vi": "Câu ngắn.", "start": 0.0, "end": 9.0}]
    monkeypatch.setattr("autodub_gui.workers.AssistWorker",
                        lambda *a, **k: pytest.fail("câu đã kịp mà vẫn gọi"))
    trang._tighten_one(1)


def test_dien_quy_uoc_dich_vao_dung_o(qapp):
    from autodub_gui.pages.editor_panels import OverviewPanel

    panel = OverviewPanel()
    panel.fill_context_suggestion([
        {"value": "mình – các bạn", "reason": "người nói xưng mình"},
        {"value": "小米 = Xiaomi", "reason": "lặp nhiều lần"},
        {"value": "老板 = ông chủ", "reason": "lặp nhiều lần"},
    ])
    assert panel._ctx_fields["pronouns"].toPlainText() == "mình – các bạn"
    thuat_ngu = panel._ctx_fields["glossary"].toPlainText()
    assert "小米 = Xiaomi" in thuat_ngu and "老板 = ông chủ" in thuat_ngu


def test_khong_tu_luu_quy_uoc_dich(qapp):
    """Quy ước dịch sai còn tệ hơn không có — nó áp cho MỌI tập sau. Người
    dùng phải đọc rồi tự bấm Lưu."""
    from autodub_gui.pages.editor_panels import OverviewPanel

    panel = OverviewPanel()
    da_luu = []
    panel.context_saved.connect(da_luu.append)
    panel.fill_context_suggestion([{"value": "tôi – anh", "reason": "x"}])
    assert not da_luu


def test_giu_lai_thuat_ngu_nguoi_dung_da_go(qapp):
    from autodub_gui.pages.editor_panels import OverviewPanel

    panel = OverviewPanel()
    panel._ctx_fields["glossary"].setPlainText("有的 = có")
    panel.fill_context_suggestion([{"value": "小米 = Xiaomi", "reason": "x"}])
    thuat_ngu = panel._ctx_fields["glossary"].toPlainText()
    assert "有的 = có" in thuat_ngu, "không được xoá thứ người dùng đã gõ"
    assert "小米 = Xiaomi" in thuat_ngu
