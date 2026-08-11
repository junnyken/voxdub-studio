"""Mini-spec V12 (docs/PLAN.md) — autodub.cloud_render: tách nhạc nền qua
máy chủ (bất đồng bộ thật — nộp → poll → tải kết quả), thay Demucs máy.

``is_configured()`` vẫn là cổng duy nhất (cùng nguyên tắc SaaS/local-only
toàn sản phẩm) — các bài dưới đây khoá lại: KHÔNG dùng được ở local-only dù
``cloud_render_enabled=True``, lỗi cloud (mạng/job hỏng/quá hạn) phải ném
lỗi cho caller tự fallback (KHÔNG tự nuốt lỗi ở tầng này), và hủy pipeline
giữa lúc chờ (PipelineCancelled) phải truyền nguyên vẹn lên trên — không bị
coi là "lỗi cloud" rồi fallback nhầm sang Demucs máy.
"""
from __future__ import annotations

import json
import os
import wave
from unittest.mock import MagicMock

import pytest

from autodub import cloud_render
from autodub.config import Settings
from autodub.progress import PipelineCancelled, ProgressReporter


@pytest.fixture
def settings_enabled(monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    return Settings(cloud_render_enabled=True)


def write_wav(path: str, seconds: float = 0.2) -> None:
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))


# --------------------------------------------------------- is_available -- #

def test_not_available_when_disabled_even_if_configured(monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    settings = Settings(cloud_render_enabled=False)
    assert cloud_render.is_available(settings) is False


def test_not_available_when_local_only_even_if_enabled(monkeypatch):
    """is_configured() là cổng duy nhất — bật cờ không đủ, phải có máy chủ."""
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: False)
    settings = Settings(cloud_render_enabled=True)
    assert cloud_render.is_available(settings) is False


def test_available_when_both_enabled_and_configured(settings_enabled):
    assert cloud_render.is_available(settings_enabled) is True


# -------------------------------------------------------------- pricing -- #

def test_pricing_none_when_not_available(monkeypatch):
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: False)
    settings = Settings(cloud_render_enabled=True)
    assert cloud_render.pricing(settings) is None


def test_pricing_reads_server_config(settings_enabled, monkeypatch):
    fake_client = MagicMock()
    fake_client.app_config.return_value = {
        "cloudRenderEnabled": True,
        "pricing": {"cloudRenderDemucs": 50},
    }
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: fake_client)
    result = cloud_render.pricing(settings_enabled)
    assert result == {"enabled": True, "cost_vox": 50}


def test_pricing_none_on_server_error(settings_enabled, monkeypatch):
    from autodub.saas_client import SaasError
    fake_client = MagicMock()
    fake_client.app_config.side_effect = SaasError("mất mạng")
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: fake_client)
    assert cloud_render.pricing(settings_enabled) is None


# ------------------------------------------------- separate_vocals_cloud - #

def test_reuses_existing_output_without_calling_server(tmp_path, settings_enabled, monkeypatch):
    write_wav(str(tmp_path / "vocals.wav"))
    write_wav(str(tmp_path / "no_vocals.wav"))
    fake_client = MagicMock()
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: fake_client)

    result = cloud_render.separate_vocals_cloud("/tmp/in.wav", str(tmp_path))
    assert result["vocals"] == str(tmp_path / "vocals.wav")
    fake_client.submit_demucs_job.assert_not_called()


def test_full_flow_submit_poll_download_normalize(tmp_path, monkeypatch):
    """Mô phỏng luồng thật: queued → running → done, rồi tải 2 stem."""
    fake_client = MagicMock()
    fake_client.submit_demucs_job.return_value = {"jobId": "job1", "status": "queued"}
    fake_client.job_status.side_effect = [
        {"status": "running"},
        {"status": "done"},
    ]

    def fake_download(job_id, stem, dest_path):
        write_wav(dest_path)
    fake_client.download_job_result.side_effect = fake_download
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: fake_client)
    monkeypatch.setattr(cloud_render, "POLL_INTERVAL_S", 0.0)

    result = cloud_render.separate_vocals_cloud(
        "/tmp/in.wav", str(tmp_path), sample_rate=16000, channels=1)

    assert os.path.isfile(result["vocals"])
    assert os.path.isfile(result["no_vocals"])
    assert fake_client.job_status.call_count == 2
    assert fake_client.download_job_result.call_count == 2
    # File thô sau normalize phải bị dọn, không để rác lại trong thư mục dự án.
    assert not os.path.exists(os.path.join(str(tmp_path), "_vocals_cloud_raw.wav"))
    assert not os.path.exists(os.path.join(str(tmp_path), "_no_vocals_cloud_raw.wav"))


def test_job_failed_raises_with_server_error_message(tmp_path, monkeypatch):
    from autodub.saas_client import SaasError
    fake_client = MagicMock()
    fake_client.submit_demucs_job.return_value = {"jobId": "job2", "status": "queued"}
    fake_client.job_status.return_value = {"status": "failed", "error": "CUDA out of memory"}
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: fake_client)
    monkeypatch.setattr(cloud_render, "POLL_INTERVAL_S", 0.0)

    with pytest.raises(SaasError, match="CUDA out of memory"):
        cloud_render.separate_vocals_cloud("/tmp/in.wav", str(tmp_path))


