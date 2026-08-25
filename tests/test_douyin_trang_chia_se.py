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


# -- Cookie của người dùng là đường CUỐI CÙNG (mini-spec C33) ---------------
#
# Đo thật 25/8: Douyin đã đóng mọi cửa ẩn danh — trang chia sẻ không còn địa
# chỉ video, API `iteminfo` trả 0 byte, API `aweme/detail` trả 403 "blocked",
# yt-dlp bản mới nhất đòi cookie, và trang chia sẻ đẩy khách sang video gợi ý
# (`abParams.reflow_to_featured_app = 1`).
#
# Trước đây Douyin bị định tuyến TRÁNH yt-dlp, nên ô cookie trong Cài đặt
# không có tác dụng gì với Douyin — đúng thứ yt-dlp đang đòi thì lại không
# bao giờ tới tay nó.

def test_duong_trinh_duyet_hong_thi_THU_TIEP_bang_cookie():
    from tests.doc_ma import cac_luot_goi

    from autodub.media.downloader import download_video

    goi = cac_luot_goi(download_video)
    assert "download_douyin" in goi
    assert "cookie_opts_from" in goi, \
        "hỏng đường trình duyệt là bỏ cuộc, không thử cookie"


def test_CHUA_cau_hinh_cookie_thi_nem_lai_loi_goc():
    """Không có cookie thì thử tiếp cũng vô ích — đừng nuốt lỗi rồi báo một
    thông báo khác gây rối."""
    import ast
    import io as _io

    nguon = _io.open("autodub/media/downloader.py", encoding="utf-8").read()
    i = nguon.index("if not cookie_opts_from(settings):")
    assert "raise" in nguon[i:i + 120]


def test_thanh_cong_thi_KHONG_thu_them_duong_nao():
    """`else` của `try` chỉ chạy khi không có lỗi — tải xong là trả về ngay.

    Hỏi CÂY CÚ PHÁP thay vì cắt một cửa sổ ký tự quanh lời gọi: khối chú
    thích ở giữa dài hơn cửa sổ nên phép cắt trượt, test đỏ oan. Đây là kiểu
    lỗi đã mắc nhiều lần trong đợt này.
    """
    import ast

    from tests.doc_ma import cay_ham

    from autodub.media.downloader import download_video

    for node in ast.walk(cay_ham(download_video)):
        if not isinstance(node, ast.Try):
            continue
        goi = [n for n in ast.walk(node.body[0] if node.body else node)
               if isinstance(n, ast.Call)]
        if not any(getattr(g.func, "id", "") == "download_douyin" for g in goi):
            continue
        assert node.orelse, "không có nhánh `else` — thành công vẫn chạy tiếp"
        assert any(isinstance(n, ast.Return) for n in ast.walk(node.orelse[-1])
                   ) or any(isinstance(n, ast.Return) for n in node.orelse), \
            "nhánh `else` không trả về ngay"
        return
    raise AssertionError("không thấy khối try quanh download_douyin")


def test_loi_dua_nham_video_co_loi_soan_san():
    from autodub_gui.dub_constants import friendly_error

    soan = friendly_error(
        "Tải video thất bại: Douyin trả về một video KHÁC "
        "(xin 7665732287728983464, nhận 7665940121195121966)")
    assert soan is not None
    tieu_de, cach_chua = soan
    assert "nhầm video" in tieu_de
    # Phải nói CẢ HAI đường: cookie, và đường luôn chạy được.
    assert "Tải video khó" in cach_chua
    assert "Tải tệp lên" in cach_chua
