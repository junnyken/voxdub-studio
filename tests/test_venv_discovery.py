"""V77 — nâng cấp lên thư mục mới không còn mất bộ nghe đã cài.

`.venv-whisper` / `.venv-asr` / `.venv-vieneu` và `models/` nằm TRONG thư mục
ứng dụng, nên cách nâng cấp duy nhất (giải nén bản mới ra thư mục khác) làm
app báo "chưa cài" dù người dùng đã cài từ lâu — chữa bằng tay là chép 2 thư
mục hoặc tải lại ~1,5 GB model. Lời than có thật, lặp ở MỌI lần lên phiên bản.

Giờ app tự dò các thư mục nằm CẠNH nó (chính là các bản cũ) và dùng lại tại
chỗ. Ba ràng buộc được khoá ở đây: không đè cài đặt tay, không nhận bản cài
dở, và không quét đĩa vô tội vạ.
"""
from __future__ import annotations

import os

import pytest

from autodub import venv_discovery
from autodub.config import Settings


@pytest.fixture(autouse=True)
def _sach():
    venv_discovery.quen_cache()
    yield
    venv_discovery.quen_cache()


def _dung_ban_cai(thu_muc, ten_venv=".venv-whisper", ten_model="whisper",
                  du=True):
    """Dựng một thư mục VoxDub đã cài xong (hoặc cài dở nếu du=False)."""
    thu_muc.mkdir(parents=True, exist_ok=True)
    exe = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    py = thu_muc / ten_venv / exe
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text("")
    md = thu_muc / "models" / ten_model
    md.mkdir(parents=True, exist_ok=True)
    if du:
        (md / "installed_ok.json").write_text("{}")
    return str(py), str(md)


def _lam_app_moi(tmp_path, monkeypatch, ten="VoxDub-Studio-v3.4.4"):
    """Bản MỚI vừa giải nén: thư mục trống trơn, chưa cài gì."""
    goc = tmp_path / ten
    goc.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("autodub.utils.app_root", lambda: str(goc))
    monkeypatch.setattr("autodub.config.app_root", lambda: str(goc))
    monkeypatch.setattr("autodub.venv_discovery.app_root", lambda: str(goc))
    return goc


def test_ban_moi_dung_duoc_bo_nghe_cua_ban_cu(tmp_path, monkeypatch):
    """Đúng cảnh người dùng gặp: giải nén bản mới cạnh bản cũ."""
    py_cu, md_cu = _dung_ban_cai(tmp_path / "VoxDub-Studio-v3.4.2")
    _lam_app_moi(tmp_path, monkeypatch)

    st = Settings()
    assert st.whisper_venv_configured(), "phải thấy bộ nghe của bản cũ"
    assert st.whisper_venv_python_path() == py_cu
    assert st.whisper_model_dir_path() == md_cu


def test_khong_co_ban_cu_thi_van_bao_chua_cai(tmp_path, monkeypatch):
    """Máy mới tinh — không được nhận bừa thư mục nào."""
    goc = _lam_app_moi(tmp_path, monkeypatch)
    (tmp_path / "Downloads").mkdir()

    st = Settings()
    assert not st.whisper_venv_configured()
    # Vẫn trả về đường dẫn MẶC ĐỊNH để lời khuyên "bấm .bat" cài đúng chỗ.
    assert str(goc) in st.whisper_venv_python_path()


def test_khong_nhan_ban_cai_do_dang(tmp_path, monkeypatch):
    """Có venv nhưng thiếu marker = cài dở. Dùng nó còn tệ hơn báo chưa cài."""
    _dung_ban_cai(tmp_path / "VoxDub-cu", du=False)
    _lam_app_moi(tmp_path, monkeypatch)

    assert not Settings().whisper_venv_configured()


def test_cai_dat_tay_khong_bao_gio_bi_de(tmp_path, monkeypatch):
    """Người dùng tự trỏ đường dẫn trong Cài đặt — bản cũ không được chen."""
    _dung_ban_cai(tmp_path / "VoxDub-cu")
    _lam_app_moi(tmp_path, monkeypatch)

    st = Settings()
    st.whisper_venv_python = "/duong/dan/tay/python"
    st.whisper_model_dir = "/duong/dan/tay/models"
    assert st.whisper_venv_python_path() == "/duong/dan/tay/python"
    assert st.whisper_model_dir_path() == "/duong/dan/tay/models"


