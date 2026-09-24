"""Phân loại lỗi tạm thời/vĩnh viễn cho retry theo VIDEO trong batch —
mini-spec V24 (docs/PLAN.md, Phase F).

Phân loại theo EXCEPTION TYPE đã có sẵn trong code (Constraint 1 của mini-
spec), KHÔNG đoán qua nội dung message (dễ vỡ khi đổi ngôn ngữ lỗi, và
message thường bị cắt 200 ký tự trước khi tới đây — xem
``batch.py::_run_items``). Mặc định AN TOÀN: exception không nhận diện
được coi là VĨNH VIỄN (không tự thử lại) — thà bỏ lỡ 1 cơ hội phục hồi hợp
lệ còn hơn lặp vô ích với lỗi chắc chắn lặp lại (Constraint 4).

Dùng lại đúng luật đã có ở :mod:`autodub.saas_retry` (mini-spec V16) cho
lỗi SaaS thay vì phát minh luật thứ 2 — 1 lỗi hết Vox/thiết bị bị khoá vẫn
là lỗi vĩnh viễn dù nhìn từ tầng nào.
"""
from __future__ import annotations

from autodub.saas_client import SaasError
from autodub.saas_retry import is_retryable_error as _is_retryable_saas_error
from autodub.subprocess_watchdog import SubprocessTimeoutError


def _is_transient_single(exc: BaseException) -> bool:
    if isinstance(exc, SubprocessTimeoutError):
        return True
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    if isinstance(exc, SaasError):
        return _is_retryable_saas_error(exc)
    return False


def is_transient_error(exc: BaseException) -> bool:
    """``True`` nếu thử lại CÓ CƠ HỘI thành công (mất mạng, subprocess
    worker treo, SaaS rate-limit/5xx) — ``False`` cho mọi thứ khác, kể cả
    khi không chắc (mặc định an toàn, xem module docstring).

    Lỗi TẠM THỜI thường bị 1 lớp gọi trung gian bọc lại thành 1 exception
    khác (vd :class:`autodub.text.translate_local.LocalTranslateError` bọc
    :class:`~autodub.subprocess_watchdog.SubprocessTimeoutError` khi worker
    dịch local treo — xem ``translate_local.py::run_local_worker``, dùng
    ``raise ... from e`` đúng để giữ chuỗi này). Duyệt qua ``__cause__``/
    ``__context__`` để không bỏ sót lỗi gốc TẠM THỜI đằng sau 1 lớp bọc.
    """
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        if _is_transient_single(current):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False
