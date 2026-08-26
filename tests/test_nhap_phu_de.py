"""Nhập video + phụ đề tiếng Việt sẵn thành dự án chỉnh sửa được (chặng 1).

Người dùng thật hỏi hai câu, 26/8/2026:

- *"lấy giọng đọc .srt cho ra tiếng Việt ghép vào trong chỉnh sửa được không"*
- *"ở chỗ chỉnh sửa tôi có thể lấy video từ file… hay chỉ chỉnh sửa được video
  làm trên tool này"*

Cả hai đều chưa được, và cả hai đều thiếu **cùng một mảnh**: biến (video, phụ
đề) thành thư mục dự án đúng khuôn. Mọi thứ phía sau — sinh giọng, ghép tiếng
theo mốc, xuất video — đã chạy được từ lâu.

Bộ test này khoá đúng ba chỗ chắc chắn vướng với phụ đề thật ngoài đời: câu bị
cắt làm đôi, mốc chồng nhau, và dòng rác.
"""
from __future__ import annotations

import json
import os

import pytest

from autodub import nhap_phu_de as npd
from autodub.text.subtitle_parse import Cue

SRT_MAU = """1
00:00:01,000 --> 00:00:03,000
Xin chào các bạn,

2
00:00:03,000 --> 00:00:05,000
hôm nay mình giới thiệu sản phẩm mới.

3
00:00:06,500 --> 00:00:09,000
Cảm ơn đã xem hết video.
"""


@pytest.fixture()
def video_gia(tmp_path):
    p = tmp_path / "video.mp4"
    p.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    return str(p)


@pytest.fixture()
def srt(tmp_path):
    p = tmp_path / "phu_de.srt"
    p.write_text(SRT_MAU, encoding="utf-8")
    return str(p)


def _cue(i, dau, cuoi, chu):
    return Cue(index=i, start=dau, end=cuoi, text=chu)


# -- Đổi dòng phụ đề thành câu thoại -----------------------------------------

def test_cau_mang_du_truong_trinh_chinh_sua_can(srt, video_gia, tmp_path):
    ket = npd.nhap_du_an(video_gia, srt, str(tmp_path / "out"))
    duong = os.path.join(ket.thu_muc, "data", "transcript_vi.json")
    cau = json.load(open(duong, encoding="utf-8"))

    assert cau, "không có câu nào"
    for c in cau:
        for truong in ("id", "start", "end", "duration", "text", "text_vi"):
            assert truong in c, f"thiếu trường «{truong}» — Trình chỉnh sửa sẽ không mở được"
    assert [c["id"] for c in cau] == list(range(1, len(cau) + 1))


def test_phu_de_da_la_tieng_viet_thi_KHONG_dich(srt, video_gia, tmp_path):
    """Bản gốc và bản đích là một — không gọi máy chủ, không tốn Vox."""
    ket = npd.nhap_du_an(video_gia, srt, str(tmp_path / "out"))
    cau = json.load(open(os.path.join(ket.thu_muc, "data",
                                      "transcript_vi.json"), encoding="utf-8"))
    for c in cau:
        assert c["text"] == c["text_vi"]


def test_cau_bi_cat_lam_doi_duoc_gop_lai():
    """Phụ đề hay cắt câu cho vừa dòng; đọc thẳng thì giọng ngắt cụt."""
    cues = [_cue(1, "00:00:01,000", "00:00:03,000", "Xin chào các bạn,"),
            _cue(2, "00:00:03,000", "00:00:05,000", "hôm nay trời đẹp.")]
    cau, canh_bao = npd.dung_cau_thoai(cues, gop=True)

    assert len(cau) == 1, "hai mẩu của cùng một câu phải thành một"
    assert cau[0]["text"] == "Xin chào các bạn, hôm nay trời đẹp."
    assert cau[0]["start"] == 1.0 and cau[0]["end"] == 5.0
    assert any("Gộp" in c for c in canh_bao), "gộp mà không nói ra"


def test_tat_gop_thi_giu_nguyen_tung_dong():
    cues = [_cue(1, "00:00:01,000", "00:00:03,000", "Xin chào các bạn,"),
            _cue(2, "00:00:03,000", "00:00:05,000", "hôm nay trời đẹp.")]
    cau, _ = npd.dung_cau_thoai(cues, gop=False)
    assert len(cau) == 2


# -- Ba loại rác của phụ đề thật ---------------------------------------------

def test_moc_chong_nhau_duoc_nan_lai():
    """Giữ nguyên thì lúc ghép tiếng hai câu đọc đè lên nhau."""
    cues = [_cue(1, "00:00:01,000", "00:00:06,000", "Câu một."),
            _cue(2, "00:00:04,000", "00:00:08,000", "Câu hai.")]
    cau, canh_bao = npd.dung_cau_thoai(cues, gop=False)

    assert cau[0]["end"] <= cau[1]["start"]
    assert any("chồng nhau" in c for c in canh_bao)


