"""Máy này có đủ thứ để chạy bộ test không — hỏi TRƯỚC, không để lòi ra sau.

Vì sao có tệp này: khi workspace mất gói hệ thống, `pytest` không nói "máy
thiếu thư viện". Nó nôn ra **24 lỗi import** của 24 tệp khác nhau, hoặc **21
test đỏ** rải rác ở những tệp chẳng liên quan gì nhau. Người đọc kết quả sẽ
đi tìm lỗi trong mã — đúng chỗ không có lỗi nào.

Nên chỗ này hỏi hai câu rẻ tiền trước khi thu thập test, và nếu thiếu thì nói
đúng một câu kèm đúng câu lệnh cần gõ.
"""
from __future__ import annotations

import os
import shutil

#: Đặt biến này để bỏ qua (vd cố ý chạy một nhóm test không cần Qt/ffmpeg).
BIEN_BO_QUA = "VOXDUB_BO_QUA_KIEM_MOI_TRUONG"

SCRIPT_SUA = "scripts/cai_moi_truong_test.sh"


def thieu_qt() -> str:
    """Chuỗi rỗng nghĩa là ổn; ngược lại là tên thư viện còn thiếu."""
    try:
        import PySide6.QtWidgets  # noqa: F401
    except ImportError as e:
        # Thông báo của trình nạp động đã nói đúng tên tệp .so còn thiếu —
        # chép lại nguyên văn thay vì đoán hộ.
        return str(e)
    return ""


def thieu_ffmpeg() -> str:
    return "" if shutil.which("ffmpeg") else "không tìm thấy lệnh «ffmpeg» trong PATH"


def thieu_gi() -> list[str]:
    return [m for m in (thieu_qt(), thieu_ffmpeg()) if m]


def loi_nhan(thieu: list[str]) -> str:
    """Một câu nói rõ chuyện gì, kèm đúng câu lệnh chữa."""
    return (
        "Máy này thiếu thư viện hệ thống để chạy bộ test:\n"
        + "".join(f"  - {m}\n" for m in thieu)
        + f"\nChữa: bash {SCRIPT_SUA}\n"
        f"(Cố ý chạy nhóm test không cần chúng thì đặt {BIEN_BO_QUA}=1.)"
    )


def kiem_hoac_dung() -> str:
    """Trả về câu lỗi nếu phải dừng, chuỗi rỗng nếu chạy tiếp được."""
    if os.environ.get(BIEN_BO_QUA):
        return ""
    thieu = thieu_gi()
    return loi_nhan(thieu) if thieu else ""
