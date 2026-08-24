"""C25 — cắt tệp dài thành nhiều đoạn.

Người dùng có tệp `.m4a` dài 3 giờ 43 và **không có phần mềm cắt nào**. ffmpeg
thì app đã cần sẵn cho mọi việc khác, nên "phải cài thêm phần mềm" là câu trả
lời sai.
"""
from __future__ import annotations

import os
import subprocess

import pytest

from autodub.media import cat_tep


def _co_ffmpeg() -> bool:
    from autodub.ffmpeg_deps import co_ffmpeg
    return co_ffmpeg()


needs_ffmpeg = pytest.mark.skipif(not _co_ffmpeg(), reason="máy chưa có ffmpeg")


@pytest.fixture()
def tep_thu(tmp_path):
    """Một tệp âm thanh THẬT dài 310 giây."""
    ra = tmp_path / "thu.m4a"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=310", "-c:a", "aac", "-b:a", "48k",
         str(ra)], check=True, timeout=120)
    return str(ra)


# -- Chặn trước khi chạy -----------------------------------------------------

def test_tep_khong_ton_tai_thi_bao_ngay(tmp_path):
    with pytest.raises(FileNotFoundError):
        cat_tep.cat_deu(str(tmp_path / "khong-co.m4a"))


@pytest.mark.parametrize("phut", [0, -5, 999])
def test_do_dai_doan_vo_ly_bi_chan(tmp_path, phut):
    tep = tmp_path / "a.m4a"
    tep.write_bytes(b"x")
    with pytest.raises(ValueError, match="phút"):
        cat_tep.cat_deu(str(tep), phut=phut)


# -- Cắt thật ----------------------------------------------------------------

@needs_ffmpeg
def test_cat_dung_so_doan_va_KHONG_MAT_thoi_luong(tep_thu, tmp_path):
    """Tổng thời lượng các đoạn phải bằng tệp gốc — mất một giây là mất lời."""
    phan = cat_tep.cat_deu(tep_thu, str(tmp_path / "ra"), phut=2)
    assert len(phan) == 3, "310 giây chia 120 giây phải ra 3 đoạn"
    tong = sum(cat_tep.do_dai_giay(p) for p in phan)
    assert abs(tong - 310) < 2, f"tổng {tong:.1f}s, gốc 310s"


@needs_ffmpeg
def test_ten_tep_mang_MOC_BAT_DAU(tep_thu, tmp_path):
    """Sau khi cắt, mốc trong mỗi bản chép lời chạy lại từ 0. Không nói ra thì
    người đọc tưởng phút 5 của phần 3 là phút 5 của cả buổi."""
    phan = cat_tep.cat_deu(tep_thu, str(tmp_path / "ra"), phut=2)
    ten = [os.path.basename(p) for p in phan]
    assert "tu_00-00-00" in ten[0]
    assert "tu_00-02-00" in ten[1]
    assert "tu_00-04-00" in ten[2]


@needs_ffmpeg
def test_thu_tu_doan_dung_theo_thoi_gian(tep_thu, tmp_path):
    phan = cat_tep.cat_deu(tep_thu, str(tmp_path / "ra"), phut=2)
    assert phan == sorted(phan), "thứ tự trả về không theo thời gian"


@needs_ffmpeg
def test_tep_ngan_hon_mot_doan_thi_TRA_VE_CHINH_NO(tep_thu, tmp_path):
    """Cắt tệp 5 phút thành «một đoạn 5 phút» chỉ tạo thêm bản sao vô ích."""
    assert cat_tep.cat_deu(tep_thu, str(tmp_path / "ra"), phut=30) == [tep_thu]
    assert not os.path.exists(str(tmp_path / "ra" / "thu_phan_01.m4a"))


@needs_ffmpeg
def test_moi_doan_van_MO_DUOC(tep_thu, tmp_path):
    """Cắt xong mà tệp không phát được thì cắt để làm gì."""
    phan = cat_tep.cat_deu(tep_thu, str(tmp_path / "ra"), phut=2)
    for p in phan:
        assert cat_tep.do_dai_giay(p) > 0, f"{p} không đọc được độ dài"
        assert os.path.getsize(p) > 1000


