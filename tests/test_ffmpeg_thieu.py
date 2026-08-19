"""V81 — "Máy chưa có FFmpeg" sau khi nâng cấp, dù đã cài từ lâu.

Người dùng báo bằng ảnh chụp (2026-08-19, v3.4.5): hộp thoại chặn *"Máy chưa
đủ điều kiện lồng tiếng — FFmpeg: Máy chưa có FFmpeg"* kèm lời khuyên tự tải
từ gyan.dev rồi sửa PATH.

Ba thứ sai cùng lúc, và cả ba đều là lỗi của app chứ không phải của người dùng:

1. Trình cài đặt tải FFmpeg về ``<thư mục app>/bin`` — nâng cấp sang thư mục
   mới là tệp nằm lại bản cũ (cùng cảnh ngộ `.venv-*` đã sửa ở V77).
2. Marker của wizard nằm ở ``~/.voxdub_cache`` tức là theo MÁY, không theo
   thư mục ứng dụng → bản mới thấy "đã chạy wizard rồi" nên không mời cài lại.
3. Hộp thoại chặn chỉ dẫn cài tay, trong khi app có sẵn bộ tải tự động
   (`FFmpegDownloadWorker`) — bắt người dùng làm phần việc của mình.
"""
from __future__ import annotations

import os

import pytest

from autodub import venv_discovery


@pytest.fixture(autouse=True)
def _sach():
    venv_discovery.quen_cache()
    yield
    venv_discovery.quen_cache()


def _dung_ban_co_ffmpeg(thu_muc):
    ten = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    bin_dir = thu_muc / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / ten).write_text("")
    return str(bin_dir)


def _lam_app_moi(tmp_path, monkeypatch, ten="VoxDub-Studio-v3.4.6"):
    goc = tmp_path / ten
    goc.mkdir(parents=True, exist_ok=True)
    for muc in ("autodub.utils", "autodub.venv_discovery", "autodub.config"):
        monkeypatch.setattr(f"{muc}.app_root", lambda: str(goc), raising=False)
    return goc


def test_muon_duoc_ffmpeg_cua_ban_cu(tmp_path, monkeypatch):
    bin_cu = _dung_ban_co_ffmpeg(tmp_path / "VoxDub-Studio-v3.4.5")
    _lam_app_moi(tmp_path, monkeypatch)

    assert venv_discovery.tim_thu_muc_bin_cu() == bin_cu


def test_khong_co_ban_cu_thi_khong_bia_ra(tmp_path, monkeypatch):
    _lam_app_moi(tmp_path, monkeypatch)
    (tmp_path / "thu-muc-khac").mkdir()

    assert venv_discovery.tim_thu_muc_bin_cu() == ""


def test_ket_qua_co_nho_dem(tmp_path, monkeypatch):
    _dung_ban_co_ffmpeg(tmp_path / "VoxDub-cu")
    _lam_app_moi(tmp_path, monkeypatch)

    dem = {"n": 0}
    that = os.scandir

    def _dem(p):
        dem["n"] += 1
        return that(p)

    monkeypatch.setattr(os, "scandir", _dem)
    for _ in range(4):
        venv_discovery.tim_thu_muc_bin_cu()
    assert dem["n"] == 1


def test_frozen_noi_thu_muc_bin_cu_vao_path(tmp_path, monkeypatch):
    """Đây là chỗ biến phát hiện trên thành hành động: PATH có thư mục đó thì
    `shutil.which("ffmpeg")` của preflight tìm thấy ngay."""
    from autodub_gui import _frozen

    bin_cu = _dung_ban_co_ffmpeg(tmp_path / "VoxDub-cu")
    goc = _lam_app_moi(tmp_path, monkeypatch)
    monkeypatch.setattr(_frozen, "app_root", lambda: str(goc))
    monkeypatch.setattr(_frozen, "is_frozen", lambda: True)
    monkeypatch.setattr("shutil.which", lambda ten: None)
    monkeypatch.setenv("PATH", "/usr/bin")
    # `_frozen.init()` gọi os.chdir(app_root()) — không trả lại thư mục làm
    # việc là mọi test khác dùng đường dẫn tương đối sẽ hỏng theo (đã dính
    # thật: 3 test diarize_worker đỏ ở lượt chạy đầy đủ, xanh khi chạy lẻ).
    monkeypatch.chdir(os.getcwd())

    _frozen.init()

    assert bin_cu in os.environ["PATH"]


def test_wizard_hien_lai_khi_thieu_ffmpeg_du_da_chay_truoc_do(tmp_path,
                                                              monkeypatch):
    """Marker nằm theo MÁY nên bản mới tưởng đã cài xong — nhưng thiếu FFmpeg
    thì app không chạy được gì, phải mời cài lại."""
    from autodub_gui import setup_wizard

    marker = tmp_path / "setup_wizard_done"
    marker.write_text("done")
    monkeypatch.setattr(setup_wizard, "_marker_path", lambda: str(marker))

    monkeypatch.setattr(setup_wizard, "_ffmpeg_ready", lambda: False)
    assert setup_wizard._is_setup_needed() is True

    monkeypatch.setattr(setup_wizard, "_ffmpeg_ready", lambda: True)
    assert setup_wizard._is_setup_needed() is False


def test_loi_khuyen_khong_bat_nguoi_dung_sua_path(tmp_path, monkeypatch):
    """Chép 2 tệp vào thư mục bin là việc ai cũng làm được; sửa PATH thì
    không — và app còn tự tải được nên đó mới là lời khuyên đầu tiên."""
    from autodub.config import Settings
    from autodub.preflight import _check_ffmpeg

    monkeypatch.setattr("shutil.which", lambda ten: None)
    monkeypatch.setattr("autodub.preflight.app_root", lambda: str(tmp_path))

    r = _check_ffmpeg(Settings())
    assert r.level == "fail"
    assert "tự tải" in r.advice
    assert "thư mục bin" in r.advice
    assert "PATH" not in r.advice.replace("không cần sửa PATH", "")


def test_hop_thoai_chan_moi_cai_dat_thay_vi_chi_bao_loi():
    """Đứt nhánh này là quay lại đúng cảnh người dùng gặp: đọc hướng dẫn rồi
    tự xoay xở."""
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = open(os.path.join(repo, "autodub_gui", "app.py"),
               encoding="utf-8").read()
    i = src.find('"Máy chưa đủ điều kiện lồng tiếng"')
    assert i > 0
    khuc = src[i:i + 900]
    assert 'confirm_label="Tải giúp tôi"' in khuc
    assert "_chay_trinh_cai_dat()" in khuc
    assert "_run_preflight()" in src[src.find("def _chay_trinh_cai_dat"):][:600]
