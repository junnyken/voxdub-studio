"""MusicSfxPanel — khối "Nhạc nền & hiệu ứng âm thanh AI" (mini-spec V37,
docs/PLAN.md Phase G). Chạy headless (QT_QPA_PLATFORM=offscreen), cùng
khuôn `test_voice_panel_ai_suggestion.py` (V33)."""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub.media.emphasis_points import EmphasisPoint  # noqa: E402
from autodub_gui.pages import editor_panels  # noqa: E402
from autodub_gui.pages.editor_panels import MusicSfxPanel  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ------------------------------------------------------------- nhạc nền --

def test_music_controls_hidden_by_default():
    panel = MusicSfxPanel()
    assert panel.btn_preview_music.isHidden()
    assert panel.btn_apply_music.isHidden()


def test_music_requested_emits_current_text():
    panel = MusicSfxPanel()
    panel.music_desc.setText("  nhạc vui tươi  ")
    received = []
    panel.music_requested.connect(received.append)
    panel.btn_gen_music.click()
    assert received == ["nhạc vui tươi"]   # đã .strip()


def test_set_music_status_with_path_shows_preview_and_apply():
    panel = MusicSfxPanel()
    panel.set_music_status("Đã sinh xong.", path="/tmp/music.mp3")
    assert not panel.btn_preview_music.isHidden()
    assert not panel.btn_apply_music.isHidden()


def test_set_music_status_without_path_hides_buttons():
    panel = MusicSfxPanel()
    panel.set_music_status("Đã sinh xong.", path="/tmp/music.mp3")
    panel.set_music_status("Lỗi rồi.")
    assert panel.btn_preview_music.isHidden()
    assert panel.btn_apply_music.isHidden()


def test_preview_music_opens_the_saved_path(monkeypatch):
    opened = []
    monkeypatch.setattr(editor_panels, "_open_in_default_player", opened.append)
    panel = MusicSfxPanel()
    panel.set_music_status("Đã sinh xong.", path="/tmp/music.mp3")
    panel._preview_music()
    assert opened == ["/tmp/music.mp3"]


def test_apply_music_requested_emitted_on_click():
    panel = MusicSfxPanel()
    panel.set_music_status("Đã sinh xong.", path="/tmp/music.mp3")
    fired = []
    panel.apply_music_requested.connect(lambda: fired.append(True))
    panel.btn_apply_music.click()
    assert fired == [True]


# ---------------------------------------------------- hiệu ứng âm thanh --

def test_sfx_controls_hidden_until_points_found():
    panel = MusicSfxPanel()
    assert panel.points_list.isHidden()
    assert panel.sfx_desc.isHidden()
    assert panel.btn_gen_sfx.isHidden()


def test_set_emphasis_points_populates_list_and_shows_controls():
    panel = MusicSfxPanel()
    points = [EmphasisPoint(time=2.0, reason="Câu kết bằng dấu nhấn mạnh"),
             EmphasisPoint(time=7.5, reason="Khoảng lặng dài")]
    panel.set_emphasis_points(points)
    assert panel.points_list.count() == 2
    assert not panel.points_list.isHidden()
    assert not panel.sfx_desc.isHidden()
    assert not panel.btn_gen_sfx.isHidden()


def test_set_emphasis_points_empty_shows_no_result_message():
    panel = MusicSfxPanel()
    panel.set_emphasis_points([])
    assert panel.points_list.isHidden()
    assert "Không tìm thấy" in panel.sfx_status.text()


def test_generate_sfx_requires_selected_point():
    panel = MusicSfxPanel()
    panel.set_emphasis_points([EmphasisPoint(time=2.0, reason="x")])
    panel.sfx_desc.setText("tiếng vỗ tay")
    # Chưa chọn dòng nào trong danh sách (currentRow() == -1 mặc định).
    received = []
    panel.sfx_requested.connect(lambda *a: received.append(a))
    panel.btn_gen_sfx.click()
    assert received == []
    assert "chọn 1 điểm" in panel.sfx_status.text()


def test_generate_sfx_requires_description():
    panel = MusicSfxPanel()
    panel.set_emphasis_points([EmphasisPoint(time=2.0, reason="x")])
    panel.points_list.setCurrentRow(0)
    received = []
    panel.sfx_requested.connect(lambda *a: received.append(a))
    panel.btn_gen_sfx.click()
    assert received == []
    assert "mô tả" in panel.sfx_status.text()


def test_generate_sfx_emits_timestamp_description_and_name():
    panel = MusicSfxPanel()
    panel.set_emphasis_points([
        EmphasisPoint(time=2.0, reason="a"), EmphasisPoint(time=7.5, reason="b")])
    panel.points_list.setCurrentRow(1)
    panel.sfx_desc.setText("tiếng chuông")
    received = []
    panel.sfx_requested.connect(lambda *a: received.append(a))
    panel.btn_gen_sfx.click()
    assert len(received) == 1
    timestamp, desc, name = received[0]
    assert timestamp == 7.5
    assert desc == "tiếng chuông"
    assert "7" in name


def test_selecting_a_different_point_resets_pending_preview():
    """Đổi điểm đang chọn phải xoá preview cũ — tránh chèn nhầm hiệu ứng
    của điểm A vào điểm B."""
    panel = MusicSfxPanel()
    panel.set_emphasis_points([
        EmphasisPoint(time=2.0, reason="a"), EmphasisPoint(time=7.5, reason="b")])
    panel.points_list.setCurrentRow(0)
    panel.set_sfx_status("Đã sinh xong.", path="/tmp/sfx.wav", timestamp=2.0)
    assert not panel.btn_apply_sfx.isHidden()

    panel.points_list.setCurrentRow(1)
    assert panel.btn_apply_sfx.isHidden()
    assert panel.btn_preview_sfx.isHidden()


def test_preview_sfx_opens_the_saved_path(monkeypatch):
    opened = []
    monkeypatch.setattr(editor_panels, "_open_in_default_player", opened.append)
    panel = MusicSfxPanel()
    panel.set_sfx_status("Đã sinh xong.", path="/tmp/sfx.wav", timestamp=2.0)
    panel._preview_sfx()
    assert opened == ["/tmp/sfx.wav"]


def test_apply_sfx_emits_timestamp_and_path():
    panel = MusicSfxPanel()
    panel.set_sfx_status("Đã sinh xong.", path="/tmp/sfx.wav", timestamp=2.0)
    received = []
    panel.sfx_apply_requested.connect(lambda *a: received.append(a))
    panel.btn_apply_sfx.click()
    assert received == [(2.0, "/tmp/sfx.wav")]


def test_apply_sfx_does_nothing_without_preview():
    panel = MusicSfxPanel()
    received = []
    panel.sfx_apply_requested.connect(lambda *a: received.append(a))
    panel._emit_apply_sfx()
    assert received == []
