"""V80 — bộ cài phải từ chối Python quá mới thay vì chết giữa lúc build wheel.

Người dùng báo bằng ảnh chụp (2026-08-19, v3.4.4): cài giọng VieNeu gãy với
`failed-wheel-build-for-install → kaldi-native-fbank`. Traceback cho thấy
tiến trình đang chạy là **Python 3.14** — các gói ONNX/ASR chưa có wheel cho
bản đó nên pip quay ra build từ mã nguồn rồi gãy.

Tệp .bat đã thử `py -3.12` trước, nhưng vẫn thủng ở hai cảnh có thật: máy có
3.12 mà `py -3.12` không tìm ra (Python Install Manager kiểu
`pythoncore-3.14-64`), và venv của lần chạy trước đã tạo bằng 3.14 nên mọi
lần cài sau đều "venv đã có — bỏ qua" rồi cài tiếp vào venv hỏng.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")


def _nap(ten: str):
    spec = importlib.util.spec_from_file_location(
        ten, os.path.join(SCRIPTS, f"{ten}.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[ten] = mod
    spec.loader.exec_module(mod)
    return mod


ho_tro = _nap("_python_ho_tro")


@pytest.mark.parametrize("ban,ok", [
    ((3, 9), False),    # quá cũ
    ((3, 10), True),
    ((3, 12), True),
    ((3, 13), False),
    ((3, 14), False),   # đúng bản làm người dùng gãy
])
def test_khoang_ban_python_duoc_ho_tro(ban, ok):
    assert ho_tro._ban_nay_ok(ban) is ok


def test_khong_tim_duoc_python_dung_thi_dung_som_va_noi_ro(monkeypatch):
    """Chết ở đây (1 dòng dễ hiểu) tốt hơn chết trong pip (mấy chục dòng)."""
    monkeypatch.setattr(ho_tro, "_ban_nay_ok", lambda *a: False)
    monkeypatch.setattr(ho_tro, "_tim_python_khac", lambda: "")

    with pytest.raises(SystemExit) as e:
        ho_tro.bao_dam_python_ho_tro()
    loi = str(e.value)
    assert "3.12" in loi and "python.org" in loi
    assert "wheel" not in loi.lower(), "đừng ném từ kỹ thuật vào mặt người dùng"


def test_tim_thay_ban_khac_thi_tu_chay_lai(monkeypatch, tmp_path):
    """Máy có 3.12 nhưng .bat lỡ chạy bằng 3.14 — phải tự chuyển, không bắt
    người dùng gõ lệnh."""
    monkeypatch.setattr(ho_tro, "_ban_nay_ok", lambda *a: False)
    monkeypatch.setattr(ho_tro, "_tim_python_khac", lambda: "/python/3.12")
    goi = {}

    def _chay(cmd, *a, **k):
        goi["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(ho_tro.subprocess, "run", _chay)
    with pytest.raises(SystemExit) as e:
        ho_tro.bao_dam_python_ho_tro()
    assert e.value.code == 0
    assert goi["cmd"][0] == "/python/3.12"


def test_ban_dang_chay_hop_le_thi_khong_lam_gi(monkeypatch):
    monkeypatch.setattr(ho_tro, "_ban_nay_ok", lambda *a: True)
    monkeypatch.setattr(ho_tro, "_tim_python_khac",
                        lambda: pytest.fail("không được dò tìm khi đã hợp lệ"))
    ho_tro.bao_dam_python_ho_tro()


def test_doc_dung_phien_ban_cua_mot_venv_that():
    """Kiểm bằng chính trình thông dịch đang chạy — không mock."""
    ok = ho_tro.venv_dung_python_ho_tro(sys.executable)
    assert ok is ho_tro._ban_nay_ok(sys.version_info[:2])


def test_venv_khong_ton_tai_thi_khong_hop_le():
    assert ho_tro.venv_dung_python_ho_tro("/khong/co/python") is False


def test_venv_cu_tao_bang_python_qua_moi_thi_bi_dung_lai(tmp_path,
                                                         monkeypatch):
    """Đúng cảnh của người dùng: chạy lại .bat sau khi đã cài Python 3.12,
    nhưng venv 3.14 của lần trước vẫn nằm đó."""
    sw = _nap("setup_whisper")
    venv_dir = tmp_path / ".venv-whisper"
    (venv_dir / "bin").mkdir(parents=True)
    (venv_dir / "bin" / "python").write_text("")
    monkeypatch.setattr(sw, "VENV_DIR", str(venv_dir))
    monkeypatch.setattr(sw, "VENV_PY", str(venv_dir / "bin" / "python"))
    monkeypatch.setattr(sw, "venv_dung_python_ho_tro", lambda p: False)
    tao_lai = {}
    monkeypatch.setattr(sw.subprocess, "run",
                        lambda cmd, **k: tao_lai.setdefault("cmd", cmd))

    sw.step_venv()

    assert "venv" in tao_lai["cmd"], "phải dựng lại venv"
    assert tao_lai["cmd"][0] == sys.executable


def test_venv_dung_ban_hop_le_thi_giu_nguyen(tmp_path, monkeypatch):
    sw = _nap("setup_whisper")
    venv_dir = tmp_path / ".venv-whisper"
    (venv_dir / "bin").mkdir(parents=True)
    (venv_dir / "bin" / "python").write_text("")
    monkeypatch.setattr(sw, "VENV_DIR", str(venv_dir))
    monkeypatch.setattr(sw, "VENV_PY", str(venv_dir / "bin" / "python"))
    monkeypatch.setattr(sw, "venv_dung_python_ho_tro", lambda p: True)
    monkeypatch.setattr(sw.subprocess, "run",
                        lambda *a, **k: pytest.fail("đừng dựng lại venv tốt"))

    sw.step_venv()
    assert (venv_dir / "bin" / "python").exists()


@pytest.mark.parametrize("ten", ["setup_whisper", "setup_vieneu",
                                 "setup_paraformer"])
def test_ca_ba_bo_cai_deu_kiem_phien_ban(ten):
    src = open(os.path.join(SCRIPTS, f"{ten}.py"), encoding="utf-8").read()
    assert "bao_dam_python_ho_tro()" in src, f"{ten} chưa kiểm phiên bản"
    assert "venv_dung_python_ho_tro" in src, f"{ten} chưa kiểm venv cũ"


def test_module_dung_chung_duoc_chep_vao_ban_dong_goi():
    """Quên chép là bản .exe chết ngay dòng import — tệ hơn lỗi đang sửa."""
    src = open(os.path.join(SCRIPTS, "build_exe.py"), encoding="utf-8").read()
    assert "_python_ho_tro.py" in src
