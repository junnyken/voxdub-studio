"""C27 — gộp mẩu vụn thành câu đọc được.

Người dùng chạy chép lời một tệp giảng bài 3 giờ 43 và nhận về những dòng
kiểu «Là những» / «Cử chỉ» / «Hành vi» / «Này.» — mỗi dòng 1-2 chữ, khoảng
tám nghìn dòng. Nguyên nhân: bộ nghe bật lọc khoảng lặng ngưỡng 0,5 giây, mà
người giảng bài ngắt nhịp liên tục.

Chữ thì ĐÚNG và ĐỦ — chỉ chỗ xuống dòng là sai. Nên bản vá nằm ở khâu ghi
`.txt`, không ở khâu nghe.
"""
from __future__ import annotations

import pytest

from autodub import transcribe_tool as tt


def _m(start, end, text):
    return {"start": start, "end": end, "text": text}


def test_noi_cac_mau_ngan_lien_nhau():
    ra = tt.gop_cau([_m(0, 1, "Là những"), _m(1.1, 2, "Cử chỉ"),
                     _m(2.1, 3, "Hành vi")])
    assert len(ra) == 1
    assert ra[0]["text"] == "Là những Cử chỉ Hành vi"


def test_dau_cham_cau_la_ranh_gioi_that():
    ra = tt.gop_cau([_m(0, 1, "Này."), _m(1.1, 2, "Nó gây")])
    assert len(ra) == 2


@pytest.mark.parametrize("dau", [".", "!", "?", "…"])
def test_moi_dau_ket_cau_deu_tach_dong(dau):
    ra = tt.gop_cau([_m(0, 1, f"Xong{dau}"), _m(1.1, 2, "Tiếp")])
    assert len(ra) == 2, dau


def test_nghi_dai_thi_tach_du_khong_co_dau_cham():
    """Nghỉ dài thường là hết ý, kể cả khi bộ nghe không đánh dấu chấm."""
    ra = tt.gop_cau([_m(0, 1, "Hết ý"), _m(3.0, 4, "Ý mới")])
    assert len(ra) == 2


def test_nghi_ngan_thi_KHONG_tach():
    ra = tt.gop_cau([_m(0, 1, "Nửa"), _m(1.2, 2, "câu")])
    assert len(ra) == 1


def test_khong_de_mot_dong_dai_vo_tan():
    """Không có ranh giới nào thì vẫn phải xuống dòng."""
    manh = [_m(i * 0.5, i * 0.5 + 0.4, "chữ") for i in range(200)]
    ra = tt.gop_cau(manh)
    assert len(ra) > 1
    assert all(len(c["text"]) <= tt._GOP_TOI_DA_CHU + 20 for c in ra)


def test_moc_thoi_gian_la_moc_MAU_DAU_TIEN():
    """Người đọc tua tới đó để nghe lại thì phải rơi vào đầu câu."""
    ra = tt.gop_cau([_m(726.0, 727.0, "Là những"), _m(727.1, 730.0, "cử chỉ")])
    assert ra[0]["start"] == 726.0
    assert ra[0]["end"] == 730.0


def test_bo_qua_mau_rong():
    ra = tt.gop_cau([_m(0, 1, "Có"), _m(1, 2, "   "), _m(2, 3, "chữ")])
    assert len(ra) == 1 and ra[0]["text"] == "Có chữ"


def test_danh_sach_rong_thi_khong_no():
    assert tt.gop_cau([]) == []


# -- Phụ đề KHÔNG được gộp ---------------------------------------------------

def test_chi_gop_cho_txt_khong_gop_cho_phu_de():
    """Phụ đề cần từng mẩu ngắn để hiện kịp trên màn hình — gộp ở đó là làm
    hỏng phụ đề."""
    import inspect

    from autodub.text import srt

    assert "gop_cau" not in inspect.getsource(srt), "đang gộp cả phụ đề"
    assert "gop_cau" not in inspect.getsource(tt.write_vtt)


def test_tat_duoc_viec_gop(tmp_path):
    duong = str(tmp_path / "a.txt")
    tt.write_txt([_m(0, 1, "Một"), _m(1.1, 2, "hai")], duong, gop=False)
    assert len(open(duong, encoding="utf-8").read().strip().splitlines()) == 2


# -- Gộp lại tệp đã xuất bằng bản cũ ----------------------------------------

def test_doc_nguoc_tep_txt_co_moc(tmp_path):
    duong = tmp_path / "vun.txt"
    duong.write_text("# ghi chú\n\n[12:06] Là những\n[01:02:03] Sau một tiếng\n",
                     encoding="utf-8")
    cau = tt.doc_txt_co_moc(str(duong))
    assert [c["start"] for c in cau] == [726.0, 3723.0]


def test_dong_khong_dung_khuon_thi_NOI_vao_cau_truoc(tmp_path):
    """Vứt đi là mất chữ."""
    duong = tmp_path / "a.txt"
    duong.write_text("[00:01] Câu đầu\nphần rớt dòng\n", encoding="utf-8")
    cau = tt.doc_txt_co_moc(str(duong))
    assert len(cau) == 1
    assert "phần rớt dòng" in cau[0]["text"]


