"""Mini-spec V29 (docs/PLAN.md, Phase G) — bảng "AI đã tự soát bản dịch"
trong trang Báo cáo chất lượng (`autodub_gui/pages/quality_page.py`).
Chạy headless (QT_QPA_PLATFORM=offscreen), cùng khuôn
`tests/test_recognize_step_warning.py`.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub_gui.pages.quality_page import QualityPage  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _page():
    return QualityPage(settings_provider=lambda: object())


def test_render_report_without_review_trace_no_crash_0_regression():
    """quality_report.json không có field translate_review (video cũ trước
    V29, hoặc review không chạy) -> không lỗi, không thêm bảng mới."""
    page = _page()
    page._current_report = {
        "summary": {"segments_total": 1, "segments_ok": 1},
        "translate_usage": {},
        "per_segment": [],
    }
    page._render_report()  # không được raise


def test_render_report_with_empty_review_trace_no_extra_table():
    page = _page()
    page._current_report = {
        "summary": {"segments_total": 1, "segments_ok": 1},
        "translate_usage": {},
        "per_segment": [],
        "translate_review": [],
    }
    page._render_report()  # không được raise (danh sách rỗng -> không thêm bảng)


def test_build_review_table_shows_correct_row_count_and_header():
    page = _page()
    trace = [
        {"id": 1, "reason": "too_short", "before": "Ngắn.",
         "after": "Bản dịch đầy đủ hơn.", "improved": True},
        {"id": 2, "reason": "cjk", "before": "Còn 你好 sót lại",
         "after": "Còn 你好 sót lại", "improved": False},
    ]
    table_card = page._build_review_table(trace)
    table = table_card.body.itemAt(table_card.body.count() - 1).widget()
    assert table.rowCount() == 2
    assert table.item(0, 0).text() == "1"
    assert table.item(0, 4).text() == "Có"    # improved=True
    assert table.item(1, 4).text() == "Không"  # improved=False


def test_review_table_translates_reason_to_vietnamese_label():
    page = _page()
    trace = [{"id": 1, "reason": "too_short", "before": "a", "after": "b",
             "improved": True}]
    table_card = page._build_review_table(trace)
    table = table_card.body.itemAt(table_card.body.count() - 1).widget()
    assert table.item(0, 1).text() == "nghi dịch sót ý"
