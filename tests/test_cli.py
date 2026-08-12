"""Mini-spec V22 (docs/PLAN.md, Phase F) — CLI headless (`autodub/cli.py`).

Nền tảng cho V23/V24/V25 (Phase F còn lại): mở đường vào pipeline không cần
Qt/GUI. Test ở đây KHÔNG chạy pipeline thật (cần mạng/GPU) — chỉ kiểm tra
lớp vỏ CLI: parse tham số đúng, cách ly import khỏi GUI, exit code đúng
contract, và validate giọng/target tường minh (không rơi ngầm như
``voices.resolve()`` — xem docstring ``_validate_voice`` trong cli.py).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from autodub import cli
from autodub.pipeline import DubResult


# --------------------------------------------------------------------- #
# Cách ly import — CLI không được kéo theo Qt/GUI (Constraint 2 của V22).
#
# PHẢI chạy trong tiến trình con riêng: chạy trong cùng tiến trình pytest
# với các file test khác (test_editor.py, test_fonts_app_only.py...) vốn
# TỰ import autodub_gui/PySide6 sẽ làm ô nhiễm sys.modules TRƯỚC KHI test
# này chạy — không phải do `import autodub.cli` gây ra, chỉ là hệ quả thứ
# tự collection của pytest. Tiến trình con sạch mới đo đúng cái cần đo.

def test_importing_cli_does_not_pull_in_gui_or_qt():
    result = subprocess.run(
        [sys.executable, "-c",
         "import autodub.cli, sys; "
         "assert 'PySide6' not in sys.modules; "
         "assert 'autodub_gui' not in sys.modules; "
         "print('OK')"],
        cwd=cli.__file__.rsplit("/autodub/", 1)[0],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


# --------------------------------------------------------------------- #
# Parser cơ bản

def test_help_exits_zero(capsys):
    parser = cli.build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--help"])
    assert exc.value.code == 0


def test_dub_subcommand_help_exits_zero():
    parser = cli.build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["dub", "--help"])
    assert exc.value.code == 0


def test_batch_subcommand_help_exits_zero():
    parser = cli.build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["batch", "--help"])
    assert exc.value.code == 0


def test_no_command_exits_nonzero():
    parser = cli.build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args([])
    assert exc.value.code != 0


def test_dub_parses_url_and_flags_into_namespace():
    parser = cli.build_parser()
    args = parser.parse_args([
        "dub", "https://youtu.be/xxxx", "--voice", "Minh Trang",
        "--target", "en", "--source-lang", "zh-CN", "--skip-video",
    ])
    assert args.url == "https://youtu.be/xxxx"
    assert args.voice == "Minh Trang"
    assert args.target == "en"
    assert args.skip_video is True
    assert args.func is cli._cmd_dub


# --------------------------------------------------------------------- #
# Tham số sai -> exit 2 (không phải lỗi pipeline)

def test_dub_missing_url_and_file_exits_2(monkeypatch, capsys):
    parser = cli.build_parser()
    args = parser.parse_args(["dub"])
    monkeypatch.setattr(cli, "_validate_target", lambda k: MagicMock(key=k))
    monkeypatch.setattr(cli, "_validate_voice", lambda *a, **k: None)
    rc = cli._cmd_dub(args)
    assert rc == 2
    assert "Lỗi tham số" in capsys.readouterr().err


def test_dub_unknown_target_exits_2(capsys):
    parser = cli.build_parser()
    args = parser.parse_args(["dub", "https://youtu.be/xxxx", "--target", "xx-not-real"])
    rc = cli._cmd_dub(args)
    assert rc == 2
    assert "Lỗi tham số" in capsys.readouterr().err


def test_dub_unknown_voice_exits_2_and_does_not_fall_back_silently(monkeypatch, capsys):
    """Bug thật đã audit ở V22: `voices.resolve()` rơi ngầm về giọng khác khi
    tên sai — CLI KHÔNG được kế thừa hành vi đó, phải báo lỗi rõ + thoát 2."""
    parser = cli.build_parser()
    args = parser.parse_args([
        "dub", "https://youtu.be/xxxx", "--voice", "Giọng Không Tồn Tại"])

    fake_voice = MagicMock()
    fake_voice.name = "Minh Trang"
    monkeypatch.setattr("autodub.speech.tts.voices.catalog", lambda *a, **k: [fake_voice])

    rc = cli._cmd_dub(args)
    err = capsys.readouterr().err
    assert rc == 2
    assert "Giọng Không Tồn Tại" in err
    assert "Minh Trang" in err  # liệt kê giọng khả dụng để người dùng sửa ngay


# --------------------------------------------------------------------- #
# Đường thành công / lỗi pipeline (DubPipeline mock — không chạy thật)

def test_dub_success_exits_0_and_prints_report(monkeypatch, capsys):
    parser = cli.build_parser()
    args = parser.parse_args(["dub", "https://youtu.be/xxxx"])

    fake_result = DubResult(status="completed", work_dir="/tmp/x",
                            report={"session_id": "abc"})
    fake_pipeline = MagicMock()
    fake_pipeline.run.return_value = fake_result
    monkeypatch.setattr(cli, "DubPipeline", lambda *a, **k: fake_pipeline)

    rc = cli._cmd_dub(args)
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["status"] == "completed"
    assert out["report"]["session_id"] == "abc"


def test_dub_non_completed_status_exits_1(monkeypatch):
    parser = cli.build_parser()
    args = parser.parse_args(["dub", "https://youtu.be/xxxx"])

    fake_result = DubResult(status="credit_blocked", work_dir="/tmp/x", report={})
    fake_pipeline = MagicMock()
    fake_pipeline.run.return_value = fake_result
    monkeypatch.setattr(cli, "DubPipeline", lambda *a, **k: fake_pipeline)

    assert cli._cmd_dub(args) == 1


def test_dub_pipeline_exception_exits_1(monkeypatch, capsys):
    parser = cli.build_parser()
    args = parser.parse_args(["dub", "https://youtu.be/xxxx"])

    fake_pipeline = MagicMock()
    fake_pipeline.run.side_effect = RuntimeError("mạng lỗi thật")
    monkeypatch.setattr(cli, "DubPipeline", lambda *a, **k: fake_pipeline)

    rc = cli._cmd_dub(args)
    assert rc == 1
    assert "mạng lỗi thật" in capsys.readouterr().err


def test_dub_request_built_from_args(monkeypatch):
    """DubRequest phải phản ánh đúng mọi cờ CLI — khoá field ánh xạ 1-1."""
    parser = cli.build_parser()
    args = parser.parse_args([
        "dub", "https://youtu.be/xxxx", "--target", "en",
        "--bg-mode", "duck", "--bg-duck-db", "-9", "--subtitle-mode", "burn",
        "--resume-dir", "/tmp/resume",
    ])

    captured = {}

    def fake_pipeline_cls(settings, progress=None):
        captured["progress"] = progress
        m = MagicMock()

        def _run(req):
            captured["req"] = req
            return DubResult(status="completed", work_dir="/tmp/x", report={})
        m.run.side_effect = _run
        return m

    monkeypatch.setattr(cli, "DubPipeline", fake_pipeline_cls)
    cli._cmd_dub(args)

    req = captured["req"]
    assert req.target == "en"
    assert req.bg_mode == "duck"
    assert req.bg_duck_db == -9.0
    assert req.subtitle_mode == "burn"
    assert req.resume_dir == "/tmp/resume"


# --------------------------------------------------------------------- #
# mini-spec V26 (Phase G) — --multi-speaker bật diarization_enabled

def test_multi_speaker_flag_enables_diarization(monkeypatch):
    parser = cli.build_parser()
    args = parser.parse_args(["dub", "https://youtu.be/xxxx", "--multi-speaker"])

    captured = {}

    def fake_pipeline_cls(settings, progress=None):
        captured["diarization_enabled"] = settings.diarization_enabled
        m = MagicMock()
        m.run.return_value = DubResult(status="completed", work_dir="/tmp/x", report={})
        return m

    monkeypatch.setattr(cli, "DubPipeline", fake_pipeline_cls)
    cli._cmd_dub(args)
    assert captured["diarization_enabled"] is True


def test_multi_speaker_flag_off_by_default(monkeypatch):
    parser = cli.build_parser()
    args = parser.parse_args(["dub", "https://youtu.be/xxxx"])

    captured = {}

    def fake_pipeline_cls(settings, progress=None):
        captured["diarization_enabled"] = settings.diarization_enabled
        m = MagicMock()
        m.run.return_value = DubResult(status="completed", work_dir="/tmp/x", report={})
        return m

    monkeypatch.setattr(cli, "DubPipeline", fake_pipeline_cls)
    cli._cmd_dub(args)
    assert captured["diarization_enabled"] is False


# --------------------------------------------------------------------- #
# batch

def test_batch_reads_file_and_reports_summary(monkeypatch, tmp_path, capsys):
    lines_file = tmp_path / "urls.txt"
    lines_file.write_text("https://youtu.be/a\nhttps://youtu.be/b\n", encoding="utf-8")

    parser = cli.build_parser()
    args = parser.parse_args(["batch", "--file", str(lines_file)])

    @dataclass
    class _Summary:
        total: int = 2
        success: int = 2
        failed: int = 0
        skipped: int = 0

    captured = {}

    def fake_run_batch(lines, settings, req_template, observer=None,
                       state_path=None, retry_done=False,
                       retry_transient=False, max_retries=2):
        captured["lines"] = lines
        return _Summary()

    monkeypatch.setattr("autodub.batch.run_batch", fake_run_batch)
    rc = cli._cmd_batch(args)
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out == {"total": 2, "success": 2, "failed": 0, "skipped": 0}
    assert "https://youtu.be/a" in captured["lines"]


def test_batch_with_failures_exits_1(monkeypatch, tmp_path):
    lines_file = tmp_path / "urls.txt"
    lines_file.write_text("https://youtu.be/a\n", encoding="utf-8")
    parser = cli.build_parser()
    args = parser.parse_args(["batch", "--file", str(lines_file)])

    @dataclass
    class _Summary:
        total: int = 1
        success: int = 0
        failed: int = 1
        skipped: int = 0

    monkeypatch.setattr("autodub.batch.run_batch",
                        lambda *a, **k: _Summary())
    assert cli._cmd_batch(args) == 1


def test_batch_unknown_voice_exits_2_before_touching_run_batch(monkeypatch, tmp_path):
    lines_file = tmp_path / "urls.txt"
    lines_file.write_text("https://youtu.be/a\n", encoding="utf-8")
    parser = cli.build_parser()
    args = parser.parse_args(["batch", "--file", str(lines_file), "--voice", "Sai Tên"])

    fake_voice = MagicMock()
    fake_voice.name = "Minh Trang"
    monkeypatch.setattr("autodub.speech.tts.voices.catalog", lambda *a, **k: [fake_voice])
    run_batch_mock = MagicMock()
    monkeypatch.setattr("autodub.batch.run_batch", run_batch_mock)

    assert cli._cmd_batch(args) == 2
    run_batch_mock.assert_not_called()


# --------------------------------------------------------------------- #
# mini-spec V23 (Phase F) — cổng chất lượng tự động (--quality-gate)

def _make_quality_report(work_dir, **summary_overrides):
    import json as _json
    import os as _os

    summary = {
        "segments_total": 10, "segments_ok": 10, "segments_shifted": 0,
        "max_shift_s": 0.0, "segments_compressed": 0, "segments_overlapped": 0,
        "total_overlap_s": 0.0, "segments_over_budget": 0,
        "segments_speed_fallback": 0, "segments_postprocess_fallback": 0,
    }
    summary.update(summary_overrides)
    data_dir = _os.path.join(work_dir, "data")
    _os.makedirs(data_dir, exist_ok=True)
    with open(_os.path.join(data_dir, "quality_report.json"), "w", encoding="utf-8") as f:
        _json.dump({"summary": summary}, f)


def test_dub_quality_gate_off_by_default_ignores_bad_report(monkeypatch, tmp_path):
    """Không truyền --quality-gate -> hành vi Y HỆT trước V23 (0 regression)."""
    parser = cli.build_parser()
    args = parser.parse_args(["dub", "https://youtu.be/xxxx"])
    work_dir = str(tmp_path / "session")
    _make_quality_report(work_dir, segments_ok=0, segments_over_budget=10)

    fake_pipeline = MagicMock()
    fake_pipeline.run.return_value = DubResult(status="completed", work_dir=work_dir, report={})
    monkeypatch.setattr(cli, "DubPipeline", lambda *a, **k: fake_pipeline)

    assert cli._cmd_dub(args) == 0


def test_dub_quality_gate_pass_exits_0(monkeypatch, tmp_path, capsys):
    parser = cli.build_parser()
    args = parser.parse_args(["dub", "https://youtu.be/xxxx", "--quality-gate"])
    work_dir = str(tmp_path / "session")
    _make_quality_report(work_dir)  # sạch hoàn toàn

    fake_pipeline = MagicMock()
    fake_pipeline.run.return_value = DubResult(status="completed", work_dir=work_dir, report={})
    monkeypatch.setattr(cli, "DubPipeline", lambda *a, **k: fake_pipeline)

    rc = cli._cmd_dub(args)
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["quality"]["status"] == "pass"


def test_dub_quality_gate_fail_exits_3(monkeypatch, tmp_path, capsys):
    parser = cli.build_parser()
    args = parser.parse_args(["dub", "https://youtu.be/xxxx", "--quality-gate"])
    work_dir = str(tmp_path / "session")
    # 80% câu vượt ngân sách -> vượt ngưỡng mặc định (15%) -> fail
    _make_quality_report(work_dir, segments_ok=2, segments_over_budget=8)

    fake_pipeline = MagicMock()
    fake_pipeline.run.return_value = DubResult(status="completed", work_dir=work_dir, report={})
    monkeypatch.setattr(cli, "DubPipeline", lambda *a, **k: fake_pipeline)

    rc = cli._cmd_dub(args)
    out = json.loads(capsys.readouterr().out)
    assert rc == 3
    assert out["quality"]["status"] == "fail"
    assert out["quality"]["reasons"]


def test_batch_quality_gate_writes_field_without_touching_status(monkeypatch, tmp_path):
    """Constraint V23: field `quality` chỉ ĐƯỢC THÊM — `status` (dùng cho
    resume của run_batch()) phải giữ nguyên y hệt."""
    lines_file = tmp_path / "urls.txt"
    lines_file.write_text("https://youtu.be/a\n", encoding="utf-8")
    output_dir = tmp_path / "out"

    parser = cli.build_parser()
    args = parser.parse_args([
        "batch", "--file", str(lines_file), "--output-dir", str(output_dir),
        "--quality-gate",
    ])

    work_dir = output_dir / "20260101_vi"
    _make_quality_report(str(work_dir), segments_ok=2, segments_over_budget=8)

    import json as _json
    from dataclasses import dataclass as _dataclass

    state_path = output_dir / "batch_state.json"
    output_dir.mkdir(parents=True, exist_ok=True)

    def fake_run_batch(lines, settings, req_template, observer=None,
                       state_path=None, retry_done=False,
                       retry_transient=False, max_retries=2):
        state = {"output_dir": str(output_dir), "videos": [
            {"video_url": "https://youtu.be/a", "status": "success",
             "output_folder": "20260101_vi"},
        ]}
        with open(state_path, "w", encoding="utf-8") as f:
            _json.dump(state, f)

        @_dataclass
        class _S:
            total: int = 1
            success: int = 1
            failed: int = 0
            skipped: int = 0
        return _S()

    monkeypatch.setattr("autodub.batch.run_batch", fake_run_batch)
    cli._cmd_batch(args)

    with open(state_path, encoding="utf-8") as f:
        saved = json.load(f)
    entry = saved["videos"][0]
    assert entry["status"] == "success"  # không đổi
    assert entry["quality"]["status"] == "fail"


# --------------------------------------------------------------------- #
# mini-spec V24 (Phase F) — --retry-transient / --max-retries flow through

def test_batch_retry_flags_flow_through_to_run_batch(monkeypatch, tmp_path):
    lines_file = tmp_path / "urls.txt"
    lines_file.write_text("https://youtu.be/a\n", encoding="utf-8")
    parser = cli.build_parser()
    args = parser.parse_args([
        "batch", "--file", str(lines_file), "--retry-transient",
        "--max-retries", "5",
    ])

    @dataclass
    class _Summary:
        total: int = 1
        success: int = 1
        failed: int = 0
        skipped: int = 0

    captured = {}

    def fake_run_batch(lines, settings, req_template, observer=None,
                       state_path=None, retry_done=False,
                       retry_transient=False, max_retries=2):
        captured["retry_transient"] = retry_transient
        captured["max_retries"] = max_retries
        return _Summary()

    monkeypatch.setattr("autodub.batch.run_batch", fake_run_batch)
    cli._cmd_batch(args)

    assert captured["retry_transient"] is True
    assert captured["max_retries"] == 5


def test_batch_retry_off_by_default(monkeypatch, tmp_path):
    lines_file = tmp_path / "urls.txt"
    lines_file.write_text("https://youtu.be/a\n", encoding="utf-8")
    parser = cli.build_parser()
    args = parser.parse_args(["batch", "--file", str(lines_file)])

    @dataclass
    class _Summary:
        total: int = 1
        success: int = 1
        failed: int = 0
        skipped: int = 0

    captured = {}

    def fake_run_batch(lines, settings, req_template, observer=None,
                       state_path=None, retry_done=False,
                       retry_transient=False, max_retries=2):
        captured["retry_transient"] = retry_transient
        return _Summary()

    monkeypatch.setattr("autodub.batch.run_batch", fake_run_batch)
    cli._cmd_batch(args)

    assert captured["retry_transient"] is False


# --------------------------------------------------------------------- #
# mini-spec V25 (Phase F) — voxdub watch

def test_watch_subcommand_help_exits_zero():
    parser = cli.build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["watch", "--help"])
    assert exc.value.code == 0


def test_watch_requires_input_dir():
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["watch"])  # --input-dir bắt buộc


def test_watch_missing_input_dir_on_disk_exits_2(tmp_path, capsys):
    parser = cli.build_parser()
    args = parser.parse_args([
        "watch", "--input-dir", str(tmp_path / "khong-ton-tai")])
    rc = cli._cmd_watch(args)
    assert rc == 2
    assert "Lỗi tham số" in capsys.readouterr().err


def test_watch_unknown_voice_exits_2_before_starting_loop(monkeypatch, tmp_path):
    parser = cli.build_parser()
    args = parser.parse_args([
        "watch", "--input-dir", str(tmp_path), "--voice", "Sai Tên"])

    fake_voice = MagicMock()
    fake_voice.name = "Minh Trang"
    monkeypatch.setattr("autodub.speech.tts.voices.catalog", lambda *a, **k: [fake_voice])
    watch_forever_mock = MagicMock()
    monkeypatch.setattr("autodub.watch_folder.watch_forever", watch_forever_mock)

    assert cli._cmd_watch(args) == 2
    watch_forever_mock.assert_not_called()


def test_watch_wires_watch_forever_with_correct_args(monkeypatch, tmp_path):
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    output_dir = tmp_path / "out"

    parser = cli.build_parser()
    args = parser.parse_args([
        "watch", "--input-dir", str(input_dir), "--output-dir", str(output_dir),
        "--poll-interval", "3", "--stable-seconds", "1",
    ])

    captured = {}

    def fake_watch_forever(input_dir_arg, pipeline, req_template, state_path,
                           poll_interval_s=10.0, stable_seconds=5.0,
                           failures_log_path=None, stop_event=None):
        captured.update(locals())

    monkeypatch.setattr("autodub.watch_folder.watch_forever", fake_watch_forever)
    monkeypatch.setattr("signal.signal", lambda *a, **k: None)

    rc = cli._cmd_watch(args)

    assert rc == 0
    assert captured["input_dir_arg"] == str(input_dir)
    assert captured["poll_interval_s"] == 3.0
    assert captured["stable_seconds"] == 1.0
    assert captured["req_template"].output_dir == str(output_dir)
    assert os.path.isdir(output_dir)  # tự tạo nếu chưa có


def test_watch_defaults_output_dir_from_target(monkeypatch, tmp_path):
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    parser = cli.build_parser()
    args = parser.parse_args(["watch", "--input-dir", str(input_dir)])

    captured = {}

    def fake_watch_forever(input_dir_arg, pipeline, req_template, state_path,
                           poll_interval_s=10.0, stable_seconds=5.0,
                           failures_log_path=None, stop_event=None):
        captured["output_dir"] = req_template.output_dir

    monkeypatch.setattr("autodub.watch_folder.watch_forever", fake_watch_forever)
    monkeypatch.setattr("signal.signal", lambda *a, **k: None)

    cli._cmd_watch(args)
    assert captured["output_dir"]  # không rỗng — DubPipeline.default_output_dir() thật


# --------------------------------------------------------------------- #
# console-script wiring

def test_console_script_registered_in_pyproject():
    import pathlib
    import tomllib

    root = pathlib.Path(__file__).resolve().parent.parent
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["scripts"]["voxdub"] == "autodub.cli:main"
