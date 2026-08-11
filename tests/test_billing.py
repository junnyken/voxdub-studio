"""Unit test cho autodub/billing.py (HoldBillingAdapter) — mini-spec V2.

Trước V2, logic này (di chuyển nguyên văn từ DubPipeline._setup_hold/
_stop_for_export/_settle_hold_inline/_money_note_for_manual) không có test nào
bảo vệ trực tiếp. File này lấp khoảng trống đó: mock autodub.saas_client (module
nguồn của get_client/is_configured — billing.py import cục bộ trong từng hàm nên
patch đúng module gốc là đủ, không cần patch billing.py), dùng file thật qua
tmp_path cho phần securestore (crypto thuần, không cần mạng/GPU).
"""
from __future__ import annotations

import json

import pytest

from autodub import securestore
from autodub.billing import HoldBillingAdapter
from autodub.config import Settings
from autodub.languages import get_target
from autodub.progress import ProgressReporter
from autodub.saas_client import (
    InsufficientCreditError, OfflineError, SaasError,
)
from autodub.text.translate_common import HOLD, USAGE


@pytest.fixture(autouse=True)
def _clean_global_hold_state():
    """HOLD/USAGE là global state (autodub.text.translate_common) — mỗi test
    phải bắt đầu/kết thúc sạch để không rò rỉ sang test khác."""
    HOLD.clear()
    USAGE.reset()
    yield
    HOLD.clear()
    USAGE.reset()


@pytest.fixture
def adapter():
    return HoldBillingAdapter(Settings(), ProgressReporter())


@pytest.fixture
def target_vi():
    return get_target("vi")


SEGMENTS = [
    {"id": 1, "text": "你好", "start": 0.0, "end": 2.0},
    {"id": 2, "text": "再见", "start": 2.0, "end": 4.0},
]


class _FakeClient:
    def __init__(self, create_hold_result=None, create_hold_error=None,
                 get_hold_result=None, commit_hold_result=None,
                 commit_hold_error=None):
        self._create_hold_result = create_hold_result
        self._create_hold_error = create_hold_error
        self._get_hold_result = get_hold_result or {}
        self._commit_hold_result = commit_hold_result
        self._commit_hold_error = commit_hold_error
        self.create_hold_calls = []
        self.commit_hold_calls = []

    def create_hold(self, run_id, n_segments, duration_s, auto_translate, metadata):
        self.create_hold_calls.append(
            (run_id, n_segments, duration_s, auto_translate, metadata))
        if self._create_hold_error:
            raise self._create_hold_error
        return self._create_hold_result

    def get_hold(self, hold_id):
        return self._get_hold_result

    def commit_hold(self, hold_id):
        self.commit_hold_calls.append(hold_id)
        if self._commit_hold_error:
            raise self._commit_hold_error
        return self._commit_hold_result


# --------------------------------------------------------------- setup_hold --

def test_setup_hold_noop_when_not_configured(adapter, target_vi, monkeypatch):
    """Không cấu hình VOXDUB_API_URL — không gọi mạng, không set HOLD."""
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: False)
    result = adapter.setup_hold(SEGMENTS, target_vi, "/tmp/wd", 4.0)
    assert result is None
    assert not HOLD.active


def test_setup_hold_success_sets_hold_and_estimate(adapter, target_vi, monkeypatch):
    client = _FakeClient(create_hold_result={
        "created": True,
        "balance": 360,
        "hold": {"encKeyHex": "a" * 64, "estimatedVox": 260},
    })
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: client)

    result = adapter.setup_hold(SEGMENTS, target_vi, "/tmp/wd", 4.0)

    assert result is None, "hold thành công không chặn pipeline"
    assert HOLD.active
    assert HOLD.key == "a" * 64
    assert adapter.hold_estimate == 260
    assert len(client.create_hold_calls) == 1
    run_id, n_segments, duration_s, auto, meta = client.create_hold_calls[0]
    assert n_segments == 2
    assert duration_s == 4.0


def test_setup_hold_insufficient_credit_blocks_pipeline(adapter, target_vi, monkeypatch):
    err = InsufficientCreditError("not enough", balance=20, required=260)
    client = _FakeClient(create_hold_error=err)
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: client)

    result = adapter.setup_hold(SEGMENTS, target_vi, "/tmp/wd", 4.0)

    assert result is not None
    assert result.status == "credit_blocked"
    assert result.report["balance"] == 20
    assert result.report["required"] == 260
    assert not HOLD.active, "chặn vì thiếu Vox thì không được set hold"


def test_setup_hold_finished_unlocks_and_continues(adapter, target_vi, monkeypatch, tmp_path):
    """Hold cũ đã tự chốt (quá 48h) — pipeline chạy tiếp kiểu thường, không
    chặn, và cố mở khóa file trung gian của lượt trước bằng key lấy lại được."""
    # Dựng 1 file đã khóa thật để unlock_after_commit có gì để mở.
    work_dir = str(tmp_path)
    key = "b" * 64
    locked_file = tmp_path / "transcript_vi.json"
    locked_file.write_text(json.dumps({"x": 1}), encoding="utf-8")
    securestore.encrypt_file(str(locked_file), key)
    securestore.add_locked_file(work_dir, "old-hold-id", str(locked_file))
    assert securestore.is_locked(work_dir)

    client = _FakeClient(
        create_hold_error=SaasError("finished", code="HOLD_FINISHED"),
        get_hold_result={"hold": {"encKeyHex": key}},
    )
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: client)

    result = adapter.setup_hold(SEGMENTS, target_vi, work_dir, 4.0)

    assert result is None, "HOLD_FINISHED không chặn — chạy tiếp kiểu thường"
    assert not securestore.is_locked(work_dir), "phải mở khóa file của lượt trước"


