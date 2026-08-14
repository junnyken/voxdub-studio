"""MusicSfxMixin (autodub_gui.pages.editor_music_sfx) — mini-spec V37,
docs/PLAN.md Phase G. Kiểm hành vi nối dây tách khỏi EditorPage thật (không
cần dựng cả trang/QThread) — host giả chỉ có đúng những thuộc tính/hàm mà
mixin gọi tới, cùng khuôn `test_editor_speakers.py`/`test_music_sfx_panel.py`.
`MusicSfxWorker` thật (chạy trong QThread) bị monkeypatch bằng 1 lớp giả
gọi hàm ngay lập tức trên luồng chính — không cần chờ signal bất đồng bộ.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub_gui.pages import editor_music_sfx  # noqa: E402
from autodub_gui.pages.editor_music_sfx import MusicSfxMixin  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


class _FakeCombo:
    def __init__(self):
        self.key = ""

    def set_key(self, key):
        self.key = key


class _FakeBackgroundPanel:
    def __init__(self):
        self.mode = _FakeCombo()


class _FakePanel:
    def __init__(self):
        self.music_status = None
        self.music_path = None
        self.sfx_status = None
        self.sfx_path = None
        self.sfx_timestamp = None
        self.points = None

    def set_music_status(self, text, *, path=""):
        self.music_status = text
        self.music_path = path

    def set_sfx_status(self, text, *, path="", timestamp=0.0):
        self.sfx_status = text
        self.sfx_path = path
        self.sfx_timestamp = timestamp

    def set_emphasis_points(self, points):
        self.points = points


class _Host(MusicSfxMixin):
    def __init__(self):
        self.music_sfx_panel = _FakePanel()
        self.background_panel = _FakeBackgroundPanel()
        self._work_dir = "/tmp/proj"
        self._segments = [
            {"id": 1, "text": "Xin chào!", "start": 0.0, "end": 1.0},
        ]
        self._state = None
        self._music_sfx_worker = None
        self._sfx_apply_resume_pos = None
        self.saved = False
        self.released = False
        self.restored = []
        self.reloaded = []
        self.errors = []

    def _busy_warn(self):
        return False

    def _flush_edits(self):
        pass

    def _save_render_opts(self):
        self.saved = True

    def release_video(self):
        self.released = True
        return 12.5

    def restore_video(self, position):
        self.restored.append(position)

    def _reload_player(self, path):
        self.reloaded.append(path)


class _FakeWorker(QObject):
    """Thay MusicSfxWorker thật — gọi ngay trên luồng chính, không QThread,
    để test khỏi phải chờ signal bất đồng bộ."""

    finished_ok = Signal(str, dict)
    failed = Signal(str)

    def __init__(self, kind, work_dir, **kwargs):
        super().__init__()
        self.kind = kind
        self.work_dir = work_dir
        self.kwargs = kwargs

    def start(self):
        pass

    def isRunning(self):
        return False


@pytest.fixture(autouse=True)
def _no_modal_dialog(monkeypatch):
    """`ConfirmDialog.show_error` mở QDialog.exec() thật — chặn test headless.
    Ghi lại lời gọi thay vì hiện hộp thoại."""
    calls = []
    monkeypatch.setattr(
        editor_music_sfx.ConfirmDialog, "show_error",
        staticmethod(lambda *a, **k: calls.append((a, k))))
    return calls


def _patch_worker(monkeypatch, factory):
    """`factory(worker)` chạy ngay khi `.start()` được gọi — mô phỏng kết
    quả thật/lỗi thật của MusicSfxWorker mà không cần luồng nền. Handler
    trong editor_music_sfx.py import `MusicSfxWorker` cục bộ (lazy) từ
    `autodub_gui.workers`, nên chỉ cần thay thuộc tính module đó."""
    import autodub_gui.workers as workers_module

    class _Worker(_FakeWorker):
        def start(self):
            factory(self)

    monkeypatch.setattr(workers_module, "MusicSfxWorker", _Worker)


# ------------------------------------------------------------- nhạc nền --

def test_music_requested_empty_description_shows_hint():
    host = _Host()
    host._on_music_requested("")
    assert "mô tả" in host.music_sfx_panel.music_status


def test_music_requested_success_updates_status(monkeypatch):
    host = _Host()

    def _run(worker):
        worker.finished_ok.emit("/tmp/proj/data/ai_music.wav",
                                {"creditCharged": 500, "balanceAfter": 100})

    _patch_worker(monkeypatch, _run)
    host._on_music_requested("nhạc vui tươi")
    assert host.music_sfx_panel.music_path == "/tmp/proj/data/ai_music.wav"
    assert "500 Vox" in host.music_sfx_panel.music_status


def test_music_requested_failure_shows_error_not_status_path(monkeypatch, _no_modal_dialog):
    host = _Host()

    def _run(worker):
        worker.failed.emit("hết Vox")

    _patch_worker(monkeypatch, _run)
    host._on_music_requested("nhạc buồn")
    assert host.music_sfx_panel.music_path == ""
    assert len(_no_modal_dialog) == 1


def test_apply_music_sets_bg_mode_and_saves():
    host = _Host()
    host._on_apply_music()
    assert host.background_panel.mode.key == "ai_music"
    assert host.saved is True


# --------------------------------------------------- hiệu ứng âm thanh --

def test_sfx_points_requested_uses_segments():
    host = _Host()
    host._on_sfx_points_requested()
    assert host.music_sfx_panel.points
    assert host.music_sfx_panel.points[0].reason.startswith("Câu kết")


def test_sfx_requested_success_updates_status_with_timestamp(monkeypatch):
    host = _Host()

    def _run(worker):
        assert worker.kind == "sfx_preview"
        worker.finished_ok.emit("/tmp/proj/data/sfx_pt0_2.wav",
                                {"creditCharged": 100, "balanceAfter": 400})

    _patch_worker(monkeypatch, _run)
    host._on_sfx_requested(2.0, "tiếng vỗ tay", "pt0_2")
    assert host.music_sfx_panel.sfx_path == "/tmp/proj/data/sfx_pt0_2.wav"
    assert host.music_sfx_panel.sfx_timestamp == 2.0
    assert "100 Vox" in host.music_sfx_panel.sfx_status


def test_sfx_apply_releases_video_and_reloads_on_success(monkeypatch):
    host = _Host()

    def _run(worker):
        assert worker.kind == "sfx_apply"
        worker.finished_ok.emit("/tmp/proj/dubbed_video.mp4", {})

    _patch_worker(monkeypatch, _run)
    host._on_sfx_apply_requested(2.0, "/tmp/proj/data/sfx_pt0_2.wav")
    assert host.released is True
    assert host.reloaded == ["/tmp/proj/dubbed_video.mp4"]
    assert host.restored == [12.5]
    assert host._sfx_apply_resume_pos is None


def test_sfx_apply_failure_restores_video_and_shows_error(monkeypatch, _no_modal_dialog):
    host = _Host()

    def _run(worker):
        worker.failed.emit("chưa có bản video đã ghép")

    _patch_worker(monkeypatch, _run)
    host._on_sfx_apply_requested(2.0, "/tmp/proj/data/sfx_pt0_2.wav")
    assert host.restored == [12.5]
    assert host.reloaded == []
    assert len(_no_modal_dialog) == 1
