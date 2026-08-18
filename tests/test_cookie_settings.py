"""V67 — cookie cho yt-dlp, đường lui khi video đòi đăng nhập.

Đo ngày 18-08: reel Facebook CÔNG KHAI tải được mà KHÔNG cần cookie
(https://www.facebook.com/share/r/1EUSdYJeXN/ → 6.2 MB, 20.166 giây). Nên
cookie là đường lui cho video giới hạn, không phải thứ bắt buộc cấu hình.
"""
from __future__ import annotations

from autodub.config import Settings
from autodub.media.downloader import cookie_opts_from


def test_khong_cau_hinh_gi_thi_khong_them_tham_so():
    """Mặc định phải sạch — link công khai không cần cookie."""
    assert cookie_opts_from(Settings()) == {}


def test_settings_None_khong_no():
    assert cookie_opts_from(None) == {}


def test_file_cookie_duoc_dung():
    s = Settings()
    s.cookies_file = "/duong/dan/cookies.txt"
    assert cookie_opts_from(s) == {"cookies_file": "/duong/dan/cookies.txt"}


def test_trinh_duyet_duoc_dung_khi_khong_co_file():
    s = Settings()
    s.cookies_from_browser = "chrome"
    assert cookie_opts_from(s) == {"cookies_from_browser": "chrome"}


def test_co_ca_hai_thi_FILE_thang():
    """Người vừa xuất cookies.txt là người đang cố sửa một lỗi cụ thể.

    "Đọc từ Chrome" là đường tự đoán và hỏng lặng lẽ (sai profile, hồ sơ đang
    khoá), nên không được phép đè lên lựa chọn tường minh.
    """
    s = Settings()
    s.cookies_file = "/duong/dan/cookies.txt"
    s.cookies_from_browser = "chrome"
    assert cookie_opts_from(s) == {"cookies_file": "/duong/dan/cookies.txt"}


def test_khoang_trang_coi_nhu_khong_dat():
    s = Settings()
    s.cookies_file = "   "
    s.cookies_from_browser = "  "
    assert cookie_opts_from(s) == {}, "gõ nhầm dấu cách không được thành cấu hình"


def test_doc_duoc_tu_bien_moi_truong(monkeypatch):
    monkeypatch.setenv("COOKIES_FILE", "/tmp/ck.txt")
    monkeypatch.setenv("COOKIES_FROM_BROWSER", "edge")
    s = Settings.load()
    assert s.cookies_file == "/tmp/ck.txt"
    assert s.cookies_from_browser == "edge"


def test_download_one_uu_tien_tham_so_truyen_tay(monkeypatch, tmp_path):
    """Chỗ gọi truyền tay thì thắng cấu hình chung — nó biết rõ hơn."""
    from autodub.media import downloader
    ghi_nhan = {}

    def gia_lap(output_dir, cookies_from_browser=None, cookies_file=None):
        ghi_nhan["browser"] = cookies_from_browser
        ghi_nhan["file"] = cookies_file
        return {}

    monkeypatch.setattr(downloader, "build_ydl_opts", gia_lap)

    class _YDL:
        def __init__(self, *a, **k): ...
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, url, download=True):
            return {"id": "x", "ext": "mp4", "title": "", "uploader": "",
                    "duration": 1, "extractor_key": "Test",
                    "requested_downloads": [{"filepath": str(tmp_path / "x.mp4")}]}

    (tmp_path / "x.mp4").write_bytes(b"\0")
    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", _YDL)

    s = Settings()
    s.cookies_file = "/tu-settings.txt"
    downloader.download_one("https://example.com/v.mp4", str(tmp_path),
                            cookies_file="/truyen-tay.txt", settings=s)

    assert ghi_nhan["file"] == "/truyen-tay.txt"
