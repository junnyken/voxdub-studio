#!/usr/bin/env python3
"""Đo THẬT từng mục `supported` của Từ điển chỉ đạo hình ảnh — MINI-SPEC I2.

Vì sao cần lượt chạy này thay vì thêm test: catalog là một lời hứa. Test đơn
vị chỉ chứng minh được lời hứa ấy KHỚP với mã; nó không chứng minh được video
ra đúng dài bằng lời đọc và khung cuối không đứng hình. Đúng hai thứ đó là
lỗi D1/H4c-1 đã tốn hai lượt pilot mới lộ ra.

Chuỗi chạy — bằng đồ thật, 0 Vox, không cần máy chủ:

    kịch bản 5 cảnh → ảnh (ffmpeg vẽ) → slideshow → giọng đọc thật
    → xuất video có tiếng → ĐỔI kiểu chuyển cảnh theo catalog → đo lại

Với mỗi mục `supported` của nhóm `transition`, script dựng lại slideshow bằng
ĐÚNG thời lượng D1 đã suy từ giọng đọc thật, cho chạy lại đường xuất chung,
rồi đo hai thứ bằng đúng bộ đo của pilot H4 (`scripts/pilot_h4_cuc_bo.py` —
không dựng bộ đo thứ hai):

* **H4c-1** — luồng hình dài đúng bằng tổng lời đọc (ngưỡng 2 khung @30fps);
* **D1** — luồng hình phủ hết luồng tiếng, không để lại đuôi mất hình.

Thêm một phép canh nữa: sau khi ghép, D1 **không được dựng lại đè** lên bản
vừa dựng. Nếu nó đè, nghĩa là kiểu chuyển cảnh đó làm lệch thời lượng quá
ngưỡng 0,25 giây — và bản đo sau đó sẽ là bản mờ chồng mặc định chứ không
phải bản đang kiểm. Không canh thì con số trông vẫn đẹp mà sai đối tượng.

    python3 scripts/kiem_catalog_h4.py [--giu] [--ra THU_MUC]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GOC)
sys.path.insert(0, os.path.join(GOC, "scripts"))

import pilot_h4_cuc_bo as pilot   # noqa: E402  (phải sau khi vá sys.path)

TEP_CATALOG = os.path.join(GOC, "control_server", "src", "data",
                           "visual-direction-catalog.v1.json")

#: Năm cảnh — mini-spec I2 §Test Plan 6 đòi tối thiểu 5, và số lẻ giúp lộ lỗi
#: lệch nửa cảnh rõ hơn số chẵn.
LOI = [
    "Sáng nào cũng vội, bữa sáng thành ra qua loa cho xong.",
    "Cắm điện, chờ ba phút, là có ngay đồ ăn nóng cho cả nhà.",
    "Nồi nhỏ gọn, rửa nhanh, để vừa kệ bếp chung cư.",
    "Nhà tôi dùng hai tháng nay, sáng nào cũng kịp giờ đi làm.",
    "Thử một tuần rồi tính tiếp, không hợp thì thôi.",
]

BEAT = ("hook", "problem_context", "demonstration", "proof", "cta")


def _kich_ban() -> dict:
    return {
        "id": "kiem-catalog-i2", "flowBlueprintId": "bp", "brandProfileId": "br",
        "status": "ready",
        "beats": [
            {"beatType": t, "voiceoverTextVi": loi,
             "captionSuggestionVi": loi.split(",")[0],
             "visualBriefVi": "Gian bếp buổi sáng"}
            for t, loi in zip(BEAT, LOI)
        ],
    }


def _bam(duong: str) -> str:
    with open(duong, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def _muc_supported() -> list[dict]:
    """Mọi mục `supported` của nhóm chuyển cảnh, đọc thẳng từ catalog."""
    with open(TEP_CATALOG, encoding="utf-8") as f:
        catalog = json.load(f)
    nhom = next(g for g in catalog["groups"] if g["id"] == "transition")
    return [m for m in nhom["values"] if m["render_mode"] == "supported"]


def chay(thu_muc_goc: str) -> bool:
    from autodub.config import Settings
    from autodub.du_an_tu_kich_ban import TEN_VIDEO_NGUON, dung_du_an
    from autodub.editor import rebuild_output, resynth_segments, load_work_dir
    from autodub import product_video

    dat_het = True
    anh_dir = os.path.join(thu_muc_goc, "anh")
    os.makedirs(anh_dir, exist_ok=True)
    work = os.path.join(thu_muc_goc, "duan")
    kb = _kich_ban()

    pilot._cau("1. Dựng dự án 5 cảnh + giọng đọc THẬT")
    anh = pilot._anh(anh_dir, len(kb["beats"]))
    ket = dung_du_an(kb, anh, work)
    print(f"  dòng thời gian ước lượng : {sum(d.giay for d in ket.storyboard.doan):.2f}s")

    state = load_work_dir(work)
    settings = Settings()
    resynth_segments(work, [int(s["id"]) for s in state.segments], settings,
                     target_key="vi")

    # Bẫy nhẹ đúng chỗ D1 gọi khâu ghép hình: cần biết D1 quyết định mỗi cảnh
    # dài bao nhiêu giây (con số suy từ giọng đọc thật), vì các biến thể phía
    # dưới phải dựng lại bằng ĐÚNG những con số ấy — dựng bằng số khác thì
    # đang đo một video khác, không phải đo kiểu chuyển cảnh.
    goc_ghep = product_video.ghep_anh_nguoi_dung
    ghi_nhan: dict = {}

    def _bat(duong_anh, duong_ra, *, giay_moi_anh, giay_chuyen=0.3,
             kieu_chuyen="mo_chong", timeout=300.0):
        ghi_nhan["giay"] = list(giay_moi_anh) if not isinstance(
            giay_moi_anh, (int, float)) else [float(giay_moi_anh)] * len(duong_anh)
        ghi_nhan["giay_chuyen"] = giay_chuyen
        return goc_ghep(duong_anh, duong_ra, giay_moi_anh=giay_moi_anh,
                        giay_chuyen=giay_chuyen, kieu_chuyen=kieu_chuyen,
                        timeout=timeout)

    product_video.ghep_anh_nguoi_dung = _bat
    try:
        ra = rebuild_output(work, settings, target_key="vi", bg_mode="none")
    finally:
        product_video.ghep_anh_nguoi_dung = goc_ghep

    if "giay" not in ghi_nhan:
        pilot._dat("D1 dựng lại hình theo giọng thật", False,
                   "D1 không chạy — không có mốc thật để đo biến thể")
        return False

    giay = ghi_nhan["giay"]
    gc = ghi_nhan["giay_chuyen"]
    tong = sum(giay)
    print("  mốc THẬT của D1          : "
          + ", ".join(f"{g:.2f}" for g in giay) + f" (tổng {tong:.2f}s)")
    print(f"  chuyển cảnh của dự án    : {gc:.2f}s")

    co, muc = pilot._co_tieng(ra)
    dat_het &= pilot._dat("video nền có tiếng thật", co,
                          f"mức âm trung bình {muc:.1f} dB")

    duong_video = os.path.join(work, TEN_VIDEO_NGUON)

    pilot._cau("2. Đo từng mục `supported` của nhóm chuyển cảnh")
    bang = []
    for m in _muc_supported():
        kieu = m["h4_mapping"]["parameters"]["kieu_chuyen"]
        print(f"\n  ── {m['id']} ({m['label_vi']}) → kieu_chuyen={kieu}")

        # Dựng lại slideshow bằng ĐÚNG mốc D1, chỉ đổi kiểu chuyển cảnh.
        goc_ghep(anh, duong_video, giay_moi_anh=giay, giay_chuyen=gc,
                 kieu_chuyen=kieu)
        bam_truoc = _bam(duong_video)
        dai_slideshow = pilot._thoi_luong_luong(duong_video, "v")

        # Chạy lại đường xuất CHUNG. D1 phải thấy thời lượng đã khớp và GIỮ
        # NGUYÊN bản này (ngưỡng 0,25s) — nếu nó dựng lại thì mọi số đo bên
        # dưới là của bản mờ chồng mặc định, không phải của mục đang kiểm.
        ra = rebuild_output(work, settings, target_key="vi", bg_mode="none")
        giu_nguyen = _bam(duong_video) == bam_truoc

        dai_hinh = pilot._thoi_luong_luong(ra, "v")
        dai_tieng = pilot._thoi_luong_luong(ra, "a")
        lech_kich_ban = abs((dai_slideshow or 0) - tong)
        thieu_duoi = (dai_tieng or 0) - (dai_hinh or 0)

        ok_giu = pilot._dat("D1 giữ nguyên bản vừa dựng (không đè)", giu_nguyen,
                            "" if giu_nguyen else
                            "D1 dựng lại ⇒ kiểu này lệch quá 0,25s")
        ok_h4c1 = pilot._dat(
            "H4c-1 — slideshow dài đúng tổng lời đọc",
            lech_kich_ban <= 2 / 30, f"lệch {lech_kich_ban:.3f}s")
        ok_d1 = pilot._dat(
            "D1 — hình phủ hết tiếng (không đuôi mất hình)",
            thieu_duoi <= 2 / 30,
            f"thiếu {thieu_duoi:.2f}s hình ở cuối" if thieu_duoi > 2 / 30
            else f"lệch {abs(thieu_duoi):.3f}s")
        print(f"     luồng hình / luồng tiếng : {dai_hinh:.2f}s / {dai_tieng:.2f}s")

        dat = ok_giu and ok_h4c1 and ok_d1
        dat_het &= dat
        bang.append((m["id"], kieu, dai_slideshow, dai_hinh, dai_tieng,
                     lech_kich_ban, thieu_duoi, dat))

    pilot._cau("BẢNG BẰNG CHỨNG")
    print(f"  tổng lời đọc (mốc D1): {tong:.2f}s · chuyển cảnh {gc:.2f}s · "
          f"{len(giay)} cảnh")
    print(f"  {'mục':<16}{'kieu_chuyen':<14}{'slideshow':>10}{'hình':>8}"
          f"{'tiếng':>8}{'lệch KB':>9}{'đuôi':>8}  kết luận")
    for ma, kieu, sl, h, t, lk, td, dat in bang:
        print(f"  {ma:<16}{kieu:<14}{sl:>9.2f}s{h:>7.2f}s{t:>7.2f}s"
              f"{lk:>8.3f}s{td:>7.3f}s  {'ĐẠT' if dat else 'HỎNG'}")

    pilot._cau("KẾT LUẬN")
    print("  ĐẠT — mọi mục supported của catalog dựng ra video giữ đúng "
          "thời lượng D1/H4c-1." if dat_het else
          "  HỎNG — xem các dòng [HỎNG]; mục tương ứng phải hạ xuống "
          "advisory_only hoặc loại khỏi catalog.")
    return dat_het


def main() -> int:
    from autodub.ffmpeg_deps import vao_duong_ffmpeg
    vao_duong_ffmpeg()

    ap = argparse.ArgumentParser()
    ap.add_argument("--giu", action="store_true", help="giữ lại thư mục dự án")
    ap.add_argument("--ra", default="", help="thư mục làm việc")
    tham_so = ap.parse_args()

    goc = tham_so.ra or tempfile.mkdtemp(prefix="kiem-catalog-i2-")
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
