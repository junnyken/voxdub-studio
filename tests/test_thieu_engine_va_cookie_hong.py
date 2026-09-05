"""C61 — hai lỗi người dùng báo 05-09, cùng một bản chất: máy nói không rõ.

**Lỗi 1 — dịch phụ đề rời, chọn "Máy này (offline)":** trên máy chưa chạy bộ
cài, `Popen` ném `FileNotFoundError` (không có python của `.venv-mt`), lỗi đó
rơi thẳng ra giao diện thành *"Dừng lại vì một lỗi ngoài dự tính"*. Người dùng
không có cách nào đoán ra việc cần làm là chạy một bộ cài. Cùng lớp lỗi với C56
ở bộ quét chữ.

**Lỗi 2 — chép lời từ liên kết TikTok:** `ERROR: Could not copy Chrome cookie
database`. Chrome đang mở nên giữ khoá tệp cookie. Cái đáng nói: phần lớn liên
kết KHÔNG cần cookie, mà cả lượt chép lời vẫn chết vì một bước người dùng không
hề yêu cầu.
"""
from __future__ import annotations

import pytest

from autodub.media.downloader import loi_do_cookie_trinh_duyet
from autodub.text.translate_local import ChuaCaiDichNgoaiTuyen, run_local_worker


# ------------------------------------ 1. chưa cài thì nói là chưa cài ---

class _CaiDatGia:
    def __init__(self, python_path: str):
        self._python = python_path

    def translate_local_venv_python_path(self) -> str:
        return self._python

    def translate_local_model_dir_path(self) -> str:
        return "/khong/quan/trong"

    def translate_local_configured(self) -> bool:
        return False


def test_chua_cai_dich_ngoai_tuyen_thi_noi_ro_viec_can_lam():
    """Lời báo phải nói ĐƯỢC VIỆC: tên bộ cài, và đường thay thế ngay lúc này."""
    with pytest.raises(ChuaCaiDichNgoaiTuyen) as e:
        run_local_worker([(1, "你好")], "zho_Hans", "vie_Latn",
                         _CaiDatGia("/khong/co/that/python"))
    loi = str(e.value)
    assert "Cai dat dich ngoai tuyen" in loi, "không chỉ ra bộ cài nào phải chạy"
    assert "Máy chủ VoxDub" in loi, "không nói đường thay thế để dịch ngay"


def test_loi_chua_cai_van_la_LocalTranslateError():
    """Nơi gọi cũ bắt `LocalTranslateError` — thêm lớp con không được làm gãy
    đường xử lý lỗi đã có."""
    from autodub.text.translate_local import LocalTranslateError

    assert issubclass(ChuaCaiDichNgoaiTuyen, LocalTranslateError)


def test_da_cai_thi_KHONG_bi_chan_nham(tmp_path):
    """Bộ chặn hay chặn nhầm còn tệ hơn không có (V90). Có python thật thì phải
    đi tiếp — hỏng ở bước sau là chuyện của bước sau."""
    import sys

    with pytest.raises(Exception) as e:      # noqa: PT011 — chỉ cần KHÔNG phải ca "chưa cài"
        run_local_worker([(1, "你好")], "zho_Hans", "vie_Latn",
                         _CaiDatGia(sys.executable))
    assert not isinstance(e.value, ChuaCaiDichNgoaiTuyen), (
        "python có thật mà vẫn bị báo 'chưa cài'")


# ------------------------------------- 2. cookie hỏng ≠ video có khoá ---

def test_nhan_ra_loi_khong_doc_duoc_kho_cookie():
    """Đúng câu yt-dlp in ra trong ảnh chụp màn hình của chủ dự án."""
    assert loi_do_cookie_trinh_duyet(
        "ERROR: Could not copy Chrome cookie database. See "
        "https://github.com/yt-dlp/yt-dlp/issues/7271 for more info")
    assert loi_do_cookie_trinh_duyet("Permission denied while opening cookies")