# -- Không mã hoá lại --------------------------------------------------------

def test_CHEP_LUONG_khong_ma_hoa_lai():
    """Mã hoá lại tệp 3 giờ mất hàng chục phút để đổi lấy một tệp xấu hơn."""
    import inspect

    than = inspect.getsource(cat_tep.cat_deu)
    assert '"-c", "copy"' in than
    for cam in ("-b:a", "libx264", "aac"):
        assert cam not in than, f"đang mã hoá lại bằng «{cam}»"


def test_dat_lai_moc_thoi_gian_cho_tung_doan():
    """Thiếu cờ này thì đoạn 2 mang mốc của phút 30 và nhiều trình phát tưởng
    tệp hỏng."""
    import inspect

    assert '"-reset_timestamps", "1"' in inspect.getsource(cat_tep.cat_deu)


def test_giao_dien_chay_cat_trong_LUONG_NEN():
    """Cắt tệp vài GB trên ổ chậm vẫn có thể mất chục giây."""
    from tests.doc_ma import co_goi

    from autodub_gui.pages.transcribe_page import TranscribePage

    assert not co_goi(TranscribePage._cat_tep, "cat_deu"), \
        "đang cắt thẳng trên luồng giao diện"
    assert co_goi(TranscribePage._cat_tep, "CatTepWorker")


# -- Cắt theo KHOẢNG LẶNG (mini-spec C26) -----------------------------------
#
# Cắt đều tăm tắp thì mỗi ranh giới rơi vào giữa một câu. Tệp 3 giờ 43 cắt 8
# đoạn là 7 câu bị chia đôi — và một câu bị chia đôi là một câu SAI ở CẢ HAI
# bản chép lời.

def test_nan_moc_ve_khoang_lang_gan_nhat():
    # Mốc đều là 120s; có quãng im ở 118.4 → phải cắt ở 118.4.
    assert cat_tep.chon_moc_cat(310, 2, [30.0, 118.4, 243.9]) == [118.4, 243.9]


def test_khong_co_lang_du_gan_thi_GIU_moc_deu():
    """Thà cắt giữa câu còn hơn để một đoạn dài gấp đôi các đoạn khác."""
    assert cat_tep.chon_moc_cat(310, 2, [5.0]) == [120.0, 240.0]


def test_khong_nan_lui_qua_moc_truoc():
    """Hai mốc dính nhau tạo ra một đoạn dài vài giây — vô dụng."""
    moc = cat_tep.chon_moc_cat(600, 2, [118.0, 121.0, 238.0, 241.0])
    assert all(b - a > 5 for a, b in zip(moc, moc[1:]))


@pytest.fixture()
def tep_co_khoang_lang(tmp_path):
    """55s tiếng — 4s im — 55s tiếng — 4s im — 55s tiếng.

    Mốc đều 60s rơi GIỮA tiếng; quãng im ở ~57s và ~116s.
    """
    ra = tmp_path / "bai.m4a"
    loc = ("sine=frequency=440:duration=55[a];"
           "anullsrc=r=44100:cl=mono,atrim=duration=4[s1];"
           "sine=frequency=550:duration=55[b];"
           "anullsrc=r=44100:cl=mono,atrim=duration=4[s2];"
           "sine=frequency=660:duration=55[c];"
           "[a][s1][b][s2][c]concat=n=5:v=0:a=1[out]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-filter_complex", loc,
                    "-map", "[out]", "-c:a", "aac", "-b:a", "48k", str(ra)],
                   check=True, timeout=120)
    return str(ra)


@needs_ffmpeg
def test_do_dung_cac_quang_im(tep_co_khoang_lang):
    lang = cat_tep.tim_khoang_lang(tep_co_khoang_lang)
    assert len(lang) == 2, f"dò ra {len(lang)} quãng im, mong 2"
    assert abs(lang[0] - 57) < 2, lang
    assert abs(lang[1] - 116) < 2, lang


