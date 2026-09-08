"""Tính năng "Tải MP3 riêng" (08/09/2026) — trang Tải xuống trước đây chỉ
tải được video (mp4). Thêm lựa chọn "Chỉ âm thanh (MP3)": dùng
`FFmpegExtractAudio` của yt-dlp, tái dùng nguyên `_resolve_filepath()` đã có
sẵn (tìm theo TIỀN TỐ tên tệp, không theo đuôi mở rộng — đo thật bằng yt-dlp
thật: sau khi chuyển mp3, `info["ext"]` ở tầng trên vẫn báo "mp4"/"none" tuỳ
phiên bản, nhưng file thật trên đĩa đã là .mp3 — `_resolve_filepath` vẫn tìm
đúng nhờ quét tiền tố, không cần sửa gì thêm).
"""
from __future__ import annotations

import pytest

from autodub.media import downloader as dl


# --------------------------------------------------------------------- #
# build_ydl_opts — thuần, không cần mạng.

def test_dinh_dang_video_mac_dinh_khong_doi_so_voi_truoc():
    opts = dl.build_ydl_opts("/ra")
    assert opts["format"] == "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    assert opts["merge_output_format"] == "mp4"
    assert "postprocessors" not in opts
    assert opts["noplaylist"] is True


def test_dinh_dang_mp3_audio_dung_bestaudio_va_postprocessor():
    opts = dl.build_ydl_opts("/ra", dinh_dang="mp3_audio")
    assert opts["format"] == "bestaudio/best"
    assert "merge_output_format" not in opts, (
        "merge_output_format chỉ có nghĩa khi ghép video+audio, để lại đây "
        "không sai nhưng thừa — dấu hiệu code chưa tách nhánh đúng")
    pp = opts["postprocessors"]
    assert len(pp) == 1
    assert pp[0]["key"] == "FFmpegExtractAudio"
    assert pp[0]["preferredcodec"] == "mp3"


def test_mp3_audio_van_giu_noplaylist_va_cookie():
    """Đổi định dạng không được đụng tới các chốt an toàn khác đã có."""
    opts = dl.build_ydl_opts("/ra", "chrome", None, dinh_dang="mp3_audio")
    assert opts["noplaylist"] is True
    assert opts["cookiesfrombrowser"] == ("chrome",)


# --------------------------------------------------------------------- #
# download_one — mock yt-dlp thật (đúng khuôn test_cookie_settings.py).

def test_download_one_truyen_dinh_dang_xuong_build_ydl_opts(tmp_path, monkeypatch):
    ghi_nhan = {}

    def gia_lap_build(output_dir, cookies_from_browser=None,
                      cookies_file=None, dinh_dang="video"):
        ghi_nhan["dinh_dang"] = dinh_dang
        return {}

    monkeypatch.setattr(dl, "build_ydl_opts", gia_lap_build)

    class _YDL:
        def __init__(self, *a, **k): ...
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, url, download=True):
            duong = tmp_path / "Youtube_x.mp3"
            duong.write_bytes(b"x")
            return {"id": "x", "ext": "mp4", "title": "", "uploader": "",
                    "duration": 1, "extractor_key": "Youtube",
                    "requested_downloads": [{}]}  # không có "filepath" —
            # đúng hành vi thật đo được của yt-dlp sau FFmpegExtractAudio.

    monkeypatch.setattr(dl.yt_dlp, "YoutubeDL", _YDL)
    ket_qua = dl.download_one("https://www.youtube.com/watch?v=x", str(tmp_path),
                              dinh_dang="mp3_audio")

    assert ghi_nhan["dinh_dang"] == "mp3_audio"
    # `requested_downloads` không có "filepath" (đúng hành vi thật) — phải
    # rơi về nhánh quét tiền tố của `_resolve_filepath`, tìm đúng .mp3 dù
    # `info["ext"]` (tầng trên) vẫn ghi "mp4".
    assert ket_qua["filepath"] == str(tmp_path / "Youtube_x.mp3")


def test_douyin_bo_qua_mp3_audio_nhung_noi_ra_ly_do(tmp_path, monkeypatch, caplog):
    """Douyin dùng bộ tải riêng, chỉ trả video — chọn MP3 mà bị bỏ qua âm
    thầm là đúng lớp lỗi #6 (FEATURES.md §6): phải LOG RA, không im lặng."""
    import logging

    def gia_lap_douyin(url, output_dir):
        duong = tmp_path / "douyin.mp4"
        duong.write_bytes(b"x")
        return {"filepath": str(duong), "title": "t"}

    monkeypatch.setattr("autodub.media.douyin.download_douyin", gia_lap_douyin)
    monkeypatch.setattr("autodub.media.douyin.is_douyin_url", lambda u: True)

    with caplog.at_level(logging.WARNING):
        ket_qua = dl.download_one("https://v.douyin.com/abc", str(tmp_path),
                                  dinh_dang="mp3_audio")

    assert ket_qua["filepath"].endswith(".mp4")
    assert any("Douyin" in r.message and "MP3" in r.message
              for r in caplog.records)
