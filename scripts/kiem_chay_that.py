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

**Chặng 2 (`--den-cuoi`, mini-spec C55)** — chặng 1 dừng ở bước dịch, nghĩa là
**giọng đọc và video xuất ra chưa từng được chạy thử trước khi phát hành**: hai
thứ chính là sản phẩm. Một bản có thể ship với VieNeu hỏng, ghép video hỏng,
hoặc video ra mà CÂM, và cả cổng kiểm lẫn smoke test đều xanh.

Chặng 2 đóng vai người dùng dịch tay (ghi `transcript_vi.json`), chạy tiếp
`--resume-dir`, rồi soi chính tệp video ra:

* có `dubbed_video.mp4` không, có luồng tiếng không;
* tiếng có **thật sự phát ra âm** không (đo `mean_volume` bằng ffmpeg — video
  câm là ca hỏng KHÔNG lộ ra ở bất kỳ mã thoát nào);
* thời lượng có khớp video nguồn không (lệch nhiều = ghép sai).

Chặng 2 cần VieNeu đã cài (`python scripts/setup_vieneu.py`).

Dùng:
    python scripts/kiem_chay_that.py --video tap01_clip.mp4
    python scripts/kiem_chay_that.py --video x.mp4 --python .venv-whisper/Scripts/python.exe
    python scripts/kiem_chay_that.py --den-cuoi        # kèm giọng đọc + xuất video

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

# Bảng mã: cùng lối đã dùng ở mọi worker của dự án (D1f). Console Windows mặc
# định là cp1252, mà tệp này in tiếng Việt — chạy trên runner CI (không qua
# .bat nên không có `chcp 65001`) là chết ngay dòng in ĐẦU TIÊN. Đã xảy ra
# thật ở lượt chạy CI đầu tiên của chính bộ canh này: UnicodeEncodeError trên
# chữ "ạ" của "Chạy thử một lượt dub".
for _luong in (sys.stdout, sys.stderr):
    try:
        _luong.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # luồng đã bị thay bằng thứ khác
        pass


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
        # Tiến trình con ghi nhật ký tiếng Việt, và ở đây stdout là ỐNG chứ
        # không phải console — Python rơi về bảng mã của máy (cp1252 trên
        # Windows) và chết y hệt. Cùng gốc với D1f.
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
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


#: Câu tiếng Việt để đóng vai "người dùng đã dịch tay". Cố ý là tiếng Việt
#: THẬT (không phải chuỗi rác): VieNeu đọc tiếng Việt, đưa chữ vô nghĩa vào là
#: đang kiểm một ca không ai gặp.
CAU_DICH_TAY = [
    "Xin chào, đây là một lượt kiểm tự động của VoxDub Studio.",
    "Giọng đọc tiếng Việt phải nghe được, chứ không phải im lặng.",
    "Nghe thấy câu này nghĩa là đường lồng tiếng còn nguyên vẹn.",
]


