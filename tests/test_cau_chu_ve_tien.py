"""Câu chữ nói về TIỀN phải khớp với thứ mã thật sự làm.

Bug thật, tìm ra 22/8/2026 trong lượt rà soát: nút "Gợi ý từ nội dung video"
ghi tooltip *"Chạy ngay trên máy, không tốn Vox"*. Đúng ở V88 (đo bằng luật),
sai từ V89 — khi có tài khoản, nó hỏi trợ lý trên máy chủ và **trừ 2 Vox**.

Hứa miễn phí rồi trừ tiền là kiểu sai tệ nhất trong mọi kiểu sai về câu chữ:
người dùng không có cách nào biết mình vừa mất tiền cho tới khi nhìn ví.
"""
from __future__ import annotations

import os
import re

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _tooltip_goi_y_nhac() -> str:
    src = open(os.path.join(GOC, "autodub_gui", "pages", "editor_panels.py"),
               encoding="utf-8").read()
    khoi = src.split("self.btn_suggest_music.setToolTip(", 1)[1].split(")", 1)[0]
    # Ghép các chuỗi lại, bỏ dấu nháy
    return " ".join(re.findall(r'"([^"]*)"', khoi))


def test_khong_hua_mien_phi_cho_viec_co_the_ton_tien():
    chu = _tooltip_goi_y_nhac()
    assert "không tốn Vox" not in chu, (
        "nút này gọi máy chủ khi có tài khoản — hứa không tốn Vox là sai")


def test_noi_ro_ca_hai_duong_va_gia_cua_duong_ton_tien():
    chu = _tooltip_goi_y_nhac()
    assert "2 Vox" in chu, "không nói giá thì người dùng vẫn bị bất ngờ"
    assert "tài khoản" in chu, "phải nói rõ khi nào tốn, khi nào không"


def test_gia_trong_cau_chu_khop_bang_gia_that():
    """Đổi giá trên máy chủ mà quên sửa câu chữ thì lại thành hứa sai."""
    cfg = open(os.path.join(GOC, "control_server", "src", "services",
                            "config.service.js"), encoding="utf-8").read()
    m = re.search(r"'credit\.cost\.assist\.music_suggest':\s*(\d+)", cfg)
    assert m, "không tìm thấy giá music_suggest trong cấu hình máy chủ"
    assert f"{m.group(1)} Vox" in _tooltip_goi_y_nhac(), (
        f"cấu hình tính {m.group(1)} Vox nhưng câu chữ nói khác")
