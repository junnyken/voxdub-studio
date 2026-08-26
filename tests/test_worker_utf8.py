"""Mọi worker in tiếng Việt ra ống PHẢI đặt mã hoá UTF-8.

Lỗi thật, người dùng gặp 26/08/2026 — nhật ký chạy:

    UnicodeEncodeError: 'charmap' codec can't encode character '\\u0110'
    → Dịch ngoại tuyến lỗi (Worker dịch local kết thúc bất thường)

Windows cho tiến trình con dùng bảng mã cp1252 khi ghi ra ống. Worker dịch
in JSON có `ensure_ascii=False`, gặp chữ "Đ" là chết giữa chừng, và tiến
trình cha chỉ thấy "worker kết thúc bất thường" — không ai đoán được nguyên
nhân là bảng mã.

Ba trong bảy worker thiếu dòng này. Ba cái kia có, nên đây không phải quy ước
mới — chỉ là quy ước bị bỏ sót, đúng kiểu lỗi mà test tồn tại để chặn.
"""
from __future__ import annotations

import os
import re

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _worker_in_tieng_viet() -> list[str]:
    """Worker nào in JSON không ép ASCII — tức có thể in chữ có dấu."""
    ra = []
    for thu, _d, tep in os.walk(os.path.join(REPO, "autodub")):
        if "__pycache__" in thu:
            continue
        for f in sorted(tep):
            if not f.endswith("worker.py"):
                continue
            duong = os.path.join(thu, f)
            src = open(duong, encoding="utf-8").read()
            if "ensure_ascii=False" in src:
                ra.append(os.path.relpath(duong, REPO).replace(os.sep, "/"))
    return ra


def test_co_worker_de_kiem():
    assert _worker_in_tieng_viet(), "không tìm thấy worker nào để kiểm"


@pytest.mark.parametrize("ten", _worker_in_tieng_viet())
def test_worker_dat_ma_hoa_utf8(ten):
    src = open(os.path.join(REPO, ten), encoding="utf-8").read()
    assert re.search(r"sys\.stdout\.reconfigure\([^)]*encoding=\"utf-8\"", src), (
        f"{ten} in chữ có dấu ra ống mà không đặt UTF-8 — trên Windows là "
        "UnicodeEncodeError giữa chừng, cha chỉ thấy 'worker kết thúc bất thường'")


@pytest.mark.parametrize("ten", _worker_in_tieng_viet())
def test_dat_ma_hoa_truoc_moi_lenh_in(ten):
    """Phải chạy TRƯỚC mọi lệnh in — nếu không thì lệnh in đầu tiên vẫn chết.

    Chấp nhận hai chỗ, vì dự án đang dùng cả hai và cả hai đều đúng:
    câu lệnh ở cấp module, hoặc dòng đầu của `main()`.

    KHÔNG so vị trí chuỗi: bản đầu của test này so `index("print(")` với vị
    trí dòng reconfigure và báo đỏ oan cho ba worker vốn đúng — `print(` nằm
    trong thân một hàm định nghĩa sớm thì đâu có nghĩa là nó chạy sớm.
    """
    import ast

    cay = ast.parse(open(os.path.join(REPO, ten), encoding="utf-8").read())

    def la_reconfigure(nut) -> bool:
        if not (isinstance(nut, ast.Expr) and isinstance(nut.value, ast.Call)):
            return False
        goi = nut.value.func
        return (isinstance(goi, ast.Attribute) and goi.attr == "reconfigure"
                and isinstance(goi.value, ast.Attribute)
                and goi.value.attr in ("stdout", "stderr"))

    if any(la_reconfigure(n) for n in cay.body):
        return                                      # cấp module — chắc chắn sớm nhất
    for nut in cay.body:
        if isinstance(nut, ast.FunctionDef) and nut.name == "main":
            # Cho phép nằm trong vài câu lệnh đầu, miễn là trước mọi lệnh in.
            for con in nut.body:
                if la_reconfigure(con):
                    return
                if any(isinstance(x, ast.Call)
                       and getattr(x.func, "id", "") == "print"
                       for x in ast.walk(con)):
                    break
    raise AssertionError(
        f"{ten}: mã hoá UTF-8 không được đặt trước mọi lệnh in — lệnh in đầu "
        "tiên vẫn sẽ chết trên Windows")
