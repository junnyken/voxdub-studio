"""Đo xem bước nghe có bỏ sót câu không — trên CHÍNH dự án của bạn.

Chủ dự án báo: *"nó vẫn chưa ghi đúng số lượng câu trong đoạn video, đôi khi
có bị thiếu câu"*. Tôi thử tái hiện trên clip mẫu 53 giây thì KHÔNG mất câu
nào (13 câu ở cả bản sạch lẫn bản trộn nhạc, cùng 107 từ) — nhạc chỉ làm VỤN
câu chứ không nuốt câu. Nghĩa là phải đo trên đúng video của bạn mới biết.

Script chạy lại bước nghe trên một thư mục dự án đã có, với vài cách khác nhau,
rồi so số câu và số từ:

* bản trộn (thứ app đang nghe) vs `vocals.wav` (giọng đã tách, nếu dự án đã
  chạy tách nhạc nền) — trả lời câu hỏi "nhạc có làm mất lời không";
* lọc tiếng nói (VAD) bật vs tắt — trả lời "bộ lọc im lặng có cắt nhầm không";
* model to hơn — trả lời "có phải do nghe bằng model nhỏ không".

Dùng:
    py scripts/so_sanh_nghe.py --du-an "output\\VN\\20260828_vi"
    py scripts/so_sanh_nghe.py --du-an ... --model small --python .venv-whisper\\Scripts\\python.exe

KHÔNG gọi máy chủ, KHÔNG tốn Vox — chỉ nghe lại trên máy.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

for _luong in (sys.stdout, sys.stderr):
    try:
        _luong.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

GOC = Path(__file__).resolve().parents[1]


def _tim_am_thanh(du_an: Path) -> dict[str, Path]:
    """Các bản âm thanh có sẵn trong thư mục dự án."""
    data = du_an / "data" if (du_an / "data").is_dir() else du_an
    ra = {}
    for ten, nhan in (("original_audio.wav", "bản trộn (app đang nghe)"),
                      ("vocals.wav", "giọng đã tách (vocals)")):
        p = data / ten
        if p.is_file():
            ra[nhan] = p
    return ra


def _nghe(python_exe: str, audio: Path, model: str, ngon_ngu: str,
          vad: bool) -> list[dict]:
    """Chạy nghe trong tiến trình con, trả về danh sách câu."""
    ma = f'''
import json, sys
from faster_whisper import WhisperModel
m = WhisperModel({model!r}, device="cpu", compute_type="int8")
segs, info = m.transcribe({str(audio)!r}, language={ngon_ngu or None!r},
                          beam_size=5, vad_filter={vad!r},
                          vad_parameters={{"min_silence_duration_ms": 500}},
                          word_timestamps=True, condition_on_previous_text=False)
ra = [{{"start": round(s.start, 2), "end": round(s.end, 2),
        "text": s.text.strip()}} for s in segs if s.text.strip()]
print("###" + json.dumps(ra, ensure_ascii=False))
'''
    kq = subprocess.run([python_exe, "-c", ma], capture_output=True, text=True,
                        errors="replace", timeout=7200)
    if kq.returncode != 0:
        raise SystemExit(f"Nghe hỏng: {kq.stderr.strip()[-500:]}")
    dong = [d for d in kq.stdout.splitlines() if d.startswith("###")]
    return json.loads(dong[-1][3:]) if dong else []


def _tom_tat(cau: list[dict]) -> str:
    tu = sum(len(c["text"].split()) for c in cau)
    giay = sum(c["end"] - c["start"] for c in cau)
    return f"{len(cau):4d} câu · {tu:5d} từ · {giay:7.1f}s có tiếng"


def _cau_thieu(nhieu: list[dict], it: list[dict]) -> list[dict]:
    """Câu có ở bản `nhieu` mà bản `it` không có (so bằng 25 ký tự đầu)."""
    co = " ".join(c["text"] for c in it).lower()
    return [c for c in nhieu
            if c["text"].lower().strip(" .,!?")[:25] not in co]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--du-an", required=True, help="thư mục dự án trong output/")
    ap.add_argument("--model", default="small")
    ap.add_argument("--ngon-ngu", default="", help="rỗng = để máy tự nhận")
    ap.add_argument("--python", default=sys.executable,
                    help="python có faster-whisper (vd .venv-whisper\\Scripts\\python.exe)")
    ap.add_argument("--ra", default="", help="ghi bản chép của từng lượt ra thư mục này")
    args = ap.parse_args()

    du_an = Path(args.du_an).resolve()
    am = _tim_am_thanh(du_an)
    if not am:
        print(f"!! Không thấy original_audio.wav trong {du_an}", file=sys.stderr)
        return 2

    print(f"Dự án: {du_an.name}")
    print(f"Model: {args.model} · ngôn ngữ: {args.ngon_ngu or 'tự nhận'}\n")

    ket: dict[str, list[dict]] = {}
    for nhan, p in am.items():
        for vad, ten_vad in ((True, "lọc im lặng BẬT"), (False, "lọc im lặng TẮT")):
            khoa = f"{nhan} · {ten_vad}"
            print(f"đang nghe: {khoa} …", flush=True)
            ket[khoa] = _nghe(args.python, p, args.model, args.ngon_ngu, vad)

    print("\n" + "=" * 72)
    for khoa, cau in ket.items():
        print(f"{khoa:44} {_tom_tat(cau)}")
    print("=" * 72)

    # Câu chỉ xuất hiện ở MỘT lượt = câu lượt kia bỏ sót.
    goc = "bản trộn (app đang nghe) · lọc im lặng BẬT"
    if goc in ket:
        for khoa, cau in ket.items():
            if khoa == goc:
                continue
            thieu = _cau_thieu(cau, ket[goc])
            if not thieu:
                continue
            print(f"\n{len(thieu)} câu có ở «{khoa}» mà lượt app đang dùng "
                  f"không có.\n(So thô theo 25 ký tự đầu — cắt câu khác nhau "
                  f"cũng lọt vào đây, nên nhìn số TỪ ở bảng trên trước, rồi "
                  f"mới đọc danh sách này.)")
            for c in thieu[:15]:
                print(f"  [{c['start']:7.1f}s] {c['text'][:70]}")
            if len(thieu) > 15:
                print(f"  … và {len(thieu) - 15} câu nữa")

    if args.ra:
        ra = Path(args.ra)
        ra.mkdir(parents=True, exist_ok=True)
        for khoa, cau in ket.items():
            ten = khoa.replace(" ", "_").replace("·", "-").replace("(", "").replace(")", "")
            (ra / f"{ten}.json").write_text(
                json.dumps(cau, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nĐã ghi bản chép từng lượt vào {ra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
