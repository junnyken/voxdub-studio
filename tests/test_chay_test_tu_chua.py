"""Lệnh chạy test phải tự cài lại thư viện hệ thống khi máy vừa mất chúng.

Máy workspace giữ `/home/coder` trên đĩa riêng nhưng dựng lại `/usr` từ image
mỗi lần khởi động — nên `libGL`, `libxkbcommon`, `libfontconfig`, `libglib`,
`ffmpeg` biến mất đều đặn giữa hai phiên. Không phải ai xoá, mà là cách
workspace hoạt động. Đã xảy ra ít nhất ba lần (21/08, 26/08, 27/08).

`tests/test_kiem_moi_truong.py` đã ngăn được chuyện NGUY HIỂM (bộ test báo
xanh với số thấp hơn vì hàng chục tệp GUI không import nổi). Thứ còn lại chỉ
là thời gian: mỗi phiên mất một vòng "chạy test → đọc lỗi → chạy script → chạy
lại". `scripts/chay_test.sh` bỏ bước gõ tay ở giữa.

GIỚI HẠN đã biết: `--neu-thieu` phát hiện bằng cách thử nạp Qt và tìm ffmpeg,
rồi gọi `apt-get install`. Nếu tệp bị xoá tay mà sổ apt vẫn ghi "đã cài" thì
lệnh cài không làm gì (phải `--reinstall`). Ở tình huống thật — container dựng
lại — sổ apt cũng mới nên không gặp chuyện này.
"""
from __future__ import annotations

import os
import stat
import subprocess

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(ten: str) -> str:
    return open(os.path.join(REPO, ten), encoding="utf-8").read()


def test_co_lenh_chay_test_tu_chua():
    duong = os.path.join(REPO, "scripts", "chay_test.sh")
    assert os.path.isfile(duong), "thiếu lệnh chạy test tự chữa"
    assert os.stat(duong).st_mode & stat.S_IXUSR, "tệp chưa có quyền chạy"


def _lenh(ten: str) -> str:
    """Chỉ các dòng LỆNH của một script shell, bỏ chú thích và dòng trống.

    Bản đầu của hai test dưới đây so vị trí chuỗi trên nguyên văn tệp, nên
    bắt trúng chữ "pytest" và "--neu-thieu" nằm trong phần chú thích ở đầu
    tệp rồi kết luận sai thứ tự. Đây là lần thứ ba trong một ngày tôi mắc
    đúng lỗi này — dò chuỗi thô trên tệp có chú thích dài.
    """
    ra = []
    for dong in _doc(ten).splitlines():
        vet = dong.strip()
        if vet and not vet.startswith("#"):
            ra.append(dong)
    return "\n".join(ra)


def test_goi_bo_cai_truoc_khi_chay_pytest():
    lenh = _lenh("scripts/chay_test.sh")
    assert "cai_moi_truong_test.sh --neu-thieu" in lenh
    assert lenh.index("cai_moi_truong_test.sh") < lenh.index("pytest"), (
        "chạy pytest trước rồi mới chữa thì vòng lặp cũ vẫn còn nguyên")


def test_khong_cham_apt_khi_may_dang_lanh():
    """Chạy `apt-get update` mỗi lượt test là làm chậm việc thường ngày để
    phòng một chuyện hiếm."""
    lenh = _lenh("scripts/cai_moi_truong_test.sh")
    i = lenh.index("--neu-thieu")
    assert "exit 0" in lenh[i:], "không có đường thoát sớm khi đã đủ gói"
    assert lenh.index("exit 0", i) < lenh.index("apt-get update", i), (
        "chạm apt trước khi kịp thoát sớm — máy lành vẫn phải chờ")


def test_thoat_som_that_su_nhanh():
    """Đo thật, không tin vào mã: kiểm phải xong dưới 3 giây."""
    import time

    t0 = time.monotonic()
    ket = subprocess.run(
        ["bash", os.path.join(REPO, "scripts", "cai_moi_truong_test.sh"),
         "--neu-thieu"],
        capture_output=True, text=True, timeout=120)
    mat = time.monotonic() - t0
    if ket.returncode != 0:
        pytest.skip("máy đang thiếu gói — phép đo này chỉ có nghĩa khi máy lành")
    assert mat < 3.0, f"kiểm mất {mat:.1f}s, quá chậm để chạy mỗi lượt test"


def test_van_giu_chot_chan_moi_truong():
    """Lệnh tự chữa KHÔNG được thay chốt chặn — chốt đó mới là thứ ngăn bộ
    test báo xanh giả khi thiếu thư viện."""
    assert os.path.isfile(os.path.join(REPO, "tests", "test_kiem_moi_truong.py"))


def test_bo_cai_van_liet_ke_du_goi_da_tung_mat():
    """Năm gói này đều đã mất thật ít nhất một lần."""
    src = _doc("scripts/cai_moi_truong_test.sh")
    for goi in ("libgl1", "libxkbcommon", "libfontconfig1", "libglib2.0-0",
                "ffmpeg"):
        assert goi in src, f"bộ cài thiếu {goi} — gói này đã mất thật"
