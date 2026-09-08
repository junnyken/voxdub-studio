"""Trang Tải xuống — thêm lựa chọn "Chỉ âm thanh (MP3)" (08/09/2026), song
song với "Video (MP4)" đã có. Test canh: combo mới có mặt, lựa chọn của
người dùng THẬT SỰ tới được `DownloadWorker` (không phải nút chỉ nằm đó),
và nhãn nút "Mở video"/"Mở audio" hiện đúng theo đuôi tệp kết quả — nói sai
đuôi tệp (vd "Mở video" cho một file .mp3) là lỗi chữ nghĩa đã từng gặp
nhiều lần trong dự án này (xem FEATURES.md §6).
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub_gui.pages import download_page as dp  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture()
def page(monkeypatch):
    p = dp.DownloadPage()
    # Hộp thoại lưu ý bản quyền là modal thật — chặn nó ở test, không phải
    # điều đang được canh ở đây.
    monkeypatch.setattr(p, "_confirm_disclaimer", lambda: True)
    return p


def test_mac_dinh_la_video():
    p = dp.DownloadPage()
    assert p.dinh_dang.current_key() == "video"


def test_co_lua_chon_chi_am_thanh():
    p = dp.DownloadPage()
    khoa = [p.dinh_dang.combo.itemData(i)
           for i in range(p.dinh_dang.combo.count())]
    assert "mp3_audio" in khoa


def test_chon_mp3_thi_worker_nhan_dung_dinh_dang(page, monkeypatch):
    ghi_nhan = {}

    class _WorkerGia:
        item_status = type("S", (), {"connect": lambda *a: None})()
        log = type("S", (), {"connect": lambda *a: None})()
        finished_ok = type("S", (), {"connect": lambda *a: None})()
        failed = type("S", (), {"connect": lambda *a: None})()
        cancelled = type("S", (), {"connect": lambda *a: None})()
        finished = type("S", (), {"connect": lambda *a: None})()

        def __init__(self, urls, output_dir, cookies_browser, cookies_file,
                    parent, dinh_dang="video"):
            ghi_nhan["dinh_dang"] = dinh_dang

        def start(self): pass

    monkeypatch.setattr(dp, "DownloadWorker", _WorkerGia)
    page.urls_edit.setPlainText("https://www.youtube.com/watch?v=abc")
    page.dinh_dang.set_key("mp3_audio")
    page._start()

    assert ghi_nhan["dinh_dang"] == "mp3_audio"


def test_mac_dinh_video_thi_worker_nhan_dinh_dang_video(page, monkeypatch):
    ghi_nhan = {}

    class _WorkerGia:
        item_status = type("S", (), {"connect": lambda *a: None})()
        log = type("S", (), {"connect": lambda *a: None})()
        finished_ok = type("S", (), {"connect": lambda *a: None})()
        failed = type("S", (), {"connect": lambda *a: None})()
        cancelled = type("S", (), {"connect": lambda *a: None})()
        finished = type("S", (), {"connect": lambda *a: None})()

        def __init__(self, urls, output_dir, cookies_browser, cookies_file,
                    parent, dinh_dang="video"):
            ghi_nhan["dinh_dang"] = dinh_dang

        def start(self): pass

    monkeypatch.setattr(dp, "DownloadWorker", _WorkerGia)
    page.urls_edit.setPlainText("https://www.youtube.com/watch?v=abc")
    page._start()

    assert ghi_nhan["dinh_dang"] == "video"


def test_nhan_nut_dung_theo_duoi_tep_mp3(page):
    actions = page._actions("https://x", "success", "/tmp/x.mp3")
    assert actions[0].toolTip() == "Mở audio"
    assert actions[1].toolTip() == "Mở thư mục chứa audio"


def test_nhan_nut_dung_theo_duoi_tep_video(page):
    actions = page._actions("https://x", "success", "/tmp/x.mp4")
    assert actions[0].toolTip() == "Mở video"
    assert actions[1].toolTip() == "Mở thư mục chứa video"
