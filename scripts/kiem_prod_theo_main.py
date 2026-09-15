#!/usr/bin/env python3
"""D5 — PROD có đang chạy đúng mã mà `main` bảo phải chạy không?

Chốt này trả lời câu duy nhất mà cả D3 không chốt nào trả lời được, vì cả hai
chốt của D3 (`--sha-nhanh`, `--sha-nguon`) nằm BÊN TRONG lượt deploy: deploy
không chạy thì chốt cũng không chạy.

Chuyện thật 14/09/2026 — `df980b2` deploy hỏng vì cổng Vibe Host 404; commit kế
tiếp chỉ sửa tài liệu nên bước "có cần deploy không" so bản dựng mới với bản
dựng TRƯỚC, thấy giống nhau, kết luận `app=0` và bỏ qua deploy. Prod chạy mã cũ
**21 giờ** với CI xanh toàn bộ.

BẤT BIẾN PHẢI GIỮ
-----------------
    Prod đúng nhịp ⟺ mã nguồn sinh ra ảnh prod đang chạy giống hệt mã nguồn
    mà `main` bảo phải chạy.

Chú ý cách phát biểu: KHÔNG phải ``prod.commit == main HEAD``. Commit chỉ sửa
tài liệu cố ý KHÔNG deploy lại (C58 chốt 2), nên prod đứng ở commit mã gần nhất
là ĐÚNG. So SHA trực tiếp sẽ đỏ ở mọi commit tài liệu — tức biến chốt thành bộ
canh kêu nhầm, mà backlog dự án đã ghi: bộ canh hay kêu nhầm thì người ta tắt
nó đi, còn tệ hơn không có. Nên phải so THEO NỘI DUNG NGUỒN.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

#: Thư mục build của mỗi dịch vụ là bản chép thuần từ mấy đường dẫn này (đọc
#: từ `scripts/gen_*.sh`). Danh sách chép tay là thứ sẽ mục nát — ai thêm một
#: dòng `cp` vào script sinh mà quên cập nhật ở đây thì chốt D5 im lặng bỏ
#: sót. Nên `tests/test_d5_prod_theo_main.py` đọc CHÍNH script sinh, bóc mọi
#: đường dẫn nó chép, và bắt mọi đường dẫn ấy phải nằm trong danh sách này.
NGUON = {
    "app": [
        "control_server",
        "website",
        "scripts/gen_vays_control_server_branch.sh",
    ],
    "worker": [
        "autodub",
        "control_server/worker-dub",
        "scripts/setup_whisper.py",
        "scripts/setup_vieneu.py",
        "scripts/setup_translate_local.py",
        "scripts/_python_ho_tro.py",
        "scripts/gen_vays_dub_worker_branch.sh",
    ],
}


class KhongKetLuanDuoc(RuntimeError):
    """Không hỏi được prod, hoặc prod không khai SHA.

    KHÁC hẳn "prod đã đúng". Gộp hai thứ này làm một là cách để một dịch vụ
    câm được ghi thành một dịch vụ khoẻ.
    """


def doc_health(url: str, *, so_lan: int = 3, nhip_s: float = 5.0,
               ngu=time.sleep, mo=urllib.request.urlopen) -> dict:
    """Hỏi `/health` và trả về thân đã parse. Thử lại vài lượt vì một cú chập
    mạng không nên biến thành một lượt CI đỏ."""
    loi_cuoi = ""
    for lan in range(so_lan):
        try:
            with mo(url, timeout=20) as resp:
                than = resp.read().decode("utf-8", "replace")
            return json.loads(than)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            loi_cuoi = f"không gọi được ({e})"
        except json.JSONDecodeError:
            loi_cuoi = "trả về không phải JSON nên không khai được SHA"
            break                       # hỏi lại cũng vậy thôi
        if lan < so_lan - 1:
            ngu(nhip_s)
    raise KhongKetLuanDuoc(f"{url}: {loi_cuoi}")


def sha_prod(than: dict) -> str:
    khai = str(than.get("commit") or "")
    if not khai:
        raise KhongKetLuanDuoc(
            "dịch vụ không khai trường `commit` — ảnh dựng thiếu tệp SOURCE_SHA")
    return khai


def _chay(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=False)


def day_du_sha(sha_ngan: str) -> str:
    """Nở SHA 12 ký tự prod khai ra thành SHA đầy đủ trong kho này.

    Không nở được nghĩa là commit ấy không có ở đây — clone nông, hoặc prod
    chạy mã đã bị xoá khỏi lịch sử. Cả hai đều là "chưa kết luận được", KHÔNG
    phải "đã đúng".
    """
    kq = _chay(["git", "rev-parse", f"{sha_ngan}^{{commit}}"])
    if kq.returncode != 0:
        raise KhongKetLuanDuoc(
            f"kho này không có commit {sha_ngan} (clone nông, hoặc lịch sử đã "
            "bị viết lại) nên không so được")
    return kq.stdout.strip()


def prod_di_truoc(sha_prod: str, sha_main: str) -> bool:
    """Prod đang chạy một commit ĐỜI SAU của `sha_main`?

    Vì sao cần — đo thật 15/09, ngay lượt chạy thứ hai của chốt này: lượt CI
    của `5af86a3` đi tới bước D5 **sau khi** bản đẩy kế tiếp `f6384e0` đã lên
    prod. Chốt thấy prod khác commit của lượt mình và kết luận **"prod tụt
    lại"** — trong khi prod đang đi TRƯỚC.

    Đó là kêu nhầm, và kêu nhầm là thứ giết một bộ canh: `deploy-branch-drift`
    đã phải tránh đúng bẫy này, và backlog dự án ghi sẵn *bộ canh hay kêu nhầm
    thì người ta tắt nó đi, còn tệ hơn không có*.

    `merge-base --is-ancestor A B` trả 0 khi A là tổ tiên của B (hoặc bằng B).
    """
    return _chay(["git", "merge-base", "--is-ancestor",
                  sha_main, sha_prod]).returncode == 0


def nguon_da_doi(sha_a: str, sha_b: str, duong_dan: list[str]) -> list[str]:
    """Những đường dẫn nguồn khác nhau giữa hai commit. Rỗng = giống hệt."""
    kq = _chay(["git", "diff", "--name-only", sha_a, sha_b, "--", *duong_dan])
    if kq.returncode != 0:
        raise KhongKetLuanDuoc(f"git diff hỏng: {kq.stderr.strip()}")
    return [d for d in kq.stdout.splitlines() if d.strip()]


#: Ba kết cục có thể có. Gộp "đi trước" vào "đúng nhịp" thì mất thông tin;
#: gộp nó vào "tụt lại" thì chốt kêu nhầm mỗi lần hai lượt đẩy chồng nhau.
DUNG_NHIP, DI_TRUOC, TUT_LAI = "dung_nhip", "di_truoc", "tut_lai"


def kiem_mot_dich_vu(ten: str, url: str, sha_main: str, *,
                     doc=doc_health) -> tuple[str, str]:
    """Trả `(trạng thái, câu giải thích)`. Ném `KhongKetLuanDuoc` khi không rõ."""
    ngan = sha_prod(doc(url))
    day_du = day_du_sha(ngan)

    doi = nguon_da_doi(day_du, sha_main, NGUON[ten])
    if not doi:
        return DUNG_NHIP, (f"{ten}: prod chạy {ngan}, nguồn giống hệt "
                           f"{sha_main[:12]} — đúng nhịp")

    # Nguồn có khác, nhưng khác theo chiều NÀO? Prod đời sau nghĩa là một lượt
    # đẩy mới hơn đã lên trước khi lượt này chạy tới đây — lượt này đã cũ, và
    # chính lượt mới kia mới là nơi kiểm. Không phải lỗi.
    if prod_di_truoc(day_du, sha_main):
        return DI_TRUOC, (f"{ten}: prod chạy {ngan}, ĐỜI SAU của "
                          f"{sha_main[:12]} — một lượt đẩy mới hơn đã lên "
                          "trước; lượt kiểm này đã cũ")

    dau = ", ".join(doi[:5]) + (f" (và {len(doi) - 5} tệp nữa)" if len(doi) > 5 else "")
    return TUT_LAI, (f"{ten}: prod chạy {ngan} nhưng nguồn ĐÃ ĐỔI so với "
                     f"{sha_main[:12]} — {len(doi)} tệp: {dau}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sha-main", required=True, help="commit main phải chạy")
    ap.add_argument("--app", default="", help="URL /health của voxdub-app")
    ap.add_argument("--worker", default="", help="URL /health của worker")
    args = ap.parse_args()

    tut_lai: list[str] = []
    chua_ro: list[str] = []
    for ten, url in (("app", args.app), ("worker", args.worker)):
        if not url:
            continue
        try:
            trang_thai, cau = kiem_mot_dich_vu(ten, url, args.sha_main)
        except KhongKetLuanDuoc as e:
            # CHƯA XÁC MINH ĐƯỢC, không phải ĐÃ ĐÚNG. Cảnh báo to nhưng không
            # làm đỏ CI: một cú chập mạng biến thành lượt đỏ thì chẳng bao lâu
            # sẽ có người tắt chốt này đi. Đánh đổi có ý thức, ghi ra để lần
            # sau ai đọc còn biết đây là lựa chọn chứ không phải sơ suất.
            chua_ro.append(f"{ten}: {e}")
            print(f"::warning::D5 CHƯA XÁC MINH ĐƯỢC {ten} — {e}")
            continue
        nhan = {DUNG_NHIP: "  [ĐÚNG NHỊP] ", DI_TRUOC: "  [ĐỜI SAU]   ",
                TUT_LAI: "  [TỤT LẠI]   "}[trang_thai]
        print(nhan + cau)
        if trang_thai == TUT_LAI:
            tut_lai.append(cau)

    if tut_lai:
        print()
        print("::error::D5 — PROD ĐANG CHẠY MÃ CŨ. Lượt deploy gần nhất hoặc đã "
              "hỏng, hoặc bị bỏ qua vì phép so chỉ nhìn bản dựng trước chứ "
              "không nhìn prod. Deploy lại rồi đối chiếu /health.")
        for c in tut_lai:
            print(f"  - {c}")
        return 1
    if chua_ro and not tut_lai:
        print("\nD5: không kết luận được cho "
              f"{len(chua_ro)} dịch vụ — xem cảnh báo bên trên.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
