""""This video is not available" GIẢ trên YouTube (08/09/2026) — chủ dự án
báo hỏng thật với 2 video Kung Fu Panda CÔNG KHAI, xem được bằng trình
duyệt bình thường. Đo thật bằng yt-dlp thật (không mock) xác nhận: YouTube
mới bắt thêm bước giải mã (n-signature challenge) mà client mặc định ("web")
không xử lý được, và yt-dlp báo lỗi CHUNG với ca video thật sự bị xoá/riêng
tư — "This video is not available", dù video vẫn công khai bình thường.
Ép sang client Android (``extractor_args: {"youtube": {"player_client":
["android"]}}``) tải được đủ, đã xác nhận bằng tải thật cả 2 video.

Bộ test này khoá hành vi DỰ PHÒNG mới trong `downloader._trich_thong_tin`:
gặp đúng câu lỗi đó trên link YouTube thì thử lại bằng client Android trước
khi báo hỏng; mọi ca khác (lỗi khác, không phải YouTube) không bị đụng tới.
"""
from __future__ import annotations

import pytest

from autodub.media import downloader as dl


class _YdlGia:
    """Giả lập yt-dlp: `hong_lan_dau` quyết định lượt gọi ĐẦU có ném lỗi
    không; `chi_android_moi_ok` quyết định lượt dự phòng có ném lỗi không."""

    goi: list[dict] = []

    def __init__(self, opts):
        self._opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=False):
        type(self).goi.append(self._opts)
        la_android = (self._opts.get("extractor_args", {})
                     .get("youtube", {}).get("player_client") == ["android"])
        if la_android:
            if type(self)._chi_android_moi_ok:
                return {"id": "abc", "ext": "mp4", "title": "OK qua Android"}
            raise RuntimeError("ERROR: [youtube] abc: This video is not available")
        if type(self)._hong_lan_dau:
            raise RuntimeError("ERROR: [youtube] abc: This video is not available")
        return {"id": "abc", "ext": "mp4", "title": "OK client mặc định"}


@pytest.fixture(autouse=True)
def _reset():
    _YdlGia.goi = []
    _YdlGia._hong_lan_dau = True
    _YdlGia._chi_android_moi_ok = True
    yield


def test_hong_kieu_not_available_thi_thu_lai_bang_android(monkeypatch):
    monkeypatch.setattr(dl.yt_dlp, "YoutubeDL", _YdlGia)

    info = dl._trich_thong_tin(
        "https://www.youtube.com/watch?v=abc", {"quiet": True})

    assert info["title"] == "OK qua Android"
    assert len(_YdlGia.goi) == 2, "phải thử đúng 2 lượt: mặc định rồi Android"
    assert _YdlGia.goi[1]["extractor_args"]["youtube"]["player_client"] == ["android"]
    assert _YdlGia.goi[1]["quiet"] is True, "lượt dự phòng phải giữ các tham số khác"


def test_ca_hai_lan_deu_hong_thi_bao_loi_GOC(monkeypatch):
    """Lượt dự phòng cũng hỏng — video thật sự có vấn đề. Báo lỗi của lượt
    ĐẦU (client mặc định), không phải lỗi của lượt dự phòng — đúng bản chất
    thật của link."""
    _YdlGia._chi_android_moi_ok = False
    monkeypatch.setattr(dl.yt_dlp, "YoutubeDL", _YdlGia)

    with pytest.raises(RuntimeError, match="not available"):
        dl._trich_thong_tin("https://www.youtube.com/watch?v=abc", {})
    assert len(_YdlGia.goi) == 2, "vẫn phải thử đủ cả hai lượt trước khi báo hỏng"


def test_loi_khac_khong_phai_not_available_thi_khong_thu_lai(monkeypatch):
    class _YdlLoiKhac:
        def __init__(self, opts):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def extract_info(self, url, download=False):
            raise RuntimeError("HTTP Error 404: Not Found")

    monkeypatch.setattr(dl.yt_dlp, "YoutubeDL", _YdlLoiKhac)

    with pytest.raises(RuntimeError, match="404"):
        dl._trich_thong_tin("https://www.youtube.com/watch?v=abc", {})


def test_khong_phai_youtube_thi_khong_thu_lai_du_cung_cau_loi(monkeypatch):
    """Câu lỗi 'not available' ở nền tảng khác có thể có nghĩa khác hẳn —
    dự phòng Android chỉ có nghĩa cho YouTube."""
    class _YdlTiktok:
        goi = 0
        def __init__(self, opts):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def extract_info(self, url, download=False):
            type(self).goi += 1
            raise RuntimeError("This video is not available")

    monkeypatch.setattr(dl.yt_dlp, "YoutubeDL", _YdlTiktok)

    with pytest.raises(RuntimeError, match="not available"):
        dl._trich_thong_tin("https://www.tiktok.com/@x/video/123", {})
    assert _YdlTiktok.goi == 1, "không phải YouTube thì không thử lại thêm lượt nào"


def test_thanh_cong_ngay_lan_dau_thi_khong_dung_toi_du_phong(monkeypatch):
    _YdlGia._hong_lan_dau = False
    monkeypatch.setattr(dl.yt_dlp, "YoutubeDL", _YdlGia)

    info = dl._trich_thong_tin("https://youtu.be/abc", {})

    assert info["title"] == "OK client mặc định"
    assert len(_YdlGia.goi) == 1, "thành công ngay thì không được gọi thêm"


def test_download_one_tu_dong_qua_duoc_bang_du_phong(monkeypatch, tmp_path):
    """Kiểm tra tới tận `download_one()` (đường Chép lời/Tải xuống thật
    dùng) — không chỉ hàm nội bộ."""
    monkeypatch.setattr(dl.yt_dlp, "YoutubeDL", _YdlGia)

    def gia_resolve(info, output_dir):
        return str(tmp_path / "abc.mp4")

    monkeypatch.setattr(dl, "_resolve_filepath", gia_resolve)

    ket_qua = dl.download_one("https://www.youtube.com/watch?v=abc", str(tmp_path))

    assert ket_qua["title"] == "OK qua Android"
    assert len(_YdlGia.goi) == 2
