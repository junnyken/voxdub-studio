"""Mini-spec V32b (docs/PLAN.md, Phase G) — ô "Đồng bộ khẩu hình AI" ở
VoiceStep (trang Tạo dự án, bước 4). Cùng khuôn `test_recognize_step_warning.py`
(dùng ``isHidden()``, không ``isVisible()`` — tránh phụ thuộc widget đã
``.show()`` hay chưa, xem ghi chú `cloud_render` trong chính module)."""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub_gui.pages.new_project_steps import VoiceStep  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_hidden_and_false_by_default():
    step = VoiceStep()
    assert step.lipsync.isHidden()
    assert step.values()["lipsync"] is False


def test_set_available_shows_and_hides():
    step = VoiceStep()
    step.set_lipsync_available(True)
    assert not step.lipsync.isHidden()
    step.set_lipsync_available(False)
    assert step.lipsync.isHidden()


def test_unavailable_never_reports_checked_even_if_forced():
    """Guardrail: `values()` chỉ đọc ô chọn khi _lipsync_available — không
    có đường nào bật lipsync=True mà GUI không xác nhận máy đủ điều kiện."""
    step = VoiceStep()
    step.lipsync.setChecked(True)   # ép trực tiếp, bỏ qua set_lipsync_available
    assert step.values()["lipsync"] is False


def test_available_and_checked_reports_true():
    step = VoiceStep()
    step.set_lipsync_available(True)
    step.lipsync.setChecked(True)
    assert step.values()["lipsync"] is True


def test_becoming_unavailable_clears_checked_state():
    step = VoiceStep()
    step.set_lipsync_available(True)
    step.lipsync.setChecked(True)
    step.set_lipsync_available(False)
    assert step.lipsync.isChecked() is False


def test_audio_only_disables_and_unchecks_lipsync():
    step = VoiceStep()
    step.set_lipsync_available(True)
    step.lipsync.setChecked(True)
    step.audio_only.setChecked(True)
    assert step.lipsync.isChecked() is False
    assert not step.lipsync.isEnabled()

    step.audio_only.setChecked(False)
    assert step.lipsync.isEnabled()


def test_load_restores_checked_state_only_when_available():
    step = VoiceStep()
    step.set_lipsync_available(True)
    step.load({"lipsync": True})
    assert step.lipsync.isChecked() is True

    step2 = VoiceStep()   # KHÔNG gọi set_lipsync_available -> vẫn False
    step2.load({"lipsync": True})
    assert step2.lipsync.isChecked() is False
