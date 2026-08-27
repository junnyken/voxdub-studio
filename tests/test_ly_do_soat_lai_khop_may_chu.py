"""Lý do soát lại mà app gửi phải nằm trong danh sách máy chủ nhận.

Lỗi thật, lộ ra trong nhật ký người dùng 26/08/2026:

    Soát lại bản dịch: 1 câu cần sửa (1 câu untranslated) — đang nhờ AI dịch lại
    Soát lại bản dịch lỗi (body/items/0/reason must be equal to one of the
    allowed values) — giữ bản lượt đầu

App thêm lý do `"untranslated"` ngày 15/08/2026 để vá đúng chuyện "đôi khi
dịch thiếu hội thoại" (lưới `cjk` cũ chỉ bắt được khi nguồn là tiếng Trung).
Nhưng KHÔNG ai thêm giá trị đó vào lược đồ của máy chủ. Hậu quả: hễ có câu
chưa dịch là CẢ LƯỢT soát lại bị từ chối, app giữ nguyên bản đầu — đúng lỗi
bản vá đó định sửa, và hỏng suốt 12 ngày mà không ai biết.

Hai phía nằm ở hai ngôn ngữ, hai kho triển khai khác nhau; không có gì buộc
chúng khớp ngoài trí nhớ con người. Test này là thứ buộc.
"""
from __future__ import annotations

import ast
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ly_do_app_gui() -> set[str]:
    """Mọi chuỗi mà `_flag()` có thể trả về — đó chính là `reason` gửi đi."""
    nguon = open(os.path.join(REPO, "autodub", "text", "translate_review.py"),
                 encoding="utf-8").read()
    for nut in ast.walk(ast.parse(nguon)):
        if isinstance(nut, ast.FunctionDef) and nut.name == "_flag":
            ra = set()
            for con in ast.walk(nut):
                if isinstance(con, ast.Return) and isinstance(con.value, ast.Constant):
                    if isinstance(con.value.value, str):
                        ra.add(con.value.value)
            return ra
    raise AssertionError("translate_review.py không còn hàm _flag")


def _ly_do_may_chu_nhan() -> set[str]:
    nguon = open(os.path.join(REPO, "control_server", "src", "routes", "ai.js"),
                 encoding="utf-8").read()
    m = re.search(r"reason:\s*\{\s*type:\s*'string',\s*\n?\s*enum:\s*\[([^\]]+)\]",
                  nguon)
    assert m, "không tìm thấy lược đồ `reason` trong ai.js"
    return set(re.findall(r"'([a-z_]+)'", m.group(1)))


def test_moi_ly_do_app_gui_deu_duoc_may_chu_nhan():
    app = _ly_do_app_gui()
    may_chu = _ly_do_may_chu_nhan()
    thua = app - may_chu
    assert not thua, (
        f"app gửi lý do {sorted(thua)} mà máy chủ không nhận — CẢ LƯỢT soát "
        "lại sẽ bị từ chối và người dùng mất bản dịch đã sửa")


def test_app_that_su_gui_untranslated():
    """Chốt riêng cho ca đã xảy ra: giá trị này phải còn ở cả hai phía."""
    assert "untranslated" in _ly_do_app_gui(), (
        "mất lưới bắt câu còn nguyên văn bản gốc — lỗi 15/08 quay lại")
    assert "untranslated" in _ly_do_may_chu_nhan()


def test_may_chu_khong_liet_ke_ly_do_ma_app_khong_bao_gio_gui():
    """Không phải lỗi chạy, nhưng lược đồ nhận thứ không ai gửi là dấu hiệu
    hai phía đã lệch — chỗ nào đó sẽ lệch tiếp."""
    thua = _ly_do_may_chu_nhan() - _ly_do_app_gui()
    assert not thua, f"máy chủ nhận {sorted(thua)} nhưng app không hề gửi"
