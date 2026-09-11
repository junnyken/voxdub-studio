#!/usr/bin/env python3
"""Pilot H4 chạy CỤC BỘ — 0 Vox, không cần máy chủ.

Đi trọn chuỗi mà H4 hứa, bằng đồ thật:

    kịch bản `ready` → ảnh → slideshow (ffmpeg) → Trình chỉnh sửa
    → giọng đọc (VieNeu) → xuất video CÓ TIẾNG

Vì sao cần một lượt chạy thật thay vì thêm test: ba lỗi nặng nhất của H4 đều
**lọt qua bộ test** vì test tiêm hàm giả ghi 9 byte làm "video" — thời lượng
lệch dần, video xuất ra câm, và mẻ vẽ ảnh hỏng thì màn hình im lặng. Test chỉ
chứng minh được thứ nó dám chạy.

Không dùng máy chủ, không dùng mô hình trả tiền: kịch bản dựng bằng tay đúng
hình dạng BrandScript `ready`, ảnh do ffmpeg vẽ, giọng đọc bằng VieNeu chạy
trên máy.

    python3 scripts/pilot_h4_cuc_bo.py [--giu] [--ra THU_MUC]

`--giu` để lại thư mục dự án cho người xem tận mắt.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: Lời đọc thật, đủ dài để nghe ra tiếng và đủ khác nhau để nhìn ra lệch nhịp.
LOI = [
    "Sáng nào cũng vội, bữa sáng thành ra qua loa cho xong.",
    "Cắm điện, chờ ba phút, là có ngay đồ ăn nóng cho cả nhà.",
    "Thử một tuần rồi tính tiếp, không hợp thì thôi.",
]


def _cau(tieu_de: str) -> None:
    print(f"\n{'=' * 66}\n{tieu_de}\n{'=' * 66}")


def _dat(ten: str, ok: bool, ghi_chu: str = "") -> bool:
    print(f"  [{'ĐẠT ' if ok else 'HỎNG'}] {ten}" + (f" — {ghi_chu}" if ghi_chu else ""))
    return ok


def _kich_ban() -> dict:
    """BrandScript đúng hình dạng H3 trả về, trạng thái `ready`."""
    return {
        "id": "pilot-local", "flowBlueprintId": "bp", "brandProfileId": "br",
        "status": "ready",
        "beats": [
            {"beatType": t, "voiceoverTextVi": loi,
             "captionSuggestionVi": loi.split(",")[0],
             "visualBriefVi": "Cận cảnh gian bếp buổi sáng"}
            for t, loi in zip(("hook", "proof", "cta"), LOI)
        ],
    }


def _anh(thu_muc: str, so: int) -> list[str]:
    ra = []
    for i in range(so):
        p = os.path.join(thu_muc, f"anh{i}.png")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
             "-i", f"color=c=0x{(i * 60) % 256:02x}4070:s=540x960:d=1",
             "-frames:v", "1", p], check=True, capture_output=True)
        ra.append(p)
    return ra


def _thoi_luong(duong: str) -> float | None:
    ra = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", duong], capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return float(ra.stdout.strip())
    except ValueError:
        return None


def _co_tieng(duong: str) -> tuple[bool, float]:
    """Video này có luồng tiếng không, và nó có THẬT SỰ kêu không.

    Đây là chỗ lỗi "video câm" đã trốn: có luồng audio không chứng minh được
    gì — một nền im lặng vẫn là một luồng audio hợp lệ. Phải đo mức âm thật.
    """
    luong = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
         "stream=codec_type", "-of", "csv=p=0", duong],
        capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    if not luong:
        return False, -999.0
    # `-hide_banner` chứ KHÔNG phải `-v error`: `volumedetect` in kết quả ở
    # mức `info`, nên hạ mức log xuống `error` là mất luôn số đo và phép kiểm
    # báo "không có tiếng" cho một video có tiếng. Chính tôi mắc lỗi này ở
    # lượt chạy đầu và suýt báo sai cho chủ dự án.
    do = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", duong, "-af", "volumedetect",
         "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    muc = -999.0
    for dong in (do.stderr or "").splitlines():
        if "mean_volume:" in dong:
            try:
                muc = float(dong.split("mean_volume:")[1].split("dB")[0].strip())
            except ValueError:
                pass
    # Nền hoàn toàn im lặng cho mean_volume rất thấp (hoặc -inf).
    return muc > -80.0, muc


def chay(thu_muc_goc: str) -> bool:
    from autodub.config import Settings
    from autodub.du_an_tu_kich_ban import dung_du_an
    from autodub.editor import (
        kiem_san_sang_xuat, load_work_dir, rebuild_output, resynth_segments,
    )
    from autodub.languages import TARGETS

    dat_het = True
    anh_dir = os.path.join(thu_muc_goc, "anh")
    os.makedirs(anh_dir, exist_ok=True)
    work = os.path.join(thu_muc_goc, "duan")
    kb = _kich_ban()

    # --- 1. Dựng dự án bằng ffmpeg THẬT -----------------------------------
    _cau("1. Dựng dự án từ kịch bản (H4a + H4b + H4c)")
    ket = dung_du_an(kb, _anh(anh_dir, len(kb["beats"])), work)
    tong_mong = sum(d.giay for d in ket.storyboard.doan)
    that = _thoi_luong(ket.duong_video)
    print(f"  dòng thời gian kịch bản : {tong_mong:.2f}s")
    print(f"  video slideshow dựng ra : {that:.2f}s")
    dat_het &= _dat("H4c-1 — video khớp dòng thời gian",
                    that is not None and abs(that - tong_mong) <= 2 / 30,
                    f"lệch {abs(that - tong_mong):.3f}s")

    # --- 2. Trình chỉnh sửa mở được ---------------------------------------
    _cau("2. Trình chỉnh sửa mở dự án")
    state = load_work_dir(work)
    dat_het &= _dat("mở được và đọc đủ câu",
                    len(state.segments) == len(kb["beats"]),
                    f"{len(state.segments)} câu")

    # --- 3. Cổng xuất phải CHẶN lúc này -----------------------------------
    _cau("3. Cổng xuất video (H4c-2) — lúc CHƯA có giọng")
    truoc = kiem_san_sang_xuat(work, TARGETS["vi"])
    dat_het &= _dat("nhận ra dự án sẽ ra video CÂM",
                    truoc.cam_hoan_toan and not truoc.xuat_duoc,
                    f"thiếu giọng {len(truoc.thieu_giong)}/{truoc.tong_cau} câu")

    # --- 4. Đọc bằng VieNeu, chạy trên máy --------------------------------
    _cau("4. Tạo giọng đọc bằng VieNeu (0 Vox, chạy trên máy)")
    settings = Settings()
    ids = [int(s["id"]) for s in state.segments]
    resynth_segments(work, ids, settings, target_key="vi")
    sau = kiem_san_sang_xuat(work, TARGETS["vi"])
    dat_het &= _dat("mọi câu đã có giọng", sau.xuat_duoc,
                    f"còn thiếu {sau.thieu_giong}" if sau.thieu_giong else "đủ")

    # --- 5. Xuất video và ĐO xem có tiếng thật không ----------------------
    _cau("5. Xuất video, rồi ĐO mức âm thật")
    ra = rebuild_output(work, settings, target_key="vi", bg_mode="none")
    print(f"  tệp ra: {ra}")
    co, muc = _co_tieng(ra)
    dat_het &= _dat("video xuất ra CÓ TIẾNG", co, f"mức âm trung bình {muc:.1f} dB")
    dai_ra = _thoi_luong(ra)
    print(f"  thời lượng video cuối    : {dai_ra:.2f}s")

    _cau("KẾT LUẬN")
    print("  ĐẠT — chuỗi H4 chạy trọn vẹn, video cuối có tiếng."
          if dat_het else
          "  HỎNG — xem các dòng [HỎNG] phía trên.")
    return dat_het


def main() -> int:
    # Script cũng ở NGOÀI GUI (B7): máy chỉ có FFmpeg trong `bin/` thì mọi
    # `["ffmpeg", …]` dưới đây chết với [WinError 2] nếu không vá PATH trước.
    from autodub.ffmpeg_deps import vao_duong_ffmpeg
    vao_duong_ffmpeg()

    ap = argparse.ArgumentParser()
    ap.add_argument("--giu", action="store_true",
                    help="giữ lại thư mục dự án để xem tận mắt")
    ap.add_argument("--ra", default="", help="thư mục làm việc")
    tham_so = ap.parse_args()

    goc = tham_so.ra or tempfile.mkdtemp(prefix="pilot-h4-")
    os.makedirs(goc, exist_ok=True)
    print(f"Thư mục làm việc: {goc}")
    try:
        return 0 if chay(goc) else 1
    finally:
        if tham_so.giu or tham_so.ra:
            print(f"\nGiữ lại: {goc}")
        else:
            shutil.rmtree(goc, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
