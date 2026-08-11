"""Mini-spec V14 (docs/PLAN.md) — core dịch phụ đề rời: parse -> dịch
(local/SaaS, mock cả hai) -> ghi file mới, giữ nguyên timestamp gốc."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from autodub.text import subtitle_translate as st

SRT = """1
00:00:01,000 --> 00:00:02,000
Hello

2
00:00:03,000 --> 00:00:04,000
World
"""


def _write_srt(tmp_path, name="input.srt"):
    p = tmp_path / name
    p.write_text(SRT, encoding="utf-8")
    return str(p)


def test_local_translate_writes_new_file_with_target_suffix(tmp_path, monkeypatch):
    path = _write_srt(tmp_path)
    import autodub.text.translate_local as translate_local
    monkeypatch.setattr(translate_local, "run_local_worker",
                         lambda *a, **k: {1: "Xin chao", 2: "The gioi"})

    result = st.translate_subtitle_file_local(
        path, "eng_Latn", "vie_Latn", settings=MagicMock())

    assert result.output_path == str(tmp_path / "input_vie_Latn.srt")
    assert result.cue_count == 2
    assert result.skipped_block_count == 0

    out_text = open(result.output_path, encoding="utf-8").read()
    assert "Xin chao" in out_text
    assert "The gioi" in out_text
    assert "00:00:01,000 --> 00:00:02,000" in out_text  # timestamp giữ nguyên


def test_local_translate_rejects_unknown_flores_code(tmp_path):
    path = _write_srt(tmp_path)
    with pytest.raises(st.SubtitleTranslateError, match="không hợp lệ"):
        st.translate_subtitle_file_local(
            path, "eng_Latn", "not_a_real_code", settings=MagicMock())


def test_translate_rejects_same_source_and_target(tmp_path):
    path = _write_srt(tmp_path)
    with pytest.raises(st.SubtitleTranslateError, match="giống nhau"):
        st.translate_subtitle_file_local(
            path, "vie_Latn", "vie_Latn", settings=MagicMock())


def test_translate_rejects_unsupported_extension(tmp_path):
    p = tmp_path / "input.txt"
    p.write_text("hello", encoding="utf-8")
    with pytest.raises(st.SubtitleTranslateError, match="Định dạng"):
        st.translate_subtitle_file_local(
            str(p), "eng_Latn", "vie_Latn", settings=MagicMock())


def test_saas_translate_charges_credit_and_writes_file(tmp_path, monkeypatch):
    path = _write_srt(tmp_path)
    fake_client = MagicMock()
    fake_client.translate_subtitle.return_value = {
        "segments": [{"id": 1, "text": "Xin chao"}, {"id": 2, "text": "The gioi"}],
        "creditCharged": 4,
        "balanceAfter": 96,
    }
    import autodub.saas_client as saas_client
    monkeypatch.setattr(saas_client, "get_client", lambda: fake_client)

    result = st.translate_subtitle_file_saas(
        path, "eng_Latn", "vie_Latn", job_id="j1")

    assert fake_client.translate_subtitle.called
    _, kwargs = fake_client.translate_subtitle.call_args
    assert kwargs["source_flores"] == "eng_Latn"
    assert kwargs["target_flores"] == "vie_Latn"
    assert kwargs["target_name"] == "Vietnamese"

    assert result.credit_charged == 4
    assert result.balance_after == 96
    out_text = open(result.output_path, encoding="utf-8").read()
    assert "Xin chao" in out_text


def test_missing_translation_falls_back_to_original_text(tmp_path, monkeypatch):
    """Câu không có trong kết quả trả về (id lệch/worker bỏ sót) giữ nguyên
    văn bản gốc thay vì để trống — an toàn hơn mất nội dung."""
    path = _write_srt(tmp_path)
    fake_client = MagicMock()
    fake_client.translate_subtitle.return_value = {
        "segments": [{"id": 1, "text": "Xin chao"}],  # thiếu id=2
        "creditCharged": 2, "balanceAfter": 98,
    }
    import autodub.saas_client as saas_client
    monkeypatch.setattr(saas_client, "get_client", lambda: fake_client)

    result = st.translate_subtitle_file_saas(
        path, "eng_Latn", "vie_Latn", job_id="j1")
    out_text = open(result.output_path, encoding="utf-8").read()
    assert "World" in out_text  # rơi về câu gốc


def test_saas_translate_retries_transient_error_then_succeeds(tmp_path, monkeypatch):
    """Mini-spec V16 (docs/PLAN.md, Phase E) — 1 chớp mạng không được làm
    hỏng cả file (job_id ổn định theo nội dung, thử lại an toàn về tiền)."""
    from autodub.saas_client import OfflineError
    from autodub import saas_retry
    monkeypatch.setattr(saas_retry, "sleep_cancellable", lambda *a, **k: None)

    path = _write_srt(tmp_path)
    fake_client = MagicMock()
    calls = {"n": 0}

    def fake_translate(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OfflineError("chớp mạng")
        return {
            "segments": [{"id": 1, "text": "Xin chao"}, {"id": 2, "text": "The gioi"}],
            "creditCharged": 4, "balanceAfter": 96,
        }
    fake_client.translate_subtitle.side_effect = fake_translate
    import autodub.saas_client as saas_client
    monkeypatch.setattr(saas_client, "get_client", lambda: fake_client)

    result = st.translate_subtitle_file_saas(
        path, "eng_Latn", "vie_Latn", job_id="j1")
    assert calls["n"] == 2
    assert result.credit_charged == 4


def test_saas_translate_non_retryable_error_raises_immediately(tmp_path, monkeypatch):
    from autodub.saas_client import InsufficientCreditError
    path = _write_srt(tmp_path)
    fake_client = MagicMock()
    fake_client.translate_subtitle.side_effect = InsufficientCreditError("hết Vox")
    import autodub.saas_client as saas_client
    monkeypatch.setattr(saas_client, "get_client", lambda: fake_client)

    with pytest.raises(InsufficientCreditError):
        st.translate_subtitle_file_saas(path, "eng_Latn", "vie_Latn", job_id="j1")
    assert fake_client.translate_subtitle.call_count == 1
