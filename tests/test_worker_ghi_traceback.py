"""Worker nền phải GHI TRACEBACK, không chỉ gửi một câu lỗi.

Lỗi thật 11/09/2026: chủ dự án phân tích một video YouTube Shorts, chờ gần
**300 giây**, rồi nhận đúng một dòng:

    Dừng lại: 'NoneType' object has no attribute 'strip'

Cả 22 worker đều làm `self.failed.emit(str(e))` — **vứt mất traceback**.
Không có traceback thì không ai định vị được lỗi: tôi đã chạy lại thật hai
lượt với chính video đó (một lượt bộ đọc cục bộ, một lượt ép bộ đọc máy chủ)
mà **không lượt nào chạm được vào lỗi**. Mất một buổi dò tìm chỉ vì thiếu
một dòng log.

Và câu `'NoneType' object has no attribute 'strip'` nói đúng chuyện gì xảy
ra với máy, đồng thời **không nói gì** với người đang chờ.
"""
from __future__ import annotations

import logging

import pytest

pytest.importorskip("PySide6")

from autodub_gui import workers  # noqa: E402


def test_ghi_loi_ghi_TRACEBACK_vao_nhat_ky(caplog):
    try:
        None.strip()          # noqa: B018 — cố ý tái hiện đúng lỗi đã gặp
    except AttributeError as e:
        with caplog.at_level(logging.ERROR, logger="autodub_gui.workers"):
            workers._ghi_loi(e)

    ghi = "\n".join(r.getMessage() + (r.exc_text or "") for r in caplog.records)
    assert "Traceback" in caplog.text or "AttributeError" in caplog.text, (
        "không ghi traceback thì lượt hỏng sau cũng không định vị được")
    assert "Tác vụ nền hỏng" in ghi


def test_loi_lap_trinh_duoc_NOI_RO_la_loi_phan_mem():
    """Người dùng không đọc được `'NoneType' object has no attribute 'strip'`.

    Phải nói thẳng đây là lỗi phần mềm và chỉ chỗ lấy tệp log — nếu không,
    họ sẽ đi sửa thứ không liên quan (đổi video, cài lại, thử lại 5 lần).
    """
    try:
        None.strip()          # noqa: B018
    except AttributeError as e:
        cau = workers._ghi_loi(e)

    assert "lỗi của phần mềm, không phải do bạn làm sai" in cau
    assert "voxdub.log" in cau, "phải chỉ đúng tệp cần gửi"
    # Vẫn giữ nguyên văn kỹ thuật để người hỗ trợ đối chiếu.
    assert "AttributeError" in cau


def test_loi_CO_CAU_NGUOI_DOC_DUOC_thi_giu_nguyen():
    """Không được bọc mọi lỗi vào một câu chung: `SaasError`, `ThieuAnh`…
    đã có câu nói đúng việc cần làm, thay nó đi là mất thông tin."""
    cau = workers._ghi_loi(RuntimeError(
        "Không đủ Vox. Cần 12, bạn có 3."))
    assert cau == "Không đủ Vox. Cần 12, bạn có 3."


def test_KHONG_con_worker_nao_vut_traceback():
    """Chốt chỗ GỌI, không chỉ chốt thân hàm — lớp sai đã mắc bốn lần."""
    import inspect

    ma = inspect.getsource(workers)
    assert "emit(str(e))" not in ma, (
        "còn worker gửi thẳng `str(e)` — traceback của lượt hỏng đó sẽ mất")
