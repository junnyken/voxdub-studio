"""CLI dịch 1 file phụ đề rời (`.srt`/`.vtt`) — mini-spec V14 (docs/PLAN.md).

Ví dụ:
    python scripts/translate_subtitle.py phim.srt --source eng_Latn --target vie_Latn
    python scripts/translate_subtitle.py phim.srt --source eng_Latn --target vie_Latn --mode saas
    python scripts/translate_subtitle.py --list-languages | grep -i french

Ngôn ngữ nhận vào là mã FLORES-200 (KHÔNG phải BCP-47) — xem
`autodub/text/flores200.py` cho bảng đầy đủ, hoặc chạy `--list-languages`.
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autodub.config import Settings  # noqa: E402
from autodub.text.flores200 import (  # noqa: E402
    FLORES200_LANGUAGES, VERIFIED_QUALITY_CODES, is_known_flores_code,
)
from autodub.text.subtitle_translate import (  # noqa: E402
    SubtitleTranslateError, translate_subtitle_file_local,
    translate_subtitle_file_saas,
)


def _print_languages() -> None:
    for code, name in sorted(FLORES200_LANGUAGES.items(), key=lambda kv: kv[1]):
        verified = " (đã kiểm chứng chất lượng)" if code in VERIFIED_QUALITY_CODES else ""
        print(f"{code}\t{name}{verified}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", nargs="?", help="File .srt/.vtt cần dịch")
    parser.add_argument("--source", help="Mã FLORES-200 ngôn ngữ nguồn (vd eng_Latn)")
    parser.add_argument("--target", help="Mã FLORES-200 ngôn ngữ đích (vd vie_Latn)")
    parser.add_argument("--mode", choices=["local", "saas"], default="local",
                         help="local = NLLB offline (mặc định, miễn phí); "
                              "saas = qua máy chủ cấu hình VOXDUB_API_URL (tốn Vox)")
    parser.add_argument("--list-languages", action="store_true",
                         help="In toàn bộ mã FLORES-200 hỗ trợ rồi thoát")
    args = parser.parse_args()

    if args.list_languages:
        _print_languages()
        return 0

    if not args.input or not args.source or not args.target:
        parser.error("cần input, --source và --target (hoặc dùng --list-languages)")

    for label, code in (("--source", args.source), ("--target", args.target)):
        if not is_known_flores_code(code):
            print(f"Lỗi: {label} {code!r} không phải mã FLORES-200 hợp lệ. "
                  f"Xem --list-languages.", file=sys.stderr)
            return 1
        if code not in VERIFIED_QUALITY_CODES:
            print(f"Cảnh báo: chất lượng dịch cho {code!r} CHƯA được kiểm chứng "
                  f"thật (chỉ vie_Latn/eng_Latn đã live-verify) — xem docs/PLAN.md V14.",
                  file=sys.stderr)

    try:
        if args.mode == "local":
            result = translate_subtitle_file_local(
                args.input, args.source, args.target, Settings())
        else:
            result = translate_subtitle_file_saas(
                args.input, args.source, args.target,
                job_id=f"sub-{uuid.uuid4().hex}")
    except SubtitleTranslateError as e:
        print(f"Lỗi: {e}", file=sys.stderr)
        return 1

    print(f"Đã dịch {result.cue_count} dòng -> {result.output_path}")
    if result.skipped_block_count:
        print(f"Bỏ qua {result.skipped_block_count} khối hỏng trong file gốc.")
    if result.credit_charged:
        print(f"Đã trừ {result.credit_charged} Vox (số dư còn lại: {result.balance_after}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
