"""V71 — chuyển giọng nói thành văn bản (liên kết / video / mp3).

Lớp này cố ý mỏng: mọi mảnh nặng (tải liên kết, bóc tiếng, ASR, xuất SRT) đã
chạy thật trong luồng dub. Test ở đây khoá đúng phần MỚI: nối các mảnh, chọn
đường đi theo kiểu đầu vào, và xuất đúng định dạng.
"""
from __future__ import annotations

import json
import os

import pytest

from autodub.config import Settings
from autodub import transcribe_tool as tt


SEGS = [
    {"start": 0.0, "end": 2.5, "text": "Câu thứ nhất."},
    {"start": 2.5, "end": 5.0, "text": "Câu thứ hai."},
    {"start": 5.0, "end": 7.25, "text": "   "},          # câu rỗng
]


# ------------------------------------------------------------ nhận dạng đầu vào
def test_phan_biet_lien_ket_va_file():
    assert tt.is_url("https://youtu.be/abc") is True
    assert tt.is_url("http://example.com/a.mp4") is True
    assert tt.is_url("C:/video/phim.mp4") is False
    assert tt.is_url("/home/coder/a.mp3") is False


def test_nhan_ra_file_am_thanh():
    assert tt.is_audio_file("bai.mp3") is True
    assert tt.is_audio_file("BAI.MP3") is True, "đuôi viết hoa vẫn là mp3"
    assert tt.is_audio_file("phim.mp4") is False


# ------------------------------------------------------------------- xuất file
def test_vtt_dung_DAU_CHAM_cho_mili_giay(tmp_path):
    """SRT dùng dấu phẩy, VTT dùng dấu chấm. Nhầm là trình phát bỏ qua cả file
    mà không báo lỗi gì."""
    out = tmp_path / "a.vtt"
    tt.write_vtt(SEGS, str(out))
    noi_dung = out.read_text(encoding="utf-8")

    assert noi_dung.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:02.500" in noi_dung
    assert "," not in noi_dung.split("\n")[2], "không được dùng dấu phẩy kiểu SRT"


def test_vtt_bo_cau_rong(tmp_path):
    out = tmp_path / "a.vtt"
    tt.write_vtt(SEGS, str(out))
    assert out.read_text(encoding="utf-8").count("-->") == 2


def test_lam_tron_999_khong_sinh_ra_1000_mili_giay():
    """2.9999 làm tròn lên phải thành 00:00:03.000, không phải 00:00:02.1000."""
    assert tt._vtt_timestamp(2.9999) == "00:00:03.000"
    assert tt._vtt_timestamp(59.9999) == "00:01:00.000"


def test_txt_khong_moc_thoi_gian_mac_dinh(tmp_path):
    out = tmp_path / "a.txt"
    tt.write_txt(SEGS, str(out))
    assert out.read_text(encoding="utf-8") == "Câu thứ nhất.\nCâu thứ hai.\n"


def test_txt_co_moc_thoi_gian_khi_duoc_yeu_cau(tmp_path):
    out = tmp_path / "a.txt"
    tt.write_txt(SEGS, str(out), with_timestamps=True)
    assert "[00:00:02.500] Câu thứ hai." in out.read_text(encoding="utf-8")


# ----------------------------------------------------------- tên file kết quả
def test_ten_file_uu_tien_tieu_de_video():
    assert tt._output_basename("https://youtu.be/x", "Phim Hay Số 1") == "Phim Hay Số 1"


def test_ten_file_lui_ve_ten_file_goc():
    assert tt._output_basename("/tmp/bai_giang.mp4", "") == "bai_giang"


def test_ten_file_bo_ky_tu_Windows_cam():
    ten = tt._output_basename("https://x/y", 'A/B:C*D?E"F<G>H|I')
    for c in '\\/:*?"<>|':
        assert c not in ten


def test_ten_rong_sau_khi_loc_khong_sinh_file_khong_mo_duoc():
    """Tiêu đề toàn ký tự cấm → tên rỗng → file `.txt` Windows không mở nổi."""
    assert tt._output_basename("https://x/y", '///:::') == "ban_ghi"
    assert tt._output_basename("https://x/y", "") == "ban_ghi"


