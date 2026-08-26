"""Một chỗ duy nhất trả lời câu hỏi "máy này có FFmpeg chưa?" (V82).

Người dùng báo (ảnh chụp 2026-08-19, v3.4.5): chép lời hỏng với

    [WinError 2] The system cannot find the file specified
    ERROR: You have requested merging of multiple formats but ffmpeg is not
    installed. Aborting due to --abort-on-error

Cùng một nguyên nhân — máy chưa có FFmpeg — nhưng người dùng không thể đoán ra
từ hai dòng đó, và họ đã loay hoay nhiều lượt. Lỗi hiện ra ở chỗ nào thì phải
nói được ở đó, không bắt người ta suy luận ngược từ mã lỗi của Windows hay của
yt-dlp.

Nên dừng SỚM với lời rõ ràng, thay vì để từng thư viện con tự gãy theo kiểu
riêng của nó.
"""
from __future__ import annotations

import os
import shutil

from autodub.utils import app_root

#: Lời nhắc dùng chung — thống nhất với preflight và log_text để người dùng
#: đọc ở đâu cũng thấy cùng một cách chữa.
THIEU_FFMPEG = (
    "Máy chưa có FFmpeg — đây là công cụ bắt buộc để đọc và cắt video/âm "
    "thanh. Mở lại ứng dụng rồi bấm \"Tải giúp tôi\" ở hộp thoại hiện ra "
    "(ứng dụng tự tải ~80 MB), hoặc chép hai tệp ffmpeg.exe và ffprobe.exe "
    "vào thư mục bin nằm cạnh ứng dụng."
)


def duong_dan_ffmpeg() -> str:
    """Đường dẫn ffmpeg dùng được, hoặc "" nếu máy chưa có.

    Tìm cả PATH hệ thống lẫn thư mục ``bin`` cạnh ứng dụng — bản đóng gói đã
    nối ``bin`` vào PATH lúc khởi động, nhưng CLI và test thì không.
    """
    tim = shutil.which("ffmpeg")
    if tim:
        return tim
    for ten in ("ffmpeg.exe", "ffmpeg"):
        cuc_bo = os.path.join(app_root(), "bin", ten)
        if os.path.isfile(cuc_bo):
            return cuc_bo
    return ""


def duong_dan_ffprobe() -> str:
    """Đường dẫn ffprobe dùng được, hoặc "" nếu máy chưa có.

    Vì sao phải có hàm riêng thay vì đổi chữ trong đường dẫn ffmpeg: cách cũ
    làm `duong_dan_ffmpeg().replace("ffmpeg", "ffprobe")`, mà `str.replace`
    đổi **mọi** chỗ khớp. Đường dẫn rất hay gặp `C:\ffmpeg\bin\ffmpeg.exe`
    thành `C:\ffprobe\bin\ffprobe.exe` — một thư mục không tồn tại.

    Hậu quả nhìn từ người dùng không phải một câu lỗi, mà là **máy đứng**:
    không đọc được độ dài thì tệp dài không được cắt nhỏ, và bộ nghe chạy
    thẳng vào tệp ba tiếng (gặp thật 26/8/2026, thanh tiến trình nằm im ở 24%).

    Đổi ĐÚNG tên tệp, giữ nguyên thư mục.
    """
    tim = shutil.which("ffprobe")
    if tim:
        return tim
    goc = duong_dan_ffmpeg()
    if goc:
        thu_muc, ten = os.path.split(goc)
        ung_vien = os.path.join(thu_muc, ten.replace("ffmpeg", "ffprobe", 1))
        if os.path.isfile(ung_vien):
            return ung_vien
    for ten in ("ffprobe.exe", "ffprobe"):
        cuc_bo = os.path.join(app_root(), "bin", ten)
        if os.path.isfile(cuc_bo):
            return cuc_bo
    return ""


def co_ffmpeg() -> bool:
    return bool(duong_dan_ffmpeg())


def bao_dam_co_ffmpeg(loi=RuntimeError) -> None:
    """Ném lỗi NÓI ĐƯỢC nếu máy chưa có FFmpeg.

    ``loi`` là lớp ngoại lệ của tầng gọi (vd ``TranscribeError``) — để thông
    báo đi đúng đường hiển thị sẵn có của tầng đó thay vì rơi vào nhánh "lỗi
    ngoài dự tính".
    """
    if not co_ffmpeg():
        raise loi(THIEU_FFMPEG)
