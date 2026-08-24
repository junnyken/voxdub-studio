"""C24 — Chép lời ghi kết quả DẦN, không đợi xong hết.

Người dùng có một tệp âm thanh **3 giờ 43 phút**. Trước bản này, kết quả chỉ
được ghi ra đĩa sau khi nghe xong toàn bộ: hỏng ở phút thứ 200 là mất sạch, và
trong lúc chạy không có gì trong tay để biết nó đã nghe tới đâu.
"""
from __future__ import annotations

import os

import pytest

from autodub import transcribe_tool as tt


def _seg(i, start, text):
    return {"id": i, "start": start, "end": start + 3, "text": text}


def test_moi_cau_ghi_ngay_ra_dia(tmp_path):
    """Đệm nằm trong bộ nhớ thì mất khi tiến trình bị giết — mà đó đúng là ca
    tệp này sinh ra để cứu."""
    duong = str(tmp_path / "a.dang_chay.txt")
    g = tt._GhiDan(duong)
    g.them(_seg(1, 0, "câu một"))
    # Chưa đóng tệp mà đã phải đọc được.
    assert "câu một" in open(duong, encoding="utf-8").read()
    g.them(_seg(2, 5, "câu hai"))
    assert "câu hai" in open(duong, encoding="utf-8").read()
    g.dong()


def test_ghi_NOI_DUOI_khong_ghi_lai_ca_tep(tmp_path):
    """Ghi lại cả tệp mỗi câu là công việc bình phương theo số câu."""
    import inspect

    than = inspect.getsource(tt._GhiDan)
    assert '"w", encoding' in than, "phải mở tệp đúng MỘT lần"
    assert than.count("open(") == 1, "đang mở lại tệp cho mỗi câu"


def test_moc_thoi_gian_doc_duoc(tmp_path):
    duong = str(tmp_path / "a.txt")
    g = tt._GhiDan(duong)
    g.them(_seg(1, 3725, "sau một tiếng"))
    g.dong()
    assert "[01:02:05]" in open(duong, encoding="utf-8").read()


def test_moc_ngan_thi_khong_hien_gio_thua(tmp_path):
    duong = str(tmp_path / "a.txt")
    g = tt._GhiDan(duong)
    g.them(_seg(1, 65, "một phút năm"))
    g.dong()
    assert "[01:05]" in open(duong, encoding="utf-8").read()


def test_chua_nghe_duoc_cau_nao_thi_khong_tao_tep_rac(tmp_path):
    duong = str(tmp_path / "a.txt")
    tt._GhiDan(duong).dong()
    assert not os.path.exists(duong), "tạo tệp rỗng làm rối thư mục kết quả"


def test_xuat_xong_thi_xoa_tep_do(tmp_path):
    duong = str(tmp_path / "a.txt")
    g = tt._GhiDan(duong)
    g.them(_seg(1, 0, "x"))
    g.xoa()
    assert not os.path.exists(duong), "để lại hai bản của cùng một nội dung"


def test_xoa_tep_khong_ton_tai_thi_khong_no(tmp_path):
    tt._GhiDan(str(tmp_path / "khong-co.txt")).xoa()


def test_ghi_hong_KHONG_lam_hong_luot_chep_loi():
    """Ghi tạm là tiện ích; nó hỏng thì cùng lắm mất tiện ích đó."""
    import inspect

    from autodub.speech import transcriber

    than = inspect.getsource(transcriber._transcribe_whisper_subprocess)
    i = than.index("on_segment(seg)")
    assert "try:" in than[max(0, i - 200):i]
    assert "except Exception" in than[i:i + 200]


def test_hong_giua_chung_thi_GIU_tep_do(tmp_path, monkeypatch):
    """Xoá phần đã nghe được là lấy đi thứ duy nhất còn cứu được."""
    import inspect

    than = inspect.getsource(tt).split("def transcribe_one")[1] \
        if "def transcribe_one" in inspect.getsource(tt) else inspect.getsource(tt)
    i = than.index("except BaseException")
    doan = than[i:i + 600]
    assert "ghi_dan.dong()" in doan
    assert "raise" in doan
    assert "xoa()" not in doan, "hỏng giữa chừng mà lại xoá phần đã nghe được"


def test_duong_ong_ASR_truyen_hook_xuong_worker():
    from tests.doc_ma import cac_luot_goi

    from autodub.speech.transcriber import transcribe

    assert "on_segment" in inspect_source(transcribe), \
        "transcribe() không nhận hook từng câu"


def inspect_source(f):
    import inspect
    return inspect.getsource(f)
