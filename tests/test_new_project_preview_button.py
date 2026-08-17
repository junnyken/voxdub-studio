"""Mini-spec V56 — nút "Nghe thử 30 giây" trên trang Tạo dự án.

Ba điều phải đúng, vì sai chỗ nào cũng làm người dùng mất tiền hoặc mất niềm
tin vào chính bản nghe thử:

* nút chỉ hiện ở bước cuối (lúc đã chọn xong giọng/xưng hô), và KHÔNG hiện khi
  đang «chạy tiếp dự án cũ» — nghe thử lại 30 giây đầu của dự án đã chạy là vô
  nghĩa;
* bản thử phải chạy bằng ĐÚNG cấu hình người dùng vừa chọn, nếu không thì nghe
  xong cũng chẳng kết luận được gì;
* bản thử phải chạy THẲNG ra video (`defer_export=False`) — wizard bình thường
  dừng trước bước Xuất video chờ người dùng chốt, giữ nguyên nếp đó thì không
  có gì để nghe.

Chạy:  QT_QPA_PLATFORM=offscreen pytest tests/test_new_project_preview_button.py
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import autodub_gui.pages.new_project_page as npp  # noqa: E402
from autodub.config import Settings  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def page(app, tmp_path):
    settings = Settings()
    settings.output_dir = str(tmp_path / "out")
    return npp.NewProjectPage(lambda: settings)


def test_button_is_hidden_before_the_last_step(page):
    page._go_to_step(0)
    assert page.btn_preview.isHidden(), (
        "chưa chọn xong giọng/xưng hô thì nghe thử chưa nói lên điều gì"
    )


def test_button_shows_on_the_run_step(page):
    page._go_to_step(npp._RUN_INDEX)
    assert not page.btn_preview.isHidden()


def test_button_stays_hidden_when_resuming_an_old_project(page):
    page.step_video.source.set_key("resume")
    page._go_to_step(npp._RUN_INDEX)
    assert page.btn_preview.isHidden(), (
        "dự án cũ đã chạy rồi — nghe thử lại 30 giây đầu là vô nghĩa"
    )


def test_preview_uses_the_chosen_settings_and_exports_straight_away(page, monkeypatch):
    launched = {}
    monkeypatch.setattr(page, "_launch", lambda req: launched.setdefault("req", req))
    monkeypatch.setattr(npp.TOASTS, "info", lambda *a, **k: None)

    built = npp.DubRequest(file_path="/tmp/x.mp4", voice="Phạm Tuyên",
                           bg_mode="demucs", defer_export=True)
    monkeypatch.setattr(page, "_build_request", lambda: built)

    page._start_preview()

    req = launched["req"]
    assert req.preview_seconds == npp.PREVIEW_SECONDS == 30
    assert req.voice == "Phạm Tuyên", "phải dùng đúng giọng người dùng đã chọn"
    assert req.bg_mode == "demucs", "phải dùng đúng chế độ nhạc nền đã chọn"
    assert req.defer_export is False, (
        "bản nghe thử phải ra thẳng video, không dừng chờ bấm Xuất video"
    )


def test_nothing_launches_when_the_form_is_incomplete(page, monkeypatch):
    launched = []
    monkeypatch.setattr(page, "_launch", lambda req: launched.append(req))
    monkeypatch.setattr(page, "_build_request", lambda: None)

    page._start_preview()

    assert not launched, "form chưa hợp lệ thì không được chạy gì cả"
