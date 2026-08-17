"""Mini-spec V64 — thẻ «Đáng sửa trước» trên trang Báo cáo chất lượng.

Kiểm đúng phần GUI thêm vào: thẻ chỉ hiện khi CÓ câu đáng sửa, và nút mở
Trình chỉnh sửa đi qua đúng cửa (cửa sổ chính) chứ không tự dựng editor.

Chạy:  QT_QPA_PLATFORM=offscreen pytest tests/test_quality_page_top_issues.py
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import autodub_gui.pages.quality_page as qpage  # noqa: E402
from autodub.config import Settings  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def page(app, tmp_path):
    settings = Settings()
    settings.output_dir = str(tmp_path)
    return qpage.QualityPage(lambda: settings)


def test_card_is_built_when_there_are_problem_segments(page):
    card = page._build_top_issues([
        {"id": 3, "overlap_prev_s": 0.9, "text": "câu chồng tiếng"},
        {"id": 8, "atempo": 1.45, "text": "câu đọc nhanh"},
    ])

    assert card is not None


def test_no_card_when_nothing_is_worth_fixing(page):
    """Không có gì đáng sửa thì đừng bày một thẻ rỗng."""
    assert page._build_top_issues([{"id": 1}, {"id": 2, "atempo": 1.0}]) is None
    assert page._build_top_issues([]) is None


def test_open_in_editor_goes_through_the_main_window(page, monkeypatch):
    opened = []

    class FakeWindow:
        def open_editor(self, work_dir):
            opened.append(work_dir)

    monkeypatch.setattr(page, "window", lambda: FakeWindow())
    monkeypatch.setattr(page, "_current_work_dir", lambda: "/du/an/A")

    page._open_in_editor()

    assert opened == ["/du/an/A"]


def test_open_in_editor_warns_when_no_project_selected(page, monkeypatch):
    warned = []
    monkeypatch.setattr(qpage.TOASTS, "warn", lambda m, *a, **k: warned.append(m))
    monkeypatch.setattr(page, "_current_work_dir", lambda: "")

    page._open_in_editor()

    assert warned, "phải báo chứ không im lặng không làm gì"


def test_open_in_editor_degrades_when_host_cannot_open(page, monkeypatch):
    """Trang có thể được dựng ngoài cửa sổ chính (test, nhúng chỗ khác) —
    không được nổ."""
    warned = []
    monkeypatch.setattr(qpage.TOASTS, "warn", lambda m, *a, **k: warned.append(m))
    monkeypatch.setattr(page, "_current_work_dir", lambda: "/du/an/A")
    monkeypatch.setattr(page, "window", lambda: object())

    page._open_in_editor()

    assert warned
