"""Mini-spec V16 (docs/PLAN.md, Phase E) — autodub.saas_retry: retry/backoff
dùng chung cho các lượt gọi SaaS MỘT-LẦN (khác translate_saas.py, đã có
backoff riêng cho luồng lô)."""
from __future__ import annotations

import pytest

from autodub import saas_retry
from autodub.saas_client import (
    DeviceBlockedError,
    InsufficientCreditError,
    MaintenanceError,
    OfflineError,
    SaasError,
)


# --------------------------------------------------------- is_retryable_error #

def test_offline_error_is_retryable():
    assert saas_retry.is_retryable_error(OfflineError("mất mạng")) is True


def test_rate_limited_is_retryable():
    assert saas_retry.is_retryable_error(
        SaasError("bận", code="RATE_LIMITED", status=429)) is True


def test_server_5xx_is_retryable():
    assert saas_retry.is_retryable_error(SaasError("lỗi", status=502)) is True


def test_insufficient_credit_not_retryable():
    assert saas_retry.is_retryable_error(InsufficientCreditError("hết Vox")) is False


def test_device_blocked_not_retryable():
    assert saas_retry.is_retryable_error(DeviceBlockedError("khoá")) is False


def test_maintenance_not_retryable():
    assert saas_retry.is_retryable_error(MaintenanceError("bảo trì")) is False


def test_generic_4xx_not_retryable():
    assert saas_retry.is_retryable_error(SaasError("sai payload", status=400)) is False


# ------------------------------------------------------------- call_with_retry #

@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """Không chờ thật trong test — chỉ quan tâm số lượt gọi/kết quả."""
    monkeypatch.setattr(saas_retry, "sleep_cancellable", lambda *a, **k: None)


def test_succeeds_first_try_no_retry():
    calls = []

    def fn():
        calls.append(1)
        return "ok"

    assert saas_retry.call_with_retry(fn, label="test") == "ok"
    assert len(calls) == 1


def test_retries_transient_then_succeeds():
    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise OfflineError("mất mạng")
        return "ok"

    result = saas_retry.call_with_retry(fn, label="test")
    assert result == "ok"
    assert attempts["n"] == 3


def test_gives_up_after_max_attempts():
    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        raise OfflineError("mất mạng mãi")

    with pytest.raises(OfflineError):
        saas_retry.call_with_retry(fn, label="test")
    assert attempts["n"] == saas_retry.MAX_ATTEMPTS


def test_non_retryable_error_raises_immediately_no_retry():
    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        raise InsufficientCreditError("hết Vox")

    with pytest.raises(InsufficientCreditError):
        saas_retry.call_with_retry(fn, label="test")
    assert attempts["n"] == 1   # không thử lại — lỗi cố định


def test_respects_retry_after_as_minimum_delay(monkeypatch):
    """retry_after của máy chủ phải được tôn trọng làm mức chờ tối thiểu."""
    seen_delays = []
    monkeypatch.setattr(
        saas_retry, "sleep_cancellable",
        lambda delay, reporter, stop: seen_delays.append(delay))

    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise SaasError("bận", code="RATE_LIMITED", status=429, retry_after=42.0)
        return "ok"

    saas_retry.call_with_retry(fn, label="test")
    assert seen_delays[0] >= 42.0
