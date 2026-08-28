"""Đóng gói thư mục `models/` thành zip + bản kê, để máy khác kéo về dùng lại.

Vì sao: bản tải về chỉ 74 MB nhưng cài xong có máy phình lên gần 18 GB. Phần
lớn là các venv — **không** mang đi được (venv gắn với đường dẫn tuyệt đối của
máy đã tạo ra nó). Nhưng `models/` thì mang đi thoải mái: đó là tệp dữ liệu
thuần, máy nào cũng dùng được, và cũng là phần tải lâu nhất.

Mỗi model một tệp zip RIÊNG (không gộp một cục vài GB): tải hỏng thì chỉ tải
lại đúng phần hỏng. Gói nào vượt trần thì tự CẮT PHẦN — model Whisper large-v3
cỡ 3 GB, trong khi GitHub Release chặn 2 GB mỗi tệp; cắt sẵn thì đưa lên đâu
cũng được.

Dùng:
    py scripts/dong_goi_models.py --ra D:\\goi-models
    py scripts/dong_goi_models.py --ra D:\\goi-models --chi whisper vieneu

Xong thì đưa cả thư mục `--ra` lên chỗ nào tải được (Vibe Host, GitHub
Release...), rồi máy khác chạy `scripts/tai_models.py --tu <URL>/models.json`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

for _luong in (sys.stdout, sys.stderr):
    try:
        _luong.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

MB = 1024 ** 2

#: Model nào mang đi được, và câu giải thích cho người đọc bản kê.
MO_TA = {
    "whisper": "Nghe-chép Whisper (bắt buộc cho mọi lượt lồng tiếng)",
    "vieneu": "Giọng đọc tiếng Việt VieNeu chạy offline",
    "paraformer-zh": "Nghe-chép tiếng Trung Paraformer",
    "lipsync": "Khớp khẩu hình MuseTalk",
    "diarization": "Tách giọng theo người nói (pyannote)",
}

#: Model có RÀNG BUỘC quyền truy cập — KHÔNG đóng gói mặc định.
#:
#: `pyannote/speaker-diarization-3.1` là gated model: mỗi người phải tự đồng ý
#: điều khoản trên HuggingFace rồi dùng token của chính mình (xem
#: scripts/setup_diarization.py). Phát tán lại trọng số qua một đường link là
#: đi vòng qua đúng cái cổng đó.
GIOI_HAN = {
    "diarization": "pyannote là gated model — mỗi người phải tự đồng ý điều "
                   "khoản trên HuggingFace và dùng token riêng",
    "lipsync": "MuseTalk là mô hình nghiên cứu, điều khoản dùng lại khác với "
               "model thường — tự kiểm trước khi phát tán",
}


def _sha256(duong_dan: Path, bao_tien_do=None) -> str:
    h = hashlib.sha256()
    da_doc = 0
    with open(duong_dan, "rb") as f:
        while True:
            khoi = f.read(4 * MB)
            if not khoi:
                break
            h.update(khoi)
            da_doc += len(khoi)
            if bao_tien_do:
                bao_tien_do(da_doc)
    return h.hexdigest()


def _nen(thu_muc: Path, tep_ra: Path) -> None:
    """Nén một thư mục model, giữ nguyên cây bên trong."""
    tam = tep_ra.with_suffix(".dangghi")
    with zipfile.ZipFile(tam, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for goc, _tm, tep in os.walk(thu_muc):
            for t in sorted(tep):
                that = Path(goc) / t
                z.write(that, that.relative_to(thu_muc).as_posix())
    # Đổi tên ở bước cuối: hỏng giữa chừng thì không để lại tệp trông như đã
    # xong (lỗi lớp "tệp dở dang trông như tệp thật").
    tam.replace(tep_ra)


def _cat_phan(tep_zip: Path, tran_bytes: int) -> list[dict]:
    """Cắt một gói lớn thành nhiều tệp `.part01`, xoá bản nguyên sau khi xong.

    Mỗi phần có mã băm RIÊNG: tải 3 GB mà hỏng ở phần cuối thì chỉ tải lại
    đúng phần đó, không phải làm lại từ đầu.
    """
    phan = []
    with open(tep_zip, "rb") as f:
        i = 0
        while True:
            du_lieu = f.read(tran_bytes)
            if not du_lieu:
                break
            i += 1
            ten_phan = f"{tep_zip.name}.part{i:02d}"
            (tep_zip.parent / ten_phan).write_bytes(du_lieu)
            phan.append({
                "tep": ten_phan,
                "bytes": len(du_lieu),
                "sha256": hashlib.sha256(du_lieu).hexdigest(),
            })
    tep_zip.unlink()   # bản nguyên đã nằm trọn trong các phần
    return phan


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--thu-muc", default=".", help="thư mục ứng dụng VoxDub")
    ap.add_argument("--ra", required=True, help="thư mục chứa zip + bản kê")
    ap.add_argument("--chi", nargs="*", default=None,
                    help="chỉ đóng gói những model này")
    ap.add_argument("--cat-phan-mb", type=int, default=1900,
                    help="cắt gói lớn hơn ngần này thành nhiều phần "
                         "(mặc định 1900 MB — vừa trần 2 GB của GitHub Release; "
                         "0 = không cắt)")
    ap.add_argument("--gom-ca-model-gioi-han", action="store_true",
                    help="đóng gói CẢ model có ràng buộc quyền truy cập "
                         "(đường link khi đó KHÔNG được để công khai)")
    args = ap.parse_args()

    goc = Path(args.thu_muc).resolve()
    thu_muc_models = goc / "models"
    if not thu_muc_models.is_dir():
        print(f"!! Không thấy {thu_muc_models}", file=sys.stderr)
        return 2
    ra = Path(args.ra).resolve()
    ra.mkdir(parents=True, exist_ok=True)

    ke: list[dict] = []
    for con in sorted(thu_muc_models.iterdir()):
        if not con.is_dir() or not any(con.rglob("*")):
            continue
        ten = con.name
        if args.chi and ten not in args.chi:
            continue
        if ten in GIOI_HAN and not args.gom_ca_model_gioi_han:
            print(f"BỎ QUA {ten}: {GIOI_HAN[ten]}.")
            print("        Vẫn muốn thì thêm --gom-ca-model-gioi-han, và đừng "
                  "để link công khai.\n")
            continue

        tep_zip = ra / f"models-{ten}.zip"
        print(f"Đang nén {ten} …", flush=True)
        _nen(con, tep_zip)
        co = tep_zip.stat().st_size
        print(f"  {tep_zip.name}: {co / MB:.1f} MB — đang tính mã băm…", flush=True)
        bam = _sha256(tep_zip)
        muc = {
            "ten": ten,
            "tep": tep_zip.name,
            "bytes": co,
            "sha256": bam,
            "mo_ta": MO_TA.get(ten, ""),
            "gioi_han": GIOI_HAN.get(ten, ""),
        }
        tran = args.cat_phan_mb * MB
        if tran and co > tran:
            muc["phan"] = _cat_phan(tep_zip, tran)
            print(f"  cắt thành {len(muc['phan'])} phần (mỗi phần "
                  f"≤ {args.cat_phan_mb} MB)")
        ke.append(muc)
        print(f"  sha256 {bam[:16]}…\n")

    if not ke:
        print("Không có model nào để đóng gói.", file=sys.stderr)
        return 1

    ban_ke = {
        "phien_ban_ke": 1,
        "tao_luc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "models": ke,
    }
    (ra / "models.json").write_text(
        json.dumps(ban_ke, ensure_ascii=False, indent=1), encoding="utf-8")

    tong = sum(m["bytes"] for m in ke)
    print(f"Xong: {len(ke)} gói, tổng {tong / MB:.1f} MB, tại {ra}")
    print("\nBước tiếp: đưa CẢ thư mục này lên chỗ tải được, rồi trên máy khác:")
    print("    py scripts\\tai_models.py --tu https://.../models.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
