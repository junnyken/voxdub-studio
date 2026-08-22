"""Bản `.exe` phát hành phải NHÚNG được địa chỉ máy chủ.

Bug thật, 22/8/2026: người dùng cài bản v3.6.0 do CI dựng, mở app lên, và máy
chủ **không thấy thiết bị nào đăng ký**. Không phải mạng, không phải khoá —
`scripts/build_exe.py` đọc `VOXDUB_API_URL` từ `.env` của máy build, mà runner
Windows của GitHub thì không có `.env`. Nên mọi bản phát hành từ trước tới nay
đều nhúng chuỗi rỗng và chạy hoàn toàn ngoại tuyến.

Nhìn từ người dùng, triệu chứng là "bấm vào không thấy gì xảy ra" — và không
có câu lỗi nào, vì với `resolve_api_url()` rỗng thì đó là chế độ chạy-thuần-
trên-máy hoàn toàn hợp lệ. Đúng loại hỏng im lặng đắt nhất.
"""
from __future__ import annotations

import importlib.util
import os

import pytest

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE_YML = os.path.join(GOC, ".github", "workflows", "release.yml")


@pytest.fixture()
def build_exe(monkeypatch, tmp_path):
    """Nạp `scripts/build_exe.py` với PROJECT_ROOT trỏ vào thư mục tạm."""
    duong = os.path.join(GOC, "scripts", "build_exe.py")
    spec = importlib.util.spec_from_file_location("build_exe_thu", duong)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("VOXDUB_API_URL", raising=False)
    return mod


def test_khong_co_env_thi_lay_tu_bien_moi_truong(build_exe, monkeypatch):
    """Đây chính là ca của runner CI: không có tệp .env nào."""
    monkeypatch.setenv("VOXDUB_API_URL", "https://may-chu.example")
    assert build_exe.read_env_value("VOXDUB_API_URL") == "https://may-chu.example"


def test_bien_moi_truong_duoc_uu_tien_hon_env(build_exe, monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("VOXDUB_API_URL=https://cua-may-nay\n",
                                   encoding="utf-8")
    monkeypatch.setenv("VOXDUB_API_URL", "https://truyen-tay")
    assert build_exe.read_env_value("VOXDUB_API_URL") == "https://truyen-tay"


def test_khong_truyen_gi_thi_van_doc_env_nhu_cu(build_exe, tmp_path):
    (tmp_path / ".env").write_text("VOXDUB_API_URL=https://cua-may-nay\n",
                                   encoding="utf-8")
    assert build_exe.read_env_value("VOXDUB_API_URL") == "https://cua-may-nay"


def test_khong_co_gi_ca_thi_tra_rong(build_exe):
    assert build_exe.read_env_value("VOXDUB_API_URL") == ""


def test_quy_trinh_phat_hanh_PHAI_truyen_dia_chi_may_chu():
    """Sửa script mà quên sửa workflow thì bản phát hành vẫn ngoại tuyến."""
    yml = open(RELEASE_YML, encoding="utf-8").read()
    assert "VOXDUB_API_URL" in yml, (
        "release.yml không truyền VOXDUB_API_URL — bản exe phát hành sẽ nhúng "
        "chuỗi rỗng và chạy ngoại tuyến, y như bug ngày 22/8/2026")
    # Cắt ở đúng DÒNG CHẠY, không phải chữ "scripts/build_exe.py" đầu tiên —
    # chữ đó còn nằm trong lời chú thích ở đầu tệp (bẫy C8: khớp phải chú
    # thích thì đỏ oan, và bản đầu của chính test này đã dính).
    truoc_build = yml.split("run: python scripts/build_exe.py", 1)[0]
    assert "VOXDUB_API_URL" in truoc_build, (
        "biến phải được đặt TRƯỚC bước chạy build_exe.py mới có tác dụng")