def _viet_ban_dich_tay(work: Path, cau: list[dict]) -> Path:
    """Đóng vai người dùng dịch tay: thêm `text_vi` vào từng câu.

    Đúng hợp đồng mà `pipeline._load_translation` đòi — giữ NGUYÊN mọi trường
    của bản chép lời gốc, chỉ THÊM trường bản dịch.
    """
    for i, s in enumerate(cau):
        s["text_vi"] = CAU_DICH_TAY[i % len(CAU_DICH_TAY)]
    dich = work / "data" / "transcript_vi.json"
    dich.write_text(json.dumps(cau, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return dich


def _chay_tiep(video: Path, work: Path, python_exe: str,
               timeout_s: int) -> subprocess.CompletedProcess:
    """Chạy tiếp lượt dở dang: dịch đã có → đọc giọng → ghép video."""
    env = dict(os.environ)
    env.update({
        "TRANSLATE_MODE": "manual",
        "VOXDUB_API_URL": "",
        "TRANSLATE_LOCAL_ENABLED": "0",
        "TRANSLATE_ANALYSIS": "0",
        "QT_QPA_PLATFORM": "offscreen",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    lenh = [python_exe, "-m", "autodub.cli", "dub",
            "--file", str(video),
            "--source-lang", "auto",
            "--bg-mode", "none",
            "--subtitle-mode", "none",
            "--resume-dir", str(work)]
    return subprocess.run(lenh, cwd=str(GOC), env=env, capture_output=True,
                          text=True, timeout=timeout_s, errors="replace")


def _ffprobe(*args: str) -> str:
    ra = subprocess.run(["ffprobe", "-v", "error", *args],
                        capture_output=True, text=True, timeout=60)
    return ra.stdout.strip()


def _thoi_luong(duong_dan: Path) -> float:
    ra = _ffprobe("-show_entries", "format=duration", "-of",
                  "default=nw=1:nk=1", str(duong_dan))
    try:
        return float(ra.splitlines()[0])
    except (ValueError, IndexError):
        return 0.0


def _muc_am_trung_binh(duong_dan: Path) -> float | None:
    """dB trung bình của luồng tiếng; None nếu không đo được.

    Đây là phép đo DUY NHẤT bắt được ca "video ra bình thường nhưng CÂM" —
    ffmpeg ghép một luồng tiếng toàn số 0 vẫn trả mã thoát 0, mọi bước sau đều
    báo thành công, và chỉ người dùng mở ra nghe mới biết.
    """
    ra = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(duong_dan),
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, timeout=300, errors="replace")
    for dong in (ra.stderr or "").splitlines():
        if "mean_volume:" in dong:
            try:
                return float(dong.split("mean_volume:")[1].split("dB")[0])
            except (ValueError, IndexError):
                return None
    return None


def _kiem_chang_hai(video: Path, work: Path, python_exe: str,
                    timeout_s: int) -> list[str]:
    """Soi tệp video ra — phần mà chặng 1 chưa bao giờ chạm tới."""
    bao_cao: list[str] = []

    goc_transcript = work / "data" / "transcript_original.json"
    cau = json.loads(goc_transcript.read_text(encoding="utf-8"))
    dich = _viet_ban_dich_tay(work, cau)
    bao_cao.append(f"đã đóng vai dịch tay: {dich.name} ({len(cau)} câu)")

    kq = _chay_tiep(video, work, python_exe, timeout_s)
    duoi = (kq.stdout or "") + (kq.stderr or "")

    ra = work / "dubbed_video.mp4"
    if not ra.is_file():
        raise Hong("Không có dubbed_video.mp4 — lượt chạy đi qua bước dịch "
                   "nhưng KHÔNG xuất được video. Đây đúng là phần mà chặng 1 "
                   f"không chạm tới. Mã thoát {kq.returncode}, 600 ký tự cuối:"
                   f"\n{duoi[-600:]}")

    tieng = _ffprobe("-select_streams", "a", "-show_entries",
                     "stream=codec_name", "-of", "default=nw=1:nk=1", str(ra))
    if not tieng:
        raise Hong("dubbed_video.mp4 KHÔNG có luồng tiếng — video ra câm hoàn "
                   "toàn, mà mọi bước đều báo thành công.")
    bao_cao.append(f"video ra: {ra.stat().st_size // 1024} KB, tiếng={tieng}")

    muc = _muc_am_trung_binh(ra)
    if muc is None:
        raise Hong("Không đo được mức âm của video ra — thiếu ffmpeg hoặc "
                   "luồng tiếng hỏng.")
    if muc <= -70:
        raise Hong(f"Luồng tiếng CÂM (mean_volume {muc:.1f} dB): video có đủ "
                   "luồng nhưng không phát ra âm nào. Giọng đọc hỏng mà không "
                   "báo lỗi — đúng lớp hỏng im lặng.")
    bao_cao.append(f"mức âm trung bình {muc:.1f} dB (không câm)")

    dai_nguon, dai_ra = _thoi_luong(video), _thoi_luong(ra)
    if dai_nguon > 0 and abs(dai_ra - dai_nguon) / dai_nguon > 0.35:
        raise Hong(f"Thời lượng lệch quá nhiều: nguồn {dai_nguon:.1f}s, ra "
                   f"{dai_ra:.1f}s — bước ghép đang cắt hoặc kéo dài sai.")
    bao_cao.append(f"thời lượng {dai_ra:.1f}s (nguồn {dai_nguon:.1f}s)")

    if kq.returncode != 0:
        raise Hong(f"Video ra có vẻ ổn nhưng lượt chạy trả mã {kq.returncode} "
                   f"— đừng phát hành khi hai thứ đó mâu thuẫn.\n{duoi[-400:]}")
    return bao_cao


def _thu_muc_lam_viec(thu_muc_ra: Path) -> Path:
    ung_vien = [p for p in thu_muc_ra.rglob("data") if p.is_dir()]
    if not ung_vien:
        raise Hong(f"Không thấy thư mục dự án nào dưới {thu_muc_ra} — "
                   "lượt chạy đổ trước cả bước nghe.")
    return max(ung_vien, key=lambda p: p.stat().st_mtime).parent


def kiem(video: Path, python_exe: str, timeout_s: int, giu_lai: bool,
         den_cuoi: bool = False) -> list[str]:
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

        # 5. Chặng 2 (C55): đi nốt phần sản phẩm thật — giọng đọc + xuất video.
        if den_cuoi:
            bao_cao.extend(_kiem_chang_hai(video, work, python_exe, timeout_s))
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
    ap.add_argument("--den-cuoi", action="store_true",
                    help="chạy tiếp qua GIỌNG ĐỌC và XUẤT VIDEO (C55) — cần "
                         "VieNeu đã cài (scripts/setup_vieneu.py)")
    args = ap.parse_args()

    video = Path(args.video)
    if not video.is_absolute():
        video = GOC / video
    if not video.is_file():
        print(f"!! Không thấy video {video}", file=sys.stderr)
        return 2

    print(f"Chạy thử một lượt dub: {video.name}")
    try:
        for dong in kiem(video, args.python, args.timeout, args.giu_lai,
                         den_cuoi=args.den_cuoi):
            print(f"  [ok] {dong}")
    except Hong as e:
        print(f"\n  [HỎNG] {e}", file=sys.stderr)
        print("\nKẾT LUẬN: KHÔNG phát hành bản này.", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        print(f"\n  [HỎNG] Quá {args.timeout}s mà lượt chạy chưa xong.",
              file=sys.stderr)
        return 1
    # Câu kết luận phải nói ĐÚNG thứ vừa chạy: bản trước in "tới bước dịch"
    # cho cả hai chặng, tức đọc log xong vẫn không biết giọng đọc có được kiểm
    # hay không. Cùng lớp với dòng "Job xong" nói dối của C54.
    if args.den_cuoi:
        print("\nKẾT LUẬN: lượt chạy thật đi HẾT đường — nghe, dịch, đọc giọng, "
              "ghép video; tệp ra có tiếng và không câm.")
    else:
        print("\nKẾT LUẬN: lượt chạy thật đi qua bước nghe và tới bước dịch, "
              "ngôn ngữ nguồn đúng là thứ máy nghe ra. (Giọng đọc và video "
              "xuất ra CHƯA kiểm — thêm --den-cuoi.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
