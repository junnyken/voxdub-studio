"""V73 — dọn file tạm, và nhận liên kết thiếu `https://`.

Hai việc còn tồn sau đợt sửa V73 đầu, tìm ra khi soát lại chứ không phải do
người dùng báo.
"""
from __future__ import annotations

import os
import subprocess

import pytest

from autodub.config import Settings
from autodub.media import downloader as dl
from autodub.utils import looks_like_bare_url


def _wav(path: str, giay: int = 1) -> str:
    subprocess.run(["ffmpeg", "-v", "quiet", "-f", "lavfi",
                    "-i", f"sine=f=440:d={giay}", "-ar", "44100", path], check=True)
    return path


@pytest.fixture()
def asr_gia(monkeypatch):
    """ASR thật mất vài chục giây và cần model — thay bằng kết quả cố định.
    Phần đang kiểm là dọn file, không phải chất lượng nhận dạng."""
    import autodub.speech.transcriber as tr
    monkeypatch.setattr(tr, "transcribe",
                        lambda *a, **k: [{"start": 0.0, "end": 1.0, "text": "xin chao"}])


# -- 1. Dọn file tạm ----------------------------------------------------------

def test_file_cua_nguoi_dung_KHONG_BAO_GIO_bi_xoa(tmp_path, asr_gia):
    """Ràng buộc quan trọng nhất của `_don_tam`.

    Với file trên máy, `prepare_audio` trả về chính đường dẫn CỦA NGƯỜI DÙNG
    làm `media_path`. Dọn mà không kiểm thư mục là xoá thẳng dữ liệu gốc của
    họ — hỏng nặng hơn mọi thứ việc dọn dẹp định sửa."""
    import autodub.transcribe_tool as tt

    goc = _wav(str(tmp_path / "phim_goc.wav"))
    ra = str(tmp_path / "kq")
    kq = tt.transcribe_media(goc, ra, Settings(), formats=("txt",))

    assert os.path.isfile(goc), "ĐÃ XOÁ FILE GỐC CỦA NGƯỜI DÙNG"
    assert os.path.isfile(kq.outputs["txt"]), "kết quả phải còn"


def test_video_tai_ve_bi_don_sau_khi_xong(tmp_path, asr_gia, monkeypatch):
    """Chép lời từ liên kết tải nguyên video về nhưng chỉ dùng phần tiếng.
    Tên đặt theo `<extractor>_<id>` nên mỗi video là một file mới — không dọn
    thì 20 video YouTube là 20 file đầy đủ nằm lại, hàng GB người dùng không
    hề xin."""
    import autodub.transcribe_tool as tt

    ra = str(tmp_path / "kq")
    tam = os.path.join(ra, "_tam")
    os.makedirs(tam, exist_ok=True)
    video = _wav(os.path.join(tam, "Youtube_abc123.wav"))

    monkeypatch.setattr(tt, "is_url", lambda s: s.startswith("https://"))
    monkeypatch.setattr(dl, "download_one",
                        lambda url, wd, **k: {"filepath": video, "title": "Bai hat"})

    kq = tt.transcribe_media("https://youtu.be/abc123", ra, Settings(),
                             formats=("txt",))
    assert not os.path.exists(video), "video tải về phải được dọn"
    assert os.listdir(tam) == [], "_tam phải sạch"
    assert os.path.isfile(kq.outputs["txt"])
    assert os.path.basename(kq.outputs["txt"]) == "Bai hat.txt"


def test_muc_hong_thi_GIU_lai_file_de_con_do(tmp_path, monkeypatch):
    """Dọn chỉ chạy khi đã xuất xong. Hỏng mà cũng xoá sạch thì mất luôn
    manh mối để tìm nguyên nhân."""
    import autodub.transcribe_tool as tt
    import autodub.speech.transcriber as tr

    goc = _wav(str(tmp_path / "a.wav"))
    ra = str(tmp_path / "kq")
    monkeypatch.setattr(tr, "transcribe", lambda *a, **k: [])   # ASR ra rỗng

    with pytest.raises(tt.TranscribeError):
        tt.transcribe_media(goc, ra, Settings(), formats=("txt",))
    assert os.listdir(os.path.join(ra, "_tam")), "hỏng thì phải giữ file tạm"


# -- 2. Liên kết thiếu `https://` ---------------------------------------------

@pytest.mark.parametrize("text", [
    "www.youtube.com/watch?v=abc",
    "youtube.com/watch?v=abc",
    "youtu.be/abc123",
    "vm.tiktok.com/ZSabc/",
])
def test_nhan_ra_dia_chi_thieu_scheme(text):
    assert looks_like_bare_url(text) is True


@pytest.mark.parametrize("text", [
    "phim.mp4",              # `mp4` trông y hệt một tên miền nếu chỉ soi đuôi
    "thu_muc/phim.mp4",
    "/home/coder/a.mp3",
    "D:/video/phim.mp4",
    "C:\\video\\a.mp4",
    "./a.mp4",
    "../x/y.mp4",
    "https://youtu.be/x",    # đã có lược đồ, không phải việc của hàm này
    "",
])
def test_khong_nham_duong_dan_file_thanh_dia_chi(text):
    """Đoán sai theo hướng này tai hại hơn: thông báo "không tìm thấy file"
    rõ ràng sẽ biến thành một lỗi tải khó hiểu."""
    assert looks_like_bare_url(text) is False


def test_file_co_that_tren_dia_luon_thang(tmp_path):
    """Tên file trùng dạng tên miền vẫn phải được coi là file nếu nó có thật."""
    d = tmp_path / "example.com"
    d.mkdir()
    (d / "a.mp4").write_bytes(b"x")
    assert looks_like_bare_url(f"{d}/a.mp4") is False


def test_is_url_va_normalize_bat_tay_nhau():
    """`is_url` cho đi qua, `normalize_url` thêm lược đồ — thiếu một trong hai
    là liên kết vẫn hỏng, chỉ khác chỗ hỏng."""
    from autodub.transcribe_tool import is_url

    assert is_url("www.youtube.com/watch?v=abc&list=PLx") is True
    assert (dl.normalize_url("www.youtube.com/watch?v=abc&list=PLx")
            == "https://www.youtube.com/watch?v=abc")
    assert is_url("thu_muc/phim.mp4") is False
