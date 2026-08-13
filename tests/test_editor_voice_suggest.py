"""`autodub.editor.suggest_voice()` — mini-spec V33, docs/PLAN.md Phase G.

Đọc `data/video_context.json` (kết quả phân tích ngữ cảnh SaaS, có thể còn
bị khóa AES-256-GCM tới khi hold Vox chốt) và đề xuất giọng phù hợp — hàm
thuần, không cần Qt, xem `tests/test_editor_speakers.py` cho cùng khuôn.
"""
from __future__ import annotations

import json

import pytest

from autodub import securestore
from autodub.editor import suggest_voice
from autodub.speech.tts.voices import Voice
from autodub.workdir import data_path


def _catalog():
    return [
        Voice(name="Minh Trang", gender="female", style="tu_nhien"),
        Voice(name="Bảo Long", gender="male", style="tu_nhien"),
        Voice(name="Thu Hà (tin tức)", gender="female", style="tin_tuc"),
    ]


@pytest.fixture()
def work_dir(tmp_path):
    work = tmp_path / "20260813_vi"
    (work / "data").mkdir(parents=True)
    return str(work)


def _write_context(work_dir: str, payload: dict, key: str | None = None) -> None:
    path = data_path(work_dir, "video_context.json")
    securestore.write_json_secure(payload, path, key=key)


def test_no_file_returns_none(work_dir):
    assert suggest_voice(work_dir, _catalog()) is None


def test_file_without_voice_hint_returns_none(work_dir):
    _write_context(work_dir, {"summary": "x", "domain": "y"})
    assert suggest_voice(work_dir, _catalog()) is None


def test_plain_unlocked_file_with_voice_hint_returns_suggestion(work_dir):
    """Dự án đã xuất video (hold đã chốt, file đã mở khóa) — đọc được ngay,
    không cần khóa."""
    _write_context(work_dir, {
        "summary": "x", "domain": "review công nghệ",
        "voice_hint": {"gender": "female", "style": "tin_tuc"},
    })
    result = suggest_voice(work_dir, _catalog())
    assert result is not None
    assert result.voice.name == "Thu Hà (tin tức)"


def test_still_locked_file_returns_none_no_server_roundtrip(work_dir):
    """Dự án chưa xuất (hold chưa chốt, file còn khóa AES-256-GCM) — KHÔNG
    xin lại khóa từ máy chủ (Design Choice), coi như không có tín hiệu."""
    real_key = "0" * 64
    _write_context(work_dir, {
        "summary": "x", "domain": "y",
        "voice_hint": {"gender": "female", "style": "tin_tuc"},
    }, key=real_key)
    assert suggest_voice(work_dir, _catalog()) is None


def test_corrupt_file_returns_none(work_dir):
    path = data_path(work_dir, "video_context.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write("{not valid json")
    assert suggest_voice(work_dir, _catalog()) is None


def test_suggestion_matching_current_voice_returns_none(work_dir):
    """Giọng đề xuất trùng giọng đang dùng — không có gì mới để gợi ý."""
    _write_context(work_dir, {
        "summary": "x", "domain": "y",
        "voice_hint": {"gender": "female", "style": "tin_tuc"},
    })
    result = suggest_voice(work_dir, _catalog(), current_voice="Thu Hà (tin tức)")
    assert result is None


def test_non_dict_analysis_returns_none(work_dir):
    """analyze_transcript() có thể lưu None/list nếu phân tích lỗi — không
    được crash khi đọc lại."""
    path = data_path(work_dir, "video_context.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(["not", "a", "dict"], f)
    assert suggest_voice(work_dir, _catalog()) is None
