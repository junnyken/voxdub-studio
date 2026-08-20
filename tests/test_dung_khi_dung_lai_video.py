"""V95 — nút Dừng lúc DỰNG LẠI video trong Trình chỉnh sửa.

V76 và V79 nối được cờ Dừng cho luồng lồng tiếng chính, nhưng ghi chú "còn
tồn" của cả hai đều nhắc một chỗ chưa xong: `autodub/editor.py` gọi
`refresh_subtitles()` và `merge_video()` mà không chuyển tiếp cờ.

Hai worker của Trình chỉnh sửa (`RebuildWorker`, `SubtitleWorker`) ĐÃ có nút
Dừng và đã dựng `ProgressReporter` mang theo cờ — chỉ là cờ dừng lại ở đó.
Nghĩa là bấm Dừng lúc đang ghép video thì phải đợi ffmpeg chạy xong, đúng thứ
V79 đã sửa cho luồng chính.
"""
from __future__ import annotations

import ast
import os
import threading

from autodub.progress import ProgressReporter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_reporter_cho_lay_lai_co_dung():
    """Không có đường lấy cờ ra thì nơi gọi phải chọc vào thuộc tính riêng —
    thứ sẽ hỏng lặng lẽ khi lớp đó đổi."""
    ev = threading.Event()
    assert ProgressReporter(None, ev).cancel_event is ev
    assert ProgressReporter(None).cancel_event is None


def _goi_trong_ham(ten_ham: str, ten_goi: str) -> list[ast.Call]:
    src = open(os.path.join(REPO, "autodub", "editor.py"), encoding="utf-8").read()
    cay = ast.parse(src)
    ra = []
    for n in ast.walk(cay):
        if isinstance(n, ast.FunctionDef) and n.name == ten_ham:
            for c in ast.walk(n):
                if (isinstance(c, ast.Call)
                        and getattr(c.func, "id", "") == ten_goi):
                    ra.append(c)
    return ra


def _co_tham_so(call: ast.Call, ten: str) -> bool:
    return any(kw.arg == ten for kw in call.keywords)


def test_dung_lai_video_chuyen_tiep_co_dung():
    for ham in ("rebuild_output", "rebuild_subtitles"):
        for goi in ("refresh_subtitles", "merge_video"):
            calls = _goi_trong_ham(ham, goi)
            assert calls, f"{ham}() không còn gọi {goi}()?"
            for c in calls:
                assert _co_tham_so(c, "cancel_event"), (
                    f"{ham}() gọi {goi}() mà không chuyển tiếp cờ Dừng — bấm "
                    "Dừng sẽ phải đợi bước đó chạy xong")


def test_co_dung_lay_tu_reporter_chu_khong_bia_ra():
    src = open(os.path.join(REPO, "autodub", "editor.py"), encoding="utf-8").read()
    assert "reporter.cancel_event if reporter is not None else None" in src


def test_quet_ocr_khong_co_nut_dung_nen_khong_can_co():
    """Ghi lại một quyết định, để lần sau không ai tưởng đây là việc bỏ sót.

    `detect_text_regions()` dùng `subprocess.run(..., timeout=60)`. Không nối
    cờ Dừng vào đó vì hộp thoại gọi nó (`_OcrWorker`) KHÔNG có nút Dừng —
    thêm tham số chỉ tạo ra mã chết. Chặn cứng 60 giây là giới hạn thật.
    """
    ocr = open(os.path.join(REPO, "autodub", "media", "text_regions.py"),
               encoding="utf-8").read()
    assert "timeout=60" in ocr, "mất trần thời gian thì mới là vấn đề thật"

    dialog = open(os.path.join(REPO, "autodub_gui", "style_dialog.py"),
                  encoding="utf-8").read()
    i = dialog.find("class _OcrWorker")
    assert i > 0
    khuc = dialog[i:i + 1200]
    assert "def cancel" not in khuc, (
        "Hộp thoại nay CÓ nút Dừng — lúc này mới đáng nối cờ xuống "
        "detect_text_regions()")
