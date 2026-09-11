"""Mọi lượt gọi tiến trình con phải khai `encoding="utf-8"`.

Lỗi thật 11/09/2026 trên máy Windows của chủ dự án. Phân tích một video
YouTube Shorts, chờ hơn **3 phút**, rồi nhận:

    Dừng lại: 'NoneType' object has no attribute 'strip'

Log chỉ đúng nguyên nhân:

    UnicodeDecodeError: 'charmap' codec can't decode byte 0x8f
      File "encodings\\cp1252.py", line 23, in decode
      File "subprocess.py", line 1599, in _readerthread

**Chuỗi nhân quả đầy đủ:**

1. Worker OCR in chữ **tiếng Việt** (UTF-8) ra stdout.
2. Tiến trình cha đọc bằng `text=True` **không kèm `encoding=`**. Trên
   Windows, Python khi đó dùng **bảng mã vùng** (cp1252/cp1258), không phải
   UTF-8 ⇒ `UnicodeDecodeError` **trong luồng đọc của subprocess**.
3. Luồng đọc chết ⇒ `communicate()` trả `None` cho stdout.
4. `proc.stdout.strip()` ⇒ `'NoneType' object has no attribute 'strip'`.

**Vì sao không test nào bắt được, và tôi không tái hiện được**: Linux mặc
định UTF-8. Tôi đã chạy lại thật hai lượt với chính video đó — cả hai đều
xong bình thường. Đây là lớp lỗi **chỉ tồn tại ở môi trường phát hành**.

Nó KHÔNG chỉ ảnh hưởng OCR: ffmpeg in lại **đường dẫn tệp** trong thông báo
lỗi, nên một tệp tên `Tệp của tôi.mp4` cũng đủ làm hỏng theo đúng cách này.
"""
from __future__ import annotations

import pathlib
import re

import pytest

GOC = pathlib.Path(__file__).resolve().parent.parent
THU_MUC = ("autodub", "autodub_gui", "scripts")


def _khoi_doi_so(s: str, dau: int) -> str:
    """Cắt đúng khối đối số của một lượt gọi, cân bằng ngoặc."""
    d, j = 0, s.index("(", dau)
    for k in range(j, len(s)):
        if s[k] == "(":
            d += 1
        elif s[k] == ")":
            d -= 1
            if d == 0:
                return s[j:k + 1]
    return s[j:]


def _cho_thieu_encoding() -> list[str]:
    xau = []
    for thu_muc in THU_MUC:
        for p in sorted((GOC / thu_muc).rglob("*.py")):
            s = p.read_text(encoding="utf-8")
            for m in re.finditer(r"subprocess\.(run|Popen)\(", s):
                khoi = _khoi_doi_so(s, m.start())
                co_text = ("text=True" in khoi
                           or "universal_newlines=True" in khoi)
                if co_text and "encoding=" not in khoi:
                    dong = s[:m.start()].count("\n") + 1
                    xau.append(f"{p.relative_to(GOC)}:{dong}")
    return xau


def test_moi_luot_goi_tien_trinh_con_deu_khai_encoding():
    xau = _cho_thieu_encoding()
    assert not xau, (
        f"{len(xau)} chỗ dùng `text=True` mà không khai `encoding`:\n  "
        + "\n  ".join(xau)
        + "\n\nTrên Windows, Python sẽ giải mã bằng bảng mã VÙNG (cp1252), "
          "và một ký tự tiếng Việt là đủ làm luồng đọc chết — stdout thành "
          "None, rồi lỗi hiện ra là 'NoneType' object has no attribute "
          "'strip'. Thêm `encoding=\"utf-8\", errors=\"replace\"`.")


def test_phep_quet_KHONG_xanh_suong():
    """Chốt tiền đề: phép quét phải thật sự tìm thấy các lượt gọi.

    Regex hỏng thì danh sách rỗng và test trên xanh suông — một test luôn đạt
    vì không kiểm gì cả còn tệ hơn không có test.
    """
    tong = 0
    for thu_muc in THU_MUC:
        for p in (GOC / thu_muc).rglob("*.py"):
            tong += len(re.findall(r"subprocess\.(?:run|Popen)\(",
                                   p.read_text(encoding="utf-8")))
    assert tong > 50, f"chỉ thấy {tong} lượt gọi — phép quét hỏng"


def test_errors_replace_de_byte_hong_khong_giet_ca_luot():
    """`encoding="utf-8"` chưa đủ: công cụ vẫn có thể phun byte không hợp lệ.

    `errors="replace"` biến chúng thành ký tự thay thế thay vì ném lại đúng
    lớp lỗi vừa sửa.
    """
    thieu = []
    for thu_muc in THU_MUC:
        for p in sorted((GOC / thu_muc).rglob("*.py")):
            s = p.read_text(encoding="utf-8")
            for m in re.finditer(r"subprocess\.(run|Popen)\(", s):
                khoi = _khoi_doi_so(s, m.start())
                if 'encoding="utf-8"' in khoi and "errors=" not in khoi:
                    thieu.append(f"{p.relative_to(GOC)}:"
                                 f"{s[:m.start()].count(chr(10)) + 1}")
    assert not thieu, "khai encoding nhưng thiếu errors=\"replace\": " + str(thieu)


# --------------------------------------------------- triệu chứng ----------

def test_worker_OCR_khong_tra_gi_thi_bao_ro_khong_nem_AttributeError(monkeypatch):
    """Phòng lớp hai: luồng đọc còn có thể chết vì lý do khác.

    Trước bản vá, `proc.stdout` là None ⇒ `.strip()` ⇒ AttributeError, và câu
    đó đi thẳng lên màn hình sau ba phút chờ.
    """
    import subprocess

    from autodub.media import text_regions as tr

    class _ProcGia:
        returncode = 0
        stdout = None       # đúng thứ xảy ra khi luồng đọc chết
        stderr = None

    class _CaiDatGia:
        def ocr_configured(self):
            return True

        def ocr_venv_python_path(self):
            return "python3"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _ProcGia())
    monkeypatch.setattr("autodub.utils.bundled_file", lambda *a, **k: __file__)

    # Không được ném AttributeError; phải trả None để rơi về đường in-process.
    try:
        ra = tr._detect_via_subprocess(["/tmp/a.png"], _CaiDatGia())
    except AttributeError as e:  # pragma: no cover - chính là lỗi cần chặn
        pytest.fail(f"vẫn ném AttributeError: {e}")
    assert ra is None
