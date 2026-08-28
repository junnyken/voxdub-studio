"""Cổng kiểm trước phát hành phải còn nguyên ở đúng chỗ (mini-spec C45).

Bài học của chính dự án này: tài liệu không sửa được lỗi con người, phải biến
quy tắc thành thứ máy tự kiểm. Một cổng kiểm bị gỡ (hoặc bị đẩy xuống SAU bước
phát hành) thì im lặng như chưa từng có — đúng kiểu hỏng mà không ai thấy cho
tới lượt phát hành hỏng tiếp theo.
"""
from __future__ import annotations

import os
import re

import pytest

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KICH_BAN = "scripts/kiem_chay_that.py"


def _doc(ten: str) -> str:
    return open(os.path.join(GOC, ten), encoding="utf-8").read()


@pytest.fixture(scope="module")
def release_yml() -> str:
    return _doc(".github/workflows/release.yml")


def test_kich_ban_kiem_chay_that_ton_tai():
    assert os.path.isfile(os.path.join(GOC, KICH_BAN))


def test_cong_kiem_nam_TRUOC_buoc_phat_hanh(release_yml):
    """Đặt sau bước phát hành thì bản hỏng đã lên mạng rồi mới biết."""
    vi_tri_kiem = release_yml.find("kiem_chay_that.py")
    vi_tri_phat_hanh = release_yml.find("Publish GitHub Release")
    assert vi_tri_kiem != -1, "release.yml không còn gọi cổng kiểm chạy thật"
    assert vi_tri_phat_hanh != -1
    assert vi_tri_kiem < vi_tri_phat_hanh, (
        "cổng kiểm nằm SAU bước phát hành — chặn không kịp gì cả")


def test_cong_kiem_khong_bi_tat_bang_continue_on_error(release_yml):
    """`continue-on-error: true` biến cổng chặn thành đèn trang trí."""
    khoi = release_yml[release_yml.find("kiem_chay_that.py") - 800:
                       release_yml.find("Publish GitHub Release")]
    assert "continue-on-error" not in khoi


def test_lo_chay_that_dung_ngon_ngu_TU_NHAN(release_yml):
    """Chạy với ngôn ngữ chọn sẵn thì bỏ lọt đúng ca C44 sinh ra để chặn."""
    kich_ban = _doc(KICH_BAN)
    assert '"--source-lang", "auto"' in kich_ban, (
        "lượt chạy thử không còn dùng 'tự nhận ngôn ngữ' — mất đúng ca cần canh")


def test_lo_chay_that_khong_goi_may_chu_va_khong_ton_vox():
    """Cổng kiểm chạy mỗi lần phát hành: nó mà tiêu tiền thì sẽ bị tắt."""
    kich_ban = _doc(KICH_BAN)
    assert '"TRANSLATE_MODE": "manual"' in kich_ban
    assert '"VOXDUB_API_URL": ""' in kich_ban


@pytest.mark.parametrize("bang_chung", [
    "is not a valid language code",   # bước nghe chết vì ngôn ngữ rỗng
    ".asr_lang",                      # ngôn ngữ nghe được có được ghi lại không
    "transcript from  to",            # khoảng trắng thay cho tên ngôn ngữ
    "READING THE SOURCE",             # luật đọc hiểu nguồn có tới tay người dùng
])
def test_cong_kiem_van_soi_dung_bon_bang_chung_cua_C44(bang_chung):
    assert bang_chung in _doc(KICH_BAN), (
        f"cổng kiểm không còn soi {bang_chung!r} — lỗi C44 tái phát sẽ lọt")


def test_test_yml_chay_that_tren_windows():
    """Windows chứ không phải ubuntu: ba lỗi thật gần đây chỉ lộ ra ở Windows."""
    y = _doc(".github/workflows/test.yml")
    assert "chay-that-windows" in y
    khoi = y[y.find("chay-that-windows"):]
    assert re.search(r"runs-on:\s*windows-latest", khoi)
    assert "kiem_chay_that.py" in khoi


def test_cong_kiem_song_duoc_voi_bang_ma_cu_cua_windows():
    """Tái hiện NGAY TRÊN LINUX lỗi đã làm đỏ lượt CI đầu tiên: đặt
    PYTHONIOENCODING=cp1252 là stdout hành xử y như console Windows chưa
    `chcp 65001`.

    Phải đi vào nhánh in ra **stdout**: Python đặt `errors="backslashreplace"`
    cho stderr nên nhánh báo lỗi KHÔNG BAO GIỜ ném UnicodeEncodeError — bản
    test đầu của tôi kiểm nhầm nhánh đó nên xanh cả khi bản vá bị gỡ (soi ra
    bằng đột biến). `--help` in nguyên phần mô tả tiếng Việt ra stdout, tức
    đúng nhánh chết thật, mà lại chạy tức thì.

    Đây là lớp lỗi #2 của dự án dưới hình dạng khác (D1f: worker in tiếng Việt
    chết vì bảng mã) — mọi worker đã có hai dòng `reconfigure`, riêng bộ canh
    mới thì quên.
    """
    import subprocess
    import sys as _sys

    moi_truong = dict(os.environ, PYTHONIOENCODING="cp1252")
    kq = subprocess.run(
        [_sys.executable, os.path.join(GOC, KICH_BAN), "--help"],
        capture_output=True, text=True, env=moi_truong, timeout=120,
        errors="replace")
    duoi = kq.stdout + kq.stderr
    assert "UnicodeEncodeError" not in duoi, (
        "bộ canh chết vì bảng mã trước cả khi kiểm được gì:\n" + duoi[-500:])
    assert kq.returncode == 0, f"--help phải thoát sạch, nhận {kq.returncode}"


def test_tien_trinh_con_cung_duoc_dat_bang_ma(tmp_path):
    """Tiến trình con ghi nhật ký tiếng Việt và stdout của nó là ỐNG, nên nó
    cũng rơi về bảng mã của máy nếu không được đặt sẵn."""
    kich_ban = _doc(KICH_BAN)
    assert '"PYTHONUTF8": "1"' in kich_ban
    assert '"PYTHONIOENCODING": "utf-8"' in kich_ban
