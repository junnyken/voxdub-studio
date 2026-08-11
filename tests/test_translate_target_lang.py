"""Mini-spec V15 (docs/PLAN.md) — bug thật đã sửa: client trước đây KHÔNG
gửi ``targetLang`` lên máy chủ, nên `/v1/ai/translate` (và analyze/review)
luôn dịch sang tiếng Việt bất kể ``target`` thật của lượt dubbing — lồng
tiếng tiếng Anh (V8/V11) qua SaaS thực chất vẫn nhận về tiếng Việt.

Test này khoá lại: mỗi lời gọi `client.translate()`/`analyze()`/`review()`
từ `translate_saas.py`/`translate_review.py` PHẢI mang đúng
``target_lang=target.key`` — không còn ngầm định "vi".
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


def test_translate_segments_passes_target_key_to_client(monkeypatch):
    fake_client = MagicMock()
    fake_client.translate.return_value = {
        "segments": [{"id": s["id"], "text_en": f"en {s['text']}"} for s in SEGMENTS],
        "creditCharged": 2, "balanceAfter": 100,
    }
    monkeypatch.setattr(translate_saas, "get_client", lambda: fake_client)

    target = get_target("en")
    translate_saas.translate_segments(SEGMENTS, target, "zh-CN", Settings())

    assert fake_client.translate.called
    _, kwargs = fake_client.translate.call_args
    assert kwargs["target_lang"] == "en"


def test_translate_segments_target_vi_unchanged(monkeypatch):
    """0 regression — target=vi vẫn gửi target_lang="vi" như hành vi ngầm
    định trước đây (không phải KHÔNG gửi gì, mà gửi ĐÚNG giá trị "vi")."""
    fake_client = MagicMock()
    fake_client.translate.return_value = {
        "segments": [{"id": s["id"], "text_vi": f"vi {s['text']}"} for s in SEGMENTS],
        "creditCharged": 2, "balanceAfter": 100,
    }
    monkeypatch.setattr(translate_saas, "get_client", lambda: fake_client)

    target = get_target("vi")
    translate_saas.translate_segments(SEGMENTS, target, "zh-CN", Settings())

    _, kwargs = fake_client.translate.call_args
    assert kwargs["target_lang"] == "vi"


def test_analyze_transcript_passes_target_key(monkeypatch):
    fake_client = MagicMock()
    fake_client.analyze.return_value = {
        "summary": "x", "domain": "y", "pronouns": "z", "glossary": [], "style_notes": "w",
    }
    monkeypatch.setattr(translate_saas, "get_client", lambda: fake_client)

    target = get_target("en")
    translate_saas.analyze_transcript(SEGMENTS, "zh-CN", target)

    assert fake_client.analyze.called
    _, kwargs = fake_client.analyze.call_args
    assert kwargs["target_lang"] == "en"


def test_analyze_transcript_defaults_to_vi_when_no_target_given(monkeypatch):
    """0 regression cho lời gọi cũ không truyền target."""
    fake_client = MagicMock()
    fake_client.analyze.return_value = None
    monkeypatch.setattr(translate_saas, "get_client", lambda: fake_client)

    translate_saas.analyze_transcript(SEGMENTS, "zh-CN")

    _, kwargs = fake_client.analyze.call_args
    assert kwargs["target_lang"] == "vi"
