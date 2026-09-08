"""Hộp thoại «Mở video + phụ đề nước ngoài (tự dịch)...» (08/09/2026).

Khoá hành vi GUI của luồng nối Nhập phụ đề + Dịch phụ đề: lựa chọn của
người dùng (ngôn ngữ nguồn/đích, cách dịch) phải THẬT SỰ tới được
`NhapPhuDeDichWorker`, cảnh báo chất lượng dịch hiện đúng lúc, và không cho
đóng dở dang khi đang dịch (tránh để lại thư mục dự án nửa vời).
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from autodub.config import Settings  # noqa: E402
from autodub_gui.pages import nhap_phu_de_dich_dialog as npdd  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture()
def dialog():
    return npdd.NhapPhuDeDichDialog(lambda: Settings())


class _WorkerGia:
    log = type("S", (), {"connect": lambda *a: None})()
    finished_ok = type("S", (), {"connect": lambda *a: None})()
    failed = type("S", (), {"connect": lambda *a: None})()
    finished = type("S", (), {"connect": lambda *a: None})()

    def __init__(self, video, phu_de, thu_muc_goc, source_flores, target_key,
                mode, settings, parent=None):
        _WorkerGia.last_args = dict(
            video=video, phu_de=phu_de, thu_muc_goc=thu_muc_goc,
            source_flores=source_flores, target_key=target_key, mode=mode)

    def start(self):
        pass

    def isRunning(self):
        return False


def test_mac_dinh_nguon_anh_dich_viet_khong_canh_bao(dialog):
    assert dialog.source.current_key() == "eng_Latn"
    assert dialog.target.current_key() == "vi"
    assert dialog.warning.isHidden()


def test_target_flores_dung_bang_da_co(dialog):
    dialog.target.set_key("ja")
    assert dialog._target_flores() == "jpn_Jpan"


def test_chon_ngon_ngu_chua_kiem_chung_thi_canh_bao_hien(dialog):
    dialog.source.set_key("ind_Latn")   # Indonesian — chưa live-verify
    dialog._refresh_warning()
    assert not dialog.warning.isHidden()


def test_thieu_video_thi_canh_bao_khong_crash(dialog, monkeypatch, tmp_path):
    warned = []
    monkeypatch.setattr(npdd.TOASTS, "warn", lambda msg, *a, **k: warned.append(msg))
    monkeypatch.setattr(npdd, "NhapPhuDeDichWorker", _WorkerGia)

    dialog.phu_de.set_text(str(tmp_path / "phu_de.srt"))
    dialog._start()

    assert warned, "thiếu video phải cảnh báo, không chạy worker"
    assert not dialog.is_running()


def test_bam_dich_truyen_dung_tham_so_xuong_worker(dialog, monkeypatch, tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"\x00")
    srt = tmp_path / "phu_de.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n", encoding="utf-8")

    monkeypatch.setattr(npdd, "NhapPhuDeDichWorker", _WorkerGia)
    dialog.video.set_text(str(video))
    dialog.phu_de.set_text(str(srt))
    dialog.target.set_key("ja")

    dialog._start()

    assert _WorkerGia.last_args["source_flores"] == "eng_Latn"
    assert _WorkerGia.last_args["target_key"] == "ja"
    assert _WorkerGia.last_args["mode"] == "local"
    assert _WorkerGia.last_args["video"] == str(video)
    assert _WorkerGia.last_args["phu_de"] == str(srt)


def test_dang_chay_thi_khong_cho_dong(monkeypatch):
    from PySide6.QtWidgets import QDialog

    goi_that = []
    monkeypatch.setattr(QDialog, "reject", lambda self: goi_that.append(1))
    dialog = npdd.NhapPhuDeDichDialog(lambda: Settings())
    monkeypatch.setattr(dialog, "is_running", lambda: True)
    warned = []
    monkeypatch.setattr(npdd.TOASTS, "warn", lambda msg, *a, **k: warned.append(msg))

    dialog.reject()

    assert not goi_that, "đang dịch mà vẫn đóng được — sẽ để lại dự án nửa vời"
    assert warned, "phải nói lý do không đóng được, không im lặng"


def test_khong_chay_thi_dong_binh_thuong(monkeypatch):
    from PySide6.QtWidgets import QDialog

    goi_that = []
    monkeypatch.setattr(QDialog, "reject", lambda self: goi_that.append(1))
    dialog = npdd.NhapPhuDeDichDialog(lambda: Settings())

    dialog.reject()

    assert goi_that, "không chạy gì mà vẫn không đóng được — Huỷ phải hoạt động"