def test_thu_muc_hien_tai_thang_ban_cu(tmp_path, monkeypatch):
    """Đã cài ngay trong thư mục hiện tại thì không được đi mượn nơi khác."""
    _dung_ban_cai(tmp_path / "VoxDub-cu")
    goc = _lam_app_moi(tmp_path, monkeypatch)
    py_moi, md_moi = _dung_ban_cai(goc)

    st = Settings()
    assert st.whisper_venv_python_path() == py_moi
    assert st.whisper_model_dir_path() == md_moi


def test_nhieu_ban_cu_thi_lay_ban_moi_nhat(tmp_path, monkeypatch):
    """Người dùng thường giữ vài bản cũ chồng nhau."""
    _py_cu, md_cu = _dung_ban_cai(tmp_path / "VoxDub-v3.3.0")
    _py_moi, md_moi = _dung_ban_cai(tmp_path / "VoxDub-v3.4.2")
    # Dìm bản 3.3.0 về quá khứ thay vì đẩy bản 3.4.2 lên tương lai — đặt mốc
    # thời gian tương lai làm test tự sai theo cách khó thấy.
    os.utime(os.path.join(md_cu, "installed_ok.json"), (1_000_000, 1_000_000))
    _lam_app_moi(tmp_path, monkeypatch)

    assert Settings().whisper_model_dir_path() == md_moi

    # Và tên thư mục in ra Nhật ký phải là tên BẢN CŨ, không phải tên venv.
    venv_discovery.quen_cache()
    import logging
    tin = []
    logging.getLogger("autodub.venv").addHandler(
        type("H", (logging.Handler,), {"emit": lambda s, r: tin.append(r.getMessage())})())
    Settings().whisper_model_dir_path()
    assert any("VoxDub-v3.4.2" in m for m in tin), tin


def test_paraformer_va_vieneu_cung_duoc_cuu(tmp_path, monkeypatch):
    """Cùng một cảnh ngộ — sửa một chỗ phải cứu cả ba bộ máy."""
    _dung_ban_cai(tmp_path / "VoxDub-cu", ".venv-asr", "paraformer-zh")
    _dung_ban_cai(tmp_path / "VoxDub-cu", ".venv-vieneu", "vieneu")
    _lam_app_moi(tmp_path, monkeypatch)

    st = Settings()
    assert st.paraformer_configured()
    assert st.vieneu_configured()


def test_khong_quet_qua_nhieu_thu_muc(tmp_path, monkeypatch):
    """App có thể nằm trong Downloads với hàng trăm thư mục — quét vô hạn ở
    đó là treo app lúc khởi động."""
    for i in range(120):
        (tmp_path / f"thu-muc-{i:03d}").mkdir()
    _lam_app_moi(tmp_path, monkeypatch, ten="zzz-app")

    dem = {"n": 0}
    that = os.path.isfile

    def _dem(p):
        dem["n"] += 1
        return that(p)

    monkeypatch.setattr(os.path, "isfile", _dem)
    Settings().whisper_venv_configured()
    assert dem["n"] < 200, f"{dem['n']} lần chạm đĩa — quá nhiều"


def test_ket_qua_co_nho_dem(tmp_path, monkeypatch):
    """whisper_venv_configured() bị gọi rất nhiều lần; quét lại mỗi lần là
    tự tay làm app chậm."""
    _dung_ban_cai(tmp_path / "VoxDub-cu")
    _lam_app_moi(tmp_path, monkeypatch)

    dem = {"n": 0}
    that = os.scandir

    def _dem(p):
        dem["n"] += 1
        return that(p)

    monkeypatch.setattr(os, "scandir", _dem)
    st = Settings()
    for _ in range(5):
        st.whisper_venv_configured()
    assert dem["n"] == 1, f"quét đĩa {dem['n']} lần cho 5 lượt hỏi"


def test_nhat_ky_noi_ro_dang_muon_bo_cua_ban_cu(tmp_path, monkeypatch):
    """Im lặng dùng thư mục khác là thứ người dùng không đoán được — dòng
    này phải qua được allowlist của khung Nhật ký."""
    import logging

    from autodub_gui.log_text import notice_for

    line = notice_for(
        "Dùng lại bộ đã cài của bản trước ở thư mục: VoxDub-Studio-v3.4.2",
        logging.INFO)
    assert line is not None
    assert "VoxDub-Studio-v3.4.2" in line[0]
