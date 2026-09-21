import sys

# Chế độ tự kiểm bản đóng gói (mini-spec I0-FDE) phải được rẽ TRƯỚC khi nhập
# `autodub_gui.app` — nhập tệp đó là kéo cả PySide6 vào tiến trình, mà lượt
# kiểm này chạy hoàn toàn không giao diện. Rẽ ở đây cũng giữ đúng lời hứa
# "không đụng vào đường chạy bình thường": không có cờ `--tu-kiem-goi` thì
# dòng dưới chạy y như trước.
from autodub_gui.tu_kiem_goi import chay as _tu_kiem, co_yeu_cau_tu_kiem

if __name__ == "__main__":
    if co_yeu_cau_tu_kiem(sys.argv[1:]):
        sys.exit(_tu_kiem(sys.argv[1:]))

    from autodub_gui.app import main

    sys.exit(main())
