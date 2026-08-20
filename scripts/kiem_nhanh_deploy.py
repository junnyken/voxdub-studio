#!/usr/bin/env python3
"""Nhánh deploy có đang tụt lại so với `main` không? (mini-spec V90)

Vì sao có tệp này: `voxdub-app` và `voxdub-dub-worker` trên VAYS deploy từ
NHÁNH SINH TỰ ĐỘNG (`deploy/vays-control-server`, `deploy/vays-dub-worker`),
không phải từ `main`. Sửa `control_server/` rồi push `main` rồi bấm redeploy
thì VAYS build lại đúng mã CŨ — và **mọi chặng đều xanh**, không dấu hiệu nào.

Bẫy này đã sập hai lần (18-08 và 19-08). Lần thứ hai xảy ra dù runbook đã có
hẳn một mục cảnh báo. Kết luận: tài liệu không sửa được lỗi con người — phải
có cái tự kêu lên.

Chạy:
    python3 scripts/kiem_nhanh_deploy.py            # kiểm cả hai nhánh
    python3 scripts/kiem_nhanh_deploy.py --ci       # im lặng khi ổn, mã 1 khi lệch

So sánh bằng **hash cây thư mục của git**, không phải theo ngày tháng hay số
commit: nội dung giống nhau thì hash giống nhau, kể cả khi nhánh deploy được
sinh lại nhiều lần.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

#: (nhánh deploy, [(đường dẫn trên main, đường dẫn tương ứng trên nhánh deploy)])
#: Ánh xạ này PHẢI khớp đúng thứ hai script sinh nhánh chép sang — đọc
#: `cp -r` trong `gen_vays_*.sh` trước khi sửa. Ánh xạ sai làm bộ kiểm kêu
#: nhầm, mà một bộ kiểm hay kêu nhầm thì người ta tắt nó đi — còn tệ hơn
#: không có (bản đầu của chính tệp này đã kêu nhầm 99 tệp cho worker).
NHANH = {
    "deploy/vays-control-server": [
        ("control_server", "webapp/control_server"),
        ("website", "webapp/website"),
    ],
    "deploy/vays-dub-worker": [
        # Worker gom từ nhiều nguồn: mã lõi + đúng 3 script cài đặt + tệp
        # chạy riêng của worker (xem gen_vays_dub_worker_branch.sh).
        ("autodub", "dub-worker/autodub"),
    ],
}

#: Tệp lẻ (không phải cả thư mục) cũng phải theo dõi, kèm ánh xạ riêng.
TEP_LE = {
    "deploy/vays-dub-worker": [
        ("control_server/worker-dub/dub_worker.py", "dub-worker/dub_worker.py"),
        ("scripts/setup_whisper.py", "dub-worker/scripts/setup_whisper.py"),
        ("scripts/setup_vieneu.py", "dub-worker/scripts/setup_vieneu.py"),
        ("scripts/setup_translate_local.py",
         "dub-worker/scripts/setup_translate_local.py"),
    ],
}

#: Thư mục sinh ra lúc build, không tính vào so sánh.
BO_QUA = ("node_modules", "dist", "__pycache__", ".venv")


def chay(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          check=False).stdout.strip()


def co_ref(ref: str) -> bool:
    return subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref],
                          capture_output=True).returncode == 0


def hash_cay(ref: str, duong_dan: str) -> str:
    """Hash nội dung một thư mục ở một ref. Rỗng nếu không có thư mục đó."""
    ra = chay("rev-parse", f"{ref}:{duong_dan}")
    return ra if ra and not ra.startswith("fatal") else ""


def _liet_ke(ref: str, duong_dan: str) -> dict[str, str]:
    out = chay("ls-tree", "-r", f"{ref}:{duong_dan}")
    tep: dict[str, str] = {}
    for dong in out.splitlines():
        if not dong.strip():
            continue
        phan, _, ten = dong.partition("\t")
        cot = phan.split()
        if len(cot) >= 3 and not any(b in ten for b in BO_QUA):
            tep[ten] = cot[2]
    return tep


def kiem_mot_nhanh(nhanh: str, cap: list[tuple[str, str]],
                   goc: str = "main") -> list[str]:
    """Danh sách khác biệt; rỗng nghĩa là nhánh deploy đang khớp `main`."""
    ref_deploy = nhanh if co_ref(nhanh) else f"github/{nhanh}"
    if not co_ref(ref_deploy):
        return [f"không tìm thấy nhánh {nhanh} (thử `git fetch github {nhanh}`)"]

    lech: list[str] = []
    for tren_main, tren_deploy in TEP_LE.get(nhanh, []):
        a = chay("rev-parse", f"{goc}:{tren_main}")
        b = chay("rev-parse", f"{ref_deploy}:{tren_deploy}")
        if a and b and a != b:
            lech.append(f"{tren_main} đã đổi nhưng nhánh deploy còn bản cũ")
        elif not b:
            lech.append(f"{tren_deploy} chưa có trên nhánh deploy")

    for tren_main, tren_deploy in cap:
        if hash_cay(goc, tren_main) == hash_cay(ref_deploy, tren_deploy):
            continue
        a = _liet_ke(goc, tren_main)
        b = _liet_ke(ref_deploy, tren_deploy)
        thieu = sorted(set(a) - set(b))
        khac = sorted(t for t in set(a) & set(b) if a[t] != b[t])
        thua = sorted(set(b) - set(a))
        chi_tiet = []
        if thieu:
            chi_tiet.append(f"{len(thieu)} tệp CHƯA có trên nhánh deploy "
                            f"(vd {thieu[0]})")
        if khac:
            chi_tiet.append(f"{len(khac)} tệp khác nội dung (vd {khac[0]})")
        if thua:
            chi_tiet.append(f"{len(thua)} tệp thừa (vd {thua[0]})")
        if chi_tiet:
            lech.append(f"{tren_main}/ ⇄ {tren_deploy}/: " + "; ".join(chi_tiet))
    return lech


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ci", action="store_true",
                        help="chỉ in khi có vấn đề")
    parser.add_argument("--goc", default="main")
    args = parser.parse_args()

    tong_lech = 0
    for nhanh, cap in NHANH.items():
        lech = kiem_mot_nhanh(nhanh, cap, args.goc)
        if lech:
            tong_lech += 1
            print(f"[!!] {nhanh} ĐANG TỤT LẠI so với {args.goc}:")
            for d in lech:
                print(f"    {d}")
        elif not args.ci:
            print(f"[ok] {nhanh} khớp {args.goc}")

    if tong_lech:
        print()
        print("Deploy bây giờ sẽ build MÃ CŨ và vẫn báo thành công.")
        print("Chạy trước khi redeploy:")
        print("    scripts/gen_vays_control_server_branch.sh")
        print("    scripts/gen_vays_dub_worker_branch.sh")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
