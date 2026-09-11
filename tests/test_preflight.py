"""Kiểm tra autodub.preflight — logic thuần, không cần Qt."""
import os

import pytest

from autodub.config import Settings
from autodub.preflight import (
    CheckResult, blocking_failures, run_preflight, warnings_of,
    _check_asr, _check_disk, _check_vieneu, _total_ram_gb,
)


@pytest.fixture
def settings():
    return Settings.load(override=True)


def test_run_preflight_returns_results(settings):
    results = run_preflight(settings)
    assert results, "phải có ít nhất một mục kiểm tra"
    for r in results:
        assert isinstance(r, CheckResult)
        assert r.level in ("ok", "warn", "fail")
        assert r.key and r.title and r.message
        # Mục không đạt phải có lời khuyên để người dùng tự xử lý.
        if r.level in ("warn", "fail"):
            assert r.advice


def test_run_preflight_never_raises(monkeypatch, settings):
    # Một mục nổ tung cũng không được chặn các mục khác.
    import autodub.preflight as pf

    def _boom(_settings):
        raise RuntimeError("nổ")

    monkeypatch.setattr(pf, "_check_ffmpeg", _boom)
    results = pf.run_preflight(settings)
    assert any(r.key == "internal" for r in results)


def test_blocking_and_warning_filters():
    results = [
        CheckResult("a", "A", "ok", "x"),
        CheckResult("b", "B", "warn", "x", "y"),
        CheckResult("c", "C", "fail", "x", "y"),
    ]
    assert [r.key for r in blocking_failures(results)] == ["c"]
    assert [r.key for r in warnings_of(results)] == ["b"]
    assert results[0].ok and not results[1].ok


def test_check_disk_missing_dir_walks_to_parent(tmp_path):
    # OUTPUT_DIR chưa tồn tại (lần chạy đầu) → đo ổ đĩa cha, không nổ.
    settings = Settings.load(override=True)
    settings.output_dir = str(tmp_path / "chua" / "ton" / "tai")
    result = _check_disk(settings)
    assert result.key == "disk"
    assert result.level in ("ok", "warn", "fail")


def test_check_vieneu_not_configured(settings, monkeypatch):
    """Chưa cài VieNeu chỉ là cảnh báo — giọng CapCut vẫn lồng tiếng được."""
    monkeypatch.setattr(Settings, "vieneu_configured", lambda self: False)
    result = _check_vieneu(settings)
    assert result.level == "warn"
    assert "setup_vieneu" in result.advice


def test_check_asr_paraformer_not_configured(settings, monkeypatch):
    settings.asr_engine = "paraformer"
    monkeypatch.setattr(Settings, "paraformer_configured", lambda self: False)
    result = _check_asr(settings)
    assert result.level == "fail"
    assert "Whisper" in result.advice


def test_total_ram_readable():
    total = _total_ram_gb()
    # Trên máy thật phải đọc được số dương; 0.0 chỉ khi API hỏng.
    assert total >= 0.0


def test_logs_dir_and_file_logging(tmp_path, monkeypatch):
    import autodub.utils as utils

    monkeypatch.setattr(utils, "app_root", lambda: str(tmp_path))
    monkeypatch.setattr(utils, "_FILE_HANDLER", None)
    path = utils.init_file_logging()
    assert path == os.path.join(str(tmp_path), "logs", "voxdub.log")
    assert os.path.isdir(os.path.dirname(path))
    # Gọi lại phải trả về cùng tệp, không thêm handler thứ hai.
    assert utils.init_file_logging() == path
    import logging
    root = logging.getLogger("autodub")
    file_handlers = [h for h in root.handlers
                     if getattr(h, "baseFilename", "") == path]
    assert len(file_handlers) == 1
    # Dọn: gỡ handler để không giữ tệp mở sang test khác.
    for h in file_handlers:
        root.removeHandler(h)
        h.close()
    monkeypatch.setattr(utils, "_FILE_HANDLER", None)