# --------------------------------------------------------------- luồng chính
def _gia_lap(monkeypatch, tmp_path, segments=None):
    """Thay 2 biên ngoài: tải mạng và ASR. Phần nối vẫn chạy thật."""
    goi = {}

    def gia_extract(media_path, output_path, *a, **k):
        goi["extract"] = media_path
        with open(output_path, "wb") as f:
            f.write(b"\0" * 100)
        return output_path

    monkeypatch.setattr("autodub.media.audio.extract_audio", gia_extract)

    def gia_asr(audio, lang, st, **k):
        goi["lang"] = lang
        return segments if segments is not None else SEGS

    monkeypatch.setattr("autodub.speech.transcriber.transcribe", gia_asr)
    return goi


def test_file_tren_may_khong_goi_tai_mang(monkeypatch, tmp_path):
    goi = _gia_lap(monkeypatch, tmp_path)

    def no_ra(*a, **k):
        raise AssertionError("file trên máy KHÔNG được đụng tới mạng")

    monkeypatch.setattr("autodub.media.downloader.download_one", no_ra)
    src = tmp_path / "phim.mp4"
    src.write_bytes(b"\0")

    kq = tt.transcribe_media(str(src), str(tmp_path / "out"), Settings(),
                             formats=("txt",))
    assert len(kq.segments) == 3
    assert os.path.isfile(kq.outputs["txt"])


def test_lien_ket_di_qua_downloader(monkeypatch, tmp_path):
    goi = _gia_lap(monkeypatch, tmp_path)
    media = tmp_path / "tai_ve.mp4"
    media.write_bytes(b"\0")
    def gia_tai(url, out, **k):
        goi["url"] = url
        return {"filepath": str(media), "title": "Video Thử"}

    monkeypatch.setattr("autodub.media.downloader.download_one", gia_tai)

    kq = tt.transcribe_media("https://youtu.be/abc", str(tmp_path / "out"),
                             Settings(), formats=("txt", "vtt"))

    assert goi["url"] == "https://youtu.be/abc"
    assert kq.title == "Video Thử"
    assert kq.outputs["txt"].endswith("Video Thử.txt"), "tên file theo tiêu đề video"


def test_file_mp3_van_di_qua_ffmpeg(monkeypatch, tmp_path):
    """ASR cần 16 kHz mono; mp3 tải trên mạng thường 44.1 kHz stereo."""
    goi = _gia_lap(monkeypatch, tmp_path)
    src = tmp_path / "bai.mp3"
    src.write_bytes(b"\0")

    tt.transcribe_media(str(src), str(tmp_path / "out"), Settings(), formats=("txt",))
    assert goi["extract"] == str(src), "mp3 vẫn phải qua bước chuẩn hoá"


def test_xuat_du_moi_dinh_dang_duoc_yeu_cau(monkeypatch, tmp_path):
    _gia_lap(monkeypatch, tmp_path)
    src = tmp_path / "phim.mp4"
    src.write_bytes(b"\0")

    kq = tt.transcribe_media(str(src), str(tmp_path / "out"), Settings(),
                             formats=("txt", "srt", "vtt", "json"))

    assert set(kq.outputs) == {"txt", "srt", "vtt", "json"}
    for path in kq.outputs.values():
        assert os.path.isfile(path)
    du_lieu = json.loads(open(kq.outputs["json"], encoding="utf-8").read())
    assert len(du_lieu) == 3, "bản json giữ NGUYÊN mốc thời gian từng câu"


def test_dinh_dang_la_bao_loi_som_truoc_khi_ton_thoi_gian_ASR(monkeypatch, tmp_path):
    """Chạy ASR xong mới báo sai định dạng là phí vài phút của người dùng."""
    def no_ra(*a, **k):
        raise AssertionError("không được chạy ASR khi định dạng đã sai")

    monkeypatch.setattr("autodub.speech.transcriber.transcribe", no_ra)
    with pytest.raises(tt.TranscribeError, match="docx"):
        tt.transcribe_media("/tmp/x.mp4", str(tmp_path), Settings(),
                            formats=("txt", "docx"))


