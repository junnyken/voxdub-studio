"""V73 — một liên kết = một video, và lý do hỏng phải nói ra được.

Lỗi thật, người dùng báo trên bản v3.4.0 (2026-08-18): dán
``watch?v=x1F3EdwrYw4&list=RDMMx1F3EdwrYw4&start_radio=1`` — liên kết mà
YouTube tự sinh khi sao chép lúc đang nghe một Mix — vào trang Chép lời thì
nhận đúng một dòng ``[1/1] HỎNG: <liên kết>``, không lý do.

Hai khiếm khuyết chồng lên nhau, test này khoá cả hai:

1. Thiếu ``noplaylist`` nên yt-dlp coi đó là DANH SÁCH PHÁT. Kiểm chứng bằng
   yt-dlp thật lúc sửa: liên kết trên trả về playlist ``RDMMx1F3EdwrYw4``
   («My Mix») với **194 mục**; thêm ``noplaylist`` thì trả về đúng video
   ``x1F3EdwrYw4``. Tải cả 194 video xong vẫn hỏng, vì ``_resolve_filepath``
   đi tìm một file duy nhất theo id của playlist.
2. Liên kết danh sách phát THUẦN (``playlist?list=…``) thì ``noplaylist``
   không cứu được — phải chặn thẳng bằng lời người đọc hiểu.
"""
from __future__ import annotations

import pytest

from autodub.media import downloader as dl


# -- 1. watch?v=…&list=… → chỉ tải video đang mở -------------------------------

def test_build_ydl_opts_chi_lay_mot_video():
    assert dl.build_ydl_opts("/ra").get("noplaylist") is True


def test_download_video_cung_chi_lay_mot_video(tmp_path, monkeypatch):
    """`download_video` dựng options riêng — sửa một chỗ mà quên chỗ kia là
    lỗi quay lại ở luồng Tạo dự án trong khi Chép lời đã lành."""
    ghi = {}

    class _Ydl:
        def __init__(self, opts): ghi["opts"] = opts
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, url, download=True):
            duong = tmp_path / "abc.mp4"
            duong.write_bytes(b"x")
            return {"id": "abc", "ext": "mp4", "title": "T",
                    "requested_downloads": [{"filepath": str(duong)}]}

    monkeypatch.setattr(dl.yt_dlp, "YoutubeDL", _Ydl)
    dl.download_video("https://www.youtube.com/watch?v=abc&list=RDMMabc",
                      str(tmp_path))
    assert ghi["opts"].get("noplaylist") is True


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=x1F3EdwrYw4&list=RDMMx1F3EdwrYw4&start_radio=1",
    "https://www.youtube.com/watch?v=abc123",
    "https://youtu.be/abc123",
    "https://www.facebook.com/share/r/1EUSdYJeXN/",
    "https://www.tiktok.com/@ai/video/123",
])
def test_lien_ket_co_video_cu_the_van_di_qua(url):
    """Có ``v=`` là có video để `noplaylist` cắt về — không được chặn nhầm.
    Chặn nhầm ở đây làm chết đúng cái liên kết người dùng đang muốn dùng."""
    dl.ensure_single_video_url(url)


# -- 2. playlist?list=… → chặn, kèm lời người đọc hiểu -------------------------

@pytest.mark.parametrize("url", [
    "https://www.youtube.com/playlist?list=PLabc",
    "https://youtube.com/playlist?list=RDMMx1F3EdwrYw4",
])
def test_lien_ket_danh_sach_phat_thuan_bi_chan(url):
    with pytest.raises(dl.PlaylistUrlError) as e:
        dl.ensure_single_video_url(url)
    loi = str(e.value)
    # Chặn thôi chưa đủ: phải nói người dùng làm gì tiếp theo. Đây là chỗ
    # người dùng đọc, không phải chỗ lập trình viên đọc.
    assert "DANH SÁCH PHÁT" in loi
    assert "watch?v=" in loi


def test_chan_TRUOC_khi_tai(tmp_path, monkeypatch):
    """Phải chặn trước khi yt-dlp chạy — chặn sau là bắt người dùng chờ hết
    cả trăm video rồi mới báo lỗi."""
    def _no(*a, **k):
        raise AssertionError("không được gọi yt-dlp cho liên kết danh sách phát")

    monkeypatch.setattr(dl.yt_dlp, "YoutubeDL", _no)
    with pytest.raises(dl.PlaylistUrlError):
        dl.download_one("https://www.youtube.com/playlist?list=PLabc", str(tmp_path))
    with pytest.raises(dl.PlaylistUrlError):
        dl.download_video("https://www.youtube.com/playlist?list=PLabc", str(tmp_path))