def test_gop_tep_KHONG_ghi_de_tep_goc(tmp_path):
    """Bản vụn vẫn là dữ liệu thật; gộp sai thì còn đường quay lại."""
    duong = tmp_path / "vun.txt"
    goc = "[12:06] Là những\n[12:07] cử chỉ\n"
    duong.write_text(goc, encoding="utf-8")
    ra = tt.gop_tep_txt(str(duong))
    assert ra != str(duong)
    assert duong.read_text(encoding="utf-8") == goc, "đã ghi đè tệp gốc"
    assert "Là những cử chỉ" in open(ra, encoding="utf-8").read()


def test_tep_khong_phai_ban_chep_loi_thi_bao_ro(tmp_path):
    duong = tmp_path / "linh tinh.txt"
    duong.write_text("không có mốc nào cả\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mốc thời gian"):
        tt.gop_tep_txt(str(duong))


# -- Lọc câu BỊA lặp lại (mini-spec C28) ------------------------------------
#
# Chạy thật bài giảng 3h43: từ phút 33 tới 37, mỗi ~40 giây một dòng "Các bạn
# hãy đăng ký kênh để ủng hộ kênh của mình" — trong khi không ai nói câu nào.
# Whisper học từ hàng triệu phụ đề YouTube nên gặp quãng im là lấp bằng đúng
# những câu quen thuộc nhất.

def test_lap_nhieu_lan_lien_tiep_thi_giu_MOT_ban():
    mau = [{"start": i, "text": "Các bạn hãy đăng ký kênh"} for i in range(5)]
    ra, bo = tt.loc_lap_lai(mau)
    assert len(ra) == 1 and bo == 4


def test_lap_HAI_lan_thi_GIU_NGUYEN():
    """Người nói lặp hai lần là chuyện thật — «Không. Không.»"""
    ra, bo = tt.loc_lap_lai([{"start": 0, "text": "Không"},
                             {"start": 1, "text": "Không"}])
    assert len(ra) == 2 and bo == 0


def test_khac_dau_cau_hay_chu_hoa_van_tinh_la_MOT_cau():
    mau = [{"start": 0, "text": "Đăng ký kênh"},
           {"start": 1, "text": "đăng ký kênh."},
           {"start": 2, "text": "Đăng ký kênh!"}]
    ra, bo = tt.loc_lap_lai(mau)
    assert len(ra) == 1 and bo == 2


def test_lap_KHONG_lien_tiep_thi_khong_dung_toi():
    """Giảng viên nhắc lại một ý ở đoạn sau là chuyện bình thường."""
    mau = [{"start": 0, "text": "Điểm quan trọng"},
           {"start": 1, "text": "Chuyện khác"},
           {"start": 2, "text": "Điểm quan trọng"}]
    ra, bo = tt.loc_lap_lai(mau)
    assert len(ra) == 3 and bo == 0


def test_cau_rong_khong_bi_gom_nham():
    ra, bo = tt.loc_lap_lai([{"start": i, "text": ""} for i in range(5)])
    assert len(ra) == 5 and bo == 0


def test_bao_RA_so_cau_da_bo():
    """Im lặng xoá chữ của người dùng là điều tệ nhất một công cụ chép lời
    có thể làm."""
    _ra, bo = tt.loc_lap_lai([{"start": i, "text": "lặp"} for i in range(7)])
    assert bo == 6


def test_loc_TRUOC_khi_xuat_moi_dinh_dang():
    """Câu bịa là dữ liệu SAI nên phụ đề và .json cũng không được có nó —
    khác hẳn chuyện gộp câu, vốn chỉ là cách trình bày."""
    from tests.doc_ma import cac_luot_goi

    goi = cac_luot_goi(tt.transcribe_media)
    assert "loc_lap_lai" in goi
    assert goi.index("loc_lap_lai") < goi.index("write_txt"), \
        "lọc sau khi đã ghi tệp thì tệp vẫn bẩn"


def test_nut_gop_tep_cu_cung_loc_lap(tmp_path):
    """Tệp xuất bằng bản cũ còn nguyên các câu bịa — đó chính là tệp cần cứu."""
    duong = tmp_path / "vun.txt"
    duong.write_text(
        "[33:48] Các bạn hãy đăng ký kênh\n"
        "[35:11] Các bạn hãy đăng ký kênh\n"
        "[35:55] Các bạn hãy đăng ký kênh\n"
        "[36:38] Các bạn hãy đăng ký kênh\n", encoding="utf-8")
    ra = tt.gop_tep_txt(str(duong))
    assert open(ra, encoding="utf-8").read().count("đăng ký kênh") == 1


def test_tat_bom_ban_chep_doan_truoc_vao_loi_nhac():
    """Gốc rễ của vòng lặp bịa: mô hình lấy chính câu vừa in làm lời nhắc."""
    import inspect
    import io as _io

    s = _io.open("autodub/speech/asr_whisper_worker.py", encoding="utf-8").read()
    assert "condition_on_previous_text=False" in s
