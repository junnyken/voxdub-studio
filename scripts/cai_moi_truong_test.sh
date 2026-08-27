#!/usr/bin/env bash
# Cài thư viện hệ thống để chạy được bộ test trên máy phát triển (Ubuntu/Debian).
#
# Vì sao có tệp này: máy workspace mất các gói ở tầng `/usr` giữa hai phiên
# làm việc (đã xảy ra thật 2026-08-21 — buổi sáng 1716 test xanh, buổi tối 24
# tệp test GUI không import nổi vì thiếu `libGL.so.1`, rồi 21 test đỏ vì mất
# `ffmpeg`). Không cái nào là lỗi trong mã, nhưng cả hai ngốn thời gian đi tìm
# lỗi ở nhầm chỗ.
#
# Danh sách này là BỘI của danh sách trong `.github/workflows/test.yml` —
# có test đối chiếu (`tests/test_kiem_moi_truong.py`), CI thêm gói mà quên
# thêm ở đây thì đỏ. Máy chạy CI của GitHub có sẵn vài gói mà workspace trần
# không có (`libfontconfig1`, `libfreetype6`), nên ở đây nhiều hơn.
#
# Dùng:
#     bash scripts/cai_moi_truong_test.sh
set -euo pipefail

GOI=(
  # Qt/PySide6 — thiếu là 24 tệp test GUI không import nổi
  libegl1 libgl1 libglib2.0-0 libdbus-1-3
  libfontconfig1 libfreetype6
  libxkbcommon0 libxkbcommon-x11-0
  libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1
  libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xfixes0
  libxcb-xinerama0
  # Vài test gọi ffmpeg thật (ghép video, trộn tiếng) — thiếu là 21 test đỏ
  ffmpeg
)

# `--neu-thieu`: không có gì thiếu thì THOÁT NGAY, không đụng apt.
#
# Vì sao cần: máy workspace giữ lại `/home/coder` (đĩa riêng) nhưng dựng lại
# `/usr` từ image mỗi lần khởi động — nên các gói này biến mất đều đặn, không
# phải do ai xoá. Chốt chặn trong `tests/test_kiem_moi_truong.py` đã ngăn được
# chuyện nguy hiểm (báo xanh giả), nhưng vẫn tốn một vòng "chạy test → đọc lỗi
# → chạy script → chạy lại test" mỗi phiên. Cờ này cho `scripts/chay_test.sh`
# tự chữa mà không làm chậm lượt chạy khi máy đang lành.
if [ "${1:-}" = "--neu-thieu" ]; then
  if QT_QPA_PLATFORM=offscreen python3 -c "from PySide6.QtWidgets import QWidget" \
       >/dev/null 2>&1 && command -v ffmpeg >/dev/null 2>&1; then
    exit 0
  fi
  echo "Thiếu thư viện hệ thống (máy workspace dựng lại /usr mỗi phiên) — cài lại…"
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "Máy này không dùng apt — tự cài tương đương: ${GOI[*]}" >&2
  exit 1
fi

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 || { echo "Cần quyền root hoặc sudo." >&2; exit 1; }
  SUDO="sudo"
fi

echo "Cài ${#GOI[@]} gói cho bộ test…"
$SUDO apt-get update -qq
$SUDO apt-get install -y --no-install-recommends "${GOI[@]}"

echo
echo "Kiểm lại bằng chính thứ đã hỏng:"
QT_QPA_PLATFORM=offscreen python3 -c "from PySide6.QtWidgets import QWidget" \
  && echo "  [ok] PySide6.QtWidgets nạp được"
command -v ffmpeg >/dev/null && echo "  [ok] ffmpeg: $(command -v ffmpeg)"
echo
echo "Xong. Chạy: pytest -q"
