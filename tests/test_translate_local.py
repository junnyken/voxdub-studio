"""Mini-spec V6 (docs/PLAN.md) — dịch local/offline (path C)."""
from __future__ import annotations

import os
import sys

import pytest

from autodub.config import Settings
from autodub.languages import get_target
from autodub.text.translate_local import (
    LANG_TO_FLORES, flores_code, is_available,
)

# 8 ngôn ngữ nguồn thật trong GUI (V4) — mọi cái phải map được sang FLORES-200.
_GUI_SOURCE_LANGS = ["zh-CN", "en-US", "zh-HK", "zh-TW",
                     "ko-KR", "ja-JP", "th-TH", "id-ID"]


def test_every_gui_source_language_has_a_flores_code():
    for lang in _GUI_SOURCE_LANGS:
        assert flores_code(lang), f"thiếu FLORES-200 cho {lang}"


def test_target_vietnamese_has_a_flores_code():
    assert flores_code("vi-VN") == "vie_Latn"


def test_unmapped_language_returns_none():
    # "fr-FR" từng dùng làm ví dụ mã chưa map, nhưng V17 (Phase E) đã thêm nó
    # làm đích dubbing — đổi sang mã giả không thể có thật.
    assert flores_code("xx-XX") is None


def test_is_available_false_when_not_configured(monkeypatch):
    settings = Settings()
    monkeypatch.setattr(settings, "translate_local_configured", lambda: False)
    assert is_available(settings, "zh-CN") is False


def test_is_available_false_for_unsupported_language(monkeypatch):
    settings = Settings()
    monkeypatch.setattr(settings, "translate_local_configured", lambda: True)
    assert is_available(settings, "xx-XX") is False


def test_is_available_true_when_configured_and_supported(monkeypatch):
    settings = Settings()
    monkeypatch.setattr(settings, "translate_local_configured", lambda: True)
    assert is_available(settings, "zh-CN") is True


# --------------------------------------------------------------------- #
# Integration thật — chạy end-to-end qua subprocess worker + model NLLB
# THẬT (622 MB, đã tải và live-verify tay khi audit V6 — xem
# docs/TEST_LOG.md). Model KHÔNG được commit vào repo (quá lớn), nên test
# này tự skip nếu không tìm thấy — chạy tay bằng cách set biến môi trường
# VOXDUB_TEST_NLLB_MODEL_DIR trỏ tới thư mục model đã tải qua
# scripts/setup_translate_local.py.
_MODEL_DIR = os.environ.get("VOXDUB_TEST_NLLB_MODEL_DIR", "/tmp/nllb-model")
_HAS_MODEL = os.path.isfile(os.path.join(_MODEL_DIR, "model.bin"))


@pytest.mark.skipif(not _HAS_MODEL, reason=(
    "Cần model NLLB thật (622MB, không commit vào repo) — set "
    "VOXDUB_TEST_NLLB_MODEL_DIR hoặc chạy scripts/setup_translate_local.py "
    "rồi trỏ về models/translate-local để chạy test này."))
def test_translate_segments_local_end_to_end_real_model(monkeypatch):
    from autodub.text.translate_local import translate_segments_local

    settings = Settings()
    monkeypatch.setattr(settings, "translate_local_venv_python_path",
                        lambda: sys.executable)
    monkeypatch.setattr(settings, "translate_local_model_dir_path",
                        lambda: _MODEL_DIR)

    segments = [
        {"id": 1, "text": "你好，欢迎来到我们的视频。"},
        {"id": 2, "text": "今天我们来做一道简单的家常菜。"},
    ]
    target = get_target("vi")
    result = translate_segments_local(segments, target, "zh-CN", settings)

    assert len(result) == 2
    for seg in result:
        text = seg[target.text_field]
        assert text, f"câu {seg['id']} dịch ra rỗng"
        # Kết quả phải là tiếng Việt thật, không phải giữ nguyên tiếng Trung.
        assert "你好" not in text and "视频" not in text
    print("Bản dịch thật (live NLLB):", [s[target.text_field] for s in result])
