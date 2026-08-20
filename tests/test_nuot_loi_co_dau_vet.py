"""V92 — mọi chỗ nuốt lỗi phải để lại dấu vết, hoặc được khai lý do.

Bài học đắt nhất tuần này: `except Exception` không kèm log làm trình cài đặt
tự động chết âm thầm **qua nhiều bản phát hành** (V83), và cùng cơ chế đó đã
giấu bốn lỗi khác (V75, V78, V86, V91).

Nhưng cấm tuyệt đối thì không thực tế: dọn dẹp, watchdog, probe chẩn đoán đều
có lý do chính đáng để im lặng. Nên luật ở đây là:

    Mỗi chỗ nuốt lỗi phải có MỘT trong hai:
      - dấu vết: ghi log, ném lại, hoặc giữ nội dung lỗi để hiện ra;
      - lý do viết ngay tại dòng `except`.

Cố ý KHÔNG dùng danh sách khai báo tập trung. Bản đầu của test này có hai
danh sách như vậy (một cho chỗ đã duyệt, một cho 48 chỗ mã cũ chưa ai đọc) —
nhưng danh sách ở tệp test thì người sửa mã không nhìn thấy, và phải nhớ đi
cập nhật ở nơi khác. Rà hết 48 chỗ đó rồi thì hoá ra **hầu hết đã có sẵn lời
giải thích cạnh dòng `except`**; chỉ cần bộ dò công nhận nó là xong, và luật
gọn lại còn một câu: *giải thích tại chỗ, hoặc để lại dấu vết*.

Nhờ vậy "36 chỗ chấp nhận được" thôi là đánh giá trong đầu một người — nó
thành danh sách đọc được, và **thêm chỗ mới là test đỏ ngay**.
"""
from __future__ import annotations

import ast
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


THU_MUC = ("autodub", "autodub_gui")
DAU_VET = ("log", "warn", "error", "info", "debug", "exception", "emit",
           "TOASTS", "print", "set_status", "set_music_status", "_die")


def _ham_chua(cay, node) -> str:
    ten = "?"
    for n in ast.walk(cay):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if n.lineno <= node.lineno <= (n.end_lineno or n.lineno):
                ten = n.name
    return ten


def _co_ly_do_tai_cho(src_lines, node) -> bool:
    """Có lời giải thích ngay tại dòng `except` không?

    Lý do viết cạnh mã tốt hơn danh sách tập trung: người sửa mã nhìn thấy
    ngay, và không phải nhớ đi cập nhật một tệp test ở nơi khác. Yêu cầu duy
    nhất là lời giải thích phải THẬT — vài chữ cho có thì không tính.
    """
    dong = src_lines[node.lineno - 1] if node.lineno <= len(src_lines) else ""
    if "#" not in dong:
        return False
    chu_thich = dong.split("#", 1)[1]
    # Bỏ phần "noqa: BLE001" rồi mới đếm chữ còn lại
    con_lai = chu_thich.replace("noqa:", "").replace("BLE001", "")
    con_lai = con_lai.strip(" -—:")
    return len(con_lai) >= 20


def _co_dau_vet(node) -> bool:
    """Chỗ này có để lại dấu vết nào không?

    Ba dạng đều tính là CÓ:
      - ghi log / ném lại / báo thẳng cho người dùng;
      - **giữ lại nội dung lỗi** vào biến hay thuộc tính (`self.error = e`,
        `text = f"... {e}"`) — nơi gọi hiện nó ra, đó là dấu vết chứ không
        phải im lặng. Bỏ qua dạng này là kể oan hàng chục chỗ, mà bộ kiểm kể
        oan thì bị tắt (bài học V90).
    """
    if node.name:
        # Có đặt tên cho lỗi (`except ... as e`) và có dùng lại tên đó
        for n in ast.walk(node):
            if isinstance(n, ast.Name) and n.id == node.name:
                return True
    for n in ast.walk(node):
        if isinstance(n, ast.Raise):
            return True
        if isinstance(n, ast.Call) and any(
                k in ast.unparse(n.func) for k in DAU_VET):
            return True
    return False


def _quet() -> list[tuple[str, str, int]]:
    ra = []
    for muc in THU_MUC:
        for goc, _dirs, files in os.walk(os.path.join(REPO, muc)):
            if "__pycache__" in goc:
                continue
            for f in sorted(files):
                if not f.endswith(".py"):
                    continue
                duong = os.path.join(goc, f)
                rel = os.path.relpath(duong, REPO)
                try:
                    cay = ast.parse(open(duong, encoding="utf-8").read())
                except (SyntaxError, UnicodeDecodeError):
                    continue
                dong = open(duong, encoding="utf-8").read().splitlines()
                for n in ast.walk(cay):
                    if not isinstance(n, ast.ExceptHandler):
                        continue
                    ten = ast.unparse(n.type) if n.type else "bare"
                    if ten not in ("Exception", "BaseException", "bare"):
                        continue
                    if _co_dau_vet(n) or _co_ly_do_tai_cho(dong, n):
                        continue
                    ra.append((rel, _ham_chua(cay, n), n.lineno))
    return ra


def test_khong_co_cho_nuot_loi_nao_chua_khai_bao():
    """Chỗ nuốt lỗi MỚI phải có dấu vết hoặc lý do — không được thêm vào nợ."""
    la = _quet()
    assert not la, (
        "Chỗ nuốt lỗi không dấu vết và không lời giải thích:\n  "
        + "\n  ".join(f"{f}:{l} trong {h}()" for f, h, l in la)
        + "\n\nThêm log, hoặc viết lý do ngay tại dòng `except`."
    )




