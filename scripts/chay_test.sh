#!/usr/bin/env bash
# Chạy bộ test — tự cài lại thư viện hệ thống nếu máy vừa mất chúng.
#
# Máy workspace giữ `/home/coder` trên đĩa riêng nhưng dựng lại `/usr` từ image
# mỗi lần khởi động, nên `libGL`, `libxkbcommon`, `libfontconfig`, `libglib` và
# `ffmpeg` biến mất đều đặn giữa hai phiên. Đã xảy ra ít nhất ba lần
# (2026-08-21, 2026-08-26, 2026-08-27), mỗi lần ngốn một vòng đi tìm lỗi ở
# nhầm chỗ.
#
# Tệp này KHÔNG thay chốt chặn trong `tests/test_kiem_moi_truong.py` — chốt đó
# vẫn là thứ ngăn chuyện nguy hiểm nhất (bộ test báo xanh với số thấp hơn vì
# hàng chục tệp GUI không import nổi). Đây chỉ bỏ bước gõ tay ở giữa.
#
# Dùng:
#     bash scripts/chay_test.sh            # cả bộ
#     bash scripts/chay_test.sh -q -k gia  # tham số truyền thẳng cho pytest
set -euo pipefail

GOC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$GOC"

bash scripts/cai_moi_truong_test.sh --neu-thieu

export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
exec python3 -m pytest "$@"