def test_khong_nghe_duoc_cau_nao_bao_loi_ro_rang(monkeypatch, tmp_path):
    _gia_lap(monkeypatch, tmp_path, segments=[])
    src = tmp_path / "phim.mp4"
    src.write_bytes(b"\0")

    with pytest.raises(tt.TranscribeError, match="không có tiếng nói|sai ngôn ngữ"):
        tt.transcribe_media(str(src), str(tmp_path / "out"), Settings(),
                            formats=("txt",))


def test_file_khong_ton_tai_bao_loi_nguoi_doc_hieu(tmp_path):
    with pytest.raises(tt.TranscribeError, match="Không tìm thấy file"):
        tt.prepare_audio("/khong/co/that.mp4", str(tmp_path))


def test_ngon_ngu_de_trong_thi_dung_mac_dinh_cua_settings(monkeypatch, tmp_path):
    """Không đẻ ra mặc định thứ hai — dùng đúng `default_source_lang` của app."""
    goi = _gia_lap(monkeypatch, tmp_path)
    settings = Settings()
    settings.default_source_lang = "ko"
    src = tmp_path / "phim.mp4"
    src.write_bytes(b"\0")

    tt.transcribe_media(str(src), str(tmp_path / "out"), settings, formats=("txt",))
    assert goi["lang"] == "ko"


def test_ngon_ngu_truyen_tay_thang_mac_dinh(monkeypatch, tmp_path):
    goi = _gia_lap(monkeypatch, tmp_path)
    settings = Settings()
    settings.default_source_lang = "ko"
    src = tmp_path / "phim.mp4"
    src.write_bytes(b"\0")

    tt.transcribe_media(str(src), str(tmp_path / "out"), settings,
                        language="en", formats=("txt",))
    assert goi["lang"] == "en"


def test_thuoc_tinh_text_gop_ca_ban_ghi(monkeypatch, tmp_path):
    _gia_lap(monkeypatch, tmp_path)
    src = tmp_path / "phim.mp4"
    src.write_bytes(b"\0")

    kq = tt.transcribe_media(str(src), str(tmp_path / "out"), Settings(),
                             formats=("txt",))
    assert kq.text == "Câu thứ nhất.\nCâu thứ hai."


# =============================================== V72: huỷ + chép lời hàng loạt
import threading  # noqa: E402

from autodub.speech.transcriber import TranscribeCancelled  # noqa: E402


def test_bung_thu_muc_thanh_danh_sach_file(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"\0")
    (tmp_path / "b.mp3").write_bytes(b"\0")
    (tmp_path / "ghi_chu.txt").write_bytes(b"\0")     # không phải media
    (tmp_path / "con").mkdir()
    (tmp_path / "con" / "c.mp4").write_bytes(b"\0")   # thư mục con: bỏ qua

    ra = tt.expand_sources([str(tmp_path)])
    assert [os.path.basename(x) for x in ra] == ["a.mp4", "b.mp3"]


def test_khong_de_quy_vao_thu_muc_con(tmp_path):
    """Thư mục con thường là bản nháp/file tạm — quét vào là chép lời cả rác."""
    (tmp_path / "con").mkdir()
    (tmp_path / "con" / "c.mp4").write_bytes(b"\0")
    assert tt.expand_sources([str(tmp_path)]) == []


def test_bo_trung_giu_nguyen_thu_tu():
    ra = tt.expand_sources(["https://b/2", "https://a/1", "https://b/2"])
    assert ra == ["https://b/2", "https://a/1"], "dán trùng thì chỉ chạy một lần"


def test_lien_ket_va_file_tron_lan_deu_nhan():
    ra = tt.expand_sources(["https://youtu.be/x", "", "  ", "/tmp/a.mp4"])
    assert ra == ["https://youtu.be/x", "/tmp/a.mp4"]


