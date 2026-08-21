#!/usr/bin/env python3
"""Máy chủ vừa deploy có THẬT SỰ chạy mã mới không? (mini-spec V90)

Trạng thái deploy `succeeded` không chứng minh được gì: lần 19-08 tất cả 11
chặng đều xanh, container chạy, MongoDB nối — mà build lại đúng mã cũ.

Phép kiểm đáng tin là **so một cửa MỚI với một cửa CŨ**:

    POST /v1/ai/translate  -> 400   (tồn tại, chỉ sai dữ liệu)
    POST /v1/ai/assist     -> 404   ← chưa có mã mới

Chỉ thử cửa mới thì 404 dễ bị hiểu nhầm là "route đăng ký sai"; phải có cái
đối chứng. Script này tự làm việc đó.

Dùng:
    python3 scripts/kiem_deploy_song.py https://voxdub-app.cmc-1.vibenode.matbao.ai
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

#: (mô tả, phương thức, đường dẫn, dữ liệu gửi, các mã CHẤP NHẬN)
#: Cửa "cũ" là mốc đối chứng — nó phải sống ở MỌI bản. Cửa "mới" là thứ đang
#: kiểm. Thêm tính năng mới thì thêm một dòng "mới" ở đây.
CU = [
    ("cửa dịch (mốc đối chứng)", "POST", "/v1/ai/translate", {}, {400, 401}),
    ("cửa sức khoẻ", "GET", "/health", None, {200}),
]
MOI = [
    ("cổng trợ lý (V89)", "POST", "/v1/ai/assist",
     {"jobId": "kiemtra12345", "task": "music_suggest", "input": {}}, {400, 401}),
    ("thống kê trợ lý (V89)", "GET", "/v1/admin/analytics/assist", None, {401}),
    # C1 — cửa dựng ảnh sản phẩm. 404 ở đây nghĩa là máy chủ đang chạy mã CŨ.
    ("dựng bối cảnh ảnh (C1)", "POST", "/v1/ai/product-scene",
     {"jobId": "kiemtra12345", "scene": "ban_go",
      "image": {"mimeType": "image/jpeg", "data": "eA=="}}, {400, 401}),
    # Tác vụ kiểm tuân thủ phải nằm trong enum: qua được schema thì mới tới
    # tầng xác thực (NO_TOKEN), còn chưa deploy thì schema đá ra 400.
    ("tác vụ kiểm bao bì (C1)", "POST", "/v1/ai/assist",
     {"jobId": "kiemtra12345", "task": "packaging_check", "input": {}}, {401}),
]
#: Tác vụ bịa PHẢI bị chặn ngay ở tầng schema — đây là lớp chặn chi phí số 1.
CHAN = ("danh sách tác vụ đóng", "POST", "/v1/ai/assist",
        {"jobId": "kiemtra12345", "task": "tac_vu_khong_co_that", "input": {}},
        {400})


def goi(base: str, method: str, path: str, body) -> int:
    du_lieu = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"{base.rstrip('/')}{path}", data=du_lieu, method=method,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:  # noqa: BLE001
        print(f"    (không gọi được: {e})")
        return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    base = sys.argv[1]
    print(f"Kiểm {base}\n")

    hong = 0
    for nhom, ten_nhom in ((CU, "Mốc đối chứng (phải sống ở MỌI bản)"),
                           (MOI, "Mã mới (thứ đang kiểm)")):
        print(ten_nhom)
        for mo_ta, method, path, body, nhan in nhom:
            ma = goi(base, method, path, body)
            dat = ma in nhan
            print(f"  {'[ok]' if dat else '[!!]'} {ma:3d}  {method:4s} "
                  f"{path}  — {mo_ta}")
            if not dat:
                hong += 1
                if nhom is MOI and ma == 404:
                    print("       404 ở cửa mới trong khi cửa cũ sống = máy chủ "
                          "đang chạy MÃ CŨ.")
                    print("       Chạy: scripts/deploy_vays.sh app  rồi redeploy.")
        print()

    mo_ta, method, path, body, nhan = CHAN
    ma = goi(base, method, path, body)
    dat = ma in nhan
    print(f"Lớp chặn chi phí\n  {'[ok]' if dat else '[!!]'} "
          f"{ma:3d}  {mo_ta}")
    if not dat:
        hong += 1

    print()
    print("KẾT LUẬN: " + ("máy chủ đang chạy mã mới." if not hong
                          else f"{hong} phép kiểm KHÔNG đạt."))
    return 1 if hong else 0


if __name__ == "__main__":
    sys.exit(main())
