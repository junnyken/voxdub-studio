"""Nút Dừng cho hai thao tác dài trong Trình chỉnh sửa còn thiếu (FEATURES.md
§9): "Lưu tất cả và đọc lại" (SaveAllWorker) và "Xuất video"/"Ghi lại phụ đề"
(RebuildWorker/SubtitleWorker, dùng chung một nút vì không bao giờ chạy chồng
nhau — `editor_export._busy_warn` chặn).

Cờ huỷ ở tầng worker đã có sẵn từ trước (`SaveAllWorker.cancel()`,
`RebuildWorker.cancel()`) — thứ thiếu chỉ là nút bấm tại chỗ trong trang, nên
bộ test này canh ĐÚNG chỗ thiếu đó: nút phải tồn tại, chỉ bật khi đang chạy,
và bấm vào phải gọi tới `cancel()` của đúng worker — không phải nút giả.

Nhân tiện phát hiện một chỗ thiếu khác cùng họ: `_on_export_cancelled` (đã có
từ trước, không phải phần mới thêm) không gọi `REGISTRY.finish_job()`, nên
sổ đăng ký việc-đang-chạy coi máy còn bận mãi sau khi bấm Dừng — Trang chủ sẽ
vẫn hiện "đang xử lý" dù không có gì chạy nữa. Test cuối cùng canh chỗ đó.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub_gui.pages.editor_panels import ExportPanel, VoicePanel  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


def _doc(*parts: str) -> str:
    return open(os.path.join(REPO, *parts), encoding="utf-8").read()


# -- "Lưu tất cả và đọc lại" (VoicePanel) -------------------------------

def test_voice_panel_co_nut_dung_va_tat_mac_dinh():
    panel = VoicePanel()
    assert not panel.btn_stop_resynth.isEnabled(), (
        "chưa đọc lại thì không có gì để dừng")


def test_voice_panel_set_running_bat_tat_dung_nut():
    panel = VoicePanel()
    panel.set_resynth_running(True)
    assert panel.btn_stop_resynth.isEnabled()
    panel.set_resynth_running(False)
    assert not panel.btn_stop_resynth.isEnabled()


def test_bam_dung_resynth_phat_tin_hieu_huy():
    panel = VoicePanel()
    nhan: list[bool] = []
    panel.resynth_cancel_requested.connect(lambda: nhan.append(True))
    panel.set_resynth_running(True)
    panel.btn_stop_resynth.click()
    assert nhan, "bấm Dừng phải phát tín hiệu — không thì nút chỉ nằm đó"


# -- "Xuất video" / "Ghi lại phụ đề" (ExportPanel) ----------------------

def test_export_panel_co_nut_dung_va_tat_mac_dinh():
    panel = ExportPanel()
    assert not panel.btn_stop.isEnabled(), "chưa xuất thì không có gì để dừng"


@pytest.mark.parametrize("subtitles_only", [False, True])
def test_export_panel_set_running_bat_tat_dung_nut(subtitles_only):
    panel = ExportPanel()
    panel.set_running(True, subtitles_only=subtitles_only)
    assert panel.btn_stop.isEnabled()
    panel.set_running(False, subtitles_only=subtitles_only)
    assert not panel.btn_stop.isEnabled()


def test_bam_dung_export_phat_tin_hieu_huy():
    panel = ExportPanel()
    nhan: list[bool] = []
    panel.cancel_requested.connect(lambda: nhan.append(True))
    panel.set_running(True)
    panel.btn_stop.click()
    assert nhan, "bấm Dừng phải phát tín hiệu — không thì nút chỉ nằm đó"


# -- Nối tín hiệu tới đúng worker (không phải nút giả) ------------------

def test_cancel_resynth_goi_dung_worker():
    src = _doc("autodub_gui", "pages", "editor_export.py")
    assert "def _cancel_resynth" in src
    assert "self._resynth_worker.cancel()" in src


def test_cancel_export_goi_dung_worker():
    src = _doc("autodub_gui", "pages", "editor_export.py")
    assert "def _cancel_export" in src
    assert "self._rebuild_worker.cancel()" in src


def test_editor_page_noi_ca_hai_tin_hieu_dung():
    src = _doc("autodub_gui", "pages", "editor_page.py")
    assert "resynth_cancel_requested.connect(self._cancel_resynth)" in src
    assert "cancel_requested.connect(self._cancel_export)" in src


# -- REGISTRY phải được giải phóng khi huỷ, không chỉ khi xong/lỗi ------

def test_huy_resynth_giai_phong_registry():
    src = _doc("autodub_gui", "pages", "editor_export.py")
    idx = src.index("def _on_resynth_cancelled")
    than = src[idx:src.index("\n    def ", idx + 1)]
    assert "REGISTRY.finish_job" in than, (
        "không giải phóng REGISTRY khi huỷ đọc lại giọng thì Trang chủ coi "
        "máy còn bận mãi, và REGISTRY.start_job() lượt sau sẽ ghi cảnh báo "
        "'chưa xong' oan")


def test_huy_export_giai_phong_registry():
    src = _doc("autodub_gui", "pages", "editor_export.py")
    idx = src.index("def _on_export_cancelled")
    than = src[idx:src.index("\n    def ", idx + 1)]
    assert "REGISTRY.finish_job" in than, (
        "không giải phóng REGISTRY khi huỷ xuất video thì Trang chủ coi máy "
        "còn bận mãi sau khi bấm Dừng")
