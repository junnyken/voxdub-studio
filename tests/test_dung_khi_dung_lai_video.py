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


def test_quet_ocr_nay_da_co_nut_dung_VA_da_noi_co_huy():
    """Bộ canh cũ ghi quyết định «hộp thoại chưa có nút Dừng nên chưa cần cờ
    huỷ», kèm câu chỉ rõ khi nào phải xem lại: *"Hộp thoại nay CÓ nút Dừng —
    lúc này mới đáng nối cờ xuống detect_text_regions()"*. C49 làm đúng việc
    đó, nên bộ canh đổi vai: từ nay canh cho HAI thứ đi cùng nhau.

    Có nút mà không nối cờ thì bấm Dừng chẳng làm gì (nút giả) — còn tệ hơn
    không có nút.
    """
    ocr = open(os.path.join(REPO, "autodub", "media", "text_regions.py"),
               encoding="utf-8").read()
    assert "timeout=60" not in ocr, (
        "mốc 60 giây cứng là hạn của MỘT khung hình — quét nhiều khung sẽ hết "
        "giờ oan, mà lời báo lại đổ cho 'worker không chạy được'")
    assert "def _han_gio" in ocr, "phải có hạn giờ tính theo số khung"
    assert "cancel_event" in ocr

    dialog = open(os.path.join(REPO, "autodub_gui", "style_dialog.py"),
                  encoding="utf-8").read()
    assert "btn_ocr_stop" in dialog, "mất nút Dừng thì cờ huỷ thành mã chết"
    assert "def dung" in dialog, "worker phải có đường dừng"
    assert "cancel_event=self._huy" in dialog, (
        "hộp thoại có nút Dừng mà không chuyển cờ xuống lõi — nút giả")
