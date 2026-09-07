"""V12/C68 (docs/PLAN.md, FEATURES.md §5.1) — "chế độ dựng trên máy chủ chưa
hiện tiến độ". Root cause thật (không phải chỉ thiếu UI): `Narrator.narrate()`
không có template cho step "separate" trong `_STEP_PROGRESS`, nên dòng
"progress" mà `autodub/cloud_render.py` emit trong lúc chờ job **không hề lên
Nhật ký** — người dùng chỉ thấy dòng tĩnh "Đang tách giọng nói khỏi nhạc nền"
(từ status "start") rồi im lặng tới khi xong, có thể tới 30 phút.

Thuần Python (log_text.py không nạp Qt) — không cần QApplication.
"""
from __future__ import annotations

from autodub.progress import ProgressEvent
from autodub_gui.log_text import Narrator


def test_separate_progress_co_dong_len_nhat_ky():
    """Trước C68: không có template -> narrate() trả None, dòng biến mất."""
    n = Narrator()
    result = n.narrate(ProgressEvent(
        step="separate", status="progress", current=12, total=1800))
    assert result is not None, (
        "thiếu template cho step 'separate' -> dòng tiến độ lúc chờ cloud "
        "không hề lên Nhật ký, đúng bug FEATURES.md §5.1")
    text, _level, is_progress = result
    assert "12" in text, "phải nói ra số giây đã chờ thật"
    assert is_progress, "dòng tiến độ phải ghi đè tại chỗ, không phải dòng mới"


def test_separate_progress_khong_hien_ti_le_gia():
    """`_STEP_PROGRESS["separate"]` chỉ dùng {current} (số giây), không được
    bịa ra một con số hoàn thành (vd "{current}/{total}") — server không trả
    % thật cho job Demucs (1 job = 1 lượt, không chia nhỏ được)."""
    n = Narrator()
    text, _level, _is_progress = n.narrate(ProgressEvent(
        step="separate", status="progress", current=5, total=1800))
    assert "1800" not in text, (
        "hiện thẳng con số hạn chờ 30 phút cho người dùng dễ hiểu nhầm là "
        "tổng thời gian job sẽ chạy, trong khi đó chỉ là ngưỡng treo")


def test_separate_start_va_done_khong_doi_hanh_vi():
    """Regression: thêm template 'progress' không được đụng tới status
    start/done/skip/error (bảng khác, xử lý khác trong narrate())."""
    n = Narrator()
    start = n.narrate(ProgressEvent(step="separate", status="start"))
    assert start[0] == "Đang tách giọng nói khỏi nhạc nền"
    n2 = Narrator()
    done = n2.narrate(ProgressEvent(step="separate", status="done"))
    assert done[0] == "Đã tách xong nhạc nền"