def test_dong_rong_bi_bo_va_duoc_DEM(  ):
    cues = [_cue(1, "00:00:01,000", "00:00:02,000", "   "),
            _cue(2, "00:00:02,000", "00:00:04,000", "Câu thật.")]
    cau, canh_bao = npd.dung_cau_thoai(cues, gop=False)

    assert len(cau) == 1
    assert any("không có chữ" in c for c in canh_bao), (
        "bỏ dòng mà im lặng thì người dùng tưởng phụ đề của mình bị mất chữ")


def test_moc_lui_bi_bo():
    cues = [_cue(1, "00:00:05,000", "00:00:02,000", "Mốc ngược."),
            _cue(2, "00:00:06,000", "00:00:08,000", "Câu thật.")]
    cau, canh_bao = npd.dung_cau_thoai(cues, gop=False)

    assert [c["text"] for c in cau] == ["Câu thật."]
    assert any("không hợp lệ" in c for c in canh_bao)


def test_khong_con_dong_nao_dung_duoc_thi_noi_ro():
    with pytest.raises(npd.LoiNhap) as loi:
        npd.dung_cau_thoai([_cue(1, "00:00:01,000", "00:00:02,000", "")])
    assert ".srt" in str(loi.value), "phải nói định dạng cần dùng"


# -- Dựng thư mục dự án ------------------------------------------------------

def test_KHONG_chep_video_chi_ghi_nho_duong_dan(srt, video_gia, tmp_path):
    """Chép một tệp 2 GB chỉ để mở ra sửa là việc vô ích."""
    ket = npd.nhap_du_an(video_gia, srt, str(tmp_path / "out"))

    trong_thu_muc = os.listdir(ket.thu_muc)
    assert not any(t.endswith(".mp4") for t in trong_thu_muc), (
        "đã chép video vào thư mục dự án")
    moc = json.load(open(os.path.join(ket.thu_muc, "data",
                                      "source_video.json"), encoding="utf-8"))
    assert moc["file_path"] == os.path.abspath(video_gia)


def test_trinh_chinh_sua_MO_DUOC_du_an_vua_nhap(srt, video_gia, tmp_path):
    """Phép thử thật sự của cả chặng: chính hàm mở dự án của Editor."""
    from autodub.editor import load_work_dir

    ket = npd.nhap_du_an(video_gia, srt, str(tmp_path / "out"))
    state = load_work_dir(ket.thu_muc)

    assert state.segments, "mở được nhưng không có câu nào"
    assert state.target.text_field == "text_vi"
    assert state.video_path == os.path.abspath(video_gia), (
        "Editor không tìm ra video nguồn thì không xuất lại được")


def test_thieu_tep_thi_bao_ro_thieu_cai_gi(tmp_path, srt, video_gia):
    with pytest.raises(npd.LoiNhap) as loi:
        npd.nhap_du_an(str(tmp_path / "khong-co.mp4"), srt, str(tmp_path))
    assert "video" in str(loi.value).lower()

    with pytest.raises(npd.LoiNhap) as loi2:
        npd.nhap_du_an(video_gia, str(tmp_path / "khong-co.srt"), str(tmp_path))
    assert "phụ đề" in str(loi2.value)


# -- Cửa vào trong giao diện (chặng 2) ---------------------------------------

def test_trang_trinh_chinh_sua_co_nut_nhap():
    """Làm xong lõi mà không có nút thì người dùng vẫn không dùng được."""
    import inspect

    pytest.importorskip("PySide6")
    from autodub_gui.pages import editor_launcher_page as elp

    nguon = inspect.getsource(elp.EditorLauncherPage)
    assert "Mở video + phụ đề" in nguon, "không có nút nào mở đường này"
    assert "nhap_du_an" in nguon, "nút không nối vào hàm nhập"


def test_nhap_xong_thi_MO_LUON_du_an(tmp_path, monkeypatch, srt, video_gia):
    """Nhập xong mà bắt người dùng tự đi tìm dự án vừa tạo là bỏ dở việc."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QFileDialog

    from autodub.config import Settings
    from autodub_gui.pages import editor_launcher_page as elp

    QApplication.instance() or QApplication([])
    settings = Settings()
    settings.output_dir = str(tmp_path / "out")
    trang = elp.EditorLauncherPage(lambda: settings)

    chon = iter([(video_gia, ""), (srt, "")])
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        lambda *a, **k: next(chon))
    da_mo = []
    trang.open_requested.connect(da_mo.append)

    trang._nhap_video_phu_de()

    assert da_mo, "nhập xong nhưng không mở dự án"
    assert os.path.isdir(da_mo[0])
    assert os.path.isfile(os.path.join(da_mo[0], "data", "transcript_vi.json"))


def test_bo_giua_chung_thi_khong_tao_ra_gi(tmp_path, monkeypatch):
    """Bấm Huỷ ở hộp chọn tệp không được để lại thư mục dự án rỗng."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QFileDialog

    from autodub.config import Settings
    from autodub_gui.pages import editor_launcher_page as elp

    QApplication.instance() or QApplication([])
    settings = Settings()
    goc = tmp_path / "out"
    settings.output_dir = str(goc)
    trang = elp.EditorLauncherPage(lambda: settings)

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    da_mo = []
    trang.open_requested.connect(da_mo.append)

    trang._nhap_video_phu_de()

    assert not da_mo
    assert not goc.exists(), "huỷ giữa chừng mà vẫn tạo thư mục"
