"""Mini-spec V13 (docs/PLAN.md) guardrail 1 — FAQ ở trang Trợ giúp
(help_page.py) phải nói rõ việc gửi trạng thái tiến trình khi ở chế độ
SaaS. Khoá lại bằng test đọc thẳng nội dung EXTRA_PROBLEMS, không chỉ tin
đã sửa đúng.
"""
from __future__ import annotations

from autodub_gui.pages.help_page import EXTRA_PROBLEMS


def test_faq_has_entry_disclosing_telemetry():
    matches = [
        (title, body) for title, body in EXTRA_PROBLEMS
        if "gửi dữ liệu" in title.lower() or "gửi dữ liệu" in body.lower()
    ]
    assert matches, "help_page.py phải có mục FAQ nói rõ việc gửi dữ liệu về máy chủ"
    title, body = matches[0]
    assert "trạng thái tiến trình" in body.lower()
    assert "không bao giờ" in body.lower()
    assert "local-only" in body.lower() or "không cấu hình máy chủ" in body.lower()
