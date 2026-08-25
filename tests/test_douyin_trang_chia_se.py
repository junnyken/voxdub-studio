"""C32 — Douyin trả về một video KHÁC.

Người dùng dán liên kết chia sẻ, app báo:
`Douyin redirected to a different video (requested 7644780389491375333, got
766594012119512196…)`.

Nguyên nhân: app giải liên kết ra SỐ VIDEO rồi **vứt bỏ địa chỉ đã giải**, sau
đó tự dựng lại một địa chỉ trần. Chuỗi chuyển hướng thật là

    v.douyin.com/XXX
      → iesdouyin.com/share/video/<id>/?…share_sign…      ← trang chia sẻ
      → www.douyin.com/video/<id>?previous_page=…          ← trang desktop

Chặng giữa mang chữ ký chia sẻ. Chặng cuối là trang desktop, mà trang đó **tự
phát video gợi ý** — đúng cái bẫy ghi ngay ở đầu `douyin.py`.
"""
from __future__ import annotations

import pytest

from autodub.media import douyin


class _Resp:
    def __init__(self, url, history_urls):
        self.url = url
        self.history = [type("H", (), {"headers": {"Location": u}})()
                        for u in history_urls]

    def close(self):
        pass


CHUOI = [
    "https://www.iesdouyin.com/share/video/7644780389491375333/"
    "?region=VN&share_sign=8NtfsrdBBOHwk&ts=1787628367",
    "https://www.douyin.com/video/7644780389491375333?previous_page=web_code_link",
]


@pytest.fixture()
def gia_lap_chuyen_huong(monkeypatch):
    monkeypatch.setattr(douyin.requests, "get",
                        lambda *a, **k: _Resp(CHUOI[-1], CHUOI))


def test_chon_TRANG_CHIA_SE_khong_chon_trang_desktop(gia_lap_chuyen_huong):
    """Trang desktop tự phát video gợi ý — mở nó là bắt nhầm video khác."""
    vid, url = douyin.resolve_share_url("https://v.douyin.com/NSY5rdSAVGs/")
    assert vid == "7644780389491375333"
    assert "iesdouyin.com/share/video" in url
    assert "www.douyin.com/video" not in url


def test_giu_lai_CHU_KY_chia_se(gia_lap_chuyen_huong):
    """Thiếu chữ ký thì Douyin coi như một lượt truy cập lạ."""
    _vid, url = douyin.resolve_share_url("https://v.douyin.com/NSY5rdSAVGs/")
    assert "share_sign=" in url


def test_khong_co_trang_chia_se_thi_dung_lai_dia_chi_tran(monkeypatch):
    """Chuỗi chuyển hướng lạ thì vẫn phải trả về thứ dùng được."""
    chi_desktop = ["https://www.douyin.com/video/7644780389491375333"]
    monkeypatch.setattr(douyin.requests, "get",
                        lambda *a, **k: _Resp(chi_desktop[0], chi_desktop))
    vid, url = douyin.resolve_share_url("https://v.douyin.com/abc/")
    assert vid == "7644780389491375333"
    assert url == "https://www.iesdouyin.com/share/video/7644780389491375333/"


def test_dia_chi_da_co_san_so_video_thi_khong_goi_mang(monkeypatch):
    monkeypatch.setattr(douyin.requests, "get",
                        lambda *a, **k: pytest.fail("gọi mạng khi không cần"))
    vid, url = douyin.resolve_share_url(
        "https://www.iesdouyin.com/share/video/7644780389491375333/?share_sign=x")
    assert vid == "7644780389491375333"
    assert "share_sign=x" in url, "đừng vứt tham số của địa chỉ người dùng đưa"


def test_khong_giai_duoc_thi_tra_None_khong_no(monkeypatch):
    def _no(*a, **k):
        raise douyin.requests.RequestException("mất mạng")

    monkeypatch.setattr(douyin.requests, "get", _no)
    vid, url = douyin.resolve_share_url("https://v.douyin.com/abc/")
    assert vid is None and url == "https://v.douyin.com/abc/"


def test_duong_trinh_duyet_DUNG_dia_chi_da_giai():
    """Dựng lại địa chỉ trần là vứt bỏ chữ ký — đúng lỗi đang sửa."""
    import inspect

    than = inspect.getsource(douyin._download_via_playwright)
    assert "share_url or f\"https://www.iesdouyin.com" in than, \
        "không nhận địa chỉ đã giải, vẫn tự dựng địa chỉ trần"


def test_download_douyin_TRUYEN_dia_chi_da_giai_xuong():
    from tests.doc_ma import cac_luot_goi

    goi = cac_luot_goi(douyin.download_douyin)
    assert "resolve_share_url" in goi, "vẫn dùng bản cũ vứt mất địa chỉ"


def test_van_GIU_chot_chan_video_lech():
    """Chốt này đúng và phải giữ: tải nhầm video rồi lồng tiếng lên nó thì
    người dùng chỉ phát hiện sau khi đã trả tiền."""
    import inspect

    than = inspect.getsource(douyin._download_via_playwright)
    assert 'info["video_id"] != video_id' in than


def test_thong_bao_lech_video_noi_VIEC_LAM_DUOC():
    import inspect

    than = inspect.getsource(douyin._download_via_playwright)
    assert "Tải tệp lên" in than, \
        "báo lỗi mà không nói cách đi tiếp thì người dùng bế tắc"