# ---------------------------------------------------------------------------
# C20 — FFmpeg có ĐÓNG được nhãn chữ lên hình không.
#
# `drawtext` CÓ MẶT không nghĩa là nó CHẠY ĐƯỢC: bộ lọc cần tìm một phông
# chữ, mà dự án không chỉ đích danh `fontfile` ở hai chỗ — nhãn AI-generated
# trên VIDEO (`product_video._lenh_ghep`) và trên ẢNH
# (`product_scene.dong_nhan_chu`).
#
# Trên Linux ffmpeg thường có libfontconfig nên tự dò ra phông — đó là lý do
# lỗi này KHÔNG thể phát hiện được ở workspace. Máy Windows thiếu fontconfig
# thì `drawtext` trả "Cannot find a valid font for the family Sans", và hậu
# quả khác hẳn nhau: ghép video HỎNG CẢ LƯỢT (nhãn nằm trên luồng ra chính),
# còn đóng nhãn ảnh thì ảnh bị loại.

def _chay_gia(monkeypatch, returncode, stderr=""):
    import subprocess as sp

    from autodub import preflight as pf

    monkeypatch.setattr(pf.shutil, "which", lambda _x: "/gia/ffmpeg")

    def _run(cmd, **kw):
        return sp.CompletedProcess(cmd, returncode, stdout="", stderr=stderr)

    monkeypatch.setattr(pf.subprocess, "run", _run)
    return pf


def test_drawtext_chay_duoc_thi_bao_ok(monkeypatch, settings):
    pf = _chay_gia(monkeypatch, 0)
    ra = pf._check_drawtext(settings)
    assert ra.level == "ok"
    assert ra.key == "drawtext"


def test_drawtext_HONG_thi_bao_fail_va_chi_dung_cach_chua(monkeypatch, settings):
    pf = _chay_gia(monkeypatch, 1,
                   "[Parsed_drawtext_0 @ 0x55] Cannot find a valid font for "
                   "the family Sans")
    ra = pf._check_drawtext(settings)

    assert ra.level == "fail", "đây là thứ làm hỏng CẢ LƯỢT ghép video"
    # Mang nguyên văn lỗi của ffmpeg: "không đóng được nhãn" một mình không
    # cho người dùng biết phải cài lại bản nào.
    assert "Cannot find a valid font" in ra.message
    assert "fontconfig" in ra.advice and "full" in ra.advice.lower()
    # Nói rõ vì sao đáng quan tâm, không chỉ báo một mã lỗi.
    assert "AI-generated" in ra.advice


def test_drawtext_kiem_bang_cach_CHAY_THAT_khong_chi_hoi_danh_sach(
        monkeypatch, settings):
    """Hỏi `-filters` chỉ biết bộ lọc có mặt hay không, không biết nó chạy
    được hay không — mà chính đó mới là chỗ hỏng."""
    lenh = {}
    import subprocess as sp

    from autodub import preflight as pf

    monkeypatch.setattr(pf.shutil, "which", lambda _x: "/gia/ffmpeg")

    def _run(cmd, **kw):
        lenh["cmd"] = list(cmd)
        return sp.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(pf.subprocess, "run", _run)
    pf._check_drawtext(settings)

    assert "-filters" not in lenh["cmd"], "chỉ hỏi danh sách là chưa kiểm gì"
    assert any("drawtext=" in x for x in lenh["cmd"]), "phải chạy thật bộ lọc"


def test_drawtext_nam_trong_bo_kiem_chung(settings, monkeypatch):
    """Thêm hàm mà quên gắn vào `run_preflight` thì người dùng không bao giờ
    thấy — đúng lớp sai 'chốt thân hàm mà quên chỗ gọi'."""
    from autodub import preflight as pf

    monkeypatch.setattr(pf.shutil, "which", lambda _x: None)
    khoa = {r.key for r in pf.run_preflight(settings)}
    assert "drawtext" in khoa
