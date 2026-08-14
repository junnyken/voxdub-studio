"""Mini-spec V37 (docs/PLAN.md, Phase G) — SaasClient.generate_sound_effect()/
generate_music(): response 200 là AUDIO NHỊ PHÂN (không phải JSON), khác mọi
phương thức AI khác của SaasClient — test mock trực tiếp ở tầng HTTP
(``_http()``) vì không có wrapper module cấp cao hơn để mock (khác cách
`test_cloud_render.py` mock `saas_client.get_client()`)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from autodub.saas_client import (
    DeviceBlockedError, InsufficientCreditError, MaintenanceError, SaasClient,
    SaasError,
)


class _FakeResponse:
    def __init__(self, status_code=200, content=b"", headers=None, json_data=None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        self._json_data = json_data if json_data is not None else {}

    def json(self):
        return self._json_data


@pytest.fixture
def client(monkeypatch):
    c = SaasClient(base_url="http://fake.test")
    monkeypatch.setattr(c, "_load_token", lambda: "fake-token")
    return c


def _mock_post(client, response):
    fake_session = MagicMock()
    fake_session.post.return_value = response
    client._http = lambda: fake_session
    return fake_session


# ------------------------------------------------------- sound effect ----

def test_generate_sound_effect_writes_file_and_returns_billing(tmp_path, client):
    audio_bytes = b"fake-mp3-bytes"
    resp = _FakeResponse(200, content=audio_bytes,
                         headers={"X-Credit-Charged": "100", "X-Balance-After": "900"})
    _mock_post(client, resp)

    dest = str(tmp_path / "sfx.mp3")
    result = client.generate_sound_effect("tiếng vỗ tay", dest, duration_seconds=2.0)

    assert result == {"creditCharged": 100, "balanceAfter": 900}
    with open(dest, "rb") as f:
        assert f.read() == audio_bytes


def test_generate_sound_effect_sends_expected_payload(tmp_path, client):
    resp = _FakeResponse(200, content=b"x", headers={})
    session = _mock_post(client, resp)

    client.generate_sound_effect("tiếng chuông", str(tmp_path / "s.mp3"),
                                 duration_seconds=3.5, job_id="job-123")

    call = session.post.call_args
    assert call.args[0] == "http://fake.test/v1/ai/sound-effect"
    assert call.kwargs["json"] == {
        "text": "tiếng chuông", "durationSeconds": 3.5, "jobId": "job-123"}
    assert call.kwargs["headers"]["Authorization"] == "Bearer fake-token"


def test_generate_sound_effect_insufficient_credit_raises(tmp_path, client):
    resp = _FakeResponse(402, json_data={"code": "INSUFFICIENT_CREDIT",
                                         "message": "hết Vox", "balance": 5, "required": 100})
    _mock_post(client, resp)

    with pytest.raises(InsufficientCreditError) as exc_info:
        client.generate_sound_effect("x", str(tmp_path / "s.mp3"))
    assert exc_info.value.balance == 5
    assert exc_info.value.required == 100


def test_generate_sound_effect_disabled_raises_saas_error(tmp_path, client):
    resp = _FakeResponse(409, json_data={"code": "MUSIC_MATCH_DISABLED",
                                         "message": "đang tắt"})
    _mock_post(client, resp)

    with pytest.raises(SaasError) as exc_info:
        client.generate_sound_effect("x", str(tmp_path / "s.mp3"))
    assert exc_info.value.code == "MUSIC_MATCH_DISABLED"


def test_generate_sound_effect_device_blocked(tmp_path, client):
    resp = _FakeResponse(403, json_data={"code": "DEVICE_BLOCKED", "message": "bị khóa"})
    _mock_post(client, resp)
    with pytest.raises(DeviceBlockedError):
        client.generate_sound_effect("x", str(tmp_path / "s.mp3"))


def test_generate_sound_effect_maintenance(tmp_path, client):
    resp = _FakeResponse(503, json_data={"code": "MAINTENANCE", "message": "bảo trì"})
    _mock_post(client, resp)
    with pytest.raises(MaintenanceError):
        client.generate_sound_effect("x", str(tmp_path / "s.mp3"))


def test_generate_sound_effect_creates_parent_dir(tmp_path, client):
    resp = _FakeResponse(200, content=b"audio", headers={})
    _mock_post(client, resp)
    dest = str(tmp_path / "nested" / "dir" / "sfx.mp3")
    client.generate_sound_effect("x", dest)
    import os
    assert os.path.isfile(dest)


# -------------------------------------------------------------- music ----

def test_generate_music_writes_file_and_returns_billing(tmp_path, client):
    audio_bytes = b"fake-music-bytes"
    resp = _FakeResponse(200, content=audio_bytes,
                         headers={"X-Credit-Charged": "500", "X-Balance-After": "500"})
    _mock_post(client, resp)

    dest = str(tmp_path / "music.mp3")
    result = client.generate_music("nhạc nền vui tươi", dest, music_length_ms=30000)

    assert result == {"creditCharged": 500, "balanceAfter": 500}
    with open(dest, "rb") as f:
        assert f.read() == audio_bytes


def test_generate_music_sends_expected_payload(tmp_path, client):
    resp = _FakeResponse(200, content=b"x", headers={})
    session = _mock_post(client, resp)

    client.generate_music("nhạc buồn", str(tmp_path / "m.mp3"), music_length_ms=60000)

    call = session.post.call_args
    assert call.args[0] == "http://fake.test/v1/ai/music"
    assert call.kwargs["json"] == {"prompt": "nhạc buồn", "musicLengthMs": 60000}


def test_generate_music_offline_raises_when_no_base_url(tmp_path, monkeypatch):
    from autodub.saas_client import OfflineError

    c = SaasClient(base_url="")
    with pytest.raises(OfflineError):
        c.generate_music("x", str(tmp_path / "m.mp3"))
