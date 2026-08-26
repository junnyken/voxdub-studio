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


# --- Vá LỚP, không chỉ vá điểm ------------------------------------------
#
# Cái nút kia sai được là vì mô tả đầu tệp `music_suggest.py` cũng sai y hệt:
# viết ở V88 ("chạy offline, không tốn Vox"), rồi V89 thêm đường hỏi máy chủ
# vào CHÍNH tệp đó mà không ai sửa lại câu mô tả. Người viết giao diện đọc mô
# tả ấy, tin nó, và chép nguyên ý sang tooltip.
#
# Nên luật ở đây không phải "cấm chữ miễn phí" — mà là: tệp nào TIÊU ĐƯỢC Vox
# (có gọi `get_client(`) mà mô tả đầu tệp có hứa miễn phí thì phải nói luôn
# đường tốn tiền giá bao nhiêu. Hứa một nửa sự thật là cách sai đã xảy ra.

import ast

HUA_MIEN_PHI = ("không tốn vox", "không tốn phí", "không tốn gì", "miễn phí")
NOI_RO_GIA = (r"trừ\s+\d+\s+vox", r"tính phí", r"vox mỗi lượt", r"bị tính")

#: Miễn trừ PHẢI kèm lý do viết ra — danh sách không lý do là danh sách sẽ dài
#: dần ra cho tới lúc bộ canh chẳng canh gì nữa.
MIEN_TRU = {
    "autodub_gui/credit_widget.py":
        "Chữ 'miễn phí' ở đây đã có điều kiện rõ ràng ngay trong câu: chỉ khi "
        "máy chủ TẮT hệ thống credit (creditEnabled=false) — widget tự ẩn "
        "luôn lúc đó. Không phải lời hứa về một thao tác nào.",
}


def _tep_tieu_duoc_vox():
    """Mọi tệp .py có gọi `get_client(` — tức là có thể tiêu Vox."""
    for goc in ("autodub", "autodub_gui"):
        for thu, _dirs, tep in os.walk(os.path.join(GOC, goc)):
            if any(x in thu for x in (".venv", "__pycache__")):
                continue
            for f in sorted(tep):
                if not f.endswith(".py"):
                    continue
                duong = os.path.join(thu, f)
                src = open(duong, encoding="utf-8").read()
                if "get_client(" in src:
                    yield os.path.relpath(duong, GOC).replace(os.sep, "/"), src


def test_tep_tieu_duoc_vox_khong_duoc_hua_mien_phi_nua_voi():
    thieu = []
    for ten, src in _tep_tieu_duoc_vox():
        if ten in MIEN_TRU:
            continue
        try:
            doc = (ast.get_docstring(ast.parse(src)) or "").lower()
        except SyntaxError:
            continue
        if not any(c in doc for c in HUA_MIEN_PHI):
            continue
        if not any(re.search(r, doc) for r in NOI_RO_GIA):
            thieu.append(ten)
    assert not thieu, (
        "tệp tiêu được Vox nhưng mô tả đầu tệp chỉ nói đường miễn phí, không "
        f"nói đường tốn tiền giá bao nhiêu: {thieu}")


def test_danh_sach_mien_tru_khong_duoc_phinh_ra_vo_co():
    """Mỗi miễn trừ phải trỏ tới tệp có thật và mang lý do đủ dài để đọc
    hiểu — không thì nó chỉ là cách làm bộ canh im lặng."""
    for ten, ly_do in MIEN_TRU.items():
        assert os.path.isfile(os.path.join(GOC, ten)), f"miễn trừ trỏ vào tệp không có: {ten}"
        assert len(ly_do) > 60, f"lý do miễn trừ quá sơ sài: {ten}"


def test_mo_ta_music_suggest_da_noi_ro_hai_duong():
    """Đây là tệp đã đẻ ra bug — giữ riêng một chốt cho nó."""
    src = open(os.path.join(GOC, "autodub", "media", "music_suggest.py"),
               encoding="utf-8").read()
    doc = ast.get_docstring(ast.parse(src)) or ""
    assert "2 Vox" in doc, "mô tả không nói giá của đường hỏi máy chủ"
    assert "V89" in doc, "mô tả không nhắc đường máy chủ được thêm từ đâu"
