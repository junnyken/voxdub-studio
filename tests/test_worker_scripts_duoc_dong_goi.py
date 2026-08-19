"""V80 — mọi tệp worker app cần lúc chạy phải có trong bản đóng gói.

Lỗi thật, người dùng báo bằng ảnh chụp màn hình (2026-08-19, bản v3.4.4):

    !! không thấy worker script: ...\\autodub\\speech\\asr_whisper_worker.py
    (rồi bộ cài dừng lại và báo thất bại)

`asr_whisper_worker.py` **chưa bao giờ** nằm trong `datas` của `autodub.spec`.
Hậu quả trên MỌI bản đóng gói từ trước tới nay: `scripts/setup_whisper.py`
luôn chết ở bước smoke test → `installed_ok.json` không bao giờ được ghi →
app mãi báo "chưa cài bộ nghe", và ngay cả khi có marker thì
`_transcribe_whisper_subprocess` cũng không tìm ra tệp để chạy.

Đây là gốc rễ sâu hơn cả V74/V75: hai mini-spec đó sửa đúng phần "app kiểm
sai", nhưng đường chép lời trong bản `.exe` vốn dĩ CHƯA BAO GIỜ chạy được.

Test này không kiểm riêng một tệp — nó bắt CẢ LỚP lỗi: quét mã tìm mọi lời
gọi `bundled_file(...)` trỏ tới tệp `.py`, rồi đối chiếu với `datas`.
"""
from __future__ import annotations

import ast
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _bundled_py_files() -> set[str]:
    """Mọi tệp .py mà mã nguồn lấy qua bundled_file() — tức là cần trong gói."""
    can: set[str] = set()
    for goc, _dirs, files in os.walk(REPO):
        if any(x in goc for x in (".venv", "node_modules", ".git", "dist",
                                  "build", "tests")):
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            path = os.path.join(goc, f)
            try:
                tree = ast.parse(open(path, encoding="utf-8").read())
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "bundled_file"):
                    continue
                parts = [a.value for a in node.args
                         if isinstance(a, ast.Constant)
                         and isinstance(a.value, str)]
                if parts and parts[-1].endswith(".py"):
                    can.add("/".join(parts))
    return can


def test_moi_worker_script_deu_nam_trong_spec():
    spec = open(os.path.join(REPO, "autodub.spec"), encoding="utf-8").read()
    m = re.search(r"^datas = \[(.*?)^\]", spec, re.S | re.M)
    assert m, "không đọc được khối datas trong autodub.spec"
    datas = m.group(1)

    thieu = [c for c in sorted(_bundled_py_files())
             if os.path.basename(c) not in datas]
    assert not thieu, (
        "Tệp app gọi qua bundled_file() nhưng KHÔNG được đóng gói — bản .exe "
        f"sẽ báo 'không thấy worker script': {thieu}")


def test_setup_whisper_tim_dung_cho_worker_trong_ban_dong_goi(tmp_path):
    """`setup_whisper.py` dò thêm `_internal/` vì bản onedir để tệp ở đó.
    Giữ lại phép kiểm này để ai đó đừng rút gọn mất nhánh dò."""
    src = open(os.path.join(REPO, "scripts", "setup_whisper.py"),
               encoding="utf-8").read()
    assert "_internal" in src
    assert "asr_whisper_worker.py" in src


def test_it_nhat_phai_thay_worker_whisper():
    """Chốt riêng tệp đã gây ra sự cố — để dù ai đổi cách quét ở trên,
    trường hợp thật này vẫn không lọt lại."""
    spec = open(os.path.join(REPO, "autodub.spec"), encoding="utf-8").read()
    assert "asr_whisper_worker.py" in spec
    assert "align_whisper_worker.py" in spec
