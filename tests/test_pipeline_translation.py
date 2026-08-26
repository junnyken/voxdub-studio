"""Tests for DubPipeline._load_translation validation."""
import json

import pytest

from autodub.config import Settings
from autodub.languages import get_target
from autodub.pipeline import DubPipeline


@pytest.fixture
def pipeline():
    return DubPipeline(Settings())


@pytest.fixture
def target_vi():
    return get_target("vi")


def _write(tmp_path, data, raw=None):
    path = tmp_path / "transcript_vi.json"
    if raw is not None:
        path.write_text(raw, encoding="utf-8")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


SEGMENTS = [
    {"id": 1, "text": "hello", "start": 0.0, "end": 2.0, "duration": 2.0},
    {"id": 2, "text": "world", "start": 2.0, "end": 4.0, "duration": 2.0},
]


def test_valid_translation_loads(pipeline, target_vi, tmp_path):
    translated = [{**s, "text_vi": f"vi {s['text']}"} for s in SEGMENTS]
    path = _write(tmp_path, translated)
    result = pipeline._load_translation(path, SEGMENTS, target_vi)
    assert len(result) == 2
    # Terminal punctuation is enforced on load (manual translations too).
    assert result[0]["text_vi"] == "vi hello."
    # Slots annotated: real window until the next line starts.
    assert result[0]["slot"] == 2.0


def test_invalid_json_raises(pipeline, target_vi, tmp_path):
    path = _write(tmp_path, None, raw='```json\n[{"id": 1}]\n```')
    with pytest.raises(ValueError, match="Invalid JSON"):
        pipeline._load_translation(path, SEGMENTS, target_vi)


def test_missing_text_field_raises(pipeline, target_vi, tmp_path):
    translated = [{**SEGMENTS[0], "text_vi": "ok"}, dict(SEGMENTS[1])]  # seg 2 untranslated
    path = _write(tmp_path, translated)
    with pytest.raises(ValueError, match="text_vi"):
        pipeline._load_translation(path, SEGMENTS, target_vi)


def test_empty_array_raises(pipeline, target_vi, tmp_path):
    path = _write(tmp_path, [])
    with pytest.raises(ValueError, match="non-empty"):
        pipeline._load_translation(path, SEGMENTS, target_vi)


def test_non_array_raises(pipeline, target_vi, tmp_path):
    path = _write(tmp_path, {"segments": []})
    with pytest.raises(ValueError, match="non-empty"):
        pipeline._load_translation(path, SEGMENTS, target_vi)


def test_thieu_cau_thi_dung_han(pipeline, target_vi, tmp_path):
    """ĐỔI HÀNH VI có chủ đích (26/08/2026): bản dịch ÍT câu hơn bản gốc là
    mất nội dung, không được lặng lẽ dùng.

    Test này trước đây tên `test_count_mismatch_warns_but_loads` và khẳng
    định điều ngược lại — chỉ ghi cảnh báo rồi nạp tệp thiếu. Người dùng thật
    báo hậu quả: *"rất nhiều câu nhưng dịch rất ít nên nó bị thiếu"*, video
    xuất ra mất hẳn phần lời thoại và cảnh báo thì trôi trong nhật ký.
    """
    translated = [{**SEGMENTS[0], "text_vi": "vi"}]
    path = _write(tmp_path, translated)
    with pytest.raises(ValueError, match="thiếu"):
        pipeline._load_translation(path, SEGMENTS, target_vi)


def test_thua_cau_van_nap_chi_canh_bao(pipeline, target_vi, tmp_path):
    """Tách một câu dài thành hai là sửa tay hợp lệ — không chặn."""
    translated = [{**s, "text_vi": "vi"} for s in SEGMENTS]
    translated.append({**SEGMENTS[-1], "id": 99, "text_vi": "vi"})
    path = _write(tmp_path, translated)
    result = pipeline._load_translation(path, SEGMENTS, target_vi)
    assert len(result) == 3
