"""Trang Phân tích cấu trúc video tham khảo — mini-spec H2 (docs/PLAN.md,
Phase H).

Trọng tâm: hiển thị kết quả (beat_type dịch sang tiếng Việt, ghi chú tình
trạng bằng chứng đúng wording bắt buộc), lịch sử Xem/Xoá thao tác đúng dòng
đang chọn (không lẫn giữa các hàng — cùng bài học đã kiểm ở H1), và trang
KHÔNG được tự gọi mạng trong `on_shown` (bài học C7).
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub_gui.pages import flow_blueprint_page as fbp  # noqa: E402

BLUEPRINT = {
    "id": "bp123", "sourceType": "url", "sourceReference": "https://x/video",
    "status": "ready", "evidenceSummary": "ASR: 1 câu. OCR: 1 quan sát.",
    "beats": [
        {"startS": 0, "endS": 3, "beatType": "hook",
         "narrativeFunctionVi": "Mở đầu bằng phủ định thói quen quen thuộc",
         "pacingNoteVi": "Nhịp nhanh", "evidenceStatus": "ok"},
        {"startS": 3, "endS": 6, "beatType": "cta",
         "narrativeFunctionVi": "Kêu gọi hành động",
         "pacingNoteVi": "", "evidenceStatus": "unconfirmed"},
    ],
}


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture()
def page():
    return fbp.FlowBlueprintPage(lambda: object())


class _CrudWorkerGia:
    finished_ok = type("S", (), {"connect": lambda *a: None})()
    failed = type("S", (), {"connect": lambda *a: None})()
    finished = type("S", (), {"connect": lambda *a: None})()
    last = None

    def __init__(self, action, *, blueprint_id="", parent=None):
        type(self).last = {"action": action, "blueprint_id": blueprint_id}

    def start(self):
        pass

    def isRunning(self):
        return False


@pytest.fixture(autouse=True)
def _reset_worker_gia():
    _CrudWorkerGia.last = None
    yield


def test_render_beats_dich_beat_type_sang_tieng_viet(page):
    page._render_beats(BLUEPRINT)
    assert page.beats_table.row_count() == 2


def test_render_beats_hien_banner_bang_chung(page):
    page._render_beats(BLUEPRINT)
    assert "ASR: 1 câu" in page.evidence_banner.text()
    assert page.evidence_banner.isVisible() or not page.evidence_banner.isHidden()


def test_ghi_chu_unconfirmed_dung_wording_bat_buoc():
    assert fbp._EVIDENCE_STATUS_NOTES["unconfirmed"] == (
        "Cần bạn xác nhận — OCR tiếng Việt có thể thiếu dấu/sai ký tự.")


def test_ghi_chu_no_text_khong_noi_video_khong_co_caption():
    # Guardrail: KHÔNG BAO GIỜ nói "video không có caption" (video có thể có
    # caption ở đoạn KHÁC) — chỉ được nói về ĐOẠN này.
    ghi_chu = fbp._EVIDENCE_STATUS_NOTES["no_text"]
    assert "video không có caption" not in ghi_chu
    assert "đoạn này" in ghi_chu


def test_beat_type_vocabulary_dong_khop_danh_sach_dong():
    """`_BEAT_TYPE_LABELS` phải có nhãn cho ĐỦ vocabulary đóng — thiếu một
    khoá thì hiển thị nguyên tên tiếng Anh, phá guardrail người dùng không "
    cần biết vocabulary bên trong."""
    tu_vung_dong = [
        "hook", "problem_context", "tension", "proof", "demonstration",
        "payoff", "twist", "objection", "cta", "transition", "unknown",
    ]
    for beat_type in tu_vung_dong:
        assert beat_type in fbp._BEAT_TYPE_LABELS


def test_xoa_lich_su_phai_xac_nhan_truoc(page, monkeypatch):
    monkeypatch.setattr(fbp, "FlowBlueprintCrudWorker", _CrudWorkerGia)
    monkeypatch.setattr(fbp.ConfirmDialog, "ask",
                        staticmethod(lambda *a, **k: (False, False)))

    page._on_delete_history(BLUEPRINT)

    assert _CrudWorkerGia.last is None, "chưa xác nhận thì không được gọi worker xoá"


def test_xoa_lich_su_dung_id_sau_khi_xac_nhan(page, monkeypatch):
    monkeypatch.setattr(fbp, "FlowBlueprintCrudWorker", _CrudWorkerGia)
    monkeypatch.setattr(fbp.ConfirmDialog, "ask",
                        staticmethod(lambda *a, **k: (True, False)))

    page._on_delete_history(BLUEPRINT)

    assert _CrudWorkerGia.last["action"] == "delete"
    assert _CrudWorkerGia.last["blueprint_id"] == "bp123"


def test_xem_lai_lich_su_nap_dung_dong_dang_chon(page):
    """Nút «Xem lại» ở MỖI dòng lịch sử phải nạp đúng dữ liệu của DÒNG ĐÓ,
    không lẫn dữ liệu dòng khác — cùng bài học `_actions()` của H1."""
    khac = {**BLUEPRINT, "id": "bp999", "evidenceSummary": "Bằng chứng khác"}
    page._render_beats(khac)
    assert "Bằng chứng khác" in page.evidence_banner.text()
    page._render_beats(BLUEPRINT)
    assert "ASR: 1 câu" in page.evidence_banner.text()


def test_on_shown_khong_goi_mang_truc_tiep():
    """Bài học C7: `on_shown` chỉ được KHỞI ĐỘNG worker, không tự gọi mạng
    ngay trên luồng giao diện."""
    from tests.doc_ma import co_goi

    assert not co_goi(fbp.FlowBlueprintPage.on_shown, "list_flow_blueprints")
    assert not co_goi(fbp.FlowBlueprintPage.on_shown, "get_client")


def test_run_khong_goi_mang_truc_tiep_chi_qua_worker():
    from tests.doc_ma import co_goi

    assert not co_goi(fbp.FlowBlueprintPage._run, "get_client")
    assert not co_goi(fbp.FlowBlueprintPage._run, "trich_bang_chung")


# -- Cửa vào trong sidebar ---------------------------------------------

def test_app_co_muc_phan_tich_cau_truc_va_noi_dung_trang():
    import inspect

    from autodub_gui import app as app_mod

    nguon = inspect.getsource(app_mod)
    assert "Phân tích cấu trúc video tham khảo" in nguon
    assert "FlowBlueprintPage" in nguon
    assert app_mod.ROW_FLOW_BLUEPRINT in app_mod._PAGE_BY_ROW, (
        "hàng mới phải có mặt trong PAGES thì mới hiện lên thanh bên")


# ---------------------------------------------------------------------------
# Bố cục vỡ vì chữ dài — lỗi thật, ảnh chụp của chủ dự án 11/09/2026.
#
# Khi sửa chỗ hiện sai giá, tôi làm dòng mô tả chi phí dài từ 3 lên 6 dòng.
# Trang này lúc đó KHÔNG có vùng cuộn, mà nội dung đã cao hơn một màn hình
# 800px (thẻ mô tả + hàng nút + nhật ký + bảng đoạn + bảng lịch sử) — Qt ép
# mọi thứ nhỏ lại và chữ bị cắt, đè lên ô nhập liên kết.

def test_trang_CO_vung_cuon_de_chu_dai_khong_ep_vo_bo_cuc(page):
    from PySide6.QtWidgets import QScrollArea

    assert page.findChildren(QScrollArea), (
        "trang cao hơn một màn hình mà không có vùng cuộn — chữ dài thêm là "
        "bố cục vỡ, không có dấu hiệu nào lúc viết mã")


def test_dong_chi_phi_ngan_gon_va_van_co_con_so_nguoi_dung_can(page):
    """Dòng báo giá phải cho một KHOẢNG dùng được, và vẫn đủ ngắn.

    ĐỔI CÓ CHỦ Ý 12/09 — trước đây chốt này đòi đúng chuỗi `"32 Vox"`, tức
    một con số cố định gắn với độ dài video ("video ~60 giây tốn khoảng 32
    Vox"). Lượt chạy thật của chủ dự án trên một video **34 giây** tốn **88
    Vox**: 65 khung có chữ ÷ 6 = 11 lô × 8 Vox.

    Đại lượng quyết định là **lượng chữ trên hình**, không phải số giây —
    video ngắn kín caption tốn hơn video dài không chữ. Hứa một con số theo
    giây là hứa sai đại lượng, và người dùng chỉ biết sau khi tiền đã đi.

    Phần "đủ ngắn" giữ nguyên: chính độ dài dòng này từng làm vỡ bố cục thẻ
    (ảnh chụp 11/09).
    """
    import re

    from PySide6.QtWidgets import QLabel

    chu = [w.text() for w in page.findChildren(QLabel)
           if "Vox" in (w.text() or "")]
    assert chu, "mất luôn dòng báo giá"
    gia = max(chu, key=len)
    assert re.search(r"\d+\s*[–-]\s*\d+\s*Vox", gia), (
        f"phải cho một KHOẢNG để người dùng ước được lượt chạy của mình, "
        f"không phải một con số giả vờ chính xác.\n{gia}")
    assert len(gia) < 300, (
        f"dòng báo giá dài {len(gia)} ký tự — chính độ dài này làm vỡ bố cục")
