"""Bộ canh cho chốt "máy có đủ thứ để chạy test không".

Hai thứ được giữ ở đây:

1. **Danh sách gói không được trôi khỏi CI.** CI thêm một gói mà quên thêm
   vào script cài thì máy phát triển lại thiếu — đúng vòng lặp đã tốn một
   buổi tối. Script được phép NHIỀU HƠN CI (máy chạy CI của GitHub có sẵn
   `libfontconfig1`/`libfreetype6`, workspace trần thì không), nhưng không
   được thiếu.
2. **Câu lỗi phải dùng được.** Một câu "thiếu thư viện" mà không nói thiếu gì,
   chữa bằng lệnh nào thì cũng chỉ bằng 24 lỗi import cũ.
"""
from __future__ import annotations

import re

from tests import kiem_moi_truong as km

CI = ".github/workflows/test.yml"
SCRIPT = "scripts/cai_moi_truong_test.sh"


def _goi_trong_ci() -> set[str]:
    noi_dung = open(CI, encoding="utf-8").read()
    khoi = noi_dung.split("apt-get install -y --no-install-recommends", 1)[1]
    goi: set[str] = set()
    for dong in khoi.splitlines()[1:]:
        tiep_tuc = dong.rstrip().endswith("\\")
        goi.update(t for t in dong.replace("\\", "").split() if t)
        if not tiep_tuc:
            break
    return goi


def _goi_trong_script() -> set[str]:
    than = open(SCRIPT, encoding="utf-8").read().split("GOI=(", 1)[1].split("\n)", 1)[0]
    # Bỏ chú thích trước khi đọc tên gói — chữ trong chú thích không phải gói.
    sach = re.sub(r"#.*", "", than)
    return {t for t in sach.split() if t}


def test_script_cai_du_moi_goi_CI_dang_cai():
    thieu = _goi_trong_ci() - _goi_trong_script()
    assert not thieu, (
        f"CI cài {sorted(thieu)} mà {SCRIPT} không có — máy phát triển sẽ "
        "thiếu đúng mấy gói đó")


def test_script_co_ffmpeg_va_libgl():
    """Hai thứ đã hỏng thật, phải có tên trong script."""
    goi = _goi_trong_script()
    assert "ffmpeg" in goi
    assert "libgl1" in goi


def test_thieu_ffmpeg_thi_bat_duoc(monkeypatch):
    monkeypatch.setattr(km.shutil, "which", lambda _ten: None)
    assert "ffmpeg" in km.thieu_ffmpeg()


def test_co_ffmpeg_thi_im_lang(monkeypatch):
    monkeypatch.setattr(km.shutil, "which", lambda _ten: "/usr/bin/ffmpeg")
    assert km.thieu_ffmpeg() == ""


def test_cau_loi_noi_ro_thieu_gi_va_chua_bang_lenh_nao():
    chu = km.loi_nhan(["không tìm thấy lệnh «ffmpeg» trong PATH"])
    assert "ffmpeg" in chu
    assert km.SCRIPT_SUA in chu, "không nói câu lệnh chữa thì người đọc vẫn kẹt"
    assert km.BIEN_BO_QUA in chu, "phải nói cả lối thoát"


def test_co_loi_thoat_bang_bien_moi_truong(monkeypatch):
    """Chạy một nhóm test không cần Qt/ffmpeg vẫn phải chạy được."""
    monkeypatch.setattr(km, "thieu_gi", lambda: ["giả vờ thiếu"])
    monkeypatch.setenv(km.BIEN_BO_QUA, "1")
    assert km.kiem_hoac_dung() == ""


def test_khong_dat_bien_thi_van_chan(monkeypatch):
    monkeypatch.setattr(km, "thieu_gi", lambda: ["giả vờ thiếu"])
    monkeypatch.delenv(km.BIEN_BO_QUA, raising=False)
    assert km.kiem_hoac_dung() != ""


def test_conftest_that_su_goi_chot_nay():
    """Gỡ lượt gọi khỏi conftest thì mọi test khác vẫn xanh — nên phải có
    thứ canh chính lượt gọi đó.

    Hỏi CÂY CÚ PHÁP, không tìm chuỗi (bài học C8).
    """
    import tests.conftest as cf

    from tests.doc_ma import co_goi

    assert co_goi(cf.pytest_configure, "kiem_hoac_dung"), (
        "pytest_configure không còn kiểm môi trường — máy thiếu thư viện sẽ "
        "lại nôn ra hàng chục lỗi import rời rạc")
