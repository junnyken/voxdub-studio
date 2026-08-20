"""V91 — chặn lớp lỗi "gọi tới thứ không tồn tại", bằng máy.

Lớp lỗi này đã cắn nhiều lần trong tuần và mỗi lần đều tốn cả buổi truy:

- V80: `asr_whisper_worker.py` được gọi qua `bundled_file()` nhưng không nằm
  trong gói.
- V83: `icons.brand_logo` được gọi ở BA nơi nhưng không tồn tại — trình cài
  đặt tự động vì thế chưa từng chạy được, và lỗi bị `except Exception` nuốt.
- V84: `VOICES_RELEASE_URL` trỏ vào một kho GitHub không tồn tại.
- V91 (chính lúc viết test này): thân hàm `brand_logo` MẤT DÒNG `def`, nằm
  lại như mã chết sau `return` của `eye_off()`.

Điểm chung: Python không kêu gì cho tới đúng lúc dòng đó chạy — mà những dòng
đó nằm ở nhánh ít đi qua nhất. `pyflakes` thấy ngay trong một giây.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Chỉ chặn những loại chắc chắn là lỗi thật, không bắt bẻ phong cách. Thêm
#: loại mới vào đây thì phải dọn sạch repo trước, nếu không test đỏ triền miên
#: rồi bị bỏ qua — bộ kiểm hay kêu nhầm thì người ta tắt đi (bài học V90).
CHET_NGUOI = (
    "undefined name",
    "local variable defined in enclosing scope referenced before assignment",
    "f-string is missing placeholders",
)

THU_MUC = ("autodub", "autodub_gui", "scripts", "tests")


def _chay_pyflakes() -> list[str]:
    pytest.importorskip("pyflakes")
    ra = subprocess.run(
        [sys.executable, "-m", "pyflakes", *THU_MUC],
        cwd=REPO, capture_output=True, text=True)
    return [d for d in (ra.stdout + ra.stderr).splitlines()
            if any(k in d for k in CHET_NGUOI)]


def test_khong_goi_ten_nao_khong_ton_tai():
    loi = _chay_pyflakes()
    assert not loi, (
        "Có tên được dùng nhưng không tồn tại — Python chỉ kêu lúc dòng đó "
        "chạy, mà đó thường là nhánh ít đi qua nhất:\n  " + "\n  ".join(loi))


def test_khong_con_ham_mat_dong_def():
    """Ca V91: thân hàm nằm lại sau `return` của hàm khác thì thành mã chết.

    Dấu hiệu chung là docstring xuất hiện ngay sau một câu lệnh `return` —
    Python không coi đó là docstring nữa, chỉ là một chuỗi vô nghĩa.
    """
    import ast

    mat = []
    for goc, _dirs, files in os.walk(REPO):
        if any(x in goc for x in (".git", "node_modules", ".venv", "__pycache__",
                                  "dist", "build")):
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            duong = os.path.join(goc, f)
            try:
                cay = ast.parse(open(duong, encoding="utf-8").read())
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(cay):
                than = getattr(node, "body", None)
                if not isinstance(than, list):
                    continue
                for truoc, sau in zip(than, than[1:]):
                    la_chuoi = (isinstance(sau, ast.Expr)
                                and isinstance(sau.value, ast.Constant)
                                and isinstance(sau.value.value, str))
                    if isinstance(truoc, ast.Return) and la_chuoi:
                        mat.append(f"{os.path.relpath(duong, REPO)}:{sau.lineno}")
    assert not mat, ("Chuỗi kiểu docstring nằm ngay sau `return` — gần như "
                     f"chắc chắn là hàm bị mất dòng `def`: {mat}")
