"""FEATURES.md phải khớp mã — vì nó được gửi cho AI khác đọc.

Tệp này không phải tài liệu nội bộ: chủ dự án gửi nó cho một trợ lý AI khác
để nhờ phân tích và đề xuất nâng cấp. Một con số cũ trong đó không gây lỗi
chạy, nhưng đẻ ra cả một bản đề xuất dựa trên tiền đề sai — đúng thứ mục
"§8 Những nhầm lẫn thường gặp" trong chính tệp đó được viết ra để chặn.

Chỉ canh những khẳng định MÁY ĐỌC ĐƯỢC (số phiên bản, giá, hạn mức). Phần
văn xuôi không canh được, và cố canh thì chỉ tạo ra bộ canh kêu nhầm.
"""
from __future__ import annotations

import os
import re

import pytest

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(ten: str) -> str:
    return open(os.path.join(GOC, ten), encoding="utf-8").read()


@pytest.fixture(scope="module")
def tai_lieu() -> str:
    return _doc("FEATURES.md")


def test_phien_ban_khop_app(tai_lieu):
    that = re.search(r'APP_VERSION = "([\d.]+)"', _doc("autodub_gui/app.py")).group(1)
    assert f"`{that}`" in tai_lieu, (
        f"tài liệu chưa cập nhật phiên bản — app đang là {that}")


def test_so_trang_giao_dien_khop(tai_lieu):
    that = re.search(r"PAGE_COUNT = (\d+)", _doc("autodub_gui/app.py")).group(1)
    ghi = re.search(r"\*\*(\d+) trang\*\*", tai_lieu)
    assert ghi and ghi.group(1) == that, (
        f"tài liệu ghi {ghi.group(1) if ghi else '?'} trang, mã có {that}")


def test_moc_tu_cat_tep_dai_khop(tai_lieu):
    that = re.search(r"PHUT_TU_CAT = (\d+)",
                     _doc("autodub/transcribe_tool.py")).group(1)
    assert f"({that} phút) thì tự cắt" in tai_lieu


def test_han_muc_gop_cau_khop(tai_lieu):
    src = _doc("autodub/transcribe_tool.py")
    giay = float(re.search(r"GOP_DICH_TOI_DA_GIAY = ([\d.]+)", src).group(1))
    chu = re.search(r"GOP_DICH_TOI_DA_CHU = (\d+)", src).group(1)
    assert f"{int(giay)} giây/{chu} chữ" in tai_lieu, (
        "hạn mức gộp câu trong tài liệu không khớp mã")


def test_gia_moi_tac_vu_tro_ly_khop(tai_lieu):
    """Giá là thứ người đọc tài liệu dùng để tính bài toán kinh tế — sai một
    con số ở đây là sai cả kết luận nên hay không nên dùng tính năng."""
    cfg = _doc("control_server/src/services/config.service.js")
    lech = []
    for ten, gia in re.findall(r"'credit\.cost\.assist\.([a-z_]+)': (\d+)", cfg):
        if "." in ten:
            continue                      # biến thể (scene_script.co_anh)
        ghi = re.search(rf"`{ten}`.*?\|\s*\**(\d+) Vox", tai_lieu)
        if ghi is None:
            lech.append(f"{ten}: không có trong bảng tài liệu")
        elif ghi.group(1) != gia:
            lech.append(f"{ten}: tài liệu {ghi.group(1)} Vox, mã {gia} Vox")
    assert not lech, lech


def test_gia_vox_quy_doi_khong_doi_le(tai_lieu):
    assert "1 Vox = 10 VNĐ" in tai_lieu
