"""Kéo bộ `models/` đã đóng gói về máy này, có kiểm mã băm.

Đi cùng `scripts/dong_goi_models.py`. Tệp vài trăm MB tải hỏng giữa chừng là
chuyện thường, mà một model hỏng thì lỗi lộ ra tận lúc đang lồng tiếng dở —
nên ở đây kiểm sha256 TRƯỚC khi giải nén, và chỉ đổi tên vào chỗ thật ở bước
cuối cùng.

Dùng:
    py scripts/tai_models.py --tu https://.../models.json
    py scripts/tai_models.py --tu https://.../models.json --chi whisper
    py scripts/tai_models.py --tu D:\\goi-models\\models.json      (từ ổ đĩa/USB)

Gói lớn được cắt thành nhiều phần thì script tự tải đủ phần rồi ghép lại —
người dùng không phải biết chuyện đó.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

for _luong in (sys.stdout, sys.stderr):
    try:
        _luong.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

MB = 1024 ** 2


class Hong(Exception):
    """Hỏng có lý do nói được — thông điệp phải nói việc thật phải làm."""


def _la_link(nguon: str) -> bool:
    return urllib.parse.urlparse(nguon).scheme in ("http", "https")


def _doc_ban_ke(nguon: str) -> tuple[dict, str]:
    """(bản kê, thư mục gốc để ghép đường dẫn tệp zip)."""
    if _la_link(nguon):
        with urllib.request.urlopen(nguon, timeout=60) as r:
            return json.loads(r.read().decode("utf-8")), nguon.rsplit("/", 1)[0]
    p = Path(nguon).resolve()
    return json.loads(p.read_text(encoding="utf-8")), str(p.parent)


def _tai(nguon_goc: str, ten_tep: str, dich: Path, tong_bytes: int) -> None:
    if _la_link(nguon_goc):
        link = f"{nguon_goc}/{ten_tep}"
        with urllib.request.urlopen(link, timeout=120) as r, open(dich, "wb") as f:
            da = 0
            while True:
                khoi = r.read(4 * MB)
                if not khoi:
                    break
                f.write(khoi)
                da += len(khoi)
                if tong_bytes:
                    print(f"\r    {da / MB:7.1f} / {tong_bytes / MB:.1f} MB "
                          f"({da * 100 // tong_bytes}%)", end="", flush=True)
            print()
    else:
        shutil.copy2(Path(nguon_goc) / ten_tep, dich)


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            khoi = f.read(4 * MB)
            if not khoi:
                break
            h.update(khoi)
    return h.hexdigest()


def _giai_nen_an_toan(tep_zip: Path, dich: Path) -> None:
    """Giải nén vào thư mục tạm rồi mới đổi tên vào chỗ thật.

    Giải thẳng vào `models/whisper` mà hỏng giữa chừng thì để lại một bộ model
    dở dang — app tưởng đã cài, rồi hỏng ở tận bước nghe.
    """
    tam = dich.parent / (dich.name + ".dangtai")
    if tam.exists():
        shutil.rmtree(tam, ignore_errors=True)
    tam.mkdir(parents=True)
    with zipfile.ZipFile(tep_zip) as z:
        for muc in z.infolist():
            # Chặn đường dẫn thoát ra ngoài (zip slip) — tệp tải từ mạng về
            # thì không được tin.
            dich_muc = (tam / muc.filename).resolve()
            if not str(dich_muc).startswith(str(tam.resolve())):
                raise Hong(f"Gói chứa đường dẫn bất thường: {muc.filename}")
        z.extractall(tam)
    if dich.exists():
        shutil.rmtree(dich, ignore_errors=True)
    tam.replace(dich)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tu", required=True, help="URL hoặc đường dẫn tới models.json")
    ap.add_argument("--thu-muc", default=".", help="thư mục ứng dụng VoxDub")
    ap.add_argument("--chi", nargs="*", default=None, help="chỉ lấy những model này")
    ap.add_argument("--ghi-de", action="store_true",
                    help="ghi đè model đã có sẵn trên máy")
    args = ap.parse_args()

    goc = Path(args.thu_muc).resolve()
    thu_muc_models = goc / "models"
    thu_muc_models.mkdir(parents=True, exist_ok=True)

    try:
        ban_ke, nguon_goc = _doc_ban_ke(args.tu)
    except Exception as e:
        print(f"!! Không đọc được bản kê ở {args.tu}: {e}", file=sys.stderr)
        return 2

    muc = ban_ke.get("models", [])
    if args.chi:
        muc = [m for m in muc if m["ten"] in args.chi]
    if not muc:
        print("Bản kê không có model nào khớp.", file=sys.stderr)
        return 1

    da_lam, bo_qua = [], []
    with tempfile.TemporaryDirectory() as tam:
        for m in muc:
            ten, dich = m["ten"], thu_muc_models / m["ten"]
            if dich.is_dir() and any(dich.rglob("*")) and not args.ghi_de:
                print(f"BỎ QUA {ten}: máy đã có sẵn (thêm --ghi-de nếu muốn thay).")
                bo_qua.append(ten)
                continue
            print(f"{ten} — {m.get('mo_ta', '')}")
            tep = Path(tam) / m["tep"]
            try:
                if m.get("phan"):
                    # Gói lớn được cắt phần (model Whisper ~3 GB vượt trần 2 GB
                    # của GitHub Release). Mỗi phần kiểm mã băm riêng: hỏng ở
                    # phần cuối thì tải lại đúng phần đó, không làm lại từ đầu.
                    print(f"    gói này gồm {len(m['phan'])} phần")
                    with open(tep, "wb") as ra_tep:
                        for i, ph in enumerate(m["phan"], 1):
                            mieng = Path(tam) / ph["tep"]
                            print(f"    phần {i}/{len(m['phan'])}:")
                            _tai(nguon_goc, ph["tep"], mieng, int(ph.get("bytes", 0)))
                            bam_phan = _sha256(mieng)
                            if bam_phan != ph["sha256"]:
                                raise Hong(
                                    f"phần {i} tải về hỏng (mã băm lệch) — "
                                    f"chạy lại lệnh này, nó sẽ tải lại từ đầu")
                            ra_tep.write(mieng.read_bytes())
                            mieng.unlink()
                else:
                    _tai(nguon_goc, m["tep"], tep, int(m.get("bytes", 0)))
            except Hong as e:
                print(f"  !! {e}", file=sys.stderr)
                return 1
            except Exception as e:
                print(f"  !! tải hỏng: {e}", file=sys.stderr)
                return 1
            print("    đang kiểm mã băm…", flush=True)
            bam = _sha256(tep)
            if bam != m["sha256"]:
                print(f"  !! MÃ BĂM KHÔNG KHỚP — tệp tải về hỏng hoặc đã bị "
                      f"đổi.\n     bản kê ghi {m['sha256'][:16]}…, tệp thật là "
                      f"{bam[:16]}…\n     Tải lại; nếu vẫn lệch thì gói trên "
                      f"máy chủ hỏng, đóng gói lại.", file=sys.stderr)
                return 1
            _giai_nen_an_toan(tep, dich)
            print(f"    đã đặt vào {dich}\n")
            da_lam.append(ten)

    print(f"Xong: lấy về {len(da_lam)} model"
          + (f", bỏ qua {len(bo_qua)} model đã có" if bo_qua else ""))
    if da_lam:
        print("Mở lại VoxDub là dùng được ngay, không phải cài lại gì.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
