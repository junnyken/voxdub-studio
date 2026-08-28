"""Cổng kiểm TRƯỚC KHI PHÁT HÀNH: chạy một lượt dub THẬT rồi soi bằng chứng.

Vì sao có tệp này (mini-spec C45): điểm yếu số 1 của dự án là **không có máy
Windows nào kiểm thử** — mọi bản phát hành đều do người dùng cuối phát hiện lỗi
(FEATURES §5.1, chuỗi V73–V87 và C29–C43 đều đến từ ảnh chụp màn hình của chủ
dự án). CI hiện chỉ chạy test đơn vị trên Linux rồi **phát hành thẳng**: không
ai chạy thử cái vừa đóng gói.

Bộ canh này khác test đơn vị ở chỗ nó **chạy thật**: tải/đọc video, nghe bằng
Whisper, rồi dừng ở bước dịch (đường dịch TAY — không cần máy chủ, không tốn
Vox), và soi những thứ chỉ lượt chạy thật mới lộ ra:

* Bước nghe có chết vì ngôn ngữ nguồn rỗng không (lỗi thật C44: faster-whisper
  ném ValueError với chuỗi rỗng, chỉ lộ ở đường in-process).
* Ngôn ngữ máy NGHE RA có đi tiếp vào các bước sau không, hay rơi về rỗng
  (lỗi thật C44: mã ngôn ngữ chỉ được ghi nhật ký rồi vứt).
* Lời nhắc dịch giao cho người dùng có gọi đúng tên ngôn ngữ không, hay để lại
  một khoảng trắng giữa câu.

Dùng:
    python scripts/kiem_chay_that.py --video tap01_clip.mp4
    python scripts/kiem_chay_that.py --video x.mp4 --python .venv-whisper/Scripts/python.exe

Mã thoát khác 0 = KHÔNG được phát hành.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

GOC = Path(__file__).resolve().parents[1]


class Hong(Exception):
    """Một mục kiểm không đạt — thông điệp phải nói việc thật phải làm."""


def _chay_dub(video: Path, thu_muc_ra: Path, python_exe: str,
              timeout_s: int) -> subprocess.CompletedProcess:
    """Chạy một lượt dub, cố ý dừng ở bước dịch tay."""
    env = dict(os.environ)
    env.update({
        # Dịch TAY: không gọi máy chủ, không tốn Vox, và vẫn ghi ra đúng lời
        # nhắc mà người dùng nhận được.
        "TRANSLATE_MODE": "manual",
        "VOXDUB_API_URL": "",
        "TRANSLATE_LOCAL_ENABLED": "0",
        "TRANSLATE_ANALYSIS": "0",
        # Model nhỏ nhất: bộ canh này kiểm ĐƯỜNG CHẠY, không chấm chất lượng
        # nghe. Máy CI không có GPU.
        "WHISPER_MODEL": env.get("WHISPER_MODEL", "tiny"),
        "ASR_ENGINE": "whisper",
        "QT_QPA_PLATFORM": "offscreen",
    })
    lenh = [python_exe, "-m", "autodub.cli", "dub",
            "--file", str(video),
            "--source-lang", "auto",     # đúng ca người dùng bật "tự nhận ngôn ngữ"
            "--bg-mode", "none",         # bỏ Demucs: không liên quan, rất nặng
            "--subtitle-mode", "none",
            "--skip-video",
            "--output-dir", str(thu_muc_ra)]
    return subprocess.run(lenh, cwd=str(GOC), env=env, capture_output=True,
                          text=True, timeout=timeout_s, errors="replace")


def _thu_muc_lam_viec(thu_muc_ra: Path) -> Path:
    ung_vien = [p for p in thu_muc_ra.rglob("data") if p.is_dir()]
    if not ung_vien:
        raise Hong(f"Không thấy thư mục dự án nào dưới {thu_muc_ra} — "
                   "lượt chạy đổ trước cả bước nghe.")
    return max(ung_vien, key=lambda p: p.stat().st_mtime).parent


def kiem(video: Path, python_exe: str, timeout_s: int, giu_lai: bool) -> list[str]:
    """Trả về danh sách dòng báo cáo; ném :class:`Hong` khi có mục không đạt."""
    bao_cao: list[str] = []
    tam = Path(tempfile.mkdtemp(prefix="voxdub_kiem_"))
    try:
        kq = _chay_dub(video, tam, python_exe, timeout_s)
        duoi = (kq.stdout or "") + (kq.stderr or "")

        # 1. Bước nghe phải sống. Lỗi C44 rơi đúng ở đây với ngôn ngữ rỗng.
        if "is not a valid language code" in duoi:
            raise Hong("Bước nghe chết vì mã ngôn ngữ rỗng — faster-whisper chỉ "
                       "tự nhận dạng khi tham số là None. Xem "
                       "`_transcribe_whisper` trong autodub/speech/transcriber.py.")

        work = _thu_muc_lam_viec(tam)
        bao_cao.append(f"thư mục dự án: {work.name}")

        transcript = work / "data" / "transcript_original.json"
        if not transcript.is_file():
            raise Hong("Không có transcript_original.json — bước nghe không chạy "
                       f"xong. 400 ký tự cuối của nhật ký:\n{duoi[-400:]}")
        cau = json.loads(transcript.read_text(encoding="utf-8"))
        if not cau:
            raise Hong("Bản chép lời rỗng — bộ nghe không nghe ra câu nào.")
        bao_cao.append(f"nghe được {len(cau)} câu")

        # 2. Ngôn ngữ máy NGHE RA phải được ghi lại, kèm độ tin cậy (C44).
        moc = work / "data" / ".asr_lang"
        if not moc.is_file():
            raise Hong("Thiếu tệp .asr_lang — ngôn ngữ nguồn không được ghi lại, "
                       "nên lượt chạy tiếp sẽ lại rơi về nguồn rỗng.")
        phan = moc.read_text(encoding="utf-8").strip().split()
        if not phan or not phan[0]:
            raise Hong("Tệp .asr_lang RỖNG — máy nghe ra ngôn ngữ nhưng không ai "
                       "ghi lại (đúng lỗi C44: mã ngôn ngữ chỉ vào nhật ký rồi vứt).")
        ma = phan[0]
        import re as _re
        if not _re.match(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})?$", ma):
            raise Hong(f"Tệp .asr_lang chứa {ma!r} — không phải mã ngôn ngữ. "
                       "Nhiều khả năng ngôn ngữ nguồn rỗng và chỉ có độ tin cậy "
                       "được ghi, nên lượt sau sẽ đọc con số đó làm tên ngôn ngữ.")
        tin_cay = float(phan[1]) if len(phan) > 1 else 0.0
        if tin_cay <= 0:
            raise Hong(f"Ngôn ngữ '{ma}' không kèm độ tin cậy — bước quyết định "
                       "'có bỏ hẳn khâu dịch không' sẽ mất căn cứ.")
        bao_cao.append(f"ngôn ngữ máy nghe ra: {ma} ({tin_cay:.0%})")

        # 3. Lời nhắc dịch giao cho người dùng phải gọi ĐÚNG TÊN ngôn ngữ.
        goi_y = work / "TRANSLATE_PENDING.txt"
        if not goi_y.is_file():
            raise Hong("Không có TRANSLATE_PENDING.txt — đường dịch tay không "
                       "chạy tới nơi, người chọn dịch ngoại tuyến sẽ mắc kẹt.")
        noi_dung = goi_y.read_text(encoding="utf-8")
        if "transcript from  to" in noi_dung:
            raise Hong("Lời nhắc dịch để lại KHOẢNG TRẮNG thay cho tên ngôn ngữ "
                       "nguồn — đúng lỗi C44 đã sửa, nay tái phát.")
        if "from auto to" in noi_dung:
            raise Hong("Lời nhắc dịch ghi nguyên chữ 'auto' làm tên ngôn ngữ.")
        if "READING THE SOURCE" not in noi_dung:
            raise Hong("Lời nhắc dịch thiếu khối luật đọc hiểu nguồn (C44).")
        bao_cao.append("lời nhắc dịch: có tên ngôn ngữ + luật đọc hiểu nguồn")

        # 4. Lượt chạy phải dừng ĐÚNG chỗ, không phải đổ vì lỗi.
        if kq.returncode != 0 and "TRANSLATE_PENDING" not in duoi:
            raise Hong(f"Lượt chạy đổ (mã {kq.returncode}). 400 ký tự cuối:\n"
                       f"{duoi[-400:]}")
        return bao_cao
    finally:
        if giu_lai:
            print(f"(giữ lại thư mục thử: {tam})")
        else:
            import shutil
            shutil.rmtree(tam, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", default="tap01_clip.mp4",
                    help="video ngắn để chạy thử (mặc định: tap01_clip.mp4 trong repo)")
    ap.add_argument("--python", default=sys.executable,
                    help="python dùng để chạy autodub.cli")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--giu-lai", action="store_true",
                    help="giữ thư mục thử để soi khi hỏng")
    args = ap.parse_args()

    video = Path(args.video)
    if not video.is_absolute():
        video = GOC / video
    if not video.is_file():
        print(f"!! Không thấy video {video}", file=sys.stderr)
        return 2

    print(f"Chạy thử một lượt dub: {video.name}")
    try:
        for dong in kiem(video, args.python, args.timeout, args.giu_lai):
            print(f"  [ok] {dong}")
    except Hong as e:
        print(f"\n  [HỎNG] {e}", file=sys.stderr)
        print("\nKẾT LUẬN: KHÔNG phát hành bản này.", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        print(f"\n  [HỎNG] Quá {args.timeout}s mà lượt chạy chưa xong.",
              file=sys.stderr)
        return 1
    print("\nKẾT LUẬN: lượt chạy thật đi qua bước nghe và tới bước dịch, "
          "ngôn ngữ nguồn đúng là thứ máy nghe ra.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
