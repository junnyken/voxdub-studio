"""Đối tượng Qt này còn sống ở tầng C++ không?

Qt và Python giữ hai vòng đời khác nhau. `deleteLater()` huỷ đối tượng C++,
nhưng biến Python vẫn trỏ vào cái vỏ — gọi bất kỳ phương thức nào lên đó sẽ
ném:

    RuntimeError: libshiboken: Internal C++ object (X) already deleted.

Gặp thật 26/8/2026: người dùng đóng app, `closeEvent` gọi `shutdown()`, hàm
này gọi `isRunning()` lên một worker thumbnail đã `deleteLater` xong từ lâu —
app hiện hộp "Ứng dụng gặp lỗi không mong muốn" ngay lúc thoát.

Cách chữa gốc là **buông tham chiếu khi worker chạy xong**. Hàm dưới đây là
lưới an toàn cho những chỗ không nắm chắc được vòng đời — dùng nó thay cho
`try/except RuntimeError` rải khắp nơi, vì bắt lỗi rồi bỏ qua thì lần sau
không ai biết chỗ nào đang hỏng.
"""
from __future__ import annotations


def con_song(obj) -> bool:
    """True khi ``obj`` không phải None và đối tượng C++ của nó chưa bị huỷ."""
    if obj is None:
        return False
    try:
        from shiboken6 import isValid
    except ImportError:  # môi trường không có PySide6 (CLI, worker máy chủ)
        return True
    return bool(isValid(obj))
