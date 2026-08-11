"""Mini-spec V24 (docs/PLAN.md, Phase F) — phân loại lỗi tạm thời/vĩnh viễn
theo VIDEO trong batch (`autodub/batch_retry.py`)."""
from __future__ import annotations

from autodub.batch_retry import is_transient_error
from autodub.config import ConfigError
from autodub.saas_client import (
    DeviceBlockedError, InsufficientCreditError, MaintenanceError, OfflineError,
)
from autodub.subprocess_watchdog import SubprocessTimeoutError
from autodub.text.translate_local import LocalTranslateError


def test_subprocess_timeout_is_transient():
    assert is_transient_error(SubprocessTimeoutError("treo")) is True


def test_offline_error_is_transient():
    assert is_transient_error(OfflineError("mất mạng")) is True


def test_connection_and_timeout_builtins_are_transient():
    assert is_transient_error(ConnectionError("reset")) is True
    assert is_transient_error(TimeoutError("hết giờ")) is True


def test_insufficient_credit_is_permanent():
    """Hết Vox — thử lại vô ích, chắc chắn lặp lại đúng lỗi."""
    assert is_transient_error(InsufficientCreditError("hết Vox")) is False


def test_device_blocked_and_maintenance_are_permanent():
    assert is_transient_error(DeviceBlockedError("bị khoá")) is False
    assert is_transient_error(MaintenanceError("bảo trì")) is False


def test_config_error_is_permanent():
    """Thiếu API key/cấu hình sai — thử lại nhận đúng lỗi đó lần nữa."""
    assert is_transient_error(ConfigError("thiếu API key")) is False


def test_generic_exception_defaults_to_permanent():
    """Mặc định AN TOÀN khi không nhận diện được — không đoán."""
    assert is_transient_error(RuntimeError("gì đó lạ")) is False
    assert is_transient_error(FileNotFoundError("mất file")) is False
    assert is_transient_error(ValueError("sai định dạng")) is False


def test_wrapped_transient_cause_detected_through_from_e_chaining():
    """Bug thật cần tránh: LocalTranslateError BỌC SubprocessTimeoutError
    khi worker dịch local treo (translate_local.py, dùng `raise ... from e`)
    — phải nhận ra lỗi GỐC tạm thời xuyên qua lớp bọc, không mặc định vĩnh
    viễn chỉ vì lớp ngoài là LocalTranslateError (kiểu chung chung)."""
    try:
        try:
            raise SubprocessTimeoutError("worker treo")
        except SubprocessTimeoutError as e:
            raise LocalTranslateError("worker dịch local không phản hồi") from e
    except LocalTranslateError as wrapped:
        assert is_transient_error(wrapped) is True


def test_local_translate_error_without_transient_cause_stays_permanent():
    """LocalTranslateError vì lý do KHÁC (model hỏng, JSON sai định dạng)
    không có SubprocessTimeoutError trong chuỗi __cause__ -> vẫn vĩnh viễn."""
    assert is_transient_error(LocalTranslateError("model dir không hợp lệ")) is False


def test_implicit_context_chaining_also_detected():
    """`raise X` (không `from e`) bên trong `except:` vẫn tự động gắn
    __context__ — is_transient_error phải xét cả 2 kiểu chaining."""
    try:
        try:
            raise SubprocessTimeoutError("treo")
        except SubprocessTimeoutError:
            raise LocalTranslateError("bọc không dùng from")
    except LocalTranslateError as wrapped:
        assert is_transient_error(wrapped) is True
