"""Hai mini-spec khác nhau không được mang cùng một số.

Chuyện thật, 26/8/2026: hai commit ngày 25/8 mang nhãn `V91`/`V92`, trùng hai
mini-spec đã có từ 20/8. Không hỏng gì lúc chạy — nhưng sổ là thứ để tra lại,
mà tra `V92` ra hai việc khác hẳn nhau thì sổ mất tác dụng đúng lúc cần nhất.
Đã đánh số lại thành `V96`/`V97`.

Chốt này chỉ xét **tiêu đề dạng chuẩn** `## <số> — <tên>`. Các mục ghi tiếp
của cùng một mini-spec (`## V89 giai đoạn 2`, `## V89 lên production`) cố ý
không theo dạng đó nên không bị tính là trùng — đó là ghi tiếp, không phải
đánh số nhầm.
"""
from __future__ import annotations

import collections
import os
import re

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SO = os.path.join(GOC, "docs", "TEST_LOG.md")

#: Trùng CÓ LÝ DO, đã soi tay. Thêm vào đây phải kèm lý do đọc được — danh
#: sách miễn trừ không có lý do thì chỉ là cách tắt chốt cho êm chuyện.
TRUNG_DUOC_PHEP = {
    "V48": "cùng một việc (sao lưu MongoDB) verify lại hôm sau, không phải "
           "hai mini-spec khác nhau",
}


def _tieu_de_chuan() -> list[tuple[str, str]]:
    ra = []
    with open(SO, encoding="utf-8") as f:
        for dong in f:
            m = re.match(r"## ([VC]\d+) — (.+)", dong)
            if m:
                ra.append((m.group(1), m.group(2).strip()))
    return ra


def test_doc_duoc_so():
    assert len(_tieu_de_chuan()) > 100, "đọc hụt tiêu đề — biểu thức khớp sai?"


def test_khong_co_so_nao_bi_dung_hai_lan():
    dem = collections.Counter(so for so, _ten in _tieu_de_chuan())
    trung = {so: n for so, n in dem.items()
             if n > 1 and so not in TRUNG_DUOC_PHEP}
    assert not trung, (
        "hai mini-spec khác nhau mang cùng số: "
        + ", ".join(f"{so} ({n} mục)" for so, n in sorted(trung.items()))
        + " — đổi số mục ra sau, và ghi chú lại vì commit cũ vẫn mang nhãn cũ")


def test_hai_so_da_sua_khong_quay_lai():
    """Ca cụ thể đã sửa — giữ để không ai vô tình đặt lại."""
    dem = collections.Counter(so for so, _ten in _tieu_de_chuan())
    assert dem["V91"] == 1, "V91 lại có hai mục"
    assert dem["V92"] == 1, "V92 lại có hai mục"
    assert dem["V96"] == 1 and dem["V97"] == 1, "thiếu mục đã đánh số lại"


def test_moi_muc_mien_tru_deu_co_ly_do():
    for so, ly_do in TRUNG_DUOC_PHEP.items():
        assert len(ly_do) > 20, f"{so} miễn trừ mà không nói lý do"
