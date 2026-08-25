"""V91 — nâng cấp không được làm mất cài đặt (khoá API, token đăng nhập).

Bối cảnh: `.venv-*`, `models/` và `bin/` đã biết tự tìm lại bản cài cũ nằm
cạnh bên (V77/V81), riêng `.env` thì chưa — nên mỗi lần lên phiên bản là phải
khai báo lại từ đầu. Bộ test này giữ ba điều:

1. Tìm được `.env` của bản cũ cạnh bên.
2. Không nhận tệp rỗng, không nhận chính thư mục đang chạy.
3. Lúc khởi động phải CHÉP sang (không đọc nhờ) và ưu tiên hơn `.env.example`.
"""
from __future__ import annotations

import os

import pytest

from autodub import venv_discovery as vd
from tests import doc_ma


@pytest.fixture
def moi_truong(tmp_path, monkeypatch):
    """Dựng một thư mục cha có bản cũ và bản mới nằm cạnh nhau."""
    cu = tmp_path / "VoxDub-v3.8.7"
    moi = tmp_path / "VoxDub-v3.8.8"
    cu.mkdir()
    moi.mkdir()
    monkeypatch.setattr(vd, "app_root", lambda: str(moi))
    vd.quen_cache()
    yield cu, moi
    vd.quen_cache()


def test_tim_duoc_env_cua_ban_cu(moi_truong):
    cu, _ = moi_truong
    (cu / ".env").write_text("VOX_TOKEN=abc\n", encoding="utf-8")
    assert vd.tim_env_cu() == str(cu / ".env")


def test_khong_co_ban_cu_thi_tra_rong(moi_truong):
    assert vd.tim_env_cu() == ""


def test_bo_qua_env_rong(moi_truong):
    """Tệp rỗng không phải cài đặt — nhận vào chỉ khiến người dùng tưởng còn."""
    cu, _ = moi_truong
    (cu / ".env").write_text("", encoding="utf-8")
    assert vd.tim_env_cu() == ""


def test_khong_lay_env_cua_chinh_minh(moi_truong):
    """Thư mục đang chạy đã có .env thì đó không phải 'bản cũ'."""
    _, moi = moi_truong
    (moi / ".env").write_text("VOX_TOKEN=xyz\n", encoding="utf-8")
    assert vd.tim_env_cu() == ""


def test_nhieu_ban_cu_thi_lay_ban_sua_gan_nhat(moi_truong, tmp_path):
    cu, _ = moi_truong
    cu2 = tmp_path / "VoxDub-v3.8.2"
    cu2.mkdir()
    (cu / ".env").write_text("VOX_TOKEN=cu\n", encoding="utf-8")
    (cu2 / ".env").write_text("VOX_TOKEN=moi_hon\n", encoding="utf-8")
    os.utime(cu / ".env", (1_000, 1_000))
    os.utime(cu2 / ".env", (2_000, 2_000))
    assert vd.tim_env_cu() == str(cu2 / ".env")


def _than_main() -> str:
    """Mã nguồn của riêng hàm ``main`` trong app.py.

    Đọc bằng AST chứ không import: nạp ``autodub_gui.app`` kéo theo PySide6 và
    cả một cửa sổ Qt — test này chỉ cần đọc mã. Cắt theo AST cũng để không
    lẫn sang hàm kế tiếp (bài học từ những lần cắt theo số ký tự).
    """
    import ast

    nguon = open("autodub_gui/app.py", encoding="utf-8").read()
    for nut in ast.parse(nguon).body:
        if isinstance(nut, ast.FunctionDef) and nut.name == "main":
            return ast.get_source_segment(nguon, nut) or ""
    raise AssertionError("app.py không còn hàm main")


def test_khoi_dong_chep_env_cu_va_uu_tien_hon_ban_mau():
    """Khởi động phải tìm .env của bản cũ TRƯỚC khi ngã sang .env.example, và
    phải CHÉP sang — đọc nhờ sẽ khiến lần Lưu đầu tiên trên màn hình Cài đặt
    xoá trắng những khoá không hiện ra ở đó."""
    than = _than_main()
    assert "tim_env_cu" in than, "khởi động không hề tìm .env của bản cũ"
    assert than.index("tim_env_cu()") < than.index("_env_example if"), \
        "bản mẫu trống được ưu tiên hơn cài đặt thật của bản cũ"
    assert "_shutil.copy(_nguon" in than, "phải chép sang, không được đọc nhờ"


def test_cli_van_muon_duoc_env_cu_khi_khong_qua_giao_dien():
    """Bản chạy dòng lệnh/worker không đi qua app.py nên config.py phải tự lo."""
    import ast

    nguon = open("autodub/config.py", encoding="utf-8").read()
    assert "tim_env_cu" in nguon, "config.py không có đường lui nào cho .env"
    ast.parse(nguon)  # đảm bảo phần vừa chèn không làm hỏng cú pháp