def test_setup_hold_disabled_falls_back_silently(adapter, target_vi, monkeypatch):
    client = _FakeClient(create_hold_error=SaasError("off", code="HOLD_DISABLED"))
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: client)

    result = adapter.setup_hold(SEGMENTS, target_vi, "/tmp/wd", 4.0)
    assert result is None
    assert not HOLD.active


def test_setup_hold_offline_falls_back_silently(adapter, target_vi, monkeypatch):
    client = _FakeClient(create_hold_error=OfflineError("no network"))
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: client)

    result = adapter.setup_hold(SEGMENTS, target_vi, "/tmp/wd", 4.0)
    assert result is None
    assert not HOLD.active


def test_setup_hold_missing_key_falls_back(adapter, target_vi, monkeypatch):
    """Máy chủ trả hold nhưng thiếu encKeyHex — coi như lỗi, không set HOLD
    (nếu không, các bước sau sẽ mã hóa bằng khóa rỗng và tự khóa chính mình)."""
    client = _FakeClient(create_hold_result={
        "created": True, "balance": 100, "hold": {"estimatedVox": 50},
    })
    monkeypatch.setattr("autodub.saas_client.is_configured", lambda: True)
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: client)

    result = adapter.setup_hold(SEGMENTS, target_vi, "/tmp/wd", 4.0)
    assert result is None
    assert not HOLD.active


# ------------------------------------------------------- money_note_for_manual --

def test_money_note_empty_when_no_hold(adapter):
    assert adapter.money_note_for_manual() == ""


def test_money_note_generic_when_estimate_missing(adapter):
    HOLD.set("run-1", "c" * 64)
    adapter.hold_estimate = 0
    note = adapter.money_note_for_manual()
    assert "không tốn thêm Vox" in note


def test_money_note_states_amount_when_known(adapter):
    HOLD.set("run-1", "c" * 64)
    adapter.hold_estimate = 260
    note = adapter.money_note_for_manual()
    assert "260" in note


# ------------------------------------------------------------ settle_hold_inline --

def test_settle_hold_inline_noop_without_active_hold(adapter, tmp_path):
    adapter.settle_hold_inline(str(tmp_path))  # không set HOLD trước — phải no-op êm


def test_settle_hold_inline_commits_and_unlocks(adapter, monkeypatch, tmp_path):
    work_dir = str(tmp_path)
    key = "d" * 64
    locked_file = tmp_path / "audio.wav"
    locked_file.write_bytes(b"fake-audio")
    securestore.encrypt_file(str(locked_file), key)
    securestore.add_locked_file(work_dir, "hold-x", str(locked_file))

    HOLD.set("hold-x", key)
    client = _FakeClient(commit_hold_result={"chargedVox": 260, "balance": 100})
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: client)

    adapter.settle_hold_inline(work_dir)

    assert client.commit_hold_calls == ["hold-x"]
    assert USAGE.snapshot()["vox"] == 260
    assert not securestore.is_locked(work_dir), "commit thành công phải mở khóa"


def test_settle_hold_inline_network_error_still_unlocks_with_ram_key(adapter, monkeypatch, tmp_path):
    """Lỗi mạng lúc commit KHÔNG được chặn — khóa vẫn còn trong RAM (đã trả
    tiền từ lúc tạo hold) nên vẫn phải mở khóa file trung gian."""
    work_dir = str(tmp_path)
    key = "e" * 64
    locked_file = tmp_path / "audio.wav"
    locked_file.write_bytes(b"fake-audio")
    securestore.encrypt_file(str(locked_file), key)
    securestore.add_locked_file(work_dir, "hold-y", str(locked_file))

    HOLD.set("hold-y", key)
    client = _FakeClient(commit_hold_error=OfflineError("mất mạng"))
    monkeypatch.setattr("autodub.saas_client.get_client", lambda: client)

    adapter.settle_hold_inline(work_dir)

    assert not securestore.is_locked(work_dir), "vẫn phải mở khóa dù commit lỗi mạng"


# ---------------------------------------------------------------- stop_for_export --

def test_stop_for_export_encrypts_and_returns_pending(adapter, monkeypatch, tmp_path):
    work_dir = str(tmp_path)
    key = "f" * 64
    HOLD.set("hold-z", key)

    merged_audio = tmp_path / "merged.wav"
    merged_audio.write_bytes(b"fake-merged-audio")

    monkeypatch.setattr("autodub.saas_client.get_client",
                        lambda: _FakeClient(get_hold_result={
                            "hold": {"estimatedVox": 260}}))

    state = {
        "merged_audio_path": str(merged_audio),
        "segments": SEGMENTS,
        "voice": "nam",
        "subtitle_mode": "none",
        "blur_regions": [],
        "subtitle_style": {},
    }
    result = adapter.stop_for_export(state, work_dir)

    assert result.status == "export_pending"
    assert result.report["hold_id"] == "hold-z"
    assert result.report["sentences"] == 2
    assert securestore.is_encrypted(str(merged_audio)), "audio ghép phải được mã hóa"
    assert securestore.is_locked(work_dir)
