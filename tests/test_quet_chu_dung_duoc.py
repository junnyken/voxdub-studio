"""Quét chữ tự động: lấy mẫu cả video, dừng được, hết giờ theo số khung (C49).

Ba chỗ hỏng thật trước C49:

1. Ba mốc lấy mẫu viết chết 1s/5s/15s — video 40 phút chỉ được quét **15 giây
   đầu**, nên chữ cháy xuất hiện từ phút thứ hai trở đi không bao giờ thấy.
   Chính chú thích trong mã cũ cũng thừa nhận đó là "ước lượng thô".
2. Không có đường dừng: quét video dài mất hàng chục giây, muốn thoát chỉ còn
   cách tắt cả hộp thoại — mất luôn mọi vùng đã vẽ tay (FEATURES §5.2).
3. Hết giờ 60 giây CỨNG cho cả lượt, dù quét bao nhiêu khung. Hết giờ thì lời
   báo nói "worker không chạy được" — sai hẳn nguyên nhân.
"""
from __future__ import annotations

import subprocess
import threading

import pytest

from autodub.media import text_regions


# ------------------------------------------------ hết giờ theo số khung -----

def test_han_gio_tang_theo_so_khung():
    mot = text_regions._han_gio(1)
    nam = text_regions._han_gio(5)
    assert nam > mot, "quét 5 khung mà vẫn dùng hạn của 1 khung là hết giờ oan"
    assert mot >= 60, "hạn cho một khung không được thấp hơn mốc 60 giây cũ"


def test_han_gio_khung_0_van_hop_le():
    assert text_regions._han_gio(0) == text_regions._han_gio(1)


# --------------------------------------------------------- dừng được -------

class _SettingsGia:
    @staticmethod
    def ocr_configured():
        return True

    @staticmethod
    def ocr_venv_python_path():
        return "python3"


def test_bam_dung_thi_giet_tien_trinh_con_va_tra_ve_rong(monkeypatch, tmp_path):
    """`subprocess.run` chặn cứng tới khi xong — bấm Dừng không có tác dụng gì.
    Nên đường có huỷ phải dùng Popen + ngó cờ huỷ."""
    huy = threading.Event()
    huy.set()   # người dùng bấm Dừng ngay từ đầu

    da_giet = {"co": False}

    class _ProcGia:
        returncode = None

        def communicate(self, timeout=None):
            if timeout is not None and not da_giet["co"]:
                raise subprocess.TimeoutExpired("cmd", timeout)
            return ("", "")

        def kill(self):
            da_giet["co"] = True

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: _ProcGia())
    monkeypatch.setattr(text_regions, "bundled_file", lambda *a: "w.py",
                        raising=False)
    ket = text_regions._detect_via_subprocess(
        [str(tmp_path / "a.png")], _SettingsGia(), cancel_event=huy)
    assert da_giet["co"], "không giết tiến trình con thì OCR vẫn chạy ngầm"
    assert ket == [], "bị huỷ phải trả rỗng, KHÔNG phải None (None = rơi về in-process)"


def test_khong_truyen_cancel_thi_hanh_vi_cu_giu_nguyen(monkeypatch, tmp_path):
    goi = {}

    def _run_gia(cmd, **kw):
        goi.update(kw)
        return subprocess.CompletedProcess(cmd, 0, '{"ok": true, "boxes": []}', "")

    monkeypatch.setattr(subprocess, "run", _run_gia)
    monkeypatch.setattr(text_regions, "bundled_file", lambda *a: "w.py",
                        raising=False)
    text_regions._detect_via_subprocess([str(tmp_path / "a.png")], _SettingsGia())
    assert "timeout" in goi, "vẫn phải có hạn giờ khi không có đường huỷ"


# ------------------------------------- lấy mẫu rải đều theo thời lượng ------

@pytest.fixture()
def worker(monkeypatch):
    pytest.importorskip("PySide6")
    from autodub_gui import style_dialog

    return style_dialog._OcrWorker, style_dialog


def test_moc_lay_mau_rai_deu_ca_video_dai(worker, monkeypatch):
    lop, mod = worker
    monkeypatch.setattr("autodub.media.video.probe_duration_s", lambda _p: 2400.0)
    w = lop("phim.mp4", None)
    moc = w._moc_lay_mau()
    assert len(moc) == lop.SO_KHUNG
    assert moc == sorted(moc)
    assert moc[-1] > 2000, (
        f"video 40 phút mà mốc cuối chỉ {moc[-1]:.0f}s — vẫn chỉ quét đoạn đầu")
    assert moc[0] > 0


def test_video_ngan_khong_lay_mau_ngoai_thoi_luong(worker, monkeypatch):
    lop, _ = worker
    monkeypatch.setattr("autodub.media.video.probe_duration_s", lambda _p: 8.0)
    moc = lop("ngan.mp4", None)._moc_lay_mau()
    assert max(moc) < 8.0, "trích khung ở giây vượt quá video là hỏng cả mẫu"


def test_khong_doc_duoc_thoi_luong_thi_giu_nep_cu(worker, monkeypatch):
    lop, _ = worker
    monkeypatch.setattr("autodub.media.video.probe_duration_s", lambda _p: None)
    assert lop("hong.mp4", None)._moc_lay_mau() == [1.0, 5.0, 15.0]
