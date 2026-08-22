"""Chưa cài VieNeu thì phải nói "chưa cài" (22/8/2026).

Người dùng nâng cấp sang thư mục mới, chạy lồng tiếng, và nhận nguyên văn:

    VieNeu worker failed to start: {'ready': False, 'error':
    "ModuleNotFoundError: No module named 'vieneu'"}

Câu đó đúng về mặt kỹ thuật và vô dụng với người đọc: họ không biết phải cài
gì, cài bằng cách nào, hay đây có phải lỗi của ứng dụng không.

Kiểm bằng DẤU HIỆU CÀI XONG trên đĩa chứ không thử import — bài học V74: bản
đóng gói không mang theo mấy gói nặng đó nên import trong tiến trình chính
luôn trả lời sai.
"""
from __future__ import annotations

import pytest

from autodub.speech.tts import vieneu_vi


class _ChuSoHuu:
    def __init__(self, settings):
        self.settings = settings
        self.voice_name = "giong-thu"
        self.intra_threads = 1


class _SettingsGia:
    def __init__(self, da_cai: bool):
        self._da_cai = da_cai
        self.vieneu_style = "tu-nhien"

    def vieneu_configured(self):
        return self._da_cai

    def vieneu_venv_python_path(self):
        return "/khong-co/python"

    def vieneu_model_dir_path(self):
        return "/khong-co/models"

    def vieneu_custom_voices_path(self):
        return "/khong-co/custom.json"


def _worker(da_cai: bool):
    w = vieneu_vi._VieNeuWorker.__new__(vieneu_vi._VieNeuWorker)
    w._owner = _ChuSoHuu(_SettingsGia(da_cai))
    w._idx = 0
    return w


def test_chua_cai_thi_noi_ro_phai_chay_tep_nao():
    with pytest.raises(RuntimeError) as loi:
        _worker(False)._start()

    chu = str(loi.value)
    assert "Chưa cài" in chu
    assert "Cai dat giong VieNeu.bat" in chu, "không chỉ ra tệp thì người đọc vẫn kẹt"
    assert "ModuleNotFoundError" not in chu


def test_chua_cai_thi_KHONG_khoi_dong_tien_trinh_con(monkeypatch):
    """Chạy rồi mới báo lỗi là để người dùng chờ vô ích."""
    monkeypatch.setattr(vieneu_vi.subprocess, "Popen",
                        lambda *a, **k: pytest.fail("đã cố khởi động worker"))
    with pytest.raises(RuntimeError):
        _worker(False)._start()


def test_da_cai_thi_van_di_tiep_nhu_cu(monkeypatch):
    """Chốt đối lập: cài rồi mà vẫn chặn là chặn nhầm người."""
    goi = {}
    monkeypatch.setattr(vieneu_vi.subprocess, "Popen",
                        lambda *a, **k: goi.setdefault("chay", True))
    with pytest.raises(Exception):  # noqa: B017 — hỏng ở bước sau, không sao
        _worker(True)._start()
    assert goi.get("chay"), "đã cài rồi mà không chạy tới bước khởi động"
