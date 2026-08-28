"""Đo xem thư mục VoxDub đang ăn dung lượng vào đâu, và chỗ nào trùng lặp.

Vì sao có tệp này: bản tải về chỉ 74 MB, nhưng cài xong có máy phình lên gần
18 GB. Trước khi bàn chuyện dọn hay chuyện tải sẵn từ máy chủ, phải biết CHÍNH
XÁC phần nào chiếm bao nhiêu — đoán thì chỉ dọn nhầm.

Dùng:  python scripts/xem_dung_luong.py
       python scripts/xem_dung_luong.py --thu-muc "C:\\...\\VoxDub-Studio-v3.14.1-win64"
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

for _luong in (sys.stdout, sys.stderr):
    try:
        _luong.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

GB = 1024 ** 3

#: Tính năng nào dùng venv nào — để nói được "không dùng thì gỡ được bao nhiêu".
TINH_NANG = {
    ".venv-whisper": "Nghe-chép (Whisper) — BẮT BUỘC cho mọi lượt lồng tiếng",
    ".venv-vieneu": "Giọng đọc VieNeu chạy offline",
    ".venv-asr": "Nghe-chép tiếng Trung (Paraformer)",
    ".venv-gpu": "Tách nhạc nền (Demucs) trên card đồ họa",
    ".venv-diar": "Tách giọng theo người nói",
    ".venv-mt": "Dịch ngoại tuyến (NLLB)",
    ".venv-lipsync": "Khớp khẩu hình — nặng nhất, và vẫn là bản thử nghiệm",
    ".venv-ocr": "Nhận diện vùng chữ để che chữ gốc",
    "models": "Model đã tải (dùng chung, KHÔNG gắn với máy nào)",
}


def _co(duong_dan: Path) -> int:
    tong = 0
    for goc, _thu_muc, tep in os.walk(duong_dan, onerror=lambda e: None):
        for t in tep:
            try:
                tong += os.path.getsize(os.path.join(goc, t))
            except OSError:
                pass
    return tong


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--thu-muc", default=".", help="thư mục ứng dụng VoxDub")
    args = ap.parse_args()
    goc = Path(args.thu_muc).resolve()
    if not goc.is_dir():
        print(f"!! Không thấy thư mục {goc}", file=sys.stderr)
        return 2

    print(f"Đo {goc}\n(vài phút với thư mục hàng trăm nghìn tệp — cứ để nó chạy)\n")
    muc = []
    for con in sorted(goc.iterdir()):
        if con.is_dir():
            muc.append((con.name, _co(con)))
    muc.sort(key=lambda x: -x[1])
    tong = sum(c for _t, c in muc)

    print(f"{'thư mục':<22} {'GB':>7}   việc nó phục vụ")
    print("-" * 78)
    for ten, co in muc:
        if co < 0.05 * GB:
            continue
        print(f"{ten:<22} {co / GB:>7.2f}   {TINH_NANG.get(ten, '')}")
    print("-" * 78)
    print(f"{'TỔNG':<22} {tong / GB:>7.2f}\n")

    # Thư viện tính toán bị cài LẶP LẠI trong từng venv — thường là phần lớn
    # dung lượng. Đo ngày 28/08 trên một venv thật: nvidia (CUDA) 2,7 GB +
    # torch 1,2 GB + triton 0,7 GB = 4,6 GB cho MỘT venv.
    print("Thư viện nặng nằm ở những đâu (mỗi venv là một lần chép riêng):")
    tong_torch = 0
    ban_torch = []
    for ten, _co_ in muc:
        for tv in ("Lib/site-packages", "lib/python3.12/site-packages",
                   "lib/python3.11/site-packages", "lib/python3.10/site-packages"):
            sp = goc / ten / tv
            if not sp.is_dir():
                continue
            c = sum(_co(sp / g) for g in ("torch", "nvidia", "triton")
                    if (sp / g).is_dir())
            if c:
                ban_torch.append((ten, c))
                tong_torch += c
            break
    for ten, c in sorted(ban_torch, key=lambda x: -x[1]):
        print(f"  {ten:<20} {c / GB:>7.2f} GB")
    if len(ban_torch) > 1:
        lon_nhat = max(c for _t, c in ban_torch)
        print(f"\n  Tổng {tong_torch / GB:.2f} GB cho {len(ban_torch)} bản chép "
              f"riêng (torch + thư viện CUDA + triton). Nếu dùng chung được "
              f"một bản thì tiết kiệm khoảng {(tong_torch - lon_nhat) / GB:.2f} GB "
              f"— nhưng chúng KHÁC phiên bản nhau nên gộp không phải chuyện "
              f"đổi một dòng.")
    elif not ban_torch:
        print("  (không thấy thư viện tính toán nặng nào)")

    print("\nGỡ được gì mà không ảnh hưởng việc lồng tiếng:")
    co_the_go = [(t, c) for t, c in muc
                 if t in (".venv-lipsync", ".venv-ocr") and c > 0.05 * GB]
    if co_the_go:
        for ten, c in co_the_go:
            print(f"  xóa {ten:<18} tiết kiệm {c / GB:.2f} GB  "
                  f"({TINH_NANG.get(ten, '')})")
        print("  Cài lại lúc nào cũng được bằng đúng tệp .bat tương ứng.")
    else:
        print("  (không có thư mục nào thuộc nhóm tuỳ chọn)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
