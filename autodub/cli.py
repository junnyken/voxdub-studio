"""CLI headless cho pipeline dub — mini-spec V22 (docs/PLAN.md, Phase F).

Lớp vỏ MỎNG gọi thẳng vào :class:`autodub.pipeline.DubPipeline` và
:func:`autodub.batch.run_batch` đã có sẵn (không viết lại logic pipeline
ở đây) — mục đích DUY NHẤT là mở 1 đường vào không cần Qt/GUI, để các
mini-spec sau (V23 cổng chất lượng, V24 retry/watchdog, V25 watch-folder)
tự động hoá được từ terminal/cron/script.

Import module này KHÔNG được kéo theo ``PySide6``/``autodub_gui`` — xem
test cách ly trong ``tests/test_cli.py``.

Ví dụ::

    voxdub dub https://youtu.be/xxxx --voice "Minh Trang" --target vi
    voxdub batch --file danh_sach.txt --state-path batch_state.json

Mã thoát: 0 = thành công; 1 = lỗi pipeline (hoặc có video batch thất bại);
2 = lỗi tham số dòng lệnh (bao gồm tên giọng không có trong danh mục);
3 = ``--quality-gate`` bật và video "fail" ngưỡng chất lượng (chỉ với
``dub`` — ``batch`` ghi verdict vào ``batch_state.json`` thay vì đổi exit
code, xem mini-spec V23 trong docs/PLAN.md).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from autodub.batch import DEFAULT_MAX_RETRIES
from autodub.config import Settings
from autodub.pipeline import DubPipeline, DubRequest
from autodub.progress import ProgressEvent
from autodub.quality_gate import QualityThresholds, evaluate as evaluate_quality


class CliArgError(ValueError):
    """Tham số dòng lệnh không hợp lệ — CLI thoát mã 2, không phải lỗi pipeline."""


def _validate_target(target_key: str):
    """Resolve ``--target`` sớm — get_target() raise ValueError rõ ràng nếu
    khoá sai, thay vì để nó rơi xuống tận lúc pipeline chạy (exit 1 lẫn với
    lỗi pipeline thật, khó phân biệt với lỗi gõ sai tham số)."""
    from autodub.languages import get_target
    return get_target(target_key)


def _validate_voice(voice: str | None, target, settings: Settings) -> None:
    """Chặn tên giọng sai NGAY tại CLI thay vì để pipeline âm thầm đổi giọng.

    ``autodub.speech.tts.voices.resolve()`` cố ý rơi ngầm về giọng khác khi
    tên không khớp danh mục — đúng cho GUI (người dùng thấy ngay, sửa lại
    bằng picker), nhưng là bẫy thật cho CLI/cron: gõ sai tên trong 1 script
    chạy định kỳ có thể âm thầm tạo hàng loạt video sai giọng nhiều tuần
    không ai biết. CLI validate tường minh, KHÔNG gọi ``resolve()``.
    """
    if not voice:
        return
    from autodub.speech.tts import voices

    names = {v.name for v in voices.catalog(settings, target)}
    if voice not in names:
        raise CliArgError(
            f"Giọng {voice!r} không có trong danh mục của ngôn ngữ đích "
            f"{target.key!r}. Các giọng khả dụng: {', '.join(sorted(names)) or '(rỗng)'}")


def _add_dub_request_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--voice", default=None, help="Tên giọng đọc (khớp danh mục)")
    parser.add_argument("--target", default="vi", help="Ngôn ngữ đích (mặc định: vi)")
    parser.add_argument("--source-lang", default="zh-CN",
                        help="Ngôn ngữ nguồn video (mặc định: zh-CN)")
    parser.add_argument("--bg-mode", default="demucs",
                        choices=["demucs", "duck", "none"],
                        help="Cách xử lý nhạc nền (mặc định: demucs)")
    parser.add_argument("--bg-duck-db", type=float, default=-12.0)
    parser.add_argument("--skip-video", action="store_true",
                        help="Chỉ xuất audio, bỏ qua ghép video")
    parser.add_argument("--subtitle-mode", default="none",
                        choices=["none", "soft", "burn"])
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--resume-dir", default=None,
                        help="Chạy tiếp 1 work_dir dở dang có sẵn")
    parser.add_argument("--json", action="store_true",
                        help="In tiến trình dạng NDJSON (1 dòng JSON/sự kiện) ra stderr")
    parser.add_argument("--quality-gate", action="store_true",
                        help="Đọc quality_report.json sau khi chạy xong, áp "
                             "ngưỡng pass/warn/fail (mini-spec V23)")
    parser.add_argument("--multi-speaker", action="store_true",
                        help="Tự tách giọng theo người nói, gán mỗi người 1 "
                             "giọng riêng (mini-spec V26 — cần cài trước qua "
                             "scripts/setup_diarization.py; gán tự động "
                             "round-robin, không có UI để chọn tay)")
    parser.add_argument("--lipsync", action="store_true",
                        help="Đồng bộ khẩu hình AI theo giọng đã lồng tiếng "
                             "(mini-spec V32b — GPU NVIDIA BẮT BUỘC, cần cài "
                             "trước qua scripts/setup_lipsync.py; phạm vi "
                             "hiện tại CHỈ 1 khuôn mặt/video ngắn, tự động "
                             "bỏ qua bước này nếu chưa cài/không đạt điều "
                             "kiện, không làm hỏng cả lượt dub)")


def _progress_fn(as_json: bool):
    def _emit(event: ProgressEvent) -> None:
        if as_json:
            print(json.dumps({
                "step": event.step, "status": event.status, "detail": event.detail,
                "current": event.current, "total": event.total,
            }, ensure_ascii=False), file=sys.stderr, flush=True)
        else:
            suffix = f" ({event.current}/{event.total})" if event.total else ""
            detail = f" — {event.detail}" if event.detail else ""
            print(f"[{event.step}] {event.status}{suffix}{detail}",
                 file=sys.stderr, flush=True)
    return _emit


def _load_quality_report(work_dir: str) -> dict:
    from autodub.workdir import data_path

    path = data_path(work_dir, "quality_report.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _cmd_dub(args: argparse.Namespace) -> int:
    settings = Settings.load()
    if args.multi_speaker:
        settings.diarization_enabled = True
    try:
        target = _validate_target(args.target)
        _validate_voice(args.voice, target, settings)
    except (CliArgError, ValueError) as e:
        print(f"Lỗi tham số: {e}", file=sys.stderr)
        return 2

    if not args.url and not args.file:
        print("Lỗi tham số: cần --file hoặc URL", file=sys.stderr)
        return 2

    pipeline = DubPipeline(settings, progress=_progress_fn(args.json))
    req = DubRequest(
        url=args.url,
        file_path=args.file,
        source_lang=args.source_lang,
        voice=args.voice,
        bg_mode=args.bg_mode,
        bg_duck_db=args.bg_duck_db,
        skip_video=args.skip_video,
        output_dir=args.output_dir,
        resume_dir=args.resume_dir,
        subtitle_mode=args.subtitle_mode,
        target=args.target,
        lipsync=args.lipsync,
    )
    try:
        result = pipeline.run(req)
    except Exception as e:  # noqa: BLE001 — lỗi pipeline thật, báo rõ rồi thoát 1
        print(f"Lỗi pipeline: {e}", file=sys.stderr)
        return 1

    output = {"status": result.status, "work_dir": result.work_dir,
             "report": result.report}
    if result.status != "completed":
        print(json.dumps(output, ensure_ascii=False))
        return 1

    if args.quality_gate:
        thresholds = QualityThresholds.from_settings(settings)
        quality_report = _load_quality_report(result.work_dir)
        verdict = evaluate_quality(quality_report, thresholds)
        output["quality"] = verdict.to_dict()
        print(json.dumps(output, ensure_ascii=False))
        return 3 if not verdict.passed else 0

    print(json.dumps(output, ensure_ascii=False))
    return 0


def _apply_quality_gate_to_batch_state(state_path: str, output_dir: str | None,
                                       target, settings: Settings) -> None:
    """Ghi THÊM field ``quality`` vào mỗi video ``success`` trong
    ``batch_state.json`` — KHÔNG đổi field ``status`` hiện có (V23
    Constraint: logic resume của ``run_batch()`` phải tiếp tục đọc đúng
    ``status`` như trước, kể cả khi cờ này không được dùng ở lần chạy kế).
    """
    from autodub.utils import save_json_atomic

    try:
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        return

    output_base = output_dir or DubPipeline(settings).default_output_dir(target)
    thresholds = QualityThresholds.from_settings(settings)
    changed = False
    for entry in state.get("videos", []):
        if entry.get("status") != "success" or not entry.get("output_folder"):
            continue
        work_dir = os.path.join(output_base, entry["output_folder"])
        verdict = evaluate_quality(_load_quality_report(work_dir), thresholds)
        entry["quality"] = verdict.to_dict()
        changed = True

    if changed:
        save_json_atomic(state, state_path)


def _cmd_cloud_batch(args: argparse.Namespace) -> int:
    """Đẩy batch lên máy chủ thay vì chạy trên máy này (mini-spec V51).

    Tách hẳn `_cmd_batch`: khác đường xác thực (API key, không phải token
    thiết bị), khác đơn vị tính tiền (phút video, không phải Vox theo
    segment), và KHÔNG chạy pipeline nào trên máy này cả.
    """
    from pathlib import Path

    from autodub.cloud_batch import format_report, run_cloud_batch
    from autodub.cloud_dub import CloudDubError, is_configured

    if not is_configured():
        print(
            "Chưa dùng được lồng tiếng trên máy chủ: cần CẢ VOXDUB_API_URL "
            "lẫn VOXDUB_API_KEY.\n"
            "Đây là chế độ khác hẳn 'voxdub batch' (chạy trên máy bạn) — "
            "không tự chuyển sang chế độ đó để bạn khỏi bất ngờ về nơi "
            "video được xử lý.",
            file=sys.stderr,
        )
        return 2

    source = Path(args.input)
    if not source.exists():
        print(f"Không thấy: {source}", file=sys.stderr)
        return 2

    try:
        report = run_cloud_batch(
            source,
            Path(args.output_dir),
            source_lang=args.source_lang,
            target_lang=args.target,
            voice=args.voice or "",
            bg_mode=args.bg_mode,
            poll_interval=args.poll_interval,
            retry_done=args.retry_done,
            queue_ahead=args.queue_ahead,
            on_progress=lambda m: print(m, flush=True),
        )
    except CloudDubError as err:
        print(f"Lỗi máy chủ: {err}", file=sys.stderr)
        return 1

    print(format_report(report))
    # Còn mục hỏng, hoặc dừng sớm vì hết quota → mã thoát khác 0 để script
    # gọi nó biết mà dừng dây chuyền, đừng coi như đã xong.
    return 1 if (report.failed or report.stopped_early) else 0


def _cmd_batch(args: argparse.Namespace) -> int:
    from autodub.batch import STATE_FILENAME, run_batch

    settings = Settings.load()
    if args.multi_speaker:
        settings.diarization_enabled = True
    try:
        target = _validate_target(args.target)
        _validate_voice(args.voice, target, settings)
    except (CliArgError, ValueError) as e:
        print(f"Lỗi tham số: {e}", file=sys.stderr)
        return 2

    if args.file:
        with open(args.file, encoding="utf-8") as f:
            lines = f.read()
    else:
        lines = sys.stdin.read()

    req_template = DubRequest(
        source_lang=args.source_lang,
        voice=args.voice,
        bg_mode=args.bg_mode,
        bg_duck_db=args.bg_duck_db,
        skip_video=args.skip_video,
        output_dir=args.output_dir,
        subtitle_mode=args.subtitle_mode,
        target=args.target,
        lipsync=args.lipsync,
    )

    def observer(index, total, item, status, detail):
        if args.json:
            print(json.dumps({
                "step": "batch", "status": status, "detail": detail,
                "current": index + 1, "total": total, "url": item.label,
            }, ensure_ascii=False), file=sys.stderr, flush=True)
        else:
            print(f"[{index + 1}/{total}] {item.label}: {status} {detail}",
                 file=sys.stderr, flush=True)

    # Resolve tường minh (thay vì để run_batch() tự tính ngầm) — cần biết
    # CHÍNH XÁC nơi state file nằm để đọc lại sau khi áp cổng chất lượng.
    resolved_state_path = args.state_path or os.path.join(
        args.output_dir or settings.output_dir, STATE_FILENAME)

    summary = run_batch(
        lines, settings, req_template, observer=observer,
        state_path=resolved_state_path, retry_done=args.retry_done,
        retry_transient=args.retry_transient,
        max_retries=(args.max_retries if args.max_retries is not None
                    else DEFAULT_MAX_RETRIES))

    if args.quality_gate:
        _apply_quality_gate_to_batch_state(
            resolved_state_path, args.output_dir, target, settings)

    print(json.dumps({"total": summary.total, "success": summary.success,
                      "failed": summary.failed, "skipped": summary.skipped}))
    return 0 if summary.failed == 0 else 1


def _cmd_watch(args: argparse.Namespace) -> int:
    import signal
    import threading

    from autodub.failures_log import failures_path
    from autodub.watch_folder import STATE_FILENAME, watch_forever

    settings = Settings.load()
    try:
        target = _validate_target(args.target)
        _validate_voice(args.voice, target, settings)
    except (CliArgError, ValueError) as e:
        print(f"Lỗi tham số: {e}", file=sys.stderr)
        return 2

    if not os.path.isdir(args.input_dir):
        print(f"Lỗi tham số: thư mục theo dõi không tồn tại: {args.input_dir}",
             file=sys.stderr)
        return 2

    # mini-spec V25: state bền nằm ở OUTPUT dir (không phải input_dir) —
    # discover_ready_files() vẫn tự loại các tên file bookkeeping đã biết
    # (STATE_FILENAME/failures.jsonl/batch_state.json) như 1 lớp an toàn
    # thứ 2, phòng khi input_dir/output_dir bị trỏ trùng nhau.
    output_dir = args.output_dir or DubPipeline(settings).default_output_dir(target)
    os.makedirs(output_dir, exist_ok=True)
    state_path = os.path.join(output_dir, STATE_FILENAME)

    req_template = DubRequest(
        source_lang=args.source_lang, voice=args.voice, bg_mode=args.bg_mode,
        bg_duck_db=args.bg_duck_db, skip_video=args.skip_video,
        subtitle_mode=args.subtitle_mode, output_dir=output_dir, target=args.target,
    )
    pipeline = DubPipeline(settings, progress=_progress_fn(args.json))

    stop_event = threading.Event()

    def _handle_sigint(signum, frame):
        # Handler tuỳ biến CHỈ đặt cờ, không raise KeyboardInterrupt — vì
        # vậy 1 lượt pipeline.run() đang dở KHÔNG bị cắt ngang, nó chạy tiếp
        # tới khi xong hẳn rồi watch_forever() mới dừng ở lượt kiểm cờ kế
        # tiếp (an toàn, không mất tiến trình dở dang, nhưng không tức thời
        # — có thể phải chờ đúng bằng thời gian dub xong video hiện tại).
        # Bấm Ctrl+C LẦN 2 (trong lúc đang chờ) thoát ngay lập tức — không
        # cần đợi hết video hiện tại nếu người dùng thật sự muốn dừng gấp.
        if stop_event.is_set():
            print("\nThoát ngay (bấm lần 2) — video đang dở có thể chưa "
                 "hoàn tất, lần chạy watch kế tiếp sẽ tự nhận ra và xử lý "
                 "tiếp.", file=sys.stderr)
            os._exit(130)  # 128+SIGINT, quy ước exit code chuẩn cho Ctrl+C
        print("\nĐang dừng theo dõi (chờ xong video đang dub — bấm Ctrl+C "
             "lần nữa để thoát ngay)...", file=sys.stderr)
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_sigint)
    print(f"Đang theo dõi {args.input_dir} — Ctrl+C để dừng.", file=sys.stderr)
    watch_forever(
        args.input_dir, pipeline, req_template, state_path,
        poll_interval_s=args.poll_interval, stable_seconds=args.stable_seconds,
        failures_log_path=failures_path(state_path), stop_event=stop_event,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="voxdub",
                                     description="VoxDub Studio — lồng tiếng tự động, chạy không giao diện")
    sub = parser.add_subparsers(dest="command", required=True)

    dub = sub.add_parser("dub", help="Lồng tiếng 1 video (URL hoặc file)")
    dub.add_argument("url", nargs="?", default=None, help="URL video")
    dub.add_argument("--file", default=None, help="File video local (thay cho URL)")
    _add_dub_request_args(dub)
    dub.set_defaults(func=_cmd_dub)

    batch = sub.add_parser("batch", help="Lồng tiếng hàng loạt từ danh sách dòng")
    batch.add_argument("--file", default=None,
                       help="File danh sách URL (mỗi dòng 1 video); mặc định đọc từ stdin")
    batch.add_argument("--state-path", default=None)
    batch.add_argument("--retry-done", action="store_true",
                       help="Chạy lại cả video đã đánh dấu success")
    batch.add_argument("--retry-transient", action="store_true",
                       help="Tự thử lại NGAY video lỗi tạm thời (mất mạng, "
                            "subprocess treo...) trong cùng lượt batch này "
                            "(mini-spec V24, mặc định TẮT)")
    batch.add_argument("--max-retries", type=int, default=None,
                       help="Số lần thử lại tối đa mỗi video (mặc định: "
                            f"{DEFAULT_MAX_RETRIES}, chỉ có nghĩa cùng "
                            "--retry-transient)")
    _add_dub_request_args(batch)
    batch.set_defaults(func=_cmd_batch)

    cloud = sub.add_parser(
        "cloud-batch",
        help="Đẩy hàng loạt video lên MÁY CHỦ lồng tiếng (mini-spec V51) — "
             "không chạy gì trên máy này, cần VOXDUB_API_KEY")
    cloud.add_argument("--input", required=True,
                       help="1 file video, hoặc thư mục chứa nhiều video")
    cloud.add_argument("--output-dir", required=True, help="Thư mục nhận kết quả")
    cloud.add_argument("--source-lang", default="en-US",
                       help="Ngôn ngữ nguồn: nhận khoá ngắn (vi) HOẶC BCP-47 (vi-VN)")
    cloud.add_argument("--target", default="vi",
                       help="Ngôn ngữ đích: CHỈ nhận khoá ngắn, vd vi")
    cloud.add_argument("--voice", default=None, help="Tên giọng đọc (tuỳ chọn)")
    cloud.add_argument("--bg-mode", default="none", choices=["none", "demucs"],
                       help="Giữ nhạc nền gốc bằng Demucs hay bỏ (mặc định: none)")
    cloud.add_argument("--poll-interval", type=float, default=5.0,
                       help="Giây giữa mỗi lượt hỏi trạng thái job (mặc định: 5)")
    cloud.add_argument("--retry-done", action="store_true",
                       help="Chạy lại cả video đã đánh dấu xong trong lượt trước")
    cloud.add_argument("--queue-ahead", type=int, default=2,
                       help="Số job giữ sẵn trong hàng đợi máy chủ (mini-spec "
                            "V52, mặc định 2) — nộp trước để worker không nằm "
                            "không giữa 2 video. Đặt 1 = chạy tuần tự như cũ. "
                            "Đừng đặt cao: mỗi job chờ đã giữ chỗ quota")
    cloud.set_defaults(func=_cmd_cloud_batch)

    watch = sub.add_parser(
        "watch", help="Theo dõi 1 thư mục, tự dub video mới xuất hiện "
                      "(mini-spec V25, chạy dài hạn tới khi Ctrl+C)")
    watch.add_argument("--input-dir", required=True, help="Thư mục theo dõi video mới")
    watch.add_argument("--output-dir", default=None,
                       help="Thư mục kết quả (mặc định theo target, xem 'dub')")
    watch.add_argument("--poll-interval", type=float, default=10.0,
                       help="Giây giữa mỗi lượt quét thư mục (mặc định: 10)")
    watch.add_argument("--stable-seconds", type=float, default=5.0,
                       help="File phải giữ nguyên kích thước bấy nhiêu giây "
                            "liên tục mới coi là ghi xong (mặc định: 5)")
    watch.add_argument("--voice", default=None, help="Tên giọng đọc (khớp danh mục)")
    watch.add_argument("--target", default="vi", help="Ngôn ngữ đích (mặc định: vi)")
    watch.add_argument("--source-lang", default="zh-CN",
                       help="Ngôn ngữ nguồn video (mặc định: zh-CN)")
    watch.add_argument("--bg-mode", default="demucs",
                       choices=["demucs", "duck", "none"])
    watch.add_argument("--bg-duck-db", type=float, default=-12.0)
    watch.add_argument("--skip-video", action="store_true")
    watch.add_argument("--subtitle-mode", default="none",
                       choices=["none", "soft", "burn"])
    watch.add_argument("--json", action="store_true",
                       help="In tiến trình dạng NDJSON ra stderr")
    watch.set_defaults(func=_cmd_watch)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
