"""Mini-spec V28 (docs/PLAN.md, Phase G) — re-audit: đóng "Remaining Limit"
ghi trong docs/TEST_LOG.md (đường tín hiệu LLM/SaaS per-segment CHƯA nối ở
lượt implement đầu). Khoá lại 2 điều:

1. `translate_segments()` gửi đúng `emotion_tone=settings.emotion_voice_enabled`
   xuống `client.translate()` — cùng cờ Cài đặt đã bật đường heuristic local
   (0 regression: tắt cờ vẫn gửi False y hệt trước khi có tham số này).
2. `_merge()` (nội bộ, ghép kết quả máy chủ vào segment gốc) copy đúng
   `seg["tone"]` khi máy chủ có trả, KHÔNG bịa khi máy chủ không trả.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from autodub.config import Settings
from autodub.languages import get_target
from autodub.text import translate_saas
from autodub.text.translate_common import HOLD

SEGMENTS = [
    {"id": 1, "text": "hello", "duration": 2.0, "slot": 2.0},
    {"id": 2, "text": "world", "duration": 2.0, "slot": 2.0},
]


@pytest.fixture(autouse=True)
def reset_hold():
    HOLD.clear()
    yield
    HOLD.clear()


def _fake_client(segments_out):
    fake = MagicMock()
    fake.translate.return_value = {
        "segments": segments_out, "creditCharged": 2, "balanceAfter": 100,
    }
    return fake


def test_translate_segments_sends_emotion_tone_false_by_default(monkeypatch):
    fake_client = _fake_client(
        [{"id": s["id"], "text_vi": f"vi {s['text']}"} for s in SEGMENTS])
    monkeypatch.setattr(translate_saas, "get_client", lambda: fake_client)

    settings = Settings()
    assert settings.emotion_voice_enabled is False
    translate_saas.translate_segments(SEGMENTS, get_target("vi"), "zh-CN", settings)

    _, kwargs = fake_client.translate.call_args
    assert kwargs["emotion_tone"] is False


def test_translate_segments_sends_emotion_tone_true_when_setting_enabled(monkeypatch):
    import dataclasses

    fake_client = _fake_client(
        [{"id": s["id"], "text_vi": f"vi {s['text']}", "tone": "neutral"} for s in SEGMENTS])
    monkeypatch.setattr(translate_saas, "get_client", lambda: fake_client)

    settings = dataclasses.replace(Settings(), emotion_voice_enabled=True)
    translate_saas.translate_segments(SEGMENTS, get_target("vi"), "zh-CN", settings)

    _, kwargs = fake_client.translate.call_args
    assert kwargs["emotion_tone"] is True


def test_translate_segments_carries_tone_into_result_segments(monkeypatch):
    """Đường dây đầy đủ: máy chủ trả tone -> segment cuối cùng người dùng
    thấy (đưa vào pipeline._apply_emotion_styles sau đó) có seg["tone"]."""
    import dataclasses

    fake_client = _fake_client([
        {"id": 1, "text_vi": "Chào.", "tone": "excited"},
        {"id": 2, "text_vi": "Thế giới.", "tone": "neutral"},
    ])
    monkeypatch.setattr(translate_saas, "get_client", lambda: fake_client)

    settings = dataclasses.replace(Settings(), emotion_voice_enabled=True)
    result = translate_saas.translate_segments(
        SEGMENTS, get_target("vi"), "zh-CN", settings)

    by_id = {s["id"]: s for s in result}
    assert by_id[1]["tone"] == "excited"
    assert by_id[2]["tone"] == "neutral"


def test_translate_segments_no_tone_field_when_server_omits_it(monkeypatch):
    """emotion_tone=False (mặc định) -> máy chủ không trả tone -> segment
    KHÔNG có field tone (0 regression, không bịa)."""
    fake_client = _fake_client(
        [{"id": s["id"], "text_vi": f"vi {s['text']}"} for s in SEGMENTS])
    monkeypatch.setattr(translate_saas, "get_client", lambda: fake_client)

    result = translate_saas.translate_segments(
        SEGMENTS, get_target("vi"), "zh-CN", Settings())

    assert all("tone" not in s for s in result)


# --------------------------------------------------------------- _merge() --

def test_merge_copies_tone_when_present():
    batch = [{"id": 1, "text": "hello"}]
    returned = [{"id": 1, "text_vi": "Xin chào.", "tone": "serious"}]
    merged = translate_saas._merge(batch, returned, "text_vi")
    assert merged[0]["tone"] == "serious"
    assert merged[0]["text_vi"] == "Xin chào."


def test_merge_omits_tone_when_absent():
    batch = [{"id": 1, "text": "hello"}]
    returned = [{"id": 1, "text_vi": "Xin chào."}]
    merged = translate_saas._merge(batch, returned, "text_vi")
    assert "tone" not in merged[0]


def test_merge_missing_segment_has_no_tone():
    """Câu máy chủ không dịch được (giữ bản gốc) không được bịa tone."""
    batch = [{"id": 1, "text": "hello"}]
    merged = translate_saas._merge(batch, [], "text_vi")
    assert "tone" not in merged[0]
    assert merged[0]["text_vi"] == "hello"
