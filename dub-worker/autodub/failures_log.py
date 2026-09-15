"""Log lỗi tập trung cho batch — mini-spec V24 (docs/PLAN.md, Phase F).

``failures.jsonl`` nằm CẠNH ``batch_state.json`` — 2 file ĐỘC LẬP, không gộp
field (Constraint 3 của mini-spec): ``batch_state.json`` vẫn là nguồn DUY
NHẤT cho logic resume của ``run_batch()``, không đổi format. File này chỉ
GHI THÊM (append-only), mục đích DUY NHẤT là cho người vận hành đọc/`grep`/
`jq` qua NHIỀU lượt batch để thấy lỗi nào lặp lại nhiều nhất — không có nơi
nào trong app đọc lại hay sửa file này.
"""
from __future__ import annotations

import json
import os


def failures_path(state_path: str) -> str:
    """``failures.jsonl`` cạnh ``batch_state.json`` — cùng thư mục."""
    return os.path.join(os.path.dirname(os.path.abspath(state_path)), "failures.jsonl")


def append_failure(entry: dict, path: str) -> None:
    """Ghi THÊM 1 dòng JSON vào ``path`` (tạo thư mục nếu chưa có).

    ``entry`` nên có ít nhất: video (url/label), lỗi, transient (bool), số
    lần đã thử, timestamp. Hàm này KHÔNG tự lấy giờ hệ thống (giữ thuần —
    caller truyền timestamp từ ngoài để test được xác định, xem
    ``batch.py::_run_items`` tham số ``now_fn``).
    """
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