def test_KHONG_nhan_nham_video_that_su_doi_dang_nhap():
    """"Fresh cookies are needed" là chuyện KHÁC: video thật sự đòi cookie. Bỏ
    cookie đi rồi thử lại thì càng chắc chắn hỏng, mà lại giấu mất nguyên nhân
    thật khỏi người dùng."""
    assert not loi_do_cookie_trinh_duyet(
        "ERROR: fresh cookies are needed to sign in")
    assert not loi_do_cookie_trinh_duyet("HTTP Error 404: Not Found")
    assert not loi_do_cookie_trinh_duyet("")


def test_cookie_hong_thi_thu_lai_KHONG_cookie(monkeypatch):
    """Đường lùi rẻ và hầu như luôn đúng — phần lớn liên kết công khai không
    cần cookie."""
    from autodub.media import downloader

    lan: list[dict] = []

    class _YdlGia:
        def __init__(self, opts):
            self._opts = opts
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def extract_info(self, url, download=False):
            lan.append(self._opts)
            if "cookiesfrombrowser" in self._opts:
                raise RuntimeError("ERROR: Could not copy Chrome cookie database")
            return {"id": "abc", "ext": "mp4"}

    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", _YdlGia)
    info = downloader._tai_bang_ydl(
        "https://tiktok.com/x", {"cookiesfrombrowser": ("chrome",), "quiet": True})

    assert info["id"] == "abc"
    assert len(lan) == 2, "phải thử lại đúng một lần"
    assert "cookiesfrombrowser" not in lan[1], "lượt thử lại vẫn kèm cookie"
    assert lan[1]["quiet"] is True, "lượt thử lại làm mất các tham số khác"


def test_thu_lai_van_hong_thi_noi_ca_hai_nguyen_nhan(monkeypatch):
    """Người dùng cần biết CẢ hai: cookie không đọc được, và video vẫn không
    tải được — kèm hai cách xử lý."""
    from autodub.media import downloader

    class _YdlLuonHong:
        def __init__(self, opts):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def extract_info(self, url, download=False):
            raise RuntimeError("Could not copy Chrome cookie database")

    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", _YdlLuonHong)
    with pytest.raises(RuntimeError) as e:
        downloader._tai_bang_ydl("https://tiktok.com/x",
                                 {"cookiesfrombrowser": ("chrome",)})
    loi = str(e.value)
    assert "đóng hẳn trình duyệt" in loi
    assert "cookies.txt" in loi


def test_khong_dung_cookie_thi_loi_giu_nguyen(monkeypatch):
    """Không cấu hình cookie mà hỏng thì đừng bịa thêm chuyện cookie vào."""
    from autodub.media import downloader

    class _YdlHong:
        def __init__(self, opts):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def extract_info(self, url, download=False):
            raise RuntimeError("HTTP Error 404: Not Found")

    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", _YdlHong)
    with pytest.raises(RuntimeError, match="404"):
        downloader._tai_bang_ydl("https://x/y", {"quiet": True})


# ------------------------- 3. lời khuyên tới được người dùng, không bị che ---

def test_hop_thoai_giu_nguyen_loi_khuyen_da_noi_duoc_viec():
    """Trang Dịch phụ đề rời trước đây LUÔN hiện một câu chung chung ("kiểm tra
    lại file/ngôn ngữ/mạng"), kể cả khi lỗi đã nói rõ việc cần làm — lấy đi
    đúng thứ người dùng cần."""
    pytest.importorskip("PySide6")
    from autodub_gui.log_text import error_line

    loi = ("Chưa cài bộ dịch ngoại tuyến trên máy này. Chạy "
           "«Cai dat dich ngoai tuyen.bat» rồi dịch lại — bộ này nặng ~600 MB.")
    text, _ = error_line(loi)
    assert text.startswith("Dừng lại: "), (
        "lời báo đã soạn tử tế mà vẫn rơi về 'lỗi ngoài dự tính'")
    assert "Cai dat dich ngoai tuyen" in text


def test_loi_that_su_kho_hieu_thi_van_co_cau_khuyen_chung():
    """Không đoán được nguyên nhân thì phải có gì đó để người dùng thử — im
    lặng hoặc ném mã lỗi ra là bỏ rơi họ."""
    pytest.importorskip("PySide6")
    from autodub_gui.pages.subtitle_translate_page import SubtitleTranslatePage

    assert "Kiểm tra lại" in SubtitleTranslatePage._KHUYEN_CHUNG
