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
