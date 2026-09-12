#!/usr/bin/env python3
"""Đọc `ocr_chan_doan.json` và trả lời BỐN câu hỏi của E6 giai đoạn 0.

Không có script này thì tệp chẩn đoán chỉ là một đống JSON, và việc "đo" lại
thành đọc bằng mắt rồi ước lượng — đúng thứ mini-spec sinh ra để tránh.

Dùng:
    python3 scripts/do_chan_doan_ocr.py <đường dẫn>/data/ocr_chan_doan.json

Xem `docs/MINI-SPEC_E6_Bot_Khung_OCR.md` mục C.
"""
from __future__ import annotations

import json
import sys
import unicodedata

#: Giá một lô và số khung mỗi lô — khớp `autodub/media/doc_chu_may_chu.py`.
SO_KHUNG_MOI_LO = 6
VOX_MOI_LO = 8


def bo_dau(chu: str) -> str:
    """Bỏ dấu tiếng Việt để so được chữ RapidOCR (mất dấu) với transcript.

    Không so được nếu không làm bước này: bộ đọc tại máy trả `met moi that su`
    còn transcript trả `Mệt mỏi thật sự`. So thẳng là mọi đoạn đều "không
    trùng", và kết luận sẽ ngược hẳn sự thật.
    """
    tach = unicodedata.normalize("NFD", chu.lower())
    khong_dau = "".join(c for c in tach if unicodedata.category(c) != "Mn")
    # `đ` không tách được bằng NFD.
    return khong_dau.replace("đ", "d")


def _tieng(chu: str) -> set[str]:
    return {t for t in bo_dau(chu).split() if t}


def chong_thoi_gian(a0, a1, b0, b1) -> bool:
    if None in (a0, a1, b0, b1):
        return False
    return a0 < b1 and b0 < a1


