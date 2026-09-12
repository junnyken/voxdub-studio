"""Retry/backoff dùng chung cho các lượt gọi SaaS một-lần (không phải lô có
sẵn backoff riêng như ``text/translate_saas.py``).

Mini-spec V16 (docs/PLAN.md, Phase E) — audit phát hiện: ``translate_saas.py``
(dịch lô cho luồng lồng tiếng) đã có bounded-retry + backoff + jitter đầy đủ
từ trước, nhưng 2 điểm gọi SaaS MỘT-LẦN khác — poll/tải kết quả cloud-render
(``cloud_render.py``, mini-spec V12) và dịch phụ đề rời qua SaaS
(``text/subtitle_translate.py``, mini-spec V14) — mỗi lượt chỉ gọi 1 lần,
một cú chớp mạng làm hỏng NGUYÊN job/lượt dịch dù job đó không có gì sai.

Nguyên tắc giống hệt ``translate_saas.py`` (KHÔNG phát minh lại): lỗi TẠM
THỜI (mất mạng, timeout, 429, 5xx) gửi lại tối đa 3 lần với giãn cách tăng
dần; lỗi CỐ ĐỊNH (hết Vox, thiết bị bị khóa, bảo trì) không thử lại — thử
lại chỉ tốn thời gian và chắc chắn nhận đúng lỗi đó lần nữa (fail-closed
đúng chỗ). Module này KHÔNG đụng vào ``translate_saas.py`` — logic đó đã
đúng, có test, gắn trực tiếp với luồng tiền (hold) nên không sửa khi không
cần (V2 đã ghi lại lý do tương tự cho việc không ép refactor HOLD/USAGE).
"""
from __future__ import annotations

import random
import threading
import time
from typing import Callable, TypeVar

from autodub.progress import ProgressReporter
from autodub.saas_client import (
    DeviceBlockedError,
    InsufficientCreditError,
    MaintenanceError,
    OfflineError,
    SaasError,
)
from autodub.utils import setup_logging

logger = setup_logging("autodub.saas_retry")

T = TypeVar("T")

#: Số lượt gửi tối đa (1 lần đầu + 3 lần thử lại) — cùng số với translate_saas.py.
MAX_ATTEMPTS = 4
#: Giãn cách giữa các lượt thử lại, giây — cùng bậc với translate_saas.py.
BACKOFF_S = (2.0, 6.0, 15.0)


def is_retryable_error(exc: BaseException) -> bool:
    """Lỗi tạm thời — gửi lại có cơ hội thành công.

    Cùng luật với ``text/translate_saas.py::_is_retryable`` (không trùng
    import trực tiếp để không phải sửa file luồng tiền — xem module
    docstring): hết Vox/thiết bị bị khoá/bảo trì là lỗi cố định, mất mạng
    luôn thử lại, các SaasError khác chỉ thử lại khi bị rate-limit hoặc lỗi
    phía máy chủ (5xx).
    """
    if isinstance(exc, (InsufficientCreditError, DeviceBlockedError,
                        MaintenanceError)):
        return False
    if isinstance(exc, OfflineError):
        return True
    if isinstance(exc, SaasError):
        return exc.code == "RATE_LIMITED" or exc.status >= 500
    return False


def sleep_cancellable(delay_s: float, reporter: ProgressReporter | None,
                      stop: threading.Event | None) -> None:
    """Chờ ``delay_s`` nhưng vẫn nghe lệnh hủy — cắt lát 0.5 giây thay vì
    ``time.sleep(delay_s)`` một lần (người dùng bấm Hủy phải thấy phản hồi
    ngay, không phải đợi hết giãn cách)."""
    deadline = time.monotonic() + delay_s
    while True:
        if reporter is not None:
            reporter.check_cancelled()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        wait_s = min(0.5, remaining)
        if stop is not None and stop.wait(wait_s):
            return
        if stop is None:
            time.sleep(wait_s)


def call_with_retry(
    fn: Callable[[], T], *, label: str,
    reporter: ProgressReporter | None = None,
    max_attempts: int = MAX_ATTEMPTS, backoff: tuple[float, ...] = BACKOFF_S,
) -> T:
    """Gọi ``fn()`` (không tham số — caller tự đóng gói bằng closure/lambda),
    thử lại tối đa ``max_attempts`` lần cho lỗi TẠM THỜI.

    ``fn`` phải an toàn để gọi lại nhiều lần (idempotent) — đúng với cả 3
    điểm dùng module này: poll trạng thái job (đọc, không ghi), tải kết quả
    (mở file ``"wb"`` mỗi lần, tự ghi đè, không nối chồng), dịch phụ đề SaaS
    (job_id ổn định theo nội dung, máy chủ không tính phí 2 lần cho cùng
    job_id — cùng nguyên tắc idempotency đã có trong ``translate_saas.py``).
    """
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        if reporter is not None:
            reporter.check_cancelled()
        try:
            return fn()
        except SaasError as e:
            last_exc = e
            if attempt >= max_attempts or not is_retryable_error(e):
                raise
            base = backoff[min(attempt, len(backoff)) - 1]
            delay = base * random.uniform(0.8, 1.2)
            delay = max(delay, float(getattr(e, "retry_after", 0.0) or 0.0))
            logger.warning(
                f"{label} lỗi tạm thời ({e}) — thử lại lần "
                f"{attempt}/{max_attempts - 1} sau {delay:.0f}s")
            sleep_cancellable(delay, reporter, None)
    # Không tới đây được (vòng lặp luôn return hoặc raise ở lần cuối), nhưng
    # giữ để type-checker/coverage yên tâm không có đường rơi qua im lặng.
    assert last_exc is not None
    raise last_exc
