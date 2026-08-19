"""V86 — vì sao "Không tách được nhạc nền" trên MỌI bản đóng gói.

Người dùng báo (2026-08-19, v3.4.8): bước Tách nhạc nền báo lỗi, video ra chỉ
còn giọng đọc.

Nguyên nhân: `autodub.spec` CỐ Ý loại torch/demucs/soundfile (nặng hàng GB) —
Demucs chạy trong venv riêng `.venv-gpu` qua `demucs_worker.py`. Nhưng **chưa
từng có script nào tạo venv đó**: 11 tệp `scripts/setup_*.py` trong repo,
không tệp nào cho Demucs; tài liệu chỉ nhắc tên `.venv-gpu` như thể nó tự có.

Cùng hình dạng với V80 (worker không được đóng gói), V83 (`icons.brand_logo`
không tồn tại), V84 (kho GitHub không tồn tại): **đường dẫn thì có, thứ ở đầu
kia thì không**.
"""
from __future__ import annotations

import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_co_script_cai_demucs():
    assert os.path.isfile(os.path.join(REPO, "scripts", "setup_demucs.py"))


def test_script_tao_dung_ten_venv_ma_app_di_tim():
    """`gpu_venv_dir()` tìm `.venv-gpu`; script tạo tên khác là cài xong vẫn
    hỏng y như cũ."""
    from autodub.utils import GPU_VENVS

    src = open(os.path.join(REPO, "scripts", "setup_demucs.py"),
               encoding="utf-8").read()
    assert any(ten in src for ten in GPU_VENVS)


def test_ban_dong_goi_chep_ca_script_lan_bat():
    src = open(os.path.join(REPO, "scripts", "build_exe.py"),
               encoding="utf-8").read()
    assert "setup_demucs.py" in src, "quên chép script vào bản phát hành"
    assert "SETUP_DEMUCS_BAT" in src, "quên tệp .bat để đúp chuột"
    assert "Cai dat tach nhac nen (Demucs).bat" in src


def test_thong_bao_loi_chi_dung_tep_can_bam():
    """Trước V86 thông báo chỉ nói "video sẽ chỉ còn giọng đọc" — đúng nhưng
    người dùng không biết phải làm gì tiếp."""
    import logging

    from autodub_gui.log_text import notice_for

    line = notice_for("Demucs separation failed: hết VRAM; falling back to "
                      "silent base.", logging.WARNING)
    assert line is not None
    assert "Cai dat tach nhac nen (Demucs).bat" in line[0]


def test_muon_duoc_venv_torch_cua_ban_cu(tmp_path, monkeypatch):
    """venv này nặng tới ~2,5 GB — nâng cấp mà bắt tải lại là quá đáng."""
    from autodub import venv_discovery

    venv_discovery.quen_cache()
    cu = tmp_path / "VoxDub-cu" / ".venv-gpu"
    exe = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    py = cu / exe
    py.parent.mkdir(parents=True)
    py.write_text("")
    moi = tmp_path / "VoxDub-moi"
    moi.mkdir()
    monkeypatch.setattr("autodub.utils.app_root", lambda: str(moi))
    monkeypatch.setattr("autodub.venv_discovery.app_root", lambda: str(moi))

    from autodub.utils import gpu_venv_dir

    assert gpu_venv_dir() == str(cu)
    venv_discovery.quen_cache()


def test_khong_co_ban_cu_thi_tra_rong(tmp_path, monkeypatch):
    from autodub import venv_discovery

    venv_discovery.quen_cache()
    moi = tmp_path / "VoxDub-moi"
    moi.mkdir()
    monkeypatch.setattr("autodub.utils.app_root", lambda: str(moi))
    monkeypatch.setattr("autodub.venv_discovery.app_root", lambda: str(moi))

    from autodub.utils import gpu_venv_dir

    assert gpu_venv_dir() == ""
    venv_discovery.quen_cache()
