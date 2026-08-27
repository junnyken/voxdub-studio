"""Thuật ngữ cố định người dùng khai phải được KIỂM LẠI, không chỉ nhắc.

Chủ dự án hỏi (27/08/2026): ô «Ngữ cảnh», «Cách xưng hô», «Thuật ngữ cố định»
có thật sự làm bản dịch hiểu đúng không.

Kiểm mã: cả bốn ô ĐỀU được gửi lên máy chủ, và thuật ngữ còn được đánh dấu
**MANDATORY** trong lời nhắc. Nhưng **không ai kiểm lại** xem mô hình có tuân
hay không — người dùng khai xong chỉ biết tin. Mô hình bỏ qua một dòng thuật
ngữ thì không có gì phát hiện.

Phép kiểm ở đây chạy hoàn toàn trên máy (0 Vox); chỉ câu SAI mới được gửi đi
dịch lại, đi chung đường với các lý do sẵn có (cjk, untranslated, …).
"""
from __future__ import annotations

import pytest

from autodub.text.translate_review import (_flag, _sai_thuat_ngu,
                                           doc_thuat_ngu)


def _seg(goc: str, dich: str) -> dict:
    return {"id": 1, "text": goc, "text_vi": dich,
            "start": 0.0, "end": 5.0, "duration": 5.0}


# --- Đọc ô thuật ngữ ----------------------------------------------------

def test_doc_dung_khuon_nguoi_dung_go():
    assert doc_thuat_ngu("显卡 = card đồ họa\n翻车 = toang") == [
        ("显卡", "card đồ họa"), ("翻车", "toang")]


def test_bo_qua_dong_rac():
    """Người dùng gõ tay: dòng trống, dòng quên dấu bằng, dòng thiếu một vế."""
    assert doc_thuat_ngu("显卡 = card đồ họa\n\nkhông có dấu bằng\n= thiếu vế trái\n"
                         "thiếu vế phải =") == [("显卡", "card đồ họa")]


def test_o_trong_thi_khong_co_gi():
    assert doc_thuat_ngu("") == []
    assert doc_thuat_ngu(None) == []


# --- Phép kiểm tuân thủ -------------------------------------------------

def test_dung_dung_thuat_ngu_thi_qua():
    tn = [("显卡", "card đồ họa")]
    assert not _sai_thuat_ngu(_seg("这个显卡很强", "Cái card đồ họa này mạnh lắm."),
                              "text_vi", tn)


def test_dich_khac_thi_bi_co():
    """Đây là toàn bộ lý do tính năng này tồn tại."""
    tn = [("显卡", "card đồ họa")]
    assert _sai_thuat_ngu(_seg("这个显卡很强", "Cái card màn hình này mạnh lắm."),
                          "text_vi", tn)


def test_khong_phan_biet_hoa_thuong():
    """Bản dịch hay viết hoa đầu câu — cờ vì chữ hoa là cờ nhầm."""
    tn = [("翻车", "toang")]
    assert not _sai_thuat_ngu(_seg("翻车了", "Toang rồi."), "text_vi", tn)


def test_cau_khong_chua_tu_goc_thi_khong_lien_quan():
    tn = [("显卡", "card đồ họa")]
    assert not _sai_thuat_ngu(_seg("你好", "Xin chào."), "text_vi", tn)


def test_khong_khai_thuat_ngu_thi_khong_co_gi_doi():
    """Người dùng bỏ trống ô đó — hành vi phải y hệt như trước."""
    assert not _sai_thuat_ngu(_seg("这个显卡很强", "Cái gì cũng được."), "text_vi", [])


# --- Nối vào lượt soát sẵn có -------------------------------------------

def test_flag_tra_ve_ly_do_glossary():
    tn = [("显卡", "card đồ họa")]
    assert _flag(_seg("这个显卡很强", "Cái card màn hình này mạnh."),
                 "text_vi", 15.0, tn) == "glossary"


def test_flag_khong_doi_hanh_vi_cu_khi_khong_co_thuat_ngu():
    """Không truyền thuật ngữ vào thì mọi thứ như trước — tham số có mặc định."""
    assert _flag(_seg("hello world", "hello world"), "text_vi", 15.0) == "untranslated"


def test_ly_do_moi_duoc_may_chu_nhan():
    """Gửi lý do máy chủ không nhận là CẢ LƯỢT soát bị từ chối — đúng lỗi đã
    xảy ra với `untranslated` suốt 12 ngày."""
    import re

    nguon = open("control_server/src/routes/ai.js", encoding="utf-8").read()
    m = re.search(r"reason:\s*\{\s*type:\s*'string',\s*\n?\s*enum:\s*\[([^\]]+)\]",
                  nguon)
    assert m and "glossary" in m.group(1)


def test_luot_soat_that_su_truyen_thuat_ngu_vao():
    """Lỗ hổng bộ canh tự tìm ra: các test trên gọi thẳng `_flag(..., tn)`
    nên vẫn xanh kể cả khi `review_translations` QUÊN truyền thuật ngữ vào.
    Đo bằng đột biến: bỏ tham số ở chỗ quét → 12 test vẫn xanh.

    Chốt này soi đúng chỗ nối, bằng AST chứ không dò chuỗi.
    """
    import ast

    nguon = open("autodub/text/translate_review.py", encoding="utf-8").read()
    for nut in ast.walk(ast.parse(nguon)):
        if isinstance(nut, ast.FunctionDef) and nut.name == "review_translations":
            than = nut
            break
    else:
        raise AssertionError("không còn hàm review_translations")

    goi_flag = [n for n in ast.walk(than)
                if isinstance(n, ast.Call)
                and getattr(n.func, "id", "") == "_flag"]
    assert goi_flag, "lượt soát không hề gọi _flag"
    for g in goi_flag:
        ten = [getattr(a, "id", "") for a in g.args]
        assert "thuat_ngu" in ten, (
            "gọi _flag mà KHÔNG truyền thuật ngữ — ô «Thuật ngữ cố định» của "
            "người dùng lại thành không ai kiểm, đúng như trước khi sửa")

    assert any(isinstance(n, ast.Call)
               and getattr(n.func, "id", "") == "doc_thuat_ngu"
               for n in ast.walk(than)), "không đọc ô thuật ngữ từ cài đặt"


def test_nhat_ky_noi_tieng_viet():
    """Nhật ký từng in ra 'untranslated' trần vì thiếu nhãn."""
    src = open("autodub/text/translate_review.py", encoding="utf-8").read()
    i = src.index("labels = {")
    khoi = src[i:i + 600]
    assert "untranslated" in khoi and "glossary" in khoi
