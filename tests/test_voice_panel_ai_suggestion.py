"""VoicePanel — khối "AI đề xuất giọng" (mini-spec V33, docs/PLAN.md
Phase G). Chạy headless (QT_QPA_PLATFORM=offscreen), cùng khuôn
`tests/test_quality_page_review_trace.py`.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub_gui.pages.editor_panels import VoicePanel  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_hidden_by_default():
    panel = VoicePanel()
    assert panel.ai_suggestion_label.isHidden()
    assert panel.btn_apply_suggestion.isHidden()


def test_set_ai_suggestion_shows_block_with_reason():
    panel = VoicePanel()
    panel.set_ai_suggestion("Thu Hà (tin tức)", "giọng nữ, phong cách tin tức")
    assert not panel.ai_suggestion_label.isHidden()
    assert not panel.btn_apply_suggestion.isHidden()
    assert "Thu Hà (tin tức)" in panel.ai_suggestion_label.text()
    assert "giọng nữ, phong cách tin tức" in panel.ai_suggestion_label.text()


def test_set_ai_suggestion_empty_name_hides_block():
    panel = VoicePanel()
    panel.set_ai_suggestion("Thu Hà (tin tức)", "giọng nữ")
    panel.set_ai_suggestion("", "")
    assert panel.ai_suggestion_label.isHidden()
    assert panel.btn_apply_suggestion.isHidden()


def test_apply_suggestion_does_nothing_without_a_pending_suggestion():
    """Bấm nút (hoặc gọi nhầm) khi chưa có gợi ý nào — không được crash,
    không đổi picker."""
    panel = VoicePanel()
    before = panel.picker.voice()
    panel._apply_ai_suggestion()
    assert panel.picker.voice() == before


def test_apply_suggestion_switches_picker_and_refreshes_pending_hint():
    """Bấm "Đổi sang giọng AI đề xuất" phải đi đúng luồng đổi giọng thủ
    công (set_voice + _on_voice_changed) — không phải tự âm thầm đổi mà
    không cập nhật băng nhắc "chưa đọc lại"."""
    from autodub.speech.tts.voices import Voice

    panel = VoicePanel()
    panel.picker._voices = [Voice(name="Thu Hà (tin tức)", gender="female",
                                  style="tin_tuc")]
    panel.set_project_voice("Bảo Long")  # giọng dự án hiện tại (khác đề xuất)
    panel.set_ai_suggestion("Thu Hà (tin tức)", "giọng nữ, phong cách tin tức")

    panel._apply_ai_suggestion()

    assert panel.picker.voice() == "Thu Hà (tin tức)"
    # Đổi rồi nhưng chưa đọc lại — băng nhắc "chuyển hẳn sang giọng..." phải hiện.
    assert not panel.voice_hint.isHidden()