@needs_ffmpeg
def test_cat_THAT_roi_vao_cho_im_khong_roi_giua_tieng(tep_co_khoang_lang, tmp_path):
    phan = cat_tep.cat_deu(tep_co_khoang_lang, str(tmp_path / "ra"), phut=1)
    assert len(phan) == 3
    # Đoạn 1 phải dài ~57s (mốc lặng), KHÔNG phải 60s (mốc đều).
    d1 = cat_tep.do_dai_giay(phan[0])
    assert abs(d1 - 57) < 2, f"đoạn 1 dài {d1:.1f}s — vẫn đang cắt đều"
    assert abs(sum(cat_tep.do_dai_giay(p) for p in phan) - 173) < 2


@needs_ffmpeg
def test_ten_tep_mang_moc_THAT_khong_suy_tu_so_thu_tu(tep_co_khoang_lang, tmp_path):
    """Mốc đã nắn thì `số thứ tự × độ dài đoạn` là sai."""
    phan = cat_tep.cat_deu(tep_co_khoang_lang, str(tmp_path / "ra"), phut=1)
    ten = [os.path.basename(p) for p in phan]
    assert "tu_00-00-57" in ten[1], ten   # không phải 00-01-00
    assert "tu_00-01-56" in ten[2], ten   # không phải 00-02-00


@needs_ffmpeg
def test_tat_do_khoang_lang_thi_quay_ve_cat_deu(tep_co_khoang_lang, tmp_path):
    phan = cat_tep.cat_deu(tep_co_khoang_lang, str(tmp_path / "ra"), phut=1,
                           theo_khoang_lang=False)
    assert abs(cat_tep.do_dai_giay(phan[0]) - 60) < 2


# -- Tệp dài thì TỰ cắt và TỰ ghép (mini-spec C26) --------------------------

def test_tep_ngan_thi_khong_cat_gi_ca(monkeypatch):
    from autodub import transcribe_tool as tt

    monkeypatch.setattr("autodub.media.cat_tep.do_dai_giay", lambda p: 600)
    monkeypatch.setattr("autodub.media.cat_tep.cat_deu",
                        lambda *a, **k: pytest.fail("tệp 10 phút mà đi cắt"))
    goi = {}

    def _asr(path, lang, settings, **k):
        goi["path"] = path
        return [{"id": 1, "start": 0, "end": 1, "text": "x"}]

    ra = tt._chep_mot_hoac_nhieu_doan(
        "a.m4a", "vi", None, _asr, cancel_event=None,
        ghi_dan=tt._GhiDan("/tmp/khong-dung.txt"), say=lambda *a, **k: None)
    assert len(ra) == 1


def test_tep_dai_thi_DOI_MOC_ve_thoi_gian_that(monkeypatch, tmp_path):
    """Không dời thì tám đoạn đều bắt đầu từ 00:00 và bản ghép lại vô nghĩa."""
    from autodub import transcribe_tool as tt

    doan = [str(tmp_path / f"p{i}.m4a") for i in range(3)]
    for d in doan:
        open(d, "wb").close()
    monkeypatch.setattr("autodub.media.cat_tep.do_dai_giay",
                        lambda p: 4 * 3600 if p == "dai.m4a" else 3600)
    monkeypatch.setattr("autodub.media.cat_tep.cat_deu", lambda *a, **k: doan)
    monkeypatch.setattr(tt, "_don_tam", lambda *a, **k: None)

    def _asr(path, lang, settings, **k):
        # Mỗi đoạn đều trả câu bắt đầu từ 0 — đúng như ASR thật.
        return [{"id": 1, "start": 10.0, "end": 12.0, "text": "câu"}]

    ra = tt._chep_mot_hoac_nhieu_doan(
        "dai.m4a", "vi", None, _asr, cancel_event=None,
        ghi_dan=tt._GhiDan(str(tmp_path / "t.txt")), say=lambda *a, **k: None)

    assert [c["start"] for c in ra] == [10.0, 3610.0, 7210.0]
    assert [c["id"] for c in ra] == [1, 2, 3], "số thứ tự câu phải chạy liền"
