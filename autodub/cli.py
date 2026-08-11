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
2 = lỗi tham số dòng lệnh (bao gồm tên giọng không có trong danh mục).
"""
from __future__ import annotations

import argparse
import json
import sys

from autodub.config import Settings
from autodub.pipeline import DubPipeline, DubRequest
from autodub.progress import ProgressEvent


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


def _cmd_dub(args: argparse.Namespace) -> int:
    settings = Settings.load()
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
    )
    try:
        result = pipeline.run(req)
    except Exception as e:  # noqa: BLE001 — lỗi pipeline thật, báo rõ rồi thoát 1
        print(f"Lỗi pipeline: {e}", file=sys.stderr)
        return 1

    print(json.dumps({"status": result.status, "work_dir": result.work_dir,
                      "report": result.report}, ensure_ascii=False))
    return 0 if result.status == "completed" else 1


def _cmd_batch(args: argparse.Namespace) -> int:
    from autodub.batch import run_batch

    settings = Settings.load()
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

    summary = run_batch(lines, settings, req_template, observer=observer,
                        state_path=args.state_path, retry_done=args.retry_done)
    print(json.dumps({"total": summary.total, "success": summary.success,
                      "failed": summary.failed, "skipped": summary.skipped}))
    return 0 if summary.failed == 0 else 1


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
    _add_dub_request_args(batch)
    batch.set_defaults(func=_cmd_batch)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
