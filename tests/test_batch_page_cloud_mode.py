"""Mini-spec V53 — chế độ "xử lý trên máy chủ" trên trang Xử lý hàng loạt.

Điều đáng test không phải "ô checkbox có hiện không" mà là những chỗ nếu sai
thì người dùng bị lừa:

* ô này phải ẨN khi máy chưa cấu hình được (đúng nếp `cloud_render` V12 và
  lip-sync V32b: không bày ra thứ bấm vào là báo lỗi),
* bật lên phải KHOÁ đúng những tuỳ chọn máy chủ không làm — để chúng bật mà
  không có tác dụng là hứa suông,
* liên kết (URL) phải bị chặn kèm lời giải thích, vì máy chủ chỉ nhận file
  tải lên; âm thầm bỏ qua vài dòng là kiểu hỏng tệ nhất.

Chạy:  QT_QPA_PLATFORM=offscreen pytest tests/test_batch_page_cloud_mode.py
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import autodub_gui.pages.batch_page as batch_page  # noqa: E402
from autodub.config import Settings  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def page(app, monkeypatch, tmp_path):
    """Trang Batch với chế độ máy chủ ĐÃ cấu hình."""
    monkeypatch.setattr(batch_page, "_cloud_dub_configured", lambda: True)
    settings = Settings()
    settings.output_dir = str(tmp_path / "out")
    return batch_page.BatchPage(lambda: settings)


def test_checkbox_hidden_when_cloud_not_configured(app, monkeypatch, tmp_path):
    monkeypatch.setattr(batch_page, "_cloud_dub_configured", lambda: False)
    settings = Settings()
    settings.output_dir = str(tmp_path / "out")
    p = batch_page.BatchPage(lambda: settings)

    # Dùng isHidden() chứ không isVisible(): trang chưa được show nên mọi
    # widget đều "không nhìn thấy" — thứ cần kiểm là có bị ẩn CÓ CHỦ Ý không.
    assert p.chk_cloud.isHidden(), (
        "chưa cấu hình được thì không bày ô ra để người dùng bấm vào rồi ăn lỗi"
    )
    assert p.cloud_mode() is False


def test_checkbox_shown_when_configured(page):
    assert not page.chk_cloud.isHidden()
    assert page.cloud_mode() is False, "mặc định vẫn là chạy trên máy"


def test_turning_it_on_locks_options_the_server_does_not_do(page):
    page.chk_cloud.setChecked(True)

    assert page.cloud_mode() is True
    assert not page.opt_subtitle.isEnabled(), "máy chủ không làm phụ đề"
    assert not page.chk_audio_only.isEnabled(), "máy chủ không có chế độ chỉ-âm-thanh"
    assert not page.chk_reuse.isEnabled(), "giữ bộ giọng là chuyện của máy này"
    assert not page.opt_duck.isEnabled(), "máy chủ không có mức giảm tiếng gốc"
    assert not page.lbl_cloud_note.isHidden(), "phải nói rõ ranh giới"


def test_turning_it_off_restores_the_options(page):
    page.chk_cloud.setChecked(True)
    page.chk_cloud.setChecked(False)

    assert page.opt_subtitle.isEnabled()
    assert page.chk_audio_only.isEnabled()
    assert page.chk_reuse.isEnabled()
    assert page.lbl_cloud_note.isHidden()


def test_links_are_refused_with_an_explanation_not_silently_skipped(page, monkeypatch):
    warned: list[str] = []
    monkeypatch.setattr(batch_page.TOASTS, "warn", lambda msg, *a, **k: warned.append(msg))
    started: list = []
    monkeypatch.setattr(batch_page, "CloudBatchWorker",
                        lambda *a, **k: started.append((a, k)))

    page.chk_cloud.setChecked(True)
    item = batch_page.BatchItem(url="https://youtu.be/abc")
    page._launch([item])

    assert not started, "không được nộp gì khi danh sách có liên kết"
    assert warned, "phải báo cho người dùng biết vì sao"
    assert "liên kết" in warned[0].lower()


def test_files_from_two_folders_are_refused_clearly(page, monkeypatch, tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "v1.mp4").write_bytes(b"x")
    (b / "v2.mp4").write_bytes(b"x")

    warned: list[str] = []
    monkeypatch.setattr(batch_page.TOASTS, "warn", lambda msg, *a_, **k: warned.append(msg))
    started: list = []
    monkeypatch.setattr(batch_page, "CloudBatchWorker",
                        lambda *a_, **k: started.append(k))

    page.chk_cloud.setChecked(True)
    page._launch([
        batch_page.BatchItem(file_path=str(a / "v1.mp4")),
        batch_page.BatchItem(file_path=str(b / "v2.mp4")),
    ])

    assert not started
    assert warned and "thư mục" in warned[0].lower()


def test_worker_gets_the_options_actually_chosen(page, monkeypatch, tmp_path):
    folder = tmp_path / "vids"
    folder.mkdir()
    (folder / "v1.mp4").write_bytes(b"x")

    captured: dict = {}

    class FakeWorker:
        def __init__(self, source, output, **kwargs):
            captured["source"] = source
            captured["output"] = output
            captured.update(kwargs)
            self.log = _Sig()
            self.finished_ok = _Sig()
            self.failed = _Sig()
            self.finished = _Sig()

        def start(self):
            captured["started"] = True

    class _Sig:
        def connect(self, *_a, **_k):
            pass

    monkeypatch.setattr(batch_page, "CloudBatchWorker", FakeWorker)
    monkeypatch.setattr(batch_page.REGISTRY, "start_job", lambda *a, **k: None)

    page.chk_cloud.setChecked(True)
    page.opt_bg.set_key("demucs")
    page._launch([batch_page.BatchItem(file_path=str(folder / "v1.mp4"))])

    assert captured.get("started") is True
    assert captured["source"] == folder
    assert captured["bg_mode"] == "demucs", "chọn giữ nhạc nền thì phải gửi đúng"
    assert "cloud" in str(captured["output"]), "kết quả để riêng, không trộn với chạy máy"
