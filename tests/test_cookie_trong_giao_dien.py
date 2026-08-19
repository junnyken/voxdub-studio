"""V87 — hai ô cookie có trong cấu hình nhưng chưa bao giờ hiện ra giao diện.

`Settings.cookies_from_browser` / `cookies_file` có từ V67, là cách chữa DUY
NHẤT khi TikTok chặn lượt tải ẩn danh (xem V85). Nhưng chúng không nằm trong
`FIELDS`, nên cách sửa duy nhất là mở tệp `.env` — điều không ai bảo người
dùng, và chính tôi cũng đã chỉ nhầm "mở Cài đặt → mục Cookie" khi chỗ đó
không tồn tại.

Bài học: có tuỳ chọn trong `Settings` KHÔNG có nghĩa là người dùng chạm được
vào nó.
"""
from __future__ import annotations

import pytest

from autodub.config import Settings
from autodub_gui.pages import settings_fields as spec


def test_hai_o_cookie_co_mat_trong_giao_dien():
    keys = {f.key for f in spec.FIELDS}
    assert "COOKIES_FROM_BROWSER" in keys
    assert "COOKIES_FILE" in keys


def test_o_cookie_nam_o_the_nguoi_dung_mo_duoc():
    """Ba thẻ Giọng đọc/Phụ đề/Dịch thuật đã tách thành trang riêng nên KHÔNG
    hiện trong Cài đặt — đặt ô mới vào đó là lại vô hình."""
    for f in spec.FIELDS:
        if f.key.startswith("COOKIES"):
            assert f.tab in spec.SETTINGS_TABS, (
                f"{f.key} nằm ở thẻ {f.tab!r} — thẻ này không hiện ra")


def test_lua_chon_trinh_duyet_khop_voi_yt_dlp():
    """Tên trình duyệt phải đúng cái yt-dlp hiểu, không phải tên đẹp."""
    f = next(f for f in spec.FIELDS if f.key == "COOKIES_FROM_BROWSER")
    gia_tri = {v for _nhan, v in f.options}
    assert {"chrome", "edge", "firefox"} <= gia_tri
    assert "" in gia_tri, "phải có lựa chọn Không dùng"


def test_gia_tri_doc_duoc_nguoc_lai_thanh_settings(monkeypatch):
    """Chọn trong giao diện xong phải tới được yt-dlp."""
    monkeypatch.setenv("COOKIES_FROM_BROWSER", "edge")
    assert Settings.load().cookies_from_browser == "edge"


def test_loi_tiktok_chi_dung_duong_di_co_that():
    """Lời khuyên phải trỏ vào chỗ CÓ THẬT — lần trước nó trỏ vào "mục Cookie"
    không tồn tại."""
    from autodub_gui.dub_constants import friendly_error

    _tieu_de, cach_chua = friendly_error(
        "ERROR: [TikTok] 123: Unexpected response from webpage request")
    assert "Nâng cao" in cach_chua
    nhom = {f.group for f in spec.FIELDS if f.key.startswith("COOKIES")}
    assert any(g in cach_chua for g in nhom), (
        f"lời khuyên phải gọi đúng tên nhóm đang có: {nhom}")


@pytest.mark.parametrize("key", ["COOKIES_FROM_BROWSER", "COOKIES_FILE"])
def test_moi_o_deu_co_loi_giai_thich(key):
    f = next(f for f in spec.FIELDS if f.key == key)
    assert len(f.hint) > 30, "ô cấu hình khó hiểu thì phải có lời giải thích"
