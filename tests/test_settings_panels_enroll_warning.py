"""Mini-spec V35 (docs/PLAN.md, Phase G) — GUI hiện cảnh báo chất lượng
NGAY sau khi enroll xong (Scope C), không bắt người dùng tự bấm "Nghe thử"
mới phát hiện. Test hàm thuần `_enroll_warning_message()` (tách khỏi
QThread/subprocess thật — xem docstring hàm)."""
from __future__ import annotations

from autodub_gui.pages.settings_panels import _enroll_warning_message


def test_no_warning_keys_returns_empty_string():
    assert _enroll_warning_message({"ok": True, "enrolled": "X"}) == ""


def test_quality_warning_alone_is_returned():
    payload = {"ok": True, "quality_warning": "Âm lượng rất nhỏ."}
    assert _enroll_warning_message(payload) == "Âm lượng rất nhỏ."


def test_truncated_warning_alone_is_returned():
    payload = {"ok": True, "truncated_warning": "Đã cắt còn 8 giây."}
    assert _enroll_warning_message(payload) == "Đã cắt còn 8 giây."


def test_both_warnings_present_are_joined():
    payload = {
        "ok": True,
        "quality_warning": "Âm lượng rất nhỏ.",
        "truncated_warning": "Đã cắt còn 8 giây.",
    }
    result = _enroll_warning_message(payload)
    assert "Âm lượng rất nhỏ." in result
    assert "Đã cắt còn 8 giây." in result


def test_blank_warning_value_treated_as_absent():
    payload = {"ok": True, "quality_warning": ""}
    assert _enroll_warning_message(payload) == ""
