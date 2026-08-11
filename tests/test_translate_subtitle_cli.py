"""Mini-spec V14 (docs/PLAN.md) — CLI `scripts/translate_subtitle.py`.

`scripts/` không phải package (không `__init__.py`) — nạp module bằng
đường dẫn file, đúng cách các CLI rời của dự án này vẫn được viết.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from unittest.mock import MagicMock

import pytest

_SCRIPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts", "translate_subtitle.py")


def _load_cli():
    spec = importlib.util.spec_from_file_location("translate_subtitle_cli", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def cli():
    return _load_cli()


SRT = "1\n00:00:01,000 --> 00:00:02,000\nHello\n"


def test_list_languages_exits_zero_and_prints_known_code(cli, capsys):
    rc = _run(cli, ["--list-languages"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "vie_Latn" in out
    assert "Vietnamese" in out


def test_missing_required_args_exits_nonzero(cli, tmp_path, capsys):
    path = tmp_path / "input.srt"
    path.write_text(SRT, encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _run(cli, [str(path), "--source", "eng_Latn"])  # thiếu --target
    assert exc.value.code != 0


def test_unknown_flores_code_exits_1(cli, tmp_path, capsys):
    path = tmp_path / "input.srt"
    path.write_text(SRT, encoding="utf-8")
    rc = _run(cli, [str(path), "--source", "eng_Latn", "--target", "bogus_code"])
    assert rc == 1
    assert "không phải mã FLORES-200 hợp lệ" in capsys.readouterr().err


def test_local_mode_translates_and_reports_output_path(cli, tmp_path, monkeypatch, capsys):
    path = tmp_path / "input.srt"
    path.write_text(SRT, encoding="utf-8")

    import autodub.text.translate_local as translate_local
    monkeypatch.setattr(translate_local, "run_local_worker",
                         lambda *a, **k: {1: "Xin chao"})

    rc = _run(cli, [str(path), "--source", "eng_Latn", "--target", "vie_Latn"])
    out = capsys.readouterr().out
    assert rc == 0
    assert str(tmp_path / "input_vie_Latn.srt") in out
    assert (tmp_path / "input_vie_Latn.srt").exists()


def test_saas_mode_reports_credit_charged(cli, tmp_path, monkeypatch, capsys):
    path = tmp_path / "input.srt"
    path.write_text(SRT, encoding="utf-8")

    fake_client = MagicMock()
    fake_client.translate_subtitle.return_value = {
        "segments": [{"id": 1, "text": "Xin chao"}],
        "creditCharged": 2, "balanceAfter": 98,
    }
    import autodub.saas_client as saas_client
    monkeypatch.setattr(saas_client, "get_client", lambda: fake_client)

    rc = _run(cli, [str(path), "--source", "eng_Latn", "--target", "vie_Latn", "--mode", "saas"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "2 Vox" in out
    assert "98" in out


def _run(cli, argv):
    old_argv = sys.argv
    sys.argv = ["translate_subtitle.py", *argv]
    try:
        return cli.main()
    finally:
        sys.argv = old_argv
