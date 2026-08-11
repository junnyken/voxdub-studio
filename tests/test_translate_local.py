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


# --------------------------------------------------------------------- #
# mini-spec V21 (docs/PLAN.md, Phase E) — bug thật tìm ra + cô lập ở V11
# (docs/TEST_LOG.md): 1 segment nhiều câu, model NLLB "dừng sớm" khi gặp
# nhiễu ASR trong 1 câu -> mất HOÀN TOÀN các câu sau trong cùng segment.
# Sửa: dịch từng câu riêng trong translate_local_worker.py.

def test_split_sentences_pure_function():
    from autodub.text.translate_local_worker import _split_sentences

    assert _split_sentences("Một câu thôi.") == ["Một câu thôi."]
    assert _split_sentences("Câu một. Câu hai! Câu ba?") == [
        "Câu một.", "Câu hai!", "Câu ba?"]
    assert _split_sentences("") == []
    assert _split_sentences("Không dấu kết câu") == ["Không dấu kết câu"]


def test_split_sentences_handles_cjk_fullwidth_punctuation():
    from autodub.text.translate_local_worker import _split_sentences

    assert _split_sentences("你好。今天天气很好！") == ["你好。", "今天天气很好！"]


@pytest.mark.skipif(not _HAS_MODEL, reason=(
    "Cần model NLLB thật (622MB, không commit vào repo) — set "
    "VOXDUB_TEST_NLLB_MODEL_DIR hoặc chạy scripts/setup_translate_local.py "
    "rồi trỏ về models/translate-local để chạy test này."))
def test_multi_sentence_segment_with_noisy_asr_no_longer_drops_second_sentence():
    """Tái tạo ĐÚNG văn bản đã gây bug thật ở V11 — segment 2 câu, câu 2 có
    lỗi nghe ASR nhẹ ("giàn lập" thay vì "giả lập"). TRƯỚC V21: model dừng
    sớm ở câu 1, câu 2 mất hoàn toàn, không lỗi, không log. SAU V21: cả 2
    câu đều có mặt trong bản dịch (không đòi hỏi câu 2 dịch HOÀN HẢO — input
    vốn nhiễu — chỉ đòi hỏi KHÔNG BỊ BỎ SÓT hoàn toàn)."""
    from autodub.text.translate_local import translate_segments_local

    settings = Settings()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(settings, "translate_local_venv_python_path",
                        lambda: sys.executable)
    monkeypatch.setattr(settings, "translate_local_model_dir_path",
                        lambda: _MODEL_DIR)
    try:
        segments = [{"id": 1, "text": (
            "Trí tựa nhân tạo đang thay đổi cách chúng ta làm việc. "
            "Đây chỉ là giàn lập, không phải thật.")}]
        target = get_target("en")
        result = translate_segments_local(segments, target, "vi-VN", settings)
        text = result[0][target.text_field]
        print("Bản dịch thật (live NLLB, sau V21):", text)
        # Trước V21: text CHỈ có câu 1 ("...changing the way we work.") rồi
        # DỪNG — câu 2 không để lại DẤU VẾT nào. Khoá: câu 2 phải có mặt.
        assert len(text) > len("Artificial intelligence is changing "
                               "the way we work.") + 10, (
            "Câu thứ 2 của segment bị bỏ sót — đúng bug V11 chưa sửa")
    finally:
        monkeypatch.undo()