def test_mot_muc_hong_KHONG_lam_hong_ca_me(monkeypatch, tmp_path):
    """Dừng cả mẻ vì một liên kết chết là bắt làm lại từ đầu những mục đã xong."""
    goi = []

    def gia(source, out, st, **k):
        goi.append(source)
        if "hong" in source:
            raise RuntimeError("liên kết chết")
        return tt.TranscribeResult(source=source, audio_path="", segments=SEGS)

    monkeypatch.setattr(tt, "transcribe_media", gia)
    ket = tt.transcribe_many(["/a.mp4", "/hong.mp4", "/b.mp4"],
                             str(tmp_path), Settings())

    assert [m.status for m in ket] == ["xong", "hong", "xong"]
    assert ket[1].error == "liên kết chết"
    assert len(goi) == 3, "mục sau mục hỏng vẫn phải chạy"


def test_huy_thi_muc_con_lai_danh_dau_huy_KHONG_phai_hong(monkeypatch, tmp_path):
    """Người dùng chủ động dừng thì không được báo là thất bại."""
    cancel = threading.Event()

    def gia(source, out, st, **k):
        cancel.set()          # mục đầu chạy xong thì bấm Dừng
        return tt.TranscribeResult(source=source, audio_path="", segments=SEGS)

    monkeypatch.setattr(tt, "transcribe_media", gia)
    ket = tt.transcribe_many(["/a.mp4", "/b.mp4", "/c.mp4"], str(tmp_path),
                             Settings(), cancel_event=cancel)

    assert [m.status for m in ket] == ["xong", "huy", "huy"]


def test_huy_giua_mot_muc_khong_xoa_ket_qua_muc_da_xong(monkeypatch, tmp_path):
    cancel = threading.Event()
    dem = {"n": 0}

    def gia(source, out, st, **k):
        dem["n"] += 1
        if dem["n"] == 2:
            raise TranscribeCancelled("Đã dừng theo yêu cầu.")
        return tt.TranscribeResult(source=source, audio_path="", segments=SEGS)

    monkeypatch.setattr(tt, "transcribe_media", gia)
    ket = tt.transcribe_many(["/a.mp4", "/b.mp4", "/c.mp4"], str(tmp_path),
                             Settings(), cancel_event=cancel)

    assert ket[0].status == "xong" and ket[0].result is not None
    assert ket[1].status == "huy" and ket[2].status == "huy"


def test_hai_file_TRUNG_TEN_khong_ghi_de_nhau(monkeypatch, tmp_path):
    """`Tap1/video.mp4` và `Tap2/video.mp4` là chuyện thường — file sau ghi đè
    file trước thì người dùng chỉ phát hiện khi mở ra thấy thiếu."""
    ten = []

    def gia(source, out, st, **k):
        ten.append(k.get("output_name"))
        return tt.TranscribeResult(source=source, audio_path="", segments=SEGS)

    monkeypatch.setattr(tt, "transcribe_media", gia)
    tt.transcribe_many(["/Tap1/video.mp4", "/Tap2/video.mp4", "/Tap3/video.mp4"],
                       str(tmp_path), Settings())

    assert ten == ["video", "video_2", "video_3"]


def test_lien_ket_de_transcribe_media_tu_dat_ten(monkeypatch, tmp_path):
    """Tên của liên kết phải chờ tải xong mới biết tiêu đề."""
    ten = []
    monkeypatch.setattr(tt, "transcribe_media",
                        lambda s, o, st, **k: (ten.append(k.get("output_name"))
                                               or tt.TranscribeResult(s, "", SEGS)))
    tt.transcribe_many(["https://youtu.be/x"], str(tmp_path), Settings())
    assert ten == [""]


def test_kiem_huy_khong_no_khi_khong_co_co(tmp_path):
    tt._kiem_huy(None)          # không có cờ = không huỷ, không được ném gì


def test_kiem_huy_nem_dung_ngoai_le_rieng():
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(TranscribeCancelled):
        tt._kiem_huy(cancel)


def test_huy_TRUOC_khi_tai_thi_khong_dung_toi_mang(monkeypatch, tmp_path):
    cancel = threading.Event()
    cancel.set()

    def no_ra(*a, **k):
        raise AssertionError("đã bấm Dừng thì không được tải gì nữa")

    monkeypatch.setattr("autodub.media.downloader.download_one", no_ra)
    with pytest.raises(TranscribeCancelled):
        tt.transcribe_media("https://youtu.be/x", str(tmp_path), Settings(),
                            formats=("txt",), cancel_event=cancel)
