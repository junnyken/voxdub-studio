"""Mini-spec V4 (docs/PLAN.md) — cảnh báo Paraformer/ngôn ngữ hiện đúng lúc
trong RecognizeStep (trang Tạo dự án, bước 2)."""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub_gui.pages.new_project_steps import RecognizeStep  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_warning_hidden_by_default():
    step = RecognizeStep()
    assert step.paraformer_warning.isHidden()


def test_warning_shows_on_mismatch_and_hides_when_fixed():
    step = RecognizeStep()
    step.engine.set_key("paraformer")
    step.language.set_key("ko-KR")
    step._update_paraformer_warning()
    assert not step.paraformer_warning.isHidden(), "phải hiện cảnh báo khi lệch"

    step.language.set_key("zh-TW")
    step._update_paraformer_warning()
    assert step.paraformer_warning.isHidden(), "đổi về tiếng Trung thì phải ẩn lại"

    step.engine.set_key("whisper")
    step.language.set_key("ko-KR")
    step._update_paraformer_warning()
    assert step.paraformer_warning.isHidden(), "Whisper nhận mọi ngôn ngữ — không cảnh báo"