def test_timeout_raises_after_max_wait(tmp_path, monkeypatch):
    from autodub.saas_client import SaasError
    fake_client = MagicMock()
    fake_client.submit_demucs_job.return_value = {"jobId": "job3", "status": "queued"}
    fake_client.job_status.return_value = {"status": "running"}
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: fake_client)
    monkeypatch.setattr(cloud_render, "POLL_INTERVAL_S", 0.0)
    monkeypatch.setattr(cloud_render, "MAX_WAIT_S", 0.0)

    with pytest.raises(SaasError, match="quá hạn"):
        cloud_render.separate_vocals_cloud("/tmp/in.wav", str(tmp_path))


# ------------------------------------------- mini-spec V16 (retry/backoff) - #

def test_poll_transient_error_retries_next_round(tmp_path, monkeypatch):
    """1 poll lỗi tạm thời (mất mạng) KHÔNG được huỷ job đang chạy khoẻ mạnh
    — vòng poll kế tiếp phải thử lại, không ném lỗi ngay."""
    from autodub.saas_client import OfflineError
    fake_client = MagicMock()
    fake_client.submit_demucs_job.return_value = {"jobId": "job5", "status": "queued"}
    fake_client.job_status.side_effect = [
        OfflineError("chớp mạng"),
        {"status": "done"},
    ]

    def fake_download(job_id, stem, dest_path):
        write_wav(dest_path)
    fake_client.download_job_result.side_effect = fake_download
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: fake_client)
    monkeypatch.setattr(cloud_render, "POLL_INTERVAL_S", 0.0)

    result = cloud_render.separate_vocals_cloud("/tmp/in.wav", str(tmp_path))
    assert os.path.isfile(result["vocals"])
    assert fake_client.job_status.call_count == 2


def test_poll_gives_up_after_consecutive_transient_errors(tmp_path, monkeypatch):
    from autodub.saas_client import OfflineError
    fake_client = MagicMock()
    fake_client.submit_demucs_job.return_value = {"jobId": "job6", "status": "queued"}
    fake_client.job_status.side_effect = OfflineError("mất mạng liên tục")
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: fake_client)
    monkeypatch.setattr(cloud_render, "POLL_INTERVAL_S", 0.0)

    with pytest.raises(OfflineError):
        cloud_render.separate_vocals_cloud("/tmp/in.wav", str(tmp_path))
    assert fake_client.job_status.call_count == cloud_render.MAX_CONSECUTIVE_POLL_ERRORS + 1


def test_poll_non_retryable_error_raises_immediately(tmp_path, monkeypatch):
    """Hết Vox giữa lúc poll (máy chủ chốt phí trễ) là lỗi CỐ ĐỊNH — không
    thử lại, ném ngay lần đầu."""
    from autodub.saas_client import InsufficientCreditError
    fake_client = MagicMock()
    fake_client.submit_demucs_job.return_value = {"jobId": "job7", "status": "queued"}
    fake_client.job_status.side_effect = InsufficientCreditError("hết Vox")
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: fake_client)
    monkeypatch.setattr(cloud_render, "POLL_INTERVAL_S", 0.0)

    with pytest.raises(InsufficientCreditError):
        cloud_render.separate_vocals_cloud("/tmp/in.wav", str(tmp_path))
    assert fake_client.job_status.call_count == 1


def test_download_retries_transient_error_then_succeeds(tmp_path, monkeypatch):
    from autodub.saas_client import OfflineError
    from autodub import saas_retry
    monkeypatch.setattr(saas_retry, "sleep_cancellable", lambda *a, **k: None)

    fake_client = MagicMock()
    fake_client.submit_demucs_job.return_value = {"jobId": "job8", "status": "queued"}
    fake_client.job_status.return_value = {"status": "done"}
    calls = {"n": 0}

    def fake_download(job_id, stem, dest_path):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OfflineError("chớp mạng lúc tải")
        write_wav(dest_path)
    fake_client.download_job_result.side_effect = fake_download
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: fake_client)
    monkeypatch.setattr(cloud_render, "POLL_INTERVAL_S", 0.0)

    result = cloud_render.separate_vocals_cloud("/tmp/in.wav", str(tmp_path))
    assert os.path.isfile(result["vocals"])
    # 2 stem, stem đầu lỗi 1 lần rồi thành công -> 3 lượt gọi tổng
    assert fake_client.download_job_result.call_count == 3


def test_cancellation_propagates_not_swallowed(tmp_path, monkeypatch):
    """Người dùng hủy giữa lúc chờ job cloud — PipelineCancelled phải bay
    thẳng lên caller, KHÔNG bị nuốt như một lỗi cloud thường."""
    fake_client = MagicMock()
    fake_client.submit_demucs_job.return_value = {"jobId": "job4", "status": "queued"}
    fake_client.job_status.return_value = {"status": "running"}
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: fake_client)
    monkeypatch.setattr(cloud_render, "POLL_INTERVAL_S", 0.0)

    def _raise_cancel():
        raise PipelineCancelled("hủy")
    reporter = ProgressReporter()
    reporter.check_cancelled = _raise_cancel

    with pytest.raises(PipelineCancelled):
        cloud_render.separate_vocals_cloud(
            "/tmp/in.wav", str(tmp_path), reporter=reporter)
