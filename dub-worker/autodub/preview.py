"""Cắt đoạn đầu video để nghe thử trước khi chạy cả bài (mini-spec V56).

Vì sao tồn tại: quy trình cũ là chạy hết video 20 phút rồi mới phát hiện giọng
không hợp hoặc xưng hô sai, và phải làm lại từ đầu. Đây là vòng lặp lãng phí
lớn nhất của người dùng.

Thiết kế cố tình NHỎ: chỉ cắt ra một clip rồi giao cho ĐÚNG pipeline cũ chạy.
Không có "pipeline preview" riêng — một nhánh xử lý song song sẽ tự trôi khác
nhánh chính và tới lúc nào đó bản nghe thử không còn phản ánh bản thật nữa,
tức là mất luôn mục đích của tính năng.
"""
from __future__ import annotations

import os
import subprocess

from autodub.utils import setup_logging

logger = setup_logging("autodub.preview")

#: Hậu tố gắn vào TÊN thư mục dự án. Nằm trong tên chứ không phải một file
#: đánh dấu bên trong: mở thư mục kết quả là thấy ngay cái nào chỉ là bản thử,
#: khỏi phải đoán theo thời gian tạo. Đăng nhầm bản 30 giây lên kênh là hỏng
#: thật, nên chỗ này phải nhìn là biết.
def folder_suffix(seconds: int) -> str:
    return f"-preview{int(seconds)}s"


def apply_folder_suffix(base_name: str, preview_seconds: int) -> str:
    """Gắn hậu tố preview vào tên thư mục dự án, nếu là lượt nghe thử.

    Tách khỏi `pipeline.py` để test thẳng được quy tắc đặt tên — chạy cả
    pipeline chỉ để kiểm một cái tên thư mục là quá đắt, mà đây lại đúng chỗ
    quyết định bản thử có bị nhầm thành bản cuối hay không.
    """
    if preview_seconds and preview_seconds > 0:
        return base_name + folder_suffix(preview_seconds)
    return base_name


def is_preview_dir(path: str) -> bool:
    return "-preview" in os.path.basename(os.path.normpath(path))


def make_preview_clip(source_path: str, work_dir: str, seconds: int) -> str:
    """Cắt ``seconds`` giây đầu của ``source_path`` vào ``work_dir``.

    Dùng ``-c copy`` (không mã hoá lại) nên gần như tức thì kể cả video vài
    GB. Đánh đổi: ``-c copy`` cắt theo keyframe nên độ dài có thể lệch vài
    phần mười giây — chấp nhận được cho bản nghe thử, và đổi lại người dùng
    không phải chờ mã hoá lại chỉ để nghe 30 giây.

    Video ngắn hơn ``seconds`` KHÔNG phải lỗi: ffmpeg trả về đúng cả video.
    """
    if seconds <= 0:
        raise ValueError("preview_seconds phải lớn hơn 0")

    dest = os.path.join(work_dir, f"preview_{int(seconds)}s.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", source_path,
        "-t", str(int(seconds)),
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        dest,
    ]
    logger.info("Cắt %ss đầu để nghe thử: %s", seconds, os.path.basename(source_path))
    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0 or not os.path.isfile(dest) or os.path.getsize(dest) == 0:
        # KHÔNG âm thầm rơi về chạy cả video: người dùng bấm "nghe thử" chính
        # là để tránh chạy cả video. Tự ý chạy full sẽ tốn của họ đúng thứ họ
        # đang cố tiết kiệm (thời gian và Vox).
        tail = (proc.stderr or "")[-400:]
        raise RuntimeError(
            f"Không cắt được đoạn nghe thử ({seconds}s) từ video này. "
            f"Chi tiết ffmpeg: {tail}")

    logger.info("Đoạn nghe thử: %s (%d byte)", dest, os.path.getsize(dest))
    return dest
