"""Đọc mã nguồn Python bằng CÂY CÚ PHÁP, không bằng tìm chuỗi (mini-spec C8).

Vì sao có tệp này: trong một ngày tôi viết bốn phép kiểm "đã nối dây chưa"
bằng cách tìm chuỗi trong mã nguồn, và **cả bốn đều hỏng**:

1. `indexOf(a) < indexOf(b)` vẫn đúng khi `a` không tồn tại → test xanh ngay
   cả khi gỡ sạch thứ cần kiểm.
2. Khớp phải chữ nằm trong lời chú thích chứ không phải mã chạy.
3. Cắt thân hàm quá rộng nên đọc lây sang hàm phía sau → đỏ oan.
4. Tìm tên hàm trần nên khớp luôn dòng `def` của chính nó.

Python có `ast` sẵn trong thư viện chuẩn, nên không có lý do gì để đoán bằng
chuỗi: hỏi thẳng cây cú pháp thì cả bốn kiểu hỏng trên biến mất.
"""
from __future__ import annotations

import ast
import inspect
import textwrap


def cay_ham(ham) -> ast.FunctionDef:
    """Cây cú pháp của MỘT hàm/phương thức — không lây sang hàm khác."""
    nguon = textwrap.dedent(inspect.getsource(ham))
    than = ast.parse(nguon).body[0]
    assert isinstance(than, (ast.FunctionDef, ast.AsyncFunctionDef)), \
        f"{ham} không phải một hàm"
    return than


def _ten_goi(node: ast.Call) -> str:
    """`product_video.kiem_lien_tuc(...)` → "product_video.kiem_lien_tuc"."""
    f = node.func
    phan: list[str] = []
    while isinstance(f, ast.Attribute):
        phan.append(f.attr)
        f = f.value
    if isinstance(f, ast.Name):
        phan.append(f.id)
    return ".".join(reversed(phan))


def cac_luot_goi(ham) -> list[str]:
    """Mọi lượt gọi hàm bên trong, THEO THỨ TỰ TRONG MÃ.

    Chỉ lấy LƯỢT GỌI thật (`ast.Call`) — dòng `def` cùng tên không tính, chữ
    trong chú thích không tính, chuỗi ký tự không tính.

    Sắp theo `(dòng, cột)`, KHÔNG theo thứ tự `ast.walk` trả về: `walk` đi
    theo bề rộng của cây nên một lượt gọi nằm ở dòng cuối có thể được trả về
    trước một lượt gọi ở dòng đầu. Bản đầu của tệp này tin vào thứ tự của
    `walk` và `goi_truoc()` so nhầm — lỗi lộ ra khi kiểm thứ tự trong
    `cli._cmd_dub` (mini-spec C22).
    """
    goi = [n for n in ast.walk(cay_ham(ham)) if isinstance(n, ast.Call)]
    goi.sort(key=lambda n: (n.lineno, n.col_offset))
    return [_ten_goi(n) for n in goi]


def co_goi(ham, ten: str) -> bool:
    """Hàm này có gọi `ten` không (khớp cả đuôi, ví dụ "kiem_lien_tuc")."""
    return any(g == ten or g.endswith("." + ten) for g in cac_luot_goi(ham))


def goi_truoc(ham, a: str, b: str) -> bool:
    """`a` phải được gọi, `b` phải được gọi, và `a` đứng trước `b`.

    Trả `False` nếu THIẾU một trong hai — chứ không âm thầm coi là đúng như
    phép so `indexOf` viết tay.
    """
    goi = cac_luot_goi(ham)
    hop = [i for i, g in enumerate(goi) if g == a or g.endswith("." + a)]
    hop_b = [i for i, g in enumerate(goi) if g == b or g.endswith("." + b)]
    if not hop or not hop_b:
        return False
    return min(hop) < min(hop_b)