def main(duong_dan: str) -> int:
    with open(duong_dan, encoding="utf-8") as f:
        d = json.load(f)

    doan = d.get("doan") or []
    tr = d.get("transcript") or []
    video = d.get("video") or {}
    thoi_gian = d.get("thoi_gian") or {}

    print(f"Video {video.get('dai_giay')}s · {video.get('so_moc_lay_mau')} mốc "
          f"lấy mẫu · {len(doan)} đoạn chữ · {len(tr)} đoạn lời")
    print()

    # --- C.1 — bao nhiêu đoạn OCR trùng lời đọc ở cùng mốc thời gian -------
    trung, rieng = [], []
    for dd in doan:
        tieng_ocr = _tieng(dd.get("chu_cuc_bo", ""))
        if not tieng_ocr:
            continue
        phu_lon_nhat = 0.0
        for t in tr:
            if not chong_thoi_gian(dd.get("bat_dau_s"), dd.get("ket_thuc_s"),
                                   t.get("bat_dau_s"), t.get("ket_thuc_s")):
                continue
            chung = tieng_ocr & _tieng(t.get("chu", ""))
            phu_lon_nhat = max(phu_lon_nhat, len(chung) / len(tieng_ocr))
        (trung if phu_lon_nhat >= 0.6 else rieng).append((dd, phu_lon_nhat))

    tong = len(trung) + len(rieng)
    if not tong:
        print("Không có đoạn chữ nào đọc được — không kết luận được gì.")
        return 1

    print(f"C.1  Trùng lời đọc (>=60% tiếng chung, cùng mốc): "
          f"{len(trung)}/{tong} = {len(trung) / tong * 100:.0f}%")
    print(f"     Riêng của hình (overlay/CTA):               {len(rieng)}/{tong}")
    print()

    # --- C.2 — phần riêng nằm ở đâu trên dòng thời gian --------------------
    dai = float(video.get("dai_giay") or 0) or 1.0
    dau = sum(1 for dd, _ in rieng if (dd.get("bat_dau_s") or 0) <= 5.0)
    cuoi = sum(1 for dd, _ in rieng if (dd.get("bat_dau_s") or 0) >= dai - 5.0)
    print(f"C.2  Đoạn RIÊNG theo vị trí: {dau} ở 5s đầu · {cuoi} ở 5s cuối · "
          f"{len(rieng) - dau - cuoi} ở giữa")
    if rieng:
        print("     Năm đoạn riêng đầu tiên (đọc bằng mắt xem có phải overlay thật):")
        for dd, p in rieng[:5]:
            print(f"       [{dd.get('bat_dau_s')}s] {dd.get('chu_cuc_bo', '')[:60]!r} "
                  f"(trùng {p * 100:.0f}%)")
    print()

    # --- C.3 — bỏ đoạn trùng thì còn bao nhiêu lô --------------------------
    def lo(n: int) -> int:
        return (n + SO_KHUNG_MOI_LO - 1) // SO_KHUNG_MOI_LO

    lo_cu, lo_moi = lo(tong), lo(len(rieng))
    print(f"C.3  Lô gửi máy chủ: {lo_cu} -> {lo_moi}   "
          f"Vox: {lo_cu * VOX_MOI_LO} -> {lo_moi * VOX_MOI_LO} "
          f"(tiết kiệm {(lo_cu - lo_moi) * VOX_MOI_LO})")
    print()

    # --- C.4 — thời gian có tỉ lệ với số khung không ----------------------
    giay = float(thoi_gian.get("ocr_cuc_bo_s") or 0)
    so_moc = int(video.get("so_moc_lay_mau") or 0)
    khoi_dong = thoi_gian.get("khoi_dong_s")
    quet = thoi_gian.get("quet_s")
    if khoi_dong is not None and quet is not None:
        tong_do = khoi_dong + quet
        so_khung = int(thoi_gian.get("so_khung") or so_moc or 1)
        print(f"C.4  Khởi động engine {khoi_dong:.1f}s (CỐ ĐỊNH, cắt khung "
              f"không giảm)")
        print(f"     Quét {so_khung} khung {quet:.1f}s = "
              f"{quet / so_khung:.2f}s/khung (co theo tỉ lệ)")
        if tong_do > 0:
            print(f"     Phần cắt được nhiều nhất: {quet / tong_do * 100:.0f}% "
                  f"thời gian OCR")
        if khoi_dong > quet:
            print("     => KHỞI ĐỘNG chiếm phần lớn. Cắt khung tiết kiệm TIỀN")
            print("        nhưng gần như KHÔNG rút ngắn thời gian chờ.")
        else:
            print("     => Phần quét chiếm phần lớn. Cắt khung rút ngắn cả hai.")
    elif giay and so_moc:
        print(f"C.4  OCR cục bộ {giay:.0f}s / {so_moc} khung = "
              f"{giay / so_moc:.2f}s mỗi khung")
        print("     Bản dựng này chưa tách được khởi động/quét (worker cũ) —")
        print("     ĐỪNG tin rằng giảm số khung sẽ giảm thời gian tương ứng.")
    print()

    # --- Kết luận, có điều kiện -------------------------------------------
    ty_le = len(trung) / tong
    print("=> Đòn bẩy D1 (bỏ đoạn trùng transcript):")
    if ty_le >= 0.5 and (dau + cuoi) >= len(rieng) * 0.5:
        print(f"   CÓ CƠ SỞ — {ty_le * 100:.0f}% đoạn là phụ đề lặp lời, và phần")
        print("   riêng dồn về đầu/cuối đúng như overlay thật thường nằm.")
    elif ty_le >= 0.5:
        print(f"   CÓ CƠ SỞ VỀ TIỀN ({ty_le * 100:.0f}% trùng) nhưng phần riêng rải")
        print("   đều dòng thời gian — kiểm tay năm đoạn ở trên trước khi áp.")
    else:
        print(f"   KHÔNG — chỉ {ty_le * 100:.0f}% trùng. Bỏ đoạn trùng cắt được ít")
        print("   mà rủi ro mất bằng chứng thật. Xét D2/D3 thay.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
